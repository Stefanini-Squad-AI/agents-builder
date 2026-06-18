"""Documentation sub-module for project documentation generation and change tracking.

Provides:
- DocumentationService: Generates versioned documentation snapshots
- Change detection: Tracks gaps filled, blockers, progress changes
- Mermaid diagram generation for Migration Map
- Event hooks for auto-regeneration
"""

from app.modules.migration_workbench.documentation.events import (
    DocumentationEventMixin,
    trigger_doc_regeneration,
)
from app.modules.migration_workbench.documentation.router import router
from app.modules.migration_workbench.documentation.schemas import (
    ChangesSummary,
    ChangeView,
    DocSnapshotView,
    GeneratedDocs,
)
from app.modules.migration_workbench.documentation.service import DocumentationService

__all__ = [
    "router",
    "DocumentationService",
    "DocumentationEventMixin",
    "trigger_doc_regeneration",
    "ChangeView",
    "ChangesSummary",
    "DocSnapshotView",
    "GeneratedDocs",
]
