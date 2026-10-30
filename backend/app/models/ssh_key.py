"""Modèle SSHKey — clés SSH réutilisables chiffrées au repos (STORY-131.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from ..core.secret_manager import get_secret_manager
from ..database import Base

if TYPE_CHECKING:
    from .host import Host


class SSHKey(Base):
    """Clé SSH réutilisable partagée par N cibles (spec 06 § SSHKey).

    Table ``ssh_keys`` : les cibles à accès SSH référencent l'entité via
    ``targets.ssh_key_id`` (FK ``SET NULL``) au lieu d'embarquer une clé
    privée chacune dans leurs credentials.

    Sécurité (spec 15 § Hosts distants, STORY-131.1) :

    - ``private_key_encrypted`` contient **exclusivement** un token Fernet
      produit par le :class:`~app.core.secret_manager.SecretManager`
      (préfixe ``gAAAA``) — **jamais** une clé privée en clair en colonne ;
    - le déchiffrement n'existe qu'en mémoire via la propriété
      :attr:`decrypted_private_key` (jamais loggée) ;
    - ``__repr__`` n'expose ni la clé privée ni la clé publique.

    Colonnes (spec 06 — conformité stricte) :

    - ``name`` : libellé d'affichage **unique** (identification dans les
      listes) ;
    - ``key_type`` : algorithme (``ssh-ed25519`` recommandé, ``ssh-rsa``
      accepté) ;
    - ``public_key`` : partie publique consultable (déploiement
      ``authorized_keys``) — non sensible par nature ;
    - ``fingerprint`` : empreinte normalisée ``SHA256:<base64nopad>``
      (~50 car., asyncssh ``get_fingerprint()``) — sert de clé de
      déduplication des clés importées (une ``SSHKey`` par clé unique) ;
    - ``last_used_at`` : dernière session réussie (STORY-131.2/131.3).
    """

    __tablename__ = "ssh_keys"
    __table_args__ = (Index("idx_ssh_keys_fingerprint", "fingerprint"),)

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="Nom d'affichage unique de la clé",
    )

    key_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ssh-ed25519",
        comment="Algorithme (ssh-ed25519 recommandé, ssh-rsa accepté)",
    )

    public_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Partie publique (déploiement authorized_keys)",
    )

    private_key_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Clé privée chiffrée (token Fernet) — jamais en clair",
    )

    fingerprint: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Empreinte SHA256:<base64nopad> (identification, dédup)",
    )

    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Dernière session SSH réussie utilisant cette clé",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relations — N hosts référencent la même clé (FK SET NULL côté
    # hosts : la suppression de la clé déréférence, jamais silencieuse
    # côté API, portée par STORY-131.2). STORY-166.1 : relation canonique
    # ``hosts`` (Host.ssh_key back_populates="hosts") ; ``targets``
    # reste un synonym de transition (purge STORY-166.6).
    hosts: Mapped[list["Host"]] = relationship(
        "Host",
        back_populates="ssh_key",
    )
    targets = synonym("hosts")

    @property
    def decrypted_private_key(self) -> str:
        """Clé privée en clair — déchiffrement en mémoire uniquement.

        Returns:
            La clé privée PEM déchiffrée. Ne vit qu'en mémoire : ne
            jamais logger ni exposer dans une réponse API.

        Raises:
            SecretDecryptionError: Si le ciphertext est illisible
                (mauvaise clé maîtresse ou donnée corrompue).
        """
        return get_secret_manager().decrypt(self.private_key_encrypted)

    def __repr__(self) -> str:
        """Représentation DEBUG sans exposer le moindre matériau de clé."""
        return (
            f"<SSHKey(id={self.id}, name={self.name}, "
            f"key_type={self.key_type}, fingerprint={self.fingerprint})>"
        )
