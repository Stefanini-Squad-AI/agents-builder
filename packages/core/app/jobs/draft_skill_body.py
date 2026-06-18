"""`draft_skill_body` Dramatiq actor.

Drafts a single skill's body and resources via LLM. This is used by the
`/skills/draft-all` endpoint to process skills asynchronously in the
background worker.

State: skill.body_md empty → being drafted → filled (with resources).
"""

from __future__ import annotations

import uuid

import dramatiq
import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import session_scope
from app.domain import register_models
from app.domain.projects import Project
from app.domain.skills import Skill, SkillResource
from app.enums import LlmRunKind, SkillDraftStatus, SkillResourceLanguage
from app.prompts.draft_skillbody import DraftSkillBodyPrompt
from app.schemas.views import SkillResourceView, SkillView
from app.services.llm_service_factory import LlmServiceFactory
from app.services.project_context_service import ProjectContextService

register_models()

log = structlog.get_logger(__name__)


def _skill_to_view(skill: Skill) -> SkillView:
    """Convert Skill ORM object to SkillView."""
    from app.enums import SkillKind

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


@dramatiq.actor(queue_name="default", max_retries=0, time_limit=180_000)
def draft_skill_body(skill_id: str, include_resources: bool = True) -> None:
    """Draft a skill's body (and optionally resources) via LLM.

    Time-limited to 180s (3 min) to allow for LLM response time.
    """
    sid = uuid.UUID(skill_id)
    log.info("draft_skill_body_start", skill_id=str(sid))

    # Step 1: Load skill and project info, mark as drafting
    with session_scope() as session:
        skill = session.execute(
            select(Skill)
            .where(Skill.id == sid)
            .options(selectinload(Skill.resources))
        ).scalar_one_or_none()

        if skill is None:
            log.warning("draft_skill_body_not_found", skill_id=str(sid))
            return

        # Skip if already has body content
        if skill.body_md and skill.body_md.strip():
            log.info("draft_skill_body_already_drafted", skill_id=str(sid))
            skill.draft_status = SkillDraftStatus.SUCCESS.value
            return

        # Mark as drafting
        skill.draft_status = SkillDraftStatus.DRAFTING.value
        skill.draft_error = None

        project = session.execute(
            select(Project).where(Project.id == skill.project_id)
        ).scalar_one()
        project_slug = project.slug
        project_id = project.id
        skill_view = _skill_to_view(skill)

    # Step 1b: Load open gaps (entity-backed, not the legacy JSON column).
    # Drafts only see gaps still waiting for resolution.
    from app.services.gap_service import GapService

    with session_scope() as session:
        open_gaps = GapService().list_open(session, project_id)
        identified_gaps = [g.title for g in open_gaps]

    # Step 2: Load project context
    with session_scope() as session:
        context_service = ProjectContextService(session)
        context = context_service.load_project_context(project_slug)

    if not context:
        log.error("draft_skill_body_no_context", skill_id=str(sid), project=project_slug)
        with session_scope() as session:
            skill = session.get(Skill, sid)
            if skill:
                skill.draft_status = SkillDraftStatus.ERROR.value
                skill.draft_error = "Failed to load project context"
        return

    # Step 3: Load sibling skills
    with session_scope() as session:
        sibling_skills = (
            session.execute(
                select(Skill)
                .where(Skill.project_id == project_id, Skill.id != sid)
                .options(selectinload(Skill.resources))
            )
            .scalars()
            .all()
        )
        sibling_views = [_skill_to_view(s) for s in sibling_skills]

    # Step 4: Create prompt and run LLM
    prompt = DraftSkillBodyPrompt.create(
        skill_view, context, sibling_views, identified_gaps=identified_gaps
    )
    llm_run_id: uuid.UUID | None = None

    with session_scope() as session:
        factory = LlmServiceFactory()
        llm_service = factory.create_for_project(project_slug, session)

        try:
            result = llm_service.run(prompt, kind=LlmRunKind.DRAFT_SKILL_BODY)
            llm_run_id = result.run_id
        except Exception as e:
            log.exception("draft_skill_body_llm_error", skill_id=str(sid))
            with session_scope() as err_session:
                skill = err_session.get(Skill, sid)
                if skill:
                    skill.draft_status = SkillDraftStatus.ERROR.value
                    skill.draft_error = f"LLM provider error: {str(e)[:500]}"
            return

        if not result.parsed:
            log.error("draft_skill_body_parse_failed", skill_id=str(sid))
            with session_scope() as err_session:
                skill = err_session.get(Skill, sid)
                if skill:
                    skill.draft_status = SkillDraftStatus.ERROR.value
                    skill.draft_error = f"Failed to parse LLM response: {result.raw_text[:500] if result.raw_text else 'empty response'}"
                    skill.last_llm_run_id = llm_run_id
            return

    # Step 5: Update skill with drafted content
    with session_scope() as session:
        skill = session.execute(
            select(Skill)
            .where(Skill.id == sid)
            .options(selectinload(Skill.resources))
        ).scalar_one()

        skill.body_md = result.parsed.body_md
        skill.draft_status = SkillDraftStatus.SUCCESS.value
        skill.draft_error = None
        skill.last_llm_run_id = llm_run_id

        resources_created = 0
        if include_resources and result.parsed.resources:
            # Delete existing resources
            for existing in skill.resources:
                session.delete(existing)

            # Create new resources
            for i, res in enumerate(result.parsed.resources):
                new_resource = SkillResource(
                    skill_id=skill.id,
                    filename=res.filename,
                    content=res.content,
                    language=res.language.value,
                    order_no=i,
                )
                session.add(new_resource)
                resources_created += 1

        # Auto-close any open gap the model explicitly claims to have
        # addressed. We match by normalised title against open gaps for this
        # project. Anything the model invented (not in the list we sent it)
        # is silently ignored.
        gaps_closed = 0
        if result.parsed.addressed_gaps:
            from app.services.gap_service import GapService, _title_key

            gap_service = GapService()
            open_gaps = gap_service.list_open(session, skill.project_id)
            by_key = {g.title_key: g for g in open_gaps}
            for claim in result.parsed.addressed_gaps:
                key = _title_key(claim)
                gap = by_key.get(key)
                if gap is None:
                    continue
                gap_service.mark_addressed_by_skill(
                    session,
                    gap,
                    skill_id=skill.id,
                    rationale="Auto-closed by DraftSkillBody (model claim).",
                )
                gaps_closed += 1

    log.info(
        "draft_skill_body_done",
        skill_id=str(sid),
        body_len=len(result.parsed.body_md or ""),
        resources_created=resources_created,
        gaps_closed=gaps_closed,
    )
