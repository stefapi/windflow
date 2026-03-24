"""
Service d'agrégation Compute.

Fournit les données agrégées pour la vue globale Compute :
- Stacks managées par WindFlow (identifiées via labels Docker windflow.managed=true)
- Objets découverts (projets Docker Compose externes sans label WindFlow)
- Containers standalone (ni compose ni WindFlow)

Stratégie de classification (par labels Docker) :
  windflow.managed=true                  → managed_stacks (enrichi avec données DB)
  com.docker.compose.project (sans wf)   → discovered_items (groupés par projet)
  aucun des deux                         → standalone_containers
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional, Union

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.deployment import Deployment, DeploymentStatus
from ..models.stack import Stack
from ..models.target import Target
from ..schemas.compute import (
    ComputeGlobalView,
    ComputeStatsResponse,
    DiscoveredItem,
    ServiceWithMetrics,
    StackWithServices,
    StandaloneContainer,
    TargetGroup,
    TargetMetrics,
)
from ..services.docker_client_service import DockerClientService, ContainerInfo

logger = logging.getLogger(__name__)

# Labels WindFlow posés sur les containers lors du déploiement
LABEL_WINDFLOW_MANAGED = "windflow.managed"
LABEL_WINDFLOW_STACK_ID = "windflow.stack_id"

# Label Docker Compose standard
LABEL_COMPOSE_PROJECT = "com.docker.compose.project"
LABEL_COMPOSE_CONFIG_FILES = "com.docker.compose.project.config_files"

# Placeholder pour la target locale (Docker sur Unix socket)
LOCAL_TARGET_ID = "local"
LOCAL_TARGET_NAME = "Local Docker"


# =============================================================================
# Helpers
# =============================================================================


def _format_memory(bytes_val: int) -> str:
    """
    Formate une valeur en bytes vers une string lisible.

    Exemples : 103809024 → "99M", 1073741824 → "1G"
    """
    if bytes_val <= 0:
        return "0M"
    kb = bytes_val / 1024
    if kb < 1024:
        return f"{kb:.0f}K"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.0f}M"
    gb = mb / 1024
    return f"{gb:.1f}G"


def _is_windflow_managed(labels: dict[str, str]) -> bool:
    """Retourne True si le container est géré par WindFlow."""
    return labels.get(LABEL_WINDFLOW_MANAGED, "").lower() == "true"


def _is_compose_project(labels: dict[str, str]) -> bool:
    """Retourne True si le container fait partie d'un projet Docker Compose."""
    return LABEL_COMPOSE_PROJECT in labels


def _classify_containers(
    containers: list[ContainerInfo],
) -> tuple[
    dict[str, list[ContainerInfo]],  # managed: {stack_id: [containers]}
    dict[str, list[ContainerInfo]],  # discovered: {project_name: [containers]}
    list[ContainerInfo],             # standalone: [containers]
]:
    """
    Classe les containers Docker en 3 catégories.

    Returns:
        (managed_by_stack_id, discovered_by_project, standalone_list)
    """
    managed: dict[str, list[ContainerInfo]] = defaultdict(list)
    discovered: dict[str, list[ContainerInfo]] = defaultdict(list)
    standalone: list[ContainerInfo] = []

    for c in containers:
        if _is_windflow_managed(c.labels):
            stack_id = c.labels.get(LABEL_WINDFLOW_STACK_ID, "unknown")
            managed[stack_id].append(c)
        elif _is_compose_project(c.labels):
            project = c.labels[LABEL_COMPOSE_PROJECT]
            discovered[project].append(c)
        else:
            standalone.append(c)

    return dict(managed), dict(discovered), standalone


async def _get_local_target(db: AsyncSession, org_id: Optional[str]) -> tuple[str, str]:
    """
    Tente de trouver la target Docker locale dans la DB.

    Returns:
        (target_id, target_name) — soit depuis la DB soit un placeholder
    """
    stmt = select(Target).where(Target.host.in_(["localhost", "127.0.0.1"]))
    if org_id:
        stmt = stmt.where(Target.organization_id == org_id)
    stmt = stmt.limit(1)
    result = await db.execute(stmt)
    target = result.scalar_one_or_none()
    if target:
        return target.id, target.name
    return LOCAL_TARGET_ID, LOCAL_TARGET_NAME


# =============================================================================
# Fonctions principales
# =============================================================================


