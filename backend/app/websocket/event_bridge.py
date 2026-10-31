"""Pont EventBus → WebSocket (STORY-162 : mapping canonique étendu).

Ce module transfère les événements du bus canonique vers les clients
WebSocket : chaque **événement canonique** spec 11 est diffusé vers les
abonnés de ``/ws/events`` sous sa **clé canonique** (ex.
``deployment.succeeded`` — spec 09 § WebSocket) ; les événements
``deployment.*`` continuent **aussi** d'être diffusés vers la clé
transport historique ``DEPLOYMENT_STATUS_CHANGED`` pendant la période de
transition frontend (double émission bornée par
``settings.legacy_ws_event_names_enabled``, retrait tracé
STORY-253/254).

Extra-canoniques (``organization.*``, ``user.*``, ``system.*``,
``host.ssh_fingerprint_*``…) : non diffusés (comportement historique
préservé, log debug inchangé). ``DEPLOYMENT_PROGRESS`` (transport WS)
n'est volontairement pas mappé ici — décision portée par STORY-163.

Fragilité corrigée (WEBSOCKET-REAL-TIME §4) : le bus n'accepte plus que
des :class:`EventType` via ``emit`` (erreur explicite
``InvalidEventTypeNameError``) — ce pont s'abonne typée et ne dépend
plus de la réencapsulation ``system.error``.
"""

import logging
from typing import Dict

from ..config import settings
from ..core.events import CANONICAL_EVENT_NAMES, Event, EventType, event_bus
from ..schemas.websocket_events import WebSocketEventType

# STORY-172 (E5/D1) : forwards bus → WS tracés (best-effort).
from .metrics import record_event_dispatch

logger = logging.getLogger(__name__)


# Clé transport WebSocket historique pour les événements de déploiement
# (compat frontend — période d'émission double bornée par le setting).
_LEGACY_DEPLOYMENT_WS_KEY = WebSocketEventType.DEPLOYMENT_STATUS_CHANGED


def _canonical_ws_targets(event: Event) -> list[str]:
    """Clés de diffusion WebSocket pour un événement (canonique d'abord).

    Retourne la liste des clés de souscription ``/ws/events`` vers
    lesquelles diffuser l'événement :

    - l'événement est canonique spec 11 → sa valeur canonique ;
    - c'est un événement ``deployment.*`` (canonique **ou**
      extra-canonique : created/rollback) et la double émission legacy
      est active → la clé historique ``DEPLOYMENT_STATUS_CHANGED`` en
      sus (compat frontend, retrait tracé STORY-253/254) ;
    - extra-canonique non déploiement → liste vide (non diffusé,
      comportement historique préservé).

    Args:
        event: Événement du bus canonique.

    Returns:
        Liste (éventuellement vide) de clés de diffusion.
    """
    value = event.event_type.value
    targets: list[str] = []
    if value in CANONICAL_EVENT_NAMES:
        targets.append(value)
    is_deployment = value.startswith("deployment.")
    if (
        is_deployment
        and settings.legacy_ws_event_names_enabled
        and _LEGACY_DEPLOYMENT_WS_KEY not in targets
    ):
        targets.append(_LEGACY_DEPLOYMENT_WS_KEY)
    return targets


async def websocket_event_handler(event: Event) -> None:
    """Handler qui transfère les événements du bus vers les clients WebSocket.

    Ce handler est enregistré auprès du bus (``setup_event_bridge``) et
    appelé à chaque événement publié : il construit le message WebSocket
    et le diffuse aux abonnés des clés pertinentes (canonique + éventuel
    legacy déploiement).

    Args:
        event: Événement provenant du bus canonique.
    """
    targets = _canonical_ws_targets(event)
    if not targets:
        # Pas de mapping (extra-canonique non déploiement) — comportement
        # historique préservé : skip silencieux, log debug.
        logger.debug("No WebSocket mapping for event type: %s", event.event_type)
        return

    try:
        # Import ici pour éviter la dépendance circulaire
        from .broadcasting import broadcast_to_event_subscribers

        message = {
            "type": event.event_type.value,
            "data": event.payload,
            "timestamp": event.timestamp.isoformat(),
        }

        logger.info(
            "[Event Bridge] forwarding %s → %s (deployment_id: %s)",
            event.event_type.value,
            targets,
            event.payload.get("deployment_id", "N/A"),
        )
        logger.debug("WebSocket message payload: %s", message)

        # Diffusion vers chaque clé pertinente : clé canonique
        # (+ clé legacy déploiement pendant la période de transition).
        for key in targets:
            await broadcast_to_event_subscribers(key, message)

        # STORY-172 : forward réussi tracé (best-effort).
        record_event_dispatch(event.event_type.value, True)
        logger.info("[Event Bridge] event forwarded to broadcast layer")

    except Exception as e:
        logger.error(
            "[Event Bridge] error forwarding event to WebSocket: %s",
            e,
            exc_info=True,
            extra={
                "event_type": event.event_type.value,
                "event_id": str(event.event_id),
            },
        )


def bridged_event_types() -> list[EventType]:
    """Types d'événements abonnés par le pont (canoniques + deployment.*).

    Retourne les membres :class:`EventType` vers lesquels le pont
    s'abonne : tous les canoniques spec 11 **et** les extra-canoniques
    ``deployment.*`` (created/rollback) qui continuent d'être diffusés
    vers la clé legacy ``DEPLOYMENT_STATUS_CHANGED``.
    """
    return [
        member
        for member in EventType
        if member.value in CANONICAL_EVENT_NAMES
        or member.value.startswith("deployment.")
    ]


# Compat : mapping historique EventType → WebSocketEventType (déploiement
# seul). Conservé pour documentation/référence ; le pont n'itère plus
# dessus (diffusion par clé canonique — STORY-162).
EVENT_TYPE_MAPPING: Dict[EventType, WebSocketEventType] = {
    EventType.DEPLOYMENT_CREATED: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
    EventType.DEPLOYMENT_STARTED: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
    EventType.DEPLOYMENT_SUCCEEDED: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
    EventType.DEPLOYMENT_FAILED: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
    EventType.DEPLOYMENT_ROLLED_BACK: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
}


def setup_event_bridge() -> None:
    """Enregistre les handlers pont bus → WebSocket (startup).

    Abonne ``websocket_event_handler`` à chaque type d'événement diffusé
    (canoniques + ``deployment.*``), sans duplication de handler. Doit
    être appelé **après** ``init_event_bus`` (le pont s'abonne au bus
    actif — lifespan).
    """
    registered_count = 0
    for event_type in bridged_event_types():
        event_bus.subscribe(event_type, websocket_event_handler)
        registered_count += 1
        logger.debug("Registered WebSocket bridge for: %s", event_type)

    logger.info(
        "Event bridge initialized: %d event types will be forwarded to "
        "WebSocket clients",
        registered_count,
    )


def teardown_event_bridge() -> None:
    """Désenregistre les handlers (cleanup, shutdown)."""
    for event_type in bridged_event_types():
        try:
            event_bus.unsubscribe(event_type, websocket_event_handler)
        except ValueError:  # déjà désabonné — idempotence
            pass

    logger.info("Event bridge handlers unregistered")
