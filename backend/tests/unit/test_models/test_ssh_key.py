"""Tests unitaires du modèle SSHKey (STORY-131.1).

Vérifie :
- le round-trip chiffrement : ``private_key_encrypted`` contient
  exclusivement un token Fernet (préfixe ``gAAAA``), jamais le PEM ;
- :attr:`SSHKey.decrypted_private_key` restitue la clé privée d'origine ;
- l'unicité de ``name`` (IntegrityError sur doublon) ;
- la sécurité : ``__repr__`` sans matériau de clé (privée/publique) ;
- l'index ``idx_ssh_keys_fingerprint`` (metadata — la présence réelle en
  base après migration est vérifiée par ``test_migrations_131.py``) ;
- la relation navigable ``SSHKey.targets`` (N cibles ↔ 1 clé, AC 2 mère).
"""

from __future__ import annotations

import asyncssh
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.secret_manager import (
    SecretManager,
    get_secret_manager,
    reset_secret_manager,
)
from app.models.ssh_key import SSHKey
from app.models.target import Target

# Clé de test générée une fois (ed25519 — rapide) ; valeurs factices.
_TEST_KEY = asyncssh.generate_private_key("ssh-ed25519")
TEST_PEM: str = _TEST_KEY.export_private_key().decode()
TEST_PUBLIC_KEY: str = _TEST_KEY.export_public_key().decode()
TEST_FINGERPRINT: str = _TEST_KEY.get_fingerprint()


@pytest.fixture(autouse=True)
def _fresh_secret_manager():
    """Instance SecretManager isolée par test (clé des settings de test)."""
    reset_secret_manager()
    yield
    reset_secret_manager()


def _make_key(name: str = "deploy-key") -> SSHKey:
    """Construit une SSHKey valide (clé privée chiffrée via SecretManager)."""
    return SSHKey(
        name=name,
        public_key=TEST_PUBLIC_KEY,
        private_key_encrypted=get_secret_manager().encrypt(TEST_PEM),
        fingerprint=TEST_FINGERPRINT,
    )


class TestEncryptedAtRest:
    """Round-trip chiffrement — jamais de clé privée en clair en colonne."""

    async def test_stored_value_is_fernet_token(self, db_session) -> None:
        """La colonne contient un token Fernet (gAAAA), pas un PEM."""
        key = _make_key()
        db_session.add(key)
        await db_session.flush()
        await db_session.refresh(key)

        stored = key.private_key_encrypted
        assert SecretManager.is_encrypted(stored), "doit être un token Fernet"
        assert stored.startswith("gAAAA")
        # Aucun fragment PEM en clair dans la valeur stockée.
        assert TEST_PEM not in stored
        assert "BEGIN" not in stored
        assert "PRIVATE KEY" not in stored

    async def test_decrypted_private_key_round_trip(self, db_session) -> None:
        """decrypted_private_key restitue exactement le PEM d'origine."""
        key = _make_key()
        db_session.add(key)
        await db_session.flush()

        assert key.decrypted_private_key == TEST_PEM

    async def test_decrypted_private_key_reimportable(self, db_session) -> None:
        """La clé déchiffrée est un PEM valide (ré-import asyncssh OK)."""
        key = _make_key()
        db_session.add(key)
        await db_session.flush()

        reimported = asyncssh.import_private_key(key.decrypted_private_key)
        assert reimported.get_fingerprint() == TEST_FINGERPRINT


class TestNameUniqueness:
    """Unicité ``name`` (spec 06 — nom d'affichage unique)."""

    async def test_duplicate_name_raises_integrity_error(self, db_session) -> None:
        """Deux clés de même nom → IntegrityError au flush."""
        db_session.add(_make_key(name="prod-key"))
        await db_session.flush()

        db_session.add(_make_key(name="prod-key"))
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_same_fingerprint_different_names_allowed(self, db_session) -> None:
        """La contrainte porte sur ``name`` uniquement : même empreinte,
        noms différents → accepté (l'unicité d'empreinte relève du service
        de déduplication, STORY-131.2)."""
        db_session.add(_make_key(name="key-a"))
        db_session.add(_make_key(name="key-b"))
        await db_session.flush()

        keys = (await db_session.execute(select(SSHKey))).scalars().all()
        assert len(keys) == 2


