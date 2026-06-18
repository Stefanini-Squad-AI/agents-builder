"""Gaps API — manage project coverage gaps surfaced by ProposeSkillSet.

A gap is a project-scoped concern flagged by the LLM (e.g. "no skill covers
secrets rotation"). It starts in `open` status and transitions to one of:

    - `addressed_by_skill`  — a project skill covers it
    - `covered_by_mcp`      — an external MCP server covers it
    - `out_of_scope`        — explicitly excluded from this project

Endpoints:
    GET    /api/projects/{slug}/gaps                       list (with status filter)
    POST   /api/projects/{slug}/gaps                       create manual gap
    POST   /api/projects/{slug}/gaps/{id}/address-by-skill set addressed_by_skill
    POST   /api/projects/{slug}/gaps/{id}/cover-by-mcp     set covered_by_mcp
    POST   /api/projects/{slug}/gaps/{id}/out-of-scope     set out_of_scope
    POST   /api/projects/{slug}/gaps/{id}/reopen           back to open
    DELETE /api/projects/{slug}/gaps/{id}                  delete (manual gaps only)
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.projects import Project, ProjectGap
from app.domain.skills import Skill
from app.enums import GapSource, GapStatus
from app.services.gap_service import GapService

router = APIRouter(tags=["gaps"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GapView(BaseModel):
    """API view of a ProjectGap row."""

    id: UUID
    project_id: UUID
    title: str
    source: GapSource
    status: GapStatus
    addressed_by_skill_id: UUID | None
    covered_by_mcp_key: str | None
    decision_rationale: str | None
    decided_by_user_id: UUID | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_row(cls, gap: ProjectGap) -> "GapView":
        return cls(
            id=gap.id,
            project_id=gap.project_id,
            title=gap.title,
            source=GapSource(gap.source),
            status=GapStatus(gap.status),
            addressed_by_skill_id=gap.addressed_by_skill_id,
            covered_by_mcp_key=gap.covered_by_mcp_key,
            decision_rationale=gap.decision_rationale,
            decided_by_user_id=gap.decided_by_user_id,
            decided_at=gap.decided_at,
            created_at=gap.created_at,
            updated_at=gap.updated_at,
        )


class CreateGapRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)


class AddressBySkillRequest(BaseModel):
    skill_slug: str = Field(..., min_length=1)
    rationale: str | None = None


class CoverByMcpRequest(BaseModel):
    mcp_key: str = Field(..., min_length=1, max_length=200)
    rationale: str | None = None


class OutOfScopeRequest(BaseModel):
    rationale: str | None = None


class GapsCountResponse(BaseModel):
    open: int
    addressed_by_skill: int
    covered_by_mcp: int
    out_of_scope: int
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_project(session: Session, slug: str) -> Project:
    project = session.execute(
        select(Project).where(Project.slug == slug)
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return project


def _get_gap(session: Session, project_id: UUID, gap_id: UUID) -> ProjectGap:
    gap = session.execute(
        select(ProjectGap).where(
            ProjectGap.id == gap_id,
            ProjectGap.project_id == project_id,
        )
    ).scalar_one_or_none()
    if gap is None:
        raise HTTPException(status_code=404, detail=f"Gap '{gap_id}' not found")
    return gap


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/projects/{slug}/gaps", response_model=list[GapView])
def list_gaps(
    slug: str,
    status: GapStatus | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[GapView]:
    """List gaps for a project, optionally filtered by status."""
    project = _get_project(session, slug)
    service = GapService()
    rows = (
        service.list_open(session, project.id)
        if status == GapStatus.OPEN
        else service.list_all(session, project.id)
    )
    if status is not None and status != GapStatus.OPEN:
        rows = [g for g in rows if g.status == status.value]
    return [GapView.from_orm_row(g) for g in rows]


@router.get("/api/projects/{slug}/gaps/stats", response_model=GapsCountResponse)
def gaps_stats(slug: str, session: Session = Depends(get_session)) -> GapsCountResponse:
    """Counts per status for the Potential Gaps panel."""
    project = _get_project(session, slug)
    rows = GapService().list_all(session, project.id)
    counts = {s.value: 0 for s in GapStatus}
    for g in rows:
        counts[g.status] = counts.get(g.status, 0) + 1
    return GapsCountResponse(
        open=counts[GapStatus.OPEN.value],
        addressed_by_skill=counts[GapStatus.ADDRESSED_BY_SKILL.value],
        covered_by_mcp=counts[GapStatus.COVERED_BY_MCP.value],
        out_of_scope=counts[GapStatus.OUT_OF_SCOPE.value],
        total=len(rows),
    )


@router.post(
    "/api/projects/{slug}/gaps",
    response_model=GapView,
    status_code=201,
)
def create_manual_gap(
    slug: str,
    request: CreateGapRequest,
    session: Session = Depends(get_session),
) -> GapView:
    """Create a manual gap (source=manual)."""
    project = _get_project(session, slug)
    inserted = GapService().upsert_from_propose(session, project.id, [request.title])
    # Re-fetch the new (or existing) gap row.
    from app.services.gap_service import _title_key  # type: ignore[attr-defined]

    key = _title_key(request.title)
    gap = session.execute(
        select(ProjectGap).where(
            ProjectGap.project_id == project.id,
            ProjectGap.title_key == key,
        )
    ).scalar_one()
    # Override source for newly-inserted manual gaps.
    if inserted and gap.source != GapSource.MANUAL.value:
        gap.source = GapSource.MANUAL.value
    session.commit()
    return GapView.from_orm_row(gap)


@router.post(
    "/api/projects/{slug}/gaps/{gap_id}/address-by-skill",
    response_model=GapView,
)
def address_by_skill(
    slug: str,
    gap_id: UUID,
    request: AddressBySkillRequest,
    session: Session = Depends(get_session),
) -> GapView:
    project = _get_project(session, slug)
    gap = _get_gap(session, project.id, gap_id)

    skill = session.execute(
        select(Skill).where(
            Skill.project_id == project.id,
            Skill.slug == request.skill_slug,
        )
    ).scalar_one_or_none()
    if skill is None:
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{request.skill_slug}' not found in project",
        )

    GapService().mark_addressed_by_skill(
        session, gap, skill_id=skill.id, rationale=request.rationale
    )
    session.commit()
    return GapView.from_orm_row(gap)


@router.post(
    "/api/projects/{slug}/gaps/{gap_id}/cover-by-mcp",
    response_model=GapView,
)
def cover_by_mcp(
    slug: str,
    gap_id: UUID,
    request: CoverByMcpRequest,
    session: Session = Depends(get_session),
) -> GapView:
    project = _get_project(session, slug)
    gap = _get_gap(session, project.id, gap_id)
    GapService().mark_covered_by_mcp(
        session, gap, mcp_key=request.mcp_key, rationale=request.rationale
    )
    session.commit()
    return GapView.from_orm_row(gap)


@router.post(
    "/api/projects/{slug}/gaps/{gap_id}/out-of-scope",
    response_model=GapView,
)
def out_of_scope(
    slug: str,
    gap_id: UUID,
    request: OutOfScopeRequest,
    session: Session = Depends(get_session),
) -> GapView:
    project = _get_project(session, slug)
    gap = _get_gap(session, project.id, gap_id)
    GapService().mark_out_of_scope(session, gap, rationale=request.rationale)
    session.commit()
    return GapView.from_orm_row(gap)


@router.post(
    "/api/projects/{slug}/gaps/{gap_id}/reopen",
    response_model=GapView,
)
def reopen_gap(
    slug: str,
    gap_id: UUID,
    session: Session = Depends(get_session),
) -> GapView:
    project = _get_project(session, slug)
    gap = _get_gap(session, project.id, gap_id)
    GapService().reopen(session, gap)
    session.commit()
    return GapView.from_orm_row(gap)


@router.delete(
    "/api/projects/{slug}/gaps/{gap_id}",
    status_code=204,
)
def delete_gap(
    slug: str,
    gap_id: UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete a gap. Only manual gaps may be deleted; LLM-surfaced gaps must
    be moved to a terminal status instead."""
    project = _get_project(session, slug)
    gap = _get_gap(session, project.id, gap_id)
    if gap.source != GapSource.MANUAL.value:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot delete an LLM-surfaced gap. "
                "Move it to addressed_by_skill, covered_by_mcp, or out_of_scope."
            ),
        )
    session.delete(gap)
    session.commit()
