"""Émissions d'événements canoniques ``host.*`` sur ``/api/v1/hosts``
(STORY-166.2, AC 2 — complément ``test_canonical_event_emitters.py``).

Couverture exigée par la story :

- POST ``/hosts/`` → ``host.added`` (payload ``{host_id, name,
  organization_id}`` — sans secret) ;
- DELETE ``/hosts/{id}`` → ``host.removed`` (revalidé sur canonique) ;
- POST ``/hosts/{id}/health-check`` avec host ONLINE devenu injoignable
  → ``host.offline`` (via ``HostService.check_health`` — transition
  online→offline uniquement) ;
- émission best-effort : un échec du bus n'altère **pas** la réponse
  API (create/delete restent 201/204) ;
- émissions identiques via l'alias ``/targets`` (handlers partagés —
  test croisé léger : host.added émis une seule fois par création,
  quelle que soit la surface appelée).

Bus espion : pattern ``SpyBus`` de ``test_canonical_event_emitters.py``
(factory ``get_event_bus`` patchée — les émetteurs importent la factory
au point d'émission).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

from app.auth.jwt import create_access_token
from app.core.cache import reset_role_cache
from app.core.events import Event, EventType, InMemoryEventBus
from app.enums.host import HostProfile
from app.enums.rbac import Role
from app.models.host import Host
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.host_service import HostService
from app.services.user_service import UserService


class SpyBus(InMemoryEventBus):
    """Bus in-memory collectant tous les événements publiés."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[Event] = []

    async def publish(self, event: Event) -> None:
        self.events.append(event)
        await super().publish(event)

    def of_type(self, event_type: EventType) -> list[Event]:
        return [e for e in self.events if e.event_type is event_type]


@pytest.fixture
def spy_bus():
    """Bus espion patché comme valeur de retour de la factory."""
    bus = SpyBus()
    with patch("app.core.events.get_event_bus", return_value=bus):
        yield bus


async def _make_admin(
    db_session: AsyncSession, username: str
) -> tuple[User, Organization]:
    user = await UserService.create(
        db_session,
        UserCreate(
            email=f"{username}@example.com",
            username=username,
            full_name=username.title(),
            password="StrongPass123!x",
        ),
    )
    org = Organization(name=f"org-{username}", slug=f"org-{username}")
    db_session.add(org)
    await db_session.flush()
    db_session.add(
        UserOrganization(user_id=user.id, organization_id=org.id, role=Role.ADMIN)
    )
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(org)
    return user, org


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_online_host(
    db_session: AsyncSession, org: Organization, name: str = "evt-host"
) -> Host:
    host = Host(
        name=name,
        host="127.0.0.1",
        port=59999,  # fermé → probe OFFLINE
        profile=HostProfile.HOST_BAREMETAL,
        status="online",  # transition online→offline attendue
        credentials={},
        organization_id=org.id,
    )
    db_session.add(host)
    await db_session.commit()
    await db_session.refresh(host)
    return host


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


@pytest.fixture(autouse=True)
def _fresh_role_cache():
    reset_role_cache()
    yield
    reset_role_cache()


CREATE_PAYLOAD: dict[str, Any] = {
    "name": "events-host",
    "host": "127.0.0.1",
    "port": 22,
    "credentials": {"auth_method": "local"},
}


class TestHostAdded:
    """POST /hosts/ → host.added (payload sans secret)."""

    async def test_create_emits_host_added(
        self, client: AsyncClient, db_session: AsyncSession, spy_bus: SpyBus
    ):
        user, org = await _make_admin(db_session, "evt-added")

        with patch(
            "app.api.v1.hosts.crud.HostService.check_health",
            new=AsyncMock(return_value=None),
        ):
            response = await client.post(
                "/api/v1/hosts/",
                json={**CREATE_PAYLOAD, "organization_id": str(org.id)},
                headers=_auth_headers(user),
            )
        assert response.status_code == 201, response.text
        host_id = unwrap(response)["id"]

        added = spy_bus.of_type(EventType.HOST_ADDED)
        assert len(added) == 1
        payload = added[0].payload
        assert payload["host_id"] == host_id
        assert payload["name"] == CREATE_PAYLOAD["name"]
        assert payload["organization_id"] == str(org.id)
        # Règle 40 : aucun secret dans le payload
        flattened = str(payload).lower()
        for forbidden in ("password", "private_key", "credentials", "passphrase"):
            assert forbidden not in flattened, forbidden

    async def test_alias_create_emits_host_added_once(
        self, client: AsyncClient, db_session: AsyncSession, spy_bus: SpyBus
    ):
        """Création via l'alias /targets → même événement host.added (handler
        partagé, un seul émetteur — pas de doublon d'émission)."""
        user, org = await _make_admin(db_session, "evt-added-alias")

        with patch(
            "app.api.v1.hosts.crud.HostService.check_health",
            new=AsyncMock(return_value=None),
        ):
            response = await client.post(
                "/api/v1/targets/",
                json={
                    **CREATE_PAYLOAD,
                    "name": "alias-events-host",
                    "organization_id": str(org.id),
                },
                headers=_auth_headers(user),
            )
        assert response.status_code == 201, response.text
        assert len(spy_bus.of_type(EventType.HOST_ADDED)) == 1


