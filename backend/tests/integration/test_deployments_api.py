"""Tests d'intégration pour les endpoints de déploiements."""

import pytest
from httpx import AsyncClient

from app.models.stack import Stack
from app.models.target import Target


@pytest.mark.asyncio
class TestDeploymentsAPI:
    """Tests d'intégration pour l'API de déploiements."""

    async def test_create_deployment(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
        test_target: Target
    ):
        """Test de création d'un déploiement via API."""
        response = await authenticated_client.post(
            "/api/v1/deployments/",
            json={
                "name": "API Test Deployment",
                "stack_id": test_stack.id,
                "target_id": test_target.id,
                "config": {
                    "version": "3.8",
                    "services": {
                        "web": {"image": "nginx:latest"}
                    }
                },
                "variables": {"port": 8080}
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "API Test Deployment"
        assert data["stack_id"] == test_stack.id
        assert data["target_id"] == test_target.id
        assert "id" in data

    async def test_get_deployment_by_id(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
        test_target: Target
    ):
        """Test de récupération d'un déploiement par ID."""
        # Créer un déploiement
        create_response = await authenticated_client.post(
            "/api/v1/deployments/",
            json={
                "name": "Deployment to Get",
                "stack_id": test_stack.id,
                "target_id": test_target.id,
                "config": {"test": "config"},
                "variables": {}
            }
        )
        deployment_id = create_response.json()["id"]

        # Récupérer le déploiement
        response = await authenticated_client.get(
            f"/api/v1/deployments/{deployment_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == deployment_id
        assert data["name"] == "Deployment to Get"

    async def test_get_deployment_not_found(
        self,
        authenticated_client: AsyncClient
    ):
        """Test de récupération d'un déploiement inexistant."""
        response = await authenticated_client.get(
            "/api/v1/deployments/nonexistent-id"
        )

        assert response.status_code == 404

    async def test_list_deployments(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
        test_target: Target
    ):
        """Test de listage des déploiements."""
        # Créer plusieurs déploiements
        for i in range(3):
            await authenticated_client.post(
                "/api/v1/deployments/",
                json={
                    "name": f"Deployment {i}",
                    "stack_id": test_stack.id,
                    "target_id": test_target.id,
                    "config": {"index": i},
                    "variables": {}
                }
            )

        # Lister les déploiements
        response = await authenticated_client.get("/api/v1/deployments/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3

    async def test_list_deployments_with_pagination(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
        test_target: Target
    ):
        """Test de listage avec pagination."""
        # Créer 5 déploiements
        for i in range(5):
            await authenticated_client.post(
                "/api/v1/deployments/",
                json={
                    "name": f"Paged Deployment {i}",
                    "stack_id": test_stack.id,
                    "target_id": test_target.id,
                    "config": {"index": i},
                    "variables": {}
                }
            )

        # Tester pagination
        response = await authenticated_client.get(
            "/api/v1/deployments/?skip=1&limit=2"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    async def test_create_deployment_unauthenticated(
        self,
        client: AsyncClient,
        test_stack: Stack,
        test_target: Target
    ):
        """Test de création sans authentification."""
        response = await client.post(
            "/api/v1/deployments/",
            json={
                "name": "Unauthorized Deployment",
                "stack_id": test_stack.id,
                "target_id": test_target.id,
                "config": {"test": "config"},
                "variables": {}
            }
        )

        assert response.status_code == 401

    async def test_create_deployment_invalid_data(
        self,
        authenticated_client: AsyncClient
    ):
        """Test de création avec données invalides."""
        response = await authenticated_client.post(
            "/api/v1/deployments/",
            json={
                "name": "",  # Nom vide - invalide
                "stack_id": "invalid",
                "target_id": "invalid",
                "config": {}
            }
        )

        assert response.status_code == 422  # Validation error

    async def test_delete_deployment(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
        test_target: Target
    ):
        """Test de suppression d'un déploiement."""
        # Créer un déploiement
        create_response = await authenticated_client.post(
            "/api/v1/deployments/",
            json={
                "name": "Deployment to Delete",
                "stack_id": test_stack.id,
                "target_id": test_target.id,
                "config": {"test": "config"},
                "variables": {}
            }
        )
        deployment_id = create_response.json()["id"]

        # Supprimer le déploiement
        response = await authenticated_client.delete(
            f"/api/v1/deployments/{deployment_id}"
        )

        assert response.status_code == 200

        # Vérifier qu'il n'existe plus
        get_response = await authenticated_client.get(
            f"/api/v1/deployments/{deployment_id}"
        )
        assert get_response.status_code == 404
