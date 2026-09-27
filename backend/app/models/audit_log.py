"""Modèle AuditLog — audit trail des actions critiques (STORY-125.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .user import User


class AuditLog(Base):
    """Ligne d'audit d'une action critique — journal immuable.

    Table ``audit_logs`` (spec 06 — modèle de données, spec 15 —
    sécurité § Audit trail) : répond à « qui a fait quoi, quand » en
    cas d'incident, avec l'acteur, l'action, la cible, l'IP source et
    le ``correlation_id`` du middleware (recherche d'incident par
    requête — colonne ajoutée par STORY-125 au-delà de la spec 06).

    Sécurité (rules 40, spec 15) :
    - **jamais de données sensibles dans ``details``** : la valeur est
      systématiquement passée par ``AuditService._sanitize_details``
      avant persistance (masquage ``***`` des clés sensibles — la
      garantie est structurelle, portée par le service) ;
    - conservation **documentaire** : contrairement aux tables des
      stories 123/124 (FK ``CASCADE``), la trace **survit** à la
      suppression de son acteur — ``user_id`` est nullable avec FK
      ``ON DELETE SET NULL`` : la ligne reste, l'acteur devient
      anonyme. Idem pour ``organization_id`` (FK ``SET NULL``, aucune
      relation ORM côté ``Organization`` requise) ;
    - la relation ``user`` est **sans cascade ni delete-orphan** (avec
      ``passive_deletes=True``) : la suppression ORM d'un user nullifie
      ``user_id`` des lignes chargées, le ``ON DELETE SET NULL`` couvre
      les suppressions SQL directes.

    Colonnes notables :
    - ``action`` : catalogue spec 15 (``user.login``, ``stack.deleted``…) ;
    - ``resource_id`` en ``Text`` : les IDs de conteneurs Docker
      peuvent excéder ``String(36)`` ;
    - ``details`` en JSON natif : lecture requêtable sans parsing.

    Écriture : ``AuditService.log()`` — best-effort, ne lève jamais
    (STORY-125.1) ; consultation : ``AuditService.list_entries()``
    (endpoint admin STORY-125.3).
    """

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Acteur — NULL si anonymisé après suppression du compte "
        "(FK SET NULL : conservation documentaire, spec 06)",
    )

    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Organisation concernée par l'action (recherche par org)",
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Action auditée — catalogue spec 15 (user.login, stack.deleted…)",
    )

    resource_type: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        comment="Type de la cible (stack, container, user…)",
    )

    resource_id: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Identifiant de la cible (Text : IDs conteneurs Docker longs)",
    )

    details: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Contexte JSON — TOUJOURS sanitizé par "
        "AuditService._sanitize_details avant persistance (secrets masqués)",
    )

    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP source de l'action (IPv6 max 45 chars)",
    )

    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="Correlation ID du middleware (X-Correlation-ID — "
        "recherche d'incident par requête, rules 45)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        comment="Horodatage de l'action (index requis spec 06)",
    )

    __table_args__ = (Index("idx_audit_resource", "resource_type", "resource_id"),)

    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        """Représentation DEBUG — jamais ``details`` ni ``ip_address``."""
        return (
            f"<AuditLog(id={self.id}, user_id={self.user_id}, "
            f"action={self.action}, resource_type={self.resource_type})>"
        )
