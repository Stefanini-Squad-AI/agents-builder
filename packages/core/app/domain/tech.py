"""Tech panorama: TechDimension, TechItem, ProjectTechChoice.

The 13 dimensions and ~70 items are seeded from `app/seed/tech_catalog.yaml`.
Users may add custom items (`is_custom=true`) and the LLM may suggest items
(rows with `source='llm_suggested'`, awaiting `accepted=true`).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
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
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, UuidPkMixin
from app.enums import TechChoiceRole, TechChoiceSource, values_csv

if TYPE_CHECKING:
    from app.domain.projects import Project


class TechDimension(UuidPkMixin, Base):
    __tablename__ = "tech_dimensions"

    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    order_no: Mapped[int] = mapped_column(nullable=False, server_default="0")

    items: Mapped[list[TechItem]] = relationship(
        back_populates="dimension",
        cascade="all, delete-orphan",
        order_by="TechItem.name",
    )


class TechItem(UuidPkMixin, Base):
    __tablename__ = "tech_items"
    __table_args__ = (
        UniqueConstraint("dimension_id", "slug", name="dimension_slug"),
        Index("ix_tech_items__dimension_name", "dimension_id", "name"),
    )

    dimension_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tech_dimensions.id", ondelete="CASCADE"),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    dimension: Mapped[TechDimension] = relationship(back_populates="items")


class ProjectTechChoice(UuidPkMixin, Base):
    __tablename__ = "project_tech_choices"
    __table_args__ = (
        CheckConstraint(f"role IN ({values_csv(TechChoiceRole)})", name="role_valid"),
        CheckConstraint(f"source IN ({values_csv(TechChoiceSource)})", name="source_valid"),
        CheckConstraint(
            "(role = 'tbd' AND tech_item_id IS NULL) "
            "OR (role <> 'tbd' AND tech_item_id IS NOT NULL)",
            name="tbd_requires_null_item",
        ),
        CheckConstraint(
            "llm_confidence IS NULL OR (llm_confidence >= 0 AND llm_confidence <= 1)",
            name="llm_confidence_range",
        ),
        # Partial UNIQUE: same (project, dimension, item) cannot repeat when item is non-null.
        Index(
            "uq_project_tech_choices__project_dimension_item",
            "project_id",
            "dimension_id",
            "tech_item_id",
            unique=True,
            postgresql_where=text("tech_item_id IS NOT NULL"),
        ),
        Index(
            "ix_project_tech_choices__project_dim_order",
            "project_id",
            "dimension_id",
            "order_no",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tech_dimensions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tech_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tech_items.id", ondelete="RESTRICT"),
    )

    role: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=TechChoiceSource.CATALOG.value,
    )
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    llm_rationale: Mapped[str | None] = mapped_column(Text)
    llm_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    order_no: Mapped[int] = mapped_column(nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="tech_choices")
    dimension: Mapped[TechDimension] = relationship()
    tech_item: Mapped[TechItem | None] = relationship()
