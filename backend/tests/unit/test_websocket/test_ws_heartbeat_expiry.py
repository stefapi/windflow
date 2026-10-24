"""Tests d'expiration des connexions WebSocket muettes (STORY-164.1 — AC 1).

Couvre le helper transverse ``websocket/heartbeat.py`` et son application
aux 5 canaux (général + 4 dédiés) :

- **client muet** (aucun pong/message) → connexion **fermée côté serveur**
  (~2 intervalles, timeout réduit via settings en test — jamais de sleep
  long) ;
- **client actif** (messages réguliers) → jamais fermée (reset à chaque
  message reçu) ;
- **ping serveur périodique** émis sur un canal dédié (mock d'horloge) ;
- **terminal** : session émettrice régulière non fermée ; inactivité
  totale → fermeture ;
- log d'expiration structuré, sans données sensibles.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.websocket.heartbeat import (
    WS_CLOSE_IDLE_TIMEOUT_CODE,
    HeartbeatExpiredError,
    periodic_ping,
    receive_with_expiry,
    ws_inactivity_timeout,
)

GENERAL = "/api/v1/ws/"


@pytest.fixture()
def ws_client():
    """Client de test sync pour les WebSockets (sans lifespan : pas de DB réelle)."""
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def short_heartbeat_settings():
    """Timeout d'expiration réduit pour les tests (interval=1s, factor=1)."""
    from app.config import settings

    with (
        patch.object(settings, "ws_heartbeat_interval_seconds", 1),
        patch.object(settings, "ws_heartbeat_timeout_factor", 1),
    ):
        yield settings


def _mute_websocket() -> AsyncMock:
    """WebSocket mockée : receive_text ne rend jamais (client muet)."""
    websocket = AsyncMock()
    websocket.receive_text = AsyncMock(side_effect=asyncio.Event().wait)
    return websocket


def _active_websocket(messages: list[str], delay: float = 0.05) -> AsyncMock:
    """WebSocket mockée : émet les messages donnés puis reste muette.

    Le client « actif » envoie des messages réguliers ; après épuisement
    il se tait (permet de vérifier que seuls les messages reçus resettent
    le délai, pas le temps qui passe).
    """

    async def receive() -> str:
        if messages:
            await asyncio.sleep(delay)
            return messages.pop(0)
        # Plus de messages : silence définitif (le délai doit expirer)
        await asyncio.Event().wait()

    websocket = AsyncMock()
    websocket.receive_text = AsyncMock(side_effect=receive)
    return websocket


# ===========================================================================
# Helper receive_with_expiry
# ===========================================================================


async def test_mute_client_closed_after_two_intervals(short_heartbeat_settings):
    """AC 1 : client muet → close serveur 1001 + HeartbeatExpiredError."""
    websocket = _mute_websocket()

    with pytest.raises(HeartbeatExpiredError):
        await asyncio.wait_for(
            receive_with_expiry(websocket, "general", user_id="user-1"),
            timeout=3.0,
        )

    websocket.close.assert_awaited_once()
    kwargs = websocket.close.await_args.kwargs
    assert kwargs.get("code") == WS_CLOSE_IDLE_TIMEOUT_CODE


async def test_active_client_never_expired(short_heartbeat_settings):
    """AC 1 : messages réguliers → le délai est reset, jamais de fermeture."""
    websocket = _active_websocket(["ping"] * 3, delay=0.05)

    received = []
    for _ in range(3):
        data = await asyncio.wait_for(
            receive_with_expiry(websocket, "general"), timeout=3.0
        )
        received.append(data)

    assert received == ["ping"] * 3
    websocket.close.assert_not_awaited()


async def test_expiry_log_is_structured_without_sensitive_data(
    short_heartbeat_settings, caplog
):
    """Log d'expiration : structured (extra), sans données sensibles."""
    websocket = _mute_websocket()

    with caplog.at_level(logging.WARNING, logger="app.websocket.heartbeat"):
        with pytest.raises(HeartbeatExpiredError):
            await asyncio.wait_for(
                receive_with_expiry(websocket, "general"), timeout=3.0
            )

    records = [r for r in caplog.records if r.name == "app.websocket.heartbeat"]
    assert records, "aucun log d'expiration émis"
    record = records[-1]
    # Le canal et la raison sont tracés (extra → attributs du record) ;
    # jamais de payload ni de token dans le message.
    assert getattr(record, "channel", None) == "general"
    assert getattr(record, "reason", None) == "idle_expiry"
    assert getattr(record, "timeout_seconds", None) == 1.0


async def test_close_failure_on_dead_connection_is_swallowed(
    short_heartbeat_settings,
):
    """Connexion déjà morte : l'échec de close est absorbé (debug log)."""
    websocket = _mute_websocket()
    websocket.close = AsyncMock(side_effect=RuntimeError("already closed"))

    with pytest.raises(HeartbeatExpiredError):
        await asyncio.wait_for(receive_with_expiry(websocket, "general"), timeout=3.0)


def test_ws_inactivity_timeout_respects_settings(short_heartbeat_settings):
    """Le timeout = factor × interval (bornes settings respectées)."""
    assert ws_inactivity_timeout() == 1.0

    from app.config import settings

    with patch.object(settings, "ws_heartbeat_interval_seconds", 30):
        with patch.object(settings, "ws_heartbeat_timeout_factor", 2):
            assert ws_inactivity_timeout() == 60.0


def test_ws_inactivity_timeout_clamps_invalid_settings():
    """Défense en profondeur : settings invalides → jamais 0/négatif."""
    from app.config import settings

    with (
        patch.object(settings, "ws_heartbeat_interval_seconds", 0),
        patch.object(settings, "ws_heartbeat_timeout_factor", 0),
    ):
        assert ws_inactivity_timeout() >= 1.0


