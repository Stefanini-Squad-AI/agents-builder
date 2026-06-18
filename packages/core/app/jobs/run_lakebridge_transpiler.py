"""`run_lakebridge_transpiler` Dramatiq actor.

Executes Lakebridge transpiler CLI in background:

  1. Load job from DB
  2. Prepare input files (copy artifacts to temp dir)
  3. Execute CLI: databricks labs lakebridge transpile ...
  4. Collect output files (may be multiple)
  5. Create artifacts for each output file
  6. Update job status with source→output mapping

State transitions:
  - RUNNING → COMPLETED (CLI exit 0, outputs created)
  - RUNNING → FAILED (CLI exit != 0 or exception)
"""

from __future__ import annotations

import asyncio
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
from app.services.lakebridge_matching import match_filename
from app.storage import resolve_artifact_path

register_models()

log = structlog.get_logger(__name__)


@dramatiq.actor(queue_name="default", max_retries=0, time_limit=900_000)
def run_lakebridge_transpiler(job_id: str) -> None:
    """Execute Lakebridge transpiler in background.

    Time-limited to 15 minutes for large codebases.

    Args:
        job_id: LakebridgeJob UUID as string
    """
    jid = uuid.UUID(job_id)
    log.info("lakebridge_transpiler_start", job_id=job_id)

    with session_scope() as session:
        job = session.get(LakebridgeJob, jid)
        if not job:
            log.error("lakebridge_transpiler_job_not_found", job_id=job_id)
            return

        if job.status != LakebridgeJobStatus.RUNNING.value:
            log.warning(
                "lakebridge_transpiler_wrong_status",
                job_id=job_id,
                status=job.status,
            )
            return

        project_id = job.project_id
        source_dialect = job.source_dialect
        transpiler = job.transpiler or "bladebridge"
        input_artifact_ids = job.input_artifact_ids
        skip_validation = job.metadata_json.get("skip_validation", False)

    config, decrypted_pat = _load_config(project_id)
    if not config or not decrypted_pat:
        _mark_failed(jid, "Databricks config not found or disabled")
        return

    with tempfile.TemporaryDirectory(prefix="lakebridge_transpile_") as tmpdir:
        tmpdir_path = Path(tmpdir)
        input_dir = tmpdir_path / "input"
        output_dir = tmpdir_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        try:
            source_file_map = _prepare_input_files(input_artifact_ids, input_dir)
        except Exception as e:
            log.exception("lakebridge_transpiler_input_error", job_id=job_id)
            _mark_failed(jid, f"Failed to prepare input files: {e}")
            return

        cli = LakebridgeCLIClient(timeout_seconds=840)

        extra_args = []
        if skip_validation:
            extra_args.append("--skip-validation")

        try:
            result = asyncio.run(
                cli.run_transpiler(
                    source_dialect=source_dialect,
                    transpiler=transpiler,
                    input_path=str(input_dir),
                    output_path=str(output_dir),
                    workspace_url=config.workspace_url,
                    pat=decrypted_pat,
                    catalog=config.catalog_name,
                    schema=config.schema_name,
                    extra_args=extra_args if extra_args else None,
                )
            )
        except Exception as e:
            log.exception("lakebridge_transpiler_cli_error", job_id=job_id)
            _mark_failed(jid, f"CLI execution error: {e}")
            return

        output_files = list(output_dir.rglob("*"))
        output_files = [f for f in output_files if f.is_file()]

        # Wrap post-CLI handling so a crash here marks the job FAILED rather
        # than leaving it stuck in RUNNING.
        try:
            if result.success and output_files:
                output_count = len(output_files)
                persisted = False
                with session_scope() as session:
                    job_service = LakebridgeJobService(session)

                    current = job_service.get_job(jid)
                    if not current or current.status != LakebridgeJobStatus.RUNNING.value:
                        log.info(
                            "lakebridge_transpiler_skip_persist",
                            job_id=job_id,
                            status=current.status if current else None,
                        )
                    else:
                        source_to_output: dict[str, str] = {}
                        output_artifact_ids: list[str] = []

                        for output_file in output_files:
                            content = output_file.read_text(encoding="utf-8", errors="replace")
                            rel_name = output_file.relative_to(output_dir)

                            source_artifact_id = _match_output_to_source(
                                output_file.name,
                                source_file_map,
                            )

                            artifact = job_service.create_result_artifact(
                                project_id=project_id,
                                job_id=jid,
                                content=content,
                                filename=str(rel_name),
                                kind=ArtifactKind.TRANSPILED_CODE,
                            )

                            output_artifact_ids.append(str(artifact.id))

                            if source_artifact_id:
                                source_to_output[source_artifact_id] = str(artifact.id)

                        job_service.update_job_metadata(
                            job_id=jid,
                            updates={
                                "source_to_output_map": source_to_output,
                                "output_artifacts": output_artifact_ids,
                                "output_file_count": output_count,
                            },
                        )

                        first_artifact_id = (
                            uuid.UUID(output_artifact_ids[0]) if output_artifact_ids else None
                        )

                        job_service.complete_job(
                            job_id=jid,
                            exit_code=result.exit_code,
                            stdout=result.stdout,
                            stderr=result.stderr,
                            duration_ms=result.duration_ms,
                            result_artifact_id=first_artifact_id,
                        )
                        persisted = True

                if persisted:
                    log.info(
                        "lakebridge_transpiler_done",
                        job_id=job_id,
                        duration_ms=result.duration_ms,
                        output_count=output_count,
                    )

            elif result.success and not output_files:
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
                    "lakebridge_transpiler_no_output",
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
            log.exception("lakebridge_transpiler_persist_error", job_id=job_id)
            _mark_failed(
                jid,
                f"Post-processing error: {e}",
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=result.duration_ms,
            )


