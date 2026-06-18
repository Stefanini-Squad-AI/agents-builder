"""DraftCardPrompt: Generate detailed card sections from proposed cards.

This prompt takes a proposed card and rich context to generate detailed card sections:
context, task, outputs, acceptance criteria, inputs, and optional human gate checklists.
The template family provides domain-specific examples and structure guidance.
"""

from __future__ import annotations

import re
from typing import Literal

from app.families._base import CardDraftContext, TemplateFamily
from app.llm.base import ChatPrompt
from app.schemas.llm_io import DraftedCard

# Progressive disclosure level for skill rendering in prompts.
#   L1: slug + name + kind (cheapest — used by ProposeBacklog)
#   L2: + description + "When to invoke" excerpt + resources list (default — used by DraftCard)
#   L3: + full body_md + resources content (most expensive — opt-in only)
SkillDetailLevel = Literal["L1", "L2", "L3"]

# Hard caps to keep prompt budget predictable even with chatty skill bodies.
_BODY_EXCERPT_MAX_CHARS = 800
_RESOURCE_CONTENT_MAX_CHARS = 400
_MAX_RESOURCES_LISTED = 5

# Regex to pull the "When to invoke" / "When to pull" / "Triggers" section out
# of a SKILL.md body. We use this in L2 so the prompt sees the most actionable
# slice of the body without the full markdown bloat.
_WHEN_TO_INVOKE_HEADERS = re.compile(
    r"^#+\s*(when to (invoke|pull|use)|triggers|usage|quando invocar).*$",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_when_to_invoke(body_md: str) -> str | None:
    """Return the body section under a 'When to invoke' header, or None.

    Looks for any markdown header matching the When-to-invoke pattern and
    returns the text up to the next header of equal or higher level.
    Falls back to None when no such section exists — the caller decides
    whether to use the leading paragraph instead.
    """
    if not body_md:
        return None

    match = _WHEN_TO_INVOKE_HEADERS.search(body_md)
    if not match:
        return None

    start = match.end()
    # Find the next header at any level after this section.
    next_header = re.search(r"^#+\s", body_md[start:], re.MULTILINE)
    end = start + next_header.start() if next_header else len(body_md)
    section = body_md[start:end].strip()
    return section or None


def _body_summary(body_md: str) -> str | None:
    """Best-effort short summary of a skill body for L2 rendering.

    Preference order:
      1. Explicit "When to invoke" section.
      2. First paragraph of the body (capped).
    """
    if not body_md or not body_md.strip():
        return None

    when = _extract_when_to_invoke(body_md)
    if when:
        return when[:_BODY_EXCERPT_MAX_CHARS]

    # Fallback: first non-empty paragraph, stripped of markdown headers.
    paragraphs = [
        p.strip()
        for p in re.split(r"\n\s*\n", body_md)
        if p.strip() and not p.strip().startswith("#")
    ]
    if not paragraphs:
        return None
    return paragraphs[0][:_BODY_EXCERPT_MAX_CHARS]


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
    def build_skills_context(
        skills: list,
        level: SkillDetailLevel = "L2",
    ) -> str:
        """Build a summary of available skills for the card.

        Uses progressive disclosure to balance context richness against token
        budget and attention dilution:

        - **L1**: slug + name + kind only. ~30 tokens/skill. Use for
          high-level proposals (e.g. ProposeBacklog) where the LLM only needs
          to know skills exist and what category they belong to.
        - **L2** (default): + description + body excerpt (When-to-invoke
          section, or first paragraph) + resource filenames with purposes.
          ~250-400 tokens/skill. Use for DraftCard and similar prompts that
          need to know *what* each skill can do without the full guidance.
        - **L3**: + full body_md + resource content excerpts. ~1500+
          tokens/skill. Opt-in only; reserve for prompts that genuinely
          need to inline the skill's full guidance.

        Args:
            skills: List of SkillView objects available for this card
            level: Progressive disclosure level (default L2)

        Returns:
            Formatted string describing skills and their purposes
        """
        if not skills:
            return "No specific skills assigned to this card."

        parts = ["**Skills to invoke:**"]

        for skill in skills:
            if level == "L1":
                parts.append(f"- `{skill.slug}`: {skill.name} ({skill.kind})")
                continue

            # L2 and L3 share the structured per-skill block.
            parts.append("")
            parts.append(f"### `{skill.slug}` ({skill.kind})")
            parts.append(f"**Name:** {skill.name}")
            parts.append(f"**Description:** {skill.description}")

            # Body content: excerpt at L2, full at L3.
            body_md = getattr(skill, "body_md", "") or ""
            if level == "L2":
                excerpt = _body_summary(body_md)
                if excerpt:
                    parts.append("")
                    parts.append("**Guidance excerpt:**")
                    parts.append(excerpt)
            elif level == "L3" and body_md.strip():
                parts.append("")
                parts.append("**Full guidance:**")
                parts.append(body_md)

            # Resources: always list (filename + purpose) up to a cap.
            resources = getattr(skill, "resources", []) or []
            if resources:
                shown = resources[:_MAX_RESOURCES_LISTED]
                parts.append("")
                parts.append("**Available resources:**")
                for res in shown:
                    # `purpose` does not exist on SkillResourceView yet, so we
                    # fall back to the first line of content as a hint.
                    hint = ""
                    if res.content:
                        first_line = res.content.strip().splitlines()[0] if res.content.strip() else ""
                        hint = f" — {first_line[:120]}" if first_line else ""
                    parts.append(f"- `{res.filename}` ({res.language}){hint}")
                if len(resources) > _MAX_RESOURCES_LISTED:
                    parts.append(f"- _...and {len(resources) - _MAX_RESOURCES_LISTED} more_")

                # At L3 also inline the resource content (capped).
                if level == "L3":
                    for res in shown:
                        if not res.content:
                            continue
                        content = res.content
                        if len(content) > _RESOURCE_CONTENT_MAX_CHARS:
                            content = content[:_RESOURCE_CONTENT_MAX_CHARS] + "\n…(truncated)"
                        parts.append("")
                        parts.append(f"<details><summary>{res.filename}</summary>\n\n```\n{content}\n```\n\n</details>")

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
