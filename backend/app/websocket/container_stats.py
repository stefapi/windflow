"""
WebSocket endpoint pour le streaming des statistiques Docker container en temps réel.

Ce module gère la connexion WebSocket pour suivre les stats d'un container Docker
avec support du streaming via docker stats API.
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


def calculate_cpu_percent(stats_data: dict) -> float:
    """
    Calcule le pourcentage CPU à partir des stats Docker.

    Args:
        stats_data: Données de stats Docker brutes

    Returns:
        Pourcentage CPU (0-100)
    """
    cpu_stats = stats_data.get("cpu_stats", {})
    precpu_stats = stats_data.get("precpu_stats", {})

    cpu_usage = cpu_stats.get("cpu_usage", {})
    precpu_usage = precpu_stats.get("cpu_usage", {})

    # Total CPU time
    cpu_total = cpu_usage.get("total_usage", 0)
    precpu_total = precpu_usage.get("total_usage", 0)

    # System CPU time
    system_cpu = cpu_stats.get("system_cpu_usage", 0)
    pre_system_cpu = precpu_stats.get("system_cpu_usage", 0)

    # Number of CPUs
    online_cpus = cpu_stats.get("online_cpus", 1)
    if online_cpus == 0:
        online_cpus = len(cpu_usage.get("percpu_usage", [])) or 1

    # Calculate delta
    cpu_delta = cpu_total - precpu_total
    system_delta = system_cpu - pre_system_cpu

    if system_delta > 0 and cpu_delta > 0:
        cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0
        return round(min(cpu_percent, 100.0 * online_cpus), 2)

    return 0.0


def calculate_memory_percent(stats_data: dict) -> tuple[float, int, int]:
    """
    Calcule le pourcentage mémoire et les valeurs utilisées/limites.

    Args:
        stats_data: Données de stats Docker brutes

    Returns:
        Tuple (pourcentage, mémoire utilisée, limite mémoire)
    """
    memory_stats = stats_data.get("memory_stats", {})

    # Memory usage (cache-inclusive)
    usage = memory_stats.get("usage", 0)
    # Cache/buffer memory (not counted as "real" usage)
    cache = memory_stats.get("cache", 0) or memory_stats.get("stats", {}).get("cache", 0)
    # Actual used memory
    used_memory = usage - cache if usage > cache else usage
    # Memory limit
    limit = memory_stats.get("limit", 0)

    if limit > 0:
        memory_percent = (used_memory / limit) * 100.0
        return round(min(memory_percent, 100.0), 2), used_memory, limit

    return 0.0, used_memory, limit


def calculate_network_io(stats_data: dict) -> tuple[int, int]:
    """
    Calcule les I/O réseau (rx/tx bytes).

    Args:
        stats_data: Données de stats Docker brutes

    Returns:
        Tuple (bytes reçus, bytes envoyés)
    """
    networks = stats_data.get("networks", {})

    total_rx = 0
    total_tx = 0

    for iface_stats in networks.values():
        total_rx += iface_stats.get("rx_bytes", 0)
        total_tx += iface_stats.get("tx_bytes", 0)

    return total_rx, total_tx


def calculate_block_io(stats_data: dict) -> tuple[int, int]:
    """
    Calcule les I/O disque (read/write bytes).

    Args:
        stats_data: Données de stats Docker brutes

    Returns:
        Tuple (bytes lus, bytes écrits)
    """
    blkio_stats = stats_data.get("blkio_stats", {})
    io_service_bytes = blkio_stats.get("io_service_bytes_recursive", [])

    total_read = 0
    total_write = 0

    if io_service_bytes:
        for entry in io_service_bytes:
            if entry.get("op", "").lower() == "read":
                total_read += entry.get("value", 0)
            elif entry.get("op", "").lower() == "write":
                total_write += entry.get("value", 0)

    return total_read, total_write


def format_stats_response(container_id: str, stats_data: dict) -> dict:
    """
    Formate les stats Docker en réponse structurée pour le frontend.

    Args:
        container_id: ID du container
        stats_data: Données de stats Docker brutes

    Returns:
        Dictionnaire formaté avec les métriques calculées
    """
    cpu_percent = calculate_cpu_percent(stats_data)
    memory_percent, memory_used, memory_limit = calculate_memory_percent(stats_data)
    network_rx, network_tx = calculate_network_io(stats_data)
    block_read, block_write = calculate_block_io(stats_data)

    return {
        "type": "stats",
        "container_id": container_id,
        "timestamp": datetime.utcnow().isoformat(),
        "cpu": {
            "percent": cpu_percent,
        },
        "memory": {
            "percent": memory_percent,
            "used": memory_used,
            "limit": memory_limit,
        },
        "network": {
            "rx_bytes": network_rx,
            "tx_bytes": network_tx,
        },
        "block_io": {
            "read_bytes": block_read,
            "write_bytes": block_write,
        },
    }


async def container_stats_websocket_endpoint(
    websocket: WebSocket, container_id: str
):
    """
    Stream Docker container stats in real-time.

    Connect to stream stats from a specific Docker container.

    Authentication:
    Authentication is performed via query parameter: ?token=JWT_TOKEN

    Query Parameters:
    - token: JWT token for authentication

    Connection Flow:
    1. Client connects with container ID and token in query string
    2. Server validates token and user permissions
    3. Server sends initial container info
    4. Client receives real-time stats updates every ~1 second

    Message Types Sent:
    - initial: Initial container state
    - stats: Real-time stats (CPU %, Memory %, Network I/O, Block I/O)
    - error: Error notifications
    - stream_status: Streaming status updates (started, stopped, container_stopped)

    Client Messages:
    - Heartbeat: Send "ping" to keep connection alive
    """
    # Extract token from query parameters
    token = websocket.query_params.get("token")

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

    # Tâche de streaming des stats en temps réel
    streaming_task: Optional[asyncio.Task] = None
    streaming_error: Optional[str] = None
    streaming_active = True

    async def stream_realtime_stats():
        """Stream les stats en temps réel vers le client WebSocket."""
        nonlocal streaming_error, streaming_active
        try:
            logger.info(
                f"[ContainerStats] Starting real-time stream for container {container_id}"
            )

            async for stats_data in docker_client.container_stats(
                container_id,
                stream=True,  # Mode streaming temps réel
            ):
                if not streaming_active:
                    break

                # Calculer et formater les stats
                formatted_stats = format_stats_response(container_id, stats_data)

                try:
                    await websocket.send_json(formatted_stats)
                except Exception as send_error:
                    logger.debug(f"Error sending stats: {send_error}")
                    break

            # Si on arrive ici, le stream s'est terminé normalement
            logger.info(f"[ContainerStats] Stream ended for container {container_id}")
            try:
                await websocket.send_json(
                    {
                        "type": "stream_status",
                        "status": "ended",
                        "message": "Stats stream ended (container may have stopped)",
                    }
                )
            except:
                pass

        except asyncio.CancelledError:
            # Normal lors de la déconnexion
            logger.debug(
                f"[ContainerStats] Stream cancelled for container {container_id}"
            )
        except Exception as e:
            streaming_error = str(e)
            streaming_active = False
            logger.error(f"[ContainerStats] Error in stats streaming task: {e}")
            try:
                await websocket.send_json(
                    {"type": "error", "message": f"Stats streaming error: {str(e)}"}
                )
            except:
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
                            f"[ContainerStats] Container {container_id} is not running (status: {container_info.state.get('Status')})"
                        )
                        try:
                            await websocket.send_json(
                                {
                                    "type": "stream_status",
                                    "status": "container_stopped",
                                    "message": f"Container is {container_info.state.get('Status')}",
                                }
                            )
                        except:
                            pass
                        streaming_active = False
                        break
                except Exception as e:
                    logger.debug(
                        f"[ContainerStats] Error checking container status: {e}"
                    )
                    # Ne pas arrêter le stream pour une erreur de vérification
        except asyncio.CancelledError:
            pass

    status_check_task: Optional[asyncio.Task] = None

    try:
        # Vérifier que le container existe et est en cours d'exécution
        container_info = await docker_client.get_container(container_id)
        container_status = container_info.state.get("Status", "unknown")

        # Envoyer les infos initiales
        await websocket.send_json(
            {
                "type": "initial",
                "container_id": container_id,
                "container_status": container_status,
            }
        )

        # Si le container n'est pas running, ne pas streamer
        if container_status != "running":
            await websocket.send_json(
                {
                    "type": "stream_status",
                    "status": "container_stopped",
                    "message": f"Container is {container_status}",
                }
            )
            streaming_active = False
            return

        # Démarrer la tâche de streaming temps réel
        streaming_task = asyncio.create_task(stream_realtime_stats())

        # Démarrer la tâche de vérification du statut du container
        status_check_task = asyncio.create_task(check_container_status())

        # Notifier le démarrage du stream
        await websocket.send_json(
            {
                "type": "stream_status",
                "status": "started",
                "message": "Stats streaming started",
            }
        )

        # Boucle principale - attendre les heartbeats du client
        while streaming_active:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0,  # 30s timeout
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
                except:
                    streaming_active = False
                    break

            # Vérifier si la tâche de streaming a échoué
            if streaming_task and streaming_task.done():
                if streaming_error:
                    logger.error(
                        f"[ContainerStats] Streaming task failed: {streaming_error}"
                    )
                streaming_active = False
                break

    except WebSocketDisconnect:
        logger.info(
            f"[ContainerStats] Client disconnected from container stats {container_id}"
        )
        streaming_active = False

    except Exception as e:
        logger.error(
            f"[ContainerStats] Error streaming container stats {container_id}: {e}"
        )
        streaming_active = False
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
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

        logger.info(f"[ContainerStats] WebSocket closed for container {container_id}")
