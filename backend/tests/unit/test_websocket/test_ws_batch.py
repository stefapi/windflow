"""Tests du canal WebSocket ``/ws/batch/{batch_id}`` (STORY-164.2 — AC 1/2).

Canal **émetteur-ready** (décision 7) : auth query param (1008 sans
token), RBAC viewer (suivi = lecture), opération groupée **simulée**
via :func:`broadcast_batch_event` — un abonné authentifié reçoit
``start`` → ``progress`` → ``complete`` (phases spec 09, enveloppe
``type``/``data``), phase ``error`` diffusée, isolation entre batchs,
purge des connexions mortes, expiration connexion muette.
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth import dependencies as auth_dependencies
from app.main import app
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.websocket import batch as batch_module

BATCH = "/api/v1/ws/batch/batch-1"


# ===========================================================================
# Helpers (patterns test_ws_ssh_session / test_ws_journal)
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
def _clean_batch_manager():
    """Manager batch vierge autour de chaque test (isolation)."""
    batch_module.batch_manager.active_connections.clear()
    yield
    batch_module.batch_manager.active_connections.clear()


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


def _patch_global_role(role: str):
    return patch.object(
        AuthorizationService,
        "get_global_role",
        AsyncMock(return_value=role),
    )


def _mock_database_session():
    mock_db = MagicMock()
    mock_database = MagicMock()
    mock_database.session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_database.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_database.session


def _auth_stack(user: User):
    stack = ExitStack()
    stack.enter_context(patch.object(auth_dependencies.settings, "disable_auth", False))
    stack.enter_context(
        patch.object(
            auth_dependencies,
            "decode_access_token",
            return_value=_make_token_data(),
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


def _emitter_as_heartbeat(batch_id: str = "batch-1", *, fail: bool = False):
    """Retourne un patch de ``periodic_ping`` qui joue l'émetteur batch.

    Le canal batch démarre ``periodic_ping`` dans la boucle d'événements
    du serveur (portal TestClient) : patcher ce helper est le moyen
    déterministe d'exécuter l'émetteur simulé **dans la même boucle**
    que la WebSocket (un ``asyncio.run`` cross-thread ne partagerait pas
    la socket starlette). La coroutine remplace le ping par la séquence
    spec 09 : start → progress ×2 → complete (ou error).
    """
    from app.websocket.batch import broadcast_batch_event

    async def _fake_ping(websocket, channel):  # noqa: ARG001
        await broadcast_batch_event(
            batch_id, "start", {"batch_id": batch_id, "total": 2}
        )
        await broadcast_batch_event(
            batch_id,
            "progress",
            {"app_id": "app_nextcloud", "step": "pulling", "current": 1, "total": 2},
        )
        await broadcast_batch_event(
            batch_id,
            "progress",
            {"app_id": "app_pihole", "step": "done", "current": 2, "total": 2},
        )
        if fail:
            await broadcast_batch_event(
                batch_id, "error", {"batch_id": batch_id, "message": "global failure"}
            )
        else:
            await broadcast_batch_event(
                batch_id,
                "complete",
                {
                    "batch_id": batch_id,
                    "total": 2,
                    "succeeded": 2,
                    "failed": 0,
                    "skipped": 0,
                },
            )

    return patch("app.websocket.batch.periodic_ping", new=_fake_ping)


# ===========================================================================
# AC 1 — Auth 1008 sans token / RBAC viewer
# ===========================================================================


class TestBatchAuthAndRbac:
    """Auth obligatoire + RBAC viewer (suivi d'opération = lecture)."""

    def test_no_token_refused_1008(self, ws_client):
        """Sécurité : sans token → handshake refusé (1008)."""
        _override_db()
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with pytest.raises(Exception):
                with ws_client.websocket_connect(BATCH):
                    pass

    def test_viewer_accepted(self, ws_client):
        """RBAC : viewer accepté (contrairement à /ws/ssh operator-only)."""
        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("viewer"):
                with ws_client.websocket_connect(BATCH + "?token=valid.jwt") as ws:
                    message = ws.receive_json()
                    assert message["type"] == "subscribed"
                    assert message["batch_id"] == "batch-1"

    def test_unknown_role_refused(self, ws_client):
        """Garde : rôle résolu incohérent → 1008 avant accept."""
        _override_db()

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value=_make_token_data(),
            ):
                with patch.object(
                    auth_dependencies.UserService,
                    "get_by_id",
                    AsyncMock(return_value=_make_user()),
                ):
                    with _patch_global_role("corrupted-role"):
                        with pytest.raises(Exception):
                            with ws_client.websocket_connect(
                                BATCH + "?token=valid.jwt"
                            ):
                                pass


# ===========================================================================
# AC 2 — Opération groupée simulée : start → progress → complete
# ===========================================================================


