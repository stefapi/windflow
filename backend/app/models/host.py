"""Modèle Host — entité canonique des serveurs pilotés (spec 06, STORY-166.1).

Remplace ``Target`` (table ``targets``) : le profil décrit **comment on
pilote** le substrat (3 valeurs canoniques), les capacités sont éclatées
(``hardware_info`` / ``installed_engines``) et l'axe ``origin`` porte
l'origine du workload (défaut ``managed`` ; pose métier complète en
STORY-166.4).

Alias de transition (purge STORY-166.6) — build vert sans modifier les
consommateurs non encore renommés :

- :attr:`scan_date` / :attr:`platform_info` : synonyms SQLAlchemy des
  colonnes canoniques ``last_scan_at`` / ``hardware_info`` (lectures et
  écritures, niveau classe et instance) ;
- :attr:`type` : property traduisant l'ancien ``TargetType`` — le
  setter mappe vers ``profile`` (tables d'arbitrage
  :mod:`app.helper.target_host_migration`), le getter restitue le type
  legacy (``extra_metadata.migrated_type`` posé par la migration 1661).

Sécurité (STORY-103, rules 40) — reprise des garde-fous :

- credentials **chiffrés au repos** (token Fernet opaque
  ``{"_encrypted": ...}`` via le SecretManager) ;
- double lecture : ligne legacy en clair lue telle quelle puis
  ré-encryptée au premier accès (:attr:`decrypted_credentials`) ;
- ``__repr__`` sans credentials ni aucune donnée sensible.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from ..core.secret_manager import SecretManager, get_secret_manager
from ..database import Base
from ..enums.host import HostProfile, HostStatus, WorkloadOrigin
from ..enums.target import TargetType
from ..helper.target_host_migration import (
    _coerce_enum_member,
    map_target_to_host_profile,
)

if TYPE_CHECKING:
    from .deployment import Deployment
    from .environment import Environment
    from .host_capability import HostCapability
    from .host_ssh_fingerprint import HostSSHFingerprint
    from .organization import Organization
    from .ssh_key import SSHKey

# Clé unique du dict opaque stocké en colonne ``credentials`` : la valeur
# est un token Fernet (préfixe ``gAAAA``) englobant tout le JSON chiffré.
_CREDENTIALS_CIPHERTEXT_KEY: str = "_encrypted"

# Persiste les **valeurs** de l'enum (spec 06 : 'online', 'host_baremetal'…)
# plutôt que les noms de membres — cohérent avec les colonnes VARCHAR de la
# spec et avec la data migration 1661 (VALUES lowercase en base).
_ENUM_VALUES = lambda cls: [member.value for member in cls]  # noqa: E731


def encrypt_credentials_for_storage(plain: dict[str, Any]) -> dict[str, str]:
    """Chiffre un dict de credentials pour stockage JSON en base (STORY-103.2).

    Le dict est sérialisé en JSON compact puis chiffré en un **token Fernet
    unique** : la colonne ne contient aucune valeur en clair et ne divulgue
    pas la structure des credentials (une seule chaîne opaque).

    Args:
        plain: Credentials en clair (jamais loggés).

    Returns:
        Dict opaque ``{"_encrypted": "<token Fernet>"}``.
    """
    payload = json.dumps(plain, separators=(",", ":"), sort_keys=True)
    return {_CREDENTIALS_CIPHERTEXT_KEY: get_secret_manager().encrypt(payload)}


def decrypt_credentials_from_storage(stored: dict[str, Any]) -> dict[str, Any]:
    """Déchiffre les credentials stockés (double lecture, STORY-103.2).

    Args:
        stored: Valeur de la colonne ``credentials``.

    Returns:
        Credentials en clair (dict, éventuellement vide).

    Raises:
        SecretDecryptionError: Si le ciphertext est illisible (mauvaise
            clé maîtresse ou donnée corrompue/altérée).
    """
    token = stored.get(_CREDENTIALS_CIPHERTEXT_KEY)
    if not isinstance(token, str) or not SecretManager.is_encrypted(token):
        # Donnée legacy en clair (pas de préfixe ``gAAAA``) → lue telle
        # quelle ; la migration est gérée par ``Host.decrypted_credentials``.
        return stored
    decoded = json.loads(get_secret_manager().decrypt(token))
    return decoded if isinstance(decoded, dict) else {}


class Host(Base):
    """Host canonique — serveur piloté par WindFlow (spec 06 § Host).

    Schéma canonique : ``profile`` (3 valeurs), ``status`` (statuts
    unifiés), ``hardware_info``/``installed_engines`` (capacités éclatées),
    ``last_scan_at``, ``origin``. Colonnes conservées verbatim de
    ``targets`` : ``host``, ``port``, ``credentials`` (+ propriétés
    dérivées STORY-103), ``ssh_key_id``, ``extra_metadata``, ``last_check``,
    ``scan_success``, ``os_info``, ``access_profile``, ``organization_id``,
    timestamps.
    """

    __tablename__ = "hosts"

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Informations de base
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Configuration
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(default=22, nullable=False)

    # ─── Schéma canonique (STORY-166.1) ───────────────────────────────

    # Profil : comment on pilote le substrat (spec 06 — 3 valeurs).
    profile: Mapped[HostProfile] = mapped_column(
        SQLEnum(HostProfile, values_callable=_ENUM_VALUES),
        nullable=False,
        default=HostProfile.HOST_BAREMETAL,
        comment="Profil canonique (host_baremetal, host_proxmox, host_remote_docker)",
    )

    # Statuts unifiés (spec 06) — défaut offline.
    status: Mapped[HostStatus] = mapped_column(
        SQLEnum(HostStatus, values_callable=_ENUM_VALUES),
        nullable=False,
        default=HostStatus.OFFLINE,
    )

    # Capacités éclatées : hardware (ex-platform_info) + moteurs détectés.
    hardware_info: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Informations matérielles détectées lors du dernier scan",
    )
    installed_engines: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="Moteurs détectés (payload {capability_type, version, is_available})",
    )

    last_scan_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Timestamp of the last capabilities scan",
    )

    # Axe origine (matrice « profil × origine ») — pose métier en 166.4.
    origin: Mapped[WorkloadOrigin] = mapped_column(
        SQLEnum(WorkloadOrigin, values_callable=_ENUM_VALUES),
        nullable=False,
        default=WorkloadOrigin.MANAGED,
        comment="Origine du workload (managed, adopted, external)",
    )

    # ─── Alias de transition (purge STORY-166.6) ──────────────────────
    # Les consommateurs non renommés (services/API 166.2/166.3) continuent
    # d'écrire/lire les noms legacy — synonyms SQLAlchemy vers les
    # colonnes canoniques (mêmes données, zéro duplication).
    scan_date = synonym("last_scan_at")
    platform_info = synonym("hardware_info")

    # Credentials SSH — chiffrés au repos via le SecretManager (STORY-103.2) :
    # format opaque ``{"_encrypted": "<token Fernet>"}`` ; les lignes legacy
    # en clair sont migrées (ré-encryptées) à la première lecture.
    # ``ssh_private_key`` (et sa passphrase) sont migrés vers l'entité
    # SSHKey par la migration 1311 (STORY-131.1) ; username/password
    # (auth password) et sudo_* restent ici.
    credentials: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Clé SSH réutilisable (STORY-131.1) — N hosts peuvent référencer la
    # même clé ; la suppression de la clé déréférence (SET NULL).
    ssh_key_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("ssh_keys.id", ondelete="SET NULL"),
        nullable=True,
        comment="Clé SSH réutilisable (FK ssh_keys.id — SET NULL)",
    )

    last_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Configuration additionnelle
    extra_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    scan_success: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Indicates if the last capabilities scan succeeded",
    )
    os_info: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Operating system information detected during the last scan",
    )
    access_profile: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Access profile detected during the last scan (SSH user, sudo, capabilities)",
    )

    # Organisation (multi-tenant)
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Rattachement environnement (A14, STORY-166.4) — SET NULL : le host
    # est conservé si son environnement est supprimé.
    environment_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("environments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Environnement de rattachement (FK environments.id — SET NULL)",
    )

    # ─── Credentials : accès déchiffré + migration double lecture ──

    @property
    def decrypted_credentials(self) -> dict[str, Any]:
        """Credentials en clair — déchiffrement transparent (STORY-103.2).

        Double lecture :

        - colonne chiffrée (token Fernet détecté via le préfixe ``gAAAA``)
          → déchiffrement à la volée ;
        - ligne legacy en clair → lue telle quelle, puis **ré-encryptée au
          premier accès** : la réassignation de ``self.credentials`` marque
          la colonne *dirty* pour SQLAlchemy, la migration est donc persistée
          par le commit de l'appelant (idempotent : un ciphertext n'est
          jamais re-chiffré).

        Les lignes avec credentials vides (``{}``) ne sont pas migrées :
        il n'y a aucun secret à protéger.

        Returns:
            Credentials en clair (dict, éventuellement vide). Ne vit
            qu'en mémoire — ne jamais logger.

        Raises:
            SecretDecryptionError: Si le ciphertext est illisible (mauvaise
                clé maîtresse ou donnée corrompue/altérée).
        """
        stored = self.credentials
        if not isinstance(stored, dict) or not stored:
            return {}
        token = stored.get(_CREDENTIALS_CIPHERTEXT_KEY)
        if isinstance(token, str) and SecretManager.is_encrypted(token):
            return decrypt_credentials_from_storage(stored)
        # Ligne legacy en clair → ré-encryptage au premier accès.
        self.credentials = encrypt_credentials_for_storage(stored)
        return stored

    # Propriétés dérivées (depuis credentials déchiffrés) pour la réponse API
    @property
    def auth_method(self) -> str | None:
        return (self.decrypted_credentials or {}).get("auth_method")

    @property
    def username(self) -> str | None:
        return (self.decrypted_credentials or {}).get("username")

    @property
    def has_sudo(self) -> bool:
        creds = self.decrypted_credentials or {}
        return bool(creds.get("sudo_enabled") and creds.get("sudo_user"))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relations
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="hosts"
    )

    deployments: Mapped[list["Deployment"]] = relationship(
        "Deployment", back_populates="host", cascade="all, delete-orphan"
    )

    capabilities: Mapped[list["HostCapability"]] = relationship(
        "HostCapability", back_populates="host", cascade="all, delete-orphan"
    )

    ssh_key: Mapped["SSHKey | None"] = relationship(
        "SSHKey",
        back_populates="hosts",
    )

    environment: Mapped["Environment | None"] = relationship(
        "Environment",
        back_populates="hosts",
        foreign_keys="Host.environment_id",
    )

    ssh_fingerprints: Mapped[list["HostSSHFingerprint"]] = relationship(
        "HostSSHFingerprint",
        back_populates="host",
        cascade="all, delete-orphan",
    )

    # ─── Alias de transition ``type`` (purge STORY-166.6) ────────────

    @hybrid_property
    def type(self) -> TargetType:
        """Type legacy ``TargetType`` (transition — divergence n°4).

        Restitution : ``extra_metadata.migrated_type`` (trace posée par
        la migration 1661 **et** par le setter lors des créations
        legacy post-migration — source unique), sinon déduction depuis
        ``profile`` (``host_remote_docker`` → ``docker``, sinon
        ``physical``).
        """
        metadata = self.extra_metadata if isinstance(self.extra_metadata, dict) else {}
        migrated = metadata.get("migrated_type")
        if isinstance(migrated, str):
            try:
                return TargetType(migrated)
            except ValueError:
                pass
        if self.profile is HostProfile.HOST_REMOTE_DOCKER:
            return TargetType.DOCKER
        return TargetType.PHYSICAL

    @type.setter  # type: ignore[no-redef]
    def type(self, value: TargetType | str | HostProfile | None) -> None:
        """Mappe une valeur legacy ``TargetType`` vers ``profile``.

        Utilise la table d'arbitrage (:func:`map_target_to_host_profile`)
        avec l'adresse courante du host et trace la valeur legacy dans
        ``extra_metadata.migrated_type`` (echo API fidèle — même clé que
        la migration 1661).

        ⚠️ À la construction l'ordre des kwargs n'est pas garanti : si
        ``host`` n'est pas encore assigné, l'arbitrage local/distant
        défaut à « distant ». ``TargetService.create`` pose donc le type
        **après** construction (host connu) ; les constructions directes
        (fixtures, tests) doivent assigner ``host`` avant ``type``.
        """
        if isinstance(value, HostProfile):
            self.profile = value
            return
        if value is None:
            return
        member = _coerce_enum_member(value, TargetType)
        host_address = getattr(self, "host", None)
        self.profile = map_target_to_host_profile(member, host_address)
        if not isinstance(self.extra_metadata, dict):
            self.extra_metadata = {}
        self.extra_metadata["migrated_type"] = member.value

    def __repr__(self) -> str:
        return (
            f"<Host(id={self.id}, name={self.name}, "
            f"profile={self.profile}, status={self.status})>"
        )
