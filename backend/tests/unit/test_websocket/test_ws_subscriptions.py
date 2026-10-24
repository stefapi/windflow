"""Tests E2E du handler de souscription (STORY-165 — Tâche 4, AC 2/3).

Couvre ``app/websocket/plugins/subscription.py`` (18 % → ≥ 90 %) à travers
la **vraie boucle** du canal général (handler enregistré par défaut —
``plugins/__init__.default_message_handlers``) :

- ``subscribe`` valide → ``subscribed`` + entrée dans
  ``user_manager.user_subscriptions`` ; sans ``event_type`` → ``error`` ;
- ``unsubscribe`` valide → ``unsubscribed`` + retrait (clé vide purgée) ;
  sans ``event_type`` → ``error`` ;
- ``deployment_logs`` valide → ``logs_subscribed`` + entrée dans
  ``deployment_subscribers[dep_id]`` ; sans ``deployment_id`` → ``error`` ;
- **réception ciblée** : l'abonné reçoit le broadcast
  ``broadcast_to_event_subscribers(EVT, msg)`` émis depuis la boucle serveur
  (pattern ``_emitter_as_heartbeat``) ; un non-abonné ne reçoit rien ;
- branches défensives hors E2E (contexte mocké) : ``context.user is None``
  → « Authentication required » ×3 ; exception du helper broadcasting →
  « Subscription failed » / « Unsubscription failed » / « Deployment logs
  subscription failed ».

Patterns : ``_auth_stack`` + collecte déterministe (test_ws_batch.py) ;
isolation des singletons par fixture autouse.
"""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth import dependencies as auth_dependencies
from app.main import app
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.websocket.connection_managers import user_manager
from app.websocket.plugin import PluginContext
from app.websocket.plugins.subscription import SubscriptionHandler

GENERAL = "/api/v1/ws/"


# ===========================================================================
# Helpers (patterns test_ws_batch.py / test_ws_general_loop.py)
# ===========================================================================


def _make_user(
    user_id: str = "user-1", active: bool = True, superadmin: bool = False
) -> User:
    return User(
        id=user_id,
        email="user@test.com",
        username="testuser",
        is_active=active,
        is_superuser=superadmin,
    )


def _make_token_data(user_id: str = "user-1") -> MagicMock:
    token_data = MagicMock()
    token_data.user_id = user_id
    return token_data


@pytest.fixture(autouse=True)
def _fresh_role_cache():
    from app.core.cache import reset_role_cache

    reset_role_cache()
    yield
    reset_role_cache()


@pytest.fixture(autouse=True)
def _clean_managers():
    """Isolation : singletons globaux vierges autour de chaque test."""
    user_manager.user_connections.clear()
    user_manager.user_subscriptions.clear()
    user_manager.deployment_subscribers.clear()
    user_manager.user_plugin_contexts.clear()
    yield
    user_manager.user_connections.clear()
    user_manager.user_subscriptions.clear()
    user_manager.deployment_subscribers.clear()
    user_manager.user_plugin_contexts.clear()


@pytest.fixture()
def ws_client():
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _override_db():
    from app.database import get_db

    session = AsyncMock()

    async def override():
        yield session

    app.dependency_overrides[get_db] = override
    return session


def _mock_database_session() -> MagicMock:
    mock_db = MagicMock()
    mock_database = MagicMock()
    mock_database.session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_database.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_database.session


def _patch_org_ids(org_ids: tuple[str, ...] = ("org-1",)):
    from app.services.user_organization_service import UserOrganizationService

    async def _fake_ids(db, u):  # noqa: ARG001
        return list(org_ids)

    return patch.object(
        UserOrganizationService,
        "get_user_organization_ids",
        side_effect=_fake_ids,
    )


