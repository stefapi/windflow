"""Tests RBAC des routers plugins + plugin_registry (STORY-122.5, AC 2).

Matrice spec 08 : Plugins — lecture = Viewer+ ; installation / mise à
jour / configuration / désinstallation = Admin+ (remplacement des 4
marqueurs intérimaires ``require_superuser``) ; Marketplace (registre
officiel) = lecture Viewer+.

Couverture :
- **viewer** : 200 ``GET /plugins/`` + ``GET /registry/plugins`` ; 403
  install / configure / uninstall (échantillon gestion) ;
- **operator** : 403 ``POST /plugins/install`` ;
- **admin** : 202 install, 200 configure, 204 uninstall (services
  mockés — assertion sur le statut, pas l'exécution) ;
- **404** plugin / entrée de registre inexistante ;
- **422** nom de registre invalide (anti path traversal) ;
- **401 sans token** (échantillon).

Chaîne d'auth réelle : JWT → ``require_*`` (pattern test_schedules_rbac).
"""

from datetime import datetime
from types import SimpleNamespace
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

INSTALL_PAYLOAD: dict = {
    "source": "https://registry.windflow.io/plugins/demo/1.0.0",
}

# Plugin factice complet (champs requis de PluginResponse)
_FAKE_PLUGIN_DETAIL = SimpleNamespace(
    id="plg-1",
    name="demo-plugin",
    version="1.0.0",
    display_name="Demo Plugin",
    description="Plugin de démonstration",
    category="monitoring",
    type="stack",
    status="installed",
    installed_at=datetime(2026, 1, 1),
    updated_at=datetime(2026, 1, 2),
    manifest_data={},
    config_values={},
    installed_by="user-1",
    organization_id="org-1",
)


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
    """Viewer : 200 lectures / 403 gestion (install/config/uninstall)."""

    async def test_viewer_200_list_plugins(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Lecture : GET /plugins/ avec viewer → 200 (liste org, vide)."""
        user, _org = await _create_user_with_role(db_session, "plg-view-l", Role.VIEWER)

        response = await client.get("/api/v1/plugins/", headers=_auth_headers(user))
        assert response.status_code == 200, response.text
        assert isinstance(unwrap(response), list)

    async def test_viewer_200_list_registry(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Marketplace : GET /registry/plugins avec viewer → 200 (catalogue mocké)."""
        user, _org = await _create_user_with_role(db_session, "plg-view-r", Role.VIEWER)

        with patch(
            "app.api.v1.plugin_registry._registry_service.list_plugins",
            new=AsyncMock(return_value=[]),
        ):
            response = await client.get(
                "/api/v1/registry/plugins", headers=_auth_headers(user)
            )
        assert response.status_code == 200, response.text
        assert unwrap(response) == []

    async def test_viewer_403_install_plugin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /plugins/install avec viewer → 403."""
        user, _org = await _create_user_with_role(db_session, "plg-view-i", Role.VIEWER)

        response = await client.post(
            "/api/v1/plugins/install",
            json=INSTALL_PAYLOAD,
            headers=_auth_headers(user),
        )
        assert response.status_code == 403
        assert response.json()["error"]["message"] == "Not enough permissions"

    async def test_viewer_403_configure_plugin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : PUT /plugins/{id}/configure avec viewer → 403."""
        user, _org = await _create_user_with_role(db_session, "plg-view-c", Role.VIEWER)

        response = await client.put(
            "/api/v1/plugins/plg-1/configure",
            json={"config_values": {"port": 9090}},
            headers=_auth_headers(user),
        )
        assert response.status_code == 403

    async def test_viewer_403_uninstall_plugin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : DELETE /plugins/{id}/uninstall avec viewer → 403."""
        user, _org = await _create_user_with_role(db_session, "plg-view-u", Role.VIEWER)

        response = await client.delete(
            "/api/v1/plugins/plg-1/uninstall", headers=_auth_headers(user)
        )
        assert response.status_code == 403


# --- Operator : gestion 403 --------------------------------------------------


class TestOperatorMatrix:
    """Operator : 403 sur la gestion admin des plugins."""

    async def test_operator_403_install_plugin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /plugins/install avec operator → 403."""
        user, _org = await _create_user_with_role(db_session, "plg-op-i", Role.OPERATOR)

        response = await client.post(
            "/api/v1/plugins/install",
            json=INSTALL_PAYLOAD,
            headers=_auth_headers(user),
        )
        assert response.status_code == 403


# --- Admin : gestion OK (services mockés) ------------------------------------


class TestAdminMatrix:
    """Admin : 202 install, 200 configure, 204 uninstall (mockés)."""

    async def test_admin_202_install_plugin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : POST /plugins/install avec admin → 202 (service mocké)."""
        user, _org = await _create_user_with_role(db_session, "plg-adm-i", Role.ADMIN)
        fake = SimpleNamespace(id="plg-1", status="installed", name="demo-plugin")

        with patch(
            "app.api.v1.plugins._plugin_service.install_plugin",
            new=AsyncMock(return_value=fake),
        ):
            response = await client.post(
                "/api/v1/plugins/install",
                json=INSTALL_PAYLOAD,
                headers=_auth_headers(user),
            )
        assert response.status_code == 202, response.text
        assert unwrap(response)["id"] == "plg-1"

    async def test_admin_200_configure_plugin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : PUT /plugins/{id}/configure avec admin → 200 (service mocké)."""
        user, _org = await _create_user_with_role(db_session, "plg-adm-c", Role.ADMIN)

        with patch(
            "app.api.v1.plugins._plugin_service.configure_plugin",
            new=AsyncMock(return_value=_FAKE_PLUGIN_DETAIL),
        ):
            response = await client.put(
                "/api/v1/plugins/plg-1/configure",
                json={"config_values": {"port": 9090}},
                headers=_auth_headers(user),
            )
        assert response.status_code == 200, response.text
        assert unwrap(response)["id"] == "plg-1"

    async def test_admin_204_uninstall_plugin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Gestion : DELETE /plugins/{id}/uninstall avec admin → 204 (service mocké)."""
        user, _org = await _create_user_with_role(db_session, "plg-adm-u", Role.ADMIN)

        with patch(
            "app.api.v1.plugins._plugin_service.uninstall_plugin",
            new=AsyncMock(return_value=None),
        ):
            response = await client.delete(
                "/api/v1/plugins/plg-1/uninstall", headers=_auth_headers(user)
            )
        assert response.status_code == 204


# --- Cas d'erreur : 404 / 422 ------------------------------------------------


class TestErrorCases:
    """404 ressource inexistante, 422 nom de registre invalide."""

    async def test_viewer_404_plugin_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Erreur : GET /plugins/{id} inexistant avec viewer → 404."""
        user, _org = await _create_user_with_role(db_session, "plg-404-p", Role.VIEWER)

        response = await client.get(
            "/api/v1/plugins/nonexistent", headers=_auth_headers(user)
        )
        assert response.status_code == 404

    async def test_viewer_404_registry_plugin_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Erreur : GET /registry/plugins/{name} introuvable → 404 (service mocké)."""
        user, _org = await _create_user_with_role(db_session, "plg-404-r", Role.VIEWER)

        with patch(
            "app.api.v1.plugin_registry._registry_service.get_plugin",
            new=AsyncMock(return_value=None),
        ):
            response = await client.get(
                "/api/v1/registry/plugins/demo-plugin", headers=_auth_headers(user)
            )
        assert response.status_code == 404

    async def test_viewer_422_registry_invalid_name(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Validation : nom de registre non kebab-case → 422 (anti path traversal)."""
        user, _org = await _create_user_with_role(db_session, "plg-422-r", Role.VIEWER)

        response = await client.get(
            "/api/v1/registry/plugins/Invalid_Name", headers=_auth_headers(user)
        )
        assert response.status_code == 422


# --- Sécurité : 401 sans token ------------------------------------------------


class TestNoToken:
    """Sans Authorization : 401 avant toute vérification de rôle."""

    async def test_no_token_401_sample(self, client: AsyncClient):
        """401 sur un échantillon lecture + gestion (plugins et registre)."""
        read_resp = await client.get("/api/v1/plugins/")
        registry_resp = await client.get("/api/v1/registry/plugins")
        adm_resp = await client.post("/api/v1/plugins/install", json=INSTALL_PAYLOAD)

        assert read_resp.status_code == 401
        assert registry_resp.status_code == 401
        assert adm_resp.status_code == 401
