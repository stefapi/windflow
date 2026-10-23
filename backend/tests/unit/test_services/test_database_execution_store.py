"""Tests du ``DatabaseExecutionStore`` (STORY-161 — Tâche 9).

Couvre le contrat ``ExecutionStore`` sur l'implémentation base de données
(table ``scheduled_task_executions``) : cycle nominal complet, assainissement
des erreurs, ``skipped``, journal JSON best-effort (AC 3), orphelins,
mapping ``triggered_by`` (décision 4), FK CASCADE et purge/rétention avec
time travel (AC 4) — l'audit n'est **jamais** touché.

Patterns : horloge injectable (jamais ``time.sleep``), base de test isolée
par fixture ``test_session_factory`` (schéma posé par les migrations).
"""

import json
import logging
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.scheduled_task import ScheduledTask
from app.models.scheduled_task_execution import ScheduledTaskExecution
from app.services.scheduler_execution_store import (
    ORPHAN_REASON,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
    DatabaseExecutionStore,
)

# Horloge de référence déterministe (aware UTC).
_T0 = datetime(2026, 10, 23, 3, 0, 0, tzinfo=timezone.utc)


class _FixedClock:
    """Horloge injectable avançable manuellement (time travel)."""

    def __init__(self) -> None:
        self.now = _T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now = self.now + timedelta(**kwargs)


@pytest.fixture
def clock() -> _FixedClock:
    return _FixedClock()


@pytest.fixture
async def seed_task(
    db_session: AsyncSession, test_organization: Organization
) -> ScheduledTask:
    """Définition minimale (l'exécution n'exige rien d'elle)."""
    task = ScheduledTask(
        id="task-store-1",
        name="store-test",
        action="host.scan",
        cron_expression="0 3 * * *",
        parameters={"target_id": "tgt-1"},
        organization_id=test_organization.id,
    )
    db_session.add(task)
    await db_session.commit()
    return task


@pytest.fixture
def store(test_session_factory, clock) -> DatabaseExecutionStore:
    """Store DB branché sur la base de test, horloge time travel."""
    return DatabaseExecutionStore(session_factory=test_session_factory, clock=clock)


async def _fetch(db_session: AsyncSession, execution_id: str) -> ScheduledTaskExecution:
    """Relit une ligne d'exécution en forçant le rafraîchissement."""
    result = await db_session.execute(
        select(ScheduledTaskExecution)
        .where(ScheduledTaskExecution.id == execution_id)
        .execution_options(populate_existing=True)
    )
    execution = result.scalar_one()
    return execution


# --- Cycle nominal -------------------------------------------------------------


class TestLifecycle:
    async def test_queued_running_success_cycle(
        self, store, db_session, seed_task, clock
    ):
        """queued → running → success : statuts, horodatages, durée (AC 3)."""
        execution_id = await store.mark_queued(seed_task.id, "schedule")
        clock.advance(seconds=1)
        await store.mark_running(execution_id)
        clock.advance(seconds=2)
        await store.mark_success(execution_id, 2.0)

        execution = await _fetch(db_session, execution_id)
        assert execution.status == STATUS_SUCCESS
        assert execution.triggered_by == "cron"  # mapping décision 4
        assert execution.started_at is not None
        assert execution.finished_at is not None
        assert execution.duration_seconds == 2.0
        # Journal ligne à ligne horodaté (JSON ISO 8601 UTC).
        logs = json.loads(execution.logs or "[]")
        assert isinstance(logs, list) and logs
        for entry in logs:
            assert set(entry) == {"timestamp", "message"}
            parsed = datetime.fromisoformat(entry["timestamp"])
            assert parsed.tzinfo is not None

    async def test_failed_error_sanitized(self, store, db_session, seed_task, clock):
        """queued → running → failed : error assaini/tronqué (rules 40)."""
        execution_id = await store.mark_queued(seed_task.id, "schedule")
        await store.mark_running(execution_id)
        long_payload = "x" * 5000
        await store.mark_failed(execution_id, long_payload)

        execution = await _fetch(db_session, execution_id)
        assert execution.status == STATUS_FAILED
        assert execution.error is not None
        assert execution.error.endswith("...")
        assert len(execution.error) <= 2000
        assert execution.finished_at is not None

    async def test_mark_skipped_direct_row(self, store, db_session, seed_task, clock):
        """mark_skipped : ligne directe ``skipped`` + raison assainie."""
        await store.mark_skipped(seed_task.id, "overlap : déjà en cours")
        result = await db_session.execute(
            select(ScheduledTaskExecution).where(
                ScheduledTaskExecution.task_id == seed_task.id
            )
        )
        execution = result.scalar_one()
        assert execution.status == STATUS_SKIPPED
        assert execution.error == "overlap : déjà en cours"
        assert execution.started_at is None  # jamais démarrée
        assert execution.finished_at is not None


