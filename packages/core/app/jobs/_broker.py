"""Dramatiq broker configuration.

Configures the global Dramatiq broker with Redis as the transport. Settings
come from `app.settings.get_settings()` so the broker tracks the same
REDIS_URL the rest of the app uses.

The broker is configured at import time so that:
  - `dramatiq app.jobs` (CLI) picks up the same broker the API uses when
    publishing messages.
  - `@dramatiq.actor` registered in any sibling module attaches to it.

Tests swap the broker for a StubBroker via `use_stub_broker()` so they run
synchronously and don't need Redis.
"""

from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker

from app.logging import configure_logging
from app.settings import get_settings

# Configure structlog for the dramatiq worker process. The FastAPI app
# does this in its lifespan, but the worker is a separate Python process
# spawned by `dramatiq app.jobs` and would otherwise inherit structlog's
# silent default config — making actor logs disappear.
configure_logging(level=get_settings().log_level, json_output=get_settings().log_json)


def _build_redis_broker() -> RedisBroker:
    """Build a RedisBroker. Lets Dramatiq install its default middleware list.

    Earlier versions of this module replaced `broker.middleware = [...]`
    with a hand-picked list. That dropped Dramatiq-internal middleware
    that the Redis broker relies on (notably `CurrentMessage` and the
    dead-letter handlers), causing every enqueued message to land in the
    dead-letter queue immediately. The fix is to accept Dramatiq's
    default middleware as-is.
    """
    settings = get_settings()
    return RedisBroker(url=settings.redis_url)  # type: ignore[no-untyped-call]


# Install the Redis broker as the global default. CLI workers (`dramatiq
# app.jobs`) and the API both share this instance.
broker: RedisBroker | StubBroker = _build_redis_broker()
dramatiq.set_broker(broker)


def use_stub_broker() -> StubBroker:
    """Replace the global broker with an in-process StubBroker.

    Uses StubBroker's own default middleware list (same hands-off rule as
    `_build_redis_broker`).
    """
    global broker
    stub = StubBroker()
    stub.emit_after("process_boot")
    dramatiq.set_broker(stub)
    broker = stub
    return stub
