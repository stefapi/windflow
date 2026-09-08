"""Modèle UserOrganization — association utilisateur ↔ organisation avec rôle."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from ..database import Base
from ..enums.rbac import Role

if TYPE_CHECKING:
    from .organization import Organization
    from .user import User


class UserOrganization(Base):
    """Association utilisateur ↔ organisation portant le rôle RBAC.

    Table d'association ``user_organizations`` (spec 06 — modèle de
    données, spec 08 — RBAC & permissions) : PK composite
    ``(user_id, organization_id)``, rôle borné à l'enum partagé ``Role``
    (``viewer`` / ``operator`` / ``admin``), défaut serveur ``viewer``.

    Le Super Admin est un rôle **système** identifié par le flag
    ``User.is_superuser`` et ne peut jamais être stocké comme valeur
    d'association (protection anti-escalade, spec 08).
    """

    __tablename__ = "user_organizations"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )

    role: Mapped[Role] = mapped_column(
        String(20),
        nullable=False,
        default=Role.VIEWER,
        server_default="viewer",
        comment="Rôle de l'utilisateur dans l'organisation "
        "(viewer | operator | admin)",
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Date d'adhésion de l'utilisateur à l'organisation",
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

    user: Mapped["User"] = relationship(
        "User",
        back_populates="organization_links",
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="user_links",
    )

    @validates("role")
    def _validate_role(self, key: str, value: Role | str) -> Role:
        """Borne ``role`` à l'enum partagé ``Role``.

        Accepte une instance ``Role`` ou une chaîne convertible et
        retourne le ``Role`` correspondant ; lève ``ValueError`` pour
        toute autre valeur — y compris ``super_admin`` (rôle système
        porté par ``User.is_superuser``, jamais une valeur
        d'association) et la chaîne vide.
        """
        if isinstance(value, Role):
            return value
        try:
            return Role(value)
        except ValueError as exc:
            raise ValueError(
                f"Invalid role {value!r}: expected one of "
                f"{[member.value for member in Role]} — super_admin is a "
                "system role (User.is_superuser) and can never be stored "
                "in user_organizations"
            ) from exc

    def __repr__(self) -> str:
        return (
            f"<UserOrganization(user_id={self.user_id}, "
            f"organization_id={self.organization_id}, "
            f"role={self.role})>"
        )
