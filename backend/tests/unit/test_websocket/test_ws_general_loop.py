"""Tests E2E de la boucle de messages du canal général (STORY-165 — Tâche 5, AC 2).

Portage du scénario §9.1 de la spec (WEBSOCKET-REAL-TIME.md) et couverture de
``app/websocket/general.py`` l.196-245 (72 % → ≥ 90 %) :

- ``ping`` **texte brut** → ``{"type": "pong", ...}`` ;
- message JSON **sans handler** → écho ``{"type": "message_received", ...}`` ;
- **texte non-JSON** → ``{"type": "text_received", ...}`` ;
- réponse d'un **handler de plugin** (``subscribe`` → ``subscribed``) sans
  écho complémentaire ;
- message ``ack`` inconnu → warning « unknown/foreign », aucune réponse (le
  branchement ack valide est couvert par ``test_ws_ack.py`` — non dupliqué) ;
- **spec §9.1 complet** : auth → ``AUTH_LOGIN_SUCCESS`` (user_id +
  organization_ids depuis ``UserOrganizationService`` mocké) → ``subscribe``
  → broadcast ``DEPLOYMENT_STATUS_CHANGED`` déclenché **depuis la boucle
  serveur** (patch one-shot de ``periodic_ping``, pattern
  ``_emitter_as_heartbeat`` de ``test_ws_batch.py``) → reçu avec son ``id``
  d'ack (type critique) via ``broadcast_to_user`` (plugin
  deployment_notifications) ;
- re-diffusion ack à la reconnexion : entrée pré-remplie au registre →
  message ``redelivered: True`` juste après ``AUTH_LOGIN_SUCCESS`` ;
- nettoyage à la déconnexion (``user_connections`` / contextes purgés) ;
- branches d'erreur : échec d'``accept`` (l.81-83), refus RBAC (l.108-110).

Patterns : ``_auth_stack`` (test_ws_batch.py) + émetteur one-shot + timeouts
par défaut suffisants (tests courts, aucun sleep long).
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.auth import dependencies as auth_dependencies
from app.main import app
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.websocket.ack_registry import AckEntry, ack_registry
from app.websocket.connection_managers import user_manager

GENERAL = "/api/v1/ws/"


# ===========================================================================
# Helpers (patterns test_ws_batch.py / test_ws_auth.py)
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
def _clean_managers_and_registry():
    """Isolation : singletons globaux + registre d'ack vierges autour de chaque test."""
    user_manager.user_connections.clear()
    user_manager.user_subscriptions.clear()
    user_manager.deployment_subscribers.clear()
    user_manager.user_plugin_contexts.clear()
    ack_registry._entries.clear()
    yield
    user_manager.user_connections.clear()
    user_manager.user_subscriptions.clear()
    user_manager.deployment_subscribers.clear()
    user_manager.user_plugin_contexts.clear()
    ack_registry._entries.clear()


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


def _patch_global_role(role: str):
    return patch.object(
        AuthorizationService,
        "get_global_role",
        AsyncMock(return_value=role),
    )


def _patch_org_ids(org_ids: tuple[str, ...] = ("org-1",)):
    """Patche la résolution des appartenances (STORY-121.3 : association)."""
    from app.services.user_organization_service import UserOrganizationService

    async def _fake_ids(db, u):  # noqa: ARG001
        return list(org_ids)

    return patch.object(
        UserOrganizationService,
        "get_user_organization_ids",
        side_effect=_fake_ids,
    )


def _auth_stack(user: User, *, role: str = "viewer"):
    """Empile les patches d'auth « premier message » du canal général."""
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
    stack.enter_context(_patch_global_role(role))
    stack.enter_context(_patch_org_ids())
    return stack


def _collect_messages(ws, max_messages: int = 50, until_type: str | None = None):
    """Consomme les messages jusqu'à until_type ou épuisement/erreur."""
    messages = []
    for _ in range(max_messages):
        try:
            message = ws.receive_json()
        except Exception:
            break
        messages.append(message)
        if until_type and message.get("type") == until_type:
            break
    return messages


def _wait_for(condition, timeout: float = 3.0, interval: float = 0.02):
    """Attend une condition post-fermeture (nettoyage asynchrone côté serveur)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(interval)
    raise AssertionError("condition non remplie dans le délai imparti")


def _auth_and_receive_success(ws) -> dict:
    """Envoie l'auth premier message et retourne AUTH_LOGIN_SUCCESS."""
    ws.send_json({"type": "auth", "token": "valid.jwt"})
    response = ws.receive_json()
    assert response["type"] == "AUTH_LOGIN_SUCCESS"
    return response


# ===========================================================================
# Protocole de la boucle de messages (general.py l.196-245)
# ===========================================================================


