"""Tests API admin stacks-management : verdict moteur unique (STORY-171 — AC 1).

Couvre ``GET /definitions``, ``POST /validate``, ``GET /health`` :
- **Sécurité obligatoire** (rules 40) : 401 sans token, 403 pour
  viewer/operator/admin d'org (registre super-admin — non-régression
  STORY-122.6) ;
- **AC 1** : les YAML réels du dépôt (postgresql ET baserow) ressortent
  **valides** via l'API admin — même verdict que le seed ;
- Cas invalides (répertoire ``tmp_path`` substitué) : ``is_valid: false`` +
  ``validation_errors`` localisant le champ fautif, YAML mal formé → invalide
  sans 500, erreurs **sans valeur d'input** ;
- 404 répertoire absent (comportement existant conservé).
"""

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

import app.api.v1.admin.stacks_management as admin_module
from app.auth.jwt import create_access_token
from app.core.cache import reset_role_cache
from app.enums.rbac import Role
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.user_service import UserService

PREFIX = "/api/v1/admin/stacks-management"


@pytest.fixture(autouse=True)
def _fresh_role_cache():
    """Cache de rôles vierge autour de chaque test (pattern 122.7)."""
    reset_role_cache()
    yield
    reset_role_cache()


VALID_YAML = (
    "metadata:\n"
    "  name: demo\n"
    "  version: 1.0.0\n"
    "  category: demo\n"
    "  author: WindFlow Team\n"
    "  license: MIT\n"
    "  description: Demo stack\n"
    "  target_type: docker\n"
    "template:\n"
    "  image: nginx:latest\n"
    "variables:\n"
    "  host_port:\n"
    "    type: integer\n"
    "    label: Port\n"
    "    default: 8080\n"
    "    minimum: 1\n"
    "    maximum: 65535\n"
)

INVALID_YAML = (
    "metadata:\n"
    "  name: bad\n"
    "  version: 1.0.0\n"
    "  category: demo\n"
    "  author: WindFlow Team\n"
    "  license: MIT\n"
    "  description: Bad stack\n"
    "  target_type: docker\n"
    "template:\n"
    "  image: nginx:latest\n"
    "variables:\n"
    "  host_port:\n"
    "    type: enum\n"  # pseudo-type inexistant du schéma strict
    "    label: Port\n"
)


async def _create_user_with_role(
    db_session: AsyncSession, username: str, role: Role
) -> User:
    from app.models.organization import Organization
    from app.models.user_organization import UserOrganization

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
    return user


async def _create_superuser(db_session: AsyncSession, username: str) -> User:
    return await UserService.create(
        db_session,
        UserCreate(
            email=f"{username}@example.com",
            username=username,
            full_name=username.title(),
            password="password123",
            is_superuser=True,
        ),
    )


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


REPO_DEFINITIONS_DIR = (
    Path(__file__).parent.parent.parent.parent.parent / "stacks_definitions"
)


def _redirect_definitions_dir(monkeypatch, target_dir: Path) -> Path:
    """Substitue le répertoire stacks_definitions résolu par le routeur.

    Le routeur dérive le chemin depuis ``Path(__file__)`` du module admin
    (layout Docker) ; en dev local ce chemin n'existe pas. Le monkeypatch
    redirige **uniquement** la division par ``"stacks_definitions"`` vers
    ``target_dir`` — toutes les autres divisions de Path (y compris celles
    du test lui-même) restent intactes.
    """
    original_truediv = Path.__truediv__

    def _selective_truediv(self, other):
        if other == "stacks_definitions":
            return target_dir
        return original_truediv(self, other)

    monkeypatch.setattr(admin_module.Path, "__truediv__", _selective_truediv)
    return target_dir


def _tmp_definitions_dir(tmp_path: Path) -> Path:
    """Répertoire temporaire stacks_definitions pour les cas invalides."""
    definitions_dir = tmp_path / "stacks_definitions"
    definitions_dir.mkdir(exist_ok=True)
    return definitions_dir


# --- Sécurité obligatoire (rules 40 — matrice 401/403) ------------------------


