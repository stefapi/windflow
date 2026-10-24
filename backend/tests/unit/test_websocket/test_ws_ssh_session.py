"""Tests du canal WebSocket ``/ws/ssh/{host_id}`` (STORY-164.2 — AC 1/2).

Patterns ``test_ws_rbac.py`` / ``test_ws_auth.py`` : auth query param
(close 1008 sans token), RBAC operator, runners SSH **mockés**
(``AsyncMock`` — jamais de vraie connexion SSH en test), TOFU STRICT
(close 1011 message générique sans empreinte), rate limit 3/user, audit
``ssh_session_audit``, pont bidirectionnel WS↔PTY, expiration connexion
muette, ``disable_auth``.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth import dependencies as auth_dependencies
from app.core.exceptions import SSHHostKeyMismatchError, SSHHostKeyNotAcceptedError
from app.main import app
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.websocket import ssh_session as ssh_session_module

SSH = "/api/v1/ws/ssh/host-1"


# ===========================================================================
# Helpers (patterns test_ws_rbac)
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


def _make_target() -> MagicMock:
    """Target mockée — host/port/ssh_key_id/credentials (pattern scanner)."""
    target = MagicMock()
    target.id = "host-1"
    target.host = "192.168.1.10"
    target.port = 22
    target.ssh_key_id = "key-1"
    target.organization_id = "org-1"
    target.decrypted_credentials = {"username": "deploy"}
    target.access_profile = None
    return target


@pytest.fixture(autouse=True)
def _clean_ssh_sessions():
    """Store de sessions SSH vierge autour de chaque test (rate limit)."""
    ssh_session_module.ssh_sessions.clear()
    yield
    ssh_session_module.ssh_sessions.clear()


@pytest.fixture(autouse=True)
def _fresh_role_cache():
    from app.core.cache import reset_role_cache

    reset_role_cache()
    yield
    reset_role_cache()


@pytest.fixture()
def ws_client():
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _override_db():
    from app.database import get_db

    session = AsyncMock()

    async def override():
        yield session

    app.dependency_overrides[get_db] = override
    return session


def _patch_global_role(role: str):
    return patch.object(
        AuthorizationService,
        "get_global_role",
        AsyncMock(return_value=role),
    )


def _mock_database_session():
    mock_db = MagicMock()
    mock_database = MagicMock()
    mock_database.session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_database.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_database.session


def _access_granted():
    """resolve_host_and_check_access → Target mockée (accès OK)."""
    return patch(
        "app.websocket.ssh_session.resolve_host_and_check_access",
        new=AsyncMock(return_value=_make_target()),
    )


def _pty_process() -> MagicMock:
    """Process PTY asyncssh mocké : stdout asynchrone fini, stdin/channel OK."""
    process = MagicMock()

    async def _empty_stdout():
        return
        yield  # pragma: no cover — generator asynchrone vide

    process.stdout = _empty_stdout()
    process.stdin = MagicMock()
    process.channel = MagicMock()
    process.channel.change_terminal_size = MagicMock()
    process.exit_status = None
    process.close = MagicMock()
    return process


def _ssh_context(
    process: MagicMock | None = None, *, connect_error: Exception | None = None
):
    """Empile TOFU OK + asyncssh.connect mocké (jamais de vraie connexion).

    Retourne le mock de connexion pour les assertions.
    """
    connection = AsyncMock()
    if process is None:
        process = _pty_process()
    connection.create_process = AsyncMock(return_value=process)

    async def _connect(**kwargs):
        if connect_error is not None:
            raise connect_error
        return connection

    stack = ExitStack()
    stack.enter_context(
        patch(
            "app.websocket.ssh_session.build_ssh_kwargs",
            new=AsyncMock(return_value={"host": "192.168.1.10"}),
        )
    )
    stack.enter_context(
        patch("app.websocket.ssh_session.asyncssh.connect", new=_connect)
    )
    return stack, connection


def _auth_stack(user: User):
    """Patches d'auth query param (get_current_user_ws)."""
    stack = ExitStack()
    stack.enter_context(patch.object(auth_dependencies.settings, "disable_auth", False))
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
        patch.object(auth_dependencies.database, "session", _mock_database_session())
    )
    return stack


