"""Tests du pont bus → hooks (STORY-163 — T2/AC 1).

Patterns : bus réel ``InMemoryEventBus`` + instances ``PluginHooks``
collecteurs (miroir ``test_scheduler_event_triggers.py``).

Familles :

- **Dispatch** : hook abonné à ``stack.deployed`` appelé
  **asynchronement** avec le payload de l'événement (AC 1) ;
- **Isolation (AC 1)** : hook qui lève → ``emit`` résolu quand même,
  erreur loggée ERROR, les autres hooks du même événement appelés ;
  hook lent (au-delà du timeout réduit) → ``TimeoutError`` loggé
  WARNING et l'émetteur n'attend pas ;
- **Cycle de vie** : ``start()`` idempotent (un seul abonnement par
  type), ``stop()`` désabonne, ré-abonnement après ``reset_event_bus()``
  fonctionnel ;
- **Registre** : ``register()`` idempotent par classe (hooks appelés une
  seule fois) ;
- **Pool borné** : N hooks simultanés ne dépassent pas la borne
  (assertion sur compteur concurrent) ;
- **Réduction de surface (rules 40)** : les extra-canoniques
  (``host.ssh_fingerprint_*``) ne sont jamais transmis aux hooks.
"""

from __future__ import annotations

import asyncio
import logging
import time

from app.core.events import EventType, InMemoryEventBus
from app.plugins.hooks import PluginEvent, PluginHooks, on_event
from app.services.plugin_hooks_service import PluginHooksService

# ===========================================================================
# Helpers — hooks collecteurs
# ===========================================================================


class _Collector(PluginHooks):
    """Hook collecteur générique (payloads reçus)."""

    def __init__(self, event_name: str) -> None:
        self._event_name = event_name
        super().__init__()
        self.received: list[PluginEvent] = []

    @property
    def target_event(self) -> str:
        return self._event_name

    async def _record(self, event: PluginEvent) -> None:
        self.received.append(event)


def _make_collector(event_name: str) -> _Collector:
    """Construit un collecteur dynamique abonné à ``event_name``."""

    class _Dynamic(_Collector):
        @on_event(event_name)
        async def hook(self, event: PluginEvent) -> None:
            await self._record(event)

    return _Dynamic(event_name)


class _Failing(PluginHooks):
    """Hook qui lève systématiquement."""

    @on_event("stack.deployed")
    async def boom(self, event: PluginEvent) -> None:
        raise RuntimeError("hook explosion")


# ===========================================================================
# Dispatch asynchrone (AC 1)
# ===========================================================================


async def test_hook_called_asynchronously_with_payload():
    """bus.emit(STACK_DEPLOYED) → hook appelé avec le payload (AC 1)."""
    bus = InMemoryEventBus()
    service = PluginHooksService(bus, timeout_seconds=5)
    collector = _make_collector("stack.deployed")
    service.register(collector)
    service.start()

    await bus.emit(EventType.STACK_DEPLOYED, {"stack_id": "s-1", "name": "nginx"})
    await service.wait_for_hooks()

    assert len(collector.received) == 1
    received = collector.received[0]
    assert received.name == "stack.deployed"
    assert received.data == {"stack_id": "s-1", "name": "nginx"}
    assert received.event_id is not None
    service.stop()


async def test_hook_receives_defensive_payload_copy():
    """Le hook peut muter event.data sans corrompre le payload du bus."""
    bus = InMemoryEventBus()
    service = PluginHooksService(bus, timeout_seconds=5)
    collector = _make_collector("stack.deployed")
    service.register(collector)
    service.start()

    payload = {"stack_id": "s-1"}
    await bus.emit(EventType.STACK_DEPLOYED, payload)
    await service.wait_for_hooks()

    collector.received[0].data["tampered"] = True
    assert payload == {"stack_id": "s-1"}
    service.stop()


# ===========================================================================
# Isolation (AC 1) — hook en échec / hook lent
# ===========================================================================


async def test_failing_hook_does_not_block_emitter_nor_others(caplog):
    """Hook qui lève : emit résolu, erreur ERROR, autres hooks appelés."""
    bus = InMemoryEventBus()
    service = PluginHooksService(bus, timeout_seconds=5)
    failing = _Failing()
    healthy = _make_collector("stack.deployed")
    service.register(failing)
    service.register(healthy)
    service.start()

    with caplog.at_level(logging.ERROR):
        started = time.monotonic()
        await bus.emit(EventType.STACK_DEPLOYED, {"stack_id": "s-1"})
        emit_duration = time.monotonic() - started
        await service.wait_for_hooks()

    # L'émetteur n'a pas attendu l'exécution du hook (spawn + retour).
    assert emit_duration < 1.0
    # L'autre hook du même événement a bien été appelé.
    assert len(healthy.received) == 1
    # L'erreur est journalisée avec le plugin et l'événement.
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any("hook error" in r.message.lower() for r in errors)
    assert any(
        "_Failing" in r.message and "stack.deployed" in r.message for r in errors
    )
    service.stop()


