"""Projects API — read-only listing and detail.

Endpoints
-  GET  /api/projects                     list all projects (newest first)
-  GET  /api/projects/{project_id}        single project detail
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.projects import Project
from app.schemas.views import ProjectView

router = APIRouter(tags=["projects"])


def _to_view(row: Project) -> ProjectView:
    return ProjectView.model_validate(row)


@router.get("/api/projects", response_model=list[ProjectView])
def list_projects(session: Session = Depends(get_session)) -> list[ProjectView]:
    """Return all projects ordered by creation date descending."""
    rows = (
        session.execute(select(Project).order_by(Project.created_at.desc()))
        .scalars()
        .all()
    )
    return [_to_view(r) for r in rows]


@router.get("/api/projects/{project_id}", response_model=ProjectView)
def get_project(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> ProjectView:
    """Return a single project by ID."""
    row = session.get(Project, project_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return _to_view(row)
