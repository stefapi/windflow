"""Tests API du sous-router empreintes SSH (STORY-131.2, famille 8).

Couvre les trois endpoints ``/targets/{id}/ssh-fingerprints*`` :

- **GET liste** : 200 avec statut TOFU (accepted/pending) ; isolation
  org — une cible d'une org étrangère est **404** (pattern
  ``test_rbac_isolation.py`` : cible inexistante ou étrangère
  traitée à l'identique, pas d'oracle d'existence) ;
- **POST accept** : 200 nominal (PENDING matching + empreinte
  identique → accepted/accepted_at + event + audit), 409 si
  fingerprint soumis ≠ stocké (anti-MITM), 404 cible inconnue ou
  aucun PENDING matching, 422 payload incomplet ;
- **DELETE reset** : 204 + re-acceptation requise ;
- **sécurité** : 401 sans token / 403 viewer **et** operator sur les
  trois verbes (admin requis — matrice spec 08) ;
- **audit** : ligne ``target.fingerprint_accepted`` écrite en base
  (pattern ``test_audit_emission.py`` — assert sur ``audit_logs``).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.conftest import create_user_with_role, error_code, unwrap

from app.auth.jwt import create_access_token
from app.enums.rbac import Role
from app.models.audit_log import AuditLog
from app.models.host_ssh_fingerprint import HostSSHFingerprint
from app.models.organization import Organization
from app.models.target import Target
from app.models.user import User

FP_STORED = "SHA256:" + "B" * 43
FP_OTHER = "SHA256:" + "C" * 43

HOST = "prod-vm01.example.com"


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 123.4."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


@pytest.fixture(autouse=True)
async def _audit_db(monkeypatch, test_session_factory: async_sessionmaker) -> None:
    """Redirige les sessions courtes d'audit vers la base de test
    (pattern test_audit_emission.py)."""
    import app.services.audit_service as audit_service_module

    monkeypatch.setattr(audit_service_module, "AsyncSessionLocal", test_session_factory)


def _auth_headers(user: User) -> dict[str, str]:
    """Headers Bearer mintés directement (pattern test_api_keys)."""
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_target_with_fp(
    db_session: AsyncSession,
    organization_id: str,
    *,
    name: str = "fp-target",
    accepted: bool = False,
) -> tuple[Target, HostSSHFingerprint]:
    """Cible + empreinte (PENDING par défaut — TOFU)."""
    target = Target(
        name=name,
        host=HOST,
        credentials={},
        organization_id=organization_id,
    )
    db_session.add(target)
    await db_session.flush()
    fp = HostSSHFingerprint(
        host_id=target.id,
        hostname=HOST,
        port=22,
        key_type="ssh-ed25519",
        fingerprint=FP_STORED,
        accepted=accepted,
    )
    db_session.add(fp)
    await db_session.commit()
    await db_session.refresh(fp)
    return target, fp


def _accept_payload(fingerprint: str = FP_STORED) -> dict:
    return {
        "hostname": HOST,
        "port": 22,
        "key_type": "ssh-ed25519",
        "fingerprint": fingerprint,
    }


class TestListFingerprints:
    """GET /targets/{id}/ssh-fingerprints."""

    async def test_list_200_with_tofu_status(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        target, fp = await _seed_target_with_fp(db_session, test_organization.id)
        response = await client.get(
            f"/api/v1/targets/{target.id}/ssh-fingerprints",
            headers=_auth_headers(test_superuser),
        )
        assert response.status_code == 200, response.text
        items = unwrap(response)
        assert isinstance(items, list) and len(items) == 1
        entry = items[0]
        assert entry["id"] == fp.id
        assert entry["accepted"] is False
        assert entry["accepted_at"] is None
        assert entry["fingerprint"] == FP_STORED

    async def test_list_unknown_target_404(
        self, client: AsyncClient, test_superuser: User
    ):
        response = await client.get(
            "/api/v1/targets/missing/ssh-fingerprints",
            headers=_auth_headers(test_superuser),
        )
        assert response.status_code == 404
        assert error_code(response) == "NOT_FOUND"

    async def test_list_foreign_org_target_404(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        """Isolation org : cible d'une org dont même un admin local
        n'est pas membre → 404 (pas d'oracle d'existence)."""
        # Organisation étrangère + cible dedans.
        foreign_org = Organization(name="Foreign Org", slug="foreign-org")
        db_session.add(foreign_org)
        await db_session.flush()
        foreign_target = Target(
            name="foreign-target",
            host=HOST,
            credentials={},
            organization_id=foreign_org.id,
        )
        db_session.add(foreign_target)
        await db_session.commit()

        # Admin (non-superuser) de test_organization uniquement.
        org_admin = await create_user_with_role(
            db_session, test_organization, Role.ADMIN, suffix="iso1"
        )
        response = await client.get(
            f"/api/v1/targets/{foreign_target.id}/ssh-fingerprints",
            headers=_auth_headers(org_admin),
        )
        assert response.status_code == 404


