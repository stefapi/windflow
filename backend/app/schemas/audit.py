"""Schemas Pydantic V2 de consultation de l'audit trail (STORY-125.1).

Schemas **en lecture uniquement** : l'audit n'est pas inscriptible par
API (écriture interne via ``AuditService.log()`` uniquement — la donnée
d'audit ne doit jamais être falsifiable depuis l'extérieur).

Sécurité (rules 40) :
- ``AuditLogResponse`` restitue fidèlement la ligne persistée : le
  masquage des secrets est structurel **à l'écriture**
  (``AuditService._sanitize_details`` — clés sensibles → ``***``), la
  lecture n'a donc jamais de champ non masqué à filtrer ;
- aucun endpoint d'écriture ne consomme ces schemas.

Consommé par l'endpoint admin de consultation (STORY-125.3 —
``GET /api/v1/admin/audit``, super_admin uniquement).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    """Schema de réponse d'une ligne d'audit.

    ``details`` est masqué à l'écriture par ``AuditService`` (clés
    sensibles → ``***``) : la valeur restituée ici est déjà sûre.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "3f1c9e2a-7b4d-4e8f-9a0b-1c2d3e4f5a6b",
                "user_id": "9d2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
                "organization_id": "c8e7d6f5-a4b3-4c2d-1e0f-9a8b7c6d5e4f",
                "action": "stack.deleted",
                "resource_type": "stack",
                "resource_id": "5a4b3c2d-1e0f-4a9b-8c7d-6e5f4a3b2c1d",
                "details": {"stack_name": "production-nginx"},
                "ip_address": "203.0.113.10",
                "correlation_id": "f0e1d2c3-b4a5-4968-8776-5544332211ff",
                "created_at": "2026-09-25T14:22:05Z",
            }
        },
    )

    id: str = Field(
        ...,
        description="ID unique de la ligne d'audit",
        json_schema_extra={"example": "3f1c9e2a-7b4d-4e8f-9a0b-1c2d3e4f5a6b"},
    )
    user_id: Optional[str] = Field(
        None,
        description="Acteur de l'action (null : acteur système ou compte "
        "supprimé — conservation documentaire)",
        json_schema_extra={"example": "9d2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b"},
    )
    organization_id: Optional[str] = Field(
        None,
        description="Organisation concernée par l'action (null si globale)",
        json_schema_extra={"example": "c8e7d6f5-a4b3-4c2d-1e0f-9a8b7c6d5e4f"},
    )
    action: str = Field(
        ...,
        description="Action auditée — catalogue spec 15 (user.login, "
        "stack.deleted…)",
        json_schema_extra={"example": "stack.deleted"},
    )
    resource_type: Optional[str] = Field(
        None,
        description="Type de la cible (stack, container, user…)",
        json_schema_extra={"example": "stack"},
    )
    resource_id: Optional[str] = Field(
        None,
        description="Identifiant de la cible",
        json_schema_extra={"example": "5a4b3c2d-1e0f-4a9b-8c7d-6e5f4a3b2c1d"},
    )
    details: Optional[dict] = Field(
        None,
        description="Contexte JSON — masqué à l'écriture par le service "
        "(secrets → ***)",
        json_schema_extra={"example": {"stack_name": "production-nginx"}},
    )
    ip_address: Optional[str] = Field(
        None,
        description="IP source de l'action",
        json_schema_extra={"example": "203.0.113.10"},
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID de la requête (X-Correlation-ID)",
        json_schema_extra={"example": "f0e1d2c3-b4a5-4968-8776-5544332211ff"},
    )
    created_at: datetime = Field(
        ...,
        description="Horodatage de l'action",
        json_schema_extra={"example": "2026-09-25T14:22:05Z"},
    )


class AuditLogListResponse(BaseModel):
    """Réponse paginée pour la consultation de l'audit trail.

    Pattern ``{items, total, skip, limit}`` (``DeploymentListResponse``) ;
    les bornes de pagination sont posées côté endpoint (STORY-125.3).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "3f1c9e2a-7b4d-4e8f-9a0b-1c2d3e4f5a6b",
                        "user_id": "9d2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
                        "organization_id": None,
                        "action": "user.login",
                        "resource_type": None,
                        "resource_id": None,
                        "details": None,
                        "ip_address": "203.0.113.10",
                        "correlation_id": "f0e1d2c3-b4a5-4968-8776-5544332211ff",
                        "created_at": "2026-09-25T14:22:05Z",
                    }
                ],
                "total": 128,
                "skip": 0,
                "limit": 100,
            }
        }
    )

    items: list[AuditLogResponse] = Field(
        ...,
        description="Lignes d'audit de la page courante",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Nombre total de lignes correspondant aux filtres",
        json_schema_extra={"example": 128},
    )
    skip: int = Field(
        ...,
        ge=0,
        description="Offset de la page courante",
        json_schema_extra={"example": 0},
    )
    limit: int = Field(
        ...,
        ge=1,
        description="Taille de la page courante",
        json_schema_extra={"example": 100},
    )
