"""
Schemas Pydantic V2 pour l'entité Organization.

Validation stricte avec type hints obligatoires selon backend.md.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class OrganizationBase(BaseModel):
    """Schema de base pour Organization."""

    name: str = Field(..., min_length=1, max_length=255, description="Nom de l'organisation")
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$", description="Slug unique")
    domain: Optional[str] = Field(None, max_length=255, description="Domaine de l'organisation")
    description: Optional[str] = Field(None, description="Description de l'organisation")


class OrganizationCreate(OrganizationBase):
    """Schema pour création d'organisation."""

    settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Configuration JSON")


class OrganizationUpdate(BaseModel):
    """Schema pour mise à jour d'organisation."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Nouveau nom")
    slug: Optional[str] = Field(None, min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$", description="Nouveau slug")
    domain: Optional[str] = Field(None, max_length=255, description="Nouveau domaine")
    description: Optional[str] = Field(None, description="Nouvelle description")
    settings: Optional[Dict[str, Any]] = Field(None, description="Nouvelle configuration JSON")


class OrganizationResponse(OrganizationBase):
    """Schema pour réponse Organization."""

    id: str = Field(..., description="ID unique de l'organisation")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Configuration JSON")
    created_at: datetime = Field(..., description="Date de création")
    updated_at: datetime = Field(..., description="Date de mise à jour")

    model_config = ConfigDict(from_attributes=True)
