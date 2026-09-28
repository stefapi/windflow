"""Tests unitaires API des endpoints membres d'une organisation (STORY-121.2).

Couvre les 4 endpoints spec 09 § Organizations (GET/POST
``/{organization_id}/users``, PUT/DELETE ``/{organization_id}/users/{user_id}``)
en nominal ET en sécurité : 401 sans token ×4, 403 rôle insuffisant
(RBAC intérim superuser), 403 isolation cross-organisation, 404, 409,
422 (rôle invalide dont ``super_admin``, format UUID), exclusion des
champs sensibles (``hashed_password``/``keycloak_id``).

Les associations ``UserOrganization`` sont insérées directement en
session de test (pattern ``test_deployments.py``) — le schéma provient
des migrations (conftest), la table ``user_organizations`` y est présente
automatiquement (STORY-121.1).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.user_organization_service import UserOrganizationService
from app.services.user_service import UserService
from tests.conftest import unwrap

MEMBERS_BASE = "/api/v1/organizations"


async def _create_org(db_session: AsyncSession, name: str, slug: str) -> Organization:
    """Crée une organisation directement en session."""
    org = Organization(
        name=name,
        slug=slug,
        description=f"{name} for member tests",
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


async def _create_user(
    db_session: AsyncSession, username: str, email: str, organization: Organization
) -> User:
    """Crée un utilisateur standard via ``UserService`` (pattern conftest)."""
    data = UserCreate(
        email=email,
        username=username,
        full_name=username.title(),
        password="password123",
        organization_id=organization.id,
        is_superuser=False,
    )
    return await UserService.create(db_session, data)


async def _seed_membership(
    db_session: AsyncSession,
    user: User,
    organization: Organization,
    role: Role = Role.VIEWER,
) -> UserOrganization:
    """Insère une association utilisateur ↔ organisation en session.

    STORY-121.3 : idempotent sur le couple (user, organization) — les
    fixtures rattachent déjà les users de test, la PK composite serait
    sinon violée ; l'association préexistante est remplacée.
    """
    from sqlalchemy import delete

    await db_session.execute(
        delete(UserOrganization).where(
            UserOrganization.user_id == user.id,
            UserOrganization.organization_id == organization.id,
        )
    )
    link = UserOrganization(
        user_id=user.id,
        organization_id=organization.id,
        role=role,
        joined_at=datetime.now(timezone.utc),
    )
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(link)
    return link


@pytest.fixture(autouse=True)
def auth_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Active l'authentification réelle pour tous les tests de ce module.

    DISABLE_AUTH=true en dev : sans ce patch, ``get_current_user``
    cherche un superadmin en base → 500 si inexistant. En forçant
    ``disable_auth=False``, l'auth JWT s'applique normalement (pattern
    ``test_plugins.py`` / ``test_compute_api.py``) — les clients
    ``authenticated_client``/``admin_client`` utilisent des tokens JWT
    réels obtenus via login.
    """
    monkeypatch.setattr(settings, "disable_auth", False)


@pytest.fixture
async def other_org(db_session: AsyncSession) -> Organization:
    """Organisation étrangère (isolation cross-org)."""
    return await _create_org(db_session, "Other Org Members", "other-org-members")


