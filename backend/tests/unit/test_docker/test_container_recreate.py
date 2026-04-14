"""
Tests unitaires pour POST /docker/containers/{container_id}/recreate.
STORY-025 : Endpoint de recréation de container

Couvre les cas nominaux, d'erreur et de validation du schéma.
Pattern : FastAPI app + httpx AsyncClient + mock get_docker_client.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.docker import router
from app.services.docker_client_service import ContainerDetail


# =============================================================================
# Fixtures
# =============================================================================


def _make_container_detail(
    container_id: str = "abc123def456",
    name: str = "test-container",
    image: str = "nginx:latest",
    env: list[str] | None = None,
    labels: dict[str, str] | None = None,
    cmd: list[str] | None = None,
    mounts: list[dict] | None = None,
    host_config: dict | None = None,
    network_settings: dict | None = None,
    state: dict | None = None,
) -> ContainerDetail:
    """Crée un ContainerDetail factice pour les tests."""
    return ContainerDetail(
        id=container_id[:12],
        name=name,
        created=datetime.now(timezone.utc),
        path="/usr/sbin/nginx",
        args=["-g", "daemon off;"],
        state=state or {"Status": "running", "Running": True},
        image=image,
        config={
            "Image": image,
            "Env": env or ["PATH=/usr/local/bin:/usr/bin"],
            "Labels": labels or {"app": "test"},
            "Cmd": cmd or ["nginx", "-g", "daemon off;"],
            "Entrypoint": None,
        },
        host_config=host_config or {
            "NetworkMode": "bridge",
            "RestartPolicy": {"Name": "unless-stopped"},
            "Privileged": False,
            "ReadonlyRootfs": False,
            "CapAdd": None,
            "CapDrop": None,
            "PortBindings": {"80/tcp": [{"HostPort": "8080"}]},
        },
        network_settings=network_settings or {"Networks": {}},
        mounts=mounts or [
            {"Type": "volume", "Source": "data-vol", "Destination": "/data", "Mode": "rw"},
        ],
        size_rw=1024,
        size_root_fs=51200,
    )


@pytest.fixture
def mock_docker_client():
    """Crée un mock DockerClientService avec les méthodes nécessaires."""
    client = AsyncMock()

    old_detail = _make_container_detail(container_id="abc123def456")
    new_detail = _make_container_detail(
        container_id="new123new456",
        name="test-container",
    )

    def _get_container(cid):
        if cid == "new123new456":
            return new_detail
        return old_detail

    client.get_container.side_effect = _get_container
    client.create_container.return_value = "new123new456"
    client.start_container.return_value = None
    client.stop_container.return_value = None
    client.remove_container.return_value = None
    client.pull_image.return_value = "Pull complete"
    client.close.return_value = None

    async def _recreate_container(container_id, **kwargs):
        """Simule le flow : inspect → merge → stop → remove → create → start → get."""
        detail = await client.get_container(container_id)

        merged_image = kwargs.get("image") or detail.config.get("Image", "")
        merged_env = kwargs.get("env") if kwargs.get("env") is not None else detail.config.get("Env", [])
        merged_labels = kwargs.get("labels") if kwargs.get("labels") is not None else detail.config.get("Labels", {})

        if kwargs.get("pull_image") and merged_image:
            await client.pull_image(merged_image)

        try:
            await client.stop_container(container_id, timeout=kwargs.get("stop_timeout", 10))
        except Exception:
            pass
        await client.remove_container(container_id, force=True, remove_volumes=False)

        new_id = await client.create_container(
            name=detail.name,
            image=merged_image,
            command=detail.config.get("Cmd"),
            env=merged_env,
            labels=merged_labels,
        )

        await client.start_container(new_id)
        new_detail = await client.get_container(new_id)
        return new_id, new_detail

    client.recreate_container = AsyncMock(side_effect=_recreate_container)

    return client


@pytest.fixture
def app():
    """Crée une app FastAPI minimale avec le router Docker."""
    _app = FastAPI()
    _app.include_router(router, prefix="/api/v1/docker")
    return _app


# =============================================================================
# Tests — Cas nominaux
# =============================================================================


@pytest.mark.asyncio
async def test_recreate_success_no_overrides(app, mock_docker_client):
    """Recreate sans overrides → merge complet, recréation OK."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["old_container_id"] == "abc123def456"
    assert data["new_container_id"] == "new123new456"
    assert data["container"]["id"] == "new123new456"


