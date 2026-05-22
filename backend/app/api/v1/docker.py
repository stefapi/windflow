"""
Routes API REST pour Docker.

API pour gérer les ressources Docker locales (containers, images, volumes, networks, system).
Connexion via Unix socket /var/run/docker.sock.
"""

import logging
from typing import Any, List, Optional

import aiohttp
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import get_current_active_user
from ...core.rate_limit import conditional_rate_limiter
from ...database import get_db
from ...models.user import User
from ...schemas.docker import (
    BatchContainerActionRequest,
    BatchContainerActionResponse,
    ContainerConfigInfo,
    ContainerCreateRequest,
    ContainerDetailResponse,
    ContainerHostConfigInfo,
    ContainerLogsResponse,
    ContainerNetworkConnectRequest,
    ContainerNetworkDisconnectRequest,
    ContainerNetworkSettingsInfo,
    ContainerProcess,
    ContainerProcessListResponse,
    ContainerPromoteRequest,
    ContainerPromoteResponse,
    ContainerRecreateRequest,
    ContainerRecreateResponse,
    ContainerRenameRequest,
    ContainerRenameResponse,
    ContainerResponse,
    ContainerShellResponse,
    ContainerStateInfo,
    ContainerStatsResponse,
    ContainerUpdateResourcesRequest,
    ContainerUpdateRestartPolicyRequest,
    ContainerUpdateResponse,
    ImageDetailResponse,
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
from ...schemas.stack import StackCreate
from ...services.docker_client_service import get_docker_client
from ...services.stack_service import StackService

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# Containers
# =============================================================================


@router.get(
    "/containers",
    response_model=List[ContainerResponse],
    summary="List containers",
    description="List all Docker containers (running and stopped). Supports pagination with skip and limit parameters.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def list_containers(
    request: Request,
    all: bool = True,
    skip: int = Query(0, ge=0, description="Nombre d'éléments à sauter"),
    limit: int = Query(50, ge=1, le=100, description="Nombre maximal d'éléments à retourner"),
    current_user: User = Depends(get_current_active_user),
):
    """Liste tous les containers Docker avec pagination."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Listing Docker containers (all={all}, skip={skip}, limit={limit})",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:
        containers = await client.list_containers(all=all)

        return [
            ContainerResponse(  # type: ignore[call-arg]
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
        ][skip : skip + limit]

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
    finally:
        await client.close()


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
    current_user: User = Depends(get_current_active_user),
):
    """Récupère les détails d'un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting container {container_id}", extra={"correlation_id": correlation_id}
    )

    client = await get_docker_client()
    try:
        container = await client.get_container(container_id)

        return ContainerDetailResponse(
            id=container.id,
            name=container.name,
            created=container.created,
            path=container.path,
            args=container.args,
            state=ContainerStateInfo.from_docker_dict(container.state),
            image=container.image,
            config=ContainerConfigInfo.from_docker_dict(container.config),
            host_config=ContainerHostConfigInfo.from_docker_dict(container.host_config),
            network_settings=ContainerNetworkSettingsInfo.from_docker_dict(container.network_settings),
            mounts=container.mounts,
            size_rw=container.size_rw,
            size_root_fs=container.size_root_fs,
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
    finally:
        await client.close()


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
    current_user: User = Depends(get_current_active_user),
):
    """Crée un nouveau container Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Creating container {container_data.name}",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:

        # Créer le container
        container_id = await client.create_container(
            name=container_data.name,
            image=container_data.image,
            command=container_data.command,
            env=container_data.env,
            ports=container_data.ports,
            volumes=container_data.volumes,  # type: ignore[arg-type]
            labels=container_data.labels,
            restart_policy=container_data.restart_policy,
            network_mode=container_data.network_mode,
            privileged=container_data.privileged,
        )

        # Récupérer les détails
        container = await client.get_container(container_id)

        return ContainerDetailResponse(  # type: ignore[call-arg]
            id=container.id,
            name=container.name,
            created=container.created,
            path=container.path,
            args=container.args,
            state=ContainerStateInfo.from_docker_dict(container.state),
            image=container.image,
            config=ContainerConfigInfo.from_docker_dict(container.config),
            host_config=ContainerHostConfigInfo.from_docker_dict(container.host_config),
            network_settings=ContainerNetworkSettingsInfo.from_docker_dict(container.network_settings),
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
    finally:
        await client.close()


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
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
):
    """Démarre un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Starting container {container_id}", extra={"correlation_id": correlation_id}
    )

    client = await get_docker_client()
    try:
        await client.start_container(container_id)

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
    finally:
        await client.close()


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
    current_user: User = Depends(get_current_active_user),
):
    """Arrête un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Stopping container {container_id}", extra={"correlation_id": correlation_id}
    )

    client = await get_docker_client()
    try:
        await client.stop_container(container_id, timeout=timeout)

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
    finally:
        await client.close()


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
    current_user: User = Depends(get_current_active_user),
):
    """Redémarre un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Restarting container {container_id}", extra={"correlation_id": correlation_id}
    )

    client = await get_docker_client()
    try:
        await client.restart_container(container_id, timeout=timeout)

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
    finally:
        await client.close()


