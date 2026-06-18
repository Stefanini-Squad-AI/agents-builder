"""Add project_gaps entity table.

Revision ID: 20260528_1100
Revises: 20260528_1000
Create Date: 2026-05-28 11:00:00.000000

Promotes the `identified_gaps` JSON snapshot to a first-class entity with
lifecycle (open / addressed_by_skill / covered_by_mcp / out_of_scope) so the
UI can track each gap's resolution and metrics can be computed.

The legacy `projects.identified_gaps` column is kept for backward compatibility
of any synchronous reads and as a cache. It is no longer the source of truth
for DraftSkillBody — open `project_gaps` rows are.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260528_1100"
down_revision: str | None = "20260528_1000"
branch_labels = None
depends_on = None

_STATUS_VALUES = "'open', 'addressed_by_skill', 'covered_by_mcp', 'out_of_scope'"
_SOURCE_VALUES = "'propose_skill_set', 'manual'"


def upgrade() -> None:
    op.create_table(
        "project_gaps",
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
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("title_key", sa.Text(), nullable=False),
        sa.Column(
            "source",
            sa.String(32),
            nullable=False,
            server_default="propose_skill_set",
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "addressed_by_skill_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("skills.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("covered_by_mcp_key", sa.Text(), nullable=True),
        sa.Column("decision_rationale", sa.Text(), nullable=True),
        sa.Column(
            "decided_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(f"status IN ({_STATUS_VALUES})", name="status_valid"),
        sa.CheckConstraint(f"source IN ({_SOURCE_VALUES})", name="source_valid"),
        sa.UniqueConstraint("project_id", "title_key", name="project_gap_title_unique"),
    )
    op.create_index(
        "ix_project_gaps__project_status",
        "project_gaps",
        ["project_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_gaps__project_status", table_name="project_gaps")
    op.drop_table("project_gaps")
