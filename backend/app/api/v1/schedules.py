"""
API endpoints pour la gestion des tâches planifiées.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import get_current_active_user
from ...database import get_db
from ...models.scheduled_task import TaskType
from ...models.user import User
from ...schemas.scheduled_task import (
    ScheduledTaskCreate,
    ScheduledTaskResponse,
    ScheduledTaskUpdate,
)
from ...services.scheduler_service import SchedulerService

router = APIRouter()


@router.get("/schedules", response_model=list[ScheduledTaskResponse])
async def list_schedules(
    organization_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Liste toutes les tâches planifiées."""
    service = SchedulerService(db)
    return await service.list_tasks(organization_id)


@router.get("/schedules/{task_id}", response_model=ScheduledTaskResponse)
async def get_schedule(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Récupère une tâche planifiée par son ID."""
    service = SchedulerService(db)
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tâche planifiée non trouvée")
    return task


@router.post("/schedules", response_model=ScheduledTaskResponse, status_code=201)
async def create_schedule(
    data: ScheduledTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Crée une nouvelle tâche planifiée."""
    service = SchedulerService(db)
    return await service.create_task(
        name=data.name,
        task_type=TaskType(data.task_type),
        cron_expression=data.cron_expression,
        organization_id=data.organization_id,
        description=data.description,
        parameters=data.parameters,
        enabled=data.enabled,
    )


@router.put("/schedules/{task_id}", response_model=ScheduledTaskResponse)
async def update_schedule(
    task_id: str,
    data: ScheduledTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Met à jour une tâche planifiée."""
    service = SchedulerService(db)
    task = await service.update_task(task_id, **data.model_dump(exclude_none=True))
    if not task:
        raise HTTPException(status_code=404, detail="Tâche planifiée non trouvée")
    return task


@router.delete("/schedules/{task_id}", status_code=204)
async def delete_schedule(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Supprime une tâche planifiée."""
    service = SchedulerService(db)
    deleted = await service.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tâche planifiée non trouvée")


@router.post("/schedules/{task_id}/toggle", response_model=ScheduledTaskResponse)
async def toggle_schedule(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Active ou désactive une tâche planifiée."""
    service = SchedulerService(db)
    task = await service.toggle_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tâche planifiée non trouvée")
    return task
