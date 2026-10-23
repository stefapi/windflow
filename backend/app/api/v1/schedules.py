"""
API endpoints pour la gestion des tâches planifiées (v2 — STORY-160.1).

Contrat spec 17 : ``action`` du registre canonique, ``trigger_type``
``cron``|``event``, ``event_name`` (∈ EventType spec 11), ``timezone``
IANA, ``error_policy``. Les 6 routes historiques sont inchangées
(garde-fou comptage de routes §2.G) — seule la payload évolue.

Audit (rules 40) : créations/modifications/suppressions/toggle tracés
via ``AuditService.log_from_request`` — ``parameters`` jamais loggés
bruts (``_sanitize_details`` structurel + on ne les passe pas).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.rbac import require_admin, require_operator, require_viewer
from ...core.exceptions import NotFoundError
from ...database import get_db
from ...helper.pagination import PaginationQuery, build_meta
from ...models.user import User
from ...schemas.common import PaginatedResponse
from ...schemas.scheduled_task import (
    ScheduledTaskCreate,
    ScheduledTaskResponse,
    ScheduledTaskUpdate,
)
from ...services.audit_service import AuditService
from ...services.scheduler_service import SchedulerService

router = APIRouter()

# Exemples OpenAPI (rules 20 : documentation riche — aucun secret).
_TASK_EXAMPLE = {
    "id": "3f2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
    "name": "prune-images-nuit",
    "description": "Nettoyage nocturne des images Docker inutilisées",
    "action": "compute.docker.prune",
    "trigger_type": "cron",
    "event_name": None,
    "timezone": "Europe/Paris",
    "error_policy": "retry",
    "cron_expression": "0 3 * * *",
    "parameters": {"resource": "images", "dry_run": True},
    "enabled": True,
    "last_run": None,
    "last_status": None,
    "last_error": None,
    "run_count": 0,
    "organization_id": "0f9e8d7c-6b5a-4c3d-2e1f-0a9b8c7d6e5f",
    "created_at": "2026-10-21T20:00:00Z",
    "updated_at": "2026-10-21T20:00:00Z",
}

_EVENT_TASK_EXAMPLE = {
    **_TASK_EXAMPLE,
    "id": "8a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
    "name": "notifier-echec-deploiement",
    "action": "notification.send",
    "trigger_type": "event",
    "event_name": "deployment.failed",
    "cron_expression": "0 * * * *",
    "parameters": {"channel": "webhook", "message": "Déploiement en échec"},
}

_ERROR_422_EXAMPLE = {
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Validation Error",
        "details": [
            {
                "loc": ["body", "cron_expression"],
                "msg": "Value error, Invalid cron expression: 'not-a-cron'",
                "type": "value_error",
            }
        ],
    }
}


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
                    "examples": {
                        "cron_task": {
                            "summary": "Tâche cron (prune Docker)",
                            "value": {
                                "data": [_TASK_EXAMPLE],
                                "pagination": {
                                    "page": 1,
                                    "per_page": 20,
                                    "total": 2,
                                    "pages": 1,
                                },
                                "message": None,
                            },
                        },
                        "event_task": {
                            "summary": "Tâche événement (notification)",
                            "value": {
                                "data": [_EVENT_TASK_EXAMPLE],
                                "pagination": {
                                    "page": 1,
                                    "per_page": 20,
                                    "total": 1,
                                    "pages": 1,
                                },
                                "message": None,
                            },
                        },
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
    tasks = await service.list_tasks(organization_id, page=page, per_page=per_page)
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
Retrieve a scheduled task by its ID (spec 17 definition: registry
action, cron|event trigger, IANA timezone, error policy).

## Access Control
- **Minimum role**: Viewer — read-only access for any authenticated user
""",
    responses={
        404: {
            "description": "Scheduled task not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Tâche planifiée non trouvée",
                        }
                    }
                }
            },
        },
    },
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
Create a new scheduled task (spec 17 — STORY-160.1).

The `action` must belong to the canonical action registry
(`host.scan`, `compute.docker.prune`, `stack.backup`, `admin.backup`,
`notification.send` — stubs carry `implemented=false` and fail
explicitly at execution, never silently succeed). `parameters` are
validated against the per-action Pydantic schema (422 otherwise).

## Validation (422 `VALIDATION_ERROR`)
- invalid cron expression (croniter) ;
- unknown IANA `timezone` ;
- unknown registry `action` ;
- `trigger_type='event'` without canonical `event_name` (spec 11) ;
- parameters rejected by the action schema.

