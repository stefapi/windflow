"""Tests RBAC des 5 canaux WebSocket (STORY-122.6, AC 2 volet WS).

Matrice spec 08 § Apps : terminal/console = Operator+, logs/stats/
déploiements/général = Viewer+ (tout authentifié actif). Vérifie par canal :

- **viewer** : terminal refusé (1008 avant/juste après auth), les 4 autres
  canaux autorisés ;
- **operator+** : terminal accepté (handshake puis réponse applicative) ;
- **admin non-superuser** : terminal accepté ;
- **user inactif** : 1008 partout (non-régression auth) ;
- **DISABLE_AUTH** : auto-login superadmin → terminal accepté ;
- pas de token → refus handshake (canaux dédiés).

Pattern ``test_ws_auth.py`` : mocks HTTP par patch, rôle global piloté via
``AuthorizationService.get_global_role`` (cache reset entre tests).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth import dependencies as auth_dependencies
from app.main import app
from app.models.user import User
from app.services.authorization_service import AuthorizationService

GENERAL = "/api/v1/ws/"
TERMINAL = "/api/v1/ws/terminal/c1"
DEPLOYMENT_LOGS = "/api/v1/ws/deployments/dep-1/logs"
CONTAINER_LOGS = "/api/v1/ws/docker/containers/c1/logs"
CONTAINER_STATS = "/api/v1/ws/docker/containers/c1/stats"

VIEWER_CHANNELS = [
    DEPLOYMENT_LOGS,
    CONTAINER_LOGS,
    CONTAINER_STATS,
]


def _make_user(
    user_id: str = "user-1",
    active: bool = True,
    superadmin: bool = False,
) -> User:
    """User non-persisté pour les tests (pattern test_ws_auth)."""
    return User(
        id=user_id,
        email="user@test.com",
        username="testuser",
        is_active=active,
        is_superuser=superadmin,
    )


def _make_token_data(user_id: str = "user-1") -> MagicMock:
    token_data = MagicMock()
    token_data.user_id = user_id
    return token_data


@pytest.fixture()
def ws_client():
    """Client de test sync pour les WebSockets (sans lifespan : pas de DB réelle)."""
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _fresh_role_cache():
    """Cache de rôles vierge autour de chaque test (rôle patché réellement lu)."""
    from app.core.cache import reset_role_cache

    reset_role_cache()
    yield
    reset_role_cache()


def _override_db():
    """Override de get_db par une session mockée + rôle global patché."""
    from app.database import get_db

    session = AsyncMock()

    async def override():
        yield session

    app.dependency_overrides[get_db] = override
    return session


def _patch_global_role(role: str):
    """Patche la résolution du rôle global (isole le RBAC de la DB)."""
    return patch.object(
        AuthorizationService,
        "get_global_role",
        AsyncMock(return_value=role),
    )


def _mock_database_session():
    """Retourne un mock de database.session() (context manager async)."""
    mock_db = MagicMock()
    mock_database = MagicMock()
    mock_database.session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_database.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_database.session


def _deployment_access_patched():
    """Mock verify_deployment_access (RBAC ressource) pour le canal deployment."""
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
# Terminal : Operator+ requis
# ============================================================================


class TestTerminalOperatorRequired:
    """Matrice : viewer refusé, operator/admin acceptés sur /terminal."""

    def _auth_context(self, user):
        """Empile les patches d'auth « premier message » (décorateur contextlib)."""
        from contextlib import ExitStack

        stack = ExitStack()
        stack.enter_context(
            patch.object(auth_dependencies.settings, "disable_auth", False)
        )
        stack.enter_context(
            patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value=_make_token_data(),
            )
        )
        stack.enter_context(
            patch.object(
                auth_dependencies.UserService,
                "get_by_id",
                AsyncMock(return_value=user),
            )
        )
        stack.enter_context(
            patch.object(
                auth_dependencies.database, "session", _mock_database_session()
            )
        )
        return stack

    def test_viewer_refused_on_terminal(self, ws_client):
        """Sécurité : viewer → message d'erreur puis close 1008 (pas de ready)."""
        _override_db()
        user = _make_user()

        with self._auth_context(user):
            with _patch_global_role("viewer"):
                with ws_client.websocket_connect(TERMINAL) as ws:
                    ws.send_json({"type": "auth", "token": "valid.jwt"})
                    message = ws.receive_json()
                    assert message["type"] == "error"
                    assert "operator" in message["message"].lower()
                    # Puis fermeture par le serveur (1008)
                    with pytest.raises(Exception):
                        ws.receive_json()

    def test_operator_accepted_on_terminal(self, ws_client):
        """Cas nominal : operator → dépasse le check RBAC (réponse ready/error)."""
        _override_db()
        user = _make_user()

        with self._auth_context(user):
            with _patch_global_role("operator"):
                with patch(
                    "app.websocket.terminal.check_terminal_rate_limit",
                    new=AsyncMock(return_value=(True, "")),
                ):
                    with patch(
                        "app.websocket.terminal.TerminalService",
                    ) as mock_service_cls:
                        # Docker indisponible en test : create_session lève
                        # → erreur applicative, PAS un refus RBAC
                        mock_service_cls.return_value.create_session = AsyncMock(
                            side_effect=RuntimeError("docker unavailable")
                        )
                        with ws_client.websocket_connect(TERMINAL) as ws:
                            ws.send_json({"type": "auth", "token": "valid.jwt"})
                            message = ws.receive_json()
                            # L'erreur applicative mentionne docker, pas les
                            # permissions (le check RBAC est passé)
                            assert message["type"] in ("ready", "error")
                            if message["type"] == "error":
                                assert "permission" not in message["message"].lower()

    def test_admin_accepted_on_terminal(self, ws_client):
        """Matrice : admin (non-superuser) → check RBAC passé."""
        _override_db()
        user = _make_user()

        with self._auth_context(user):
            with _patch_global_role("admin"):
                with patch(
                    "app.websocket.terminal.check_terminal_rate_limit",
                    new=AsyncMock(return_value=(True, "")),
                ):
                    with patch(
                        "app.websocket.terminal.TerminalService",
                    ) as mock_service_cls:
                        mock_service_cls.return_value.create_session = AsyncMock(
                            side_effect=RuntimeError("docker unavailable")
                        )
                        with ws_client.websocket_connect(TERMINAL) as ws:
                            ws.send_json({"type": "auth", "token": "valid.jwt"})
                            message = ws.receive_json()
                            assert message["type"] in ("ready", "error")
                            if message["type"] == "error":
                                assert "permission" not in message["message"].lower()

    def test_terminal_audit_logged_on_rbac_refusal(self, ws_client):
        """Audit : refus RBAC terminal → log_terminal_audit (connect échoué)."""
        _override_db()
        user = _make_user()

        with self._auth_context(user):
            with _patch_global_role("viewer"):
                with patch(
                    "app.websocket.terminal.log_terminal_audit",
                    new_callable=AsyncMock,
                ) as mock_audit:
                    with ws_client.websocket_connect(TERMINAL) as ws:
                        ws.send_json({"type": "auth", "token": "valid.jwt"})
                        message = ws.receive_json()
                        assert message["type"] == "error"
                        with pytest.raises(Exception):
                            ws.receive_json()
                    mock_audit.assert_awaited_once()
                    args = mock_audit.await_args.args
                    assert args[3] == "connect"
                    assert args[4] is False
                    assert "operator" in args[5].lower()


