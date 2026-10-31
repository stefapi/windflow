"""Tests de contrat des enveloppes API spec 09 — un échantillon par router (STORY-126.2, AC 1 story mère).

Le backend sert les enveloppes ``{"data", "message"}`` /
``{"error": {"code", "message"}}`` systématiquement (défaut activé par
STORY-126.2, flag retiré par STORY-126.3). Ce fichier verrouille
le contrat pour **chacun des 16 routers REST** : un échantillon de lecture
(2xx → ``data`` présent + ``message`` clé présente, nullable) et un cas
d'erreur (``error.code`` + ``error.message`` non vide).

Stratégie d'échantillonnage pragmatique (story, tâche 5) :
- lectures authentifiées légères (listes vides ou stubs) ;
- erreurs 401/403/404 sans création de ressources lourdes ;
- docker : ``GET /docker/system/ping`` (léger, mocké) + 404 conteneur ;
- workflows : stub → ``data == []`` ; admin : ``/admin/audit`` (RBAC fort).

Les tests assertent l'enveloppe **explicitement** (jamais via ``unwrap``) :
le format EST l'objet du test. Aucun état partagé entre routers (base
isolée par test via conftest).

Sécurité (rules 40) : ``_jwt_mode`` — le ``.env`` racine porte
``DISABLE_AUTH=true`` qui court-circuiterait ``get_current_user`` et
ferait échouer les 401 attendus.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.models.user import User

UNKNOWN_UUID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 123.4."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


def _bearer(user: User) -> dict:
    """Headers Authorization — mint direct (pattern test_api_keys)."""
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


def assert_success_envelope(body: dict) -> None:
    """2xx : ``data`` présent + ``message`` clé présente (nullable)."""
    assert "data" in body, f"data absent du body 2xx : {body}"
    assert "message" in body, f"message absent du body 2xx : {body}"


def assert_error_envelope(body: dict, code: str) -> None:
    """Erreur : ``error.code`` exact + ``error.message`` non vide."""
    assert "error" in body, f"error absent du body d'erreur : {body}"
    assert (
        body["error"]["code"] == code
    ), f"error.code attendu {code}, obtenu {body['error'].get('code')}"
    assert body["error"]["message"], "error.message doit être non vide"


# ============================================================================
# 1. auth
# ============================================================================


class TestAuthRouterContract:
    """auth : login ok → data.access_token ; mauvais mdp → INVALID_CREDENTIALS."""

    async def test_login_success_enveloped(self, client: AsyncClient, test_user: User):
        """Login valide → 200 ``data.access_token`` + message présent."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "testpassword123"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert_success_envelope(body)
        assert body["data"]["access_token"]

    async def test_login_invalid_credentials_enveloped(
        self, client: AsyncClient, test_user: User
    ):
        """Login invalide → 401 ``INVALID_CREDENTIALS`` (spécialisation login)."""
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "wrong-password"},
        )
        assert response.status_code == 401, response.text
        assert_error_envelope(response.json(), "INVALID_CREDENTIALS")


# ============================================================================
# 2. users
# ============================================================================


class TestUsersRouterContract:
    """users : GET /users (admin) → data liste/objet paginé ; 401 sans token."""

    async def test_list_users_enveloped(self, admin_client: AsyncClient):
        """Liste users (superuser) → 200 data + message."""
        response = await admin_client.get("/api/v1/users/")
        assert response.status_code == 200, response.text
        assert_success_envelope(response.json())

    async def test_list_users_401_enveloped(self, client: AsyncClient):
        """Sans token → 401 ``INVALID_OR_EXPIRED_TOKEN``."""
        response = await client.get("/api/v1/users/")
        assert response.status_code == 401, response.text
        assert_error_envelope(response.json(), "INVALID_OR_EXPIRED_TOKEN")


# ============================================================================
# 3. organizations
# ============================================================================


