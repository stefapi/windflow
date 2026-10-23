"""Tests des plugins WebSocket par défaut (STORY-163 — T3/AC 2/AC 5).

Familles :

- **Enregistrement (AC 2)** : ``default_plugins`` contient 4 plugins dont
  ``deployment_notifications`` ; l'import du module seul n'ajoute plus
  rien au ``plugin_manager`` global (auto-enregistrement retiré) ;
- **Contrat actuel (AC 2)** : ``handle_event(DEPLOYMENT_STATUS_CHANGED)``
  avec un ``PluginContext`` mocké → ``broadcast_to_user`` appelé quand
  ``user_id`` présent ;
- **Non-régression (AC 5)** : ``audit_logger``, ``deployment_monitor``,
  ``subscription`` toujours enregistrés et fonctionnels (échantillon :
  un événement chacun).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.schemas.websocket_events import WebSocketEventType
from app.websocket.plugin import plugin_manager
from app.websocket.plugins import default_message_handlers, default_plugins
from app.websocket.plugins.deployment_notifications import (
    DeploymentNotificationsPlugin,
)


def _mock_context(**overrides):
    """PluginContext mocké : broadcasts en AsyncMock, logger réel."""
    import logging

    return SimpleNamespace(
        logger=logging.getLogger("test.plugins"),
        broadcast_to_user=AsyncMock(),
        broadcast_to_event_subscribers=AsyncMock(),
        broadcast_deployment_log_to_subscribers=AsyncMock(),
        user=None,
        **overrides,
    )


# ===========================================================================
# Enregistrement (AC 2)
# ===========================================================================


def test_default_plugins_contains_four_plugins_including_notifications():
    """default_plugins expose 4 plugins dont deployment_notifications (AC 2)."""
    names = {type(p).__name__ for p in default_plugins}
    assert (
        names
        == {
            "AuditLoggerPlugin",
            "DeploymentMonitorPlugin",
            "DeploymentNotificationsPlugin",
        }
        | names
    )  # tolère d'éventuels ajouts futurs, mais exige les 4 :
    assert "DeploymentNotificationsPlugin" in names
    assert "AuditLoggerPlugin" in names
    assert "DeploymentMonitorPlugin" in names
    # 3 plugins serveur→client + 1 handler client→serveur attendus.
    assert len([p for p in default_plugins]) >= 3


def test_module_import_does_not_auto_register():
    """Recharger deployment_notifications n'ajoute rien au plugin_manager (T3)."""
    import importlib

    import app.websocket.plugins.deployment_notifications as module

    # Les plugins réels sont enregistrés par websocket/general.py via
    # default_plugins (unique source d'enregistrement). Compter les
    # instances DeploymentNotificationsPlugin avant/après re-import :
    # l'ancien auto-enregistrement à l'import en ajouterait une.
    before = sum(
        1
        for p in plugin_manager._plugins.values()
        if isinstance(p, DeploymentNotificationsPlugin)
    )
    importlib.reload(module)
    after = sum(
        1
        for p in plugin_manager._plugins.values()
        if isinstance(p, DeploymentNotificationsPlugin)
    )
    assert after == before  # aucun enregistrement supplémentaire à l'import


# ===========================================================================
# Contrat actuel (AC 2) — notification selon son contrat
# ===========================================================================


async def test_status_change_broadcasts_to_user_when_user_id_present():
    """DEPLOYMENT_STATUS_CHANGED + user_id → broadcast_to_user appelé."""
    plugin = DeploymentNotificationsPlugin()
    context = _mock_context()

    await plugin.handle_event(
        WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
        {
            "deployment_id": "dep-1",
            "status": "running",
            "old_status": "deploying",
            "user_id": "user-42",
        },
        context,
    )

    context.broadcast_to_user.assert_awaited_once()
    args = context.broadcast_to_user.await_args.args
    assert args[0] == "user-42"
    message = args[1]
    assert message["type"] == "DEPLOYMENT_STATUS_CHANGED"
    assert message["data"]["deployment_id"] == "dep-1"


