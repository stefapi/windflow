"""
Routes de gestion des cibles de déploiement.
"""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas.target import TargetResponse, TargetCreate, TargetUpdate
from ...services.target_service import TargetService
from ...auth.dependencies import get_current_active_user
from ...models.user import User

router = APIRouter()


@router.get("/", response_model=List[TargetResponse])
async def list_targets(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Liste les cibles de déploiement de l'organisation.

    Args:
        skip: Nombre d'éléments à ignorer pour la pagination
        limit: Nombre maximum d'éléments à retourner
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        List[TargetResponse]: Liste des cibles
    """
    targets = await TargetService.list_by_organization(
        session,
        current_user.organization_id,
        skip,
        limit
    )
    return targets


@router.get("/{target_id}", response_model=TargetResponse)
async def get_target(
    target_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Récupère une cible par son ID.

    Args:
        target_id: ID de la cible
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        TargetResponse: Cible demandée

    Raises:
        HTTPException: Si la cible n'existe pas ou accès refusé
    """
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    # Vérifier que la cible appartient à la même organisation
    if target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
        )

    return target


@router.post("/", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
async def create_target(
    target_data: TargetCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Crée une nouvelle cible de déploiement.

    Args:
        target_data: Données de la cible à créer
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        TargetResponse: Cible créée

    Raises:
        HTTPException: Si le nom existe déjà dans l'organisation
    """
    # Vérifier que le nom n'existe pas déjà dans l'organisation
    existing = await TargetService.get_by_name(
        session,
        current_user.organization_id,
        target_data.name
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cible avec le nom '{target_data.name}' existe déjà"
        )

    target = await TargetService.create(session, target_data, current_user.organization_id)
    return target


@router.put("/{target_id}", response_model=TargetResponse)
async def update_target(
    target_id: UUID,
    target_data: TargetUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Met à jour une cible de déploiement.

    Args:
        target_id: ID de la cible à modifier
        target_data: Nouvelles données de la cible
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        TargetResponse: Cible mise à jour

    Raises:
        HTTPException: Si la cible n'existe pas, accès refusé ou nom en conflit
    """
    # Vérifier que la cible existe
    existing_target = await TargetService.get_by_id(session, target_id)
    if not existing_target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    # Vérifier les permissions
    if existing_target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
        )

    # Si changement de nom, vérifier qu'il n'existe pas déjà
    if target_data.name and target_data.name != existing_target.name:
        existing_name = await TargetService.get_by_name(
            session,
            current_user.organization_id,
            target_data.name
        )
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cible avec le nom '{target_data.name}' existe déjà"
            )

    target = await TargetService.update(session, target_id, target_data)
    return target


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(
    target_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Supprime une cible de déploiement.

    Args:
        target_id: ID de la cible à supprimer
        current_user: Utilisateur courant
        session: Session de base de données

    Raises:
        HTTPException: Si la cible n'existe pas ou accès refusé
    """
    # Vérifier que la cible existe
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    # Vérifier les permissions
    if target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
        )

    await TargetService.delete(session, target_id)
