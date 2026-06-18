"""Backlog API — Phases, Cards, and LLM proposal.

Endpoints:
- GET    /api/projects/{slug}/phases                     list all phases for project
- GET    /api/projects/{slug}/phases/{phase_id}          get single phase with cards
- PATCH  /api/projects/{slug}/phases/{phase_id}          update phase
- GET    /api/projects/{slug}/cards                      list all cards for project
- GET    /api/projects/{slug}/cards/{card_id}            get single card
- PATCH  /api/projects/{slug}/cards/{card_id}            update card
- GET    /api/projects/{slug}/cards/stats                card statistics
- POST   /api/projects/{slug}/backlog/propose            propose backlog via LLM
- POST   /api/projects/{slug}/backlog/bulk               bulk create from proposals
- PATCH  /api/projects/{slug}/cards/{card_id}/sections/{section}           update section
- POST   /api/projects/{slug}/cards/{card_id}/sections/{section}/regenerate regenerate section
- POST   /api/projects/{slug}/cards/{card_id}/draft      draft entire card via LLM
- PUT    /api/projects/{slug}/cards/{card_id}/dependencies update dependencies
- GET    /api/projects/{slug}/cards/{card_id}/inputs     list card inputs
- POST   /api/projects/{slug}/cards/{card_id}/inputs     create card input
- PATCH  /api/projects/{slug}/cards/{card_id}/inputs/{id} update card input
- DELETE /api/projects/{slug}/cards/{card_id}/inputs/{id} delete card input
- GET    /api/projects/{slug}/dag                        get project DAG for visualization
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.domain.backlog import Card, CardDep, CardInput, CardSkill, Phase
from app.domain.projects import Project
from app.domain.skills import Skill
from app.enums import (
    CardDepRelation,
    CardInputKind,
    CardStatus,
    CardType,
    LlmRunKind,
    Priority,
)
from app.families import get_family
from app.prompts import DraftCardPrompt, ProposeBacklogPrompt
from app.schemas.llm_io import ProposedBacklog, ProposedCard, ProposedPhase
from app.schemas.views import CardInputView, CardView, PhaseView, SkillView
from app.services.llm_service_factory import LlmServiceFactory
from app.services.project_context_service import ProjectContextService

router = APIRouter(tags=["backlog"])


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class UpdatePhaseRequest(BaseModel):
    """Request to update a phase."""

    name: str | None = None
    description_md: str | None = None


class UpdateCardRequest(BaseModel):
    """Request to update a card."""

    title: str | None = None
    context_md: str | None = None
    task_md: str | None = None
    outputs_md: str | None = None
    acceptance_criteria_md: str | None = None
    human_gate: bool | None = None
    human_gate_checklist_md: str | None = None
    story_points: int | None = None
    priority: Priority | None = None
    status: CardStatus | None = None


class CardsStatsResponse(BaseModel):
    """Card statistics response."""

    total: int
    by_type: dict[str, int]
    by_status: dict[str, int]
    by_priority: dict[str, int]
    total_story_points: int


class ProposeBacklogResponse(BaseModel):
    """Response from backlog proposal."""

    phases: list[PhaseView]
    rationale_md: str
    critical_path_codes: list[str]
    llm_run_id: UUID


class BulkPhaseRequest(BaseModel):
    """Single phase in bulk create request."""

    code: str
    name: str
    description: str = ""
    cards: list["BulkCardRequest"] = Field(default_factory=list)


class BulkCardRequest(BaseModel):
    """Single card in bulk create request."""

    code: str
    title: str
    type: CardType
    story_points: int = 3
    skill_slugs: list[str] = Field(default_factory=list)
    depends_on_codes: list[str] = Field(default_factory=list)
    parallel_with_codes: list[str] = Field(default_factory=list)
    human_gate: bool = False
    short_scope_summary: str = ""


class BulkCreateBacklogRequest(BaseModel):
    """Request to bulk create backlog from proposals."""

    phases: list[BulkPhaseRequest] = Field(..., min_length=1, max_length=10)


class BulkCreateBacklogResponse(BaseModel):
    """Response from bulk backlog creation."""

    phases_created: int
    cards_created: int
    phases: list[PhaseView]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _get_project_by_slug(session: Session, slug: str) -> Project:
    """Get project by slug or raise 404."""
    project = session.execute(
        select(Project).where(Project.slug == slug)
    ).scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return project


def _card_to_view(card: Card) -> CardView:
    """Convert Card ORM to CardView with denormalized fields."""
    # Get skill slugs
    skill_slugs = [link.skill.slug for link in card.skill_links]

    # Get dependency codes
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

    # Get inputs
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


def _phase_to_view(phase: Phase) -> PhaseView:
    """Convert Phase ORM to PhaseView with cards."""
    cards = [_card_to_view(card) for card in phase.cards]
    return PhaseView(
        id=phase.id,
        project_id=phase.project_id,
        code=phase.code,
        name=phase.name,
        description_md=phase.description_md,
        order_no=phase.order_no,
        cards=cards,
    )


def _skill_to_view(skill: Skill) -> SkillView:
    """Convert Skill ORM to SkillView."""
    from app.enums import SkillKind, SkillResourceLanguage
    from app.schemas.views import SkillResourceView

    return SkillView(
        id=skill.id,
        project_id=skill.project_id,
        slug=skill.slug,
        name=skill.name,
        description=skill.description,
        kind=SkillKind(skill.kind),
        body_md=skill.body_md,
        order_no=skill.order_no,
        resources=[
            SkillResourceView(
                id=r.id,
                skill_id=r.skill_id,
                filename=r.filename,
                content=r.content,
                language=SkillResourceLanguage(r.language),
                order_no=r.order_no,
            )
            for r in skill.resources
        ],
    )


# ---------------------------------------------------------------------------
# Phase endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/api/projects/{slug}/phases",
    response_model=list[PhaseView],
)
def list_phases(
    slug: str,
    session: Session = Depends(get_session),
) -> list[PhaseView]:
    """List all phases for a project with their cards."""
    project = _get_project_by_slug(session, slug)

    phases = (
        session.execute(
            select(Phase)
            .where(Phase.project_id == project.id)
            .options(
                selectinload(Phase.cards)
                .selectinload(Card.skill_links)
                .selectinload(CardSkill.skill),
                selectinload(Phase.cards)
                .selectinload(Card.deps_out)
                .selectinload(CardDep.depends_on_card),
                selectinload(Phase.cards).selectinload(Card.inputs),
            )
            .order_by(Phase.order_no)
        )
        .scalars()
        .all()
    )

    return [_phase_to_view(p) for p in phases]


@router.get(
    "/api/projects/{slug}/phases/{phase_id}",
    response_model=PhaseView,
)
def get_phase(
    slug: str,
    phase_id: UUID,
    session: Session = Depends(get_session),
) -> PhaseView:
    """Get a single phase with its cards."""
    project = _get_project_by_slug(session, slug)

    phase = session.execute(
        select(Phase)
        .where(Phase.id == phase_id, Phase.project_id == project.id)
        .options(
            selectinload(Phase.cards)
            .selectinload(Card.skill_links)
            .selectinload(CardSkill.skill),
            selectinload(Phase.cards)
            .selectinload(Card.deps_out)
            .selectinload(CardDep.depends_on_card),
            selectinload(Phase.cards).selectinload(Card.inputs),
        )
    ).scalar_one_or_none()

    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")

    return _phase_to_view(phase)


@router.patch(
    "/api/projects/{slug}/phases/{phase_id}",
    response_model=PhaseView,
)
def update_phase(
    slug: str,
    phase_id: UUID,
    request: UpdatePhaseRequest,
    session: Session = Depends(get_session),
) -> PhaseView:
    """Update a phase."""
    project = _get_project_by_slug(session, slug)

    phase = session.execute(
        select(Phase)
        .where(Phase.id == phase_id, Phase.project_id == project.id)
        .options(
            selectinload(Phase.cards)
            .selectinload(Card.skill_links)
            .selectinload(CardSkill.skill),
            selectinload(Phase.cards)
            .selectinload(Card.deps_out)
            .selectinload(CardDep.depends_on_card),
            selectinload(Phase.cards).selectinload(Card.inputs),
        )
    ).scalar_one_or_none()

    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")

    if request.name is not None:
        phase.name = request.name
    if request.description_md is not None:
        phase.description_md = request.description_md

    session.commit()
    session.refresh(phase)

    return _phase_to_view(phase)


# ---------------------------------------------------------------------------
# Card endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/api/projects/{slug}/cards",
    response_model=list[CardView],
)
def list_cards(
    slug: str,
    session: Session = Depends(get_session),
) -> list[CardView]:
    """List all cards for a project."""
    project = _get_project_by_slug(session, slug)

    # Get all phases for ordering
    phases = (
        session.execute(
            select(Phase)
            .where(Phase.project_id == project.id)
            .options(
                selectinload(Phase.cards)
                .selectinload(Card.skill_links)
                .selectinload(CardSkill.skill),
                selectinload(Phase.cards)
                .selectinload(Card.deps_out)
                .selectinload(CardDep.depends_on_card),
                selectinload(Phase.cards).selectinload(Card.inputs),
            )
            .order_by(Phase.order_no)
        )
        .scalars()
        .all()
    )

    # Flatten cards from all phases
    cards = []
    for phase in phases:
        cards.extend([_card_to_view(card) for card in phase.cards])

    return cards


@router.get(
    "/api/projects/{slug}/cards/stats",
    response_model=CardsStatsResponse,
)
def get_cards_stats(
    slug: str,
    session: Session = Depends(get_session),
) -> CardsStatsResponse:
    """Get card statistics for a project."""
    project = _get_project_by_slug(session, slug)

    # Get all cards via phases
    phases = (
        session.execute(
            select(Phase)
            .where(Phase.project_id == project.id)
            .options(selectinload(Phase.cards))
        )
        .scalars()
        .all()
    )

    # Count stats
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    total_story_points = 0
    total = 0

    for phase in phases:
        for card in phase.cards:
            total += 1
            by_type[card.type] = by_type.get(card.type, 0) + 1
            by_status[card.status] = by_status.get(card.status, 0) + 1
            if card.priority:
                by_priority[card.priority] = by_priority.get(card.priority, 0) + 1
            if card.story_points:
                total_story_points += card.story_points

    return CardsStatsResponse(
        total=total,
        by_type=by_type,
        by_status=by_status,
        by_priority=by_priority,
        total_story_points=total_story_points,
    )


@router.get(
    "/api/projects/{slug}/cards/{card_id}",
    response_model=CardView,
)
def get_card(
    slug: str,
    card_id: UUID,
    session: Session = Depends(get_session),
) -> CardView:
    """Get a single card."""
    project = _get_project_by_slug(session, slug)

    # Get card with phase check
    card = session.execute(
        select(Card)
        .join(Phase)
        .where(Card.id == card_id, Phase.project_id == project.id)
        .options(
            selectinload(Card.skill_links).selectinload(CardSkill.skill),
            selectinload(Card.deps_out).selectinload(CardDep.depends_on_card),
            selectinload(Card.inputs),
        )
    ).scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    return _card_to_view(card)


@router.patch(
    "/api/projects/{slug}/cards/{card_id}",
    response_model=CardView,
)
def update_card(
    slug: str,
    card_id: UUID,
    request: UpdateCardRequest,
    session: Session = Depends(get_session),
) -> CardView:
    """Update a card."""
    project = _get_project_by_slug(session, slug)

    card = session.execute(
        select(Card)
        .join(Phase)
        .where(Card.id == card_id, Phase.project_id == project.id)
        .options(
            selectinload(Card.skill_links).selectinload(CardSkill.skill),
            selectinload(Card.deps_out).selectinload(CardDep.depends_on_card),
            selectinload(Card.inputs),
        )
    ).scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Update fields
    if request.title is not None:
        card.title = request.title
    if request.context_md is not None:
        card.context_md = request.context_md
    if request.task_md is not None:
        card.task_md = request.task_md
    if request.outputs_md is not None:
        card.outputs_md = request.outputs_md
    if request.acceptance_criteria_md is not None:
        card.acceptance_criteria_md = request.acceptance_criteria_md
    if request.human_gate is not None:
        card.human_gate = request.human_gate
    if request.human_gate_checklist_md is not None:
        card.human_gate_checklist_md = request.human_gate_checklist_md
    if request.story_points is not None:
        card.story_points = request.story_points
    if request.priority is not None:
        card.priority = request.priority.value
    if request.status is not None:
        card.status = request.status.value

    session.commit()
    session.refresh(card)

    return _card_to_view(card)


# ---------------------------------------------------------------------------
# Backlog proposal (LLM)
# ---------------------------------------------------------------------------


@router.post(
    "/api/projects/{slug}/backlog/propose",
    response_model=ProposeBacklogResponse,
)
def propose_backlog(
    slug: str,
    session: Session = Depends(get_session),
) -> ProposeBacklogResponse:
    """Propose a project backlog using LLM.

    Gathers project context and skills, then calls the LLM to generate
    a phase-based backlog structure with cards.
    """
    project = _get_project_by_slug(session, slug)

    # Load project context
    context_service = ProjectContextService()
    context = context_service.load_project_context(slug)

    if not context:
        raise HTTPException(
            status_code=400,
            detail="Failed to load project context. Ensure project has objective and Q&A answers.",
        )

    # Get project skills
    skills = (
        session.execute(
            select(Skill)
            .where(Skill.project_id == project.id)
            .options(selectinload(Skill.resources))
            .order_by(Skill.order_no)
        )
        .scalars()
        .all()
    )

    if not skills:
        raise HTTPException(
            status_code=400,
            detail="No skills found. Please create or propose skills first.",
        )

    skill_views = [_skill_to_view(s) for s in skills]

    # Get template family
    template_family = get_family(project.card_template)

    # Render context string
    context_str = context_service.render_context_string(context)

    # Create prompt
    prompt = ProposeBacklogPrompt.create(context_str, skill_views, template_family)

    # Create LLM service
    factory = LlmServiceFactory()
    llm_service = factory.create_for_project(slug, session)

    # Run the prompt
    result = llm_service.run(prompt, kind=LlmRunKind.PROPOSE_BACKLOG)

    if not result.parsed:
        raise HTTPException(
            status_code=500,
            detail="LLM failed to generate valid backlog. Check LLM run logs.",
        )

    proposed: ProposedBacklog = result.parsed

    # Create phases and cards in database
    created_phases = []
    skill_map = {s.slug: s for s in skills}
    card_map: dict[str, Card] = {}  # code -> card for dependency resolution

    for phase_idx, prop_phase in enumerate(proposed.phases):
        phase = Phase(
            project_id=project.id,
            code=prop_phase.code,
            name=prop_phase.name,
            description_md=prop_phase.description,
            order_no=phase_idx,
        )
        session.add(phase)
        session.flush()  # Get phase ID

        for card_idx, prop_card in enumerate(prop_phase.cards):
            # If human_gate is True, generate a placeholder checklist
            # (will be properly filled when card is drafted via DraftCard)
            human_gate = prop_card.human_gate
            human_gate_checklist = None
            if human_gate:
                human_gate_checklist = f"- [ ] Review and approve: {prop_card.title}"
            
            card = Card(
                phase_id=phase.id,
                code=prop_card.code,
                title=prop_card.title,
                type=prop_card.type.value,
                story_points=prop_card.story_points,
                human_gate=human_gate,
                human_gate_checklist_md=human_gate_checklist,
                context_md=prop_card.short_scope_summary,
                order_no=card_idx,
            )
            session.add(card)
            session.flush()  # Get card ID

            card_map[prop_card.code] = card

            # Link skills
            for pos, skill_slug in enumerate(prop_card.skill_slugs):
                if skill_slug in skill_map:
                    skill_link = CardSkill(
                        card_id=card.id,
                        skill_id=skill_map[skill_slug].id,
                        position=pos,
                    )
                    session.add(skill_link)

        created_phases.append(phase)

    # Create dependencies (second pass after all cards exist)
    for prop_phase in proposed.phases:
        for prop_card in prop_phase.cards:
            if prop_card.code not in card_map:
                continue
            card = card_map[prop_card.code]

            for dep_code in prop_card.depends_on_codes:
                if dep_code in card_map:
                    dep = CardDep(
                        card_id=card.id,
                        depends_on_card_id=card_map[dep_code].id,
                        relation=CardDepRelation.DEPENDS_ON.value,
                    )
                    session.add(dep)

            for par_code in prop_card.parallel_with_codes:
                if par_code in card_map:
                    dep = CardDep(
                        card_id=card.id,
                        depends_on_card_id=card_map[par_code].id,
                        relation=CardDepRelation.PARALLEL_WITH.value,
                    )
                    session.add(dep)

    # Get LLM run ID
    from app.domain.llm import LlmRun

    llm_run = session.execute(
        select(LlmRun)
        .where(LlmRun.project_id == project.id)
        .order_by(LlmRun.created_at.desc())
        .limit(1)
    ).scalar_one()

    session.commit()

    # Refresh phases to get all relationships
    phase_views = []
    for phase in created_phases:
        session.refresh(phase)
        # Re-query with all relationships
        full_phase = session.execute(
            select(Phase)
            .where(Phase.id == phase.id)
            .options(
                selectinload(Phase.cards)
                .selectinload(Card.skill_links)
                .selectinload(CardSkill.skill),
                selectinload(Phase.cards)
                .selectinload(Card.deps_out)
                .selectinload(CardDep.depends_on_card),
                selectinload(Phase.cards).selectinload(Card.inputs),
            )
        ).scalar_one()
        phase_views.append(_phase_to_view(full_phase))

    return ProposeBacklogResponse(
        phases=phase_views,
        rationale_md=proposed.rationale_md,
        critical_path_codes=proposed.critical_path_codes,
        llm_run_id=llm_run.id,
    )


@router.post(
    "/api/projects/{slug}/backlog/bulk",
    response_model=BulkCreateBacklogResponse,
    status_code=201,
)
def bulk_create_backlog(
    slug: str,
    request: BulkCreateBacklogRequest,
    session: Session = Depends(get_session),
) -> BulkCreateBacklogResponse:
    """Bulk create phases and cards from proposals.

    This is useful for accepting proposed backlog without calling LLM again.
    """
    project = _get_project_by_slug(session, slug)

    # Get skill map
    skills = session.execute(select(Skill).where(Skill.project_id == project.id)).scalars().all()
    skill_map = {s.slug: s for s in skills}

    created_phases: list[Phase] = []
    card_map: dict[str, Card] = {}
    total_cards = 0

    for phase_idx, phase_req in enumerate(request.phases):
        phase = Phase(
            project_id=project.id,
            code=phase_req.code,
            name=phase_req.name,
            description_md=phase_req.description,
            order_no=phase_idx,
        )
        session.add(phase)
        session.flush()

        for card_idx, card_req in enumerate(phase_req.cards):
            card = Card(
                phase_id=phase.id,
                code=card_req.code,
                title=card_req.title,
                type=card_req.type.value,
                story_points=card_req.story_points,
                human_gate=card_req.human_gate,
                context_md=card_req.short_scope_summary,
                order_no=card_idx,
            )
            session.add(card)
            session.flush()

            card_map[card_req.code] = card
            total_cards += 1

            # Link skills
            for pos, skill_slug in enumerate(card_req.skill_slugs):
                if skill_slug in skill_map:
                    skill_link = CardSkill(
                        card_id=card.id,
                        skill_id=skill_map[skill_slug].id,
                        position=pos,
                    )
                    session.add(skill_link)

        created_phases.append(phase)

    # Create dependencies
    for phase_req in request.phases:
        for card_req in phase_req.cards:
            if card_req.code not in card_map:
                continue
            card = card_map[card_req.code]

            for dep_code in card_req.depends_on_codes:
                if dep_code in card_map:
                    dep = CardDep(
                        card_id=card.id,
                        depends_on_card_id=card_map[dep_code].id,
                        relation=CardDepRelation.DEPENDS_ON.value,
                    )
                    session.add(dep)

            for par_code in card_req.parallel_with_codes:
                if par_code in card_map:
                    dep = CardDep(
                        card_id=card.id,
                        depends_on_card_id=card_map[par_code].id,
                        relation=CardDepRelation.PARALLEL_WITH.value,
                    )
                    session.add(dep)

    session.commit()

    # Refresh and build views
    phase_views = []
    for phase in created_phases:
        full_phase = session.execute(
            select(Phase)
            .where(Phase.id == phase.id)
            .options(
                selectinload(Phase.cards)
                .selectinload(Card.skill_links)
                .selectinload(CardSkill.skill),
                selectinload(Phase.cards)
                .selectinload(Card.deps_out)
                .selectinload(CardDep.depends_on_card),
                selectinload(Phase.cards).selectinload(Card.inputs),
            )
        ).scalar_one()
        phase_views.append(_phase_to_view(full_phase))

    return BulkCreateBacklogResponse(
        phases_created=len(created_phases),
        cards_created=total_cards,
        phases=phase_views,
    )


# ---------------------------------------------------------------------------
# Card Section Endpoints
# ---------------------------------------------------------------------------


VALID_SECTIONS = {"context", "task", "outputs", "acceptance_criteria", "human_gate_checklist"}


class UpdateSectionRequest(BaseModel):
    """Request to update a single card section."""

    content: str


class RegenerateSectionResponse(BaseModel):
    """Response from section regeneration."""

    section: str
    content: str
    llm_run_id: UUID


class DraftCardResponse(BaseModel):
    """Response from card drafting."""

    card: CardView
    llm_run_id: UUID


class UpdateDependenciesRequest(BaseModel):
    """Request to update card dependencies."""

    depends_on_codes: list[str] = Field(default_factory=list)
    parallel_with_codes: list[str] = Field(default_factory=list)


class CreateCardInputRequest(BaseModel):
    """Request to create a card input."""

    kind: CardInputKind
    path: str
    label: str | None = None
    order_no: int = 0


class UpdateCardInputRequest(BaseModel):
    """Request to update a card input."""

    kind: CardInputKind | None = None
    path: str | None = None
    label: str | None = None
    order_no: int | None = None


@router.patch(
    "/api/projects/{slug}/cards/{card_id}/sections/{section}",
    response_model=CardView,
)
def update_card_section(
    slug: str,
    card_id: UUID,
    section: str,
    request: UpdateSectionRequest,
    session: Session = Depends(get_session),
) -> CardView:
    """Update a single section of a card."""
    if section not in VALID_SECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid section. Must be one of: {', '.join(VALID_SECTIONS)}",
        )

    project = _get_project_by_slug(session, slug)

    card = session.execute(
        select(Card)
        .join(Phase)
        .where(Card.id == card_id, Phase.project_id == project.id)
        .options(
            selectinload(Card.skill_links).selectinload(CardSkill.skill),
            selectinload(Card.deps_out).selectinload(CardDep.depends_on_card),
            selectinload(Card.inputs),
        )
    ).scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Update the specific section
    setattr(card, f"{section}_md", request.content)

    session.commit()
    session.refresh(card)

    return _card_to_view(card)


@router.post(
    "/api/projects/{slug}/cards/{card_id}/sections/{section}/regenerate",
    response_model=RegenerateSectionResponse,
)
def regenerate_card_section(
    slug: str,
    card_id: UUID,
    section: str,
    session: Session = Depends(get_session),
) -> RegenerateSectionResponse:
    """Regenerate a single section of a card using LLM.

    This preserves other sections and only updates the specified section.
    """
    if section not in VALID_SECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid section. Must be one of: {', '.join(VALID_SECTIONS)}",
        )

    project = _get_project_by_slug(session, slug)

    card = session.execute(
        select(Card)
        .join(Phase)
        .where(Card.id == card_id, Phase.project_id == project.id)
        .options(
            selectinload(Card.skill_links).selectinload(CardSkill.skill),
            selectinload(Card.phase),
        )
    ).scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Load project context
    context_service = ProjectContextService()
    context = context_service.load_project_context(slug)

    if not context:
        raise HTTPException(
            status_code=400,
            detail="Failed to load project context.",
        )

    # Get skills for this card
    skill_views = [_skill_to_view(link.skill) for link in card.skill_links]

    # Get template family
    template_family = get_family(project.card_template)

    # Build context for the prompt - simplified single-section regeneration
    from app.families._base import CardDraftContext
    from app.schemas.views import ProjectView
    from datetime import datetime, UTC
    from decimal import Decimal

    # Create project view
    project_view = ProjectView(
        id=project.id,
        tenant_id=project.tenant_id,
        owner_user_id=project.owner_user_id,
        slug=project.slug,
        name=project.name,
        objective=project.objective or "",
        card_code_prefix=project.card_code_prefix,
        card_template=project.card_template,
        grouping=project.grouping,
        status=project.status,
        llm_provider=project.llm_provider,
        llm_model=project.llm_model,
        llm_temperature=Decimal(str(project.llm_temperature)) if project.llm_temperature else Decimal("0.7"),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )

    # Create card view
    card_view = _card_to_view(card)

    # Create phase view
    phase_view = _phase_to_view(card.phase)

    # Build draft context
    draft_context = CardDraftContext(
        project=project_view,
        project_context=context_service.render_context_string(context),
        phase=phase_view,
        card=card_view,
        skills_used=skill_views,
        upstream_cards=[],
        sibling_cards_in_phase=[],
    )

    # Create LLM service
    factory = LlmServiceFactory()
    llm_service = factory.create_for_project(slug, session)

    # Create a simple prompt for single section regeneration
    from app.llm.base import ChatPrompt

    section_prompt = f"""You are regenerating ONLY the {section.replace('_', ' ')} section of a project card.

