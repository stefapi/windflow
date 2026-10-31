"""Tests des métriques scheduler (STORY-172 — Tâche 6, AC 1).

Le moteur ``SchedulerEngine`` instrumente les trois statuts terminaux :
``success``/``failed`` sur les deux chemins (cron ``_execute`` + manuel
``_execute_manual``) et ``skipped`` (chevauchements). Les assertions
portent sur des **deltas de séries** ``windflow_scheduler_*`` du
``REGISTRY`` global après de vraies exécutions du moteur (time travel,
pattern ``test_scheduler_engine.py``).
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from prometheus_client import REGISTRY

import app.services.action_registry as action_registry_module
from app.config import Settings
from app.models.scheduled_task import ScheduledTask
from app.services.action_registry import get_action
from app.services.scheduler_engine import SchedulerEngine
from app.services.scheduler_execution_store import InMemoryExecutionStore


def _value(name: str, labels: dict | None = None) -> float:
    """Valeur actuelle d'un sample (0 si la série n'existe pas encore)."""
    value = REGISTRY.get_sample_value(name, labels)
    return value if value is not None else 0.0


class TimeTravel:
    """Horloge injectable : ``now`` avancé manuellement entre les ticks."""

    def __init__(self, start: datetime) -> None:
        assert start.tzinfo is not None
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: int) -> None:
        self.now = self.now + timedelta(**kwargs)


def _test_settings() -> Settings:
    """Settings dédiés aux tests (sans lecture du ``.env`` local)."""
    return Settings(
        _env_file=None,  # type: ignore[arg-type]
        scheduler_tick_seconds=30,
        scheduler_task_timeout_seconds=5,
        scheduler_retry_backoff=0,
        scheduler_default_timezone=None,
        scheduler_default_error_policy="ignore",
    )


def _patch_handler(monkeypatch: pytest.MonkeyPatch, action: str, handler) -> None:
    """Injecte un handler de test sur une action du registre (restauré)."""
    definition = replace(get_action(action), handler=handler)
    monkeypatch.setitem(action_registry_module._REGISTRY, action, definition)


async def _make_task(
    db_session, organization_id: str, *, task_id: str = "task-metrics"
) -> ScheduledTask:
    """Insère une définition cron toutes les minutes directement en base."""
    task = ScheduledTask(
        id=task_id,
        name=f"task {task_id}",
        action="host.scan",
        cron_expression="* * * * *",
        timezone=None,
        error_policy="ignore",
        parameters={"target_id": "tgt-1"},
        enabled=True,
        organization_id=organization_id,
    )
    db_session.add(task)
    await db_session.commit()
    return task


def _make_engine(test_session_factory, clock: TimeTravel) -> SchedulerEngine:
    return SchedulerEngine(
        _test_settings(),
        store=InMemoryExecutionStore(),
        clock=clock,
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )


async def _run_cron_once(engine, clock: TimeTravel) -> None:
    """Tick d'initialisation puis tick déclencheur + attente de l'exécution."""
    await engine.tick()
    clock.advance(minutes=1)
    await engine.tick()
    await engine.wait_for_executions()


class TestSchedulerMetrics:
    """Deltas ``windflow_scheduler_executions_total`` par statut."""

    @pytest.mark.asyncio
    async def test_successful_execution_increments_counter(
        self, db_session, test_session_factory, test_organization, monkeypatch
    ):
        """Handler OK → ``status="success"`` +1 et durée observée (+1 _count)."""

        async def handler(params: dict) -> None:
            return None

        _patch_handler(monkeypatch, "host.scan", handler)
        await _make_task(db_session, test_organization.id)
        clock = TimeTravel(datetime(2026, 10, 31, 3, 0, 0, tzinfo=timezone.utc))
        engine = _make_engine(test_session_factory, clock)

        before = _value("windflow_scheduler_executions_total", {"status": "success"})
        before_count = _value("windflow_scheduler_execution_duration_seconds_count")

        await _run_cron_once(engine, clock)

        assert (
            _value("windflow_scheduler_executions_total", {"status": "success"})
            - before
            == 1.0
        )
        assert (
            _value("windflow_scheduler_execution_duration_seconds_count") - before_count
            == 1.0
        )

    @pytest.mark.asyncio
    async def test_failed_execution_increments_counter(
        self, db_session, test_session_factory, test_organization, monkeypatch
    ):
        """Handler qui lève → ``status="failed"`` +1."""

        async def failing_handler(params: dict) -> None:
            raise RuntimeError("boom scheduler metrics")

        _patch_handler(monkeypatch, "host.scan", failing_handler)
        await _make_task(db_session, test_organization.id)
        clock = TimeTravel(datetime(2026, 10, 31, 3, 0, 0, tzinfo=timezone.utc))
        engine = _make_engine(test_session_factory, clock)

        before = _value("windflow_scheduler_executions_total", {"status": "failed"})

        await _run_cron_once(engine, clock)

        assert (
            _value("windflow_scheduler_executions_total", {"status": "failed"}) - before
            == 1.0
        )

    @pytest.mark.asyncio
    async def test_skipped_overlap_increments_counter(
        self, db_session, test_session_factory, test_organization, monkeypatch
    ):
        """Chevauchement (verrou actif) → ``status="skipped"`` +1."""
        from sqlalchemy import select

        from app.services.scheduler_engine import _snapshot

        release = asyncio.Event()

        async def slow_handler(params: dict) -> None:
            await release.wait()

        _patch_handler(monkeypatch, "host.scan", slow_handler)
        task = await _make_task(db_session, test_organization.id)
        clock = TimeTravel(datetime(2026, 10, 31, 3, 0, 0, tzinfo=timezone.utc))
        engine = _make_engine(test_session_factory, clock)

        before = _value("windflow_scheduler_executions_total", {"status": "skipped"})

        await engine.tick()  # init
        clock.advance(minutes=1)
        await engine.tick()  # première exécution lancée (lente — verrou tenu)
        # La définition est encore « running » → re-trigger direct → skipped.
        result = await db_session.execute(
            select(ScheduledTask).where(ScheduledTask.id == task.id)
        )
        fresh = result.scalar_one()
        assert await engine._trigger(_snapshot(fresh)) is False  # noqa: SLF001

        release.set()
        await engine.wait_for_executions()

        # Le chevauchement a bien été compté « skipped » par mark_skipped.
        assert (
            _value("windflow_scheduler_executions_total", {"status": "skipped"})
            - before
            == 1.0
        )

    @pytest.mark.asyncio
    async def test_manual_run_records_execution(
        self, db_session, test_session_factory, test_organization, monkeypatch
    ):
        """Chemin ``run_task_now`` (manuel) → compteur success aussi instrumenté."""

        async def handler(params: dict) -> None:
            return None

        _patch_handler(monkeypatch, "host.scan", handler)
        await _make_task(db_session, test_organization.id, task_id="task-manual")
        clock = TimeTravel(datetime(2026, 10, 31, 3, 0, 0, tzinfo=timezone.utc))
        engine = _make_engine(test_session_factory, clock)

        before = _value("windflow_scheduler_executions_total", {"status": "success"})

        await engine.run_task_now("task-manual")
        await engine.wait_for_executions()

        assert (
            _value("windflow_scheduler_executions_total", {"status": "success"})
            - before
            == 1.0
        )

    @pytest.mark.asyncio
    async def test_metrics_never_break_engine(
        self, db_session, test_session_factory, test_organization, monkeypatch
    ):
        """Best-effort : helper levant → l'exécution reste tracée dans le store."""

        async def handler(params: dict) -> None:
            return None

        _patch_handler(monkeypatch, "host.scan", handler)
        await _make_task(db_session, test_organization.id, task_id="task-resilient")
        clock = TimeTravel(datetime(2026, 10, 31, 3, 0, 0, tzinfo=timezone.utc))
        engine = _make_engine(test_session_factory, clock)
        await engine.tick()  # init

        with patch(
            "app.services.scheduler_engine.record_scheduler_execution",
            side_effect=RuntimeError("metrics exploded"),
        ):
            clock.advance(minutes=1)
            await engine.tick()
            await engine.wait_for_executions()

        records = engine.store.executions_for_task("task-resilient")
        assert [r.status for r in records] == ["success"]
