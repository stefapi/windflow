"""
WebSocket Event Types - Shared types between backend and frontend.

These types must match the WebSocketEventType enum in frontend/src/services/websocket/types.ts
"""

from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WebSocketEventType(str, Enum):
    """
    Types d'événements WebSocket supportés.

    IMPORTANT: Ces types doivent correspondre exactement aux types définis
    dans frontend/src/services/websocket/types.ts pour que le système de plugins
    frontend fonctionne correctement.
    """

    # ============================================================================
    # Authentification
    # ============================================================================
    AUTH_LOGIN_SUCCESS = "AUTH_LOGIN_SUCCESS"
    AUTH_LOGOUT = "AUTH_LOGOUT"
    AUTH_TOKEN_REFRESH = "AUTH_TOKEN_REFRESH"

    # ============================================================================
    # Notifications
    # ============================================================================
    NOTIFICATION_SYSTEM = "NOTIFICATION_SYSTEM"
    NOTIFICATION_USER = "NOTIFICATION_USER"
    NOTIFICATION_DEPLOYMENT = "NOTIFICATION_DEPLOYMENT"

    # ============================================================================
    # Session
    # ============================================================================
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_AUTH_REQUIRED = "SESSION_AUTH_REQUIRED"
    SESSION_PERMISSION_CHANGED = "SESSION_PERMISSION_CHANGED"
    SESSION_ORGANIZATION_CHANGED = "SESSION_ORGANIZATION_CHANGED"

    # ============================================================================
    # UI Navigation (server-driven UI)
    # ============================================================================
    UI_NAVIGATION_REQUEST = "UI_NAVIGATION_REQUEST"
    UI_MODAL_DISPLAY = "UI_MODAL_DISPLAY"
    UI_TOAST_DISPLAY = "UI_TOAST_DISPLAY"
    UI_WORKFLOW_STEP = "UI_WORKFLOW_STEP"

    # ============================================================================
    # Déploiements
    # ============================================================================
    DEPLOYMENT_STATUS_CHANGED = "DEPLOYMENT_STATUS_CHANGED"
    DEPLOYMENT_LOGS_UPDATE = "DEPLOYMENT_LOGS_UPDATE"
    DEPLOYMENT_PROGRESS = "DEPLOYMENT_PROGRESS"

    # ============================================================================
    # Système
    # ============================================================================
    SYSTEM_MAINTENANCE = "SYSTEM_MAINTENANCE"
    SYSTEM_BROADCAST = "SYSTEM_BROADCAST"

    # ============================================================================
    # Types système internes (ne passent pas par le système de plugins)
    # ============================================================================
    PONG = "pong"  # Réponse au heartbeat ping
    ERROR = "error"  # Messages d'erreur
    SUBSCRIBED = "subscribed"  # Confirmation d'abonnement
    UNSUBSCRIBED = "unsubscribed"  # Confirmation de désabonnement
    LOGS_SUBSCRIBED = "logs_subscribed"  # Confirmation d'abonnement aux logs
    MESSAGE_RECEIVED = "message_received"  # Accusé de réception
    TEXT_RECEIVED = "text_received"  # Texte reçu


class WebSocketMessageEnvelope(BaseModel):
    """Enveloppe des messages WebSocket serveur → client (STORY-164.1).

    Documente le contrat de l'enveloppe diffusée par
    ``websocket/broadcasting.py`` :

    - ``type`` : type d'événement (``WebSocketEventType`` ou type interne) ;
    - ``data`` : charge utile de l'événement ;
    - ``timestamp`` : horodatage ISO (renseigné à l'émission) ;
    - ``id`` : identifiant d'acknowledgment **uniquement pour les types
      critiques** (``ws_ack_critical_types`` — défaut
      ``DEPLOYMENT_STATUS_CHANGED`` + ``NOTIFICATION_USER``). Absent par
      conception pour les streaming logs, heartbeats et toasts.

    Le client accuse réception d'un message critique via :
    ``{"type": "ack", "data": {"id": "<uuid>"}}`` (canal général) —
    registre TTL ~30 s, re-diffusion à la reconnexion du même utilisateur.
    """

    type: str
    data: Optional[dict[str, Any]] = None
    timestamp: Optional[str] = None
    id: Optional[UUID] = Field(
        default=None,
        description="Ack id (UUID) — critical event types only; the client "
        "acknowledges with {'type': 'ack', 'data': {'id': ...}}",
    )


# Types helpers pour la construction des messages
class NotificationLevel(str, Enum):
    """Niveaux de notification."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class DeploymentStatus(str, Enum):
    """Statuts de déploiement."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
