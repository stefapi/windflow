"""Tests du moteur ``SchedulerEngine`` (STORY-160.2) — time travel, jamais de sleep réel.

L'horloge est injectée (:class:`TimeTravel`) : chaque tick avance l'heure
manuellement. Les handlers sont mockés au
[registre](app/services/action_registry.py) via ``dataclasses.replace`` +
``monkeypatch.setitem`` (restauré après test) — aucune action réelle (160.3).

Familles (AC 1-3 de la story) : déclenchement à chaque échéance, relecture
défensive, verrou anti-chevauchement ``skipped``, timeout sans tuer la boucle,
politiques d'erreur, orphelins au démarrage, fuseaux IANA (2 h locale, pas
décalage UTC implicite), réinscription à chaud, action inconnue/stub,
``record_run``, logs sans secrets, intégration lifespan.
"""

import asyncio
import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

import app.services.action_registry as action_registry_module
import app.services.scheduler_engine as scheduler_engine_module
from app.config import Settings
from app.models.scheduled_task import ScheduledTask
from app.services.action_registry import get_action
from app.services.scheduler_engine import SchedulerEngine
from app.services.scheduler_execution_store import (
    ORPHAN_REASON,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
    InMemoryExecutionStore,
)

# Racine backend/ (backend/tests/unit/test_services/x.py → parents[3]).
BACKEND_ROOT = Path(__file__).resolve().parents[3]

# ===========================================================================
# Helpers : horloge time travel, handlers mockés, moteur branché sur la
# factory de sessions de test.
# ===========================================================================


class TimeTravel:
    """Horloge injectable : ``now`` avancé manuellement entre les ticks."""

    def __init__(self, start: datetime) -> None:
        assert start.tzinfo is not None, "l'horloge du moteur est aware UTC"
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: int) -> None:
        self.now = self.now + timedelta(**kwargs)


def _test_settings(**overrides: object) -> Settings:
    """Settings dédiés aux tests (sans lecture du ``.env`` local)."""
    defaults: dict = {
        "scheduler_tick_seconds": 30,
        "scheduler_task_timeout_seconds": 5,
        "scheduler_retry_backoff": 3,
        "scheduler_default_timezone": None,
        "scheduler_default_error_policy": "ignore",
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)  # type: ignore[arg-type]


def _patch_handler(monkeypatch: pytest.MonkeyPatch, action: str, handler) -> None:
    """Injecte un handler de test sur une action du registre (restauré)."""
    definition = replace(get_action(action), handler=handler)
    monkeypatch.setitem(action_registry_module._REGISTRY, action, definition)


async def _make_task(
    db_session,
    organization_id: str,
    *,
    task_id: str = "task-1",
    action: str = "host.scan",
    cron: str = "* * * * *",
    timezone_name: str | None = None,
    error_policy: str = "ignore",
    parameters: dict | None = None,
    enabled: bool = True,
) -> ScheduledTask:
    """Insère une définition directement en base (commit explicite).

    L'insertion ORM directe permet de poser des définitions qui ne passeraient
    pas la validation service (actions legacy gelées) — c'est précisément le
    cas de test « défense en profondeur » du moteur.
    """
    task = ScheduledTask(
        id=task_id,
        name=f"task {task_id}",
        action=action,
        cron_expression=cron,
        timezone=timezone_name,
        error_policy=error_policy,
        parameters=parameters or {"target_id": "tgt-1"},
        enabled=enabled,
        organization_id=organization_id,
    )
    db_session.add(task)
    await db_session.commit()
    return task


async def _refetch(db_session, task_id: str) -> ScheduledTask:
    """Relit une définition depuis la base en **forçant** le rafraîchissement
    (populate_existing) — le moteur écrit via ses propres sessions."""
    result = await db_session.execute(
        select(ScheduledTask)
        .where(ScheduledTask.id == task_id)
        .execution_options(populate_existing=True)
    )
    task = result.scalar_one()
    await db_session.commit()
    return task


def _make_engine(
    test_session_factory, clock: TimeTravel, **settings_overrides: object
) -> SchedulerEngine:
    return SchedulerEngine(
        _test_settings(**settings_overrides),
        store=InMemoryExecutionStore(),
        clock=clock,
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )


def _store(engine: SchedulerEngine) -> InMemoryExecutionStore:
    """Accès typé au store mémoire du moteur (inspection des tests)."""
    store = engine.store
    assert isinstance(store, InMemoryExecutionStore)
    return store