@router.post(
    "/containers/{container_id}/pause",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Pause container",
    description="Pause a running container.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(50, 60))],
)
async def pause_container(
    request: Request,
    container_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Met en pause un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Pausing container {container_id}", extra={"correlation_id": correlation_id}
    )

    client = await get_docker_client()
    try:
        await client.pause_container(container_id)

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
        logger.error(f"Error pausing container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise en pause: {str(e)}",
        )
    finally:
        await client.close()


@router.post(
    "/containers/{container_id}/unpause",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unpause container",
    description="Unpause a paused container.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(50, 60))],
)
async def unpause_container(
    request: Request,
    container_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Reprend un container en pause."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Unpausing container {container_id}", extra={"correlation_id": correlation_id}
    )

    client = await get_docker_client()
    try:
        await client.unpause_container(container_id)

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
        logger.error(f"Error unpausing container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la reprise: {str(e)}",
        )
    finally:
        await client.close()


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
    current_user: User = Depends(get_current_active_user),
):
    """Supprime un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Removing container {container_id} (force={force})",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:
        await client.remove_container(container_id, force=force)

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
    finally:
        await client.close()


@router.post(
    "/containers/{container_id}/recreate",
    response_model=ContainerRecreateResponse,
    summary="Recreate container",
    description=(
        "Recreate a container with updated configuration. "
        "Stops, removes, and recreates the container. "
        "None fields preserve the current value. "
        "Named volumes and bind mounts are preserved."
    ),
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
)
async def recreate_container(
    request: Request,
    container_id: str,
    recreate_data: ContainerRecreateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Recrée un container avec une nouvelle configuration."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Recreating container {container_id}",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:
        new_id, new_detail = await client.recreate_container(
            container_id=container_id,
            image=recreate_data.image,
            pull_image=recreate_data.pull_image,
            env=recreate_data.env,
            labels=recreate_data.labels,
            port_bindings=recreate_data.port_bindings,
            mounts=recreate_data.mounts,
            privileged=recreate_data.privileged,
            readonly_rootfs=recreate_data.readonly_rootfs,
            cap_add=recreate_data.cap_add,
            cap_drop=recreate_data.cap_drop,
            stop_timeout=recreate_data.stop_timeout,
        )

        container_response = ContainerDetailResponse(
            id=new_detail.id,
            name=new_detail.name,
            created=new_detail.created,
            path=new_detail.path,
            args=new_detail.args,
            state=ContainerStateInfo.from_docker_dict(new_detail.state),
            image=new_detail.image,
            config=ContainerConfigInfo.from_docker_dict(new_detail.config),
            host_config=ContainerHostConfigInfo.from_docker_dict(new_detail.host_config),
            network_settings=ContainerNetworkSettingsInfo.from_docker_dict(new_detail.network_settings),
            mounts=new_detail.mounts,
            size_rw=new_detail.size_rw,
            size_root_fs=new_detail.size_root_fs,
        )

        return ContainerRecreateResponse(
            success=True,
            message=f"Container {container_id} recréé avec succès en {new_id}",
            old_container_id=container_id,
            new_container_id=new_id,
            container=container_response,
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
    except RuntimeError as e:
        # Chemin critique : container supprimé mais recréation échouée
        logger.critical(
            f"Critical recreate failure for {container_id}: {e}",
            extra={"correlation_id": correlation_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Container {container_id} supprimé mais la recréation a échoué: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error recreating container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recréation du container: {str(e)}",
        )
    finally:
        await client.close()


@router.patch(
    "/containers/{container_id}/restart-policy",
    response_model=ContainerUpdateResponse,
    summary="Update container restart policy",
    description="Update the restart policy of a container without recreation.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
)
async def update_restart_policy(
    request: Request,
    container_id: str,
    update_data: ContainerUpdateRestartPolicyRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Met à jour la politique de redémarrage d'un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Updating restart policy for container {container_id}: {update_data.name}",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:
        restart_policy: dict[str, Any] = {"Name": update_data.name}
        if update_data.maximum_retry_count is not None:
            restart_policy["MaximumRetryCount"] = update_data.maximum_retry_count

        update_config = {"RestartPolicy": restart_policy}
        result = await client.update_container(container_id, update_config)

        return ContainerUpdateResponse(warnings=result.get("Warnings") or [])

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
        logger.error(f"Error updating restart policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour: {str(e)}",
        )
    finally:
        await client.close()


@router.patch(
    "/containers/{container_id}/resources",
    response_model=ContainerUpdateResponse,
    summary="Update container resources",
    description="Update resource limits of a container without recreation.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
)
async def update_resources(
    request: Request,
    container_id: str,
    update_data: ContainerUpdateResourcesRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Met à jour les limites de ressources d'un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Updating resources for container {container_id}",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:
        resources: dict[str, Any] = {}
        if update_data.memory_limit is not None:
            resources["Memory"] = update_data.memory_limit
        if update_data.cpu_shares is not None:
            resources["CpuShares"] = update_data.cpu_shares
        if update_data.pids_limit is not None:
            resources["PidsLimit"] = update_data.pids_limit

        update_config = {"Resources": resources}
        result = await client.update_container(container_id, update_config)

        return ContainerUpdateResponse(warnings=result.get("Warnings") or [])

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
        logger.error(f"Error updating resources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour: {str(e)}",
        )
    finally:
        await client.close()


@router.post(
    "/containers/{container_id}/rename",
    response_model=ContainerRenameResponse,
    summary="Rename container",
    description="Rename a container.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
)
async def rename_container(
    request: Request,
    container_id: str,
    rename_data: ContainerRenameRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Renomme un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Renaming container {container_id} to {rename_data.new_name}",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:
        await client.rename_container(container_id, rename_data.new_name)

        return ContainerRenameResponse(
            success=True,
            message=f"Container renommé en {rename_data.new_name}",
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
        logger.error(f"Error renaming container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du renommage: {str(e)}",
        )
    finally:
        await client.close()


@router.post(
    "/containers/{container_id}/networks/connect",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Connect container to network",
    description="Connect a container to a Docker network at runtime.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
)
async def connect_container_to_network(
    request: Request,
    container_id: str,
    connect_data: ContainerNetworkConnectRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Connecte un container à un réseau Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Connecting container {container_id} to network {connect_data.network_id}",
        extra={
            "correlation_id": correlation_id,
            "container_id": container_id,
            "network_id": connect_data.network_id,
        },
    )

    client = await get_docker_client()
    try:
        await client.connect_container_to_network(
            network_id=connect_data.network_id,
            container_id=container_id,
            aliases=connect_data.aliases,
            ipv4_address=connect_data.ipv4_address,
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} ou réseau {connect_data.network_id} non trouvé",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur Docker: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error connecting container to network: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la connexion au réseau: {str(e)}",
        )
    finally:
        await client.close()


@router.post(
    "/containers/{container_id}/networks/disconnect",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Disconnect container from network",
    description="Disconnect a container from a Docker network at runtime.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
)
async def disconnect_container_from_network(
    request: Request,
    container_id: str,
    disconnect_data: ContainerNetworkDisconnectRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Déconnecte un container d'un réseau Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Disconnecting container {container_id} from network {disconnect_data.network_id}",
        extra={
            "correlation_id": correlation_id,
            "container_id": container_id,
            "network_id": disconnect_data.network_id,
        },
    )

    client = await get_docker_client()
    try:
        await client.disconnect_container_from_network(
            network_id=disconnect_data.network_id,
            container_id=container_id,
            force=disconnect_data.force,
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} ou réseau {disconnect_data.network_id} non trouvé",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur Docker: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error disconnecting container from network: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la déconnexion du réseau: {str(e)}",
        )
    finally:
        await client.close()


@router.post(
    "/containers/{container_id}/promote",
    response_model=ContainerPromoteResponse,
    summary="Promote container to stack",
    description="Promote a standalone container to a WindFlow managed stack.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
)
async def promote_container(
    request: Request,
    container_id: str,
    promote_data: ContainerPromoteRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """Promeut un container standalone en stack WindFlow managée."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Promoting container {container_id} to stack '{promote_data.name}'",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "container_id": container_id,
        },
    )

    client = await get_docker_client()
    try:
        # 1. Inspect the container via Docker API
        container_info = await client.inspect_container(container_id)

        # 2. Check if container is already managed
        labels = container_info.get("Config", {}).get("Labels") or {}
        if labels.get("windflow.managed"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ce container est déjà managé par WindFlow",
            )

        # 3. Build Compose template from container config
        host_config = container_info.get("HostConfig", {})
        container_config = container_info.get("Config", {})

        service_def: dict[str, Any] = {}

        # Image
        image = container_config.get("Image")
        if image:
            service_def["image"] = image

        # Environment variables
        env_list = container_config.get("Env")
        if env_list:
            service_def["environment"] = env_list

        # Ports
        port_bindings = host_config.get("PortBindings") or {}
        if port_bindings:
            ports: list[str] = []
            for container_port, bindings in port_bindings.items():
                port_parts = container_port.split("/")
                container_port_num = port_parts[0]
                if bindings and len(bindings) > 0:
                    host_port = bindings[0].get("HostPort", "")
                    if host_port:
                        ports.append(f"{host_port}:{container_port_num}")
                    else:
                        ports.append(container_port_num)
                else:
                    ports.append(container_port_num)
            if ports:
                service_def["ports"] = ports

        # Volumes
        binds = host_config.get("Binds")
        if binds:
            service_def["volumes"] = binds

        # Restart policy
        restart_policy = host_config.get("RestartPolicy", {})
        rp_name = restart_policy.get("Name")
        if rp_name and rp_name != "":
            rp_entry: dict[str, Any] = {"condition": rp_name}
            max_retry = restart_policy.get("MaximumRetryCount")
            if max_retry:
                rp_entry["max_attempts"] = max_retry
            service_def["restart"] = rp_entry

        # Resources
        memory = host_config.get("Memory")
        cpu_shares = host_config.get("CpuShares")
        pids_limit = host_config.get("PidsLimit")
        deploy: dict[str, Any] = {}
        if memory and memory > 0:
            deploy.setdefault("resources", {}).setdefault("limits", {})["memory"] = memory
        if cpu_shares and cpu_shares > 0:
            deploy.setdefault("resources", {}).setdefault("limits", {})["cpus"] = cpu_shares / 1024
        if pids_limit and pids_limit > 0:
            deploy.setdefault("resources", {}).setdefault("limits", {})["pids"] = pids_limit
        if deploy:
            service_def["deploy"] = deploy

        # Container name as service key
        container_name = container_info.get("Name", "").lstrip("/") or "service"
        # Sanitize name for compose service key
        import re
        service_key = container_name.replace("_", "-").replace(".", "-").lower()
        # Ensure it starts with alphanumeric
        service_key = re.sub(r"[^a-z0-9-]", "", service_key)
        if not service_key or not service_key[0].isalnum():
            service_key = f"svc-{service_key}"
        if not service_key:
            service_key = "service"

        compose_template: dict[str, Any] = {
            "version": "3.8",
            "services": {
                service_key: service_def,
            },
        }

        # 4. Check name uniqueness
        existing = await StackService.get_by_name(
            session, promote_data.name, str(current_user.organization_id)
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Une stack avec le nom '{promote_data.name}' existe déjà",
            )

        # 5. Create the stack
        stack_data = StackCreate(  # type: ignore[call-arg]
            name=promote_data.name,
            description=f"Stack promue depuis le container {container_name}",
            template=compose_template,
            variables={},
            organization_id=str(current_user.organization_id),
        )
        stack = await StackService.create(session, stack_data)

        logger.info(
            f"Container {container_id} promoted to stack {stack.id}",
            extra={
                "correlation_id": correlation_id,
                "user_id": str(current_user.id),
                "container_id": container_id,
                "stack_id": str(stack.id),
            },
        )

        return ContainerPromoteResponse(
            success=True,
            message=f"Container promu en stack '{promote_data.name}'",
            stack_id=str(stack.id),
            stack_name=stack.name,
        )

    except HTTPException:
        raise
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
        logger.error(f"Error promoting container: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la promotion: {str(e)}",
        )
    finally:
        await client.close()