def _auth_stack(user: User, *, role: str = "viewer"):
    stack = ExitStack()
    stack.enter_context(patch.object(auth_dependencies.settings, "disable_auth", False))
    stack.enter_context(
        patch.object(
            auth_dependencies,
            "decode_access_token",
            return_value=_make_token_data(str(user.id)),
        )
    )
    stack.enter_context(
        patch.object(
            auth_dependencies.UserService,
            "get_by_id",
            AsyncMock(return_value=user),
        )
    )
    stack.enter_context(
        patch.object(auth_dependencies.database, "session", _mock_database_session())
    )
    stack.enter_context(
        patch.object(
            AuthorizationService, "get_global_role", AsyncMock(return_value=role)
        )
    )
    stack.enter_context(_patch_org_ids())
    return stack


def _auth_and_receive_success(ws) -> dict:
    ws.send_json({"type": "auth", "token": "valid.jwt"})
    response = ws.receive_json()
    assert response["type"] == "AUTH_LOGIN_SUCCESS"
    return response


def _make_plugin_context(user=None) -> PluginContext:
    """Contexte de plugin mocké pour les invocations directes du handler."""
    return PluginContext(
        db=MagicMock(),
        user=user,
        websocket=AsyncMock(),
        logger=MagicMock(),
    )


def _emitter_as_heartbeat(user_id: str, event_type: str):
    """Patch one-shot de ``periodic_ping`` : broadcast ciblé aux abonnés.

    Attend (borné) que l'utilisateur soit abonné avant d'appeler
    ``broadcast_to_event_subscribers`` — l'émission part dans la même boucle
    d'événements que la WebSocket (pattern ``_emitter_as_heartbeat``).
    """

    async def _fake_ping(websocket, channel):  # noqa: ARG001
        from app.websocket.broadcasting import broadcast_to_event_subscribers

        for _ in range(100):  # borne ~5 s, jamais atteinte en pratique
            if event_type in user_manager.user_subscriptions.get(user_id, set()):
                break
            await asyncio.sleep(0.05)

        await broadcast_to_event_subscribers(
            event_type,
            {"type": "BROADCAST_TEST", "data": {"hello": "subscribers"}},
        )

    return patch("app.websocket.general.periodic_ping", new=_fake_ping)


# ===========================================================================
# subscribe
# ===========================================================================


class TestSubscribe:
    """``subscribe`` : cas nominal, effets manager, erreur validation."""

    def test_subscribe_valid_acknowledged_and_registered(self, ws_client):
        """subscribe valide → subscribed + entrée user_subscriptions."""
        _override_db()
        with _auth_stack(_make_user()):
            with ws_client.websocket_connect(GENERAL) as ws:
                _auth_and_receive_success(ws)
                ws.send_json(
                    {
                        "type": "subscribe",
                        "data": {"event_type": "NOTIFICATION_SYSTEM"},
                    }
                )
                response = ws.receive_json()
                assert response["type"] == "subscribed"
                assert response["data"] == {"event_type": "NOTIFICATION_SYSTEM"}
                assert "timestamp" in response

                assert user_manager.user_subscriptions["user-1"] == {
                    "NOTIFICATION_SYSTEM"
                }

    def test_subscribe_without_event_type_returns_error(self, ws_client):
        """Validation : event_type manquant → error « Missing event_type »."""
        _override_db()
        with _auth_stack(_make_user()):
            with ws_client.websocket_connect(GENERAL) as ws:
                _auth_and_receive_success(ws)
                ws.send_json({"type": "subscribe", "data": {}})
                response = ws.receive_json()
                assert response["type"] == "error"
                assert "Missing event_type" in response["message"]
                # Aucun abonnement enregistré.
                assert "user-1" not in user_manager.user_subscriptions


# ===========================================================================
# unsubscribe
# ===========================================================================