class TestOrganizationsRouterContract:
    """organizations : GET → data ; 403 viewer sur POST → PERMISSION_DENIED."""

    async def test_list_organizations_enveloped(
        self, client: AsyncClient, test_superuser: User
    ):
        """Liste globale (superuser) → 200 data + message."""
        response = await client.get(
            "/api/v1/organizations/", headers=_bearer(test_superuser)
        )
        assert response.status_code == 200, response.text
        assert_success_envelope(response.json())

    async def test_create_organization_viewer_403_enveloped(
        self, client: AsyncClient, viewer_user: User
    ):
        """POST /organizations avec viewer → 403 PERMISSION_DENIED (création = SA)."""
        response = await client.post(
            "/api/v1/organizations/",
            json={"name": "Contract Viewer Org"},
            headers=_bearer(viewer_user),
        )
        assert response.status_code == 403, response.text
        assert_error_envelope(response.json(), "PERMISSION_DENIED")


# ============================================================================
# 4. targets
# ============================================================================


class TestTargetsRouterContract:
    """targets : GET /targets → data ; 404 cible inconnue → NOT_FOUND."""

    async def test_list_targets_enveloped(self, client: AsyncClient, test_user: User):
        """Liste targets (viewer OK) → 200 data + message."""
        response = await client.get("/api/v1/targets/", headers=_bearer(test_user))
        assert response.status_code == 200, response.text
        assert_success_envelope(response.json())

    async def test_get_unknown_target_404_enveloped(
        self, client: AsyncClient, test_user: User
    ):
        """Cible inexistante → 404 NOT_FOUND."""
        response = await client.get(
            f"/api/v1/targets/{UNKNOWN_UUID}", headers=_bearer(test_user)
        )
        assert response.status_code == 404, response.text
        assert_error_envelope(response.json(), "NOT_FOUND")


# ============================================================================
# 5. stacks
# ============================================================================


class TestStacksRouterContract:
    """stacks : GET /stacks → data ; détail inconnu 404 enveloppé."""

    async def test_list_stacks_enveloped(self, client: AsyncClient, test_user: User):
        """Liste stacks scopée → 200 data (liste) + message."""
        response = await client.get("/api/v1/stacks/", headers=_bearer(test_user))
        assert response.status_code == 200, response.text
        body = response.json()
        assert_success_envelope(body)
        assert isinstance(body["data"], list)

    async def test_get_unknown_stack_404_enveloped(
        self, client: AsyncClient, test_user: User
    ):
        """Stack inconnue → 404 NOT_FOUND enveloppé."""
        response = await client.get(
            f"/api/v1/stacks/{UNKNOWN_UUID}", headers=_bearer(test_user)
        )
        assert response.status_code == 404, response.text
        assert_error_envelope(response.json(), "NOT_FOUND")


# ============================================================================
# 6. deployments
# ============================================================================


class TestDeploymentsRouterContract:
    """deployments : GET /deployments → {data, pagination} (STORY-128) ; 404 inconnu."""

    async def test_list_deployments_enveloped(
        self, client: AsyncClient, test_user: User
    ):
        """Liste deployments → 200 contrat paginé STORY-128 : liste sous
        ``data`` + bloc ``pagination`` au même niveau (pas ré-enveloppé)."""
        response = await client.get("/api/v1/deployments", headers=_bearer(test_user))
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body["data"], list), f"data doit être une liste : {body}"
        pagination = body.get("pagination")
        assert isinstance(pagination, dict), f"pagination manquant : {body}"
        for key in ("page", "per_page", "total", "pages"):
            assert key in pagination

    async def test_get_unknown_deployment_404_enveloped(
        self, client: AsyncClient, test_user: User
    ):
        """Déploiement inconnu → 404 NOT_FOUND."""
        response = await client.get(
            f"/api/v1/deployments/{UNKNOWN_UUID}", headers=_bearer(test_user)
        )
        assert response.status_code == 404, response.text
        assert_error_envelope(response.json(), "NOT_FOUND")


# ============================================================================
# 8. stats
# ============================================================================


