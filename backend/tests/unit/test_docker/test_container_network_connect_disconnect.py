"""
Tests unitaires pour POST /docker/containers/{container_id}/networks/connect
et POST /docker/containers/{container_id}/networks/disconnect.
STORY-026 : Backend — Endpoints connect/disconnect réseau

Couvre les cas nominaux, d'erreur, de validation et les appels service.
Pattern : FastAPI app + httpx AsyncClient + mock get_docker_client.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.docker import router
from app.auth.dependencies import get_current_active_user
from app.auth.rbac import require_admin, require_operator, require_viewer

# =============================================================================
# Fixtures
# =============================================================================


def _make_mock_user():
    """Crée un mock utilisateur authentifié."""
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_user.email = "test@example.com"
    mock_user.is_active = True
    return mock_user


@pytest.fixture
def mock_docker_client():
    """Crée un mock DockerClientService avec les méthodes network connect/disconnect."""
    client = AsyncMock()
    client.connect_container_to_network.return_value = None
    client.disconnect_container_from_network.return_value = None
    client.close.return_value = None
    return client


@pytest.fixture
def app():
    """Crée une app FastAPI minimale avec le router Docker."""
    _app = FastAPI()
    _app.include_router(router, prefix="/api/v1/docker")
    _app.dependency_overrides[get_current_active_user] = lambda: _make_mock_user()
    # STORY-122.2 : routes Docker protégées par require_* — délégation au
    # même provider (mini-app sans DB ; RBAC couvert par test_docker_rbac.py)
    for _rbac_dep in (require_viewer, require_operator, require_admin):
        _app.dependency_overrides[_rbac_dep] = lambda: _make_mock_user()
    return _app


# =============================================================================
# Tests — Cas nominaux (connect)
# =============================================================================


@pytest.mark.asyncio
async def test_connect_network_success(app, mock_docker_client):
    """Connecte un container à un réseau avec network_id valide → 204."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/connect",
                json={"network_id": "net123"},
            )

    assert response.status_code == 204
    mock_docker_client.connect_container_to_network.assert_called_once_with(
        network_id="net123",
        container_id="abc123",
        aliases=None,
        ipv4_address=None,
    )
    mock_docker_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_connect_network_with_aliases(app, mock_docker_client):
    """Connecte avec aliases réseau → 204."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/connect",
                json={"network_id": "net123", "aliases": ["web", "app"]},
            )

    assert response.status_code == 204
    mock_docker_client.connect_container_to_network.assert_called_once_with(
        network_id="net123",
        container_id="abc123",
        aliases=["web", "app"],
        ipv4_address=None,
    )


@pytest.mark.asyncio
async def test_connect_network_with_ipv4(app, mock_docker_client):
    """Connecte avec IP fixe → 204."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/connect",
                json={"network_id": "net123", "ipv4_address": "172.18.0.10"},
            )

    assert response.status_code == 204
    mock_docker_client.connect_container_to_network.assert_called_once_with(
        network_id="net123",
        container_id="abc123",
        aliases=None,
        ipv4_address="172.18.0.10",
    )