@router.get(
    "/containers/{container_id}/shells",
    response_model=List[ContainerShellResponse],
    summary="List available shells",
    description="Detect available shells in a container for terminal access.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(50, 60))],
)
async def get_container_shells(
    request: Request,
    container_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Détecte les shells disponibles dans un conteneur.

    Retourne une liste de shells avec leur chemin et disponibilité.
    Nécessite une authentification valide.
    """
    from ...services.terminal_service import TerminalService

    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Detecting shells in container {container_id}",
        extra={"correlation_id": correlation_id, "user_id": str(current_user.id)},
    )

    try:
        terminal_service = TerminalService()
        shells = await terminal_service.detect_shells(container_id)
        await terminal_service.close()

        return [
            ContainerShellResponse(
                path=shell.path, label=shell.label, available=shell.available
            )
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
    current_user: User = Depends(get_current_active_user),
):
    """Récupère un snapshot des statistiques d'un container."""
    from ...websocket.container_stats import format_stats_response

    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting stats snapshot for container {container_id}",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:

        # Get single stats snapshot (stream=False)
        # container_stats() is an async generator — consume first item
        stats_gen = client.container_stats(container_id, stream=False)
        stats_data = await anext(stats_gen)

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
    finally:
        await client.close()


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
    current_user: User = Depends(get_current_active_user),
):
    """Liste les processus d'un container."""
    from datetime import datetime, timezone

    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting processes for container {container_id}",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:
        data = await client.list_processes(container_id, ps_args=ps_args)

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
    finally:
        await client.close()


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
    current_user: User = Depends(get_current_active_user),
):
    """Récupère les logs d'un container."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting logs for container {container_id}",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:

        # Collecter les logs
        logs_lines = []
        async for line in client.container_logs(
            container_id=container_id,
            tail=tail,
            timestamps=timestamps,
        ):
            logs_lines.append(line)

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
    finally:
        await client.close()


# =============================================================================
# Images
# =============================================================================


@router.get(
    "/images",
    response_model=List[ImageResponse],
    summary="List images",
    description="List all Docker images. Supports pagination with skip and limit parameters.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def list_images(
    request: Request,
    all: bool = False,
    skip: int = Query(0, ge=0, description="Nombre d'éléments à sauter"),
    limit: int = Query(50, ge=1, le=100, description="Nombre maximal d'éléments à retourner"),
    current_user: User = Depends(get_current_active_user),
):
    """Liste toutes les images Docker avec indicateur d'utilisation par containers et pagination."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Listing Docker images (all={all}, skip={skip}, limit={limit})",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:
        images = await client.list_images(all=all)

        # Récupérer les containers pour calculer l'utilisation des images
        containers = await client.list_containers(all=True)

        # Construire un mapping image_id_short → count
        # ContainerInfo.image_id est au format "sha256:abc123..." (complet)
        # ImageInfo.id est tronqué à 12 chars sans prefix "sha256:"
        image_usage: dict[str, int] = {}
        for c in containers:
            normalized_id = c.image_id.replace("sha256:", "")[:12]
            image_usage[normalized_id] = image_usage.get(normalized_id, 0) + 1

        return [
            ImageResponse(  # type: ignore[call-arg]
                id=img.id,
                repo_tags=img.repo_tags,
                repo_digests=img.repo_digests,
                created=img.created,
                size=img.size,
                virtual_size=img.virtual_size,
                labels=img.labels,
                in_use=image_usage.get(img.id, 0) > 0,
                containers_count=image_usage.get(img.id, 0),
            )
            for img in images
        ][skip : skip + limit]

    except Exception as e:
        logger.error(f"Error listing images: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la liste des images: {str(e)}",
        )
    finally:
        await client.close()


