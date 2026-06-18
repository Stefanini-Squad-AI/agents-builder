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
from dataclasses import dataclass

import psycopg
import redis

from app.settings import Settings


@dataclass
class WorkerStatus:
    """Status of the Dramatiq worker infrastructure."""

    redis_connected: bool
    pending_jobs: int
    workers_detected: int
    status: str  # "healthy" | "no_workers" | "redis_down"
    error: str | None = None


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


def _check_worker_status_sync(settings: Settings) -> WorkerStatus:
    """Check Dramatiq worker infrastructure status. Synchronous.

    Checks:
    1. Redis connectivity
    2. Pending jobs in the default queue
    3. Active consumers (workers) via PUBSUB NUMSUB on Dramatiq's channel
    """
    try:
        client = redis.from_url(
            settings.redis_url,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        try:
            # Check Redis connectivity
            client.ping()

            # Count pending jobs in the default queue
            # Dramatiq uses 'dramatiq:default.msgs' as the queue key (sorted set)
            pending_jobs = client.zcard("dramatiq:default.msgs") or 0

            # Check for active workers via PUBSUB NUMSUB
            # Dramatiq workers subscribe to 'dramatiq:__events__.<queue>'
            # We check multiple possible channels
            channels_to_check = [
                "dramatiq:__events__.default",
                "dramatiq:default",
            ]
            workers_detected = 0
            for channel in channels_to_check:
                numsub = client.pubsub_numsub(channel)
                if numsub:
                    workers_detected += numsub[0][1] if numsub[0][1] else 0

            # Determine overall status
            if workers_detected > 0:
                status = "healthy"
            else:
                status = "no_workers"

            return WorkerStatus(
                redis_connected=True,
                pending_jobs=int(pending_jobs),
                workers_detected=workers_detected,
                status=status,
            )
        finally:
            client.close()
    except Exception as e:
        return WorkerStatus(
            redis_connected=False,
            pending_jobs=0,
            workers_detected=0,
            status="redis_down",
            error=str(e)[:200],
        )


async def check_worker_status(settings: Settings) -> WorkerStatus:
    """Async wrapper around the sync worker status probe."""
    return await asyncio.to_thread(_check_worker_status_sync, settings)
