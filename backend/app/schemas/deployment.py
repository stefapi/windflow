"""
Schemas Pydantic V2 pour l'entité Deployment.

Validation stricte avec type hints obligatoires selon backend.md.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DeploymentStatus(str, Enum):
    """Statuts possibles pour un déploiement."""
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
    """Schema pour création de déploiement."""

    stack_id: str = Field(..., description="ID du stack à déployer")
    target_id: str = Field(..., description="ID de la cible de déploiement")
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Nom du déploiement (auto-généré si absent)")
    config: Optional[Dict[str, Any]] = Field(None, description="Configuration du déploiement (générée depuis le template si absente)")
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Variables à appliquer (utilise les defaults du stack si absent)")


class DeploymentUpdate(BaseModel):
    """Schema pour mise à jour de déploiement."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Nouveau nom")
    status: Optional[DeploymentStatus] = Field(None, description="Nouveau statut")
    variables: Optional[Dict[str, Any]] = Field(None, description="Nouvelles variables")
    logs: Optional[str] = Field(None, description="Logs du déploiement")
    error_message: Optional[str] = Field(None, description="Message d'erreur")


class DeploymentResponse(BaseModel):
    """Schema pour réponse Deployment."""

    name: str = Field(..., min_length=1, max_length=255, description="Nom du déploiement")
    id: str = Field(..., description="ID unique du déploiement")
    stack_id: str = Field(..., description="ID du stack")
    target_id: str = Field(..., description="ID de la cible")
    status: DeploymentStatus = Field(..., description="Statut du déploiement")
    config: Dict[str, Any] = Field(..., description="Configuration utilisée")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Variables appliquées")
    logs: Optional[str] = Field(None, description="Logs du déploiement")
    error_message: Optional[str] = Field(None, description="Message d'erreur si échec")
    deployed_at: Optional[datetime] = Field(None, description="Date de déploiement réussi")
    created_at: datetime = Field(..., description="Date de création")
    updated_at: datetime = Field(..., description="Date de mise à jour")

    model_config = ConfigDict(from_attributes=True)


class DeploymentLogsResponse(BaseModel):
    """Schema pour réponse des logs d'un déploiement."""

    deployment_id: str = Field(..., description="ID du déploiement")
    logs: Optional[str] = Field(None, description="Logs du déploiement")
    updated_at: datetime = Field(..., description="Date de dernière mise à jour des logs")
