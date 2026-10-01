"""
Schemas Pydantic V2 communs et partagés.

STORY-126.1 : enveloppes de réponse spec 09 (§ Format de réponse) —

- Succès : ``{"data": ..., "message": ...}`` (``APIResponse``) ;
- Listes paginées : ``{"data": [...], "pagination": {...}}``
  (``PaginatedResponse`` + ``PaginationMeta``) ;
- Erreurs : ``{"error": {"code": ..., "message": ..., "details"?}}``
  (``ErrorResponse`` + ``ErrorDetail``).

Ces enveloppes sont systématiques depuis STORY-126.2 (défaut actif) ;
le flag transitoire ``API_ENVELOPE_ENABLED`` a été retiré par
STORY-126.3 — il n'existe plus de mode legacy.
"""

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PaginationMeta(BaseModel):
    """
    Métadonnées de pagination spec 09 (modèle ``page``/``per_page``).

    Contra à l'ancien format interne ``skip``/``limit`` — les listes
    paginées exposent des pages 1-indexées.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"page": 1, "per_page": 20, "total": 87, "pages": 5}
        }
    )

    page: int = Field(
        ...,
        ge=1,
        description="Numéro de la page courante (1-indexé)",
        json_schema_extra={"example": 1},
    )
    per_page: int = Field(
        ...,
        ge=1,
        description="Nombre d'éléments par page",
        json_schema_extra={"example": 20},
    )
    total: int = Field(
        ...,
        ge=0,
        description="Nombre total d'éléments disponibles",
        json_schema_extra={"example": 87},
    )
    pages: int = Field(
        ...,
        ge=0,
        description="Nombre total de pages",
        json_schema_extra={"example": 5},
    )


class APIResponse(BaseModel):
    """
    Enveloppe de réponse standard spec 09.

    Toute réponse 2xx JSON de ``/api/v1/*`` est transportée sous
    ``data`` ; ``message`` porte un message optionnel (``null`` par
    défaut, alimenté par le header interne ``X-API-Message``).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": {"id": "app_nextcloud", "status": "running"},
                "message": None,
            }
        }
    )

    data: Any = Field(
        default=None,
        description="Charge utile de la réponse (objet, liste ou scalaire)",
        json_schema_extra={"example": {"id": "app_nextcloud", "status": "running"}},
    )
    message: Optional[str] = Field(
        default=None,
        description="Message optionnel de la réponse (null par défaut)",
        json_schema_extra={"example": None},
    )


class PaginatedResponse(BaseModel):
    """
    Enveloppe de réponse liste paginée spec 09.

    La liste vit sous ``data`` ; les métadonnées de pagination sous
    ``pagination`` (modèle :doc:`PaginationMeta`).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [{"id": "app_nextcloud"}, {"id": "app_pihole"}],
                "pagination": {"page": 1, "per_page": 20, "total": 87, "pages": 5},
            }
        }
    )

    data: List[Any] = Field(
        ...,
        description="Liste des éléments de la page courante",
        json_schema_extra={"example": [{"id": "app_nextcloud"}]},
    )
    pagination: PaginationMeta = Field(
        ...,
        description="Métadonnées de pagination",
    )


class ErrorDetail(BaseModel):
    """
    Détail d'une erreur spec 09 (§ Gestion des erreurs).

    ``code`` est un code machine stable (ex. ``NOT_FOUND``,
    ``VALIDATION_ERROR``) ; ``message`` un message lisible ;
    ``details`` optionnel porte le contexte structuré (ex. liste
    d'erreurs Pydantic pour les 422).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "NOT_FOUND",
                "message": "App not found: abc123",
                "details": None,
            }
        }
    )

    code: str = Field(
        ...,
        description="Code d'erreur machine stable (spec 09)",
        json_schema_extra={"example": "NOT_FOUND"},
    )
    message: str = Field(
        ...,
        description="Message d'erreur lisible",
        json_schema_extra={"example": "App not found: abc123"},
    )
    details: Optional[dict] = Field(
        default=None,
        description="Contexte structuré optionnel (ex. erreurs de validation Pydantic)",
        json_schema_extra={
            "example": {
                "field": "name",
                "issue": "String should have at least 1 character",
            }
        },
    )


class ErrorResponse(BaseModel):
    """
    Enveloppe d'erreur spec 09.

    Toutes les réponses d'erreur ``/api/v1/*`` (4xx/5xx) suivent ce
    format ; un ``correlation_id`` top-level est ajouté par le handler
    pour le traçage distribué.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "NOT_FOUND",
                    "message": "App not found: abc123",
                },
                "correlation_id": "abc12345-6789-def0-1234-567890abcdef",
            }
        }
    )

    error: ErrorDetail = Field(
        ...,
        description="Détail de l'erreur (code, message, détails optionnels)",
    )


class HealthResponse(BaseModel):
    """
    Réponse du endpoint de santé.

    Retourné par GET /health pour les systèmes de monitoring
    et les load balancers (hors périmètre enveloppes — jamais
    enveloppé, cf. STORY-126.1 garde-fous).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "environment": "production",
                "services": {
                    "database": {"status": "healthy", "type": "postgresql"},
                    "rate_limiter": {"status": "healthy"},
                },
            }
        }
    )

    status: str = Field(
        ...,
        description="Statut global (healthy ou unhealthy)",
        json_schema_extra={"example": "healthy"},
    )
    version: str = Field(
        ...,
        description="Version de l'application",
        json_schema_extra={"example": "1.0.0"},
    )
    environment: str = Field(
        ...,
        description="Environnement d'exécution",
        json_schema_extra={"example": "production"},
    )
    services: dict = Field(
        default_factory=dict,
        description="Statut des services dépendants",
        json_schema_extra={"example": {"database": {"status": "healthy"}}},
    )
