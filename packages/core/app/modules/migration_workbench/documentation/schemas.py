"""Pydantic schemas for Documentation service."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class GeneratedDocs(BaseModel):
    """Generated documentation content."""
    
    project_summary_md: str = Field(..., description="Project overview markdown")
    migration_map_md: str = Field(..., description="Migration map with Mermaid diagrams")
    packages_summary_md: str = Field(..., description="All packages status table")
    
    # Raw state for storage
    state_json: dict = Field(default_factory=dict)


class DocSnapshotView(BaseModel):
    """Documentation snapshot response."""
    
    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    snapshot_type: str
    
    project_summary_md: str
    migration_map_md: str
    packages_summary_md: str
    
    trigger_event: str
    trigger_package_id: uuid.UUID | None = None
    generated_at: datetime
    
    model_config = {"from_attributes": True}


class ChangeView(BaseModel):
    """Documentation change response."""
    
    id: uuid.UUID
    change_type: str
    category: str
    package_id: uuid.UUID | None = None
    
    description: str
    previous_value: str | None = None
    new_value: str | None = None
    
    significance: str
    detected_at: datetime
    
    model_config = {"from_attributes": True}


class ChangesSummary(BaseModel):
    """Summary of changes between versions."""
    
    from_version: int
    to_version: int
    total_changes: int
    
    gaps_filled: int = 0
    new_blockers: int = 0
    blockers_resolved: int = 0
    progress_updates: int = 0
    
    critical_changes: list[ChangeView] = []
    notable_changes: list[ChangeView] = []
    info_changes: list[ChangeView] = []


class PackageState(BaseModel):
    """State of a single package for diffing."""
    
    id: uuid.UUID
    name: str
    status: str
    domain: str | None = None
    complexity: str
    card_prefix: str | None = None
    
    # Progress metrics
    total_cards: int = 0
    completed_cards: int = 0
    progress_percent: float = 0.0
    
    # Blockers
    blockers: list[dict] = []
    
    model_config = {"from_attributes": True}


class ConnectionState(BaseModel):
    """State of a connection for diffing."""
    
    id: uuid.UUID
    name: str
    resolved: bool = False
    target_catalog: str | None = None
    target_schema: str | None = None
    used_by_count: int = 0


class RuleState(BaseModel):
    """State of a business rule for diffing."""
    
    id: uuid.UUID
    rule_id: str
    name: str
    status: str
    has_implementation: bool = False


class ProjectState(BaseModel):
    """Complete project state for snapshot storage and diffing."""
    
    project_id: uuid.UUID
    source_technology: str | None = None
    target_technology: str | None = None
    
    packages: dict[str, PackageState] = {}
    connections: dict[str, ConnectionState] = {}
    rules: dict[str, RuleState] = {}
    decisions_count: int = 0
    
    # Aggregate metrics
    total_packages: int = 0
    analyzed_packages: int = 0
    migrated_packages: int = 0
    total_blockers: int = 0
    
    # Wave assignments
    waves: dict[int, list[str]] = {}  # wave_number -> [package_ids]
