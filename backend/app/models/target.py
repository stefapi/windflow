"""
Modèle Target pour gestion des serveurs cibles de déploiement.
"""

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.secret_manager import SecretManager, get_secret_manager
from ..database import Base
from ..enums.target import TargetStatus, TargetType

if TYPE_CHECKING:
    from .deployment import Deployment
    from .host_ssh_fingerprint import HostSSHFingerprint
    from .organization import Organization
    from .ssh_key import SSHKey
    from .target_capability import TargetCapability

# Clé unique du dict opaque stocké en colonne ``credentials`` : la valeur
# est un token Fernet (préfixe ``gAAAA``) englobant tout le JSON chiffré.
_CREDENTIALS_CIPHERTEXT_KEY: str = "_encrypted"


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
        # quelle ; la migration est gérée par ``Target.decrypted_credentials``.
        return stored
    decoded = json.loads(get_secret_manager().decrypt(token))
    return decoded if isinstance(decoded, dict) else {}


class Target(Base):
    """
    Modèle serveur cible pour déploiements.

    Représente un serveur Docker, VM, ou serveur physique
    où déployer des stacks.
    """

    __tablename__ = "targets"

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
    type: Mapped[TargetType] = mapped_column(
        SQLEnum(TargetType), nullable=False, default=TargetType.DOCKER
    )

    # Credentials SSH — chiffrés au repos via le SecretManager (STORY-103.2) :
    # format opaque ``{"_encrypted": "<token Fernet>"}`` ; les lignes legacy
    # en clair sont migrées (ré-encryptées) à la première lecture.
    # ``ssh_private_key`` (et sa passphrase) sont migrés vers l'entité
    # SSHKey par la migration 1311 (STORY-131.1) ; username/password
    # (auth password) et sudo_* restent ici.
    credentials: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Clé SSH réutilisable (STORY-131.1) — N cibles peuvent référencer la
    # même clé ; la suppression de la clé déréférence (SET NULL), la
    # gestion (API) est portée par STORY-131.2.
    ssh_key_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("ssh_keys.id", ondelete="SET NULL"),
        nullable=True,
        comment="Clé SSH réutilisable (FK ssh_keys.id — SET NULL)",
    )

    # Statut
    status: Mapped[TargetStatus] = mapped_column(
        SQLEnum(TargetStatus), nullable=False, default=TargetStatus.OFFLINE
    )
    last_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Configuration additionnelle
    extra_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    scan_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Timestamp of the last capabilities scan",
    )
    scan_success: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Indicates if the last capabilities scan succeeded",
    )
    platform_info: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Platform capabilities detected during the last scan",
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
        "Organization", back_populates="targets"
    )

    deployments: Mapped[list["Deployment"]] = relationship(
        "Deployment", back_populates="target", cascade="all, delete-orphan"
    )

    capabilities: Mapped[list["TargetCapability"]] = relationship(
        "TargetCapability", back_populates="target", cascade="all, delete-orphan"
    )

    ssh_key: Mapped["SSHKey | None"] = relationship(
        "SSHKey",
        back_populates="targets",
    )

    ssh_fingerprints: Mapped[list["HostSSHFingerprint"]] = relationship(
        "HostSSHFingerprint",
        back_populates="target",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Target(id={self.id}, name={self.name}, type={self.type}, status={self.status})>"
