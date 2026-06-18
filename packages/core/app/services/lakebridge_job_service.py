"""Lakebridge Job Service — orchestrates analyzer/transpiler/reconciler jobs.

Manages the lifecycle of LakebridgeJob records:
- Create job (PENDING)
- Dispatch to background worker
- Track progress (RUNNING → COMPLETED/FAILED)
- Store results as artifacts
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.lakebridge import DatabricksConfig, LakebridgeJob
from app.domain.projects import Project, ProjectArtifact
from app.enums import ArtifactKind, ExtractionStatus, LakebridgeJobStatus, LakebridgeJobType
from app.schemas.lakebridge import (
    AnalyzerSummaryView,
    LakebridgeJobView,
    ReconcileSummaryView,
    ReconcileStatusView,
    ReconcileTableResult,
    TranspileStatusView,
)
from app.settings import get_settings
from app.storage import resolve_artifact_path

log = structlog.get_logger(__name__)

# Cap CLI output stored on LakebridgeJob.cli_stdout/cli_stderr (documented 64KB
# contract). Oversized logs keep their head (command echo) and tail (errors).
MAX_CLI_LOG_CHARS = 64 * 1024
_CLI_LOG_HEAD_CHARS = 48 * 1024
_CLI_LOG_TAIL_CHARS = MAX_CLI_LOG_CHARS - _CLI_LOG_HEAD_CHARS


def _truncate_log(text: str | None) -> str | None:
    """Cap CLI output to ``MAX_CLI_LOG_CHARS``, keeping head + tail."""
    if text is None or len(text) <= MAX_CLI_LOG_CHARS:
        return text

    omitted = len(text) - _CLI_LOG_HEAD_CHARS - _CLI_LOG_TAIL_CHARS
    head = text[:_CLI_LOG_HEAD_CHARS]
    tail = text[-_CLI_LOG_TAIL_CHARS:]
    return f"{head}\n... [truncated {omitted} characters] ...\n{tail}"


class LakebridgeJobService:
    """Service for managing Lakebridge job lifecycle.

    Handles job creation, status updates, artifact storage,
    and job history queries.
    """

    def __init__(self, session: Session):
        self._session = session

    def create_analyzer_job(
        self,
        project_id: uuid.UUID,
        source_dialect: str,
        input_artifact_ids: list[uuid.UUID],
        cli_command: str,
        metadata: dict[str, Any] | None = None,
    ) -> LakebridgeJob:
        """Create a new analyzer job.

        Args:
            project_id: Project UUID
            source_dialect: Source dialect (oracle, snowflake, tsql, ssis)
            input_artifact_ids: Artifacts to analyze
            cli_command: Full CLI command to execute
            metadata: Optional metadata dict

        Returns:
            Created LakebridgeJob in PENDING status
        """
        job = LakebridgeJob(
            id=uuid.uuid4(),
            project_id=project_id,
            job_type=LakebridgeJobType.ANALYZE.value,
            status=LakebridgeJobStatus.PENDING.value,
            source_dialect=source_dialect,
            transpiler=None,
            input_artifact_ids=[str(aid) for aid in input_artifact_ids],
            cli_command=cli_command,
            metadata_json=metadata or {},
        )

        self._session.add(job)
        self._session.flush()

        log.info(
            "lakebridge_job_created",
            job_id=str(job.id),
            project_id=str(project_id),
            job_type="analyze",
            source_dialect=source_dialect,
            input_count=len(input_artifact_ids),
        )

        return job

    def create_transpiler_job(
        self,
        project_id: uuid.UUID,
        source_dialect: str,
        transpiler: str,
        input_artifact_ids: list[uuid.UUID],
        cli_command: str,
        skip_validation: bool = False,
        options: dict[str, Any] | None = None,
    ) -> LakebridgeJob:
        """Create a new transpiler job.

        Args:
            project_id: Project UUID
            source_dialect: Source dialect (oracle, snowflake, tsql, ssis)
            transpiler: Transpiler to use (bladebridge, morpheus, switch)
            input_artifact_ids: Artifacts to transpile
            cli_command: Full CLI command to execute
            skip_validation: Skip semantic validation
            options: Transpiler-specific options

        Returns:
            Created LakebridgeJob in PENDING status
        """
        job_type = self._get_transpiler_job_type(transpiler)

        metadata = {
            "transpiler": transpiler,
            "skip_validation": skip_validation,
            "options": options or {},
            "source_to_output_map": {},
            "output_artifacts": [],
        }

        job = LakebridgeJob(
            id=uuid.uuid4(),
            project_id=project_id,
            job_type=job_type.value,
            status=LakebridgeJobStatus.PENDING.value,
            source_dialect=source_dialect,
            transpiler=transpiler,
            input_artifact_ids=[str(aid) for aid in input_artifact_ids],
            cli_command=cli_command,
            metadata_json=metadata,
        )

        self._session.add(job)
        self._session.flush()

        log.info(
            "lakebridge_job_created",
            job_id=str(job.id),
            project_id=str(project_id),
            job_type=job_type.value,
            transpiler=transpiler,
            source_dialect=source_dialect,
            input_count=len(input_artifact_ids),
        )

        return job

    def start_transpiler_job(self, job_id: uuid.UUID) -> None:
        """Mark transpiler job as running and dispatch to background worker.

        Args:
            job_id: Job UUID to start
        """
        from app.jobs.run_lakebridge_transpiler import run_lakebridge_transpiler

        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if job.status != LakebridgeJobStatus.PENDING.value:
            raise ValueError(f"Job is not pending: {job.status}")

        job.status = LakebridgeJobStatus.RUNNING.value
        self._session.commit()

        run_lakebridge_transpiler.send(str(job_id))

        log.info("lakebridge_transpiler_job_started", job_id=str(job_id))

    def start_job(self, job_id: uuid.UUID) -> None:
        """Mark job as running and dispatch to background worker.

        Args:
            job_id: Job UUID to start
        """
        from app.jobs.run_lakebridge_analyzer import run_lakebridge_analyzer

        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if job.status != LakebridgeJobStatus.PENDING.value:
            raise ValueError(f"Job is not pending: {job.status}")

        job.status = LakebridgeJobStatus.RUNNING.value
        self._session.commit()

        run_lakebridge_analyzer.send(str(job_id))

        log.info("lakebridge_job_started", job_id=str(job_id))

    def complete_job(
        self,
        job_id: uuid.UUID,
        exit_code: int,
        stdout: str,
        stderr: str,
        duration_ms: int,
        result_artifact_id: uuid.UUID | None = None,
    ) -> LakebridgeJob:
        """Mark job as completed.

        Args:
            job_id: Job UUID
            exit_code: CLI exit code (0 = success)
            stdout: Final stdout
            stderr: Final stderr
            duration_ms: Execution time in milliseconds
            result_artifact_id: Optional artifact with results

        Returns:
            Updated job
        """
        job = self._get_job_or_raise(job_id)

        job.exit_code = exit_code
        job.cli_stdout = _truncate_log(stdout)
        job.cli_stderr = _truncate_log(stderr)
        job.duration_ms = duration_ms
        job.result_artifact_id = result_artifact_id

        # A cancelled job must stay cancelled: record audit fields but do not
        # resurrect it to COMPLETED if the user cancelled while the CLI ran.
        if job.status == LakebridgeJobStatus.CANCELLED.value:
            log.info("lakebridge_job_complete_after_cancel", job_id=str(job_id))
        else:
            job.status = LakebridgeJobStatus.COMPLETED.value

        self._session.flush()

        log.info(
            "lakebridge_job_completed",
            job_id=str(job_id),
            exit_code=exit_code,
            duration_ms=duration_ms,
            has_artifact=result_artifact_id is not None,
        )

        return job

    def fail_job(
        self,
        job_id: uuid.UUID,
        error_message: str,
        exit_code: int | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        duration_ms: int | None = None,
    ) -> LakebridgeJob:
        """Mark job as failed.

        Args:
            job_id: Job UUID
            error_message: Human-readable error
            exit_code: Optional CLI exit code
            stdout: Optional stdout
            stderr: Optional stderr
            duration_ms: Optional execution time

        Returns:
            Updated job
        """
        job = self._get_job_or_raise(job_id)

        job.error_message = error_message[:1000]

        if exit_code is not None:
            job.exit_code = exit_code
        if stdout is not None:
            job.cli_stdout = _truncate_log(stdout)
        if stderr is not None:
            job.cli_stderr = _truncate_log(stderr)
        if duration_ms is not None:
            job.duration_ms = duration_ms

        # A cancelled job must stay cancelled even if the CLI later errors out.
        if job.status == LakebridgeJobStatus.CANCELLED.value:
            log.info("lakebridge_job_fail_after_cancel", job_id=str(job_id))
        else:
            job.status = LakebridgeJobStatus.FAILED.value

        self._session.flush()

        log.warning(
            "lakebridge_job_failed",
            job_id=str(job_id),
            error=error_message[:200],
        )

        return job

    def cancel_job(self, job_id: uuid.UUID) -> LakebridgeJob:
        """Cancel a pending or running job.

        Best-effort (soft) cancellation: the job row is marked CANCELLED and
        the background worker will skip persisting any result and skip Workshop
        integration once it re-checks status. A CLI subprocess that is already
        running is NOT killed; it finishes in the background but its output is
        discarded. Hard cancellation (subprocess kill) is a future enhancement.

        Args:
            job_id: Job UUID

        Returns:
            Updated job

        Raises:
            ValueError: If job is already completed/failed
        """
        job = self._get_job_or_raise(job_id)

        if job.status in (
            LakebridgeJobStatus.COMPLETED.value,
            LakebridgeJobStatus.FAILED.value,
            LakebridgeJobStatus.CANCELLED.value,
        ):
            raise ValueError(f"Cannot cancel job in status: {job.status}")

        job.status = LakebridgeJobStatus.CANCELLED.value
        self._session.flush()

        log.info("lakebridge_job_cancelled", job_id=str(job_id))
        return job

    def create_result_artifact(
        self,
        project_id: uuid.UUID,
        job_id: uuid.UUID,
        content: str,
        filename: str,
        kind: ArtifactKind = ArtifactKind.ANALYZER_REPORT,
    ) -> ProjectArtifact:
        """Create an artifact from job results.

        Args:
            project_id: Project UUID
            job_id: Job UUID (for path organization)
            content: Artifact content (JSON or text)
            filename: Artifact filename
            kind: Artifact kind

        Returns:
            Created artifact
        """
        settings = get_settings()
        base_dir = Path(settings.workshop_data_dir).resolve()

        rel_path = f"lakebridge/{project_id}/{job_id}/{filename}"
        abs_path = base_dir / rel_path

        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")

        artifact = ProjectArtifact(
            id=uuid.uuid4(),
            project_id=project_id,
            kind=kind.value,
            filename=filename,
            path=rel_path,
            size_bytes=len(content.encode("utf-8")),
            mime_type="application/json" if filename.endswith(".json") else "text/plain",
            extraction_status=ExtractionStatus.DONE.value,
            content_md=content[:50000] if len(content) < 100000 else None,
        )

        self._session.add(artifact)
        self._session.flush()

        log.info(
            "lakebridge_artifact_created",
            artifact_id=str(artifact.id),
            job_id=str(job_id),
            kind=kind.value,
            size_bytes=artifact.size_bytes,
        )

        return artifact

    def get_job(self, job_id: uuid.UUID) -> LakebridgeJob | None:
        """Get job by ID.

        Args:
            job_id: Job UUID

        Returns:
            LakebridgeJob or None
        """
        return self._session.get(LakebridgeJob, job_id)

    def list_jobs(
        self,
        project_id: uuid.UUID,
        status: LakebridgeJobStatus | None = None,
        job_type: LakebridgeJobType | None = None,
        limit: int = 50,
    ) -> list[LakebridgeJob]:
        """List jobs for a project.

        Args:
            project_id: Project UUID
            status: Optional status filter
            job_type: Optional job type filter
            limit: Max results

        Returns:
            List of jobs, newest first
        """
        stmt = (
            select(LakebridgeJob)
            .where(LakebridgeJob.project_id == project_id)
            .order_by(LakebridgeJob.created_at.desc())
            .limit(limit)
        )

        if status:
            stmt = stmt.where(LakebridgeJob.status == status.value)
        if job_type:
            stmt = stmt.where(LakebridgeJob.job_type == job_type.value)

        return list(self._session.scalars(stmt).all())

    def get_latest_analyzer_result(
        self,
        project_id: uuid.UUID,
    ) -> LakebridgeJob | None:
        """Get most recent completed analyzer job.

        Args:
            project_id: Project UUID

        Returns:
            Latest completed analyzer job or None
        """
        stmt = (
            select(LakebridgeJob)
            .where(
                LakebridgeJob.project_id == project_id,
                LakebridgeJob.job_type == LakebridgeJobType.ANALYZE.value,
                LakebridgeJob.status == LakebridgeJobStatus.COMPLETED.value,
            )
            .order_by(LakebridgeJob.created_at.desc())
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    def get_analyzer_summary(
        self,
        project_id: uuid.UUID,
    ) -> AnalyzerSummaryView | None:
        """Get summary from latest analyzer run.

        Args:
            project_id: Project UUID

        Returns:
            AnalyzerSummaryView or None if no completed runs
        """
        job = self.get_latest_analyzer_result(project_id)
        if not job or not job.result_artifact_id:
            return None

        artifact = self._session.get(ProjectArtifact, job.result_artifact_id)
        if not artifact:
            return None

        try:
            if artifact.content_md:
                report = json.loads(artifact.content_md)
            else:
                abs_path = resolve_artifact_path(artifact.path)
                report = json.loads(abs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return None

        return self._parse_analyzer_summary(report, job)

    def to_view(self, job: LakebridgeJob) -> LakebridgeJobView:
        """Convert job to API view."""
        return LakebridgeJobView(
            id=job.id,
            project_id=job.project_id,
            job_type=LakebridgeJobType(job.job_type),
            status=LakebridgeJobStatus(job.status),
            source_dialect=job.source_dialect,
            transpiler=job.transpiler,
            input_artifact_ids=job.input_artifact_ids,
            result_artifact_id=job.result_artifact_id,
            cli_command=job.cli_command,
            cli_stdout=job.cli_stdout,
            cli_stderr=job.cli_stderr,
            exit_code=job.exit_code,
            duration_ms=job.duration_ms,
            error_message=job.error_message,
            metadata_json=job.metadata_json,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    def _get_job_or_raise(self, job_id: uuid.UUID) -> LakebridgeJob:
        """Get job or raise ValueError."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        return job

    def _parse_analyzer_summary(
        self,
        report: dict[str, Any],
        job: LakebridgeJob,
    ) -> AnalyzerSummaryView:
        """Parse Lakebridge analyzer JSON report into summary view.

        The analyzer output format varies; this handles common structures.
        """
        files = report.get("files", report.get("results", []))
        
        total = len(files)
        analyzed = sum(1 for f in files if f.get("analyzed", True))
        skipped = total - analyzed

        complexity_dist: dict[str, int] = {}
        high_count = 0
        very_high_count = 0

        for f in files:
            complexity = f.get("complexity", "unknown")
            complexity_dist[complexity] = complexity_dist.get(complexity, 0) + 1

            if complexity == "high":
                high_count += 1
            elif complexity in ("very_high", "very-high"):
                very_high_count += 1

        return AnalyzerSummaryView(
            total_files=total,
            analyzed_files=analyzed,
            skipped_files=skipped,
            high_complexity_count=high_count,
            very_high_complexity_count=very_high_count,
            source_dialect=job.source_dialect,
            complexity_distribution=complexity_dist,
            analyzed_at=job.updated_at,
        )

    def get_transpile_status(
        self,
        project_id: uuid.UUID,
    ) -> TranspileStatusView:
        """Get transpilation status overview for a project.

        Args:
            project_id: Project UUID

        Returns:
            TranspileStatusView with counts and latest job info
        """
        total_artifacts = self._count_code_artifacts(project_id)

        transpiler_job_types = [
            LakebridgeJobType.TRANSPILE_BLADEBRIDGE.value,
            LakebridgeJobType.TRANSPILE_MORPHEUS.value,
            LakebridgeJobType.TRANSPILE_SWITCH.value,
        ]

        stmt = (
            select(LakebridgeJob)
            .where(
                LakebridgeJob.project_id == project_id,
                LakebridgeJob.job_type.in_(transpiler_job_types),
            )
            .order_by(LakebridgeJob.created_at.desc())
        )
        jobs = list(self._session.scalars(stmt).all())

        transpiled_ids: set[str] = set()
        failed_ids: set[str] = set()

        for job in jobs:
            if job.status == LakebridgeJobStatus.COMPLETED.value:
                output_map = job.metadata_json.get("source_to_output_map", {})
                for source_id in output_map.keys():
                    transpiled_ids.add(source_id)
            elif job.status == LakebridgeJobStatus.FAILED.value:
                for aid in job.input_artifact_ids:
                    if aid not in transpiled_ids:
                        failed_ids.add(aid)

        transpiled_count = len(transpiled_ids)
        failed_count = len(failed_ids - transpiled_ids)
        pending_count = max(0, total_artifacts - transpiled_count - failed_count)

        latest_job = jobs[0] if jobs else None

        return TranspileStatusView(
            total_artifacts=total_artifacts,
            transpiled_count=transpiled_count,
            failed_count=failed_count,
            pending_count=pending_count,
            latest_job_id=latest_job.id if latest_job else None,
            latest_job_status=LakebridgeJobStatus(latest_job.status) if latest_job else None,
            transpiler_used=latest_job.transpiler if latest_job else None,
        )

    def create_reconciler_job(
        self,
        project_id: uuid.UUID,
        source_dialect: str,
        source_artifact_ids: list[uuid.UUID],
        transpiled_artifact_ids: list[uuid.UUID],
        source_connection: str,
        cli_command: str,
        sample_size: int = 1000,
        tolerance: float = 0.0,
        tables: list[str] | None = None,
    ) -> LakebridgeJob:
        """Create a new reconciler job.

        Args:
            project_id: Project UUID
            source_dialect: Source dialect (oracle, snowflake, tsql)
            source_artifact_ids: Original source artifacts
            transpiled_artifact_ids: Transpiled output artifacts
            source_connection: Source database connection string
            cli_command: Full CLI command to execute
            sample_size: Rows to compare per table
            tolerance: Numeric comparison tolerance
            tables: Specific tables to reconcile (None = all)

        Returns:
            Created LakebridgeJob in PENDING status
        """
        metadata = {
            "source_connection": source_connection,
            "sample_size": sample_size,
            "tolerance": tolerance,
            "tables": tables,
            "source_artifact_ids": [str(aid) for aid in source_artifact_ids],
            "transpiled_artifact_ids": [str(aid) for aid in transpiled_artifact_ids],
            "reconcile_results": {},
        }

        all_input_ids = [str(aid) for aid in source_artifact_ids + transpiled_artifact_ids]

        job = LakebridgeJob(
            id=uuid.uuid4(),
            project_id=project_id,
            job_type=LakebridgeJobType.RECONCILE.value,
            status=LakebridgeJobStatus.PENDING.value,
            source_dialect=source_dialect,
            transpiler=None,
            input_artifact_ids=all_input_ids,
            cli_command=cli_command,
            metadata_json=metadata,
        )

        self._session.add(job)
        self._session.flush()

        log.info(
            "lakebridge_job_created",
            job_id=str(job.id),
            project_id=str(project_id),
            job_type="reconcile",
            source_dialect=source_dialect,
            source_count=len(source_artifact_ids),
            transpiled_count=len(transpiled_artifact_ids),
        )

        return job

    def start_reconciler_job(self, job_id: uuid.UUID) -> None:
        """Mark reconciler job as running and dispatch to background worker.

        Args:
            job_id: Job UUID to start
        """
        from app.jobs.run_lakebridge_reconciler import run_lakebridge_reconciler

        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if job.status != LakebridgeJobStatus.PENDING.value:
            raise ValueError(f"Job is not pending: {job.status}")

        job.status = LakebridgeJobStatus.RUNNING.value
        self._session.commit()

        run_lakebridge_reconciler.send(str(job_id))

        log.info("lakebridge_reconciler_job_started", job_id=str(job_id))

    def get_reconcile_summary(
        self,
        project_id: uuid.UUID,
    ) -> ReconcileSummaryView | None:
        """Get summary from latest reconciler run.

        Args:
            project_id: Project UUID

        Returns:
            ReconcileSummaryView or None if no completed runs
        """
        stmt = (
            select(LakebridgeJob)
            .where(
                LakebridgeJob.project_id == project_id,
                LakebridgeJob.job_type == LakebridgeJobType.RECONCILE.value,
                LakebridgeJob.status == LakebridgeJobStatus.COMPLETED.value,
            )
            .order_by(LakebridgeJob.created_at.desc())
            .limit(1)
        )
        job = self._session.scalars(stmt).first()

        if not job or not job.result_artifact_id:
            return None

        artifact = self._session.get(ProjectArtifact, job.result_artifact_id)
        if not artifact:
            return None

        try:
            if artifact.content_md:
                report = json.loads(artifact.content_md)
            else:
                abs_path = resolve_artifact_path(artifact.path)
                report = json.loads(abs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return None

        return self._parse_reconcile_summary(report, job)

    def get_reconcile_status(
        self,
        project_id: uuid.UUID,
    ) -> ReconcileStatusView:
        """Get reconciliation status overview for a project.

        Args:
            project_id: Project UUID

        Returns:
            ReconcileStatusView with counts and latest job info
        """
        stmt = (
            select(LakebridgeJob)
            .where(
                LakebridgeJob.project_id == project_id,
                LakebridgeJob.job_type == LakebridgeJobType.RECONCILE.value,
            )
            .order_by(LakebridgeJob.created_at.desc())
        )
        jobs = list(self._session.scalars(stmt).all())

        total = len(jobs)
        successful = sum(1 for j in jobs if j.status == LakebridgeJobStatus.COMPLETED.value)
        failed = sum(1 for j in jobs if j.status == LakebridgeJobStatus.FAILED.value)

        latest_job = jobs[0] if jobs else None
        latest_pass_rate: float | None = None

        if latest_job and latest_job.status == LakebridgeJobStatus.COMPLETED.value:
            results = latest_job.metadata_json.get("reconcile_results", {})
            if results:
                passed = results.get("passed_tables", 0)
                total_tables = results.get("total_tables", 0)
                if total_tables > 0:
                    latest_pass_rate = (passed / total_tables) * 100

        return ReconcileStatusView(
            total_reconcile_jobs=total,
            successful_jobs=successful,
            failed_jobs=failed,
            latest_job_id=latest_job.id if latest_job else None,
            latest_job_status=LakebridgeJobStatus(latest_job.status) if latest_job else None,
            latest_pass_rate=latest_pass_rate,
        )

    def _parse_reconcile_summary(
        self,
        report: dict[str, Any],
        job: LakebridgeJob,
    ) -> ReconcileSummaryView:
        """Parse Lakebridge reconciler JSON report into summary view."""
        tables = report.get("tables", report.get("results", []))

        table_results: list[ReconcileTableResult] = []
        passed = 0
        failed = 0
        row_mismatches = 0
        schema_mismatches = 0
        data_mismatches = 0

        for t in tables:
            row_match = t.get("row_count_match", True)
            schema_match = t.get("schema_match", True)
            sample_match = t.get("sample_match", t.get("data_match", True))

            all_passed = row_match and schema_match and sample_match

            if all_passed:
                passed += 1
            else:
                failed += 1
                if not row_match:
                    row_mismatches += 1
                if not schema_match:
                    schema_mismatches += 1
                if not sample_match:
                    data_mismatches += 1

            table_results.append(ReconcileTableResult(
                table_name=t.get("table_name", t.get("name", "unknown")),
                source_row_count=t.get("source_row_count", t.get("source_count", 0)),
                target_row_count=t.get("target_row_count", t.get("target_count", 0)),
                row_count_match=row_match,
                schema_match=schema_match,
                sample_match=sample_match,
                sample_rows_compared=t.get("sample_rows_compared", t.get("rows_compared", 0)),
                mismatched_rows=t.get("mismatched_rows", t.get("diff_count", 0)),
                discrepancies=t.get("discrepancies", t.get("errors", [])),
            ))

        total = passed + failed
        pass_rate = (passed / total * 100) if total > 0 else 0.0

        return ReconcileSummaryView(
            total_tables=total,
            passed_tables=passed,
            failed_tables=failed,
            pass_rate=pass_rate,
            row_count_mismatches=row_mismatches,
            schema_mismatches=schema_mismatches,
            data_mismatches=data_mismatches,
            table_results=table_results,
            reconciled_at=job.updated_at,
            job_id=job.id,
            source_dialect=job.source_dialect,
        )

    def update_job_metadata(
        self,
        job_id: uuid.UUID,
        updates: dict[str, Any],
    ) -> LakebridgeJob:
        """Update job metadata_json with new values.

        Args:
            job_id: Job UUID
            updates: Dict of values to merge into metadata_json

        Returns:
            Updated job
        """
        job = self._get_job_or_raise(job_id)
        job.metadata_json = {**job.metadata_json, **updates}
        self._session.flush()
        return job

    def _count_code_artifacts(self, project_id: uuid.UUID) -> int:
        """Count code artifacts in project."""
        from sqlalchemy import func

        code_kinds = [
            ArtifactKind.CODE.value,
            ArtifactKind.SSIS_PACKAGE.value,
            ArtifactKind.SQL_SCRIPT.value,
        ]

        stmt = (
            select(func.count())
            .select_from(ProjectArtifact)
            .where(
                ProjectArtifact.project_id == project_id,
                ProjectArtifact.kind.in_(code_kinds),
            )
        )
        return self._session.scalar(stmt) or 0

    def _get_transpiler_job_type(self, transpiler: str) -> LakebridgeJobType:
        """Map transpiler name to job type enum."""
        mapping = {
            "bladebridge": LakebridgeJobType.TRANSPILE_BLADEBRIDGE,
            "morpheus": LakebridgeJobType.TRANSPILE_MORPHEUS,
            "switch": LakebridgeJobType.TRANSPILE_SWITCH,
        }
        job_type = mapping.get(transpiler.lower())
        if not job_type:
            raise ValueError(
                f"Invalid transpiler: {transpiler}. "
                f"Must be one of: {', '.join(mapping.keys())}"
            )
        return job_type
