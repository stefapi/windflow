"""
Routes API REST pour Docker.

API pour gérer les ressources Docker locales (containers, images, volumes, networks, system).
Connexion via Unix socket /var/run/docker.sock.
"""

import logging
from typing import List, Optional

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...core.rate_limit import conditional_rate_limiter
from ...schemas.docker import (
    BatchContainerActionRequest,
    BatchContainerActionResponse,
    ContainerCreateRequest,
    ContainerDetailResponse,
    ContainerLogsResponse,
    ContainerProcess,
    ContainerProcessListResponse,
    ContainerResponse,
    ContainerStatsResponse,
    ImagePullRequest,
    ImagePullResponse,
    ImageResponse,
    NetworkResponse,
    PingResponse,
    SystemInfoResponse,
    SystemVersionResponse,
    VolumeCreateRequest,
    VolumeResponse,
)
from ...services.docker_client_service import get_docker_client

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# Containers
# =============================================================================


@router.get(
    "/containers",
    response_model=List[ContainerResponse],
    summary="List containers",
    description="List all Docker containers (running and stopped).",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def list_containers(
    request: Request,
    all: bool = True,
):
    """Liste tous les containers Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Listing Docker containers (all={all})",
        extra={"correlation_id": correlation_id},
    )

    try:
        client = await get_docker_client()
        containers = await client.list_containers(all=all)
        await client.close()

        return [
            ContainerResponse(
                id=c.id,
                name=c.name,
                image=c.image,
                image_id=c.image_id,
                command=c.command,
                created=c.created,
                state=c.state,
                status=c.status,
                ports=c.ports,
                labels=c.labels,
                networks=c.networks,
                mounts=c.mounts,
                restart_count=c.restart_count,
            )
            for c in containers
        ]

    except ConnectionError as e:
        logger.error(f"Docker not available: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Docker n'est pas disponible: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error listing containers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la liste des containers: {str(e)}",
        )


@router.get(
    "/containers/{container_id}",
    response_model=ContainerDetailResponse,
    summary="Inspect container",
    description="Get detailed information about a container.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def get_container(
    request: Request,
    container_id: str,
):
    """Récupère les détails d'un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting container {container_id}", extra={"correlation_id": correlation_id}
    )

    try:
        client = await get_docker_client()
        container = await client.get_container(container_id)
        await client.close()

        return ContainerDetailResponse(
            id=container.id,
            name=container.name,
            created=container.created,
            path=container.path,
            args=container.args,
            state=container.state,
            image=container.image,
            config=container.config,
            host_config=container.host_config,
            network_settings=container.network_settings,
            mounts=container.mounts,
        )

    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} non trouvé",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur Docker: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error getting container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération du container: {str(e)}",
        )


@router.post(
    "/containers",
    response_model=ContainerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create container",
    description="Create a new Docker container without starting it.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
)
async def create_container(
    request: Request,
    container_data: ContainerCreateRequest,
):
    """Crée un nouveau container Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Creating container {container_data.name}",
        extra={"correlation_id": correlation_id},
    )

    try:
        client = await get_docker_client()

        # Créer le container
        container_id = await client.create_container(
            name=container_data.name,
            image=container_data.image,
            command=container_data.command,
            env=container_data.env,
            ports=container_data.ports,
            volumes=container_data.volumes,
            labels=container_data.labels,
            restart_policy=container_data.restart_policy,
            network_mode=container_data.network_mode,
            privileged=container_data.privileged,
        )

        # Récupérer les détails
        container = await client.get_container(container_id)
        await client.close()

        return ContainerDetailResponse(
            id=container.id,
            name=container.name,
            created=container.created,
            path=container.path,
            args=container.args,
            state=container.state,
            image=container.image,
            config=container.config,
            host_config=container.host_config,
            network_settings=container.network_settings,
            mounts=container.mounts,
        )

    except aiohttp.ClientResponseError as e:
        if e.status == 409:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Container {container_data.name} existe déjà",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur Docker: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error creating container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création du container: {str(e)}",
        )


# =============================================================================
# Batch container actions (for discovered/unmanaged stacks)
# IMPORTANT: These routes MUST be defined BEFORE the {container_id} routes
# to avoid FastAPI matching "batch" as a container_id parameter.
# =============================================================================


@router.post(
    "/containers/batch/start",
    response_model=BatchContainerActionResponse,
    summary="Start multiple containers",
    description="Start a batch of containers by their IDs. Used for discovered stacks.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
)
async def batch_start_containers(
    request: Request,
    batch_data: BatchContainerActionRequest,
):
    """Démarre un ensemble de containers en une seule requête."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Batch starting {len(batch_data.container_ids)} containers",
        extra={"correlation_id": correlation_id},
    )

    affected = 0
    errors: list[str] = []

    try:
        client = await get_docker_client()
        try:
            for cid in batch_data.container_ids:
                try:
                    await client.start_container(cid)
                    affected += 1
                except aiohttp.ClientResponseError as e:
                    if e.status == 304:
                        affected += 1  # déjà démarré
                    elif e.status == 404:
                        errors.append(f"{cid}: non trouvé")
                    else:
                        errors.append(f"{cid}: {e}")
                except Exception as exc:
                    errors.append(f"{cid}: {exc}")
        finally:
            await client.close()
    except ConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Docker n'est pas disponible: {exc}",
        )

    message = f"{affected}/{len(batch_data.container_ids)} containers démarrés"
    if errors:
        message += f" — erreurs : {'; '.join(errors[:3])}"

    return BatchContainerActionResponse(
        success=len(errors) == 0,
        message=message,
        action="start",
        affected=affected,
        errors=errors,
    )


