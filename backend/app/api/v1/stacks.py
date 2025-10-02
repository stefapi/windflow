"""
Routes de gestion des stacks Docker Compose.
"""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import db
from ...schemas.stack import StackResponse, StackCreate, StackUpdate
from ...services.stack_service import StackService
from ...auth.dependencies import get_current_active_user
from ...models.user import User

router = APIRouter()


@router.get("/", response_model=List[StackResponse])
async def list_stacks(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(db.get_session)
):
    """
    Liste les stacks Docker Compose de l'organisation.

    Args:
        skip: Nombre d'éléments à ignorer pour la pagination
        limit: Nombre maximum d'éléments à retourner
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        List[StackResponse]: Liste des stacks
    """
    stacks = await StackService.list_by_organization(
        session,
        current_user.organization_id,
        skip,
        limit
    )
    return stacks


@router.get("/{stack_id}", response_model=StackResponse)
async def get_stack(
    stack_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(db.get_session)
):
    """
    Récupère une stack par son ID.

    Args:
        stack_id: ID de la stack
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        StackResponse: Stack demandée

    Raises:
        HTTPException: Si la stack n'existe pas ou accès refusé
    """
    stack = await StackService.get_by_id(session, stack_id)
    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack {stack_id} non trouvée"
        )

    # Vérifier que la stack appartient à la même organisation
    if stack.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette stack"
        )

    return stack


@router.post("/", response_model=StackResponse, status_code=status.HTTP_201_CREATED)
async def create_stack(
    stack_data: StackCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(db.get_session)
):
    """
    Crée une nouvelle stack Docker Compose.

    Args:
        stack_data: Données de la stack à créer
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        StackResponse: Stack créée

    Raises:
        HTTPException: Si le nom existe déjà dans l'organisation
    """
    # Vérifier que le nom n'existe pas déjà dans l'organisation
    existing = await StackService.get_by_name(
        session,
        current_user.organization_id,
        stack_data.name
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stack avec le nom '{stack_data.name}' existe déjà"
        )

    stack = await StackService.create(session, stack_data, current_user.organization_id)
    return stack


@router.put("/{stack_id}", response_model=StackResponse)
async def update_stack(
    stack_id: UUID,
    stack_data: StackUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(db.get_session)
):
    """
    Met à jour une stack Docker Compose.

    Args:
        stack_id: ID de la stack à modifier
        stack_data: Nouvelles données de la stack
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        StackResponse: Stack mise à jour

    Raises:
        HTTPException: Si la stack n'existe pas, accès refusé ou nom en conflit
    """
    # Vérifier que la stack existe
    existing_stack = await StackService.get_by_id(session, stack_id)
    if not existing_stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack {stack_id} non trouvée"
        )

    # Vérifier les permissions
    if existing_stack.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette stack"
        )

    # Si changement de nom, vérifier qu'il n'existe pas déjà
    if stack_data.name and stack_data.name != existing_stack.name:
        existing_name = await StackService.get_by_name(
            session,
            current_user.organization_id,
            stack_data.name
        )
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stack avec le nom '{stack_data.name}' existe déjà"
            )

    stack = await StackService.update(session, stack_id, stack_data)
    return stack


@router.delete("/{stack_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stack(
    stack_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(db.get_session)
):
    """
    Supprime une stack Docker Compose.

    Args:
        stack_id: ID de la stack à supprimer
        current_user: Utilisateur courant
        session: Session de base de données

    Raises:
        HTTPException: Si la stack n'existe pas ou accès refusé
    """
    # Vérifier que la stack existe
    stack = await StackService.get_by_id(session, stack_id)
    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack {stack_id} non trouvée"
        )

    # Vérifier les permissions
    if stack.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette stack"
        )

    await StackService.delete(session, stack_id)
