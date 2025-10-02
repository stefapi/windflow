"""
Modèle Target pour gestion des serveurs cibles de déploiement.
"""

from datetime import datetime
from uuid import uuid4
from enum import Enum
from sqlalchemy import String, DateTime, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, List

from ..database import Base

if TYPE_CHECKING:
    from .organization import Organization
    from .deployment import Deployment


class TargetType(str, Enum):
    """Types de cibles de déploiement supportés."""
    DOCKER = "docker"
    DOCKER_SWARM = "docker_swarm"
    KUBERNETES = "kubernetes"
    VM = "vm"
    PHYSICAL = "physical"


class TargetStatus(str, Enum):
    """Statuts possibles pour une cible."""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class Target(Base):
    """
    Modèle serveur cible pour déploiements.

    Représente un serveur Docker, VM, ou serveur physique où déployer des stacks.
    """

    __tablename__ = "targets"

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )

    # Informations de base
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=True)

    # Configuration
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(default=22, nullable=False)
    type: Mapped[TargetType] = mapped_column(
        SQLEnum(TargetType),
        nullable=False,
        default=TargetType.DOCKER
    )

    # Credentials (chiffrés en production avec Vault)
    credentials: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Statut
    status: Mapped[TargetStatus] = mapped_column(
        SQLEnum(TargetStatus),
        nullable=False,
        default=TargetStatus.OFFLINE
    )
    last_check: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Configuration additionnelle
    extra_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Organisation (multi-tenant)
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relations
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="targets"
    )

    deployments: Mapped[List["Deployment"]] = relationship(
        "Deployment",
        back_populates="target",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Target(id={self.id}, name={self.name}, type={self.type}, status={self.status})>"
