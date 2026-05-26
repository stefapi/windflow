"""
Tests unitaires du service PluginManagerService.

Couvre : install, update, uninstall, configure, list, get,
gestion d'erreurs, validation manifest, sécurité (password masking).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import WindFlowException
from app.models.organization import Organization
from app.models.plugin import Plugin, PluginStatus
from app.models.user import User
from app.schemas.plugin import PluginConfigureRequest, PluginInstallRequest, PluginUpdateRequest
from app.services.plugin_manager_service import PluginManagerService


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def service() -> PluginManagerService:
    """Instance du service PluginManager."""
    return PluginManagerService()


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

        # Vérifier que la valeur brute est bien stockée
        assert plugin.config_values.get("api_key") == "super-secret-key"

        # Vérifier via PluginResponse que le password est masqué
        from app.schemas.plugin import PluginResponse

        response = PluginResponse.model_validate(plugin)
        assert response.config_values["api_key"] == "********"
        assert response.config_values["host"] == "localhost"
