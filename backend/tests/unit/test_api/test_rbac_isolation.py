"""Tests d'isolation organisationnelle croisée (STORY-122.3, AC 4).

**AC 4** : un utilisateur n'accède pas aux ressources d'une organisation à
laquelle il n'appartient pas (``403``/``404`` selon la matrice) — vérifié
sur un échantillon représentatif (stacks, deployments, targets).

Setup : 2 organisations (A et B) + utilisateurs :
- ``admin-A`` : admin **dans A uniquement** ;
- ``viewer-B`` : viewer dans B uniquement (contrôle du scoping listes) ;
- ``superuser`` : bypass — accès partout (``is_member`` superuser).

Ressources : stack/deployment/target dans A **et** dans B.

Assertion clé : « pas 200 » sur toute ressource étrangère (403 sur les
détails/actions via ``is_member``, listes scopées sans fuite via le
scoping STORY-121.3).

Note divergence story : la route ``POST /stacks/{id}/deploy`` citée en AC 4
n'existe pas — le déploiement passe par ``POST /deployments`` (stack_id en
body) : le test d'isolation porte sur cette route réelle, avec le check
``is_member`` sur la stack référencée introduit par 122.3.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

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


async def _seed_org_resources(
    db_session: AsyncSession, org: Organization, suffix: str
) -> tuple[Stack, Target, Deployment]:
    """Insère stack + target + deployment dans l'organisation donnée."""
    stack = Stack(
        name=f"stack-{suffix}",
        template={"image": "nginx"},
        variables={},
        organization_id=org.id,
        version="1.0.0",
    )
    target = Target(
        name=f"target-{suffix}",
        host="127.0.0.1",
        credentials={},
        organization_id=org.id,
    )
    db_session.add_all([stack, target])
    await db_session.commit()

    deployment = Deployment(
        stack_id=stack.id,
        target_id=target.id,
        organization_id=org.id,
        name=f"deployment-{suffix}",
        config={},
        variables={},
        status=DeploymentStatus.RUNNING,
    )
    db_session.add(deployment)
    await db_session.commit()
    await db_session.refresh(deployment)
    return stack, target, deployment


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
async def isolation_setup(db_session: AsyncSession):
    """Seed complet : org A + org B, admin-A, viewer-B, ressources A et B."""
    org_a = await _create_org(db_session, "Org Alpha")
    org_b = await _create_org(db_session, "Org Beta")

    admin_a = await _create_user_in_org(db_session, "admin-alpha", org_a, Role.ADMIN)
    viewer_b = await _create_user_in_org(db_session, "viewer-beta", org_b, Role.VIEWER)

    stack_a, target_a, deployment_a = await _seed_org_resources(
        db_session, org_a, "alpha"
    )
    stack_b, target_b, deployment_b = await _seed_org_resources(
        db_session, org_b, "beta"
    )

    return {
        "org_a": org_a,
        "org_b": org_b,
        "admin_a": admin_a,
        "viewer_b": viewer_b,
        "stack_a": stack_a,
        "stack_b": stack_b,
        "target_a": target_a,
        "target_b": target_b,
        "deployment_a": deployment_a,
        "deployment_b": deployment_b,
    }


# --- AC 4 : cross-organisation -----------------------------------------------


