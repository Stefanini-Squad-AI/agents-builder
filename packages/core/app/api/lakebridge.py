"""Lakebridge Integration API — Databricks config and job management.

Phase 1b Endpoints (Config):
- GET    /api/projects/{project_ref}/lakebridge/config       Get config
- POST   /api/projects/{project_ref}/lakebridge/config       Create/update config
- DELETE /api/projects/{project_ref}/lakebridge/config       Delete config
- PATCH  /api/projects/{project_ref}/lakebridge/config/toggle  Toggle enabled

Phase 1c Endpoints (Prerequisites):
- GET    /api/projects/{project_ref}/lakebridge/prerequisites  Check CLI prerequisites

Phase 1d Endpoints (Analyzer & Jobs):
- POST   /api/projects/{project_ref}/lakebridge/analyze        Start analyzer
- GET    /api/projects/{project_ref}/lakebridge/analyze/summary  Get analysis summary
- GET    /api/projects/{project_ref}/lakebridge/jobs           List jobs
- GET    /api/projects/{project_ref}/lakebridge/jobs/{job_id}  Get job detail
- POST   /api/projects/{project_ref}/lakebridge/jobs/{job_id}/cancel  Cancel job

Phase 2 Endpoints (Transpiler):
- POST   /api/projects/{project_ref}/lakebridge/transpile        Start transpiler
- GET    /api/projects/{project_ref}/lakebridge/transpile/status  Get transpilation status

Phase 3 Endpoints (Reconciler):
- POST   /api/projects/{project_ref}/lakebridge/reconcile        Start reconciler
- GET    /api/projects/{project_ref}/lakebridge/reconcile/summary  Get reconciliation summary
- GET    /api/projects/{project_ref}/lakebridge/reconcile/status   Get reconciliation status
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.projects import Project, ProjectArtifact
from app.enums import ArtifactKind, LakebridgeJobStatus
from app.schemas.lakebridge import (
    AnalyzeRequest,
    AnalyzerSummaryView,
    DatabricksConfigCreate,
    DatabricksConfigToggle,
    DatabricksConfigView,
    LakebridgeJobView,
    PrerequisitesView,
    ReconcileRequest,
    ReconcileStatusView,
    ReconcileSummaryView,
    TranspileRequest,
    TranspileStatusView,
)
from app.services.databricks_config_service import DatabricksConfigService
from app.services.lakebridge_cli_client import LakebridgeCLIClient, get_cli_client
from app.services.lakebridge_job_service import LakebridgeJobService

router = APIRouter(tags=["Lakebridge"])


# -----------------------------------------------------------------------------
# Helper: Resolve project by UUID or slug
# -----------------------------------------------------------------------------


def _get_project_by_ref(session: Session, project_ref: str) -> Project | None:
    """Fetch project by UUID or slug."""
    try:
        project_uuid = uuid.UUID(project_ref)
        return session.get(Project, project_uuid)
    except ValueError:
        pass

    return session.execute(
        select(Project).where(Project.slug == project_ref)
    ).scalar_one_or_none()


def _get_project_or_404(session: Session, project_ref: str) -> Project:
    """Get project or raise 404."""
    project = _get_project_by_ref(session, project_ref)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_ref}' not found",
        )
    return project


# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------


def get_config_service(
    session: Session = Depends(get_session),
) -> DatabricksConfigService:
    """Dependency to get the Databricks config service."""
    return DatabricksConfigService(session)


def get_job_service(
    session: Session = Depends(get_session),
) -> LakebridgeJobService:
    """Dependency to get the Lakebridge job service."""
    return LakebridgeJobService(session)


# -----------------------------------------------------------------------------
# Phase 1b: Databricks Config Endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/api/projects/{project_ref}/lakebridge/config",
    response_model=DatabricksConfigView | None,
    summary="Get Databricks configuration",
)
def get_databricks_config(
    project_ref: str,
    session: Session = Depends(get_session),
    service: DatabricksConfigService = Depends(get_config_service),
) -> DatabricksConfigView | None:
    """Get Databricks workspace configuration for a project.

    Returns None if not configured. PAT is never included in the response.
    """
    project = _get_project_or_404(session, project_ref)
    config = service.get_config(project.id)

    if not config:
        return None

    return service.to_view(config)


@router.post(
    "/api/projects/{project_ref}/lakebridge/config",
    response_model=DatabricksConfigView,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update Databricks configuration",
)
def save_databricks_config(
    project_ref: str,
    payload: DatabricksConfigCreate,
    session: Session = Depends(get_session),
    service: DatabricksConfigService = Depends(get_config_service),
) -> DatabricksConfigView:
    """Create or update Databricks workspace configuration.

    The PAT is encrypted before storage and never returned in responses.
    If a config already exists, it is updated (upsert behavior).
    """
    project = _get_project_or_404(session, project_ref)
    config = service.save_config(project.id, payload)
    return service.to_view(config)


@router.delete(
    "/api/projects/{project_ref}/lakebridge/config",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Databricks configuration",
)
def delete_databricks_config(
    project_ref: str,
    session: Session = Depends(get_session),
    service: DatabricksConfigService = Depends(get_config_service),
) -> None:
    """Delete Databricks workspace configuration.

    This also cascades to delete all Lakebridge jobs for the project.
    """
    project = _get_project_or_404(session, project_ref)
    deleted = service.delete_config(project.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Databricks config not found",
        )


@router.patch(
    "/api/projects/{project_ref}/lakebridge/config/toggle",
    response_model=DatabricksConfigView,
    summary="Toggle Databricks integration enabled state",
)
def toggle_databricks_config(
    project_ref: str,
    payload: DatabricksConfigToggle,
    session: Session = Depends(get_session),
    service: DatabricksConfigService = Depends(get_config_service),
) -> DatabricksConfigView:
    """Enable or disable Lakebridge integration without deleting the config.

    When disabled, all Lakebridge operations will return an error.
    """
    project = _get_project_or_404(session, project_ref)

    try:
        config = service.toggle_enabled(project.id, payload.enabled)
        return service.to_view(config)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# -----------------------------------------------------------------------------
# Phase 1c: Prerequisites Check Endpoint
# -----------------------------------------------------------------------------


@router.get(
    "/api/projects/{project_ref}/lakebridge/prerequisites",
    response_model=PrerequisitesView,
    summary="Check Lakebridge CLI prerequisites",
)
async def check_prerequisites(
    project_ref: str,
    session: Session = Depends(get_session),
    service: DatabricksConfigService = Depends(get_config_service),
) -> PrerequisitesView:
    """Check if Lakebridge CLI prerequisites are met.

    Validates:
    - Databricks CLI is installed
    - Lakebridge extension is installed
    - Workspace is reachable with configured PAT

    Returns all checks as false if no Databricks config exists.
    """
    project = _get_project_or_404(session, project_ref)
    config = service.get_config(project.id)

    decrypted_pat: str | None = None
    if config:
        decrypted_pat = service.decrypt_pat(config)

    cli_client = get_cli_client()
    return await cli_client.check_all_prerequisites(config, decrypted_pat)


# -----------------------------------------------------------------------------
# Phase 1d: Analyzer & Jobs Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/api/projects/{project_ref}/lakebridge/analyze",
    response_model=LakebridgeJobView,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Lakebridge analyzer job",
)
def start_analyzer(
    project_ref: str,
    payload: AnalyzeRequest,
    session: Session = Depends(get_session),
    config_service: DatabricksConfigService = Depends(get_config_service),
    job_service: LakebridgeJobService = Depends(get_job_service),
) -> LakebridgeJobView:
    """Start a new Lakebridge analyzer job.

    The job runs in the background. Poll GET /jobs/{id} for status.

    If artifact_ids is None, analyzes all artifacts in the code_to_be_migrated group.
    """
    project = _get_project_or_404(session, project_ref)

    config = config_service.get_config(project.id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Databricks config not found. Configure via POST /lakebridge/config first.",
        )

    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Databricks integration is disabled. Enable via PATCH /lakebridge/config/toggle.",
        )

    if payload.artifact_ids:
        artifact_ids = payload.artifact_ids
    else:
        artifact_ids = _get_migratable_artifact_ids(session, project.id)

    if not artifact_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No artifacts found to analyze. Upload artifacts first.",
        )

    cli_command = _build_analyzer_command(
        source_dialect=payload.source_dialect,
        config=config,
    )

    job = job_service.create_analyzer_job(
        project_id=project.id,
        source_dialect=payload.source_dialect,
        input_artifact_ids=artifact_ids,
        cli_command=cli_command,
        metadata={"requested_by": "api"},
    )

    job_service.start_job(job.id)

    return job_service.to_view(job)


@router.get(
    "/api/projects/{project_ref}/lakebridge/analyze/summary",
    response_model=AnalyzerSummaryView | None,
    summary="Get latest analyzer summary",
)
def get_analyzer_summary(
    project_ref: str,
    session: Session = Depends(get_session),
    job_service: LakebridgeJobService = Depends(get_job_service),
) -> AnalyzerSummaryView | None:
    """Get summary of the most recent completed analyzer run.

    Returns None if no analyzer has been run yet.
    """
    project = _get_project_or_404(session, project_ref)
    return job_service.get_analyzer_summary(project.id)


@router.get(
    "/api/projects/{project_ref}/lakebridge/jobs",
    response_model=list[LakebridgeJobView],
    summary="List Lakebridge jobs",
)
def list_jobs(
    project_ref: str,
    status_filter: LakebridgeJobStatus | None = None,
    limit: int = 50,
    session: Session = Depends(get_session),
    job_service: LakebridgeJobService = Depends(get_job_service),
) -> list[LakebridgeJobView]:
    """List Lakebridge jobs for a project.

    Results are sorted by creation date descending (newest first).
    """
    project = _get_project_or_404(session, project_ref)
    jobs = job_service.list_jobs(
        project_id=project.id,
        status=status_filter,
        limit=min(limit, 100),
    )
    return [job_service.to_view(j) for j in jobs]


@router.get(
    "/api/projects/{project_ref}/lakebridge/jobs/{job_id}",
    response_model=LakebridgeJobView,
    summary="Get Lakebridge job details",
)
def get_job(
    project_ref: str,
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
    job_service: LakebridgeJobService = Depends(get_job_service),
) -> LakebridgeJobView:
    """Get details of a specific Lakebridge job."""
    project = _get_project_or_404(session, project_ref)
    job = job_service.get_job(job_id)

    if not job or job.project_id != project.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )

    return job_service.to_view(job)


@router.post(
    "/api/projects/{project_ref}/lakebridge/jobs/{job_id}/cancel",
    response_model=LakebridgeJobView,
    summary="Cancel a Lakebridge job",
)
def cancel_job(
    project_ref: str,
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
    job_service: LakebridgeJobService = Depends(get_job_service),
) -> LakebridgeJobView:
    """Cancel a pending or running job.

    Cannot cancel completed, failed, or already cancelled jobs.
    """
    project = _get_project_or_404(session, project_ref)
    job = job_service.get_job(job_id)

    if not job or job.project_id != project.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )

    try:
        job = job_service.cancel_job(job_id)
        return job_service.to_view(job)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# -----------------------------------------------------------------------------
# Phase 2: Transpiler Endpoints
# -----------------------------------------------------------------------------


VALID_TRANSPILERS = {"bladebridge", "morpheus", "switch"}


@router.post(
    "/api/projects/{project_ref}/lakebridge/transpile",
    response_model=LakebridgeJobView,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Lakebridge transpiler job",
)
def start_transpiler(
    project_ref: str,
    payload: TranspileRequest,
    session: Session = Depends(get_session),
    config_service: DatabricksConfigService = Depends(get_config_service),
    job_service: LakebridgeJobService = Depends(get_job_service),
) -> LakebridgeJobView:
    """Start a new Lakebridge transpiler job.

    The job runs in the background. Poll GET /jobs/{id} for status.

    Transpilers:
    - bladebridge: Simple SQL translations
    - morpheus: Complex transformations, stored procedures → Python notebooks
    - switch: ETL packages (SSIS, Informatica) → Databricks workflows
    """
    project = _get_project_or_404(session, project_ref)

    if payload.transpiler.lower() not in VALID_TRANSPILERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transpiler: {payload.transpiler}. "
                   f"Must be one of: {', '.join(sorted(VALID_TRANSPILERS))}",
        )

    config = config_service.get_config(project.id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Databricks config not found. Configure via POST /lakebridge/config first.",
        )

    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Databricks integration is disabled. Enable via PATCH /lakebridge/config/toggle.",
        )

    if payload.artifact_ids:
        artifact_ids = payload.artifact_ids
    else:
        artifact_ids = _get_migratable_artifact_ids(session, project.id)

    if not artifact_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No artifacts found to transpile. Upload artifacts first.",
        )

    cli_command = _build_transpiler_command(
        source_dialect=payload.source_dialect,
        transpiler=payload.transpiler,
        config=config,
        skip_validation=payload.skip_validation,
    )

    job = job_service.create_transpiler_job(
        project_id=project.id,
        source_dialect=payload.source_dialect,
        transpiler=payload.transpiler.lower(),
        input_artifact_ids=artifact_ids,
        cli_command=cli_command,
        skip_validation=payload.skip_validation,
        options=payload.options,
    )

    job_service.start_transpiler_job(job.id)

    return job_service.to_view(job)


@router.get(
    "/api/projects/{project_ref}/lakebridge/transpile/status",
    response_model=TranspileStatusView,
    summary="Get transpilation status overview",
)
def get_transpile_status(
    project_ref: str,
    session: Session = Depends(get_session),
    job_service: LakebridgeJobService = Depends(get_job_service),
) -> TranspileStatusView:
    """Get overview of transpilation progress for a project.

    Shows counts of transpiled, failed, and pending artifacts,
    plus info about the latest transpiler job.
    """
    project = _get_project_or_404(session, project_ref)
    return job_service.get_transpile_status(project.id)


# -----------------------------------------------------------------------------
# Phase 3: Reconciler Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/api/projects/{project_ref}/lakebridge/reconcile",
    response_model=LakebridgeJobView,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Lakebridge reconciler job",
)
def start_reconciler(
    project_ref: str,
    payload: ReconcileRequest,
    session: Session = Depends(get_session),
    config_service: DatabricksConfigService = Depends(get_config_service),
    job_service: LakebridgeJobService = Depends(get_job_service),
) -> LakebridgeJobView:
    """Start a new Lakebridge reconciliation job.

    Compares execution results between source code and transpiled code:
    - Row counts
    - Schema compatibility
    - Sample data comparison

    The job runs in the background. Poll GET /jobs/{id} for status.
    """
    project = _get_project_or_404(session, project_ref)

    config = config_service.get_config(project.id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Databricks config not found. Configure via POST /lakebridge/config first.",
        )

    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Databricks integration is disabled. Enable via PATCH /lakebridge/config/toggle.",
        )

    _validate_artifacts_exist(session, project.id, payload.source_artifact_ids, "source")
    _validate_artifacts_exist(session, project.id, payload.transpiled_artifact_ids, "transpiled")

    cli_command = _build_reconciler_command(
        source_dialect=payload.source_dialect,
        source_connection=payload.source_connection,
        config=config,
        sample_size=payload.sample_size,
        tolerance=payload.tolerance,
    )

    job = job_service.create_reconciler_job(
        project_id=project.id,
        source_dialect=payload.source_dialect,
        source_artifact_ids=payload.source_artifact_ids,
        transpiled_artifact_ids=payload.transpiled_artifact_ids,
        source_connection=payload.source_connection,
        cli_command=cli_command,
        sample_size=payload.sample_size,
        tolerance=payload.tolerance,
        tables=payload.tables,
    )

    job_service.start_reconciler_job(job.id)

    return job_service.to_view(job)


@router.get(
    "/api/projects/{project_ref}/lakebridge/reconcile/summary",
    response_model=ReconcileSummaryView | None,
    summary="Get latest reconciliation summary",
)
def get_reconcile_summary(
    project_ref: str,
    session: Session = Depends(get_session),
    job_service: LakebridgeJobService = Depends(get_job_service),
) -> ReconcileSummaryView | None:
    """Get detailed results from the most recent completed reconciliation.

    Returns None if no reconciler has been run yet.
    Includes per-table pass/fail status and discrepancy details.
    """
    project = _get_project_or_404(session, project_ref)
    return job_service.get_reconcile_summary(project.id)


@router.get(
    "/api/projects/{project_ref}/lakebridge/reconcile/status",
    response_model=ReconcileStatusView,
    summary="Get reconciliation status overview",
)
def get_reconcile_status(
    project_ref: str,
    session: Session = Depends(get_session),
    job_service: LakebridgeJobService = Depends(get_job_service),
) -> ReconcileStatusView:
    """Get overview of reconciliation job history.

    Shows counts of successful/failed jobs and latest job status.
    """
    project = _get_project_or_404(session, project_ref)
    return job_service.get_reconcile_status(project.id)


# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------


def _get_migratable_artifact_ids(
    session: Session,
    project_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Get artifact IDs for analysis.

    Returns artifacts that are:
    - In the project
    - Have code-related kinds (sql, dtsx, etc.)
    """
    migratable_kinds = [
        ArtifactKind.CODE.value,
        ArtifactKind.SSIS_PACKAGE.value,
        ArtifactKind.SQL_SCRIPT.value,
    ]

    stmt = (
        select(ProjectArtifact.id)
        .where(
            ProjectArtifact.project_id == project_id,
            ProjectArtifact.kind.in_(migratable_kinds),
        )
    )

    return list(session.scalars(stmt).all())


