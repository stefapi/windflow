"""
Service métier pour gestion des stacks Docker Compose.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.stack import Stack
from ..schemas.stack import StackCreate, StackUpdate


class StackService:
    """Service de gestion des stacks."""
    
    @staticmethod
    async def get_by_id(db: AsyncSession, stack_id: str) -> Optional[Stack]:
        """Récupère un stack par son ID."""
        result = await db.execute(
            select(Stack).where(Stack.id == stack_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def list_by_organization(
        db: AsyncSession,
        organization_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Stack]:
        """Liste les stacks d'une organisation."""
        result = await db.execute(
            select(Stack)
            .where(Stack.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def create(db: AsyncSession, stack_data: StackCreate) -> Stack:
        """Crée un nouveau stack."""
        stack = Stack(**stack_data.model_dump())
        db.add(stack)
        await db.commit()
        await db.refresh(stack)
        return stack
