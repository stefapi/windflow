"""Tests pour les endpoints d'actions de stack (start/stop/redeploy)."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import error_message, unwrap

from app.models.organization import Organization
from app.models.stack import Stack


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 122.2.

    Le fichier ``.env`` local (git-ignored) peut contenir ``DISABLE_AUTH=true``
    (valeur recommandée par ``env.example`` pour le dev). Sans ce forçage,
    ``get_current_user`` court-circuite le JWT pour chercher un superadmin
    en base → 500 ``INTERNAL_ERROR`` sur tous les endpoints authentifiés.
    """

    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


# ─── Helpers ─────────────────────────────────────────────────────────


class MockContainer:
    """Mock d'un container Docker avec les attributs nécessaires."""

    def __init__(self, container_id: str, name: str, state: str, stack_id: str):
        self.id = container_id
        self.name = name
        self.state = state
        self.labels = {"windflow.stack_id": stack_id}


def _make_docker_mock(
    containers=None,
    ping_ok=True,
    start_side_effect=None,
    stop_side_effect=None,
):
    """Crée un mock AsyncMock de DockerClientService configuré."""
    mock = AsyncMock()
    mock.ping.return_value = ping_ok
    mock.list_containers.return_value = containers or []
    if start_side_effect is not None:
        mock.start_container.side_effect = start_side_effect
    if stop_side_effect is not None:
        mock.stop_container.side_effect = stop_side_effect
    mock.close.return_value = None
    return mock


# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
async def second_organization(db_session: AsyncSession) -> Organization:
    """Crée une seconde organisation pour les tests cross-org."""
    org = Organization(
        name="Second Organization",
        slug="second-org",
        description="Second org for stack action tests",
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


# ─── TestStartStack ──────────────────────────────────────────────────


class TestStartStack:
    """Tests pour POST /api/v1/stacks/{stack_id}/start."""

    @pytest.mark.asyncio
    async def test_start_stack_success(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Démarre les containers d'une stack existante → 200, success=True."""
        containers = [
            MockContainer("c1", "web", "stopped", test_stack.id),
            MockContainer("c2", "db", "stopped", test_stack.id),
        ]
        mock_docker = _make_docker_mock(containers=containers)

        with patch("app.api.v1.stacks.DockerClientService", return_value=mock_docker):
            response = await authenticated_client.post(
                f"/api/v1/stacks/{test_stack.id}/start",
            )

        assert response.status_code == 200
        data = unwrap(response)
        assert data["success"] is True
        assert data["action"] == "start"
        assert data["affected_services"] > 0
        assert data["stack_id"] == test_stack.id

    @pytest.mark.asyncio
    async def test_start_stack_no_containers(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Stack sans containers Docker → 200, affected_services=0."""
        mock_docker = _make_docker_mock(containers=[])

        with patch("app.api.v1.stacks.DockerClientService", return_value=mock_docker):
            response = await authenticated_client.post(
                f"/api/v1/stacks/{test_stack.id}/start",
            )

        assert response.status_code == 200
        data = unwrap(response)
        assert data["success"] is True
        assert data["affected_services"] == 0
        assert "aucun container" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_start_stack_partial_error(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Un container échoue au démarrage → 200, success=False."""
        containers = [
            MockContainer("c1", "web", "stopped", test_stack.id),
            MockContainer("c2", "db", "stopped", test_stack.id),
        ]
        mock_docker = _make_docker_mock(
            containers=containers,
            start_side_effect=[None, Exception("Container db: start failed")],
        )

        with patch("app.api.v1.stacks.DockerClientService", return_value=mock_docker):
            response = await authenticated_client.post(
                f"/api/v1/stacks/{test_stack.id}/start",
            )

        assert response.status_code == 200
        data = unwrap(response)
        assert data["success"] is False
        assert "erreur" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_start_stack_not_found(
        self,
        authenticated_client: AsyncClient,
    ):
        """Stack inexistante → 404."""
        response = await authenticated_client.post(
            "/api/v1/stacks/nonexistent-id/start",
        )

        assert response.status_code == 404
        assert "non trouvée" in error_message(response).lower()

    @pytest.mark.asyncio
    async def test_start_stack_unauthenticated(
        self,
        client: AsyncClient,
        test_stack: Stack,
    ):
        """Appel sans token → 401."""
        response = await client.post(
            f"/api/v1/stacks/{test_stack.id}/start",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_start_stack_forbidden_org(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        second_organization: Organization,
    ):
        """Stack d'une autre organisation → 403."""
        stack = Stack(
            name="Other Org Stack",
            description="Stack in another org",
            template={"version": "3.8", "services": {}},
            variables={},
            organization_id=second_organization.id,
        )
        db_session.add(stack)
        await db_session.commit()
        await db_session.refresh(stack)

        response = await authenticated_client.post(
            f"/api/v1/stacks/{stack.id}/start",
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_start_stack_docker_unavailable(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Docker indisponible → 503."""
        mock_docker = _make_docker_mock(ping_ok=False)

        with patch("app.api.v1.stacks.DockerClientService", return_value=mock_docker):
            response = await authenticated_client.post(
                f"/api/v1/stacks/{test_stack.id}/start",
            )

        assert response.status_code == 503


# ─── TestStopStack ───────────────────────────────────────────────────


class TestStopStack:
    """Tests pour POST /api/v1/stacks/{stack_id}/stop."""

    @pytest.mark.asyncio
    async def test_stop_stack_success(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Arrête les containers running → 200, success=True."""
        containers = [
            MockContainer("c1", "web", "running", test_stack.id),
            MockContainer("c2", "db", "running", test_stack.id),
        ]
        mock_docker = _make_docker_mock(containers=containers)

        with patch("app.api.v1.stacks.DockerClientService", return_value=mock_docker):
            response = await authenticated_client.post(
                f"/api/v1/stacks/{test_stack.id}/stop",
            )

        assert response.status_code == 200
        data = unwrap(response)
        assert data["success"] is True
        assert data["action"] == "stop"
        assert data["affected_services"] > 0

    @pytest.mark.asyncio
    async def test_stop_stack_no_containers(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Stack sans containers → 200, affected_services=0."""
        mock_docker = _make_docker_mock(containers=[])

        with patch("app.api.v1.stacks.DockerClientService", return_value=mock_docker):
            response = await authenticated_client.post(
                f"/api/v1/stacks/{test_stack.id}/stop",
            )

        assert response.status_code == 200
        data = unwrap(response)
        assert data["success"] is True
        assert data["affected_services"] == 0

    @pytest.mark.asyncio
    async def test_stop_stack_partial_error(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Un container échoue à l'arrêt → 200, success=False."""
        containers = [
            MockContainer("c1", "web", "running", test_stack.id),
            MockContainer("c2", "db", "running", test_stack.id),
        ]
        mock_docker = _make_docker_mock(
            containers=containers,
            stop_side_effect=[None, Exception("Container db: stop failed")],
        )

        with patch("app.api.v1.stacks.DockerClientService", return_value=mock_docker):
            response = await authenticated_client.post(
                f"/api/v1/stacks/{test_stack.id}/stop",
            )

        assert response.status_code == 200
        data = unwrap(response)
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_stop_stack_not_found(
        self,
        authenticated_client: AsyncClient,
    ):
        """Stack inexistante → 404."""
        response = await authenticated_client.post(
            "/api/v1/stacks/nonexistent-id/stop",
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_stop_stack_unauthenticated(
        self,
        client: AsyncClient,
        test_stack: Stack,
    ):
        """Appel sans token → 401."""
        response = await client.post(
            f"/api/v1/stacks/{test_stack.id}/stop",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_stop_stack_forbidden_org(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        second_organization: Organization,
    ):
        """Stack d'une autre organisation → 403."""
        stack = Stack(
            name="Other Org Stack Stop",
            description="Stack in another org",
            template={"version": "3.8", "services": {}},
            variables={},
            organization_id=second_organization.id,
        )
        db_session.add(stack)
        await db_session.commit()
        await db_session.refresh(stack)

        response = await authenticated_client.post(
            f"/api/v1/stacks/{stack.id}/stop",
        )

        assert response.status_code == 403


# ─── TestRedeployStack ───────────────────────────────────────────────


class TestRedeployStack:
    """Tests pour POST /api/v1/stacks/{stack_id}/redeploy."""

    @pytest.mark.asyncio
    async def test_redeploy_stack_stop_start(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Stratégie stop_start (défaut) → 200, success=True."""
        containers = [
            MockContainer("c1", "web", "running", test_stack.id),
            MockContainer("c2", "db", "running", test_stack.id),
        ]
        mock_docker = _make_docker_mock(containers=containers)

        with patch("app.api.v1.stacks.DockerClientService", return_value=mock_docker):
            response = await authenticated_client.post(
                f"/api/v1/stacks/{test_stack.id}/redeploy",
                json={},
            )

        assert response.status_code == 200
        data = unwrap(response)
        assert data["success"] is True
        assert data["action"] == "redeploy"
        assert data["strategy"] == "stop_start"
        assert data["affected_services"] > 0

    @pytest.mark.asyncio
    async def test_redeploy_stack_rolling(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Stratégie rolling → 200, affected_services correct."""
        containers = [
            MockContainer("c1", "web", "running", test_stack.id),
            MockContainer("c2", "db", "running", test_stack.id),
        ]
        mock_docker = _make_docker_mock(containers=containers)

        with patch("app.api.v1.stacks.DockerClientService", return_value=mock_docker):
            response = await authenticated_client.post(
                f"/api/v1/stacks/{test_stack.id}/redeploy",
                json={"strategy": "rolling"},
            )

        assert response.status_code == 200
        data = unwrap(response)
        assert data["success"] is True
        assert data["strategy"] == "rolling"
        assert data["affected_services"] == 2

    @pytest.mark.asyncio
    async def test_redeploy_stack_no_containers(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Stack sans containers → 200, affected_services=0."""
        mock_docker = _make_docker_mock(containers=[])

        with patch("app.api.v1.stacks.DockerClientService", return_value=mock_docker):
            response = await authenticated_client.post(
                f"/api/v1/stacks/{test_stack.id}/redeploy",
            )

        assert response.status_code == 200
        data = unwrap(response)
        assert data["success"] is True
        assert data["affected_services"] == 0

    @pytest.mark.asyncio
    async def test_redeploy_stack_not_found(
        self,
        authenticated_client: AsyncClient,
    ):
        """Stack inexistante → 404."""
        response = await authenticated_client.post(
            "/api/v1/stacks/nonexistent-id/redeploy",
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_redeploy_stack_unauthenticated(
        self,
        client: AsyncClient,
        test_stack: Stack,
    ):
        """Appel sans token → 401."""
        response = await client.post(
            f"/api/v1/stacks/{test_stack.id}/redeploy",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_redeploy_stack_forbidden_org(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        second_organization: Organization,
    ):
        """Stack d'une autre organisation → 403."""
        stack = Stack(
            name="Other Org Stack Redeploy",
            description="Stack in another org",
            template={"version": "3.8", "services": {}},
            variables={},
            organization_id=second_organization.id,
        )
        db_session.add(stack)
        await db_session.commit()
        await db_session.refresh(stack)

        response = await authenticated_client.post(
            f"/api/v1/stacks/{stack.id}/redeploy",
        )

        assert response.status_code == 403
