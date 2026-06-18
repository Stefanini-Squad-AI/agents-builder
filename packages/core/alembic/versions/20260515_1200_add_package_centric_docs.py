"""Add package-centric cards and documentation tracking.

Revision ID: 20260515_1200
Revises: 20260515_1100
Create Date: 2026-05-15

Adds:
- card_prefix to etl_packages
- package_id to cards
- map_relationships table
- migration_doc_snapshots table
- documentation_changes table
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260515_1200"
down_revision: str | None = "20260515_1100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Add card_prefix to etl_packages ---
    op.add_column(
        "etl_packages",
        sa.Column("card_prefix", sa.String(10), nullable=True),
    )
    
    # --- Add package_id to cards ---
    op.add_column(
        "cards",
        sa.Column(
            "package_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etl_packages.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_cards__package", "cards", ["package_id"])
    
    # --- map_relationships ---
    op.create_table(
        "map_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_package_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("etl_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_package_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("etl_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", sa.String(30), nullable=False),
        sa.Column("shared_tables", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("direction", sa.String(20), nullable=False, server_default="reads_from"),
        sa.Column("dependency_reason", sa.String(200), nullable=True),
        sa.Column("is_blocking", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("discovered_by", sa.String(20), nullable=False, server_default="auto"),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "relationship_type IN ('data_dependency', 'execution_dependency')",
            name="ck_map_relationships__map_relationships_type_valid",
        ),
        sa.CheckConstraint(
            "direction IN ('reads_from', 'writes_to', 'bidirectional')",
            name="ck_map_relationships__map_relationships_direction_valid",
        ),
    )
    op.create_index("ix_map_relationships_project", "map_relationships", ["project_id"])
    op.create_index("ix_map_relationships_source", "map_relationships", ["source_package_id"])
    op.create_index("ix_map_relationships_target", "map_relationships", ["target_package_id"])
    
    # --- migration_doc_snapshots ---
    op.create_table(
        "migration_doc_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("snapshot_type", sa.String(20), nullable=False, server_default="full"),
        sa.Column("project_summary_md", sa.Text, nullable=False),
        sa.Column("migration_map_md", sa.Text, nullable=False),
        sa.Column("packages_summary_md", sa.Text, nullable=False),
        sa.Column("state_json", postgresql.JSONB, nullable=False),
        sa.Column("trigger_event", sa.String(100), nullable=False),
        sa.Column("trigger_package_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("etl_packages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "snapshot_type IN ('full', 'incremental')",
            name="ck_migration_doc_snapshots__migration_doc_snapshots_type_valid",
        ),
    )
    op.create_index("ix_migration_doc_snapshots_project", "migration_doc_snapshots", ["project_id"])
    op.create_index("ix_migration_doc_snapshots_version", "migration_doc_snapshots", ["project_id", "version"])
    
    # --- documentation_changes ---
    op.create_table(
        "documentation_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("migration_doc_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("migration_doc_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("change_type", sa.String(30), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("etl_packages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("previous_value", sa.Text, nullable=True),
        sa.Column("new_value", sa.Text, nullable=True),
        sa.Column("significance", sa.String(20), nullable=False, server_default="info"),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "change_type IN ('gap_filled', 'new_blocker', 'blocker_resolved', 'progress', 'wave_change', 'dependency_added', 'dependency_removed', 'decision_made', 'connection_mapped', 'rule_implemented')",
            name="ck_documentation_changes__documentation_changes_type_valid",
        ),
        sa.CheckConstraint(
            "category IN ('connections', 'rules', 'blockers', 'progress', 'waves', 'dependencies', 'decisions')",
            name="ck_documentation_changes__documentation_changes_category_valid",
        ),
        sa.CheckConstraint(
            "significance IN ('info', 'notable', 'critical')",
            name="ck_documentation_changes__documentation_changes_significance_valid",
        ),
    )
    op.create_index("ix_documentation_changes_project", "documentation_changes", ["project_id"])
    op.create_index("ix_documentation_changes_snapshots", "documentation_changes", ["from_snapshot_id", "to_snapshot_id"])


def downgrade() -> None:
    op.drop_table("documentation_changes")
    op.drop_table("migration_doc_snapshots")
    op.drop_table("map_relationships")
    op.drop_index("ix_cards__package", table_name="cards")
    op.drop_column("cards", "package_id")
    op.drop_column("etl_packages", "card_prefix")
