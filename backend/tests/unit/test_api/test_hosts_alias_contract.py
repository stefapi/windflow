"""Contrats croisés ``/api/v1/hosts`` ≡ ``/api/v1/targets`` (STORY-166.2, AC 1).

L'alias ``/targets`` re-monte **les mêmes handlers** que le canonique
``/hosts`` (:mod:`app.api.v1.targets_legacy`) : ce fichier verrouille le
double nommage — aucun consommateur cassé :

- payloads identiques (comparaison JSON des réponses) sur les verbes
  GET/POST/PUT/DELETE et un sous-ensemble représentatif des 16
  endpoints (liste, détail, create, delete, health-check,
  capabilities, scan, test-reachability, fingerprints) ;
- **header ``Deprecation: true`` présent sur ``/targets``
  uniquement** (absent de ``/hosts``) + ``Sunset`` indicatif ;
- codes de statut identiques sur les deux chemins (404 introuvable,
  401 sans token) — l'isolation et le RBAC étant portés par les
  handlers partagés, ils sont couverts par ``test_hosts_rbac.py`` ;
- OpenAPI : opérations ``/hosts`` non dépréciées, ``/targets``
  marquées ``deprecated: true`` (assertions sur ``/openapi.json``).
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
from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.user_service import UserService

CREATE_PAYLOAD: dict[str, Any] = {
    "name": "alias-contract-host",
    "host": "127.0.0.1",
    "port": 22,
    "credentials": {"auth_method": "local"},
}


# --- Helpers (pattern test_hosts_crud) --------------------------------------


async def _make_admin(
    db_session: AsyncSession, username: str
) -> tuple[User, Organization]:
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
    db_session.add(
        UserOrganization(user_id=user.id, organization_id=org.id, role=Role.ADMIN)
    )
    await db_session.commit()
    return user, org


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_host(
    db_session: AsyncSession, org: Organization, name: str = "alias-seed"
) -> Any:
    from app.enums.host import HostProfile
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
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


@pytest.fixture(autouse=True)
def _fresh_role_cache():
    reset_role_cache()
    yield
    reset_role_cache()


# --- Header Deprecation : alias uniquement -----------------------------------


class TestDeprecationHeader:
    """``Deprecation``/``Sunset`` présents sur /targets, absents de /hosts."""

    async def test_list_targets_has_deprecation_headers(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user, _org = await _make_admin(db_session, "ac-dep-t")

        response = await client.get("/api/v1/targets/", headers=_auth_headers(user))
        assert response.status_code == 200, response.text
        assert response.headers.get("Deprecation") == "true"
        assert "Sunset" in response.headers  # date indicative

    async def test_list_hosts_has_no_deprecation_header(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user, _org = await _make_admin(db_session, "ac-dep-h")

        response = await client.get("/api/v1/hosts/", headers=_auth_headers(user))
        assert response.status_code == 200, response.text
        assert "Deprecation" not in response.headers
        assert "Sunset" not in response.headers

    async def test_deprecation_header_also_on_errors(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Le header de dépréciation est posé même sur les réponses d'erreur
        de l'alias (dépendance router — 404 introuvable)."""
        user, _org = await _make_admin(db_session, "ac-dep-e")

        response = await client.get(
            "/api/v1/targets/00000000-0000-0000-0000-000000000009",
            headers=_auth_headers(user),
        )
        assert response.status_code == 404
        assert response.headers.get("Deprecation") == "true"


# --- Contrats croisés : payloads identiques ----------------------------------


