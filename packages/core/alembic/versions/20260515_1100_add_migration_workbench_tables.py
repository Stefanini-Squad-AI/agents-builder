"""Add migration workbench tables.

Revision ID: 20260515_1100
Revises: 20260515_1000
Create Date: 2026-05-15

Creates tables for Migration Workbench Phase 2:
- etl_packages: Individual packages being migrated
- package_connection_points: Extracted data flows
- migration_connections: Shared connection definitions
- migration_business_rules: Discovered business rules
- migration_resolved_decisions: Project-wide decisions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260515_1100"
down_revision: str | None = "c3d4e5f6g7h8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- etl_packages ---
    op.create_table(
        "etl_packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_artifacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("package_name", sa.String(500), nullable=False),
        sa.Column("package_path", sa.String(1000), nullable=True),
        sa.Column("domain", sa.String(200), nullable=True),
        sa.Column("complexity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(20), nullable=False, server_default="registered"),
        sa.Column("pending_feedback_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("blocking_feedback_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("migrated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('registered', 'analyzing', 'analyzed', 'needs_feedback', 'ready', 'generating', 'generated', 'validating', 'validated', 'migrated', 'verified')",
            name="ck_etl_packages__etl_packages_status_valid",
        ),
        sa.CheckConstraint(
            "complexity IN ('low', 'medium', 'high', 'critical')",
            name="ck_etl_packages__etl_packages_complexity_valid",
        ),
        sa.UniqueConstraint("project_id", "package_name", name="uq_etl_packages_project_name"),
    )
    op.create_index("ix_etl_packages_project_status", "etl_packages", ["project_id", "status"])
    op.create_index("ix_etl_packages_domain", "etl_packages", ["project_id", "domain"])
    
    # --- package_connection_points ---
    op.create_table(
        "package_connection_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("etl_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_tables", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("source_connections", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("target_tables", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("target_connections", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("declared_predecessors", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("package_id", name="uq_package_connection_points_package"),
    )
    
    # --- migration_connections ---
    op.create_table(
        "migration_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_name", sa.String(500), nullable=False),
        sa.Column("connection_type", sa.String(100), nullable=True),
        sa.Column("source_server", sa.String(500), nullable=True),
        sa.Column("source_database", sa.String(200), nullable=True),
        sa.Column("auth_method", sa.String(50), nullable=True),
        sa.Column("target_catalog", sa.String(200), nullable=True),
        sa.Column("target_schema", sa.String(200), nullable=True),
        sa.Column("used_by_packages", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("project_id", "connection_name", name="uq_migration_connections_project_name"),
    )
    op.create_index("ix_migration_connections_project", "migration_connections", ["project_id"])
    
    # --- migration_business_rules ---
    op.create_table(
        "migration_business_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("rule_name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source_implementation", sa.Text, nullable=True),
        sa.Column("target_implementation", sa.Text, nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("applies_to_domains", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("used_by_packages", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="discovered"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('discovered', 'confirmed', 'implemented', 'verified')",
            name="ck_migration_business_rules__migration_business_rules_status_valid",
        ),
        sa.UniqueConstraint("project_id", "rule_id", name="uq_migration_business_rules_project_rule"),
    )
    op.create_index("ix_migration_business_rules_project", "migration_business_rules", ["project_id"])
    op.create_index("ix_migration_business_rules_category", "migration_business_rules", ["project_id", "category"])
    
    # --- migration_resolved_decisions ---
    op.create_table(
        "migration_resolved_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision_type", sa.String(200), nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("resolution", sa.Text, nullable=False),
        sa.Column("resolution_rationale", sa.Text, nullable=True),
        sa.Column("scope", sa.String(20), nullable=False, server_default="project"),
        sa.Column("flow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("etl_packages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_by", sa.String(200), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("applied_to_packages", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.CheckConstraint(
            "scope IN ('project', 'flow', 'package')",
            name="ck_migration_resolved_decisions__migration_resolved_decisions_scope_valid",
        ),
    )
    op.create_index("ix_migration_resolved_decisions_project", "migration_resolved_decisions", ["project_id"])
    op.create_index("ix_migration_resolved_decisions_type", "migration_resolved_decisions", ["project_id", "decision_type"])


def downgrade() -> None:
    op.drop_table("migration_resolved_decisions")
    op.drop_table("migration_business_rules")
    op.drop_table("migration_connections")
    op.drop_table("package_connection_points")
    op.drop_table("etl_packages")
