"""Documentation service for generating and tracking project documentation.

Provides:
- Auto-generation of versioned documentation snapshots
- Change detection between versions
- Mermaid diagram generation for Migration Map
- Gap analysis and progress tracking
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.backlog import Card, Phase
from app.domain.projects import Project
from app.modules.migration_workbench.documentation.schemas import (
    ChangeView,
    ChangesSummary,
    ConnectionState,
    DocSnapshotView,
    GeneratedDocs,
    PackageState,
    ProjectState,
    RuleState,
)
from app.modules.migration_workbench.models import (
    DocumentationChange,
    ETLPackage,
    MapRelationship,
    MigrationBusinessRule,
    MigrationConnection,
    MigrationDocSnapshot,
    MigrationResolvedDecision,
)


class DocumentationService:
    """Service for generating versioned project documentation with change tracking.
    
    Auto-regenerates documentation when significant events occur and
    detects changes (gaps filled, new blockers, progress) between versions.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # -------------------------------------------------------------------------
    # Main Entry Points
    # -------------------------------------------------------------------------
    
    def generate_snapshot(
        self,
        project_id: uuid.UUID,
        trigger_event: str,
        trigger_package_id: uuid.UUID | None = None,
    ) -> MigrationDocSnapshot:
        """Generate new documentation snapshot and detect changes.
        
        This is the main method called when events occur that should
        trigger documentation regeneration.
        
        Args:
            project_id: The project to document
            trigger_event: What caused this generation (e.g., 'package_analyzed')
            trigger_package_id: If triggered by a specific package
            
        Returns:
            The new snapshot with changes recorded
        """
        # 1. Build current state
        current_state = self._build_project_state(project_id)
        
        # 2. Get previous snapshot
        previous = self._get_latest_snapshot(project_id)
        
        # 3. Generate documentation markdown
        docs = self._render_documentation(current_state)
        
        # 4. Determine version
        version = (previous.version + 1) if previous else 1
        
        # 5. Create new snapshot
        snapshot = MigrationDocSnapshot(
            project_id=project_id,
            version=version,
            snapshot_type="full",
            project_summary_md=docs.project_summary_md,
            migration_map_md=docs.migration_map_md,
            packages_summary_md=docs.packages_summary_md,
            state_json=current_state.model_dump(mode="json"),
            trigger_event=trigger_event,
            trigger_package_id=trigger_package_id,
        )
        self.db.add(snapshot)
        self.db.flush()  # Get ID
        
        # 6. Detect and record changes
        if previous:
            prev_state = ProjectState.model_validate(previous.state_json)
            changes = self._detect_changes(prev_state, current_state, project_id)
            for change in changes:
                change.from_snapshot_id = previous.id
                change.to_snapshot_id = snapshot.id
                self.db.add(change)
        
        return snapshot
    
    def get_latest_snapshot(self, project_id: uuid.UUID) -> DocSnapshotView | None:
        """Get the most recent documentation snapshot."""
        snapshot = self._get_latest_snapshot(project_id)
        if snapshot:
            return DocSnapshotView.model_validate(snapshot)
        return None
    
    def get_changes_summary(
        self,
        project_id: uuid.UUID,
        from_version: int | None = None,
        to_version: int | None = None,
    ) -> ChangesSummary:
        """Get summary of changes between versions."""
        # Default to latest two versions
        if to_version is None:
            latest = self._get_latest_snapshot(project_id)
            to_version = latest.version if latest else 0
        if from_version is None:
            from_version = max(1, to_version - 1)
        
        # Get snapshots
        from_snap = self.db.scalar(
            select(MigrationDocSnapshot).where(
                MigrationDocSnapshot.project_id == project_id,
                MigrationDocSnapshot.version == from_version,
            )
        )
        to_snap = self.db.scalar(
            select(MigrationDocSnapshot).where(
                MigrationDocSnapshot.project_id == project_id,
                MigrationDocSnapshot.version == to_version,
            )
        )
        
        if not from_snap or not to_snap:
            return ChangesSummary(
                from_version=from_version,
                to_version=to_version,
                total_changes=0,
            )
        
        # Get changes
        stmt = (
            select(DocumentationChange)
            .where(
                DocumentationChange.from_snapshot_id == from_snap.id,
                DocumentationChange.to_snapshot_id == to_snap.id,
            )
            .order_by(DocumentationChange.detected_at)
        )
        changes = list(self.db.scalars(stmt))
        
        # Categorize
        critical = [ChangeView.model_validate(c) for c in changes if c.significance == "critical"]
        notable = [ChangeView.model_validate(c) for c in changes if c.significance == "notable"]
        info = [ChangeView.model_validate(c) for c in changes if c.significance == "info"]
        
        return ChangesSummary(
            from_version=from_version,
            to_version=to_version,
            total_changes=len(changes),
            gaps_filled=sum(1 for c in changes if c.change_type == "gap_filled"),
            new_blockers=sum(1 for c in changes if c.change_type == "new_blocker"),
            blockers_resolved=sum(1 for c in changes if c.change_type == "blocker_resolved"),
            progress_updates=sum(1 for c in changes if c.change_type == "progress"),
            critical_changes=critical,
            notable_changes=notable,
            info_changes=info,
        )
    
    # -------------------------------------------------------------------------
    # State Building
    # -------------------------------------------------------------------------
    
    def _build_project_state(self, project_id: uuid.UUID) -> ProjectState:
        """Build complete project state for snapshot."""
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Get packages
        packages_stmt = select(ETLPackage).where(ETLPackage.project_id == project_id)
        packages = {
            str(p.id): self._build_package_state(p)
            for p in self.db.scalars(packages_stmt)
        }
        
        # Get connections
        conns_stmt = select(MigrationConnection).where(
            MigrationConnection.project_id == project_id
        )
        connections = {
            c.connection_name: ConnectionState(
                id=c.id,
                name=c.connection_name,
                resolved=c.resolved_at is not None,
                target_catalog=c.target_catalog,
                target_schema=c.target_schema,
                used_by_count=len(c.used_by_packages or []),
            )
            for c in self.db.scalars(conns_stmt)
        }
        
        # Get rules
        rules_stmt = select(MigrationBusinessRule).where(
            MigrationBusinessRule.project_id == project_id
        )
        rules = {
            r.rule_id: RuleState(
                id=r.id,
                rule_id=r.rule_id,
                name=r.rule_name,
                status=r.status,
                has_implementation=r.target_implementation is not None,
            )
            for r in self.db.scalars(rules_stmt)
        }
        
        # Count decisions
        decisions_count = self.db.scalar(
            select(func.count()).where(
                MigrationResolvedDecision.project_id == project_id
            )
        ) or 0
        
        # Calculate aggregates
        pkg_list = list(packages.values())
        total_packages = len(pkg_list)
        analyzed = sum(1 for p in pkg_list if p.status in (
            "analyzed", "ready", "generating", "generated", "validating", "validated", "migrated", "verified"
        ))
        migrated = sum(1 for p in pkg_list if p.status in ("migrated", "verified"))
        total_blockers = sum(len(p.blockers) for p in pkg_list)
        
        return ProjectState(
            project_id=project_id,
            source_technology=project.source_technology,
            target_technology=project.target_technology,
            packages=packages,
            connections=connections,
            rules=rules,
            decisions_count=decisions_count,
            total_packages=total_packages,
            analyzed_packages=analyzed,
            migrated_packages=migrated,
            total_blockers=total_blockers,
        )
    
    def _build_package_state(self, package: ETLPackage) -> PackageState:
        """Build state for a single package."""
        # Count cards for this package
        total_cards = self.db.scalar(
            select(func.count()).where(Card.package_id == package.id)
        ) or 0
        completed_cards = self.db.scalar(
            select(func.count()).where(
                Card.package_id == package.id,
                Card.status == "done",
            )
        ) or 0
        
        progress = (completed_cards / total_cards * 100) if total_cards > 0 else 0.0
        
        return PackageState(
            id=package.id,
            name=package.package_name,
            status=package.status,
            domain=package.domain,
            complexity=package.complexity,
            card_prefix=package.card_prefix,
            total_cards=total_cards,
            completed_cards=completed_cards,
            progress_percent=round(progress, 1),
            blockers=[],  # TODO: Add blocker tracking
        )
    
    # -------------------------------------------------------------------------
    # Change Detection
    # -------------------------------------------------------------------------
    
    def _detect_changes(
        self,
        old_state: ProjectState,
        new_state: ProjectState,
        project_id: uuid.UUID,
    ) -> list[DocumentationChange]:
        """Compare states and generate change records."""
        changes: list[DocumentationChange] = []
        
        # Connection changes
        changes.extend(self._detect_connection_changes(old_state, new_state, project_id))
        
        # Rule changes
        changes.extend(self._detect_rule_changes(old_state, new_state, project_id))
        
        # Package progress changes
        changes.extend(self._detect_progress_changes(old_state, new_state, project_id))
        
        # Decision changes
        if new_state.decisions_count > old_state.decisions_count:
            diff = new_state.decisions_count - old_state.decisions_count
            changes.append(DocumentationChange(
                project_id=project_id,
                change_type="decision_made",
                category="decisions",
                description=f"{diff} new decision(s) recorded",
                previous_value=str(old_state.decisions_count),
                new_value=str(new_state.decisions_count),
                significance="notable",
            ))
        
        return changes
    
    def _detect_connection_changes(
        self,
        old_state: ProjectState,
        new_state: ProjectState,
        project_id: uuid.UUID,
    ) -> list[DocumentationChange]:
        """Detect connection resolution changes."""
        changes = []
        
        for name, new_conn in new_state.connections.items():
            old_conn = old_state.connections.get(name)
            
            # New connection resolved
            if new_conn.resolved:
                if not old_conn or not old_conn.resolved:
                    target = f"{new_conn.target_catalog}.{new_conn.target_schema}"
                    changes.append(DocumentationChange(
                        project_id=project_id,
                        change_type="gap_filled",
                        category="connections",
                        description=f"Connection '{name}' mapped to '{target}'",
                        previous_value=None,
                        new_value=target,
                        significance="notable",
                    ))
        
        return changes
    
    def _detect_rule_changes(
        self,
        old_state: ProjectState,
        new_state: ProjectState,
        project_id: uuid.UUID,
    ) -> list[DocumentationChange]:
        """Detect business rule implementation changes."""
        changes = []
        
        for rule_id, new_rule in new_state.rules.items():
            old_rule = old_state.rules.get(rule_id)
            
            # Rule newly implemented
            if new_rule.has_implementation:
                if not old_rule or not old_rule.has_implementation:
                    changes.append(DocumentationChange(
                        project_id=project_id,
                        change_type="rule_implemented",
                        category="rules",
                        description=f"Business rule '{new_rule.name}' implemented",
                        previous_value=old_rule.status if old_rule else None,
                        new_value=new_rule.status,
                        significance="notable",
                    ))
            
            # Rule status changed
            elif old_rule and old_rule.status != new_rule.status:
                changes.append(DocumentationChange(
                    project_id=project_id,
                    change_type="progress",
                    category="rules",
                    description=f"Rule '{new_rule.name}' status: {old_rule.status} → {new_rule.status}",
                    previous_value=old_rule.status,
                    new_value=new_rule.status,
                    significance="info",
                ))
        
        return changes
    
    def _detect_progress_changes(
        self,
        old_state: ProjectState,
        new_state: ProjectState,
        project_id: uuid.UUID,
    ) -> list[DocumentationChange]:
        """Detect package progress changes."""
        changes = []
        
        for pkg_id, new_pkg in new_state.packages.items():
            old_pkg = old_state.packages.get(pkg_id)
            
            if not old_pkg:
                # New package added
                changes.append(DocumentationChange(
                    project_id=project_id,
                    change_type="progress",
                    category="progress",
                    package_id=uuid.UUID(pkg_id),
                    description=f"Package '{new_pkg.name}' registered",
                    significance="info",
                ))
                continue
            
            # Progress change
            if new_pkg.progress_percent > old_pkg.progress_percent:
                changes.append(DocumentationChange(
                    project_id=project_id,
                    change_type="progress",
                    category="progress",
                    package_id=uuid.UUID(pkg_id),
                    description=f"Package '{new_pkg.name}' progress: {old_pkg.progress_percent}% → {new_pkg.progress_percent}%",
                    previous_value=str(old_pkg.progress_percent),
                    new_value=str(new_pkg.progress_percent),
                    significance="info",
                ))
            
            # Status change
            if new_pkg.status != old_pkg.status:
                significance = "notable" if new_pkg.status in ("migrated", "verified") else "info"
                changes.append(DocumentationChange(
                    project_id=project_id,
                    change_type="progress",
                    category="progress",
                    package_id=uuid.UUID(pkg_id),
                    description=f"Package '{new_pkg.name}' status: {old_pkg.status} → {new_pkg.status}",
                    previous_value=old_pkg.status,
                    new_value=new_pkg.status,
                    significance=significance,
                ))
        
        return changes
    
    # -------------------------------------------------------------------------
    # Documentation Rendering
    # -------------------------------------------------------------------------
    
    def _render_documentation(self, state: ProjectState) -> GeneratedDocs:
        """Render documentation markdown from state."""
        return GeneratedDocs(
            project_summary_md=self._render_project_summary(state),
            migration_map_md=self._render_migration_map(state),
            packages_summary_md=self._render_packages_summary(state),
            state_json=state.model_dump(mode="json"),
        )
    
    def _render_project_summary(self, state: ProjectState) -> str:
        """Render project overview markdown."""
        lines = [
            f"# Migration Project Status",
            f"",
            f"> **Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"",
            f"## Overview",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Source Technology | {state.source_technology or 'Not set'} |",
            f"| Target Technology | {state.target_technology or 'Not set'} |",
            f"| Total Packages | {state.total_packages} |",
            f"| Analyzed | {state.analyzed_packages} ({self._pct(state.analyzed_packages, state.total_packages)}%) |",
            f"| Migrated | {state.migrated_packages} ({self._pct(state.migrated_packages, state.total_packages)}%) |",
            f"| Connections | {len(state.connections)} ({sum(1 for c in state.connections.values() if c.resolved)} resolved) |",
            f"| Business Rules | {len(state.rules)} ({sum(1 for r in state.rules.values() if r.has_implementation)} implemented) |",
            f"| Decisions | {state.decisions_count} |",
            f"",
        ]
        return "\n".join(lines)
    
    def _render_migration_map(self, state: ProjectState) -> str:
        """Render migration map with Mermaid diagrams."""
        lines = [
            f"## Migration Map",
            f"",
            f"### Data Dependencies View",
            f"",
            f"```mermaid",
            f"flowchart LR",
        ]
        
        # Add package nodes
        for pkg_id, pkg in state.packages.items():
            status_icon = self._status_icon(pkg.status)
            prefix = pkg.card_prefix or pkg.name[:4].upper()
            lines.append(f"    {prefix}[{prefix}<br/>{status_icon} {pkg.status}]")
        
        # TODO: Add relationships from MapRelationship table
        # For now, just show nodes
        
        # Style nodes by status
        lines.append(f"")
        for pkg_id, pkg in state.packages.items():
            prefix = pkg.card_prefix or pkg.name[:4].upper()
            style = self._status_style(pkg.status)
            lines.append(f"    style {prefix} {style}")
        
        lines.extend([
            f"```",
            f"",
            f"### Execution Dependencies View",
            f"",
            f"```mermaid",
            f"flowchart TD",
        ])
        
        # Similar structure for execution view
        for pkg_id, pkg in state.packages.items():
            status_icon = self._status_icon(pkg.status)
            prefix = pkg.card_prefix or pkg.name[:4].upper()
            lines.append(f"    {prefix}[{prefix}<br/>{status_icon}]")
        
        lines.append(f"```")
        lines.append(f"")
        
        return "\n".join(lines)
    
    def _render_packages_summary(self, state: ProjectState) -> str:
        """Render packages status table."""
        lines = [
            f"## Package Status",
            f"",
            f"| Package | Prefix | Domain | Status | Progress | Cards |",
            f"|---------|--------|--------|--------|----------|-------|",
        ]
        
        for pkg in sorted(state.packages.values(), key=lambda p: p.name):
            prefix = pkg.card_prefix or "-"
            domain = pkg.domain or "-"
            status_icon = self._status_icon(pkg.status)
            progress = f"{pkg.progress_percent}%"
            cards = f"{pkg.completed_cards}/{pkg.total_cards}"
            lines.append(f"| {pkg.name} | {prefix} | {domain} | {status_icon} {pkg.status} | {progress} | {cards} |")
        
        lines.append(f"")
        return "\n".join(lines)
    
    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    
    def _get_latest_snapshot(self, project_id: uuid.UUID) -> MigrationDocSnapshot | None:
        """Get the most recent snapshot for a project."""
        return self.db.scalar(
            select(MigrationDocSnapshot)
            .where(MigrationDocSnapshot.project_id == project_id)
            .order_by(MigrationDocSnapshot.version.desc())
            .limit(1)
        )
    
    @staticmethod
    def _pct(part: int, whole: int) -> int:
        """Calculate percentage."""
        return round(part / whole * 100) if whole > 0 else 0
    
    @staticmethod
    def _status_icon(status: str) -> str:
        """Get emoji icon for status."""
        icons = {
            "registered": "📋",
            "analyzing": "🔍",
            "analyzed": "✅",
            "needs_feedback": "❓",
            "ready": "🟢",
            "generating": "⚙️",
            "generated": "📝",
            "validating": "🧪",
            "validated": "✔️",
            "migrated": "🚀",
            "verified": "🏆",
        }
        return icons.get(status, "❔")
    
    @staticmethod
    def _status_style(status: str) -> str:
        """Get Mermaid style for status."""
        if status in ("migrated", "verified"):
            return "fill:#4ade80"  # Green
        elif status in ("analyzing", "generating", "validating"):
            return "fill:#facc15"  # Yellow
        elif status == "needs_feedback":
            return "fill:#f87171"  # Red
        elif status in ("analyzed", "ready", "generated", "validated"):
            return "fill:#60a5fa"  # Blue
        return "fill:#e5e7eb"  # Gray
