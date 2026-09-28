"""Tests RBAC du router stacks (STORY-122.3, AC 2 volet stacks).

Matrice rôle × endpoint conforme à la spec 08 (cf. story § Contexte
technique) — les stacks sont des ressources **d'organisation** : le rôle
global s'applique via ``require_role`` + l'isolation par organisation via
les checks existants (``is_member``, scoping 121.3).

Couverture :
- **viewer** : 200 sur ``GET /stacks`` (liste scopée), 403 sur
  ``POST /stacks``, ``PUT /stacks/{id}``, ``DELETE /stacks/{id}`` ;
- **operator** : 200 sur les actions opérationnelles (``POST /stacks/{id}/start``
  avec Docker mocké), 403 sur la gestion (``POST /stacks``,
  ``DELETE /stacks/{id}``) ;
- **admin** : 201 sur ``POST /stacks`` (dans son organisation) ;
- **401 sans token** (échantillon).

Stratégie : les assertions 403/401 portent sur le statut HTTP **avant
toute E/S** (le socle ``require_role`` court-circuite la requête). Les
tests 200 mockent Docker (``DockerClientService``) ou n'en dépendent pas.

Chaîne d'auth réelle : JWT ``create_access_token`` → ``get_current_user``
→ ``get_current_active_user`` → ``require_*`` (pattern test_docker_rbac).
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
from tests.conftest import unwrap

STACK_CREATE_PAYLOAD_BASE: dict = {
    "name": "rbac-test-stack",
    "template": {"image": "nginx:latest"},
    "variables": {},
    "target_type": "docker",
}


# --- Helpers --------------------------------------------------------------


async def _create_user_with_role(
    db_session: AsyncSession,
    username: str,
    role: Role,
    is_superuser: bool = False,
) -> tuple[User, Organization]:
    """Crée un utilisateur + organisation + association du rôle donné."""
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
    org = Organization(name=f"Org {username}", slug=f"org-{username}")
    db_session.add(org)
    await db_session.commit()
    db_session.add(UserOrganization(user_id=user.id, organization_id=org.id, role=role))
    await db_session.commit()
    return user, org


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


# --- Viewer : lectures OK, gestion 403 --------------------------------------


class TestViewerMatrix:
    """Viewer : 200 lectures / 403 gestion."""

    async def test_viewer_200_list_stacks(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /stacks avec viewer → 200 (liste scopée, vide OK)."""
        user, _ = await _create_user_with_role(db_session, "stk-view-list", Role.VIEWER)
        response = await client.get("/api/v1/stacks/", headers=_auth_headers(user))
        assert response.status_code == 200
        assert isinstance(unwrap(response), list)

    async def test_viewer_403_create_stack(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /stacks avec viewer → 403."""
        user, org = await _create_user_with_role(db_session, "stk-view-c", Role.VIEWER)
        response = await client.post(
            "/api/v1/stacks/",
            json={**STACK_CREATE_PAYLOAD_BASE, "organization_id": org.id},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403
        assert response.json()["error"]["message"] == "Not enough permissions"

    async def test_viewer_403_update_stack(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : PUT /stacks/{id} avec viewer → 403."""
        user, _ = await _create_user_with_role(db_session, "stk-view-u", Role.VIEWER)
        response = await client.put(
            "/api/v1/stacks/550e8400-e29b-41d4-a716-446655440000",
            json={"name": "forbidden"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403

    async def test_viewer_403_delete_stack(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : DELETE /stacks/{id} avec viewer → 403."""
        user, _ = await _create_user_with_role(db_session, "stk-view-d", Role.VIEWER)
        response = await client.delete(
            "/api/v1/stacks/550e8400-e29b-41d4-a716-446655440000",
            headers=_auth_headers(user),
        )
        assert response.status_code == 403


# --- Operator : actions opérationnelles OK, gestion 403 ----------------------


class TestOperatorMatrix:
    """Operator : 200 actions opérationnelles / 403 gestion."""

    async def test_operator_200_start_stack(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Opération : POST /stacks/{id}/start avec operator → 200 (Docker mocké)."""
        from unittest.mock import AsyncMock, patch

        from app.models.stack import Stack

        user, org = await _create_user_with_role(
            db_session, "stk-op-start", Role.OPERATOR
        )
        stack = Stack(
            name="op-stack",
            template={"image": "nginx"},
            variables={},
            organization_id=org.id,
            version="1.0.0",
        )
        db_session.add(stack)
        await db_session.commit()

        docker = AsyncMock()
        docker.ping.return_value = True
        docker.list_containers.return_value = []
        docker.close = AsyncMock()

        with patch("app.api.v1.stacks.DockerClientService", return_value=docker):
            response = await client.post(
                f"/api/v1/stacks/{stack.id}/start", headers=_auth_headers(user)
            )

        assert response.status_code == 200, response.text
        assert unwrap(response)["success"] is True

    async def test_operator_403_create_stack(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /stacks avec operator → 403."""
        user, org = await _create_user_with_role(db_session, "stk-op-c", Role.OPERATOR)
        response = await client.post(
            "/api/v1/stacks/",
            json={**STACK_CREATE_PAYLOAD_BASE, "organization_id": org.id},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403

    async def test_operator_403_delete_stack(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : DELETE /stacks/{id} avec operator → 403."""
        user, _ = await _create_user_with_role(db_session, "stk-op-d", Role.OPERATOR)
        response = await client.delete(
            "/api/v1/stacks/550e8400-e29b-41d4-a716-446655440000",
            headers=_auth_headers(user),
        )
        assert response.status_code == 403


# --- Admin : gestion OK dans son organisation -------------------------------


class TestAdminMatrix:
    """Admin : 201 création dans son organisation."""

    async def test_admin_201_create_stack(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /stacks avec admin → 201 (org primaire)."""
        from sqlalchemy import select as _select

        from app.models.stack import Stack as _Stack

        user, org = await _create_user_with_role(db_session, "stk-adm-c", Role.ADMIN)
        response = await client.post(
            "/api/v1/stacks/",
            json={**STACK_CREATE_PAYLOAD_BASE, "organization_id": org.id},
            headers=_auth_headers(user),
        )
        assert response.status_code == 201, response.text
        assert unwrap(response)["name"] == STACK_CREATE_PAYLOAD_BASE["name"]

        # La stack créée est rangée dans l'organisation de l'utilisateur
        # (vérifiée en persistance — StackSummaryResponse n'expose pas org).
        created = (
            await db_session.execute(
                _select(_Stack).where(_Stack.name == STACK_CREATE_PAYLOAD_BASE["name"])
            )
        ).scalar_one()
        assert created.organization_id == org.id


# --- Sécurité : 401 sans token ------------------------------------------------


class TestNoToken:
    """Sans Authorization : 401 avant toute vérification de rôle."""

    async def test_no_token_401_sample(self, client: AsyncClient):
        """401 sur un échantillon lecture/opération/gestion."""
        read_resp = await client.get("/api/v1/stacks/")
        op_resp = await client.post("/api/v1/stacks/abc/start")
        adm_resp = await client.post(
            "/api/v1/stacks/",
            json={**STACK_CREATE_PAYLOAD_BASE, "organization_id": "whatever"},
        )

        assert read_resp.status_code == 401
        assert op_resp.status_code == 401
        assert adm_resp.status_code == 401