class TestHostRemoved:
    """DELETE /hosts/{id} → host.removed."""

    async def test_delete_emits_host_removed(
        self, client: AsyncClient, db_session: AsyncSession, spy_bus: SpyBus
    ):
        user, org = await _make_admin(db_session, "evt-removed")
        host = await _seed_online_host(db_session, org, name="removed-host")

        with patch(
            "app.api.v1.hosts.crud.AuditService.log_from_request",
            new=AsyncMock(),
        ):
            response = await client.delete(
                f"/api/v1/hosts/{host.id}", headers=_auth_headers(user)
            )
        assert response.status_code == 204, response.text

        removed = spy_bus.of_type(EventType.HOST_REMOVED)
        assert len(removed) == 1
        assert removed[0].payload["host_id"] == str(host.id)
        assert "password" not in str(removed[0].payload).lower()


class TestHostOffline:
    """POST /hosts/{id}/health-check → host.offline (via HostService)."""

    async def test_health_check_offline_transition_emits_host_offline(
        self, client: AsyncClient, db_session: AsyncSession, spy_bus: SpyBus
    ):
        """Host ONLINE → port fermé : health-check → OFFLINE + host.offline."""
        user, org = await _make_admin(db_session, "evt-offline")
        host = await _seed_online_host(db_session, org)

        # check_health réel : port 59999 fermé → OFFLINE (timeout court
        # pour ne pas ralentir la suite)
        with patch.object(HostService, "HEALTH_CHECK_TIMEOUT", 0.2):
            response = await client.post(
                f"/api/v1/hosts/{host.id}/health-check",
                headers=_auth_headers(user),
            )
        assert response.status_code == 200, response.text
        detail = unwrap(response)
        assert detail["status"] == "offline"
        assert detail["host_id"] == str(host.id)
        assert detail["target_id"] == str(host.id)  # alias legacy conservé

        offline = spy_bus.of_type(EventType.HOST_OFFLINE)
        assert len(offline) == 1
        assert offline[0].payload["host_id"] == str(host.id)

    async def test_no_offline_event_when_staying_offline(
        self, client: AsyncClient, db_session: AsyncSession, spy_bus: SpyBus
    ):
        """Déjà OFFLINE → pas de nouvel événement (anti-spam transition)."""
        user, org = await _make_admin(db_session, "evt-offline-2")
        host = await _seed_online_host(db_session, org, name="already-offline")
        host.status = "offline"  # déjà injoignable
        db_session.add(host)
        await db_session.commit()

        with patch.object(HostService, "HEALTH_CHECK_TIMEOUT", 0.2):
            response = await client.post(
                f"/api/v1/hosts/{host.id}/health-check",
                headers=_auth_headers(user),
            )
        assert response.status_code == 200
        assert spy_bus.of_type(EventType.HOST_OFFLINE) == []


class TestBestEffortEmission:
    """Échec du bus n'altère jamais la réponse API."""

    async def test_create_succeeds_when_bus_fails(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user, org = await _make_admin(db_session, "evt-busfail")

        failing_bus = AsyncMock()
        failing_bus.emit = AsyncMock(side_effect=RuntimeError("bus down"))

        with patch(
            "app.api.v1.hosts.crud.HostService.check_health",
            new=AsyncMock(return_value=None),
        ), patch("app.core.events.get_event_bus", return_value=failing_bus):
            response = await client.post(
                "/api/v1/hosts/",
                json={**CREATE_PAYLOAD, "organization_id": str(org.id)},
                headers=_auth_headers(user),
            )
        assert response.status_code == 201, response.text  # best-effort

    async def test_delete_succeeds_when_bus_fails(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user, org = await _make_admin(db_session, "evt-busfail-d")
        host = await _seed_online_host(db_session, org, name="busfail-del")

        failing_bus = AsyncMock()
        failing_bus.emit = AsyncMock(side_effect=RuntimeError("bus down"))

        with patch(
            "app.api.v1.hosts.crud.AuditService.log_from_request", new=AsyncMock()
        ), patch("app.core.events.get_event_bus", return_value=failing_bus):
            response = await client.delete(
                f"/api/v1/hosts/{host.id}", headers=_auth_headers(user)
            )
        assert response.status_code == 204, response.text
