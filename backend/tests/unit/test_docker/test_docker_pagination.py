"""
Tests unitaires pour la pagination des listes Docker.

STORY-035 : Pagination des listes Docker (skip/limit — historique).
STORY-128 : harmonisation au contrat paginé spec 09 — les 4 endpoints de
listage (containers, images, volumes, networks) répondent désormais
``{data: [...], pagination: {page, per_page, total, pages}}`` via
``?page=&per_page=`` (défauts 1/20, bornes per_page 1-100).
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.api.v1.docker import router
from app.auth.dependencies import get_current_active_user
from app.auth.rbac import require_admin, require_operator, require_viewer
from app.core.exceptions import WindFlowException
from app.middleware.error_handler import windflow_exception_handler


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


def _assert_pagination_contract(body: dict) -> dict:
    """Vérifie le contrat PaginatedResponse{data, pagination} spec 09."""
    assert isinstance(body.get("data"), list), f"data doit être une liste : {body}"
    pagination = body.get("pagination")
    assert isinstance(pagination, dict), f"pagination manquant : {body}"
    for key in ("page", "per_page", "total", "pages"):
        assert key in pagination, f"pagination.{key} manquant : {pagination}"
    return pagination


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Crée une application FastAPI de test."""
    application = FastAPI()
    # STORY-127 : exceptions typées → handler global requis
    application.add_exception_handler(WindFlowException, windflow_exception_handler)
    application.include_router(router, prefix="/api/v1/docker")
    application.dependency_overrides[get_current_active_user] = (
        lambda: _make_mock_user()
    )
    # STORY-122.2 : routes Docker protégées par require_* — délégation au
    # même provider (mini-app sans DB ; RBAC couvert par test_docker_rbac.py)
    for _rbac_dep in (require_viewer, require_operator, require_admin):
        application.dependency_overrides[_rbac_dep] = lambda: _make_mock_user()
    return application


@pytest.fixture
def unauth_app():
    """App sans authentification (401) pour les tests de sécurité."""
    application = FastAPI()
    # STORY-127 : exceptions typées → handler global requis
    application.add_exception_handler(WindFlowException, windflow_exception_handler)
    application.include_router(router, prefix="/api/v1/docker")
    application.dependency_overrides[get_current_active_user] = lambda: _raise_401()
    for _rbac_dep in (require_viewer, require_operator, require_admin):
        application.dependency_overrides[_rbac_dep] = lambda: _raise_401()
    return application


# ===========================================================================
# TestContainerPagination
# ===========================================================================


