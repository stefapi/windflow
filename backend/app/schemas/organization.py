"""
Schemas Pydantic V2 pour l'entité Organization.

Validation stricte avec type hints obligatoires selon backend.md.
Chaque modèle inclut model_config avec exemples et json_schema_extra
pour une documentation OpenAPI complète.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class OrganizationBase(BaseModel):
    """Schema de base pour Organization."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Nom de l'organisation",
        json_schema_extra={"example": "Acme Corp"}
    )
    slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9-]+$",
        description="Slug unique (minuscules, chiffres et tirets uniquement)",
        json_schema_extra={"example": "acme-corp"}
    )
    domain: Optional[str] = Field(
        None,
        max_length=255,
        description="Domaine de l'organisation",
        json_schema_extra={"example": "acme.com"}
    )
    description: Optional[str] = Field(
        None,
        description="Description de l'organisation",
        json_schema_extra={"example": "Leading cloud deployment company"}
    )


class OrganizationCreate(OrganizationBase):
    """
    Schema pour création d'organisation.

    **Règles de validation:**
    - name: 1-255 caractères, obligatoire
    - slug: Minuscules, chiffres et tirets uniquement, unique
    - settings: Configuration JSON libre
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Acme Corp",
                    "slug": "acme-corp",
                    "domain": "acme.com",
                    "description": "Leading cloud deployment company",
                    "settings": {
                        "max_deployments": 100,
                        "allowed_targets": ["docker", "kubernetes"]
                    }
                },
                {
                    "name": "Startup Labs",
                    "slug": "startup-labs",
                    "description": "Small startup team"
                },
                {
                    "name": "DevOps Team",
                    "slug": "devops-team",
                    "domain": "devops.internal",
                    "settings": {
                        "notifications_enabled": True,
                        "default_target": "docker"
                    }
                }
            ]
        }
    )

    settings: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Configuration JSON",
        json_schema_extra={"example": {"max_deployments": 100, "allowed_targets": ["docker"]}}
    )


class OrganizationUpdate(BaseModel):
    """
    Schema pour mise à jour d'organisation.

    Tous les champs sont optionnels. Seuls les champs fournis
    seront mis à jour.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Acme Corporation",
                    "description": "Updated description"
                },
                {
                    "settings": {"max_deployments": 200, "notifications_enabled": True}
                },
                {
                    "domain": "new-domain.com",
                    "slug": "acme-corporation"
                }
            ]
        }
    )

    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Nouveau nom",
        json_schema_extra={"example": "Acme Corporation"}
    )
    slug: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9-]+$",
        description="Nouveau slug",
        json_schema_extra={"example": "acme-corporation"}
    )
    domain: Optional[str] = Field(
        None,
        max_length=255,
        description="Nouveau domaine",
        json_schema_extra={"example": "new-domain.com"}
    )
    description: Optional[str] = Field(
        None,
        description="Nouvelle description",
        json_schema_extra={"example": "Updated organization description"}
    )
    settings: Optional[Dict[str, Any]] = Field(
        None,
        description="Nouvelle configuration JSON",
        json_schema_extra={"example": {"max_deployments": 200}}
    )


class OrganizationResponse(OrganizationBase):
    """
    Schema pour réponse Organization.

    Retourné après création réussie ou lors de la consultation
    d'une organisation. Inclut les métadonnées et la configuration.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "org-550e8400",
                "name": "Acme Corp",
                "slug": "acme-corp",
                "domain": "acme.com",
                "description": "Leading cloud deployment company",
                "settings": {"max_deployments": 100},
                "created_at": "2026-01-02T10:00:00Z",
                "updated_at": "2026-01-02T10:00:00Z"
            }
        }
    )

    id: str = Field(
        ...,
        description="ID unique de l'organisation",
        json_schema_extra={"example": "org-550e8400"}
    )
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration JSON",
        json_schema_extra={"example": {"max_deployments": 100}}
    )
    created_at: datetime = Field(
        ...,
        description="Date de création",
        json_schema_extra={"example": "2026-01-02T10:00:00Z"}
    )
    updated_at: datetime = Field(
        ...,
        description="Date de mise à jour",
        json_schema_extra={"example": "2026-01-02T10:00:00Z"}
    )
