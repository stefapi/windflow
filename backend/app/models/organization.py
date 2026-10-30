"""
Modèle Organization pour support multi-tenant.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from ..database import Base

if TYPE_CHECKING:
    from .deployment import Deployment
    from .environment import Environment
    from .host import Host
    from .stack import Stack
    from .user_organization import UserOrganization


class Organization(Base):
    """
    Modèle organisation pour support multi-tenant.

    Chaque organisation a ses propres utilisateurs, serveurs cibles et stacks.
    """

    __tablename__ = "organizations"

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Informations de base
    name: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Configuration JSON
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relations
    # (STORY-121.3 : la relation directe users (FK héritée
    # users.organization_id) a été retirée — les membres passent
    # exclusivement par l'association user_links)

    # Associations RBAC multi-membres (STORY-121.1)
    user_links: Mapped[List["UserOrganization"]] = relationship(
        "UserOrganization", back_populates="organization", cascade="all, delete-orphan"
    )

    # STORY-166.1 : relation canonique ``hosts`` (Host.organization
    # back_populates="hosts") ; ``targets`` reste un synonym de
    # transition (purge STORY-166.6).
    hosts: Mapped[List["Host"]] = relationship(
        "Host", back_populates="organization", cascade="all, delete-orphan"
    )
    targets = synonym("hosts")

    stacks: Mapped[List["Stack"]] = relationship(
        "Stack", back_populates="organization", cascade="all, delete-orphan"
    )

    # STORY-166.4 : environnements de déploiement (spec 06 — table
    # ``environments``, UNIQUE(organization_id, name)).
    environments: Mapped[List["Environment"]] = relationship(
        "Environment", back_populates="organization", cascade="all, delete-orphan"
    )

    deployments: Mapped[List["Deployment"]] = relationship(
        "Deployment", back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name}, slug={self.slug})>"
