"""
Routes API REST pour la vue Compute.

Expose les endpoints d'agrégation et de gestion de la surface compute
(spec 09 § Vue Compute — STORY-173) :
- GET  /compute/stats            → métriques synthétiques (bandeau)
- GET  /compute/global           → vue détaillée classifiée
- GET  /compute/browse           → inventaire aplati paginé/filtrable
- GET  /compute/volumes          → liste paginée des volumes
- GET  /compute/volumes/{name}   → détail d'un volume
- GET  /compute/volumes/{name}/browse → contenu d'un volume (éphémère)
- POST /compute/prune            → prune protégé (superadmin + confirm)
"""

import logging
from typing import Annotated, List, Optional, Union

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import require_superuser
from ...auth.rbac import require_viewer
from ...core.exceptions import (
    InvalidInputError,
    NotFoundError,
    PermissionDeniedError,
    WindFlowException,
)
from ...core.rate_limit import conditional_rate_limiter
from ...database import get_db
from ...helper.pagination import PaginationQuery, paginate_sequence
from ...models.user import User
from ...schemas.common import PaginatedResponse
from ...schemas.compute import (
    ComputeGlobalView,
    ComputePruneRequest,
    ComputePruneResponse,
    ComputeStatsResponse,
    ComputeVolumeResponse,
    PruneItemFailure,
    TargetGroup,
)
from ...services import compute_service, volume_browser_service
from ...services.audit_service import AuditService
from ...services.docker_client_service import DockerClientService, PruneResult
from ...services.user_organization_service import UserOrganizationService

router = APIRouter()
logger = logging.getLogger(__name__)


async def _resolve_org_scope(
    db: AsyncSession, current_user: User, organization_id: Optional[str]
) -> List[str]:
    """Résout le scope organisationnel (pattern stats/global — STORY-121.3).

    Paramètre explicite vérifié contre l'appartenance (403 sinon) ;
    sinon scoping sur toutes les appartenances de l'utilisateur.
    """
    if organization_id:
        if not await UserOrganizationService.is_member(
            db, current_user, organization_id
        ):
            raise PermissionDeniedError("Accès refusé à cette organisation")
        return [organization_id]
    return await UserOrganizationService.get_user_organization_ids(db, current_user)


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
    current_user: User = Depends(require_viewer),
) -> ComputeStatsResponse:
    """
    Statistiques synthétiques pour le bandeau supérieur de la vue Compute.

    Agrège les données de la base de données (stacks, targets) et du daemon
    Docker local. Si Docker n'est pas disponible, les compteurs Docker sont
    retournés à 0 (graceful degradation).

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — métriques/statut
    compute) + isolation par organisation (``is_member``).
    """
    org_filter = await _resolve_org_scope(db, current_user, organization_id)

    logger.info(
        f"GET /compute/stats — user={current_user.username} orgs={len(org_filter)}"
    )
    return await compute_service.get_compute_stats(db=db, org_ids=org_filter)


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
    current_user: User = Depends(require_viewer),
) -> "Union[ComputeGlobalView, list[TargetGroup]]":
    """
    Vue globale des ressources compute.

    Retourne soit un `ComputeGlobalView` (group_by=stack, défaut) soit une
    liste de `TargetGroup` (group_by=target).

    La classification des containers Docker repose sur leurs labels :
    - `windflow.managed=true` → stack managée par WindFlow
    - `com.docker.compose.project` (sans label WindFlow) → objet découvert
    - aucun des deux → container standalone

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — vue détaillée
    compute) + isolation par organisation (``is_member``).
    """
    org_filter = await _resolve_org_scope(db, current_user, organization_id)

    logger.info(
        f"GET /compute/global — user={current_user.username} orgs={len(org_filter)} "
        f"group_by={group_by} type={type} search={search}"
    )
    return await compute_service.get_compute_global(
        db=db,
        org_ids=org_filter,
        type_filter=type,
        technology=technology,
        target_id_filter=target_id,
        status_filter=status,
        search=search,
        group_by=group_by,
    )


