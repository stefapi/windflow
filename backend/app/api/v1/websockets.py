"""
Endpoints WebSocket pour WindFlow.

Gère les connexions WebSocket pour le streaming de logs en temps réel.
"""

from typing import Dict, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio
import logging
import json
from datetime import datetime

from ...database import get_db
from ...models.deployment import Deployment
from ...models.user import User
from ...auth.dependencies import get_current_user_ws

logger = logging.getLogger(__name__)

router = APIRouter()




@router.websocket("/")
async def general_websocket(
    websocket: WebSocket
):
    """
    WebSocket endpoint général pour notifications et événements système.

    Authentification via envoi de token dans le premier message JSON:
    {"type": "auth", "token": "JWT_TOKEN"}

    Ce endpoint maintient une connexion WebSocket pour recevoir:
    - Notifications système
    - Événements globaux
    - Mises à jour de statut générales
    - Logs de déploiement en temps réel
    """
    try:
        await websocket.accept()
        logger.info("WebSocket connection accepted")
    except Exception as e:
        logger.error(f"Error accepting WebSocket: {e}")
        raise

    # Variables pour l'authentification et la connexion
    user = None
    authenticated = False

    try:
        # Attendre le premier message d'authentification avec timeout
        logger.info("Waiting for authentication message...")
        try:
            data = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=30.0  # 30 secondes timeout pour le debug
            )
            logger.info(f"Received data from client: {data}")
        except asyncio.TimeoutError:
            logger.warning("WebSocket authentication timeout - no message received")
            await websocket.close(code=1008, reason="Authentication timeout")
            return

        try:
            message = json.loads(data)
        except json.JSONDecodeError:
            await websocket.close(code=1008, reason="Invalid JSON format")
            return

        # Vérifier si c'est un message d'authentification
        logger.info(f"Received first message: {message}")
        if message.get("type") != "auth" or "token" not in message:
            logger.warning(f"Invalid authentication message: {message}")
            await websocket.close(code=1008, reason="Authentication required as first message")
            return

        token = message["token"]
        logger.info(f"Authenticating with token length: {len(token)}")

        # Vérifier le token et récupérer l'utilisateur
        from ...auth.jwt import decode_access_token
        from ...services.user_service import UserService
        from ...database import db as database

        token_data = decode_access_token(token)
        logger.info(f"Token decoded: {token_data is not None}")
        if token_data is None or token_data.user_id is None:
            logger.error(f"Invalid token - could not decode token")
            await websocket.close(code=1008, reason="Invalid token - could not decode")
            return

        # Créer une session manuellement pour l'authentification
        async with database.session() as db:
            user = await UserService.get_by_id(db, token_data.user_id)
            logger.info(f"User found: {user is not None}, active: {user.is_active if user else 'N/A'}")
            if user is None or not user.is_active:
                logger.error(f"User not found or inactive: {token_data.user_id}")
                await websocket.close(code=1008, reason="User not found or inactive")
                return

        # Authentification réussie
        authenticated = True

        # Envoyer un message de confirmation d'authentification
        from datetime import datetime
        await websocket.send_json({
            "type": "auth_success",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "user_id": str(user.id),
                "username": user.username,
                "organization_id": str(user.organization_id) if user.organization_id else None
            }
        })

        logger.info(f"General WebSocket connected for user {user.id}")

        # Ajouter l'utilisateur aux connexions actives
        await add_user_connection(user.id, websocket)

        # Boucle de maintien de connexion
        try:
            while True:
                # Attendre un message du client (heartbeat)
                data = await websocket.receive_text()

                # Le client peut envoyer "ping" pour maintenir la connexion
                if data == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                else:
                    # Essayer de parser comme JSON pour d'autres types de messages
                    try:
                        message = json.loads(data)

                        # Gestion des différents types de messages
                        if message.get("type") == "subscribe":
                            # S'abonner à des événements spécifiques
                            event_type = message.get("event_type")
                            if event_type:
                                await subscribe_to_event(user.id, event_type, websocket)
                                await websocket.send_json({
                                    "type": "subscribed",
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "data": {"event_type": event_type}
                                })

                        elif message.get("type") == "unsubscribe":
                            # Se désabonner d'événements
                            event_type = message.get("event_type")
                            if event_type:
                                await unsubscribe_from_event(user.id, event_type, websocket)
                                await websocket.send_json({
                                    "type": "unsubscribed",
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "data": {"event_type": event_type}
                                })

                        elif message.get("type") == "deployment_logs":
                            # S'abonner aux logs d'un déploiement spécifique
                            deployment_id = message.get("deployment_id")
                            if deployment_id:
                                await subscribe_to_deployment_logs(user.id, deployment_id, websocket)
                                await websocket.send_json({
                                    "type": "logs_subscribed",
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "data": {"deployment_id": deployment_id}
                                })

                        else:
                            # Répondre avec un écho pour les autres messages
                            await websocket.send_json({
                                "type": "message_received",
                                "timestamp": datetime.utcnow().isoformat(),
                                "data": message
                            })

                    except json.JSONDecodeError:
                        # Message texte simple
                        await websocket.send_json({
                            "type": "text_received",
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": data
                        })

        except WebSocketDisconnect:
            logger.info(f"General WebSocket disconnected for user {user.id}")

    except Exception as e:
        logger.error(f"General WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass

    finally:
        # Nettoyer les connexions
        if user and authenticated:
            await remove_user_connection(user.id, websocket)


class ConnectionManager:
    """Gestionnaire de connexions WebSocket."""

    def __init__(self):
        # deployment_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, deployment_id: str):
        """Accepte une nouvelle connexion WebSocket."""
        await websocket.accept()

        async with self._lock:
            if deployment_id not in self.active_connections:
                self.active_connections[deployment_id] = set()
            self.active_connections[deployment_id].add(websocket)

        logger.info(f"WebSocket connected for deployment {deployment_id}")

    async def disconnect(self, websocket: WebSocket, deployment_id: str):
        """Déconnecte un WebSocket."""
        async with self._lock:
            if deployment_id in self.active_connections:
                self.active_connections[deployment_id].discard(websocket)

                # Nettoyer si plus aucune connexion
                if not self.active_connections[deployment_id]:
                    del self.active_connections[deployment_id]

        logger.info(f"WebSocket disconnected for deployment {deployment_id}")

    async def broadcast_to_deployment(self, deployment_id: str, message: dict):
        """Envoie un message à toutes les connexions d'un déploiement."""
        if deployment_id not in self.active_connections:
            return

        disconnected = set()

        for websocket in self.active_connections[deployment_id].copy():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.add(websocket)

        # Nettoyer les connexions mortes
        async with self._lock:
            for ws in disconnected:
                self.active_connections[deployment_id].discard(ws)


# Instance globale du gestionnaire
manager = ConnectionManager()


async def verify_deployment_access(
    deployment_id: str,
    user: User,
    db: AsyncSession
) -> Deployment:
    """Vérifie que l'utilisateur a accès au déploiement."""

    stmt = select(Deployment).where(Deployment.id == deployment_id)
    result = await db.execute(stmt)
    deployment = result.scalar_one_or_none()

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment not found"
        )

    # Si pas d'utilisateur authentifié, refuser l'accès
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    # Vérifier l'accès utilisateur (organisation)
    if not user.is_superadmin and deployment.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this deployment"
        )

    return deployment


