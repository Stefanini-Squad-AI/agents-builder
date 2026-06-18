"""Analysis service for ETL package analysis.

Coordinates parsing, extraction, LLM analysis, and blocker detection.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.migration_workbench.analysis.schemas import (
    AnalysisResultView,
    BlockerView,
    PackageAnalysis,
)
from app.modules.migration_workbench.models import ETLPackage, PackageConnectionPoints


class AnalysisService:
    """Service for managing package analysis."""
    
    def __init__(self, session: Session):
        """Initialize service.
        
        Args:
            session: Database session
        """
        self.session = session
    
    def get_analysis_status(self, package_id: uuid.UUID) -> dict[str, Any]:
        """Get analysis status for a package.
        
        Args:
            package_id: Package ID
            
        Returns:
            Status dict with progress and results summary
        """
        package = self.session.execute(
            select(ETLPackage).where(ETLPackage.id == package_id)
        ).scalar_one_or_none()
        
        if not package:
            return {"status": "not_found"}
        
        result = {
            "package_id": str(package_id),
            "package_name": package.package_name,
            "status": package.analysis_status or "pending",
            "analyzed_at": package.analyzed_at.isoformat() if package.analyzed_at else None,
        }
        
        if package.analysis_status == "failed":
            result["error"] = package.analysis_error
        
        if package.analysis_status == "analyzed":
            result["complexity"] = package.complexity
            result["domain"] = package.domain
            result["estimated_effort"] = package.estimated_effort
            result["blockers_count"] = package.blockers_count or 0
            result["auto_resolved_count"] = package.auto_resolved_count or 0
        
        return result
    
    def get_analysis_results(self, package_id: uuid.UUID) -> dict[str, Any] | None:
        """Get full analysis results for a package.
        
        Args:
            package_id: Package ID
            
        Returns:
            Full analysis results or None if not analyzed
        """
        package = self.session.execute(
            select(ETLPackage).where(ETLPackage.id == package_id)
        ).scalar_one_or_none()
        
        if not package or package.analysis_status != "analyzed":
            return None
        
        # Get connection points — one row per package (UNIQUE constraint on package_id).
        # PackageConnectionPoints stores sources and targets as separate JSONB columns,
        # not as individual rows with a direction field.
        conn_point = self.session.execute(
            select(PackageConnectionPoints).where(
                PackageConnectionPoints.package_id == package_id
            )
        ).scalar_one_or_none()

        def _extract_table_entries(items: list | None) -> list[dict]:
            result = []
            for item in (items or []):
                if isinstance(item, dict):
                    result.append({
                        "type": item.get("type", "table"),
                        "name": item.get("table_name") or item.get("name", ""),
                        "schema": item.get("schema_name") or item.get("schema", ""),
                        "connection": item.get("connection_ref") or item.get("connection", ""),
                    })
                elif isinstance(item, str):
                    result.append({"type": "table", "name": item, "schema": "", "connection": ""})
            return result

        sources = _extract_table_entries(conn_point.source_tables if conn_point else None)
        targets = _extract_table_entries(conn_point.target_tables if conn_point else None)
        
        return {
            "package_id": str(package_id),
            "package_name": package.package_name,
            "complexity": package.complexity,
            "domain": package.domain,
            "estimated_effort": package.estimated_effort,
            "analyzed_at": package.analyzed_at.isoformat() if package.analyzed_at else None,
            "connection_points": {
                "sources": sources,
                "targets": targets,
            },
            "analysis": package.analysis_json or {},
            "parse_warnings": package.parse_warnings or [],
        }
    
    def get_project_analysis_summary(self, project_id: uuid.UUID) -> dict[str, Any]:
        """Get analysis summary for all packages in a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            Summary statistics
        """
        # Count packages by status
        status_counts = self.session.execute(
            select(
                ETLPackage.analysis_status,
                func.count(ETLPackage.id),
            )
            .where(ETLPackage.project_id == project_id)
            .group_by(ETLPackage.analysis_status)
        ).all()
        
        by_status = {status or "pending": count for status, count in status_counts}
        total = sum(by_status.values())
        
        # Count by complexity
        complexity_counts = self.session.execute(
            select(
                ETLPackage.complexity,
                func.count(ETLPackage.id),
            )
            .where(
                ETLPackage.project_id == project_id,
                ETLPackage.analysis_status == "analyzed",
            )
            .group_by(ETLPackage.complexity)
        ).all()
        
        by_complexity = {complexity or "unknown": count for complexity, count in complexity_counts}
        
        # Aggregate blocker counts
        blocker_totals = self.session.execute(
            select(
                func.sum(ETLPackage.blockers_count),
                func.sum(ETLPackage.auto_resolved_count),
            )
            .where(
                ETLPackage.project_id == project_id,
                ETLPackage.analysis_status == "analyzed",
            )
        ).one()
        
        return {
            "total_packages": total,
            "by_status": by_status,
            "by_complexity": by_complexity,
            "total_blockers": blocker_totals[0] or 0,
            "auto_resolved_blockers": blocker_totals[1] or 0,
            "pending_blockers": (blocker_totals[0] or 0) - (blocker_totals[1] or 0),
            "analysis_progress": (
                by_status.get("analyzed", 0) / total * 100 if total > 0 else 0
            ),
        }
    
    def queue_analysis(self, package_id: uuid.UUID) -> bool:
        """Queue a package for analysis.
        
        Args:
            package_id: Package ID to analyze
            
        Returns:
            True if queued, False if already analyzed/analyzing
        """
        package = self.session.execute(
            select(ETLPackage).where(ETLPackage.id == package_id)
        ).scalar_one_or_none()
        
        if not package:
            return False
        
        if package.analysis_status in ("analyzing", "analyzed"):
            return False
        
        # Set to pending and enqueue
        package.analysis_status = "pending"
        self.session.flush()
        
        # Import here to avoid circular imports
        from app.jobs.analyze_package import analyze_package
        analyze_package.send(str(package_id))
        
        return True
    
    def queue_bulk_analysis(
        self,
        project_id: uuid.UUID,
        limit: int = 100,
    ) -> int:
        """Queue multiple packages for analysis.
        
        Args:
            project_id: Project ID
            limit: Maximum number to queue
            
        Returns:
            Number of packages queued
        """
        # Find packages needing analysis
        packages = self.session.execute(
            select(ETLPackage)
            .where(
                ETLPackage.project_id == project_id,
                ETLPackage.analysis_status.in_(["pending", "failed", None]),
            )
            .limit(limit)
        ).scalars().all()
        
        from app.jobs.analyze_package import analyze_package
        
        count = 0
        for package in packages:
            package.analysis_status = "pending"
            analyze_package.send(str(package.id))
            count += 1
        
        self.session.flush()
        return count
    
    def retry_failed_analysis(self, package_id: uuid.UUID) -> bool:
        """Retry analysis for a failed package.
        
        Args:
            package_id: Package ID
            
        Returns:
            True if retried, False otherwise
        """
        package = self.session.execute(
            select(ETLPackage).where(ETLPackage.id == package_id)
        ).scalar_one_or_none()
        
        if not package or package.analysis_status != "failed":
            return False
        
        package.analysis_status = "pending"
        package.analysis_error = None
        self.session.flush()
        
        from app.jobs.analyze_package import analyze_package
        analyze_package.send(str(package_id))
        
        return True
    
    def get_blockers_needing_decisions(
        self,
        project_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Get all blockers that need decisions across the project.
        
        Args:
            project_id: Project ID
            
        Returns:
            List of blockers with package context
        """
        packages = self.session.execute(
            select(ETLPackage)
            .where(
                ETLPackage.project_id == project_id,
                ETLPackage.analysis_status == "analyzed",
                ETLPackage.blockers_count > ETLPackage.auto_resolved_count,
            )
        ).scalars().all()
        
        blockers = []
        for package in packages:
            analysis = package.analysis_json or {}
            for blocker in analysis.get("blockers", []):
                if not blocker.get("auto_resolved"):
                    blockers.append({
                        "package_id": str(package.id),
                        "package_name": package.package_name,
                        **blocker,
                    })
        
        return blockers