# ===========================================================================
# AC 1 — déclenchement à chaque échéance + relecture défensive
# ===========================================================================


async def test_cron_every_minute_triggers_at_each_due(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Cron ``* * * * *`` : déclenché à chaque échéance minute (time travel)."""
    calls: list[dict] = []

    async def handler(params: dict) -> None:
        calls.append(dict(params))

    _patch_handler(monkeypatch, "host.scan", handler)
    await _make_task(db_session, test_organization.id)
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 45, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    assert await engine.tick() == 0  # première vue : initialisation sans trigger
    clock.advance(minutes=1)  # 02:31:45
    assert await engine.tick() == 1
    await engine.wait_for_executions()  # l'exécution dédiée se termine
    clock.advance(seconds=10)  # 02:31:55 — même minute : pas de déclenchement
    assert await engine.tick() == 0
    clock.advance(minutes=1)  # 02:32:55
    assert await engine.tick() == 1
    await engine.wait_for_executions()

    assert len(calls) == 2
    # Les paramètres transmis au handler sont validés/normalisés par le schéma.
    assert calls[0] == {"target_id": "tgt-1"}
    records = _store(engine).executions_for_task("task-1")
    assert [r.status for r in records] == [STATUS_SUCCESS, STATUS_SUCCESS]


async def test_disabled_task_never_executed(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Tâche ``enabled=false`` : jamais exécutée (relecture à chaque tick)."""
    calls: list[dict] = []

    async def handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "host.scan", handler)
    task = await _make_task(db_session, test_organization.id, enabled=True)
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()  # init
    task.enabled = False
    await db_session.commit()
    clock.advance(minutes=2)
    assert await engine.tick() == 0
    await engine.wait_for_executions()
    assert calls == []


async def test_deleted_task_never_executed(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Tâche supprimée entre deux ticks : jamais exécutée."""
    calls: list[dict] = []

    async def handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "host.scan", handler)
    task = await _make_task(db_session, test_organization.id)
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()  # init
    await db_session.delete(task)
    await db_session.commit()
    clock.advance(minutes=2)
    assert await engine.tick() == 0
    await engine.wait_for_executions()
    assert calls == []


async def test_trigger_rechecks_fresh_definition(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Relecture défensive au déclenchement : la définition est relue en base
    (existence + enabled) juste avant l'exécution — désactivation concurrente
    → pas d'exécution."""
    calls: list[dict] = []

    async def handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "host.scan", handler)
    task = await _make_task(db_session, test_organization.id)
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()  # init : tâche vue active
    task.enabled = False  # désactivée APRÈS la lecture du tick, AVANT trigger
    await db_session.commit()
    clock.advance(minutes=1)

    fresh = await _refetch(db_session, task.id)
    snapshot = scheduler_engine_module._snapshot(fresh)
    assert await engine._trigger(snapshot) is False  # noqa: SLF001
    assert calls == []


# ===========================================================================
# AC 2 — verrou anti-chevauchement, tâche dédiée, timeout
# ===========================================================================


