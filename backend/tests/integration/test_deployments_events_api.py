"""Tests d'intégration API — deployment_events bout-en-bout (STORY-167 — AC 2/3).

Parcours complet : création de déploiement → appels réels de
``DeploymentService.update_status`` (pipeline simulé, orchestrateur non
impliqué — pattern test_deployments_api) → events persistés à chaque
étape → ``GET /deployments/{id}/events`` paginé retourne le déroulé
complet dans l'ordre.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

from app.models.deployment import Deployment, DeploymentStatus
from app.models.host import Host
from app.models.organization import Organization
from app.models.stack import Stack
from app.models.user import User
from app.services.deployment_service import DeploymentService


async def _seed_base(db_session: AsyncSession, org: Organization) -> Deployment:
    """Stack + host + déploiement PENDING dans l'organisation donnée."""
    stack = Stack(
        name="e2e-stack",
        template={"image": "nginx"},
        variables={},
        organization_id=org.id,
        version="1.0.0",
    )
    host = Host(
        name="e2e-host",
        host="127.0.0.1",
        credentials={},
        organization_id=org.id,
    )
    db_session.add_all([stack, host])
    await db_session.commit()
    deployment = Deployment(
        stack_id=stack.id,
        host_id=host.id,
        organization_id=org.id,
        name="e2e-deployment",
        config={},
        variables={},
        status=DeploymentStatus.PENDING,
    )
    db_session.add(deployment)
    await db_session.commit()
    return deployment


class TestDeploymentEventsEndToEnd:
    """Pipeline simulé → events persistés → endpoint paginé complet."""

    @pytest.mark.asyncio
    async def test_pipeline_updates_materialize_events_endpoint(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization: Organization,
    ):
        """Le déroulé update_status ×3 = 3 events requêtables via l'API,
        dans l'ordre chronologique (deploying → success → error).

        test_superuser est déjà admin de test_organization (fixture
        conftest) — pas d'association supplémentaire à créer.
        """
        deployment = await _seed_base(db_session, test_organization)

        # Pipeline simulé : les transitions réelles du background task.
        await DeploymentService.update_status(
            db_session,
            deployment.id,
            DeploymentStatus.DEPLOYING,
            logs="[INFO] Starting deployment",
        )
        await DeploymentService.update_status(
            db_session,
            deployment.id,
            DeploymentStatus.RUNNING,
            logs="[SUCCESS] Container running",
        )
        await DeploymentService.update_status(
            db_session,
            deployment.id,
            DeploymentStatus.FAILED,
            error_message="[ERROR] Health check failed",
        )

        response = await client.get(f"/api/v1/deployments/{deployment.id}/events")
        assert response.status_code == 200, response.text
        # Format wire spec 09 : {"data": [...], "pagination": {...}}.
        body = response.json()
        items = body["data"]

        # Déroulé complet, ordre chronologique (AC 2).
        assert [item["event_type"] for item in items] == [
            "deploying",
            "success",
            "error",
        ]
        assert [item["level"] for item in items] == ["info", "info", "error"]
        # Chaque event porte le contrat complet (AC 2).
        for item in items:
            for field in ("id", "deployment_id", "event_type", "level", "created_at"):
                assert field in item
        assert body["pagination"]["total"] == 3

        # Les transitions sont visibles dans data (AC 3).
        assert items[1]["data"]["old_status"] == "deploying"
        assert items[1]["data"]["new_status"] == "running"

        # La colonne texte logs brute est toujours là (double écriture).
        deployment_row = await db_session.get(Deployment, deployment.id)
        assert deployment_row is not None
        assert "[INFO] Starting deployment" in (deployment_row.logs or "")

    @pytest.mark.asyncio
    async def test_endpoint_completes_logs_route(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization: Organization,
    ):
        """GET /logs (contrat inchangé) et GET /events coexistent : le
        payload texte brut reste accessible (non-régression AC 4)."""
        deployment = await _seed_base(db_session, test_organization)
        await DeploymentService.update_status(
            db_session,
            deployment.id,
            DeploymentStatus.RUNNING,
            logs="[INFO] up",
        )

        logs_response = await client.get(f"/api/v1/deployments/{deployment.id}/logs")
        assert logs_response.status_code == 200
        logs_body = unwrap(logs_response)
        assert logs_body["logs"] == "[INFO] up"

        events_response = await client.get(
            f"/api/v1/deployments/{deployment.id}/events"
        )
        assert events_response.status_code == 200
        assert events_response.json()["pagination"]["total"] == 1
