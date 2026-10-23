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

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.rbac import require_admin, require_operator, require_viewer
from ...core.exceptions import NotFoundError
from ...database import get_db
from ...helper.pagination import PaginationQuery, build_meta
from ...models.scheduled_task import ScheduledTask
from ...models.scheduled_task_execution import ScheduledTaskExecution
from ...models.user import User
from ...schemas.common import PaginatedResponse
from ...schemas.scheduled_task import (
    ScheduledTaskCreate,
    ScheduledTaskResponse,
    ScheduledTaskUpdate,
)
from ...schemas.scheduled_task_execution import (
    ManualRunResponse,
    ScheduledTaskExecutionListItem,
    ScheduledTaskExecutionResponse,
)
from ...services.audit_service import AuditService
from ...services.scheduler_service import SchedulerService

if TYPE_CHECKING:
    # Référence de type uniquement (évite un import circulaire au runtime).
    from ...services.scheduler_engine import SchedulerEngine

router = APIRouter()


def get_scheduler_engine() -> "SchedulerEngine":
    """Fournit le moteur scheduler pour le run manuel (dépendance injectable).

    Même configuration que le lifespan (STORY-161 tâche 8) : moteur
    branché sur :class:`DatabaseExecutionStore` — chemin d'exécution
    canonique (tâche dédiée, verrou, timeout, politique d'erreur). Les
    tests surchargent cette dépendance (pattern ``get_db``) pour injecter
    un moteur branché sur la base de test.
    """
    from ...services.scheduler_engine import SchedulerEngine
    from ...services.scheduler_execution_store import DatabaseExecutionStore

    return SchedulerEngine(store=DatabaseExecutionStore())


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


# --- STORY-161 : exécutions (consultation + run manuel) -----------------------
#
# ⚠ Ordre des routes : ``/schedules/executions`` et
# ``/schedules/executions/{execution_id}`` sont déclarées AVANT les routes
# paramétrées ``/schedules/{task_id}`` (matching dans l'ordre
# d'enregistrement — sinon « executions » capturerait le ``{task_id}``).
# ``/schedules/{task_id}/executions`` et ``/schedules/{task_id}/run`` ne
# présentent pas d'ambiguïté (segment suffixé distinct).

_EXECUTION_EXAMPLE = {
    "id": "b4e1c0a2-9f3d-4c5b-8e7a-1d2f3a4b5c6d",
    "task_id": "3f2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
    "status": "success",
    "triggered_by": "cron",
    "started_at": "2026-10-23T03:00:00.100000+00:00",
    "finished_at": "2026-10-23T03:00:42.500000+00:00",
    "duration_seconds": 42.4,
    "error": None,
    "created_at": "2026-10-23T03:00:00.050000+00:00",
}

_EXECUTION_LIST_EXAMPLE = {
    "data": [{**_EXECUTION_EXAMPLE, "status": "failed", "error": "ValueError: x..."}],
    "pagination": {"page": 1, "per_page": 20, "total": 87, "pages": 5},
    "message": None,
}

_EXECUTION_DETAIL_EXAMPLE = {
    **_EXECUTION_EXAMPLE,
    "logs": [
        {
            "timestamp": "2026-10-23T03:00:00.100000+00:00",
            "message": "queued (triggered_by=schedule)",
        },
        {"timestamp": "2026-10-23T03:00:00.150000+00:00", "message": "running"},
        {
            "timestamp": "2026-10-23T03:00:42.500000+00:00",
            "message": "success (42.400s)",
        },
    ],
}

_MANUAL_RUN_EXAMPLE = {
    "execution_id": "c5f2d1b3-8a4e-4b6c-9d0a-2e3f4a5b6c7e",
    "status": "queued",
    "triggered_by": "manual",
}


def _decode_execution_logs(execution: ScheduledTaskExecution) -> list[dict]:
    """Décode la colonne ``logs`` JSON (tolère vide/corrompu — [])."""
    import json

    raw = execution.logs
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _execution_list_item(execution: ScheduledTaskExecution) -> dict:
    """Sérialise une exécution ORM en item de liste (sans ``logs``)."""
    return ScheduledTaskExecutionListItem.model_validate(execution).model_dump()


def _execution_response(execution: ScheduledTaskExecution) -> dict:
    """Sérialise une exécution ORM en payload détaillé (journal décodé)."""
    item = ScheduledTaskExecutionListItem.model_validate(execution).model_dump()
    item["logs"] = _decode_execution_logs(execution)
    return item