class TestSecurityMatrix:
    """Sécurité : super-admin uniquement — non-régression STORY-122.6."""

    async def test_definitions_returns_401_without_token(self, client: AsyncClient):
        """Sécurité : GET /definitions sans token → 401."""
        response = await client.get(f"{PREFIX}/definitions")
        assert response.status_code == 401

    async def test_validate_returns_401_without_token(self, client: AsyncClient):
        """Sécurité : POST /validate sans token → 401."""
        response = await client.post(f"{PREFIX}/validate")
        assert response.status_code == 401

    async def test_health_returns_401_without_token(self, client: AsyncClient):
        """Sécurité : GET /health sans token → 401."""
        response = await client.get(f"{PREFIX}/health")
        assert response.status_code == 401

    async def test_definitions_returns_403_for_org_admin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sécurité clé : admin d'organisation (non-superuser) → 403."""
        user = await _create_user_with_role(db_session, "wf171-admin", Role.ADMIN)
        response = await client.get(
            f"{PREFIX}/definitions", headers=_auth_headers(user)
        )
        assert response.status_code == 403

    async def test_definitions_returns_403_for_viewer(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sécurité : viewer → 403 (registre système)."""
        user = await _create_user_with_role(db_session, "wf171-viewer", Role.VIEWER)
        response = await client.get(
            f"{PREFIX}/definitions", headers=_auth_headers(user)
        )
        assert response.status_code == 403

    async def test_definitions_returns_403_for_operator(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sécurité : operator → 403 (échantillon matrice)."""
        user = await _create_user_with_role(db_session, "wf171-oper", Role.OPERATOR)
        response = await client.get(
            f"{PREFIX}/definitions", headers=_auth_headers(user)
        )
        assert response.status_code == 403

    async def test_validate_returns_403_for_non_superadmin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sécurité : POST /validate pour admin d'org → 403."""
        user = await _create_user_with_role(db_session, "wf171-admin2", Role.ADMIN)
        response = await client.post(f"{PREFIX}/validate", headers=_auth_headers(user))
        assert response.status_code == 403


# --- AC 1 : YAML réels du dépôt → valides via l'API admin ---------------------


class TestRepoYamlsAllValid:
    """AC 1 : postgresql.yaml ET baserow.yaml valides côté admin (bug corrigé)."""

    async def test_definitions_all_repo_yamls_valid(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ):
        """Inventaire : chaque YAML du dépôt (non ``_``) → ``is_valid: true``."""
        _redirect_definitions_dir(monkeypatch, REPO_DEFINITIONS_DIR)
        user = await _create_superuser(db_session, "wf171-sa-def")
        response = await client.get(
            f"{PREFIX}/definitions",
            headers=_auth_headers(user),
            params={"per_page": 100},
        )
        assert response.status_code == 200

        data = unwrap(response)
        items = data["data"] if isinstance(data, dict) and "data" in data else data
        # Le répertoire réel contient postgresql.yaml et baserow.yaml
        names = {item["filename"] for item in items}
        assert {"postgresql.yaml", "baserow.yaml"} <= names

        for item in items:
            assert (
                item["is_valid"] is True
            ), f"{item['filename']} invalide: {item.get('validation_errors')}"
            assert item["validation_errors"] is None
            assert item["name"] != "N/A"

    async def test_validate_all_valid_on_repo_yamls(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ):
        """Validation globale : ``all_valid: true``, ``invalid: 0`` (AC 1)."""
        _redirect_definitions_dir(monkeypatch, REPO_DEFINITIONS_DIR)
        user = await _create_superuser(db_session, "wf171-sa-val")
        response = await client.post(f"{PREFIX}/validate", headers=_auth_headers(user))
        assert response.status_code == 200

        body = unwrap(response)
        assert body["all_valid"] is True
        assert body["invalid"] == 0
        assert body["errors"] == []

    async def test_postgresql_and_baserow_were_the_bug_cases(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch
    ):
        """Régression : les deux fichiers utilisant ``type: integer`` sont valides."""
        _redirect_definitions_dir(monkeypatch, REPO_DEFINITIONS_DIR)
        user = await _create_superuser(db_session, "wf171-sa-bug")
        response = await client.get(
            f"{PREFIX}/definitions",
            headers=_auth_headers(user),
            params={"per_page": 100},
        )
        assert response.status_code == 200

        data = unwrap(response)
        items = data["data"] if isinstance(data, dict) and "data" in data else data
        by_name = {item["filename"]: item for item in items}

        pg = by_name["postgresql.yaml"]
        assert pg["is_valid"] is True
        assert pg["variables_count"] >= 1

        bw = by_name["baserow.yaml"]
        assert bw["is_valid"] is True


# --- Cas invalides : verdict détaillé sans 500 --------------------------------


class TestInvalidDefinitionsVerdict:
    """Fichiers invalides → ``is_valid: false`` + erreurs localisées, pas de 500."""

    async def test_definitions_invalid_file_reports_field(
        self, client, db_session, tmp_path, monkeypatch
    ):
        """Invalide : ``validation_errors`` contient le champ fautif (ex. type)."""
        _redirect_definitions_dir(monkeypatch, _tmp_definitions_dir(tmp_path))
        (tmp_path / "stacks_definitions" / "bad.yaml").write_text(
            INVALID_YAML, encoding="utf-8"
        )
        user = await _create_superuser(db_session, "wf171-sa-inv")

        response = await client.get(
            f"{PREFIX}/definitions", headers=_auth_headers(user)
        )
        assert response.status_code == 200

        data = unwrap(response)
        items = data["data"] if isinstance(data, dict) and "data" in data else data
        assert len(items) == 1
        item = items[0]
        assert item["is_valid"] is False
        assert item["validation_errors"], "erreurs de validation attendues"
        # Champ fautif localisé (variables.host_port.type)
        assert any("host_port" in err for err in item["validation_errors"])

    async def test_validate_aggregates_errors_without_500(
        self, client, db_session, tmp_path, monkeypatch
    ):
        """POST /validate agrège {file, error} sans lever 500."""
        _redirect_definitions_dir(monkeypatch, _tmp_definitions_dir(tmp_path))
        (tmp_path / "stacks_definitions" / "bad.yaml").write_text(
            INVALID_YAML, encoding="utf-8"
        )
        user = await _create_superuser(db_session, "wf171-sa-agg")

        response = await client.post(f"{PREFIX}/validate", headers=_auth_headers(user))
        assert response.status_code == 200

        body = unwrap(response)
        assert body["all_valid"] is False
        assert body["invalid"] == 1
        assert body["errors"][0]["file"] == "bad.yaml"
        assert "host_port" in body["errors"][0]["error"]

    async def test_malformed_yaml_invalid_not_500(
        self, client, db_session, tmp_path, monkeypatch
    ):
        """YAML syntaxiquement invalide → invalide (pas d'exception/500)."""
        _redirect_definitions_dir(monkeypatch, _tmp_definitions_dir(tmp_path))
        (tmp_path / "stacks_definitions" / "broken.yaml").write_text(
            "metadata: [unclosed\n  bad", encoding="utf-8"
        )
        user = await _create_superuser(db_session, "wf171-sa-yaml")

        response = await client.get(
            f"{PREFIX}/definitions", headers=_auth_headers(user)
        )
        assert response.status_code == 200
        data = unwrap(response)
        items = data["data"] if isinstance(data, dict) and "data" in data else data
        assert items[0]["is_valid"] is False

        response = await client.post(f"{PREFIX}/validate", headers=_auth_headers(user))
        assert response.status_code == 200
        body = unwrap(response)
        assert body["all_valid"] is False

    async def test_errors_do_not_expose_input_value(
        self, client, db_session, tmp_path, monkeypatch
    ):
        """Rules 40 : la valeur d'input (ex. ``enum``) n'apparaît pas dans les
        messages servis."""
        _redirect_definitions_dir(monkeypatch, _tmp_definitions_dir(tmp_path))
        # target_type invalide “lxd” : la valeur fautive ne doit pas fuiter
        content = VALID_YAML.replace("target_type: docker", "target_type: lxd")
        (tmp_path / "stacks_definitions" / "leaky.yaml").write_text(
            content, encoding="utf-8"
        )
        user = await _create_superuser(db_session, "wf171-sa-leak")

        response = await client.get(
            f"{PREFIX}/definitions", headers=_auth_headers(user)
        )
        assert response.status_code == 200
        data = unwrap(response)
        items = data["data"] if isinstance(data, dict) and "data" in data else data
        errors_text = " ".join(items[0]["validation_errors"])
        assert "lxd" not in errors_text
        assert "target_type" in errors_text

    async def test_underscore_files_skipped(
        self, client, db_session, tmp_path, monkeypatch
    ):
        """Skip des fichiers ``_`` conservé à l'identique (STORY-122.6/171)."""
        _redirect_definitions_dir(monkeypatch, _tmp_definitions_dir(tmp_path))
        d = tmp_path / "stacks_definitions"
        (d / "_skipme.yaml").write_text("invalid: [", encoding="utf-8")
        (d / "good.yaml").write_text(VALID_YAML, encoding="utf-8")
        user = await _create_superuser(db_session, "wf171-sa-skip")

        response = await client.post(f"{PREFIX}/validate", headers=_auth_headers(user))
        assert response.status_code == 200
        body = unwrap(response)
        assert body["all_valid"] is True  # _skipme ignoré

    async def test_missing_directory_404(
        self, client, db_session, tmp_path, monkeypatch
    ):
        """404 répertoire absent (comportement existant conservé)."""
        missing = tmp_path / "inexistant"
        monkeypatch.setattr(
            admin_module.Path, "__truediv__", lambda self, other: missing
        )
        user = await _create_superuser(db_session, "wf171-sa-404")

        response = await client.get(
            f"{PREFIX}/definitions", headers=_auth_headers(user)
        )
        assert response.status_code == 404

        response = await client.post(f"{PREFIX}/validate", headers=_auth_headers(user))
        assert response.status_code == 404
