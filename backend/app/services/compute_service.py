"""
Service d'agrégation Compute — Orchestrateur.

Délègue la classification, la construction et le filtrage aux modules spécialisés :
- container_classifier : classification des containers par labels
- container_builder : construction des objets domaine Pydantic
- compute_helpers : utilitaires (formatage, filtrage)
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Union

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..helper.compute_helpers import apply_filters
from ..helper.pagination import paginate_sequence
from ..models.host import Host
from ..models.stack import Stack
from ..schemas.common import PaginatedResponse
from ..schemas.compute import (
    ComputeBrowseItem,
    ComputeGlobalView,
    ComputeStatsResponse,
)
from ..services.container_builder import (
    build_discovered_items,
    build_managed_stacks,
    build_standalone_containers,
    build_target_groups,
)

# Ré-export pour compatibilité (tests existants qui importent depuis compute_service)
from ..services.container_classifier import (
    LOCAL_HOST_ID,
    LOCAL_HOST_NAME,
    classify_containers,
)
from ..services.docker_client_service import DockerClientService

logger = logging.getLogger(__name__)


async def _resolve_local_host(
    db: AsyncSession, org_ids: Optional[List[str]]
) -> tuple[str, str]:
    """
    Résout le host Docker local dans la DB (STORY-166.3 T8).

    Retourne l'ID du host seedé (premier ``Host`` avec
    ``host IN ('localhost', '127.0.0.1')``) pour rattacher stacks et
    containers adoptés au **vrai** host (coopération STORY-166.5 — le
    seed garantit son existence).

    Returns:
        (host_id, host_name) — soit du host seedé en DB, soit le
        placeholder ``("local", "Local Docker")`` si absent.
    """
    stmt = select(Host).where(Host.host.in_(["localhost", "127.0.0.1"]))
    if org_ids:
        stmt = stmt.where(Host.organization_id.in_(org_ids))
    stmt = stmt.limit(1)
    result = await db.execute(stmt)
    host = result.scalar_one_or_none()
    if host:
        return host.id, host.name
    return LOCAL_HOST_ID, LOCAL_HOST_NAME


async def get_compute_stats(
    db: AsyncSession,
    org_ids: Optional[List[str]],
) -> ComputeStatsResponse:
    """
    Retourne les statistiques synthétiques de la vue Compute.

    Agrège les données DB (stacks, targets) et Docker (containers).
    Si Docker n'est pas disponible, les compteurs Docker sont mis à 0.

    Args:
        db: Session base de données async
        org_ids: IDs des organisations (filtre multi-tenant,
            multi-appartenance STORY-121.3)

    Returns:
        ComputeStatsResponse avec les 9 compteurs
    """
    # --- DB : stacks ---
    stacks_stmt = select(func.count(Stack.id))
    if org_ids:
        stacks_stmt = stacks_stmt.where(Stack.organization_id.in_(org_ids))
    stacks_count: int = (await db.execute(stacks_stmt)).scalar() or 0

    # --- DB : targets ---
    targets_stmt = select(func.count(Host.id))
    if org_ids:
        targets_stmt = targets_stmt.where(Host.organization_id.in_(org_ids))
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
                        t_id = c.labels.get("windflow.target_id", LOCAL_HOST_ID)
                        stack_target_ids.add(t_id)
            stacks_targets_count = len(stack_target_ids)

            # Calcul des targets distinctes pour discovered
            discovered_target_ids: set[str] = set()
            for project_name, project_containers in discovered.items():
                for c in project_containers:
                    t_id = c.labels.get("windflow.target_id", LOCAL_HOST_ID)
                    discovered_target_ids.add(t_id)
            discovered_targets_count = len(discovered_target_ids)

            # Calcul des targets distinctes pour standalone
            standalone_target_ids: set[str] = set()
            for c in standalone_list:
                t_id = c.labels.get("windflow.target_id", LOCAL_HOST_ID)
                standalone_target_ids.add(t_id)
            standalone_targets_count = len(standalone_target_ids)
        else:
            await docker.close()
            logger.warning("Docker non disponible — compteurs containers à 0")
    except Exception as exc:
        logger.warning(
            f"Impossible de contacter Docker : {exc} — compteurs containers à 0"
        )

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


async def _collect_inventory(
    db: AsyncSession,
    org_ids: Optional[List[str]],
    type_filter: Optional[str] = None,
    technology: Optional[str] = None,
    target_id_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> Tuple[list, list, list, dict[str, Host]]:
    """Construit l'inventaire compute filtré (chemin commun global/browse).

    Facteur commun de ``get_compute_global`` et ``get_compute_browse``
    (STORY-173 — D1) : stacks DB + classification Docker + builders +
    ``apply_filters``. Si Docker n'est pas disponible, retourne
    uniquement les stacks DB avec statut ``stopped`` (graceful
    degradation inchangée).

    Returns:
        Tuple ``(managed_stacks, discovered_items, standalone_list,
        targets_by_id)`` — les trois sections déjà filtrées et l'index
        des hosts.
    """
    # 1. Récupérer les stacks DB avec leurs deployments actifs
    stacks_stmt = select(Stack).options(selectinload(Stack.deployments))
    if org_ids:
        stacks_stmt = stacks_stmt.where(Stack.organization_id.in_(org_ids))
    stacks_result = await db.execute(stacks_stmt)
    db_stacks = stacks_result.scalars().all()

    # Index des hosts pour éviter les N+1
    targets_stmt = select(Host)
    if org_ids:
        targets_stmt = targets_stmt.where(Host.organization_id.in_(org_ids))
    targets_result = await db.execute(targets_stmt)
    targets_by_id: dict[str, Host] = {t.id: t for t in targets_result.scalars().all()}

    # 2. Récupérer les containers Docker (graceful degradation)
    docker_containers: list = []
    docker_available = False

    try:
        docker = DockerClientService()
        if await docker.ping():
            pass

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
    local_target_id, local_target_name = await _resolve_local_host(db, org_ids)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Client Docker partagé pour les inspections health
    docker_for_health: Optional[DockerClientService] = None
    if docker_available:
        try:
            docker_for_health = DockerClientService()
            if not await docker_for_health.ping():
                await docker_for_health.close()
                docker_for_health = None
        except Exception:
            docker_for_health = None

    try:
        managed_stacks = await build_managed_stacks(
            db_stacks,  # type: ignore[arg-type]
            managed_by_stack_id,
            targets_by_id,
            local_target_id,
            local_target_name,
            docker_for_health=docker_for_health,
        )

        discovered_items = await build_discovered_items(
            discovered_by_project,
            local_target_id,
            local_target_name,
            now_iso,
            docker_for_health=docker_for_health,
        )

        standalone_list = await build_standalone_containers(
            standalone_containers_raw,
            local_target_id,
            local_target_name,
            docker_available,
        )
    finally:
        if docker_for_health:
            await docker_for_health.close()

    # 5. Appliquer les filtres
    managed_stacks, discovered_items, standalone_list = apply_filters(
        managed_stacks,
        discovered_items,
        standalone_list,
        type_filter=type_filter,
        technology=technology,
        target_id_filter=target_id_filter,
        status_filter=status_filter,
        search=search,
    )

    return managed_stacks, discovered_items, standalone_list, targets_by_id


async def get_compute_global(
    db: AsyncSession,
    org_ids: Optional[List[str]],
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
        org_ids: Filtre organisations (multi-appartenance STORY-121.3)
        type_filter: Filtre par type ("managed", "discovered", "standalone")
        technology: Filtre par technologie (ex: "compose")
        target_id_filter: Filtre par target_id
        status_filter: Filtre par statut (running, stopped, etc.)
        search: Recherche textuelle sur le nom
        group_by: "stack" (vue par type) ou "target" (vue par target)

    Returns:
        ComputeGlobalView ou list[TargetGroup] selon group_by
    """
    (
        managed_stacks,
        discovered_items,
        standalone_list,
        targets_by_id,
    ) = await _collect_inventory(
        db,
        org_ids,
        type_filter=type_filter,
        technology=technology,
        target_id_filter=target_id_filter,
        status_filter=status_filter,
        search=search,
    )

    # Retourner selon group_by
    if group_by == "target":
        return build_target_groups(
            managed_stacks,
            discovered_items,
            standalone_list,
            targets_by_id,
        )

    return ComputeGlobalView(
        managed_stacks=managed_stacks,
        discovered_items=discovered_items,
        standalone_containers=standalone_list,
    )


