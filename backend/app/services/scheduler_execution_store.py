"""Contrat ``ExecutionStore`` — persistance des exécutions scheduler (160.2/161).

Le moteur ([`services/scheduler_engine.py`](scheduler_engine.py)) est isolé de
la persistance par cette interface : l'implémentation mémoire
(:class:`InMemoryExecutionStore`, STORY-160.2) sert à l'isolation des tests
du moteur ; l'implémentation base de données
(:class:`DatabaseExecutionStore`, STORY-161) persiste le cycle de vie complet
dans la table ``scheduled_task_executions`` (spec 06) sur **cette même
interface** — couplage par interface uniquement, le moteur n'est pas modifié
dans son comportement.

Statuts d'exécution (spec 06 § Entités d'automatisation) :
``queued`` → ``running`` → ``success`` | ``failed`` ; ``skipped`` (verrou
anti-chevauchement / annulation défensive) — ``triggered_by`` trace l'origine
(``schedule`` | ``retry`` | ``manual`` pour le contrat moteur ; la
nomenclature spec 06 ``cron`` | ``event`` | ``manual`` est posée en base, la
traduction ``schedule`` → ``cron`` est faite au point unique
``DatabaseExecutionStore.mark_queued``).

Sécurité (rules 40) : les messages d'erreur transitant vers la persistance
sont **assainis/tronqués** (:func:`sanitize_error`) — jamais de stack brute ni
de paramètre potentiellement sensible.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# --- Statuts (spec 06 § Entités d'automatisation) ----------------------------
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

# Origines d'exécution (triggered_by) — contrat moteur (160.2).
TRIGGERED_BY_SCHEDULE = "schedule"
TRIGGERED_BY_RETRY = "retry"
# STORY-161 : déclenchements événement (160.3 → chemin moteur) et manuel
# (``POST /schedules/{task_id}/run``).
TRIGGERED_BY_EVENT = "event"
TRIGGERED_BY_MANUAL = "manual"

# Nomenclature spec 06 en base (``cron|event|manual``) : traduction au point
# unique qu'est l'impl DB — l'impl mémoire conserve les valeurs du contrat
# (tests 160.2 intacts). ``retry`` ne crée pas de ligne dédiée (les
# retentatives sont des lignes de journal de la même exécution).
_TRIGGERED_BY_DB_MAP: dict[str, str] = {
    TRIGGERED_BY_SCHEDULE: "cron",
    TRIGGERED_BY_EVENT: "event",
    TRIGGERED_BY_MANUAL: "manual",
}

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


class DatabaseExecutionStore(ExecutionStore):
    """Implémentation DB du contrat (STORY-161 — table spec 06).

    Branche le moteur sur ``scheduled_task_executions`` sans modification de
    son comportement (couplage par interface) : session fraîche **par
    opération** via une factory injectable (défaut ``AsyncSessionLocal``,
    pattern des boucles lifespan), horloge injectable pour des tests par
    time travel.

    Spécificités (décisions d'analyse STORY-161) :

    - ``triggered_by`` : traduction ``schedule`` → ``cron`` au point unique
      :meth:`mark_queued` (nomenclature spec 06 en base) ;
    - :meth:`append_log` est **best-effort** : un échec d'écriture d'une
      ligne de journal n'est jamais propagé (try/except + ``logger.error``,
      seule la ligne est perdue — AC 3) ; les transitions ``mark_*``
      propagent leurs erreurs (le moteur les convertit en échec propre) ;
    - :meth:`purge_expired` implémente la rétention (AC 4) sur
      ``COALESCE(started_at, created_at)`` — les lignes sans démarrage
      (``skipped``) purgent sur leur création ; **jamais** ``audit_logs``
      (table distincte, gouvernée séparément).

    Args:
        session_factory: Factory de sessions async (défaut :
            ``AsyncSessionLocal``) — session fraîche par opération.
        clock: Horloge injectable retournant un datetime **aware UTC**.
    """

    def __init__(
        self,
        session_factory: Optional[Callable[..., Any]] = None,
        *,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        from ..database import AsyncSessionLocal

        self._session_factory = session_factory or AsyncSessionLocal
        self._clock: Callable[[], datetime] = clock or (
            lambda: datetime.now(timezone.utc)
        )

    # --- Helpers -------------------------------------------------------------

    @staticmethod
    def _to_db_triggered_by(triggered_by: str) -> str:
        """Traduit l'origine du contrat moteur vers la nomenclature spec 06."""
        return _TRIGGERED_BY_DB_MAP.get(triggered_by, triggered_by)

    def _log_entry(self, message: str) -> dict[str, str]:
        """Construit une ligne de journal sérialisable (ISO 8601 UTC)."""
        return {"timestamp": self._clock().isoformat(), "message": message}

    @staticmethod
    def _decode_logs(raw: Optional[str]) -> list[dict[str, str]]:
        """Décode la colonne ``logs`` (JSON) — tolère vide/corrompu ([])."""
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []

    # --- Contrat -------------------------------------------------------------

    async def mark_queued(self, task_id: str, triggered_by: str = "schedule") -> str:
        """Crée la ligne ``queued`` (mapping ``schedule`` → ``cron``)."""
        from ..models.scheduled_task_execution import ScheduledTaskExecution

        execution_id = str(uuid4())
        async with self._session_factory() as session:
            session.add(
                ScheduledTaskExecution(
                    id=execution_id,
                    task_id=task_id,
                    status=STATUS_QUEUED,
                    triggered_by=self._to_db_triggered_by(triggered_by),
                    created_at=self._clock(),
                    logs=json.dumps(
                        [self._log_entry(f"queued (triggered_by={triggered_by})")],
                        ensure_ascii=False,
                    ),
                )
            )
            await session.commit()
        return execution_id

    async def mark_running(self, execution_id: str) -> None:
        """Passe la ligne en ``running`` (horodatage de démarrage)."""
        from ..models.scheduled_task_execution import ScheduledTaskExecution

        async with self._session_factory() as session:
            execution = await session.get(ScheduledTaskExecution, execution_id)
            if execution is None:
                return
            execution.status = STATUS_RUNNING
            execution.started_at = self._clock()
            await session.commit()

    async def mark_success(self, execution_id: str, duration_seconds: float) -> None:
        """Clôture la ligne en ``success`` (durée + horodatage de fin)."""
        from ..models.scheduled_task_execution import ScheduledTaskExecution

        async with self._session_factory() as session:
            execution = await session.get(ScheduledTaskExecution, execution_id)
            if execution is None:
                return
            execution.status = STATUS_SUCCESS
            execution.duration_seconds = duration_seconds
            execution.finished_at = self._clock()
            await session.commit()

    async def mark_failed(self, execution_id: str, error: str) -> None:
        """Clôture la ligne en ``failed`` avec l'erreur assainie (rules 40)."""
        from ..models.scheduled_task_execution import ScheduledTaskExecution

        async with self._session_factory() as session:
            execution = await session.get(ScheduledTaskExecution, execution_id)
            if execution is None:
                return
            execution.status = STATUS_FAILED
            execution.error = sanitize_error(error, limit=_MAX_ERROR_LENGTH)
            execution.finished_at = self._clock()
            await session.commit()

    async def mark_skipped(self, task_id: str, reason: str) -> None:
        """Trace un ``skipped`` direct (verrou) avec la raison assainie."""
        from ..models.scheduled_task_execution import ScheduledTaskExecution

        async with self._session_factory() as session:
            session.add(
                ScheduledTaskExecution(
                    id=str(uuid4()),
                    task_id=task_id,
                    status=STATUS_SKIPPED,
                    triggered_by=self._to_db_triggered_by(TRIGGERED_BY_SCHEDULE),
                    error=sanitize_error(reason, limit=_MAX_ERROR_LENGTH),
                    created_at=self._clock(),
                    finished_at=self._clock(),
                    logs=json.dumps([self._log_entry("skipped")], ensure_ascii=False),
                )
            )
            await session.commit()

    async def append_log(self, execution_id: str, line: str) -> None:
        """Ajoute une ligne horodatée au journal JSON — **best-effort**.

        AC 3 / décision d'analyse : un échec d'écriture n'est **jamais
        propagé** (seule la ligne de journal est perdue, avec trace
        ``logger.error``) — le statut de l'exécution reste intact.
        """
        from ..models.scheduled_task_execution import ScheduledTaskExecution

        try:
            async with self._session_factory() as session:
                execution = await session.get(ScheduledTaskExecution, execution_id)
                if execution is None:
                    return
                entries = self._decode_logs(execution.logs)
                entries.append(self._log_entry(line))
                execution.logs = json.dumps(entries, ensure_ascii=False)
                await session.commit()
        except Exception:
            logger.error(
                "DatabaseExecutionStore : échec d'écriture de journal pour "
                "l'exécution %s (ligne perdue, exécution intacte)",
                execution_id,
                exc_info=True,
            )

    async def recover_orphans(self) -> int:
        """Marque les ``queued``/``running`` orphelins en ``failed`` (spec 06).

        Sémantique identique à l'impl mémoire : au redémarrage du scheduler,
        toute exécution restée ``queued``/``running`` est close ``failed``
        avec :data:`ORPHAN_REASON` (libellé contractualisé par les tests
        160.2). Retourne le nombre de lignes récupérées.
        """
        from sqlalchemy import update

        from ..models.scheduled_task_execution import ScheduledTaskExecution

        async with self._session_factory() as session:
            result = await session.execute(
                update(ScheduledTaskExecution)
                .where(
                    ScheduledTaskExecution.status.in_((STATUS_QUEUED, STATUS_RUNNING))
                )
                .values(
                    status=STATUS_FAILED,
                    error=sanitize_error(ORPHAN_REASON, limit=_MAX_ERROR_LENGTH),
                    finished_at=self._clock(),
                )
            )
            await session.commit()
            # rowcount n'existe que sur CursorResult (UPDATE/DELETE) —
            # accès défensif pour mypy (Result nu n'expose pas l'attribut).
            recovered = int(getattr(result, "rowcount", 0) or 0)
        if recovered:
            logger.info(
                "DatabaseExecutionStore : %d exécution(s) orpheline(s) "
                "récupérée(s) (queued/running → failed)",
                recovered,
            )
        return recovered

    # --- Rétention (AC 4 — tâche 7) -------------------------------------------

    async def purge_expired(self, retention_days: int) -> int:
        """Purge les exécutions au-delà de la rétention (jamais l'audit).

        Seuil sur ``COALESCE(started_at, created_at)`` : les lignes sans
        démarrage (``skipped``) purgent sur leur date de création (décision
        d'analyse 6). La purge s'applique **uniformément** à toutes les
        lignes (« le job purge ses propres traces » — pas de ligne d'exécution
        dédiée au job système, divergence documentée).

        Args:
            retention_days: Rétention en jours (≥ 1 — ``None`` est géré par
                l'appelant : boucle lifespan non démarrée).

        Returns:
            Le nombre de lignes supprimées.
        """
        from sqlalchemy import delete, func

        from ..models.scheduled_task_execution import ScheduledTaskExecution

        cutoff = self._clock() - timedelta(days=retention_days)
        async with self._session_factory() as session:
            result = await session.execute(
                delete(ScheduledTaskExecution).where(
                    func.coalesce(
                        ScheduledTaskExecution.started_at,
                        ScheduledTaskExecution.created_at,
                    )
                    < cutoff
                )
            )
            await session.commit()
            # rowcount : accès défensif (CursorResult uniquement — mypy).
            return int(getattr(result, "rowcount", 0) or 0)
