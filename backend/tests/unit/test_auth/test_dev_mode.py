"""
Tests pour le mode développement sans authentification.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

from app.auth.dependencies import get_current_user, get_current_user_ws
from app.models.user import User
from app.config import settings


@pytest.mark.asyncio
class TestDevMode:
    """Tests du mode développement DISABLE_AUTH."""

    async def test_get_current_user_with_disable_auth(self):
        """Test que get_current_user retourne le premier superadmin quand DISABLE_AUTH=true."""

        # Mock du superadmin
        mock_superadmin = User(
            id="test-admin-id",
            email="admin@test.com",
            username="admin",
            is_superuser=True,
            is_active=True,
            organization_id="org-1"
        )

        # Mock de la session DB
        mock_session = AsyncMock()

        # Patch settings.disable_auth et UserService
        with patch('app.auth.dependencies.settings') as mock_settings:
            with patch('app.auth.dependencies.UserService') as mock_user_service:
                # Activer le mode dev
                mock_settings.disable_auth = True

                # Mock de get_first_superadmin
                mock_user_service.get_first_superadmin = AsyncMock(return_value=mock_superadmin)

                # Appeler get_current_user (le token n'est pas utilisé en mode dev)
                user = await get_current_user(token="fake-token", session=mock_session)

                # Vérifications
                assert user.id == "test-admin-id"
                assert user.is_superuser is True
                assert user.email == "admin@test.com"
                mock_user_service.get_first_superadmin.assert_called_once_with(mock_session)

    async def test_get_current_user_no_superadmin_in_db(self):
        """Test que get_current_user lève une erreur si aucun superadmin en base."""

        # Mock de la session DB
        mock_session = AsyncMock()

        # Patch settings.disable_auth et UserService
        with patch('app.auth.dependencies.settings') as mock_settings:
            with patch('app.auth.dependencies.UserService') as mock_user_service:
                # Activer le mode dev
                mock_settings.disable_auth = True

                # Pas de superadmin en base
                mock_user_service.get_first_superadmin = AsyncMock(return_value=None)

                # Doit lever une HTTPException
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(token="fake-token", session=mock_session)

                assert exc_info.value.status_code == 500
                assert "No superadmin user found" in exc_info.value.detail

    async def test_get_current_user_ws_with_disable_auth(self):
        """Test que get_current_user_ws retourne le premier superadmin quand DISABLE_AUTH=true."""

        # Mock du superadmin
        mock_superadmin = User(
            id="test-admin-id",
            email="admin@test.com",
            username="admin",
            is_superuser=True,
            is_active=True,
            organization_id="org-1"
        )

        # Mock de la session DB et WebSocket
        mock_session = AsyncMock()
        mock_websocket = AsyncMock()

        # Patch settings.disable_auth et UserService
        with patch('app.auth.dependencies.settings') as mock_settings:
            with patch('app.auth.dependencies.UserService') as mock_user_service:
                # Activer le mode dev
                mock_settings.disable_auth = True

                # Mock de get_first_superadmin
                mock_user_service.get_first_superadmin = AsyncMock(return_value=mock_superadmin)

                # Appeler get_current_user_ws (le token n'est pas utilisé en mode dev)
                user = await get_current_user_ws(
                    websocket=mock_websocket,
                    token=None,
                    session=mock_session
                )

                # Vérifications
                assert user.id == "test-admin-id"
                assert user.is_superuser is True
                mock_user_service.get_first_superadmin.assert_called_once_with(mock_session)

    async def test_normal_auth_when_disable_auth_false(self):
        """Test que l'authentification normale fonctionne quand DISABLE_AUTH=false."""

        # Mock de la session DB
        mock_session = AsyncMock()

        # Patch settings.disable_auth
        with patch('app.auth.dependencies.settings') as mock_settings:
            with patch('app.auth.dependencies.decode_access_token') as mock_decode:
                with patch('app.auth.dependencies.UserService') as mock_user_service:
                    # Désactiver le mode dev (mode normal)
                    mock_settings.disable_auth = False

                    # Le flux JWT normal doit être utilisé
                    # On ne devrait PAS appeler get_first_superadmin
                    mock_user_service.get_first_superadmin = AsyncMock()

                    # Simuler un token invalide
                    mock_decode.return_value = None

                    # Doit lever une HTTPException (credentials invalides)
                    with pytest.raises(HTTPException) as exc_info:
                        await get_current_user(token="invalid-token", session=mock_session)

                    assert exc_info.value.status_code == 401
                    # get_first_superadmin ne doit PAS être appelé en mode normal
                    mock_user_service.get_first_superadmin.assert_not_called()
