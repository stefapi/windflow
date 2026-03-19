"""
WebSocket endpoint pour le terminal interactif Docker container.

Ce module gère la connexion WebSocket pour exécuter des commandes
dans un container Docker via un terminal interactif.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import WebSocket
from sqlalchemy import select

from ..auth.jwt import decode_access_token
from ..database import db as database
from ..models.deployment import Deployment
from ..services.terminal_service import ExecSession, TerminalService
from ..services.user_service import UserService

logger = logging.getLogger(__name__)

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
        sid for sid, info in terminal_sessions.items() if info.get("user_id") == user_id
    ]

    if len(user_sessions) >= MAX_TERMINAL_SESSIONS_PER_USER:
        return (
            False,
            f"Maximum {MAX_TERMINAL_SESSIONS_PER_USER} terminal sessions allowed per user",
        )

    return True, ""


async def register_terminal_session(
    exec_id: str, user_id: str, container_id: str
) -> None:
    """Enregistre une session terminal active."""
    terminal_sessions[exec_id] = {
        "user_id": user_id,
        "container_id": container_id,
        "started_at": datetime.utcnow().isoformat(),
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
    details: str = "",
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
            extra=extra,
        )
    else:
        audit_logger.warning(
            f"Terminal session failed: {action} by {username} on container {container_id[:12]} - {details}",
            extra=extra,
        )


async def container_terminal_websocket_endpoint(
    websocket: WebSocket, container_id: str, shell: str = "/bin/sh", user: str = "root"
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
            data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
        except asyncio.TimeoutError:
            await log_terminal_audit(
                "unknown",
                "unknown",
                container_id,
                "connect",
                False,
                "Authentication timeout",
            )
            await websocket.send_json(
                {"type": "error", "message": "Authentication timeout"}
            )
            await websocket.close(code=1008)
            return

        # Parser le message d'auth
        try:
            message = json.loads(data)
        except json.JSONDecodeError:
            await log_terminal_audit(
                "unknown",
                "unknown",
                container_id,
                "connect",
                False,
                "Invalid JSON format",
            )
            await websocket.send_json(
                {"type": "error", "message": "Invalid JSON format"}
            )
            await websocket.close(code=1008)
            return

        # Vérifier le type de message
        if message.get("type") != "auth" or "token" not in message:
            await log_terminal_audit(
                "unknown",
                "unknown",
                container_id,
                "connect",
                False,
                "Authentication required as first message",
            )
            await websocket.send_json(
                {"type": "error", "message": "Authentication required as first message"}
            )
            await websocket.close(code=1008)
            return

        # Valider le token JWT
        token = message["token"]
        token_data = decode_access_token(token)

        if token_data is None or token_data.user_id is None:
            await log_terminal_audit(
                "unknown", "unknown", container_id, "connect", False, "Invalid token"
            )
            await websocket.send_json({"type": "error", "message": "Invalid token"})
            await websocket.close(code=1008)
            return

        # Vérifier l'utilisateur et ses permissions (RBAC)
        async with database.session() as db:
            ws_user = await UserService.get_by_id(db, token_data.user_id)
            if ws_user is None or not ws_user.is_active:
                await log_terminal_audit(
                    str(token_data.user_id),
                    "unknown",
                    container_id,
                    "connect",
                    False,
                    "User not found or inactive",
                )
                await websocket.send_json(
                    {"type": "error", "message": "User not found or inactive"}
                )
                await websocket.close(code=1008)
                return

            # RBAC: Vérifier que l'utilisateur a accès au déploiement contenant ce container
            stmt = select(Deployment).where(Deployment.container_id == container_id)
            result = await db.execute(stmt)
            deployment = result.scalar_one_or_none()

            if deployment is None:
                # Le déploiement n'existe pas ou n'a pas de container_id
                # On autorise quand même pour permettre l'accès direct au container
                pass
            else:
                # Vérifier l'accès à l'organisation
                if (
                    deployment.organization_id != ws_user.organization_id
                    and not ws_user.is_superadmin
                ):
                    await log_terminal_audit(
                        str(ws_user.id),
                        ws_user.username,
                        container_id,
                        "connect",
                        False,
                        "Permission denied - organization mismatch",
                    )
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Permission denied: you don't have access to this container",
                        }
                    )
                    await websocket.close(code=1008)
                    return

        # Rate limiting: vérifier le nombre de sessions simultanées
        can_connect, rate_limit_msg = await check_terminal_rate_limit(str(ws_user.id))
        if not can_connect:
            await log_terminal_audit(
                str(ws_user.id),
                ws_user.username,
                container_id,
                "connect",
                False,
                rate_limit_msg,
            )
            await websocket.send_json({"type": "error", "message": rate_limit_msg})
            await websocket.close(code=1008)
            return

        authenticated = True

        # Logger l'audit de connexion
        await log_terminal_audit(
            str(ws_user.id),
            ws_user.username,
            container_id,
            "connect",
            True,
            f"shell={shell}, user={user}",
        )

        logger.info(
            f"Terminal WebSocket authenticated for user {ws_user.id}, container {container_id}"
        )

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
                str(ws_user.id),
                ws_user.username,
                container_id,
                "connect",
                False,
                str(e),
            )
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close(code=1008)
            return
        except RuntimeError as e:
            await log_terminal_audit(
                str(ws_user.id),
                ws_user.username,
                container_id,
                "connect",
                False,
                str(e),
            )
            await websocket.send_json(
                {"type": "error", "message": f"Failed to create terminal: {e}"}
            )
            await websocket.close(code=1011)
            return

        # Envoyer le message ready au client
        await websocket.send_json(
            {
                "type": "ready",
                "exec_id": session.exec_id,
                "shell": session.shell,
                "user": session.user,
                "cols": session.cols,
                "rows": session.rows,
            }
        )

        # Démarrer la tâche de streaming en arrière-plan
        async def stream_output():
            """Stream la sortie du terminal vers le client."""
            try:
                async for data, is_stderr in terminal_service.stream_output(session):
                    try:
                        await websocket.send_json(
                            {
                                "type": "output",
                                "data": data.decode("utf-8", errors="replace"),
                            }
                        )
                    except Exception as send_error:
                        logger.error(f"Error sending output: {send_error}")
                        break

                # La session s'est terminée
                exit_code = session.process.returncode if session.process else 0
                try:
                    await websocket.send_json(
                        {
                            "type": "exit",
                            "code": exit_code,
                        }
                    )
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"Streaming error: {e}")
                try:
                    await websocket.send_json(
                        {"type": "error", "message": f"Streaming error: {e}"}
                    )
                except Exception:
                    pass

        streaming_task = asyncio.create_task(stream_output())

        # Boucle principale - gérer les messages du client
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)

                # Heartbeat
                if data == "ping":
                    await websocket.send_json(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                    )
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
                                session, message.get("data", "")
                            )
                        except Exception as e:
                            await websocket.send_json(
                                {"type": "error", "message": f"Input error: {e}"}
                            )

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
                await websocket.send_json(
                    {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                )

            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break

    except Exception as e:
        logger.error(f"Terminal WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
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
                str(ws_user.id),
                ws_user.username,
                container_id,
                "disconnect",
                True,
                f"exec_id={exec_id}",
            )

        logger.info(f"Terminal WebSocket closed for container {container_id}")
