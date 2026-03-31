"""
Exécuteurs de commandes pour le scan de cibles (local et distant).

Fournit un protocole commun (:class:`CommandExecutor`) et deux implémentations :
- :class:`LocalCommandExecutor` pour les commandes locales via subprocess
- :class:`SSHCommandExecutor` pour les commandes distantes via asyncssh
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

import asyncssh
from asyncssh import ConnectionLost

from ..core.exceptions import CommandExecutionError


# ─── Résultat de commande ─────────────────────────────────────


@dataclass(slots=True)
class CommandResult:
    """Résultat d'une exécution de commande."""

    exit_status: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        """Retourne ``True`` si le code de retour est 0."""
        return self.exit_status == 0

    def stripped_stdout(self) -> str:
        """Retourne stdout sans espaces de début/fin."""
        return self.stdout.strip()

    def stripped_stderr(self) -> str:
        """Retourne stderr sans espaces de début/fin."""
        return self.stderr.strip()


# ─── Protocole ────────────────────────────────────────────────


class CommandExecutor(Protocol):
    """Protocole décrivant un exécuteur de commande."""

    async def run(  # noqa: E704
        self, command: str, timeout: int = 30, require_success: bool = False
    ) -> CommandResult: ...


# ─── Helpers partagés ─────────────────────────────────────────


def _build_sudo_prefix(sudo_user: str) -> str:
    """Construit le préfixe sudo pour une commande.

    Args:
        sudo_user: Utilisateur cible pour sudo.

    Returns:
        Préfixe sudo formaté.
    """
    parts = ["sudo", "-S", "-p", "''", "-u", sudo_user]
    return " ".join(parts)


# ─── Exécuteur local ─────────────────────────────────────────


class LocalCommandExecutor:
    """Exécute des commandes sur la machine locale via subprocess."""

    def __init__(
        self, sudo_user: str | None = None, sudo_password: str | None = None
    ):
        self._sudo_user = sudo_user
        self._sudo_password = sudo_password

    async def run(
        self, command: str, timeout: int = 30, require_success: bool = False
    ) -> CommandResult:
        """Exécute une commande locale avec option sudo.

        Args:
            command: Commande shell à exécuter.
            timeout: Délai maximal en secondes.
            require_success: Si ``True``, lève une exception en cas d'échec.

        Returns:
            Le résultat de la commande.

        Raises:
            CommandExecutionError: En cas de timeout ou d'échec (si ``require_success``).
        """
        wrapped = _build_sudo_prefix(self._sudo_user) + " " + command if self._sudo_user else command
        process = await self._launch_process(wrapped)
        stdout_bytes, stderr_bytes = await self._communicate(process, command, timeout)
        result = self._build_result(process, stdout_bytes, stderr_bytes)

        if require_success and not result.success:
            raise CommandExecutionError(command, result.exit_status, result.stderr)
        return result

    async def _launch_process(self, wrapped_command: str):
        """Lance le sous-processus avec ou sans stdin selon sudo."""
        stdin_pipe = asyncio.subprocess.PIPE if self._sudo_user else None
        process = await asyncio.create_subprocess_shell(
            wrapped_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=stdin_pipe,
        )
        if self._sudo_user and self._sudo_password:
            await self._pipe_password(process)
        return process

    async def _pipe_password(self, process: asyncio.subprocess.Process) -> None:
        """Envoie le mot de passe sudo via stdin."""
        if not process.stdin:
            return
        payload = f"{self._sudo_password}\n".encode("utf-8")
        process.stdin.write(payload)
        await process.stdin.drain()
        process.stdin.close()

    async def _communicate(self, process, command: str, timeout: int):
        """Attend la fin du processus avec timeout.

        Args:
            process: Processus en cours.
            command: Commande d'origine (pour le message d'erreur).
            timeout: Délai maximal en secondes.

        Returns:
            Tuple (stdout_bytes, stderr_bytes).

        Raises:
            CommandExecutionError: En cas de timeout.
        """
        try:
            return await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            process.kill()
            raise CommandExecutionError(
                command,
                exit_status=124,
                stderr=f"Commande expirée après {timeout}s : {exc}",
            ) from exc

    @staticmethod
    def _build_result(process, stdout_bytes: bytes, stderr_bytes: bytes) -> CommandResult:
        """Construit le CommandResult à partir des sorties du processus."""
        stdout = stdout_bytes.decode("utf-8", errors="ignore")
        stderr = stderr_bytes.decode("utf-8", errors="ignore")
        return CommandResult(process.returncode, stdout, stderr)


# ─── Exécuteur SSH ────────────────────────────────────────────


class SSHCommandExecutor:
    """Exécute des commandes sur un hôte distant via asyncssh."""

    def __init__(
        self,
        connection: asyncssh.SSHClientConnection,
        sudo_user: str | None = None,
        sudo_password: str | None = None,
    ):
        self._connection = connection
        self._sudo_user = sudo_user
        self._sudo_password = sudo_password

    async def run(
        self, command: str, timeout: int = 30, require_success: bool = False
    ) -> CommandResult:
        """Exécute une commande distante avec option sudo.

        Args:
            command: Commande shell à exécuter.
            timeout: Délai maximal en secondes.
            require_success: Si ``True``, lève une exception en cas d'échec.

        Returns:
            Le résultat de la commande.

        Raises:
            CommandExecutionError: En cas de timeout, erreur SSH ou d'échec.
        """
        wrapped = _build_sudo_prefix(self._sudo_user) + " " + command if self._sudo_user else command
        input_payload = f"{self._sudo_password}\n" if (self._sudo_user and self._sudo_password) else None

        completed = await self._execute_remote(wrapped, command, input_payload, timeout)
        result = CommandResult(
            completed.exit_status, completed.stdout or "", completed.stderr or ""
        )

        if require_success and not result.success:
            raise CommandExecutionError(command, result.exit_status, result.stderr)
        return result

    async def _execute_remote(self, wrapped_command, original_command, input_payload, timeout):
        """Exécute la commande via SSH avec gestion des erreurs.

        Args:
            wrapped_command: Commande (avec préfixe sudo si applicable).
            original_command: Commande d'origine (pour le message d'erreur).
            input_payload: Données à envoyer via stdin.
            timeout: Délai maximal en secondes.

        Returns:
            Le résultat asyncssh.

        Raises:
            CommandExecutionError: En cas de timeout ou erreur SSH.
        """
        try:
            return await asyncio.wait_for(
                self._connection.run(
                    wrapped_command,
                    input=input_payload,
                    check=False,
                    encoding="utf-8",
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise CommandExecutionError(
                original_command,
                exit_status=124,
                stderr=f"Commande distante expirée après {timeout}s",
            ) from exc
        except (asyncssh.Error, ConnectionLost) as exc:
            raise CommandExecutionError(
                original_command, exit_status=255, stderr=f"Échec SSH : {exc}"
            ) from exc
