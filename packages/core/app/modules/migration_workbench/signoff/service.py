"""Sign-off workflow service — DB-backed implementation.

Replaces the in-memory dict from the stub (Batch B1). All state is now
persisted to signoff_requests + signoff_checklist_items (added in Batch B2).

Design decisions:
- Service calls session.flush() but never session.commit(). The router owns
  the transaction boundary and commits after each successful mutating call.
- approved_at is always set server-side (datetime.now(timezone.utc)).
  The client never provides a timestamp for approvals.
- approved_by is a free-text name string (no FK to users — multi-user auth
  is SPEC §16 non-goal for MVP).
- _orm_to_pydantic() bridges the structural mismatch between the ORM
  (flat checklist_items list, comments_json JSONB) and the Pydantic response
  schema (nested SignoffChecklist, comments list[str]).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.migration_workbench.models import (
    ETLPackage,
    SignoffChecklistItem as ORMChecklistItem,
    SignoffRequest as ORMSignoffRequest,
)
from app.modules.migration_workbench.signoff.schemas import (
    ApproveSignoffRequest,
    ChecklistItem,
    ChecklistItemStatus,
    CreateSignoffRequest,
    RejectSignoffRequest,
    SignoffChecklist,
    SignoffRequest,
    SignoffRequestView,
    SignoffStatus,
    SignoffType,
    UpdateChecklistItem,
)

log = structlog.get_logger(__name__)


# Default checklists per sign-off type (source of truth for item creation)
DEFAULT_CHECKLISTS: dict[SignoffType, list[dict]] = {
    SignoffType.STATIC_ANALYSIS: [
        {
            "item_key": "sa_01",
            "title": "Code review completed",
            "description": "Generated notebooks reviewed by senior engineer",
            "category": "review",
            "required": True,
        },
        {
            "item_key": "sa_02",
            "title": "Security scan passed",
            "description": "No credentials or secrets in generated code",
            "category": "security",
            "required": True,
        },
        {
            "item_key": "sa_03",
            "title": "Performance review",
            "description": "Reviewed for Photon compatibility and join optimization",
            "category": "performance",
            "required": False,
        },
        {
            "item_key": "sa_04",
            "title": "Documentation complete",
            "description": "README and inline comments are adequate",
            "category": "documentation",
            "required": True,
        },
    ],
    SignoffType.PARALLEL_RUN: [
        {
            "item_key": "pr_01",
            "title": "Parallel run duration met",
            "description": "Source and target ran in parallel for required period",
            "category": "execution",
            "required": True,
        },
        {
            "item_key": "pr_02",
            "title": "Row counts match",
            "description": "Reconciliation shows matching row counts",
            "category": "validation",
            "required": True,
            # auto_populated = True when set by ReconciliationRun (Batch B4b)
        },
        {
            "item_key": "pr_03",
            "title": "Checksums match",
            "description": "Data checksums are identical",
            "category": "validation",
            "required": True,
            # auto_populated = True when set by ReconciliationRun (Batch B4b)
        },
        {
            "item_key": "pr_04",
            "title": "Business validation",
            "description": "Business stakeholders verified sample outputs",
            "category": "business",
            "required": True,
        },
        {
            "item_key": "pr_05",
            "title": "Performance acceptable",
            "description": "Target execution time within SLA",
            "category": "performance",
            "required": False,
        },
    ],
    SignoffType.CUTOVER: [
        {
            "item_key": "co_01",
            "title": "Parallel run sign-off obtained",
            "description": "Parallel run sign-off is approved",
            "category": "prerequisite",
            "required": True,
        },
        {
            "item_key": "co_02",
            "title": "Rollback plan documented",
            "description": "Rollback procedure is documented and tested",
            "category": "risk",
            "required": True,
        },
        {
            "item_key": "co_03",
            "title": "Monitoring configured",
            "description": "Alerts and dashboards set up for target system",
            "category": "operations",
            "required": True,
        },
        {
            "item_key": "co_04",
            "title": "Stakeholder approval",
            "description": "Business owner approved cutover date",
            "category": "business",
            "required": True,
        },
        {
            "item_key": "co_05",
            "title": "Source system disable plan",
            "description": "Plan for disabling source after cutover",
            "category": "operations",
            "required": False,
        },
    ],
    SignoffType.POST_MIGRATION: [
        {
            "item_key": "pm_01",
            "title": "Production verification",
            "description": "Target system verified in production",
            "category": "validation",
            "required": True,
        },
        {
            "item_key": "pm_02",
            "title": "Source system decommissioned",
            "description": "Source jobs disabled or removed",
            "category": "cleanup",
            "required": False,
        },
        {
            "item_key": "pm_03",
            "title": "Documentation updated",
            "description": "Runbooks and architecture docs updated",
            "category": "documentation",
            "required": True,
        },
        {
            "item_key": "pm_04",
            "title": "Knowledge transfer complete",
            "description": "Team trained on new system",
            "category": "knowledge",
            "required": True,
        },
    ],
}

_TERMINAL_STATUSES = {SignoffStatus.APPROVED, SignoffStatus.REJECTED}
_COMPLETED_ITEM_STATUSES = {
    ChecklistItemStatus.PASSED,
    ChecklistItemStatus.SKIPPED,
    ChecklistItemStatus.NOT_APPLICABLE,
}


class SignoffService:
    """DB-backed sign-off workflow service."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ── Public API ─────────────────────────────────────────────────────────

    def create_signoff(
        self,
        project_id: uuid.UUID,
        request: CreateSignoffRequest,
    ) -> SignoffRequest:
        """Create a new sign-off request with default checklist items."""
        orm = ORMSignoffRequest(
            project_id=project_id,
            signoff_type=request.signoff_type.value,
            status=SignoffStatus.DRAFT.value,
            package_ids=request.package_ids,
            wave_number=request.wave_number,
            title=request.title,
            description=request.description,
            requested_by=request.requested_by,
            requested_at=datetime.now(timezone.utc),
            comments_json=[],
        )
        self.session.add(orm)
        self.session.flush()  # assign orm.id before creating child rows

        for item_def in DEFAULT_CHECKLISTS.get(request.signoff_type, []):
            self.session.add(
                ORMChecklistItem(
                    signoff_id=orm.id,
                    item_key=item_def["item_key"],
                    title=item_def["title"],
                    description=item_def.get("description"),
                    category=item_def.get("category", "general"),
                    required=item_def.get("required", True),
                    status=ChecklistItemStatus.NOT_STARTED.value,
                )
            )

        self.session.flush()

        # Re-fetch with checklist items loaded to build the response
        return self._fetch_and_convert(orm.id)

    def get_signoff(self, signoff_id: uuid.UUID) -> SignoffRequest | None:
        """Get a sign-off request by ID, including all checklist items."""
        orm = self._fetch_orm(signoff_id)
        return self._orm_to_pydantic(orm) if orm else None

    def list_signoffs(
        self,
        project_id: uuid.UUID,
        status: SignoffStatus | None = None,
        signoff_type: SignoffType | None = None,
        limit: int = 50,
    ) -> list[SignoffRequestView]:
        """List sign-off requests for a project."""
        stmt = (
            select(ORMSignoffRequest)
            .where(ORMSignoffRequest.project_id == project_id)
            .options(selectinload(ORMSignoffRequest.checklist_items))
            .order_by(ORMSignoffRequest.created_at.desc())
            .limit(limit)
        )
        if status is not None:
            stmt = stmt.where(ORMSignoffRequest.status == status.value)
        if signoff_type is not None:
            stmt = stmt.where(ORMSignoffRequest.signoff_type == signoff_type.value)

        rows = self.session.execute(stmt).scalars().all()
        return [self._orm_to_view(row) for row in rows]

    def submit_signoff(self, signoff_id: uuid.UUID) -> SignoffRequest:
        """Move a sign-off from DRAFT to PENDING."""
        orm = self._get_or_raise(signoff_id)

        if orm.status != SignoffStatus.DRAFT.value:
            raise ValueError(f"Sign-off is not in DRAFT status: {orm.status}")

        incomplete = self._required_incomplete(orm)
        if incomplete:
            raise ValueError(
                f"Cannot submit: {len(incomplete)} required checklist "
                f"items are incomplete"
            )

        orm.status = SignoffStatus.PENDING.value
        self.session.flush()
        return self._orm_to_pydantic(orm)

    def update_checklist_item(
        self,
        signoff_id: uuid.UUID,
        update: UpdateChecklistItem,
    ) -> SignoffRequest:
        """Update a single checklist item within a sign-off."""
        orm = self._get_or_raise(signoff_id)

        item = self.session.execute(
            select(ORMChecklistItem).where(
                ORMChecklistItem.signoff_id == signoff_id,
                ORMChecklistItem.item_key == update.item_id,
            )
        ).scalar_one_or_none()

        if not item:
            raise ValueError(f"Checklist item '{update.item_id}' not found")

        if update.status is not None:
            item.status = update.status.value
            if update.status in (ChecklistItemStatus.PASSED, ChecklistItemStatus.FAILED):
                item.completed_at = datetime.now(timezone.utc)
                if update.completed_by:
                    item.completed_by = update.completed_by

        if update.evidence is not None:
            item.evidence = update.evidence
        if update.notes is not None:
            item.notes = update.notes

        self.session.flush()
        return self._orm_to_pydantic(orm)

    def approve_signoff(
        self,
        signoff_id: uuid.UUID,
        approval: ApproveSignoffRequest,
    ) -> SignoffRequest:
        """Approve a PENDING sign-off. approved_at is set server-side."""
        orm = self._get_or_raise(signoff_id)

        if orm.status != SignoffStatus.PENDING.value:
            raise ValueError(f"Sign-off is not PENDING: {orm.status}")

        failed = [
            i for i in orm.checklist_items
            if i.status == ChecklistItemStatus.FAILED.value
        ]
        if failed:
            raise ValueError(
                f"Cannot approve: {len(failed)} checklist items have FAILED status"
            )

        orm.status = SignoffStatus.APPROVED.value
        orm.approved_by = approval.approved_by
        orm.approved_at = datetime.now(timezone.utc)  # always server-generated

        if approval.comments:
            comments = list(orm.comments_json or [])
            comments.append(f"[APPROVED] {approval.comments}")
            orm.comments_json = comments

        # Bump package statuses
        for pkg_id in (orm.package_ids or []):
            pkg = self.session.get(ETLPackage, pkg_id)
            if pkg:
                if orm.signoff_type == SignoffType.CUTOVER.value:
                    pkg.status = "migrated"
                elif orm.signoff_type == SignoffType.POST_MIGRATION.value:
                    pkg.status = "verified"
                self.session.add(pkg)

        self.session.flush()
        return self._orm_to_pydantic(orm)

    def reject_signoff(
        self,
        signoff_id: uuid.UUID,
        rejection: RejectSignoffRequest,
    ) -> SignoffRequest:
        """Reject a PENDING sign-off."""
        orm = self._get_or_raise(signoff_id)

        if orm.status != SignoffStatus.PENDING.value:
            raise ValueError(f"Sign-off is not PENDING: {orm.status}")

        orm.status = SignoffStatus.REJECTED.value
        orm.rejection_reason = rejection.reason

        comments = list(orm.comments_json or [])
        comments.append(f"[REJECTED by {rejection.rejected_by}] {rejection.reason}")
        orm.comments_json = comments

        self.session.flush()
        return self._orm_to_pydantic(orm)

    def cancel_signoff(self, signoff_id: uuid.UUID) -> SignoffRequest:
        """Cancel a sign-off that has not yet been finalised."""
        orm = self._get_or_raise(signoff_id)

        if SignoffStatus(orm.status) in _TERMINAL_STATUSES:
            raise ValueError(f"Cannot cancel finalized sign-off: {orm.status}")

        orm.status = SignoffStatus.CANCELLED.value
        self.session.flush()
        return self._orm_to_pydantic(orm)

    # ── Reconciliation Integration (B4b) ───────────────────────────────────

    def auto_populate_from_reconciliation(
        self,
        signoff_id: uuid.UUID,
        reconciliation_run_id: uuid.UUID,
    ) -> SignoffRequest:
        """Auto-populate checklist items from a reconciliation run.
        
        Updates pr_02 (row counts match) and pr_03 (checksums match)
        based on the reconciliation run results.
        
        Args:
            signoff_id: Sign-off request to update
            reconciliation_run_id: Reconciliation run to use as evidence
        
        Returns:
            Updated SignoffRequest
        """
        from app.modules.migration_workbench.models import ReconciliationRun
        
        orm = self._get_or_raise(signoff_id)
        
        # Verify sign-off is not finalized
        if SignoffStatus(orm.status) in _TERMINAL_STATUSES:
            raise ValueError(f"Cannot update finalized sign-off: {orm.status}")
        
        # Get reconciliation run
        run = self.session.get(ReconciliationRun, reconciliation_run_id)
        if not run:
            raise ValueError(f"Reconciliation run {reconciliation_run_id} not found")
        
        # Check results
        row_count_passed = False
        checksum_passed = False
        
        for check in run.check_results:
            if check.check_type == "row_count" and check.match:
                row_count_passed = True
            elif check.check_type == "checksum" and check.match:
                checksum_passed = True
        
        # Update checklist items
        now = datetime.now(timezone.utc)
        updated_count = 0
        
        for item in orm.checklist_items:
            if item.item_key == "pr_02" and row_count_passed:
                item.status = ChecklistItemStatus.PASSED.value
                item.auto_populated = True
                item.auto_populated_from = str(reconciliation_run_id)
                item.evidence = (
                    f"Auto-populated from ReconciliationRun {reconciliation_run_id}. "
                    f"Source: {run.source_row_count} rows, "
                    f"Target: {run.target_row_count} rows."
                )
                item.completed_at = now
                updated_count += 1
                log.info(
                    "signoff_item_auto_populated",
                    signoff_id=str(signoff_id),
                    item_key="pr_02",
                    run_id=str(reconciliation_run_id),
                )
            
            elif item.item_key == "pr_03" and checksum_passed:
                item.status = ChecklistItemStatus.PASSED.value
                item.auto_populated = True
                item.auto_populated_from = str(reconciliation_run_id)
                item.evidence = f"Auto-populated from ReconciliationRun {reconciliation_run_id}. Checksums match."
                item.completed_at = now
                updated_count += 1
                log.info(
                    "signoff_item_auto_populated",
                    signoff_id=str(signoff_id),
                    item_key="pr_03",
                    run_id=str(reconciliation_run_id),
                )
        
        if updated_count > 0:
            # Add comment to sign-off
            comments = list(orm.comments_json or [])
            comments.append(
                f"[SYSTEM] Auto-populated {updated_count} item(s) from reconciliation run {reconciliation_run_id}"
            )
            orm.comments_json = comments
        
        self.session.flush()
        return self._orm_to_pydantic(orm)

    def get_signoffs_for_reconciliation(
        self,
        project_id: uuid.UUID,
        package_id: uuid.UUID,
    ) -> list[SignoffRequestView]:
        """Get sign-offs that could be updated by a reconciliation run for a package.
        
        Returns parallel_run sign-offs that include the package and are not finalized.
        """
        stmt = (
            select(ORMSignoffRequest)
            .where(
                ORMSignoffRequest.project_id == project_id,
                ORMSignoffRequest.signoff_type == SignoffType.PARALLEL_RUN.value,
                ORMSignoffRequest.status.in_([
                    SignoffStatus.DRAFT.value,
                    SignoffStatus.PENDING.value,
                ]),
            )
            .options(selectinload(ORMSignoffRequest.checklist_items))
        )
        signoffs = list(self.session.scalars(stmt))
        
        # Filter to those that include this package
        matching = []
        for orm in signoffs:
            pkg_ids = orm.package_ids or []
            if package_id in pkg_ids or str(package_id) in [str(p) for p in pkg_ids]:
                matching.append(self._orm_to_view(orm))
        
        return matching

    # ── Internal helpers ───────────────────────────────────────────────────

    def _fetch_orm(self, signoff_id: uuid.UUID) -> ORMSignoffRequest | None:
        """Fetch ORM row with checklist items eagerly loaded."""
        return self.session.execute(
            select(ORMSignoffRequest)
            .where(ORMSignoffRequest.id == signoff_id)
            .options(selectinload(ORMSignoffRequest.checklist_items))
        ).scalar_one_or_none()

    def _fetch_and_convert(self, signoff_id: uuid.UUID) -> SignoffRequest:
        """Re-fetch from DB (post-flush) and convert to Pydantic."""
        orm = self._fetch_orm(signoff_id)
        if not orm:
            raise ValueError(f"Sign-off {signoff_id} not found after flush")
        return self._orm_to_pydantic(orm)

    def _get_or_raise(self, signoff_id: uuid.UUID) -> ORMSignoffRequest:
        """Fetch ORM row or raise ValueError."""
        orm = self._fetch_orm(signoff_id)
        if not orm:
            raise ValueError(f"Sign-off {signoff_id} not found")
        return orm

    def _required_incomplete(self, orm: ORMSignoffRequest) -> list[ORMChecklistItem]:
        """Return required items that are not yet in a completed state."""
        return [
            i for i in orm.checklist_items
            if i.required
            and ChecklistItemStatus(i.status) not in _COMPLETED_ITEM_STATUSES
        ]

    def _orm_to_pydantic(self, orm: ORMSignoffRequest) -> SignoffRequest:
        """Convert ORM SignoffRequest → Pydantic SignoffRequest.

        Bridges the structural difference:
          ORM  → flat checklist_items list + comments_json JSONB
          Pydantic → nested SignoffChecklist + comments list[str]
        """
        signoff_type = SignoffType(orm.signoff_type)

        items = [
            ChecklistItem(
                id=i.item_key,
                title=i.title,
                description=i.description,
                category=i.category or "general",
                required=i.required,
                status=ChecklistItemStatus(i.status),
                evidence=i.evidence,
                notes=i.notes,
                completed_by=i.completed_by,
                completed_at=i.completed_at,
            )
            for i in sorted(orm.checklist_items, key=lambda x: x.item_key)
        ]

        return SignoffRequest(
            id=orm.id,
            project_id=orm.project_id,
            signoff_type=signoff_type,
            status=SignoffStatus(orm.status),
            package_ids=list(orm.package_ids or []),
            wave_number=orm.wave_number,
            title=orm.title,
            description=orm.description,
            checklist=SignoffChecklist(signoff_type=signoff_type, items=items),
            requested_by=orm.requested_by,
            requested_at=orm.requested_at,
            approved_by=orm.approved_by,
            approved_at=orm.approved_at,
            rejection_reason=orm.rejection_reason,
            comments=list(orm.comments_json or []),
        )

    def _orm_to_view(self, orm: ORMSignoffRequest) -> SignoffRequestView:
        """Convert ORM SignoffRequest → SignoffRequestView for list endpoints."""
        completed = sum(
            1 for i in orm.checklist_items
            if ChecklistItemStatus(i.status) in _COMPLETED_ITEM_STATUSES
        )
        failed = sum(
            1 for i in orm.checklist_items
            if i.status == ChecklistItemStatus.FAILED.value
        )
        return SignoffRequestView(
            id=orm.id,
            project_id=orm.project_id,
            signoff_type=SignoffType(orm.signoff_type),
            status=SignoffStatus(orm.status),
            title=orm.title,
            package_count=len(orm.package_ids or []),
            wave_number=orm.wave_number,
            checklist_total=len(orm.checklist_items),
            checklist_completed=completed,
            checklist_failed=failed,
            requested_by=orm.requested_by,
            requested_at=orm.requested_at,
            approved_by=orm.approved_by,
            approved_at=orm.approved_at,
        )
