"""LLM Runs API — audit log and statistics.

Endpoints:
- GET  /api/projects/{slug}/llm-runs         List runs for a project
- GET  /api/projects/{slug}/llm-runs/stats   Get aggregated statistics
- GET  /api/llm-runs/{run_id}                Get a single run
- GET  /api/llm-runs/{run_id}/details        Get run with full prompt/response
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.llm import LlmRun
from app.domain.projects import Project
from app.enums import LlmRunKind, LlmRunStatus, LlmProvider
from app.schemas.views import LlmRunView

router = APIRouter(tags=["llm-runs"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class LlmRunsListResponse(BaseModel):
    runs: list[LlmRunView]
    total: int


class LlmRunsStatsResponse(BaseModel):
    total_runs: int
    by_kind: dict[str, int]
    by_status: dict[str, int]
    by_provider: dict[str, int]
    total_cost_usd: float
    total_tokens_in: int
    total_tokens_out: int


class PromptMessage(BaseModel):
    role: str
    content: str


class LlmRunPrompt(BaseModel):
    system: str | None = None
    messages: list[PromptMessage]


class LlmRunResponse(BaseModel):
    text: str | None = None
    json: dict[str, Any] | None = None
    reasoning: str | None = None


class LlmRunDetailsResponse(BaseModel):
    run: LlmRunView
    prompt: LlmRunPrompt
    response: LlmRunResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_project_by_slug(session: Session, slug: str) -> Project:
    """Get project by slug or raise 404."""
    project = session.execute(
        select(Project).where(Project.slug == slug)
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return project


def _to_view(run: LlmRun) -> LlmRunView:
    return LlmRunView.model_validate(run)


def _parse_prompt_messages(messages_json: list[dict[str, Any]]) -> LlmRunPrompt:
    """Parse prompt messages JSON into structured format."""
    system = None
    messages = []
    
    for msg in messages_json:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        if role == "system":
            system = content
        else:
            messages.append(PromptMessage(role=role, content=content))
    
    return LlmRunPrompt(system=system, messages=messages)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/projects/{slug}/llm-runs", response_model=LlmRunsListResponse)
def list_llm_runs(
    slug: str,
    kind: LlmRunKind | None = Query(None, description="Filter by run kind"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> LlmRunsListResponse:
    """List LLM runs for a project with pagination and optional filtering."""
    project = _get_project_by_slug(session, slug)
    
    # Base query
    base_query = select(LlmRun).where(LlmRun.project_id == project.id)
    
    # Apply kind filter if provided
    if kind:
        base_query = base_query.where(LlmRun.kind == kind)
    
    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total = session.execute(count_query).scalar() or 0
    
    # Get paginated results
    query = (
        base_query
        .order_by(LlmRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    runs = session.execute(query).scalars().all()
    
    return LlmRunsListResponse(
        runs=[_to_view(r) for r in runs],
        total=total,
    )


@router.get("/api/projects/{slug}/llm-runs/stats", response_model=LlmRunsStatsResponse)
def get_llm_runs_stats(
    slug: str,
    session: Session = Depends(get_session),
) -> LlmRunsStatsResponse:
    """Get aggregated statistics for LLM runs in a project."""
    project = _get_project_by_slug(session, slug)
    
    # Get all runs for the project
    runs = session.execute(
        select(LlmRun).where(LlmRun.project_id == project.id)
    ).scalars().all()
    
    # Compute aggregates
    total_runs = len(runs)
    by_kind: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_provider: dict[str, int] = {}
    total_cost = Decimal("0")
    total_tokens_in = 0
    total_tokens_out = 0
    
    for run in runs:
        # Count by kind
        by_kind[run.kind] = by_kind.get(run.kind, 0) + 1
        
        # Count by status
        by_status[run.status] = by_status.get(run.status, 0) + 1
        
        # Count by provider
        by_provider[run.provider] = by_provider.get(run.provider, 0) + 1
        
        # Sum costs and tokens
        if run.cost_usd:
            total_cost += run.cost_usd
        if run.tokens_in:
            total_tokens_in += run.tokens_in
        if run.tokens_out:
            total_tokens_out += run.tokens_out
    
    return LlmRunsStatsResponse(
        total_runs=total_runs,
        by_kind=by_kind,
        by_status=by_status,
        by_provider=by_provider,
        total_cost_usd=float(total_cost),
        total_tokens_in=total_tokens_in,
        total_tokens_out=total_tokens_out,
    )


@router.get("/api/llm-runs/{run_id}", response_model=LlmRunView)
def get_llm_run(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> LlmRunView:
    """Get a single LLM run by ID."""
    run = session.get(LlmRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"LLM run '{run_id}' not found")
    return _to_view(run)


@router.get("/api/llm-runs/{run_id}/details", response_model=LlmRunDetailsResponse)
def get_llm_run_details(
    run_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> LlmRunDetailsResponse:
    """Get LLM run with full prompt and response details."""
    run = session.get(LlmRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"LLM run '{run_id}' not found")
    
    # Parse prompt messages
    prompt = _parse_prompt_messages(run.prompt_messages_json or [])
    
    # Build response
    response = LlmRunResponse(
        text=run.response_text,
        json=run.response_json,
        reasoning=run.reasoning_md,
    )
    
    return LlmRunDetailsResponse(
        run=_to_view(run),
        prompt=prompt,
        response=response,
    )