async def get_compute_stats(
    db: AsyncSession,
    org_id: Optional[str],
) -> ComputeStatsResponse:
    """
    Retourne les statistiques synthétiques de la vue Compute.

    Agrège les données DB (stacks, targets) et Docker (containers).
    Si Docker n'est pas disponible, les compteurs Docker sont mis à 0.

    Args:
        db: Session base de données async
        org_id: ID de l'organisation (filtre multi-tenant)

    Returns:
        ComputeStatsResponse avec les 7 compteurs
    """
    # --- DB : stacks ---
    stacks_stmt = select(func.count(Stack.id))
    if org_id:
        stacks_stmt = stacks_stmt.where(Stack.organization_id == org_id)
    stacks_count: int = (await db.execute(stacks_stmt)).scalar() or 0

    # --- DB : targets ---
    targets_stmt = select(func.count(Target.id))
    if org_id:
        targets_stmt = targets_stmt.where(Target.organization_id == org_id)
    targets_count: int = (await db.execute(targets_stmt)).scalar() or 0

    # --- Docker : containers (graceful degradation) ---
    total_containers = 0
    running_containers = 0
    stacks_services_count = 0
    discovered_count = 0
    standalone_count = 0

    try:
        docker = DockerClientService()
        if await docker.ping():
            containers = await docker.list_containers(all=True)
            await docker.close()

            managed, discovered, standalone_list = _classify_containers(containers)

            total_containers = len(containers)
            running_containers = sum(1 for c in containers if c.state == "running")
            stacks_services_count = sum(len(v) for v in managed.values())
            discovered_count = len(discovered)
            standalone_count = len(standalone_list)
        else:
            await docker.close()
            logger.warning("Docker non disponible — compteurs containers à 0")
    except Exception as exc:
        logger.warning(f"Impossible de contacter Docker : {exc} — compteurs containers à 0")

    return ComputeStatsResponse(
        total_containers=total_containers,
        running_containers=running_containers,
        stacks_count=stacks_count,
        stacks_services_count=stacks_services_count,
        discovered_count=discovered_count,
        standalone_count=standalone_count,
        targets_count=targets_count,
    )


