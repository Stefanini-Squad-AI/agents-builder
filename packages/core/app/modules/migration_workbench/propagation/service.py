"""Propagation service for knowledge transfer between packages.

When a human resolves a blocker or makes a decision for one package,
this service can propagate that resolution to other packages that
have the same unresolved question.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import Session

from app.modules.migration_workbench.models import (
    ETLPackage,
    MigrationResolvedDecision,
    PackageCluster,
    PackageClusterMember,
)
from app.modules.migration_workbench.propagation.schemas import (
    BatchWaveResult,
    PropagationPreview,
    PropagationResult,
    PropagationScope,
)

log = structlog.get_logger(__name__)


class PropagationService:
    """Service for propagating decisions across packages.
    
    When a decision is resolved for one package, it can be propagated
    to other packages that have the same unresolved decision type.
    This enables "resolve once, apply everywhere" workflows.
    """
    
    def __init__(self, session: Session):
        """Initialize the service.
        
        Args:
            session: Database session
        """
        self.session = session
    
    def preview_propagation(
        self,
        decision_id: uuid.UUID,
        scope: PropagationScope = PropagationScope.PROJECT,
        cluster_id: uuid.UUID | None = None,
        domain: str | None = None,
    ) -> PropagationPreview:
        """Preview what packages would be affected by propagation.
        
        Args:
            decision_id: ID of the source decision to propagate
            scope: Scope of propagation (project, cluster, domain)
            cluster_id: Required if scope is CLUSTER
            domain: Required if scope is DOMAIN
            
        Returns:
            Preview showing what would be affected
        """
        # Get the source decision
        decision = self.session.get(MigrationResolvedDecision, decision_id)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")
        
        # Find candidate packages
        candidates = self._find_candidate_packages(
            project_id=decision.project_id,
            decision_type=decision.decision_type,
            source_package_id=decision.package_id,
            scope=scope,
            cluster_id=cluster_id,
            domain=domain,
        )
        
        # Check which are already resolved
        already_resolved = self._find_already_resolved(
            project_id=decision.project_id,
            decision_type=decision.decision_type,
            package_ids=[c.id for c in candidates],
        )
        
        would_affect = [c for c in candidates if c.id not in already_resolved]
        
        return PropagationPreview(
            decision_id=decision_id,
            decision_type=decision.decision_type,
            question=decision.question,
            resolution=decision.resolution,
            scope=scope,
            would_affect_count=len(would_affect),
            already_resolved_count=len(already_resolved),
            affected_packages=[
                {
                    "id": str(p.id),
                    "name": p.package_name,
                    "domain": p.domain,
                    "status": p.status,
                }
                for p in would_affect
            ],
        )
    
    def propagate_decision(
        self,
        decision_id: uuid.UUID,
        scope: PropagationScope = PropagationScope.PROJECT,
        cluster_id: uuid.UUID | None = None,
        domain: str | None = None,
        propagated_by: str | None = None,
    ) -> PropagationResult:
        """Propagate a decision to matching packages.
        
        Creates new resolved decisions for packages that have the same
        decision type but haven't been resolved yet.
        
        Args:
            decision_id: ID of the source decision to propagate
            scope: Scope of propagation
            cluster_id: Required if scope is CLUSTER
            domain: Required if scope is DOMAIN
            propagated_by: User who triggered propagation
            
        Returns:
            Result with counts and affected package IDs
        """
        # Get the source decision
        decision = self.session.get(MigrationResolvedDecision, decision_id)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")
        
        log.info(
            "propagate_decision_start",
            decision_id=str(decision_id),
            decision_type=decision.decision_type,
            scope=scope.value,
        )
        
        # Find candidate packages
        candidates = self._find_candidate_packages(
            project_id=decision.project_id,
            decision_type=decision.decision_type,
            source_package_id=decision.package_id,
            scope=scope,
            cluster_id=cluster_id,
            domain=domain,
        )
        
        # Check which are already resolved
        already_resolved = self._find_already_resolved(
            project_id=decision.project_id,
            decision_type=decision.decision_type,
            package_ids=[c.id for c in candidates],
        )
        
        # Filter to unresolved packages
        to_resolve = [c for c in candidates if c.id not in already_resolved]
        
        affected_ids: list[uuid.UUID] = []
        errors: list[str] = []
        
        for package in to_resolve:
            try:
                self._apply_decision_to_package(decision, package, propagated_by)
                affected_ids.append(package.id)
            except Exception as e:
                log.exception("propagate_decision_error", package_id=str(package.id))
                errors.append(f"Package {package.package_name}: {str(e)}")
        
        # Update the source decision's applied_to_packages list
        existing_applied = decision.applied_to_packages or []
        decision.applied_to_packages = list(set(existing_applied + affected_ids))
        
        self.session.commit()
        
        log.info(
            "propagate_decision_done",
            decision_id=str(decision_id),
            affected_count=len(affected_ids),
            already_resolved=len(already_resolved),
            errors=len(errors),
        )
        
        return PropagationResult(
            source_decision_id=decision_id,
            decision_type=decision.decision_type,
            packages_affected=len(affected_ids),
            packages_already_resolved=len(already_resolved),
            affected_package_ids=affected_ids,
            errors=errors,
            propagated_at=datetime.now(timezone.utc),
        )
    
    def _find_candidate_packages(
        self,
        project_id: uuid.UUID,
        decision_type: str,
        source_package_id: uuid.UUID | None,
        scope: PropagationScope,
        cluster_id: uuid.UUID | None = None,
        domain: str | None = None,
    ) -> list[ETLPackage]:
        """Find packages that might need this decision.
        
        Looks for packages with analysis_json containing blockers
        with matching decision_type that are not auto_resolved.
        """
        # Base query: packages in the same project, analyzed
        query = select(ETLPackage).where(
            ETLPackage.project_id == project_id,
            ETLPackage.status.in_(["analyzing", "analyzed", "reviewed"]),
            ETLPackage.analysis_json.isnot(None),
        )
        
        # Exclude source package
        if source_package_id:
            query = query.where(ETLPackage.id != source_package_id)
        
        # Apply scope filters
        if scope == PropagationScope.CLUSTER and cluster_id:
            # Get packages in the same cluster
            member_ids = self.session.execute(
                select(PackageClusterMember.package_id).where(
                    PackageClusterMember.cluster_id == cluster_id
                )
            ).scalars().all()
            query = query.where(ETLPackage.id.in_(member_ids))
            
        elif scope == PropagationScope.DOMAIN and domain:
            query = query.where(ETLPackage.domain == domain)
        
        packages = self.session.execute(query).scalars().all()
        
        # Filter to packages that have this decision_type in their blockers
        matching = []
        for pkg in packages:
            if self._package_has_unresolved_blocker(pkg, decision_type):
                matching.append(pkg)
        
        return matching
    
    def _package_has_unresolved_blocker(
        self,
        package: ETLPackage,
        decision_type: str,
    ) -> bool:
        """Check if package has an unresolved blocker with this decision_type."""
        if not package.analysis_json:
            return False
        
        blockers = package.analysis_json.get("blockers", [])
        for blocker in blockers:
            if (
                blocker.get("decision_type") == decision_type
                and not blocker.get("auto_resolved", False)
            ):
                return True
        
        return False
    
    def _find_already_resolved(
        self,
        project_id: uuid.UUID,
        decision_type: str,
        package_ids: list[uuid.UUID],
    ) -> set[uuid.UUID]:
        """Find which packages already have this decision resolved."""
        if not package_ids:
            return set()
        
        resolved = self.session.execute(
            select(MigrationResolvedDecision.package_id).where(
                MigrationResolvedDecision.project_id == project_id,
                MigrationResolvedDecision.decision_type == decision_type,
                MigrationResolvedDecision.package_id.in_(package_ids),
            )
        ).scalars().all()
        
        return set(r for r in resolved if r is not None)
    
    def _apply_decision_to_package(
        self,
        source_decision: MigrationResolvedDecision,
        package: ETLPackage,
        propagated_by: str | None,
    ) -> None:
        """Apply a decision to a package.
        
        Creates a new resolved decision for the package and updates
        the package's analysis_json to mark the blocker as auto_resolved.
        """
        # Create a new resolved decision for this package
        new_decision = MigrationResolvedDecision(
            id=uuid.uuid4(),
            project_id=source_decision.project_id,
            decision_type=source_decision.decision_type,
            question=source_decision.question,
            resolution=source_decision.resolution,
            resolution_rationale=f"Auto-propagated from decision {source_decision.id}",
            scope="package",
            package_id=package.id,
            resolved_by=propagated_by or "system:propagation",
            resolved_at=datetime.now(timezone.utc),
            applied_to_packages=[],
        )
        self.session.add(new_decision)
        
        # Update the package's analysis_json to mark blocker as auto_resolved
        if package.analysis_json:
            analysis = dict(package.analysis_json)
            blockers = analysis.get("blockers", [])
            updated_blockers = []
            auto_resolved_count = 0
            
            for blocker in blockers:
                if blocker.get("decision_type") == source_decision.decision_type:
                    blocker = dict(blocker)
                    blocker["auto_resolved"] = True
                    blocker["resolution"] = source_decision.resolution
                    auto_resolved_count += 1
                updated_blockers.append(blocker)
            
            analysis["blockers"] = updated_blockers
            package.analysis_json = analysis
            
            # Update auto_resolved_count
            if package.auto_resolved_count is None:
                package.auto_resolved_count = 0
            package.auto_resolved_count += auto_resolved_count
    
    def batch_assign_waves(
        self,
        project_id: uuid.UUID,
        assignments: list[dict[str, Any]],
    ) -> BatchWaveResult:
        """Assign waves to multiple packages at once.
        
        Args:
            project_id: Project ID
            assignments: List of {"package_id": UUID, "wave": int}
            
        Returns:
            Result with success/failure counts
        """
        successful = 0
        failed = 0
        errors: list[str] = []
        assigned_ids: list[uuid.UUID] = []
        
        for assignment in assignments:
            pkg_id = assignment.get("package_id")
            wave = assignment.get("wave")
            
            if not pkg_id or wave is None:
                errors.append(f"Invalid assignment: {assignment}")
                failed += 1
                continue
            
            try:
                # Verify package belongs to project
                pkg = self.session.execute(
                    select(ETLPackage).where(
                        ETLPackage.id == pkg_id,
                        ETLPackage.project_id == project_id,
                    )
                ).scalar_one_or_none()
                
                if not pkg:
                    errors.append(f"Package {pkg_id} not found in project")
                    failed += 1
                    continue
                
                # Update wave via cluster membership or direct field
                # For now, we'll track wave in analysis_json
                if pkg.analysis_json:
                    analysis = dict(pkg.analysis_json)
                else:
                    analysis = {}
                
                analysis["migration_wave"] = wave
                pkg.analysis_json = analysis
                
                successful += 1
                assigned_ids.append(pkg_id)
                
            except Exception as e:
                log.exception("batch_assign_wave_error", package_id=str(pkg_id))
                errors.append(f"Package {pkg_id}: {str(e)}")
                failed += 1
        
        self.session.commit()
        
        return BatchWaveResult(
            successful=successful,
            failed=failed,
            errors=errors,
            assigned_packages=assigned_ids,
        )
