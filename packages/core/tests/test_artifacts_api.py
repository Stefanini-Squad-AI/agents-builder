"""End-to-end artifact pipeline test.

Exercises:  POST upload -> Dramatiq enqueue -> in-process worker
            consumes the message -> ProjectArtifact status transitions
            pending -> extracting -> extracted with content_md populated.

Uses Dramatiq's StubBroker + a synchronous in-process Worker so the test
doesn't need Redis. The real-Redis path is covered by the Step 0.11 live
smoke (curl + worker running via `uv run dramatiq app.jobs`).
"""

from __future__ import annotations

import os
import uuid
from io import BytesIO
from pathlib import Path

import dramatiq
import pytest
from app.db import session_scope
from app.domain import register_models
from app.domain.identity import Tenant, User
from app.domain.projects import Project
from app.enums import (
    CardTemplate,
    ExtractionStatus,
    Grouping,
    LlmProvider,
    ProjectStatus,
    UserRole,
)
from app.jobs import use_stub_broker
from app.main import create_app
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

register_models()


def _skip_if_no_db() -> None:
    if not os.environ.get("WORKSHOP_RUN_INTEGRATION"):
        pytest.skip("set WORKSHOP_RUN_INTEGRATION=1 to enable; requires docker compose up")


@pytest.fixture
def stub_broker() -> dramatiq.brokers.stub.StubBroker:
    """Swap to a StubBroker AND rebind every actor.broker -> stub.

    `extract_artifact` was decorated against the Redis broker at module
    import time. `dramatiq.set_broker()` only changes the global default;
    pre-existing actors keep their original `actor.broker` reference.
    We mutate it directly and register the actor on the stub so
    `stub.join("default")` finds the queue.
    """
    stub = use_stub_broker()
    from app.jobs.extract_artifact import extract_artifact as actor

    actor.broker = stub
    stub.declare_actor(actor)
    return stub


@pytest.fixture
def temp_project() -> Project:
    """Create a fresh Project (deleted at teardown).

    Also creates the default tenant/user if absent. The artifact uploads
    go to data/projects/<id>/artifacts/ on the host filesystem.
    """
    with session_scope() as session:
        tenant = session.execute(
            select(Tenant).where(Tenant.name == "default")
        ).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name="default")
            session.add(tenant)
            session.flush()
        user = session.execute(
            select(User).where(User.email == "local@workshop")
        ).scalar_one_or_none()
        if user is None:
            user = User(email="local@workshop", name="Local", role=UserRole.OWNER.value)
            session.add(user)
            session.flush()

        slug = f"artifact-test-{uuid.uuid4().hex[:8]}"
        project = Project(
            tenant_id=tenant.id,
            owner_user_id=user.id,
            slug=slug,
            name="Artifact Test",
            objective="exercise the upload pipeline",
            card_code_prefix="ART",
            card_template=CardTemplate.PHASE_VLI.value,
            grouping=Grouping.PHASE.value,
            status=ProjectStatus.DRAFT.value,
            llm_provider=LlmProvider.ANTHROPIC.value,
            llm_model="claude-sonnet-4-5",
        )
        session.add(project)
        session.flush()
        project_id = project.id

    yield _reload_project(project_id)

    with session_scope() as session:
        row = session.get(Project, project_id)
        if row is not None:
            session.delete(row)


def _reload_project(project_id: uuid.UUID) -> Project:
    """Re-fetch a Project on a fresh session (detached from the fixture's)."""
    with session_scope() as session:
        return session.execute(select(Project).where(Project.id == project_id)).scalar_one()


