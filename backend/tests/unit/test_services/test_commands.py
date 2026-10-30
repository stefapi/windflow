"""Non-régression de ``SSHCommandExecutor`` après le refactor TOFU (STORY-131.3, famille 11).

L'AC 2 de la story : le flux ``commands.py`` est **inchangé côté
appelants** — ``SSHCommandExecutor`` reçoit une connexion asyncssh
déjà établie (la vérification TOFU se joue en amont, dans le helper
``ssh_connection``). Ces tests verrouillent le contrat existant :

- signature ``run(command, timeout, require_success)`` inchangée ;
- wrapping sudo (préfixe + stdin password) inchangé ;
- ``CommandResult`` (exit_status/stdout/stderr) inchangé ;
- erreurs : timeout → ``CommandExecutionError`` 124, erreur SSH →
  ``CommandExecutionError`` 255, ``require_success`` → raise ;
- complément scanner (R2) : ``_build_ssh_kwargs`` délègue désormais
  au helper TOFU (mock ``build_ssh_kwargs``) et ne produit jamais de
  ``known_hosts``.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import asyncssh
import pytest

from app.core.exceptions import CommandExecutionError
from app.schemas.target_scan import ScanRequest
from app.services.commands import CommandResult, SSHCommandExecutor
from app.services.host_scanner_service import TargetScannerService
from app.services.ssh_connection import HostKeyPolicy


def _make_conn() -> MagicMock:
    """Connexion asyncssh factice (run → result exit 0)."""
    conn = MagicMock()
    completed = MagicMock()
    completed.exit_status = 0
    completed.stdout = "ok"
    completed.stderr = ""
    conn.run = AsyncMock(return_value=completed)
    return conn


class TestSSHCommandExecutorUnchanged:
    """Contrat ``SSHCommandExecutor`` — inchangé par STORY-131.3."""

    def test_signature_unchanged(self):
        """Signature historique (connection, sudo_user, sudo_password)."""
        executor = SSHCommandExecutor(
            _make_conn(), sudo_user="root", sudo_password="pw"
        )
        assert executor._sudo_user == "root"
        assert executor._sudo_password == "pw"

    async def test_run_returns_command_result(self):
        """run → CommandResult(exit_status, stdout, stderr) tel quel."""
        executor = SSHCommandExecutor(_make_conn())
        result = await executor.run("uname -a")
        assert isinstance(result, CommandResult)
        assert result.exit_status == 0
        assert result.stdout == "ok"
        assert result.success is True

    async def test_run_wraps_sudo_prefix_and_stdin(self):
        """sudo_user → préfixe sudo + password en stdin (comportement inchangé).

        Le préfixe historique est ``sudo -S -p '' -u <user>`` (lecture
        du mot de passe sur stdin, prompt vide) — inchangé par
        STORY-131.3 (AC 2 : flux commands.py inchangé côté appelants).
        """
        conn = _make_conn()
        executor = SSHCommandExecutor(conn, sudo_user="root", sudo_password="secret")
        await executor.run("apt update")
        call = conn.run.await_args
        assert call.args[0] == "sudo -S -p '' -u root apt update"
        assert call.kwargs["input"] == "secret\n"

    async def test_run_require_success_raises_on_failure(self):
        """Échec + require_success → CommandExecutionError."""
        conn = _make_conn()
        conn.run.return_value.exit_status = 2
        conn.run.return_value.stderr = "boom"
        executor = SSHCommandExecutor(conn)
        with pytest.raises(CommandExecutionError) as exc_info:
            await executor.run("failing-cmd", require_success=True)
        assert exc_info.value.exit_status == 2

    async def test_run_timeout_raises_124(self):
        """Timeout → CommandExecutionError exit 124 (inchangé)."""
        import asyncio

        conn = MagicMock()

        async def slow_run(*args, **kwargs):
            await asyncio.sleep(10)

        conn.run = slow_run
        executor = SSHCommandExecutor(conn)
        with pytest.raises(CommandExecutionError) as exc_info:
            await executor.run("slow", timeout=1)
        assert exc_info.value.exit_status == 124

    async def test_run_ssh_error_raises_255(self):
        """Erreur SSH en cours de commande → CommandExecutionError 255."""
        conn = MagicMock()
        conn.run = AsyncMock(
            side_effect=asyncssh.Error(asyncssh.DISC_CONNECTION_LOST, "connection lost")
        )
        executor = SSHCommandExecutor(conn)
        with pytest.raises(CommandExecutionError) as exc_info:
            await executor.run("cmd")
        assert exc_info.value.exit_status == 255


class TestScannerDelegatesToHelper:
    """R2 — le scanner délègue ses kwargs au helper TOFU (STORY-131.3)."""

    async def test_build_ssh_kwargs_delegates_to_helper(self):
        """_build_ssh_kwargs appelle ssh_connection.build_ssh_kwargs
        (STRICT) et retourne ses kwargs tels quels."""
        sentinel_kwargs = {
            "host": "h",
            "port": 22,
            "username": "u",
            "server_host_key_verify": lambda: None,
        }
        with patch(
            "app.services.host_scanner_service.build_ssh_kwargs",
            new=AsyncMock(return_value=sentinel_kwargs),
        ) as mock_helper:
            result = await TargetScannerService._build_ssh_kwargs(
                ScanRequest(host="h", username="u", password="p")
            )
        assert result is sentinel_kwargs
        mock_helper.assert_awaited_once()
        # Politique STRICT imposée (sessions opérationnelles).
        assert mock_helper.call_args.kwargs["mode"] is HostKeyPolicy.STRICT

    async def test_scan_remote_wraps_tofu_blocking_as_command_error(self):
        """Blocage TOFU (SSHHostKeyNotAcceptedError) → CommandExecutionError
        wrapping (contrat historique de scan_remote inchangé côté appelants)."""
        from unittest.mock import patch

        from app.core.exceptions import SSHHostKeyNotAcceptedError

        scanner = TargetScannerService()
        with patch(
            "app.services.host_scanner_service.build_ssh_kwargs",
            new=AsyncMock(side_effect=SSHHostKeyNotAcceptedError()),
        ):
            with pytest.raises(CommandExecutionError) as exc_info:
                await scanner.scan_remote(
                    ScanRequest(host="h", username="u", password="p")
                )
        assert exc_info.value.exit_status == 255
        assert "acceptation explicite" in exc_info.value.stderr
