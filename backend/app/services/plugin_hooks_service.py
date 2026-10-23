"""Pont bus d'événements → hooks ``@on_event`` des plugins (STORY-163 — T2).

Composant d'abonnement qui dispatche les événements **canoniques** du bus
([`app.core.events`](../core/events.py), STORY-162) vers les instances
``PluginHooks`` enregistrées (SDK [`app.plugins.hooks`](../plugins/hooks.py),
T1).

Garanties (AC 1 — isolation d'exécution) :

- chaque hook est exécuté dans une **tâche asyncio dédiée** : le
  ``publish``/``emit`` de l'émetteur revient immédiatement, un hook lent
  ne retarde ni l'émetteur ni les abonnés suivants (le dispatch in-memory
  du bus est séquentiel — le pont est le point d'isolation) ;
- **timeout par hook** (``asyncio.wait_for`` +
  ``plugin_hooks_timeout_seconds``, défaut 30 s aligné sur
  ``HOOK_TIMEOUT_SECONDS`` des hooks lifecycle) : un hook qui dépasse est
  annulé et journalisé WARNING — jamais propagé ;
- **erreur de hook** journalisée ERROR avec nom du plugin et événement —
  jamais propagée à l'émetteur ni aux autres hooks ;
- **pool borné** (sémaphore) : un événement très fréquent ne peut pas
  spawner des dizaines de tâches orphelines (anti-DoS, rules 40) ; la
  borne vaut ``max_concurrent_hooks`` (défaut 16) — les hooks au-delà de
  la borne attendent leur tour dans leur tâche dédiée, l'émetteur n'est
  jamais bloqué ;
- les tâches gardent une **référence forte** (set + done-callback, pattern
  cleanup ``deployment_orchestrator``) pour éviter la GC prématurée par
  asyncio.

Réduction de surface (rules 40) : le pont s'abonne **uniquement aux 18
événements canoniques** (itération de ``CANONICAL_EVENT_NAMES``). Les
extra-canoniques — dont les événements de sécurité TOFU
``host.ssh_fingerprint_*`` — ne sont **jamais** transmis aux plugins
(décision d'analyse n°1).

Cycle de vie : ``start()``/``stop()`` idempotents sur le modèle de
[`scheduler_event_triggers`](scheduler_event_triggers.py) — utilisé au
lifespan (T6) et ré-abonnable après un ``reset_event_bus()`` de test.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Set

from ..config import settings
from ..core.events import CANONICAL_EVENT_NAMES, Event, EventType, get_event_bus
from ..plugins.hooks import PluginEvent, PluginHooks

logger = logging.getLogger(__name__)

#: Membres canoniques (résolus une fois — frozenset des valeurs).
_CANONICAL_TYPES: List[EventType] = [
    EventType(member) for member in sorted(CANONICAL_EVENT_NAMES)
]


class PluginHooksService:
    """Pont bus canonique → hooks ``@on_event`` des plugins enregistrés.

    Args:
        bus: Bus d'événements (défaut : singleton global
            ``get_event_bus()`` — même instance que les émetteurs et que
            les autres consommateurs). Injecté par les tests.
        timeout_seconds: Timeout d'exécution par hook (défaut :
            ``settings.plugin_hooks_timeout_seconds``).
        max_concurrent_hooks: Borne du pool d'exécution des hooks
            (défaut 16) — au-delà, les tâches attendent la libération
            d'un slot (jamais d'échec, jamais de blocage émetteur).
    """

    def __init__(
        self,
        bus: Any = None,
        *,
        timeout_seconds: Optional[float] = None,
        max_concurrent_hooks: int = 16,
    ) -> None:
        self._bus = bus if bus is not None else get_event_bus()
        self._timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.plugin_hooks_timeout_seconds
        )
        self._semaphore = asyncio.Semaphore(max_concurrent_hooks)
        self._instances: Dict[type, PluginHooks] = {}
        self._subscribed = False
        # Références fortes sur les tâches actives (anti-GC asyncio).
        self._tasks: Set[asyncio.Task[None]] = set()

    # ------------------------------------------------------------------
    # Registre des instances de hooks
    # ------------------------------------------------------------------

    def register(self, hooks_instance: PluginHooks) -> None:
        """Enregistre une instance de hooks (idempotent par classe).

        Une même classe enregistrée deux fois (ex. deux chargements du
        même module) n'active les hooks qu'une fois — la première
        instance l'emporte, un warning trace la tentative.

        Args:
            hooks_instance: Instance ``PluginHooks`` (SDK T1) à brancher.
        """
        klass = type(hooks_instance)
        if klass in self._instances:
            logger.warning(
                "Plugin hooks : %s déjà enregistré (classe %s) — ignore",
                getattr(hooks_instance, "plugin_name", klass.__name__),
                klass.__name__,
            )
            return
        self._instances[klass] = hooks_instance
        count = sum(len(v) for v in hooks_instance.hooks.values())
        logger.info(
            "Plugin hooks enregistrés : %s (%d hook(s) sur %d événement(s))",
            hooks_instance.plugin_name,
            count,
            len(hooks_instance.hooks),
        )

    def unregister(self, hooks_instance: PluginHooks) -> None:
        """Retire une instance du registre (shutdown d'un plugin)."""
        self._instances.pop(type(hooks_instance), None)

    @property
    def registered_count(self) -> int:
        """Nombre d'instances actuellement enregistrées."""
        return len(self._instances)

    # ------------------------------------------------------------------
    # Cycle de vie (lifespan) — idempotent, modèle scheduler_event_triggers
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Abonne la callback aux **18 événements canoniques** (idempotent)."""
        if self._subscribed:
            return
        for event_type in _CANONICAL_TYPES:
            self._bus.subscribe(event_type, self._on_event)
        self._subscribed = True
        logger.info(
            "Plugin hooks service : abonné à %d événement(s) canonique(s)",
            len(_CANONICAL_TYPES),
        )

    def stop(self) -> None:
        """Désabonne la callback (shutdown propre avec le bus)."""
        if not self._subscribed:
            return
        for event_type in _CANONICAL_TYPES:
            try:
                self._bus.unsubscribe(event_type, self._on_event)
            except ValueError:  # déjà désabonné — défense
                pass
        self._subscribed = False
        logger.info("Plugin hooks service : désabonné du bus")

    def reset(self) -> None:
        """Purge complète pour les tests : désabonnement + registre vide."""
        self.stop()
        self._instances.clear()

    # ------------------------------------------------------------------
    # Callback du bus — dispatch en tâches isolées, jamais bloquant
    # ------------------------------------------------------------------

    async def _on_event(self, event: Event) -> None:
        """Callback du bus : spawn une tâche par hook abonné au nom.

        Ne lève jamais et n'attend jamais l'exécution des hooks : le
        ``publish`` de l'émetteur revient dès les tâches créées (AC 1 —
        un hook lent/erreur ne bloque jamais l'émetteur).
        """
        try:
            name = event.event_type.value
            for instance in list(self._instances.values()):
                for hook in instance.hooks.get(name, []):
                    self._spawn_hook_task(instance, hook, event, name)
        except Exception:  # pragma: no cover — défense absolue
            logger.exception(
                "Plugin hooks service : erreur de dispatch de %s (ignorée)",
                getattr(event.event_type, "value", "?"),
            )

    def _spawn_hook_task(
        self,
        instance: PluginHooks,
        hook: Any,
        event: Event,
        name: str,
    ) -> None:
        """Crée la tâche isolée d'un hook (référence forte + done-callback)."""
        task = asyncio.create_task(
            self._run_hook(instance, hook, event, name),
            name=f"plugin-hook:{instance.plugin_name}:{name}",
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run_hook(
        self,
        instance: PluginHooks,
        hook: Any,
        event: Event,
        name: str,
    ) -> None:
        """Exécute un hook sous sémaphore + timeout ; erreurs journalisées.

        Toute exception (dont ``TimeoutError`` du ``wait_for``) est
        interceptée et journalisée — **jamais** remontée à l'émetteur.
        """
        plugin_event = self._to_plugin_event(event)
        async with self._semaphore:
            try:
                await asyncio.wait_for(hook(plugin_event), timeout=self._timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    "Plugin hook timeout (%ss) : plugin=%s événement=%s "
                    "(hook annulé, émetteur non affecté)",
                    self._timeout,
                    instance.plugin_name,
                    name,
                )
            except asyncio.CancelledError:
                # Shutdown pendant l'exécution d'un hook — remonte
                # normalement au propriétaire de la tâche, sans log
                # d'erreur (annulation volontaire).
                raise
            except Exception as exc:
                logger.error(
                    "Plugin hook error : plugin=%s événement=%s — %s",
                    instance.plugin_name,
                    name,
                    exc,
                    exc_info=True,
                )

    @staticmethod
    def _to_plugin_event(event: Event) -> PluginEvent:
        """Projette l'``Event`` interne en ``PluginEvent`` (copie défensive)."""
        return PluginEvent(
            name=event.event_type.value,
            data=dict(event.payload),  # copie défensive — rules 40
            timestamp=event.timestamp,
            event_id=str(event.event_id),
        )

    async def wait_for_hooks(self, timeout: Optional[float] = 5.0) -> None:
        """Attend la fin des tâches de hooks actives (helper de tests)."""
        while self._tasks:
            done, _ = await asyncio.wait(
                set(self._tasks), timeout=timeout, return_when=asyncio.ALL_COMPLETED
            )
            if len(done) == 0:  # timeout global atteint sans progression
                return

    # ------------------------------------------------------------------
    # Chargement lifespan des hooks_module (T6) — best-effort, sécurisé
    # ------------------------------------------------------------------

    async def load_installed_hooks(self, session_factory: Any = None) -> int:
        """Charge les ``hooks_module`` des plugins installés en base.

        STORY-163 (T6) : requête les plugins ``type IN (extension,
        hybrid)`` ET ``status IN (installed, running)`` ; pour chaque
        ``manifest_data.extensions.hooks_module`` présent :

        1. résolution du chemin sous ``plugins_base_dir/<plugin_name>/``
           avec contrôle **anti path-traversal** (pattern
           ``plugin_lifecycle_service._resolve_script_path`` — refus des
           chemins absolus, des ``..`` et de toute sortie du base_dir) ;
        2. import dynamique ``importlib`` du module (dossier ajouté au
           ``sys.path`` de manière isolée le temps de l'import) ;
        3. instanciation de la première sous-classe ``PluginHooks`` du
           module, puis ``register()``.

        Best-effort (rules 40 + robustesse startup) : l'échec d'un plugin
        (chemin invalide, import impossible, aucune sous-classe) est
        journalisé WARNING et le plugin ignoré — le startup reste intact.
        Tant que STORY-169 (installation réelle) n'est pas faite, la base
        ne contient pas de fichiers extraits : le comportement attendu en
        environnement courant est zéro hook chargé (log debug).

        Args:
            session_factory: Factory de sessions async (défaut :
                ``AsyncSessionLocal``) — injectable pour les tests.

        Returns:
            Nombre d'instances de hooks effectivement chargées.
        """
        from sqlalchemy import select

        if session_factory is None:
            from ..database import AsyncSessionLocal

            session_factory = AsyncSessionLocal

        from ..models.plugin import Plugin

        try:
            async with session_factory() as session:
                result = await session.execute(
                    select(Plugin).where(
                        Plugin.type.in_(("extension", "hybrid")),
                        Plugin.status.in_(("installed", "running")),
                    )
                )
                plugins = list(result.scalars().all())
        except Exception as exc:
            logger.error(
                "Plugin hooks : lecture des plugins installés impossible (%s) "
                "— aucun hook chargé (startup intact)",
                exc,
            )
            return 0

        loaded = 0
        for plugin in plugins:
            instance = self._load_plugin_hooks(plugin.name, plugin.manifest_data or {})
            if instance is not None:
                self.register(instance)
                loaded += 1
        if loaded == 0:
            logger.debug(
                "Plugin hooks : aucun hooks_module chargé "
                "(%d plugin(s) extension/hybrid installé(s) examiné(s))",
                len(plugins),
            )
        return loaded

    def _load_plugin_hooks(
        self, plugin_name: str, manifest_data: Dict[str, Any]
    ) -> Optional[PluginHooks]:
        """Importe et instancie le ``hooks_module`` d'un plugin (best-effort).

        Retourne ``None`` (avec WARNING) si le manifest ne déclare pas de
        ``hooks_module``, si le chemin est refusé (path traversal), si
        l'import échoue ou si le module n'expose pas de sous-classe
        ``PluginHooks``. Ne lève jamais.
        """
        extensions = manifest_data.get("extensions") or {}
        if not isinstance(extensions, dict):
            extensions = {}
        hooks_module = extensions.get("hooks_module")
        if not hooks_module:
            return None  # plugin sans hooks — cas nominal, pas de log

        try:
            module_path = _resolve_hooks_module_path(plugin_name, hooks_module)
        except Exception as exc:
            logger.warning(
                "Plugin hooks : hooks_module de %r refusé (%s) — plugin ignoré",
                plugin_name,
                exc,
            )
            return None

        module_name = _module_name_from_path(hooks_module)
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"spec introuvable pour {module_path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = (
                module  # registre standard requis par dataclass etc.
            )
            spec.loader.exec_module(module)
            instance = _instantiate_hooks(module)
            if instance is None:
                logger.warning(
                    "Plugin hooks : aucune sous-classe PluginHooks dans le "
                    "hooks_module de %r — plugin ignoré",
                    plugin_name,
                )
                return None
            logger.info(
                "Plugin hooks chargés depuis %s (plugin=%s)",
                hooks_module,
                plugin_name,
            )
            return instance
        except Exception as exc:
            logger.warning(
                "Plugin hooks : échec d'import du hooks_module de %r (%s) — "
                "plugin ignoré, startup intact",
                plugin_name,
                exc,
            )
            return None


# ----------------------------------------------------------------------
# Helpers de chargement (module-level — testables isolément)
# ----------------------------------------------------------------------


def _resolve_hooks_module_path(plugin_name: str, hooks_module: str) -> str:
    """Résout le chemin absolu d'un ``hooks_module`` sous ``plugins_base_dir``.

    Miroir strict de ``plugin_lifecycle_service._resolve_script_path``
    (pattern réutilisé tel quel) : le chemin est résolu relativement à
    ``settings.plugins_base_dir/<plugin_name>/`` avec refus des chemins
    absolus, des segments ``..`` et de toute résolution sortant du
    base_dir (anti path-traversal, rules 40).

    Args:
        plugin_name: Nom du plugin (kebab-case — répertoire d'installation).
        hooks_module: Chemin relatif du module déclaré dans le manifest
            (ex. ``hooks/main.py`` ou ``hooks.main``).

    Returns:
        Chemin absolu du fichier module.

    Raises:
        WindFlowException: Si le chemin est invalide (absolu, traversal,
            hors base_dir) ou si l'extension n'est pas ``.py``.
    """
    from ..core.exceptions import WindFlowException

    # Normaliser la notation dotted (hooks.main → hooks/main.py) —
    # uniquement si le chemin n'est pas déjà en notation fichier
    # (sinon "main.py" deviendrait "main/py").
    if "/" not in hooks_module and os.sep not in hooks_module:
        normalized = hooks_module.replace(".", os.sep)
        if not normalized.endswith(".py"):
            normalized = normalized + ".py"
    else:
        normalized = hooks_module
        if not normalized.endswith(".py"):
            normalized = normalized + ".py"

    if os.path.isabs(normalized):
        raise WindFlowException(
            f"Chemin de hooks_module absolu interdit : {hooks_module}",
            details={"error_type": "invalid_hooks_path", "hooks_module": hooks_module},
        )
    if ".." in normalized.split(os.sep) or ".." in normalized.split("/"):
        raise WindFlowException(
            f"Path traversal détecté dans hooks_module : {hooks_module}",
            details={"error_type": "path_traversal", "hooks_module": hooks_module},
        )

    base_dir = os.path.normpath(settings.plugins_base_dir.rstrip("/"))
    full_path = os.path.normpath(os.path.join(base_dir, plugin_name, normalized))
    if not full_path.startswith(base_dir + os.sep) and full_path != base_dir:
        raise WindFlowException(
            f"hooks_module en dehors du répertoire de base : {hooks_module}",
            details={"error_type": "path_traversal", "hooks_module": hooks_module},
        )
    return full_path


def _module_name_from_path(hooks_module: str) -> str:
    """Convertis un chemin de module relatif en nom importable.

    ``hooks/main.py`` → ``main`` ; ``hooks.main`` → ``hooks.main``. Le
    nom est préfixé par ``windflow_plugin_`` pour éviter tout masquage
    accidentel d'un module applicatif (``app.*``) par un module plugin.
    """
    normalized = hooks_module.replace(os.sep, ".").replace("/", ".")
    if normalized.endswith(".py"):
        normalized = normalized[: -len(".py")]
    parts = [part for part in normalized.split(".") if part]
    leaf = parts[-1] if parts else "hooks"
    return f"windflow_plugin_{leaf}"


def _instantiate_hooks(module: Any) -> Optional[PluginHooks]:
    """Instancie la première sous-classe concrète de ``PluginHooks``.

    Parcourt les membres du module (ordre ``dir``) ; ``PluginHooks``
    lui-même est exclu, de même que les classes dont le module d'origine
    n'est pas le module plugin (ex. imports du SDK) — seule une
    sous-classe **définie dans le module** est instanciée.
    """
    for attr_name in dir(module):
        member = getattr(module, attr_name)
        if (
            isinstance(member, type)
            and issubclass(member, PluginHooks)
            and member is not PluginHooks
            and getattr(member, "__module__", None) == module.__name__
        ):
            return member()
    return None
