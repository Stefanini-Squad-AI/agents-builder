"""Pydantic schemas for SSIS parsing and analysis results."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# SSIS Parsed Structure
# -----------------------------------------------------------------------------


class ConnectionManager(BaseModel):
    """Connection manager definition from SSIS package."""
    
    name: str = Field(..., description="Connection manager name")
    object_name: str | None = Field(None, description="DTS:ObjectName attribute")
    connection_type: str = Field(..., description="OLEDB, ADO.NET, FLATFILE, etc.")
    connection_string: str | None = Field(None, description="Connection string (may be expression)")
    server: str | None = Field(None, description="Extracted server name")
    database: str | None = Field(None, description="Extracted database name")
    provider: str | None = Field(None, description="Provider name")
    is_expression_based: bool = Field(False, description="Uses expression for connection string")


class Column(BaseModel):
    """Column definition."""
    
    name: str
    data_type: str | None = None
    length: int | None = None
    precision: int | None = None
    scale: int | None = None


class ColumnMapping(BaseModel):
    """Column mapping from source to destination."""
    
    source_column: str
    destination_column: str
    transform: str | None = None


class Source(BaseModel):
    """Data flow source component."""
    
    name: str
    component_type: str = Field(..., description="OLE DB Source, Flat File Source, etc.")
    connection_ref: str | None = Field(None, description="Connection manager reference")
    access_mode: str | None = Field(None, description="Table, SQL Command, Variable")
    table_name: str | None = Field(None, description="Source table name")
    sql_command: str | None = Field(None, description="SQL query if access_mode is SQL Command")
    columns: list[Column] = Field(default_factory=list)


class Destination(BaseModel):
    """Data flow destination component."""
    
    name: str
    component_type: str = Field(..., description="OLE DB Destination, Flat File Destination, etc.")
    connection_ref: str | None = Field(None, description="Connection manager reference")
    table_name: str | None = Field(None, description="Destination table name")
    access_mode: str | None = None
    columns: list[ColumnMapping] = Field(default_factory=list)


class Transform(BaseModel):
    """Data flow transformation component."""
    
    name: str
    component_type: str = Field(..., description="Lookup, Derived Column, Merge Join, etc.")
    description: str | None = None
    properties: dict = Field(default_factory=dict)


class DataFlow(BaseModel):
    """Data flow task containing sources, transforms, and destinations."""
    
    name: str
    description: str | None = None
    sources: list[Source] = Field(default_factory=list)
    destinations: list[Destination] = Field(default_factory=list)
    transformations: list[Transform] = Field(default_factory=list)


class Variable(BaseModel):
    """Package or container variable."""
    
    name: str
    namespace: str = "User"
    data_type: str | None = None
    value: str | None = None
    expression: str | None = None
    is_expression: bool = False


class Parameter(BaseModel):
    """Package parameter."""
    
    name: str
    data_type: str | None = None
    value: str | None = None
    required: bool = False
    sensitive: bool = False


class TaskType(str, Enum):
    """SSIS task types."""
    
    DATA_FLOW = "Data Flow Task"
    EXECUTE_SQL = "Execute SQL Task"
    SCRIPT = "Script Task"
    EXECUTE_PACKAGE = "Execute Package Task"
    FOR_LOOP = "For Loop Container"
    FOREACH_LOOP = "Foreach Loop Container"
    SEQUENCE = "Sequence Container"
    EXPRESSION = "Expression Task"
    FILE_SYSTEM = "File System Task"
    FTP = "FTP Task"
    SEND_MAIL = "Send Mail Task"
    EXECUTE_PROCESS = "Execute Process Task"
    OTHER = "Other"


class Task(BaseModel):
    """Control flow task or container."""
    
    name: str
    task_type: TaskType
    description: str | None = None
    disabled: bool = False
    
    # For Execute SQL Task
    sql_statement: str | None = None
    connection_ref: str | None = None
    
    # For containers
    child_tasks: list["Task"] = Field(default_factory=list)
    
    # For Data Flow Task - link to DataFlow
    data_flow: DataFlow | None = None
    
    # Generic properties
    properties: dict = Field(default_factory=dict)


class PrecedenceConstraint(BaseModel):
    """Precedence constraint between tasks."""
    
    from_task: str
    to_task: str
    constraint_type: str = "Success"  # Success, Failure, Completion, Expression
    expression: str | None = None


class Annotation(BaseModel):
    """Developer annotation/comment."""
    
    text: str
    position_x: float | None = None
    position_y: float | None = None


class SSISPackage(BaseModel):
    """Complete parsed SSIS package structure."""
    
    name: str
    description: str | None = None
    creation_date: str | None = None
    creator_name: str | None = None
    
    # Connection managers
    connection_managers: list[ConnectionManager] = Field(default_factory=list)
    
    # Control flow
    tasks: list[Task] = Field(default_factory=list)
    precedence_constraints: list[PrecedenceConstraint] = Field(default_factory=list)
    
    # Data flows (extracted from Data Flow Tasks)
    data_flows: list[DataFlow] = Field(default_factory=list)
    
    # Variables and parameters
    variables: list[Variable] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
    
    # Metadata
    annotations: list[Annotation] = Field(default_factory=list)
    disabled_tasks: list[str] = Field(default_factory=list)
    
    # Parsing metadata
    parse_warnings: list[str] = Field(default_factory=list)
    
    def get_all_connections_used(self) -> set[str]:
        """Get all connection manager names referenced in the package."""
        connections = set()
        for task in self.tasks:
            if task.connection_ref:
                connections.add(task.connection_ref)
        for df in self.data_flows:
            for source in df.sources:
                if source.connection_ref:
                    connections.add(source.connection_ref)
            for dest in df.destinations:
                if dest.connection_ref:
                    connections.add(dest.connection_ref)
        return connections


# Update forward reference
Task.model_rebuild()


# -----------------------------------------------------------------------------
# Connection Points (what tables are read/written)
# -----------------------------------------------------------------------------


class TableRef(BaseModel):
    """Reference to a table."""
    
    schema_name: str | None = "dbo"
    table_name: str
    connection_ref: str | None = None
    access_type: str = "table"  # table, view, query
    sql_query: str | None = None


class FileRef(BaseModel):
    """Reference to a file."""
    
    file_path: str | None = None
    connection_ref: str | None = None
    file_type: str | None = None  # csv, txt, excel, etc.


class ColumnLineage(BaseModel):
    """Column-level lineage mapping."""
    
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    transformation: str | None = None


class ExtractedConnectionPoints(BaseModel):
    """Connection points extracted from a package."""
    
    # Sources
    source_tables: list[TableRef] = Field(default_factory=list)
    source_files: list[FileRef] = Field(default_factory=list)
    source_connections: list[str] = Field(default_factory=list)
    
    # Targets
    target_tables: list[TableRef] = Field(default_factory=list)
    target_files: list[FileRef] = Field(default_factory=list)
    target_connections: list[str] = Field(default_factory=list)
    
    # Dependencies
    declared_predecessors: list[str] = Field(default_factory=list)
    
    # Column lineage (optional)
    column_lineage: list[ColumnLineage] = Field(default_factory=list)
    
    # Flags for manual review
    has_dynamic_sources: bool = False
    has_dynamic_destinations: bool = False
    extraction_warnings: list[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Analysis Results
# -----------------------------------------------------------------------------


class DetectedPattern(BaseModel):
    """A pattern detected in the package matching tech profile."""
    
    pattern_id: str
    pattern_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str | None = None
    location: str | None = None  # Where in the package
    migration_implication: str | None = None


class BusinessRuleDiscovery(BaseModel):
    """A business rule discovered during analysis."""
    
    rule_id: str
    rule_name: str
    description: str | None = None
    source_code: str | None = None
    category: str | None = None
    applies_to_tables: list[str] = Field(default_factory=list)


class BlockerSeverity(str, Enum):
    """Blocker severity levels."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BlockerType(str, Enum):
    """Types of blockers."""
    
    TECHNICAL = "technical"
    BUSINESS = "business"
    INFRASTRUCTURE = "infrastructure"
    DATA_QUALITY = "data_quality"


