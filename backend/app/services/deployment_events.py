"""
Deployment Events Service.

Service for emitting deployment-related events that will be
broadcast to WebSocket clients via the plugin system.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID

from ..core.events import EventBus
from ..schemas.websocket_events import WebSocketEventType
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
            "status": new_status.value if isinstance(new_status, DeploymentStatus) else new_status,
            "old_status": old_status.value if isinstance(old_status, DeploymentStatus) else old_status if old_status else None,
            "user_id": str(user_id) if user_id else None,
        }

        if additional_data:
            event_data.update(additional_data)

        logger.info(
            f"📡 Emitting status change event: {deployment_id} → {new_status}"
        )

        await self.event_bus.emit(
            WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
            event_data
        )

    async def emit_logs_update(
        self,
        deployment_id: UUID,
        logs: str,
        user_id: Optional[UUID] = None,
        append: bool = True
    ) -> None:
        """
        Emit a deployment logs update event.

        Args:
            deployment_id: ID of the deployment
            logs: New log content
            user_id: ID of the user who initiated the deployment
            append: If True, append to existing logs; if False, replace
        """
        event_data = {
            "deployment_id": str(deployment_id),
            "logs": logs,
            "user_id": str(user_id) if user_id else None,
            "append": append
        }

        logger.debug(
            f"📝 Emitting logs update event: {deployment_id} ({len(logs)} chars)"
        )

        await self.event_bus.emit(
            WebSocketEventType.DEPLOYMENT_LOGS_UPDATE,
            event_data
        )

    async def emit_progress_update(
        self,
        deployment_id: UUID,
        progress: int,
        current_step: str,
        total_steps: int = 100,
        user_id: Optional[UUID] = None
    ) -> None:
        """
        Emit a deployment progress update event.

        Args:
            deployment_id: ID of the deployment
            progress: Progress percentage (0-100)
            current_step: Description of current step
            total_steps: Total number of steps
            user_id: ID of the user who initiated the deployment
        """
        event_data = {
            "deployment_id": str(deployment_id),
            "progress": progress,
            "current_step": current_step,
            "total_steps": total_steps,
            "user_id": str(user_id) if user_id else None
        }

        logger.debug(
            f"⏳ Emitting progress event: {deployment_id} - {progress}% - {current_step}"
        )

        await self.event_bus.emit(
            WebSocketEventType.DEPLOYMENT_PROGRESS,
            event_data
        )


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
