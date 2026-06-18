"""Pydantic schemas for MCP Catalog entries.

Defines the structure of MCP server definitions in YAML files.
Each entry describes an MCP server's configuration requirements,
environment variables, tools, and approval status.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class MCPRiskLevel(str, Enum):
    """Risk level for MCP tools.
    
    N1: Read-only operations, no side effects
    N2: Query/search operations, limited scope
    N3: Write/mutate operations, requires careful review
    """
    
    N1 = "N1"
    N2 = "N2"
    N3 = "N3"


class MCPCategory(str, Enum):
    """Categories for MCP servers."""
    
    SOURCE_CONTROL = "source_control"
    DATABASE = "database"
    PROJECT_MANAGEMENT = "project_management"
    DOCUMENTATION = "documentation"
    MESSAGING = "messaging"
    MONITORING = "monitoring"
    UTILITY = "utility"
    CLOUD = "cloud"


class MCPCatalogEnvVar(BaseModel):
    """Environment variable definition for an MCP server.
    
    Attributes:
        required: Whether this env var must be provided
        secret: Whether this value should be encrypted at rest
        label: Human-readable label for UI
        hint: Help text explaining what this value is for
    """
    
    required: bool = True
    secret: bool = False
    label: str
    hint: str = ""


class MCPCatalogConfigField(BaseModel):
    """Configuration field definition for an MCP server.
    
    These are non-secret configuration values that customize
    the MCP server's behavior (e.g., repository owner, project key).
    
    Attributes:
        type: Data type for validation
        required: Whether this field must be provided
        label: Human-readable label for UI
        hint: Help text explaining what this value is for
        default: Default value if not provided
    """
    
    type: Literal["string", "number", "boolean", "url"] = "string"
    required: bool = True
    label: str
    hint: str = ""
    default: str | None = None


class MCPCatalogTool(BaseModel):
    """Tool definition within an MCP server.
    
    Attributes:
        name: Tool name as exposed by the MCP server
        description: What this tool does
        risk_level: Risk classification for approval workflows
    """
    
    name: str
    description: str = ""
    risk_level: MCPRiskLevel = MCPRiskLevel.N1


class MCPCatalogEntry(BaseModel):
    """Complete definition of an MCP server in the catalog.
    
    Each YAML file in mcp_catalog/entries/ should conform to this schema.
    
    Attributes:
        key: Unique identifier (e.g., "github", "jira-atlassian")
        name: Display name (e.g., "GitHub", "Jira")
        description: What this MCP server provides
        vendor: Organization that provides this MCP
        category: Classification for filtering
        run_command: Command to start the MCP server
        env_vars: Environment variables the server needs
        config_fields: Non-secret configuration fields
        tools: List of tools exposed by the server
        requires_approval: Whether human approval is needed before use
        documentation_url: Link to MCP server documentation
        icon: Icon name or URL for UI display
    """
    
    key: str = Field(..., pattern=r"^[a-z][a-z0-9-]*$")
    name: str
    description: str
    vendor: str
    category: MCPCategory
    run_command: str = Field(..., description="Command to start the MCP server (e.g., 'npx @modelcontextprotocol/server-github')")
    
    env_vars: dict[str, MCPCatalogEnvVar] = Field(default_factory=dict)
    config_fields: dict[str, MCPCatalogConfigField] = Field(default_factory=dict)
    tools: list[MCPCatalogTool] = Field(default_factory=list)
    
    requires_approval: bool = False
    documentation_url: str | None = None
    icon: str | None = None
    
    @property
    def has_secrets(self) -> bool:
        """Check if this MCP requires any secret values."""
        return any(ev.secret for ev in self.env_vars.values())
    
    @property
    def has_n3_tools(self) -> bool:
        """Check if this MCP has any N3 (write/mutate) tools."""
        return any(t.risk_level == MCPRiskLevel.N3 for t in self.tools)
    
    @property
    def required_env_vars(self) -> list[str]:
        """Get list of required environment variable names."""
        return [k for k, v in self.env_vars.items() if v.required]
    
    @property
    def required_config_fields(self) -> list[str]:
        """Get list of required configuration field names."""
        return [k for k, v in self.config_fields.items() if v.required]


class MCPCatalogView(BaseModel):
    """API view of an MCP catalog entry.
    
    Adds computed fields for easier frontend consumption.
    """
    
    key: str
    name: str
    description: str
    vendor: str
    category: MCPCategory
    
    env_var_count: int
    secret_count: int
    config_field_count: int
    tool_count: int
    
    has_secrets: bool
    has_n3_tools: bool
    requires_approval: bool
    
    documentation_url: str | None = None
    icon: str | None = None

    # Detail fields (needed by the configuration form on the frontend)
    run_command: str
    env_vars: dict[str, MCPCatalogEnvVar] = Field(default_factory=dict)
    config_fields: dict[str, MCPCatalogConfigField] = Field(default_factory=dict)
    tools: list[MCPCatalogTool] = Field(default_factory=list)
    
    @classmethod
    def from_entry(cls, entry: MCPCatalogEntry) -> "MCPCatalogView":
        """Create a view from a catalog entry."""
        return cls(
            key=entry.key,
            name=entry.name,
            description=entry.description,
            vendor=entry.vendor,
            category=entry.category,
            env_var_count=len(entry.env_vars),
            secret_count=sum(1 for ev in entry.env_vars.values() if ev.secret),
            config_field_count=len(entry.config_fields),
            tool_count=len(entry.tools),
            has_secrets=entry.has_secrets,
            has_n3_tools=entry.has_n3_tools,
            requires_approval=entry.requires_approval,
            documentation_url=entry.documentation_url,
            icon=entry.icon,
            run_command=entry.run_command,
            env_vars=entry.env_vars,
            config_fields=entry.config_fields,
            tools=entry.tools,
        )
