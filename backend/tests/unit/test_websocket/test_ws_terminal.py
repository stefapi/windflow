"""Tests E2E du canal terminal interactif (STORY-165 — Tâche 7, AC 2/4).

Couvre ``app/websocket/terminal.py`` l.274-473 (50 % → ≥ 80 %) — boucle
interactive avec **mock complet de ``TerminalService``** :

- connexion operator : message ``ready`` (exec_id/shell/user/cols/rows) +
  **audit ``connect`` succès** ;
- ``{"type": "input", ...}`` → ``send_input`` appelé avec la session et les
  données ; erreur ``send_input`` → message ``error`` (Input error) ;
- ``{"type": "resize", ...}`` → ``resize_tty`` appelé ; erreur → warning
  absorbé, **aucun** message d'erreur envoyé ;
- ``ping`` texte → ``pong`` ; JSON invalide → ignoré (continue) ;
- flux ``output`` : ``stream_output`` rend 2 lignes puis se termine →
  messages ``output`` ×2 + ``exit`` (returncode) ;
- **``ValueError`` à la création** (conteneur indisponible) → error +
  **close 1008** + audit échec ;
- **``RuntimeError`` à la création** → error « Failed to create terminal » +
  **close 1011** + audit échec ;
- déconnexion : ``cleanup_session`` + ``close`` appelés,
  ``unregister_terminal_session``, **audit ``disconnect``** ;
- rate limit unitaire : store mémoire réel (3 sessions max par user,
  comportement de ``check_terminal_rate_limit`` — non couvert ailleurs :
  ``test_ws_rbac.py`` patche le check sans le tester).

Le RBAC terminal (viewer refusé / operator accepté / audits d'échec auth)
est déjà couvert par ``test_ws_rbac.py`` et ``test_ws_auth.py`` — non
dupliqué ici (rôle « operator » résolu par patch pour passer la garde).

Patterns : ``_auth_stack`` premier message (test_ws_rbac.py) + sessions
terminal factices (contexte technique de la story).
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.auth import dependencies as auth_dependencies
from app.main import app
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.websocket import terminal as terminal_module

TERMINAL = "/api/v1/ws/terminal/container-1"


# ===========================================================================
# Helpers (patterns test_ws_rbac.py / test_ws_batch.py)
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


def _make_exec_session(exec_id: str = "exec-abc123", returncode: int = 0) -> MagicMock:
    """ExecSession factice (terminal_service.ExecSession simulé)."""
    session = MagicMock()
    session.exec_id = exec_id
    session.shell = "/bin/sh"
    session.user = "root"
    session.cols = 80
    session.rows = 24
    session.process = MagicMock()
    session.process.returncode = returncode
    return session


@pytest.fixture(autouse=True)
def _fresh_role_cache():
    from app.core.cache import reset_role_cache

    reset_role_cache()
    yield
    reset_role_cache()


@pytest.fixture(autouse=True)
def _clean_terminal_sessions():
    """Store de rate limiting vierge autour de chaque test (isolation)."""
    terminal_module.terminal_sessions.clear()
    yield
    terminal_module.terminal_sessions.clear()


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


def _mock_database_session() -> MagicMock:
    """Session mockée : aucune association → role global viewer par défaut."""
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=_rbac_empty_roles_result())
    mock_database = MagicMock()
    mock_database.session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_database.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_database.session


def _auth_stack(user: User, *, role: str = "operator"):
    """Empile l'auth « premier message » du terminal (RBAC operator patché)."""
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
        patch.object(auth_dependencies.database, "session", _mock_database_session())
    )
    stack.enter_context(
        patch.object(
            AuthorizationService, "get_global_role", AsyncMock(return_value=role)
        )
    )
    # Aucun deployment associé au container en DB mockée → accès direct
    # autorisé (branche deployment is None du terminal).
    return stack


def _patch_audit() -> AsyncMock:
    """Patche log_terminal_audit (assertion des audits connect/disconnect)."""
    return patch(
        "app.websocket.terminal.log_terminal_audit",
        new_callable=AsyncMock,
    )