class TestStatsRouterContract:
    """stats : GET /stats/dashboard → data ; 401 sans token."""

    async def test_dashboard_enveloped(self, client: AsyncClient, test_user: User):
        """Dashboard (base vide) → 200 data + message."""
        response = await client.get(
            "/api/v1/stats/dashboard", headers=_bearer(test_user)
        )
        assert response.status_code == 200, response.text
        assert_success_envelope(response.json())

    async def test_dashboard_401_enveloped(self, client: AsyncClient):
        """Sans token → 401 enveloppé."""
        response = await client.get("/api/v1/stats/dashboard")
        assert response.status_code == 401, response.text
        assert_error_envelope(response.json(), "INVALID_OR_EXPIRED_TOKEN")


# ============================================================================
# 9. import_export
# ============================================================================


class TestImportExportRouterContract:
    """import_export : 404 export stack inconnue → enveloppe ; 401 sans token."""

    async def test_export_unknown_stack_404_enveloped(
        self, client: AsyncClient, test_user: User
    ):
        """Export d'une stack inexistante → 404 NOT_FOUND enveloppé."""
        response = await client.get(
            f"/api/v1/stacks/{UNKNOWN_UUID}/export", headers=_bearer(test_user)
        )
        assert response.status_code == 404, response.text
        assert_error_envelope(response.json(), "NOT_FOUND")

    async def test_export_401_enveloped(self, client: AsyncClient):
        """Sans token → 401 enveloppé."""
        response = await client.get(f"/api/v1/stacks/{UNKNOWN_UUID}/export")
        assert response.status_code == 401, response.text
        assert_error_envelope(response.json(), "INVALID_OR_EXPIRED_TOKEN")


# ============================================================================
# 10. schedules
# ============================================================================


class TestSchedulesRouterContract:
    """schedules : GET /schedules → data ; 401 sans token."""

    async def test_list_schedules_enveloped(self, client: AsyncClient, test_user: User):
        """Liste schedules (viewer) → 200 data + message."""
        response = await client.get("/api/v1/schedules", headers=_bearer(test_user))
        assert response.status_code == 200, response.text
        assert_success_envelope(response.json())

    async def test_schedules_401_enveloped(self, client: AsyncClient):
        """Sans token → 401 enveloppé."""
        response = await client.get("/api/v1/schedules")
        assert response.status_code == 401, response.text
        assert_error_envelope(response.json(), "INVALID_OR_EXPIRED_TOKEN")


# ============================================================================
# 11. docker
# ============================================================================


