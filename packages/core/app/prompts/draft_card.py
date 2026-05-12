"""DraftCardPrompt: Generate detailed card sections from proposed cards.

This prompt takes a proposed card and rich context to generate detailed card sections:
context, task, outputs, acceptance criteria, inputs, and optional human gate checklists.
The template family provides domain-specific examples and structure guidance.
"""

from __future__ import annotations

from app.families._base import CardDraftContext, TemplateFamily
from app.llm.base import ChatPrompt
from app.schemas.llm_io import DraftedCard


class DraftCardPrompt:
    """LLM prompt for drafting detailed card sections from proposed cards."""

    @staticmethod
    def create(
        context: CardDraftContext,
        template_family: TemplateFamily
    ) -> ChatPrompt:
        """Create a prompt for drafting detailed card sections.

        Args:
            context: Complete context including project, phase, card, skills, and dependencies
            template_family: Template family that provides domain-specific guidance and examples

        Returns:
            ChatPrompt configured for card drafting
        """
        # Delegate to template family for domain-specific prompt creation
        return template_family.draft_card_prompt(context)

    @staticmethod
    def build_dependency_context(context: CardDraftContext) -> str:
        """Build a summary of card dependencies for context.

        Args:
            context: Card drafting context with dependency information

        Returns:
            Formatted string describing card dependencies and relationships
        """
        parts = []

        if context.upstream_cards:
            parts.append("**Depends on:**")
            for card in context.upstream_cards:
                parts.append(f"- {card.code}: {card.title} (provides foundational work)")

        if context.sibling_cards_in_phase:
            parallel_cards = [c for c in context.sibling_cards_in_phase if c.code != context.card.code]
            if parallel_cards:
                parts.append("**Runs in parallel with:**")
                for card in parallel_cards:
                    parts.append(f"- {card.code}: {card.title}")

        return "\n".join(parts) if parts else "No direct dependencies within this phase."

    @staticmethod
    def build_skills_context(skills: list) -> str:
        """Build a summary of available skills for the card.

        Args:
            skills: List of SkillView objects available for this card

        Returns:
            Formatted string describing skills and their purposes
        """
        if not skills:
            return "No specific skills assigned to this card."

        parts = ["**Skills to invoke:**"]
        for skill in skills:
            parts.append(f"- `{skill.slug}`: {skill.name} ({skill.kind})")
            parts.append(f"  {skill.description}")

        return "\n".join(parts)

    @staticmethod
    def suggest_card_inputs(context: CardDraftContext) -> list[dict[str, str]]:
        """Suggest likely inputs for a card based on its skills and context.

        Args:
            context: Card drafting context with skill and project information

        Returns:
            List of suggested input dictionaries with kind, path, and label
        """
        suggestions = []

        # Add skill resources for each skill used
        for skill in context.skills_used:
            # Main skill file
            suggestions.append({
                "kind": "skill_resource",
                "path": f".agents/skills/{skill.slug}/SKILL.md",
                "label": f"{skill.name} guidance"
            })

            # Suggest common resource types based on skill kind
            if skill.kind == "analyzer":
                suggestions.append({
                    "kind": "skill_resource",
                    "path": f".agents/skills/{skill.slug}/resources/analysis-checklist.md",
                    "label": "Analysis methodology and checklist"
                })
            elif skill.kind == "authoring":
                suggestions.append({
                    "kind": "skill_resource",
                    "path": f".agents/skills/{skill.slug}/resources/code-template.py",
                    "label": "Implementation template and examples"
                })
            elif skill.kind == "procedure":
                suggestions.append({
                    "kind": "skill_resource",
                    "path": f".agents/skills/{skill.slug}/resources/workflow-checklist.md",
                    "label": "Step-by-step workflow guide"
                })

        # Add outputs from upstream cards as potential inputs
        for upstream in context.upstream_cards:
            suggestions.append({
                "kind": "artifact",
                "path": f"data/projects/{context.project.slug}/artifacts/{upstream.code}-outputs/",
                "label": f"Outputs from {upstream.title}"
            })

        return suggestions

    @staticmethod
    def validate_drafted_card(
        drafted_card: DraftedCard,
        context: CardDraftContext
    ) -> list[str]:
        """Validate a drafted card for completeness and consistency.

        Args:
            drafted_card: The drafted card to validate
            context: Original context used for drafting

        Returns:
            List of validation warnings (empty if valid)
        """
        warnings = []

        # Check required sections are non-empty
        if not drafted_card.context_md.strip():
            warnings.append("Context section is empty")
        if not drafted_card.task_md.strip():
            warnings.append("Task section is empty")
        if not drafted_card.outputs_md.strip():
            warnings.append("Outputs section is empty")
        if not drafted_card.acceptance_criteria_md.strip():
            warnings.append("Acceptance criteria section is empty")

        # Check acceptance criteria format
        if drafted_card.acceptance_criteria_md and "- [ ]" not in drafted_card.acceptance_criteria_md:
            warnings.append("Acceptance criteria should contain checkbox format (- [ ])")

        # Check human gate consistency
        if context.card.human_gate and not drafted_card.human_gate_checklist_md:
            warnings.append("Card has human_gate=true but no human gate checklist provided")
        elif not context.card.human_gate and drafted_card.human_gate_checklist_md:
            warnings.append("Card has human_gate=false but human gate checklist provided")

        # Check skill resource references in inputs
        skill_slugs = {skill.slug for skill in context.skills_used}
        for input_item in drafted_card.inputs:
            if input_item.kind == "skill_resource":
                # Extract skill slug from path like .agents/skills/skill-name/...
                path_parts = input_item.path.split('/')
                if len(path_parts) >= 3 and path_parts[0] == ".agents" and path_parts[1] == "skills":
                    referenced_skill = path_parts[2]
                    if referenced_skill not in skill_slugs:
                        warnings.append(
                            f"Input references skill '{referenced_skill}' not in card's skill list"
                        )

        return warnings
