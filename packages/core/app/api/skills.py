"""Skills API — CRUD + LLM proposal for project skills.

Endpoints:
- GET    /api/projects/{slug}/skills                  list all skills for project
- GET    /api/projects/{slug}/skills/stats            skill statistics
- GET    /api/projects/{slug}/skills/{skill_slug}     get single skill with resources
- POST   /api/projects/{slug}/skills                  create skill
- PATCH  /api/projects/{slug}/skills/{skill_slug}     update skill
- DELETE /api/projects/{slug}/skills/{skill_slug}     delete skill
- POST   /api/projects/{slug}/skills/propose          propose skills via LLM
- POST   /api/projects/{slug}/skills/bulk             bulk create skills from proposals
- POST   /api/projects/{slug}/skills/{skill_slug}/draft   regenerate body via LLM
- GET    /api/projects/{slug}/skills/{skill_slug}/resources       list resources
- POST   /api/projects/{slug}/skills/{skill_slug}/resources       create resource
- PATCH  /api/projects/{slug}/skills/{skill_slug}/resources/{id}  update resource
- DELETE /api/projects/{slug}/skills/{skill_slug}/resources/{id}  delete resource
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.domain.projects import Project
from app.domain.skills import Skill, SkillResource
from app.enums import LlmRunKind, SkillDraftStatus, SkillKind, SkillResourceLanguage
from app.llm.service import LLMService
from app.prompts.draft_skillbody import DraftSkillBodyPrompt
from app.prompts.propose_skillset import ProposeSkillSetPrompt
from app.schemas.llm_io import DraftedSkillBody, ProposedSkill, ProposedSkillSet
from app.schemas.views import SkillResourceView, SkillView
from app.services.llm_service_factory import LlmServiceFactory
from app.services.project_context_service import ProjectContextService

router = APIRouter(tags=["skills"])


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class CreateSkillRequest(BaseModel):
    """Request to create a new skill."""

    slug: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)
    kind: SkillKind
    body_md: str = ""
    order_no: int = 0


class UpdateSkillRequest(BaseModel):
    """Request to update an existing skill."""

    name: str | None = None
    description: str | None = None
    kind: SkillKind | None = None
    body_md: str | None = None
    order_no: int | None = None


class CreateResourceRequest(BaseModel):
    """Request to create a skill resource."""

    filename: str
    content: str
    language: SkillResourceLanguage = SkillResourceLanguage.MARKDOWN
    order_no: int = 0


class BulkCreateSkillRequest(BaseModel):
    """Single skill in bulk create request."""

    slug: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)
    kind: SkillKind
    rationale: str = ""
    body_md: str = ""


class BulkCreateSkillsRequest(BaseModel):
    """Request to bulk create skills from proposals."""

    skills: list[BulkCreateSkillRequest] = Field(..., min_length=1, max_length=20)


class SkillStatsResponse(BaseModel):
    """Skill statistics response."""

    total_skills: int
    by_kind: dict[str, int]
    with_content: int
    with_resources: int
    completion_percentage: float
    by_draft_status: dict[str, int]  # {"none": 0, "pending": 3, "drafting": 1, "success": 8, "error": 0}


class ProposeSkillsResponse(BaseModel):
    """Response from skill proposal."""

    skills: list[ProposedSkill]
    coverage_notes: str
    gaps: list[str]
    llm_run_id: UUID


class BulkCreateResponse(BaseModel):
    """Response from bulk skill creation."""

    created: int
    skills: list[SkillView]


class DraftSkillBodyRequest(BaseModel):
    """Request to regenerate skill body via LLM."""

    include_resources: bool = False  # If True, also regenerate resources


class DraftSkillBodyResponse(BaseModel):
    """Response from skill body drafting."""

    body_md: str
    resources_created: int
    sibling_skills_referenced: list[str]
    llm_run_id: UUID


class DraftAllSkillsRequest(BaseModel):
    """Request to draft all undrafted skills."""

    include_resources: bool = True  # If True, also generate resources
    force: bool = False  # If True, re-draft skills that already have content


class DraftAllSkillsResponse(BaseModel):
    """Response from drafting all skills."""

    queued: int
    skill_slugs: list[str]


class UpdateResourceRequest(BaseModel):
    """Request to update a skill resource."""

    filename: str | None = None
    content: str | None = None
    language: SkillResourceLanguage | None = None
    order_no: int | None = None


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def _get_project_by_slug(session: Session, slug: str) -> Project:
    """Get project by slug or raise 404."""
    project = session.execute(
        select(Project).where(Project.slug == slug)
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return project


def _get_skill(session: Session, project_id: UUID, skill_slug: str) -> Skill:
    """Get skill by project ID and slug or raise 404."""
    skill = session.execute(
        select(Skill)
        .where(Skill.project_id == project_id, Skill.slug == skill_slug)
        .options(selectinload(Skill.resources))
    ).scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_slug}' not found")
    return skill


def _skill_to_view(skill: Skill) -> SkillView:
    """Convert Skill ORM object to SkillView."""
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
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/projects/{slug}/skills", response_model=list[SkillView])
def list_skills(
    slug: str,
    session: Session = Depends(get_session),
) -> list[SkillView]:
    """List all skills for a project."""
    project = _get_project_by_slug(session, slug)

    skills = (
        session.execute(
            select(Skill)
            .where(Skill.project_id == project.id)
            .options(selectinload(Skill.resources))
            .order_by(Skill.order_no, Skill.name)
        )
        .scalars()
        .all()
    )

    return [_skill_to_view(s) for s in skills]


@router.get("/api/projects/{slug}/skills/stats", response_model=SkillStatsResponse)
def get_skill_stats(
    slug: str,
    session: Session = Depends(get_session),
) -> SkillStatsResponse:
    """Get skill statistics for a project."""
    project = _get_project_by_slug(session, slug)

    skills = (
        session.execute(
            select(Skill)
            .where(Skill.project_id == project.id)
            .options(selectinload(Skill.resources))
        )
        .scalars()
        .all()
    )

    if not skills:
        return SkillStatsResponse(
            total_skills=0,
            by_kind={},
            with_content=0,
            with_resources=0,
            completion_percentage=0.0,
            by_draft_status={"none": 0, "pending": 0, "drafting": 0, "success": 0, "error": 0},
        )

    by_kind: dict[str, int] = {}
    by_draft_status: dict[str, int] = {"none": 0, "pending": 0, "drafting": 0, "success": 0, "error": 0}
    with_content = 0
    with_resources = 0

    for skill in skills:
        kind = skill.kind
        by_kind[kind] = by_kind.get(kind, 0) + 1

        if skill.body_md and skill.body_md.strip():
            with_content += 1

        if skill.resources:
            with_resources += 1

        # Count draft statuses
        draft_status = skill.draft_status or "none"
        if draft_status in by_draft_status:
            by_draft_status[draft_status] += 1
        else:
            by_draft_status["none"] += 1

    return SkillStatsResponse(
        total_skills=len(skills),
        by_kind=by_kind,
        with_content=with_content,
        with_resources=with_resources,
        completion_percentage=(with_content / len(skills) * 100) if skills else 0.0,
        by_draft_status=by_draft_status,
    )


@router.get("/api/projects/{slug}/skills/{skill_slug}", response_model=SkillView)
def get_skill(
    slug: str,
    skill_slug: str,
    session: Session = Depends(get_session),
) -> SkillView:
    """Get a single skill with its resources."""
    project = _get_project_by_slug(session, slug)
    skill = _get_skill(session, project.id, skill_slug)
    return _skill_to_view(skill)


@router.post("/api/projects/{slug}/skills", response_model=SkillView, status_code=201)
def create_skill(
    slug: str,
    request: CreateSkillRequest,
    session: Session = Depends(get_session),
) -> SkillView:
    """Create a new skill."""
    project = _get_project_by_slug(session, slug)

    # Check for duplicate slug
    existing = session.execute(
        select(Skill).where(
            Skill.project_id == project.id, Skill.slug == request.slug
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Skill with slug '{request.slug}' already exists in this project",
        )

    skill = Skill(
        project_id=project.id,
        slug=request.slug,
        name=request.name,
        description=request.description,
        kind=request.kind.value,
        body_md=request.body_md,
        order_no=request.order_no,
    )
    session.add(skill)
    session.commit()
    session.refresh(skill)

    return _skill_to_view(skill)


@router.patch("/api/projects/{slug}/skills/{skill_slug}", response_model=SkillView)
def update_skill(
    slug: str,
    skill_slug: str,
    request: UpdateSkillRequest,
    session: Session = Depends(get_session),
) -> SkillView:
    """Update an existing skill."""
    project = _get_project_by_slug(session, slug)
    skill = _get_skill(session, project.id, skill_slug)

    if request.name is not None:
        skill.name = request.name
    if request.description is not None:
        skill.description = request.description
    if request.kind is not None:
        skill.kind = request.kind.value
    if request.body_md is not None:
        skill.body_md = request.body_md
    if request.order_no is not None:
        skill.order_no = request.order_no

    session.commit()
    session.refresh(skill)

    return _skill_to_view(skill)


@router.delete("/api/projects/{slug}/skills/{skill_slug}", status_code=204)
def delete_skill(
    slug: str,
    skill_slug: str,
    session: Session = Depends(get_session),
) -> None:
    """Delete a skill."""
    project = _get_project_by_slug(session, slug)
    skill = _get_skill(session, project.id, skill_slug)

    session.delete(skill)
    session.commit()


@router.post("/api/projects/{slug}/skills/propose", response_model=ProposeSkillsResponse)
def propose_skills(
    slug: str,
    session: Session = Depends(get_session),
) -> ProposeSkillsResponse:
    """Propose a skill set using LLM based on project context.

    This endpoint gathers all project discovery context (Q&A, tech choices,
    artifacts) and uses the ProposeSkillSet prompt to generate 5-10 skills.
    """
    project = _get_project_by_slug(session, slug)

    # Load project context
    context_service = ProjectContextService(session)
    context = context_service.load_project_context(slug)

    if not context:
        raise HTTPException(
            status_code=400,
            detail="Failed to load project context. Ensure project has an objective defined.",
        )

    if not context.objective or not context.objective.strip():
        raise HTTPException(
            status_code=400,
            detail="Project objective is required before proposing skills.",
        )

    # Create prompt
    prompt = ProposeSkillSetPrompt.create(context)

    # Create LLM service for this project
    factory = LlmServiceFactory()
    llm_service = factory.create_for_project(slug, session)

    # Run the prompt
    result = llm_service.run(prompt, kind=LlmRunKind.PROPOSE_SKILL_SET)

    if not result.parsed:
        raise HTTPException(
            status_code=500,
            detail="LLM failed to generate valid skill proposals. Check LLM run logs.",
        )

    # Get the LLM run ID from the audit table (most recent for this project)
    from app.domain.llm import LlmRun

    llm_run = session.execute(
        select(LlmRun)
        .where(LlmRun.project_id == project.id)
        .order_by(LlmRun.created_at.desc())
        .limit(1)
    ).scalar_one()

    # Persist identified gaps so DraftSkillBody can thread them as context.
    project.identified_gaps = list(result.parsed.gaps or [])

    # Upsert gaps as first-class entities. Existing rows are preserved (we
    # never demote a resolved gap back to open). The JSONB column above is
    # kept as a denormalised cache for clients that don't need lifecycle.
    from app.services.gap_service import GapService

    GapService().upsert_from_propose(
        session, project.id, list(result.parsed.gaps or [])
    )

    session.commit()

    return ProposeSkillsResponse(
        skills=result.parsed.skills,
        coverage_notes=result.parsed.coverage_notes,
        gaps=result.parsed.gaps,
        llm_run_id=llm_run.id,
    )


@router.post(
    "/api/projects/{slug}/skills/bulk",
    response_model=BulkCreateResponse,
    status_code=201,
)
def bulk_create_skills(
    slug: str,
    request: BulkCreateSkillsRequest,
    session: Session = Depends(get_session),
) -> BulkCreateResponse:
    """Bulk create skills from proposals.

    Accepts a list of skills (typically from the propose endpoint) and creates
    them all. Duplicate slugs within the request or existing in the project
    will be skipped with a warning.
    """
    project = _get_project_by_slug(session, slug)

    # Get existing skill slugs
    existing_slugs = set(
        session.execute(
            select(Skill.slug).where(Skill.project_id == project.id)
        )
        .scalars()
        .all()
    )

    created_skills: list[Skill] = []
    seen_slugs: set[str] = set()

    for i, skill_req in enumerate(request.skills):
        # Skip duplicates
        if skill_req.slug in existing_slugs or skill_req.slug in seen_slugs:
            continue

        seen_slugs.add(skill_req.slug)

        skill = Skill(
            project_id=project.id,
            slug=skill_req.slug,
            name=skill_req.name,
            description=skill_req.description,
            kind=skill_req.kind.value,
            body_md=skill_req.body_md,
            order_no=i,
        )
        session.add(skill)
        created_skills.append(skill)

    session.commit()

    # Refresh all created skills to get IDs
    for skill in created_skills:
        session.refresh(skill)

    return BulkCreateResponse(
        created=len(created_skills),
        skills=[_skill_to_view(s) for s in created_skills],
    )


@router.post(
    "/api/projects/{slug}/skills/draft-all",
    response_model=DraftAllSkillsResponse,
)
def draft_all_skills(
    slug: str,
    request: DraftAllSkillsRequest = DraftAllSkillsRequest(),
    session: Session = Depends(get_session),
) -> DraftAllSkillsResponse:
    """Queue draft jobs for all skills that need drafting.

    By default, only drafts skills with empty body_md. Set force=True to
    re-draft all skills. Jobs run asynchronously in the background worker.
    """
    from app.jobs.draft_skill_body import draft_skill_body as draft_job

    project = _get_project_by_slug(session, slug)

    # Get skills that need drafting
    query = select(Skill).where(Skill.project_id == project.id)
    if not request.force:
        # Only skills with empty body
        query = query.where((Skill.body_md == "") | (Skill.body_md.is_(None)))

    skills = session.execute(query).scalars().all()

    queued_slugs: list[str] = []
    for skill in skills:
        # Mark as pending before queueing
        skill.draft_status = SkillDraftStatus.PENDING.value
        skill.draft_error = None
        draft_job.send(str(skill.id), request.include_resources)
        queued_slugs.append(skill.slug)

    return DraftAllSkillsResponse(
        queued=len(queued_slugs),
        skill_slugs=queued_slugs,
    )


# ---------------------------------------------------------------------------
# Skill Body Drafting (LLM)
# ---------------------------------------------------------------------------


@router.post(
    "/api/projects/{slug}/skills/{skill_slug}/draft",
    response_model=DraftSkillBodyResponse,
)
def draft_skill_body(
    slug: str,
    skill_slug: str,
    request: DraftSkillBodyRequest,
    session: Session = Depends(get_session),
) -> DraftSkillBodyResponse:
    """Regenerate skill body (and optionally resources) via LLM.

    Uses project context and sibling skills to generate appropriate content.
    If include_resources is True, also generates and replaces resources.
    """
    project = _get_project_by_slug(session, slug)
    skill = _get_skill(session, project.id, skill_slug)

    # Load project context
    context_service = ProjectContextService(session)
    context = context_service.load_project_context(slug)

    if not context:
        raise HTTPException(
            status_code=400,
            detail="Failed to load project context.",
        )

    # Get sibling skills (other skills in this project)
    sibling_skills = (
        session.execute(
            select(Skill)
            .where(Skill.project_id == project.id, Skill.id != skill.id)
            .options(selectinload(Skill.resources))
        )
        .scalars()
        .all()
    )

    sibling_views = [_skill_to_view(s) for s in sibling_skills]

    # Create prompt
    skill_view = _skill_to_view(skill)
    prompt = DraftSkillBodyPrompt.create(
        skill_view,
        context,
        sibling_views,
        identified_gaps=list(project.identified_gaps or []),
    )

    # Create LLM service
    factory = LlmServiceFactory()
    llm_service = factory.create_for_project(slug, session)

    # Run the prompt
    result = llm_service.run(prompt, kind=LlmRunKind.DRAFT_SKILL_BODY)

    if not result.parsed:
        raise HTTPException(
            status_code=500,
            detail="LLM failed to generate valid skill body. Check LLM run logs.",
        )

    # Update skill body
    skill.body_md = result.parsed.body_md

    resources_created = 0

    # Optionally update resources
    if request.include_resources and result.parsed.resources:
        # Delete existing resources
        session.execute(
            select(SkillResource).where(SkillResource.skill_id == skill.id)
        )
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

    # Get the LLM run ID
    from app.domain.llm import LlmRun

    llm_run = session.execute(
        select(LlmRun)
        .where(LlmRun.project_id == project.id)
        .order_by(LlmRun.created_at.desc())
    ).scalar_one()

    session.commit()

    return DraftSkillBodyResponse(
        body_md=result.parsed.body_md,
        resources_created=resources_created,
        sibling_skills_referenced=result.parsed.sibling_skills_referenced,
        llm_run_id=llm_run.id,
    )


# ---------------------------------------------------------------------------
# Skill Resources CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/api/projects/{slug}/skills/{skill_slug}/resources",
    response_model=list[SkillResourceView],
)
def list_skill_resources(
    slug: str,
    skill_slug: str,
    session: Session = Depends(get_session),
) -> list[SkillResourceView]:
    """List all resources for a skill."""
    project = _get_project_by_slug(session, slug)
    skill = _get_skill(session, project.id, skill_slug)

    return [
        SkillResourceView(
            id=r.id,
            skill_id=r.skill_id,
            filename=r.filename,
            content=r.content,
            language=SkillResourceLanguage(r.language),
            order_no=r.order_no,
        )
        for r in skill.resources
    ]


@router.post(
    "/api/projects/{slug}/skills/{skill_slug}/resources",
    response_model=SkillResourceView,
    status_code=201,
)
def create_skill_resource(
    slug: str,
    skill_slug: str,
    request: CreateResourceRequest,
    session: Session = Depends(get_session),
) -> SkillResourceView:
    """Create a new resource for a skill."""
    project = _get_project_by_slug(session, slug)
    skill = _get_skill(session, project.id, skill_slug)

    # Check for duplicate filename
    existing = session.execute(
        select(SkillResource).where(
            SkillResource.skill_id == skill.id,
            SkillResource.filename == request.filename,
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Resource with filename '{request.filename}' already exists",
        )

    resource = SkillResource(
        skill_id=skill.id,
        filename=request.filename,
        content=request.content,
        language=request.language.value,
        order_no=request.order_no,
    )
    session.add(resource)
    session.commit()
    session.refresh(resource)

    return SkillResourceView(
        id=resource.id,
        skill_id=resource.skill_id,
        filename=resource.filename,
        content=resource.content,
        language=SkillResourceLanguage(resource.language),
        order_no=resource.order_no,
    )


@router.patch(
    "/api/projects/{slug}/skills/{skill_slug}/resources/{resource_id}",
    response_model=SkillResourceView,
)
def update_skill_resource(
    slug: str,
    skill_slug: str,
    resource_id: UUID,
    request: UpdateResourceRequest,
    session: Session = Depends(get_session),
) -> SkillResourceView:
    """Update an existing skill resource."""
    project = _get_project_by_slug(session, slug)
    skill = _get_skill(session, project.id, skill_slug)

    resource = session.execute(
        select(SkillResource).where(
            SkillResource.id == resource_id,
            SkillResource.skill_id == skill.id,
        )
    ).scalar_one_or_none()

    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    if request.filename is not None:
        # Check for duplicate filename (excluding current)
        existing = session.execute(
            select(SkillResource).where(
                SkillResource.skill_id == skill.id,
                SkillResource.filename == request.filename,
                SkillResource.id != resource_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Resource with filename '{request.filename}' already exists",
            )
        resource.filename = request.filename

    if request.content is not None:
        resource.content = request.content
    if request.language is not None:
        resource.language = request.language.value
    if request.order_no is not None:
        resource.order_no = request.order_no

    session.commit()
    session.refresh(resource)

    return SkillResourceView(
        id=resource.id,
        skill_id=resource.skill_id,
        filename=resource.filename,
        content=resource.content,
        language=SkillResourceLanguage(resource.language),
        order_no=resource.order_no,
    )


@router.delete(
    "/api/projects/{slug}/skills/{skill_slug}/resources/{resource_id}",
    status_code=204,
)
def delete_skill_resource(
    slug: str,
    skill_slug: str,
    resource_id: UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete a skill resource."""
    project = _get_project_by_slug(session, slug)
    skill = _get_skill(session, project.id, skill_slug)

    resource = session.execute(
        select(SkillResource).where(
            SkillResource.id == resource_id,
            SkillResource.skill_id == skill.id,
        )
    ).scalar_one_or_none()

    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    session.delete(resource)
    session.commit()
