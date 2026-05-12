"""Add bedrock to LlmProvider CHECK constraints.

Revision ID: a1b2c3d4e5f6
Revises: 284feb88a8ef
Create Date: 2026-05-12 15:17:00.000000

Updates two CHECK constraints that enumerate allowed LlmProvider values:
  - llm_runs.provider        (ck_llm_runs__provider_valid)
  - projects.llm_provider    (ck_projects__llm_provider_valid)

Both constraints are dropped and recreated with the new value 'bedrock' added.
"""

from __future__ import annotations

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "284feb88a8ef"
branch_labels = None
depends_on = None

_OLD_PROVIDERS = "'anthropic', 'openai', 'ollama'"
_NEW_PROVIDERS = "'anthropic', 'openai', 'ollama', 'bedrock'"


def upgrade() -> None:
    # llm_runs.provider
    op.drop_constraint("ck_llm_runs__provider_valid", "llm_runs")
    op.create_check_constraint(
        "ck_llm_runs__provider_valid",
        "llm_runs",
        f"provider IN ({_NEW_PROVIDERS})",
    )

    # projects.llm_provider
    op.drop_constraint("ck_projects__llm_provider_valid", "projects")
    op.create_check_constraint(
        "ck_projects__llm_provider_valid",
        "projects",
        f"llm_provider IN ({_NEW_PROVIDERS})",
    )


def downgrade() -> None:
    # llm_runs.provider
    op.drop_constraint("ck_llm_runs__provider_valid", "llm_runs")
    op.create_check_constraint(
        "ck_llm_runs__provider_valid",
        "llm_runs",
        f"provider IN ({_OLD_PROVIDERS})",
    )

    # projects.llm_provider
    op.drop_constraint("ck_projects__llm_provider_valid", "projects")
    op.create_check_constraint(
        "ck_projects__llm_provider_valid",
        "projects",
        f"llm_provider IN ({_OLD_PROVIDERS})",
    )
