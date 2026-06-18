"""Skill domain: Skill + SkillResource.

A Skill is one .agents/skills/<slug>/SKILL.md file (YAML frontmatter + body).
SkillResources are the optional `resources/*.{md,sql,yaml,...}` files that sit
next to it (heavily used by analyzer-kind skills in the VLI reference PoC).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampsMixin, UuidPkMixin
from app.enums import SkillDraftStatus, SkillKind, SkillResourceLanguage, values_csv

if TYPE_CHECKING:
    from app.domain.backlog import CardSkill
    from app.domain.projects import Project


class Skill(UuidPkMixin, TimestampsMixin, Base):
    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", name="project_slug"),
        CheckConstraint(f"kind IN ({values_csv(SkillKind)})", name="kind_valid"),
        CheckConstraint(
            f"draft_status IN ({values_csv(SkillDraftStatus)})",
            name="draft_status_valid",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    order_no: Mapped[int] = mapped_column(nullable=False, server_default="0")

    # Drafting status tracking
    draft_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=SkillDraftStatus.NONE.value
    )
    last_llm_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    draft_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="skills")
    resources: Mapped[list[SkillResource]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
        order_by="SkillResource.order_no",
    )
    card_links: Mapped[list[CardSkill]] = relationship(back_populates="skill")


class SkillResource(UuidPkMixin, Base):
    __tablename__ = "skill_resources"
    __table_args__ = (
        UniqueConstraint("skill_id", "filename", name="skill_filename"),
        CheckConstraint(
            f"language IN ({values_csv(SkillResourceLanguage)})",
            name="language_valid",
        ),
    )

    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=SkillResourceLanguage.MARKDOWN.value,
    )
    order_no: Mapped[int] = mapped_column(nullable=False, server_default="0")

    skill: Mapped[Skill] = relationship(back_populates="resources")
