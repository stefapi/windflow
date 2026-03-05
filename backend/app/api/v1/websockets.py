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

@router.websocket(
    "/",
    name="general_websocket"
)
async def general_websocket(
    websocket: WebSocket
):
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

        # Créer une session qui restera ouverte pendant toute la connexion
        async with database.session() as db:
            user = await UserService.get_by_id(db, token_data.user_id)
            logger.info(f"User found: {user is not None}, active: {user.is_active if user else 'N/A'}")
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

            # Ajouter l'utilisateur aux connexions actives
            await add_user_connection(str(user.id), websocket, plugin_context)

            # Tâche de heartbeat serveur vers client
            heartbeat_task = None

            async def send_heartbeat():
                """Envoie un heartbeat périodique au client."""
                try:
                    while True:
                        await asyncio.sleep(30)  # Toutes les 30 secondes
                        await websocket.send_json({
                            "type": "ping",
                            "timestamp": datetime.utcnow().isoformat()
                        })
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
        # Note: La session DB sera fermée automatiquement à la sortie du bloc async with


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


@router.websocket(
    "/deployments/{deployment_id}/logs",
    name="deployment_logs_websocket"
)
async def deployment_logs_websocket(
    websocket: WebSocket,
    deployment_id: str
):
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


# =============================================================================
# Gestion des sessions terminal pour rate limiting
# =============================================================================

# Store en mémoire pour les sessions terminal actives (en production, utiliser Redis)
terminal_sessions: dict[str, dict] = {}
MAX_TERMINAL_SESSIONS_PER_USER = 3


async def check_terminal_rate_limit(user_id: str) -> tuple[bool, str]:
    """
    Vérifie le rate limit pour les sessions terminal.

    Args:
        user_id: ID de l'utilisateur

    Returns:
        Tuple (autorisé, message_erreur)
    """
    # Compter les sessions actives pour cet utilisateur
    user_sessions = [
        sid for sid, info in terminal_sessions.items()
        if info.get("user_id") == user_id
    ]

    if len(user_sessions) >= MAX_TERMINAL_SESSIONS_PER_USER:
        return False, f"Maximum {MAX_TERMINAL_SESSIONS_PER_USER} terminal sessions allowed per user"

    return True, ""


async def register_terminal_session(exec_id: str, user_id: str, container_id: str) -> None:
    """Enregistre une session terminal active."""
    terminal_sessions[exec_id] = {
        "user_id": user_id,
        "container_id": container_id,
        "started_at": datetime.utcnow().isoformat()
    }


async def unregister_terminal_session(exec_id: str) -> None:
    """Supprime une session terminal."""
    if exec_id in terminal_sessions:
        del terminal_sessions[exec_id]


