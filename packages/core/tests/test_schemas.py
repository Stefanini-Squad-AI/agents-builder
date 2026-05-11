"""Unit tests for Pydantic schemas.

These tests exercise the schemas in isolation — they do NOT import
`app.domain` (the SQLAlchemy ORM), only `app.domain.enums` (pure Python).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from app.enums import (
    CardInputKind,
    CardStatus,
    CardTemplate,
    CardType,
    Grouping,
    LlmProvider,
    ProjectStatus,
    SkillKind,
    SkillResourceLanguage,
    TechChoiceRole,
    UserRole,
)
from app.schemas import (
    ArtifactSummary,
    CardView,
    DraftedCard,
    DraftedCardInput,
    DraftedResource,
    DraftedSkillBody,
    PhaseView,
    ProjectContext,
    ProjectView,
    ProposedCard,
    ProposedPhase,
    ProposedSkill,
    ProposedSkillSet,
    SuggestedTechForDimension,
    SuggestedTechItem,
    TenantView,
    UserView,
    ValidationIssue,
    ValidationSeverity,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Views: round-trip + enum coercion
# ---------------------------------------------------------------------------


def test_tenant_user_view_roundtrip() -> None:
    now = datetime.now(UTC)
    t = TenantView(id=uuid4(), name="Default", created_at=now)
    assert TenantView.model_validate(t.model_dump()) == t

    u = UserView(id=uuid4(), email="x@y", name="Local", role=UserRole.OWNER, created_at=now)
    assert u.role == UserRole.OWNER
    again = UserView.model_validate(u.model_dump())
    assert again.role == UserRole.OWNER


def test_project_view_accepts_decimal_temperature() -> None:
    now = datetime.now(UTC)
    p = ProjectView(
        id=uuid4(),
        tenant_id=uuid4(),
        owner_user_id=uuid4(),
        slug="demo",
        name="Demo",
        objective="Build a thing",
        card_code_prefix="DEMO",
        card_template=CardTemplate.PHASE_VLI,
        grouping=Grouping.PHASE,
        status=ProjectStatus.DRAFT,
        llm_provider=LlmProvider.ANTHROPIC,
        llm_model="claude-sonnet-4-5",
        llm_temperature=Decimal("0.20"),
        created_at=now,
        updated_at=now,
    )
    assert p.llm_temperature == Decimal("0.20")
    # Round-trip preserves Decimal
    again = ProjectView.model_validate(p.model_dump())
    assert again.llm_temperature == Decimal("0.20")


def test_phase_and_card_view_assemble() -> None:
    now = datetime.now(UTC)
    card = CardView(
        id=uuid4(),
        phase_id=uuid4(),
        code="DEMO-101",
        title="Bootstrap",
        type=CardType.TASK,
        story_points=2,
        status=CardStatus.READY,
        skill_slugs=["context", "scaffold"],
        depends_on_codes=[],
        parallel_with_codes=["DEMO-102"],
        created_at=now,
        updated_at=now,
    )
    phase = PhaseView(
        id=uuid4(),
        project_id=uuid4(),
        code="phase-1-discovery",
        name="Discovery",
        order_no=0,
        cards=[card],
    )
    assert phase.cards[0].code == "DEMO-101"


def test_project_context_default_init() -> None:
    ctx = ProjectContext(objective="x")
    assert ctx.qa == {}
    assert ctx.artifact_summaries == []
    assert ctx.context_notes_md == ""


# ---------------------------------------------------------------------------
# LLM I/O: structural constraints
# ---------------------------------------------------------------------------


def test_proposed_skill_set_enforces_size() -> None:
    """Less than 3 skills must fail; more than 12 must fail."""
    with pytest.raises(ValidationError):
        ProposedSkillSet(skills=[], coverage_notes="empty")

    too_many = [
        ProposedSkill(
            slug=f"s-{i}",
            name=f"S{i}",
            description=f"use when {i}",
            kind=SkillKind.AUTHORING,
            rationale="r",
        )
        for i in range(13)
    ]
    with pytest.raises(ValidationError):
        ProposedSkillSet(skills=too_many, coverage_notes="too many")


def test_proposed_skill_set_happy_path() -> None:
    skills = [
        ProposedSkill(
            slug="proj-context",
            name="Project Context",
            description="Use whenever the user asks about this project's domain.",
            kind=SkillKind.CONTEXT,
            rationale="Single source of truth for glossary and gaps.",
            sibling_refs=[],
        ),
        ProposedSkill(
            slug="add-feature",
            name="Add Feature",
            description="Use when adding a new full-stack feature.",
            kind=SkillKind.AUTHORING,
            rationale="Project follows a fixed full-stack chain.",
            sibling_refs=["proj-context"],
        ),
        ProposedSkill(
            slug="analyze-legacy",
            name="Analyze Legacy",
            description="Use when extracting business rules from legacy code.",
            kind=SkillKind.ANALYZER,
            rationale="Legacy code is the only source of truth for some rules.",
            sibling_refs=["proj-context"],
        ),
    ]
    s = ProposedSkillSet(skills=skills, coverage_notes="ok")
    assert len(s.skills) == 3


def test_drafted_skill_body_resources_optional() -> None:
    b = DraftedSkillBody(body_md="# X", resources=[], sibling_skills_referenced=[])
    assert b.resources == []

    b2 = DraftedSkillBody(
        body_md="# X",
        resources=[
            DraftedResource(
                filename="template.md",
                language=SkillResourceLanguage.MARKDOWN,
                content="hello",
                purpose="checklist",
            )
        ],
        sibling_skills_referenced=["proj-context"],
    )
    assert b2.resources[0].language == SkillResourceLanguage.MARKDOWN


def test_proposed_backlog_phase_must_have_cards() -> None:
    """A phase must contain at least one card."""
    with pytest.raises(ValidationError):
        ProposedPhase(
            code="phase-1-discovery",
            name="Discovery",
            description="d",
            cards=[],
        )


def test_proposed_backlog_card_story_points_bounded() -> None:
    """Story points are bounded to a sane range (1..21)."""
    with pytest.raises(ValidationError):
        ProposedCard(
            code="X-101",
            title="x",
            type=CardType.TASK,
            story_points=99,
            short_scope_summary="x",
        )


def test_drafted_card_inputs() -> None:
    c = DraftedCard(
        context_md="ctx",
        task_md="t",
        outputs_md="o",
        acceptance_criteria_md="- [ ] a",
        inputs=[
            DraftedCardInput(
                kind=CardInputKind.SKILL_RESOURCE,
                path=".agents/skills/foo/resources/bar.md",
                label="Bar template",
            ),
        ],
    )
    assert c.inputs[0].kind == CardInputKind.SKILL_RESOURCE


def test_suggested_tech_confidence_clamped() -> None:
    """Confidence must be in [0, 1]."""
    with pytest.raises(ValidationError):
        SuggestedTechItem(
            free_form_name="X",
            role=TechChoiceRole.TARGET,
            rationale="r",
            confidence=1.5,
        )


def test_suggested_tech_for_dimension_happy() -> None:
    s = SuggestedTechForDimension(
        dimension_slug="languages",
        items=[
            SuggestedTechItem(
                catalog_slug="python",
                role=TechChoiceRole.TARGET,
                rationale="Backend lingua franca.",
                confidence=0.9,
            ),
        ],
        reasoning_summary="Sole target language",
    )
    assert s.items[0].catalog_slug == "python"


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------


def test_validation_issue_severity_enum() -> None:
    iss = ValidationIssue(
        severity=ValidationSeverity.ERROR,
        code="dag.cycle",
        message="A -> B -> A",
        location={"card_codes": "A,B,A"},
    )
    assert iss.severity == ValidationSeverity.ERROR
    assert iss.model_dump()["severity"] == "error"


def test_artifact_summary_optional_fields() -> None:
    from app.enums import ArtifactKind, ExtractionStatus

    a = ArtifactSummary(
        id=uuid4(),
        filename="spec.pdf",
        kind=ArtifactKind.SPEC,
        extraction_status=ExtractionStatus.PENDING,
        size_bytes=1024,
    )
    assert a.content_md_excerpt is None
    assert a.content_md_truncated is False
