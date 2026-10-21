"""Tests API du TOFU sur ``POST /targets/test-connection`` (STORY-131.3, famille 9).

Mode COLLECT (mock asyncssh — pas de réseau réel, rules 35) :

- réponse contenant ``host_fingerprint`` + ``fingerprint_status=
  "unknown"`` et **aucune ligne créée** en base après l'appel (AC 1
  « jamais d'ajout silencieux ») ;
- cas mismatch simulé → ``fingerprint_status="mismatch"`` et connexion
  refusée (``success=false``) ;
- nominal : connexion établie, empreinte jointe au message ;
- sécurité : 401 sans token, 403 viewer (Operator+ requis — RBAC
  inchangé par le refactor).
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import create_user_with_role, unwrap

from app.auth.jwt import create_access_token
from app.enums.rbac import Role
from app.models.host_ssh_fingerprint import HostSSHFingerprint
from app.services.ssh_connection import HostKeyCapture

FP_A = "SHA256:" + "A" * 43
FP_B = "SHA256:" + "B" * 43
HOST = "prod-vm01.example.com"

CRED_PASSWORD = {
    "auth_method": "password",
    "username": "deploy",
    "password": "s3cr3t",
}


class _FakeAsyncConnect:
    """Remplaçant d'``asyncssh.connect`` (double protocole await/async-with).

    Reproduit la sémantique réelle : l'établissement de la connexion
    (``__aenter__``) invoque ``server_host_key_verify`` ; un refus
    (callback ``False``) lève une erreur de connexion — l'endpoint
    n'obtient jamais de session vers un hôte non vérifié.
    """

    def __init__(self, kwargs: dict, fingerprint: str):
        self._kwargs = kwargs
        self._fingerprint = fingerprint

    def __await__(self):
        async def _coro():
            return self

        return _coro().__await__()

    async def __aenter__(self):
        key = MagicMock()
        key.get_fingerprint.return_value = self._fingerprint
        key.get_algorithm.return_value = "ssh-ed25519"
        accepted = await self._kwargs["server_host_key_verify"](
            self._kwargs["host"], "203.0.113.10", self._kwargs["port"],
            key, "ssh-ed25519",
        )
        if not accepted:
            raise ConnectionError("host key verification failed")
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def run(self, command, **kwargs):
        result = MagicMock()
        result.exit_status = 0
        result.stdout = "Linux prod-vm01 5.15\n"
        return result


def _patch_connect(fingerprint: str = FP_A):
    """Patch d'``asyncssh.connect`` côté module connectivity."""
    def factory(**kwargs):
        return _FakeAsyncConnect(kwargs, fingerprint)

    return patch(
        "app.api.v1.targets.connectivity.asyncssh.connect", side_effect=factory
    )


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (pattern 131.2)."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


def _auth_headers(user) -> dict[str, str]:
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


class TestCollectUnknown:
    """Premier contact : empreinte capturée, rien persisté."""

    async def test_unknown_fingerprint_returned_nothing_persisted(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_organization,
    ):
        user = await create_user_with_role(db_session, test_organization, Role.OPERATOR)

        with _patch_connect(FP_A):
            response = await client.post(
                "/api/v1/targets/test-connection",
                json={"host": HOST, "port": 22, "credentials": CRED_PASSWORD},
                headers=_auth_headers(user),
            )

        assert response.status_code == 200, response.text
        data = unwrap(response)
        assert data["success"] is True
        assert data["host_fingerprint"] == FP_A
        assert data["fingerprint_status"] == "unknown"

        rows = list(
            (await db_session.execute(select(HostSSHFingerprint))).scalars().all()
        )
        assert rows == []  # jamais d'ajout silencieux (AC 1)


class TestCollectMismatch:
    """Divergence : connexion refusée, statut mismatch exposé, rien écrit.

    Le mismatch n'est détectable que vis-à-vis d'une cible persistée
    (TOFU sur ``targets.id``) ; la requête test-connection ne portant
    pas de cible, on **simule le helper** (famille 9 : « cas mismatch
    simulé ») : le callback COLLECT produit une capture mismatch et
    refuse la négociation — l'endpoint doit refuser la connexion et
    exposer ``fingerprint_status="mismatch"``.
    """

    async def test_mismatch_refuses_connection(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_organization,
    ):
        user = await create_user_with_role(db_session, test_organization, Role.OPERATOR)

        async def fake_build_ssh_kwargs(db, **kwargs):
            captures: list[HostKeyCapture] = kwargs.setdefault(
                "capture_out", []
            )

            async def verify(_h, _a, _p, key, _alg):
                captures.append(
                    HostKeyCapture(
                        fingerprint=key.get_fingerprint(),
                        key_type="ssh-ed25519",
                        status="mismatch",
                        hostname=HOST,
                        port=22,
                        details={"expected_fingerprint": FP_A},
                    )
                )
                return False

            return {
                "host": kwargs["host"],
                "port": kwargs["port"],
                "username": kwargs["username"],
                "password": "s3cr3t",
                "server_host_key_verify": verify,
            }

        with patch(
            "app.api.v1.targets.connectivity.build_ssh_kwargs",
            side_effect=fake_build_ssh_kwargs,
        ):
            # asyncssh.connect non mocké : jamais atteint (kwargs
            # factices sans capture_out réel ? non — build fournit un
            # callback; connect serait appelé). On patche aussi connect
            # pour renvoyer un FakeAsyncConnect qui exécutera verify.
            def factory(**kw):
                return _FakeAsyncConnect(kw, FP_B)

            with patch(
                "app.api.v1.targets.connectivity.asyncssh.connect",
                side_effect=factory,
            ):
                response = await client.post(
                    "/api/v1/targets/test-connection",
                    json={"host": HOST, "port": 22, "credentials": CRED_PASSWORD},
                    headers=_auth_headers(user),
                )

        assert response.status_code == 200, response.text
        data = unwrap(response)
        assert data["success"] is False
        assert data["fingerprint_status"] == "mismatch"
        assert data["host_fingerprint"] == FP_B
        # Aucune écriture en base (lecture seule — jamais silencieux).
        rows = list(
            (await db_session.execute(select(HostSSHFingerprint))).scalars().all()
        )
        assert rows == []


class TestCollectAccepted:
    """Non-régression du flux nominal complet (session + OS info)."""

    async def test_successful_connection_returns_fingerprint(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_organization,
    ):
        user = await create_user_with_role(db_session, test_organization, Role.OPERATOR)

        with _patch_connect(FP_A):
            response = await client.post(
                "/api/v1/targets/test-connection",
                json={"host": HOST, "port": 22, "credentials": CRED_PASSWORD},
                headers=_auth_headers(user),
            )

        assert response.status_code == 200
        data = unwrap(response)
        assert data["success"] is True
        assert data["host_fingerprint"] == FP_A
        assert FP_A in data["message"]  # empreinte présentée au message


class TestSecurity:
    """RBAC inchangé par le refactor COLLECT."""

    async def test_returns_401_without_token(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/targets/test-connection",
            json={"host": HOST, "port": 22, "credentials": CRED_PASSWORD},
        )
        assert response.status_code == 401

    async def test_returns_403_for_viewer(
        self, client: AsyncClient, db_session: AsyncSession, test_organization
    ):
        user = await create_user_with_role(db_session, test_organization, Role.VIEWER)
        response = await client.post(
            "/api/v1/targets/test-connection",
            json={"host": HOST, "port": 22, "credentials": CRED_PASSWORD},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403
