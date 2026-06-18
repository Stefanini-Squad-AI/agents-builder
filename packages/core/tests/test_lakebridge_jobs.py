"""Unit tests for Lakebridge job lifecycle guards and schemas (Phase A fixes).

These tests are DB-free: they use a tiny fake session that returns a single
in-memory ``LakebridgeJob`` instance, so they run in the normal suite without
Postgres. They cover:

- A1: cancelling a job must "stick" — ``complete_job`` / ``fail_job`` must not
  resurrect a CANCELLED job to COMPLETED / FAILED.
- A3: ``ReconcileRequest`` exposes a configurable ``source_dialect``.
"""

from __future__ import annotations

import uuid

from app.domain import register_models

register_models()

from app.domain.lakebridge import LakebridgeJob  # noqa: E402
from app.enums import LakebridgeJobStatus, LakebridgeJobType  # noqa: E402
from app.schemas.lakebridge import ReconcileRequest  # noqa: E402
from app.services.lakebridge_integration_service import (  # noqa: E402
    LakebridgeIntegrationService,
)
from app.services.lakebridge_job_service import (  # noqa: E402
    MAX_CLI_LOG_CHARS,
    LakebridgeJobService,
    _truncate_log,
)
from app.services.lakebridge_matching import (  # noqa: E402
    match_filename,
    select_output_file,
)


class _FakeSession:
    """Minimal Session stand-in: serves one job, records flush calls."""

    def __init__(self, job: LakebridgeJob) -> None:
        self._job = job
        self.flush_count = 0

    def get(self, model, pk):  # noqa: ANN001 - mimics Session.get
        return self._job

    def flush(self) -> None:
        self.flush_count += 1


def _make_job(status: str) -> LakebridgeJob:
    job = LakebridgeJob()
    job.id = uuid.uuid4()
    job.project_id = uuid.uuid4()
    job.job_type = LakebridgeJobType.ANALYZE.value
    job.status = status
    job.source_dialect = "tsql"
    job.input_artifact_ids = []
    job.cli_command = "databricks labs lakebridge analyze"
    job.metadata_json = {}
    return job


# -----------------------------------------------------------------------------
# A1: cancellation must stick
# -----------------------------------------------------------------------------


def test_complete_job_does_not_overwrite_cancelled() -> None:
    job = _make_job(LakebridgeJobStatus.CANCELLED.value)
    service = LakebridgeJobService(_FakeSession(job))

    service.complete_job(
        job_id=job.id,
        exit_code=0,
        stdout="ok",
        stderr="",
        duration_ms=123,
        result_artifact_id=None,
    )

    # Status stays CANCELLED, but audit fields are still recorded.
    assert job.status == LakebridgeJobStatus.CANCELLED.value
    assert job.exit_code == 0
    assert job.duration_ms == 123


def test_complete_job_completes_running_job() -> None:
    job = _make_job(LakebridgeJobStatus.RUNNING.value)
    service = LakebridgeJobService(_FakeSession(job))

    service.complete_job(
        job_id=job.id,
        exit_code=0,
        stdout="ok",
        stderr="",
        duration_ms=10,
        result_artifact_id=None,
    )

    assert job.status == LakebridgeJobStatus.COMPLETED.value


def test_fail_job_does_not_overwrite_cancelled() -> None:
    job = _make_job(LakebridgeJobStatus.CANCELLED.value)
    service = LakebridgeJobService(_FakeSession(job))

    service.fail_job(job_id=job.id, error_message="boom", exit_code=1)

    assert job.status == LakebridgeJobStatus.CANCELLED.value
    assert job.error_message == "boom"
    assert job.exit_code == 1


def test_fail_job_fails_running_job() -> None:
    job = _make_job(LakebridgeJobStatus.RUNNING.value)
    service = LakebridgeJobService(_FakeSession(job))

    service.fail_job(job_id=job.id, error_message="boom")

    assert job.status == LakebridgeJobStatus.FAILED.value


# -----------------------------------------------------------------------------
# A3: reconcile source dialect is configurable
# -----------------------------------------------------------------------------


def test_reconcile_request_defaults_to_tsql() -> None:
    req = ReconcileRequest(
        source_artifact_ids=[uuid.uuid4()],
        transpiled_artifact_ids=[uuid.uuid4()],
        source_connection="conn",
    )
    assert req.source_dialect == "tsql"


def test_reconcile_request_honors_explicit_dialect() -> None:
    req = ReconcileRequest(
        source_dialect="oracle",
        source_artifact_ids=[uuid.uuid4()],
        transpiled_artifact_ids=[uuid.uuid4()],
        source_connection="conn",
    )
    assert req.source_dialect == "oracle"


# -----------------------------------------------------------------------------
# B2: filename matching is tiered and refuses ambiguous matches
# -----------------------------------------------------------------------------


def test_match_filename_exact_case_insensitive() -> None:
    assert match_filename("Order.SQL", ["order.sql", "other.sql"]) == "order.sql"


