"""
Modèle User pour l'authentification et gestion des utilisateurs.
"""

from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from ..database import Base

if TYPE_CHECKING:
    from .organization import Organization
    from .stack_review import StackReview


class User(Base):
    """
    Modèle utilisateur avec authentification JWT.

    Supporte l'authentification locale et Keycloak SSO (optionnel).
    """

    __tablename__ = "users"

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )

    # Informations de base
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)

    # Authentification
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Keycloak SSO (optionnel)
    keycloak_id: Mapped[str] = mapped_column(String(255), nullable=True, unique=True)

    # Organisation
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
    last_login: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Relations
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="users"
    )

    stack_reviews: Mapped[list["StackReview"]] = relationship(
        "StackReview",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"
