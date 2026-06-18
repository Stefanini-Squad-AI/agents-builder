"""Technology Profile loader.

Loads and caches YAML technology profiles from disk.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.modules.migration_workbench.profiles.schema import TechnologyProfile

# Directory containing profile YAML files
PROFILES_DIR = Path(__file__).parent


@lru_cache(maxsize=32)
def _load_profile_from_file(profile_path: str) -> TechnologyProfile:
    """Load a single profile from a YAML file (cached)."""
    path = Path(profile_path)
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    return TechnologyProfile(**data)


def get_profile(slug: str) -> TechnologyProfile:
    """Get a technology profile by slug.
    
    Args:
        slug: Technology identifier (e.g., "ssis", "airflow")
        
    Returns:
        TechnologyProfile instance
        
    Raises:
        FileNotFoundError: If profile doesn't exist
    """
    profile_path = PROFILES_DIR / f"{slug}.yaml"
    return _load_profile_from_file(str(profile_path))


def list_profiles() -> list[str]:
    """List all available profile slugs.
    
    Returns:
        List of profile slugs (e.g., ["ssis", "airflow"])
    """
    profiles = []
    for path in PROFILES_DIR.glob("*.yaml"):
        # Skip files that aren't profiles (like common_etl which is shared)
        if path.stem not in ("common_etl",):
            profiles.append(path.stem)
    return sorted(profiles)


def get_all_profiles() -> dict[str, TechnologyProfile]:
    """Load all available profiles.
    
    Returns:
        Dict mapping slug to TechnologyProfile
    """
    profiles = {}
    for slug in list_profiles():
        try:
            profiles[slug] = get_profile(slug)
        except Exception:
            # Skip invalid profiles
            pass
    return profiles


def clear_cache() -> None:
    """Clear the profile cache (useful for testing)."""
    _load_profile_from_file.cache_clear()


class ProfileLoader:
    """Class-based wrapper for profile loading functions.
    
    Provides object-oriented access to technology profiles.
    """
    
    def get_profile(self, slug: str) -> TechnologyProfile:
        """Get a technology profile by slug."""
        return get_profile(slug)
    
    def list_profiles(self) -> list[str]:
        """List all available profile slugs."""
        return list_profiles()
    
    def get_all_profiles(self) -> dict[str, TechnologyProfile]:
        """Load all available profiles."""
        return get_all_profiles()
    
    def clear_cache(self) -> None:
        """Clear the profile cache."""
        clear_cache()
