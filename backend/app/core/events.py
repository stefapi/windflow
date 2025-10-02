"""
Infrastructure Event-Driven pour WindFlow.

Implémente Event Sourcing, CQRS pattern, et Pub/Sub messaging
avec support Redis Streams (optionnel).
"""

from typing import Optional, Dict, Any, List, Callable, Awaitable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import json
import logging
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types d'événements système."""
    # Déploiement
    DEPLOYMENT_CREATED = "deployment.created"
    DEPLOYMENT_STARTED = "deployment.started"
    DEPLOYMENT_COMPLETED = "deployment.completed"
    DEPLOYMENT_FAILED = "deployment.failed"
    DEPLOYMENT_ROLLED_BACK = "deployment.rollback"

    # Target
    TARGET_CREATED = "target.created"
    TARGET_UPDATED = "target.updated"
    TARGET_DELETED = "target.deleted"
    TARGET_HEALTH_CHECK = "target.health_check"

    # Stack
    STACK_CREATED = "stack.created"
    STACK_UPDATED = "stack.updated"
    STACK_DELETED = "stack.deleted"

    # Organisation
    ORGANIZATION_CREATED = "organization.created"
    ORGANIZATION_UPDATED = "organization.updated"

    # User
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"

    # Système
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"


@dataclass
class Event:
    """
    Événement immutable pour Event Sourcing.

    Représente un fait qui s'est produit dans le système.
    """
    event_id: UUID = field(default_factory=uuid4)
    event_type: EventType = EventType.SYSTEM_ERROR
    aggregate_id: Optional[UUID] = None
    aggregate_type: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    user_id: Optional[UUID] = None

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'événement en dictionnaire."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "aggregate_id": str(self.aggregate_id) if self.aggregate_id else None,
            "aggregate_type": self.aggregate_type,
            "payload": self.payload,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "user_id": str(self.user_id) if self.user_id else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Désérialise un événement depuis un dictionnaire."""
        return cls(
            event_id=UUID(data["event_id"]),
            event_type=EventType(data["event_type"]),
            aggregate_id=UUID(data["aggregate_id"]) if data.get("aggregate_id") else None,
            aggregate_type=data.get("aggregate_type"),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            version=data.get("version", 1),
            user_id=UUID(data["user_id"]) if data.get("user_id") else None
        )


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """
    Bus d'événements pour pub/sub messaging.

    Implémente le pattern Observer pour la distribution d'événements
    aux handlers enregistrés.
    """

    def __init__(self, redis_enabled: bool = False, redis_url: Optional[str] = None):
        """
        Initialise le bus d'événements.

        Args:
            redis_enabled: Active Redis Streams pour la persistence
            redis_url: URL de connexion Redis (optionnel)
        """
        self.redis_enabled = redis_enabled
        self.redis_url = redis_url
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._redis_client = None

        if redis_enabled and redis_url:
            self._init_redis()
        else:
            logger.info("EventBus initialized without Redis (in-memory only)")

    def _init_redis(self) -> None:
        """Initialise la connexion Redis pour les Streams."""
        try:
            # TODO: Initialiser le client Redis quand la dépendance sera ajoutée
            # import redis.asyncio as aioredis
            # self._redis_client = aioredis.from_url(self.redis_url)
            logger.info(f"Redis Streams initialized at {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            self.redis_enabled = False

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        Enregistre un handler pour un type d'événement.

        Args:
            event_type: Type d'événement à écouter
            handler: Fonction async à appeler lors de l'événement
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        self._handlers[event_type].append(handler)
        logger.debug(f"Handler registered for {event_type}")

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        Désenregistre un handler.

        Args:
            event_type: Type d'événement
            handler: Handler à retirer
        """
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)
            logger.debug(f"Handler unregistered for {event_type}")

    async def publish(self, event: Event) -> None:
        """
        Publie un événement à tous les handlers enregistrés.

        Args:
            event: Événement à publier
        """
        logger.info(f"Publishing event: {event.event_type} (id={event.event_id})")

        # Persistence dans Redis Streams si activé
        if self.redis_enabled and self._redis_client:
            await self._publish_to_redis(event)

        # Distribution aux handlers locaux
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}", exc_info=True)
                # Ne pas bloquer les autres handlers en cas d'erreur

    async def _publish_to_redis(self, event: Event) -> None:
        """Publie l'événement dans Redis Streams."""
        try:
            # TODO: Implémenter avec Redis Streams
            # stream_name = f"windflow:events:{event.event_type.value}"
            # await self._redis_client.xadd(
            #     stream_name,
            #     event.to_dict(),
            #     maxlen=10000  # Limite de rétention
            # )
            logger.debug(f"Event published to Redis: {event.event_id}")
        except Exception as e:
            logger.error(f"Failed to publish to Redis: {e}")

    async def replay_events(
        self,
        aggregate_id: UUID,
        event_types: Optional[List[EventType]] = None
    ) -> List[Event]:
        """
        Rejoue les événements pour un agrégat (Event Sourcing).

        Args:
            aggregate_id: ID de l'agrégat
            event_types: Types d'événements à rejouer (optionnel)

        Returns:
            Liste d'événements dans l'ordre chronologique
        """
        if not self.redis_enabled:
            logger.warning("Event replay requires Redis Streams")
            return []

        # TODO: Implémenter la lecture depuis Redis Streams
        logger.info(f"Replaying events for aggregate {aggregate_id}")
        return []

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du bus d'événements."""
        return {
            "redis_enabled": self.redis_enabled,
            "handlers_count": {
                event_type.value: len(handlers)
                for event_type, handlers in self._handlers.items()
            },
            "total_handlers": sum(len(h) for h in self._handlers.values())
        }


