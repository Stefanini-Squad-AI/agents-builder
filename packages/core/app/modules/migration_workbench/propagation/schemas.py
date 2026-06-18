"""Propagation schemas for knowledge transfer between packages."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PropagationScope(str, Enum):
    """Scope of propagation."""
    
    PROJECT = "project"      # Apply to all packages in project
    CLUSTER = "cluster"      # Apply to packages in same cluster
    DOMAIN = "domain"        # Apply to packages with same domain
    SIMILAR = "similar"      # Apply to similar packages (based on analysis)


class PropagationResult(BaseModel):
    """Result of a propagation operation."""
    
    source_decision_id: uuid.UUID
    decision_type: str
    packages_affected: int
    packages_already_resolved: int
    affected_package_ids: list[uuid.UUID] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    propagated_at: datetime


class PropagationRequest(BaseModel):
    """Request to propagate a decision."""
    
    decision_id: uuid.UUID
    scope: PropagationScope = PropagationScope.PROJECT
    cluster_id: uuid.UUID | None = None
    domain: str | None = None
    dry_run: bool = False


class PropagationPreview(BaseModel):
    """Preview of what a propagation would affect."""
    
    decision_id: uuid.UUID
    decision_type: str
    question: str
    resolution: str
    scope: PropagationScope
    would_affect_count: int
    already_resolved_count: int
    affected_packages: list[dict[str, Any]] = Field(default_factory=list)


class BatchWaveAssignment(BaseModel):
    """Request to assign waves to multiple packages."""
    
    assignments: list[dict[str, Any]]  # [{"package_id": UUID, "wave": int}]


class BatchWaveResult(BaseModel):
    """Result of batch wave assignment."""
    
    successful: int
    failed: int
    errors: list[str] = Field(default_factory=list)
    assigned_packages: list[uuid.UUID] = Field(default_factory=list)


class PropagationHistoryItem(BaseModel):
    """Historical record of a propagation."""
    
    id: uuid.UUID
    source_decision_id: uuid.UUID
    decision_type: str
    question: str
    resolution: str
    scope: PropagationScope
    packages_affected: int
    propagated_by: str | None
    propagated_at: datetime
    
    class Config:
        from_attributes = True
