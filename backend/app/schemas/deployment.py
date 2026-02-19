"""
Schemas Pydantic V2 pour l'entité Deployment.

Validation stricte avec type hints obligatoires selon backend.md.
Chaque modèle inclut model_config avec exemples et json_schema_extra
pour une documentation OpenAPI complète.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DeploymentStatus(str, Enum):
    """Statuts possibles pour un déploiement.

    - PENDING: En attente de traitement
    - DEPLOYING: Déploiement en cours
    - RUNNING: Déploiement actif et fonctionnel
    - FAILED: Déploiement échoué
    - STOPPED: Déploiement arrêté manuellement
    - ROLLING_BACK: Retour en arrière en cours
    """
    PENDING = "pending"
    DEPLOYING = "deploying"
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"
    ROLLING_BACK = "rolling_back"


class DeploymentBase(BaseModel):
    """Schema de base pour Deployment."""
    pass


class DeploymentCreate(DeploymentBase):
    """
    Schema pour création de déploiement.

    Définit les paramètres requis et optionnels pour créer
    un nouveau déploiement. Les déploiements sont des opérations
    asynchrones traçables via WebSocket ou polling.

    **Règles de validation:**
    - stack_id: Doit référencer un stack existant
    - target_id: Doit référencer une cible de déploiement existante
    - name: 1-255 caractères (auto-généré si absent)
    - variables: Utilise les défauts du stack si absent
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "stack_id": "550e8400-e29b-41d4-a716-446655440000",
                    "target_id": "660e8400-e29b-41d4-a716-446655440001",
                    "name": "production-nginx",
                    "variables": {
                        "port": 8080,
                        "domain": "app.example.com"
                    }
                },
                {
                    "stack_id": "550e8400-e29b-41d4-a716-446655440000",
                    "target_id": "660e8400-e29b-41d4-a716-446655440001",
                    "name": "staging-api",
                    "config": {
                        "scale": {"web": 2}
                    },
                    "variables": {
                        "environment": "staging",
                        "debug": True
                    }
                },
                {
                    "stack_id": "770e8400-e29b-41d4-a716-446655440002",
                    "target_id": "880e8400-e29b-41d4-a716-446655440003"
                }
            ]
        }
    )

    stack_id: str = Field(
        ...,
        description="ID du stack à déployer",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"}
    )
    target_id: str = Field(
        ...,
        description="ID de la cible de déploiement",
        json_schema_extra={"example": "660e8400-e29b-41d4-a716-446655440001"}
    )
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Nom du déploiement (auto-généré si absent)",
        json_schema_extra={"example": "production-nginx"}
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Configuration du déploiement (générée depuis le template si absente)",
        json_schema_extra={"example": {"ports": [80, 443], "environment": {"NODE_ENV": "production"}}}
    )
    variables: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Variables à appliquer (utilise les defaults du stack si absent)",
        json_schema_extra={"example": {"port": 8080, "domain": "app.example.com"}}
    )


class DeploymentUpdate(BaseModel):
    """
    Schema pour mise à jour de déploiement.

    Tous les champs sont optionnels. Seuls les champs fournis
    seront mis à jour.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "production-nginx-v2",
                    "variables": {"port": 9090}
                },
                {
                    "status": "stopped"
                },
                {
                    "name": "updated-deployment",
                    "variables": {"debug": False},
                    "error_message": None
                }
            ]
        }
    )

    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Nouveau nom",
        json_schema_extra={"example": "production-nginx-v2"}
    )
    status: Optional[DeploymentStatus] = Field(
        None,
        description="Nouveau statut",
        json_schema_extra={"example": "running"}
    )
    variables: Optional[Dict[str, Any]] = Field(
        None,
        description="Nouvelles variables",
        json_schema_extra={"example": {"port": 9090}}
    )
    logs: Optional[str] = Field(
        None,
        description="Logs du déploiement",
        json_schema_extra={"example": "Deploying... Done."}
    )
    error_message: Optional[str] = Field(
        None,
        description="Message d'erreur",
        json_schema_extra={"example": "Connection refused on port 8080"}
    )


class DeploymentResponse(BaseModel):
    """
    Schema pour réponse Deployment.

    Retourné après création réussie ou lors de la consultation
    du statut d'un déploiement. Inclut toutes les métadonnées
    et le statut actuel.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "990e8400-e29b-41d4-a716-446655440000",
                "name": "production-nginx",
                "stack_id": "550e8400-e29b-41d4-a716-446655440000",
                "target_id": "660e8400-e29b-41d4-a716-446655440001",
                "status": "running",
                "config": {"ports": [80, 443]},
                "variables": {"port": 8080, "domain": "app.example.com"},
                "logs": "Deploying... Container started. Health check OK.",
                "error_message": None,
                "deployed_at": "2026-01-02T22:35:00Z",
                "created_at": "2026-01-02T22:30:00Z",
                "updated_at": "2026-01-02T22:35:00Z"
            }
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Nom du déploiement",
        json_schema_extra={"example": "production-nginx"}
    )
    id: str = Field(
        ...,
        description="ID unique du déploiement",
        json_schema_extra={"example": "990e8400-e29b-41d4-a716-446655440000"}
    )
    stack_id: str = Field(
        ...,
        description="ID du stack",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"}
    )
    target_id: str = Field(
        ...,
        description="ID de la cible",
        json_schema_extra={"example": "660e8400-e29b-41d4-a716-446655440001"}
    )
    status: DeploymentStatus = Field(
        ...,
        description="Statut du déploiement",
        json_schema_extra={"example": "running"}
    )
    config: Dict[str, Any] = Field(
        ...,
        description="Configuration utilisée",
        json_schema_extra={"example": {"ports": [80, 443]}}
    )
    variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Variables appliquées",
        json_schema_extra={"example": {"port": 8080}}
    )
    logs: Optional[str] = Field(
        None,
        description="Logs du déploiement",
        json_schema_extra={"example": "Deploying... Container started."}
    )
    error_message: Optional[str] = Field(
        None,
        description="Message d'erreur si échec",
        json_schema_extra={"example": None}
    )
    deployed_at: Optional[datetime] = Field(
        None,
        description="Date de déploiement réussi",
        json_schema_extra={"example": "2026-01-02T22:35:00Z"}
    )
    created_at: datetime = Field(
        ...,
        description="Date de création",
        json_schema_extra={"example": "2026-01-02T22:30:00Z"}
    )
    updated_at: datetime = Field(
        ...,
        description="Date de mise à jour",
        json_schema_extra={"example": "2026-01-02T22:35:00Z"}
    )


class DeploymentLogsResponse(BaseModel):
    """Schema pour réponse des logs d'un déploiement."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "deployment_id": "990e8400-e29b-41d4-a716-446655440000",
                "logs": "2026-01-02 22:30:00 Starting deployment...\n2026-01-02 22:31:00 Container created.\n2026-01-02 22:31:05 Health check passed.",
                "updated_at": "2026-01-02T22:31:05Z"
            }
        }
    )

    deployment_id: str = Field(
        ...,
        description="ID du déploiement",
        json_schema_extra={"example": "990e8400-e29b-41d4-a716-446655440000"}
    )
    logs: Optional[str] = Field(
        None,
        description="Logs du déploiement",
        json_schema_extra={"example": "Starting deployment...\nContainer created."}
    )
    updated_at: datetime = Field(
        ...,
        description="Date de dernière mise à jour des logs",
        json_schema_extra={"example": "2026-01-02T22:31:05Z"}
    )
