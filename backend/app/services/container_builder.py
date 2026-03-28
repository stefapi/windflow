"""
Builders d'objets domaine pour le module Compute.

Construction des objets Pydantic (StackWithServices, DiscoveredItem,
StandaloneContainer, TargetGroup) à partir des données brutes DB + Docker.
"""

import logging
from typing import Optional

from ..models.deployment import Deployment, DeploymentStatus
from ..models.target import Target
from ..schemas.compute import (
    DiscoveredItem,
    ServiceWithMetrics,
    StackWithServices,
    StandaloneContainer,
    TargetGroup,
    TargetMetrics,
)
from ..services.docker_client_service import DockerClientService, ContainerInfo
from ..services.container_classifier import (
    LABEL_COMPOSE_PROJECT,
    LABEL_COMPOSE_CONFIG_FILES,
    LOCAL_TARGET_ID,
    LOCAL_TARGET_NAME,
)
from ..helper.compute_helpers import extract_uptime, parse_ports

logger = logging.getLogger(__name__)


async def _build_service_with_metrics(
    c: ContainerInfo,
    docker_for_health: Optional[DockerClientService] = None,
) -> ServiceWithMetrics:
    """
    Construit un ServiceWithMetrics enrichi depuis un ContainerInfo.

    Extrait uptime, ports et health_status quand les données sont disponibles.
    Graceful degradation : en cas d'erreur d'inspection, les champs optionnels
    restent à leur valeur par défaut.

    Args:
        c: ContainerInfo brut depuis Docker.
        docker_for_health: Client Docker pour inspection health (optionnel).

    Returns:
        ServiceWithMetrics avec uptime, ports et health_status.
    """
    uptime = extract_uptime(c.status)
    ports = parse_ports(c.ports)
    health_status: Optional[str] = None

    if c.state == "running" and docker_for_health:
        try:
            detail = await docker_for_health.inspect_container(c.id)
            state_info = detail.get("State", {})
            health_info = state_info.get("Health", {})
            if health_info:
                health_status = health_info.get("Status")
        except Exception as e:
            logger.debug(f"Impossible d'inspecter le container {c.id}: {e}")

    return ServiceWithMetrics(
        id=c.id,
        name=c.name,
        image=c.image,
        status=c.state,
        cpu_percent=0.0,
        memory_usage="0M",
        uptime=uptime,
        ports=ports,
        health_status=health_status,
    )


def get_latest_active_deployment(
    deployments: list[Deployment],
) -> Optional[Deployment]:
    """
    Retourne le déploiement le plus récent qui n'est pas STOPPED/FAILED.

    Si tous les déploiements sont STOPPED ou FAILED, retourne le plus récent
    en fallback. Retourne None si la liste est vide.

    Args:
        deployments: Liste des déploiements ORM.

    Returns:
        Le déploiement le plus récent actif, ou None.
    """
    active = [
        d for d in deployments
        if d.status not in (DeploymentStatus.STOPPED, DeploymentStatus.FAILED)
    ]
    if not active:
        all_sorted = sorted(deployments, key=lambda d: d.created_at, reverse=True)
        return all_sorted[0] if all_sorted else None
    return sorted(active, key=lambda d: d.created_at, reverse=True)[0]


async def build_managed_stacks(
    db_stacks: list,
    managed_by_stack_id: dict[str, list[ContainerInfo]],
    targets_by_id: dict[str, Target],
    local_target_id: str,
    local_target_name: str,
    docker_for_health: Optional[DockerClientService] = None,
) -> list[StackWithServices]:
    """
    Construit les StackWithServices depuis les stacks DB enrichies avec Docker.

    Pour chaque stack DB :
    - Résout la target via le déploiement actif le plus récent.
    - Construit les services à partir des containers Docker correspondants.
    - Extrait uptime, ports et health_status pour chaque service.
    - Calcule le statut dérivé : running/partial/stopped.
    - Normalise la technologie (docker_compose → docker-compose).

    Args:
        db_stacks: Stacks ORM depuis la DB.
        managed_by_stack_id: Containers groupés par stack_id.
        targets_by_id: Targets indexées par ID.
        local_target_id: ID de la target locale.
        local_target_name: Nom de la target locale.
        docker_for_health: Client Docker pour inspections health (optionnel).

    Returns:
        Liste de StackWithServices.
    """
    managed_stacks: list[StackWithServices] = []

    for stack in db_stacks:
        # Trouver le déploiement le plus récent pour obtenir la target
        active_deployment = get_latest_active_deployment(stack.deployments)
        if active_deployment and active_deployment.target_id in targets_by_id:
            t = targets_by_id[active_deployment.target_id]
            s_target_id = t.id
            s_target_name = t.name
        else:
            s_target_id = local_target_id
            s_target_name = local_target_name

        # Containers actifs de cette stack (via labels)
        stack_containers = managed_by_stack_id.get(stack.id, [])
        services = [
            await _build_service_with_metrics(c, docker_for_health)
            for c in stack_containers
        ]
        services_total = len(stack_containers)
        services_running = sum(1 for c in stack_containers if c.state == "running")

        # Statut dérivé
        if services_total == 0:
            computed_status: str = "stopped"
        elif services_running == services_total:
            computed_status = "running"
        elif services_running > 0:
            computed_status = "partial"
        else:
            computed_status = "stopped"

        # Normaliser la technologie (docker_compose → docker-compose)
        raw_tech = stack.target_type or "windflow"
        normalized_tech = "docker-compose" if raw_tech == "docker_compose" else raw_tech

        managed_stacks.append(
            StackWithServices(
                id=stack.id,
                name=stack.name,
                technology=normalized_tech,
                target_id=s_target_id,
                target_name=s_target_name,
                services_total=services_total,
                services_running=services_running,
                status=computed_status,  # type: ignore[arg-type]
                services=services,
            )
        )

    return managed_stacks