def _terminal_service_mock(
    session=None,
    *,
    create_error: Exception | None = None,
    output_lines: tuple[bytes, ...] = (b"line 1\n", b"line 2\n"),
) -> MagicMock:
    """TerminalService factice : create/stream/input/resize/cleanup/close."""
    service = MagicMock()
    if create_error is not None:
        service.create_session = AsyncMock(side_effect=create_error)
    else:
        service.create_session = AsyncMock(return_value=session or _make_exec_session())

    async def _stream_output(session_arg):  # noqa: ARG001
        for line in output_lines:
            yield (line, False)

    service.stream_output = _stream_output
    service.send_input = AsyncMock()
    service.resize_tty = AsyncMock()
    service.cleanup_session = AsyncMock()
    service.close = AsyncMock()
    return service


def _service_patch(service: MagicMock):
    return patch("app.websocket.terminal.TerminalService", return_value=service)


def _collect_until(ws, wanted_type: str, max_messages: int = 30):
    """Consomme les messages jusqu'au type voulu (ou épuisement)."""
    messages = []
    for _ in range(max_messages):
        try:
            message = ws.receive_json()
        except Exception:
            break
        messages.append(message)
        if message.get("type") == wanted_type:
            break
    return messages


# ===========================================================================
# Connexion nominale — ready + audit connect
# ===========================================================================


class TestTerminalReady:
    """Operator authentifié : session créée → ready + audit succès."""

    def test_ready_message_and_connect_audit(self, ws_client):
        _override_db()
        user = _make_user()
        session = _make_exec_session(exec_id="exec-xyz")
        service = _terminal_service_mock(session=session)

        with _auth_stack(user):
            with _patch_audit() as mock_audit:
                with _service_patch(service):
                    with ws_client.websocket_connect(TERMINAL) as ws:
                        ws.send_json({"type": "auth", "token": "valid.jwt"})
                        ready = ws.receive_json()
                        assert ready["type"] == "ready"
                        assert ready["exec_id"] == "exec-xyz"
                        assert ready["shell"] == "/bin/sh"
                        assert ready["user"] == "root"
                        assert ready["cols"] == 80
                        assert ready["rows"] == 24

                        # create_session appelé avec les paramètres du canal.
                        service.create_session.assert_awaited_once_with(
                            container_id="container-1",
                            shell="/bin/sh",
                            user="root",
                            cols=80,
                            rows=24,
                        )
                        # Session enregistrée pour le rate limiting.
                        assert "exec-xyz" in terminal_module.terminal_sessions

                        # Audit connect succès.
                        mock_audit.assert_any_await(
                            "user-1",
                            "testuser",
                            "container-1",
                            "connect",
                            True,
                            "shell=/bin/sh, user=root",
                        )

    def test_disconnect_cleans_up_session_and_audits(self, ws_client):
        """Fermeture client : cleanup + close + unregister + audit disconnect."""
        _override_db()
        user = _make_user()
        session = _make_exec_session(exec_id="exec-clean")
        service = _terminal_service_mock(session=session)

        with _auth_stack(user):
            with _patch_audit() as mock_audit:
                with _service_patch(service):
                    with ws_client.websocket_connect(TERMINAL) as ws:
                        ws.send_json({"type": "auth", "token": "valid.jwt"})
                        assert ws.receive_json()["type"] == "ready"
                        # La fermeture du context manager déconnecte le
                        # client → finally du terminal.

        service.cleanup_session.assert_awaited_once()
        service.close.assert_awaited_once()
        # Session retirée du store de rate limiting.
        assert "exec-clean" not in terminal_module.terminal_sessions
        # Audit disconnect succès (exec_id tracé).
        disconnect_calls = [
            call for call in mock_audit.await_args_list if call.args[3] == "disconnect"
        ]
        assert disconnect_calls
        assert disconnect_calls[0].args[4] is True
        assert "exec_id=exec-clean" in disconnect_calls[0].args[5]


# ===========================================================================
# Boucle interactive — input / resize / ping / texte invalide
# ===========================================================================


