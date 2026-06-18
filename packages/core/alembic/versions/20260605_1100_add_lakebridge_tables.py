"""Add Lakebridge integration tables.

Creates:
- databricks_configs: Per-project Databricks workspace connection
- lakebridge_jobs: Tracks CLI executions (analyze, transpile, reconcile)

Revision ID: 20260605_1100
Revises: 20260604_1500
Create Date: 2026-06-05 11:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260605_1100"
down_revision: Union[str, None] = "20260604_1500"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum values for CHECK constraints
_JOB_TYPE_VALUES = (
    "'analyze', 'transpile_bladebridge', 'transpile_morpheus', "
    "'transpile_switch', 'reconcile'"
)
_JOB_STATUS_VALUES = "'pending', 'running', 'completed', 'failed', 'cancelled'"


def upgrade() -> None:
    # Create databricks_configs table
    op.create_table(
        "databricks_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("workspace_url", sa.Text(), nullable=False),
        sa.Column(
            "cli_profile",
            sa.String(length=64),
            server_default="DEFAULT",
            nullable=False,
        ),
        sa.Column("pat_enc", sa.Text(), nullable=False),
        sa.Column(
            "catalog_name",
            sa.String(length=128),
            server_default="remorph",
            nullable=False,
        ),
        sa.Column(
            "schema_name",
            sa.String(length=128),
            server_default="transpiler",
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_databricks_configs_project"),
    )
    op.create_index(
        "ix_databricks_configs_project", "databricks_configs", ["project_id"]
    )

    # Create lakebridge_jobs table
    op.create_table(
        "lakebridge_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("source_dialect", sa.String(length=32), nullable=False),
        sa.Column("transpiler", sa.String(length=32), nullable=True),
        sa.Column(
            "input_artifact_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("result_artifact_id", sa.UUID(), nullable=True),
        sa.Column("cli_command", sa.Text(), nullable=False),
        sa.Column("cli_stdout", sa.Text(), nullable=True),
        sa.Column("cli_stderr", sa.Text(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["result_artifact_id"],
            ["project_artifacts.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            f"job_type IN ({_JOB_TYPE_VALUES})",
            name="ck_lakebridge_jobs_type",
        ),
        sa.CheckConstraint(
            f"status IN ({_JOB_STATUS_VALUES})",
            name="ck_lakebridge_jobs_status",
        ),
    )
    op.create_index(
        "ix_lakebridge_jobs_project_status",
        "lakebridge_jobs",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_lakebridge_jobs_project_type",
        "lakebridge_jobs",
        ["project_id", "job_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_lakebridge_jobs_project_type", table_name="lakebridge_jobs")
    op.drop_index("ix_lakebridge_jobs_project_status", table_name="lakebridge_jobs")
    op.drop_table("lakebridge_jobs")
    op.drop_index("ix_databricks_configs_project", table_name="databricks_configs")
    op.drop_table("databricks_configs")
