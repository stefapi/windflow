"""
Exceptions de base pour l'application WindFlow.

Toutes les exceptions métier doivent hériter de :class:`WindFlowException`.
"""

from __future__ import annotations


class WindFlowException(Exception):
    """Exception de base pour toutes les erreurs WindFlow."""

    def __init__(self, message: str = "", *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class CommandExecutionError(WindFlowException):
    """Levée lorsqu'une commande système échoue (local ou distant).

    Attributes:
        command: La commande ayant échoué.
        exit_status: Code de retour du processus.
        stderr: Sortie d'erreur standard (déstrippée).
    """

    def __init__(
        self,
        command: str,
        exit_status: int,
        stderr: str,
    ):
        self.command = command
        self.exit_status = exit_status
        self.stderr = stderr.strip()
        message = (
            f"La commande '{command}' a échoué avec le code {exit_status}. "
            f"Stderr : {self.stderr}"
        )
        super().__init__(message, details={
            "command": command,
            "exit_status": exit_status,
            "stderr": self.stderr,
        })
