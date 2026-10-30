"""
Service métier pour l'exécution des hooks lifecycle des plugins.

Exécute les scripts shell déclarés dans le manifest (on_install, on_configure,
on_start, on_stop, on_uninstall) avec gestion d'erreurs, timeout, logging
et sécurité (anti path traversal, masquage des secrets).
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.events import EventType
from ..core.exceptions import WindFlowException
from ..models.plugin import (
    Plugin,
    PluginStatus,
    decrypt_config_values_from_storage,
)
from ..models.plugin_hook_log import PluginHookLog
from ..schemas.plugin_hook_log import HookExecutionResult

logger = logging.getLogger(__name__)

# Limite de troncature pour stdout/stderr
_OUTPUT_MAX_LENGTH = 10_000

# Mapping transition → hook_name
_TRANSITION_HOOK_MAP: Dict[str, str] = {
    "install": "on_install",
    "configure": "on_configure",
    "uninstall": "on_uninstall",
    "start": "on_start",
    "stop": "on_stop",
}


class PluginLifecycleService:
    """Service d'exécution des hooks lifecycle des plugins.

    Exécute les scripts shell déclarés dans le manifest des plugins
    lors des transitions d'état (install, configure, uninstall, start, stop).
    """

    HOOK_TIMEOUT_SECONDS: int = 30

    # ── Exécution des hooks ─────────────────────────────────────────────────

    async def execute_hook(
        self,
        db: AsyncSession,
        plugin: Plugin,
        hook_name: str,
        user_id: str,
    ) -> HookExecutionResult:
        """Exécute un hook lifecycle pour un plugin.

        Résout le chemin du script, l'exécute via subprocess, capture
        les sorties et enregistre le résultat en base.

        Args:
            db: Session de base de données.
            plugin: Le plugin concerné.
            hook_name: Nom du hook (on_install, on_configure, etc.).
            user_id: ID de l'utilisateur déclenchant le hook.

        Returns:
            HookExecutionResult avec le résultat de l'exécution.

        Raises:
            WindFlowException: Si le chemin du script est invalide (path traversal).
        """
        # Récupérer le chemin du script depuis le manifest
        manifest_data = plugin.manifest_data or {}
        hooks_data = manifest_data.get("hooks") or {}
        script_path = hooks_data.get(hook_name)

        if not script_path:
            # Pas de hook déclaré → no-op
            logger.debug(
                "hook_not_declared",
                extra={
                    "plugin_name": plugin.name,
                    "hook_name": hook_name,
                },
            )
            return HookExecutionResult(success=True)

        # Résoudre et valider le chemin du script
        script_abs_path = self._resolve_script_path(plugin.name, script_path)

        # Créer l'entrée de log
        hook_log = PluginHookLog(
            plugin_id=plugin.id,
            hook_name=hook_name,
            script_path=script_path,
            status="running",
            started_at=datetime.now(timezone.utc),
            triggered_by=user_id,
        )
        db.add(hook_log)
        await db.flush()

        # Construire les variables d'environnement sécurisées
        env_vars = self._build_safe_env_vars(plugin)

        # Exécuter le script
        started_at = datetime.now(timezone.utc)
        result = await self._run_subprocess(script_abs_path, env_vars)
        completed_at = datetime.now(timezone.utc)

        # Calculer la durée
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        # Mettre à jour le log
        hook_log.status = "success" if result.success else "failed"
        hook_log.exit_code = result.exit_code
        hook_log.stdout = result.stdout[:_OUTPUT_MAX_LENGTH]
        hook_log.stderr = result.stderr[:_OUTPUT_MAX_LENGTH]
        hook_log.completed_at = completed_at
        hook_log.duration_ms = duration_ms
        hook_log.error_message = result.error_message

        await db.flush()

        logger.info(
            "hook_executed",
            extra={
                "plugin_name": plugin.name,
                "hook_name": hook_name,
                "status": hook_log.status,
                "exit_code": result.exit_code,
                "duration_ms": duration_ms,
                "user_id": user_id,
            },
        )

        # Mettre à jour le résultat avec la durée
        result.duration_ms = duration_ms
        return result

    async def execute_lifecycle_transition(
        self,
        db: AsyncSession,
        plugin: Plugin,
        transition: str,
        user_id: str,
    ) -> Plugin:
        """Exécute une transition lifecycle complète avec hook.

        Mappe la transition vers le hook correspondant, exécute le hook,
        et gère le statut du plugin en cas de succès ou d'échec.

        Args:
            db: Session de base de données.
            plugin: Le plugin concerné.
            transition: Nom de la transition (install, configure, uninstall, start, stop).
            user_id: ID de l'utilisateur déclenchant la transition.

        Returns:
            Le plugin mis à jour.

        Raises:
            WindFlowException: Si le hook échoue (plugin passé en ERROR).
        """
        hook_name = _TRANSITION_HOOK_MAP.get(transition)
        if not hook_name:
            raise WindFlowException(
                f"Transition lifecycle inconnue : {transition}",
                details={"error_type": "invalid_transition", "transition": transition},
            )

        # Vérifier si le hook est déclaré dans le manifest
        manifest_data = plugin.manifest_data or {}
        hooks_data = manifest_data.get("hooks") or {}
        script_path = hooks_data.get(hook_name)

        if not script_path:
            # Pas de hook déclaré → no-op, retourner le plugin sans erreur
            logger.debug(
                "lifecycle_transition_noop",
                extra={
                    "plugin_name": plugin.name,
                    "transition": transition,
                    "hook_name": hook_name,
                },
            )
            return plugin

        # Exécuter le hook
        result = await self.execute_hook(db, plugin, hook_name, user_id)

        if not result.success:
            # Le hook a échoué → passer le plugin en ERROR
            plugin.status = PluginStatus.ERROR.value
            await db.flush()

            # Émettre l'événement PLUGIN_ERROR
            self._emit_event(
                event_type=EventType.PLUGIN_ERROR,
                plugin_id=plugin.id,
                plugin_name=plugin.name,
                user_id=user_id,
                organization_id=plugin.organization_id,
                payload={
                    "hook_name": hook_name,
                    "transition": transition,
                    "exit_code": result.exit_code,
                    "error_message": result.error_message,
                },
            )
            # STORY-162 : publication réelle sur le bus canonique (extra-
            # canonique ``plugin.error`` — best-effort, jamais bloquant).
            await self._publish_to_bus(
                EventType.PLUGIN_ERROR,
                plugin_name=plugin.name,
                hook_name=hook_name,
                transition=transition,
                exit_code=result.exit_code,
            )

            logger.error(
                "hook_failed_plugin_error",
                extra={
                    "plugin_name": plugin.name,
                    "hook_name": hook_name,
                    "exit_code": result.exit_code,
                    "error_message": result.error_message,
                },
            )

            raise WindFlowException(
                f"Le hook '{hook_name}' a échoué pour le plugin '{plugin.name}' : "
                f"{result.error_message or 'exit code ' + str(result.exit_code)}",
                details={
                    "error_type": "hook_failed",
                    "hook_name": hook_name,
                    "transition": transition,
                    "exit_code": result.exit_code,
                    "stderr": result.stderr[:500] if result.stderr else None,
                },
            )

        return plugin

    async def execute_on_start(
        self,
        db: AsyncSession,
        plugin: Plugin,
        user_id: str,
    ) -> Plugin:
        """Exécute le hook on_start pour un plugin.

        Méthode exposée mais non câblée dans PluginManagerService
        (pas d'opérations start/stop existantes).

        Args:
            db: Session de base de données.
            plugin: Le plugin à démarrer.
            user_id: ID de l'utilisateur.

        Returns:
            Le plugin mis à jour.
        """
        return await self.execute_lifecycle_transition(db, plugin, "start", user_id)

    async def execute_on_stop(
        self,
        db: AsyncSession,
        plugin: Plugin,
        user_id: str,
    ) -> Plugin:
        """Exécute le hook on_stop pour un plugin.

        Méthode exposée mais non câblée dans PluginManagerService
        (pas d'opérations start/stop existantes).

        Args:
            db: Session de base de données.
            plugin: Le plugin à arrêter.
            user_id: ID de l'utilisateur.

        Returns:
            Le plugin mis à jour.
        """
        return await self.execute_lifecycle_transition(db, plugin, "stop", user_id)

    # ── Lecture des logs ─────────────────────────────────────────────────────

    @staticmethod
    async def list_hook_logs(
        db: AsyncSession,
        plugin_id: str,
        page: int = 1,
        per_page: int = 20,
    ) -> List[PluginHookLog]:
        """Liste les logs d'exécution des hooks pour un plugin, paginés
        (STORY-128).

        Tri ``started_at desc`` conservé (logs les plus récents d'abord).

        Args:
            db: Session de base de données.
            plugin_id: ID du plugin.
            page: Page demandée (1-indexée, bornée par le Query endpoint).
            per_page: Taille de page (1-100, bornée par le Query endpoint).

        Returns:
            Liste des logs de hooks de la page.
        """
        result = await db.execute(
            select(PluginHookLog)
            .where(PluginHookLog.plugin_id == plugin_id)
            .order_by(PluginHookLog.started_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_hook_logs(db: AsyncSession, plugin_id: str) -> int:
        """Compte les logs d'exécution des hooks d'un plugin (STORY-128).

        ``COUNT`` avec le **même scoping** que :meth:`list_hook_logs`
        (rules 40 — pas d'oracle de comptage).

        Args:
            db: Session de base de données.
            plugin_id: ID du plugin.

        Returns:
            Nombre total de logs de hooks du plugin.
        """
        result = await db.execute(
            select(func.count())
            .select_from(PluginHookLog)
            .where(PluginHookLog.plugin_id == plugin_id)
        )
        return int(result.scalar() or 0)

    @staticmethod
    async def get_hook_log(
        db: AsyncSession,
        log_id: str,
    ) -> Optional[PluginHookLog]:
        """Récupère un log de hook par son ID.

        Args:
            db: Session de base de données.
            log_id: ID du log.

        Returns:
            Le log ou None si non trouvé.
        """
        result = await db.execute(
            select(PluginHookLog).where(PluginHookLog.id == log_id)
        )
        return result.scalar_one_or_none()

    # ── Helpers internes ─────────────────────────────────────────────────────

    async def _run_subprocess(
        self,
        script_path: str,
        env_vars: Dict[str, str],
    ) -> HookExecutionResult:
        """Exécute un script via subprocess avec timeout.

        Args:
            script_path: Chemin absolu du script à exécuter.
            env_vars: Variables d'environnement pour le script.

        Returns:
            HookExecutionResult avec les sorties capturées.
        """
        try:
            # Fusionner les env vars du processus actuel avec les vars du plugin
            process_env = dict(os.environ)
            process_env.update(env_vars)

            process = await asyncio.create_subprocess_exec(
                script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=self.HOOK_TIMEOUT_SECONDS,
            )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            exit_code = process.returncode
            success = exit_code == 0

            return HookExecutionResult(
                success=success,
                exit_code=exit_code,
                stdout=stdout[:_OUTPUT_MAX_LENGTH],
                stderr=stderr[:_OUTPUT_MAX_LENGTH],
                error_message=(
                    None if success else (stderr[:500] or f"Exit code: {exit_code}")
                ),
            )

        except asyncio.TimeoutError:
            # Tuer le processus si encore en cours
            try:
                process.kill()
            except ProcessLookupError:
                pass

            return HookExecutionResult(
                success=False,
                exit_code=None,
                stdout="",
                stderr="",
                error_message=f"Hook timeout after {self.HOOK_TIMEOUT_SECONDS}s",
            )

        except FileNotFoundError:
            return HookExecutionResult(
                success=False,
                exit_code=127,
                stdout="",
                stderr=f"Script not found: {script_path}",
                error_message=f"Script not found: {script_path}",
            )

        except Exception as exc:
            return HookExecutionResult(
                success=False,
                exit_code=None,
                stdout="",
                stderr=str(exc),
                error_message=f"Unexpected error: {exc}",
            )

    @staticmethod
    def _resolve_script_path(plugin_name: str, script_path: str) -> str:
        """Résout et valide le chemin d'un script hook.

        Le chemin est résolu relativement au répertoire de base des plugins
        (settings.plugins_base_dir / plugin_name / script_path).

        Sécurité :
        - Rejette les chemins contenant '..' (anti path traversal)
        - Rejette les chemins absolus

        Args:
            plugin_name: Nom du plugin (kebab-case).
            script_path: Chemin relatif du script déclaré dans le manifest.

        Returns:
            Chemin absolu résolu.

        Raises:
            WindFlowException: Si le chemin est invalide (path traversal ou absolu).
        """
        # Vérifier les chemins absolus
        if os.path.isabs(script_path):
            raise WindFlowException(
                f"Chemin de script absolu interdit : {script_path}",
                details={
                    "error_type": "invalid_script_path",
                    "script_path": script_path,
                },
            )

        # Vérifier le path traversal (..)
        if ".." in script_path.split(os.sep) or ".." in script_path.split("/"):
            raise WindFlowException(
                f"Path traversal détecté dans le chemin du script : {script_path}",
                details={"error_type": "path_traversal", "script_path": script_path},
            )

        # Construire le chemin absolu
        base_dir = settings.plugins_base_dir.rstrip("/")
        full_path = os.path.normpath(os.path.join(base_dir, plugin_name, script_path))

        # Vérification supplémentaire : le chemin résolu doit être sous le base_dir
        resolved_base = os.path.normpath(base_dir)
        if (
            not full_path.startswith(resolved_base + os.sep)
            and full_path != resolved_base
        ):
            raise WindFlowException(
                f"Chemin de script en dehors du répertoire de base : {script_path}",
                details={"error_type": "path_traversal", "script_path": script_path},
            )

        return full_path

    @staticmethod
    def _build_safe_env_vars(plugin: Plugin) -> Dict[str, str]:
        """Construit les variables d'environnement sécurisées pour un script hook.

        Les config_values de type 'password' sont masquées avec '***'.
        Les autres config_values sont exposées avec le préfixe 'PLUGIN_CONFIG_'.

        Args:
            plugin: Le plugin concerné.

        Returns:
            Dictionnaire des variables d'environnement.
        """
        env_vars: Dict[str, str] = {}

        # Informations de base du plugin
        env_vars["PLUGIN_NAME"] = plugin.name
        env_vars["PLUGIN_VERSION"] = plugin.version
        env_vars["PLUGIN_ID"] = plugin.id

        # Récupérer les types de config depuis le manifest
        manifest_data = plugin.manifest_data or {}
        config_fields = manifest_data.get("config", [])

        # Identifier les clés de type password
        password_keys: set = set()
        for field_def in config_fields:
            if isinstance(field_def, dict) and field_def.get("type") == "password":
                key = field_def.get("key")
                if key:
                    password_keys.add(key)

        # Exposer les config_values avec masquage des passwords
        config_values = plugin.config_values or {}
        for key, value in config_values.items():
            env_key = f"PLUGIN_CONFIG_{key.upper()}"
            if key in password_keys:
                env_vars[env_key] = "***"
            else:
                env_vars[env_key] = str(value)

        return env_vars

    @staticmethod
    def _build_injection_env_vars(plugin: Plugin) -> Dict[str, str]:
        """Construit les variables d'environnement d'injection au compose.

        STORY-169.4 (divergence n°4) : contrairement à
        ``_build_safe_env_vars`` (hooks — passwords masqués ``***`` car
        les sorties des scripts sont persistées dans
        ``PluginHookLog.stdout/stderr``), ce plan d'injection fournit les
        valeurs RÉELLES déchiffrées en mémoire au conteneur
        (``docker compose up``, spec 11 étape 4 « injecter la
        configuration dans le container »). Les tokens Fernet de
        ``config_values`` sont déchiffrés ici ; les valeurs legacy en
        clair sont relues telles quelles (double lecture).

        Sécurité (rules 40) : les valeurs déchiffrées vivent en mémoire
        uniquement — ne JAMAIS les logger ni les écrire (deploy_compose
        n'imprime pas l'env, l'erreur compose n'embarque que la sortie
        docker tronquée).

        Args:
            plugin: Le plugin concerné (config_values possiblement
                chiffrée).

        Returns:
            Dictionnaire des variables d'environnement avec valeurs
            réelles (non masquées).

        Raises:
            SecretDecryptionError: Si un ciphertext de configuration est
                illisible (mauvaise clé maîtresse ou donnée corrompue) —
                remontée au manager qui la convertit en erreur typée
                ``config_decryption_failed`` avant rollback.
        """
        env_vars: Dict[str, str] = {
            "PLUGIN_NAME": plugin.name,
            "PLUGIN_VERSION": plugin.version,
            "PLUGIN_ID": plugin.id,
        }

        decrypted = decrypt_config_values_from_storage(plugin.config_values or {})
        for key, value in decrypted.items():
            env_vars[f"PLUGIN_CONFIG_{key.upper()}"] = str(value)

        return env_vars

    @staticmethod
    async def _publish_to_bus(
        event_type: EventType,
        plugin_name: str,
        **context: object,
    ) -> None:
        """Publie l'événement plugin sur le bus canonique (STORY-162).

        Best-effort strict : aucune exception ne remonte — l'émission ne
        doit jamais altérer la transition lifecycle. Payload minimal sans
        secret (nom + contexte technique borné).
        """
        try:
            from ..core.events import get_event_bus

            await get_event_bus().emit(
                event_type, {"plugin_name": plugin_name, **context}
            )
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
        """Émet un événement plugin via le logger structuré (log conservé ;
        la publication bus est assurée par ``_publish_to_bus``).

        Args:
            event_type: Type d'événement.
            plugin_id: ID du plugin.
            plugin_name: Nom du plugin.
            user_id: ID de l'utilisateur.
            organization_id: ID de l'organisation.
            payload: Données supplémentaires.
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
