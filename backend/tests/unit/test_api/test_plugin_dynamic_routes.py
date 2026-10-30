"""Tests API des routes dynamiques des plugins (STORY-170.1 — T6).

Valide l'AC 1 + le volet routes de l'AC 5 sur l'app réelle (pattern
conftest ``client`` ASGITransport) avec un plugin extension
démonstrateur : module réel écrit sous ``tmp_path`` + montage via
``PluginApiRouterService.mount_from_manifest`` (le chemin exact
emprunté par le manager à l'install).

Sécurité obligatoire (rules 40) :

- ``test_route_200_authenticated`` ;
- ``test_route_401_without_token`` ;
- ``test_route_403_insufficient_role`` (endpoint ``require_operator``
  appelé viewer) ;
- ``test_route_422_invalid_body`` (POST Pydantic) ;
- ``test_openapi_contains_plugin_tag`` ;
- ``test_uninstall_removes_route_404_and_openapi`` (DELETE réel) ;
- ``test_response_does_not_expose_plugin_secrets``.
"""

from pathlib import Path

import pytest
from httpx import AsyncClient
from tests.conftest import unwrap

from app.config import settings
from app.main import app as main_app
from app.models.plugin import Plugin, PluginStatus
from app.services.plugin_api_router_service import get_plugin_api_router_service

# ── Plugin démonstrateur ────────────────────────────────────────────────────

PLUGIN_NAME = "demo-ext"

#: Module ``api_module`` réel du démonstrateur : GET /status
#: (require_viewer), POST /items (require_operator + body Pydantic
#: borné), GET /config-preview (clés de config sans valeurs — jamais
#: de secrets dans les réponses, rules 40).
DEMO_API_MODULE = """\
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.plugins.api import plugin_router, require_operator, require_viewer

router = plugin_router("demo-ext")


@router.get("/status", dependencies=[Depends(require_viewer)])
async def status() -> dict:
    return {"plugin": "demo-ext", "status": "ok"}


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    quantity: int = Field(ge=0, le=100)


@router.post("/items", dependencies=[Depends(require_operator)])
async def create_item(item: ItemCreate) -> dict:
    return {"created": True, "name": item.name}


@router.get("/config-preview", dependencies=[Depends(require_viewer)])
async def config_preview() -> dict:
    # Pattern du core : clés uniquement, jamais les valeurs.
    return {"plugin": "demo-ext", "configured_keys": ["api_key", "host"]}
"""


@pytest.fixture()
def auth_enabled(monkeypatch):
    """Active l'authentification réelle pour les tests 401/403."""
    monkeypatch.setattr(settings, "disable_auth", False)


@pytest.fixture()
def demo_plugin_routes(tmp_path: Path, monkeypatch) -> str:
    """Écrit + monte le plugin démo sur l'app réelle, démonte après test.

    Le montage passe par ``mount_from_manifest`` — le chemin exact du
    manager à l'install (import sécurisé anti path-traversal + garde
    de préfixe + JWT défense en profondeur + invalidation OpenAPI).
    Le teardown ``reset()`` est **obligatoire** : le singleton est
    process-wide et ce fichier s'exécute avant ``test_plugins.py``
    (ordre alphabétique) dont les installs n'ont pas de fichiers
    api_module réels (montage différé attendu, pas d'échec).
    """
    plugin_dir = tmp_path / PLUGIN_NAME
    plugin_dir.mkdir()
    (plugin_dir / "api.py").write_text(DEMO_API_MODULE, encoding="utf-8")
    monkeypatch.setattr(settings, "plugins_base_dir", str(tmp_path))

    service = get_plugin_api_router_service()
    service.reset()  # hygiène : état propre avant chaque test
    service.initialize(main_app)
    mounted = service.mount_from_manifest(
        PLUGIN_NAME, {"extensions": {"api_module": "api.py"}}
    )
    assert mounted == 3  # status + items + config-preview
    yield PLUGIN_NAME
    service.reset()