class TestGeneralLoopProtocol:
    """Messages client → réponses serveur de la boucle du canal général."""

    def test_text_ping_answered_with_pong(self, ws_client):
        """``ping`` texte brut → pong horodaté."""
        _override_db()
        with _auth_stack(_make_user()):
            with ws_client.websocket_connect(GENERAL) as ws:
                _auth_and_receive_success(ws)
                ws.send_text("ping")
                pong = ws.receive_json()
                assert pong["type"] == "pong"
                assert "timestamp" in pong

    def test_json_message_without_handler_echoed(self, ws_client):
        """JSON sans handler de plugin → écho message_received (données conservées)."""
        _override_db()
        with _auth_stack(_make_user()):
            with ws_client.websocket_connect(GENERAL) as ws:
                _auth_and_receive_success(ws)
                ws.send_json({"type": "unknown", "payload": {"k": "v"}})
                echoed = ws.receive_json()
                assert echoed["type"] == "message_received"
                assert echoed["data"] == {"type": "unknown", "payload": {"k": "v"}}
                assert "timestamp" in echoed

    def test_non_json_text_answered_with_text_received(self, ws_client):
        """Texte non-JSON → text_received avec le contenu brut."""
        _override_db()
        with _auth_stack(_make_user()):
            with ws_client.websocket_connect(GENERAL) as ws:
                _auth_and_receive_success(ws)
                ws.send_text("hello plain text")
                echoed = ws.receive_json()
                assert echoed["type"] == "text_received"
                assert echoed["data"] == "hello plain text"

    def test_plugin_handler_response_sent_without_echo(self, ws_client):
        """Un handler qui répond (subscribe → subscribed) court-circuite l'écho."""
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
                # Le message suivant est bien le pong : aucun écho
                # message_received n'a été émis entre les deux.
                ws.send_text("ping")
                assert ws.receive_json()["type"] == "pong"

    def test_ack_unknown_id_ignored_without_response(self, ws_client, caplog):
        """``ack`` d'un id inconnu → warning, aucune réponse (continue).

        Le branchement ack **valide** (acquittement + purge) est couvert par
        ``test_ws_ack.py`` — on ne duplique pas, on vérifie ici que la boucle
        générale ignore silencieusement un ack étranger et continue à traiter
        les messages suivants.
        """
        _override_db()
        with _auth_stack(_make_user()):
            with caplog.at_level(logging.WARNING, logger="app.websocket.general"):
                with ws_client.websocket_connect(GENERAL) as ws:
                    _auth_and_receive_success(ws)
                    ws.send_json({"type": "ack", "data": {"id": "foreign-id"}})
                    ws.send_text("ping")
                    # Premier message après AUTH : le pong — l'ack n'a
                    # déclenché ni réponse ni écho.
                    assert ws.receive_json()["type"] == "pong"

        warnings = [
            r
            for r in caplog.records
            if r.name == "app.websocket.general" and "ack ignored" in r.getMessage()
        ]
        assert warnings, "le warning ack ignoré doit être journalisé"
        assert getattr(warnings[0], "user_id", None) == "user-1"
        assert getattr(warnings[0], "message_id", None) == "foreign-id"


# ===========================================================================
# Portage spec §9.1 — flux complet auth → subscribe → broadcast
# ===========================================================================


def _emitter_as_heartbeat(
    user_id: str = "user-1", event_type: str = "DEPLOYMENT_STATUS_CHANGED"
):
    """Patch one-shot de ``periodic_ping`` : joue l'émetteur de la spec §9.1.

    Attend (borné) que l'utilisateur soit abonné avant d'émettre le
    changement de statut — le broadcast part dans la même boucle
    d'événements que la WebSocket (pattern ``_emitter_as_heartbeat`` de
    ``test_ws_batch.py``, un émetteur cross-boucle ne partagerait pas la
    socket Starlette).
    """

    async def _fake_ping(websocket, channel):  # noqa: ARG001
        from app.websocket.broadcasting import broadcast_deployment_status

        for _ in range(100):  # borne ~5 s, jamais atteinte en pratique
            if event_type in user_manager.user_subscriptions.get(user_id, set()):
                break
            await asyncio.sleep(0.05)

        await broadcast_deployment_status(
            "dep-1",
            "deploying",
            deployment_name="my stack",
            old_status="pending",
            user_id=user_id,
        )

    return patch("app.websocket.general.periodic_ping", new=_fake_ping)


