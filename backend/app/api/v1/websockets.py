"""
Endpoints WebSocket pour WindFlow.

Ce module contient uniquement les routes WebSocket.
La logique métier a été déplacée dans backend/app/websocket/ pour une
meilleure organisation et maintenabilité.
"""

from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio
import logging
import json
from datetime import datetime

from ...database import get_db
from ...models.deployment import Deployment
from ...models.user import User
from ...schemas.websocket_events import WebSocketEventType

# Import depuis le package websocket
from ...websocket import (
    plugin_manager,
    PluginContext,
    manager,
    user_manager,
    add_user_connection,
    remove_user_connection,
    broadcast_deployment_log,
    broadcast_deployment_status,
    broadcast_deployment_progress,
    broadcast_deployment_complete,
    broadcast_to_user,
    broadcast_to_event_subscribers,
    broadcast_deployment_log_to_subscribers
)
from ...websocket.plugins import default_plugins, default_message_handlers

logger = logging.getLogger(__name__)

router = APIRouter()

# Register default plugins
for plugin in default_plugins:
    plugin_manager.register(plugin)

# Register default message handlers
for handler in default_message_handlers:
    plugin_manager.register_message_handler(handler)


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

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

            # Créer le contexte pour les plugins (sans db car la session sera fermée)
            plugin_context = PluginContext(
                db=None,  # On ne garde pas de session ouverte pendant toute la connexion
                user=user,
                websocket=websocket,
                logger=logger,
                broadcast_to_user=lambda uid, msg: broadcast_to_user(uid, msg),
                broadcast_to_event_subscribers=lambda evt, msg: broadcast_to_event_subscribers(evt, msg),
                broadcast_deployment_log_to_subscribers=lambda dep_id, msg: broadcast_deployment_log_to_subscribers(dep_id, msg)
            )

            # Initialiser les plugins avec le contexte
            await plugin_manager.initialize_all(plugin_context)

            # Préparer les données d'événement
            auth_event_data = {
                "user_id": str(user.id),
                "username": user.username,
                "organization_id": str(user.organization_id) if user.organization_id else None
            }

            # Envoyer un message de confirmation d'authentification
            await websocket.send_json({
                "type": WebSocketEventType.AUTH_LOGIN_SUCCESS,
                "timestamp": datetime.utcnow().isoformat(),
                "data": auth_event_data
            })

            # Dispatcher l'événement aux plugins
            await plugin_manager.dispatch(
                WebSocketEventType.AUTH_LOGIN_SUCCESS,
                auth_event_data,
                plugin_context
            )

            logger.info(f"General WebSocket connected for user {user.id}")

        # Ajouter l'utilisateur aux connexions actives (en dehors du bloc async with)
        await add_user_connection(str(user.id), websocket, plugin_context)

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

                        # Utiliser le système de plugins pour gérer le message
                        response = await plugin_manager.handle_client_message(message, plugin_context)

                        if response:
                            # Le handler a retourné une réponse, l'envoyer au client
                            await websocket.send_json(response)
                        else:
                            # Aucun handler n'a traité le message, répondre avec un écho
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
            await remove_user_connection(str(user.id), websocket)
            # Nettoyer les plugins
            if 'plugin_context' in locals():
                await plugin_manager.cleanup_all(plugin_context)


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