## Access Control
- **Minimum role**: Admin — resource management (create/delete/configure)
""",
    responses={
        201: {
            "description": "Scheduled task created",
            "content": {
                "application/json": {
                    "examples": {
                        "cron_task": {
                            "summary": "Tâche cron (prune Docker, fuseau Paris)",
                            "value": _TASK_EXAMPLE,
                        },
                        "event_task": {
                            "summary": "Tâche événement (notification.send)",
                            "value": _EVENT_TASK_EXAMPLE,
                        },
                    }
                }
            },
        },
        422: {
            "description": "Semantic validation error (cron, timezone, action, event)",
            "content": {"application/json": {"example": _ERROR_422_EXAMPLE}},
        },
    },
)
async def create_schedule(
    data: ScheduledTaskCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Crée une nouvelle tâche planifiée (v2 — spec 17)."""
    service = SchedulerService(db)
    task = await service.create_task(
        name=data.name,
        action=data.action,
        cron_expression=data.cron_expression,
        organization_id=data.organization_id,
        description=data.description,
        parameters=data.parameters,
        enabled=data.enabled,
        trigger_type=data.trigger_type,
        event_name=data.event_name,
        timezone=data.timezone,
        error_policy=data.error_policy,
    )
    # Audit (rules 40) : jamais les parameters bruts dans les détails.
    await AuditService.log_from_request(
        request,
        "schedule.created",
        user=current_user,
        organization_id=task.organization_id,
        resource_type="scheduled_task",
        resource_id=task.id,
        details={
            "name": task.name,
            "action": task.action,
            "trigger_type": task.trigger_type,
            "enabled": task.enabled,
        },
        db=db,
    )
    return task


@router.put(
    "/schedules/{task_id}",
    response_model=ScheduledTaskResponse,
    summary="Update a scheduled task",
    description="""
Update an existing scheduled task (spec 17 — STORY-160.1).

Partial-update semantics: only provided fields are applied, with the
same validation as creation (registry action, croniter, IANA timezone,
canonical event). The merged definition is re-validated — an update
cannot corrupt trigger/event consistency.

## Access Control
- **Minimum role**: Admin — resource management (create/delete/configure)
""",
    responses={
        404: {
            "description": "Scheduled task not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Tâche planifiée non trouvée",
                        }
                    }
                }
            },
        },
        422: {
            "description": "Semantic validation error (merged definition invalid)",
            "content": {"application/json": {"example": _ERROR_422_EXAMPLE}},
        },
    },
)
async def update_schedule(
    task_id: str,
    data: ScheduledTaskUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Met à jour une tâche planifiée (définition fusionnée revalidée)."""
    service = SchedulerService(db)
    task = await service.update_task(task_id, **data.model_dump(exclude_none=True))
    if not task:
        raise NotFoundError("Tâche planifiée non trouvée")
    await AuditService.log_from_request(
        request,
        "schedule.updated",
        user=current_user,
        organization_id=task.organization_id,
        resource_type="scheduled_task",
        resource_id=task.id,
        details={
            "name": task.name,
            "action": task.action,
            "trigger_type": task.trigger_type,
            "enabled": task.enabled,
        },
        db=db,
    )
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
    responses={
        404: {
            "description": "Scheduled task not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Tâche planifiée non trouvée",
                        }
                    }
                }
            },
        },
    },
)
async def delete_schedule(
    task_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Supprime une tâche planifiée."""
    service = SchedulerService(db)
    task = await service.get_task(task_id)
    if not task:
        raise NotFoundError("Tâche planifiée non trouvée")
    org_id = task.organization_id
    task_name = task.name
    deleted = await service.delete_task(task_id)
    if not deleted:
        raise NotFoundError("Tâche planifiée non trouvée")
    await AuditService.log_from_request(
        request,
        "schedule.deleted",
        user=current_user,
        organization_id=org_id,
        resource_type="scheduled_task",
        resource_id=task_id,
        details={"name": task_name},
        db=db,
    )


@router.post(
    "/schedules/{task_id}/toggle",
    response_model=ScheduledTaskResponse,
    summary="Toggle scheduled task activation",
    description="""
Enable or disable a scheduled task (operational activation action).

## Access Control
- **Minimum role**: Operator — operational action (enable/disable)
""",
    responses={
        404: {
            "description": "Scheduled task not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Tâche planifiée non trouvée",
                        }
                    }
                }
            },
        },
    },
)
async def toggle_schedule(
    task_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Active ou désactive une tâche planifiée."""
    service = SchedulerService(db)
    task = await service.toggle_task(task_id)
    if not task:
        raise NotFoundError("Tâche planifiée non trouvée")
    await AuditService.log_from_request(
        request,
        "schedule.toggled",
        user=current_user,
        organization_id=task.organization_id,
        resource_type="scheduled_task",
        resource_id=task.id,
        details={"name": task.name, "enabled": task.enabled},
        db=db,
    )
    return task
