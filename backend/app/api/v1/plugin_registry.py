"""
Routes du registre officiel de plugins — Endpoints en lecture seule.

Endpoints REST pour consulter le registre officiel :
liste des plugins disponibles et détail d'un plugin spécifique.
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends

from ...auth.rbac import require_viewer
from ...config import settings as app_settings
from ...core.exceptions import (
    NotFoundError,
    UnprocessableEntityError,
)
from ...core.rate_limit import conditional_rate_limiter
from ...helper.pagination import PaginationQuery, paginate_sequence
from ...models.user import User
from ...schemas.common import PaginatedResponse
from ...schemas.plugin_registry import (
    RegistryPluginDetailResponse,
    RegistryPluginSummaryResponse,
)
from ...services.plugin_registry_service import PluginRegistryService

router = APIRouter()
logger = logging.getLogger(__name__)

# Pattern de validation kebab-case pour le paramètre plugin_name
_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Instance du service — injecte les settings de l'application
_registry_service = PluginRegistryService(app_settings)


def _get_registry_service() -> PluginRegistryService:
    """Retourne l'instance du service registre."""
    return _registry_service


@router.get(
    "/plugins",
    response_model=PaginatedResponse,
    summary="Liste des plugins du registre officiel",
    description=(
        "Retourne la liste paginée des plugins disponibles dans le registre "
        "officiel WindFlow — STORY-128 : enveloppe "
        "`PaginatedResponse{data, pagination{page, per_page, total, pages}}` ; "
        "les filtres `category`/`query` sont appliqués AVANT la pagination "
        "(`total` = taille de la liste filtrée, source YAML non SQL)."
    ),
    responses={
        200: {
            "description": "Page de plugins du registre (enveloppe paginée)",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "name": "traefik",
                                "version": "1.2.0",
                                "display_name": "Traefik",
                                "description": "Reverse proxy",
                                "category": "access",
                                "tags": ["proxy"],
                            }
                        ],
                        "pagination": {
                            "page": 1,
                            "per_page": 20,
                            "total": 42,
                            "pages": 3,
                        },
                        "message": None,
                    }
                }
            },
        },
        401: {"description": "Authentification requise"},
    },
)
async def list_registry_plugins(
    category: Optional[str] = None,
    query: Optional[str] = None,
    page: int = PaginationQuery.page,
    per_page: int = PaginationQuery.per_page,
    current_user: User = Depends(require_viewer),
    _rate_limit=Depends(conditional_rate_limiter(60, 60)),
) -> PaginatedResponse:
    """Liste paginée des plugins du registre officiel (STORY-128).

    Filtres ``category``/``query`` appliqués **avant** le slicing mémoire
    (``total = len(liste filtrée)`` — source YAML filesystem, aucun
    ``COUNT`` SQL possible).

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (parcourir le marketplace —
    matrice spec 08 : « Parcourir le registre » = tous les rôles).
    """
    logger.info(
        "list_registry_plugins",
        extra={
            "user_id": current_user.id,
            "page": page,
            "per_page": per_page,
            "category": category,
            "query": query,
        },
    )

    service = _get_registry_service()

    if query:
        plugins = await service.search_plugins(query)
    else:
        plugins = await service.list_plugins()

    # Filtre par catégorie si spécifié — AVANT la pagination pour que
    # total reflète la liste filtrée (AC 3)
    if category:
        plugins = [p for p in plugins if p.category.value == category]

    # Tri stable par nom (le registry n'a pas d'ordre garanti filesystem)
    plugins = sorted(plugins, key=lambda p: p.name)

    summaries = [
        RegistryPluginSummaryResponse(
            name=p.name,
            version=p.version,
            display_name=p.display_name,
            description=p.description,
            category=p.category.value,
            tags=p.tags,
        ).model_dump()
        for p in plugins
    ]
    return paginate_sequence(summaries, page, per_page)


@router.get(
    "/plugins/{plugin_name}",
    response_model=RegistryPluginDetailResponse,
    summary="Détail d'un plugin du registre officiel",
    description="Retourne les détails complets d'un plugin du registre officiel, y compris le checksum SHA-256 et l'URL de téléchargement.",
    responses={
        200: {"description": "Détail du plugin"},
        401: {"description": "Authentification requise"},
        404: {"description": "Plugin non trouvé dans le registre"},
        422: {"description": "Nom de plugin invalide"},
    },
)
async def get_registry_plugin_detail(
    plugin_name: str,
    current_user: User = Depends(require_viewer),
    _rate_limit=Depends(conditional_rate_limiter(60, 60)),
) -> RegistryPluginDetailResponse:
    """Récupère les détails d'un plugin du registre par son nom.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture marketplace —
    matrice spec 08).
    """
    logger.info(
        "get_registry_plugin_detail",
        extra={
            "plugin_name": plugin_name,
            "user_id": current_user.id,
        },
    )

    # Validation kebab-case du paramètre (anti path traversal)
    if not _NAME_PATTERN.match(plugin_name):
        raise UnprocessableEntityError(
            f"Nom de plugin invalide : '{plugin_name}'. Le nom doit être en kebab-case (lettres minuscules, chiffres et tirets).",
        )

    service = _get_registry_service()
    plugin = await service.get_plugin(plugin_name)

    if not plugin:
        raise NotFoundError(f"Plugin non trouvé dans le registre : {plugin_name}")

    return RegistryPluginDetailResponse(
        name=plugin.name,
        version=plugin.version,
        display_name=plugin.display_name,
        description=plugin.description,
        category=plugin.category.value,
        type=plugin.type.value,
        author=plugin.author,
        license=plugin.license,
        architectures=[arch.value for arch in plugin.architectures],
        download_url=plugin.download_url,
        checksum_sha256=plugin.checksum_sha256,
        homepage=plugin.homepage,
        tags=plugin.tags,
    )
