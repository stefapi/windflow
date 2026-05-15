"""
Tests for Docker system ping API endpoint.
STORY-020: GET /docker/system/ping — secured with get_current_active_user
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.api.v1.docker import router
from app.auth.dependencies import get_current_active_user
from app.models.user import User
from app.services.docker_client_service import DockerClientService


def _make_mock_user() -> User:
    """Create a mock authenticated user."""
    user = MagicMock(spec=User)
    user.id = 1
    user.username = "testuser"
    user.email = "test@example.com"
    user.is_active = True
    user.is_superuser = False
    return user


@pytest.fixture
def app():
    """Create a minimal FastAPI app with Docker router and auth override."""
    _app = FastAPI()
    _app.include_router(router, prefix="/docker")
    # Override auth dependency for all tests by default
    _app.dependency_overrides[get_current_active_user] = lambda: _make_mock_user()
    return _app


@pytest.fixture
def mock_docker_client():
    """Create a mock DockerClientService."""
    client = DockerClientService()
    client.ping = AsyncMock()
    client.close = AsyncMock()
    return client


class TestPing:
    """Tests for GET /docker/system/ping."""

    @pytest.mark.asyncio
    async def test_ping_returns_200_authenticated(self, app, mock_docker_client):
        """Test successful ping when Docker is available and user is authenticated."""
        mock_docker_client.ping.return_value = True

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/docker/system/ping")

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["message"] == "Docker is available"
        mock_docker_client.ping.assert_called_once()
        mock_docker_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_ping_returns_200_unavailable(self, app, mock_docker_client):
        """Test ping when Docker is not available."""
        mock_docker_client.ping.return_value = False

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/docker/system/ping")

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert data["message"] == "Docker is not available"

    @pytest.mark.asyncio
    async def test_ping_returns_401_without_token(self, app):
        """Test that ping endpoint returns 401 without authentication."""
        # Override auth to raise 401 (simulating no token)
        app.dependency_overrides[get_current_active_user] = lambda: (
            _ for _ in ()
        ).throw(HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"))

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/docker/system/ping")

        assert response.status_code == 401
