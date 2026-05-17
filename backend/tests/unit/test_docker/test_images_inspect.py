"""
Tests unitaires pour l'endpoint GET /api/v1/docker/images/{image_id}.

STORY-031.1 : Backend — API Images enrichie, inspect et import/export.
Teste l'inspect d'image : cas nominal, 404, erreur Docker.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.docker import router


def _make_mock_user():
    """Crée un mock utilisateur authentifié."""
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_user.email = "test@example.com"
    mock_user.is_active = True
    return mock_user


def _make_inspect_data():
    """Retourne un dict Docker inspect réaliste pour une image."""
    return {
        "Id": "sha256:abc123def456789012345678901234567890abcdef1234567890abcdef1234567",
        "RepoTags": ["nginx:latest", "nginx:1.25"],
        "RepoDigests": [
            "nginx@sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef12345678"
        ],
        "Created": "2025-01-15T10:30:00Z",
        "Size": 187500000,
        "VirtualSize": 200000000,
        "Architecture": "amd64",
        "Os": "linux",
        "Author": "NGINX Docker Maintainers",
        "DockerVersion": "24.0.7",
        "Config": {
            "Hostname": "",
            "Domainname": "",
            "User": "",
            "AttachStdin": False,
            "AttachStdout": False,
            "AttachStderr": False,
            "ExposedPorts": {"80/tcp": {}, "443/tcp": {}},
            "Tty": False,
            "OpenStdin": False,
            "StdinOnce": False,
            "Env": [
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "NGINX_VERSION=1.25.3",
            ],
            "Cmd": ["nginx", "-g", "daemon off;"],
            "Entrypoint": ["/docker-entrypoint.sh"],
            "Labels": {
                "maintainer": "NGINX Docker Maintainers <docker-maint@nginx.com>",
            },
            "Volumes": None,
            "WorkingDir": "",
            "OnBuild": None,
        },
    }


def _make_client_response_error(status_code: int) -> aiohttp.ClientResponseError:
    """Helper to create a ClientResponseError with given status."""
    return aiohttp.ClientResponseError(
        MagicMock(), (), status=status_code, message="Error"
    )


@pytest.fixture
def app():
    """Crée une application FastAPI de test."""
    application = FastAPI()
    application.include_router(router, prefix="/api/v1/docker")
    return application


class TestGetImageInspect:
    """Tests pour l'endpoint GET /images/{image_id}."""

    @pytest.mark.asyncio
    async def test_get_image_returns_200_and_detail(self, app):
        """Cas nominal : inspect image retourne les détails complets."""
        mock_client = AsyncMock()
        mock_client.inspect_image = AsyncMock(return_value=_make_inspect_data())
        mock_client.close = AsyncMock()

        with patch(
            "app.api.v1.docker.get_docker_client", return_value=mock_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/images/nginx:latest")

        assert response.status_code == 200
        data = response.json()

        # Vérifier les champs principaux
        assert data["id"] == "abc123def456"
        assert data["architecture"] == "amd64"
        assert data["os"] == "linux"
        assert data["size"] == 187500000
        assert data["virtualSize"] == 200000000
        assert data["author"] == "NGINX Docker Maintainers"
        assert data["dockerVersion"] == "24.0.7"
        assert "nginx:latest" in data["repoTags"]
        assert "nginx:1.25" in data["repoTags"]
        assert len(data["repoDigests"]) == 1
        assert data["cmd"] == ["nginx", "-g", "daemon off;"]
        assert data["entrypoint"] == ["/docker-entrypoint.sh"]
        assert len(data["env"]) == 2
        assert "80/tcp" in data["exposedPorts"]
        assert "443/tcp" in data["exposedPorts"]
        assert data["labels"]["maintainer"] == (
            "NGINX Docker Maintainers <docker-maint@nginx.com>"
        )
        assert data["config"] is not None
        assert data["config"]["Cmd"] == ["nginx", "-g", "daemon off;"]

        mock_client.inspect_image.assert_called_once_with("nginx:latest")
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_image_returns_404_when_not_found(self, app):
        """Cas d'erreur : image inexistante retourne 404."""
        mock_client = AsyncMock()
        mock_client.inspect_image = AsyncMock(
            side_effect=_make_client_response_error(404)
        )
        mock_client.close = AsyncMock()

        with patch(
            "app.api.v1.docker.get_docker_client", return_value=mock_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get(
                    "/api/v1/docker/images/nonexistent:latest"
                )

        assert response.status_code == 404
        assert "non trouvée" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_image_handles_docker_error(self, app):
        """Cas d'erreur : erreur Docker générique retourne 500."""
        mock_client = AsyncMock()
        mock_client.inspect_image = AsyncMock(
            side_effect=Exception("Docker daemon error")
        )
        mock_client.close = AsyncMock()

        with patch(
            "app.api.v1.docker.get_docker_client", return_value=mock_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/images/nginx:latest")

        assert response.status_code == 500
        assert "Erreur" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_image_with_minimal_data(self, app):
        """Cas nominal : image avec données minimales (champs manquants)."""
        minimal_data = {
            "Id": "sha256:abc123def456",
            "Created": "2025-01-15T10:30:00Z",
            "Size": 1000,
        }

        mock_client = AsyncMock()
        mock_client.inspect_image = AsyncMock(return_value=minimal_data)
        mock_client.close = AsyncMock()

        with patch(
            "app.api.v1.docker.get_docker_client", return_value=mock_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/images/abc123def456")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "abc123def456"
        assert data["repoTags"] == []
        assert data["repoDigests"] == []
        assert data["architecture"] == ""
        assert data["os"] == ""
        assert data["cmd"] is None
        assert data["entrypoint"] is None
        assert data["env"] is None
        assert data["exposedPorts"] is None
        assert data["labels"] == {}
        assert data["config"] is None
