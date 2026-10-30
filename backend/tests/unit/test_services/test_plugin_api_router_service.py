"""Tests unitaires de ``PluginApiRouterService`` (STORY-170.1 — T3).

Couvre (cf. story § Tests à écrire) :

- **montage** : routes présentes sous ``/api/v1/plugins/{name}/…``
  uniquement, tag OpenAPI ``plugin-{name}``, cache OpenAPI invalidé
  (path visible dans ``/openapi.json`` après montage) ;
- **démontage** : routes retirées, **idempotent**, OpenAPI re-généré
  sans le path ;
- **garde de préfixe** : router au préfixe étranger refusé (un plugin
  ne peut pas injecter de routes hors de son espace de noms) ;
- **JWT défense en profondeur** : endpoint de plugin sans dependency →
  401 sans token quand même (injection au ``include_router``) ;
- ``mount_from_manifest`` : no-op sans ``api_module``, montage différé
  sans app, erreur typée ``extension_load_failed`` ;
- ``load_installed_routers`` : best-effort (pattern
  ``test_plugin_hooks_loading`` — session factory factice).
"""

import logging
from pathlib import Path
from typing import Any, List

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import WindFlowException
from app.plugins.api import plugin_router
from app.services.plugin_api_router_service import PluginApiRouterService

# ── Helpers ─────────────────────────────────────────────────────────────────


def _demo_router(name: str, *, with_auth_deps: bool = True) -> APIRouter:
    """Router de plugin démonstrateur (pattern ``plugin_router``).

    ``with_auth_deps=False`` simule un plugin qui **oublie** les
    dependencies d'auth — la défense en profondeur du service doit
    quand même exiger un token (401).
    """
    from fastapi import Depends

    from app.auth.rbac import require_operator

    router = plugin_router(name)
    deps = [Depends(require_operator)] if with_auth_deps else []
    router.add_api_route(
        "/ping",
        lambda: {"ok": True},
        methods=["GET"],
        dependencies=deps,
    )
    return router


def _service_with_app() -> "tuple[PluginApiRouterService, FastAPI]":
    """Service initialisé sur une app FastAPI fraîche (mode test).

    L'app embarque le handler ``windflow_exception_handler`` de la main
    app (sinon les WindFlowException levées par les dépendances d'auth,
    ex. AuthenticationError 401, remonteraient en 500 sur une app nue).
    """
    from app.middleware.error_handler import windflow_exception_handler

    service = PluginApiRouterService()
    app = FastAPI()
    app.add_exception_handler(WindFlowException, windflow_exception_handler)
    service.initialize(app)
    return service, app


# ── SDK plugin_router ───────────────────────────────────────────────────────


class TestPluginRouterFactory:
    """Factory ``plugin_router`` (STORY-170.1 — T2)."""

    def test_prefix_is_namespaced(self) -> None:
        """Le router est préfixé /api/v1/plugins/{name}."""
        router = plugin_router("my-plugin")
        assert router.prefix == "/api/v1/plugins/my-plugin"

    def test_openapi_tag(self) -> None:
        """Le router porte le tag plugin-{name} (visible /docs)."""
        router = plugin_router("my-plugin")
        assert router.tags == ["plugin-my-plugin"]

    @pytest.mark.parametrize(
        "bad_name",
        ["My_Plugin", "my plugin", "-my-plugin", "my-plugin-", "my--plugin"],
    )
    def test_invalid_name_raises(self, bad_name: str) -> None:
        """Nom non kebab-case → WindFlowException typée (fail-fast)."""
        with pytest.raises(WindFlowException) as exc_info:
            plugin_router(bad_name)
        assert exc_info.value.details["error_type"] == "invalid_plugin_name"


# ── Montage ─────────────────────────────────────────────────────────────────


