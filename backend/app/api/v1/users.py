"""
Routes de gestion des utilisateurs.
"""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas.user import UserResponse, UserCreate, UserUpdate
from ...services.user_service import UserService
from ...auth.dependencies import get_current_active_user, require_superuser
from ...models.user import User

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """
    Récupère le profil de l'utilisateur courant.

    Args:
        current_user: Utilisateur courant authentifié

    Returns:
        UserResponse: Profil de l'utilisateur
    """
    return current_user


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Liste les utilisateurs de l'organisation.

    Args:
        skip: Nombre d'éléments à ignorer pour la pagination
        limit: Nombre maximum d'éléments à retourner
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        List[UserResponse]: Liste des utilisateurs
    """
    users = await UserService.list_by_organization(
        session,
        current_user.organization_id,
        skip,
        limit
    )
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Récupère un utilisateur par son ID.

    Args:
        user_id: ID de l'utilisateur
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        UserResponse: Utilisateur demandé

    Raises:
        HTTPException: Si l'utilisateur n'existe pas ou accès refusé
    """
    user = await UserService.get_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Utilisateur {user_id} non trouvé"
        )

    # Vérifier que l'utilisateur appartient à la même organisation ou est superuser
    if not current_user.is_superuser and user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cet utilisateur"
        )

    return user


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Crée un nouvel utilisateur dans l'organisation.

    Args:
        user_data: Données de l'utilisateur à créer
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        UserResponse: Utilisateur créé

    Raises:
        HTTPException: Si l'email existe déjà
    """
    # Vérifier que l'email n'existe pas déjà
    existing = await UserService.get_by_email(session, user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Utilisateur avec l'email '{user_data.email}' existe déjà"
        )

    # Utiliser l'organisation de l'utilisateur courant
    user = await UserService.create(session, user_data, current_user.organization_id)
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Met à jour un utilisateur.

    Args:
        user_id: ID de l'utilisateur à modifier
        user_data: Nouvelles données de l'utilisateur
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        UserResponse: Utilisateur mis à jour

    Raises:
        HTTPException: Si l'utilisateur n'existe pas ou accès refusé
    """
    # Vérifier que l'utilisateur existe
    existing_user = await UserService.get_by_id(session, user_id)
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Utilisateur {user_id} non trouvé"
        )

    # Vérifier les permissions (même organisation ou superuser)
    if not current_user.is_superuser and existing_user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cet utilisateur"
        )

    # Si changement d'email, vérifier qu'il n'existe pas déjà
    if user_data.email and user_data.email != existing_user.email:
        existing_email = await UserService.get_by_email(session, user_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Utilisateur avec l'email '{user_data.email}' existe déjà"
            )

    user = await UserService.update(session, user_id, user_data)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Supprime un utilisateur.

    Args:
        user_id: ID de l'utilisateur à supprimer
        current_user: Utilisateur courant
        session: Session de base de données

    Raises:
        HTTPException: Si l'utilisateur n'existe pas, accès refusé ou tentative d'auto-suppression
    """
    # Empêcher l'auto-suppression
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de supprimer son propre compte"
        )

    # Vérifier que l'utilisateur existe
    user = await UserService.get_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Utilisateur {user_id} non trouvé"
        )

    # Vérifier les permissions (même organisation ou superuser)
    if not current_user.is_superuser and user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cet utilisateur"
        )

    await UserService.delete(session, user_id)
