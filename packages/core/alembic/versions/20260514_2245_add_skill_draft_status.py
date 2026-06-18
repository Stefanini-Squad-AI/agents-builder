"""Add draft status tracking to skills.

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-14 22:45:00.000000

Adds columns to track skill drafting progress:
  - draft_status: 'none', 'pending', 'drafting', 'success', 'error'
  - last_llm_run_id: UUID of the last LLM run that drafted this skill
  - draft_error: Error message if draft failed
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b2c3d4e5f6g7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

_DRAFT_STATUS_VALUES = "'none', 'pending', 'drafting', 'success', 'error'"


def upgrade() -> None:
    # Add new columns
    op.add_column(
        "skills",
        sa.Column(
            "draft_status",
            sa.String(16),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "skills",
        sa.Column(
            "last_llm_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "skills",
        sa.Column(
            "draft_error",
            sa.Text(),
            nullable=True,
        ),
    )

    # Add check constraint for draft_status
    op.create_check_constraint(
        "draft_status_valid",
        "skills",
        f"draft_status IN ({_DRAFT_STATUS_VALUES})",
    )


def downgrade() -> None:
    op.drop_constraint("draft_status_valid", "skills")
    op.drop_column("skills", "draft_error")
    op.drop_column("skills", "last_llm_run_id")
    op.drop_column("skills", "draft_status")
