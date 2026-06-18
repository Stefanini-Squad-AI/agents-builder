"""Add identified_gaps JSON column to projects.

Revision ID: 20260528_1000
Revises: 20260515_1400
Create Date: 2026-05-28 10:00:00.000000

Persists the `gaps` array produced by the ProposeSkillSet prompt so the
DraftSkillBody prompt can include them as context (minimal closed-loop).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260528_1000"
down_revision: str | None = "20260515_1400"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "identified_gaps",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "identified_gaps")
