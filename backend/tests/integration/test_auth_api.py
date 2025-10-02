"""Tests d'intégration pour les endpoints d'authentification."""

import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
class TestAuthAPI:
    """Tests d'intégration pour l'API d'authentification."""

    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test de login réussi."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.username,
                "password": "testpassword123"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """Test de login avec mauvais mot de passe."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.username,
                "password": "wrongpassword"
            }
        )

        assert response.status_code == 401
        assert "detail" in response.json()

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test de login avec utilisateur inexistant."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent",
                "password": "password123"
            }
        )

        assert response.status_code == 401
        assert "detail" in response.json()

    async def test_login_missing_credentials(self, client: AsyncClient):
        """Test de login avec credentials manquantes."""
        response = await client.post(
            "/api/v1/auth/login",
            data={}
        )

        assert response.status_code == 422  # Validation error

    async def test_authenticated_request(
        self,
        authenticated_client: AsyncClient
    ):
        """Test d'une requête authentifiée."""
        response = await authenticated_client.get("/api/v1/users/me")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data
        assert "username" in data

    async def test_unauthenticated_request(self, client: AsyncClient):
        """Test d'une requête non authentifiée sur route protégée."""
        response = await client.get("/api/v1/users/me")

        assert response.status_code == 401
        assert "detail" in response.json()

    async def test_invalid_token(self, client: AsyncClient):
        """Test avec token JWT invalide."""
        client.headers.update({"Authorization": "Bearer invalid_token"})
        response = await client.get("/api/v1/users/me")

        assert response.status_code == 401
        assert "detail" in response.json()

    async def test_superuser_access(self, admin_client: AsyncClient):
        """Test d'accès avec droits superuser."""
        response = await admin_client.get("/api/v1/users/me")

        assert response.status_code == 200
        data = response.json()
        assert data["is_superuser"] is True
