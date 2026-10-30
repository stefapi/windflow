"""Tests des triggers événement scheduler (STORY-160.3, tâche 6) — 100 % mocks.

Vérifie l'AC 2 de la story : l'émission de ``DEPLOYMENT_FAILED`` sur le
bus déclenche la définition ``trigger_type="event"`` correspondante,
exécutée **via le chemin moteur** (tâche dédiée, verrou, timeout —
jamais inline dans la callback) avec les **données de l'événement en
paramètres additionnels** (re-validées par le schéma de l'action).

Aucun Docker/SSH/réseau réel : le handler exécuté est un espion branché
au [registre](app/services/action_registry.py) (pattern moteur 160.2) ;
la base est la base de test migrate-then-seed standard.

Familles : dispatch sur event_name, payload en paramètres additionnels,
relecture défensive (désactivée/supprimée → jamais exécutée), payload
invalide → pas d'exécution, délégation non-bloquante au chemin moteur,
action inconnue → failed explicite, isolation d'échec (AC 3), verrou
anti-chevauchement, cycle de vie start/stop.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import app.services.action_registry as action_registry_module
from app.config import Settings
from app.core.events import Event, EventBus, EventType
from app.models.scheduled_task import ScheduledTask
from app.services.scheduler_engine import SchedulerEngine
from app.services.scheduler_event_triggers import SchedulerEventTriggers
from app.services.scheduler_execution_store import (
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
    InMemoryExecutionStore,
)

# ===========================================================================
# Helpers
# ===========================================================================


class FixedClock:
    """Horloge déterministe (avance à la demande)."""

    def __init__(self) -> None:
        self.now = datetime(2026, 10, 23, 10, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: int) -> None:
        self.now = self.now + timedelta(**kwargs)


def _test_settings(**overrides: object) -> Settings:
    defaults: dict = {
        "scheduler_tick_seconds": 30,
        "scheduler_task_timeout_seconds": 5,
        "scheduler_retry_backoff": 3,
        "scheduler_default_timezone": None,
        "scheduler_default_error_policy": "ignore",
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)  # type: ignore[arg-type]


def _patch_handler(monkeypatch: pytest.MonkeyPatch, action: str, handler):
    """Injecte un handler espion sur une action du registre (restauré)."""
    from dataclasses import replace

    definition = replace(
        action_registry_module.get_action(action),
        handler=handler,
        implemented=True,
    )
    monkeypatch.setitem(action_registry_module._REGISTRY, action, definition)


async def _make_event_task(
    db_session,
    organization_id: str,
    *,
    task_id: str = "event-task-1",
    action: str = "notification.send",
    event_name: str = "deployment.failed",
    parameters: dict | None = None,
    enabled: bool = True,
) -> ScheduledTask:
    """Insère une définition trigger événement directement en base."""
    task = ScheduledTask(
        id=task_id,
        name=f"task {task_id}",
        action=action,
        trigger_type="event",
        event_name=event_name,
        cron_expression="0 * * * *",  # non évalué pour les triggers event
        error_policy="ignore",
        parameters=parameters or {"channel": "webhook", "message": "défaut"},
        enabled=enabled,
        organization_id=organization_id,
    )
    db_session.add(task)
    await db_session.commit()
    return task


def _make_component(
    engine: SchedulerEngine, bus: EventBus, test_session_factory
) -> SchedulerEventTriggers:
    return SchedulerEventTriggers(engine, bus=bus, session_factory=test_session_factory)


async def _emit_failed_event(bus: EventBus, payload: dict | None = None):
    await bus.publish(
        Event(
            event_type=EventType.DEPLOYMENT_FAILED,
            aggregate_id=uuid.uuid4(),
            aggregate_type="deployment",
            payload=payload
            or {
                "deployment_id": "dep-1",
                "message": "Déploiement échoué — image introuvable",
                "new_status": "failed",
            },
        )
    )


# ===========================================================================
# AC 2 — dispatch + payload en paramètres additionnels
# ===========================================================================


async def test_event_triggers_action_with_event_payload(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """DEPLOYMENT_FAILED → la définition correspondante s'exécute avec le
    payload de l'événement en paramètres additionnels."""
    calls: list[dict] = []

    async def spy_handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "notification.send", spy_handler)
    await _make_event_task(db_session, test_organization.id)

    bus = EventBus()
    engine = SchedulerEngine(
        _test_settings(),
        store=InMemoryExecutionStore(),
        clock=FixedClock(),
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )
    component = _make_component(engine, bus, test_session_factory)
    component.start()

    await _emit_failed_event(bus)
    await engine.wait_for_executions()

    assert len(calls) == 1
    assert calls[0]["message"] == "Déploiement échoué — image introuvable"
    assert calls[0]["event_type"] == "deployment.failed"
    component.stop()


