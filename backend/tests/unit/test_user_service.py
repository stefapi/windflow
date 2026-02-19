"""Tests unitaires pour UserService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService
from app.schemas.user import UserCreate, UserUpdate
from app.models.user import User
from app.models.organization import Organization


@pytest.mark.asyncio
class TestUserService:
    """Tests pour le service utilisateur."""

    async def test_hash_password(self):
        """Test du hashing de mot de passe."""
        password = "testpassword123"
        hashed = UserService.hash_password(password)

        assert hashed != password
        assert len(hashed) > 0
        assert UserService.verify_password(password, hashed)

    async def test_verify_password_invalid(self):
        """Test de vérification avec mot de passe incorrect."""
        password = "testpassword123"
        hashed = UserService.hash_password(password)

        assert not UserService.verify_password("wrongpassword", hashed)

    async def test_hash_password_long(self):
        """Test du hashing avec mot de passe long (>72 bytes)."""
        # Créer un mot de passe > 72 bytes
        long_password = "a" * 100  # 100 caractères = 100 bytes en ASCII
        hashed = UserService.hash_password(long_password)

        assert hashed != long_password
        assert len(hashed) > 0
        # Vérifier que le mot de passe complet fonctionne
        assert UserService.verify_password(long_password, hashed)
        # Vérifier qu'un mot de passe tronqué ne fonctionne pas (argon2 utilise le mot de passe complet)
        assert not UserService.verify_password(long_password[:72], hashed)

    async def test_create_user(self, db_session: AsyncSession, test_organization: Organization):
        """Test de création d'utilisateur."""
        user_data = UserCreate(
            email="newuser@example.com",
            username="newuser",
            full_name="New User",
            password="password123",
            organization_id=test_organization.id,
            is_superuser=False
        )

        user = await UserService.create(db_session, user_data)

        assert user.id is not None
        assert user.email == "newuser@example.com"
        assert user.username == "newuser"
        assert user.hashed_password != "password123"
        assert user.organization_id == test_organization.id

    async def test_get_by_id(self, db_session: AsyncSession, test_user: User):
        """Test de récupération par ID."""
        user = await UserService.get_by_id(db_session, test_user.id)

        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    async def test_get_by_email(self, db_session: AsyncSession, test_user: User):
        """Test de récupération par email."""
        user = await UserService.get_by_email(db_session, test_user.email)

        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    async def test_get_by_username(self, db_session: AsyncSession, test_user: User):
        """Test de récupération par username."""
        user = await UserService.get_by_username(db_session, test_user.username)

        assert user is not None
        assert user.id == test_user.id
        assert user.username == test_user.username

    async def test_update_user(self, db_session: AsyncSession, test_user: User):
        """Test de mise à jour d'utilisateur."""
        update_data = UserUpdate(
            full_name="Updated Name",
            email="updated@example.com"
        )

        updated_user = await UserService.update(db_session, test_user, update_data)

        assert updated_user.full_name == "Updated Name"
        assert updated_user.email == "updated@example.com"

    async def test_delete_user(self, db_session: AsyncSession, test_organization: Organization):
        """Test de suppression d'utilisateur."""
        user_data = UserCreate(
            email="todelete@example.com",
            username="todelete",
            full_name="To Delete",
            password="password123",
            organization_id=test_organization.id,
            is_superuser=False
        )

        user = await UserService.create(db_session, user_data)
        user_id = user.id

        await UserService.delete(db_session, user)

        deleted_user = await UserService.get_by_id(db_session, user_id)
        assert deleted_user is None
