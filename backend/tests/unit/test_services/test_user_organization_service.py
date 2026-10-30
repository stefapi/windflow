"""Tests unitaires du service UserOrganizationService (STORY-121.2).

Couvre les 6 méthodes du service : helper d'isolation cross-organisation
``is_member`` (association, fallback intérim colonne héritée, refus
utilisateur étranger, bypass superuser), CRUD des associations
(``list_members``, ``add_member``, ``get_membership``,
``update_member_role``, ``remove_member``).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.organization_member import OrganizationMemberAddRequest
from app.schemas.user import UserCreate
from app.services.user_organization_service import UserOrganizationService
from app.services.user_service import UserService


@pytest.fixture
async def other_org(db_session: AsyncSession) -> Organization:
    """Organisation étrangère (distincte de ``test_organization``)."""
    org = Organization(
        name="Other Organization",
        slug="other-org",
        description="Foreign organization for isolation tests",
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


async def _create_user(
    db_session: AsyncSession, username: str, email: str, organization: Organization
) -> User:
    """Crée un utilisateur standard rattaché à l'organisation donnée."""
    data = UserCreate(
        email=email,
        username=username,
        full_name=username.title(),
        password="password123",
        organization_id=organization.id,
        is_superuser=False,
    )
    return await UserService.create(db_session, data)


def _seed_link(
    user: User,
    organization: Organization,
    role: Role = Role.VIEWER,
    joined_at: datetime | None = None,
) -> UserOrganization:
    """Construit une association (non commitée) avec ``joined_at`` contrôlable."""
    return UserOrganization(
        user_id=user.id,
        organization_id=organization.id,
        role=role,
        joined_at=joined_at or datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc),
    )


async def _purge_user_links(db_session: AsyncSession, user: User) -> None:
    """Purge les appartenances du user avant re-seed (STORY-121.3 : les
    fixtures rattachent déjà les users de test — PK composite sinon
    violée par les scénarios qui réinsèrent ces couples)."""
    await db_session.execute(
        delete(UserOrganization).where(UserOrganization.user_id == user.id)
    )