def _load_config(project_id: uuid.UUID) -> tuple[DatabricksConfig | None, str | None]:
    """Load Databricks config and decrypt PAT."""
    with session_scope() as session:
        config_service = DatabricksConfigService(session)
        config = config_service.get_config(project_id)

        if not config or not config.enabled:
            return None, None

        decrypted_pat = config_service.decrypt_pat(config)
        return config, decrypted_pat


def _prepare_input_files(
    artifact_ids: list[str],
    input_dir: Path,
) -> dict[str, str]:
    """Copy input artifacts to temp directory.

    Args:
        artifact_ids: List of artifact UUIDs as strings
        input_dir: Directory to copy files to

    Returns:
        Mapping of filename → artifact_id for reverse lookup
    """
    source_file_map: dict[str, str] = {}

    with session_scope() as session:
        for aid_str in artifact_ids:
            aid = uuid.UUID(aid_str)
            artifact = session.get(ProjectArtifact, aid)

            if not artifact:
                log.warning("lakebridge_transpiler_artifact_not_found", artifact_id=aid_str)
                continue

            src_path = resolve_artifact_path(artifact.path)
            if not src_path.exists():
                log.warning(
                    "lakebridge_transpiler_artifact_file_missing",
                    artifact_id=aid_str,
                    path=str(src_path),
                )
                continue

            dst_filename = artifact.filename
            dst_path = input_dir / dst_filename
            counter = 1
            while dst_path.exists():
                stem = Path(artifact.filename).stem
                suffix = Path(artifact.filename).suffix
                dst_filename = f"{stem}_{counter}{suffix}"
                dst_path = input_dir / dst_filename
                counter += 1

            shutil.copy2(src_path, dst_path)
            source_file_map[dst_filename] = aid_str

            log.debug(
                "lakebridge_transpiler_file_copied",
                artifact_id=aid_str,
                dst=str(dst_path),
            )

    return source_file_map


def _match_output_to_source(
    output_filename: str,
    source_file_map: dict[str, str],
) -> str | None:
    """Try to match output file to its source artifact.

    Lakebridge typically preserves the base filename, so we look for
    partial matches.

    Args:
        output_filename: Name of the output file
        source_file_map: Mapping of input filename → artifact_id

    Returns:
        Source artifact ID if matched, None otherwise
    """
    matched_filename = match_filename(output_filename, source_file_map.keys())
    if matched_filename:
        return source_file_map[matched_filename]

    # Fall back to the single source only when there is exactly one.
    if len(source_file_map) == 1:
        return next(iter(source_file_map.values()))

    return None


def _mark_failed(
    job_id: uuid.UUID,
    error: str,
    exit_code: int | None = None,
    stdout: str | None = None,
    stderr: str | None = None,
    duration_ms: int | None = None,
) -> None:
    """Mark job as failed."""
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
        "lakebridge_transpiler_failed",
        job_id=str(job_id),
        error=error[:200],
    )
