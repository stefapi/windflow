"""Tests unitaires des schémas Pydantic /schedules v2 (STORY-160.1, AC 2).

Validateurs sémantiques spec 17 — chaque rejet est un 422
``VALIDATION_ERROR`` :
- cron invalide (croniter) ;
- fuseau IANA inconnu (zoneinfo) ;
- action hors registre ;
- ``trigger_type='event'`` sans ``event_name`` ;
- ``event_name`` non canonique (∉ EventType spec 11) ;
- ``parameters`` invalides au regard du schéma de l'action ;
- champ legacy ``task_type`` rejeté (extra=forbid).

Nominaux : cron + event + timezone ``Europe/Paris``.
"""

import pytest
from pydantic import ValidationError

from app.schemas.scheduled_task import (
    ScheduledTaskCreate,
    ScheduledTaskResponse,
    ScheduledTaskUpdate,
)

VALID_BASE = {
    "name": "scan-hote",
    "action": "host.scan",
    "cron_expression": "0 3 * * *",
    "organization_id": "org-1",
    "parameters": {"target_id": "tgt-1"},
}


class TestCreateNominal:
    """Cas nominaux acceptés."""

    def test_cron_task_valid(self):
        task = ScheduledTaskCreate(**VALID_BASE)
        assert task.trigger_type == "cron"
        assert task.event_name is None
        assert task.error_policy == "ignore"  # défaut spec 17

    def test_cron_task_with_paris_timezone(self):
        task = ScheduledTaskCreate(**{**VALID_BASE, "timezone": "Europe/Paris"})
        assert task.timezone == "Europe/Paris"

    def test_event_task_valid(self):
        task = ScheduledTaskCreate(
            **{
                **VALID_BASE,
                "action": "notification.send",
                "trigger_type": "event",
                "event_name": "deployment.failed",
                "parameters": {"channel": "webhook", "message": "échec"},
            }
        )
        assert task.trigger_type == "event"
        assert task.event_name == "deployment.failed"

    def test_error_policy_retry_accepted(self):
        task = ScheduledTaskCreate(**{**VALID_BASE, "error_policy": "retry"})
        assert task.error_policy == "retry"

    def test_parameters_normalized_with_defaults(self):
        """Les paramètres sont normalisés par les défauts du schéma
        d'action (dry_run=True pour prune)."""
        task = ScheduledTaskCreate(
            **{
                **VALID_BASE,
                "action": "compute.docker.prune",
                "parameters": {"resource": "volumes"},
            }
        )
        assert task.parameters["dry_run"] is True


class TestCreateRejections:
    """Rejets 422 — validation sémantique spec 17."""

    def test_invalid_cron_rejected(self):
        with pytest.raises(ValidationError):
            ScheduledTaskCreate(**{**VALID_BASE, "cron_expression": "not-a-cron"})

    def test_cron_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            ScheduledTaskCreate(**{**VALID_BASE, "cron_expression": "99 * * * *"})

    def test_unknown_timezone_rejected(self):
        with pytest.raises(ValidationError):
            ScheduledTaskCreate(**{**VALID_BASE, "timezone": "Mars/Olympus"})

    def test_unknown_action_rejected(self):
        with pytest.raises(ValidationError):
            ScheduledTaskCreate(**{**VALID_BASE, "action": "nope.action"})

    def test_event_without_event_name_rejected(self):
        with pytest.raises(ValidationError):
            ScheduledTaskCreate(
                **{**VALID_BASE, "trigger_type": "event", "event_name": None}
            )

    def test_non_canonical_event_name_rejected(self):
        with pytest.raises(ValidationError):
            ScheduledTaskCreate(
                **{
                    **VALID_BASE,
                    "trigger_type": "event",
                    "event_name": "not.an.event",
                }
            )

    def test_invalid_parameters_rejected_by_action_schema(self):
        """resource 'networks' ∉ Literal['images','volumes'] → 422."""
        with pytest.raises(ValidationError):
            ScheduledTaskCreate(
                **{
                    **VALID_BASE,
                    "action": "compute.docker.prune",
                    "parameters": {"resource": "networks"},
                }
            )

    def test_legacy_task_type_rejected(self):
        """Le champ task_type (retiré migration 1321) est rejeté
        (extra=forbid) — pas de compat silencieuse."""
        with pytest.raises(ValidationError):
            ScheduledTaskCreate(**{**VALID_BASE, "task_type": "cleanup_logs"})

    def test_invalid_trigger_type_rejected(self):
        with pytest.raises(ValidationError):
            ScheduledTaskCreate(**{**VALID_BASE, "trigger_type": "webhook"})

    def test_invalid_error_policy_rejected(self):
        with pytest.raises(ValidationError):
            ScheduledTaskCreate(**{**VALID_BASE, "error_policy": "explode"})


class TestUpdateSchema:
    """Update partiel — même validation sur les champs fournis."""

    def test_partial_update_name_only(self):
        update = ScheduledTaskUpdate(name="renamed")
        assert update.name == "renamed"
        assert update.action is None  # champ non fourni

    def test_update_validates_cron(self):
        with pytest.raises(ValidationError):
            ScheduledTaskUpdate(cron_expression="bad-cron")

    def test_update_validates_action(self):
        with pytest.raises(ValidationError):
            ScheduledTaskUpdate(action="unknown.action")

    def test_update_validates_timezone(self):
        with pytest.raises(ValidationError):
            ScheduledTaskUpdate(timezone="Nowhere/City")

    def test_update_validates_event_consistency(self):
        with pytest.raises(ValidationError):
            ScheduledTaskUpdate(trigger_type="event")

    def test_update_validates_parameters_against_new_action(self):
        """Update action+parameters : validés ensemble (payload brut)."""
        update = ScheduledTaskUpdate(
            action="host.scan", parameters={"target_id": "tgt-9"}
        )
        assert update.parameters == {"target_id": "tgt-9"}
        with pytest.raises(ValidationError):
            ScheduledTaskUpdate(action="host.scan", parameters={})

    def test_update_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            ScheduledTaskUpdate(task_type="custom")


class TestResponseSchema:
    """Response — champs v2 exposés, sans champ sensible."""

    def test_response_carries_v2_fields(self):
        response = ScheduledTaskResponse(
            id="t-1",
            name="scan",
            action="host.scan",
            trigger_type="cron",
            event_name=None,
            timezone="Europe/Paris",
            error_policy="retry",
            cron_expression="0 3 * * *",
            parameters={"target_id": "tgt"},
            enabled=True,
            run_count=0,
            organization_id="org-1",
            created_at="2026-10-21T20:00:00",
            updated_at="2026-10-21T20:00:00",
        )
        dumped = response.model_dump()
        for field in (
            "action",
            "trigger_type",
            "event_name",
            "timezone",
            "error_policy",
        ):
            assert field in dumped
        # Le champ legacy n'existe plus dans les réponses.
        assert "task_type" not in dumped

    def test_response_model_fields_exclude_secrets(self):
        """Aucun champ sensible (password/token/secret) dans la réponse."""
        field_names = set(ScheduledTaskResponse.model_fields)
        for forbidden in ("password", "token", "secret", "credential"):
            assert not any(
                forbidden in name for name in field_names
            ), f"Champ sensible suspect : {forbidden}"
