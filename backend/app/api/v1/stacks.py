"""
Routes de gestion des stacks Docker Compose.
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import db
from ...schemas.stack import StackResponse, StackCreate
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
    """Liste les stacks disponibles."""
    stacks = await StackService.list_by_organization(
        session,
        current_user.organization_id,
        skip,
        limit
    )
    return stacks
