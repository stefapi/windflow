"""
Service métier pour la gestion du cycle de vie des plugins.

Orchestre les opérations CRUD sur les plugins installés :
install, update, uninstall, configure, list, get.
Valide le manifest via PluginManifestService avant installation.
Émet des événements plugin via le système event-driven.
"""

import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.events import EventType
from ..core.exceptions import WindFlowException
from ..models.plugin import Plugin, PluginStatus
from ..schemas.plugin import PluginConfigureRequest, PluginInstallRequest, PluginUpdateRequest
from .plugin_manifest_service import PluginManifestService

logger = logging.getLogger(__name__)


class PluginManagerService:
    """Service de gestion du cycle de vie des plugins."""

    def __init__(self) -> None:
        self._manifest_service = PluginManifestService()

    # ── Lecture ─────────────────────────────────────────────────────────────

    @staticmethod
    async def list_plugins(
        db: AsyncSession,
        organization_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Plugin]:
        """Liste les plugins d'une organisation.

        Args:
            db: Session de base de données.
            organization_id: ID de l'organisation.
            skip: Nombre de résultats à ignorer (pagination).
            limit: Nombre maximum de résultats.

        Returns:
            Liste des plugins de l'organisation.
        """
        result = await db.execute(
            select(Plugin)
            .where(Plugin.organization_id == organization_id)
            .order_by(Plugin.name)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_plugin(db: AsyncSession, plugin_id: str) -> Optional[Plugin]:
        """Récupère un plugin par son ID.

        Args:
            db: Session de base de données.
            plugin_id: ID du plugin.

        Returns:
            Le plugin ou None si non trouvé.
        """
        result = await db.execute(select(Plugin).where(Plugin.id == plugin_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_plugin_by_name(db: AsyncSession, name: str) -> Optional[Plugin]:
        """Récupère un plugin par son nom unique.

        Args:
            db: Session de base de données.
            name: Nom du plugin (kebab-case).

        Returns:
            Le plugin ou None si non trouvé.
        """
        result = await db.execute(select(Plugin).where(Plugin.name == name))
        return result.scalar_one_or_none()

    # ── Écriture ────────────────────────────────────────────────────────────

    async def install_plugin(
        self,
        db: AsyncSession,
        install_data: PluginInstallRequest,
        user_id: str,
        organization_id: str,
    ) -> Plugin:
        """Installe un nouveau plugin après validation du manifest.

        Args:
            db: Session de base de données.
            install_data: Données d'installation (source ou manifest_yaml).
            user_id: ID de l'utilisateur effectuant l'installation.
            organization_id: ID de l'organisation cible.

        Returns:
            Le plugin nouvellement installé.

        Raises:
            WindFlowException: Si le manifest est invalide ou le plugin existe déjà.
        """
        # Valider le manifest YAML si fourni directement
        if install_data.manifest_yaml:
            manifest = self._manifest_service.validate_manifest(install_data.manifest_yaml)
        else:
            # Pour le moment, source seule sans téléchargement — on lève une erreur
            raise WindFlowException(
                "L'installation depuis une source distante n'est pas encore supportée. "
                "Veuillez fournir le manifest YAML directement.",
                details={"error_type": "source_not_supported"},
            )

        # Vérifier l'absence de doublon (name unique)
        existing = await self.get_plugin_by_name(db, manifest.name)
        if existing:
            raise WindFlowException(
                f"Le plugin '{manifest.name}' est déjà installé",
                details={"error_type": "duplicate", "plugin_name": manifest.name},
            )

        # Créer le plugin en DB avec status INSTALLING
        plugin = Plugin(
            name=manifest.name,
            version=manifest.version,
            display_name=manifest.display_name,
            description=manifest.description,
            category=manifest.category.value,
            type=manifest.type.value,
            status=PluginStatus.INSTALLING.value,
            manifest_data=manifest.model_dump(mode="json"),
            config_values=install_data.config_values,
            organization_id=organization_id,
            installed_by=user_id,
        )
        db.add(plugin)
        await db.commit()
        await db.refresh(plugin)

        logger.info(
            "plugin_installing",
            extra={
                "plugin_name": plugin.name,
                "plugin_id": plugin.id,
                "version": plugin.version,
                "user_id": user_id,
                "organization_id": organization_id,
            },
        )

        # Passer en status INSTALLED (installation synchrone pour l'instant)
        plugin.status = PluginStatus.INSTALLED.value
        await db.commit()
        await db.refresh(plugin)

        # Émettre l'événement PLUGIN_INSTALLED
        self._emit_event(
            event_type=EventType.PLUGIN_INSTALLED,
            plugin_id=plugin.id,
            plugin_name=plugin.name,
            user_id=user_id,
            organization_id=organization_id,
            payload={"version": plugin.version},
        )

        logger.info(
            "plugin_installed",
            extra={
                "plugin_name": plugin.name,
                "plugin_id": plugin.id,
                "version": plugin.version,
                "user_id": user_id,
            },
        )

        return plugin

    async def update_plugin(
        self,
        db: AsyncSession,
        plugin_id: str,
        update_data: PluginUpdateRequest,
        user_id: str,
    ) -> Plugin:
        """Met à jour un plugin existant.

        Args:
            db: Session de base de données.
            plugin_id: ID du plugin à mettre à jour.
            update_data: Données de mise à jour.
            user_id: ID de l'utilisateur effectuant la mise à jour.

        Returns:
            Le plugin mis à jour.

        Raises:
            WindFlowException: Si le plugin n'existe pas.
        """
        plugin = await self.get_plugin(db, plugin_id)
        if not plugin:
            raise WindFlowException(
                f"Plugin non trouvé : {plugin_id}",
                details={"error_type": "not_found", "plugin_id": plugin_id},
            )

        # Passer en status UPDATING
        plugin.status = PluginStatus.UPDATING.value
        await db.commit()
        await db.refresh(plugin)

        logger.info(
            "plugin_updating",
            extra={
                "plugin_name": plugin.name,
                "plugin_id": plugin.id,
                "user_id": user_id,
            },
        )

        # Mettre à jour la version si fournie
        if update_data.version:
            plugin.version = update_data.version

        # Re-valider le manifest si un nouveau manifest_yaml est fourni
        # (pour l'instant, on met juste à jour la version)
        plugin.status = PluginStatus.INSTALLED.value
        await db.commit()
        await db.refresh(plugin)

        # Émettre l'événement PLUGIN_UPDATED
        self._emit_event(
            event_type=EventType.PLUGIN_UPDATED,
            plugin_id=plugin.id,
            plugin_name=plugin.name,
            user_id=user_id,
            organization_id=plugin.organization_id,
            payload={"version": plugin.version},
        )

        logger.info(
            "plugin_updated",
            extra={
                "plugin_name": plugin.name,
                "plugin_id": plugin.id,
                "version": plugin.version,
                "user_id": user_id,
            },
        )

        return plugin

    async def uninstall_plugin(
        self,
        db: AsyncSession,
        plugin_id: str,
        user_id: str,
    ) -> None:
        """Désinstalle un plugin en le supprimant de la base.

        Args:
            db: Session de base de données.
            plugin_id: ID du plugin à désinstaller.
            user_id: ID de l'utilisateur effectuant la désinstallation.

        Raises:
            WindFlowException: Si le plugin n'existe pas.
        """
        plugin = await self.get_plugin(db, plugin_id)
        if not plugin:
            raise WindFlowException(
                f"Plugin non trouvé : {plugin_id}",
                details={"error_type": "not_found", "plugin_id": plugin_id},
            )

        plugin_name = plugin.name
        organization_id = plugin.organization_id

        await db.delete(plugin)
        await db.commit()

        # Émettre l'événement PLUGIN_UNINSTALLED
        self._emit_event(
            event_type=EventType.PLUGIN_UNINSTALLED,
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            user_id=user_id,
            organization_id=organization_id,
        )

        logger.info(
            "plugin_uninstalled",
            extra={
                "plugin_name": plugin_name,
                "plugin_id": plugin_id,
                "user_id": user_id,
            },
        )

    async def configure_plugin(
        self,
        db: AsyncSession,
        plugin_id: str,
        config_data: PluginConfigureRequest,
        user_id: str,
    ) -> Plugin:
        """Met à jour la configuration d'un plugin.

        Args:
            db: Session de base de données.
            plugin_id: ID du plugin à configurer.
            config_data: Nouvelles valeurs de configuration.
            user_id: ID de l'utilisateur effectuant la configuration.

        Returns:
            Le plugin avec la configuration mise à jour.

        Raises:
            WindFlowException: Si le plugin n'existe pas.
        """
        plugin = await self.get_plugin(db, plugin_id)
        if not plugin:
            raise WindFlowException(
                f"Plugin non trouvé : {plugin_id}",
                details={"error_type": "not_found", "plugin_id": plugin_id},
            )

        # Fusionner les config existantes avec les nouvelles valeurs
        from sqlalchemy.orm.attributes import flag_modified

        current_config = dict(plugin.config_values or {})
        current_config.update(config_data.config_values)
        plugin.config_values = current_config
        flag_modified(plugin, "config_values")

        await db.commit()
        await db.refresh(plugin)

        # Émettre l'événement PLUGIN_CONFIGURED
        self._emit_event(
            event_type=EventType.PLUGIN_CONFIGURED,
            plugin_id=plugin.id,
            plugin_name=plugin.name,
            user_id=user_id,
            organization_id=plugin.organization_id,
        )

        logger.info(
            "plugin_configured",
            extra={
                "plugin_name": plugin.name,
                "plugin_id": plugin.id,
                "user_id": user_id,
            },
        )

        return plugin

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _emit_event(
        event_type: EventType,
        plugin_id: str,
        plugin_name: str,
        user_id: str,
        organization_id: str,
        payload: Optional[dict] = None,
    ) -> None:
        """Émet un événement plugin via le logger structuré.

        Note: L'intégration avec l'EventBus sera faite dans STORY-006 (Hooks lifecycle).
        Pour l'instant, on logge l'événement de manière structurée.
        """
        logger.info(
            event_type.value,
            extra={
                "plugin_id": plugin_id,
                "plugin_name": plugin_name,
                "user_id": user_id,
                "organization_id": organization_id,
                **(payload or {}),
            },
        )
