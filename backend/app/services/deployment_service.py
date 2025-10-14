"""
Service métier pour gestion des déploiements.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

from typing import Optional, List
from sqlalchemy import select, and_
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
    async def list_by_organization(
        db: AsyncSession,
        organization_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Deployment]:
        """Liste les déploiements d'une organisation."""
        result = await db.execute(
            select(Deployment)
            .where(Deployment.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_name(
        db: AsyncSession,
        organization_id: str,
        name: str
    ) -> Optional[Deployment]:
        """Récupère un déploiement par son nom dans une organisation."""
        result = await db.execute(
            select(Deployment).where(
                and_(
                    Deployment.organization_id == organization_id,
                    Deployment.name == name
                )
            )
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
    async def create(
        db: AsyncSession,
        deployment_data: DeploymentCreate,
        organization_id: str,
        user_id: str
    ) -> Deployment:
        """Crée un nouveau déploiement."""
        deployment_dict = deployment_data.model_dump()
        deployment_dict["organization_id"] = organization_id
        deployment = Deployment(**deployment_dict)
        db.add(deployment)
        await db.commit()
        await db.refresh(deployment)
        return deployment

    @staticmethod
    async def update(
        db: AsyncSession,
        deployment_id: str,
        deployment_data: DeploymentUpdate
    ) -> Optional[Deployment]:
        """Met à jour un déploiement."""
        deployment = await DeploymentService.get_by_id(db, deployment_id)
        if not deployment:
            return None

        update_data = deployment_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(deployment, field, value)

        await db.commit()
        await db.refresh(deployment)
        return deployment

    @staticmethod
    async def delete(db: AsyncSession, deployment_id: str) -> bool:
        """Supprime un déploiement."""
        deployment = await DeploymentService.get_by_id(db, deployment_id)
        if not deployment:
            return False

        await db.delete(deployment)
        await db.commit()
        return True
