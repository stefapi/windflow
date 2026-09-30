"""
Tests de sécurité pour vérifier que tous les endpoints Docker retournent 401 sans token JWT.

STORY-032 : Sécurité — Authentification sur les endpoints Docker.
Teste que chaque endpoint Docker exige une authentification valide.
Conformément à .clinerules/40-security.md — Checklist des tests de sécurité.
"""

import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.api.v1.docker import router
from app.auth.dependencies import get_current_active_user
from app.core.exceptions import WindFlowException
from app.middleware.error_handler import windflow_exception_handler


def _raise_401():
    """Lève une exception 401 pour simuler l'absence de token JWT."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


@pytest.fixture
def app():
    """Crée une app FastAPI avec auth override levant systématiquement 401."""
    _app = FastAPI()
    # STORY-127 : exceptions typées → handler global requis
    _app.add_exception_handler(WindFlowException, windflow_exception_handler)
    _app.include_router(router, prefix="/api/v1/docker")
    # Override auth to raise 401 (simulating no token)
    _app.dependency_overrides[get_current_active_user] = lambda: _raise_401()
    return _app


# =============================================================================
# Containers — 20 endpoints
# =============================================================================


class TestContainerEndpointsAuth:
    """Tests 401 pour les endpoints Containers."""

    @pytest.mark.asyncio
    async def test_list_containers_returns_401_without_token(self, app):
        """GET /containers → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/containers")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_container_returns_401_without_token(self, app):
        """GET /containers/{id} → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/containers/abc123")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_container_returns_401_without_token(self, app):
        """POST /containers → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/docker/containers",
                json={"name": "test", "image": "nginx:latest"},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_batch_start_returns_401_without_token(self, app):
        """POST /containers/batch/start → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/docker/containers/batch/start",
                json={"container_ids": ["abc123"]},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_batch_stop_returns_401_without_token(self, app):
        """POST /containers/batch/stop → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/docker/containers/batch/stop",
                json={"container_ids": ["abc123"]},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_start_container_returns_401_without_token(self, app):
        """POST /containers/{id}/start → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/api/v1/docker/containers/abc123/start")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_stop_container_returns_401_without_token(self, app):
        """POST /containers/{id}/stop → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/api/v1/docker/containers/abc123/stop")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_restart_container_returns_401_without_token(self, app):
        """POST /containers/{id}/restart → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/api/v1/docker/containers/abc123/restart")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_pause_container_returns_401_without_token(self, app):
        """POST /containers/{id}/pause → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/api/v1/docker/containers/abc123/pause")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unpause_container_returns_401_without_token(self, app):
        """POST /containers/{id}/unpause → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/api/v1/docker/containers/abc123/unpause")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_remove_container_returns_401_without_token(self, app):
        """DELETE /containers/{id} → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.delete("/api/v1/docker/containers/abc123")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_recreate_container_returns_401_without_token(self, app):
        """POST /containers/{id}/recreate → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/recreate",
                json={},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_restart_policy_returns_401_without_token(self, app):
        """PATCH /containers/{id}/restart-policy → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.patch(
                "/api/v1/docker/containers/abc123/restart-policy",
                json={"name": "always"},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_resources_returns_401_without_token(self, app):
        """PATCH /containers/{id}/resources → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.patch(
                "/api/v1/docker/containers/abc123/resources",
                json={"memory_limit": 536870912},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_rename_container_returns_401_without_token(self, app):
        """POST /containers/{id}/rename → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/rename",
                json={"new_name": "renamed-container"},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_connect_network_returns_401_without_token(self, app):
        """POST /containers/{id}/networks/connect → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/connect",
                json={"network_id": "net123"},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_disconnect_network_returns_401_without_token(self, app):
        """POST /containers/{id}/networks/disconnect → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/disconnect",
                json={"network_id": "net123"},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_container_stats_returns_401_without_token(self, app):
        """GET /containers/{id}/stats → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/containers/abc123/stats")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_container_processes_returns_401_without_token(self, app):
        """GET /containers/{id}/top → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/containers/abc123/top")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_container_logs_returns_401_without_token(self, app):
        """GET /containers/{id}/logs → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/containers/abc123/logs")
        assert response.status_code == 401


# =============================================================================
# Images — 6 endpoints
# =============================================================================


class TestImageEndpointsAuth:
    """Tests 401 pour les endpoints Images."""

    @pytest.mark.asyncio
    async def test_list_images_returns_401_without_token(self, app):
        """GET /images → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/images")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_image_returns_401_without_token(self, app):
        """GET /images/{id} → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/images/abc123")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_pull_image_returns_401_without_token(self, app):
        """POST /images/pull → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/docker/images/pull",
                json={"name": "nginx", "tag": "latest"},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_remove_image_returns_401_without_token(self, app):
        """DELETE /images/{id} → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.delete("/api/v1/docker/images/abc123")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_load_image_returns_401_without_token(self, app):
        """POST /images/load → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/docker/images/load",
                files={"file": ("image.tar", b"fake_tar", "application/x-tar")},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_save_image_returns_401_without_token(self, app):
        """GET /images/{id}/save → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/images/abc123/save")
        assert response.status_code == 401


# =============================================================================
# Volumes — 3 endpoints
# =============================================================================


class TestVolumeEndpointsAuth:
    """Tests 401 pour les endpoints Volumes."""

    @pytest.mark.asyncio
    async def test_list_volumes_returns_401_without_token(self, app):
        """GET /volumes → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/volumes")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_volume_returns_401_without_token(self, app):
        """POST /volumes → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/docker/volumes",
                json={"name": "test-volume"},
            )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_remove_volume_returns_401_without_token(self, app):
        """DELETE /volumes/{name} → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.delete("/api/v1/docker/volumes/test-volume")
        assert response.status_code == 401


# =============================================================================
# Networks — 1 endpoint
# =============================================================================


class TestNetworkEndpointsAuth:
    """Tests 401 pour les endpoints Networks."""

    @pytest.mark.asyncio
    async def test_list_networks_returns_401_without_token(self, app):
        """GET /networks → 401 sans token."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/networks")
        assert response.status_code == 401