def _executions_base_query(
    task_id: Optional[str],
    organization_id: Optional[str],
    status: Optional[str],
    triggered_by: Optional[str],
):
    """Requête de base de la vue globale (filtres communs liste/comptage)."""
    query = select(ScheduledTaskExecution)
    if task_id:
        query = query.where(ScheduledTaskExecution.task_id == task_id)
    if status:
        query = query.where(ScheduledTaskExecution.status == status)
    if triggered_by:
        query = query.where(ScheduledTaskExecution.triggered_by == triggered_by)
    if organization_id:
        query = query.join(ScheduledTask).where(
            ScheduledTask.organization_id == organization_id
        )
    return query


async def _count_executions(
    db: AsyncSession,
    task_id: Optional[str],
    organization_id: Optional[str],
    status: Optional[str],
    triggered_by: Optional[str],
) -> int:
    """``COUNT`` avec les mêmes filtres que la liste (pas d'oracle)."""
    from sqlalchemy import func

    base = _executions_base_query(task_id, organization_id, status, triggered_by)
    if organization_id:
        # Le join est requis pour le filtre organisation : reproduire la
        # construction plutôt que réutiliser l'objet select (with_only_columns
        # sur une requête joinée réécrit le FROM de façon non portable).
        count_query = (
            select(func.count())
            .select_from(ScheduledTaskExecution)
            .join(ScheduledTask)
            .where(ScheduledTask.organization_id == organization_id)
        )
        if task_id:
            count_query = count_query.where(ScheduledTaskExecution.task_id == task_id)
        if status:
            count_query = count_query.where(ScheduledTaskExecution.status == status)
        if triggered_by:
            count_query = count_query.where(
                ScheduledTaskExecution.triggered_by == triggered_by
            )
        query = count_query
    else:
        query = base.with_only_columns(func.count())
    result = await db.execute(query)
    return int(result.scalar() or 0)


@router.get(
    "/schedules/executions",
    response_model=PaginatedResponse,
    summary="List all scheduled task executions (global activity view)",
    description="""
Global filtered view of scheduled task executions across all definitions
(spec 17 § Gestion des tâches — écran Activité). Filters are combined:
`status`, `triggered_by`, `started_after`/`started_before` (ISO 8601),
`task_id`, and optional `organization_id` (executions inherit their
task's organization — same pattern as `GET /schedules`).

## Ordering & pagination
- **Stable order**: `started_at DESC` (most recent first)
- `?page=1&per_page=20` (max 100) — STORY-128 envelope, `total` scoped
  to the same filters

## Validation (422 `VALIDATION_ERROR`)
- unknown `status` / `triggered_by` value (closed domains spec 06)
- invalid ISO 8601 date in `started_after`/`started_before`

## Access Control
- **Minimum role**: Viewer — read-only access for any authenticated user
""",
    responses={
        200: {
            "description": "Paginated executions — enveloppe spec 09",
            "content": {"application/json": {"example": _EXECUTION_LIST_EXAMPLE}},
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
        422: {
            "description": "Invalid filter value (status/triggered_by/date)",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Validation Error",
                        }
                    }
                }
            },
        },
    },
)
async def list_executions_global(
    status: Optional[str] = Query(
        None,
        pattern="^(queued|running|success|failed|skipped)$",
        description="Filter by execution status (spec 06 closed domain).",
    ),
    triggered_by: Optional[str] = Query(
        None,
        pattern="^(cron|event|manual)$",
        description="Filter by trigger origin (spec 06 closed domain).",
    ),
    started_after: Optional[datetime] = Query(
        None, description="ISO 8601 — executions started at or after."
    ),
    started_before: Optional[datetime] = Query(
        None, description="ISO 8601 — executions started at or before."
    ),
    task_id: Optional[str] = Query(None, description="Filter by task definition."),
    organization_id: Optional[str] = Query(
        None, description="Filter by the task's organization."
    ),
    page: int = PaginationQuery.page,
    per_page: int = PaginationQuery.per_page,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    """Vue globale filtrable des exécutions (spec 17 — écran Activité)."""
    query = _executions_base_query(task_id, organization_id, status, triggered_by)
    if started_after is not None:
        query = query.where(ScheduledTaskExecution.started_at >= started_after)
    if started_before is not None:
        query = query.where(ScheduledTaskExecution.started_at <= started_before)
    query = query.order_by(ScheduledTaskExecution.started_at.desc())
    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    executions = list(result.scalars().all())
    total = await _count_executions(db, task_id, organization_id, status, triggered_by)
    data: List[dict] = [_execution_list_item(e) for e in executions]
    return PaginatedResponse(data=data, pagination=build_meta(page, per_page, total))


@router.get(
    "/schedules/executions/{execution_id}",
    response_model=ScheduledTaskExecutionResponse,
    summary="Get a scheduled task execution by ID (with logs)",
    description="""
Retrieve the full detail of a single execution: status, `triggered_by`,
`duration_seconds`, sanitized `error` (rules 40 — never a raw stack trace)
and the complete line-by-line timestamped log (ISO 8601 UTC, spec 06).

## Access Control
- **Minimum role**: Viewer — read-only access for any authenticated user
""",
    responses={
        404: {
            "description": "Execution not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Exécution non trouvée",
                        }
                    }
                }
            },
        },
    },
)
async def get_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    """Détail d'une exécution avec journal complet."""
    execution = await db.get(ScheduledTaskExecution, execution_id)
    if execution is None:
        raise NotFoundError("Exécution non trouvée")
    return _execution_response(execution)


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