class TestCrossOrganizationIsolation:
    """AC 4 : rôle suffisant ≠ accès aux ressources d'une autre org."""

    async def test_admin_org_a_cannot_read_stack_of_org_b(
        self, client: AsyncClient, isolation_setup
    ):
        """GET /stacks/{stack_B} avec admin-A → 403 (pas 200)."""
        response = await client.get(
            f"/api/v1/stacks/{isolation_setup['stack_b'].id}",
            headers=_auth_headers(isolation_setup["admin_a"]),
        )
        assert response.status_code == 403

    async def test_admin_org_a_cannot_deploy_stack_of_org_b(
        self, client: AsyncClient, isolation_setup
    ):
        """POST /deployments (stack_B) avec admin-A → 403 (pas 200).

        Divergence story : la route ``POST /stacks/{id}/deploy`` n'existe
        pas — le déploiement réel passe par ``POST /deployments`` avec le
        stack_id en body. Le check d'isolation sur la stack référencée a
        été introduit par 122.3 (AC 4).
        """
        response = await client.post(
            "/api/v1/deployments",
            json={
                "stack_id": isolation_setup["stack_b"].id,
                "target_id": isolation_setup["target_b"].id,
                "name": "cross-org-deployment",
            },
            headers=_auth_headers(isolation_setup["admin_a"]),
        )
        assert response.status_code == 403

    async def test_admin_org_a_cannot_read_deployment_of_org_b(
        self, client: AsyncClient, isolation_setup
    ):
        """GET /deployments/{deployment_B} avec admin-A → pas 200 (403)."""
        response = await client.get(
            f"/api/v1/deployments/{isolation_setup['deployment_b'].id}",
            headers=_auth_headers(isolation_setup["admin_a"]),
        )
        assert response.status_code != 200
        assert response.status_code == 403

    async def test_admin_org_a_cannot_delete_deployment_of_org_b(
        self, client: AsyncClient, isolation_setup
    ):
        """DELETE /deployments/{deployment_B} avec admin-A → 403 (pas 200)."""
        response = await client.delete(
            f"/api/v1/deployments/{isolation_setup['deployment_b'].id}",
            headers=_auth_headers(isolation_setup["admin_a"]),
        )
        assert response.status_code == 403

    async def test_admin_org_a_cannot_read_target_of_org_b(
        self, client: AsyncClient, isolation_setup
    ):
        """GET /targets/{target_B} avec admin-A → pas 200 (404 si le
        détail est scopé par requête, 403 via check explicite)."""
        response = await client.get(
            f"/api/v1/targets/{isolation_setup['target_b'].id}",
            headers=_auth_headers(isolation_setup["admin_a"]),
        )
        assert response.status_code != 200

    async def test_user_without_membership_gets_404_list_scoped(
        self, client: AsyncClient, isolation_setup
    ):
        """Listes scopées : GET /stacks d'admin-A ne contient AUCUNE
        ressource de B (scoping 121.3 non régressé).

        StackSummaryResponse n'expose pas organization_id : identification
        par id des stacks seedées.
        """
        response = await client.get(
            "/api/v1/stacks/", headers=_auth_headers(isolation_setup["admin_a"])
        )
        assert response.status_code == 200
        stacks = unwrap(response)
        stack_ids = {s["id"] for s in stacks}
        assert (
            isolation_setup["stack_b"].id not in stack_ids
        ), "Fuite de la stack de l'org B dans la liste d'admin-A"
        # Et les ressources de A sont bien présentes
        assert isolation_setup["stack_a"].id in stack_ids

    async def test_viewer_org_b_list_contains_no_org_a_resources(
        self, client: AsyncClient, isolation_setup
    ):
        """Contrôle croisé : GET /deployments de viewer-B ne contient que B
        (identification par id — DeploymentResponse n'expose pas org ;
        contrat paginé STORY-128 : liste sous ``data``)."""
        response = await client.get(
            "/api/v1/deployments", headers=_auth_headers(isolation_setup["viewer_b"])
        )
        assert response.status_code == 200
        items = response.json()["data"]
        item_ids = {i["id"] for i in items}
        assert isolation_setup["deployment_a"].id not in item_ids
        assert isolation_setup["deployment_b"].id in item_ids


# --- Superuser : bypass toutes organisations ---------------------------------


class TestSuperuserAccessesAllOrgs:
    """Superuser : 200 partout (is_member bypass, spec 08)."""

    async def test_superuser_accesses_all_orgs(
        self, client: AsyncClient, db_session: AsyncSession, isolation_setup
    ):
        """Superuser lit les ressources des orgs A ET B (200)."""
        superuser = await UserService.create(
            db_session,
            UserCreate(
                email="super@example.com",
                username="super-everywhere",
                full_name="Super User",
                password="password123",
                is_superuser=True,
            ),
        )
        headers = _auth_headers(superuser)

        stack_b_resp = await client.get(
            f"/api/v1/stacks/{isolation_setup['stack_b'].id}", headers=headers
        )
        deployment_b_resp = await client.get(
            f"/api/v1/deployments/{isolation_setup['deployment_b'].id}", headers=headers
        )

        assert stack_b_resp.status_code == 200, stack_b_resp.text
        assert deployment_b_resp.status_code == 200, deployment_b_resp.text
