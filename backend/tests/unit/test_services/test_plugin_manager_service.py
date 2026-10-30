"""
Tests unitaires du service PluginManagerService.

Couvre : install, update, uninstall, configure, list, get,
gestion d'erreurs, validation manifest, sécurité (password masking),
installation depuis une source registre (STORY-169.1 — volet download),
validation environnement (STORY-169.2 — volet VALIDATE), install réel
hook + compose up + rollback complet (STORY-169.3 — volet INSTALL).
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.events import EventType
from app.core.exceptions import WindFlowException
from app.core.secret_manager import reset_secret_manager
from app.models.organization import Organization
from app.models.plugin import (
    Plugin,
    PluginStatus,
    decrypt_config_values_from_storage,
)
from app.models.plugin_hook_log import PluginHookLog
from app.models.user import User
from app.schemas.plugin import (
    PluginConfigureRequest,
    PluginInstallRequest,
    PluginUpdateRequest,
)
from app.schemas.plugin_manifest import parse_dependency_string
from app.schemas.plugin_package import PluginPackageResult
from app.schemas.plugin_registry import RegistryPluginEntry
from app.services.plugin_manager_service import PluginManagerService

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _fresh_secret_manager():
    """Instance SecretManager isolée par test (STORY-169.4)."""
    reset_secret_manager()
    yield
    reset_secret_manager()


@pytest.fixture()
def service() -> PluginManagerService:
    """Instance du service PluginManager."""
    return PluginManagerService()


@pytest.fixture()
def pkg_settings(tmp_path: Path) -> Settings:
    """Settings isolés : plugins_base_dir dans tmp_path (STORY-169.1)."""
    return Settings(plugins_base_dir=str(tmp_path))


@pytest.fixture()
def sourced_service(pkg_settings: Settings) -> PluginManagerService:
    """Service avec settings isolés et sous-services registre/package/
    validation mockés (STORY-169.1/169.2 — injectables pour les tests,
    indépendants de la machine hôte)."""
    manager = PluginManagerService(pkg_settings)
    manager._registry_service = AsyncMock()
    manager._package_service = AsyncMock()
    manager._validation_service = MagicMock()
    return manager


def _compose_manager(sourced_service: PluginManagerService) -> PluginManagerService:
    """Prépare le service pour les tests INSTALL (STORY-169.3) :
    ComposeExecutor et lifecycle mockés (jamais de Docker réel ni de
    subprocess en unitaire) — le lifecycle retourne le plugin par
    défaut (no-op hook), les cas d'échec le surchargent."""
    sourced_service._compose_executor = AsyncMock()
    sourced_service._compose_executor.deploy_compose = AsyncMock(
        return_value=(True, "deployed")
    )
    sourced_service._compose_executor.remove_compose = AsyncMock(
        return_value=(True, "removed")
    )
    sourced_service._lifecycle_service = AsyncMock()
    sourced_service._lifecycle_service.execute_lifecycle_transition = AsyncMock(
        side_effect=lambda _db, plugin, _transition, _user: plugin
    )
    return sourced_service


def _service_manifest_yaml(name: str = "redis-service") -> str:
    """Manifest minimal de type service (compose_file obligatoire)."""
    return (
        "name: %s\n"
        "version: 1.0.0\n"
        'display_name: "%s"\n'
        'description: "Service plugin for compose tests"\n'
        "category: database\n"
        'author: "Test Author"\n'
        "license: MIT\n"
        "type: service\n"
        "architectures:\n"
        "  - linux/amd64\n"
        "compose_file: docker-compose.yml\n" % (name, name)
    )


def _hybrid_manifest_yaml(name: str = "hybrid-plugin") -> str:
    """Manifest minimal de type hybrid (compose_file + extensions)."""
    return (
        "name: %s\n"
        "version: 1.0.0\n"
        'display_name: "%s"\n'
        'description: "Hybrid plugin for compose tests"\n'
        "category: other\n"
        'author: "Test Author"\n'
        "license: MIT\n"
        "type: hybrid\n"
        "architectures:\n"
        "  - linux/amd64\n"
        "compose_file: docker-compose.yml\n"
        "extensions:\n"
        "  api_module: extensions/api.py\n" % (name, name)
    )


def _write_package(
    base: Path,
    name: str,
    manifest_yaml: str,
    compose: bool = True,
) -> Path:
    """Écrit un package local ``base/name/`` : windflow-plugin.yml (+ un
    docker-compose.yml factice si ``compose``). Retourne le chemin."""
    pkg_dir = base / name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "windflow-plugin.yml").write_text(manifest_yaml, encoding="utf-8")
    if compose:
        (pkg_dir / "docker-compose.yml").write_text(
            "services:\n  app:\n    image: alpine\n", encoding="utf-8"
        )
    return pkg_dir


def _sourced_package(
    pkg_settings: Settings,
    entry: RegistryPluginEntry,
    manifest_yaml: str,
    compose: bool = True,
) -> Any:
    """Simule l'extraction 169.1 d'un package contenant le manifest +
    compose, et branche le package service mocké."""
    extracted = _write_package(
        Path(pkg_settings.plugins_base_dir), entry.name, manifest_yaml, compose
    )
    return PluginPackageResult(
        name=entry.name,
        version=entry.version,
        checksum_sha256=entry.checksum_sha256,
        package_size_bytes=2048,
        extracted_path=str(extracted),
        files_count=3 if compose else 2,
    )


async def _install_source(
    service: PluginManagerService,
    db_session: AsyncSession,
    test_superuser: User,
    test_organization: Organization,
    source: str = "redis-service",
) -> Plugin:
    """Raccourci : install_plugin via une source registre."""
    return await service.install_plugin(
        db_session,
        install_data=PluginInstallRequest(source=source),
        user_id=test_superuser.id,
        organization_id=test_organization.id,
    )


@pytest.fixture()
def registry_entry() -> RegistryPluginEntry:
    """Entrée de registre valide pour l'installation depuis une source."""
    return RegistryPluginEntry(
        name="traefik",
        version="1.2.0",
        display_name="Traefik",
        description="Reverse proxy avec TLS automatique",
        category="access",
        type="hybrid",
        author="WindFlow Team",
        license="MIT",
        architectures=["linux/amd64"],
        download_url="https://registry.example.com/plugins/traefik/1.2.0/package.tar.gz",
        checksum_sha256="a" * 64,
        tags=["proxy"],
    )


PACKAGE_MANIFEST_YAML = """\
name: traefik
version: 1.2.0
display_name: "Traefik"
description: "Reverse proxy avec TLS automatique"
category: access
author: "WindFlow Team"
license: MIT
type: extension
architectures:
  - linux/amd64
extensions:
  api_module: extensions/api.py
"""


def _fake_extraction(pkg_settings: Settings, entry: RegistryPluginEntry) -> Any:
    """Simule l'extraction du package : écrit un manifest valide et retourne
    le PluginPackageResult correspondant."""
    extracted = Path(pkg_settings.plugins_base_dir) / entry.name
    extracted.mkdir(parents=True, exist_ok=True)
    (extracted / "windflow-plugin.yml").write_text(
        PACKAGE_MANIFEST_YAML, encoding="utf-8"
    )
    return PluginPackageResult(
        name=entry.name,
        version=entry.version,
        checksum_sha256=entry.checksum_sha256,
        package_size_bytes=2048,
        extracted_path=str(extracted),
        files_count=2,
    )


VALID_MANIFEST_YAML = """
name: test-plugin
version: 1.0.0
display_name: "Test Plugin"
description: "A test plugin for unit tests"
category: other
author: "Test Author"
license: MIT
type: extension
architectures:
  - linux/amd64
extensions:
  api_module: extensions/api.py
"""

