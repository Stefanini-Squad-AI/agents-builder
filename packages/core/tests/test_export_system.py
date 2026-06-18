"""Tests for the export system."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.enums import ExportKind
from app.exporters import create_exporter, export_project
from app.exporters.base import ExportError, ExportManifest
from app.exporters.dag import create_dag_renderer, render_project_dag
from app.exporters.filesystem import FilesystemExporter
from app.exporters.zip import ZipExporter
from app.services import DagService, ExportService
from app.services.export_service import ValidationError


class TestExporters:
    """Test individual exporters."""

    def test_create_exporter_filesystem(self):
        """Test creating filesystem exporter."""
        exporter = create_exporter(ExportKind.FILESYSTEM, target_path="./test")
        assert isinstance(exporter, FilesystemExporter)
        assert exporter.target_path == Path("./test")

    def test_create_exporter_zip(self):
        """Test creating ZIP exporter."""
        exporter = create_exporter(ExportKind.ZIP, output_file="test.zip")
        assert isinstance(exporter, ZipExporter)
        assert exporter.output_file == Path("test.zip")

    def test_create_exporter_unsupported(self):
        """Test creating exporter with unsupported kind."""
        with pytest.raises(ValueError, match="Unsupported export kind"):
            create_exporter("invalid_kind")

    def test_create_exporter_zip_missing_file(self):
        """Test creating ZIP exporter without output file."""
        with pytest.raises(ValueError, match="ZipExporter requires 'output_file' parameter"):
            create_exporter(ExportKind.ZIP)

    def test_filesystem_exporter_init(self):
        """Test filesystem exporter initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = FilesystemExporter(target_path=Path(temp_dir))
            assert exporter.target_path == Path(temp_dir)
            assert exporter.agents_path == Path(temp_dir) / ".agents"

    def test_zip_exporter_init(self):
        """Test ZIP exporter initialization."""
        output_file = Path("test.zip")
        exporter = ZipExporter(output_file=output_file)
        assert exporter.output_file == output_file

    def test_export_project_nonexistent(self):
        """Test exporting non-existent project."""
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = FilesystemExporter(target_path=Path(temp_dir))
            
            with patch.object(exporter, '_load_project_data', return_value=None):
                with pytest.raises(ExportError, match="Project 'nonexistent' not found"):
                    exporter.export_project("nonexistent")


class TestDagRenderers:
    """Test DAG rendering system."""

    def test_create_dag_renderer_mermaid(self):
        """Test creating Mermaid renderer."""
        renderer = create_dag_renderer("mermaid")
        assert renderer is not None

    def test_create_dag_renderer_unsupported(self):
        """Test creating unsupported renderer."""
        with pytest.raises(ValueError, match="Unsupported DAG format"):
            create_dag_renderer("invalid")

    def test_render_project_dag_basic(self):
        """Test basic project DAG rendering."""
        with patch('app.exporters.dag.base.app.db.session_scope') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = None
            
            result = render_project_dag("nonexistent", "mermaid")
            assert "not found" in result


class TestExportService:
    """Test export service functionality."""

    def test_export_service_init(self):
        """Test export service initialization."""
        service = ExportService()
        assert service is not None

    def test_export_project_nonexistent_project(self):
        """Test exporting non-existent project."""
        service = ExportService()
        
        with patch.object(service, '_get_project', return_value=None):
            with pytest.raises(ValueError, match="Project 'nonexistent' not found"):
                service.export_project("nonexistent", ExportKind.FILESYSTEM)

    def test_export_project_validation_failure(self):
        """Test export with validation failure."""
        service = ExportService()
        mock_project = Mock()
        mock_project.id = 1
        
        # Mock validation issues
        mock_issues = [
            Mock(severity=Mock(value="error"), message="Test error")
        ]
        
        with patch.object(service, '_get_project', return_value=mock_project), \
             patch('app.services.export_service.validate_project', return_value=mock_issues):
            
            with pytest.raises(ValidationError, match="Project validation failed"):
                service.export_project(
                    "test", 
                    ExportKind.FILESYSTEM,
                    validate_before_export=True
                )

    def test_export_project_skip_validation(self):
        """Test export with validation disabled."""
        service = ExportService()
        mock_project = Mock()
        mock_project.id = 1
        
        mock_manifest = Mock()
        mock_manifest.project_slug = "test"
        mock_manifest.export_kind = "filesystem"
        mock_manifest.files = []
        mock_manifest.total_files = 0
        mock_manifest.total_size_bytes = 0
        mock_manifest.export_started_at = Mock()
        mock_manifest.export_completed_at = Mock()
        mock_manifest.duration_seconds = 1.0
        
        with patch.object(service, '_get_project', return_value=mock_project), \
             patch('app.exporters.filesystem.FilesystemExporter.export_project', return_value=mock_manifest), \
             patch.object(service, '_log_export') as mock_log:
            
            result = service.export_project(
                "test",
                ExportKind.FILESYSTEM,
                validate_before_export=False,
                target_path="./test"
            )
            
            assert result == mock_manifest
            mock_log.assert_called_once()

    def test_get_export_statistics_empty(self):
        """Test getting export statistics with no exports.""" 
        service = ExportService()
        
        with patch('app.db.session_scope') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalars.return_value.all.return_value = []
            
            stats = service.get_export_statistics()
            
            assert stats["total_exports"] == 0
            assert stats["exports_by_kind"] == {}
            assert stats["total_files_exported"] == 0


