"""MCP Catalog — central registry of MCP server definitions.

This module provides a catalog of available MCP servers that can be
configured per project. Each server is defined in a YAML file that
describes its configuration requirements, tools, and approval status.

Usage:
    from app.mcp_catalog import get_catalog_loader, MCPCatalogEntry

    loader = get_catalog_loader()
    github = loader.get_entry("github")
    databases = loader.list_by_category(MCPCategory.DATABASE)

    # Per-project config
    from app.mcp_catalog import MCPConfigService
    service = MCPConfigService(session)
    configs = service.list_configs(project_id)

    # Export to Cursor format
    from app.mcp_catalog import MCPExportService
    export = MCPExportService(session)
    cursor_config = export.build_cursor_config(project_id)
"""

from app.mcp_catalog.export import MCPExportService
from app.mcp_catalog.loader import (
    MCPCatalogLoader,
    get_catalog_loader,
    get_mcp_entry,
    list_mcp_entries,
)
from app.mcp_catalog.schema import (
    MCPCatalogConfigField,
    MCPCatalogEntry,
    MCPCatalogEnvVar,
    MCPCatalogTool,
    MCPCatalogView,
    MCPCategory,
    MCPRiskLevel,
)
from app.mcp_catalog.schemas import (
    CursorMCPConfig,
    CursorMCPServerConfig,
    MCPCatalogListItem,
    MCPConfigCreate,
    MCPConfigSummary,
    MCPConfigToggle,
    MCPConfigUpdate,
    MCPConfigValidation,
    MCPConfigView,
    MCPExportPreview,
)
from app.mcp_catalog.service import MCPConfigService

__all__ = [
    # Catalog Schema
    "MCPCatalogEntry",
    "MCPCatalogView",
    "MCPCatalogEnvVar",
    "MCPCatalogConfigField",
    "MCPCatalogTool",
    "MCPCategory",
    "MCPRiskLevel",
    # Loader
    "MCPCatalogLoader",
    "get_catalog_loader",
    "get_mcp_entry",
    "list_mcp_entries",
    # Config API Schemas
    "MCPCatalogListItem",
    "MCPConfigCreate",
    "MCPConfigUpdate",
    "MCPConfigToggle",
    "MCPConfigValidation",
    "MCPConfigView",
    "MCPConfigSummary",
    # Cursor Export Schemas
    "CursorMCPConfig",
    "CursorMCPServerConfig",
    "MCPExportPreview",
    # Services
    "MCPConfigService",
    "MCPExportService",
]
