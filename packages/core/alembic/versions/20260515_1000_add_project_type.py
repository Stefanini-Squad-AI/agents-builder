"""Add project type and migration columns.

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-05-15 10:00:00.000000

Adds columns to support Migration Workbench:
  - project_type: 'application' | 'migration'
  - source_technology: Source ETL technology (e.g., 'ssis')
  - target_technology: Target platform (e.g., 'databricks')
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6g7h8"
down_revision = "b2c3d4e5f6g7"
branch_labels = None
depends_on = None

_PROJECT_TYPE_VALUES = "'application', 'migration'"


def upgrade() -> None:
    # Add project_type column with default 'application'
    op.add_column(
        "projects",
        sa.Column(
            "project_type",
            sa.String(32),
            nullable=False,
            server_default="application",
        ),
    )

    # Add source_technology column (nullable, only for migrations)
    op.add_column(
        "projects",
        sa.Column(
            "source_technology",
            sa.String(32),
            nullable=True,
        ),
    )

    # Add target_technology column (nullable, only for migrations)
    op.add_column(
        "projects",
        sa.Column(
            "target_technology",
            sa.String(32),
            nullable=True,
        ),
    )

    # Add check constraint for project_type
    op.create_check_constraint(
        "project_type_valid",
        "projects",
        f"project_type IN ({_PROJECT_TYPE_VALUES})",
    )

    # Add check constraint: migration projects must have source_technology
    op.create_check_constraint(
        "migration_requires_source",
        "projects",
        "project_type != 'migration' OR source_technology IS NOT NULL",
    )


def downgrade() -> None:
    # Drop constraints first
    op.drop_constraint("migration_requires_source", "projects", type_="check")
    op.drop_constraint("project_type_valid", "projects", type_="check")

    # Drop columns
    op.drop_column("projects", "target_technology")
    op.drop_column("projects", "source_technology")
    op.drop_column("projects", "project_type")
