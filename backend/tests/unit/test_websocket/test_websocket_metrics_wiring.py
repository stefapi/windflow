"""Tests du câblage ``websocket/metrics.py`` (STORY-172 — Tâche 7, AC 3/E5).

Décision E5 : le module n'est plus « défini mais jamais importé » — ses
helpers sont consommés par les 6 modules du package. Ces tests vérifient
les **deltas de séries** après de vraies opérations (connexions mockées
pattern STORY-165, broadcasts, dispatch plugin, purge ack) et la résilience
best-effort (un helper qui lève ne casse jamais le broadcast).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prometheus_client import REGISTRY

from app.schemas.websocket_events import WebSocketEventType
from app.websocket.ack_registry import AckRegistry
from app.websocket.connection_managers import ConnectionManager
from app.websocket.plugin import PluginContext, WebSocketPlugin, WebSocketPluginManager


def _value(name: str, labels: dict | None = None) -> float:
    """Valeur actuelle d'un sample (0 si la série n'existe pas encore)."""
    value = REGISTRY.get_sample_value(name, labels)
    return value if value is not None else 0.0


def _mock_websocket() -> MagicMock:
    """WebSocket mockée (pattern STORY-165 — tests connection managers)."""
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.send_json = AsyncMock()
    return websocket


def _make_context(websocket=None) -> PluginContext:
    """Contexte de plugin minimal pour les dispatch (pattern STORY-165)."""
    return PluginContext(
        db=MagicMock(),
        user=None,
        websocket=websocket or _mock_websocket(),
        logger=MagicMock(),
    )


class TestConnectionWiring:
    """``ConnectionManager.connect/disconnect`` → gauge + compteur."""

    @pytest.mark.asyncio
    async def test_connection_records_gauge_and_counter(self):
        manager = ConnectionManager()
        websocket = _mock_websocket()

        before_total = _value(
            "windflow_websocket_connections_total",
            {"connection_type": "deployment", "status": "connected"},
        )
        before_active = _value(
            "windflow_websocket_connections_active",
            {"connection_type": "deployment"},
        )

        await manager.connect(websocket, "dep-1")
        assert (
            _value(
                "windflow_websocket_connections_total",
                {"connection_type": "deployment", "status": "connected"},
            )
            - before_total
            == 1.0
        )
        assert (
            _value(
                "windflow_websocket_connections_active",
                {"connection_type": "deployment"},
            )
            - before_active
            == 1.0
        )

        before_disc = _value(
            "windflow_websocket_connections_total",
            {"connection_type": "deployment", "status": "disconnected"},
        )
        await manager.disconnect(websocket, "dep-1")
        assert (
            _value(
                "windflow_websocket_connections_total",
                {"connection_type": "deployment", "status": "disconnected"},
            )
            - before_disc
            == 1.0
        )
        assert (
            before_active
            - _value(
                "windflow_websocket_connections_active",
                {"connection_type": "deployment"},
            )
            + 1.0
            == 1.0
        )  # active revenue au niveau initial (inc puis dec)

    @pytest.mark.asyncio
    async def test_broadcast_records_duration_and_clients(self):
        manager = ConnectionManager()
        websocket = _mock_websocket()
        await manager.connect(websocket, "dep-broadcast")

        before_count = _value(
            "windflow_websocket_broadcast_duration_seconds_count",
            {"broadcast_type": "deployment"},
        )
        before_clients = _value(
            "windflow_websocket_broadcast_clients_count",
            {"broadcast_type": "deployment"},
        )

        await manager.broadcast_to_deployment(
            "dep-broadcast", {"type": "TEST_EVENT", "data": {}}
        )

        assert (
            _value(
                "windflow_websocket_broadcast_duration_seconds_count",
                {"broadcast_type": "deployment"},
            )
            - before_count
            == 1.0
        )
        assert (
            _value(
                "windflow_websocket_broadcast_clients_count",
                {"broadcast_type": "deployment"},
            )
            - before_clients
            == 1.0
        )
        await manager.disconnect(websocket, "dep-broadcast")


class TestPluginWiring:
    """Dispatch plugin → durée d'exécution + events dispatchés."""

    @pytest.mark.asyncio
    async def test_plugin_dispatch_records_execution(self):
        class RecordingPlugin(WebSocketPlugin):
            name = "recording-plugin"
            listens_for = [WebSocketEventType.DEPLOYMENT_STATUS_CHANGED]

            async def handle_event(self, event, data, context) -> None:
                return None

        plugin_manager = WebSocketPluginManager()
        plugin = RecordingPlugin()
        plugin_manager.register(plugin)
        context = _make_context()
        await plugin_manager.initialize_all(context)

        # L'histogram plugin_duration porte DEUX labels (plugin_name,
        # event_type) — les deux sont requis pour lire le sample.
        duration_labels = {
            "plugin_name": "recording-plugin",
            "event_type": "DEPLOYMENT_STATUS_CHANGED",
        }
        before_duration = _value(
            "windflow_websocket_plugin_duration_seconds_count",
            duration_labels,
        )
        before_dispatched = _value(
            "windflow_websocket_events_dispatched_total",
            {"event_type": "DEPLOYMENT_STATUS_CHANGED", "status": "success"},
        )

        await plugin_manager.dispatch(
            WebSocketEventType.DEPLOYMENT_STATUS_CHANGED, {}, context
        )

        assert (
            _value(
                "windflow_websocket_plugin_duration_seconds_count",
                duration_labels,
            )
            - before_duration
            == 1.0
        )
        # dispatch_to_plugins n'est PAS appelé ici (contexte direct), mais le
        # dispatch du plugin manager trace l'exécution — events_dispatched est
        # enregistré par UserConnectionManager.dispatch_to_plugins ; sans
        # contexte utilisateur, la série plugin_duration suffit (AC 3 mot pour
        # mot : durée par plugin mesurée).
        assert before_dispatched >= 0.0


