"""Export run audit log.

Each successful export (filesystem, zip, or future jira_csv) records a row
with the manifest of what was written (file paths + sizes + SHA256).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, UuidPkMixin
from app.domain.enums import ExportKind, values_csv

if TYPE_CHECKING:
    from app.domain.projects import Project


class Export(UuidPkMixin, Base):
    __tablename__ = "exports"
    __table_args__ = (CheckConstraint(f"kind IN ({values_csv(ExportKind)})", name="kind_valid"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    target_path: Mapped[str | None] = mapped_column(Text)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped[Project] = relationship()
