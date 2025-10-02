"""
Routes de gestion des organisations.
"""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas.organization import OrganizationResponse, OrganizationCreate, OrganizationUpdate
from ...services.organization_service import OrganizationService
from ...auth.dependencies import get_current_active_user, require_superuser
from ...models.user import User

router = APIRouter()


@router.get("/", response_model=List[OrganizationResponse])
async def list_organizations(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_db)
):
    """
    Liste toutes les organisations (superuser uniquement).

    Args:
        skip: Nombre d'éléments à ignorer pour la pagination
        limit: Nombre maximum d'éléments à retourner
        current_user: Utilisateur courant (doit être superuser)
        session: Session de base de données

    Returns:
        List[OrganizationResponse]: Liste des organisations
    """
    organizations = await OrganizationService.list_all(session, skip, limit)
    return organizations


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Récupère une organisation par son ID.

    Args:
        organization_id: ID de l'organisation
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        OrganizationResponse: Organisation demandée

    Raises:
        HTTPException: Si l'organisation n'existe pas ou accès refusé
    """
    # Vérifier que l'utilisateur appartient à l'organisation ou est superuser
    if not current_user.is_superuser and current_user.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette organisation"
        )

    organization = await OrganizationService.get_by_id(session, organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organisation {organization_id} non trouvée"
        )
    return organization


@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    organization_data: OrganizationCreate,
    current_user: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_db)
):
    """
    Crée une nouvelle organisation (superuser uniquement).

    Args:
        organization_data: Données de l'organisation à créer
        current_user: Utilisateur courant (doit être superuser)
        session: Session de base de données

    Returns:
        OrganizationResponse: Organisation créée

    Raises:
        HTTPException: Si le nom existe déjà
    """
    # Vérifier que le nom n'existe pas déjà
    existing = await OrganizationService.get_by_name(session, organization_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organisation avec le nom '{organization_data.name}' existe déjà"
        )

    organization = await OrganizationService.create(session, organization_data)
    return organization


@router.put("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: UUID,
    organization_data: OrganizationUpdate,
    current_user: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_db)
):
    """
    Met à jour une organisation (superuser uniquement).

    Args:
        organization_id: ID de l'organisation à modifier
        organization_data: Nouvelles données de l'organisation
        current_user: Utilisateur courant (doit être superuser)
        session: Session de base de données

    Returns:
        OrganizationResponse: Organisation mise à jour

    Raises:
        HTTPException: Si l'organisation n'existe pas ou nom en conflit
    """
    # Vérifier que l'organisation existe
    existing_org = await OrganizationService.get_by_id(session, organization_id)
    if not existing_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organisation {organization_id} non trouvée"
        )

    # Si changement de nom, vérifier qu'il n'existe pas déjà
    if organization_data.name and organization_data.name != existing_org.name:
        existing_name = await OrganizationService.get_by_name(session, organization_data.name)
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Organisation avec le nom '{organization_data.name}' existe déjà"
            )

    organization = await OrganizationService.update(session, organization_id, organization_data)
    return organization


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    organization_id: UUID,
    current_user: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_db)
):
    """
    Supprime une organisation (superuser uniquement).

    Args:
        organization_id: ID de l'organisation à supprimer
        current_user: Utilisateur courant (doit être superuser)
        session: Session de base de données

    Raises:
        HTTPException: Si l'organisation n'existe pas
    """
    # Vérifier que l'organisation existe
    organization = await OrganizationService.get_by_id(session, organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organisation {organization_id} non trouvée"
        )

    await OrganizationService.delete(session, organization_id)
