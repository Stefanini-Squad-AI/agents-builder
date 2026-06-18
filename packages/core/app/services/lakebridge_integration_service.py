"""Lakebridge Integration Service — bridges Lakebridge jobs with Workshop modules.

Imports Lakebridge analyzer/reconciler results into:
- ETLPackage.analysis_json (analyzer)
- ReconciliationRun (reconciler)
- Sign-off checklist items (reconciler → parallel-run sign-offs, pr_02/pr_03)

This ensures Lakebridge outputs are not isolated artifacts but integrated
into the Workshop's structured migration workflow.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.lakebridge import LakebridgeJob
from app.domain.projects import ProjectArtifact
from app.enums import ArtifactKind, LakebridgeJobStatus, LakebridgeJobType
from app.modules.migration_workbench.models import (
    ETLPackage,
    ReconciliationCheckResult,
    ReconciliationRun,
)
from app.services.lakebridge_matching import match_filename
from app.storage import resolve_artifact_path

log = structlog.get_logger(__name__)


class LakebridgeIntegrationService:
    """Bridge between Lakebridge jobs and Workshop modules.

    Provides methods to import Lakebridge CLI outputs into the
    existing Workshop data model for unified tracking.
    """

    def __init__(self, session: Session):
        self._session = session

    def import_analyzer_results(
        self,
        job_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        """Import Lakebridge analyzer results into ETLPackages.

        For each input artifact in the job:
        1. Find the corresponding ETLPackage (via artifact_id)
        2. Parse the analyzer report
        3. Merge Lakebridge metrics into analysis_json

        Args:
            job_id: Completed LakebridgeJob UUID

        Returns:
            List of updated ETLPackage IDs
        """
        job = self._session.get(LakebridgeJob, job_id)
        if not job:
            log.warning("integration_job_not_found", job_id=str(job_id))
            return []

        if job.status != LakebridgeJobStatus.COMPLETED.value:
            log.warning(
                "integration_job_not_completed",
                job_id=str(job_id),
                status=job.status,
            )
            return []

        if job.job_type != LakebridgeJobType.ANALYZE.value:
            log.warning(
                "integration_wrong_job_type",
                job_id=str(job_id),
                job_type=job.job_type,
            )
            return []

        report = self._load_analyzer_report(job)
        if not report:
            log.warning("integration_no_report", job_id=str(job_id))
            return []

        file_results = self._parse_file_results(report)

        updated_packages: list[uuid.UUID] = []

        for artifact_id_str in job.input_artifact_ids:
            try:
                artifact_id = uuid.UUID(artifact_id_str)
            except ValueError:
                continue

            artifact = self._session.get(ProjectArtifact, artifact_id)
            if not artifact:
                continue

            package = self._find_package_for_artifact(artifact_id, job.project_id)
            if not package:
                log.debug(
                    "integration_no_package_for_artifact",
                    artifact_id=artifact_id_str,
                )
                continue

            file_result = self._match_file_result(artifact.filename, file_results)

            self._merge_lakebridge_analysis(
                package=package,
                job=job,
                file_result=file_result,
                report_summary=report,
            )

            updated_packages.append(package.id)

            log.info(
                "integration_package_updated",
                package_id=str(package.id),
                package_name=package.package_name,
                artifact_id=artifact_id_str,
            )

        if job.input_artifact_ids and not updated_packages:
            log.warning(
                "integration_analyzer_no_packages_matched",
                job_id=str(job_id),
                input_count=len(job.input_artifact_ids),
                note=(
                    "No ETLPackage is linked (via artifact_id) to the analyzed "
                    "artifacts; analyzer metrics were not merged."
                ),
            )

        self._session.flush()

        log.info(
            "integration_analyzer_complete",
            job_id=str(job_id),
            packages_updated=len(updated_packages),
        )

        return updated_packages

    def _load_analyzer_report(self, job: LakebridgeJob) -> dict[str, Any] | None:
        """Load analyzer report from job's result artifact."""
        if not job.result_artifact_id:
            return None

        artifact = self._session.get(ProjectArtifact, job.result_artifact_id)
        if not artifact:
            return None

        try:
            if artifact.content_md:
                return json.loads(artifact.content_md)
            else:
                abs_path = resolve_artifact_path(artifact.path)
                return json.loads(abs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError) as e:
            log.warning(
                "integration_report_parse_error",
                artifact_id=str(artifact.id),
                error=str(e),
            )
            return None

    def _parse_file_results(
        self,
        report: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Parse analyzer report into per-file results.

        Returns:
            Dict mapping filename (lowercased) to file analysis result
        """
        results: dict[str, dict[str, Any]] = {}

        files = report.get("files", report.get("results", []))

        for f in files:
            filename = f.get("file", f.get("filename", f.get("name", "")))
            if filename:
                results[filename.lower()] = f

        return results

    def _find_package_for_artifact(
        self,
        artifact_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> ETLPackage | None:
        """Find ETLPackage linked to an artifact.

        Args:
            artifact_id: The artifact UUID
            project_id: Project UUID for scoping

        Returns:
            ETLPackage if found, None otherwise
        """
        stmt = select(ETLPackage).where(
            ETLPackage.project_id == project_id,
            ETLPackage.artifact_id == artifact_id,
        )
        return self._session.scalars(stmt).first()

    def _match_file_result(
        self,
        filename: str,
        file_results: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Match artifact filename to analyzer file result.

        Uses tiered matching (exact → stem → unambiguous substring) so that
        similarly-named files (e.g. ``order.sql`` vs ``order_detail.sql``) are
        not mis-linked.
        """
        key = match_filename(filename, file_results.keys())
        return file_results.get(key) if key else None

    def _merge_lakebridge_analysis(
        self,
        package: ETLPackage,
        job: LakebridgeJob,
        file_result: dict[str, Any] | None,
        report_summary: dict[str, Any],
    ) -> None:
        """Merge Lakebridge analysis into ETLPackage.analysis_json.

        Creates a 'lakebridge' section within the existing analysis_json,
        preserving any prior LLM analysis.
        """
        existing = package.analysis_json or {}

        lakebridge_data: dict[str, Any] = {
            "job_id": str(job.id),
            "analyzed_at": job.updated_at.isoformat() if job.updated_at else None,
            "source_dialect": job.source_dialect,
        }

        if file_result:
            lakebridge_data["complexity"] = file_result.get(
                "complexity",
                file_result.get("complexity_level", "unknown"),
            )
            lakebridge_data["complexity_score"] = file_result.get(
                "complexity_score",
                file_result.get("score"),
            )
            lakebridge_data["issues"] = file_result.get(
                "issues",
                file_result.get("errors", []),
            )
            lakebridge_data["warnings"] = file_result.get("warnings", [])
            lakebridge_data["analyzed"] = file_result.get("analyzed", True)
            lakebridge_data["migration_readiness"] = self._calculate_readiness(
                file_result
            )
        else:
            lakebridge_data["analyzed"] = False
            lakebridge_data["note"] = "File not found in analyzer report"

        report_meta = {
            "total_files": report_summary.get("total_files", len(report_summary.get("files", []))),
            "report_version": report_summary.get("version"),
        }
        lakebridge_data["report_metadata"] = report_meta

        existing["lakebridge"] = lakebridge_data
        package.analysis_json = existing

        if file_result and not package.complexity:
            complexity = file_result.get("complexity", "medium")
            if complexity in ("low", "medium", "high", "very_high"):
                package.complexity = complexity

    def _calculate_readiness(self, file_result: dict[str, Any]) -> str:
        """Calculate migration readiness based on issues and complexity.

        Returns:
            'high', 'medium', or 'low'
        """
        issues = file_result.get("issues", file_result.get("errors", []))
        complexity = file_result.get("complexity", "medium")

        issue_count = len(issues) if isinstance(issues, list) else 0

        if issue_count == 0 and complexity in ("low", "medium"):
            return "high"
        elif issue_count <= 3 and complexity != "very_high":
            return "medium"
        else:
            return "low"

    # =========================================================================
    # Reconciler Integration
    # =========================================================================

    def import_reconciler_results(
        self,
        job_id: uuid.UUID,
        package_id: uuid.UUID | None = None,
    ) -> uuid.UUID | None:
        """Import Lakebridge reconciler results into ReconciliationRun.

        Creates a ReconciliationRun with per-table check results from the
        Lakebridge reconciler output, then auto-populates the row-count and
        checksum checklist items on any open parallel-run sign-off covering
        the resolved package.

        Args:
            job_id: Completed LakebridgeJob UUID
            package_id: Optional ETLPackage to link. When None, the package is
                resolved from the reconcile source artifacts; if it cannot be
                uniquely resolved, the import is skipped (returns None).

        Returns:
            Created ReconciliationRun ID, or None if skipped/failed
        """
        job = self._session.get(LakebridgeJob, job_id)
        if not job:
            log.warning("integration_reconciler_job_not_found", job_id=str(job_id))
            return None

        if job.status != LakebridgeJobStatus.COMPLETED.value:
            log.warning(
                "integration_reconciler_job_not_completed",
                job_id=str(job_id),
                status=job.status,
            )
            return None

        if job.job_type != LakebridgeJobType.RECONCILE.value:
            log.warning(
                "integration_reconciler_wrong_job_type",
                job_id=str(job_id),
                job_type=job.job_type,
            )
            return None

        report = self._load_reconciler_report(job)
        if not report:
            log.warning("integration_reconciler_no_report", job_id=str(job_id))
            return None

        effective_package_id = package_id or self._find_package_for_reconciliation(job)

        # ReconciliationRun.package_id is NOT NULL: only import when we can
        # attribute the run to a single, unambiguous package. Otherwise skip
        # rather than mis-attribute to an unrelated package.
        if not effective_package_id:
            log.warning(
                "integration_reconciler_no_package",
                job_id=str(job_id),
                note=(
                    "Could not resolve a unique ETLPackage from the reconcile "
                    "source artifacts; skipping reconciliation-run import."
                ),
            )
            return None

        run = self._create_reconciliation_run(
            job=job,
            report=report,
            package_id=effective_package_id,
        )

        self._create_check_results(run, report)

        self._session.flush()

        # B3b: auto-populate parallel-run sign-off checklist items (pr_02/pr_03)
        # from this reconciliation run. Non-fatal.
        self._auto_populate_signoffs(job.project_id, effective_package_id, run.id)

        log.info(
            "integration_reconciler_complete",
            job_id=str(job_id),
            run_id=str(run.id),
            status=run.status,
        )

        return run.id

    def _load_reconciler_report(self, job: LakebridgeJob) -> dict[str, Any] | None:
        """Load reconciler report from job's result artifact."""
        if not job.result_artifact_id:
            return job.metadata_json.get("reconcile_results")

        artifact = self._session.get(ProjectArtifact, job.result_artifact_id)
        if not artifact:
            return job.metadata_json.get("reconcile_results")

        try:
            if artifact.content_md:
                return json.loads(artifact.content_md)
            else:
                abs_path = resolve_artifact_path(artifact.path)
                return json.loads(abs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError) as e:
            log.warning(
                "integration_reconciler_report_parse_error",
                artifact_id=str(artifact.id),
                error=str(e),
            )
            return job.metadata_json.get("reconcile_results")

    def _find_package_for_reconciliation(
        self,
        job: LakebridgeJob,
    ) -> uuid.UUID | None:
        """Resolve the ETLPackage a reconciliation run belongs to.

        Matches via the run's *source* artifacts: the package whose
        ``artifact_id`` is among the reconcile source artifacts. Returns the
        package id only when exactly one package matches; returns None when
        zero or multiple match (ambiguous → caller skips the import) so the
        run is never attributed to an unrelated package.
        """
        source_ids: list[uuid.UUID] = []
        for aid in job.metadata_json.get("source_artifact_ids", []):
            try:
                source_ids.append(uuid.UUID(str(aid)))
            except (ValueError, TypeError):
                continue

        if not source_ids:
            return None

        stmt = (
            select(ETLPackage.id)
            .where(
                ETLPackage.project_id == job.project_id,
                ETLPackage.artifact_id.in_(source_ids),
            )
            .distinct()
        )
        package_ids = list(self._session.scalars(stmt).all())

        if len(package_ids) == 1:
            return package_ids[0]
        return None

    def _auto_populate_signoffs(
        self,
        project_id: uuid.UUID,
        package_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> None:
        """Auto-populate parallel-run sign-off checklist items from a run.

        Marks the row-count (pr_02) and checksum (pr_03) checklist items as
        passed on any open parallel-run sign-off covering ``package_id``,
        using the reconciliation run as evidence. Non-fatal: a failure here
        never breaks reconciliation import.
        """
        try:
            from app.modules.migration_workbench.signoff.service import (
                SignoffService,
            )

            signoff_service = SignoffService(self._session)
            candidates = signoff_service.get_signoffs_for_reconciliation(
                project_id, package_id
            )

            populated = 0
            for candidate in candidates:
                signoff_service.auto_populate_from_reconciliation(
                    candidate.id, run_id
                )
                populated += 1

            if populated:
                log.info(
                    "lakebridge_signoff_autopopulated",
                    run_id=str(run_id),
                    package_id=str(package_id),
                    signoffs_updated=populated,
                )
        except Exception as e:
            log.warning(
                "lakebridge_signoff_autopopulate_failed",
                run_id=str(run_id),
                error=str(e),
            )

    def _create_reconciliation_run(
        self,
        job: LakebridgeJob,
        report: dict[str, Any],
        package_id: uuid.UUID | None,
    ) -> ReconciliationRun:
        """Create a ReconciliationRun from Lakebridge results."""
        tables = report.get("tables", report.get("results", []))

        total_source = 0
        total_target = 0
        passed = 0
        failed = 0

        for t in tables:
            source_count = t.get("source_row_count", t.get("source_count", 0))
            target_count = t.get("target_row_count", t.get("target_count", 0))
            total_source += source_count
            total_target += target_count

            row_match = t.get("row_count_match", True)
            schema_match = t.get("schema_match", True)
            sample_match = t.get("sample_match", t.get("data_match", True))

            if row_match and schema_match and sample_match:
                passed += 1
            else:
                failed += 1

        if failed == 0 and passed > 0:
            status = "passed"
        elif passed == 0 and failed > 0:
            status = "failed"
        elif failed > 0:
            status = "warning"
        else:
            status = "warning"

        now = datetime.now(timezone.utc)

        run = ReconciliationRun(
            id=uuid.uuid4(),
            project_id=job.project_id,
            package_id=package_id,
            status=status,
            started_at=job.created_at,
            completed_at=now,
            source_row_count=total_source,
            target_row_count=total_target,
            triggered_by="lakebridge",
            uc_connection_name=job.metadata_json.get("source_connection"),
            summary_json={
                "lakebridge_job_id": str(job.id),
                "total_tables": len(tables),
                "passed_tables": passed,
                "failed_tables": failed,
                "pass_rate": (passed / len(tables) * 100) if tables else 0,
                "tables": [
                    {
                        "name": t.get("table_name", t.get("name", "unknown")),
                        "source_count": t.get("source_row_count", t.get("source_count", 0)),
                        "target_count": t.get("target_row_count", t.get("target_count", 0)),
                        "row_match": t.get("row_count_match", True),
                        "schema_match": t.get("schema_match", True),
                        "data_match": t.get("sample_match", t.get("data_match", True)),
                    }
                    for t in tables
                ],
            },
        )

        self._session.add(run)

        return run

    def _create_check_results(
        self,
        run: ReconciliationRun,
        report: dict[str, Any],
    ) -> list[ReconciliationCheckResult]:
        """Create ReconciliationCheckResult records for each table check."""
        tables = report.get("tables", report.get("results", []))
        results: list[ReconciliationCheckResult] = []

        for t in tables:
            table_name = t.get("table_name", t.get("name", "unknown"))
            source_count = t.get("source_row_count", t.get("source_count", 0))
            target_count = t.get("target_row_count", t.get("target_count", 0))
            row_match = t.get("row_count_match", source_count == target_count)

            row_count_check = ReconciliationCheckResult(
                id=uuid.uuid4(),
                run_id=run.id,
                check_type="row_count",
                source_table=table_name,
                target_table=table_name,
                source_value=str(source_count),
                target_value=str(target_count),
                match=row_match,
                variance=abs(source_count - target_count) if not row_match else 0,
                source_data_method="lakebridge",
                target_data_method="lakebridge",
            )
            self._session.add(row_count_check)
            results.append(row_count_check)

            if "sample_match" in t or "data_match" in t or "checksum" in t:
                sample_match = t.get("sample_match", t.get("data_match", True))
                checksum_check = ReconciliationCheckResult(
                    id=uuid.uuid4(),
                    run_id=run.id,
                    check_type="checksum",
                    source_table=table_name,
                    target_table=table_name,
                    source_value=t.get("source_checksum", "computed"),
                    target_value=t.get("target_checksum", "computed"),
                    match=sample_match,
                    source_data_method="lakebridge",
                    target_data_method="lakebridge",
                    notes="; ".join(t.get("discrepancies", []))[:500] if not sample_match else None,
                )
                self._session.add(checksum_check)
                results.append(checksum_check)

        return results
