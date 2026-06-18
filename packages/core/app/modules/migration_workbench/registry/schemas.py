"""Pydantic schemas for Package Registry API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Package schemas
# -----------------------------------------------------------------------------


class PackageBase(BaseModel):
    """Base fields for a package."""
    
    package_name: str = Field(..., description="Package name (e.g., ETL_Sales_Daily.dtsx)")
    package_path: str | None = Field(None, description="Original file path")
    domain: str | None = Field(None, description="Business domain (Sales, Finance, etc.)")
    complexity: str = Field("medium", description="Complexity: low, medium, high, critical")


class PackageCreate(PackageBase):
    """Create a new package registration."""
    
    artifact_id: uuid.UUID | None = Field(
        None, 
        description="Link to uploaded artifact"
    )


class PackageUpdate(BaseModel):
    """Update package metadata."""
    
    domain: str | None = None
    complexity: str | None = None
    status: str | None = None


class PackageView(PackageBase):
    """Package response."""
    
    id: uuid.UUID
    project_id: uuid.UUID
    artifact_id: uuid.UUID | None = None
    status: str
    pending_feedback_count: int = 0
    blocking_feedback_count: int = 0
    analyzed_at: datetime | None = None
    migrated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class PackageListResponse(BaseModel):
    """Paginated package list."""
    
    items: list[PackageView]
    total: int
    page: int = 1
    page_size: int = 50


# -----------------------------------------------------------------------------
# Bulk import schemas
# -----------------------------------------------------------------------------


class BulkPackageItem(BaseModel):
    """Single item in bulk import."""
    
    package_name: str
    package_path: str | None = None
    domain: str | None = None
    complexity: str = "medium"


class BulkImportRequest(BaseModel):
    """Bulk import request."""
    
    packages: list[BulkPackageItem] = Field(
        ..., 
        min_length=1,
        description="List of packages to import"
    )
    default_domain: str | None = Field(
        None,
        description="Default domain if not specified per package"
    )


class BulkImportResult(BaseModel):
    """Result of bulk import."""
    
    imported: int
    skipped: int
    errors: list[str] = []
    package_ids: list[uuid.UUID] = []


# -----------------------------------------------------------------------------
# Statistics schemas
# -----------------------------------------------------------------------------


class RegistryStats(BaseModel):
    """Package registry statistics."""
    
    total_packages: int = 0
    by_status: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    by_complexity: dict[str, int] = {}
    analyzed_count: int = 0
    migrated_count: int = 0
    needing_feedback_count: int = 0
