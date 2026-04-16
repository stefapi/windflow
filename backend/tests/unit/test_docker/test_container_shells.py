"""
Tests unitaires pour l'endpoint GET /api/v1/docker/containers/{container_id}/shells.

STORY-017 : Détection des shells disponibles dans le terminal.
Teste l'authentification, le schéma de réponse et les cas d'erreur.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.docker import router
from app.auth.dependencies import get_current_active_user
from app.schemas.docker import ContainerShellResponse


def _make_mock_user():
    """Crée un mock utilisateur authentifié."""
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_user.email = "test@example.com"
    mock_user.is_active = True
    return mock_user


class TestContainerShellsEndpoint:
    """Tests pour l'endpoint get_container_shells."""

    @pytest.fixture
    def app(self):
        """Crée une application FastAPI de test."""
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/docker")
        return app

    @pytest.fixture
    def mock_shells(self):
        """Shells de test retournés par le service."""
        from app.services.terminal_service import ShellInfo

        return [
            ShellInfo(path="/bin/bash", label="bash", available=True),
            ShellInfo(path="/bin/sh", label="sh", available=True),
            ShellInfo(path="/bin/zsh", label="zsh", available=False),
        ]

    @pytest.mark.asyncio
    async def test_get_container_shells_returns_401_without_token(self, app):
        """Sécurité : l'endpoint doit refuser l'accès sans token JWT."""
        from app.config import settings
        from app.database import get_db

        async def fake_get_db():
            yield MagicMock()

        app.dependency_overrides[get_db] = fake_get_db

        # Forcer le mode production pour que l'authentification soit requise
        # (en mode dev, get_current_user appelle UserService.get_first_superadmin
        # qui nécessite une vraie session async — inutile pour ce test 401)
        with patch.object(settings, "disable_auth", False):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/v1/docker/containers/abc123/shells"
                )

        app.dependency_overrides.clear()

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_container_shells_authenticated(self, app, mock_shells):
        """Cas nominal : retourne la liste des shells avec authentification valide."""
        mock_terminal_service = MagicMock()
        mock_terminal_service.detect_shells = AsyncMock(return_value=mock_shells)
        mock_terminal_service.close = AsyncMock()

        # Surcharge la dépendance d'authentification
        app.dependency_overrides[get_current_active_user] = lambda: _make_mock_user()

        with patch(
            "app.services.terminal_service.TerminalService",
            return_value=mock_terminal_service,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/docker/containers/abc123/shells")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
        assert data[0]["path"] == "/bin/bash"
        assert data[0]["available"] is True
        assert data[2]["path"] == "/bin/zsh"
        assert data[2]["available"] is False

    @pytest.mark.asyncio
    async def test_get_container_shells_returns_404_for_unknown_container(self, app):
        """Cas d'erreur : container inexistant retourne 404."""
        import aiohttp

        mock_terminal_service = MagicMock()
        error = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=404,
            message="Not Found",
        )
        mock_terminal_service.detect_shells = AsyncMock(side_effect=error)
        mock_terminal_service.close = AsyncMock()

        app.dependency_overrides[get_current_active_user] = lambda: _make_mock_user()

        with patch(
            "app.services.terminal_service.TerminalService",
            return_value=mock_terminal_service,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/v1/docker/containers/nonexistent/shells"
                )

        app.dependency_overrides.clear()

        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_container_shells_response_schema(self, app, mock_shells):
        """Validation : la réponse respecte le schéma ContainerShellResponse."""
        mock_terminal_service = MagicMock()
        mock_terminal_service.detect_shells = AsyncMock(return_value=mock_shells)
        mock_terminal_service.close = AsyncMock()

        app.dependency_overrides[get_current_active_user] = lambda: _make_mock_user()

        with patch(
            "app.services.terminal_service.TerminalService",
            return_value=mock_terminal_service,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/docker/containers/abc123/shells")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        # Valider que chaque élément correspond au schéma ContainerShellResponse
        for item in data:
            schema = ContainerShellResponse(**item)
            assert isinstance(schema.path, str)
            assert isinstance(schema.label, str)
            assert isinstance(schema.available, bool)
