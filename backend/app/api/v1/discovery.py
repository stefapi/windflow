"""
Routes API REST pour l'adoption d'objets découverts.

Endpoints :
- GET  /discovery/{item_type}/{item_id}/adoption-data
- POST /discovery/adopt
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.rbac import require_admin, require_viewer
from ...database import get_db
from ...models.user import User
from ...schemas.adoption import AdoptionRequest, AdoptionResponse, AdoptionWizardData
from ...services import adoption_service
from ...services.user_organization_service import UserOrganizationService

router = APIRouter(tags=["discovery"])
logger = logging.getLogger(__name__)


@router.get(
    "/{item_type}/{item_id}/adoption-data",
    response_model=AdoptionWizardData,
    summary="Données d'adoption d'un objet découvert",
    description=(
        "Retourne les données détaillées (services, env, volumes, réseaux, ports) "
        "d'un objet découvert pour alimenter le wizard d'adoption en 3 étapes."
    ),
    responses={
        200: {"description": "Données d'adoption collectées avec succès"},
        401: {"description": "Authentification requise"},
        404: {"description": "Objet découvert introuvable"},
        503: {"description": "Docker indisponible"},
    },
)
async def get_adoption_data(
    item_type: str,
    item_id: str,
    organization_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
) -> AdoptionWizardData:
    """
    Collecte les données détaillées d'un objet découvert pour le wizard.

    Args:
        item_type: Type d'objet (container, composition, helm_release).
        item_id: ID de l'objet découvert (ex: compose:myproject@local).
        organization_id: ID de l'organisation (optionnel, pour multi-tenant).
        db: Session de base de données.
        current_user: Utilisateur authentifié.

    Returns:
        AdoptionWizardData avec inventaire complet et aperçu Compose.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — données du
    wizard) + isolation par organisation (``is_member``).
    """
    # STORY-121.3 : org explicite vérifiée contre l'appartenance (403) ;
    # sinon organisation primaire de l'utilisateur
    if organization_id and not await UserOrganizationService.is_member(
        db, current_user, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette organisation",
        )
    org_id = (
        organization_id
        or await UserOrganizationService.get_primary_organization_id(db, current_user)
    )
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune organisation : rattachez d'abord votre compte",
        )

    return await adoption_service.get_adoption_data(
        db=db,
        org_id=org_id,
        item_type=item_type,
        item_id=item_id,
    )


@router.post(
    "/adopt",
    response_model=AdoptionResponse,
    summary="Adopter un objet découvert",
    description=(
        "Adopte un objet découvert en le convertissant en stack managée WindFlow. "
        "Crée un Stack et un Deployment en base de données."
    ),
    responses={
        200: {"description": "Adoption réussie"},
        401: {"description": "Authentification requise"},
        404: {"description": "Objet découvert introuvable"},
        409: {"description": "Nom de stack déjà pris"},
        422: {"description": "Données invalides"},
        503: {"description": "Docker indisponible"},
    },
)
async def adopt_discovered_item(
    request: AdoptionRequest,
    organization_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> AdoptionResponse:
    """
    Adopte un objet découvert en le convertissant en stack managée.

    Args:
        request: Données de la requête d'adoption.
        organization_id: ID de l'organisation (optionnel).
        db: Session de base de données.
        current_user: Utilisateur authentifié.

    Returns:
        AdoptionResponse avec les IDs de la stack et du deployment créés.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``admin`` minimum (matrice spec 08 : l'adoption
    crée une stack + un deployment — gestion Admin+, aligné sur la création
    de stacks STORY-122.3) + isolation par organisation (``is_member``).
    """
    # STORY-121.3 : org explicite vérifiée contre l'appartenance (403) ;
    # sinon organisation primaire de l'utilisateur
    if organization_id and not await UserOrganizationService.is_member(
        db, current_user, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette organisation",
        )
    org_id = (
        organization_id
        or await UserOrganizationService.get_primary_organization_id(db, current_user)
    )
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune organisation : rattachez d'abord votre compte",
        )

    return await adoption_service.adopt_discovered_item(
        db=db,
        org_id=org_id,
        request=request,
    )