# ===========================================================================
# AC 1 — Auth 1008 sans token / RBAC viewer↔operator
# ===========================================================================


class TestSshAuthAndRbac:
    """Auth obligatoire + RBAC operator (matrice spec 08 § Hosts)."""

    def test_no_token_refused_1008(self, ws_client):
        """Sécurité : sans token → handshake refusé (1008), avant accept."""
        _override_db()
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with pytest.raises(Exception):
                with ws_client.websocket_connect(SSH):
                    pass

    def test_viewer_refused(self, ws_client):
        """RBAC : viewer → 1008 « Insufficient permissions » (action WS)."""
        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("viewer"):
                with pytest.raises(Exception):
                    with ws_client.websocket_connect(SSH + "?token=valid.jwt"):
                        pass

    def test_operator_passes_rbac(self, ws_client):
        """Cas nominal : operator → RBAC passé (réponse applicative ensuite)."""
        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with _access_granted():
                    ssh_stack, _ = _ssh_context()
                    with ssh_stack:
                        with ws_client.websocket_connect(
                            SSH + "?token=valid.jwt"
                        ) as ws:
                            message = ws.receive_json()
                            # Le check RBAC est passé : réponse applicative
                            assert message["type"] in ("ready", "error")
                            if message["type"] == "error":
                                assert "permission" not in message["message"].lower()

    def test_disable_auth_auto_login_accepted(self, ws_client):
        """disable_auth (dev) : auto-login superadmin → RBAC passé."""
        _override_db()
        superadmin = _make_user(superadmin=True)

        with patch.object(auth_dependencies.settings, "disable_auth", True):
            with patch.object(
                auth_dependencies.UserService,
                "get_first_superadmin",
                AsyncMock(return_value=superadmin),
            ):
                with _patch_global_role("super_admin"):
                    with _access_granted():
                        ssh_stack, _ = _ssh_context()
                        with ssh_stack:
                            with ws_client.websocket_connect(SSH) as ws:
                                message = ws.receive_json()
                                assert message["type"] in ("ready", "error")


# ===========================================================================
# AC 2 — Accès Host : 404 / isolation organisation
# ===========================================================================


class TestSshHostAccess:
    """Résolution Host + isolation organisation (host_access.py)."""

    def test_host_not_found_closes(self, ws_client):
        """Host introuvable → message error + fermeture (404 traduit)."""
        from fastapi import HTTPException

        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with patch(
                    "app.websocket.ssh_session.resolve_host_and_check_access",
                    new=AsyncMock(
                        side_effect=HTTPException(
                            status_code=404, detail="Host not found"
                        )
                    ),
                ):
                    with ws_client.websocket_connect(SSH + "?token=valid.jwt") as ws:
                        message = ws.receive_json()
                        assert message["type"] == "error"
                        assert "not found" in message["message"].lower()

    def test_foreign_organization_host_refused(self, ws_client):
        """Isolation : host d'une autre organisation → refus (403 traduit)."""
        from fastapi import HTTPException

        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with patch(
                    "app.websocket.ssh_session.resolve_host_and_check_access",
                    new=AsyncMock(
                        side_effect=HTTPException(
                            status_code=403, detail="Access denied to this host"
                        )
                    ),
                ):
                    with ws_client.websocket_connect(SSH + "?token=valid.jwt") as ws:
                        message = ws.receive_json()
                        assert message["type"] == "error"
                        assert "denied" in message["message"].lower()


# ===========================================================================
# AC 2 — TOFU STRICT (empreinte inconnue / divergence → 1011 générique)
# ===========================================================================


