"""MCP Configuration Service — CRUD and validation for per-project MCP configs.

Manages ProjectMCPConfig records, validates against the catalog,
and provides masked views for the API.

Secrets are encrypted at rest using Fernet with project-scoped keys
when WORKSHOP_ENCRYPTION_KEY is configured.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto import get_crypto_service
from app.mcp_catalog.loader import get_catalog_loader
from app.mcp_catalog.schema import MCPCatalogEntry
from app.mcp_catalog.schemas import (
    MCPConfigCreate,
    MCPConfigSummary,
    MCPConfigUpdate,
    MCPConfigValidation,
    MCPConfigView,
)
from app.modules.migration_workbench.models import ProjectMCPConfig

log = structlog.get_logger(__name__)


class MCPConfigService:
    """Service for managing per-project MCP configurations.

    Secrets in env_vars are encrypted at rest when WORKSHOP_ENCRYPTION_KEY
    is configured. Without encryption, secrets are stored as plain JSON
    (not recommended for production).
    """

    def __init__(self, session: Session):
        self._session = session
        self._catalog = get_catalog_loader()
        self._crypto = get_crypto_service()

    def create_config(
        self,
        project_id: uuid.UUID,
        payload: MCPConfigCreate,
    ) -> ProjectMCPConfig:
        """Create a new MCP configuration for a project.

        Args:
            project_id: The project to add the config to
            payload: Configuration data

        Returns:
            The created ProjectMCPConfig

        Raises:
            ValueError: If mcp_key is not in catalog or already configured
        """
        entry = self._catalog.get_entry(payload.mcp_key)
        if not entry:
            raise ValueError(f"MCP '{payload.mcp_key}' not found in catalog")

        existing = self._get_by_key(project_id, payload.mcp_key)
        if existing:
            raise ValueError(
                f"MCP '{payload.mcp_key}' is already configured for this project"
            )

        config = ProjectMCPConfig(
            id=uuid.uuid4(),
            project_id=project_id,
            mcp_key=payload.mcp_key,
            env_vars_encrypted=self._encrypt_env_vars(project_id, payload.env_vars),
            config_fields=payload.config_fields or {},
            enabled=payload.enabled,
            created_by=payload.created_by,
        )

        self._session.add(config)
        self._session.flush()

        log.info(
            "mcp_config_created",
            project_id=str(project_id),
            mcp_key=payload.mcp_key,
            config_id=str(config.id),
        )

        return config

    def update_config(
        self,
        config_id: uuid.UUID,
        payload: MCPConfigUpdate,
    ) -> ProjectMCPConfig:
        """Update an existing MCP configuration.

        Args:
            config_id: The config to update
            payload: Fields to update (merged with existing)

        Returns:
            The updated ProjectMCPConfig

        Raises:
            ValueError: If config not found
        """
        config = self.get_config(config_id)
        if not config:
            raise ValueError(f"MCP config '{config_id}' not found")

        if payload.env_vars is not None:
            existing_vars = self._decrypt_env_vars(config)
            existing_vars.update(payload.env_vars)
            config.env_vars_encrypted = self._encrypt_env_vars(
                config.project_id, existing_vars
            )
            config.validated_at = None
            config.validation_error = None

        if payload.config_fields is not None:
            existing_fields = dict(config.config_fields or {})
            existing_fields.update(payload.config_fields)
            config.config_fields = existing_fields
            config.validated_at = None
            config.validation_error = None

        if payload.enabled is not None:
            config.enabled = payload.enabled

        self._session.flush()

        log.info(
            "mcp_config_updated",
            config_id=str(config_id),
            mcp_key=config.mcp_key,
        )

        return config

    def delete_config(self, config_id: uuid.UUID) -> bool:
        """Delete an MCP configuration.

        Args:
            config_id: The config to delete

        Returns:
            True if deleted, False if not found
        """
        config = self.get_config(config_id)
        if not config:
            return False

        self._session.delete(config)
        self._session.flush()

        log.info(
            "mcp_config_deleted",
            config_id=str(config_id),
            mcp_key=config.mcp_key,
        )

        return True

    def get_config(self, config_id: uuid.UUID) -> ProjectMCPConfig | None:
        """Get a single MCP configuration by ID."""
        stmt = select(ProjectMCPConfig).where(ProjectMCPConfig.id == config_id)
        return self._session.scalars(stmt).first()

    def list_configs(self, project_id: uuid.UUID) -> list[ProjectMCPConfig]:
        """List all MCP configurations for a project."""
        stmt = (
            select(ProjectMCPConfig)
            .where(ProjectMCPConfig.project_id == project_id)
            .order_by(ProjectMCPConfig.mcp_key)
        )
        return list(self._session.scalars(stmt).all())

    def list_enabled_configs(self, project_id: uuid.UUID) -> list[ProjectMCPConfig]:
        """List only enabled MCP configurations for a project."""
        stmt = (
            select(ProjectMCPConfig)
            .where(ProjectMCPConfig.project_id == project_id)
            .where(ProjectMCPConfig.enabled.is_(True))
            .order_by(ProjectMCPConfig.mcp_key)
        )
        return list(self._session.scalars(stmt).all())

    def toggle_enabled(self, config_id: uuid.UUID, enabled: bool) -> ProjectMCPConfig:
        """Enable or disable an MCP configuration.

        Args:
            config_id: The config to toggle
            enabled: New enabled state

        Returns:
            The updated config

        Raises:
            ValueError: If config not found
        """
        config = self.get_config(config_id)
        if not config:
            raise ValueError(f"MCP config '{config_id}' not found")

        config.enabled = enabled
        self._session.flush()

        log.info(
            "mcp_config_toggled",
            config_id=str(config_id),
            mcp_key=config.mcp_key,
            enabled=enabled,
        )

        return config

    def validate_config(self, config_id: uuid.UUID) -> MCPConfigValidation:
        """Validate an MCP configuration against its catalog entry.

        Checks that all required env_vars and config_fields are present.

        Args:
            config_id: The config to validate

        Returns:
            Validation result

        Raises:
            ValueError: If config not found
        """
        config = self.get_config(config_id)
        if not config:
            raise ValueError(f"MCP config '{config_id}' not found")

        entry = self._catalog.get_entry(config.mcp_key)
        if not entry:
            return MCPConfigValidation(
                valid=False,
                errors=[f"MCP '{config.mcp_key}' no longer exists in catalog"],
            )

        env_vars = self._decrypt_env_vars(config)
        config_fields = config.config_fields or {}

        missing_env_vars = [
            k for k, v in entry.env_vars.items() if v.required and k not in env_vars
        ]

        missing_config_fields = [
            k
            for k, v in entry.config_fields.items()
            if v.required and v.default is None and k not in config_fields
        ]

        errors: list[str] = []

        valid = not missing_env_vars and not missing_config_fields and not errors

        if valid:
            config.validated_at = datetime.now(timezone.utc)
            config.validation_error = None
        else:
            config.validation_error = "; ".join(
                [f"Missing env: {k}" for k in missing_env_vars]
                + [f"Missing config: {k}" for k in missing_config_fields]
                + errors
            )

        self._session.flush()

        log.info(
            "mcp_config_validated",
            config_id=str(config_id),
            mcp_key=config.mcp_key,
            valid=valid,
        )

        return MCPConfigValidation(
            valid=valid,
            missing_env_vars=missing_env_vars,
            missing_config_fields=missing_config_fields,
            errors=errors,
        )

    def to_view(self, config: ProjectMCPConfig) -> MCPConfigView:
        """Convert a config to an API view with masked secrets."""
        entry = self._catalog.get_entry(config.mcp_key)

        env_vars = self._decrypt_env_vars(config)
        env_vars_masked = {k: "***" if v else "" for k, v in env_vars.items()}

        return MCPConfigView(
            id=config.id,
            project_id=config.project_id,
            mcp_key=config.mcp_key,
            env_vars_masked=env_vars_masked,
            config_fields=config.config_fields or {},
            enabled=config.enabled,
            validated_at=config.validated_at,
            validation_error=config.validation_error,
            mcp_name=entry.name if entry else config.mcp_key,
            mcp_description=entry.description if entry else "",
            mcp_category=entry.category if entry else "utility",
            mcp_vendor=entry.vendor if entry else "unknown",
            created_at=config.created_at,
            updated_at=config.updated_at,
            created_by=config.created_by,
        )

    def to_summary(self, config: ProjectMCPConfig) -> MCPConfigSummary:
        """Convert a config to a lightweight summary."""
        entry = self._catalog.get_entry(config.mcp_key)

        return MCPConfigSummary(
            id=config.id,
            mcp_key=config.mcp_key,
            mcp_name=entry.name if entry else config.mcp_key,
            mcp_category=entry.category if entry else "utility",
            enabled=config.enabled,
            validated_at=config.validated_at,
            has_validation_error=bool(config.validation_error),
        )

    def get_env_vars(self, config: ProjectMCPConfig) -> dict[str, str]:
        """Get decrypted environment variables for a config.

        WARNING: Returns actual secrets. Only use internally for
        generating Cursor config or running MCP servers.
        """
        return self._decrypt_env_vars(config)

    def _get_by_key(
        self, project_id: uuid.UUID, mcp_key: str
    ) -> ProjectMCPConfig | None:
        """Get a config by project and mcp_key."""
        stmt = (
            select(ProjectMCPConfig)
            .where(ProjectMCPConfig.project_id == project_id)
            .where(ProjectMCPConfig.mcp_key == mcp_key)
        )
        return self._session.scalars(stmt).first()

    def _encrypt_env_vars(
        self, project_id: uuid.UUID, env_vars: dict[str, str] | None
    ) -> str | None:
        """Encrypt environment variables for storage.

        Uses Fernet encryption if WORKSHOP_ENCRYPTION_KEY is set,
        otherwise falls back to plain JSON.
        """
        if not env_vars:
            return None
        return self._crypto.encrypt_or_json(project_id, env_vars)

    def _decrypt_env_vars(self, config: ProjectMCPConfig) -> dict[str, str]:
        """Decrypt environment variables from storage.

        Handles both Fernet-encrypted and plain JSON formats for
        backward compatibility during migration.
        """
        return self._crypto.decrypt_or_parse_json(
            config.project_id, config.env_vars_encrypted
        )
