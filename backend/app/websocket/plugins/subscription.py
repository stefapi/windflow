"""
Subscription Message Handler Plugin.

Handles CLIENT → SERVER subscription messages like:
- subscribe: Subscribe to specific event types
- unsubscribe: Unsubscribe from event types
- deployment_logs: Subscribe to deployment-specific logs
"""

from typing import Dict, Any, Optional
from datetime import datetime

from ..plugin import WebSocketMessageHandler, PluginContext


class SubscriptionHandler(WebSocketMessageHandler):
    """
    Handles subscription-related messages from clients.

    This handler processes:
    - "subscribe": Client wants to receive specific event types
    - "unsubscribe": Client wants to stop receiving specific event types
    - "deployment_logs": Client wants to receive logs for a specific deployment
    """

    name = "subscription_handler"
    version = "1.0.0"
    description = "Handles WebSocket subscription messages"
    handles_message_types = ["subscribe", "unsubscribe", "deployment_logs"]

    async def handle_message(
        self,
        message: Dict[str, Any],
        context: PluginContext
    ) -> Optional[Dict[str, Any]]:
        """
        Process subscription messages.

        Args:
            message: Client message data
            context: Plugin context with WebSocket and user info

        Returns:
            Response to send back to client
        """
        message_type = message.get("type")

        if message_type == "subscribe":
            return await self._handle_subscribe(message, context)
        elif message_type == "unsubscribe":
            return await self._handle_unsubscribe(message, context)
        elif message_type == "deployment_logs":
            return await self._handle_deployment_logs(message, context)

        return None

    async def _handle_subscribe(
        self,
        message: Dict[str, Any],
        context: PluginContext
    ) -> Dict[str, Any]:
        """
        Handle subscribe message: client wants to receive specific events.

        Example message:
        {
            "type": "subscribe",
            "event_type": "DEPLOYMENT_STATUS_CHANGED"
        }
        """
        event_type = message.get("event_type")

        if not event_type:
            return {
                "type": "error",
                "message": "Missing event_type in subscribe message",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Use the helper function from websockets.py
        # This would need to be injected or imported
        from ...api.v1.websockets import subscribe_to_event

        user_id = str(context.user.id) if context.user else None
        if not user_id:
            return {
                "type": "error",
                "message": "Authentication required",
                "timestamp": datetime.utcnow().isoformat()
            }

        try:
            await subscribe_to_event(user_id, event_type, context.websocket)

            context.logger.info(
                f"User {user_id} subscribed to event type: {event_type}",
                extra={
                    "user_id": user_id,
                    "event_type": event_type,
                    "action": "subscribe"
                }
            )

            return {
                "type": "subscribed",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {"event_type": event_type}
            }
        except Exception as e:
            context.logger.error(
                f"Error subscribing to event: {e}",
                exc_info=True
            )
            return {
                "type": "error",
                "message": f"Subscription failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }

    async def _handle_unsubscribe(
        self,
        message: Dict[str, Any],
        context: PluginContext
    ) -> Dict[str, Any]:
        """
        Handle unsubscribe message: client wants to stop receiving specific events.

        Example message:
        {
            "type": "unsubscribe",
            "event_type": "DEPLOYMENT_STATUS_CHANGED"
        }
        """
        event_type = message.get("event_type")

        if not event_type:
            return {
                "type": "error",
                "message": "Missing event_type in unsubscribe message",
                "timestamp": datetime.utcnow().isoformat()
            }

        from ...api.v1.websockets import unsubscribe_from_event

        user_id = str(context.user.id) if context.user else None
        if not user_id:
            return {
                "type": "error",
                "message": "Authentication required",
                "timestamp": datetime.utcnow().isoformat()
            }

        try:
            await unsubscribe_from_event(user_id, event_type, context.websocket)

            context.logger.info(
                f"User {user_id} unsubscribed from event type: {event_type}",
                extra={
                    "user_id": user_id,
                    "event_type": event_type,
                    "action": "unsubscribe"
                }
            )

            return {
                "type": "unsubscribed",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {"event_type": event_type}
            }
        except Exception as e:
            context.logger.error(
                f"Error unsubscribing from event: {e}",
                exc_info=True
            )
            return {
                "type": "error",
                "message": f"Unsubscription failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }

    async def _handle_deployment_logs(
        self,
        message: Dict[str, Any],
        context: PluginContext
    ) -> Dict[str, Any]:
        """
        Handle deployment_logs message: client wants to receive logs for a deployment.

        Example message:
        {
            "type": "deployment_logs",
            "deployment_id": "uuid-here"
        }
        """
        deployment_id = message.get("deployment_id")

        if not deployment_id:
            return {
                "type": "error",
                "message": "Missing deployment_id in deployment_logs message",
                "timestamp": datetime.utcnow().isoformat()
            }

        from ...api.v1.websockets import subscribe_to_deployment_logs

        user_id = str(context.user.id) if context.user else None
        if not user_id:
            return {
                "type": "error",
                "message": "Authentication required",
                "timestamp": datetime.utcnow().isoformat()
            }

        try:
            await subscribe_to_deployment_logs(user_id, deployment_id, context.websocket)

            context.logger.info(
                f"User {user_id} subscribed to deployment logs: {deployment_id}",
                extra={
                    "user_id": user_id,
                    "deployment_id": deployment_id,
                    "action": "subscribe_deployment_logs"
                }
            )

            return {
                "type": "logs_subscribed",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {"deployment_id": deployment_id}
            }
        except Exception as e:
            context.logger.error(
                f"Error subscribing to deployment logs: {e}",
                exc_info=True
            )
            return {
                "type": "error",
                "message": f"Deployment logs subscription failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