class TestIsMember:
    """Helper d'isolation cross-organisation ``is_member``."""

    async def test_is_member_true_via_association(
        self,
        db_session: AsyncSession,
        test_user: User,
        other_org: Organization,
    ):
        """Cas nominal : ligne ``UserOrganization`` présente → True."""
        db_session.add(_seed_link(test_user, other_org))
        await db_session.commit()

        result = await UserOrganizationService.is_member(
            db_session, test_user, other_org.id
        )
        assert result is True

    async def test_is_member_false_without_association(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """STORY-121.3 : sans ligne en table (la colonne héritée n'existe
        plus) → False — le fallback intérim a été retiré."""
        from uuid import uuid4

        result = await UserOrganizationService.is_member(
            db_session, test_user, str(uuid4())
        )
        assert result is False

    async def test_is_member_false_for_foreign_user(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        other_org: Organization,
    ):
        """Cas d'erreur : utilisateur d'une autre organisation → False."""
        foreign_user = await _create_user(
            db_session, "foreignuser", "foreign@example.com", other_org
        )

        result = await UserOrganizationService.is_member(
            db_session, foreign_user, test_organization.id
        )
        assert result is False

    async def test_is_member_superuser_bypass(
        self,
        db_session: AsyncSession,
        test_superuser: User,
        other_org: Organization,
    ):
        """Sécurité : superuser sans aucune appartenance → True (bypass)."""
        result = await UserOrganizationService.is_member(
            db_session, test_superuser, other_org.id
        )
        assert result is True


class TestAddMember:
    """Création d'associations ``add_member``."""

    async def test_add_member_defaults_to_viewer(
        self,
        db_session: AsyncSession,
        test_user: User,
        other_org: Organization,
    ):
        """Cas nominal : ajout sans rôle → rôle par défaut ``viewer``."""
        data = OrganizationMemberAddRequest(user_id=UUID(test_user.id))

        membership = await UserOrganizationService.add_member(
            db_session, other_org.id, data
        )

        assert membership.role == Role.VIEWER
        assert membership.organization_id == other_org.id

    async def test_add_member_with_explicit_role(
        self,
        db_session: AsyncSession,
        test_user: User,
        other_org: Organization,
    ):
        """Cas nominal : rôle ``operator`` explicite persisté."""
        data = OrganizationMemberAddRequest(
            user_id=UUID(test_user.id), role=Role.OPERATOR
        )

        membership = await UserOrganizationService.add_member(
            db_session, other_org.id, data
        )

        assert membership.role == Role.OPERATOR

    async def test_add_member_unknown_user_raises(
        self,
        db_session: AsyncSession,
        other_org: Organization,
    ):
        """Cas d'erreur : ``user_id`` inexistant → ValueError (404 côté API)."""
        data = OrganizationMemberAddRequest(user_id=uuid4())

        with pytest.raises(ValueError):
            await UserOrganizationService.add_member(db_session, other_org.id, data)

    async def test_add_member_duplicate_raises(
        self,
        db_session: AsyncSession,
        test_user: User,
        other_org: Organization,
    ):
        """Cas d'erreur : membre déjà présent → ValueError (409 côté API)."""
        data = OrganizationMemberAddRequest(user_id=UUID(test_user.id))
        await UserOrganizationService.add_member(db_session, other_org.id, data)

        with pytest.raises(ValueError):
            await UserOrganizationService.add_member(db_session, other_org.id, data)


class TestListMembers:
    """Liste paginée des membres ``list_members``."""

    async def test_list_members_returns_links_with_user_loaded(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_superuser: User,
        test_organization: Organization,
    ):
        """Cas nominal : membres ordonnés par ``joined_at``, relation ``user``
        accessible sans requête supplémentaire (``selectinload``)."""
        base = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)
        # STORY-121.3 : les fixtures rattachent déjà ces users à
        # test_organization — purger avant de re-seeder avec des
        # joined_at contrôlés (PK composite sinon violée)
        await db_session.execute(
            delete(UserOrganization).where(
                UserOrganization.organization_id == test_organization.id
            )
        )
        db_session.add_all(
            [
                _seed_link(
                    test_user,
                    test_organization,
                    role=Role.VIEWER,
                    joined_at=base,
                ),
                _seed_link(
                    test_superuser,
                    test_organization,
                    role=Role.ADMIN,
                    joined_at=base + timedelta(hours=1),
                ),
            ]
        )
        await db_session.commit()

        members = await UserOrganizationService.list_members(
            db_session, test_organization.id
        )

        assert len(members) == 2
        # Tri par joined_at croissant : test_user (10:00) avant test_superuser (11:00)
        assert members[0].user_id == test_user.id
        assert members[1].user_id == test_superuser.id
        # Relation user chargée (selectinload) : attributs accessibles
        assert members[0].user.username == test_user.username
        assert members[1].user.username == test_superuser.username
        assert members[0].role == Role.VIEWER

    async def test_list_members_pagination(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_superuser: User,
        test_organization: Organization,
    ):
        """``skip``/``limit`` respectés."""
        base = datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc)
        # STORY-121.3 : purge des appartenances posées par les fixtures
        await db_session.execute(
            delete(UserOrganization).where(
                UserOrganization.organization_id == test_organization.id
            )
        )
        third_user = await _create_user(
            db_session, "thirduser", "third@example.com", test_organization
        )
        await _purge_user_links(db_session, third_user)
        db_session.add_all(
            [
                _seed_link(test_user, test_organization, joined_at=base),
                _seed_link(
                    test_superuser,
                    test_organization,
                    joined_at=base + timedelta(hours=1),
                ),
                _seed_link(
                    third_user,
                    test_organization,
                    joined_at=base + timedelta(hours=2),
                ),
            ]
        )
        await db_session.commit()

        page = await UserOrganizationService.list_members(
            db_session, test_organization.id, skip=1, limit=1
        )

        assert len(page) == 1
        assert page[0].user_id == test_superuser.id


