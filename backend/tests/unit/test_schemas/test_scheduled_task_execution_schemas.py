"""Tests des schemas Pydantic des exécutions (STORY-161 — Tâche 9).

Validation des domaines fermés (``Literal`` — futur 422), des champs
exposés (liste sans ``logs``, détail avec journal structuré) et de
l'absence de tout champ sensible (checklist rules 40 : jamais de
``parameters`` de définition ni de secret). Désérialisation ORM
(``model_validate``) sur fixture réaliste.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.scheduled_task_execution import (
    ExecutionLogLine,
    ExecutionQueryParams,
    ManualRunResponse,
    ScheduledTaskExecutionListItem,
    ScheduledTaskExecutionResponse,
)


class _FakeExecution:
    """Fixture ORM réaliste (attributs scalaires — from_attributes)."""

    def __init__(self, **overrides: object) -> None:
        base = {
            "id": "exec-1",
            "task_id": "task-1",
            "status": "success",
            "triggered_by": "cron",
            "started_at": datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc),
            "finished_at": datetime(2026, 10, 23, 3, 1, tzinfo=timezone.utc),
            "duration_seconds": 60.0,
            "error": None,
            "created_at": datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc),
        }
        base.update(overrides)
        for key, value in base.items():
            setattr(self, key, value)


class TestLiteralDomains:
    """Valeur hors domaine → ValidationError (futur 422 à l'API)."""

    def test_status_domain(self):
        with pytest.raises(ValidationError):
            ScheduledTaskExecutionListItem.model_validate(
                {**vars(_FakeExecution()), "status": "bogus"}
            )

    def test_triggered_by_domain(self):
        with pytest.raises(ValidationError):
            ScheduledTaskExecutionListItem.model_validate(
                {**vars(_FakeExecution()), "triggered_by": "schedule"}
            )

    def test_query_params_status_domain(self):
        with pytest.raises(ValidationError):
            ExecutionQueryParams(status="unknown")

    def test_query_params_triggered_by_domain(self):
        # "schedule" (contrat moteur) est refusé : seul le domaine spec 06
        # (cron|event|manual) est exposé à l'API.
        with pytest.raises(ValidationError):
            ExecutionQueryParams(triggered_by="schedule")

    def test_query_params_valid_combination(self):
        params = ExecutionQueryParams(
            status="failed",
            triggered_by="cron",
            started_after=datetime(2026, 10, 1, tzinfo=timezone.utc),
            started_before=datetime(2026, 10, 31, tzinfo=timezone.utc),
        )
        assert params.status == "failed"
        assert params.triggered_by == "cron"


class TestExposedFields:
    def test_list_item_has_no_logs(self):
        """Item de liste léger : champ ``logs`` absent."""
        item = ScheduledTaskExecutionListItem.model_validate(_FakeExecution())
        assert "logs" not in item.model_fields
        assert item.model_dump().get("logs") is None

    def test_response_has_structured_logs(self):
        """Détail : journal structuré ``[{timestamp, message}]``."""
        response = ScheduledTaskExecutionResponse(
            **ScheduledTaskExecutionListItem.model_validate(
                _FakeExecution()
            ).model_dump(),
            logs=[
                ExecutionLogLine(
                    timestamp=datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc),
                    message="running",
                )
            ],
        )
        assert response.logs[0].message == "running"
        assert response.logs[0].timestamp.tzinfo is not None

    def test_no_sensitive_fields(self):
        """Aucun champ parameters/secret/token dans les schémas de réponse."""
        for schema in (
            ScheduledTaskExecutionListItem,
            ScheduledTaskExecutionResponse,
            ManualRunResponse,
        ):
            field_names = set(schema.model_fields)
            assert "parameters" not in field_names
            assert "secrets" not in field_names
            assert "token" not in field_names
            assert "password" not in field_names

    def test_manual_run_response(self):
        payload = ManualRunResponse(execution_id="exec-42")
        assert payload.status == "queued"
        assert payload.triggered_by == "manual"


class TestOrmDeserialization:
    def test_model_validate_from_realistic_fixture(self):
        item = ScheduledTaskExecutionListItem.model_validate(_FakeExecution())
        assert item.id == "exec-1"
        assert item.status == "success"
        assert item.duration_seconds == 60.0
        assert item.started_at is not None

    def test_model_validate_minimal_running_row(self):
        item = ScheduledTaskExecutionListItem.model_validate(
            _FakeExecution(
                status="running",
                triggered_by="manual",
                finished_at=None,
                duration_seconds=None,
            )
        )
        assert item.finished_at is None
        assert item.duration_seconds is None
