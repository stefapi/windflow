"""Tests RBAC du sous-paquet hosts (STORY-122.5, AC 2 — chemins canoniques
STORY-166.2 ; l'alias /targets est couvert par test_hosts_alias_contract.py).

Matrice spec 08 appliquée :
- lectures (liste/détail/capabilities) + health-check TCP = Viewer+ ;
- tests de connectivité lecture-only (reachability / SSH) = Operator+
  (divergence inventaire signalée — cf. notes STORY-122.5) ;
- gestion host (create/update/delete) + découverte/scan = Admin+.

Couverture :
- **viewer** : 200 ``GET /hosts/`` + ``GET /targets/{id}`` +
  ``GET /targets/{id}/capabilities`` ; 403 create / scan / test-connection ;
- **operator** : 200 ``POST /targets/test-connection`` (mocké) ; 403 create ;
- **admin** : 201 create, 200 update, 204 delete, 200 scan (services
  mockés pour les effets de bord réseau) ;
- **404** target inexistante ; **422** payload invalide ;
- **401 sans token** (échantillon).

Chaîne d'auth réelle : JWT → ``require_*`` (pattern test_schedules_rbac).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

from app.auth.jwt import create_access_token
from app.core.cache import reset_role_cache
from app.enums.rbac import Role
from app.enums.target import TargetStatus, TargetType
from app.models.host import Host
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.user_service import UserService

CREATE_PAYLOAD_BASE: dict = {
    "name": "rbac-target",
    "host": "127.0.0.1",
    "port": 22,
    "credentials": {"auth_method": "local"},
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


async def _seed_target(db_session: AsyncSession, org: Organization) -> Host:
    """Insère une target ONLINE dans l'organisation donnée."""
    target = Host(
        name="seed-target",
        host="127.0.0.1",
        port=22,
        type=TargetType.PHYSICAL,
        status=TargetStatus.ONLINE,
        credentials={},
        organization_id=org.id,
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)
    return target


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
    """Viewer : 200 lectures / 403 gestion et opérations SSH."""

    async def test_viewer_200_list_targets(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /targets/ avec viewer → 200 (host seedé visible)."""
        user, org = await _create_user_with_role(db_session, "tgt-view-l", Role.VIEWER)
        await _seed_target(db_session, org)

        response = await client.get("/api/v1/hosts/", headers=_auth_headers(user))
        assert response.status_code == 200, response.text
        assert isinstance(unwrap(response), list)
        assert len(unwrap(response)) == 1

    async def test_viewer_200_get_target(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /targets/{id} avec viewer → 200 (isolation OK)."""
        user, org = await _create_user_with_role(db_session, "tgt-view-g", Role.VIEWER)
        target = await _seed_target(db_session, org)

        response = await client.get(
            f"/api/v1/hosts/{target.id}", headers=_auth_headers(user)
        )
        assert response.status_code == 200, response.text
        assert unwrap(response)["id"] == target.id

    async def test_viewer_200_capabilities(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /targets/{id}/capabilities avec viewer → 200."""
        user, org = await _create_user_with_role(db_session, "tgt-view-c", Role.VIEWER)
        target = await _seed_target(db_session, org)

        response = await client.get(
            f"/api/v1/hosts/{target.id}/capabilities", headers=_auth_headers(user)
        )
        assert response.status_code == 200, response.text

    async def test_viewer_403_create_target(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /targets/ avec viewer → 403."""
        user, org = await _create_user_with_role(db_session, "tgt-view-cr", Role.VIEWER)

        response = await client.post(
            "/api/v1/hosts/",
            json={**CREATE_PAYLOAD_BASE, "organization_id": org.id},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403
        assert response.json()["error"]["message"] == "Not enough permissions"

    async def test_viewer_403_scan_target(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /targets/{id}/scan avec viewer → 403 (Scanner = Admin+)."""
        user, org = await _create_user_with_role(db_session, "tgt-view-s", Role.VIEWER)
        target = await _seed_target(db_session, org)

        response = await client.post(
            f"/api/v1/hosts/{target.id}/scan", headers=_auth_headers(user)
        )
        assert response.status_code == 403

    async def test_viewer_403_test_connection(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Opération : POST /targets/test-connection avec viewer → 403 (Operator+)."""
        user, _org = await _create_user_with_role(db_session, "tgt-view-t", Role.VIEWER)

        response = await client.post(
            "/api/v1/hosts/test-connection",
            json={
                "host": "127.0.0.1",
                "port": 22,
                "credentials": {"auth_method": "local"},
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 403


# --- Operator : tests connectivité OK, gestion 403 ---------------------------


class TestOperatorMatrix:
    """Operator : 200 tests lecture-only / 403 gestion."""

    async def test_operator_200_test_connection(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Opération : POST /targets/test-connection avec operator → 200 (mocké)."""
        user, _org = await _create_user_with_role(db_session, "tgt-op-t", Role.OPERATOR)

        with patch(
            "app.api.v1.hosts.connectivity._test_local_connection",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    success=True, message="Connexion locale réussie", os_info=None
                )
            ),
        ):
            response = await client.post(
                "/api/v1/hosts/test-connection",
                json={
                    "host": "127.0.0.1",
                    "port": 22,
                    "credentials": {"auth_method": "local"},
                },
                headers=_auth_headers(user),
            )
        assert response.status_code == 200, response.text
        assert unwrap(response)["success"] is True

    async def test_operator_403_create_target(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /targets/ avec operator → 403."""
        user, org = await _create_user_with_role(db_session, "tgt-op-c", Role.OPERATOR)

        response = await client.post(
            "/api/v1/hosts/",
            json={**CREATE_PAYLOAD_BASE, "organization_id": org.id},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403


# --- Admin : CRUD + scan OK ---------------------------------------------------


class TestAdminMatrix:
    """Admin : 201 create, 200 update, 204 delete, 200 scan (mockés)."""

    async def test_admin_201_create_target(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /targets/ avec admin → 201 (health-check mocké)."""
        user, org = await _create_user_with_role(db_session, "tgt-adm-c", Role.ADMIN)

        with patch(
            "app.api.v1.hosts.crud.HostService.check_health",
            new=AsyncMock(return_value="online"),
        ):
            response = await client.post(
                "/api/v1/hosts/",
                json={**CREATE_PAYLOAD_BASE, "organization_id": org.id},
                headers=_auth_headers(user),
            )
        assert response.status_code == 201, response.text
        assert unwrap(response)["name"] == CREATE_PAYLOAD_BASE["name"]

    async def test_admin_200_update_target(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : PUT /targets/{id} avec admin → 200."""
        user, org = await _create_user_with_role(db_session, "tgt-adm-u", Role.ADMIN)
        target = await _seed_target(db_session, org)

        response = await client.put(
            f"/api/v1/hosts/{target.id}",
            json={"name": "renamed-target"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 200, response.text
        assert unwrap(response)["name"] == "renamed-target"

    async def test_admin_204_delete_target(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : DELETE /targets/{id} avec admin → 204."""
        user, org = await _create_user_with_role(db_session, "tgt-adm-d", Role.ADMIN)
        target = await _seed_target(db_session, org)

        response = await client.delete(
            f"/api/v1/hosts/{target.id}", headers=_auth_headers(user)
        )
        assert response.status_code == 204

    async def test_admin_200_scan_target(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /targets/{id}/scan avec admin → 200 (scanner mocké)."""
        user, org = await _create_user_with_role(db_session, "tgt-adm-s", Role.ADMIN)
        target = await _seed_target(db_session, org)

        with patch(
            "app.api.v1.hosts.scanning.HostScannerService.scan_and_update_host",
            new=AsyncMock(return_value=target),
        ):
            response = await client.post(
                f"/api/v1/hosts/{target.id}/scan", headers=_auth_headers(user)
            )
        assert response.status_code == 200, response.text
        assert unwrap(response)["id"] == target.id


# --- Cas d'erreur : 404 / 422 ------------------------------------------------


class TestErrorCases:
    """404 target inexistante, 422 payload invalide."""

    async def test_viewer_404_target_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Erreur : GET /targets/{id} inexistant avec viewer → 404."""
        user, _org = await _create_user_with_role(db_session, "tgt-404", Role.VIEWER)

        response = await client.get(
            "/api/v1/hosts/nonexistent-id", headers=_auth_headers(user)
        )
        assert response.status_code == 404

    async def test_admin_422_invalid_payload(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Validation : POST /targets/ sans host avec admin → 422."""
        user, org = await _create_user_with_role(db_session, "tgt-422", Role.ADMIN)

        response = await client.post(
            "/api/v1/hosts/",
            json={
                "name": "incomplete",
                "organization_id": org.id,
                "credentials": {"auth_method": "local"},
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 422


# --- Sécurité : 401 sans token ------------------------------------------------


class TestNoToken:
    """Sans Authorization : 401 avant toute vérification de rôle."""

    async def test_no_token_401_sample(self, client: AsyncClient):
        """401 sur un échantillon lecture/opération/gestion."""
        read_resp = await client.get("/api/v1/hosts/")
        op_resp = await client.post(
            "/api/v1/hosts/test-connection",
            json={
                "host": "127.0.0.1",
                "port": 22,
                "credentials": {"auth_method": "local"},
            },
        )
        adm_resp = await client.post("/api/v1/hosts/", json={})

        assert read_resp.status_code == 401
        assert op_resp.status_code == 401
        assert adm_resp.status_code == 401
