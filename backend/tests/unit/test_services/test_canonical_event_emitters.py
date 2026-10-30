"""Tests d'émission des événements canoniques par les émetteurs réels
(STORY-162, T4-T7 — AC 3).

Échantillon représentatif exigé par l'AC 3 :

- ``container.created|started|stopped|removed`` (``api/v1/docker.py``) —
  endpoints réels, Docker client mocké (pattern ``test_docker_rbac``),
  bus espion ;
- ``host.added``/``host.removed`` (``api/v1/hosts/crud.py``) —
  endpoints réels, payloads **sans credentials** (règle 40) ;
- ``plugin.installed``/``plugin.removed`` (plugin manager) — publication
  bus vérifiée via ``_publish_to_bus`` (best-effort, jamais bloquant) ;
- ``host.offline`` (``target_service.check_health``) — transition
  joignable→injoignable uniquement ;
- ``deployment.succeeded`` (mapping) couvert par
  ``test_deployment_events.py`` ; ici : ``stack.deployed`` émis au
  succès RUNNING d'un déploiement de stack (mock bus).

Bus espion : ``SpyBus`` (InMemoryEventBus + collecteur) patché comme
valeur de ``app.core.events.get_event_bus`` — les émetteurs importent la
factory au point d'émission (``from ..core.events import get_event_bus``).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.core.events import Event, EventType, InMemoryEventBus
from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
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


# ===========================================================================
# Helpers utilisateurs/rôles (pattern test_docker_rbac / test_targets_rbac)
# ===========================================================================


async def _make_admin(
    db_session: AsyncSession, username: str
) -> tuple[User, Organization]:
    """Crée un admin + organisation + association (pattern conftest)."""
    user = await UserService.create(
        db_session,
        UserCreate(
            email=f"{username}@example.com",
            username=username,
            password="StrongPass123!x",
            full_name=username.title(),
        ),
    )
    user.role = Role.ADMIN
    db_session.add(user)
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


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — herméticité locale."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


def _docker_client_mock() -> AsyncMock:
    """Client Docker mocké (AsyncMock direct, pattern test_docker_rbac)."""
    docker = AsyncMock()
    docker.create_container.return_value = "new-container-id"
    detail = SimpleNamespace(
        id="new-container-id",
        name="/my-container",
        created="2026-10-23T12:00:00Z",
        path="echo",
        args=[],
        state={"Status": "created", "Running": False},
        image="nginx:latest",
        config={},
        host_config={},
        network_settings={},
        mounts=[],
    )
    docker.get_container.return_value = detail
    return docker


# ===========================================================================
# T6 — container.* (api/v1/docker.py)
# ===========================================================================


async def test_create_container_emits_container_created(spy_bus):
    """create_container (fonction endpoint réelle) → container.created.

    Appel direct de la fonction endpoint : le périmètre de ce test est
    l'émission d'event (T6), pas le chemin HTTP — désormais couvert par
    ``test_container_create.py`` et ``test_docker_rbac.py`` depuis la
    correction BUG-003 (``response_model=ContainerDetailResponse``,
    contrat aligné sur l'objet réellement retourné).
    """
    from types import SimpleNamespace

    from app.api.v1.docker import create_container
    from app.schemas.docker import ContainerCreateRequest

    docker = _docker_client_mock()
    request = SimpleNamespace(state=SimpleNamespace(correlation_id=None))
    user = SimpleNamespace(id=str(uuid4()))

    with patch("app.api.v1.docker.get_docker_client", return_value=docker):
        await create_container(
            request=request,
            container_data=ContainerCreateRequest(
                name="my-container", image="nginx:latest"
            ),
            current_user=user,  # type: ignore[arg-type]
        )

    created = spy_bus.of_type(EventType.CONTAINER_CREATED)
    assert len(created) == 1
    payload = created[0].payload
    assert payload["container_id"] == "new-container-id"
    assert payload["name"] == "my-container"
    assert payload["image"] == "nginx:latest"
    # Payload minimal : pas d'env/labels (règle 40)
    assert "env" not in payload and "labels" not in payload


async def test_start_stop_remove_emit_canonical_events(client, db_session, spy_bus):
    """start/stop/remove → container.started/stopped/removed, une fois chacun."""
    user, _ = await _make_admin(db_session, "docker-ops-admin")
    docker = _docker_client_mock()

    with patch("app.api.v1.docker.get_docker_client", return_value=docker), patch(
        "app.api.v1.docker.AuditService.log_from_request", new=AsyncMock()
    ):
        headers = _auth_headers(user)
        r1 = await client.post(
            "/api/v1/docker/containers/abc123/start", headers=headers
        )
        r2 = await client.post("/api/v1/docker/containers/abc123/stop", headers=headers)
        r3 = await client.delete("/api/v1/docker/containers/abc123", headers=headers)

    assert (r1.status_code, r2.status_code, r3.status_code) == (204, 204, 204)
    assert len(spy_bus.of_type(EventType.CONTAINER_STARTED)) == 1
    assert len(spy_bus.of_type(EventType.CONTAINER_STOPPED)) == 1
    assert len(spy_bus.of_type(EventType.CONTAINER_REMOVED)) == 1
    started = spy_bus.of_type(EventType.CONTAINER_STARTED)[0]
    assert started.payload["container_id"] == "abc123"


# ===========================================================================
# T5 — host.added / host.removed (api/v1/hosts/crud.py)
# ===========================================================================


async def test_create_and_delete_target_emit_host_events(client, db_session, spy_bus):
    """POST /hosts → host.added ; DELETE /hosts/{id} → host.removed
    (payloads SANS credentials — règle 40)."""
    user, org = await _make_admin(db_session, "targets-admin")

    with patch(
        "app.api.v1.hosts.crud.HostService.check_health",
        new=AsyncMock(return_value=None),
    ), patch("app.api.v1.hosts.crud.AuditService.log_from_request", new=AsyncMock()):
        created = await client.post(
            "/api/v1/hosts/",
            json={
                "name": "host-canonical",
                "host": "127.0.0.1",
                "port": 22,
                "credentials": {"auth_method": "local"},
                "organization_id": str(org.id),
            },
            headers=_auth_headers(user),
        )
        assert created.status_code == 201, created.text
        host_id = created.json()["data"]["id"]

        deleted = await client.delete(
            f"/api/v1/hosts/{host_id}", headers=_auth_headers(user)
        )
        assert deleted.status_code == 204, deleted.text

    added = spy_bus.of_type(EventType.HOST_ADDED)
    removed = spy_bus.of_type(EventType.HOST_REMOVED)
    assert len(added) == 1
    assert len(removed) == 1
    assert added[0].payload["host_id"] == host_id
    assert added[0].payload["name"] == "host-canonical"
    assert removed[0].payload["host_id"] == host_id
    # Règle 40 : aucun credential ni matériel de clé SSH dans les payloads
    for event in (added[0], removed[0]):
        flattened = str(event.payload).lower()
        for forbidden in ("password", "private_key", "credentials", "passphrase"):
            assert forbidden not in flattened, forbidden


# ===========================================================================
# T5 — host.offline (target_service.check_health)
# ===========================================================================


async def test_health_check_transition_emits_host_offline(db_session):
    """ONLINE → probe injoignable → host.offline une seule fois par
    transition (pas de spam OFFLINE→OFFLINE)."""
    from app.enums.host import HostStatus
    from app.models.host import Host
    from app.services.host_service import HostService

    bus = SpyBus()
    host = Host(
        id=str(uuid4()),
        name="host-offline-test",
        host="127.0.0.1",
        port=59999,  # fermé → OFFLINE
        type="physical",
        status=HostStatus.ONLINE,
        organization_id=str(uuid4()),
    )
    db_session.add(host)
    await db_session.commit()

    with patch("app.core.events.get_event_bus", return_value=bus), patch.object(
        HostService, "HEALTH_CHECK_TIMEOUT", 0.2
    ):
        new_status = await HostService.check_health(db_session, host)
        assert new_status == HostStatus.OFFLINE
        offline_events = bus.of_type(EventType.HOST_OFFLINE)
        assert len(offline_events) == 1
        payload = offline_events[0].payload
        assert payload["host_id"] == str(host.id)
        assert payload["name"] == "host-offline-test"
        assert "last_seen" in payload

        # Déjà OFFLINE → nouvelle vérification : pas de nouvel événement
        await HostService.check_health(db_session, host)

    assert len(bus.of_type(EventType.HOST_OFFLINE)) == 1


# ===========================================================================
# T7 — plugin.installed / plugin.removed (publication bus)
# ===========================================================================


async def test_plugin_publish_to_bus_payloads(spy_bus):
    """plugin.installed {plugin_name, version} ; plugin.removed
    {plugin_name} — publiés sur le bus canonique."""
    from app.services.plugin_manager_service import PluginManagerService

    await PluginManagerService._publish_to_bus(
        EventType.PLUGIN_INSTALLED, plugin_name="my-plugin", version="1.2.0"
    )
    await PluginManagerService._publish_to_bus(
        EventType.PLUGIN_REMOVED, plugin_name="my-plugin"
    )

    installed = spy_bus.of_type(EventType.PLUGIN_INSTALLED)
    removed = spy_bus.of_type(EventType.PLUGIN_REMOVED)
    assert len(installed) == 1
    assert installed[0].payload == {
        "plugin_name": "my-plugin",
        "version": "1.2.0",
    }
    assert len(removed) == 1
    assert removed[0].payload == {"plugin_name": "my-plugin"}


async def test_plugin_bus_publication_never_raises():
    """Un bus indisponible n'interrompt jamais l'opération métier."""
    from app.services.plugin_manager_service import PluginManagerService

    with patch("app.core.events.get_event_bus", side_effect=RuntimeError("no bus")):
        # Ne doit pas lever malgré un bus indisponible
        await PluginManagerService._publish_to_bus(
            EventType.PLUGIN_INSTALLED, plugin_name="p", version="1"
        )


# ===========================================================================
# T4 — stack.deployed (deployment_service, succès RUNNING d'un stack)
# ===========================================================================


async def test_update_status_success_emits_stack_deployed(
    db_session, test_organization
):
    """Transition RUNNING d'un déploiement de stack → stack.deployed
    (payload IDs/nom — jamais de secrets)."""
    from app.models.deployment import Deployment, DeploymentStatus
    from app.services.deployment_service import DeploymentService

    bus = SpyBus()
    deployment = Deployment(
        id=str(uuid4()),
        name="stack-deploy-event",
        status=DeploymentStatus.DEPLOYING,
        stack_id=str(uuid4()),
        target_id=str(uuid4()),
        organization_id=test_organization.id,
        variables={},
        config={},
    )
    db_session.add(deployment)
    await db_session.commit()

    with patch(
        # update_status émet stack.deployed via le singleton
        # deployment_events.deployment_events.event_bus (attribut d'instance)
        "app.services.deployment_events.deployment_events.event_bus",
        bus,
    ), patch(
        "app.services.deployment_events.deployment_events.emit_status_change",
        new=AsyncMock(),
    ), patch(
        "app.services.deployment_service.AuditService.log", new=AsyncMock()
    ):
        await DeploymentService.update_status(
            db_session, deployment.id, DeploymentStatus.RUNNING, user_id=None
        )

    stack_deployed = bus.of_type(EventType.STACK_DEPLOYED)
    assert stack_deployed, "stack.deployed doit être émis au succès RUNNING"
    payload = stack_deployed[0].payload
    assert payload["stack_id"] == str(deployment.stack_id)
    assert payload["name"] == "stack-deploy-event"
    assert payload["host_id"] == str(deployment.target_id)
    assert payload["deployment_id"] == str(deployment.id)
    flattened = str(payload).lower()
    for forbidden in ("password", "token", "secret", "variables"):
        assert forbidden not in flattened