@pytest.fixture
async def target_user(db_session: AsyncSession) -> User:
    """Utilisateur cible existant, sans aucune appartenance (STORY-121.3 :
    ``_create_user`` rattacherait sinon en viewer et le POST membre
    retournerait légitimement 409)."""
    user = User(
        email="memberadd@example.com",
        username="memberadd",
        full_name="Member Add",
        hashed_password=UserService.hash_password("password123"),
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestListMembers:
    """GET /{organization_id}/users."""

    async def test_list_members_returns_members_with_role_and_joined_at(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_organization: Organization,
    ):
        """200 : membres retournés avec ``role`` et ``joined_at`` présents."""
        await _seed_membership(db_session, test_user, test_organization, Role.OPERATOR)

        response = await admin_client.get(
            f"{MEMBERS_BASE}/{test_organization.id}/users"
        )

        assert response.status_code == 200
        members = unwrap(response)
        # STORY-121.3 : le superadmin fixture est membre (role admin) de
        # l'organisation — les membres réels sont listés
        assert len(members) == 2
        by_user = {m["user_id"]: m for m in members}
        member = by_user[test_user.id]
        assert member["role"] == "operator"
        assert "joined_at" in member
        assert member["joined_at"] is not None

    async def test_list_members_empty_organization(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
    ):
        """200 : organisation sans membres → liste vide."""
        # STORY-121.3 : purger les rattachements des fixtures
        # (test_user/test_superuser membres de test_organization)
        from sqlalchemy import delete

        await db_session.execute(
            delete(UserOrganization).where(
                UserOrganization.organization_id == test_organization.id
            )
        )
        await db_session.commit()
        response = await admin_client.get(
            f"{MEMBERS_BASE}/{test_organization.id}/users"
        )

        assert response.status_code == 200
        assert unwrap(response) == []

    async def test_list_members_returns_401_without_token(
        self,
        client: AsyncClient,
        test_organization: Organization,
    ):
        """Sécurité : 401 sans token."""
        response = await client.get(f"{MEMBERS_BASE}/{test_organization.id}/users")
        assert response.status_code == 401

    async def test_list_members_returns_403_for_non_member(
        self,
        authenticated_client: AsyncClient,
        other_org: Organization,
    ):
        """Sécurité isolation : utilisateur non membre de l'org ciblée → 403."""
        response = await authenticated_client.get(
            f"{MEMBERS_BASE}/{other_org.id}/users"
        )
        assert response.status_code == 403

    async def test_list_members_superuser_can_list_any_organization(
        self,
        admin_client: AsyncClient,
        other_org: Organization,
    ):
        """Superuser bypass : 200 sur une organisation étrangère."""
        response = await admin_client.get(f"{MEMBERS_BASE}/{other_org.id}/users")
        assert response.status_code == 200
        assert unwrap(response) == []

    async def test_list_members_returns_404_unknown_organization(
        self,
        admin_client: AsyncClient,
    ):
        """404 : organisation inexistante."""
        response = await admin_client.get(f"{MEMBERS_BASE}/{uuid4()}/users")
        assert response.status_code == 404


class TestAddMember:
    """POST /{organization_id}/users."""

    async def test_add_member_creates_with_default_viewer_role(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
        target_user: User,
    ):
        """201 : ajout sans rôle → rôle par défaut ``viewer``."""
        response = await admin_client.post(
            f"{MEMBERS_BASE}/{test_organization.id}/users",
            json={"user_id": target_user.id},
        )

        assert response.status_code == 201
        body = unwrap(response)
        assert body["user_id"] == target_user.id
        assert body["role"] == "viewer"
        assert body["joined_at"] is not None
        # Persistance en base
        membership = await UserOrganizationService.get_membership(
            db_session, test_organization.id, target_user.id
        )
        assert membership is not None
        assert membership.role == Role.VIEWER

    async def test_add_member_with_explicit_role(
        self,
        admin_client: AsyncClient,
        test_organization: Organization,
        target_user: User,
    ):
        """201 : rôle explicite ``operator`` persisté."""
        response = await admin_client.post(
            f"{MEMBERS_BASE}/{test_organization.id}/users",
            json={"user_id": target_user.id, "role": "operator"},
        )

        assert response.status_code == 201
        assert unwrap(response)["role"] == "operator"

    async def test_add_member_returns_401_without_token(
        self,
        client: AsyncClient,
        test_organization: Organization,
        target_user: User,
    ):
        """Sécurité : 401 sans token."""
        response = await client.post(
            f"{MEMBERS_BASE}/{test_organization.id}/users",
            json={"user_id": target_user.id},
        )
        assert response.status_code == 401

    async def test_add_member_returns_403_for_non_superuser(
        self,
        authenticated_client: AsyncClient,
        test_organization: Organization,
        target_user: User,
    ):
        """Sécurité RBAC intérim : utilisateur standard (même membre) → 403."""
        response = await authenticated_client.post(
            f"{MEMBERS_BASE}/{test_organization.id}/users",
            json={"user_id": target_user.id},
        )
        assert response.status_code == 403

    async def test_add_member_returns_403_for_foreign_organization(
        self,
        authenticated_client: AsyncClient,
        other_org: Organization,
        target_user: User,
    ):
        """Sécurité isolation : non-superuser sur une autre org → 403.

        Intérim : avec ``require_superuser``, un utilisateur standard est
        rejeté 403 (RBAC) avant même le check d'isolation — les deux gardes
        convergent vers 403. Le cas « admin d'une autre org » deviendra
        effectif avec STORY-122 (``require_role("admin")``), l'isolation
        deviendra alors le garde effectif.
        """
        response = await authenticated_client.post(
            f"{MEMBERS_BASE}/{other_org.id}/users",
            json={"user_id": target_user.id},
        )
        assert response.status_code == 403

    async def test_add_member_superuser_can_add_to_foreign_organization(
        self,
        admin_client: AsyncClient,
        other_org: Organization,
        target_user: User,
    ):
        """Superuser bypass de l'isolation : ajout autorisé sur une autre org."""
        response = await admin_client.post(
            f"{MEMBERS_BASE}/{other_org.id}/users",
            json={"user_id": target_user.id},
        )
        assert response.status_code == 201

    async def test_add_member_returns_404_unknown_user(
        self,
        admin_client: AsyncClient,
        test_organization: Organization,
    ):
        """404 : utilisateur cible inexistant."""
        response = await admin_client.post(
            f"{MEMBERS_BASE}/{test_organization.id}/users",
            json={"user_id": str(uuid4())},
        )
        assert response.status_code == 404

    async def test_add_member_returns_409_when_already_member(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
        target_user: User,
    ):
        """409 : utilisateur déjà membre."""
        await _seed_membership(db_session, target_user, test_organization)

        response = await admin_client.post(
            f"{MEMBERS_BASE}/{test_organization.id}/users",
            json={"user_id": target_user.id},
        )
        assert response.status_code == 409

    async def test_add_member_returns_422_on_invalid_role(
        self,
        admin_client: AsyncClient,
        test_organization: Organization,
        target_user: User,
    ):
        """Sécurité anti-escalade : rôle ``super_admin`` (ou arbitraire) → 422."""
        for invalid_role in ("super_admin", "hacker"):
            response = await admin_client.post(
                f"{MEMBERS_BASE}/{test_organization.id}/users",
                json={"user_id": target_user.id, "role": invalid_role},
            )
            assert response.status_code == 422, invalid_role

    async def test_add_member_returns_422_on_invalid_user_id_format(
        self,
        admin_client: AsyncClient,
        test_organization: Organization,
    ):
        """422 : ``user_id`` au format invalide (pas un UUID)."""
        response = await admin_client.post(
            f"{MEMBERS_BASE}/{test_organization.id}/users",
            json={"user_id": "not-an-uuid"},
        )
        assert response.status_code == 422


class TestUpdateMemberRole:
    """PUT /{organization_id}/users/{user_id}."""

    async def test_update_member_role_changes_role(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
        target_user: User,
    ):
        """200 : nouveau rôle retourné et persisté."""
        await _seed_membership(db_session, target_user, test_organization, Role.VIEWER)

        response = await admin_client.put(
            f"{MEMBERS_BASE}/{test_organization.id}/users/{target_user.id}",
            json={"role": "admin"},
        )

        assert response.status_code == 200
        body = unwrap(response)
        assert body["user_id"] == target_user.id
        assert body["role"] == "admin"
        # Persistance
        membership = await UserOrganizationService.get_membership(
            db_session, test_organization.id, target_user.id
        )
        assert membership is not None
        assert membership.role == Role.ADMIN

    async def test_update_member_role_returns_401_without_token(
        self,
        client: AsyncClient,
        test_organization: Organization,
        target_user: User,
    ):
        """Sécurité : 401 sans token."""
        response = await client.put(
            f"{MEMBERS_BASE}/{test_organization.id}/users/{target_user.id}",
            json={"role": "operator"},
        )
        assert response.status_code == 401

    async def test_update_member_role_returns_403_for_non_superuser(
        self,
        authenticated_client: AsyncClient,
        test_organization: Organization,
        target_user: User,
    ):
        """Sécurité RBAC intérim : utilisateur standard → 403."""
        response = await authenticated_client.put(
            f"{MEMBERS_BASE}/{test_organization.id}/users/{target_user.id}",
            json={"role": "operator"},
        )
        assert response.status_code == 403

    async def test_update_member_role_returns_403_for_foreign_organization(
        self,
        authenticated_client: AsyncClient,
        other_org: Organization,
        target_user: User,
    ):
        """Sécurité isolation : non-superuser sur une autre org → 403."""
        response = await authenticated_client.put(
            f"{MEMBERS_BASE}/{other_org.id}/users/{target_user.id}",
            json={"role": "operator"},
        )
        assert response.status_code == 403

    async def test_update_member_role_returns_404_when_not_member(
        self,
        admin_client: AsyncClient,
        test_organization: Organization,
        target_user: User,
    ):
        """404 : utilisateur existant mais non membre de l'organisation."""
        response = await admin_client.put(
            f"{MEMBERS_BASE}/{test_organization.id}/users/{target_user.id}",
            json={"role": "operator"},
        )
        assert response.status_code == 404

    async def test_update_member_role_returns_422_on_invalid_role(
        self,
        admin_client: AsyncClient,
        test_organization: Organization,
        target_user: User,
    ):
        """Sécurité anti-escalade : ``super_admin`` → 422."""
        response = await admin_client.put(
            f"{MEMBERS_BASE}/{test_organization.id}/users/{target_user.id}",
            json={"role": "super_admin"},
        )
        assert response.status_code == 422

    async def test_update_member_role_returns_422_on_missing_role(
        self,
        admin_client: AsyncClient,
        test_organization: Organization,
        target_user: User,
    ):
        """422 : body sans champ ``role``."""
        response = await admin_client.put(
            f"{MEMBERS_BASE}/{test_organization.id}/users/{target_user.id}",
            json={},
        )
        assert response.status_code == 422


class TestRemoveMember:
    """DELETE /{organization_id}/users/{user_id}."""

    async def test_remove_member_returns_204_and_deletes(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
        target_user: User,
    ):
        """204 : membership supprimé en base."""
        await _seed_membership(db_session, target_user, test_organization)

        response = await admin_client.delete(
            f"{MEMBERS_BASE}/{test_organization.id}/users/{target_user.id}"
        )

        assert response.status_code == 204
        assert (
            await UserOrganizationService.get_membership(
                db_session, test_organization.id, target_user.id
            )
            is None
        )

    async def test_remove_member_returns_401_without_token(
        self,
        client: AsyncClient,
        test_organization: Organization,
        target_user: User,
    ):
        """Sécurité : 401 sans token."""
        response = await client.delete(
            f"{MEMBERS_BASE}/{test_organization.id}/users/{target_user.id}"
        )
        assert response.status_code == 401

    async def test_remove_member_returns_403_for_non_superuser(
        self,
        authenticated_client: AsyncClient,
        test_organization: Organization,
        target_user: User,
    ):
        """Sécurité RBAC intérim : utilisateur standard → 403."""
        response = await authenticated_client.delete(
            f"{MEMBERS_BASE}/{test_organization.id}/users/{target_user.id}"
        )
        assert response.status_code == 403

    async def test_remove_member_returns_403_for_foreign_organization(
        self,
        authenticated_client: AsyncClient,
        other_org: Organization,
        target_user: User,
    ):
        """Sécurité isolation : non-superuser sur une autre org → 403."""
        response = await authenticated_client.delete(
            f"{MEMBERS_BASE}/{other_org.id}/users/{target_user.id}"
        )
        assert response.status_code == 403

    async def test_remove_member_returns_404_when_not_member(
        self,
        admin_client: AsyncClient,
        test_organization: Organization,
        target_user: User,
    ):
        """404 : utilisateur existant mais non membre."""
        response = await admin_client.delete(
            f"{MEMBERS_BASE}/{test_organization.id}/users/{target_user.id}"
        )
        assert response.status_code == 404


class TestSensitiveFieldsExposure:
    """Sécurité transverse : aucune réponse membre n'expose de champs sensibles."""

    async def test_members_responses_do_not_expose_sensitive_fields(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
        target_user: User,
    ):
        """Liste / ajout / update : ni ``hashed_password`` ni ``keycloak_id``
        dans le JSON sérialisé (whitelist stricte du schéma dédié)."""
        # Liste (après seed)
        await _seed_membership(db_session, target_user, test_organization)
        list_response = await admin_client.get(
            f"{MEMBERS_BASE}/{test_organization.id}/users"
        )
        assert list_response.status_code == 200
        assert "hashed_password" not in list_response.text
        assert "keycloak_id" not in list_response.text

        # Ajout (autre utilisateur, sans rattachement préalable —
        # STORY-121.3 : sinon déjà membre → 409 légitime)
        from app.models.user import User as UserModel

        other_target = UserModel(
            email="memberadd2@example.com",
            username="memberadd2",
            full_name="Member Add2",
            hashed_password=UserService.hash_password("password123"),
            is_superuser=False,
        )
        db_session.add(other_target)
        await db_session.commit()
        add_response = await admin_client.post(
            f"{MEMBERS_BASE}/{test_organization.id}/users",
            json={"user_id": other_target.id},
        )
        assert add_response.status_code == 201
        assert "hashed_password" not in add_response.text
        assert "keycloak_id" not in add_response.text

        # Update de rôle
        update_response = await admin_client.put(
            f"{MEMBERS_BASE}/{test_organization.id}/users/{other_target.id}",
            json={"role": "operator"},
        )
        assert update_response.status_code == 200
        assert "hashed_password" not in update_response.text
        assert "keycloak_id" not in update_response.text