class TestTerminalInteractiveLoop:
    """Messages client : input, resize, ping, JSON invalide."""

    def test_input_forwarded_to_send_input(self, ws_client):
        _override_db()
        user = _make_user()
        session = _make_exec_session()
        service = _terminal_service_mock(session=session)

        with _auth_stack(user):
            with _service_patch(service):
                with ws_client.websocket_connect(TERMINAL) as ws:
                    ws.send_json({"type": "auth", "token": "valid.jwt"})
                    assert ws.receive_json()["type"] == "ready"

                    ws.send_json({"type": "input", "data": "ls -la\n"})
                    # Attendre le traitement (pong de confirmation de boucle) ;
                    # le stream de sortie peut intercaler output/exit avant.
                    ws.send_text("ping")
                    messages = _collect_until(ws, "pong")
                    assert messages[-1]["type"] == "pong"

                    service.send_input.assert_awaited_once_with(session, "ls -la\n")

    def test_input_error_returns_error_message(self, ws_client):
        """send_input lève → message error « Input error » (boucle continue)."""
        _override_db()
        user = _make_user()
        service = _terminal_service_mock(session=_make_exec_session())
        service.send_input = AsyncMock(side_effect=RuntimeError("stream closed"))

        with _auth_stack(user):
            with _service_patch(service):
                with ws_client.websocket_connect(TERMINAL) as ws:
                    ws.send_json({"type": "auth", "token": "valid.jwt"})
                    assert ws.receive_json()["type"] == "ready"

                    ws.send_json({"type": "input", "data": "ls\n"})
                    messages = _collect_until(ws, "error")
                    error = next(m for m in messages if m["type"] == "error")
                    assert "Input error" in error["message"]
                    assert "stream closed" in error["message"]

    def test_resize_forwarded_to_resize_tty(self, ws_client):
        _override_db()
        user = _make_user()
        session = _make_exec_session()
        service = _terminal_service_mock(session=session)

        with _auth_stack(user):
            with _service_patch(service):
                with ws_client.websocket_connect(TERMINAL) as ws:
                    ws.send_json({"type": "auth", "token": "valid.jwt"})
                    assert ws.receive_json()["type"] == "ready"

                    ws.send_json({"type": "resize", "cols": 120, "rows": 40})
                    ws.send_text("ping")
                    messages = _collect_until(ws, "pong")
                    assert messages[-1]["type"] == "pong"

                    service.resize_tty.assert_awaited_once_with(session, 120, 40)

    def test_resize_error_swallowed_without_error_message(self, ws_client):
        """resize_tty lève → warning absorbé, aucun message error (l.416-417)."""
        _override_db()
        user = _make_user()
        service = _terminal_service_mock(session=_make_exec_session())
        service.resize_tty = AsyncMock(side_effect=RuntimeError("tty gone"))

        with _auth_stack(user):
            with _service_patch(service):
                with ws_client.websocket_connect(TERMINAL) as ws:
                    ws.send_json({"type": "auth", "token": "valid.jwt"})
                    assert ws.receive_json()["type"] == "ready"

                    ws.send_json({"type": "resize", "cols": 120, "rows": 40})
                    ws.send_text("ping")
                    # Seuls output/exit/pong sont attendus — aucun error.
                    messages = _collect_until(ws, "pong")
                    assert all(m["type"] != "error" for m in messages)
                    assert messages[-1]["type"] == "pong"

    def test_text_ping_answered_with_pong(self, ws_client):
        _override_db()
        user = _make_user()
        service = _terminal_service_mock(session=_make_exec_session())

        with _auth_stack(user):
            with _service_patch(service):
                with ws_client.websocket_connect(TERMINAL) as ws:
                    ws.send_json({"type": "auth", "token": "valid.jwt"})
                    assert ws.receive_json()["type"] == "ready"

                    ws.send_text("ping")
                    messages = _collect_until(ws, "pong")
                    pong = messages[-1]
                    assert pong["type"] == "pong"
                    assert "timestamp" in pong

    def test_invalid_json_ignored_loop_continues(self, ws_client):
        """Texte non-JSON → ignoré (continue) ; le ping suivant répond pong."""
        _override_db()
        user = _make_user()
        service = _terminal_service_mock(session=_make_exec_session())

        with _auth_stack(user):
            with _service_patch(service):
                with ws_client.websocket_connect(TERMINAL) as ws:
                    ws.send_json({"type": "auth", "token": "valid.jwt"})
                    assert ws.receive_json()["type"] == "ready"

                    ws.send_text("garbage-not-json{{")
                    ws.send_text("ping")
                    messages = _collect_until(ws, "pong")
                    assert messages[-1]["type"] == "pong"


# ===========================================================================
# Flux de sortie — output ×N puis exit
# ===========================================================================


