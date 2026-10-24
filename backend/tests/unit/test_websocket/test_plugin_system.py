"""Tests du système de plugins WebSocket (STORY-165 — Tâche 3, AC 3).

Couvre ``app/websocket/plugin.py`` (70 % → ≥ 90 %) et les **effets** non
couverts des plugins par défaut :

- ``WebSocketPluginManager`` **isolé** (jamais le singleton
  ``plugin_manager`` global) : ``register`` (index par ``listens_for``),
  register **duplicate** → warning + remplacement, ``register_message_handler``
  (+ duplicate), ``unregister`` (retrait de l'index ; **inconnu** → warning
  no-op), ``get`` / ``list`` ;
- ``initialize_all`` : tous initialisés ; **exception d'un plugin** →
  absorbée + log error (les autres initialisés) ;
- ``dispatch`` : **sans ``initialize_all``** → warning + return ; event sans
  handler → no-op ; N handlers → tous exécutés ; **exception d'un handler**
  → logguée via le contexte, jamais propagée ;
- ``handle_client_message`` : sans ``type`` → ``{"type": "error"}`` ; type
  sans handler → ``None`` (log debug) ; handler qui répond → réponse
  retournée ; **handler qui lève** → ``{"type": "error", "message":
  "Handler error: …"}`` ;
- ``cleanup_all`` : tous nettoyés ; exception absorbée + log ;
- Effets des plugins par défaut : ``audit_logger.handle_event`` (ligne de
  log émise par type écouté, extra structuré), ``deployment_monitor``
  (log status/progress), ``deployment_notifications.logs_subscribed`` →
  ``subscribe_to_deployment_logs``.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock

import pytest

from app.schemas.websocket_events import WebSocketEventType
from app.websocket.plugin import (
    PluginContext,
    WebSocketMessageHandler,
    WebSocketPlugin,
    WebSocketPluginManager,
)

EVENT_LOGGER = "app.websocket.plugin"


# ===========================================================================
# Fakes — plugins/handlers de test + contexte
# ===========================================================================


class FakePlugin(WebSocketPlugin):
    """Plugin espion : enregistre les appels, peut échouer à la demande."""

    def __init__(
        self,
        name: str = "fake",
        listens: Optional[list] = None,
        init_error: Optional[Exception] = None,
        handle_error: Optional[Exception] = None,
        cleanup_error: Optional[Exception] = None,
    ):
        self.name = name
        self.listens_for = listens or []
        self.initialized = False
        self.handled_events: list = []
        self.cleaned_up = False
        self._init_error = init_error
        self._handle_error = handle_error
        self._cleanup_error = cleanup_error

    async def initialize(self, context: PluginContext) -> None:
        if self._init_error:
            raise self._init_error
        self.initialized = True

    async def handle_event(
        self, event: WebSocketEventType, data: Dict[str, Any], context: PluginContext
    ) -> None:
        if self._handle_error:
            raise self._handle_error
        self.handled_events.append((event, data))

    async def cleanup(self) -> None:
        if self._cleanup_error:
            raise self._cleanup_error
        self.cleaned_up = True


class FakeHandler(WebSocketMessageHandler):
    """Handler client→serveur espion : réponse configurable ou exception."""

    def __init__(
        self,
        name: str = "fake_handler",
        handles: Optional[list] = None,
        response: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
    ):
        self.name = name
        self.handles_message_types = handles or []
        self.initialized = False
        self.handled_messages: list = []
        self.cleaned_up = False
        self._response = response
        self._error = error

    async def initialize(self, context: PluginContext) -> None:
        self.initialized = True

    async def handle_message(
        self, message: Dict[str, Any], context: PluginContext
    ) -> Optional[Dict[str, Any]]:
        if self._error:
            raise self._error
        self.handled_messages.append(message)
        return self._response

    async def cleanup(self) -> None:
        self.cleaned_up = True


@pytest.fixture()
def context():
    """PluginContext minimal : logger réel caplog-compatible, broadcasts mockés."""
    return SimpleNamespace(
        logger=logging.getLogger("test.plugin_context"),
        broadcast_to_user=AsyncMock(),
        broadcast_to_event_subscribers=AsyncMock(),
        broadcast_deployment_log_to_subscribers=AsyncMock(),
        user=None,
    )


# ===========================================================================
# register / unregister / get / list
# ===========================================================================


class TestRegisterUnregister:
    def test_register_indexes_by_listens_for(self):
        plugin_manager = WebSocketPluginManager()
        plugin = FakePlugin(
            listens=[
                WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
                WebSocketEventType.DEPLOYMENT_PROGRESS,
            ]
        )

        plugin_manager.register(plugin)

        assert plugin_manager.get("fake") is plugin
        assert (
            plugin
            in plugin_manager._event_handlers[
                WebSocketEventType.DEPLOYMENT_STATUS_CHANGED
            ]
        )
        assert (
            plugin
            in plugin_manager._event_handlers[WebSocketEventType.DEPLOYMENT_PROGRESS]
        )

    def test_register_duplicate_warns_and_replaces(self, caplog):
        plugin_manager = WebSocketPluginManager()
        first = FakePlugin(name="dup", listens=[WebSocketEventType.AUTH_LOGOUT])
        second = FakePlugin(name="dup", listens=[WebSocketEventType.AUTH_LOGOUT])

        with caplog.at_level(logging.WARNING, logger=EVENT_LOGGER):
            plugin_manager.register(first)
            plugin_manager.register(second)

        assert plugin_manager.get("dup") is second
        assert any("already registered" in r.message for r in caplog.records)

    @pytest.mark.xfail(
        reason=(
            "Bug production détecté (non corrigé, décision 7 STORY-165) : "
            "register en duplicate remplace _plugins[name] mais ne retire "
            "jamais l'ancienne instance de _event_handlers → le plugin "
            "'remplacé' continue de recevoir les dispatch (plugin.py:200-206). "
            "Fix attendue : discard de l'ancien plugin des index avant "
            "ré-indexation (ou unregister préalable)."
        ),
        strict=True,
    )
    def test_register_duplicate_replaces_event_index(self):
        plugin_manager = WebSocketPluginManager()
        first = FakePlugin(name="dup", listens=[WebSocketEventType.AUTH_LOGOUT])
        second = FakePlugin(name="dup", listens=[WebSocketEventType.AUTH_LOGOUT])

        plugin_manager.register(first)
        plugin_manager.register(second)

        # L'index par event doit pointer vers la nouvelle instance uniquement.
        handlers = plugin_manager._event_handlers[WebSocketEventType.AUTH_LOGOUT]
        assert handlers == {second}

    def test_register_message_handler_indexes_types(self):
        plugin_manager = WebSocketPluginManager()
        handler = FakeHandler(handles=["subscribe", "unsubscribe"])

        plugin_manager.register_message_handler(handler)

        assert "subscribe" in plugin_manager._message_type_handlers
        assert plugin_manager._message_type_handlers["subscribe"] == {handler}

    def test_register_message_handler_duplicate_warns(self, caplog):
        plugin_manager = WebSocketPluginManager()
        first = FakeHandler(name="dup", handles=["x"])
        second = FakeHandler(name="dup", handles=["x"])

        with caplog.at_level(logging.WARNING, logger=EVENT_LOGGER):
            plugin_manager.register_message_handler(first)
            plugin_manager.register_message_handler(second)

        assert plugin_manager._message_handlers["dup"] is second
        assert any("already registered" in r.message for r in caplog.records)

    def test_unregister_removes_from_indexes(self):
        plugin_manager = WebSocketPluginManager()
        plugin = FakePlugin(listens=[WebSocketEventType.AUTH_LOGOUT])
        plugin_manager.register(plugin)

        plugin_manager.unregister("fake")

        assert plugin_manager.get("fake") is None
        assert plugin_manager.list() == []
        # La clé d'index devenue vide est supprimée.
        assert WebSocketEventType.AUTH_LOGOUT not in plugin_manager._event_handlers

    def test_unregister_keeps_index_with_remaining_plugins(self):
        plugin_manager = WebSocketPluginManager()
        first = FakePlugin(name="a", listens=[WebSocketEventType.AUTH_LOGOUT])
        second = FakePlugin(name="b", listens=[WebSocketEventType.AUTH_LOGOUT])
        plugin_manager.register(first)
        plugin_manager.register(second)

        plugin_manager.unregister("a")

        assert plugin_manager._event_handlers[WebSocketEventType.AUTH_LOGOUT] == {
            second
        }

    def test_unregister_unknown_warns_noop(self, caplog):
        plugin_manager = WebSocketPluginManager()

        with caplog.at_level(logging.WARNING, logger=EVENT_LOGGER):
            plugin_manager.unregister("ghost")

        assert any("'ghost' not found" in r.message for r in caplog.records)

    def test_list_returns_all_plugins(self):
        plugin_manager = WebSocketPluginManager()
        first, second = FakePlugin(name="a"), FakePlugin(name="b")
        plugin_manager.register(first)
        plugin_manager.register(second)

        assert set(plugin_manager.list()) == {first, second}

    def test_get_unknown_returns_none(self):
        assert WebSocketPluginManager().get("ghost") is None


# ===========================================================================
# initialize_all
# ===========================================================================


class TestInitializeAll:
    async def test_initializes_all_plugins_and_handlers(self, context):
        plugin_manager = WebSocketPluginManager()
        plugin = FakePlugin(listens=[WebSocketEventType.AUTH_LOGOUT])
        handler = FakeHandler(handles=["x"])
        plugin_manager.register(plugin)
        plugin_manager.register_message_handler(handler)

        await plugin_manager.initialize_all(context)

        assert plugin.initialized
        assert handler.initialized
        assert plugin_manager._context is context

    async def test_plugin_init_exception_absorbed_others_initialized(self, context):
        plugin_manager = WebSocketPluginManager()
        failing = FakePlugin(
            name="bad",
            init_error=RuntimeError("boom"),
        )
        healthy_plugin = FakePlugin(name="good")
        healthy_handler = FakeHandler(name="good_handler", handles=["x"])
        plugin_manager.register(failing)
        plugin_manager.register(healthy_plugin)
        plugin_manager.register_message_handler(healthy_handler)

        with caplog_scope(context.logger, logging.ERROR):
            await plugin_manager.initialize_all(context)

        assert not failing.initialized
        assert healthy_plugin.initialized
        assert healthy_handler.initialized

    async def test_handler_init_exception_absorbed(self, context):
        plugin_manager = WebSocketPluginManager()
        failing = FakeHandler(
            name="bad",
            handles=["x"],
            error=None,
        )
        failing.initialize = AsyncMock(side_effect=RuntimeError("boom"))
        plugin_manager.register_message_handler(failing)

        with caplog_scope(context.logger, logging.ERROR):
            await plugin_manager.initialize_all(context)


class caplog_scope:
    """Capture les records du logger du contexte via un handler mémoire."""

    def __init__(self, logger: logging.Logger, level: int):
        self._logger = logger
        self._level = level
        self._handler = logging.Handler()

        class MemoryHandler(logging.Handler):
            def __init__(self):
                super().__init__(level=logging.DEBUG)
                self.records: list[logging.LogRecord] = []

            def emit(self, record: logging.LogRecord) -> None:
                self.records.append(record)

        self._memory = MemoryHandler()

    def __enter__(self):
        self._logger.addHandler(self._memory)
        return self._memory

    def __exit__(self, *exc_info):
        self._logger.removeHandler(self._memory)
        assert any(
            r.levelno >= self._level for r in self._memory.records
        ), "un log ERROR/WARNING était attendu (exception absorbée)"


# ===========================================================================
# dispatch
# ===========================================================================


class TestDispatch:
    async def test_dispatch_without_initialize_warns_and_returns(self, context, caplog):
        plugin_manager = WebSocketPluginManager()
        plugin = FakePlugin(listens=[WebSocketEventType.AUTH_LOGOUT])
        plugin_manager.register(plugin)

        with caplog.at_level(logging.WARNING, logger=EVENT_LOGGER):
            await plugin_manager.dispatch(WebSocketEventType.AUTH_LOGOUT, {}, context)

        assert any("not initialized" in r.message for r in caplog.records)
        assert plugin.handled_events == []

    async def test_dispatch_without_handler_is_noop(self, context):
        plugin_manager = WebSocketPluginManager()
        plugin = FakePlugin(listens=[WebSocketEventType.AUTH_LOGOUT])
        plugin_manager.register(plugin)
        await plugin_manager.initialize_all(context)

        # Event non écouté par le plugin → aucun effet.
        await plugin_manager.dispatch(
            WebSocketEventType.NOTIFICATION_SYSTEM, {}, context
        )

        assert plugin.handled_events == []

    async def test_dispatch_executes_all_listening_handlers(self, context):
        plugin_manager = WebSocketPluginManager()
        first = FakePlugin(name="a", listens=[WebSocketEventType.DEPLOYMENT_PROGRESS])
        second = FakePlugin(name="b", listens=[WebSocketEventType.DEPLOYMENT_PROGRESS])
        plugin_manager.register(first)
        plugin_manager.register(second)
        await plugin_manager.initialize_all(context)

        payload = {"deployment_id": "dep-1", "progress": 42}
        await plugin_manager.dispatch(
            WebSocketEventType.DEPLOYMENT_PROGRESS, payload, context
        )

        assert first.handled_events == [
            (WebSocketEventType.DEPLOYMENT_PROGRESS, payload)
        ]
        assert second.handled_events == [
            (WebSocketEventType.DEPLOYMENT_PROGRESS, payload)
        ]

    async def test_handler_exception_logged_never_propagated(self, context):
        plugin_manager = WebSocketPluginManager()
        failing = FakePlugin(
            name="bad",
            listens=[WebSocketEventType.AUTH_LOGOUT],
            handle_error=RuntimeError("handler boom"),
        )
        healthy = FakePlugin(name="good", listens=[WebSocketEventType.AUTH_LOGOUT])
        plugin_manager.register(failing)
        plugin_manager.register(healthy)
        await plugin_manager.initialize_all(context)

        with caplog_scope(context.logger, logging.ERROR):
            # Ne doit jamais lever (gather return_exceptions=True + try/except).
            await plugin_manager.dispatch(WebSocketEventType.AUTH_LOGOUT, {}, context)

        # Le handler sain a bien été exécuté malgré l'échec du premier.
        assert len(healthy.handled_events) == 1


# ===========================================================================
# handle_client_message
# ===========================================================================


class TestHandleClientMessage:
    async def test_message_without_type_returns_error(self, context):
        plugin_manager = WebSocketPluginManager()

        response = await plugin_manager.handle_client_message({"data": {}}, context)

        assert response == {"type": "error", "message": "Missing message type"}

    async def test_unknown_type_returns_none_logs_debug(self, context, caplog):
        plugin_manager = WebSocketPluginManager()

        with caplog.at_level(logging.DEBUG, logger="test.plugin_context"):
            response = await plugin_manager.handle_client_message(
                {"type": "unknown_type"}, context
            )

        assert response is None
        assert any(
            "No handler for message type: unknown_type" in r.message
            for r in caplog.records
        )

    async def test_handler_response_returned(self, context):
        plugin_manager = WebSocketPluginManager()
        expected = {"type": "subscribed", "data": {"event_type": "EVT"}}
        handler = FakeHandler(handles=["subscribe"], response=expected)
        plugin_manager.register_message_handler(handler)

        response = await plugin_manager.handle_client_message(
            {"type": "subscribe", "data": {"event_type": "EVT"}}, context
        )

        assert response == expected
        assert handler.handled_messages == [
            {"type": "subscribe", "data": {"event_type": "EVT"}}
        ]

    async def test_all_silent_handlers_return_none(self, context):
        plugin_manager = WebSocketPluginManager()
        first = FakeHandler(name="silent_a", handles=["x"], response=None)
        second = FakeHandler(name="silent_b", handles=["x"], response=None)
        plugin_manager.register_message_handler(first)
        plugin_manager.register_message_handler(second)

        response = await plugin_manager.handle_client_message({"type": "x"}, context)

        # Aucun handler ne répond → None (itération jusqu'au bout du set).
        assert response is None
        assert first.handled_messages and second.handled_messages

    async def test_handler_raising_returns_error_response(self, context):
        plugin_manager = WebSocketPluginManager()
        handler = FakeHandler(handles=["boom"], error=RuntimeError("kaboom"))
        plugin_manager.register_message_handler(handler)

        with caplog_scope(context.logger, logging.ERROR):
            response = await plugin_manager.handle_client_message(
                {"type": "boom"}, context
            )

        assert response["type"] == "error"
        assert response["message"] == "Handler error: kaboom"


# ===========================================================================
# cleanup_all
# ===========================================================================


class TestCleanupAll:
    async def test_cleans_up_plugins_and_handlers(self, context):
        plugin_manager = WebSocketPluginManager()
        plugin = FakePlugin(listens=[WebSocketEventType.AUTH_LOGOUT])
        handler = FakeHandler(handles=["x"])
        plugin_manager.register(plugin)
        plugin_manager.register_message_handler(handler)

        await plugin_manager.cleanup_all(context)

        assert plugin.cleaned_up
        assert handler.cleaned_up

    async def test_cleanup_exception_absorbed_others_cleaned(self, context, caplog):
        plugin_manager = WebSocketPluginManager()
        failing = FakePlugin(name="bad", cleanup_error=RuntimeError("cleanup boom"))
        healthy = FakePlugin(name="good")
        plugin_manager.register(failing)
        plugin_manager.register(healthy)

        with caplog.at_level(logging.ERROR, logger=EVENT_LOGGER):
            await plugin_manager.cleanup_all(context)

        assert any(
            "Failed to cleanup plugin 'bad'" in r.message for r in caplog.records
        )
        assert healthy.cleaned_up

    async def test_handler_cleanup_exception_absorbed(self, context, caplog):
        plugin_manager = WebSocketPluginManager()
        failing = FakeHandler(name="bad", handles=["x"])
        failing.cleanup = AsyncMock(side_effect=RuntimeError("boom"))
        plugin_manager.register_message_handler(failing)

        with caplog.at_level(logging.ERROR, logger=EVENT_LOGGER):
            await plugin_manager.cleanup_all(context)

        assert any(
            "Failed to cleanup handler 'bad'" in r.message for r in caplog.records
        )


# ===========================================================================
# Effets des plugins par défaut — audit_logger (l.64-120)
# ===========================================================================


class TestAuditLoggerEffects:
    @pytest.mark.parametrize(
        ("event", "expected_level"),
        [
            (WebSocketEventType.AUTH_LOGIN_SUCCESS, logging.INFO),
            (WebSocketEventType.AUTH_LOGOUT, logging.INFO),
            (WebSocketEventType.AUTH_TOKEN_REFRESH, logging.INFO),
            (WebSocketEventType.SESSION_EXPIRED, logging.WARNING),
            (WebSocketEventType.SESSION_AUTH_REQUIRED, logging.WARNING),
            (WebSocketEventType.SESSION_PERMISSION_CHANGED, logging.INFO),
            (WebSocketEventType.SESSION_ORGANIZATION_CHANGED, logging.INFO),
        ],
    )
    async def test_listened_event_emits_structured_log(
        self, context, event, expected_level
    ):
        from app.websocket.plugins.audit_logger import AuditLoggerPlugin

        plugin = AuditLoggerPlugin()
        context.user = SimpleNamespace(id="user-77", username="alice")

        with caplog_for(context.logger) as records:
            await plugin.handle_event(event, {"k": "v"}, context)

        matching = [r for r in records if r.levelno == expected_level]
        assert matching, f"aucun log {expected_level} émis pour {event}"
        extra = matching[0].__dict__
        assert extra.get("event") == event.value
        assert extra.get("user_id") == "user-77"
        # SESSION_AUTH_REQUIRED n'embarque pas username (audit_logger.py:97) ;
        # tous les autres types écoutés le portent.
        if event is not WebSocketEventType.SESSION_AUTH_REQUIRED:
            assert extra.get("username") == "alice"
        assert extra.get("timestamp")

    async def test_anonymous_user_logged_as_anonymous(self, context):
        from app.websocket.plugins.audit_logger import AuditLoggerPlugin

        plugin = AuditLoggerPlugin()
        # context.user est None → "anonymous", jamais de crash.
        with caplog_for(context.logger) as records:
            await plugin.handle_event(
                WebSocketEventType.AUTH_LOGIN_SUCCESS, {}, context
            )

        info_records = [r for r in records if r.levelno == logging.INFO]
        assert info_records
        assert info_records[0].__dict__.get("user_id") == "anonymous"

    async def test_invalid_payload_never_crashes(self, context):
        from app.websocket.plugins.audit_logger import AuditLoggerPlugin

        plugin = AuditLoggerPlugin()
        # Payload quelconque (None, données malformées) → aucune exception.
        await plugin.handle_event(WebSocketEventType.AUTH_LOGOUT, None, context)  # type: ignore[arg-type]
        await plugin.handle_event(
            WebSocketEventType.SESSION_EXPIRED, {"unexpected": object()}, context
        )


# ===========================================================================
# Effets des plugins par défaut — deployment_monitor (l.48-74)
# ===========================================================================


class TestDeploymentMonitorEffects:
    async def test_status_change_emits_info_log(self, context):
        from app.websocket.plugins.deployment_monitor import DeploymentMonitorPlugin

        plugin = DeploymentMonitorPlugin()

        with caplog_for(context.logger) as records:
            await plugin.handle_event(
                WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
                {
                    "deploymentId": "dep-5",
                    "deploymentName": "my stack",
                    "oldStatus": "deploying",
                    "newStatus": "running",
                },
                context,
            )

        matching = [
            r
            for r in records
            if r.levelno == logging.INFO and "Deployment status changed" in r.message
        ]
        assert matching
        extra = matching[0].__dict__
        assert extra.get("deployment_id") == "dep-5"
        assert extra.get("new_status") == "running"

    async def test_logs_update_emits_debug_log(self, context):
        from app.websocket.plugins.deployment_monitor import DeploymentMonitorPlugin

        plugin = DeploymentMonitorPlugin()

        with caplog_for(context.logger, level=logging.DEBUG) as records:
            await plugin.handle_event(
                WebSocketEventType.DEPLOYMENT_LOGS_UPDATE,
                {"deploymentId": "dep-5", "logs": ["l1", "l2"], "level": "info"},
                context,
            )

        matching = [
            r
            for r in records
            if r.levelno == logging.DEBUG and "Deployment logs updated" in r.message
        ]
        assert matching
        assert matching[0].__dict__.get("log_count") == 2

    async def test_progress_emits_info_log_with_step(self, context):
        from app.websocket.plugins.deployment_monitor import DeploymentMonitorPlugin

        plugin = DeploymentMonitorPlugin()

        with caplog_for(context.logger) as records:
            await plugin.handle_event(
                WebSocketEventType.DEPLOYMENT_PROGRESS,
                {"deployment_id": "dep-5", "progress": 60, "current_step": "deploying"},
                context,
            )

        matching = [
            r
            for r in records
            if r.levelno == logging.INFO and "Deployment progress" in r.message
        ]
        assert matching
        extra = matching[0].__dict__
        assert extra.get("progress") == 60
        assert extra.get("step") == "deploying"


# ===========================================================================
# Effets des plugins par défaut — deployment_notifications (l.122-148)
# ===========================================================================


class TestDeploymentNotificationsEffects:
    async def test_logs_update_broadcasts_to_log_subscribers(self, context):
        from app.websocket.plugins.deployment_notifications import (
            DeploymentNotificationsPlugin,
        )

        plugin = DeploymentNotificationsPlugin()

        await plugin.handle_event(
            WebSocketEventType.DEPLOYMENT_LOGS_UPDATE,
            {
                "deployment_id": "dep-3",
                "logs": "applying manifest",
                "user_id": "user-9",
            },
            context,
        )

        # Effet logs_subscribed : les abonnés aux logs du déploiement
        # reçoivent le message DEPLOYMENT_LOGS_UPDATE.
        context.broadcast_deployment_log_to_subscribers.assert_awaited_once()
        deployment_id, message = (
            context.broadcast_deployment_log_to_subscribers.await_args.args
        )
        assert deployment_id == "dep-3"
        assert message["type"] == "DEPLOYMENT_LOGS_UPDATE"
        assert message["data"]["logs"] == "applying manifest"

        # L'utilisateur initiateur est aussi notifié directement.
        context.broadcast_to_user.assert_awaited_once()
        user_id, user_message = context.broadcast_to_user.await_args.args
        assert user_id == "user-9"
        assert user_message["type"] == "DEPLOYMENT_LOGS_UPDATE"

    async def test_logs_update_without_helpers_is_noop(self):
        """Contexte sans fonctions broadcast (None) → aucun appel, pas de crash."""
        from app.websocket.plugins.deployment_notifications import (
            DeploymentNotificationsPlugin,
        )

        plugin = DeploymentNotificationsPlugin()
        bare_context = SimpleNamespace(
            logger=logging.getLogger("test.notifications"),
            broadcast_to_user=None,
            broadcast_to_event_subscribers=None,
            broadcast_deployment_log_to_subscribers=None,
            user=None,
        )

        await plugin.handle_event(
            WebSocketEventType.DEPLOYMENT_LOGS_UPDATE,
            {"deployment_id": "dep-3", "logs": "x"},
            bare_context,
        )

    async def test_progress_update_broadcasts_to_user(self, context):
        from app.websocket.plugins.deployment_notifications import (
            DeploymentNotificationsPlugin,
        )

        plugin = DeploymentNotificationsPlugin()

        await plugin.handle_event(
            WebSocketEventType.DEPLOYMENT_PROGRESS,
            {
                "deployment_id": "dep-3",
                "progress": 80,
                "current_step": "starting",
                "user_id": "user-9",
            },
            context,
        )

        context.broadcast_to_user.assert_awaited_once()
        message = context.broadcast_to_user.await_args.args[1]
        assert message["type"] == "DEPLOYMENT_PROGRESS"
        assert message["data"]["progress"] == 80
        # Pas de diffusion aux abonnés de logs pour la progression.
        context.broadcast_deployment_log_to_subscribers.assert_not_awaited()


# ===========================================================================
# Helper de capture des logs du logger du contexte
# ===========================================================================


def caplog_for(logger: logging.Logger, level: int = logging.INFO):
    """Context manager capturant les records d'un logger spécifique.

    Équivalent ciblé de ``caplog.at_level`` pour les loggers de test hors
    système ``caplog`` : force le level effectif du logger pendant la
    capture (DEBUG par défaut non propagé autrement).
    """

    class _Capture:
        def __init__(self):
            self.records: list[logging.LogRecord] = []
            self._handler = logging.Handler()
            self._previous_level: Optional[int] = None

        def __enter__(self):
            self._previous_level = logger.level
            logger.setLevel(level)
            self._handler.emit = lambda record: self.records.append(record)  # type: ignore[method-assign]
            logger.addHandler(self._handler)
            return self.records

        def __exit__(self, *exc_info):
            logger.removeHandler(self._handler)
            logger.setLevel(self._previous_level or logging.NOTSET)

    return _Capture()
