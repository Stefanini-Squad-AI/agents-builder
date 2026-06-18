"""API router for Migration Map module."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.projects import Project
from app.modules.migration_workbench.map.schemas import (
    ClusterView,
    ClusterWithMembers,
    ClustersListResponse,
    FlowDepConfirm,
    FlowDepCreate,
    FlowDepsListResponse,
    FlowDepView,
    MapRefreshResult,
    MapVisualization,
    ObjectsListResponse,
    ObjectView,
    ObjectWithPackages,
    WaveSuggestionsResult,
)
from app.modules.migration_workbench.map.service import MigrationMapService

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


def get_map_service(db: Session = Depends(get_session)) -> MigrationMapService:
    """Dependency for MigrationMapService."""
    return MigrationMapService(db)


# -----------------------------------------------------------------------------
# Map Visualization
# -----------------------------------------------------------------------------


@router.get(
    "/{project_ref}/map",
    response_model=MapVisualization,
    summary="Get full map visualization",
)
async def get_map(
    project_ref: str,
    include_objects: bool = Query(False, description="Include object nodes"),
    db: Session = Depends(get_session),
    service: MigrationMapService = Depends(get_map_service),
) -> MapVisualization:
    """Get the full migration map visualization data for React Flow.
    
    Returns nodes (packages), edges (dependencies), clusters,
    orphan packages, and statistics.
    """
    project = _get_project_or_404(db, project_ref)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return service.get_map_visualization(project.id, include_objects)


@router.post(
    "/{project_ref}/map/refresh",
    response_model=MapRefreshResult,
    summary="Refresh the migration map",
)
async def refresh_map(
    project_ref: str,
    db: Session = Depends(get_session),
    service: MigrationMapService = Depends(get_map_service),
) -> MapRefreshResult:
    """Recompute all relationships and clusters.
    
    Use this after manual changes or when the map may be stale.
    """
    project = _get_project_or_404(db, project_ref)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    result = service.refresh_map(project.id)
    db.commit()
    return result


# -----------------------------------------------------------------------------
# Objects
# -----------------------------------------------------------------------------


@router.get(
    "/{project_ref}/map/objects",
    response_model=ObjectsListResponse,
    summary="List discovered objects",
)
async def list_objects(
    project_ref: str,
    object_type: str | None = Query(None, description="Filter by type"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
    service: MigrationMapService = Depends(get_map_service),
) -> ObjectsListResponse:
    """List all tables/files/APIs discovered across packages."""
    project = _get_project_or_404(db, project_ref)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    objects = service.get_objects(project.id, object_type, limit, offset)
    return ObjectsListResponse(objects=objects, total=len(objects))


@router.get(
    "/{project_ref}/map/objects/{object_id}",
    response_model=ObjectWithPackages,
    summary="Get object details",
)
async def get_object(
    project_ref: str,
    object_id: uuid.UUID,
    db: Session = Depends(get_session),
    service: MigrationMapService = Depends(get_map_service),
) -> ObjectWithPackages:
    """Get object details with list of reading/writing packages."""
    project = _get_project_or_404(db, project_ref)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    obj = service.object_registry.get_object_with_packages(object_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")
    
    return obj


# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------


@router.get(
    "/{project_ref}/map/deps",
    response_model=FlowDepsListResponse,
    summary="List flow dependencies",
)
async def list_dependencies(
    project_ref: str,
    db: Session = Depends(get_session),
    service: MigrationMapService = Depends(get_map_service),
) -> FlowDepsListResponse:
    """List all flow dependencies between packages."""
    project = _get_project_or_404(db, project_ref)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    deps = service.get_dependencies(project.id)
    return FlowDepsListResponse(dependencies=deps, total=len(deps))


@router.post(
    "/{project_ref}/map/deps",
    response_model=FlowDepView,
    summary="Create manual dependency",
)
async def create_dependency(
    project_ref: str,
    body: FlowDepCreate,
    db: Session = Depends(get_session),
    service: MigrationMapService = Depends(get_map_service),
) -> FlowDepView:
    """Create a manual dependency between packages."""
    project = _get_project_or_404(db, project_ref)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    dep = service.create_manual_dependency(
        project.id,
        body.upstream_package_id,
        body.downstream_package_id,
    )
    db.commit()
    return dep


@router.put(
    "/{project_ref}/map/deps/{dep_id}/confirm",
    response_model=dict,
    summary="Confirm or reject dependency",
)
async def confirm_dependency(
    project_ref: str,
    dep_id: uuid.UUID,
    body: FlowDepConfirm,
    db: Session = Depends(get_session),
    service: MigrationMapService = Depends(get_map_service),
) -> dict:
    """Confirm or reject an auto-detected dependency."""
    project = _get_project_or_404(db, project_ref)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    success = service.confirm_dependency(dep_id, body.is_confirmed)
    if not success:
        raise HTTPException(status_code=404, detail="Dependency not found")
    
    db.commit()
    return {"success": True, "is_confirmed": body.is_confirmed}


@router.delete(
    "/{project_ref}/map/deps/{dep_id}",
    response_model=dict,
    summary="Delete dependency",
)
async def delete_dependency(
    project_ref: str,
    dep_id: uuid.UUID,
    db: Session = Depends(get_session),
    service: MigrationMapService = Depends(get_map_service),
) -> dict:
    """Delete a dependency (manual or auto-detected)."""
    project = _get_project_or_404(db, project_ref)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    success = service.delete_dependency(dep_id)
    if not success:
        raise HTTPException(status_code=404, detail="Dependency not found")
    
    db.commit()
    return {"success": True}


# -----------------------------------------------------------------------------
# Clusters
# -----------------------------------------------------------------------------


@router.get(
    "/{project_ref}/map/clusters",
    response_model=ClustersListResponse,
    summary="List clusters",
)
async def list_clusters(
    project_ref: str,
    db: Session = Depends(get_session),
    service: MigrationMapService = Depends(get_map_service),
) -> ClustersListResponse:
    """List all package clusters (connected components)."""
    project = _get_project_or_404(db, project_ref)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    clusters = service.get_clusters(project.id)
    return ClustersListResponse(clusters=clusters, total=len(clusters))


@router.get(
    "/{project_ref}/map/clusters/{cluster_id}",
    response_model=ClusterWithMembers,
    summary="Get cluster details",
)
async def get_cluster(
    project_ref: str,
    cluster_id: uuid.UUID,
    db: Session = Depends(get_session),
    service: MigrationMapService = Depends(get_map_service),
) -> ClusterWithMembers:
    """Get cluster details with member packages."""
    project = _get_project_or_404(db, project_ref)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    cluster = service.get_cluster(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    
    return cluster


# -----------------------------------------------------------------------------
# Waves
# -----------------------------------------------------------------------------


@router.post(
    "/{project_ref}/map/waves/suggest",
    response_model=WaveSuggestionsResult,
    summary="Suggest wave assignments",
)
async def suggest_waves(
    project_ref: str,
    db: Session = Depends(get_session),
    service: MigrationMapService = Depends(get_map_service),
) -> WaveSuggestionsResult:
    """Compute suggested wave assignments based on dependencies."""
    project = _get_project_or_404(db, project_ref)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return service.suggest_waves(project.id)


@router.put(
    "/{project_ref}/map/packages/{package_id}/wave",
    response_model=dict,
    summary="Assign wave to package",
)
async def assign_wave(
    project_ref: str,
    package_id: uuid.UUID,
    wave: int = Query(..., ge=1, description="Wave number"),
    db: Session = Depends(get_session),
    service: MigrationMapService = Depends(get_map_service),
) -> dict:
    """Manually assign a wave to a package."""
    project = _get_project_or_404(db, project_ref)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    success = service.assign_wave(package_id, wave)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Package not found or not in a cluster",
        )
    
    db.commit()
    return {"success": True, "wave": wave}
