"""Contrat ``ExecutionStore`` — persistance des exécutions scheduler (STORY-160.2).

Le moteur ([`services/scheduler_engine.py`](scheduler_engine.py)) est isolé de
la persistance par cette interface : à ce stade (pré-STORY-161), seule une
**implémentation mémoire** est livrée — elle sert au fonctionnement du moteur
avant la table ``scheduled_task_executions`` et à l'isolation des tests du
moteur (aucune dépendance à la table posée par 161).

STORY-161 branchera son implémentation DB sur **cette même interface**, sans
modifier le moteur (couplage par interface uniquement — analyse conjointe
160.2/161 recommandée).

Statuts d'exécution (spec 06 § Entités d'automatisation) :
``queued`` → ``running`` → ``success`` | ``failed`` ; ``skipped`` (verrou
anti-chevauchement / annulation défensive) — ``triggered_by`` trace l'origine
(``schedule`` | ``retry`` | ``manual`` — ce dernier porté par STORY-161).

Sécurité (rules 40) : les messages d'erreur transitant vers la persistance
sont **assainis/tronqués** (:func:`sanitize_error`) — jamais de stack brute ni
de paramètre potentiellement sensible.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# --- Statuts (spec 06 § Entités d'automatisation) ----------------------------
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

# Origines d'exécution (triggered_by).
TRIGGERED_BY_SCHEDULE = "schedule"
TRIGGERED_BY_RETRY = "retry"

# Raison exacte de récupération post-redémarrage (spec 06, sémantique des
# orphelins — modèle direct ``recover_pending_deployments``). Le libellé est
# contractualisé par les tests (AC 3 de STORY-160.2).
ORPHAN_REASON = "interrompue — le scheduler a été redémarré pendant l'exécution"

# Bornage défensif des messages stockés en mémoire.
_MAX_ERROR_LENGTH = 2000


def sanitize_error(message: Optional[str], *, limit: int = 500) -> str:
    """Assainit et tronque un message d'erreur avant persistance/journal.

    Rules 40 : ``last_error`` doit rester court, sans stack brute ni donnée
    sensible ; un message vide devient ``unknown error`` (jamais de chaîne
    vide ambiguë côté API).

    Args:
        message: Message brut (ex. ``str(exc)``).
        limit: Longueur maximale conservée (défaut 500).

    Returns:
        Le message assaini, éventuellement tronqué avec ellipse.
    """
    text = (message or "").strip()
    if not text:
        return "unknown error"
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text[:_MAX_ERROR_LENGTH]


@dataclass
class ExecutionRecord:
    """Ligne d'exécution en mémoire (miroir de la future table 161).

    Attributes:
        execution_id: Identifiant unique de l'exécution.
        task_id: Identifiant de la définition ``scheduled_tasks``.
        status: ``queued`` | ``running`` | ``success`` | ``failed`` | ``skipped``.
        triggered_by: Origine — ``schedule`` | ``retry`` | ``manual``.
        error: Message d'erreur assaini (échec/skip), sinon ``None``.
        duration_seconds: Durée d'exécution (succès), sinon ``None``.
        created_at: Horodatage de création (queued).
        started_at: Horodatage de passage en ``running``.
        finished_at: Horodatage de clôture (success/failed).
        logs: Journal ligne à ligne horodaté.
    """

    execution_id: str
    task_id: str
    status: str
    triggered_by: str = TRIGGERED_BY_SCHEDULE
    error: Optional[str] = None
    duration_seconds: Optional[float] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    logs: list[tuple[datetime, str]] = field(default_factory=list)


class ExecutionStore(ABC):
    """Contrat de persistance des exécutions scheduler (interface 160.2 ↔ 161).

    Le moteur ne connaît que ce contrat ; l'implémentation DB (STORY-161 :
    table ``scheduled_task_executions``) s'y branchera sans toucher au moteur.
    """

    @abstractmethod
    async def mark_queued(self, task_id: str, triggered_by: str = "schedule") -> str:
        """Crée une ligne d'exécution ``queued`` et retourne son identifiant."""

    @abstractmethod
    async def mark_running(self, execution_id: str) -> None:
        """Passe l'exécution en ``running`` (horodatage de démarrage)."""

    @abstractmethod
    async def mark_success(self, execution_id: str, duration_seconds: float) -> None:
        """Clôture l'exécution en ``success`` avec sa durée."""

    @abstractmethod
    async def mark_failed(self, execution_id: str, error: str) -> None:
        """Clôture l'exécution en ``failed`` avec l'erreur assainie."""

    @abstractmethod
    async def mark_skipped(self, task_id: str, reason: str) -> None:
        """Trace un ``skipped`` (verrou anti-chevauchement, annulation défensive)."""

    @abstractmethod
    async def append_log(self, execution_id: str, line: str) -> None:
        """Ajoute une ligne horodatée au journal de l'exécution."""

    @abstractmethod
    async def recover_orphans(self) -> int:
        """Marque les ``queued``/``running`` orphelins en ``failed`` (redémarrage).

        Sémantique spec 06 : toute exécution restée ``queued``/``running`` au
        démarrage du scheduler est marquée ``failed`` avec la raison
        :data:`ORPHAN_REASON`. Retourne le nombre de lignes récupérées.
        """


