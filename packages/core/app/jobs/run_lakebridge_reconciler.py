"""`run_lakebridge_reconciler` Dramatiq actor.

Executes Lakebridge reconciler CLI in background:

  1. Load job from DB
  2. Prepare source and transpiled files
  3. Execute CLI: databricks labs lakebridge reconcile ...
  4. Parse JSON results
  5. Create artifact with results
  6. Update job status with reconciliation summary
  7. Import results into ReconciliationRun (Workshop integration)

State transitions:
  - RUNNING → COMPLETED (CLI exit 0, results parsed)
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
from app.services.lakebridge_cli_client import LakebridgeCLIClient, CLIResult
from app.services.lakebridge_job_service import LakebridgeJobService
from app.services.lakebridge_matching import select_output_file
from app.storage import resolve_artifact_path

register_models()

log = structlog.get_logger(__name__)


@dramatiq.actor(queue_name="default", max_retries=0, time_limit=1200_000)
def run_lakebridge_reconciler(job_id: str) -> None:
    """Execute Lakebridge reconciler in background.

    Time-limited to 20 minutes for large data comparisons.

    Args:
        job_id: LakebridgeJob UUID as string
    """
    jid = uuid.UUID(job_id)
    log.info("lakebridge_reconciler_start", job_id=job_id)

    with session_scope() as session:
        job = session.get(LakebridgeJob, jid)
        if not job:
            log.error("lakebridge_reconciler_job_not_found", job_id=job_id)
            return

        if job.status != LakebridgeJobStatus.RUNNING.value:
            log.warning(
                "lakebridge_reconciler_wrong_status",
                job_id=job_id,
                status=job.status,
            )
            return

        project_id = job.project_id
        source_dialect = job.source_dialect
        metadata = job.metadata_json

        source_artifact_ids = metadata.get("source_artifact_ids", [])
        transpiled_artifact_ids = metadata.get("transpiled_artifact_ids", [])
        source_connection = metadata.get("source_connection", "")
        sample_size = metadata.get("sample_size", 1000)
        tolerance = metadata.get("tolerance", 0.0)
        tables = metadata.get("tables")

    config, decrypted_pat = _load_config(project_id)
    if not config or not decrypted_pat:
        _mark_failed(jid, "Databricks config not found or disabled")
        return

    with tempfile.TemporaryDirectory(prefix="lakebridge_reconcile_") as tmpdir:
        tmpdir_path = Path(tmpdir)
        source_dir = tmpdir_path / "source"
        transpiled_dir = tmpdir_path / "transpiled"
        output_dir = tmpdir_path / "output"
        source_dir.mkdir()
        transpiled_dir.mkdir()
        output_dir.mkdir()

        try:
            _prepare_artifacts(source_artifact_ids, source_dir)
            _prepare_artifacts(transpiled_artifact_ids, transpiled_dir)
        except Exception as e:
            log.exception("lakebridge_reconciler_input_error", job_id=job_id)
            _mark_failed(jid, f"Failed to prepare input files: {e}")
            return

        cli = LakebridgeCLIClient(timeout_seconds=1140)

        try:
            result = asyncio.run(
                _run_reconcile_command(
                    cli=cli,
                    source_dialect=source_dialect,
                    source_path=str(source_dir),
                    transpiled_path=str(transpiled_dir),
                    output_path=str(output_dir),
                    source_connection=source_connection,
                    workspace_url=config.workspace_url,
                    pat=decrypted_pat,
                    catalog=config.catalog_name,
                    schema=config.schema_name,
                    sample_size=sample_size,
                    tolerance=tolerance,
                    tables=tables,
                )
            )
        except Exception as e:
            log.exception("lakebridge_reconciler_cli_error", job_id=job_id)
            _mark_failed(jid, f"CLI execution error: {e}")
            return

        output_file = select_output_file(
            output_dir, prefer_keywords=("reconcile", "recon", "report", "summary")
        )

        # Wrap post-CLI handling so a crash here marks the job FAILED rather
        # than leaving it stuck in RUNNING.
        try:
            if result.success and output_file:
                content = output_file.read_text(encoding="utf-8", errors="replace")

                try:
                    report = json.loads(content)
                    reconcile_results = _extract_summary(report)
                except json.JSONDecodeError:
                    report = {"raw_output": content}
                    reconcile_results = {}

                persisted = False
                artifact_id: uuid.UUID | None = None
                with session_scope() as session:
                    job_service = LakebridgeJobService(session)

                    current = job_service.get_job(jid)
                    if not current or current.status != LakebridgeJobStatus.RUNNING.value:
                        log.info(
                            "lakebridge_reconciler_skip_persist",
                            job_id=job_id,
                            status=current.status if current else None,
                        )
                    else:
                        artifact = job_service.create_result_artifact(
                            project_id=project_id,
                            job_id=jid,
                            content=content,
                            filename="reconcile_report.json",
                            kind=ArtifactKind.RECONCILE_RESULT,
                        )
                        artifact_id = artifact.id

                        job_service.update_job_metadata(
                            job_id=jid,
                            updates={"reconcile_results": reconcile_results},
                        )

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
                        "lakebridge_reconciler_done",
                        job_id=job_id,
                        duration_ms=result.duration_ms,
                        artifact_id=str(artifact_id),
                        pass_rate=reconcile_results.get("pass_rate"),
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
                    "lakebridge_reconciler_no_output",
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
            log.exception("lakebridge_reconciler_persist_error", job_id=job_id)
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


def _prepare_artifacts(artifact_ids: list[str], target_dir: Path) -> None:
    """Copy artifacts to target directory."""
    with session_scope() as session:
        for aid_str in artifact_ids:
            aid = uuid.UUID(aid_str)
            artifact = session.get(ProjectArtifact, aid)

            if not artifact:
                log.warning("lakebridge_reconciler_artifact_not_found", artifact_id=aid_str)
                continue

            src_path = resolve_artifact_path(artifact.path)
            if not src_path.exists():
                log.warning(
                    "lakebridge_reconciler_artifact_file_missing",
                    artifact_id=aid_str,
                    path=str(src_path),
                )
                continue

            dst_filename = artifact.filename
            dst_path = target_dir / dst_filename
            counter = 1
            while dst_path.exists():
                stem = Path(artifact.filename).stem
                suffix = Path(artifact.filename).suffix
                dst_filename = f"{stem}_{counter}{suffix}"
                dst_path = target_dir / dst_filename
                counter += 1

            shutil.copy2(src_path, dst_path)

            log.debug(
                "lakebridge_reconciler_file_copied",
                artifact_id=aid_str,
                dst=str(dst_path),
            )


async def _run_reconcile_command(
    cli: LakebridgeCLIClient,
    source_dialect: str,
    source_path: str,
    transpiled_path: str,
    output_path: str,
    source_connection: str,
    workspace_url: str,
    pat: str,
    catalog: str,
    schema: str,
    sample_size: int,
    tolerance: float,
    tables: list[str] | None,
) -> CLIResult:
    """Run Lakebridge reconcile command."""
    env = {
        "DATABRICKS_HOST": workspace_url,
        "DATABRICKS_TOKEN": pat,
    }

    args = [
        "databricks",
        "labs",
        "lakebridge",
        "reconcile",
        "--source",
        source_dialect,
        "--source-path",
        source_path,
        "--target-path",
        transpiled_path,
        "--output-path",
        output_path,
        "--source-connection",
        source_connection,
        "--catalog",
        catalog,
        "--schema",
        schema,
        "--sample-size",
        str(sample_size),
    ]

    if tolerance > 0:
        args.extend(["--tolerance", str(tolerance)])

    if tables:
        for table in tables:
            args.extend(["--table", table])

    return await cli.run_command(args, env=env, timeout=1140)


def _extract_summary(report: dict) -> dict:
    """Extract summary statistics from reconciliation report."""
    tables = report.get("tables", report.get("results", []))

    passed = 0
    failed = 0

    for t in tables:
        row_match = t.get("row_count_match", True)
        schema_match = t.get("schema_match", True)
        sample_match = t.get("sample_match", t.get("data_match", True))

        if row_match and schema_match and sample_match:
            passed += 1
        else:
            failed += 1

    total = passed + failed
    pass_rate = (passed / total * 100) if total > 0 else 0.0

    return {
        "total_tables": total,
        "passed_tables": passed,
        "failed_tables": failed,
        "pass_rate": round(pass_rate, 2),
    }


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
        "lakebridge_reconciler_failed",
        job_id=str(job_id),
        error=error[:200],
    )


def _integrate_with_workshop(job_id: uuid.UUID) -> None:
    """Import reconciler results into Workshop's ReconciliationRun model.

    This bridges Lakebridge outputs with the Workshop's structured
    migration workflow, enabling:
    - Unified reconciliation tracking
    - Sign-off checklist auto-population
    - Audit trail for compliance

    Non-fatal if integration fails.

    Args:
        job_id: Completed LakebridgeJob UUID
    """
    try:
        with session_scope() as session:
            from app.services.lakebridge_integration_service import (
                LakebridgeIntegrationService,
            )

            integration_service = LakebridgeIntegrationService(session)
            run_id = integration_service.import_reconciler_results(job_id)

            if run_id:
                log.info(
                    "lakebridge_reconciler_integrated",
                    job_id=str(job_id),
                    reconciliation_run_id=str(run_id),
                )
            else:
                log.warning(
                    "lakebridge_reconciler_integration_skipped",
                    job_id=str(job_id),
                )
    except Exception as e:
        log.warning(
            "lakebridge_reconciler_integration_failed",
            job_id=str(job_id),
            error=str(e),
        )
