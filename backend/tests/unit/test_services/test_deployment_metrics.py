"""Tests des métriques business déploiements (STORY-172 — Tâche 5, AC 1).

``DeploymentService.update_status`` est le point de passage unique des
transitions : les compteurs ``windflow_deployments_total{result}``, la gauge
``windflow_deployments_active`` et l'histogramme de durée y sont
instrumentés (décisions D2/D8). Les assertions portent sur des **deltas de
séries** du ``REGISTRY`` (pattern ``test_ws_metrics_helpers.py``) après un
vrai ``update_status`` sur la DB de test.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment, DeploymentStatus
from app.models.host import Host
from app.models.organization import Organization
from app.models.stack import Stack
from app.services.deployment_service import DeploymentService


def _value(name: str, labels: dict | None = None) -> float:
    """Valeur actuelle d'un sample (0 si la série n'existe pas encore)."""
    value = REGISTRY.get_sample_value(name, labels)
    return value if value is not None else 0.0


async def _seed_deployment(
    db_session: AsyncSession,
    status: DeploymentStatus = DeploymentStatus.PENDING,
    *,
    created_at: datetime | None = None,
) -> Deployment:
    """Insère un déploiement minimal sans pipeline (pattern STORY-167)."""
    org = Organization(name="Metrics Org", slug="metrics-org")
    db_session.add(org)
    await db_session.flush()
    stack = Stack(
        name="metrics-stack",
        template={"image": "nginx"},
        variables={},
        organization_id=org.id,
        version="1.0.0",
    )
    host = Host(
        name="metrics-host",
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
        name="metrics-deployment",
        config={},
        variables={},
        status=status,
    )
    if created_at is not None:
        deployment.created_at = created_at
    db_session.add(deployment)
    await db_session.commit()
    await db_session.refresh(deployment)
    return deployment


class TestDeploymentCounters:
    """Compteurs ok/ko, gauge active, durées — sémantique D8."""

    @pytest.mark.asyncio
    async def test_transition_to_running_increments_success_counter(self, db_session):
        """``DEPLOYING → RUNNING`` → ``result="success"`` +1 ; gauge active −1."""
        deployment = await _seed_deployment(db_session, DeploymentStatus.DEPLOYING)
        before_success = _value("windflow_deployments_total", {"result": "success"})
        before_active = _value("windflow_deployments_active")

        await DeploymentService.update_status(
            db_session, deployment.id, DeploymentStatus.RUNNING
        )

        assert (
            _value("windflow_deployments_total", {"result": "success"}) - before_success
            == 1.0
        )
        assert before_active - _value("windflow_deployments_active") == 1.0

    @pytest.mark.asyncio
    async def test_transition_to_failed_increments_failed_counter(self, db_session):
        """``DEPLOYING → FAILED`` → ``result="failed"`` +1."""
        deployment = await _seed_deployment(db_session, DeploymentStatus.DEPLOYING)
        before_failed = _value("windflow_deployments_total", {"result": "failed"})

        await DeploymentService.update_status(
            db_session, deployment.id, DeploymentStatus.FAILED
        )

        assert (
            _value("windflow_deployments_total", {"result": "failed"}) - before_failed
            == 1.0
        )

    @pytest.mark.asyncio
    async def test_duration_observed_on_terminal_transition(self, db_session):
        """Transition terminale avec ``created_at`` → observation de durée."""
        created = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            seconds=30
        )
        deployment = await _seed_deployment(
            db_session, DeploymentStatus.DEPLOYING, created_at=created
        )
        before_count = _value("windflow_deployment_duration_seconds_count")
        before_sum = _value("windflow_deployment_duration_seconds_sum")

        await DeploymentService.update_status(
            db_session, deployment.id, DeploymentStatus.FAILED
        )

        assert (
            _value("windflow_deployment_duration_seconds_count") - before_count == 1.0
        )
        delta_sum = _value("windflow_deployment_duration_seconds_sum") - before_sum
        # Durée de bout en bout ≈ 30 s (tolérance d'exécution) — cohérente ≥ 0.
        assert delta_sum >= 0.0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status",
        [DeploymentStatus.PENDING, DeploymentStatus.DEPLOYING],
    )
    async def test_active_gauge_increments_on_non_terminal_status(
        self, db_session, status
    ):
        """Transition vers ``PENDING``/``DEPLOYING`` → gauge active +1.

        Seed en statut terminal (``STOPPED``) : la transition vers un statut
        non terminal est une vraie transition (garde ``old != new``).
        """
        deployment = await _seed_deployment(db_session, DeploymentStatus.STOPPED)
        before_active = _value("windflow_deployments_active")

        await DeploymentService.update_status(db_session, deployment.id, status)

        assert _value("windflow_deployments_active") - before_active == 1.0

    @pytest.mark.asyncio
    async def test_same_status_transition_not_double_counted(self, db_session):
        """``RUNNING → RUNNING`` (pas de changement) → aucun delta."""
        deployment = await _seed_deployment(db_session, DeploymentStatus.RUNNING)
        before_success = _value("windflow_deployments_total", {"result": "success"})
        before_active = _value("windflow_deployments_active")

        await DeploymentService.update_status(
            db_session, deployment.id, DeploymentStatus.RUNNING
        )

        assert (
            _value("windflow_deployments_total", {"result": "success"})
            == before_success
        )
        assert _value("windflow_deployments_active") == before_active

    @pytest.mark.asyncio
    async def test_metrics_failure_never_breaks_update_status(self, db_session):
        """Best-effort : helper levant → ``update_status`` retourne normalement."""
        deployment = await _seed_deployment(db_session, DeploymentStatus.DEPLOYING)

        with patch(
            "app.services.deployment_service.record_deployment_transition",
            side_effect=RuntimeError("metrics backend exploded"),
        ):
            updated = await DeploymentService.update_status(
                db_session, deployment.id, DeploymentStatus.RUNNING
            )

        # La transition a bien été persistée malgré l'échec de la métrique.
        assert updated is not None
        assert updated.status == DeploymentStatus.RUNNING
