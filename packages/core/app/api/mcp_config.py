"""MCP Configuration API — manage per-project MCP server configurations.

Endpoints:
- /projects/{project_id}/mcps - List/create MCP configs
- /projects/{project_id}/mcps/{config_id} - Get/update/delete config
- /projects/{project_id}/mcps/{config_id}/validate - Validate config
- /projects/{project_id}/mcps/{config_id}/toggle - Enable/disable
- /projects/{project_id}/mcps/export - Export to Cursor format
- /projects/{project_id}/mcps/export/preview - Preview export
- /mcp-catalog - List catalog entries
- /mcp-catalog/{key} - Get catalog entry details
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_session
from app.mcp_catalog.export import MCPExportService
from app.mcp_catalog.loader import get_catalog_loader, MCPCatalogLoader
from app.mcp_catalog.schema import MCPCatalogEntry, MCPCatalogView
from app.mcp_catalog.schemas import (
    CursorMCPConfig,
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

router = APIRouter(tags=["MCP Configuration"])


def get_service(session: Session = Depends(get_session)) -> MCPConfigService:
    """Dependency to get the MCP config service."""
    return MCPConfigService(session)


def get_loader() -> MCPCatalogLoader:
    """Dependency to get the MCP catalog loader."""
    return get_catalog_loader()


def get_export_service(session: Session = Depends(get_session)) -> MCPExportService:
    """Dependency to get the MCP export service."""
    return MCPExportService(session)


# -----------------------------------------------------------------------------
# Project MCP Configuration Endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/mcps",
    response_model=list[MCPConfigSummary],
    summary="List MCP configs for project",
)
def list_project_mcps(
    project_id: uuid.UUID,
    enabled_only: bool = False,
    service: MCPConfigService = Depends(get_service),
) -> list[MCPConfigSummary]:
    """List all MCP configurations for a project."""
    if enabled_only:
        configs = service.list_enabled_configs(project_id)
    else:
        configs = service.list_configs(project_id)

    return [service.to_summary(c) for c in configs]


@router.post(
    "/projects/{project_id}/mcps",
    response_model=MCPConfigView,
    status_code=status.HTTP_201_CREATED,
    summary="Add MCP config to project",
)
def create_project_mcp(
    project_id: uuid.UUID,
    payload: MCPConfigCreate,
    service: MCPConfigService = Depends(get_service),
) -> MCPConfigView:
    """Add an MCP server configuration to a project."""
    try:
        config = service.create_config(project_id, payload)
        return service.to_view(config)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/projects/{project_id}/mcps/{config_id}",
    response_model=MCPConfigView,
    summary="Get MCP config details",
)
def get_project_mcp(
    project_id: uuid.UUID,
    config_id: uuid.UUID,
    service: MCPConfigService = Depends(get_service),
) -> MCPConfigView:
    """Get details of a specific MCP configuration."""
    config = service.get_config(config_id)
    if not config or config.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP config '{config_id}' not found",
        )
    return service.to_view(config)


@router.patch(
    "/projects/{project_id}/mcps/{config_id}",
    response_model=MCPConfigView,
    summary="Update MCP config",
)
def update_project_mcp(
    project_id: uuid.UUID,
    config_id: uuid.UUID,
    payload: MCPConfigUpdate,
    service: MCPConfigService = Depends(get_service),
) -> MCPConfigView:
    """Update an existing MCP configuration."""
    config = service.get_config(config_id)
    if not config or config.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP config '{config_id}' not found",
        )

    try:
        updated = service.update_config(config_id, payload)
        return service.to_view(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/projects/{project_id}/mcps/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete MCP config",
)
def delete_project_mcp(
    project_id: uuid.UUID,
    config_id: uuid.UUID,
    service: MCPConfigService = Depends(get_service),
) -> None:
    """Remove an MCP configuration from a project."""
    config = service.get_config(config_id)
    if not config or config.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP config '{config_id}' not found",
        )

    service.delete_config(config_id)


@router.post(
    "/projects/{project_id}/mcps/{config_id}/validate",
    response_model=MCPConfigValidation,
    summary="Validate MCP config",
)
def validate_project_mcp(
    project_id: uuid.UUID,
    config_id: uuid.UUID,
    service: MCPConfigService = Depends(get_service),
) -> MCPConfigValidation:
    """Validate an MCP configuration against its catalog entry."""
    config = service.get_config(config_id)
    if not config or config.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP config '{config_id}' not found",
        )

    try:
        return service.validate_config(config_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/projects/{project_id}/mcps/{config_id}/toggle",
    response_model=MCPConfigView,
    summary="Toggle MCP config enabled state",
)
def toggle_project_mcp(
    project_id: uuid.UUID,
    config_id: uuid.UUID,
    payload: MCPConfigToggle,
    service: MCPConfigService = Depends(get_service),
) -> MCPConfigView:
    """Enable or disable an MCP configuration."""
    config = service.get_config(config_id)
    if not config or config.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP config '{config_id}' not found",
        )

    try:
        updated = service.toggle_enabled(config_id, payload.enabled)
        return service.to_view(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# -----------------------------------------------------------------------------
# MCP Export Endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/mcps/export/preview",
    response_model=MCPExportPreview,
    summary="Preview MCP export",
)
def preview_mcp_export(
    project_id: uuid.UUID,
    export_service: MCPExportService = Depends(get_export_service),
) -> MCPExportPreview:
    """Preview what will be included in the MCP export.

    Returns a summary without actual secrets, allowing the user
    to review before confirming the export.
    """
    return export_service.get_export_preview(project_id)


@router.get(
    "/projects/{project_id}/mcps/export",
    response_model=CursorMCPConfig,
    summary="Export MCP config as JSON",
    responses={
        200: {
            "description": "Cursor MCP configuration (contains secrets)",
            "headers": {
                "X-Contains-Secrets": {
                    "description": "Indicates response contains sensitive data",
                    "schema": {"type": "string"},
                }
            },
        }
    },
)
def export_mcp_config_json(
    project_id: uuid.UUID,
    export_service: MCPExportService = Depends(get_export_service),
) -> CursorMCPConfig:
    """Export MCP configuration as JSON object.

    WARNING: Response contains decrypted secrets.
    Use for programmatic access or UI preview.
    """
    return export_service.build_cursor_config(project_id)


@router.get(
    "/projects/{project_id}/mcps/export/download",
    summary="Download mcp.json file",
    response_class=Response,
    responses={
        200: {
            "description": "mcp.json file download (contains secrets)",
            "content": {"application/json": {}},
            "headers": {
                "Content-Disposition": {
                    "description": "File attachment header",
                    "schema": {"type": "string"},
                },
                "X-Contains-Secrets": {
                    "description": "Indicates response contains sensitive data",
                    "schema": {"type": "string"},
                },
            },
        }
    },
)
def download_mcp_config(
    project_id: uuid.UUID,
    export_service: MCPExportService = Depends(get_export_service),
) -> Response:
    """Download MCP configuration as mcp.json file.

    WARNING: Downloaded file contains decrypted secrets.
    Handle the file securely and do not commit to version control.
    """
    json_bytes = export_service.export_to_bytes(project_id)

    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=mcp.json",
            "X-Contains-Secrets": "true",
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
    )


# -----------------------------------------------------------------------------
# MCP Catalog Endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/mcp-catalog",
    response_model=list[MCPCatalogListItem],
    summary="List MCP catalog entries",
)
def list_mcp_catalog(
    category: str | None = None,
    loader: MCPCatalogLoader = Depends(get_loader),
) -> list[MCPCatalogListItem]:
    """List all available MCP server definitions from the catalog."""
    if category:
        entries = loader.list_by_category(category)
    else:
        entries = loader.list_entries()

    return [
        MCPCatalogListItem(
            key=e.key,
            name=e.name,
            description=e.description,
            vendor=e.vendor,
            category=e.category,
            requires_approval=e.requires_approval,
            has_secrets=e.has_secrets,
            tool_count=len(e.tools),
        )
        for e in entries
    ]


@router.get(
    "/mcp-catalog/{key}",
    response_model=MCPCatalogView,
    summary="Get MCP catalog entry details",
)
def get_mcp_catalog_entry(
    key: str,
    loader: MCPCatalogLoader = Depends(get_loader),
) -> MCPCatalogView:
    """Get detailed information about an MCP server from the catalog."""
    entry = loader.get_entry(key)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP '{key}' not found in catalog",
        )
    return MCPCatalogView.from_entry(entry)
