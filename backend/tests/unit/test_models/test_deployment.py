"""Tests unitaires du modèle Deployment — snapshots chiffrés (STORY-103.3).

Vérifie :
- le chiffrement au repos des valeurs sensibles des snapshots ``variables``
  et ``config`` (préfixe ``gAAAA``, clés conservées) ;
- la migration par double lecture : snapshot legacy en clair → accès →
  ré-encryptage au premier accès (persisté par le commit de l'appelant) ;
- l'idempotence (un ciphertext n'est jamais re-chiffré) ;
- le passage des valeurs non sensibles et non-chaînes ;
- l'erreur explicite en cas de ciphertext corrompu.
"""

from __future__ import annotations

import pytest

from app.core.secret_manager import SecretManager, reset_secret_manager
from app.models.deployment import (
    Deployment,
    DeploymentStatus,
    decrypt_variables_from_storage,
    encrypt_variables_for_storage,
    is_sensitive_variable,
)

# Snapshot réaliste : mélange de variables sensibles et non sensibles.
CLEAR_VARIABLES: dict = {
    "db_password": "S3cr3t!Pass",
    "api_token": "tok_abc123",
    "domain": "app.example.com",
    "port": 8080,
    "debug": False,
    "empty_secret": "",
    "generated_password": "xK9$mP2#nL7",
}


@pytest.fixture(autouse=True)
def _fresh_secret_manager():
    """Instance SecretManager isolée par test (clé déterministe)."""
    reset_secret_manager()
    yield
    reset_secret_manager()


def _make_deployment(variables: dict) -> Deployment:
    """Construit un Deployment non persisté avec le snapshot donné."""
    return Deployment(
        stack_id="stack-1",
        target_id="target-1",
        organization_id="org-1",
        name="test-deployment",
        config={},
        variables=variables,
        status=DeploymentStatus.PENDING,
    )


class TestSensitiveDetection:
    """Heuristique de sensibilité par nom de variable."""

    def test_sensitive_names_detected(self):
        """Les noms PASSWORD/SECRET/TOKEN/API_KEY... sont sensibles."""
        for name in (
            "db_password",
            "POSTGRES_PASSWORD",
            "api_token",
            "JWT_SECRET",
            "PRIVATE_KEY",
            "access_key",
            "auth_key",
            "credentials",
        ):
            assert is_sensitive_variable(name) is True, name

    def test_non_sensitive_names_pass(self):
        """Les noms neutres ne sont pas marqués sensibles."""
        for name in ("domain", "port", "debug", "app_mode", "timezone"):
            assert is_sensitive_variable(name) is False, name


class TestEncryptForStorage:
    """Tâche 1 — chiffrement des valeurs sensibles pour stockage."""

    def test_sensitive_values_encrypted_at_rest(self):
        """Les valeurs sensibles deviennent des tokens Fernet (gAAAA)."""
        stored = encrypt_variables_for_storage(CLEAR_VARIABLES)

        assert SecretManager.is_encrypted(stored["db_password"])
        assert SecretManager.is_encrypted(stored["api_token"])
        assert SecretManager.is_encrypted(stored["generated_password"])
        # Aucune valeur sensible en clair dans le snapshot stocké.
        assert "S3cr3t!Pass" not in str(stored.values())
        assert "tok_abc123" not in str(stored.values())

    def test_keys_preserved_and_non_sensitive_clear(self):
        """Clés conservées ; valeurs non sensibles restent lisibles (UI)."""
        stored = encrypt_variables_for_storage(CLEAR_VARIABLES)

        assert set(stored.keys()) == set(CLEAR_VARIABLES.keys())
        assert stored["domain"] == "app.example.com"
        assert stored["port"] == 8080
        assert stored["debug"] is False

    def test_empty_values_left_as_is(self):
        """Les valeurs vides ne sont pas chiffrées (exclusions, 103.2)."""
        stored = encrypt_variables_for_storage({"db_password": ""})

        assert stored["db_password"] == ""

    def test_non_string_values_not_encrypted(self):
        """Les valeurs non-chaînes (int/bool/dict) passent telles quelles."""
        stored = encrypt_variables_for_storage(
            {"password": 12345, "replicas": 3, "limits": {"cpu": 1}}
        )

        assert stored["password"] == 12345
        assert stored["replicas"] == 3
        assert stored["limits"] == {"cpu": 1}

    def test_idempotent_already_encrypted_value(self):
        """Un ciphertext existant n'est jamais re-chiffré."""
        manager = SecretManager(master_key="test-key-103-3")
        token = manager.encrypt("already-encrypted")
        stored = encrypt_variables_for_storage({"db_password": token})

        assert stored["db_password"] == token

    def test_round_trip_decrypt(self):
        """Round-trip : chiffrement → déchiffrement → snapshot identique."""
        stored = encrypt_variables_for_storage(CLEAR_VARIABLES)

        assert decrypt_variables_from_storage(stored) == CLEAR_VARIABLES

    def test_decrypt_legacy_clear_snapshot_untouched(self):
        """Double lecture : snapshot legacy en clair lu tel quel."""
        assert decrypt_variables_from_storage(CLEAR_VARIABLES) == CLEAR_VARIABLES

    def test_decrypt_corrupted_token_raises(self):
        """Ciphertext altéré → SecretDecryptionError explicite."""
        from app.core.exceptions import SecretDecryptionError

        stored = encrypt_variables_for_storage({"db_password": "valeur"})
        tampered = dict(stored)
        tampered["db_password"] = stored["db_password"][:-4] + "AAAA"

        with pytest.raises(SecretDecryptionError):
            decrypt_variables_from_storage(tampered)


