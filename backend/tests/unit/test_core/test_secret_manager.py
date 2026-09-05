"""
Tests unitaires du SecretManager — chiffrement au repos (STORY-103.1).

Vérifie (spec 15-securite.md § « SecretManager ») :
- round-trip : chiffre → déchiffre → valeur initiale ; ciphertext ≠ clair ;
- mauvaise clé maîtresse → ``SecretDecryptionError`` explicite ;
- helper de détection de ciphertext (préfixe Fernet ``gAAAA``) ;
- cas limites : chaîne vide, unicode, payloads longs (JSON credentials) ;
- intégration settings : fallback ``jwt_secret_key`` / clé dédiée,
  instance partagée ``get_secret_manager()`` ;
- sécurité : aucun matériel cryptographique dans les messages d'erreur.
"""

import pytest

from app.core.exceptions import (
    SecretDecryptionError,
    SecretEncryptionError,
    WindFlowException,
)
from app.core.secret_manager import (
    SecretManager,
    get_secret_manager,
    reset_secret_manager,
)

# Clés maîtresses factices de test (jamais utilisées ailleurs).
MASTER_KEY = "unit-test-master-key-0123456789abcdef"
OTHER_MASTER_KEY = "another-master-key-9876543210fedcba"

# JSON type "credentials cibles" (cas d'usage STORY-103.2).
CREDENTIALS_JSON = '{"username": "root", "password": "S3cr3t!Pass", "port": 22}'


class TestRoundTrip:
    """AC 1 — chiffre → déchiffre → valeur initiale ; ciphertext ≠ clair."""

    def test_round_trip_encrypt_decrypt(self):
        """Cas nominal : la valeur déchiffrée est identique à l'originale."""
        manager = SecretManager(MASTER_KEY)
        plaintext = "my-super-secret-password"

        ciphertext = manager.encrypt(plaintext)
        decrypted = manager.decrypt(ciphertext)

        assert decrypted == plaintext
        assert ciphertext != plaintext

    def test_ciphertext_is_fernet_token(self):
        """Le ciphertext produit est un token Fernet (préfixe ``gAAAA``)."""
        manager = SecretManager(MASTER_KEY)
        ciphertext = manager.encrypt("some-value")

        assert ciphertext.startswith("gAAAA")

    def test_plaintext_not_leaked_in_ciphertext(self):
        """Sécurité : la valeur en clair n'apparaît pas dans le ciphertext."""
        manager = SecretManager(MASTER_KEY)
        plaintext = "VeryPredictableSecretValue123"

        ciphertext = manager.encrypt(plaintext)

        assert plaintext not in ciphertext

    def test_encryption_is_non_deterministic(self):
        """Deux chiffrements de la même valeur diffèrent (IV Fernet)."""
        manager = SecretManager(MASTER_KEY)

        first = manager.encrypt("same-value")
        second = manager.encrypt("same-value")

        assert first != second
        assert manager.decrypt(first) == manager.decrypt(second) == "same-value"

    def test_same_master_key_two_instances_interoperable(self):
        """Deux instances de même clé maîtresse déchiffrent mutuellement."""
        writer = SecretManager(MASTER_KEY)
        reader = SecretManager(MASTER_KEY)

        assert reader.decrypt(writer.encrypt("shared-secret")) == "shared-secret"


