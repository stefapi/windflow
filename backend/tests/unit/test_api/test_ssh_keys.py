"""Tests API des endpoints ``/api/v1/ssh-keys`` (STORY-131.2, famille 7).

Nominaux : 201 generate/import (``private_key`` présent **une seule
fois** — absent des GET/LIST), 200 liste paginée avec enveloppe
``pagination{}``, 200 détail, 200 rename, 204 delete (+ ``force=true``
déréférençant les cibles).

Sécurité (rules 40 / story) :

- 401 sans token, 403 viewer **et** operator (gestion des credentials =
  Admin+ — matrice spec 08) ;
- 422 : name vide, key_type inconnu, PEM invalide (sémantique service),
  body manquant ;
- 404 id inconnu ; 409 delete référencée / name dupliqué / empreinte
  déjà enregistrée ;
- **aucun secret dans les réponses ni les logs** : ni
  ``private_key_encrypted`` ni ``decrypted_private_key`` ni passphrase —
  assert sur les bodies et caplog.

Pattern : httpx ``AsyncClient`` + ``ASGITransport`` via la fixture
``client`` (conftest), mint JWT direct (pattern test_api_keys), asyncssh
non mocké (génération locale sans I/O).
"""

import logging

import asyncssh
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import create_user_with_role, error_code, unwrap

from app.auth.jwt import create_access_token
from app.enums.rbac import Role
from app.models.ssh_key import SSHKey
from app.models.host import Host
from app.models.user import User

SSH_KEYS_URL = "/api/v1/ssh-keys"


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 123.4."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


def _auth_headers(user: User) -> dict[str, str]:
    """Headers Bearer mintés directement (pattern test_api_keys)."""
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


def _pem() -> str:
    """PEM ed25519 en clair pour les imports."""
    return asyncssh.generate_private_key("ssh-ed25519").export_private_key().decode()


async def _generate_key(client: AsyncClient, headers: dict, name: str) -> dict:
    """POST /ssh-keys/generate → 201 ; retourne le body enveloppé."""
    response = await client.post(
        f"{SSH_KEYS_URL}/generate", json={"name": name}, headers=headers
    )
    assert response.status_code == 201, response.text
    return unwrap(response)


