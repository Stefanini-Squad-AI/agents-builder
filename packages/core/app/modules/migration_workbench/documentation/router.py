"""Documentation API routes.

Endpoints for:
- Getting current documentation state
- Viewing documentation history
- Viewing changes between versions
- Triggering manual regeneration
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.projects import Project
from app.modules.migration_workbench.documentation.schemas import (
    ChangesSummary,
    ChangeView,
    DocSnapshotView,
)
from app.modules.migration_workbench.documentation.service import DocumentationService
from app.modules.migration_workbench.models import (
    DocumentationChange,
    MigrationDocSnapshot,
)

router = APIRouter()


def _get_project_or_404(session: Session, project_ref: str) -> Project:
    """Get project by ID or slug."""
    try:
        project_id = uuid.UUID(project_ref)
        project = session.get(Project, project_id)
    except ValueError:
        project = session.scalar(
            select(Project).where(Project.slug == project_ref)
        )
    
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_ref} not found")
    return project


# -----------------------------------------------------------------------------
# Documentation Snapshots
# -----------------------------------------------------------------------------


@router.get("/{project_ref}/docs", response_model=DocSnapshotView | None)
async def get_current_documentation(
    project_ref: str,
    session: Session = Depends(get_session),
) -> DocSnapshotView | None:
    """Get the current (latest) documentation snapshot."""
    project = _get_project_or_404(session, project_ref)
    service = DocumentationService(session)
    return service.get_latest_snapshot(project.id)


@router.post("/{project_ref}/docs/regenerate", response_model=DocSnapshotView)
async def regenerate_documentation(
    project_ref: str,
    reason: str = Query("manual_regeneration", description="Reason for regeneration"),
    session: Session = Depends(get_session),
) -> DocSnapshotView:
    """Manually trigger documentation regeneration."""
    project = _get_project_or_404(session, project_ref)
    service = DocumentationService(session)
    
    snapshot = service.generate_snapshot(project.id, trigger_event=reason)
    session.commit()
    
    return DocSnapshotView.model_validate(snapshot)


@router.get("/{project_ref}/docs/history", response_model=list[DocSnapshotView])
async def get_documentation_history(
    project_ref: str,
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> list[DocSnapshotView]:
    """Get documentation version history."""
    project = _get_project_or_404(session, project_ref)
    
    stmt = (
        select(MigrationDocSnapshot)
        .where(MigrationDocSnapshot.project_id == project.id)
        .order_by(MigrationDocSnapshot.version.desc())
        .limit(limit)
    )
    
    return [DocSnapshotView.model_validate(s) for s in session.scalars(stmt)]


@router.get("/{project_ref}/docs/{version}", response_model=DocSnapshotView)
async def get_documentation_version(
    project_ref: str,
    version: int,
    session: Session = Depends(get_session),
) -> DocSnapshotView:
    """Get a specific documentation version."""
    project = _get_project_or_404(session, project_ref)
    
    snapshot = session.scalar(
        select(MigrationDocSnapshot).where(
            MigrationDocSnapshot.project_id == project.id,
            MigrationDocSnapshot.version == version,
        )
    )
    
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")
    
    return DocSnapshotView.model_validate(snapshot)


# -----------------------------------------------------------------------------
# Change Tracking
# -----------------------------------------------------------------------------


@router.get("/{project_ref}/docs/changes", response_model=ChangesSummary)
async def get_changes_summary(
    project_ref: str,
    from_version: int | None = Query(None, description="Starting version (default: previous)"),
    to_version: int | None = Query(None, description="Ending version (default: latest)"),
    session: Session = Depends(get_session),
) -> ChangesSummary:
    """Get summary of changes between versions."""
    project = _get_project_or_404(session, project_ref)
    service = DocumentationService(session)
    return service.get_changes_summary(project.id, from_version, to_version)


@router.get("/{project_ref}/docs/changes/recent", response_model=list[ChangeView])
async def get_recent_changes(
    project_ref: str,
    limit: int = Query(20, ge=1, le=100),
    significance: str | None = Query(None, description="Filter: critical, notable, info"),
    category: str | None = Query(None, description="Filter by category"),
    session: Session = Depends(get_session),
) -> list[ChangeView]:
    """Get recent documentation changes."""
    project = _get_project_or_404(session, project_ref)
    
    stmt = (
        select(DocumentationChange)
        .where(DocumentationChange.project_id == project.id)
    )
    
    if significance:
        stmt = stmt.where(DocumentationChange.significance == significance)
    if category:
        stmt = stmt.where(DocumentationChange.category == category)
    
    stmt = stmt.order_by(DocumentationChange.detected_at.desc()).limit(limit)
    
    return [ChangeView.model_validate(c) for c in session.scalars(stmt)]


# -----------------------------------------------------------------------------
# Content Endpoints (for direct markdown rendering)
# -----------------------------------------------------------------------------


@router.get("/{project_ref}/docs/content/summary")
async def get_project_summary_content(
    project_ref: str,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Get just the project summary markdown."""
    project = _get_project_or_404(session, project_ref)
    service = DocumentationService(session)
    snapshot = service.get_latest_snapshot(project.id)
    
    if not snapshot:
        return {"content": "No documentation generated yet."}
    
    return {"content": snapshot.project_summary_md}


@router.get("/{project_ref}/docs/content/map")
async def get_migration_map_content(
    project_ref: str,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Get just the migration map markdown (with Mermaid)."""
    project = _get_project_or_404(session, project_ref)
    service = DocumentationService(session)
    snapshot = service.get_latest_snapshot(project.id)
    
    if not snapshot:
        return {"content": "No documentation generated yet."}
    
    return {"content": snapshot.migration_map_md}


@router.get("/{project_ref}/docs/content/packages")
async def get_packages_summary_content(
    project_ref: str,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Get just the packages summary markdown."""
    project = _get_project_or_404(session, project_ref)
    service = DocumentationService(session)
    snapshot = service.get_latest_snapshot(project.id)
    
    if not snapshot:
        return {"content": "No documentation generated yet."}
    
    return {"content": snapshot.packages_summary_md}
