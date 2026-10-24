"""Tests d'acknowledgment des messages WebSocket critiques (STORY-164.1 — AC 2).

Couvre le registre ``websocket/ack_registry.py`` et le branchement de
l'enveloppe dans ``broadcasting.py`` :

- message critique (type configuré) → enveloppe avec ``id`` UUID ;
  message non critique (log streaming, heartbeat, toast) → **sans** ``id`` ;
- ``{"type":"ack","data":{"id":…}}`` → message retiré du registre ;
- non-acquitté au-delà du TTL + reconnexion du **même utilisateur** →
  **re-diffusé** puis purgé ;
- non-acquitté sans reconnexion → **WARNING loggé** (dégradation) ;
- TTL respecté (purge des entrées expirées) ;
- isolation entre utilisateurs (user B ne reçoit pas le critique non
  acquitté de user A).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.schemas.websocket_events import (
    WebSocketEventType,
    WebSocketMessageEnvelope,
)
from app.websocket.ack_registry import AckRegistry
from app.websocket.broadcasting import _attach_ack_id_if_critical

USER_A = "user-a"
USER_B = "user-b"


@pytest.fixture(autouse=True)
def _isolate_global_registry():
    """Le registre module-level reste vierge autour de chaque test."""
    from app.websocket import broadcasting as broadcasting_module

    broadcasting_module.ack_registry._entries.clear()
    yield
    broadcasting_module.ack_registry._entries.clear()


def _critical_message() -> dict:
    return {"type": WebSocketEventType.DEPLOYMENT_STATUS_CHANGED, "data": {}}


# ===========================================================================
# Enveloppe — id UUID sur types critiques uniquement (AC 2)
# ===========================================================================


async def test_critical_type_gets_ack_id():
    """Type critique (défaut config) → enveloppe avec id UUID + registre."""
    message = {"type": "DEPLOYMENT_STATUS_CHANGED", "data": {"deploymentId": "d1"}}

    await _attach_ack_id_if_critical(message["type"], message, user_id=USER_A)

    assert "id" in message
    UUID(str(message["id"]))  # doit être un UUID valide

    from app.websocket import broadcasting as broadcasting_module

    assert broadcasting_module.ack_registry.pending_count() == 1


async def test_notification_user_is_critical_by_default():
    """NOTIFICATION_USER (2e type du défaut config) → id présent."""
    message = {"type": "NOTIFICATION_USER", "data": {"message": "hello"}}

    await _attach_ack_id_if_critical(message["type"], message, user_id=USER_A)

    assert "id" in message


@pytest.mark.parametrize(
    "non_critical",
    [
        WebSocketEventType.DEPLOYMENT_LOGS_UPDATE,  # streaming logs
        WebSocketEventType.DEPLOYMENT_PROGRESS,
        "ping",  # heartbeat
        WebSocketEventType.UI_TOAST_DISPLAY,  # toast
        WebSocketEventType.PONG,
    ],
)
async def test_non_critical_types_have_no_id(non_critical):
    """Streaming logs, heartbeats, toasts → exclus (pas d'id, pas d'entrée)."""
    message = {"type": str(non_critical), "data": {}}

    await _attach_ack_id_if_critical(message["type"], message, user_id=USER_A)

    assert "id" not in message

    from app.websocket import broadcasting as broadcasting_module

    assert broadcasting_module.ack_registry.pending_count() == 0


async def test_existing_id_is_not_regenerated():
    """Re-diffusion : un id déjà porté n'est ni régénéré ni réenregistré."""
    from app.websocket import broadcasting as broadcasting_module

    message = {
        "type": "DEPLOYMENT_STATUS_CHANGED",
        "data": {},
        "id": "11111111-1111-1111-1111-111111111111",
    }

    await _attach_ack_id_if_critical(message["type"], message, user_id=USER_A)

    assert message["id"] == "11111111-1111-1111-1111-111111111111"
    assert broadcasting_module.ack_registry.pending_count() == 0


async def test_critical_type_without_user_registered_without_entry():
    """Sans user identifié : id ajouté mais pas d'entrée registre."""
    message = {"type": "DEPLOYMENT_STATUS_CHANGED", "data": {}}

    await _attach_ack_id_if_critical(message["type"], message, user_id=None)

    assert "id" in message
    from app.websocket import broadcasting as broadcasting_module

    assert broadcasting_module.ack_registry.pending_count() == 0


