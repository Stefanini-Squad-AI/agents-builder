"""SQLAlchemy engine + session factory.

A single `Engine` per process is created lazily on first use. Tests and Alembic
reuse the same `engine_factory()` so configuration stays centralized.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.settings import get_settings


@lru_cache(maxsize=1)
def engine_factory() -> Engine:
    """Return the singleton SQLAlchemy Engine."""
    settings = get_settings()
    return create_engine(
        settings.database_url,
        future=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


@lru_cache(maxsize=1)
def session_factory() -> sessionmaker[Session]:
    """Return the singleton sessionmaker. Bound to the engine on first call."""
    return sessionmaker(
        bind=engine_factory(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations.

    Usage:
        with session_scope() as session:
            session.add(obj)
            # auto-commit on exit; rollback on exception
    """
    session = session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a transactional Session.

    Used as `Depends(get_session)` in API handlers; commits on a clean
    return path and rolls back on exception.
    """
    session = session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
