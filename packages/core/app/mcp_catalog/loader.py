"""MCP Catalog Loader — loads and caches MCP server definitions from YAML.

Provides:
- Load all catalog entries from YAML files
- Filter by category, approval status, etc.
- Singleton caching for performance
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterator

import structlog
import yaml
from pydantic import ValidationError

from app.mcp_catalog.schema import (
    MCPCatalogEntry,
    MCPCatalogView,
    MCPCategory,
    MCPRiskLevel,
)

log = structlog.get_logger(__name__)

# Default path to catalog entries
_DEFAULT_ENTRIES_DIR = Path(__file__).parent / "entries"


class MCPCatalogLoader:
    """Load and query MCP catalog entries.
    
    Catalog entries are YAML files in the entries/ directory.
    Each file defines one MCP server's configuration.
    
    Usage:
        loader = MCPCatalogLoader()
        all_entries = loader.load_all()
        github = loader.get_entry("github")
        databases = loader.list_by_category(MCPCategory.DATABASE)
    """
    
    def __init__(self, entries_dir: Path | None = None):
        """Initialize the loader.
        
        Args:
            entries_dir: Directory containing YAML entry files.
                        Defaults to mcp_catalog/entries/
        """
        self._entries_dir = entries_dir or _DEFAULT_ENTRIES_DIR
        self._cache: dict[str, MCPCatalogEntry] | None = None
    
    def load_all(self) -> dict[str, MCPCatalogEntry]:
        """Load all catalog entries, keyed by mcp_key.
        
        Results are cached after first load.
        
        Returns:
            Dictionary mapping mcp_key to MCPCatalogEntry
        """
        if self._cache is not None:
            return self._cache
        
        self._cache = {}
        
        if not self._entries_dir.exists():
            log.warning("mcp_catalog_dir_missing", path=str(self._entries_dir))
            return self._cache
        
        for yaml_file in self._entries_dir.glob("*.yaml"):
            try:
                entry = self._load_entry(yaml_file)
                if entry:
                    self._cache[entry.key] = entry
                    log.debug("mcp_catalog_entry_loaded", key=entry.key)
            except Exception as e:
                log.error(
                    "mcp_catalog_entry_failed",
                    file=yaml_file.name,
                    error=str(e),
                )
        
        log.info("mcp_catalog_loaded", count=len(self._cache))
        return self._cache
    
    def _load_entry(self, yaml_file: Path) -> MCPCatalogEntry | None:
        """Load a single catalog entry from a YAML file."""
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if not data:
            log.warning("mcp_catalog_empty_file", file=yaml_file.name)
            return None
        
        try:
            return MCPCatalogEntry.model_validate(data)
        except ValidationError as e:
            log.error(
                "mcp_catalog_validation_error",
                file=yaml_file.name,
                errors=e.error_count(),
            )
            raise
    
    def reload(self) -> dict[str, MCPCatalogEntry]:
        """Force reload of all catalog entries.
        
        Clears the cache and reloads from disk.
        """
        self._cache = None
        return self.load_all()
    
    def get_entry(self, key: str) -> MCPCatalogEntry | None:
        """Get a specific catalog entry by key.
        
        Args:
            key: MCP key (e.g., "github", "postgres")
        
        Returns:
            MCPCatalogEntry if found, None otherwise
        """
        entries = self.load_all()
        return entries.get(key)
    
    def get_entry_or_raise(self, key: str) -> MCPCatalogEntry:
        """Get a catalog entry or raise ValueError.
        
        Args:
            key: MCP key
        
        Returns:
            MCPCatalogEntry
        
        Raises:
            ValueError: If entry not found
        """
        entry = self.get_entry(key)
        if not entry:
            raise ValueError(f"MCP catalog entry '{key}' not found")
        return entry
    
    def list_entries(self) -> list[MCPCatalogEntry]:
        """Get all catalog entries as a list."""
        return list(self.load_all().values())
    
    def list_views(self) -> list[MCPCatalogView]:
        """Get all catalog entries as API views."""
        return [MCPCatalogView.from_entry(e) for e in self.list_entries()]
    
    def list_by_category(self, category: MCPCategory) -> list[MCPCatalogEntry]:
        """Filter entries by category.
        
        Args:
            category: MCPCategory to filter by
        
        Returns:
            List of matching entries
        """
        return [e for e in self.list_entries() if e.category == category]
    
    def list_by_vendor(self, vendor: str) -> list[MCPCatalogEntry]:
        """Filter entries by vendor.
        
        Args:
            vendor: Vendor name to filter by (case-insensitive)
        
        Returns:
            List of matching entries
        """
        vendor_lower = vendor.lower()
        return [e for e in self.list_entries() if e.vendor.lower() == vendor_lower]
    
    def list_requiring_approval(self) -> list[MCPCatalogEntry]:
        """Get entries that require human approval."""
        return [e for e in self.list_entries() if e.requires_approval]
    
    def list_with_secrets(self) -> list[MCPCatalogEntry]:
        """Get entries that require secret values."""
        return [e for e in self.list_entries() if e.has_secrets]
    
    def list_with_n3_tools(self) -> list[MCPCatalogEntry]:
        """Get entries that have N3 (write/mutate) tools."""
        return [e for e in self.list_entries() if e.has_n3_tools]
    
    def search(self, query: str) -> list[MCPCatalogEntry]:
        """Search entries by name, description, or key.
        
        Args:
            query: Search string (case-insensitive)
        
        Returns:
            List of matching entries
        """
        query_lower = query.lower()
        results = []
        for entry in self.list_entries():
            if (
                query_lower in entry.key.lower()
                or query_lower in entry.name.lower()
                or query_lower in entry.description.lower()
            ):
                results.append(entry)
        return results
    
    def get_keys(self) -> list[str]:
        """Get all available MCP keys."""
        return list(self.load_all().keys())
    
    def get_categories(self) -> list[MCPCategory]:
        """Get all categories that have at least one entry."""
        categories = set()
        for entry in self.list_entries():
            categories.add(entry.category)
        return sorted(categories, key=lambda c: c.value)
    
    def __iter__(self) -> Iterator[MCPCatalogEntry]:
        """Iterate over all catalog entries."""
        return iter(self.list_entries())
    
    def __len__(self) -> int:
        """Get number of catalog entries."""
        return len(self.load_all())
    
    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the catalog."""
        return key in self.load_all()


@lru_cache(maxsize=1)
def get_catalog_loader() -> MCPCatalogLoader:
    """Get the singleton catalog loader instance.
    
    Use this for dependency injection in FastAPI.
    """
    return MCPCatalogLoader()


def get_mcp_entry(key: str) -> MCPCatalogEntry | None:
    """Convenience function to get an MCP entry by key."""
    return get_catalog_loader().get_entry(key)


def list_mcp_entries() -> list[MCPCatalogEntry]:
    """Convenience function to list all MCP entries."""
    return get_catalog_loader().list_entries()