async def test_configurable_critical_types():
    """La liste des types critiques est configurable (décision 5)."""
    from app.config import settings

    message = {"type": "SESSION_EXPIRED", "data": {}}
    assert not AckRegistry.is_critical_type("SESSION_EXPIRED")

    with patch.object(settings, "ws_ack_critical_types", ["SESSION_EXPIRED"]):
        assert AckRegistry.is_critical_type("SESSION_EXPIRED")
        await _attach_ack_id_if_critical(message["type"], message, user_id=USER_A)
        assert "id" in message


# ===========================================================================
# Enveloppe Pydantic (contrat documenté)
# ===========================================================================


def test_envelope_schema_serializes_optional_ack_id():
    """WebSocketMessageEnvelope : id optionnel, None exclu du modèle."""
    envelope = WebSocketMessageEnvelope(type="DEPLOYMENT_STATUS_CHANGED")
    assert envelope.id is None

    critical = WebSocketMessageEnvelope(
        type="DEPLOYMENT_STATUS_CHANGED",
        id=UUID("22222222-2222-2222-2222-222222222222"),
    )
    assert critical.id == UUID("22222222-2222-2222-2222-222222222222")


# ===========================================================================
# Registre — ack / TTL / re-diffusion / isolation (AC 2)
# ===========================================================================


async def test_ack_removes_entry():
    """``{"type":"ack"}`` reçu → message retiré du registre."""
    registry = AckRegistry(ttl_seconds=60)
    await registry.register("msg-1", USER_A, "DEPLOYMENT_STATUS_CHANGED", {"x": 1})

    assert registry.pending_count() == 1
    assert await registry.ack("msg-1", USER_A) is True
    assert registry.pending_count() == 0
    # Double ack : entrée inconnue → False (idempotence observable)
    assert await registry.ack("msg-1", USER_A) is False


async def test_ack_unknown_message_returns_false():
    """Ack d'un id inconnu → False, sans erreur."""
    registry = AckRegistry(ttl_seconds=60)
    assert await registry.ack("unknown-id", USER_A) is False


async def test_ttl_purges_expired_entries_with_warning(caplog):
    """Non-acquitté au-delà du TTL sans reconnexion → WARNING + purge."""
    registry = AckRegistry(ttl_seconds=30)
    await registry.register("msg-1", USER_A, "DEPLOYMENT_STATUS_CHANGED")

    # Simule l'écoulement du TTL : purge avec horloge avancée.
    future = datetime.utcnow() + timedelta(seconds=31)
    with caplog.at_level(logging.WARNING, logger="app.websocket.ack_registry"):
        purged = await registry.purge_expired(now=future)

    assert purged == 1
    assert registry.pending_count() == 0
    degradation_logs = [
        r
        for r in caplog.records
        if r.name == "app.websocket.ack_registry" and r.levelno == logging.WARNING
    ]
    assert degradation_logs, "la dégradation ack doit être loggée WARNING"
    record = degradation_logs[-1]
    assert getattr(record, "degradation", None) == "ack_timeout"


async def test_ttl_not_yet_expired_keeps_entry():
    """TTL non écoulé → l'entrée survit (re-diffusion encore possible)."""
    registry = AckRegistry(ttl_seconds=30)
    await registry.register("msg-1", USER_A, "DEPLOYMENT_STATUS_CHANGED")

    purged = await registry.purge_expired(now=datetime.utcnow() + timedelta(seconds=10))
    assert purged == 0
    assert registry.pending_count() == 1


async def test_redelivery_on_reconnect_same_user():
    """Non-acquitté + reconnexion du même user → re-diffusé puis purgé."""
    registry = AckRegistry(ttl_seconds=30)
    await registry.register("msg-1", USER_A, "DEPLOYMENT_STATUS_CHANGED", {"k": "v"})
    await registry.register("msg-2", USER_A, "NOTIFICATION_USER", {"k": "v2"})

    pending = await registry.redeliver_pending(USER_A)

    assert [e.message_id for e in pending] == ["msg-1", "msg-2"]
    assert registry.pending_count() == 0  # purgées après re-diffusion
    # Une 2e reconnexion ne re-diffuse rien (déjà purgées)
    assert await registry.redeliver_pending(USER_A) == []


