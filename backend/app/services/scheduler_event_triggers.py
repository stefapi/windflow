"""Triggers événement du scheduler — abonnement EventBus (STORY-160.3, tâche 6).

Composant d'abonnement qui déclenche les définitions
``trigger_type="event"`` depuis le [bus d'événements](../core/events.py)
et **délègue l'exécution au chemin moteur** de STORY-160.2
([`scheduler_engine.py`](scheduler_engine.py)) : tâche asyncio dédiée,
verrou anti-chevauchement, timeout, ``ExecutionStore``, ``record_run``,
politique d'erreur — **jamais d'exécution inline dans la callback du
bus** (un handler lent/erreur ne bloque ni le bus ni les autres
handlers).

Mécanique :

1. ``start()`` abonne une callback unique à **tous** les
   :class:`EventType` (enum legacy — double nomenclature documentée :
   STORY-162 harmonisera, risque §7.3 de l'epic) ; ``stop()`` désabonne ;
2. la callback résout les définitions actives ``trigger_type="event"``
   dont ``event_name`` correspond à l'événement émis ;
3. pour chaque définition : **relecture défensive** (existence +
   ``enabled`` relus en base — une tâche désactivée/supprimée entre
   l'émission et le déclenchement n'est jamais exécutée), **fusion des
   paramètres** (définition + données de l'événement projetées sur les
   champs du schéma de l'action — jamais de payload brut injecté),
   **re-validation** par le schéma Pydantic de l'action, puis
   délégation au chemin moteur (``_execute``) dans une tâche dédiée
   sous verrou anti-chevauchement.

Divergences tracées (notes d'implémentation de la story 160.3) :

- ~~le moteur (160.2) code ``triggered_by="schedule"`` dans ``_execute``~~
  **Résolue par STORY-161** : ``_execute`` accepte un paramètre additif
  ``triggered_by`` (défaut ``schedule`` — comportement inchangé) et ce
  composant passe désormais ``triggered_by="event"`` à la délégation ;
- ``_trigger`` du moteur re-snapshotterait les paramètres **depuis la
  base**, ce qui perdrait la fusion définition+payload : ce composant
  reproduit donc le préambule défensif de ``_trigger`` (relecture +
  verrou, ~15 lignes) puis délègue à ``_execute`` — l'exécution elle-même
  reste 100 % celle du moteur ;
- la fusion projette le payload sur les **champs déclarés** du schéma
  de l'action (``extra="forbid"`` — les clés étrangères au schéma sont
  ignorées, jamais injectées) et pose l'origine
  ``event_type=<nom canonique>`` lorsque le schéma de l'action expose
  ce champ (ex. ``notification.send``).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.events import (
    LEGACY_EVENT_ALIASES,
    Event,
    EventType,
    get_event_bus,
    resolve_event_name,
)
from ..models.scheduled_task import ScheduledTask
from .action_registry import get_action, validate_params
from .scheduler_engine import SchedulerEngine, _snapshot, _TaskSnapshot
from .scheduler_execution_store import TRIGGERED_BY_EVENT
from .scheduler_service import SchedulerService

logger = logging.getLogger(__name__)


def _aliases_resolving_to(canonical: str) -> set[str]:
    """Alias legacy dont la résolution mène à ``canonical`` (STORY-162)."""
    return {
        alias for alias, target in LEGACY_EVENT_ALIASES.items() if target == canonical
    }


class SchedulerEventTriggers:
    """Abonnement EventBus → exécution des définitions trigger événement.

    Args:
        engine: Moteur scheduler (STORY-160.2) — son chemin d'exécution
            (``_execute`` : tâche dédiée, verrou, timeout, store,
            ``record_run``, politique d'erreur) est le **seul** chemin
            d'exécution ; ce composant ne fait jamais de travail métier.
        bus: Bus d'événements (défaut : singleton global
            ``get_event_bus()`` — même instance que les émetteurs).
        session_factory: Factory de sessions async (défaut :
            ``AsyncSessionLocal``) ; session fraîche par événement,
            pattern des boucles lifespan existantes.
    """

    def __init__(
        self,
        engine: SchedulerEngine,
        *,
        bus: Any = None,
        session_factory: Optional[Any] = None,
    ) -> None:
        from ..database import AsyncSessionLocal

        self._engine = engine
        self._bus = bus if bus is not None else get_event_bus()
        self._session_factory = session_factory or AsyncSessionLocal
        self._subscribed = False

    # ------------------------------------------------------------------
    # Cycle de vie (lifespan)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Abonne la callback à tous les ``EventType`` (idempotent)."""
        if self._subscribed:
            return
        for event_type in EventType:
            self._bus.subscribe(event_type, self._on_event)
        self._subscribed = True
        logger.info(
            "Scheduler event triggers : abonné à %d type(s) d'événement",
            len(EventType),
        )

    def stop(self) -> None:
        """Désabonne la callback (shutdown propre avec le moteur)."""
        if not self._subscribed:
            return
        for event_type in EventType:
            try:
                self._bus.unsubscribe(event_type, self._on_event)
            except ValueError:  # déjà désabonné — défense
                pass
        self._subscribed = False
        logger.info("Scheduler event triggers : désabonné du bus")

    # ------------------------------------------------------------------
    # Callback du bus — résolution seulement, jamais d'exécution inline
    # ------------------------------------------------------------------

    async def _on_event(self, event: Event) -> None:
        """Callback EventBus : résout les définitions et délègue au moteur.

        Ne lève jamais (le bus ignore déjà les erreurs de handlers, on
        évite quand même le bruit de log) — une erreur de résolution
        n'affecte ni le bus ni les autres abonnés.
        """
        try:
            await self._dispatch(event)
        except Exception:
            logger.exception(
                "Scheduler event triggers : erreur de traitement de " "%s (ignorée)",
                event.event_type.value,
            )

    async def _dispatch(self, event: Event) -> None:
        """Résout les définitions actives correspondant à l'événement.

        STORY-162 (T9) — défense en profondeur bidirectionnelle : on
        matche le canonique émis **et** tout alias legacy qui lui
        correspond (une ligne encore stockée sous ``deployment.completed``
        reste déclenchée par ``deployment.succeeded`` même si la data
        migration n'est pas encore appliquée ; réciproquement un émetteur
        legacy serait rapproché d'une définition canonique).
        """
        canonical = resolve_event_name(event.event_type.value)
        names = {canonical} | _aliases_resolving_to(canonical)
        tasks: list[ScheduledTask] = []
        async with self._session_factory() as session:
            for name in names:
                tasks.extend(await self._enabled_event_tasks(session, name))
        if not tasks:
            return  # événement sans définition → no-op
        seen: set[str] = set()
        for task in tasks:
            if task.id not in seen:  # même ligne via canonique + alias
                seen.add(task.id)
                await self._dispatch_one(task.id, event)

    async def _enabled_event_tasks(
        self, session: AsyncSession, event_name: str
    ) -> list[ScheduledTask]:
        """Définitions actives ``trigger_type="event"`` pour l'événement."""
        result = await session.execute(
            select(ScheduledTask).where(
                ScheduledTask.trigger_type == "event",
                ScheduledTask.event_name == event_name,
                ScheduledTask.enabled == True,  # noqa: E712 — SQL
            )
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Déclenchement — préambule défensif puis chemin moteur
    # ------------------------------------------------------------------

    async def _dispatch_one(self, task_id: str, event: Event) -> None:
        """Déclenche une définition via le chemin moteur (jamais inline).

        Préambule (miroir défensif de ``_trigger``, moteur 160.2) :
        relecture fraîche de la définition (existence + ``enabled``) puis
        verrou anti-chevauchement ; l'exécution elle-même est intégralement
        celle du moteur (``_execute`` : store, timeout, retries, politique
        d'erreur, ``record_run``) dans une tâche asyncio dédiée.
        """
        async with self._session_factory() as session:
            fresh = await SchedulerService(session).get_task(task_id)
        if fresh is None or not fresh.enabled:
            logger.debug(
                "Scheduler event triggers : tâche %s disparue/désactivée "
                "avant déclenchement — ignorée",
                task_id,
            )
            return
        merged = self._merge_params(fresh, event)
        if merged is None:
            return  # payload invalide → pas d'exécution (déjà journalisé)
        if task_id in self._engine._running:
            await self._engine.store.mark_skipped(
                task_id,
                "overlap : l'exécution précédente est toujours en cours "
                "(trigger événement)",
            )
            logger.info(
                "Scheduler event triggers : tâche %s skipped — " "chevauchement",
                task_id,
            )
            return
        snapshot = _merge_snapshot(_snapshot(fresh), merged)
        self._engine._running.add(task_id)
        # STORY-161 : origine explicite « event » (paramètre additif du
        # chemin moteur — la nomenclature spec 06 est posée par l'impl DB).
        task = asyncio.create_task(
            self._engine._execute(snapshot, triggered_by=TRIGGERED_BY_EVENT)
        )
        self._engine._inflight.add(task)
        task.add_done_callback(self._engine._inflight.discard)

    # ------------------------------------------------------------------
    # Fusion & validation des paramètres
    # ------------------------------------------------------------------

    def _merge_params(
        self, task: ScheduledTask, event: Event
    ) -> Optional[dict[str, Any]]:
        """Fusionne définition + données d'événement, puis re-valide.

        Projection stricte : seuls les champs **déclarés** par le schéma
        de l'action peuvent être alimentés par le payload (les clés
        étrangères sont ignorées — ``extra="forbid"``, jamais de payload
        brut injecté) ; l'origine ``event_type`` est posée lorsque le
        schéma l'expose. La fusion est re-validée par le schéma :
        invalide → ``None`` (pas d'exécution, warning sans données
        sensibles).
        """
        try:
            definition = get_action(task.action)
        except Exception:
            # Action inconnue : on laisse passer les paramètres non
            # fusionnés — l'exécution est déléguée au chemin moteur qui
            # échouera **explicitement** (``_attempt_once`` →
            # ``get_action`` → erreur « Unknown scheduler action »),
            # matérialisée ``failed`` dans l'ExecutionStore (AC).
            logger.warning(
                "Scheduler event triggers : action inconnue %r pour la "
                "tâche %s — déléguée au moteur (échec explicite)",
                task.action,
                task.id,
            )
            return dict(task.parameters or {})
        schema_fields = set(definition.params_schema.model_fields)
        merged = dict(task.parameters or {})
        payload = event.payload or {}
        for field in schema_fields & set(payload):
            merged[field] = payload[field]
        if "event_type" in schema_fields:
            merged.setdefault("event_type", event.event_type.value)
        try:
            return validate_params(task.action, merged)
        except Exception:
            logger.warning(
                "Scheduler event triggers : paramètres fusionnés "
                "invalides pour la tâche %s (action=%s) — exécution "
                "annulée",
                task.id,
                task.action,
            )
            return None


def _merge_snapshot(base: _TaskSnapshot, parameters: dict[str, Any]) -> _TaskSnapshot:
    """Retourne une copie du snapshot avec les paramètres fusionnés."""
    from dataclasses import replace

    return replace(base, parameters=parameters)


__all__ = ["SchedulerEventTriggers"]
