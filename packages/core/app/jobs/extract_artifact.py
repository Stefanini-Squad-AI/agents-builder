"""`extract_artifact` Dramatiq actor.

Pipeline (driven from a single DB transaction per state change):

  1. `pending`     -> `extracting`   (worker picked the job)
  2. `extracting`  -> `extracted`    (extractor returned a result)
                  or `failed`       (extractor raised / no matching extractor)

State transitions are idempotent: re-running on an `extracted` artifact
is a no-op. Retries (`workshop artifact retry <id>`) reset status to
`pending` and re-enqueue.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import dramatiq
import structlog
from sqlalchemy import select

from app.db import session_scope
from app.domain import register_models
from app.domain.projects import ProjectArtifact
from app.enums import ExtractionStatus
from app.extractors import NoExtractorError, select_extractor
from app.storage import resolve_artifact_path

register_models()

log = structlog.get_logger(__name__)


@dramatiq.actor(queue_name="default", max_retries=0, time_limit=120_000)
def extract_artifact(artifact_id: str) -> None:
    """Open `artifact_id`, run the chosen extractor, update the row.

    Time-limited to 120 s. Catches every exception and writes the message
    into `extraction_error` so the UI can surface it without the worker
    crashing.
    """
    aid = uuid.UUID(artifact_id)
    log.info("extract_artifact_start", artifact_id=str(aid))

    # Step 1: claim the artifact (status pending -> extracting).
    with session_scope() as session:
        row = session.execute(
            select(ProjectArtifact).where(ProjectArtifact.id == aid)
        ).scalar_one_or_none()
        if row is None:
            log.warning("extract_artifact_not_found", artifact_id=str(aid))
            return
        if row.extraction_status == ExtractionStatus.EXTRACTED.value:
            log.info("extract_artifact_already_done", artifact_id=str(aid))
            return
        if row.extraction_status == ExtractionStatus.EXTRACTING.value:
            log.warning("extract_artifact_already_in_progress", artifact_id=str(aid))
            return
        row.extraction_status = ExtractionStatus.EXTRACTING.value
        row.extraction_error = None
        path_rel = row.path
        filename = row.filename
        mime = row.mime_type

    # Step 2: run the extractor outside the transaction so a slow IO does
    # not hold the row lock the whole time.
    try:
        abs_path = resolve_artifact_path(path_rel)
        extractor = select_extractor(filename, mime_type=mime)
        result = extractor.extract(abs_path)
    except NoExtractorError as e:
        _mark_failed(aid, str(e)[:200])
        return
    except Exception as e:
        log.exception("extract_artifact_unhandled", artifact_id=str(aid))
        _mark_failed(aid, f"{type(e).__name__}: {e}"[:200])
        return

    # Step 3: write the result (status extracting -> extracted or failed).
    with session_scope() as session:
        row = session.execute(select(ProjectArtifact).where(ProjectArtifact.id == aid)).scalar_one()
        if result.error and not result.content_md:
            row.extraction_status = ExtractionStatus.FAILED.value
            row.extraction_error = result.error[:200]
        else:
            row.extraction_status = ExtractionStatus.EXTRACTED.value
            row.extraction_error = result.error  # may be non-None (partial OK)
            row.content_md = result.content_md
            row.content_md_truncated = result.content_md_truncated
            row.extractor_used = result.extractor_used
            row.extracted_at = datetime.now(UTC)
    log.info(
        "extract_artifact_done",
        artifact_id=str(aid),
        status=row.extraction_status,
        chars=len(result.content_md or ""),
        truncated=result.content_md_truncated,
        used=result.extractor_used,
    )


def _mark_failed(aid: uuid.UUID, error_message: str) -> None:
    """Atomic status -> failed update with an error message."""
    with session_scope() as session:
        row = session.execute(select(ProjectArtifact).where(ProjectArtifact.id == aid)).scalar_one()
        row.extraction_status = ExtractionStatus.FAILED.value
        row.extraction_error = error_message
    log.warning("extract_artifact_failed", artifact_id=str(aid), error=error_message)
