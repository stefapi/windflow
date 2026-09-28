"""Tests RBAC du router admin instance (STORY-122.6, AC 2 volet admin).

Couvre les 15 routes ``/api/v1/admin/stacks-management/*`` — registre
système global réservé Super Admin (spec 08 § Système « Registres ») :
- **Matrice 403** : viewer / operator / admin d'organisation → 403 sur un
  échantillon GET + POST + PATCH + DELETE (l'admin d'org n'est PAS
  superuser — registre instance) ;
- **Superuser** : 200/404 selon la ressource (services non mockés → lecture
  réelle du répertoire ``stacks_definitions``) ;
- **401 sans token** (échantillon) ;
- **Non-régression structurelle** : 15 routes sous le préfixe ``/admin/``.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.core.cache import reset_role_cache
from app.enums.rbac import Role
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.schemas.user import UserCreate
from app.services.user_service import UserService

PREFIX = "/api/v1/admin/stacks-management"


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


async def _create_superuser(
    db_session: AsyncSession,
    username: str,
) -> User:
    """Crée un superuser (flag système — rôle global super_admin)."""
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


async def _create_admin_of_org(
    db_session: AsyncSession,
    username: str,
) -> tuple[User, Organization]:
    """Admin d'organisation (non-superuser) — le cas clé du registre."""
    return await _create_user_with_role(db_session, username, Role.ADMIN)


import pytest
from tests.conftest import unwrap


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


# --- Matrice 403 : tous rôles non-SA ----------------------------------------


