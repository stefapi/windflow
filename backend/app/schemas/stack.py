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


class StackCreate(StackBase):
    """Schema pour création de stack."""

    template: Dict[str, Any] = Field(..., description="Template Docker Compose (format JSON)")
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Variables configurables")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags de recherche")
    is_public: bool = Field(default=False, description="Stack public dans marketplace")
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


class StackResponse(StackBase):
    """Schema pour réponse Stack."""

    id: str = Field(..., description="ID unique du stack")
    template: Dict[str, Any] = Field(..., description="Template Docker Compose")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Variables configurables")
    tags: List[str] = Field(default_factory=list, description="Tags")
    is_public: bool = Field(..., description="Stack public")
    downloads: int = Field(default=0, description="Nombre de téléchargements")
    rating: float = Field(default=0.0, description="Note moyenne")
    organization_id: str = Field(..., description="ID de l'organisation")
    created_at: datetime = Field(..., description="Date de création")
    updated_at: datetime = Field(..., description="Date de mise à jour")

    model_config = ConfigDict(from_attributes=True)
