"""Tests for GET /api/projects and GET /api/projects/{id}.

These are integration tests: they need a live Postgres and the seeded
reference PoCs. Enable with WORKSHOP_RUN_INTEGRATION=1.
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
async def test_list_projects_returns_seeded_projects() -> None:
    _skip_if_no_db()
    r = await _hit("GET", "/api/projects")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    # The seeder loads 3 reference PoCs.
    assert len(body) >= 3, f"Expected at least 3 projects, got {len(body)}"
    # Each project has the required fields.
    for p in body:
        assert "id" in p
        assert "slug" in p
        assert "name" in p
        assert "objective" in p
        assert "status" in p


@pytest.mark.integration
async def test_get_project_by_id() -> None:
    _skip_if_no_db()
    # Fetch list first to get a real ID.
    r_list = await _hit("GET", "/api/projects")
    assert r_list.status_code == 200
    projects = r_list.json()
    assert projects, "No projects seeded"

    project_id = projects[0]["id"]
    r = await _hit("GET", f"/api/projects/{project_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == project_id
    assert body["slug"] == projects[0]["slug"]


@pytest.mark.integration
async def test_get_project_404() -> None:
    _skip_if_no_db()
    r = await _hit("GET", "/api/projects/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
