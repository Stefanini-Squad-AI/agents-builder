"""Backlog domain: Phase, Card, CardSkill, CardDep, CardInput.

A Phase groups Cards in the phase-VLI family. Cards are the unit of work the
exported .agents/jira-cards/ folder hands to AI agents. Sections (context,
task, outputs, acceptance_criteria) live as separate markdown columns so the
editor can regenerate one section without touching the others.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, TimestampsMixin, UuidPkMixin
from app.enums import (
    CardDepRelation,
    CardInputKind,
    CardStatus,
    CardType,
    Priority,
    values_csv,
)

if TYPE_CHECKING:
    from app.domain.projects import Project
    from app.domain.skills import Skill


class Phase(UuidPkMixin, Base):
    __tablename__ = "phases"
    __table_args__ = (UniqueConstraint("project_id", "code", name="project_code"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description_md: Mapped[str | None] = mapped_column(Text)
    order_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    project: Mapped[Project] = relationship(back_populates="phases")
    cards: Mapped[list[Card]] = relationship(
        back_populates="phase",
        cascade="all, delete-orphan",
        order_by="Card.order_no",
    )


class Card(UuidPkMixin, TimestampsMixin, Base):
    __tablename__ = "cards"
    __table_args__ = (
        UniqueConstraint("phase_id", "code", name="phase_code"),
        CheckConstraint(f"type IN ({values_csv(CardType)})", name="type_valid"),
        CheckConstraint(f"status IN ({values_csv(CardStatus)})", name="status_valid"),
        CheckConstraint(
            f"priority IS NULL OR priority IN ({values_csv(Priority)})",
            name="priority_valid",
        ),
        CheckConstraint(
            "(human_gate = false) OR (human_gate_checklist_md IS NOT NULL "
            "AND char_length(human_gate_checklist_md) > 0)",
            name="gate_requires_checklist",
        ),
        Index("ix_cards__phase_order", "phase_id", "order_no"),
        Index("ix_cards__code", "code"),
    )

    phase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("phases.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    story_points: Mapped[int | None] = mapped_column(Integer)
    priority: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=CardStatus.DRAFT.value,
    )
    human_gate: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    human_gate_checklist_md: Mapped[str | None] = mapped_column(Text)

    context_md: Mapped[str | None] = mapped_column(Text)
    task_md: Mapped[str | None] = mapped_column(Text)
    outputs_md: Mapped[str | None] = mapped_column(Text)
    acceptance_criteria_md: Mapped[str | None] = mapped_column(Text)

    order_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    phase: Mapped[Phase] = relationship(back_populates="cards")
    skill_links: Mapped[list[CardSkill]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        order_by="CardSkill.position",
    )
    inputs: Mapped[list[CardInput]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        order_by="CardInput.order_no",
    )
    deps_out: Mapped[list[CardDep]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        foreign_keys="CardDep.card_id",
    )
    deps_in: Mapped[list[CardDep]] = relationship(
        back_populates="depends_on_card",
        foreign_keys="CardDep.depends_on_card_id",
    )


class CardSkill(Base):
    """Many-to-many `cards <-> skills` with an explicit position field."""

    __tablename__ = "card_skills"

    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", ondelete="CASCADE"),
        primary_key=True,
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    card: Mapped[Card] = relationship(back_populates="skill_links")
    skill: Mapped[Skill] = relationship(back_populates="card_links")


class CardDep(Base):
    """DAG edges between cards. `relation` distinguishes hard deps from parallel-with."""

    __tablename__ = "card_deps"
    __table_args__ = (
        CheckConstraint(
            f"relation IN ({values_csv(CardDepRelation)})",
            name="relation_valid",
        ),
        CheckConstraint(
            "card_id <> depends_on_card_id",
            name="no_self_dep",
        ),
        Index("ix_card_deps__depends_on", "depends_on_card_id"),
    )

    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", ondelete="CASCADE"),
        primary_key=True,
    )
    depends_on_card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    relation: Mapped[str] = mapped_column(
        String(16),
        primary_key=True,
        server_default=CardDepRelation.DEPENDS_ON.value,
    )

    card: Mapped[Card] = relationship(
        back_populates="deps_out",
        foreign_keys=[card_id],
    )
    depends_on_card: Mapped[Card] = relationship(
        back_populates="deps_in",
        foreign_keys=[depends_on_card_id],
    )


class CardInput(UuidPkMixin, Base):
    """An entry in the card's `## Inputs` section. Paths point at skill resources,
    project artifacts, or external references."""

    __tablename__ = "card_inputs"
    __table_args__ = (CheckConstraint(f"kind IN ({values_csv(CardInputKind)})", name="kind_valid"),)

    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    order_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    card: Mapped[Card] = relationship(back_populates="inputs")
