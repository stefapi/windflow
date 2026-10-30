"""Modèle HostSSHFingerprint — empreintes known_hosts (STORY-131.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from ..database import Base

if TYPE_CHECKING:
    from .host import Host


class HostSSHFingerprint(Base):
    """Empreinte SSH attendue d'un serveur distant (spec 06, spec 15).

    Table ``host_ssh_fingerprints`` — équivalent ``known_hosts`` :
    vérifiée à chaque connexion (STORY-131.3), acceptation explicite à
    la première connexion (TOFU — *Trust On First Use*), blocage en cas
    de divergence (anti-MITM).

    STORY-166.1 : la FK ``host_id`` référence désormais ``hosts.id``
    (l'entité Host des specs existe en base — fin de l'arbitrage F3 de
    STORY-131).

    - ``key_type`` : algorithme de la **clé d'hôte** présentée (ex.
      ``ssh-ed25519``) — distinct du ``SSHKey.key_type`` (clé
      d'authentification utilisateur) ;
    - ``fingerprint`` : empreinte normalisée ``SHA256:<base64nopad>`` ;
    - ``accepted`` : ``TRUE`` après acceptation explicite (défaut
      ``False`` — une empreinte enregistrée mais non acceptée ne fait
      pas autorité) ;
    - contrainte UNIQUE ``(host_id, hostname, port, key_type)`` : une
      empreinte par serveur et par algorithme — un même hôte peut
      présenter plusieurs empreintes (multi-algorithmes) sans collision.
    """

    __tablename__ = "host_ssh_fingerprints"
    __table_args__ = (
        UniqueConstraint(
            "host_id",
            "hostname",
            "port",
            "key_type",
            name="uq_host_ssh_fp_identity",
        ),
        Index("idx_host_ssh_fp_host", "host_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    host_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hosts.id", ondelete="CASCADE"),
        nullable=False,
        comment="Host (hosts.id — STORY-166.1)",
    )

    hostname: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Adresse de connexion vérifiée",
    )

    port: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=22,
        comment="Port SSH de l'hôte vérifié",
    )

    key_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Algorithme de la clé d'hôte (ssh-ed25519…)",
    )

    fingerprint: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Empreinte attendue SHA256:<base64nopad>",
    )

    accepted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="TRUE après acceptation explicite (TOFU)",
    )

    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Date d'acceptation explicite",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    host: Mapped["Host"] = relationship(
        "Host",
        back_populates="ssh_fingerprints",
    )
    # Alias de transition (purge STORY-166.6) : relation legacy.
    target = synonym("host")

    def __repr__(self) -> str:
        """Représentation DEBUG (aucun secret — l'empreinte est publique)."""
        return (
            f"<HostSSHFingerprint(id={self.id}, host_id={self.host_id}, "
            f"hostname={self.hostname}, port={self.port}, "
            f"key_type={self.key_type}, accepted={bool(self.accepted)})>"
        )
