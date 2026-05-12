"""ProposeSkillSet prompt implementation with few-shot examples from seeded data."""

from __future__ import annotations

from app.llm.base import ChatMessage, ChatPrompt
from app.schemas.llm_io import ProposedSkillSet
from app.schemas.views import ProjectContext


class ProposeSkillSetPrompt:
    """Prompt for proposing an initial skill set based on project context.

    Takes a ProjectContext (objective + Q&A + tech choices + artifacts) and
    generates 5-10 skills covering different aspects of the project work.

    Uses few-shot examples from the three reference PoCs:
    - Caixa-2 (SIGLM): Banking modernization with COBOL analysis
    - VLI (CORP): SSIS to Databricks migration
    - Enel (Cronos): Full-stack feature development
    """

    @staticmethod
    def create(context: ProjectContext) -> ChatPrompt[ProposedSkillSet]:
        """Create the ProposeSkillSet prompt with project context.

        Args:
            context: Complete project context from discovery phase

        Returns:
            ChatPrompt ready for LLM execution
        """
        system_prompt = """You are an expert technical project manager specializing in breaking down complex software projects into reusable skills.

Your task is to analyze a project and propose a comprehensive skill set that covers all aspects of the work. Each skill should be:

**Skill Types:**
- **context**: Domain knowledge, architecture, conventions (1-2 per project)
- **analyzer**: Code/data analysis, discovery tools (2-4 per project)
- **authoring**: Creating new code/features (2-4 per project)
- **procedure**: Step-by-step operational tasks (1-3 per project)

**Skill Quality Guidelines:**
- Skills should be **reusable** across similar cards/tasks
- Each skill covers a **distinct capability** with clear boundaries
- Skills should **reference each other** when they build on related work
- Slugs should be **project-prefixed** and descriptive (e.g., "banking-cobol-analyzer")
- Descriptions must include **when to invoke** the skill (trigger scenarios)

**Coverage Strategy:**
- Start with **context** skills for domain knowledge
- Add **analyzer** skills for discovery/assessment work
- Include **authoring** skills for implementation work
- Add **procedure** skills for deployment/operational tasks
- Ensure skills cover the full project lifecycle

Generate 5-10 skills that comprehensively address the project objective."""

        user_message = ProposeSkillSetPrompt._build_user_message(context)

        return ChatPrompt(
            system=system_prompt,
            messages=[
                ChatMessage(role="user", content=user_message)
            ],
            response_schema=ProposedSkillSet
        )

    @staticmethod
    def _build_user_message(context: ProjectContext) -> str:
        """Build the user message with project context and few-shot examples."""

        # Start with project context
        message_parts = [
            f"**Project Objective**: {context.objective}",
            ""
        ]

        # Add Q&A context if available
        if context.qa:
            message_parts.append("**Discovery Q&A:**")
            for question, answer in context.qa.items():
                message_parts.append(f"- **{question}**: {answer}")
            message_parts.append("")

        # Add tech choices if available
        if context.tech_choices_by_dimension:
            message_parts.append("**Technology Choices:**")
            for dimension, choices in context.tech_choices_by_dimension.items():
                choice_names = [choice.tech_item_name or choice.tech_item_slug or "TBD" for choice in choices]
                message_parts.append(f"- **{dimension}**: {', '.join(choice_names)}")
            message_parts.append("")

        # Add artifact summaries if available
        if context.artifact_summaries:
            message_parts.append("**Uploaded Artifacts:**")
            for artifact in context.artifact_summaries:
                excerpt = artifact.content_md_excerpt or "No content extracted"
                truncated_note = " (truncated)" if artifact.content_md_truncated else ""
                message_parts.append(f"- **{artifact.filename}**: {excerpt}{truncated_note}")
            message_parts.append("")

        # Add context notes if available
        if context.context_notes_md:
            message_parts.append("**Additional Context:**")
            message_parts.append(context.context_notes_md)
            message_parts.append("")

        # Add few-shot examples
        message_parts.extend([
            "**Examples from similar projects:**",
            "",
            ProposeSkillSetPrompt._get_few_shot_examples(),
            "",
            "Based on this project context, propose a comprehensive skill set that covers all aspects of the work from discovery through implementation to deployment."
        ])

        return "\n".join(message_parts)

    @staticmethod
    def _get_few_shot_examples() -> str:
        """Get few-shot examples from the three reference PoCs."""
        return """**Example 1: Banking Legacy Modernization (Caixa-2 SIGLM)**
*Objective: Modernize COBOL-based banking limits system to Java/Angular*

```json
{
  "skills": [
    {
      "slug": "siglm-context",
      "name": "SIGLM Project Context",
      "description": "Canonical knowledge base for banking limits modernization - architecture, domain glossary, DB2->Postgres mapping, COBOL conventions. Use when user asks about banking limits, legacy systems, or domain concepts.",
      "kind": "context",
      "rationale": "Banking domain is complex with many legacy conventions that need centralized documentation",
      "sibling_refs": ["siglm-cobol-analyzer"]
    },
    {
      "slug": "siglm-cobol-analyzer",
      "name": "SIGLM COBOL -> Rules",
      "description": "Extract business rules from legacy COBOL batch programs and translate to neutral specs. Use when analyzing GLMTB013, GLMTBC01, or other COBOL source files for rule extraction.",
      "kind": "analyzer",
      "rationale": "COBOL programs contain embedded business logic that must be extracted before modernization",
      "sibling_refs": ["siglm-context", "siglm-spring-backend"]
    }
  ],
  "coverage_notes": "Covers domain context and legacy code analysis for banking modernization",
  "gaps": ["Frontend component patterns", "Database migration procedures"]
}
```

**Example 2: Data Pipeline Migration (VLI CORP)**
*Objective: Migrate SSIS ETL packages to Databricks Delta Lake*

```json
{
  "skills": [
    {
      "slug": "corp-ssis-analyzer",
      "name": "CORP SSIS Package Analyzer",
      "description": "Analyze SSIS packages (.dtsx XML) to produce business flow summary, data flow diagram, and task inventory. Use when provided with SSIS .dtsx files for migration assessment.",
      "kind": "analyzer",
      "rationale": "SSIS packages are complex XML with embedded logic that needs systematic analysis",
      "sibling_refs": ["corp-databricks-planner"]
    },
    {
      "slug": "corp-databricks-planner",
      "name": "CORP Databricks Migration Planner",
      "description": "Plan migration of ETL workflows to Databricks notebooks and Delta tables. Use after SSIS analysis to design target architecture.",
      "kind": "procedure",
      "rationale": "Migration requires careful planning of data flows, transformations, and scheduling",
      "sibling_refs": ["corp-ssis-analyzer", "corp-delta-merge"]
    }
  ],
  "coverage_notes": "Covers SSIS analysis and Databricks migration planning for ETL modernization",
  "gaps": ["Data quality validation", "Performance optimization strategies"]
}
```

**Example 3: Full-Stack Feature Development (Enel Cronos)**
*Objective: Add role-based access control to NestJS/Angular application*

```json
{
  "skills": [
    {
      "slug": "cronos-add-feature",
      "name": "Cronos Add Full-Stack Feature",
      "description": "End-to-end workflow for adding features touching Prisma schema + NestJS endpoint + Angular frontend. Use when adding new domain entities, modules, or data-driven pages.",
      "kind": "authoring",
      "rationale": "Full-stack features require coordinated changes across multiple layers with consistent patterns",
      "sibling_refs": ["cronos-frontend-conventions", "cronos-role-access"]
    },
    {
      "slug": "cronos-frontend-conventions",
      "name": "Cronos Frontend Conventions",
      "description": "Angular component patterns, routing structure, and UI conventions for Cronos project. Use when creating new Angular components, pages, or updating frontend architecture.",
      "kind": "context",
      "rationale": "Consistent frontend patterns improve maintainability and developer experience",
      "sibling_refs": ["cronos-add-feature"]
    }
  ],
  "coverage_notes": "Covers full-stack development patterns and frontend conventions",
  "gaps": ["Authentication integration", "API testing procedures"]
}
```"""
