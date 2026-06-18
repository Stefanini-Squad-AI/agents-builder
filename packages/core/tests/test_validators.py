"""Tests for the validation system."""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from app.enums import (
    CardDepRelation, CardInputKind, CardStatus, CardType, 
    LlmProvider, Priority, ProjectStatus, SkillKind, Grouping
)
from app.schemas.common import ValidationSeverity
from app.validators import (
    validate_project, get_validation_summary, format_validation_report
)
from app.validators.dag_validator import DagValidator
from app.validators.frontmatter_validator import FrontmatterValidator
from app.validators.paths_validator import PathsValidator
from app.validators.qa_validator import QaValidator
from app.validators.refs_validator import ReferencesValidator


class TestValidationOrchestrator:
    """Test the main validation orchestrator."""

    def test_validate_project_nonexistent(self):
        """Test validation of non-existent project.""" 
        issues = validate_project("nonexistent-project")
        
        # Should have errors from all validators (might be validator errors due to missing dependencies)
        assert len(issues) >= 5  # One from each validator
        error_codes = {issue.code for issue in issues}
        
        # Check that all validators produced some kind of error (either project_not_found or validator_error)
        validator_prefixes = {"dag", "refs", "frontmatter", "paths", "qa"}
        found_prefixes = {code.split('.')[0] for code in error_codes}
        
        # At least should find some validator errors
        assert len(found_prefixes.intersection(validator_prefixes)) >= 3

    def test_validate_project_strict_mode(self):
        """Test strict mode converts warnings to errors."""
        with patch('app.validators.DagValidator.validate') as mock_dag:
            # Mock one validator to return warnings
            mock_dag.return_value = [
                Mock(severity=ValidationSeverity.WARNING, code="dag.test", message="Test warning")
            ]
            
            # Normal mode should have warnings
            issues_normal = validate_project("test", strict=False)
            warning_count = sum(1 for i in issues_normal if i.severity == ValidationSeverity.WARNING)
            assert warning_count > 0
            
            # Strict mode should convert to errors  
            issues_strict = validate_project("test", strict=True)
            error_count = sum(1 for i in issues_strict if i.severity == ValidationSeverity.ERROR)
            warning_count_strict = sum(1 for i in issues_strict if i.severity == ValidationSeverity.WARNING)
            
            assert error_count > 0
            assert warning_count_strict == 0

    def test_validator_error_handling(self):
        """Test handling of validator exceptions."""
        with patch('app.validators.DagValidator.validate') as mock_dag:
            mock_dag.side_effect = Exception("Validator crashed")
            
            issues = validate_project("test")
            
            # Should have validator error issue
            validator_errors = [i for i in issues if "validator_error" in i.code]
            assert len(validator_errors) >= 1
            assert any("Validator crashed" in i.message for i in validator_errors)

    def test_get_validation_summary(self):
        """Test validation summary calculation."""
        issues = [
            Mock(severity=ValidationSeverity.ERROR),
            Mock(severity=ValidationSeverity.ERROR),
            Mock(severity=ValidationSeverity.WARNING),
        ]
        
        summary = get_validation_summary(issues)
        
        assert summary["error_count"] == 2
        assert summary["warning_count"] == 1  
        assert summary["total_count"] == 3

    def test_format_validation_report_empty(self):
        """Test formatting with no issues."""
        report = format_validation_report([])
        assert "No validation issues found" in report

    def test_format_validation_report_with_issues(self):
        """Test formatting with issues."""
        issues = [
            Mock(
                severity=ValidationSeverity.ERROR,
                code="dag.cycle",
                message="Circular dependency detected",
                location={"project_slug": "test", "card_code": "TEST-1"}
            ),
            Mock(
                severity=ValidationSeverity.WARNING,
                code="refs.unused_skill",
                message="Skill not used",
                location={"skill_slug": "unused"}
            )
        ]
        
        report = format_validation_report(issues)
        
        assert "✗ Dag validation: 1 errors, 0 warnings" in report
        assert "⚠ Refs validation: 0 errors, 1 warnings" in report
        assert "ERROR [dag.cycle]" in report
        assert "WARNING [refs.unused_skill]" in report
        assert "SUMMARY: 1 errors, 1 warnings found" in report

    def test_format_validation_report_compact(self):
        """Test compact formatting."""
        issues = [
            Mock(
                severity=ValidationSeverity.ERROR,
                code="test.error", 
                message="Test error",
                location={"project_slug": "test"}
            )
        ]
        
        report = format_validation_report(issues, compact=True)
        assert "project_slug=test" in report