VALID_MANIFEST_V2_YAML = """
name: test-plugin
version: 2.0.0
display_name: "Test Plugin"
description: "A test plugin for unit tests"
category: other
author: "Test Author"
license: MIT
type: extension
architectures:
  - linux/amd64
extensions:
  api_module: extensions/api.py
"""

VALID_MANIFEST_WITH_PASSWORD_CONFIG = """
name: plugin-with-password
version: 1.0.0
display_name: "Plugin With Password"
description: "A plugin with password config"
category: other
author: "Test Author"
license: MIT
type: extension
architectures:
  - linux/amd64
extensions:
  api_module: extensions/api.py
config:
  - key: api_key
    label: "API Key"
    type: password
    required: true
  - key: host
    label: "Host"
    type: string
    required: true
    default: "localhost"
"""

INVALID_MANIFEST_YAML = """
name: INVALID NAME!
version: not-semver
"""


@pytest.fixture()
async def installed_plugin(
    db_session: AsyncSession,
    test_organization: Organization,
    test_superuser: User,
) -> Plugin:
    """Plugin déjà installé en base pour les tests."""
    plugin = Plugin(
        name="existing-plugin",
        version="1.0.0",
        display_name="Existing Plugin",
        description="An existing plugin",
        category="other",
        type="extension",
        status=PluginStatus.INSTALLED.value,
        manifest_data={
            "name": "existing-plugin",
            "version": "1.0.0",
            "display_name": "Existing Plugin",
            "description": "An existing plugin",
            "category": "other",
            "type": "extension",
            "config": [],
        },
        config_values={"host": "localhost"},
        organization_id=test_organization.id,
        installed_by=test_superuser.id,
    )
    db_session.add(plugin)
    await db_session.commit()
    await db_session.refresh(plugin)
    return plugin


# ── Tests list_plugins ──────────────────────────────────────────────────────


class TestListPlugins:
    """Tests de la méthode list_plugins."""

    @pytest.mark.asyncio
    async def test_list_plugins_returns_empty_list(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        service: PluginManagerService,
    ) -> None:
        """Cas nominal : liste vide pour une organisation sans plugins."""
        plugins = await service.list_plugins(db_session, test_organization.id)
        assert plugins == []

    @pytest.mark.asyncio
    async def test_list_plugins_returns_installed_plugins(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        service: PluginManagerService,
        installed_plugin: Plugin,
    ) -> None:
        """Cas nominal : liste avec plugins installés."""
        plugins = await service.list_plugins(db_session, test_organization.id)
        assert len(plugins) == 1
        assert plugins[0].name == "existing-plugin"


# ── Tests get_plugin ────────────────────────────────────────────────────────


class TestGetPlugin:
    """Tests des méthodes get_plugin et get_plugin_by_name."""

    @pytest.mark.asyncio
    async def test_get_plugin_by_id_returns_plugin(
        self,
        db_session: AsyncSession,
        service: PluginManagerService,
        installed_plugin: Plugin,
    ) -> None:
        """Cas nominal : récupération par ID."""
        plugin = await service.get_plugin(db_session, installed_plugin.id)
        assert plugin is not None
        assert plugin.id == installed_plugin.id
        assert plugin.name == "existing-plugin"

    @pytest.mark.asyncio
    async def test_get_plugin_by_id_returns_none_when_not_found(
        self,
        db_session: AsyncSession,
        service: PluginManagerService,
    ) -> None:
        """Cas d'erreur : ID inexistant retourne None."""
        plugin = await service.get_plugin(db_session, "nonexistent-id")
        assert plugin is None

    @pytest.mark.asyncio
    async def test_get_plugin_by_name_returns_plugin(
        self,
        db_session: AsyncSession,
        service: PluginManagerService,
        installed_plugin: Plugin,
    ) -> None:
        """Cas nominal : récupération par nom."""
        plugin = await service.get_plugin_by_name(db_session, "existing-plugin")
        assert plugin is not None
        assert plugin.name == "existing-plugin"


# ── Tests install_plugin ────────────────────────────────────────────────────


class TestInstallPlugin:
    """Tests de la méthode install_plugin."""

    @pytest.mark.asyncio
    async def test_install_plugin_with_valid_manifest(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        service: PluginManagerService,
    ) -> None:
        """Cas nominal : installation réussie avec manifest YAML valide."""
        install_data = PluginInstallRequest(manifest_yaml=VALID_MANIFEST_YAML)
        plugin = await service.install_plugin(
            db_session,
            install_data=install_data,
            user_id=test_superuser.id,
            organization_id=test_organization.id,
        )
        assert plugin.name == "test-plugin"
        assert plugin.version == "1.0.0"
        assert plugin.status == PluginStatus.INSTALLED.value
        assert plugin.organization_id == test_organization.id
        assert plugin.installed_by == test_superuser.id

    @pytest.mark.asyncio
    async def test_install_plugin_raises_on_duplicate_name(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        service: PluginManagerService,
        installed_plugin: Plugin,
    ) -> None:
        """Cas d'erreur : conflit si plugin déjà installé."""
        # Le manifest a le même name que installed_plugin
        duplicate_yaml = """
name: existing-plugin
version: 2.0.0
display_name: "Duplicate"
description: "Duplicate plugin"
category: other
author: "Test"
license: MIT
type: extension
architectures:
  - linux/amd64
extensions:
  api_module: api.py
"""
        install_data = PluginInstallRequest(manifest_yaml=duplicate_yaml)
        with pytest.raises(WindFlowException, match="déjà installé"):
            await service.install_plugin(
                db_session,
                install_data=install_data,
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )

    @pytest.mark.asyncio
    async def test_install_plugin_raises_on_invalid_manifest(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        service: PluginManagerService,
    ) -> None:
        """Cas d'erreur : manifest YAML invalide."""
        install_data = PluginInstallRequest(manifest_yaml=INVALID_MANIFEST_YAML)
        with pytest.raises(WindFlowException):
            await service.install_plugin(
                db_session,
                install_data=install_data,
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )


# ── Tests update_plugin ─────────────────────────────────────────────────────


class TestUpdatePlugin:
    """Tests de la méthode update_plugin."""

    @pytest.mark.asyncio
    async def test_update_plugin_with_valid_version(
        self,
        db_session: AsyncSession,
        test_superuser: User,
        service: PluginManagerService,
        installed_plugin: Plugin,
    ) -> None:
        """Cas nominal : mise à jour réussie."""
        update_data = PluginUpdateRequest(version="2.0.0")
        plugin = await service.update_plugin(
            db_session,
            plugin_id=installed_plugin.id,
            update_data=update_data,
            user_id=test_superuser.id,
        )
        assert plugin.version == "2.0.0"
        assert plugin.status == PluginStatus.INSTALLED.value

    @pytest.mark.asyncio
    async def test_update_plugin_raises_when_not_found(
        self,
        db_session: AsyncSession,
        test_superuser: User,
        service: PluginManagerService,
    ) -> None:
        """Cas d'erreur : plugin inexistant."""
        update_data = PluginUpdateRequest(version="2.0.0")
        with pytest.raises(WindFlowException, match="non trouvé"):
            await service.update_plugin(
                db_session,
                plugin_id="nonexistent-id",
                update_data=update_data,
                user_id=test_superuser.id,
            )


# ── Tests uninstall_plugin ──────────────────────────────────────────────────


class TestUninstallPlugin:
    """Tests de la méthode uninstall_plugin."""

    @pytest.mark.asyncio
    async def test_uninstall_plugin_removes_from_db(
        self,
        db_session: AsyncSession,
        test_superuser: User,
        service: PluginManagerService,
        installed_plugin: Plugin,
    ) -> None:
        """Cas nominal : désinstallation réussie."""
        await service.uninstall_plugin(
            db_session,
            plugin_id=installed_plugin.id,
            user_id=test_superuser.id,
        )
        # Vérifier que le plugin n'existe plus
        plugin = await service.get_plugin(db_session, installed_plugin.id)
        assert plugin is None

    @pytest.mark.asyncio
    async def test_uninstall_plugin_raises_when_not_found(
        self,
        db_session: AsyncSession,
        test_superuser: User,
        service: PluginManagerService,
    ) -> None:
        """Cas d'erreur : plugin inexistant."""
        with pytest.raises(WindFlowException, match="non trouvé"):
            await service.uninstall_plugin(
                db_session,
                plugin_id="nonexistent-id",
                user_id=test_superuser.id,
            )


