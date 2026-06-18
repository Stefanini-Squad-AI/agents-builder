"""Technology Profiles sub-module.

Provides technology-aware context for skill generation and analysis.
Profiles describe structural patterns, execution modes, and validation
requirements for source technologies (SSIS, Airflow, etc.).
"""

from app.modules.migration_workbench.profiles.loader import (
    get_profile,
    list_profiles,
    get_all_profiles,
)
from app.modules.migration_workbench.profiles.schema import (
    TechnologyProfile,
    StructuralPattern,
    ExecutionPattern,
    ValidationRequirement,
)
from app.modules.migration_workbench.profiles.router import router

__all__ = [
    "router",
    "get_profile",
    "list_profiles",
    "get_all_profiles",
    "TechnologyProfile",
    "StructuralPattern",
    "ExecutionPattern",
    "ValidationRequirement",
]
