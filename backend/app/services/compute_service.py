"""
Service d'agrégation Compute — Orchestrateur.

Délègue la classification, la construction et le filtrage aux modules spécialisés :
- container_classifier : classification des containers par labels
- container_builder : construction des objets domaine Pydantic
- compute_helpers : utilitaires (formatage, filtrage)
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Union

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.stack import Stack
from ..models.target import Target
from ..schemas.compute import (
    ComputeGlobalView,
    ComputeStatsResponse,
)
from ..services.docker_client_service import DockerClientService
from ..services.container_classifier import (
    classify_containers,
    LOCAL_TARGET_ID,
    LOCAL_TARGET_NAME,
)
from ..services.container_builder import (
    build_managed_stacks,
    build_discovered_items,
    build_standalone_containers,
    build_target_groups,
)
from ..helper.compute_helpers import apply_filters

# Ré-export pour compatibilité (tests existants qui importent depuis compute_service)
from ..services.container_classifier import classify_containers as _classify_containers
from ..helper.compute_helpers import format_memory as _format_memory

logger = logging.getLogger(__name__)


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
        ComputeStatsResponse avec les 9 compteurs
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
    stacks_running_count = 0
    stacks_targets_count = 0
    discovered_count = 0
    discovered_targets_count = 0
    standalone_count = 0
    standalone_targets_count = 0

    try:
        docker = DockerClientService()
        if await docker.ping():
            containers = await docker.list_containers(all=True)
            await docker.close()

            managed, discovered, standalone_list = classify_containers(containers)

            total_containers = len(containers)
            running_containers = sum(1 for c in containers if c.state == "running")
            stacks_services_count = sum(len(v) for v in managed.values())
            discovered_count = len(discovered)
            standalone_count = len(standalone_list)

            # Calcul des stacks running et targets distinctes
            stack_target_ids: set[str] = set()
            for stack_id, stack_containers in managed.items():
                if stack_containers:
                    all_running = all(c.state == "running" for c in stack_containers)
                    if all_running:
                        stacks_running_count += 1
                    for c in stack_containers:
                        t_id = c.labels.get("windflow.target_id", LOCAL_TARGET_ID)
                        stack_target_ids.add(t_id)
            stacks_targets_count = len(stack_target_ids)

            # Calcul des targets distinctes pour discovered
            discovered_target_ids: set[str] = set()
            for project_name, project_containers in discovered.items():
                for c in project_containers:
                    t_id = c.labels.get("windflow.target_id", LOCAL_TARGET_ID)
                    discovered_target_ids.add(t_id)
            discovered_targets_count = len(discovered_target_ids)

            # Calcul des targets distinctes pour standalone
            standalone_target_ids: set[str] = set()
            for c in standalone_list:
                t_id = c.labels.get("windflow.target_id", LOCAL_TARGET_ID)
                standalone_target_ids.add(t_id)
            standalone_targets_count = len(standalone_target_ids)
        else:
            await docker.close()
            logger.warning("Docker non disponible — compteurs containers à 0")
    except Exception as exc:
        logger.warning(f"Impossible de contacter Docker : {exc} — compteurs containers à 0")

    return ComputeStatsResponse(
        total_containers=total_containers,
        running_containers=running_containers,
        stacks_count=stacks_count,
        stacks_running_count=stacks_running_count,
        stacks_targets_count=stacks_targets_count,
        stacks_services_count=stacks_services_count,
        discovered_count=discovered_count,
        discovered_targets_count=discovered_targets_count,
        standalone_count=standalone_count,
        standalone_targets_count=standalone_targets_count,
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
) -> Union[ComputeGlobalView, list]:
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
    # 1. Récupérer les stacks DB avec leurs deployments actifs
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

    # 2. Récupérer les containers Docker (graceful degradation)
    docker_containers: list = []
    docker_available = False

    try:
        docker = DockerClientService()
        if await docker.ping():
            from ..services.docker_client_service import ContainerInfo
            docker_containers = await docker.list_containers(all=True)
            docker_available = True
        await docker.close()
    except Exception as exc:
        logger.warning(f"Docker non disponible, vue partielle : {exc}")

    # 3. Classifier les containers Docker
    managed_by_stack_id: dict = {}
    discovered_by_project: dict = {}
    standalone_containers_raw: list = []

    if docker_available:
        managed_by_stack_id, discovered_by_project, standalone_containers_raw = (
            classify_containers(docker_containers)
        )

    # 4. Construire les objets domaine via les builders
    local_target_id, local_target_name = await _get_local_target(db, org_id)
    now_iso = datetime.now(timezone.utc).isoformat()

    managed_stacks = build_managed_stacks(
        db_stacks, managed_by_stack_id, targets_by_id,
        local_target_id, local_target_name,
    )

    discovered_items = build_discovered_items(
        discovered_by_project, local_target_id, local_target_name, now_iso,
    )

    standalone_list = await build_standalone_containers(
        standalone_containers_raw, local_target_id, local_target_name,
        docker_available,
    )

    # 5. Appliquer les filtres
    managed_stacks, discovered_items, standalone_list = apply_filters(
        managed_stacks, discovered_items, standalone_list,
        type_filter=type_filter,
        technology=technology,
        target_id_filter=target_id_filter,
        status_filter=status_filter,
        search=search,
    )

    # 6. Retourner selon group_by
    if group_by == "target":
        return build_target_groups(
            managed_stacks, discovered_items, standalone_list, targets_by_id,
        )

    return ComputeGlobalView(
        managed_stacks=managed_stacks,
        discovered_items=discovered_items,
        standalone_containers=standalone_list,
    )
