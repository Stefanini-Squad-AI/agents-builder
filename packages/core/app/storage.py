"""Filesystem storage for project artifacts.

Files land under `<WORKSHOP_DATA_DIR>/projects/<project_id>/artifacts/`.
Names are `<uuid>-<original-filename>` so the disk path is unique even
when the same filename is re-uploaded. The path stored on the DB row is
RELATIVE to WORKSHOP_DATA_DIR so the workspace is portable across
machines.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.settings import get_settings

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(filename: str) -> str:
    """Strip path separators and unsafe chars from an upload filename."""
    base = Path(filename).name or "upload"
    cleaned = _SAFE_FILENAME_RE.sub("_", base).strip("._")
    return cleaned[:240] or "upload"


def project_artifacts_dir(project_id: uuid.UUID, *, create: bool = True) -> Path:
    """Return the absolute on-disk directory for a project's artifacts."""
    root = Path(get_settings().workshop_data_dir).resolve()
    target = root / "projects" / str(project_id) / "artifacts"
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target


def save_upload(project_id: uuid.UUID, filename: str, content: bytes) -> tuple[Path, str]:
    """Write the uploaded bytes to disk.

    Returns `(absolute_path, relative_path)`. The relative path is what
    the DB row stores; the absolute is what the extractor opens.
    """
    safe = _safe_name(filename)
    unique = f"{uuid.uuid4()}-{safe}"

    target_dir = project_artifacts_dir(project_id)
    abs_path = target_dir / unique
    abs_path.write_bytes(content)

    rel = abs_path.relative_to(Path(get_settings().workshop_data_dir).resolve())
    # Always emit forward slashes so the path is portable across Windows / *nix.
    return abs_path, rel.as_posix()


def resolve_artifact_path(rel_path: str) -> Path:
    """Turn a DB-stored relative path into an absolute path for opening."""
    return (Path(get_settings().workshop_data_dir).resolve() / rel_path).resolve()
