"""Tests unitaires du modèle UserOrganization et de l'enum Role (STORY-121.1).

Vérifie :
- l'enum partagé ``Role`` : valeurs exactes ``{viewer, operator, admin}``,
  héritage ``(str, Enum)`` et absence structurelle de ``super_admin``
  (rôle système porté par ``User.is_superuser`` — anti-escalade spec 08) ;
- les défauts du modèle : rôle ``viewer`` (Python et ``server_default``
  SQL sur INSERT brut), timestamps ``joined_at``/``created_at``/``updated_at`` ;
- le bornage du rôle via ``@validates`` (acceptation des 3 rôles en str
  et en ``Role``, refus de ``super_admin``, valeurs inconnues, chaîne vide) ;
- l'intégrité PK composite (doublon ``(user_id, organization_id)`` →
  ``IntegrityError``) ;
- les relations ``User.organization_links`` / ``Organization.user_links``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization


class TestRoleEnum:
    """Enum partagé Role — source unique de vérité du rôle d'association."""

    def test_role_enum_exact_values(self) -> None:
        """Role expose exactement viewer/operator/admin (str minuscules)."""
        assert {member.value for member in Role} == {"viewer", "operator", "admin"}
        assert [member.name for member in Role] == ["VIEWER", "OPERATOR", "ADMIN"]

    def test_role_enum_has_no_super_admin(self) -> None:
        """Sécurité anti-escalade : super_admin n'est pas une valeur d'Role.

        Le Super Admin est un rôle système identifié par le flag
        ``User.is_superuser`` (spec 08) — jamais une valeur d'association
        stockable dans ``user_organizations``.
        """
        values = {member.value for member in Role}
        assert "super_admin" not in values
        assert not hasattr(Role, "SUPER_ADMIN")
        with pytest.raises(ValueError):
            _ = Role("super_admin")

    def test_role_enum_is_str(self) -> None:
        """Héritage (str, Enum) : comparaison directe avec la valeur stockée."""
        assert isinstance(Role.VIEWER, str)
        assert Role.VIEWER == "viewer"
        assert Role.ADMIN == "admin"




async def _purge_user_links(db_session, user) -> None:
    """STORY-121.3 : purge les appartenances du user avant re-seed (les
    fixtures rattachent déjà test_user à test_organization — PK composite
    sinon violée)."""
    from sqlalchemy import delete

    await db_session.execute(
        delete(UserOrganization).where(UserOrganization.user_id == user.id)
    )
    await db_session.commit()

