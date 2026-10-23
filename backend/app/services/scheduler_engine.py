"""Moteur scheduler asyncio — exécution réelle des tâches planifiées (STORY-160.2).

Boucle lifespan (4ᵉ tâche de fond, arbitrage F1 : runtime asyncio dans le
processus API) qui évalue les expressions cron des définitions
``scheduled_tasks`` (spec 17) et exécute leurs actions via le
[registre canonique](action_registry.py) de STORY-160.1.

Garanties (spec 17 § Exécutions / spec 06 § Entités d'automatisation) :

- **Tick minute** : granularité cron = minute → tick configurable
  (~30 s par défaut) ; **relecture défensive** à chaque échéance (existence +
  ``enabled`` relus en base) — une tâche désactivée ou supprimée entre deux
  ticks n'est jamais exécutée ;
- **Fuseaux IANA** : ``task.timezone`` → ``settings.scheduler_default_timezone``
  → UTC ; évaluation croniter sur l'horloge locale murale du fuseau (le
  croniter vendored supporte les datetimes *aware*) ; **réinscription à
  chaud** : tout changement de cron/fuseau est détecté au tick suivant par
  empreinte (fingerprint) et réinitialisé sans déclenchement surprise ;
- **Verrou anti-chevauchement** (en mémoire, mono-processus) : une seule
  exécution à la fois par tâche — un déclenchement qui chevauche est tracé
  ``skipped`` (jamais empilé) ; chaque exécution tourne dans une **tâche
  asyncio dédiée** (jamais inline dans le tick) ;
- **Timeout** : ``asyncio.wait_for`` par tentative (défaut 10 min) — au-delà
  l'exécution est ``failed`` mais **la boucle survit** ;
- **Politique d'erreur** : ``ignore`` | ``retry`` (retentatives avec backoff,
  défaut 3) | ``disable`` (définition passée ``enabled=false`` + événement
  système) ; chaque exécution est reflétée sur la définition via
  ``SchedulerService.record_run()`` ;
- **Orphelins** : au démarrage du moteur, ``ExecutionStore.recover_orphans()``
  marque toute exécution ``queued``/``running`` en ``failed`` (pattern
  ``recover_pending_deployments``) ;
- **Observabilité** : logs structurés (task_id/action/statut/durée) — jamais
  les ``parameters`` bruts (rules 40) ; événements système pour échecs
  répétés (seuil 3 consécutifs — matérialisation minimale, alerte renvoyée
  STORY-161/P2-15).

⚠ **Limite multi-workers** : le verrou anti-chevauchement et le suivi des
échéances vivent en mémoire process-local — avec ``--workers > 1`` chaque
worker aurait sa propre boucle (exécutions dupliquées possibles). Le
déploiement supporté est **single-worker** (défaut, arbitrage F1).

Horloge **injectable** (``clock``) : tous les tests se font par time travel /
monkeypatch — jamais de ``time.sleep`` réel ni ``datetime.now()`` en dur.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional, TypeVar
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..config import Settings
from ..core.events import Event, EventType, publish_event
from ..core.exceptions import WindFlowException
from ..helper.croniter import CroniterBadCronError, croniter
from ..models.scheduled_task import ScheduledTask
from .action_registry import get_action, validate_params
from .scheduler_execution_store import (
    ORPHAN_REASON,
    TRIGGERED_BY_MANUAL,
    TRIGGERED_BY_SCHEDULE,
    ExecutionStore,
    InMemoryExecutionStore,
    sanitize_error,
)
from .scheduler_service import SchedulerService

logger = logging.getLogger(__name__)

# Type de l'horloge injectable : retourne un datetime aware UTC.
Clock = Callable[[], datetime]

# Contrat du handler d'action (branché par STORY-160.3) : reçoit les
# paramètres **validés** (model_dump du params_schema de l'action) et retourne
# un awaitable.
ActionHandler = Callable[[dict], Awaitable[Any]]

# Seuil d'échecs consécutifs déclenchant l'événement système (alerte
# « 3 échecs » — matérialisation minimale, renvoi STORY-161/P2-15).
_CONSECUTIVE_FAILURES_ALERT = 3

# Bornage du backoff retry (secondes) — pas de tempête de retentatives.
_RETRY_BACKOFF_MAX_SECONDS = 30.0

T = TypeVar("T")


class SchedulerEngineError(WindFlowException):
    """Erreur d'exécution du moteur scheduler (interne — jamais HTTP).

    Hérite de :class:`WindFlowException` (rules 30) ; levée pour les échecs
    de dispatch explicites (action inconnue, stub non implémenté, handler
    absent) — toujours interceptée par le moteur et convertie en exécution
    ``failed`` propre.
    """


@dataclass(frozen=True)
class _TaskSnapshot:
    """Copie scalaire d'une définition lue en base (défensive).

    Le moteur ne conserve jamais d'instance ORM détachée de sa session : le
    snapshot est pris à la lecture (tick / relecture défensive) et consommé
    par la tâche d'exécution dédiée.
    """

    task_id: str
    name: str
    action: str
    cron_expression: str
    timezone: Optional[str]
    error_policy: str
    parameters: dict
    enabled: bool


def _snapshot(task: ScheduledTask) -> _TaskSnapshot:
    """Construit un snapshot scalaire d'une définition ORM."""
    return _TaskSnapshot(
        task_id=task.id,
        name=task.name,
        action=task.action,
        cron_expression=task.cron_expression,
        timezone=task.timezone,
        error_policy=task.error_policy,
        parameters=dict(task.parameters or {}),
        enabled=bool(task.enabled),
    )


