"""Migration Map module.

Provides flow graph visualization and relationship detection
for ETL package migrations.

Main components:
- ObjectRegistry: Track tables/files/APIs across packages
- RelationshipDetector: Detect data flow dependencies
- FlowDetector: Find clusters and compute migration order (NetworkX)
- MigrationMapService: Orchestration layer
"""

from app.modules.migration_workbench.map.detector import RelationshipDetector
from app.modules.migration_workbench.map.graph import FlowDetector
from app.modules.migration_workbench.map.object_registry import ObjectRegistry
from app.modules.migration_workbench.map.router import router as map_router
from app.modules.migration_workbench.map.service import MigrationMapService

__all__ = [
    "ObjectRegistry",
    "RelationshipDetector",
    "FlowDetector",
    "MigrationMapService",
    "map_router",
]
