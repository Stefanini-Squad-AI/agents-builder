"""Add migration map tables for Phase 4.

Revision ID: 20260515_1400
Revises: 20260515_1300
Create Date: 2026-05-15

Adds tables for Migration Map functionality:
- migration_objects: Tables/files/APIs discovered across packages
- package_object_refs: Package ↔ Object relationships (read/write)
- package_flow_deps: Computed flow dependencies between packages
- package_clusters: Connected components in the flow graph
- package_cluster_members: Cluster membership
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260515_1400"
down_revision: str | None = "20260515_1300"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # migration_objects - Tables/Files/APIs discovered across packages
    # -------------------------------------------------------------------------
    op.create_table(
        "migration_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Object identity
        sa.Column("object_type", sa.String(20), nullable=False),
        sa.Column("object_name", sa.String(500), nullable=False),
        sa.Column("connection_ref", sa.String(200), nullable=True),
        # Location details
        sa.Column("schema_name", sa.String(200), nullable=True),
        sa.Column("database_name", sa.String(200), nullable=True),
        # Discovered metadata
        sa.Column("discovered_columns", postgresql.JSONB, nullable=True),
        # Statistics
        sa.Column("read_by_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("written_by_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Constraints
        sa.UniqueConstraint(
            "project_id", "object_type", "object_name",
            name="uq_migration_objects_identity"
        ),
        sa.CheckConstraint(
            "object_type IN ('table', 'file', 'api', 'queue', 'topic')",
            name="migration_objects_type_valid",
        ),
    )
    op.create_index(
        "ix_migration_objects_project",
        "migration_objects",
        ["project_id"],
    )
    op.create_index(
        "ix_migration_objects_name",
        "migration_objects",
        ["project_id", "object_name"],
    )

    # -------------------------------------------------------------------------
    # package_object_refs - Package ↔ Object relationships
    # -------------------------------------------------------------------------
    op.create_table(
        "package_object_refs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "package_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etl_packages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "object_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("migration_objects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Relationship type
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("access_type", sa.String(20), nullable=True),
        # Extracted details
        sa.Column("sql_fragment", sa.Text, nullable=True),
        sa.Column("columns_accessed", postgresql.ARRAY(sa.Text), nullable=True),
        # Source location
        sa.Column("task_name", sa.String(200), nullable=True),
        sa.Column("extraction_confidence", sa.Float, nullable=False, server_default="1.0"),
        # Constraints
        sa.UniqueConstraint(
            "package_id", "object_id", "direction",
            name="uq_package_object_refs_identity"
        ),
        sa.CheckConstraint(
            "direction IN ('read', 'write', 'lookup')",
            name="package_object_refs_direction_valid",
        ),
    )
    op.create_index(
        "ix_package_object_refs_package",
        "package_object_refs",
        ["package_id"],
    )
    op.create_index(
        "ix_package_object_refs_object",
        "package_object_refs",
        ["object_id"],
    )

    # -------------------------------------------------------------------------
    # package_flow_deps - Computed flow dependencies
    # -------------------------------------------------------------------------
    op.create_table(
        "package_flow_deps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "upstream_package_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etl_packages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "downstream_package_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etl_packages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "via_object_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("migration_objects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("relationship_type", sa.String(20), nullable=False),
        sa.Column("is_confirmed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("auto_detected", sa.Boolean, nullable=False, server_default="true"),
        # Constraints
        sa.UniqueConstraint(
            "upstream_package_id", "downstream_package_id", "via_object_id",
            name="uq_package_flow_deps_identity"
        ),
        sa.CheckConstraint(
            "relationship_type IN ('data_flow', 'control', 'inferred')",
            name="package_flow_deps_type_valid",
        ),
    )
    op.create_index(
        "ix_package_flow_deps_project",
        "package_flow_deps",
        ["project_id"],
    )
    op.create_index(
        "ix_package_flow_deps_upstream",
        "package_flow_deps",
        ["upstream_package_id"],
    )
    op.create_index(
        "ix_package_flow_deps_downstream",
        "package_flow_deps",
        ["downstream_package_id"],
    )

    # -------------------------------------------------------------------------
    # package_clusters - Connected components
    # -------------------------------------------------------------------------
    op.create_table(
        "package_clusters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Identity
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        # Statistics
        sa.Column("package_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("root_packages", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column("leaf_packages", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        # Migration planning
        sa.Column("suggested_wave", sa.Integer, nullable=True),
        sa.Column("migration_order", postgresql.JSONB, nullable=True),
        # Cycle detection
        sa.Column("has_cycles", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("cycle_packages", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_package_clusters_project",
        "package_clusters",
        ["project_id"],
    )

    # -------------------------------------------------------------------------
    # package_cluster_members - Cluster membership
    # -------------------------------------------------------------------------
    op.create_table(
        "package_cluster_members",
        sa.Column(
            "cluster_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("package_clusters.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "package_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etl_packages.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("position_in_cluster", sa.Integer, nullable=True),
        sa.Column("assigned_wave", sa.Integer, nullable=True),
    )
    op.create_index(
        "ix_package_cluster_members_package",
        "package_cluster_members",
        ["package_id"],
    )


def downgrade() -> None:
    op.drop_table("package_cluster_members")
    op.drop_table("package_clusters")
    op.drop_table("package_flow_deps")
    op.drop_table("package_object_refs")
    op.drop_table("migration_objects")
