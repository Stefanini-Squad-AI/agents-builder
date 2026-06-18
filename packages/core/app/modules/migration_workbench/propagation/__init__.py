"""Propagation module for knowledge transfer between packages.

This module enables "resolve once, apply everywhere" workflows by
propagating decisions from one package to similar packages.
"""

from app.modules.migration_workbench.propagation.router import router as propagation_router
from app.modules.migration_workbench.propagation.schemas import (
    BatchWaveAssignment,
    BatchWaveResult,
    PropagationPreview,
    PropagationRequest,
    PropagationResult,
    PropagationScope,
)
from app.modules.migration_workbench.propagation.service import PropagationService

__all__ = [
    "PropagationService",
    "PropagationScope",
    "PropagationRequest",
    "PropagationResult",
    "PropagationPreview",
    "BatchWaveAssignment",
    "BatchWaveResult",
    "propagation_router",
]
