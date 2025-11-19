"""
Schemas Pydantic V2 pour l'entité Target.

Validation stricte avec type hints obligatoires selon backend.md.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class TargetType(str, Enum):
    """Types de cibles de déploiement supportés."""
    DOCKER = "docker"
    DOCKER_COMPOSE = "docker_compose"
    DOCKER_SWARM = "docker_swarm"
    KUBERNETES = "kubernetes"
    VM = "vm"
    PHYSICAL = "physical"


class TargetStatus(str, Enum):
    """Statuts possibles pour une cible."""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class TargetBase(BaseModel):
    """Schema de base pour Target."""

    name: str = Field(..., min_length=1, max_length=255, description="Nom de la cible")
    description: Optional[str] = Field(None, max_length=500, description="Description")
    host: str = Field(..., min_length=1, max_length=255, description="Hôte (IP ou domaine)")
    port: int = Field(default=22, ge=1, le=65535, description="Port de connexion")
    type: TargetType = Field(default=TargetType.DOCKER, description="Type de cible")


class TargetCreate(TargetBase):
    """Schema pour création de cible."""

    credentials: Dict[str, Any] = Field(..., description="Credentials de connexion (seront chiffrés)")
    organization_id: str = Field(..., description="ID de l'organisation")
    extra_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Métadonnées additionnelles")


class TargetUpdate(BaseModel):
    """Schema pour mise à jour de cible."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Nouveau nom")
    description: Optional[str] = Field(None, max_length=500, description="Nouvelle description")
    host: Optional[str] = Field(None, min_length=1, max_length=255, description="Nouvel hôte")
    port: Optional[int] = Field(None, ge=1, le=65535, description="Nouveau port")
    type: Optional[TargetType] = Field(None, description="Nouveau type")
    credentials: Optional[Dict[str, Any]] = Field(None, description="Nouveaux credentials")
    status: Optional[TargetStatus] = Field(None, description="Nouveau statut")
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="Nouvelles métadonnées")


class TargetResponse(TargetBase):
    """Schema pour réponse Target (sans credentials sensibles)."""

    id: str = Field(..., description="ID unique de la cible")
    status: TargetStatus = Field(..., description="Statut de la cible")
    last_check: Optional[datetime] = Field(None, description="Dernière vérification")
    scan_date: Optional[datetime] = Field(
        default=None,
        description="Date du dernier scan des capacités"
    )
    scan_success: Optional[bool] = Field(
        default=None,
        description="Indique si le dernier scan des capacités a réussi"
    )
    platform_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Informations sur la plateforme détectées lors du dernier scan"
    )
    os_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Informations sur le système d'exploitation détectées lors du dernier scan"
    )
    extra_metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées")
    organization_id: str = Field(..., description="ID de l'organisation")
    created_at: datetime = Field(..., description="Date de création")
    updated_at: datetime = Field(..., description="Date de mise à jour")

    model_config = ConfigDict(from_attributes=True)