# ============================================================================
# Canaux dédiés : viewer minimum (refus avant accept si rôle insuffisant)
# ============================================================================


class TestDedicatedChannelsViewerMinimum:
    """Matrice : les 3 canaux dédiés refusent avant accept si rôle < viewer.

    viewer étant le plancher hiérarchique, aucun rôle valide ne peut être
    refusé — la garde s'assure qu'un rôle inconnu/résolu incohérent (ex.
    ``None`` → hiérarchie -1) est bien refusé 1008 (garde homogène).
    """

    def test_unknown_role_refused_before_accept(self, ws_client):
        """Garde : rôle global résolu inconnu (corruption cache) → 1008
        au handshake, avant acceptation (canal dédié logs)."""
        _override_db()

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value=_make_token_data(),
            ):
                with patch.object(
                    auth_dependencies.UserService,
                    "get_by_id",
                    AsyncMock(return_value=_make_user()),
                ):
                    with _patch_global_role("corrupted-role"):
                        with pytest.raises(Exception):
                            with ws_client.websocket_connect(
                                CONTAINER_LOGS + "?token=valid.jwt"
                            ):
                                pass

    @pytest.mark.parametrize("channel", VIEWER_CHANNELS)
    def test_viewer_accepted_on_read_channels(self, ws_client, channel):
        """Cas nominal : viewer → handshake accepté (erreur applicative
        Docker ensuite, pas un refus RBAC)."""
        _override_db()

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value=_make_token_data(),
            ):
                with patch.object(
                    auth_dependencies.UserService,
                    "get_by_id",
                    AsyncMock(return_value=_make_user()),
                ):
                    with _patch_global_role("viewer"):
                        with patch.object(
                            auth_dependencies.database,
                            "session",
                            _mock_database_session(),
                        ):
                            with _deployment_access_patched():
                                with ws_client.websocket_connect(
                                    channel + "?token=valid.jwt"
                                ) as ws:
                                    message = ws.receive_json()
                                    assert message["type"] in (
                                        "error",
                                        "status",
                                        "initial",
                                    )