@pytest.mark.asyncio
async def test_connect_network_with_all_options(app, mock_docker_client):
    """Connecte avec aliases + IP fixe → 204."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/connect",
                json={
                    "network_id": "net123",
                    "aliases": ["web"],
                    "ipv4_address": "172.18.0.10",
                },
            )

    assert response.status_code == 204
    mock_docker_client.connect_container_to_network.assert_called_once_with(
        network_id="net123",
        container_id="abc123",
        aliases=["web"],
        ipv4_address="172.18.0.10",
    )


# =============================================================================
# Tests — Cas nominaux (disconnect)
# =============================================================================


@pytest.mark.asyncio
async def test_disconnect_network_success(app, mock_docker_client):
    """Déconnecte un container d'un réseau → 204."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/disconnect",
                json={"network_id": "net123"},
            )

    assert response.status_code == 204
    mock_docker_client.disconnect_container_from_network.assert_called_once_with(
        network_id="net123",
        container_id="abc123",
        force=False,
    )
    mock_docker_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_disconnect_network_with_force(app, mock_docker_client):
    """Déconnecte avec force=True → 204."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/disconnect",
                json={"network_id": "net123", "force": True},
            )

    assert response.status_code == 204
    mock_docker_client.disconnect_container_from_network.assert_called_once_with(
        network_id="net123",
        container_id="abc123",
        force=True,
    )


# =============================================================================
# Tests — Erreurs Docker (connect)
# =============================================================================


@pytest.mark.asyncio
async def test_connect_network_container_not_found(app, mock_docker_client):
    """Container inexistant → Docker API 404 → 404."""
    mock_docker_client.connect_container_to_network.side_effect = (
        aiohttp.ClientResponseError(
            MagicMock(), (), status=404, message="container not found"
        )
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/missing-container/networks/connect",
                json={"network_id": "net123"},
            )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_connect_network_network_not_found(app, mock_docker_client):
    """Réseau inexistant → Docker API 404 → 404."""
    mock_docker_client.connect_container_to_network.side_effect = (
        aiohttp.ClientResponseError(
            MagicMock(), (), status=404, message="network not found"
        )
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/connect",
                json={"network_id": "missing-network"},
            )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_connect_network_docker_error(app, mock_docker_client):
    """Erreur Docker générique (500) → 500."""
    mock_docker_client.connect_container_to_network.side_effect = (
        aiohttp.ClientResponseError(
            MagicMock(), (), status=500, message="internal server error"
        )
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/connect",
                json={"network_id": "net123"},
            )

    assert response.status_code == 500


# =============================================================================
# Tests — Erreurs Docker (disconnect)
# =============================================================================


@pytest.mark.asyncio
async def test_disconnect_network_container_not_found(app, mock_docker_client):
    """Container inexistant → Docker API 404 → 404."""
    mock_docker_client.disconnect_container_from_network.side_effect = (
        aiohttp.ClientResponseError(
            MagicMock(), (), status=404, message="container not found"
        )
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/missing-container/networks/disconnect",
                json={"network_id": "net123"},
            )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_disconnect_network_network_not_found(app, mock_docker_client):
    """Réseau inexistant → Docker API 404 → 404."""
    mock_docker_client.disconnect_container_from_network.side_effect = (
        aiohttp.ClientResponseError(
            MagicMock(), (), status=404, message="network not found"
        )
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/disconnect",
                json={"network_id": "missing-network"},
            )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_disconnect_network_docker_error(app, mock_docker_client):
    """Erreur Docker générique (500) → 500."""
    mock_docker_client.disconnect_container_from_network.side_effect = (
        aiohttp.ClientResponseError(
            MagicMock(), (), status=500, message="internal server error"
        )
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/disconnect",
                json={"network_id": "net123"},
            )

    assert response.status_code == 500


# =============================================================================
# Tests — Validation (sécurité)
# =============================================================================


@pytest.mark.asyncio
async def test_connect_network_empty_network_id(app, mock_docker_client):
    """network_id vide → 422."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/connect",
                json={"network_id": ""},
            )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_connect_network_missing_network_id(app, mock_docker_client):
    """Body sans network_id → 422."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/connect",
                json={},
            )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_connect_network_invalid_body(app, mock_docker_client):
    """Body complètement invalide → 422."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/connect",
                content="not json",
                headers={"Content-Type": "application/json"},
            )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_disconnect_network_empty_network_id(app, mock_docker_client):
    """network_id vide → 422."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/disconnect",
                json={"network_id": ""},
            )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_disconnect_network_missing_network_id(app, mock_docker_client):
    """Body sans network_id → 422."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/disconnect",
                json={},
            )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_disconnect_network_invalid_body(app, mock_docker_client):
    """Body complètement invalide → 422."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123/networks/disconnect",
                content="not json",
                headers={"Content-Type": "application/json"},
            )

    assert response.status_code == 422


# =============================================================================
# Tests — Service (DockerClientService)
# =============================================================================


@pytest.mark.asyncio
async def test_service_connect_calls_correct_endpoint():
    """Vérifie l'appel POST /networks/{id}/connect avec le bon body."""
    from app.services.docker_client_service import DockerClientService

    service = DockerClientService()
    service._request = AsyncMock()

    await service.connect_container_to_network(
        network_id="net123",
        container_id="abc123",
    )

    service._request.assert_called_once_with(
        "POST",
        "/networks/net123/connect",
        body={"Container": "abc123", "EndpointConfig": {}},
    )


@pytest.mark.asyncio
async def test_service_disconnect_calls_correct_endpoint():
    """Vérifie l'appel POST /networks/{id}/disconnect avec le bon body."""
    from app.services.docker_client_service import DockerClientService

    service = DockerClientService()
    service._request = AsyncMock()

    await service.disconnect_container_from_network(
        network_id="net456",
        container_id="def789",
    )

    service._request.assert_called_once_with(
        "POST",
        "/networks/net456/disconnect",
        body={"Container": "def789", "Force": False},
    )


@pytest.mark.asyncio
async def test_service_connect_with_aliases():
    """Vérifie que les aliases sont inclus dans EndpointConfig."""
    from app.services.docker_client_service import DockerClientService

    service = DockerClientService()
    service._request = AsyncMock()

    await service.connect_container_to_network(
        network_id="net123",
        container_id="abc123",
        aliases=["web", "app"],
    )

    service._request.assert_called_once_with(
        "POST",
        "/networks/net123/connect",
        body={
            "Container": "abc123",
            "EndpointConfig": {"Aliases": ["web", "app"]},
        },
    )


@pytest.mark.asyncio
async def test_service_connect_with_ipv4():
    """Vérifie que l'IP est incluse dans IPAMConfig."""
    from app.services.docker_client_service import DockerClientService

    service = DockerClientService()
    service._request = AsyncMock()

    await service.connect_container_to_network(
        network_id="net123",
        container_id="abc123",
        ipv4_address="172.18.0.10",
    )

    service._request.assert_called_once_with(
        "POST",
        "/networks/net123/connect",
        body={
            "Container": "abc123",
            "EndpointConfig": {
                "IPAMConfig": {"IPv4Address": "172.18.0.10"},
            },
        },
    )


@pytest.mark.asyncio
async def test_service_disconnect_with_force():
    """Vérifie que Force est passé dans le body."""
    from app.services.docker_client_service import DockerClientService

    service = DockerClientService()
    service._request = AsyncMock()

    await service.disconnect_container_from_network(
        network_id="net123",
        container_id="abc123",
        force=True,
    )

    service._request.assert_called_once_with(
        "POST",
        "/networks/net123/disconnect",
        body={"Container": "abc123", "Force": True},
    )
