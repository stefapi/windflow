"""Tests unitaires d'AuthorizationService (STORY-122.1).

Couverture (cf. story Tâche 5) :
- ``get_global_role`` : superuser → super_admin ; multi-appartenances → max ;
  aucune appartenance → viewer (conservateur) ;
- ``get_role_in_organization`` : superuser bypass, membre / non-membre (None) ;
- ``role_at_least`` : bornes exactes de la hiérarchie, scope global vs org ;
- **cache** : 2e appel servi sans re-requête SQL, TTL expiré → re-requête,
  valeur périmée servie jusqu'à TTL (pire cas borne 300 s) ;
- **invalidation** : rôle changé en base + ``invalidate_user_role_cache``
  → nouvelle résolution immédiate (AC 1).
"""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import MemoryRoleCache, get_role_cache, reset_role_cache
from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.authorization_service import AuthorizationService
from app.services.user_service import UserService


@pytest.fixture(autouse=True)
def _fresh_role_cache():
    """Cache de rôles vierge autour de chaque test (isolation stricte)."""
    reset_role_cache()
    yield
    reset_role_cache()


async def _create_user(
    db: AsyncSession, username: str, is_superuser: bool = False
) -> User:
    """Crée un utilisateur sans appartenance (rôle global attendu : viewer)."""
    return await UserService.create(
        db,
        UserCreate(
            email=f"{username}@example.com",
            username=username,
            full_name=username.title(),
            password="password123",
            is_superuser=is_superuser,
        ),
    )


async def _attach(db: AsyncSession, user: User, org: Organization, role: Role) -> None:
    """Attache un utilisateur à une organisation avec un rôle donné."""
    db.add(UserOrganization(user_id=user.id, organization_id=org.id, role=role))
    await db.commit()


class TestGetGlobalRole:
    """Résolution du rôle global effectif."""

    async def test_superuser_returns_super_admin(
        self, db_session: AsyncSession, test_superuser: User
    ):
        """Superuser → super_admin (court-circuit, sans cache)."""
        role = await AuthorizationService.get_global_role(db_session, test_superuser)
        assert role == "super_admin"

    async def test_no_membership_returns_viewer(self, db_session: AsyncSession):
        """Aucune appartenance → viewer (moindre privilège, conservateur)."""
        user = await _create_user(db_session, "orphan")
        role = await AuthorizationService.get_global_role(db_session, user)
        assert role == "viewer"

    async def test_multiple_memberships_returns_max_role(
        self, db_session: AsyncSession
    ):
        """Multi-appartenances → rôle max (viewer dans org A + admin dans org B → admin)."""
        user = await _create_user(db_session, "multi")
        org_a = Organization(name="Org A", slug="org-a")
        org_b = Organization(name="Org B", slug="org-b")
        db_session.add_all([org_a, org_b])
        await db_session.commit()

        await _attach(db_session, user, org_a, Role.VIEWER)
        await _attach(db_session, user, org_b, Role.ADMIN)

        role = await AuthorizationService.get_global_role(db_session, user)
        assert role == "admin"

    async def test_single_membership_returns_association_role(
        self, db_session: AsyncSession, test_user: User
    ):
        """Fixture test_user (association operator) → operator."""
        role = await AuthorizationService.get_global_role(db_session, test_user)
        assert role == "operator"


class TestGetRoleInOrganization:
    """Résolution du rôle par organisation (isolation)."""

    async def test_superuser_is_super_admin_everywhere(
        self, db_session: AsyncSession, test_superuser: User
    ):
        """Superuser → super_admin dans toute organisation (même inconnue)."""
        role = await AuthorizationService.get_role_in_organization(
            db_session, test_superuser, uuid4()
        )
        assert role == "super_admin"

    async def test_member_returns_stored_role(
        self, db_session: AsyncSession, test_user: User, test_organization: Organization
    ):
        """Membre → rôle stocké dans l'association (operator pour test_user)."""
        role = await AuthorizationService.get_role_in_organization(
            db_session, test_user, test_organization.id
        )
        assert role == "operator"

    async def test_non_member_returns_none(
        self, db_session: AsyncSession, test_user: User
    ):
        """Isolation : organisation inconnue → None (non-membre)."""
        role = await AuthorizationService.get_role_in_organization(
            db_session, test_user, uuid4()
        )
        assert role is None