class EventStore:
    """
    Store pour la persistence des événements (Event Sourcing).

    Stocke tous les événements pour permettre la reconstruction
    de l'état des agrégats.
    """

    def __init__(
        self,
        redis_enabled: bool = False,
        redis_url: Optional[str] = None
    ):
        """
        Initialise l'Event Store.

        Args:
            redis_enabled: Active Redis pour la persistence
            redis_url: URL de connexion Redis
        """
        self.redis_enabled = redis_enabled
        self.redis_url = redis_url
        self._in_memory_store: List[Event] = []
        self._redis_client = None

        if redis_enabled and redis_url:
            self._init_redis()

    def _init_redis(self) -> None:
        """Initialise la connexion Redis."""
        try:
            # TODO: Initialiser Redis client
            logger.info("EventStore initialized with Redis")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            self.redis_enabled = False

    async def append(self, event: Event) -> None:
        """
        Ajoute un événement au store.

        Args:
            event: Événement à persister
        """
        if self.redis_enabled and self._redis_client:
            await self._append_to_redis(event)
        else:
            # Fallback en mémoire
            self._in_memory_store.append(event)

        logger.debug(f"Event appended: {event.event_id}")

    async def _append_to_redis(self, event: Event) -> None:
        """Persiste l'événement dans Redis."""
        # TODO: Implémenter avec Redis
        pass

    async def get_events(
        self,
        aggregate_id: Optional[UUID] = None,
        event_types: Optional[List[EventType]] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Event]:
        """
        Récupère des événements selon des critères.

        Args:
            aggregate_id: Filtrer par agrégat
            event_types: Filtrer par types d'événements
            since: Filtrer par date
            limit: Nombre maximum d'événements

        Returns:
            Liste d'événements filtrés
        """
        if self.redis_enabled:
            return await self._get_from_redis(aggregate_id, event_types, since, limit)
        else:
            return self._get_from_memory(aggregate_id, event_types, since, limit)

    def _get_from_memory(
        self,
        aggregate_id: Optional[UUID],
        event_types: Optional[List[EventType]],
        since: Optional[datetime],
        limit: int
    ) -> List[Event]:
        """Récupère les événements depuis la mémoire."""
        events = self._in_memory_store

        if aggregate_id:
            events = [e for e in events if e.aggregate_id == aggregate_id]

        if event_types:
            events = [e for e in events if e.event_type in event_types]

        if since:
            events = [e for e in events if e.timestamp >= since]

        return events[:limit]

    async def _get_from_redis(
        self,
        aggregate_id: Optional[UUID],
        event_types: Optional[List[EventType]],
        since: Optional[datetime],
        limit: int
    ) -> List[Event]:
        """Récupère les événements depuis Redis."""
        # TODO: Implémenter la lecture depuis Redis
        return []

    async def snapshot(self, aggregate_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Crée un snapshot de l'état d'un agrégat.

        Optimisation pour éviter de rejouer tous les événements.

        Args:
            aggregate_id: ID de l'agrégat

        Returns:
            Snapshot de l'état
        """
        events = await self.get_events(aggregate_id=aggregate_id)

        if not events:
            return None

        # Reconstruction de l'état depuis les événements
        state = {
            "aggregate_id": str(aggregate_id),
            "event_count": len(events),
            "last_event": events[-1].to_dict() if events else None,
            "version": events[-1].version if events else 0
        }

        return state


# Instance globale du bus d'événements
_event_bus: Optional[EventBus] = None


def get_event_bus(
    redis_enabled: bool = False,
    redis_url: Optional[str] = None
) -> EventBus:
    """
    Retourne l'instance globale du bus d'événements (singleton).

    Args:
        redis_enabled: Active Redis Streams
        redis_url: URL Redis

    Returns:
        Instance du EventBus
    """
    global _event_bus

    if _event_bus is None:
        _event_bus = EventBus(redis_enabled, redis_url)

    return _event_bus


async def publish_event(event: Event) -> None:
    """
    Raccourci pour publier un événement.

    Args:
        event: Événement à publier
    """
    bus = get_event_bus()
    await bus.publish(event)
