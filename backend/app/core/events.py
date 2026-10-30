"""Bus d'événements canonique WindFlow (STORY-162 — P2-2, arbitrage F6).

Interface unique ``Bus`` + nomenclature canonique des 18 événements de la
spec 11 (``11-plugins.md`` § Liste canonique) avec deux implémentations
interchangeables :

- ``InMemoryEventBus`` : dispatch local ``asyncio`` — mode léger par
  défaut (RPi, dev, tests) ; comportement identique à l'ancien
  ``EventBus`` (non-régression pont WebSocket / scheduler) ;
- ``RedisPubSubEventBus`` : dispatch local **+** diffusion Redis Pub/Sub
  sur le canal unique ``windflow:events`` (mode standard multi-instances)
  — activée quand ``cache_url`` est configuré et Redis joignable ;
  échec Redis → log warning (une fois par épisode) + dispatch local
  intact (résilience, pattern ``RedisRoleCache`` de ``core/cache.py``).

Hors périmètre assumé (arbitrage F6) : Redis **Streams**, replay /
event-sourcing — l'ancienne classe ``EventStore`` et ``replay_events``
ont été supprimés (aucune référence hors module, constat analyse).

Nomenclature (miroir exact de la spec 11) :
``container.created|started|stopped|removed``,
``stack.deployed|updated|removed``, ``machine.created|started|stopped``,
``deployment.started|succeeded|failed``, ``host.added|removed|offline``,
``plugin.installed|removed``. Les événements ``host.*`` remplacent les
anciens ``target.*`` (alias historiques, ``LEGACY_EVENT_ALIASES``) ;
``deployment.succeeded`` est la forme canonique (jamais
``deployment.completed``). Les domaines extra-canoniques existants
(``organization.*``, ``user.*``, ``system.*``, sécurité TOFU…) restent
émis mais clairement séparés de la liste canonique (pas de silence
métier). ``machine.*`` sont définis **sans émetteur** (Roadmap VMs).

Sécurité (rules 40) : les payloads d'événements ne contiennent jamais de
secrets (IDs/noms/statuts uniquement) ; l'URL Redis n'est jamais loggée
avec ses credentials (masquage ``_safe_redis_url``) ; l'émission est
best-effort côté émetteurs et n'altère jamais les réponses API.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol
from uuid import UUID, uuid4

from .exceptions import InvalidEventTypeNameError

logger = logging.getLogger("windflow.events")

# Import conditionnel de redis.asyncio (le mode léger n'exige pas Redis)
try:  # pragma: no cover - couvert indirectement selon l'environnement
    import redis.asyncio as aioredis

    REDIS_AVAILABLE: bool = True
except ImportError:  # pragma: no cover
    aioredis = None  # type: ignore[assignment]
    REDIS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Référentiel canonique des événements (STORY-162 — spec 11, liste unique)
# ---------------------------------------------------------------------------


class EventType(str, Enum):
    """Types d'événements système — référentiel unique.

    Blocs :

    1. **Canoniques spec 11** (18 membres exacts — voir
       ``CANONICAL_EVENT_NAMES``) : l'intégralité de la liste canonique
       de la spec ; ``machine.*`` n'ont pas encore d'émetteur (Roadmap
       VMs — définis pour le contrat, pas un silence métier) ;
    2. **Extra-canoniques conservés** : émis par WindFlow mais hors
       liste spec 11 — conservés explicitement (pas de silence métier),
       non diffusés sur le pont WebSocket canonique.
    """

    # ── Canoniques spec 11 ─────────────────────────────────────────────
    # container.* (émetteurs : api/v1/docker.py)
    CONTAINER_CREATED = "container.created"
    CONTAINER_STARTED = "container.started"
    CONTAINER_STOPPED = "container.stopped"
    CONTAINER_REMOVED = "container.removed"

    # stack.* (émetteurs : deployment_service — stack.deployed au succès
    # d'un déploiement de stack ; stack.updated/removed définis)
    STACK_DEPLOYED = "stack.deployed"
    STACK_UPDATED = "stack.updated"
    STACK_REMOVED = "stack.removed"

    # machine.* — définis SANS émetteur (Roadmap VMs, documenté)
    MACHINE_CREATED = "machine.created"
    MACHINE_STARTED = "machine.started"
    MACHINE_STOPPED = "machine.stopped"

    # deployment.* (émetteurs : deployment_events — deployment.succeeded
    # est LA forme canonique, jamais deployment.completed)
    DEPLOYMENT_STARTED = "deployment.started"
    DEPLOYMENT_SUCCEEDED = "deployment.succeeded"
    DEPLOYMENT_FAILED = "deployment.failed"

    # host.* (émetteurs : hosts/crud.py + health check périodique —
    # STORY-166.2 : surface canonique /api/v1/hosts, alias /targets
    # déprécié pour la transition)
    HOST_ADDED = "host.added"
    HOST_REMOVED = "host.removed"
    HOST_OFFLINE = "host.offline"

    # plugin.* (émetteurs : plugin_manager_service)
    PLUGIN_INSTALLED = "plugin.installed"
    PLUGIN_REMOVED = "plugin.removed"

    # ── Extra-canoniques conservés (émis, hors liste spec 11) ──────────
    # Déploiement — granularité lifecycle au-delà du canon
    DEPLOYMENT_CREATED = "deployment.created"  # création de la définition
    DEPLOYMENT_ROLLED_BACK = "deployment.rollback"

    # Sécurité TOFU empreintes SSH d'hôte (spec 15) — extra-canoniques :
    # ACCEPTED : acceptation explicite via API (STORY-131.2) ;
    # PENDING : empreinte capturée en session STRICT bloquée (131.3) ;
    # DIVERGENCE : empreinte divergente — alerte MITM potentielle (131.3).
    HOST_SSH_FINGERPRINT_ACCEPTED = "host.ssh_fingerprint_accepted"
    HOST_SSH_FINGERPRINT_PENDING = "host.ssh_fingerprint_pending"
    HOST_SSH_FINGERPRINT_DIVERGENCE = "host.ssh_fingerprint_divergence"

    # Stack — granularité de définition (≠ déploiement)
    STACK_CREATED = "stack.created"

    # Organisation / utilisateur
    ORGANIZATION_CREATED = "organization.created"
    ORGANIZATION_UPDATED = "organization.updated"
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"

    # Plugin — granularité lifecycle au-delà du canon
    PLUGIN_INSTALLING = "plugin.installing"
    PLUGIN_UPDATED = "plugin.updated"
    PLUGIN_CONFIGURED = "plugin.configured"
    PLUGIN_ERROR = "plugin.error"

    # Système
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"


#: Les 18 valeurs canoniques exactes de la spec 11 (référence unique).
CANONICAL_EVENT_NAMES: frozenset[str] = frozenset(
    {
        "container.created",
        "container.started",
        "container.stopped",
        "container.removed",
        "stack.deployed",
        "stack.updated",
        "stack.removed",
        "machine.created",
        "machine.started",
        "machine.stopped",
        "deployment.started",
        "deployment.succeeded",
        "deployment.failed",
        "host.added",
        "host.removed",
        "host.offline",
        "plugin.installed",
        "plugin.removed",
    }
)

#: Alias historiques → canonique (table de correspondance ancien→nouveau,
#: miroir documenté dans docs/technical_specs/EVENT-BUS.md). Utilisés par
#: la résolution défensive du scheduler (schéma, service, triggers) et la
#: data migration Alembic des ``scheduled_tasks.event_name`` stockés.
#: ``target.updated`` n'a jamais été émis et n'a pas d'équivalent host.*
#: — sa clé est conservée pour traduire de façon déterministe toute
#: valeur legacy éventuellement stockée (robustesse).
LEGACY_EVENT_ALIASES: Dict[str, str] = {
    "deployment.completed": "deployment.succeeded",
    "target.created": "host.added",
    "target.updated": "host.offline",
    "target.deleted": "host.removed",
    "target.health_check": "host.offline",
    "stack.deleted": "stack.removed",
    "plugin.uninstalled": "plugin.removed",
}


def resolve_event_name(raw: str) -> str:
    """Résout un nom d'événement vers sa forme canonique.

    Défense en profondeur : les valeurs legacy stockées (ex.
    ``deployment.completed``) sont traduites vers le canonique spec 11 ;
    un nom déjà canonique est retourné inchangé.

    Args:
        raw: Nom d'événement candidat (canonique, alias ou inconnu).

    Returns:
        Le nom canonique si ``raw`` est un alias ou un membre canonique ;
        ``raw`` inchangé sinon (le contrôle d'appartenance à ``EventType``
        reste à la charge de l'appelant).
    """
    return LEGACY_EVENT_ALIASES.get(raw, raw)


def is_canonical(value: str) -> bool:
    """Retourne True si ``value`` fait partie de la liste canonique spec 11."""
    return value in CANONICAL_EVENT_NAMES


# ---------------------------------------------------------------------------
# Enveloppe d'événement (réutilisée telle quelle — transport JSON-safe)
# ---------------------------------------------------------------------------


@dataclass
class Event:
    """Événement immuable transporté sur le bus (sérialisable JSON).

    Représente un fait qui s'est produit dans le système ; les payloads
    ne contiennent jamais de secrets (rules 40 — IDs/noms/statuts).
    """

    event_id: UUID = field(default_factory=uuid4)
    event_type: EventType = EventType.SYSTEM_ERROR
    aggregate_id: Optional[UUID] = None
    aggregate_type: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    user_id: Optional[UUID] = None

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'événement en dictionnaire JSON-safe."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "aggregate_id": str(self.aggregate_id) if self.aggregate_id else None,
            "aggregate_type": self.aggregate_type,
            "payload": self.payload,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "user_id": str(self.user_id) if self.user_id else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Désérialise un événement depuis un dictionnaire."""
        return cls(
            event_id=UUID(data["event_id"]),
            event_type=EventType(data["event_type"]),
            aggregate_id=(
                UUID(data["aggregate_id"]) if data.get("aggregate_id") else None
            ),
            aggregate_type=data.get("aggregate_type"),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            version=data.get("version", 1),
            user_id=UUID(data["user_id"]) if data.get("user_id") else None,
        )


EventHandler = Callable[[Event], Awaitable[None]]


# ---------------------------------------------------------------------------
# Interface canonique Bus (STORY-162 — point d'entrée des plugins, 163)
# ---------------------------------------------------------------------------


class Bus(Protocol):
    """Interface canonique du bus d'événements (protocol typing).

    Contrat stable exposé aux plugins (STORY-163) et aux composants
    internes : deux implémentations interchangeables (in-memory léger /
    Redis Pub/Sub standard) derrière la même signature. ``emit`` accepte
    exclusivement des :class:`EventType` — une valeur étrangère lève
    :class:`InvalidEventTypeNameError` (plus de réencapsulation silencieuse
    en ``system.error``, fragilité corrigée — STORY-162 AC 4).
    """

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Enregistre un handler async pour un type d'événement."""
        ...

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Désenregistre un handler."""
        ...

    async def publish(self, event: Event) -> None:
        """Publie un événement aux handlers locaux (+ transport si configuré)."""
        ...

    async def emit(self, event_type: EventType, event_data: Dict[str, Any]) -> None:
        """Crée un ``Event`` depuis des données brutes et le publie."""
        ...

    async def start(self) -> None:
        """Démarre le bus (connexion transport, tâche subscriber)."""
        ...

    async def stop(self) -> None:
        """Arrête le bus proprement (annulation tâche, fermeture transport)."""
        ...


class InMemoryEventBus:
    """Bus d'événements en mémoire — mode léger par défaut.

    Pattern Observer : distribution aux handlers enregistrés ; un handler
    qui lève n'interrompt jamais les autres (isolation d'erreurs — le
    ``publish`` ne propage jamais l'exception d'un handler).

    Sûr en event loop unique (asyncio) : les mutations de ``_handlers``
    se font sans ``await`` intermédiaire (même garde-fou que
    ``MemoryRoleCache``).
    """

    def __init__(self) -> None:
        self._handlers: Dict[EventType, List[EventHandler]] = {}

    # -- Cycle de vie : no-ops (pas de transport) ------------------------

    async def start(self) -> None:
        """No-op — le bus mémoire n'a pas de transport à démarrer."""

    async def stop(self) -> None:
        """No-op — le bus mémoire n'a pas de transport à arrêter."""

    # -- Abonnements ------------------------------------------------------

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Enregistre un handler pour un type d'événement.

        Args:
            event_type: Type d'événement à écouter.
            handler: Fonction async à appeler lors de l'événement.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug("Handler registered for %s", event_type)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Désenregistre un handler.

        Args:
            event_type: Type d'événement.
            handler: Handler à retirer.
        """
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)
            logger.debug("Handler unregistered for %s", event_type)

    # -- Publication -------------------------------------------------------

    async def publish(self, event: Event) -> None:
        """Publie un événement à tous les handlers enregistrés.

        Args:
            event: Événement à publier.
        """
        logger.info(
            "Publishing event: %s (id=%s)",
            event.event_type.value,
            event.event_id,
        )
        await self._dispatch_local(event)

    async def _dispatch_local(self, event: Event) -> None:
        """Distribue l'événement aux handlers locaux (isolation d'erreurs)."""
        handlers = list(self._handlers.get(event.event_type, []))
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    "Error in event handler for %s: %s",
                    event.event_type.value,
                    e,
                    exc_info=True,
                )
                # Ne pas bloquer les autres handlers en cas d'erreur

    async def emit(self, event_type: EventType, event_data: Dict[str, Any]) -> None:
        """Crée un ``Event`` depuis des données et le publie.

        Args:
            event_type: Type d'événement — DOIT être un :class:`EventType`
                (une valeur étrangère, ex. un ``WebSocketEventType``, lève
                ``InvalidEventTypeNameError`` : l'ancienne réencapsulation
                silencieuse en ``system.error`` est supprimée, AC 4).
            event_data: Données de l'événement (payload sans secret).

        Raises:
            InvalidEventTypeNameError: Si ``event_type`` n'est pas un
                membre de :class:`EventType`.
        """
        if not isinstance(event_type, EventType):
            raise InvalidEventTypeNameError(
                "event_type must be an EventType member, got "
                f"{type(event_type).__name__}: {event_type!r}",
                details={"received": str(event_type)},
            )
        event = Event(event_type=event_type, payload=event_data)
        await self.publish(event)

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du bus d'événements."""
        return {
            "implementation": type(self).__name__,
            "handlers_count": {
                event_type.value: len(handlers)
                for event_type, handlers in self._handlers.items()
            },
            "total_handlers": sum(len(h) for h in self._handlers.values()),
        }