class InMemoryExecutionStore(ExecutionStore):
    """Implémentation mémoire du contrat (pré-161 + isolation des tests).

    ``clock`` injectable pour des horodats déterministes en tests.
    """

    def __init__(self, clock: Optional[Callable[[], datetime]] = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._records: list[ExecutionRecord] = []
        self._by_id: dict[str, ExecutionRecord] = {}

    # --- Inspection (tests / observabilité) --------------------------------

    def all_executions(self) -> list[ExecutionRecord]:
        """Retourne une copie ordonnée de toutes les lignes (création)."""
        return list(self._records)

    def executions_for_task(self, task_id: str) -> list[ExecutionRecord]:
        """Retourne les lignes d'exécution d'une définition (ordre création)."""
        return [r for r in self._records if r.task_id == task_id]

    def get(self, execution_id: str) -> Optional[ExecutionRecord]:
        """Retourne une ligne par identifiant (``None`` si inconnue)."""
        return self._by_id.get(execution_id)

    # --- Contrat -------------------------------------------------------------

    def _new_record(
        self, task_id: str, status: str, triggered_by: str, error: Optional[str]
    ) -> ExecutionRecord:
        record = ExecutionRecord(
            execution_id=str(uuid4()),
            task_id=task_id,
            status=status,
            triggered_by=triggered_by,
            error=error,
            created_at=self._clock(),
        )
        self._records.append(record)
        self._by_id[record.execution_id] = record
        return record

    async def mark_queued(self, task_id: str, triggered_by: str = "schedule") -> str:
        record = self._new_record(task_id, STATUS_QUEUED, triggered_by, None)
        record.logs.append((self._clock(), f"queued (triggered_by={triggered_by})"))
        return record.execution_id

    async def mark_running(self, execution_id: str) -> None:
        record = self._by_id.get(execution_id)
        if record is None:
            return
        record.status = STATUS_RUNNING
        record.started_at = self._clock()
        record.logs.append((self._clock(), "running"))

    async def mark_success(self, execution_id: str, duration_seconds: float) -> None:
        record = self._by_id.get(execution_id)
        if record is None:
            return
        record.status = STATUS_SUCCESS
        record.duration_seconds = duration_seconds
        record.finished_at = self._clock()
        record.logs.append((self._clock(), f"success ({duration_seconds:.3f}s)"))

    async def mark_failed(self, execution_id: str, error: str) -> None:
        record = self._by_id.get(execution_id)
        if record is None:
            return
        record.status = STATUS_FAILED
        record.error = sanitize_error(error, limit=_MAX_ERROR_LENGTH)
        record.finished_at = self._clock()
        record.logs.append((self._clock(), "failed"))

    async def mark_skipped(self, task_id: str, reason: str) -> None:
        record = self._new_record(
            task_id, STATUS_SKIPPED, TRIGGERED_BY_SCHEDULE, sanitize_error(reason)
        )
        record.finished_at = self._clock()
        record.logs.append((self._clock(), "skipped"))

    async def append_log(self, execution_id: str, line: str) -> None:
        record = self._by_id.get(execution_id)
        if record is None:
            return
        record.logs.append((self._clock(), line))

    async def recover_orphans(self) -> int:
        recovered = 0
        for record in self._records:
            if record.status in (STATUS_QUEUED, STATUS_RUNNING):
                record.status = STATUS_FAILED
                record.error = sanitize_error(ORPHAN_REASON, limit=_MAX_ERROR_LENGTH)
                record.finished_at = self._clock()
                record.logs.append((self._clock(), f"recovered: {ORPHAN_REASON}"))
                recovered += 1
        if recovered:
            logger.info(
                "ExecutionStore : %d exécution(s) orpheline(s) récupérée(s) "
                "(queued/running → failed)",
                recovered,
            )
        return recovered
