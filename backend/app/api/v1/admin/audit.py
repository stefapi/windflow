"""API de consultation de l'audit trail — Administration (STORY-125.3).

Endpoint super_admin exposant le journal d'audit posé par le socle
(STORY-125.1 — table ``audit_logs`` + ``AuditService``) et alimenté par
l'émission sur les actions critiques (STORY-125.2).

Sécurité (spec 08 § matrice, rules 40) :
- **Lecture uniquement** — l'audit n'est pas inscriptible par API (la
  donnée d'audit ne doit jamais être falsifiable depuis l'extérieur) ;
- ``require_super_admin`` : l'endpoint vit sous ``/admin/``
  (administration système = Super Admin — spec 08) ; viewer/operator et
  admin d'organisation reçoivent 403 ;
- filtres bornés (anti-abus — ``user_id`` ≤ 36, ``action`` ≤ 50,
  ``resource_type`` ≤ 30) et pagination plafonnée à 100 (rules 20) ;
- ``details`` est masqué **structurellement à l'écriture** par
  ``AuditService._sanitize_details`` (clés sensibles → ``***``) : la
  lecture restitue fidèlement des lignes déjà sûres ;
- aucun log de requête ne contient les entrées consultées.

Rétention : la purge périodique selon ``AUDIT_RETENTION_DAYS`` (défaut :
conservation indéfinie) est portée par la boucle lifespan dédiée de
``main.py`` (``_periodic_audit_purge``) — cet endpoint ne fait que
consulter.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....auth.rbac import require_super_admin
from ....database import get_db
from ....models.user import User
from ....schemas.audit import AuditLogListResponse
from ....services.audit_service import AuditService

router = APIRouter()


@router.get(
    "",
    response_model=AuditLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="Consult the audit trail (paginated, filterable)",
    description="""
Retrieve the security audit trail — who did what, when, on which target.

## Purpose
Answers incident-response and compliance questions: every critical
action (auth events, deletions, role changes, deployments, container and
plugin lifecycle) writes a line here with actor, organization, target
and the `X-Correlation-ID` of the triggering request.

## Access Control (spec 08 — System Administration)
- **Super Admin only**: this endpoint lives under `/admin/`
  (system-wide administration) — organization admins, operators and
  viewers receive `403`.

## Filters
- `user_id`: exact match on the actor (UUID)
- `action`: exact match on the action (catalog spec 15 — `user.login`,
  `stack.deleted`, `deployment.failed`…)
- `resource_type`: exact match on the target type (`stack`, `container`…)
- `since`: inclusive lower bound on `created_at` (ISO 8601 datetime)

## Pagination
`skip`/`limit` (max 100 per page), ordered by `created_at` descending —
most recent entries first.

## Note on `details`
Sensitive values (passwords, tokens, secrets…) are masked **at write
time** by the audit service (`***`) — this endpoint can never expose an
unmasked secret.

## Retention
Entries older than `AUDIT_RETENTION_DAYS` are purged periodically by a
dedicated background job (default: keep forever).
""",
    responses={
        200: {
            "description": (
                "Paginated audit entries — enveloppe spec 09 (page sous data)"
            ),
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "items": [
                                {
                                    "id": "3f1c9e2a-7b4d-4e8f-9a0b-1c2d3e4f5a6b",
                                    "user_id": "9d2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
                                    "organization_id": None,
                                    "action": "stack.deleted",
                                    "resource_type": "stack",
                                    "resource_id": "5a4b3c2d-1e0f-4a9b-8c7d-6e5f4a3b2c1d",
                                    "details": {"name": "production-nginx"},
                                    "ip_address": "203.0.113.10",
                                    "correlation_id": "f0e1d2c3-b4a5-4968-8776-5544332211ff",
                                    "created_at": "2026-09-25T14:22:05Z",
                                }
                            ],
                            "total": 128,
                            "skip": 0,
                            "limit": 100,
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
                            "message": "Not authenticated",
                        }
                    }
                }
            },
        },
        403: {
            "description": "Not a Super Admin (spec 08 — system administration)",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "PERMISSION_DENIED",
                            "message": "Not enough permissions",
                        }
                    }
                }
            },
        },
        422: {
            "description": "Invalid query parameter (since not ISO, limit out of bounds…)",
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
async def list_audit_entries(
    current_user: User = Depends(require_super_admin),
    user_id: Optional[str] = Query(
        None,
        max_length=36,
        description="Filter by actor (exact UUID)",
    ),
    action: Optional[str] = Query(
        None,
        max_length=50,
        description="Filter by action (exact — spec 15 catalog)",
    ),
    resource_type: Optional[str] = Query(
        None,
        max_length=30,
        description="Filter by target type (exact)",
    ),
    since: Optional[datetime] = Query(
        None,
        description="Inclusive lower bound on created_at (ISO 8601)",
    ),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=100, description="Page size (max 100)"),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """
    Liste les lignes d'audit, filtrées et paginées (``created_at`` desc).

    ## Access Control (STORY-125.3)

    Nécessite le rôle global ``super_admin`` — consultation système du
    journal complet (toutes organisations ; les admins d'org reçoivent
    403, spec 08 § Système).
    """
    entries, total = await AuditService.list_entries(
        db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        since=since,
        skip=skip,
        limit=limit,
    )
    return AuditLogListResponse(
        items=entries,  # type: ignore[arg-type]  # ORM → from_attributes
        total=total,
        skip=skip,
        limit=limit,
    )
