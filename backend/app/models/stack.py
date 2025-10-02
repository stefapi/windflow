"""
Modèle Stack pour gestion des templates Docker Compose.
"""

from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, List

from ..database import Base

if TYPE_CHECKING:
    from .organization import Organization
    from .deployment import Deployment


class Stack(Base):
    """
    Modèle stack pour templates Docker Compose.

    Représente une configuration Docker Compose réutilisable.
    """

    __tablename__ = "stacks"

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )

    # Informations de base
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Template Docker Compose (YAML stocké en JSON)
    template: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Variables configurables
    variables: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Métadonnées
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    category: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Marketplace (si le stack est public)
    is_public: Mapped[bool] = mapped_column(default=False, nullable=False)
    downloads: Mapped[int] = mapped_column(default=0, nullable=False)
    rating: Mapped[float] = mapped_column(default=0.0, nullable=False)

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
        back_populates="stacks"
    )

    deployments: Mapped[List["Deployment"]] = relationship(
        "Deployment",
        back_populates="stack",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Stack(id={self.id}, name={self.name}, version={self.version})>"
