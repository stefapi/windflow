"""
Routes de gestion des plugins — CRUD complet.

Endpoints REST pour le cycle de vie des plugins :
list, get, install, update, configure, uninstall, hooks/logs.
"""

import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.rbac import require_admin, require_viewer
from ...core.exceptions import WindFlowException
from ...core.rate_limit import conditional_rate_limiter
from ...database import get_db
from ...models.user import User
from ...services.audit_service import AuditService
from ...schemas.plugin import (
    PluginActionResponse,
    PluginConfigureRequest,
    PluginDependencyRefResponse,
    PluginDependencyTreeResponse,
    PluginInstallRequest,
    PluginResponse,
    PluginSummaryResponse,
    PluginUpdateRequest,
)
from ...schemas.plugin_hook_log import HookLogResponse, HookLogSummaryResponse
from ...schemas.plugin_manifest import parse_dependency_string
from ...services.plugin_dependency_service import PluginDependencyService
from ...services.plugin_lifecycle_service import PluginLifecycleService
from ...services.plugin_manager_service import PluginManagerService
from ...services.user_organization_service import UserOrganizationService

router = APIRouter()
logger = logging.getLogger(__name__)

# Instance du service — les méthodes de lecture sont statiques,
# les méthodes d'écriture utilisent l'instance (pour le manifest_service)
_plugin_service = PluginManagerService()
_dependency_service = PluginDependencyService()
_lifecycle_service = PluginLifecycleService()


@router.get(
    "/",
    response_model=List[PluginSummaryResponse],
    summary="Liste des plugins installés",
    description="Retourne la liste paginée des plugins installés pour l'organisation de l'utilisateur courant.",
    responses={
        200: {"description": "Liste des plugins"},
        401: {"description": "Authentification requise"},
    },
)
async def list_plugins(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
    _rate_limit=Depends(conditional_rate_limiter(100, 60)),
) -> List[PluginSummaryResponse]:
    """Liste les plugins des organisations de l'utilisateur courant.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — matrice spec 08 :
    « Voir les plugins installés » = tous les rôles).
    """
    # STORY-121.3 : scoping sur les appartenances (la plupart des users
    # ont une seule org — on liste pour la première, comportement
    # conservé ; multi-appartenance complète via les endpoints membres)
    org_ids = await UserOrganizationService.get_user_organization_ids(db, current_user)
    if not org_ids:
        return []
    primary_org = org_ids[0]
    logger.info(
        "list_plugins",
        extra={
            "user_id": current_user.id,
            "organization_count": len(org_ids),
            "skip": skip,
            "limit": limit,
        },
    )
    plugins = await PluginManagerService.list_plugins(
        db,
        organization_id=primary_org,
        skip=skip,
        limit=limit,
    )
    return [PluginSummaryResponse.model_validate(p) for p in plugins]


@router.get(
    "/{plugin_id}",
    response_model=PluginResponse,
    summary="Détail d'un plugin",
    description="Retourne les détails complets d'un plugin installé, y compris le manifest et la configuration (champs password masqués).",
    responses={
        200: {"description": "Détail du plugin"},
        401: {"description": "Authentification requise"},
        404: {"description": "Plugin non trouvé"},
    },
)
async def get_plugin(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
    _rate_limit=Depends(conditional_rate_limiter(100, 60)),
) -> PluginResponse:
    """Récupère les détails d'un plugin par son ID.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — matrice spec 08).
    """
    logger.info(
        "get_plugin",
        extra={
            "plugin_id": plugin_id,
            "user_id": current_user.id,
        },
    )
    plugin = await PluginManagerService.get_plugin(db, plugin_id)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin non trouvé : {plugin_id}",
        )
    return PluginResponse.model_validate(plugin)