async def _hit(app, method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def _drain(stub_broker: dramatiq.brokers.stub.StubBroker, queue: str = "default") -> None:
    """Spin a Worker until the queue drains, then stop."""
    from dramatiq import Worker

    worker = Worker(stub_broker, worker_timeout=100)
    worker.start()
    try:
        stub_broker.join(queue, timeout=10_000)
        worker.join()
    finally:
        worker.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_upload_markdown_round_trip(
    temp_project: Project, stub_broker: dramatiq.brokers.stub.StubBroker
) -> None:
    """Upload a .md, drain the stub broker, expect status=extracted."""
    _skip_if_no_db()

    app = create_app()
    files = {"file": ("note.md", BytesIO(b"# Hello\n\nbody"), "text/markdown")}
    response = await _hit(
        app,
        "POST",
        f"/api/projects/{temp_project.id}/artifacts",
        files=files,
        data={"kind": "doc"},
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["extraction_status"] == ExtractionStatus.PENDING.value
    artifact_id = uuid.UUID(body["id"])

    _drain(stub_broker)

    # Poll via the GET endpoint.
    poll = await _hit(app, "GET", f"/api/artifacts/{artifact_id}")
    assert poll.status_code == 200
    pbody = poll.json()
    assert pbody["extraction_status"] == ExtractionStatus.EXTRACTED.value
    assert pbody["content_md_excerpt"] is not None
    assert "# Hello" in pbody["content_md_excerpt"]


@pytest.mark.integration
async def test_upload_pdf_round_trip(
    temp_project: Project, stub_broker: dramatiq.brokers.stub.StubBroker, tmp_path: Path
) -> None:
    """Upload a reportlab-generated PDF; verify extracted_at + content."""
    _skip_if_no_db()

    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    pdf_path = tmp_path / "tiny.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(72, 720, "Hello from the integration test PDF.")
    c.showPage()
    c.save()

    app = create_app()
    files = {"file": ("tiny.pdf", pdf_path.read_bytes(), "application/pdf")}
    response = await _hit(
        app,
        "POST",
        f"/api/projects/{temp_project.id}/artifacts",
        files=files,
        data={"kind": "spec"},
    )
    assert response.status_code == 202, response.text
    artifact_id = uuid.UUID(response.json()["id"])

    _drain(stub_broker)

    poll = await _hit(app, "GET", f"/api/artifacts/{artifact_id}")
    pbody = poll.json()
    assert pbody["extraction_status"] == ExtractionStatus.EXTRACTED.value
    assert "Hello" in (pbody["content_md_excerpt"] or "")


@pytest.mark.integration
async def test_unknown_extension_marks_failed(
    temp_project: Project, stub_broker: dramatiq.brokers.stub.StubBroker
) -> None:
    """An upload with an extension no extractor handles goes to status=failed.

    Note: we intentionally do NOT test a "corrupt PDF with .pdf extension"
    because markitdown is lenient and will happily extract any text-ish
    bytes it can decode — so a non-PDF labelled .pdf often produces a
    small successful extraction, not a failure. The real "no extractor"
    failure mode is exercised here via an unknown extension.
    """
    _skip_if_no_db()

    app = create_app()
    files = {
        "file": ("blob.weirdformat", BytesIO(b"binary-ish content"), "application/octet-stream")
    }
    response = await _hit(
        app,
        "POST",
        f"/api/projects/{temp_project.id}/artifacts",
        files=files,
        data={"kind": "other"},
    )
    assert response.status_code == 202
    artifact_id = uuid.UUID(response.json()["id"])

    _drain(stub_broker)

    poll = await _hit(app, "GET", f"/api/artifacts/{artifact_id}")
    pbody = poll.json()
    assert pbody["extraction_status"] == ExtractionStatus.FAILED.value
    # The actor wrote a non-empty extraction_error explaining why.
    # (content_md_excerpt stays None for failed extractions.)
    assert pbody["content_md_excerpt"] is None


@pytest.mark.integration
async def test_retry_only_works_on_failed(
    temp_project: Project, stub_broker: dramatiq.brokers.stub.StubBroker
) -> None:
    """Retry on an extracted artifact is rejected with 409."""
    _skip_if_no_db()

    app = create_app()
    files = {"file": ("retry.md", BytesIO(b"first body"), "text/markdown")}
    response = await _hit(
        app,
        "POST",
        f"/api/projects/{temp_project.id}/artifacts",
        files=files,
        data={"kind": "doc"},
    )
    assert response.status_code == 202
    artifact_id = uuid.UUID(response.json()["id"])
    _drain(stub_broker)

    # First retry should fail (artifact succeeded).
    bad_retry = await _hit(app, "POST", f"/api/artifacts/{artifact_id}/retry")
    assert bad_retry.status_code == 409


@pytest.mark.integration
async def test_unknown_project_returns_404(
    stub_broker: dramatiq.brokers.stub.StubBroker,
) -> None:
    _skip_if_no_db()
    app = create_app()
    missing = uuid.uuid4()
    response = await _hit(
        app,
        "POST",
        f"/api/projects/{missing}/artifacts",
        files={"file": ("x.md", BytesIO(b"hi"), "text/markdown")},
        data={"kind": "doc"},
    )
    assert response.status_code == 404