async def test_event_triggers_execution_via_engine_path(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """L'exécution est matérialisée par le chemin moteur : ExecutionStore
    + record_run sur la définition (jamais inline)."""
    calls: list[dict] = []

    async def spy_handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "notification.send", spy_handler)
    await _make_event_task(db_session, test_organization.id)

    bus = EventBus()
    store = InMemoryExecutionStore()
    engine = SchedulerEngine(
        _test_settings(),
        store=store,
        clock=FixedClock(),
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )
    component = _make_component(engine, bus, test_session_factory)
    component.start()

    await _emit_failed_event(bus)
    await engine.wait_for_executions()

    records = store.executions_for_task("event-task-1")
    assert len(records) == 1
    assert records[0].status == STATUS_SUCCESS
    from sqlalchemy import select

    result = await db_session.execute(
        select(ScheduledTask)
        .where(ScheduledTask.id == "event-task-1")
        .execution_options(populate_existing=True)
    )
    task = result.scalar_one()
    await db_session.commit()
    assert task.last_status == "success"
    assert task.run_count == 1
    component.stop()


async def test_event_without_matching_definition_is_noop(
    test_session_factory, monkeypatch
):
    """Événement sans définition → aucune exécution, aucune erreur."""
    calls: list[dict] = []

    async def spy_handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "notification.send", spy_handler)

    bus = EventBus()
    store = InMemoryExecutionStore()
    engine = SchedulerEngine(
        _test_settings(),
        store=store,
        clock=FixedClock(),
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )
    component = _make_component(engine, bus, test_session_factory)
    component.start()

    await _emit_failed_event(bus)  # aucune définition en base
    await engine.wait_for_executions()

    assert calls == []
    assert store.all_executions() == []
    component.stop()


# ===========================================================================
# AC 2 — relecture défensive + validation du payload
# ===========================================================================


async def test_disabled_definition_never_executed(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Définition désactivée → jamais exécutée (relecture défensive)."""
    calls: list[dict] = []

    async def spy_handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "notification.send", spy_handler)
    await _make_event_task(db_session, test_organization.id, enabled=False)

    bus = EventBus()
    store = InMemoryExecutionStore()
    engine = SchedulerEngine(
        _test_settings(),
        store=store,
        clock=FixedClock(),
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )
    component = _make_component(engine, bus, test_session_factory)
    component.start()

    await _emit_failed_event(bus)
    await engine.wait_for_executions()

    assert calls == []
    assert store.all_executions() == []
    component.stop()


async def test_deleted_definition_never_executed(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Définition supprimée entre résolution et déclenchement → ignorée."""
    calls: list[dict] = []

    async def spy_handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "notification.send", spy_handler)
    task = await _make_event_task(db_session, test_organization.id)
    await db_session.delete(task)
    await db_session.commit()

    bus = EventBus()
    store = InMemoryExecutionStore()
    engine = SchedulerEngine(
        _test_settings(),
        store=store,
        clock=FixedClock(),
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )
    component = _make_component(engine, bus, test_session_factory)
    component.start()

    await _emit_failed_event(bus)
    await engine.wait_for_executions()

    assert calls == []
    component.stop()