@router.post(
    "/install",
    response_model=PluginActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Installer un plugin",
    description="Installe un nouveau plugin depuis un manifest YAML ou une source distante. L'installation est asynchrone.",
    responses={
        202: {"description": "Installation acceptée (asynchrone)"},
        400: {"description": "Manifest invalide"},
        401: {"description": "Authentification requise"},
        403: {"description": "Droits insuffisants (rôle Admin requis)"},
        409: {"description": "Plugin déjà installé"},
        422: {"description": "Données invalides"},
    },
)
async def install_plugin(
    request: Request,
    install_data: PluginInstallRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
    _rate_limit=Depends(conditional_rate_limiter(10, 60)),
) -> PluginActionResponse:
    """Installe un nouveau plugin (asynchrone via BackgroundTasks).

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``admin`` minimum (matrice spec 08 :
    « Installer/Désinstaller/Configurer un plugin » = Admin+ — remplace le
    marqueur intérimaire ``require_superuser``).
    """
    # STORY-121.3 : organisation primaire de l'utilisateur
    primary_org = await UserOrganizationService.get_primary_organization_id(
        db, current_user
    )
    if primary_org is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune organisation : rattachez d'abord votre compte",
        )
    logger.info(
        "install_plugin_requested",
        extra={
            "user_id": current_user.id,
            "source": install_data.source,
        },
    )
    try:
        plugin = await _plugin_service.install_plugin(
            db,
            install_data=install_data,
            user_id=current_user.id,
            organization_id=primary_org,
        )
        # STORY-125.2 : audit de l'installation (après succès, org du
        # plugin — catalogue spec 15 ``plugin.installed``).
        await AuditService.log_from_request(
            request,
            "plugin.installed",
            user=current_user,
            organization_id=primary_org,
            resource_type="plugin",
            resource_id=str(plugin.id),
            details={"name": plugin.name},
        )
        return PluginActionResponse(
            id=plugin.id,
            status=plugin.status,
            message=f"Plugin '{plugin.name}' installé avec succès",
        )
    except WindFlowException as exc:
        if exc.details.get("error_type") == "duplicate":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=exc.message,
            ) from exc
        if exc.details.get("error_type") == "dependency_unsatisfied":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=exc.message,
            ) from exc
        if exc.details.get("error_type") in ("validation", "yaml_syntax", "value"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=exc.message,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc


@router.put(
    "/{plugin_id}/update",
    response_model=PluginActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Mettre à jour un plugin",
    description="Met à jour un plugin vers une nouvelle version. La mise à jour est asynchrone.",
    responses={
        202: {"description": "Mise à jour acceptée (asynchrone)"},
        401: {"description": "Authentification requise"},
        403: {"description": "Droits insuffisants (rôle Admin requis)"},
        404: {"description": "Plugin non trouvé"},
        422: {"description": "Données invalides"},
    },
)
async def update_plugin(
    plugin_id: str,
    update_data: PluginUpdateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
    _rate_limit=Depends(conditional_rate_limiter(10, 60)),
) -> PluginActionResponse:
    """Met à jour un plugin existant (asynchrone via BackgroundTasks).

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``admin`` minimum (matrice spec 08 — remplace
    le marqueur intérimaire ``require_superuser``).
    """
    logger.info(
        "update_plugin_requested",
        extra={
            "plugin_id": plugin_id,
            "user_id": current_user.id,
        },
    )
    try:
        plugin = await _plugin_service.update_plugin(
            db,
            plugin_id=plugin_id,
            update_data=update_data,
            user_id=current_user.id,
        )
        return PluginActionResponse(
            id=plugin.id,
            status=plugin.status,
            message=f"Plugin '{plugin.name}' mis à jour vers la version {plugin.version}",
        )
    except WindFlowException as exc:
        if exc.details.get("error_type") == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=exc.message,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc


@router.put(
    "/{plugin_id}/configure",
    response_model=PluginResponse,
    summary="Configurer un plugin",
    description="Met à jour la configuration d'un plugin installé.",
    responses={
        200: {"description": "Configuration mise à jour"},
        401: {"description": "Authentification requise"},
        403: {"description": "Droits insuffisants (rôle Admin requis)"},
        404: {"description": "Plugin non trouvé"},
        422: {"description": "Données invalides"},
    },
)
async def configure_plugin(
    plugin_id: str,
    config_data: PluginConfigureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
    _rate_limit=Depends(conditional_rate_limiter(20, 60)),
) -> PluginResponse:
    """Configure un plugin existant.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``admin`` minimum (matrice spec 08 — remplace
    le marqueur intérimaire ``require_superuser``).
    """
    logger.info(
        "configure_plugin_requested",
        extra={
            "plugin_id": plugin_id,
            "user_id": current_user.id,
        },
    )
    try:
        plugin = await _plugin_service.configure_plugin(
            db,
            plugin_id=plugin_id,
            config_data=config_data,
            user_id=current_user.id,
        )
        return PluginResponse.model_validate(plugin)
    except WindFlowException as exc:
        if exc.details.get("error_type") == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=exc.message,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc


@router.delete(
    "/{plugin_id}/uninstall",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Désinstaller un plugin",
    description="Supprime un plugin installé du système.",
    responses={
        204: {"description": "Plugin désinstallé avec succès"},
        401: {"description": "Authentification requise"},
        403: {"description": "Droits insuffisants (rôle Admin requis)"},
        404: {"description": "Plugin non trouvé"},
    },
)
async def uninstall_plugin(
    request: Request,
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
    _rate_limit=Depends(conditional_rate_limiter(10, 60)),
) -> None:
    """Désinstalle un plugin.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``admin`` minimum (matrice spec 08 — remplace
    le marqueur intérimaire ``require_superuser``).
    """
    logger.info(
        "uninstall_plugin_requested",
        extra={
            "plugin_id": plugin_id,
            "user_id": current_user.id,
        },
    )
    try:
        plugin = await _plugin_service.get_plugin(db, plugin_id)
        # STORY-125.2 : org du plugin capturée AVANT suppression (la ligne
        # cesse d'exister après uninstall — correlation/org tracées).
        plugin_org_id = plugin.organization_id if plugin else None
        plugin_name = plugin.name if plugin else None
        await _plugin_service.uninstall_plugin(
            db,
            plugin_id=plugin_id,
            user_id=current_user.id,
        )
        # Audit après succès (catalogue spec 15 ``plugin.removed``) —
        # resource = plugin retiré, org capturée avant suppression.
        await AuditService.log_from_request(
            request,
            "plugin.removed",
            user=current_user,
            organization_id=plugin_org_id,
            resource_type="plugin",
            resource_id=plugin_id,
            details={"name": plugin_name},
        )
    except WindFlowException as exc:
        if exc.details.get("error_type") == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=exc.message,
            ) from exc
        if exc.details.get("error_type") == "has_dependents":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=exc.message,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.message,
        ) from exc