class TestGeneralSpec91FullFlow:
    """Portage §9.1 : auth → subscribe → observation d'un broadcast déclenché."""

    def test_auth_login_success_payload(self, ws_client):
        """AUTH_LOGIN_SUCCESS expose user_id/username + les orgs (association)."""
        _override_db()
        with _auth_stack(_make_user()):
            with ws_client.websocket_connect(GENERAL) as ws:
                response = _auth_and_receive_success(ws)
                assert response["data"]["user_id"] == "user-1"
                assert response["data"]["username"] == "testuser"
                assert response["data"]["organization_id"] == "org-1"
                assert response["data"]["organization_ids"] == ["org-1"]

    def test_full_flow_subscribe_then_broadcast_received_with_ack_id(self, ws_client):
        """§9.1 : l'abonné reçoit DEPLOYMENT_STATUS_CHANGED avec son id d'ack.

        Chaîne réelle : ``broadcast_deployment_status`` (émetteur, boucle
        serveur) → ``dispatch_to_plugins`` → plugin deployment_notifications
        → ``broadcast_to_user`` → type critique → id UUID + registre.
        """
        _override_db()
        user = _make_user()
        with _auth_stack(user):
            with _emitter_as_heartbeat(str(user.id)):
                with ws_client.websocket_connect(GENERAL) as ws:
                    _auth_and_receive_success(ws)
                    ws.send_json(
                        {
                            "type": "subscribe",
                            "data": {"event_type": "DEPLOYMENT_STATUS_CHANGED"},
                        }
                    )
                    assert ws.receive_json()["type"] == "subscribed"

                    messages = _collect_messages(
                        ws,
                        max_messages=10,
                        until_type="DEPLOYMENT_STATUS_CHANGED",
                    )
                    event = next(
                        m for m in messages if m["type"] == "DEPLOYMENT_STATUS_CHANGED"
                    )
                    # Type critique → id d'ack UUID généré à l'émission.
                    assert event["id"]
                    # Payload effectivement diffusé (camelCase via **data).
                    assert event["data"]["newStatus"] == "deploying"
                    assert event["data"]["deploymentName"] == "my stack"
                    assert event["data"]["user_id"] == "user-1"


# ===========================================================================
# Re-diffusion des messages critiques non acquittés (STORY-164.1)
# ===========================================================================


class TestGeneralAckRedelivery:
    """Entrée pending au registre → re-diffusée à la reconnexion (redelivered)."""

    def test_pending_critical_redelivered_after_auth(self, ws_client):
        _override_db()
        # Pré-remplissage direct du registre (pas de lock nécessaire : simple
        # insertion dict, sans contention cross-boucle).
        ack_registry._entries["msg-42"] = AckEntry(
            message_id="msg-42",
            user_id="user-1",
            event_type="DEPLOYMENT_STATUS_CHANGED",
            payload={"deploymentId": "dep-9", "newStatus": "success"},
            emitted_at=datetime.utcnow(),
        )

        with _auth_stack(_make_user()):
            with ws_client.websocket_connect(GENERAL) as ws:
                _auth_and_receive_success(ws)
                redelivered = ws.receive_json()
                assert redelivered["type"] == "DEPLOYMENT_STATUS_CHANGED"
                assert redelivered["id"] == "msg-42"
                assert redelivered["redelivered"] is True
                assert redelivered["data"] == {
                    "deploymentId": "dep-9",
                    "newStatus": "success",
                }
        # L'entrée a été purgée à la re-diffusion (une reconnexion ne
        # re-diffuserait rien).
        assert "msg-42" not in ack_registry._entries


# ===========================================================================
# Nettoyage à la déconnexion + branches d'erreur
# ===========================================================================


class TestGeneralCleanupAndErrorBranches:
    """Déconnexion → nettoyage managers/plugins ; erreurs accept/RBAC."""

    def test_disconnect_cleans_user_connection_and_plugin_contexts(self, ws_client):
        """À la fermeture : user_connections et user_plugin_contexts purgés."""
        _override_db()
        user = _make_user()
        with _auth_stack(user):
            with ws_client.websocket_connect(GENERAL) as ws:
                _auth_and_receive_success(ws)
                assert "user-1" in user_manager.user_connections
                ws.send_text("ping")
                assert ws.receive_json()["type"] == "pong"

        _wait_for(lambda: "user-1" not in user_manager.user_connections)
        assert "user-1" not in user_manager.user_plugin_contexts

    async def test_accept_failure_is_logged_and_reraised(self):
        """Branch l.81-83 : échec d'accept → loggué puis ré-propagé."""
        from app.websocket.general import general_websocket_endpoint

        websocket = AsyncMock()
        websocket.accept = AsyncMock(side_effect=RuntimeError("handshake failed"))

        with pytest.raises(RuntimeError, match="handshake failed"):
            await general_websocket_endpoint(websocket)

    def test_rbac_refusal_after_auth_closes_1008(self, ws_client):
        """Rôle résolu incohérent → close 1008 juste après l'auth (l.108-110)."""
        _override_db()
        with _auth_stack(_make_user(), role="corrupted-role"):
            with ws_client.websocket_connect(GENERAL) as ws:
                ws.send_json({"type": "auth", "token": "valid.jwt"})
                with pytest.raises(WebSocketDisconnect) as exc_info:
                    ws.receive_json()
                assert exc_info.value.code == 1008

    def test_mute_connection_expired_server_side(self, ws_client):
        """Expiration : client muet après l'auth → fermeture serveur (1001)."""
        from app.config import settings

        _override_db()
        with _auth_stack(_make_user()):
            with patch.object(settings, "ws_heartbeat_interval_seconds", 1):
                with patch.object(settings, "ws_heartbeat_timeout_factor", 1):
                    with ws_client.websocket_connect(GENERAL) as ws:
                        _auth_and_receive_success(ws)
                        # Silence client : le serveur ping puis ferme après
                        # expiration — la réception finit par échouer côté
                        # client (pattern test_ws_batch.test_mute_connection_expired).
                        with pytest.raises(Exception):
                            while True:
                                ws.receive_json()