@router.get(
    "/schedules/{task_id}/executions",
    response_model=PaginatedResponse,
    summary="List executions of a scheduled task",
    description="""
Paginated execution history of one scheduled task definition — the
backing data of the spec 17 activity view. Stable order `started_at DESC`
(most recent first); light items **without** `logs` (fetch the execution
detail for the full journal).

## Access Control
- **Minimum role**: Viewer — read-only access for any authenticated user
""",
    responses={
        200: {
            "description": "Paginated executions of the task",
            "content": {
                "application/json": {
                    "example": {
                        "data": [_EXECUTION_EXAMPLE],
                        "pagination": {
                            "page": 1,
                            "per_page": 20,
                            "total": 3,
                            "pages": 1,
                        },
                        "message": None,
                    }
                }
            },
        },
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
async def list_task_executions(
    task_id: str,
    page: int = PaginationQuery.page,
    per_page: int = PaginationQuery.per_page,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    """Historique paginé des exécutions d'une définition."""
    task = await db.get(ScheduledTask, task_id)
    if task is None:
        raise NotFoundError("Tâche planifiée non trouvée")
    from sqlalchemy import func

    base = select(ScheduledTaskExecution).where(
        ScheduledTaskExecution.task_id == task_id
    )
    result = await db.execute(
        base.order_by(ScheduledTaskExecution.started_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    executions = list(result.scalars().all())
    count = await db.execute(
        select(func.count())
        .select_from(ScheduledTaskExecution)
        .where(ScheduledTaskExecution.task_id == task_id)
    )
    total = int(count.scalar() or 0)
    data: List[dict] = [_execution_list_item(e) for e in executions]
    return PaginatedResponse(data=data, pagination=build_meta(page, per_page, total))


@router.post(
    "/schedules/{task_id}/run",
    response_model=ManualRunResponse,
    status_code=202,
    summary="Trigger a scheduled task manually (fire-and-forget)",
    description="""
Trigger the immediate execution of a scheduled task through the engine's
canonical execution path (dedicated asyncio task, anti-overlap lock,
timeout, error policy, ExecutionStore — same guarantees as the cron
path). Returns **202 Accepted** immediately with the `queued` execution
identifier: the response never waits for completion.

## Behaviour
- unknown or disabled task → **404** (no execution row created)
- task already running → **409** (the skip is traced as a `skipped`
  execution row)

## Access Control
- **Minimum role**: Operator — operational action (symmetry with toggle)

## Audit
`schedule.manual_run` (task name/action/organization — never the raw
`parameters`, rules 40)
""",
    responses={
        202: {
            "description": "Execution queued (fire-and-forget)",
            "content": {"application/json": {"example": _MANUAL_RUN_EXAMPLE}},
        },
        404: {
            "description": "Scheduled task not found or disabled",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Tâche planifiée inconnue ou désactivée",
                        }
                    }
                }
            },
        },
        409: {
            "description": "An execution of this task is already running",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "CONFLICT",
                            "message": "Une exécution de cette tâche est déjà en cours",
                        }
                    }
                }
            },
        },
    },
)
async def run_schedule_now(
    task_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
    engine: "SchedulerEngine" = Depends(get_scheduler_engine),
):
    """Déclenche l'exécution immédiate d'une tâche (202 fire-and-forget)."""
    task = await db.get(ScheduledTask, task_id)
    if task is None:
        raise NotFoundError("Tâche planifiée non trouvée")
    # Moteur fourni par ``get_scheduler_engine`` (même configuration que
    # le lifespan — store DB, chemin d'exécution canonique) ; jamais
    # d'exécution inline dans la requête (tâche dédiée, verrou, timeout).
    execution_id = await engine.run_task_now(task_id)
    await engine.wait_for_executions()
    await AuditService.log_from_request(
        request,
        "schedule.manual_run",
        user=current_user,
        organization_id=task.organization_id,
        resource_type="scheduled_task",
        resource_id=task.id,
        # Rules 40 : jamais les parameters bruts dans l'audit.
        details={"name": task.name, "action": task.action},
        db=db,
    )
    return ManualRunResponse(execution_id=execution_id)


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
