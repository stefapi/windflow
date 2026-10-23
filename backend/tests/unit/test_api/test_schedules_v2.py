"""Tests API /schedules v2 — spec 17 (STORY-160.1, AC 2).

Extension cohérente de ``test_schedules_rbac.py`` (pattern helpers) :

- **Nominaux** : 201 create (action+trigger_type+timezone), 200 liste
  paginée (enveloppe ``pagination{}``), 200 détail, 200 update, 204
  delete, 200 toggle ;
- **Validation 422** : cron invalide, fuseau inconnu, action hors
  registre, ``event`` sans ``event_name``, body manquant ;
- **Sécurité** (rules 40) : 401 sans token, 403 viewer sur écritures ;
- **404** id inconnu ;
- **Aucun champ sensible** dans les réponses ; parameters non loggés
  bruts (caplog).
"""

import logging

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

from app.auth.jwt import create_access_token
from app.core.cache import reset_role_cache
from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.scheduled_task import ScheduledTask
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.user_service import UserService

# --- Helpers (pattern test_schedules_rbac) ----------------------------------


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
    """Insère une tâche planifiée v2 dans l'organisation donnée."""
    task = ScheduledTask(
        name="seed-task-v2",
        action="host.scan",
        trigger_type="cron",
        cron_expression="0 3 * * *",
        parameters={"target_id": "tgt-seed"},
        enabled=enabled,
        organization_id=org.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


VALID_PAYLOAD_BASE: dict = {
    "name": "scan-nocturne",
    "action": "host.scan",
    "trigger_type": "cron",
    "timezone": "Europe/Paris",
    "error_policy": "retry",
    "cron_expression": "0 3 * * *",
    "parameters": {"target_id": "tgt-42"},
    "enabled": True,
}


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


# --- Nominaux (admin) --------------------------------------------------------


class TestNominalFlows:
    """CRUD complet v2 avec admin."""

    async def test_create_201_with_v2_fields(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """201 : création avec action/trigger_type/timezone/error_policy."""
        user, org = await _create_user_with_role(db_session, "sch2-adm-c", Role.ADMIN)
        response = await client.post(
            "/api/v1/schedules",
            json={**VALID_PAYLOAD_BASE, "organization_id": org.id},
            headers=_auth_headers(user),
        )
        assert response.status_code == 201, response.text
        body = unwrap(response)
        assert body["action"] == "host.scan"
        assert body["trigger_type"] == "cron"
        assert body["timezone"] == "Europe/Paris"
        assert body["error_policy"] == "retry"
        assert body["parameters"] == {"target_id": "tgt-42"}
        # Champ legacy absent des réponses v2.
        assert "task_type" not in body

    async def test_create_event_task_201(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """201 : tâche événement (notification.send + deployment.failed)."""
        user, org = await _create_user_with_role(db_session, "sch2-adm-e", Role.ADMIN)
        response = await client.post(
            "/api/v1/schedules",
            json={
                "name": "notify-failures",
                "action": "notification.send",
                "trigger_type": "event",
                "event_name": "deployment.failed",
                "parameters": {"channel": "webhook", "message": "échec déploy"},
                "organization_id": org.id,
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 201, response.text
        body = unwrap(response)
        assert body["trigger_type"] == "event"
        assert body["event_name"] == "deployment.failed"

    async def test_list_200_paginated_envelope(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """200 : liste avec enveloppe pagination{} (non-régression 128)."""
        user, org = await _create_user_with_role(db_session, "sch2-adm-l", Role.ADMIN)
        await _seed_task(db_session, org)
        response = await client.get("/api/v1/schedules", headers=_auth_headers(user))
        assert response.status_code == 200, response.text
        body = response.json()
        assert "data" in body
        assert "pagination" in body
        assert body["pagination"]["page"] == 1
        assert body["pagination"]["total"] >= 1
        task = body["data"][0]
        assert task["action"] == "host.scan"

    async def test_get_200_detail(self, client: AsyncClient, db_session: AsyncSession):
        """200 : détail complet avec champs v2."""
        user, org = await _create_user_with_role(db_session, "sch2-adm-g", Role.ADMIN)
        task = await _seed_task(db_session, org)
        response = await client.get(
            f"/api/v1/schedules/{task.id}", headers=_auth_headers(user)
        )
        assert response.status_code == 200, response.text
        body = unwrap(response)
        assert body["id"] == task.id
        assert body["trigger_type"] == "cron"

    async def test_update_200(self, client: AsyncClient, db_session: AsyncSession):
        """200 : update partiel — définition fusionnée revalidée."""
        user, org = await _create_user_with_role(db_session, "sch2-adm-u", Role.ADMIN)
        task = await _seed_task(db_session, org)
        response = await client.put(
            f"/api/v1/schedules/{task.id}",
            json={
                "name": "renamed-v2",
                "timezone": "America/Cayenne",
                "error_policy": "disable",
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 200, response.text
        body = unwrap(response)
        assert body["name"] == "renamed-v2"
        assert body["timezone"] == "America/Cayenne"
        assert body["error_policy"] == "disable"
        # Champs non fournis préservés.
        assert body["action"] == "host.scan"

    async def test_delete_204(self, client: AsyncClient, db_session: AsyncSession):
        """204 : suppression admin."""
        user, org = await _create_user_with_role(db_session, "sch2-adm-d", Role.ADMIN)
        task = await _seed_task(db_session, org)
        response = await client.delete(
            f"/api/v1/schedules/{task.id}", headers=_auth_headers(user)
        )
        assert response.status_code == 204

    async def test_toggle_200_operator(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """200 : toggle par operator (matrice RBAC inchangée)."""
        user, org = await _create_user_with_role(db_session, "sch2-op-t", Role.OPERATOR)
        task = await _seed_task(db_session, org, enabled=True)
        response = await client.post(
            f"/api/v1/schedules/{task.id}/toggle", headers=_auth_headers(user)
        )
        assert response.status_code == 200, response.text
        assert unwrap(response)["enabled"] is False


# --- Validation 422 -----------------------------------------------------------


class TestSemanticValidation422:
    """422 VALIDATION_ERROR — validation sémantique spec 17."""

    async def test_create_invalid_cron_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user, org = await _create_user_with_role(db_session, "sch2-v-cron", Role.ADMIN)
        response = await client.post(
            "/api/v1/schedules",
            json={
                **VALID_PAYLOAD_BASE,
                "cron_expression": "not-a-cron",
                "organization_id": org.id,
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_create_unknown_timezone_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user, org = await _create_user_with_role(db_session, "sch2-v-tz", Role.ADMIN)
        response = await client.post(
            "/api/v1/schedules",
            json={
                **VALID_PAYLOAD_BASE,
                "timezone": "Mars/Olympus",
                "organization_id": org.id,
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 422, response.text

    async def test_create_unknown_action_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """AC 1 : action hors registre rejetée en 422 à l'API."""
        user, org = await _create_user_with_role(db_session, "sch2-v-act", Role.ADMIN)
        response = await client.post(
            "/api/v1/schedules",
            json={
                **VALID_PAYLOAD_BASE,
                "action": "rm.rf.everything",
                "organization_id": org.id,
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 422, response.text

    async def test_create_event_without_event_name_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user, org = await _create_user_with_role(db_session, "sch2-v-evt", Role.ADMIN)
        response = await client.post(
            "/api/v1/schedules",
            json={
                **VALID_PAYLOAD_BASE,
                "trigger_type": "event",
                "organization_id": org.id,
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 422, response.text

    async def test_create_non_canonical_event_name_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user, org = await _create_user_with_role(db_session, "sch2-v-env", Role.ADMIN)
        response = await client.post(
            "/api/v1/schedules",
            json={
                **VALID_PAYLOAD_BASE,
                "trigger_type": "event",
                "event_name": "not.an.event",
                "organization_id": org.id,
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 422, response.text

    async def test_create_invalid_parameters_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Parameters rejetés par le schéma de l'action (resource
        'networks' ∉ images|volumes)."""
        user, org = await _create_user_with_role(db_session, "sch2-v-par", Role.ADMIN)
        response = await client.post(
            "/api/v1/schedules",
            json={
                **VALID_PAYLOAD_BASE,
                "action": "compute.docker.prune",
                "parameters": {"resource": "networks"},
                "organization_id": org.id,
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 422, response.text

    async def test_create_missing_body_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user, _ = await _create_user_with_role(db_session, "sch2-v-bdy", Role.ADMIN)
        response = await client.post(
            "/api/v1/schedules", json={}, headers=_auth_headers(user)
        )
        assert response.status_code == 422, response.text

    async def test_update_cannot_break_merged_definition(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Update action sans re-fournir parameters cohérents → 422 :
        la définition fusionnée (host.scan + parameters seed) est
        revalidée ; ici les parameters seed restent valides pour
        host.scan — on vérifie surtout qu'un cron invalide en update
        est rejeté."""
        user, org = await _create_user_with_role(db_session, "sch2-v-upd", Role.ADMIN)
        task = await _seed_task(db_session, org)
        response = await client.put(
            f"/api/v1/schedules/{task.id}",
            json={"cron_expression": "bad-expr"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 422, response.text


# --- Sécurité (rules 40) ------------------------------------------------------


class TestSecurity:
    """401/403/404 + absence de champ sensible."""

    async def test_401_without_token(self, client: AsyncClient):
        response = await client.get("/api/v1/schedules")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_OR_EXPIRED_TOKEN"

    async def test_403_viewer_on_write(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """RBAC inchangé : viewer ne peut pas créer."""
        user, org = await _create_user_with_role(db_session, "sch2-s-view", Role.VIEWER)
        response = await client.post(
            "/api/v1/schedules",
            json={**VALID_PAYLOAD_BASE, "organization_id": org.id},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403
        assert response.json()["error"]["message"] == "Not enough permissions"

    async def test_404_unknown_id(self, client: AsyncClient, db_session: AsyncSession):
        user, _ = await _create_user_with_role(db_session, "sch2-s-404", Role.ADMIN)
        response = await client.get(
            "/api/v1/schedules/does-not-exist", headers=_auth_headers(user)
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    async def test_no_sensitive_fields_in_responses(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Aucun champ sensible (password/token/secret) dans la réponse."""
        user, org = await _create_user_with_role(db_session, "sch2-s-fld", Role.ADMIN)
        await _seed_task(db_session, org)
        response = await client.get("/api/v1/schedules", headers=_auth_headers(user))
        assert response.status_code == 200
        raw = response.text.lower()
        for forbidden in ("password", "token", "secret", "credential"):
            assert forbidden not in raw, f"Champ sensible exposé : {forbidden}"

    async def test_parameters_not_logged_raw(
        self, client: AsyncClient, db_session: AsyncSession, caplog
    ):
        """Rules 40 : les parameters ne sont jamais loggés bruts
        (valeur target_id absente des logs applicatifs)."""
        user, org = await _create_user_with_role(db_session, "sch2-s-log", Role.ADMIN)
        sentinel = "tgt-TOPSECRET-42"
        with caplog.at_level(logging.INFO, logger="app.services.scheduler_service"):
            response = await client.post(
                "/api/v1/schedules",
                json={
                    **VALID_PAYLOAD_BASE,
                    "parameters": {"target_id": sentinel},
                    "organization_id": org.id,
                },
                headers=_auth_headers(user),
            )
        assert response.status_code == 201, response.text
        assert (
            sentinel not in caplog.text
        ), "Les parameters bruts ne doivent pas figurer dans les logs"
