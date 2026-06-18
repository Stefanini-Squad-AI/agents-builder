"""Generation service: orchestrates package -> notebook generation."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.migration_workbench.analysis.parsers.ssis import SSISParser
from app.modules.migration_workbench.analysis.schemas import SSISPackage
from app.modules.migration_workbench.analysis.strategy_classifier import (
    StrategyClassifier,
)
from app.modules.migration_workbench.generation.generators.databricks import (
    DatabricksGenerator,
)
from app.modules.migration_workbench.generation.schemas import (
    GenerationOptions,
    GenerationPreview,
    GenerationResult,
)
from app.modules.migration_workbench.models import ETLPackage


class GenerationService:
    """High-level generation API used by the router."""
    
    def __init__(self, session: Session) -> None:
        self.session = session
        self.generator = DatabricksGenerator()
    
    # ------------------------------------------------------------------
    
    def get_package_or_raise(self, package_id: uuid.UUID) -> ETLPackage:
        package = self.session.get(ETLPackage, package_id)
        if not package:
            raise ValueError(f"Package {package_id} not found")
        return package
    
    def load_parsed_package(self, package: ETLPackage) -> SSISPackage:
        """Reparse the package file (cached parse not yet persisted).
        
        Note: We re-parse on demand to avoid a heavy JSONB column. Future
        optimization: cache the parsed structure in package.analysis_json.
        """
        if not package.file_path:
            raise ValueError(
                f"Package '{package.package_name}' has no file_path; cannot generate"
            )
        
        if (package.source_technology or "ssis").lower() != "ssis":
            raise ValueError(
                f"Unsupported source technology: {package.source_technology}"
            )
        
        with open(package.file_path, encoding="utf-8") as f:
            content = f.read()
        return SSISParser().parse(content)
    
    # ------------------------------------------------------------------
    
    def preview(self, package_id: uuid.UUID) -> GenerationPreview:
        """Run backward analysis without generating content."""
        package = self.get_package_or_raise(package_id)
        parsed = self.load_parsed_package(package)
        plan = StrategyClassifier().classify(parsed)
        
        planned = [
            {
                "name": m.name,
                "tier": m.notebook_type,
                "purpose": m.purpose,
                "estimated_cells": m.estimated_cells,
            }
            for m in plan.modules
        ]
        
        return GenerationPreview(
            package_id=package_id,
            package_name=package.package_name,
            strategy=plan.strategy,
            rationale=plan.rationale,
            planned_artifacts=planned,
        )
    
    def generate(
        self,
        package_id: uuid.UUID,
        options: GenerationOptions | None = None,
    ) -> GenerationResult:
        """Generate notebook artifacts for a package."""
        package = self.get_package_or_raise(package_id)
        parsed = self.load_parsed_package(package)
        
        result = self.generator.generate(
            package=parsed,
            package_id=package_id,
            options=options,
        )
        
        # Update package status so the UI can reflect progress
        if result.status == "success":
            package.status = "generated"
            self.session.add(package)
            self.session.flush()
        
        return result
