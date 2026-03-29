"""
Routes API REST pour la vue Compute.

Expose deux endpoints d'agrégation :
- GET /compute/stats   → métriques synthétiques (bandeau de la vue globale)
- GET /compute/global  → vue détaillée (stacks managées, objets découverts, standalone)
"""

import logging
from typing import Annotated, Optional, Union

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import get_current_active_user
from ...database import get_db
from ...models.user import User
from ...schemas.compute import ComputeGlobalView, ComputeStatsResponse, TargetGroup
from ...services import compute_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/stats",
    response_model=ComputeStatsResponse,
    summary="Statistiques synthétiques Compute",
    description=(
        "Retourne les 7 compteurs synthétiques pour le bandeau supérieur "
        "de la vue globale Compute : "
        "containers totaux/running, stacks WindFlow, services actifs, "
        "objets découverts, containers standalone, targets enregistrées."
    ),
    tags=["compute"],
)
async def get_compute_stats(
    organization_id: Annotated[
        Optional[str],
        Query(description="Filtrer par ID d'organisation (multi-tenant)"),
    ] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ComputeStatsResponse:
    """
    Statistiques synthétiques pour le bandeau supérieur de la vue Compute.

    Agrège les données de la base de données (stacks, targets) et du daemon
    Docker local. Si Docker n'est pas disponible, les compteurs Docker sont
    retournés à 0 (graceful degradation).
    """
    org_id = organization_id or current_user.organization_id
    logger.info(f"GET /compute/stats — user={current_user.username} org={org_id}")
    return await compute_service.get_compute_stats(db=db, org_id=org_id)


@router.get(
    "/global",
    summary="Vue globale Compute",
    description=(
        "Retourne la vue détaillée des ressources compute, classées en trois sections : "
        "stacks managées par WindFlow, objets découverts (projets Compose externes), "
        "et containers standalone. "
        "Avec `group_by=target`, les ressources sont regroupées par target. "
        "Supporte les filtres : type, technology, target_id, status, search."
    ),
    tags=["compute"],
    responses={
        200: {
            "description": (
                "ComputeGlobalView (group_by=stack) "
                "ou liste de TargetGroup (group_by=target)"
            ),
        }
    },
)
async def get_compute_global(
    type: Annotated[
        Optional[str],
        Query(
            description="Filtre par type : managed | discovered | standalone",
            pattern="^(managed|discovered|standalone)$",
        ),
    ] = None,
    technology: Annotated[
        Optional[str],
        Query(description="Filtre par technologie (ex: compose, helm)"),
    ] = None,
    target_id: Annotated[
        Optional[str],
        Query(description="Filtre par ID de target"),
    ] = None,
    status: Annotated[
        Optional[str],
        Query(description="Filtre par statut (running, stopped, partial, exited…)"),
    ] = None,
    search: Annotated[
        Optional[str],
        Query(description="Recherche textuelle sur le nom (insensible à la casse)"),
    ] = None,
    group_by: Annotated[
        str,
        Query(
            description="Mode de regroupement : stack (défaut) ou target",
            pattern="^(stack|target)$",
        ),
    ] = "stack",
    organization_id: Annotated[
        Optional[str],
        Query(description="Filtrer par ID d'organisation (multi-tenant)"),
    ] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Union[ComputeGlobalView, list[TargetGroup]]:
    """
    Vue globale des ressources compute.

    Retourne soit un `ComputeGlobalView` (group_by=stack, défaut) soit une
    liste de `TargetGroup` (group_by=target).

    La classification des containers Docker repose sur leurs labels :
    - `windflow.managed=true` → stack managée par WindFlow
    - `com.docker.compose.project` (sans label WindFlow) → objet découvert
    - aucun des deux → container standalone
    """
    org_id = organization_id or current_user.organization_id
    logger.info(
        f"GET /compute/global — user={current_user.username} org={org_id} "
        f"group_by={group_by} type={type} search={search}"
    )
    return await compute_service.get_compute_global(
        db=db,
        org_id=org_id,
        type_filter=type,
        technology=technology,
        target_id_filter=target_id,
        status_filter=status,
        search=search,
        group_by=group_by,
    )
