"""
Endpoints API pour les favoris utilisateur.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, delete
from typing import List

from ...database import get_db
from ...models.user import User
from ...models.stack import Stack
from ...models.user_favorite import user_favorites
from ...schemas.stack import MarketplaceStackResponse
from ...auth.dependencies import get_current_user

router = APIRouter()


@router.get("/favorites", response_model=List[MarketplaceStackResponse])
async def list_user_favorites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Liste tous les stacks favoris de l'utilisateur."""

    stmt = (
        select(Stack)
        .join(user_favorites, Stack.id == user_favorites.c.stack_id)
        .where(user_favorites.c.user_id == current_user.id)
        .where(Stack.is_public == True)
    )

    result = await db.execute(stmt)
    stacks = result.scalars().all()

    return [MarketplaceStackResponse.model_validate(stack) for stack in stacks]


@router.post("/favorites/{stack_id}", status_code=status.HTTP_201_CREATED)
async def add_favorite(
    stack_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Ajoute un stack aux favoris."""

    # Vérifier que le stack existe
    stmt = select(Stack).where(Stack.id == stack_id)
    result = await db.execute(stmt)
    stack = result.scalar_one_or_none()

    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stack not found"
        )

    # Ajouter aux favoris (ignore si existe déjà)
    stmt = insert(user_favorites).values(
        user_id=current_user.id,
        stack_id=stack_id
    ).prefix_with('OR IGNORE')

    await db.execute(stmt)
    await db.commit()

    return {"message": "Stack added to favorites"}


@router.delete("/favorites/{stack_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    stack_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retire un stack des favoris."""

    stmt = delete(user_favorites).where(
        user_favorites.c.user_id == current_user.id,
        user_favorites.c.stack_id == stack_id
    )

    await db.execute(stmt)
    await db.commit()

    return None


@router.get("/favorites/{stack_id}/check")
async def check_favorite(
    stack_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Vérifie si un stack est dans les favoris."""

    stmt = select(user_favorites).where(
        user_favorites.c.user_id == current_user.id,
        user_favorites.c.stack_id == stack_id
    )

    result = await db.execute(stmt)
    is_favorite = result.first() is not None

    return {"is_favorite": is_favorite}
