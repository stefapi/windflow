"""Tests unitaires du modèle Target — credentials chiffrés (STORY-103.2).

Vérifie :
- la migration par double lecture : ligne claire → accès → ré-encryptage ;
- les propriétés dérivées (auth_method/username/has_sudo) sur données
  chiffrées et sur données legacy en clair ;
- le round-trip des credentials vides (non-régression fixtures) ;
- la détection de ciphertext et le refus de double chiffrement ;
- l'erreur explicite en cas de donnée corrompue (mauvaise clé).
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.core.secret_manager import SecretManager, reset_secret_manager
from app.models.target import (
    Target,
    decrypt_credentials_from_storage,
    encrypt_credentials_for_storage,
)

# Credentials réalistes (valeurs factices, jamais utilisées ailleurs).
CLEAR_CREDENTIALS: dict = {
    "auth_method": "password",
    "username": "deploy",
    "password": "S3cr3t!Pass",
    "sudo_enabled": True,
    "sudo_user": "root",
    "sudo_password": "sudo-pass-123",
}


@pytest.fixture(autouse=True)
def _fresh_secret_manager():
    """Instance SecretManager isolée par test (clé déterministe)."""
    reset_secret_manager()
    yield
    reset_secret_manager()


def _is_encrypted_storage(stored: dict) -> bool:
    """Vrai si le dict stocké est le format opaque chiffré (token Fernet)."""
    token = stored.get("_encrypted")
    return isinstance(token, str) and SecretManager.is_encrypted(token)


class TestEncryptForStorage:
    """Tâche 1 — helpers de chiffrement pour stockage."""

    def test_encrypt_returns_opaque_dict(self):
        """Le stockage est opaque : une seule clé ``_encrypted``, token Fernet."""
        stored = encrypt_credentials_for_storage(CLEAR_CREDENTIALS)

        assert set(stored.keys()) == {"_encrypted"}
        assert _is_encrypted_storage(stored)
        # Aucune valeur en clair ne fuite dans la colonne.
        assert json.dumps(CLEAR_CREDENTIALS) not in json.dumps(stored)
        assert "S3cr3t!Pass" not in stored["_encrypted"]

    def test_encrypt_then_decrypt_round_trip(self):
        """Round-trip : déchiffrement → dict identique."""
        stored = encrypt_credentials_for_storage(CLEAR_CREDENTIALS)

        assert decrypt_credentials_from_storage(stored) == CLEAR_CREDENTIALS

    def test_encrypt_empty_dict_round_trip(self):
        """Le dict vide reste un cas valide (fixtures ``credentials={}``)."""
        stored = encrypt_credentials_for_storage({})

        assert _is_encrypted_storage(stored)
        assert decrypt_credentials_from_storage(stored) == {}

    def test_decrypt_legacy_clear_dict_returned_as_is(self):
        """Double lecture : un dict legacy en clair est retourné tel quel."""
        assert decrypt_credentials_from_storage(CLEAR_CREDENTIALS) == CLEAR_CREDENTIALS

    def test_decrypt_corrupted_token_raises(self):
        """Ciphertext altéré → SecretDecryptionError explicite."""
        from app.core.exceptions import SecretDecryptionError

        stored = encrypt_credentials_for_storage(CLEAR_CREDENTIALS)
        tampered = {"_encrypted": stored["_encrypted"][:-4] + "AAAA"}

        with pytest.raises(SecretDecryptionError):
            decrypt_credentials_from_storage(tampered)


class TestDoubleReadingMigration:
    """AC 4 — migration des lignes legacy par double lecture."""

    async def test_double_reading_migrates_clear_row(
        self, db_session, test_organization
    ):
        """Ligne claire → accès → relecture : la ligne est chiffrée (gAAAA)."""
        target = Target(
            name="legacy-target",
            host="192.0.2.10",
            credentials=dict(CLEAR_CREDENTIALS),  # simule une ligne legacy
            organization_id=test_organization.id,
        )
        db_session.add(target)
        await db_session.commit()

        # Premier accès → lecture en clair + ré-encryptage (dirty).
        read = target.decrypted_credentials
        assert read == CLEAR_CREDENTIALS
        assert _is_encrypted_storage(target.credentials)

        # Persistance de la migration par le commit de l'appelant.
        await db_session.commit()
        await db_session.refresh(target)
        assert _is_encrypted_storage(target.credentials)

        # Relecture après persistance : toujours déchiffrable, idempotent.
        assert target.decrypted_credentials == CLEAR_CREDENTIALS

    async def test_encrypted_row_is_not_re_encrypted(
        self, db_session, test_organization
    ):
        """Idempotence : un ciphertext n'est jamais re-chiffré à la lecture."""
        target = Target(
            name="already-encrypted",
            host="192.0.2.11",
            credentials=encrypt_credentials_for_storage(CLEAR_CREDENTIALS),
            organization_id=test_organization.id,
        )
        db_session.add(target)
        await db_session.commit()

        first_token = target.credentials["_encrypted"]
        assert target.decrypted_credentials == CLEAR_CREDENTIALS

        # Pas de double chiffrement : même token, toujours lisible.
        assert target.credentials["_encrypted"] == first_token
        assert target.decrypted_credentials == CLEAR_CREDENTIALS

    async def test_empty_credentials_left_as_is(self, db_session, test_organization):
        """Credentials vides (``{}``) : pas de migration inutile."""
        target = Target(
            name="empty-creds",
            host="192.0.2.12",
            credentials={},
            organization_id=test_organization.id,
        )
        db_session.add(target)
        await db_session.commit()

        assert target.decrypted_credentials == {}
        assert target.credentials == {}  # inchangé côté fixtures conftest


