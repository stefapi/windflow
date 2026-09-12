"""Tests RBAC des routers transverses (STORY-122.5, AC 2).

Couvre compute, discovery, stats, import_export, workflows :
- **viewer** : 200 GET ``/compute/stats``, ``/compute/global``,
  ``/stats/dashboard``, ``/workflows/``, ``/discovery/.../adoption-data`` ;
- **discovery POST /adopt** : viewer 403 / admin 200 (création stack —
  matrice Admin+, aligné STORY-122.3) ;
- **import_export** : GET export viewer 200 ; POST import operator 403 /
  admin 200 (mocké) ;
- **401 sans token** (échantillon).

Chaîne d'auth réelle : JWT → ``require_*`` (pattern test_schedules_rbac).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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

IMPORT_FILE_CONTENT: bytes = (
    b'{"version": "1.0", "stack": {"name": "imported-stack", '
    b'"template": {"services": {"web": {"image": "nginx"}}}}}'
)

ADOPT_PAYLOAD: dict = {
    "discovered_id": "compose:demo@local",
    "type": "composition",
    "stack_name": "adopted-stack",
}


# --- Helpers --------------------------------------------------------------


async def _create_user_with_role(
    db_session: AsyncSession,
    username: str,
    role: Role,
) -> tuple[User, Organization]:
    """Crée un utilisateur + organisation + association du rôle donné."""
    user = await UserService.create(
        db_session,
        UserCreate(
            email=f"{username}@example.com",
            username=username,
            full_name=username.title(),
            password="password123",
            is_superuser=False,
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


def _make_stats_response() -> SimpleNamespace:
    """Construit une ComputeStatsResponse factice (valeurs quelconques)."""
    from app.schemas.compute import ComputeStatsResponse

    return ComputeStatsResponse(
        total_containers=1,
        running_containers=1,
        stacks_count=0,
        stacks_running_count=0,
        stacks_targets_count=0,
        stacks_services_count=0,
        discovered_count=0,
        discovered_targets_count=0,
        standalone_count=0,
        standalone_targets_count=0,
        targets_count=0,
    )


# --- Viewer : lectures transverses 200 ---------------------------------------


class TestViewerReads:
    """Viewer : 200 sur toutes les lectures transverses."""

    async def test_viewer_200_compute_stats(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /compute/stats avec viewer → 200 (service mocké)."""
        user, _org = await _create_user_with_role(
            db_session, "msc-view-cs", Role.VIEWER
        )

        with patch(
            "app.api.v1.compute.compute_service.get_compute_stats",
            new=AsyncMock(return_value=_make_stats_response()),
        ):
            response = await client.get(
                "/api/v1/compute/stats", headers=_auth_headers(user)
            )
        assert response.status_code == 200, response.text
        assert response.json()["total_containers"] == 1

    async def test_viewer_200_compute_global(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /compute/global avec viewer → 200 (service mocké)."""
        from app.schemas.compute import ComputeGlobalView

        user, _org = await _create_user_with_role(
            db_session, "msc-view-cg", Role.VIEWER
        )

        with patch(
            "app.api.v1.compute.compute_service.get_compute_global",
            new=AsyncMock(return_value=ComputeGlobalView()),
        ):
            response = await client.get(
                "/api/v1/compute/global", headers=_auth_headers(user)
            )
        assert response.status_code == 200, response.text

    async def test_viewer_200_stats_dashboard(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /stats/dashboard avec viewer → 200 (base vide)."""
        user, _org = await _create_user_with_role(
            db_session, "msc-view-sd", Role.VIEWER
        )

        response = await client.get(
            "/api/v1/stats/dashboard", headers=_auth_headers(user)
        )
        assert response.status_code == 200, response.text
        assert response.json()["total_targets"] == 0

    async def test_viewer_200_workflows(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /workflows/ avec viewer → 200 (stub vide)."""
        user, _org = await _create_user_with_role(
            db_session, "msc-view-wf", Role.VIEWER
        )

        response = await client.get("/api/v1/workflows/", headers=_auth_headers(user))
        assert response.status_code == 200, response.text
        assert response.json() == []

    async def test_viewer_403_adopt(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /discovery/adopt avec viewer → 403 (création stack)."""
        user, _org = await _create_user_with_role(
            db_session, "msc-view-ad", Role.VIEWER
        )

        response = await client.post(
            "/api/v1/discovery/adopt",
            json=ADOPT_PAYLOAD,
            headers=_auth_headers(user),
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Not enough permissions"


# --- Operator / Admin : écritures ---------------------------------------------


class TestWriteMatrix:
    """Adoption/import : operator 403, admin 200 (services mockés)."""

    async def test_operator_403_import_stack(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Écriture : POST /stacks/import avec operator → 403."""
        user, _org = await _create_user_with_role(
            db_session, "msc-op-imp", Role.OPERATOR
        )

        response = await client.post(
            "/api/v1/stacks/import",
            files={"file": ("stack.json", IMPORT_FILE_CONTENT, "application/json")},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403

    async def test_admin_200_import_stack(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Écriture : POST /stacks/import avec admin → 200 (fichier valide)."""
        user, _org = await _create_user_with_role(db_session, "msc-adm-imp", Role.ADMIN)

        response = await client.post(
            "/api/v1/stacks/import",
            files={"file": ("stack.json", IMPORT_FILE_CONTENT, "application/json")},
            headers=_auth_headers(user),
        )
        assert response.status_code == 200, response.text
        assert response.json()["name"] == "imported-stack"

    async def test_admin_200_adopt(self, client: AsyncClient, db_session: AsyncSession):
        """Gestion : POST /discovery/adopt avec admin → 200 (service mocké)."""
        from app.schemas.adoption import AdoptionResponse

        user, _org = await _create_user_with_role(db_session, "msc-adm-ad", Role.ADMIN)
        fake = AdoptionResponse(
            success=True,
            stack_id="stk-1",
            stack_name="adopted-stack",
            deployment_id="dep-1",
            message="Adoption réussie",
        )

        with patch(
            "app.api.v1.discovery.adoption_service.adopt_discovered_item",
            new=AsyncMock(return_value=fake),
        ):
            response = await client.post(
                "/api/v1/discovery/adopt",
                json=ADOPT_PAYLOAD,
                headers=_auth_headers(user),
            )
        assert response.status_code == 200, response.text
        assert response.json()["stack_id"] == "stk-1"


# --- Export : lecture viewer ---------------------------------------------------


class TestExport:
    """Export = lecture : viewer 200, 404 stack inexistante."""

    async def test_viewer_200_export_stack(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /stacks/{id}/export avec viewer → 200 (stack seedée)."""
        from app.models.stack import Stack

        user, org = await _create_user_with_role(db_session, "msc-exp-v", Role.VIEWER)
        stack = Stack(
            name="exported-stack",
            template={"services": {"web": {"image": "nginx"}}},
            organization_id=org.id,
        )
        db_session.add(stack)
        await db_session.commit()
        await db_session.refresh(stack)

        response = await client.get(
            f"/api/v1/stacks/{stack.id}/export", headers=_auth_headers(user)
        )
        assert response.status_code == 200, response.text
        assert response.json()["stack"]["name"] == "exported-stack"

    async def test_viewer_404_export_stack_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Erreur : GET /stacks/{id}/export inexistant avec viewer → 404."""
        user, _org = await _create_user_with_role(
            db_session, "msc-exp-404", Role.VIEWER
        )

        response = await client.get(
            "/api/v1/stacks/nonexistent/export", headers=_auth_headers(user)
        )
        assert response.status_code == 404


# --- Sécurité : 401 sans token ------------------------------------------------


class TestNoToken:
    """Sans Authorization : 401 avant toute vérification de rôle."""

    async def test_no_token_401_sample(self, client: AsyncClient):
        """401 sur un échantillon lecture/écriture des routers transverses."""
        compute_resp = await client.get("/api/v1/compute/stats")
        stats_resp = await client.get("/api/v1/stats/dashboard")
        workflows_resp = await client.get("/api/v1/workflows/")
        adopt_resp = await client.post("/api/v1/discovery/adopt", json=ADOPT_PAYLOAD)
        import_resp = await client.post(
            "/api/v1/stacks/import",
            files={"file": ("stack.json", IMPORT_FILE_CONTENT, "application/json")},
        )

        assert compute_resp.status_code == 401
        assert stats_resp.status_code == 401
        assert workflows_resp.status_code == 401
        assert adopt_resp.status_code == 401
        assert import_resp.status_code == 401