class TestWrongMasterKey:
    """AC 1 — mauvaise clé maîtresse → erreur explicite."""

    def test_decrypt_with_wrong_master_key_raises(self):
        """Déchiffrement avec une autre clé → ``SecretDecryptionError``."""
        writer = SecretManager(MASTER_KEY)
        ciphertext = writer.encrypt("confidential")

        wrong_reader = SecretManager(OTHER_MASTER_KEY)
        with pytest.raises(SecretDecryptionError) as exc_info:
            wrong_reader.decrypt(ciphertext)

        # Message explicite, sans matériel cryptographique.
        message = str(exc_info.value)
        assert "déchi" in message.lower()
        assert MASTER_KEY not in message
        assert "confidential" not in message
        assert ciphertext not in message

    def test_decrypt_error_is_windflow_exception(self):
        """L'erreur hérite de ``WindFlowException`` (règle projet)."""
        writer = SecretManager(MASTER_KEY)
        ciphertext = writer.encrypt("x")

        with pytest.raises(WindFlowException):
            SecretManager(OTHER_MASTER_KEY).decrypt(ciphertext)

    def test_decrypt_corrupted_ciphertext_raises(self):
        """Ciphertext altéré (HMAC invalide) → ``SecretDecryptionError``."""
        manager = SecretManager(MASTER_KEY)
        ciphertext = manager.encrypt("integrity-check")

        tampered = ciphertext[:-4] + "AAAA"

        with pytest.raises(SecretDecryptionError):
            manager.decrypt(tampered)

    def test_decrypt_invalid_format_raises(self):
        """Chaîne qui n'est pas un token Fernet → ``SecretDecryptionError``."""
        manager = SecretManager(MASTER_KEY)

        with pytest.raises(SecretDecryptionError):
            manager.decrypt("definitely-not-a-fernet-token")

    def test_corrupted_ciphertext_raises_clean_error(self):
        """STORY-103.4 — ciphertext corrompu → erreur propre, sans trace crypto.

        Couvre la branche générique (non-``InvalidToken``) de ``decrypt`` :
        un ciphertext au mauvais format interne (mauvais type décodé) lève
        ``SecretDecryptionError`` avec un message générique — jamais de
        stack trace cryptographique ni de matériel de clé dans l'erreur.
        """
        manager = SecretManager(MASTER_KEY)

        # Token Fernet valide en apparence (préfixe gAAAA + base64) mais
        # payload interne non décodable → SecretDecryptionError propre.
        with pytest.raises(SecretDecryptionError):
            manager.decrypt("gAAAAABmk8yJk0WmnExn8H2jYJ8Am3ld")

        # Cas 2 — donnée binaire corrompue (surrogate isolé non encodable
        # en UTF-8) : exception générique (pas InvalidToken) → aussi une
        # SecretDecryptionError propre, sans stack trace cryptographique.
        with pytest.raises(SecretDecryptionError) as exc_info:
            manager.decrypt("gAAAA\ud800corrupted")

        message = str(exc_info.value)
        # Message explicite mais générique — aucun détail cryptographique.
        assert "déchi" in message.lower()
        assert MASTER_KEY not in message
        assert "gAAAA" not in message
        # L'exception d'origine (détails internes) reste chaînée mais n'est
        # pas exposée dans le message métier.
        assert exc_info.value.__cause__ is not None


class TestCiphertextDetection:
    """Helper ``is_encrypted`` — détection pour la double lecture (103.2)."""

    def test_ciphertext_detection(self):
        """Préfixe ``gAAAA`` reconnu comme chiffré ; JSON clair non reconnu."""
        manager = SecretManager(MASTER_KEY)

        assert SecretManager.is_encrypted(manager.encrypt("value")) is True

        # Données legacy en clair : jamais détectées comme chiffrées.
        assert SecretManager.is_encrypted(CREDENTIALS_JSON) is False
        assert SecretManager.is_encrypted('{"env": "VAR=value"}') is False

    def test_detection_edge_cases(self):
        """Chaîne vide et valeurs communes ne sont pas détectées chiffrées."""
        assert SecretManager.is_encrypted("") is False
        assert SecretManager.is_encrypted("gAAA") is False  # préfixe incomplet
        assert SecretManager.is_encrypted("plaintext") is False
        assert SecretManager.is_encrypted(" gAAAA...") is False  # espace initial


class TestEmptyAndUnicodeValues:
    """Cas limites : chaîne vide, unicode, payloads longs."""

    def test_empty_and_unicode_values(self):
        """Round-trip sur chaîne vide, unicode et JSON de credentials."""
        manager = SecretManager(MASTER_KEY)

        for value in [
            "",
            "mot-de-passe-avec-accents-éàç",
            "密码パスワード 🔐",
            CREDENTIALS_JSON,
        ]:
            ciphertext = manager.encrypt(value)
            assert ciphertext != value
            assert manager.decrypt(ciphertext) == value

    def test_long_payload_round_trip(self):
        """Payload long (clé SSH privée simulée) : round-trip intact."""
        manager = SecretManager(MASTER_KEY)
        large_secret = "-----BEGIN OPENSSH PRIVATE KEY-----\n" + "A" * 4000

        assert manager.decrypt(manager.encrypt(large_secret)) == large_secret


class TestSettingsIntegration:
    """Tâche 2 — résolution de la clé maîtresse depuis les settings."""

    def test_master_encryption_key_falls_back_to_jwt(self):
        """Sans SECRET_ENCRYPTION_KEY, la clé maîtresse dérive du JWT."""
        from app.config import Settings

        config = Settings(_env_file=None)
        assert config.secret_encryption_key is None
        assert config.master_encryption_key == config.jwt_secret_key

    def test_master_encryption_key_dedicated_value(self):
        """SECRET_ENCRYPTION_KEY dédiée prime sur le JWT secret."""
        from app.config import Settings

        config = Settings(_env_file=None, secret_encryption_key="dedicated-key-123")
        assert config.master_encryption_key == "dedicated-key-123"

    def test_get_secret_manager_is_singleton(self):
        """L'instance partagée est construite une seule fois (cache)."""
        reset_secret_manager()
        try:
            first = get_secret_manager()
            second = get_secret_manager()
            assert first is second
        finally:
            reset_secret_manager()

    def test_empty_master_key_rejected(self):
        """Clé maîtresse vide → ``SecretEncryptionError`` explicite."""
        with pytest.raises(SecretEncryptionError):
            SecretManager("")