async def get_compute_global(
    db: AsyncSession,
    org_id: Optional[str],
    type_filter: Optional[str] = None,
    technology: Optional[str] = None,
    target_id_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    group_by: str = "stack",
) -> Union[ComputeGlobalView, list[TargetGroup]]:
    """
    Retourne la vue globale des ressources compute.

    Agrège stacks DB, containers Docker (managed + discovered + standalone).
    Si Docker n'est pas disponible, retourne uniquement les stacks DB avec
    statut "stopped" (graceful degradation).

    Args:
        db: Session base de données async
        org_id: Filtre organisation
        type_filter: Filtre par type ("managed", "discovered", "standalone")
        technology: Filtre par technologie (ex: "compose")
        target_id_filter: Filtre par target_id
        status_filter: Filtre par statut (running, stopped, etc.)
        search: Recherche textuelle sur le nom
        group_by: "stack" (vue par type) ou "target" (vue par target)

    Returns:
        ComputeGlobalView ou list[TargetGroup] selon group_by
    """
    # =========================================================================
    # 1. Récupérer les stacks DB avec leurs deployments actifs
    # =========================================================================
    stacks_stmt = (
        select(Stack)
        .options(selectinload(Stack.deployments))
    )
    if org_id:
        stacks_stmt = stacks_stmt.where(Stack.organization_id == org_id)
    stacks_result = await db.execute(stacks_stmt)
    db_stacks = stacks_result.scalars().all()

    # Index des targets pour éviter les N+1
    targets_stmt = select(Target)
    if org_id:
        targets_stmt = targets_stmt.where(Target.organization_id == org_id)
    targets_result = await db.execute(targets_stmt)
    targets_by_id: dict[str, Target] = {t.id: t for t in targets_result.scalars().all()}

    # =========================================================================
    # 2. Récupérer les containers Docker (graceful degradation)
    # =========================================================================
    docker_containers: list[ContainerInfo] = []
    docker_available = False

    try:
        docker = DockerClientService()
        if await docker.ping():
            docker_containers = await docker.list_containers(all=True)
            docker_available = True
        await docker.close()
    except Exception as exc:
        logger.warning(f"Docker non disponible, vue partielle : {exc}")

    # =========================================================================
    # 3. Classifier les containers Docker
    # =========================================================================
    managed_by_stack_id: dict[str, list[ContainerInfo]] = {}
    discovered_by_project: dict[str, list[ContainerInfo]] = {}
    standalone_containers_raw: list[ContainerInfo] = []

    if docker_available:
        managed_by_stack_id, discovered_by_project, standalone_containers_raw = (
            _classify_containers(docker_containers)
        )

    # =========================================================================
    # 4. Construire les StackWithServices (depuis DB, enrichies avec Docker)
    # =========================================================================
    local_target_id, local_target_name = await _get_local_target(db, org_id)
    now_iso = datetime.now(timezone.utc).isoformat()

    managed_stacks: list[StackWithServices] = []

    for stack in db_stacks:
        # Trouver le déploiement le plus récent pour obtenir la target
        active_deployment = _get_latest_active_deployment(stack.deployments)
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
            ServiceWithMetrics(
                id=c.id,
                name=c.name,
                image=c.image,
                status=c.state,
                cpu_percent=0.0,
                memory_usage="0M",
            )
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

        managed_stacks.append(
            StackWithServices(
                id=stack.id,
                name=stack.name,
                technology=stack.target_type or "compose",
                target_id=s_target_id,
                target_name=s_target_name,
                services_total=services_total,
                services_running=services_running,
                status=computed_status,  # type: ignore[arg-type]
                services=services,
            )
        )

    # =========================================================================
    # 5. Construire les DiscoveredItem (projets Compose externes)
    # =========================================================================
    discovered_items: list[DiscoveredItem] = []

    for project_name, containers in discovered_by_project.items():
        total = len(containers)
        running = sum(1 for c in containers if c.state == "running")
        source_path = None
        # Essayer d'extraire le chemin depuis le premier container
        if containers:
            source_path = containers[0].labels.get(LABEL_COMPOSE_CONFIG_FILES)

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
            )
        )

    # =========================================================================
    # 6. Construire les StandaloneContainer
    # =========================================================================
    standalone_list: list[StandaloneContainer] = [
        StandaloneContainer(
            id=c.id,
            name=c.name,
            image=c.image,
            target_id=local_target_id,
            target_name=local_target_name,
            status=c.state,
            cpu_percent=0.0,
            memory_usage="0M",
        )
        for c in standalone_containers_raw
    ]

    # =========================================================================
    # 7. Appliquer les filtres
    # =========================================================================
    if type_filter:
        if type_filter == "managed":
            discovered_items = []
            standalone_list = []
        elif type_filter == "discovered":
            managed_stacks = []
            standalone_list = []
        elif type_filter == "standalone":
            managed_stacks = []
            discovered_items = []

    if search:
        search_lower = search.lower()
        managed_stacks = [s for s in managed_stacks if search_lower in s.name.lower()]
        discovered_items = [d for d in discovered_items if search_lower in d.name.lower()]
        standalone_list = [c for c in standalone_list if search_lower in c.name.lower()]

    if status_filter:
        managed_stacks = [s for s in managed_stacks if s.status == status_filter]
        standalone_list = [c for c in standalone_list if c.status == status_filter]

    if target_id_filter:
        managed_stacks = [s for s in managed_stacks if s.target_id == target_id_filter]
        discovered_items = [d for d in discovered_items if d.target_id == target_id_filter]
        standalone_list = [c for c in standalone_list if c.target_id == target_id_filter]

    if technology:
        managed_stacks = [s for s in managed_stacks if s.technology == technology]
        discovered_items = [d for d in discovered_items if d.technology == technology]

    # =========================================================================
    # 8. Retourner selon group_by
    # =========================================================================
    if group_by == "target":
        return _build_target_groups(
            managed_stacks, discovered_items, standalone_list, targets_by_id
        )

    return ComputeGlobalView(
        managed_stacks=managed_stacks,
        discovered_items=discovered_items,
        standalone_containers=standalone_list,
    )


# =============================================================================
# Helpers privés
# =============================================================================


def _get_latest_active_deployment(
    deployments: list[Deployment],
) -> Optional[Deployment]:
    """Retourne le déploiement le plus récent qui n'est pas STOPPED/FAILED."""
    active = [
        d for d in deployments
        if d.status not in (DeploymentStatus.STOPPED, DeploymentStatus.FAILED)
    ]
    if not active:
        # Fallback : le plus récent même si stopped
        all_sorted = sorted(deployments, key=lambda d: d.created_at, reverse=True)
        return all_sorted[0] if all_sorted else None
    return sorted(active, key=lambda d: d.created_at, reverse=True)[0]


def _build_target_groups(
    managed_stacks: list[StackWithServices],
    discovered_items: list[DiscoveredItem],
    standalone_list: list[StandaloneContainer],
    targets_by_id: dict[str, "Target"],
) -> list[TargetGroup]:
    """
    Regroupe toutes les ressources par target.

    Les ressources Docker locales non associées à une target DB sont regroupées
    sous le groupe "local".
    """
    groups: dict[str, TargetGroup] = {}

    def _get_or_create_group(tid: str, tname: str) -> TargetGroup:
        if tid not in groups:
            tech = "docker"
            if tid in targets_by_id:
                tech = targets_by_id[tid].type.value if hasattr(targets_by_id[tid].type, "value") else str(targets_by_id[tid].type)
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
