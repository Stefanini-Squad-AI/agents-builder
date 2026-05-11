"""Pydantic schemas: domain *Views (read-only) + LLM I/O DTOs.

Three logical groups live here:
- `views.py`        : read-only views for API responses and prompt context.
                      Mirror the ORM but are denormalized for client / prompt
                      consumption. `ConfigDict(from_attributes=True)` makes
                      them constructable from ORM rows.
- `llm_io.py`       : structured input/output Pydantic models for the five
                      LLM prompts (ProposeSkillSet, DraftSkillBody,
                      ProposeBacklog, DraftCard, SuggestTechStack).
- `common.py`       : tiny shared models (ValidationIssue) used by validators
                      and surfaced by the CLI / API.
"""

from app.schemas.common import ValidationIssue, ValidationSeverity
from app.schemas.llm_io import (
    DraftedCard,
    DraftedCardInput,
    DraftedResource,
    DraftedSkillBody,
    ProposedBacklog,
    ProposedCard,
    ProposedPhase,
    ProposedSkill,
    ProposedSkillSet,
    SuggestedTechForDimension,
    SuggestedTechItem,
)
from app.schemas.views import (
    ArtifactSummary,
    CardInputView,
    CardView,
    LlmRunView,
    PhaseView,
    ProjectContext,
    ProjectView,
    QaAnswerView,
    SkillResourceView,
    SkillView,
    TechChoiceView,
    TechDimensionView,
    TechItemView,
    TenantView,
    UserView,
)

__all__ = [
    "ArtifactSummary",
    "CardInputView",
    "CardView",
    "DraftedCard",
    "DraftedCardInput",
    "DraftedResource",
    "DraftedSkillBody",
    "LlmRunView",
    "PhaseView",
    "ProjectContext",
    "ProjectView",
    "ProposedBacklog",
    "ProposedCard",
    "ProposedPhase",
    "ProposedSkill",
    "ProposedSkillSet",
    "QaAnswerView",
    "SkillResourceView",
    "SkillView",
    "SuggestedTechForDimension",
    "SuggestedTechItem",
    "TechChoiceView",
    "TechDimensionView",
    "TechItemView",
    "TenantView",
    "UserView",
    "ValidationIssue",
    "ValidationSeverity",
]
