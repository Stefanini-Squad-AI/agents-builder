"""`ping` actor — a tiny no-op job used as a wiring sanity check.

Verifies that the worker is correctly subscribed to the broker, that an
actor registered in this package is discoverable, and that round-trip
latency is sub-second under healthy conditions.

Usage:
    from app.jobs.ping import ping_actor
    ping_actor.send(message="hello")
"""

from __future__ import annotations

from datetime import UTC, datetime

import dramatiq
import structlog

log = structlog.get_logger(__name__)


@dramatiq.actor(queue_name="default", max_retries=0)
def ping_actor(message: str = "ping") -> None:
    """Log a 'pong' line. Used by the Step 0.9 round-trip smoke test."""
    log.info(
        "ping_received",
        message=message,
        received_at=datetime.now(UTC).isoformat(),
    )
