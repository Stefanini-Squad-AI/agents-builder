"""Artifact API: upload, fetch, list, retry, delete.

Endpoints
- POST   /api/projects/{project_ref}/artifacts     multipart upload, 202
- GET    /api/projects/{project_ref}/artifacts     list project artifacts
- GET    /api/artifacts/{artifact_id}              single artifact (poll)
- POST   /api/artifacts/{artifact_id}/retry        re-enqueue extraction
- DELETE /api/artifacts/{artifact_id}              delete artifact + file

The upload handler is intentionally narrow: write file, insert row,
enqueue actor, return 202 + the row. The actor (Step 0.10) does the
extraction asynchronously; the client polls GET to see status transitions.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.projects import Project, ProjectArtifact
from app.enums import ArtifactKind, ExtractionStatus
from app.jobs.extract_artifact import extract_artifact
from app.schemas.views import ArtifactSummary
from app.storage import save_upload

router = APIRouter(tags=["artifacts"])

# 50 MB max body size — same as SPEC section 8.4.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


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


def _to_summary(row: ProjectArtifact) -> ArtifactSummary:
    """ORM row -> API view used by every artifact response.
    
    Full content_md is included — no truncation for richer context.
    """
    return ArtifactSummary(
        id=row.id,
        filename=row.filename,
        kind=ArtifactKind(row.kind),
        extraction_status=ExtractionStatus(row.extraction_status),
        size_bytes=row.size_bytes,
        content_md_excerpt=row.content_md,  # Full content
        content_md_truncated=row.content_md_truncated,
    )


@router.post(
    "/api/projects/{project_ref}/artifacts",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ArtifactSummary,
)
async def upload_artifact(
    project_ref: str,
    file: Annotated[UploadFile, File(..., description="Binary upload")],
    kind: Annotated[str, Form(...)] = ArtifactKind.DOC.value,
    session: Session = Depends(get_session),
) -> ArtifactSummary:
    """Save the file to disk, insert a row in 'pending' state, enqueue extraction."""
    project = _get_project_by_ref(session, project_ref)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_ref} not found")

    try:
        kind_enum = ArtifactKind(kind)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"kind must be one of {[k.value for k in ArtifactKind]}"
        ) from None

    blob = await file.read()
    if len(blob) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(blob)} > {MAX_UPLOAD_BYTES} bytes",
        )

    abs_path, rel_path = save_upload(project.id, file.filename or "upload", blob)

    row = ProjectArtifact(
        project_id=project.id,
        kind=kind_enum.value,
        filename=file.filename or abs_path.name,
        mime_type=file.content_type,
        path=rel_path,
        size_bytes=len(blob),
        extraction_status=ExtractionStatus.PENDING.value,
    )
    session.add(row)
    session.commit()  # commit before enqueue — worker must see the row (P1: TOCTOU fix)

    extract_artifact.send(str(row.id))
    return _to_summary(row)


@router.get(
    "/api/projects/{project_ref}/artifacts",
    response_model=list[ArtifactSummary],
)
def list_project_artifacts(
    project_ref: str,
    session: Session = Depends(get_session),
) -> list[ArtifactSummary]:
    project = _get_project_by_ref(session, project_ref)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_ref} not found")
    rows = (
        session.execute(
            select(ProjectArtifact)
            .where(ProjectArtifact.project_id == project.id)
            .order_by(ProjectArtifact.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_to_summary(r) for r in rows]


@router.get(
    "/api/artifacts/{artifact_id}",
    response_model=ArtifactSummary,
)
def get_artifact(
    artifact_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> ArtifactSummary:
    row = session.get(ProjectArtifact, artifact_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
    return _to_summary(row)


@router.post(
    "/api/artifacts/{artifact_id}/retry",
    response_model=ArtifactSummary,
)
def retry_artifact(
    artifact_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> ArtifactSummary:
    """Reset status to pending and re-enqueue the extraction actor.

    Only `failed` artifacts may be retried — successful ones are immutable
    (deleting + re-uploading is the explicit happy-path for replacement).
    """
    row = session.get(ProjectArtifact, artifact_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
    if row.extraction_status != ExtractionStatus.FAILED.value:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Artifact is in status {row.extraction_status!r}; "
                "only failed artifacts can be retried."
            ),
        )
    row.extraction_status = ExtractionStatus.PENDING.value
    row.extraction_error = None
    session.commit()  # commit before enqueue — worker must see the row (P1: TOCTOU fix)
    extract_artifact.send(str(row.id))
    return _to_summary(row)


@router.delete(
    "/api/artifacts/{artifact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_artifact(
    artifact_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete an artifact record and its file from disk."""
    from app.storage import resolve_artifact_path

    row = session.get(ProjectArtifact, artifact_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")

    # Try to delete the file from disk (ignore if missing)
    try:
        abs_path = resolve_artifact_path(row.path)
        abs_path.unlink(missing_ok=True)
    except Exception:
        pass  # File may already be missing; that's OK

    session.delete(row)
    session.flush()
