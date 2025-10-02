"""
Routes de gestion des déploiements.
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import db
from ...schemas.deployment import DeploymentResponse, DeploymentCreate
from ...services.deployment_service import DeploymentService
from ...auth.dependencies import get_current_active_user
from ...models.user import User

router = APIRouter()


@router.get("/", response_model=List[DeploymentResponse])
async def list_deployments(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(db.get_session)
):
    """Liste tous les déploiements."""
    deployments = await DeploymentService.list_all(session, skip, limit)
    return deployments
