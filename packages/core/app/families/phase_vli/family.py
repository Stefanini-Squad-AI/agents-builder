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
            depends_on_links=context.depends_on_links,
            parallel_with_links=context.parallel_with_links,
        )

    def render_grouping_readme(self, context: GroupingReadmeContext) -> str:
        """Render a phase README."""
        template = self.jinja_env.get_template("phase_readme.md.j2")

        return template.render(
            grouping=context.grouping,  # This is a PhaseView
            cards=context.cards,
            skills_referenced=context.skills_referenced,
            project=context.project,
            card_links=context.card_links,
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
        system_prompt = self._build_card_draft_system_prompt()
        user_message = self._build_card_draft_user_message(context)

        return ChatPrompt(
            system=system_prompt,
            messages=[user_message],
            response_schema=DraftedCard
        )

    def _build_card_draft_system_prompt(self) -> str:
        """Build system prompt for card drafting with examples."""
        return f"""You are an expert technical project manager specializing in breaking down complex software projects into actionable cards.

**Your Task:**
Draft detailed markdown content for specific sections of a project card following the VLI (phase-based) template.

**Required Sections:**
- **Context**: Background, rationale, and how this work fits into the project flow
- **Task**: Detailed step-by-step instructions that a developer can follow
- **Outputs**: Specific deliverables, files, and artifacts expected
- **Acceptance Criteria**: Measurable, testable checkboxes for completion validation
- **Inputs**: Files, resources, and dependencies needed (skill resources, artifacts, external data)

**Quality Guidelines:**
- Write actionable, specific instructions (not vague descriptions)
- Include concrete file paths, naming conventions, and technical details
- Make acceptance criteria testable from outputs alone
- Reference skills appropriately for implementation guidance
- Consider dependencies and build on upstream card outputs
- Include human gate checklists only when card.human_gate is true

**Input Types:**
- `skill_resource`: References to .agents/skills/[skill-slug]/resources/[file]
- `artifact`: Project data in data/projects/[project-slug]/artifacts/
- `external`: External files, databases, APIs, or legacy systems

{self._get_card_draft_examples()}

Write professional, detailed content that enables successful project execution."""

    def _build_card_draft_user_message(self, context: CardDraftContext) -> ChatMessage:
        """Build user message with complete card context."""
        from app.prompts.draft_card import DraftCardPrompt

        # Build context sections
        parts = [
            f"**Project**: {context.project.name}",
            f"**Objective**: {context.project.objective}",
            f"**Phase**: {context.phase.name}",
            f"**Card**: {context.card.code} — {context.card.title}",
            f"**Type**: {context.card.type} ({context.card.story_points} story points)",
        ]

        if context.project_context:
            parts.append(f"**Project Context**:\n{context.project_context}")

        # Skills context
        if context.skills_used:
            skills_context = DraftCardPrompt.build_skills_context(context.skills_used)
            parts.append(skills_context)

        # Dependency context
        dependency_context = DraftCardPrompt.build_dependency_context(context)
        parts.append(dependency_context)

        # Human gate note
        if context.card.human_gate:
            parts.append("**Note**: This card has human_gate=true - include human_gate_checklist_md")

        parts.append("Draft the Context, Task, Outputs, Acceptance Criteria sections and suggest appropriate Inputs for this card.")

        return ChatMessage(role="user", content="\n\n".join(parts))

    def _get_card_draft_examples(self) -> str:
        """Get few-shot examples for card drafting."""
        return """
**Example 1: Analysis Card**
*Card: MIGRATE-101 — Legacy system data analysis*

```json
{
  "context_md": "Legacy system contains 15 years of customer data across 8 databases. Current documentation is outdated and business rules are embedded in stored procedures. This analysis provides foundation for migration design.",
  "task_md": "1. Connect to legacy SQL Server instances using provided credentials\\n2. Execute schema extraction queries for each database\\n3. Document table relationships and foreign key constraints\\n4. Extract business rules from stored procedures and triggers\\n5. Profile data quality (nulls, duplicates, referential integrity)\\n6. Create consolidated data inventory spreadsheet\\n7. Flag potential migration blockers and data issues",
  "outputs_md": "- `discovery/legacy-schema-analysis.md` with complete table documentation\\n- `discovery/business-rules-inventory.xlsx` categorized by domain\\n- `discovery/data-quality-report.md` with specific issues and counts\\n- `discovery/migration-blockers.md` with risk assessment and owners",
  "acceptance_criteria_md": "- [ ] All 47 tables documented with column descriptions and constraints\\n- [ ] Business rules extracted and categorized by business domain\\n- [ ] Data quality issues quantified with row counts and percentages\\n- [ ] Migration blockers identified with specific resolution owners\\n- [ ] ERD diagram shows all table relationships correctly",
  "inputs": [
    {"kind": "skill_resource", "path": ".agents/skills/legacy-analyzer/SKILL.md", "label": "Legacy analysis methodology"},
    {"kind": "skill_resource", "path": ".agents/skills/legacy-analyzer/resources/schema-extraction-queries.sql", "label": "SQL queries for schema discovery"},
    {"kind": "external", "path": "legacy/database-connection-strings.txt", "label": "Database connection details"}
  ]
}
```

**Example 2: Implementation Card**
*Card: API-201 — User authentication service*

```json
{
  "context_md": "Application requires JWT-based authentication with role-based access control. Must integrate with existing Active Directory for user validation and support multiple client applications.",
  "task_md": "1. Set up JWT library (jsonwebtoken) and configure secret key rotation\\n2. Implement `/auth/login` endpoint with AD integration\\n3. Create middleware for token validation on protected routes\\n4. Add role-based access control with user permissions matrix\\n5. Implement token refresh mechanism with sliding expiration\\n6. Add comprehensive error handling for auth failures\\n7. Create API documentation with authentication examples",
  "outputs_md": "- `src/auth/auth-service.js` with login and token validation logic\\n- `src/middleware/auth-middleware.js` for route protection\\n- `src/auth/roles.js` with permissions matrix and role definitions\\n- `docs/authentication-api.md` with usage examples and error codes\\n- Unit tests achieving 90%+ coverage for auth logic",
  "acceptance_criteria_md": "- [ ] Login endpoint validates credentials against Active Directory\\n- [ ] JWT tokens include user roles and expire appropriately\\n- [ ] Protected routes return 401 for invalid/expired tokens\\n- [ ] Role-based access control blocks unauthorized actions\\n- [ ] Token refresh works without requiring re-authentication\\n- [ ] All authentication errors return consistent error format\\n- [ ] API documentation includes working curl examples",
  "inputs": [
    {"kind": "skill_resource", "path": ".agents/skills/api-security/SKILL.md", "label": "API security best practices"},
    {"kind": "skill_resource", "path": ".agents/skills/api-security/resources/jwt-implementation-guide.md", "label": "JWT implementation patterns"},
    {"kind": "artifact", "path": "data/projects/app/artifacts/AD-001-outputs/user-schema.json", "label": "Active Directory user schema from discovery"}
  ]
}
```

**Example 3: Infrastructure Card**
*Card: INFRA-101 — Container orchestration setup*

```json
{
  "context_md": "Application deployment currently manual and error-prone. Need containerized deployment with orchestration for scalability and reliability. This card establishes the foundation for automated deployments.",
  "task_md": "1. Create multi-stage Dockerfile optimized for production\\n2. Set up Kubernetes cluster configuration (3 nodes minimum)\\n3. Configure ingress controller with SSL termination\\n4. Implement horizontal pod autoscaling (HPA) rules\\n5. Set up persistent volume claims for database storage\\n6. Configure monitoring with Prometheus and Grafana dashboards\\n7. Create deployment pipeline with health checks",
  "outputs_md": "- `docker/Dockerfile` with optimized multi-stage build\\n- `k8s/` directory with all Kubernetes manifests\\n- `k8s/ingress.yaml` with SSL and routing configuration\\n- `monitoring/prometheus-config.yaml` with custom metrics\\n- `docs/deployment-guide.md` with step-by-step instructions",
  "acceptance_criteria_md": "- [ ] Application builds and runs in Docker container locally\\n- [ ] Kubernetes cluster deploys application successfully\\n- [ ] Ingress routes traffic correctly with HTTPS\\n- [ ] HPA scales pods based on CPU usage (tested with load)\\n- [ ] Database persists data across pod restarts\\n- [ ] Monitoring dashboards show key application metrics\\n- [ ] Deployment can be executed by following documentation alone",
  "human_gate_checklist_md": "Production deployment approval:\\n- [ ] Security team reviewed ingress and network policies\\n- [ ] Database backup strategy confirmed\\n- [ ] Monitoring alerts configured and tested\\n- [ ] Rollback procedure documented and verified",
  "inputs": [
    {"kind": "skill_resource", "path": ".agents/skills/container-orchestrator/SKILL.md", "label": "Container orchestration patterns"},
    {"kind": "skill_resource", "path": ".agents/skills/container-orchestrator/resources/k8s-templates.yaml", "label": "Kubernetes configuration templates"},
    {"kind": "external", "path": "infrastructure/cluster-specs.json", "label": "Target cluster specifications"}
  ]
}
```"""

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
