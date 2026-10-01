"""Tests API utilisateurs après la bascule STORY-121.3.

Scoping multi-appartenances, isolation croisée (403 sans org partagée),
validation des organisations cibles (404), réaffectation via associations.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.user_service import UserService


async def _make_user_in(
    db_session: AsyncSession, username: str, org: Organization
) -> User:
    """Crée un utilisateur rattaché (viewer) à l'organisation donnée."""
    user = await UserService.create(
        db_session,
        UserCreate(
            email=f"{username}@example.com",
            username=username,
            full_name=username.title(),
            password="password123",
            organization_id=org.id,
            is_superuser=False,
        ),
    )
    return user


async def _make_org(db_session: AsyncSession, slug: str) -> Organization:
    org = Organization(name=f"Org {slug}", slug=slug, description="")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


class TestListUsersScoping:
    """Scoping de la liste sur les appartenances."""

    async def test_list_users_scopes_to_all_memberships(
        self, authenticated_client, db_session, test_user, test_organization
    ):
        """User membre de 2 orgs → users des 2 orgs listés (contrat paginé
        STORY-128 : liste sous ``data``)."""
        other_org = await _make_org(db_session, "scope-other")
        other_user = await _make_user_in(db_session, "scopedother", other_org)
        # test_user appartient déjà à test_organization (fixture) ; on
        # ajoute la 2e appartenance
        db_session.add(
            UserOrganization(
                user_id=test_user.id,
                organization_id=other_org.id,
                role=Role.VIEWER,
            )
        )
        await db_session.commit()

        response = await authenticated_client.get("/api/v1/users/")
        assert response.status_code == 200, response.text
        body = response.json()
        listed_ids = {item["id"] for item in body["data"]}
        assert test_user.id in listed_ids
        assert other_user.id in listed_ids, "la 2e appartenance doit être scopée"


class TestGetUserIsolation:
    """Isolation croisée sur les lectures users."""

    async def test_get_user_forbidden_without_shared_organization(
        self, authenticated_client, db_session, test_organization
    ):
        """Sécurité isolation : cible sans org commune avec le demandeur
        (non-superuser) → 403."""
        foreign_org = await _make_org(db_session, "foreign-isolation")
        foreign_user = await _make_user_in(db_session, "foreignuser", foreign_org)

        response = await authenticated_client.get(f"/api/v1/users/{foreign_user.id}")
        assert response.status_code == 403

    async def test_get_user_allowed_with_shared_organization(
        self, authenticated_client, db_session, test_user, test_organization
    ):
        """Cible partageant une org avec le demandeur → 200."""
        colleague = await _make_user_in(db_session, "colleague", test_organization)

        response = await authenticated_client.get(f"/api/v1/users/{colleague.id}")
        assert response.status_code == 200, response.text
        assert unwrap(response)["id"] == colleague.id

    async def test_superuser_access_unaffected(
        self, admin_client, db_session, test_organization
    ):
        """Superuser → 200 sur toute cible (bypass conservé)."""
        foreign_org = await _make_org(db_session, "super-foreign")
        foreign_user = await _make_user_in(db_session, "superforeign", foreign_org)

        response = await admin_client.get(f"/api/v1/users/{foreign_user.id}")
        assert response.status_code == 200, response.text


class TestCreateUser:
    """Création : validation de l'organisation cible."""

    async def test_create_user_validates_target_organization_404(self, admin_client):
        """Org cible inexistante → 404 (aucun user créé)."""
        response = await admin_client.post(
            "/api/v1/users/",
            json={
                "email": "badorg@example.com",
                "username": "badorguser",
                "password": "password123",
                "organization_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert response.status_code == 404


class TestUpdateUserReassignment:
    """Réaffectation via UserUpdate.organization_id (opération d'association)."""

    async def test_update_user_reassignment_moves_membership(
        self,
        admin_client,
        db_session,
        test_user,
        test_organization,
    ):
        """Update avec organization_id → ancienne appartenance supprimée,
        nouvelle créée avec rôle viewer."""
        new_org = await _make_org(db_session, "reassign-target")

        response = await admin_client.put(
            f"/api/v1/users/{test_user.id}",
            json={"organization_id": new_org.id},
        )
        assert response.status_code == 200, response.text

        links = (
            (
                await db_session.execute(
                    select(UserOrganization).where(
                        UserOrganization.user_id == test_user.id
                    )
                )
            )
            .scalars()
            .all()
        )
        org_links = {link.organization_id: link for link in links}
        # L'ancienne appartenance unique est retirée (réaffectation) et la
        # nouvelle org est présente en viewer. La fixture ayant promu
        # test_user en operator sur test_organization, l'ancienne ligne
        # (test_organization) doit avoir été supprimée par la réaffectation.
        assert new_org.id in org_links, "nouvelle appartenance absente"
        new_link = org_links[new_org.id]
        role_value = (
            new_link.role.value if hasattr(new_link.role, "value") else new_link.role
        )
        assert role_value == "viewer"
        assert test_organization.id not in org_links, (
            "l'ancienne appartenance doit être retirée (sémantique "
            "unique-appartenance conservée)"
        )

    async def test_reassign_bulk_moves_memberships(
        self, admin_client, db_session, test_organization, test_user
    ):
        """Réaffectation en masse → associations déplacées (pas de colonne)."""
        new_org = await _make_org(db_session, "bulk-target")

        response = await admin_client.post(
            "/api/v1/users/bulk/assign-organization",
            json={"user_ids": [test_user.id], "organization_id": new_org.id},
        )
        assert response.status_code == 200, response.text
        assert unwrap(response)["success"] == [test_user.id]

        links = (
            (
                await db_session.execute(
                    select(UserOrganization).where(
                        UserOrganization.user_id == test_user.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert {link.organization_id for link in links} == {new_org.id}
