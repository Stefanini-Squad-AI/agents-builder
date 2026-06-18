"""Databricks Configuration Service — CRUD for workspace connections.

Manages DatabricksConfig records with encrypted PAT storage.
Uses the same Fernet encryption as MCP secrets (app/crypto.py).
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto import get_crypto_service
from app.domain.lakebridge import DatabricksConfig
from app.schemas.lakebridge import DatabricksConfigCreate, DatabricksConfigView

log = structlog.get_logger(__name__)


class DatabricksConfigService:
    """Service for managing per-project Databricks configurations.

    PAT is encrypted at rest using Fernet with project-scoped keys.
    The PAT is never included in API responses.
    """

    def __init__(self, session: Session):
        self._session = session
        self._crypto = get_crypto_service()

    def get_config(self, project_id: uuid.UUID) -> DatabricksConfig | None:
        """Get Databricks configuration for a project.

        Args:
            project_id: The project UUID

        Returns:
            DatabricksConfig if exists, None otherwise
        """
        stmt = select(DatabricksConfig).where(
            DatabricksConfig.project_id == project_id
        )
        return self._session.scalars(stmt).first()

    def get_config_or_raise(self, project_id: uuid.UUID) -> DatabricksConfig:
        """Get Databricks configuration or raise ValueError.

        Args:
            project_id: The project UUID

        Returns:
            DatabricksConfig

        Raises:
            ValueError: If config not found
        """
        config = self.get_config(project_id)
        if not config:
            raise ValueError(
                f"Databricks config not found for project '{project_id}'. "
                "Configure via POST /api/projects/{slug}/lakebridge/config"
            )
        return config

    def save_config(
        self,
        project_id: uuid.UUID,
        payload: DatabricksConfigCreate,
    ) -> DatabricksConfig:
        """Create or update Databricks configuration.

        If a config already exists for the project, it is updated.
        The PAT is encrypted before storage.

        Args:
            project_id: The project UUID
            payload: Configuration data with plaintext PAT

        Returns:
            Created or updated DatabricksConfig
        """
        encrypted_pat = self._encrypt_pat(project_id, payload.pat)

        existing = self.get_config(project_id)

        if existing:
            existing.workspace_url = payload.workspace_url
            existing.cli_profile = payload.cli_profile
            existing.pat_enc = encrypted_pat
            existing.catalog_name = payload.catalog_name
            existing.schema_name = payload.schema_name

            self._session.flush()

            log.info(
                "databricks_config_updated",
                project_id=str(project_id),
                workspace_url=payload.workspace_url,
            )

            return existing

        config = DatabricksConfig(
            id=uuid.uuid4(),
            project_id=project_id,
            workspace_url=payload.workspace_url,
            cli_profile=payload.cli_profile,
            pat_enc=encrypted_pat,
            catalog_name=payload.catalog_name,
            schema_name=payload.schema_name,
            enabled=True,
        )

        self._session.add(config)
        self._session.flush()

        log.info(
            "databricks_config_created",
            project_id=str(project_id),
            config_id=str(config.id),
            workspace_url=payload.workspace_url,
        )

        return config

    def delete_config(self, project_id: uuid.UUID) -> bool:
        """Delete Databricks configuration.

        Args:
            project_id: The project UUID

        Returns:
            True if deleted, False if not found
        """
        config = self.get_config(project_id)
        if not config:
            return False

        self._session.delete(config)
        self._session.flush()

        log.info(
            "databricks_config_deleted",
            project_id=str(project_id),
        )

        return True

    def toggle_enabled(
        self,
        project_id: uuid.UUID,
        enabled: bool,
    ) -> DatabricksConfig:
        """Enable or disable Databricks integration.

        Args:
            project_id: The project UUID
            enabled: New enabled state

        Returns:
            Updated DatabricksConfig

        Raises:
            ValueError: If config not found
        """
        config = self.get_config_or_raise(project_id)

        config.enabled = enabled
        self._session.flush()

        log.info(
            "databricks_config_toggled",
            project_id=str(project_id),
            enabled=enabled,
        )

        return config

    def decrypt_pat(self, config: DatabricksConfig) -> str:
        """Decrypt PAT for CLI invocation.

        WARNING: Returns plaintext PAT. Only use internally for
        executing Lakebridge CLI commands. Never expose via API.

        Args:
            config: The DatabricksConfig with encrypted PAT

        Returns:
            Plaintext PAT string
        """
        data = self._crypto.decrypt_or_parse_json(
            config.project_id, config.pat_enc
        )
        return data.get("pat", "")

    def to_view(self, config: DatabricksConfig) -> DatabricksConfigView:
        """Convert config to API view (PAT excluded)."""
        return DatabricksConfigView(
            id=config.id,
            project_id=config.project_id,
            workspace_url=config.workspace_url,
            cli_profile=config.cli_profile,
            catalog_name=config.catalog_name,
            schema_name=config.schema_name,
            enabled=config.enabled,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )

    def _encrypt_pat(self, project_id: uuid.UUID, pat: str) -> str:
        """Encrypt PAT for storage.

        Uses Fernet with project-scoped key derivation.
        Falls back to plain JSON if encryption key not configured.
        """
        return self._crypto.encrypt_or_json(project_id, {"pat": pat})
