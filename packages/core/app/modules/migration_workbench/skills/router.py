"""API router for skills endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.modules.migration_workbench.skills.skill_loader import (
    SkillLoader,
    SkillSummary,
    SkillDetail,
    skill_to_summary,
    skill_to_detail,
)

router = APIRouter(prefix="/skills", tags=["skills"])

# Singleton loader instance
_loader = SkillLoader()


@router.get("")
async def list_skills() -> list[SkillSummary]:
    """List all available pre-built skills."""
    skills = _loader.list_skills()
    return [skill_to_summary(s) for s in skills]


@router.get("/{skill_id}")
async def get_skill(skill_id: str) -> SkillDetail:
    """Get detailed information about a specific skill."""
    skill = _loader.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill_to_detail(skill)
