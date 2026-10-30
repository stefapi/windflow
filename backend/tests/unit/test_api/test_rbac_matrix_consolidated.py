"""Matrice RBAC consolidée de bout en bout (STORY-122.7, Tâche 3 — AC 2/AC 5).

Parcours par rôle sur des endpoints réels de chaque famille (fixtures
``viewer_client`` / ``operator_client`` / ``org_admin_client`` / superuser —
Tâche 1), services mockés pour les 200 :

- **viewer** : 403 sur ``DELETE /docker/containers/{id}`` (AC 2 littéral),
  POST /stacks, POST /plugins/install, POST /admin/stacks-management/import,
  POST /organizations ; 200 lectures (GET /docker/containers, /stats/dashboard) ;
- **operator** : 200 POST /docker/containers/{id}/start, POST /deployments ;
  403 DELETE container, POST /stacks, POST /organizations/{id}/users ;
- **admin d'org** : 201 POST /stacks, 201 POST /organizations/{own}/users ;
  403 POST /organizations (création = SA), 403 /admin/* ;
- **super_admin** : 200 /admin/stacks-management/definitions, 201
  POST /organizations ;
- **404/403 ressource étrangère** : stack + target d'une org étrangère ;
- **401** sans token (paramétré, un endpoint par router) ;
- **non-régression** : disable_auth → 200 sans header ; login username ET
  email ; register 201 ; logout 200.

Chaîne d'auth réelle : login JWT → ``require_*`` (résolution rôle global via
``AuthorizationService``, DB de test — pattern suites 122.2-122.6).
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import create_user_with_role, unwrap

from app.auth.jwt import create_access_token
from app.core.cache import reset_role_cache
from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.stack import Stack
from app.models.host import Host
from app.models.user import User

STACK_CREATE_PAYLOAD: dict = {
    "name": "consolidated-matrix-stack",
    "template": {"image": "nginx:latest"},
    "variables": {},
    "target_type": "docker",
}

ADMIN_PREFIX = "/api/v1/admin/stacks-management"


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 122.2."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


@pytest.fixture(autouse=True)
def _fresh_role_cache():
    """Cache de rôles vierge autour de chaque test (pas de fuite entre rôles)."""
    reset_role_cache()
    yield
    reset_role_cache()


def _auth_headers(user: User) -> dict[str, str]:
    """Header JWT direct (sans passer par le login — contrôle fin par test)."""
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_foreign_resources(
    db_session: AsyncSession,
) -> tuple[Organization, Stack, Host]:
    """Organisation étrangère + stack + target (aucun utilisateur commun)."""
    foreign_org = Organization(name="Foreign Org", slug="foreign-org-consolidated")
    db_session.add(foreign_org)
    await db_session.commit()

    stack = Stack(
        name="foreign-stack",
        template={"image": "nginx"},
        variables={},
        organization_id=foreign_org.id,
        version="1.0.0",
    )
    target = Host(
        name="foreign-target",
        host="127.0.0.1",
        credentials={},
        organization_id=foreign_org.id,
    )
    db_session.add_all([stack, target])
    await db_session.commit()
    await db_session.refresh(stack)
    await db_session.refresh(target)
    return foreign_org, stack, target


# ============================================================================
# Viewer : lectures 200, toutes écritures 403
# ============================================================================


class TestViewerMatrix:
    """Viewer : lecture seule stricte sur l'échantillon de chaque famille."""

    async def test_viewer_403_delete_docker_container(self, viewer_client: AsyncClient):
        """AC 2 littéral : DELETE /docker/containers/{id} avec viewer → 403."""
        response = await viewer_client.delete("/api/v1/docker/containers/abc123")
        assert response.status_code == 403
        assert response.json()["error"]["message"] == "Not enough permissions"

    async def test_viewer_403_create_stack(self, viewer_client: AsyncClient):
        """Gestion : POST /stacks avec viewer → 403."""
        response = await viewer_client.post(
            "/api/v1/stacks/", json=STACK_CREATE_PAYLOAD
        )
        assert response.status_code == 403

    async def test_viewer_403_install_plugin(self, viewer_client: AsyncClient):
        """Gestion : POST /plugins/install avec viewer → 403."""
        response = await viewer_client.post(
            "/api/v1/plugins/install", json={"plugin_id": "traefik"}
        )
        assert response.status_code == 403

    async def test_viewer_403_admin_import(self, viewer_client: AsyncClient):
        """Instance : POST /admin/stacks-management/import avec viewer → 403."""
        response = await viewer_client.post(f"{ADMIN_PREFIX}/import", json={})
        assert response.status_code == 403

    async def test_viewer_403_create_organization(self, viewer_client: AsyncClient):
        """Instance : POST /organizations avec viewer → 403 (création = SA)."""
        response = await viewer_client.post(
            "/api/v1/organizations/", json={"name": "Viewer Org"}
        )
        assert response.status_code == 403

    async def test_viewer_200_list_containers(self, viewer_client: AsyncClient):
        """Lecture : GET /docker/containers avec viewer → 200 (Docker mocké)."""
        docker = AsyncMock()
        docker.list_containers.return_value = []
        docker.close = AsyncMock()
        with patch("app.api.v1.docker.get_docker_client", return_value=docker):
            response = await viewer_client.get("/api/v1/docker/containers")
        assert response.status_code == 200, response.text

    async def test_viewer_200_stats_dashboard(self, viewer_client: AsyncClient):
        """Lecture : GET /stats/dashboard avec viewer → 200 (base vide)."""
        response = await viewer_client.get("/api/v1/stats/dashboard")
        assert response.status_code == 200, response.text