class TestMount:
    """Montage des routes sur l'app (garde de préfixe, tracking)."""

    def test_mount_adds_routes_under_plugin_namespace(self) -> None:
        """Les routes ajoutées vivent sous /api/v1/plugins/{name}/ uniquement."""
        service, app = _service_with_app()
        before = len(app.router.routes)
        added = service.mount("demo-plugin", _demo_router("demo-plugin"))
        assert added == 1
        assert len(app.router.routes) == before + 1
        plugin_paths = [
            getattr(route, "path", "")
            for route in app.router.routes
            if getattr(route, "path", "").startswith("/api/v1/plugins/demo-plugin")
        ]
        assert plugin_paths == ["/api/v1/plugins/demo-plugin/ping"]

    def test_mount_invalidates_openapi_cache(self) -> None:
        """Point critique AC 1 : app.openapi_schema invalidé au montage."""
        service, app = _service_with_app()
        app.openapi_schema = {"stale": True}  # cache préexistant
        service.mount("demo-plugin", _demo_router("demo-plugin"))
        assert app.openapi_schema is None

    def test_mount_without_initialize_raises(self) -> None:
        """Service non initialisé → erreur typée."""
        service = PluginApiRouterService()
        with pytest.raises(WindFlowException) as exc_info:
            service.mount("demo-plugin", _demo_router("demo-plugin"))
        assert exc_info.value.details["error_type"] == "router_service_not_initialized"

    def test_mount_foreign_prefix_refused(self) -> None:
        """Garde sécurité : router au préfixe étranger refusé."""
        service, _app = _service_with_app()
        foreign = APIRouter(prefix="/api/v1/stacks")
        with pytest.raises(WindFlowException) as exc_info:
            service.mount("demo-plugin", foreign)
        assert exc_info.value.details["error_type"] == "invalid_router_prefix"
        # Le namespace d'un AUTRE plugin est tout aussi refusé.
        other = plugin_router("other-plugin")
        with pytest.raises(WindFlowException):
            service.mount("demo-plugin", other)

    def test_mount_twice_refused(self) -> None:
        """Double montage du même plugin → erreur typée (idempotence interdite)."""
        service, _app = _service_with_app()
        service.mount("demo-plugin", _demo_router("demo-plugin"))
        with pytest.raises(WindFlowException) as exc_info:
            service.mount("demo-plugin", _demo_router("demo-plugin"))
        assert exc_info.value.details["error_type"] == "plugin_routes_already_mounted"

    def test_mount_invalid_plugin_name_refused(self) -> None:
        """Nom non kebab-case → erreur typée au montage (défense en profondeur)."""
        service, _app = _service_with_app()
        # Router "fabriqué à la main" avec un préfixe correspondant au nom
        # invalide — la garde de nom doit refuser avant celle de préfixe.
        router = APIRouter(prefix="/api/v1/plugins/Bad_Name")
        with pytest.raises(WindFlowException) as exc_info:
            service.mount("Bad_Name", router)
        assert exc_info.value.details["error_type"] == "invalid_plugin_name"


# ── Démontage ───────────────────────────────────────────────────────────────


class TestUnmount:
    """Démontage des routes trackées (idempotence, OpenAPI)."""

    def test_unmount_removes_tracked_routes(self) -> None:
        """Les routes trackées sont retirées, l'app revient à l'état initial."""
        service, app = _service_with_app()
        before = len(app.router.routes)
        service.mount("demo-plugin", _demo_router("demo-plugin"))
        removed = service.unmount("demo-plugin")
        assert removed == 1
        assert len(app.router.routes) == before
        assert service.mounted_plugins == []

    def test_unmount_is_idempotent(self) -> None:
        """Unmount sur plugin non monté → no-op 0, sans erreur."""
        service, _app = _service_with_app()
        assert service.unmount("demo-plugin") == 0
        service.mount("demo-plugin", _demo_router("demo-plugin"))
        service.unmount("demo-plugin")
        assert service.unmount("demo-plugin") == 0

    def test_unmount_invalidates_openapi_cache(self) -> None:
        """OpenAPI invalidé au démontage — le path disparaît du schéma."""
        service, app = _service_with_app()
        service.mount("demo-plugin", _demo_router("demo-plugin"))
        app.openapi()  # régénère + met en cache
        assert app.openapi_schema is not None
        service.unmount("demo-plugin")
        assert app.openapi_schema is None

    def test_unmount_without_initialize_is_noop(self) -> None:
        """Unmont sans app référencée → 0, pas d'erreur (best-effort)."""
        service = PluginApiRouterService()
        assert service.unmount("demo-plugin") == 0

    def test_unmount_preserves_other_plugins(self) -> None:
        """Le démontage d'un plugin ne touche pas les routes d'un autre."""
        service, app = _service_with_app()
        service.mount("plugin-a", _demo_router("plugin-a"))
        service.mount("plugin-b", _demo_router("plugin-b"))
        service.unmount("plugin-a")
        remaining = [
            getattr(route, "path", "")
            for route in app.router.routes
            if getattr(route, "path", "").startswith("/api/v1/plugins/")
        ]
        assert remaining == ["/api/v1/plugins/plugin-b/ping"]
        assert service.mounted_plugins == ["plugin-b"]

    def test_reset_clears_state(self) -> None:
        """Reset démonte tout et oubli l'app (isolation tests)."""
        service, app = _service_with_app()
        service.mount("demo-plugin", _demo_router("demo-plugin"))
        service.reset()
        assert service.mounted_plugins == []
        assert service.is_initialized is False


