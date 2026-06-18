"""ZIP exporter for packaging .agents/ directory as a zip file."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from app.enums import ExportKind
from app.exporters.base import BaseExporter, ExportError, ExportManifest
from app.exporters.filesystem import FilesystemExporter


class ZipExporter(BaseExporter):
    """Exports projects as .zip files containing .agents/ directory structure."""

    def __init__(self, output_file: Path) -> None:
        """Initialize ZIP exporter.
        
        Args:
            output_file: Path where the .zip file will be created
        """
        super().__init__()
        self.output_file = Path(output_file)

    def export_project(self, project_slug: str) -> ExportManifest:
        """Export a complete project as a ZIP file.
        
        Args:
            project_slug: Project to export
            
        Returns:
            Manifest of exported files (includes the .zip file itself)
        """
        self._start_export(project_slug)
        
        try:
            # Use a temporary directory for the filesystem export
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # First export to filesystem in temp directory
                filesystem_exporter = FilesystemExporter(target_path=temp_path)
                filesystem_manifest = filesystem_exporter.export_project(project_slug)
                
                # Create the ZIP file
                self._create_zip_file(temp_path / ".agents", filesystem_manifest)
                
                # Add the ZIP file to our manifest
                zip_content = self.output_file.read_bytes()
                self._add_file(f"{project_slug}.zip", zip_content)
                
                return self._finish_export(project_slug, ExportKind.ZIP.value)
                
        except Exception as e:
            if isinstance(e, ExportError):
                raise
            raise ExportError(f"ZIP export failed: {str(e)}", project_slug, e) from e

    def _write_file(self, relative_path: str, content: str | bytes) -> None:
        """Write a file to the ZIP export destination.
        
        Note: This is used internally by _add_file to track the ZIP file itself.
        The actual file writing is handled by _create_zip_file.
        """
        # For ZIP exports, we don't write individual files directly
        # This method is called by _add_file to track the final ZIP file
        pass

    def _create_zip_file(self, agents_dir: Path, filesystem_manifest: ExportManifest) -> None:
        """Create the ZIP file from the filesystem export.
        
        Args:
            agents_dir: Path to the .agents directory to zip
            filesystem_manifest: Manifest from the filesystem export
        """
        # Ensure output directory exists
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(self.output_file, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
            # Add all files from the filesystem export
            for export_file in filesystem_manifest.files:
                file_path = agents_dir / export_file.relative_path
                
                if file_path.exists():
                    # Add to ZIP with .agents/ prefix to maintain structure
                    archive_path = f".agents/{export_file.relative_path}"
                    zipf.write(file_path, archive_path)

    def get_default_filename(self, project_slug: str) -> str:
        """Generate a default filename for the ZIP export.
        
        Args:
            project_slug: Project being exported
            
        Returns:
            Default ZIP filename
        """
        return f"{project_slug}.zip"