"""
WebSocket endpoint pour le streaming des logs de déploiement en temps réel.

Ce module gère la connexion WebSocket pour suivre les logs d'un déploiement
avec support du streaming en temps réel.
"""

import asyncio
import logging
from datetime import datetime

from fastapi import HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from ..database import db as database
from ..models.deployment import Deployment
from ..models.user import User
from ..services.user_organization_service import UserOrganizationService
from .connection_managers import manager
from .heartbeat import (
    HeartbeatExpiredError,
    periodic_ping,
    receive_with_expiry,
)

logger = logging.getLogger(__name__)


async def verify_deployment_access(deployment_id: str, user, db) -> Deployment:
    """Vérifie que l'utilisateur a accès au déploiement."""

    stmt = select(Deployment).where(Deployment.id == deployment_id)
    result = await db.execute(stmt)
    deployment = result.scalar_one_or_none()

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found"
        )

    # Si pas d'utilisateur authentifié, refuser l'accès
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    # Vérifier l'accès utilisateur (organisation) — STORY-121.3 :
    # appartenance via l'association (is_member, superuser bypass inclus) ;
    # corrige le bug is_superadmin (attribut inexistant) qui rendait le
    # check inopérant
    if not await UserOrganizationService.is_member(
        db, user, deployment.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this deployment",
        )

    return deployment


async def deployment_logs_websocket_endpoint(
    websocket: WebSocket, deployment_id: str, user: User
):
    """
    Stream deployment logs in real-time.

    Connect to a specific deployment's log stream for real-time monitoring.

    Authentication:
    Authentication is performed via query parameter: ?token=JWT_TOKEN and is
    enforced by the `get_current_user_ws` dependency **before** the handshake
    (refused with 1008 if the token is absent, invalid, expired or the user
    is inactive). In development mode (DISABLE_AUTH=true), the first superadmin
    is auto-logged in.

    Connection Flow:
    1. Client connects with deployment ID and token in query string
    2. Server validates token and user permissions (refuses handshake on failure)
    3. Server verifies user has access to the deployment
    4. Server sends initial deployment status
    5. Client receives real-time log updates as they occur

    Message Types Received:
    - Status: Initial deployment status
    - Log: Real-time log entries
    - Progress: Deployment progress updates
    - Complete: Deployment completion notification
    - Error: Error notifications

    Client Messages:
    - Heartbeat: Send "ping" to keep connection alive
    - Server Response: Receives {"type": "pong", "timestamp": "..."}

    Access Control:
    - User must be authenticated with valid JWT token
    - User must belong to the same organization as the deployment
    - Superadmins can access all deployments
    """
    # Accepter la connexion (l'authentification a déjà été validée par la
    # dépendance get_current_user_ws lors du handshake)
    await websocket.accept()

    # Vérifier l'accès au déploiement (RBAC organisation)
    async with database.session() as db:
        try:
            deployment = await verify_deployment_access(deployment_id, user, db)
        except HTTPException as e:
            await websocket.send_json({"type": "error", "message": e.detail})
            await websocket.close(code=1008)  # Policy Violation
            return

    try:
        # Enregistrer la connexion
        await manager.connect(websocket, deployment_id)

        # Envoyer le statut initial
        await websocket.send_json(
            {
                "type": "status",
                "timestamp": (
                    deployment.updated_at.isoformat() if deployment.updated_at else None
                ),
                "data": {
                    "status": deployment.status,
                    "deployment_id": deployment.id,
                    "name": deployment.name,
                },
            }
        )

        # STORY-164.1 : ping serveur périodique (même mécanique que le canal
        # général) + expiration des connexions muettes — tout message client
        # reçu reset le délai, fermeture serveur 1001 après
        # factor × interval sans activité.
        heartbeat_task = asyncio.create_task(
            periodic_ping(websocket, f"deployment_logs:{deployment_id}")
        )

        # Boucle de maintien de connexion
        try:
            while True:
                # Attendre un message du client (heartbeat) — borné par le
                # helper d'expiration
                data = await receive_with_expiry(
                    websocket, f"deployment_logs:{deployment_id}"
                )

                # Le client peut envoyer "ping" pour maintenir la connexion
                if data == "ping":
                    await websocket.send_json(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                    )

        except WebSocketDisconnect:
            logger.info(f"Client disconnected from deployment {deployment_id}")
        except HeartbeatExpiredError:
            logger.info(
                "Deployment logs WebSocket expired (idle) for deployment %s",
                deployment_id,
            )
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f"WebSocket error for deployment {deployment_id}: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass

    finally:
        await manager.disconnect(websocket, deployment_id)