# ── JWT défense en profondeur ───────────────────────────────────────────────


class TestJwtDefenseInDepth:
    """La route plugin sans dependency reste protégée (401 sans token)."""

    @staticmethod
    def _override_db(app: FastAPI) -> None:
        """Override ``get_db`` par une session mockée (app de test locale
        hors lifespan — la Database globale n'est pas connectée ; le 401
        est levé avant tout usage de la session, l'override neutralise
        la résolution de la dépendance)."""
        from unittest.mock import AsyncMock

        from app.database import get_db

        session = AsyncMock()

        async def override():
            yield session

        app.dependency_overrides[get_db] = override

    @pytest.mark.asyncio
    async def test_endpoint_without_deps_returns_401_without_token(self) -> None:
        """Plugin qui oublie l'auth → 401 quand même (include_router)."""
        from app.config import settings

        service, app = _service_with_app()
        self._override_db(app)
        # Router SANS dependencies d'auth (plugin négligent)
        service.mount("demo-plugin", _demo_router("demo-plugin", with_auth_deps=False))
        transport = ASGITransport(app=app)
        original = settings.disable_auth
        settings.disable_auth = False
        try:
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/plugins/demo-plugin/ping")
            assert response.status_code == 401
        finally:
            settings.disable_auth = original
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_endpoint_with_rbac_returns_401_without_token(self) -> None:
        """Endpoint protégé require_operator → 401 sans token (pas 403)."""
        from app.config import settings

        service, app = _service_with_app()
        self._override_db(app)
        service.mount("demo-plugin", _demo_router("demo-plugin"))
        transport = ASGITransport(app=app)
        original = settings.disable_auth
        settings.disable_auth = False
        try:
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/plugins/demo-plugin/ping")
            assert response.status_code == 401
        finally:
            settings.disable_auth = original
            app.dependency_overrides.clear()


# ── OpenAPI (AC 1) ──────────────────────────────────────────────────────────


class TestOpenapiIntegration:
    """Le path et le tag apparaissent/disparaissent de /openapi.json."""

    @pytest.mark.asyncio
    async def test_openapi_contains_path_and_tag_after_mount(self) -> None:
        """AC 1 : path présent + tag plugin-{name} dans le schéma généré."""
        service, app = _service_with_app()
        service.mount("demo-plugin", _demo_router("demo-plugin"))
        schema = app.openapi()
        assert "/api/v1/plugins/demo-plugin/ping" in schema["paths"]
        tags = schema["paths"]["/api/v1/plugins/demo-plugin/ping"]["get"]["tags"]
        assert "plugin-demo-plugin" in tags

    @pytest.mark.asyncio
    async def test_openapi_regenerated_without_path_after_unmount(self) -> None:
        """AC 1 : après unmount, le path disparaît du schéma re-généré."""
        service, app = _service_with_app()
        service.mount("demo-plugin", _demo_router("demo-plugin"))
        assert "/api/v1/plugins/demo-plugin/ping" in app.openapi()["paths"]
        service.unmount("demo-plugin")
        assert "/api/v1/plugins/demo-plugin/ping" not in app.openapi()["paths"]


