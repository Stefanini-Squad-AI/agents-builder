"""Schemas for code generation module."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.modules.migration_workbench.analysis.strategy_classifier import (
    GenerationStrategy,
)


class ArtifactTier(str, Enum):
    """Type/tier of a generated artifact."""
    
    ORCHESTRATOR = "orchestrator"      # PySpark coordinator notebook
    SQL_MODULE = "sql_module"           # Standalone SQL sub-notebook
    PYSPARK_MODULE = "pyspark_module"   # Standalone PySpark notebook
    HYBRID_MODULE = "hybrid_module"     # Mixed SQL/Python notebook
    CONFIG = "config"                   # YAML/JSON config file
    DOCUMENTATION = "documentation"     # README, design doc
    TEST = "test"                       # Validation/test notebook


class GeneratedArtifact(BaseModel):
    """A single generated file."""
    
    name: str = Field(..., description="Filename without path")
    relative_path: str = Field(..., description="Path relative to package root")
    tier: ArtifactTier
    language: str = Field(..., description="python | sql | yaml | markdown")
    content: str = Field(..., description="Full file content")
    
    # Metadata
    line_count: int = 0
    depends_on: list[str] = Field(
        default_factory=list,
        description="Names of other artifacts this one calls/imports",
    )
    notes: list[str] = Field(default_factory=list)
    
    def model_post_init(self, _ctx: object) -> None:
        """Compute line_count after construction."""
        if not self.line_count and self.content:
            self.line_count = self.content.count("\n") + 1


class GenerationOptions(BaseModel):
    """User-provided generation options."""
    
    # Override the auto-detected strategy
    force_strategy: GenerationStrategy | None = Field(
        None,
        description="If set, override the classifier's recommendation",
    )
    
    # Target catalog/schema in Databricks
    target_catalog: str = Field("main", description="Unity Catalog name")
    target_schema: str = Field("default", description="Schema/database name")
    
    # Style preferences
    include_comments: bool = Field(True, description="Include explanatory comments")
    include_docstring_header: bool = Field(True, description="Add header docstring")
    include_validation_cells: bool = Field(
        True, description="Add row-count assertion cells"
    )
    
    # Performance hints
    enable_photon_hints: bool = Field(True, description="Add Photon optimization hints")
    use_delta_merge: bool = Field(True, description="Prefer MERGE over INSERT/UPDATE")


class GenerationRequest(BaseModel):
    """Request to generate artifacts for a package."""
    
    options: GenerationOptions = Field(default_factory=GenerationOptions)


class GenerationResult(BaseModel):
    """Complete result of a generation run for one package."""
    
    package_id: uuid.UUID
    package_name: str
    
    # What strategy was actually used (may differ from plan if forced)
    strategy: GenerationStrategy
    strategy_source: str = Field(
        "classifier",
        description="classifier | user_override",
    )
    
    # All generated files
    artifacts: list[GeneratedArtifact] = Field(default_factory=list)
    
    # Summary
    total_files: int = 0
    total_lines: int = 0
    
    # Status
    status: str = Field("success", description="success | partial | failed")
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def model_post_init(self, _ctx: object) -> None:
        """Compute aggregates."""
        if not self.total_files:
            self.total_files = len(self.artifacts)
        if not self.total_lines:
            self.total_lines = sum(a.line_count for a in self.artifacts)


class GenerationPreview(BaseModel):
    """Preview of what would be generated (without producing content)."""
    
    package_id: uuid.UUID
    package_name: str
    strategy: GenerationStrategy
    rationale: str
    planned_artifacts: list[dict] = Field(
        default_factory=list,
        description="List of {name, tier, purpose} dicts",
    )
