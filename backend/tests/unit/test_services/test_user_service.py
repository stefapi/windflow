"""Tests unitaires du service UserService — count_superadmins (STORY-122.4).

Couvre le helper introduit pour la protection « dernier superadmin »
(AC 3) : comptage des utilisateurs ``is_superuser == True`` sur les 3
cas — 0, 1 et N superadmins.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import UserCreate
from app.services.user_service import UserService


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
