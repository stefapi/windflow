"""
Fonctions utilitaires de broadcast WebSocket.

Ce module contient toutes les fonctions helper pour broadcaster
des messages aux clients WebSocket, extraites de api/v1/websockets.py
pour une meilleure organisation et réutilisabilité.

Fonctions de broadcast déploiement:
    - broadcast_deployment_log: Broadcaster les logs de déploiement
    - broadcast_deployment_status: Broadcaster les changements de statut
    - broadcast_deployment_progress: Broadcaster la progression
    - broadcast_deployment_complete: Broadcaster la complétion

Fonctions de broadcast utilisateur:
    - broadcast_to_user: Broadcaster à un utilisateur spécifique
    - broadcast_to_event_subscribers: Broadcaster aux abonnés d'un événement
    - broadcast_deployment_log_to_subscribers: Broadcaster logs aux abonnés

Fonctions de gestion des abonnements:
    - add_user_connection: Ajouter une connexion utilisateur
    - remove_user_connection: Retirer une connexion utilisateur
    - subscribe_to_event: S'abonner à un type d'événement
    - unsubscribe_from_event: Se désabonner d'un événement
    - subscribe_to_deployment_logs: S'abonner aux logs d'un déploiement
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import WebSocket

from ..schemas.websocket_events import WebSocketEventType
from .ack_registry import AckRegistry, ack_registry
from .connection_managers import manager, user_manager
from .plugin import PluginContext

# ============================================================================
# FONCTIONS DE BROADCAST - DÉPLOIEMENTS
# ============================================================================


async def _attach_ack_id_if_critical(
    event_type: object, message: dict, user_id: Optional[str] = None
) -> None:
    """
    Attache un ``id`` UUID d'acknowledgment aux messages critiques (STORY-164.1).

    Décision 5 : seuls les types configurés dans ``ws_ack_critical_types``
    (défaut ``DEPLOYMENT_STATUS_CHANGED`` + ``NOTIFICATION_USER``) portent un
    ``id`` et sont adressés au registre d'ack — les streaming logs, les
    heartbeats et les toasts sont exclus par conception. Si le message porte
    déjà un ``id`` (re-diffusion après reconnexion), rien n'est régénéré ni
    réenregistré.

    Args:
        event_type: Type d'événement WebSocket (enum ou str).
        message: Enveloppe du message (mutée sur place : ``id`` ajouté).
        user_id: Destinataire si identifié — condition pour l'enregistrement
            au registre (re-diffusion à la reconnexion du même utilisateur).
    """
    if not AckRegistry.is_critical_type(event_type):
        return
    if message.get("id"):
        return  # id déjà porté (re-diffusion) — pas de double entrée
    message_id = str(uuid.uuid4())
    message["id"] = message_id
    if user_id:
        await ack_registry.register(
            message_id=message_id,
            user_id=user_id,
            event_type=str(event_type),
            payload=message.get("data") or {},
        )


async def _broadcast_deployment_event(
    deployment_id: str, event_type: WebSocketEventType, event_data: dict
) -> None:
    """
    Fonction générique pour broadcaster un événement de déploiement.

    Gère automatiquement:
    - Ajout du timestamp si absent
    - Création du message WebSocket
    - Id d'acknowledgment sur les types critiques + registre (STORY-164.1,
      destinataire identifié via ``event_data["user_id"]``)
    - Broadcast aux connexions directes
    - Dispatch aux plugins

    Args:
        deployment_id: ID du déploiement
        event_type: Type d'événement WebSocket
        event_data: Données de l'événement
    """
    if "timestamp" not in event_data:
        event_data["timestamp"] = datetime.utcnow().isoformat()

    websocket_message = {"type": event_type, "data": event_data}

    # STORY-164.1 : id UUID + registre d'ack pour les types critiques —
    # le destinataire identifiable est l'initiateur (``user_id``) lorsqu'il
    # est fourni dans le payload.
    await _attach_ack_id_if_critical(
        event_type, websocket_message, user_id=event_data.get("user_id")
    )

    await manager.broadcast_to_deployment(deployment_id, websocket_message)
    await user_manager.dispatch_to_plugins(event_type, event_data)


async def broadcast_deployment_log(
    deployment_id: str, message: str, level: str = "info", **extra_data
):
    """
    Broadcast deployment logs to all connected WebSocket clients.

    Args:
        deployment_id: ID of the deployment
        message: Log message to broadcast
        level: Log level (info, warning, error)
        **extra_data: Additional data to include in the event
    """
    await _broadcast_deployment_event(
        deployment_id,
        WebSocketEventType.DEPLOYMENT_LOGS_UPDATE,
        {
            "deploymentId": deployment_id,
            "logs": [message],
            "level": level,
            **extra_data,
        },
    )


async def broadcast_deployment_status(
    deployment_id: str,
    new_status: str,
    deployment_name: str = "",
    old_status: str = "",
    **extra_data,
):
    """
    Broadcast deployment status changes to all connected WebSocket clients.

    Args:
        deployment_id: ID of the deployment
        new_status: New deployment status
        deployment_name: Name of the deployment (optional)
        old_status: Previous deployment status (optional)
        **extra_data: Additional data to include in the event
    """
    await _broadcast_deployment_event(
        deployment_id,
        WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
        {
            "deploymentId": deployment_id,
            "deploymentName": deployment_name,
            "oldStatus": old_status,
            "newStatus": new_status,
            **extra_data,
        },
    )


async def broadcast_deployment_progress(
    deployment_id: str,
    progress: int,
    step: str,
    total_steps: Optional[int] = None,
    **extra_data,
):
    """
    Broadcast deployment progress updates to all connected WebSocket clients.

    This function is used by the plugin system to send real-time progress updates
    during deployment execution.

    STORY-163 (T4) : le payload est aligné sur le contrat frontend existant
    (``frontend/src/types/websocket.ts`` — ``deployment_id``, ``progress``,
    ``current_step``, ``total_steps``, consommé par ``handleProgress`` de
    ``useDeploymentWebSocket.ts``) — snake_case, sans période de
    compatibilité (aucun consommateur backend du camelCase : vérifié).
    ``step`` est conservé en plus de ``current_step`` pour les logs
    internes (``deployment_monitor`` lit ``current_step`` avec fallback
    ``step``).

    Args:
        deployment_id: ID of the deployment
        progress: Progress percentage (0-100)
        step: Current deployment step description
        total_steps: Total number of pipeline steps (optional)
        **extra_data: Additional data to include in the event

    Note:
        Called by WebSocket plugins (see backend/app/websocket/plugins/)
    """
    await _broadcast_deployment_event(
        deployment_id,
        WebSocketEventType.DEPLOYMENT_PROGRESS,
        {
            "deployment_id": deployment_id,
            "progress": progress,
            "current_step": step,
            "step": step,  # compat logs internes (deployment_monitor)
            "total_steps": total_steps,
            **extra_data,
        },
    )


async def broadcast_deployment_complete(
    deployment_id: str, success: bool = True, deployment_name: str = "", **extra_data
):
    """
    Broadcast deployment completion to all connected WebSocket clients.

    This is a convenience function that broadcasts a status change event
    indicating deployment completion (success or failure).

    Args:
        deployment_id: ID of the deployment
        success: True if deployment succeeded, False if failed
        deployment_name: Name of the deployment (optional)
        **extra_data: Additional data to include in the event

    Note:
        Called by WebSocket plugins (see backend/app/websocket/plugins/)
        Internally calls broadcast_deployment_status with final status
    """
    final_status = "success" if success else "failed"

    await broadcast_deployment_status(
        deployment_id=deployment_id,
        new_status=final_status,
        deployment_name=deployment_name,
        old_status="running",
        **extra_data,
    )


# ============================================================================
# FONCTIONS DE BROADCAST - UTILISATEURS
# ============================================================================


async def broadcast_to_user(user_id: str, message: dict):
    """
    Envoie un message à un utilisateur spécifique.

    Broadcaste le message à toutes les connexions WebSocket actives
    de l'utilisateur spécifié.

    Args:
        user_id: ID de l'utilisateur
        message: Message JSON à envoyer

    Example:
        >>> await broadcast_to_user("user-123", {
        ...     "type": "notification",
        ...     "data": {"message": "Hello!"}
        ... })
    """
    # STORY-164.1 : les messages critiques adressés à un utilisateur portent
    # un id d'ack (généré si absent) et sont enregistrés au registre pour
    # re-diffusion à la reconnexion de ce même utilisateur.
    await _attach_ack_id_if_critical(message.get("type"), message, user_id=user_id)
    await user_manager.broadcast_to_user(user_id, message)


async def broadcast_to_event_subscribers(event_type: str, message: dict):
    """
    Envoie un message à tous les abonnés d'un événement.

    Broadcaste le message à tous les utilisateurs qui se sont abonnés
    au type d'événement spécifié via le plugin de subscription.

    Args:
        event_type: Type d'événement (WebSocketEventType)
        message: Message JSON à envoyer

    Example:
        >>> await broadcast_to_event_subscribers(
        ...     WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
        ...     {"type": "status_change", "data": {...}}
        ... )
    """
    import logging

    logger = logging.getLogger(__name__)

    logger.debug(f"📢 Broadcasting to event subscribers: {event_type}")
    logger.debug(f"Message: {message}")

    await user_manager.broadcast_to_event_subscribers(event_type, message)

    logger.debug("✅ Broadcast to event subscribers completed")


async def broadcast_deployment_log_to_subscribers(deployment_id: str, message: dict):
    """
    Envoie un log de déploiement à tous les abonnés.

    Broadcaste les logs de déploiement à tous les utilisateurs qui se sont
    abonnés aux logs de ce déploiement spécifique.

    Args:
        deployment_id: ID du déploiement
        message: Message JSON contenant les logs à envoyer

    Example:
        >>> await broadcast_deployment_log_to_subscribers("dep-456", {
        ...     "type": "deployment_log",
        ...     "data": {"logs": ["Starting deployment..."]}
        ... })
    """
    await user_manager.broadcast_deployment_log_to_subscribers(deployment_id, message)


# ============================================================================
# FONCTIONS DE GESTION DES CONNEXIONS
# ============================================================================


async def add_user_connection(
    user_id: str, websocket: WebSocket, context: Optional[PluginContext] = None
):
    """
    Ajoute une connexion utilisateur.

    Enregistre une nouvelle connexion WebSocket pour l'utilisateur spécifié.
    Optionnellement, stocke le contexte du plugin pour les dispatching d'événements.

    Args:
        user_id: ID de l'utilisateur
        websocket: Instance de connexion WebSocket
        context: Contexte du plugin (optionnel)

    Note:
        Appelé automatiquement lors de la connexion WebSocket dans l'endpoint général.
    """
    await user_manager.add_connection(user_id, websocket, context)


async def remove_user_connection(user_id: str, websocket: WebSocket):
    """
    Supprime une connexion utilisateur.

    Retire une connexion WebSocket existante pour l'utilisateur spécifié.
    Nettoie automatiquement les abonnements si c'était la dernière connexion.

    Args:
        user_id: ID de l'utilisateur
        websocket: Instance de connexion WebSocket

    Note:
        Appelé automatiquement lors de la déconnexion WebSocket.
    """
    await user_manager.remove_connection(user_id, websocket)


# ============================================================================
# FONCTIONS DE GESTION DES ABONNEMENTS
# ============================================================================


async def subscribe_to_event(user_id: str, event_type: str, websocket: WebSocket):
    """
    Abonne un utilisateur à un événement.

    Enregistre l'utilisateur comme abonné au type d'événement spécifié.
    L'utilisateur recevra tous les messages broadcasters pour ce type d'événement.

    Args:
        user_id: ID de l'utilisateur
        event_type: Type d'événement (WebSocketEventType)
        websocket: Instance de connexion WebSocket

    Example:
        >>> await subscribe_to_event(
        ...     "user-123",
        ...     WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
        ...     websocket
        ... )

    Note:
        Utilisé par le plugin SubscriptionHandler pour gérer les messages "subscribe" du client.
    """
    await user_manager.subscribe_to_event(user_id, event_type, websocket)


async def unsubscribe_from_event(user_id: str, event_type: str, websocket: WebSocket):
    """
    Désabonne un utilisateur d'un événement.

    Retire l'utilisateur de la liste des abonnés au type d'événement spécifié.
    L'utilisateur ne recevra plus les messages broadcasters pour ce type d'événement.

    Args:
        user_id: ID de l'utilisateur
        event_type: Type d'événement (WebSocketEventType)
        websocket: Instance de connexion WebSocket

    Example:
        >>> await unsubscribe_from_event(
        ...     "user-123",
        ...     WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
        ...     websocket
        ... )

    Note:
        Utilisé par le plugin SubscriptionHandler pour gérer les messages "unsubscribe" du client.
    """
    await user_manager.unsubscribe_from_event(user_id, event_type, websocket)


async def subscribe_to_deployment_logs(
    user_id: str, deployment_id: str, websocket: WebSocket
):
    """
    Abonne un utilisateur aux logs d'un déploiement.

    Enregistre l'utilisateur comme abonné aux logs du déploiement spécifique.
    L'utilisateur recevra tous les logs en temps réel pour ce déploiement.

    Args:
        user_id: ID de l'utilisateur
        deployment_id: ID du déploiement
        websocket: Instance de connexion WebSocket

    Example:
        >>> await subscribe_to_deployment_logs(
        ...     "user-123",
        ...     "dep-456",
        ...     websocket
        ... )

    Note:
        Utilisé par le plugin SubscriptionHandler pour gérer les messages
        "subscribe_deployment_logs" du client.
    """
    await user_manager.subscribe_to_deployment_logs(user_id, deployment_id, websocket)
