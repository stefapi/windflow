"""Tests unitaires des fonctions de broadcast WebSocket (STORY-165 — Tâche 2, AC 3).

Couvre ``app/websocket/broadcasting.py`` (62 % → ≥ 90 %) :

- ``broadcast_deployment_log`` / ``broadcast_deployment_status`` /
  ``broadcast_deployment_progress`` / ``broadcast_deployment_complete`` :
  enveloppe ``{type, data}`` + **timestamp auto si absent** (préservé si
  fourni) + payload correct — progress en **snake_case**
  ``deployment_id``/``progress``/``current_step``/``step``/``total_steps``
  (contrat STORY-163 T4) ; complete → statut final ``success``/``failed`` ;
- ``_broadcast_deployment_event`` : ``id`` UUID d'ack sur type critique
  quand ``user_id`` est fourni (+ entrée au registre), pas d'id sinon ;
  dispatch aux plugins appelé avec l'event brut ;
- ``broadcast_to_user`` : ack id + entrée registre pour type critique
  (complément test_ws_ack.py) ;
- ``broadcast_to_event_subscribers`` / ``broadcast_deployment_log_to_subscribers`` :
  délégation au manager + logs debug ;
- helpers ``add_user_connection`` / ``remove_user_connection`` /
  ``subscribe_to_event`` / ``unsubscribe_from_event`` /
  ``subscribe_to_deployment_logs`` : délégation au ``user_manager`` ;
- **spec §9.3** (WEBSOCKET-REAL-TIME.md) : chaque ``broadcast_*`` sans
  aucune connexion enregistrée → **no-op sans exception** (retour
  silencieux, aucune entrée d'ack orpheline pour les types non critiques).

Patterns : managers patchés via ``patch.object(broadcasting.manager, …)``
et ``patch.object(broadcasting.user_manager, …)`` — les singletons réels
restent référencés par le module (jamais remplacés, cohérent avec le code).
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.websocket_events import WebSocketEventType
from app.websocket import broadcasting
from app.websocket.connection_managers import manager, user_manager

LOGGER = "app.websocket.broadcasting"


@pytest.fixture(autouse=True)
def _clean_managers_and_registry():
    """Isolation : singletons globaux + registre d'ack vierges autour de chaque test."""
    manager.active_connections.clear()
    user_manager.user_connections.clear()
    user_manager.user_subscriptions.clear()
    user_manager.deployment_subscribers.clear()
    user_manager.user_plugin_contexts.clear()
    broadcasting.ack_registry._entries.clear()
    yield
    manager.active_connections.clear()
    user_manager.user_connections.clear()
    user_manager.user_subscriptions.clear()
    user_manager.deployment_subscribers.clear()
    user_manager.user_plugin_contexts.clear()
    broadcasting.ack_registry._entries.clear()


# ===========================================================================
# broadcast_deployment_log
# ===========================================================================


class TestBroadcastDeploymentLog:
    async def test_envelope_type_data_and_payload(self):
        with patch.object(
            broadcasting.manager, "broadcast_to_deployment", new=AsyncMock()
        ) as broadcast, patch.object(
            broadcasting.user_manager, "dispatch_to_plugins", new=AsyncMock()
        ):
            await broadcasting.broadcast_deployment_log(
                "dep-1", "line 1", level="warning"
            )

        broadcast.assert_awaited_once()
        envelope = broadcast.await_args.args[1]
        assert envelope["type"] == WebSocketEventType.DEPLOYMENT_LOGS_UPDATE
        data = envelope["data"]
        assert data["deploymentId"] == "dep-1"
        assert data["logs"] == ["line 1"]
        assert data["level"] == "warning"
        # Streaming logs : type non critique → pas d'id d'ack.
        assert "id" not in envelope

    async def test_extra_data_merged(self):
        with patch.object(
            broadcasting.manager, "broadcast_to_deployment", new=AsyncMock()
        ) as broadcast, patch.object(
            broadcasting.user_manager, "dispatch_to_plugins", new=AsyncMock()
        ):
            await broadcasting.broadcast_deployment_log("dep-1", "msg", custom="x")

        assert broadcast.await_args.args[1]["data"]["custom"] == "x"


# ===========================================================================
# broadcast_deployment_status
# ===========================================================================


