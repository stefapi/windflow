"""Tests unitaires de la double écriture dans update_status (STORY-167 — Tâche 5).

AC 3 : à chaque appel de ``DeploymentService.update_status()``, un
``DeploymentEvent`` typé est inséré **dans la même transaction** que le
changement de statut, la colonne texte ``logs`` continuant d'être
appendée (payload brut). Mapping statut→event_type et préfixe→level
(décisions d'analyse 1), ``data`` sans aucune donnée sensible (rules 40),
échec d'insert ⇒ rollback du statut.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment, DeploymentStatus
from app.models.deployment_event import DeploymentEvent
from app.models.host import Host
from app.models.organization import Organization
from app.models.stack import Stack
from app.services.deployment_service import DeploymentService


async def _seed_deployment(
    db_session: AsyncSession, status: DeploymentStatus = DeploymentStatus.PENDING
) -> Deployment:
    """Insère un déploiement minimal sans pipeline (pattern 103.3)."""
    org = Organization(name="Events Org", slug="events-org")
    db_session.add(org)
    await db_session.flush()
    stack = Stack(
        name="events-stack",
        template={"image": "nginx"},
        variables={},
        organization_id=org.id,
        version="1.0.0",
    )
    host = Host(
        name="events-host",
        host="127.0.0.1",
        credentials={},
        organization_id=org.id,
    )
    db_session.add_all([stack, host])
    await db_session.flush()
    deployment = Deployment(
        stack_id=stack.id,
        host_id=host.id,
        organization_id=org.id,
        name="events-deployment",
        config={},
        variables={},
        status=status,
    )
    db_session.add(deployment)
    await db_session.commit()
    await db_session.refresh(deployment)
    return deployment


async def _events_of(db_session: AsyncSession, deployment_id: str) -> list:
    result = await db_session.execute(
        select(DeploymentEvent)
        .where(DeploymentEvent.deployment_id == deployment_id)
        .order_by(DeploymentEvent.created_at.asc())
    )
    return list(result.scalars().all())


class TestUpdateStatusDoubleWrite:
    """Un event inséré par appel, mappings décision 1, colonne logs intacte."""

    @pytest.mark.asyncio
    async def test_running_maps_to_success_event(self, db_session):
        deployment = await _seed_deployment(db_session)
        updated = await DeploymentService.update_status(
            db_session,
            deployment.id,
            DeploymentStatus.RUNNING,
            logs="[INFO] Container started",
        )
        assert updated is not None
        events = await _events_of(db_session, deployment.id)
        assert len(events) == 1
        assert events[0].event_type == "success"  # RUNNING → success (décision 1)
        assert events[0].level == "info"
        # Double écriture : la colonne texte logs toujours appendée.
        assert updated.logs == "[INFO] Container started"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status,expected_type",
        [
            (DeploymentStatus.DEPLOYING, "deploying"),
            (DeploymentStatus.PENDING, "deploying"),
            (DeploymentStatus.FAILED, "error"),
            (DeploymentStatus.ROLLING_BACK, "rollback"),
            (DeploymentStatus.STOPPED, "rollback"),  # annulation → rollback
        ],
    )
    async def test_status_to_event_type_mapping(
        self, db_session, status, expected_type
    ):
        deployment = await _seed_deployment(db_session)
        await DeploymentService.update_status(
            db_session, deployment.id, status, logs="[INFO] step"
        )
        events = await _events_of(db_session, deployment.id)
        assert len(events) == 1
        assert events[0].event_type == expected_type

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "message,expected_level",
        [
            ("[ERROR] boom", "error"),
            ("[SYSTEM] cancelled", "warning"),
            ("[INFO] ok", "info"),
            ("[SUCCESS] done", "info"),
            ("bare message", "info"),
        ],
    )
    async def test_prefix_to_level_mapping(self, db_session, message, expected_level):
        deployment = await _seed_deployment(db_session)
        await DeploymentService.update_status(
            db_session,
            deployment.id,
            DeploymentStatus.FAILED,
            logs=message,
        )
        events = await _events_of(db_session, deployment.id)
        assert events[0].level == expected_level

    @pytest.mark.asyncio
    async def test_one_event_per_call_sequence(self, db_session):
        """Un pipeline complet : un event par update_status, dans l'ordre."""
        deployment = await _seed_deployment(db_session)
        await DeploymentService.update_status(
            db_session, deployment.id, DeploymentStatus.DEPLOYING, logs="[INFO] start"
        )
        await DeploymentService.update_status(
            db_session,
            deployment.id,
            DeploymentStatus.RUNNING,
            logs="[SUCCESS] running",
        )
        await DeploymentService.update_status(
            db_session,
            deployment.id,
            DeploymentStatus.FAILED,
            error_message="[ERROR] crashed",
        )
        events = await _events_of(db_session, deployment.id)
        assert [event.event_type for event in events] == [
            "deploying",
            "success",
            "error",
        ]
        # Colonne texte : payload brut intégral (logs concaténés) ;
        # error_message alimente la colonne dédiée (comportement
        # existant inchangé — l'event porte lui aussi le message).
        deployment_row = await db_session.get(Deployment, deployment.id)
        assert deployment_row is not None
        assert "[INFO] start" in (deployment_row.logs or "")
        assert "[SUCCESS] running" in (deployment_row.logs or "")
        assert deployment_row.error_message == "[ERROR] crashed"
        assert events[2].message == "[ERROR] crashed"

    @pytest.mark.asyncio
    async def test_data_contains_statuses_no_sensitive_fields(self, db_session):
        """``data`` = identifiants/métriques uniquement — rules 40."""
        deployment = await _seed_deployment(db_session)
        await DeploymentService.update_status(
            db_session, deployment.id, DeploymentStatus.RUNNING, logs="[INFO] up"
        )
        events = await _events_of(db_session, deployment.id)
        data = events[0].data or {}
        assert data.get("old_status") == "pending"
        assert data.get("new_status") == "running"
        # Aucune clé sensible, jamais (liste blanche du store).
        for forbidden in ("variables", "configuration", "token", "password", "secret"):
            assert forbidden not in data

    @pytest.mark.asyncio
    async def test_insert_failure_rolls_back_status(self, db_session, monkeypatch):
        """Échec d'insert ⇒ rollback du statut (même transaction — AC 3)."""
        deployment = await _seed_deployment(db_session)
        deployment_id = deployment.id  # capturé avant rollback (pas de
        # lazy-load async sur attribut expiré après rollback).

        async def _boom(*args, **kwargs):
            raise RuntimeError("insert failed")

        monkeypatch.setattr(
            "app.services.deployment_event_store.DeploymentEventStore.append_event",
            _boom,
        )
        with pytest.raises(RuntimeError):
            await DeploymentService.update_status(
                db_session, deployment.id, DeploymentStatus.RUNNING
            )
        await db_session.rollback()

        # Ni le statut ni l'event n'ont été persistés.
        db_session.expire_all()
        deployment_row = await db_session.get(Deployment, deployment_id)
        assert deployment_row is not None
        assert deployment_row.status == DeploymentStatus.PENDING
        assert await _events_of(db_session, deployment_id) == []


