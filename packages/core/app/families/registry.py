"""Template family registry and factory functions."""

from app.families._base import TemplateFamily
from app.families.phase_vli import PhaseVliFamily

# Global registry of all available template families
TEMPLATE_REGISTRY: dict[str, TemplateFamily] = {
    "phase_vli": PhaseVliFamily(),
    # Future families will be added here:
    # "strict_9": Strict9Family(),   # P5+
    # "free_form": FreeFormFamily(), # P5+
}


def get_family(slug: str) -> TemplateFamily:
    """Get a template family by its slug.

    Args:
        slug: Template family slug (e.g., "phase_vli")

    Returns:
        Template family instance

    Raises:
        ValueError: If slug is not found in registry
    """
    if slug not in TEMPLATE_REGISTRY:
        available = ", ".join(TEMPLATE_REGISTRY.keys())
        raise ValueError(f"Unknown template family: '{slug}'. Available families: {available}")

    return TEMPLATE_REGISTRY[slug]


def list_families() -> list[str]:
    """List all available template family slugs.

    Returns:
        List of template family slugs
    """
    return list(TEMPLATE_REGISTRY.keys())


def get_default_family() -> TemplateFamily:
    """Get the default template family (phase_vli).

    Returns:
        Default template family instance
    """
    return TEMPLATE_REGISTRY["phase_vli"]
