"""Tests E2E du canal dédié des logs de déploiement (STORY-165 — Tâche 6, AC 4).

Couvre ``app/websocket/deployment_logs.py`` l.104-177 (60 % → ≥ 90 %) —
portage des scénarios §9.2/§9.3 de la spec (WEBSOCKET-REAL-TIME.md) et
**isolation organisationnelle bout-en-bout** :

- **accès autorisé** : statut initial ``{"type": "status", "data":
  {"status", "deployment_id", "name"}}`` (§9.2), ping/pong via la boucle,
  déconnexion propre (``manager.disconnect`` — plus aucune connexion pour le
  deployment_id) ;
- **404** deployment inconnu → message ``{"type": "error", "message":
  "Deployment not found"}`` + **close 1008** ;
- **403** user non-membre de l'org du déploiement → error + close 1008
  (isolation E2E — complément des tests unitaires ``test_ws_isolation_1213.py``) ;
- **401** user None → error + close 1008 (branche défensive) ;
- **superadmin** → accès accordé malgré une org étrangère ;
- **broadcast reçu en cours d'abonnement** : un émetteur one-shot (patch de
  ``periodic_ping``) appelle ``broadcast_deployment_log(dep_id, ...)`` → le
  client du canal dédié reçoit ``DEPLOYMENT_LOGS_UPDATE`` via ``manager`` ;
- **expiration muette** : settings réduits → silence → fermeture serveur ;
- exception dans la boucle → message ``error`` envoyé si possible (l.169-174).

⚠️ **Bug de production documenté (non corrigé — story tests-only)** :
``deployment_logs_websocket_endpoint`` fait ``websocket.accept()`` (l.102)
puis ``manager.connect(websocket, ...)`` (l.115) qui effectue un **second**
``websocket.accept()`` (``connection_managers.py`` l.128). Starlette refuse
le double accept (``application_state`` déjà ACCEPTED) → ``AssertionError``
attrapée par le ``except`` générique → le client reçoit ``error`` au lieu du
statut initial. Les tests auth existants masquaient le bug
(``assert type in ("error", "status", "initial")``). Le bug est démontré par
``test_initial_status_without_connect_workaround`` (xfail strict) ; les
tests nominaux utilisent le contournement ``_register_only_connect`` (patch
de ``manager.connect`` : enregistrement sans accept) pour couvrir la boucle
réelle du canal.

Le handshake est authentifié par la dépendance ``get_current_user_ws``
(query param ``?token=``) puis ``ensure_role_ws("viewer")`` dans le routeur —
mockés via le pattern ``_auth_stack`` de ``test_ws_auth.py``.
"""

from __future__ import annotations

import time
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.auth import dependencies as auth_dependencies
from app.main import app
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.websocket import deployment_logs as deployment_logs_module
from app.websocket.connection_managers import manager

CHANNEL = "/api/v1/ws/deployments/dep-1/logs"

# Bug production (voir docstring module) : le double websocket.accept()
# empêche le parcours nominal. Documenté pour suivi — non corrigé ici.
DOUBLE_ACCEPT_BUG = (
    "BUG production (STORY-165 Tâche 6) : double websocket.accept() sur le "
    "canal deployment_logs — deployment_logs.py l.102 accepte la connexion "
    "puis manager.connect() (connection_managers.py l.128) ré-accepte ; "
    "Starlette lève AssertionError('Expected ASGI message websocket.send or "
    "websocket.close, but got websocket.accept') → le client reçoit error "
    "au lieu du statut initial. Non corrigé : story tests-only."
)


# ===========================================================================
# Helpers (patterns test_ws_auth.py / test_ws_batch.py)
# ===========================================================================


def _make_user(
    user_id: str = "user-1", active: bool = True, superadmin: bool = False
) -> User:
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


def _make_deployment(
    deployment_id: str = "dep-1",
    status: str = "running",
    name: str = "test-deployment",
    updated_at=None,
) -> MagicMock:
    deployment = MagicMock()
    deployment.id = deployment_id
    deployment.status = status
    deployment.name = name
    deployment.updated_at = updated_at
    deployment.organization_id = "org-1"
    return deployment


@pytest.fixture(autouse=True)
def _fresh_role_cache():
    from app.core.cache import reset_role_cache

    reset_role_cache()
    yield
    reset_role_cache()


@pytest.fixture(autouse=True)
def _clean_manager():
    """Manager par déploiement vierge autour de chaque test (isolation)."""
    manager.active_connections.clear()
    yield
    manager.active_connections.clear()


@pytest.fixture()
def ws_client():
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _rbac_empty_roles_result() -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    return result


def _override_db():
    from app.database import get_db

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_rbac_empty_roles_result())

    async def override():
        yield session

    app.dependency_overrides[get_db] = override
    return session


