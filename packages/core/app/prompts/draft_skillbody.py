"""DraftSkillBodyPrompt: Generate individual skill bodies with resources based on kind biases.

This prompt takes a proposed skill and project context to generate:
1. The markdown body content (below YAML frontmatter)
2. Appropriate resources based on skill kind biases
3. References to sibling skills where relevant

Resource biases by skill kind:
- context: Documentation, reference materials, domain glossaries
- analyzer: Checklists, analysis frameworks, SQL scripts, audit templates
- authoring: Code samples, configuration templates, implementation guides
- procedure: Step-by-step checklists, workflow templates, validation guides
"""

from __future__ import annotations

from app.enums import SkillKind, SkillResourceLanguage
from app.llm.base import ChatMessage, ChatPrompt
from app.schemas.llm_io import DraftedSkillBody
from app.schemas.views import ProjectContext, SkillView


class DraftSkillBodyPrompt:
    """LLM prompt for drafting individual skill bodies with appropriate resources."""

    @staticmethod
    def create(
        skill: SkillView,
        project_context: ProjectContext,
        sibling_skills: list[SkillView],
        identified_gaps: list[str] | None = None,
    ) -> ChatPrompt:
        """Create a prompt for drafting a skill body.

        Args:
            skill: The skill to draft body content for
            project_context: Full project context for relevant information
            sibling_skills: Other skills in the project for cross-referencing
            identified_gaps: Coverage gaps surfaced by ProposeSkillSet. The
                draft will be asked to address gaps that are naturally adjacent
                to this skill's scope. Pass None or [] when there are no gaps.

        Returns:
            ChatPrompt configured for skill body drafting
        """
        system_prompt = DraftSkillBodyPrompt._build_system_prompt(skill.kind)
        user_message = DraftSkillBodyPrompt._build_user_message(
            skill, project_context, sibling_skills, identified_gaps or []
        )

        return ChatPrompt(
            system=system_prompt,
            messages=[user_message],
            response_schema=DraftedSkillBody
        )

    @staticmethod
    def _build_system_prompt(skill_kind: SkillKind) -> str:
        """Build system prompt with kind-specific resource biases."""

        resource_guidance = DraftSkillBodyPrompt._get_resource_guidance_for_kind(skill_kind)

        return f"""You are drafting the body content for a skill in an AI agent development project.

**Your Task:**
Generate the markdown body content (below YAML frontmatter) and appropriate resources for a {skill_kind} skill.

**Skill Body Guidelines:**
- Write practical, actionable content that helps developers accomplish the skill's purpose
- Use markdown formatting with clear section headers
- Include specific examples, code snippets, or references where helpful
- End with a "When to pull in sibling skills" section referencing related skills
- Keep the tone professional but approachable
- Focus on the "how" and "when" rather than just the "what"

**Resource Guidelines for {skill_kind.upper()} skills:**
{resource_guidance}

**IMPORTANT - Resource Format:**
Each resource MUST have exactly these fields:
- `filename`: A descriptive filename with extension (e.g., "analysis_checklist.md", "profiling_queries.sql")
- `language`: One of: "markdown", "sql", "yaml", "python", "plain"
- `content`: The full content of the resource file (keep concise, max 500 words per resource)
- `purpose`: One sentence explaining why this resource exists

**IMPORTANT - Be Concise:**
- Limit body_md to 800-1200 words
- Include 2-3 resources maximum
- Focus on actionable, practical content

**Cross-References:**
- Reference sibling skills by slug in the body when relevant
- List sibling skill slugs you reference in `sibling_skills_referenced`
- Only reference skills that actually exist in the provided list

**Output Requirements:**
- `body_md`: Complete markdown content (no YAML frontmatter)
- `resources`: List of helpful resources following the kind-specific patterns
- `sibling_skills_referenced`: Actual slugs mentioned in the body
- `addressed_gaps`: Verbatim titles from the "Identified Coverage Gaps" block (if any) that this body genuinely addresses. Leave empty when none apply — do not pad.

Be specific and practical. Developers should be able to follow your guidance immediately."""

    @staticmethod
    def _get_resource_guidance_for_kind(skill_kind: SkillKind) -> str:
        """Get resource creation guidance specific to skill kind."""

        if skill_kind == SkillKind.CONTEXT:
            return """**Context skills should include resources like:**
- Domain glossaries (markdown)
- Architecture diagrams as text (markdown)
- Reference documentation (markdown)
- Configuration examples (yaml/plain)
- Key mappings or lookup tables (markdown)

Focus on canonical knowledge that developers reference repeatedly."""

        elif skill_kind == SkillKind.ANALYZER:
            return """**Analyzer skills should include resources like:**
- Analysis checklists (markdown)
- Audit frameworks (markdown)
- SQL queries for data profiling (sql)
- Classification templates (yaml)
- Quality assessment rubrics (markdown)

Focus on systematic approaches to understanding existing systems."""

        elif skill_kind == SkillKind.AUTHORING:
            return """**Authoring skills should include resources like:**
- Code templates and examples (python/sql/yaml)
- Configuration templates (yaml)
- Implementation guides (markdown)
- Best practices checklists (markdown)
- Common patterns and snippets (python/sql)

Focus on accelerating creation of new code and configurations."""

        elif skill_kind == SkillKind.PROCEDURE:
            return """**Procedure skills should include resources like:**
- Step-by-step checklists (markdown)
- Workflow templates (yaml/markdown)
- Validation checklists (markdown)
- Approval process guides (markdown)
- Troubleshooting guides (markdown)

Focus on ensuring consistent execution of multi-step processes."""

        else:
            return """**Generic resource guidance:**
- Include 1-3 resources that directly support the skill's purpose
- Use appropriate file extensions and languages
- Keep resources focused and practical
- Avoid duplicating content that's already in the body"""

    @staticmethod
    def _build_user_message(
        skill: SkillView,
        project_context: ProjectContext,
        sibling_skills: list[SkillView],
        identified_gaps: list[str],
    ) -> ChatMessage:
        """Build the user message with skill and context information."""

        from app.prompts.context_helpers import render_project_context_compact

        # Format sibling skills for reference
        sibling_list = "\n".join([
            f"- `{s.slug}`: {s.name} ({s.kind})"
            for s in sibling_skills
        ]) if sibling_skills else "No sibling skills available"

        # Get compact project context
        project_summary = render_project_context_compact(project_context)

        # Optional gaps block: only inject when gaps exist, to avoid pulling
        # the model toward generic content when there's nothing to address.
        gaps_block = ""
        if identified_gaps:
            bullet_list = "\n".join(f"- {g}" for g in identified_gaps)
            gaps_block = f"""

**Identified Coverage Gaps (project-wide):**
These gaps were flagged when the skill set was proposed. If any gap is
naturally adjacent to THIS skill's scope, address it in the body (and only
then). Do not force coverage of unrelated gaps — leave those to other skills.
{bullet_list}"""

        content = f"""**Project Context:**
{project_summary}{gaps_block}

**Skill to Draft:**
- **Slug**: `{skill.slug}`
- **Name**: {skill.name}
- **Kind**: {skill.kind}
- **Description**: {skill.description}

**Available Sibling Skills for Cross-Reference:**
{sibling_list}

Please draft the skill body content and appropriate resources following the guidelines for {skill.kind} skills. Make the content practical and actionable for developers working on this project."""

        return ChatMessage(role="user", content=content)

    @staticmethod
    def get_recommended_resource_count(skill_kind: SkillKind) -> int:
        """Get the recommended number of resources for a skill kind."""
        return {
            SkillKind.CONTEXT: 2,      # Reference docs, glossaries
            SkillKind.ANALYZER: 3,     # Checklists, frameworks, queries
            SkillKind.AUTHORING: 2,    # Templates, examples
            SkillKind.PROCEDURE: 3,    # Checklists, workflows, validation
        }.get(skill_kind, 2)

    @staticmethod
    def get_preferred_languages(skill_kind: SkillKind) -> list[SkillResourceLanguage]:
        """Get preferred resource languages for a skill kind."""
        return {
            SkillKind.CONTEXT: [
                SkillResourceLanguage.MARKDOWN,
                SkillResourceLanguage.YAML,
                SkillResourceLanguage.PLAIN
            ],
            SkillKind.ANALYZER: [
                SkillResourceLanguage.MARKDOWN,
                SkillResourceLanguage.SQL,
                SkillResourceLanguage.YAML
            ],
            SkillKind.AUTHORING: [
                SkillResourceLanguage.PYTHON,
                SkillResourceLanguage.SQL,
                SkillResourceLanguage.YAML,
                SkillResourceLanguage.MARKDOWN
            ],
            SkillKind.PROCEDURE: [
                SkillResourceLanguage.MARKDOWN,
                SkillResourceLanguage.YAML,
                SkillResourceLanguage.PLAIN
            ],
        }.get(skill_kind, [SkillResourceLanguage.MARKDOWN, SkillResourceLanguage.YAML])
