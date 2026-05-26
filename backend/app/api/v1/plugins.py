"""
Routes de gestion des plugins — CRUD complet.

Endpoints REST pour le cycle de vie des plugins :
list, get, install, update, configure, uninstall.
"""

import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import get_current_active_user, require_superuser
from ...core.exceptions import WindFlowException
from ...core.rate_limit import conditional_rate_limiter
from ...database import get_db
from ...models.user import User
from ...schemas.plugin import (
    PluginActionResponse,
    PluginConfigureRequest,
    PluginInstallRequest,
    PluginResponse,
    PluginSummaryResponse,
    PluginUpdateRequest,
)
from ...services.plugin_manager_service import PluginManagerService

router = APIRouter()
logger = logging.getLogger(__name__)

# Instance du service — les méthodes de lecture sont statiques,
# les méthodes d'écriture utilisent l'instance (pour le manifest_service)
_plugin_service = PluginManagerService()


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
    current_user: User = Depends(get_current_active_user),
    _rate_limit=Depends(conditional_rate_limiter(100, 60)),
) -> List[PluginSummaryResponse]:
    """Liste les plugins de l'organisation de l'utilisateur courant."""
    logger.info(
        "list_plugins",
        extra={
            "user_id": current_user.id,
            "organization_id": current_user.organization_id,
            "skip": skip,
            "limit": limit,
        },
    )
    plugins = await PluginManagerService.list_plugins(
        db,
        organization_id=current_user.organization_id,
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
    current_user: User = Depends(get_current_active_user),
    _rate_limit=Depends(conditional_rate_limiter(100, 60)),
) -> PluginResponse:
    """Récupère les détails d'un plugin par son ID."""
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
        403: {"description": "Droits insuffisants (superuser requis)"},
        409: {"description": "Plugin déjà installé"},
        422: {"description": "Données invalides"},
    },
)
async def install_plugin(
    install_data: PluginInstallRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superuser),
    _rate_limit=Depends(conditional_rate_limiter(10, 60)),
) -> PluginActionResponse:
    """Installe un nouveau plugin (asynchrone via BackgroundTasks)."""
    logger.info(
        "install_plugin_requested",
        extra={
            "user_id": current_user.id,
            "organization_id": current_user.organization_id,
            "source": install_data.source,
        },
    )
    try:
        plugin = await _plugin_service.install_plugin(
            db,
            install_data=install_data,
            user_id=current_user.id,
            organization_id=current_user.organization_id,
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
        403: {"description": "Droits insuffisants (superuser requis)"},
        404: {"description": "Plugin non trouvé"},
        422: {"description": "Données invalides"},
    },
)
async def update_plugin(
    plugin_id: str,
    update_data: PluginUpdateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superuser),
    _rate_limit=Depends(conditional_rate_limiter(10, 60)),
) -> PluginActionResponse:
    """Met à jour un plugin existant (asynchrone via BackgroundTasks)."""
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
        403: {"description": "Droits insuffisants (superuser requis)"},
        404: {"description": "Plugin non trouvé"},
        422: {"description": "Données invalides"},
    },
)
async def configure_plugin(
    plugin_id: str,
    config_data: PluginConfigureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superuser),
    _rate_limit=Depends(conditional_rate_limiter(20, 60)),
) -> PluginResponse:
    """Configure un plugin existant."""
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
        403: {"description": "Droits insuffisants (superuser requis)"},
        404: {"description": "Plugin non trouvé"},
    },
)
async def uninstall_plugin(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superuser),
    _rate_limit=Depends(conditional_rate_limiter(10, 60)),
) -> None:
    """Désinstalle un plugin."""
    logger.info(
        "uninstall_plugin_requested",
        extra={
            "plugin_id": plugin_id,
            "user_id": current_user.id,
        },
    )
    try:
        await _plugin_service.uninstall_plugin(
            db,
            plugin_id=plugin_id,
            user_id=current_user.id,
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
