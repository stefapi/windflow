"""Tests ``DeploymentEventsService.emit_status_change`` (STORY-162, T4 — AC 3)
et ``emit_progress_update`` (STORY-163, T4 — AC 3).

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

STORY-163 — ``emit_progress_update`` :

- broadcast **direct** via ``broadcast_deployment_progress`` (mock) avec
  payload **snake_case exact** : ``deployment_id``, ``progress``,
  ``current_step``, ``total_steps`` (+ ``step`` compat logs internes) —
  cohérence avec ``frontend/src/types/websocket.ts`` ;
- échec du broadcast → aucune exception propagée (best-effort) ;
- payload sans secret (rules 40).

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
from unittest.mock import AsyncMock
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


# ===========================================================================
# STORY-163 (T4/AC 3) — emit_progress_update : transport WS direct
# ===========================================================================


async def test_emit_progress_update_broadcasts_snake_case_payload(mocker):
    """emit_progress_update → broadcast appelé avec le contrat exact (AC 3)."""
    broadcast = mocker.patch(
        "app.websocket.broadcasting.broadcast_deployment_progress",
        new_callable=AsyncMock,
    )
    service = DeploymentEventsService(event_bus=InMemoryEventBus())

    await service.emit_progress_update(
        deployment_id=uuid4(),
        progress=45,
        step="validated",
        total_steps=7,
        user_id=uuid4(),
    )

    broadcast.assert_awaited_once()
    kwargs = broadcast.await_args.kwargs
    # Contrat snake_case exact du frontend (types/websocket.ts l.33-38) :
    # les données de progression partent dans le corps du message, le
    # broadcast ajoute deployment_id/progress/current_step/step.
    assert kwargs["progress"] == 45
    assert kwargs["step"] == "validated"
    assert kwargs["total_steps"] == 7


async def test_emit_progress_update_payload_has_no_secrets(mocker):
    """Payload limité à ID/étapes/progression — aucun secret (rules 40)."""
    broadcast = mocker.patch(
        "app.websocket.broadcasting.broadcast_deployment_progress",
        new_callable=AsyncMock,
    )
    service = DeploymentEventsService(event_bus=InMemoryEventBus())
    deployment_id = uuid4()

    # Contexte sensible imaginaire autour de l'appel — seuls les champs
    # explicites de la signature peuvent partir dans le message.
    await service.emit_progress_update(
        deployment_id=deployment_id,
        progress=75,
        step="deploying",
        total_steps=7,
    )

    broadcast.assert_awaited_once()
    kwargs = broadcast.await_args.kwargs
    serialized = str(kwargs)
    assert "password" not in serialized.lower()
    assert "secret" not in serialized.lower()
    assert "token" not in serialized.lower()
    assert "api_key" not in serialized.lower()


async def test_emit_progress_update_never_raises_on_broadcast_failure(mocker):
    """Échec du broadcast → loggué, jamais propagé (best-effort)."""
    mocker.patch(
        "app.websocket.broadcasting.broadcast_deployment_progress",
        new_callable=AsyncMock,
        side_effect=ConnectionError("ws down"),
    )
    service = DeploymentEventsService(event_bus=InMemoryEventBus())

    # Aucune exception — le pipeline de déploiement ne doit pas échouer
    # pour une notification.
    await service.emit_progress_update(
        deployment_id=uuid4(),
        progress=100,
        step="completed",
        total_steps=7,
    )


async def test_emit_progress_update_passes_user_id_as_string(mocker):
    """user_id UUID → string dans le routage du broadcast."""
    broadcast = mocker.patch(
        "app.websocket.broadcasting.broadcast_deployment_progress",
        new_callable=AsyncMock,
    )
    service = DeploymentEventsService(event_bus=InMemoryEventBus())
    user_id = uuid4()

    await service.emit_progress_update(
        deployment_id=uuid4(),
        progress=20,
        step="mode_determined",
        total_steps=9,
        user_id=user_id,
    )

    assert broadcast.await_args.kwargs["user_id"] == str(user_id)
    # Sans user_id → None (pas de broadcast utilisateur)
    await service.emit_progress_update(
        deployment_id=uuid4(),
        progress=35,
        step="variables_substituted",
        total_steps=9,
    )
    assert broadcast.await_args.kwargs["user_id"] is None


async def test_broadcast_deployment_progress_message_contract():
    """Le message émis par broadcasting expose bien le contrat snake_case."""
    from unittest.mock import AsyncMock as _AsyncMock
    from unittest.mock import patch

    from app.websocket.broadcasting import broadcast_deployment_progress

    with patch(
        "app.websocket.broadcasting._broadcast_deployment_event",
        new_callable=_AsyncMock,
    ) as dispatch:
        await broadcast_deployment_progress(
            deployment_id="dep-1",
            progress=45,
            step="validated",
            total_steps=7,
        )

    dispatch.assert_awaited_once()
    args = dispatch.await_args.args
    payload = args[2]
    assert payload["deployment_id"] == "dep-1"
    assert payload["progress"] == 45
    assert payload["current_step"] == "validated"
    assert payload["step"] == "validated"  # compat logs internes
    assert payload["total_steps"] == 7
    # Plus aucun camelCase (correction sans période de compatibilité).
    assert "deploymentId" not in payload


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