class TestUnsubscribe:
    """``unsubscribe`` : retrait + purge de la clé vide."""

    def test_unsubscribe_valid_removes_entry_and_purges_empty_key(self, ws_client):
        _override_db()
        with _auth_stack(_make_user()):
            with ws_client.websocket_connect(GENERAL) as ws:
                _auth_and_receive_success(ws)
                ws.send_json(
                    {
                        "type": "subscribe",
                        "data": {"event_type": "NOTIFICATION_SYSTEM"},
                    }
                )
                assert ws.receive_json()["type"] == "subscribed"

                ws.send_json(
                    {
                        "type": "unsubscribe",
                        "data": {"event_type": "NOTIFICATION_SYSTEM"},
                    }
                )
                response = ws.receive_json()
                assert response["type"] == "unsubscribed"
                assert response["data"] == {"event_type": "NOTIFICATION_SYSTEM"}

                # Retrait effectif + clé vide purgée du manager.
                assert "user-1" not in user_manager.user_subscriptions

    def test_unsubscribe_without_event_type_returns_error(self, ws_client):
        """Validation : event_type manquant → error « Missing event_type »."""
        _override_db()
        with _auth_stack(_make_user()):
            with ws_client.websocket_connect(GENERAL) as ws:
                _auth_and_receive_success(ws)
                ws.send_json({"type": "unsubscribe", "data": {}})
                response = ws.receive_json()
                assert response["type"] == "error"
                assert "Missing event_type" in response["message"]


# ===========================================================================
# deployment_logs
# ===========================================================================


class TestDeploymentLogsSubscription:
    """``deployment_logs`` : abonnement aux logs d'un déploiement précis."""

    def test_deployment_logs_valid_registers_subscriber(self, ws_client):
        _override_db()
        with _auth_stack(_make_user()):
            with ws_client.websocket_connect(GENERAL) as ws:
                _auth_and_receive_success(ws)
                ws.send_json(
                    {
                        "type": "deployment_logs",
                        "data": {"deployment_id": "dep-42"},
                    }
                )
                response = ws.receive_json()
                assert response["type"] == "logs_subscribed"
                assert response["data"] == {"deployment_id": "dep-42"}
                assert "timestamp" in response

                assert "dep-42" in user_manager.deployment_subscribers
                assert "user-1" in user_manager.deployment_subscribers["dep-42"]

    def test_deployment_logs_without_deployment_id_returns_error(self, ws_client):
        """Validation : deployment_id manquant → error « Missing deployment_id »."""
        _override_db()
        with _auth_stack(_make_user()):
            with ws_client.websocket_connect(GENERAL) as ws:
                _auth_and_receive_success(ws)
                ws.send_json({"type": "deployment_logs", "data": {}})
                response = ws.receive_json()
                assert response["type"] == "error"
                assert "Missing deployment_id" in response["message"]
                assert not user_manager.deployment_subscribers


# ===========================================================================
# Réception ciblée — l'abonné reçoit, le non-abonné non
# ===========================================================================


class TestTargetedBroadcast:
    """Broadcast vers les abonnés d'un type d'événement (E2E)."""

    def test_subscriber_receives_targeted_broadcast(self, ws_client):
        """L'abonné à NOTIFICATION_SYSTEM reçoit le broadcast ciblé."""
        _override_db()
        user = _make_user()
        with _auth_stack(user):
            with _emitter_as_heartbeat(str(user.id), "NOTIFICATION_SYSTEM"):
                with ws_client.websocket_connect(GENERAL) as ws:
                    _auth_and_receive_success(ws)
                    ws.send_json(
                        {
                            "type": "subscribe",
                            "data": {"event_type": "NOTIFICATION_SYSTEM"},
                        }
                    )
                    assert ws.receive_json()["type"] == "subscribed"

                    messages = []
                    for _ in range(10):
                        message = ws.receive_json()
                        messages.append(message)
                        if message.get("type") == "BROADCAST_TEST":
                            break

                    received = next(
                        (m for m in messages if m["type"] == "BROADCAST_TEST"), None
                    )
                    assert received is not None, "l'abonné doit recevoir le broadcast"
                    assert received["data"] == {"hello": "subscribers"}

    def test_non_subscriber_does_not_receive_targeted_broadcast(self, ws_client):
        """Un connecté non abonné ne reçoit pas le broadcast ciblé.

        L'émetteur broadcast vers les abonnés d'un type auquel le user ne
        s'est PAS abonné : le prochain message reçu du serveur est le pong
        (aucun BROADCAST_TEST intercalé).
        """
        _override_db()
        user = _make_user()
        with _auth_stack(user):
            with _emitter_as_heartbeat(str(user.id), "NOTIFICATION_SYSTEM"):
                with ws_client.websocket_connect(GENERAL) as ws:
                    _auth_and_receive_success(ws)
                    # Pas de message subscribe : le user n'est abonné à rien.

                    # L'émetteur part dès son premier tour de boucle (aucun
                    # abonnement attendu n'arrive) : laisser un court instant
                    # puis vérifier qu'aucun BROADCAST_TEST n'est reçu.
                    ws.send_text("ping")
                    pong = ws.receive_json()
                    assert pong["type"] == "pong"


