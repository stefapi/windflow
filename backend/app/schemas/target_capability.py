"""Schemas Pydantic pour les capacités de cibles détectées."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..enums.target import CapabilityType


class TargetCapabilityBase(BaseModel):
    """Schéma de base pour représenter une capacité détectée."""

    capability_type: CapabilityType = Field(
        ..., description="Type de capacité détectée sur la cible"
    )
    is_available: bool = Field(
        default=False, description="Indique si la capacité est disponible sur la cible"
    )
    version: str | None = Field(
        default=None, description="Version de l'outil détectée lorsque disponible"
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Informations supplémentaires retournées par le scanner",
    )


class TargetCapabilityResponse(TargetCapabilityBase):
    """Schéma de réponse pour une capacité détectée."""

    id: str = Field(..., description="Identifiant unique de la capacité")
    target_id: str = Field(..., description="Identifiant de la cible associée")
    detected_at: datetime = Field(..., description="Date de détection de la capacité")
    created_at: datetime = Field(..., description="Date de création de l'entrée")
    updated_at: datetime = Field(..., description="Date de dernière mise à jour")

    model_config = ConfigDict(from_attributes=True)