class TestSshTofuStrict:
    """TOFU STRICT via build_ssh_kwargs (STORY-131) — jamais 1011 détaillé."""

    def test_unknown_fingerprint_close_1011_generic(self, ws_client):
        """Empreinte inconnue → SSHHostKeyNotAcceptedError → close 1011,
        message SANS empreinte en clair."""
        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with _access_granted():
                    ssh_stack, _ = _ssh_context(
                        connect_error=SSHHostKeyNotAcceptedError(
                            "unknown fingerprint SHA256:SECRET"
                        )
                    )
                    with ssh_stack:
                        with ws_client.websocket_connect(
                            SSH + "?token=valid.jwt"
                        ) as ws:
                            message = ws.receive_json()
                            assert message["type"] == "error"
                            # Message générique : jamais l'empreinte
                            assert "SHA256" not in message["message"]
                            assert "SECRET" not in message["message"]
                            assert "host key" in message["message"].lower()

    def test_mismatch_fingerprint_close_1011(self, ws_client):
        """Divergence d'empreinte → SSHHostKeyMismatchError → close 1011."""
        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with _access_granted():
                    ssh_stack, _ = _ssh_context(
                        connect_error=SSHHostKeyMismatchError(
                            "divergence SHA256:AAA vs SHA256:BBB"
                        )
                    )
                    with ssh_stack:
                        with ws_client.websocket_connect(
                            SSH + "?token=valid.jwt"
                        ) as ws:
                            message = ws.receive_json()
                            assert message["type"] == "error"
                            assert "SHA256" not in message["message"]
                            assert "AAA" not in message["message"]

    def test_tofu_failure_audited(self, ws_client, caplog):
        """Audit : refus TOFU → ssh_session_audit (connect échoué)."""
        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with _access_granted():
                    ssh_stack, _ = _ssh_context(
                        connect_error=SSHHostKeyNotAcceptedError("unknown")
                    )
                    with ssh_stack:
                        with caplog.at_level(
                            logging.WARNING, logger="ssh_session_audit"
                        ):
                            with ws_client.websocket_connect(
                                SSH + "?token=valid.jwt"
                            ) as ws:
                                ws.receive_json()

        audit_records = [
            r
            for r in caplog.records
            if r.name == "ssh_session_audit" and r.action == "connect"
        ]
        assert audit_records, "refus TOFU non audité"
        assert getattr(audit_records[0], "success", None) is False


# ===========================================================================
# Rate limit 3 sessions/user + audit + pont bidirectionnel
# ===========================================================================


