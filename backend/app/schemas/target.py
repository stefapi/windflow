"""Schemas Pydantic pour les cibles de déploiement."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..enums.target import SSHAuthMethod, TargetStatus, TargetType


# ─── Credentials ────────────────────────────────────────────────


class SSHCredentials(BaseModel):
    """Informations d'authentification SSH.

    Quand auth_method == LOCAL, username et password sont optionnels
    car la connexion se fait directement en local sans SSH.
    """

    auth_method: SSHAuthMethod = Field(
        ..., description="Méthode d'authentification (local, password ou ssh_key)"
    )
    username: str | None = Field(default=None, description="Utilisateur SSH")
    password: str | None = Field(default=None, description="Mot de passe SSH")
    ssh_private_key: str | None = Field(
        default=None, description="Clé privée SSH (PEM)"
    )
    ssh_private_key_passphrase: str | None = Field(
        default=None, description="Passphrase de la clé privée"
    )
    sudo_user: str | None = Field(
        default=None, description="Utilisateur pour escalation sudo"
    )
    sudo_password: str | None = Field(
        default=None, description="Mot de passe sudo"
    )

    @model_validator(mode="after")
    def _validate_credentials_for_auth_method(self) -> SSHCredentials:
        """Valide que les champs requis sont présents selon la méthode d'auth."""
        if self.auth_method == SSHAuthMethod.PASSWORD:
            if not self.username:
                msg = "username est requis quand auth_method=password"
                raise ValueError(msg)
        elif self.auth_method == SSHAuthMethod.SSH_KEY:
            if not self.username:
                msg = "username est requis quand auth_method=ssh_key"
                raise ValueError(msg)
        return self

    def to_storage_dict(self) -> dict[str, Any]:
        """Convertit les credentials en dict pour stockage JSON en base.

        Exclut les champs None pour ne pas polluer le JSON stocké.
        La valeur `auth_method` est convertie en string.
        """
        data: dict[str, Any] = {"auth_method": self.auth_method.value}
        for field_name in (
            "username",
            "password",
            "ssh_private_key",
            "ssh_private_key_passphrase",
            "sudo_user",
            "sudo_password",
        ):
            value = getattr(self, field_name)
            if value is not None:
                data[field_name] = value
        return data


class SSHCredentialsUpdate(BaseModel):
    """Mise à jour partielle des credentials SSH."""

    auth_method: SSHAuthMethod | None = None
    username: str | None = None
    password: str | None = None
    ssh_private_key: str | None = None
    ssh_private_key_passphrase: str | None = None
    sudo_user: str | None = None
    sudo_password: str | None = None


# ─── Connection Test ────────────────────────────────────────────


class ConnectionTestRequest(BaseModel):
    """Requête de test de connexion SSH."""

    host: str = Field(..., description="Adresse IP ou hostname")
    port: int = Field(default=22, ge=1, le=65535, description="Port SSH")
    credentials: SSHCredentials


class ConnectionTestResponse(BaseModel):
    """Résultat d'un test de connexion SSH."""

    success: bool = Field(..., description="La connexion a réussi")
    message: str = Field(..., description="Message descriptif du résultat")
    os_info: dict[str, Any] | None = Field(
        default=None, description="Informations OS détectées"
    )


# ─── Target Create / Update ─────────────────────────────────────


class TargetCreate(BaseModel):
    """Schéma de création d'une cible."""

    name: str = Field(..., min_length=1, max_length=255, description="Nom de la cible")
    type: TargetType = Field(
        default=TargetType.DOCKER, description="Type de cible (auto-détecté via scan)"
    )
    host: str = Field(..., min_length=1, max_length=255, description="Adresse IP ou hostname")
    port: int = Field(default=22, ge=1, le=65535, description="Port SSH")
    description: str | None = Field(default=None, max_length=500)
    credentials: SSHCredentials
    organization_id: str = Field(..., description="ID de l'organisation")
    extra_metadata: dict[str, Any] | None = Field(default=None)


class TargetUpdate(BaseModel):
    """Schéma de mise à jour partielle d'une cible."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: TargetType | None = None
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    description: str | None = Field(default=None, max_length=500)
    credentials: SSHCredentialsUpdate | None = None
    status: TargetStatus | None = None
    extra_metadata: dict[str, Any] | None = None


# ─── Target Response ────────────────────────────────────────────


class TargetResponse(BaseModel):
    """Schéma de réponse pour une cible (sans credentials)."""

    id: str
    name: str
    type: TargetType
    host: str
    port: int
    description: str | None
    status: TargetStatus
    auth_method: str | None
    username: str | None
    has_sudo: bool
    scan_date: datetime | None = None
    scan_success: bool | None = None
    platform_info: dict[str, Any] | None = None
    os_info: dict[str, Any] | None = None
    extra_metadata: dict[str, Any]
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TargetCapabilitiesResponse(BaseModel):
    """Réponse incluant les capacités détectées d'une cible."""

    scan_date: datetime | None = None
    scan_success: bool | None = None
    platform_info: dict[str, Any] | None = None
    os_info: dict[str, Any] | None = None
    capabilities: list[Any] = Field(
        default_factory=list,
        description="Liste des capacités détectées (TargetCapabilityResponse)",
    )
