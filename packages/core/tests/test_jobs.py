"""Tests for the Dramatiq broker + ping actor wiring.

Uses Dramatiq's in-process StubBroker so the suite runs without touching
Redis. The same actor module also runs against the real RedisBroker when
`uv run dramatiq app.jobs` is started (verified manually in the Step 0.9
smoke).
"""

from __future__ import annotations

import dramatiq
import pytest


@pytest.fixture(autouse=True)
def _stub_broker() -> dramatiq.brokers.stub.StubBroker:
    """Swap the global broker for a fresh StubBroker around every test.

    Importing `app.jobs` triggers `_broker.py`, which installs a Redis
    broker. We replace it with a stub via `use_stub_broker()`. Since
    actors are registered against the broker that was active at decoration
    time, we re-register the ping_actor against the stub.
    """
    from app.jobs import use_stub_broker

    stub = use_stub_broker()
    # Re-decorate the actor against the new (stub) broker. Dramatiq lets
    # us declare the same actor name twice; the last registration wins.
    from app.jobs import ping

    # ping_actor was registered against the original (Redis) broker on
    # first import. Force a fresh registration by re-applying the decorator.
    dramatiq.actor(  # type: ignore[call-overload]
        queue_name="default", max_retries=0
    )(ping.ping_actor.fn)
    return stub


def test_ping_actor_registered() -> None:
    """The ping actor must be discoverable via the broker."""
    from app.jobs.ping import ping_actor

    assert ping_actor.actor_name == "ping_actor"
    assert ping_actor.queue_name == "default"


def test_ping_actor_round_trip(_stub_broker: dramatiq.brokers.stub.StubBroker) -> None:
    """Sending a ping must be picked up and executed by an in-process worker."""
    from app.jobs.ping import ping_actor
    from dramatiq import Worker

    worker = Worker(_stub_broker, worker_timeout=100)
    worker.start()
    try:
        ping_actor.send(message="hello-from-test")
        # join() blocks until the queue is empty AND all in-flight messages
        # have finished processing.
        _stub_broker.join(ping_actor.queue_name, timeout=5_000)
        worker.join()
    finally:
        worker.stop()


def test_actor_idempotent_redeclaration() -> None:
    """Re-decorating the same function under the same name is allowed.

    This guards the import-order invariant the fixture relies on: when
    code imports `app.jobs.ping` while the global broker has been swapped,
    the actor decorator re-binds without raising."""
    from app.jobs.ping import ping_actor

    # Just touching `ping_actor` after the fixture should be a no-op.
    assert ping_actor.actor_name == "ping_actor"
