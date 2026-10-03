"""Tests unitaires du service UserService.

- count_superadmins (STORY-122.4) : protection « dernier superadmin » ;
- hashage Argon2 / migration bcrypt (STORY-130.1) : écriture ``$argon2id$``,
  double lecture bcrypt legacy + re-hash automatique, pas de re-hash
  superflu sur hash Argon2, échec silencieux sur hash illisible.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate
from app.services.user_service import UserService

# Contexte local dédié à la génération de hashes bcrypt legacy de fixture
# (la production écrit exclusivement en Argon2id — STORY-130.1).
_BCRYPT_FIXTURE_CTX = CryptContext(schemes=["bcrypt"])


def _legacy_bcrypt_hash(password: str) -> str:
    """Génère un hash bcrypt legacy ($2b$...) pour les fixtures de migration."""
    return _BCRYPT_FIXTURE_CTX.hash(password)


def _user_with_hash(hashed_password: str) -> User:
    """Construit un User ORM minimal portant le hash donné (sans DB)."""
    user = User(
        email="hash-migration@example.com",
        username="hash-migration",
        full_name="Hash Migration",
        hashed_password=hashed_password,
        is_active=True,
    )
    # Le seed ``id`` est requis par les logs du login ; pas de DB ici.
    user.id = str(uuid4())
    return user


async def _create_superuser(
    db_session: AsyncSession, username: str, email: str
) -> None:
    """Crée un superutilisateur (is_superuser=True)."""
    await UserService.create(
        db_session,
        UserCreate(
            email=email,
            username=username,
            full_name=username.title(),
            password="password123",
            is_superuser=True,
        ),
    )


class TestCountSuperadmins:
    """``UserService.count_superadmins`` : garde du dernier superadmin (AC 3)."""

    async def test_count_superadmins_zero(self, db_session: AsyncSession):
        """Aucun superadmin en base → 0."""
        count = await UserService.count_superadmins(db_session)
        assert count == 0

    async def test_count_superadmins_one(self, db_session: AsyncSession):
        """Un seul superadmin → 1 (cas « dernier superadmin » → 409)."""
        await _create_superuser(db_session, "count-sa-one", "count-sa-one@example.com")
        count = await UserService.count_superadmins(db_session)
        assert count == 1

    async def test_count_superadmins_many(self, db_session: AsyncSession):
        """Plusieurs superadmins → N exact (démotion/suppression permis)."""
        await _create_superuser(db_session, "count-sa-a", "count-sa-a@example.com")
        await _create_superuser(db_session, "count-sa-b", "count-sa-b@example.com")
        await _create_superuser(db_session, "count-sa-c", "count-sa-c@example.com")
        # Un utilisateur standard ne compte pas
        await UserService.create(
            db_session,
            UserCreate(
                email="count-std@example.com",
                username="count-std",
                full_name="Count Std",
                password="password123",
            ),
        )
        count = await UserService.count_superadmins(db_session)
        assert count == 3


class TestArgon2Hashing:
    """Écriture et vérification Argon2id (STORY-130.1, tâche 3)."""

    def test_hash_password_produces_argon2id_prefix(self):
        """hash_password écrit des hashes préfixés $argon2id$ (AC 1)."""
        hashed = UserService.hash_password("Secret123!")
        assert hashed.startswith("$argon2id$")

    def test_verify_password_roundtrip_argon2(self):
        """Round-trip Argon2 : hash puis verify → True ; faux mot de passe → False."""
        hashed = UserService.hash_password("Secret123!")
        assert UserService.verify_password("Secret123!", hashed) is True
        assert UserService.verify_password("wrong-password", hashed) is False


class TestVerifyAndUpdate:
    """``verify_and_update`` : double lecture + re-hash (cœur AC 1)."""

    def test_bcrypt_hash_is_verified_and_upgraded_to_argon2id(self):
        """Hash bcrypt legacy → (True, nouveau hash $argon2id$) — cœur AC 1."""
        legacy = _legacy_bcrypt_hash("Secret123!")
        assert legacy.startswith("$2b$")

        verified, new_hash = UserService.verify_and_update("Secret123!", legacy)

        assert verified is True
        assert new_hash is not None
        assert new_hash.startswith("$argon2id$")

    def test_argon2_hash_is_verified_without_rehash(self):
        """Hash argon2 à jour → (True, None) : pas de re-hash superflu (arbitrage n°2)."""
        hashed = UserService.hash_password("Secret123!")

        verified, new_hash = UserService.verify_and_update("Secret123!", hashed)

        assert verified is True
        assert new_hash is None

    def test_wrong_password_returns_false_none(self):
        """Mot de passe faux → (False, None), même sur hash bcrypt legacy."""
        legacy = _legacy_bcrypt_hash("Secret123!")

        verified, new_hash = UserService.verify_and_update("wrong-password", legacy)

        assert verified is False
        assert new_hash is None

    def test_unreadable_hash_fails_silently_verify_and_update(self):
        """Hash illisible ($scrypt$...) → (False, None) sans lever (arbitrage n°9)."""
        verified, new_hash = UserService.verify_and_update(
            "Secret123!", "$scrypt$N=16384,r=8,p=1$deadbeef$deadbeef"
        )

        assert verified is False
        assert new_hash is None

    def test_unreadable_hash_fails_silently_verify_password(self):
        """Hash illisible → False sans lever (arbitrage n°9 — jamais de 500 au login)."""
        result = UserService.verify_password(
            "Secret123!", "$scrypt$N=16384,r=8,p=1$deadbeef$deadbeef"
        )

        assert result is False


class TestVerifyAndUpdateUser:
    """``verify_and_update_user`` : persistance du re-hash (session mockée)."""

    async def test_bcrypt_hash_triggers_update_and_commit(self):
        """Hash bcrypt → hashed_password mis à jour en Argon2id + commit appelé."""
        db = AsyncMock()
        user = _user_with_hash(_legacy_bcrypt_hash("Secret123!"))

        is_valid = await UserService.verify_and_update_user(db, user, "Secret123!")

        assert is_valid is True
        assert user.hashed_password.startswith("$argon2id$")
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(user)

    async def test_argon2_hash_does_not_commit(self):
        """Hash argon2 à jour → valide mais AUCUN commit superflu (arbitrage n°2)."""
        db = AsyncMock()
        user = _user_with_hash(UserService.hash_password("Secret123!"))
        hash_before = user.hashed_password

        is_valid = await UserService.verify_and_update_user(db, user, "Secret123!")

        assert is_valid is True
        assert user.hashed_password == hash_before
        db.commit.assert_not_awaited()

    async def test_wrong_password_does_not_commit(self):
        """Mot de passe faux → False, aucun commit ni modification du hash."""
        db = AsyncMock()
        user = _user_with_hash(_legacy_bcrypt_hash("Secret123!"))
        hash_before = user.hashed_password

        is_valid = await UserService.verify_and_update_user(db, user, "wrong-password")

        assert is_valid is False
        assert user.hashed_password == hash_before
        db.commit.assert_not_awaited()