@router.post(
    "/containers/batch/stop",
    response_model=BatchContainerActionResponse,
    summary="Stop multiple containers",
    description="Stop a batch of containers by their IDs. Used for discovered stacks.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
)
async def batch_stop_containers(
    request: Request,
    batch_data: BatchContainerActionRequest,
):
    """Arrête un ensemble de containers en une seule requête."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Batch stopping {len(batch_data.container_ids)} containers",
        extra={"correlation_id": correlation_id},
    )

    affected = 0
    errors: list[str] = []

    try:
        client = await get_docker_client()
        try:
            for cid in batch_data.container_ids:
                try:
                    await client.stop_container(cid, timeout=10)
                    affected += 1
                except aiohttp.ClientResponseError as e:
                    if e.status == 304:
                        affected += 1  # déjà arrêté
                    elif e.status == 404:
                        errors.append(f"{cid}: non trouvé")
                    else:
                        errors.append(f"{cid}: {e}")
                except Exception as exc:
                    errors.append(f"{cid}: {exc}")
        finally:
            await client.close()
    except ConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Docker n'est pas disponible: {exc}",
        )

    message = f"{affected}/{len(batch_data.container_ids)} containers arrêtés"
    if errors:
        message += f" — erreurs : {'; '.join(errors[:3])}"

    return BatchContainerActionResponse(
        success=len(errors) == 0,
        message=message,
        action="stop",
        affected=affected,
        errors=errors,
    )


@router.post(
    "/containers/{container_id}/start",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Start container",
    description="Start a stopped container.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(50, 60))],
)
async def start_container(
    request: Request,
    container_id: str,
):
    """Démarre un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Starting container {container_id}", extra={"correlation_id": correlation_id}
    )

    try:
        client = await get_docker_client()
        await client.start_container(container_id)
        await client.close()

    except aiohttp.ClientResponseError as e:
        if e.status == 304:
            # Container déjà démarré
            pass
        elif e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} non trouvé",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur Docker: {str(e)}",
            )
    except Exception as e:
        logger.error(f"Error starting container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du démarrage: {str(e)}",
        )


@router.post(
    "/containers/{container_id}/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Stop container",
    description="Stop a running container.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(50, 60))],
)
async def stop_container(
    request: Request,
    container_id: str,
    timeout: int = 10,
):
    """Arrête un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Stopping container {container_id}", extra={"correlation_id": correlation_id}
    )

    try:
        client = await get_docker_client()
        await client.stop_container(container_id, timeout=timeout)
        await client.close()

    except aiohttp.ClientResponseError as e:
        if e.status == 304:
            # Container déjà arrêté
            pass
        elif e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} non trouvé",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur Docker: {str(e)}",
            )
    except Exception as e:
        logger.error(f"Error stopping container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'arrêt: {str(e)}",
        )


@router.post(
    "/containers/{container_id}/restart",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Restart container",
    description="Restart a container.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(50, 60))],
)
async def restart_container(
    request: Request,
    container_id: str,
    timeout: int = 10,
):
    """Redémarre un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Restarting container {container_id}", extra={"correlation_id": correlation_id}
    )

    try:
        client = await get_docker_client()
        await client.restart_container(container_id, timeout=timeout)
        await client.close()

    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} non trouvé",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur Docker: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error restarting container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du redémarrage: {str(e)}",
        )


