"""Service d'exécution des gates pre-deploy des plugins (STORY-170.2 — T5).

Registre process-local des gates déclarées via
``manifest_data.deploy_hooks.pre_deploy`` (spec 11 § Hooks de déploiement)
et exécution **bloquante** de celles-ci dans le pipeline de déploiement
(:func:`app.tasks.background_tasks.deploy_stack_async`) — après résolution
d'images, **avant création des containers**.

Responsabilités :

- **registre** (:meth:`PluginGateService.register` /
  :meth:`PluginGateService.unregister`) : un handler par plugin (nom de
  plugin = clé — le branchement install/uninstall du
  ``plugin_manager_service`` maintient le registre en phase avec la base,
  persistant via ``manifest_data``, aucune migration) ;
- **chargement lifespan** (:meth:`PluginGateService.load_installed_gates`)
  : pattern ``plugin_hooks_service.load_installed_hooks`` (STORY-163) —
  plugins ``extension|hybrid`` + ``installed|running``, lecture du
  manifest, import sécurisé anti path-traversal du handler
  ``module:fonction`` (helpers STORY-163 réutilisés par import direct —
  pas de copier-coller), best-effort WARNING sans crash du startup ;
- **exécution** (:meth:`PluginGateService.run_gates`) : itération en
  **ordre alphabétique des noms de plugins** (déterminisme), chaque gate
  sous ``asyncio.wait_for`` avec le timeout du manifest ou le défaut
  settings ``plugin_gate_timeout_seconds`` (spec 11 : 300 s) ;

Comportements par défaut (spec 11 + divergences documentées de l'analyse
STORY-170) :

- **aucune gate enregistrée** → approbation immédiate (le core ne bloque
  jamais par défaut — non-régression des déploiements sans plugin) ;
- **timeout** → refus prudent ``GATE_TIMEOUT`` (« on ne déploie pas ce
  qu'on n'a pas pu évaluer ») sauf ``on_timeout: approve`` déclaré ;
- **handler en erreur** (divergence n°4) → refus prudent ``gate_error`` ;
- **plusieurs gates** : approbation de toutes requise, **premier deny
  court-circuite** (les gates suivantes ne sont pas exécutées).

Sécurité (rules 40) : le contexte transmis au handler
(:class:`~app.plugins.gates.DeployContext`) ne contient jamais de secret
(IDs/noms/images uniquement) ; les logs structurés ne journalisent ni
payload ni raison complète — plugin, code et décision uniquement.

Divergence n°6 (multi-workers) : le registre est process-local — cohérent
avec l'arbitrage F1 (déploiement supporté single-worker, déjà documenté
pour le scheduler).
"""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import logging
import sys
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..config import settings
from ..core.exceptions import WindFlowException
from ..plugins.gates import DeployContext, GateDecision
from .plugin_hooks_service import _module_name_from_path, _resolve_hooks_module_path

logger = logging.getLogger(__name__)

#: Signature d'un handler de gate : coroutine recevant un
#: ``DeployContext`` et retournant une ``GateDecision``.
GateHandler = Callable[[DeployContext], Awaitable[GateDecision]]

#: Comportements ``on_timeout`` acceptés par le manifest.
_ON_TIMEOUT_VALUES = ("deny", "approve")


@dataclass
class GateOutcome:
    """Verdict consolidé de l'exécution des gates pour un déploiement.

    Attributes:
        decision: La décision portée par le verdict (approuvée ou refusée).
        plugin_name: Plugin dont la gate a refusé (``None`` si approbation).
        code: ``GATE_DENIED`` | ``GATE_TIMEOUT`` | ``gate_error`` sur un
            refus ; ``None`` sur une approbation.
        reason: Raison lisible du refus (jamais de secret — rules 40).
    """

    decision: GateDecision
    plugin_name: Optional[str] = None
    code: Optional[str] = None
    reason: Optional[str] = None

    @property
    def approved(self) -> bool:
        """``True`` si le déploiement est autorisé à poursuivre."""
        return self.decision.approved