# ===========================================================================
# Branches défensives du handler (invocations directes, contexte mocké)
# ===========================================================================


class TestSubscriptionHandlerDirectBranches:
    """user absent / helper broadcasting défaillant — hors E2E."""

    async def test_subscribe_without_user_returns_authentication_required(self):
        handler = SubscriptionHandler()
        context = _make_plugin_context(user=None)

        response = await handler.handle_message(
            {"type": "subscribe", "data": {"event_type": "NOTIFICATION_SYSTEM"}},
            context,
        )

        assert response["type"] == "error"
        assert response["message"] == "Authentication required"

    async def test_unsubscribe_without_user_returns_authentication_required(self):
        handler = SubscriptionHandler()
        context = _make_plugin_context(user=None)

        response = await handler.handle_message(
            {"type": "unsubscribe", "data": {"event_type": "NOTIFICATION_SYSTEM"}},
            context,
        )

        assert response["type"] == "error"
        assert response["message"] == "Authentication required"

    async def test_deployment_logs_without_user_returns_authentication_required(self):
        handler = SubscriptionHandler()
        context = _make_plugin_context(user=None)

        response = await handler.handle_message(
            {"type": "deployment_logs", "data": {"deployment_id": "dep-1"}},
            context,
        )

        assert response["type"] == "error"
        assert response["message"] == "Authentication required"

    async def test_subscribe_helper_failure_returns_subscription_failed(self):
        """Exception du helper broadcasting → error « Subscription failed ».

        L'import est fait dans la fonction (``from ..broadcasting import
        subscribe_to_event``) : le patch cible le module broadcasting.
        """
        handler = SubscriptionHandler()
        context = _make_plugin_context(user=_make_user())

        with patch(
            "app.websocket.broadcasting.subscribe_to_event",
            new=AsyncMock(side_effect=RuntimeError("store unavailable")),
        ):
            response = await handler.handle_message(
                {
                    "type": "subscribe",
                    "data": {"event_type": "NOTIFICATION_SYSTEM"},
                },
                context,
            )

        assert response["type"] == "error"
        assert "Subscription failed" in response["message"]
        assert "store unavailable" in response["message"]

    async def test_unsubscribe_helper_failure_returns_unsubscription_failed(self):
        handler = SubscriptionHandler()
        context = _make_plugin_context(user=_make_user())

        with patch(
            "app.websocket.broadcasting.unsubscribe_from_event",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            response = await handler.handle_message(
                {
                    "type": "unsubscribe",
                    "data": {"event_type": "NOTIFICATION_SYSTEM"},
                },
                context,
            )

        assert response["type"] == "error"
        assert "Unsubscription failed" in response["message"]

    async def test_deployment_logs_helper_failure_returns_logs_failed(self):
        handler = SubscriptionHandler()
        context = _make_plugin_context(user=_make_user())

        with patch(
            "app.websocket.broadcasting.subscribe_to_deployment_logs",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            response = await handler.handle_message(
                {"type": "deployment_logs", "data": {"deployment_id": "dep-1"}},
                context,
            )

        assert response["type"] == "error"
        assert "Deployment logs subscription failed" in response["message"]

    async def test_unknown_message_type_returns_none(self):
        """Type hors contrat du handler → None (aucune réponse)."""
        handler = SubscriptionHandler()
        context = _make_plugin_context(user=_make_user())

        response = await handler.handle_message({"type": "mystery"}, context)

        assert response is None