class TestAcceptFingerprint:
    """POST /targets/{id}/ssh-fingerprints/accept."""

    async def test_accept_nominal_200(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        """PENDING matching + empreinte identique → 200 accepted=True."""
        target, fp = await _seed_target_with_fp(db_session, test_organization.id)
        response = await client.post(
            f"/api/v1/targets/{target.id}/ssh-fingerprints/accept",
            json=_accept_payload(),
            headers=_auth_headers(test_superuser),
        )
        assert response.status_code == 200, response.text
        body = unwrap(response)
        assert body["accepted"] is True
        assert body["accepted_at"] is not None

        await db_session.refresh(fp)
        assert fp.accepted is True and fp.accepted_at is not None

    async def test_accept_divergent_fingerprint_409(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        """Anti-MITM : payload fingerprint ≠ stocké → 409, ligne
        inchangée (jamais d'écrasement silencieux)."""
        target, fp = await _seed_target_with_fp(db_session, test_organization.id)
        response = await client.post(
            f"/api/v1/targets/{target.id}/ssh-fingerprints/accept",
            json=_accept_payload(fingerprint=FP_OTHER),
            headers=_auth_headers(test_superuser),
        )
        assert response.status_code == 409
        assert error_code(response) == "CONFLICT"

        await db_session.refresh(fp)
        assert fp.accepted is False

    async def test_accept_no_pending_matching_404(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        """Aucune ligne PENDING ne matche (hostname inconnu) → 404."""
        target, _ = await _seed_target_with_fp(db_session, test_organization.id)
        payload = _accept_payload()
        payload["hostname"] = "other-host.example.com"
        response = await client.post(
            f"/api/v1/targets/{target.id}/ssh-fingerprints/accept",
            json=payload,
            headers=_auth_headers(test_superuser),
        )
        assert response.status_code == 404

    async def test_accept_already_accepted_not_matched_again(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        """Une ligne déjà accepted n'est plus PENDING → re-accepter la
        même identité → 404 (plus aucun PENDING matching)."""
        target, _ = await _seed_target_with_fp(
            db_session, test_organization.id, accepted=True
        )
        response = await client.post(
            f"/api/v1/targets/{target.id}/ssh-fingerprints/accept",
            json=_accept_payload(),
            headers=_auth_headers(test_superuser),
        )
        assert response.status_code == 404

    async def test_accept_unknown_target_404(
        self, client: AsyncClient, test_superuser: User
    ):
        response = await client.post(
            "/api/v1/targets/missing/ssh-fingerprints/accept",
            json=_accept_payload(),
            headers=_auth_headers(test_superuser),
        )
        assert response.status_code == 404

    async def test_accept_incomplete_payload_422(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        """422 : fingerprint manquant / malformé / port invalide."""
        target, _ = await _seed_target_with_fp(db_session, test_organization.id)
        base = _accept_payload()
        cases = [
            {k: v for k, v in base.items() if k != "fingerprint"},
            {**base, "fingerprint": "md5:not-a-sha256"},
            {**base, "port": 99999},
        ]
        for payload in cases:
            response = await client.post(
                f"/api/v1/targets/{target.id}/ssh-fingerprints/accept",
                json=payload,
                headers=_auth_headers(test_superuser),
            )
            assert response.status_code == 422, payload

    async def test_accept_writes_audit_line(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        """Audit : ligne ``target.fingerprint_accepted`` en base avec
        acteur et cible (pattern test_audit_emission.py)."""
        target, fp = await _seed_target_with_fp(db_session, test_organization.id)
        response = await client.post(
            f"/api/v1/targets/{target.id}/ssh-fingerprints/accept",
            json=_accept_payload(),
            headers=_auth_headers(test_superuser),
        )
        assert response.status_code == 200

        lines = (
            (
                await db_session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "target.fingerprint_accepted"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert lines, "la ligne d'audit d'acceptation doit exister"
        line = lines[-1]
        assert line.user_id == test_superuser.id
        assert line.resource_id == fp.id
        assert line.details["fingerprint"] == FP_STORED

    async def test_accept_emits_event(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        """Event ``HOST_SSH_FINGERPRINT_ACCEPTED`` publié sur le bus."""
        from app.api.v1.targets import fingerprints as fp_module
        from app.core.events import EventType

        target, _ = await _seed_target_with_fp(db_session, test_organization.id)
        emitted: list = []
        original = fp_module.event_bus.emit

        async def _spy(event_type, data):
            emitted.append((event_type, data))
            await original(event_type, data)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(fp_module.event_bus, "emit", _spy)
            response = await client.post(
                f"/api/v1/targets/{target.id}/ssh-fingerprints/accept",
                json=_accept_payload(),
                headers=_auth_headers(test_superuser),
            )
        assert response.status_code == 200
        assert any(
            et == EventType.HOST_SSH_FINGERPRINT_ACCEPTED for et, _ in emitted
        ), emitted
        payload = next(
            d for et, d in emitted if et == EventType.HOST_SSH_FINGERPRINT_ACCEPTED
        )
        assert payload["target_id"] == target.id
        assert payload["fingerprint"] == FP_STORED


class TestResetFingerprint:
    """DELETE /targets/{id}/ssh-fingerprints/{fp_id}."""

    async def test_reset_204(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        """Reset : 204 + ligne supprimée → re-acceptation requise."""
        target, fp = await _seed_target_with_fp(
            db_session, test_organization.id, accepted=True
        )
        response = await client.delete(
            f"/api/v1/targets/{target.id}/ssh-fingerprints/{fp.id}",
            headers=_auth_headers(test_superuser),
        )
        assert response.status_code == 204

        remaining = (
            await db_session.execute(
                select(HostSSHFingerprint).where(HostSSHFingerprint.id == fp.id)
            )
        ).scalar_one_or_none()
        assert remaining is None

    async def test_reset_unknown_fingerprint_404(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        """404 : fp_id inconnu ou appartenant à une autre cible."""
        target, _ = await _seed_target_with_fp(db_session, test_organization.id)
        response = await client.delete(
            f"/api/v1/targets/{target.id}/ssh-fingerprints/missing-fp",
            headers=_auth_headers(test_superuser),
        )
        assert response.status_code == 404

    async def test_reset_writes_audit_line(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization,
    ):
        target, fp = await _seed_target_with_fp(
            db_session, test_organization.id, accepted=True
        )
        response = await client.delete(
            f"/api/v1/targets/{target.id}/ssh-fingerprints/{fp.id}",
            headers=_auth_headers(test_superuser),
        )
        assert response.status_code == 204
        lines = (
            (
                await db_session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "target.fingerprint_reset"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert lines


class TestSecurity:
    """401 sans token / 403 viewer-operator sur les trois verbes."""

    async def test_all_401_without_token(self, client: AsyncClient):
        for method, path in [
            ("get", "/api/v1/targets/t1/ssh-fingerprints"),
            ("post", "/api/v1/targets/t1/ssh-fingerprints/accept"),
            ("delete", "/api/v1/targets/t1/ssh-fingerprints/f1"),
        ]:
            response = await getattr(client, method)(
                path, **({"json": _accept_payload()} if method == "post" else {})
            )
            assert response.status_code == 401, f"{method} {path}"

    async def test_all_403_for_viewer_and_operator(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_organization,
    ):
        viewer = await create_user_with_role(
            db_session, test_organization, Role.VIEWER, suffix="fpv"
        )
        operator = await create_user_with_role(
            db_session, test_organization, Role.OPERATOR, suffix="fpo"
        )
        for user in (viewer, operator):
            headers = _auth_headers(user)
            for method, path, kwargs in [
                ("get", "/api/v1/targets/t1/ssh-fingerprints", {}),
                (
                    "post",
                    "/api/v1/targets/t1/ssh-fingerprints/accept",
                    {"json": _accept_payload()},
                ),
                ("delete", "/api/v1/targets/t1/ssh-fingerprints/f1", {}),
            ]:
                response = await getattr(client, method)(
                    path, headers=headers, **kwargs
                )
                assert (
                    response.status_code == 403
                ), f"{user.username} {method} {path} -> {response.status_code}"