# ── GET /plugins/{plugin_id}/dependencies ────────────────────────────────────


@router.get(
    "/{plugin_id}/dependencies",
    response_model=PluginDependencyTreeResponse,
    summary="Arbre de dépendances d'un plugin",
    description="Retourne l'arbre de dépendances complet d'un plugin installé : requires, optional, conflicts, dependents.",
    responses={
        200: {"description": "Arbre de dépendances"},
        401: {"description": "Authentification requise"},
        404: {"description": "Plugin non trouvé"},
    },
)
async def get_plugin_dependencies(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
    _rate_limit=Depends(conditional_rate_limiter(100, 60)),
) -> PluginDependencyTreeResponse:
    """Retourne l'arbre de dépendances complet d'un plugin installé.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — matrice spec 08).
    """
    logger.info(
        "get_plugin_dependencies",
        extra={
            "plugin_id": plugin_id,
            "user_id": current_user.id,
        },
    )
    plugin = await PluginManagerService.get_plugin(db, plugin_id)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin non trouvé : {plugin_id}",
        )

    # Extraire les dépendances du manifest_data
    manifest_data = plugin.manifest_data or {}
    deps_data = manifest_data.get("dependencies") or {}
    requires_raw: list[str] = deps_data.get("requires", [])
    optional_raw: list[str] = deps_data.get("optional", [])
    conflicts_raw: list[str] = deps_data.get("conflicts", [])

    # Récupérer les plugins installés pour vérifier le statut
    # (STORY-121.3 : toutes les organisations de l'utilisateur)
    from sqlalchemy import select as sql_select

    from ...models.plugin import Plugin as PluginModel

    org_ids = await UserOrganizationService.get_user_organization_ids(db, current_user)
    stmt = sql_select(PluginModel)
    if org_ids:
        stmt = stmt.where(PluginModel.organization_id.in_(org_ids))
    result = await db.execute(stmt)
    installed_plugins = {p.name: p for p in result.scalars().all()}

    # Construire les réponses pour requires
    requires_refs: list[PluginDependencyRefResponse] = []
    for req_str in requires_raw:
        try:
            dep_ref = parse_dependency_string(req_str)
            installed_plugin = installed_plugins.get(dep_ref.name)
            requires_refs.append(
                PluginDependencyRefResponse(
                    name=dep_ref.name,
                    version_constraint=dep_ref.version_constraint,
                    installed=installed_plugin is not None,
                    installed_version=(
                        installed_plugin.version if installed_plugin else None
                    ),
                )
            )
        except ValueError:
            continue

    # Construire les réponses pour optional
    optional_refs: list[PluginDependencyRefResponse] = []
    for opt_str in optional_raw:
        try:
            dep_ref = parse_dependency_string(opt_str)
            installed_plugin = installed_plugins.get(dep_ref.name)
            optional_refs.append(
                PluginDependencyRefResponse(
                    name=dep_ref.name,
                    version_constraint=dep_ref.version_constraint,
                    installed=installed_plugin is not None,
                    installed_version=(
                        installed_plugin.version if installed_plugin else None
                    ),
                )
            )
        except ValueError:
            continue

    # Construire la liste des conflits (noms simples)
    conflicts_names: list[str] = []
    for conf_str in conflicts_raw:
        try:
            dep_ref = parse_dependency_string(conf_str)
            conflicts_names.append(dep_ref.name)
        except ValueError:
            conflicts_names.append(conf_str)

    # Récupérer les dépendants (plugins qui dépendent de celui-ci)
    # (STORY-121.3 : organisation primaire)
    primary_org_deps = await UserOrganizationService.get_primary_organization_id(
        db, current_user
    )
    if primary_org_deps is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune organisation : rattachez d'abord votre compte",
        )
    dependents = await _dependency_service.check_uninstall_dependents(
        db, plugin.name, primary_org_deps
    )

    return PluginDependencyTreeResponse(
        plugin_id=plugin.id,
        plugin_name=plugin.name,
        requires=requires_refs,
        optional=optional_refs,
        conflicts=conflicts_names,
        dependents=dependents,
    )