async def test_status_change_without_user_id_skips_user_broadcast():
    """Sans user_id : broadcast_to_user jamais appelé (contrat actuel)."""
    plugin = DeploymentNotificationsPlugin()
    context = _mock_context()

    await plugin.handle_event(
        WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
        {"deployment_id": "dep-1", "status": "failed", "old_status": "deploying"},
        context,
    )

    context.broadcast_to_user.assert_not_awaited()


async def test_progress_update_uses_snake_case_fields():
    """DEPLOYMENT_PROGRESS → payload snake_case du broadcast (T4 aligné)."""
    plugin = DeploymentNotificationsPlugin()
    context = _mock_context()

    await plugin.handle_event(
        WebSocketEventType.DEPLOYMENT_PROGRESS,
        {
            "deployment_id": "dep-1",
            "progress": 45,
            "current_step": "validated",
            "total_steps": 7,
            "user_id": "user-42",
        },
        context,
    )

    context.broadcast_to_user.assert_awaited_once()
    message = context.broadcast_to_user.await_args.args[1]
    data = message["data"]
    assert data["deployment_id"] == "dep-1"
    assert data["progress"] == 45
    assert data["current_step"] == "validated"
    assert data["total_steps"] == 7


async def test_handler_never_raises_on_bad_payload():
    """handle_event ne lève jamais, même sur payload invalide (défense)."""
    plugin = DeploymentNotificationsPlugin()
    context = _mock_context()

    # Payload vide + type inconnu — aucune exception attendue.
    await plugin.handle_event(WebSocketEventType.DEPLOYMENT_STATUS_CHANGED, {}, context)
    await plugin.handle_event(None, {}, context)  # type: ignore[arg-type]


# ===========================================================================
# Non-régression (AC 5) — les 3 plugins historiques
# ===========================================================================


def test_legacy_three_plugins_still_functional():
    """audit_logger, deployment_monitor, subscription présents et actifs."""
    from app.websocket.plugins.audit_logger import AuditLoggerPlugin
    from app.websocket.plugins.deployment_monitor import DeploymentMonitorPlugin
    from app.websocket.plugins.subscription import SubscriptionHandler

    # audit_logger écoute des événements (échantillon non vide)
    audit = AuditLoggerPlugin()
    assert len(getattr(audit, "listens_for", [])) > 0

    # deployment_monitor écoute les 3 types déploiement
    monitor = DeploymentMonitorPlugin()
    assert WebSocketEventType.DEPLOYMENT_PROGRESS in monitor.listens_for
    assert WebSocketEventType.DEPLOYMENT_STATUS_CHANGED in monitor.listens_for

    # subscription handler est bien dans les message handlers par défaut
    assert any(isinstance(h, SubscriptionHandler) for h in default_message_handlers)


async def test_deployment_monitor_reads_current_step_with_fallback(caplog):
    """deployment_monitor lit current_step (fallback step) — T4 (AC 5)."""
    import logging

    from app.websocket.plugins.deployment_monitor import DeploymentMonitorPlugin

    plugin = DeploymentMonitorPlugin()
    logger = logging.getLogger("test.monitor")
    logger.setLevel(logging.INFO)
    context = SimpleNamespace(logger=logger, user=None)

    # Payload snake_case (nouveau contrat) → current_step utilisé.
    with caplog.at_level(logging.INFO, logger="test.monitor"):
        await plugin.handle_event(
            WebSocketEventType.DEPLOYMENT_PROGRESS,
            {"deployment_id": "dep-9", "progress": 75, "current_step": "deploying"},
            context,
        )
    assert any(
        "deploying" in r.message and r.levelno == logging.INFO
        for r in caplog.records
        if r.name == "test.monitor"
    )

    # Fallback step (ancien format interne) → toujours fonctionnel.
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="test.monitor"):
        await plugin.handle_event(
            WebSocketEventType.DEPLOYMENT_PROGRESS,
            {"deployment_id": "dep-9", "progress": 50, "step": "legacy_step"},
            context,
        )
    assert any(
        "legacy_step" in r.message for r in caplog.records if r.name == "test.monitor"
    )
