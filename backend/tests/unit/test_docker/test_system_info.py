"""
Tests for Docker system info API endpoint.
STORY-018: GET /docker/system/info — secured with get_current_active_user
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


def _make_system_info():
    """Create a mock SystemInfo dataclass instance."""
    from dataclasses import dataclass

    @dataclass
    class MockSystemInfo:
        id: str = "ABCD1234"
        name: str = "docker-desktop"
        server_version: str = "24.0.7"
        containers: int = 10
        containers_running: int = 5
        containers_paused: int = 1
        containers_stopped: int = 4
        images: int = 25
        driver: str = "overlay2"
        docker_root_dir: str = "/var/lib/docker"
        kernel_version: str = "6.1.0-test"
        operating_system: str = "Docker Desktop"
        os_type: str = "linux"
        architecture: str = "x86_64"
        cpus: int = 8
        memory: int = 17179869184  # 16 Go

    return MockSystemInfo()


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
    client.system_info = AsyncMock()
    client.close = AsyncMock()
    return client


class TestGetSystemInfo:
    """Tests for GET /docker/system/info."""

    @pytest.mark.asyncio
    async def test_get_system_info_returns_200_authenticated(self, app, mock_docker_client):
        """Test successful system info retrieval when authenticated."""
        mock_docker_client.system_info.return_value = _make_system_info()

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/docker/system/info")

        assert response.status_code == 200
        mock_docker_client.system_info.assert_called_once()
        mock_docker_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_system_info_returns_401_without_token(self, app):
        """Test that system info returns 401 without authentication."""
        # Override auth to raise 401 (simulating no token)
        app.dependency_overrides[get_current_active_user] = lambda: (
            _ for _ in ()
        ).throw(HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"))

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/docker/system/info")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_system_info_returns_data_shape(self, app, mock_docker_client):
        """Test that response contains all expected fields."""
        mock_docker_client.system_info.return_value = _make_system_info()

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/docker/system/info")

        assert response.status_code == 200
        data = response.json()

        # Verify all expected fields are present (Pydantic uses aliases for serialization)
        expected_fields = [
            "ID", "Name", "ServerVersion",
            "containers", "ContainersRunning", "ContainersPaused", "ContainersStopped",
            "images", "driver", "DockerRootDir",
            "KernelVersion", "OperatingSystem", "OSType",
            "architecture", "NCPU", "MemTotal",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

        # Verify specific values
        assert data["ServerVersion"] == "24.0.7"
        assert data["containers"] == 10
        assert data["ContainersRunning"] == 5
        assert data["ContainersPaused"] == 1
        assert data["ContainersStopped"] == 4
        assert data["images"] == 25
        assert data["OperatingSystem"] == "Docker Desktop"
        assert data["architecture"] == "x86_64"
        assert data["NCPU"] == 8
        assert data["MemTotal"] == 17179869184