# ── Tests configure_plugin ──────────────────────────────────────────────────


class TestConfigurePlugin:
    """Tests de la méthode configure_plugin."""

    @pytest.mark.asyncio
    async def test_configure_plugin_updates_config_values(
        self,
        db_session: AsyncSession,
        test_superuser: User,
        service: PluginManagerService,
        installed_plugin: Plugin,
    ) -> None:
        """Cas nominal : configuration mise à jour."""
        config_data = PluginConfigureRequest(
            config_values={"host": "0.0.0.0", "port": 9090}
        )
        plugin = await service.configure_plugin(
            db_session,
            plugin_id=installed_plugin.id,
            config_data=config_data,
            user_id=test_superuser.id,
        )
        assert plugin.config_values["host"] == "0.0.0.0"
        assert plugin.config_values["port"] == 9090

    @pytest.mark.asyncio
    async def test_configure_plugin_masks_password_fields(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        service: PluginManagerService,
    ) -> None:
        """Sécurité : champs password masqués dans le résultat via PluginResponse."""
        # Installer un plugin avec config password
        install_data = PluginInstallRequest(
            manifest_yaml=VALID_MANIFEST_WITH_PASSWORD_CONFIG,
            config_values={"api_key": "super-secret-key", "host": "localhost"},
        )
        plugin = await service.install_plugin(
            db_session,
            install_data=install_data,
            user_id=test_superuser.id,
            organization_id=test_organization.id,
        )

        # STORY-169.4 (C12) : la valeur brute en base est un token
        # Fernet — plus jamais le secret en clair (divergence assumée :
        # l'ancienne assertion d'un stockage clair est obsolète par
        # conception).
        stored = plugin.config_values.get("api_key")
        assert isinstance(stored, str) and stored.startswith("gAAAA")
        assert stored != "super-secret-key"

        # Vérifier via PluginResponse que le password est masqué
        from app.schemas.plugin import PluginResponse

        response = PluginResponse.model_validate(plugin)
        assert response.config_values["api_key"] == "********"
        assert response.config_values["host"] == "localhost"


# ── Tests install depuis une source (STORY-169.1 — volet download) ─────────


class TestInstallFromSource:
    """Tests de l'installation depuis une source registre (STORY-169.1)."""

    @pytest.mark.asyncio
    async def test_install_from_source_success(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        sourced_service: PluginManagerService,
        pkg_settings: Settings,
        registry_entry: RegistryPluginEntry,
    ) -> None:
        """Cas nominal : source = nom registre → plugin créé, statut
        installed, manifest issu du package extrait."""
        sourced_service._registry_service.get_plugin = AsyncMock(
            return_value=registry_entry
        )
        sourced_service._package_service.download_and_extract = AsyncMock(
            return_value=_fake_extraction(pkg_settings, registry_entry)
        )

        plugin = await sourced_service.install_plugin(
            db_session,
            install_data=PluginInstallRequest(source="traefik"),
            user_id=test_superuser.id,
            organization_id=test_organization.id,
        )

        assert plugin.name == "traefik"
        assert plugin.version == "1.2.0"
        assert plugin.status == PluginStatus.INSTALLED.value
        # Le manifest en base provient bien du package extrait
        assert plugin.manifest_data["display_name"] == "Traefik"
        # L'extraction est en place sous plugins_base_dir/{name}/
        assert (
            Path(pkg_settings.plugins_base_dir) / "traefik" / "windflow-plugin.yml"
        ).exists()

    @pytest.mark.asyncio
    async def test_install_source_unknown_plugin_rejected(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        sourced_service: PluginManagerService,
    ) -> None:
        """Sécurité : registre ne connaît pas la source →
        plugin_not_in_registry, aucune ligne Plugin en base."""
        sourced_service._registry_service.get_plugin = AsyncMock(return_value=None)

        with pytest.raises(WindFlowException) as exc_info:
            await sourced_service.install_plugin(
                db_session,
                install_data=PluginInstallRequest(source="unknown-plugin"),
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )

        assert exc_info.value.details.get("error_type") == "plugin_not_in_registry"
        result = await db_session.execute(select(Plugin))
        assert result.scalars().all() == []
        # Le package service n'a jamais été appelé
        sourced_service._package_service.download_and_extract.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_install_source_url_not_in_registry_rejected(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        sourced_service: PluginManagerService,
    ) -> None:
        """Sécurité (arbitrage n°1) : URL qui ne correspond à aucune entrée
        du registre → rejet (pas de download sans checksum de registre)."""
        sourced_service._registry_service.list_plugins = AsyncMock(return_value=[])

        with pytest.raises(WindFlowException) as exc_info:
            await sourced_service.install_plugin(
                db_session,
                install_data=PluginInstallRequest(
                    source="https://evil.example.com/package.tar.gz"
                ),
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )

        assert exc_info.value.details.get("error_type") == "plugin_not_in_registry"
        result = await db_session.execute(select(Plugin))
        assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_install_source_checksum_mismatch_no_db_row(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        sourced_service: PluginManagerService,
        pkg_settings: Settings,
        registry_entry: RegistryPluginEntry,
    ) -> None:
        """Sécurité : checksum_mismatch du package service → exception
        remontée, aucune ligne Plugin, aucun résidu filesystem."""
        sourced_service._registry_service.get_plugin = AsyncMock(
            return_value=registry_entry
        )
        sourced_service._package_service.download_and_extract = AsyncMock(
            side_effect=WindFlowException(
                "Checksum SHA-256 invalide pour le package téléchargé",
                details={"error_type": "checksum_mismatch"},
            )
        )

        with pytest.raises(WindFlowException) as exc_info:
            await sourced_service.install_plugin(
                db_session,
                install_data=PluginInstallRequest(source="traefik"),
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )

        assert exc_info.value.details.get("error_type") == "checksum_mismatch"
        result = await db_session.execute(select(Plugin))
        assert result.scalars().all() == []
        # Aucun résidu : ni extraction ni staging
        base = Path(pkg_settings.plugins_base_dir)
        assert not (base / "traefik").exists()
        assert not (base / ".staging").exists()

    @pytest.mark.asyncio
    async def test_install_source_invalid_manifest_purges_extraction(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        sourced_service: PluginManagerService,
        pkg_settings: Settings,
        registry_entry: RegistryPluginEntry,
    ) -> None:
        """Sécurité : extraction OK puis manifest invalide → rejet
        manifest_invalid + plugins_base_dir/{name} purgé (rejet sans
        résidu)."""
        extracted = Path(pkg_settings.plugins_base_dir) / registry_entry.name
        extracted.mkdir(parents=True)
        (extracted / "windflow-plugin.yml").write_text(
            "name: INVALID NAME!\nversion: not-semver\n", encoding="utf-8"
        )
        sourced_service._registry_service.get_plugin = AsyncMock(
            return_value=registry_entry
        )
        sourced_service._package_service.download_and_extract = AsyncMock(
            return_value=PluginPackageResult(
                name=registry_entry.name,
                version=registry_entry.version,
                checksum_sha256=registry_entry.checksum_sha256,
                package_size_bytes=2048,
                extracted_path=str(extracted),
                files_count=2,
            )
        )

        with pytest.raises(WindFlowException) as exc_info:
            await sourced_service.install_plugin(
                db_session,
                install_data=PluginInstallRequest(source="traefik"),
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )

        assert exc_info.value.details.get("error_type") == "manifest_invalid"
        # Le répertoire extrait a été purgé
        assert not extracted.exists()
        result = await db_session.execute(select(Plugin))
        assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_install_manifest_yaml_path_unchanged(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        tmp_path: Path,
    ) -> None:
        """Non-régression : le chemin local manifest_yaml existant continue
        de fonctionner sans toucher au filesystem."""
        # Base dédiée (distincte de tmp_path qui héberge la DB de test)
        base = tmp_path / "plugins-local"
        local_service = PluginManagerService(Settings(plugins_base_dir=str(base)))

        plugin = await local_service.install_plugin(
            db_session,
            install_data=PluginInstallRequest(manifest_yaml=VALID_MANIFEST_YAML),
            user_id=test_superuser.id,
            organization_id=test_organization.id,
        )

        assert plugin.name == "test-plugin"
        assert plugin.status == PluginStatus.INSTALLED.value
        # Aucune écriture filesystem : plugins_base_dir n'a pas été créé
        # (l'installation locale ne télécharge rien).
        assert not base.exists()


