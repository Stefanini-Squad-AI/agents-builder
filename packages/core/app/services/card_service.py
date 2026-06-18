"""Card service for CLI and API operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.db
from app.domain.backlog import Card, CardInput, CardSkill, Phase
from app.domain.projects import Project
from app.enums import CardInputKind


class CardSummary:
    """Simplified card data structure for CLI operations."""
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class CardService:
    """Service for card CRUD operations and management."""

    def __init__(self) -> None:
        """Initialize the card service."""
        pass

    def list_project_cards(self, project_slug: str) -> list[CardSummary]:
        """List all cards in a project, grouped by phase.
        
        Args:
            project_slug: Project slug
            
        Returns:
            List of card summaries ordered by phase order and card code
        """
        with app.db.session_scope() as session:
            # Get project
            project = session.execute(
                select(Project).where(Project.slug == project_slug)
            ).scalar_one_or_none()
            
            if not project:
                return []
            
            # Query cards with phase information
            query = (
                select(Card, Phase.code.label('phase_code'), Phase.name.label('phase_name'))
                .join(Phase, Card.phase_id == Phase.id)
                .where(Phase.project_id == project.id)
                .order_by(Phase.order_no, Card.code)
            )
            
            results = session.execute(query).all()
            
            card_summaries = []
            for card, phase_code, phase_name in results:
                card_summary = CardSummary(
                    id=card.id,
                    phase_id=card.phase_id,
                    phase_code=phase_code,
                    phase_name=phase_name,
                    code=card.code,
                    name=card.name,
                    description=card.description,
                    status=card.status,
                    context_md=card.context_md,
                    task_md=card.task_md,
                    outputs_md=card.outputs_md,
                    acceptance_criteria_md=card.acceptance_criteria_md,
                    human_gate_checklist_md=card.human_gate_checklist_md,
                    has_human_gate=card.has_human_gate,
                    priority=card.priority,
                    estimated_hours=card.estimated_hours,
                    created_at=card.created_at,
                    updated_at=card.updated_at
                )
                card_summaries.append(card_summary)
            
            return card_summaries

    def get_card(self, project_slug: str, card_code: str) -> CardSummary | None:
        """Get a specific card by project and card code.
        
        Args:
            project_slug: Project slug
            card_code: Card code (e.g., "PROJ-101")
            
        Returns:
            Card summary with full details or None if not found
        """
        with app.db.session_scope() as session:
            # Load card with all relationships
            query = (
                select(Card, Phase.code.label('phase_code'), Phase.name.label('phase_name'))
                .join(Phase, Card.phase_id == Phase.id)
                .join(Project, Phase.project_id == Project.id)
                .where(Project.slug == project_slug, Card.code == card_code)
                .options(
                    selectinload(Card.skills),
                    selectinload(Card.inputs),
                    selectinload(Card.dependencies_out),
                    selectinload(Card.dependencies_in)
                )
            )
            
            result = session.execute(query).first()
            if not result:
                return None
            
            card, phase_code, phase_name = result
            
            # Build full card summary with relationships
            card_summary = CardSummary(
                id=card.id,
                phase_id=card.phase_id,
                phase_code=phase_code,
                phase_name=phase_name,
                code=card.code,
                name=card.name,
                description=card.description,
                status=card.status,
                context_md=card.context_md,
                task_md=card.task_md,
                outputs_md=card.outputs_md,
                acceptance_criteria_md=card.acceptance_criteria_md,
                human_gate_checklist_md=card.human_gate_checklist_md,
                has_human_gate=card.has_human_gate,
                priority=card.priority,
                estimated_hours=card.estimated_hours,
                created_at=card.created_at,
                updated_at=card.updated_at,
                # Relationships
                skills=[{"slug": cs.skill.slug, "name": cs.skill.name} for cs in card.skills],
                inputs=[
                    {
                        "kind": ci.kind,
                        "path": ci.path,
                        "description": ci.description
                    }
                    for ci in card.inputs
                ],
                dependencies_out=[dep.to_card_code for dep in card.dependencies_out],
                dependencies_in=[dep.from_card_code for dep in card.dependencies_in]
            )
            
            return card_summary

    def update_card_content(
        self, 
        project_slug: str, 
        card_code: str, 
        *,
        context_md: str | None = None,
        task_md: str | None = None,
        outputs_md: str | None = None,
        acceptance_criteria_md: str | None = None,
        human_gate_checklist_md: str | None = None
    ) -> CardSummary | None:
        """Update card content sections.
        
        Args:
            project_slug: Project slug
            card_code: Card code
            context_md: New context content (optional)
            task_md: New task content (optional)
            outputs_md: New outputs content (optional)
            acceptance_criteria_md: New acceptance criteria (optional)
            human_gate_checklist_md: New human gate checklist (optional)
            
        Returns:
            Updated card summary or None if not found
        """
        with app.db.session_scope() as session:
            # Find card
            query = (
                select(Card)
                .join(Phase, Card.phase_id == Phase.id)
                .join(Project, Phase.project_id == Project.id)
                .where(Project.slug == project_slug, Card.code == card_code)
            )
            
            card = session.execute(query).scalar_one_or_none()
            if not card:
                return None
            
            # Update provided fields
            if context_md is not None:
                card.context_md = context_md
            if task_md is not None:
                card.task_md = task_md
            if outputs_md is not None:
                card.outputs_md = outputs_md
            if acceptance_criteria_md is not None:
                card.acceptance_criteria_md = acceptance_criteria_md
            if human_gate_checklist_md is not None:
                card.human_gate_checklist_md = human_gate_checklist_md
                # Update human gate flag based on content
                card.has_human_gate = bool(human_gate_checklist_md and human_gate_checklist_md.strip())
            
            session.commit()
            session.refresh(card)
            
            # Return updated summary
            phase = session.get(Phase, card.phase_id)
            return CardSummary(
                id=card.id,
                phase_id=card.phase_id,
                phase_code=phase.code,
                phase_name=phase.name,
                code=card.code,
                name=card.name,
                description=card.description,
                status=card.status,
                context_md=card.context_md,
                task_md=card.task_md,
                outputs_md=card.outputs_md,
                acceptance_criteria_md=card.acceptance_criteria_md,
                human_gate_checklist_md=card.human_gate_checklist_md,
                has_human_gate=card.has_human_gate,
                priority=card.priority,
                estimated_hours=card.estimated_hours,
                created_at=card.created_at,
                updated_at=card.updated_at
            )

    def render_card_markdown(self, card: CardSummary) -> str:
        """Render card as complete markdown format (VLI-style).
        
        Args:
            card: Card summary with data
            
        Returns:
            Complete card markdown content
        """
        lines = []
        
        # Header
        lines.append(f"# {card.code}: {card.name}")
        lines.append("")
        lines.append(f"**Phase:** {card.phase_code} - {card.phase_name}")
        lines.append(f"**Status:** {card.status}")
        
        if hasattr(card, 'priority') and card.priority:
            lines.append(f"**Priority:** {card.priority}")
        
        if hasattr(card, 'estimated_hours') and card.estimated_hours:
            lines.append(f"**Estimated Hours:** {card.estimated_hours}")
        
        lines.append("")
        lines.append(f"**Description:** {card.description}")
        lines.append("")
        
        # Context
        lines.append("## Context")
        lines.append("")
        if card.context_md and card.context_md.strip():
            lines.append(card.context_md)
        else:
            lines.append("_Context will be added during planning._")
        lines.append("")
        
        # Skills to invoke
        if hasattr(card, 'skills') and card.skills:
            lines.append("## Skills to Invoke")
            lines.append("")
            for skill in card.skills:
                lines.append(f"- **{skill['slug']}**: {skill['name']}")
            lines.append("")
        
        # Inputs
        if hasattr(card, 'inputs') and card.inputs:
            lines.append("## Inputs")
            lines.append("")
            for input_item in card.inputs:
                if input_item['kind'] == CardInputKind.SKILL_RESOURCE.value:
                    lines.append(f"- **Skill Resource:** {input_item['path']}")
                elif input_item['kind'] == CardInputKind.ARTIFACT.value:
                    lines.append(f"- **Artifact:** {input_item['path']}")
                else:
                    lines.append(f"- **External:** {input_item['path']}")
                
                if input_item.get('description'):
                    lines.append(f"  {input_item['description']}")
            lines.append("")
        
        # Tasks
        lines.append("## Tasks")
        lines.append("")
        if card.task_md and card.task_md.strip():
            lines.append(card.task_md)
        else:
            lines.append("_Tasks will be defined during implementation planning._")
        lines.append("")
        
        # Outputs
        lines.append("## Outputs")
        lines.append("")
        if card.outputs_md and card.outputs_md.strip():
            lines.append(card.outputs_md)
        else:
            lines.append("_Outputs will be defined during implementation planning._")
        lines.append("")
        
        # Acceptance Criteria
        lines.append("## Acceptance Criteria")
        lines.append("")
        if card.acceptance_criteria_md and card.acceptance_criteria_md.strip():
            lines.append(card.acceptance_criteria_md)
        else:
            lines.append("_Acceptance criteria will be defined during implementation planning._")
        lines.append("")
        
        # Human Gate
        if card.has_human_gate and card.human_gate_checklist_md:
            lines.append("## Human Gate Checklist")
            lines.append("")
            lines.append(card.human_gate_checklist_md)
            lines.append("")
        
        # Dependencies
        if hasattr(card, 'dependencies_in') and card.dependencies_in:
            lines.append("## Dependencies")
            lines.append("")
            lines.append("This card depends on:")
            for dep in card.dependencies_in:
                lines.append(f"- {dep}")
            lines.append("")
        
        if hasattr(card, 'dependencies_out') and card.dependencies_out:
            lines.append("## Blocks")
            lines.append("")
            lines.append("This card blocks:")
            for dep in card.dependencies_out:
                lines.append(f"- {dep}")
            lines.append("")
        
        return "\n".join(lines)

    def get_cards_statistics(self, project_slug: str) -> dict[str, Any]:
        """Get card statistics for a project.
        
        Args:
            project_slug: Project slug
            
        Returns:
            Dictionary with card statistics
        """
        cards = self.list_project_cards(project_slug)
        
        if not cards:
            return {
                "total_cards": 0,
                "by_status": {},
                "by_phase": {},
                "with_human_gates": 0,
                "estimated_total_hours": 0,
                "completion_percentage": 0
            }
        
        # Group by status
        by_status = {}
        by_phase = {}
        with_human_gates = 0
        total_hours = 0
        
        for card in cards:
            # Count by status
            status = card.status
            by_status[status] = by_status.get(status, 0) + 1
            
            # Count by phase
            phase_key = f"{card.phase_code}"
            by_phase[phase_key] = by_phase.get(phase_key, 0) + 1
            
            # Count human gates
            if card.has_human_gate:
                with_human_gates += 1
            
            # Sum estimated hours
            if hasattr(card, 'estimated_hours') and card.estimated_hours:
                total_hours += card.estimated_hours
        
        # Calculate completion percentage
        completed_statuses = ["done", "completed", "closed"]
        completed_count = sum(
            count for status, count in by_status.items() 
            if status.lower() in completed_statuses
        )
        completion_percentage = (completed_count / len(cards) * 100) if cards else 0
        
        return {
            "total_cards": len(cards),
            "by_status": by_status,
            "by_phase": by_phase,
            "with_human_gates": with_human_gates,
            "estimated_total_hours": total_hours,
            "completion_percentage": completion_percentage
        }