# ============================================================================
# Général : viewer minimum (fermeture 1008 après auth premier message)
# ============================================================================


class TestGeneralChannelViewerMinimum:
    """Garde homogène : général = lecture → viewer (tout actif authentifié)."""

    def test_general_accepted_for_viewer(self, ws_client):
        """Cas nominal : viewer authentifié au 1er message → AUTH_LOGIN_SUCCESS."""
        from app.services.user_organization_service import UserOrganizationService

        user = _make_user()

        async def _fake_ids(db, u):
            return ["org-1"]

        async def _fake_primary(db, u):
            return "org-1"

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value=_make_token_data(),
            ):
                with patch.object(
                    auth_dependencies.UserService,
                    "get_by_id",
                    AsyncMock(return_value=user),
                ):
                    with _patch_global_role("viewer"):
                        with patch.object(
                            auth_dependencies.database,
                            "session",
                            _mock_database_session(),
                        ):
                            with patch.object(
                                UserOrganizationService,
                                "get_user_organization_ids",
                                side_effect=_fake_ids,
                            ):
                                with patch.object(
                                    UserOrganizationService,
                                    "get_primary_organization_id",
                                    side_effect=_fake_primary,
                                ):
                                    with ws_client.websocket_connect(GENERAL) as ws:
                                        ws.send_json(
                                            {"type": "auth", "token": "valid.jwt"}
                                        )
                                        response = ws.receive_json()
                                        assert response["type"] == "AUTH_LOGIN_SUCCESS"

    def test_general_refused_for_corrupted_role(self, ws_client):
        """Garde : rôle résolu inconnu → close 1008 après le 1er message."""
        user = _make_user()

        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with patch.object(
                auth_dependencies,
                "decode_access_token",
                return_value=_make_token_data(),
            ):
                with patch.object(
                    auth_dependencies.UserService,
                    "get_by_id",
                    AsyncMock(return_value=user),
                ):
                    with _patch_global_role("corrupted-role"):
                        with patch.object(
                            auth_dependencies.database,
                            "session",
                            _mock_database_session(),
                        ):
                            with ws_client.websocket_connect(GENERAL) as ws:
                                ws.send_json({"type": "auth", "token": "valid.jwt"})
                                with pytest.raises(Exception):
                                    ws.receive_json()


# ============================================================================
# Non-régression : user inactif → 1008 partout
# ============================================================================


class TestInactiveUserRefused:
    """Sécurité : utilisateur inactif → refus sur tous les canaux."""

    @pytest.mark.parametrize(
        "channel",
        VIEWER_CHANNELS,
    )
    def test_inactive_user_refused_dedicated(self, ws_client, channel):
        """Inactif → handshake refusé (canaux dédiés, query param)."""
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

    def test_inactive_user_refused_terminal(self, ws_client):
        """Inactif → 1er message auth → erreur + close 1008 (terminal)."""
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
                    with ws_client.websocket_connect(TERMINAL) as ws:
                        ws.send_json({"type": "auth", "token": "valid.jwt"})
                        message = ws.receive_json()
                        assert message["type"] == "error"
                        with pytest.raises(Exception):
                            ws.receive_json()


# ============================================================================
# DISABLE_AUTH : auto-login superadmin → tout autorisé
# ============================================================================


class TestDisableAuthMode:
    """Mode dev : auto-login superadmin → terminal accepté sans vérification."""

    def test_terminal_accepted_in_disable_auth(self, ws_client):
        """DISABLE_AUTH + 1er message auth → superadmin → RBAC passé."""
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
                    with patch(
                        "app.websocket.terminal.check_terminal_rate_limit",
                        new=AsyncMock(return_value=(True, "")),
                    ):
                        with patch(
                            "app.websocket.terminal.TerminalService",
                        ) as mock_service_cls:
                            mock_service_cls.return_value.create_session = AsyncMock(
                                side_effect=RuntimeError("docker unavailable")
                            )
                            with ws_client.websocket_connect(TERMINAL) as ws:
                                ws.send_json(
                                    {"type": "auth", "token": "ignored-in-dev"}
                                )
                                message = ws.receive_json()
                                assert message["type"] in ("ready", "error")
                                if message["type"] == "error":
                                    assert (
                                        "permission" not in message["message"].lower()
                                    )

    def test_dedicated_channel_accepted_in_disable_auth(self, ws_client):
        """DISABLE_AUTH (canaux dédiés) → superadmin → handshake accepté."""
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
                    with _deployment_access_patched():
                        with ws_client.websocket_connect(CONTAINER_STATS) as ws:
                            message = ws.receive_json()
                            assert message["type"] in ("error", "status", "initial")
