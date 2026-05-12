"""Tests for GET /api/tech/dimensions and GET /api/tech/dimensions/{slug}.

Integration tests: need live Postgres + seeded tech catalog.
Enable with WORKSHOP_RUN_INTEGRATION=1.
"""

from __future__ import annotations

import os

import pytest
from app.domain import register_models
from app.main import create_app
from httpx import ASGITransport, AsyncClient

register_models()


def _skip_if_no_db() -> None:
    if not os.environ.get("WORKSHOP_RUN_INTEGRATION"):
        pytest.skip("set WORKSHOP_RUN_INTEGRATION=1 to enable; requires docker compose up")


async def _hit(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.integration
async def test_list_dimensions_returns_13() -> None:
    _skip_if_no_db()
    r = await _hit("GET", "/api/tech/dimensions")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 13, f"Expected 13 tech dimensions, got {len(body)}"
    # Each dimension has required fields.
    for d in body:
        assert "id" in d
        assert "slug" in d
        assert "name" in d
        assert isinstance(d["items"], list)


@pytest.mark.integration
async def test_list_dimensions_items_non_empty() -> None:
    _skip_if_no_db()
    r = await _hit("GET", "/api/tech/dimensions")
    body = r.json()
    total_items = sum(len(d["items"]) for d in body)
    assert total_items >= 70, f"Expected >= 70 items across all dimensions, got {total_items}"


@pytest.mark.integration
async def test_get_dimension_by_slug() -> None:
    _skip_if_no_db()
    r = await _hit("GET", "/api/tech/dimensions/languages")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "languages"
    assert len(body["items"]) > 0


@pytest.mark.integration
async def test_get_dimension_404() -> None:
    _skip_if_no_db()
    r = await _hit("GET", "/api/tech/dimensions/does_not_exist")
    assert r.status_code == 404
