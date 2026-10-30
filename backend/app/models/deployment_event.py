"""Modèle DeploymentEvent — événements de déploiement structurés (STORY-167).

Matérialise le schéma spec 06 § DeploymentEvent (P2-7 — axe A15) : chaque
étape clé du pipeline de déploiement est persistée comme une ligne typée,
horodatée et requêtable, remplaçant l'accumulation de texte non structuré
comme unique source d'historique. La colonne texte ``deployments.logs``
est **conservée** pour le payload brut (double écriture — décision
d'analyse 1) : les consommateurs existants (``GET /deployments/{id}/logs``,
WS ``DEPLOYMENT_LOGS_UPDATE``) ne sont pas impactés.

Domaines fermés (spec 06) :

- ``event_type`` : ``pulling`` | ``deploying`` | ``health_check`` |
  ``success`` | ``error`` | ``rollback`` — stockés en valeurs littérales
  ``String(50)`` (pattern ``ScheduledTaskExecution.status``, pas de
  ``SQLEnum`` : la data migration 1671 écrit des valeurs littérales).
  Divergence documentée : ``success`` (spec 06) ≠ statut métier
  ``running`` — l'event ``success`` marque la transition vers ``RUNNING``
  (même divergence que STORY-162, nomenclature canonique du bus). Les
  sous-étapes ``pulling``/``health_check`` ne sont pas observables dans
  le pipeline actuel (décision 2) : le domaine reste complet pour les
  futurs adapters / gates (STORY-170).
- ``level`` : ``debug`` | ``info`` | ``warning`` | ``error``.

Index (noms spec 06 — requêtes par déploiement et rétention) :
``idx_deploy_events_deployment`` (``deployment_id``),
``idx_deploy_events_created`` (``created_at``).

La suppression d'un déploiement emporte ses événements (FK
``ON DELETE CASCADE`` — la base est source de vérité ; pas de cascade
ORM, pattern ``ScheduledTaskExecution``).

Horodatage : ``created_at`` naïf UTC (``datetime.utcnow``, décision
d'analyse 5) — cohérent avec le modèle ``Deployment`` (SQLite stocke des
naïfs ; une valeur aware lèverait des ``TypeError`` de comparaison).
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .deployment import Deployment


class DeploymentEventType(str, Enum):
    """Types d'événements de déploiement (domaine fermé spec 06).

    Divergence ``success`` ↔ statut métier ``running`` : l'event
    ``success`` marque la transition vers ``RUNNING`` (STORY-162).
    """

    PULLING = "pulling"
    DEPLOYING = "deploying"
    HEALTH_CHECK = "health_check"
    SUCCESS = "success"
    ERROR = "error"
    ROLLBACK = "rollback"


class DeploymentEventLevel(str, Enum):
    """Niveaux de sévérité des événements (domaine fermé spec 06)."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DeploymentEvent(Base):
    """Événement structuré d'un déploiement (spec 06 — STORY-167).

    Écrit par :data:`DeploymentEventStore.append_event` (double écriture
    dans ``DeploymentService.update_status`` — même transaction que le
    changement de statut), la data migration 1671 (logs texte historiques)
    et les futurs gates pre-deploy (STORY-170). Lu par l'endpoint paginé
    ``GET /deployments/{id}/events``.

    Attributes:
        id: Identifiant unique (uuid4 str).
        deployment_id: FK ``deployments.id`` (CASCADE à la suppression).
        event_type: ``pulling`` | ``deploying`` | ``health_check`` |
            ``success`` | ``error`` | ``rollback`` (spec 06).
        level: ``debug`` | ``info`` | ``warning`` | ``error``
            (défaut ``info``, spec 06).
        message: Ligne de journal lisible (payload texte, jamais de
            secret — rules 40).
        data: Données additionnelles non sensibles (identifiants,
            métriques — ``container_id``, ``duration_seconds``,
            ``old_status``/``new_status``…), JSON nullable.
        created_at: Horodatage naïf UTC de l'événement.
    """

    __tablename__ = "deployment_events"
    __table_args__ = (
        Index("idx_deploy_events_deployment", "deployment_id"),
        Index("idx_deploy_events_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    deployment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=DeploymentEventType.DEPLOYING.value
    )
    level: Mapped[str] = mapped_column(
        String(10), nullable=False, default=DeploymentEventLevel.INFO.value
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relation de consultation (lazy="selectin" — pattern
    # ScheduledTaskExecution). Pas de cascade ORM : la suppression en
    # cascade est portée par la FK SQL ``ON DELETE CASCADE`` (la base est
    # source de vérité, testée avec PRAGMA foreign_keys=ON sous SQLite).
    deployment: Mapped["Deployment"] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<DeploymentEvent(id={self.id}, "
            f"deployment_id={self.deployment_id}, "
            f"event_type={self.event_type}, level={self.level})>"
        )