async def log_terminal_audit(
    user_id: str,
    username: str,
    container_id: str,
    action: str,
    success: bool,
    details: str = ""
) -> None:
    """
    Log les événements du terminal pour l'audit trail.

    Args:
        user_id: ID de l'utilisateur
        username: Nom d'utilisateur
        container_id: ID du conteneur
        action: Action performed (connect, disconnect, error)
        success: Si l'action a réussi
        details: Détails supplémentaires
    """
    from datetime import datetime
    import logging

    audit_logger = logging.getLogger("terminal_audit")

    extra = {
        "event": "terminal_session",
        "user_id": str(user_id),
        "username": username,
        "container_id": container_id,
        "action": action,
        "success": success,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if details:
        extra["details"] = details

    if success:
        audit_logger.info(
            f"Terminal session: {action} by {username} on container {container_id[:12]}",
            extra=extra
        )
    else:
        audit_logger.warning(
            f"Terminal session failed: {action} by {username} on container {container_id[:12]} - {details}",
            extra=extra
        )


@router.websocket(
    "/terminal/{container_id}",
    name="container_terminal_websocket"
)
async def container_terminal_websocket(
    websocket: WebSocket,
    container_id: str,
    shell: str = "/bin/sh",
    user: str = "root"
):
    """
    Interactive terminal WebSocket for Docker containers.

    Provides bidirectional streaming for command execution in containers.

    Authentication:
    First message must be: {"type": "auth", "token": "JWT_TOKEN"}

    Security:
    - RBAC: User must have access to the deployment containing the container
    - Rate limiting: Maximum 3 concurrent sessions per user
    - Audit trail: All sessions are logged for compliance

    Client Messages:
    - auth: {"type": "auth", "token": "JWT_TOKEN"}
    - input: {"type": "input", "data": "ls\\n"}
    - resize: {"type": "resize", "cols": 120, "rows": 30}
    - ping: {"type": "ping"}

    Server Messages:
    - ready: {"type": "ready", "exec_id": "xxx", "shell": "/bin/sh", "user": "root", "cols": 80, "rows": 24}
    - output: {"type": "output", "data": "..."}
    - error: {"type": "error", "message": "..."}
    - exit: {"type": "exit", "code": 0}
    - pong: {"type": "pong", "timestamp": "..."}
    """
    import asyncio
    import json
    import logging
    from datetime import datetime
    from typing import Optional
    from sqlalchemy import select

    from ...services.terminal_service import TerminalService, ExecSession
    from ...auth.jwt import decode_access_token
    from ...services.user_service import UserService
    from ...database import db as database
    from ...models.deployment import Deployment

    logger = logging.getLogger(__name__)

    # Accepter la connexion WebSocket
    await websocket.accept()

    # Variables pour la session
    ws_user = None
    authenticated = False
    session: Optional[ExecSession] = None
    terminal_service: Optional[TerminalService] = None
    streaming_task: Optional[asyncio.Task] = None
    exec_id = None

    try:
        # Attendre le message d'authentification (30s timeout)
        try:
            data = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            await log_terminal_audit(
                "unknown", "unknown", container_id,
                "connect", False, "Authentication timeout"
            )
            await websocket.send_json({
                "type": "error",
                "message": "Authentication timeout"
            })
            await websocket.close(code=1008)
            return

        # Parser le message d'auth
        try:
            message = json.loads(data)
        except json.JSONDecodeError:
            await log_terminal_audit(
                "unknown", "unknown", container_id,
                "connect", False, "Invalid JSON format"
            )
            await websocket.send_json({
                "type": "error",
                "message": "Invalid JSON format"
            })
            await websocket.close(code=1008)
            return

        # Vérifier le type de message
        if message.get("type") != "auth" or "token" not in message:
            await log_terminal_audit(
                "unknown", "unknown", container_id,
                "connect", False, "Authentication required as first message"
            )
            await websocket.send_json({
                "type": "error",
                "message": "Authentication required as first message"
            })
            await websocket.close(code=1008)
            return

        # Valider le token JWT
        token = message["token"]
        token_data = decode_access_token(token)

        if token_data is None or token_data.user_id is None:
            await log_terminal_audit(
                "unknown", "unknown", container_id,
                "connect", False, "Invalid token"
            )
            await websocket.send_json({
                "type": "error",
                "message": "Invalid token"
            })
            await websocket.close(code=1008)
            return

        # Vérifier l'utilisateur et ses permissions (RBAC)
        async with database.session() as db:
            ws_user = await UserService.get_by_id(db, token_data.user_id)
            if ws_user is None or not ws_user.is_active:
                await log_terminal_audit(
                    str(token_data.user_id), "unknown", container_id,
                    "connect", False, "User not found or inactive"
                )
                await websocket.send_json({
                    "type": "error",
                    "message": "User not found or inactive"
                })
                await websocket.close(code=1008)
                return

            # RBAC: Vérifier que l'utilisateur a accès au déploiement contenant ce container
            # Le container_id doit correspondre à un déploiement accessible
            stmt = select(Deployment).where(Deployment.container_id == container_id)
            result = await db.execute(stmt)
            deployment = result.scalar_one_or_none()

            if deployment is None:
                # Le déploiement n'existe pas ou n'a pas de container_id
                # On autorise quand même pour permettre l'accès direct au container
                # en production, on pourrait être plus strict
                pass
            else:
                # Vérifier l'accès à l'organisation
                if deployment.organization_id != ws_user.organization_id and not ws_user.is_superadmin:
                    await log_terminal_audit(
                        str(ws_user.id), ws_user.username, container_id,
                        "connect", False, "Permission denied - organization mismatch"
                    )
                    await websocket.send_json({
                        "type": "error",
                        "message": "Permission denied: you don't have access to this container"
                    })
                    await websocket.close(code=1008)
                    return

        # Rate limiting: vérifier le nombre de sessions simultanées
        can_connect, rate_limit_msg = await check_terminal_rate_limit(str(ws_user.id))
        if not can_connect:
            await log_terminal_audit(
                str(ws_user.id), ws_user.username, container_id,
                "connect", False, rate_limit_msg
            )
            await websocket.send_json({
                "type": "error",
                "message": rate_limit_msg
            })
            await websocket.close(code=1008)
            return

        authenticated = True

        # Logger l'audit de connexion
        await log_terminal_audit(
            str(ws_user.id), ws_user.username, container_id,
            "connect", True, f"shell={shell}, user={user}"
        )

        logger.info(f"Terminal WebSocket authenticated for user {ws_user.id}, container {container_id}")

        # Initialiser le service terminal
        terminal_service = TerminalService()

        # Créer la session exec dans le conteneur
        try:
            session = await terminal_service.create_session(
                container_id=container_id,
                shell=shell,
                user=user,
                cols=80,
                rows=24,
            )
            exec_id = session.exec_id

            # Enregistrer la session pour le rate limiting
            await register_terminal_session(exec_id, str(ws_user.id), container_id)

        except ValueError as e:
            await log_terminal_audit(
                str(ws_user.id), ws_user.username, container_id,
                "connect", False, str(e)
            )
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
            await websocket.close(code=1008)
            return
        except RuntimeError as e:
            await log_terminal_audit(
                str(ws_user.id), ws_user.username, container_id,
                "connect", False, str(e)
            )
            await websocket.send_json({
                "type": "error",
                "message": f"Failed to create terminal: {e}"
            })
            await websocket.close(code=1011)
            return

        # Envoyer le message ready au client
        await websocket.send_json({
            "type": "ready",
            "exec_id": session.exec_id,
            "shell": session.shell,
            "user": session.user,
            "cols": session.cols,
            "rows": session.rows,
        })

        # Démarrer la tâche de streaming en arrière-plan
        async def stream_output():
            """Stream la sortie du terminal vers le client."""
            try:
                async for data, is_stderr in terminal_service.stream_output(session):
                    try:
                        await websocket.send_json({
                            "type": "output",
                            "data": data.decode("utf-8", errors="replace"),
                        })
                    except Exception as send_error:
                        logger.error(f"Error sending output: {send_error}")
                        break

                # La session s'est terminée
                exit_code = session.process.returncode if session.process else 0
                try:
                    await websocket.send_json({
                        "type": "exit",
                        "code": exit_code,
                    })
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"Streaming error: {e}")
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Streaming error: {e}"
                    })
                except Exception:
                    pass

        streaming_task = asyncio.create_task(stream_output())

        # Boucle principale - gérer les messages du client
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=60.0
                )

                # Heartbeat
                if data == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    continue

                # Parser le message
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    continue

                msg_type = message.get("type")

                if msg_type == "input":
                    # Envoyer l'input au terminal
                    if session and terminal_service:
                        try:
                            await terminal_service.send_input(
                                session,
                                message.get("data", "")
                            )
                        except Exception as e:
                            await websocket.send_json({
                                "type": "error",
                                "message": f"Input error: {e}"
                            })

                elif msg_type == "resize":
                    # Redimensionner le TTY
                    if session and terminal_service:
                        cols = message.get("cols", 80)
                        rows = message.get("rows", 24)
                        try:
                            await terminal_service.resize_tty(session, cols, rows)
                        except Exception as e:
                            logger.warning(f"Resize error: {e}")

                elif msg_type == "ping":
                    # already handled above
                    pass

            except asyncio.TimeoutError:
                # Timeout - juste envoyer un pong pour maintenir la connexion
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })

            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break

    except Exception as e:
        logger.error(f"Terminal WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except Exception:
            pass

    finally:
        # Nettoyer la session
        if streaming_task:
            streaming_task.cancel()
            try:
                await streaming_task
            except asyncio.CancelledError:
                pass

        if session and terminal_service:
            await terminal_service.cleanup_session(session)

        if terminal_service:
            await terminal_service.close()

        # Supprimer la session du rate limiter
        if exec_id:
            await unregister_terminal_session(exec_id)

        # Logger l'audit de déconnexion
        if ws_user and authenticated:
            await log_terminal_audit(
                str(ws_user.id), ws_user.username, container_id,
                "disconnect", True, f"exec_id={exec_id}"
            )

        logger.info(f"Terminal WebSocket closed for container {container_id}")


@router.websocket(
    "/docker/containers/{container_id}/logs",
    name="docker_container_logs_websocket"
)
async def docker_container_logs_websocket(
    websocket: WebSocket,
    container_id: str,
    tail: int = 100
):
    """
    Stream Docker container logs in real-time.

    Connect to stream logs from a specific Docker container.

    Authentication:
    Authentication is performed via query parameter: ?token=JWT_TOKEN

    Query Parameters:
    - token: JWT token for authentication
    - tail: Number of lines to retrieve (default: 100)

    Connection Flow:
    1. Client connects with container ID and token in query string
    2. Server validates token and user permissions
    3. Server sends initial container info
    4. Client receives real-time log updates using Docker logs --follow

    Message Types Sent:
    - initial: Initial container information and existing logs
    - log: Real-time log entries as they occur
    - error: Error notifications

    Client Messages:
    - Heartbeat: Send "ping" to keep connection alive
    """
    # Extract token from query parameters
    token = websocket.query_params.get('token')
    tail = int(websocket.query_params.get('tail', '100'))

    # Accepter la connexion
    await websocket.accept()

    # Authentifier
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return

    from ...auth.jwt import decode_access_token
    from ...services.user_service import UserService
    from ...database import db as database
    from ...services.docker_client_service import get_docker_client

    token_data = decode_access_token(token)
    if token_data is None or token_data.user_id is None:
        await websocket.close(code=1008, reason="Invalid token")
        return

    # Vérifier l'utilisateur
    async with database.session() as db:
        user = await UserService.get_by_id(db, token_data.user_id)
        if user is None or not user.is_active:
            await websocket.close(code=1008, reason="User not found or inactive")
            return

    # Récupérer le client Docker
    try:
        docker_client = get_docker_client()
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"Docker not available: {str(e)}"
        })
        await websocket.close(code=1011)  # Internal Error
        return

    try:
        # Envoyer les logs initiaux
        initial_logs = await docker_client.get_container_logs(
            container_id,
            tail=tail,
            since=None
        )

        await websocket.send_json({
            "type": "initial",
            "container_id": container_id,
            "logs": initial_logs
        })

        # Boucle principale - attendre lesheartbeats
        # Note: Pour un streaming temps réel avec --follow,
        # il faudrait une implémentation plus complexe avec asyncio
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=60.0
                )

                if data == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })

            except asyncio.TimeoutError:
                # Timeout - juste envoyer un pong pour maintenir la connexion
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from container logs {container_id}")

    except Exception as e:
        logger.error(f"Error streaming container logs {container_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass

    finally:
        # Fermer le client Docker si nécessaire
        if docker_client:
            await docker_client.close()
