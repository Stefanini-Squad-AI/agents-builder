"""`run_lakebridge_analyzer` Dramatiq actor.

Executes Lakebridge analyzer CLI in background:

  1. Load job from DB
  2. Prepare input files (copy artifacts to temp dir)
  3. Execute CLI command
  4. Store output as artifact
  5. Update job status
  6. Import results into ETLPackages (Workshop integration)

State transitions:
  - RUNNING → COMPLETED (CLI exit 0)
  - RUNNING → FAILED (CLI exit != 0 or exception)
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import uuid
from pathlib import Path

import dramatiq
import structlog
from sqlalchemy import select

from app.db import session_scope
from app.domain import register_models
from app.domain.lakebridge import DatabricksConfig, LakebridgeJob
from app.domain.projects import ProjectArtifact
from app.enums import ArtifactKind, LakebridgeJobStatus
from app.services.databricks_config_service import DatabricksConfigService
from app.services.lakebridge_cli_client import LakebridgeCLIClient
from app.services.lakebridge_job_service import LakebridgeJobService
from app.services.lakebridge_matching import select_output_file
from app.storage import resolve_artifact_path

register_models()

log = structlog.get_logger(__name__)


@dramatiq.actor(queue_name="default", max_retries=0, time_limit=600_000)
def run_lakebridge_analyzer(job_id: str) -> None:
    """Execute Lakebridge analyzer in background.

    Time-limited to 10 minutes for large codebases.

    Args:
        job_id: LakebridgeJob UUID as string
    """
    jid = uuid.UUID(job_id)
    log.info("lakebridge_analyzer_start", job_id=job_id)

    with session_scope() as session:
        job = session.get(LakebridgeJob, jid)
        if not job:
            log.error("lakebridge_analyzer_job_not_found", job_id=job_id)
            return

        if job.status != LakebridgeJobStatus.RUNNING.value:
            log.warning(
                "lakebridge_analyzer_wrong_status",
                job_id=job_id,
                status=job.status,
            )
            return

        project_id = job.project_id
        source_dialect = job.source_dialect
        input_artifact_ids = job.input_artifact_ids

    config, decrypted_pat = _load_config(project_id)
    if not config or not decrypted_pat:
        _mark_failed(jid, "Databricks config not found or disabled")
        return

    with tempfile.TemporaryDirectory(prefix="lakebridge_") as tmpdir:
        tmpdir_path = Path(tmpdir)
        input_dir = tmpdir_path / "input"
        output_dir = tmpdir_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        try:
            _prepare_input_files(input_artifact_ids, input_dir)
        except Exception as e:
            log.exception("lakebridge_analyzer_input_error", job_id=job_id)
            _mark_failed(jid, f"Failed to prepare input files: {e}")
            return

        cli = LakebridgeCLIClient(timeout_seconds=540)

        try:
            result = asyncio.run(
                cli.run_analyzer(
                    source_dialect=source_dialect,
                    input_path=str(input_dir),
                    output_path=str(output_dir),
                    workspace_url=config.workspace_url,
                    pat=decrypted_pat,
                    catalog=config.catalog_name,
                    schema=config.schema_name,
                )
            )
        except Exception as e:
            log.exception("lakebridge_analyzer_cli_error", job_id=job_id)
            _mark_failed(jid, f"CLI execution error: {e}")
            return

        output_file = select_output_file(
            output_dir, prefer_keywords=("analy", "report", "summary")
        )

        # Everything after the CLI returns is wrapped so that any failure
        # (decode error, DB error, etc.) marks the job FAILED instead of
        # leaving it stuck in RUNNING forever.
        try:
            if result.success and output_file:
                content = output_file.read_text(encoding="utf-8", errors="replace")

                persisted = False
                artifact_id: uuid.UUID | None = None
                with session_scope() as session:
                    job_service = LakebridgeJobService(session)

                    current = job_service.get_job(jid)
                    if not current or current.status != LakebridgeJobStatus.RUNNING.value:
                        log.info(
                            "lakebridge_analyzer_skip_persist",
                            job_id=job_id,
                            status=current.status if current else None,
                        )
                    else:
                        artifact = job_service.create_result_artifact(
                            project_id=project_id,
                            job_id=jid,
                            content=content,
                            filename="analyzer_report.json",
                            kind=ArtifactKind.ANALYZER_REPORT,
                        )
                        artifact_id = artifact.id

                        job_service.complete_job(
                            job_id=jid,
                            exit_code=result.exit_code,
                            stdout=result.stdout,
                            stderr=result.stderr,
                            duration_ms=result.duration_ms,
                            result_artifact_id=artifact.id,
                        )
                        persisted = True

                if persisted:
                    log.info(
                        "lakebridge_analyzer_done",
                        job_id=job_id,
                        duration_ms=result.duration_ms,
                        artifact_id=str(artifact_id),
                    )
                    _integrate_with_workshop(jid)

            elif result.success and not output_file:
                with session_scope() as session:
                    job_service = LakebridgeJobService(session)
                    job_service.complete_job(
                        job_id=jid,
                        exit_code=result.exit_code,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        duration_ms=result.duration_ms,
                        result_artifact_id=None,
                    )

                log.warning(
                    "lakebridge_analyzer_no_output",
                    job_id=job_id,
                    duration_ms=result.duration_ms,
                )

            else:
                error_msg = result.stderr[:500] if result.stderr else f"Exit code: {result.exit_code}"
                _mark_failed(
                    jid,
                    error_msg,
                    exit_code=result.exit_code,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    duration_ms=result.duration_ms,
                )
        except Exception as e:
            log.exception("lakebridge_analyzer_persist_error", job_id=job_id)
            _mark_failed(
                jid,
                f"Post-processing error: {e}",
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=result.duration_ms,
            )


def _load_config(project_id: uuid.UUID) -> tuple[DatabricksConfig | None, str | None]:
    """Load Databricks config and decrypt PAT.

    Args:
        project_id: Project UUID

    Returns:
        (config, decrypted_pat) or (None, None) if not configured
    """
    with session_scope() as session:
        config_service = DatabricksConfigService(session)
        config = config_service.get_config(project_id)

        if not config or not config.enabled:
            return None, None

        decrypted_pat = config_service.decrypt_pat(config)
        
        return config, decrypted_pat


def _prepare_input_files(artifact_ids: list[str], input_dir: Path) -> None:
    """Copy input artifacts to temp directory.

    Args:
        artifact_ids: List of artifact UUIDs as strings
        input_dir: Directory to copy files to
    """
    with session_scope() as session:
        for aid_str in artifact_ids:
            aid = uuid.UUID(aid_str)
            artifact = session.get(ProjectArtifact, aid)

            if not artifact:
                log.warning("lakebridge_analyzer_artifact_not_found", artifact_id=aid_str)
                continue

            src_path = resolve_artifact_path(artifact.path)
            if not src_path.exists():
                log.warning(
                    "lakebridge_analyzer_artifact_file_missing",
                    artifact_id=aid_str,
                    path=str(src_path),
                )
                continue

            dst_path = input_dir / artifact.filename
            counter = 1
            while dst_path.exists():
                stem = Path(artifact.filename).stem
                suffix = Path(artifact.filename).suffix
                dst_path = input_dir / f"{stem}_{counter}{suffix}"
                counter += 1

            shutil.copy2(src_path, dst_path)

            log.debug(
                "lakebridge_analyzer_file_copied",
                artifact_id=aid_str,
                dst=str(dst_path),
            )


def _mark_failed(
    job_id: uuid.UUID,
    error: str,
    exit_code: int | None = None,
    stdout: str | None = None,
    stderr: str | None = None,
    duration_ms: int | None = None,
) -> None:
    """Mark job as failed.

    Args:
        job_id: Job UUID
        error: Error message
        exit_code: Optional CLI exit code
        stdout: Optional stdout
        stderr: Optional stderr
        duration_ms: Optional duration
    """
    with session_scope() as session:
        job_service = LakebridgeJobService(session)
        job_service.fail_job(
            job_id=job_id,
            error_message=error,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
        )

    log.warning(
        "lakebridge_analyzer_failed",
        job_id=str(job_id),
        error=error[:200],
    )


def _integrate_with_workshop(job_id: uuid.UUID) -> None:
    """Import analyzer results into Workshop's ETLPackage model.

    This bridges Lakebridge outputs with the Workshop's structured
    migration workflow. Non-fatal if integration fails.

    Args:
        job_id: Completed LakebridgeJob UUID
    """
    try:
        with session_scope() as session:
            from app.services.lakebridge_integration_service import (
                LakebridgeIntegrationService,
            )

            integration_service = LakebridgeIntegrationService(session)
            updated_packages = integration_service.import_analyzer_results(job_id)

            log.info(
                "lakebridge_analyzer_integrated",
                job_id=str(job_id),
                packages_updated=len(updated_packages),
            )
    except Exception as e:
        log.warning(
            "lakebridge_integration_failed",
            job_id=str(job_id),
            error=str(e),
        )
