"""Tests unitaires des helpers de chiffrement ``config_values`` (STORY-169.4).

Vérifie la stratégie « clé conservée, valeur chiffrée » appliquée à la
colonne ``plugins.config_values`` (C12) :

- la détection des clés sensibles depuis le manifest (``type=password``) ;
- le chiffrement à l'écriture : seules les valeurs password deviennent des
  tokens Fernet (préfixe ``gAAAA``), idempotent, non-str inchangé ;
- le déchiffrement en double lecture : legacy clair conservé tel quel,
  round-trip complet, passthrough des valeurs non chiffrées.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import SecretDecryptionError
from app.core.secret_manager import SecretManager, reset_secret_manager
from app.models.plugin import (
    decrypt_config_values_from_storage,
    encrypt_config_values_for_storage,
    sensitive_config_keys,
)

# Manifest avec un champ password + champs non sensibles (string/boolean).
_MANIFEST_WITH_PASSWORD: dict = {
    "name": "redis-service",
    "version": "1.0.0",
    "type": "service",
    "config": [
        {"key": "api_key", "type": "password", "label": "API key"},
        {"key": "host", "type": "string", "label": "Host"},
        {"key": "tls_enabled", "type": "boolean", "label": "TLS"},
    ],
}


@pytest.fixture(autouse=True)
def _fresh_secret_manager():
    """Instance SecretManager isolée par test (clé déterministe)."""
    reset_secret_manager()
    yield
    reset_secret_manager()


class TestSensitiveConfigKeys:
    """T1 — détection des clés sensibles depuis le manifest."""

    def test_sensitive_config_keys_extracts_password_fields_only(self):
        """Cas nominal : seule la clé ``type=password`` est sensitive."""
        keys = sensitive_config_keys(_MANIFEST_WITH_PASSWORD)

        assert keys == {"api_key"}

    def test_sensitive_config_keys_empty_manifest(self):
        """Cas limite : manifest sans section config → ensemble vide."""
        assert sensitive_config_keys({}) == set()
        assert sensitive_config_keys({"config": []}) == set()


class TestEncryptConfigValuesForStorage:
    """T1 — chiffrement à l'écriture (clé conservée, valeur chiffrée)."""

    def test_encrypt_encrypts_only_password_values(self):
        """Cas nominal : password → token ``gAAAA``, les autres lisibles."""
        stored = encrypt_config_values_for_storage(
            _MANIFEST_WITH_PASSWORD, {"api_key": "s3cret", "host": "localhost"}
        )

        assert isinstance(stored["api_key"], str)
        assert stored["api_key"].startswith("gAAAA")
        assert stored["api_key"] != "s3cret"
        assert stored["host"] == "localhost"

    def test_encrypt_is_idempotent_on_existing_tokens(self):
        """Idempotence : un token déjà chiffré est conservé tel quel."""
        first_pass = encrypt_config_values_for_storage(
            _MANIFEST_WITH_PASSWORD, {"api_key": "s3cret"}
        )
        token = first_pass["api_key"]

        second_pass = encrypt_config_values_for_storage(
            _MANIFEST_WITH_PASSWORD, first_pass
        )

        assert second_pass["api_key"] == token

    def test_encrypt_skips_non_string_values(self):
        """Cas limite : int/bool/None sur clé password → inchangés."""
        stored = encrypt_config_values_for_storage(
            _MANIFEST_WITH_PASSWORD,
            {"api_key": 12345, "tls_enabled": True, "other": None},
        )

        assert stored["api_key"] == 12345
        assert stored["tls_enabled"] is True
        assert stored["other"] is None


class TestDecryptConfigValuesFromStorage:
    """T1 — déchiffrement en double lecture."""

    def test_decrypt_roundtrip_restores_plaintext(self):
        """Round-trip : encrypt → decrypt = valeur d'origine."""
        stored = encrypt_config_values_for_storage(
            _MANIFEST_WITH_PASSWORD, {"api_key": "s3cret", "host": "localhost"}
        )

        decrypted = decrypt_config_values_from_storage(stored)

        assert decrypted["api_key"] == "s3cret"
        assert decrypted["host"] == "localhost"

    def test_decrypt_double_read_legacy_plaintext(self):
        """Double lecture : dict legacy tout clair → relu tel quel."""
        legacy = {"api_key": "legacy-in-clear", "host": "localhost"}

        assert decrypt_config_values_from_storage(legacy) == legacy

    def test_decrypt_passthrough_non_encrypted_and_non_str(self):
        """Passthrough : valeurs claires str et non-str conservées."""
        stored = {"host": "localhost", "port": 6379, "enabled": False, "n": None}

        result = decrypt_config_values_from_storage(stored)

        assert result == stored
        assert not any(
            SecretManager.is_encrypted(v) for v in stored.values() if isinstance(v, str)
        )

    def test_decrypt_corrupted_token_raises(self):
        """Cas d'erreur : ciphertext altéré → SecretDecryptionError."""
        stored = encrypt_config_values_for_storage(
            _MANIFEST_WITH_PASSWORD, {"api_key": "s3cret"}
        )
        tampered = dict(stored)
        tampered["api_key"] = stored["api_key"][:-4] + "AAAA"

        with pytest.raises(SecretDecryptionError):
            decrypt_config_values_from_storage(tampered)
