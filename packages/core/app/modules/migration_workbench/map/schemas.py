"""Pydantic schemas for Migration Map module."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class ObjectType(str, Enum):
    """Type of data object."""
    
    TABLE = "table"
    FILE = "file"
    API = "api"
    QUEUE = "queue"
    TOPIC = "topic"


class ObjectDirection(str, Enum):
    """Direction of object access."""
    
    READ = "read"
    WRITE = "write"
    LOOKUP = "lookup"


class AccessType(str, Enum):
    """Type of data access pattern."""
    
    FULL_LOAD = "full_load"
    INCREMENTAL = "incremental"
    MERGE = "merge"
    DELETE_INSERT = "delete_insert"
    UPSERT = "upsert"
    APPEND = "append"


class FlowRelationshipType(str, Enum):
    """Type of flow relationship."""
    
    DATA_FLOW = "data_flow"
    CONTROL = "control"
    INFERRED = "inferred"


# -----------------------------------------------------------------------------
# Object Schemas
# -----------------------------------------------------------------------------


class ObjectCreate(BaseModel):
    """Create a new migration object."""
    
    object_type: ObjectType
    object_name: str
    connection_ref: str | None = None
    schema_name: str | None = None
    database_name: str | None = None
    discovered_columns: list[dict] | None = None


class ObjectView(BaseModel):
    """View of a migration object."""
    
    id: uuid.UUID
    project_id: uuid.UUID
    object_type: ObjectType
    object_name: str
    connection_ref: str | None
    schema_name: str | None
    database_name: str | None
    discovered_columns: list[dict] | None
    read_by_count: int
    written_by_count: int
    first_seen_at: datetime
    
    class Config:
        from_attributes = True


class ObjectWithPackages(ObjectView):
    """Object with list of packages that reference it."""
    
    reading_packages: list[str] = Field(default_factory=list)
    writing_packages: list[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Package Object Reference Schemas
# -----------------------------------------------------------------------------


class PackageObjectRefCreate(BaseModel):
    """Create a reference from package to object."""
    
    object_type: ObjectType
    object_name: str
    direction: ObjectDirection
    connection_ref: str | None = None
    schema_name: str | None = None
    database_name: str | None = None
    access_type: AccessType | None = None
    sql_fragment: str | None = None
    columns_accessed: list[str] | None = None
    task_name: str | None = None
    extraction_confidence: float = 1.0


class PackageObjectRefView(BaseModel):
    """View of a package-object reference."""
    
    id: uuid.UUID
    package_id: uuid.UUID
    object_id: uuid.UUID
    direction: ObjectDirection
    access_type: AccessType | None
    sql_fragment: str | None
    columns_accessed: list[str] | None
    task_name: str | None
    extraction_confidence: float
    
    # Denormalized for convenience
    object_name: str | None = None
    object_type: ObjectType | None = None
    
    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Flow Dependency Schemas
# -----------------------------------------------------------------------------


class FlowDepCreate(BaseModel):
    """Create a flow dependency."""
    
    upstream_package_id: uuid.UUID
    downstream_package_id: uuid.UUID
    via_object_id: uuid.UUID | None = None
    relationship_type: FlowRelationshipType = FlowRelationshipType.DATA_FLOW
    is_confirmed: bool = False
    auto_detected: bool = True


class FlowDepView(BaseModel):
    """View of a flow dependency."""
    
    id: uuid.UUID
    project_id: uuid.UUID
    upstream_package_id: uuid.UUID
    downstream_package_id: uuid.UUID
    via_object_id: uuid.UUID | None
    relationship_type: FlowRelationshipType
    is_confirmed: bool
    auto_detected: bool
    
    # Denormalized
    upstream_package_name: str | None = None
    downstream_package_name: str | None = None
    via_object_name: str | None = None
    
    class Config:
        from_attributes = True


class FlowDepConfirm(BaseModel):
    """Confirm or reject a flow dependency."""
    
    is_confirmed: bool


# -----------------------------------------------------------------------------
# Cluster Schemas
# -----------------------------------------------------------------------------


class ClusterView(BaseModel):
    """View of a package cluster."""
    
    id: uuid.UUID
    project_id: uuid.UUID
    name: str | None
    description: str | None
    package_count: int
    root_packages: list[uuid.UUID] | None
    leaf_packages: list[uuid.UUID] | None
    suggested_wave: int | None
    migration_order: list[dict] | None
    has_cycles: bool
    cycle_packages: list[uuid.UUID] | None
    
    class Config:
        from_attributes = True


class ClusterMemberView(BaseModel):
    """View of a cluster member."""
    
    cluster_id: uuid.UUID
    package_id: uuid.UUID
    package_name: str
    position_in_cluster: int | None
    assigned_wave: int | None


class ClusterWithMembers(ClusterView):
    """Cluster with full member details."""
    
    members: list[ClusterMemberView] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Map Visualization Schemas (for React Flow)
# -----------------------------------------------------------------------------


class MapNode(BaseModel):
    """Node in the map visualization."""
    
    id: str
    type: str  # 'package' | 'table' | 'file'
    data: dict  # Status, wave, feedback count, etc.
    position: dict | None = None  # Let frontend auto-layout if None


class MapEdge(BaseModel):
    """Edge in the map visualization."""
    
    id: str
    source: str  # Node ID
    target: str  # Node ID
    label: str | None = None  # Object name connecting them
    animated: bool = False  # True for in-progress flows
    style: dict | None = None


class MapStats(BaseModel):
    """Statistics about the migration map."""
    
    total_packages: int
    analyzed_packages: int
    total_objects: int
    total_dependencies: int
    cluster_count: int
    orphan_count: int
    cycles_detected: int
    suggested_waves: int


class MapVisualization(BaseModel):
    """Full map data for visualization."""
    
    nodes: list[MapNode]
    edges: list[MapEdge]
    clusters: list[ClusterView]
    orphan_packages: list[str]
    stats: MapStats


# -----------------------------------------------------------------------------
# API Response Schemas
# -----------------------------------------------------------------------------


class ObjectsListResponse(BaseModel):
    """Response for listing objects."""
    
    objects: list[ObjectView]
    total: int


class FlowDepsListResponse(BaseModel):
    """Response for listing flow dependencies."""
    
    dependencies: list[FlowDepView]
    total: int


class ClustersListResponse(BaseModel):
    """Response for listing clusters."""
    
    clusters: list[ClusterView]
    total: int


class MapRefreshResult(BaseModel):
    """Result of refreshing the migration map."""
    
    objects_created: int
    objects_updated: int
    dependencies_created: int
    dependencies_removed: int
    clusters_created: int
    clusters_merged: int
    cycles_detected: int
    duration_ms: float


class WaveSuggestion(BaseModel):
    """Suggested wave assignment."""
    
    package_id: uuid.UUID
    package_name: str
    current_wave: int | None
    suggested_wave: int
    reason: str


class WaveSuggestionsResult(BaseModel):
    """Result of wave suggestion algorithm."""
    
    suggestions: list[WaveSuggestion]
    total_waves: int
    unassignable: list[str]  # Packages in cycles
