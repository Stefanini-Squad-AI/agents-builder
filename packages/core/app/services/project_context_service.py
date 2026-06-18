"""Service for loading comprehensive project context for LLM prompts."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload, Session

from app.domain.backlog import Card, Phase
from app.domain.projects import Project, ProjectQaAnswer
from app.domain.skills import Skill
from app.domain.tech import ProjectTechChoice, TechDimension, TechItem
from app.schemas.views import (
    ArtifactSummary, 
    ProjectContext, 
    QaAnswerView, 
    TechChoiceView
)
from app.enums import TechChoiceSource, TechChoiceRole, ExtractionStatus


class ProjectContextService:
    """Service for loading comprehensive project context for LLM prompts.
    
    Args:
        session: SQLAlchemy session owned by the caller. The service uses this
                 session for all DB operations but never commits — caller owns commit.
    """

    def __init__(self, session: Session) -> None:
        """Initialize the project context service with caller's session (P2 fix)."""
        self._session = session

    def load_project_context(self, project_slug: str) -> ProjectContext | None:
        """Load full project context for LLM prompts.
        
        Args:
            project_slug: Project slug
            
        Returns:
            ProjectContext with all relevant project data, or None if project not found
        """
        # Load project with all relationships
        project_query = (
            select(Project)
            .where(Project.slug == project_slug)
            .options(
                selectinload(Project.qa_answers),
                selectinload(Project.artifacts),
                selectinload(Project.tech_choices).selectinload(ProjectTechChoice.dimension),
                selectinload(Project.tech_choices).selectinload(ProjectTechChoice.tech_item)
            )
        )
        
        project = self._session.execute(project_query).scalar_one_or_none()
        if not project:
            return None
        
        # Build Q&A dictionary
        qa = {}
        for qa_answer in project.qa_answers:
            if qa_answer.answer_md and qa_answer.answer_md.strip():
                qa[qa_answer.question_key] = qa_answer.answer_md
        
        # Build tech choices by dimension
        tech_choices_by_dimension = {}
        for choice in project.tech_choices:
            dimension = choice.dimension
            dimension_slug = dimension.slug
            
            if dimension_slug not in tech_choices_by_dimension:
                tech_choices_by_dimension[dimension_slug] = []
            
            # Create TechChoiceView
            choice_view = TechChoiceView(
                id=choice.id,
                project_id=choice.project_id,
                dimension_id=choice.dimension_id,
                dimension_slug=dimension.slug,
                dimension_name=dimension.name,
                tech_item_id=choice.tech_item_id,
                tech_item_slug=choice.tech_item.slug if choice.tech_item else None,
                tech_item_name=choice.tech_item.name if choice.tech_item else None,
                role=TechChoiceRole(choice.role),
                source=TechChoiceSource(choice.source),
                accepted=choice.accepted,
                llm_rationale=choice.llm_rationale,
                llm_confidence=choice.llm_confidence,
                notes=choice.notes,
                order_no=choice.order_no
            )
            tech_choices_by_dimension[dimension_slug].append(choice_view)
        
        # Build artifact summaries — no truncation, full content for richer context
        artifact_summaries = []
        for artifact in project.artifacts:
            if artifact.extraction_status == "extracted":
                summary = ArtifactSummary(
                    id=artifact.id,
                    filename=artifact.filename,
                    kind=artifact.kind,
                    extraction_status=artifact.extraction_status,
                    size_bytes=artifact.size_bytes,
                    content_md_excerpt=artifact.content_md,  # Full content
                    content_md_truncated=artifact.content_md_truncated
                )
                artifact_summaries.append(summary)
        
        # Create ProjectContext
        return ProjectContext(
            objective=project.objective,
            qa=qa,
            tech_choices_by_dimension=tech_choices_by_dimension,
            artifact_summaries=artifact_summaries,
            context_notes_md=project.context_md or ""
        )

    def render_context_string(self, context: ProjectContext) -> str:
        """Render ProjectContext to a human-readable string for LLM prompts.
        
        Args:
            context: ProjectContext object
            
        Returns:
            Formatted string representation of the project context
        """
        parts = []
        
        # Objective
        parts.append(f"**Project Objective:** {context.objective}")
        parts.append("")
        
        # Q&A answers
        if context.qa:
            parts.append("**Discovery Q&A:**")
            qa_labels = {
                "business_problem": "Business Problem",
                "success_definition": "Success Definition",
                "users_and_actors": "Users and Actors",
                "must_preserve": "Must Preserve",
                "must_change": "Must Change",
                "compliance": "Compliance Requirements",
                "known_gaps": "Known Gaps",
            }
            for key, answer in context.qa.items():
                label = qa_labels.get(key, key.replace("_", " ").title())
                parts.append(f"- **{label}:** {answer}")
            parts.append("")
        
        # Tech choices
        if context.tech_choices_by_dimension:
            parts.append("**Technology Stack:**")
            for dimension, choices in context.tech_choices_by_dimension.items():
                choice_names = []
                for choice in choices:
                    name = choice.tech_item_name or choice.tech_item_slug or "TBD"
                    role = choice.role.value if hasattr(choice.role, 'value') else choice.role
                    if role != "target":
                        name = f"{name} ({role})"
                    choice_names.append(name)
                parts.append(f"- **{dimension.replace('_', ' ').title()}:** {', '.join(choice_names)}")
            parts.append("")
        
        # Artifact summaries
        if context.artifact_summaries:
            parts.append("**Uploaded Artifacts:**")
            for artifact in context.artifact_summaries:
                kind_str = artifact.kind.value if hasattr(artifact.kind, 'value') else artifact.kind
                parts.append(f"- **{artifact.filename}** ({kind_str}, {artifact.size_bytes} bytes)")
                if artifact.content_md_excerpt:
                    # Full content — no truncation for richer LLM context
                    parts.append(f"  Content: {artifact.content_md_excerpt}")
            parts.append("")
        
        # Additional context notes
        if context.context_notes_md:
            parts.append("**Additional Context:**")
            parts.append(context.context_notes_md)
            parts.append("")
        
        return "\n".join(parts)

    def get_project_summary_stats(self, project_slug: str) -> dict[str, int] | None:
        """Get summary statistics for project completion status.
        
        Args:
            project_slug: Project slug
            
        Returns:
            Dictionary with completion stats, or None if project not found
        """
        # Get project
        project = self._session.execute(
            select(Project).where(Project.slug == project_slug)
        ).scalar_one_or_none()
        
        if not project:
            return None
        
        # Count Q&A answers
        qa_count = self._session.execute(
            select(ProjectQaAnswer.id).where(
                ProjectQaAnswer.project_id == project.id,
                ProjectQaAnswer.answer_md.isnot(None),
                ProjectQaAnswer.answer_md != ""
            )
        ).rowcount or 0
        
        # Count tech choices
        tech_count = self._session.execute(
            select(ProjectTechChoice.id).where(
                ProjectTechChoice.project_id == project.id
            )
        ).rowcount or 0
        
        # Count skills
        skill_count = self._session.execute(
            select(Skill.id).where(Skill.project_id == project.id)
        ).rowcount or 0
        
        # Count cards
        card_count = self._session.execute(
            select(Card.id)
            .join(Phase, Card.phase_id == Phase.id)
            .where(Phase.project_id == project.id)
        ).rowcount or 0
        
        # Count phases
        phase_count = self._session.execute(
            select(Phase.id).where(Phase.project_id == project.id)
        ).rowcount or 0
        
        return {
            "qa_answers": qa_count,
            "tech_choices": tech_count,
            "skills": skill_count,
            "cards": card_count,
            "phases": phase_count
        }

    def validate_project_readiness_for_ai(self, project_slug: str) -> dict[str, bool | str]:
        """Check if project has sufficient context for AI generation.
        
        Args:
            project_slug: Project slug
            
        Returns:
            Dictionary with readiness status and recommendations
        """
        context = self.load_project_context(project_slug)
        if not context:
            return {
                "ready": False,
                "reason": "Project not found"
            }
        
        # Check critical requirements
        critical_qa_keys = ["objective", "scope", "stakeholders"]  # First 3 critical questions
        critical_qa_answered = sum(1 for key in critical_qa_keys if key in context.qa)
        
        if critical_qa_answered < 3:
            return {
                "ready": False,
                "reason": f"Need to answer critical Q&A questions. Answered {critical_qa_answered}/3."
            }
        
        # Recommended but not required
        recommendations = []
        
        if len(context.qa) < 5:
            recommendations.append("Consider answering more Q&A questions for better results")
        
        if len(context.tech_choices_by_dimension) < 3:
            recommendations.append("Consider selecting more technology choices")
        
        if not context.artifact_summaries:
            recommendations.append("Consider uploading relevant documents for additional context")
        
        return {
            "ready": True,
            "recommendations": recommendations
        }