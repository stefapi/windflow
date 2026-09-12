"""Tests RBAC du router schedules (STORY-122.3, AC 2 volet schedules).

Matrice spec 08 : schedules = gestion d'automatisation → Admin+ ;
activation/toggle = action opérationnelle → Operator+ ; lectures → Viewer.

Couverture :
- **viewer** : 200 ``GET /schedules`` (liste), 403 ``POST /schedules`` ;
- **operator** : 200 ``POST /schedules/{task_id}/toggle`` + 403
  ``POST /schedules`` ;
- **admin** : 201 ``POST /schedules``, 200 ``PUT``, 204 ``DELETE`` ;
- **401 sans token** (échantillon).

Chaîne d'auth réelle : JWT → ``require_*`` (pattern test_docker_rbac).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.core.cache import reset_role_cache
from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.scheduled_task import ScheduledTask, TaskType
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.user_service import UserService

TASK_PAYLOAD_BASE: dict = {
    "name": "rbac-cleanup",
    "task_type": "cleanup_logs",
    "cron_expression": "0 3 * * *",
    "parameters": {},
    "enabled": True,
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


async def _seed_task(
    db_session: AsyncSession, org: Organization, enabled: bool = True
) -> ScheduledTask:
    """Insère une tâche planifiée dans l'organisation donnée."""
    task = ScheduledTask(
        name="seed-task",
        task_type=TaskType.CLEANUP_LOGS,
        cron_expression="0 3 * * *",
        parameters={},
        enabled=enabled,
        organization_id=org.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


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
    """Viewer : 200 lectures / 403 création."""

    async def test_viewer_200_list_schedules(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /schedules avec viewer → 200."""
        user, org = await _create_user_with_role(db_session, "sch-view-l", Role.VIEWER)
        await _seed_task(db_session, org)

        response = await client.get("/api/v1/schedules", headers=_auth_headers(user))
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_viewer_403_create_schedule(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /schedules avec viewer → 403."""
        user, org = await _create_user_with_role(db_session, "sch-view-c", Role.VIEWER)
        response = await client.post(
            "/api/v1/schedules",
            json={**TASK_PAYLOAD_BASE, "organization_id": org.id},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Not enough permissions"


# --- Operator : toggle OK, gestion 403 --------------------------------------


class TestOperatorMatrix:
    """Operator : 200 toggle / 403 création."""

    async def test_operator_200_toggle_schedule(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Opération : POST /schedules/{task_id}/toggle avec operator → 200."""
        user, org = await _create_user_with_role(db_session, "sch-op-t", Role.OPERATOR)
        task = await _seed_task(db_session, org, enabled=True)

        response = await client.post(
            f"/api/v1/schedules/{task.id}/toggle", headers=_auth_headers(user)
        )
        assert response.status_code == 200, response.text
        assert response.json()["enabled"] is False

    async def test_operator_403_create_schedule(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /schedules avec operator → 403."""
        user, org = await _create_user_with_role(db_session, "sch-op-c", Role.OPERATOR)
        response = await client.post(
            "/api/v1/schedules",
            json={**TASK_PAYLOAD_BASE, "organization_id": org.id},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403


# --- Admin : CRUD OK ---------------------------------------------------------


class TestAdminMatrix:
    """Admin : 201 création, 200 update, 204 suppression."""

    async def test_admin_201_create_schedule(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /schedules avec admin → 201."""
        user, org = await _create_user_with_role(db_session, "sch-adm-c", Role.ADMIN)
        response = await client.post(
            "/api/v1/schedules",
            json={**TASK_PAYLOAD_BASE, "organization_id": org.id},
            headers=_auth_headers(user),
        )
        assert response.status_code == 201, response.text
        assert response.json()["name"] == TASK_PAYLOAD_BASE["name"]

    async def test_admin_200_update_schedule(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : PUT /schedules/{task_id} avec admin → 200."""
        user, org = await _create_user_with_role(db_session, "sch-adm-u", Role.ADMIN)
        task = await _seed_task(db_session, org)

        response = await client.put(
            f"/api/v1/schedules/{task.id}",
            json={"name": "renamed-task"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 200, response.text
        assert response.json()["name"] == "renamed-task"

    async def test_admin_204_delete_schedule(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : DELETE /schedules/{task_id} avec admin → 204."""
        user, org = await _create_user_with_role(db_session, "sch-adm-d", Role.ADMIN)
        task = await _seed_task(db_session, org)

        response = await client.delete(
            f"/api/v1/schedules/{task.id}", headers=_auth_headers(user)
        )
        assert response.status_code == 204


# --- Sécurité : 401 sans token ------------------------------------------------


class TestNoToken:
    """Sans Authorization : 401 avant toute vérification de rôle."""

    async def test_no_token_401_sample(self, client: AsyncClient):
        """401 sur un échantillon lecture/opération/gestion."""
        read_resp = await client.get("/api/v1/schedules")
        op_resp = await client.post("/api/v1/schedules/some-task/toggle")
        adm_resp = await client.post("/api/v1/schedules", json={})

        assert read_resp.status_code == 401
        assert op_resp.status_code == 401
        assert adm_resp.status_code == 401
