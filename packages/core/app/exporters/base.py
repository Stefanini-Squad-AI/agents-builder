"""Base exporter classes and common utilities."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.schemas.views import ProjectView


class ExportFile(BaseModel):
    """Represents a single exported file."""
    
    relative_path: str  # Relative to export root (e.g., "skills/auth-context/SKILL.md")
    size_bytes: int
    sha256_hash: str
    created_at: datetime


class ExportManifest(BaseModel):
    """Manifest of all files created during export."""
    
    project_slug: str
    export_kind: str
    files: list[ExportFile]
    total_files: int
    total_size_bytes: int
    export_started_at: datetime
    export_completed_at: datetime
    
    @property
    def duration_seconds(self) -> float:
        """Calculate export duration."""
        delta = self.export_completed_at - self.export_started_at
        return delta.total_seconds()


class BaseExporter(ABC):
    """Abstract base class for all project exporters."""

    def __init__(self) -> None:
        """Initialize the exporter."""
        self.start_time: datetime | None = None
        self.files: list[ExportFile] = []

    @abstractmethod
    def export_project(self, project_slug: str) -> ExportManifest:
        """Export a complete project.
        
        Args:
            project_slug: Project to export
            
        Returns:
            Manifest of exported files
            
        Raises:
            ExportError: If export fails
        """
        ...

    @abstractmethod 
    def _write_file(self, relative_path: str, content: str | bytes) -> None:
        """Write a file to the export destination.
        
        Args:
            relative_path: Path relative to export root
            content: File content (text or binary)
        """
        ...

    def _start_export(self, project_slug: str) -> None:
        """Initialize export tracking."""
        self.start_time = datetime.now(timezone.utc)
        self.files = []

    def _add_file(self, relative_path: str, content: str | bytes) -> ExportFile:
        """Track an exported file and calculate its hash.
        
        Args:
            relative_path: Path relative to export root
            content: File content
            
        Returns:
            ExportFile record
        """
        # Convert content to bytes for hashing
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content
        
        # Calculate hash and size
        sha256_hash = hashlib.sha256(content_bytes).hexdigest()
        size_bytes = len(content_bytes)
        
        export_file = ExportFile(
            relative_path=relative_path,
            size_bytes=size_bytes,
            sha256_hash=sha256_hash,
            created_at=datetime.now(timezone.utc)
        )
        
        self.files.append(export_file)
        return export_file

    def _finish_export(self, project_slug: str, export_kind: str) -> ExportManifest:
        """Finalize export and create manifest.
        
        Args:
            project_slug: Project that was exported
            export_kind: Type of export performed
            
        Returns:
            Complete export manifest
        """
        end_time = datetime.now(timezone.utc)
        
        return ExportManifest(
            project_slug=project_slug,
            export_kind=export_kind,
            files=self.files,
            total_files=len(self.files),
            total_size_bytes=sum(f.size_bytes for f in self.files),
            export_started_at=self.start_time,
            export_completed_at=end_time
        )

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename for cross-platform compatibility.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename safe for filesystem use
        """
        import re
        
        # Remove or replace invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
        
        # Replace multiple spaces/hyphens with single hyphen
        sanitized = re.sub(r'[-\s_]+', '-', sanitized)
        
        # Remove leading/trailing hyphens and dots
        sanitized = sanitized.strip('-. ')
        
        # Ensure it's not empty
        if not sanitized:
            sanitized = "file"
        
        return sanitized

    def _slugify(self, text: str) -> str:
        """Convert text to a URL-safe slug.
        
        Args:
            text: Text to convert
            
        Returns:
            URL-safe slug
        """
        import re
        
        # Convert to lowercase and replace spaces/underscores with hyphens  
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[-\s_]+', '-', slug)
        return slug.strip('-')


class ExportError(Exception):
    """Exception raised when export operations fail."""
    
    def __init__(
        self, 
        message: str, 
        project_slug: str | None = None, 
        cause: Exception | None = None
    ):
        super().__init__(message)
        self.project_slug = project_slug
        self.cause = cause