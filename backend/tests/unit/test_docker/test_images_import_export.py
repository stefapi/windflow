"""
Tests unitaires pour les endpoints import/export d'images (load/save).

STORY-031.1 : Backend — API Images enrichie, inspect et import/export.
Teste l'upload tar (load), le download tar (save), et les cas d'erreur.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.docker import router
from app.auth.dependencies import get_current_active_user


def _make_mock_user():
    """Crée un mock utilisateur authentifié."""
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_user.email = "test@example.com"
    mock_user.is_active = True
    return mock_user


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
    application.dependency_overrides[get_current_active_user] = lambda: _make_mock_user()
    return application


class TestLoadImage:
    """Tests pour l'endpoint POST /images/load."""

    @pytest.mark.asyncio
    async def test_load_image_returns_success(self, app):
        """Upload tar valide → 200, {"success": true, "message": "..."}."""
        mock_client = AsyncMock()
        mock_client.load_image = AsyncMock(return_value="Load complete")
        mock_client.close = AsyncMock()

        with patch(
            "app.api.v1.docker.get_docker_client", return_value=mock_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/v1/docker/images/load",
                    files={
                        "file": (
                            "image.tar",
                            b"\x00\x00\x00\x00fake_tar_content",
                            "application/x-tar",
                        )
                    },
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Load complete" in data["message"]

        # Vérifier que load_image a été appelé avec les bytes
        mock_client.load_image.assert_called_once()
        call_args = mock_client.load_image.call_args[0]
        assert len(call_args[0]) > 0  # tar_bytes non vide

    @pytest.mark.asyncio
    async def test_load_image_rejects_invalid_mime(self, app):
        """Upload avec content_type='text/plain' → HTTP 400."""
        mock_client = AsyncMock()

        with patch(
            "app.api.v1.docker.get_docker_client", return_value=mock_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/v1/docker/images/load",
                    files={
                        "file": (
                            "image.txt",
                            b"not a tar file",
                            "text/plain",
                        )
                    },
                )

        assert response.status_code == 400
        assert "non supporté" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_load_image_handles_docker_error(self, app):
        """Erreur Docker pendant le load → HTTP 500."""
        mock_client = AsyncMock()
        mock_client.load_image = AsyncMock(
            side_effect=Exception("Docker daemon error")
        )
        mock_client.close = AsyncMock()

        with patch(
            "app.api.v1.docker.get_docker_client", return_value=mock_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/v1/docker/images/load",
                    files={
                        "file": (
                            "image.tar",
                            b"fake_tar",
                            "application/x-tar",
                        )
                    },
                )

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_load_image_accepts_octet_stream(self, app):
        """Upload avec content_type='application/octet-stream' → accepté."""
        mock_client = AsyncMock()
        mock_client.load_image = AsyncMock(return_value="Load complete")
        mock_client.close = AsyncMock()

        with patch(
            "app.api.v1.docker.get_docker_client", return_value=mock_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/v1/docker/images/load",
                    files={
                        "file": (
                            "image.tar",
                            b"fake_tar_content",
                            "application/octet-stream",
                        )
                    },
                )

        assert response.status_code == 200
        assert response.json()["success"] is True


class TestSaveImage:
    """Tests pour l'endpoint GET /images/{image_id}/save."""

    @pytest.mark.asyncio
    async def test_save_image_returns_tar(self, app):
        """Download image → Content-Type: application/x-tar, contenu binaire."""
        fake_tar = b"\x00\x00\x00\x00fake_tar_binary_content"

        mock_client = AsyncMock()
        mock_client.save_image = AsyncMock(return_value=fake_tar)
        mock_client.close = AsyncMock()

        with patch(
            "app.api.v1.docker.get_docker_client", return_value=mock_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get(
                    "/api/v1/docker/images/nginx:latest/save"
                )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-tar"
        assert "attachment" in response.headers.get("content-disposition", "")
        assert "nginx:latest.tar" in response.headers.get(
            "content-disposition", ""
        )
        assert response.content == fake_tar

        mock_client.save_image.assert_called_once_with("nginx:latest")
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_image_returns_404_when_not_found(self, app):
        """Image inexistante → HTTP 404."""
        mock_client = AsyncMock()
        mock_client.save_image = AsyncMock(
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
                    "/api/v1/docker/images/nonexistent:latest/save"
                )

        assert response.status_code == 404
        assert "non trouvée" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_save_image_handles_docker_error(self, app):
        """Erreur Docker générique → HTTP 500."""
        mock_client = AsyncMock()
        mock_client.save_image = AsyncMock(
            side_effect=Exception("Docker daemon error")
        )
        mock_client.close = AsyncMock()

        with patch(
            "app.api.v1.docker.get_docker_client", return_value=mock_client
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get(
                    "/api/v1/docker/images/nginx:latest/save"
                )

        assert response.status_code == 500
        assert "Erreur" in response.json()["detail"]
