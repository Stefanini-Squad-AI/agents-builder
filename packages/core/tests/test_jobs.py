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
    """Swap to StubBroker and rebind ping_actor.broker to it.

    `dramatiq.set_broker(stub)` only changes the global default; actors
    decorated before the swap keep their original `.broker` reference,
    so `.send()` would still queue into Redis. We mutate `actor.broker`
    directly and register the actor on the stub so `stub.join("default")`
    finds the queue.
    """
    from app.jobs import use_stub_broker
    from app.jobs.ping import ping_actor

    stub = use_stub_broker()
    ping_actor.broker = stub
    stub.declare_actor(ping_actor)
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


def test_actor_broker_is_the_stub(
    _stub_broker: dramatiq.brokers.stub.StubBroker,
) -> None:
    """After the fixture runs, ping_actor.broker must BE the stub.

    This is the assertion that the previous version of the test missed —
    without rebinding `actor.broker`, the round-trip test was a false-pass
    (queue empty, .join() returned without checking anything).
    """
    from app.jobs.ping import ping_actor

    assert ping_actor.broker is _stub_broker
