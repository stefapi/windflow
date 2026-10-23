"""
Modèle ScheduledTask pour les tâches planifiées (moteur scheduler — STORY-160).

STORY-160.1 — alignement spec 17 § Scheduler core : une définition porte
une ``action`` issue du **registre canonique**
([`services/action_registry.py`](../services/action_registry.py)) —
l'enum fermé ``TaskType`` a été retiré (migration ``1321`` avec mapping
défensif des ``task_type`` legacy) — un déclencheur ``cron`` **ou**
événement (``trigger_type``/``event_name``), un fuseau IANA
(``timezone``, défaut résolu au runtime depuis les settings) et une
politique d'erreur (``error_policy`` : ``ignore``|``retry``|``disable``).
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .organization import Organization


class ScheduledTask(Base):
    """
    Tâche planifiée conforme spec 17 (STORY-160.1).

    Stocke la configuration des tâches récurrentes/event-driven gérées
    par le moteur scheduler asyncio (STORY-160.2) : ``action`` du
    registre + ``parameters`` validés par le schéma Pydantic de l'action,
    trigger ``cron`` (expression validée croniter) ou ``event``
    (``event_name`` ∈ liste canonique ``EventType``), fuseau IANA et
    politique d'erreur.
    """

    __tablename__ = "scheduled_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    # STORY-160.1 : clé du registre canonique (validation à l'API via
    # action_registry.is_valid) — remplace l'enum fermé TaskType. Les
    # lignes legacy migrées portent une clé "legacy.<task_type>" gelée
    # (enabled=False, jamais exécutable — hors registre).
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    # Trigger : "cron" | "event" (spec 17). event_name requis si "event"
    # (validé à l'API — 422), ignoré sinon.
    trigger_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="cron"
    )
    event_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Fuseau IANA (ex. "Europe/Paris") — None = défaut settings (UTC),
    # résolu au runtime par le moteur (STORY-160.2).
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Politique d'erreur : "ignore" | "retry" | "disable" (spec 17).
    error_policy: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ignore"
    )
    cron_expression: Mapped[str] = mapped_column(
        String(100), nullable=False, default="0 * * * *"
    )
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_count: Mapped[int] = mapped_column(default=0)

    # Relations
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False
    )
    organization: Mapped["Organization"] = relationship(lazy="selectin")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<ScheduledTask(id={self.id}, name={self.name}, "
            f"action={self.action}, trigger={self.trigger_type}, "
            f"enabled={self.enabled})>"
        )
