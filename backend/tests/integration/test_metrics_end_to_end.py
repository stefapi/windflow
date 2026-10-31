"""Tests d'intégration bout-en-bout de l'exposition Prometheus (STORY-172 — AC 1).

App réelle (fixture ``client`` du conftest — DB de test, ``ASGITransport``) :
requêtes HTTP + transitions de déploiement via ``update_status`` + exécution
scheduler → ``GET /api/v1/metrics`` **sans auth** contient AU MOINS une
série de chaque famille (``windflow_http_*``, ``windflow_deployments_*``,
``windflow_scheduler_executions_*``) — l'AC 1 mot pour mot.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.metrics import record_scheduler_execution
from app.models.deployment import Deployment, DeploymentStatus
from app.models.host import Host
from app.models.organization import Organization
from app.models.stack import Stack
from app.services.deployment_service import DeploymentService


@pytest.fixture
def prometheus_enabled():
    original = settings.prometheus_enabled
    settings.prometheus_enabled = True
    yield
    settings.prometheus_enabled = original


@pytest.fixture
def prometheus_disabled():
    original = settings.prometheus_enabled
    settings.prometheus_enabled = False
    yield
    settings.prometheus_enabled = original


async def _seed_and_transition_deployment(
    db_session: AsyncSession,
) -> Deployment:
    """Déploiement complet PENDING → DEPLOYING → RUNNING via update_status."""
    org = Organization(name="E2E Metrics Org", slug="e2e-metrics-org")
    db_session.add(org)
    await db_session.flush()
    stack = Stack(
        name="e2e-metrics-stack",
        template={"image": "nginx"},
        variables={},
        organization_id=org.id,
        version="1.0.0",
    )
    host = Host(
        name="e2e-metrics-host",
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
        name="e2e-metrics-deployment",
        config={},
        variables={},
        status=DeploymentStatus.PENDING,
    )
    db_session.add(deployment)
    await db_session.commit()
    await db_session.refresh(deployment)

    await DeploymentService.update_status(
        db_session, deployment.id, DeploymentStatus.DEPLOYING
    )
    await DeploymentService.update_status(
        db_session, deployment.id, DeploymentStatus.RUNNING
    )
    return deployment


async def test_full_flow_exposes_all_families(
    client: AsyncClient, db_session, prometheus_enabled
):
    """AC 1 : trafic + déploiement + tâche scheduler → toutes les familles exposées."""
    # 1) Trafic HTTP réel (login + lecture — le login échoue éventuellement,
    #    seule la requête comptée importe).
    await client.post(
        "/api/v1/auth/login", data={"username": "admin", "password": "wrong"}
    )
    await client.get("/api/v1/system/health")

    # 2) Déploiement complet (transitions PENDING→DEPLOYING→RUNNING).
    await _seed_and_transition_deployment(db_session)

    # 3) Une exécution scheduler simulée à la source (helper exact du moteur).
    record_scheduler_execution("success", 0.25)

    # 4) Le scrape expose au moins une série de chaque famille — SANS auth.
    client.headers.pop("Authorization", None)
    response = await client.get("/api/v1/metrics")

    assert response.status_code == 200
    body = response.text
    assert "windflow_http_requests_total{" in body
    assert "windflow_deployments_total{" in body
    assert "windflow_scheduler_executions_total{" in body
    # Les durées business sont observées (transition terminale + exécution).
    assert "windflow_deployment_duration_seconds_count" in body
    assert "windflow_scheduler_execution_duration_seconds_count" in body


async def test_prometheus_disabled_hides_endpoint_integration(
    client: AsyncClient, prometheus_disabled
):
    """AC 2 (parité unitaire) : flag off → 404 au niveau app."""
    response = await client.get("/api/v1/metrics")
    assert response.status_code == 404