def test_match_filename_exact_wins_over_substring() -> None:
    assert (
        match_filename("order.sql", ["order.sql", "order_detail.sql"]) == "order.sql"
    )


def test_match_filename_stem_match_across_extensions() -> None:
    assert match_filename("order.py", ["order.sql"]) == "order.sql"


def test_match_filename_ambiguous_substring_returns_none() -> None:
    # "order" is a substring of both candidate stems → ambiguous → no match.
    assert (
        match_filename("order.sql", ["order_detail.sql", "order_header.sql"]) is None
    )


def test_match_filename_unambiguous_substring() -> None:
    assert match_filename("order_x.sql", ["order.sql"]) == "order.sql"


def test_match_filename_no_candidates() -> None:
    assert match_filename("anything.sql", []) is None


# -----------------------------------------------------------------------------
# B1: reconciliation package attribution via source artifacts
# -----------------------------------------------------------------------------


class _FakeScalarResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self) -> list:
        return self._rows


class _QueryFakeSession:
    """Fake session that returns canned rows for ``scalars(stmt).all()``."""

    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self, stmt):  # noqa: ANN001 - mimics Session.scalars
        return _FakeScalarResult(self._rows)


def _make_recon_job(source_artifact_ids: list[str]) -> LakebridgeJob:
    job = _make_job(LakebridgeJobStatus.COMPLETED.value)
    job.job_type = LakebridgeJobType.RECONCILE.value
    job.metadata_json = {"source_artifact_ids": source_artifact_ids}
    return job


def test_find_package_unique_match() -> None:
    pkg_id = uuid.uuid4()
    job = _make_recon_job([str(uuid.uuid4())])
    service = LakebridgeIntegrationService(_QueryFakeSession([pkg_id]))

    assert service._find_package_for_reconciliation(job) == pkg_id


def test_find_package_ambiguous_returns_none() -> None:
    job = _make_recon_job([str(uuid.uuid4())])
    service = LakebridgeIntegrationService(
        _QueryFakeSession([uuid.uuid4(), uuid.uuid4()])
    )

    assert service._find_package_for_reconciliation(job) is None


def test_find_package_no_source_ids_returns_none() -> None:
    job = _make_recon_job([])
    service = LakebridgeIntegrationService(_QueryFakeSession([uuid.uuid4()]))

    assert service._find_package_for_reconciliation(job) is None


# -----------------------------------------------------------------------------
# B3b: sign-off status enum is consistent with the wiring
# -----------------------------------------------------------------------------


def test_signoff_status_uses_pending_not_pending_review() -> None:
    from app.modules.migration_workbench.signoff.schemas import SignoffStatus

    # The reconciliation auto-populate wiring targets PENDING; the broken
    # PENDING_REVIEW member must not exist.
    assert hasattr(SignoffStatus, "PENDING")
    assert not hasattr(SignoffStatus, "PENDING_REVIEW")


# -----------------------------------------------------------------------------
# C1: CLI log truncation (head + tail)
# -----------------------------------------------------------------------------


def test_truncate_log_passes_through_none_and_short() -> None:
    assert _truncate_log(None) is None
    assert _truncate_log("short output") == "short output"


def test_truncate_log_caps_oversized_keeping_head_and_tail() -> None:
    text = "H" * 1000 + "M" * (MAX_CLI_LOG_CHARS) + "T" * 1000
    out = _truncate_log(text)

    assert out is not None
    assert out != text
    assert "[truncated" in out
    assert out.startswith("H" * 1000)  # head preserved
    assert out.endswith("T" * 1000)  # tail preserved


# -----------------------------------------------------------------------------
# C2: deterministic, intentional output-file selection
# -----------------------------------------------------------------------------


def test_select_output_file_prefers_keyword(tmp_path) -> None:  # noqa: ANN001
    (tmp_path / "aaa.json").write_text("{}", encoding="utf-8")
    (tmp_path / "analyzer_report.json").write_text("{}", encoding="utf-8")

    chosen = select_output_file(tmp_path, prefer_keywords=("report",))
    assert chosen is not None
    assert chosen.name == "analyzer_report.json"


def test_select_output_file_deterministic_when_no_keyword(tmp_path) -> None:  # noqa: ANN001
    (tmp_path / "bbb.json").write_text("{}", encoding="utf-8")
    (tmp_path / "aaa.json").write_text("{}", encoding="utf-8")

    chosen = select_output_file(tmp_path, prefer_keywords=("nope",))
    assert chosen is not None
    assert chosen.name == "aaa.json"  # sorted-name fallback


def test_select_output_file_falls_back_to_non_json(tmp_path) -> None:  # noqa: ANN001
    (tmp_path / "result.txt").write_text("data", encoding="utf-8")

    chosen = select_output_file(tmp_path, prefer_keywords=("report",))
    assert chosen is not None
    assert chosen.name == "result.txt"


def test_select_output_file_empty_dir_returns_none(tmp_path) -> None:  # noqa: ANN001
    assert select_output_file(tmp_path, prefer_keywords=("report",)) is None
