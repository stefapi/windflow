"""
Tests de sécurité de l'authentification WebSocket (STORY-100 — P0-1).

Vérifie que les 5 canaux WebSocket refusent les connexions sans token valide :
- Canaux dédiés (query param `?token=`) : refus au handshake via la dépendance
  stricte `get_current_user_ws` (WebSocketException 1008).
- Canaux « premier message » (général, terminal) : close 1008 via le helper
  centralisé `authenticate_ws_first_message`.

Couvre : sans token, token invalide, token expiré (mock), utilisateur inactif,
token valide, et mode dev `DISABLE_AUTH=true` (auto-login superadmin).
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketException
from fastapi.testclient import TestClient

from app.auth import dependencies as auth_dependencies
from app.auth.dependencies import (
    authenticate_ws_first_message,
    get_current_user_ws,
)
from app.main import app
from app.models.user import User


def _make_user(
    user_id: str = "user-1",
    active: bool = True,
    superadmin: bool = False,
    org_id: str = "org-1",
) -> User:
    """Construit un User non-persisté pour les tests."""
    return User(
        id=user_id,
        email="user@test.com",
        username="testuser",
        is_active=active,
        is_superuser=superadmin,
        organization_id=org_id,
    )


def _make_token_data(user_id: str = "user-1") -> MagicMock:
    """Construit un TokenData simulé."""
    token_data = MagicMock()
    token_data.user_id = user_id
    return token_data


@pytest.fixture()
def ws_client():
    """Client de test sync pour les WebSockets (sans lifespan : pas de DB réelle)."""
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _override_db():
    """Override de get_db par une session mockée (aucune DB réelle nécessaire)."""
    from app.database import get_db

    session = AsyncMock()

    async def override():
        yield session

    app.dependency_overrides[get_db] = override
    return session


def _mock_database_session():
    """Retourne un mock de database.session() (context manager async)."""
    mock_db = MagicMock()
    mock_database = MagicMock()
    mock_database.session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_database.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_database.session


def _deployment_access_patched(channel: str):
    """
    Pour le canal deployment : mock verify_deployment_access (RBAC ressource)
    afin d'isoler l'authentification du reste du flux.

    Les autres canaux n'utilisent pas cette fonction : le context manager
    est alors un no-op.
    """
    from contextlib import ExitStack

    if "/deployments/" not in channel:
        return ExitStack()

    deployment = MagicMock()
    deployment.updated_at = None
    deployment.status = "running"
    deployment.id = "dep-1"
    deployment.name = "test-deployment"

    return patch(
        "app.websocket.deployment_logs.verify_deployment_access",
        new=AsyncMock(return_value=deployment),
    )


# ============================================================================
# Canaux dédiés : refus au handshake (dépendance stricte)
# ============================================================================


class TestWsDedicatedChannelsAuth:
    """Sécurité : les 3 canaux dédiés refusent le handshake sans token valide."""

    CHANNELS = [
        "/api/v1/ws/deployments/dep-1/logs",
        "/api/v1/ws/docker/containers/c1/logs",
        "/api/v1/ws/docker/containers/c1/stats",
    ]

    @pytest.mark.parametrize("channel", CHANNELS)
    def test_ws_connection_refused_without_token(self, ws_client, channel):
        """Sécurité AC 4 : sans ?token= → handshake refusé (1008)."""
        _override_db()
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with pytest.raises(Exception) as exc_info:
                with ws_client.websocket_connect(channel):
                    pass  # ne doit jamais s'exécuter
            # WebSocketDisconnect (refus du handshake) — code 1008 côté serveur
            assert exc_info.value is not None

    @pytest.mark.parametrize("channel", CHANNELS)
    def test_ws_connection_refused_with_invalid_token(self, ws_client, channel):
        """Sécurité AC 4 : token indécodable → handshake refusé (1008)."""
        _override_db()
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies, "decode_access_token", return_value=None
            ):
                with pytest.raises(Exception):
                    with ws_client.websocket_connect(channel + "?token=invalid.jwt"):
                        pass

    @pytest.mark.parametrize("channel", CHANNELS)
    def test_ws_connection_refused_with_expired_token(self, ws_client, channel):
        """Sécurité : token expiré (decode → None) → handshake refusé (1008)."""
        _override_db()
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies, "decode_access_token", return_value=None
            ):
                with pytest.raises(Exception):
                    with ws_client.websocket_connect(channel + "?token=expired.jwt"):
                        pass

    @pytest.mark.parametrize("channel", CHANNELS)
    def test_ws_connection_refused_with_inactive_user(self, ws_client, channel):
        """Sécurité : token valide mais utilisateur inactif → handshake refusé."""
        _override_db()
        inactive_user = _make_user(active=False)
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value=_make_token_data(),
            ):
                with patch.object(
                    auth_dependencies.UserService,
                    "get_by_id",
                    AsyncMock(return_value=inactive_user),
                ):
                    with pytest.raises(Exception):
                        with ws_client.websocket_connect(channel + "?token=valid.jwt"):
                            pass

    @pytest.mark.parametrize("channel", CHANNELS)
    def test_ws_connection_accepted_with_valid_token(self, ws_client, channel):
        """Cas nominal : token valide + utilisateur actif → handshake accepté."""
        _override_db()
        valid_user = _make_user()
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value=_make_token_data(),
            ):
                with patch.object(
                    auth_dependencies.UserService,
                    "get_by_id",
                    AsyncMock(return_value=valid_user),
                ):
                    with patch.object(
                        auth_dependencies.database,
                        "session",
                        _mock_database_session(),
                    ):
                        with _deployment_access_patched(channel):
                            # Docker / déploiement indisponibles en test : la
                            # connexion doit être acceptée puis fermée avec un
                            # message d'erreur applicatif — PAS refusée au
                            # handshake.
                            with ws_client.websocket_connect(
                                channel + "?token=valid.jwt"
                            ) as ws:
                                # Le premier message doit être une erreur
                                # applicative (Docker indisponible), pas un
                                # refus d'authentification
                                message = ws.receive_json()
                                assert message["type"] in ("error", "status", "initial")

    @pytest.mark.parametrize("channel", CHANNELS)
    def test_ws_connection_accepted_in_disable_auth_mode(self, ws_client, channel):
        """AC 2 : DISABLE_AUTH=true + superadmin en base → accepté sans token."""
        _override_db()
        superadmin = _make_user(superadmin=True)
        with patch.object(auth_dependencies.settings, "disable_auth", True):
            with patch.object(
                auth_dependencies.UserService,
                "get_first_superadmin",
                AsyncMock(return_value=superadmin),
            ):
                with patch.object(
                    auth_dependencies.database,
                    "session",
                    _mock_database_session(),
                ):
                    with _deployment_access_patched(channel):
                        with ws_client.websocket_connect(channel) as ws:
                            message = ws.receive_json()
                            assert message["type"] in (
                                "error",
                                "status",
                                "initial",
                            )

    @pytest.mark.parametrize("channel", CHANNELS)
    def test_ws_connection_refused_in_disable_auth_mode_without_superadmin(
        self, ws_client, channel
    ):
        """DISABLE_AUTH=true mais aucun superadmin → handshake refusé."""
        _override_db()
        with patch.object(auth_dependencies.settings, "disable_auth", True):
            with patch.object(
                auth_dependencies.UserService,
                "get_first_superadmin",
                AsyncMock(return_value=None),
            ):
                with pytest.raises(Exception):
                    with ws_client.websocket_connect(channel):
                        pass


# ============================================================================
# Canaux « premier message » : général et terminal
# ============================================================================


class TestWsFirstMessageChannelsAuth:
    """Sécurité : les canaux général et terminal exigent l'auth au 1er message."""

    GENERAL = "/api/v1/ws/"
    TERMINAL = "/api/v1/ws/terminal/c1"

    @pytest.fixture(autouse=True)
    def _short_timeout(self):
        """Réduit le timeout d'auth à 0.3 s pour des tests rapides."""
        original = auth_dependencies.WS_AUTH_TIMEOUT_SECONDS
        auth_dependencies.WS_AUTH_TIMEOUT_SECONDS = 0.3
        yield
        auth_dependencies.WS_AUTH_TIMEOUT_SECONDS = original

    def test_ws_connection_closed_without_auth_message(self, ws_client):
        """Sécurité : connexion acceptée puis silence → close 1008 après timeout."""
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with ws_client.websocket_connect(self.GENERAL) as ws:
                with pytest.raises(Exception):
                    # Aucun message envoyé : le serveur ferme (1008) au timeout
                    ws.receive_json()

    def test_ws_connection_closed_with_invalid_token_in_first_message(self, ws_client):
        """Sécurité : token invalide dans le 1er message → close 1008."""
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies, "decode_access_token", return_value=None
            ):
                with ws_client.websocket_connect(self.GENERAL) as ws:
                    ws.send_json({"type": "auth", "token": "invalid.jwt"})
                    with pytest.raises(Exception):
                        ws.receive_json()

    def test_ws_connection_closed_when_first_message_is_not_auth(self, ws_client):
        """Sécurité : 1er message ≠ auth → close 1008."""
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with ws_client.websocket_connect(self.GENERAL) as ws:
                ws.send_json({"type": "ping"})
                with pytest.raises(Exception):
                    ws.receive_json()

    def test_ws_connection_closed_with_invalid_json_first_message(self, ws_client):
        """Sécurité : 1er message non-JSON → close 1008."""
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with ws_client.websocket_connect(self.GENERAL) as ws:
                ws.send_text("not-json{{")
                with pytest.raises(Exception):
                    ws.receive_json()

    def test_ws_connection_accepted_with_valid_token_first_message(self, ws_client):
        """Cas nominal : auth valide au 1er message → AUTH_LOGIN_SUCCESS."""
        valid_user = _make_user()
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value=_make_token_data(),
            ):
                with patch.object(
                    auth_dependencies.UserService,
                    "get_by_id",
                    AsyncMock(return_value=valid_user),
                ):
                    with ws_client.websocket_connect(self.GENERAL) as ws:
                        ws.send_json({"type": "auth", "token": "valid.jwt"})
                        response = ws.receive_json()
                        assert response["type"] == "AUTH_LOGIN_SUCCESS"
                        assert response["data"]["user_id"] == "user-1"
                        assert response["data"]["username"] == "testuser"

    def test_ws_connection_closed_with_inactive_user_first_message(self, ws_client):
        """Sécurité : token valide mais utilisateur inactif → close 1008."""
        inactive_user = _make_user(active=False)
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value=_make_token_data(),
            ):
                with patch.object(
                    auth_dependencies.UserService,
                    "get_by_id",
                    AsyncMock(return_value=inactive_user),
                ):
                    with ws_client.websocket_connect(self.GENERAL) as ws:
                        ws.send_json({"type": "auth", "token": "valid.jwt"})
                        with pytest.raises(Exception):
                            ws.receive_json()

    def test_ws_connection_accepted_in_disable_auth_mode(self, ws_client):
        """AC 2 : DISABLE_AUTH=true + 1er message auth → auto-login superadmin."""
        superadmin = _make_user(superadmin=True)
        with patch.object(auth_dependencies.settings, "disable_auth", True):
            with patch.object(
                auth_dependencies.UserService,
                "get_first_superadmin",
                AsyncMock(return_value=superadmin),
            ):
                with ws_client.websocket_connect(self.GENERAL) as ws:
                    ws.send_json({"type": "auth", "token": "ignored-in-dev"})
                    response = ws.receive_json()
                    assert response["type"] == "AUTH_LOGIN_SUCCESS"
                    assert response["data"]["user_id"] == "user-1"

    def test_general_ws_auth_login_success_payload(self, ws_client):
        """AC 3 : contenu du message AUTH_LOGIN_SUCCESS = user/username/org."""
        valid_user = _make_user()
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value=_make_token_data(),
            ):
                with patch.object(
                    auth_dependencies.UserService,
                    "get_by_id",
                    AsyncMock(return_value=valid_user),
                ):
                    with ws_client.websocket_connect(self.GENERAL) as ws:
                        ws.send_json({"type": "auth", "token": "valid.jwt"})
                        response = ws.receive_json()
                        assert response["type"] == "AUTH_LOGIN_SUCCESS"
                        assert response["data"]["organization_id"] == "org-1"

    def test_terminal_closed_with_invalid_token_first_message(self, ws_client):
        """Sécurité : terminal + token invalide → message d'erreur puis close 1008."""
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies, "decode_access_token", return_value=None
            ):
                with ws_client.websocket_connect(self.TERMINAL) as ws:
                    ws.send_json({"type": "auth", "token": "invalid.jwt"})
                    # Le terminal envoie son message d'erreur (audit callback)
                    # AVANT la fermeture 1008 — comportement préservé pour xterm
                    message = ws.receive_json()
                    assert message["type"] == "error"
                    # Puis la connexion est fermée (1008)
                    with pytest.raises(Exception):
                        ws.receive_json()

    def test_terminal_accepted_with_valid_token(self, ws_client):
        """Cas nominal terminal : auth valide → message terminal (ready/error)."""
        valid_user = _make_user(superadmin=True)
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value=_make_token_data(),
            ):
                with patch.object(
                    auth_dependencies.UserService,
                    "get_by_id",
                    AsyncMock(return_value=valid_user),
                ):
                    with ws_client.websocket_connect(self.TERMINAL) as ws:
                        ws.send_json({"type": "auth", "token": "valid.jwt"})
                        # Docker indisponible en test : le terminal répondra par
                        # une erreur applicative (pas un refus d'authentification)
                        message = ws.receive_json()
                        assert message["type"] in ("ready", "error")

    def test_terminal_audit_logged_on_auth_failure(self, ws_client):
        """Audit : échec d'auth terminal → log_terminal_audit appelé (connect échoué)."""
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies, "decode_access_token", return_value=None
            ):
                with patch(
                    "app.websocket.terminal.log_terminal_audit",
                    new_callable=AsyncMock,
                ) as mock_audit:
                    with ws_client.websocket_connect(self.TERMINAL) as ws:
                        ws.send_json({"type": "auth", "token": "invalid.jwt"})
                        # Message d'erreur envoyé par le callback d'audit, puis close
                        message = ws.receive_json()
                        assert message["type"] == "error"
                        with pytest.raises(Exception):
                            ws.receive_json()
                    mock_audit.assert_awaited_once()
                    args = mock_audit.await_args.args
                    assert args[3] == "connect"
                    assert args[4] is False