# ── STORY-170.2 — event_data_extra (gate) + bus deployment.failed ──────────


class TestUpdateStatusEventDataExtra:
    """Paramètre ``event_data_extra`` : fusion dans le data de l'event."""

    @pytest.mark.asyncio
    async def test_extra_data_merged_in_event(self, db_session):
        """Les clés gate sont fusionnées dans le data de l'event STORY-167."""
        deployment = await _seed_deployment(db_session)
        await DeploymentService.update_status(
            db_session,
            deployment.id,
            DeploymentStatus.FAILED,
            error_message="gate refused",
            logs="[ERROR] Déploiement refusé par la gate du plugin plugin-a",
            event_data_extra={
                "code": "GATE_DENIED",
                "plugin": "plugin-a",
                "reason": "vulnerable image",
            },
        )
        events = await _events_of(db_session, deployment.id)
        data = events[-1].data or {}
        assert data.get("code") == "GATE_DENIED"
        assert data.get("plugin") == "plugin-a"
        assert data.get("reason") == "vulnerable image"
        assert data.get("new_status") == "failed"

    @pytest.mark.asyncio
    async def test_extra_data_none_keeps_default_payload(self, db_session):
        """Sans event_data_extra : payload identique au comportement 167."""
        deployment = await _seed_deployment(db_session)
        await DeploymentService.update_status(
            db_session, deployment.id, DeploymentStatus.FAILED, logs="[ERROR] x"
        )
        events = await _events_of(db_session, deployment.id)
        data = events[-1].data or {}
        assert "code" not in data and "plugin" not in data

    @pytest.mark.asyncio
    async def test_extra_data_sensitive_keys_filtered(self, db_session):
        """La liste blanche du store filtre toute clé hors périmètre."""
        deployment = await _seed_deployment(db_session)
        await DeploymentService.update_status(
            db_session,
            deployment.id,
            DeploymentStatus.FAILED,
            logs="[ERROR] x",
            event_data_extra={
                "code": "GATE_DENIED",
                "token": "should-not-persist",  # hors liste blanche
                "variables": {"SECRET": "no"},  # hors liste blanche
            },
        )
        events = await _events_of(db_session, deployment.id)
        data = events[-1].data or {}
        assert data.get("code") == "GATE_DENIED"
        assert "token" not in data
        assert "variables" not in data


