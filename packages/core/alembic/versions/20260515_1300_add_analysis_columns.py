"""Add analysis columns to etl_packages.

Revision ID: 20260515_1300
Revises: 20260515_1200
Create Date: 2026-05-15

Adds columns for package analysis:
- file_path: Path to the .dtsx or other package file
- source_technology: Technology type (ssis, airflow, etc.)
- analysis_status: pending, analyzing, analyzed, failed
- analysis_error: Error message if analysis failed
- analysis_json: Full analysis results as JSONB
- estimated_effort: xs, s, m, l, xl
- blockers_count: Total blockers found
- auto_resolved_count: Blockers auto-resolved from context
- parse_warnings: Warnings from parsing
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260515_1300"
down_revision: str | None = "20260515_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add columns to etl_packages
    op.add_column(
        "etl_packages",
        sa.Column("file_path", sa.String(1000), nullable=True),
    )
    op.add_column(
        "etl_packages",
        sa.Column("source_technology", sa.String(50), nullable=True),
    )
    op.add_column(
        "etl_packages",
        sa.Column("analysis_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "etl_packages",
        sa.Column("analysis_error", sa.String(500), nullable=True),
    )
    op.add_column(
        "etl_packages",
        sa.Column("analysis_json", postgresql.JSONB, nullable=True),
    )
    op.add_column(
        "etl_packages",
        sa.Column("estimated_effort", sa.String(10), nullable=True),
    )
    op.add_column(
        "etl_packages",
        sa.Column("blockers_count", sa.Integer, nullable=True),
    )
    op.add_column(
        "etl_packages",
        sa.Column("auto_resolved_count", sa.Integer, nullable=True),
    )
    op.add_column(
        "etl_packages",
        sa.Column("parse_warnings", postgresql.ARRAY(sa.Text), nullable=True),
    )
    
    # Add index for analysis status
    op.create_index(
        "ix_etl_packages_analysis_status",
        "etl_packages",
        ["project_id", "analysis_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_etl_packages_analysis_status")
    op.drop_column("etl_packages", "parse_warnings")
    op.drop_column("etl_packages", "auto_resolved_count")
    op.drop_column("etl_packages", "blockers_count")
    op.drop_column("etl_packages", "estimated_effort")
    op.drop_column("etl_packages", "analysis_json")
    op.drop_column("etl_packages", "analysis_error")
    op.drop_column("etl_packages", "analysis_status")
    op.drop_column("etl_packages", "source_technology")
    op.drop_column("etl_packages", "file_path")
