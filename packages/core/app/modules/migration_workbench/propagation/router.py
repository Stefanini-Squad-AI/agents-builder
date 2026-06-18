"""API router for propagation endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.projects import Project
from app.modules.migration_workbench.propagation.schemas import (
    BatchWaveAssignment,
    BatchWaveResult,
    PropagationPreview,
    PropagationRequest,
    PropagationResult,
    PropagationScope,
)
from app.modules.migration_workbench.propagation.service import PropagationService

router = APIRouter(prefix="/{project_ref}/propagation", tags=["propagation"])


async def _get_project_or_404(
    project_ref: str,
    session: Session = Depends(get_session),
) -> Project:
    """Get project by slug or UUID, or raise 404."""
    from sqlalchemy import select
    
    # Try UUID first
    try:
        project_id = uuid.UUID(project_ref)
        project = session.get(Project, project_id)
    except ValueError:
        # Try slug
        project = session.execute(
            select(Project).where(Project.slug == project_ref)
        ).scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return project


@router.get("/decisions/{decision_id}/preview")
async def preview_propagation(
    decision_id: uuid.UUID,
    scope: PropagationScope = Query(PropagationScope.PROJECT),
    cluster_id: uuid.UUID | None = Query(None),
    domain: str | None = Query(None),
    project: Project = Depends(_get_project_or_404),
    session: Session = Depends(get_session),
) -> PropagationPreview:
    """Preview what packages would be affected by propagating a decision.
    
    Use this before actually propagating to see the impact.
    """
    service = PropagationService(session)
    
    try:
        return service.preview_propagation(
            decision_id=decision_id,
            scope=scope,
            cluster_id=cluster_id,
            domain=domain,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/decisions/{decision_id}/propagate")
async def propagate_decision(
    decision_id: uuid.UUID,
    request: PropagationRequest | None = None,
    project: Project = Depends(_get_project_or_404),
    session: Session = Depends(get_session),
) -> PropagationResult:
    """Propagate a resolved decision to matching packages.
    
    Finds all packages with the same unresolved decision type and
    automatically resolves them with the same answer.
    
    This enables "resolve once, apply everywhere" workflows.
    """
    service = PropagationService(session)
    
    scope = PropagationScope.PROJECT
    cluster_id = None
    domain = None
    
    if request:
        scope = request.scope
        cluster_id = request.cluster_id
        domain = request.domain
    
    try:
        return service.propagate_decision(
            decision_id=decision_id,
            scope=scope,
            cluster_id=cluster_id,
            domain=domain,
            propagated_by=None,  # TODO: Get from auth context
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/waves/batch")
async def batch_assign_waves(
    request: BatchWaveAssignment,
    project: Project = Depends(_get_project_or_404),
    session: Session = Depends(get_session),
) -> BatchWaveResult:
    """Assign migration waves to multiple packages at once.
    
    Useful for bulk wave planning from the migration map.
    """
    service = PropagationService(session)
    
    return service.batch_assign_waves(
        project_id=project.id,
        assignments=request.assignments,
    )