async def test_invalid_payload_rejected_no_execution(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Payload invalide au regard du schéma → pas d'exécution (jamais de
    payload brut non validé injecté)."""
    calls: list[dict] = []

    async def spy_handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "notification.send", spy_handler)
    # message > 2000 caractères → rejeté par NotificationSendParams.
    await _make_event_task(db_session, test_organization.id)

    bus = EventBus()
    store = InMemoryExecutionStore()
    engine = SchedulerEngine(
        _test_settings(),
        store=store,
        clock=FixedClock(),
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )
    component = _make_component(engine, bus, test_session_factory)
    component.start()

    await _emit_failed_event(bus, payload={"message": "x" * 3000})
    await engine.wait_for_executions()

    assert calls == []
    assert store.all_executions() == []
    component.stop()


async def test_payload_extra_keys_not_injected(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Les clés étrangères au schéma sont ignorées (extra="forbid" —
    projection stricte, jamais de payload brut)."""
    calls: list[dict] = []

    async def spy_handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "notification.send", spy_handler)
    await _make_event_task(db_session, test_organization.id)

    bus = EventBus()
    engine = SchedulerEngine(
        _test_settings(),
        store=InMemoryExecutionStore(),
        clock=FixedClock(),
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )
    component = _make_component(engine, bus, test_session_factory)
    component.start()

    await _emit_failed_event(bus, payload={"message": "échec", "password": "leak-me"})
    await engine.wait_for_executions()

    assert len(calls) == 1
    assert "password" not in calls[0]  # clé étrangère au schéma → ignorée
    assert calls[0]["message"] == "échec"
    component.stop()


# ===========================================================================
# AC 2 — jamais inline : la callback ne bloque pas sur un handler lent
# ===========================================================================


