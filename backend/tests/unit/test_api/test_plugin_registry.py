"""
Tests unitaires des endpoints API du registre officiel.

Couvre : liste des plugins, détail d'un plugin, sécurité (401),
filtres (catégorie, recherche), pagination, validation kebab-case,
et vérification des champs checksum/download_url (AC 2).

Note : DISABLE_AUTH=true en dev, les tests de sécurité 401
utilisent monkeypatch pour forcer l'authentification.
"""

from typing import List
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.config import settings
from app.schemas.plugin_registry import RegistryPluginEntry


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_plugin_entry(
    name: str = "traefik",
    version: str = "1.2.0",
    display_name: str = "Traefik",
    description: str = "Reverse proxy avec TLS automatique",
    category: str = "access",
    type: str = "hybrid",
    tags: List[str] | None = None,
) -> RegistryPluginEntry:
    """Crée une RegistryPluginEntry de test."""
    return RegistryPluginEntry(
        name=name,
        version=version,
        display_name=display_name,
        description=description,
        category=category,
        type=type,
        author="WindFlow Team",
        license="MIT",
        architectures=["linux/amd64", "linux/arm64"],
        download_url=f"https://registry.windflow.io/plugins/{name}/{version}/package.tar.gz",
        checksum_sha256="a" * 64,
        homepage=f"https://github.com/windflow/plugin-{name}",
        tags=tags or ["test"],
    )


@pytest.fixture()
def auth_enabled(monkeypatch):
    """Active l'authentification réelle pour les tests de sécurité."""
    monkeypatch.setattr(settings, "disable_auth", False)


@pytest.fixture()
def mock_plugins() -> List[RegistryPluginEntry]:
    """Liste de plugins de test."""
    return [
        _make_plugin_entry(
            name="traefik",
            version="1.2.0",
            display_name="Traefik",
            description="Reverse proxy avec TLS automatique",
            category="access",
            tags=["reverse-proxy", "tls"],
        ),
        _make_plugin_entry(
            name="postgresql",
            version="1.0.0",
            display_name="PostgreSQL",
            description="Base de données relationnelle avec backup",
            category="database",
            tags=["database", "sql", "backup"],
        ),
        _make_plugin_entry(
            name="redis",
            version="1.0.0",
            display_name="Redis",
            description="Cache en mémoire avec monitoring",
            category="database",
            tags=["cache", "monitoring"],
        ),
    ]


# ── Tests GET /registry/plugins ─────────────────────────────────────────────