# Alias de compatibilité transitionnelle (imports existants conservés)
EventBus = InMemoryEventBus


# ---------------------------------------------------------------------------
# Implémentation Redis Pub/Sub (mode standard — activée par cache_url)
# ---------------------------------------------------------------------------

#: Canal unique de diffusion des événements (spec 04 § modes standard).
EVENTS_CHANNEL = "windflow:events"


def _safe_redis_url(url: str) -> str:
    """Masque les credentials d'une URL Redis pour les logs (rules 40).

    Délègue au helper mutualisé ``core/cache.py`` (STORY-168 — une seule
    implémentation du masquage entre bus et cache).
    """
    from .cache import _safe_redis_url as _impl

    return _impl(url)


class RedisPubSubEventBus(InMemoryEventBus):
    """Bus d'événements Redis Pub/Sub — dispatch local + diffusion multi-instances.

    Hérite du dispatch in-memory (les handlers locaux sont appelés dans
    tous les cas) et ajoute :

    - ``publish()`` → ``PUBLISH`` JSON (``Event.to_dict()`` + champ
      ``instance_id`` identifiant l'instance émettrice) sur le canal
      ``windflow:events`` ;
    - ``start()`` → tâche subscriber dédiée (``pubsub.subscribe`` +
      boucle ``listen``) qui re-dispatche **localement** les messages
      des **autres** instances (filtrage ``instance_id`` — jamais de
      double dispatch de ses propres événements) ;
    - échec Redis → log warning **une fois par épisode** (flag
      ``_warned_publish`` réinitialisé au succès) + dispatch local
      intact (résilience) ;
    - ``stop()`` → annulation propre de la tâche + fermeture pubsub et
      client (pattern cleanup lifespan).

    Le client ``redis.asyncio`` est **injecté** (tests : ``AsyncMock``).
    """

    def __init__(self, client: Any) -> None:
        super().__init__()
        self._redis = client
        self.instance_id: str = str(uuid4())
        self._subscriber_task: Optional[asyncio.Task[None]] = None
        self._pubsub: Any = None
        self._warned_publish = False

    async def start(self) -> None:
        """Démarre la tâche subscriber (idempotent)."""
        if self._subscriber_task is not None:
            return
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(EVENTS_CHANNEL)
        self._subscriber_task = asyncio.create_task(
            self._subscriber_loop(), name="windflow-event-bus-subscriber"
        )
        logger.info(
            "Event bus: Redis Pub/Sub subscriber started (channel=%s)",
            EVENTS_CHANNEL,
        )

    async def stop(self) -> None:
        """Arrête la tâche subscriber et ferme le transport proprement."""
        task = self._subscriber_task
        self._subscriber_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        pubsub = self._pubsub
        self._pubsub = None
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(EVENTS_CHANNEL)
                await pubsub.close()
            except Exception as exc:  # pragma: no cover - défense shutdown
                logger.warning("Event bus: pubsub close failed: %s", exc)
        try:
            await self._redis.close()
        except Exception as exc:  # pragma: no cover - défense shutdown
            logger.warning("Event bus: redis client close failed: %s", exc)
        logger.info("Event bus: Redis Pub/Sub stopped")

    async def publish(self, event: Event) -> None:
        """Dispatch local + ``PUBLISH`` sur ``windflow:events`` (best-effort)."""
        await self._dispatch_local(event)
        await self._publish_to_redis(event)

    async def _publish_to_redis(self, event: Event) -> None:
        """Publie l'événement sur le canal (échec → warning unique, jamais levé)."""
        message = json.dumps({**event.to_dict(), "instance_id": self.instance_id})
        try:
            await self._redis.publish(EVENTS_CHANNEL, message)
            self._warned_publish = False
        except Exception as exc:
            if not self._warned_publish:
                logger.warning(
                    "Event bus: Redis PUBLISH failed (%s) — local dispatch "
                    "only (warning logged once per episode)",
                    exc,
                )
                self._warned_publish = True

    async def _subscriber_loop(self) -> None:
        """Boucle d'écoute : re-dispatch local des messages des autres instances.

        Une erreur de boucle (connexion perdue…) loggée une fois puis
        termine la tâche — le dispatch local reste intact (résilience).
        """
        try:
            await self._consume_messages()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "Event bus: Redis subscriber stopped after failure (%s) — "
                "local dispatch only",
                exc,
            )

    async def _consume_messages(self) -> None:
        """Consomme les messages du pubsub et re-dispatche les externes."""
        if self._pubsub is None:  # pragma: no cover - défense
            return
        async for raw in self._pubsub.listen():
            if self._subscriber_task is None:
                break  # arrêt demandé pendant l'écoute
            message = self._decode_message(raw)
            if message is None:
                continue
            if message.get("instance_id") == self.instance_id:
                continue  # écho de soi-même → pas de double dispatch
            await self._dispatch_remote_message(message)

    async def _dispatch_remote_message(self, message: Dict[str, Any]) -> None:
        """Re-dispatche localement un événement reçu d'une autre instance."""
        try:
            event = Event.from_dict(message)
            await self._dispatch_local(event)
        except Exception as exc:
            logger.warning("Event bus: ignoring malformed remote event (%s)", exc)

    @staticmethod
    def _decode_message(raw: Any) -> Optional[Dict[str, Any]]:
        """Décode un message pubsub brut en dict (None si non-donnée/invalide)."""
        if not isinstance(raw, dict) or raw.get("type") != "message":
            return None
        data = raw.get("data")
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        if not isinstance(data, str):
            return None
        try:
            decoded = json.loads(data)
        except (TypeError, ValueError):
            return None
        return decoded if isinstance(decoded, dict) else None