class TestDockerRouterContract:
    """docker : GET /docker/system/ping (mocké) → data.available ; 404 conteneur."""

    async def test_system_ping_enveloped(self, client: AsyncClient, test_user: User):
        """Ping système (Docker mocké) → 200 data.available + message."""
        docker = AsyncMock()
        docker.ping.return_value = True
        docker.close = AsyncMock()
        with patch("app.api.v1.docker.get_docker_client", return_value=docker):
            response = await client.get(
                "/api/v1/docker/system/ping", headers=_bearer(test_user)
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert_success_envelope(body)
        assert body["data"]["available"] is True

    async def test_unknown_container_404_enveloped(
        self, client: AsyncClient, test_user: User
    ):
        """Conteneur inconnu → 404 enveloppé (garde-fou : aucun endpoint retiré).

        Le routeur mappe ``aiohttp.ClientResponseError`` avec
        ``e.status == 404`` — le mock lève cette exception exacte (une
        exception générique ou ``None`` produirait le 500 préexistant
        de la branche générique, hors périmètre de cette story).
        """
        import aiohttp

        error = aiohttp.ClientResponseError(
            request_info=None,
            history=(),
            status=404,
            message="Not Found",
        )
        docker = AsyncMock()
        docker.get_container.side_effect = error
        docker.close = AsyncMock()
        with patch("app.api.v1.docker.get_docker_client", return_value=docker):
            response = await client.get(
                "/api/v1/docker/containers/contract-unknown", headers=_bearer(test_user)
            )
        assert response.status_code == 404, response.text
        assert_error_envelope(response.json(), "NOT_FOUND")


# ============================================================================
# 12. compute
# ============================================================================


class TestComputeRouterContract:
    """compute : GET /compute/stats (mocké) → data ; 401 sans token.

    STORY-173 : contrats enveloppe des nouvelles routes browse / volumes
    / prune (dry-run superadmin).
    """

    async def test_compute_stats_enveloped(self, client: AsyncClient, test_user: User):
        """Stats compute (service mocké) → 200 data + message."""
        from types import SimpleNamespace

        fake = SimpleNamespace(
            total_containers=0,
            running_containers=0,
            stacks_count=0,
            stacks_running_count=0,
            stacks_targets_count=0,
            stacks_services_count=0,
            discovered_count=0,
            discovered_targets_count=0,
            standalone_count=0,
            standalone_targets_count=0,
            targets_count=0,
        )
        with patch(
            "app.api.v1.compute.compute_service.get_compute_stats",
            new=AsyncMock(return_value=fake),
        ):
            response = await client.get(
                "/api/v1/compute/stats", headers=_bearer(test_user)
            )
        assert response.status_code == 200, response.text
        assert_success_envelope(response.json())

    async def test_compute_401_enveloped(self, client: AsyncClient):
        """Sans token → 401 enveloppé."""
        response = await client.get("/api/v1/compute/stats")
        assert response.status_code == 401, response.text
        assert_error_envelope(response.json(), "INVALID_OR_EXPIRED_TOKEN")

    async def test_compute_browse_enveloped(self, client: AsyncClient, test_user: User):
        """STORY-173 : browse → 200 {data: liste, pagination{}} (pas
        ré-enveloppé — anti double-enveloppe STORY-128)."""
        from app.schemas.common import PaginatedResponse

        fake = PaginatedResponse.model_validate(
            {
                "data": [{"id": "app_web", "kind": "managed_service"}],
                "pagination": {"page": 1, "per_page": 20, "total": 1, "pages": 1},
            }
        )
        with patch(
            "app.api.v1.compute.compute_service.get_compute_browse",
            new=AsyncMock(return_value=fake),
        ):
            response = await client.get(
                "/api/v1/compute/browse", headers=_bearer(test_user)
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body["data"], list)
        pagination = body.get("pagination")
        assert isinstance(pagination, dict)
        for key in ("page", "per_page", "total", "pages"):
            assert key in pagination

    async def test_compute_volumes_enveloped(
        self, client: AsyncClient, test_user: User
    ):
        """STORY-173 : GET /compute/volumes (client mocké) → contrat paginé."""
        from datetime import datetime, timezone

        fake_volume = SimpleNamespace(
            name="data-a",
            driver="local",
            mountpoint="/var/lib/docker/volumes/data-a",
            created_at=datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc),
            labels={},
            scope="local",
        )
        docker = AsyncMock()
        docker.list_volumes.return_value = [fake_volume]
        docker.close = AsyncMock()
        with patch("app.api.v1.compute.DockerClientService", return_value=docker):
            response = await client.get(
                "/api/v1/compute/volumes", headers=_bearer(test_user)
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body["data"], list) and len(body["data"]) == 1
        assert isinstance(body.get("pagination"), dict)

    async def test_compute_prune_dry_run_contract(
        self, client: AsyncClient, test_superuser: User
    ):
        """STORY-173 : superadmin + dry_run → enveloppe data = rapport complet."""
        from app.services.docker_client_service import PruneResult

        docker = AsyncMock()
        docker.prune_volumes.return_value = PruneResult(
            resource="volumes",
            dry_run=True,
            pruned_count=1,
            space_reclaimed_bytes=0,
            spared_count=1,
            pruned_names=["data-orphan"],
            spared_names=["windflow-plugin-trivy-cache"],
            failed_names=[],
            failed_count=0,
        )
        docker.close = AsyncMock()
        with patch("app.api.v1.compute.DockerClientService", return_value=docker):
            response = await client.post(
                "/api/v1/compute/prune",
                json={"resource": "volumes", "dry_run": True},
                headers=_bearer(test_superuser),
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert_success_envelope(body)
        report = body["data"]
        assert report["resource"] == "volumes"
        assert report["dry_run"] is True
        assert report["pruned"] == ["data-orphan"]
        assert report["space_reclaimed_bytes"] == 0


# ============================================================================
# 13. discovery
# ============================================================================


class TestDiscoveryRouterContract:
    """discovery : 401 POST sans token enveloppé ; adoption-data 404."""

    async def test_adopt_401_enveloped(self, client: AsyncClient):
        """POST /discovery/adopt sans token → 401 enveloppé."""
        response = await client.post(
            "/api/v1/discovery/adopt",
            json={
                "discovered_id": "compose:demo@local",
                "type": "composition",
                "stack_name": "contract-stack",
            },
        )
        assert response.status_code == 401, response.text
        assert_error_envelope(response.json(), "INVALID_OR_EXPIRED_TOKEN")

    async def test_adoption_data_unknown_404_enveloped(
        self, client: AsyncClient, test_user: User
    ):
        """GET adoption-data d'un item inconnu → 404 enveloppé."""
        response = await client.get(
            "/api/v1/discovery/composition/contract-unknown@nowhere/adoption-data",
            headers=_bearer(test_user),
        )
        assert response.status_code == 404, response.text
        assert_error_envelope(response.json(), "NOT_FOUND")


# ============================================================================
# 14. plugins
# ============================================================================


class TestPluginsRouterContract:
    """plugins : GET /plugins → data ; 404 plugin inconnu."""

    async def test_list_plugins_enveloped(self, admin_client: AsyncClient):
        """Liste plugins (superuser) → 200 data + message."""
        response = await admin_client.get("/api/v1/plugins/")
        assert response.status_code == 200, response.text
        assert_success_envelope(response.json())

    async def test_unknown_plugin_404_enveloped(self, admin_client: AsyncClient):
        """Plugin inconnu → 404 NOT_FOUND enveloppé."""
        response = await admin_client.get("/api/v1/plugins/contract-unknown-id")
        assert response.status_code == 404, response.text
        assert_error_envelope(response.json(), "NOT_FOUND")


# ============================================================================
# 15. plugin_registry
# ============================================================================


class TestPluginRegistryRouterContract:
    """plugin_registry : GET /registry/plugins (mocké) → data ; 401 sans token."""

    async def test_list_registry_enveloped(self, client: AsyncClient, test_user: User):
        """Registre officiel (service mocké vide) → 200 data + message."""
        with patch("app.api.v1.plugin_registry._get_registry_service") as mock_get_svc:
            svc = AsyncMock()
            svc.list_plugins = AsyncMock(return_value=[])
            mock_get_svc.return_value = svc
            response = await client.get(
                "/api/v1/registry/plugins", headers=_bearer(test_user)
            )
        assert response.status_code == 200, response.text
        assert_success_envelope(response.json())

    async def test_registry_401_enveloped(self, client: AsyncClient):
        """Sans token → 401 enveloppé."""
        response = await client.get("/api/v1/registry/plugins")
        assert response.status_code == 401, response.text
        assert_error_envelope(response.json(), "INVALID_OR_EXPIRED_TOKEN")


# ============================================================================
# 16. admin
# ============================================================================


class TestAdminRouterContract:
    """admin : /admin/audit viewer → 403 PERMISSION_DENIED ; super_admin → {data, pagination} (STORY-128)."""

    async def test_admin_audit_viewer_403_enveloped(
        self, client: AsyncClient, viewer_user: User
    ):
        """Viewer sur /admin/audit → 403 PERMISSION_DENIED enveloppé
        (journal global = super_admin only, spec 08 § Système)."""
        response = await client.get("/api/v1/admin/audit", headers=_bearer(viewer_user))
        assert response.status_code == 403, response.text
        assert_error_envelope(response.json(), "PERMISSION_DENIED")

    async def test_admin_audit_superuser_enveloped(
        self, client: AsyncClient, test_superuser: User
    ):
        """super_admin sur /admin/audit → 200 contrat paginé STORY-128 :
        liste sous ``data`` + bloc ``pagination`` (pas ré-enveloppé)."""
        response = await client.get(
            "/api/v1/admin/audit", headers=_bearer(test_superuser)
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body["data"], list), f"data doit être une liste : {body}"
        pagination = body.get("pagination")
        assert isinstance(pagination, dict), f"pagination manquant : {body}"
        for key in ("page", "per_page", "total", "pages"):
            assert key in pagination
