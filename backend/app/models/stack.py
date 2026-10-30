"""
Modèle Stack pour gestion des templates Docker Compose.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ..enums.host import WorkloadOrigin
from ..enums.target import TargetType

if TYPE_CHECKING:
    from .deployment import Deployment
    from .environment import Environment
    from .organization import Organization
    from .stack_version import StackVersion


class Stack(Base):
    """
    Modèle stack pour templates Docker Compose.

    Représente une configuration Docker Compose réutilisable.
    """

    __tablename__ = "stacks"

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Informations de base
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Template Docker Compose (YAML stocké en JSON)
    template: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Variables configurables (format simple pour JSONForms)
    variables: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Variables configurables au format simple",
    )

    # Métadonnées
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    category: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Type de déploiement supporté
    target_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=TargetType.DOCKER.value,
        comment="Type de déploiement supporté par ce stack",
    )

    # Paramètres spécifiques à la target (ex: volumes à supprimer)
    target_parameters: Mapped[dict] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Paramètres spécifiques à la target (ex: volumes à supprimer)",
    )

    # Statut public et statistiques
    is_public: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    is_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, default=None
    )
    downloads: Mapped[int] = mapped_column(default=0, nullable=False)
    rating: Mapped[float] = mapped_column(default=0.0, nullable=False)

    # Métadonnées additionnelles
    icon_url: Mapped[str] = mapped_column(String(500), nullable=True)
    screenshots: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    documentation_url: Mapped[str] = mapped_column(String(500), nullable=True)
    author: Mapped[str] = mapped_column(String(255), nullable=True)
    license: Mapped[str] = mapped_column(String(100), nullable=True, default="MIT")
    deployment_name: Mapped[str] = mapped_column(
        String(255), nullable=True, comment="Nom par défaut du déploiement (template)"
    )

    # Organisation (multi-tenant)
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ─── Axe origine + environnement + GitOps (STORY-166.4) ──────────

    # Axe origine de la matrice « profil × origine » (spec 03/06) —
    # l'adoption pose ``adopted`` (T5), la création manuelle reste
    # ``managed`` (défaut), l'import externe posera ``external``.
    origin: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=WorkloadOrigin.MANAGED.value,
        comment="Origine du workload (managed, adopted, external)",
    )

    # URL du dépôt Git source — persistée pour le GitOps futur, jamais
    # clonée/exécutée à ce stade (D2 ; validation URL côté schémas).
    git_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL du dépôt Git source — GitOps futur (pas de clone à ce stade)",
    )

    # Rattachement environnement (A14) — la suppression de
    # l'environnement déréférence (SET NULL), la stack est conservée.
    environment_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("environments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Environnement de rattachement (FK environments.id — SET NULL)",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relations
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="stacks"
    )

    deployments: Mapped[list["Deployment"]] = relationship(
        "Deployment", back_populates="stack", cascade="all, delete-orphan"
    )

    versions: Mapped[list["StackVersion"]] = relationship(
        "StackVersion",
        back_populates="stack",
        cascade="all, delete-orphan",
        order_by="StackVersion.version_number.desc()",
    )

    environment: Mapped[Optional["Environment"]] = relationship(
        "Environment", back_populates="stacks"
    )

    def __repr__(self) -> str:
        return f"<Stack(id={self.id}, name={self.name}, version={self.version})>"
