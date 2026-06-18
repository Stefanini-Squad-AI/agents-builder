"""Dramatiq actors + broker config.

`uv run dramatiq app.jobs` is the worker entrypoint. The Dramatiq CLI
imports this package, runs `_broker.py` (which sets the global broker),
and then walks submodules to discover every `@dramatiq.actor` for
subscription.

To add a new actor:
1. Create `app/jobs/<name>.py` with `@dramatiq.actor` decorators.
2. Import the module from this `__init__.py` so the CLI discovers it.
"""

# Import order is significant and ruff's import-sorter would reshuffle it.
# ruff: noqa: I001

# The broker MUST be configured before any actor module is imported, so
# that `@dramatiq.actor` decorators attach to our Redis broker (not
# Dramatiq's default).
from app.jobs._broker import broker, use_stub_broker

# Eagerly import every actor module so `dramatiq app.jobs` discovers them.
from app.jobs import (
    draft_skill_body,
    extract_artifact,
    ping,
    run_lakebridge_analyzer,
    run_lakebridge_reconciler,
    run_lakebridge_transpiler,
)

__all__ = [
    "broker",
    "draft_skill_body",
    "extract_artifact",
    "ping",
    "run_lakebridge_analyzer",
    "run_lakebridge_reconciler",
    "run_lakebridge_transpiler",
    "use_stub_broker",
]
