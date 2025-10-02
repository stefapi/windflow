"""
Modèle Organization pour support multi-tenant.
"""

from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, List

from ..database import Base

if TYPE_CHECKING:
    from .user import User
    from .target import Target
    from .stack import Stack


class Organization(Base):
    """
    Modèle organisation pour support multi-tenant.

    Chaque organisation a ses propres utilisateurs, serveurs cibles et stacks.
    """

    __tablename__ = "organizations"

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )

    # Informations de base
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Configuration JSON
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

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
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan"
    )

    targets: Mapped[List["Target"]] = relationship(
        "Target",
        back_populates="organization",
        cascade="all, delete-orphan"
    )

    stacks: Mapped[List["Stack"]] = relationship(
        "Stack",
        back_populates="organization",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name}, slug={self.slug})>"
