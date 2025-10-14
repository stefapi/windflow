"""
Modèle Deployment pour suivi des déploiements de stacks.
"""

from datetime import datetime
from uuid import uuid4
from enum import Enum
from sqlalchemy import String, DateTime, JSON, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from ..database import Base

if TYPE_CHECKING:
    from .stack import Stack
    from .target import Target
    from .organization import Organization


class DeploymentStatus(str, Enum):
    """Statuts possibles pour un déploiement."""
    PENDING = "pending"
    DEPLOYING = "deploying"
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"
    ROLLING_BACK = "rolling_back"


class Deployment(Base):
    """
    Modèle déploiement pour tracking des stacks déployées.

    Représente l'instance d'une stack déployée sur une cible.
    """

    __tablename__ = "deployments"

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )

    # Relations avec stack et target
    stack_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("stacks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    target_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("targets.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Organisation (multi-tenant)
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Informations de déploiement
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Statut
    status: Mapped[DeploymentStatus] = mapped_column(
        SQLEnum(DeploymentStatus),
        nullable=False,
        default=DeploymentStatus.PENDING
    )

    # Configuration utilisée au déploiement (snapshot)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Variables appliquées
    variables: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Logs et erreurs
    logs: Mapped[str] = mapped_column(Text, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    # Métriques
    deploy_duration_seconds: Mapped[float] = mapped_column(nullable=True)

    # Timestamps
    deployed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

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
        back_populates="deployments"
    )

    stack: Mapped["Stack"] = relationship(
        "Stack",
        back_populates="deployments"
    )

    target: Mapped["Target"] = relationship(
        "Target",
        back_populates="deployments"
    )

    def __repr__(self) -> str:
        return f"<Deployment(id={self.id}, name={self.name}, status={self.status})>"