class BlockerItem(BaseModel):
    """A blocker requiring attention."""
    
    blocker_type: BlockerType
    title: str
    description: str | None = None
    severity: BlockerSeverity
    
    # For auto-resolution
    decision_type: str | None = None
    auto_resolved: bool = False
    resolution: str | None = None
    
    # Context
    affected_components: list[str] = Field(default_factory=list)
    suggested_action: str | None = None


class DecisionItem(BaseModel):
    """A decision needed from the user."""
    
    decision_type: str
    question: str
    options: list[str] = Field(default_factory=list)
    context: str | None = None
    default_option: str | None = None


class PackageAnalysis(BaseModel):
    """Complete analysis results for a package."""
    
    package_id: uuid.UUID
    
    # Classification
    complexity: str = "medium"
    domain: str | None = None
    estimated_effort: str | None = None
    
    # Patterns
    detected_patterns: list[DetectedPattern] = Field(default_factory=list)
    
    # Business rules
    business_rules: list[BusinessRuleDiscovery] = Field(default_factory=list)
    
    # Blockers and decisions
    blockers: list[BlockerItem] = Field(default_factory=list)
    decisions_needed: list[DecisionItem] = Field(default_factory=list)
    
    # Recommendations
    analysis_summary: str | None = None
    target_notebook_structure: str | None = None
    migration_notes: list[str] = Field(default_factory=list)
    
    # Backward analysis: target architecture plan
    generation_plan: "GenerationPlan | None" = Field(
        None,
        description="Planned target Databricks notebook structure (backward analysis)",
    )
    
    # Metadata
    analyzed_at: datetime | None = None
    llm_run_id: uuid.UUID | None = None


# -----------------------------------------------------------------------------
# API Response Models
# -----------------------------------------------------------------------------


class AnalysisResultView(BaseModel):
    """Analysis result for API response."""
    
    package_id: uuid.UUID
    package_name: str
    status: str
    
    complexity: str | None = None
    domain: str | None = None
    
    patterns_count: int = 0
    blockers_count: int = 0
    auto_resolved_count: int = 0
    
    analyzed_at: datetime | None = None
    
    model_config = {"from_attributes": True}


class BlockerView(BaseModel):
    """Blocker for API response."""
    
    id: uuid.UUID
    package_id: uuid.UUID
    
    blocker_type: str
    title: str
    description: str | None = None
    severity: str
    
    auto_resolved: bool = False
    resolution: str | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    
    model_config = {"from_attributes": True}


# Resolve forward reference for GenerationPlan
from app.modules.migration_workbench.analysis.strategy_classifier import (  # noqa: E402
    GenerationPlan,
)

PackageAnalysis.model_rebuild()

