"""Mécaniques de protocole heartbeat WebSocket (STORY-164.1 — P2-5, axe C3).

Deux briques transverses consommables par **tous** les canaux WebSocket
(les 5 existants comme les 3 futurs de STORY-164.2) :

- :func:`receive_with_expiry` — expiration des connexions muettes : attend
  un message client borné par ``ws_heartbeat_timeout_factor ×
  ws_heartbeat_interval_seconds``. Toute activité reçue (``pong`` ou
  n'importe quel message) reset le délai puisque le timeout s'applique à
  chaque appel ; en cas de silence total, la connexion est fermée côté
  serveur (code ``1001``) et :class:`HeartbeatExpiredError` est levée pour
  que la boucle appelante sorte proprement (décision 4 de l'analyse
  STORY-164).
- :func:`periodic_ping` — ping serveur périodique (même mécanique que
  l'ancien heartbeat inline de ``general.py``), à exécuter dans une tâche
  annulée à la déconnexion.

Les délais sont bornés par les settings → réductibles en test sans
``sleep`` long (jamais de constante dure ici).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import WebSocket

from ..config import settings
from ..core.exceptions import WindFlowException

logger = logging.getLogger(__name__)

# Code de fermeture documenté pour l'expiration d'une connexion muette :
# 1001 (Going Away) — le serveur met fin à une connexion jugée morte.
WS_CLOSE_IDLE_TIMEOUT_CODE = 1001
WS_CLOSE_IDLE_TIMEOUT_REASON = "Idle connection expired (no client activity)"


class HeartbeatExpiredError(WindFlowException):
    """Connexion WebSocket fermée côté serveur pour inactivité totale.

    Levée par :func:`receive_with_expiry` après fermeture de la socket —
    les boucles de réception des canaux l'interceptent pour sortir
    proprement (le ``finally`` de chaque canal fait le nettoyage).
    """

    def __init__(self, channel: str = "", *, details: dict | None = None):
        super().__init__(
            f"WebSocket idle connection expired on channel {channel!r}",
            details=details,
        )
        self.channel = channel


def ws_inactivity_timeout() -> float:
    """Délai d'inactivité avant expiration (secondes), borné par les settings.

    ``ws_heartbeat_timeout_factor × ws_heartbeat_interval_seconds`` —
    défense en profondeur : les bornes ``gt``/``ge`` des settings sont
    re-vérifiées ici (jamais de timeout nul ou négatif).
    """
    interval = max(1, settings.ws_heartbeat_interval_seconds)
    factor = max(1, settings.ws_heartbeat_timeout_factor)
    return float(interval * factor)


async def receive_with_expiry(
    websocket: WebSocket, channel: str, user_id: Optional[str] = None
) -> str:
    """Attend un message client avec expiration de la connexion muette.

    Encapsule ``asyncio.wait_for(websocket.receive_text(), timeout=…)`` —
    chaque appel repart de zéro, donc **tout message reçu reset le délai**
    (décision 4 : l'activité peut être un ``pong``, un ping client ou
    n'importe quel message applicatif). En cas d'expiration : fermeture
    propre côté serveur (code ``1001``), log structuré sans donnée
    sensible, puis :class:`HeartbeatExpiredError`.

    Args:
        websocket: Connexion WebSocket active.
        channel: Nom du canal (pour les logs uniquement).
        user_id: Identifiant de l'utilisateur si connu (logs uniquement).

    Returns:
        Le message texte reçu du client.

    Raises:
        HeartbeatExpiredError: Aucune activité reçue dans le délai — la
            connexion a été fermée côté serveur.
    """
    timeout = ws_inactivity_timeout()
    try:
        return await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
    except asyncio.TimeoutError:
        extra: dict = {
            "channel": channel,
            "timeout_seconds": timeout,
            "reason": "idle_expiry",
        }
        if user_id is not None:
            extra["user_id"] = str(user_id)
        logger.warning(
            "WebSocket idle connection expired — closing server-side",
            extra=extra,
        )
        try:
            await websocket.close(
                code=WS_CLOSE_IDLE_TIMEOUT_CODE, reason=WS_CLOSE_IDLE_TIMEOUT_REASON
            )
        except Exception:
            # Connexion déjà morte côté réseau : rien à fermer.
            logger.debug(
                "WebSocket already closed when expiring idle connection",
                extra={"channel": channel},
            )
        raise HeartbeatExpiredError(channel) from None


async def periodic_ping(websocket: WebSocket, channel: str) -> None:
    """Émet un ping serveur périodique (coroutine longue durée).

    Même mécanique que l'ancien heartbeat inline de ``general.py`` :
    à exécuter via ``asyncio.create_task`` et annuler à la déconnexion
    (``CancelledError`` absorbé silencieusement). L'intervalle est
    ``ws_heartbeat_interval_seconds``.

    Args:
        websocket: Connexion WebSocket active.
        channel: Nom du canal (pour les logs uniquement).
    """
    interval = max(1, settings.ws_heartbeat_interval_seconds)
    try:
        while True:
            await asyncio.sleep(interval)
            await websocket.send_json(
                {"type": "ping", "timestamp": datetime.utcnow().isoformat()}
            )
    except asyncio.CancelledError:
        pass  # Annulation normale à la déconnexion du canal
    except Exception as e:
        # Envoi impossible : la connexion est morte — la boucle de réception
        # du canal constatera la déconnexion de son côté (log debug ici).
        logger.debug("Heartbeat periodic ping failed on channel %s: %s", channel, e)
