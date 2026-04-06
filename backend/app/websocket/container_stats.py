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

    Supporte cgroups v1 ET cgroups v2 :
    - cgroups v1 : cache dans memory_stats.cache ou memory_stats.stats.cache
    - cgroups v2 : cache dans memory_stats.stats.inactive_file

    Args:
        stats_data: Données de stats Docker brutes

    Returns:
        Tuple (pourcentage, mémoire utilisée, limite mémoire)
    """
    memory_stats = stats_data.get("memory_stats", {})
    memory_sub_stats = memory_stats.get("stats", {})

    # Memory usage (cache-inclusive)
    usage = memory_stats.get("usage", 0)

    # Cache/buffer memory (not counted as "real" usage)
    # cgroups v1: memory_stats.cache or memory_stats.stats.cache
    # cgroups v2: memory_stats.stats.inactive_file (cache n'existe plus)
    cache = (
        memory_stats.get("cache", 0)
        or memory_sub_stats.get("cache", 0)
        or memory_sub_stats.get("inactive_file", 0)
    )

    # Actual used memory
    used_memory = usage - cache if usage > cache else usage
    # Memory limit
    limit = memory_stats.get("limit", 0)

    if limit > 0:
        memory_percent = (used_memory / limit) * 100.0
        return round(min(memory_percent, 100.0), 2), used_memory, limit

    return 0.0, used_memory, limit


def calculate_network_io(stats_data: dict) -> dict:
    """
    Calcule les I/O réseau détaillées par interface.

    Retourne un dict structuré avec les totaux globaux et le détail
    par interface (bytes, packets, errors, drops).

    Args:
        stats_data: Données de stats Docker brutes

    Returns:
        Dict structuré :
        {
            "rx_bytes": int, "tx_bytes": int,
            "total_rx_errors": int, "total_tx_errors": int,
            "total_rx_dropped": int, "total_tx_dropped": int,
            "interfaces": [{"name": str, "rx_bytes": int, ...}, ...]
        }
    """
    networks = stats_data.get("networks", {})

    total_rx = 0
    total_tx = 0
    total_rx_errors = 0
    total_tx_errors = 0
    total_rx_dropped = 0
    total_tx_dropped = 0
    interfaces = []

    for iface_name, iface_stats in networks.items():
        rx_bytes = iface_stats.get("rx_bytes", 0)
        tx_bytes = iface_stats.get("tx_bytes", 0)
        rx_packets = iface_stats.get("rx_packets", 0)
        tx_packets = iface_stats.get("tx_packets", 0)
        rx_errors = iface_stats.get("rx_errors", 0)
        tx_errors = iface_stats.get("tx_errors", 0)
        rx_dropped = iface_stats.get("rx_dropped", 0)
        tx_dropped = iface_stats.get("tx_dropped", 0)

        total_rx += rx_bytes
        total_tx += tx_bytes
        total_rx_errors += rx_errors
        total_tx_errors += tx_errors
        total_rx_dropped += rx_dropped
        total_tx_dropped += tx_dropped

        interfaces.append({
            "name": iface_name,
            "rx_bytes": rx_bytes,
            "tx_bytes": tx_bytes,
            "rx_packets": rx_packets,
            "tx_packets": tx_packets,
            "rx_errors": rx_errors,
            "tx_errors": tx_errors,
            "rx_dropped": rx_dropped,
            "tx_dropped": tx_dropped,
        })

    return {
        "rx_bytes": total_rx,
        "tx_bytes": total_tx,
        "total_rx_errors": total_rx_errors,
        "total_tx_errors": total_tx_errors,
        "total_rx_dropped": total_rx_dropped,
        "total_tx_dropped": total_tx_dropped,
        "interfaces": interfaces,
    }


def _sum_blkio_entries(entries: list | None) -> tuple[int, int]:
    """
    Additionne les entrées read/write d'une liste blkio_stats.

    Args:
        entries: Liste d'entrées blkio (format [{"op": "read", "value": N}, ...])

    Returns:
        Tuple (total_read, total_write) en bytes
    """
    if not entries:
        return 0, 0

    total_read = 0
    total_write = 0

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        op = entry.get("op", "")
        if isinstance(op, str):
            op_lower = op.lower()
            if op_lower == "read":
                total_read += entry.get("value", 0) or 0
            elif op_lower == "write":
                total_write += entry.get("value", 0) or 0

    return total_read, total_write


def _build_device_stats(
    service_bytes_entries: list | None,
    serviced_entries: list | None,
) -> list[dict]:
    """
    Agrège les entrées blkio par device (major, minor) en combinant
    io_service_bytes_recursive (bytes) et io_serviced_recursive (IOPS).

    Args:
        service_bytes_entries: Liste d'entrées io_service_bytes_recursive
        serviced_entries: Liste d'entrées io_serviced_recursive

    Returns:
        Liste de dicts par device :
        [{"major": int, "minor": int, "read_bytes": int, "write_bytes": int,
          "read_ops": int, "write_ops": int}, ...]
    """
    devices: dict[tuple[int, int], dict[str, int]] = {}

    # Agréger io_service_bytes_recursive (bytes)
    for entry in service_bytes_entries or []:
        if not isinstance(entry, dict):
            continue
        major = entry.get("major", 0)
        minor = entry.get("minor", 0)
        key = (major, minor)
        if key not in devices:
            devices[key] = {
                "major": major, "minor": minor,
                "read_bytes": 0, "write_bytes": 0,
                "read_ops": 0, "write_ops": 0,
            }
        op = entry.get("op", "")
        value = entry.get("value", 0) or 0
        if isinstance(op, str):
            op_lower = op.lower()
            if op_lower == "read":
                devices[key]["read_bytes"] += value
            elif op_lower == "write":
                devices[key]["write_bytes"] += value

    # Agréger io_serviced_recursive (IOPS)
    for entry in serviced_entries or []:
        if not isinstance(entry, dict):
            continue
        major = entry.get("major", 0)
        minor = entry.get("minor", 0)
        key = (major, minor)
        if key not in devices:
            devices[key] = {
                "major": major, "minor": minor,
                "read_bytes": 0, "write_bytes": 0,
                "read_ops": 0, "write_ops": 0,
            }
        op = entry.get("op", "")
        value = entry.get("value", 0) or 0
        if isinstance(op, str):
            op_lower = op.lower()
            if op_lower == "read":
                devices[key]["read_ops"] += value
            elif op_lower == "write":
                devices[key]["write_ops"] += value

    return list(devices.values())


def calculate_block_io(stats_data: dict) -> dict:
    """
    Calcule les I/O disque détaillées par device (bytes + IOPS).

    Supporte cgroups v1 ET cgroups v2 :
    - cgroups v1 : io_service_bytes_recursive (principal)
    - cgroups v2 : io_service_bytes_recursive (Docker 25+) ou
                   throttle_io_service_bytes_recursive (fallback en bytes)

    Args:
        stats_data: Données de stats Docker brutes

    Returns:
        Dict structuré :
        {
            "read_bytes": int, "write_bytes": int,
            "devices": [{"major": int, "minor": int, "read_bytes": int,
                         "write_bytes": int, "read_ops": int, "write_ops": int}, ...]
        }
    """
    blkio_stats = stats_data.get("blkio_stats", {})

    # Entries principales
    service_bytes = blkio_stats.get("io_service_bytes_recursive")
    serviced = blkio_stats.get("io_serviced_recursive")

    # Construire les stats par device
    devices = _build_device_stats(service_bytes, serviced)

    # Si aucune donnée dans l'entrée principale, essayer le fallback
    if not devices:
        fallback_bytes = blkio_stats.get("throttle_io_service_bytes_recursive")
        devices = _build_device_stats(fallback_bytes, None)

    # Calculer les totaux globaux
    total_read = sum(d["read_bytes"] for d in devices)
    total_write = sum(d["write_bytes"] for d in devices)

    if total_read == 0 and total_write == 0:
        logger.debug(
            "[ContainerStats] No block I/O data available (all blkio fields are null/empty, "
            "possibly cgroups v2 with older Docker version)"
        )

    return {
        "read_bytes": total_read,
        "write_bytes": total_write,
        "devices": devices,
    }


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
    network_data = calculate_network_io(stats_data)
    block_data = calculate_block_io(stats_data)

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
        "network": network_data,
        "block_io": block_data,
    }


async def container_stats_websocket_endpoint(websocket: WebSocket, container_id: str):
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
            except Exception:
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
                        except Exception:
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
                except Exception:
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

        logger.info(f"[ContainerStats] WebSocket closed for container {container_id}")