@router.get(
    "/browse",
    response_model=PaginatedResponse,
    summary="Browse de l'inventaire compute (aplati, paginé)",
    description=(
        "Aplatissement paginé et filtrable de l'inventaire compute "
        "(STORY-173) : chaque service de stack managée, chaque projet "
        "découvert et chaque container standalone devient un item "
        "uniforme `{id, name, kind, status, target_id, target_name, "
        "image, technology, stack_id}`. Réutilise l'inventaire de "
        "`/compute/global` — aucun appel Docker nouveau.\n\n"
        "Réponse enveloppée : `{data: [...], pagination: {page, per_page, "
        "total, pages}}`."
    ),
    tags=["compute"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        401: {"description": "Token absent/invalide"},
        403: {"description": "Rôle insuffisant ou organisation étrangère"},
        422: {"description": "Paramètres invalides (type, per_page > 100…)"},
    },
)
async def get_compute_browse(
    request: Request,
    type: Annotated[
        Optional[str],
        Query(
            description="Filtre par type : managed | discovered | standalone",
            pattern="^(managed|discovered|standalone)$",
        ),
    ] = None,
    target_id: Annotated[
        Optional[str],
        Query(description="Filtre par ID de host (label windflow.target_id)"),
    ] = None,
    status: Annotated[
        Optional[str],
        Query(description="Filtre par statut (running, stopped, partial…)"),
    ] = None,
    search: Annotated[
        Optional[str],
        Query(description="Recherche textuelle sur le nom (insensible à la casse)"),
    ] = None,
    organization_id: Annotated[
        Optional[str],
        Query(description="Filtrer par ID d'organisation (multi-tenant)"),
    ] = None,
    page: int = PaginationQuery.page,
    per_page: int = PaginationQuery.per_page,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
) -> PaginatedResponse:
    """
    Browse paginé de l'inventaire compute (STORY-173 — AC 1).

    Vue détaillée aplatie : filtres par type/Host/statut + recherche
    libre, pagination `?page&per_page` (bornes 1-100).

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture) + isolation
    par organisation (``is_member`` — 403 pour une org non membre).
    """
    org_filter = await _resolve_org_scope(db, current_user, organization_id)

    logger.info(
        f"GET /compute/browse — user={current_user.username} "
        f"orgs={len(org_filter)} type={type} search={search} "
        f"page={page} per_page={per_page}",
        extra={"correlation_id": getattr(request.state, "correlation_id", None)},
    )
    return await compute_service.get_compute_browse(
        db=db,
        org_ids=org_filter,
        type_filter=type,
        target_id_filter=target_id,
        status_filter=status,
        search=search,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/volumes",
    response_model=PaginatedResponse,
    summary="Liste paginée des volumes Docker",
    description=(
        "Liste les volumes du démon Docker local (miroir compute de "
        "`GET /docker/volumes` — STORY-173). La taille par volume "
        "n'est pas exposée par le listage de l'API Engine (aucune valeur "
        "fabriquée).\n\n"
        "Réponse enveloppée : `{data: [...], pagination: {...}}`."
    ),
    tags=["compute"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        401: {"description": "Token absent/invalide"},
        403: {"description": "Rôle insuffisant"},
    },
)
async def list_compute_volumes(
    request: Request,
    page: int = PaginationQuery.page,
    per_page: int = PaginationQuery.per_page,
    current_user: User = Depends(require_viewer),
) -> PaginatedResponse:
    """
    Liste paginée des volumes Docker (STORY-173 — AC 1).

    Source Docker daemon (non SQL) : ``total = len(liste)`` via
    ``paginate_sequence`` (slicing mémoire).
    """
    logger.info(
        f"GET /compute/volumes — user={current_user.username} "
        f"page={page} per_page={per_page}",
        extra={"correlation_id": getattr(request.state, "correlation_id", None)},
    )
    client = DockerClientService()
    try:
        volumes = await client.list_volumes()
        return paginate_sequence(
            [
                ComputeVolumeResponse(
                    name=v.name,
                    driver=v.driver,
                    mountpoint=v.mountpoint,
                    created_at=v.created_at.isoformat(),
                    labels=v.labels,
                    scope=v.scope,
                ).model_dump()
                for v in volumes
            ],
            page,
            per_page,
        )
    except WindFlowException:
        raise
    except Exception as exc:
        logger.error(f"Error listing volumes (compute): {exc}")
        raise WindFlowException(f"Erreur lors de la liste des volumes: {str(exc)}")
    finally:
        await client.close()


