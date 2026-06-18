"""Context service for shared migration context management.

Provides methods to:
- Register and lookup connections across packages
- Discover and share business rules
- Store and propagate resolved decisions
- Build aggregated project context for LLM prompts
- Build unified MigrationAnalysisContext for LLM analysis (B3d)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.migration_workbench.context.schemas import (
    BusinessRuleCreate,
    BusinessRuleUpdate,
    BusinessRuleView,
    ConnectionCreate,
    ConnectionUpdate,
    ConnectionView,
    DatabaseSchema,
    DecisionCreate,
    DecisionView,
    MigrationAnalysisContext,
    PackageStructureContext,
    PackageSummary,
    ProjectContext,
    UnparsedFeatureView,
)
from app.modules.migration_workbench.models import (
    ETLPackage,
    MigrationBusinessRule,
    MigrationConnection,
    MigrationResolvedDecision,
)

log = structlog.get_logger(__name__)


class ContextService:
    """Service for managing shared migration context.
    
    Context accumulates as packages are analyzed, enabling:
    - Automatic connection reuse
    - Business rule sharing across packages
    - Decision propagation to avoid re-asking
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # -------------------------------------------------------------------------
    # Project Context Aggregation
    # -------------------------------------------------------------------------
    
    def get_project_context(self, project_id: uuid.UUID) -> ProjectContext:
        """Build complete project context for analysis and generation.
        
        This is the primary method called before analyzing a package
        or generating code, providing all accumulated knowledge.
        """
        from app.domain.projects import Project
        
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        packages = self._get_packages(project_id)
        connections = self._get_connections(project_id)
        business_rules = self._get_business_rules(project_id)
        decisions = self._get_decisions(project_id)
        
        # Calculate statistics
        total = len(packages)
        analyzed = sum(1 for p in packages if p.status in ("analyzed", "ready", "generated", "migrated", "verified"))
        needs_feedback = sum(1 for p in packages if p.status == "needs_feedback")
        migrated = sum(1 for p in packages if p.status in ("migrated", "verified"))
        unresolved_conns = sum(1 for c in connections if c.resolved_at is None)
        unimpl_rules = sum(1 for r in business_rules if r.status in ("discovered", "confirmed"))
        
        return ProjectContext(
            project_id=project_id,
            source_technology=project.source_technology,
            target_technology=project.target_technology,
            packages=[PackageSummary.model_validate(p) for p in packages],
            connections=connections,
            business_rules=business_rules,
            resolved_decisions=decisions,
            total_packages=total,
            analyzed_packages=analyzed,
            packages_needing_feedback=needs_feedback,
            migrated_packages=migrated,
            unresolved_connections=unresolved_conns,
            unimplemented_rules=unimpl_rules,
        )
    
    def _get_packages(self, project_id: uuid.UUID) -> list[ETLPackage]:
        """Get all packages for a project."""
        stmt = (
            select(ETLPackage)
            .where(ETLPackage.project_id == project_id)
            .order_by(ETLPackage.created_at)
        )
        return list(self.db.scalars(stmt))
    
    def _get_connections(self, project_id: uuid.UUID) -> list[ConnectionView]:
        """Get all connections for a project."""
        stmt = (
            select(MigrationConnection)
            .where(MigrationConnection.project_id == project_id)
            .order_by(MigrationConnection.connection_name)
        )
        return [ConnectionView.model_validate(c) for c in self.db.scalars(stmt)]
    
    def _get_business_rules(self, project_id: uuid.UUID) -> list[BusinessRuleView]:
        """Get all business rules for a project."""
        stmt = (
            select(MigrationBusinessRule)
            .where(MigrationBusinessRule.project_id == project_id)
            .order_by(MigrationBusinessRule.rule_id)
        )
        return [BusinessRuleView.model_validate(r) for r in self.db.scalars(stmt)]
    
    def _get_decisions(self, project_id: uuid.UUID) -> list[DecisionView]:
        """Get all resolved decisions for a project."""
        stmt = (
            select(MigrationResolvedDecision)
            .where(MigrationResolvedDecision.project_id == project_id)
            .order_by(MigrationResolvedDecision.resolved_at.desc())
        )
        return [DecisionView.model_validate(d) for d in self.db.scalars(stmt)]
    
    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------
    
    def register_connection(
        self, 
        project_id: uuid.UUID, 
        connection: ConnectionCreate
    ) -> MigrationConnection:
        """Register a connection, merging if it already exists.
        
        When a package references a connection that's already known,
        we add it to the used_by_packages list rather than duplicating.
        """
        stmt = select(MigrationConnection).where(
            MigrationConnection.project_id == project_id,
            MigrationConnection.connection_name == connection.connection_name,
        )
        existing = self.db.scalar(stmt)
        
        if existing:
            # Merge: add package to used_by list if not already there
            if connection.discovered_in_package:
                used_by = list(existing.used_by_packages or [])
                if connection.discovered_in_package not in used_by:
                    used_by.append(connection.discovered_in_package)
                    existing.used_by_packages = used_by
            return existing
        
        # Create new
        conn = MigrationConnection(
            project_id=project_id,
            connection_name=connection.connection_name,
            connection_type=connection.connection_type,
            source_server=connection.source_server,
            source_database=connection.source_database,
            auth_method=connection.auth_method,
            used_by_packages=[connection.discovered_in_package] if connection.discovered_in_package else [],
        )
        self.db.add(conn)
        self.db.flush()
        return conn
    
    def resolve_connection(
        self, 
        connection_id: uuid.UUID, 
        update: ConnectionUpdate
    ) -> MigrationConnection:
        """Resolve a connection's target mapping."""
        conn = self.db.get(MigrationConnection, connection_id)
        if not conn:
            raise ValueError(f"Connection {connection_id} not found")
        
        if update.target_catalog is not None:
            conn.target_catalog = update.target_catalog
        if update.target_schema is not None:
            conn.target_schema = update.target_schema
        if update.resolved_by is not None:
            conn.resolved_by = update.resolved_by
        conn.resolved_at = datetime.now(timezone.utc)
        
        return conn
    
    def find_connection(
        self, 
        project_id: uuid.UUID, 
        connection_name: str
    ) -> MigrationConnection | None:
        """Find a connection by name."""
        stmt = select(MigrationConnection).where(
            MigrationConnection.project_id == project_id,
            MigrationConnection.connection_name == connection_name,
        )
        return self.db.scalar(stmt)
    
    # -------------------------------------------------------------------------
    # Business Rule Management
    # -------------------------------------------------------------------------
    
    def register_business_rule(
        self, 
        project_id: uuid.UUID, 
        rule: BusinessRuleCreate
    ) -> MigrationBusinessRule:
        """Register a business rule, merging if it already exists."""
        stmt = select(MigrationBusinessRule).where(
            MigrationBusinessRule.project_id == project_id,
            MigrationBusinessRule.rule_id == rule.rule_id,
        )
        existing = self.db.scalar(stmt)
        
        if existing:
            # Merge: add package to used_by list
            if rule.discovered_in_package:
                used_by = list(existing.used_by_packages or [])
                if rule.discovered_in_package not in used_by:
                    used_by.append(rule.discovered_in_package)
                    existing.used_by_packages = used_by
            # Merge domains
            if rule.applies_to_domains:
                domains = list(set(existing.applies_to_domains or []) | set(rule.applies_to_domains))
                existing.applies_to_domains = domains
            return existing
        
        # Create new
        br = MigrationBusinessRule(
            project_id=project_id,
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            description=rule.description,
            source_implementation=rule.source_implementation,
            category=rule.category,
            applies_to_domains=rule.applies_to_domains or [],
            used_by_packages=[rule.discovered_in_package] if rule.discovered_in_package else [],
        )
        self.db.add(br)
        self.db.flush()
        return br
    
    def update_business_rule(
        self, 
        rule_id: uuid.UUID, 
        update: BusinessRuleUpdate
    ) -> MigrationBusinessRule:
        """Update a business rule's implementation or status."""
        rule = self.db.get(MigrationBusinessRule, rule_id)
        if not rule:
            raise ValueError(f"Business rule {rule_id} not found")
        
        if update.target_implementation is not None:
            rule.target_implementation = update.target_implementation
        if update.status is not None:
            rule.status = update.status
        
        return rule
    
    def find_business_rule(
        self, 
        project_id: uuid.UUID, 
        rule_id: str
    ) -> MigrationBusinessRule | None:
        """Find a business rule by its rule_id."""
        stmt = select(MigrationBusinessRule).where(
            MigrationBusinessRule.project_id == project_id,
            MigrationBusinessRule.rule_id == rule_id,
        )
        return self.db.scalar(stmt)
    
    # -------------------------------------------------------------------------
    # Resolved Decision Management
    # -------------------------------------------------------------------------
    
    def record_decision(
        self, 
        project_id: uuid.UUID, 
        decision: DecisionCreate
    ) -> MigrationResolvedDecision:
        """Record a resolved decision for future propagation."""
        dec = MigrationResolvedDecision(
            project_id=project_id,
            decision_type=decision.decision_type,
            question=decision.question,
            resolution=decision.resolution,
            resolution_rationale=decision.resolution_rationale,
            scope=decision.scope,
            flow_id=decision.flow_id,
            package_id=decision.package_id,
            resolved_by=decision.resolved_by,
        )
        self.db.add(dec)
        self.db.flush()
        return dec
    
    def find_resolved_decision(
        self, 
        project_id: uuid.UUID, 
        decision_type: str,
        scope: str = "project",
        flow_id: uuid.UUID | None = None,
    ) -> MigrationResolvedDecision | None:
        """Find a resolved decision that could apply to a new question.
        
        Lookup order:
        1. Exact match on decision_type + scope + flow_id (if flow-scoped)
        2. Project-level decision of same type
        """
        # Try exact match first
        stmt = select(MigrationResolvedDecision).where(
            MigrationResolvedDecision.project_id == project_id,
            MigrationResolvedDecision.decision_type == decision_type,
            MigrationResolvedDecision.scope == scope,
        )
        if scope == "flow" and flow_id:
            stmt = stmt.where(MigrationResolvedDecision.flow_id == flow_id)
        
        result = self.db.scalar(stmt)
        if result:
            return result
        
        # Fall back to project-level
        if scope != "project":
            stmt = select(MigrationResolvedDecision).where(
                MigrationResolvedDecision.project_id == project_id,
                MigrationResolvedDecision.decision_type == decision_type,
                MigrationResolvedDecision.scope == "project",
            )
            return self.db.scalar(stmt)
        
        return None
    
    def apply_decision_to_package(
        self, 
        decision_id: uuid.UUID, 
        package_id: uuid.UUID
    ) -> MigrationResolvedDecision:
        """Mark a decision as applied to a specific package."""
        decision = self.db.get(MigrationResolvedDecision, decision_id)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")
        
        applied = list(decision.applied_to_packages or [])
        if package_id not in applied:
            applied.append(package_id)
            decision.applied_to_packages = applied
        
        return decision
    
    # -------------------------------------------------------------------------
    # Context for LLM Prompts
    # -------------------------------------------------------------------------
    
    def get_context_summary_for_prompt(self, project_id: uuid.UUID) -> str:
        """Generate a text summary of project context for LLM prompts.
        
        This provides a condensed view of accumulated knowledge that
        can be injected into analysis or generation prompts.
        """
        ctx = self.get_project_context(project_id)
        
        lines = [
            f"# Migration Project Context",
            f"",
            f"**Source:** {ctx.source_technology or 'Unknown'}",
            f"**Target:** {ctx.target_technology or 'Unknown'}",
            f"**Progress:** {ctx.migrated_packages}/{ctx.total_packages} packages migrated",
            f"",
        ]
        
        # Resolved connections
        resolved_conns = [c for c in ctx.connections if c.resolved_at]
        if resolved_conns:
            lines.append("## Resolved Connection Mappings")
            for c in resolved_conns:
                lines.append(f"- `{c.connection_name}` → `{c.target_catalog}.{c.target_schema}`")
            lines.append("")
        
        # Implemented business rules — full implementation, no truncation (B3a: BUG-14 fix)
        impl_rules = [r for r in ctx.business_rules if r.status in ("implemented", "verified")]
        if impl_rules:
            lines.append("## Implemented Business Rules")
            for r in impl_rules:
                lines.append(f"- **{r.rule_name}** ({r.rule_id})")
                if r.target_implementation:
                    lines.append(f"  ```\n  {r.target_implementation}\n  ```")
            lines.append("")

        # Project-level decisions — all of them, no cap (B3a: BUG-15 fix)
        project_decisions = [d for d in ctx.resolved_decisions if d.scope == "project"]
        if project_decisions:
            lines.append("## Project Decisions")
            for d in project_decisions:
                lines.append(f"- **{d.decision_type}**: {d.resolution}")
            lines.append("")
        
        return "\n".join(lines)
    
    # -------------------------------------------------------------------------
    # Unified MigrationAnalysisContext (B3d)
    # -------------------------------------------------------------------------
    
    def build_analysis_context(
        self,
        project_id: uuid.UUID,
        package: Any | None = None,
        source_schema: DatabaseSchema | None = None,
        include_structural_comparison: bool = True,
    ) -> MigrationAnalysisContext:
        """Build complete MigrationAnalysisContext for LLM calls.
        
        This is the B3d unified context model that assembles ALL context
        needed for migration analysis LLM calls in one place. No more
        ad-hoc formatting or truncation in individual callers.
        
        Args:
            project_id: Project UUID
            package: Parsed SSISPackage (optional, for package-specific context)
            source_schema: DatabaseSchema from Phase A dump (optional)
            include_structural_comparison: Whether to run schema comparison
        
        Returns:
            MigrationAnalysisContext ready for LLM prompt rendering
        """
        from app.domain.projects import Project
        from app.modules.migration_workbench.analysis.schemas import SSISPackage
        
        # Get project
        project = self.db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Get base context
        base_ctx = self.get_project_context(project_id)
        
        # Build Q&A dict from project
        qa_dict = self._build_qa_dict(project)
        
        # Build tech choices dict
        tech_choices = self._build_tech_choices_dict(project)
        
        # Build package structure context if package provided
        package_structure = None
        if package is not None and isinstance(package, SSISPackage):
            package_structure = self._build_package_structure_context(package)
        
        # Run structural comparison if schema provided
        structural_comparison = None
        if source_schema and package and include_structural_comparison:
            try:
                from app.modules.migration_workbench.analysis.structural_comparator import (
                    compare_schemas,
                )
                structural_comparison = compare_schemas(package, source_schema)
            except Exception as e:
                log.warning("structural_comparison_failed", error=str(e))
        
        # Get related packages (packages sharing objects with this one)
        related_packages: list[PackageSummary] = []
        shared_object_count = 0
        if package:
            related_packages, shared_object_count = self._get_related_packages(
                project_id, package
            )
        
        return MigrationAnalysisContext(
            project_id=project_id,
            objective=project.objective,
            qa=qa_dict,
            tech_choices=tech_choices,
            context_notes_md=project.context_md,
            source_technology=project.source_technology,
            target_technology=project.target_technology,
            resolved_decisions=base_ctx.resolved_decisions,
            business_rules=base_ctx.business_rules,
            connections=base_ctx.connections,
            package_structure=package_structure,
            source_schema=source_schema,
            target_schema=None,  # Future: from Databricks catalog
            structural_comparison=structural_comparison,
            related_packages=related_packages,
            shared_object_count=shared_object_count,
        )
    
    def _build_qa_dict(self, project: Any) -> dict[str, str]:
        """Build Q&A dictionary from project QA answers."""
        from app.domain.projects import ProjectQaAnswer
        
        qa_dict: dict[str, str] = {}
        stmt = select(ProjectQaAnswer).where(ProjectQaAnswer.project_id == project.id)
        answers = self.db.scalars(stmt)
        
        for answer in answers:
            qa_dict[answer.question_slug] = answer.answer_md
        
        return qa_dict
    
    def _build_tech_choices_dict(self, project: Any) -> dict[str, list[str]]:
        """Build tech choices dictionary from project tech choices."""
        from app.domain.projects import ProjectTechChoice
        
        tech_dict: dict[str, list[str]] = {}
        stmt = select(ProjectTechChoice).where(ProjectTechChoice.project_id == project.id)
        choices = self.db.scalars(stmt)
        
        for choice in choices:
            dim = choice.dimension_slug
            if dim not in tech_dict:
                tech_dict[dim] = []
            tech_dict[dim].append(choice.tech_item_name or choice.tech_item_slug)
        
        return tech_dict
    
    def _build_package_structure_context(
        self, 
        package: Any
    ) -> PackageStructureContext:
        """Build PackageStructureContext from parsed SSISPackage.
        
        Serializes the full package structure to JSON dicts for
        inclusion in the MigrationAnalysisContext. No truncation.
        """
        from app.modules.migration_workbench.analysis.schemas import SSISPackage
        
        if not isinstance(package, SSISPackage):
            raise TypeError(f"Expected SSISPackage, got {type(package)}")
        
        # Serialize to JSON-compatible dicts
        tasks_json = [t.model_dump(mode="json") for t in package.tasks]
        data_flows_json = [df.model_dump(mode="json") for df in package.data_flows]
        variables_json = [v.model_dump(mode="json") for v in package.variables]
        parameters_json = [p.model_dump(mode="json") for p in package.parameters]
        connections_json = [c.model_dump(mode="json") for c in package.connection_managers]
        constraints_json = [pc.model_dump(mode="json") for pc in package.precedence_constraints]
        
        # Build unparsed features list
        unparsed_features: list[UnparsedFeatureView] = []
        if hasattr(package, "unparsed_features") and package.unparsed_features:
            for uf in package.unparsed_features:
                unparsed_features.append(UnparsedFeatureView(
                    feature=uf.feature,
                    count=uf.count,
                    location=uf.location,
                    note=uf.note,
                ))
        
        return PackageStructureContext(
            package_name=package.package_name,
            package_id=package.package_id,
            task_count=len(package.tasks),
            data_flow_count=len(package.data_flows),
            connection_count=len(package.connection_managers),
            variable_count=len(package.variables),
            parameter_count=len(package.parameters),
            tasks_json=tasks_json,
            data_flows_json=data_flows_json,
            variables_json=variables_json,
            parameters_json=parameters_json,
            connections_json=connections_json,
            precedence_constraints_json=constraints_json,
            unparsed_features=unparsed_features,
            parse_warnings=package.parse_warnings or [],
        )
    
    def _get_related_packages(
        self, 
        project_id: uuid.UUID, 
        package: Any
    ) -> tuple[list[PackageSummary], int]:
        """Find packages that share objects with the given package.
        
        Uses the migration map to find packages that access the same
        tables, stored procedures, or other objects.
        
        Returns:
            Tuple of (related packages list, shared object count)
        """
        # For now, return empty — will be wired to MigrationMap in future
        # This is a placeholder for cross-package context
        return [], 0
    
    def load_schema_dump_from_artifact(
        self,
        project_id: uuid.UUID,
    ) -> DatabaseSchema | None:
        """Load schema dump from project artifacts.
        
        Looks for an artifact of kind 'spec' with a JSON schema dump
        that matches the DatabaseSchema format.
        
        Args:
            project_id: Project UUID
        
        Returns:
            DatabaseSchema if found and valid, None otherwise
        """
        from app.domain.projects import ProjectArtifact
        from app.extractors.schema_dump_extractor import parse_schema_dump_from_json
        
        # Look for schema dump artifacts
        stmt = select(ProjectArtifact).where(
            ProjectArtifact.project_id == project_id,
            ProjectArtifact.kind == "spec",
            ProjectArtifact.extraction_status == "extracted",
        )
        artifacts = self.db.scalars(stmt)
        
        for artifact in artifacts:
            # Try to parse as schema dump
            if artifact.filename.endswith(".json"):
                # Load from file path
                try:
                    artifact_path = Path(artifact.file_path) if artifact.file_path else None
                    if artifact_path and artifact_path.exists():
                        with open(artifact_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        
                        # Check if it looks like a schema dump
                        if "dialect" in data and "tables" in data:
                            schema = parse_schema_dump_from_json(data)
                            if schema:
                                log.info(
                                    "schema_dump_loaded",
                                    artifact_id=str(artifact.id),
                                    table_count=len(schema.tables),
                                )
                                return schema
                except Exception as e:
                    log.warning(
                        "schema_dump_load_failed",
                        artifact_id=str(artifact.id),
                        error=str(e),
                    )
        
        return None
