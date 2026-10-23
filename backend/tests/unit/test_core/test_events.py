"""Tests du bus d'événements canonique — socle (STORY-162, T1/T2/T3).

Familles (AC 1/AC 2/AC 4) :

- **Référentiel** : les 18 valeurs canoniques **exactes** spec 11
  (assertion d'égalité de set) ; ``is_canonical`` vrai/faux ;
  ``resolve_event_name`` sur chaque alias ; extra-canoniques bien
  séparés de la liste canonique ; members supprimés absents ;
- **In-memory (AC 1)** : ``publish`` → handlers abonnés appelés ; un
  handler qui lève n'interrompt pas les autres ; ``unsubscribe`` ;
  ``emit`` avec un ``EventType`` OK ; ``emit`` avec une valeur étrangère
  → ``InvalidEventTypeNameError`` (plus de réencapsule ``system.error``) ;
- **Factory (AC 2)** : sans ``cache_url`` → ``InMemoryEventBus``, aucune
  tentative de connexion, un seul log info « mode léger ».
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest

from app.core.events import (
    CANONICAL_EVENT_NAMES,
    LEGACY_EVENT_ALIASES,
    Event,
    EventType,
    InMemoryEventBus,
    init_event_bus,
    is_canonical,
    reset_event_bus,
    resolve_event_name,
)
from app.core.exceptions import InvalidEventTypeNameError

# ===========================================================================
# Référentiel canonique (T1)
# ===========================================================================

#: Les 18 valeurs exactes de la spec 11 § Liste canonique.
SPEC11_CANONICAL = frozenset(
    {
        "container.created",
        "container.started",
        "container.stopped",
        "container.removed",
        "stack.deployed",
        "stack.updated",
        "stack.removed",
        "machine.created",
        "machine.started",
        "machine.stopped",
        "deployment.started",
        "deployment.succeeded",
        "deployment.failed",
        "host.added",
        "host.removed",
        "host.offline",
        "plugin.installed",
        "plugin.removed",
    }
)


def test_canonical_event_names_match_spec11_exactly():
    """Le référentiel expose exactement les 18 valeurs spec 11."""
    assert CANONICAL_EVENT_NAMES == SPEC11_CANONICAL


def test_every_canonical_value_is_an_event_type_member():
    """Chaque valeur canonique correspond à un membre EventType."""
    members = {member.value for member in EventType}
    assert CANONICAL_EVENT_NAMES <= members


def test_removed_members_are_gone():
    """Les membres retirés n'existent plus (renommés/supprimés)."""
    members = {member.name for member in EventType}
    for removed in (
        "DEPLOYMENT_COMPLETED",
        "TARGET_CREATED",
        "TARGET_UPDATED",
        "TARGET_DELETED",
        "TARGET_HEALTH_CHECK",
        "STACK_DELETED",
        "PLUGIN_UNINSTALLED",
    ):
        assert removed not in members
    values = {member.value for member in EventType}
    for removed_value in (
        "deployment.completed",
        "target.updated",
        "stack.deleted",
        "plugin.uninstalled",
    ):
        assert removed_value not in values


def test_new_canonical_members_exist():
    """Les membres canoniques manquants sont définis."""
    members = {member.name: member.value for member in EventType}
    assert members["DEPLOYMENT_SUCCEEDED"] == "deployment.succeeded"
    assert members["HOST_ADDED"] == "host.added"
    assert members["HOST_REMOVED"] == "host.removed"
    assert members["HOST_OFFLINE"] == "host.offline"
    assert members["STACK_DEPLOYED"] == "stack.deployed"
    assert members["STACK_REMOVED"] == "stack.removed"
    assert members["PLUGIN_REMOVED"] == "plugin.removed"
    assert members["CONTAINER_CREATED"] == "container.created"
    assert members["MACHINE_CREATED"] == "machine.created"


def test_is_canonical_true_for_spec11_false_for_extras():
    """is_canonical vrai sur les 18, faux sur extra-canoniques/alias."""
    for name in SPEC11_CANONICAL:
        assert is_canonical(name), name
    for extra in (
        "organization.created",
        "user.login",
        "system.error",
        "deployment.created",
        "plugin.configured",
        "host.ssh_fingerprint_pending",
    ):
        assert not is_canonical(extra), extra


def test_resolve_event_name_maps_every_alias():
    """Chaque alias legacy se résout vers sa cible canonique."""
    expected = {
        "deployment.completed": "deployment.succeeded",
        "target.created": "host.added",
        "target.updated": "host.offline",
        "target.deleted": "host.removed",
        "target.health_check": "host.offline",
        "stack.deleted": "stack.removed",
        "plugin.uninstalled": "plugin.removed",
    }
    assert LEGACY_EVENT_ALIASES == expected
    for alias, canonical in expected.items():
        assert resolve_event_name(alias) == canonical


