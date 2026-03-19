"""
WebSocket endpoint pour le streaming des logs de déploiement en temps réel.

Ce module gère la connexion WebSocket pour suivre les logs d'un déploiement
avec support du streaming en temps réel.
"""

import logging
from datetime import datetime

from fastapi import HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from ..auth.jwt import decode_access_token
from ..database import db as database
from ..models.deployment import Deployment
from ..services.user_service import UserService
from .connection_managers import manager

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

    # Vérifier l'accès utilisateur (organisation)
    if not user.is_superadmin and deployment.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this deployment",
        )

    return deployment


async def deployment_logs_websocket_endpoint(websocket: WebSocket, deployment_id: str):
    """
    Stream deployment logs in real-time.

    Connect to a specific deployment's log stream for real-time monitoring.

    Authentication:
    Authentication is performed via query parameter: ?token=JWT_TOKEN

    Connection Flow:
    1. Client connects with deployment ID and token in query string
    2. Server validates token and user permissions
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
    # Extract token from query parameters manually
    token = websocket.query_params.get("token")

    # Accepter la connexion d'abord (requis par le protocole WebSocket)
    await websocket.accept()

    # Authentifier après acceptation
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return

    # Vérifier le token et récupérer l'utilisateur
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

        # Boucle de maintien de connexion
        try:
            while True:
                # Attendre un message du client (heartbeat)
                data = await websocket.receive_text()

                # Le client peut envoyer "ping" pour maintenir la connexion
                if data == "ping":
                    await websocket.send_json(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                    )

        except WebSocketDisconnect:
            logger.info(f"Client disconnected from deployment {deployment_id}")

    except Exception as e:
        logger.error(f"WebSocket error for deployment {deployment_id}: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass

    finally:
        await manager.disconnect(websocket, deployment_id)
