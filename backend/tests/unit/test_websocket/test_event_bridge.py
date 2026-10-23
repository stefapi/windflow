"""Tests du pont EventBus → WebSocket étendu (STORY-162, T8 — AC 4).

Familles :

- ``deployment.succeeded`` → broadcast vers la **clé canonique** ET
  ``DEPLOYMENT_STATUS_CHANGED`` (double émission, défaut actif) ;
- ``legacy_ws_event_names_enabled=False`` → clé canonique seule ;
- ``container.started``, ``host.added``, ``stack.deployed``,
  ``plugin.installed`` → broadcast clé canonique ;
- extra-canonique (``organization.created``) → **pas** de broadcast ;
- ``setup/teardown_event_bridge`` : abonnements ajoutés/retirés,
  idempotence ;
- AC 1 explicite : sans Redis, les abonnés ``deployment.*`` du pont
  reçoivent bien les événements (non-régression in-memory).

Le broadcast est espionné via ``patch`` de
``broadcast_to_event_subscribers`` (aucune WebSocket réelle).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import app.websocket.event_bridge as bridge_module
from app.core.events import Event, EventType, InMemoryEventBus
from app.websocket.event_bridge import (
    _canonical_ws_targets,
    setup_event_bridge,
    teardown_event_bridge,
    websocket_event_handler,
)


@pytest.fixture
def spy_broadcast():
    """Espionne broadcast_to_event_subscribers (clés enregistrées).

    Le handler importe la fonction **dans son corps** depuis
    ``app.websocket.broadcasting`` : c'est ce point d'import qu'il faut
    patcher (le module event_bridge n'expose pas l'attribut).
    """
    with patch(
        "app.websocket.broadcasting.broadcast_to_event_subscribers",
        new=AsyncMock(),
    ) as mock:
        yield mock


def _event(event_type: EventType, payload: dict | None = None) -> Event:
    return Event(event_type=event_type, payload=payload or {})


# ===========================================================================
# Cibles de diffusion (mapping étendu)
# ===========================================================================


def test_deployment_succeeded_targets_canonical_and_legacy():
    """Double émission : clé canonique + DEPLOYMENT_STATUS_CHANGED."""
    targets = _canonical_ws_targets(_event(EventType.DEPLOYMENT_SUCCEEDED))
    assert targets == ["deployment.succeeded", "DEPLOYMENT_STATUS_CHANGED"]


def test_deployment_failed_targets_canonical_and_legacy():
    targets = _canonical_ws_targets(_event(EventType.DEPLOYMENT_FAILED))
    assert targets == ["deployment.failed", "DEPLOYMENT_STATUS_CHANGED"]


def test_deployment_created_extra_canonical_still_hits_legacy_key():
    """Extra-canonique deployment.created/rollback → clé legacy conservée."""
    targets = _canonical_ws_targets(_event(EventType.DEPLOYMENT_CREATED))
    assert targets == ["DEPLOYMENT_STATUS_CHANGED"]


def test_other_canonical_events_target_canonical_key_only():
    """container.*/host.*/stack.*/plugin.* → clé canonique seule."""
    cases = {
        EventType.CONTAINER_STARTED: "container.started",
        EventType.HOST_ADDED: "host.added",
        EventType.STACK_DEPLOYED: "stack.deployed",
        EventType.PLUGIN_INSTALLED: "plugin.installed",
        EventType.MACHINE_CREATED: "machine.created",
    }
    for event_type, expected in cases.items():
        assert _canonical_ws_targets(_event(event_type)) == [expected]


def test_extra_canonical_non_deployment_has_no_target():
    """Extra-canonique non déploiement → aucun broadcast (comportement
    historique préservé)."""
    for event_type in (
        EventType.ORGANIZATION_CREATED,
        EventType.USER_LOGIN,
        EventType.SYSTEM_WARNING,
        EventType.HOST_SSH_FINGERPRINT_PENDING,
    ):
        assert _canonical_ws_targets(_event(event_type)) == []


def test_legacy_double_emission_disabled(monkeypatch):
    """LEGACY_WS_EVENT_NAMES_ENABLED=False → clé canonique seule."""
    from app.config import settings

    monkeypatch.setattr(settings, "legacy_ws_event_names_enabled", False)
    targets = _canonical_ws_targets(_event(EventType.DEPLOYMENT_SUCCEEDED))
    assert targets == ["deployment.succeeded"]
    # Les non-déploiements restent identiques
    assert _canonical_ws_targets(_event(EventType.HOST_ADDED)) == ["host.added"]


# ===========================================================================
# Handler : broadcast effectif
# ===========================================================================


async def test_handler_broadcasts_deployment_on_both_keys(spy_broadcast):
    """deployment.succeeded → broadcast canonique + legacy (double)."""
    event = _event(EventType.DEPLOYMENT_SUCCEEDED, {"deployment_id": "d-1"})
    await websocket_event_handler(event)

    keys = [call.args[0] for call in spy_broadcast.await_args_list]
    assert keys == ["deployment.succeeded", "DEPLOYMENT_STATUS_CHANGED"]
    message = spy_broadcast.await_args_list[0].args[1]
    assert message["type"] == "deployment.succeeded"
    assert message["data"] == {"deployment_id": "d-1"}


async def test_handler_broadcasts_canonical_key_for_sample(spy_broadcast):
    """Échantillon canonique → broadcast clé canonique (spec 09)."""
    cases = [
        (EventType.CONTAINER_STARTED, "container.started"),
        (EventType.HOST_ADDED, "host.added"),
        (EventType.STACK_DEPLOYED, "stack.deployed"),
        (EventType.PLUGIN_INSTALLED, "plugin.installed"),
    ]
    for event_type, expected_key in cases:
        spy_broadcast.reset_mock()
        await websocket_event_handler(_event(event_type))
        keys = [call.args[0] for call in spy_broadcast.await_args_list]
        assert keys == [expected_key]


async def test_handler_skips_extra_canonical(spy_broadcast):
    """Extra-canonique non déploiement → aucun broadcast appelé."""
    await websocket_event_handler(_event(EventType.ORGANIZATION_CREATED))
    spy_broadcast.assert_not_awaited()


async def test_handler_broadcast_failure_is_contained(spy_broadcast, caplog):
    """Un échec de broadcast est loggué sans propagation (résilience)."""
    spy_broadcast.side_effect = RuntimeError("ws layer down")
    await websocket_event_handler(_event(EventType.HOST_OFFLINE))
    spy_broadcast.assert_awaited_once()


# ===========================================================================
# setup/teardown : abonnements, idempotence, non-régression in-memory
# ===========================================================================


def test_setup_teardown_bridge_subscriptions():
    """setup ajoute le handler ; teardown le retire ; double appel safe."""
    bus = InMemoryEventBus()
    with patch.object(bridge_module, "event_bus", bus):
        setup_event_bridge()
        bridged = bridge_module.bridged_event_types()
        assert bridged  # non vide : canoniques + deployment.*
        for event_type in bridged:
            assert websocket_event_handler in bus._handlers.get(event_type, [])

        teardown_event_bridge()
        for event_type in bridged:
            assert websocket_event_handler not in bus._handlers.get(event_type, [])

        # Idempotence : second teardown sans erreur
        teardown_event_bridge()


def test_bridged_types_cover_all_canonical_plus_deployment_extras():
    """Le pont couvre les 18 canoniques + deployment.created/rollback."""
    bridged = {member.value for member in bridge_module.bridged_event_types()}
    from app.core.events import CANONICAL_EVENT_NAMES

    assert CANONICAL_EVENT_NAMES <= bridged
    assert {"deployment.created", "deployment.rollback"} <= bridged
    # Extra-canoniques non déploiement exclus
    assert "organization.created" not in bridged


async def test_bridge_receives_deployment_events_without_redis(spy_broadcast):
    """AC 1 (non-régression explicite) : sans Redis, un événement
    ``deployment.succeeded`` publié sur le bus in-memory traverse le pont
    et atteint les abonnés WebSocket."""
    bus = InMemoryEventBus()
    with patch.object(bridge_module, "event_bus", bus):
        setup_event_bridge()
        try:
            await bus.publish(
                _event(EventType.DEPLOYMENT_SUCCEEDED, {"deployment_id": "d-42"})
            )
        finally:
            teardown_event_bridge()

    keys = [call.args[0] for call in spy_broadcast.await_args_list]
    assert "deployment.succeeded" in keys
    assert "DEPLOYMENT_STATUS_CHANGED" in keys
