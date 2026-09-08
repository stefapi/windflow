"""
Routes de gestion des workflows.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import get_current_active_user
from ...database import get_db
from ...models.user import User

router = APIRouter()


@router.get("/")
async def list_workflows(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Liste les workflows de l'organisation.

    Args:
        skip: Nombre d'éléments à ignorer pour la pagination
        limit: Nombre maximum d'éléments à retourner
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        List: Liste des workflows (vide pour l'instant)
    """
    # Pour l'instant, retourner une liste vide
    # Le modèle Workflow et WorkflowService seront implémentés plus tard
    # (STORY-121.3 : paramètre organization_id mort retiré — l'endpoint
    # stub ne consomme aucune organisation)
    return []
