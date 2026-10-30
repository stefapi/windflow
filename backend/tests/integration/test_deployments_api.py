"""Tests d'intégration pour les endpoints de déploiements."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from tests.conftest import unwrap

from app.models.stack import Stack
from app.models.host import Host

ORCH_PATCH = (
    "app.services.deployment_orchestrator.DeploymentOrchestrator.start_deployment"
)


@pytest.mark.asyncio
class TestDeploymentsAPI:
    """Tests d'intégration pour l'API de déploiements."""

    async def test_create_deployment(
        self, authenticated_client: AsyncClient, test_stack: Stack, test_target: Host
    ):
        """Test de création d'un déploiement via API."""
        with patch(ORCH_PATCH, new_callable=AsyncMock, return_value=None):
            response = await authenticated_client.post(
                "/api/v1/deployments",
                json={
                    "name": "API Test Deployment",
                    "stack_id": test_stack.id,
                    "target_id": test_target.id,
                    "config": {
                        "version": "3.8",
                        "services": {"web": {"image": "nginx:latest"}},
                    },
                    "variables": {"port": 8080},
                },
            )
        assert response.status_code == 201
        data = unwrap(response)
        assert data["name"] == "API Test Deployment"
        assert data["stack_id"] == test_stack.id
        assert data["target_id"] == test_target.id
        assert "id" in data

    async def test_get_deployment_by_id(
        self, authenticated_client: AsyncClient, test_stack: Stack, test_target: Host
    ):
        """Test de récupération d'un déploiement par ID."""
        with patch(ORCH_PATCH, new_callable=AsyncMock, return_value=None):
            create_response = await authenticated_client.post(
                "/api/v1/deployments",
                json={
                    "name": "Deployment to Get",
                    "stack_id": test_stack.id,
                    "target_id": test_target.id,
                    "config": {"test": "config"},
                    "variables": {},
                },
            )
        deployment_id = unwrap(create_response)["id"]

        response = await authenticated_client.get(
            f"/api/v1/deployments/{deployment_id}"
        )
        assert response.status_code == 200
        data = unwrap(response)
        assert data["id"] == deployment_id
        assert data["name"] == "Deployment to Get"

    async def test_get_deployment_not_found(self, authenticated_client: AsyncClient):
        """Test de récupération d'un déploiement inexistant."""
        fake_uuid = str(uuid.uuid4())
        response = await authenticated_client.get(f"/api/v1/deployments/{fake_uuid}")
        assert response.status_code == 404

    async def test_list_deployments(
        self, authenticated_client: AsyncClient, test_stack: Stack, test_target: Host
    ):
        """Test de listage des déploiements (contrat paginé STORY-128)."""
        with patch(ORCH_PATCH, new_callable=AsyncMock, return_value=None):
            for i in range(3):
                await authenticated_client.post(
                    "/api/v1/deployments",
                    json={
                        "name": f"Deployment {i}",
                        "stack_id": test_stack.id,
                        "target_id": test_target.id,
                        "config": {"index": i},
                        "variables": {},
                    },
                )

        response = await authenticated_client.get("/api/v1/deployments")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body["data"], list)
        assert len(body["data"]) >= 3
        assert body["pagination"]["total"] >= 3

    async def test_list_deployments_with_pagination(
        self, authenticated_client: AsyncClient, test_stack: Stack, test_target: Host
    ):
        """Test de listage avec pagination page/per_page (STORY-128)."""
        with patch(ORCH_PATCH, new_callable=AsyncMock, return_value=None):
            for i in range(5):
                await authenticated_client.post(
                    "/api/v1/deployments",
                    json={
                        "name": f"Paged Deployment {i}",
                        "stack_id": test_stack.id,
                        "target_id": test_target.id,
                        "config": {"index": i},
                        "variables": {},
                    },
                )

        response = await authenticated_client.get(
            "/api/v1/deployments?page=2&per_page=2"
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 2
        assert body["pagination"]["page"] == 2
        assert body["pagination"]["per_page"] == 2

    async def test_create_deployment_unauthenticated(
        self, client: AsyncClient, test_stack: Stack, test_target: Host
    ):
        """Test de création sans authentification."""
        response = await client.post(
            "/api/v1/deployments",
            json={
                "name": "Unauthorized Deployment",
                "stack_id": test_stack.id,
                "target_id": test_target.id,
                "config": {"test": "config"},
                "variables": {},
            },
        )
        assert response.status_code == 401

    async def test_create_deployment_invalid_data(
        self, authenticated_client: AsyncClient
    ):
        """Test de création avec données invalides."""
        response = await authenticated_client.post(
            "/api/v1/deployments",
            json={
                "name": "",
                "stack_id": "invalid",
                "target_id": "invalid",
                "config": {},
            },
        )
        assert response.status_code == 422

    async def test_deployment_cycle_emits_progress_messages(
        self,
        db_session,
        test_session_factory,
        test_organization,
        test_stack: Stack,
        test_target: Host,
    ):
        """STORY-163 (AC 3) : un cycle de déploiement réel (DB de test,
        Docker mocké) produit des messages DEPLOYMENT_PROGRESS via
        emit_progress_update — espion sur toute la durée du cycle."""
        from unittest.mock import MagicMock

        from app.enums.target import TargetType
        from app.models.deployment import Deployment, DeploymentStatus
        from app.tasks.background_tasks import deploy_stack_async

        # Déploiement réel en base (statut initial), stack docker réelle.
        test_stack.target_type = TargetType.DOCKER.value
        await db_session.flush()

        deployment = Deployment(
            name="progress-integration",
            stack_id=test_stack.id,
            target_id=test_target.id,
            organization_id=test_organization.id,
            status=DeploymentStatus.PENDING,
            config={},
            variables={},
        )
        db_session.add(deployment)
        # Commit : le pipeline ouvre ses propres sessions (factory), la
        # ligne doit être visible hors de la transaction courante.
        await db_session.commit()

        # Espion progress + Docker mocké (aucun daemon requis).
        progress_calls: list[dict] = []

        async def _spy_progress(**kwargs):
            progress_calls.append(kwargs)

        docker_service = MagicMock()
        docker_service.substitute_variables.return_value = {}
        docker_service.validate_container_config.return_value = (True, "")
        docker_service.deploy_container = AsyncMock(return_value=(True, "cid"))

        with patch(
            "app.database.AsyncSessionLocal", new=test_session_factory
        ), patch(
            "app.services.docker_service.DockerService", return_value=docker_service
        ), patch(
            "app.services.deployment_events.get_deployment_events",
            return_value=MagicMock(emit_progress_update=_spy_progress),
        ):
            result = await deploy_stack_async(
                deployment_id=deployment.id,
                stack_id=test_stack.id,
                target_id=test_target.id,
                user_id="integration-user",
                configuration={},
            )

        assert result["status"] == "success"
        # AC 3 bout-en-bout : messages DEPLOYMENT_PROGRESS produits
        # pendant le cycle, séquence monotone jusqu'à 100.
        progresses = [c["progress"] for c in progress_calls]
        assert progresses, "aucun DEPLOYMENT_PROGRESS émis pendant le cycle"
        assert progresses == sorted(progresses)
        assert progresses[-1] == 100
        steps = [c["step"] for c in progress_calls]
        assert "starting" in steps and "completed" in steps

    async def test_delete_deployment(
        self, authenticated_client: AsyncClient, test_stack: Stack, test_target: Host
    ):
        """Test de suppression d'un déploiement."""
        with patch(ORCH_PATCH, new_callable=AsyncMock, return_value=None):
            create_response = await authenticated_client.post(
                "/api/v1/deployments",
                json={
                    "name": "Deployment to Delete",
                    "stack_id": test_stack.id,
                    "target_id": test_target.id,
                    "config": {"test": "config"},
                    "variables": {},
                },
            )
        deployment_id = unwrap(create_response)["id"]

        response = await authenticated_client.delete(
            f"/api/v1/deployments/{deployment_id}"
        )
        assert response.status_code == 204

        # Le service marque le déploiement comme FAILED si la suppression
        # des ressources Docker échoue (pas de Docker en test),
        # donc le déploiement reste accessible mais avec un statut terminal
        get_response = await authenticated_client.get(
            f"/api/v1/deployments/{deployment_id}"
        )
        assert get_response.status_code in (200, 404)
        if get_response.status_code == 200:
            data = unwrap(get_response)
            assert data["status"] in ("failed", "stopped")
