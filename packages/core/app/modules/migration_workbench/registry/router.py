"""Package Registry API routes.

Endpoints for managing ETL packages in a migration project:
- List/create/update packages
- Bulk import
- Statistics
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.projects import Project
from app.modules.migration_workbench.models import ETLPackage
from app.modules.migration_workbench.registry.schemas import (
    BulkImportRequest,
    BulkImportResult,
    PackageCreate,
    PackageListResponse,
    PackageUpdate,
    PackageView,
    RegistryStats,
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


@router.get("/{project_ref}/packages", response_model=PackageListResponse)
async def list_packages(
    project_ref: str,
    status: str | None = Query(None, description="Filter by status"),
    domain: str | None = Query(None, description="Filter by domain"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> PackageListResponse:
    """List all packages in a project's registry."""
    project = _get_project_or_404(session, project_ref)
    
    stmt = select(ETLPackage).where(ETLPackage.project_id == project.id)
    
    if status:
        stmt = stmt.where(ETLPackage.status == status)
    if domain:
        stmt = stmt.where(ETLPackage.domain == domain)
    
    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.scalar(count_stmt) or 0
    
    # Paginate
    stmt = stmt.order_by(ETLPackage.package_name)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    
    packages = list(session.scalars(stmt))
    
    return PackageListResponse(
        items=[PackageView.model_validate(p) for p in packages],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{project_ref}/packages", response_model=PackageView, status_code=201)
async def create_package(
    project_ref: str,
    body: PackageCreate,
    session: Session = Depends(get_session),
) -> PackageView:
    """Register a new package in the registry."""
    project = _get_project_or_404(session, project_ref)
    
    # Check for duplicate
    existing = session.scalar(
        select(ETLPackage).where(
            ETLPackage.project_id == project.id,
            ETLPackage.package_name == body.package_name,
        )
    )
    if existing:
        raise HTTPException(
            status_code=409, 
            detail=f"Package '{body.package_name}' already registered"
        )
    
    package = ETLPackage(
        project_id=project.id,
        package_name=body.package_name,
        package_path=body.package_path,
        domain=body.domain,
        complexity=body.complexity,
        artifact_id=body.artifact_id,
    )
    session.add(package)
    session.commit()
    session.refresh(package)
    
    return PackageView.model_validate(package)


@router.get("/{project_ref}/packages/{package_id}", response_model=PackageView)
async def get_package(
    project_ref: str,
    package_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> PackageView:
    """Get a specific package by ID."""
    project = _get_project_or_404(session, project_ref)
    
    package = session.scalar(
        select(ETLPackage).where(
            ETLPackage.project_id == project.id,
            ETLPackage.id == package_id,
        )
    )
    if not package:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    
    return PackageView.model_validate(package)


@router.patch("/{project_ref}/packages/{package_id}", response_model=PackageView)
async def update_package(
    project_ref: str,
    package_id: uuid.UUID,
    body: PackageUpdate,
    session: Session = Depends(get_session),
) -> PackageView:
    """Update package metadata."""
    project = _get_project_or_404(session, project_ref)
    
    package = session.scalar(
        select(ETLPackage).where(
            ETLPackage.project_id == project.id,
            ETLPackage.id == package_id,
        )
    )
    if not package:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    
    if body.domain is not None:
        package.domain = body.domain
    if body.complexity is not None:
        package.complexity = body.complexity
    if body.status is not None:
        package.status = body.status
    
    session.commit()
    session.refresh(package)
    
    return PackageView.model_validate(package)


@router.delete("/{project_ref}/packages/{package_id}", status_code=204)
async def delete_package(
    project_ref: str,
    package_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete a package from the registry."""
    project = _get_project_or_404(session, project_ref)
    
    package = session.scalar(
        select(ETLPackage).where(
            ETLPackage.project_id == project.id,
            ETLPackage.id == package_id,
        )
    )
    if not package:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    
    session.delete(package)
    session.commit()


@router.post("/{project_ref}/packages/bulk", response_model=BulkImportResult)
async def bulk_import_packages(
    project_ref: str,
    body: BulkImportRequest,
    session: Session = Depends(get_session),
) -> BulkImportResult:
    """Bulk import packages into the registry.
    
    Skips packages that already exist (by name).
    """
    project = _get_project_or_404(session, project_ref)
    
    # Get existing package names
    existing_names = set(session.scalars(
        select(ETLPackage.package_name).where(ETLPackage.project_id == project.id)
    ))
    
    imported = 0
    skipped = 0
    errors: list[str] = []
    package_ids: list[uuid.UUID] = []
    
    for item in body.packages:
        if item.package_name in existing_names:
            skipped += 1
            continue
        
        try:
            package = ETLPackage(
                project_id=project.id,
                package_name=item.package_name,
                package_path=item.package_path,
                domain=item.domain or body.default_domain,
                complexity=item.complexity,
            )
            session.add(package)
            session.flush()  # Get the ID
            package_ids.append(package.id)
            existing_names.add(item.package_name)
            imported += 1
        except Exception as e:
            errors.append(f"{item.package_name}: {str(e)}")
    
    session.commit()
    
    return BulkImportResult(
        imported=imported,
        skipped=skipped,
        errors=errors,
        package_ids=package_ids,
    )


@router.get("/{project_ref}/packages/stats", response_model=RegistryStats)
async def get_registry_stats(
    project_ref: str,
    session: Session = Depends(get_session),
) -> RegistryStats:
    """Get statistics for the package registry."""
    project = _get_project_or_404(session, project_ref)
    
    # Total count
    total = session.scalar(
        select(func.count()).where(ETLPackage.project_id == project.id)
    ) or 0
    
    # By status
    status_rows = session.execute(
        select(ETLPackage.status, func.count())
        .where(ETLPackage.project_id == project.id)
        .group_by(ETLPackage.status)
    ).all()
    by_status = {row[0]: row[1] for row in status_rows}
    
    # By domain
    domain_rows = session.execute(
        select(ETLPackage.domain, func.count())
        .where(ETLPackage.project_id == project.id)
        .group_by(ETLPackage.domain)
    ).all()
    by_domain = {(row[0] or "unassigned"): row[1] for row in domain_rows}
    
    # By complexity
    complexity_rows = session.execute(
        select(ETLPackage.complexity, func.count())
        .where(ETLPackage.project_id == project.id)
        .group_by(ETLPackage.complexity)
    ).all()
    by_complexity = {row[0]: row[1] for row in complexity_rows}
    
    # Computed counts
    analyzed = sum(
        by_status.get(s, 0) 
        for s in ("analyzed", "ready", "generating", "generated", "validating", "validated", "migrated", "verified")
    )
    migrated = by_status.get("migrated", 0) + by_status.get("verified", 0)
    needing_feedback = by_status.get("needs_feedback", 0)
    
    return RegistryStats(
        total_packages=total,
        by_status=by_status,
        by_domain=by_domain,
        by_complexity=by_complexity,
        analyzed_count=analyzed,
        migrated_count=migrated,
        needing_feedback_count=needing_feedback,
    )