@router.delete(
    "/containers/{container_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove container",
    description="Remove a container.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
)
async def remove_container(
    request: Request,
    container_id: str,
    force: bool = False,
):
    """Supprime un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Removing container {container_id} (force={force})",
        extra={"correlation_id": correlation_id},
    )

    try:
        client = await get_docker_client()
        await client.remove_container(container_id, force=force)
        await client.close()

    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} non trouvé",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur Docker: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error removing container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression: {str(e)}",
        )


@router.get(
    "/containers/{container_id}/shells",
    response_model=List[dict],
    summary="List available shells",
    description="Detect available shells in a container for terminal access.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(50, 60))],
)
async def get_container_shells(
    request: Request,
    container_id: str,
):
    """
    Détecte les shells disponibles dans un conteneur.

    Retourne une liste de shells avec leur chemin et disponibilité.
    """
    from ...services.terminal_service import TerminalService

    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Detecting shells in container {container_id}",
        extra={"correlation_id": correlation_id},
    )

    try:
        terminal_service = TerminalService()
        shells = await terminal_service.detect_shells(container_id)
        await terminal_service.close()

        return [
            {"path": shell.path, "label": shell.label, "available": shell.available}
            for shell in shells
        ]

    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} non trouvé",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur Docker: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error detecting shells: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la détection des shells: {str(e)}",
        )


@router.get(
    "/containers/{container_id}/stats",
    response_model=ContainerStatsResponse,
    summary="Get container stats snapshot",
    description="Get a single snapshot of container resource usage statistics.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def get_container_stats(
    request: Request,
    container_id: str,
):
    """Récupère un snapshot des statistiques d'un container."""
    from ...websocket.container_stats import format_stats_response

    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting stats snapshot for container {container_id}",
        extra={"correlation_id": correlation_id},
    )

    try:
        client = await get_docker_client()

        # Get single stats snapshot (stream=False)
        stats_data = await client.container_stats(container_id, stream=False)
        await client.close()

        # Format the response using existing helper
        return format_stats_response(container_id, stats_data)

    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} non trouvé",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur Docker: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error getting container stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des stats: {str(e)}",
        )


@router.get(
    "/containers/{container_id}/top",
    response_model=ContainerProcessListResponse,
    summary="List container processes",
    description="Get the list of processes running in a container.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def get_container_processes(
    request: Request,
    container_id: str,
    ps_args: Optional[str] = None,
):
    """Liste les processus d'un container."""
    from datetime import datetime, timezone

    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting processes for container {container_id}",
        extra={"correlation_id": correlation_id},
    )

    try:
        client = await get_docker_client()
        data = await client.list_processes(container_id, ps_args=ps_args)
        await client.close()

        # Parser la réponse Docker
        titles = data.get("Titles", [])
        processes_raw = data.get("Processes", [])

        # Mapping des titres vers nos champs
        def find_index(possible_names: List[str]) -> int:
            for name in possible_names:
                if name in titles:
                    return titles.index(name)
            return -1

        pid_idx = find_index(["PID", "pid"])
        user_idx = find_index(["USER", "user"])
        cpu_idx = find_index(["%CPU", "%Cpu", "cpu"])
        mem_idx = find_index(["%MEM", "%Mem", "mem"])
        time_idx = find_index(["TIME", "time"])
        cmd_idx = find_index(["COMMAND", "CMD", "command", "cmd"])

        processes = []
        for proc in processes_raw:

            def get_val(idx: int, default: str = "") -> str:
                if 0 <= idx < len(proc):
                    return proc[idx]
                return default

            def parse_float(val: str) -> float:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return 0.0

            def parse_int(val: str) -> int:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return 0

            processes.append(
                ContainerProcess(
                    pid=parse_int(get_val(pid_idx, "0")),
                    user=get_val(user_idx),
                    cpu=parse_float(get_val(cpu_idx, "0")),
                    mem=parse_float(get_val(mem_idx, "0")),
                    time=get_val(time_idx),
                    command=get_val(cmd_idx),
                )
            )

        return ContainerProcessListResponse(
            container_id=container_id,
            titles=titles,
            processes=processes,
            timestamp=datetime.now(timezone.utc),
        )

    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} non trouvé",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur Docker: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error getting container processes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des processus: {str(e)}",
        )


