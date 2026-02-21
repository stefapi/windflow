"""
Modèle StackVersion pour le versioning des stacks.

Stocke l'historique des modifications d'un stack (compose content, variables, etc.).
"""

from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, DateTime, JSON, ForeignKey, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from ..database import Base

if TYPE_CHECKING:
    from .stack import Stack
    from .user import User


class StackVersion(Base):
    """
    Version historique d'un stack.

    Chaque modification du compose_content ou des variables
    crée une nouvelle entrée dans l'historique.
    """

    __tablename__ = "stack_versions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    stack_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("stacks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Numéro de version incrémental",
    )

    compose_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Contenu YAML du compose à cette version",
    )

    variables: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Variables à cette version",
    )

    change_summary: Mapped[str] = mapped_column(
        String(500),
        nullable=True,
        comment="Résumé des modifications",
    )

    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relations
    stack: Mapped["Stack"] = relationship(
        "Stack",
        back_populates="versions",
    )

    author: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<StackVersion(id={self.id}, stack_id={self.stack_id}, v={self.version_number})>"