async def get_compute_browse(
    db: AsyncSession,
    org_ids: Optional[List[str]],
    type_filter: Optional[str] = None,
    target_id_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> PaginatedResponse:
    """Aplatissement paginé de l'inventaire compute (STORY-173 — D1).

    Réutilise le chemin de :func:`get_compute_global` (stacks DB +
    classification + builders + ``apply_filters`` — aucun appel Docker
    nouveau) et aplatit les trois sections en items uniformes
    :class:`ComputeBrowseItem` :

    - chaque service d'une stack managée → ``kind=managed_service`` ;
    - chaque projet découvert → ``kind=discovered`` ;
    - chaque container standalone → ``kind=standalone``.

    La pagination est mémoire (``paginate_sequence`` — source non SQL,
    pattern docker.py). Docker indisponible → stacks DB seules, pas
    d'exception (graceful degradation inchangée).

    Args:
        db: Session base de données async
        org_ids: Filtre organisations (multi-appartenance STORY-121.3)
        type_filter: Filtre par type ("managed", "discovered", "standalone")
        target_id_filter: Filtre par host
        status_filter: Filtre par statut
        search: Recherche textuelle sur le nom
        page: Page demandée (1-indexée)
        per_page: Taille de page (bornée par PaginationQuery)

    Returns:
        :class:`PaginatedResponse` d'items ``ComputeBrowseItem``.
    """
    managed_stacks, discovered_items, standalone_list, _ = await _collect_inventory(
        db,
        org_ids,
        type_filter=type_filter,
        target_id_filter=target_id_filter,
        status_filter=status_filter,
        search=search,
    )

    items: list[ComputeBrowseItem] = []

    # Services des stacks managées (le filtre "managed" ne vide que les
    # autres sections — les services managés gardent leur stack_id)
    for stack in managed_stacks:
        for service in stack.services:
            items.append(
                ComputeBrowseItem(
                    id=service.id,
                    name=service.name,
                    kind="managed_service",
                    status=service.status,
                    target_id=stack.target_id,
                    target_name=stack.target_name,
                    image=service.image,
                    technology=stack.technology,
                    stack_id=stack.id,
                )
            )
        # Stack sans container actif (stopped/archived) : l'item stack
        # reste visible pour le browse (services_total=0 côté global)
        if not stack.services:
            items.append(
                ComputeBrowseItem(
                    id=stack.id,
                    name=stack.name,
                    kind="managed_service",
                    status=stack.status,
                    target_id=stack.target_id,
                    target_name=stack.target_name,
                    image=None,
                    technology=stack.technology,
                    stack_id=stack.id,
                )
            )

    # Projets découverts
    for item in discovered_items:
        items.append(
            ComputeBrowseItem(
                id=item.id,
                name=item.name,
                kind="discovered",
                status=(
                    "running"
                    if item.services_running == item.services_total
                    and item.services_total > 0
                    else ("stopped" if item.services_running == 0 else "partial")
                ),
                target_id=item.target_id,
                target_name=item.target_name,
                image=None,
                technology=item.technology,
                stack_id=None,
            )
        )

    # Containers standalone
    for container in standalone_list:
        items.append(
            ComputeBrowseItem(
                id=container.id,
                name=container.name,
                kind="standalone",
                status=container.status,
                target_id=container.target_id,
                target_name=container.target_name,
                image=container.image,
                technology=None,
                stack_id=None,
            )
        )

    return paginate_sequence(items, page, per_page)
