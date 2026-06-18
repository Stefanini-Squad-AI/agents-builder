"""Project validation suite for ensuring consistency and quality.

This module provides comprehensive validation across all project artifacts:
- DAG validation: Cycle detection, dependency analysis
- References validation: Skill links, input paths, cross-references
- Frontmatter validation: YAML structure, required fields
- Paths validation: Naming conventions, file structure
- Q&A validation: Completeness, consistency

Usage:
    from app.validators import validate_project

    issues = validate_project(project_slug)
    for issue in issues:
        print(f"{issue.severity}: {issue.message}")
"""

from __future__ import annotations

from app.domain import register_models
from app.schemas.common import ValidationIssue, ValidationSeverity

# Ensure all ORM models are registered before validators use them
register_models()

# Import individual validators
from app.validators.dag_validator import DagValidator
from app.validators.frontmatter_validator import FrontmatterValidator
from app.validators.paths_validator import PathsValidator
from app.validators.qa_validator import QaValidator
from app.validators.refs_validator import ReferencesValidator


def validate_project(project_slug: str, *, strict: bool = False) -> list[ValidationIssue]:
    """Run comprehensive validation suite on a project.

    Args:
        project_slug: Project to validate
        strict: If True, treat warnings as errors

    Returns:
        List of validation issues found (errors and warnings)
    """
    all_issues = []

    # Define validators in execution order (independent validators can run in parallel)
    validators = [
        ("DAG", DagValidator()),
        ("References", ReferencesValidator()),
        ("Frontmatter", FrontmatterValidator()),
        ("Paths", PathsValidator()),
        ("Q&A", QaValidator()),
    ]

    # Run each validator and collect issues
    for validator_name, validator in validators:
        try:
            issues = validator.validate(project_slug)

            # In strict mode, convert warnings to errors
            if strict:
                for issue in issues:
                    if issue.severity == ValidationSeverity.WARNING:
                        issue.severity = ValidationSeverity.ERROR

            all_issues.extend(issues)

        except Exception as e:
            # If a validator fails, create an error issue
            all_issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code=f"{validator_name.lower()}.validator_error",
                message=f"{validator_name} validator failed: {e!s}",
                location={"project_slug": project_slug}
            ))

    return all_issues


def get_validation_summary(issues: list[ValidationIssue]) -> dict[str, int]:
    """Get summary statistics for validation issues.

    Args:
        issues: List of validation issues

    Returns:
        Dictionary with error_count, warning_count, total_count
    """
    error_count = sum(1 for issue in issues if issue.severity == ValidationSeverity.ERROR)
    warning_count = sum(1 for issue in issues if issue.severity == ValidationSeverity.WARNING)

    return {
        "error_count": error_count,
        "warning_count": warning_count,
        "total_count": len(issues)
    }


def format_validation_report(issues: list[ValidationIssue], *, compact: bool = False) -> str:
    """Format validation issues into a human-readable report.

    Args:
        issues: List of validation issues
        compact: If True, use compact single-line format

    Returns:
        Formatted report string
    """
    if not issues:
        return "✓ No validation issues found"

    summary = get_validation_summary(issues)
    lines = []

    # Group issues by category (first part of code before '.')
    categories = {}
    for issue in issues:
        category = issue.code.split('.')[0] if '.' in issue.code else 'other'
        if category not in categories:
            categories[category] = []
        categories[category].append(issue)

    # Format each category
    for category, category_issues in categories.items():
        error_count = sum(1 for i in category_issues if i.severity == ValidationSeverity.ERROR)
        warning_count = sum(1 for i in category_issues if i.severity == ValidationSeverity.WARNING)

        status = "FAIL" if error_count > 0 else "WARN" if warning_count > 0 else "PASS"

        category_name = category.title()
        lines.append(f"{status} {category_name} validation: {error_count} errors, {warning_count} warnings")

        # Add individual issues
        for issue in category_issues:
            severity_icon = "ERROR" if issue.severity == ValidationSeverity.ERROR else "WARNING"

            if compact:
                location_str = ", ".join(f"{k}={v}" for k, v in issue.location.items())
                lines.append(f"  {severity_icon} [{issue.code}] {issue.message} ({location_str})")
            else:
                lines.append(f"  {severity_icon} [{issue.code}] {issue.message}")
                if issue.location:
                    location_str = ", ".join(f"{k}={v}" for k, v in issue.location.items())
                    lines.append(f"    Location: {location_str}")

        lines.append("")  # Blank line between categories

    # Add summary
    lines.append(f"SUMMARY: {summary['error_count']} errors, {summary['warning_count']} warnings found")

    return "\n".join(lines)


__all__ = [
    "ValidationIssue",
    "ValidationSeverity",
    "format_validation_report",
    "get_validation_summary",
    "validate_project",
]
