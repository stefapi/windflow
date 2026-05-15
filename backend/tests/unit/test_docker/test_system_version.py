"""
Tests for Docker system version API endpoint.
STORY-020: GET /docker/system/version — secured with get_current_active_user
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


def _make_version_data() -> dict:
    """Create mock version data as returned by DockerClientService.system_version()."""
    return {
        "Version": "24.0.7",
        "ApiVersion": "1.43",
        "MinAPIVersion": "1.12",
        "GitCommit": "afdd53b",
        "GoVersion": "go1.20.10",
        "Os": "linux",
        "Arch": "amd64",
        "KernelVersion": "6.1.0-test",
        "BuildTime": "2023-10-26T14:00:00.000000000+00:00",
    }


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
    client.system_version = AsyncMock()
    client.close = AsyncMock()
    return client


class TestGetVersion:
    """Tests for GET /docker/system/version."""

    @pytest.mark.asyncio
    async def test_get_version_returns_200_authenticated(self, app, mock_docker_client):
        """Test successful version retrieval when authenticated."""
        mock_docker_client.system_version.return_value = _make_version_data()

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/docker/system/version")

        assert response.status_code == 200
        mock_docker_client.system_version.assert_called_once()
        mock_docker_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_version_returns_401_without_token(self, app):
        """Test that version endpoint returns 401 without authentication."""
        # Override auth to raise 401 (simulating no token)
        app.dependency_overrides[get_current_active_user] = lambda: (
            _ for _ in ()
        ).throw(HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"))

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/docker/system/version")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_version_returns_data_shape(self, app, mock_docker_client):
        """Test that response contains all expected fields."""
        mock_docker_client.system_version.return_value = _make_version_data()

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/docker/system/version")

        assert response.status_code == 200
        data = response.json()

        # Verify all expected fields are present
        expected_fields = [
            "version", "ApiVersion", "MinAPIVersion",
            "GitCommit", "GoVersion", "os", "arch",
            "KernelVersion", "BuildTime",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

        # Verify specific values
        assert data["version"] == "24.0.7"
        assert data["ApiVersion"] == "1.43"
        assert data["MinAPIVersion"] == "1.12"
        assert data["GitCommit"] == "afdd53b"
        assert data["GoVersion"] == "go1.20.10"
        assert data["os"] == "linux"
        assert data["arch"] == "amd64"
        assert data["KernelVersion"] == "6.1.0-test"
        assert data["BuildTime"] == "2023-10-26T14:00:00.000000000+00:00"