async def test_slow_handler_does_not_block_bus_callback(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Un handler lent s'exécute dans une tâche dédiée : la callback du
    bus rend la main immédiatement (assert temporel — jamais inline)."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_handler(params: dict) -> None:
        started.set()
        await release.wait()

    _patch_handler(monkeypatch, "notification.send", slow_handler)
    await _make_event_task(db_session, test_organization.id)

    bus = EventBus()
    engine = SchedulerEngine(
        _test_settings(),
        store=InMemoryExecutionStore(),
        clock=FixedClock(),
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )
    component = _make_component(engine, bus, test_session_factory)
    component.start()

    loop = asyncio.get_running_loop()
    start = loop.time()
    task = loop.create_task(_emit_failed_event(bus))
    await asyncio.wait_for(task, timeout=1.0)  # la callback rend la main…
    elapsed = loop.time() - start
    # …sans attendre le handler (qui bloque sur release) : la callback
    # n'a passé que quelques cycles à scheduler la tâche dédiée.
    assert elapsed < 0.5

    await asyncio.wait_for(started.wait(), timeout=1.0)  # …mais démarre
    release.set()
    await engine.wait_for_executions()
    component.stop()


# ===========================================================================
# AC 3 — isolation d'échec, action inconnue, verrou
# ===========================================================================


async def test_handler_failure_does_not_affect_next_executions(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Un handler qui lève → exécution failed, les suivantes passent
    (isolation par exécution — ni le bus ni les autres tâches impactés)."""
    calls: list[dict] = []
    fail = {"on": True}

    async def flaky_handler(params: dict) -> None:
        calls.append(params)
        if fail["on"]:
            raise RuntimeError("panne contrôlée")

    _patch_handler(monkeypatch, "notification.send", flaky_handler)
    await _make_event_task(db_session, test_organization.id)

    bus = EventBus()
    store = InMemoryExecutionStore()
    engine = SchedulerEngine(
        _test_settings(),
        store=store,
        clock=FixedClock(),
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )
    component = _make_component(engine, bus, test_session_factory)
    component.start()

    await _emit_failed_event(bus)
    await engine.wait_for_executions()
    assert store.executions_for_task("event-task-1")[0].status == STATUS_FAILED

    fail["on"] = False
    await _emit_failed_event(bus, payload={"message": "second essai"})
    await engine.wait_for_executions()
    records = store.executions_for_task("event-task-1")
    assert records[1].status == STATUS_SUCCESS
    assert len(calls) == 2
    component.stop()


async def test_unknown_action_fails_explicitly_end_to_end(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Définition référençant une action absente du registre → exécution
    failed avec erreur explicite (complément AC, bout en bout)."""
    await _make_event_task(
        db_session, test_organization.id, action="legacy.purge_celery"
    )

    bus = EventBus()
    store = InMemoryExecutionStore()
    engine = SchedulerEngine(
        _test_settings(),
        store=store,
        clock=FixedClock(),
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )
    component = _make_component(engine, bus, test_session_factory)
    component.start()

    await _emit_failed_event(bus)
    await engine.wait_for_executions()

    records = store.executions_for_task("event-task-1")
    assert records[0].status == STATUS_FAILED
    assert "Unknown scheduler action" in (records[0].error or "")
    component.stop()


async def test_overlapping_event_trigger_skipped(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Chevauchement : un second déclenchement pendant l'exécution est
    tracé skipped (verrou anti-chevauchement du chemin moteur)."""
    release = asyncio.Event()

    async def blocking_handler(params: dict) -> None:
        await release.wait()

    _patch_handler(monkeypatch, "notification.send", blocking_handler)
    await _make_event_task(db_session, test_organization.id)

    bus = EventBus()
    store = InMemoryExecutionStore()
    engine = SchedulerEngine(
        _test_settings(),
        store=store,
        clock=FixedClock(),
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )
    component = _make_component(engine, bus, test_session_factory)
    component.start()

    await _emit_failed_event(bus)  # 1ʳᵉ exécution (bloquée)
    await asyncio.sleep(0.05)  # laisse la tâche dédiée démarrer
    await _emit_failed_event(bus)  # chevauchante → skipped
    release.set()
    await engine.wait_for_executions()

    statuses = sorted(r.status for r in store.executions_for_task("event-task-1"))
    assert STATUS_SKIPPED in statuses
    component.stop()


# ===========================================================================
# Cycle de vie start/stop
# ===========================================================================


async def test_stop_unsubscribes_from_bus(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Après stop(), plus aucun événement ne déclenche d'exécution."""
    calls: list[dict] = []

    async def spy_handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "notification.send", spy_handler)
    await _make_event_task(db_session, test_organization.id)

    bus = EventBus()
    store = InMemoryExecutionStore()
    engine = SchedulerEngine(
        _test_settings(),
        store=store,
        clock=FixedClock(),
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )
    component = _make_component(engine, bus, test_session_factory)
    component.start()
    component.stop()

    await _emit_failed_event(bus)
    await engine.wait_for_executions()

    assert calls == []
    assert store.all_executions() == []


def test_start_is_idempotent(test_session_factory):
    """Double start() n'abonne pas la callback deux fois."""
    bus = EventBus()
    engine = SchedulerEngine(
        _test_settings(),
        store=InMemoryExecutionStore(),
        clock=FixedClock(),
        session_factory=test_session_factory,
    )
    component = _make_component(engine, bus, test_session_factory)
    component.start()
    component.start()
    # Un seul handler par type d'événement (la callback est une bound
    # method — le bus stocke les références distinctes ; idempotence
    # garantie par le flag _subscribed).
    for handlers in bus._handlers.values():
        assert len([h for h in handlers if h == component._on_event]) == 1
    component.stop()


# ===========================================================================
# STORY-162 (T9) — résolution d'alias : un event_name canonique déclenche,
# un alias stocké en base déclenche aussi le canonique émis.
# ===========================================================================


async def test_event_trigger_matches_canonical_and_resolves_legacy_alias(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """DEPLOYMENT_SUCCEEDED (canonique) déclenche la définition stockée
    en canonique ; une ligne encore stockée en alias
    ``deployment.completed`` est aussi rapprochée via resolve_event_name."""
    calls: list[dict] = []

    async def spy_handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "notification.send", spy_handler)
    # Définition stockée en CANONIQUE
    await _make_event_task(
        db_session,
        test_organization.id,
        task_id="event-canonical",
        event_name="deployment.succeeded",
    )
    # Définition encore stockée en ALIAS legacy (migration non appliquée)
    await _make_event_task(
        db_session,
        test_organization.id,
        task_id="event-alias",
        event_name="deployment.completed",
    )

    bus = EventBus()
    engine = SchedulerEngine(
        _test_settings(),
        store=InMemoryExecutionStore(),
        clock=FixedClock(),
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )
    component = _make_component(engine, bus, test_session_factory)
    component.start()

    # Émission du canonique deployment.succeeded
    await bus.publish(
        Event(
            event_type=EventType.DEPLOYMENT_SUCCEEDED,
            aggregate_id=uuid.uuid4(),
            aggregate_type="deployment",
            payload={
                "deployment_id": "dep-9",
                "message": "ok",
                "new_status": "running",
            },
        )
    )
    await engine.wait_for_executions()

    # Les DEUX définitions (canonique + alias résolu) se déclenchent
    assert len(calls) == 2
    component.stop()