@pytest.fixture()
async def db_demo_plugin(
    db_session, test_organization, demo_plugin_routes: str
) -> Plugin:
    """Ligne plugin démo en base (status installed, config chiffrée)."""
    from app.models.plugin import encrypt_config_values_for_storage

    plugin = Plugin(
        name=PLUGIN_NAME,
        version="1.0.0",
        display_name="Demo Extension",
        description="Plugin extension de démonstration",
        category="other",
        type="extension",
        status=PluginStatus.INSTALLED.value,
        manifest_data={"name": PLUGIN_NAME, "extensions": {"api_module": "api.py"}},
        config_values=encrypt_config_values_for_storage(
            {"name": PLUGIN_NAME, "extensions": {"api_module": "api.py"}},
            {"api_key": "super-secret-key-123", "host": "localhost"},
        ),
        organization_id=test_organization.id,
    )
    db_session.add(plugin)
    await db_session.commit()
    await db_session.refresh(plugin)
    return plugin


# ── Sécurité : 200 / 401 / 403 / 422 ────────────────────────────────────────


class TestPluginRouteSecurity:
    """RBAC core appliqué aux routes dynamiques (échantillon AC 5)."""

    @pytest.mark.asyncio
    async def test_route_200_authenticated(
        self, admin_client: AsyncClient, demo_plugin_routes: str
    ) -> None:
        """Cas nominal : GET authentifié (admin) → 200 + enveloppe."""
        response = await admin_client.get(f"/api/v1/plugins/{PLUGIN_NAME}/status")
        assert response.status_code == 200
        assert unwrap(response)["status"] == "ok"

    @pytest.mark.asyncio
    async def test_route_401_without_token(
        self, client: AsyncClient, auth_enabled, demo_plugin_routes: str
    ) -> None:
        """Sécurité : sans token → 401 (défense en profondeur JWT)."""
        client.headers.pop("Authorization", None)
        response = await client.get(f"/api/v1/plugins/{PLUGIN_NAME}/status")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_route_403_insufficient_role(
        self, viewer_client: AsyncClient, auth_enabled, demo_plugin_routes: str
    ) -> None:
        """Sécurité RBAC : viewer sur endpoint require_operator → 403."""
        response = await viewer_client.post(
            f"/api/v1/plugins/{PLUGIN_NAME}/items",
            json={"name": "thing", "quantity": 1},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_can_read(
        self, viewer_client: AsyncClient, auth_enabled, demo_plugin_routes: str
    ) -> None:
        """RBAC spec 08 : lecture Viewer autorisée sur require_viewer."""
        response = await viewer_client.get(f"/api/v1/plugins/{PLUGIN_NAME}/status")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_route_422_invalid_body(
        self, admin_client: AsyncClient, demo_plugin_routes: str
    ) -> None:
        """Validation : POST body invalide (contraintes Pydantic) → 422."""
        response = await admin_client.post(
            f"/api/v1/plugins/{PLUGIN_NAME}/items",
            json={"name": "", "quantity": 999},
        )
        assert response.status_code == 422
        response = await admin_client.post(
            f"/api/v1/plugins/{PLUGIN_NAME}/items",
            json={"unexpected": "field"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_route_404_when_plugin_not_mounted(
        self, admin_client: AsyncClient
    ) -> None:
        """Plugin non monté (nom inconnu) → 404 standard FastAPI."""
        response = await admin_client.get("/api/v1/plugins/unknown-plugin/status")
        assert response.status_code == 404


# ── OpenAPI (AC 1) ──────────────────────────────────────────────────────────


class TestPluginOpenapi:
    """Documentation OpenAPI des routes dynamiques (tag plugin-{name})."""

    @pytest.mark.asyncio
    async def test_openapi_contains_plugin_tag(
        self, client: AsyncClient, demo_plugin_routes: str
    ) -> None:
        """AC 1 : le path figure dans /openapi.json avec son tag."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        path = f"/api/v1/plugins/{PLUGIN_NAME}/status"
        assert path in schema["paths"]
        tags = schema["paths"][path]["get"]["tags"]
        assert f"plugin-{PLUGIN_NAME}" in tags

    @pytest.mark.asyncio
    async def test_openapi_excludes_foreign_routes(
        self, client: AsyncClient, demo_plugin_routes: str
    ) -> None:
        """Garde : aucune route dynamique hors /api/v1/plugins/demo-ext."""
        response = await client.get("/openapi.json")
        schema = response.json()
        plugin_paths = [p for p in schema["paths"] if p.startswith("/api/v1/plugins/")]
        # Les routes du core sous /plugins (management) ne sont pas
        # concernées ; les routes démo vivent sous leur namespace.
        demo_paths = [p for p in plugin_paths if f"/{PLUGIN_NAME}/" in p]
        assert demo_paths, plugin_paths
        for path in demo_paths:
            assert path.startswith(f"/api/v1/plugins/{PLUGIN_NAME}/")


# ── Uninstall : démontage réel (AC 1) ───────────────────────────────────────


class TestUninstallRemovesRoutes:
    """La désinstallation retire la route (404) et l'entrée OpenAPI."""

    @pytest.mark.asyncio
    async def test_uninstall_removes_route_404_and_openapi(
        self,
        admin_client: AsyncClient,
        db_demo_plugin: Plugin,
    ) -> None:
        """DELETE uninstall → 204 ; route 404 ; path absent de l'OpenAPI."""
        # Pré-condition : la route répond avant uninstall.
        response = await admin_client.get(f"/api/v1/plugins/{PLUGIN_NAME}/status")
        assert response.status_code == 200
        openapi_before = (await admin_client.get("/openapi.json")).json()
        assert f"/api/v1/plugins/{PLUGIN_NAME}/status" in openapi_before["paths"]

        # Uninstall réel via l'API (manager : unmount AVANT db.delete).
        response = await admin_client.delete(
            f"/api/v1/plugins/{db_demo_plugin.id}/uninstall"
        )
        assert response.status_code == 204

        # La route a disparu → 404, et l'OpenAPI est re-généré sans elle.
        response = await admin_client.get(f"/api/v1/plugins/{PLUGIN_NAME}/status")
        assert response.status_code == 404
        openapi_after = (await admin_client.get("/openapi.json")).json()
        assert f"/api/v1/plugins/{PLUGIN_NAME}/status" not in openapi_after["paths"]


# ── Secrets (rules 40) ──────────────────────────────────────────────────────


class TestPluginSecretsNotExposed:
    """Aucun secret du plugin dans les réponses des routes dynamiques."""

    @pytest.mark.asyncio
    async def test_response_does_not_expose_plugin_secrets(
        self,
        admin_client: AsyncClient,
        db_demo_plugin: Plugin,
        demo_plugin_routes: str,
    ) -> None:
        """La réponse ne contient ni password clair ni token Fernet."""
        # Récupérer les valeurs chiffrées stockées (tokens Fernet).
        stored = db_demo_plugin.config_values or {}
        encrypted_api_key = str(stored.get("api_key", ""))

        response = await admin_client.get(
            f"/api/v1/plugins/{PLUGIN_NAME}/config-preview"
        )
        assert response.status_code == 200
        body_text = response.text

        # Le secret en clair n'apparaît jamais.
        assert "super-secret-key-123" not in body_text
        # Le token Fernet stocké non plus.
        assert encrypted_api_key not in body_text
        assert "gAAAA" not in body_text  # préfixe Fernet défense en profondeur
        # L'endpoint n'expose que les clés (pattern du core).
        assert unwrap(response)["configured_keys"] == ["api_key", "host"]

    @pytest.mark.asyncio
    async def test_status_response_is_minimal(
        self, admin_client: AsyncClient, demo_plugin_routes: str
    ) -> None:
        """La réponse status ne contient pas config_values du tout."""
        response = await admin_client.get(f"/api/v1/plugins/{PLUGIN_NAME}/status")
        assert response.status_code == 200
        body = response.json()
        assert "config_values" not in str(body)
        assert "api_key" not in str(body)


# ── Intégration manager : rollback extension_load_failed (AC 2 de 169.3) ───


class TestInstallRollbackOnExtensionLoadFailure:
    """3e cas différé par 169.3 : échec de chargement → rollback complet.

    Test service (pas API — le router relance sans ``details``, cf.
    divergence documentée 169.3) : l'install d'un plugin dont
    l'api_module n'existe pas doit échouer avec ``extension_load_failed``
    et laisser la base sans le plugin (rollback complet).
    """

    @pytest.mark.asyncio
    async def test_install_failure_rolls_back(
        self,
        db_session,
        test_superuser,
        test_organization,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """api_module déclaré mais fichier absent → rollback + plugin purgé."""
        from unittest.mock import AsyncMock

        from app.schemas.plugin import PluginInstallRequest
        from app.schemas.plugin_registry import RegistryPluginEntry
        from app.services.plugin_manager_service import PluginManagerService

        # Préparer le service : registre + package mockés (pattern 169.3),
        # manifest déclariant extensions.api_module SANS fichier réel.
        entry = RegistryPluginEntry(
            name="broken-ext",
            version="1.0.0",
            display_name="Broken Ext",
            description="Extension dont l'api_module manque",
            category="other",
            type="extension",
            author="Test",
            license="MIT",
            architectures=["linux/amd64"],
            download_url="https://registry.example.com/broken.tar.gz",
            checksum_sha256="b" * 64,
        )
        manifest_yaml = (
            "name: broken-ext\n"
            "version: 1.0.0\n"
            'display_name: "Broken Ext"\n'
            'description: "api_module missing"\n'
            "category: other\n"
            'author: "Test"\n'
            "license: MIT\n"
            "type: extension\n"
            "architectures:\n"
            "  - linux/amd64\n"
            "extensions:\n"
            "  api_module: extensions/api.py\n"
        )
        plugin_dir = tmp_path / "broken-ext"
        plugin_dir.mkdir()
        (plugin_dir / "windflow-plugin.yml").write_text(manifest_yaml, encoding="utf-8")
        monkeypatch.setattr(settings, "plugins_base_dir", str(tmp_path))

        service = PluginManagerService()
        service._registry_service.get_plugin = AsyncMock(return_value=entry)

        async def _fake_download(_entry):
            from app.schemas.plugin_package import PluginPackageResult

            return PluginPackageResult(
                name=entry.name,
                version=entry.version,
                checksum_sha256=entry.checksum_sha256,
                package_size_bytes=128,
                extracted_path=str(plugin_dir),
                files_count=1,
            )

        service._package_service.download_and_extract = _fake_download  # type: ignore[method-assign]

        # Le singleton routes DOIT être initialisé pour que le montage
        # soit tenté (sinon différé) — sur une app FastAPI jetable.
        from fastapi import FastAPI

        router_service = get_plugin_api_router_service()
        router_service.reset()
        router_service.initialize(FastAPI())
        try:
            with pytest.raises(Exception) as exc_info:
                await service.install_plugin(
                    db_session,
                    install_data=PluginInstallRequest(source="broken-ext"),
                    user_id=test_superuser.id,
                    organization_id=test_organization.id,
                )
            assert exc_info.value.details.get("error_type") == "extension_load_failed"
            assert exc_info.value.details.get("rollback_performed") is True

            # Rollback complet : le plugin n'est plus en base.
            from sqlalchemy import select

            result = await db_session.execute(
                select(Plugin).where(Plugin.name == "broken-ext")
            )
            assert result.scalar_one_or_none() is None
        finally:
            router_service.reset()