class TestGetMembership:
    """Lookup par PK composite ``get_membership``."""

    async def test_get_membership_by_composite_pk(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
        other_org: Organization,
    ):
        """Found pour (user, org) ; None pour autre org ou autre user."""
        await _purge_user_links(db_session, test_user)
        db_session.add(_seed_link(test_user, test_organization))
        await db_session.commit()

        found = await UserOrganizationService.get_membership(
            db_session, test_organization.id, test_user.id
        )
        assert found is not None
        assert found.user_id == test_user.id
        assert found.role == Role.VIEWER

        # Autre organisation → None
        assert (
            await UserOrganizationService.get_membership(
                db_session, other_org.id, test_user.id
            )
            is None
        )
        # Autre utilisateur → None
        assert (
            await UserOrganizationService.get_membership(
                db_session, test_organization.id, uuid4()
            )
            is None
        )


class TestGetUserOrganizationIds:
    """Helper de scoping multi-appartenance (STORY-121.3)."""

    async def test_get_user_organization_ids_returns_all_memberships(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
        other_org: Organization,
    ):
        """User avec 2 associations → les 2 org_ids."""
        await _purge_user_links(db_session, test_user)
        db_session.add_all(
            [
                _seed_link(
                    test_user,
                    test_organization,
                    joined_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
                _seed_link(
                    test_user,
                    other_org,
                    joined_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
                ),
            ]
        )
        await db_session.commit()

        ids = await UserOrganizationService.get_user_organization_ids(
            db_session, test_user
        )
        assert set(ids) == {test_organization.id, other_org.id}

    async def test_get_user_organization_ids_empty_for_user_without_membership(
        self,
        db_session: AsyncSession,
    ):
        """User sans aucune appartenance → liste vide."""
        from uuid import uuid4

        orphan = User(
            id=str(uuid4()),
            email="orphan@example.com",
            username="orphan",
            hashed_password="x",
        )
        db_session.add(orphan)
        await db_session.commit()

        ids = await UserOrganizationService.get_user_organization_ids(
            db_session, orphan
        )
        assert ids == []


class TestGetPrimaryOrganizationId:
    """Helper d'organisation primaire (STORY-121.3)."""

    async def test_get_primary_organization_id_returns_oldest_membership(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
        other_org: Organization,
    ):
        """2 associations avec joined_at ordonnés → la plus ancienne."""
        await _purge_user_links(db_session, test_user)
        db_session.add_all(
            [
                _seed_link(
                    test_user,
                    other_org,
                    joined_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
                ),
                _seed_link(
                    test_user,
                    test_organization,
                    joined_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
            ]
        )
        await db_session.commit()

        primary = await UserOrganizationService.get_primary_organization_id(
            db_session, test_user
        )
        assert primary == test_organization.id

    async def test_get_primary_organization_id_none_without_membership(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Aucune appartenance → None (après retrait des lignes de test)."""
        # Retirer les appartenances posées par les fixtures
        await db_session.execute(
            select(UserOrganization).where(UserOrganization.user_id == test_user.id)
        )
        from sqlalchemy import delete

        await db_session.execute(
            delete(UserOrganization).where(UserOrganization.user_id == test_user.id)
        )
        await db_session.commit()

        primary = await UserOrganizationService.get_primary_organization_id(
            db_session, test_user
        )
        assert primary is None


class TestUpdateAndRemove:
    """Mise à jour de rôle et retrait de membre."""

    async def test_update_member_role_persists(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """Cas nominal : changement ``viewer`` → ``admin`` persisté."""
        await _purge_user_links(db_session, test_user)
        db_session.add(_seed_link(test_user, test_organization))
        await db_session.commit()
        membership = await UserOrganizationService.get_membership(
            db_session, test_organization.id, test_user.id
        )
        assert membership is not None

        await UserOrganizationService.update_member_role(
            db_session, membership, Role.ADMIN
        )

        refreshed = await UserOrganizationService.get_membership(
            db_session, test_organization.id, test_user.id
        )
        assert refreshed is not None
        assert refreshed.role == Role.ADMIN

    async def test_remove_member_deletes_row(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """Cas nominal : ligne supprimée, ``get_membership`` → None après."""
        await _purge_user_links(db_session, test_user)
        await _purge_user_links(db_session, test_user)
        db_session.add(_seed_link(test_user, test_organization))
        await db_session.commit()
        membership = await UserOrganizationService.get_membership(
            db_session, test_organization.id, test_user.id
        )
        assert membership is not None

        await UserOrganizationService.remove_member(db_session, membership)

        assert (
            await UserOrganizationService.get_membership(
                db_session, test_organization.id, test_user.id
            )
            is None
        )