@router.get(
    "/images/{image_id}",
    response_model=ImageDetailResponse,
    summary="Inspect image",
    description="Get detailed information about a Docker image.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def get_image(
    request: Request,
    image_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Inspecte une image Docker et retourne ses détails."""
    from datetime import datetime, timezone

    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Inspecting image {image_id}",
        extra={"correlation_id": correlation_id, "image_id": image_id},
    )

    client = await get_docker_client()
    try:
        data = await client.inspect_image(image_id)

        # Parser le dict Docker pour peupler ImageDetailResponse
        config = data.get("Config", {}) or {}

        # Parser la date de création (format ISO 8601 Docker)
        created_str = data.get("Created", "")
        if created_str:
            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        else:
            created = datetime.now(timezone.utc)

        return ImageDetailResponse(  # type: ignore[call-arg]
            id=data.get("Id", "").replace("sha256:", "")[:12],
            repo_tags=data.get("RepoTags", []),
            repo_digests=data.get("RepoDigests", []),
            created=created,
            size=data.get("Size", 0),
            virtual_size=data.get("VirtualSize", 0),
            labels=config.get("Labels", {}) or {},
            architecture=data.get("Architecture", ""),
            os=data.get("Os", ""),
            author=data.get("Author", ""),
            docker_version=data.get("DockerVersion", ""),
            cmd=config.get("Cmd"),
            entrypoint=config.get("Entrypoint"),
            env=config.get("Env"),
            exposed_ports=config.get("ExposedPorts"),
            config=config if config else None,
        )

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
        logger.error(f"Error inspecting image {image_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'inspection de l'image: {str(e)}",
        )
    finally:
        await client.close()


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
    current_user: User = Depends(get_current_active_user),
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

    client = await get_docker_client()
    try:
        pull_status = await client.pull_image(
            name=pull_data.name,
            tag=pull_data.tag,
            on_progress=on_progress,
        )

        return ImagePullResponse(  # type: ignore[call-arg]
            status=pull_status,
            id=last_id,
        )

    except Exception as e:
        logger.error(f"Error pulling image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du pull: {str(e)}",
        )
    finally:
        await client.close()


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
    current_user: User = Depends(get_current_active_user),
):
    """Supprime une image Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Removing image {image_id} (force={force})",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:
        result = await client.remove_image(image_id, force=force)

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
    finally:
        await client.close()


@router.post(
    "/images/load",
    summary="Load image",
    description="Load a Docker image from a tar archive.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
)
async def load_image(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Importe une image Docker depuis un fichier tar."""
    correlation_id = getattr(request.state, "correlation_id", None)

    # Valider le type MIME
    content_type = file.content_type or ""
    if content_type not in (
        "application/x-tar",
        "application/octet-stream",
        "application/gzip",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Type de fichier non supporté: {content_type}. "
            "Attendu: application/x-tar ou application/octet-stream",
        )

    try:
        tar_bytes = await file.read()
        logger.info(
            "image_load",
            extra={
                "correlation_id": correlation_id,
                "file_name": file.filename,
                "size": len(tar_bytes),
            },
        )

        client = await get_docker_client()
        try:
            status_msg = await client.load_image(tar_bytes)
        finally:
            await client.close()

        return {"success": True, "message": status_msg}

    except Exception as e:
        logger.error(f"Error loading image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement de l'image: {str(e)}",
        )


@router.get(
    "/images/{image_id}/save",
    summary="Save image",
    description="Export a Docker image as a tar archive.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
)
async def save_image(
    request: Request,
    image_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Exporte une image Docker au format tar."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "image_save",
        extra={"correlation_id": correlation_id, "image_id": image_id},
    )

    client = await get_docker_client()
    try:
        tar_bytes = await client.save_image(image_id)

        logger.info(
            "image_save_complete",
            extra={
                "correlation_id": correlation_id,
                "image_id": image_id,
                "size": len(tar_bytes),
            },
        )

        return Response(
            content=tar_bytes,
            media_type="application/x-tar",
            headers={
                "Content-Disposition": f"attachment; filename={image_id}.tar"
            },
        )

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
        logger.error(f"Error saving image {image_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'export de l'image: {str(e)}",
        )
    finally:
        await client.close()


# =============================================================================
# Volumes
# =============================================================================


@router.get(
    "/volumes",
    response_model=List[VolumeResponse],
    summary="List volumes",
    description="List all Docker volumes. Supports pagination with skip and limit parameters.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def list_volumes(
    request: Request,
    skip: int = Query(0, ge=0, description="Nombre d'éléments à sauter"),
    limit: int = Query(50, ge=1, le=100, description="Nombre maximal d'éléments à retourner"),
    current_user: User = Depends(get_current_active_user),
):
    """Liste tous les volumes Docker avec pagination."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Listing Docker volumes (skip={skip}, limit={limit})",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:
        volumes = await client.list_volumes()

        return [
            VolumeResponse(  # type: ignore[call-arg]
                name=v.name,
                driver=v.driver,
                mountpoint=v.mountpoint,
                created_at=v.created_at,
                labels=v.labels,
                scope=v.scope,
            )
            for v in volumes
        ][skip : skip + limit]

    except Exception as e:
        logger.error(f"Error listing volumes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la liste des volumes: {str(e)}",
        )
    finally:
        await client.close()


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
    current_user: User = Depends(get_current_active_user),
):
    """Crée un nouveau volume Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Creating volume {volume_data.name}", extra={"correlation_id": correlation_id}
    )

    client = await get_docker_client()
    try:
        volume = await client.create_volume(
            name=volume_data.name,
            driver=volume_data.driver,
            labels=volume_data.labels,
        )

        return VolumeResponse(  # type: ignore[call-arg]
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
    finally:
        await client.close()


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
    current_user: User = Depends(get_current_active_user),
):
    """Supprime un volume Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Removing volume {volume_name} (force={force})",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:
        await client.remove_volume(volume_name, force=force)

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
    finally:
        await client.close()


# =============================================================================
# Networks
# =============================================================================


@router.get(
    "/networks",
    response_model=List[NetworkResponse],
    summary="List networks",
    description="List all Docker networks. Supports pagination with skip and limit parameters.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def list_networks(
    request: Request,
    skip: int = Query(0, ge=0, description="Nombre d'éléments à sauter"),
    limit: int = Query(50, ge=1, le=100, description="Nombre maximal d'éléments à retourner"),
    current_user: User = Depends(get_current_active_user),
):
    """Liste tous les réseaux Docker avec pagination."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Listing Docker networks (skip={skip}, limit={limit})",
        extra={"correlation_id": correlation_id},
    )

    client = await get_docker_client()
    try:
        networks = await client.list_networks()

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
        ][skip : skip + limit]

    except Exception as e:
        logger.error(f"Error listing networks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la liste des réseaux: {str(e)}",
        )
    finally:
        await client.close()


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
async def get_system_info(request: Request, current_user: User = Depends(get_current_active_user)):
    """Récupère les informations système Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info("Getting Docker system info", extra={"correlation_id": correlation_id})

    client = await get_docker_client()
    try:
        info = await client.system_info()

        return SystemInfoResponse(  # type: ignore[call-arg]
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
    finally:
        await client.close()


@router.get(
    "/system/version",
    response_model=SystemVersionResponse,
    summary="Get version",
    description="Get Docker version information.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(50, 60))],
)
async def get_version(request: Request, current_user: User = Depends(get_current_active_user)):
    """Récupère la version Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info("Getting Docker version", extra={"correlation_id": correlation_id})

    client = await get_docker_client()
    try:
        version = await client.system_version()

        return SystemVersionResponse(  # type: ignore[call-arg]
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
    finally:
        await client.close()


@router.get(
    "/system/ping",
    response_model=PingResponse,
    summary="Ping Docker",
    description="Test Docker connectivity.",
    tags=["docker"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def ping(request: Request, current_user: User = Depends(get_current_active_user)):
    """Teste la connexion Docker."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info("Pinging Docker", extra={"correlation_id": correlation_id})

    client = await get_docker_client()
    try:
        available = await client.ping()

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
    finally:
        await client.close()