# --- Journal best-effort (AC 3) -------------------------------------------------


class TestAppendLog:
    async def test_append_log_json_lines(self, store, db_session, seed_task, clock):
        """Lignes horodatées sérialisées JSON, ordre d'ajout respecté."""
        execution_id = await store.mark_queued(seed_task.id, "schedule")
        clock.advance(seconds=5)
        await store.append_log(execution_id, "étape 1")
        clock.advance(seconds=5)
        await store.append_log(execution_id, "étape 2")

        execution = await _fetch(db_session, execution_id)
        logs = json.loads(execution.logs or "[]")
        messages = [entry["message"] for entry in logs]
        assert messages[-2:] == ["étape 1", "étape 2"]
        # Horodatages ordonnés et ISO 8601 parsables.
        stamps = [datetime.fromisoformat(e["timestamp"]) for e in logs]
        assert stamps == sorted(stamps)

    async def test_append_log_failure_never_propagates(
        self, store, db_session, seed_task, monkeypatch, caplog
    ):
        """Échec d'écriture avalé : aucune exception, trace logger.error,
        statut de l'exécution intact (AC 3 — best-effort)."""
        execution_id = await store.mark_queued(seed_task.id, "schedule")

        # Échec d'écriture simulé au niveau du commit de session.
        from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession

        async def _failing_commit(self_inner):
            raise RuntimeError("simulated commit failure")

        monkeypatch.setattr(_AsyncSession, "commit", _failing_commit)
        with caplog.at_level(
            logging.ERROR, logger="app.services.scheduler_execution_store"
        ):
            # NE DOIT PAS lever (best-effort — seule la ligne est perdue).
            await store.append_log(execution_id, "ligne perdue")
        monkeypatch.undo()

        assert any(
            "échec d'écriture de journal" in rec.message.lower()
            for rec in caplog.records
        )
        # Le statut reste queued — l'exécution est intacte.
        execution = await _fetch(db_session, execution_id)
        assert execution.status == STATUS_QUEUED


# --- Orphelins ------------------------------------------------------------------


class TestRecoverOrphans:
    async def test_recover_orphans_marks_failed(
        self, store, db_session, seed_task, clock
    ):
        """queued/running → failed avec le libellé exact ORPHAN_REASON."""
        queued_id = await store.mark_queued(seed_task.id, "schedule")
        other_id = await store.mark_queued(seed_task.id, "schedule")
        await store.mark_running(other_id)
        closed_id = await store.mark_queued(seed_task.id, "schedule")
        await store.mark_success(closed_id, 1.0)

        recovered = await store.recover_orphans()
        assert recovered == 2
        for execution_id in (queued_id, other_id):
            execution = await _fetch(db_session, execution_id)
            assert execution.status == STATUS_FAILED
            assert execution.error == ORPHAN_REASON
            assert execution.finished_at is not None
        # La ligne close est inchangée.
        closed = await _fetch(db_session, closed_id)
        assert closed.status == STATUS_SUCCESS


# --- Mapping triggered_by (décision 4) ------------------------------------------


class TestTriggeredByMapping:
    async def test_schedule_mapped_to_cron(self, store, db_session, seed_task):
        """« schedule » (contrat moteur) persisté « cron » (spec 06)."""
        execution_id = await store.mark_queued(seed_task.id, "schedule")
        execution = await _fetch(db_session, execution_id)
        assert execution.triggered_by == "cron"

    async def test_event_and_manual_unchanged(self, store, db_session, seed_task):
        """« event » et « manual » persistés tels quels."""
        event_id = await store.mark_queued(seed_task.id, "event")
        manual_id = await store.mark_queued(seed_task.id, "manual")
        assert (await _fetch(db_session, event_id)).triggered_by == "event"
        assert (await _fetch(db_session, manual_id)).triggered_by == "manual"


