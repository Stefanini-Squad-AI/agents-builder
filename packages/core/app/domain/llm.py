"""LLM run audit log.

Every LLM call goes through `LLMService.run()` and lands here. Schema includes
reasoning capture columns that stay NULL in MVP and get populated in P3+ when
Anthropic Extended Thinking / OpenAI reasoning models / Ollama think-blocks
are wired.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, UuidPkMixin
from app.domain.enums import LlmProvider, LlmRunKind, LlmRunStatus, values_csv

if TYPE_CHECKING:
    from app.domain.projects import Project


class LlmRun(UuidPkMixin, Base):
    __tablename__ = "llm_runs"
    __table_args__ = (
        CheckConstraint(f"kind IN ({values_csv(LlmRunKind)})", name="kind_valid"),
        CheckConstraint(f"provider IN ({values_csv(LlmProvider)})", name="provider_valid"),
        CheckConstraint(f"status IN ({values_csv(LlmRunStatus)})", name="status_valid"),
        Index("ix_llm_runs__project_created", "project_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)

    prompt_messages_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    response_text: Mapped[str | None] = mapped_column(Text)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Reasoning capture (P3+; populated by providers that expose a reasoning channel)
    reasoning_md: Mapped[str | None] = mapped_column(Text)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_truncated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    extended_thinking_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))

    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped[Project | None] = relationship(back_populates="llm_runs")
