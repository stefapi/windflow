"""Service de montage/démontage des routes API dynamiques des plugins.

STORY-170.1 (T3) — implémente le volet « routes dynamiques » de la spec 11
§ Extension de l'API : les plugins extension/hybrid déclarant
``manifest_data.extensions.api_module`` voient leurs routes montées sous
``/api/v1/plugins/{name}/…`` sur l'app FastAPI racine.

Responsabilités :

- **montage** (:meth:`PluginApiRouterService.mount`) : snapshot de
  ``app.router.routes`` avant ``include_router`` puis diff par identité
  pour tracker les routes ajoutées par plugin — c'est ce tracking qui
  rend le démontage possible (FastAPI n'a pas d'API ``remove_router``) ;
- **garde de préfixe** : le router monté DOIT avoir le préfixe
  ``/api/v1/plugins/{plugin_name}`` (refus typé sinon) — un plugin ne
  peut pas injecter de routes hors de son espace de noms (sécurité,
  rules 40) ;
- **défense en profondeur JWT** : ``get_current_active_user`` est
  injecté au niveau du ``include_router`` **même si le plugin ne
  l'a pas déclaré** — combiné au RBAC par endpoint du SDK
  (``require_viewer``/``require_operator``/``require_admin``, spec 08),
  une route plugin oubliée reste protégée (401 sans token) ;
- **invalidation OpenAPI** : ``app.openapi_schema = None`` à chaque
  montage/démontage — point critique, ``custom_openapi()`` (main.py)
  met le schéma en cache ; sans invalidation, la route n'apparaîtrait
  pas/disparaîtrait pas de ``/openapi.json`` (AC 1) ;
- **démontage** (:meth:`PluginApiRouterService.unmount`) : retrait des
  routes trackées + invalidation OpenAPI, **idempotent** (no-op si le
  plugin n'est pas monté) ;
- **chargement lifespan** (:meth:`PluginApiRouterService.load_installed_routers`)
  : pattern ``plugin_hooks_service.load_installed_hooks`` — plugins
  ``extension|hybrid`` actifs avec ``api_module``, import sécurisé anti
  path-traversal (helpers STORY-163 réutilisés par import direct),
  montage best-effort WARNING sans crash du startup.

Divergences documentées (analyse STORY-170) :

- n°3 : montage **process-wide** (``plugins.name`` unique globalement) —
  la confidentialité repose sur JWT + RBAC core (rôle global) ;
- n°6 : montage à chaud process-local — cohérent avec l'arbitrage F1
  (déploiement supporté single-worker).
"""

import importlib.util
import logging
import sys
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, FastAPI

from ..auth.dependencies import get_current_active_user
from ..core.exceptions import WindFlowException
from ..plugins.api import PLUGINS_API_PREFIX, is_valid_plugin_name
from .plugin_hooks_service import _module_name_from_path, _resolve_hooks_module_path

logger = logging.getLogger(__name__)


