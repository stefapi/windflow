"""
Modèle User pour l'authentification et gestion des utilisateurs.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .refresh_token import RefreshToken
    from .user_organization import UserOrganization


class User(Base):
    """
    Modèle utilisateur avec authentification JWT.

    Supporte l'authentification locale et Keycloak SSO (optionnel).
    """

    __tablename__ = "users"

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Informations de base
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    username: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)

    # Authentification
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Keycloak SSO (optionnel)
    keycloak_id: Mapped[str] = mapped_column(String(255), nullable=True, unique=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_login: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Associations RBAC multi-organisations (STORY-121.1) — depuis
    # STORY-121.3, l'appartenance organisation passe exclusivement par
    # cette table (la colonne héritée users.organization_id a été
    # retirée par la migration 1213)
    organization_links: Mapped[List["UserOrganization"]] = relationship(
        "UserOrganization", back_populates="user", cascade="all, delete-orphan"
    )

    # Refresh tokens opaques révocables (STORY-123.1) — la suppression
    # du user purge ses refresh tokens (FK CASCADE + delete-orphan)
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"
