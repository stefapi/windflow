"""Modèle HostCapability — capacités détectées par host (STORY-166.1).

Renommage canonique de ``TargetCapability`` (table ``target_capabilities``
→ ``host_capabilities``) : colonnes identiques, FK ``hosts.id`` CASCADE,
contrainte ``UNIQUE(host_id, capability_type)`` recréée sous le nom
``uq_host_capability_type``.

L'ancien chemin :mod:`app.models.target_capability` devient un alias de
transition (``TargetCapability = HostCapability``) — purge STORY-166.6.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from ..database import Base
from ..enums.host import CapabilityType

if TYPE_CHECKING:
    from .host import Host

_ENUM_VALUES = lambda cls: [member.value for member in cls]  # noqa: E731


class HostCapability(Base):
    """Capacité détectée pour un host donné."""

    __tablename__ = "host_capabilities"
    __table_args__ = (
        UniqueConstraint(
            "host_id",
            "capability_type",
            name="uq_host_capability_type",
        ),
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
        index=True,
    )

    capability_type: Mapped[CapabilityType] = mapped_column(
        SQLEnum(CapabilityType, values_callable=_ENUM_VALUES),
        nullable=False,
    )

    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Informations supplémentaires retournées par le scanner",
    )

    detected_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Date de détection de la capacité",
    )

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

    host: Mapped["Host"] = relationship(
        "Host",
        back_populates="capabilities",
    )
    # Alias de transition (purge STORY-166.6) : les services non encore
    # renommés écrivent/lisent ``target_id`` — même colonne hosts.id.
    target_id = synonym("host_id")

    def __repr__(self) -> str:
        return (
            f"<HostCapability(id={self.id}, "
            f"host_id={self.host_id}, "
            f"type={self.capability_type}, "
            f"available={self.is_available})>"
        )