class TestContainerPagination:
    """Tests de pagination pour GET /docker/containers (contrat STORY-128)."""

    @pytest.mark.asyncio
    async def test_default_pagination_returns_20(self, app):
        """Sans paramètres, retourne les 20 premiers éléments (défaut spec 09)."""
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
        body = response.json()
        pagination = _assert_pagination_contract(body)
        assert len(body["data"]) == 20
        assert pagination["page"] == 1
        assert pagination["per_page"] == 20
        assert pagination["total"] == 60
        assert pagination["pages"] == 3

    @pytest.mark.asyncio
    async def test_page_2_skips_first_page(self, app):
        """page=2 saute les 20 premiers éléments sur 60 mockés."""
        containers = [_make_container_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_containers = AsyncMock(return_value=containers)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/containers?page=2")

        assert response.status_code == 200
        body = response.json()
        _assert_pagination_contract(body)
        assert len(body["data"]) == 20
        assert body["data"][0]["id"] == "container0020"

    @pytest.mark.asyncio
    async def test_per_page_parameter_works(self, app):
        """per_page=5 retourne exactement 5 éléments."""
        containers = [_make_container_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_containers = AsyncMock(return_value=containers)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/containers?per_page=5")

        assert response.status_code == 200
        body = response.json()
        pagination = _assert_pagination_contract(body)
        assert len(body["data"]) == 5
        assert pagination["per_page"] == 5
        assert pagination["pages"] == 12

    @pytest.mark.asyncio
    async def test_page_and_per_page_combined(self, app):
        """page=2&per_page=10 retourne 10 éléments à partir du 11ème."""
        containers = [_make_container_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_containers = AsyncMock(return_value=containers)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/containers?page=2&per_page=10")

        assert response.status_code == 200
        body = response.json()
        _assert_pagination_contract(body)
        assert len(body["data"]) == 10
        assert body["data"][0]["id"] == "container0010"
        assert body["data"][9]["id"] == "container0019"

    @pytest.mark.asyncio
    async def test_beyond_last_page_returns_empty(self, app):
        """page au-delà de la dernière → 200 avec data: [] et méta exactes."""
        containers = [_make_container_info(i) for i in range(10)]

        mock_client = AsyncMock()
        mock_client.list_containers = AsyncMock(return_value=containers)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/containers?page=99")

        assert response.status_code == 200
        body = response.json()
        pagination = _assert_pagination_contract(body)
        assert body["data"] == []
        assert pagination["total"] == 10
        assert pagination["pages"] == 1

    @pytest.mark.asyncio
    async def test_per_page_1_returns_single(self, app):
        """per_page=1 retourne exactement 1 élément."""
        containers = [_make_container_info(i) for i in range(10)]

        mock_client = AsyncMock()
        mock_client.list_containers = AsyncMock(return_value=containers)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/containers?per_page=1")

        assert response.status_code == 200
        body = response.json()
        _assert_pagination_contract(body)
        assert len(body["data"]) == 1
        assert body["data"][0]["id"] == "container0000"

    @pytest.mark.asyncio
    async def test_pagination_returns_401_without_token(self, unauth_app):
        """Sécurité : accès sans authentification → 401."""
        async with AsyncClient(
            transport=ASGITransport(app=unauth_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/containers")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_page_zero_returns_422(self, app):
        """Validation : page=0 → 422 (pagination 1-indexée)."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/containers?page=0")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_per_page_zero_returns_422(self, app):
        """Validation : per_page=0 → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/containers?per_page=0")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_per_page_over_100_returns_422(self, app):
        """Validation : per_page=101 → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/containers?per_page=101")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_legacy_skip_limit_rejected(self, app):
        """STORY-128 : les paramètres legacy skip/limit ne sont plus admis
        (ignorés par FastAPI — le contrat est page/per_page uniquement).
        skip=-1&limit=0 n'invalide plus la requête : vérifie que la réponse
        reste 200 avec le contrat paginé (les query params inconnus sont
        ignorés par FastAPI, comportement standard)."""
        containers = [_make_container_info(i) for i in range(5)]

        mock_client = AsyncMock()
        mock_client.list_containers = AsyncMock(return_value=containers)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/containers?limit=1")

        assert response.status_code == 200
        body = response.json()
        pagination = _assert_pagination_contract(body)
        # limit inconnu → defaults paginés appliqués (20 max sur 5 items)
        assert len(body["data"]) == 5
        assert pagination["total"] == 5


# ===========================================================================
# TestImagePagination
# ===========================================================================


class TestImagePagination:
    """Tests de pagination pour GET /docker/images (contrat STORY-128)."""

    @pytest.mark.asyncio
    async def test_default_pagination_returns_20(self, app):
        """Sans paramètres, retourne les 20 premières images (défaut spec 09)."""
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
        body = response.json()
        pagination = _assert_pagination_contract(body)
        assert len(body["data"]) == 20
        assert pagination["total"] == 60
        assert pagination["pages"] == 3

    @pytest.mark.asyncio
    async def test_page_and_per_page_combined(self, app):
        """page=2&per_page=10 retourne 10 images à partir de la 11ème."""
        images = [_make_image_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_images = AsyncMock(return_value=images)
        mock_client.list_containers = AsyncMock(return_value=[])
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/images?page=2&per_page=10")

        assert response.status_code == 200
        body = response.json()
        _assert_pagination_contract(body)
        assert len(body["data"]) == 10
        assert body["data"][0]["id"] == f"img{10:012d}"
        assert body["data"][9]["id"] == f"img{19:012d}"

    @pytest.mark.asyncio
    async def test_pagination_returns_401_without_token(self, unauth_app):
        """Sécurité : accès sans authentification → 401."""
        async with AsyncClient(
            transport=ASGITransport(app=unauth_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/images")

        assert response.status_code == 401


# ===========================================================================
# TestVolumePagination
# ===========================================================================


class TestVolumePagination:
    """Tests de pagination pour GET /docker/volumes (contrat STORY-128)."""

    @pytest.mark.asyncio
    async def test_default_pagination_returns_20(self, app):
        """Sans paramètres, retourne les 20 premiers volumes (défaut spec 09)."""
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
        body = response.json()
        pagination = _assert_pagination_contract(body)
        assert len(body["data"]) == 20
        assert pagination["total"] == 60
        assert pagination["pages"] == 3

    @pytest.mark.asyncio
    async def test_page_and_per_page_combined(self, app):
        """page=2&per_page=10 retourne 10 volumes à partir du 11ème."""
        volumes = [_make_volume_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_volumes = AsyncMock(return_value=volumes)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/volumes?page=2&per_page=10")

        assert response.status_code == 200
        body = response.json()
        _assert_pagination_contract(body)
        assert len(body["data"]) == 10
        assert body["data"][0]["name"] == "volume-10"
        assert body["data"][9]["name"] == "volume-19"

    @pytest.mark.asyncio
    async def test_pagination_returns_401_without_token(self, unauth_app):
        """Sécurité : accès sans authentification → 401."""
        async with AsyncClient(
            transport=ASGITransport(app=unauth_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/volumes")

        assert response.status_code == 401


# ===========================================================================
# TestNetworkPagination
# ===========================================================================


class TestNetworkPagination:
    """Tests de pagination pour GET /docker/networks (contrat STORY-128)."""

    @pytest.mark.asyncio
    async def test_default_pagination_returns_20(self, app):
        """Sans paramètres, retourne les 20 premiers réseaux (défaut spec 09)."""
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
        body = response.json()
        pagination = _assert_pagination_contract(body)
        assert len(body["data"]) == 20
        assert pagination["total"] == 60
        assert pagination["pages"] == 3

    @pytest.mark.asyncio
    async def test_page_and_per_page_combined(self, app):
        """page=2&per_page=10 retourne 10 réseaux à partir du 11ème."""
        networks = [_make_network_info(i) for i in range(60)]

        mock_client = AsyncMock()
        mock_client.list_networks = AsyncMock(return_value=networks)
        mock_client.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/v1/docker/networks?page=2&per_page=10")

        assert response.status_code == 200
        body = response.json()
        _assert_pagination_contract(body)
        assert len(body["data"]) == 10
        assert body["data"][0]["name"] == "network-10"
        assert body["data"][9]["name"] == "network-19"

    @pytest.mark.asyncio
    async def test_pagination_returns_401_without_token(self, unauth_app):
        """Sécurité : accès sans authentification → 401."""
        async with AsyncClient(
            transport=ASGITransport(app=unauth_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/docker/networks")

        assert response.status_code == 401
