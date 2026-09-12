"""
Tests unitaires pour la pagination des listes Docker.

STORY-035 : Pagination des listes Docker.
Teste les paramètres skip/limit sur les 4 endpoints de listage :
containers, images, volumes et networks.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.api.v1.docker import router
from app.auth.dependencies import get_current_active_user
from app.auth.rbac import require_admin, require_operator, require_viewer


def _make_mock_user():
    """Crée un mock utilisateur authentifié."""
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_user.email = "test@example.com"
    mock_user.is_active = True
    return mock_user


def _raise_401():
    """Lève une exception 401 pour simuler l'absence de token JWT."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------------------------------------------------------------------------
# Helpers pour générer N mocks d'items
# ---------------------------------------------------------------------------


def _make_container_info(idx: int):
    """Crée un mock ContainerInfo."""
    c = MagicMock()
    c.id = f"container{idx:04d}"
    c.name = f"test-container-{idx}"
    c.image = f"nginx:{idx}"
    c.image_id = f"sha256:img{idx:012d}"
    c.command = "nginx"
    c.created = datetime(2025, 1, 15, 10, 30, 0)
    c.state = "running"
    c.status = "Up 2 hours"
    c.ports = []
    c.labels = {}
    c.networks = ["bridge"]
    c.mounts = []
    c.restart_count = 0
    return c


def _make_image_info(idx: int):
    """Crée un mock ImageInfo."""
    img = MagicMock()
    img.id = f"img{idx:012d}"
    img.repo_tags = [f"image-{idx}:latest"]
    img.repo_digests = []
    img.created = datetime(2025, 1, 15, 10, 30, 0)
    img.size = 187500000
    img.virtual_size = 200000000
    img.labels = {}
    return img


def _make_volume_info(idx: int):
    """Crée un mock VolumeInfo."""
    v = MagicMock()
    v.name = f"volume-{idx}"
    v.driver = "local"
    v.mountpoint = f"/var/lib/docker/volumes/volume-{idx}/_data"
    v.created_at = datetime(2025, 1, 15, 10, 30, 0).isoformat()
    v.labels = {}
    v.scope = "local"
    return v


def _make_network_info(idx: int):
    """Crée un mock NetworkInfo."""
    n = MagicMock()
    n.id = f"net{idx:012d}"
    n.name = f"network-{idx}"
    n.driver = "bridge"
    n.scope = "local"
    n.internal = False
    n.attachable = False
    n.ingress = False
    n.created = datetime(2025, 1, 15, 10, 30, 0).isoformat()
    n.subnet = f"172.{idx % 256}.0.0/16"
    n.gateway = f"172.{idx % 256}.0.1"
    return n


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Crée une application FastAPI de test."""
    application = FastAPI()
    application.include_router(router, prefix="/api/v1/docker")
    application.dependency_overrides[get_current_active_user] = (
        lambda: _make_mock_user()
    )
    # STORY-122.2 : routes Docker protégées par require_* — délégation au
    # même provider (mini-app sans DB ; RBAC couvert par test_docker_rbac.py)
    for _rbac_dep in (require_viewer, require_operator, require_admin):
        application.dependency_overrides[_rbac_dep] = lambda: _make_mock_user()
    return application


# ===========================================================================
# TestContainerPagination
# ===========================================================================


class TestContainerPagination:
    """Tests de pagination pour GET /docker/containers."""

    @pytest.mark.asyncio
    async def test_default_pagination_returns_50_max(self, app):
        """Sans paramètres, retourne max 50 éléments sur 60 mockés."""
        containers = [_make_container_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_containers = AsyncMock(return_value=containers)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/containers")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 50

    @pytest.mark.asyncio
    async def test_skip_parameter_works(self, app):
        """skip=10 saute les 10 premiers éléments sur 60 mockés."""
        containers = [_make_container_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_containers = AsyncMock(return_value=containers)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/containers?skip=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 50
        assert data[0]["id"] == "container0010"

    @pytest.mark.asyncio
    async def test_limit_parameter_works(self, app):
        """limit=5 retourne exactement 5 éléments."""
        containers = [_make_container_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_containers = AsyncMock(return_value=containers)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/containers?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

    @pytest.mark.asyncio
    async def test_skip_and_limit_combined(self, app):
        """skip=5&limit=10 retourne 10 éléments à partir du 6ème."""
        containers = [_make_container_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_containers = AsyncMock(return_value=containers)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/containers?skip=5&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10
        assert data[0]["id"] == "container0005"
        assert data[9]["id"] == "container0014"

    @pytest.mark.asyncio
    async def test_skip_beyond_list_returns_empty(self, app):
        """skip=999 au-delà du nombre total → liste vide."""
        containers = [_make_container_info(i) for i in range(10)]

        mock_client = AsyncMock()
        mock_client.list_containers = AsyncMock(return_value=containers)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/containers?skip=999")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_limit_1_returns_single(self, app):
        """limit=1 retourne exactement 1 élément."""
        containers = [_make_container_info(i) for i in range(10)]

        mock_client = AsyncMock()
        mock_client.list_containers = AsyncMock(return_value=containers)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/containers?limit=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "container0000"

    @pytest.mark.asyncio
    async def test_pagination_returns_401_without_token(self, app):
        """Sécurité : accès sans authentification → 401."""
        unauth_app = FastAPI()
        unauth_app.include_router(router, prefix="/api/v1/docker")
        unauth_app.dependency_overrides[get_current_active_user] = lambda: _raise_401()
        for _rbac_dep in (require_viewer, require_operator, require_admin):
            unauth_app.dependency_overrides[_rbac_dep] = lambda: _raise_401()

        async with AsyncClient(
            transport=ASGITransport(app=unauth_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/containers")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_skip_negative_returns_422(self, app):
        """Validation : skip=-1 → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/containers?skip=-1")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_limit_zero_returns_422(self, app):
        """Validation : limit=0 → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/containers?limit=0")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_limit_over_100_returns_422(self, app):
        """Validation : limit=101 → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/containers?limit=101")

        assert response.status_code == 422