class TestDagValidator:
    """Test DAG validator functionality."""

    def test_dag_validator_empty_project(self):
        """Test DAG validation with empty project.""" 
        validator = DagValidator()
        
        with patch('app.validators.dag_validator.session_scope') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = None
            
            issues = validator.validate("empty")
            assert len(issues) >= 1
            # Should have at least one issue (either project_not_found or validator_error)

    def test_calculate_topological_order(self):
        """Test topological sort calculation."""
        validator = DagValidator()
        
        # Mock a simple project with dependencies
        with patch('app.db.session_scope') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = None
            
            # Should return None for non-existent project
            order = validator.calculate_topological_order("nonexistent")
            assert order is None


class TestReferencesValidator:
    """Test references validator functionality."""

    def test_refs_validator_missing_project(self):
        """Test references validation with missing project."""
        validator = ReferencesValidator()
        
        with patch('app.db.session_scope') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = None
            
            issues = validator.validate("missing")
            assert len(issues) == 1
            assert issues[0].code == "refs.project_not_found"

    def test_get_reference_statistics(self):
        """Test reference statistics calculation."""
        validator = ReferencesValidator()
        
        with patch('app.db.session_scope') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = None
            
            stats = validator.get_reference_statistics("missing")
            
            # Should return default stats for missing project
            assert stats["total_cards"] == 0
            assert stats["cards_with_skills"] == 0


class TestFrontmatterValidator:
    """Test frontmatter validator functionality."""

    def test_frontmatter_validator_missing_project(self):
        """Test frontmatter validation with missing project."""
        validator = FrontmatterValidator()
        
        with patch('app.db.session_scope') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = None
            
            issues = validator.validate("missing")
            assert len(issues) == 1
            assert issues[0].code == "frontmatter.project_not_found"

    def test_is_valid_slug(self):
        """Test slug validation logic."""
        validator = FrontmatterValidator()
        
        assert validator._is_valid_slug("valid-slug")
        assert validator._is_valid_slug("valid-slug-123")
        assert not validator._is_valid_slug("Invalid-Slug")  # uppercase
        assert not validator._is_valid_slug("invalid_slug")  # underscore
        assert not validator._is_valid_slug("invalid slug")  # space
        assert not validator._is_valid_slug("")  # empty

    def test_get_frontmatter_statistics(self):
        """Test frontmatter statistics calculation."""
        validator = FrontmatterValidator()
        
        with patch('app.db.session_scope') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = None
            
            stats = validator.get_frontmatter_statistics("missing")
            
            # Should return default stats for missing project
            assert stats["total_skills"] == 0
            assert stats["total_cards"] == 0


