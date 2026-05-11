"""Liveness/readiness checks for /health.

Implementation note (Windows): on Python 3.12 the default Windows event loop
is ProactorEventLoop, which the *async* clients of both psycopg (3.x) and
redis (asyncio) refuse to run on. Rather than force a SelectorEventLoop on the
whole process — which would conflict with libraries that need Proactor (e.g.
subprocess streams used by Dramatiq later) — we run the (cheap) checks via the
sync clients on a worker thread using `asyncio.to_thread`.

For real DB work in Step 0.4+ we move to SQLAlchemy 2.0's async engine, which
handles the Windows loop story internally.
"""

from __future__ import annotations

import asyncio

import psycopg
import redis

from app.settings import Settings


def _psycopg_dsn(sqlalchemy_url: str) -> str:
    """Strip the SQLAlchemy driver suffix so psycopg accepts the URL.

    `postgresql+psycopg://...` -> `postgresql://...`
    """
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _check_db_sync(settings: Settings) -> tuple[str, str | None]:
    """Run `SELECT 1` against Postgres. Synchronous."""
    try:
        with (
            psycopg.connect(
                _psycopg_dsn(settings.database_url),
                connect_timeout=2,
            ) as conn,
            conn.cursor() as cur,
        ):
            cur.execute("SELECT 1")
            cur.fetchone()
        return "ok", None
    except Exception as e:
        return "error", str(e)[:200]


def _check_redis_sync(settings: Settings) -> tuple[str, str | None]:
    """PING Redis. Synchronous."""
    try:
        client = redis.from_url(
            settings.redis_url,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        try:
            client.ping()
        finally:
            client.close()
        return "ok", None
    except Exception as e:
        return "error", str(e)[:200]


async def check_db(settings: Settings) -> tuple[str, str | None]:
    """Async wrapper around the sync DB probe."""
    return await asyncio.to_thread(_check_db_sync, settings)


async def check_redis(settings: Settings) -> tuple[str, str | None]:
    """Async wrapper around the sync Redis probe."""
    return await asyncio.to_thread(_check_redis_sync, settings)
