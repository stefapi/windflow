"""
Routes de gestion des utilisateurs.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import db
from ...schemas.user import UserResponse, UserCreate, UserUpdate
from ...services.user_service import UserService
from ...auth.dependencies import get_current_active_user, require_superuser
from ...models.user import User

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Récupère le profil de l'utilisateur courant."""
    return current_user


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(db.get_session)
):
    """Liste les utilisateurs de l'organisation."""
    users = await UserService.list_by_organization(
        session,
        current_user.organization_id,
        skip,
        limit
    )
    return users