class TestSshRateLimitAndBridge:
    """Rate limit calqué terminal.py + pont WS↔PTY + audit fermeture."""

    def test_fourth_concurrent_session_refused(self, ws_client):
        """Rate limit : 4e session simultanée du même user → refus."""
        _override_db()
        user = _make_user()

        # 3 sessions déjà enregistrées pour user-1
        for i in range(3):
            ssh_session_module.ssh_sessions[f"existing-{i}"] = {
                "user_id": "user-1",
                "host_id": "host-1",
                "started_at": "2026-10-23T00:00:00",
            }

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with _access_granted():
                    ssh_stack, _ = _ssh_context()
                    with ssh_stack:
                        with ws_client.websocket_connect(
                            SSH + "?token=valid.jwt"
                        ) as ws:
                            message = ws.receive_json()
                            assert message["type"] == "error"
                            assert "maximum" in message["message"].lower()

    def test_ready_then_input_and_resize_relayed(self, ws_client):
        """Pont bidirectionnel : ready → input écrit au PTY, resize propagé."""
        _override_db()
        user = _make_user()
        process = _pty_process()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with _access_granted():
                    ssh_stack, _ = _ssh_context(process=process)
                    with ssh_stack:
                        with ws_client.websocket_connect(
                            SSH + "?token=valid.jwt"
                        ) as ws:
                            ready = ws.receive_json()
                            assert ready["type"] == "ready"
                            assert ready["host_id"] == "host-1"

                            # Entrées WS : input → PTY, resize → channel,
                            # ping → pong (le TestClient exécute la boucle
                            # serveur en thread, receive_json synchronise).
                            ws.send_json({"type": "input", "data": "ls\n"})
                            ws.send_json({"type": "resize", "cols": 120, "rows": 30})
                            ws.send_text("ping")

                            # Consomme la réponse pong (le ping est traité
                            # après input/resize → le PTY a déjà reçu).
                            reply = None
                            for _ in range(10):
                                reply = ws.receive_json()
                                if reply.get("type") == "pong":
                                    break
                            assert reply is not None and reply.get("type") == "pong"

        # Le pont a bien relayé : stdin a reçu l'input, le channel le resize
        process.stdin.write.assert_called_with("ls\n")
        process.channel.change_terminal_size.assert_called_with(120, 30)

    def test_disconnect_audited_with_duration(self, ws_client, caplog):
        """Audit : fermeture → disconnect tracé (user, host, durée)."""
        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with _access_granted():
                    ssh_stack, _ = _ssh_context()
                    with ssh_stack:
                        with caplog.at_level(logging.INFO, logger="ssh_session_audit"):
                            with ws_client.websocket_connect(
                                SSH + "?token=valid.jwt"
                            ) as ws:
                                ws.receive_json()
                                # La fermeture du contexte WS déconnecte

        disconnect_records = [
            r
            for r in caplog.records
            if r.name == "ssh_session_audit"
            and getattr(r, "action", "") == "disconnect"
        ]
        assert disconnect_records, "fermeture de session non auditée"
        assert hasattr(disconnect_records[0], "duration_seconds")
        # Pas de secret dans le log
        assert "password" not in disconnect_records[0].getMessage().lower()


# ===========================================================================
# Expiration connexion muette (helper STORY-164.1)
# ===========================================================================


class TestSshIdleExpiry:
    """Expiration via receive_with_expiry — timeout réduit en test."""

    def test_mute_connection_expired(self, ws_client):
        """Client muet → fermeture serveur (~factor × interval réduits)."""
        from app.config import settings

        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with _access_granted():
                    ssh_stack, _ = _ssh_context()
                    with ssh_stack:
                        with patch.object(settings, "ws_heartbeat_interval_seconds", 1):
                            with patch.object(
                                settings, "ws_heartbeat_timeout_factor", 1
                            ):
                                with ws_client.websocket_connect(
                                    SSH + "?token=valid.jwt"
                                ) as ws:
                                    ready = ws.receive_json()
                                    assert ready["type"] == "ready"
                                    # Silence : le serveur doit fermer (1001)
                                    with pytest.raises(Exception):
                                        for _ in range(5):
                                            ws.receive_json()


# ===========================================================================
# host_access.py — unitaire (résolution + username)
# ===========================================================================


