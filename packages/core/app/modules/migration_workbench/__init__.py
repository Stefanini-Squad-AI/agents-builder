"""Migration Workbench module.

Provides comprehensive ETL migration support including:
- Package registry and tracking
- Technology profiles (SSIS, Airflow, etc.)
- Shared context (connections, rules, decisions)
- Migration Map (flow graph visualization)
- Batch operations and knowledge propagation

All routes are mounted at /api/migrations/*
"""

from app.modules.migration_workbench.models import (
    DocumentationChange,
    ETLPackage,
    MapRelationship,
    MigrationBusinessRule,
    MigrationConnection,
    MigrationDocSnapshot,
    MigrationResolvedDecision,
    PackageConnectionPoints,
)
from app.modules.migration_workbench.router import router

__all__ = [
    "router",
    "ETLPackage",
    "PackageConnectionPoints",
    "MigrationConnection",
    "MigrationBusinessRule",
    "MigrationResolvedDecision",
    "MapRelationship",
    "MigrationDocSnapshot",
    "DocumentationChange",
]