@router.websocket("/deployments/{deployment_id}/logs")
async def deployment_logs_websocket(
    websocket: WebSocket,
    deployment_id: str
):
    """
    WebSocket endpoint pour streamer les logs de déploiement en temps réel.

    Authentification via query parameter: ?token=JWT_TOKEN

    Le client reçoit des messages JSON avec cette structure:
    {
        "type": "log" | "status" | "error" | "complete",
        "timestamp": "ISO8601",
        "message": "Log message",
        "level": "info" | "warning" | "error",
        "data": {...}  # Données additionnelles selon le type
    }
    """
    # Extract token from query parameters manually
    token = websocket.query_params.get('token')

    # Accepter la connexion d'abord (requis par le protocole WebSocket)
    await websocket.accept()

    # Authentifier après acceptation
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return

    # Vérifier le token et récupérer l'utilisateur
    from ...auth.jwt import decode_access_token
    from ...services.user_service import UserService
    from ...database import db as database

    token_data = decode_access_token(token)
    if token_data is None or token_data.user_id is None:
        await websocket.close(code=1008, reason="Invalid token")
        return

    # Créer une session manuellement pour l'authentification
    async with database.session() as db:
        user = await UserService.get_by_id(db, token_data.user_id)
        if user is None or not user.is_active:
            await websocket.close(code=1008, reason="User not found or inactive")
            return

        # Vérifier l'accès au déploiement
        try:
            deployment = await verify_deployment_access(deployment_id, user, db)
        except HTTPException as e:
            await websocket.send_json({
                "type": "error",
                "message": e.detail
            })
            await websocket.close(code=1008)  # Policy Violation
            return

    try:
        # Enregistrer la connexion
        await manager.connect(websocket, deployment_id)

        # Envoyer le statut initial
        await websocket.send_json({
            "type": "status",
            "timestamp": deployment.updated_at.isoformat() if deployment.updated_at else None,
            "data": {
                "status": deployment.status,
                "deployment_id": deployment.id,
                "name": deployment.name
            }
        })

        # Boucle de maintien de connexion
        try:
            while True:
                # Attendre un message du client (heartbeat)
                data = await websocket.receive_text()

                # Le client peut envoyer "ping" pour maintenir la connexion
                if data == "ping":
                    from datetime import datetime
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })

        except WebSocketDisconnect:
            logger.info(f"Client disconnected from deployment {deployment_id}")

    except Exception as e:
        logger.error(f"WebSocket error for deployment {deployment_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass

    finally:
        await manager.disconnect(websocket, deployment_id)


async def broadcast_deployment_log(
    deployment_id: str,
    message: str,
    level: str = "info",
    **extra_data
):
    """
    Fonction helper pour broadcaster un log à tous les clients connectés.

    À appeler depuis les tasks Celery ou autres services.
    """
    from datetime import datetime

    await manager.broadcast_to_deployment(deployment_id, {
        "type": "log",
        "timestamp": datetime.utcnow().isoformat(),
        "message": message,
        "level": level,
        **extra_data
    })


async def broadcast_deployment_status(
    deployment_id: str,
    status: str,
    **extra_data
):
    """
    Fonction helper pour broadcaster un changement de statut.
    """
    from datetime import datetime

    await manager.broadcast_to_deployment(deployment_id, {
        "type": "status",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "status": status,
            **extra_data
        }
    })