class TestTerminalOutputStreaming:
    """stream_output : lignes output décodées puis message exit."""

    def test_output_lines_then_exit(self, ws_client):
        _override_db()
        user = _make_user()
        session = _make_exec_session(returncode=3)
        service = _terminal_service_mock(
            session=session, output_lines=(b"hello\n", b"world\n")
        )

        with _auth_stack(user):
            with _service_patch(service):
                with ws_client.websocket_connect(TERMINAL) as ws:
                    ws.send_json({"type": "auth", "token": "valid.jwt"})
                    assert ws.receive_json()["type"] == "ready"

                    messages = _collect_until(ws, "exit", max_messages=20)
                    outputs = [m for m in messages if m["type"] == "output"]
                    assert [m["data"] for m in outputs] == ["hello\n", "world\n"]
                    exit_message = next(m for m in messages if m["type"] == "exit")
                    assert exit_message["code"] == 3


# ===========================================================================
# Échecs à la création — ValueError → 1008, RuntimeError → 1011
# ===========================================================================


class TestTerminalCreationFailures:
    """create_session échoue : codes de fermeture différenciés + audits."""

    def test_value_error_closes_1008_with_audit_failure(self, ws_client):
        """ValueError (ex. conteneur absent) → error + close 1008 + audit."""
        _override_db()
        user = _make_user()
        service = _terminal_service_mock(
            create_error=ValueError("Container not running")
        )

        with _auth_stack(user):
            with _patch_audit() as mock_audit:
                with _service_patch(service):
                    with ws_client.websocket_connect(TERMINAL) as ws:
                        ws.send_json({"type": "auth", "token": "valid.jwt"})
                        error = ws.receive_json()
                        assert error["type"] == "error"
                        assert error["message"] == "Container not running"

                        with pytest.raises(WebSocketDisconnect) as exc_info:
                            ws.receive_json()
                        assert exc_info.value.code == 1008

        mock_audit.assert_any_await(
            "user-1",
            "testuser",
            "container-1",
            "connect",
            False,
            "Container not running",
        )

    def test_runtime_error_closes_1011_with_audit_failure(self, ws_client):
        """RuntimeError (docker indisponible) → error « Failed to create
        terminal » + close 1011 + audit échec."""
        _override_db()
        user = _make_user()
        service = _terminal_service_mock(
            create_error=RuntimeError("docker daemon unreachable")
        )

        with _auth_stack(user):
            with _patch_audit() as mock_audit:
                with _service_patch(service):
                    with ws_client.websocket_connect(TERMINAL) as ws:
                        ws.send_json({"type": "auth", "token": "valid.jwt"})
                        error = ws.receive_json()
                        assert error["type"] == "error"
                        assert (
                            error["message"]
                            == "Failed to create terminal: docker daemon unreachable"
                        )

                        with pytest.raises(WebSocketDisconnect) as exc_info:
                            ws.receive_json()
                        assert exc_info.value.code == 1011

        mock_audit.assert_any_await(
            "user-1",
            "testuser",
            "container-1",
            "connect",
            False,
            "docker daemon unreachable",
        )

    def test_rate_limit_exceeded_closes_1008(self, ws_client):
        """Rate limit : 3 sessions actives → 4e refusée (error + 1008)."""
        _override_db()
        user = _make_user()
        service = _terminal_service_mock(session=_make_exec_session())

        # Store pré-rempli : 3 sessions actives pour user-1 (max autorisé).
        for exec_id in ("e1", "e2", "e3"):
            terminal_module.terminal_sessions[exec_id] = {
                "user_id": "user-1",
                "container_id": "container-1",
                "started_at": "2026-10-24T00:00:00",
            }

        with _auth_stack(user):
            with _patch_audit() as mock_audit:
                with _service_patch(service):
                    with ws_client.websocket_connect(TERMINAL) as ws:
                        ws.send_json({"type": "auth", "token": "valid.jwt"})
                        error = ws.receive_json()
                        assert error["type"] == "error"
                        assert "Maximum 3 terminal sessions" in error["message"]

                        with pytest.raises(WebSocketDisconnect) as exc_info:
                            ws.receive_json()
                        assert exc_info.value.code == 1008

        # Aucune session créée, audit d'échec avec le message de rate limit.
        service.create_session.assert_not_awaited()
        failure_calls = [
            call for call in mock_audit.await_args_list if call.args[4] is False
        ]
        assert any("Maximum 3" in call.args[5] for call in failure_calls)


