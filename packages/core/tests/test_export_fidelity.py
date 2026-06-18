"""Golden + unit tests for filesystem export fidelity (Plan 1 fix).

These run without a database: `_load_project_data` is monkeypatched to return
ORM-shaped `SimpleNamespace` objects, so the exporter exercises the real
converters, templates, and link resolution end-to-end against a tmp dir.

Regression coverage:
- Export no longer crashes on projects with skills (the `trigger_phrases` bug).
- Skill resources are written.
- Cards render their skill links, inputs, and dependency links.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app.domain import register_models

register_models()

from app.exporters.filesystem import FilesystemExporter  # noqa: E402
from app.view_mappers import card_to_view, skill_to_view  # noqa: E402

_NOW = datetime(2026, 6, 8, tzinfo=timezone.utc)


def _build_fixture():
    """Build an ORM-shaped fixture: 1 project, 1 phase, 2 cards, 1 skill."""
    project_id = uuid.uuid4()
    phase_id = uuid.uuid4()
    skill_id = uuid.uuid4()

    resource = SimpleNamespace(
        id=uuid.uuid4(),
        skill_id=skill_id,
        filename="queries.sql",
        content="SELECT 1;",
        language="sql",
        order_no=0,
    )
    skill = SimpleNamespace(
        id=skill_id,
        project_id=project_id,
        slug="ssis-analyzer",
        name="SSIS Analyzer",
        description="Use when analyzing SSIS packages",
        kind="analyzer",
        body_md="# How to analyze",
        order_no=0,
        resources=[resource],
        draft_status="none",
        last_llm_run_id=None,
        draft_error=None,
    )

    def _card(code, title, order_no, deps_out, inputs):
        return SimpleNamespace(
            id=uuid.uuid4(),
            phase_id=phase_id,
            code=code,
            title=title,
            type="Task",
            story_points=3,
            priority=None,
            status="draft",
            human_gate=False,
            human_gate_checklist_md=None,
            context_md=f"Context for {code}",
            task_md=f"Task for {code}",
            outputs_md=f"Outputs for {code}",
            acceptance_criteria_md=f"AC for {code}",
            order_no=order_no,
            skill_links=[SimpleNamespace(skill=skill, position=0)],
            deps_out=deps_out,
            inputs=inputs,
            created_at=_NOW,
            updated_at=_NOW,
        )

    card1 = _card("DEMO-101", "First Card", 0, deps_out=[], inputs=[])
    card2 = _card(
        "DEMO-102",
        "Second Card",
        1,
        deps_out=[
            SimpleNamespace(
                relation="depends_on",
                depends_on_card=SimpleNamespace(code="DEMO-101"),
            )
        ],
        inputs=[
            SimpleNamespace(
                id=uuid.uuid4(),
                card_id=uuid.uuid4(),
                kind="skill_resource",
                path="ssis-analyzer/queries.sql",
                label="Queries",
                order_no=0,
            )
        ],
    )

    phase = SimpleNamespace(
        id=phase_id,
        project_id=project_id,
        code="phase-1-discovery",
        name="Discovery",
        description_md="Discovery phase",
        order_no=1,
    )
    project = SimpleNamespace(
        id=project_id,
        tenant_id=uuid.uuid4(),
        owner_user_id=uuid.uuid4(),
        slug="demo",
        name="Demo Project",
        objective="Migrate things",
        context_md=None,
        card_code_prefix="DEMO",
        card_template="phase_vli",
        grouping="phase",
        status="draft",
        llm_provider="anthropic",
        llm_model="claude-sonnet-4-5",
        llm_temperature=Decimal("0.2"),
        llm_enable_reasoning=False,
        created_at=_NOW,
        updated_at=_NOW,
    )

    return project, [phase], [card1, card2], [skill]


# -----------------------------------------------------------------------------
# Mapper unit tests
# -----------------------------------------------------------------------------


def test_card_to_view_denormalizes_links_and_inputs() -> None:
    _, _, (card1, card2), _ = _build_fixture()

    view2 = card_to_view(card2)
    assert view2.skill_slugs == ["ssis-analyzer"]
    assert view2.depends_on_codes == ["DEMO-101"]
    assert view2.parallel_with_codes == []
    assert len(view2.inputs) == 1
    assert view2.inputs[0].kind.value == "skill_resource"


def test_skill_to_view_includes_resources() -> None:
    _, _, _, (skill,) = _build_fixture()
    view = skill_to_view(skill)
    assert view.slug == "ssis-analyzer"
    assert len(view.resources) == 1
    assert view.resources[0].filename == "queries.sql"


# -----------------------------------------------------------------------------
# Golden export test
# -----------------------------------------------------------------------------


def test_export_writes_full_fidelity_tree(tmp_path) -> None:  # noqa: ANN001
    fixture = _build_fixture()
    exporter = FilesystemExporter(target_path=tmp_path)

    with patch.object(exporter, "_load_project_data", return_value=fixture):
        manifest = exporter.export_project("demo")

    assert manifest.total_files > 0

    agents = tmp_path / ".agents"

    # Skill + its resource are written
    skill_md = agents / "skills" / "ssis-analyzer" / "SKILL.md"
    assert skill_md.exists()
    assert "name: SSIS Analyzer" in skill_md.read_text(encoding="utf-8")
    resource = agents / "skills" / "ssis-analyzer" / "resources" / "queries.sql"
    assert resource.exists()
    assert "SELECT 1;" in resource.read_text(encoding="utf-8")

    # Card 2 renders skill link, input, and dependency link
    card2_md = (
        agents / "jira-cards" / "phase-1-discovery" / "DEMO-102-second-card.md"
    ).read_text(encoding="utf-8")
    assert "(.agents/skills/ssis-analyzer/SKILL.md)" in card2_md
    assert ".agents/skills/ssis-analyzer/queries.sql" in card2_md
    assert "[DEMO-101](../phase-1-discovery/DEMO-101-first-card.md)" in card2_md

    # Phase README lists the referenced skill and the dependency
    phase_readme = (
        agents / "jira-cards" / "phase-1-discovery" / "README.md"
    ).read_text(encoding="utf-8")
    assert "ssis-analyzer" in phase_readme
    assert "**DEMO-102** depends on **DEMO-101**" in phase_readme

    # Project README links into jira-cards/ and lists the skill
    project_readme = (agents / "README.md").read_text(encoding="utf-8")
    assert "jira-cards/phase-1-discovery/README.md" in project_readme
    assert "skills/ssis-analyzer/SKILL.md" in project_readme