class TestBroadcastDeploymentStatus:
    async def test_envelope_and_status_payload(self):
        with patch.object(
            broadcasting.manager, "broadcast_to_deployment", new=AsyncMock()
        ) as broadcast, patch.object(
            broadcasting.user_manager, "dispatch_to_plugins", new=AsyncMock()
        ):
            await broadcasting.broadcast_deployment_status(
                "dep-1",
                new_status="running",
                deployment_name="my stack",
                old_status="deploying",
            )

        envelope = broadcast.await_args.args[1]
        assert envelope["type"] == WebSocketEventType.DEPLOYMENT_STATUS_CHANGED
        data = envelope["data"]
        assert data["deploymentId"] == "dep-1"
        assert data["newStatus"] == "running"
        assert data["oldStatus"] == "deploying"
        assert data["deploymentName"] == "my stack"

    async def test_critical_type_with_user_id_gets_ack_id_and_registry(self):
        with patch.object(
            broadcasting.manager, "broadcast_to_deployment", new=AsyncMock()
        ) as broadcast, patch.object(
            broadcasting.user_manager, "dispatch_to_plugins", new=AsyncMock()
        ):
            await broadcasting.broadcast_deployment_status(
                "dep-1", new_status="running", user_id="user-42"
            )

        envelope = broadcast.await_args.args[1]
        assert envelope["id"]
        # Entrée au registre pour re-diffusion à la reconnexion du user-42.
        assert broadcasting.ack_registry.pending_count() == 1

    async def test_critical_type_without_user_id_has_id_but_no_registry(self):
        with patch.object(
            broadcasting.manager, "broadcast_to_deployment", new=AsyncMock()
        ) as broadcast, patch.object(
            broadcasting.user_manager, "dispatch_to_plugins", new=AsyncMock()
        ):
            await broadcasting.broadcast_deployment_status(
                "dep-1", new_status="running"
            )

        envelope = broadcast.await_args.args[1]
        # id généré (le message reste critique côté client) mais aucun
        # destinataire identifié → pas d'entrée au registre.
        assert "id" in envelope
        assert broadcasting.ack_registry.pending_count() == 0

    async def test_extra_id_lands_in_data_not_envelope(self):
        """``id`` via **extra_data atterrit dans ``data`` — l'enveloppe génère le sien.

        Le chemin « id déjà porté, jamais régénéré » (re-diffusion) n'est
        atteignable que via ``broadcast_to_user`` (message dict direct) —
        couvert par ``TestBroadcastToUserAck`` ci-dessous et test_ws_ack.py.
        """
        with patch.object(
            broadcasting.manager, "broadcast_to_deployment", new=AsyncMock()
        ) as broadcast, patch.object(
            broadcasting.user_manager, "dispatch_to_plugins", new=AsyncMock()
        ):
            await broadcasting.broadcast_deployment_status(
                "dep-1", new_status="running", user_id="user-42", id="preset-id"
            )

        envelope = broadcast.await_args.args[1]
        assert envelope["data"]["id"] == "preset-id"
        # L'enveloppe porte son propre id UUID généré + entrée au registre.
        assert envelope["id"] and envelope["id"] != "preset-id"
        assert broadcasting.ack_registry.pending_count() == 1


# ===========================================================================
# broadcast_deployment_progress — payload snake_case (contrat STORY-163 T4)
# ===========================================================================


class TestBroadcastDeploymentProgress:
    async def test_payload_is_snake_case(self):
        with patch.object(
            broadcasting.manager, "broadcast_to_deployment", new=AsyncMock()
        ) as broadcast, patch.object(
            broadcasting.user_manager, "dispatch_to_plugins", new=AsyncMock()
        ):
            await broadcasting.broadcast_deployment_progress(
                "dep-1", progress=45, step="pulling images", total_steps=7
            )

        envelope = broadcast.await_args.args[1]
        assert envelope["type"] == WebSocketEventType.DEPLOYMENT_PROGRESS
        data = envelope["data"]
        # Contrat frontend (types/websocket.ts + handleProgress) — snake_case.
        assert data["deployment_id"] == "dep-1"
        assert data["progress"] == 45
        assert data["current_step"] == "pulling images"
        assert data["total_steps"] == 7
        # step conservé pour les logs internes (deployment_monitor fallback).
        assert data["step"] == "pulling images"
        # Type non critique → pas d'id.
        assert "id" not in envelope

    async def test_total_steps_optional(self):
        with patch.object(
            broadcasting.manager, "broadcast_to_deployment", new=AsyncMock()
        ) as broadcast, patch.object(
            broadcasting.user_manager, "dispatch_to_plugins", new=AsyncMock()
        ):
            await broadcasting.broadcast_deployment_progress("dep-1", 10, "init")

        assert broadcast.await_args.args[1]["data"]["total_steps"] is None


# ===========================================================================
# broadcast_deployment_complete
# ===========================================================================


