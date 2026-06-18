"""API router for sign-off workflow endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.projects import Project
from app.modules.migration_workbench.signoff.schemas import (
    ApproveSignoffRequest,
    CreateSignoffRequest,
    RejectSignoffRequest,
    SignoffRequest,
    SignoffRequestView,
    SignoffStatus,
    SignoffType,
    UpdateChecklistItem,
)
from app.modules.migration_workbench.signoff.service import SignoffService

router = APIRouter(prefix="/{project_ref}/signoff", tags=["signoff"])


async def _get_project_or_404(
    project_ref: str,
    session: Session = Depends(get_session),
) -> Project:
    try:
        project_id = uuid.UUID(project_ref)
        project = session.get(Project, project_id)
    except ValueError:
        project = session.execute(
            select(Project).where(Project.slug == project_ref)
        ).scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_signoff_service(
    session: Session = Depends(get_session),
) -> SignoffService:
    """Create a fresh SignoffService per request — no shared state."""
    return SignoffService(session)


@router.post("/requests")
async def create_signoff(
    request: CreateSignoffRequest,
    project: Annotated[Project, Depends(_get_project_or_404)],
    service: Annotated[SignoffService, Depends(get_signoff_service)],
    session: Annotated[Session, Depends(get_session)],
) -> SignoffRequest:
    """Create a new sign-off request with the default checklist."""
    try:
        result = service.create_signoff(project.id, request)
        session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/requests")
async def list_signoffs(
    project: Annotated[Project, Depends(_get_project_or_404)],
    service: Annotated[SignoffService, Depends(get_signoff_service)],
    status: SignoffStatus | None = Query(None),
    signoff_type: SignoffType | None = Query(None),
    limit: int = Query(50, le=100),
) -> list[SignoffRequestView]:
    """List sign-off requests for a project."""
    return service.list_signoffs(
        project_id=project.id,
        status=status,
        signoff_type=signoff_type,
        limit=limit,
    )


@router.get("/requests/{signoff_id}")
async def get_signoff(
    signoff_id: uuid.UUID,
    project: Annotated[Project, Depends(_get_project_or_404)],
    service: Annotated[SignoffService, Depends(get_signoff_service)],
) -> SignoffRequest:
    """Get a specific sign-off request including all checklist items."""
    signoff = service.get_signoff(signoff_id)
    if not signoff or signoff.project_id != project.id:
        raise HTTPException(status_code=404, detail="Sign-off not found")
    return signoff


@router.post("/requests/{signoff_id}/submit")
async def submit_signoff(
    signoff_id: uuid.UUID,
    project: Annotated[Project, Depends(_get_project_or_404)],
    service: Annotated[SignoffService, Depends(get_signoff_service)],
    session: Annotated[Session, Depends(get_session)],
) -> SignoffRequest:
    """Submit a sign-off for approval (DRAFT → PENDING).

    All required checklist items must be completed before submission.
    """
    try:
        result = service.submit_signoff(signoff_id)
        session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/requests/{signoff_id}/checklist")
async def update_checklist_item(
    signoff_id: uuid.UUID,
    update: UpdateChecklistItem,
    project: Annotated[Project, Depends(_get_project_or_404)],
    service: Annotated[SignoffService, Depends(get_signoff_service)],
    session: Annotated[Session, Depends(get_session)],
) -> SignoffRequest:
    """Update a checklist item in a sign-off (status, evidence, notes)."""
    try:
        result = service.update_checklist_item(signoff_id, update)
        session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/requests/{signoff_id}/approve")
async def approve_signoff(
    signoff_id: uuid.UUID,
    approval: ApproveSignoffRequest,
    project: Annotated[Project, Depends(_get_project_or_404)],
    service: Annotated[SignoffService, Depends(get_signoff_service)],
    session: Annotated[Session, Depends(get_session)],
) -> SignoffRequest:
    """Approve a pending sign-off (N3/N4 gate).

    approved_at is set server-side — the client cannot supply a timestamp.
    """
    try:
        result = service.approve_signoff(signoff_id, approval)
        session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/requests/{signoff_id}/reject")
async def reject_signoff(
    signoff_id: uuid.UUID,
    rejection: RejectSignoffRequest,
    project: Annotated[Project, Depends(_get_project_or_404)],
    service: Annotated[SignoffService, Depends(get_signoff_service)],
    session: Annotated[Session, Depends(get_session)],
) -> SignoffRequest:
    """Reject a pending sign-off with a mandatory reason."""
    try:
        result = service.reject_signoff(signoff_id, rejection)
        session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/requests/{signoff_id}/cancel")
async def cancel_signoff(
    signoff_id: uuid.UUID,
    project: Annotated[Project, Depends(_get_project_or_404)],
    service: Annotated[SignoffService, Depends(get_signoff_service)],
    session: Annotated[Session, Depends(get_session)],
) -> SignoffRequest:
    """Cancel a sign-off that has not yet been approved or rejected."""
    try:
        result = service.cancel_signoff(signoff_id)
        session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
