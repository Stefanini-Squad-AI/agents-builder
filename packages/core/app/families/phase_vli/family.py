"""VLI-style phase-based template family implementation."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.families._base import (
    BacklogProposalContext,
    CardDraftContext,
    CardExample,
    GroupingReadmeContext,
    ProjectReadmeContext,
    TemplateFamily,
)
from app.llm.base import ChatMessage, ChatPrompt
from app.schemas.common import ValidationIssue
from app.schemas.llm_io import DraftedCard, ProposedBacklog
from app.schemas.views import CardView, ProjectView


class PhaseVliFamily(TemplateFamily):
    """VLI-style phase-based template family.

    Features:
    - Phase-based grouping with sequential order
    - 10-section card format (Context → Skills → Inputs → Task → Outputs → Acceptance → Deps → Parallel → Gate)
    - Validation rules: ≥1 skill per card, no forward-phase deps
    - File structure: phase-{order}-{slug}/  and  {code}-{title-slug}.md
    """

    # Metadata
    slug = "phase_vli"
    display_name = "Phase-based VLI"
    grouping = "phase"
    grouping_label_singular = "Phase"
    grouping_label_plural = "Phases"
    card_filename_pattern = "{code}-{title_slug}"
    grouping_folder_pattern = "phase-{order}-{slug}"

    def __init__(self) -> None:
        """Initialize the Jinja2 environment for template rendering."""
        # Get the templates directory relative to this file
        templates_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        self.jinja_env.filters['slugify'] = self._slugify

    def render_card(self, card: CardView, context: CardDraftContext) -> str:
        """Render a VLI-format card to markdown."""
        template = self.jinja_env.get_template("card.md.j2")

        return template.render(
            card=card,
            skills_used=context.skills_used,
            project=context.project,
            phase=context.phase,
        )

    def render_grouping_readme(self, context: GroupingReadmeContext) -> str:
        """Render a phase README."""
        template = self.jinja_env.get_template("phase_readme.md.j2")

        return template.render(
            grouping=context.grouping,  # This is a PhaseView
            cards=context.cards,
            skills_referenced=context.skills_referenced,
            project=context.project,
        )

    def render_project_readme(self, context: ProjectReadmeContext) -> str:
        """Render the project-level README."""
        template = self.jinja_env.get_template("project_readme.md.j2")

        return template.render(
            project=context.project,
            phases=context.phases,
            all_cards=context.all_cards,
            all_skills=context.all_skills,
        )

    def draft_card_prompt(self, context: CardDraftContext) -> ChatPrompt[DraftedCard]:
        """Create LLM prompt for drafting VLI card sections."""
        system_prompt = """You are an expert technical project manager specializing in breaking down complex software projects into actionable cards.

Your task is to draft the markdown content for specific sections of a project card. The card follows the VLI (phase-based) template with these sections:
- Context: Background and rationale for this work
- Task: Detailed step-by-step instructions
- Outputs: Specific deliverables expected
- Acceptance criteria: Measurable completion criteria

Write clear, actionable content that a developer can follow without ambiguity. Reference the provided skills and inputs appropriately."""

        # Build context about the project and card
        user_message_parts = [
            f"**Project**: {context.project.name}",
            f"**Objective**: {context.project.objective}",
            f"**Phase**: {context.phase.title}",
            f"**Card**: {context.card.code} — {context.card.title}",
        ]

        if context.project_context:
            user_message_parts.append(f"**Project Context**:\n{context.project_context}")

        if context.skills_used:
            user_message_parts.append("**Skills to use**:")
            for skill in context.skills_used:
                user_message_parts.append(f"- {skill.name}: {skill.description}")

        if context.card.inputs:
            user_message_parts.append("**Inputs available**:")
            for input_item in context.card.inputs:
                user_message_parts.append(f"- {input_item.label}: {input_item.path}")

        if context.upstream_cards:
            user_message_parts.append("**Upstream cards completed**:")
            for upstream in context.upstream_cards:
                user_message_parts.append(f"- {upstream.code}: {upstream.title}")

        if context.sibling_cards_in_phase:
            user_message_parts.append("**Other cards in this phase**:")
            for sibling in context.sibling_cards_in_phase:
                user_message_parts.append(f"- {sibling.code}: {sibling.title}")

        user_message_parts.append("\nDraft the Context, Task, Outputs, and Acceptance Criteria sections for this card.")

        return ChatPrompt(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content="\n\n".join(user_message_parts))
            ],
            response_schema=DraftedCard
        )

    def few_shot_card_examples(self) -> list[CardExample]:
        """Provide VLI-specific few-shot examples."""
        return [
            CardExample(
                title="Database schema analysis",
                context_md="Legacy system uses DB2 with 15+ years of organic growth. Schema documentation is outdated and business rules are embedded in stored procedures.",
                task_md="1. Extract DDL for all tables, indexes, and constraints\n2. Analyze data relationships and foreign keys\n3. Document business rules found in triggers/procedures\n4. Create entity-relationship diagram\n5. Identify potential normalization issues",
                outputs_md="- Complete schema documentation (Markdown)\n- ERD diagram (Mermaid or PNG)\n- Business rules inventory (Excel)\n- Data quality issues report",
                acceptance_criteria_md="- [ ] All tables documented with column descriptions\n- [ ] ERD shows all relationships correctly\n- [ ] Business rules extracted and categorized\n- [ ] Data quality report includes specific issues found",
                explanation="Good analyzer card: systematic data discovery with clear deliverables"
            ),
            CardExample(
                title="Implement user authentication middleware",
                context_md="Application needs JWT-based authentication with role-based access control. Must integrate with existing Active Directory for user management.",
                task_md="1. Install and configure JWT library\n2. Create middleware to validate tokens\n3. Implement role checking logic\n4. Add error handling for expired/invalid tokens\n5. Update route guards to use new middleware\n6. Test with different user roles",
                outputs_md="- Authentication middleware component\n- Role-based route guards\n- Unit tests for auth logic\n- Updated API documentation",
                acceptance_criteria_md="- [ ] JWT tokens are validated on protected routes\n- [ ] Role-based access works correctly\n- [ ] Expired tokens return 401 with clear message\n- [ ] All tests pass with 90%+ coverage",
                explanation="Good procedure card: step-by-step implementation with testable outcomes"
            ),
        ]

    def propose_backlog_prompt(self, context: BacklogProposalContext) -> ChatPrompt[ProposedBacklog]:
        """Create LLM prompt for proposing a phase-based backlog."""
        system_prompt = self._build_backlog_system_prompt()
        user_message = self._build_backlog_user_message(context)

        return ChatPrompt(
            system=system_prompt,
            messages=[user_message],
            response_schema=ProposedBacklog
        )

    def _build_backlog_system_prompt(self) -> str:
        """Build system prompt for backlog proposal with diverse examples."""
        return f"""You are an expert project manager specializing in phase-based software delivery.

