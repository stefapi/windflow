"""Tests unitaires de TargetService — chiffrement des credentials (STORY-103.2).

Vérifie :
- ``create()`` stocke la colonne chiffrée (aucune valeur en clair en base) ;
- ``update()`` fusionne sur les credentials déchiffrés puis ré-encrypte ;
- la relecture après écriture redonne les credentials attendus (flux
  identiques pour l'utilisateur — non-régression) ;
- les credentials vides restent fonctionnels (fixtures existantes).
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.core.secret_manager import SecretManager, reset_secret_manager
from app.enums.target import SSHAuthMethod
from app.models.target import Target
from app.schemas.target import (
    SSHCredentials,
    SSHCredentialsUpdate,
    TargetCreate,
    TargetUpdate,
)
from app.services.target_service import TargetService


def _is_encrypted_storage(stored: dict) -> bool:
    """Vrai si le dict stocké est le format opaque chiffré (token Fernet)."""
    token = stored.get("_encrypted")
    return isinstance(token, str) and SecretManager.is_encrypted(token)


def _make_create_payload(org_id: str, password: str = "S3cr3t!Pass") -> TargetCreate:
    return TargetCreate(
        name="svc-target",
        host="192.0.2.20",
        port=22,
        credentials=SSHCredentials(
            auth_method=SSHAuthMethod.PASSWORD,
            username="deploy",
            password=password,
        ),
        organization_id=org_id,
    )


@pytest.fixture(autouse=True)
def _fresh_secret_manager():
    """Instance SecretManager isolée par test."""
    reset_secret_manager()
    yield
    reset_secret_manager()


class TestCreateStoresEncrypted:
    """test_create_stores_encrypted_credentials — AC 2 (écriture)."""

    async def test_create_stores_encrypted_credentials(
        self, db_session, test_organization
    ):
        """Après create(), la colonne ne contient aucune valeur en clair."""
        target = await TargetService.create(
            db_session, _make_create_payload(test_organization.id)
        )

        stored = target.credentials
        assert _is_encrypted_storage(stored)
        assert "S3cr3t!Pass" not in json.dumps(stored)
        assert "deploy" not in json.dumps(stored)

        # Relecture déchiffrée : flux identiques pour l'utilisateur.
        assert target.decrypted_credentials["username"] == "deploy"
        assert target.decrypted_credentials["password"] == "S3cr3t!Pass"

        # Persistance réelle : la ligne en base est bien chiffrée.
        await db_session.refresh(target)
        row = (
            await db_session.execute(select(Target).where(Target.id == target.id))
        ).scalar_one()
        assert _is_encrypted_storage(row.credentials)


class TestUpdateMergeReencrypts:
    """test_update_merge_reencrypts — AC 2 (mise à jour partielle)."""

    async def test_update_merge_reencrypts(self, db_session, test_organization):
        """Update partiel → fusion correcte sur clair, colonne ré-encryptée."""
        target = await TargetService.create(
            db_session, _make_create_payload(test_organization.id)
        )

        await TargetService.update(
            db_session,
            target.id,
            TargetUpdate(
                credentials=SSHCredentialsUpdate(
                    username="newuser",
                    sudo_enabled=True,
                    sudo_user="root",
                )
            ),
        )
        await db_session.refresh(target)

        # Colonne chiffrée, aucune trace des valeurs en clair.
        assert _is_encrypted_storage(target.credentials)
        assert "newuser" not in json.dumps(target.credentials)

        # Fusion : username remplacé, password initial conservé, sudo ajouté.
        creds = target.decrypted_credentials
        assert creds["username"] == "newuser"
        assert creds["password"] == "S3cr3t!Pass"
        assert creds["sudo_enabled"] is True
        assert creds["sudo_user"] == "root"

    async def test_update_legacy_clear_row_merges_and_encrypts(
        self, db_session, test_organization
    ):
        """Update d'une ligne legacy claire → fusion puis chiffrement."""
        legacy = Target(
            name="legacy-svc",
            host="192.0.2.21",
            credentials={
                "auth_method": "password",
                "username": "olduser",
                "password": "OldPass123",
                "sudo_enabled": False,
            },
            organization_id=test_organization.id,
        )
        db_session.add(legacy)
        await db_session.commit()

        await TargetService.update(
            db_session,
            legacy.id,
            TargetUpdate(credentials=SSHCredentialsUpdate(password="NewPass456")),
        )
        await db_session.refresh(legacy)

        assert _is_encrypted_storage(legacy.credentials)
        creds = legacy.decrypted_credentials
        assert creds["username"] == "olduser"  # conservé par la fusion
        assert creds["password"] == "NewPass456"

    async def test_update_without_credentials_keeps_encryption(
        self, db_session, test_organization
    ):
        """Update sans credentials → colonne chiffrée inchangée."""
        target = await TargetService.create(
            db_session, _make_create_payload(test_organization.id)
        )
        token_before = target.credentials["_encrypted"]

        await TargetService.update(
            db_session, target.id, TargetUpdate(name="renamed-target")
        )
        await db_session.refresh(target)

        assert target.name == "renamed-target"
        assert _is_encrypted_storage(target.credentials)
        # Même token : pas de re-chiffrement inutile.
        assert target.credentials["_encrypted"] == token_before


class TestEmptyCredentials:
    """Non-régression : credentials minimaux (LOCAL) restent fonctionnels."""

    async def test_create_local_empty_credentials_roundtrip(
        self, db_session, test_organization
    ):
        """Création LOCAL sans username/password → déchiffrable, has_sudo False."""
        payload = TargetCreate(
            name="local-target",
            host="localhost",
            credentials=SSHCredentials(auth_method=SSHAuthMethod.LOCAL),
            organization_id=test_organization.id,
        )
        target = await TargetService.create(db_session, payload)

        assert _is_encrypted_storage(target.credentials)
        creds = target.decrypted_credentials
        assert creds["auth_method"] == "local"
        assert creds["sudo_enabled"] is False
        assert target.has_sudo is False