def test_resolve_event_name_passthrough_canonical_and_unknown():
    """Canonoique/inconnu retournés inchangés (résolution défensive)."""
    assert resolve_event_name("deployment.succeeded") == "deployment.succeeded"
    assert resolve_event_name("not.an.event") == "not.an.event"


# ===========================================================================
# In-memory : dispatch, isolation d'erreurs, emit strict (T2 — AC 1/AC 4)
# ===========================================================================


async def test_publish_calls_subscribed_handlers():
    """publish → tous les handlers abonnés au type sont appelés (AC 1)."""
    bus = InMemoryEventBus()
    calls: list[Event] = []

    async def handler(event: Event) -> None:
        calls.append(event)

    bus.subscribe(EventType.DEPLOYMENT_SUCCEEDED, handler)
    event = Event(event_type=EventType.DEPLOYMENT_SUCCEEDED, payload={"x": 1})
    await bus.publish(event)

    assert calls == [event]


async def test_handler_error_does_not_block_others():
    """Un handler qui lève n'interrompt pas les suivants (isolation)."""
    bus = InMemoryEventBus()
    calls: list[str] = []

    async def boom(event: Event) -> None:
        raise RuntimeError("handler failure")

    async def ok(event: Event) -> None:
        calls.append("ok")

    bus.subscribe(EventType.HOST_OFFLINE, boom)
    bus.subscribe(EventType.HOST_OFFLINE, ok)
    await bus.publish(Event(event_type=EventType.HOST_OFFLINE))

    assert calls == ["ok"]


async def test_unsubscribe_stops_delivery():
    """unsubscribe → le handler n'est plus appelé."""
    bus = InMemoryEventBus()
    calls: list[Event] = []

    async def handler(event: Event) -> None:
        calls.append(event)

    bus.subscribe(EventType.PLUGIN_INSTALLED, handler)
    bus.unsubscribe(EventType.PLUGIN_INSTALLED, handler)
    await bus.publish(Event(event_type=EventType.PLUGIN_INSTALLED))

    assert calls == []


async def test_emit_with_event_type_publishes():
    """emit(EventType, data) → événement créé et dispatché."""
    bus = InMemoryEventBus()
    calls: list[Event] = []

    async def handler(event: Event) -> None:
        calls.append(event)

    bus.subscribe(EventType.CONTAINER_STARTED, handler)
    await bus.emit(EventType.CONTAINER_STARTED, {"container_id": "abc"})

    assert len(calls) == 1
    assert calls[0].payload == {"container_id": "abc"}
    assert calls[0].event_type is EventType.CONTAINER_STARTED


async def test_emit_with_foreign_type_raises_explicit_error():
    """emit(valeur étrangère, ex. WebSocketEventType) → erreur explicite.

    AC 4 : l'ancienne réencapsulation silencieuse en ``system.error``
    est supprimée — une valeur hors ``EventType`` lève
    ``InvalidEventTypeNameError`` et aucun événement n'est publié.
    """
    bus = InMemoryEventBus()
    system_calls: list[Event] = []

    async def system_handler(event: Event) -> None:
        system_calls.append(event)

    bus.subscribe(EventType.SYSTEM_ERROR, system_handler)

    class FakeWsEventType:
        """Simule un WebSocketEventType étranger au bus."""

        value = "DEPLOYMENT_STATUS_CHANGED"

    with pytest.raises(InvalidEventTypeNameError):
        await bus.emit(FakeWsEventType(), {"whatever": 1})  # type: ignore[arg-type]

    assert system_calls == []  # aucun réencapsule system.error


async def test_event_dict_roundtrip():
    """Event.to_dict/from_dict : sérialisation JSON-safe (transport)."""
    event = Event(
        event_type=EventType.STACK_DEPLOYED,
        payload={"stack_id": "s-1", "services": []},
        aggregate_type="stack",
    )
    restored = Event.from_dict(event.to_dict())
    assert restored.event_type is EventType.STACK_DEPLOYED
    assert restored.payload == {"stack_id": "s-1", "services": []}
    assert str(restored.event_id) == str(event.event_id)


# ===========================================================================
# Factory singleton (T3 — AC 2 : mode léger sans tentative de connexion)
# ===========================================================================


