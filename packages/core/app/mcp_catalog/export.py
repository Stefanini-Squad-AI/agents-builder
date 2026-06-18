"""MCP Export Service — generate Cursor-format MCP configurations.

Exports project MCP configurations to .cursor/mcp.json format for
direct use in Cursor IDE.

WARNING: Export operations return decrypted secrets. Ensure proper
authentication and audit logging before using these methods.
"""

from __future__ import annotations

import shlex
import uuid
from pathlib import Path

import structlog
from sqlalchemy.orm import Session

from app.mcp_catalog.loader import get_catalog_loader, MCPCatalogLoader
from app.mcp_catalog.schema import MCPCatalogEntry
from app.mcp_catalog.schemas import (
    CursorMCPConfig,
    CursorMCPServerConfig,
    MCPExportPreview,
)
from app.mcp_catalog.service import MCPConfigService
from app.modules.migration_workbench.models import ProjectMCPConfig

log = structlog.get_logger(__name__)


class MCPExportService:
    """Export MCP configurations to Cursor format.

    Generates .cursor/mcp.json files from enabled project MCP configs.
    Decrypts secrets for the export — handle output securely.
    """

    def __init__(self, session: Session):
        self._session = session
        self._config_service = MCPConfigService(session)
        self._catalog = get_catalog_loader()

    def build_cursor_config(self, project_id: uuid.UUID) -> CursorMCPConfig:
        """Build Cursor-format MCP config from project configurations.

        Only includes enabled and validated configurations.

        Args:
            project_id: The project to export

        Returns:
            CursorMCPConfig ready for serialization

        Note:
            This method returns decrypted secrets. Audit and authenticate.
        """
        configs = self._config_service.list_enabled_configs(project_id)
        servers: dict[str, CursorMCPServerConfig] = {}

        for config in configs:
            entry = self._catalog.get_entry(config.mcp_key)
            if not entry:
                log.warning(
                    "mcp_export_missing_catalog_entry",
                    project_id=str(project_id),
                    mcp_key=config.mcp_key,
                )
                continue

            try:
                server_config = self._build_server_config(config, entry)
                servers[config.mcp_key] = server_config
            except Exception as e:
                log.error(
                    "mcp_export_server_build_failed",
                    project_id=str(project_id),
                    mcp_key=config.mcp_key,
                    error=str(e),
                )

        log.info(
            "mcp_export_built",
            project_id=str(project_id),
            server_count=len(servers),
        )

        return CursorMCPConfig(mcpServers=servers)

    def _build_server_config(
        self,
        config: ProjectMCPConfig,
        entry: MCPCatalogEntry,
    ) -> CursorMCPServerConfig:
        """Build Cursor config for a single MCP server.

        Parses the run_command from the catalog entry and merges
        environment variables from the project config.
        """
        command, args = self._parse_run_command(entry.run_command)

        env_vars = self._config_service.get_env_vars(config)

        for key, field in entry.config_fields.items():
            value = config.config_fields.get(key)
            if value is not None:
                env_vars[key] = str(value)
            elif field.default is not None:
                env_vars[key] = str(field.default)

        return CursorMCPServerConfig(
            command=command,
            args=args,
            env=env_vars,
        )

    def _parse_run_command(self, run_command: str) -> tuple[str, list[str]]:
        """Parse a run_command string into command and args.

        Examples:
            "npx @mcp/server-github" → ("npx", ["@mcp/server-github"])
            "uvx mcp-server-fetch" → ("uvx", ["mcp-server-fetch"])
            "python -m mcp_server" → ("python", ["-m", "mcp_server"])

        Args:
            run_command: The command string from catalog entry

        Returns:
            Tuple of (command, args)
        """
        parts = shlex.split(run_command)
        if not parts:
            return ("npx", [])

        command = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        return command, args

    def get_export_preview(self, project_id: uuid.UUID) -> MCPExportPreview:
        """Get a preview of what will be exported (without secrets).

        Use this to show the user what will be included before they
        confirm the export.

        Args:
            project_id: The project to preview

        Returns:
            MCPExportPreview with server list and metadata
        """
        configs = self._config_service.list_enabled_configs(project_id)

        servers = []
        has_secrets = False

        for config in configs:
            entry = self._catalog.get_entry(config.mcp_key)
            if entry:
                servers.append(config.mcp_key)
                if entry.has_secrets:
                    has_secrets = True

        return MCPExportPreview(
            server_count=len(servers),
            servers=servers,
            has_secrets=has_secrets,
        )

    def export_to_json(self, project_id: uuid.UUID, indent: int = 2) -> str:
        """Export as JSON string.

        Args:
            project_id: The project to export
            indent: JSON indentation (default 2 spaces)

        Returns:
            JSON string ready for .cursor/mcp.json
        """
        config = self.build_cursor_config(project_id)
        return config.to_json(indent=indent)

    def export_to_file(
        self,
        project_id: uuid.UUID,
        base_path: Path,
        create_dirs: bool = True,
    ) -> Path:
        """Export to .cursor/mcp.json file.

        Args:
            project_id: The project to export
            base_path: Base directory (e.g., project workspace root)
            create_dirs: Whether to create .cursor directory if missing

        Returns:
            Path to the created mcp.json file
        """
        cursor_dir = base_path / ".cursor"
        if create_dirs:
            cursor_dir.mkdir(parents=True, exist_ok=True)

        mcp_json_path = cursor_dir / "mcp.json"
        json_content = self.export_to_json(project_id)

        mcp_json_path.write_text(json_content, encoding="utf-8")

        log.info(
            "mcp_export_written",
            project_id=str(project_id),
            path=str(mcp_json_path),
        )

        return mcp_json_path

    def export_to_bytes(self, project_id: uuid.UUID) -> bytes:
        """Export as UTF-8 bytes (for ZIP inclusion or download).

        Args:
            project_id: The project to export

        Returns:
            UTF-8 encoded JSON bytes
        """
        json_content = self.export_to_json(project_id)
        return json_content.encode("utf-8")
