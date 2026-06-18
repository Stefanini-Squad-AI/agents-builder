"""Lakebridge integration domain models.

Contains SQLAlchemy ORM models for:
- DatabricksConfig: Per-project Databricks workspace connection.
- LakebridgeJob: Tracks CLI executions (analyze, transpile, reconcile).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampsMixin, UuidPkMixin
from app.enums import LakebridgeJobStatus, LakebridgeJobType, values_csv

if TYPE_CHECKING:
    from app.domain.projects import Project, ProjectArtifact


# -----------------------------------------------------------------------------
# DatabricksConfig — Per-project Databricks workspace connection
# -----------------------------------------------------------------------------


class DatabricksConfig(UuidPkMixin, TimestampsMixin, Base):
    """Per-project Databricks workspace connection.

    Stores the workspace URL, CLI profile, and encrypted PAT for
    authenticating Lakebridge CLI operations. Each project can have
    at most one Databricks config (1:1 relationship).

    The PAT is encrypted using Fernet with project-scoped keys
    (same encryption as MCP secrets in app/crypto.py).
    """

    __tablename__ = "databricks_configs"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_databricks_configs_project"),
        Index("ix_databricks_configs_project", "project_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Databricks workspace URL (e.g., https://myorg.cloud.databricks.com)
    workspace_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Databricks CLI profile name in ~/.databrickscfg
    # Note: LakebridgeClient uses env vars, not this profile directly
    cli_profile: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="DEFAULT"
    )

    # Fernet-encrypted Personal Access Token
    # Never returned in API responses; decrypted only for CLI execution
    pat_enc: Mapped[str] = mapped_column(Text, nullable=False)

    # Default Unity Catalog for Lakebridge operations
    catalog_name: Mapped[str] = mapped_column(
        String(128), nullable=False, server_default="remorph"
    )

    # Default schema within the catalog
    schema_name: Mapped[str] = mapped_column(
        String(128), nullable=False, server_default="transpiler"
    )

    # Toggle Lakebridge integration on/off without deleting config
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    # Relationship
    project: Mapped["Project"] = relationship(
        "Project", back_populates="databricks_config"
    )


# -----------------------------------------------------------------------------
# LakebridgeJob — Tracks Lakebridge CLI executions
# -----------------------------------------------------------------------------


class LakebridgeJob(UuidPkMixin, TimestampsMixin, Base):
    """Tracks a Lakebridge CLI execution.

    Records the full lifecycle of analyze, transpile, or reconcile
    operations including the CLI command, captured output, exit code,
    duration, and any result artifacts created.

    For Switch (LLM transpiler), metadata_json contains the async
    Databricks job URL for polling.
    """

    __tablename__ = "lakebridge_jobs"
    __table_args__ = (
        CheckConstraint(
            f"job_type IN ({values_csv(LakebridgeJobType)})",
            name="ck_lakebridge_jobs_type",
        ),
        CheckConstraint(
            f"status IN ({values_csv(LakebridgeJobStatus)})",
            name="ck_lakebridge_jobs_status",
        ),
        Index("ix_lakebridge_jobs_project_status", "project_id", "status"),
        Index("ix_lakebridge_jobs_project_type", "project_id", "job_type"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Job type: analyze, transpile_bladebridge, transpile_morpheus, transpile_switch, reconcile
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Job status: pending, running, completed, failed, cancelled
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="pending"
    )

    # Source dialect used (e.g., oracle, snowflake, mssql, ssis)
    source_dialect: Mapped[str] = mapped_column(String(32), nullable=False)

    # Transpiler used (nullable for analyze/reconcile jobs)
    # Values: bladebridge, morpheus, switch
    transpiler: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Input artifact IDs (JSONB array of UUIDs)
    # Which Workshop artifacts were used as input
    input_artifact_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    # Result artifact ID (FK to project_artifacts)
    # Points to the artifact created from job output (e.g., analyzer JSON report)
    result_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Full CLI command string that was executed
    cli_command: Mapped[str] = mapped_column(Text, nullable=False)

    # Captured stdout (truncated to 64KB)
    cli_stdout: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Captured stderr (truncated to 64KB)
    cli_stderr: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Process exit code
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Wall-clock duration of the CLI execution in milliseconds
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Human-readable error message if job failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Job-type-specific metadata (JSONB)
    # Examples:
    #   - Switch: {"switch_job_url": "https://..."}
    #   - Reconcile: {"recon_id": "..."}
    #   - Analyzer: {"report_path": "..."}
    #   - Card link: {"card_id": "..."}
    metadata_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project", back_populates="lakebridge_jobs"
    )
    result_artifact: Mapped["ProjectArtifact | None"] = relationship(
        "ProjectArtifact", back_populates="lakebridge_jobs"
    )