class SchedulerEngine:
    """Moteur d'exécution des tâches planifiées (boucle asyncio unique).

    Args:
        settings: Settings applicatifs (défaut : instance globale). Les
            tests injectent une instance dédiée (time travel sans ``.env``).
        store: Contrat :class:`ExecutionStore` (défaut : implémentation
            mémoire pré-STORY-161).
        clock: Horloge injectable retournant un datetime **aware UTC** —
            seul point de lecture du temps du moteur (time travel tests).
        session_factory: Factory de sessions async (défaut :
            ``AsyncSessionLocal``) ; session fraîche par itération, pattern
            des boucles lifespan existantes.
        retry_backoff_base: Base (secondes) du backoff exponentiel des
            retentatives (défaut 1 s ; tests : 0 pour être instantané).
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        *,
        store: Optional[ExecutionStore] = None,
        clock: Optional[Clock] = None,
        session_factory: Optional[Callable[..., Any]] = None,
        retry_backoff_base: float = 1.0,
    ) -> None:
        from ..config import settings as global_settings
        from ..database import AsyncSessionLocal

        self._settings = settings or global_settings
        self.store: ExecutionStore = store or InMemoryExecutionStore()
        self._clock: Clock = clock or (lambda: datetime.now(timezone.utc))
        self._session_factory = session_factory or AsyncSessionLocal
        self._retry_backoff_base = retry_backoff_base
        # Verrou anti-chevauchement (mono-processus — limite multi-workers
        # documentée en tête de module).
        self._running: set[str] = set()
        self._inflight: set[asyncio.Task[None]] = set()
        # Dernière échéance (timestamp UTC) traitée par tâche + empreinte de
        # définition (cron, fuseau) pour la réinscription à chaud.
        self._last_due_ts: dict[str, float] = {}
        self._last_def: dict[str, tuple[str, Optional[str]]] = {}
        # Échecs consécutifs (alerte événement système).
        self._consecutive_failures: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Boucle principale
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Boucle principale du moteur (tâche de fond du lifespan).

        Au démarrage : récupération des orphelins (``queued``/``running`` →
        ``failed``, sémantique spec 06). Puis tick périodique — toute erreur
        de tick est journalisée sans tuer la boucle ; l'annulation (shutdown)
        annule proprement les exécutions en cours.
        """
        recovered = await self.store.recover_orphans()
        if recovered:
            logger.info(
                "Scheduler engine : %d exécution(s) orpheline(s) récupérée(s) "
                "(raison=%s)",
                recovered,
                ORPHAN_REASON,
            )
        logger.info(
            "Scheduler engine démarré (tick=%ds, timeout=%ds, retry_max=%d)",
            self._settings.scheduler_tick_seconds,
            self._settings.scheduler_task_timeout_seconds,
            self._settings.scheduler_retry_backoff,
        )
        try:
            while True:
                try:
                    await self.tick()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # La boucle ne meurt jamais d'un tick défaillant (DB
                    # injoignable, etc.) — journalisé, tick suivant programmé.
                    logger.exception("Scheduler engine : erreur de tick ignorée")
                await asyncio.sleep(self._settings.scheduler_tick_seconds)
        finally:
            await self._cancel_inflight()

    async def _cancel_inflight(self) -> None:
        """Annule et attend les exécutions en cours (shutdown propre)."""
        for task in list(self._inflight):
            task.cancel()
        if self._inflight:
            await asyncio.gather(*self._inflight, return_exceptions=True)
        self._running.clear()

    async def wait_for_executions(self) -> None:
        """Attend la fin des exécutions en cours (utile aux tests)."""
        if self._inflight:
            await asyncio.gather(*list(self._inflight), return_exceptions=True)

    # ------------------------------------------------------------------
    # Déclenchement manuel (STORY-161 — additif)
    # ------------------------------------------------------------------

    async def run_task_now(self, task_id: str) -> str:
        """Déclenche l'exécution immédiate d'une tâche (``POST /run``).

        Symétrique du chemin cron mais **sans attendre la fin** :
        relecture défensive (existence + ``enabled``), verrou
        anti-chevauchement (chevauchement → ligne ``skipped`` tracée +
        :class:`ConflictError`), puis exécution dans une tâche asyncio
        dédiée ``triggered_by="manual"`` (contrat moteur — l'impl DB
        persiste la nomenclature spec 06 telle quelle).

        Args:
            task_id: Identifiant de la définition ``scheduled_tasks``.

        Returns:
            L'identifiant de la ligne d'exécution ``queued`` créée dans
            l':class:`ExecutionStore` (réponse 202 fire-and-forget).

        Raises:
            NotFoundError: Définition inconnue ou désactivée (erreur
                explicite, **aucune** ligne d'exécution créée).
            ConflictError: Une exécution de la même tâche est déjà en
                cours (le saut est tracé ``skipped`` dans le store).
        """
        from ..core.exceptions import ConflictError, NotFoundError

        async with self._session_factory() as session:
            fresh = await SchedulerService(session).get_task(task_id)
        if fresh is None or not fresh.enabled:
            raise NotFoundError(f"Tâche planifiée inconnue ou désactivée : {task_id}")
        if task_id in self._running:
            await self.store.mark_skipped(
                task_id,
                "overlap : l'exécution précédente est toujours en cours "
                "(déclenchement manuel)",
            )
            logger.info(
                "Scheduler engine : run manuel de %s skipped — chevauchement",
                task_id,
            )
            raise ConflictError(
                "Une exécution de cette tâche est déjà en cours " "(saut tracé skipped)"
            )
        # Ligne queued créée AVANT le lancement : l'identifiant est
        # retourné immédiatement (202) sans attendre l'exécution.
        execution_id = await self.store.mark_queued(task_id, TRIGGERED_BY_MANUAL)
        snapshot = _snapshot(fresh)
        self._running.add(task_id)
        task = asyncio.create_task(self._execute_manual(execution_id, snapshot))
        self._inflight.add(task)
        task.add_done_callback(self._inflight.discard)
        return execution_id

    async def _execute_manual(self, execution_id: str, snapshot: _TaskSnapshot) -> None:
        """Exécute une tâche manuelle sur sa ligne ``queued`` existante.

        Variante de :meth:`_execute` : la ligne ``queued`` a déjà été
        créée par :meth:`run_task_now` (l'API retourne son identifiant en
        202 sans attendre) — l'orchestration reprend à ``running``.
        """
        await self.store.mark_running(execution_id)
        started = self._clock()
        logger.info(
            "Scheduler engine : exécution manuelle démarrée task=%s "
            "action=%s (execution=%s)",
            snapshot.task_id,
            snapshot.action,
            execution_id,
        )
        try:
            await self._attempt_with_retries(snapshot, execution_id)
        except asyncio.CancelledError:
            await self.store.mark_failed(
                execution_id, "annulée — arrêt du scheduler pendant l'exécution"
            )
            logger.info(
                "Scheduler engine : exécution manuelle annulée task=%s (shutdown)",
                snapshot.task_id,
            )
            raise
        except Exception as exc:
            error = sanitize_error(f"{type(exc).__name__}: {exc}")
            await self.store.mark_failed(execution_id, error)
            await self._apply_error_policy(snapshot, error)
            await self._record_run(snapshot.task_id, "failed", error)
            self._note_failure(snapshot)
            logger.warning(
                "Scheduler engine : exécution manuelle échouée task=%s "
                "action=%s policy=%s erreur=%r",
                snapshot.task_id,
                snapshot.action,
                snapshot.error_policy,
                error,
            )
        else:
            duration = (self._clock() - started).total_seconds()
            await self.store.mark_success(execution_id, duration)
            await self._record_run(snapshot.task_id, "success")
            self._consecutive_failures.pop(snapshot.task_id, None)
            logger.info(
                "Scheduler engine : exécution manuelle réussie task=%s "
                "action=%s (%.3fs)",
                snapshot.task_id,
                snapshot.action,
                duration,
            )
        finally:
            self._running.discard(snapshot.task_id)

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------

    async def tick(self) -> int:
        """Évalue les définitions actives et déclenche les échéances dues.

        Relecture complète à chaque tick (« réinscription à chaud » : pas de
        cache à invalider — cron/fuseau modifiés sont détectés par empreinte
        au tick suivant).

        Returns:
            Nombre de déclenchements effectifs (hors ``skipped``).
        """
        async with self._session_factory() as session:
            tasks = await SchedulerService(session).get_enabled_tasks()
        by_id = {t.id: t for t in tasks}
        # Nettoyage défensif : définitions disparues/désactivées depuis le
        # dernier tick (le suivi mémoire ne retient que l'existant).
        for gone_id in set(self._last_due_ts) - set(by_id):
            self._last_due_ts.pop(gone_id, None)
            self._last_def.pop(gone_id, None)
        triggered = 0
        for task in tasks:
            snapshot = _snapshot(task)
            if self._is_due(snapshot):
                triggered += 1 if await self._trigger(snapshot) else 0
        return triggered

    def _resolve_timezone(self, snapshot: _TaskSnapshot) -> Optional[ZoneInfo]:
        """Résout le fuseau d'évaluation : tâche → settings → UTC.

        Retourne ``None`` si la définition est incohérente (fuseau inconnu en
        base — corruption) : la tâche est alors simplement non évaluée ce
        tick, avec un warning (défense en profondeur ; la validation à
        l'écriture est déjà en place — STORY-160.1).
        """
        name = snapshot.timezone or self._settings.scheduler_default_timezone or "UTC"
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            logger.warning(
                "Scheduler engine : fuseau inconnu %r pour la tâche %s — "
                "définition ignorée ce tick",
                name,
                snapshot.task_id,
            )
            return None

    def _is_due(self, snapshot: _TaskSnapshot) -> bool:
        """Détermine si l'échéance cron de la tâche est atteinte (time travel).

        Évalue la **dernière échéance ≤ maintenant** (croniter ``get_prev``
        sur l'horloge locale du fuseau) et la compare à la dernière échéance
        déjà traitée :

        - première vue (ou réinscription après changement de cron/fuseau,
          détecté par empreinte) → initialisation **sans déclenchement** ;
        - échéance plus récente → dû (déclenchement) ;
        - échéance plus ancienne (changement de définition) → réinitialisation
          sans déclenchement.
        """
        tz = self._resolve_timezone(snapshot)
        if tz is None:
            return False
        try:
            now_local = self._clock().astimezone(tz)
            last = croniter(snapshot.cron_expression, start_time=now_local).get_prev(
                datetime
            )
        except (CroniterBadCronError, ValueError):
            logger.warning(
                "Scheduler engine : expression cron invalide %r pour la tâche %s — "
                "définition ignorée ce tick",
                snapshot.cron_expression,
                snapshot.task_id,
            )
            return False
        due_ts = last.timestamp()
        fingerprint = (snapshot.cron_expression, snapshot.timezone)
        previous_ts = self._last_due_ts.get(snapshot.task_id)
        previous_def = self._last_def.get(snapshot.task_id)
        self._last_due_ts[snapshot.task_id] = due_ts
        self._last_def[snapshot.task_id] = fingerprint
        if previous_ts is None or previous_def != fingerprint:
            return False  # première vue / réinscription à chaud : pas de trigger
        return due_ts > previous_ts

    async def _trigger(self, snapshot: _TaskSnapshot) -> bool:
        """Déclenche l'exécution d'une tâche due (relecture défensive + verrou).

        Returns:
            ``True`` si l'exécution a été lancée, ``False`` sinon (définition
            retirée/désactivée entre deux ticks, ou chevauchement → ``skipped``).
        """
        async with self._session_factory() as session:
            fresh = await SchedulerService(session).get_task(snapshot.task_id)
        if fresh is None or not fresh.enabled:
            # Relecture défensive : la définition a changé depuis la lecture
            # du tick — jamais exécutée, suivi réinitialisé.
            self._last_due_ts.pop(snapshot.task_id, None)
            self._last_def.pop(snapshot.task_id, None)
            logger.debug(
                "Scheduler engine : tâche %s disparue/désactivée avant "
                "déclenchement — ignorée",
                snapshot.task_id,
            )
            return False
        if snapshot.task_id in self._running:
            await self.store.mark_skipped(
                snapshot.task_id,
                "overlap : l'exécution précédente est toujours en cours",
            )
            logger.info(
                "Scheduler engine : tâche %s (action=%s) skipped — chevauchement",
                snapshot.task_id,
                snapshot.action,
            )
            return False
        self._running.add(snapshot.task_id)
        task = asyncio.create_task(self._execute(_snapshot(fresh)))
        self._inflight.add(task)
        task.add_done_callback(self._inflight.discard)
        return True

    # ------------------------------------------------------------------
    # Exécution
    # ------------------------------------------------------------------

    async def _execute(
        self, snapshot: _TaskSnapshot, triggered_by: str = TRIGGERED_BY_SCHEDULE
    ) -> None:
        """Exécute une tâche (tâche asyncio dédiée — jamais inline au tick).

        Orchestration : queued → running → success/failed dans le
        :class:`ExecutionStore`, politique d'erreur, ``record_run`` sur la
        définition, événements système. Toute exception est interceptée —
        seules :class:`asyncio.CancelledError` traversent (shutdown propre).

        Args:
            snapshot: Copie scalaire de la définition (relecture défensive).
            triggered_by: Origine de l'exécution (contrat moteur —
                ``schedule`` | ``event`` | ``manual`` ; STORY-161 : la
                divergence 160.3 « origine codée en dur » est levée, le
                paramètre est additif et vaut ``schedule`` par défaut —
                aucun changement de comportement des chemins existants).
        """
        execution_id = await self.store.mark_queued(snapshot.task_id, triggered_by)
        await self.store.mark_running(execution_id)
        started = self._clock()
        logger.info(
            "Scheduler engine : exécution démarrée task=%s action=%s " "(execution=%s)",
            snapshot.task_id,
            snapshot.action,
            execution_id,
        )
        try:
            await self._attempt_with_retries(snapshot, execution_id)
        except asyncio.CancelledError:
            await self.store.mark_failed(
                execution_id, "annulée — arrêt du scheduler pendant l'exécution"
            )
            logger.info(
                "Scheduler engine : exécution annulée task=%s (shutdown)",
                snapshot.task_id,
            )
            raise
        except Exception as exc:
            error = sanitize_error(f"{type(exc).__name__}: {exc}")
            await self.store.mark_failed(execution_id, error)
            await self._apply_error_policy(snapshot, error)
            await self._record_run(snapshot.task_id, "failed", error)
            self._note_failure(snapshot)
            logger.warning(
                "Scheduler engine : exécution échouée task=%s action=%s "
                "policy=%s erreur=%r",
                snapshot.task_id,
                snapshot.action,
                snapshot.error_policy,
                error,
            )
        else:
            duration = (self._clock() - started).total_seconds()
            await self.store.mark_success(execution_id, duration)
            await self._record_run(snapshot.task_id, "success")
            self._consecutive_failures.pop(snapshot.task_id, None)
            logger.info(
                "Scheduler engine : exécution réussie task=%s action=%s " "(%.3fs)",
                snapshot.task_id,
                snapshot.action,
                duration,
            )
        finally:
            self._running.discard(snapshot.task_id)

    async def _attempt_with_retries(
        self, snapshot: _TaskSnapshot, execution_id: str
    ) -> None:
        """Tente l'exécution, avec retentatives bornées si policy=retry.

        Backoff exponentiel borné (base × 2^tentative, plafond 30 s) — chaque
        retentative est tracée dans le journal d'exécution ; le timeout
        s'applique **par tentative** (le verrou reste tenu pendant toute la
        stratégie : une seule exécution à la fois, retentatives incluses).
        """
        max_retries = (
            self._settings.scheduler_retry_backoff
            if snapshot.error_policy == "retry"
            else 0
        )
        for attempt in range(max_retries + 1):
            try:
                await self._attempt_once(snapshot)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if attempt >= max_retries:
                    raise
                delay = min(
                    self._retry_backoff_base * (2**attempt),
                    _RETRY_BACKOFF_MAX_SECONDS,
                )
                await self.store.append_log(
                    execution_id,
                    f"retry {attempt + 1}/{max_retries} dans {delay:.1f}s "
                    f"après échec ({type(exc).__name__})",
                )
                logger.info(
                    "Scheduler engine : retry %d/%d task=%s dans %.1fs",
                    attempt + 1,
                    max_retries,
                    snapshot.task_id,
                    delay,
                )
                await asyncio.sleep(delay)

    async def _attempt_once(self, snapshot: _TaskSnapshot) -> None:
        """Une tentative : dispatch registre → validation params → handler.

        Raises:
            SchedulerEngineError: Action inconnue du registre, stub non
                implémenté (``implemented=False``) ou handler non enregistré
                (STORY-160.3) — échec explicite, jamais de succès silencieux.
            asyncio.TimeoutError: Timeout d'exécution dépassé — l'exécution
                est ``failed`` mais la boucle du moteur survit.
        """
        definition = get_action(snapshot.action)  # action inconnue → explicite
        if not definition.implemented:
            raise SchedulerEngineError(
                f"action {snapshot.action!r} non implémentée (stub explicite "
                "du registre)"
            )
        handler = definition.handler
        if handler is None:
            raise SchedulerEngineError(
                f"aucun handler enregistré pour {snapshot.action!r} "
                "(attendu STORY-160.3)"
            )
        # Défense en profondeur : les paramètres ont été validés à l'écriture
        # (160.1) — revalidés avant toute exécution.
        params = validate_params(snapshot.action, snapshot.parameters)
        timeout = self._settings.scheduler_task_timeout_seconds
        try:
            await asyncio.wait_for(
                self._await_handler(handler, params), timeout=timeout
            )
        except asyncio.TimeoutError as exc:
            raise asyncio.TimeoutError(
                f"timeout d'exécution dépassé ({timeout}s)"
            ) from exc

    @staticmethod
    async def _await_handler(handler: ActionHandler, params: dict) -> None:
        """Invoque le handler avec les paramètres validés (contrat 160.3)."""
        result = handler(params)
        await result

    # ------------------------------------------------------------------
    # Politique d'erreur & traçabilité
    # ------------------------------------------------------------------

    async def _apply_error_policy(self, snapshot: _TaskSnapshot, error: str) -> None:
        """Applique la politique d'erreur de la définition à l'échec.

        - ``ignore`` (défaut) : journalisé uniquement ;
        - ``retry`` : les retentatives ont déjà eu lieu (backoff borné) ;
        - ``disable`` : définition passée ``enabled=false`` + WARNING +
          événement système (jamais de suppression silencieuse).
        """
        if snapshot.error_policy == "disable":
            async with self._session_factory() as session:
                task = await SchedulerService(session).get_task(snapshot.task_id)
                if task is not None and task.enabled:
                    task.enabled = False
                    await session.commit()
            logger.warning(
                "Scheduler engine : tâche %s (action=%s) désactivée par "
                "politique d'erreur après échec — %s",
                snapshot.task_id,
                snapshot.action,
                error,
            )
            await self._publish_event(
                EventType.SYSTEM_WARNING,
                snapshot,
                "scheduled_task.disabled_by_error_policy",
                {"error": error},
            )

    async def _record_run(
        self, task_id: str, status: str, error: Optional[str] = None
    ) -> None:
        """Reflète l'exécution sur la définition (record_run — best effort)."""
        try:
            async with self._session_factory() as session:
                await SchedulerService(session).record_run(task_id, status, error)
        except Exception:
            logger.exception(
                "Scheduler engine : record_run impossible pour %s (statut=%s)",
                task_id,
                status,
            )

    def _note_failure(self, snapshot: _TaskSnapshot) -> None:
        """Comptabilise un échec consécutif ; alerte événement au seuil 3."""
        count = self._consecutive_failures.get(snapshot.task_id, 0) + 1
        self._consecutive_failures[snapshot.task_id] = count
        if count == _CONSECUTIVE_FAILURES_ALERT:
            logger.error(
                "Scheduler engine : %d échecs consécutifs pour la tâche %s "
                "(action=%s) — alerte émise",
                count,
                snapshot.task_id,
                snapshot.action,
            )
            # Fire-and-forget : le seuil est atteint une fois exactement.
            task = asyncio.create_task(
                self._publish_event(
                    EventType.SYSTEM_WARNING,
                    snapshot,
                    "scheduled_task.repeated_failures",
                    {"consecutive_failures": count},
                )
            )
            self._inflight.add(task)
            task.add_done_callback(self._inflight.discard)

    async def _publish_event(
        self,
        event_type: EventType,
        snapshot: _TaskSnapshot,
        reason: str,
        extra_payload: dict[str, Any],
    ) -> None:
        """Publie un événement système (best effort, sans ``parameters``)."""
        payload: dict[str, Any] = {
            "task_id": snapshot.task_id,
            "task_name": snapshot.name,
            "action": snapshot.action,
            "reason": reason,
            **extra_payload,
        }
        try:
            await publish_event(
                Event(
                    event_type=event_type,
                    aggregate_id=_safe_uuid(snapshot.task_id),
                    aggregate_type="scheduled_task",
                    payload=payload,
                )
            )
        except Exception:
            logger.exception(
                "Scheduler engine : émission d'événement impossible (%s)",
                reason,
            )


def _safe_uuid(value: str) -> Optional[UUID]:
    """Convertit un id en UUID (``None`` si non parsable — best effort)."""
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None