class TestBroadcastDeploymentComplete:
    async def test_success_maps_to_final_status(self):
        with patch.object(
            broadcasting.manager, "broadcast_to_deployment", new=AsyncMock()
        ) as broadcast, patch.object(
            broadcasting.user_manager, "dispatch_to_plugins", new=AsyncMock()
        ):
            await broadcasting.broadcast_deployment_complete(
                "dep-1", success=True, deployment_name="stack"
            )

        envelope = broadcast.await_args.args[1]
        assert envelope["type"] == WebSocketEventType.DEPLOYMENT_STATUS_CHANGED
        data = envelope["data"]
        assert data["newStatus"] == "success"
        assert data["oldStatus"] == "running"
        assert data["deploymentName"] == "stack"

    async def test_failure_maps_to_failed(self):
        with patch.object(
            broadcasting.manager, "broadcast_to_deployment", new=AsyncMock()
        ) as broadcast, patch.object(
            broadcasting.user_manager, "dispatch_to_plugins", new=AsyncMock()
        ):
            await broadcasting.broadcast_deployment_complete("dep-1", success=False)

        assert broadcast.await_args.args[1]["data"]["newStatus"] == "failed"


# ===========================================================================
# _broadcast_deployment_event — timestamp + dispatch plugins
# ===========================================================================


class TestBroadcastDeploymentEventInternals:
    async def test_timestamp_added_when_missing(self):
        with patch.object(
            broadcasting.manager, "broadcast_to_deployment", new=AsyncMock()
        ) as broadcast, patch.object(
            broadcasting.user_manager, "dispatch_to_plugins", new=AsyncMock()
        ):
            await broadcasting.broadcast_deployment_log("dep-1", "msg")

        assert broadcast.await_args.args[1]["data"]["timestamp"]

    async def test_existing_timestamp_preserved(self):
        with patch.object(
            broadcasting.manager, "broadcast_to_deployment", new=AsyncMock()
        ) as broadcast, patch.object(
            broadcasting.user_manager, "dispatch_to_plugins", new=AsyncMock()
        ):
            await broadcasting.broadcast_deployment_log(
                "dep-1", "msg", timestamp="2026-10-24T10:00:00"
            )

        assert (
            broadcast.await_args.args[1]["data"]["timestamp"] == "2026-10-24T10:00:00"
        )

    async def test_dispatch_to_plugins_called_with_raw_event(self):
        with patch.object(
            broadcasting.manager, "broadcast_to_deployment", new=AsyncMock()
        ), patch.object(
            broadcasting.user_manager, "dispatch_to_plugins", new=AsyncMock()
        ) as dispatch:
            await broadcasting.broadcast_deployment_progress("dep-9", 50, "mid")

        dispatch.assert_awaited_once()
        event_type, event_data = (
            dispatch.await_args.args[0],
            dispatch.await_args.args[1],
        )
        assert event_type == WebSocketEventType.DEPLOYMENT_PROGRESS
        assert event_data["deployment_id"] == "dep-9"
        # Le dispatch reçoit l'event brut (data), pas l'enveloppe.
        assert "type" not in event_data


# ===========================================================================
# broadcast_to_user — ack (complément test_ws_ack.py)
# ===========================================================================


class TestBroadcastToUserAck:
    async def test_critical_message_with_user_registers_ack(self):
        message = {"type": "NOTIFICATION_USER", "data": {"message": "deploy ok"}}

        with patch.object(
            broadcasting.user_manager, "broadcast_to_user", new=AsyncMock()
        ) as broadcast:
            await broadcasting.broadcast_to_user("user-42", message)

        broadcast.assert_awaited_once()
        sent = broadcast.await_args.args[1]
        assert sent["id"]
        assert broadcasting.ack_registry.pending_count() == 1

    async def test_message_already_carried_id_not_reregistered(self):
        message = {
            "type": "NOTIFICATION_USER",
            "data": {},
            "id": "already-there",
        }

        with patch.object(
            broadcasting.user_manager, "broadcast_to_user", new=AsyncMock()
        ):
            await broadcasting.broadcast_to_user("user-42", message)

        assert message["id"] == "already-there"
        assert broadcasting.ack_registry.pending_count() == 0


# ===========================================================================
# broadcast_to_event_subscribers / broadcast_deployment_log_to_subscribers
# ===========================================================================


class TestSubscriberBroadcastDelegation:
    async def test_event_subscribers_delegates_to_manager(self, caplog):
        message = {"type": "DEPLOYMENT_STATUS_CHANGED", "data": {}}

        with patch.object(
            broadcasting.user_manager,
            "broadcast_to_event_subscribers",
            new=AsyncMock(),
        ) as delegate:
            with caplog.at_level(logging.DEBUG, logger=LOGGER):
                await broadcasting.broadcast_to_event_subscribers(
                    "DEPLOYMENT_STATUS_CHANGED", message
                )

        delegate.assert_awaited_once_with("DEPLOYMENT_STATUS_CHANGED", message)
        assert any(
            "Broadcasting to event subscribers" in r.message for r in caplog.records
        )
        assert any(
            "Broadcast to event subscribers completed" in r.message
            for r in caplog.records
        )

    async def test_deployment_log_subscribers_delegates_to_manager(self):
        message = {"type": "DEPLOYMENT_LOGS_UPDATE", "data": {"logs": ["x"]}}

        with patch.object(
            broadcasting.user_manager,
            "broadcast_deployment_log_to_subscribers",
            new=AsyncMock(),
        ) as delegate:
            await broadcasting.broadcast_deployment_log_to_subscribers("dep-1", message)

        delegate.assert_awaited_once_with("dep-1", message)


