"""
API endpoints pour la gestion des tâches planifiées.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.rbac import require_admin, require_operator, require_viewer
from ...core.exceptions import (
    NotFoundError,
)
from ...database import get_db
from ...helper.pagination import PaginationQuery, build_meta
from ...models.scheduled_task import TaskType
from ...models.user import User
from ...schemas.common import PaginatedResponse
from ...schemas.scheduled_task import (
    ScheduledTaskCreate,
    ScheduledTaskResponse,
    ScheduledTaskUpdate,
)
from ...services.scheduler_service import SchedulerService

router = APIRouter()


@router.get(
    "/schedules",
    response_model=PaginatedResponse,
    summary="List scheduled tasks",
    description="""
List scheduled tasks, optionally filtered by organization.

## Pagination
- `?page=1&per_page=20` (max 100) — STORY-128 canonical format,
  response envelope `PaginatedResponse{data, pagination{page, per_page, total, pages}}`
- **Stable order**: `ORDER BY name` — no duplicates/holes across pages

## Access Control
- **Minimum role**: Viewer — read-only access for any authenticated user
""",
    responses={
        200: {
            "description": ("Paginated list of scheduled tasks — enveloppe spec 09"),
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": "3f2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
                                "name": "cleanup-logs",
                                "task_type": "cleanup_logs",
                                "cron_expression": "0 3 * * *",
                                "parameters": {},
                                "enabled": True,
                                "organization_id": None,
                            }
                        ],
                        "pagination": {
                            "page": 1,
                            "per_page": 20,
                            "total": 12,
                            "pages": 1,
                        },
                        "message": None,
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INVALID_OR_EXPIRED_TOKEN",
                            "message": "Unauthorized",
                        }
                    }
                }
            },
        },
    },
)
async def list_schedules(
    organization_id: Optional[str] = Query(None),
    page: int = PaginationQuery.page,
    per_page: int = PaginationQuery.per_page,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    """Liste paginée des tâches planifiées (STORY-128).

    Filtre ``organization_id`` combiné avec la pagination dans la même
    requête ; ``total`` scopusé sur le même filtre (AC 3).

    Args:
        organization_id: Filtre optionnel par organisation
        page: Page demandée (1-indexée, défaut 1)
        per_page: Taille de page (1-100, défaut 20)
        db: Session de base de données
        current_user: Utilisateur courant

    Returns:
        PaginatedResponse: Page de tâches planifiées + métadonnées
    """
    service = SchedulerService(db)
    tasks = await service.list_tasks(
        organization_id, page=page, per_page=per_page
    )
    total = await service.count_tasks(organization_id)
    data: List[dict] = [
        ScheduledTaskResponse.model_validate(t).model_dump() for t in tasks
    ]
    return PaginatedResponse(data=data, pagination=build_meta(page, per_page, total))


@router.get(
    "/schedules/{task_id}",
    response_model=ScheduledTaskResponse,
    summary="Get scheduled task by ID",
    description="""
Retrieve a scheduled task by its ID.

## Access Control
- **Minimum role**: Viewer — read-only access for any authenticated user
""",
)
async def get_schedule(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    """Récupère une tâche planifiée par son ID."""
    service = SchedulerService(db)
    task = await service.get_task(task_id)
    if not task:
        raise NotFoundError("Tâche planifiée non trouvée")
    return task


@router.post(
    "/schedules",
    response_model=ScheduledTaskResponse,
    status_code=201,
    summary="Create a scheduled task",
    description="""
Create a new scheduled task (automation management).

## Access Control
- **Minimum role**: Admin — resource management (create/delete/configure)
""",
)
async def create_schedule(
    data: ScheduledTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
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


@router.put(
    "/schedules/{task_id}",
    response_model=ScheduledTaskResponse,
    summary="Update a scheduled task",
    description="""
Update an existing scheduled task.

## Access Control
- **Minimum role**: Admin — resource management (create/delete/configure)
""",
)
async def update_schedule(
    task_id: str,
    data: ScheduledTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Met à jour une tâche planifiée."""
    service = SchedulerService(db)
    task = await service.update_task(task_id, **data.model_dump(exclude_none=True))
    if not task:
        raise NotFoundError("Tâche planifiée non trouvée")
    return task


@router.delete(
    "/schedules/{task_id}",
    status_code=204,
    summary="Delete a scheduled task",
    description="""
Delete a scheduled task permanently.

## Access Control
- **Minimum role**: Admin — resource management (create/delete/configure)
""",
)
async def delete_schedule(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Supprime une tâche planifiée."""
    service = SchedulerService(db)
    deleted = await service.delete_task(task_id)
    if not deleted:
        raise NotFoundError("Tâche planifiée non trouvée")


@router.post(
    "/schedules/{task_id}/toggle",
    response_model=ScheduledTaskResponse,
    summary="Toggle scheduled task activation",
    description="""
Enable or disable a scheduled task (operational activation action).

## Access Control
- **Minimum role**: Operator — operational action (enable/disable)
""",
)
async def toggle_schedule(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Active ou désactive une tâche planifiée."""
    service = SchedulerService(db)
    task = await service.toggle_task(task_id)
    if not task:
        raise NotFoundError("Tâche planifiée non trouvée")
    return task
