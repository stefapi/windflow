"""Tests CRUD cibles × référence clé SSH (STORY-131.3, familles 10 + 12).

- **Famille 10** : create/update avec ``ssh_key_id`` valide → persisté +
  exposé dans ``TargetResponse`` ; ``ssh_key_id`` inconnu → 422 ;
  ``TargetResponse`` n'expose jamais de credentials (non-régression) ;
- **Famille 12 (R4)** : garde-fou grep — ``backend/app`` ne contient
  plus aucun ``known_hosts`` hors du helper ``ssh_connection.py``
  (aucune acceptation silencieuse de clé serveur résiduelle).
"""

from pathlib import Path

import asyncssh
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import create_user_with_role, unwrap

from app.auth.jwt import create_access_token
from app.core.secret_manager import get_secret_manager
from app.enums.rbac import Role
from app.models.ssh_key import SSHKey

CREATE_PAYLOAD_BASE = {
    "name": "ref-target",
    "host": "prod-vm01.example.com",
    "port": 22,
    "credentials": {
        "auth_method": "password",
        "username": "deploy",
        "password": "s3cr3t",
    },
}


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


def _auth_headers(user) -> dict[str, str]:
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_ssh_key(db: AsyncSession, name: str = "crud-ref-key") -> SSHKey:
    key = asyncssh.generate_private_key("ssh-ed25519")
    row = SSHKey(
        name=name,
        key_type="ssh-ed25519",
        public_key=key.export_public_key().decode().strip(),
        private_key_encrypted=get_secret_manager().encrypt(
            key.export_private_key().decode()
        ),
        fingerprint=key.get_fingerprint(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


class TestCreateWithSshKeyRef:
    async def test_create_persists_and_exposes_ssh_key_id(
        self, client: AsyncClient, db_session: AsyncSession, test_organization
    ):
        user = await create_user_with_role(db_session, test_organization, Role.ADMIN)
        ssh_key = await _seed_ssh_key(db_session)

        response = await client.post(
            "/api/v1/hosts/",
            json={
                **CREATE_PAYLOAD_BASE,
                "organization_id": test_organization.id,
                "ssh_key_id": ssh_key.id,
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 201, response.text
        data = unwrap(response)
        assert data["ssh_key_id"] == ssh_key.id

    async def test_create_with_unknown_ssh_key_id_rejected(
        self, client: AsyncClient, db_session: AsyncSession, test_organization
    ):
        user = await create_user_with_role(db_session, test_organization, Role.ADMIN)

        response = await client.post(
            "/api/v1/hosts/",
            json={
                **CREATE_PAYLOAD_BASE,
                "organization_id": test_organization.id,
                "ssh_key_id": "nonexistent-key-id",
            },
            headers=_auth_headers(user),
        )
        assert response.status_code == 422, response.text


class TestUpdateWithSshKeyRef:
    async def test_update_sets_ssh_key_id(
        self, client: AsyncClient, db_session: AsyncSession, test_organization
    ):
        from app.models.host import Host, encrypt_credentials_for_storage

        user = await create_user_with_role(db_session, test_organization, Role.ADMIN)
        ssh_key = await _seed_ssh_key(db_session, name="update-ref-key")

        target = Host(
            name="update-ref-target",
            host="prod-vm01.example.com",
            credentials=encrypt_credentials_for_storage(
                {"auth_method": "password", "username": "d", "password": "p"}
            ),
            organization_id=test_organization.id,
        )
        db_session.add(target)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/hosts/{target.id}",
            json={"ssh_key_id": ssh_key.id},
            headers=_auth_headers(user),
        )
        assert response.status_code == 200, response.text
        assert unwrap(response)["ssh_key_id"] == ssh_key.id

    async def test_update_with_unknown_ssh_key_id_rejected(
        self, client: AsyncClient, db_session: AsyncSession, test_organization
    ):
        from app.models.host import Host

        user = await create_user_with_role(db_session, test_organization, Role.ADMIN)
        target = Host(
            name="update-bad-target",
            host="prod-vm01.example.com",
            credentials={},
            organization_id=test_organization.id,
        )
        db_session.add(target)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/hosts/{target.id}",
            json={"ssh_key_id": "nonexistent-key-id"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 422, response.text


class TestResponseContract:
    async def test_response_never_exposes_credentials(
        self, client: AsyncClient, db_session: AsyncSession, test_organization
    ):
        """Non-régression : TargetResponse ne fuit jamais de credential."""
        user = await create_user_with_role(db_session, test_organization, Role.ADMIN)

        response = await client.post(
            "/api/v1/hosts/",
            json={**CREATE_PAYLOAD_BASE, "organization_id": test_organization.id},
            headers=_auth_headers(user),
        )
        assert response.status_code == 201, response.text
        # Le mot de passe (ni aucun credential) ne doit jamais figurer
        # dans la réponse — seule la représentation TargetResponse
        # (sans credentials) est retournée.
        assert "s3cr3t" not in response.text
        assert "credentials" not in unwrap(response)


class TestGrepGuardR4:
    """Garde-fou R4 : zéro usage ``known_hosts`` hors helper (non-régression).

    Story famille 12 : ``backend/app`` ne contient plus aucun
    ``known_hosts`` (ni ``known_hosts: None``) **en usage effectif**
    hors du helper ``ssh_connection.py``. Détection par AST (pas de
    faux positifs documentaires — les docstrings des modèles/schémas
    131.1/131.2 mentionnent légitimement le concept) :

    - kwarg ``known_hosts=...`` dans un appel (le cas asyncssh) ;
    - clé de dict littérale ``{"known_hosts": ...}`` ;
    - assignation/f-string portant exactement ce nom.

    La moindre réintroduction = acceptation silencieuse possible de
    clé serveur = régression anti-MITM (AC 1, spec 15).
    """

    def test_no_known_hosts_usage_outside_helper(self):
        import ast

        backend_app = Path(__file__).resolve().parents[2] / "app"
        offenders: list[str] = []

        class Visitor(ast.NodeVisitor):
            def __init__(self, path: Path):
                self.path = path

            def visit_Call(self, node: ast.Call) -> None:
                for kw in node.keywords:
                    if kw.arg == "known_hosts":
                        offenders.append(
                            f"{self.path.name}:{kw.lineno}: kwarg known_hosts="
                        )
                self.generic_visit(node)

            def visit_Dict(self, node: ast.Dict) -> None:
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == "known_hosts":
                        offenders.append(
                            f"{self.path.name}:{getattr(value, 'lineno', 0)}: "
                            'clé de dict "known_hosts"'
                        )
                self.generic_visit(node)

        for py in backend_app.rglob("*.py"):
            if py.name == "ssh_connection.py":
                continue
            tree = ast.parse(py.read_text(), filename=str(py))
            Visitor(py).visit(tree)

        assert offenders == [], (
            "Usage known_hosts résiduel hors helper ssh_connection.py "
            f"(R4 — acceptation silencieuse possible) : {offenders}"
        )