class TestGenerateAndImport:
    """POST /ssh-keys/generate et /ssh-keys/import — 201 + affichage unique."""

    async def test_generate_201_private_key_once(
        self, client: AsyncClient, db_session: AsyncSession, test_superuser: User
    ):
        """201 : ``private_key`` présent dans LA réponse de création,
        absent du GET et du LIST ultérieurs (affichage unique)."""
        headers = _auth_headers(test_superuser)
        body = await _generate_key(client, headers, "prod-key")

        assert body["name"] == "prod-key"
        assert body["key_type"] == "ssh-ed25519"
        assert body["public_key"].startswith("ssh-ed25519 ")
        assert body["fingerprint"].startswith("SHA256:")
        assert body["targets_count"] == 0
        pem = body["private_key"]
        assert pem.startswith("-----BEGIN OPENSSH PRIVATE KEY-----")

        detail = await client.get(f"{SSH_KEYS_URL}/{body['id']}", headers=headers)
        assert detail.status_code == 200
        assert "private_key" not in unwrap(detail)
        assert pem not in detail.text

        listing = await client.get(SSH_KEYS_URL, headers=headers)
        assert listing.status_code == 200
        items = unwrap(listing)
        assert len(items) == 1
        assert "private_key" not in items[0]
        assert "private_key_encrypted" not in items[0]
        assert "decrypted_private_key" not in items[0]
        assert pem not in listing.text

    async def test_import_201(self, client: AsyncClient, test_superuser: User):
        """Import nominal : 201, empreinte cohérente, PEM affiché une fois."""
        headers = _auth_headers(test_superuser)
        response = await client.post(
            f"{SSH_KEYS_URL}/import",
            json={"name": "imported", "private_key": _pem()},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        body = unwrap(response)
        assert body["fingerprint"].startswith("SHA256:")
        assert body["private_key"].startswith("-----BEGIN OPENSSH PRIVATE KEY-----")

    async def test_generate_duplicate_name_409(
        self, client: AsyncClient, test_superuser: User
    ):
        """Name dupliqué → 409 CONFLICT."""
        headers = _auth_headers(test_superuser)
        await _generate_key(client, headers, "dup")
        response = await client.post(
            f"{SSH_KEYS_URL}/generate", json={"name": "dup"}, headers=headers
        )
        assert response.status_code == 409
        assert error_code(response) == "CONFLICT"

    async def test_import_same_material_409(
        self, client: AsyncClient, test_superuser: User
    ):
        """Dédup par empreinte : même matériau, autre nom → 409."""
        headers = _auth_headers(test_superuser)
        pem = _pem()
        first = await client.post(
            f"{SSH_KEYS_URL}/import",
            json={"name": "one", "private_key": pem},
            headers=headers,
        )
        assert first.status_code == 201
        second = await client.post(
            f"{SSH_KEYS_URL}/import",
            json={"name": "two", "private_key": pem},
            headers=headers,
        )
        assert second.status_code == 409
        assert error_code(second) == "CONFLICT"

    async def test_import_invalid_pem_422(
        self, client: AsyncClient, test_superuser: User
    ):
        """PEM illisible → 422 VALIDATION_ERROR (sémantique service)."""
        headers = _auth_headers(test_superuser)
        response = await client.post(
            f"{SSH_KEYS_URL}/import",
            json={"name": "junk", "private_key": "not a pem"},
            headers=headers,
        )
        assert response.status_code == 422
        assert error_code(response) == "VALIDATION_ERROR"


class TestList:
    """GET /ssh-keys — enveloppe paginée."""

    async def test_list_paginated_envelope(
        self, client: AsyncClient, test_superuser: User
    ):
        """200 : ``data`` + ``pagination{page, per_page, total, pages}``."""
        headers = _auth_headers(test_superuser)
        await _generate_key(client, headers, "k-list")

        response = await client.get(
            f"{SSH_KEYS_URL}?page=1&per_page=20", headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["pagination"]["page"] == 1
        assert body["pagination"]["per_page"] == 20
        assert body["pagination"]["total"] == 1
        assert body["pagination"]["pages"] == 1
        assert isinstance(body["data"], list) and len(body["data"]) == 1

    async def test_list_per_page_over_100_422(
        self, client: AsyncClient, test_superuser: User
    ):
        """Bornes canoniques : per_page > 100 → 422 (pas de clamp)."""
        response = await client.get(
            f"{SSH_KEYS_URL}?per_page=101",
            headers=_auth_headers(test_superuser),
        )
        assert response.status_code == 422


class TestDetailRenameDelete:
    """GET/PUT/DELETE /ssh-keys/{id}."""

    async def test_get_unknown_404(self, client: AsyncClient, test_superuser: User):
        response = await client.get(
            f"{SSH_KEYS_URL}/missing-id", headers=_auth_headers(test_superuser)
        )
        assert response.status_code == 404
        assert error_code(response) == "NOT_FOUND"

    async def test_rename_200(self, client: AsyncClient, test_superuser: User):
        headers = _auth_headers(test_superuser)
        body = await _generate_key(client, headers, "before")
        response = await client.put(
            f"{SSH_KEYS_URL}/{body['id']}",
            json={"name": "after"},
            headers=headers,
        )
        assert response.status_code == 200
        assert unwrap(response)["name"] == "after"

    async def test_rename_conflict_409(self, client: AsyncClient, test_superuser: User):
        headers = _auth_headers(test_superuser)
        await _generate_key(client, headers, "taken")
        other = await _generate_key(client, headers, "other")
        response = await client.put(
            f"{SSH_KEYS_URL}/{other['id']}",
            json={"name": "taken"},
            headers=headers,
        )
        assert response.status_code == 409

    async def test_delete_referenced_409_then_force_204(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        """AC 1 : suppression refusée (409) si référencée ; ``force=true``
        → 204 + cibles déréférencées."""
        headers = _auth_headers(test_superuser)
        body = await _generate_key(client, headers, "referenced")
        db_session.add(
            Host(
                name="holder",
                host="h",
                credentials={},
                organization_id=test_organization.id,
                ssh_key_id=body["id"],
            )
        )
        await db_session.commit()

        refused = await client.delete(f"{SSH_KEYS_URL}/{body['id']}", headers=headers)
        assert refused.status_code == 409
        assert error_code(refused) == "CONFLICT"

        forced = await client.delete(
            f"{SSH_KEYS_URL}/{body['id']}?force=true", headers=headers
        )
        assert forced.status_code == 204

        # La cible est déréférencée (ssh_key_id NULL) et la clé supprimée.
        target = (
            await db_session.execute(select(Host).where(Host.name == "holder"))
        ).scalar_one()
        assert target.ssh_key_id is None
        remaining = (await db_session.execute(select(SSHKey.id))).scalars().all()
        assert body["id"] not in remaining

    async def test_delete_unreferenced_204(
        self, client: AsyncClient, test_superuser: User
    ):
        headers = _auth_headers(test_superuser)
        body = await _generate_key(client, headers, "free")
        response = await client.delete(f"{SSH_KEYS_URL}/{body['id']}", headers=headers)
        assert response.status_code == 204

    async def test_delete_unknown_404(self, client: AsyncClient, test_superuser: User):
        response = await client.delete(
            f"{SSH_KEYS_URL}/missing-id", headers=_auth_headers(test_superuser)
        )
        assert response.status_code == 404


class TestSecurity:
    """Sécurité systématique : 401/403/422 + zéro secret exposé."""

    async def test_all_endpoints_401_without_token(self, client: AsyncClient):
        """401 sans token sur les 6 verbes/paths."""
        for method, path in [
            ("get", SSH_KEYS_URL),
            ("post", f"{SSH_KEYS_URL}/generate"),
            ("post", f"{SSH_KEYS_URL}/import"),
            ("get", f"{SSH_KEYS_URL}/some-id"),
            ("put", f"{SSH_KEYS_URL}/some-id"),
            ("delete", f"{SSH_KEYS_URL}/some-id"),
        ]:
            response = await getattr(client, method)(path)
            assert response.status_code == 401, f"{method} {path}"

    async def test_all_endpoints_403_for_viewer_and_operator(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_organization,
    ):
        """403 pour viewer ET operator (admin requis — spec 08)."""
        viewer = await create_user_with_role(
            db_session, test_organization, Role.VIEWER, suffix="v7"
        )
        operator = await create_user_with_role(
            db_session, test_organization, Role.OPERATOR, suffix="o7"
        )
        for user in (viewer, operator):
            headers = _auth_headers(user)
            for method, path, kwargs in [
                ("get", SSH_KEYS_URL, {}),
                ("post", f"{SSH_KEYS_URL}/generate", {"json": {"name": "x"}}),
                (
                    "post",
                    f"{SSH_KEYS_URL}/import",
                    {"json": {"name": "x", "private_key": "p"}},
                ),
                ("get", f"{SSH_KEYS_URL}/some-id", {}),
                ("put", f"{SSH_KEYS_URL}/some-id", {"json": {"name": "x"}}),
                ("delete", f"{SSH_KEYS_URL}/some-id", {}),
            ]:
                response = await getattr(client, method)(
                    path, headers=headers, **kwargs
                )
                assert (
                    response.status_code == 403
                ), f"{user.username} {method} {path} -> {response.status_code}"

    async def test_invalid_bodies_422(self, client: AsyncClient, test_superuser: User):
        """422 : name vide, key_type inconnu, body manquant."""
        headers = _auth_headers(test_superuser)
        cases = [
            (f"{SSH_KEYS_URL}/generate", {"name": ""}),
            (f"{SSH_KEYS_URL}/generate", {"name": "ok", "key_type": "ecdsa"}),
            (f"{SSH_KEYS_URL}/generate", {}),
            (f"{SSH_KEYS_URL}/import", {"name": "x"}),
        ]
        for path, payload in cases:
            response = await client.post(path, json=payload, headers=headers)
            assert response.status_code == 422, f"{path} {payload}"

    async def test_no_secret_in_responses_nor_logs(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        caplog,
    ):
        """Aucun champ/clé privée ni passphrase dans les réponses et logs."""
        passphrase = "api-log-secret"
        encrypted_pem = (
            asyncssh.generate_private_key("ssh-ed25519")
            .export_private_key(passphrase=passphrase)
            .decode()
        )
        headers = _auth_headers(test_superuser)

        with caplog.at_level(logging.DEBUG):
            gen = await client.post(
                f"{SSH_KEYS_URL}/generate", json={"name": "log-gen"}, headers=headers
            )
            imp = await client.post(
                f"{SSH_KEYS_URL}/import",
                json={
                    "name": "log-imp",
                    "private_key": encrypted_pem,
                    "passphrase": passphrase,
                },
                headers=headers,
            )
            assert imp.status_code == 201, imp.text
            list_all = await client.get(SSH_KEYS_URL, headers=headers)
            assert gen.status_code == 201

        # Réponses de consultation : aucun matériau.
        body = list_all.text
        assert "private_key" not in body.replace('private_key": null', "")
        assert passphrase not in body
        assert "decrypted_private_key" not in body
        assert "private_key_encrypted" not in body

        # Base : token Fernet uniquement (jamais de PEM clair).
        rows = (await db_session.execute(select(SSHKey))).scalars().all()
        for row in rows:
            assert row.private_key_encrypted.startswith("gAAAA")
            assert "BEGIN OPENSSH PRIVATE KEY" not in row.private_key_encrypted
            assert passphrase not in row.private_key_encrypted

        # Logs : ni PEM ni passphrase.
        assert "BEGIN OPENSSH PRIVATE KEY" not in caplog.text
        assert passphrase not in caplog.text
