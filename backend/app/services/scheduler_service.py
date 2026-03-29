"""
Service de gestion des tâches planifiées.

CRUD et exécution des tâches récurrentes via Celery Beat.
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.scheduled_task import ScheduledTask, TaskType

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service CRUD pour les tâches planifiées."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_tasks(
        self, organization_id: Optional[str] = None
    ) -> list[ScheduledTask]:
        """Liste toutes les tâches planifiées."""
        query = select(ScheduledTask).order_by(ScheduledTask.created_at.desc())
        if organization_id:
            query = query.where(ScheduledTask.organization_id == organization_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Récupère une tâche par son ID."""
        result = await self.db.execute(
            select(ScheduledTask).where(ScheduledTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def create_task(
        self,
        name: str,
        task_type: TaskType,
        cron_expression: str,
        organization_id: str,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        enabled: bool = True,
    ) -> ScheduledTask:
        """Crée une nouvelle tâche planifiée."""
        task = ScheduledTask(
            id=str(uuid4()),
            name=name,
            description=description,
            task_type=task_type,
            cron_expression=cron_expression,
            parameters=parameters or {},
            enabled=enabled,
            organization_id=organization_id,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        logger.info(f"Tâche planifiée créée : {task.name} ({task.cron_expression})")
        return task

    async def update_task(
        self,
        task_id: str,
        **kwargs,
    ) -> Optional[ScheduledTask]:
        """Met à jour une tâche planifiée."""
        task = await self.get_task(task_id)
        if not task:
            return None

        for key, value in kwargs.items():
            if hasattr(task, key) and value is not None:
                setattr(task, key, value)

        task.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(task)
        logger.info(f"Tâche planifiée mise à jour : {task.name}")
        return task

    async def delete_task(self, task_id: str) -> bool:
        """Supprime une tâche planifiée."""
        result = await self.db.execute(
            delete(ScheduledTask).where(ScheduledTask.id == task_id)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def toggle_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Active/désactive une tâche planifiée."""
        task = await self.get_task(task_id)
        if not task:
            return None

        task.enabled = not task.enabled
        task.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(task)
        logger.info(f"Tâche {task.name} {'activée' if task.enabled else 'désactivée'}")
        return task

    async def record_run(
        self, task_id: str, status: str, error: Optional[str] = None
    ) -> Optional[ScheduledTask]:
        """Enregistre le résultat d'une exécution."""
        task = await self.get_task(task_id)
        if not task:
            return None

        task.last_run = datetime.utcnow()
        task.last_status = status
        task.last_error = error
        task.run_count += 1
        task.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_enabled_tasks(self) -> list[ScheduledTask]:
        """Récupère toutes les tâches actives pour Celery Beat."""
        result = await self.db.execute(
            select(ScheduledTask).where(ScheduledTask.enabled == True)
        )
        return list(result.scalars().all())
