"""Tests du canal WebSocket ``/ws/journal/{host_id}`` (STORY-164.2 — AC 1/2).

Patterns ``test_ws_rbac.py`` : auth query param (close 1008 sans token),
RBAC (operator — matrice spec 08 § Hosts, divergence vs décision
d'analyse « viewer » signalée), runner SSH **mocké** (``AsyncMock`` —
jamais de vraie connexion), streaming journalctl → messages ``log`` +
``stream_status``, ``tail`` borné, Host non-systemd → ``error``,
TOFU STRICT, isolation organisation.
"""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth import dependencies as auth_dependencies
from app.core.exceptions import SSHHostKeyMismatchError, SSHHostKeyNotAcceptedError
from app.main import app
from app.models.user import User
from app.services.authorization_service import AuthorizationService

JOURNAL = "/api/v1/ws/journal/host-1"


# ===========================================================================
# Helpers (patterns test_ws_ssh_session)
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
    target = MagicMock()
    target.id = "host-1"
    target.host = "192.168.1.10"
    target.port = 22
    target.ssh_key_id = None
    target.organization_id = "org-1"
    target.decrypted_credentials = {"username": "deploy"}
    target.access_profile = None
    return target


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
    return patch(
        "app.websocket.journal.resolve_host_and_check_access",
        new=AsyncMock(return_value=_make_target()),
    )


def _journal_process(lines: list[str] | None = None):
    """Process journalctl mocké : stdout asynchrone émettant les lignes."""
    process = MagicMock()

    async def _stdout():
        for line in lines or []:
            yield line

    process.stdout = _stdout()
    process.wait = AsyncMock(return_value=0)
    process.close = MagicMock()
    return process


def _ssh_stack(
    process: MagicMock | None = None, connect_error: Exception | None = None
):
    """Empile build_ssh_kwargs OK + asyncssh.connect mocké."""
    connection = AsyncMock()
    if process is None:
        process = _journal_process()
    connection.create_process = AsyncMock(return_value=process)

    async def _connect(**kwargs):
        if connect_error is not None:
            raise connect_error
        return connection

    stack = ExitStack()
    stack.enter_context(
        patch(
            "app.websocket.journal.build_ssh_kwargs",
            new=AsyncMock(return_value={"host": "192.168.1.10"}),
        )
    )
    stack.enter_context(patch("app.websocket.journal.asyncssh.connect", new=_connect))
    return stack


def _auth_stack(user: User):
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


def _collect_messages(ws, max_messages: int = 50, until_status: str | None = None):
    """Consomme les messages jusqu'au stream_status demandé ou épuisement.

    ``until_status`` cible le statut du message ``stream_status`` (ex.
    ``"ended"``) — les lignes ``log`` précèdent le statut de fin.
    """
    messages = []
    for _ in range(max_messages):
        try:
            message = ws.receive_json()
        except Exception:
            break
        messages.append(message)
        if (
            until_status
            and message.get("type") == "stream_status"
            and message.get("status") == until_status
        ):
            break
    return messages


# ===========================================================================
# AC 1 — Auth 1008 sans token / RBAC operator (divergence matrice signalée)
# ===========================================================================


class TestJournalAuthAndRbac:
    """Auth obligatoire + RBAC operator (matrice spec 08 § Hosts)."""

    def test_no_token_refused_1008(self, ws_client):
        """Sécurité : sans token → handshake refusé (1008)."""
        _override_db()
        with patch.object(auth_dependencies.settings, "disable_auth", False):
            with pytest.raises(Exception):
                with ws_client.websocket_connect(JOURNAL):
                    pass

    def test_viewer_refused(self, ws_client):
        """RBAC : viewer → 1008 (journalctl = Operator+, matrice spec 08)."""
        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("viewer"):
                with pytest.raises(Exception):
                    with ws_client.websocket_connect(JOURNAL + "?token=valid.jwt"):
                        pass

    def test_operator_accepted(self, ws_client):
        """Cas nominal : operator → accepté, messages initial/stream_status."""
        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with _access_granted():
                    with _ssh_stack(_journal_process(["line-1"])):
                        with ws_client.websocket_connect(
                            JOURNAL + "?token=valid.jwt"
                        ) as ws:
                            messages = _collect_messages(ws, until_status="started")
                            types = [m["type"] for m in messages]
                            assert "initial" in types
                            assert "stream_status" in types
                            initial = next(
                                m for m in messages if m["type"] == "initial"
                            )
                            assert initial["host_id"] == "host-1"
                            assert initial["tail"] == 100

    def test_disable_auth_accepted(self, ws_client):
        """disable_auth (dev) : auto-login superadmin → accepté."""
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
                        with _ssh_stack(_journal_process([])):
                            with ws_client.websocket_connect(JOURNAL) as ws:
                                messages = _collect_messages(ws, until_status="started")
                                assert any(m["type"] == "initial" for m in messages)


# ===========================================================================
# AC 2 — Streaming journalctl mocké + tail borné
# ===========================================================================


