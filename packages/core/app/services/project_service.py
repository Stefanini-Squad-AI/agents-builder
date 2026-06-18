"""Project service for CLI and API operations."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

import app.db
from app.domain.backlog import Card, Phase
from app.domain.projects import Project, ProjectQaAnswer
from app.domain.skills import Skill
from app.enums import LlmProvider, ProjectStatus, CardTemplate, Grouping


class ProjectSummary:
    """Simplified project data structure for CLI operations."""
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class ProjectService:
    """Service for project CRUD operations and management."""

    def __init__(self) -> None:
        """Initialize the project service."""
        # For CLI purposes, we'll use a default tenant and user
        # In a real multi-tenant system, these would come from authentication
        self.default_tenant_id = uuid.uuid4()  # Placeholder
        self.default_user_id = uuid.uuid4()     # Placeholder

    def list_projects(self) -> list[ProjectSummary]:
        """List all projects with basic statistics.
        
        Returns:
            List of project summaries ordered by creation date (newest first)
        """
        with app.db.session_scope() as session:
            # Query projects with card and skill counts
            query = (
                select(
                    Project.id,
                    Project.slug,
                    Project.name,
                    Project.objective,
                    Project.created_at,
                    Project.updated_at,
                    func.count(Card.id).label('card_count'),
                    func.count(Skill.id).label('skill_count')
                )
                .select_from(Project)
                .outerjoin(Phase, Phase.project_id == Project.id)
                .outerjoin(Card, Card.phase_id == Phase.id)
                .outerjoin(Skill, Skill.project_id == Project.id)
                .group_by(Project.id, Project.slug, Project.name, Project.objective, Project.created_at, Project.updated_at)
                .order_by(Project.created_at.desc())
            )
            
            results = session.execute(query).all()
            
            projects = []
            for row in results:
                project_summary = ProjectSummary(
                    id=row.id,
                    slug=row.slug,
                    name=row.name,
                    objective=row.objective,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    card_count=row.card_count or 0,
                    skill_count=row.skill_count or 0
                )
                projects.append(project_summary)
            
            return projects

    def get_project_by_slug(self, slug: str) -> ProjectSummary | None:
        """Get project by slug with detailed information.
        
        Args:
            slug: Project slug
            
        Returns:
            Project summary with statistics or None if not found
        """
        with app.db.session_scope() as session:
            # Load project with all relationships for detailed view
            query = select(Project).where(
                Project.slug == slug
            ).options(
                selectinload(Project.phases).selectinload(Phase.cards),
                selectinload(Project.skills),
                selectinload(Project.qa_answers)
            )
            
            project = session.execute(query).scalar_one_or_none()
            if not project:
                return None
            
            # Add statistics
            total_cards = sum(len(phase.cards) for phase in project.phases)
            completed_cards = sum(
                len([card for card in phase.cards if card.status == "done"]) 
                for phase in project.phases
            )
            
            project_summary = ProjectSummary(
                id=project.id,
                slug=project.slug,
                name=project.name,
                objective=project.objective,
                context_md=project.context_md,
                card_code_prefix=project.card_code_prefix,
                llm_provider=project.llm_provider,
                llm_model=project.llm_model,
                llm_temperature=project.llm_temperature,
                created_at=project.created_at,
                updated_at=project.updated_at,
                card_count=total_cards,
                skill_count=len(project.skills),
                phase_count=len(project.phases),
                qa_answers_count=len([qa for qa in project.qa_answers if qa.answer_md]),
                completion_percentage=((completed_cards / total_cards * 100) if total_cards > 0 else 0)
            )
            
            return project_summary

    def create_project(
        self,
        name: str,
        slug: str,
        objective: str,
        card_code_prefix: str,
        llm_provider: LlmProvider | str | None = None,
        llm_model: str | None = None,
        llm_temperature: float | None = None,
        context_md: str | None = None
    ) -> ProjectSummary:
        """Create a new project.
        
        Args:
            name: Project name
            slug: Project slug (must be unique)
            objective: Project objective description
            card_code_prefix: Prefix for card codes (e.g., "PROJ")
            llm_provider: LLM provider for AI generation
            llm_model: LLM model name
            llm_temperature: LLM temperature setting
            context_md: Optional project context markdown
            
        Returns:
            Created project summary
            
        Raises:
            ValueError: If slug already exists or validation fails
        """
        # Validate inputs
        if not slug or not self._is_valid_slug(slug):
            raise ValueError(f"Invalid slug: {slug}")
        
        if not card_code_prefix or not self._is_valid_code_prefix(card_code_prefix):
            raise ValueError(f"Invalid card code prefix: {card_code_prefix}")
        
        with app.db.session_scope() as session:
            # Check if slug already exists
            existing = session.execute(
                select(Project).where(Project.slug == slug)
            ).scalar_one_or_none()
            
            if existing:
                raise ValueError(f"Project with slug '{slug}' already exists")
            
            # For CLI operations, we need to get or create a default tenant/user
            # This is a simplified approach - in production you'd get these from auth context
            tenant_id, user_id = self._get_or_create_default_identity(session)
            
            # Create project with defaults
            project = Project(
                tenant_id=tenant_id,
                owner_user_id=user_id,
                name=name,
                slug=slug,
                objective=objective,
                context_md=context_md,
                card_code_prefix=card_code_prefix,
                card_template=CardTemplate.PHASE_VLI.value,
                grouping=Grouping.PHASE.value,
                status=ProjectStatus.DRAFT.value,
                llm_provider=str(llm_provider) if llm_provider else LlmProvider.ANTHROPIC.value,
                llm_model=llm_model or "claude-3-5-sonnet-20241022",
                llm_temperature=llm_temperature or 0.7,
                llm_enable_reasoning=False
            )
            
            session.add(project)
            session.commit()
            session.refresh(project)
            
            return ProjectSummary(
                id=project.id,
                slug=project.slug,
                name=project.name,
                objective=project.objective,
                context_md=project.context_md,
                card_code_prefix=project.card_code_prefix,
                llm_provider=project.llm_provider,
                llm_model=project.llm_model,
                llm_temperature=float(project.llm_temperature),
                created_at=project.created_at,
                updated_at=project.updated_at,
                card_count=0,
                skill_count=0,
                phase_count=0,
                qa_answers_count=0,
                completion_percentage=0
            )

    def update_project(
        self,
        slug: str,
        *,
        name: str | None = None,
        objective: str | None = None,
        card_code_prefix: str | None = None,
        llm_provider: LlmProvider | str | None = None,
        llm_model: str | None = None,
        llm_temperature: float | None = None,
        context_md: str | None = None
    ) -> ProjectSummary | None:
        """Update project settings.
        
        Args:
            slug: Project slug
            name: New project name (optional)
            objective: New objective (optional)
            card_code_prefix: New card prefix (optional)
            llm_provider: New LLM provider (optional)
            llm_model: New LLM model (optional)
            llm_temperature: New LLM temperature (optional)
            context_md: New context markdown (optional)
            
        Returns:
            Updated project summary or None if not found
        """
        with app.db.session_scope() as session:
            project = session.execute(
                select(Project).where(Project.slug == slug)
            ).scalar_one_or_none()
            
            if not project:
                return None
            
            # Update fields if provided
            if name is not None:
                project.name = name
            if objective is not None:
                project.objective = objective
            if card_code_prefix is not None:
                if not self._is_valid_code_prefix(card_code_prefix):
                    raise ValueError(f"Invalid card code prefix: {card_code_prefix}")
                project.card_code_prefix = card_code_prefix
            if llm_provider is not None:
                project.llm_provider = str(llm_provider)
            if llm_model is not None:
                project.llm_model = llm_model
            if llm_temperature is not None:
                project.llm_temperature = llm_temperature
            if context_md is not None:
                project.context_md = context_md
            
            session.commit()
            session.refresh(project)
            
            return ProjectSummary(
                id=project.id,
                slug=project.slug,
                name=project.name,
                objective=project.objective,
                context_md=project.context_md,
                card_code_prefix=project.card_code_prefix,
                llm_provider=project.llm_provider,
                llm_model=project.llm_model,
                llm_temperature=float(project.llm_temperature),
                created_at=project.created_at,
                updated_at=project.updated_at
            )

    def delete_project(self, slug: str) -> bool:
        """Delete a project and all its data.
        
        Args:
            slug: Project slug
            
        Returns:
            True if project was deleted, False if not found
        """
        with app.db.session_scope() as session:
            project = session.execute(
                select(Project).where(Project.slug == slug)
            ).scalar_one_or_none()
            
            if not project:
                return False
            
            session.delete(project)
            session.commit()
            
            return True

    def get_project_summary(self, slug: str) -> dict[str, Any] | None:
        """Get comprehensive project summary for CLI display.
        
        Args:
            slug: Project slug
            
        Returns:
            Dictionary with project summary data or None if not found
        """
        project_view = self.get_project_by_slug(slug)
        if not project_view:
            return None
        
        with app.db.session_scope() as session:
            project_query = select(Project).where(
                Project.slug == slug
            ).options(
                selectinload(Project.phases).selectinload(Phase.cards),
                selectinload(Project.skills),
                selectinload(Project.qa_answers),
                selectinload(Project.tech_choices)
            )
            
            project = session.execute(project_query).scalar_one_or_none()
            
            # Build summary data
            phases_summary = []
            for phase in sorted(project.phases, key=lambda p: p.order_no):
                phase_cards = phase.cards
                completed_cards = [c for c in phase_cards if c.status == "done"]
                
                phases_summary.append({
                    "code": phase.code,
                    "name": phase.name,
                    "card_count": len(phase_cards),
                    "completed_count": len(completed_cards),
                    "completion_percentage": (
                        len(completed_cards) / len(phase_cards) * 100 
                        if phase_cards else 0
                    )
                })
            
            # Q&A summary
            qa_summary = {
                "total_questions": 7,  # Standard Q&A questions
                "answered_questions": len([qa for qa in project.qa_answers if qa.answer_md]),
                "completion_percentage": (
                    len([qa for qa in project.qa_answers if qa.answer_md]) / 7 * 100
                )
            }
            
            # Tech choices summary
            tech_summary = {
                "total_dimensions": 13,  # Standard tech dimensions
                "chosen_dimensions": len(project.tech_choices),
                "completion_percentage": (
                    len(project.tech_choices) / 13 * 100 if project.tech_choices else 0
                )
            }
            
            return {
                "project": project_view,
                "phases": phases_summary,
                "qa": qa_summary,
                "tech": tech_summary,
                "skills": {
                    "total_count": len(project.skills),
                    "by_kind": self._group_skills_by_kind(project.skills)
                }
            }

    def _get_or_create_default_identity(self, session) -> tuple[uuid.UUID, uuid.UUID]:
        """Get or create default tenant and user for CLI operations.
        
        Args:
            session: Database session
            
        Returns:
            Tuple of (tenant_id, user_id)
        """
        # Import here to avoid circular imports
        from app.domain.identity import Tenant, User
        
        # Check for existing default tenant
        default_tenant = session.execute(
            select(Tenant).where(Tenant.slug == "default")
        ).scalar_one_or_none()
        
        if not default_tenant:
            # Create default tenant for CLI operations
            default_tenant = Tenant(
                slug="default",
                name="Default Tenant",
                is_active=True
            )
            session.add(default_tenant)
            session.flush()  # Get the ID
        
        # Check for existing default user
        default_user = session.execute(
            select(User).where(User.email == "cli@localhost")
        ).scalar_one_or_none()
        
        if not default_user:
            # Create default user for CLI operations
            default_user = User(
                tenant_id=default_tenant.id,
                email="cli@localhost",
                full_name="CLI User",
                is_active=True
            )
            session.add(default_user)
            session.flush()  # Get the ID
        
        return default_tenant.id, default_user.id

    def _is_valid_slug(self, slug: str) -> bool:
        """Validate project slug format."""
        import re
        return bool(re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', slug))

    def _is_valid_code_prefix(self, prefix: str) -> bool:
        """Validate card code prefix format."""
        import re
        return bool(re.match(r'^[A-Z][A-Z0-9-]*$', prefix))

    def _group_skills_by_kind(self, skills: list[Skill]) -> dict[str, int]:
        """Group skills by kind for summary display."""
        groups = {}
        for skill in skills:
            kind = skill.kind
            groups[kind] = groups.get(kind, 0) + 1
        return groups