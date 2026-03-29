"""
Audit Logger Plugin - Logs security-related WebSocket events.

Handles authentication and session events for audit purposes.
"""

from datetime import datetime
from typing import Any, Dict

from ...schemas.websocket_events import WebSocketEventType
from ..plugin import PluginContext, WebSocketPlugin


class AuditLoggerPlugin(WebSocketPlugin):
    """
    Plugin for auditing security-related WebSocket events.

    Logs authentication events, session changes, and other
    security-sensitive operations for compliance and debugging.
    """

    name = "audit_logger"
    version = "1.0.0"
    description = "Logs security-related WebSocket events for audit trail"

    listens_for = [
        WebSocketEventType.AUTH_LOGIN_SUCCESS,
        WebSocketEventType.AUTH_LOGOUT,
        WebSocketEventType.AUTH_TOKEN_REFRESH,
        WebSocketEventType.SESSION_EXPIRED,
        WebSocketEventType.SESSION_AUTH_REQUIRED,
        WebSocketEventType.SESSION_PERMISSION_CHANGED,
        WebSocketEventType.SESSION_ORGANIZATION_CHANGED,
    ]

    async def handle_event(
        self, event: WebSocketEventType, data: Dict[str, Any], context: PluginContext
    ) -> None:
        """
        Handle security-related events by logging them.

        Args:
            event: The event type being handled
            data: Event data payload
            context: Plugin context
        """
        # Extract user info
        user_id = context.user.id if context.user else "anonymous"
        username = context.user.username if context.user else "anonymous"

        # Log based on event type
        if event == WebSocketEventType.AUTH_LOGIN_SUCCESS:
            context.logger.info(
                "🔐 WebSocket authentication successful",
                extra={
                    "event": event.value,
                    "user_id": str(user_id),
                    "username": username,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": data,
                },
            )

        elif event == WebSocketEventType.AUTH_LOGOUT:
            context.logger.info(
                "🔓 WebSocket logout",
                extra={
                    "event": event.value,
                    "user_id": str(user_id),
                    "username": username,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        elif event == WebSocketEventType.AUTH_TOKEN_REFRESH:
            context.logger.info(
                "🔄 WebSocket token refreshed",
                extra={
                    "event": event.value,
                    "user_id": str(user_id),
                    "username": username,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        elif event == WebSocketEventType.SESSION_EXPIRED:
            context.logger.warning(
                "⚠️ WebSocket session expired",
                extra={
                    "event": event.value,
                    "user_id": str(user_id),
                    "username": username,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        elif event == WebSocketEventType.SESSION_AUTH_REQUIRED:
            context.logger.warning(
                "⚠️ WebSocket authentication required",
                extra={
                    "event": event.value,
                    "user_id": str(user_id),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        elif event == WebSocketEventType.SESSION_PERMISSION_CHANGED:
            context.logger.info(
                "🔑 WebSocket user permissions changed",
                extra={
                    "event": event.value,
                    "user_id": str(user_id),
                    "username": username,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": data,
                },
            )

        elif event == WebSocketEventType.SESSION_ORGANIZATION_CHANGED:
            context.logger.info(
                "🏢 WebSocket user organization changed",
                extra={
                    "event": event.value,
                    "user_id": str(user_id),
                    "username": username,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": data,
                },
            )

        # TODO: Potential future enhancements:
        # - Persist audit logs to database for long-term storage
        # - Send critical events to SIEM system
        # - Trigger alerts for suspicious patterns