def _build_analyzer_command(
    source_dialect: str,
    config,
) -> str:
    """Build CLI command string for logging/display.

    Note: Actual execution uses separate args, not this string.
    """
    return (
        f"databricks labs lakebridge analyze "
        f"--source {source_dialect} "
        f"--catalog {config.catalog_name} "
        f"--schema {config.schema_name}"
    )


def _build_transpiler_command(
    source_dialect: str,
    transpiler: str,
    config,
    skip_validation: bool = False,
) -> str:
    """Build transpiler CLI command string for logging/display.

    Note: Actual execution uses separate args, not this string.
    """
    cmd = (
        f"databricks labs lakebridge transpile "
        f"--source {source_dialect} "
        f"--transpiler {transpiler} "
        f"--catalog {config.catalog_name} "
        f"--schema {config.schema_name}"
    )
    if skip_validation:
        cmd += " --skip-validation"
    return cmd


def _build_reconciler_command(
    source_dialect: str,
    source_connection: str,
    config,
    sample_size: int = 1000,
    tolerance: float = 0.0,
) -> str:
    """Build reconciler CLI command string for logging/display.

    Note: Actual execution uses separate args, not this string.
    """
    cmd = (
        f"databricks labs lakebridge reconcile "
        f"--source {source_dialect} "
        f"--source-connection <masked> "
        f"--catalog {config.catalog_name} "
        f"--schema {config.schema_name} "
        f"--sample-size {sample_size}"
    )
    if tolerance > 0:
        cmd += f" --tolerance {tolerance}"
    return cmd


def _validate_artifacts_exist(
    session: Session,
    project_id: uuid.UUID,
    artifact_ids: list[uuid.UUID],
    artifact_type: str,
) -> None:
    """Validate that all artifact IDs exist and belong to the project.

    Args:
        session: Database session
        project_id: Project UUID
        artifact_ids: List of artifact UUIDs to validate
        artifact_type: Description for error messages (e.g., "source", "transpiled")

    Raises:
        HTTPException: If any artifact is not found or doesn't belong to project
    """
    for aid in artifact_ids:
        artifact = session.get(ProjectArtifact, aid)
        if not artifact:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{artifact_type.capitalize()} artifact not found: {aid}",
            )
        if artifact.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{artifact_type.capitalize()} artifact {aid} does not belong to this project",
            )