# ============================================================================
# Operator : actions opérationnelles 200, gestion 403
# ============================================================================


class TestOperatorMatrix:
    """Operator : opérationnel autorisé, gestion refusée."""

    async def test_operator_204_start_container(self, operator_client: AsyncClient):
        """Opération : POST /docker/containers/{id}/start → 204 (Docker mocké)."""
        docker = AsyncMock()
        docker.close = AsyncMock()
        with patch("app.api.v1.docker.get_docker_client", return_value=docker):
            response = await operator_client.post(
                "/api/v1/docker/containers/abc123/start"
            )
        assert response.status_code == 204, response.text

    async def test_operator_201_create_deployment(
        self,
        operator_client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
    ):
        """Opération : POST /deployments avec operator → 201 (orchestrateur mocké)."""
        stack = Stack(
            name="matrix-op-stack",
            template={"image": "nginx"},
            variables={},
            organization_id=test_organization.id,
            version="1.0.0",
        )
        target = Host(
            name="matrix-op-target",
            host="127.0.0.1",
            credentials={},
            organization_id=test_organization.id,
        )
        db_session.add_all([stack, target])
        await db_session.commit()

        orchestrator = AsyncMock()
        with patch(
            "app.services.deployment_orchestrator.DeploymentOrchestrator.start_deployment",
            orchestrator,
        ):
            response = await operator_client.post(
                "/api/v1/deployments",
                json={
                    "stack_id": str(stack.id),
                    "target_id": str(target.id),
                    "name": "matrix-deployment",
                },
            )
        assert response.status_code == 201, response.text
        orchestrator.assert_awaited_once()

    async def test_operator_403_delete_container(self, operator_client: AsyncClient):
        """Gestion : DELETE /docker/containers/{id} avec operator → 403."""
        response = await operator_client.delete("/api/v1/docker/containers/abc123")
        assert response.status_code == 403

    async def test_operator_403_create_stack(self, operator_client: AsyncClient):
        """Gestion : POST /stacks avec operator → 403."""
        response = await operator_client.post(
            "/api/v1/stacks/", json=STACK_CREATE_PAYLOAD
        )
        assert response.status_code == 403

    async def test_operator_403_add_org_user(
        self, operator_client: AsyncClient, test_organization: Organization
    ):
        """Gestion : POST /organizations/{id}/users avec operator → 403."""
        response = await operator_client.post(
            f"/api/v1/organizations/{test_organization.id}/users",
            json={"user_id": "00000000-0000-0000-0000-000000000000", "role": "viewer"},
        )
        assert response.status_code == 403


# ============================================================================
# Admin d'organisation : gestion 200 dans son org, instance 403
# ============================================================================


