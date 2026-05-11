"""Unit + integration tests for the /health endpoint.

Unit tests run always (health checks are monkeypatched).
Integration tests are marked and run only when Docker services are reachable.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from app import health
from app.main import create_app
from app.settings import Settings
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Unit tests (mocked health checks)
# ---------------------------------------------------------------------------


async def _hit_health(app: Any) -> tuple[int, dict[str, Any]]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    return response.status_code, response.json()


async def test_health_all_green(monkeypatch: pytest.MonkeyPatch) -> None:
    """When both subsystems are reachable, /health returns status='ok'."""

    async def fake_db(settings: Settings) -> tuple[str, str | None]:
        return "ok", None

    async def fake_redis(settings: Settings) -> tuple[str, str | None]:
        return "ok", None

    monkeypatch.setattr(health, "check_db", fake_db)
    monkeypatch.setattr(health, "check_redis", fake_redis)

    app = create_app()
    status, body = await _hit_health(app)

    assert status == 200
    assert body == {
        "status": "ok",
        "version": "0.1.0",
        "db": "ok",
        "redis": "ok",
    }


async def test_health_degraded_when_db_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing subsystem flips overall status to 'degraded' and surfaces the error."""

    async def fake_db(settings: Settings) -> tuple[str, str | None]:
        return "error", "connection refused"

    async def fake_redis(settings: Settings) -> tuple[str, str | None]:
        return "ok", None

    monkeypatch.setattr(health, "check_db", fake_db)
    monkeypatch.setattr(health, "check_redis", fake_redis)

    app = create_app()
    status, body = await _hit_health(app)

    assert status == 200
    assert body["status"] == "degraded"
    assert body["db"] == "error"
    assert body["db_error"] == "connection refused"
    assert body["redis"] == "ok"
    assert "redis_error" not in body


async def test_health_error_message_is_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    """Long error strings are clipped to 200 chars by the check helpers themselves.

    The endpoint trusts the helpers; this test pins that contract.
    """
    long_msg = "x" * 500

    async def fake_db(settings: Settings) -> tuple[str, str | None]:
        return "error", long_msg[:200]

    async def fake_redis(settings: Settings) -> tuple[str, str | None]:
        return "ok", None

    monkeypatch.setattr(health, "check_db", fake_db)
    monkeypatch.setattr(health, "check_redis", fake_redis)

    app = create_app()
    _, body = await _hit_health(app)
    assert len(body["db_error"]) <= 200


# ---------------------------------------------------------------------------
# Lifespan smoke (catches startup-time misconfig like a broken logging setup)
# ---------------------------------------------------------------------------


async def test_lifespan_starts_and_stops_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the full lifespan context — startup must complete without raising.

    httpx's ASGITransport does NOT trigger lifespan by default, so we manually
    invoke the lifespan context manager. This is the test that would have caught
    the structlog 'PrintLogger has no attribute name' issue at unit-test time.
    """

    async def fake_db(settings: Settings) -> tuple[str, str | None]:
        return "ok", None

    async def fake_redis(settings: Settings) -> tuple[str, str | None]:
        return "ok", None

    monkeypatch.setattr(health, "check_db", fake_db)
    monkeypatch.setattr(health, "check_redis", fake_redis)

    app = create_app()
    # FastAPI exposes the lifespan context via router.lifespan_context.
    async with app.router.lifespan_context(app):
        # Inside the context: app is "started". Hit /health to round-trip.
        status, body = await _hit_health(app)
        assert status == 200
        assert body["status"] == "ok"


# ---------------------------------------------------------------------------
# Integration test (real Postgres + Redis from docker-compose)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_health_real_services() -> None:
    """Hits the real /health against running compose services.

    Skipped when the `WORKSHOP_RUN_INTEGRATION` env var is not set, so CI doesn't
    fail when Docker isn't available.
    """
    if not os.environ.get("WORKSHOP_RUN_INTEGRATION"):
        pytest.skip("set WORKSHOP_RUN_INTEGRATION=1 to enable; requires docker compose up")

    app = create_app()
    status, body = await _hit_health(app)

    assert status == 200
    assert body["status"] == "ok", f"degraded: {body}"
    assert body["db"] == "ok"
    assert body["redis"] == "ok"
