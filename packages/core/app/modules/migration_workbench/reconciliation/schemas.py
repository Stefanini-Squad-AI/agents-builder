"""Schemas for reconciliation module.

Reconciliation compares source and target data post-migration to ensure
accuracy and completeness.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ReconciliationType(str, Enum):
    """Type of reconciliation check."""
    
    ROW_COUNT = "row_count"           # Compare row counts between source/target
    CHECKSUM = "checksum"             # Hash-based comparison
    KEY_MATCH = "key_match"           # Match primary keys exist in both
    AGGREGATE = "aggregate"           # SUM/COUNT/AVG on numeric columns
    SAMPLE_DATA = "sample_data"       # Compare sample rows


class ReconciliationStatus(str, Enum):
    """Status of a reconciliation run."""
    
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"      # Passed with minor discrepancies
    ERROR = "error"          # Could not complete check


class ReconciliationMetric(BaseModel):
    """A single metric result from reconciliation."""
    
    metric_name: str = Field(..., description="e.g., 'row_count', 'checksum_md5'")
    source_value: str | int | float | None = None
    target_value: str | int | float | None = None
    match: bool = False
    variance: float | None = Field(None, description="Percentage variance if numeric")
    variance_threshold: float | None = Field(
        None, description="Acceptable variance percentage"
    )
    notes: str | None = None


class TableReconciliation(BaseModel):
    """Reconciliation result for one table."""
    
    source_table: str
    target_table: str
    status: ReconciliationStatus
    metrics: list[ReconciliationMetric] = Field(default_factory=list)
    
    # Computed
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0
    
    error_message: str | None = None
    
    def model_post_init(self, _ctx: object) -> None:
        if not self.passed_count and not self.failed_count:
            self.passed_count = sum(1 for m in self.metrics if m.match)
            self.failed_count = sum(1 for m in self.metrics if not m.match)


class ReconciliationConfig(BaseModel):
    """Configuration for a reconciliation run."""
    
    # Which check types to perform
    check_types: list[ReconciliationType] = Field(
        default_factory=lambda: [ReconciliationType.ROW_COUNT]
    )
    
    # Thresholds
    row_count_variance_threshold: float = Field(
        0.0, description="Acceptable row count variance (0.0 = exact match)"
    )
    checksum_sample_size: int = Field(
        10000, description="Max rows to include in checksum"
    )
    
    # Table mappings (source → target)
    # If empty, infer from package analysis
    table_mappings: dict[str, str] = Field(
        default_factory=dict,
        description="Explicit source→target table name mappings",
    )
    
    # Connection info (references to connection names in project)
    source_connection: str | None = None
    target_connection: str | None = None


class ReconciliationRequest(BaseModel):
    """Request to run reconciliation for a package."""
    
    config: ReconciliationConfig = Field(default_factory=ReconciliationConfig)


class ReconciliationRunResult(BaseModel):
    """Result of a complete reconciliation run."""
    
    id: uuid.UUID
    package_id: uuid.UUID
    package_name: str
    
    status: ReconciliationStatus
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    
    # Per-table results
    tables: list[TableReconciliation] = Field(default_factory=list)
    
    # Summary
    total_tables: int = 0
    passed_tables: int = 0
    failed_tables: int = 0
    warning_tables: int = 0
    
    # Config used
    config: ReconciliationConfig | None = None
    
    # Errors
    error_message: str | None = None
    
    def model_post_init(self, _ctx: object) -> None:
        if not self.total_tables:
            self.total_tables = len(self.tables)
        if not self.passed_tables:
            self.passed_tables = sum(
                1 for t in self.tables if t.status == ReconciliationStatus.PASSED
            )
        if not self.failed_tables:
            self.failed_tables = sum(
                1 for t in self.tables if t.status == ReconciliationStatus.FAILED
            )
        if not self.warning_tables:
            self.warning_tables = sum(
                1 for t in self.tables if t.status == ReconciliationStatus.WARNING
            )
        if self.started_at and self.completed_at and not self.duration_seconds:
            self.duration_seconds = (
                self.completed_at - self.started_at
            ).total_seconds()


class ReconciliationRunView(BaseModel):
    """Summary view of a reconciliation run for listings."""
    
    id: uuid.UUID
    package_id: uuid.UUID
    package_name: str
    status: ReconciliationStatus
    started_at: datetime
    completed_at: datetime | None = None
    
    total_tables: int = 0
    passed_tables: int = 0
    failed_tables: int = 0
    
    model_config = {"from_attributes": True}
