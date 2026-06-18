"""ProposeBacklogPrompt: Generate phase-based project backlogs from skills.

This prompt delegates to template families to create project-specific backlog structures.
The template family provides domain expertise while allowing LLM flexibility to adapt
phase structures to the specific project context and objectives.
"""

from __future__ import annotations

from datetime import UTC

from app.families._base import BacklogProposalContext, TemplateFamily
from app.llm.base import ChatPrompt
from app.schemas.llm_io import ProposedBacklog
from app.schemas.views import SkillView


class ProposeBacklogPrompt:
    """LLM prompt for generating project backlogs with phase-based structure."""

    @staticmethod
    def create(
        project_context_str: str,
        proposed_skills: list[SkillView],
        template_family: TemplateFamily
    ) -> ChatPrompt:
        """Create a prompt for proposing a project backlog.

        Args:
            project_context_str: Rendered project context string
            proposed_skills: Skills available for the project (from Step 1.6)
            template_family: Template family that provides domain-specific guidance

        Returns:
            ChatPrompt configured for backlog proposal
        """
        # Create a minimal project view for the context
        # This is a simplified approach - in practice this would come from a ProjectView
        from datetime import datetime
        from decimal import Decimal
        from uuid import uuid4

        from app.enums import Grouping, LlmProvider, ProjectStatus
        from app.schemas.views import ProjectView

        mock_project = ProjectView(
            id=uuid4(),
            tenant_id=uuid4(),
            owner_user_id=uuid4(),
            slug="temp-project",
            name="Temporary Project",
            objective="Project objective extracted from context",
            card_code_prefix="PROJ",
            card_template="phase_vli",
            grouping=Grouping.PHASE,
            status=ProjectStatus.DRAFT,
            llm_provider=LlmProvider.ANTHROPIC,
            llm_model="claude-3-5-sonnet-20241022",
            llm_temperature=Decimal("0.7"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Create context for template family
        backlog_context = BacklogProposalContext(
            project=mock_project,
            project_context=project_context_str,
            proposed_skills=proposed_skills
        )

        # Delegate to template family for domain-specific prompt creation
        return template_family.propose_backlog_prompt(backlog_context)

    @staticmethod
    def get_skill_categories(skills: list[SkillView]) -> dict[str, list[SkillView]]:
        """Categorize skills by kind for easier reference in prompts.

        Args:
            skills: List of skills to categorize

        Returns:
            Dictionary mapping skill kinds to skill lists
        """
        from collections import defaultdict

        categories = defaultdict(list)
        for skill in skills:
            categories[skill.kind.value].append(skill)

        return dict(categories)

    @staticmethod
    def format_skills_summary(skills: list[SkillView]) -> str:
        """Format skills into a concise summary for LLM consumption.

        Groups by kind and includes name + description for each skill so the
        proposer can assign the right skills to each card. We deliberately
        omit body_md and resources here — the goal is a scannable inventory,
        not deep guidance. DraftCard handles that (via L2/L3 progressive
        disclosure) once a specific card has been chosen.

        Args:
            skills: Skills to format

        Returns:
            Formatted string with skill categories, slugs, names, and
            one-line descriptions.
        """
        categories = ProposeBacklogPrompt.get_skill_categories(skills)

        parts = []
        for kind, skill_list in categories.items():
            parts.append(f"**{kind.title()}:**")
            for s in skill_list:
                # Keep each line scannable — truncate verbose descriptions.
                desc = s.description.strip().replace("\n", " ")
                if len(desc) > 200:
                    desc = desc[:200].rstrip() + "…"
                parts.append(f"- `{s.slug}` — {s.name}: {desc}")
            parts.append("")

        return "\n".join(parts).rstrip()

    @staticmethod
    def validate_proposed_backlog(
        backlog: ProposedBacklog,
        available_skills: list[SkillView]
    ) -> list[str]:
        """Validate a proposed backlog for common issues.

        Args:
            backlog: The proposed backlog to validate
            available_skills: Skills that were available for the proposal

        Returns:
            List of validation warnings (empty if valid)
        """
        warnings = []
        available_skill_slugs = {s.slug for s in available_skills}
        all_card_codes = {card.code for phase in backlog.phases for card in phase.cards}

        # Check skill references
        for phase in backlog.phases:
            for card in phase.cards:
                for skill_slug in card.skill_slugs:
                    if skill_slug not in available_skill_slugs:
                        warnings.append(
                            f"Card {card.code} references unknown skill: {skill_slug}"
                        )

        # Check dependency references
        for phase in backlog.phases:
            for card in phase.cards:
                for dep_code in card.depends_on_codes:
                    if dep_code not in all_card_codes:
                        warnings.append(
                            f"Card {card.code} depends on unknown card: {dep_code}"
                        )

                for parallel_code in card.parallel_with_codes:
                    if parallel_code not in all_card_codes:
                        warnings.append(
                            f"Card {card.code} parallel with unknown card: {parallel_code}"
                        )

        # Check critical path references
        for path_code in backlog.critical_path_codes:
            if path_code not in all_card_codes:
                warnings.append(
                    f"Critical path references unknown card: {path_code}"
                )

        return warnings