async def test_init_event_bus_without_cache_url_is_inmemory(caplog):
    """Sans cache_url : InMemoryEventBus, aucune connexion, 1 log info."""
    import app.core.events as events_module

    reset_event_bus()
    # Garde : s'assurer que le module n'a PAS tenté redis (monkeypatch
    # de from_url qui échouerait bruyamment si appelé).
    original_from_url = getattr(events_module.aioredis, "from_url", None)
    assert original_from_url is not None or not events_module.REDIS_AVAILABLE

    with caplog.at_level(logging.INFO, logger="windflow.events"):
        bus = await init_event_bus()

    assert type(bus) is InMemoryEventBus
    light_logs = [r for r in caplog.records if "mode léger" in r.message]
    assert len(light_logs) == 1  # un seul log info, pas de warning répété
    reset_event_bus()


async def test_init_event_bus_is_memosized():
    """Le singleton est mémosé : second appel retourne la même instance."""
    reset_event_bus()
    first = await init_event_bus()
    second = await init_event_bus()
    assert first is second
    reset_event_bus()


async def test_init_event_bus_with_unreachable_redis_falls_back(monkeypatch):
    """Redis configuré mais injoignable → fallback in-memory + warning."""
    import app.core.events as events_module

    reset_event_bus()
    # init_event_bus importe settings depuis app.config : patcher la
    # source réelle du setting.
    monkeypatch.setattr("app.config.settings.cache_url", "redis://localhost:1/9")

    class _Unreachable:
        @staticmethod
        def from_url(url: str):
            client = AsyncMock()
            client.ping.side_effect = ConnectionError("refused")
            return client

    monkeypatch.setattr(events_module, "aioredis", _Unreachable)
    monkeypatch.setattr(events_module, "REDIS_AVAILABLE", True)

    bus = await init_event_bus()
    assert type(bus) is InMemoryEventBus
    reset_event_bus()


# ===========================================================================
# STORY-163 — multi-consommateurs : pont hooks + bridge WS + triggers
# scheduler abonnés simultanément, isolation mutuelle préservée.
# ===========================================================================


async def test_multi_consumers_all_notified_with_mutual_isolation():
    """Trois familles de consommateurs sur le même bus : tous notifiés.

    Un consommateur en échec (bridge qui lève) n'affecte ni les hooks
    plugins (pont STORY-163) ni les consommateurs directs du bus.
    """
    from app.plugins.hooks import PluginEvent, PluginHooks, on_event
    from app.services.plugin_hooks_service import PluginHooksService

    bus = InMemoryEventBus()

    # Consommateur 1 : pont hooks plugins (STORY-163).
    received_hooks: list[PluginEvent] = []

    class _StackHooks(PluginHooks):
        @on_event("stack.deployed")
        async def hook(self, event: PluginEvent) -> None:
            received_hooks.append(event)

    bridge = PluginHooksService(bus, timeout_seconds=5)
    bridge.register(_StackHooks())
    bridge.start()

    # Consommateur 2 : handler direct « bridge WS » qui LÈVE.
    async def failing_ws_bridge(event: Event) -> None:
        raise RuntimeError("bridge ws down")

    bus.subscribe(EventType.STACK_DEPLOYED, failing_ws_bridge)

    # Consommateur 3 : handler direct « triggers scheduler ».
    received_scheduler: list[Event] = []

    async def scheduler_like(event: Event) -> None:
        received_scheduler.append(event)

    bus.subscribe(EventType.STACK_DEPLOYED, scheduler_like)

    await bus.emit(EventType.STACK_DEPLOYED, {"stack_id": "s-multi"})
    await bridge.wait_for_hooks()

    # Tous les consommateurs sains ont été notifiés malgré l'échec du
    # consommateur 2 — isolation mutuelle préservée.
    assert len(received_hooks) == 1
    assert received_hooks[0].data == {"stack_id": "s-multi"}
    assert len(received_scheduler) == 1

    bridge.stop()


async def test_canonical_value_of_stack_deployed_reaches_hooks_only_canonical():
    """Le pont ne dispatche que les canoniques — vérif via host.offline."""
    from app.plugins.hooks import PluginEvent, PluginHooks, on_event
    from app.services.plugin_hooks_service import PluginHooksService

    bus = InMemoryEventBus()

    received: list[PluginEvent] = []

    class _HostHooks(PluginHooks):
        @on_event("host.offline")
        async def hook(self, event: PluginEvent) -> None:
            received.append(event)

    bridge = PluginHooksService(bus, timeout_seconds=5)
    bridge.register(_HostHooks())
    bridge.start()

    await bus.emit(EventType.HOST_OFFLINE, {"host_id": "h-1"})
    await bridge.wait_for_hooks()
    assert len(received) == 1

    bridge.stop()