Card: {card.code} - {card.title}
Type: {card.type}
Phase: {card.phase.name}

Current card content:
- Context: {card.context_md or '(empty)'}
- Task: {card.task_md or '(empty)'}
- Outputs: {card.outputs_md or '(empty)'}
- Acceptance Criteria: {card.acceptance_criteria_md or '(empty)'}

Skills assigned: {', '.join(s.slug for s in skill_views) or 'None'}

Project context:
{draft_context.project_context}

Generate ONLY the {section.replace('_', ' ')} section content in markdown format.
Be concise but thorough. Follow the existing style and tone of other sections.
"""

    from pydantic import BaseModel

    class SectionContent(BaseModel):
        content: str

    prompt = ChatPrompt[SectionContent](
        system="You are an expert technical writer generating project card sections.",
        user=section_prompt,
        response_schema=SectionContent,
    )

    result = llm_service.run(prompt, kind=LlmRunKind.DRAFT_CARD)

    if not result.parsed:
        raise HTTPException(
            status_code=500,
            detail="LLM failed to generate section content.",
        )

    # Update the section
    setattr(card, f"{section}_md", result.parsed.content)

    # Get LLM run ID
    from app.domain.llm import LlmRun

    llm_run = session.execute(
        select(LlmRun)
        .where(LlmRun.project_id == project.id)
        .order_by(LlmRun.created_at.desc())
    ).scalar_one()

    session.commit()

    return RegenerateSectionResponse(
        section=section,
        content=result.parsed.content,
        llm_run_id=llm_run.id,
    )


@router.post(
    "/api/projects/{slug}/cards/{card_id}/draft",
    response_model=DraftCardResponse,
)
def draft_card(
    slug: str,
    card_id: UUID,
    session: Session = Depends(get_session),
) -> DraftCardResponse:
    """Draft all sections of a card using LLM.

    This regenerates context, task, outputs, and acceptance_criteria sections.
    If human_gate is enabled, also generates the checklist.
    """
    project = _get_project_by_slug(session, slug)

    card = session.execute(
        select(Card)
        .join(Phase)
        .where(Card.id == card_id, Phase.project_id == project.id)
        .options(
            selectinload(Card.skill_links).selectinload(CardSkill.skill),
            selectinload(Card.phase).selectinload(Phase.cards),
            selectinload(Card.deps_out).selectinload(CardDep.depends_on_card),
            selectinload(Card.inputs),
        )
    ).scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Load project context
    context_service = ProjectContextService()
    context = context_service.load_project_context(slug)

    if not context:
        raise HTTPException(
            status_code=400,
            detail="Failed to load project context.",
        )

    # Get skills for this card
    skill_views = [_skill_to_view(link.skill) for link in card.skill_links]

    # Get template family
    template_family = get_family(project.card_template)

    # Build context
    from app.families._base import CardDraftContext
    from app.schemas.views import ProjectView
    from datetime import datetime, UTC
    from decimal import Decimal

    project_view = ProjectView(
        id=project.id,
        tenant_id=project.tenant_id,
        owner_user_id=project.owner_user_id,
        slug=project.slug,
        name=project.name,
        objective=project.objective or "",
        card_code_prefix=project.card_code_prefix,
        card_template=project.card_template,
        grouping=project.grouping,
        status=project.status,
        llm_provider=project.llm_provider,
        llm_model=project.llm_model,
        llm_temperature=Decimal(str(project.llm_temperature)) if project.llm_temperature else Decimal("0.7"),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )

    card_view = _card_to_view(card)
    phase_view = _phase_to_view(card.phase)

    # Get upstream cards (dependencies)
    upstream_cards = [_card_to_view(dep.depends_on_card) for dep in card.deps_out]

    # Get sibling cards in phase
    sibling_cards = [_card_to_view(c) for c in card.phase.cards if c.id != card.id]

    draft_context = CardDraftContext(
        project=project_view,
        project_context=context_service.render_context_string(context),
        phase=phase_view,
        card=card_view,
        skills_used=skill_views,
        upstream_cards=upstream_cards,
        sibling_cards_in_phase=sibling_cards,
    )

    # Create prompt using template family
    from app.prompts import DraftCardPrompt

    prompt = DraftCardPrompt.create(draft_context, template_family)

    # Create LLM service
    factory = LlmServiceFactory()
    llm_service = factory.create_for_project(slug, session)

    # Run the prompt
    result = llm_service.run(prompt, kind=LlmRunKind.DRAFT_CARD)

    if not result.parsed:
        raise HTTPException(
            status_code=500,
            detail="LLM failed to draft card. Check LLM run logs.",
        )

    # Update card sections
    card.context_md = result.parsed.context_md
    card.task_md = result.parsed.task_md
    card.outputs_md = result.parsed.outputs_md
    card.acceptance_criteria_md = result.parsed.acceptance_criteria_md

    if card.human_gate and result.parsed.human_gate_checklist_md:
        card.human_gate_checklist_md = result.parsed.human_gate_checklist_md

    # Update inputs if provided
    if result.parsed.inputs:
        # Delete existing inputs
        for existing_input in card.inputs:
            session.delete(existing_input)

        # Create new inputs
        for i, inp in enumerate(result.parsed.inputs):
            new_input = CardInput(
                card_id=card.id,
                kind=inp.kind.value,
                path=inp.path,
                label=inp.label,
                order_no=i,
            )
            session.add(new_input)

    # Get LLM run ID from the result (set by LlmService.run())
    llm_run_id = result.run_id

    session.commit()

    # Refresh card with all relationships
    card = session.execute(
        select(Card)
        .where(Card.id == card_id)
        .options(
            selectinload(Card.skill_links).selectinload(CardSkill.skill),
            selectinload(Card.deps_out).selectinload(CardDep.depends_on_card),
            selectinload(Card.inputs),
        )
    ).scalar_one()

    return DraftCardResponse(
        card=_card_to_view(card),
        llm_run_id=llm_run_id,
    )


# ---------------------------------------------------------------------------
# Card Dependencies
# ---------------------------------------------------------------------------


@router.put(
    "/api/projects/{slug}/cards/{card_id}/dependencies",
    response_model=CardView,
)
def update_card_dependencies(
    slug: str,
    card_id: UUID,
    request: UpdateDependenciesRequest,
    session: Session = Depends(get_session),
) -> CardView:
    """Update card dependencies (depends_on and parallel_with)."""
    project = _get_project_by_slug(session, slug)

    card = session.execute(
        select(Card)
        .join(Phase)
        .where(Card.id == card_id, Phase.project_id == project.id)
        .options(
            selectinload(Card.deps_out),
        )
    ).scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Get all cards in project for validation
    all_cards = (
        session.execute(
            select(Card)
            .join(Phase)
            .where(Phase.project_id == project.id)
        )
        .scalars()
        .all()
    )
    card_by_code = {c.code: c for c in all_cards}

    # Delete existing dependencies
    for dep in card.deps_out:
        session.delete(dep)

    # Add new depends_on dependencies
    for dep_code in request.depends_on_codes:
        if dep_code not in card_by_code:
            continue
        if dep_code == card.code:
            continue  # No self-deps

        dep = CardDep(
            card_id=card.id,
            depends_on_card_id=card_by_code[dep_code].id,
            relation=CardDepRelation.DEPENDS_ON.value,
        )
        session.add(dep)

    # Add new parallel_with dependencies
    for par_code in request.parallel_with_codes:
        if par_code not in card_by_code:
            continue
        if par_code == card.code:
            continue

        dep = CardDep(
            card_id=card.id,
            depends_on_card_id=card_by_code[par_code].id,
            relation=CardDepRelation.PARALLEL_WITH.value,
        )
        session.add(dep)

    session.commit()

    # Refresh with all relationships
    card = session.execute(
        select(Card)
        .where(Card.id == card_id)
        .options(
            selectinload(Card.skill_links).selectinload(CardSkill.skill),
            selectinload(Card.deps_out).selectinload(CardDep.depends_on_card),
            selectinload(Card.inputs),
        )
    ).scalar_one()

    return _card_to_view(card)


# ---------------------------------------------------------------------------
# Card Inputs CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/api/projects/{slug}/cards/{card_id}/inputs",
    response_model=list[CardInputView],
)
def list_card_inputs(
    slug: str,
    card_id: UUID,
    session: Session = Depends(get_session),
) -> list[CardInputView]:
    """List all inputs for a card."""
    project = _get_project_by_slug(session, slug)

    card = session.execute(
        select(Card)
        .join(Phase)
        .where(Card.id == card_id, Phase.project_id == project.id)
        .options(selectinload(Card.inputs))
    ).scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    return [
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


@router.post(
    "/api/projects/{slug}/cards/{card_id}/inputs",
    response_model=CardInputView,
    status_code=201,
)
def create_card_input(
    slug: str,
    card_id: UUID,
    request: CreateCardInputRequest,
    session: Session = Depends(get_session),
) -> CardInputView:
    """Create a new card input."""
    project = _get_project_by_slug(session, slug)

    card = session.execute(
        select(Card)
        .join(Phase)
        .where(Card.id == card_id, Phase.project_id == project.id)
    ).scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    inp = CardInput(
        card_id=card.id,
        kind=request.kind.value,
        path=request.path,
        label=request.label,
        order_no=request.order_no,
    )
    session.add(inp)
    session.commit()
    session.refresh(inp)

    return CardInputView(
        id=inp.id,
        card_id=inp.card_id,
        kind=CardInputKind(inp.kind),
        path=inp.path,
        label=inp.label,
        order_no=inp.order_no,
    )


@router.patch(
    "/api/projects/{slug}/cards/{card_id}/inputs/{input_id}",
    response_model=CardInputView,
)
def update_card_input(
    slug: str,
    card_id: UUID,
    input_id: UUID,
    request: UpdateCardInputRequest,
    session: Session = Depends(get_session),
) -> CardInputView:
    """Update a card input."""
    project = _get_project_by_slug(session, slug)

    inp = session.execute(
        select(CardInput)
        .join(Card)
        .join(Phase)
        .where(
            CardInput.id == input_id,
            CardInput.card_id == card_id,
            Phase.project_id == project.id,
        )
    ).scalar_one_or_none()

    if not inp:
        raise HTTPException(status_code=404, detail="Input not found")

    if request.kind is not None:
        inp.kind = request.kind.value
    if request.path is not None:
        inp.path = request.path
    if request.label is not None:
        inp.label = request.label
    if request.order_no is not None:
        inp.order_no = request.order_no

    session.commit()
    session.refresh(inp)

    return CardInputView(
        id=inp.id,
        card_id=inp.card_id,
        kind=CardInputKind(inp.kind),
        path=inp.path,
        label=inp.label,
        order_no=inp.order_no,
    )


@router.delete(
    "/api/projects/{slug}/cards/{card_id}/inputs/{input_id}",
    status_code=204,
)
def delete_card_input(
    slug: str,
    card_id: UUID,
    input_id: UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete a card input."""
    project = _get_project_by_slug(session, slug)

    inp = session.execute(
        select(CardInput)
        .join(Card)
        .join(Phase)
        .where(
            CardInput.id == input_id,
            CardInput.card_id == card_id,
            Phase.project_id == project.id,
        )
    ).scalar_one_or_none()

    if not inp:
        raise HTTPException(status_code=404, detail="Input not found")

    session.delete(inp)
    session.commit()