# ============================================================================
# Tests unitaires directs des dépendances
# ============================================================================


class TestGetCurrentUserWsUnit:
    """Tests unitaires du nouveau contrat strict de get_current_user_ws."""

    @pytest.mark.asyncio
    async def test_refuses_without_token(self):
        """Sécurité : sans token et disable_auth=false → WebSocketException 1008."""
        websocket = MagicMock()
        websocket.url.path = "/api/v1/ws/"
        session = AsyncMock()

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with pytest.raises(WebSocketException) as exc_info:
                await get_current_user_ws(
                    websocket=websocket, token=None, session=session
                )

        assert exc_info.value.code == 1008

    @pytest.mark.asyncio
    async def test_refuses_with_invalid_token(self):
        """Sécurité : token indécodable → WebSocketException 1008."""
        websocket = MagicMock()
        websocket.url.path = "/api/v1/ws/"
        session = AsyncMock()

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies, "decode_access_token", return_value=None
            ):
                with pytest.raises(WebSocketException) as exc_info:
                    await get_current_user_ws(
                        websocket=websocket, token="invalid.jwt", session=session
                    )

        assert exc_info.value.code == 1008

    @pytest.mark.asyncio
    async def test_refuses_inactive_user(self):
        """Sécurité : utilisateur inactif → WebSocketException 1008."""
        websocket = MagicMock()
        websocket.url.path = "/api/v1/ws/"
        session = AsyncMock()
        inactive_user = _make_user(active=False)

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value=_make_token_data(),
            ):
                with patch.object(
                    auth_dependencies.UserService,
                    "get_by_id",
                    AsyncMock(return_value=inactive_user),
                ):
                    with pytest.raises(WebSocketException) as exc_info:
                        await get_current_user_ws(
                            websocket=websocket, token="valid.jwt", session=session
                        )

        assert exc_info.value.code == 1008

    @pytest.mark.asyncio
    async def test_returns_user_with_disable_auth(self):
        """AC 2 : disable_auth=true → auto-login superadmin."""
        websocket = MagicMock()
        websocket.url.path = "/api/v1/ws/"
        session = AsyncMock()
        superadmin = _make_user(superadmin=True)

        with patch.object(auth_dependencies.settings, "disable_auth", True):
            with patch.object(
                auth_dependencies.UserService,
                "get_first_superadmin",
                AsyncMock(return_value=superadmin),
            ):
                user = await get_current_user_ws(
                    websocket=websocket, token=None, session=session
                )

        assert user.id == "user-1"

    @pytest.mark.asyncio
    async def test_refuses_in_disable_auth_mode_without_superadmin(self):
        """disable_auth=true mais aucun superadmin → WebSocketException 1008."""
        websocket = MagicMock()
        websocket.url.path = "/api/v1/ws/"
        session = AsyncMock()

        with patch.object(auth_dependencies.settings, "disable_auth", True):
            with patch.object(
                auth_dependencies.UserService,
                "get_first_superadmin",
                AsyncMock(return_value=None),
            ):
                with pytest.raises(WebSocketException) as exc_info:
                    await get_current_user_ws(
                        websocket=websocket, token=None, session=session
                    )

        assert exc_info.value.code == 1008

    @pytest.mark.asyncio
    async def test_returns_valid_user_with_valid_token(self):
        """Cas nominal : token valide + utilisateur actif → User retourné."""
        websocket = MagicMock()
        websocket.url.path = "/api/v1/ws/"
        session = AsyncMock()
        valid_user = _make_user()

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value=_make_token_data(),
            ):
                with patch.object(
                    auth_dependencies.UserService,
                    "get_by_id",
                    AsyncMock(return_value=valid_user),
                ):
                    user = await get_current_user_ws(
                        websocket=websocket, token="valid.jwt", session=session
                    )

        assert user.id == "user-1"


