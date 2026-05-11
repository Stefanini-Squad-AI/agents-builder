"""Shared schema primitives used by both views and validators."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class ValidationIssue(BaseModel):
    """One finding from the deterministic validator suite.

    `location` is a free-form dict that points the UI / CLI at the offending
    entity. Typical keys: `project_slug`, `skill_slug`, `card_code`, `phase_code`.
    """

    model_config = ConfigDict(extra="forbid")

    severity: ValidationSeverity
    code: str  # e.g. "dag.cycle", "card.no_skill", "phase.empty"
    message: str
    location: dict[str, str] = {}
