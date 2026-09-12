"""Tests unitaires de la dépendance WebSocket ``require_role_ws(...)`` (STORY-122.1).

Couverture : rôle global insuffisant → ``WebSocketException`` 1008 au
handshake (« policy violation », pattern ``get_current_user_ws``), jamais
d'utilisateur anonyme ; rôle suffisant → utilisateur retourné.

L'appel direct de la dépendance avec un user patché isole la vérification
de rôle (la chaîne ``get_current_user_ws`` est couverte par
``test_ws_auth.py``).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketException

from app.auth.rbac import require_role_ws
from app.models.user import User
from app.services.authorization_service import AuthorizationService


def _viewer_user() -> User:
    return User(
        id="ws-viewer-id",
        email="viewer@test.com",
        username="ws-viewer",
        is_superuser=False,
        is_active=True,
    )


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    # get_global_role est patché — la session n'est jamais réellement requêtée
    return session


class TestRequireRoleWsInsufficientRole:
    """Rôle insuffisant → WebSocketException 1008 au handshake."""

    async def test_viewer_refused_on_admin_channel(self):
        """viewer sur canal admin → 1008 « Insufficient permissions »."""
        websocket = MagicMock()
        websocket.url.path = "/ws/admin-test"

        checker = require_role_ws("admin")
        user = _viewer_user()

        with patch.object(
            AuthorizationService,
            "get_global_role",
            AsyncMock(return_value="viewer"),
        ):
            with pytest.raises(WebSocketException) as exc_info:
                await checker(
                    websocket=websocket,
                    current_user=user,
                    session=_mock_session(),
                )

        assert exc_info.value.code == 1008
        assert exc_info.value.reason == "Insufficient permissions"

    async def test_operator_refused_on_super_admin_channel(self):
        """operator sur canal super_admin → 1008."""
        websocket = MagicMock()
        websocket.url.path = "/ws/instance-test"

        checker = require_role_ws("super_admin")
        user = _viewer_user()

        with patch.object(
            AuthorizationService,
            "get_global_role",
            AsyncMock(return_value="operator"),
        ):
            with pytest.raises(WebSocketException) as exc_info:
                await checker(
                    websocket=websocket,
                    current_user=user,
                    session=_mock_session(),
                )

        assert exc_info.value.code == 1008


class TestRequireRoleWsSufficientRole:
    """Rôle suffisant → utilisateur retourné (handshake poursuivi)."""

    async def test_admin_passes_on_admin_channel(self):
        """admin sur canal admin → user retourné tel quel."""
        websocket = MagicMock()
        websocket.url.path = "/ws/admin-test"

        checker = require_role_ws("admin")
        user = _viewer_user()

        with patch.object(
            AuthorizationService,
            "get_global_role",
            AsyncMock(return_value="admin"),
        ):
            returned = await checker(
                websocket=websocket,
                current_user=user,
                session=_mock_session(),
            )

        assert returned is user

    async def test_super_admin_passes_everywhere(self):
        """super_admin sur canal super_admin → OK."""
        websocket = MagicMock()
        websocket.url.path = "/ws/instance-test"

        checker = require_role_ws("super_admin")
        user = _viewer_user()

        with patch.object(
            AuthorizationService,
            "get_global_role",
            AsyncMock(return_value="super_admin"),
        ):
            returned = await checker(
                websocket=websocket,
                current_user=user,
                session=_mock_session(),
            )

        assert returned is user


class TestRequireRoleWsConstruction:
    """Validation de minimum_role à la construction (erreur dev)."""

    def test_unknown_role_raises_assertion_error(self):
        """Rôle inconnu → AssertionError (paramètre code-only)."""
        with pytest.raises(AssertionError, match="Unknown minimum role"):
            require_role_ws("root")