@router.get(
    "/volumes/{volume_name}",
    response_model=ComputeVolumeResponse,
    summary="Détail d'un volume Docker",
    description=(
        "Retourne le détail d'un volume par son nom (404 si absent). "
        "Miroir compute de la sous-surface volumes — STORY-173."
    ),
    tags=["compute"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        401: {"description": "Token absent/invalide"},
        403: {"description": "Rôle insuffisant"},
        404: {"description": "Volume introuvable"},
    },
)
async def get_compute_volume(
    request: Request,
    volume_name: str,
    current_user: User = Depends(require_viewer),
) -> ComputeVolumeResponse:
    """
    Détail d'un volume Docker (STORY-173 — AC 1).

    Le démon n'expose pas de GET unitaire fiable : comparaison sur la
    liste, 404 si absent.
    """
    logger.info(
        f"GET /compute/volumes/{volume_name} — user={current_user.username}",
        extra={"correlation_id": getattr(request.state, "correlation_id", None)},
    )
    client = DockerClientService()
    try:
        volumes = await client.list_volumes()
        for v in volumes:
            if v.name == volume_name:
                return ComputeVolumeResponse(
                    name=v.name,
                    driver=v.driver,
                    mountpoint=v.mountpoint,
                    created_at=v.created_at.isoformat(),
                    labels=v.labels,
                    scope=v.scope,
                )
        raise NotFoundError(f"Volume {volume_name} non trouvé")
    except WindFlowException:
        raise
    except Exception as exc:
        logger.error(f"Error getting volume {volume_name}: {exc}")
        raise WindFlowException(f"Erreur lors de la lecture du volume: {str(exc)}")
    finally:
        await client.close()


@router.get(
    "/volumes/{volume_name}/browse",
    response_model=PaginatedResponse,
    summary="Browse du contenu d'un volume",
    description=(
        "Liste le contenu d'un volume via un conteneur éphémère **durci** "
        "(STORY-173) : image épinglée `busybox:1.37`, montage read-only, "
        "`network_mode=none`, exec `ls -1p` en args-liste (aucun shell), "
        "nettoyage garanti du conteneur. Le pull de l'image au premier "
        "appel est un comportement documenté.\n\n"
        "Réponse enveloppée : `{data: [{name, is_dir, path}], "
        "pagination: {...}}`."
    ),
    tags=["compute"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        401: {"description": "Token absent/invalide"},
        403: {"description": "Rôle insuffisant"},
        404: {"description": "Volume introuvable"},
        422: {"description": "Nom de volume/sous-chemin invalide (anti-traversal)"},
        503: {"description": "Docker indisponible"},
    },
)
async def browse_compute_volume(
    request: Request,
    volume_name: str,
    subpath: Annotated[
        Optional[str],
        Query(
            description=(
                "Sous-chemin relatif dans le volume (optionnel) — rejeté "
                "s'il contient .. ou un chemin absolu"
            )
        ),
    ] = None,
    page: int = PaginationQuery.page,
    per_page: int = PaginationQuery.per_page,
    current_user: User = Depends(require_viewer),
) -> PaginatedResponse:
    """
    Browse du contenu d'un volume (STORY-173 — AC 1, sécurité D3).

    Lecture seule par construction : le volume est monté read-only dans
    un conteneur éphémère sans réseau.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture).
    """
    logger.info(
        f"GET /compute/volumes/{volume_name}/browse — "
        f"user={current_user.username} subpath={subpath}",
        extra={"correlation_id": getattr(request.state, "correlation_id", None)},
    )
    return await volume_browser_service.browse_volume(
        volume_name, subpath, page, per_page
    )


def _map_prune_result(result: PruneResult) -> ComputePruneResponse:
    """Mappe un ``PruneResult`` du socle vers la réponse API (STORY-173)."""
    return ComputePruneResponse(
        resource=result.resource,
        dry_run=result.dry_run,
        pruned=result.pruned_names,
        spared=result.spared_names,
        failed=[
            PruneItemFailure(name=name, error="suppression unitaire échouée")
            for name in result.failed_names
        ],
        pruned_count=result.pruned_count,
        spared_count=result.spared_count,
        failed_count=result.failed_count,
        space_reclaimed_bytes=result.space_reclaimed_bytes,
    )