class TestOrgAdminMatrix:
    """Admin d'org (non-superuser) : gestion locale OK, instance refusée."""

    async def test_admin_201_create_stack(
        self,
        org_admin_client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
    ):
        """Gestion : POST /stacks avec admin d'org → 201 dans son organisation."""
        response = await org_admin_client.post(
            "/api/v1/stacks/",
            json={**STACK_CREATE_PAYLOAD, "organization_id": str(test_organization.id)},
        )
        assert response.status_code == 201, response.text
        assert unwrap(response)["name"] == STACK_CREATE_PAYLOAD["name"]

    async def test_admin_201_add_org_user(
        self,
        org_admin_client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
    ):
        """Gestion : POST /organizations/{own}/users → 201 (candidat viewer)."""
        candidate = await create_user_with_role(
            db_session, test_organization, Role.VIEWER, suffix="cand"
        )
        # Retirer le lien créé par le helper : le POST recrée l'association
        from app.models.user_organization import UserOrganization

        link = (
            await db_session.execute(
                __import__("sqlalchemy")
                .select(UserOrganization)
                .where(UserOrganization.user_id == candidate.id)
            )
        ).scalar_one()
        await db_session.delete(link)
        await db_session.commit()

        response = await org_admin_client.post(
            f"/api/v1/organizations/{test_organization.id}/users",
            json={"user_id": str(candidate.id), "role": "viewer"},
        )
        assert response.status_code == 201, response.text
        assert unwrap(response)["role"] == "viewer"

    async def test_admin_403_create_organization(self, org_admin_client: AsyncClient):
        """Instance : POST /organizations avec admin d'org → 403 (création = SA)."""
        response = await org_admin_client.post(
            "/api/v1/organizations/", json={"name": "Admin Created Org"}
        )
        assert response.status_code == 403

    async def test_admin_403_admin_sample(self, org_admin_client: AsyncClient):
        """Instance : GET /admin/stacks-management/definitions → 403."""
        response = await org_admin_client.get(f"{ADMIN_PREFIX}/definitions")
        assert response.status_code == 403


# ============================================================================
# Super admin : accès total
# ============================================================================


class TestSuperAdminMatrix:
    """Superuser : admin instance + création d'organisation."""

    async def test_superuser_200_admin_definitions(
        self, admin_client: AsyncClient, tmp_path, monkeypatch
    ):
        """Instance : GET /admin/stacks-management/definitions → 200.

        Répertoire ``stacks_definitions`` substitué (pattern test_admin_rbac).
        """
        import app.api.v1.admin.stacks_management as admin_module

        definitions_dir = tmp_path / "stacks_definitions"
        definitions_dir.mkdir()
        (definitions_dir / "demo.yaml").write_text(
            "metadata:\n"
            "  name: demo\n"
            "  version: 1.0.0\n"
            "  category: demo\n"
            "  description: Demo stack\n"
            "stack:\n"
            "  services:\n"
            "    web:\n"
            "      image: nginx\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            admin_module.Path, "__truediv__", lambda self, other: definitions_dir
        )

        response = await admin_client.get(f"{ADMIN_PREFIX}/definitions")
        assert response.status_code == 200, response.text

    async def test_superuser_201_create_organization(self, admin_client: AsyncClient):
        """Instance : POST /organizations avec superuser → 201."""
        response = await admin_client.post(
            "/api/v1/organizations/", json={"name": "Org By Superuser Matrix"}
        )
        assert response.status_code == 201, response.text


# ============================================================================
# Isolation : ressources d'une organisation étrangère
# ============================================================================