# ── Tests validation environnement (STORY-169.2 — volet VALIDATE) ────────────


class TestValidateEnvironment:
    """Tests du branchement de PluginValidationService dans install_plugin
    (STORY-169.2) : validation avant toute écriture DB + purge du package
    extrait sur rejet (branche source uniquement)."""

    @pytest.mark.asyncio
    async def test_install_from_source_calls_validate_environment(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        sourced_service: PluginManagerService,
        pkg_settings: Settings,
        registry_entry: RegistryPluginEntry,
    ) -> None:
        """Cas nominal : install source succès → validate_environment
        appelé une fois avec le manifest extrait, avant la création DB
        (assert d'ordre via les mocks)."""
        sourced_service._registry_service.get_plugin = AsyncMock(
            return_value=registry_entry
        )
        sourced_service._package_service.download_and_extract = AsyncMock(
            return_value=_fake_extraction(pkg_settings, registry_entry)
        )
        # Spy sur la création DB : plugin instancié seulement après validation
        validation_mock = sourced_service._validation_service.validate_environment

        plugin = await sourced_service.install_plugin(
            db_session,
            install_data=PluginInstallRequest(source="traefik"),
            user_id=test_superuser.id,
            organization_id=test_organization.id,
        )

        assert plugin.name == "traefik"
        assert plugin.status == PluginStatus.INSTALLED.value
        # validate_environment appelé exactement une fois, avec le manifest
        # extrait (name du package, pas celui de l'entry)
        validation_mock.assert_called_once()
        validated_manifest = validation_mock.call_args[0][0]
        assert validated_manifest.name == "traefik"
        assert validated_manifest.version == "1.2.0"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error_type",
        [
            "architecture_incompatible",
            "insufficient_resources",
            "windflow_version_incompatible",
        ],
    )
    async def test_install_source_validation_failure_purges_extraction(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        sourced_service: PluginManagerService,
        pkg_settings: Settings,
        registry_entry: RegistryPluginEntry,
        error_type: str,
    ) -> None:
        """AC 1 + AC 2 : échec validate_environment (architecture /
        ressources / version) → exception remontée avec error_type
        préservé, plugins_base_dir/{name} purgé, aucune ligne Plugin en
        base."""
        result = _fake_extraction(pkg_settings, registry_entry)
        extracted = Path(result.extracted_path)
        assert extracted.exists()  # pré-condition : extraction en place
        sourced_service._registry_service.get_plugin = AsyncMock(
            return_value=registry_entry
        )
        sourced_service._package_service.download_and_extract = AsyncMock(
            return_value=result
        )
        sourced_service._validation_service.validate_environment = MagicMock(
            side_effect=WindFlowException(
                f"Rejet de validation ({error_type})",
                details={"error_type": error_type},
            )
        )

        with pytest.raises(WindFlowException) as exc_info:
            await sourced_service.install_plugin(
                db_session,
                install_data=PluginInstallRequest(source="traefik"),
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )

        # error_type du service de validation préservé tel quel
        assert exc_info.value.details.get("error_type") == error_type
        # AC 2 : rejet sans résidu — le répertoire extrait a été purgé
        assert not extracted.exists()
        # Aucune inscription en base
        select_result = await db_session.execute(select(Plugin))
        assert select_result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_install_manifest_yaml_validates_environment(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        sourced_service: PluginManagerService,
    ) -> None:
        """Branche locale : validate_environment appelé après validation du
        manifest YAML ; échec → rejet et **aucune tentative de purge**
        (aucun chemin extrait — vérifié par patch de shutil.rmtree)."""
        validation_mock = sourced_service._validation_service.validate_environment
        validation_mock.side_effect = WindFlowException(
            "Version WindFlow insuffisante",
            details={"error_type": "windflow_version_incompatible"},
        )

        with pytest.raises(WindFlowException) as exc_info, patch(
            "app.services.plugin_manager_service.shutil.rmtree"
        ) as rmtree_mock:
            await sourced_service.install_plugin(
                db_session,
                install_data=PluginInstallRequest(manifest_yaml=VALID_MANIFEST_YAML),
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )

        assert (
            exc_info.value.details.get("error_type") == "windflow_version_incompatible"
        )
        validation_mock.assert_called_once()
        # Branche locale : rien n'a été extrait → aucun rmtree exécuté
        rmtree_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_install_manifest_yaml_environment_failure_no_db_row(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        sourced_service: PluginManagerService,
    ) -> None:
        """Cas d'erreur : échec validation sur branche locale → aucune
        ligne Plugin en base (validation AVANT toute écriture)."""
        sourced_service._validation_service.validate_environment.side_effect = (
            WindFlowException(
                "Architecture incompatible",
                details={"error_type": "architecture_incompatible"},
            )
        )

        with pytest.raises(WindFlowException):
            await sourced_service.install_plugin(
                db_session,
                install_data=PluginInstallRequest(manifest_yaml=VALID_MANIFEST_YAML),
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )

        select_result = await db_session.execute(select(Plugin))
        assert select_result.scalars().all() == []


# ── Tests INSTALL réel : compose + hooks + rollback (STORY-169.3) ───────────


def _sourced_package_for(
    pkg_settings: Settings, name: str, manifest_yaml: str, compose: bool = True
) -> Any:
    """Simule l'extraction 169.1 d'un package pour un nom libre (évite
    le unique=True sur les noms déjà utilisés par d'autres tests)."""
    extracted = _write_package(
        Path(pkg_settings.plugins_base_dir), name, manifest_yaml, compose
    )
    return PluginPackageResult(
        name=name,
        version="1.0.0",
        checksum_sha256="c" * 64,
        package_size_bytes=2048,
        extracted_path=str(extracted),
        files_count=3 if compose else 2,
    )


def _wire_source(
    manager: PluginManagerService,
    pkg_settings: Settings,
    name: str,
    manifest_yaml: str,
    compose: bool = True,
) -> None:
    """Branche les mocks source (registre/package/validation) pour un
    plugin ``name`` : le package extrait contient le manifest (+ compose
    factice). Circuit complet de la branche source sans réseau."""
    manager._registry_service = AsyncMock()
    manager._package_service = AsyncMock()
    manager._validation_service = MagicMock()
    manager._registry_service.get_plugin = AsyncMock(
        return_value=RegistryPluginEntry(
            name=name,
            version="1.0.0",
            display_name=name,
            description="Plugin for compose tests",
            category="database",
            type="service",
            author="Test Author",
            license="MIT",
            architectures=["linux/amd64"],
            download_url=f"https://registry.example.com/plugins/{name}/1.0.0/package.tar.gz",
            checksum_sha256="b" * 64,
            tags=[],
        )
    )
    manager._package_service.download_and_extract = AsyncMock(
        return_value=_sourced_package_for(pkg_settings, name, manifest_yaml, compose)
    )