class TestBatchSimulatedOperation:
    """Un abonné authentifié reçoit les phases spec 09 via broadcast."""

    def test_subscriber_receives_full_sequence(self, ws_client):
        """start → progress → complete reçus (enveloppe type/data)."""
        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("viewer"):
                with _emitter_as_heartbeat("batch-1"):
                    with ws_client.websocket_connect(BATCH + "?token=valid.jwt") as ws:
                        subscribed = ws.receive_json()
                        assert subscribed["type"] == "subscribed"

                        messages = _collect_messages(
                            ws, max_messages=20, until_type="complete"
                        )
                        types = [m["type"] for m in messages]

                        assert "start" in types
                        assert "progress" in types
                        assert "complete" in types

                        complete = next(m for m in messages if m["type"] == "complete")
                        assert complete["data"]["total"] == 2
                        assert complete["data"]["succeeded"] == 2
                        assert complete["data"]["batch_id"] == "batch-1"

    def test_error_phase_broadcast(self, ws_client):
        """Phase error (échec global) diffusée aux abonnés."""
        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("viewer"):
                with _emitter_as_heartbeat("batch-1", fail=True):
                    with ws_client.websocket_connect(BATCH + "?token=valid.jwt") as ws:
                        ws.receive_json()  # subscribed

                        messages = _collect_messages(
                            ws, max_messages=20, until_type="error"
                        )
                        types = [m["type"] for m in messages]
                        assert "error" in types
                        error_event = next(m for m in messages if m["type"] == "error")
                        assert "global failure" in error_event["data"]["message"]

    async def test_broadcast_batch_event_validates_phase(self):
        """Garde : phase inconnue rejetée (contrat d'émission)."""
        from app.websocket.batch import broadcast_batch_event

        with pytest.raises(ValueError):
            await broadcast_batch_event("batch-1", "unknown-phase", {})

    async def test_broadcast_batch_event_timestamp_and_envelope(self):
        """L'enveloppe porte type/data + batch_id + timestamp auto."""
        from app.websocket.batch import broadcast_batch_event

        websocket = AsyncMock()
        await batch_module.batch_manager.connect(websocket, "batch-x")
        try:
            await broadcast_batch_event("batch-x", "start", {"total": 3})
            websocket.send_json.assert_awaited()
            message = websocket.send_json.await_args.args[0]
            assert message["type"] == "start"
            assert message["data"]["batch_id"] == "batch-x"
            assert message["data"]["total"] == 3
            assert "timestamp" in message["data"]
        finally:
            await batch_module.batch_manager.disconnect(websocket, "batch-x")


# ===========================================================================
# Isolation entre batchs + purge connexions mortes + expiration
# ===========================================================================


class TestBatchIsolationAndManager:
    """Abonné du batch A ne reçoit pas les événements du batch B."""

    async def test_subscriber_of_batch_a_does_not_receive_batch_b(self):
        """Isolation : le broadcast batch B n'atteint pas l'abonné A."""
        from app.websocket.batch import broadcast_batch_event

        ws_a = AsyncMock()
        await batch_module.batch_manager.connect(ws_a, "batch-a")

        try:
            await broadcast_batch_event("batch-b", "start", {"total": 1})
            ws_a.send_json.assert_not_awaited()

            await broadcast_batch_event("batch-a", "start", {"total": 1})
            ws_a.send_json.assert_awaited_once()
        finally:
            await batch_module.batch_manager.disconnect(ws_a, "batch-a")

    async def test_dead_connections_purged_on_broadcast(self):
        """Manager : les connexions mortes sont purgées au broadcast."""
        from app.websocket.batch import broadcast_batch_event

        dead_ws = AsyncMock()
        dead_ws.send_json = AsyncMock(side_effect=RuntimeError("closed"))
        await batch_module.batch_manager.connect(dead_ws, "batch-z")

        try:
            # Le broadcast ne lève pas malgré la connexion morte…
            await broadcast_batch_event("batch-z", "start", {"total": 1})
            # …et la purge l'a retirée du set du batch (le set devient
            # vide — la clé peut subsister jusqu'au disconnect).
            connections = batch_module.batch_manager.active_connections.get(
                "batch-z", set()
            )
            assert dead_ws not in connections
            assert not connections
        finally:
            await batch_module.batch_manager.disconnect(dead_ws, "batch-z")

    def test_mute_connection_expired(self, ws_client):
        """Expiration : client muet → fermeture serveur (timeout réduit)."""
        from app.config import settings

        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("viewer"):
                with patch.object(settings, "ws_heartbeat_interval_seconds", 1):
                    with patch.object(settings, "ws_heartbeat_timeout_factor", 1):
                        with ws_client.websocket_connect(
                            BATCH + "?token=valid.jwt"
                        ) as ws:
                            ws.receive_json()  # subscribed
                            # Silence client : le serveur ping (messages
                            # reçus) puis ferme après expiration — la
                            # boucle absorbe les pings jusqu'à la
                            # fermeture (exception côté client).
                            with pytest.raises(Exception):
                                while True:
                                    ws.receive_json()
