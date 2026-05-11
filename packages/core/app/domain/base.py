"""ORM base + shared column helpers.

- `Base` is the single `DeclarativeBase` every model inherits from.
- A constraint-naming convention is set so Alembic emits stable, readable names
  for indexes, FKs, UQ, CK, PK across migrations.
- Two mixins are provided:
    `UuidPkMixin`    — adds an `id: UUID` PK with a server-side default.
    `TimestampsMixin` — adds `created_at` and `updated_at` (server-defaulted).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Postgres-friendly constraint naming. Alembic autogen uses these names so
# migrations stay diff-stable across runs.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s__%(column_0_N_name)s",
    "uq": "uq_%(table_name)s__%(column_0_N_name)s",
    "ck": "ck_%(table_name)s__%(constraint_name)s",
    "fk": "fk_%(table_name)s__%(column_0_N_name)s__%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UuidPkMixin:
    """Adds `id: UUID` primary key with server-side default."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),  # built into Postgres 13+; no extension
    )


class TimestampsMixin:
    """Adds `created_at` and `updated_at` (both server-defaulted, TZ-aware)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),  # Python-side update; also handled by app code
        nullable=False,
    )
