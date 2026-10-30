"""Modèle Environment — environnements de déploiement (spec 06, STORY-166.4).

Table ``environments`` (item plan A14) : regroupement logique des stacks
et des hosts d'une organisation (dev/staging/prod — ``type`` à valeur
libre à ce stade). Le CRUD multi-environnements complet est hors
périmètre (plan §6) : cette story pose la table + le rattachement
(``stacks.environment_id`` / ``hosts.environment_id``), sans endpoint.

Isolation organisationnelle (règle 40) :

- FK ``organizations.id`` ``ON DELETE CASCADE`` ;
- ``UNIQUE(organization_id, name)`` (contrainte ``uq_environment_org_name``)
  — deux organisations peuvent réutiliser le même nom, jamais au sein
  d'une même organisation.

Sécurité : ``configuration`` (paramètres réseau, variables partagées)
peut contenir des valeurs sensibles — jamais exposée dans ``__repr__``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .host import Host
    from .organization import Organization
    from .stack import Stack


class Environment(Base):
    """Environnement de déploiement rattaché à une organisation (spec 06).

    Schéma canonique : ``id``, ``name``, ``type``, ``organization_id``
    (FK CASCADE), ``configuration`` (JSON), ``is_active``, timestamps,
    ``UNIQUE(organization_id, name)``.
    """

    __tablename__ = "environments"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_environment_org_name"),
    )

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Informations de base
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="development",
        comment="Type d'environnement (dev, staging, prod — valeur libre à ce stade)",
    )

    # Organisation (multi-tenant) — isolation : CASCADE à la suppression
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Configuration JSON : paramètres réseau, variables partagées
    # (potentiellement sensible — jamais loggée ni exposée dans __repr__)
    configuration: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Paramètres réseau, variables partagées (JSON)",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

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
        "Organization", back_populates="environments"
    )

    # Rattachements (STORY-166.4) — suppression de l'environnement →
    # SET NULL côté stacks/hosts (les entités rattachées sont conservées).
    stacks: Mapped[list["Stack"]] = relationship(
        "Stack",
        back_populates="environment",
        foreign_keys="Stack.environment_id",
    )
    hosts: Mapped[list["Host"]] = relationship(
        "Host",
        back_populates="environment",
        foreign_keys="Host.environment_id",
    )

    def __repr__(self) -> str:
        # Pas de ``configuration`` (variables partagées potentiellement
        # sensibles — règle 40).
        return (
            f"<Environment(id={self.id}, name={self.name}, "
            f"type={self.type}, organization_id={self.organization_id})>"
        )