class TestSnapshotEncryptedAtRest:
    """AC 3 — après création, la colonne ne contient pas de clair."""

    async def test_snapshot_variables_encrypted_at_rest(
        self, db_session, test_organization
    ):
        """Après commit, les valeurs sensibles de la colonne sont en gAAAA."""
        deployment = _make_deployment(dict(CLEAR_VARIABLES))
        deployment.variables = encrypt_variables_for_storage(CLEAR_VARIABLES)
        db_session.add(deployment)
        await db_session.commit()
        await db_session.refresh(deployment)

        stored = deployment.variables
        assert SecretManager.is_encrypted(stored["db_password"])
        assert SecretManager.is_encrypted(stored["api_token"])
        assert stored["domain"] == "app.example.com"
        # Le clair n'apparaît nulle part dans la colonne.
        assert "S3cr3t!Pass" not in str(stored)

    async def test_snapshot_config_encrypted_at_rest(
        self, db_session, test_organization
    ):
        """Le snapshot config suit le même traitement que variables."""
        deployment = _make_deployment({})
        deployment.config = encrypt_variables_for_storage(
            {"POSTGRES_PASSWORD": "pg-pass-123", "port": 5432}
        )
        db_session.add(deployment)
        await db_session.commit()
        await db_session.refresh(deployment)

        assert SecretManager.is_encrypted(deployment.config["POSTGRES_PASSWORD"])
        assert deployment.config["port"] == 5432


class TestDoubleReadingMigration:
    """AC 3 — migration des snapshots legacy par double lecture."""

    async def test_double_reading_deployments(self, db_session, test_organization):
        """Snapshot ancien en clair → accès → relecture : chiffré en base."""
        deployment = _make_deployment(dict(CLEAR_VARIABLES))
        db_session.add(deployment)
        await db_session.commit()

        # Premier accès → lecture en clair + ré-encryptage (dirty).
        read = deployment.decrypted_variables
        assert read == CLEAR_VARIABLES
        assert SecretManager.is_encrypted(deployment.variables["db_password"])

        # Persistance de la migration par le commit de l'appelant.
        await db_session.commit()
        await db_session.refresh(deployment)
        assert SecretManager.is_encrypted(deployment.variables["db_password"])

        # Relecture après persistance : toujours déchiffrable, idempotent.
        assert deployment.decrypted_variables == CLEAR_VARIABLES

    async def test_decrypted_config_double_reading(self, db_session):
        """Même comportement pour la propriété decrypted_config."""
        deployment = _make_deployment({})
        deployment.config = {"api_key": "sk-live-123", "retries": 3}
        db_session.add(deployment)
        await db_session.commit()

        read = deployment.decrypted_config
        assert read == {"api_key": "sk-live-123", "retries": 3}
        assert SecretManager.is_encrypted(deployment.config["api_key"])
        assert deployment.config["retries"] == 3

    async def test_encrypted_snapshot_not_re_encrypted(self, db_session):
        """Idempotence : accès répétés → même ciphertext, pas de double chiffrement."""
        deployment = _make_deployment(encrypt_variables_for_storage(CLEAR_VARIABLES))
        db_session.add(deployment)
        await db_session.commit()

        first_token = deployment.variables["db_password"]
        assert deployment.decrypted_variables == CLEAR_VARIABLES
        assert deployment.decrypted_variables == CLEAR_VARIABLES
        assert deployment.variables["db_password"] == first_token

    async def test_empty_snapshot_returns_empty(self, db_session):
        """Snapshot vide → dict vide, aucune erreur."""
        deployment = _make_deployment({})
        db_session.add(deployment)
        await db_session.commit()

        assert deployment.decrypted_variables == {}
        assert deployment.variables == {}
