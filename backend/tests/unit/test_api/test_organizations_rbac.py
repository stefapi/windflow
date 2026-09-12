"""Tests RBAC du router organizations (STORY-122.4, matrice spec 08).

Couverture (AC 2 volet organizations) :
- GET membres : viewer **membre** → 200 ; non-membre → 403 (isolation) ;
- écritures membres (POST/PUT/DELETE) : admin d'org A → 200 **dans A**,
  403 sur org B (isolation), operator → 403 (rôle insuffisant) ;
- création org : admin simple → 403, superuser → 201 (Super Admin only) ;
- liste globale / suppression / bulk : super_admin uniquement ;
- 401 sans token (échantillon), 404 org inexistante.

Setup : org A + org B ; admin-A, operator-A, viewer-A, viewer-B, superuser.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.core.cache import reset_role_cache
from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.user_service import UserService

# --- Helpers --------------------------------------------------------------


async def _create_org(db_session: AsyncSession, name: str) -> Organization:
    """Crée une organisation."""
    org = Organization(name=name, slug=name.lower().replace(" ", "-"))
    db_session.add(org)
    await db_session.commit()
    return org


async def _create_user_in_org(
    db_session: AsyncSession,
    username: str,
    org: Organization,
    role: Role,
    is_superuser: bool = False,
) -> User:
    """Crée un utilisateur rattaché à l'organisation avec le rôle donné."""
    user = await UserService.create(
        db_session,
        UserCreate(
            email=f"{username}@example.com",
            username=username,
            full_name=username.title(),
            password="password123",
            is_superuser=is_superuser,
        ),
    )
    db_session.add(UserOrganization(user_id=user.id, organization_id=org.id, role=role))
    await db_session.commit()
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 122.2."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


@pytest.fixture(autouse=True)
def _fresh_role_cache():
    """Cache de rôles vierge autour de chaque test."""
    reset_role_cache()
    yield
    reset_role_cache()


@pytest.fixture
async def orgs_setup(db_session: AsyncSession):
    """Seed : org A + org B, admin-A, operator-A, viewer-A, viewer-B, superuser."""
    org_a = await _create_org(db_session, "Org Charlie")
    org_b = await _create_org(db_session, "Org Delta")

    admin_a = await _create_user_in_org(
        db_session, "org-admin-charlie", org_a, Role.ADMIN
    )
    operator_a = await _create_user_in_org(
        db_session, "org-operator-charlie", org_a, Role.OPERATOR
    )
    viewer_a = await _create_user_in_org(
        db_session, "org-viewer-charlie", org_a, Role.VIEWER
    )
    viewer_b = await _create_user_in_org(
        db_session, "org-viewer-delta", org_b, Role.VIEWER
    )
    # Cible d'ajout : user sans org (candidate à l'ajout dans A)
    candidate = await UserService.create(
        db_session,
        UserCreate(
            email="candidate-charlie@example.com",
            username="candidate-charlie",
            full_name="Candidate Charlie",
            password="password123",
        ),
    )
    superuser = await UserService.create(
        db_session,
        UserCreate(
            email="super-org-rbac@example.com",
            username="super-org-rbac",
            full_name="Super Org Rbac",
            password="password123",
            is_superuser=True,
        ),
    )
    return {
        "org_a": org_a,
        "org_b": org_b,
        "admin_a": admin_a,
        "operator_a": operator_a,
        "viewer_a": viewer_a,
        "viewer_b": viewer_b,
        "candidate": candidate,
        "superuser": superuser,
    }


# --- GET membres : viewer + isolation --------------------------------------


class TestListMembersMatrix:
    """Route 8 : GET /organizations/{id}/users — viewer membre, isolation."""

    async def test_viewer_member_can_list_own_org_members(
        self, client: AsyncClient, orgs_setup
    ):
        """Viewer membre de A → 200 sur GET membres de A."""
        response = await client.get(
            f"/api/v1/organizations/{orgs_setup['org_a'].id}/users",
            headers=_auth_headers(orgs_setup["viewer_a"]),
        )
        assert response.status_code == 200, response.text
        assert isinstance(response.json(), list)

    async def test_viewer_cannot_list_foreign_org_members(
        self, client: AsyncClient, orgs_setup
    ):
        """Viewer de A sur org B → 403 (isolation cross-organisation)."""
        response = await client.get(
            f"/api/v1/organizations/{orgs_setup['org_b'].id}/users",
            headers=_auth_headers(orgs_setup["viewer_a"]),
        )
        assert response.status_code == 403

    async def test_superuser_can_list_any_org_members(
        self, client: AsyncClient, orgs_setup
    ):
        """Superuser bypass → 200 sur les membres de B."""
        response = await client.get(
            f"/api/v1/organizations/{orgs_setup['org_b'].id}/users",
            headers=_auth_headers(orgs_setup["superuser"]),
        )
        assert response.status_code == 200, response.text

    async def test_list_members_404_unknown_org(self, client: AsyncClient, orgs_setup):
        """Org inexistante → 404 (après le check d'isolation)."""
        response = await client.get(
            "/api/v1/organizations/00000000-0000-0000-0000-000000000001/users",
            headers=_auth_headers(orgs_setup["superuser"]),
        )
        assert response.status_code == 404


