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
        super().__init__(
            message,
            details={
                "command": command,
                "exit_status": exit_status,
                "stderr": self.stderr,
            },
        )


class SecretEncryptionError(WindFlowException):
    """Levée lorsqu'une opération de chiffrement de secret échoue.

    Le message ne contient jamais de matériel cryptographique
    (ni clé maîtresse, ni valeur chiffrée/déchiffrée).
    """


class SecretDecryptionError(WindFlowException):
    """Levée lorsqu'une opération de déchiffrement de secret échoue.

    Typiquement : mauvaise clé maîtresse, ciphertext corrompu ou
    altéré (Fernet invalide la signature HMAC). Le message ne contient
    jamais de matériel cryptographique.
    """


class InvalidRefreshTokenError(WindFlowException):
    """Levée lorsqu'un refresh token est invalide (STORY-123.2).

    Token inconnu, expiré, consommé ou malformé. Refus sémantique
    ``401 INVALID_OR_EXPIRED_TOKEN`` (spec 09) — le message ne divulgue
    ni la valeur du token ni la raison exacte (anti-énumération) :
    l'appelant (STORY-123.3) mappe systématiquement à 401.
    """

    def __init__(self, reason: str = "Invalid or expired refresh token") -> None:
        self.reason = reason
        super().__init__(reason)
