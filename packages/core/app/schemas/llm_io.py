"""Structured input/output Pydantic models for the five LLM prompts.

Each prompt declares its `response_schema` as one of the `*` output models
here. Providers (Anthropic tool-use, OpenAI JSON mode, Ollama lenient parse)
all unify on these schemas.

The five prompts:
  1. ProposeSkillSet     -> ProposedSkillSet
  2. DraftSkillBody      -> DraftedSkillBody
  3. ProposeBacklog      -> ProposedBacklog
  4. DraftCard           -> DraftedCard
  5. SuggestTechStack    -> SuggestedTechForDimension
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import (
    CardInputKind,
    CardType,
    SkillKind,
    SkillResourceLanguage,
    TechChoiceRole,
)

_LLM_CONFIG = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 1. ProposeSkillSet
# ---------------------------------------------------------------------------


class ProposedSkill(BaseModel):
    model_config = _LLM_CONFIG

    slug: str = Field(
        ...,
        description="kebab-case identifier, prefixed with the project slug when helpful",
    )
    name: str = Field(..., description="Human-readable title")
    description: str = Field(
        ...,
        description=(
            "YAML-frontmatter-style description with trigger phrases. "
            "Must state what the skill does AND when to invoke it."
        ),
    )
    kind: SkillKind
    rationale: str = Field(..., description="Why this skill exists in this specific project.")
    sibling_refs: list[str] = Field(
        default_factory=list,
        description="Slugs of other proposed skills this one will reference.",
    )


class ProposedSkillSet(BaseModel):
    """Output of `ProposeSkillSet` (Step 1.6)."""

    model_config = _LLM_CONFIG

    skills: list[ProposedSkill] = Field(..., min_length=3, max_length=12)
    coverage_notes: str = Field(
        ..., description="Which areas of the objective the proposed set covers."
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="Areas that may need a skill but are unclear from the inputs.",
    )


# ---------------------------------------------------------------------------
# 2. DraftSkillBody
# ---------------------------------------------------------------------------


class DraftedResource(BaseModel):
    model_config = _LLM_CONFIG

    filename: str
    language: SkillResourceLanguage
    content: str
    purpose: str = Field(..., description="One-sentence rationale for why this resource exists.")


class DraftedSkillBody(BaseModel):
    """Output of `DraftSkillBody` (Step 1.7)."""

    model_config = _LLM_CONFIG

    body_md: str = Field(..., description="The SKILL.md body below the YAML frontmatter.")
    resources: list[DraftedResource] = Field(default_factory=list)
    sibling_skills_referenced: list[str] = Field(
        default_factory=list,
        description="Slugs of sibling skills the body mentions; must be real.",
    )


# ---------------------------------------------------------------------------
# 3. ProposeBacklog
# ---------------------------------------------------------------------------


class ProposedCard(BaseModel):
    model_config = _LLM_CONFIG

    code: str = Field(
        ..., description="Format: <project.card_code_prefix>-<phase><card>, e.g. SIGLM-101"
    )
    title: str
    type: CardType
    story_points: int = Field(..., ge=1, le=21)
    skill_slugs: list[str] = Field(
        default_factory=list, description="Skills the card will invoke, in order."
    )
    depends_on_codes: list[str] = Field(default_factory=list)
    parallel_with_codes: list[str] = Field(default_factory=list)
    human_gate: bool = False
    short_scope_summary: str = Field(
        ...,
        description=(
            "One paragraph summarizing the work. The full card body is drafted "
            "later by `DraftCard`."
        ),
    )


class ProposedPhase(BaseModel):
    model_config = _LLM_CONFIG

    code: str = Field(..., description="Phase folder slug, e.g. phase-1-discovery")
    name: str
    description: str
    cards: list[ProposedCard] = Field(..., min_length=1)


class ProposedBacklog(BaseModel):
    """Output of `ProposeBacklog` (Step 1.8)."""

    model_config = _LLM_CONFIG

    phases: list[ProposedPhase] = Field(..., min_length=2, max_length=10)
    rationale_md: str = Field(..., description="Why this phase structure.")
    critical_path_codes: list[str] = Field(
        default_factory=list,
        description="Ordered list of card codes representing the critical path.",
    )


# ---------------------------------------------------------------------------
# 4. DraftCard
# ---------------------------------------------------------------------------


class DraftedCardInput(BaseModel):
    model_config = _LLM_CONFIG

    kind: CardInputKind
    path: str = Field(
        ...,
        description=(
            "Path resolvable relative to .agents/ or data/. For skill_resource "
            "kind, must match an existing resource on a skill in skill_slugs."
        ),
    )
    label: str | None = None


class DraftedCard(BaseModel):
    """Output of `DraftCard` (Step 1.9)."""

    model_config = _LLM_CONFIG

    context_md: str
    task_md: str
    outputs_md: str
    acceptance_criteria_md: str = Field(
        ...,
        description=("Markdown checkbox list. Each item must be testable from the outputs alone."),
    )
    human_gate_checklist_md: str | None = Field(
        None,
        description="Required iff the card has human_gate=true; otherwise None.",
    )
    inputs: list[DraftedCardInput] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 5. SuggestTechStack
# ---------------------------------------------------------------------------


class SuggestedTechItem(BaseModel):
    model_config = _LLM_CONFIG

    catalog_slug: str | None = Field(
        None,
        description=(
            "If the proposal matches an existing catalog item, its slug. "
            "Otherwise None and `free_form_name` is set."
        ),
    )
    free_form_name: str | None = Field(
        None,
        description="Set when no catalog match exists. Will be inserted as a user-added item.",
    )
    role: TechChoiceRole
    rationale: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class SuggestedTechForDimension(BaseModel):
    """Output of `SuggestTechStack` (Step 1.10).

    Returned per single dimension. The UI calls this prompt once per
    "Suggest with AI" button click; the user then accepts/edits each chip.
    """

    model_config = _LLM_CONFIG

    dimension_slug: str
    items: list[SuggestedTechItem] = Field(..., max_length=10)
    reasoning_summary: str = Field(
        ...,
        description="Short paragraph explaining the rationale across all items.",
    )


# ---------------------------------------------------------------------------
# Shared LLM-execution kind tag (matches LlmRunKind in app.domain.enums)
# ---------------------------------------------------------------------------

PromptKind = Literal[
    "propose_skill_set",
    "draft_skill_body",
    "propose_backlog",
    "draft_card",
    "suggest_tech",
    "other",
]