# ── GET /plugins/{plugin_id}/hooks/logs ──────────────────────────────────────


@router.get(
    "/{plugin_id}/hooks/logs",
    response_model=List[HookLogSummaryResponse],
    summary="Logs d'exécution des hooks d'un plugin",
    description="Retourne la liste paginée des logs d'exécution des hooks lifecycle pour un plugin.",
    responses={
        200: {"description": "Liste des logs de hooks"},
        401: {"description": "Authentification requise"},
        403: {"description": "Accès interdit (plugin d'une autre organisation)"},
        404: {"description": "Plugin non trouvé"},
    },
)
async def get_hook_logs(
    plugin_id: str,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
    _rate_limit=Depends(conditional_rate_limiter(100, 60)),
) -> List[HookLogSummaryResponse]:
    """Liste les logs d'exécution des hooks pour un plugin.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — matrice spec 08).
    """
    logger.info(
        "get_hook_logs",
        extra={
            "plugin_id": plugin_id,
            "user_id": current_user.id,
            "skip": skip,
            "limit": limit,
        },
    )
    plugin = await PluginManagerService.get_plugin(db, plugin_id)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin non trouvé : {plugin_id}",
        )
    # STORY-121.3 : isolation via l'appartenance (superuser bypass
    # intégré à is_member)
    if not await UserOrganizationService.is_member(
        db, current_user, plugin.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès interdit : ce plugin appartient à une autre organisation",
        )

    logs = await PluginLifecycleService.list_hook_logs(db, plugin_id, skip, limit)
    return [HookLogSummaryResponse.model_validate(log) for log in logs]


@router.get(
    "/{plugin_id}/hooks/logs/{log_id}",
    response_model=HookLogResponse,
    summary="Détail d'un log d'exécution de hook",
    description="Retourne le détail complet d'un log d'exécution de hook, incluant stdout et stderr.",
    responses={
        200: {"description": "Détail du log de hook"},
        401: {"description": "Authentification requise"},
        403: {"description": "Accès interdit (plugin d'une autre organisation)"},
        404: {"description": "Plugin ou log non trouvé"},
    },
)
async def get_hook_log_detail(
    plugin_id: str,
    log_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
    _rate_limit=Depends(conditional_rate_limiter(100, 60)),
) -> HookLogResponse:
    """Récupère le détail d'un log d'exécution de hook.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — matrice spec 08).
    """
    logger.info(
        "get_hook_log_detail",
        extra={
            "plugin_id": plugin_id,
            "log_id": log_id,
            "user_id": current_user.id,
        },
    )
    plugin = await PluginManagerService.get_plugin(db, plugin_id)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin non trouvé : {plugin_id}",
        )
    # STORY-121.3 : isolation via l'appartenance
    if not await UserOrganizationService.is_member(
        db, current_user, plugin.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès interdit : ce plugin appartient à une autre organisation",
        )

    log = await PluginLifecycleService.get_hook_log(db, log_id)
    if not log or log.plugin_id != plugin_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log de hook non trouvé : {log_id}",
        )

    return HookLogResponse.model_validate(log)
