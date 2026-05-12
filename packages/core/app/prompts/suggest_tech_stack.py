"""SuggestTechStackPrompt: Generate AI-powered technology recommendations for dimensions.

This prompt takes project context and a specific tech dimension to generate contextual
technology recommendations. It considers existing project choices, skills, and objectives
to suggest appropriate technologies with role classifications and confidence scores.
"""

from __future__ import annotations

from app.llm.base import ChatMessage, ChatPrompt
from app.schemas.llm_io import SuggestedTechForDimension
from app.schemas.views import ProjectContext, TechChoiceView, TechDimensionView


class SuggestTechStackPrompt:
    """LLM prompt for generating contextual technology recommendations."""

    @staticmethod
    def create(
        project_context: ProjectContext,
        dimension: TechDimensionView,
        existing_choices: list[TechChoiceView] | None = None
    ) -> ChatPrompt:
        """Create a prompt for technology stack suggestions.

        Args:
            project_context: Complete project context including objective, skills, etc.
            dimension: Target dimension with available catalog items
            existing_choices: Current tech choices across all dimensions (for context)

        Returns:
            ChatPrompt configured for tech suggestion generation
        """
        system_prompt = SuggestTechStackPrompt._build_system_prompt(dimension)
        user_message = SuggestTechStackPrompt._build_user_message(
            project_context, dimension, existing_choices or []
        )

        return ChatPrompt(
            system=system_prompt,
            messages=[user_message],
            response_schema=SuggestedTechForDimension
        )

    @staticmethod
    def _build_system_prompt(dimension: TechDimensionView) -> str:
        """Build system prompt with dimension-specific guidance."""
        catalog_items_text = SuggestTechStackPrompt._format_catalog_items(dimension.items)

        return f"""You are an expert technology architect specializing in recommending appropriate technology stacks for software projects.

**Your Task:**
Analyze the project context and suggest up to 10 technology items for the "{dimension.name}" dimension that best fit the project's needs, constraints, and objectives.

**Target Dimension: {dimension.name}**
*{dimension.description}*

**Available Catalog Items:**
{catalog_items_text}

**Suggestion Guidelines:**
- **Prefer catalog items** when they match project needs (use `catalog_slug`)
- **Suggest free-form items** only when no catalog item fits (use `free_form_name`)
- **Consider project maturity**: Enterprise vs startup, legacy vs greenfield
- **Factor in team skills**: Match existing expertise while allowing strategic growth
- **Respect constraints**: Budget, timeline, compliance, existing infrastructure
- **Think holistically**: How choices interact with other dimensions

**Role Classification:**
- **TARGET**: Primary recommended choice for this project
- **LEGACY**: Technology being migrated FROM (identify what exists)
- **OPTIONAL**: Nice-to-have or alternative option
- **MUST_AVOID**: Technologies that would be problematic for this project

**Confidence Scoring (0.0-1.0):**
- **0.9-1.0**: Highly confident, strong project fit, proven track record
- **0.7-0.8**: Good fit with minor considerations or assumptions
- **0.5-0.6**: Reasonable option but requires validation or has trade-offs
- **0.3-0.4**: Speculative suggestion, needs significant evaluation
- **0.1-0.2**: Low confidence, high-risk or experimental

**Quality Standards:**
- Provide specific, actionable rationales (not generic descriptions)
- Consider integration complexity and learning curve
- Factor in community support, documentation, and ecosystem maturity
- Align with project timeline and team capabilities
- Reference specific project requirements when possible

Generate 3-8 suggestions focused on the most relevant options for this specific project context."""

    @staticmethod
    def _build_user_message(
        project_context: ProjectContext,
        dimension: TechDimensionView,
        existing_choices: list[TechChoiceView]
    ) -> ChatMessage:
        """Build user message with complete context."""
        from app.prompts.context_helpers import render_project_context

        # Render project context
        context_text = render_project_context(project_context, include_header=False)

        parts = [
            "**Project Context:**",
            context_text,
            "",
            f"**Target Dimension:** {dimension.name} ({dimension.slug})",
            f"**Description:** {dimension.description}",
        ]

        # Add existing tech choices for context
        if existing_choices:
            parts.append("**Current Technology Choices:**")
            choices_by_dim = SuggestTechStackPrompt._group_choices_by_dimension(existing_choices)
            for dim_name, choices in choices_by_dim.items():
                if choices:
                    choice_summaries = []
                    for choice in choices:
                        item_name = choice.tech_item_name or choice.tech_item_slug or "TBD"
                        choice_summaries.append(f"{item_name} ({choice.role})")
                    parts.append(f"- **{dim_name}**: {', '.join(choice_summaries)}")
        else:
            parts.append("**Current Technology Choices:** None selected yet")

        parts.extend([
            "",
            f"Suggest appropriate technologies for the **{dimension.name}** dimension that align with this project's context, objectives, and constraints.",
            "",
            "Focus on technologies that:",
            "- Support the project's technical objectives and requirements",
            "- Integrate well with existing or likely technology choices",
            "- Match the team's skill level and available timeline",
            "- Provide good ecosystem support and community resources",
            "- Align with the project's scale, complexity, and architectural patterns"
        ])

        return ChatMessage(role="user", content="\n".join(parts))

    @staticmethod
    def _format_catalog_items(items: list) -> str:
        """Format catalog items for system prompt."""
        if not items:
            return "No catalog items available for this dimension."

        # Group by common tags for better organization
        items_by_category = {}
        uncategorized = []

        for item in items:
            if item.tags:
                # Use first tag as primary category
                category = item.tags[0]
                if category not in items_by_category:
                    items_by_category[category] = []
                items_by_category[category].append(item)
            else:
                uncategorized.append(item)

        parts = []

        # Add categorized items
        for category, category_items in sorted(items_by_category.items()):
            parts.append(f"**{category.title()}:**")
            for item in category_items:
                tags_text = f" [{', '.join(item.tags)}]" if item.tags else ""
                description = f" - {item.description}" if item.description else ""
                parts.append(f"- `{item.slug}`: {item.name}{tags_text}{description}")
            parts.append("")

        # Add uncategorized items
        if uncategorized:
            parts.append("**Other:**")
            for item in uncategorized:
                description = f" - {item.description}" if item.description else ""
                parts.append(f"- `{item.slug}`: {item.name}{description}")

        return "\n".join(parts)

    @staticmethod
    def _group_choices_by_dimension(choices: list[TechChoiceView]) -> dict[str, list[TechChoiceView]]:
        """Group tech choices by dimension for context display."""
        groups = {}
        for choice in choices:
            dim_name = choice.dimension_name or choice.dimension_slug
            if dim_name not in groups:
                groups[dim_name] = []
            groups[dim_name].append(choice)
        return groups

    @staticmethod
    def validate_suggestions(
        suggestions: SuggestedTechForDimension,
        dimension: TechDimensionView
    ) -> list[str]:
        """Validate generated tech suggestions for consistency and completeness.

        Args:
            suggestions: Generated suggestions to validate
            dimension: Target dimension with catalog items

        Returns:
            List of validation warnings (empty if valid)
        """
        warnings = []

        # Check dimension slug matches
        if suggestions.dimension_slug != dimension.slug:
            warnings.append(
                f"Dimension slug mismatch: got '{suggestions.dimension_slug}', "
                f"expected '{dimension.slug}'"
            )

        # Validate catalog slug references
        catalog_slugs = {item.slug for item in dimension.items}
        for item in suggestions.items:
            if item.catalog_slug and item.catalog_slug not in catalog_slugs:
                warnings.append(
                    f"Unknown catalog slug '{item.catalog_slug}' - "
                    f"not found in dimension '{dimension.slug}'"
                )

            # Check mutual exclusivity
            if item.catalog_slug and item.free_form_name:
                warnings.append(
                    f"Item has both catalog_slug ('{item.catalog_slug}') and "
                    f"free_form_name ('{item.free_form_name}') - should be one or the other"
                )
            elif not item.catalog_slug and not item.free_form_name:
                warnings.append("Item has neither catalog_slug nor free_form_name")

        # Check for reasonable number of suggestions
        if len(suggestions.items) == 0:
            warnings.append("No suggestions provided")
        elif len(suggestions.items) > 10:
            warnings.append(f"Too many suggestions ({len(suggestions.items)}), maximum is 10")

        # Check confidence score distribution
        confidences = [item.confidence for item in suggestions.items]
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            if avg_confidence < 0.3:
                warnings.append(
                    f"Average confidence is very low ({avg_confidence:.2f}) - "
                    "consider more suitable suggestions"
                )
            elif avg_confidence > 0.95:
                warnings.append(
                    f"Average confidence is unusually high ({avg_confidence:.2f}) - "
                    "ensure realistic confidence scoring"
                )

        # Check for role diversity (should have at least one TARGET)
        roles = {item.role for item in suggestions.items}
        if "target" not in roles:
            warnings.append("No TARGET role suggestions - should include recommended technologies")

        return warnings

    @staticmethod
    def suggest_prompt_optimizations(
        project_context: ProjectContext,
        dimension: TechDimensionView
    ) -> list[str]:
        """Suggest ways to improve prompt effectiveness based on project context.

        Args:
            project_context: Project context to analyze
            dimension: Target dimension

        Returns:
            List of optimization suggestions for better results
        """
        suggestions = []

        # Check for missing context
        if not project_context.objective.strip():
            suggestions.append("Add a clear project objective for better technology alignment")

        if not project_context.tech_choices_by_dimension:
            suggestions.append("Provide existing tech choices to improve compatibility suggestions")

        if not project_context.qa:
            suggestions.append("Answer Q&A questions to provide more context for suggestions")

        # Dimension-specific optimizations
        if dimension.slug == "databases" and "data" not in project_context.objective.lower():
            suggestions.append("Clarify data requirements and scale for better database suggestions")

        if dimension.slug == "cloud_infra" and "budget" not in project_context.objective.lower():
            suggestions.append("Include budget/scale information for infrastructure recommendations")

        if dimension.slug in ["languages", "backend_framework", "frontend_framework"] and not project_context.artifact_summaries:
            suggestions.append("Provide code artifacts to better understand technical requirements")

        return suggestions
