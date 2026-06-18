"""Add project_mcp_configs table for per-project MCP server configuration.

Revision ID: 20260604_1500
Revises: 20260601_1900
Create Date: 2026-06-04 15:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260604_1500"
down_revision: Union[str, None] = "20260601_1900"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_mcp_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("mcp_key", sa.String(length=100), nullable=False),
        sa.Column("env_vars_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "config_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=200), nullable=True),
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
        sa.UniqueConstraint(
            "project_id", "mcp_key", name="uq_project_mcp_configs_project_key"
        ),
    )
    op.create_index(
        "ix_project_mcp_configs_project", "project_mcp_configs", ["project_id"]
    )
    op.create_index(
        "ix_project_mcp_configs_enabled",
        "project_mcp_configs",
        ["project_id", "enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_mcp_configs_enabled", table_name="project_mcp_configs")
    op.drop_index("ix_project_mcp_configs_project", table_name="project_mcp_configs")
    op.drop_table("project_mcp_configs")