# --- Écritures membres : admin d'org + isolation ----------------------------


class TestMemberWritesMatrix:
    """Routes 9-10 : POST/PUT/DELETE membres — admin dans son org seulement."""

    async def test_admin_adds_member_in_own_org(self, client: AsyncClient, orgs_setup):
        """Admin de A ajoute un viewer dans A → 201."""
        response = await client.post(
            f"/api/v1/organizations/{orgs_setup['org_a'].id}/users",
            json={"user_id": str(orgs_setup["candidate"].id), "role": "viewer"},
            headers=_auth_headers(orgs_setup["admin_a"]),
        )
        assert response.status_code == 201, response.text
        assert response.json()["role"] == "viewer"

    async def test_admin_cannot_add_member_in_foreign_org(
        self, client: AsyncClient, orgs_setup
    ):
        """Admin de A tente un ajout dans B → 403 (isolation)."""
        response = await client.post(
            f"/api/v1/organizations/{orgs_setup['org_b'].id}/users",
            json={"user_id": str(orgs_setup["candidate"].id), "role": "viewer"},
            headers=_auth_headers(orgs_setup["admin_a"]),
        )
        assert response.status_code == 403

    async def test_admin_updates_member_role_in_own_org(
        self, client: AsyncClient, orgs_setup
    ):
        """Admin de A promeut viewer→operator dans A → 200 (rôle < sien)."""
        response = await client.put(
            f"/api/v1/organizations/{orgs_setup['org_a'].id}/users"
            f"/{orgs_setup['viewer_a'].id}",
            json={"role": "operator"},
            headers=_auth_headers(orgs_setup["admin_a"]),
        )
        assert response.status_code == 200, response.text
        assert response.json()["role"] == "operator"

    async def test_admin_cannot_update_member_in_foreign_org(
        self, client: AsyncClient, orgs_setup
    ):
        """Admin de A modifie un membre de B → 403 (isolation)."""
        response = await client.put(
            f"/api/v1/organizations/{orgs_setup['org_b'].id}/users"
            f"/{orgs_setup['viewer_b'].id}",
            json={"role": "operator"},
            headers=_auth_headers(orgs_setup["admin_a"]),
        )
        assert response.status_code == 403

    async def test_admin_removes_member_in_own_org(
        self, client: AsyncClient, orgs_setup
    ):
        """Admin de A retire un membre de A → 204."""
        response = await client.delete(
            f"/api/v1/organizations/{orgs_setup['org_a'].id}/users"
            f"/{orgs_setup['viewer_a'].id}",
            headers=_auth_headers(orgs_setup["admin_a"]),
        )
        assert response.status_code == 204, response.text

    async def test_admin_cannot_remove_member_in_foreign_org(
        self, client: AsyncClient, orgs_setup
    ):
        """Admin de A retire un membre de B → 403 (isolation)."""
        response = await client.delete(
            f"/api/v1/organizations/{orgs_setup['org_b'].id}/users"
            f"/{orgs_setup['viewer_b'].id}",
            headers=_auth_headers(orgs_setup["admin_a"]),
        )
        assert response.status_code == 403

    async def test_operator_cannot_write_members(self, client: AsyncClient, orgs_setup):
        """Operator de A (membre) → 403 sur POST membres (rôle insuffisant)."""
        response = await client.post(
            f"/api/v1/organizations/{orgs_setup['org_a'].id}/users",
            json={"user_id": str(orgs_setup["candidate"].id), "role": "viewer"},
            headers=_auth_headers(orgs_setup["operator_a"]),
        )
        assert response.status_code == 403

    async def test_member_write_404_unknown_org(self, client: AsyncClient, orgs_setup):
        """Ajout dans une org inexistante → 404 (superuser : passe isolation)."""
        response = await client.post(
            "/api/v1/organizations/00000000-0000-0000-0000-000000000002/users",
            json={"user_id": str(orgs_setup["candidate"].id), "role": "viewer"},
            headers=_auth_headers(orgs_setup["superuser"]),
        )
        assert response.status_code == 404