# ── mount_from_manifest ─────────────────────────────────────────────────────


class TestMountFromManifest:
    """Variante stricte appelée par le manager à l'install."""

    def test_noop_without_api_module(self) -> None:
        """Manifest sans extensions.api_module → 0 route, pas d'erreur."""
        service, _app = _service_with_app()
        assert service.mount_from_manifest("demo-plugin", {}) == 0
        assert (
            service.mount_from_manifest(
                "demo-plugin", {"extensions": {"hooks_module": "hooks/main.py"}}
            )
            == 0
        )

    def test_deferred_without_app_in_process(self, caplog) -> None:
        """Sans app FastAPI dans le process → montage différé (0, INFO)."""
        service = PluginApiRouterService()
        with caplog.at_level(logging.INFO):
            mounted = service.mount_from_manifest(
                "demo-plugin", {"extensions": {"api_module": "api.py"}}
            )
        assert mounted == 0
        assert any("plugin_routes_mount_deferred" in r.message for r in caplog.records)

    def test_missing_file_raises_extension_load_failed(self) -> None:
        """api_module inexistant → extension_load_failed (rollback 169.3)."""
        service, _app = _service_with_app()
        with pytest.raises(WindFlowException) as exc_info:
            service.mount_from_manifest(
                "demo-plugin", {"extensions": {"api_module": "api.py"}}
            )
        assert exc_info.value.details["error_type"] == "extension_load_failed"
        assert exc_info.value.details["cause"] == "import_error"

    def test_module_without_router_raises(self, tmp_path: Path) -> None:
        """Module sans variable ``router`` → extension_load_failed."""
        service = PluginApiRouterService()
        service.initialize(FastAPI())
        # Pointe plugins_base_dir sur tmp_path pour l'import sécurisé.
        from app.config import settings

        plugin_dir = tmp_path / "demo-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "api.py").write_text("value = 42\n", encoding="utf-8")
        original = settings.plugins_base_dir
        settings.plugins_base_dir = str(tmp_path)
        try:
            with pytest.raises(WindFlowException) as exc_info:
                service.mount_from_manifest(
                    "demo-plugin", {"extensions": {"api_module": "api.py"}}
                )
            assert exc_info.value.details["error_type"] == "extension_load_failed"
            assert exc_info.value.details["cause"] == "api_module_missing_router"
        finally:
            settings.plugins_base_dir = original

    def test_valid_module_mounts_routes(self, tmp_path: Path) -> None:
        """Chemin nominal : module réel → routes montées sous le préfixe."""
        service = PluginApiRouterService()
        app = FastAPI()
        service.initialize(app)
        from app.config import settings

        plugin_dir = tmp_path / "demo-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "api.py").write_text(
            "from fastapi import APIRouter\n"
            "from app.plugins.api import plugin_router\n"
            "router = plugin_router('demo-plugin')\n"
            "@router.get('/ping')\n"
            "def ping() -> dict:\n"
            "    return {'ok': True}\n",
            encoding="utf-8",
        )
        original = settings.plugins_base_dir
        settings.plugins_base_dir = str(tmp_path)
        try:
            mounted = service.mount_from_manifest(
                "demo-plugin", {"extensions": {"api_module": "api.py"}}
            )
            assert mounted == 1
            paths = [
                getattr(route, "path", "")
                for route in app.router.routes
                if getattr(route, "path", "").startswith("/api/v1/plugins/demo-plugin")
            ]
            assert paths == ["/api/v1/plugins/demo-plugin/ping"]
        finally:
            settings.plugins_base_dir = original


# ── load_installed_routers (pattern lifespan, best-effort) ─────────────────


class _FakePlugin:
    """Plugin factice (pattern test_plugin_hooks_loading)."""

    def __init__(self, name: str, type_: str, status: str, manifest_data: Any) -> None:
        self.name = name
        self.type = type_
        self.status = status
        self.manifest_data = manifest_data


