"""Read-only domain views.

These mirror the ORM but are denormalized for HTTP responses and LLM prompt
context. `ConfigDict(from_attributes=True)` lets them be built directly from
ORM rows via `XView.model_validate(orm_row)`.

Notes on import safety: this module imports only from `app.domain.enums`
(pure Python — no SQLAlchemy). It does NOT import the ORM models themselves,
so it stays usable in code paths that should not pull in SQLAlchemy.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.enums import (
    ArtifactKind,
    CardDepRelation,
    CardInputKind,
    CardStatus,
    CardTemplate,
    CardType,
    ExportKind,
    ExtractionStatus,
    Grouping,
    LlmProvider,
    LlmRunKind,
    LlmRunStatus,
    Priority,
    ProjectStatus,
    ProjectType,
    SkillDraftStatus,
    SkillKind,
    SkillResourceLanguage,
    TechChoiceRole,
    TechChoiceSource,
    UserRole,
)

# A single Pydantic config reused by every view: build from ORM, ignore extras.
_VIEW_CONFIG = ConfigDict(from_attributes=True, extra="ignore")


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


class TenantView(BaseModel):
    model_config = _VIEW_CONFIG
    id: UUID
    name: str
    created_at: datetime


class UserView(BaseModel):
    model_config = _VIEW_CONFIG
    id: UUID
    email: str
    name: str
    role: UserRole
    created_at: datetime


# ---------------------------------------------------------------------------
# Tech panorama
# ---------------------------------------------------------------------------


class TechItemView(BaseModel):
    model_config = _VIEW_CONFIG
    id: UUID
    dimension_id: UUID
    slug: str
    name: str
    description: str | None = None
    tags: list[str] = []
    is_custom: bool = False


class TechDimensionView(BaseModel):
    model_config = _VIEW_CONFIG
    id: UUID
    slug: str
    name: str
    description: str | None = None
    order_no: int = 0
    items: list[TechItemView] = []


class TechChoiceView(BaseModel):
    """Denormalized: includes the resolved item name/slug when present.

    A row with `role == TBD` carries `tech_item_id = None` and only the
    dimension reference; the resolved item fields stay None.
    """

    model_config = _VIEW_CONFIG
    id: UUID
    project_id: UUID
    dimension_id: UUID
    dimension_slug: str
    dimension_name: str
    tech_item_id: UUID | None = None
    tech_item_slug: str | None = None
    tech_item_name: str | None = None
    role: TechChoiceRole
    source: TechChoiceSource
    accepted: bool = True
    llm_rationale: str | None = None
    llm_confidence: Decimal | None = None
    notes: str | None = None
    order_no: int = 0


# ---------------------------------------------------------------------------
# Projects (incl. artifacts, qa)
# ---------------------------------------------------------------------------


class QaAnswerView(BaseModel):
    model_config = _VIEW_CONFIG
    project_id: UUID
    question_key: str
    answer_md: str
    updated_at: datetime


class ArtifactSummary(BaseModel):
    """Compact view of a project artifact for inclusion in prompt context.

    `content_md_excerpt` is the first ~2000 characters of the extracted
    markdown; the full content is too large to ship to every prompt.
    """

    model_config = _VIEW_CONFIG
    id: UUID
    filename: str
    kind: ArtifactKind
    extraction_status: ExtractionStatus
    size_bytes: int
    content_md_excerpt: str | None = None
    content_md_truncated: bool = False


class ProjectView(BaseModel):
    model_config = _VIEW_CONFIG
    id: UUID
    tenant_id: UUID
    owner_user_id: UUID
    slug: str
    name: str
    objective: str
    context_md: str | None = None
    card_code_prefix: str
    card_template: CardTemplate
    grouping: Grouping
    status: ProjectStatus
    project_type: ProjectType = ProjectType.APPLICATION
    source_technology: str | None = None
    target_technology: str | None = None
    llm_provider: LlmProvider
    llm_model: str
    llm_temperature: Decimal
    llm_enable_reasoning: bool = False
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


class SkillResourceView(BaseModel):
    model_config = _VIEW_CONFIG
    id: UUID
    skill_id: UUID
    filename: str
    content: str
    language: SkillResourceLanguage
    order_no: int = 0


class SkillView(BaseModel):
    model_config = _VIEW_CONFIG
    id: UUID
    project_id: UUID
    slug: str
    name: str
    description: str
    kind: SkillKind
    body_md: str
    order_no: int = 0
    resources: list[SkillResourceView] = []
    # Draft status tracking
    draft_status: SkillDraftStatus = SkillDraftStatus.NONE
    last_llm_run_id: UUID | None = None
    draft_error: str | None = None


# ---------------------------------------------------------------------------
# Backlog: phases, cards
# ---------------------------------------------------------------------------


class CardInputView(BaseModel):
    model_config = _VIEW_CONFIG
    id: UUID
    card_id: UUID
    kind: CardInputKind
    path: str
    label: str | None = None
    order_no: int = 0


class CardDepView(BaseModel):
    """Edge in the DAG, expressed using card *codes* (not UUIDs) for readability."""

    model_config = _VIEW_CONFIG
    from_code: str
    to_code: str
    relation: CardDepRelation


class CardView(BaseModel):
    model_config = _VIEW_CONFIG
    id: UUID
    phase_id: UUID
    code: str
    title: str
    type: CardType
    story_points: int | None = None
    priority: Priority | None = None
    status: CardStatus
    human_gate: bool = False
    human_gate_checklist_md: str | None = None
    context_md: str | None = None
    task_md: str | None = None
    outputs_md: str | None = None
    acceptance_criteria_md: str | None = None
    order_no: int = 0
    # Denormalized helpers populated by the API layer
    skill_slugs: list[str] = Field(default_factory=list)
    depends_on_codes: list[str] = Field(default_factory=list)
    parallel_with_codes: list[str] = Field(default_factory=list)
    inputs: list[CardInputView] = []
    created_at: datetime
    updated_at: datetime


class PhaseView(BaseModel):
    model_config = _VIEW_CONFIG
    id: UUID
    project_id: UUID
    code: str
    name: str
    description_md: str | None = None
    order_no: int = 0
    cards: list[CardView] = []


class CardLinkView(BaseModel):
    """Resolved link target for a card, used to render cross-card markdown links.

    `phase_folder` and `filename` mirror the on-disk export layout so links in
    rendered cards/READMEs point at the actual files.
    """

    model_config = _VIEW_CONFIG
    code: str
    title: str
    phase_folder: str
    filename: str


# ---------------------------------------------------------------------------
# Project context — the composite payload every LLM prompt receives
# ---------------------------------------------------------------------------


class ProjectContext(BaseModel):
    """Composite context payload assembled by the API for each LLM call.

    Discovery channels (objective + Q&A + tech + artifacts) all collapse into
    this single structure. Prompts render it into the user-message body via
    a shared template helper (Step 1.6+).
    """

    model_config = ConfigDict(extra="forbid")

    objective: str
    qa: dict[str, str] = {}  # question_key -> answer_md
    tech_choices_by_dimension: dict[str, list[TechChoiceView]] = {}
    artifact_summaries: list[ArtifactSummary] = []
    context_notes_md: str = ""


# ---------------------------------------------------------------------------
# LLM run audit view
# ---------------------------------------------------------------------------


class LlmRunView(BaseModel):
    model_config = _VIEW_CONFIG
    id: UUID
    project_id: UUID | None = None
    kind: LlmRunKind
    provider: LlmProvider
    model: str
    response_text: str | None = None
    response_json: dict[str, Any] | None = None
    reasoning_md: str | None = None
    reasoning_tokens: int | None = None
    reasoning_truncated: bool = False
    extended_thinking_enabled: bool = False
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: Decimal | None = None
    status: LlmRunStatus
    error: str | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Exports view
# ---------------------------------------------------------------------------


class ExportView(BaseModel):
    model_config = _VIEW_CONFIG
    id: UUID
    project_id: UUID
    kind: ExportKind
    target_path: str | None = None
    manifest_json: dict[str, Any]
    created_at: datetime
