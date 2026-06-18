"""Domain models for Migration Workbench.

Contains SQLAlchemy ORM models for:
- ETLPackage: Individual packages being migrated
- MigrationConnection: Shared connection definitions
- MigrationBusinessRule: Discovered business rules
- MigrationResolvedDecision: Decisions applied project-wide
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampsMixin, UuidPkMixin

if TYPE_CHECKING:
    from app.domain.projects import Project, ProjectArtifact


# -----------------------------------------------------------------------------
# Enums as CHECK constraints
# -----------------------------------------------------------------------------

PACKAGE_STATUS_VALUES = (
    "registered",
    "analyzing",
    "analyzed",
    "needs_feedback",
    "ready",
    "generating",
    "generated",
    "validating",
    "validated",
    "migrated",
    "verified",
)

COMPLEXITY_VALUES = ("low", "medium", "high", "critical")

DECISION_SCOPE_VALUES = ("project", "flow", "package")

RULE_STATUS_VALUES = ("discovered", "confirmed", "implemented", "verified")

# Reconciliation
RECONCILIATION_STATUS_VALUES = (
    "pending", "running", "passed", "failed", "warning", "error"
)
RECONCILIATION_CHECK_TYPE_VALUES = (
    "row_count", "checksum", "key_match", "aggregate", "sample_data"
)
RECONCILIATION_DATA_METHOD_VALUES = (
    "user_provided", "lakebridge", "databricks_api"
)

# Sign-off
SIGNOFF_TYPE_VALUES = (
    "static_analysis", "parallel_run", "cutover", "post_migration"
)
SIGNOFF_STATUS_VALUES = (
    "draft", "pending", "approved", "rejected", "cancelled"
)
CHECKLIST_ITEM_STATUS_VALUES = (
    "not_started", "in_progress", "passed", "failed", "skipped", "n/a"
)


def _values_csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# -----------------------------------------------------------------------------
# ETLPackage - Individual packages being migrated
# -----------------------------------------------------------------------------


class ETLPackage(UuidPkMixin, TimestampsMixin, Base):
    """An ETL package registered for migration.
    
    Represents a single SSIS package, Airflow DAG, or other ETL unit
    that will be analyzed and migrated to the target platform.
    """
    
    __tablename__ = "etl_packages"
    __table_args__ = (
        UniqueConstraint("project_id", "package_name", name="uq_etl_packages_project_name"),
        CheckConstraint(
            f"status IN ({_values_csv(PACKAGE_STATUS_VALUES)})",
            name="etl_packages_status_valid",
        ),
        CheckConstraint(
            f"complexity IN ({_values_csv(COMPLEXITY_VALUES)})",
            name="etl_packages_complexity_valid",
        ),
        Index("ix_etl_packages_project_status", "project_id", "status"),
        Index("ix_etl_packages_domain", "project_id", "domain"),
    )
    
    # Foreign keys
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Identity
    package_name: Mapped[str] = mapped_column(String(500), nullable=False)
    package_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_technology: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Card prefix for package-specific backlog (e.g., TTR, PCT, CORP)
    card_prefix: Mapped[str | None] = mapped_column(String(10), nullable=True)
    
    # Classification
    domain: Mapped[str | None] = mapped_column(String(200), nullable=True)
    complexity: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    estimated_effort: Mapped[str | None] = mapped_column(String(10), nullable=True)
    
    # Status tracking
    status: Mapped[str] = mapped_column(String(20), default="registered", nullable=False)
    analysis_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    analysis_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pending_feedback_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocking_feedback_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Analysis results
    analysis_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    blockers_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auto_resolved_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parse_warnings: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    
    # Timestamps
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    migrated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="etl_packages")
    artifact: Mapped["ProjectArtifact | None"] = relationship("ProjectArtifact")
    connection_points: Mapped["PackageConnectionPoints | None"] = relationship(
        "PackageConnectionPoints", back_populates="package", uselist=False
    )


# -----------------------------------------------------------------------------
# PackageConnectionPoints - Extracted data flows from a package
# -----------------------------------------------------------------------------


class PackageConnectionPoints(UuidPkMixin, Base):
    """Connection points extracted from an ETL package.
    
    Contains the sources, targets, and declared dependencies
    that define how this package relates to others.
    """
    
    __tablename__ = "package_connection_points"
    __table_args__ = (
        UniqueConstraint("package_id", name="uq_package_connection_points_package"),
    )
    
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etl_packages.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Source side
    source_tables: Mapped[dict] = mapped_column(JSONB, default=list, nullable=False)
    source_connections: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, nullable=False
    )
    
    # Target side
    target_tables: Mapped[dict] = mapped_column(JSONB, default=list, nullable=False)
    target_connections: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, nullable=False
    )
    
    # Dependencies
    declared_predecessors: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, nullable=False
    )
    
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    package: Mapped["ETLPackage"] = relationship(
        "ETLPackage", back_populates="connection_points"
    )


# -----------------------------------------------------------------------------
# MigrationConnection - Shared connection definitions
# -----------------------------------------------------------------------------


class MigrationConnection(UuidPkMixin, TimestampsMixin, Base):
    """A connection discovered and shared across packages.
    
    When multiple packages reference the same connection manager,
    we consolidate them here to enable project-wide mapping.
    """
    
    __tablename__ = "migration_connections"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "connection_name", 
            name="uq_migration_connections_project_name"
        ),
        Index("ix_migration_connections_project", "project_id"),
    )
    
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Source connection info
    connection_name: Mapped[str] = mapped_column(String(500), nullable=False)
    connection_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_server: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_database: Mapped[str | None] = mapped_column(String(200), nullable=True)
    auth_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Target mapping
    target_catalog: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_schema: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # Usage tracking
    used_by_packages: Mapped[list[str]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, nullable=False
    )
    
    # Resolution
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="migration_connections")


# -----------------------------------------------------------------------------
# MigrationBusinessRule - Discovered business rules
# -----------------------------------------------------------------------------


class MigrationBusinessRule(UuidPkMixin, TimestampsMixin, Base):
    """A business rule discovered during package analysis.
    
    Rules can be shared across packages within a domain or project.
    Once implemented, the target_implementation serves as a template.
    """
    
    __tablename__ = "migration_business_rules"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "rule_id", 
            name="uq_migration_business_rules_project_rule"
        ),
        CheckConstraint(
            f"status IN ({_values_csv(RULE_STATUS_VALUES)})",
            name="migration_business_rules_status_valid",
        ),
        Index("ix_migration_business_rules_project", "project_id"),
        Index("ix_migration_business_rules_category", "project_id", "category"),
    )
    
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Identity
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Implementation
    source_implementation: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_implementation: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Classification
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    applies_to_domains: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, nullable=False
    )
    used_by_packages: Mapped[list[str]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, nullable=False
    )
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="discovered", nullable=False)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="migration_business_rules")


# -----------------------------------------------------------------------------
# MigrationResolvedDecision - Project-wide decisions
# -----------------------------------------------------------------------------


class MigrationResolvedDecision(UuidPkMixin, Base):
    """A resolved decision that can be applied to future packages.
    
    When a human resolves a question (e.g., "How should we handle
    incremental loads?"), the resolution is stored here and
    automatically applied when similar questions arise.
    """
    
    __tablename__ = "migration_resolved_decisions"
    __table_args__ = (
        CheckConstraint(
            f"scope IN ({_values_csv(DECISION_SCOPE_VALUES)})",
            name="migration_resolved_decisions_scope_valid",
        ),
        Index("ix_migration_resolved_decisions_project", "project_id"),
        Index("ix_migration_resolved_decisions_type", "project_id", "decision_type"),
    )
    
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Decision identity
    decision_type: Mapped[str] = mapped_column(String(200), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Scope
    scope: Mapped[str] = mapped_column(String(20), default="project", nullable=False)
    flow_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    package_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etl_packages.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Resolution metadata
    resolved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    applied_to_packages: Mapped[list[str]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, nullable=False
    )
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="migration_resolved_decisions")
    package: Mapped["ETLPackage | None"] = relationship("ETLPackage")


# -----------------------------------------------------------------------------
# MapRelationship - Package relationships in Migration Map
# -----------------------------------------------------------------------------

RELATIONSHIP_TYPE_VALUES = ("data_dependency", "execution_dependency")
DIRECTION_VALUES = ("reads_from", "writes_to", "bidirectional")


class MapRelationship(UuidPkMixin, TimestampsMixin, Base):
    """Relationship between packages in the migration map.
    
    Supports two views:
    - Data dependencies: which packages share tables
    - Execution dependencies: which packages must complete first
    """
    
    __tablename__ = "map_relationships"
    __table_args__ = (
        CheckConstraint(
            f"relationship_type IN ({_values_csv(RELATIONSHIP_TYPE_VALUES)})",
            name="map_relationships_type_valid",
        ),
        CheckConstraint(
            f"direction IN ({_values_csv(DIRECTION_VALUES)})",
            name="map_relationships_direction_valid",
        ),
        Index("ix_map_relationships_project", "project_id"),
        Index("ix_map_relationships_source", "source_package_id"),
        Index("ix_map_relationships_target", "target_package_id"),
    )
    
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Relationship endpoints
    source_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etl_packages.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etl_packages.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Relationship type (data vs execution view)
    relationship_type: Mapped[str] = mapped_column(String(30), nullable=False)
    
    # For data dependencies
    shared_tables: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, nullable=False
    )
    direction: Mapped[str] = mapped_column(String(20), default="reads_from", nullable=False)
    
    # For execution dependencies
    dependency_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_blocking: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Discovery metadata
    discovered_by: Mapped[str] = mapped_column(String(20), default="auto", nullable=False)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project")
    source_package: Mapped["ETLPackage"] = relationship(
        "ETLPackage", foreign_keys=[source_package_id]
    )
    target_package: Mapped["ETLPackage"] = relationship(
        "ETLPackage", foreign_keys=[target_package_id]
    )


# -----------------------------------------------------------------------------
# MigrationDocSnapshot - Versioned documentation state
# -----------------------------------------------------------------------------

SNAPSHOT_TYPE_VALUES = ("full", "incremental")


class MigrationDocSnapshot(UuidPkMixin, Base):
    """Versioned snapshot of project documentation state.
    
    Auto-generated when significant events occur. Enables
    change tracking and gap analysis over time.
    """
    
    __tablename__ = "migration_doc_snapshots"
    __table_args__ = (
        CheckConstraint(
            f"snapshot_type IN ({_values_csv(SNAPSHOT_TYPE_VALUES)})",
            name="migration_doc_snapshots_type_valid",
        ),
        Index("ix_migration_doc_snapshots_project", "project_id"),
        Index("ix_migration_doc_snapshots_version", "project_id", "version"),
    )
    
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Versioning
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_type: Mapped[str] = mapped_column(String(20), default="full", nullable=False)
    
    # Rendered documentation (Markdown with Mermaid)
    project_summary_md: Mapped[str] = mapped_column(Text, nullable=False)
    migration_map_md: Mapped[str] = mapped_column(Text, nullable=False)
    packages_summary_md: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Raw state for diff computation
    state_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Trigger metadata
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_package_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etl_packages.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    project: Mapped["Project"] = relationship("Project")
    trigger_package: Mapped["ETLPackage | None"] = relationship("ETLPackage")


# -----------------------------------------------------------------------------
# DocumentationChange - Change tracking between snapshots
# -----------------------------------------------------------------------------

CHANGE_TYPE_VALUES = (
    "gap_filled",
    "new_blocker",
    "blocker_resolved",
    "progress",
    "wave_change",
    "dependency_added",
    "dependency_removed",
    "decision_made",
    "connection_mapped",
    "rule_implemented",
)

CHANGE_CATEGORY_VALUES = (
    "connections",
    "rules",
    "blockers",
    "progress",
    "waves",
    "dependencies",
    "decisions",
)

SIGNIFICANCE_VALUES = ("info", "notable", "critical")


class DocumentationChange(UuidPkMixin, Base):
    """Individual change detected between documentation versions.
    
    Tracks what changed, enabling audit trails and
    visibility into project evolution.
    """
    
    __tablename__ = "documentation_changes"
    __table_args__ = (
        CheckConstraint(
            f"change_type IN ({_values_csv(CHANGE_TYPE_VALUES)})",
            name="documentation_changes_type_valid",
        ),
        CheckConstraint(
            f"category IN ({_values_csv(CHANGE_CATEGORY_VALUES)})",
            name="documentation_changes_category_valid",
        ),
        CheckConstraint(
            f"significance IN ({_values_csv(SIGNIFICANCE_VALUES)})",
            name="documentation_changes_significance_valid",
        ),
        Index("ix_documentation_changes_project", "project_id"),
        Index("ix_documentation_changes_snapshots", "from_snapshot_id", "to_snapshot_id"),
    )
    
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Snapshot references
    from_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("migration_doc_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("migration_doc_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Change details
    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    package_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etl_packages.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    description: Mapped[str] = mapped_column(Text, nullable=False)
    previous_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    significance: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    project: Mapped["Project"] = relationship("Project")
    from_snapshot: Mapped["MigrationDocSnapshot"] = relationship(
        "MigrationDocSnapshot", foreign_keys=[from_snapshot_id]
    )
    to_snapshot: Mapped["MigrationDocSnapshot"] = relationship(
        "MigrationDocSnapshot", foreign_keys=[to_snapshot_id]
    )
    package: Mapped["ETLPackage | None"] = relationship("ETLPackage")


# =============================================================================
# Phase 4: Migration Map Models
# =============================================================================

# -----------------------------------------------------------------------------
# MigrationObject - Tables/Files/APIs discovered across packages
# -----------------------------------------------------------------------------

OBJECT_TYPE_VALUES = ("table", "file", "api", "queue", "topic")


class MigrationObject(UuidPkMixin, Base):
    """A data object (table, file, API, etc.) discovered across packages.
    
    When multiple packages reference the same object, we consolidate
    them here to enable relationship detection and lineage tracking.
    """
    
    __tablename__ = "migration_objects"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "object_type", "object_name",
            name="uq_migration_objects_identity"
        ),
        CheckConstraint(
            f"object_type IN ({_values_csv(OBJECT_TYPE_VALUES)})",
            name="migration_objects_type_valid",
        ),
        Index("ix_migration_objects_project", "project_id"),
        Index("ix_migration_objects_name", "project_id", "object_name"),
    )
    
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Object identity
    object_type: Mapped[str] = mapped_column(String(20), nullable=False)
    object_name: Mapped[str] = mapped_column(String(500), nullable=False)
    connection_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # Location details
    schema_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    database_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # Discovered metadata (accumulated from multiple packages)
    discovered_columns: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    
    # Statistics (updated as packages are analyzed)
    read_by_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    written_by_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    project: Mapped["Project"] = relationship("Project")
    package_refs: Mapped[list["PackageObjectRef"]] = relationship(
        "PackageObjectRef", back_populates="object", cascade="all, delete-orphan"
    )


# -----------------------------------------------------------------------------
# PackageObjectRef - Package ↔ Object relationships
# -----------------------------------------------------------------------------

OBJECT_DIRECTION_VALUES = ("read", "write", "lookup")
ACCESS_TYPE_VALUES = ("full_load", "incremental", "merge", "delete_insert", "upsert", "append")


class PackageObjectRef(UuidPkMixin, Base):
    """Reference from a package to a data object.
    
    Tracks whether a package reads or writes an object,
    enabling flow relationship detection.
    """
    
    __tablename__ = "package_object_refs"
    __table_args__ = (
        UniqueConstraint(
            "package_id", "object_id", "direction",
            name="uq_package_object_refs_identity"
        ),
        CheckConstraint(
            f"direction IN ({_values_csv(OBJECT_DIRECTION_VALUES)})",
            name="package_object_refs_direction_valid",
        ),
        Index("ix_package_object_refs_package", "package_id"),
        Index("ix_package_object_refs_object", "object_id"),
    )
    
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etl_packages.id", ondelete="CASCADE"),
        nullable=False,
    )
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("migration_objects.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Relationship type
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    access_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    # Extracted details
    sql_fragment: Mapped[str | None] = mapped_column(Text, nullable=True)
    columns_accessed: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    
    # Source location in package
    task_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    extraction_confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)
    
    # Relationships
    package: Mapped["ETLPackage"] = relationship("ETLPackage")
    object: Mapped["MigrationObject"] = relationship(
        "MigrationObject", back_populates="package_refs"
    )


# -----------------------------------------------------------------------------
# PackageFlowDep - Computed flow dependencies (Package A → Package B)
# -----------------------------------------------------------------------------

FLOW_RELATIONSHIP_TYPE_VALUES = ("data_flow", "control", "inferred")


class PackageFlowDep(UuidPkMixin, Base):
    """Computed data flow dependency between packages.
    
    Created when Package A writes an object that Package B reads.
    Enables migration order computation and wave assignment.
    """
    
    __tablename__ = "package_flow_deps"
    __table_args__ = (
        UniqueConstraint(
            "upstream_package_id", "downstream_package_id", "via_object_id",
            name="uq_package_flow_deps_identity"
        ),
        CheckConstraint(
            f"relationship_type IN ({_values_csv(FLOW_RELATIONSHIP_TYPE_VALUES)})",
            name="package_flow_deps_type_valid",
        ),
        Index("ix_package_flow_deps_project", "project_id"),
        Index("ix_package_flow_deps_upstream", "upstream_package_id"),
        Index("ix_package_flow_deps_downstream", "downstream_package_id"),
    )
    
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Dependency endpoints
    upstream_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etl_packages.id", ondelete="CASCADE"),
        nullable=False,
    )
    downstream_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etl_packages.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # What connects them
    via_object_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("migration_objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Confirmation status
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_detected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project")
    upstream_package: Mapped["ETLPackage"] = relationship(
        "ETLPackage", foreign_keys=[upstream_package_id]
    )
    downstream_package: Mapped["ETLPackage"] = relationship(
        "ETLPackage", foreign_keys=[downstream_package_id]
    )
    via_object: Mapped["MigrationObject | None"] = relationship("MigrationObject")


# -----------------------------------------------------------------------------
# PackageCluster - Connected components in the flow graph
# -----------------------------------------------------------------------------


class PackageCluster(UuidPkMixin, TimestampsMixin, Base):
    """A cluster of related packages (connected component).
    
    Packages in the same cluster share data dependencies and
    should typically migrate together in the same wave.
    """
    
    __tablename__ = "package_clusters"
    __table_args__ = (
        Index("ix_package_clusters_project", "project_id"),
    )
    
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Cluster identity
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Computed statistics
    package_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    root_packages: Mapped[list[str] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    leaf_packages: Mapped[list[str] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    
    # Migration planning
    suggested_wave: Mapped[int | None] = mapped_column(Integer, nullable=True)
    migration_order: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    
    # Cycle detection
    has_cycles: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cycle_packages: Mapped[list[str] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project")
    members: Mapped[list["PackageClusterMember"]] = relationship(
        "PackageClusterMember", back_populates="cluster", cascade="all, delete-orphan"
    )


# -----------------------------------------------------------------------------
# PackageClusterMember - Membership in clusters
# -----------------------------------------------------------------------------


class PackageClusterMember(Base):
    """Package membership in a cluster with position info."""
    
    __tablename__ = "package_cluster_members"
    __table_args__ = (
        Index("ix_package_cluster_members_package", "package_id"),
    )
    
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("package_clusters.id", ondelete="CASCADE"),
        primary_key=True,
    )
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etl_packages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    
    # Position in topological order
    position_in_cluster: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Assigned wave within cluster
    assigned_wave: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Relationships
    cluster: Mapped["PackageCluster"] = relationship(
        "PackageCluster", back_populates="members"
    )
    package: Mapped["ETLPackage"] = relationship("ETLPackage")


# -----------------------------------------------------------------------------
# ReconciliationRun - One reconciliation execution for a package
# -----------------------------------------------------------------------------


class ReconciliationRun(UuidPkMixin, TimestampsMixin, Base):
    """Records one reconciliation execution comparing source vs target data.

    Phase A (no Lakebridge): target counts queried via Databricks Statement
    Execution API; source counts entered manually by the user.

    Phase B (Lakebridge): both sides queried automatically via the Unity
    Catalog Connection configured in the Databricks workspace.

    Auto-populates signoff checklist items pr_02 (row counts) and pr_03
    (checksums) when the run completes.
    """

    __tablename__ = "reconciliation_runs"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_values_csv(RECONCILIATION_STATUS_VALUES)})",
            name="reconciliation_runs_status_valid",
        ),
        Index("ix_reconciliation_runs_package", "package_id"),
        Index("ix_reconciliation_runs_project_status", "project_id", "status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("etl_packages.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Quick-access aggregates (populated on completion for signoff auto-populate)
    source_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # How the run was triggered and configured
    triggered_by: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="manual"
    )
    # Databricks SQL Warehouse used for Phase A target-side auto-queries
    sql_warehouse_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Unity Catalog Connection used when triggered via Lakebridge (Phase B)
    uc_connection_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Full result payload (all check types and per-table detail)
    summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    package: Mapped["ETLPackage"] = relationship("ETLPackage")
    check_results: Mapped[list["ReconciliationCheckResult"]] = relationship(
        "ReconciliationCheckResult",
        back_populates="run",
        cascade="all, delete-orphan",
    )


# -----------------------------------------------------------------------------
# ReconciliationCheckResult - One check within a reconciliation run
# -----------------------------------------------------------------------------


class ReconciliationCheckResult(UuidPkMixin, Base):
    """Per-check-type result within a reconciliation run.

    source_data_method and target_data_method record HOW each side's data
    was obtained so the sign-off audit trail is unambiguous:
      user_provided  — the user entered the value manually
      databricks_api — queried automatically via Databricks Statement Execution API
      lakebridge     — queried automatically via Lakebridge reconcile command
    """

    __tablename__ = "reconciliation_check_results"
    __table_args__ = (
        CheckConstraint(
            f"check_type IN ({_values_csv(RECONCILIATION_CHECK_TYPE_VALUES)})",
            name="reconciliation_check_results_type_valid",
        ),
        CheckConstraint(
            f"source_data_method IN ({_values_csv(RECONCILIATION_DATA_METHOD_VALUES)})",
            name="reconciliation_check_results_src_method_valid",
        ),
        CheckConstraint(
            f"target_data_method IN ({_values_csv(RECONCILIATION_DATA_METHOD_VALUES)})",
            name="reconciliation_check_results_tgt_method_valid",
        ),
        Index("ix_reconciliation_check_results_run", "run_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    check_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_table: Mapped[str] = mapped_column(String(500), nullable=False)
    target_table: Mapped[str] = mapped_column(String(500), nullable=False)

    # Values stored as TEXT — covers counts (ints), hashes, JSON snippets
    source_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    match: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    variance: Mapped[float | None] = mapped_column(nullable=True)
    variance_threshold: Mapped[float | None] = mapped_column(nullable=True)

    # Audit: how was each side's data obtained?
    source_data_method: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="user_provided"
    )
    target_data_method: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="databricks_api"
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    run: Mapped["ReconciliationRun"] = relationship(
        "ReconciliationRun", back_populates="check_results"
    )


# -----------------------------------------------------------------------------
# SignoffRequest - Approval gate for a migration milestone
# -----------------------------------------------------------------------------


class SignoffRequest(UuidPkMixin, TimestampsMixin, Base):
    """A formal sign-off request for a migration milestone.

    Replaces the in-memory dict in SignoffService (B4a). Each request
    carries a set of checklist items (SignoffChecklistItem) that must all
    pass before the request can be approved.

    approved_by is a free-text name string — real user binding is deferred
    until multi-user auth is implemented (SPEC §16 non-goal for MVP).
    approved_at is always set server-side, never trusted from the client.

    HITL risk levels:
      static_analysis  → N3 (named approval required)
      parallel_run     → N3
      cutover          → N4 (business owner sign-off)
      post_migration   → N4
    """

    __tablename__ = "signoff_requests"
    __table_args__ = (
        CheckConstraint(
            f"signoff_type IN ({_values_csv(SIGNOFF_TYPE_VALUES)})",
            name="signoff_requests_type_valid",
        ),
        CheckConstraint(
            f"status IN ({_values_csv(SIGNOFF_STATUS_VALUES)})",
            name="signoff_requests_status_valid",
        ),
        Index("ix_signoff_requests_project_status", "project_id", "status"),
        Index("ix_signoff_requests_package_type", "project_id", "signoff_type"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    signoff_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="draft"
    )

    # Scope — which packages or wave this sign-off covers
    package_ids: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}"
    )
    wave_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Description
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Requestor (free text — no FK to users in MVP)
    requested_by: Mapped[str] = mapped_column(String(200), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Approver — set server-side on approve, never from client
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Append-only comment thread (list of strings stored as JSONB)
    comments_json: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    # Relationships
    checklist_items: Mapped[list["SignoffChecklistItem"]] = relationship(
        "SignoffChecklistItem",
        back_populates="signoff",
        cascade="all, delete-orphan",
        order_by="SignoffChecklistItem.item_key",
    )


# -----------------------------------------------------------------------------
# SignoffChecklistItem - Individual checklist gate within a sign-off
# -----------------------------------------------------------------------------


class SignoffChecklistItem(UuidPkMixin, Base):
    """One checklist item within a sign-off request.

    auto_populated marks items that were set by the system (e.g. pr_02
    row-count match and pr_03 checksum match auto-filled from a
    ReconciliationRun). auto_populated_from records the run ID so the
    audit trail shows exactly which reconciliation result drove the item.

    evidence is a free-text field where the approver links their proof:
    a Confluence URL, a screenshot attachment path, a SQL query result, etc.
    """

    __tablename__ = "signoff_checklist_items"
    __table_args__ = (
        UniqueConstraint(
            "signoff_id", "item_key",
            name="uq_signoff_checklist_items_signoff_key",
        ),
        CheckConstraint(
            f"status IN ({_values_csv(CHECKLIST_ITEM_STATUS_VALUES)})",
            name="signoff_checklist_items_status_valid",
        ),
        Index("ix_signoff_checklist_items_signoff", "signoff_id"),
    )

    signoff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("signoff_requests.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Stable identifier within the checklist (e.g. 'pr_01', 'sa_02', 'co_03')
    item_key: Mapped[str] = mapped_column(String(50), nullable=False)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="general"
    )
    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="not_started"
    )

    # Evidence and notes provided by the human completing the item
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    completed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Auto-population tracking (for pr_02 and pr_03 from ReconciliationRun)
    auto_populated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # Stores the reconciliation_run.id (as string) that set this item
    auto_populated_from: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )

    # Relationship
    signoff: Mapped["SignoffRequest"] = relationship(
        "SignoffRequest", back_populates="checklist_items"
    )


# -----------------------------------------------------------------------------
# ProjectMCPConfig - Per-project MCP server configuration
# -----------------------------------------------------------------------------


class ProjectMCPConfig(UuidPkMixin, TimestampsMixin, Base):
    """Per-project MCP server configuration.

    Stores the configuration for an MCP server that has been enabled
    for a specific project. Each project can have multiple MCP configs,
    but only one per mcp_key.

    Secrets are stored in env_vars_encrypted using Fernet encryption.
    The encryption key is project-scoped (derived from project_id + master key).

    Phase 2: env_vars_encrypted stored as plain JSON (no encryption yet).
    Phase 3: Fernet encryption with project-scoped keys.
    """

    __tablename__ = "project_mcp_configs"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "mcp_key",
            name="uq_project_mcp_configs_project_key",
        ),
        Index("ix_project_mcp_configs_project", "project_id"),
        Index("ix_project_mcp_configs_enabled", "project_id", "enabled"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    # MCP catalog key (e.g., "github", "databricks", "jira-atlassian")
    mcp_key: Mapped[str] = mapped_column(String(100), nullable=False)

    # Environment variables (secrets) — stored encrypted in Phase 3
    # For Phase 2, this is plain JSON: {"GITHUB_TOKEN": "xxx", ...}
    env_vars_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Non-secret configuration fields as JSONB
    # e.g., {"owner": "myorg", "repo": "myrepo"}
    config_fields: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # Status
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    # Validation tracking
    validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="mcp_configs")
