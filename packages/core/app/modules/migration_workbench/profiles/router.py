"""Technology Profiles API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.modules.migration_workbench.profiles.loader import (
    get_profile,
    list_profiles,
    get_all_profiles,
)
from app.modules.migration_workbench.profiles.schema import TechnologyProfile

router = APIRouter()


@router.get("/", response_model=list[str])
async def list_available_profiles() -> list[str]:
    """List all available technology profile slugs."""
    return list_profiles()


@router.get("/all", response_model=dict[str, TechnologyProfile])
async def get_all_available_profiles() -> dict[str, TechnologyProfile]:
    """Get all technology profiles."""
    return get_all_profiles()


@router.get("/{slug}", response_model=TechnologyProfile)
async def get_profile_by_slug(slug: str) -> TechnologyProfile:
    """Get a specific technology profile by slug.
    
    Args:
        slug: Technology identifier (e.g., "ssis", "airflow")
    """
    try:
        return get_profile(slug)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Technology profile '{slug}' not found"
        )
