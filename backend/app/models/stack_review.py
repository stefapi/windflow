"""
Modèle StackReview pour les avis et notes des stacks.
"""

from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, DateTime, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from ..database import Base

if TYPE_CHECKING:
    from .stack import Stack
    from .user import User


class StackReview(Base):
    """
    Modèle pour les avis et notes des stacks marketplace.

    Un utilisateur ne peut laisser qu'un seul avis par stack.
    """

    __tablename__ = "stack_reviews"

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4())
    )

    # Relations
    stack_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("stacks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Contenu de l'avis
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Note de 1 à 5 étoiles"
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Titre de l'avis"
    )

    comment: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Commentaire détaillé"
    )

    # Statistiques d'utilité
    helpful_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Nombre de personnes ayant trouvé l'avis utile"
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

    # Relations ORM
    stack: Mapped["Stack"] = relationship(
        "Stack",
        back_populates="reviews"
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="stack_reviews"
    )

    # Contrainte : un seul avis par utilisateur et par stack
    __table_args__ = (
        UniqueConstraint('stack_id', 'user_id', name='uq_stack_user_review'),
    )

    def __repr__(self) -> str:
        return f"<StackReview(id={self.id}, stack_id={self.stack_id}, rating={self.rating})>"
