"""
Endpoints WebSocket pour WindFlow.

Gère les connexions WebSocket pour le streaming de logs en temps réel.
"""

from typing import Dict, Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio
import logging

from ...database import get_db
from ...models.deployment import Deployment
from ...models.user import User
from ...auth.dependencies import get_current_user_ws

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/")
async def general_websocket(
    websocket: WebSocket,
    user: Optional[User] = Depends(get_current_user_ws)
):
    """
    WebSocket endpoint général pour notifications et événements système.

    Authentification via query parameter: ?token=JWT_TOKEN

    Ce endpoint maintient une connexion WebSocket pour recevoir:
    - Notifications système
    - Événements globaux
    - Mises à jour de statut générales
    """
    # Accepter la connexion
    await websocket.accept()

    # Vérifier l'authentification
    if user is None:
        await websocket.close(code=1008, reason="Authentication required")
        return

    try:
        logger.info(f"General WebSocket connected for user {user.id}")

        # Envoyer un message de confirmation
        from datetime import datetime
        await websocket.send_json({
            "type": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "user_id": str(user.id),
                "username": user.username
            }
        })

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

        except WebSocketDisconnect:
            logger.info(f"General WebSocket disconnected for user {user.id}")

    except Exception as e:
        logger.error(f"General WebSocket error for user {user.id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass


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
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_ws)
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

    # Accepter la connexion d'abord (requis par FastAPI/Starlette)
    await websocket.accept()

    # Vérifier l'authentification après acceptation
    if user is None:
        await websocket.close(code=1008, reason="Authentication required")
        return

    try:
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
