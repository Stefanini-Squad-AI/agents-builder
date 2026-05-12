"""Template families for rendering skills, cards, and project structure.

Public API:
    get_family(slug) -> TemplateFamily
    TEMPLATE_REGISTRY -> dict[str, TemplateFamily]
    TemplateFamily -> ABC base class
    PhaseVliFamily -> VLI-style phase-based template family
"""

from app.families._base import TemplateFamily
from app.families.phase_vli import PhaseVliFamily
from app.families.registry import TEMPLATE_REGISTRY, get_family

__all__ = [
    "TEMPLATE_REGISTRY",
    "PhaseVliFamily",
    "TemplateFamily",
    "get_family",
]
