"""
SecretManager — chiffrement au repos des données sensibles (STORY-103.1).

Référence unique : docs/general_specs/15-securite.md § « SecretManager ».

- AES-256 via Fernet ;
- clé dérivée de la clé maîtresse par PBKDF2HMAC (salt ``windflow-secrets-v1``,
  480 000 itérations, SHA-256) — une seule version du salt ;
- ``encrypt(str) -> str`` / ``decrypt(str) -> str`` pour stockage/lire des
  valeurs en base (le ciphertext est ASCII urlsafe base64, préfixe ``gAAAA``).

Sécurité :
- la clé maîtresse et les valeurs déchiffrées ne sont JAMAIS loggées ;
- les erreurs de déchiffrement lèvent :class:`SecretDecryptionError`
  (héritant de ``WindFlowException``) sans révéler de matériel
  cryptographique ;
- la dérivation PBKDF2 (coûteuse) est effectuée une seule fois par
  instance et mise en cache.
"""

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .exceptions import SecretDecryptionError, SecretEncryptionError

# Paramètres de dérivation — spec 15-securite.md (ne jamais changer sur
# des données existantes : une seule version du salt).
_SALT: bytes = b"windflow-secrets-v1"
_ITERATIONS: int = 480_000
_KEY_LENGTH: int = 32  # AES-256

# Préfixe des tokens Fernet (version 0x80 + timestamp) — utilisé par le
# helper de détection de ciphertext pour la double lecture (STORY-103.2).
_FERNET_TOKEN_PREFIX: str = "gAAAA"


class SecretManager:
    """Chiffrement des données sensibles en base (AES-256 via Fernet).

    La clé Fernet est dérivée de ``master_key`` par PBKDF2HMAC (SHA-256,
    480 000 itérations, salt ``windflow-secrets-v1``) puis encodée en
    urlsafe base64. La dérivation est réalisée une seule fois, à la
    construction de l'instance.

    Example:
        >>> manager = SecretManager(master_key="instance-master-key")
        >>> token = manager.encrypt("my-password")
        >>> manager.decrypt(token)
        'my-password'
    """

    def __init__(self, master_key: str):
        """
        Args:
            master_key: Clé maîtresse de l'instance (ex. ``settings.master_encryption_key``).
                Ne doit jamais être loggée.

        Raises:
            SecretEncryptionError: Si la clé maîtresse est vide.
        """
        if not master_key:
            raise SecretEncryptionError(
                "SecretManager requiert une clé maîtresse non vide "
                "(vérifiez SECRET_ENCRYPTION_KEY / JWT_SECRET_KEY)."
            )
        self._fernet = Fernet(self._derive_key(master_key))

    @staticmethod
    def _derive_key(master_key: str) -> bytes:
        """Dérive la clé Fernet (urlsafe base64) de la clé maîtresse.

        Args:
            master_key: Clé maîtresse de l'instance.

        Returns:
            Clé Fernet encodée en urlsafe base64 (32 octets dérivés).
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=_KEY_LENGTH,
            salt=_SALT,
            iterations=_ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(master_key.encode()))

    def encrypt(self, plaintext: str) -> str:
        """Chiffre une valeur avant stockage en base.

        Args:
            plaintext: Valeur en clair (jamais loggée).

        Returns:
            Ciphertext Fernet (ASCII urlsafe base64, préfixe ``gAAAA``).

        Raises:
            SecretEncryptionError: Si le chiffrement échoue.
        """
        try:
            return self._fernet.encrypt(plaintext.encode()).decode()
        except Exception as exc:  # pragma: no cover - défense en profondeur
            raise SecretEncryptionError(
                "Échec du chiffrement d'un secret (détails internes masqués)."
            ) from exc

    def decrypt(self, ciphertext: str) -> str:
        """Déchiffre une valeur lue depuis la base.

        Args:
            ciphertext: Ciphertext Fernet produit par :meth:`encrypt`.

        Returns:
            Valeur en clair (jamais loggée).

        Raises:
            SecretDecryptionError: Mauvaise clé maîtresse, ciphertext
                corrompu ou altéré (HMAC invalide).
        """
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise SecretDecryptionError(
                "Échec du déchiffrement d'un secret : clé maîtresse "
                "incorrecte ou donnée chiffrée corrompue/altérée."
            ) from exc
        except Exception as exc:
            raise SecretDecryptionError(
                "Échec du déchiffrement d'un secret (format invalide)."
            ) from exc

    @staticmethod
    def is_encrypted(value: str) -> bool:
        """Détecte si une valeur stockée est un ciphertext Fernet.

        Helper de la migration « double lecture » (STORY-103.2) : les
        tokens Fernet commencent par ``gAAAA`` (version 0x80 + timestamp
        big-endian) ; un JSON en clair ne commence jamais ainsi.

        Heuristique volontairement simple : ``gAAAA`` étant improbable en
        début de donnée légitime en clair, elle suffit à discriminer.

        Args:
            value: Valeur lue depuis la base.

        Returns:
            True si la valeur ressemble à un ciphertext Fernet.
        """
        return value.startswith(_FERNET_TOKEN_PREFIX)


# Instance unique partagée (pattern de core/rate_limit.py) — construite
# paresseusement depuis les settings pour éviter une dérivation PBKDF2
# coûteuse à l'import et les cycles d'import.
_secret_manager: SecretManager | None = None


def get_secret_manager() -> SecretManager:
    """Retourne l'instance unique du SecretManager de l'application.

    La clé maîtresse est résolue depuis ``settings.master_encryption_key``
    (SECRET_ENCRYPTION_KEY dédiée, sinon fallback JWT_SECRET_KEY). La
    dérivation PBKDF2 n'est effectuée qu'une seule fois (cache).

    Returns:
        L'instance partagée :class:`SecretManager`.
    """
    global _secret_manager
    if _secret_manager is None:
        from ..config import settings

        _secret_manager = SecretManager(settings.master_encryption_key)
    return _secret_manager


def reset_secret_manager() -> None:
    """Réinitialise l'instance partagée (utilisé par les tests)."""
    global _secret_manager
    _secret_manager = None