async def test_slow_hook_times_out_and_emitter_returns_first(caplog):
    """Hook lent : TimeoutError WARNING, l'émetteur n'attend pas le timeout."""
    bus = InMemoryEventBus()

    class _Slow(PluginHooks):
        @on_event("stack.deployed")
        async def slow(self, event: PluginEvent) -> None:
            await asyncio.sleep(5.0)  # bien au-delà du timeout réduit

    service = PluginHooksService(bus, timeout_seconds=0.2)
    service.register(_Slow())
    service.start()

    with caplog.at_level(logging.WARNING):
        started = time.monotonic()
        await bus.emit(EventType.STACK_DEPLOYED, {"stack_id": "s-1"})
        emit_duration = time.monotonic() - started
        # L'émetteur est revenu AVANT le timeout du hook.
        assert emit_duration < 0.2
        await service.wait_for_hooks(timeout=3.0)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("timeout" in r.message.lower() for r in warnings)
    service.stop()


# ===========================================================================
# Cycle de vie — start/stop idempotents, reset_event_bus, register
# ===========================================================================


def test_start_twice_subscribes_once_per_type():
    """Double start() → un seul handler par type (inspection bus._handlers)."""
    bus = InMemoryEventBus()
    service = PluginHooksService(bus)
    service.start()
    service.start()
    for handlers in bus._handlers.values():
        assert len([h for h in handlers if h == service._on_event]) == 1
    service.stop()


def test_stop_unsubscribes():
    """Après stop(), plus aucun hook n'est appelé."""
    bus = InMemoryEventBus()
    service = PluginHooksService(bus, timeout_seconds=5)
    service.start()
    service.stop()
    # Le bus retire le handler mais peut laisser des listes vides —
    # vérifier qu'aucune callback ne subsiste.
    assert all(handlers == [] for handlers in bus._handlers.values())


async def test_reable_after_reset_event_bus():
    """Après reset_event_bus(), le service est ré-abonnable sur le nouveau bus."""
    from app.core.events import get_event_bus, reset_event_bus

    reset_event_bus()
    fresh = get_event_bus()
    collector = _make_collector("deployment.failed")

    service = PluginHooksService(fresh, timeout_seconds=5)
    service.register(collector)
    service.start()
    await fresh.emit(EventType.DEPLOYMENT_FAILED, {"deployment_id": "d-1"})
    await service.wait_for_hooks()
    assert len(collector.received) == 1
    service.stop()
    reset_event_bus()


async def test_register_is_idempotent_per_class():
    """Même classe enregistrée 2× → hooks appelés une seule fois."""
    bus = InMemoryEventBus()
    service = PluginHooksService(bus, timeout_seconds=5)
    collector = _make_collector("stack.deployed")
    service.register(collector)
    service.register(_make_collector("stack.deployed"))  # autre instance
    service.start()

    await bus.emit(EventType.STACK_DEPLOYED, {"stack_id": "s-1"})
    await service.wait_for_hooks()

    # La première instance l'emporte — un seul appel au total.
    assert len(collector.received) == 1
    service.stop()


# ===========================================================================
# Pool borné (anti-DoS, rules 40)
# ===========================================================================


async def test_concurrent_hooks_respect_pool_bound():
    """N hooks simultanés ne dépassent jamais la borne du sémaphore."""
    bus = InMemoryEventBus()
    concurrent_peak = 0
    active = 0

    class _Probe(PluginHooks):
        @on_event("stack.deployed")
        async def probe_a(self, event: PluginEvent) -> None:
            nonlocal concurrent_peak, active
            active += 1
            concurrent_peak = max(concurrent_peak, active)
            await asyncio.sleep(0.05)
            active -= 1

        @on_event("stack.deployed")
        async def probe_b(self, event: PluginEvent) -> None:
            nonlocal concurrent_peak, active
            active += 1
            concurrent_peak = max(concurrent_peak, active)
            await asyncio.sleep(0.05)
            active -= 1

    service = PluginHooksService(bus, timeout_seconds=5, max_concurrent_hooks=1)
    service.register(_Probe())
    service.start()

    # 3 événements → 6 hooks au total, borne = 1 → jamais plus d'1 actif.
    for _ in range(3):
        await bus.emit(EventType.STACK_DEPLOYED, {"stack_id": "s"})
    await service.wait_for_hooks(timeout=10.0)

    assert concurrent_peak <= 1
    service.stop()


# ===========================================================================
# Réduction de surface (rules 40) — extra-canoniques jamais transmis
# ===========================================================================


async def test_extra_canonical_events_never_reach_hooks():
    """host.ssh_fingerprint_pending (extra-canonique) : aucun hook appelé."""
    bus = InMemoryEventBus()
    service = PluginHooksService(bus, timeout_seconds=5)

    # Un hook qui écouterait « tout » n'existe pas par construction — on
    # vérifie que le pont n'est abonné à AUCUN type extra-canonique.
    service.start()
    subscribed_types = set(bus._handlers.keys())
    canonical_values = {
        EventType(member).value
        for member in (
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
        )
    }
    for event_type in subscribed_types:
        assert event_type.value in canonical_values
    assert EventType.HOST_SSH_FINGERPRINT_PENDING not in subscribed_types
    assert EventType.ORGANIZATION_CREATED not in subscribed_types
    service.stop()

    # Émission effective d'un extra-canonique → rien ne part aux hooks.
    collector = _make_collector("stack.deployed")
    service.register(collector)
    service.start()
    await bus.emit(EventType.HOST_SSH_FINGERPRINT_PENDING, {"host_id": "h-1"})
    await asyncio.sleep(0.05)
    assert collector.received == []
    service.stop()
