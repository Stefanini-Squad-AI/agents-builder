"""Pydantic schemas for MCP Configuration API.

Request/response models for per-project MCP server configuration.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.mcp_catalog.schema import MCPCategory


class MCPConfigCreate(BaseModel):
    """Request to add an MCP server configuration to a project."""

    mcp_key: str = Field(
        ...,
        description="MCP catalog key (e.g., 'github', 'databricks')",
        pattern=r"^[a-z][a-z0-9-]*$",
    )
    env_vars: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables (including secrets)",
    )
    config_fields: dict[str, str | int | bool] = Field(
        default_factory=dict,
        description="Non-secret configuration fields",
    )
    enabled: bool = Field(default=True, description="Whether this config is active")
    created_by: str | None = Field(
        default=None, description="User who created this config"
    )


class MCPConfigUpdate(BaseModel):
    """Request to update an existing MCP config."""

    env_vars: dict[str, str] | None = Field(
        default=None,
        description="Environment variables to update (merged with existing)",
    )
    config_fields: dict[str, str | int | bool] | None = Field(
        default=None,
        description="Config fields to update (merged with existing)",
    )
    enabled: bool | None = Field(default=None, description="Enable/disable the config")


class MCPConfigToggle(BaseModel):
    """Request to enable/disable an MCP config."""

    enabled: bool


class MCPConfigValidation(BaseModel):
    """Result of validating an MCP configuration."""

    valid: bool
    missing_env_vars: list[str] = Field(default_factory=list)
    missing_config_fields: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class MCPConfigView(BaseModel):
    """API response for an MCP configuration.

    Secrets are masked in env_vars_masked — actual values are never returned.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    mcp_key: str

    # Masked secrets (values replaced with "***")
    env_vars_masked: dict[str, str]

    # Non-secret config
    config_fields: dict[str, str | int | bool]

    # Status
    enabled: bool
    validated_at: datetime | None
    validation_error: str | None

    # Catalog metadata (joined from catalog entry)
    mcp_name: str
    mcp_description: str
    mcp_category: MCPCategory
    mcp_vendor: str

    # Audit
    created_at: datetime
    updated_at: datetime
    created_by: str | None


class MCPConfigSummary(BaseModel):
    """Lightweight summary for listing MCP configs."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mcp_key: str
    mcp_name: str
    mcp_category: MCPCategory
    enabled: bool
    validated_at: datetime | None
    has_validation_error: bool


class MCPCatalogListItem(BaseModel):
    """Summary of an MCP catalog entry for listing."""

    key: str
    name: str
    description: str
    vendor: str
    category: MCPCategory
    requires_approval: bool
    has_secrets: bool
    tool_count: int


# -----------------------------------------------------------------------------
# Cursor Export Schemas
# -----------------------------------------------------------------------------


class CursorMCPServerConfig(BaseModel):
    """Single MCP server configuration in Cursor format.

    This is the format expected by Cursor IDE in .cursor/mcp.json.
    """

    command: str = Field(..., description="Executable command (e.g., 'npx', 'uvx', 'python')")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables (contains decrypted secrets)",
    )


class CursorMCPConfig(BaseModel):
    """Complete Cursor MCP configuration for .cursor/mcp.json.

    WARNING: This schema contains decrypted secrets in the env fields.
    Only use for export operations with proper authentication.
    """

    mcpServers: dict[str, CursorMCPServerConfig] = Field(
        default_factory=dict,
        description="Map of server name to server configuration",
    )

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=indent)


class MCPExportPreview(BaseModel):
    """Preview of MCP export without actual secrets.

    Used to show what will be exported before the user confirms.
    """

    server_count: int
    servers: list[str] = Field(description="List of MCP keys to be exported")
    has_secrets: bool = Field(description="Whether any servers have secrets")
    warning: str = Field(
        default="Export will contain decrypted secrets. Handle with care.",
    )
