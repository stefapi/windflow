"""
Tests for Docker container config update and rename API endpoints.
STORY-028.1: PATCH restart-policy, PATCH resources, POST rename
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
    client.update_container = AsyncMock(return_value={"Warnings": []})
    client.rename_container = AsyncMock()
    client.close = AsyncMock()
    return client


def _make_client_response_error(status: int) -> aiohttp.ClientResponseError:
    """Helper to create a ClientResponseError with given status."""
    return aiohttp.ClientResponseError(
        MagicMock(), (), status=status, message="Error"
    )


# =========================================================================
# PATCH /containers/{id}/restart-policy
# =========================================================================


class TestUpdateRestartPolicy:
    """Tests for PATCH /docker/containers/{container_id}/restart-policy."""

    @pytest.mark.asyncio
    async def test_restart_policy_success(self, app, mock_docker_client):
        """Test successful restart policy update returns 200."""
        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/docker/containers/abc123/restart-policy",
                    json={"name": "always"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["warnings"] == []
        mock_docker_client.update_container.assert_called_once_with(
            "abc123",
            {"RestartPolicy": {"Name": "always"}},
        )
        mock_docker_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_restart_policy_with_retry_count(self, app, mock_docker_client):
        """Test restart policy update with maximum_retry_count."""
        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/docker/containers/abc123/restart-policy",
                    json={"name": "on-failure", "maximum_retry_count": 5},
                )

        assert response.status_code == 200
        mock_docker_client.update_container.assert_called_once_with(
            "abc123",
            {"RestartPolicy": {"Name": "on-failure", "MaximumRetryCount": 5}},
        )

    @pytest.mark.asyncio
    async def test_restart_policy_with_warnings(self, app, mock_docker_client):
        """Test restart policy update returning warnings from Docker."""
        mock_docker_client.update_container = AsyncMock(
            return_value={"Warnings": ["Some warning"]}
        )

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/docker/containers/abc123/restart-policy",
                    json={"name": "always"},
                )

        assert response.status_code == 200
        assert response.json()["warnings"] == ["Some warning"]

    @pytest.mark.asyncio
    async def test_restart_policy_not_found(self, app, mock_docker_client):
        """Test restart policy update returns 404 when container not found."""
        mock_docker_client.update_container.side_effect = (
            _make_client_response_error(404)
        )

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/docker/containers/nonexistent/restart-policy",
                    json={"name": "always"},
                )

        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_restart_policy_server_error(self, app, mock_docker_client):
        """Test restart policy update returns 500 on Docker internal error."""
        mock_docker_client.update_container.side_effect = Exception("Docker error")

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/docker/containers/abc123/restart-policy",
                    json={"name": "always"},
                )

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_restart_policy_invalid_name(self, app, mock_docker_client):
        """Test restart policy update returns 422 for invalid policy name."""
        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/docker/containers/abc123/restart-policy",
                    json={"name": "invalid"},
                )

        assert response.status_code == 422


# =========================================================================
# PATCH /containers/{id}/resources
# =========================================================================


class TestUpdateResources:
    """Tests for PATCH /docker/containers/{container_id}/resources."""

    @pytest.mark.asyncio
    async def test_resources_success(self, app, mock_docker_client):
        """Test successful resources update returns 200."""
        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/docker/containers/abc123/resources",
                    json={"memory_limit": 536870912},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["warnings"] == []
        mock_docker_client.update_container.assert_called_once_with(
            "abc123",
            {"Resources": {"Memory": 536870912}},
        )
        mock_docker_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_resources_all_fields(self, app, mock_docker_client):
        """Test resources update with all fields."""
        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/docker/containers/abc123/resources",
                    json={
                        "memory_limit": 536870912,
                        "cpu_shares": 512,
                        "pids_limit": 100,
                    },
                )

        assert response.status_code == 200
        mock_docker_client.update_container.assert_called_once_with(
            "abc123",
            {"Resources": {"Memory": 536870912, "CpuShares": 512, "PidsLimit": 100}},
        )

    @pytest.mark.asyncio
    async def test_resources_empty_body(self, app, mock_docker_client):
        """Test resources update with no fields sends empty Resources dict."""
        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/docker/containers/abc123/resources",
                    json={},
                )

        assert response.status_code == 200
        mock_docker_client.update_container.assert_called_once_with(
            "abc123",
            {"Resources": {}},
        )

    @pytest.mark.asyncio
    async def test_resources_not_found(self, app, mock_docker_client):
        """Test resources update returns 404 when container not found."""
        mock_docker_client.update_container.side_effect = (
            _make_client_response_error(404)
        )

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/docker/containers/nonexistent/resources",
                    json={"memory_limit": 536870912},
                )

        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_resources_server_error(self, app, mock_docker_client):
        """Test resources update returns 500 on Docker internal error."""
        mock_docker_client.update_container.side_effect = Exception("Docker error")

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/docker/containers/abc123/resources",
                    json={"memory_limit": 536870912},
                )

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_resources_negative_memory(self, app, mock_docker_client):
        """Test resources update returns 422 for negative memory_limit."""
        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/docker/containers/abc123/resources",
                    json={"memory_limit": -1},
                )

        assert response.status_code == 422


# =========================================================================
# POST /containers/{id}/rename
# =========================================================================


class TestRenameContainer:
    """Tests for POST /docker/containers/{container_id}/rename."""

    @pytest.mark.asyncio
    async def test_rename_success(self, app, mock_docker_client):
        """Test successful rename returns 200 with confirmation."""
        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/docker/containers/abc123/rename",
                    json={"new_name": "my-app"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "my-app" in data["message"]
        mock_docker_client.rename_container.assert_called_once_with(
            "abc123", "my-app"
        )
        mock_docker_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_rename_not_found(self, app, mock_docker_client):
        """Test rename returns 404 when container not found."""
        mock_docker_client.rename_container.side_effect = (
            _make_client_response_error(404)
        )

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/docker/containers/nonexistent/rename",
                    json={"new_name": "new-name"},
                )

        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_rename_server_error(self, app, mock_docker_client):
        """Test rename returns 500 on Docker internal error."""
        mock_docker_client.rename_container.side_effect = Exception("Docker error")

        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/docker/containers/abc123/rename",
                    json={"new_name": "new-name"},
                )

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_rename_invalid_name(self, app, mock_docker_client):
        """Test rename returns 422 for name with spaces and special chars."""
        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/docker/containers/abc123/rename",
                    json={"new_name": "invalid name!"},
                )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_rename_empty_name(self, app, mock_docker_client):
        """Test rename returns 422 for empty name."""
        with patch(
            "app.api.v1.docker.get_docker_client",
            new_callable=AsyncMock,
            return_value=mock_docker_client,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/docker/containers/abc123/rename",
                    json={"new_name": ""},
                )

        assert response.status_code == 422


# =========================================================================
# Schema validation tests
# =========================================================================


class TestSchemaValidation:
    """Tests for Pydantic schema validation."""

    def test_restart_policy_request_valid_values(self):
        """Test all 4 valid restart policy values."""
        from app.schemas.docker import ContainerUpdateRestartPolicyRequest

        for policy in ["no", "always", "on-failure", "unless-stopped"]:
            req = ContainerUpdateRestartPolicyRequest(name=policy)
            assert req.name == policy

    def test_restart_policy_request_with_retry_count(self):
        """Test restart policy with maximum_retry_count."""
        from app.schemas.docker import ContainerUpdateRestartPolicyRequest

        req = ContainerUpdateRestartPolicyRequest(
            name="on-failure", maximum_retry_count=10
        )
        assert req.maximum_retry_count == 10

    def test_restart_policy_request_invalid_value(self):
        """Test restart policy rejects invalid values."""
        from pydantic import ValidationError

        from app.schemas.docker import ContainerUpdateRestartPolicyRequest

        with pytest.raises(ValidationError):
            ContainerUpdateRestartPolicyRequest(name="invalid")

    def test_resources_request_none_values(self):
        """Test resources request with all None (empty body is valid)."""
        from app.schemas.docker import ContainerUpdateResourcesRequest

        req = ContainerUpdateResourcesRequest()
        assert req.memory_limit is None
        assert req.cpu_shares is None
        assert req.pids_limit is None

    def test_resources_request_negative_memory(self):
        """Test resources request rejects negative memory."""
        from pydantic import ValidationError

        from app.schemas.docker import ContainerUpdateResourcesRequest

        with pytest.raises(ValidationError):
            ContainerUpdateResourcesRequest(memory_limit=-1)

    def test_resources_request_negative_cpu(self):
        """Test resources request rejects negative cpu_shares."""
        from pydantic import ValidationError

        from app.schemas.docker import ContainerUpdateResourcesRequest

        with pytest.raises(ValidationError):
            ContainerUpdateResourcesRequest(cpu_shares=-1)

    def test_rename_request_valid_names(self):
        """Test rename request accepts valid container names."""
        from app.schemas.docker import ContainerRenameRequest

        for name in ["my-container", "my_container", "container.v2", "MyApp"]:
            req = ContainerRenameRequest(new_name=name)
            assert req.new_name == name

    def test_rename_request_invalid_name(self):
        """Test rename request rejects names starting with special chars."""
        from pydantic import ValidationError

        from app.schemas.docker import ContainerRenameRequest

        with pytest.raises(ValidationError):
            ContainerRenameRequest(new_name="-invalid")

    def test_rename_request_name_with_spaces(self):
        """Test rename request rejects names with spaces."""
        from pydantic import ValidationError

        from app.schemas.docker import ContainerRenameRequest

        with pytest.raises(ValidationError):
            ContainerRenameRequest(new_name="invalid name")

    def test_pids_limit_unlimited(self):
        """Test pids_limit accepts -1 (unlimited)."""
        from app.schemas.docker import ContainerUpdateResourcesRequest

        req = ContainerUpdateResourcesRequest(pids_limit=-1)
        assert req.pids_limit == -1
