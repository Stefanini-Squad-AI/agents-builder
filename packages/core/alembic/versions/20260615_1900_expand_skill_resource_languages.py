"""Expand SkillResourceLanguage enum.

Adds typescript, javascript, json, bash, dockerfile, html, css to the
``ck_skill_resources__language_valid`` CHECK constraint so DraftSkillBody
can produce resources in languages real frontend / DevOps work needs.

Revision ID: 20260615_1900
Revises: 20260605_1100
Create Date: 2026-06-15 19:00:00

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260615_1900"
down_revision: Union[str, None] = "20260605_1100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "'markdown', 'sql', 'yaml', 'python', 'plain'"
_NEW = (
    "'markdown', 'sql', 'yaml', 'python', 'typescript', "
    "'javascript', 'json', 'bash', 'dockerfile', 'html', 'css', 'plain'"
)


def upgrade() -> None:
    op.drop_constraint("ck_skill_resources__language_valid", "skill_resources")
    op.create_check_constraint(
        "ck_skill_resources__language_valid",
        "skill_resources",
        f"language IN ({_NEW})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_skill_resources__language_valid", "skill_resources")
    op.create_check_constraint(
        "ck_skill_resources__language_valid",
        "skill_resources",
        f"language IN ({_OLD})",
    )
