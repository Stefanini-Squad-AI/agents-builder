"""FastAPI application factory.

Step 0.3: only the /health endpoint is exposed. Domain routers land in later
steps (projects, skills, cards, exports, etc.). The factory pattern lets us
build a fresh app instance per-test without import-time side effects.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI

from app import health
from app.api import artifacts as artifacts_api
from app.logging import configure_logging
from app.settings import get_settings

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)
    log.info(
        "workshop_starting",
        version=app.version,
        provider=settings.workshop_default_provider,
        model=settings.workshop_default_model,
    )
    yield
    log.info("workshop_stopping")


def create_app() -> FastAPI:
    """Build a FastAPI instance. Called once at module load and once per test."""
    app = FastAPI(
        title="Agents Workshop API",
        version="0.1.0",
        description=(
            "Generates .agents/ contract folders (skill library + phase-organized "
            "Jira card backlog) for AI-agent-driven projects."
        ),
        lifespan=lifespan,
    )

    app.include_router(artifacts_api.router)

    @app.get("/health", tags=["meta"])
    async def health_endpoint() -> dict[str, Any]:
        """Liveness + readiness check. Returns 200 always; status field reflects health."""
        settings = get_settings()
        db_status, db_error = await health.check_db(settings)
        redis_status, redis_error = await health.check_redis(settings)

        overall = "ok" if (db_status == "ok" and redis_status == "ok") else "degraded"
        body: dict[str, Any] = {
            "status": overall,
            "version": app.version,
            "db": db_status,
            "redis": redis_status,
        }
        if db_error:
            body["db_error"] = db_error
        if redis_error:
            body["redis_error"] = redis_error
        return body

    return app


# Module-level app instance for `uvicorn app.main:app`.
app = create_app()
