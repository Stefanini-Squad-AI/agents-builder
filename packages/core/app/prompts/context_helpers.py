"""Helper functions for rendering ProjectContext in LLM prompts."""

from __future__ import annotations

from app.schemas.views import ProjectContext


def render_project_context(context: ProjectContext, *, include_header: bool = True) -> str:
    """Render ProjectContext into a consistent markdown format for LLM prompts.

    Args:
        context: The project context to render
        include_header: Whether to include "Project Context" header

    Returns:
        Formatted markdown string suitable for LLM consumption
    """
    parts = []

    if include_header:
        parts.append("## Project Context")
        parts.append("")

    # Always include objective
    parts.append(f"**Objective**: {context.objective}")
    parts.append("")

    # Add Q&A if available
    if context.qa:
        parts.append("**Discovery Questions & Answers:**")
        for question, answer in context.qa.items():
            # Clean up question key (replace underscores with spaces, title case)
            clean_question = question.replace('_', ' ').title()
            parts.append(f"- **{clean_question}**: {answer}")
        parts.append("")

    # Add technology choices if available
    if context.tech_choices_by_dimension:
        parts.append("**Technology Stack:**")
        for dimension, choices in context.tech_choices_by_dimension.items():
            # Clean up dimension name
            clean_dimension = dimension.replace('_', ' ').title()
            choice_names = [choice.tech_item_name or choice.tech_item_slug or "TBD" for choice in choices]
            parts.append(f"- **{clean_dimension}**: {', '.join(choice_names)}")
        parts.append("")

    # Add artifact summaries if available
    if context.artifact_summaries:
        parts.append("**Uploaded Documents:**")
        for artifact in context.artifact_summaries:
            excerpt = artifact.content_md_excerpt or "No content extracted"
            truncated_note = " (truncated)" if artifact.content_md_truncated else ""
            parts.append(f"- **{artifact.filename}** ({artifact.kind}): {excerpt}{truncated_note}")
        parts.append("")

    # Add additional context notes if available
    if context.context_notes_md and context.context_notes_md.strip():
        parts.append("**Additional Notes:**")
        parts.append(context.context_notes_md.strip())
        parts.append("")

    return "\n".join(parts).rstrip()


def render_project_context_compact(context: ProjectContext) -> str:
    """Render ProjectContext in a compact single-paragraph format.

    Useful for prompts where context needs to be brief.

    Args:
        context: The project context to render

    Returns:
        Compact string representation
    """
    parts = [f"Objective: {context.objective}"]

    if context.qa:
        # Full QA answers — no truncation for richer LLM context
        qa_summary = "; ".join([f"{k}: {v}" for k, v in context.qa.items()])
        parts.append(f"Q&A: {qa_summary}")

    if context.tech_choices_by_dimension:
        tech_summary = "; ".join([f"{dim}: {', '.join(choice.tech_item_name or choice.tech_item_slug or 'TBD' for choice in choices)}"
                                 for dim, choices in context.tech_choices_by_dimension.items()])
        parts.append(f"Tech: {tech_summary}")

    if context.artifact_summaries:
        artifact_count = len(context.artifact_summaries)
        parts.append(f"Artifacts: {artifact_count} files uploaded")

    return ". ".join(parts) + "."
