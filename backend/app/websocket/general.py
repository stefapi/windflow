"""
WebSocket endpoint général pour les événements temps réel.

Ce module gère la connexion WebSocket principale pour les notifications
système, mises à jour de déploiements et événements utilisateur.
"""

import asyncio
import json
import logging
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

from ..auth.jwt import decode_access_token
from ..database import db as database
from ..schemas.websocket_events import WebSocketEventType
from ..services.user_service import UserService

# Import depuis le package websocket
from . import (
    PluginContext,
    add_user_connection,
    broadcast_deployment_log_to_subscribers,
    broadcast_to_event_subscribers,
    broadcast_to_user,
    plugin_manager,
    remove_user_connection,
)
from .plugins import default_message_handlers, default_plugins

logger = logging.getLogger(__name__)

# Register default plugins
for plugin in default_plugins:
    plugin_manager.register(plugin)

# Register default message handlers
for handler in default_message_handlers:
    plugin_manager.register_message_handler(handler)


async def general_websocket_endpoint(websocket: WebSocket):
    """
    General WebSocket connection for real-time events.

    Connect to the general WebSocket endpoint for real-time system notifications and events.

    Authentication Process:
    1. Client connects to WebSocket endpoint
    2. Server accepts connection
    3. Client sends authentication message within 30 seconds: {"type": "auth", "token": "JWT_TOKEN"}
    4. Server validates token and user status
    5. Server sends authentication confirmation
    6. Connection is established for bidirectional communication

    Event Types Received:
    - System Notifications: Global system events and alerts
    - Deployment Updates: Real-time deployment status changes
    - Deployment Logs: Live streaming of deployment logs
    - User Events: User-specific notifications
    - Organization Events: Organization-wide updates

    Client Messages:
    - Authentication: {"type": "auth", "token": "JWT_TOKEN"}
    - Heartbeat: Send "ping" to keep connection alive
    - Custom Messages: Plugin-based message handling

    Server Responses:
    - Authentication Success: {"type": "auth.login.success", "data": {...}}
    - Pong: {"type": "pong", "timestamp": "..."}
    - Events: Various event types based on subscriptions
    - Errors: {"type": "error", "message": "..."}
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
                timeout=30.0,  # 30 secondes timeout pour le debug
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
            await websocket.close(
                code=1008, reason="Authentication required as first message"
            )
            return

        token = message["token"]
        logger.info(f"Authenticating with token length: {len(token)}")

        # Vérifier le token et récupérer l'utilisateur
        token_data = decode_access_token(token)
        logger.info(f"Token decoded: {token_data is not None}")
        if token_data is None or token_data.user_id is None:
            logger.error("Invalid token - could not decode token")
            await websocket.close(code=1008, reason="Invalid token - could not decode")
            return

        # Créer une session qui restera ouverte pendant toute la connexion
        async with database.session() as db:
            user = await UserService.get_by_id(db, token_data.user_id)
            logger.info(
                f"User found: {user is not None}, active: {user.is_active if user else 'N/A'}"
            )
            if user is None or not user.is_active:
                logger.error(f"User not found or inactive: {token_data.user_id}")
                await websocket.close(code=1008, reason="User not found or inactive")
                return

            # Authentification réussie
            authenticated = True

            # Créer le contexte pour les plugins avec la session DB disponible
            plugin_context = PluginContext(
                db=db,  # Session disponible pour toute la durée de la connexion
                user=user,
                websocket=websocket,
                logger=logger,
                broadcast_to_user=lambda uid, msg: broadcast_to_user(uid, msg),
                broadcast_to_event_subscribers=lambda evt, msg: broadcast_to_event_subscribers(
                    evt, msg
                ),
                broadcast_deployment_log_to_subscribers=lambda dep_id, msg: broadcast_deployment_log_to_subscribers(
                    dep_id, msg
                ),
            )

            # Initialiser les plugins avec le contexte
            await plugin_manager.initialize_all(plugin_context)

            # Préparer les données d'événement
            auth_event_data = {
                "user_id": str(user.id),
                "username": user.username,
                "organization_id": (
                    str(user.organization_id) if user.organization_id else None
                ),
            }

            # Envoyer un message de confirmation d'authentification
            await websocket.send_json(
                {
                    "type": WebSocketEventType.AUTH_LOGIN_SUCCESS,
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": auth_event_data,
                }
            )

            # Dispatcher l'événement aux plugins
            await plugin_manager.dispatch(
                WebSocketEventType.AUTH_LOGIN_SUCCESS, auth_event_data, plugin_context
            )

            logger.info(f"General WebSocket connected for user {user.id}")

            # Ajouter l'utilisateur aux connexions actives
            await add_user_connection(str(user.id), websocket, plugin_context)

            # Tâche de heartbeat serveur vers client
            heartbeat_task = None

            async def send_heartbeat():
                """Envoie un heartbeat périodique au client."""
                try:
                    while True:
                        await asyncio.sleep(30)  # Toutes les 30 secondes
                        await websocket.send_json(
                            {"type": "ping", "timestamp": datetime.utcnow().isoformat()}
                        )
                except asyncio.CancelledError:
                    pass  # Tâche annulée, normal lors de la déconnexion
                except Exception as e:
                    logger.error(f"Error in heartbeat task: {e}")

            # Démarrer la tâche de heartbeat
            heartbeat_task = asyncio.create_task(send_heartbeat())

            # Boucle de maintien de connexion
            try:
                while True:
                    # Attendre un message du client
                    data = await websocket.receive_text()

                    # Le client peut envoyer "ping" pour maintenir la connexion
                    if data == "ping":
                        await websocket.send_json(
                            {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                        )
                    else:
                        # Essayer de parser comme JSON pour d'autres types de messages
                        try:
                            message = json.loads(data)

                            # Utiliser le système de plugins pour gérer le message
                            response = await plugin_manager.handle_client_message(
                                message, plugin_context
                            )

                            if response:
                                # Le handler a retourné une réponse, l'envoyer au client
                                await websocket.send_json(response)
                            else:
                                # Aucun handler n'a traité le message, répondre avec un écho
                                await websocket.send_json(
                                    {
                                        "type": "message_received",
                                        "timestamp": datetime.utcnow().isoformat(),
                                        "data": message,
                                    }
                                )

                        except json.JSONDecodeError:
                            # Message texte simple
                            await websocket.send_json(
                                {
                                    "type": "text_received",
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "data": data,
                                }
                            )

            except WebSocketDisconnect:
                logger.info(f"General WebSocket disconnected for user {user.id}")
            finally:
                # Annuler la tâche de heartbeat
                if heartbeat_task:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass

    except Exception as e:
        logger.error(f"General WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass

    finally:
        # Nettoyer les connexions
        if user and authenticated:
            await remove_user_connection(str(user.id), websocket)
            # Nettoyer les plugins
            if "plugin_context" in locals():
                await plugin_manager.cleanup_all(plugin_context)
        # Note: La session DB sera fermée automatiquement à la sortie du bloc async with