class TestUpdateStatusDeploymentFailedBus:
    """Émission bus ``deployment.failed`` au passage FAILED (170.2 n°2)."""

    @pytest.mark.asyncio
    async def test_failed_transition_emits_deployment_failed(self, db_session):
        """Passage FAILED → événement canonique deployment.failed émis."""
        from unittest.mock import patch as _patch

        from app.core.events import EventType

        deployment = await _seed_deployment(
            db_session, status=DeploymentStatus.DEPLOYING
        )
        emitted: list = []

        class _Bus:
            async def emit(self, event_type, payload):
                emitted.append((event_type, payload))

        manager = type("M", (), {})()
        manager.event_bus = _Bus()

        with _patch(
            "app.services.deployment_events.get_deployment_events",
            return_value=manager,
        ):
            await DeploymentService.update_status(
                db_session,
                deployment.id,
                DeploymentStatus.FAILED,
                error_message="boom",
                event_data_extra={
                    "code": "GATE_DENIED",
                    "plugin": "plugin-a",
                    "reason": "vulnerable image",
                },
            )

        assert any(et == EventType.DEPLOYMENT_FAILED for et, _ in emitted)
        payload = next(p for et, p in emitted if et == EventType.DEPLOYMENT_FAILED)
        assert payload["deployment_id"] == str(deployment.id)
        assert payload["code"] == "GATE_DENIED"
        assert payload["plugin"] == "plugin-a"
        # Aucun secret dans le payload (rules 40).
        for forbidden in ("token", "password", "secret", "variables"):
            assert forbidden not in payload

    @pytest.mark.asyncio
    async def test_running_transition_does_not_emit_deployment_failed(self, db_session):
        """Le bus deployment.failed n'est émis QUE au passage FAILED."""
        from unittest.mock import patch as _patch

        from app.core.events import EventType

        deployment = await _seed_deployment(db_session)
        emitted: list = []

        class _Bus:
            async def emit(self, event_type, payload):
                emitted.append((event_type, payload))

        manager = type("M", (), {})()
        manager.event_bus = _Bus()

        with _patch(
            "app.services.deployment_events.get_deployment_events",
            return_value=manager,
        ):
            await DeploymentService.update_status(
                db_session, deployment.id, DeploymentStatus.RUNNING
            )

        assert all(et != EventType.DEPLOYMENT_FAILED for et, _ in emitted)

    @pytest.mark.asyncio
    async def test_bus_emission_failure_never_breaks_update(self, db_session):
        """Best-effort : un bus en erreur n'altère pas le passage FAILED."""
        from unittest.mock import patch as _patch

        deployment = await _seed_deployment(
            db_session, status=DeploymentStatus.DEPLOYING
        )

        class _BrokenBus:
            async def emit(self, event_type, payload):
                raise RuntimeError("bus down")

        manager = type("M", (), {})()
        manager.event_bus = _BrokenBus()

        with _patch(
            "app.services.deployment_events.get_deployment_events",
            return_value=manager,
        ):
            updated = await DeploymentService.update_status(
                db_session, deployment.id, DeploymentStatus.FAILED, logs="[ERROR] x"
            )

        assert updated is not None
        assert updated.status == DeploymentStatus.FAILED
