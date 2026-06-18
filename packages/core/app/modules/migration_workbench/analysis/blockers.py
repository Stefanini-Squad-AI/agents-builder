"""Blocker detection and auto-resolution.

Detects blockers from analysis results and attempts to auto-resolve
them using project context (prior decisions, business rules).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.migration_workbench.analysis.schemas import (
    BlockerItem,
    BlockerSeverity,
    BlockerType,
    PackageAnalysis,
)
from app.modules.migration_workbench.models import (
    ETLPackage,
    MigrationResolvedDecision,
)


class BlockerDetector:
    """Detects and processes blockers from analysis results.
    
    Integrates with the context service to auto-resolve blockers
    when prior decisions exist for the same decision type.
    """
    
    def __init__(self, session: Session, project_id: uuid.UUID):
        """Initialize detector.
        
        Args:
            session: Database session
            project_id: Project ID for context lookup
        """
        self.session = session
        self.project_id = project_id
    
    def process_blockers(
        self,
        analysis: PackageAnalysis,
        package_id: uuid.UUID,
    ) -> list[BlockerItem]:
        """Process blockers from analysis, attempting auto-resolution.
        
        Args:
            analysis: Package analysis containing detected blockers
            package_id: Package ID for storing results
            
        Returns:
            List of blockers with resolution status updated
        """
        processed: list[BlockerItem] = []
        
        for blocker in analysis.blockers:
            # Try auto-resolution if blocker has a decision type
            if blocker.decision_type:
                resolution = self._find_resolution(blocker.decision_type)
                if resolution:
                    # Auto-resolve
                    processed.append(BlockerItem(
                        blocker_type=blocker.blocker_type,
                        title=blocker.title,
                        description=blocker.description,
                        severity=blocker.severity,
                        affected_components=blocker.affected_components,
                        suggested_action=blocker.suggested_action,
                        decision_type=blocker.decision_type,
                        auto_resolved=True,
                        resolution=resolution,
                    ))
                    continue
            
            # Not auto-resolved
            processed.append(blocker)
        
        return processed
    
    def _find_resolution(self, decision_type: str) -> str | None:
        """Look up prior resolution for a decision type.
        
        Args:
            decision_type: Type of decision to look up
            
        Returns:
            Resolution text if found, None otherwise
        """
        stmt = (
            select(MigrationResolvedDecision)
            .where(
                MigrationResolvedDecision.project_id == self.project_id,
                MigrationResolvedDecision.decision_type == decision_type,
            )
            .order_by(MigrationResolvedDecision.created_at.desc())
            .limit(1)
        )
        
        result = self.session.execute(stmt).scalar_one_or_none()
        
        if result:
            return result.resolution
        
        return None
    
    def detect_structural_blockers(
        self,
        package: Any,  # SSISPackage
    ) -> list[BlockerItem]:
        """Detect blockers from package structure (without LLM).
        
        This provides basic blocker detection for packages that fail
        LLM analysis or for quick pre-analysis checks.
        
        Args:
            package: Parsed SSIS package
            
        Returns:
            List of detected blockers
        """
        blockers: list[BlockerItem] = []
        
        # Check for Script Tasks (often complex to migrate)
        script_tasks = [
            t for t in package.tasks
            if t.task_type.value == "Script Task"
        ]
        if script_tasks:
            blockers.append(BlockerItem(
                blocker_type=BlockerType.TECHNICAL,
                title="Script Tasks detected",
                description=f"Package contains {len(script_tasks)} Script Task(s) that require manual code migration",
                severity=BlockerSeverity.HIGH,
                affected_components=[t.name for t in script_tasks],
                suggested_action="Review script logic and rewrite in PySpark or Python",
                decision_type="script_task_strategy",
            ))
        
        # Check for Execute Package Tasks (dependencies)
        exec_pkg_tasks = [
            t for t in package.tasks
            if t.task_type.value == "Execute Package Task"
        ]
        if exec_pkg_tasks:
            blockers.append(BlockerItem(
                blocker_type=BlockerType.TECHNICAL,
                title="Child package execution detected",
                description=f"Package calls {len(exec_pkg_tasks)} child package(s)",
                severity=BlockerSeverity.MEDIUM,
                affected_components=[t.name for t in exec_pkg_tasks],
                suggested_action="Map dependencies and ensure child packages are migrated first",
                decision_type="child_package_strategy",
            ))
        
        # Check for dynamic connections
        dynamic_conns = [
            cm for cm in package.connection_managers
            if cm.is_expression_based
        ]
        if dynamic_conns:
            blockers.append(BlockerItem(
                blocker_type=BlockerType.TECHNICAL,
                title="Dynamic connection strings detected",
                description=f"{len(dynamic_conns)} connection(s) use expressions",
                severity=BlockerSeverity.MEDIUM,
                affected_components=[cm.name for cm in dynamic_conns],
                suggested_action="Parameterize connections in Databricks notebook",
                decision_type="dynamic_connection_strategy",
            ))
        
        # Check for disabled tasks
        if package.disabled_tasks:
            blockers.append(BlockerItem(
                blocker_type=BlockerType.BUSINESS,
                title="Disabled tasks present",
                description=f"{len(package.disabled_tasks)} task(s) are disabled",
                severity=BlockerSeverity.LOW,
                affected_components=package.disabled_tasks,
                suggested_action="Confirm whether disabled tasks should be migrated",
                decision_type="disabled_task_handling",
            ))
        
        # Check for complex transformations
        complex_transforms = []
        for df in package.data_flows:
            for t in df.transformations:
                if any(kw in t.component_type.lower() for kw in [
                    "fuzzy", "term", "percentage", "aggregate", "pivot", "unpivot"
                ]):
                    complex_transforms.append(t.name)
        
        if complex_transforms:
            blockers.append(BlockerItem(
                blocker_type=BlockerType.TECHNICAL,
                title="Complex transformations detected",
                description=f"Package contains advanced transformations requiring careful migration",
                severity=BlockerSeverity.MEDIUM,
                affected_components=complex_transforms,
                suggested_action="Review transformation logic and implement in PySpark",
            ))
        
        return blockers
    
    def get_blocking_summary(
        self,
        blockers: list[BlockerItem],
    ) -> dict[str, Any]:
        """Generate summary statistics for blockers.
        
        Args:
            blockers: List of blockers
            
        Returns:
            Summary dict with counts by type and severity
        """
        total = len(blockers)
        auto_resolved = sum(1 for b in blockers if b.auto_resolved)
        pending = total - auto_resolved
        
        by_type = {}
        for b in blockers:
            by_type[b.blocker_type.value] = by_type.get(b.blocker_type.value, 0) + 1
        
        by_severity = {}
        for b in blockers:
            by_severity[b.severity.value] = by_severity.get(b.severity.value, 0) + 1
        
        critical_pending = sum(
            1 for b in blockers
            if b.severity == BlockerSeverity.CRITICAL and not b.auto_resolved
        )
        
        return {
            "total": total,
            "auto_resolved": auto_resolved,
            "pending": pending,
            "critical_pending": critical_pending,
            "by_type": by_type,
            "by_severity": by_severity,
            "can_proceed": critical_pending == 0,
        }


def detect_blockers(
    session: Session,
    project_id: uuid.UUID,
    analysis: PackageAnalysis,
    package_id: uuid.UUID,
) -> list[BlockerItem]:
    """Convenience function to detect and process blockers.
    
    Args:
        session: Database session
        project_id: Project ID
        analysis: Package analysis results
        package_id: Package ID
        
    Returns:
        Processed blockers with auto-resolution applied
    """
    detector = BlockerDetector(session, project_id)
    return detector.process_blockers(analysis, package_id)