@router.get(
    "/containers/{container_id}/logs",
    summary="Get container logs",
    description="Get logs from a container.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def get_container_logs(
    request: Request,
    container_id: str,
    tail: int = 100,
    timestamps: bool = False,
):
    """Récupère les logs d'un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting logs for container {container_id}",
        extra={"correlation_id": correlation_id},
    )

    try:
        client = await get_docker_client()

        # Collecter les logs
        logs_lines = []
        async for line in client.container_logs(
            container_id=container_id,
            tail=tail,
            timestamps=timestamps,
        ):
            logs_lines.append(line)

        await client.close()

        logs_text = "\n".join(logs_lines)

        return ContainerLogsResponse(
            logs=logs_text,
            container_id=container_id,
        )

    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} non trouvé",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur Docker: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error getting container logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des logs: {str(e)}",
        )


# =============================================================================
# Images
# =============================================================================


@router.get(
    "/images",
    response_model=List[ImageResponse],
    summary="List images",
    description="List all Docker images.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def list_images(
    request: Request,
    all: bool = False,
):
    """Liste toutes les images Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Listing Docker images (all={all})", extra={"correlation_id": correlation_id}
    )

    try:
        client = await get_docker_client()
        images = await client.list_images(all=all)
        await client.close()

        return [
            ImageResponse(
                id=img.id,
                repo_tags=img.repo_tags,
                repo_digests=img.repo_digests,
                created=img.created,
                size=img.size,
                virtual_size=img.virtual_size,
                labels=img.labels,
            )
            for img in images
        ]

    except Exception as e:
        logger.error(f"Error listing images: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la liste des images: {str(e)}",
        )


@router.post(
    "/images/pull",
    response_model=ImagePullResponse,
    summary="Pull image",
    description="Pull an image from a registry.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
)
async def pull_image(
    request: Request,
    pull_data: ImagePullRequest,
):
    """Pull une image Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Pulling image {pull_data.name}:{pull_data.tag}",
        extra={"correlation_id": correlation_id},
    )

    last_status = ""
    last_id = None

    def on_progress(event):
        nonlocal last_status, last_id
        last_status = event.status
        last_id = event.id

    try:
        client = await get_docker_client()
        status = await client.pull_image(
            name=pull_data.name,
            tag=pull_data.tag,
            on_progress=on_progress,
        )
        await client.close()

        return ImagePullResponse(
            status=status,
            id=last_id,
        )

    except Exception as e:
        logger.error(f"Error pulling image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du pull: {str(e)}",
        )


@router.delete(
    "/images/{image_id}",
    summary="Remove image",
    description="Remove a Docker image.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
)
async def remove_image(
    request: Request,
    image_id: str,
    force: bool = False,
):
    """Supprime une image Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Removing image {image_id} (force={force})",
        extra={"correlation_id": correlation_id},
    )

    try:
        client = await get_docker_client()
        result = await client.remove_image(image_id, force=force)
        await client.close()

        return result

    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image {image_id} non trouvée",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur Docker: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error removing image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression: {str(e)}",
        )


# =============================================================================
# Volumes
# =============================================================================


@router.get(
    "/volumes",
    response_model=List[VolumeResponse],
    summary="List volumes",
    description="List all Docker volumes.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def list_volumes(request: Request):
    """Liste tous les volumes Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info("Listing Docker volumes", extra={"correlation_id": correlation_id})

    try:
        client = await get_docker_client()
        volumes = await client.list_volumes()
        await client.close()

        return [
            VolumeResponse(
                name=v.name,
                driver=v.driver,
                mountpoint=v.mountpoint,
                created_at=v.created_at,
                labels=v.labels,
                scope=v.scope,
            )
            for v in volumes
        ]

    except Exception as e:
        logger.error(f"Error listing volumes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la liste des volumes: {str(e)}",
        )


@router.post(
    "/volumes",
    response_model=VolumeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create volume",
    description="Create a new Docker volume.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
)
async def create_volume(
    request: Request,
    volume_data: VolumeCreateRequest,
):
    """Crée un nouveau volume Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Creating volume {volume_data.name}", extra={"correlation_id": correlation_id}
    )

    try:
        client = await get_docker_client()
        volume = await client.create_volume(
            name=volume_data.name,
            driver=volume_data.driver,
            labels=volume_data.labels,
        )
        await client.close()

        return VolumeResponse(
            name=volume.name,
            driver=volume.driver,
            mountpoint=volume.mountpoint,
            created_at=volume.created_at,
            labels=volume.labels,
            scope=volume.scope,
        )

    except aiohttp.ClientResponseError as e:
        if e.status == 409:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Volume {volume_data.name} existe déjà",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur Docker: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error creating volume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création: {str(e)}",
        )


