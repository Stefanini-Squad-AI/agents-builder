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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampsMixin, UuidPkMixin
from app.enums import (
    ArtifactKind,
    CardTemplate,
    ExtractionStatus,
    GapSource,
    GapStatus,
    Grouping,
    LlmProvider,
    ProjectStatus,
    values_csv,
)
from app.defaults import (
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_TEMPERATURE,
)

if TYPE_CHECKING:
    from app.domain.backlog import Phase
    from app.domain.identity import Tenant, User
    from app.domain.llm import LlmRun
    from app.domain.skills import Skill
    from app.domain.tech import ProjectTechChoice
    from app.modules.migration_workbench.models import (
        ETLPackage,
        MigrationBusinessRule,
        MigrationConnection,
        MigrationResolvedDecision,
        ProjectMCPConfig,
    )


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

    # Project type and migration settings
    project_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="application",
    )
    source_technology: Mapped[str | None] = mapped_column(String(32))
    target_technology: Mapped[str | None] = mapped_column(String(32))

    # Per-project LLM defaults
    llm_provider: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=DEFAULT_LLM_PROVIDER.value,
    )
    llm_model: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=DEFAULT_LLM_MODEL
    )
    llm_temperature: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=str(DEFAULT_LLM_TEMPERATURE)
    )
    llm_enable_reasoning: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Coverage gaps identified by the most recent ProposeSkillSet run.
    # Threaded into DraftSkillBody so individual skills can attempt to address
    # adjacent gaps in their body content.
    identified_gaps: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
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
    gaps: Mapped[list[ProjectGap]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectGap.created_at",
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
    
    # Migration Workbench relationships
    etl_packages: Mapped[list["ETLPackage"]] = relationship(
        "ETLPackage",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    migration_connections: Mapped[list["MigrationConnection"]] = relationship(
        "MigrationConnection",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    migration_business_rules: Mapped[list["MigrationBusinessRule"]] = relationship(
        "MigrationBusinessRule",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    migration_resolved_decisions: Mapped[list["MigrationResolvedDecision"]] = relationship(
        "MigrationResolvedDecision",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    # Lakebridge integration (one-to-one)
    databricks_config: Mapped["DatabricksConfig | None"] = relationship(
        "DatabricksConfig",
        back_populates="project",
        cascade="all, delete-orphan",
        uselist=False,
    )
    lakebridge_jobs: Mapped[list["LakebridgeJob"]] = relationship(
        "LakebridgeJob",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    # Per-project MCP server configurations
    mcp_configs: Mapped[list["ProjectMCPConfig"]] = relationship(
        "ProjectMCPConfig",
        back_populates="project",
        cascade="all, delete-orphan",
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
    lakebridge_jobs: Mapped[list["LakebridgeJob"]] = relationship(
        "LakebridgeJob",
        back_populates="result_artifact",
    )


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


class ProjectGap(UuidPkMixin, Base):
    """Coverage gap surfaced for a project.

    Initial source is the ProposeSkillSet prompt output. A gap is open until a
    human (or the system, when a draft addresses it) moves it to a terminal
    status: addressed_by_skill, covered_by_mcp, or out_of_scope.
    """

    __tablename__ = "project_gaps"
    __table_args__ = (
        CheckConstraint(f"status IN ({values_csv(GapStatus)})", name="status_valid"),
        CheckConstraint(f"source IN ({values_csv(GapSource)})", name="source_valid"),
        Index("ix_project_gaps__project_status", "project_id", "status"),
        UniqueConstraint("project_id", "title_key", name="project_gap_title_unique"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(Text, nullable=False)
    # Normalised title used for de-duplication when the same gap is surfaced
    # by repeated ProposeSkillSet runs. Lowercase, whitespace-collapsed.
    title_key: Mapped[str] = mapped_column(Text, nullable=False)

    source: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=GapSource.PROPOSE_SKILL_SET.value
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=GapStatus.OPEN.value
    )

    # Terminal-status payload. Exactly zero or one of these is set.
    addressed_by_skill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="SET NULL"),
        nullable=True,
    )
    covered_by_mcp_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="gaps")