# ---------------------------------------------------------------------------
# DAG View
# ---------------------------------------------------------------------------


class DagNodeView(BaseModel):
    """Node in the DAG view."""

    id: str
    code: str
    title: str
    type: CardType
    status: CardStatus
    phase_code: str
    phase_name: str
    story_points: int | None = None


class DagEdgeView(BaseModel):
    """Edge in the DAG view."""

    id: str
    source: str
    target: str
    relation: CardDepRelation


class DagResponse(BaseModel):
    """Response for DAG view."""

    nodes: list[DagNodeView]
    edges: list[DagEdgeView]


@router.get(
    "/api/projects/{slug}/dag",
    response_model=DagResponse,
)
def get_project_dag(
    slug: str,
    session: Session = Depends(get_session),
) -> DagResponse:
    """Get the project DAG (Directed Acyclic Graph) for visualization.

    Returns all cards as nodes and their dependencies as edges.
    """
    project = _get_project_by_slug(session, slug)

    # Get all cards with their phases and dependencies
    cards = (
        session.execute(
            select(Card)
            .join(Phase)
            .where(Phase.project_id == project.id)
            .options(
                selectinload(Card.phase),
                selectinload(Card.deps_out).selectinload(CardDep.depends_on_card),
            )
            .order_by(Phase.order_no, Card.order_no)
        )
        .scalars()
        .all()
    )

    # Build nodes
    nodes: list[DagNodeView] = []
    for card in cards:
        nodes.append(
            DagNodeView(
                id=str(card.id),
                code=card.code,
                title=card.title,
                type=CardType(card.type),
                status=CardStatus(card.status),
                phase_code=card.phase.code,
                phase_name=card.phase.name,
                story_points=card.story_points,
            )
        )

    # Build edges
    edges: list[DagEdgeView] = []
    for card in cards:
        for dep in card.deps_out:
            edges.append(
                DagEdgeView(
                    id=f"{card.id}-{dep.depends_on_card_id}",
                    source=str(card.id),
                    target=str(dep.depends_on_card_id),
                    relation=CardDepRelation(dep.relation),
                )
            )

    return DagResponse(nodes=nodes, edges=edges)