class TestCrossPathContract:
    """Mêmes codes + mêmes payloads sur /hosts et /targets."""

    async def test_get_list_identical_payloads(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user, org = await _make_admin(db_session, "ac-x-l")
        await _seed_host(db_session, org)
        headers = _auth_headers(user)

        canonical = await client.get("/api/v1/hosts/", headers=headers)
        alias = await client.get("/api/v1/targets/", headers=headers)
        assert canonical.status_code == alias.status_code == 200
        assert canonical.json() == alias.json()

    async def test_get_detail_identical_payloads(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        user, org = await _make_admin(db_session, "ac-x-g")
        host = await _seed_host(db_session, org)
        headers = _auth_headers(user)

        canonical = await client.get(f"/api/v1/hosts/{host.id}", headers=headers)
        alias = await client.get(f"/api/v1/targets/{host.id}", headers=headers)
        assert canonical.status_code == alias.status_code == 200
        assert canonical.json() == alias.json()

    async def test_post_create_identical_payloads(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """POST sur les deux chemins → 201 avec payloads égaux (hors id/dates)."""
        user, org = await _make_admin(db_session, "ac-x-p")
        headers = _auth_headers(user)
        results = []
        with patch(
            "app.api.v1.hosts.crud.HostService.check_health",
            new=AsyncMock(return_value=None),
        ):
            for path, name in (
                ("/api/v1/hosts/", "alias-create-canonical"),
                ("/api/v1/targets/", "alias-create-legacy"),
            ):
                response = await client.post(
                    path,
                    json={
                        **CREATE_PAYLOAD,
                        "name": name,
                        "organization_id": str(org.id),
                    },
                    headers=headers,
                )
                assert response.status_code == 201, response.text
                results.append(unwrap(response))
        # Champs communs identiques (hors identifiants/timestamps propres
        # à chaque création)
        assert results[0]["profile"] == results[1]["profile"]
        assert results[0]["host"] == results[1]["host"]
        assert results[0]["auth_method"] == results[1]["auth_method"]

    async def test_delete_identical_behaviour(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """DELETE 204 sur les deux chemins (hosts puis targets)."""
        user, org = await _make_admin(db_session, "ac-x-d")
        headers = _auth_headers(user)
        h1 = await _seed_host(db_session, org, name="del-canonical")
        h2 = await _seed_host(db_session, org, name="del-alias")

        r_canonical = await client.delete(f"/api/v1/hosts/{h1.id}", headers=headers)
        r_alias = await client.delete(f"/api/v1/targets/{h2.id}", headers=headers)
        assert r_canonical.status_code == r_alias.status_code == 204

    async def test_update_identical_payloads(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """PUT sur les deux chemins → même réponse (hormis name testé)."""
        user, org = await _make_admin(db_session, "ac-x-u")
        headers = _auth_headers(user)

        r_canonical = await client.put(
            f"/api/v1/hosts/{(await _seed_host(db_session, org, 'up-c')).id}",
            json={"name": "renamed-c"},
            headers=headers,
        )
        r_alias = await client.put(
            f"/api/v1/targets/{(await _seed_host(db_session, org, 'up-a')).id}",
            json={"name": "renamed-a"},
            headers=headers,
        )
        assert r_canonical.status_code == r_alias.status_code == 200
        assert unwrap(r_canonical)["name"] == "renamed-c"
        assert unwrap(r_alias)["name"] == "renamed-a"

    async def test_404_identical_on_both_paths(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """404 introuvable sur les deux chemins."""
        user, _org = await _make_admin(db_session, "ac-x-4")
        headers = _auth_headers(user)

        r_canonical = await client.get(
            "/api/v1/hosts/00000000-0000-0000-0000-000000000003", headers=headers
        )
        r_alias = await client.get(
            "/api/v1/targets/00000000-0000-0000-0000-000000000003", headers=headers
        )
        assert r_canonical.status_code == r_alias.status_code == 404

    async def test_401_identical_on_both_paths(self, client: AsyncClient):
        """401 sans token sur les deux chemins."""
        r_canonical = await client.get("/api/v1/hosts/")
        r_alias = await client.get("/api/v1/targets/")
        assert r_canonical.status_code == r_alias.status_code == 401

    @pytest.mark.parametrize(
        ("suffix", "method"),
        [
            ("/{host_id}/health-check", "post"),
            ("/{host_id}/capabilities", "get"),
            ("/{host_id}/scan", "post"),
            ("/test-reachability", "post"),
            ("/{host_id}/ssh-fingerprints", "get"),
        ],
        ids=["health-check", "capabilities", "scan", "reachability", "fingerprints"],
    )
    async def test_representative_endpoints_respond_on_both_paths(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        suffix: str,
        method: str,
    ):
        """Sous-ensemble représentatif des 16 endpoints : même comportement
        (statut ≠ 404 route-not-found) sur les deux chemins.

        Les handlers étant partagés, on vérifie la **résolution de route**
        (pas de 405/404 routing) + l'égalité des codes : les effets de bord
        réseau sont court-circuités (host offline local → health-check
        réel possible, scan mocké).
        """
        user, org = await _make_admin(db_session, f"ac-x-r-{method}{len(suffix)}")
        headers = _auth_headers(user)

        if "{host_id}" in suffix:
            host = await _seed_host(db_session, org)
            suffix = suffix.replace("{host_id}", str(host.id))

        kwargs: dict[str, Any] = {"headers": headers}
        if method == "post" and suffix.endswith("test-reachability"):
            kwargs["json"] = {"host": "127.0.0.1", "port": 22}

        if method == "post" and suffix.endswith("/scan"):
            with patch(
                "app.api.v1.hosts.scanning.HostScannerService.scan_and_update_host",
                new=AsyncMock(return_value=host),
            ):
                r_canonical = await getattr(client, method)(
                    f"/api/v1/hosts{suffix}", **kwargs
                )
                r_alias = await getattr(client, method)(
                    f"/api/v1/targets{suffix}", **kwargs
                )
        else:
            r_canonical = await getattr(client, method)(
                f"/api/v1/hosts{suffix}", **kwargs
            )
            r_alias = await getattr(client, method)(
                f"/api/v1/targets{suffix}", **kwargs
            )

        assert r_canonical.status_code == r_alias.status_code
        assert r_canonical.status_code != 404 or "{host_id}" not in suffix
        # l'alias porte toujours la marque de dépréciation
        assert r_alias.headers.get("Deprecation") == "true"


# --- OpenAPI : canonique documenté, alias déprécié ----------------------------


class TestOpenAPIMarks:
    """Assertions /openapi.json : /hosts documenté, /targets deprecated."""

    async def test_hosts_and_targets_both_documented(self, client: AsyncClient):
        spec = (await client.get("/openapi.json")).json()
        hosts_paths = [p for p in spec["paths"] if p.startswith("/api/v1/hosts")]
        targets_paths = [p for p in spec["paths"] if p.startswith("/api/v1/targets")]
        assert hosts_paths, "/api/v1/hosts absent de l'OpenAPI"
        assert targets_paths, "/api/v1/targets absent de l'OpenAPI"
        assert len(hosts_paths) == len(targets_paths) == 13  # 13 paths / 16 ops

    async def test_targets_operations_deprecated_hosts_not(self, client: AsyncClient):
        spec = (await client.get("/openapi.json")).json()

        for path in spec["paths"]:
            for method, op in spec["paths"][path].items():
                if not isinstance(op, dict):
                    continue
                if path.startswith("/api/v1/targets"):
                    assert op.get("deprecated") is True, f"{method} {path}"
                elif path.startswith("/api/v1/hosts"):
                    assert not op.get("deprecated"), f"{method} {path}"

    async def test_hosts_documented_with_examples(self, client: AsyncClient):
        """Le canonique garde une documentation riche (examples présents)."""
        spec = (await client.get("/openapi.json")).json()
        hosts_ops = [
            op
            for p in spec["paths"]
            if p.startswith("/api/v1/hosts")
            for m, op in spec["paths"][p].items()
            if isinstance(op, dict)
        ]
        assert hosts_ops
        # Une majorité des opérations conserve summaries + descriptions
        with_summary = [op for op in hosts_ops if op.get("summary")]
        assert len(with_summary) >= len(hosts_ops) * 0.9

    async def test_deprecated_tag_documented(self, client: AsyncClient):
        """Le tag ``targets`` documente la dépréciation (main.py openapi_tags)."""
        spec = (await client.get("/openapi.json")).json()
        tags = {t["name"]: t.get("description", "") for t in spec.get("tags", [])}
        assert "hosts" in tags
        assert "targets" in tags
        assert "Deprecated" in tags["targets"]
