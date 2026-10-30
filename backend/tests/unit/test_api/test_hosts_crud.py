"""Tests API de la surface canonique ``/api/v1/hosts`` (STORY-166.2, AC 1/3).

Couverture (règle 35 + story) :

- nominaux : liste vide/avec éléments + enveloppe/pagination STORY-128,
  détail complet (champs canoniques spec 06 : ``profile``, ``status``,
  ``hardware_info``, ``installed_engines``, ``origin``), POST 201,
  PUT 200, DELETE 204 ;
- sécurité obligatoire : 401 sans token (chaque verbe), 403 viewer et
  operator sur create, 422 body invalide (``host`` manquant, ``port``
  hors bornes, ``name`` vide), 404 introuvable, **403/404 isolation
  organisationnelle**, 409 doublon de nom dans l'org ;
- absence de champs sensibles (règle 40) : ``credentials``,
  ``connection_config``, ``password``, ``ssh_private_key`` absents de
  toutes les réponses (liste, détail, POST) ;
- alias legacy : le champ ``type`` reste accepté en entrée et exposé en
  sortie (contrat /targets figé) ; ``profile`` prime en cas de doublon.

Pattern : JWT réel → ``require_*`` (cf. ``test_hosts_rbac.py`` pour la
matrice complète des rôles).
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
from app.enums.host import HostProfile
from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.user_service import UserService

CREATE_PAYLOAD_BASE: dict[str, Any] = {
    "name": "hosts-crud-test",
    "host": "127.0.0.1",
    "port": 22,
    "credentials": {"auth_method": "local"},
}


# --- Helpers (pattern test_hosts_rbac) -------------------------------------


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


async def _seed_host(
    db_session: AsyncSession, org: Organization, name: str = "seed-host"
) -> Any:
    """Insère un host ONLINE dans l'organisation donnée."""
    from app.models.host import Host

    host = Host(
        name=name,
        host="127.0.0.1",
        port=22,
        profile=HostProfile.HOST_BAREMETAL,
        status="online",
        credentials={},
        organization_id=org.id,
    )
    db_session.add(host)
    await db_session.commit()
    await db_session.refresh(host)
    return host


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


# --- Nominaux ---------------------------------------------------------------