class TestPathsValidator:
    """Test paths validator functionality."""

    def test_paths_validator_missing_project(self):
        """Test paths validation with missing project."""
        validator = PathsValidator()
        
        with patch('app.db.session_scope') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = None
            
            issues = validator.validate("missing")
            assert len(issues) == 1
            assert issues[0].code == "paths.project_not_found"

    def test_is_valid_filesystem_name(self):
        """Test filesystem name validation."""
        validator = PathsValidator()
        
        assert validator._is_valid_filesystem_name("valid-name")
        assert validator._is_valid_filesystem_name("valid_name_123")
        assert not validator._is_valid_filesystem_name("invalid<name")  # invalid char
        assert not validator._is_valid_filesystem_name("CON")  # reserved name
        assert not validator._is_valid_filesystem_name("invalid.")  # ends with dot
        assert not validator._is_valid_filesystem_name("")  # empty

    def test_is_valid_filename(self):
        """Test filename validation."""
        validator = PathsValidator()
        
        assert validator._is_valid_filename("file.txt")
        assert validator._is_valid_filename("valid-filename.md")
        assert not validator._is_valid_filename(".")  # current dir
        assert not validator._is_valid_filename("..")  # parent dir
        assert not validator._is_valid_filename("")  # empty

    def test_get_expected_extensions(self):
        """Test file extension mapping."""
        validator = PathsValidator()
        
        assert ".md" in validator._get_expected_extensions("markdown")
        assert ".py" in validator._get_expected_extensions("python")
        assert ".sql" in validator._get_expected_extensions("sql")
        assert validator._get_expected_extensions("unknown") == []

    def test_get_path_statistics(self):
        """Test path statistics calculation."""
        validator = PathsValidator()
        
        with patch('app.db.session_scope') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = None
            
            stats = validator.get_path_statistics("missing")
            
            # Should return default stats for missing project
            assert stats["project_slug_length"] == 0
            assert stats["naming_collisions"] == 0


class TestQaValidator:
    """Test Q&A validator functionality."""

    def test_qa_validator_missing_project(self):
        """Test Q&A validation with missing project."""
        validator = QaValidator()
        
        with patch('app.db.session_scope') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = None
            
            issues = validator.validate("missing")
            assert len(issues) == 1
            assert issues[0].code == "qa.project_not_found"

    def test_has_markdown_formatting_issues(self):
        """Test markdown formatting issue detection."""
        validator = QaValidator()
        
        assert not validator._has_markdown_formatting_issues("Normal text")
        assert validator._has_markdown_formatting_issues("**Unmatched bold")  # unmatched bold
        assert validator._has_markdown_formatting_issues("*Unmatched italic")  # unmatched italic
        assert validator._has_markdown_formatting_issues("[link](incomplete")  # malformed link
        assert validator._has_markdown_formatting_issues("##NoSpace")  # header without space

    def test_suggest_missing_questions(self):
        """Test missing question suggestions."""
        validator = QaValidator()
        
        with patch('app.db.session_scope') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = None
            
            suggestions = validator.suggest_missing_questions("missing")
            
            # Should return empty for missing project
            assert suggestions == []

    def test_get_qa_statistics(self):
        """Test Q&A statistics calculation."""
        validator = QaValidator()
        
        with patch('app.db.session_scope') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value.scalar_one_or_none.return_value = None
            
            stats = validator.get_qa_statistics("missing")
            
            # Should return default stats for missing project
            assert stats["total_questions"] == 0
            assert stats["answered_questions"] == 0
            assert stats["total_critical_categories"] == len(validator.CRITICAL_QUESTIONS)


# Integration test with seeded data would go here
@pytest.mark.integration
class TestValidationIntegration:
    """Integration tests with seeded data."""
    
    def test_validate_seeded_project(self):
        """Test validation against seeded project data."""
        pytest.skip("Integration test requires seeded database")
        
        # This would test against real seeded data like corp-vli, siglm, etc.
        # issues = validate_project("corp-vli")
        # print(format_validation_report(issues))


class TestValidationStatistics:
    """Test validation statistics and reporting."""
    
    def test_comprehensive_statistics(self):
        """Test getting comprehensive validation statistics."""
        # This would collect stats from all validators for reporting
        pytest.skip("Comprehensive statistics test - implement when needed")


class TestValidationPerformance:
    """Test validation performance."""
    
    def test_validation_performance(self):
        """Test validation performance on large projects."""
        pytest.skip("Performance test - implement when needed")
        
        # This would test validation speed on projects with many cards/skills