# ===========================================================================
# Rate limiting — comportement unitaire du store mémoire
# ===========================================================================


def _mock_database_module() -> MagicMock:
    """Module database factice pour les invocations directes du endpoint.

    ``execute`` retourne un résultat sans deployment (``scalar_one_or_none``
    → None) : la branche « accès direct au conteneur » du terminal est prise
    (aucune vérification d'organisation supplémentaire).
    """
    mock_db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)

    mock_database = MagicMock()
    mock_database.session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_database.session.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_database


class TestTerminalStreamEdgeBranches:
    """Branches d'erreur du stream, de la boucle et de l'audit (unitaires)."""

    async def test_audit_failure_log_is_warning(self, caplog):
        """log_terminal_audit success=False → log warning structuré (l.117)."""
        import logging

        with caplog.at_level(logging.WARNING, logger="terminal_audit"):
            await terminal_module.log_terminal_audit(
                "u1", "alice", "container-1", "error", False, "boom"
            )

        records = [r for r in caplog.records if r.name == "terminal_audit"]
        assert records
        record = records[-1]
        assert getattr(record, "action") == "error"
        assert getattr(record, "success") is False
        assert getattr(record, "details") == "boom"

    def test_json_ping_message_ignored_text_ping_answers(self, ws_client):
        """``{"type": "ping"}`` JSON → pass silencieux (l.419-421) ; seul le
        ping **texte** déclenche pong."""
        _override_db()
        user = _make_user()
        service = _terminal_service_mock(session=_make_exec_session())

        with _auth_stack(user):
            with _service_patch(service):
                with ws_client.websocket_connect(TERMINAL) as ws:
                    ws.send_json({"type": "auth", "token": "valid.jwt"})
                    assert ws.receive_json()["type"] == "ready"

                    ws.send_json({"type": "ping"})  # JSON → pass
                    ws.send_text("ping")  # texte → pong
                    messages = _collect_until(ws, "pong")
                    assert messages[-1]["type"] == "pong"

    def test_mute_terminal_expires_and_cleans_up(self, ws_client):
        """Inactivité totale → expiration (l.426-430) → fermeture serveur ;
        cleanup + unregister + audit disconnect."""
        from app.config import settings

        _override_db()
        user = _make_user()
        session = _make_exec_session(exec_id="exec-mute")
        service = _terminal_service_mock(session=session)

        with _auth_stack(user):
            with _patch_audit() as mock_audit:
                with _service_patch(service):
                    with patch.object(settings, "ws_heartbeat_interval_seconds", 1):
                        with patch.object(settings, "ws_heartbeat_timeout_factor", 1):
                            with ws_client.websocket_connect(TERMINAL) as ws:
                                ws.send_json({"type": "auth", "token": "valid.jwt"})
                                assert ws.receive_json()["type"] == "ready"
                                # Silence total : fermeture serveur (1001).
                                with pytest.raises(Exception):
                                    while True:
                                        ws.receive_json()

        service.cleanup_session.assert_awaited_once()
        assert "exec-mute" not in terminal_module.terminal_sessions
        assert any(call.args[3] == "disconnect" for call in mock_audit.await_args_list)

    def test_infinite_stream_cancelled_on_disconnect(self, ws_client):
        """Stream infini à la déconnexion → annulé (l.449-450), cleanup fait."""
        import asyncio

        _override_db()
        user = _make_user()
        session = _make_exec_session(exec_id="exec-inf")

        async def _endless_stream(session_arg):  # noqa: ARG001
            while True:
                await asyncio.sleep(0.05)
                yield (b"tick\n", False)

        service = MagicMock()
        service.create_session = AsyncMock(return_value=session)
        service.stream_output = _endless_stream
        service.send_input = AsyncMock()
        service.resize_tty = AsyncMock()
        service.cleanup_session = AsyncMock()
        service.close = AsyncMock()

        with _auth_stack(user):
            with _service_patch(service):
                with ws_client.websocket_connect(TERMINAL) as ws:
                    ws.send_json({"type": "auth", "token": "valid.jwt"})
                    assert ws.receive_json()["type"] == "ready"
                    # Fermeture immédiate : la tâche de streaming (infinie)
                    # est annulée dans le finally → CancelledError absorbé.

        service.cleanup_session.assert_awaited_once()
        assert "exec-inf" not in terminal_module.terminal_sessions

    async def test_streaming_error_sends_error_message(self):
        """stream_output lève → message error « Streaming error » (l.355-365)."""
        import asyncio

        from app.config import settings
        from app.websocket.terminal import container_terminal_websocket_endpoint

        user = _make_user()
        session = _make_exec_session(exec_id="exec-err")

        async def _failing_stream(session_arg):  # noqa: ARG001
            raise RuntimeError("docker stream broke")
            yield  # pragma: no cover — async generator

        service = MagicMock()
        service.create_session = AsyncMock(return_value=session)
        service.stream_output = _failing_stream
        service.cleanup_session = AsyncMock()
        service.close = AsyncMock()

        websocket = AsyncMock()
        websocket.url.path = TERMINAL

        async def _no_message():
            await asyncio.Event().wait()

        websocket.receive_text = AsyncMock(side_effect=_no_message)

        with patch(
            "app.websocket.terminal.authenticate_ws_first_message",
            new=AsyncMock(return_value=user),
        ):
            with patch(
                "app.websocket.terminal.ensure_role_ws",
                new=AsyncMock(return_value=user),
            ):
                with patch(
                    "app.websocket.terminal.database", new=_mock_database_module()
                ):
                    with _service_patch(service):
                        # Client muet : expiration rapide (1 s) pour sortir
                        # de la boucle après l'erreur de streaming.
                        with patch.object(settings, "ws_heartbeat_interval_seconds", 1):
                            with patch.object(
                                settings, "ws_heartbeat_timeout_factor", 1
                            ):
                                await asyncio.wait_for(
                                    container_terminal_websocket_endpoint(
                                        websocket, "container-1"
                                    ),
                                    timeout=5.0,
                                )

        sent = [
            (call.args[0] if call.args else call.kwargs)
            for call in websocket.send_json.await_args_list
        ]
        errors = [m for m in sent if isinstance(m, dict) and m.get("type") == "error"]
        assert any("Streaming error" in m["message"] for m in errors)
        service.cleanup_session.assert_awaited_once()

    async def test_loop_exception_breaks_silently_and_cleans_up(self, caplog):
        """Exception de réception dans la boucle interne (l.432-434) →
        logguée + break **silencieux** (aucun error envoyé au client),
        cleanup complet du finally."""
        import logging

        from app.websocket.terminal import container_terminal_websocket_endpoint

        user = _make_user()
        session = _make_exec_session(exec_id="exec-boom")
        service = _terminal_service_mock(session=session)

        websocket = AsyncMock()
        websocket.url.path = TERMINAL

        with patch(
            "app.websocket.terminal.authenticate_ws_first_message",
            new=AsyncMock(return_value=user),
        ):
            with patch(
                "app.websocket.terminal.ensure_role_ws",
                new=AsyncMock(return_value=user),
            ):
                with patch(
                    "app.websocket.terminal.database", new=_mock_database_module()
                ):
                    with patch(
                        "app.websocket.terminal.receive_with_expiry",
                        new=AsyncMock(side_effect=RuntimeError("loop boom")),
                    ):
                        with _service_patch(service):
                            await container_terminal_websocket_endpoint(
                                websocket, "container-1"
                            )

        # Comportement actuel : break silencieux — l'exception est logguée…
        with_caplog = [
            r
            for r in caplog.records
            if r.name == "app.websocket.terminal"
            and r.levelno >= logging.ERROR
            and "loop boom" in r.getMessage()
        ]
        assert with_caplog, "l'exception de boucle doit être logguée (ERROR)"
        # …mais AUCUN message d'erreur n'est envoyé au client (break interne).
        sent = [
            (call.args[0] if call.args else call.kwargs)
            for call in websocket.send_json.await_args_list
        ]
        assert not [m for m in sent if isinstance(m, dict) and m.get("type") == "error"]
        # Cleanup complet du finally.
        service.cleanup_session.assert_awaited_once()
        assert "exec-boom" not in terminal_module.terminal_sessions

    async def test_outer_exception_sends_error_message(self):
        """Exception **hors** boucle interne (l.436-441) → message error au
        client puis sortie propre — simulée par check_terminal_rate_limit."""
        from app.websocket.terminal import container_terminal_websocket_endpoint

        user = _make_user()
        service = _terminal_service_mock(session=_make_exec_session())

        websocket = AsyncMock()
        websocket.url.path = TERMINAL

        with patch(
            "app.websocket.terminal.authenticate_ws_first_message",
            new=AsyncMock(return_value=user),
        ):
            with patch(
                "app.websocket.terminal.ensure_role_ws",
                new=AsyncMock(return_value=user),
            ):
                with patch(
                    "app.websocket.terminal.database", new=_mock_database_module()
                ):
                    with patch(
                        "app.websocket.terminal.check_terminal_rate_limit",
                        new=AsyncMock(side_effect=RuntimeError("store exploded")),
                    ):
                        with _service_patch(service):
                            await container_terminal_websocket_endpoint(
                                websocket, "container-1"
                            )

        sent = [
            (call.args[0] if call.args else call.kwargs)
            for call in websocket.send_json.await_args_list
        ]
        errors = [m for m in sent if isinstance(m, dict) and m.get("type") == "error"]
        assert errors, "un message error doit être envoyé sur exception externe"
        assert "store exploded" in errors[0]["message"]
        # Aucune session créée (échec avant create_session).
        service.create_session.assert_not_awaited()

    async def test_output_send_failure_breaks_stream(self):
        """send_json lève pendant le stream → break silencieux (l.342-344)."""
        import asyncio

        from app.config import settings
        from app.websocket.terminal import container_terminal_websocket_endpoint

        user = _make_user()
        session = _make_exec_session(exec_id="exec-sendfail", returncode=0)

        websocket = AsyncMock()
        websocket.url.path = TERMINAL

        def _failing_send(message):
            if isinstance(message, dict) and message.get("type") == "output":
                raise RuntimeError("closed")
            return None

        websocket.send_json = AsyncMock(side_effect=_failing_send)

        async def _no_message():
            await asyncio.Event().wait()

        websocket.receive_text = AsyncMock(side_effect=_no_message)

        service = _terminal_service_mock(session=session)

        with patch(
            "app.websocket.terminal.authenticate_ws_first_message",
            new=AsyncMock(return_value=user),
        ):
            with patch(
                "app.websocket.terminal.ensure_role_ws",
                new=AsyncMock(return_value=user),
            ):
                with patch(
                    "app.websocket.terminal.database", new=_mock_database_module()
                ):
                    with _service_patch(service):
                        # Client muet : expiration rapide (1 s) pour sortir
                        # de la boucle après le break du stream.
                        with patch.object(settings, "ws_heartbeat_interval_seconds", 1):
                            with patch.object(
                                settings, "ws_heartbeat_timeout_factor", 1
                            ):
                                await asyncio.wait_for(
                                    container_terminal_websocket_endpoint(
                                        websocket, "container-1"
                                    ),
                                    timeout=5.0,
                                )

        service.cleanup_session.assert_awaited_once()