def _mock_database_session(deployment=None) -> MagicMock:
    """Session ``database.session()`` mockée — execute retourne le deployment."""
    mock_db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = deployment
    mock_db.execute = AsyncMock(return_value=result)

    mock_database = MagicMock()
    mock_database.session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_database.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_database.session


def _auth_stack(
    user: User,
    deployment=None,
    *,
    role: str = "viewer",
):
    """Empile auth query-param + RBAC routeur + accès déploiement (via DB mockée).

    ``verify_deployment_access`` n'est PAS patchée : la session mockée
    retourne le deployment et ``UserOrganizationService.is_member`` est
    patchée selon le cas (membre / non-membre).
    """
    stack = ExitStack()
    stack.enter_context(patch.object(auth_dependencies.settings, "disable_auth", False))
    stack.enter_context(
        patch.object(
            auth_dependencies,
            "decode_access_token",
            return_value=_make_token_data(str(user.id)),
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
            auth_dependencies.database,
            "session",
            _mock_database_session(deployment),
        )
    )
    stack.enter_context(
        patch.object(
            AuthorizationService, "get_global_role", AsyncMock(return_value=role)
        )
    )
    # RBAC organisation du canal : is_member piloté par le superuser flag —
    # un superuser est membre partout (bypass interne de is_member).
    from app.services.user_organization_service import UserOrganizationService

    async def _fake_is_member(db, u, org_id):  # noqa: ARG001
        return u.is_superuser or org_id == "org-1"

    stack.enter_context(
        patch.object(UserOrganizationService, "is_member", side_effect=_fake_is_member)
    )
    return stack


def _register_only_connect():
    """Contournement du bug double-accept : ``manager.connect`` sans accept.

    L'endpoint a déjà accepté la connexion (l.102) ; le ``connect`` du
    manager ré-accepte et fait échouer le canal (voir DOUBLE_ACCEPT_BUG).
    Ce patch enregistre la connexion **sans** ré-accepter, ce qui permet de
    couvrir la boucle réelle du canal (statut initial, ping/pong, broadcast,
    expiration) en attendant la correction du bug.
    """

    async def _connect(websocket, deployment_id):
        if deployment_id not in manager.active_connections:
            manager.active_connections[deployment_id] = set()
        manager.active_connections[deployment_id].add(websocket)

    return patch.object(manager, "connect", new=_connect)


