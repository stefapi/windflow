"""
Routes de gestion des cibles de déploiement.
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import db
from ...schemas.target import TargetResponse, TargetCreate
from ...services.target_service import TargetService
from ...auth.dependencies import get_current_active_user
from ...models.user import User

router = APIRouter()


@router.get("/", response_model=List[TargetResponse])
async def list_targets(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(db.get_session)
):
    """Liste les cibles de déploiement."""
    targets = await TargetService.list_by_organization(
        session,
        current_user.organization_id,
        skip,
        limit
    )
    return targets
