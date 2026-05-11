"""Structured logging via structlog.

Two output modes:
  - console (default in dev) — colored, human-readable.
  - JSON (prod, or when WORKSHOP_LOG_JSON=true) — one structured event per line.

Both modes include a UTC ISO timestamp, log level, logger name, and any context
variables bound via `structlog.contextvars.bind_contextvars(...)`.
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.types import Processor


def configure_logging(*, level: str = "INFO", json_output: bool = False) -> None:
    """Configure structlog. Idempotent — safe to call multiple times."""

    level_int = getattr(logging, level.upper(), logging.INFO)

    # Note: we use structlog.PrintLoggerFactory (not stdlib), so processors that
    # require stdlib's Logger object (e.g. add_logger_name) are intentionally
    # omitted. Logger names are bound via `structlog.get_logger(__name__)`
    # using bind() if/when needed.
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Processor
    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level_int),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