class PluginApiRouterService:
    """Monte/démonte les routes API des plugins sur l'app FastAPI racine."""

    def __init__(self) -> None:
        self._app: Optional[FastAPI] = None
        # plugin_name → routes ajoutées par le montage (identités
        # d'objets route Starlette, retirées à l'unmount).
        self._mounted: Dict[str, List[Any]] = {}

    # ── Cycle de vie du service ────────────────────────────────────────────

    @property
    def app(self) -> Optional[FastAPI]:
        """App FastAPI référencée (``None`` tant que non initialisée)."""
        return self._app

    @property
    def is_initialized(self) -> bool:
        """``True`` si le service référence une app FastAPI montable."""
        return self._app is not None

    def initialize(self, app: FastAPI) -> None:
        """Référence l'app FastAPI cible des montages (appelé au startup).

        Args:
            app: L'application FastAPI racine (main.app).
        """
        self._app = app
        logger.info("Plugin API router service initialized")

    @property
    def mounted_plugins(self) -> List[str]:
        """Noms des plugins dont les routes sont actuellement montées."""
        return sorted(self._mounted.keys())

    # ── Montage / démontage ────────────────────────────────────────────────

    def mount_from_manifest(
        self, plugin_name: str, manifest_data: Dict[str, Any]
    ) -> int:
        """Monte les routes ``api_module`` d'un plugin fraîchement installé.

        Variante **stricte** du chargement lifespan : l'échec de
        chargement (module introuvable, import impossible, module sans
        ``router``, garde de préfixe refusée) lève une
        ``WindFlowException`` typée ``extension_load_failed`` —
        l'appelant (:class:`~app.services.plugin_manager_service.PluginManagerService`)
        déclenche alors le rollback complet 169.3 (3e cas différé par
        169.3, AC 2) : démontage immédiat des routes déjà montées +
        rollback DB/FS/conteneur + erreur cause+suggestion.

        Cas particuliers :

        - manifest sans ``extensions.api_module`` : no-op (retour 0) —
          plugin sans routes, cas nominal ;
        - service non initialisé (aucune app FastAPI dans le process —
          CLI, worker, tests service) : montage **différé** au
          chargement lifespan du prochain démarrage API (divergence n°6
          process-local documentée) — l'install reste vert.

        Args:
            plugin_name: Nom du plugin (kebab-case — espace de noms).
            manifest_data: ``manifest_data`` persisté du plugin.

        Returns:
            Nombre de routes montées.

        Raises:
            WindFlowException: ``extension_load_failed`` si le
                chargement ou le montage échoue (cause de l'étage dans
                ``details.cause``).
        """
        extensions = manifest_data.get("extensions") or {}
        if not isinstance(extensions, dict):
            extensions = {}
        api_module = extensions.get("api_module")
        if not api_module:
            return 0

        if self._app is None:
            logger.info(
                "plugin_routes_mount_deferred",
                extra={
                    "plugin_name": plugin_name,
                    "reason": "no_fastapi_app_in_process",
                },
            )
            return 0

        try:
            router = self._import_plugin_router(plugin_name, str(api_module))
            return self.mount(plugin_name, router)
        except WindFlowException as exc:
            details = dict(exc.details)
            cause = details.get("error_type") or "unknown"
            details.update(
                {
                    "error_type": "extension_load_failed",
                    "plugin_name": plugin_name,
                    "api_module": api_module,
                    "cause": cause,
                }
            )
            raise WindFlowException(
                f"Échec du chargement des routes du plugin {plugin_name!r} "
                f"({api_module}) : {exc.message}",
                details=details,
            ) from exc
        except Exception as exc:  # import Python cassé (SyntaxError…)
            raise WindFlowException(
                f"Échec d'import de l'api_module {api_module!r} du plugin "
                f"{plugin_name!r} : {exc}",
                details={
                    "error_type": "extension_load_failed",
                    "plugin_name": plugin_name,
                    "api_module": api_module,
                    "cause": "import_error",
                },
            ) from exc

    def _import_plugin_router(self, plugin_name: str, api_module: str) -> APIRouter:
        """Import sécurisé de l'``api_module`` d'un plugin → son router.

        Variante stricte de ``_load_plugin_router`` (best-effort
        lifespan) : lève ``WindFlowException`` typée à chaque étage
        refusé (chemin path-traversal, import impossible, module sans
        ``router``) au lieu d'avaler.

        Args:
            plugin_name: Nom du plugin (répertoire d'installation).
            api_module: Chemin relatif déclaré dans le manifest.

        Returns:
            Le ``APIRouter`` exposé par le module.

        Raises:
            WindFlowException: Chemin refusé, import impossible ou
                module sans ``router``.
        """
        module_path = _resolve_hooks_module_path(plugin_name, api_module)
        module_name = _module_name_from_path(api_module)
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise WindFlowException(
                f"Module introuvable : {module_path}",
                details={
                    "error_type": "api_module_import_failed",
                    "plugin_name": plugin_name,
                },
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # registre standard requis
        spec.loader.exec_module(module)
        router = getattr(module, "router", None)
        if not isinstance(router, APIRouter):
            raise WindFlowException(
                f"Le module {api_module!r} du plugin {plugin_name!r} n'expose "
                "pas de variable 'router' APIRouter (issue de "
                "plugin_router(...))",
                details={
                    "error_type": "api_module_missing_router",
                    "plugin_name": plugin_name,
                },
            )
        logger.info(
            "Plugin routes chargées depuis %s (plugin=%s)",
            api_module,
            plugin_name,
        )
        return router

    def mount(self, plugin_name: str, router: APIRouter) -> int:
        """Monte le router d'un plugin sur l'app, avec tracking des routes.

        Garanties appliquées au ``include_router`` :

        - **garde de préfixe** : ``router.prefix`` doit être exactement
          ``/api/v1/plugins/{plugin_name}`` (refus typé sinon) ;
        - **défense en profondeur JWT** : ``get_current_active_user``
          injecté au niveau router (s'ajoute aux dependencies des
          endpoints du plugin) ;
        - **invalidation OpenAPI** : ``app.openapi_schema = None``.

        Args:
            plugin_name: Nom du plugin (kebab-case — espace de noms).
            router: Le router issu de ``plugin_router(plugin_name)``.

        Returns:
            Nombre de routes ajoutées à ``app.router.routes``.

        Raises:
            WindFlowException: Si le service n'est pas initialisé
                (``router_service_not_initialized``), si le nom est
                invalide (``invalid_plugin_name``), si le router n'est
                pas dans l'espace de noms du plugin
                (``invalid_router_prefix``) ou si les routes du plugin
                sont déjà montées (``plugin_routes_already_mounted``).
        """
        if self._app is None:
            raise WindFlowException(
                "Plugin API router service non initialisé — appeler "
                "initialize(app) au startup avant tout montage",
                details={"error_type": "router_service_not_initialized"},
            )
        if not is_valid_plugin_name(plugin_name):
            raise WindFlowException(
                f"Nom de plugin invalide pour le montage : {plugin_name!r} "
                "(kebab-case attendu)",
                details={"error_type": "invalid_plugin_name", "plugin_name": plugin_name},
            )
        expected_prefix = f"{PLUGINS_API_PREFIX}/{plugin_name}"
        if router.prefix != expected_prefix:
            raise WindFlowException(
                f"Router du plugin {plugin_name!r} hors de son espace de "
                f"noms : préfixe {router.prefix!r}, attendu {expected_prefix!r}",
                details={
                    "error_type": "invalid_router_prefix",
                    "plugin_name": plugin_name,
                    "expected_prefix": expected_prefix,
                    "actual_prefix": router.prefix,
                },
            )
        if plugin_name in self._mounted:
            raise WindFlowException(
                f"Les routes du plugin {plugin_name!r} sont déjà montées",
                details={
                    "error_type": "plugin_routes_already_mounted",
                    "plugin_name": plugin_name,
                },
            )

        # Snapshot avant montage → diff par identité (les routes
        # Starlette ne redéfinissent pas __eq__ de façon fiable pour un
        # diff ; l'identité d'objet est le seul critère exact).
        snapshot_ids = {id(route) for route in self._app.router.routes}

        # Défense en profondeur JWT (STORY-170.1) : même si le plugin a
        # oublié les dependencies d'auth, la route reste protégée.
        self._app.include_router(
            router, dependencies=[Depends(get_current_active_user)]
        )

        added = [
            route
            for route in self._app.router.routes
            if id(route) not in snapshot_ids
        ]
        self._mounted[plugin_name] = added
        self._invalidate_openapi()
        logger.info(
            "plugin_routes_mounted",
            extra={"plugin_name": plugin_name, "route_count": len(added)},
        )
        return len(added)

    def unmount(self, plugin_name: str) -> int:
        """Démonte les routes trackées d'un plugin (idempotent).

        Retire les routes ajoutées au montage de ``app.router.routes``
        et invalide le cache OpenAPI. No-op (retour 0) si le plugin
        n'est pas monté — l'uninstall et le rollback doivent rester
        sûrs en tout état de la DB/process.

        Args:
            plugin_name: Nom du plugin.

        Returns:
            Nombre de routes retirées (0 si rien n'était monté).
        """
        if self._app is None or plugin_name not in self._mounted:
            return 0

        mounted_ids = {id(route) for route in self._mounted[plugin_name]}
        # Mutation en place (slice assignment) : la liste ``routes`` peut
        # être référencée ailleurs (ex. openapi generation en cours).
        self._app.router.routes[:] = [
            route
            for route in self._app.router.routes
            if id(route) not in mounted_ids
        ]
        del self._mounted[plugin_name]
        self._invalidate_openapi()
        logger.info(
            "plugin_routes_unmounted",
            extra={"plugin_name": plugin_name, "route_count": len(mounted_ids)},
        )
        return len(mounted_ids)

    # ── Chargement lifespan ────────────────────────────────────────────────

    async def load_installed_routers(self, session_factory: Any = None) -> int:
        """Charge les ``api_module`` des plugins installés en base.

        Pattern ``plugin_hooks_service.load_installed_hooks`` (STORY-163)
        : requête les plugins ``type IN (extension, hybrid)`` ET
        ``status IN (installed, running)`` ; pour chaque
        ``manifest_data.extensions.api_module`` présent :

        1. résolution du chemin sous ``plugins_base_dir/<plugin_name>/``
           avec contrôle anti path-traversal (helpers STORY-163
           réutilisés par import direct) ;
        2. import dynamique ``importlib`` du module ;
        3. le module doit exposer une variable ``router``
           (``APIRouter``, issue de ``plugin_router(...)``) → montage.

        Best-effort (rules 40 + robustesse startup) : l'échec d'un
        plugin (chemin invalide, import impossible, module sans
        ``router``, préfixe refusé) est journalisé WARNING et le plugin
        ignoré — le startup reste intact.

        Args:
            session_factory: Factory de sessions async (défaut :
                ``AsyncSessionLocal``) — injectable pour les tests.

        Returns:
            Nombre de plugins dont les routes sont effectivement montées.
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
                "Plugin routes : lecture des plugins installés impossible "
                "(%s) — aucune route montée (startup intact)",
                exc,
            )
            return 0

        mounted = 0
        for plugin in plugins:
            router = self._load_plugin_router(plugin.name, plugin.manifest_data or {})
            if router is not None:
                try:
                    self.mount(plugin.name, router)
                    mounted += 1
                except Exception as exc:
                    logger.warning(
                        "Plugin routes : montage de %r impossible (%s) — "
                        "plugin ignoré, startup intact",
                        plugin.name,
                        exc,
                    )
        if mounted == 0:
            logger.debug(
                "Plugin routes : aucun api_module monté "
                "(%d plugin(s) extension/hybrid installé(s) examiné(s))",
                len(plugins),
            )
        return mounted

    def _load_plugin_router(
        self, plugin_name: str, manifest_data: Dict[str, Any]
    ) -> Optional[APIRouter]:
        """Importe l'``api_module`` d'un plugin et retourne son router.

        Best-effort (pattern ``_load_plugin_hooks``) : retourne
        ``None`` (avec WARNING) si le manifest ne déclare pas
        d'``api_module``, si le chemin est refusé (path traversal), si
        l'import échoue ou si le module n'expose pas de ``router``
        ``APIRouter``. Ne lève jamais.
        """
        extensions = manifest_data.get("extensions") or {}
        if not isinstance(extensions, dict):
            extensions = {}
        api_module = extensions.get("api_module")
        if not api_module:
            return None  # plugin sans routes — cas nominal, pas de log

        try:
            module_path = _resolve_hooks_module_path(plugin_name, api_module)
        except Exception as exc:
            logger.warning(
                "Plugin routes : api_module de %r refusé (%s) — plugin ignoré",
                plugin_name,
                exc,
            )
            return None

        module_name = _module_name_from_path(api_module)
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"spec introuvable pour {module_path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module  # registre standard requis
            spec.loader.exec_module(module)
            router = getattr(module, "router", None)
            if not isinstance(router, APIRouter):
                logger.warning(
                    "Plugin routes : api_module de %r n'expose pas de "
                    "variable 'router' APIRouter — plugin ignoré",
                    plugin_name,
                )
                return None
            logger.info(
                "Plugin routes chargées depuis %s (plugin=%s)",
                api_module,
                plugin_name,
            )
            return router
        except Exception as exc:
            logger.warning(
                "Plugin routes : échec d'import de l'api_module de %r (%s) "
                "— plugin ignoré, startup intact",
                plugin_name,
                exc,
            )
            return None

    # ── Internes ───────────────────────────────────────────────────────────

    def _invalidate_openapi(self) -> None:
        """Invalide le cache OpenAPI de l'app (point critique AC 1).

        ``custom_openapi()`` (main.py) met le schéma en cache dans
        ``app.openapi_schema`` : toute modification dynamique du set de
        routes DOIT invalider ce cache pour que la route apparaisse /
        disparaisse de ``/openapi.json`` et ``/docs``.
        """
        if self._app is not None:
            self._app.openapi_schema = None


# Singleton process-wide — l'app est référencée au startup (main.py),
# le manager (install/uninstall) et le lifespan partagent la même
# instance pour opérer sur le même set de routes.
_plugin_api_router_service: Optional[PluginApiRouterService] = None


def get_plugin_api_router_service() -> PluginApiRouterService:
    """Retourne le singleton process-wide du service (le crée au besoin)."""
    global _plugin_api_router_service
    if _plugin_api_router_service is None:
        _plugin_api_router_service = PluginApiRouterService()
    return _plugin_api_router_service