class TestDagService:
    """Test DAG service functionality."""

    def test_dag_service_init(self):
        """Test DAG service initialization."""
        service = DagService()
        assert service.dag_validator is not None

    def test_render_dag_mermaid(self):
        """Test rendering DAG in Mermaid format."""
        service = DagService()
        
        with patch('app.exporters.dag.mermaid.MermaidRenderer.render_project_dag') as mock_render:
            mock_render.return_value = "graph TD\n    A --> B"
            
            result = service.render_dag("test", "mermaid")
            assert "graph TD" in result

    def test_render_dag_unsupported_format(self):
        """Test rendering DAG with unsupported format."""
        service = DagService()
        
        with pytest.raises(ValueError, match="Unsupported DAG format"):
            service.render_dag("test", "invalid")

    def test_analyze_dependencies_nonexistent(self):
        """Test analyzing dependencies for non-existent project."""
        service = DagService()
        
        with patch('app.exporters.dag.base.BaseDagRenderer.load_project_dag', return_value=None):
            result = service.analyze_dependencies("nonexistent")
            assert "error" in result
            assert "not found" in result["error"]

    def test_validate_dependencies_basic(self):
        """Test basic dependency validation."""
        service = DagService()
        
        with patch.object(service.dag_validator, 'validate', return_value=[]) as mock_validate, \
             patch.object(service, 'get_topological_order', return_value=['CARD-1', 'CARD-2']):
            
            result = service.validate_dependencies("test")
            
            assert result["project_slug"] == "test"
            assert result["is_valid"] is True
            assert result["total_issues"] == 0
            assert result["topological_order_possible"] is True
            mock_validate.assert_called_once_with("test")


# Integration tests (require database setup)
@pytest.mark.integration
class TestExportIntegration:
    """Integration tests for export system."""
    
    def test_export_seeded_project(self):
        """Test exporting a seeded project."""
        pytest.skip("Integration test requires seeded database")
        
        # This would test against real seeded data
        # service = ExportService()
        # manifest = service.export_project("corp-vli", ExportKind.FILESYSTEM, target_path="./test-export")
        # assert manifest.total_files > 0

    def test_dag_render_seeded_project(self):
        """Test DAG rendering for seeded project."""
        pytest.skip("Integration test requires seeded database")
        
        # This would test against real seeded data
        # service = DagService()
        # dag_content = service.render_dag("corp-vli", "mermaid")
        # assert "graph TD" in dag_content


class TestExportManifest:
    """Test export manifest functionality."""

    def test_export_manifest_duration(self):
        """Test calculating export duration."""
        from datetime import datetime, timezone, timedelta
        
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(seconds=5.5)
        
        manifest = ExportManifest(
            project_slug="test",
            export_kind="filesystem",
            files=[],
            total_files=0,
            total_size_bytes=0,
            export_started_at=start_time,
            export_completed_at=end_time
        )
        
        assert abs(manifest.duration_seconds - 5.5) < 0.1


class TestFileSystemOperations:
    """Test filesystem operations in exporters."""

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        from app.exporters.base import BaseExporter
        
        class TestExporter(BaseExporter):
            def export_project(self, project_slug: str):
                return None
            def _write_file(self, relative_path: str, content: str | bytes) -> None:
                pass
        
        exporter = TestExporter()
        
        # Test invalid characters
        assert exporter._sanitize_filename("test<>file") == "testfile"
        assert exporter._sanitize_filename("test file") == "test-file"
        assert exporter._sanitize_filename("test___file") == "test-file"
        assert exporter._sanitize_filename("") == "file"
        assert exporter._sanitize_filename("...") == "file"

    def test_slugify(self):
        """Test text slugification."""
        from app.exporters.base import BaseExporter
        
        class TestExporter(BaseExporter):
            def export_project(self, project_slug: str):
                return None
            def _write_file(self, relative_path: str, content: str | bytes) -> None:
                pass
        
        exporter = TestExporter()
        
        assert exporter._slugify("Test Project") == "test-project"
        assert exporter._slugify("Project_Name") == "project-name"  
        assert exporter._slugify("Special@#$Characters!") == "specialcharacters"
        assert exporter._slugify("Multiple   Spaces") == "multiple-spaces"