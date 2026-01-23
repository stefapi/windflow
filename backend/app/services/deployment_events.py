"""
Deployment Events Service.

Service for emitting deployment-related events that will be
broadcast to WebSocket clients via the plugin system.

Note: Logs and progress updates are handled directly via WebSocket
plugins (see backend/app/websocket/plugins/) for real-time streaming.
This service focuses on deployment lifecycle events (status changes).
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from ..core.events import EventBus, EventType
from ..schemas.deployment import DeploymentStatus


logger = logging.getLogger(__name__)


class DeploymentEventsService:
    """
    Service pour émettre des événements de déploiement.

    Ce service utilise le système d'événements centralisé pour émettre
    des événements qui seront capturés par les plugins WebSocket et
    diffusés aux clients connectés.
    """

    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        Initialize the deployment events service.

        Args:
            event_bus: Event bus instance (will use global instance if None)
        """
        from ..core.events import event_bus as global_event_bus
        self.event_bus = event_bus or global_event_bus

    async def emit_status_change(
        self,
        deployment_id: UUID,
        new_status: DeploymentStatus,
        old_status: Optional[DeploymentStatus] = None,
        user_id: Optional[UUID] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Emit a deployment status change event.

        Args:
            deployment_id: ID of the deployment
            new_status: New deployment status
            old_status: Previous deployment status (optional)
            user_id: ID of the user who initiated the deployment
            additional_data: Additional data to include in the event
        """
        event_data = {
            "deployment_id": str(deployment_id),
            "new_status": new_status.value if isinstance(new_status, DeploymentStatus) else new_status,
            "old_status": old_status.value if isinstance(old_status, DeploymentStatus) else old_status if old_status else None,
            "user_id": str(user_id) if user_id else None,
        }

        if additional_data:
            event_data.update(additional_data)

        # Map DeploymentStatus to EventType
        status_str = new_status.value if isinstance(new_status, DeploymentStatus) else new_status
        event_type_map = {
            "pending": EventType.DEPLOYMENT_CREATED,
            "deploying": EventType.DEPLOYMENT_STARTED,
            "running": EventType.DEPLOYMENT_STARTED,  # Un déploiement "running" est démarré, pas terminé
            "success": EventType.DEPLOYMENT_COMPLETED,
            "failed": EventType.DEPLOYMENT_FAILED,
            "rollback": EventType.DEPLOYMENT_ROLLED_BACK,
        }

        event_type = event_type_map.get(status_str, EventType.DEPLOYMENT_COMPLETED)

        logger.info(
            f"📡 [STEP 1/4] Emitting status change event: {deployment_id} → {new_status} (EventType: {event_type})"
        )
        logger.debug(
            f"Event data: {event_data}"
        )

        await self.event_bus.emit(
            event_type,
            event_data
        )

        logger.info(
            f"✅ [STEP 1/4] Event emitted to EventBus successfully"
        )

    async def emit_logs_update(
        self,
        deployment_id: UUID,
        logs: str,
        user_id: Optional[UUID] = None,
        append: bool = True
    ) -> None:
        """
        Broadcast deployment logs update directly via WebSocket.

        Note: Logs are broadcasted directly via WebSocket rather than through
        the event bus, as they are real-time streaming data.

        Args:
            deployment_id: ID of the deployment
            logs: Log message(s) to send
            user_id: ID of the user (optional)
            append: Whether to append logs or replace (default: True)
        """
        try:
            # Import here to avoid circular dependency
            from ..websocket import broadcast_deployment_log

            logger.debug(
                f"📡 Broadcasting logs update via WebSocket: {deployment_id} (append={append})"
            )

            # Broadcast directement via WebSocket
            await broadcast_deployment_log(
                deployment_id=str(deployment_id),
                message=logs,
                level="info"
            )

        except Exception as e:
            logger.error(f"Failed to broadcast logs update: {e}", exc_info=True)


# Singleton instance with lazy initialization to avoid circular imports
_deployment_events_instance: Optional[DeploymentEventsService] = None


def get_deployment_events() -> DeploymentEventsService:
    """
    Get or create the deployment events service singleton.

    Returns:
        DeploymentEventsService: Singleton instance
    """
    global _deployment_events_instance
    if _deployment_events_instance is None:
        _deployment_events_instance = DeploymentEventsService()
    return _deployment_events_instance


# Alias for backward compatibility and easy import
deployment_events = get_deployment_events()