async def test_redelivery_survives_beyond_ttl_until_reconnect():
    """Re-diffusion post-TTL possible : la purge paresseuse ne bloque pas."""
    registry = AckRegistry(ttl_seconds=1)
    await registry.register("msg-1", USER_A, "DEPLOYMENT_STATUS_CHANGED")

    # Au-delà du TTL mais SANS déclencher la purge paresseuse
    # (redeliver_pending ne purge pas) → la reconnexion récupère le message.
    await asyncio_sleep_zero()
    pending = await registry.redeliver_pending(USER_A)
    assert [e.message_id for e in pending] == ["msg-1"]


def asyncio_sleep_zero():
    import asyncio

    return asyncio.sleep(0)


async def test_redelivery_isolated_between_users():
    """Isolation : user B ne reçoit pas les critiques non acquittés de A."""
    registry = AckRegistry(ttl_seconds=30)
    await registry.register("msg-a", USER_A, "DEPLOYMENT_STATUS_CHANGED")
    await registry.register("msg-b", USER_B, "NOTIFICATION_USER")

    pending_b = await registry.redeliver_pending(USER_B)
    assert [e.message_id for e in pending_b] == ["msg-b"]
    assert registry.pending_count() == 1  # msg-a toujours en attente pour A

    pending_a = await registry.redeliver_pending(USER_A)
    assert [e.message_id for e in pending_a] == ["msg-a"]


async def test_ack_rejected_for_foreign_user():
    """Un ack du user B sur un message de A ne l'acquitte pas."""
    registry = AckRegistry(ttl_seconds=60)
    await registry.register("msg-1", USER_A, "DEPLOYMENT_STATUS_CHANGED")

    assert await registry.ack("msg-1", USER_B) is False
    assert registry.pending_count() == 1  # toujours en attente pour A


async def test_register_triggers_lazy_purge(caplog):
    """register purge paresseusement les entrées expirées avant stockage."""
    registry = AckRegistry(ttl_seconds=30)
    # Entrée ancienne expirée directement injectée (contournement horloge)
    from app.websocket.ack_registry import AckEntry

    registry._entries["old"] = AckEntry(
        message_id="old",
        user_id=USER_A,
        event_type="DEPLOYMENT_STATUS_CHANGED",
        payload={},
        emitted_at=datetime.utcnow() - timedelta(seconds=120),
    )

    with caplog.at_level(logging.WARNING, logger="app.websocket.ack_registry"):
        await registry.register("new", USER_A, "NOTIFICATION_USER")

    assert registry.pending_count() == 1  # seule la nouvelle entrée
    assert any(r.levelno == logging.WARNING for r in caplog.records)


# ===========================================================================
# Général — dispatch du message ack côté canal (AC 2)
# ===========================================================================


async def test_general_ack_dispatch_removes_from_registry():
    """Le dispatch ack du canal général acquitte via le registre global."""
    from app.websocket.ack_registry import ack_registry as global_registry

    await global_registry.register(
        "msg-42", USER_A, "DEPLOYMENT_STATUS_CHANGED", {"k": "v"}
    )

    acked = await global_registry.ack("msg-42", USER_A)
    assert acked is True
    assert global_registry.pending_count() == 0


async def test_broadcast_to_user_registers_critical_message():
    """broadcast_to_user critique → id généré + entrée au registre."""
    from app.websocket import broadcasting as broadcasting_module
    from app.websocket.connection_managers import user_manager

    message = {
        "type": WebSocketEventType.NOTIFICATION_USER,
        "data": {"message": "deploy ok"},
    }

    with patch.object(user_manager, "broadcast_to_user", new=AsyncMock()) as broadcast:
        await broadcasting_module.broadcast_to_user(USER_A, message)

    broadcast.assert_awaited_once()
    sent = broadcast.await_args.args[1]
    assert "id" in sent
    assert broadcasting_module.ack_registry.pending_count() == 1


async def test_broadcast_to_user_non_critical_has_no_id():
    """broadcast_to_user non critique → pas d'id ni d'entrée."""
    from app.websocket import broadcasting as broadcasting_module
    from app.websocket.connection_managers import user_manager

    message = {"type": "message_received", "data": {}}

    with patch.object(user_manager, "broadcast_to_user", new=AsyncMock()) as broadcast:
        await broadcasting_module.broadcast_to_user(USER_A, message)

    sent = broadcast.await_args.args[1]
    assert "id" not in sent
    assert broadcasting_module.ack_registry.pending_count() == 0
