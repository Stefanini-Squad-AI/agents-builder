"""Service for managing project coverage gaps.

A gap is a project-scoped concern that the system flagged but no skill yet
addresses. Each gap has a lifecycle (open → terminal) so the UI can track
resolution and metrics can be computed (e.g. % gaps closed at project end).

Sources:
    - propose_skill_set: gaps surfaced by the ProposeSkillSet LLM run.
    - manual: gaps a user added by hand.

Terminal statuses:
    - addressed_by_skill: a project skill covers this gap.
    - covered_by_mcp: an external MCP server covers this gap.
    - out_of_scope: explicitly excluded.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domain.projects import ProjectGap
from app.enums import GapSource, GapStatus

# Title normalisation for de-duplication: lowercase + collapse whitespace +
# strip punctuation we don't care about. Two titles that differ only in
# capitalisation/spacing should map to the same row.
_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[.,;:!?\"'`()\[\]{}]+")


def _title_key(title: str) -> str:
    """Compute the de-duplication key for a gap title."""
    s = title.strip().lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s)
    return s.strip()


class GapService:
    """Persist and query coverage gaps."""

    def upsert_from_propose(
        self,
        session: Session,
        project_id: uuid.UUID,
        titles: list[str],
    ) -> int:
        """Upsert gaps coming from a ProposeSkillSet run.

        For each title, insert a new `open` gap if no row exists for
        (project_id, title_key). If a row already exists, leave it alone —
        we never demote a resolved gap back to open.

        Returns:
            Number of rows inserted (i.e. brand new gaps).
        """
        if not titles:
            return 0

        # Build deduped payload by title_key so a single propose run doesn't
        # trigger upsert conflicts within itself.
        seen: dict[str, str] = {}
        for raw in titles:
            if not raw or not raw.strip():
                continue
            key = _title_key(raw)
            if key and key not in seen:
                seen[key] = raw.strip()

        if not seen:
            return 0

        rows = [
            {
                "project_id": project_id,
                "title": title,
                "title_key": key,
                "source": GapSource.PROPOSE_SKILL_SET.value,
                "status": GapStatus.OPEN.value,
            }
            for key, title in seen.items()
        ]

        stmt = (
            pg_insert(ProjectGap)
            .values(rows)
            .on_conflict_do_nothing(
                constraint="project_gap_title_unique",
            )
            .returning(ProjectGap.id)
        )
        result = session.execute(stmt)
        inserted = result.fetchall()
        return len(inserted)

    def list_open(
        self,
        session: Session,
        project_id: uuid.UUID,
    ) -> list[ProjectGap]:
        """Return open gaps for a project, ordered by creation time."""
        return list(
            session.execute(
                select(ProjectGap)
                .where(
                    ProjectGap.project_id == project_id,
                    ProjectGap.status == GapStatus.OPEN.value,
                )
                .order_by(ProjectGap.created_at)
            )
            .scalars()
            .all()
        )

    def list_all(
        self,
        session: Session,
        project_id: uuid.UUID,
    ) -> list[ProjectGap]:
        """Return every gap for a project (any status)."""
        return list(
            session.execute(
                select(ProjectGap)
                .where(ProjectGap.project_id == project_id)
                .order_by(ProjectGap.created_at)
            )
            .scalars()
            .all()
        )

    def mark_addressed_by_skill(
        self,
        session: Session,
        gap: ProjectGap,
        skill_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        rationale: str | None = None,
    ) -> ProjectGap:
        """Move a gap to `addressed_by_skill`. Idempotent on the same skill."""
        gap.status = GapStatus.ADDRESSED_BY_SKILL.value
        gap.addressed_by_skill_id = skill_id
        gap.covered_by_mcp_key = None
        gap.decision_rationale = rationale
        gap.decided_by_user_id = user_id
        gap.decided_at = datetime.now(timezone.utc)
        return gap

    def mark_covered_by_mcp(
        self,
        session: Session,
        gap: ProjectGap,
        mcp_key: str,
        user_id: uuid.UUID | None = None,
        rationale: str | None = None,
    ) -> ProjectGap:
        """Move a gap to `covered_by_mcp`."""
        gap.status = GapStatus.COVERED_BY_MCP.value
        gap.covered_by_mcp_key = mcp_key
        gap.addressed_by_skill_id = None
        gap.decision_rationale = rationale
        gap.decided_by_user_id = user_id
        gap.decided_at = datetime.now(timezone.utc)
        return gap

    def mark_out_of_scope(
        self,
        session: Session,
        gap: ProjectGap,
        user_id: uuid.UUID | None = None,
        rationale: str | None = None,
    ) -> ProjectGap:
        """Move a gap to `out_of_scope`."""
        gap.status = GapStatus.OUT_OF_SCOPE.value
        gap.addressed_by_skill_id = None
        gap.covered_by_mcp_key = None
        gap.decision_rationale = rationale
        gap.decided_by_user_id = user_id
        gap.decided_at = datetime.now(timezone.utc)
        return gap

    def reopen(
        self,
        session: Session,
        gap: ProjectGap,
    ) -> ProjectGap:
        """Send a gap back to `open` and clear decision metadata."""
        gap.status = GapStatus.OPEN.value
        gap.addressed_by_skill_id = None
        gap.covered_by_mcp_key = None
        gap.decision_rationale = None
        gap.decided_by_user_id = None
        gap.decided_at = None
        return gap
