"""
Tests unitaires pour l'enrichissement de la liste d'images avec in_use/containers_count.

STORY-031.1 : Backend — API Images enrichie, inspect et import/export.
Teste le cross-referencement images ↔ containers pour l'indicateur d'utilisation.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.docker import router
from app.auth.dependencies import get_current_active_user
from app.auth.rbac import require_admin, require_operator, require_viewer
from app.core.exceptions import WindFlowException
from app.middleware.error_handler import windflow_exception_handler


def _make_mock_user():
    """Crée un mock utilisateur authentifié."""
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_user.email = "test@example.com"
    mock_user.is_active = True
    return mock_user


def _make_image_info(image_id: str, repo_tags=None):
    """Crée un mock ImageInfo."""
    img = MagicMock()
    img.id = image_id  # Déjà tronqué à 12 chars sans prefix sha256:
    img.repo_tags = repo_tags or [f"{image_id}:latest"]
    img.repo_digests = []
    img.created = datetime(2025, 1, 15, 10, 30, 0)
    img.size = 187500000
    img.virtual_size = 200000000
    img.labels = {}
    return img


def _make_container_info(image_id: str):
    """Crée un mock ContainerInfo avec image_id au format Docker complet."""
    container = MagicMock()
    container.id = "container123456"
    container.name = "test-container"
    container.image = "nginx:latest"
    # ContainerInfo.image_id est au format complet "sha256:abc123..."
    container.image_id = f"sha256:{image_id}abcdef1234567890"
    container.command = "nginx"
    container.created = datetime(2025, 1, 15, 10, 30, 0)
    container.state = "running"
    container.status = "Up 2 hours"
    container.ports = []
    container.labels = {}
    container.networks = ["bridge"]
    container.mounts = []
    container.restart_count = 0
    return container


@pytest.fixture
def app():
    """Crée une application FastAPI de test."""
    application = FastAPI()
    # STORY-127 : exceptions typées → handler global requis
    application.add_exception_handler(WindFlowException, windflow_exception_handler)
    application.include_router(router, prefix="/api/v1/docker")
    application.dependency_overrides[get_current_active_user] = (
        lambda: _make_mock_user()
    )
    # STORY-122.2 : routes Docker protégées par require_* — délégation au
    # même provider (mini-app sans DB ; RBAC couvert par test_docker_rbac.py)
    for _rbac_dep in (require_viewer, require_operator, require_admin):
        application.dependency_overrides[_rbac_dep] = lambda: _make_mock_user()
    return application


class TestListImagesInUse:
    """Tests pour l'enrichissement in_use de la liste d'images."""

    @pytest.mark.asyncio
    async def test_list_images_marks_in_use_correctly(self, app):
        """Image utilisée par un container → in_use=true, containers_count=1."""
        img = _make_image_info("abc123def456", ["nginx:latest"])
        container = _make_container_info("abc123def456")

        mock_client = AsyncMock()
        mock_client.list_images = AsyncMock(return_value=[img])
        mock_client.list_containers = AsyncMock(return_value=[container])
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/images")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        image = data[0]
        assert image["inUse"] is True
        assert image["containersCount"] == 1

    @pytest.mark.asyncio
    async def test_list_images_marks_unused_correctly(self, app):
        """Image non utilisée → in_use=false, containers_count=0."""
        img = _make_image_info("abc123def456", ["nginx:latest"])

        mock_client = AsyncMock()
        mock_client.list_images = AsyncMock(return_value=[img])
        mock_client.list_containers = AsyncMock(return_value=[])
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/images")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        image = data[0]
        assert image["inUse"] is False
        assert image["containersCount"] == 0

    @pytest.mark.asyncio
    async def test_list_images_mixed_usage(self, app):
        """3 images dont 2 utilisées → vérifier les counts respectifs."""
        img1 = _make_image_info("abc111111111", ["nginx:latest"])
        img2 = _make_image_info("def222222222", ["redis:latest"])
        img3 = _make_image_info("ghi333333333", ["postgres:latest"])

        # 2 containers utilisent img1, 1 container utilise img2, img3 non utilisée
        c1 = _make_container_info("abc111111111")
        c2 = _make_container_info("abc111111111")
        c3 = _make_container_info("def222222222")

        mock_client = AsyncMock()
        mock_client.list_images = AsyncMock(return_value=[img1, img2, img3])
        mock_client.list_containers = AsyncMock(return_value=[c1, c2, c3])
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/images")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # img1 : 2 containers
        img1_data = next(i for i in data if i["id"] == "abc111111111")
        assert img1_data["inUse"] is True
        assert img1_data["containersCount"] == 2

        # img2 : 1 container
        img2_data = next(i for i in data if i["id"] == "def222222222")
        assert img2_data["inUse"] is True
        assert img2_data["containersCount"] == 1

        # img3 : 0 container
        img3_data = next(i for i in data if i["id"] == "ghi333333333")
        assert img3_data["inUse"] is False
        assert img3_data["containersCount"] == 0

    @pytest.mark.asyncio
    async def test_list_images_id_normalization(self, app):
        """Vérifie que ContainerInfo.image_id='sha256:abc...' matche ImageInfo.id='abc...'."""
        # ImageInfo.id est tronqué à 12 chars sans prefix
        img = _make_image_info("abc123def456", ["nginx:latest"])

        # ContainerInfo.image_id est au format complet "sha256:abc123def456..."
        # La normalisation doit extraire "abc123def456" (12 chars sans sha256:)
        container = MagicMock()
        container.image_id = "sha256:abc123def456789012345678901234567890abcdef"
        # Après normalisation : "abc123def456" → match img.id

        mock_client = AsyncMock()
        mock_client.list_images = AsyncMock(return_value=[img])
        mock_client.list_containers = AsyncMock(return_value=[container])
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/images")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["inUse"] is True
        assert data[0]["containersCount"] == 1

    @pytest.mark.asyncio
    async def test_list_images_empty(self, app):
        """Liste vide d'images → réponse vide."""
        mock_client = AsyncMock()
        mock_client.list_images = AsyncMock(return_value=[])
        mock_client.list_containers = AsyncMock(return_value=[])
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/images")

        assert response.status_code == 200
        assert response.json() == []
