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
from dramatiq.middleware import (
    AgeLimit,
    Callbacks,
    Pipelines,
    Retries,
    ShutdownNotifications,
    TimeLimit,
)

from app.settings import get_settings


def _standard_middleware() -> list:  # type: ignore[type-arg]
    """The middleware list used by both Redis and Stub brokers.

    Order matters: Pipelines/Callbacks must come before Retries.
    """
    return [
        Pipelines(),
        Callbacks(),
        AgeLimit(),
        TimeLimit(),
        ShutdownNotifications(),
        Retries(),
    ]


def _build_redis_broker() -> RedisBroker:
    """Build a RedisBroker with sensible defaults + the project's middleware."""
    settings = get_settings()
    redis_broker = RedisBroker(url=settings.redis_url)  # type: ignore[no-untyped-call]
    redis_broker.middleware = _standard_middleware()
    return redis_broker


# Install the Redis broker as the global default. CLI workers (`dramatiq
# app.jobs`) and the API both share this instance.
broker: RedisBroker | StubBroker = _build_redis_broker()
dramatiq.set_broker(broker)


def use_stub_broker() -> StubBroker:
    """Replace the global broker with an in-process StubBroker.

    Returns the StubBroker so tests can call `.join(queue_name)` to wait
    for queued messages to be processed. Reapplies the same middleware
    list so actor behavior matches production.
    """
    global broker
    stub = StubBroker()
    stub.middleware = _standard_middleware()
    stub.emit_after("process_boot")
    dramatiq.set_broker(stub)
    broker = stub
    return stub
