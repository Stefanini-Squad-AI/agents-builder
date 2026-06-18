"""Migration Workbench main router.

Mounts all sub-routers for the migration workbench module.
All routes are prefixed with /api/migrations.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.migration_workbench.analysis.router import router as analysis_router
from app.modules.migration_workbench.context.router import router as context_router
from app.modules.migration_workbench.documentation.router import router as docs_router
from app.modules.migration_workbench.generation.router import router as generation_router
from app.modules.migration_workbench.map.router import router as map_router
from app.modules.migration_workbench.profiles.router import router as profiles_router
from app.modules.migration_workbench.propagation.router import router as propagation_router
from app.modules.migration_workbench.reconciliation.router import router as reconciliation_router
from app.modules.migration_workbench.registry.router import router as registry_router
from app.modules.migration_workbench.signoff.router import router as signoff_router
from app.modules.migration_workbench.skills.router import router as skills_router

# Main module router
router = APIRouter(prefix="/api/migrations", tags=["Migration Workbench"])


# Health check endpoint
@router.get("/health")
async def health_check() -> dict[str, str]:
    """Check if Migration Workbench module is healthy."""
    return {"status": "ok", "module": "migration_workbench"}


# Mount sub-routers
# Profiles are global (not project-specific)
router.include_router(profiles_router, prefix="/profiles", tags=["Technology Profiles"])

# Registry, context, and docs are project-specific - routes include {project_ref}
router.include_router(registry_router, tags=["Package Registry"])
router.include_router(context_router, tags=["Shared Context"])
router.include_router(docs_router, tags=["Documentation"])
router.include_router(analysis_router, tags=["Analysis"])
router.include_router(map_router, tags=["Migration Map"])
router.include_router(propagation_router, tags=["Propagation"])
router.include_router(generation_router, tags=["Generation"])
router.include_router(reconciliation_router, tags=["Reconciliation"])
router.include_router(signoff_router, tags=["Sign-off"])
router.include_router(skills_router, tags=["Skills"])

# Future sub-routers (to be added in later phases):