class PluginGateService:
    """Registre et exécution des gates pre-deploy des plugins.

    Args:
        default_timeout: Timeout par défaut en secondes (défaut :
            ``settings.plugin_gate_timeout_seconds`` — surchargé par
            manifest). Injecté par les tests.
    """

    def __init__(self, *, default_timeout: Optional[float] = None) -> None:
        self._default_timeout = (
            default_timeout
            if default_timeout is not None
            else float(settings.plugin_gate_timeout_seconds)
        )
        # plugin_name → entrée de registre (handler + overrides manifest).
        self._gates: Dict[str, "_GateEntry"] = {}

    # ── Registre ────────────────────────────────────────────────────────────

    def register(
        self,
        plugin_name: str,
        handler: GateHandler,
        timeout_override: Optional[float] = None,
        on_timeout: str = "deny",
    ) -> None:
        """Enregistre la gate d'un plugin (idempotent par nom de plugin).

        Un ré-enregistrement remplace l'entrée précédente (le
        branchement install/uninstall du manager garde le registre en
        phase avec la base — la clé est le nom unique du plugin).

        Args:
            plugin_name: Nom du plugin (kebab-case).
            handler: Coroutine ``DeployContext → GateDecision``.
            timeout_override: Timeout en secondes déclaré par le manifest
                (``None`` → défaut settings).
            on_timeout: ``"deny"`` (refus prudent, défaut) ou
                ``"approve"`` (déploiement autorisé au timeout).
        """
        if on_timeout not in _ON_TIMEOUT_VALUES:
            # Défense en profondeur — le schéma manifest a déjà validé.
            logger.warning(
                "plugin_gate_invalid_on_timeout",
                extra={"plugin_name": plugin_name, "on_timeout": on_timeout},
            )
            on_timeout = "deny"
        self._gates[plugin_name] = _GateEntry(
            handler=handler,
            timeout_override=timeout_override,
            on_timeout=on_timeout,
        )
        logger.info(
            "plugin_gate_registered",
            extra={
                "plugin_name": plugin_name,
                "timeout": timeout_override or self._default_timeout,
                "on_timeout": on_timeout,
            },
        )

    def unregister(self, plugin_name: str) -> None:
        """Retire la gate d'un plugin (idempotent — no-op si absente)."""
        if self._gates.pop(plugin_name, None) is not None:
            logger.info("plugin_gate_unregistered", extra={"plugin_name": plugin_name})

    @property
    def registered_count(self) -> int:
        """Nombre de gates actuellement enregistrées."""
        return len(self._gates)

    @property
    def registered_plugins(self) -> List[str]:
        """Noms des plugins dont une gate est enregistrée (triés)."""
        return sorted(self._gates.keys())

    def reset(self) -> None:
        """Purge le registre (isolation des tests)."""
        self._gates.clear()

    # ── Exécution ───────────────────────────────────────────────────────────

    async def run_gates(self, ctx: DeployContext) -> GateOutcome:
        """Exécute toutes les gates enregistrées et retourne le verdict.

        Sémantique (spec 11 § Hooks de déploiement + divergences) :

        - aucune gate → approbation immédiate (le core ne bloque jamais
          par défaut) ;
        - itération **ordre alphabétique des noms de plugins**
          (déterminisme — tests et audit reproductibles) ;
        - chaque gate sous ``asyncio.wait_for`` avec le timeout du
          manifest (borné par le schéma 1-3600) ou le défaut settings ;
        - timeout → ``on_timeout == "approve"`` sinon refus ``GATE_TIMEOUT`` ;
        - exception handler → refus prudent ``gate_error`` (divergence
          n°4 — on ne déploie pas ce qu'on n'a pas pu évaluer) ;
        - premier refus **court-circuite** — les gates suivantes ne sont
          pas exécutées (AC 2).

        Args:
            ctx: Contexte de déploiement (payload sans secret — rules 40).

        Returns:
            Le verdict consolidé (décision + plugin/code/raison du refus).
        """
        if not self._gates:
            return GateOutcome(decision=GateDecision.approve())

        for plugin_name in sorted(self._gates.keys()):
            entry = self._gates[plugin_name]
            timeout = (
                entry.timeout_override
                if entry.timeout_override is not None
                else self._default_timeout
            )
            # Défense en profondeur : le contrat SDK est un handler
            # ``async`` — un handler sync (gate décisionnelle pure,
            # sans I/O) est néanmoins toléré (pas de timeout possible
            # sur du code non-awaitable, ce qui est sans risque ici).
            try:
                call = entry.handler(ctx)
                if inspect.isawaitable(call):
                    decision = await asyncio.wait_for(call, timeout=timeout)
                else:
                    decision = call
            except asyncio.TimeoutError:
                if entry.on_timeout == "approve":
                    logger.warning(
                        "plugin_gate_timeout_approved",
                        extra={
                            "plugin_name": plugin_name,
                            "timeout": timeout,
                        },
                    )
                    continue  # gate suivante
                logger.warning(
                    "plugin_gate_timeout_denied",
                    extra={"plugin_name": plugin_name, "timeout": timeout},
                )
                return GateOutcome(
                    decision=GateDecision.deny(
                        f"gate timeout ({timeout}s) — refus prudent"
                    ),
                    plugin_name=plugin_name,
                    code="GATE_TIMEOUT",
                    reason=f"gate timeout ({timeout}s)",
                )
            except asyncio.CancelledError:
                # Annulation du déploiement lui-même — remonte au
                # pipeline (pas une décision de gate).
                raise
            except Exception as exc:
                # Divergence n°4 : handler en erreur = refus prudent.
                logger.error(
                    "plugin_gate_handler_error",
                    extra={"plugin_name": plugin_name, "error": str(exc)},
                    exc_info=True,
                )
                return GateOutcome(
                    decision=GateDecision.deny("gate_error — refus prudent"),
                    plugin_name=plugin_name,
                    code="gate_error",
                    reason="gate_error",
                )

            if not isinstance(decision, GateDecision):
                # Contrat SDK non respecté — même logique prudente que
                # l'erreur (défense en profondeur).
                logger.error(
                    "plugin_gate_invalid_decision_type",
                    extra={
                        "plugin_name": plugin_name,
                        "decision_type": type(decision).__name__,
                    },
                )
                return GateOutcome(
                    decision=GateDecision.deny("gate_error — refus prudent"),
                    plugin_name=plugin_name,
                    code="gate_error",
                    reason="gate_error",
                )

            if not decision.approved:
                logger.info(
                    "plugin_gate_denied",
                    extra={"plugin_name": plugin_name},
                )
                return GateOutcome(
                    decision=decision,
                    plugin_name=plugin_name,
                    code="GATE_DENIED",
                    reason=decision.reason or "refus sans raison fournie",
                )

        return GateOutcome(decision=GateDecision.approve())

    # ── Chargement lifespan ─────────────────────────────────────────────────

    async def load_installed_gates(self, session_factory: Any = None) -> int:
        """Charge les gates ``deploy_hooks.pre_deploy`` des plugins installés.

        Pattern ``plugin_hooks_service.load_installed_hooks`` (STORY-163)
        : requête les plugins ``type IN (extension, hybrid)`` ET
        ``status IN (installed, running)`` ; pour chaque
        ``manifest_data.deploy_hooks.pre_deploy`` présent :

        1. split du handler ``module:fonction`` ;
        2. résolution du chemin module sous
           ``plugins_base_dir/<plugin_name>/`` via
           ``_resolve_hooks_module_path`` (anti path-traversal, préfixe
           ``windflow_plugin_`` anti-masquage — helpers STORY-163
           réutilisés par import direct) ;
        3. import dynamique ``importlib`` + ``getattr`` de la fonction.

        Best-effort (rules 40 + robustesse startup) : l'échec d'un plugin
        (handler introuvable, chemin refusé, import impossible, fonction
        absente) est journalisé WARNING et le plugin ignoré — le startup
        reste intact. Un plugin ``service`` déclarant une gate est ignoré
        (warning) : les gates ne concernent que extension/hybrid.

        Args:
            session_factory: Factory de sessions async (défaut :
                ``AsyncSessionLocal``) — injectable pour les tests.

        Returns:
            Nombre de gates effectivement chargées.
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
                "Plugin gates : lecture des plugins installés impossible "
                "(%s) — aucune gate chargée (startup intact)",
                exc,
            )
            return 0

        loaded = 0
        for plugin in plugins:
            if self._load_plugin_gate(plugin.name, plugin.manifest_data or {}):
                loaded += 1
        if loaded == 0:
            logger.debug(
                "Plugin gates : aucune gate chargée "
                "(%d plugin(s) extension/hybrid installé(s) examiné(s))",
                len(plugins),
            )
        return loaded

    def load_gate_from_manifest(
        self, plugin_name: str, manifest_data: Dict[str, Any]
    ) -> bool:
        """Charge et enregistre la gate d'un plugin fraîchement installé.

        Variante synchrone best-effort de :meth:`load_installed_gates`
        appelée par le ``plugin_manager_service`` à l'install
        (branchement volet gates, STORY-170.2) : lit
        ``manifest_data.deploy_hooks.pre_deploy``, importe le handler
        (import sécurisé STORY-163) et l'enregistre au registre. Un
        handler introuvable est ignoré avec WARNING — l'installation ne
        doit pas échouer pour un problème de gate (le redémarrage
        retentera via le chargement lifespan).

        Args:
            plugin_name: Nom du plugin (kebab-case).
            manifest_data: ``manifest_data`` persisté du plugin.

        Returns:
            ``True`` si une gate a été enregistrée.
        """
        return self._load_plugin_gate(plugin_name, manifest_data)

    def _load_plugin_gate(
        self, plugin_name: str, manifest_data: Dict[str, Any]
    ) -> bool:
        """Importe le handler de gate d'un plugin (best-effort).

        Retourne ``False`` (avec WARNING) si le manifest ne déclare pas
        de ``deploy_hooks.pre_deploy``, si le type du plugin n'est pas
        extension/hybrid (la requête lifespan filtre déjà — défense en
        profondeur pour l'appel direct), si le handler est malformé, si
        le chemin est refusé (path traversal), si l'import échoue ou si
        la fonction est absente du module. Ne lève jamais.
        """
        deploy_hooks = manifest_data.get("deploy_hooks") or {}
        if not isinstance(deploy_hooks, dict):
            deploy_hooks = {}
        pre_deploy = deploy_hooks.get("pre_deploy")
        if not pre_deploy:
            return False  # plugin sans gate — cas nominal, pas de log

        if not isinstance(pre_deploy, dict):
            logger.warning(
                "Plugin gates : deploy_hooks.pre_deploy de %r malformé "
                "(dict attendu) — plugin ignoré",
                plugin_name,
            )
            return False

        handler_ref = pre_deploy.get("handler")
        if (
            not handler_ref
            or not isinstance(handler_ref, str)
            or ":" not in handler_ref
        ):
            logger.warning(
                "Plugin gates : handler manquant ou invalide dans "
                "deploy_hooks.pre_deploy de %r — plugin ignoré",
                plugin_name,
            )
            return False

        module_part, _, function_part = handler_ref.rpartition(":")
        try:
            module_path = _resolve_hooks_module_path(plugin_name, module_part)
        except WindFlowException as exc:
            logger.warning(
                "Plugin gates : handler de %r refusé (%s) — plugin ignoré",
                plugin_name,
                exc,
            )
            return False

        module_name = _module_name_from_path(module_part)
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"spec introuvable pour {module_path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = (
                module  # registre standard requis par dataclass etc.
            )
            spec.loader.exec_module(module)
            function = getattr(module, function_part, None)
            if not callable(function):
                logger.warning(
                    "Plugin gates : fonction %r absente du module %r de %r "
                    "— plugin ignoré, startup intact",
                    function_part,
                    module_part,
                    plugin_name,
                )
                return False
        except Exception as exc:
            logger.warning(
                "Plugin gates : échec d'import du handler de %r (%s) — "
                "plugin ignoré, startup intact",
                plugin_name,
                exc,
            )
            return False

        timeout_override = pre_deploy.get("timeout")
        self.register(
            plugin_name,
            function,  # type: ignore[arg-type]
            timeout_override=(
                float(timeout_override) if timeout_override is not None else None
            ),
            on_timeout=pre_deploy.get("on_timeout", "deny"),
        )
        logger.info(
            "Plugin gate chargée depuis %s (plugin=%s)",
            handler_ref,
            plugin_name,
        )
        return True


@dataclass
class _GateEntry:
    """Entrée de registre : handler + overrides du manifest."""

    handler: GateHandler
    timeout_override: Optional[float]
    on_timeout: str


# Singleton process-wide — le manager (install/uninstall), le lifespan
# (chargement startup) et le pipeline (run_gates) partagent la même
# instance pour opérer sur le même registre (pattern instances
# module-level des routers ; divergence n°6 : registre process-local).
_plugin_gate_service: Optional[PluginGateService] = None


def get_plugin_gate_service() -> PluginGateService:
    """Retourne le singleton process-wide du service (le crée au besoin)."""
    global _plugin_gate_service
    if _plugin_gate_service is None:
        _plugin_gate_service = PluginGateService()
    return _plugin_gate_service


def reset_plugin_gate_service() -> None:
    """Réinitialise le singleton (isolation des tests)."""
    global _plugin_gate_service
    if _plugin_gate_service is not None:
        _plugin_gate_service.reset()
    _plugin_gate_service = None