# --- FK CASCADE -----------------------------------------------------------------


class TestForeignKeyCascade:
    async def test_task_deletion_cascades_executions(
        self, store, test_db_engine, db_session, seed_task
    ):
        """Suppression de la définition → ses exécutions disparaissent (FK).

        SQLite n'active pas ``PRAGMA foreign_keys`` par défaut : la
        cascade est vérifiée sur une connexion dédiée avec le PRAGMA
        actif (comportement natif de PostgreSQL).
        """
        task_id = seed_task.id  # capturé avant expiration de l'instance
        await store.mark_queued(task_id, "schedule")
        await store.mark_queued(task_id, "schedule")

        from sqlalchemy import text

        async with test_db_engine.connect() as conn:
            await conn.execute(text("PRAGMA foreign_keys=ON"))
            await conn.execute(
                text("DELETE FROM scheduled_tasks WHERE id = :tid"),
                {"tid": task_id},
            )
            await conn.commit()
        # Invalider le cache d'identité de la session de test.
        db_session.expire_all()
        result = await db_session.execute(
            select(ScheduledTaskExecution).where(
                ScheduledTaskExecution.task_id == task_id
            )
        )
        assert result.scalars().all() == []


# --- Rétention / purge (AC 4) ----------------------------------------------------


class TestPurgeExpired:
    async def _seed_executions(
        self, store, seed_task, clock, *, age_days: float
    ) -> str:
        """Crée une exécution close dont le démarrage date de age_days."""
        clock.now = _T0 - timedelta(days=age_days)
        execution_id = await store.mark_queued(seed_task.id, "schedule")
        await store.mark_running(execution_id)
        await store.mark_success(execution_id, 1.0)
        return execution_id

    async def test_purge_removes_old_keeps_recent(
        self, store, db_session, seed_task, clock
    ):
        """Rétention 7 j : lignes âgées purgées, récentes conservées."""
        old_id = await self._seed_executions(store, seed_task, clock, age_days=10)
        clock.now = _T0 - timedelta(days=2)
        recent_id = await store.mark_queued(seed_task.id, "schedule")
        await store.mark_running(recent_id)
        await store.mark_success(recent_id, 1.0)

        clock.now = _T0
        removed = await store.purge_expired(retention_days=7)
        assert removed == 1
        # old purgée, récente conservée.
        result = await db_session.execute(select(ScheduledTaskExecution.id))
        remaining = {row[0] for row in result.all()}
        assert recent_id in remaining
        assert old_id not in remaining

    async def test_purge_uses_created_at_when_no_started_at(
        self, store, db_session, seed_task, clock
    ):
        """Lignes sans started_at (skipped) purgées sur created_at."""
        clock.now = _T0 - timedelta(days=30)
        await store.mark_skipped(seed_task.id, "raison ancienne")
        clock.now = _T0
        removed = await store.purge_expired(retention_days=7)
        assert removed >= 1

    async def test_never_touches_audit_logs(
        self, store, db_session, seed_task, clock, test_organization
    ):
        """AC 4 : la purge ne supprime JAMAIS de lignes audit_logs."""
        from app.models.user import User

        user = User(
            email="purge-audit@example.com",
            username="purge-audit",
            hashed_password="x",
            is_superuser=False,
        )
        db_session.add(user)
        await db_session.flush()
        for i in range(3):
            db_session.add(
                AuditLog(
                    user_id=user.id,
                    organization_id=test_organization.id,
                    action=f"test.action.{i}",
                    resource_type="test",
                    created_at=_T0 - timedelta(days=30),
                )
            )
        await db_session.commit()
        before = len((await db_session.execute(select(AuditLog.id))).all())

        await store.purge_expired(retention_days=7)

        after = len((await db_session.execute(select(AuditLog.id))).all())
        assert after == before
