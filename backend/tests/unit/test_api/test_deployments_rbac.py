"""Tests RBAC du router deployments (STORY-122.3, AC 2 volet deployments).

Matrice rôle × endpoint conforme à la spec 08 — deployments = ressources
d'organisation : rôle global via ``require_role`` + isolation via les
checks ``is_member`` existants (l. 284/422 avant 122.3, conservés).

Couverture (échantillon GET/POST/DELETE) :
- **viewer** : 200 sur ``GET /deployments`` (liste scopée) et
  ``GET /deployments/{id}`` (déploiement de son org), 403 sur ``DELETE`` ;
- **operator** : 200 sur ``POST /deployments`` (stack de son org,
  orchestrator mocké), 403 sur ``PUT`` ;
- **admin** : 204 sur ``DELETE /deployments/{id}`` (déploiement de son
  org, sans container → pas d'E/S Docker) ;
- **401 sans token** (échantillon).

Chaîne d'auth réelle : JWT → ``require_*`` (pattern test_docker_rbac).
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.core.cache import reset_role_cache
from app.enums.rbac import Role
from app.models.deployment import Deployment, DeploymentStatus
from app.models.organization import Organization
from app.models.stack import Stack
from app.models.target import Target
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.user_service import UserService
from tests.conftest import unwrap

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


async def _seed_stack_target(
    db_session: AsyncSession, org: Organization
) -> tuple[Stack, Target]:
    """Insère une stack et une target dans l'organisation donnée."""
    stack = Stack(
        name=f"stack-{org.slug}",
        template={"image": "nginx"},
        variables={},
        organization_id=org.id,
        version="1.0.0",
    )
    target = Target(
        name=f"target-{org.slug}",
        host="127.0.0.1",
        credentials={},
        organization_id=org.id,
    )
    db_session.add_all([stack, target])
    await db_session.commit()
    return stack, target


async def _seed_deployment(
    db_session: AsyncSession,
    org: Organization,
    stack: Stack,
    target: Target,
    status: DeploymentStatus = DeploymentStatus.RUNNING,
) -> Deployment:
    """Insère un déploiement sans lancer la tâche asynchrone (pattern 103.3)."""
    deployment = Deployment(
        stack_id=stack.id,
        target_id=target.id,
        organization_id=org.id,
        name=f"deployment-{org.slug}",
        config={},
        variables={},
        status=status,
    )
    db_session.add(deployment)
    await db_session.commit()
    await db_session.refresh(deployment)
    return deployment


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
    """Viewer : 200 lectures / 403 suppression."""

    async def test_viewer_200_list_deployments(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /deployments avec viewer → 200 (liste scopée)."""
        user, org = await _create_user_with_role(db_session, "dep-view-l", Role.VIEWER)
        stack, target = await _seed_stack_target(db_session, org)
        deployment = await _seed_deployment(db_session, org, stack, target)

        response = await client.get("/api/v1/deployments", headers=_auth_headers(user))
        assert response.status_code == 200
        body = unwrap(response)
        assert body["total"] == 1
        # DeploymentResponse n'expose pas organization_id : identification
        # par id (le seed n'a créé qu'un seul déploiement, dans son org).
        assert body["items"][0]["id"] == deployment.id

    async def test_viewer_200_get_deployment(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /deployments/{id} avec viewer → 200 (son org)."""
        user, org = await _create_user_with_role(db_session, "dep-view-g", Role.VIEWER)
        stack, target = await _seed_stack_target(db_session, org)
        deployment = await _seed_deployment(db_session, org, stack, target)

        response = await client.get(
            f"/api/v1/deployments/{deployment.id}", headers=_auth_headers(user)
        )
        assert response.status_code == 200
        assert unwrap(response)["id"] == deployment.id

    async def test_viewer_403_delete_deployment(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : DELETE /deployments/{id} avec viewer → 403."""
        user, _ = await _create_user_with_role(db_session, "dep-view-d", Role.VIEWER)
        response = await client.delete(
            "/api/v1/deployments/990e8400-e29b-41d4-a716-446655440000",
            headers=_auth_headers(user),
        )
        assert response.status_code == 403
        assert response.json()["error"]["message"] == "Not enough permissions"


# --- Operator : création OK, gestion 403 --------------------------------------


class TestOperatorMatrix:
    """Operator : 200 création / 403 gestion."""

    async def test_operator_201_create_deployment(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Opération : POST /deployments avec operator → 201 (orchestrateur mocké)."""
        user, org = await _create_user_with_role(db_session, "dep-op-c", Role.OPERATOR)
        stack, target = await _seed_stack_target(db_session, org)

        orchestrator = AsyncMock()
        with patch(
            "app.services.deployment_orchestrator.DeploymentOrchestrator.start_deployment",
            orchestrator,
        ):
            response = await client.post(
                "/api/v1/deployments",
                json={
                    "stack_id": stack.id,
                    "target_id": target.id,
                    "name": "op-deployment",
                },
                headers=_auth_headers(user),
            )

        assert response.status_code == 201, response.text
        orchestrator.assert_awaited_once()
        assert unwrap(response)["name"] == "op-deployment"

    async def test_operator_403_update_deployment(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : PUT /deployments/{id} avec operator → 403."""
        user, _ = await _create_user_with_role(db_session, "dep-op-u", Role.OPERATOR)
        response = await client.put(
            "/api/v1/deployments/990e8400-e29b-41d4-a716-446655440000",
            json={"name": "forbidden"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403


# --- Admin : gestion OK dans son organisation -------------------------------


class TestAdminMatrix:
    """Admin : 204 suppression (déploiement de son org, sans container)."""

    async def test_admin_204_delete_deployment(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : DELETE /deployments/{id} avec admin → 204."""
        user, org = await _create_user_with_role(db_session, "dep-adm-d", Role.ADMIN)
        stack, target = await _seed_stack_target(db_session, org)
        deployment = await _seed_deployment(db_session, org, stack, target)

        response = await client.delete(
            f"/api/v1/deployments/{deployment.id}", headers=_auth_headers(user)
        )
        assert response.status_code == 204


# --- Sécurité : 401 sans token ------------------------------------------------


class TestNoToken:
    """Sans Authorization : 401 avant toute vérification de rôle."""

    async def test_no_token_401_sample(self, client: AsyncClient):
        """401 sur un échantillon lecture/opération/gestion."""
        read_resp = await client.get("/api/v1/deployments")
        op_resp = await client.post("/api/v1/deployments", json={})
        adm_resp = await client.delete(
            "/api/v1/deployments/990e8400-e29b-41d4-a716-446655440000"
        )

        assert read_resp.status_code == 401
        assert op_resp.status_code == 401
        assert adm_resp.status_code == 401