async def build_discovered_items(
    discovered_by_project: dict[str, list[ContainerInfo]],
    local_target_id: str,
    local_target_name: str,
    now_iso: str,
    docker_for_health: Optional[DockerClientService] = None,
) -> list[DiscoveredItem]:
    """
    Construit les DiscoveredItem (projets Compose externes).

    Extrait source_path depuis les labels Docker, génère un ID au format
    ``compose:<project>@<target>``. Enrichit chaque service avec uptime,
    ports et health_status.

    Args:
        discovered_by_project: Containers groupés par nom de projet Compose.
        local_target_id: ID de la target locale.
        local_target_name: Nom de la target locale.
        now_iso: Timestamp ISO actuel.
        docker_for_health: Client Docker pour inspections health (optionnel).

    Returns:
        Liste de DiscoveredItem.
    """
    discovered_items: list[DiscoveredItem] = []

    for project_name, containers in discovered_by_project.items():
        total = len(containers)
        running = sum(1 for c in containers if c.state == "running")
        source_path = None
        # Essayer d'extraire le chemin depuis le premier container
        if containers:
            source_path = containers[0].labels.get(LABEL_COMPOSE_CONFIG_FILES)

        services = [
            await _build_service_with_metrics(c, docker_for_health)
            for c in containers
        ]

        discovered_items.append(
            DiscoveredItem(
                id=f"compose:{project_name}@{local_target_id}",
                name=project_name,
                type="composition",
                technology="docker-compose",
                source_path=source_path,
                target_id=local_target_id,
                target_name=local_target_name,
                services_total=total,
                services_running=running,
                detected_at=now_iso,
                adoptable=True,
                services=services,
            )
        )

    return discovered_items


async def build_standalone_containers(
    standalone_containers_raw: list[ContainerInfo],
    local_target_id: str,
    local_target_name: str,
    docker_available: bool,
) -> list[StandaloneContainer]:
    """
    Construit les StandaloneContainer avec uptime, ports et health.

    Crée un DockerClientService interne si ``docker_available`` et des
    containers sont présents, afin d'inspecter le health_status.

    Args:
        standalone_containers_raw: Containers standalone bruts.
        local_target_id: ID de la target locale.
        local_target_name: Nom de la target locale.
        docker_available: Si Docker est accessible.

    Returns:
        Liste de StandaloneContainer.
    """
    standalone_list: list[StandaloneContainer] = []

    # Client Docker pour les inspections de health
    docker_for_health: Optional[DockerClientService] = None
    if docker_available and standalone_containers_raw:
        try:
            docker_for_health = DockerClientService()
            if not await docker_for_health.ping():
                await docker_for_health.close()
                docker_for_health = None
        except Exception:
            docker_for_health = None

    for c in standalone_containers_raw:
        # Parser les ports
        ports = parse_ports(c.ports)

        # Extraire l'uptime depuis le status Docker
        uptime = extract_uptime(c.status)

        # Récupérer le health status seulement si running
        health_status: Optional[str] = None
        if c.state == "running" and docker_for_health:
            try:
                detail = await docker_for_health.inspect_container(c.id)
                state_info = detail.get("State", {})
                health_info = state_info.get("Health", {})
                if health_info:
                    health_status = health_info.get("Status")
            except Exception as e:
                logger.debug(f"Impossible d'inspecter le container {c.id}: {e}")

        standalone_list.append(
            StandaloneContainer(
                id=c.id,
                name=c.name,
                image=c.image,
                target_id=local_target_id,
                target_name=local_target_name,
                status=c.state,
                cpu_percent=0.0,
                memory_usage="0M",
                uptime=uptime,
                ports=ports,
                health_status=health_status,
            )
        )

    # Fermer le client Docker d'inspection
    if docker_for_health:
        await docker_for_health.close()

    return standalone_list


def build_target_groups(
    managed_stacks: list[StackWithServices],
    discovered_items: list[DiscoveredItem],
    standalone_list: list[StandaloneContainer],
    targets_by_id: dict[str, Target],
) -> list[TargetGroup]:
    """
    Regroupe toutes les ressources par target.

    Les ressources Docker locales non associées à une target DB sont
    regroupées sous le groupe "local".

    Args:
        managed_stacks: Stacks managées.
        discovered_items: Objets découverts.
        standalone_list: Containers standalone.
        targets_by_id: Targets indexées par ID.

    Returns:
        Liste de TargetGroup.
    """
    groups: dict[str, TargetGroup] = {}

    def _get_or_create_group(tid: str, tname: str) -> TargetGroup:
        if tid not in groups:
            tech = "docker"
            if tid in targets_by_id:
                tech = (
                    targets_by_id[tid].type.value
                    if hasattr(targets_by_id[tid].type, "value")
                    else str(targets_by_id[tid].type)
                )
            groups[tid] = TargetGroup(
                target_id=tid,
                target_name=tname,
                technology=tech,
                metrics=TargetMetrics(),
            )
        return groups[tid]

    for stack in managed_stacks:
        grp = _get_or_create_group(stack.target_id, stack.target_name)
        grp.stacks.append(stack)

    for item in discovered_items:
        grp = _get_or_create_group(item.target_id, item.target_name)
        grp.discovered.append(item)

    for container in standalone_list:
        grp = _get_or_create_group(container.target_id, container.target_name)
        grp.standalone.append(container)

    return list(groups.values())
