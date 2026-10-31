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


class TestSSHCircuitBreaker:
    """STORY-251 : circuit ``ssh:{host_id}`` — transport uniquement (H4).

    Le paramètre ``circuit_name`` est optionnel : sans lui, comportement
    131.3 strictement inchangé. Seuls les exit 124 (timeout) et 255
    (échec SSH) comptent comme panne de l'hôte.
    """

    CIRCUIT = "ssh:11111111-2222-3333-4444-555555555555"

    @pytest.fixture(autouse=True)
    def _isolate(self, monkeypatch):
        from app.config import settings as app_settings
        from app.core.resilience import get_circuit_breaker_registry

        get_circuit_breaker_registry().reset_all()
        monkeypatch.setattr(app_settings, "circuit_breaker_enabled", True)
        monkeypatch.setattr(app_settings, "circuit_breaker_failure_threshold", 2)
        yield
        get_circuit_breaker_registry().reset_all()

    def _circuit(self):
        from app.core.resilience import get_circuit_breaker_registry

        return get_circuit_breaker_registry().get_or_create(self.CIRCUIT)

    def _conn_transport_failure(self, exit_status: int) -> MagicMock:
        """Connexion dont run échoue en échec transport (124 ou 255)."""
        conn = MagicMock()
        conn.run = AsyncMock(
            side_effect=CommandExecutionError("cmd", exit_status, "transport")
        )
        return conn

    async def test_ssh_transport_error_counts_failure(self):
        """exit_status=255 → échec compté."""
        executor = SSHCommandExecutor(
            self._conn_transport_failure(255), circuit_name=self.CIRCUIT
        )
        with pytest.raises(CommandExecutionError):
            await executor.run("cmd")
        assert self._circuit().failure_count == 1

    async def test_ssh_timeout_counts_failure(self):
        """exit_status=124 → échec compté."""
        executor = SSHCommandExecutor(
            self._conn_transport_failure(124), circuit_name=self.CIRCUIT
        )
        with pytest.raises(CommandExecutionError):
            await executor.run("cmd")
        assert self._circuit().failure_count == 1

    async def test_ssh_business_exit_code_does_not_count(self):
        """H4 : exit 1 métier (require_success) → re-raise sans comptage."""
        conn = _make_conn()
        conn.run.return_value.exit_status = 1
        conn.run.return_value.stderr = "script failed"
        executor = SSHCommandExecutor(conn, circuit_name=self.CIRCUIT)
        with pytest.raises(CommandExecutionError) as exc_info:
            await executor.run("failing-script", require_success=True)
        assert exc_info.value.exit_status == 1
        # Un script qui échoue n'ouvre JAMAIS le circuit
        assert self._circuit().failure_count == 0
        assert self._circuit().state.value == "closed"

    async def test_open_ssh_circuit_rejects_before_run(self):
        """Circuit ouvert → CircuitBreakerOpenError, conn.run jamais appelé."""
        from app.core.exceptions import CircuitBreakerOpenError

        conn = self._conn_transport_failure(255)
        executor = SSHCommandExecutor(conn, circuit_name=self.CIRCUIT)
        for _ in range(2):  # threshold=2 → OPEN
            with pytest.raises(CommandExecutionError):
                await executor.run("cmd")
        assert self._circuit().state.value == "open"
        assert conn.run.await_count == 2

        with pytest.raises(CircuitBreakerOpenError):
            await executor.run("cmd")
        assert conn.run.await_count == 2  # aucune tentative réseau supplémentaire

    async def test_ssh_executor_without_circuit_name_unchanged(self):
        """Non-régression 131.3 : sans circuit_name, aucun breaker."""
        conn = self._conn_transport_failure(255)
        executor = SSHCommandExecutor(conn)  # signature historique
        for _ in range(3):  # au-delà du threshold global
            with pytest.raises(CommandExecutionError):
                await executor.run("cmd")
        from app.core.resilience import get_circuit_breaker_registry

        # Aucun circuit créé, aucun rejet : comportement historique
        assert self.CIRCUIT not in get_circuit_breaker_registry().get_all_states()
        assert conn.run.await_count == 3


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