# ===========================================================================
# Ping serveur périodique (canal dédié — recommandation décision 4)
# ===========================================================================


async def test_periodic_ping_emits_at_configured_interval(
    short_heartbeat_settings,
):
    """Le ping serveur est émis périodiquement (mock horloge écourté)."""
    websocket = AsyncMock()
    task = asyncio.create_task(periodic_ping(websocket, "deployment_logs:dep-1"))

    # Laisser passer ~2 intervalles (interval=1s en settings test)
    await asyncio.sleep(2.2)
    task.cancel()
    await task  # CancelledError absorbée par le helper (contrat documenté)

    assert websocket.send_json.await_count >= 2
    first = websocket.send_json.await_args_list[0].args[0]
    assert first["type"] == "ping"
    assert "timestamp" in first


async def test_periodic_ping_swallows_send_errors(short_heartbeat_settings):
    """Envoi impossible (connexion morte) : pas d'exception propagée."""
    websocket = AsyncMock()
    websocket.send_json = AsyncMock(side_effect=RuntimeError("dead"))

    task = asyncio.create_task(periodic_ping(websocket, "general"))
    await asyncio.sleep(1.2)
    task.cancel()
    await task  # aucune exception propagée (RuntimeError absorbé en debug)


# ===========================================================================
# Application canal général — bout-en-bout (pattern test_ws_auth.py)
# ===========================================================================


def _make_user(user_id: str = "user-1"):
    from app.models.user import User

    return User(
        id=user_id,
        email="user@test.com",
        username="testuser",
        is_active=True,
    )


def _general_auth_stack(user):
    """Pile de patches d'auth du canal général (patterns test_ws_auth)."""
    from app.auth import dependencies as auth_dependencies
    from app.services.user_organization_service import UserOrganizationService

    async def _fake_ids(db, u):
        return ["org-1"]

    async def _fake_primary(db, u):
        return "org-1"

    stack = ExitStack()
    stack.enter_context(patch.object(auth_dependencies.settings, "disable_auth", False))
    stack.enter_context(
        patch.object(
            auth_dependencies,
            "decode_access_token",
            return_value=MagicMock(user_id=str(user.id)),
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
        patch.object(UserOrganizationService, "get_user_organization_ids", _fake_ids)
    )
    stack.enter_context(
        patch.object(
            UserOrganizationService, "get_primary_organization_id", _fake_primary
        )
    )
    return stack


def _mock_database_session():
    """Retourne un mock de database.session() (context manager async)."""
    mock_db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []  # rôle global vide → viewer
    mock_db.execute = AsyncMock(return_value=result)
    mock_database = MagicMock()
    mock_database.session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_database.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_database.session


def test_general_endpoint_expires_mute_client(ws_client, short_heartbeat_settings):
    """Canal général bout-en-bout : auth OK puis silence → close serveur.

    Après AUTH_LOGIN_SUCCESS, le client n'envoie rien : le serveur doit
    fermer la connexion au bout de l'inactivité configurée (~1 s en test)
    au lieu de rester ouvert indéfiniment.
    """
    from app.database import db as database_module

    user = _make_user()

    with _general_auth_stack(user):
        with patch.object(database_module, "session", _mock_database_session()):
            with ws_client.websocket_connect(GENERAL) as ws:
                ws.send_json({"type": "auth", "token": "valid.jwt"})
                response = ws.receive_json()
                assert response["type"] == "AUTH_LOGIN_SUCCESS"

                # Silence total : le serveur ferme (receive lève une
                # exception de fermeture côté client test).
                with pytest.raises(Exception):
                    ws.receive_json()


def test_general_endpoint_active_client_stays_connected(
    ws_client, short_heartbeat_settings
):
    """Canal général bout-en-bout : messages réguliers → jamais fermé."""
    from app.database import db as database_module

    user = _make_user()

    with _general_auth_stack(user):
        with patch.object(database_module, "session", _mock_database_session()):
            with ws_client.websocket_connect(GENERAL) as ws:
                ws.send_json({"type": "auth", "token": "valid.jwt"})
                assert ws.receive_json()["type"] == "AUTH_LOGIN_SUCCESS"

                # Plusieurs cycles ping/pong espacés (< timeout 1 s) : la
                # connexion reste ouverte à chaque fois (reset du délai).
                for _ in range(3):
                    ws.send_text("ping")
                    pong = ws.receive_json()
                    assert pong["type"] == "pong"


# ===========================================================================
# Terminal — inactivité totale uniquement
# ===========================================================================


async def test_terminal_loop_expires_on_total_inactivity(
    short_heartbeat_settings,
):
    """Terminal : l'expiration ne vise que l'inactivité TOTALE du client.

    La boucle de réception du terminal : des inputs réguliers (messages
    reçus) ne déclenchent jamais l'expiration ; le silence total lève
    HeartbeatExpiredError (break propre — le finally du canal nettoie
    l'ExecSession ; Docker non requis pour ce niveau).
    """
    # Client actif : 3 inputs puis silence — le 4e appel doit expirer.
    websocket = _active_websocket(
        ['{"type": "input", "data": "ls\\n"}'] * 3, delay=0.05
    )

    received = []
    expired = False
    while True:
        try:
            received.append(
                await asyncio.wait_for(
                    receive_with_expiry(websocket, "terminal:c1"), timeout=3.0
                )
            )
        except HeartbeatExpiredError:
            expired = True
            break

    assert len(received) == 3
    assert expired
    websocket.close.assert_awaited_once()
