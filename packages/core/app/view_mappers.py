"""Shared ORM → view mappers.

Single source of truth for converting backlog/skill ORM rows into the
denormalized Pydantic views used by both the HTTP API and the exporters.

Kept at the top-level `app` package (not under `app.services`) so importing it
from the exporters does not pull in the `app.services` package __init__, which
imports `export_service` and would create an import cycle
(exporters → services → export_service → exporters).
"""

from __future__ import annotations

from app.domain.backlog import Card
from app.domain.skills import Skill
from app.enums import (
    CardDepRelation,
    CardInputKind,
    CardStatus,
    CardType,
    Priority,
)
from app.schemas.views import CardInputView, CardView, SkillView


def card_to_view(card: Card) -> CardView:
    """Convert a Card ORM row to a CardView with denormalized fields.

    Requires ``card.skill_links``, ``card.deps_out``, and ``card.inputs`` to be
    loaded (eager-load them when querying for export).
    """
    skill_slugs = [link.skill.slug for link in card.skill_links]

    depends_on_codes = [
        dep.depends_on_card.code
        for dep in card.deps_out
        if dep.relation == CardDepRelation.DEPENDS_ON.value
    ]
    parallel_with_codes = [
        dep.depends_on_card.code
        for dep in card.deps_out
        if dep.relation == CardDepRelation.PARALLEL_WITH.value
    ]

    inputs = [
        CardInputView(
            id=inp.id,
            card_id=inp.card_id,
            kind=CardInputKind(inp.kind),
            path=inp.path,
            label=inp.label,
            order_no=inp.order_no,
        )
        for inp in card.inputs
    ]

    return CardView(
        id=card.id,
        phase_id=card.phase_id,
        code=card.code,
        title=card.title,
        type=CardType(card.type),
        story_points=card.story_points,
        priority=Priority(card.priority) if card.priority else None,
        status=CardStatus(card.status),
        human_gate=card.human_gate,
        human_gate_checklist_md=card.human_gate_checklist_md,
        context_md=card.context_md,
        task_md=card.task_md,
        outputs_md=card.outputs_md,
        acceptance_criteria_md=card.acceptance_criteria_md,
        order_no=card.order_no,
        skill_slugs=skill_slugs,
        depends_on_codes=depends_on_codes,
        parallel_with_codes=parallel_with_codes,
        inputs=inputs,
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


def skill_to_view(skill: Skill) -> SkillView:
    """Convert a Skill ORM row (with resources loaded) to a SkillView.

    Uses ``from_attributes`` validation so ``skill.resources`` is converted to
    ``list[SkillResourceView]`` automatically.
    """
    return SkillView.model_validate(skill)
