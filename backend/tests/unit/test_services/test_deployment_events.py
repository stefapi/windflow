"""Tests ``DeploymentEventsService.emit_status_change`` (STORY-162, T4 — AC 3).

Familles :

- ``running`` (statut de succès du modèle) → ``DEPLOYMENT_SUCCEEDED``
  (``deployment.succeeded``) — **jamais** ``deployment.completed`` ;
- ``deploying`` → ``DEPLOYMENT_STARTED`` ; ``pending`` →
  ``DEPLOYMENT_CREATED`` ; ``failed`` → ``FAILED`` ; ``rolling_back`` →
  ``ROLLED_BACK`` ;
- statut sans événement canonique (``stopped``/inconnu) → **aucune
  émission** + warning (plus de fallback silencieux) ;
- payload : IDs/noms/statuts uniquement — assertion d'absence de
  secrets (règle 40).

Note de divergence (documentée dans la story) : l'enum
``DeploymentStatus`` n'a pas de membre ``success`` — le statut métier de
succès est ``running`` (déploiement actif), aligné avec l'audit
``deployment.succeeded`` émis sur transition vers RUNNING par
``deployment_service.update_status``.

Bus espion : instance ``InMemoryEventBus`` réelle + handler collecteur
(pattern ``test_scheduler_event_triggers.py``).
"""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from app.core.events import Event, EventType, InMemoryEventBus
from app.schemas.deployment import DeploymentStatus
from app.services.deployment_events import DeploymentEventsService


@pytest.fixture
def spy_bus():
    """Bus réel + handler collecteur sur tous les types de déploiement."""
    bus = InMemoryEventBus()
    collected: list[Event] = []

    async def collector(event: Event) -> None:
        collected.append(event)

    for member in (
        EventType.DEPLOYMENT_CREATED,
        EventType.DEPLOYMENT_STARTED,
        EventType.DEPLOYMENT_SUCCEEDED,
        EventType.DEPLOYMENT_FAILED,
        EventType.DEPLOYMENT_ROLLED_BACK,
    ):
        bus.subscribe(member, collector)
    return bus, collected


async def _emit_status(bus, status: DeploymentStatus) -> list[Event]:
    collected: list[Event] = []
    service = DeploymentEventsService(event_bus=bus)

    async def collector(event: Event) -> None:
        collected.append(event)

    for member in (
        EventType.DEPLOYMENT_CREATED,
        EventType.DEPLOYMENT_STARTED,
        EventType.DEPLOYMENT_SUCCEEDED,
        EventType.DEPLOYMENT_FAILED,
        EventType.DEPLOYMENT_ROLLED_BACK,
    ):
        bus.subscribe(member, collector)

    await service.emit_status_change(
        deployment_id=uuid4(),
        new_status=status,
        old_status=DeploymentStatus.DEPLOYING,
        user_id=uuid4(),
        additional_data={"name": "my-stack", "error_message": None},
    )
    return collected


async def test_running_emits_deployment_succeeded_never_completed(spy_bus):
    """running (succès métier) → deployment.succeeded — jamais completed."""
    bus, _ = spy_bus
    collected = await _emit_status(bus, DeploymentStatus.RUNNING)
    values = [e.event_type.value for e in collected]
    assert "deployment.succeeded" in values
    assert "deployment.completed" not in values
    # Le membre legacy n'existe plus dans le référentiel
    assert "DEPLOYMENT_COMPLETED" not in EventType.__members__
    assert "deployment.completed" not in {member.value for member in EventType}


async def test_deploying_emits_started(spy_bus):
    """deploying → DEPLOYMENT_STARTED."""
    bus, _ = spy_bus
    collected = await _emit_status(bus, DeploymentStatus.DEPLOYING)
    assert [e.event_type for e in collected] == [EventType.DEPLOYMENT_STARTED]


async def test_pending_failed_rolling_back_mappings(spy_bus):
    """pending → CREATED ; failed → FAILED ; rolling_back → ROLLED_BACK."""
    bus, _ = spy_bus
    cases = {
        DeploymentStatus.PENDING: EventType.DEPLOYMENT_CREATED,
        DeploymentStatus.FAILED: EventType.DEPLOYMENT_FAILED,
        DeploymentStatus.ROLLING_BACK: EventType.DEPLOYMENT_ROLLED_BACK,
    }
    for status, expected in cases.items():
        collected = await _emit_status(bus, status)
        assert [e.event_type for e in collected] == [expected]


async def test_stopped_and_unknown_status_emit_nothing_and_warn(spy_bus, caplog):
    """stopped/inconnu → aucune émission + warning explicite (AC 3)."""
    bus, _ = spy_bus
    collected: list[Event] = []
    service = DeploymentEventsService(event_bus=bus)

    async def collector(event: Event) -> None:
        collected.append(event)

    for member in (
        EventType.DEPLOYMENT_CREATED,
        EventType.DEPLOYMENT_STARTED,
        EventType.DEPLOYMENT_SUCCEEDED,
        EventType.DEPLOYMENT_FAILED,
        EventType.DEPLOYMENT_ROLLED_BACK,
    ):
        bus.subscribe(member, collector)

    with caplog.at_level(logging.WARNING):
        await service.emit_status_change(
            deployment_id=uuid4(),
            new_status=DeploymentStatus.STOPPED,
            old_status=DeploymentStatus.RUNNING,
            user_id=None,
        )
        await service.emit_status_change(
            deployment_id=uuid4(),
            new_status="mystery-status",  # type: ignore[arg-type]
            old_status=None,
            user_id=None,
        )

    assert collected == []  # plus de fallback silencieux
    warnings = [r.message for r in caplog.records if "no canonical event" in r.message]
    assert len(warnings) == 2


async def test_payload_contains_no_secrets(spy_bus):
    """Le payload ne contient que IDs/noms/statuts (règle 40)."""
    bus, _ = spy_bus
    deployment_id = uuid4()
    user_id = uuid4()
    service = DeploymentEventsService(event_bus=bus)
    collected: list[Event] = []

    async def collector(event: Event) -> None:
        collected.append(event)

    bus.subscribe(EventType.DEPLOYMENT_FAILED, collector)
    await service.emit_status_change(
        deployment_id=deployment_id,
        new_status=DeploymentStatus.FAILED,
        old_status=DeploymentStatus.DEPLOYING,
        user_id=user_id,
        additional_data={"name": "stack-x", "error_message": "boom"},
    )

    assert len(collected) == 1
    payload = collected[0].payload
    assert payload["deployment_id"] == str(deployment_id)
    assert payload["user_id"] == str(user_id)
    assert payload["name"] == "stack-x"
    # Absence de secrets / variables d'environnement
    flattened = str(payload).lower()
    for forbidden in ("password", "token", "secret", "api_key", "env"):
        assert forbidden not in flattened
