"""
Schemas Pydantic V2 communs et partagés.

Modèles génériques pour la pagination, les réponses d'erreur
et les structures de données partagées entre les endpoints.
"""

from datetime import datetime
from typing import Optional, List, Any, Generic, TypeVar
from pydantic import BaseModel, Field, ConfigDict


T = TypeVar("T")


class PaginationParams(BaseModel):
    """
    Paramètres de pagination pour les requêtes de liste.

    Utilisé dans les query parameters des endpoints GET
    qui retournent des listes paginées.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "skip": 0,
                    "limit": 20
                },
                {
                    "skip": 40,
                    "limit": 20
                },
                {
                    "skip": 0,
                    "limit": 100
                }
            ]
        }
    )

    skip: int = Field(
        default=0,
        ge=0,
        description="Nombre d'éléments à ignorer (offset)",
        json_schema_extra={"example": 0}
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Nombre maximum d'éléments à retourner (1-100)",
        json_schema_extra={"example": 20}
    )


class PaginatedResponse(BaseModel):
    """
    Réponse paginée générique.

    Encapsule une liste d'éléments avec les métadonnées
    de pagination (total, skip, limit).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 42,
                "skip": 0,
                "limit": 20,
                "has_more": True
            }
        }
    )

    items: List[Any] = Field(
        ...,
        description="Liste des éléments de la page courante"
    )
    total: int = Field(
        ...,
        ge=0,
        description="Nombre total d'éléments disponibles",
        json_schema_extra={"example": 42}
    )
    skip: int = Field(
        ...,
        ge=0,
        description="Offset de la page courante",
        json_schema_extra={"example": 0}
    )
    limit: int = Field(
        ...,
        ge=1,
        description="Taille de la page courante",
        json_schema_extra={"example": 20}
    )
    has_more: bool = Field(
        ...,
        description="Indique s'il existe d'autres pages",
        json_schema_extra={"example": True}
    )


class ErrorResponse(BaseModel):
    """
    Format standard de réponse d'erreur.

    Utilisé pour toutes les réponses d'erreur HTTP (4xx, 5xx).
    Inclut un identifiant de corrélation pour le traçage distribué.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "error": "Not Found",
                    "detail": "Deployment with ID '550e8400-e29b-41d4-a716-446655440000' not found",
                    "correlation_id": "abc12345-6789-def0-1234-567890abcdef",
                    "timestamp": "2026-01-02T22:30:00Z"
                },
                {
                    "error": "Validation Error",
                    "detail": [
                        {
                            "loc": ["body", "name"],
                            "msg": "String should have at least 1 character",
                            "type": "string_too_short"
                        }
                    ],
                    "correlation_id": "def45678-9012-abc3-4567-890123456789",
                    "timestamp": "2026-01-02T22:31:00Z"
                },
                {
                    "error": "Unauthorized",
                    "detail": "Invalid or expired token",
                    "correlation_id": "ghi78901-2345-def6-7890-123456789abc",
                    "timestamp": "2026-01-02T22:32:00Z"
                }
            ]
        }
    )

    error: str = Field(
        ...,
        description="Type d'erreur (ex: Not Found, Validation Error, Unauthorized)",
        json_schema_extra={"example": "Not Found"}
    )
    detail: Any = Field(
        ...,
        description="Détails de l'erreur (string ou liste d'erreurs de validation)",
        json_schema_extra={"example": "Resource not found"}
    )
    correlation_id: Optional[str] = Field(
        None,
        description="ID de corrélation pour le traçage distribué",
        json_schema_extra={"example": "abc12345-6789-def0-1234-567890abcdef"}
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Horodatage de l'erreur",
        json_schema_extra={"example": "2026-01-02T22:30:00Z"}
    )


class HealthResponse(BaseModel):
    """
    Réponse du endpoint de santé.

    Retourné par GET /health pour les systèmes de monitoring
    et les load balancers.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "environment": "production",
                "services": {
                    "database": {"status": "healthy", "type": "postgresql"},
                    "rate_limiter": {"status": "healthy"}
                }
            }
        }
    )

    status: str = Field(
        ...,
        description="Statut global (healthy ou unhealthy)",
        json_schema_extra={"example": "healthy"}
    )
    version: str = Field(
        ...,
        description="Version de l'application",
        json_schema_extra={"example": "1.0.0"}
    )
    environment: str = Field(
        ...,
        description="Environnement d'exécution",
        json_schema_extra={"example": "production"}
    )
    services: dict = Field(
        default_factory=dict,
        description="Statut des services dépendants",
        json_schema_extra={"example": {"database": {"status": "healthy"}}}
    )