async def broadcast_deployment_complete(
    deployment_id: str,
    success: bool = True,
    **extra_data
):
    """
    Fonction helper pour broadcaster la fin d'un déploiement.
    """
    from datetime import datetime

    await manager.broadcast_to_deployment(deployment_id, {
        "type": "complete",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "success": success,
            **extra_data
        }
    })


# Gestionnaire de connexions utilisateur pour l'endpoint général
class UserConnectionManager:
    """Gestionnaire de connexions WebSocket par utilisateur."""

    def __init__(self):
        # user_id -> set of WebSocket connections
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        # user_id -> set of subscribed event types
        self.user_subscriptions: Dict[str, Set[str]] = {}
        # deployment_id -> set of user_ids subscribed to deployment logs
        self.deployment_subscribers: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def add_connection(self, user_id: str, websocket: WebSocket):
        """Ajoute une connexion utilisateur."""
        async with self._lock:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(websocket)

    async def remove_connection(self, user_id: str, websocket: WebSocket):
        """Supprime une connexion utilisateur."""
        async with self._lock:
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(websocket)

                # Nettoyer si plus aucune connexion
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
                    # Nettoyer aussi les abonnements
                    if user_id in self.user_subscriptions:
                        del self.user_subscriptions[user_id]

    async def subscribe_to_event(self, user_id: str, event_type: str, websocket: WebSocket):
        """Abonne un utilisateur à un type d'événement."""
        async with self._lock:
            if user_id not in self.user_subscriptions:
                self.user_subscriptions[user_id] = set()
            self.user_subscriptions[user_id].add(event_type)

    async def unsubscribe_from_event(self, user_id: str, event_type: str, websocket: WebSocket):
        """Désabonne un utilisateur d'un type d'événement."""
        async with self._lock:
            if user_id in self.user_subscriptions:
                self.user_subscriptions[user_id].discard(event_type)

                # Nettoyer si plus d'abonnements
                if not self.user_subscriptions[user_id]:
                    del self.user_subscriptions[user_id]

    async def subscribe_to_deployment_logs(self, user_id: str, deployment_id: str, websocket: WebSocket):
        """Abonne un utilisateur aux logs d'un déploiement."""
        async with self._lock:
            if deployment_id not in self.deployment_subscribers:
                self.deployment_subscribers[deployment_id] = set()
            self.deployment_subscribers[deployment_id].add(user_id)

    async def broadcast_to_user(self, user_id: str, message: dict):
        """Envoie un message à toutes les connexions d'un utilisateur."""
        if user_id not in self.user_connections:
            return

        disconnected = set()

        for websocket in self.user_connections[user_id].copy():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to user WebSocket: {e}")
                disconnected.add(websocket)

        # Nettoyer les connexions mortes
        async with self._lock:
            for ws in disconnected:
                await self.remove_connection(user_id, ws)

    async def broadcast_to_event_subscribers(self, event_type: str, message: dict):
        """Envoie un message à tous les utilisateurs abonnés à un événement."""
        disconnected_users = set()

        async with self._lock:
            for user_id, subscriptions in self.user_subscriptions.items():
                if event_type in subscriptions:
                    if user_id in self.user_connections:
                        for websocket in self.user_connections[user_id].copy():
                            try:
                                await websocket.send_json(message)
                            except Exception as e:
                                logger.error(f"Error sending to subscriber WebSocket: {e}")
                                disconnected_users.add((user_id, websocket))

        # Nettoyer les connexions mortes
        for user_id, ws in disconnected_users:
            await self.remove_connection(user_id, ws)

    async def broadcast_deployment_log_to_subscribers(self, deployment_id: str, message: dict):
        """Envoie un log de déploiement à tous les abonnés."""
        if deployment_id not in self.deployment_subscribers:
            return

        disconnected_users = set()

        async with self._lock:
            for user_id in self.deployment_subscribers[deployment_id]:
                if user_id in self.user_connections:
                    for websocket in self.user_connections[user_id].copy():
                        try:
                            await websocket.send_json(message)
                        except Exception as e:
                            logger.error(f"Error sending deployment log to subscriber: {e}")
                            disconnected_users.add((user_id, websocket))

        # Nettoyer les connexions mortes
        for user_id, ws in disconnected_users:
            await self.remove_connection(user_id, ws)


