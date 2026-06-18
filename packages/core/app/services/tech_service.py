"""Tech service for CLI and API operations."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

import app.db
from app.domain.projects import Project
from app.domain.tech import ProjectTechChoice, TechDimension, TechItem
from app.enums import TechChoiceRole, TechChoiceSource


@dataclass
class TechChoiceSummary:
    """Tech choice data structure for API/CLI operations."""
    id: uuid.UUID
    project_id: uuid.UUID
    dimension_id: uuid.UUID
    dimension_slug: str
    dimension_name: str
    tech_item_id: uuid.UUID | None
    item_slug: str | None
    item_name: str | None
    item_description: str | None
    role: str
    source: str
    accepted: bool
    llm_rationale: str | None
    llm_confidence: float | None
    notes: str | None
    order_no: int


@dataclass
class DimensionWithChoices:
    """Dimension with its items and project choices."""
    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    order_no: int
    items: list[dict[str, Any]]
    choices: list[TechChoiceSummary]


class TechService:
    """Service for tech panorama CRUD operations and management."""

    def list_dimensions(self) -> list[dict[str, Any]]:
        """List all available tech dimensions from the catalog.
        
        Returns:
            List of dimension dictionaries with items
        """
        with app.db.session_scope() as session:
            query = (
                select(TechDimension)
                .options(selectinload(TechDimension.items))
                .order_by(TechDimension.order_no)
            )
            
            dimensions = session.execute(query).scalars().all()
            
            return [
                {
                    "id": str(d.id),
                    "slug": d.slug,
                    "name": d.name,
                    "description": d.description,
                    "order_no": d.order_no,
                    "items": [
                        {
                            "id": str(item.id),
                            "slug": item.slug,
                            "name": item.name,
                            "description": item.description,
                            "tags": item.tags or [],
                            "is_custom": item.is_custom,
                        }
                        for item in sorted(d.items, key=lambda x: x.name)
                    ]
                }
                for d in dimensions
            ]

    def get_dimension(self, dimension_slug: str) -> dict[str, Any] | None:
        """Get a single dimension with its items.
        
        Args:
            dimension_slug: Dimension slug
            
        Returns:
            Dimension dict or None if not found
        """
        with app.db.session_scope() as session:
            dimension = session.execute(
                select(TechDimension)
                .options(selectinload(TechDimension.items))
                .where(TechDimension.slug == dimension_slug)
            ).scalar_one_or_none()
            
            if not dimension:
                return None
            
            return {
                "id": str(dimension.id),
                "slug": dimension.slug,
                "name": dimension.name,
                "description": dimension.description,
                "order_no": dimension.order_no,
                "items": [
                    {
                        "id": str(item.id),
                        "slug": item.slug,
                        "name": item.name,
                        "description": item.description,
                        "tags": item.tags or [],
                        "is_custom": item.is_custom,
                    }
                    for item in sorted(dimension.items, key=lambda x: x.name)
                ]
            }

    def list_project_tech_choices(self, project_slug: str) -> list[TechChoiceSummary]:
        """List all tech choices for a project.
        
        Args:
            project_slug: Project slug
            
        Returns:
            List of tech choice summaries
        """
        with app.db.session_scope() as session:
            project = session.execute(
                select(Project).where(Project.slug == project_slug)
            ).scalar_one_or_none()
            
            if not project:
                return []
            
            query = (
                select(ProjectTechChoice)
                .options(
                    selectinload(ProjectTechChoice.dimension),
                    selectinload(ProjectTechChoice.tech_item),
                )
                .where(ProjectTechChoice.project_id == project.id)
                .order_by(ProjectTechChoice.order_no)
            )
            
            choices = session.execute(query).scalars().all()
            
            return [
                TechChoiceSummary(
                    id=c.id,
                    project_id=c.project_id,
                    dimension_id=c.dimension_id,
                    dimension_slug=c.dimension.slug,
                    dimension_name=c.dimension.name,
                    tech_item_id=c.tech_item_id,
                    item_slug=c.tech_item.slug if c.tech_item else None,
                    item_name=c.tech_item.name if c.tech_item else None,
                    item_description=c.tech_item.description if c.tech_item else None,
                    role=c.role,
                    source=c.source,
                    accepted=c.accepted,
                    llm_rationale=c.llm_rationale,
                    llm_confidence=float(c.llm_confidence) if c.llm_confidence else None,
                    notes=c.notes,
                    order_no=c.order_no,
                )
                for c in choices
            ]

    def get_dimension_choices(
        self, project_slug: str, dimension_slug: str
    ) -> list[TechChoiceSummary]:
        """Get tech choices for a specific dimension in a project."""
        choices = self.list_project_tech_choices(project_slug)
        return [c for c in choices if c.dimension_slug == dimension_slug]

    def list_dimensions_with_choices(
        self, project_slug: str
    ) -> list[DimensionWithChoices]:
        """List all dimensions with their items and project's choices.
        
        Args:
            project_slug: Project slug
            
        Returns:
            List of dimensions with choices attached
        """
        dimensions = self.list_dimensions()
        choices = self.list_project_tech_choices(project_slug)
        
        # Group choices by dimension
        choices_by_dim: dict[str, list[TechChoiceSummary]] = {}
        for c in choices:
            choices_by_dim.setdefault(c.dimension_slug, []).append(c)
        
        return [
            DimensionWithChoices(
                id=uuid.UUID(d["id"]),
                slug=d["slug"],
                name=d["name"],
                description=d["description"],
                order_no=d["order_no"],
                items=d["items"],
                choices=choices_by_dim.get(d["slug"], []),
            )
            for d in dimensions
        ]

    def set_tech_choice(
        self,
        project_slug: str,
        dimension_slug: str,
        item_slug: str,
        role: TechChoiceRole,
        notes: str | None = None,
    ) -> TechChoiceSummary | None:
        """Set a tech choice for a project from catalog.
        
        Args:
            project_slug: Project slug
            dimension_slug: Dimension slug
            item_slug: Tech item slug from catalog
            role: Role of this technology choice
            notes: Optional notes
            
        Returns:
            Created/updated tech choice summary
        """
        with app.db.session_scope() as session:
            # Get project
            project = session.execute(
                select(Project).where(Project.slug == project_slug)
            ).scalar_one_or_none()
            if not project:
                return None
            
            # Get dimension
            dimension = session.execute(
                select(TechDimension).where(TechDimension.slug == dimension_slug)
            ).scalar_one_or_none()
            if not dimension:
                raise ValueError(f"Dimension '{dimension_slug}' not found")
            
            # Get tech item
            tech_item = session.execute(
                select(TechItem).where(
                    TechItem.slug == item_slug,
                    TechItem.dimension_id == dimension.id
                )
            ).scalar_one_or_none()
            if not tech_item:
                raise ValueError(
                    f"Tech item '{item_slug}' not found in dimension '{dimension_slug}'"
                )
            
            # Check for existing choice
            existing = session.execute(
                select(ProjectTechChoice).where(
                    ProjectTechChoice.project_id == project.id,
                    ProjectTechChoice.dimension_id == dimension.id,
                    ProjectTechChoice.tech_item_id == tech_item.id,
                )
            ).scalar_one_or_none()
            
            if existing:
                # Update existing
                existing.role = role.value
                existing.notes = notes
                session.commit()
                session.refresh(existing)
                choice = existing
            else:
                # Get next order_no
                max_order = session.execute(
                    select(func.max(ProjectTechChoice.order_no)).where(
                        ProjectTechChoice.project_id == project.id,
                        ProjectTechChoice.dimension_id == dimension.id,
                    )
                ).scalar() or 0
                
                choice = ProjectTechChoice(
                    project_id=project.id,
                    dimension_id=dimension.id,
                    tech_item_id=tech_item.id,
                    role=role.value,
                    source=TechChoiceSource.CATALOG.value,
                    accepted=True,
                    notes=notes,
                    order_no=max_order + 1,
                )
                session.add(choice)
                session.commit()
                session.refresh(choice)
            
            return TechChoiceSummary(
                id=choice.id,
                project_id=choice.project_id,
                dimension_id=choice.dimension_id,
                dimension_slug=dimension.slug,
                dimension_name=dimension.name,
                tech_item_id=choice.tech_item_id,
                item_slug=tech_item.slug,
                item_name=tech_item.name,
                item_description=tech_item.description,
                role=choice.role,
                source=choice.source,
                accepted=choice.accepted,
                llm_rationale=choice.llm_rationale,
                llm_confidence=float(choice.llm_confidence) if choice.llm_confidence else None,
                notes=choice.notes,
                order_no=choice.order_no,
            )

    def remove_tech_choice(
        self, project_slug: str, dimension_slug: str, item_slug: str
    ) -> bool:
        """Remove a tech choice from a project.
        
        Args:
            project_slug: Project slug
            dimension_slug: Dimension slug
            item_slug: Tech item slug
            
        Returns:
            True if removed, False if not found
        """
        with app.db.session_scope() as session:
            project = session.execute(
                select(Project).where(Project.slug == project_slug)
            ).scalar_one_or_none()
            if not project:
                return False
            
            dimension = session.execute(
                select(TechDimension).where(TechDimension.slug == dimension_slug)
            ).scalar_one_or_none()
            if not dimension:
                return False
            
            tech_item = session.execute(
                select(TechItem).where(
                    TechItem.slug == item_slug,
                    TechItem.dimension_id == dimension.id
                )
            ).scalar_one_or_none()
            if not tech_item:
                return False
            
            choice = session.execute(
                select(ProjectTechChoice).where(
                    ProjectTechChoice.project_id == project.id,
                    ProjectTechChoice.dimension_id == dimension.id,
                    ProjectTechChoice.tech_item_id == tech_item.id,
                )
            ).scalar_one_or_none()
            
            if not choice:
                return False
            
            session.delete(choice)
            session.commit()
            return True

    def mark_dimension_tbd(
        self, project_slug: str, dimension_slug: str, notes: str | None = None
    ) -> TechChoiceSummary | None:
        """Mark a dimension as TBD (to be determined).
        
        Creates a choice with role='tbd' and tech_item_id=NULL.
        
        Args:
            project_slug: Project slug
            dimension_slug: Dimension slug
            notes: Optional notes about why TBD
            
        Returns:
            Created tech choice summary
        """
        with app.db.session_scope() as session:
            project = session.execute(
                select(Project).where(Project.slug == project_slug)
            ).scalar_one_or_none()
            if not project:
                return None
            
            dimension = session.execute(
                select(TechDimension).where(TechDimension.slug == dimension_slug)
            ).scalar_one_or_none()
            if not dimension:
                raise ValueError(f"Dimension '{dimension_slug}' not found")
            
            # Check for existing TBD
            existing = session.execute(
                select(ProjectTechChoice).where(
                    ProjectTechChoice.project_id == project.id,
                    ProjectTechChoice.dimension_id == dimension.id,
                    ProjectTechChoice.role == TechChoiceRole.TBD.value,
                )
            ).scalar_one_or_none()
            
            if existing:
                existing.notes = notes
                session.commit()
                session.refresh(existing)
                choice = existing
            else:
                choice = ProjectTechChoice(
                    project_id=project.id,
                    dimension_id=dimension.id,
                    tech_item_id=None,  # TBD has no specific item
                    role=TechChoiceRole.TBD.value,
                    source=TechChoiceSource.CATALOG.value,
                    accepted=True,
                    notes=notes,
                    order_no=0,
                )
                session.add(choice)
                session.commit()
                session.refresh(choice)
            
            return TechChoiceSummary(
                id=choice.id,
                project_id=choice.project_id,
                dimension_id=choice.dimension_id,
                dimension_slug=dimension.slug,
                dimension_name=dimension.name,
                tech_item_id=None,
                item_slug=None,
                item_name="TBD",
                item_description=None,
                role=choice.role,
                source=choice.source,
                accepted=choice.accepted,
                llm_rationale=None,
                llm_confidence=None,
                notes=choice.notes,
                order_no=choice.order_no,
            )

    def clear_dimension_tbd(self, project_slug: str, dimension_slug: str) -> bool:
        """Remove TBD marking from a dimension.
        
        Args:
            project_slug: Project slug
            dimension_slug: Dimension slug
            
        Returns:
            True if removed, False if not found
        """
        with app.db.session_scope() as session:
            project = session.execute(
                select(Project).where(Project.slug == project_slug)
            ).scalar_one_or_none()
            if not project:
                return False
            
            dimension = session.execute(
                select(TechDimension).where(TechDimension.slug == dimension_slug)
            ).scalar_one_or_none()
            if not dimension:
                return False
            
            choice = session.execute(
                select(ProjectTechChoice).where(
                    ProjectTechChoice.project_id == project.id,
                    ProjectTechChoice.dimension_id == dimension.id,
                    ProjectTechChoice.role == TechChoiceRole.TBD.value,
                )
            ).scalar_one_or_none()
            
            if not choice:
                return False
            
            session.delete(choice)
            session.commit()
            return True

    def add_custom_item(
        self,
        project_slug: str,
        dimension_slug: str,
        name: str,
        role: TechChoiceRole,
        description: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
    ) -> TechChoiceSummary | None:
        """Add a custom tech item and select it for the project.
        
        Creates a new TechItem with is_custom=True, then adds a ProjectTechChoice.
        
        Args:
            project_slug: Project slug
            dimension_slug: Dimension slug
            name: Custom item name
            role: Role of this technology choice
            description: Optional description
            tags: Optional tags
            notes: Optional notes
            
        Returns:
            Created tech choice summary
        """
        with app.db.session_scope() as session:
            project = session.execute(
                select(Project).where(Project.slug == project_slug)
            ).scalar_one_or_none()
            if not project:
                return None
            
            dimension = session.execute(
                select(TechDimension).where(TechDimension.slug == dimension_slug)
            ).scalar_one_or_none()
            if not dimension:
                raise ValueError(f"Dimension '{dimension_slug}' not found")
            
            # Generate slug from name
            item_slug = self._slugify(name)
            
            # Check if slug exists in dimension
            existing_item = session.execute(
                select(TechItem).where(
                    TechItem.dimension_id == dimension.id,
                    TechItem.slug == item_slug,
                )
            ).scalar_one_or_none()
            
            if existing_item:
                # Use existing item
                tech_item = existing_item
            else:
                # Create new custom item
                tech_item = TechItem(
                    dimension_id=dimension.id,
                    slug=item_slug,
                    name=name,
                    description=description,
                    tags=tags or [],
                    is_custom=True,
                    created_by_user_id=project.owner_user_id,
                )
                session.add(tech_item)
                session.flush()  # Get ID
            
            # Get next order_no
            max_order = session.execute(
                select(func.max(ProjectTechChoice.order_no)).where(
                    ProjectTechChoice.project_id == project.id,
                    ProjectTechChoice.dimension_id == dimension.id,
                )
            ).scalar() or 0
            
            # Create choice
            choice = ProjectTechChoice(
                project_id=project.id,
                dimension_id=dimension.id,
                tech_item_id=tech_item.id,
                role=role.value,
                source=TechChoiceSource.USER_ADDED.value,
                accepted=True,
                notes=notes,
                order_no=max_order + 1,
            )
            session.add(choice)
            session.commit()
            session.refresh(choice)
            session.refresh(tech_item)
            
            return TechChoiceSummary(
                id=choice.id,
                project_id=choice.project_id,
                dimension_id=choice.dimension_id,
                dimension_slug=dimension.slug,
                dimension_name=dimension.name,
                tech_item_id=choice.tech_item_id,
                item_slug=tech_item.slug,
                item_name=tech_item.name,
                item_description=tech_item.description,
                role=choice.role,
                source=choice.source,
                accepted=choice.accepted,
                llm_rationale=None,
                llm_confidence=None,
                notes=choice.notes,
                order_no=choice.order_no,
            )

    def add_llm_suggestion(
        self,
        project_slug: str,
        dimension_slug: str,
        item_slug: str | None,
        item_name: str | None,
        role: TechChoiceRole,
        rationale: str,
        confidence: float,
    ) -> TechChoiceSummary | None:
        """Add an LLM-suggested tech choice (not yet accepted).
        
        If item_slug matches a catalog item, uses that. Otherwise creates a custom item.
        
        Args:
            project_slug: Project slug
            dimension_slug: Dimension slug
            item_slug: Catalog item slug (if matching)
            item_name: Free-form name (if no catalog match)
            role: Suggested role
            rationale: LLM's rationale
            confidence: Confidence score 0.0-1.0
            
        Returns:
            Created tech choice summary (accepted=False)
        """
        with app.db.session_scope() as session:
            project = session.execute(
                select(Project).where(Project.slug == project_slug)
            ).scalar_one_or_none()
            if not project:
                return None
            
            dimension = session.execute(
                select(TechDimension).where(TechDimension.slug == dimension_slug)
            ).scalar_one_or_none()
            if not dimension:
                raise ValueError(f"Dimension '{dimension_slug}' not found")
            
            # Try to find catalog item
            tech_item = None
            if item_slug:
                tech_item = session.execute(
                    select(TechItem).where(
                        TechItem.dimension_id == dimension.id,
                        TechItem.slug == item_slug,
                    )
                ).scalar_one_or_none()
            
            # If no catalog match and we have a name, create custom item
            if not tech_item and item_name:
                slug = self._slugify(item_name)
                tech_item = TechItem(
                    dimension_id=dimension.id,
                    slug=slug,
                    name=item_name,
                    tags=[],
                    is_custom=True,
                    created_by_user_id=project.owner_user_id,
                )
                session.add(tech_item)
                session.flush()
            
            if not tech_item:
                raise ValueError("Either item_slug or item_name must be provided")
            
            # Check for existing suggestion for this item
            existing = session.execute(
                select(ProjectTechChoice).where(
                    ProjectTechChoice.project_id == project.id,
                    ProjectTechChoice.dimension_id == dimension.id,
                    ProjectTechChoice.tech_item_id == tech_item.id,
                )
            ).scalar_one_or_none()
            
            if existing:
                # Update existing
                existing.role = role.value
                existing.source = TechChoiceSource.LLM_SUGGESTED.value
                existing.accepted = False
                existing.llm_rationale = rationale
                existing.llm_confidence = Decimal(str(confidence))
                session.commit()
                session.refresh(existing)
                choice = existing
            else:
                max_order = session.execute(
                    select(func.max(ProjectTechChoice.order_no)).where(
                        ProjectTechChoice.project_id == project.id,
                        ProjectTechChoice.dimension_id == dimension.id,
                    )
                ).scalar() or 0
                
                choice = ProjectTechChoice(
                    project_id=project.id,
                    dimension_id=dimension.id,
                    tech_item_id=tech_item.id,
                    role=role.value,
                    source=TechChoiceSource.LLM_SUGGESTED.value,
                    accepted=False,
                    llm_rationale=rationale,
                    llm_confidence=Decimal(str(confidence)),
                    order_no=max_order + 1,
                )
                session.add(choice)
                session.commit()
                session.refresh(choice)
            
            return TechChoiceSummary(
                id=choice.id,
                project_id=choice.project_id,
                dimension_id=choice.dimension_id,
                dimension_slug=dimension.slug,
                dimension_name=dimension.name,
                tech_item_id=choice.tech_item_id,
                item_slug=tech_item.slug,
                item_name=tech_item.name,
                item_description=tech_item.description,
                role=choice.role,
                source=choice.source,
                accepted=choice.accepted,
                llm_rationale=choice.llm_rationale,
                llm_confidence=float(choice.llm_confidence) if choice.llm_confidence else None,
                notes=choice.notes,
                order_no=choice.order_no,
            )

    def accept_suggestion(
        self, project_slug: str, dimension_slug: str, item_slug: str
    ) -> TechChoiceSummary | None:
        """Accept an LLM-suggested tech choice.
        
        Args:
            project_slug: Project slug
            dimension_slug: Dimension slug
            item_slug: Tech item slug
            
        Returns:
            Updated tech choice summary
        """
        with app.db.session_scope() as session:
            project = session.execute(
                select(Project).where(Project.slug == project_slug)
            ).scalar_one_or_none()
            if not project:
                return None
            
            dimension = session.execute(
                select(TechDimension).where(TechDimension.slug == dimension_slug)
            ).scalar_one_or_none()
            if not dimension:
                return None
            
            tech_item = session.execute(
                select(TechItem).where(
                    TechItem.dimension_id == dimension.id,
                    TechItem.slug == item_slug,
                )
            ).scalar_one_or_none()
            if not tech_item:
                return None
            
            choice = session.execute(
                select(ProjectTechChoice).where(
                    ProjectTechChoice.project_id == project.id,
                    ProjectTechChoice.dimension_id == dimension.id,
                    ProjectTechChoice.tech_item_id == tech_item.id,
                    ProjectTechChoice.source == TechChoiceSource.LLM_SUGGESTED.value,
                )
            ).scalar_one_or_none()
            
            if not choice:
                return None
            
            choice.accepted = True
            session.commit()
            session.refresh(choice)
            
            return TechChoiceSummary(
                id=choice.id,
                project_id=choice.project_id,
                dimension_id=choice.dimension_id,
                dimension_slug=dimension.slug,
                dimension_name=dimension.name,
                tech_item_id=choice.tech_item_id,
                item_slug=tech_item.slug,
                item_name=tech_item.name,
                item_description=tech_item.description,
                role=choice.role,
                source=choice.source,
                accepted=choice.accepted,
                llm_rationale=choice.llm_rationale,
                llm_confidence=float(choice.llm_confidence) if choice.llm_confidence else None,
                notes=choice.notes,
                order_no=choice.order_no,
            )

    def dismiss_suggestion(
        self, project_slug: str, dimension_slug: str, item_slug: str
    ) -> bool:
        """Dismiss (delete) an LLM-suggested tech choice.
        
        Args:
            project_slug: Project slug
            dimension_slug: Dimension slug
            item_slug: Tech item slug
            
        Returns:
            True if dismissed, False if not found
        """
        with app.db.session_scope() as session:
            project = session.execute(
                select(Project).where(Project.slug == project_slug)
            ).scalar_one_or_none()
            if not project:
                return False
            
            dimension = session.execute(
                select(TechDimension).where(TechDimension.slug == dimension_slug)
            ).scalar_one_or_none()
            if not dimension:
                return False
            
            tech_item = session.execute(
                select(TechItem).where(
                    TechItem.dimension_id == dimension.id,
                    TechItem.slug == item_slug,
                )
            ).scalar_one_or_none()
            if not tech_item:
                return False
            
            choice = session.execute(
                select(ProjectTechChoice).where(
                    ProjectTechChoice.project_id == project.id,
                    ProjectTechChoice.dimension_id == dimension.id,
                    ProjectTechChoice.tech_item_id == tech_item.id,
                    ProjectTechChoice.source == TechChoiceSource.LLM_SUGGESTED.value,
                    ProjectTechChoice.accepted == False,
                )
            ).scalar_one_or_none()
            
            if not choice:
                return False
            
            session.delete(choice)
            session.commit()
            return True

    def get_tech_statistics(self, project_slug: str) -> dict[str, Any]:
        """Get tech selection statistics for a project.
        
        Args:
            project_slug: Project slug
            
        Returns:
            Dictionary with tech selection statistics
        """
        choices = self.list_project_tech_choices(project_slug)
        dimensions = self.list_dimensions()
        total_dimensions = len(dimensions)
        
        if not choices:
            return {
                "total_choices": 0,
                "by_role": {},
                "by_source": {},
                "by_dimension": {},
                "coverage_percentage": 0.0,
                "covered_dimensions": 0,
                "total_dimensions": total_dimensions,
                "tbd_dimensions": 0,
                "pending_suggestions": 0,
            }
        
        by_role: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_dimension: dict[str, int] = {}
        tbd_count = 0
        pending_suggestions = 0
        
        for choice in choices:
            by_role[choice.role] = by_role.get(choice.role, 0) + 1
            by_source[choice.source] = by_source.get(choice.source, 0) + 1
            by_dimension[choice.dimension_slug] = by_dimension.get(choice.dimension_slug, 0) + 1
            
            if choice.role == TechChoiceRole.TBD.value:
                tbd_count += 1
            if choice.source == TechChoiceSource.LLM_SUGGESTED.value and not choice.accepted:
                pending_suggestions += 1
        
        covered = len(by_dimension)
        
        return {
            "total_choices": len(choices),
            "by_role": by_role,
            "by_source": by_source,
            "by_dimension": by_dimension,
            "coverage_percentage": (covered / total_dimensions * 100) if total_dimensions else 0,
            "covered_dimensions": covered,
            "total_dimensions": total_dimensions,
            "tbd_dimensions": tbd_count,
            "pending_suggestions": pending_suggestions,
        }

    def render_tech_summary(self, project_slug: str) -> str:
        """Render tech choices summary as markdown.
        
        Args:
            project_slug: Project slug
            
        Returns:
            Formatted markdown summary of all tech choices
        """
        choices = self.list_project_tech_choices(project_slug)
        
        if not choices:
            return "# Tech Panorama\n\nNo technology choices defined for this project."
        
        lines = ["# Tech Panorama", ""]
        
        # Group by dimension
        by_dimension: dict[str, list[TechChoiceSummary]] = {}
        for choice in choices:
            by_dimension.setdefault(choice.dimension_slug, []).append(choice)
        
        role_emoji = {
            TechChoiceRole.TARGET.value: "🎯",
            TechChoiceRole.LEGACY.value: "⏳",
            TechChoiceRole.OPTIONAL.value: "⚪",
            TechChoiceRole.MUST_AVOID.value: "🚫",
            TechChoiceRole.TBD.value: "❓",
        }
        
        for dim_slug in sorted(by_dimension.keys()):
            dim_choices = by_dimension[dim_slug]
            dim_name = dim_choices[0].dimension_name
            lines.append(f"## {dim_name}")
            lines.append("")
            
            for choice in dim_choices:
                emoji = role_emoji.get(choice.role, "")
                name = choice.item_name or "TBD"
                source_note = ""
                if choice.source == TechChoiceSource.USER_ADDED.value:
                    source_note = " (custom)"
                elif choice.source == TechChoiceSource.LLM_SUGGESTED.value:
                    source_note = " ✨" if not choice.accepted else " (AI suggested)"
                
                lines.append(f"- {emoji} **{name}**{source_note}")
                
                if choice.llm_rationale:
                    lines.append(f"  - *Rationale:* {choice.llm_rationale}")
                if choice.notes:
                    lines.append(f"  - *Notes:* {choice.notes}")
            
            lines.append("")
        
        # Statistics
        stats = self.get_tech_statistics(project_slug)
        lines.append("## Summary")
        lines.append("")
        lines.append(
            f"- **Coverage:** {stats['covered_dimensions']}/{stats['total_dimensions']} "
            f"dimensions ({stats['coverage_percentage']:.0f}%)"
        )
        lines.append(f"- **Total choices:** {stats['total_choices']}")
        
        if stats["by_role"]:
            role_summary = ", ".join(f"{c} {r}" for r, c in stats["by_role"].items())
            lines.append(f"- **By role:** {role_summary}")
        
        return "\n".join(lines)

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to slug format."""
        slug = text.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")