"""Schemas Pydantic pour les cibles de déploiement."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..enums.target import AccessLevel, SSHAuthMethod, TargetStatus, TargetType


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
    sudo_enabled: bool = Field(
        default=False, description="Activer l'escalade sudo"
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
        if self.sudo_enabled and not self.sudo_user:
            # When sudo is enabled without a specific user, default to root
            self.sudo_user = "root"
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
        # Always store sudo_enabled explicitly (even False)
        data["sudo_enabled"] = self.sudo_enabled
        return data


class SSHCredentialsUpdate(BaseModel):
    """Mise à jour partielle des credentials SSH."""

    auth_method: SSHAuthMethod | None = None
    username: str | None = None
    password: str | None = None
    ssh_private_key: str | None = None
    ssh_private_key_passphrase: str | None = None
    sudo_enabled: bool | None = None
    sudo_user: str | None = None
    sudo_password: str | None = None


# ─── Connection Test ────────────────────────────────────────────


# ─── Host Reachability Test ────────────────────────────────────


class HostReachabilityStepResult(BaseModel):
    """Résultat d'une étape individuelle du test de joignabilité."""

    step: str = Field(..., description="Nom de l'étape (dns, ssh)")
    success: bool = Field(..., description="L'étape a réussi")
    message: str = Field(..., description="Message descriptif du résultat")
    duration_ms: float | None = Field(
        default=None, description="Durée de l'étape en millisecondes"
    )


class HostReachabilityRequest(BaseModel):
    """Requête de test de joignabilité d'un hôte (sans credentials)."""

    host: str = Field(..., min_length=1, max_length=255, description="Adresse IP ou hostname")
    port: int = Field(default=22, ge=1, le=65535, description="Port SSH")


class HostReachabilityResponse(BaseModel):
    """Résultat du test de joignabilité d'un hôte."""

    host: str = Field(..., description="Hôte testé")
    port: int = Field(..., description="Port testé")
    steps: list[HostReachabilityStepResult] = Field(
        default_factory=list, description="Résultats détaillés par étape"
    )
    reachable: bool = Field(..., description="L'hôte est globalement joignable")


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


# ─── Access Profile ─────────────────────────────────────────────


class TargetAccessProfile(BaseModel):
    """Profil d'accès détecté sur une cible lors d'un scan.

    Stocké en JSON dans la colonne ``access_profile`` du modèle Target.
    Représente les permissions effectives du compte SSH et du compte sudo.
    """

    # Identité SSH
    ssh_user: str = Field(..., description="Utilisateur SSH utilisé pour la connexion")
    is_root_user: bool = Field(..., description="L'utilisateur SSH est root")

    # Sudo
    sudo_available: bool = Field(
        default=False, description="La commande sudo est installée sur la cible"
    )
    sudo_verified: bool = Field(
        default=False, description="L'accès sudo a été testé et fonctionne"
    )
    sudo_passwordless: bool = Field(
        default=False, description="sudo fonctionne sans mot de passe"
    )
    sudo_user: str | None = Field(
        default=None, description="Utilisateur effectif après sudo (ex: root)"
    )

    # Niveau d'accès global
    access_level: AccessLevel = Field(
        ..., description="Niveau d'accès effectif: root, sudo, sudo_passwordless, limited"
    )
    can_install_packages: bool = Field(
        default=False, description="Possibilité d'installer des packages (root ou sudo root)"
    )

    # Capabilities par niveau
    standard_capabilities: list[str] = Field(
        default_factory=list,
        description="Liste des capacités détectées avec le compte SSH standard",
    )
    elevated_capabilities: list[str] = Field(
        default_factory=list,
        description="Liste des capacités supplémentaires détectées via sudo/root",
    )

    # Métadonnées de détection
    detected_at: datetime = Field(..., description="Date de détection du profil")
    detection_method: str = Field(
        ..., description="Méthode de détection: scan, discovery"
    )


# ─── Target Create / Update ─────────────────────────────────────


class TargetCreate(BaseModel):
    """Schéma de création d'une cible."""

    name: str = Field(..., min_length=1, max_length=255, description="Nom de la cible")
    type: TargetType = Field(
        default=TargetType.PHYSICAL, description="Type de cible (physical par défaut, mis à jour par scan)"
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
    last_check: datetime | None = None
    scan_date: datetime | None = None
    scan_success: bool | None = None
    platform_info: dict[str, Any] | None = None
    os_info: dict[str, Any] | None = None
    access_profile: TargetAccessProfile | None = Field(
        default=None, description="Profil d'accès détecté lors du dernier scan"
    )
    extra_metadata: dict[str, Any]
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthCheckResponse(BaseModel):
    """Résultat d'un health check sur une cible."""

    target_id: str = Field(..., description="ID de la cible")
    status: TargetStatus = Field(..., description="Nouveau statut après vérification")
    last_check: datetime = Field(..., description="Horodatage du health check")
    message: str = Field(..., description="Message descriptif du résultat")


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
