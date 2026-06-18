"""Migration template family implementation.

7-phase migration structure optimized for ETL migrations (SSIS → Databricks, etc.).

Phases:
1. Discovery & Assessment
2. Infrastructure Foundation  
3. Data Transformation (Silver)
4. Data Aggregation (Gold)
5. Business Rules Implementation
6. Cutover Preparation
7. Parallel Run & Validation
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

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


# Fixed 7-phase structure for migrations
MIGRATION_PHASES = [
    {
        "code": "phase-1-discovery",
        "name": "Discovery & Assessment",
        "order_no": 1,
        "description_md": "Analyze source packages, extract connection points, identify patterns and risks.",
    },
    {
        "code": "phase-2-foundation",
        "name": "Infrastructure Foundation",
        "order_no": 2,
        "description_md": "Set up target infrastructure, configure connections, establish naming conventions.",
    },
    {
        "code": "phase-3-silver",
        "name": "Data Transformation (Silver)",
        "order_no": 3,
        "description_md": "Implement core data transformations, create Silver layer tables.",
    },
    {
        "code": "phase-4-gold",
        "name": "Data Aggregation (Gold)",
        "order_no": 4,
        "description_md": "Build aggregated views, create Gold layer analytics tables.",
    },
    {
        "code": "phase-5-business-rules",
        "name": "Business Rules Implementation",
        "order_no": 5,
        "description_md": "Implement soft deletes, SCD logic, and complex business rules.",
    },
    {
        "code": "phase-6-cutover",
        "name": "Cutover Preparation",
        "order_no": 6,
        "description_md": "Plan and prepare for production cutover, document rollback procedures.",
    },
    {
        "code": "phase-7-validation",
        "name": "Parallel Run & Validation",
        "order_no": 7,
        "description_md": "Run source and target in parallel, validate data reconciliation, sign off.",
    },
]


class MigrationFamily(TemplateFamily):
    """Migration template family for ETL migrations.

    Features:
    - Fixed 7-phase structure based on real-world migration experience
    - Migration-specific card format with automation_level field
    - Validation rules for migration workflows
    - Few-shot examples from ETL migration domain
    """

    # Metadata
    slug = "migration"
    display_name = "ETL Migration"
    grouping: Literal["phase", "epic", "flat"] = "phase"
    grouping_label_singular = "Phase"
    grouping_label_plural = "Phases"
    card_filename_pattern = "{code}-{title_slug}"
    grouping_folder_pattern = "phase-{order}-{slug}"

    def __init__(self) -> None:
        """Initialize the Jinja2 environment for template rendering."""
        templates_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.jinja_env.filters["slugify"] = self._slugify

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to URL-safe slug."""
        return text.lower().replace(" ", "-").replace("_", "-")

    @classmethod
    def get_phases(cls) -> list[dict]:
        """Get the fixed 7-phase structure for migrations."""
        return MIGRATION_PHASES.copy()

    def render_card(self, card: CardView, context: CardDraftContext) -> str:
        """Render a migration card to markdown."""
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
            grouping=context.grouping,
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
        """Create LLM prompt for drafting migration card sections."""
        system_prompt = self._build_card_draft_system_prompt()
        user_message = self._build_card_draft_user_message(context)

        return ChatPrompt(
            system=system_prompt,
            messages=[user_message],
            response_schema=DraftedCard,
        )

    def _build_card_draft_system_prompt(self) -> str:
        """Build system prompt for migration card drafting."""
        return """You are an expert ETL migration architect specializing in migrating legacy ETL systems (SSIS, Informatica, etc.) to modern cloud platforms (Databricks, Snowflake, etc.).

**Your Task:**
Draft detailed markdown content for migration card sections following the Migration template.

**Migration Card Sections:**
- **Context**: Background on what's being migrated, source/target systems, dependencies
- **Task**: Step-by-step migration instructions with specific technical details
- **Outputs**: Specific deliverables (notebooks, tables, documentation)
- **Acceptance Criteria**: Testable validation criteria for migration success
- **Inputs**: Source artifacts, skill resources, configuration files

**Automation Levels:**
- `auto`: Fully automated migration (simple patterns)
- `auto_hitl`: Automated with human review (standard patterns)
- `hitl`: Human-in-the-loop required (complex business logic)

**Quality Guidelines:**
- Include specific table names, column mappings, and transformation logic
- Reference source package artifacts and target notebook paths
- Include data validation criteria (row counts, aggregates, checksums)
- Consider incremental vs full load modes
- Include rollback and recovery procedures where appropriate

""" + self._get_migration_examples()

    def _build_card_draft_user_message(self, context: CardDraftContext) -> ChatMessage:
        """Build user message with migration-specific context."""
        from app.prompts.draft_card import DraftCardPrompt

        parts = [
            f"**Migration Project**: {context.project.name}",
            f"**Objective**: {context.project.objective}",
            f"**Phase**: {context.phase.name}",
            f"**Card**: {context.card.code} — {context.card.title}",
            f"**Type**: {context.card.type} ({context.card.story_points} story points)",
        ]

        if context.project_context:
            parts.append(f"**Project Context**:\n{context.project_context}")

        if context.skills_used:
            skills_context = DraftCardPrompt.build_skills_context(context.skills_used)
            parts.append(skills_context)

        dependency_context = DraftCardPrompt.build_dependency_context(context)
        parts.append(dependency_context)

        if context.card.human_gate:
            parts.append("**Note**: This card has human_gate=true - include human_gate_checklist_md")

        parts.append("Draft the Context, Task, Outputs, Acceptance Criteria sections and suggest appropriate Inputs for this migration card.")

        return ChatMessage(role="user", content="\n\n".join(parts))

    def _get_migration_examples(self) -> str:
        """Get migration-specific few-shot examples."""
        return """
**Example 1: Discovery Phase Card**
*Card: MIGRATE-101 — Analyze SSIS package connection points*

```json
{
  "context_md": "Package PKG_DAILY_SALES.dtsx processes daily sales data from the DW_Sales database. Uses 3 connection managers (OLEDB_DW_Sales, OLEDB_STG_Sales, FTP_Reports) and includes both incremental and full reload modes controlled by the @ProcessingMode variable.",
  "task_md": "1. Extract all ConnectionManager elements from package XML\\n2. Document source tables: stg.raw_orders, stg.raw_returns, dim.products\\n3. Document target tables: bronze.fact_daily_sales\\n4. Identify execution modes by analyzing precedence constraints\\n5. Extract SQL queries from ExecuteSQLTask elements\\n6. Document any Script Tasks requiring manual conversion\\n7. Create connection mapping to Databricks Unity Catalog",
  "outputs_md": "- `discovery/PKG_DAILY_SALES_analysis.md` with complete package documentation\\n- `discovery/connection_mapping.yaml` with source→target connection mapping\\n- `discovery/table_lineage.json` with source/target table relationships\\n- Feedback items created for any ambiguous business rules",
  "acceptance_criteria_md": "- [ ] All 3 connection managers documented with target equivalents\\n- [ ] All source tables (3) and target tables (1) identified\\n- [ ] Both execution modes (incremental/full) documented\\n- [ ] SQL logic extracted and formatted\\n- [ ] Script Tasks flagged for manual review\\n- [ ] Connection mapping validated by data team",
  "inputs": [
    {"kind": "project_artifact", "path": "artifacts/PKG_DAILY_SALES.dtsx", "label": "Source SSIS package"},
    {"kind": "skill_resource", "path": ".agents/skills/ssis-analyzer/resources/connection-extraction.md", "label": "Connection extraction guide"}
  ]
}
```

**Example 2: Silver Layer Card**
*Card: MIGRATE-301 — Implement fact_daily_sales transformation*

```json
{
  "context_md": "Migrating PKG_DAILY_SALES to Databricks. Source reads from 3 staging tables, applies currency conversion and date enrichment, then writes to bronze.fact_daily_sales. Must support both incremental (MERGE) and full reload (OVERWRITE) modes.",
  "task_md": "1. Create notebook `silver/fact_daily_sales.py` with Spark transformations\\n2. Implement read from bronze tables with schema validation\\n3. Apply currency conversion using dim_currency lookup\\n4. Enrich with date dimension attributes\\n5. Implement MERGE logic for incremental mode (match on order_id)\\n6. Implement OVERWRITE logic for full reload mode\\n7. Add data quality checks (null counts, referential integrity)\\n8. Configure notebook parameters for execution mode",
  "outputs_md": "- `silver/fact_daily_sales.py` Databricks notebook\\n- `tests/test_fact_daily_sales.py` unit tests\\n- Updated `workflows/daily_sales.yml` with notebook task\\n- `docs/fact_daily_sales_mapping.md` column-level mapping documentation",
  "acceptance_criteria_md": "- [ ] Notebook executes successfully in both modes\\n- [ ] Row counts match source within 0.1% tolerance\\n- [ ] Aggregate totals (SUM(amount)) match within $0.01\\n- [ ] All lookup joins succeed (no null foreign keys)\\n- [ ] Unit tests pass with 90%+ coverage\\n- [ ] Execution time < 30 minutes for full reload",
  "inputs": [
    {"kind": "skill_resource", "path": ".agents/skills/databricks-transformer/SKILL.md", "label": "Transformation patterns"},
    {"kind": "project_artifact", "path": "discovery/PKG_DAILY_SALES_analysis.md", "label": "Package analysis from discovery"},
    {"kind": "external", "path": "bronze.fact_daily_sales", "label": "Target Delta table"}
  ]
}
```

**Example 3: Validation Phase Card**
*Card: MIGRATE-701 — Parallel run reconciliation for sales pipeline*

```json
{
  "context_md": "Sales pipeline migration complete. Need to run source (SSIS) and target (Databricks) in parallel for 2 weeks and validate data consistency. Pipeline processes ~500K records daily.",
  "task_md": "1. Configure dual-write mode: SSIS writes to SQL Server, Databricks writes to Delta\\n2. Create reconciliation notebook comparing daily outputs\\n3. Implement row count comparison by date partition\\n4. Implement aggregate comparison (SUM, AVG, MIN, MAX) with tolerance\\n5. Create discrepancy report for any mismatches\\n6. Set up alerting for reconciliation failures\\n7. Document sign-off criteria and create approval workflow",
  "outputs_md": "- `validation/reconciliation_sales.py` comparison notebook\\n- `validation/reconciliation_report.html` daily report\\n- `docs/signoff_checklist.md` migration sign-off document\\n- Dashboard showing reconciliation metrics over time",
  "acceptance_criteria_md": "- [ ] Row counts match 100% for 14 consecutive days\\n- [ ] Aggregate totals match within 0.01% tolerance\\n- [ ] No critical discrepancies requiring investigation\\n- [ ] Sign-off obtained from data owner and QA lead\\n- [ ] Rollback procedure tested and documented\\n- [ ] Source system decommission plan approved",
  "human_gate_checklist_md": "Production cutover approval:\\n- [ ] 14-day parallel run completed successfully\\n- [ ] Data owner sign-off obtained\\n- [ ] QA lead sign-off obtained\\n- [ ] Rollback procedure tested\\n- [ ] On-call support scheduled for cutover weekend",
  "inputs": [
    {"kind": "skill_resource", "path": ".agents/skills/etl-reconciler/SKILL.md", "label": "Reconciliation methodology"},
    {"kind": "skill_resource", "path": ".agents/skills/etl-reconciler/resources/tolerance-framework.md", "label": "Tolerance thresholds"},
    {"kind": "external", "path": "SQL Server DW_Sales", "label": "Source system for comparison"}
  ]
}
```"""

    def few_shot_card_examples(self) -> list[CardExample]:
        """Provide migration-specific few-shot examples."""
        return [
            CardExample(
                title="SSIS package analysis",
                context_md="Package PKG_DAILY_SALES.dtsx processes daily sales data with incremental and full reload modes.",
                task_md="1. Extract ConnectionManager elements\n2. Document source and target tables\n3. Identify execution modes\n4. Extract SQL logic\n5. Create connection mapping",
                outputs_md="- Package analysis markdown\n- Connection mapping YAML\n- Table lineage JSON",
                acceptance_criteria_md="- [ ] All connections documented\n- [ ] All tables identified\n- [ ] Execution modes documented\n- [ ] SQL logic extracted",
                explanation="Good discovery card: systematic package analysis with clear deliverables",
            ),
            CardExample(
                title="Silver layer transformation",
                context_md="Migrating daily sales processing to Databricks Silver layer with MERGE support.",
                task_md="1. Create transformation notebook\n2. Implement schema validation\n3. Apply business transformations\n4. Implement MERGE for incremental\n5. Add data quality checks",
                outputs_md="- Databricks notebook\n- Unit tests\n- Workflow YAML\n- Column mapping docs",
                acceptance_criteria_md="- [ ] Notebook executes successfully\n- [ ] Row counts match\n- [ ] Aggregates match\n- [ ] Tests pass",
                explanation="Good transformation card: clear technical steps with validation criteria",
            ),
            CardExample(
                title="Parallel run validation",
                context_md="Sales pipeline ready for parallel run validation before production cutover.",
                task_md="1. Configure dual-write\n2. Create reconciliation notebook\n3. Compare row counts daily\n4. Compare aggregates\n5. Generate discrepancy reports\n6. Document sign-off process",
                outputs_md="- Reconciliation notebook\n- Daily report\n- Sign-off checklist",
                acceptance_criteria_md="- [ ] 14-day parallel run\n- [ ] Row counts match 100%\n- [ ] Aggregates within tolerance\n- [ ] Sign-offs obtained",
                explanation="Good validation card: comprehensive QA with sign-off gates",
            ),
        ]

    def propose_backlog_prompt(self, context: BacklogProposalContext) -> ChatPrompt[ProposedBacklog]:
        """Create LLM prompt for proposing a migration backlog."""
        system_prompt = self._build_backlog_system_prompt()
        user_message = self._build_backlog_user_message(context)

        return ChatPrompt(
            system=system_prompt,
            messages=[user_message],
            response_schema=ProposedBacklog,
        )

    def _build_backlog_system_prompt(self) -> str:
        """Build system prompt for migration backlog proposal."""
        return """You are an expert ETL migration project manager. Generate a comprehensive migration backlog using the 7-phase structure.

**Fixed Phases (do not modify):**
1. Discovery & Assessment - Analyze source packages, identify patterns
2. Infrastructure Foundation - Set up target environment, connections
3. Data Transformation (Silver) - Core transformations, Silver layer
4. Data Aggregation (Gold) - Aggregations, Gold layer analytics
5. Business Rules Implementation - Soft deletes, SCD, complex logic
6. Cutover Preparation - Plan production migration, rollback
7. Parallel Run & Validation - Side-by-side validation, sign-off

**Card Guidelines:**
- Each card should be 2-5 story points
- Include human_gate for production-affecting changes
- Assign appropriate automation_level (auto/auto_hitl/hitl)
- Reference relevant skills for each card
- Create clear dependencies between cards

**Coverage Strategy:**
- Phase 1: One card per major source system/package group
- Phase 2: Connection setup, schema creation, permissions
- Phase 3: One card per major transformation pipeline
- Phase 4: Aggregation cards for reporting needs
- Phase 5: Complex business rules requiring special handling
- Phase 6: Cutover planning, documentation, training
- Phase 7: Reconciliation cards, sign-off gates"""

    def _build_backlog_user_message(self, context: BacklogProposalContext) -> ChatMessage:
        """Build user message for backlog proposal."""
        parts = [
            f"**Migration Project**: {context.project.name}",
            f"**Objective**: {context.project.objective}",
            "",
        ]

        if context.project_context:
            parts.append(f"**Project Context**:\n{context.project_context}")
            parts.append("")

        if context.proposed_skills:
            parts.append("**Available Skills:**")
            for skill in context.proposed_skills:
                parts.append(f"- {skill.name}: {skill.description}")
            parts.append("")

        parts.append("Generate a comprehensive migration backlog with cards organized by the 7 migration phases.")

        return ChatMessage(role="user", content="\n".join(parts))

    def validate_card(self, card: CardView, project: ProjectView) -> list[ValidationIssue]:
        """Validate a migration card."""
        issues: list[ValidationIssue] = []
        # Basic validation - can be extended
        return issues

    def validate_project(self, project: ProjectView) -> list[ValidationIssue]:
        """Validate the entire migration project."""
        issues: list[ValidationIssue] = []

        # Migration projects should have source and target technologies defined
        if project.project_type == "migration":
            if not project.source_technology:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        field="source_technology",
                        message="Migration projects must specify a source technology",
                    )
                )
            if not project.target_technology:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        field="target_technology",
                        message="Migration projects must specify a target technology",
                    )
                )

        return issues
