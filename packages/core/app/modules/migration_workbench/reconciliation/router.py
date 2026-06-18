"""API router for reconciliation endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.projects import Project
from app.modules.migration_workbench.models import ETLPackage
from app.modules.migration_workbench.reconciliation.schemas import (
    ReconciliationRequest,
    ReconciliationRunResult,
    ReconciliationRunView,
)
from app.modules.migration_workbench.reconciliation.service import (
    ReconciliationService,
)

router = APIRouter(prefix="/{project_ref}/reconciliation", tags=["reconciliation"])


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


def _check_package_in_project(
    session: Session, package_id: uuid.UUID, project: Project
) -> ETLPackage:
    package = session.get(ETLPackage, package_id)
    if not package or package.project_id != project.id:
        raise HTTPException(status_code=404, detail="Package not found in project")
    return package


@router.post("/packages/{package_id}/run")
async def run_reconciliation(
    package_id: uuid.UUID,
    project: Annotated[Project, Depends(_get_project_or_404)],
    session: Annotated[Session, Depends(get_session)],
    request: ReconciliationRequest | None = None,
) -> ReconciliationRunResult:
    """Run reconciliation checks for a package.
    
    Compares source and target data to validate the migration.
    """
    _check_package_in_project(session, package_id, project)
    
    service = ReconciliationService(session)
    config = request.config if request else None
    
    try:
        result = service.run_reconciliation(package_id, config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    session.commit()
    return result


@router.get("/packages/{package_id}/runs")
async def list_package_runs(
    package_id: uuid.UUID,
    project: Annotated[Project, Depends(_get_project_or_404)],
    session: Annotated[Session, Depends(get_session)],
    limit: int = 20,
) -> list[ReconciliationRunView]:
    """List reconciliation runs for a specific package."""
    _check_package_in_project(session, package_id, project)
    
    service = ReconciliationService(session)
    return service.list_runs(project.id, package_id=package_id, limit=limit)


@router.get("/runs")
async def list_project_runs(
    project: Annotated[Project, Depends(_get_project_or_404)],
    session: Annotated[Session, Depends(get_session)],
    limit: int = 50,
) -> list[ReconciliationRunView]:
    """List all reconciliation runs for a project."""
    service = ReconciliationService(session)
    return service.list_runs(project.id, limit=limit)


@router.get("/runs/{run_id}")
async def get_run(
    run_id: uuid.UUID,
    project: Annotated[Project, Depends(_get_project_or_404)],
    session: Annotated[Session, Depends(get_session)],
) -> ReconciliationRunResult:
    """Get details of a specific reconciliation run."""
    service = ReconciliationService(session)
    result = service.get_run(run_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Reconciliation run not found")
    
    return result