class TestDerivedProperties:
    """AC 2 — propriétés dérivées fonctionnent sur données chiffrées."""

    async def test_derived_properties_still_work_encrypted(
        self, db_session, test_organization
    ):
        """auth_method/username/has_sudo corrects sur credentials chiffrés."""
        target = Target(
            name="derived-props",
            host="192.0.2.13",
            credentials=encrypt_credentials_for_storage(CLEAR_CREDENTIALS),
            organization_id=test_organization.id,
        )
        db_session.add(target)
        await db_session.commit()

        assert target.auth_method == "password"
        assert target.username == "deploy"
        assert target.has_sudo is True

    def test_derived_properties_on_legacy_clear_row(self, test_organization):
        """Les propriétés fonctionnent aussi sur une ligne legacy en clair."""
        target = Target(
            name="legacy-props",
            host="192.0.2.14",
            credentials=dict(CLEAR_CREDENTIALS),
            organization_id=test_organization.id,
        )

        assert target.auth_method == "password"
        assert target.username == "deploy"
        assert target.has_sudo is True

    def test_derived_properties_on_empty_credentials(self):
        """Credentials vides → valeurs neutres, pas d'erreur."""
        target = Target(
            name="empty",
            host="192.0.2.15",
            credentials={},
            organization_id="org-1",
        )

        assert target.auth_method is None
        assert target.username is None
        assert target.has_sudo is False

    async def test_empty_credentials_roundtrip_via_full_db(
        self, db_session, test_organization
    ):
        """Non-régression fixture conftest : ``credentials={}`` persisté tel quel."""
        target = Target(
            name="Test Docker Target",
            host="localhost",
            port=2375,
            credentials={},
            organization_id=test_organization.id,
        )
        db_session.add(target)
        await db_session.commit()
        await db_session.refresh(target)

        assert target.decrypted_credentials == {}

        row = (
            await db_session.execute(
                select(Target).where(Target.name == "Test Docker Target")
            )
        ).scalar_one()
        assert row.credentials == {}


class TestWrongKeyBehaviour:
    """Sécurité — donnée chiffrée avec une autre clé : erreur explicite."""

    def test_encrypted_with_other_key_raises_on_access(self):
        """Accès à une ligne chiffrée avec la clé courante différente → erreur."""
        from app.core.exceptions import SecretDecryptionError
        from app.core.secret_manager import SecretManager as SM

        other = SM("another-master-key-zzz")
        stored = {"_encrypted": other.encrypt(json.dumps(CLEAR_CREDENTIALS))}

        target = Target(
            name="foreign-key",
            host="192.0.2.16",
            credentials=stored,
            organization_id="org-1",
        )

        with pytest.raises(SecretDecryptionError):
            _ = target.decrypted_credentials