@router.delete(
    "/volumes/{volume_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove volume",
    description="Remove a Docker volume.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
)
async def remove_volume(
    request: Request,
    volume_name: str,
    force: bool = False,
):
    """Supprime un volume Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Removing volume {volume_name} (force={force})",
        extra={"correlation_id": correlation_id},
    )

    try:
        client = await get_docker_client()
        await client.remove_volume(volume_name, force=force)
        await client.close()

    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Volume {volume_name} non trouvé",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur Docker: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error removing volume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression: {str(e)}",
        )


# =============================================================================
# Networks
# =============================================================================


@router.get(
    "/networks",
    response_model=List[NetworkResponse],
    summary="List networks",
    description="List all Docker networks.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def list_networks(request: Request):
    """Liste tous les réseaux Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info("Listing Docker networks", extra={"correlation_id": correlation_id})

    try:
        client = await get_docker_client()
        networks = await client.list_networks()
        await client.close()

        return [
            NetworkResponse(
                id=n.id,
                name=n.name,
                driver=n.driver,
                scope=n.scope,
                internal=n.internal,
                attachable=n.attachable,
                ingress=n.ingress,
                created=n.created,
                subnet=n.subnet,
                gateway=n.gateway,
            )
            for n in networks
        ]

    except Exception as e:
        logger.error(f"Error listing networks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la liste des réseaux: {str(e)}",
        )


# =============================================================================
# System
# =============================================================================


@router.get(
    "/system/info",
    response_model=SystemInfoResponse,
    summary="Get system info",
    description="Get Docker system information.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(50, 60))],
)
async def get_system_info(request: Request):
    """Récupère les informations système Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info("Getting Docker system info", extra={"correlation_id": correlation_id})

    try:
        client = await get_docker_client()
        info = await client.system_info()
        await client.close()

        return SystemInfoResponse(
            id=info.id,
            name=info.name,
            server_version=info.server_version,
            containers=info.containers,
            containers_running=info.containers_running,
            containers_paused=info.containers_paused,
            containers_stopped=info.containers_stopped,
            images=info.images,
            driver=info.driver,
            docker_root_dir=info.docker_root_dir,
            kernel_version=info.kernel_version,
            operating_system=info.operating_system,
            os_type=info.os_type,
            architecture=info.architecture,
            cpus=info.cpus,
            memory=info.memory,
        )

    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des infos: {str(e)}",
        )


@router.get(
    "/system/version",
    response_model=SystemVersionResponse,
    summary="Get version",
    description="Get Docker version information.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(50, 60))],
)
async def get_version(request: Request):
    """Récupère la version Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info("Getting Docker version", extra={"correlation_id": correlation_id})

    try:
        client = await get_docker_client()
        version = await client.system_version()
        await client.close()

        return SystemVersionResponse(
            version=version.get("Version", ""),
            api_version=version.get("ApiVersion", ""),
            min_api_version=version.get("MinAPIVersion", ""),
            git_commit=version.get("GitCommit", ""),
            go_version=version.get("GoVersion", ""),
            os=version.get("Os", ""),
            arch=version.get("Arch", ""),
            kernel_version=version.get("KernelVersion", ""),
            build_time=version.get("BuildTime", ""),
        )

    except Exception as e:
        logger.error(f"Error getting version: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de la version: {str(e)}",
        )


@router.get(
    "/system/ping",
    response_model=PingResponse,
    summary="Ping Docker",
    description="Test Docker connectivity.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def ping(request: Request):
    """Teste la connexion Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info("Pinging Docker", extra={"correlation_id": correlation_id})

    try:
        client = await get_docker_client()
        available = await client.ping()
        await client.close()

        return PingResponse(
            available=available,
            message="Docker is available" if available else "Docker is not available",
        )

    except ConnectionError:
        return PingResponse(
            available=False,
            message="Docker socket not accessible",
        )
    except Exception as e:
        logger.error(f"Error pinging Docker: {e}")
        return PingResponse(
            available=False,
            message=f"Error: {str(e)}",
        )
