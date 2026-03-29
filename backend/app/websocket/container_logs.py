"""
WebSocket endpoint pour le streaming des logs Docker container en temps réel.

Ce module gère la connexion WebSocket pour suivre les logs d'un container Docker
avec support du streaming follow=True via aiohttp.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from ..auth.jwt import decode_access_token
from ..database import db as database
from ..services.docker_client_service import get_docker_client
from ..services.user_service import UserService

logger = logging.getLogger(__name__)


async def container_logs_websocket_endpoint(
    websocket: WebSocket, container_id: str, tail: int = 100
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
    - stream_status: Streaming status updates (started, stopped, container_stopped)

    Client Messages:
    - Heartbeat: Send "ping" to keep connection alive
    """
    # Extract token from query parameters
    token = websocket.query_params.get("token")
    tail = int(websocket.query_params.get("tail", "100"))

    # Accepter la connexion
    await websocket.accept()

    # Authentifier
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return

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
        docker_client = await get_docker_client()
    except Exception as e:
        await websocket.send_json(
            {"type": "error", "message": f"Docker not available: {str(e)}"}
        )
        await websocket.close(code=1011)  # Internal Error
        return

    # Tâche de streaming des logs en temps réel
    streaming_task: Optional[asyncio.Task] = None
    streaming_error: Optional[str] = None
    streaming_active = True

    async def stream_realtime_logs():
        """Stream les logs en temps réel vers le client WebSocket."""
        nonlocal streaming_error, streaming_active
        try:
            logger.info(
                f"[ContainerLogs] Starting real-time stream for container {container_id}"
            )

            async for line in docker_client.container_logs(
                container_id,
                tail=0,  # Ne pas récupérer les logs passés, seulement les nouveaux
                timestamps=False,
                follow=True,  # Mode streaming temps réel
            ):
                if not streaming_active:
                    break
                try:
                    await websocket.send_json({"type": "log", "data": line})
                except Exception as send_error:
                    logger.debug(f"Error sending log line: {send_error}")
                    break

            # Si on arrive ici, le stream s'est terminé normalement
            # Cela peut arriver si le container s'arrête
            logger.info(f"[ContainerLogs] Stream ended for container {container_id}")
            try:
                await websocket.send_json(
                    {
                        "type": "stream_status",
                        "status": "ended",
                        "message": "Log stream ended (container may have stopped)",
                    }
                )
            except Exception:
                pass

        except asyncio.CancelledError:
            # Normal lors de la déconnexion
            logger.debug(
                f"[ContainerLogs] Stream cancelled for container {container_id}"
            )
        except Exception as e:
            streaming_error = str(e)
            streaming_active = False
            logger.error(f"[ContainerLogs] Error in log streaming task: {e}")
            try:
                await websocket.send_json(
                    {"type": "error", "message": f"Log streaming error: {str(e)}"}
                )
            except Exception:
                pass

    async def check_container_status():
        """Vérifie périodiquement si le container est toujours en cours d'exécution."""
        nonlocal streaming_active
        try:
            while streaming_active:
                await asyncio.sleep(5)  # Vérifier toutes les 5 secondes
                if not streaming_active:
                    break
                try:
                    container_info = await docker_client.get_container(container_id)
                    if container_info.state.get("Status") != "running":
                        logger.info(
                            f"[ContainerLogs] Container {container_id} is not running (status: {container_info.state.get('Status')})"
                        )
                        try:
                            await websocket.send_json(
                                {
                                    "type": "stream_status",
                                    "status": "container_stopped",
                                    "message": f"Container is {container_info.state.get('Status')}",
                                }
                            )
                        except Exception:
                            pass
                        streaming_active = False
                        break
                except Exception as e:
                    logger.debug(
                        f"[ContainerLogs] Error checking container status: {e}"
                    )
                    # Ne pas arrêter le stream pour une erreur de vérification
        except asyncio.CancelledError:
            pass

    status_check_task: Optional[asyncio.Task] = None

    try:
        # Envoyer les logs initiaux
        logs_list = []
        async for line in docker_client.container_logs(
            container_id, tail=tail, timestamps=False, follow=False
        ):
            logs_list.append(line)
        initial_logs = "\n".join(logs_list)

        await websocket.send_json(
            {"type": "initial", "container_id": container_id, "logs": initial_logs}
        )

        # Démarrer la tâche de streaming temps réel
        streaming_task = asyncio.create_task(stream_realtime_logs())

        # Démarrer la tâche de vérification du statut du container
        status_check_task = asyncio.create_task(check_container_status())

        # Notifier le démarrage du stream
        await websocket.send_json(
            {
                "type": "stream_status",
                "status": "started",
                "message": "Log streaming started",
            }
        )

        # Boucle principale - attendre les heartbeats du client
        while streaming_active:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0,  # Réduit à 30s pour une détection plus rapide
                )

                if data == "ping":
                    await websocket.send_json(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                    )

            except asyncio.TimeoutError:
                # Timeout - envoyer un ping pour maintenir la connexion
                try:
                    await websocket.send_json(
                        {"type": "ping", "timestamp": datetime.utcnow().isoformat()}
                    )
                except Exception:
                    streaming_active = False
                    break

            # Vérifier si la tâche de streaming a échoué
            if streaming_task and streaming_task.done():
                if streaming_error:
                    logger.error(
                        f"[ContainerLogs] Streaming task failed: {streaming_error}"
                    )
                streaming_active = False
                break

    except WebSocketDisconnect:
        logger.info(
            f"[ContainerLogs] Client disconnected from container logs {container_id}"
        )
        streaming_active = False

    except Exception as e:
        logger.error(
            f"[ContainerLogs] Error streaming container logs {container_id}: {e}"
        )
        streaming_active = False
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass

    finally:
        streaming_active = False

        # Annuler la tâche de streaming
        if streaming_task and not streaming_task.done():
            streaming_task.cancel()
            try:
                await streaming_task
            except asyncio.CancelledError:
                pass

        # Annuler la tâche de vérification du statut
        if status_check_task and not status_check_task.done():
            status_check_task.cancel()
            try:
                await status_check_task
            except asyncio.CancelledError:
                pass

        # Fermer le client Docker si nécessaire
        if docker_client:
            await docker_client.close()

        logger.info(f"[ContainerLogs] WebSocket closed for container {container_id}")
