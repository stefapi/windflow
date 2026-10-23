"""Modèle ScheduledTaskExecution — historique des exécutions (STORY-161).

Matérialise le schéma spec 06 § Entités d'automatisation : chaque
exécution d'une définition ``scheduled_tasks`` — par cron, par événement
ou manuelle — est persistée avec son cycle de vie complet
(``queued → running → success | failed`` ; ``skipped`` pour un saut par
verrou), l'origine du déclenchement (``triggered_by`` :
``cron``|``event``|``manual`` — nomenclature spec 06, la traduction
depuis le contrat moteur ``schedule`` est faite par
``DatabaseExecutionStore``), sa durée, son erreur assainie et son
journal ligne à ligne horodaté (JSON ISO 8601 UTC).

Index (spec 06, requêtes de rétention/historique) : ``task_id``,
``status``, ``started_at`` — nommés selon la migration ``1331`` pour
rester en phase avec Alembic (``alembic check`` sans diff).

La suppression d'une définition emporte ses exécutions (FK
``ON DELETE CASCADE`` — testée en intégration ; les relations ORM ne
portent pas de cascade Python, la base est source de vérité).
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .scheduled_task import ScheduledTask


def _utcnow() -> datetime:
    """Horodatage UTC aware (stockage UTC — spec 06/17)."""
    return datetime.now(timezone.utc)


class ScheduledTaskExecution(Base):
    """Exécution d'une tâche planifiée (spec 06 — STORY-161).

    Écrite exclusivement par ``DatabaseExecutionStore`` (contrat
    ``ExecutionStore`` de STORY-160.2) depuis le moteur scheduler ; lue
    par les endpoints de consultation ``/schedules/executions``.

    Attributes:
        id: Identifiant unique (uuid4 str).
        task_id: FK ``scheduled_tasks.id`` (CASCADE à la suppression).
        status: ``queued`` | ``running`` | ``success`` | ``failed`` |
            ``skipped``.
        triggered_by: Origine — ``cron`` | ``event`` | ``manual``
            (nomenclature spec 06).
        started_at: Passage en ``running`` (UTC aware, nullable — une
            exécution ``skipped`` n'a jamais démarré).
        finished_at: Clôture ``success``/``failed``/``skipped``.
        duration_seconds: Durée calculée à la clôture (secondes
            fractionnaires — le moteur produit ``total_seconds()``).
        error: Message assaini/tronqué (``sanitize_error``, rules 40) —
            jamais de stack brute ni de paramètre potentiellement
            sensible.
        logs: Journal ligne à ligne ``[{"timestamp": ISO 8601 UTC,
            "message": str}]`` sérialisé JSON (spec 06 : stockage UTC).
        created_at: Création de la ligne (passage ``queued``).
    """

    __tablename__ = "scheduled_task_executions"
    __table_args__ = (
        Index("idx_scheduled_exec_task", "task_id"),
        Index("idx_scheduled_exec_status", "status"),
        Index("idx_scheduled_exec_started", "started_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("scheduled_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="queued")
    triggered_by: Mapped[str] = mapped_column(String(10), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )

    # Relation de consultation (lazy="selectin" — pattern ScheduledTask).
    # Pas de cascade ORM : la suppression en cascade est portée par la FK
    # SQL ``ON DELETE CASCADE`` (la base est source de vérité, testée en
    # intégration avec PRAGMA foreign_keys=ON sous SQLite).
    task: Mapped["ScheduledTask"] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<ScheduledTaskExecution(id={self.id}, task_id={self.task_id}, "
            f"status={self.status}, triggered_by={self.triggered_by})>"
        )