class TestUserOrganizationDefaults:
    """Cas nominaux : défauts de rôle et timestamps."""

    async def test_default_role_is_viewer(
        self, db_session, test_user, test_organization
    ):
        """Association créée sans rôle → role == Role.VIEWER après flush."""
        await _purge_user_links(db_session, test_user)
        link = UserOrganization(
            user_id=test_user.id, organization_id=test_organization.id
        )
        db_session.add(link)
        await db_session.flush()

        assert link.role == Role.VIEWER

    async def test_server_default_viewer_on_raw_insert(
        self, db_session, test_user, test_organization
    ):
        """INSERT SQL brut sans colonne role → 'viewer' en base.

        Preuve du ``server_default`` : c'est la base (pas Python) qui
        fournit la valeur — utilisé par la migration de données
        STORY-121.3 (INSERT bruts).
        """
        await _purge_user_links(db_session, test_user)
        await db_session.execute(
            text(
                "INSERT INTO user_organizations "
                "(user_id, organization_id, joined_at, created_at, updated_at) "
                "VALUES (:uid, :oid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            ),
            {"uid": test_user.id, "oid": test_organization.id},
        )
        stored = (
            await db_session.execute(
                text(
                    "SELECT role FROM user_organizations "
                    "WHERE user_id = :uid AND organization_id = :oid"
                ),
                {"uid": test_user.id, "oid": test_organization.id},
            )
        ).scalar_one()
        assert stored == "viewer"

    async def test_joined_at_and_timestamps_defaulted(
        self, db_session, test_user, test_organization
    ):
        """joined_at, created_at, updated_at non nuls après flush."""
        await _purge_user_links(db_session, test_user)
        link = UserOrganization(
            user_id=test_user.id, organization_id=test_organization.id
        )
        db_session.add(link)
        await db_session.flush()

        assert link.joined_at is not None
        assert link.created_at is not None
        assert link.updated_at is not None


class TestRoleValidation:
    """Cas d'erreurs + sécurité : bornage role via @validates."""

    async def test_validates_accepts_all_three_roles(
        self, db_session, test_user, test_organization
    ):
        """viewer/operator/admin acceptés, en str comme en Role."""
        for index, role_value in enumerate(["viewer", "operator", "admin"]):
            link = UserOrganization(
                user_id=test_user.id,
                organization_id=f"00000000-0000-0000-0000-00000000000{index}",
                role=role_value,
            )
            assert link.role == Role(role_value)

        link_enum = UserOrganization(
            user_id=test_user.id,
            organization_id="00000000-0000-0000-0000-0000000000ff",
            role=Role.ADMIN,
        )
        assert link_enum.role is Role.ADMIN

    async def test_validates_rejects_super_admin(self, test_user, test_organization):
        """Sécurité anti-escalade : role='super_admin' → ValueError."""
        with pytest.raises(ValueError, match="super_admin"):
            UserOrganization(
                user_id=test_user.id,
                organization_id=test_organization.id,
                role="super_admin",
            )

    async def test_validates_rejects_unknown_role(self, test_user, test_organization):
        """role='hacker' → ValueError (liste blanche enum uniquement)."""
        with pytest.raises(ValueError, match="hacker"):
            UserOrganization(
                user_id=test_user.id,
                organization_id=test_organization.id,
                role="hacker",
            )

    async def test_validates_rejects_empty_role(self, test_user, test_organization):
        """role='' → ValueError (chaîne vide refusée explicitement)."""
        with pytest.raises(ValueError):
            UserOrganization(
                user_id=test_user.id,
                organization_id=test_organization.id,
                role="",
            )


class TestIntegrity:
    """Intégrité PK composite (user_id, organization_id)."""

    async def test_duplicate_pair_raises_integrity_error(
        self, db_session, test_user, test_organization
    ):
        """2 lignes même (user_id, organization_id) → IntegrityError."""
        await _purge_user_links(db_session, test_user)
        first = UserOrganization(
            user_id=test_user.id, organization_id=test_organization.id
        )
        db_session.add(first)
        await db_session.flush()

        duplicate = UserOrganization(
            user_id=test_user.id, organization_id=test_organization.id
        )
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


class TestRelationships:
    """Relations navigables User ↔ UserOrganization ↔ Organization."""

    async def test_user_relationship_organization_links(
        self, db_session, test_user, test_organization
    ):
        """test_user.organization_links navigable après flush d'une association."""
        await _purge_user_links(db_session, test_user)
        link = UserOrganization(
            user_id=test_user.id, organization_id=test_organization.id
        )
        db_session.add(link)
        await db_session.flush()

        # Rechargement explicite (selectinload) : le lazy-loading est
        # interdit en contexte async (greenlet).
        user = (
            await db_session.execute(
                select(User).options(selectinload(User.organization_links))
            )
        ).scalar_one()
        assert len(user.organization_links) == 1
        assert user.organization_links[0].role == Role.VIEWER

    async def test_organization_relationship_user_links(
        self, db_session, test_user, test_organization
    ):
        """test_organization.user_links navigable après flush d'une association."""
        await _purge_user_links(db_session, test_user)
        link = UserOrganization(
            user_id=test_user.id, organization_id=test_organization.id
        )
        db_session.add(link)
        await db_session.flush()

        # Rechargement explicite (selectinload) : le lazy-loading est
        # interdit en contexte async (greenlet).
        organization = (
            await db_session.execute(
                select(Organization).options(selectinload(Organization.user_links))
            )
        ).scalar_one()
        assert len(organization.user_links) == 1
        assert organization.user_links[0].user_id == test_user.id

    def test_tablename(self) -> None:
        """__tablename__ == 'user_organizations' (convention spec 06)."""
        assert UserOrganization.__tablename__ == "user_organizations"
