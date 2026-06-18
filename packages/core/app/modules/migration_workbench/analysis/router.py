"""Analysis API router.

Endpoints for triggering and retrieving ETL package analysis.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.modules.migration_workbench.analysis.service import AnalysisService


router = APIRouter(prefix="/analysis", tags=["analysis"])


# -----------------------------------------------------------------------------
# Request/Response Models
# -----------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    """Request to analyze a package."""
    
    package_id: uuid.UUID


class BulkAnalyzeRequest(BaseModel):
    """Request to analyze multiple packages."""
    
    limit: int = Field(100, ge=1, le=500)


class AnalysisStatusResponse(BaseModel):
    """Analysis status response."""
    
    package_id: str
    package_name: str
    status: str
    analyzed_at: str | None = None
    error: str | None = None
    complexity: str | None = None
    domain: str | None = None
    estimated_effort: str | None = None
    blockers_count: int = 0
    auto_resolved_count: int = 0


class ProjectAnalysisSummary(BaseModel):
    """Project-level analysis summary."""
    
    total_packages: int
    by_status: dict[str, int]
    by_complexity: dict[str, int]
    total_blockers: int
    auto_resolved_blockers: int
    pending_blockers: int
    analysis_progress: float


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/packages/{project_slug}/analyze",
    summary="Analyze a package",
    description="Queue a package for analysis",
)
def analyze_package(
    project_slug: str,
    request: AnalyzeRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Queue a package for analysis.
    
    Args:
        project_slug: Project slug
        request: Analysis request with package ID
        session: Database session
        
    Returns:
        Status of the queue operation
    """
    service = AnalysisService(session)
    
    queued = service.queue_analysis(request.package_id)
    
    if not queued:
        return {
            "status": "skipped",
            "message": "Package is already analyzed or analyzing",
        }
    
    return {
        "status": "queued",
        "package_id": str(request.package_id),
    }


@router.post(
    "/packages/{project_slug}/analyze-bulk",
    summary="Bulk analyze packages",
    description="Queue multiple packages for analysis",
)
def analyze_packages_bulk(
    project_slug: str,
    request: BulkAnalyzeRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Queue multiple packages for analysis.
    
    Args:
        project_slug: Project slug
        request: Bulk analysis request
        session: Database session
        
    Returns:
        Number of packages queued
    """
    # Get project ID from slug
    from app.domain.projects import Project
    from sqlalchemy import select
    
    project = session.execute(
        select(Project).where(Project.slug == project_slug)
    ).scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    service = AnalysisService(session)
    count = service.queue_bulk_analysis(project.id, limit=request.limit)
    
    return {
        "status": "queued",
        "count": count,
    }


@router.get(
    "/packages/{project_slug}/{package_id}/status",
    response_model=AnalysisStatusResponse,
    summary="Get analysis status",
)
def get_analysis_status(
    project_slug: str,
    package_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> AnalysisStatusResponse:
    """Get analysis status for a package.
    
    Args:
        project_slug: Project slug
        package_id: Package ID
        session: Database session
        
    Returns:
        Analysis status
    """
    service = AnalysisService(session)
    result = service.get_analysis_status(package_id)
    
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Package not found")
    
    return AnalysisStatusResponse(**result)


@router.get(
    "/packages/{project_slug}/{package_id}/results",
    summary="Get analysis results",
)
def get_analysis_results(
    project_slug: str,
    package_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get full analysis results for a package.
    
    Args:
        project_slug: Project slug
        package_id: Package ID
        session: Database session
        
    Returns:
        Full analysis results
    """
    service = AnalysisService(session)
    results = service.get_analysis_results(package_id)
    
    if not results:
        raise HTTPException(
            status_code=404,
            detail="Analysis results not found (package may not be analyzed yet)",
        )
    
    return results


@router.get(
    "/projects/{project_slug}/summary",
    response_model=ProjectAnalysisSummary,
    summary="Get project analysis summary",
)
def get_project_summary(
    project_slug: str,
    session: Session = Depends(get_session),
) -> ProjectAnalysisSummary:
    """Get analysis summary for a project.
    
    Args:
        project_slug: Project slug
        session: Database session
        
    Returns:
        Project-level analysis summary
    """
    from app.domain.projects import Project
    from sqlalchemy import select
    
    project = session.execute(
        select(Project).where(Project.slug == project_slug)
    ).scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    service = AnalysisService(session)
    summary = service.get_project_analysis_summary(project.id)
    
    return ProjectAnalysisSummary(**summary)


@router.post(
    "/packages/{project_slug}/{package_id}/retry",
    summary="Retry failed analysis",
)
def retry_analysis(
    project_slug: str,
    package_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Retry analysis for a failed package.
    
    Args:
        project_slug: Project slug
        package_id: Package ID
        session: Database session
        
    Returns:
        Status of the retry operation
    """
    service = AnalysisService(session)
    retried = service.retry_failed_analysis(package_id)
    
    if not retried:
        raise HTTPException(
            status_code=400,
            detail="Package is not in failed state",
        )
    
    return {
        "status": "queued",
        "package_id": str(package_id),
    }


@router.get(
    "/projects/{project_slug}/blockers",
    summary="Get blockers needing decisions",
)
def get_pending_blockers(
    project_slug: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get all blockers that need decisions.
    
    Args:
        project_slug: Project slug
        session: Database session
        
    Returns:
        List of blockers needing decisions
    """
    from app.domain.projects import Project
    from sqlalchemy import select
    
    project = session.execute(
        select(Project).where(Project.slug == project_slug)
    ).scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    service = AnalysisService(session)
    blockers = service.get_blockers_needing_decisions(project.id)
    
    return {
        "count": len(blockers),
        "blockers": blockers,
    }
