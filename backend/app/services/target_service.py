"""
Service métier pour gestion des cibles de déploiement.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.target import Target
from ..schemas.target import TargetCreate, TargetUpdate


class TargetService:
    """Service de gestion des serveurs cibles."""

    @staticmethod
    async def get_by_id(db: AsyncSession, target_id: str) -> Optional[Target]:
        """Récupère une cible par son ID."""
        result = await db.execute(select(Target).where(Target.id == target_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(
        db: AsyncSession,
        organization_id: str,
        name: str
    ) -> Optional[Target]:
        """Récupère une cible par son nom dans une organisation."""
        result = await db.execute(
            select(Target).where(
                Target.organization_id == organization_id,
                Target.name == name
            )
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
    async def create(
        db: AsyncSession,
        target_data: TargetCreate,
        organization_id: Optional[str] = None
    ) -> Target:
        """Crée une nouvelle cible."""
        payload = target_data.model_dump()
        if organization_id:
            payload["organization_id"] = organization_id

        target = Target(**payload)
        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target

    @staticmethod
    async def update(
        db: AsyncSession,
        target_id: str,
        target_data: TargetUpdate
    ) -> Optional[Target]:
        """Met à jour les informations d'une cible."""
        target = await TargetService.get_by_id(db, target_id)
        if target is None:
            return None

        update_data = target_data.model_dump(exclude_unset=True, exclude_none=True)
        if not update_data:
            return target

        for key, value in update_data.items():
            setattr(target, key, value)

        target.updated_at = datetime.utcnow()
        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target

    @staticmethod
    async def delete(db: AsyncSession, target_id: str) -> bool:
        """Supprime une cible."""
        target = await TargetService.get_by_id(db, target_id)
        if target is None:
            return False

        await db.delete(target)
        await db.commit()
        return True

    @staticmethod
    async def set_scan_status(
        db: AsyncSession,
        target: Target,
        status: str
    ) -> Target:
        """Met à jour le statut du dernier scan."""
        target.scan_status = status
        target.updated_at = datetime.utcnow()
        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target

    @staticmethod
    async def update_discovered_capabilities(
        db: AsyncSession,
        target: Target,
        capabilities: Dict,
        scan_date: datetime,
        status: str = "completed"
    ) -> Target:
        """Met à jour les capacités découvertes pour une cible."""
        target.discovered_capabilities = capabilities
        target.last_scan_date = scan_date
        target.scan_status = status
        target.updated_at = datetime.utcnow()

        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target
