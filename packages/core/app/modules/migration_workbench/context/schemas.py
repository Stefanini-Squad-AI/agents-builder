"""Pydantic schemas for Context service.

Includes:
- Connection, BusinessRule, Decision schemas (CRUD)
- DatabaseSchema models for Phase A schema dumps
- MigrationAnalysisContext for unified LLM context
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Connection schemas
# -----------------------------------------------------------------------------


class ConnectionBase(BaseModel):
    """Base fields for connection."""
    
    connection_name: str = Field(..., description="Connection manager name")
    connection_type: str | None = Field(None, description="Type (OLEDB, ADO.NET, etc.)")
    source_server: str | None = Field(None, description="Source server")
    source_database: str | None = Field(None, description="Source database")
    auth_method: str | None = Field(None, description="Authentication method")


class ConnectionCreate(ConnectionBase):
    """Create a new connection."""
    
    discovered_in_package: uuid.UUID | None = Field(
        None, 
        description="Package ID where this connection was discovered"
    )


class ConnectionUpdate(BaseModel):
    """Update connection mapping."""
    
    target_catalog: str | None = Field(None, description="Target catalog in Databricks")
    target_schema: str | None = Field(None, description="Target schema in Databricks")
    resolved_by: str | None = Field(None, description="Who resolved this mapping")


class ConnectionView(ConnectionBase):
    """Connection response."""
    
    id: uuid.UUID
    target_catalog: str | None = None
    target_schema: str | None = None
    used_by_packages: list[uuid.UUID] = []
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    created_at: datetime
    
    model_config = {"from_attributes": True}


# -----------------------------------------------------------------------------
# Business rule schemas
# -----------------------------------------------------------------------------


class BusinessRuleBase(BaseModel):
    """Base fields for business rule."""
    
    rule_id: str = Field(..., description="Unique rule identifier")
    rule_name: str = Field(..., description="Human-readable name")
    description: str | None = Field(None, description="Rule description")
    category: str | None = Field(None, description="Rule category")


class BusinessRuleCreate(BusinessRuleBase):
    """Create a new business rule."""
    
    source_implementation: str | None = Field(
        None, 
        description="How rule is implemented in source"
    )
    applies_to_domains: list[str] = Field(
        default_factory=list,
        description="Domains where this rule applies"
    )
    discovered_in_package: uuid.UUID | None = Field(
        None,
        description="Package ID where this rule was discovered"
    )


class BusinessRuleUpdate(BaseModel):
    """Update business rule implementation."""
    
    target_implementation: str | None = Field(
        None, 
        description="How rule should be implemented in target"
    )
    status: str | None = Field(None, description="Rule status")


class BusinessRuleView(BusinessRuleBase):
    """Business rule response."""
    
    id: uuid.UUID
    source_implementation: str | None = None
    target_implementation: str | None = None
    applies_to_domains: list[str] = []
    used_by_packages: list[uuid.UUID] = []
    status: str
    created_at: datetime
    
    model_config = {"from_attributes": True}


# -----------------------------------------------------------------------------
# Resolved decision schemas
# -----------------------------------------------------------------------------


class DecisionBase(BaseModel):
    """Base fields for resolved decision."""
    
    decision_type: str = Field(..., description="Type of decision")
    question: str = Field(..., description="The question that was asked")
    resolution: str = Field(..., description="The resolution")


class DecisionCreate(DecisionBase):
    """Create a new resolved decision."""
    
    resolution_rationale: str | None = Field(None, description="Why this resolution")
    scope: str = Field("project", description="Scope: project, flow, or package")
    flow_id: uuid.UUID | None = Field(None, description="Flow ID if flow-scoped")
    package_id: uuid.UUID | None = Field(None, description="Package ID if package-scoped")
    resolved_by: str | None = Field(None, description="Who resolved this")


class DecisionView(DecisionBase):
    """Resolved decision response."""
    
    id: uuid.UUID
    resolution_rationale: str | None = None
    scope: str
    flow_id: uuid.UUID | None = None
    package_id: uuid.UUID | None = None
    resolved_by: str | None = None
    resolved_at: datetime
    applied_to_packages: list[uuid.UUID] = []
    
    model_config = {"from_attributes": True}


# -----------------------------------------------------------------------------
# Package summary for context
# -----------------------------------------------------------------------------


class PackageSummary(BaseModel):
    """Summary of a package for context."""
    
    id: uuid.UUID
    package_name: str
    domain: str | None = None
    status: str
    complexity: str
    
    model_config = {"from_attributes": True}


# -----------------------------------------------------------------------------
# Aggregated project context
# -----------------------------------------------------------------------------


class ProjectContext(BaseModel):
    """Complete project context for analysis and generation.
    
    This is the aggregated context that provides all shared knowledge
    accumulated during the migration project.
    """
    
    project_id: uuid.UUID
    source_technology: str | None = None
    target_technology: str | None = None
    
    packages: list[PackageSummary] = Field(
        default_factory=list,
        description="All registered packages"
    )
    connections: list[ConnectionView] = Field(
        default_factory=list,
        description="All discovered connections"
    )
    business_rules: list[BusinessRuleView] = Field(
        default_factory=list,
        description="All discovered business rules"
    )
    resolved_decisions: list[DecisionView] = Field(
        default_factory=list,
        description="All resolved decisions"
    )
    
    # Statistics
    total_packages: int = 0
    analyzed_packages: int = 0
    packages_needing_feedback: int = 0
    migrated_packages: int = 0
    unresolved_connections: int = 0
    unimplemented_rules: int = 0


# -----------------------------------------------------------------------------
# Database Schema models (Phase A: Schema Dump)
# -----------------------------------------------------------------------------


class DatabaseDialect(str, Enum):
    """Supported database dialects for schema dumps."""
    
    MSSQL = "mssql"
    POSTGRESQL = "postgresql"
    ORACLE = "oracle"
    MYSQL = "mysql"


class ColumnSchema(BaseModel):
    """Schema for a database column."""
    
    name: str = Field(..., description="Column name")
    ordinal_position: int = Field(..., description="Position in table (1-based)")
    data_type: str = Field(..., description="Database-specific data type")
    max_length: int | None = Field(None, description="Max length for string types")
    precision: int | None = Field(None, description="Numeric precision")
    scale: int | None = Field(None, description="Numeric scale")
    is_nullable: bool = Field(True, description="Whether column allows NULL")
    is_identity: bool = Field(False, description="Whether column is auto-increment")
    is_primary_key: bool = Field(False, description="Whether column is part of PK")
    is_foreign_key: bool = Field(False, description="Whether column is part of FK")
    default_value: str | None = Field(None, description="Default value expression")
    computed_expression: str | None = Field(None, description="Computed column expression")


class PrimaryKeySchema(BaseModel):
    """Schema for a primary key constraint."""
    
    name: str = Field(..., description="Constraint name")
    columns: list[str] = Field(..., description="Column names in key order")


class ForeignKeySchema(BaseModel):
    """Schema for a foreign key constraint."""
    
    name: str = Field(..., description="Constraint name")
    columns: list[str] = Field(..., description="Local column names")
    referenced_table: str = Field(..., description="Referenced table name")
    referenced_schema: str | None = Field(None, description="Referenced schema")
    referenced_columns: list[str] = Field(..., description="Referenced column names")
    on_delete: str | None = Field(None, description="ON DELETE action")
    on_update: str | None = Field(None, description="ON UPDATE action")


class IndexSchema(BaseModel):
    """Schema for a database index."""
    
    name: str = Field(..., description="Index name")
    columns: list[str] = Field(..., description="Indexed columns in order")
    is_unique: bool = Field(False, description="Whether index enforces uniqueness")
    is_clustered: bool = Field(False, description="Whether index is clustered (SQL Server)")
    type: str | None = Field(None, description="Index type (BTREE, HASH, etc.)")
    filter_expression: str | None = Field(None, description="Filtered index WHERE clause")


class CheckConstraintSchema(BaseModel):
    """Schema for a check constraint."""
    
    name: str = Field(..., description="Constraint name")
    expression: str = Field(..., description="Check expression")


class TableSchema(BaseModel):
    """Schema for a database table."""
    
    schema_name: str = Field(..., description="Schema/owner name")
    table_name: str = Field(..., description="Table name")
    table_type: str = Field("BASE TABLE", description="BASE TABLE or VIEW")
    row_count: int | None = Field(None, description="Approximate row count")
    columns: list[ColumnSchema] = Field(default_factory=list)
    primary_key: PrimaryKeySchema | None = None
    foreign_keys: list[ForeignKeySchema] = Field(default_factory=list)
    indexes: list[IndexSchema] = Field(default_factory=list)
    constraints: list[CheckConstraintSchema] = Field(default_factory=list)


class ViewSchema(BaseModel):
    """Schema for a database view."""
    
    schema_name: str = Field(..., description="Schema/owner name")
    view_name: str = Field(..., description="View name")
    definition: str | None = Field(None, description="View definition SQL")
    columns: list[ColumnSchema] = Field(default_factory=list)


class StoredProcedureSchema(BaseModel):
    """Schema for a stored procedure."""
    
    schema_name: str = Field(..., description="Schema/owner name")
    procedure_name: str = Field(..., description="Procedure name")
    definition: str | None = Field(None, description="Procedure definition SQL")
    parameters: list[dict[str, Any]] = Field(default_factory=list)


class FunctionSchema(BaseModel):
    """Schema for a database function."""
    
    schema_name: str = Field(..., description="Schema/owner name")
    function_name: str = Field(..., description="Function name")
    return_type: str | None = Field(None, description="Return data type")
    definition: str | None = Field(None, description="Function definition SQL")
    parameters: list[dict[str, Any]] = Field(default_factory=list)


class DatabaseSchema(BaseModel):
    """Complete database schema from a schema dump.
    
    This is the Phase A schema dump format — whether uploaded manually
    or extracted via Lakebridge Profiler, it uses this same structure.
    """
    
    dialect: DatabaseDialect = Field(..., description="Source database dialect")
    database_name: str = Field(..., description="Database name")
    schema_name: str | None = Field(None, description="Default schema if applicable")
    extracted_at: datetime = Field(..., description="When the schema was extracted")
    extraction_method: str = Field(
        "schema_dump_cli",
        description="How schema was extracted: schema_dump_cli, lakebridge_profiler, manual"
    )
    
    tables: list[TableSchema] = Field(default_factory=list)
    views: list[ViewSchema] = Field(default_factory=list)
    stored_procedures: list[StoredProcedureSchema] = Field(default_factory=list)
    functions: list[FunctionSchema] = Field(default_factory=list)
    
    def get_table(self, schema: str, table: str) -> TableSchema | None:
        """Find a table by schema and name."""
        for t in self.tables:
            if t.schema_name.lower() == schema.lower() and t.table_name.lower() == table.lower():
                return t
        return None
    
    def get_column(self, schema: str, table: str, column: str) -> ColumnSchema | None:
        """Find a column by schema, table, and column name."""
        tbl = self.get_table(schema, table)
        if not tbl:
            return None
        for c in tbl.columns:
            if c.name.lower() == column.lower():
                return c
        return None


# -----------------------------------------------------------------------------
# Structural Comparison Result
# -----------------------------------------------------------------------------


class ColumnMismatch(BaseModel):
    """A mismatch between SSIS-declared column and actual DB column."""
    
    table_name: str
    column_name: str
    mismatch_type: str = Field(
        ..., 
        description="missing_in_db, missing_in_ssis, type_mismatch, nullable_mismatch"
    )
    ssis_type: str | None = None
    db_type: str | None = None
    ssis_nullable: bool | None = None
    db_nullable: bool | None = None
    note: str | None = None


class StructuralComparisonResult(BaseModel):
    """Result of comparing SSIS-declared schema against actual DB schema."""
    
    compared_at: datetime
    source_tables_checked: int = 0
    destination_tables_checked: int = 0
    
    mismatches: list[ColumnMismatch] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    
    @property
    def has_critical_issues(self) -> bool:
        """Check if any mismatches could cause migration failures."""
        critical_types = {"missing_in_db", "type_mismatch"}
        return any(m.mismatch_type in critical_types for m in self.mismatches)


# -----------------------------------------------------------------------------
# Unparsed Feature (explicit gaps for LLM awareness)
# -----------------------------------------------------------------------------


class UnparsedFeatureView(BaseModel):
    """An SSIS feature that couldn't be fully parsed.
    
    Tells the LLM what it DOESN'T know, so it can flag risks.
    """
    
    feature: str = Field(..., description="Feature type: event_handlers, script_tasks, etc.")
    count: int = Field(..., description="How many instances exist")
    location: str = Field(..., description="Where in the package")
    note: str = Field(..., description="Human-readable explanation")


# -----------------------------------------------------------------------------
# Package Structure Context (full detail from SSIS parse)
# -----------------------------------------------------------------------------


class PackageStructureContext(BaseModel):
    """Rich structural context from SSIS parse.
    
    This is the full package structure with NO truncation,
    ready to be included in MigrationAnalysisContext.
    """
    
    package_name: str
    package_id: str | None = None
    
    # Summary counts
    task_count: int = 0
    data_flow_count: int = 0
    connection_count: int = 0
    variable_count: int = 0
    parameter_count: int = 0
    
    # Full structure (serialized from SSISPackage)
    tasks_json: list[dict[str, Any]] = Field(default_factory=list)
    data_flows_json: list[dict[str, Any]] = Field(default_factory=list)
    variables_json: list[dict[str, Any]] = Field(default_factory=list)
    parameters_json: list[dict[str, Any]] = Field(default_factory=list)
    connections_json: list[dict[str, Any]] = Field(default_factory=list)
    precedence_constraints_json: list[dict[str, Any]] = Field(default_factory=list)
    
    # Explicit gaps
    unparsed_features: list[UnparsedFeatureView] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# MigrationAnalysisContext — unified context for all LLM calls
# -----------------------------------------------------------------------------


class MigrationAnalysisContext(BaseModel):
    """Complete context for any migration-related LLM call.
    
    Assembled ONCE per analysis run, then passed to whichever
    prompt needs it. No more ad-hoc formatting or truncation.
    
    This is the B3d unified context model that combines:
    - Project-level context (objective, Q&A, tech choices)
    - Migration-specific context (connections, rules, decisions)
    - Package structure (full SSIS parse, no truncation)
    - Database schema (from Phase A dump or Lakebridge Profiler)
    - Structural comparison results
    """
    
    # --- Project-level context ---
    project_id: uuid.UUID
    objective: str | None = None
    qa: dict[str, str] = Field(default_factory=dict)
    tech_choices: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Tech choices by dimension slug"
    )
    context_notes_md: str | None = None
    
    # --- Migration-specific context ---
    source_technology: str | None = None
    target_technology: str | None = None
    resolved_decisions: list[DecisionView] = Field(default_factory=list)
    business_rules: list[BusinessRuleView] = Field(default_factory=list)
    connections: list[ConnectionView] = Field(default_factory=list)
    
    # --- Package structure (from SSIS parse) ---
    package_structure: PackageStructureContext | None = None
    
    # --- Database schema (from Phase A dump or Lakebridge) ---
    source_schema: DatabaseSchema | None = None
    target_schema: DatabaseSchema | None = None
    
    # --- Structural comparison ---
    structural_comparison: StructuralComparisonResult | None = None
    
    # --- Cross-package context (from migration map) ---
    related_packages: list[PackageSummary] = Field(default_factory=list)
    shared_object_count: int = 0
    
    def render_for_prompt(self) -> str:
        """Render the context as a markdown string for LLM prompts.
        
        This replaces all ad-hoc formatting scattered across the codebase.
        """
        lines: list[str] = []
        
        # Project overview
        lines.append("# Migration Analysis Context\n")
        
        if self.objective:
            lines.append(f"**Objective:** {self.objective}\n")
        
        lines.append(f"**Source Technology:** {self.source_technology or 'Unknown'}")
        lines.append(f"**Target Technology:** {self.target_technology or 'Unknown'}\n")
        
        # Q&A
        if self.qa:
            lines.append("## Project Q&A\n")
            for q, a in self.qa.items():
                lines.append(f"**{q}:** {a}\n")
        
        # Tech choices
        if self.tech_choices:
            lines.append("## Technology Choices\n")
            for dim, choices in self.tech_choices.items():
                lines.append(f"- **{dim}:** {', '.join(choices)}")
            lines.append("")
        
        # Resolved decisions
        if self.resolved_decisions:
            lines.append("## Resolved Decisions\n")
            for d in self.resolved_decisions:
                lines.append(f"- **{d.decision_type}** ({d.scope}): {d.resolution}")
                if d.resolution_rationale:
                    lines.append(f"  - Rationale: {d.resolution_rationale}")
            lines.append("")
        
        # Business rules
        impl_rules = [r for r in self.business_rules if r.status in ("implemented", "verified")]
        if impl_rules:
            lines.append("## Implemented Business Rules\n")
            for r in impl_rules:
                lines.append(f"- **{r.rule_name}** ({r.rule_id}): {r.description or ''}")
                if r.target_implementation:
                    lines.append(f"  ```\n  {r.target_implementation}\n  ```")
            lines.append("")
        
        # Connections
        resolved_conns = [c for c in self.connections if c.resolved_at]
        if resolved_conns:
            lines.append("## Resolved Connection Mappings\n")
            for c in resolved_conns:
                lines.append(f"- `{c.connection_name}` → `{c.target_catalog}.{c.target_schema}`")
            lines.append("")
        
        # Source schema summary
        if self.source_schema:
            lines.append("## Source Database Schema\n")
            lines.append(f"**Database:** {self.source_schema.database_name} ({self.source_schema.dialect.value})")
            lines.append(f"**Tables:** {len(self.source_schema.tables)}")
            lines.append(f"**Views:** {len(self.source_schema.views)}\n")
            
            # List tables with row counts
            if self.source_schema.tables:
                lines.append("### Tables\n")
                for t in self.source_schema.tables[:50]:  # Cap at 50 for prompt readability
                    row_info = f" (~{t.row_count:,} rows)" if t.row_count else ""
                    col_count = len(t.columns)
                    lines.append(f"- `{t.schema_name}.{t.table_name}` ({col_count} columns){row_info}")
                if len(self.source_schema.tables) > 50:
                    lines.append(f"- ... and {len(self.source_schema.tables) - 50} more tables")
                lines.append("")
        
        # Structural comparison results
        if self.structural_comparison:
            lines.append("## Structural Comparison Results\n")
            if self.structural_comparison.mismatches:
                lines.append(f"**Mismatches Found:** {len(self.structural_comparison.mismatches)}\n")
                for m in self.structural_comparison.mismatches:
                    lines.append(f"- `{m.table_name}.{m.column_name}`: {m.mismatch_type}")
                    if m.note:
                        lines.append(f"  - {m.note}")
            else:
                lines.append("No schema mismatches detected.\n")
            
            if self.structural_comparison.warnings:
                lines.append("\n**Warnings:**")
                for w in self.structural_comparison.warnings:
                    lines.append(f"- {w}")
            lines.append("")
        
        # Package structure (if present)
        if self.package_structure:
            lines.append("## Package Structure\n")
            lines.append(f"**Package:** {self.package_structure.package_name}")
            lines.append(f"**Tasks:** {self.package_structure.task_count}")
            lines.append(f"**Data Flows:** {self.package_structure.data_flow_count}")
            lines.append(f"**Variables:** {self.package_structure.variable_count}")
            lines.append(f"**Parameters:** {self.package_structure.parameter_count}\n")
            
            # Unparsed features (critical for LLM awareness)
            if self.package_structure.unparsed_features:
                lines.append("### Unparsed Features (Risks)\n")
                lines.append("*The following features could not be fully parsed and may contain logic not visible to analysis:*\n")
                for uf in self.package_structure.unparsed_features:
                    lines.append(f"- **{uf.feature}** ({uf.count} instances): {uf.note}")
                lines.append("")
            
            # Parse warnings
            if self.package_structure.parse_warnings:
                lines.append("### Parse Warnings\n")
                for w in self.package_structure.parse_warnings:
                    lines.append(f"- {w}")
                lines.append("")
        
        # Context notes
        if self.context_notes_md:
            lines.append("## Additional Context\n")
            lines.append(self.context_notes_md)
            lines.append("")
        
        return "\n".join(lines)
