"""Tests d'intégration ``RedisPubSubEventBus`` avec Redis réel (STORY-162, AC 2).

Skippés si Redis n'est pas joignable (``WINDFLOW_TEST_REDIS_URL``, défaut
``redis://localhost:6379/15`` — DB dédiée aux tests, éphémère).

Familles :

- ``publish`` via ``RedisPubSubEventBus`` → un souscripteur du canal
  ``windflow:events`` reçoit un ``Event`` désérialisable ;
- multi-instances : l'instance B reçoit le message de A et re-dispatche
  vers ses handlers locaux (filtrage ``instance_id`` : pas de double
  dispatch de ses propres messages).
"""

from __future__ import annotations

import asyncio
import json
import os
from uuid import uuid4

import pytest

from app.core.events import EVENTS_CHANNEL, Event, EventType, RedisPubSubEventBus

REDIS_TEST_URL = os.environ.get("WINDFLOW_TEST_REDIS_URL", "redis://localhost:6379/15")

pytestmark = pytest.mark.integration


def _redis_available() -> bool:
    """Probe Redis de test (import + ping synchrone, timeout court)."""
    try:
        import redis  # noqa: PLC0415 — probe dédiée

        client = redis.from_url(REDIS_TEST_URL, socket_connect_timeout=1)
        client.ping()
        client.close()
        return True
    except Exception:
        return False


#: Skip collectif si le Redis de test est absent ( environnement local/CI sans service).
pytest_plugins: list[str] = []


@pytest.fixture(scope="module")
def redis_url() -> str:
    if not _redis_available():
        pytest.skip(f"Redis de test indisponible ({REDIS_TEST_URL})")
    return REDIS_TEST_URL


async def test_publish_visible_on_pubsub_channel(redis_url):
    """publish → un souscripteur du canal reçoit un Event désérialisable."""
    import redis.asyncio as aioredis

    subscriber_client = aioredis.from_url(redis_url)
    bus_client = aioredis.from_url(redis_url)
    bus = RedisPubSubEventBus(bus_client)
    received: list[dict] = []

    pubsub = subscriber_client.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)
    await asyncio.sleep(0.1)  # laisser l'abonnement s'établir

    try:
        event = Event(
            event_type=EventType.DEPLOYMENT_SUCCEEDED,
            payload={"deployment_id": "integ-1", "name": "stack-integ"},
        )
        await bus._publish_to_redis(event)

        raw = await asyncio.wait_for(pubsub.get_message(timeout=2.0), 5.0)
        while raw is not None and raw.get("type") != "message":
            raw = await asyncio.wait_for(pubsub.get_message(timeout=2.0), 5.0)
        assert raw is not None, "aucun message reçu sur windflow:events"
        data = raw["data"]
        if isinstance(data, bytes):
            data = data.decode()
        received.append(json.loads(data))

        message = received[0]
        # Désérialisable en Event complet
        restored = Event.from_dict(message)
        assert restored.event_type is EventType.DEPLOYMENT_SUCCEEDED
        assert restored.payload["deployment_id"] == "integ-1"
        assert message["instance_id"] == bus.instance_id
    finally:
        await pubsub.unsubscribe(EVENTS_CHANNEL)
        await pubsub.close()
        await subscriber_client.close()
        bus._subscriber_task = None  # jamais démarré ici
        await bus.stop()


async def test_multi_instances_remote_dispatch(redis_url):
    """Instance B démarre son subscriber → reçoit A et dispatche en local."""
    import redis.asyncio as aioredis

    client_a = aioredis.from_url(redis_url)
    client_b = aioredis.from_url(redis_url)
    bus_a = RedisPubSubEventBus(client_a)
    bus_b = RedisPubSubEventBus(client_b)
    local_b: list[Event] = []

    async def handler_b(event: Event) -> None:
        local_b.append(event)

    bus_b.subscribe(EventType.HOST_ADDED, handler_b)

    try:
        await bus_b.start()
        await asyncio.sleep(0.2)  # souscription établie

        # A publie (dispatch local A + PUBLISH) ; B doit recevoir et
        # re-dispatcher vers ses handlers locaux.
        calls_a: list[Event] = []

        async def handler_a(event: Event) -> None:
            calls_a.append(event)

        bus_a.subscribe(EventType.HOST_ADDED, handler_a)
        await bus_a.publish(
            Event(
                event_type=EventType.HOST_ADDED,
                payload={"host_id": str(uuid4()), "name": "host-b"},
            )
        )

        for _ in range(50):  # ≤ 5 s
            if local_b:
                break
            await asyncio.sleep(0.1)

        assert len(calls_a) == 1  # dispatch local A intact
        assert len(local_b) == 1  # B a reçu et re-dispatché
        assert local_b[0].event_type is EventType.HOST_ADDED
        assert local_b[0].payload["name"] == "host-b"

        # B publie à son tour : son publish dispatche LOCALEMENT (1 appel
        # handler, par conception) mais l'écho Redis de son propre
        # message doit être filtré — sans le filtrage instance_id on
        # observerait 2 appels (local + re-dispatch de l'écho).
        local_b.clear()
        await bus_b.publish(
            Event(event_type=EventType.HOST_ADDED, payload={"host_id": "b-self"})
        )
        await asyncio.sleep(0.5)
        assert len(local_b) == 1  # dispatch local seul, écho filtré
        assert local_b[0].payload["host_id"] == "b-self"
    finally:
        await bus_a.stop()
        await bus_b.stop()
        await client_a.close()
        await client_b.close()