class TestListRegistryPlugins:
    """Tests de l'endpoint GET /registry/plugins."""

    @pytest.mark.asyncio
    async def test_list_registry_plugins_returns_200_authenticated(
        self, admin_client: AsyncClient, mock_plugins: List[RegistryPluginEntry]
    ) -> None:
        """Cas nominal : liste accessible avec auth."""
        with patch(
            "app.api.v1.plugin_registry._get_registry_service"
        ) as mock_get_svc:
            svc = AsyncMock()
            svc.list_plugins = AsyncMock(return_value=mock_plugins)
            svc.search_plugins = AsyncMock(return_value=mock_plugins)
            mock_get_svc.return_value = svc

            response = await admin_client.get("/api/v1/registry/plugins")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["name"] == "traefik"

    @pytest.mark.asyncio
    async def test_list_registry_plugins_returns_empty_when_no_plugins(
        self, admin_client: AsyncClient
    ) -> None:
        """Cas nominal : liste vide."""
        with patch(
            "app.api.v1.plugin_registry._get_registry_service"
        ) as mock_get_svc:
            svc = AsyncMock()
            svc.list_plugins = AsyncMock(return_value=[])
            mock_get_svc.return_value = svc

            response = await admin_client.get("/api/v1/registry/plugins")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_registry_plugins_returns_401_without_token(
        self, client: AsyncClient, auth_enabled
    ) -> None:
        """Sécurité : accès sans token → 401."""
        response = await client.get("/api/v1/registry/plugins")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_registry_plugins_with_category_filter(
        self, admin_client: AsyncClient, mock_plugins: List[RegistryPluginEntry]
    ) -> None:
        """Filtre par catégorie : ne retourne que les plugins de la catégorie."""
        with patch(
            "app.api.v1.plugin_registry._get_registry_service"
        ) as mock_get_svc:
            svc = AsyncMock()
            svc.list_plugins = AsyncMock(return_value=mock_plugins)
            mock_get_svc.return_value = svc

            response = await admin_client.get(
                "/api/v1/registry/plugins", params={"category": "database"}
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(p["category"] == "database" for p in data)

    @pytest.mark.asyncio
    async def test_list_registry_plugins_with_query_search(
        self, admin_client: AsyncClient, mock_plugins: List[RegistryPluginEntry]
    ) -> None:
        """Recherche textuelle : utilise search_plugins du service."""
        search_results = [mock_plugins[0]]
        with patch(
            "app.api.v1.plugin_registry._get_registry_service"
        ) as mock_get_svc:
            svc = AsyncMock()
            svc.search_plugins = AsyncMock(return_value=search_results)
            mock_get_svc.return_value = svc

            response = await admin_client.get(
                "/api/v1/registry/plugins", params={"query": "proxy"}
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "traefik"

    @pytest.mark.asyncio
    async def test_list_registry_plugins_pagination(
        self, admin_client: AsyncClient, mock_plugins: List[RegistryPluginEntry]
    ) -> None:
        """Pagination skip/limit."""
        with patch(
            "app.api.v1.plugin_registry._get_registry_service"
        ) as mock_get_svc:
            svc = AsyncMock()
            svc.list_plugins = AsyncMock(return_value=mock_plugins)
            mock_get_svc.return_value = svc

            response = await admin_client.get(
                "/api/v1/registry/plugins", params={"skip": 1, "limit": 1}
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "postgresql"


# ── Tests GET /registry/plugins/{plugin_name} ──────────────────────────────


class TestGetRegistryPluginDetail:
    """Tests de l'endpoint GET /registry/plugins/{plugin_name}."""

    @pytest.mark.asyncio
    async def test_get_registry_plugin_detail_returns_200(
        self, admin_client: AsyncClient, mock_plugins: List[RegistryPluginEntry]
    ) -> None:
        """Cas nominal : détail plugin."""
        with patch(
            "app.api.v1.plugin_registry._get_registry_service"
        ) as mock_get_svc:
            svc = AsyncMock()
            svc.get_plugin = AsyncMock(return_value=mock_plugins[0])
            mock_get_svc.return_value = svc

            response = await admin_client.get("/api/v1/registry/plugins/traefik")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "traefik"
        assert data["version"] == "1.2.0"
        assert data["display_name"] == "Traefik"

    @pytest.mark.asyncio
    async def test_get_registry_plugin_detail_returns_404_not_found(
        self, admin_client: AsyncClient
    ) -> None:
        """Plugin inexistant → 404."""
        with patch(
            "app.api.v1.plugin_registry._get_registry_service"
        ) as mock_get_svc:
            svc = AsyncMock()
            svc.get_plugin = AsyncMock(return_value=None)
            mock_get_svc.return_value = svc

            response = await admin_client.get(
                "/api/v1/registry/plugins/nonexistent"
            )

        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_registry_plugin_detail_returns_401_without_token(
        self, client: AsyncClient, auth_enabled
    ) -> None:
        """Sécurité : accès sans token → 401."""
        response = await client.get("/api/v1/registry/plugins/traefik")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_registry_plugin_detail_invalid_name_format(
        self, admin_client: AsyncClient
    ) -> None:
        """Name non kebab-case → 422."""
        response = await admin_client.get(
            "/api/v1/registry/plugins/INVALID NAME!"
        )
        assert response.status_code == 422
        assert "invalide" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_registry_plugin_detail_includes_checksum_and_url(
        self, admin_client: AsyncClient, mock_plugins: List[RegistryPluginEntry]
    ) -> None:
        """Vérifie présence checksum + download_url (AC 2)."""
        with patch(
            "app.api.v1.plugin_registry._get_registry_service"
        ) as mock_get_svc:
            svc = AsyncMock()
            svc.get_plugin = AsyncMock(return_value=mock_plugins[0])
            mock_get_svc.return_value = svc

            response = await admin_client.get("/api/v1/registry/plugins/traefik")

        assert response.status_code == 200
        data = response.json()
        assert "checksum_sha256" in data
        assert len(data["checksum_sha256"]) == 64
        assert "download_url" in data
        assert data["download_url"].startswith("https://")