class TestJournalStreaming:
    """Streaming lignes journalctl → messages log + stream_status."""

    def test_lines_streamed_as_log_messages(self, ws_client):
        """Chaque ligne journalctl → {"type":"log","data":ligne}."""
        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with _access_granted():
                    with _ssh_stack(_journal_process(["kernel: boot", "sshd: ok"])):
                        with ws_client.websocket_connect(
                            JOURNAL + "?token=valid.jwt"
                        ) as ws:
                            # Attend la fin du flux (les lignes précèdent
                            # le stream_status ended).
                            messages = _collect_messages(ws, until_status="ended")
                            log_messages = [m for m in messages if m["type"] == "log"]
                            datas = [m["data"] for m in log_messages]
                            assert "kernel: boot" in datas
                            assert "sshd: ok" in datas

    def test_tail_transmitted_and_bounded(self, ws_client):
        """tail transmis à journalctl et borné (rejet hors bornes)."""
        from app.websocket.journal import JOURNAL_TAIL_MAX, validate_journal_tail

        # Validation unitaire : bornes rejetées
        with pytest.raises(ValueError):
            validate_journal_tail(-1)
        with pytest.raises(ValueError):
            validate_journal_tail(JOURNAL_TAIL_MAX + 1)
        assert validate_journal_tail(50) == 50

        # Route : Query(ge/le) refuse un tail hors bornes (422/close)
        _override_db()
        user = _make_user()
        with _auth_stack(user):
            with _patch_global_role("operator"):
                with pytest.raises(Exception):
                    with ws_client.websocket_connect(
                        JOURNAL + "?token=valid.jwt&tail=999999"
                    ):
                        pass

    def test_non_systemd_host_error_message(self, ws_client):
        """Host non-systemd (exit ≠ 0) → message error explicite + fermeture."""
        _override_db()
        user = _make_user()

        process = _journal_process([])
        process.wait = AsyncMock(return_value=127)  # command not found

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with _access_granted():
                    with _ssh_stack(process):
                        with ws_client.websocket_connect(
                            JOURNAL + "?token=valid.jwt"
                        ) as ws:
                            messages = _collect_messages(ws, max_messages=30)
                            error_messages = [
                                m for m in messages if m["type"] == "error"
                            ]
                            assert error_messages, "pas de message error sur exit 127"
                            assert "journalctl" in error_messages[0]["message"].lower()


# ===========================================================================
# TOFU STRICT + isolation organisation
# ===========================================================================


class TestJournalTofuAndIsolation:
    """TOFU STRICT identique au canal SSH + isolation organisation."""

    def test_unknown_fingerprint_generic_error(self, ws_client):
        """Empreinte inconnue → 1011, message SANS empreinte."""
        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with _access_granted():
                    with _ssh_stack(
                        connect_error=SSHHostKeyNotAcceptedError(
                            "unknown SHA256:SECRET"
                        )
                    ):
                        with ws_client.websocket_connect(
                            JOURNAL + "?token=valid.jwt"
                        ) as ws:
                            message = ws.receive_json()
                            assert message["type"] == "error"
                            assert "SHA256" not in message["message"]
                            assert "SECRET" not in message["message"]

    def test_mismatch_fingerprint_generic_error(self, ws_client):
        """Divergence → message générique (jamais les empreintes)."""
        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with _access_granted():
                    with _ssh_stack(
                        connect_error=SSHHostKeyMismatchError(
                            "SHA256:AAA != SHA256:BBB"
                        )
                    ):
                        with ws_client.websocket_connect(
                            JOURNAL + "?token=valid.jwt"
                        ) as ws:
                            message = ws.receive_json()
                            assert message["type"] == "error"
                            assert "AAA" not in message["message"]

    def test_foreign_organization_host_refused(self, ws_client):
        """Isolation : host d'une autre org → refus (403 traduit)."""
        from fastapi import HTTPException

        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with patch(
                    "app.websocket.journal.resolve_host_and_check_access",
                    new=AsyncMock(
                        side_effect=HTTPException(
                            status_code=403, detail="Access denied to this host"
                        )
                    ),
                ):
                    with ws_client.websocket_connect(
                        JOURNAL + "?token=valid.jwt"
                    ) as ws:
                        message = ws.receive_json()
                        assert message["type"] == "error"
                        assert "denied" in message["message"].lower()

    def test_host_not_found_closes(self, ws_client):
        """Host introuvable → message error (404 traduit)."""
        from fastapi import HTTPException

        _override_db()
        user = _make_user()

        with _auth_stack(user):
            with _patch_global_role("operator"):
                with patch(
                    "app.websocket.journal.resolve_host_and_check_access",
                    new=AsyncMock(
                        side_effect=HTTPException(
                            status_code=404, detail="Host not found"
                        )
                    ),
                ):
                    with ws_client.websocket_connect(
                        JOURNAL + "?token=valid.jwt"
                    ) as ws:
                        message = ws.receive_json()
                        assert message["type"] == "error"
                        assert "not found" in message["message"].lower()


