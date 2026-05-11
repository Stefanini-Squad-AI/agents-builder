"""Domain layer — SQLAlchemy 2.0 ORM models.

Importing this package by itself is *cheap*: it only loads `Base` (which
pulls in SQLAlchemy core) and exposes `register_models()`. Model registration
on `Base.metadata` is opt-in via `register_models()` — Alembic env.py and any
code that needs the full ORM call it explicitly.

This split lets light-weight consumers (e.g. `app.schemas` which imports
`app.domain.enums`) avoid eagerly loading every ORM module, which keeps
import latency and dependency surface low.
"""

from app.domain.base import Base


def register_models() -> None:
    """Import every ORM module so its classes register on `Base.metadata`.

    Idempotent — re-importing modules is a no-op in Python. Call this before
    any operation that introspects `Base.metadata` (Alembic autogeneration,
    `Base.metadata.create_all()`, etc.).
    """
    # Import order does not matter for SQLAlchemy thanks to string-based
    # relationship() targets, but the listed order follows the ERD
    # (identity -> projects -> tech -> skills -> backlog -> llm -> exports).
    from app.domain import (  # noqa: F401 - registration side-effect
        backlog,
        exports,
        identity,
        llm,
        projects,
        skills,
        tech,
    )


__all__ = ["Base", "register_models"]
