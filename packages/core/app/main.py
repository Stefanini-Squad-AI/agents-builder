"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import health
from app.api import artifacts as artifacts_api
from app.api import auth as auth_api
from app.api import backlog as backlog_api
from app.api import export as export_api
from app.api import gaps as gaps_api
from app.api import lakebridge as lakebridge_api
from app.api import llm_runs as llm_runs_api
from app.api import mcp_config as mcp_config_api
from app.api import project_tech as project_tech_api
from app.api import projects as projects_api
from app.api import qa as qa_api
from app.api import settings as settings_api
from app.api import skills as skills_api
from app.api import tech as tech_api
from app.llm.base import ProviderNotConfigured
from app.logging import configure_logging
from app.modules.migration_workbench import router as migration_router
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

    # CORS middleware — allow Next.js frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_api.router)
    app.include_router(projects_api.router)
    app.include_router(qa_api.router)
    app.include_router(tech_api.router)
    app.include_router(project_tech_api.router)
    app.include_router(artifacts_api.router)
    app.include_router(skills_api.router)
    app.include_router(gaps_api.router)
    app.include_router(backlog_api.router)
    app.include_router(export_api.router)
    app.include_router(llm_runs_api.router)
    app.include_router(settings_api.router)
    app.include_router(mcp_config_api.router)  # MCP Configuration
    app.include_router(lakebridge_api.router)  # Lakebridge Integration
    app.include_router(migration_router)  # Migration Workbench module

    @app.exception_handler(ProviderNotConfigured)
    async def _provider_not_configured_handler(  # type: ignore[no-untyped-def]
        request: Request, exc: ProviderNotConfigured
    ) -> JSONResponse:
        log.warning(
            "provider_not_configured_response",
            provider=exc.provider,
            reason=exc.reason,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    f"LLM provider '{exc.provider}' is not configured: {exc.reason}. "
                    "Set the matching credentials, or change the project's "
                    "LLM provider in Settings."
                ),
                "provider": exc.provider,
                "code": "provider_not_configured",
            },
        )

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

    @app.get("/api/worker-status", tags=["meta"])
    async def worker_status_endpoint() -> dict[str, Any]:
        """Check Dramatiq worker infrastructure status.

        Returns:
            - redis_connected: Is Redis reachable?
            - pending_jobs: Number of jobs waiting in queue
            - workers_detected: Number of active worker consumers
            - status: "healthy" | "no_workers" | "redis_down"
        """
        settings = get_settings()
        worker_status = await health.check_worker_status(settings)
        return {
            "redis_connected": worker_status.redis_connected,
            "pending_jobs": worker_status.pending_jobs,
            "workers_detected": worker_status.workers_detected,
            "status": worker_status.status,
            "error": worker_status.error,
        }

    return app


# Module-level app instance for `uvicorn app.main:app`.
app = create_app()
