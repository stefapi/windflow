"""Plugin démonstrateur — consommateur de 2 événements canoniques (AC 4).

Sous-classe :class:`~app.plugins.hooks.PluginHooks` consommant :

- ``stack.deployed`` → log d'action (INFO, contexte sans secret) ;
- ``deployment.failed`` → log/notification d'échec (WARNING).

**Non enregistré par défaut** : chargé uniquement si le setting
``plugin_hooks_demo_enabled`` est activé (défaut ``False`` — aucun
comportement ajouté en production) ou si le module est copié dans le
``plugins_base_dir`` d'une installation réelle (STORY-169). Les noms
SCREAMING_SNAKE ne sont jamais utilisés comme contrat d'abonnement
(refusés par ``@on_event`` — transport WebSocket uniquement).
"""

from __future__ import annotations

import logging

from ..hooks import PluginEvent, PluginHooks, on_event

logger = logging.getLogger("windflow.plugins.demo")


class DemoLoggerHooks(PluginHooks):
    """Démonstrateur : réaction à stack.deployed et deployment.failed."""

    @on_event("stack.deployed")
    async def on_stack_deployed(self, event: PluginEvent) -> None:
        """stack.deployed → log d'action (payload IDs/noms uniquement)."""
        stack_id = event.data.get("stack_id") or event.data.get("id")
        stack_name = event.data.get("stack_name") or event.data.get("name")
        logger.info(
            "DemoLoggerHooks : stack déployée (stack_id=%s, name=%s)",
            stack_id,
            stack_name,
        )

    @on_event("deployment.failed")
    async def on_deployment_failed(self, event: PluginEvent) -> None:
        """deployment.failed → log/notification d'échec."""
        deployment_id = event.data.get("deployment_id")
        logger.warning(
            "DemoLoggerHooks : déploiement échoué (deployment_id=%s) — "
            "notification simulée",
            deployment_id,
        )