class TestAdminForbiddenMatrix:
    """Sécurité : viewer/operator/admin d'org → 403 sur toutes les routes admin."""

    SAMPLE_ROUTES = [
        ("GET", f"{PREFIX}/definitions", None),
        ("POST", f"{PREFIX}/validate", None),
        ("GET", f"{PREFIX}/imported", None),
        ("GET", f"{PREFIX}/sync/status", None),
        ("GET", f"{PREFIX}/stats/overview", None),
        ("GET", f"{PREFIX}/health", None),
        ("GET", f"{PREFIX}/search", None),
    ]

    async def test_viewer_403_get_definitions(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sécurité : viewer sur GET /definitions → 403 « Not enough permissions »."""
        user, _org = await _create_user_with_role(db_session, "adm-v-get", Role.VIEWER)

        response = await client.get(
            f"{PREFIX}/definitions", headers=_auth_headers(user)
        )
        assert response.status_code == 403
        assert response.json()["error"]["message"] == "Not enough permissions"

    async def test_operator_403_get_definitions(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sécurité : operator sur GET /definitions → 403."""
        user, _org = await _create_user_with_role(
            db_session, "adm-o-get", Role.OPERATOR
        )

        response = await client.get(
            f"{PREFIX}/definitions", headers=_auth_headers(user)
        )
        assert response.status_code == 403

    async def test_org_admin_403_get_definitions(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sécurité clé : admin d'organisation (non-superuser) → 403 — le
        catalogue de stacks est un registre système global, pas une
        ressource d'organisation."""
        user, _org = await _create_admin_of_org(db_session, "adm-a-get")

        response = await client.get(
            f"{PREFIX}/definitions", headers=_auth_headers(user)
        )
        assert response.status_code == 403

    async def test_org_admin_403_post_import(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sécurité : admin d'org sur POST /import → 403 (avant toute écriture)."""
        user, _org = await _create_admin_of_org(db_session, "adm-a-imp")

        response = await client.post(
            f"{PREFIX}/import",
            json={},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403

    async def test_org_admin_403_post_sync_auto(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sécurité : admin d'org sur POST /sync/auto → 403."""
        user, _org = await _create_admin_of_org(db_session, "adm-a-syn")

        response = await client.post(
            f"{PREFIX}/sync/auto",
            json={},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403

    async def test_org_admin_403_patch_toggle_visibility(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sécurité : admin d'org sur PATCH /{id}/toggle-visibility → 403."""
        user, _org = await _create_admin_of_org(db_session, "adm-a-tog")

        response = await client.patch(
            f"{PREFIX}/some-stack-id/toggle-visibility",
            headers=_auth_headers(user),
        )
        assert response.status_code == 403

    async def test_org_admin_403_delete_stack(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sécurité : admin d'org sur DELETE /{id} → 403."""
        user, _org = await _create_admin_of_org(db_session, "adm-a-del")

        response = await client.delete(
            f"{PREFIX}/some-stack-id", headers=_auth_headers(user)
        )
        assert response.status_code == 403


# --- Superuser : accès autorisé ----------------------------------------------


class TestSuperuserAccess:
    """Superuser (super_admin) : les routes admin répondent (200/404)."""

    async def test_superuser_200_definitions(
        self, client: AsyncClient, db_session: AsyncSession, tmp_path, monkeypatch
    ):
        """Cas nominal : superuser sur GET /definitions → 200 (liste).

        Le répertoire ``stacks_definitions`` est dérivé de ``__file__`` dans
        le routeur (layout dépendant du contexte d'exécution — Docker vs
        dev local) : un répertoire temporaire avec un YAML valide est
        substitué pour valider le contrat RBAC (superuser → 200), pas le
        chargement YAML lui-même.
        """
        import app.api.v1.admin.stacks_management as admin_module

        definitions_dir = tmp_path / "stacks_definitions"
        definitions_dir.mkdir()
        (definitions_dir / "demo.yaml").write_text(
            "metadata:\n"
            "  name: demo\n"
            "  version: 1.0.0\n"
            "  category: demo\n"
            "  description: Demo stack\n"
            "stack:\n"
            "  services:\n"
            "    web:\n"
            "      image: nginx\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            admin_module.Path, "__truediv__", lambda self, other: definitions_dir
        )

        user = await _create_superuser(db_session, "adm-sa-def")

        response = await client.get(
            f"{PREFIX}/definitions", headers=_auth_headers(user)
        )
        assert response.status_code == 200, response.text
        # Liste non vide (le YAML de démo est détecté, éventuellement en
        # erreur de validation de schéma — le contrat RBAC est le 200)
        assert isinstance(unwrap(response), list) and len(unwrap(response)) >= 1

    async def test_superuser_200_imported(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Cas nominal : superuser sur GET /imported → 200 (base vide → [])."""
        user = await _create_superuser(db_session, "adm-sa-imp")

        response = await client.get(f"{PREFIX}/imported", headers=_auth_headers(user))
        assert response.status_code == 200, response.text
        assert unwrap(response) == []

    async def test_superuser_200_sync_status(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Cas nominal : superuser sur GET /sync/status → 200."""
        user = await _create_superuser(db_session, "adm-sa-sync")

        response = await client.get(
            f"{PREFIX}/sync/status", headers=_auth_headers(user)
        )
        assert response.status_code == 200, response.text

    async def test_superuser_200_stats_overview(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Cas nominal : superuser sur GET /stats/overview → 200."""
        user = await _create_superuser(db_session, "adm-sa-ovr")

        response = await client.get(
            f"{PREFIX}/stats/overview", headers=_auth_headers(user)
        )
        assert response.status_code == 200, response.text

    async def test_superuser_404_delete_unknown_stack(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Cas d'erreur : superuser sur DELETE inexistant → 404 (pas 403)."""
        user = await _create_superuser(db_session, "adm-sa-404")

        response = await client.delete(
            f"{PREFIX}/nonexistent-stack", headers=_auth_headers(user)
        )
        assert response.status_code == 404


# --- Sécurité : 401 sans token ------------------------------------------------


class TestNoToken:
    """Sans Authorization : 401 avant toute vérification de rôle."""

    async def test_no_token_401_sample(self, client: AsyncClient):
        """401 sur un échantillon des routes admin (GET/POST/DELETE)."""
        get_resp = await client.get(f"{PREFIX}/definitions")
        post_resp = await client.post(f"{PREFIX}/validate")
        delete_resp = await client.delete(f"{PREFIX}/some-id")

        assert get_resp.status_code == 401
        assert post_resp.status_code == 401
        assert delete_resp.status_code == 401


# --- Non-régression structurelle ----------------------------------------------


class TestAdminRoutesInventory:
    """Garde-fou : exactement 15 routes sur le router stacks_management."""

    def test_admin_routes_count_unchanged(self):
        """Le router stacks_management expose 15 routes (inventaire
        STORY-122.6 — monté sous /api/v1/admin/stacks-management)."""
        from app.api.v1.admin.stacks_management import router

        paths = [getattr(route, "path", None) for route in router.routes]
        assert (
            len(paths) == 15
        ), f"Attendu 15 routes admin, trouvé {len(paths)} : {paths}"
        # Échantillon de vérification des chemins attendus
        assert "/definitions" in paths
        assert "/import" in paths
        assert "/{stack_id}" in paths
        assert "/search" in paths
