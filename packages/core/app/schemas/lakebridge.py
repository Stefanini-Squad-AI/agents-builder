"""Pydantic schemas for Lakebridge integration API.

Request/response models for Databricks configuration, job tracking,
and analyzer results.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums import LakebridgeJobStatus, LakebridgeJobType


# -----------------------------------------------------------------------------
# Databricks Config Schemas
# -----------------------------------------------------------------------------


class DatabricksConfigCreate(BaseModel):
    """Request to create or update Databricks workspace configuration."""

    workspace_url: str = Field(
        ...,
        min_length=1,
        description="Databricks workspace URL (e.g., https://myorg.cloud.databricks.com)",
    )
    cli_profile: str = Field(
        default="DEFAULT",
        max_length=64,
        description="Databricks CLI profile name",
    )
    pat: str = Field(
        ...,
        min_length=1,
        description="Personal Access Token (encrypted before storage)",
    )
    catalog_name: str = Field(
        default="remorph",
        max_length=128,
        description="Default Unity Catalog for Lakebridge operations",
    )
    schema_name: str = Field(
        default="transpiler",
        max_length=128,
        description="Default schema within the catalog",
    )


class DatabricksConfigView(BaseModel):
    """API response for Databricks configuration.

    Note: PAT is never included in responses — only stored encrypted.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    workspace_url: str
    cli_profile: str
    catalog_name: str
    schema_name: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class DatabricksConfigToggle(BaseModel):
    """Request to enable/disable Databricks integration."""

    enabled: bool


# -----------------------------------------------------------------------------
# Prerequisites Schemas (Phase 1c)
# -----------------------------------------------------------------------------


class PrerequisitesView(BaseModel):
    """Result of checking Lakebridge CLI prerequisites."""

    cli_installed: bool = Field(description="Databricks CLI is installed")
    lakebridge_installed: bool = Field(description="Lakebridge extension is installed")
    workspace_reachable: bool = Field(description="Workspace is reachable with PAT")
    all_ok: bool = Field(description="All prerequisites are met")


# -----------------------------------------------------------------------------
# Lakebridge Job Schemas (Phase 1d)
# -----------------------------------------------------------------------------


class LakebridgeJobView(BaseModel):
    """API response for a Lakebridge job."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    job_type: LakebridgeJobType
    status: LakebridgeJobStatus
    source_dialect: str
    transpiler: str | None = None
    input_artifact_ids: list[str] = Field(default_factory=list)
    result_artifact_id: uuid.UUID | None = None
    cli_command: str
    cli_stdout: str | None = None
    cli_stderr: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    error_message: str | None = None
    metadata_json: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AnalyzeRequest(BaseModel):
    """Request to start a Lakebridge analyzer job."""

    source_dialect: str = Field(
        ...,
        description="Source dialect (e.g., oracle, snowflake, mssql, ssis)",
    )
    artifact_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Specific artifacts to analyze; None = all in code_to_be_migrated group",
    )


class AnalyzerSummaryView(BaseModel):
    """Summary of the latest analyzer results."""

    model_config = ConfigDict(extra="forbid")

    total_files: int
    analyzed_files: int
    skipped_files: int
    high_complexity_count: int
    very_high_complexity_count: int
    source_dialect: str
    complexity_distribution: dict[str, int] = Field(default_factory=dict)
    analyzed_at: datetime | None = None


# -----------------------------------------------------------------------------
# Transpiler Schemas (Phase 2)
# -----------------------------------------------------------------------------


class TranspileRequest(BaseModel):
    """Request to start a Lakebridge transpiler job."""

    source_dialect: str = Field(
        ...,
        description="Source dialect (oracle, snowflake, tsql, ssis)",
    )
    transpiler: str = Field(
        default="bladebridge",
        description="Transpiler to use: bladebridge, morpheus, switch",
    )
    artifact_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Specific artifacts to transpile; None = all code artifacts",
    )
    skip_validation: bool = Field(
        default=False,
        description="Skip semantic validation against catalog",
    )
    options: dict = Field(
        default_factory=dict,
        description="Transpiler-specific options",
    )


class TranspileStatusView(BaseModel):
    """Overview of transpilation progress for a project."""

    total_artifacts: int = Field(description="Total code artifacts in project")
    transpiled_count: int = Field(description="Artifacts with successful transpilation")
    failed_count: int = Field(description="Artifacts with failed transpilation")
    pending_count: int = Field(description="Artifacts not yet transpiled")
    latest_job_id: uuid.UUID | None = Field(description="Most recent transpiler job")
    latest_job_status: LakebridgeJobStatus | None = Field(description="Status of latest job")
    transpiler_used: str | None = Field(description="Transpiler used in latest job")


class TranspiledArtifactInfo(BaseModel):
    """Information about a transpiled output artifact."""

    source_artifact_id: uuid.UUID
    source_filename: str
    output_artifact_id: uuid.UUID
    output_filename: str
    transpiler: str
    success: bool
    error_message: str | None = None


# -----------------------------------------------------------------------------
# Reconciler Schemas (Phase 3)
# -----------------------------------------------------------------------------


class ReconcileRequest(BaseModel):
    """Request to start a Lakebridge reconciliation job."""

    source_dialect: str = Field(
        default="tsql",
        description="Source dialect (e.g., tsql, oracle, snowflake)",
    )
    source_artifact_ids: list[uuid.UUID] = Field(
        ...,
        min_length=1,
        description="Original source code artifacts to reconcile",
    )
    transpiled_artifact_ids: list[uuid.UUID] = Field(
        ...,
        min_length=1,
        description="Transpiled output artifacts to compare against",
    )
    source_connection: str = Field(
        ...,
        min_length=1,
        description="Source database connection string or MCP config key",
    )
    sample_size: int = Field(
        default=1000,
        ge=1,
        le=100000,
        description="Number of rows to compare per table",
    )
    tolerance: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Numeric comparison tolerance (0.0 = exact match)",
    )
    tables: list[str] | None = Field(
        default=None,
        description="Specific tables to reconcile; None = all tables",
    )


class ReconcileTableResult(BaseModel):
    """Reconciliation result for a single table."""

    table_name: str
    source_row_count: int
    target_row_count: int
    row_count_match: bool
    schema_match: bool
    sample_match: bool
    sample_rows_compared: int = 0
    mismatched_rows: int = 0
    discrepancies: list[str] = Field(default_factory=list)


class ReconcileSummaryView(BaseModel):
    """Summary of reconciliation results."""

    total_tables: int
    passed_tables: int
    failed_tables: int
    pass_rate: float = Field(description="Percentage of tables that passed (0.0-100.0)")
    row_count_mismatches: int = Field(description="Tables with row count differences")
    schema_mismatches: int = Field(description="Tables with schema differences")
    data_mismatches: int = Field(description="Tables with data differences")
    table_results: list[ReconcileTableResult] = Field(default_factory=list)
    reconciled_at: datetime | None = None
    job_id: uuid.UUID | None = None
    source_dialect: str | None = None


class ReconcileStatusView(BaseModel):
    """Overview of reconciliation status for a project."""

    total_reconcile_jobs: int
    successful_jobs: int
    failed_jobs: int
    latest_job_id: uuid.UUID | None
    latest_job_status: LakebridgeJobStatus | None
    latest_pass_rate: float | None = Field(description="Pass rate of latest completed job")