# --- Administration d'instance : super_admin only ---------------------------


class TestInstanceAdministrationMatrix:
    """Routes 1, 3, 5, 6 : liste globale, création, suppression, bulk."""

    async def test_list_all_orgs_admin_forbidden(self, client: AsyncClient, orgs_setup):
        """GET /organizations (liste globale) avec admin d'org → 403."""
        response = await client.get(
            "/api/v1/organizations/",
            headers=_auth_headers(orgs_setup["admin_a"]),
        )
        assert response.status_code == 403

    async def test_list_all_orgs_superuser_ok(self, client: AsyncClient, orgs_setup):
        """GET /organizations avec superuser → 200."""
        response = await client.get(
            "/api/v1/organizations/",
            headers=_auth_headers(orgs_setup["superuser"]),
        )
        assert response.status_code == 200, response.text

    async def test_create_org_admin_forbidden(self, client: AsyncClient, orgs_setup):
        """POST /organizations avec admin simple → 403 (Super Admin only)."""
        response = await client.post(
            "/api/v1/organizations/",
            json={"name": "Org Created By Admin"},
            headers=_auth_headers(orgs_setup["admin_a"]),
        )
        assert response.status_code == 403

    async def test_create_org_superuser_created(self, client: AsyncClient, orgs_setup):
        """POST /organizations avec superuser → 201 (matrice spec 08)."""
        response = await client.post(
            "/api/v1/organizations/",
            json={"name": "Org Created By Superuser"},
            headers=_auth_headers(orgs_setup["superuser"]),
        )
        assert response.status_code == 201, response.text

    async def test_delete_org_admin_forbidden(self, client: AsyncClient, orgs_setup):
        """DELETE /organizations/{id} avec admin d'org → 403."""
        response = await client.delete(
            f"/api/v1/organizations/{orgs_setup['org_b'].id}",
            headers=_auth_headers(orgs_setup["admin_a"]),
        )
        assert response.status_code == 403

    async def test_bulk_delete_orgs_admin_forbidden(
        self, client: AsyncClient, orgs_setup
    ):
        """POST /organizations/bulk/delete avec admin d'org → 403."""
        response = await client.post(
            "/api/v1/organizations/bulk/delete",
            json={"organization_ids": [str(orgs_setup["org_b"].id)]},
            headers=_auth_headers(orgs_setup["admin_a"]),
        )
        assert response.status_code == 403


# --- PUT org (route 4) : admin de l'org + isolation -------------------------


class TestUpdateOrganizationMatrix:
    """Route 4 : PUT /organizations/{id} — admin membre ; non-membre → 403."""

    async def test_admin_updates_own_org(self, client: AsyncClient, orgs_setup):
        """Admin de A modifie A → 200."""
        response = await client.put(
            f"/api/v1/organizations/{orgs_setup['org_a'].id}",
            json={"description": "Updated by org admin"},
            headers=_auth_headers(orgs_setup["admin_a"]),
        )
        assert response.status_code == 200, response.text
        assert response.json()["description"] == "Updated by org admin"

    async def test_admin_cannot_update_foreign_org(
        self, client: AsyncClient, orgs_setup
    ):
        """Admin de A modifie B → 403 (isolation)."""
        response = await client.put(
            f"/api/v1/organizations/{orgs_setup['org_b'].id}",
            json={"description": "Should not pass"},
            headers=_auth_headers(orgs_setup["admin_a"]),
        )
        assert response.status_code == 403

    async def test_superuser_updates_any_org(self, client: AsyncClient, orgs_setup):
        """Superuser modifie B → 200 (bypass)."""
        response = await client.put(
            f"/api/v1/organizations/{orgs_setup['org_b'].id}",
            json={"description": "Updated by superuser"},
            headers=_auth_headers(orgs_setup["superuser"]),
        )
        assert response.status_code == 200, response.text


# --- 401 sans token (échantillon) -------------------------------------------


class TestUnauthenticatedAccess:
    """Sécurité : 401 sans token sur un échantillon de routes."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/api/v1/organizations/"),
            ("POST", "/api/v1/organizations/"),
            ("PUT", "/api/v1/organizations/00000000-0000-0000-0000-000000000003"),
            ("DELETE", "/api/v1/organizations/00000000-0000-0000-0000-000000000003"),
        ],
    )
    async def test_routes_require_authentication(
        self, client: AsyncClient, method: str, path: str
    ):
        """Sans Authorization header → 401 (jamais 200/403 anonyme)."""
        response = await client.request(method, path)
        assert response.status_code == 401, response.text