class TestRoleAtLeast:
    """Vérification hiérarchique — bornes exactes."""

    async def test_admin_at_least_admin_is_true(
        self, db_session: AsyncSession, test_superuser: User
    ):
        """Bornes exactes : admin ≥ admin → True (via superuser ? Non — admin pur)."""
        # Utilisateur admin pur (non superuser)
        user = await _create_user(db_session, "pure-admin")
        org = Organization(name="Org C", slug="org-c")
        db_session.add(org)
        await db_session.commit()
        await _attach(db_session, user, org, Role.ADMIN)

        assert (
            await AuthorizationService.role_at_least(db_session, user, "admin") is True
        )

    async def test_admin_at_least_super_admin_is_false(self, db_session: AsyncSession):
        """Bornes exactes : admin ≥ super_admin → False."""
        user = await _create_user(db_session, "pure-admin-2")
        org = Organization(name="Org D", slug="org-d")
        db_session.add(org)
        await db_session.commit()
        await _attach(db_session, user, org, Role.ADMIN)

        assert (
            await AuthorizationService.role_at_least(db_session, user, "super_admin")
            is False
        )

    async def test_viewer_at_least_operator_is_false(self, db_session: AsyncSession):
        """viewer ≥ operator → False (hiérarchie stricte)."""
        user = await _create_user(db_session, "pure-viewer")
        assert (
            await AuthorizationService.role_at_least(db_session, user, "operator")
            is False
        )

    async def test_superuser_at_least_super_admin_is_true(
        self, db_session: AsyncSession, test_superuser: User
    ):
        """Superuser passe tout, y compris super_admin."""
        assert (
            await AuthorizationService.role_at_least(
                db_session, test_superuser, "super_admin"
            )
            is True
        )

    async def test_scoped_by_organization_ignores_global_role(
        self, db_session: AsyncSession
    ):
        """Scope org : le rôle global ne compte pas — seule l'association org."""
        user = await _create_user(db_session, "scoped-user")
        org = Organization(name="Org E", slug="org-e")
        db_session.add(org)
        await db_session.commit()
        await _attach(db_session, user, org, Role.VIEWER)

        # Global : viewer (une seule appartenance viewer)
        assert (
            await AuthorizationService.role_at_least(db_session, user, "operator")
            is False
        )
        # Scope org : viewer → operator insuffisant, viewer suffisant
        assert (
            await AuthorizationService.role_at_least(
                db_session, user, "operator", organization_id=org.id
            )
            is False
        )
        assert (
            await AuthorizationService.role_at_least(
                db_session, user, "viewer", organization_id=org.id
            )
            is True
        )

    async def test_scoped_non_member_is_false(self, db_session: AsyncSession):
        """Scope org : non-membre → False quel que soit le minimum."""
        user = await _create_user(db_session, "non-member")
        assert (
            await AuthorizationService.role_at_least(
                db_session, user, "viewer", organization_id=uuid4()
            )
            is False
        )

    async def test_unknown_minimum_role_raises(self, db_session: AsyncSession):
        """Rôle minimum inconnu → ValueError (erreur développeur)."""
        user = await _create_user(db_session, "some-user")
        with pytest.raises(ValueError, match="Unknown minimum role"):
            await AuthorizationService.role_at_least(db_session, user, "root")


class TestGlobalRoleCache:
    """Cache TTL du rôle global — cœur de l'AC 1."""

    async def test_second_call_served_from_cache_without_sql(
        self, db_session: AsyncSession, test_user: User
    ):
        """2e appel → hit cache : aucune nouvelle requête SQL (execute non appelé)."""
        first = await AuthorizationService.get_global_role(db_session, test_user)
        assert first == "operator"

        calls = []
        original_execute = db_session.execute

        async def counting_execute(*args, **kwargs):
            calls.append(args)
            return await original_execute(*args, **kwargs)

        db_session.execute = counting_execute  # type: ignore[method-assign]

        second = await AuthorizationService.get_global_role(db_session, test_user)
        assert second == "operator"
        assert calls == []  # servi par le cache, pas de SQL

    async def test_role_change_without_invalidation_served_until_ttl(
        self, db_session: AsyncSession
    ):
        """Pire cas (borne 300 s) : sans invalidation, la valeur périmée reste
        servie jusqu'à l'expiration de la TTL — changement visible seulement après."""
        user = await _create_user(db_session, "cached-user")
        org = Organization(name="Org F", slug="org-f")
        db_session.add(org)
        await db_session.commit()
        await _attach(db_session, user, org, Role.VIEWER)

        assert await AuthorizationService.get_global_role(db_session, user) == "viewer"

        # Le rôle change en base SANS invalidation (simulation d'un écrit
        # direct, hors hooks de gestion des membres)
        link = (
            await db_session.execute(
                select(UserOrganization).where(UserOrganization.user_id == user.id)
            )
        ).scalar_one()
        link.role = Role.ADMIN
        await db_session.commit()

        # Toujours servi depuis le cache : périmé mais cohérent avec la TTL
        assert await AuthorizationService.get_global_role(db_session, user) == "viewer"

        # Expiration de la TTL simulée : les entrées mémoire expirent
        cache = await get_role_cache()
        assert isinstance(cache, MemoryRoleCache)
        for key, (value, expires_at) in list(cache._store.items()):
            cache._store[key] = (value, expires_at - 10_000)

        # Après TTL : la re-requête sert le nouveau rôle
        assert await AuthorizationService.get_global_role(db_session, user) == "admin"

    async def test_invalidation_forces_immediate_resolution(
        self, db_session: AsyncSession
    ):
        """AC 1 : rôle changé + invalidate_user_role_cache → nouvelle valeur
        immédiate (au plus tard 300 s → immédiat avec hook)."""
        user = await _create_user(db_session, "invalidated-user")
        org = Organization(name="Org G", slug="org-g")
        db_session.add(org)
        await db_session.commit()
        await _attach(db_session, user, org, Role.VIEWER)

        assert await AuthorizationService.get_global_role(db_session, user) == "viewer"

        # Changement de rôle + invalidation (comme le hook update_member_role)
        link = (
            await db_session.execute(
                select(UserOrganization).where(UserOrganization.user_id == user.id)
            )
        ).scalar_one()
        link.role = Role.ADMIN
        await db_session.commit()
        await AuthorizationService.invalidate_user_role_cache(user.id)

        # Nouvelle résolution immédiate : admin
        assert await AuthorizationService.get_global_role(db_session, user) == "admin"

    async def test_superuser_bypasses_cache_entirely(
        self, db_session: AsyncSession, test_superuser: User
    ):
        """Superuser : court-circuit — rien n'est mis en cache."""
        assert (
            await AuthorizationService.get_global_role(db_session, test_superuser)
            == "super_admin"
        )
        cache = await get_role_cache()
        assert isinstance(cache, MemoryRoleCache)
        assert cache._store == {}
