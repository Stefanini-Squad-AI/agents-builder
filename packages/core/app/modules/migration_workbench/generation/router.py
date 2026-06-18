"""API router for code generation endpoints."""

from __future__ import annotations

import io
import uuid
import zipfile
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.projects import Project
from app.modules.migration_workbench.analysis.data_pattern_classifier import (
    DataPatternClassifier,
    PackageDesignAnalysis,
)
from app.modules.migration_workbench.generation.schemas import (
    GenerationPreview,
    GenerationRequest,
    GenerationResult,
)
from app.modules.migration_workbench.generation.service import GenerationService
from app.modules.migration_workbench.models import ETLPackage

router = APIRouter(prefix="/{project_ref}/generation", tags=["generation"])


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


# ---------------------------------------------------------------------------


@router.get("/packages/{package_id}/preview")
async def preview_generation(
    package_id: uuid.UUID,
    project: Annotated[Project, Depends(_get_project_or_404)],
    session: Annotated[Session, Depends(get_session)],
) -> GenerationPreview:
    """Preview what would be generated (runs backward analysis only)."""
    _check_package_in_project(session, package_id, project)
    
    service = GenerationService(session)
    try:
        return service.preview(package_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/packages/{package_id}/generate")
async def generate_package(
    package_id: uuid.UUID,
    project: Annotated[Project, Depends(_get_project_or_404)],
    session: Annotated[Session, Depends(get_session)],
    request: GenerationRequest | None = None,
) -> GenerationResult:
    """Generate all notebook artifacts for a package."""
    _check_package_in_project(session, package_id, project)
    
    service = GenerationService(session)
    options = request.options if request else None
    try:
        result = service.generate(package_id, options)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    session.commit()
    return result


@router.post("/packages/{package_id}/download")
async def download_bundle(
    package_id: uuid.UUID,
    project: Annotated[Project, Depends(_get_project_or_404)],
    session: Annotated[Session, Depends(get_session)],
    request: GenerationRequest | None = None,
) -> StreamingResponse:
    """Generate and return a ZIP bundle of all artifacts."""
    _check_package_in_project(session, package_id, project)
    
    service = GenerationService(session)
    options = request.options if request else None
    try:
        result = service.generate(package_id, options)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    session.commit()
    
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for artifact in result.artifacts:
            zf.writestr(artifact.relative_path, artifact.content)
    buf.seek(0)
    
    safe_name = "".join(
        c if c.isalnum() or c in "._-" else "_" for c in result.package_name
    )
    
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_bundle.zip"',
        },
    )


@router.get("/packages/{package_id}/design")
async def get_design_guidance(
    package_id: uuid.UUID,
    project: Annotated[Project, Depends(_get_project_or_404)],
    session: Annotated[Session, Depends(get_session)],
) -> PackageDesignAnalysis:
    """Analyze package to provide design guidance before generation.
    
    Returns per-task pattern classification, Medallion layer assignments,
    and performance recommendations. Read-only analysis - no input required.
    """
    package = _check_package_in_project(session, package_id, project)
    
    # Use the generation service to get backward analysis results
    service = GenerationService(session)
    try:
        preview = service.preview(package_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Classify all tasks
    classifier = DataPatternClassifier()
    analysis = classifier.analyze_package(
        package_name=preview.package_name,
        tasks=preview.analysis.tasks,
    )
    
    return analysis
