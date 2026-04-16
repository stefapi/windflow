"""Tests pour l'endpoint POST /docker/containers/{id}/promote."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.stack import Stack
from app.models.user import User
from app.schemas.stack import StackCreate
from app.services.stack_service import StackService


def _make_container_inspect(
    name: str = "test-container",
    image: str = "nginx:latest",
    labels: dict | None = None,
    env: list | None = None,
    port_bindings: dict | None = None,
    binds: list | None = None,
    restart_policy: dict | None = None,
    memory: int = 0,
    cpu_shares: int = 0,
    pids_limit: int = 0,
) -> dict:
    """Build a mock Docker inspect response."""
    return {
        "Id": "abc123def456",
        "Name": f"/{name}",
        "Config": {
            "Image": image,
            "Labels": labels or {},
            "Env": env or [],
        },
        "HostConfig": {
            "PortBindings": port_bindings or {},
            "Binds": binds or [],
            "RestartPolicy": restart_policy or {"Name": "", "MaximumRetryCount": 0},
            "Memory": memory,
            "CpuShares": cpu_shares,
            "PidsLimit": pids_limit,
        },
    }


@pytest.fixture
async def existing_stack(db_session: AsyncSession, test_organization: Organization) -> Stack:
    """Crée un stack existant pour tester les conflits de nom."""
    stack_data = StackCreate(
        name="Existing Stack",
        description="An existing stack",
        template={"version": "3.8", "services": {"web": {"image": "nginx:latest"}}},
        variables={},
        organization_id=test_organization.id,
    )
    return await StackService.create(db_session, stack_data)


class TestPromoteContainer:
    """Tests pour POST /api/v1/docker/containers/{container_id}/promote."""

    @pytest.mark.asyncio
    async def test_promote_container_success(
        self,
        authenticated_client: AsyncClient,
    ):
        """Nominal : promeut un container standalone en stack → 200."""
        mock_inspect = _make_container_inspect(
            name="my-nginx",
            image="nginx:latest",
            env=["NODE_ENV=production"],
            port_bindings={"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]},
            restart_policy={"Name": "always", "MaximumRetryCount": 0},
        )

        with patch(
            "app.api.v1.docker.get_docker_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.inspect_container = AsyncMock(return_value=mock_inspect)
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await authenticated_client.post(
                "/api/v1/docker/containers/abc123/promote",
                json={"name": "My Promoted Stack"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["stack_id"]
        assert data["stack_name"] == "My Promoted Stack"
        assert "promu" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_promote_returns_401_without_token(
        self,
        client: AsyncClient,
    ):
        """Sécurité : accès sans authentification → 401."""
        response = await client.post(
            "/api/v1/docker/containers/abc123/promote",
            json={"name": "Test Stack"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_promote_returns_404_container_not_found(
        self,
        authenticated_client: AsyncClient,
    ):
        """Erreur : container Docker inexistant → 404."""
        import aiohttp

        with patch(
            "app.api.v1.docker.get_docker_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            error = aiohttp.ClientResponseError(
                request_info=AsyncMock(),
                history=(),
                status=404,
                message="Not Found",
            )
            mock_client.inspect_container = AsyncMock(side_effect=error)
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await authenticated_client.post(
                "/api/v1/docker/containers/nonexistent/promote",
                json={"name": "Test Stack"},
            )

        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_promote_returns_409_already_managed(
        self,
        authenticated_client: AsyncClient,
    ):
        """Conflit : container déjà managé (label windflow.managed) → 409."""
        mock_inspect = _make_container_inspect(
            labels={"windflow.managed": "true"},
        )

        with patch(
            "app.api.v1.docker.get_docker_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.inspect_container = AsyncMock(return_value=mock_inspect)
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await authenticated_client.post(
                "/api/v1/docker/containers/abc123/promote",
                json={"name": "Test Stack"},
            )

        assert response.status_code == 409
        assert "managé" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_promote_returns_409_name_conflict(
        self,
        authenticated_client: AsyncClient,
        existing_stack: Stack,
    ):
        """Conflit : nom de stack déjà pris dans l'organisation → 409."""
        mock_inspect = _make_container_inspect()

        with patch(
            "app.api.v1.docker.get_docker_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.inspect_container = AsyncMock(return_value=mock_inspect)
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await authenticated_client.post(
                "/api/v1/docker/containers/abc123/promote",
                json={"name": existing_stack.name},
            )

        assert response.status_code == 409
        assert "existe déjà" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_promote_returns_422_empty_name(
        self,
        authenticated_client: AsyncClient,
    ):
        """Validation : nom vide dans le body → 422."""
        response = await authenticated_client.post(
            "/api/v1/docker/containers/abc123/promote",
            json={"name": ""},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_promote_returns_422_name_too_long(
        self,
        authenticated_client: AsyncClient,
    ):
        """Validation : nom > 255 caractères → 422."""
        response = await authenticated_client.post(
            "/api/v1/docker/containers/abc123/promote",
            json={"name": "a" * 256},
        )

        assert response.status_code == 422
