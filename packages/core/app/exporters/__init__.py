"""Export system for generating .agents/ folder structures and artifacts.

This module provides exporters for different output formats:
- FilesystemExporter: Generate .agents/ directory structure
- ZipExporter: Package exports as .zip files
- DAG renderers: Generate Mermaid dependency visualizations

Usage:
    from app.exporters import create_exporter, export_project
    
    # Export to filesystem
    exporter = create_exporter("filesystem", target_path="./output")
    manifest = exporter.export_project("my-project-slug")
    
    # Export to ZIP
    exporter = create_exporter("zip", output_file="project.zip") 
    manifest = exporter.export_project("my-project-slug")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.enums import ExportKind
from app.exporters.base import BaseExporter, ExportManifest
from app.exporters.filesystem import FilesystemExporter
from app.exporters.zip import ZipExporter


def create_exporter(kind: ExportKind | str, **kwargs: Any) -> BaseExporter:
    """Factory function to create the appropriate exporter.
    
    Args:
        kind: Export type ("filesystem", "zip", "jira_csv")
        **kwargs: Exporter-specific configuration
        
    Returns:
        Configured exporter instance
        
    Raises:
        ValueError: If export kind is not supported
    """
    if isinstance(kind, str):
        kind = ExportKind(kind)
    
    if kind == ExportKind.FILESYSTEM:
        target_path = kwargs.get("target_path", Path("./output"))
        return FilesystemExporter(target_path=Path(target_path))
    
    elif kind == ExportKind.ZIP:
        output_file = kwargs.get("output_file")
        if not output_file:
            raise ValueError("ZipExporter requires 'output_file' parameter")
        return ZipExporter(output_file=Path(output_file))
    
    elif kind == ExportKind.JIRA_CSV:
        raise NotImplementedError("Jira CSV export is planned for P5+")
    
    else:
        raise ValueError(f"Unsupported export kind: {kind}")


def export_project(
    project_slug: str,
    kind: ExportKind | str,
    **kwargs: Any
) -> ExportManifest:
    """High-level function to export a project.
    
    Args:
        project_slug: Project to export
        kind: Export type
        **kwargs: Export configuration
        
    Returns:
        Export manifest with file list and metadata
    """
    exporter = create_exporter(kind, **kwargs)
    return exporter.export_project(project_slug)


__all__ = [
    "BaseExporter",
    "ExportManifest", 
    "FilesystemExporter",
    "ZipExporter",
    "create_exporter",
    "export_project",
]