# Instance globale du gestionnaire de connexions utilisateur
user_manager = UserConnectionManager()


# Fonctions helper pour la gestion des connexions utilisateur
async def add_user_connection(user_id: str, websocket: WebSocket):
    """Ajoute une connexion utilisateur."""
    await user_manager.add_connection(user_id, websocket)


async def remove_user_connection(user_id: str, websocket: WebSocket):
    """Supprime une connexion utilisateur."""
    await user_manager.remove_connection(user_id, websocket)


async def subscribe_to_event(user_id: str, event_type: str, websocket: WebSocket):
    """Abonne un utilisateur à un événement."""
    await user_manager.subscribe_to_event(user_id, event_type, websocket)


async def unsubscribe_from_event(user_id: str, event_type: str, websocket: WebSocket):
    """Désabonne un utilisateur d'un événement."""
    await user_manager.unsubscribe_from_event(user_id, event_type, websocket)


async def subscribe_to_deployment_logs(user_id: str, deployment_id: str, websocket: WebSocket):
    """Abonne un utilisateur aux logs d'un déploiement."""
    await user_manager.subscribe_to_deployment_logs(user_id, deployment_id, websocket)


# Fonctions helper pour le broadcast
async def broadcast_to_user(user_id: str, message: dict):
    """Envoie un message à un utilisateur spécifique."""
    await user_manager.broadcast_to_user(user_id, message)


async def broadcast_to_event_subscribers(event_type: str, message: dict):
    """Envoie un message à tous les abonnés d'un événement."""
    await user_manager.broadcast_to_event_subscribers(event_type, message)


async def broadcast_deployment_log_to_subscribers(deployment_id: str, message: dict):
    """Envoie un log de déploiement à tous les abonnés."""
    await user_manager.broadcast_deployment_log_to_subscribers(deployment_id, message)