class TestHostAccessUnit:
    """resolve_host_and_check_access + resolve_ssh_username (Tâche 1)."""

    async def test_resolve_returns_target_when_member(self):
        from sqlalchemy.sql import Select

        from app.websocket.host_access import resolve_host_and_check_access

        target = _make_target()
        user = _make_user()
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = target
        db.execute = AsyncMock(return_value=result_mock)

        with patch(
            "app.websocket.host_access.UserOrganizationService.is_member",
            new=AsyncMock(return_value=True),
        ):
            resolved = await resolve_host_and_check_access("host-1", user, db)

        assert resolved is target
        db.execute.assert_awaited_once()
        assert isinstance(db.execute.await_args.args[0], Select)

    async def test_resolve_404_when_not_found(self):
        from fastapi import HTTPException

        from app.websocket.host_access import resolve_host_and_check_access

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException) as exc_info:
            await resolve_host_and_check_access("ghost", _make_user(), db)
        assert exc_info.value.status_code == 404

    async def test_resolve_403_when_not_member(self):
        from fastapi import HTTPException

        from app.websocket.host_access import resolve_host_and_check_access

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = _make_target()
        db.execute = AsyncMock(return_value=result_mock)

        with patch(
            "app.websocket.host_access.UserOrganizationService.is_member",
            new=AsyncMock(return_value=False),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await resolve_host_and_check_access("host-1", _make_user(), db)
        assert exc_info.value.status_code == 403

    async def test_resolve_401_when_no_user(self):
        from fastapi import HTTPException

        from app.websocket.host_access import resolve_host_and_check_access

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = _make_target()
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException) as exc_info:
            await resolve_host_and_check_access("host-1", None, db)
        assert exc_info.value.status_code == 401

    def test_username_from_credentials_then_profile_then_default(self):
        from app.websocket.host_access import resolve_ssh_username

        # 1. credentials["username"] prioritaire
        target = _make_target()
        target.access_profile = {"ssh_user": "scanner-user"}
        assert resolve_ssh_username(target) == "deploy"

        # 2. access_profile sinon
        target.decrypted_credentials = {}
        assert resolve_ssh_username(target) == "scanner-user"

        # 3. root par défaut
        target.access_profile = None
        assert resolve_ssh_username(target) == "root"


# ===========================================================================
# Format de messages du canal
# ===========================================================================


def test_client_message_contract_documented():
    """Garde documentation : le contrat client (input/resize/ping) est
    bien celui documenté dans la docstring du handler."""
    import inspect

    from app.websocket.ssh_session import ssh_session_websocket_endpoint

    docstring = inspect.getdoc(ssh_session_websocket_endpoint) or ""
    assert '"type": "input"' in docstring
    assert '"type": "resize"' in docstring
    assert "TOFU STRICT" in docstring


# ===========================================================================
# Branches d'erreur — handler direct avec WebSocket mockée (couverture ≥ 80 %)
# ===========================================================================


def _mute_ws() -> AsyncMock:
    """WebSocket mockée : receive_text muet (handler bloqué en boucle)."""
    websocket = AsyncMock()
    websocket.receive_text = AsyncMock(side_effect=asyncio.Event().wait)
    return websocket


def _then_mute_receive(messages: list[str]) -> AsyncMock:
    """receive_text émet les messages donnés puis reste muet."""
    pending = list(messages)

    async def _receive():
        if pending:
            return pending.pop(0)
        await asyncio.Event().wait()

    return AsyncMock(side_effect=_receive)


