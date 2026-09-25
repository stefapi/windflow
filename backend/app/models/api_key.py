"""Modèle APIKey — clés API ``wf_ak_`` révocables (STORY-124.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .user import User


class APIKey(Base):
    """Clé API préfixée ``wf_ak_`` associée à un utilisateur.

    Table ``api_keys`` (spec 06 — modèle de données, spec 07 —
    authentification) : seule l'empreinte (**hash**) de la clé est
    stockée — jamais la valeur en clair (garantie structurelle :
    aucune colonne n'existe pour la valeur brute).

    - ``name`` : libellé choisi par l'utilisateur (identification
      des clés dans la liste, sans secret) ;
    - ``key_hash`` : hash fort de la clé ``wf_ak_`` émise à la
      création (génération et vérification portées par
      STORY-124.2/124.3) — la clé complète n'est affichée qu'une
      seule fois à la création ;
    - ``expires_at`` : date d'expiration optionnelle — ``NULL``
      signifie que la clé n'expire jamais ;
    - ``last_used_at`` : dernière utilisation réussie (alimentée
      de façon throttlée par la voie d'authentification par clé) ;
    - ``revoked`` : révocation **administrative** distincte de
      l'expiration — une clé expirée n'est pas « révoquée » et
      réciproquement (les deux états sont indépendants).

    La suppression d'un utilisateur entraîne la purge de ses clés
    API (``ondelete="CASCADE"`` — hygiène des données).
    """

    __tablename__ = "api_keys"

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
        comment="Propriétaire de la clé (index requis spec 06)",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Libellé de la clé choisi par l'utilisateur",
    )

    key_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hash de la clé wf_ak_ — jamais la valeur en clair",
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Date d'expiration (NULL = n'expire jamais)",
    )

    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Dernière utilisation réussie (mise à jour throttlée)",
    )

    revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Révocation administrative (distincte de l'expiration)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="api_keys",
    )

    def __repr__(self) -> str:
        """Représentation DEBUG sans exposer le hash ni la clé."""
        return (
            f"<APIKey(id={self.id}, user_id={self.user_id}, "
            f"name={self.name}, revoked={bool(self.revoked)})>"
        )
