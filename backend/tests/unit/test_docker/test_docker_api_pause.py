"""
Tests for Docker container pause/unpause API endpoints.
STORY-025: POST /docker/containers/{id}/pause and /unpause
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.docker import router
from app.services.docker_client_service import DockerClientService


@pytest.fixture
def app():
    """Create a minimal FastAPI app with Docker router."""
    _app = FastAPI()
    _app.include_router(router, prefix="/docker")
    return _app


@pytest.fixture
def mock_docker_client():
    """Create a mock DockerClientService."""
    client = DockerClientService()
    client.pause_container = AsyncMock()
    client.unpause_container = AsyncMock()
    client.close = AsyncMock()
    return client


def _make_client_response_error(status: int) -> aiohttp.ClientResponseError:
    """Helper to create a ClientResponseError with given status."""
    return aiohttp.ClientResponseError(
        MagicMock(), (), status=status, message="Error"
    )


class TestPauseContainer:
    """Tests for POST /docker/containers/{container_id}/pause."""

    @pytest.mark.asyncio
    async def test_pause_success(self, app, mock_docker_client):
        """Test successful pause returns 204."""
        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post("/docker/containers/abc123/pause")

        assert response.status_code == 204
        mock_docker_client.pause_container.assert_called_once_with("abc123")
        mock_docker_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_not_found(self, app, mock_docker_client):
        """Test pause returns 404 when container not found."""
        mock_docker_client.pause_container.side_effect = _make_client_response_error(404)

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post("/docker/containers/nonexistent/pause")

        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_pause_server_error(self, app, mock_docker_client):
        """Test pause returns 500 on Docker internal error."""
        mock_docker_client.pause_container.side_effect = Exception("Docker error")

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post("/docker/containers/abc123/pause")

        assert response.status_code == 500


class TestUnpauseContainer:
    """Tests for POST /docker/containers/{container_id}/unpause."""

    @pytest.mark.asyncio
    async def test_unpause_success(self, app, mock_docker_client):
        """Test successful unpause returns 204."""
        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post("/docker/containers/abc123/unpause")

        assert response.status_code == 204
        mock_docker_client.unpause_container.assert_called_once_with("abc123")
        mock_docker_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_unpause_not_found(self, app, mock_docker_client):
        """Test unpause returns 404 when container not found."""
        mock_docker_client.unpause_container.side_effect = _make_client_response_error(404)

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post("/docker/containers/nonexistent/unpause")

        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_unpause_server_error(self, app, mock_docker_client):
        """Test unpause returns 500 on Docker internal error."""
        mock_docker_client.unpause_container.side_effect = Exception("Docker error")

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post("/docker/containers/abc123/unpause")

        assert response.status_code == 500
