"""
Modèle Target pour gestion des serveurs cibles de déploiement.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ..enums.target import CapabilityType, TargetStatus, TargetType

if TYPE_CHECKING:
    from .deployment import Deployment
    from .organization import Organization
    from .target_capability import TargetCapability


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

    # Credentials (chiffrés en production avec Vault)
    credentials: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Statut
    status: Mapped[TargetStatus] = mapped_column(
        SQLEnum(TargetStatus), nullable=False, default=TargetStatus.OFFLINE
    )
    last_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Configuration additionnelle
    extra_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    scan_date: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
        comment="Timestamp of the last capabilities scan",
    )
    scan_success: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True,
        comment="Indicates if the last capabilities scan succeeded",
    )
    platform_info: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None,
        comment="Platform capabilities detected during the last scan",
    )
    os_info: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None,
        comment="Operating system information detected during the last scan",
    )

    # Organisation (multi-tenant)
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Propriétés dérivées (depuis credentials JSON) pour la réponse API
    @property
    def auth_method(self) -> str | None:
        return (self.credentials or {}).get("auth_method")

    @property
    def username(self) -> str | None:
        return (self.credentials or {}).get("username")

    @property
    def has_sudo(self) -> bool:
        return bool((self.credentials or {}).get("sudo_user"))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
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

    def __repr__(self) -> str:
        return f"<Target(id={self.id}, name={self.name}, type={self.type}, status={self.status})>"
