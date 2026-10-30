"""Tests API de GET /deployments/{id}/events (STORY-167 — Tâche 6).

Matrice rules 35/40 sur le nouvel endpoint : nominal (séquence ordonnée,
enveloppe ``data`` + ``pagination{}``, filtres), sécurité (401 sans
token, 403 org étrangère, 200 viewer de son org), erreurs (404, 422
domaines fermés / per_page > 100 / date invalide), non-fuite de données
sensibles (rules 40).

Chaîne d'auth réelle : JWT → ``require_viewer`` (pattern
test_deployments_rbac.py) ; déploiements + events insérés directement en
session (pas de pipeline asynchrone).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.enums.rbac import Role
from app.models.deployment import Deployment, DeploymentStatus
from app.models.deployment_event import DeploymentEvent
from app.models.host import Host
from app.models.organization import Organization
from app.models.stack import Stack
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.user_service import UserService

# Horodatages déterministes de la séquence pulling → … → error.
_BASE = datetime(2026, 1, 2, 22, 30, 0)


async def _create_user_with_role(
    db_session: AsyncSession,
    username: str,
    role: Role,
) -> tuple[User, Organization]:
    """Utilisateur + organisation + association du rôle donné."""
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


async def _seed_full_deployment(
    db_session: AsyncSession, org: Organization
) -> Deployment:
    """Déploiement + séquence complète d'events (déroulé chronologique)."""
    stack = Stack(
        name="events-stack",
        template={"image": "nginx"},
        variables={},
        organization_id=org.id,
        version="1.0.0",
    )
    host = Host(
        name="events-host",
        host="127.0.0.1",
        credentials={},
        organization_id=org.id,
    )
    db_session.add_all([stack, host])
    await db_session.commit()

    deployment = Deployment(
        stack_id=stack.id,
        host_id=host.id,
        organization_id=org.id,
        name="events-deployment",
        config={},
        variables={},
        status=DeploymentStatus.FAILED,
        logs="[INFO] start\n[ERROR] boom",
    )
    db_session.add(deployment)
    await db_session.commit()

    sequence = [
        ("deploying", "info", "[INFO] Starting deployment", {"step": 0}),
        ("pulling", "info", "[INFO] Pulling image nginx", {"step": 1}),
        ("deploying", "info", "[INFO] Creating container", {"step": 2}),
        ("error", "error", "[ERROR] Image pull failed", {"step": 3}),
    ]
    db_session.add_all(
        [
            DeploymentEvent(
                deployment_id=deployment.id,
                event_type=event_type,
                level=level,
                message=message,
                data=data,
                created_at=_BASE + timedelta(minutes=i),
            )
            for i, (event_type, level, message, data) in enumerate(sequence)
        ]
    )
    await db_session.commit()
    return deployment


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 122.2."""
    from app.config import settings

    monkeypatch.setattr(settings, "disable_auth", False)
    yield


class TestDeploymentEventsNominal:
    """Cas nominaux : séquence ordonnée, enveloppe, filtres."""

    @pytest.mark.asyncio
    async def test_returns_ordered_sequence_with_envelope(
        self, db_session, admin_client, test_superuser
    ):
        """200 : déroulé complet dans l'ordre, enveloppe data+pagination."""
        org = Organization(name="Nominal Org", slug="nominal-org")
        db_session.add(org)
        await db_session.commit()
        db_session.add(
            UserOrganization(
                user_id=test_superuser.id,
                organization_id=org.id,
                role=Role.ADMIN,
            )
        )
        await db_session.commit()
        deployment = await _seed_full_deployment(db_session, org)

        response = await admin_client.get(f"/api/v1/deployments/{deployment.id}/events")
        assert response.status_code == 200
        # Format wire spec 09 : {"data": [...], "pagination": {...}} —
        # unwrap() retourne directement la liste des items.
        body = response.json()
        items = body["data"]
        assert len(items) == 4
        # Ordre chronologique du déroulé (decision 4) : deploying → pulling
        # → deploying → error.
        assert [item["event_type"] for item in items] == [
            "deploying",
            "pulling",
            "deploying",
            "error",
        ]
        # Champs complets sur chaque event.
        first = items[0]
        for field in (
            "id",
            "deployment_id",
            "event_type",
            "level",
            "message",
            "created_at",
        ):
            assert field in first
        # Enveloppe pagination spec 09.
        pagination = body["pagination"]
        assert pagination["page"] == 1
        assert pagination["per_page"] == 20
        assert pagination["total"] == 4
        assert pagination["pages"] == 1

    @pytest.mark.asyncio
    async def test_filter_event_type(self, db_session, admin_client, test_superuser):
        org = Organization(name="Filter Org", slug="filter-org")
        db_session.add(org)
        await db_session.commit()
        db_session.add(
            UserOrganization(
                user_id=test_superuser.id, organization_id=org.id, role=Role.ADMIN
            )
        )
        await db_session.commit()
        deployment = await _seed_full_deployment(db_session, org)

        response = await admin_client.get(
            f"/api/v1/deployments/{deployment.id}/events",
            params={"event_type": "error"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["pagination"]["total"] == 1
        assert body["data"][0]["event_type"] == "error"
        assert body["data"][0]["level"] == "error"

    @pytest.mark.asyncio
    async def test_filter_level_and_dates(
        self, db_session, admin_client, test_superuser
    ):
        org = Organization(name="Filter2 Org", slug="filter2-org")
        db_session.add(org)
        await db_session.commit()
        db_session.add(
            UserOrganization(
                user_id=test_superuser.id, organization_id=org.id, role=Role.ADMIN
            )
        )
        await db_session.commit()
        deployment = await _seed_full_deployment(db_session, org)

        # Filtre level=info : 3 events (tous sauf l'erreur).
        response = await admin_client.get(
            f"/api/v1/deployments/{deployment.id}/events",
            params={"level": "info"},
        )
        assert response.status_code == 200
        assert response.json()["pagination"]["total"] == 3

        # Filtre after : bornes ISO 8601 inclusives (events à m2 et m3).
        after = (_BASE + timedelta(minutes=2)).isoformat()
        response = await admin_client.get(
            f"/api/v1/deployments/{deployment.id}/events",
            params={"after": after},
        )
        assert response.status_code == 200
        assert response.json()["pagination"]["total"] == 2

    @pytest.mark.asyncio
    async def test_pagination_page2(self, db_session, admin_client, test_superuser):
        org = Organization(name="Page Org", slug="page-org")
        db_session.add(org)
        await db_session.commit()
        db_session.add(
            UserOrganization(
                user_id=test_superuser.id, organization_id=org.id, role=Role.ADMIN
            )
        )
        await db_session.commit()
        deployment = await _seed_full_deployment(db_session, org)

        response = await admin_client.get(
            f"/api/v1/deployments/{deployment.id}/events",
            params={"page": 2, "per_page": 3},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["event_type"] == "error"
        assert body["pagination"]["total"] == 4
        assert body["pagination"]["page"] == 2


class TestDeploymentEventsSecurity:
    """Sécurité rules 40 : 401 / 403 (isolation org) / RBAC viewer+."""

    @pytest.mark.asyncio
    async def test_returns_401_without_token(
        self, client: AsyncClient, db_session, test_organization
    ):
        """Sécurité : pas d'accès sans authentification."""
        deployment = await _seed_full_deployment(db_session, test_organization)
        response = await client.get(f"/api/v1/deployments/{deployment.id}/events")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_403_for_viewer_foreign_org(
        self, client: AsyncClient, db_session
    ):
        """Isolation : un viewer d'une autre org ne voit pas les events."""
        viewer, viewer_org = await _create_user_with_role(
            db_session, "evtviewer", Role.VIEWER
        )
        _, owner_org = await _create_user_with_role(
            db_session, "evtowner", Role.OPERATOR
        )
        deployment = await _seed_full_deployment(db_session, owner_org)

        response = await client.get(
            f"/api/v1/deployments/{deployment.id}/events",
            headers=_auth_headers(viewer),
        )
        assert response.status_code == 403
        assert viewer_org.id != owner_org.id  # sanity : orgs distinctes

    @pytest.mark.asyncio
    async def test_returns_200_for_viewer_own_org(
        self, client: AsyncClient, db_session
    ):
        """RBAC lecture viewer+ : un viewer de l'org du déploiement passe."""
        viewer, viewer_org = await _create_user_with_role(
            db_session, "ownviewer", Role.VIEWER
        )
        deployment = await _seed_full_deployment(db_session, viewer_org)

        response = await client.get(
            f"/api/v1/deployments/{deployment.id}/events",
            headers=_auth_headers(viewer),
        )
        assert response.status_code == 200
        assert response.json()["pagination"]["total"] == 4


class TestDeploymentEventsErrors:
    """Cas d'erreur : 404, 422 (domaines fermés, per_page, dates)."""

    @pytest.mark.asyncio
    async def test_returns_404_unknown_deployment(self, admin_client):
        response = await admin_client.get(
            "/api/v1/deployments/00000000-0000-0000-0000-000000000099/events"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_422_invalid_event_type(
        self, db_session, admin_client, test_superuser
    ):
        org = Organization(name="Err Org", slug="err-org")
        db_session.add(org)
        await db_session.commit()
        deployment = await _seed_full_deployment(db_session, org)

        response = await admin_client.get(
            f"/api/v1/deployments/{deployment.id}/events",
            params={"event_type": "stopped"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_returns_422_invalid_level(self, db_session, admin_client):
        org = Organization(name="Err2 Org", slug="err2-org")
        db_session.add(org)
        await db_session.commit()
        deployment = await _seed_full_deployment(db_session, org)

        response = await admin_client.get(
            f"/api/v1/deployments/{deployment.id}/events",
            params={"level": "critical"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_returns_422_per_page_over_100(self, db_session, admin_client):
        org = Organization(name="Err3 Org", slug="err3-org")
        db_session.add(org)
        await db_session.commit()
        deployment = await _seed_full_deployment(db_session, org)

        response = await admin_client.get(
            f"/api/v1/deployments/{deployment.id}/events",
            params={"per_page": 101},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_returns_422_invalid_date(self, db_session, admin_client):
        org = Organization(name="Err4 Org", slug="err4-org")
        db_session.add(org)
        await db_session.commit()
        deployment = await _seed_full_deployment(db_session, org)

        response = await admin_client.get(
            f"/api/v1/deployments/{deployment.id}/events",
            params={"after": "not-a-date"},
        )
        assert response.status_code == 422


class TestDeploymentEventsNoSensitiveLeak:
    """Rules 40 : aucune clé sensible dans les items (data non sensible)."""

    @pytest.mark.asyncio
    async def test_response_does_not_expose_variables_or_secrets(
        self, db_session, admin_client, test_superuser
    ):
        org = Organization(name="Leak Org", slug="leak-org")
        db_session.add(org)
        await db_session.commit()
        db_session.add(
            UserOrganization(
                user_id=test_superuser.id, organization_id=org.id, role=Role.ADMIN
            )
        )
        await db_session.commit()
        deployment = await _seed_full_deployment(db_session, org)

        response = await admin_client.get(f"/api/v1/deployments/{deployment.id}/events")
        assert response.status_code == 200
        raw = response.json()
        for forbidden in ("variables", "configuration", "password", "secret", "token"):
            assert forbidden not in raw["data"][0]
            for item in raw["data"]:
                assert forbidden not in (item.get("data") or {})
        # organization_id jamais exposé dans la réponse (scoping implicite).
        assert "organization_id" not in raw["data"][0]