async def test_overlap_second_trigger_is_skipped(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """2 déclenchements simultanés → 1 exécution, la seconde tracée skipped."""
    calls: list[dict] = []
    release = asyncio.Event()

    async def slow_handler(params: dict) -> None:
        calls.append(params)
        await release.wait()

    _patch_handler(monkeypatch, "host.scan", slow_handler)
    await _make_task(db_session, test_organization.id)
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()  # init
    clock.advance(minutes=1)
    assert await engine.tick() == 1
    await asyncio.sleep(0.05)  # l'exécution dédiée atteint le handler bloqué

    clock.advance(minutes=1)
    assert await engine.tick() == 0  # chevauchement → skipped, pas empilé
    await asyncio.sleep(0.05)

    release.set()
    await engine.wait_for_executions()

    statuses = sorted(r.status for r in _store(engine).executions_for_task("task-1"))
    assert statuses == [STATUS_SKIPPED, STATUS_SUCCESS]
    assert len(calls) == 1


async def test_timeout_fails_execution_loop_survives(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Timeout (handler lent) → failed ; la boucle survit et exécute après.

    1ᵉʳ appel : handler bloqué 30 s > timeout 1 s → failed. L'échéance
    suivante (02:32) déclenche une nouvelle exécution dont le handler
    (2ᵉ appel) retourne immédiatement → success : preuve que la boucle a
    survécu au timeout."""
    calls: list[dict] = []

    async def slow_then_fast_handler(params: dict) -> None:
        calls.append(params)
        if len(calls) == 1:
            await asyncio.sleep(30)

    _patch_handler(monkeypatch, "host.scan", slow_then_fast_handler)
    await _make_task(db_session, test_organization.id)
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock, scheduler_task_timeout_seconds=1)

    await engine.tick()  # init : due 02:29
    clock.advance(minutes=1)  # 02:31:00
    assert await engine.tick() == 1
    await engine.wait_for_executions()  # attend le timeout (1 s réel)

    records = _store(engine).executions_for_task("task-1")
    assert len(records) == 1
    assert records[0].status == STATUS_FAILED
    assert "timeout" in (records[0].error or "")
    # La boucle survit : l'échéance suivante déclenche et réussit.
    clock.advance(minutes=2)  # 02:33:00 — due 02:32 non traitée
    assert await engine.tick() == 1
    await engine.wait_for_executions()

    records = _store(engine).executions_for_task("task-1")
    assert [r.status for r in records] == [STATUS_FAILED, STATUS_SUCCESS]
    task = await _refetch(db_session, "task-1")
    assert task.last_status == "success"
    assert task.run_count == 2
    assert len(calls) == 2


async def test_execution_runs_in_dedicated_task(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """L'exécution tourne dans une tâche asyncio dédiée, jamais inline dans
    le tick : ``tick()`` retourne AVANT la fin du handler."""
    handler_started = asyncio.Event()
    release = asyncio.Event()

    async def handler(params: dict) -> None:
        handler_started.set()
        await release.wait()

    _patch_handler(monkeypatch, "host.scan", handler)
    await _make_task(db_session, test_organization.id)
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()
    clock.advance(minutes=1)
    tick_done = asyncio.create_task(engine.tick())
    await asyncio.wait_for(handler_started.wait(), timeout=2)
    # Le handler tourne mais tick() est déjà retourné (1 = déclenché).
    assert await tick_done == 1
    release.set()
    await engine.wait_for_executions()


# ===========================================================================
# AC 2 — politique d'erreur
# ===========================================================================


async def test_policy_ignore_continues(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """``ignore`` : échec journalisé, exécution suivante normale."""
    calls: list[dict] = []

    async def failing(params: dict) -> None:
        calls.append(params)
        raise RuntimeError("boom")

    _patch_handler(monkeypatch, "host.scan", failing)
    await _make_task(db_session, test_organization.id, error_policy="ignore")
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()
    clock.advance(minutes=1)
    assert await engine.tick() == 1
    await engine.wait_for_executions()
    clock.advance(minutes=1)
    assert await engine.tick() == 1  # l'exécution suivante a bien lieu
    await engine.wait_for_executions()
    assert len(calls) == 2
    task = await _refetch(db_session, "task-1")
    assert task.enabled is True  # jamais désactivée
    assert task.last_status == "failed"


async def test_policy_retry_backoff(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """``retry`` : retentatives tracées avec backoff (défaut 3), puis échec."""
    calls: list[dict] = []

    async def failing(params: dict) -> None:
        calls.append(params)
        raise RuntimeError("always failing")

    _patch_handler(monkeypatch, "host.scan", failing)
    await _make_task(db_session, test_organization.id, error_policy="retry")
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()
    clock.advance(minutes=1)
    assert await engine.tick() == 1
    await engine.wait_for_executions()

    assert len(calls) == 4  # 1 tentative + 3 retentatives
    records = _store(engine).executions_for_task("task-1")
    assert len(records) == 1
    assert records[0].status == STATUS_FAILED
    retry_lines = [line for _, line in records[0].logs if line.startswith("retry ")]
    assert len(retry_lines) == 3


async def test_policy_retry_succeeds_on_second_attempt(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """``retry`` : succès à la 2ᵉ tentative → exécution success au final."""
    calls: list[dict] = []

    async def flaky(params: dict) -> None:
        calls.append(params)
        if len(calls) < 2:
            raise RuntimeError("transient")

    _patch_handler(monkeypatch, "host.scan", flaky)
    await _make_task(db_session, test_organization.id, error_policy="retry")
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()
    clock.advance(minutes=1)
    assert await engine.tick() == 1
    await engine.wait_for_executions()

    assert len(calls) == 2
    records = _store(engine).executions_for_task("task-1")
    assert records[0].status == STATUS_SUCCESS
    task = await _refetch(db_session, "task-1")
    assert task.last_status == "success"


async def test_policy_disable_disables_definition_and_emits_event(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """``disable`` : définition passée enabled=false + WARNING + événement."""
    events: list[object] = []

    async def failing(params: dict) -> None:
        raise RuntimeError("fatal")

    _patch_handler(monkeypatch, "host.scan", failing)

    async def fake_publish(event) -> None:
        events.append(event)

    monkeypatch.setattr(scheduler_engine_module, "publish_event", fake_publish)
    await _make_task(db_session, test_organization.id, error_policy="disable")
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()
    clock.advance(minutes=1)
    assert await engine.tick() == 1
    await engine.wait_for_executions()

    task = await _refetch(db_session, "task-1")
    assert task.enabled is False
    assert task.last_status == "failed"
    assert len(events) == 1
    assert events[0].payload["reason"] == "scheduled_task.disabled_by_error_policy"
    clock.advance(minutes=1)
    assert await engine.tick() == 0  # désactivée : plus jamais exécutée


async def test_repeated_failures_emit_alert_event(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """3 échecs consécutifs → événement système (alerte minimale, renvoi 161)."""
    events: list[object] = []

    async def failing(params: dict) -> None:
        raise RuntimeError("boom")

    _patch_handler(monkeypatch, "host.scan", failing)

    async def fake_publish(event) -> None:
        events.append(event)

    monkeypatch.setattr(scheduler_engine_module, "publish_event", fake_publish)
    await _make_task(db_session, test_organization.id, error_policy="ignore")
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()
    for _ in range(3):
        clock.advance(minutes=1)
        await engine.tick()
        await engine.wait_for_executions()

    alerts = [
        e for e in events if e.payload["reason"] == "scheduled_task.repeated_failures"
    ]
    assert len(alerts) == 1  # émis une fois exactement au seuil
    assert alerts[0].payload["consecutive_failures"] == 3


# ===========================================================================
# AC 3 — orphelins au démarrage
# ===========================================================================


async def test_run_recovers_orphans_at_startup(test_session_factory):
    """Au démarrage du moteur, les queued/running du store → failed (raison
    exacte spec 06) — pattern ``recover_pending_deployments``."""

    class WatchStore(InMemoryExecutionStore):
        def __init__(self) -> None:
            super().__init__()
            self.recovered = asyncio.Event()

        async def recover_orphans(self) -> int:
            count = await super().recover_orphans()
            self.recovered.set()
            return count

    store = WatchStore()
    orphan_queued = await store.mark_queued("old-task-1")
    orphan_running = await store.mark_queued("old-task-2")
    await store.mark_running(orphan_running)

    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = SchedulerEngine(
        _test_settings(),
        store=store,
        clock=clock,
        session_factory=test_session_factory,
    )
    run_task = asyncio.create_task(engine.run())
    await asyncio.wait_for(store.recovered.wait(), timeout=2)

    assert store.get(orphan_queued).status == STATUS_FAILED
    assert ORPHAN_REASON in (store.get(orphan_queued).error or "")
    assert store.get(orphan_running).status == STATUS_FAILED

    run_task.cancel()
    results = await asyncio.gather(run_task, return_exceptions=True)
    assert any(isinstance(r, asyncio.CancelledError) for r in results)


# ===========================================================================
# AC 3 — fuseaux IANA + réinscription à chaud
# ===========================================================================


async def test_timezone_paris_local_time_not_utc_shift(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Cron ``0 2 * * 0`` + Europe/Paris : déclenche à 2 h **locale**, pas à
    un décalage UTC implicite.

    Départ 2026-10-25 01:30 UTC = 03:30 Paris (CEST, avant le changement
    d'heure du 25/10 à 03:00 locale) — échéance locale précédente : 02:00 du
    25/10. À 02:30 UTC une évaluation UTC naïve verrait « 02:00 UTC atteint »
    et déclencherait à tort : l'évaluation locale ne déclenche PAS. Le vrai
    déclenchement arrive le dimanche suivant (01/11), 02:00 Paris = 01:00 UTC
    (CET)."""
    calls: list[datetime] = []

    async def handler(params: dict) -> None:
        calls.append(clock.now)

    _patch_handler(monkeypatch, "host.scan", handler)
    await _make_task(
        db_session,
        test_organization.id,
        cron="0 2 * * 0",
        timezone_name="Europe/Paris",
    )
    clock = TimeTravel(datetime(2026, 10, 25, 1, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()  # 03:30 Paris — init sans trigger
    clock.advance(hours=1)  # 02:30 UTC ≈ 03:30 Paris : PAS dû en local
    assert await engine.tick() == 0
    # Dimanche suivant (01/11), 01:30 UTC = 02:30 Paris (CET) : due 02:00
    # locale du 01/11 atteinte.
    clock.advance(days=6, hours=23)
    assert await engine.tick() == 1
    await engine.wait_for_executions()

    assert len(calls) == 1
    assert calls[0].hour == 1  # 01:30 UTC = 02:30 heure de Paris


async def test_global_default_timezone_utc(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Sans timezone sur la définition ni sur les settings : évaluation UTC."""
    calls: list[dict] = []

    async def handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "host.scan", handler)
    await _make_task(db_session, test_organization.id, cron="0 2 * * *")
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()  # init : due 02:00 UTC du 21/10
    clock.advance(minutes=30)  # 03:00 UTC : échéance précédente toujours 02:00
    assert await engine.tick() == 0
    clock.advance(hours=23)  # 22/10 02:00 UTC : get_prev strict → due du 21/10
    assert await engine.tick() == 0
    clock.advance(minutes=1)  # 02:01 UTC : due 02:00 du 22/10 > 02:00 du 21/10
    assert await engine.tick() == 1
    await engine.wait_for_executions()
    assert len(calls) == 1


async def test_settings_default_timezone_used(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Résolution du fuseau : ``task.timezone`` → ``settings`` → UTC — ici le
    settings porte ``Europe/Paris`` et la définition n'a pas de timezone.
    Départ 01:30 UTC = 03:30 Paris (CEST) ; passage CET dans la nuit du 24 ;
    le déclenchement a lieu le 22/10 à 02:00 Paris = 00:00 UTC... en réalité
    01:00 UTC après le passage CET (02:00 locale = 01:00 UTC)."""
    calls: list[datetime] = []

    async def handler(params: dict) -> None:
        calls.append(clock.now)

    _patch_handler(monkeypatch, "host.scan", handler)
    await _make_task(db_session, test_organization.id, cron="0 2 * * *")
    clock = TimeTravel(datetime(2026, 10, 21, 1, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(
        test_session_factory, clock, scheduler_default_timezone="Europe/Paris"
    )

    await engine.tick()  # 03:30 Paris — init, due 02:00 locale du 21/10
    clock.advance(minutes=30)  # 02:00 UTC = 04:00 Paris (CEST) : PAS dû
    assert await engine.tick() == 0
    clock.advance(hours=22)  # 22/10 00:00 UTC = 01:00 Paris (CET) : PAS dû
    assert await engine.tick() == 0
    clock.advance(hours=1)  # 01:00 UTC = 02:00 Paris : dû
    assert await engine.tick() == 1
    await engine.wait_for_executions()
    assert len(calls) == 1
    assert calls[0].hour == 1  # 01:00 UTC = 02:00 heure de Paris


async def test_hot_re_registration_on_timezone_change(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Réinscription à chaud : un changement de fuseau est pris en compte au
    tick suivant, sans redémarrage ni déclenchement rétroactif."""
    calls: list[dict] = []

    async def handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "host.scan", handler)
    task = await _make_task(db_session, test_organization.id)
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()  # init UTC : due 02:30
    # Changement de fuseau : l'heure locale New York est ~6 h en arrière.
    task.timezone = "America/New_York"
    await db_session.commit()
    clock.advance(minutes=1)
    assert await engine.tick() == 0  # réinscription : réinit, pas de trigger
    clock.advance(minutes=1)
    assert await engine.tick() == 1  # due selon le NOUVEAU fuseau
    await engine.wait_for_executions()
    assert len(calls) == 1


async def test_hot_re_registration_on_cron_change(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """Réinscription à chaud : changement de cron pris en compte au tick
    suivant sans redémarrage."""
    calls: list[dict] = []

    async def handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "host.scan", handler)
    task = await _make_task(db_session, test_organization.id, cron="0 4 * * *")
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()  # init : due 04:00 (du 20/10)
    task.cron_expression = "0 3 * * *"
    await db_session.commit()
    clock.advance(minutes=10)  # 02:40 — réinit sur le nouveau cron (due 03:00)
    assert await engine.tick() == 0
    clock.advance(minutes=19)  # 02:59 — toujours pas dûe (03:00 non atteinte)
    assert await engine.tick() == 0
    clock.advance(minutes=2)  # 03:01 — due 03:00 atteinte
    assert await engine.tick() == 1
    await engine.wait_for_executions()
    assert len(calls) == 1


async def test_corrupted_timezone_or_cron_ignored_defensively(
    db_session, test_session_factory, test_organization, monkeypatch, caplog
):
    """Défense en profondeur : fuseau IANA inconnu ou cron invalide en base
    (corruption, contournement API) → définition ignorée, boucle intacte."""
    calls: list[dict] = []

    async def handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "host.scan", handler)
    await _make_task(
        db_session,
        test_organization.id,
        task_id="bad-tz",
        timezone_name="Mars/Olympus",
    )
    await _make_task(
        db_session, test_organization.id, task_id="bad-cron", cron="not a cron"
    )
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    with caplog.at_level(logging.WARNING, logger="app.services.scheduler_engine"):
        await engine.tick()
        clock.advance(minutes=5)
        assert await engine.tick() == 0

    assert calls == []
    assert "fuseau inconnu" in caplog.text
    assert "expression cron invalide" in caplog.text


# ===========================================================================
# Dispatch défensif via le registre (160.1)
# ===========================================================================


async def test_unknown_action_fails_execution_explicitly(
    db_session, test_session_factory, test_organization
):
    """Action hors registre (ex. legacy gelée) → failed erreur explicite,
    boucle intacte (jamais de KeyError brut)."""
    await _make_task(
        db_session,
        test_organization.id,
        action="legacy.cleanup_logs",  # gelée par la migration 1321
    )
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()
    clock.advance(minutes=1)
    assert await engine.tick() == 1
    await engine.wait_for_executions()

    records = _store(engine).executions_for_task("task-1")
    assert records[0].status == STATUS_FAILED
    assert "Unknown scheduler action" in (records[0].error or "")
    task = await _refetch(db_session, "task-1")
    assert task.last_status == "failed"
    clock.advance(minutes=1)  # la boucle survit
    await engine.tick()


async def test_stub_action_fails_explicitly(
    db_session, test_session_factory, test_organization
):
    """Stub ``implemented=False`` (stack.backup) → failed explicite, jamais
    de succès silencieux."""
    await _make_task(
        db_session,
        test_organization.id,
        action="stack.backup",
        parameters={"stack_id": "stk-1"},
    )
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()
    clock.advance(minutes=1)
    await engine.tick()
    await engine.wait_for_executions()

    records = _store(engine).executions_for_task("task-1")
    assert records[0].status == STATUS_FAILED
    assert "non implémentée" in (records[0].error or "")


async def test_missing_handler_fails_explicitly(
    db_session, test_session_factory, test_organization
):
    """Action ``implemented=True`` mais handler non enregistré (pré-160.3)
    → failed explicite « attendu STORY-160.3 »."""
    await _make_task(db_session, test_organization.id)  # host.scan, handler None
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()
    clock.advance(minutes=1)
    await engine.tick()
    await engine.wait_for_executions()

    records = _store(engine).executions_for_task("task-1")
    assert records[0].status == STATUS_FAILED
    assert "160.3" in (records[0].error or "")


async def test_record_run_updates_definition(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """``record_run`` reflète l'exécution sur la définition (last_status,
    run_count, last_run)."""
    calls: list[dict] = []

    async def handler(params: dict) -> None:
        calls.append(params)

    _patch_handler(monkeypatch, "host.scan", handler)
    await _make_task(db_session, test_organization.id)
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()
    clock.advance(minutes=1)
    await engine.tick()
    await engine.wait_for_executions()

    task = await _refetch(db_session, "task-1")
    assert task.last_status == "success"
    assert task.run_count == 1
    assert task.last_run is not None


# ===========================================================================
# Sécurité (rules 40) — logs sans secrets
# ===========================================================================


async def test_logs_never_contain_raw_parameters(
    db_session, test_session_factory, test_organization, monkeypatch, caplog
):
    """Aucun parameter brut dans les logs du moteur (rules 40)."""

    async def failing(params: dict) -> None:
        raise RuntimeError("échec contrôlé")

    _patch_handler(monkeypatch, "host.scan", failing)
    secret = "tgt-super-secret-42"
    await _make_task(db_session, test_organization.id, parameters={"target_id": secret})
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    with caplog.at_level(logging.INFO, logger="app.services.scheduler_engine"):
        await engine.tick()
        clock.advance(minutes=1)
        await engine.tick()
        await engine.wait_for_executions()

    # Seuls les logs DU MOTEUR sont audités (caplog capture aussi les logs
    # SQLAlchemy — echo SQL hors périmètre du moteur).
    engine_logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == "app.services.scheduler_engine"
    )
    assert secret not in engine_logs
    # L'erreur persistée est assainie, sans paramètre.
    records = _store(engine).executions_for_task("task-1")
    assert secret not in (records[0].error or "")


async def test_last_error_truncated_in_store(
    db_session, test_session_factory, test_organization, monkeypatch
):
    """``last_error`` tronqué : un handler levant une erreur kilométrique ne
    pose jamais un texte démesuré en store ni en base."""

    async def failing(params: dict) -> None:
        raise ValueError("E" * 10_000)

    _patch_handler(monkeypatch, "host.scan", failing)
    await _make_task(db_session, test_organization.id)
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = _make_engine(test_session_factory, clock)

    await engine.tick()
    clock.advance(minutes=1)
    await engine.tick()
    await engine.wait_for_executions()

    records = _store(engine).executions_for_task("task-1")
    assert len(records[0].error or "") <= 2000
    task = await _refetch(db_session, "task-1")
    assert len(task.last_error or "") <= 2000


# ===========================================================================
# Intégration lifespan (non-régression AC 4)
# ===========================================================================


def test_lifespan_wiring_and_existing_loops_preserved():
    """Garde-fou structurel (pattern test_no_celery_residue) : le lifespan
    démarre le moteur comme 4ᵉ tâche SANS fusionner les 3 boucles existantes
    ni toucher à ``recover_pending_deployments`` ; shutdown dédié."""
    source = (BACKEND_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    # Les 3 boucles existantes sont intactes.
    assert "_periodic_health_check" in source
    assert "_periodic_refresh_token_purge" in source
    assert "_periodic_audit_purge" in source
    assert "recover_pending_deployments" in source
    # 4ᵉ tâche lifespan : moteur scheduler + shutdown dédié.
    assert "SchedulerEngine" in source
    assert "scheduler_task = asyncio.create_task(scheduler_engine.run())" in source
    assert "scheduler_task.cancel()" in source
    # Démarrage conditionné par le setting.
    assert "settings.scheduler_enabled" in source


def test_scheduler_disabled_by_default():
    """Le moteur n'est PAS démarré par défaut (opt-in, SCHEDULER_ENABLED)."""
    settings = Settings(_env_file=None)
    assert settings.scheduler_enabled is False


async def test_run_loop_cancels_cleanly(test_session_factory):
    """Annulation de ``run()`` : CancelledError traitée, pas d'exception
    non-attendue qui fuiterait dans la boucle."""
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = SchedulerEngine(
        _test_settings(scheduler_tick_seconds=30),
        store=InMemoryExecutionStore(),
        clock=clock,
        session_factory=test_session_factory,
    )
    run_task = asyncio.create_task(engine.run())
    await asyncio.sleep(0.05)  # laisse la boucle démarrer
    run_task.cancel()
    results = await asyncio.gather(run_task, return_exceptions=True)
    assert any(isinstance(r, asyncio.CancelledError) for r in results)


async def test_tick_error_does_not_kill_run_loop(test_session_factory, monkeypatch):
    """Une erreur de tick (ex. DB injoignable) est journalisée — la boucle
    ``run()`` continue (jamais de mort silencieuse du moteur)."""
    clock = TimeTravel(datetime(2026, 10, 21, 2, 30, 0, tzinfo=timezone.utc))
    engine = SchedulerEngine(
        _test_settings(scheduler_tick_seconds=1),
        store=InMemoryExecutionStore(),
        clock=clock,
        session_factory=test_session_factory,
    )

    async def exploding_tick() -> int:
        raise RuntimeError("db injoignable")

    monkeypatch.setattr(engine, "tick", exploding_tick)
    run_task = asyncio.create_task(engine.run())
    await asyncio.sleep(0.2)  # plusieurs ticks défaillants enchaînés
    assert not run_task.done()  # la boucle a survécu
    run_task.cancel()
    await asyncio.gather(run_task, return_exceptions=True)