# ===========================================================================
# Helpers de gestion des connexions / abonnements — délégation
# ===========================================================================


class TestConnectionHelpersDelegate:
    async def test_add_user_connection_delegates(self):
        websocket = AsyncMock()
        context = object()

        with patch.object(
            broadcasting.user_manager, "add_connection", new=AsyncMock()
        ) as add:
            await broadcasting.add_user_connection("user-1", websocket, context=context)

        add.assert_awaited_once_with("user-1", websocket, context)

    async def test_remove_user_connection_delegates(self):
        websocket = AsyncMock()

        with patch.object(
            broadcasting.user_manager, "remove_connection", new=AsyncMock()
        ) as remove:
            await broadcasting.remove_user_connection("user-1", websocket)

        remove.assert_awaited_once_with("user-1", websocket)

    async def test_subscribe_to_event_delegates(self):
        websocket = AsyncMock()

        with patch.object(
            broadcasting.user_manager, "subscribe_to_event", new=AsyncMock()
        ) as subscribe:
            await broadcasting.subscribe_to_event(
                "user-1", "DEPLOYMENT_STATUS_CHANGED", websocket
            )

        subscribe.assert_awaited_once_with(
            "user-1", "DEPLOYMENT_STATUS_CHANGED", websocket
        )

    async def test_unsubscribe_from_event_delegates(self):
        websocket = AsyncMock()

        with patch.object(
            broadcasting.user_manager, "unsubscribe_from_event", new=AsyncMock()
        ) as unsubscribe:
            await broadcasting.unsubscribe_from_event(
                "user-1", "DEPLOYMENT_STATUS_CHANGED", websocket
            )

        unsubscribe.assert_awaited_once_with(
            "user-1", "DEPLOYMENT_STATUS_CHANGED", websocket
        )

    async def test_subscribe_to_deployment_logs_delegates(self):
        websocket = AsyncMock()

        with patch.object(
            broadcasting.user_manager,
            "subscribe_to_deployment_logs",
            new=AsyncMock(),
        ) as subscribe:
            await broadcasting.subscribe_to_deployment_logs(
                "user-1", "dep-1", websocket
            )

        subscribe.assert_awaited_once_with("user-1", "dep-1", websocket)


# ===========================================================================
# spec §9.3 — broadcast sans aucun client connecté = no-op sans exception
# ===========================================================================


class TestSpec93BroadcastWithoutClients:
    """Portage spec WEBSOCKET-REAL-TIME.md §9.3 : aucun client → silence.

    Managers réels (vides, purgés par la fixture) : chaque fonction doit
    retourner sans lever.
    """

    async def test_all_deployment_broadcasts_are_noops(self):
        await broadcasting.broadcast_deployment_log("dep-x", "line")
        await broadcasting.broadcast_deployment_status("dep-x", "running")
        await broadcasting.broadcast_deployment_progress("dep-x", 10, "init")
        await broadcasting.broadcast_deployment_complete("dep-x", success=True)

    async def test_user_broadcasts_are_noops(self):
        await broadcasting.broadcast_to_user(
            "ghost-user", {"type": "NOTIFICATION_USER", "data": {}}
        )
        await broadcasting.broadcast_to_event_subscribers(
            "DEPLOYMENT_STATUS_CHANGED",
            {"type": "DEPLOYMENT_STATUS_CHANGED", "data": {}},
        )
        await broadcasting.broadcast_deployment_log_to_subscribers(
            "dep-x", {"type": "DEPLOYMENT_LOGS_UPDATE", "data": {}}
        )
        # Un critique **adressé** à un utilisateur reste au registre même sans
        # connexion active (spec §8 : re-diffusion à sa prochaine connexion).
        assert broadcasting.ack_registry.pending_count() == 1
        entry = next(iter(broadcasting.ack_registry._entries.values()))
        assert entry.user_id == "ghost-user"

    async def test_noop_broadcast_writes_nothing_to_managers(self):
        await broadcasting.broadcast_deployment_status("dep-x", "running")
        assert manager.active_connections == {}
        assert user_manager.user_connections == {}
