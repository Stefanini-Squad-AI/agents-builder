"""Base validator interface and common utilities."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.common import ValidationIssue


class BaseValidator(ABC):
    """Base class for all project validators."""

    @abstractmethod
    def validate(self, project_slug: str) -> list[ValidationIssue]:
        """Validate a project and return any issues found.

        Args:
            project_slug: Project to validate

        Returns:
            List of validation issues (empty if no issues)
        """
        ...

    def create_issue(
        self,
        severity: str,
        code: str,
        message: str,
        location: dict[str, str] | None = None
    ) -> ValidationIssue:
        """Helper to create a ValidationIssue with proper typing.

        Args:
            severity: "error" or "warning"
            code: Issue code (e.g. "dag.cycle")
            message: Human-readable description
            location: Context dict (e.g. {"project_slug": "...", "card_code": "..."})

        Returns:
            Properly constructed ValidationIssue
        """
        from app.schemas.common import ValidationSeverity

        return ValidationIssue(
            severity=ValidationSeverity.ERROR if severity == "error" else ValidationSeverity.WARNING,
            code=code,
            message=message,
            location=location or {}
        )
