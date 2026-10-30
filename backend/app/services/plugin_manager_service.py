"""
Service métier pour la gestion du cycle de vie des plugins.

Orchestre le pipeline d'installation réel des plugins (spec 11) :
résolution source registre → download sécurisé/checksum/extraction
(STORY-169.1) → validation architecture/ressources/version WindFlow
(STORY-169.2) → hook ``on_install`` puis ``docker compose up -d`` du
service (service/hybrid) avec **rollback complet** DB + filesystem +
conteneur sur échec à chaque étage (STORY-169.3). Le chiffrement de
la configuration est porté par STORY-169.4.

Couvre également les opérations CRUD : update, uninstall, configure,
list, get — et émet des événements plugin via le système event-driven.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..config import settings as global_settings
from ..core.events import EventType
from ..core.exceptions import SecretDecryptionError, WindFlowException
from ..models.plugin import (
    _CONFIG_MASKS,
    Plugin,
    PluginStatus,
    encrypt_config_values_for_storage,
)
from ..models.plugin_hook_log import PluginHookLog
from ..schemas.plugin import (
    PluginConfigureRequest,
    PluginInstallRequest,
    PluginUpdateRequest,
)
from ..schemas.plugin_manifest import PluginManifest, PluginType
from ..schemas.plugin_registry import RegistryPluginEntry
from .docker_executor import ComposeExecutor
from .plugin_dependency_service import PluginDependencyService
from .plugin_lifecycle_service import PluginLifecycleService
from .plugin_manifest_service import PluginManifestService
from .plugin_package_service import PluginPackageService
from .plugin_registry_service import PluginRegistryService
from .plugin_validation_service import PluginValidationService

logger = logging.getLogger(__name__)

# STORY-169.3 : borne de troncature de la sortie ``docker compose``
# exposée dans les erreurs (rules 40 — pas de flood ; la sortie ne
# contient ni env vars ni secrets, ceux-ci n'étant jamais imprimés).
_COMPOSE_OUTPUT_MAX_LENGTH = 500
# Extrait de la sortie docker repris dans le message utilisateur.
_COMPOSE_EXCERPT_LENGTH = 200


class PluginManagerService:
    """Service de gestion du cycle de vie des plugins."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """
        Args:
            settings: Settings de l'application (défaut : singleton global) —
                rétrocompatible avec l'instanciation module-level du router.
        """
        self._settings = settings or global_settings
        self._manifest_service = PluginManifestService()
        self._dependency_service = PluginDependencyService()
        self._lifecycle_service = PluginLifecycleService()
        # STORY-169.1 : services du volet DOWNLOAD — résolution registre +
        # package (download sécurisé, checksum, extraction durcie).
        self._registry_service = PluginRegistryService(self._settings)
        self._package_service = PluginPackageService(self._settings)
        # STORY-169.2 : service du volet VALIDATE — architecture, ressources
        # et version WindFlow (mockable en tests, pattern _package_service).
        self._validation_service = PluginValidationService(self._settings)
        # STORY-169.3 : exécuteur compose du volet INSTALL — `up -d` du
        # service (service/hybrid) et `down` au rollback (mockable en
        # tests ; l'instanciation est sans effet de bord, les subprocess
        # ne sont créés qu'à l'appel).
        self._compose_executor = ComposeExecutor()

    # ── Lecture ─────────────────────────────────────────────────────────────

    @staticmethod
    async def list_plugins(
        db: AsyncSession,
        organization_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> List[Plugin]:
        """Liste les plugins d'une organisation, paginés (STORY-128).

        Tri stable ``ORDER BY name`` conservé.

        Args:
            db: Session de base de données.
            organization_id: ID de l'organisation.
            page: Page demandée (1-indexée, bornée par le Query endpoint).
            per_page: Taille de page (1-100, bornée par le Query endpoint).

        Returns:
            Liste des plugins de la page, triée par nom.
        """
        result = await db.execute(
            select(Plugin)
            .where(Plugin.organization_id == organization_id)
            .order_by(Plugin.name)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_plugins(db: AsyncSession, organization_id: str) -> int:
        """Compte les plugins d'une organisation (STORY-128).

        ``COUNT`` avec le **même scoping** que :meth:`list_plugins`
        (rules 40 — pas d'oracle de comptage).

        Args:
            db: Session de base de données.
            organization_id: ID de l'organisation.

        Returns:
            Nombre total de plugins de l'organisation.
        """
        result = await db.execute(
            select(func.count())
            .select_from(Plugin)
            .where(Plugin.organization_id == organization_id)
        )
        return int(result.scalar() or 0)

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

        Pipeline complet (spec 11, stories 169.1→169.3) : résolution
        source registre → download/checksum/extraction (169.1) →
        validation environnement (169.2) → doublon/dépendances →
        création du row (``installing``) → hook ``on_install`` →
        ``docker compose up -d`` pour service/hybrid → statut final →
        événements ``plugin.installed`` (bus + audit router).

        Arbitrages (analyse STORY-169.3) :

        - **Statuts (n°2)** : pas d'extension d'enum — le row naît
          ``installing`` puis passe directement au statut final
          ``running`` (service/hybrid, conteneur démarré) ou
          ``installed`` (extension — le démarrage d'une extension
          relève de STORY-170). Les statuts intermédiaires de la
          statechart (downloading/validating/starting) ne sont jamais
          persistés : le pipeline est synchrone.
        - **Unicité globale de ``plugins.name`` (n°5)** : contrainte
          ``unique=True`` existante sur un modèle multi-tenant — deux
          organisations ne peuvent pas installer le même plugin
          (comportement conservé, arbitré hors de cette story).
        - **Rollback (n°7)** : sur échec hook/compose, rollback complet
          (conteneur, filesystem branche source, DB + dépendances
          auto-installées + hook logs) puis erreur cause + suggestion.

        Args:
            db: Session de base de données.
            install_data: Données d'installation (source ou manifest_yaml).
            user_id: ID de l'utilisateur effectuant l'installation.
            organization_id: ID de l'organisation cible.

        Returns:
            Le plugin nouvellement installé.

        Raises:
            WindFlowException: Si le manifest est invalide, le plugin
                existe déjà, les dépendances sont insatisfaites, ou un
                étage du pipeline réel (hook, compose) échoue — dans ce
                dernier cas après rollback complet.
        """
        # Valider le manifest YAML si fourni directement, sinon résoudre
        # la source (registre) → download sécurisé → checksum → extraction
        # (STORY-169.1, volet DOWNLOAD). La branche source retourne aussi
        # le chemin extrait (purge en cas de rejet validation, STORY-169.2).
        if install_data.manifest_yaml:
            manifest = self._manifest_service.validate_manifest(
                install_data.manifest_yaml
            )
            extracted_path: Optional[Path] = None
        else:
            manifest, extracted_path = await self._install_from_source(
                install_data.source or ""
            )

        # STORY-169.2 : valider l'environnement local (architecture,
        # ressources, windflow_version) AVANT tout écriture en base.
        # Sur échec : purge du package extrait (rejet sans résidu
        # filesystem — branche source uniquement, la branche locale
        # n'extraie rien) puis remontée de l'erreur typée telle quelle.
        try:
            self._validation_service.validate_environment(manifest)
        except WindFlowException:
            if extracted_path is not None:
                shutil.rmtree(extracted_path, ignore_errors=True)
                logger.warning(
                    "plugin_validation_failed_purged",
                    extra={
                        "plugin_name": manifest.name,
                        "extracted_path": str(extracted_path),
                    },
                )
            raise

        # Vérifier l'absence de doublon (name unique)
        existing = await self.get_plugin_by_name(db, manifest.name)
        if existing:
            raise WindFlowException(
                f"Le plugin '{manifest.name}' est déjà installé",
                details={"error_type": "duplicate", "plugin_name": manifest.name},
            )

        # Vérifier les dépendances à l'installation
        dep_result = await self._dependency_service.check_install_dependencies(
            db, manifest, organization_id
        )

        # STORY-169.3 (divergence n°7) : journal des dépendances
        # réellement créées par CETTE installation — le bloc suivant
        # committe avant la création du plugin principal, le rollback
        # supprimera donc plugin principal + ces dépendances. Journal
        # volatile (temps de l'appel, aucune persistance — YAGNI).
        auto_installed: List[str] = []

        if not dep_result.can_proceed:
            # Tenter la résolution transitive des dépendances manquantes
            if dep_result.missing:
                try:
                    resolved = (
                        await self._dependency_service.resolve_transitive_dependencies(
                            db, manifest, organization_id
                        )
                    )
                    # Installer chaque dépendance résolue avant le plugin principal
                    for dep_manifest in resolved:
                        dep_existing = await self.get_plugin_by_name(
                            db, dep_manifest.name
                        )
                        if dep_existing:
                            continue
                        dep_plugin = Plugin(
                            name=dep_manifest.name,
                            version=dep_manifest.version,
                            display_name=dep_manifest.display_name,
                            description=dep_manifest.description,
                            category=dep_manifest.category.value,
                            type=dep_manifest.type.value,
                            status=PluginStatus.INSTALLED.value,
                            manifest_data=dep_manifest.model_dump(mode="json"),
                            config_values={},
                            organization_id=organization_id,
                            installed_by=user_id,
                        )
                        db.add(dep_plugin)
                        await db.flush()
                        auto_installed.append(dep_manifest.name)

                        logger.info(
                            "dependency_auto_installed",
                            extra={
                                "plugin_name": dep_manifest.name,
                                "required_by": manifest.name,
                                "user_id": user_id,
                                "organization_id": organization_id,
                            },
                        )
                    await db.commit()
                except WindFlowException:
                    logger.warning(
                        "dependency_check_failed",
                        extra={
                            "plugin_name": manifest.name,
                            "missing": [r.name for r in dep_result.missing],
                            "organization_id": organization_id,
                        },
                    )
                    raise WindFlowException(
                        f"Dépendances non satisfaites pour '{manifest.name}' : "
                        f"manquantes={', '.join(r.name for r in dep_result.missing)}, "
                        f"conflits={', '.join(dep_result.conflicts)}",
                        details={
                            "error_type": "dependency_unsatisfied",
                            "missing": [r.name for r in dep_result.missing],
                            "version_mismatches": [
                                m.model_dump() for m in dep_result.version_mismatches
                            ],
                            "conflicts": dep_result.conflicts,
                        },
                    )
            else:
                # Conflits ou version mismatches sans résolution possible
                logger.warning(
                    "dependency_check_failed",
                    extra={
                        "plugin_name": manifest.name,
                        "version_mismatches": len(dep_result.version_mismatches),
                        "conflicts": dep_result.conflicts,
                        "organization_id": organization_id,
                    },
                )
                raise WindFlowException(
                    f"Dépendances non satisfaites pour '{manifest.name}' : "
                    f"conflits={', '.join(dep_result.conflicts)}, "
                    f"versions incompatibles={len(dep_result.version_mismatches)}",
                    details={
                        "error_type": "dependency_unsatisfied",
                        "missing": [r.name for r in dep_result.missing],
                        "version_mismatches": [
                            m.model_dump() for m in dep_result.version_mismatches
                        ],
                        "conflicts": dep_result.conflicts,
                    },
                )

        logger.info(
            "dependency_check_passed",
            extra={
                "plugin_name": manifest.name,
                "organization_id": organization_id,
            },
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
            # STORY-169.4 : les valeurs password sont chiffrées AVANT
            # l'écriture en base (C12) — tokens Fernet en colonne JSON,
            # clés conservées lisibles (pattern models/deployment.py).
            config_values=encrypt_config_values_for_storage(
                manifest.model_dump(mode="json"), install_data.config_values
            ),
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

        # STORY-169.3 : pipeline INSTALL réel — hook on_install PUIS
        # ``docker compose up -d`` (statechart spec 11 : « Installing -->
        # Configuring : on_install exécuté » — le hook peut préparer
        # l'environnement dont le compose dépend). L'ordre DB-first est
        # imposé par le code existant : execute_lifecycle_transition
        # journalise un PluginHookLog avec FK plugin_id, le row doit
        # exister en base avant le hook (créé + commit ci-dessus).
        try:
            # 1. Hook on_install (no-op si non déclaré ; sur échec le
            #    lifecycle passe le plugin en error, émet plugin.error
            #    et lève hook_failed).
            plugin = await self._lifecycle_service.execute_lifecycle_transition(
                db, plugin, "install", user_id
            )

            # 2. Déploiement compose pour les plugins qui embarquent un
            #    service (service/hybrid). Arbitrage n°7 : fichier
            #    introuvable → rejet typé compose_file_missing (un
            #    plugin service sans conteneur = B5 non corrigé).
            if manifest.type in (PluginType.SERVICE, PluginType.HYBRID):
                compose_file = self._resolve_compose_file(manifest, extracted_path)
                await self._deploy_plugin_compose(plugin, compose_file)
        except WindFlowException as exc:
            residuals = await self._rollback_install(
                db,
                plugin=plugin,
                auto_installed=auto_installed,
                extracted_path=extracted_path,
                user_id=user_id,
            )
            raise self._installation_failed(exc, plugin, residuals) from exc

        # 3. Statut final (arbitrage n°2 — pas d'extension d'enum) :
        #    running pour service/hybrid (conteneur démarré), installed
        #    pour extension (le chargement relève de STORY-170).
        plugin.status = (
            PluginStatus.RUNNING.value
            if manifest.type in (PluginType.SERVICE, PluginType.HYBRID)
            else PluginStatus.INSTALLED.value
        )
        await db.commit()
        await db.refresh(plugin)

        # 4. Événements plugin.installed — contenu inchangé (bus +
        #    audit router), émis uniquement si hook ET compose ont réussi.
        self._emit_event(
            event_type=EventType.PLUGIN_INSTALLED,
            plugin_id=plugin.id,
            plugin_name=plugin.name,
            user_id=user_id,
            organization_id=organization_id,
            payload={"version": plugin.version},
        )
        # STORY-162 : publication réelle sur le bus canonique (best-effort
        # — ne doit jamais faire échouer l'installation).
        await self._publish_to_bus(
            EventType.PLUGIN_INSTALLED,
            plugin_name=plugin.name,
            version=plugin.version,
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
        # STORY-162 : publication réelle sur le bus canonique (extra-
        # canonique ``plugin.updated`` — best-effort).
        await self._publish_to_bus(
            EventType.PLUGIN_UPDATED,
            plugin_name=plugin.name,
            version=plugin.version,
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

        # Vérifier les dépendants avant suppression
        dependents = await self._dependency_service.check_uninstall_dependents(
            db, plugin_name, organization_id
        )
        if dependents:
            logger.warning(
                "dependency_check_failed",
                extra={
                    "plugin_name": plugin_name,
                    "dependents": dependents,
                    "organization_id": organization_id,
                },
            )
            raise WindFlowException(
                f"Impossible de désinstaller '{plugin_name}' : "
                f"les plugins suivants en dépendent : {', '.join(dependents)}",
                details={
                    "error_type": "has_dependents",
                    "dependents": dependents,
                },
            )

        logger.info(
            "dependency_check_passed",
            extra={
                "plugin_name": plugin_name,
                "organization_id": organization_id,
            },
        )

        # Exécuter le hook on_uninstall (si déclaré dans le manifest)
        # Si le hook échoue, le plugin passe en ERROR et une exception est levée
        # (le plugin n'est PAS supprimé)
        await self._lifecycle_service.execute_lifecycle_transition(
            db, plugin, "uninstall", user_id
        )

        await db.delete(plugin)
        await db.commit()

        # Émettre l'événement PLUGIN_REMOVED (uniquement si le hook a réussi)
        self._emit_event(
            event_type=EventType.PLUGIN_REMOVED,
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            user_id=user_id,
            organization_id=organization_id,
        )
        # STORY-162 : publication réelle sur le bus canonique
        # (``plugin.removed`` — best-effort).
        await self._publish_to_bus(EventType.PLUGIN_REMOVED, plugin_name=plugin_name)

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

        # STORY-169.4 : round-trip masque (arbitrage n°5) — une valeur
        # entrante égale au masque renvoyé par l'UI (``********`` réponse
        # ou ``***`` hooks) pour une clé DÉJÀ présente est ignorée : le
        # secret stocké est conservé, jamais écrasé par son propre masque.
        current_config = dict(plugin.config_values or {})
        incoming = {
            key: value
            for key, value in config_data.config_values.items()
            if not (
                key in current_config
                and isinstance(value, str)
                and value in _CONFIG_MASKS
            )
        }
        # Chiffrement à l'écriture (C12) : le helper idempotent est
        # appliqué au merge complet — les tokens existants sont conservés
        # byte-à-byte (pas de re-chiffrement), les valeurs password
        # nouvelles OU legacy en clair sont chiffrées (la double lecture
        # legacy se termine à l'occasion de cette écriture).
        plugin.config_values = encrypt_config_values_for_storage(
            plugin.manifest_data or {}, {**current_config, **incoming}
        )
        flag_modified(plugin, "config_values")

        await db.commit()
        await db.refresh(plugin)

        # Exécuter le hook on_configure (si déclaré dans le manifest)
        # Si le hook échoue, le plugin passe en ERROR et une exception est levée
        plugin = await self._lifecycle_service.execute_lifecycle_transition(
            db, plugin, "configure", user_id
        )

        # Émettre l'événement PLUGIN_CONFIGURED (uniquement si le hook a réussi)
        self._emit_event(
            event_type=EventType.PLUGIN_CONFIGURED,
            plugin_id=plugin.id,
            plugin_name=plugin.name,
            user_id=user_id,
            organization_id=plugin.organization_id,
        )
        # STORY-162 : publication réelle sur le bus canonique (extra-
        # canonique ``plugin.configured`` — best-effort).
        await self._publish_to_bus(EventType.PLUGIN_CONFIGURED, plugin_name=plugin.name)

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

    async def _resolve_registry_entry(self, source: str) -> RegistryPluginEntry:
        """Résout une source d'installation en entrée du registre officiel.

        Arbitrage n°1 de l'analyse STORY-169.1 : le checksum SHA-256 étant
        obligatoire et sourcé de ``RegistryPluginEntry.checksum_sha256``,
        seules les entrées du registre sont téléchargeables — une URL qui
        ne correspond à aucun ``download_url`` connu est rejetée, tout
        comme un identifiant inconnu (``plugin_not_in_registry``). Pas de
        download d'URL arbitraire sans checksum de registre.

        Args:
            source: URL HTTPS (match sur ``download_url``) ou identifiant
                nom du plugin dans le registre.

        Returns:
            L'entrée du registre correspondante (source de vérité du
            ``download_url`` et du ``checksum_sha256``).

        Raises:
            WindFlowException: ``plugin_not_in_registry`` si la source ne
                correspond à aucun plugin du registre.
        """
        if source.startswith("https://"):
            plugins = await self._registry_service.list_plugins()
            for plugin in plugins:
                if plugin.download_url == source:
                    return plugin
            raise WindFlowException(
                "Aucun plugin du registre ne correspond à l'URL fournie : "
                "impossible de vérifier son checksum SHA-256 — "
                "téléchargement refusé",
                details={"error_type": "plugin_not_in_registry"},
            )

        entry = await self._registry_service.get_plugin(source)
        if entry is None:
            raise WindFlowException(
                f"Plugin '{source}' introuvable dans le registre officiel",
                details={
                    "error_type": "plugin_not_in_registry",
                    "plugin_name": source,
                },
            )
        return entry

    async def _install_from_source(self, source: str) -> Tuple[PluginManifest, Path]:
        """Exécute le volet download : résolution registre → package.

        Pipeline STORY-169.1 : résolution de l'entrée du registre →
        ``PluginPackageService.download_and_extract`` (validation SSRF,
        streaming borné, checksum obligatoire, extraction durcie, install
        atomique) → validation du manifest extrait
        (``windflow-plugin.yml`` standard). En cas d'échec du manifest
        après extraction réussie, le répertoire extrait est purgé avant
        remontée de l'erreur (rejet sans résidu filesystem).

        Args:
            source: URL HTTPS ou identifiant nom (résolu registre).

        Returns:
            Le tuple ``(manifest validé, chemin extrait)`` — le chemin
            permet à l'appelant de purger le package si la validation
            d'environnement (STORY-169.2) rejette le plugin.

        Raises:
            WindFlowException: Celles de la résolution registre et du
                package service, plus ``manifest_invalid`` (extraction
                purgée avant remontée).
        """
        entry = await self._resolve_registry_entry(source)
        result = await self._package_service.download_and_extract(entry)

        try:
            manifest = self._manifest_service.validate_manifest_file(
                Path(result.extracted_path) / "windflow-plugin.yml"
            )
        except WindFlowException as exc:
            # Rejet sans résidu : purge du répertoire extrait avant de
            # remonter l'erreur manifest (périmètre download 169.1).
            shutil.rmtree(
                Path(self._settings.plugins_base_dir) / entry.name,
                ignore_errors=True,
            )
            logger.warning(
                "plugin_source_manifest_invalid_purged",
                extra={"plugin_name": entry.name, "error": exc.message},
            )
            raise WindFlowException(
                f"Manifest du package extrait invalide : {exc.message}",
                details={"error_type": "manifest_invalid"},
            ) from exc
        return manifest, Path(result.extracted_path)

    @staticmethod
    def _plugin_project_name(name: str) -> str:
        """Retourne le nom du projet Docker Compose d'un plugin.

        Convention spec 11 § marketplace / STORY-173 : le préfixe
        ``windflow-plugin-{name}`` garantit que le network créé par
        Compose (``{project}_default``) et le volume de données
        ``windflow-plugin-{name}-data`` matchent le pattern
        ``windflow-plugin-*`` épargné par le prune.

        Args:
            name: Nom du plugin (kebab-case).

        Returns:
            Le nom du projet Compose (``windflow-plugin-{name}``).
        """
        return f"windflow-plugin-{name}"

    def _resolve_compose_file(
        self, manifest: PluginManifest, extracted_path: Optional[Path]
    ) -> Path:
        """Résout et valide le chemin du fichier compose d'un plugin.

        Arbitrage n°6 de l'analyse STORY-169.3 (sécurité) : le champ
        ``compose_file`` du manifest n'est **pas** validé anti
        path-traversal par le schéma Pydantic (contrairement à
        ``name``) — ce contrôle est donc porté par le manager, sur le
        modèle de ``PluginLifecycleService._resolve_script_path`` :

        - rejet des chemins absolus et des segments ``..`` ;
        - résolution relative à la base du plugin : ``extracted_path``
          (branche source registre) sinon
          ``plugins_base_dir/{name}`` (branche manifest local) ;
        - containment vérifié par ``normpath``/``commonpath`` — le
          chemin résolu doit rester sous la base (défense en
          profondeur) ;
        - fichier inexistant → ``compose_file_missing`` avec cause et
          suggestion (jamais à moitié installé).

        Args:
            manifest: Le manifest validé du plugin (service/hybrid).
            extracted_path: Chemin extrait (branche source) ou None
                (branche manifest local).

        Returns:
            Le chemin absolu validé du fichier compose.

        Raises:
            WindFlowException: ``compose_file_invalid`` (chemin absolu,
                ``..`` ou hors base) ou ``compose_file_missing``
                (fichier introuvable sur disque).
        """
        compose_file = manifest.compose_file or ""

        if os.path.isabs(compose_file):
            raise WindFlowException(
                f"Chemin de fichier compose absolu interdit : {compose_file}. "
                "Suggestion : utiliser un chemin relatif au répertoire du "
                "plugin dans le manifest.",
                details={
                    "error_type": "compose_file_invalid",
                    "compose_file": compose_file,
                    "plugin_name": manifest.name,
                },
            )

        if ".." in compose_file.split(os.sep) or ".." in compose_file.split("/"):
            raise WindFlowException(
                f"Path traversal détecté dans le chemin du fichier compose : "
                f"{compose_file}. Suggestion : utiliser un chemin relatif "
                "au répertoire du plugin dans le manifest.",
                details={
                    "error_type": "compose_file_invalid",
                    "compose_file": compose_file,
                    "plugin_name": manifest.name,
                },
            )

        base_dir = (
            extracted_path
            if extracted_path is not None
            else Path(self._settings.plugins_base_dir) / manifest.name
        )
        base_abs = os.path.normpath(str(base_dir))
        resolved = os.path.normpath(os.path.join(base_abs, compose_file))

        # Défense en profondeur : le chemin résolu doit rester sous la
        # base du plugin (pattern _resolve_script_path).
        if os.path.commonpath([resolved, base_abs]) != base_abs:
            raise WindFlowException(
                f"Chemin du fichier compose en dehors du répertoire du "
                f"plugin : {compose_file}. Suggestion : utiliser un chemin "
                "relatif au répertoire du plugin dans le manifest.",
                details={
                    "error_type": "compose_file_invalid",
                    "compose_file": compose_file,
                    "plugin_name": manifest.name,
                },
            )

        compose_path = Path(resolved)
        if not compose_path.is_file():
            raise WindFlowException(
                f"Fichier compose '{compose_file}' introuvable pour le "
                f"plugin '{manifest.name}' (attendu sous {base_abs}). "
                "Suggestion : installer le plugin depuis une source "
                "registre (le package contient le fichier compose) ou "
                f"déposer le fichier sous {base_abs}/.",
                details={
                    "error_type": "compose_file_missing",
                    "compose_file": compose_file,
                    "plugin_name": manifest.name,
                    "expected_dir": base_abs,
                },
            )
        return compose_path

    async def _deploy_plugin_compose(self, plugin: Plugin, compose_file: Path) -> None:
        """Déploie le service du plugin via ``docker compose up -d``.

        Réutilise ``ComposeExecutor.deploy_compose`` (timeout 300 s
        interne) avec le projet conventionné
        ``windflow-plugin-{name}``. L'injection de configuration passe
        par ``PluginLifecycleService._build_injection_env_vars``
        (STORY-169.4, divergence n°4) : valeurs RÉELLES déchiffrées en
        mémoire — mêmes variables ``PLUGIN_CONFIG_*`` que les hooks,
        mais sans masquage ``***`` car le conteneur a besoin du vrai
        secret (spec 11 étape 4). Ces valeurs ne sont jamais loggées
        (deploy_compose n'imprime pas l'env, l'erreur ``compose_up_failed``
        ne contient que la sortie docker tronquée).

        Sécurité (rules 40) : la sortie docker est tronquée à 500
        caractères dans les ``details`` et l'extrait du message ne
        contient ni env vars ni secrets (jamais imprimés par compose).

        Args:
            plugin: Le plugin (row DB, statut installing).
            compose_file: Chemin validé du fichier compose.

        Raises:
            WindFlowException: ``config_decryption_failed`` si la
                configuration chiffrée est illisible (mauvaise clé
                maîtresse / donnée corrompue) — dans le pipeline install,
                le catch amont déclenche le rollback complet (arbitrage
                n°6) ; ``compose_up_failed`` avec extrait de la sortie
                docker + suggestion, après émission de ``plugin.error``
                (parité avec le lifecycle).
        """
        try:
            env_vars = PluginLifecycleService._build_injection_env_vars(plugin)
        except SecretDecryptionError as exc:
            # Arbitrage n°6 : erreur typée avant deploy_compose — le
            # catch WindFlowException du pipeline install déclenche le
            # rollback complet (jamais de plugin à moitié installé).
            raise WindFlowException(
                f"Échec du déchiffrement de la configuration du plugin "
                f"'{plugin.name}' : impossible d'injecter les secrets au "
                f"conteneur. Suggestion : vérifier SECRET_ENCRYPTION_KEY "
                f"(clé maîtresse) ou réinstaller le plugin.",
                details={
                    "error_type": "config_decryption_failed",
                    "plugin_name": plugin.name,
                },
            ) from exc
        project = self._plugin_project_name(plugin.name)

        success, output = await self._compose_executor.deploy_compose(
            compose_file, project, env_vars
        )

        if not success:
            # Parité avec le lifecycle : plugin.error émis AVANT la
            # levée (log structuré + bus canonique best-effort).
            self._emit_event(
                event_type=EventType.PLUGIN_ERROR,
                plugin_id=plugin.id,
                plugin_name=plugin.name,
                user_id=plugin.installed_by or "system",
                organization_id=plugin.organization_id,
                payload={"stage": "compose_up", "project": project},
            )
            await self._publish_to_bus(
                EventType.PLUGIN_ERROR,
                plugin_name=plugin.name,
                stage="compose_up",
            )
            logger.error(
                "plugin_compose_up_failed",
                extra={"plugin_name": plugin.name, "project": project},
            )
            excerpt = (output or "").strip()[:_COMPOSE_EXCERPT_LENGTH]
            raise WindFlowException(
                f"Échec du déploiement Docker Compose du plugin "
                f"'{plugin.name}' : {excerpt or 'sortie docker vide'}. "
                f"Suggestion : vérifier l'image et les ressources Docker, "
                f"puis consulter 'docker compose -p {project} logs'.",
                details={
                    "error_type": "compose_up_failed",
                    "plugin_name": plugin.name,
                    "compose_output": (output or "")[:_COMPOSE_OUTPUT_MAX_LENGTH],
                },
            )

        logger.info(
            "plugin_compose_up_succeeded",
            extra={"plugin_name": plugin.name, "project": project},
        )

    async def _rollback_install(
        self,
        db: AsyncSession,
        plugin: Plugin,
        auto_installed: List[str],
        extracted_path: Optional[Path],
        user_id: str,
    ) -> List[str]:
        """Annule une installation échouée — ordre inverse de l'install.

        Rollback complet (AC 2, spec 11 § rollback) : conteneur → hook
        ``on_uninstall`` best-effort → filesystem (branche source
        uniquement) → DB (hook logs, plugin, dépendances
        auto-installées). Chaque étape est best-effort : un échec
        n'interrompt jamais les suivantes, il est cumulé dans les
        résidus remontés à l'appelant (exposés dans
        ``details.rollback_residuals`` de l'erreur finale).

        Notes d'implémentation :

        - ``remove_compose`` est appelé **même sur échec hook** :
          Compose n'a pas encore tourné, l'appel est idempotent
          (défense en profondeur — AC 2 « docker compose down
          effectué ») ;
        - la purge explicite des ``PluginHookLog`` est obligatoire :
          la FK ``ondelete=CASCADE`` n'est pas appliquée par SQLite
          sans pragma ``foreign_keys=ON`` (arbitrage n°3) ;
        - la branche ``manifest_yaml`` locale ne purge jamais le
          filesystem (fichiers posés par l'utilisateur, pas par
          WindFlow — arbitrage n°7 de l'analyse 169.1).

        Args:
            db: Session de base de données.
            plugin: Le plugin dont l'installation a échoué.
            auto_installed: Journal des dépendances réellement créées
                par cette installation (divergence n°7).
            extracted_path: Chemin extrait (branche source) ou None.
            user_id: ID de l'utilisateur (hooks).

        Returns:
            La liste des résidus de rollback (``"compose"``,
            ``"database"``) — vide si le rollback est complet.
        """
        residuals: List[str] = []
        project = self._plugin_project_name(plugin.name)

        # 1. Conteneur — down + volumes (idempotent, appelé même si le
        #    compose n'a jamais tourné).
        try:
            ok, _ = await self._compose_executor.remove_compose(
                project, remove_volumes=True
            )
            if not ok:
                residuals.append("compose")
                logger.error(
                    "plugin_rollback_step_failed",
                    extra={
                        "step": "compose",
                        "plugin_name": plugin.name,
                        "error": "remove_compose a retourné un échec",
                    },
                )
        except Exception as exc:  # best-effort : jamais bloquant
            residuals.append("compose")
            logger.error(
                "plugin_rollback_step_failed",
                extra={
                    "step": "compose",
                    "plugin_name": plugin.name,
                    "error": str(exc),
                },
            )

        # 2. Hook on_uninstall best-effort — une installation partielle
        #    peut rendre le script inapte à tourner : jamais bloquant.
        try:
            await self._lifecycle_service.execute_lifecycle_transition(
                db, plugin, "uninstall", user_id
            )
        except Exception as exc:
            logger.warning(
                "plugin_rollback_uninstall_hook_failed",
                extra={"plugin_name": plugin.name, "error": str(exc)},
            )

        # 3. Filesystem — branche source uniquement (on ne supprime que
        #    ce que WindFlow a écrit).
        if extracted_path is not None:
            shutil.rmtree(extracted_path, ignore_errors=True)

        # 4. DB (ordre FK → rows) : purge explicite des hook logs
        #    (CASCADE inopérant sur SQLite sans pragma), suppression du
        #    plugin puis des dépendances auto-installées.
        try:
            await db.execute(
                delete(PluginHookLog).where(PluginHookLog.plugin_id == plugin.id)
            )
            await db.delete(plugin)
            for dep_name in auto_installed:
                dep = await self.get_plugin_by_name(db, dep_name)
                if dep is not None:
                    await db.execute(
                        delete(PluginHookLog).where(PluginHookLog.plugin_id == dep.id)
                    )
                    await db.delete(dep)
            await db.commit()
        except Exception as exc:  # best-effort : session cohérente
            residuals.append("database")
            await db.rollback()
            logger.error(
                "plugin_rollback_step_failed",
                extra={
                    "step": "database",
                    "plugin_name": plugin.name,
                    "error": str(exc),
                },
            )

        logger.warning(
            "plugin_install_rolled_back",
            extra={
                "plugin_name": plugin.name,
                "auto_installed": auto_installed,
                "residuals": residuals,
            },
        )
        return residuals

    def _installation_failed(
        self, exc: WindFlowException, plugin: Plugin, residuals: List[str]
    ) -> WindFlowException:
        """Construit l'erreur finale d'installation annulée (AC 2).

        Message explicite **cause + suggestion** (spec 11 § rollback :
        « l'utilisateur voit un message explicite avec la cause et la
        suggestion de résolution »), ``details`` de l'exception
        d'origine préservés et enrichis (``plugin_name``,
        ``rollback_performed``, ``rollback_residuals`` si rollback
        partiel). Le code principal (``error_type``) reste celui de
        l'étage ayant échoué.

        Args:
            exc: L'exception typée de l'étage échoué.
            plugin: Le plugin dont l'installation a été annulée.
            residuals: Résidus de rollback éventuels.

        Returns:
            La WindFlowException à remonter à l'appelant.
        """
        suggestions = {
            "hook_failed": (
                "corriger le script on_install ou contacter l'auteur du "
                "plugin — les détails de l'exécution sont dans les logs "
                "applicatifs"
            ),
            "compose_up_failed": (
                f"vérifier l'image et les ressources Docker, puis consulter "
                f"'docker compose -p {self._plugin_project_name(plugin.name)} "
                "logs'"
            ),
            "compose_file_missing": (
                "installer le plugin depuis une source registre (le package "
                "contient le fichier compose) ou déposer le fichier compose "
                f"sous plugins_base_dir/{plugin.name}/"
            ),
            "compose_file_invalid": (
                "corriger le champ compose_file du manifest (chemin relatif "
                "au répertoire du plugin, sans '..')"
            ),
        }
        error_type = str(exc.details.get("error_type") or "")
        suggestion = suggestions.get(
            error_type, "consulter les logs applicatifs pour le détail"
        )

        details = dict(exc.details)
        details["plugin_name"] = plugin.name
        details["rollback_performed"] = True
        if residuals:
            details["rollback_residuals"] = residuals

        return WindFlowException(
            f"Installation de '{plugin.name}' annulée — rollback effectué. "
            f"Cause : {exc.message}. Suggestion : {suggestion}",
            details=details,
        )

    @staticmethod
    async def _publish_to_bus(
        event_type: EventType,
        plugin_name: str,
        version: Optional[str] = None,
        **context: object,
    ) -> None:
        """Publie l'événement plugin sur le bus canonique (STORY-162).

        Best-effort strict : aucune exception ne remonte — un échec
        d'émission ne doit jamais faire échouer install/uninstall/
        configure (règle : l'émission n'altère pas l'opération métier).
        Payload minimal sans secret (nom/version + contexte technique
        borné, ex. ``stage`` pour les erreurs compose — STORY-169.3).
        """
        try:
            from ..core.events import get_event_bus

            payload: dict = {"plugin_name": plugin_name}
            if version is not None:
                payload["version"] = version
            if context:
                payload.update(context)
            await get_event_bus().emit(event_type, payload)
        except Exception:
            logger.warning(
                "plugin bus event emission failed (%s)",
                getattr(event_type, "value", event_type),
            )

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