class _FakeResult:
    """Résultat de session.execute factice."""

    def __init__(self, plugins: List[_FakePlugin]) -> None:
        self._plugins = plugins

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> List[_FakePlugin]:
        return self._plugins


class _FakeSession:
    """Session async factice."""

    def __init__(self, plugins: List[_FakePlugin]) -> None:
        self._plugins = plugins

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
        return _FakeResult(self._plugins)


def _session_factory(plugins: List[_FakePlugin]) -> Any:
    return lambda: _FakeSession(plugins)


class TestLoadInstalledRouters:
    """Chargement lifespan des api_module (best-effort, WARNING sans crash)."""

    @pytest.mark.asyncio
    async def test_no_plugins_returns_zero(self) -> None:
        """Aucun plugin installé → 0 montage."""
        service, _app = _service_with_app()
        loaded = await service.load_installed_routers(_session_factory([]))
        assert loaded == 0

    @pytest.mark.asyncio
    async def test_plugin_without_api_module_skipped(self) -> None:
        """Plugin sans api_module → ignoré en silence (cas nominal)."""
        service, _app = _service_with_app()
        plugins = [
            _FakePlugin("demo-plugin", "extension", "installed", {"extensions": {}})
        ]
        loaded = await service.load_installed_routers(_session_factory(plugins))
        assert loaded == 0

    @pytest.mark.asyncio
    async def test_broken_module_warns_and_continues(self, tmp_path, caplog) -> None:
        """Module cassé → WARNING, plugin ignoré, chargement continue."""
        from app.config import settings

        plugin_dir = tmp_path / "broken-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "api.py").write_text("syntax error(((\n", encoding="utf-8")
        original = settings.plugins_base_dir
        settings.plugins_base_dir = str(tmp_path)
        try:
            service, _app = _service_with_app()
            plugins = [
                _FakePlugin(
                    "broken-plugin",
                    "extension",
                    "installed",
                    {"extensions": {"api_module": "api.py"}},
                )
            ]
            with caplog.at_level(logging.WARNING):
                loaded = await service.load_installed_routers(_session_factory(plugins))
            assert loaded == 0
            assert any(
                "échec d'import de l'api_module" in r.message for r in caplog.records
            )
        finally:
            settings.plugins_base_dir = original

    @pytest.mark.asyncio
    async def test_db_error_returns_zero(self, caplog) -> None:
        """Erreur de lecture DB → 0 montage, startup intact (ERROR log)."""

        class _BrokenFactory:
            def __call__(self) -> "_BrokenFactory":
                return self

            async def __aenter__(self) -> "_BrokenFactory":
                raise RuntimeError("db down")

            async def __aexit__(self, *args: Any) -> None:
                return None

            async def execute(self, *_a: Any, **_k: Any) -> None:  # pragma: no cover
                raise AssertionError("never reached")

        service, _app = _service_with_app()
        with caplog.at_level(logging.ERROR):
            loaded = await service.load_installed_routers(_BrokenFactory())
        assert loaded == 0
        assert any(
            "lecture des plugins installés impossible" in r.message
            for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_valid_plugin_mounted(self, tmp_path: Path) -> None:
        """Chemin nominal : plugin installé → routes montées au chargement."""
        from app.config import settings

        plugin_dir = tmp_path / "demo-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "api.py").write_text(
            "from app.plugins.api import plugin_router\n"
            "router = plugin_router('demo-plugin')\n"
            "@router.get('/ping')\n"
            "def ping() -> dict:\n"
            "    return {'ok': True}\n",
            encoding="utf-8",
        )
        original = settings.plugins_base_dir
        settings.plugins_base_dir = str(tmp_path)
        try:
            service, app = _service_with_app()
            plugins = [
                _FakePlugin(
                    "demo-plugin",
                    "extension",
                    "installed",
                    {"extensions": {"api_module": "api.py"}},
                )
            ]
            loaded = await service.load_installed_routers(_session_factory(plugins))
            assert loaded == 1
            assert service.mounted_plugins == ["demo-plugin"]
            assert "/api/v1/plugins/demo-plugin/ping" in app.openapi()["paths"]
        finally:
            settings.plugins_base_dir = original