@pytest.mark.asyncio
async def test_recreate_with_image_override(app, mock_docker_client):
    """Changement d'image nginx:latest → nginx:1.26."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={"image": "nginx:1.26"},
            )

    assert response.status_code == 200
    call_kwargs = mock_docker_client.create_container.call_args
    assert call_kwargs[1]["image"] == "nginx:1.26"


@pytest.mark.asyncio
async def test_recreate_with_env_override(app, mock_docker_client):
    """Override des variables d'environnement."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={"env": ["FOO=bar", "BAZ=qux"]},
            )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_recreate_with_labels_override(app, mock_docker_client):
    """Override des labels."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={"labels": {"app": "updated", "version": "2.0"}},
            )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_recreate_with_port_bindings_override(app, mock_docker_client):
    """Override des port bindings."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={"port_bindings": {"443/tcp": [{"HostPort": "8443"}]}},
            )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_recreate_mounts_preserved(app, mock_docker_client):
    """Les volumes/bind mounts du container original sont préservés (AC 9)."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={},
            )

    assert response.status_code == 200
    mock_docker_client.remove_container.assert_called_once_with(
        "abc123def456", force=True, remove_volumes=False,
    )


@pytest.mark.asyncio
async def test_recreate_privileged_and_caps(app, mock_docker_client):
    """Override privileged, cap_add, cap_drop."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={
                    "privileged": True,
                    "cap_add": ["NET_ADMIN", "SYS_PTRACE"],
                    "cap_drop": ["MKNOD"],
                },
            )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_recreate_readonly_rootfs(app, mock_docker_client):
    """Override readonly_rootfs."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={"readonly_rootfs": True},
            )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_recreate_with_pull_image(app, mock_docker_client):
    """pull_image=True déclenche un appel à pull_image() (AC 3)."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={"pull_image": True},
            )

    assert response.status_code == 200
    mock_docker_client.pull_image.assert_called()


@pytest.mark.asyncio
async def test_recreate_auto_start(app, mock_docker_client):
    """Vérifie que start_container est appelé après création (AC 5)."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={},
            )

    assert response.status_code == 200
    mock_docker_client.start_container.assert_called()


@pytest.mark.asyncio
async def test_recreate_response_contains_ids(app, mock_docker_client):
    """Vérifie old_container_id et new_container_id dans la réponse (AC 6)."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={},
            )

    data = response.json()
    assert "old_container_id" in data
    assert "new_container_id" in data
    assert data["old_container_id"] == "abc123def456"
    assert data["new_container_id"] == "new123new456"


# =============================================================================
# Tests — Cas d'erreur
# =============================================================================


@pytest.mark.asyncio
async def test_recreate_container_not_found(app, mock_docker_client):
    """Container inexistant → 404 (AC 7)."""
    mock_docker_client.recreate_container.side_effect = aiohttp.ClientResponseError(
        MagicMock(), (), status=404, message="Not Found",
    )

    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/nonexistent/recreate",
                json={},
            )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_recreate_stop_fails(app, mock_docker_client):
    """Erreur générale → 500."""
    mock_docker_client.recreate_container.side_effect = RuntimeError("Stop failed")

    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={},
            )

    assert response.status_code == 500


@pytest.mark.asyncio
async def test_recreate_remove_succeeds_create_fails(app, mock_docker_client):
    """Chemin critique : remove OK mais create échoue → 500 avec détail (AC 8)."""
    mock_docker_client.recreate_container.side_effect = RuntimeError(
        "Container abc123def456 was removed but the new container "
        "could not be created: image not found"
    )

    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={"image": "nonexistent:latest"},
            )

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "abc123def456" in detail


@pytest.mark.asyncio
async def test_recreate_remove_succeeds_start_fails(app, mock_docker_client):
    """Chemin critique : remove + create OK mais start échoue → 500."""
    mock_docker_client.recreate_container.side_effect = RuntimeError(
        "Container abc123def456 was removed, new container new123new456 "
        "was created but could not be started: port already in use"
    )

    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={},
            )

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "abc123def456" in detail


# =============================================================================
# Tests — Validation schéma
# =============================================================================


@pytest.mark.asyncio
async def test_recreate_schema_validation_stop_timeout_too_high(app, mock_docker_client):
    """stop_timeout > 300 → 422 Validation Error."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={"stop_timeout": 999},
            )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_recreate_schema_validation_negative_stop_timeout(app, mock_docker_client):
    """stop_timeout < 0 → 422 Validation Error."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={"stop_timeout": -1},
            )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_recreate_schema_validation_invalid_type(app, mock_docker_client):
    """Type invalide pour pull_image → 422."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    with patch("app.api.v1.docker.get_docker_client", return_value=mock_docker_client):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/docker/containers/abc123def456/recreate",
                json={"pull_image": "not_a_boolean"},
            )

    assert response.status_code == 422