class TestSshErrorBranches:
    """Branches d'erreur du handler non couvertes par l'E2E TestClient."""

    async def test_ssh_generic_error_closes_1011(self):
        """asyncssh.Error générique à la connexion → error + close 1011."""
        import asyncssh as _asyncssh

        from app.websocket.ssh_session import ssh_session_websocket_endpoint

        websocket = _mute_ws()
        user = _make_user()
        session = AsyncMock()

        async def _connect_error(**kwargs):
            raise _asyncssh.ConnectionLost("unreachable")

        with _access_granted():
            with patch(
                "app.websocket.ssh_session.build_ssh_kwargs",
                new=AsyncMock(return_value={}),
            ):
                with patch(
                    "app.websocket.ssh_session.asyncssh.connect", new=_connect_error
                ):
                    # Le handler envoie error puis close puis return :
                    # la coroutine termine proprement (bornée par sûreté).
                    await asyncio.wait_for(
                        ssh_session_websocket_endpoint(
                            websocket, "host-1", user, session
                        ),
                        timeout=3.0,
                    )

        sent = [c.args[0] for c in websocket.send_json.await_args_list]
        error_messages = [m for m in sent if m.get("type") == "error"]
        assert error_messages
        assert "SSH connection failed" in error_messages[0]["message"]
        websocket.close.assert_awaited()

    async def test_create_process_failure_closes(self):
        """Échec create_process → error « Failed to open remote shell » + close."""
        import asyncssh as _asyncssh

        from app.websocket.ssh_session import ssh_session_websocket_endpoint

        websocket = _mute_ws()
        user = _make_user()
        session = AsyncMock()

        connection = AsyncMock()
        connection.create_process = AsyncMock(
            side_effect=_asyncssh.ChannelOpenError("en", "denied")
        )

        async def _connect(**kwargs):
            return connection

        with _access_granted():
            with patch(
                "app.websocket.ssh_session.build_ssh_kwargs",
                new=AsyncMock(return_value={}),
            ):
                with patch("app.websocket.ssh_session.asyncssh.connect", new=_connect):
                    # error → close → return : termine proprement.
                    await asyncio.wait_for(
                        ssh_session_websocket_endpoint(
                            websocket, "host-1", user, session
                        ),
                        timeout=3.0,
                    )

        sent = [c.args[0] for c in websocket.send_json.await_args_list]
        assert any(m.get("message") == "Failed to open remote shell" for m in sent)
        websocket.close.assert_awaited()
        connection.close.assert_called()

    async def test_exit_code_sent_on_process_exit(self):
        """PTY terminé (exit_status) → message exit envoyé à la fermeture."""
        from app.websocket.ssh_session import ssh_session_websocket_endpoint

        websocket = _mute_ws()
        user = _make_user()
        session = AsyncMock()
        process = _pty_process()
        process.exit_status = 42

        connection = AsyncMock()
        connection.create_process = AsyncMock(return_value=process)

        async def _connect(**kwargs):
            return connection

        with _access_granted():
            with patch(
                "app.websocket.ssh_session.build_ssh_kwargs",
                new=AsyncMock(return_value={}),
            ):
                with patch("app.websocket.ssh_session.asyncssh.connect", new=_connect):
                    with pytest.raises(asyncio.TimeoutError):
                        await asyncio.wait_for(
                            ssh_session_websocket_endpoint(
                                websocket, "host-1", user, session
                            ),
                            timeout=3.0,
                        )

        sent = [c.args[0] for c in websocket.send_json.await_args_list]
        assert {"type": "exit", "code": 42} in sent
        process.close.assert_called()
        connection.close.assert_called()

    async def test_invalid_json_and_messages_ignored(self):
        """JSON invalide / types inconnus / resize invalide → ignorés (pas d'erreur)."""
        from app.websocket.ssh_session import ssh_session_websocket_endpoint

        websocket = AsyncMock()
        websocket.receive_text = _then_mute_receive(
            [
                "not-json",
                '{"type": "unknown"}',
                '{"type": "resize", "cols": "bad", "rows": "x"}',
                '{"type": "resize", "cols": -5, "rows": 0}',
                '{"type": "input", "data": 123}',
            ]
        )
        user = _make_user()
        session = AsyncMock()
        process = _pty_process()

        connection = AsyncMock()
        connection.create_process = AsyncMock(return_value=process)

        async def _connect(**kwargs):
            return connection

        with _access_granted():
            with patch(
                "app.websocket.ssh_session.build_ssh_kwargs",
                new=AsyncMock(return_value={}),
            ):
                with patch("app.websocket.ssh_session.asyncssh.connect", new=_connect):
                    with pytest.raises(asyncio.TimeoutError):
                        await asyncio.wait_for(
                            ssh_session_websocket_endpoint(
                                websocket, "host-1", user, session
                            ),
                            timeout=3.0,
                        )

        # Aucun input non-string ni resize invalide n'a atteint le PTY
        process.stdin.write.assert_not_called()
        process.channel.change_terminal_size.assert_not_called()
        sent = [c.args[0] for c in websocket.send_json.await_args_list]
        assert not any(m.get("type") == "error" for m in sent)