class TestAuthenticateWsFirstMessageUnit:
    """Tests unitaires du helper d'auth « premier message »."""

    @pytest.mark.asyncio
    async def test_timeout_closes_with_1008(self):
        """Helper : silence au-delà du timeout → close 1008, retourne None."""
        websocket = AsyncMock()
        websocket.url.path = "/api/v1/ws/"
        websocket.receive_text = AsyncMock(side_effect=asyncio_timeout_error)

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            result = await authenticate_ws_first_message(websocket)

        assert result is None
        websocket.close.assert_awaited_once_with(
            code=1008, reason="Authentication timeout"
        )

    @pytest.mark.asyncio
    async def test_invalid_json_closes_with_1008(self):
        """Helper : 1er message non-JSON → close 1008."""
        websocket = AsyncMock()
        websocket.url.path = "/api/v1/ws/"
        websocket.receive_text = AsyncMock(return_value="not-json")

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            result = await authenticate_ws_first_message(websocket)

        assert result is None
        websocket.close.assert_awaited_once_with(
            code=1008, reason="Invalid message format"
        )

    @pytest.mark.asyncio
    async def test_receive_error_closes_with_1008(self):
        """Helper : erreur réseau avant auth → close 1008, retourne None."""
        websocket = AsyncMock()
        websocket.url.path = "/api/v1/ws/"
        websocket.receive_text = AsyncMock(side_effect=RuntimeError("boom"))

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            result = await authenticate_ws_first_message(websocket)

        assert result is None
        websocket.close.assert_awaited_once_with(code=1008, reason="Receive error")

    @pytest.mark.asyncio
    async def test_on_failure_error_does_not_prevent_close(self):
        """Helper : si le callback on_failure lève, la close 1008 a quand même lieu."""
        websocket = AsyncMock()
        websocket.url.path = "/api/v1/ws/"
        websocket.receive_text = AsyncMock(return_value="not-json")
        on_failure = AsyncMock(side_effect=RuntimeError("audit broken"))

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            result = await authenticate_ws_first_message(
                websocket, on_failure=on_failure
            )

        assert result is None
        on_failure.assert_awaited_once()
        websocket.close.assert_awaited_once_with(
            code=1008, reason="Invalid message format"
        )

    @pytest.mark.asyncio
    async def test_disable_auth_returns_superadmin_ignoring_token(self):
        """Helper : disable_auth → token ignoré, auto-login superadmin."""
        websocket = AsyncMock()
        websocket.url.path = "/api/v1/ws/"
        websocket.receive_text = AsyncMock(
            return_value=json.dumps({"type": "auth", "token": "whatever"})
        )
        superadmin = _make_user(superadmin=True)
        mock_session = _mock_database_session()

        with patch.object(auth_dependencies.settings, "disable_auth", True):
            with patch.object(
                auth_dependencies.UserService,
                "get_first_superadmin",
                AsyncMock(return_value=superadmin),
            ):
                with patch.object(auth_dependencies.database, "session", mock_session):
                    result = await authenticate_ws_first_message(websocket)

        assert result is not None
        assert result.is_superuser is True

    @pytest.mark.asyncio
    async def test_get_current_user_ws_unexpected_error_refuses(self):
        """Dépendance : erreur inattendue (DB) pendant l'auth → refus 1008 générique."""
        websocket = MagicMock()
        websocket.url.path = "/api/v1/ws/"
        session = AsyncMock()

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies,
                "decode_access_token",
                side_effect=RuntimeError("db exploded"),
            ):
                with pytest.raises(WebSocketException) as exc_info:
                    await get_current_user_ws(
                        websocket=websocket, token="valid.jwt", session=session
                    )

        assert exc_info.value.code == 1008
        assert exc_info.value.reason == "Authentication failed"

    @pytest.mark.asyncio
    async def test_non_auth_message_closes_with_1008(self):
        """Helper : 1er message ≠ auth → close 1008."""
        websocket = AsyncMock()
        websocket.url.path = "/api/v1/ws/"
        websocket.receive_text = AsyncMock(
            return_value=json.dumps({"type": "subscribe"})
        )

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            result = await authenticate_ws_first_message(websocket)

        assert result is None
        websocket.close.assert_awaited_once_with(
            code=1008, reason="Authentication required"
        )

    @pytest.mark.asyncio
    async def test_on_failure_callback_called_before_close(self):
        """Helper : on_failure (audit) appelé avant la fermeture."""
        websocket = AsyncMock()
        websocket.url.path = "/api/v1/ws/"
        websocket.receive_text = AsyncMock(
            return_value=json.dumps({"type": "auth", "token": "bad"})
        )
        on_failure = AsyncMock()

        # Mock de la base globale (non initialisée hors application)
        mock_db_session = AsyncMock()
        mock_database = MagicMock()
        mock_database.session.return_value.__aenter__ = AsyncMock(
            return_value=mock_db_session
        )
        mock_database.session.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies, "decode_access_token", return_value=None
            ):
                with patch.object(auth_dependencies, "database", mock_database):
                    result = await authenticate_ws_first_message(
                        websocket, on_failure=on_failure
                    )

        assert result is None
        on_failure.assert_awaited_once()
        websocket.close.assert_awaited_once()


def asyncio_timeout_error():
    """Side effect simulant un timeout asyncio (levé par wait_for)."""
    import asyncio

    raise asyncio.TimeoutError()