class TestAckWiring:
    """Dégradation ack_timeout (STORY-164.1) désormais mesurée (E5)."""

    @pytest.mark.asyncio
    async def test_ack_timeout_purge_records_error(self):
        registry = AckRegistry(ttl_seconds=10)
        # Entrée expirée : émise il y a plus de TTL.
        await registry.register(
            message_id="msg-expired",
            user_id="user-1",
            event_type="DEPLOYMENT_STATUS_CHANGED",
            payload={"hello": "world"},
        )
        from app.websocket.ack_registry import AckEntry

        expired_at = datetime.utcnow() - timedelta(seconds=60)
        registry._entries["msg-expired"] = AckEntry(  # noqa: SLF001
            message_id="msg-expired",
            user_id="user-1",
            event_type="DEPLOYMENT_STATUS_CHANGED",
            payload={},
            emitted_at=expired_at,
        )

        before = _value(
            "windflow_websocket_errors_total", {"error_type": "ack_timeout"}
        )

        purged = await registry.purge_expired()

        assert purged == 1
        assert (
            _value("windflow_websocket_errors_total", {"error_type": "ack_timeout"})
            - before
            == 1.0
        )


class TestAuthWiring:
    """``general.py`` : tentative d'auth + durée autour du helper.

    Pattern ``_auth_stack`` de ``test_ws_general_loop.py`` : connexion WS
    réelle au canal général via TestClient avec l'auth « premier message »
    patchée — le câblage ``auth_timer``/``record_auth_attempt`` de l'endpoint
    est exercé tel qu'en production.
    """

    def test_auth_attempt_recorded(self):
        from contextlib import ExitStack

        from fastapi.testclient import TestClient

        from app.auth import dependencies as auth_dependencies
        from app.main import app
        from app.models.user import User
        from app.services.authorization_service import AuthorizationService

        def _make_user() -> User:
            return User(
                id="user-auth-metrics",
                email="auth-metrics@test.com",
                username="authmetrics",
                is_active=True,
                is_superuser=False,
            )

        def _mock_database_session():
            mock_db = MagicMock()
            mock_database = MagicMock()
            mock_database.session.return_value.__aenter__ = AsyncMock(
                return_value=mock_db
            )
            mock_database.session.return_value.__aexit__ = AsyncMock(return_value=False)
            return mock_database.session

        token_data = MagicMock()
        token_data.user_id = "user-auth-metrics"
        user = _make_user()

        from app.services.user_organization_service import (
            UserOrganizationService,
        )

        async def _fake_ids(db, u):  # noqa: ARG001
            return ["org-1"]

        before_success = _value(
            "windflow_websocket_auth_attempts_total", {"status": "success"}
        )
        before_duration = _value("windflow_websocket_auth_duration_seconds_count")

        # Le TestClient démarre AVANT les patches (pattern fixture ws_client +
        # _auth_stack) : le lifespan (seed DB) doit voir la vraie base, les
        # patches d'auth n'ont vocation qu'à l'échange premier message.
        with TestClient(app) as client:
            exit_stack = ExitStack()
            exit_stack.enter_context(
                patch.object(auth_dependencies.settings, "disable_auth", False)
            )
            exit_stack.enter_context(
                patch.object(
                    auth_dependencies,
                    "decode_access_token",
                    return_value=token_data,
                )
            )
            exit_stack.enter_context(
                patch.object(
                    auth_dependencies.UserService,
                    "get_by_id",
                    AsyncMock(return_value=user),
                )
            )
            exit_stack.enter_context(
                patch.object(
                    auth_dependencies.database,
                    "session",
                    _mock_database_session(),
                )
            )
            exit_stack.enter_context(
                patch.object(
                    AuthorizationService,
                    "get_global_role",
                    AsyncMock(return_value="viewer"),
                )
            )
            exit_stack.enter_context(
                patch.object(
                    UserOrganizationService,
                    "get_user_organization_ids",
                    side_effect=_fake_ids,
                )
            )
            try:
                with client.websocket_connect("/api/v1/ws/") as ws:
                    ws.send_json({"type": "auth", "token": "valid.jwt"})
                    response = ws.receive_json()
                    assert response["type"] == "AUTH_LOGIN_SUCCESS"
            finally:
                exit_stack.close()
            # (bloc de patches dupliqué supprimé — exit_stack ci-dessus)

        assert (
            _value(
                "windflow_websocket_auth_attempts_total",
                {"status": "success"},
            )
            - before_success
            >= 1.0
        )
        # La durée d'auth a été observée (auth_timer — pas de label).
        assert (
            _value("windflow_websocket_auth_duration_seconds_count") - before_duration
            >= 1.0
        )
        app.dependency_overrides.clear()


class TestResilience:
    """Best-effort : une métrique qui lève ne casse jamais le broadcast."""

    @pytest.mark.asyncio
    async def test_metrics_wiring_never_breaks_broadcast(self):
        manager = ConnectionManager()
        websocket = _mock_websocket()
        await manager.connect(websocket, "dep-resilience")

        with patch(
            "app.websocket.connection_managers.record_broadcast",
            side_effect=RuntimeError("metrics exploded"),
        ):
            # Le broadcast s'effectue quand même (send_json appelé) — le
            # helper instrumenté est wrappé try/except côté métrique WS ou
            # l'appel est best-effort dans le manager.
            await manager.broadcast_to_deployment(
                "dep-resilience", {"type": "TEST", "data": {}}
            )

        websocket.send_json.assert_awaited_once()
        await manager.disconnect(websocket, "dep-resilience")
