"""
Tests unitaires des schémas Pydantic du registre officiel.

Couvre : validation des entrées du registre, index complet,
réponses API (summary et detail), et cas d'erreur.
"""

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from app.schemas.plugin_registry import (
    RegistryIndex,
    RegistryPluginDetailResponse,
    RegistryPluginEntry,
    RegistryPluginSummaryResponse,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def valid_entry_data() -> Dict[str, Any]:
    """Données valides pour une entrée du registre."""
    return {
        "name": "traefik",
        "version": "1.2.0",
        "display_name": "Traefik",
        "description": "Reverse proxy avec TLS automatique",
        "category": "access",
        "type": "hybrid",
        "author": "WindFlow Team",
        "license": "MIT",
        "architectures": ["linux/amd64", "linux/arm64"],
        "download_url": "https://registry.windflow.io/plugins/traefik/1.2.0/package.tar.gz",
        "checksum_sha256": "a" * 64,
        "homepage": "https://github.com/windflow/plugin-traefik",
        "tags": ["reverse-proxy", "tls"],
    }


@pytest.fixture()
def valid_index_data(valid_entry_data: Dict[str, Any]) -> Dict[str, Any]:
    """Données valides pour un index complet."""
    return {
        "version": "1.0",
        "updated_at": "2026-05-26T00:00:00Z",
        "registry_url": "https://registry.windflow.io",
        "plugins": [valid_entry_data],
    }


# ── Tests RegistryPluginEntry ───────────────────────────────────────────────


class TestRegistryPluginEntry:
    """Tests du schéma RegistryPluginEntry."""

    def test_registry_plugin_entry_valid(self, valid_entry_data: Dict[str, Any]) -> None:
        """Une entrée valide avec tous les champs passe la validation."""
        entry = RegistryPluginEntry(**valid_entry_data)
        assert entry.name == "traefik"
        assert entry.version == "1.2.0"
        assert entry.display_name == "Traefik"
        assert entry.category.value == "access"
        assert entry.type.value == "hybrid"
        assert len(entry.architectures) == 2
        assert entry.checksum_sha256 == "a" * 64
        assert entry.tags == ["reverse-proxy", "tls"]

    def test_registry_plugin_entry_invalid_name(self, valid_entry_data: Dict[str, Any]) -> None:
        """Un name non kebab-case lève une ValidationError."""
        valid_entry_data["name"] = "INVALID NAME!"
        with pytest.raises(ValidationError, match="kebab-case"):
            RegistryPluginEntry(**valid_entry_data)

    def test_registry_plugin_entry_invalid_version(self, valid_entry_data: Dict[str, Any]) -> None:
        """Une version non semver lève une ValidationError."""
        valid_entry_data["version"] = "not-semver"
        with pytest.raises(ValidationError, match="semver"):
            RegistryPluginEntry(**valid_entry_data)

    def test_registry_plugin_entry_invalid_url(self, valid_entry_data: Dict[str, Any]) -> None:
        """Une download_url non HTTPS lève une ValidationError."""
        valid_entry_data["download_url"] = "http://example.com/package.tar.gz"
        with pytest.raises(ValidationError, match="HTTPS"):
            RegistryPluginEntry(**valid_entry_data)

    def test_registry_plugin_entry_invalid_checksum(self, valid_entry_data: Dict[str, Any]) -> None:
        """Un checksum non hex 64 chars lève une ValidationError."""
        valid_entry_data["checksum_sha256"] = "not-hex"
        with pytest.raises(ValidationError, match="hexadécimale"):
            RegistryPluginEntry(**valid_entry_data)

    def test_registry_plugin_entry_empty_architectures(self, valid_entry_data: Dict[str, Any]) -> None:
        """Une liste d'architectures vide lève une ValidationError."""
        valid_entry_data["architectures"] = []
        with pytest.raises(ValidationError):
            RegistryPluginEntry(**valid_entry_data)


# ── Tests RegistryIndex ─────────────────────────────────────────────────────


class TestRegistryIndex:
    """Tests du schéma RegistryIndex."""

    def test_registry_index_valid(self, valid_index_data: Dict[str, Any]) -> None:
        """Un index complet valide passe la validation."""
        index = RegistryIndex(**valid_index_data)
        assert index.version == "1.0"
        assert len(index.plugins) == 1
        assert index.plugins[0].name == "traefik"

    def test_registry_index_empty_plugins(self, valid_index_data: Dict[str, Any]) -> None:
        """Un index avec liste plugins vide passe la validation."""
        valid_index_data["plugins"] = []
        index = RegistryIndex(**valid_index_data)
        assert index.version == "1.0"
        assert len(index.plugins) == 0


# ── Tests RegistryPluginSummaryResponse ─────────────────────────────────────


class TestRegistryPluginSummaryResponse:
    """Tests du schéma RegistryPluginSummaryResponse."""

    def test_registry_plugin_summary_response(self) -> None:
        """La sérialisation du summary est correcte."""
        summary = RegistryPluginSummaryResponse(
            name="traefik",
            version="1.2.0",
            display_name="Traefik",
            description="Reverse proxy",
            category="access",
            tags=["proxy"],
        )
        assert summary.name == "traefik"
        assert summary.version == "1.2.0"
        assert summary.category == "access"
        assert summary.tags == ["proxy"]
        # Vérifie la sérialisation JSON
        data = summary.model_dump()
        assert "download_url" not in data
        assert "checksum_sha256" not in data


# ── Tests RegistryPluginDetailResponse ──────────────────────────────────────


class TestRegistryPluginDetailResponse:
    """Tests du schéma RegistryPluginDetailResponse."""

    def test_registry_plugin_detail_response(self) -> None:
        """La sérialisation du detail est correcte avec tous les champs."""
        detail = RegistryPluginDetailResponse(
            name="traefik",
            version="1.2.0",
            display_name="Traefik",
            description="Reverse proxy",
            category="access",
            type="hybrid",
            author="WindFlow Team",
            license="MIT",
            architectures=["linux/amd64", "linux/arm64"],
            download_url="https://registry.windflow.io/plugins/traefik/1.2.0/package.tar.gz",
            checksum_sha256="a" * 64,
            homepage="https://github.com/windflow/plugin-traefik",
            tags=["proxy"],
        )
        assert detail.name == "traefik"
        assert detail.download_url.startswith("https://")
        assert len(detail.checksum_sha256) == 64
        # Vérifie la sérialisation JSON
        data = detail.model_dump()
        assert "download_url" in data
        assert "checksum_sha256" in data
        assert "architectures" in data