class TestListHosts:
    """GET /hosts/ : enveloppe STORY-128 + pagination + isolation."""

    async def test_list_empty_200_envelope(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Liste vide → 200, data=[] + pagination{page,per_page,total,pages}."""
        user, _org = await _create_user_with_role(db_session, "hc-lst-e", Role.VIEWER)

        response = await client.get("/api/v1/hosts/", headers=_auth_headers(user))
        assert response.status_code == 200, response.text
        # STORY-128 : corps paginé passé tel quel (pas de double enveloppe)
        body = response.json()["data"]
        assert body == []
        assert response.json()["pagination"]["page"] == 1
        assert response.json()["pagination"]["total"] == 0

    async def test_list_with_items_and_pagination(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Hosts visibles + paramètres page/per_page respectés."""
        user, org = await _create_user_with_role(db_session, "hc-lst-p", Role.VIEWER)
        for i in range(3):
            await _seed_host(db_session, org, name=f"host-{i}")

        response = await client.get(
            "/api/v1/hosts/?page=1&per_page=2", headers=_auth_headers(user)
        )
        assert response.status_code == 200, response.text
        body = response.json()["data"]
        assert len(body) == 2
        pagination = response.json()["pagination"]
        assert pagination["per_page"] == 2
        assert pagination["total"] == 3
        assert pagination["pages"] == 2

    async def test_list_scoped_to_user_orgs(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Isolation : les hosts d'une org étrangère n'apparaissent pas."""
        user, org = await _create_user_with_role(db_session, "hc-lst-s", Role.VIEWER)
        _, other_org = await _create_user_with_role(db_session, "hc-lst-o", Role.VIEWER)
        await _seed_host(db_session, org, name="mine")
        await _seed_host(db_session, other_org, name="foreign")

        response = await client.get("/api/v1/hosts/", headers=_auth_headers(user))
        assert response.status_code == 200
        names = [h["name"] for h in response.json()["data"]]
        assert names == ["mine"]


class TestGetHost:
    """GET /hosts/{id} : détail complet, champs canoniques spec 06."""

    async def test_get_detail_canonical_fields(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Détail : profile/status/hardware_info/installed_engines/origin présents."""
        user, org = await _create_user_with_role(db_session, "hc-get-c", Role.VIEWER)
        host = await _seed_host(db_session, org)

        response = await client.get(
            f"/api/v1/hosts/{host.id}", headers=_auth_headers(user)
        )
        assert response.status_code == 200, response.text
        detail = unwrap(response)
        for field in (
            "id",
            "name",
            "host",
            "port",
            "profile",
            "status",
            "hardware_info",
            "installed_engines",
            "last_scan_at",
            "origin",
            "auth_method",
            "username",
            "has_sudo",
            "ssh_key_id",
            "type",  # alias legacy conservé (contrat /targets figé)
            "organization_id",
        ):
            assert field in detail, f"champ manquant : {field}"
        assert detail["profile"] == "host_baremetal"

    async def test_get_404_unknown(self, client: AsyncClient, db_session: AsyncSession):
        """Host inexistant → 404."""
        user, _org = await _create_user_with_role(db_session, "hc-get-4", Role.VIEWER)

        response = await client.get(
            "/api/v1/hosts/00000000-0000-0000-0000-000000000001",
            headers=_auth_headers(user),
        )
        assert response.status_code == 404

    async def test_get_foreign_org_host_denied(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Host d'une autre organisation → 403 (isolation org)."""
        user, _org = await _create_user_with_role(db_session, "hc-get-i", Role.ADMIN)
        _, other_org = await _create_user_with_role(db_session, "hc-get-f", Role.VIEWER)
        foreign = await _seed_host(db_session, other_org)

        response = await client.get(
            f"/api/v1/hosts/{foreign.id}", headers=_auth_headers(user)
        )
        assert response.status_code == 403


class TestCreateHost:
    """POST /hosts/ : 201 + arbitrage profile/type + 409 doublon."""

    async def test_create_201_minimal(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Création minimale → 201 ; défaut profile=host_baremetal."""
        user, org = await _create_user_with_role(db_session, "hc-cr-m", Role.ADMIN)

        with patch(
            "app.api.v1.hosts.crud.HostService.check_health",
            new=AsyncMock(return_value=None),
        ):
            response = await client.post(
                "/api/v1/hosts/",
                json={**CREATE_PAYLOAD_BASE, "organization_id": str(org.id)},
                headers=_auth_headers(user),
            )
        assert response.status_code == 201, response.text
        created = unwrap(response)
        assert created["name"] == CREATE_PAYLOAD_BASE["name"]
        assert created["profile"] == "host_baremetal"

    async def test_create_201_with_explicit_profile(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """profile explicite respecté et prioritaire sur type."""
        user, org = await _create_user_with_role(db_session, "hc-cr-p", Role.ADMIN)

        with patch(
            "app.api.v1.hosts.crud.HostService.check_health",
            new=AsyncMock(return_value=None),
        ):
            response = await client.post(
                "/api/v1/hosts/",
                json={
                    **CREATE_PAYLOAD_BASE,
                    "organization_id": str(org.id),
                    "profile": "host_proxmox",
                    "type": "docker",  # doit être neutralisé par le canonique
                },
                headers=_auth_headers(user),
            )
        assert response.status_code == 201, response.text
        created = unwrap(response)
        assert created["profile"] == "host_proxmox"

    async def test_create_201_with_legacy_type(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """type legacy seul → mappé vers profile (compat contrat /targets)."""
        user, org = await _create_user_with_role(db_session, "hc-cr-t", Role.ADMIN)

        with patch(
            "app.api.v1.hosts.crud.HostService.check_health",
            new=AsyncMock(return_value=None),
        ):
            response = await client.post(
                "/api/v1/hosts/",
                json={
                    **CREATE_PAYLOAD_BASE,
                    "name": "legacy-typed-host",
                    "organization_id": str(org.id),
                    "type": "docker",
                },
                headers=_auth_headers(user),
            )
        assert response.status_code == 201, response.text
        created = unwrap(response)
        # docker + adresse locale (127.0.0.1) → host_baremetal (arbitrage
        # 166.1 : socket local = pilotage direct)
        assert created["profile"] == "host_baremetal"
        assert created["type"] == "docker"  # écho legacy fidèle

    async def test_create_409_duplicate_name(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Doublon de nom dans l'org → 409 Conflict."""
        user, org = await _create_user_with_role(db_session, "hc-cr-d", Role.ADMIN)
        await _seed_host(db_session, org, name=CREATE_PAYLOAD_BASE["name"])

        response = await client.post(
            "/api/v1/hosts/",
            json={**CREATE_PAYLOAD_BASE, "organization_id": str(org.id)},
            headers=_auth_headers(user),
        )
        assert response.status_code == 409


class TestUpdateHost:
    """PUT /hosts/{id} : mise à jour partielle."""

    async def test_update_200_rename(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Renommage → 200 + name à jour."""
        user, org = await _create_user_with_role(db_session, "hc-up-r", Role.ADMIN)
        host = await _seed_host(db_session, org)

        response = await client.put(
            f"/api/v1/hosts/{host.id}",
            json={"name": "renamed-host"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 200, response.text
        assert unwrap(response)["name"] == "renamed-host"

    async def test_update_404_unknown(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Update d'un host inexistant → 404."""
        user, _org = await _create_user_with_role(db_session, "hc-up-4", Role.ADMIN)

        response = await client.put(
            "/api/v1/hosts/00000000-0000-0000-0000-000000000002",
            json={"name": "x"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 404


class TestDeleteHost:
    """DELETE /hosts/{id} : 204 + isolation."""

    async def test_delete_204(self, client: AsyncClient, db_session: AsyncSession):
        """Suppression admin → 204."""
        user, org = await _create_user_with_role(db_session, "hc-de-m", Role.ADMIN)
        host = await _seed_host(db_session, org)

        response = await client.delete(
            f"/api/v1/hosts/{host.id}", headers=_auth_headers(user)
        )
        assert response.status_code == 204

    async def test_delete_403_foreign_org(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Suppression d'un host d'une autre org → 403."""
        user, _org = await _create_user_with_role(db_session, "hc-de-i", Role.ADMIN)
        _, other_org = await _create_user_with_role(db_session, "hc-de-f", Role.VIEWER)
        foreign = await _seed_host(db_session, other_org)

        response = await client.delete(
            f"/api/v1/hosts/{foreign.id}", headers=_auth_headers(user)
        )
        assert response.status_code == 403


# --- Sécurité obligatoire (règle 35/40) --------------------------------------


class TestSecurity:
    """401 sans token (chaque verbe), 403 rôles insuffisants, 422 validation."""

    async def test_401_without_token_all_verbs(self, client: AsyncClient):
        """Sans Authorization : 401 sur GET/POST/PUT/DELETE."""
        r_list = await client.get("/api/v1/hosts/")
        r_post = await client.post("/api/v1/hosts/", json={})
        r_put = await client.put("/api/v1/hosts/x", json={})
        r_delete = await client.delete("/api/v1/hosts/x")
        assert r_list.status_code == 401
        assert r_post.status_code == 401
        assert r_put.status_code == 401
        assert r_delete.status_code == 401

    async def test_403_viewer_cannot_manage(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Viewer : 403 sur POST/PUT/DELETE (gestion = Admin+)."""
        user, org = await _create_user_with_role(db_session, "hc-sec-v", Role.VIEWER)
        host = await _seed_host(db_session, org)
        headers = _auth_headers(user)

        r_post = await client.post(
            "/api/v1/hosts/",
            json={**CREATE_PAYLOAD_BASE, "organization_id": str(org.id)},
            headers=headers,
        )
        r_put = await client.put(
            f"/api/v1/hosts/{host.id}", json={"name": "x"}, headers=headers
        )
        r_delete = await client.delete(f"/api/v1/hosts/{host.id}", headers=headers)
        assert r_post.status_code == 403
        assert r_put.status_code == 403
        assert r_delete.status_code == 403

    async def test_403_operator_cannot_create(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Operator : 403 sur create (gestion = Admin+)."""
        user, org = await _create_user_with_role(db_session, "hc-sec-o", Role.OPERATOR)

        response = await client.post(
            "/api/v1/hosts/",
            json={**CREATE_PAYLOAD_BASE, "organization_id": str(org.id)},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "payload",
        [
            {},  # body vide
            {"name": "no-host"},  # host manquant
            {**CREATE_PAYLOAD_BASE, "port": 0},  # port hors bornes
            {**CREATE_PAYLOAD_BASE, "port": 70000},
            {**CREATE_PAYLOAD_BASE, "name": ""},  # name vide
        ],
        ids=["empty", "missing-host", "port-zero", "port-too-high", "empty-name"],
    )
    async def test_422_invalid_bodies(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        payload: dict[str, Any],
    ):
        """Bodies invalides → 422 (validation Pydantic)."""
        user, org = await _create_user_with_role(db_session, "hc-sec-4", Role.ADMIN)
        body = {**payload, "organization_id": str(org.id)}

        response = await client.post(
            "/api/v1/hosts/", json=body, headers=_auth_headers(user)
        )
        assert response.status_code == 422, response.text


class TestNoSensitiveFields:
    """Règle 40 : aucun secret dans les réponses (liste/détail/POST)."""

    FORBIDDEN = ("credentials", "connection_config", "password", "ssh_private_key")

    async def _create_host_via_api(
        self, client: AsyncClient, db_session: AsyncSession, username: str
    ):
        user, org = await _create_user_with_role(db_session, username, Role.ADMIN)
        with patch(
            "app.api.v1.hosts.crud.HostService.check_health",
            new=AsyncMock(return_value=None),
        ):
            response = await client.post(
                "/api/v1/hosts/",
                json={**CREATE_PAYLOAD_BASE, "organization_id": str(org.id)},
                headers=_auth_headers(user),
            )
        assert response.status_code == 201, response.text
        return user, unwrap(response)

    async def test_post_response_has_no_secrets(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Réponse POST : pas de credentials/password/ssh_private_key."""
        _user, created = await self._create_host_via_api(client, db_session, "hc-no-p")
        flattened = str(created).lower()
        for forbidden in self.FORBIDDEN:
            assert forbidden not in flattened, forbidden

    async def test_list_and_detail_have_no_secrets(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Réponses liste + détail : idem — aucun champ sensible."""
        user, created = await self._create_host_via_api(client, db_session, "hc-no-l")
        headers = _auth_headers(user)

        listing = (await client.get("/api/v1/hosts/", headers=headers)).json()["data"]
        detail = unwrap(
            await client.get(f"/api/v1/hosts/{created['id']}", headers=headers)
        )
        for payload in (
            listing[0],
            detail,
        ):
            flattened = str(payload).lower()
            for forbidden in self.FORBIDDEN:
                assert forbidden not in flattened, forbidden