def _hook_failure(exc: WindFlowException) -> AsyncMock:
    """Lifecycle mock levant ``exc`` sur toute transition."""
    return AsyncMock(side_effect=lambda _db, _p, _t, _u: (_ for _ in ()).throw(exc))


class TestInstallServiceCompose:
    """Cas nominaux AC 1 : compose up pour service/hybrid, statut
    running, événements émis (lifecycle + ComposeExecutor mockés)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("manifest_yaml", "plugin_name"),
        [
            (_service_manifest_yaml("redis-service"), "redis-service"),
            (_hybrid_manifest_yaml("hybrid-plugin"), "hybrid-plugin"),
        ],
    )
    async def test_install_service_runs_compose_and_reaches_running(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
        manifest_yaml: str,
        plugin_name: str,
    ) -> None:
        """AC 1 : service/hybrid → deploy_compose awaited une fois avec
        le project conventionné windflow-plugin-{name} et le compose
        résolu sous plugins_base_dir/{name}/docker-compose.yml, statut
        final running, événement PLUGIN_INSTALLED émis."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(manager, pkg_settings, plugin_name, manifest_yaml)

        with patch("app.core.events.get_event_bus") as bus_mock:
            bus_mock.return_value.emit = AsyncMock()
            plugin = await _install_source(
                manager, db_session, test_superuser, test_organization, plugin_name
            )

        assert plugin.status == PluginStatus.RUNNING.value
        manager._compose_executor.deploy_compose.assert_awaited_once()
        call = manager._compose_executor.deploy_compose.await_args
        assert call.args[1] == f"windflow-plugin-{plugin_name}"
        assert str(call.args[0]) == str(
            Path(pkg_settings.plugins_base_dir) / plugin_name / "docker-compose.yml"
        )
        emitted = [c.args[0] for c in bus_mock.return_value.emit.await_args_list]
        assert EventType.PLUGIN_INSTALLED in emitted

    @pytest.mark.asyncio
    async def test_install_extension_skips_compose_stays_installed(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Non-régression : extension → aucun compose, statut installed
        (le chargement d'extension relève de STORY-170)."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(
            manager,
            pkg_settings,
            "ext-plugin",
            PACKAGE_MANIFEST_YAML.replace("name: traefik", "name: ext-plugin"),
        )

        plugin = await _install_source(
            manager, db_session, test_superuser, test_organization, "ext-plugin"
        )

        assert plugin.status == PluginStatus.INSTALLED.value
        manager._compose_executor.deploy_compose.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_compose_receives_real_decrypted_password(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Sécurité (rules 40) — divergence n°4 assumée (STORY-169.4) :
        le compose reçoit la valeur RÉELLE déchiffrée en mémoire via
        _build_injection_env_vars (le conteneur a besoin du vrai secret,
        spec 11 étape 4) ; la valeur n'est JAMAIS loggée. Mise à jour du
        test 169.3 test_compose_receives_safe_env_vars (le masquage ***
        reste la règle pour les hooks, cf. test_hooks_still_receive_
        masked_passwords)."""
        manifest_yaml = _service_manifest_yaml("svc-with-password") + (
            "config:\n"
            "  - key: api_key\n"
            '    label: "API Key"\n'
            "    type: password\n"
            "    required: true\n"
        )
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(manager, pkg_settings, "svc-with-password", manifest_yaml)

        await manager.install_plugin(
            db_session,
            install_data=PluginInstallRequest(
                source="svc-with-password",
                config_values={"api_key": "super-secret", "host": "localhost"},
            ),
            user_id=test_superuser.id,
            organization_id=test_organization.id,
        )

        env_vars = manager._compose_executor.deploy_compose.await_args.args[2]
        assert env_vars["PLUGIN_CONFIG_API_KEY"] == "super-secret"
        assert env_vars["PLUGIN_CONFIG_HOST"] == "localhost"

    @pytest.mark.asyncio
    async def test_install_success_emits_events_and_keeps_row(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Succès : row unique en base, statut running, événement
        PLUGIN_INSTALLED publié sur le bus canonique."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(manager, pkg_settings, "redis-service", _service_manifest_yaml())

        with patch("app.core.events.get_event_bus") as bus_mock:
            bus_mock.return_value.emit = AsyncMock()
            plugin = await _install_source(
                manager, db_session, test_superuser, test_organization
            )

        assert plugin.status == PluginStatus.RUNNING.value
        result = await db_session.execute(select(Plugin))
        plugins = result.scalars().all()
        assert len(plugins) == 1
        assert plugins[0].name == plugin.name
        emitted = [c.args[0] for c in bus_mock.return_value.emit.await_args_list]
        assert EventType.PLUGIN_INSTALLED in emitted


class TestInstallHookFailureRollback:
    """AC 2 : échec du hook on_install → rollback complet DB +
    filesystem + conteneur, message cause + suggestion."""

    @pytest.mark.asyncio
    async def test_hook_failure_triggers_full_rollback(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """lifecycle lève hook_failed → remove_compose awaited avec
        remove_volumes=True, FS purgé, aucune ligne Plugin, erreur
        error_type préservé + rollback_performed + cause/suggestion."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(manager, pkg_settings, "redis-service", _service_manifest_yaml())
        manager._lifecycle_service.execute_lifecycle_transition = _hook_failure(
            WindFlowException(
                "Le hook 'on_install' a échoué : exit code 1",
                details={"error_type": "hook_failed", "hook_name": "on_install"},
            )
        )

        with pytest.raises(WindFlowException) as exc_info:
            await _install_source(
                manager, db_session, test_superuser, test_organization
            )

        assert exc_info.value.details.get("error_type") == "hook_failed"
        assert exc_info.value.details.get("rollback_performed") is True
        assert "Cause" in exc_info.value.message
        assert "Suggestion" in exc_info.value.message
        # compose down effectué (défense en profondeur, idempotent)
        manager._compose_executor.remove_compose.assert_awaited_once_with(
            "windflow-plugin-redis-service", remove_volumes=True
        )
        # FS purgé (branche source)
        assert not (Path(pkg_settings.plugins_base_dir) / "redis-service").exists()
        # aucune ligne en base
        result = await db_session.execute(select(Plugin))
        assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_hook_failure_no_hook_log_residue(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Arbitrage n°3 : le PluginHookLog du hook échoué est purgé
        (CASCADE SQLite inopérant sans pragma → purge explicite)."""

        async def _transition_with_log(db, plugin, transition, user):
            db.add(
                PluginHookLog(
                    plugin_id=plugin.id,
                    hook_name="on_install",
                    script_path="install.sh",
                    status="failed",
                )
            )
            await db.flush()
            raise WindFlowException(
                "hook failed", details={"error_type": "hook_failed"}
            )

        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(manager, pkg_settings, "redis-service", _service_manifest_yaml())
        manager._lifecycle_service.execute_lifecycle_transition = AsyncMock(
            side_effect=_transition_with_log
        )

        with pytest.raises(WindFlowException):
            await _install_source(
                manager, db_session, test_superuser, test_organization
            )

        logs = await db_session.execute(select(PluginHookLog))
        assert logs.scalars().all() == []

    @pytest.mark.asyncio
    async def test_local_manifest_hook_failure_never_purges_fs(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Arbitrage n°7 : branche manifest_yaml locale → rollback
        DB/compose mais le répertoire posé par l'utilisateur subsiste."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        manager._validation_service = MagicMock()
        # Fichiers posés par l'utilisateur (pas par WindFlow)
        user_dir = _write_package(
            Path(pkg_settings.plugins_base_dir),
            "local-svc",
            _service_manifest_yaml("local-svc"),
        )
        manager._lifecycle_service.execute_lifecycle_transition = _hook_failure(
            WindFlowException("hook failed", details={"error_type": "hook_failed"})
        )

        with pytest.raises(WindFlowException):
            await manager.install_plugin(
                db_session,
                install_data=PluginInstallRequest(
                    manifest_yaml=_service_manifest_yaml("local-svc")
                ),
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )

        assert user_dir.exists()
        result = await db_session.execute(select(Plugin))
        assert result.scalars().all() == []


class TestInstallComposeFailureRollback:
    """AC 2 : échec du déploiement Docker → rollback complet + message
    avec extrait de la sortie docker + suggestion, PLUGIN_ERROR émis."""

    @pytest.mark.asyncio
    async def test_compose_failure_triggers_full_rollback(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """deploy_compose échoue → remove_compose awaited, FS purgé,
        aucune ligne Plugin + PluginHookLog, compose_up_failed,
        PLUGIN_ERROR émis sur le bus avant la levée."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(manager, pkg_settings, "redis-service", _service_manifest_yaml())
        manager._compose_executor.deploy_compose = AsyncMock(
            return_value=(False, "pull access denied for redis")
        )

        with pytest.raises(WindFlowException) as exc_info, patch(
            "app.core.events.get_event_bus"
        ) as bus_mock:
            bus_mock.return_value.emit = AsyncMock()
            await _install_source(
                manager, db_session, test_superuser, test_organization
            )

        details = exc_info.value.details
        assert details.get("error_type") == "compose_up_failed"
        assert details.get("rollback_performed") is True
        assert "pull access denied" in exc_info.value.message
        assert "Suggestion" in exc_info.value.message
        manager._compose_executor.remove_compose.assert_awaited_once()
        assert not (Path(pkg_settings.plugins_base_dir) / "redis-service").exists()
        result = await db_session.execute(select(Plugin))
        assert result.scalars().all() == []
        logs = await db_session.execute(select(PluginHookLog))
        assert logs.scalars().all() == []
        emitted = [c.args[0] for c in bus_mock.return_value.emit.await_args_list]
        assert EventType.PLUGIN_ERROR in emitted

    @pytest.mark.asyncio
    async def test_compose_file_missing_rejected(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Arbitrage n°7 : manifest service sans compose sur disque →
        compose_file_missing + rollback DB (jamais à moitié installé),
        message mentionnant le chemin attendu et la suggestion registre."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(
            manager,
            pkg_settings,
            "redis-service",
            _service_manifest_yaml("redis-service"),
            compose=False,
        )

        with pytest.raises(WindFlowException) as exc_info:
            await _install_source(
                manager, db_session, test_superuser, test_organization
            )

        assert exc_info.value.details.get("error_type") == "compose_file_missing"
        assert exc_info.value.details.get("rollback_performed") is True
        assert "registre" in exc_info.value.message
        result = await db_session.execute(select(Plugin))
        assert result.scalars().all() == []
        manager._compose_executor.deploy_compose.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "compose_file",
        ["../../etc/compose.yml", "/etc/docker-compose.yml"],
    )
    async def test_compose_file_path_traversal_rejected(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
        compose_file: str,
    ) -> None:
        """Sécurité (arbitrage n°6) : chemin absolu ou avec .. →
        compose_file_invalid, aucun accès disque hors base (deploy
        jamais appelé, rollback DB effectif)."""
        malicious_yaml = (
            "name: evil-svc\n"
            "version: 1.0.0\n"
            'display_name: "Evil"\n'
            'description: "Path traversal attempt"\n'
            "category: other\n"
            'author: "Evil"\n'
            "license: MIT\n"
            "type: service\n"
            "architectures:\n"
            "  - linux/amd64\n"
            f"compose_file: {compose_file}\n"
        )
        manager = _compose_manager(PluginManagerService(pkg_settings))
        manager._validation_service = MagicMock()

        with pytest.raises(WindFlowException) as exc_info:
            await manager.install_plugin(
                db_session,
                install_data=PluginInstallRequest(manifest_yaml=malicious_yaml),
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )

        assert exc_info.value.details.get("error_type") == "compose_file_invalid"
        manager._compose_executor.deploy_compose.assert_not_awaited()
        result = await db_session.execute(select(Plugin))
        assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_compose_output_truncated_in_error(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Rules 40 : sortie docker de 10 000 chars → compose_output
        dans details ≤ 500 chars (pas de flood)."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(manager, pkg_settings, "redis-service", _service_manifest_yaml())
        manager._compose_executor.deploy_compose = AsyncMock(
            return_value=(False, "x" * 10_000)
        )

        with pytest.raises(WindFlowException) as exc_info:
            await _install_source(
                manager, db_session, test_superuser, test_organization
            )

        compose_output = exc_info.value.details.get("compose_output")
        assert compose_output is not None
        assert len(compose_output) <= 500


class TestRollbackDependenciesAndResiduals:
    """Rollback avec dépendances auto-installées + rollback partiel
    (divergence n°7)."""

    @pytest.mark.asyncio
    async def test_rollback_removes_auto_installed_dependencies(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Échec compose avec dépendance auto-installée → les DEUX rows
        supprimés (plugin + dépendance), aucune ligne Plugin restante."""
        import yaml as yaml_lib

        from app.schemas.plugin_manifest import PluginManifest
        from app.services.plugin_dependency_service import DependencyCheckResult

        manager = _compose_manager(PluginManagerService(pkg_settings))
        main_yaml = _service_manifest_yaml("main-svc") + (
            "dependencies:\n  requires:\n    - shared-dep\n"
        )
        _wire_source(manager, pkg_settings, "main-svc", main_yaml)
        manager._compose_executor.deploy_compose = AsyncMock(
            return_value=(False, "image not found")
        )

        dep_manifest = PluginManifest.model_validate(
            yaml_lib.safe_load(
                "name: shared-dep\n"
                "version: 1.0.0\n"
                'display_name: "Shared Dep"\n'
                'description: "Dependency plugin"\n'
                "category: other\n"
                'author: "Test"\n'
                "license: MIT\n"
                "type: extension\n"
                "architectures:\n"
                "  - linux/amd64\n"
                "extensions:\n"
                "  api_module: api.py\n"
            )
        )
        dep_service = AsyncMock()
        dep_service.check_install_dependencies = AsyncMock(
            return_value=DependencyCheckResult(
                can_proceed=False,
                missing=[parse_dependency_string("shared-dep")],
                version_mismatches=[],
                conflicts=[],
            )
        )
        dep_service.resolve_transitive_dependencies = AsyncMock(
            return_value=[dep_manifest]
        )
        manager._dependency_service = dep_service

        with pytest.raises(WindFlowException) as exc_info:
            await _install_source(
                manager, db_session, test_superuser, test_organization, "main-svc"
            )

        assert exc_info.value.details.get("error_type") == "compose_up_failed"
        result = await db_session.execute(select(Plugin))
        assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_rollback_partial_compose_failure_reports_residuals(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """remove_compose échoue aussi → rollback continue (FS purgé,
        DB vidée), details.rollback_residuals == ["compose"], code
        principal compose_up_failed préservé."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(manager, pkg_settings, "redis-service", _service_manifest_yaml())
        manager._compose_executor.deploy_compose = AsyncMock(
            return_value=(False, "image not found")
        )
        manager._compose_executor.remove_compose = AsyncMock(
            return_value=(False, "docker daemon down")
        )

        with pytest.raises(WindFlowException) as exc_info:
            await _install_source(
                manager, db_session, test_superuser, test_organization
            )

        details = exc_info.value.details
        assert details.get("error_type") == "compose_up_failed"
        assert details.get("rollback_residuals") == ["compose"]
        # Le rollback a continué malgré l'échec compose
        assert not (Path(pkg_settings.plugins_base_dir) / "redis-service").exists()
        result = await db_session.execute(select(Plugin))
        assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_rollback_uninstall_hook_failure_does_not_block(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """on_uninstall lève pendant le rollback → le rollback
        s'achève quand même (aucune exception secondaire remontée)."""

        async def _transition(_db, _plugin, transition, _user):
            if transition == "uninstall":
                raise WindFlowException(
                    "on_uninstall failed", details={"error_type": "hook_failed"}
                )
            return _plugin

        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(manager, pkg_settings, "redis-service", _service_manifest_yaml())
        manager._compose_executor.deploy_compose = AsyncMock(
            return_value=(False, "image not found")
        )
        manager._lifecycle_service.execute_lifecycle_transition = AsyncMock(
            side_effect=_transition
        )

        with pytest.raises(WindFlowException) as exc_info:
            await _install_source(
                manager, db_session, test_superuser, test_organization
            )

        # L'erreur principale reste compose_up_failed (pas hook_failed
        # de l'on_uninstall best-effort), aucun résidu database.
        assert exc_info.value.details.get("error_type") == "compose_up_failed"
        assert exc_info.value.details.get("rollback_residuals", []) == []
        result = await db_session.execute(select(Plugin))
        assert result.scalars().all() == []


class TestInstallStatusArbitration:
    """AC 3 : arbitrage n°2 — statuts finaux par type, jamais
    d'intermédiaire installed pour un service."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("plugin_type", "expected_status"),
        [
            ("service", "running"),
            ("hybrid", "running"),
            ("extension", "installed"),
        ],
    )
    async def test_final_status_by_type(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
        plugin_type: str,
        expected_status: str,
    ) -> None:
        """Paramétré : service/hybrid → running, extension → installed ;
        le row naît installing et passe directement au statut final
        (jamais downloading/validating/starting persistés)."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        if plugin_type == "extension":
            manifest_yaml = PACKAGE_MANIFEST_YAML.replace(
                "name: traefik", "name: status-extension"
            )
            _wire_source(manager, pkg_settings, "status-extension", manifest_yaml)
            plugin = await _install_source(
                manager,
                db_session,
                test_superuser,
                test_organization,
                "status-extension",
            )
        elif plugin_type == "hybrid":
            manifest_yaml = _hybrid_manifest_yaml("status-hybrid")
            _wire_source(manager, pkg_settings, "status-hybrid", manifest_yaml)
            plugin = await _install_source(
                manager, db_session, test_superuser, test_organization, "status-hybrid"
            )
        else:
            manifest_yaml = _service_manifest_yaml("status-service")
            _wire_source(manager, pkg_settings, "status-service", manifest_yaml)
            plugin = await _install_source(
                manager,
                db_session,
                test_superuser,
                test_organization,
                "status-service",
            )

        assert plugin.status == expected_status

    @pytest.mark.asyncio
    async def test_no_intermediate_installed_commit_for_service(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Le segment INSTALLING → INSTALLED pré-compose de l'ancien
        code est supprimé : un plugin service n'est jamais observé
        installed après un succès (statut final running direct)."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(manager, pkg_settings, "redis-service", _service_manifest_yaml())

        # Le spy de commit observe chaque statut persisté en base.
        statuses_persisted: list = []
        original_commit = db_session.commit

        async def _spy_commit():
            await original_commit()
            for obj in getattr(db_session, "new", []) or []:
                statuses_persisted.append(getattr(obj, "status", None))

        with patch.object(db_session, "commit", side_effect=_spy_commit):
            plugin = await _install_source(
                manager, db_session, test_superuser, test_organization
            )

        assert plugin.status == PluginStatus.RUNNING.value
        # Statut final (post-dernier commit) jamais "installed" pour un
        # service : le segment intermédiaire a disparu.
        result = await db_session.execute(select(Plugin))
        final = result.scalars().all()
        assert len(final) == 1
        assert final[0].status == PluginStatus.RUNNING.value
        assert final[0].status != PluginStatus.INSTALLED.value
        # Aucun commit intermédiaire n'a persisté "installed" (le row
        # naît installing, dernier commit = running).
        assert PluginStatus.INSTALLED.value not in [
            s for s in statuses_persisted if s is not None
        ]


# ── STORY-169.4 : CONFIGURE chiffré et injection déchiffrée ──────────────────

_PASSWORD_MANIFEST_SUFFIX = (
    "config:\n"
    "  - key: api_key\n"
    '    label: "API Key"\n'
    "    type: password\n"
    "    required: true\n"
)


def _password_manifest_yaml(name: str = "svc-crypto") -> str:
    """Manifest service avec un champ password (variant 169.4)."""
    return _service_manifest_yaml(name) + _PASSWORD_MANIFEST_SUFFIX


async def _fetch_raw_config_values(db_session: AsyncSession, name: str) -> dict:
    """Oracle at-rest : lecture BRUTE de la colonne config_values via
    SQL text() (jamais via l'ORM — pattern test_secret_encryption)."""
    result = await db_session.execute(
        text("SELECT config_values FROM plugins WHERE name = :name"),
        {"name": name},
    )
    row = result.scalar_one_or_none()
    if row is None:
        return {}
    if isinstance(row, str):
        return json.loads(row)
    return dict(row)


class TestConfigValuesEncryptionAtRest:
    """AC 1 (169.4) : les valeurs password sont chiffrées en base."""

    @pytest.mark.asyncio
    async def test_install_encrypts_password_values_in_db(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Install avec password → SELECT brut : api_key = token gAAAA
        (≠ clair), host lisible (clé conservée, valeur chiffrée)."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(manager, pkg_settings, "svc-crypto", _password_manifest_yaml())

        await manager.install_plugin(
            db_session,
            install_data=PluginInstallRequest(
                source="svc-crypto",
                config_values={"api_key": "super-secret", "host": "localhost"},
            ),
            user_id=test_superuser.id,
            organization_id=test_organization.id,
        )

        stored = await _fetch_raw_config_values(db_session, "svc-crypto")
        assert isinstance(stored.get("api_key"), str)
        assert stored["api_key"].startswith("gAAAA")
        assert stored["api_key"] != "super-secret"
        assert stored["host"] == "localhost"

    @pytest.mark.asyncio
    async def test_configure_encrypts_new_password_and_keeps_existing_tokens(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Configure d'une nouvelle clé password → token en base ; le
        token de la clé non re-saisie est conservé byte-à-byte."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        manifest_yaml = _password_manifest_yaml("svc-merge") + (
            "  - key: second_key\n"
            '    label: "Second"\n'
            "    type: password\n"
            "    required: false\n"
        )
        _wire_source(manager, pkg_settings, "svc-merge", manifest_yaml)

        plugin = await manager.install_plugin(
            db_session,
            install_data=PluginInstallRequest(
                source="svc-merge",
                config_values={"api_key": "first-secret"},
            ),
            user_id=test_superuser.id,
            organization_id=test_organization.id,
        )
        token_before = (await _fetch_raw_config_values(db_session, "svc-merge"))[
            "api_key"
        ]

        await manager.configure_plugin(
            db_session,
            plugin_id=plugin.id,
            config_data=PluginConfigureRequest(
                config_values={"second_key": "second-secret"}
            ),
            user_id=test_superuser.id,
        )

        stored = await _fetch_raw_config_values(db_session, "svc-merge")
        assert stored["api_key"] == token_before
        assert isinstance(stored.get("second_key"), str)
        assert stored["second_key"].startswith("gAAAA")
        assert stored["second_key"] != "second-secret"

    @pytest.mark.asyncio
    async def test_configure_ignores_masked_roundtrip_value(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Configure renvoyant ******** sur une clé password existante →
        le secret stocké est inchangé, le masque n'est pas stocké
        (arbitrage n°5)."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(
            manager, pkg_settings, "svc-mask", _password_manifest_yaml("svc-mask")
        )

        plugin = await manager.install_plugin(
            db_session,
            install_data=PluginInstallRequest(
                source="svc-mask",
                config_values={"api_key": "original-secret"},
            ),
            user_id=test_superuser.id,
            organization_id=test_organization.id,
        )

        await manager.configure_plugin(
            db_session,
            plugin_id=plugin.id,
            config_data=PluginConfigureRequest(config_values={"api_key": "********"}),
            user_id=test_superuser.id,
        )

        stored = await _fetch_raw_config_values(db_session, "svc-mask")
        token = stored.get("api_key")
        assert isinstance(token, str) and token.startswith("gAAAA")
        assert token != "********"
        assert (
            decrypt_config_values_from_storage({"api_key": token})["api_key"]
            == "original-secret"
        )

    @pytest.mark.asyncio
    async def test_configure_reencrypts_legacy_plaintext(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Row seedé avec password en clair (legacy) + configure d'une
        autre clé → le password legacy est re-chiffré à l'occasion de
        l'écriture (double lecture terminée)."""
        from app.core.secret_manager import get_secret_manager

        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(
            manager, pkg_settings, "svc-legacy", _password_manifest_yaml("svc-legacy")
        )

        plugin = await manager.install_plugin(
            db_session,
            install_data=PluginInstallRequest(
                source="svc-legacy",
                config_values={"host": "db.internal"},
            ),
            user_id=test_superuser.id,
            organization_id=test_organization.id,
        )
        # Forcer un row legacy : password en clair directement en base.
        await db_session.execute(
            text("UPDATE plugins SET config_values = :cv " "WHERE id = :pid"),
            {
                "cv": '{"api_key": "legacy-clear-secret", "host": "db.internal"}',
                "pid": plugin.id,
            },
        )
        await db_session.commit()
        await db_session.refresh(plugin)
        assert plugin.config_values["api_key"] == "legacy-clear-secret"

        await manager.configure_plugin(
            db_session,
            plugin_id=plugin.id,
            config_data=PluginConfigureRequest(config_values={"port": "6380"}),
            user_id=test_superuser.id,
        )

        stored = await _fetch_raw_config_values(db_session, "svc-legacy")
        token = stored.get("api_key")
        assert isinstance(token, str) and token.startswith("gAAAA")
        assert token != "legacy-clear-secret"
        assert (
            decrypt_config_values_from_storage({"api_key": token})["api_key"]
            == "legacy-clear-secret"
        )
        assert stored["port"] == "6380"
        # get_secret_manager utilisé pour éviter l'import inutilisé flake8.
        assert get_secret_manager() is not None


class TestComposeInjectionDecrypted:
    """AC 1 (169.4, divergence n°4) : injection compose déchiffrée en
    mémoire + non-fuite des secrets."""

    @pytest.mark.asyncio
    async def test_compose_injection_never_logs_secret(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
        caplog,
    ) -> None:
        """Sécurité (rules 40) : aucun record de log ne contient le
        secret en clair ni son token pendant l'installation."""
        import logging as _logging

        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(
            manager, pkg_settings, "svc-log", _password_manifest_yaml("svc-log")
        )

        with caplog.at_level(_logging.INFO, logger="app.services"):
            await manager.install_plugin(
                db_session,
                install_data=PluginInstallRequest(
                    source="svc-log",
                    config_values={"api_key": "super-secret"},
                ),
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )

        token = (await _fetch_raw_config_values(db_session, "svc-log"))["api_key"]
        for record in caplog.records:
            assert "super-secret" not in record.getMessage()
            assert token not in record.getMessage()

    @pytest.mark.asyncio
    async def test_compose_failure_details_do_not_leak_secret(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Non-régression 169.3 : deploy_compose → (False, boom) →
        details[compose_output] tronqué, ni secret ni token dedans."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(manager, pkg_settings, "svc-fail", _password_manifest_yaml())
        manager._compose_executor.deploy_compose = AsyncMock(
            return_value=(False, "boom")
        )

        with pytest.raises(WindFlowException) as exc_info:
            await manager.install_plugin(
                db_session,
                install_data=PluginInstallRequest(
                    source="svc-fail",
                    config_values={"api_key": "super-secret"},
                ),
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )

        details_dump = str(exc_info.value.details)
        assert exc_info.value.details.get("error_type") == "compose_up_failed"
        assert "super-secret" not in details_dump
        assert "gAAAA" not in details_dump
        assert "PLUGIN_CONFIG_" not in details_dump

    @pytest.mark.asyncio
    async def test_decryption_failure_raises_typed_error_and_rolls_back(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Arbitrage n°6 : token corrompu en base → erreur typée
        config_decryption_failed avec cause + suggestion, aucune ligne
        Plugin après rollback (le catch 169.3 enchaîne)."""
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(
            manager, pkg_settings, "svc-bad", _password_manifest_yaml("svc-bad")
        )

        # Corrompre le token APRÈS l'écriture en base mais AVANT le
        # compose : le déchiffrement a lieu dans _deploy_plugin_compose,
        # donc la corruption passe par le hook on_install (exécuté juste
        # avant) — pas par un side_effect de deploy_compose (trop tard).
        async def _corrupt_config(_db, plugin, _transition, _user):
            await db_session.execute(
                text("UPDATE plugins SET config_values = :cv " "WHERE id = :pid"),
                {
                    "cv": (
                        '{"api_key": "gAAAAcorrupted-token-invalid", '
                        '"host": "localhost"}'
                    ),
                    "pid": plugin.id,
                },
            )
            await db_session.commit()
            await db_session.refresh(plugin)
            return plugin

        manager._lifecycle_service.execute_lifecycle_transition = AsyncMock(
            side_effect=_corrupt_config
        )

        with pytest.raises(WindFlowException) as exc_info:
            await manager.install_plugin(
                db_session,
                install_data=PluginInstallRequest(
                    source="svc-bad",
                    config_values={"api_key": "super-secret"},
                ),
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )

        assert exc_info.value.details.get("error_type") == "config_decryption_failed"
        assert "SECRET_ENCRYPTION_KEY" in exc_info.value.message
        result = await db_session.execute(select(Plugin))
        assert result.scalars().all() == []


class TestHooksStillMasked:
    """Non-régression (arbitrage n°1) : les hooks continuent de recevoir
    les passwords masqués *** même après le chiffrement au repos."""

    @pytest.mark.asyncio
    async def test_hooks_still_receive_masked_passwords(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        pkg_settings: Settings,
    ) -> None:
        """Le plan masqué hooks est conservé : le conteneur reçoit la
        valeur réelle (divergence n°4) mais les scripts hooks voient ***
        (stdout persisté en PluginHookLog)."""
        manifest_yaml = _password_manifest_yaml("svc-hooks") + (
            "hooks:\n" "  on_install: scripts/install.sh\n"
        )
        manager = _compose_manager(PluginManagerService(pkg_settings))
        _wire_source(manager, pkg_settings, "svc-hooks", manifest_yaml)
        # Vrai lifecycle (pas de mock) mais subprocess mocké.
        from app.services.plugin_lifecycle_service import PluginLifecycleService

        manager._lifecycle_service = PluginLifecycleService()

        with patch(
            "app.services.plugin_lifecycle_service.asyncio.create_subprocess_exec"
        ) as mock_exec:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"OK", b""))
            mock_exec.return_value = mock_proc

            await manager.install_plugin(
                db_session,
                install_data=PluginInstallRequest(
                    source="svc-hooks",
                    config_values={"api_key": "super-secret"},
                ),
                user_id=test_superuser.id,
                organization_id=test_organization.id,
            )

        env_passed = mock_exec.call_args.kwargs.get("env") or {}
        assert env_passed.get("PLUGIN_CONFIG_API_KEY") == "***"
