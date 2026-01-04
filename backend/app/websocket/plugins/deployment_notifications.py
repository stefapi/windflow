"""
Deployment Notifications WebSocket Plugin.

Handles real-time notifications for deployment events:
- Status changes (PENDING → DEPLOYING → RUNNING/FAILED)
- Log updates
- Progress tracking
"""

import logging
from typing import Dict, Any
from datetime import datetime

from ..plugin import WebSocketPlugin, PluginContext
from ...schemas.websocket_events import WebSocketEventType


class DeploymentNotificationsPlugin(WebSocketPlugin):
    """
    Plugin pour gérer les notifications de déploiement en temps réel.

    Ce plugin écoute les événements de déploiement et les transmet
    aux clients WebSocket appropriés.
    """

    name = "deployment_notifications"
    version = "1.0.0"
    description = "Real-time deployment status and logs notifications"

    listens_for = [
        WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
        WebSocketEventType.DEPLOYMENT_LOGS_UPDATE,
        WebSocketEventType.DEPLOYMENT_PROGRESS,
    ]

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def initialize(self, context: PluginContext) -> None:
        """Initialize the deployment notifications plugin."""
        self.logger.info("🚀 Deployment Notifications Plugin initialized")

    async def handle_event(
        self,
        event: WebSocketEventType,
        data: Dict[str, Any],
        context: PluginContext
    ) -> None:
        """
        Handle deployment events and broadcast to subscribers.

        Args:
            event: Type of deployment event
            data: Event data (deployment_id, status, logs, etc.)
            context: Plugin context with broadcast functions
        """
        try:
            if event == WebSocketEventType.DEPLOYMENT_STATUS_CHANGED:
                await self._handle_status_change(data, context)

            elif event == WebSocketEventType.DEPLOYMENT_LOGS_UPDATE:
                await self._handle_logs_update(data, context)

            elif event == WebSocketEventType.DEPLOYMENT_PROGRESS:
                await self._handle_progress_update(data, context)

        except Exception as e:
            context.logger.error(
                f"Error handling deployment event {event}: {e}",
                exc_info=True
            )

    async def _handle_status_change(
        self,
        data: Dict[str, Any],
        context: PluginContext
    ) -> None:
        """
        Handle deployment status change events.

        Broadcasts status updates to:
        1. The user who initiated the deployment
        2. All users subscribed to deployment events
        3. Organization admins (if applicable)
        """
        deployment_id = data.get("deployment_id")
        new_status = data.get("status")
        old_status = data.get("old_status")
        user_id = data.get("user_id")

        context.logger.info(
            f"📡 Deployment {deployment_id} status: {old_status} → {new_status}"
        )

        # Prepare broadcast message
        message = {
            "type": "DEPLOYMENT_STATUS_CHANGED",
            "data": {
                "deployment_id": deployment_id,
                "status": new_status,
                "old_status": old_status,
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                **data  # Include any additional data
            }
        }

        # Broadcast to specific user if available
        if user_id and context.broadcast_to_user:
            await context.broadcast_to_user(user_id, message)

        # Broadcast to all deployment event subscribers
        if context.broadcast_to_event_subscribers:
            await context.broadcast_to_event_subscribers(
                "deployment_events",
                message
            )

    async def _handle_logs_update(
        self,
        data: Dict[str, Any],
        context: PluginContext
    ) -> None:
        """
        Handle deployment logs update events.

        Broadcasts new log entries to subscribed clients.
        """
        deployment_id = data.get("deployment_id")
        logs = data.get("logs", "")
        user_id = data.get("user_id")

        # Don't log the full logs content to avoid cluttering logs
        context.logger.debug(
            f"📝 New logs for deployment {deployment_id} ({len(logs)} chars)"
        )

        # Prepare broadcast message
        message = {
            "type": "DEPLOYMENT_LOGS_UPDATE",
            "data": {
                "deployment_id": deployment_id,
                "logs": logs,
                "timestamp": datetime.utcnow().isoformat(),
                "append": data.get("append", True)  # If false, replace all logs
            }
        }

        # Broadcast to specific user
        if user_id and context.broadcast_to_user:
            await context.broadcast_to_user(user_id, message)

        # Broadcast to deployment log subscribers
        if context.broadcast_deployment_log_to_subscribers:
            await context.broadcast_deployment_log_to_subscribers(
                deployment_id,
                message
            )

    async def _handle_progress_update(
        self,
        data: Dict[str, Any],
        context: PluginContext
    ) -> None:
        """
        Handle deployment progress update events.

        Broadcasts progress percentage and current step.
        """
        deployment_id = data.get("deployment_id")
        progress = data.get("progress", 0)
        current_step = data.get("current_step", "")
        total_steps = data.get("total_steps", 100)
        user_id = data.get("user_id")

        context.logger.debug(
            f"⏳ Deployment {deployment_id} progress: {progress}% - {current_step}"
        )

        # Prepare broadcast message
        message = {
            "type": "DEPLOYMENT_PROGRESS",
            "data": {
                "deployment_id": deployment_id,
                "progress": progress,
                "current_step": current_step,
                "total_steps": total_steps,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        # Broadcast to specific user
        if user_id and context.broadcast_to_user:
            await context.broadcast_to_user(user_id, message)

        # Broadcast to deployment event subscribers
        if context.broadcast_to_event_subscribers:
            await context.broadcast_to_event_subscribers(
                f"deployment_progress_{deployment_id}",
                message
            )

    async def cleanup(self) -> None:
        """Clean up plugin resources."""
        self.logger.info("🔌 Deployment Notifications Plugin cleaned up")


# Register the plugin with the global plugin manager
from ..plugin import plugin_manager

deployment_notifications_plugin = DeploymentNotificationsPlugin()
plugin_manager.register(deployment_notifications_plugin)
