"""Skill service for CLI and API operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.db
from app.domain.projects import Project
from app.domain.skills import Skill, SkillResource
from app.enums import SkillKind


class SkillSummary:
    """Simplified skill data structure for CLI operations."""
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class SkillService:
    """Service for skill CRUD operations and management."""

    def __init__(self) -> None:
        """Initialize the skill service."""
        pass

    def list_project_skills(self, project_slug: str) -> list[SkillSummary]:
        """List all skills in a project.
        
        Args:
            project_slug: Project slug
            
        Returns:
            List of skill summaries ordered by name
        """
        with app.db.session_scope() as session:
            # Get project
            project = session.execute(
                select(Project).where(Project.slug == project_slug)
            ).scalar_one_or_none()
            
            if not project:
                return []
            
            # Query skills with resource counts
            query = (
                select(Skill)
                .where(Skill.project_id == project.id)
                .options(selectinload(Skill.resources))
                .order_by(Skill.name)
            )
            
            skills = session.execute(query).scalars().all()
            
            skill_summaries = []
            for skill in skills:
                skill_summary = SkillSummary(
                    id=skill.id,
                    project_id=skill.project_id,
                    slug=skill.slug,
                    name=skill.name,
                    description=skill.description,
                    kind=skill.kind,
                    trigger_phrases=skill.trigger_phrases or [],
                    body_md=skill.body_md,
                    resource_count=len(skill.resources),
                    created_at=skill.created_at,
                    updated_at=skill.updated_at
                )
                skill_summaries.append(skill_summary)
            
            return skill_summaries

    def get_skill(self, project_slug: str, skill_slug: str) -> SkillSummary | None:
        """Get a specific skill by project and skill slug.
        
        Args:
            project_slug: Project slug
            skill_slug: Skill slug
            
        Returns:
            Skill summary or None if not found
        """
        with app.db.session_scope() as session:
            # Load skill with project and resources
            query = (
                select(Skill)
                .join(Project, Skill.project_id == Project.id)
                .where(Project.slug == project_slug, Skill.slug == skill_slug)
                .options(selectinload(Skill.resources))
            )
            
            skill = session.execute(query).scalar_one_or_none()
            if not skill:
                return None
            
            return SkillSummary(
                id=skill.id,
                project_id=skill.project_id,
                slug=skill.slug,
                name=skill.name,
                description=skill.description,
                kind=skill.kind,
                trigger_phrases=skill.trigger_phrases or [],
                body_md=skill.body_md,
                resource_count=len(skill.resources),
                resources=[
                    {
                        "id": res.id,
                        "filename": res.filename,
                        "language": res.language,
                        "content": res.content
                    }
                    for res in skill.resources
                ],
                created_at=skill.created_at,
                updated_at=skill.updated_at
            )

    def update_skill_body(self, project_slug: str, skill_slug: str, body_md: str) -> SkillSummary | None:
        """Update skill body content.
        
        Args:
            project_slug: Project slug
            skill_slug: Skill slug
            body_md: New body markdown content
            
        Returns:
            Updated skill summary or None if not found
        """
        with app.db.session_scope() as session:
            # Find skill
            query = (
                select(Skill)
                .join(Project, Skill.project_id == Project.id)
                .where(Project.slug == project_slug, Skill.slug == skill_slug)
            )
            
            skill = session.execute(query).scalar_one_or_none()
            if not skill:
                return None
            
            # Update body
            skill.body_md = body_md
            session.commit()
            session.refresh(skill)
            
            return SkillSummary(
                id=skill.id,
                project_id=skill.project_id,
                slug=skill.slug,
                name=skill.name,
                description=skill.description,
                kind=skill.kind,
                trigger_phrases=skill.trigger_phrases or [],
                body_md=skill.body_md,
                resource_count=0,  # We didn't load resources for update
                created_at=skill.created_at,
                updated_at=skill.updated_at
            )

    def render_skill_markdown(self, skill: SkillSummary) -> str:
        """Render skill as complete SKILL.md format.
        
        Args:
            skill: Skill summary with data
            
        Returns:
            Complete SKILL.md content with YAML frontmatter and body
        """
        lines = []
        
        # YAML frontmatter
        lines.append("---")
        lines.append(f"name: {skill.name}")
        lines.append(f"description: {skill.description}")
        lines.append(f"kind: {skill.kind}")
        
        if skill.trigger_phrases:
            lines.append("trigger_phrases:")
            for phrase in skill.trigger_phrases:
                # Escape quotes in YAML
                escaped_phrase = phrase.replace('"', '\\"')
                lines.append(f'  - "{escaped_phrase}"')
        
        lines.append("---")
        lines.append("")
        
        # Body content
        if skill.body_md and skill.body_md.strip():
            lines.append(skill.body_md)
        else:
            lines.append("_Skill content will be added during development._")
            lines.append("")
            lines.append("## Guidelines")
            lines.append("")
            lines.append("Add specific guidance for this skill here.")
            lines.append("")
            lines.append("## Resources")
            lines.append("")
            lines.append("List any useful resources, examples, or references.")
        
        return "\n".join(lines)

    def get_skills_statistics(self, project_slug: str) -> dict[str, Any]:
        """Get skill statistics for a project.
        
        Args:
            project_slug: Project slug
            
        Returns:
            Dictionary with skill statistics
        """
        skills = self.list_project_skills(project_slug)
        
        if not skills:
            return {
                "total_skills": 0,
                "by_kind": {},
                "with_content": 0,
                "with_resources": 0,
                "avg_trigger_phrases": 0
            }
        
        # Group by kind
        by_kind = {}
        with_content = 0
        with_resources = 0
        total_trigger_phrases = 0
        
        for skill in skills:
            # Count by kind
            kind = skill.kind
            by_kind[kind] = by_kind.get(kind, 0) + 1
            
            # Count with content
            if skill.body_md and skill.body_md.strip():
                with_content += 1
            
            # Count with resources
            if hasattr(skill, 'resource_count') and skill.resource_count > 0:
                with_resources += 1
            
            # Count trigger phrases
            total_trigger_phrases += len(skill.trigger_phrases)
        
        return {
            "total_skills": len(skills),
            "by_kind": by_kind,
            "with_content": with_content,
            "with_resources": with_resources,
            "avg_trigger_phrases": total_trigger_phrases / len(skills) if skills else 0,
            "completion_percentage": (with_content / len(skills) * 100) if skills else 0
        }