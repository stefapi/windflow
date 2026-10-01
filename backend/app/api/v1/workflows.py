"""
Routes de gestion des workflows.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.rbac import require_viewer
from ...database import get_db
from ...helper.pagination import PaginationQuery, build_meta
from ...models.user import User
from ...schemas.common import PaginatedResponse

router = APIRouter()


@router.get(
    "/",
    response_model=PaginatedResponse,
    summary="List workflows (stub — paginated envelope)",
)
async def list_workflows(
    page: int = PaginationQuery.page,
    per_page: int = PaginationQuery.per_page,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """
    Liste paginée des workflows de l'organisation (STORY-128).

    Endpoint **stub** : le modèle Workflow et WorkflowService ne sont
    pas encore implémentés — le handler contracte dès maintenant le
    format canonique ``{data, pagination}`` (data vide, métadonnées
    exactes) pour éviter un breaking change supplémentaire le jour de
    l'implémentation.

    Args:
        page: Page demandée (1-indexée, défaut 1)
        per_page: Taille de page (1-100, défaut 20)
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        PaginatedResponse: Page vide + métadonnées exactes

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — endpoint stub).
    """
    # Pour l'instant, retourner une liste vide
    # Le modèle Workflow et WorkflowService seront implémentés plus tard
    # (STORY-121.3 : paramètre organization_id mort retiré — l'endpoint
    # stub ne consomme aucune organisation)
    return PaginatedResponse(
        data=[],
        pagination=build_meta(page, per_page, total=0),
    )
