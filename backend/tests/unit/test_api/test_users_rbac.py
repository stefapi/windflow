"""Tests RBAC du router users (STORY-122.4, matrice spec 08).

Couverture (AC 2 volet users) :
- Lectures (GET /, GET /{id}) : ``viewer`` minimum, scoping existant
  conservé (superusers voient tout, sinon organisations partagées) ;
- Écritures (POST/PUT/DELETE + bulk) : ``super_admin`` uniquement —
  operator et admin d'org → 403 ;
- 401 sans token (échantillon), 404 user inexistant.

Setup : org A + admin-A (admin d'org, non superuser), operator-A,
viewer-A (cible), superuser.
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
async def users_setup(db_session: AsyncSession):
    """Seed : org A, admin-A, operator-A, viewer-A (cible), superuser."""
    org_a = await _create_org(db_session, "Org Echo")

    admin_a = await _create_user_in_org(db_session, "usr-admin-echo", org_a, Role.ADMIN)
    operator_a = await _create_user_in_org(
        db_session, "usr-operator-echo", org_a, Role.OPERATOR
    )
    viewer_a = await _create_user_in_org(
        db_session, "usr-viewer-echo", org_a, Role.VIEWER
    )
    superuser = await UserService.create(
        db_session,
        UserCreate(
            email="super-users-rbac@example.com",
            username="super-users-rbac",
            full_name="Super Users Rbac",
            password="password123",
            is_superuser=True,
        ),
    )
    return {
        "org_a": org_a,
        "admin_a": admin_a,
        "operator_a": operator_a,
        "viewer_a": viewer_a,
        "superuser": superuser,
    }


# --- Lectures : viewer minimum ----------------------------------------------


class TestUsersReadMatrix:
    """Routes 1-3 : GET /users — viewer minimum, scoping conservé."""

    async def test_viewer_lists_users_in_own_org(
        self, client: AsyncClient, users_setup
    ):
        """Viewer membre → 200 (liste scopée à ses organisations)."""
        response = await client.get(
            "/api/v1/users/",
            headers=_auth_headers(users_setup["viewer_a"]),
        )
        assert response.status_code == 200, response.text

    async def test_viewer_reads_user_sharing_org(
        self, client: AsyncClient, users_setup
    ):
        """Viewer lit un user de la même org (isolation 121.3 passe) → 200."""
        response = await client.get(
            f"/api/v1/users/{users_setup['operator_a'].id}",
            headers=_auth_headers(users_setup["viewer_a"]),
        )
        assert response.status_code == 200, response.text

    async def test_get_user_404_unknown(self, client: AsyncClient, users_setup):
        """User inexistant → 404."""
        response = await client.get(
            "/api/v1/users/00000000-0000-0000-0000-000000000004",
            headers=_auth_headers(users_setup["superuser"]),
        )
        assert response.status_code == 404


# --- Écritures : super_admin uniquement --------------------------------------


class TestUsersWriteMatrix:
    """Routes 4-8 : POST/PUT/DELETE/bulk — super_admin seulement."""

    async def test_operator_cannot_create_user(self, client: AsyncClient, users_setup):
        """POST /users avec operator → 403."""
        response = await client.post(
            "/api/v1/users/",
            json={
                "email": "new-user-echo@example.com",
                "username": "new-user-echo",
                "full_name": "New User Echo",
                "password": "password123",
                "organization_id": str(users_setup["org_a"].id),
            },
            headers=_auth_headers(users_setup["operator_a"]),
        )
        assert response.status_code == 403

    async def test_admin_cannot_create_user(self, client: AsyncClient, users_setup):
        """POST /users avec admin d'org (non superuser) → 403."""
        response = await client.post(
            "/api/v1/users/",
            json={
                "email": "new-user-echo2@example.com",
                "username": "new-user-echo2",
                "full_name": "New User Echo2",
                "password": "password123",
                "organization_id": str(users_setup["org_a"].id),
            },
            headers=_auth_headers(users_setup["admin_a"]),
        )
        assert response.status_code == 403

    async def test_superuser_creates_user(self, client: AsyncClient, users_setup):
        """POST /users avec superuser → 201."""
        response = await client.post(
            "/api/v1/users/",
            json={
                "email": "created-by-super@example.com",
                "username": "created-by-super",
                "full_name": "Created By Super",
                "password": "password123",
                "organization_id": str(users_setup["org_a"].id),
            },
            headers=_auth_headers(users_setup["superuser"]),
        )
        assert response.status_code == 201, response.text

    async def test_operator_cannot_update_user(self, client: AsyncClient, users_setup):
        """PUT /users/{id} avec operator → 403."""
        response = await client.put(
            f"/api/v1/users/{users_setup['viewer_a'].id}",
            json={"full_name": "Hacked Name"},
            headers=_auth_headers(users_setup["operator_a"]),
        )
        assert response.status_code == 403

    async def test_admin_cannot_delete_user(self, client: AsyncClient, users_setup):
        """DELETE /users/{id} avec admin d'org → 403."""
        response = await client.delete(
            f"/api/v1/users/{users_setup['viewer_a'].id}",
            headers=_auth_headers(users_setup["admin_a"]),
        )
        assert response.status_code == 403

    async def test_admin_cannot_bulk_delete(self, client: AsyncClient, users_setup):
        """POST /users/bulk/delete avec admin d'org → 403."""
        response = await client.post(
            "/api/v1/users/bulk/delete",
            json={"user_ids": [str(users_setup["viewer_a"].id)]},
            headers=_auth_headers(users_setup["admin_a"]),
        )
        assert response.status_code == 403

    async def test_admin_cannot_bulk_assign_organization(
        self, client: AsyncClient, users_setup
    ):
        """POST /users/bulk/assign-organization avec admin d'org → 403."""
        response = await client.post(
            "/api/v1/users/bulk/assign-organization",
            json={
                "user_ids": [str(users_setup["viewer_a"].id)],
                "organization_id": str(users_setup["org_a"].id),
            },
            headers=_auth_headers(users_setup["admin_a"]),
        )
        assert response.status_code == 403

    async def test_update_user_404_unknown(self, client: AsyncClient, users_setup):
        """PUT user inexistant → 404 (superuser passe le rôle)."""
        response = await client.put(
            "/api/v1/users/00000000-0000-0000-0000-000000000005",
            json={"full_name": "Ghost"},
            headers=_auth_headers(users_setup["superuser"]),
        )
        assert response.status_code == 404

    async def test_delete_user_404_unknown(self, client: AsyncClient, users_setup):
        """DELETE user inexistant → 404."""
        response = await client.delete(
            "/api/v1/users/00000000-0000-0000-0000-000000000006",
            headers=_auth_headers(users_setup["superuser"]),
        )
        assert response.status_code == 404


# --- 401 sans token (échantillon) -------------------------------------------


class TestUnauthenticatedAccess:
    """Sécurité : 401 sans token sur un échantillon de routes."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/api/v1/users/"),
            ("POST", "/api/v1/users/"),
            ("PUT", "/api/v1/users/00000000-0000-0000-0000-000000000007"),
            ("DELETE", "/api/v1/users/00000000-0000-0000-0000-000000000007"),
        ],
    )
    async def test_routes_require_authentication(
        self, client: AsyncClient, method: str, path: str
    ):
        """Sans Authorization header → 401 (jamais 200/403 anonyme)."""
        response = await client.request(method, path)
        assert response.status_code == 401, response.text
