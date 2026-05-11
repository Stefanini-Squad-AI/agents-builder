"""Integration tests for reference-PoC seeders.

These hit the running Postgres (compose). They are gated by the
WORKSHOP_RUN_INTEGRATION env var, the same gate the existing
test_health_real_services uses.

Each test creates a fresh schema-like isolation by deleting prior
reference projects (idempotency means we can re-seed without crashing).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from app.db import session_scope
from app.domain.backlog import Card, CardDep, Phase
from app.domain.projects import Project, ProjectQaAnswer
from app.domain.skills import Skill
from app.domain.tech import ProjectTechChoice
from app.seed.seeder import seed_reference_pocs, seed_tech_catalog
from sqlalchemy import select

REFERENCE_ROOT = Path(__file__).parent.parent / "app" / "seed" / "reference"


def _skip_if_no_db() -> None:
    if not os.environ.get("WORKSHOP_RUN_INTEGRATION"):
        pytest.skip("set WORKSHOP_RUN_INTEGRATION=1 to enable; requires docker compose up")


def _wipe_reference_projects() -> None:
    """Remove any prior `ref-*` projects so seeders run on a clean slate."""
    with session_scope() as session:
        existing = (
            session.execute(select(Project).where(Project.slug.like("ref-%"))).scalars().all()
        )
        for p in existing:
            session.delete(p)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_seed_reference_pocs_inserts_all_three() -> None:
    """Seeding from scratch produces all three reference PoCs with AC counts."""
    _skip_if_no_db()
    _wipe_reference_projects()

    with session_scope() as session:
        seed_tech_catalog(session)
        report = seed_reference_pocs(session)

    # All three present.
    expected = {"ref-siglm", "ref-cronos", "ref-corp-vli"}
    assert expected.issubset(set(report.keys())), f"missing: {expected - set(report.keys())}"

    # AC from the plan: each PoC must have >= 4 skills, >= 3 phases,
    # >= 6 cards, plus first-3 Q&A answers + a handful of tech choices.
    for slug in expected:
        counts = report[slug]
        assert counts["skills"] >= 4, f"{slug} skills: {counts}"
        assert counts["phases"] >= 3, f"{slug} phases: {counts}"
        assert counts["cards"] >= 6, f"{slug} cards: {counts}"
        assert counts["qa_answers"] >= 3, f"{slug} qa: {counts}"
        assert counts["tech_choices"] >= 5, f"{slug} tech: {counts}"


@pytest.mark.integration
def test_seed_reference_pocs_is_idempotent() -> None:
    """Second run inserts nothing (project-level idempotency)."""
    _skip_if_no_db()
    _wipe_reference_projects()

    with session_scope() as session:
        seed_reference_pocs(session)
    with session_scope() as session:
        second_report = seed_reference_pocs(session)

    for slug, counts in second_report.items():
        assert counts == {"already_present": 1}, (
            f"{slug} re-seed report should be already_present: got {counts}"
        )


@pytest.mark.integration
def test_seeded_card_dependencies_resolve() -> None:
    """Every CardDep.depends_on_card_id must point at an existing Card."""
    _skip_if_no_db()
    _wipe_reference_projects()

    with session_scope() as session:
        seed_reference_pocs(session)

        deps = session.execute(select(CardDep)).scalars().all()
        for dep in deps:
            tgt = session.get(Card, dep.depends_on_card_id)
            assert tgt is not None, f"orphan dep: {dep.card_id} -> {dep.depends_on_card_id}"


@pytest.mark.integration
def test_seeded_ref_siglm_phase_count_and_human_gates() -> None:
    """ref-siglm has 4 phases and at least 3 human-gate cards (one per
    demo)."""
    _skip_if_no_db()
    _wipe_reference_projects()

    with session_scope() as session:
        seed_reference_pocs(session)

        project = session.execute(select(Project).where(Project.slug == "ref-siglm")).scalar_one()

        phases = (
            session.execute(
                select(Phase).where(Phase.project_id == project.id).order_by(Phase.order_no)
            )
            .scalars()
            .all()
        )
        assert len(phases) == 4
        assert [p.code for p in phases] == [
            "phase-0-quality-gates",
            "phase-1-frontend-mock",
            "phase-2-backend-rules-postgres",
            "phase-3-lifecycle-async",
        ]

        gated = session.execute(select(Card).where(Card.human_gate.is_(True))).scalars().all()
        siglm_gated = [c for c in gated if c.code.startswith("SIGLM")]
        assert len(siglm_gated) >= 3


@pytest.mark.integration
def test_seeded_ref_siglm_qa_and_tech() -> None:
    """Q&A required keys present, tech choices reference real items."""
    _skip_if_no_db()
    _wipe_reference_projects()

    with session_scope() as session:
        seed_reference_pocs(session)

        project = session.execute(select(Project).where(Project.slug == "ref-siglm")).scalar_one()

        qa_keys = {
            row.question_key
            for row in session.execute(
                select(ProjectQaAnswer).where(ProjectQaAnswer.project_id == project.id)
            ).scalars()
        }
        required = {"business_problem", "success_definition", "users_and_actors"}
        assert required.issubset(qa_keys), f"missing required Q&A: {required - qa_keys}"

        choices = (
            session.execute(
                select(ProjectTechChoice).where(ProjectTechChoice.project_id == project.id)
            )
            .scalars()
            .all()
        )
        assert len(choices) >= 10, f"too few tech choices: {len(choices)}"

        # All catalog-source choices must have a non-null tech_item_id
        # (only role=tbd allows null; ref-siglm has none of those).
        for c in choices:
            if c.source == "catalog":
                assert c.tech_item_id is not None


@pytest.mark.integration
def test_seeded_skills_have_kinds_and_bodies() -> None:
    """Every skill across all reference PoCs has a non-empty body and a
    trigger-rich description."""
    _skip_if_no_db()
    _wipe_reference_projects()

    with session_scope() as session:
        seed_reference_pocs(session)

        for slug in ("ref-siglm", "ref-cronos", "ref-corp-vli"):
            project = session.execute(select(Project).where(Project.slug == slug)).scalar_one()
            skills = (
                session.execute(select(Skill).where(Skill.project_id == project.id)).scalars().all()
            )
            for s in skills:
                assert s.body_md and len(s.body_md) > 100, (
                    f"{slug}: skill {s.slug} body too short ({len(s.body_md or '')})"
                )
                assert s.description and "use" in s.description.lower(), (
                    f"{slug}: skill {s.slug} description must include 'use'"
                )

        # ref-siglm specifically has at least one context-kind skill.
        siglm = session.execute(select(Project).where(Project.slug == "ref-siglm")).scalar_one()
        siglm_kinds = {
            s.kind
            for s in session.execute(select(Skill).where(Skill.project_id == siglm.id))
            .scalars()
            .all()
        }
        assert "context" in siglm_kinds