# ===========================================================================
# TestImagePagination
# ===========================================================================


class TestImagePagination:
    """Tests de pagination pour GET /docker/images."""

    @pytest.mark.asyncio
    async def test_default_pagination_returns_50_max(self, app):
        """Sans paramètres, retourne max 50 images sur 60 mockées."""
        images = [_make_image_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_images = AsyncMock(return_value=images)
        mock_client.list_containers = AsyncMock(return_value=[])
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/images")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 50

    @pytest.mark.asyncio
    async def test_skip_and_limit_combined(self, app):
        """skip=5&limit=10 retourne 10 images à partir de la 6ème."""
        images = [_make_image_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_images = AsyncMock(return_value=images)
        mock_client.list_containers = AsyncMock(return_value=[])
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/images?skip=5&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10
        assert data[0]["id"] == f"img{5:012d}"
        assert data[9]["id"] == f"img{14:012d}"

    @pytest.mark.asyncio
    async def test_pagination_returns_401_without_token(self, app):
        """Sécurité : accès sans authentification → 401."""
        unauth_app = FastAPI()
        unauth_app.include_router(router, prefix="/api/v1/docker")
        unauth_app.dependency_overrides[get_current_active_user] = lambda: _raise_401()
        for _rbac_dep in (require_viewer, require_operator, require_admin):
            unauth_app.dependency_overrides[_rbac_dep] = lambda: _raise_401()

        async with AsyncClient(
            transport=ASGITransport(app=unauth_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/images")

        assert response.status_code == 401


# ===========================================================================
# TestVolumePagination
# ===========================================================================


class TestVolumePagination:
    """Tests de pagination pour GET /docker/volumes."""

    @pytest.mark.asyncio
    async def test_default_pagination_returns_50_max(self, app):
        """Sans paramètres, retourne max 50 volumes sur 60 mockés."""
        volumes = [_make_volume_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_volumes = AsyncMock(return_value=volumes)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/volumes")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 50

    @pytest.mark.asyncio
    async def test_skip_and_limit_combined(self, app):
        """skip=5&limit=10 retourne 10 volumes à partir du 6ème."""
        volumes = [_make_volume_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_volumes = AsyncMock(return_value=volumes)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/volumes?skip=5&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10
        assert data[0]["name"] == "volume-5"
        assert data[9]["name"] == "volume-14"

    @pytest.mark.asyncio
    async def test_pagination_returns_401_without_token(self, app):
        """Sécurité : accès sans authentification → 401."""
        unauth_app = FastAPI()
        unauth_app.include_router(router, prefix="/api/v1/docker")
        unauth_app.dependency_overrides[get_current_active_user] = lambda: _raise_401()
        for _rbac_dep in (require_viewer, require_operator, require_admin):
            unauth_app.dependency_overrides[_rbac_dep] = lambda: _raise_401()

        async with AsyncClient(
            transport=ASGITransport(app=unauth_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/volumes")

        assert response.status_code == 401


# ===========================================================================
# TestNetworkPagination
# ===========================================================================


class TestNetworkPagination:
    """Tests de pagination pour GET /docker/networks."""

    @pytest.mark.asyncio
    async def test_default_pagination_returns_50_max(self, app):
        """Sans paramètres, retourne max 50 réseaux sur 60 mockés."""
        networks = [_make_network_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_networks = AsyncMock(return_value=networks)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/networks")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 50

    @pytest.mark.asyncio
    async def test_skip_and_limit_combined(self, app):
        """skip=5&limit=10 retourne 10 réseaux à partir du 6ème."""
        networks = [_make_network_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_networks = AsyncMock(return_value=networks)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/networks?skip=5&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10
        assert data[0]["name"] == "network-5"
        assert data[9]["name"] == "network-14"

    @pytest.mark.asyncio
    async def test_pagination_returns_401_without_token(self, app):
        """Sécurité : accès sans authentification → 401."""
        unauth_app = FastAPI()
        unauth_app.include_router(router, prefix="/api/v1/docker")
        unauth_app.dependency_overrides[get_current_active_user] = lambda: _raise_401()
        for _rbac_dep in (require_viewer, require_operator, require_admin):
            unauth_app.dependency_overrides[_rbac_dep] = lambda: _raise_401()

        async with AsyncClient(
            transport=ASGITransport(app=unauth_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/networks")

        assert response.status_code == 401
