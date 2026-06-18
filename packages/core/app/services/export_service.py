"""Export service for project export orchestration and audit logging."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select

import app.db
from app.domain.exports import Export
from app.domain.projects import Project
from app.enums import ExportKind
from app.exporters import create_exporter
from app.exporters.base import ExportManifest
from app.validators import validate_project


class ExportService:
    """Service for managing project exports with validation and audit logging."""

    def __init__(self) -> None:
        """Initialize the export service."""
        pass

    def export_project(
        self,
        project_slug: str,
        export_kind: ExportKind | str,
        *,
        target_path: Path | str | None = None,
        output_file: Path | str | None = None,
        validate_before_export: bool = True,
        validation_strict: bool = False,
        **kwargs: Any
    ) -> ExportManifest:
        """Export a project with validation and audit logging.
        
        Args:
            project_slug: Project to export
            export_kind: Export format ("filesystem", "zip", "jira_csv")
            target_path: Target directory for filesystem exports
            output_file: Output file for ZIP exports
            validate_before_export: Whether to run validation before export
            validation_strict: Whether to treat validation warnings as errors
            **kwargs: Additional exporter configuration
            
        Returns:
            Export manifest with file list and metadata
            
        Raises:
            ValidationError: If validation fails and validate_before_export=True
            ExportError: If export operation fails
        """
        # Validate project exists
        project = self._get_project(project_slug)
        if not project:
            raise ValueError(f"Project '{project_slug}' not found")
        
        # Optional pre-export validation
        if validate_before_export:
            validation_issues = validate_project(project_slug, strict=validation_strict)
            
            # Check for errors
            error_count = sum(1 for issue in validation_issues if issue.severity.value == "error")
            if error_count > 0:
                raise ValidationError(
                    f"Project validation failed with {error_count} errors. "
                    f"Fix validation issues before exporting or disable validation.",
                    project_slug,
                    validation_issues
                )
        
        # Prepare exporter configuration
        exporter_config = dict(kwargs)
        if target_path is not None:
            exporter_config["target_path"] = Path(target_path)
        if output_file is not None:
            exporter_config["output_file"] = Path(output_file)
        
        # Perform export
        exporter = create_exporter(export_kind, **exporter_config)
        manifest = exporter.export_project(project_slug)
        
        # Log export to database
        self._log_export(project, export_kind, manifest, target_path or output_file)
        
        return manifest

    def list_project_exports(self, project_slug: str) -> list[Export]:
        """List all exports for a project.
        
        Args:
            project_slug: Project to list exports for
            
        Returns:
            List of export records, newest first
        """
        with app.db.session_scope() as session:
            project_query = select(Project).where(Project.slug == project_slug)
            project = session.execute(project_query).scalar_one_or_none()
            
            if not project:
                return []
            
            export_query = select(Export).where(
                Export.project_id == project.id
            ).order_by(Export.created_at.desc())
            
            result = session.execute(export_query)
            return list(result.scalars().all())

    def get_export_statistics(self) -> dict[str, Any]:
        """Get overall export statistics.
        
        Returns:
            Dictionary with export statistics
        """
        with app.db.session_scope() as session:
            # Total exports by kind
            export_query = select(Export)
            exports = session.execute(export_query).scalars().all()
            
            stats = {
                "total_exports": len(exports),
                "exports_by_kind": {},
                "total_files_exported": 0,
                "total_bytes_exported": 0,
                "recent_exports": []
            }
            
            for export in exports:
                # Count by kind
                kind = export.kind
                if kind not in stats["exports_by_kind"]:
                    stats["exports_by_kind"][kind] = 0
                stats["exports_by_kind"][kind] += 1
                
                # Sum file counts and sizes
                manifest = export.manifest_json
                if isinstance(manifest, dict):
                    stats["total_files_exported"] += manifest.get("total_files", 0)
                    stats["total_bytes_exported"] += manifest.get("total_size_bytes", 0)
            
            # Recent exports (last 10)
            recent_exports = sorted(exports, key=lambda e: e.created_at, reverse=True)[:10]
            stats["recent_exports"] = [
                {
                    "project_slug": export.project.slug if export.project else "unknown",
                    "kind": export.kind,
                    "created_at": export.created_at,
                    "file_count": (
                        export.manifest_json.get("total_files", 0) 
                        if isinstance(export.manifest_json, dict) else 0
                    )
                }
                for export in recent_exports
            ]
            
            return stats

    def cleanup_old_exports(self, days_to_keep: int = 30) -> int:
        """Clean up old export records (but not files).
        
        Args:
            days_to_keep: Number of days of export records to keep
            
        Returns:
            Number of export records deleted
        """
        from datetime import datetime, timedelta, timezone
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        
        with app.db.session_scope() as session:
            # Find old exports
            old_exports_query = select(Export).where(Export.created_at < cutoff_date)
            old_exports = session.execute(old_exports_query).scalars().all()
            
            count = len(old_exports)
            
            # Delete old export records
            for export in old_exports:
                session.delete(export)
            
            session.commit()
            
            return count

    def _get_project(self, project_slug: str) -> Project | None:
        """Get project by slug.
        
        Args:
            project_slug: Project slug
            
        Returns:
            Project instance or None if not found
        """
        with app.db.session_scope() as session:
            query = select(Project).where(Project.slug == project_slug)
            return session.execute(query).scalar_one_or_none()

    def _log_export(
        self,
        project: Project,
        export_kind: ExportKind | str,
        manifest: ExportManifest,
        target_path: Path | str | None
    ) -> None:
        """Log export to database for audit trail.
        
        Args:
            project: Project that was exported
            export_kind: Type of export performed
            manifest: Export manifest
            target_path: Target path or file
        """
        if isinstance(export_kind, str):
            export_kind = ExportKind(export_kind)
        
        # Convert manifest to JSON-serializable dict
        manifest_dict = {
            "project_slug": manifest.project_slug,
            "export_kind": manifest.export_kind,
            "files": [
                {
                    "relative_path": f.relative_path,
                    "size_bytes": f.size_bytes,
                    "sha256_hash": f.sha256_hash,
                    "created_at": f.created_at.isoformat()
                }
                for f in manifest.files
            ],
            "total_files": manifest.total_files,
            "total_size_bytes": manifest.total_size_bytes,
            "export_started_at": manifest.export_started_at.isoformat(),
            "export_completed_at": manifest.export_completed_at.isoformat(),
            "duration_seconds": manifest.duration_seconds
        }
        
        # Create export record
        export_record = Export(
            project_id=project.id,
            kind=export_kind.value,
            target_path=str(target_path) if target_path else None,
            manifest_json=manifest_dict
        )
        
        with app.db.session_scope() as session:
            session.add(export_record)
            session.commit()


class ValidationError(Exception):
    """Exception raised when pre-export validation fails."""
    
    def __init__(self, message: str, project_slug: str, validation_issues: list):
        super().__init__(message)
        self.project_slug = project_slug
        self.validation_issues = validation_issues