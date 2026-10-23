"""
Deployment Events Service.

Service for emitting deployment-related events that will be
broadcast to WebSocket clients via the plugin system.

Note: Logs and progress updates are handled directly via WebSocket
plugins (see backend/app/websocket/plugins/) for real-time streaming.
This service focuses on deployment lifecycle events (status changes).
"""

import logging
from typing import Any, Dict, Optional
from uuid import UUID

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
        additional_data: Optional[Dict[str, Any]] = None,
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
            "new_status": (
                new_status.value
                if isinstance(new_status, DeploymentStatus)
                else new_status
            ),
            "old_status": (
                old_status.value
                if isinstance(old_status, DeploymentStatus)
                else old_status if old_status else None
            ),
            "user_id": str(user_id) if user_id else None,
        }

        if additional_data:
            event_data.update(additional_data)

        # Map DeploymentStatus → EventType canonique (spec 11 — STORY-162).
        # Divergence documentée vs analyse : l'enum n'a pas de statut
        # ``success`` — le statut métier de succès est ``running`` (le
        # déploiement est actif/déployé ; l'audit ``deployment.succeeded``
        # est déjà émis sur la transition vers RUNNING par
        # ``deployment_service.update_status``). Le bus s'aligne :
        # ``running`` → ``deployment.succeeded`` (JAMAIS
        # ``deployment.completed``). Statut sans événement canonique
        # (``stopped``, inconnu) → pas d'émission + warning.
        status_str = (
            new_status.value if isinstance(new_status, DeploymentStatus) else new_status
        )
        event_type_map: Dict[str, EventType] = {
            "pending": EventType.DEPLOYMENT_CREATED,
            "deploying": EventType.DEPLOYMENT_STARTED,
            "running": EventType.DEPLOYMENT_SUCCEEDED,
            "failed": EventType.DEPLOYMENT_FAILED,
            "rolling_back": EventType.DEPLOYMENT_ROLLED_BACK,
        }

        event_type = event_type_map.get(status_str)
        if event_type is None:
            # Statut sans événement canonique (stopped, inconnu) →
            # warning explicite, aucune émission (plus de fallback
            # silencieux vers un événement trompeur).
            logger.warning(
                "Deployment status %r has no canonical event — nothing emitted",
                status_str,
            )
            return

        logger.info(
            f"📡 [STEP 1/4] Emitting status change event: {deployment_id} → {new_status} (EventType: {event_type})"
        )
        logger.debug(f"Event data: {event_data}")

        await self.event_bus.emit(event_type, event_data)

        logger.info("✅ [STEP 1/4] Event emitted to EventBus successfully")

    async def emit_logs_update(
        self,
        deployment_id: UUID,
        logs: str,
        user_id: Optional[UUID] = None,
        append: bool = True,
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
                deployment_id=str(deployment_id), message=logs, level="info"
            )

        except Exception as e:
            logger.error(f"Failed to broadcast logs update: {e}", exc_info=True)

    async def emit_progress_update(
        self,
        deployment_id: UUID,
        progress: int,
        step: str,
        total_steps: int,
        user_id: Optional[UUID] = None,
    ) -> None:
        """Broadcast une mise à jour de progression directement via WebSocket.

        STORY-163 (T4/AC 3) : ``DEPLOYMENT_PROGRESS`` est un type de
        **transport WebSocket** — jamais émis sur le bus canonique
        (avertissement WEBSOCKET-REAL-TIME §4.2 : couche transport vs
        couche canonique), sur le modèle de ``emit_logs_update``.

        Payload **snake_case** aligné sur le contrat frontend existant
        ([``frontend/src/types/websocket.ts`` l.33-38] consommé par
        ``handleProgress`` de ``useDeploymentWebSocket.ts``) :
        ``deployment_id``, ``progress``, ``current_step``,
        ``total_steps``, ``timestamp``.

        Sécurité (rules 40) : payload limité à ID/étapes/progression —
        jamais de variables de déploiement ni de secrets ; l'émission est
        best-effort (échec de broadcast loggué, jamais propagé — le
        pipeline de déploiement ne doit pas échouer pour une notification).

        Args:
            deployment_id: ID du déploiement.
            progress: Progression (0-100, monotone au fil du pipeline).
            step: Libellé explicite de l'étape courante (ex. ``deploying``).
            total_steps: Nombre total d'étapes du chemin de déploiement.
            user_id: ID de l'utilisateur initiateur (transmis pour
                routage des notifications, non exposé dans le message).
        """
        try:
            # Import ici pour éviter la dépendance circulaire (pattern
            # emit_logs_update).
            from ..websocket.broadcasting import broadcast_deployment_progress

            logger.debug(
                "📡 Broadcasting progress via WebSocket: %s (%s%% — %s)",
                deployment_id,
                progress,
                step,
            )

            await broadcast_deployment_progress(
                deployment_id=str(deployment_id),
                progress=progress,
                step=step,
                total_steps=total_steps,
                user_id=str(user_id) if user_id else None,
            )

        except Exception as e:
            # Best-effort : jamais de remontée au pipeline de déploiement.
            logger.error(f"Failed to broadcast progress update: {e}", exc_info=True)


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
