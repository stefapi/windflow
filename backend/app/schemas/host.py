"""Schemas Pydantic canoniques pour les hôtes de déploiement (STORY-166.2).

Module canonique de la famille Hosts (spec 09 — ``HostCreateRequest`` /
``HostResponse`` / ``HostUpdate``). L'ancien module
:mod:`app.schemas.target` devient un alias de transition (re-exports) —
purge par STORY-166.6.

Règle 40 (sécurité) : ``HostResponse`` ne définit **jamais** les champs
``credentials``/``connection_config`` — aucun secret ne peut fuiter dans
une réponse API. Les champs dérivés sans secret (``auth_method``,
``username``, ``has_sudo``, ``ssh_key_id``) sont conservés à l'identique.

Double nommage ``profile``/``type`` (transition 166.x) :

- ``profile`` est le champ canonique (spec 06 — ``host_baremetal``,
  ``host_proxmox``, ``host_remote_docker``) ;
- ``type`` (``TargetType`` legacy) reste accepté en entrée pour ne casser
  aucun consommateur de l'alias ``/targets`` (contrat figé) ;
- si les deux sont fournis, le canonique prime (validator) ; si aucun,
  le défaut métier ``host_baremetal`` s'applique (défaut colonne du
  modèle ``Host``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from ..enums.host import AccessLevel, HostProfile, HostStatus, SSHAuthMethod
from ..enums.target import TargetType

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
    sudo_enabled: bool = Field(default=False, description="Activer l'escalade sudo")
    sudo_user: str | None = Field(
        default=None, description="Utilisateur pour escalation sudo"
    )
    sudo_password: str | None = Field(default=None, description="Mot de passe sudo")

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


# ─── Host Reachability Test ─────────────────────────────────────


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

    host: str = Field(
        ..., min_length=1, max_length=255, description="Adresse IP ou hostname"
    )
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
    """Résultat d'un test de connexion SSH (empreinte capturée — STORY-131.3).

    Mode COLLECT : l'empreinte de la clé d'hôte présentée est
    **capturée sans être persistée** (jamais d'ajout silencieux —
    spec 15) et retournée pour acceptation explicite via
    ``POST /hosts/{id}/ssh-fingerprints/accept`` (STORY-131.2).
    """

    success: bool = Field(..., description="La connexion a réussi")
    message: str = Field(..., description="Message descriptif du résultat")
    os_info: dict[str, Any] | None = Field(
        default=None, description="Informations OS détectées"
    )
    host_fingerprint: str | None = Field(
        default=None,
        description=(
            "Empreinte de la clé d'hôte capturée (SHA256:<base64nopad>) — "
            "NON persistée par le test : acceptation explicite requise "
            "(STORY-131.3, TOFU)"
        ),
    )
    fingerprint_status: Literal["unknown", "accepted", "mismatch"] | None = Field(
        default=None,
        description=(
            "Statut TOFU de l'empreinte capturée : unknown (première "
            "utilisation), accepted (matching une empreinte acceptée), "
            "mismatch (divergence — connexion refusée, spec 15 anti-MITM)"
        ),
    )


# ─── Access Profile ─────────────────────────────────────────────


class HostAccessProfile(BaseModel):
    """Profil d'accès détecté sur un hôte lors d'un scan.

    Stocké en JSON dans la colonne ``access_profile`` du modèle Host.
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
        ...,
        description="Niveau d'accès effectif: root, sudo, sudo_passwordless, limited",
    )
    can_install_packages: bool = Field(
        default=False,
        description="Possibilité d'installer des packages (root ou sudo root)",
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


# ─── Host Create / Update ───────────────────────────────────────


class HostCreateRequest(BaseModel):
    """Schéma de création d'un hôte (canonique spec 09).

    ``profile`` est le champ canonique ; ``type`` (legacy ``TargetType``)
    reste accepté pour la compatibilité de l'alias ``/targets`` (contrat
    figé — STORY-166.2). Voir docstring module pour l'arbitrage.
    """

    name: str = Field(..., min_length=1, max_length=255, description="Nom de l'hôte")
    host: str = Field(
        ..., min_length=1, max_length=255, description="Adresse IP ou hostname"
    )
    port: int = Field(default=22, ge=1, le=65535, description="Port SSH")
    type: TargetType | None = Field(
        default=None,
        description=(
            "[Legacy /targets] Type de cible — mappé vers ``profile`` "
            "(table d'arbitrage STORY-166.1). Ignoré si ``profile`` est fourni."
        ),
    )
    profile: HostProfile | None = Field(
        default=None,
        description=(
            "Profil canonique spec 06 (host_baremetal, host_proxmox, "
            "host_remote_docker) — prioritaire sur ``type``. "
            "Défaut ``host_baremetal`` si ni ``profile`` ni ``type`` fourni."
        ),
    )
    description: str | None = Field(default=None, max_length=500)
    credentials: SSHCredentials
    ssh_key_id: str | None = Field(
        default=None,
        description=(
            "Clé SSH réutilisable référencée (voie canonique — "
            "STORY-131) ; la clé doit exister (sinon 422/404)"
        ),
    )
    environment_id: str | None = Field(
        default=None,
        description=(
            "Environnement de rattachement (STORY-166.4 — UUID, doit "
            "exister dans l'organisation, sinon 404)"
        ),
    )
    organization_id: str = Field(..., description="ID de l'organisation")
    extra_metadata: dict[str, Any] | None = Field(default=None)

    @model_validator(mode="after")
    def _resolve_profile(self) -> HostCreateRequest:
        """Arbitrage ``profile``/``type`` (canonique prioritaire).

        - les deux fournis → ``type`` neutralisé (le setter hybrid du
          modèle ne doit pas écraser ``profile`` au constructeur) ;
        - aucun fourni → défaut canonique ``host_baremetal`` (le
          ``model_dump`` ne doit pas contenir ``profile=None`` : la
          colonne est NOT NULL et un None explicite casserait le défaut
          SQLAlchemy) ;
        - ``type`` seul → conservé : le mapping est porté par le setter
          ``Host.type`` (table d'arbitrage + trace ``migrated_type``).
        """
        if self.profile is not None and self.type is not None:
            self.type = None
        if self.profile is None:
            self.profile = HostProfile.HOST_BAREMETAL
        return self


class HostUpdate(BaseModel):
    """Schéma de mise à jour partielle d'un hôte.

    ``profile`` est déclaré APRÈS ``type`` : en cas de mise à jour
    simultanée, le canonique est appliqué en dernier (``setattr``
    séquentiel dans ``HostService.update``) — même règle de priorité
    que la création.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: TargetType | None = Field(
        default=None,
        description="[Legacy /targets] Type de cible — mappé vers ``profile``.",
    )
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    description: str | None = Field(default=None, max_length=500)
    credentials: SSHCredentialsUpdate | None = None
    ssh_key_id: str | None = Field(
        default=None,
        description=(
            "Clé SSH réutilisable référencée (voie canonique — "
            "STORY-131) ; la clé doit exister (sinon 422/404)"
        ),
    )
    status: HostStatus | None = None
    profile: HostProfile | None = Field(
        default=None, description="Profil canonique spec 06 (prioritaire sur type)"
    )
    environment_id: str | None = Field(
        default=None,
        description="Environnement de rattachement (STORY-166.4 — UUID)",
    )
    extra_metadata: dict[str, Any] | None = None


# ─── Host Response ──────────────────────────────────────────────


class HostResponse(BaseModel):
    """Schéma de réponse pour un hôte (sans credentials — règle 40).

    Champs canoniques spec 06 (``profile``, ``hardware_info``,
    ``installed_engines``, ``last_scan_at``, ``origin``) + champs
    dérivés legacy (``type``, ``scan_date``, ``platform_info``) conservés
    pendant la transition pour ne casser aucun consommateur de l'alias
    ``/targets`` (contrat figé) — purge par STORY-166.6.
    """

    id: str
    name: str
    host: str
    port: int
    description: str | None

    # ── Canonique (STORY-166.1/166.2) ──
    profile: HostProfile = Field(description="Profil canonique spec 06")
    status: HostStatus
    hardware_info: dict[str, Any] | None = Field(
        default=None, description="Informations matérielles (dernier scan)"
    )
    installed_engines: list[Any] = Field(
        default_factory=list, description="Moteurs détectés (dernier scan)"
    )
    last_scan_at: datetime | None = Field(
        default=None, description="Timestamp du dernier scan"
    )
    origin: str = Field(description="Origine du workload (managed/adopted/external)")

    # ── Dérivés credentials (sans secret — règle 40) ──
    auth_method: str | None
    username: str | None
    has_sudo: bool
    ssh_key_id: str | None = Field(
        default=None,
        description="Clé SSH réutilisable référencée (voie canonique — STORY-131)",
    )

    # ── Alias legacy (purge STORY-166.6) ──
    type: TargetType = Field(description="[Legacy /targets] Type dérivé du profil")
    scan_date: datetime | None = Field(
        default=None, description="[Legacy /targets] Alias de last_scan_at"
    )
    platform_info: dict[str, Any] | None = Field(
        default=None, description="[Legacy /targets] Alias de hardware_info"
    )

    last_check: datetime | None = None
    scan_success: bool | None = None
    os_info: dict[str, Any] | None = None
    access_profile: HostAccessProfile | None = Field(
        default=None, description="Profil d'accès détecté lors du dernier scan"
    )
    extra_metadata: dict[str, Any]
    organization_id: str
    environment_id: str | None = Field(
        default=None,
        description="Environnement de rattachement (STORY-166.4 — lecture seule)",
    )
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HostHealthCheckResponse(BaseModel):
    """Résultat d'un health check sur un hôte.

    ``host_id`` est le champ canonique ; ``target_id`` est un alias de
    lecture (même valeur) conservé pour les consommateurs legacy de
    l'alias ``/targets`` — purge par STORY-166.6.
    """

    host_id: str = Field(..., description="ID de l'hôte")
    status: HostStatus = Field(..., description="Nouveau statut après vérification")
    last_check: datetime = Field(..., description="Horodatage du health check")
    message: str = Field(..., description="Message descriptif du résultat")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def target_id(self) -> str:
        """Alias legacy de ``host_id`` (compat /targets — purge 166.6)."""
        return self.host_id


class HostCapabilitiesResponse(BaseModel):
    """Réponse incluant les capacités détectées d'un hôte."""

    scan_date: datetime | None = None
    scan_success: bool | None = None
    platform_info: dict[str, Any] | None = None
    os_info: dict[str, Any] | None = None
    capabilities: list[Any] = Field(
        default_factory=list,
        description="Liste des capacités détectées (HostCapabilityResponse)",
    )