# ---------------------------------------------------------------------------
# Factory singleton (pattern get_role_cache / reset_role_cache)
# ---------------------------------------------------------------------------

# Instance globale du bus d'événements (résolution paresseuse)
_event_bus: Optional[Bus] = None


async def init_event_bus() -> Bus:
    """Factory singleton du bus d'événements (mémosée).

    Choix de l'implémentation :

    - ``RedisPubSubEventBus`` si le package ``redis`` est importable,
      qu'une URL est configurée (``settings.cache_url`` — mode standard)
      **et** que le ``ping`` réussit ;
    - ``InMemoryEventBus`` sinon (mode léger — **aucune tentative de
      connexion**, un seul log info).

    Returns:
        Instance singleton implémentant ``Bus`` (déjà démarrée).
    """
    global _event_bus
    if _event_bus is not None:
        return _event_bus

    from ..config import settings

    cache_url = settings.cache_url
    if REDIS_AVAILABLE and cache_url:
        try:
            client = aioredis.from_url(cache_url)
            await client.ping()
            bus: Bus = RedisPubSubEventBus(client)
            await bus.start()
            _event_bus = bus
            logger.info(
                "Event bus: Redis Pub/Sub actif (mode standard, %s)",
                _safe_redis_url(cache_url),
            )
            return _event_bus
        except Exception as exc:
            logger.warning(
                "Event bus: Redis indisponible (%s) — mode léger in-memory", exc
            )
    else:
        logger.info(
            "Event bus: mode léger in-memory (cache_url non configuré — "
            "dispatch process-local uniquement)"
        )

    _event_bus = InMemoryEventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Réinitialise le singleton de la factory (utilisé par les tests)."""
    global _event_bus
    _event_bus = None


def get_event_bus() -> Bus:
    """Retourne le bus actif (sans l'initialiser — compat imports module).

    Le bus réel est initialisé au lifespan (``init_event_bus`` **avant**
    ``setup_event_bridge``) ; avant startup ou en dehors d'une app
    FastAPI (tests unitaires), retourne le mode in-memory par défaut.

    Attention : après un ``reset_event_bus()`` (tests), cette fonction
    recrée une instance in-memory fraîche — l'ancienne instance (et ses
    abonnés) est perdue, ce qui est le comportement attendu des tests.
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = InMemoryEventBus()
    return _event_bus


async def shutdown_event_bus() -> None:
    """Arrête le bus actif s'il possède un transport (shutdown lifespan)."""
    global _event_bus
    if _event_bus is None:
        return
    try:
        await _event_bus.stop()
    except Exception as exc:  # pragma: no cover - défense shutdown
        logger.warning("Event bus: stop failed: %s", exc)
    _event_bus = None


async def publish_event(event: Event) -> None:
    """Raccourci pour publier un événement sur le bus actif."""
    bus = get_event_bus()
    await bus.publish(event)


# Instance globale du bus d'événements pour import direct.
# Cette instance est créée au premier import du module (mode in-memory ;
# remplacée par le bus actif au lifespan via init_event_bus).
event_bus: Bus = get_event_bus()
