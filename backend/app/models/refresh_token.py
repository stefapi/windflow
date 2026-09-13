"""Modèle RefreshToken — refresh tokens opaques révocables (STORY-123.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .user import User


class RefreshToken(Base):
    """Refresh token opaque révocable associé à un utilisateur.

    Table ``refresh_tokens`` (spec 06 — modèle de données, spec 07 —
    authentification) : seule l'empreinte (**hash**) du token est
    stockée — jamais la valeur en clair (garantie structurelle :
    aucune colonne n'existe pour la valeur brute).

    - ``token_hash`` : hash fort (Argon2, arbitrage F2) du token opaque
      émis au login (émission portée par STORY-123.2/123.3) ;
    - ``expires_at`` : date d'expiration — durée de vie configurable
      via ``REFRESH_TOKEN_EXPIRE_DAYS`` (7 jours par défaut) ;
    - ``revoked_at`` : date de révocation (NULL = token actif) — permet
      de distinguer un token inconnu d'un token consommé réutilisé
      (révocation défensive de la famille, STORY-123.3) et laisse une
      trace auditable du logout.

    La suppression d'un utilisateur entraîne la purge de ses refresh
    tokens (``ondelete="CASCADE"`` — hygiène des données).
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Propriétaire du token (index requis spec 06)",
    )

    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hash du token opaque — jamais la valeur en clair",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="Date d'expiration (index requis spec 06 — purge)",
    )

    revoked_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
        comment="Date de révocation (NULL = token actif)",
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
        back_populates="refresh_tokens",
    )

    def __repr__(self) -> str:
        """Représentation DEBUG sans exposer le hash du token."""
        return (
            f"<RefreshToken(user_id={self.user_id}, "
            f"expires_at={self.expires_at}, "
            f"revoked={self.revoked_at is not None})>"
        )