# ===========================================================================
# Commande — garde anti-injection
# ===========================================================================


def test_journalctl_command_uses_bounded_integer():
    """La commande n'interpole que des entiers validés (anti-injection)."""
    from app.websocket.journal import _JOURNALCTL_COMMAND, validate_journal_tail

    tail = validate_journal_tail(200)
    command = _JOURNALCTL_COMMAND.format(tail=tail)
    assert command == "journalctl -f -n 200 --no-pager -o short-iso"
    # Aucun caractère de shell possible via tail validé
    assert ";" not in command and "&" not in command and "|" not in command


# ===========================================================================
# Branches d'erreur — handler direct avec WebSocket mockée (couverture ≥ 80 %)
# ===========================================================================


def _mute_ws() -> AsyncMock:
    """WebSocket mockée : receive_text muet (handler bloqué en boucle)."""
    websocket = AsyncMock()
    websocket.receive_text = AsyncMock(side_effect=asyncio.Event().wait)
    return websocket


def _then_mute(messages: list[str]) -> object:
    """Side effect receive_text : émet les messages donnés puis reste muet."""
    pending = list(messages)

    async def _receive():
        if pending:
            return pending.pop(0)
        await asyncio.Event().wait()

    return _receive


class TestJournalErrorBranches:
    """Branches d'erreur du handler non couvertes par l'E2E TestClient."""

    async def test_invalid_tail_closes_1008(self):
        """tail invalide passé au handler → error + close 1008 (garde)."""
        from app.websocket.journal import journal_websocket_endpoint

        websocket = _mute_ws()
        user = _make_user()
        session = AsyncMock()

        with _access_granted():
            # invalid tail → error + close + return : termine proprement.
            await asyncio.wait_for(
                journal_websocket_endpoint(
                    websocket, "host-1", user, session, tail=99_999_999
                ),
                timeout=3.0,
            )

        sent = [c.args[0] for c in websocket.send_json.await_args_list]
        assert any(m.get("type") == "error" for m in sent)
        websocket.close.assert_awaited()

    async def test_ssh_generic_error_closes_1011(self):
        """asyncssh.Error générique → error + close 1011."""
        import asyncssh as _asyncssh

        from app.websocket.journal import journal_websocket_endpoint

        websocket = _mute_ws()
        user = _make_user()
        session = AsyncMock()

        async def _connect_error(**kwargs):
            raise _asyncssh.ConnectionLost("unreachable")

        with _access_granted():
            with patch(
                "app.websocket.journal.build_ssh_kwargs",
                new=AsyncMock(return_value={}),
            ):
                with patch(
                    "app.websocket.journal.asyncssh.connect", new=_connect_error
                ):
                    # error → close → return : termine proprement.
                    await asyncio.wait_for(
                        journal_websocket_endpoint(websocket, "host-1", user, session),
                        timeout=3.0,
                    )

        sent = [c.args[0] for c in websocket.send_json.await_args_list]
        error_messages = [m for m in sent if m.get("type") == "error"]
        assert error_messages
        assert "SSH connection failed" in error_messages[0]["message"]
        websocket.close.assert_awaited()

    async def test_create_process_failure_closes(self):
        """Échec create_process → error « Failed to start journalctl » + close."""
        import asyncssh as _asyncssh

        from app.websocket.journal import journal_websocket_endpoint

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
                "app.websocket.journal.build_ssh_kwargs",
                new=AsyncMock(return_value={}),
            ):
                with patch("app.websocket.journal.asyncssh.connect", new=_connect):
                    # error → close → return : termine proprement.
                    await asyncio.wait_for(
                        journal_websocket_endpoint(websocket, "host-1", user, session),
                        timeout=3.0,
                    )

        sent = [c.args[0] for c in websocket.send_json.await_args_list]
        assert any(m.get("message") == "Failed to start journalctl" for m in sent)
        websocket.close.assert_awaited()
        connection.close.assert_called()

    async def test_ping_answered_with_pong(self):
        """ping client → pong (maintien de connexion)."""
        from app.websocket.journal import journal_websocket_endpoint

        websocket = AsyncMock()
        websocket.receive_text = AsyncMock(side_effect=_then_mute(["ping"]))
        user = _make_user()
        session = AsyncMock()
        process = _journal_process([])

        connection = AsyncMock()
        connection.create_process = AsyncMock(return_value=process)

        async def _connect(**kwargs):
            return connection

        with _access_granted():
            with patch(
                "app.websocket.journal.build_ssh_kwargs",
                new=AsyncMock(return_value={}),
            ):
                with patch("app.websocket.journal.asyncssh.connect", new=_connect):
                    with patch("app.websocket.journal.periodic_ping", new=AsyncMock()):
                        with pytest.raises(asyncio.TimeoutError):
                            await asyncio.wait_for(
                                journal_websocket_endpoint(
                                    websocket, "host-1", user, session
                                ),
                                timeout=3.0,
                            )

        sent = [c.args[0] for c in websocket.send_json.await_args_list]
        assert any(m.get("type") == "pong" for m in sent)
