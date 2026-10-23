"""Tests du contrat ``ExecutionStore`` — implémentation mémoire (STORY-160.2).

Transitions d'états spec 06 (``queued→running→success/failed``, ``skipped``),
récupération des orphelins au redémarrage (raison exacte contractualisée),
journaux horodatés ligne à ligne, ``triggered_by`` tracé, assainissement des
erreurs. Aucune dépendance à la table ``scheduled_task_executions``
(STORY-161) — l'isolation est précisément le rôle de cette implémentation.
"""

from datetime import datetime, timedelta, timezone

from app.services.scheduler_execution_store import (
    ORPHAN_REASON,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
    InMemoryExecutionStore,
    sanitize_error,
)


async def test_full_success_transition():
    """Nominal : queued → running → success, durée et horodatages portés."""
    store = InMemoryExecutionStore()
    execution_id = await store.mark_queued("task-1")
    await store.mark_running(execution_id)
    await store.mark_success(execution_id, duration_seconds=1.25)

    record = store.get(execution_id)
    assert record is not None
    assert record.status == STATUS_SUCCESS
    assert record.task_id == "task-1"
    assert record.duration_seconds == 1.25
    assert record.started_at is not None
    assert record.finished_at is not None
    # Journal : chaque étape a écrit sa ligne horodatée.
    lines = [line for _, line in record.logs]
    assert any("queued" in line for line in lines)
    assert any("running" in line for line in lines)
    assert any("success" in line for line in lines)
    assert all(isinstance(ts, datetime) for ts, _ in record.logs)


async def test_failed_transition_sanitizes_error():
    """Échec : erreur assainie/tronquée, statut failed, horodatage de fin."""
    store = InMemoryExecutionStore()
    execution_id = await store.mark_queued("task-1")
    await store.mark_running(execution_id)
    await store.mark_failed(execution_id, "x" * 10_000)

    record = store.get(execution_id)
    assert record is not None
    assert record.status == STATUS_FAILED
    assert len(record.error or "") <= 2000
    assert record.finished_at is not None


async def test_skipped_standalone_record():
    """Skipped : ligne autonome (verrou anti-chevauchement) avec raison."""
    store = InMemoryExecutionStore()
    await store.mark_skipped("task-1", "overlap : exécution précédente en cours")

    executions = store.executions_for_task("task-1")
    assert len(executions) == 1
    record = executions[0]
    assert record.status == STATUS_SKIPPED
    assert record.error == "overlap : exécution précédente en cours"
    assert record.finished_at is not None


async def test_triggered_by_traced():
    """``triggered_by`` est tracé (schedule | retry | manual)."""
    store = InMemoryExecutionStore()
    by_schedule = await store.mark_queued("task-1", "schedule")
    by_retry = await store.mark_queued("task-1", "retry")
    assert store.get(by_schedule).triggered_by == "schedule"
    assert store.get(by_retry).triggered_by == "retry"


async def test_recover_orphans_marks_queued_and_running_failed():
    """Orphelins : queued/running → failed avec la raison exacte spec 06
    (« interrompue — le scheduler a été redémarré pendant l'exécution »),
    simulation de lignes orphelines laissées par un crash."""
    store = InMemoryExecutionStore()
    queued_id = await store.mark_queued("task-1")
    running_id = await store.mark_queued("task-2")
    await store.mark_running(running_id)
    success_id = await store.mark_queued("task-3")
    await store.mark_running(success_id)
    await store.mark_success(success_id, 0.1)

    recovered = await store.recover_orphans()

    assert recovered == 2
    assert store.get(queued_id).status == STATUS_FAILED
    assert store.get(running_id).status == STATUS_FAILED
    assert ORPHAN_REASON in (store.get(queued_id).error or "")
    assert ORPHAN_REASON in (store.get(running_id).error or "")
    # Les exécutions déjà closes ne sont pas touchées.
    assert store.get(success_id).status == STATUS_SUCCESS


async def test_recover_orphans_empty_store_is_noop():
    """Base vide : récupération no-op (retourne 0, ne lève pas)."""
    store = InMemoryExecutionStore()
    assert await store.recover_orphans() == 0


async def test_append_log_is_chronological():
    """``append_log`` horodate ligne à ligne, dans l'ordre d'ajout."""
    base = datetime(2026, 10, 21, 12, 0, 0, tzinfo=timezone.utc)
    ticks = iter(
        [
            base,
            base + timedelta(seconds=1),
            base + timedelta(seconds=2),
            base + timedelta(seconds=5),
        ]
    )
    store = InMemoryExecutionStore(clock=lambda: next(ticks))
    execution_id = await store.mark_queued("task-1")
    await store.append_log(execution_id, "étape 1")
    await store.append_log(execution_id, "étape 2")

    record = store.get(execution_id)
    timestamps = [ts for ts, _ in record.logs]
    assert timestamps == sorted(timestamps)
    lines = [line for _, line in record.logs]
    assert "étape 1" in lines
    assert "étape 2" in lines


async def test_unknown_execution_id_is_ignored():
    """Défensif : identifiant inconnu → no-op (jamais d'exception)."""
    store = InMemoryExecutionStore()
    await store.mark_running("inexistant")  # ne lève pas
    await store.append_log("inexistant", "ligne")  # ne lève pas
    assert store.get("inexistant") is None


async def test_all_executions_ordered_by_creation():
    """Inspection : lignes retournées dans l'ordre de création."""
    store = InMemoryExecutionStore()
    await store.mark_queued("task-a")
    await store.mark_queued("task-b")
    all_records = store.all_executions()
    assert [r.task_id for r in all_records] == ["task-a", "task-b"]


def test_sanitize_error_edge_cases():
    """Assainissement : vide → « unknown error », troncature avec ellipse."""
    assert sanitize_error(None) == "unknown error"
    assert sanitize_error("   ") == "unknown error"
    long = "A" * 600
    sanitized = sanitize_error(long, limit=500)
    assert len(sanitized) == 500
    assert sanitized.endswith("...")
    assert sanitize_error("boom") == "boom"