class TestForeignResourcesIsolation:
    """AC 5 : ressource étrangère → 403/404, jamais 200."""

    async def test_org_admin_404_foreign_stack(
        self,
        org_admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Isolation : GET /stacks/{id} d'une org étrangère avec admin d'org
        → 404 (scoping par organisation)."""
        _org, stack, _target = await _seed_foreign_resources(db_session)

        response = await org_admin_client.get(f"/api/v1/stacks/{stack.id}")
        assert response.status_code in (403, 404)
        assert response.status_code != 200

    async def test_org_admin_404_foreign_target(
        self,
        org_admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Isolation : GET /targets/{id} d'une org étrangère → 404."""
        _org, _stack, target = await _seed_foreign_resources(db_session)

        response = await org_admin_client.get(f"/api/v1/targets/{target.id}")
        assert response.status_code in (403, 404)
        assert response.status_code != 200


# ============================================================================
# 401 sans token : échantillon par router (paramétré)
# ============================================================================

NO_TOKEN_SAMPLES: list[tuple[str, str]] = [
    ("GET", "/api/v1/auth/me"),
    ("GET", "/api/v1/users/"),
    ("GET", "/api/v1/organizations/"),
    ("GET", "/api/v1/targets/"),
    ("GET", "/api/v1/stacks/"),
    ("GET", "/api/v1/deployments"),
    ("GET", "/api/v1/docker/containers"),
    ("GET", "/api/v1/schedules"),
    ("GET", "/api/v1/plugins/"),
    ("GET", "/api/v1/registry/plugins"),
    ("GET", f"{ADMIN_PREFIX}/definitions"),
    ("GET", "/api/v1/compute/stats"),
    ("GET", "/api/v1/discovery/composition/demo@local/adoption-data"),
    ("GET", "/api/v1/stats/dashboard"),
    ("GET", "/api/v1/workflows/"),
]


class TestNoTokenParametrized:
    """401 sans Authorization sur un endpoint de chaque router."""

    @pytest.mark.parametrize(
        "method,path", NO_TOKEN_SAMPLES, ids=[p for _m, p in NO_TOKEN_SAMPLES]
    )
    async def test_401_without_token(self, client: AsyncClient, method: str, path: str):
        """Sans token : 401 avant toute vérification de rôle."""
        response = await client.request(method, path)
        assert response.status_code == 401, f"{method} {path} → {response.status_code}"


# ============================================================================
# Non-régression : disable_auth, login, register, logout
# ============================================================================


class TestAuthNonRegression:
    """Garde-fous : les flux auth historiques ne sont pas régressés."""

    async def test_disable_auth_auto_login_superadmin(
        self, client: AsyncClient, monkeypatch, test_superuser: User
    ):
        """disable_auth=True → GET /api/v1/users 200 sans header (auto-login
        superadmin — mode dev préservé, garde-fou §2.G).

        ``test_superuser`` est l'unique superuser de la base isolée du
        test : l'auto-login dev le résout sans token.
        """
        from app.auth import dependencies as auth_deps

        monkeypatch.setattr(auth_deps.settings, "disable_auth", True)
        try:
            response = await client.get("/api/v1/users/")
        finally:
            monkeypatch.setattr(auth_deps.settings, "disable_auth", False)

        assert response.status_code == 200, response.text

    async def test_login_with_username_and_email(
        self, client: AsyncClient, viewer_user: User
    ):
        """Login username ET email → 200 + token (non-régression)."""
        by_username = await client.post(
            "/api/v1/auth/login",
            data={
                "username": viewer_user.username,
                "password": "rolepassword123",
            },
        )
        assert by_username.status_code == 200, by_username.text
        assert "access_token" in unwrap(by_username)

        by_email = await client.post(
            "/api/v1/auth/login",
            data={
                "username": viewer_user.email,
                "password": "rolepassword123",
            },
        )
        assert by_email.status_code == 200, by_email.text
        assert "access_token" in unwrap(by_email)

    async def test_register_201(self, client: AsyncClient, db_session: AsyncSession):
        """Register public → 201 (rattachement org par défaut en viewer)."""
        from app.config import settings
        from app.models.organization import Organization as OrgModel

        default_org = (
            await db_session.execute(
                select(OrgModel).where(OrgModel.slug == settings.default_org_slug)
            )
        ).scalar_one_or_none()
        if default_org is None:
            db_session.add(
                OrgModel(
                    name="Default Org",
                    slug=settings.default_org_slug,
                    description="",
                )
            )
            await db_session.commit()

        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "matrix-newuser@example.com",
                "username": "matrix-newuser",
                "password": "SecurePass123!",
                "full_name": "Matrix New User",
            },
        )
        assert response.status_code == 201, response.text

    async def test_logout_200(self, client: AsyncClient, viewer_user: User):
        """Logout public (révocation best-effort) → 200."""
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": viewer_user.username, "password": "rolepassword123"},
        )
        token = unwrap(login)["access_token"]

        response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
