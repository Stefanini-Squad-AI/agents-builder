"""Add reconciliation and sign-off tables.

Revision ID: 20260601_1900
Revises: 20260528_1100
Create Date: 2026-06-01 19:00:00.000000

Adds four new tables for the Migration Workbench reconciliation and
sign-off workflow:

  reconciliation_runs          — one execution comparing source vs target
  reconciliation_check_results — per-check-type result (row_count, checksum …)
  signoff_requests             — formal approval gate for a migration milestone
  signoff_checklist_items      — individual checklist gates within a sign-off

Key design decisions captured here:
  - source_data_method / target_data_method on check_results: Phase A uses
    databricks_api for target and user_provided for source; Phase B (Lakebridge)
    uses lakebridge for both.
  - sql_warehouse_id on reconciliation_runs: Databricks SQL Warehouse used for
    Phase A target-side auto-queries via Statement Execution API.
  - auto_populated / auto_populated_from on checklist items: pr_02 (row counts)
    and pr_03 (checksums) are filled automatically from a ReconciliationRun;
    this field records which run ID triggered the auto-fill.
  - approved_by is TEXT, not a users FK: multi-user auth is a SPEC §16 non-goal
    for MVP. approved_at is always set server-side.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260601_1900"
down_revision: str | None = "20260528_1100"
branch_labels = None
depends_on = None

_RECON_STATUS = "'pending', 'running', 'passed', 'failed', 'warning', 'error'"
_RECON_CHECK_TYPE = "'row_count', 'checksum', 'key_match', 'aggregate', 'sample_data'"
_RECON_DATA_METHOD = "'user_provided', 'lakebridge', 'databricks_api'"
_SIGNOFF_TYPE = "'static_analysis', 'parallel_run', 'cutover', 'post_migration'"
_SIGNOFF_STATUS = "'draft', 'pending', 'approved', 'rejected', 'cancelled'"
_CHECKLIST_STATUS = "'not_started', 'in_progress', 'passed', 'failed', 'skipped', 'n/a'"


def upgrade() -> None:
    # ── 1. reconciliation_runs ──────────────────────────────────────────────
    op.create_table(
        "reconciliation_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "package_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etl_packages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_row_count", sa.Integer(), nullable=True),
        sa.Column("target_row_count", sa.Integer(), nullable=True),
        sa.Column("triggered_by", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("sql_warehouse_id", sa.String(200), nullable=True),
        sa.Column("uc_connection_name", sa.String(200), nullable=True),
        sa.Column("summary_json", postgresql.JSONB(), nullable=True),
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
        sa.CheckConstraint(f"status IN ({_RECON_STATUS})", name="reconciliation_runs_status_valid"),
    )
    op.create_index(
        "ix_reconciliation_runs_package",
        "reconciliation_runs",
        ["package_id"],
    )
    op.create_index(
        "ix_reconciliation_runs_project_status",
        "reconciliation_runs",
        ["project_id", "status"],
    )

    # ── 2. reconciliation_check_results ────────────────────────────────────
    op.create_table(
        "reconciliation_check_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("check_type", sa.String(20), nullable=False),
        sa.Column("source_table", sa.String(500), nullable=False),
        sa.Column("target_table", sa.String(500), nullable=False),
        sa.Column("source_value", sa.Text(), nullable=True),
        sa.Column("target_value", sa.Text(), nullable=True),
        sa.Column("match", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("variance", sa.Float(), nullable=True),
        sa.Column("variance_threshold", sa.Float(), nullable=True),
        sa.Column(
            "source_data_method",
            sa.String(20),
            nullable=False,
            server_default="user_provided",
        ),
        sa.Column(
            "target_data_method",
            sa.String(20),
            nullable=False,
            server_default="databricks_api",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            f"check_type IN ({_RECON_CHECK_TYPE})",
            name="reconciliation_check_results_type_valid",
        ),
        sa.CheckConstraint(
            f"source_data_method IN ({_RECON_DATA_METHOD})",
            name="reconciliation_check_results_src_method_valid",
        ),
        sa.CheckConstraint(
            f"target_data_method IN ({_RECON_DATA_METHOD})",
            name="reconciliation_check_results_tgt_method_valid",
        ),
    )
    op.create_index(
        "ix_reconciliation_check_results_run",
        "reconciliation_check_results",
        ["run_id"],
    )

    # ── 3. signoff_requests ─────────────────────────────────────────────────
    op.create_table(
        "signoff_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("signoff_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column(
            "package_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("wave_number", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.String(200), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.String(200), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "comments_json",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
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
        sa.CheckConstraint(
            f"signoff_type IN ({_SIGNOFF_TYPE})", name="signoff_requests_type_valid"
        ),
        sa.CheckConstraint(
            f"status IN ({_SIGNOFF_STATUS})", name="signoff_requests_status_valid"
        ),
    )
    op.create_index(
        "ix_signoff_requests_project_status",
        "signoff_requests",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_signoff_requests_package_type",
        "signoff_requests",
        ["project_id", "signoff_type"],
    )

    # ── 4. signoff_checklist_items ──────────────────────────────────────────
    op.create_table(
        "signoff_checklist_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "signoff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("signoff_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_key", sa.String(50), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(20), nullable=False, server_default="not_started"),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("completed_by", sa.String(200), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_populated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("auto_populated_from", sa.String(200), nullable=True),
        sa.UniqueConstraint(
            "signoff_id", "item_key",
            name="uq_signoff_checklist_items_signoff_key",
        ),
        sa.CheckConstraint(
            f"status IN ({_CHECKLIST_STATUS})",
            name="signoff_checklist_items_status_valid",
        ),
    )
    op.create_index(
        "ix_signoff_checklist_items_signoff",
        "signoff_checklist_items",
        ["signoff_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_signoff_checklist_items_signoff", table_name="signoff_checklist_items")
    op.drop_table("signoff_checklist_items")

    op.drop_index("ix_signoff_requests_package_type", table_name="signoff_requests")
    op.drop_index("ix_signoff_requests_project_status", table_name="signoff_requests")
    op.drop_table("signoff_requests")

    op.drop_index("ix_reconciliation_check_results_run", table_name="reconciliation_check_results")
    op.drop_table("reconciliation_check_results")

    op.drop_index("ix_reconciliation_runs_project_status", table_name="reconciliation_runs")
    op.drop_index("ix_reconciliation_runs_package", table_name="reconciliation_runs")
    op.drop_table("reconciliation_runs")
