"""Tests API exécutions /schedules (STORY-161 — Tâche 9, AC 2).

Couvre les 4 nouvelles routes : liste par tâche, vue globale filtrable,
détail avec journal, run manuel 202. Sécurité rules 40 (401/403/422/404),
isolation organisationnelle via le filtre ``organization_id`` (pattern
liste existante), pagination scopusée, non-régression des 6 routes
historiques (comptage de routes du router — AC 5).

Patterns : helpers ``test_schedules_v2.py`` (création utilisateur+org+role,
JWT direct, fixture ``_jwt_mode``), moteur injecté par override de la
dépendance ``get_scheduler_engine`` (base de test).
"""

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

from app.api.v1 import schedules as schedules_module
from app.api.v1.schedules import router as schedules_router
from app.auth.jwt import create_access_token
from app.core.cache import reset_role_cache
from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.scheduled_task import ScheduledTask
from app.models.scheduled_task_execution import ScheduledTaskExecution
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.scheduler_engine import SchedulerEngine
from app.services.scheduler_execution_store import DatabaseExecutionStore
from app.services.user_service import UserService

# --- Helpers (pattern test_schedules_v2) --------------------------------------


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
    task = ScheduledTask(
        name="exec-test-task",
        action="host.scan",
        trigger_type="cron",
        cron_expression="0 3 * * *",
        parameters={"target_id": "tgt-exec"},
        enabled=enabled,
        organization_id=org.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


async def _seed_execution(
    db_session: AsyncSession,
    task_id: str,
    *,
    status: str = "success",
    triggered_by: str = "cron",
    age_seconds: float = 0,
) -> ScheduledTaskExecution:
    """Insère une ligne d'exécution close (started_at triable)."""
    now = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    execution = ScheduledTaskExecution(
        task_id=task_id,
        status=status,
        triggered_by=triggered_by,
        started_at=now,
        finished_at=now + timedelta(seconds=1),
        duration_seconds=1.0,
        error="boom" if status == "failed" else None,
        logs=json.dumps(
            [
                {
                    "timestamp": now.isoformat(),
                    "message": f"queued (triggered_by={triggered_by})",
                },
                {"timestamp": now.isoformat(), "message": "running"},
            ]
        ),
        created_at=now,
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)
    return execution


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
def engine(test_session_factory):
    """Moteur branché sur le store DB de la base de test (override dépendance)."""
    from app.config import Settings
    from app.main import app

    engine = SchedulerEngine(
        Settings(_env_file=None, scheduler_tick_seconds=30),
        store=DatabaseExecutionStore(session_factory=test_session_factory),
        session_factory=test_session_factory,
        retry_backoff_base=0.0,
    )
    app.dependency_overrides[schedules_module.get_scheduler_engine] = lambda: engine
    yield engine
    app.dependency_overrides.pop(schedules_module.get_scheduler_engine, None)


# --- Nominaux --------------------------------------------------------------------


class TestListPerTask:
    async def test_200_paginated_envelope_no_logs(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """200 : enveloppe pagination{}, tri started_at DESC, items sans logs."""
        user, org = await _create_user_with_role(db_session, "exe-adm-l", Role.ADMIN)
        task = await _seed_task(db_session, org)
        await _seed_execution(db_session, task.id, status="success")
        await _seed_execution(db_session, task.id, status="failed", age_seconds=60)

        response = await client.get(
            f"/api/v1/schedules/{task.id}/executions", headers=_auth_headers(user)
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "pagination" in body
        assert body["pagination"]["total"] == 2
        items = body["data"]
        assert len(items) == 2
        # Tri DESC : la plus récente (success, age 0) d'abord.
        assert items[0]["status"] == "success"
        assert items[1]["status"] == "failed"
        # Items de liste légers : pas de journal.
        assert "logs" not in items[0]

    async def test_404_unknown_task(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user, _ = await _create_user_with_role(db_session, "exe-adm-404", Role.ADMIN)
        response = await client.get(
            "/api/v1/schedules/nope/executions", headers=_auth_headers(user)
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"


class TestGlobalView:
    async def test_200_filters(self, client: AsyncClient, db_session: AsyncSession):
        """Vue globale : filtres status/triggered_by/task_id combinés."""
        user, org = await _create_user_with_role(db_session, "exe-adm-g", Role.ADMIN)
        task = await _seed_task(db_session, org)
        await _seed_execution(db_session, task.id, status="failed", triggered_by="cron")
        await _seed_execution(
            db_session, task.id, status="success", triggered_by="manual"
        )

        response = await client.get(
            "/api/v1/schedules/executions",
            params={"status": "failed", "triggered_by": "cron"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["pagination"]["total"] == 1
        assert body["data"][0]["status"] == "failed"

    async def test_200_date_filters(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """started_after/before ISO 8601 bornent la fenêtre."""
        user, org = await _create_user_with_role(db_session, "exe-adm-d", Role.ADMIN)
        task = await _seed_task(db_session, org)
        await _seed_execution(db_session, task.id, age_seconds=3600)
        await _seed_execution(db_session, task.id, age_seconds=0)

        now = datetime.now(timezone.utc)
        response = await client.get(
            "/api/v1/schedules/executions",
            params={"started_after": (now - timedelta(minutes=30)).isoformat()},
            headers=_auth_headers(user),
        )
        assert response.status_code == 200, response.text
        assert response.json()["pagination"]["total"] == 1

    async def test_200_organization_isolation(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Isolation : les exécutions d'une autre org n'apparaissent pas
        via le filtre organization_id (pattern liste existante)."""
        user_a, org_a = await _create_user_with_role(
            db_session, "exe-iso-a", Role.ADMIN
        )
        user_b, org_b = await _create_user_with_role(
            db_session, "exe-iso-b", Role.ADMIN
        )
        task_a = await _seed_task(db_session, org_a)
        task_b = await _seed_task(db_session, org_b)
        await _seed_execution(db_session, task_a.id)
        await _seed_execution(db_session, task_b.id)

        response = await client.get(
            "/api/v1/schedules/executions",
            params={"organization_id": org_a.id},
            headers=_auth_headers(user_a),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["pagination"]["total"] == 1
        assert body["data"][0]["task_id"] == task_a.id

    async def test_422_invalid_filter_values(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Domaines fermés : status/triggered_by hors domaine → 422."""
        user, _ = await _create_user_with_role(db_session, "exe-adm-v", Role.ADMIN)
        for params in (
            {"status": "exploded"},
            {"triggered_by": "schedule"},  # contrat moteur ≠ spec 06
            {"started_after": "not-a-date"},
        ):
            response = await client.get(
                "/api/v1/schedules/executions",
                params=params,
                headers=_auth_headers(user),
            )
            assert response.status_code == 422, params

    async def test_per_page_bounded(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """per_page ≤ 100 : au-delà → 422 (pattern 128)."""
        user, _ = await _create_user_with_role(db_session, "exe-adm-p", Role.ADMIN)
        response = await client.get(
            "/api/v1/schedules/executions",
            params={"per_page": 101},
            headers=_auth_headers(user),
        )
        assert response.status_code == 422


class TestDetail:
    async def test_200_with_logs(self, client: AsyncClient, db_session: AsyncSession):
        """Détail : statut, triggered_by, duration, error, journal complet."""
        user, org = await _create_user_with_role(db_session, "exe-adm-t", Role.ADMIN)
        task = await _seed_task(db_session, org)
        execution = await _seed_execution(db_session, task.id, status="failed")

        response = await client.get(
            f"/api/v1/schedules/executions/{execution.id}",
            headers=_auth_headers(user),
        )
        assert response.status_code == 200, response.text
        body = unwrap(response)
        assert body["status"] == "failed"
        assert body["triggered_by"] == "cron"
        assert body["duration_seconds"] == 1.0
        assert body["error"] == "boom"  # version assainie persistée
        assert isinstance(body["logs"], list) and len(body["logs"]) == 2
        assert set(body["logs"][0]) == {"timestamp", "message"}

    async def test_404_unknown_execution(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user, _ = await _create_user_with_role(db_session, "exe-adm-404e", Role.ADMIN)
        response = await client.get(
            "/api/v1/schedules/executions/unknown-id",
            headers=_auth_headers(user),
        )
        assert response.status_code == 404


class TestManualRun:
    async def test_202_manual_execution_created(
        self, client: AsyncClient, db_session: AsyncSession, engine, monkeypatch
    ):
        """202 : exécution queued triggered_by=manual créée (fire-and-forget)."""
        import app.services.action_registry as action_registry_module
        from app.services.action_registry import get_action

        async def handler(params: dict) -> None:
            return None

        definition = replace(get_action("host.scan"), handler=handler)
        monkeypatch.setitem(action_registry_module._REGISTRY, "host.scan", definition)

        user, org = await _create_user_with_role(db_session, "exe-op-r", Role.OPERATOR)
        task = await _seed_task(db_session, org)

        response = await client.post(
            f"/api/v1/schedules/{task.id}/run", headers=_auth_headers(user)
        )
        assert response.status_code == 202, response.text
        body = unwrap(response)
        assert body["status"] == "queued"
        assert body["triggered_by"] == "manual"

        # La ligne manual est persistée et consultable.
        rows = (
            (
                await db_session.execute(
                    select(ScheduledTaskExecution).where(
                        ScheduledTaskExecution.task_id == task.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert any(
            e.triggered_by == "manual" for e in rows
        ), "exécution manual non persistée"

    async def test_404_unknown_or_disabled_task(
        self, client: AsyncClient, db_session: AsyncSession, engine
    ):
        user, org = await _create_user_with_role(
            db_session, "exe-op-404", Role.OPERATOR
        )
        await _seed_task(db_session, org, enabled=False)
        disabled = (await db_session.execute(select(ScheduledTask))).scalars().one()
        response = await client.post(
            f"/api/v1/schedules/{disabled.id}/run", headers=_auth_headers(user)
        )
        assert response.status_code == 404
        response = await client.post(
            "/api/v1/schedules/ghost/run", headers=_auth_headers(user)
        )
        assert response.status_code == 404

    async def test_audit_emitted_without_parameters(
        self, client: AsyncClient, db_session: AsyncSession, engine, caplog, monkeypatch
    ):
        """Audit schedule.manual_run émis, sans parameters bruts (rules 40)."""
        import app.services.action_registry as action_registry_module
        from app.models.audit_log import AuditLog
        from app.services.action_registry import get_action

        async def handler(params: dict) -> None:
            return None

        monkeypatch.setitem(
            action_registry_module._REGISTRY,
            "host.scan",
            replace(get_action("host.scan"), handler=handler),
        )
        user, org = await _create_user_with_role(db_session, "exe-op-a", Role.OPERATOR)
        task = await _seed_task(db_session, org)

        await client.post(
            f"/api/v1/schedules/{task.id}/run", headers=_auth_headers(user)
        )
        entries = (await db_session.execute(select(AuditLog))).scalars().all()
        manual_runs = [e for e in entries if e.action == "schedule.manual_run"]
        assert manual_runs, "audit schedule.manual_run absent"
        details = manual_runs[0].details or {}
        assert "tgt-exec" not in json.dumps(details), "parameters bruts dans l'audit"
        assert details.get("name") == "exec-test-task"


# --- Sécurité (rules 40) -----------------------------------------------------------


class TestSecurity:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/api/v1/schedules/executions"),
            ("GET", "/api/v1/schedules/executions/some-id"),
            ("GET", "/api/v1/schedules/some-task/executions"),
            ("POST", "/api/v1/schedules/some-task/run"),
        ],
    )
    async def test_401_without_token(self, client: AsyncClient, method: str, path: str):
        response = await client.request(method, path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_OR_EXPIRED_TOKEN"

    async def test_403_viewer_on_run(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Run manuel = operator : viewer → 403."""
        user, org = await _create_user_with_role(db_session, "exe-view-r", Role.VIEWER)
        task = await _seed_task(db_session, org)
        response = await client.post(
            f"/api/v1/schedules/{task.id}/run", headers=_auth_headers(user)
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    async def test_viewer_can_read(self, client: AsyncClient, db_session: AsyncSession):
        """Lecture : viewer autorisé sur les 3 routes de consultation."""
        user, org = await _create_user_with_role(db_session, "exe-view-c", Role.VIEWER)
        task = await _seed_task(db_session, org)
        execution = await _seed_execution(db_session, task.id)
        for path in (
            "/api/v1/schedules/executions",
            f"/api/v1/schedules/executions/{execution.id}",
            f"/api/v1/schedules/{task.id}/executions",
        ):
            response = await client.get(path, headers=_auth_headers(user))
            assert response.status_code == 200, path

    async def test_error_is_sanitized_version(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_session_factory,
    ):
        """error de la réponse = version assainie persistée par le store
        (tronquée à l'écriture — jamais de stack brute côté API)."""
        user, org = await _create_user_with_role(db_session, "exe-view-e", Role.VIEWER)
        task = await _seed_task(db_session, org)
        store = DatabaseExecutionStore(session_factory=test_session_factory)
        execution_id = await store.mark_queued(task.id, "schedule")
        await store.mark_running(execution_id)
        await store.mark_failed(execution_id, "ValueError: " + "x" * 3000)

        response = await client.get(
            f"/api/v1/schedules/executions/{execution_id}",
            headers=_auth_headers(user),
        )
        assert response.status_code == 200
        error = unwrap(response)["error"]
        assert error is not None
        assert error.endswith("...")
        assert len(error) <= 2000
        assert "Traceback" not in error


# --- Non-régression (AC 5) ------------------------------------------------------------


class TestNonRegression:
    def test_historical_routes_unchanged(self):
        """Les 6 routes historiques + 4 nouvelles = 10 routes au router,
        chemins/méthodes historiques inchangés (garde-fou AC 5)."""
        historical = {
            ("GET", "/schedules"),
            ("GET", "/schedules/{task_id}"),
            ("POST", "/schedules"),
            ("PUT", "/schedules/{task_id}"),
            ("DELETE", "/schedules/{task_id}"),
            ("POST", "/schedules/{task_id}/toggle"),
        }
        current = {
            (list(route.methods)[0], route.path) for route in schedules_router.routes
        }
        assert historical <= current
        assert len(current) == 10

    async def test_schedules_crud_still_works(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Non-régression fonctionnelle : GET /schedules répond toujours."""
        user, _ = await _create_user_with_role(db_session, "exe-nr-l", Role.ADMIN)
        response = await client.get("/api/v1/schedules", headers=_auth_headers(user))
        assert response.status_code == 200
        assert "pagination" in response.json()
