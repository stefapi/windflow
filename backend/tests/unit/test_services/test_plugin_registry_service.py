"""
Tests unitaires du service PluginRegistryService.

Couvre : fetch avec cache TTL, validation Pydantic, recherche par nom,
recherche textuelle, gestion d'erreurs (timeout, HTTP, JSON invalide),
fallback sur cache expiré.

STORY-168 : le cache TTL repose sur l'interface unifiée ``core/cache``
(clé ``registry:index``) ; la copie locale last-known-good porte le
fallback stale-while-error.
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from app.config import Settings
from app.core import cache as cache_module
from app.core.cache import reset_cache
from app.core.exceptions import WindFlowException
from app.schemas.plugin_registry import RegistryIndex
from app.services.plugin_registry_service import PluginRegistryService

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _fresh_unified_cache():
    """Cache unifié vierge (mode mémoire forcé) autour de chaque test."""
    reset_cache()
    with patch.object(cache_module.settings, "cache_url", None), patch.object(
        cache_module.settings, "rate_limit_storage_url", None
    ):
        yield
    reset_cache()


@pytest.fixture()
def test_settings() -> Settings:
    """Settings de test avec URL et TTL configurés."""
    return Settings(
        plugin_registry_url="https://registry.example.com/index.json",
        plugin_registry_cache_ttl=300,
        plugin_registry_timeout=10,
    )


@pytest.fixture()
def service(test_settings: Settings) -> PluginRegistryService:
    """Instance du service avec settings de test."""
    return PluginRegistryService(test_settings)


@pytest.fixture()
def valid_index_json() -> Dict[str, Any]:
    """Données JSON valides pour un index de registre."""
    return {
        "version": "1.0",
        "updated_at": "2026-05-26T00:00:00Z",
        "registry_url": "https://registry.example.com",
        "plugins": [
            {
                "name": "traefik",
                "version": "1.2.0",
                "display_name": "Traefik",
                "description": "Reverse proxy avec TLS automatique",
                "category": "access",
                "type": "hybrid",
                "author": "WindFlow Team",
                "license": "MIT",
                "architectures": ["linux/amd64", "linux/arm64"],
                "download_url": "https://registry.example.com/plugins/traefik/1.2.0/package.tar.gz",
                "checksum_sha256": "a" * 64,
                "homepage": "https://github.com/windflow/plugin-traefik",
                "tags": ["reverse-proxy", "tls"],
            },
            {
                "name": "postgresql",
                "version": "1.0.0",
                "display_name": "PostgreSQL",
                "description": "Base de données relationnelle avec backup",
                "category": "database",
                "type": "hybrid",
                "author": "WindFlow Team",
                "license": "MIT",
                "architectures": ["linux/amd64", "linux/arm64"],
                "download_url": "https://registry.example.com/plugins/postgresql/1.0.0/package.tar.gz",
                "checksum_sha256": "b" * 64,
                "homepage": "https://github.com/windflow/plugin-postgresql",
                "tags": ["database", "sql", "backup"],
            },
        ],
    }


def _make_mock_session_response(status: int = 200, json_data: Any = None) -> AsyncMock:
    """Crée un mock de réponse HTTP aiohttp (async context manager).

    Retourne un AsyncMock qui se comporte comme un async context manager
    en retournant lui-même dans __aenter__.
    """
    response = AsyncMock()
    response.status = status
    response.json = AsyncMock(return_value=json_data)
    # async context manager : retourne self
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)
    return response


def _make_mock_session(
    get_return: AsyncMock | None = None,
    get_side_effect: Any = None,
) -> AsyncMock:
    """Crée un mock de aiohttp.ClientSession (async context manager).

    Retourne un AsyncMock qui se comporte comme un async context manager
    en retournant lui-même dans __aenter__.
    """
    session = AsyncMock()
    if get_side_effect is not None:
        session.get = MagicMock(side_effect=get_side_effect)
    elif get_return is not None:
        session.get = MagicMock(return_value=get_return)
    # async context manager : retourne self
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


# ── Tests fetch_index ───────────────────────────────────────────────────────


class TestFetchIndex:
    """Tests de la méthode fetch_index."""

    @pytest.mark.asyncio
    async def test_fetch_index_success(
        self, service: PluginRegistryService, valid_index_json: Dict[str, Any]
    ) -> None:
        """Fetch réussi, index parsé et mis en cache."""
        mock_response = _make_mock_session_response(json_data=valid_index_json)
        mock_session = _make_mock_session(get_return=mock_response)

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            index = await service.fetch_index()

        assert isinstance(index, RegistryIndex)
        assert len(index.plugins) == 2
        assert index.plugins[0].name == "traefik"

    @pytest.mark.asyncio
    async def test_fetch_index_caches_result(
        self, service: PluginRegistryService, valid_index_json: Dict[str, Any]
    ) -> None:
        """Second appel utilise le cache unifié (pas de second fetch)."""
        mock_response = _make_mock_session_response(json_data=valid_index_json)
        mock_session = _make_mock_session(get_return=mock_response)

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            index1 = await service.fetch_index()
            index2 = await service.fetch_index()

        assert index2.version == index1.version
        assert index2.plugins == index1.plugins
        # Un seul appel HTTP car le second utilise le cache
        assert mock_session.get.call_count == 1
        # L'entrée est présente dans le cache unifié sous registry:index
        unified = cache_module._cache
        assert unified is not None
        assert "registry:index" in unified._store

    @pytest.mark.asyncio
    async def test_fetch_index_cache_expired(
        self, test_settings: Settings, valid_index_json: Dict[str, Any]
    ) -> None:
        """Cache expiré → nouveau fetch."""
        # TTL très court pour forcer l'expiration
        test_settings.plugin_registry_cache_ttl = 0
        service = PluginRegistryService(test_settings)

        mock_response = _make_mock_session_response(json_data=valid_index_json)
        mock_session = _make_mock_session(get_return=mock_response)

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            index1 = await service.fetch_index()
            index2 = await service.fetch_index()

        assert index1.version == index2.version
        # Deux appels HTTP car le cache expire immédiatement
        assert mock_session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_index_timeout(self, service: PluginRegistryService) -> None:
        """Timeout HTTP → WindFlowException error_type=registry_timeout."""
        mock_session = _make_mock_session(get_side_effect=asyncio.TimeoutError())

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            with pytest.raises(WindFlowException, match="Timeout") as exc_info:
                await service.fetch_index()

        assert exc_info.value.details.get("error_type") == "registry_timeout"

    @pytest.mark.asyncio
    async def test_fetch_index_http_error(self, service: PluginRegistryService) -> None:
        """Erreur HTTP → WindFlowException error_type=registry_unavailable."""
        mock_response = _make_mock_session_response(status=500)
        mock_session = _make_mock_session(get_return=mock_response)

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            with pytest.raises(WindFlowException, match="Erreur HTTP") as exc_info:
                await service.fetch_index()

        assert exc_info.value.details.get("error_type") == "registry_unavailable"

    @pytest.mark.asyncio
    async def test_fetch_index_invalid_json(
        self, service: PluginRegistryService
    ) -> None:
        """JSON invalide → WindFlowException error_type=registry_invalid."""
        invalid_data = {"version": "1.0", "plugins": [{"name": "BAD NAME!"}]}
        mock_response = _make_mock_session_response(json_data=invalid_data)
        mock_session = _make_mock_session(get_return=mock_response)

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            with pytest.raises(WindFlowException, match="invalide") as exc_info:
                await service.fetch_index()

        assert exc_info.value.details.get("error_type") == "registry_invalid"

    @pytest.mark.asyncio
    async def test_fetch_index_fallback_on_error(
        self, service: PluginRegistryService, valid_index_json: Dict[str, Any]
    ) -> None:
        """Fetch échoue → last-known-good servi (stale-while-error)."""
        # Premier appel réussi pour remplir le cache + la copie locale
        mock_response_ok = _make_mock_session_response(json_data=valid_index_json)
        mock_session_ok = _make_mock_session(get_return=mock_response_ok)

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session_ok,
        ):
            index1 = await service.fetch_index()

        # Simuler l'expiration de l'entrée du cache unifié (TTL écoulé)
        unified = cache_module._cache
        assert unified is not None
        for key, (value, expires_at) in list(unified._store.items()):
            unified._store[key] = (value, expires_at - 10_000)

        # Second appel échoue → fallback sur la copie locale
        mock_session_fail = _make_mock_session(
            get_side_effect=aiohttp.ClientError("Connection refused")
        )

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session_fail,
        ):
            index2 = await service.fetch_index()

        assert index2.version == index1.version
        assert index2.plugins == index1.plugins


# ── Tests list_plugins / get_plugin / search_plugins ────────────────────────


class TestListAndGetPlugins:
    """Tests des méthodes list_plugins, get_plugin, search_plugins."""

    @pytest.mark.asyncio
    async def test_list_plugins_returns_all(
        self, service: PluginRegistryService, valid_index_json: Dict[str, Any]
    ) -> None:
        """Retourne tous les plugins du registre."""
        mock_response = _make_mock_session_response(json_data=valid_index_json)
        mock_session = _make_mock_session(get_return=mock_response)

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            plugins = await service.list_plugins()

        assert len(plugins) == 2
        assert plugins[0].name == "traefik"
        assert plugins[1].name == "postgresql"

    @pytest.mark.asyncio
    async def test_get_plugin_by_name_found(
        self, service: PluginRegistryService, valid_index_json: Dict[str, Any]
    ) -> None:
        """Retourne le plugin correspondant au nom."""
        mock_response = _make_mock_session_response(json_data=valid_index_json)
        mock_session = _make_mock_session(get_return=mock_response)

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            plugin = await service.get_plugin("traefik")

        assert plugin is not None
        assert plugin.name == "traefik"
        assert plugin.version == "1.2.0"

    @pytest.mark.asyncio
    async def test_get_plugin_by_name_not_found(
        self, service: PluginRegistryService, valid_index_json: Dict[str, Any]
    ) -> None:
        """Retourne None si le plugin n'existe pas."""
        mock_response = _make_mock_session_response(json_data=valid_index_json)
        mock_session = _make_mock_session(get_return=mock_response)

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            plugin = await service.get_plugin("nonexistent")

        assert plugin is None

    @pytest.mark.asyncio
    async def test_search_plugins_by_query(
        self, service: PluginRegistryService, valid_index_json: Dict[str, Any]
    ) -> None:
        """Recherche dans name/description/tags."""
        mock_response = _make_mock_session_response(json_data=valid_index_json)
        mock_session = _make_mock_session(get_return=mock_response)

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            # Recherche par tag
            results = await service.search_plugins("backup")
            assert len(results) == 1
            assert results[0].name == "postgresql"

            # Recherche par nom
            results = await service.search_plugins("traefik")
            assert len(results) == 1
            assert results[0].name == "traefik"

            # Recherche par description
            results = await service.search_plugins("relationnelle")
            assert len(results) == 1
            assert results[0].name == "postgresql"

    @pytest.mark.asyncio
    async def test_invalidate_cache(
        self, service: PluginRegistryService, valid_index_json: Dict[str, Any]
    ) -> None:
        """Invalidation force un nouveau fetch (cache unifié + copie locale)."""
        mock_response = _make_mock_session_response(json_data=valid_index_json)
        mock_session = _make_mock_session(get_return=mock_response)

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            await service.fetch_index()

        await service._invalidate_cache()
        assert service._last_good_index is None

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            await service.fetch_index()

        # Deux appels car le cache a été invalidé
        assert mock_session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_two_service_instances_share_unified_cache(
        self, test_settings: Settings, valid_index_json: Dict[str, Any]
    ) -> None:
        """STORY-168 : deux instances partagent l'index via le cache unifié."""
        service_a = PluginRegistryService(test_settings)
        service_b = PluginRegistryService(test_settings)

        mock_response = _make_mock_session_response(json_data=valid_index_json)
        mock_session = _make_mock_session(get_return=mock_response)

        with patch(
            "app.services.plugin_registry_service.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            index_a = await service_a.fetch_index()
            index_b = await service_b.fetch_index()

        # Un seul appel HTTP : B est servi par le cache partagé (process-local)
        assert mock_session.get.call_count == 1
        assert index_b.version == index_a.version
        assert index_b.plugins == index_a.plugins