**Your Task:**
Create a structured backlog of phases and cards based on the project objective and available skills.

**Phase Structure Guidelines:**
- Adapt phase count (2-7) and names to fit the project objective
- Common patterns: Discovery → Design → Implementation → Testing → Deployment
- For data projects: Analysis → Foundation → Implementation → Validation → Cutover
- For web apps: Planning → Backend → Frontend → Integration → Launch
- Each phase should have 2-6 cards maximum for manageability

**Card Design Guidelines:**
- Each card represents 1-5 days of focused work
- Reference appropriate skills from the available skill set
- Use specific, actionable titles that describe deliverables
- Include both discovery/analysis and implementation work as needed
- Assign realistic story points (1-8, with 5 being average)

**Dependency Guidelines:**
- Phases should flow logically (no backward dependencies)
- Cards within a phase can run in parallel unless explicitly dependent
- Cross-phase dependencies should be clear and necessary
- Avoid creating unnecessary bottlenecks in the critical path

**Code Format:**
- Use project-appropriate prefixes: PROJECT-XYZ where X=phase, YZ=card number
- Example: For "BANKING" project, use BANKING-101, BANKING-102, BANKING-201, etc.

{self._get_diverse_backlog_examples()}

Generate a realistic, deliverable backlog that addresses the full project objective."""

    def _build_backlog_user_message(self, context: BacklogProposalContext) -> ChatMessage:
        """Build user message with project context and skills."""
        from app.prompts.propose_backlog import ProposeBacklogPrompt

        skills_summary = ProposeBacklogPrompt.format_skills_summary(context.proposed_skills)

        content = f"""**Project Context:**
{context.project_context}

**Available Skills:**
{skills_summary}

Please create a phase-based backlog that leverages these skills to deliver the project objective efficiently. Consider the project type and adapt the phase structure accordingly."""

        return ChatMessage(role="user", content=content)

    def _get_diverse_backlog_examples(self) -> str:
        """Provide diverse few-shot examples for different project types."""
        return """
**Example 1: Data Migration Project**
*Objective: Migrate SSIS data pipeline to cloud platform*

```json
{
  "phases": [
    {
      "code": "phase-1-discovery",
      "name": "Discovery & Analysis",
      "description": "Analyze existing systems and extract migration requirements",
      "cards": [
        {
          "code": "MIGRATE-101",
          "title": "SSIS package analysis and rule extraction",
          "type": "Task",
          "story_points": 5,
          "skill_slugs": ["ssis-analyzer", "rule-extractor"],
          "depends_on_codes": [],
          "short_scope_summary": "Complete technical analysis of legacy SSIS packages with business rule documentation."
        }
      ]
    },
    {
      "code": "phase-2-foundation",
      "name": "Platform Foundation",
      "description": "Set up target platform and data models",
      "cards": [
        {
          "code": "MIGRATE-201",
          "title": "Cloud platform setup and schemas",
          "type": "Story",
          "story_points": 8,
          "skill_slugs": ["cloud-architect", "data-modeler"],
          "depends_on_codes": ["MIGRATE-101"],
          "short_scope_summary": "Provision cloud resources and implement target data schemas based on analysis."
        }
      ]
    }
  ],
  "rationale_md": "Two-phase approach separates analysis from implementation for reduced risk and clear handoff points.",
  "critical_path_codes": ["MIGRATE-101", "MIGRATE-201"]
}
```

