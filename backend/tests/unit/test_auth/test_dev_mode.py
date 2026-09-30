"""
Tests pour le mode développement sans authentification.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.auth.dependencies import get_current_user, get_current_user_ws
from app.core.exceptions import AuthenticationError, WindFlowException
from app.models.user import User
from tests.conftest import unwrap


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
        )

        # Mock de la session DB
        mock_session = AsyncMock()

        # Patch settings.disable_auth et UserService
        with patch("app.auth.dependencies.settings") as mock_settings:
            with patch("app.auth.dependencies.UserService") as mock_user_service:
                # Activer le mode dev
                mock_settings.disable_auth = True

                # Mock de get_first_superadmin
                mock_user_service.get_first_superadmin = AsyncMock(
                    return_value=mock_superadmin
                )

                # Appeler get_current_user (le token n'est pas utilisé en mode dev)
                user = await get_current_user(token="fake-token", session=mock_session)

                # Vérifications
                assert user.id == "test-admin-id"
                assert user.is_superuser is True
                assert user.email == "admin@test.com"
                mock_user_service.get_first_superadmin.assert_called_once_with(
                    mock_session
                )

    async def test_get_current_user_no_superadmin_in_db(self):
        """Test que get_current_user lève une erreur si aucun superadmin en base."""

        # Mock de la session DB
        mock_session = AsyncMock()

        # Patch settings.disable_auth et UserService
        with patch("app.auth.dependencies.settings") as mock_settings:
            with patch("app.auth.dependencies.UserService") as mock_user_service:
                # Activer le mode dev
                mock_settings.disable_auth = True

                # Pas de superadmin en base
                mock_user_service.get_first_superadmin = AsyncMock(return_value=None)

                # Doit lever une WindFlowException typée (STORY-127 : 500
                # INTERNAL_ERROR enveloppé par le handler global)
                with pytest.raises(WindFlowException) as exc_info:
                    await get_current_user(token="fake-token", session=mock_session)

                assert exc_info.value.status_code == 500
                assert "No superadmin user found" in exc_info.value.message

    async def test_get_current_user_ws_with_disable_auth(self):
        """Test que get_current_user_ws retourne le premier superadmin quand DISABLE_AUTH=true."""

        # Mock du superadmin
        mock_superadmin = User(
            id="test-admin-id",
            email="admin@test.com",
            username="admin",
            is_superuser=True,
            is_active=True,
        )

        # Mock de la session DB et WebSocket
        mock_session = AsyncMock()
        mock_websocket = AsyncMock()

        # Patch settings.disable_auth et UserService
        with patch("app.auth.dependencies.settings") as mock_settings:
            with patch("app.auth.dependencies.UserService") as mock_user_service:
                # Activer le mode dev
                mock_settings.disable_auth = True

                # Mock de get_first_superadmin
                mock_user_service.get_first_superadmin = AsyncMock(
                    return_value=mock_superadmin
                )

                # Appeler get_current_user_ws (le token n'est pas utilisé en mode dev)
                user = await get_current_user_ws(
                    websocket=mock_websocket, token=None, session=mock_session
                )

                # Vérifications
                assert user.id == "test-admin-id"
                assert user.is_superuser is True
                mock_user_service.get_first_superadmin.assert_called_once_with(
                    mock_session
                )

    async def test_normal_auth_when_disable_auth_false(self):
        """Test que l'authentification normale fonctionne quand DISABLE_AUTH=false."""

        # Mock de la session DB
        mock_session = AsyncMock()

        # Patch settings.disable_auth
        with patch("app.auth.dependencies.settings") as mock_settings:
            with patch("app.auth.dependencies.decode_access_token") as mock_decode:
                with patch("app.auth.dependencies.UserService") as mock_user_service:
                    # Désactiver le mode dev (mode normal)
                    mock_settings.disable_auth = False

                    # Le flux JWT normal doit être utilisé
                    # On ne devrait PAS appeler get_first_superadmin
                    mock_user_service.get_first_superadmin = AsyncMock()

                    # Simuler un token invalide
                    mock_decode.return_value = None

                    # Doit lever une AuthenticationError typée (STORY-127 :
                    # 401 + WWW-Authenticate portés par la classe)
                    with pytest.raises(AuthenticationError) as exc_info:
                        await get_current_user(
                            token="invalid-token", session=mock_session
                        )

                    assert exc_info.value.status_code == 401
                    # get_first_superadmin ne doit PAS être appelé en mode normal
                    mock_user_service.get_first_superadmin.assert_not_called()

    async def test_dev_auto_login_persists_refresh_token(
        self, client, db_session, test_superuser, monkeypatch
    ):
        """STORY-123.3 (arbitrage n°3) : l'auto-login du mode dev
        persiste la ligne ``refresh_tokens`` (hash, jamais la valeur
        claire) — le flux refresh reste fonctionnel en ``disable_auth``.

        Divergence documentée : l'appel HTTP avec form vide est filtré en
        422 par FastAPI 0.141 (champs form vides traités comme manquants
        — comportement framework vérifié sur app minimale, préexistant à
        123.3) ; le chemin auto-login est donc exercé par appel direct du
        handler avec un ``OAuth2PasswordRequestForm`` aux credentials
        vides, comme le ferait un form correctement parsé.
        """
        from unittest.mock import MagicMock

        from fastapi.security import OAuth2PasswordRequestForm
        from sqlalchemy import select

        from app.api.v1 import auth as auth_module
        from app.models.refresh_token import RefreshToken

        # Même objet settings que celui consommé par login()
        monkeypatch.setattr(auth_module.settings, "disable_auth", True)

        fake_request = MagicMock()
        fake_request.client.host = "127.0.0.1"
        empty_form = OAuth2PasswordRequestForm(username="", password="")

        response = await auth_module.login(
            request=fake_request, form_data=empty_form, session=db_session
        )
        assert response.user.id == test_superuser.id

        rows = (
            (
                await db_session.execute(
                    select(RefreshToken).where(
                        RefreshToken.user_id == test_superuser.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1, "auto-login dev doit persister le hash"
        assert rows[0].token_hash != response.refresh_token
        assert rows[0].token_hash.startswith("$argon2")

        # Le flux refresh HTTP fonctionne avec le token émis en dev
        refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": response.refresh_token},
        )
        assert refresh.status_code == 200, refresh.text
        assert unwrap(refresh)["access_token"]
        assert unwrap(refresh)["refresh_token"] != response.refresh_token
