"""Identity domain: users + tenants.

In MVP a single user is seeded (`local@workshop`) and a single default tenant
is created. The schema is multi-tenant-ready so adding team mode later is a
no-migration change.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.base import Base, UuidPkMixin
from app.domain.enums import UserRole, values_csv

if TYPE_CHECKING:
    from app.domain.projects import Project


class Tenant(UuidPkMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    projects: Mapped[list[Project]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )


class User(UuidPkMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            f"role IN ({values_csv(UserRole)})",
            name="role_valid",
        ),
    )

    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=UserRole.OWNER.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    owned_projects: Mapped[list[Project]] = relationship(
        back_populates="owner",
        foreign_keys="Project.owner_user_id",
    )
