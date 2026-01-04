"""
Schemas Pydantic V2 pour l'entité Stack.

Validation stricte avec type hints obligatoires selon backend.md.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class StackBase(BaseModel):
    """Schema de base pour Stack."""

    name: str = Field(..., min_length=1, max_length=255, description="Nom du stack")
    description: Optional[str] = Field(None, description="Description du stack")
    version: str = Field(default="1.0.0", max_length=50, description="Version du stack")
    category: Optional[str] = Field(None, max_length=100, description="Catégorie")
    icon_url: Optional[str] = Field(None, max_length=500, description="URL de l'icône")
    author: Optional[str] = Field(None, max_length=255, description="Auteur du stack")
    license: Optional[str] = Field(default="MIT", max_length=100, description="Licence")
    deployment_name: Optional[str] = Field(None, max_length=255, description="Nom par défaut du déploiement (template)")


class StackCreate(StackBase):
    """Schema pour création de stack."""

    template: Dict[str, Any] = Field(..., description="Template Docker Compose (format JSON)")
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Variables configurables (format simple)")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags de recherche")
    is_public: bool = Field(default=False, description="Stack public dans marketplace")
    screenshots: Optional[List[str]] = Field(default_factory=list, description="URLs des screenshots")
    documentation_url: Optional[str] = Field(None, max_length=500, description="URL de la documentation")
    organization_id: str = Field(..., description="ID de l'organisation")


class StackUpdate(BaseModel):
    """Schema pour mise à jour de stack."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Nouveau nom")
    description: Optional[str] = Field(None, description="Nouvelle description")
    template: Optional[Dict[str, Any]] = Field(None, description="Nouveau template")
    variables: Optional[Dict[str, Any]] = Field(None, description="Nouvelles variables")
    version: Optional[str] = Field(None, max_length=50, description="Nouvelle version")
    category: Optional[str] = Field(None, max_length=100, description="Nouvelle catégorie")
    tags: Optional[List[str]] = Field(None, description="Nouveaux tags")
    is_public: Optional[bool] = Field(None, description="Statut public")
    deployment_name: Optional[str] = Field(None, max_length=255, description="Nouveau nom par défaut du déploiement")


class StackResponse(StackBase):
    """Schema pour réponse Stack."""

    id: str = Field(..., description="ID unique du stack")
    template: Dict[str, Any] = Field(..., description="Template Docker Compose")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Variables configurables")
    tags: List[str] = Field(default_factory=list, description="Tags")
    is_public: bool = Field(..., description="Stack public")
    downloads: int = Field(default=0, description="Nombre de téléchargements")
    rating: float = Field(default=0.0, description="Note moyenne")
    screenshots: List[str] = Field(default_factory=list, description="Screenshots")
    documentation_url: Optional[str] = Field(None, description="URL documentation")
    organization_id: str = Field(..., description="ID de l'organisation")
    created_at: datetime = Field(..., description="Date de création")
    updated_at: datetime = Field(..., description="Date de mise à jour")
    default_name: Optional[str] = Field(None, description="Nom par défaut généré pour le déploiement")

    model_config = ConfigDict(from_attributes=True)


class MarketplaceStackResponse(BaseModel):
    """Schema pour réponse Stack marketplace (sans template complet)."""

    id: str = Field(..., description="ID unique du stack")
    name: str = Field(..., description="Nom du stack")
    description: Optional[str] = Field(None, description="Description")
    version: str = Field(..., description="Version")
    category: Optional[str] = Field(None, description="Catégorie")
    tags: List[str] = Field(default_factory=list, description="Tags")
    icon_url: Optional[str] = Field(None, description="URL icône")
    screenshots: List[str] = Field(default_factory=list, description="Screenshots")
    author: Optional[str] = Field(None, description="Auteur")
    license: Optional[str] = Field(None, description="Licence")
    downloads: int = Field(default=0, description="Téléchargements")
    rating: float = Field(default=0.0, description="Note")
    created_at: datetime = Field(..., description="Date de création")
    updated_at: datetime = Field(..., description="Date de mise à jour")

    model_config = ConfigDict(from_attributes=True)


class DeploymentConfigRequest(BaseModel):
    """Schema pour configuration de déploiement."""

    stack_id: str = Field(..., description="ID du stack à déployer")
    target_id: str = Field(..., description="ID de la cible de déploiement")
    configuration: Dict[str, Any] = Field(..., description="Configuration des variables")
    name: Optional[str] = Field(None, description="Nom du déploiement (optionnel)")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stack_id": "uuid-baserow",
            "target_id": "target-docker-local",
            "configuration": {
                "baserow_version": "1.26.1",
                "db_password": "secure_password_123",
                "domain": "baserow.localhost",
                "workers": 2
            }
        }
    })
