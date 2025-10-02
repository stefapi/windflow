"""
Service métier pour gestion des organisations.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.organization import Organization
from ..schemas.organization import OrganizationCreate, OrganizationUpdate


class OrganizationService:
    """Service de gestion des organisations (multi-tenant)."""
    
    @staticmethod
    async def get_by_id(db: AsyncSession, org_id: str) -> Optional[Organization]:
        """Récupère une organisation par son ID."""
        result = await db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create(db: AsyncSession, org_data: OrganizationCreate) -> Organization:
        """Crée une nouvelle organisation."""
        org = Organization(**org_data.model_dump())
        db.add(org)
        await db.commit()
        await db.refresh(org)
        return org
