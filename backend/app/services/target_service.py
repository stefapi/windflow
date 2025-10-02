"""
Service métier pour gestion des cibles de déploiement.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.target import Target
from ..schemas.target import TargetCreate, TargetUpdate


class TargetService:
    """Service de gestion des serveurs cibles."""
    
    @staticmethod
    async def get_by_id(db: AsyncSession, target_id: str) -> Optional[Target]:
        """Récupère une cible par son ID."""
        result = await db.execute(
            select(Target).where(Target.id == target_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def list_by_organization(
        db: AsyncSession,
        organization_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Target]:
        """Liste les cibles d'une organisation."""
        result = await db.execute(
            select(Target)
            .where(Target.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def create(db: AsyncSession, target_data: TargetCreate) -> Target:
        """Crée une nouvelle cible."""
        target = Target(**target_data.model_dump())
        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target