def _wait_for(condition, timeout: float = 3.0, interval: float = 0.02):
    """Attend une condition post-fermeture (nettoyage asynchrone côté serveur)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(interval)
    raise AssertionError("condition non remplie dans le délai imparti")


def _emitter_as_heartbeat(deployment_id: str = "dep-1"):
    """Patch one-shot de ``periodic_ping`` : joue l'émetteur de la spec §9.2.

    Attend (borné) que la connexion soit enregistrée auprès du manager
    avant d'émettre ``broadcast_deployment_log`` — même boucle d'événements
    que la WebSocket (pattern ``_emitter_as_heartbeat`` de test_ws_batch.py).
    """

    async def _fake_ping(websocket, channel):  # noqa: ARG001
        import asyncio

        from app.websocket.broadcasting import broadcast_deployment_log

        for _ in range(100):  # borne ~5 s, jamais atteinte en pratique
            if manager.active_connections.get(deployment_id):
                break
            await asyncio.sleep(0.05)

        await broadcast_deployment_log(deployment_id, "step 1/2 pulling images")
        await broadcast_deployment_log(deployment_id, "step 2/2 done", level="warning")

    return patch("app.websocket.deployment_logs.periodic_ping", new=_fake_ping)


# ===========================================================================
# Cas nominal — accès autorisé (portage §9.2)
# ===========================================================================


class TestDeploymentLogsAuthorized:
    """Membre de l'org : statut initial, ping/pong, déconnexion propre.

    Ces tests parcourent la boucle réelle du canal via le contournement
    documenté ``_register_only_connect`` (bug double-accept — voir module).
    """

    def test_initial_status_message_sent_on_connect(self, ws_client):
        """§9.2 : premier message = statut du déploiement (id/name/status)."""
        _override_db()
        user = _make_user()
        deployment = _make_deployment()

        with _auth_stack(user, deployment):
            with _register_only_connect():
                with ws_client.websocket_connect(CHANNEL + "?token=valid.jwt") as ws:
                    status_message = ws.receive_json()
                    assert status_message["type"] == "status"
                    assert status_message["data"] == {
                        "status": "running",
                        "deployment_id": "dep-1",
                        "name": "test-deployment",
                    }
                    # updated_at None → timestamp null (pas de crash).
                    assert status_message["timestamp"] is None

                    # Connexion enregistrée auprès du manager.
                    assert "dep-1" in manager.active_connections

    def test_ping_pong_loop(self, ws_client):
        """Boucle : ping texte client → pong horodaté."""
        _override_db()
        user = _make_user()
        deployment = _make_deployment()

        with _auth_stack(user, deployment):
            with _register_only_connect():
                with ws_client.websocket_connect(CHANNEL + "?token=valid.jwt") as ws:
                    ws.receive_json()  # status
                    ws.send_text("ping")
                    pong = ws.receive_json()
                    assert pong["type"] == "pong"
                    assert "timestamp" in pong

    def test_disconnect_removes_connection_from_manager(self, ws_client):
        """Déconnexion client → manager.disconnect (plus aucune connexion)."""
        _override_db()
        user = _make_user()
        deployment = _make_deployment()

        with _auth_stack(user, deployment):
            with _register_only_connect():
                with ws_client.websocket_connect(CHANNEL + "?token=valid.jwt") as ws:
                    ws.receive_json()  # status
                    assert "dep-1" in manager.active_connections

        _wait_for(lambda: "dep-1" not in manager.active_connections)

    def test_broadcast_log_received_while_subscribed(self, ws_client):
        """§9.2 : log émis depuis la boucle serveur → DEPLOYMENT_LOGS_UPDATE."""
        _override_db()
        user = _make_user()
        deployment = _make_deployment()

        with _auth_stack(user, deployment):
            with _register_only_connect():
                with _emitter_as_heartbeat("dep-1"):
                    with ws_client.websocket_connect(
                        CHANNEL + "?token=valid.jwt"
                    ) as ws:
                        ws.receive_json()  # status

                        messages = []
                        for _ in range(10):
                            message = ws.receive_json()
                            messages.append(message)
                            logs_count = len(
                                [
                                    m
                                    for m in messages
                                    if m["type"] == "DEPLOYMENT_LOGS_UPDATE"
                                ]
                            )
                            if message.get("type") == "DEPLOYMENT_LOGS_UPDATE" and (
                                logs_count >= 2
                            ):
                                break

                        logs = [
                            m for m in messages if m["type"] == "DEPLOYMENT_LOGS_UPDATE"
                        ]
                        assert len(logs) >= 2
                        first, second = logs[0], logs[1]
                        assert first["data"]["logs"] == ["step 1/2 pulling images"]
                        assert first["data"]["level"] == "info"
                        assert second["data"]["level"] == "warning"
                        # Streaming logs : type non critique → pas d'id d'ack.
                        assert "id" not in first

    @pytest.mark.xfail(
        strict=True,
        reason=DOUBLE_ACCEPT_BUG,
    )
    def test_initial_status_without_connect_workaround(self, ws_client):
        """Démontre le bug double-accept : sans contournement, le client
        reçoit ``error`` (et non le statut initial) — Starlette refuse le
        second ``websocket.accept`` émis par ``manager.connect``.

        xfail strict : si le bug est corrigé (``manager.connect`` sans
        accept, ou accept retiré de l'endpoint), ce test XPASS et échoue —
        retirer alors le marquage ET le contournement ``_register_only_connect``.
        """
        _override_db()
        user = _make_user()
        deployment = _make_deployment()

        with _auth_stack(user, deployment):
            with ws_client.websocket_connect(CHANNEL + "?token=valid.jwt") as ws:
                status_message = ws.receive_json()
                assert status_message["type"] == "status"


# ===========================================================================
# Sécurité — refus d'accès → error + close 1008 (isolation E2E)
# ===========================================================================


class TestDeploymentLogsAccessRefusal:
    """404/403/401 : message d'erreur applicatif puis close 1008.

    Ces branches retournent **avant** ``manager.connect`` : aucun
    contournement nécessaire (le bug double-accept ne les atteint pas).
    """

    def test_unknown_deployment_404_error_then_close_1008(self, ws_client):
        """Déploiement introuvable → error « Deployment not found » + 1008."""
        _override_db()
        user = _make_user()
        # DB mockée sans deployment → verify_deployment_access lève 404.

        with _auth_stack(user, deployment=None):
            with ws_client.websocket_connect(CHANNEL + "?token=valid.jwt") as ws:
                error_message = ws.receive_json()
                assert error_message == {
                    "type": "error",
                    "message": "Deployment not found",
                }
                with pytest.raises(WebSocketDisconnect) as exc_info:
                    ws.receive_json()
                assert exc_info.value.code == 1008

    def test_foreign_org_user_403_error_then_close_1008(self, ws_client):
        """Isolation organisationnelle E2E : non-membre → 403 + error + 1008.

        ``is_member`` patchée False : le user authentifié (mais étranger à
        l'org du déploiement) est refusé après le handshake — complément
        bout-en-bout des tests unitaires ``test_ws_isolation_1213.py``.
        """
        _override_db()
        user = _make_user(superadmin=False)
        deployment = _make_deployment()

        from app.services.user_organization_service import UserOrganizationService

        with _auth_stack(user, deployment):
            with patch.object(
                UserOrganizationService,
                "is_member",
                new=AsyncMock(return_value=False),
            ):
                with ws_client.websocket_connect(CHANNEL + "?token=valid.jwt") as ws:
                    error_message = ws.receive_json()
                    assert error_message["type"] == "error"
                    assert (
                        error_message["message"] == "Access denied to this deployment"
                    )
                    with pytest.raises(WebSocketDisconnect) as exc_info:
                        ws.receive_json()
                    assert exc_info.value.code == 1008

        # Aucune connexion résiduelle pour ce déploiement.
        assert "dep-1" not in manager.active_connections

    def test_superadmin_access_granted_on_foreign_org(self, ws_client):
        """Superadmin → bypass : statut initial reçu malgré l'org étrangère."""
        _override_db()
        user = _make_user(superadmin=True)
        deployment = _make_deployment()

        # is_member par défaut du _auth_stack : superuser → True partout.
        with _auth_stack(user, deployment):
            with _register_only_connect():
                with ws_client.websocket_connect(CHANNEL + "?token=valid.jwt") as ws:
                    status_message = ws.receive_json()
                    assert status_message["type"] == "status"
                    assert status_message["data"]["deployment_id"] == "dep-1"

    async def test_none_user_401_unit_branch(self):
        """Branche défensive 401 : user None → HTTPException 401 (verify unitaire).

        Le parcours endpoint ne peut pas produire un user None (la dépendance
        ``get_current_user_ws`` refuse le handshake avant) : la branche est
        couverte directement sur ``verify_deployment_access``.
        """
        from app.websocket.deployment_logs import verify_deployment_access

        deployment = _make_deployment()
        db = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = deployment
        db.execute = AsyncMock(return_value=result)

        with pytest.raises(HTTPException) as exc_info:
            await verify_deployment_access("dep-1", None, db)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required"


# ===========================================================================
# Expiration muette + exception dans la boucle
# ===========================================================================


class TestDeploymentLogsExpiryAndErrors:
    """Silence client → fermeture serveur ; erreur boucle → message error."""

    def test_mute_connection_expired_server_side(self, ws_client):
        """Expiration : client muet → fermeture serveur (timeout réduit)."""
        from app.config import settings

        _override_db()
        user = _make_user()
        deployment = _make_deployment()

        with _auth_stack(user, deployment):
            with _register_only_connect():
                with patch.object(settings, "ws_heartbeat_interval_seconds", 1):
                    with patch.object(settings, "ws_heartbeat_timeout_factor", 1):
                        with ws_client.websocket_connect(
                            CHANNEL + "?token=valid.jwt"
                        ) as ws:
                            ws.receive_json()  # status
                            # Silence client : le serveur ping puis ferme
                            # après expiration — la réception finit par
                            # échouer (pattern test_ws_batch mute expiry).
                            with pytest.raises(Exception):
                                while True:
                                    ws.receive_json()

    async def test_loop_exception_sends_error_message(self):
        """Boucle : exception non WebSocketDisconnect/Heartbeat → error envoyé.

        Le branch l.169-174 exige une exception pendant la boucle (après le
        statut initial) — simulée par un receive_with_expiry qui lève, sans
        WS réelle (websocket mockée : le double accept ne s'applique pas,
        AsyncMock ne valide pas les messages ASGI).
        """
        from app.websocket.deployment_logs import (
            deployment_logs_websocket_endpoint,
        )

        deployment = _make_deployment()
        user = _make_user()

        websocket = AsyncMock()
        websocket.url.path = CHANNEL

        with patch.object(
            deployment_logs_module.database,
            "session",
            _mock_database_session(deployment),
        ):
            with patch.object(
                deployment_logs_module,
                "verify_deployment_access",
                new=AsyncMock(return_value=deployment),
            ):
                with patch.object(
                    deployment_logs_module,
                    "receive_with_expiry",
                    new=AsyncMock(side_effect=RuntimeError("loop crashed")),
                ):
                    await deployment_logs_websocket_endpoint(websocket, "dep-1", user)

        # Le message d'erreur applicatif a été envoyé avant la fermeture.
        sent_messages = [
            (call.args[0] if call.args else call.kwargs)
            for call in websocket.send_json.await_args_list
        ]
        error_messages = [
            m for m in sent_messages if isinstance(m, dict) and m.get("type") == "error"
        ]
        assert error_messages, "un message error doit être envoyé sur exception boucle"
        assert "loop crashed" in error_messages[0]["message"]
        # Nettoyage finally : connexion retirée du manager.
        assert "dep-1" not in manager.active_connections
