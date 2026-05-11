"""Project domain: Project, ProjectArtifact, ProjectQaAnswer.

Each project is a separate workspace producing one .agents/ contract. Artifacts
are uploaded files (PDF/DOCX/MD/TXT/CSV/code) that flow through async extraction.
QA answers are the 7-question discovery wizard (first 3 required).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampsMixin, UuidPkMixin
from app.domain.enums import (
    ArtifactKind,
    CardTemplate,
    ExtractionStatus,
    Grouping,
    LlmProvider,
    ProjectStatus,
    values_csv,
)

if TYPE_CHECKING:
    from app.domain.backlog import Phase
    from app.domain.identity import Tenant, User
    from app.domain.llm import LlmRun
    from app.domain.skills import Skill
    from app.domain.tech import ProjectTechChoice


class Project(UuidPkMixin, TimestampsMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="tenant_slug"),
        CheckConstraint(f"status IN ({values_csv(ProjectStatus)})", name="status_valid"),
        CheckConstraint(
            f"card_template IN ({values_csv(CardTemplate)})", name="card_template_valid"
        ),
        CheckConstraint(f"grouping IN ({values_csv(Grouping)})", name="grouping_valid"),
        CheckConstraint(f"llm_provider IN ({values_csv(LlmProvider)})", name="llm_provider_valid"),
        CheckConstraint(
            "char_length(card_code_prefix) BETWEEN 2 AND 8",
            name="card_code_prefix_length",
        ),
        CheckConstraint(
            "llm_temperature >= 0.00 AND llm_temperature <= 2.00",
            name="llm_temperature_range",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    context_md: Mapped[str | None] = mapped_column(Text)

    card_code_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    card_template: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=CardTemplate.PHASE_VLI.value,
    )
    grouping: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=Grouping.PHASE.value,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=ProjectStatus.DRAFT.value,
    )

    # Per-project LLM defaults
    llm_provider: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=LlmProvider.ANTHROPIC.value,
    )
    llm_model: Mapped[str] = mapped_column(Text, nullable=False, server_default="claude-sonnet-4-5")
    llm_temperature: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, server_default="0.20"
    )
    llm_enable_reasoning: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Relationships
    tenant: Mapped[Tenant] = relationship(back_populates="projects")
    owner: Mapped[User] = relationship(
        back_populates="owned_projects",
        foreign_keys=[owner_user_id],
    )
    artifacts: Mapped[list[ProjectArtifact]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    qa_answers: Mapped[list[ProjectQaAnswer]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    tech_choices: Mapped[list[ProjectTechChoice]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    skills: Mapped[list[Skill]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Skill.order_no",
    )
    phases: Mapped[list[Phase]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Phase.order_no",
    )
    llm_runs: Mapped[list[LlmRun]] = relationship(
        back_populates="project",
    )


class ProjectArtifact(UuidPkMixin, Base):
    __tablename__ = "project_artifacts"
    __table_args__ = (
        CheckConstraint(f"kind IN ({values_csv(ArtifactKind)})", name="kind_valid"),
        CheckConstraint(
            f"extraction_status IN ({values_csv(ExtractionStatus)})",
            name="extraction_status_valid",
        ),
        Index("ix_project_artifacts__project_status", "project_id", "extraction_status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    extraction_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=ExtractionStatus.PENDING.value,
    )
    extraction_error: Mapped[str | None] = mapped_column(Text)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extractor_used: Mapped[str | None] = mapped_column(String(32))

    content_md: Mapped[str | None] = mapped_column(Text)
    content_md_truncated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="artifacts")


# Allowed question keys for project_qa_answers.question_key
_QA_KEYS = (
    "business_problem",
    "success_definition",
    "users_and_actors",
    "must_preserve",
    "must_change",
    "compliance",
    "known_gaps",
)


class ProjectQaAnswer(Base):
    __tablename__ = "project_qa_answers"
    __table_args__ = (
        CheckConstraint(
            "question_key IN (" + ", ".join(f"'{k}'" for k in _QA_KEYS) + ")",
            name="question_key_valid",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    question_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    answer_md: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="qa_answers")
