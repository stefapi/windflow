"""
Service métier pour gestion des déploiements.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.deployment import Deployment
from ..schemas.deployment import DeploymentCreate, DeploymentUpdate


class DeploymentService:
    """Service de gestion des déploiements."""
    
    @staticmethod
    async def get_by_id(db: AsyncSession, deployment_id: str) -> Optional[Deployment]:
        """Récupère un déploiement par son ID."""
        result = await db.execute(
            select(Deployment).where(Deployment.id == deployment_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def list_all(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[Deployment]:
        """Liste tous les déploiements."""
        result = await db.execute(
            select(Deployment)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def create(db: AsyncSession, deployment_data: DeploymentCreate) -> Deployment:
        """Crée un nouveau déploiement."""
        deployment = Deployment(**deployment_data.model_dump())
        db.add(deployment)
        await db.commit()
        await db.refresh(deployment)
        return deployment