class TestTerminalRateLimitUnit:
    """check/register/unregister : comportement réel du store (non couvert
    ailleurs — test_ws_rbac.py patche le check sans le tester)."""

    async def test_under_limit_allowed(self):
        allowed, message = await terminal_module.check_terminal_rate_limit("u1")
        assert allowed is True
        assert message == ""

    async def test_at_limit_refused_with_message(self):
        for i in range(3):
            await terminal_module.register_terminal_session(f"e{i}", "u1", "c1")

        allowed, message = await terminal_module.check_terminal_rate_limit("u1")
        assert allowed is False
        assert "Maximum 3 terminal sessions" in message

    async def test_limit_isolated_per_user(self):
        """3 sessions du user A ne bloquent pas le user B."""
        for i in range(3):
            await terminal_module.register_terminal_session(f"a{i}", "user-a", "c1")

        allowed, _ = await terminal_module.check_terminal_rate_limit("user-b")
        assert allowed is True

    async def test_unregister_frees_a_slot(self):
        for i in range(3):
            await terminal_module.register_terminal_session(f"e{i}", "u1", "c1")
        await terminal_module.unregister_terminal_session("e1")

        allowed, message = await terminal_module.check_terminal_rate_limit("u1")
        assert allowed is True
        assert message == ""

    async def test_unregister_unknown_exec_id_is_noop(self):
        """unregister d'un id inconnu : no-op silencieux (pas d'exception)."""
        await terminal_module.unregister_terminal_session("ghost")
        assert "ghost" not in terminal_module.terminal_sessions