class TestDefaults:
    """Défauts du modèle (spec 06)."""

    async def test_key_type_defaults_to_ed25519(self, db_session) -> None:
        """key_type défaut ``ssh-ed25519`` (recommandé spec 06)."""
        key = _make_key()
        db_session.add(key)
        await db_session.flush()

        assert key.key_type == "ssh-ed25519"

    async def test_defaults_last_used_at_none(self, db_session) -> None:
        """last_used_at NULL à la création (jamais utilisée)."""
        key = _make_key()
        db_session.add(key)
        await db_session.flush()

        assert key.last_used_at is None
        assert key.created_at is not None
        assert len(key.id) == 36, "id doit être un UUID String(36)"


class TestReprSecurity:
    """Sécurité : __repr__ sans matériau de clé (privée ET publique)."""

    def test_repr_does_not_expose_key_material(self) -> None:
        """__repr__ ne contient ni clé privée ni clé publique."""
        key = _make_key()
        representation = repr(key)

        assert TEST_PEM not in representation
        assert TEST_PUBLIC_KEY not in representation
        assert "private_key" not in representation
        assert "public_key" not in representation
        assert "name=deploy-key" in representation
        assert f"fingerprint={TEST_FINGERPRINT}" in representation

    def test_tablename(self) -> None:
        """__tablename__ == 'ssh_keys' (convention spec 06)."""
        assert SSHKey.__tablename__ == "ssh_keys"


class TestStructure:
    """Structure : colonnes spec 06 + index fingerprint (metadata)."""

    def test_expected_columns(self) -> None:
        """Exactement les colonnes de la spec 06 § SSHKey."""
        assert set(SSHKey.__table__.columns.keys()) == {
            "id",
            "name",
            "key_type",
            "public_key",
            "private_key_encrypted",
            "fingerprint",
            "last_used_at",
            "created_at",
        }

    def test_fingerprint_index_in_metadata(self) -> None:
        """Index idx_ssh_keys_fingerprint(fingerprint) présent (spec 06)."""
        indexes = {
            idx.name: [c.name for c in idx.columns] for idx in SSHKey.__table__.indexes
        }
        assert "idx_ssh_keys_fingerprint" in indexes
        assert indexes["idx_ssh_keys_fingerprint"] == ["fingerprint"]

    def test_name_bounded_100_chars(self) -> None:
        """Bornage spec 06 : name String(100), fingerprint String(100)."""
        assert SSHKey.__table__.columns["name"].type.length == 100
        assert SSHKey.__table__.columns["fingerprint"].type.length == 100
        assert not SSHKey.__table__.columns["name"].nullable


class TestTargetsRelationship:
    """Relation N cibles ↔ 1 clé (AC 2 de la story mère)."""

    async def test_n_targets_share_one_key(self, db_session, test_organization) -> None:
        """Deux cibles référencent la même clé → SSHKey.targets navigable."""
        key = _make_key()
        db_session.add(key)
        await db_session.flush()

        for name in ("target-a", "target-b"):
            db_session.add(
                Target(
                    name=name,
                    host=f"192.0.2.{10 + len(name)}",
                    credentials={},
                    organization_id=test_organization.id,
                    ssh_key_id=key.id,
                )
            )
        await db_session.flush()

        loaded = (
            await db_session.execute(
                select(SSHKey).options(selectinload(SSHKey.targets))
            )
        ).scalar_one()
        assert {t.name for t in loaded.targets} == {"target-a", "target-b"}