**Example 2: Web Application Project**
*Objective: Build customer portal with authentication*

```json
{
  "phases": [
    {
      "code": "phase-1-planning",
      "name": "Planning & Design",
      "description": "Define requirements and system architecture",
      "cards": [
        {
          "code": "PORTAL-101",
          "title": "API design and authentication strategy",
          "type": "Task",
          "story_points": 3,
          "skill_slugs": ["api-architect", "auth-designer"],
          "depends_on_codes": [],
          "short_scope_summary": "Design REST API contracts and OAuth2 authentication flow for customer portal."
        }
      ]
    },
    {
      "code": "phase-2-backend",
      "name": "Backend Development",
      "description": "Implement core API and business logic",
      "cards": [
        {
          "code": "PORTAL-201",
          "title": "Customer API implementation",
          "type": "Story",
          "story_points": 5,
          "skill_slugs": ["api-builder", "database-designer"],
          "depends_on_codes": ["PORTAL-101"],
          "short_scope_summary": "Build customer management APIs with database integration and authentication middleware."
        }
      ]
    }
  ],
  "rationale_md": "Backend-first approach ensures solid foundation before frontend development begins.",
  "critical_path_codes": ["PORTAL-101", "PORTAL-201"]
}
```

**Example 3: Platform Enhancement Project**
*Objective: Add real-time monitoring to existing system*

```json
{
  "phases": [
    {
      "code": "phase-1-integration",
      "name": "Monitoring Integration",
      "description": "Integrate monitoring capabilities with existing system",
      "cards": [
        {
          "code": "MONITOR-101",
          "title": "Observability stack implementation",
          "type": "Story",
          "story_points": 8,
          "skill_slugs": ["observability-implementer", "metrics-designer"],
          "depends_on_codes": [],
          "human_gate": true,
          "short_scope_summary": "Deploy Prometheus, Grafana, and OpenTelemetry with custom dashboards and alerts."
        }
      ]
    }
  ],
  "rationale_md": "Single-phase delivery for focused enhancement with human gate for production deployment approval.",
  "critical_path_codes": ["MONITOR-101"]
}
```"""

    def validate_card(self, card: CardView, project: ProjectView) -> list[ValidationIssue]:
        """Validate a card according to VLI rules."""
        issues: list[ValidationIssue] = []

        # Rule: Every card must have ≥ 1 skill
        if not card.skill_links or len(card.skill_links) == 0:
            issues.append(ValidationIssue(
                severity="error",
                message=f"Card {card.code} has no skills assigned",
                location=f"cards.{card.id}.skills"
            ))

        # Rule: skill_resource inputs must reference existing skills
        for input_item in card.inputs:
            if input_item.kind == "skill_resource":
                # Parse skill slug from path (assumes format: skill_slug/resource_name)
                parts = input_item.path.split('/', 1)
                if len(parts) >= 2:
                    skill_slug = parts[0]
                    # Check if this skill is in the card's skills
                    skill_found = any(
                        skill_link.skill.slug == skill_slug
                        for skill_link in card.skill_links
                    )
                    if not skill_found:
                        issues.append(ValidationIssue(
                            severity="error",
                            message=f"Card {card.code} references skill resource '{input_item.path}' but skill '{skill_slug}' is not assigned to this card",
                            location=f"cards.{card.id}.inputs.{input_item.id}"
                        ))

        return issues

    def validate_project(self, project: ProjectView) -> list[ValidationIssue]:
        """Validate the entire project according to VLI rules."""
        issues: list[ValidationIssue] = []

        if not project.phases:
            issues.append(ValidationIssue(
                severity="error",
                message="Project has no phases defined",
                location="project.phases"
            ))
            return issues

        # Rule: No forward-phase dependencies
        for phase in project.phases:
            for card in phase.cards:
                for dep in card.deps_out:
                    if dep.relation == "depends_on":
                        dep_phase_order = dep.depends_on_card.phase.order_no
                        current_phase_order = phase.order_no

                        if dep_phase_order > current_phase_order:
                            issues.append(ValidationIssue(
                                severity="error",
                                message=f"Card {card.code} (Phase {current_phase_order}) depends on {dep.depends_on_card.code} (Phase {dep_phase_order}). Forward-phase dependencies are not allowed.",
                                location=f"cards.{card.id}.dependencies"
                            ))

        # Warning: Each phase should end with a human gate
        for phase in project.phases:
            if phase.cards:
                last_card = max(phase.cards, key=lambda c: c.order_no)
                if not last_card.human_gate:
                    issues.append(ValidationIssue(
                        severity="warning",
                        message=f"Phase '{phase.title}' should end with a human gate (consider adding human_gate=true to card {last_card.code})",
                        location=f"phases.{phase.id}.human_gate"
                    ))

        # Warning: Empty phases
        for phase in project.phases:
            if not phase.cards:
                issues.append(ValidationIssue(
                    severity="warning",
                    message=f"Phase '{phase.title}' has no cards",
                    location=f"phases.{phase.id}.cards"
                ))

        return issues