@router.post(
    "/prune",
    response_model=ComputePruneResponse,
    summary="Prune Docker protégé (superadmin, confirmé, dry-run possible)",
    description=(
        "Prune des images inutilisées / volumes orphelins / containers "
        "stoppés non managés — sémantique protégée (STORY-173, spec 09 "
        "§ Prune) :\n\n"
        "- la liste `windflow-plugin-*` est **épargnée par construction** ;\n"
        "- un volume monté par un container **arrêté** n'est pas éligible ;\n"
        "- suppression **unitaire** : un échec n'interrompt pas la file "
        "(rapport `failed`) ;\n"
        "- l'espace libéré est **réel pour les images**, toujours `0` pour "
        "les volumes (taille non exposée par l'API Docker).\n\n"
        "**Sémantique de confirmation** : `dry_run=true` → rapport "
        "prévisionnel sans aucune suppression (toujours disponible) ; "
        "exécution réelle **seulement** avec `confirm=true` — sans "
        "confirm ni dry-run → **400** avec message actionnable.\n\n"
        "**Réservé superadmin** (flag `is_superuser`) — opérations "
        "destructrices globales (spec 08)."
    ),
    tags=["compute"],
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
    responses={
        400: {"description": "Confirmation explicite requise (confirm=true)"},
        401: {"description": "Token absent/invalide"},
        403: {"description": "Superadmin requis (403 pour admin/operator/viewer)"},
        422: {"description": "Body invalide (resource inconnue, champ inconnu)"},
    },
)
async def prune_compute_resources(
    request: Request,
    prune_request: ComputePruneRequest,
    current_user: User = Depends(require_superuser),
) -> ComputePruneResponse:
    """
    Prune Docker protégé (STORY-173 — AC 2/AC 3).

    ## Access Control (D7)

    Réservé au **superadmin** (flag ``is_superuser`` — le marqueur le
    plus strict, spec 08 « opérations destructrices globales »).
    ``require_superuser`` lève ``PermissionDeniedError`` 403 pour tout
    autre rôle.

    ## Confirmation & audit

    - sans ``confirm=true`` ni ``dry_run=true`` → ``InvalidInputError``
      400 (message actionnable) ;
    - exécution réelle auditée via ``AuditService.log`` (acteur
      utilisateur, comptages uniquement — jamais les noms complets ni
      ``force`` dans l'audit).
    """
    correlation_id = getattr(request.state, "correlation_id", None)

    # AC 3 : confirmation explicite requise pour toute exécution réelle.
    if not prune_request.confirm and not prune_request.dry_run:
        raise InvalidInputError(
            "Confirmation explicite requise pour un prune réel : "
            "rejouez avec confirm=true (ou dry_run=true pour un rapport "
            "prévisionnel sans suppression)"
        )

    logger.info(
        "POST /compute/prune — user=%s resource=%s dry_run=%s",
        current_user.username,
        prune_request.resource,
        prune_request.dry_run,
        extra={"correlation_id": correlation_id},
    )

    client = DockerClientService()
    try:
        if prune_request.resource == "images":
            result = await client.prune_images(
                dry_run=prune_request.dry_run, force=prune_request.force
            )
        elif prune_request.resource == "containers":
            result = await client.prune_stopped_containers(
                dry_run=prune_request.dry_run, force=prune_request.force
            )
        else:
            result = await client.prune_volumes(
                dry_run=prune_request.dry_run, force=prune_request.force
            )
    finally:
        await client.close()

    response = _map_prune_result(result)

    # Audit de l'exécution réelle uniquement (dry-run = lecture).
    if not prune_request.dry_run:
        await AuditService.log_from_request(
            request,
            "compute.prune",
            user=current_user,
            resource_type="docker",
            resource_id=prune_request.resource,
            details={
                "dry_run": False,
                "pruned_count": response.pruned_count,
                "spared_count": response.spared_count,
                "failed_count": response.failed_count,
                "space_reclaimed_bytes": response.space_reclaimed_bytes,
                "protected_prefix": "windflow-plugin-*",
            },
        )
        logger.info(
            "compute.prune exécuté — resource=%s pruned=%d spared=%d "
            "failed=%d reclaimed=%d bytes",
            response.resource,
            response.pruned_count,
            response.spared_count,
            response.failed_count,
            response.space_reclaimed_bytes,
            extra={"correlation_id": correlation_id},
        )

    return response
