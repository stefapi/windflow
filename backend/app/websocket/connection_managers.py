"""
Gestionnaires de connexions WebSocket.

Ce module contient toutes les classes de gestion des connexions WebSocket,
extraites de api/v1/websockets.py pour une meilleure organisation et maintenabilité.

Classes:
    BroadcastManager: Logique commune de broadcast WebSocket
    ConnectionManager: Gestion des connexions par déploiement
    UserConnectionManager: Gestion des connexions par utilisateur
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Set

from fastapi import WebSocket

# STORY-172 (E5/D1) : câblage des métriques WebSocket — best-effort : chaque
# appel est protégé au point d'appel (jamais casser une connexion ou un
# broadcast pour une métrique).
from .metrics import (
    record_broadcast,
    record_connection,
    record_event_dispatch,
    record_message_sent,
)


def _safe(record_fn, *args, **kwargs) -> None:
    """Invoque un helper de métrique sans jamais lever (best-effort)."""
    try:
        record_fn(*args, **kwargs)
    except Exception:  # pragma: no cover — défense en profondeur
        logger.exception("Métrique WebSocket impossible (ignorée)")


logger = logging.getLogger(__name__)


# ============================================================================
# BROADCAST MANAGER - Logique commune de broadcast
# ============================================================================


class BroadcastManager:
    """
    Classe de base fournissant la logique commune de broadcast WebSocket.

    Cette classe factorise le code dupliqué entre ConnectionManager et
    UserConnectionManager pour l'envoi de messages aux WebSocket clients.
    """

    @staticmethod
    async def _broadcast_to_connections(
        connections: Set[WebSocket], message: dict, context_description: str = ""
    ) -> tuple[int, Set[WebSocket]]:
        """
        Logique commune pour broadcaster un message à un ensemble de connexions.

        Args:
            connections: Ensemble de connexions WebSocket
            message: Message JSON à envoyer
            context_description: Description du contexte pour les logs

        Returns:
            Tuple (nombre_envois_reussis, connexions_mortes)
        """
        sent_count = 0
        disconnected = set()

        for websocket in connections.copy():
            try:
                await websocket.send_json(message)
                sent_count += 1
                # STORY-172 : chaque envoi réel est compté (succès).
                _safe(
                    record_message_sent,
                    str(message.get("type", "unknown")),
                    True,
                )
            except Exception as e:
                logger.error(
                    f"Error broadcasting to WebSocket {context_description}: {e}"
                )
                disconnected.add(websocket)
                # STORY-172 : l'échec d'envoi est compté (erreur).
                _safe(
                    record_message_sent,
                    str(message.get("type", "unknown")),
                    False,
                )

        return sent_count, disconnected

    @staticmethod
    def _log_broadcast(
        message: dict, sent_count: int, total_count: int, context: str, icon: str = "📡"
    ) -> None:
        """
        Log standardisé pour les broadcasts.

        Args:
            message: Message envoyé
            sent_count: Nombre de clients ayant reçu le message
            total_count: Nombre total de clients potentiels
            context: Description du contexte (deployment: xxx, user: yyy, etc.)
            icon: Emoji pour le type de broadcast (📡 ou 🔌)
        """
        if sent_count > 0:
            # Log debug pour détails, info uniquement pour événements importants
            message_type = message.get("type", "unknown")
            if message_type in [
                "DEPLOYMENT_STATUS_CHANGED",
                "DEPLOYMENT_COMPLETE",
                "AUTH_LOGIN_SUCCESS",
            ]:
                logger.info(
                    f"{icon} WebSocket broadcast: {message_type} "
                    f"→ {sent_count}/{total_count} client(s) ({context})"
                )
            else:
                logger.debug(
                    f"{icon} WebSocket broadcast: {message_type} "
                    f"→ {sent_count}/{total_count} client(s) ({context})"
                )
        elif total_count > 0:
            logger.debug(
                f"{icon} No active connections despite {total_count} potential target(s) ({context})"
            )


# ============================================================================
# CONNECTION MANAGER - Gestion des connexions par déploiement
# ============================================================================


class ConnectionManager:
    """
    Gestionnaire de connexions WebSocket par déploiement.

    Gère les connexions WebSocket pour le streaming de logs de déploiement
    en temps réel. Chaque déploiement peut avoir plusieurs clients connectés.
    """

    def __init__(self):
        # deployment_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, deployment_id: str, accept_connection: bool = True
    ):
        """
        Accepte une nouvelle connexion WebSocket.

        Args:
            websocket: Instance de connexion WebSocket
            deployment_id: ID du déploiement concerné
            accept_connection: Si True (défaut), accepte la connexion avant
                l'enregistrement. Passer False lorsque l'endpoint a déjà
                appelé ``websocket.accept()`` (ex: canal ``deployment_logs``,
                qui accepte tôt pour émettre un message d'erreur applicatif
                avant le close 1008) — un second accept ferait échouer la
                connexion (machine à états ASGI de Starlette).

        Returns:
            None. La connexion est enregistrée sous ``deployment_id``.
        """
        if accept_connection:
            await websocket.accept()

        async with self._lock:
            if deployment_id not in self.active_connections:
                self.active_connections[deployment_id] = set()
            self.active_connections[deployment_id].add(websocket)

        # STORY-172 : gauge + compteur de connexions (best-effort).
        _safe(record_connection, "deployment", "connected")
        logger.info(f"WebSocket connected for deployment {deployment_id}")

    async def disconnect(self, websocket: WebSocket, deployment_id: str):
        """
        Déconnecte un WebSocket.

        Args:
            websocket: Instance de connexion WebSocket
            deployment_id: ID du déploiement concerné
        """
        async with self._lock:
            if deployment_id in self.active_connections:
                self.active_connections[deployment_id].discard(websocket)

                # Nettoyer si plus aucune connexion
                if not self.active_connections[deployment_id]:
                    del self.active_connections[deployment_id]

        # STORY-172 : gauge + compteur de déconnexions (best-effort).
        _safe(record_connection, "deployment", "disconnected")
        logger.info(f"WebSocket disconnected for deployment {deployment_id}")

    async def broadcast_to_deployment(self, deployment_id: str, message: dict):
        """
        Envoie un message à toutes les connexions d'un déploiement.

        Args:
            deployment_id: ID du déploiement
            message: Message JSON à envoyer
        """
        if deployment_id not in self.active_connections:
            logger.debug(f"📡 No active connections for deployment {deployment_id}")
            return

        connections = self.active_connections[deployment_id]
        connection_count = len(connections)

        # STORY-172 : durée réelle du broadcast + nombre de clients touchés
        # (measure-then-record — sent_count exact, best-effort).
        _broadcast_started = time.monotonic()
        # Utiliser la logique commune de broadcast
        sent_count, disconnected = await BroadcastManager._broadcast_to_connections(
            connections, message, f"deployment {deployment_id}"
        )
        _safe(
            record_broadcast,
            "deployment",
            time.monotonic() - _broadcast_started,
            sent_count,
        )

        # Log standardisé
        BroadcastManager._log_broadcast(
            message, sent_count, connection_count, f"deployment: {deployment_id}"
        )

        # Nettoyer les connexions mortes — même hygiène que disconnect :
        # purge des sockets + suppression de la clé devenue vide (BUG-007).
        # Garde .get() : la clé peut avoir été supprimée par un disconnect
        # concurrent pendant l'envoi (la purge ne doit jamais lever KeyError).
        if disconnected:
            async with self._lock:
                connections = self.active_connections.get(deployment_id)
                if connections is not None:
                    connections.difference_update(disconnected)
                    if not connections:
                        del self.active_connections[deployment_id]


# ============================================================================
# USER CONNECTION MANAGER - Gestion des connexions par utilisateur
# ============================================================================


class UserConnectionManager:
    """
    Gestionnaire de connexions WebSocket par utilisateur.

    Gère les connexions WebSocket générales pour chaque utilisateur,
    permettant les notifications en temps réel et les abonnements
    à différents types d'événements.
    """

    def __init__(self):
        # user_id -> set of WebSocket connections
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        # user_id -> set of subscribed event types
        self.user_subscriptions: Dict[str, Set[str]] = {}
        # deployment_id -> set of user_ids subscribed to deployment logs
        self.deployment_subscribers: Dict[str, Set[str]] = {}
        # user_id -> PluginContext for dispatching events to plugins
        self.user_plugin_contexts: Dict[str, "PluginContext"] = {}  # noqa: F821
        self._lock = asyncio.Lock()

    async def add_connection(
        self,
        user_id: str,
        websocket: WebSocket,
        context: Optional["PluginContext"] = None,  # type: ignore[name-defined]  # noqa: F821
    ):
        """
        Ajoute une connexion utilisateur.

        Args:
            user_id: ID de l'utilisateur
            websocket: Instance de connexion WebSocket
            context: Contexte du plugin (optionnel)
        """
        async with self._lock:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(websocket)

            # Stocker le contexte du plugin pour ce user (si fourni)
            if context and user_id not in self.user_plugin_contexts:
                self.user_plugin_contexts[user_id] = context

        # STORY-172 : gauge + compteur de connexions utilisateur.
        _safe(record_connection, "user", "connected")

    async def remove_connection(self, user_id: str, websocket: WebSocket):
        """
        Supprime une connexion utilisateur.

        Args:
            user_id: ID de l'utilisateur
            websocket: Instance de connexion WebSocket
        """
        async with self._lock:
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(websocket)

                # Nettoyer si plus aucune connexion
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
                    # Nettoyer aussi les abonnements
                    if user_id in self.user_subscriptions:
                        del self.user_subscriptions[user_id]
                    # Nettoyer le contexte du plugin
                    if user_id in self.user_plugin_contexts:
                        del self.user_plugin_contexts[user_id]

        # STORY-172 : gauge + compteur de déconnexions utilisateur.
        _safe(record_connection, "user", "disconnected")

    async def subscribe_to_event(
        self, user_id: str, event_type: str, websocket: WebSocket
    ):
        """
        Abonne un utilisateur à un type d'événement.

        Args:
            user_id: ID de l'utilisateur
            event_type: Type d'événement (WebSocketEventType)
            websocket: Instance de connexion WebSocket
        """
        async with self._lock:
            if user_id not in self.user_subscriptions:
                self.user_subscriptions[user_id] = set()
            self.user_subscriptions[user_id].add(event_type)

    async def unsubscribe_from_event(
        self, user_id: str, event_type: str, websocket: WebSocket
    ):
        """
        Désabonne un utilisateur d'un type d'événement.

        Args:
            user_id: ID de l'utilisateur
            event_type: Type d'événement (WebSocketEventType)
            websocket: Instance de connexion WebSocket
        """
        async with self._lock:
            if user_id in self.user_subscriptions:
                self.user_subscriptions[user_id].discard(event_type)

                # Nettoyer si plus d'abonnements
                if not self.user_subscriptions[user_id]:
                    del self.user_subscriptions[user_id]

    async def subscribe_to_deployment_logs(
        self, user_id: str, deployment_id: str, websocket: WebSocket
    ):
        """
        Abonne un utilisateur aux logs d'un déploiement.

        Args:
            user_id: ID de l'utilisateur
            deployment_id: ID du déploiement
            websocket: Instance de connexion WebSocket
        """
        async with self._lock:
            if deployment_id not in self.deployment_subscribers:
                self.deployment_subscribers[deployment_id] = set()
            self.deployment_subscribers[deployment_id].add(user_id)

    async def broadcast_to_user(self, user_id: str, message: dict):
        """
        Envoie un message à toutes les connexions d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            message: Message JSON à envoyer
        """
        if user_id not in self.user_connections:
            logger.debug(f"📡 No active connections for user {user_id}")
            return

        connections = self.user_connections[user_id]
        connection_count = len(connections)

        # STORY-172 : durée réelle du broadcast + nombre de clients touchés.
        _broadcast_started = time.monotonic()
        # Utiliser la logique commune de broadcast
        sent_count, disconnected = await BroadcastManager._broadcast_to_connections(
            connections, message, f"user {user_id}"
        )
        _safe(
            record_broadcast,
            "user",
            time.monotonic() - _broadcast_started,
            sent_count,
        )

        # Log standardisé
        BroadcastManager._log_broadcast(
            message, sent_count, connection_count, f"user: {user_id}"
        )

        # Nettoyer les connexions mortes — HORS lock (remove_connection acquiert
        # _lock, qui est non-réentrant : l'appeler sous le lock deadloque).
        # Pattern de broadcast_to_event_subscribers (purge après libération).
        for ws in disconnected:
            await self.remove_connection(user_id, ws)

    async def broadcast_to_event_subscribers(self, event_type: str, message: dict):
        """
        Envoie un message à tous les utilisateurs abonnés à un événement.

        Args:
            event_type: Type d'événement (WebSocketEventType)
            message: Message JSON à envoyer
        """
        # Collecter toutes les connexions des abonnés
        all_connections = set()
        disconnected_users = set()
        subscriber_count = 0

        logger.debug(f"📢 Finding subscribers for event: {event_type}")

        async with self._lock:
            for user_id, subscriptions in self.user_subscriptions.items():
                if event_type in subscriptions:
                    subscriber_count += 1
                    if user_id in self.user_connections:
                        all_connections.update(self.user_connections[user_id])
                        logger.debug(
                            f"Found subscriber: user {user_id} with {len(self.user_connections[user_id])} connection(s)"
                        )

        logger.debug(
            f"📢 Found {subscriber_count} subscriber(s) with {len(all_connections)} total connection(s)"
        )

        # STORY-172 : durée réelle du broadcast + nombre de clients touchés.
        _broadcast_started = time.monotonic()
        # Utiliser la logique commune de broadcast
        sent_count, disconnected = await BroadcastManager._broadcast_to_connections(
            all_connections, message, f"event subscribers for {event_type}"
        )
        _safe(
            record_broadcast,
            "event",
            time.monotonic() - _broadcast_started,
            sent_count,
        )

        # Log standardisé avec info sur les subscribers
        message_type = message.get("type", "unknown")
        if sent_count > 0:
            # Log important uniquement pour certains événements
            if message_type in [
                "DEPLOYMENT_STATUS_CHANGED",
                "DEPLOYMENT_COMPLETE",
                "AUTH_LOGIN_SUCCESS",
            ]:
                logger.info(
                    f"✅ WebSocket broadcast successful: {message_type} "
                    f"→ {sent_count} client(s) / {subscriber_count} subscriber(s) (event: {event_type})"
                )
            else:
                logger.debug(
                    f"✅ WebSocket broadcast successful: {message_type} "
                    f"→ {sent_count} client(s) / {subscriber_count} subscriber(s) (event: {event_type})"
                )
        elif subscriber_count > 0:
            logger.debug(
                f"⚠️ Event {event_type} has {subscriber_count} subscriber(s) but NO active connections!"
            )
        else:
            logger.debug(f"No subscribers found for event {event_type}")

        # Nettoyer les connexions mortes
        if disconnected:
            # Identifier les user_ids des connexions mortes
            async with self._lock:
                for user_id in list(self.user_connections.keys()):
                    user_disconnected = disconnected & self.user_connections[user_id]
                    for ws in user_disconnected:
                        disconnected_users.add((user_id, ws))

            for user_id, ws in disconnected_users:
                await self.remove_connection(user_id, ws)

    async def broadcast_deployment_log_to_subscribers(
        self, deployment_id: str, message: dict
    ):
        """
        Envoie un log de déploiement à tous les abonnés.

        Args:
            deployment_id: ID du déploiement
            message: Message JSON à envoyer
        """
        if deployment_id not in self.deployment_subscribers:
            logger.debug(f"📡 No subscribers for deployment logs {deployment_id}")
            return

        # Collecter toutes les connexions des abonnés
        all_connections = set()
        disconnected_users = set()
        subscriber_count = len(self.deployment_subscribers[deployment_id])

        async with self._lock:
            for user_id in self.deployment_subscribers[deployment_id]:
                if user_id in self.user_connections:
                    all_connections.update(self.user_connections[user_id])

        # Utiliser la logique commune de broadcast
        sent_count, disconnected = await BroadcastManager._broadcast_to_connections(
            all_connections, message, f"deployment log subscribers for {deployment_id}"
        )

        # Log standardisé avec info sur les subscribers
        if sent_count > 0:
            logger.info(
                f"📡 WebSocket broadcast: {message.get('type', 'unknown')} "
                f"→ {sent_count} client(s) / {subscriber_count} subscriber(s) (deployment logs: {deployment_id})"
            )

        # Nettoyer les connexions mortes
        if disconnected:
            # Identifier les user_ids des connexions mortes
            async with self._lock:
                for user_id in self.deployment_subscribers[deployment_id]:
                    if user_id in self.user_connections:
                        user_disconnected = (
                            disconnected & self.user_connections[user_id]
                        )
                        for ws in user_disconnected:
                            disconnected_users.add((user_id, ws))

            for user_id, ws in disconnected_users:
                await self.remove_connection(user_id, ws)

    async def dispatch_to_plugins(self, event_type: str, event_data: dict):
        """
        Dispatch un événement à tous les plugins des utilisateurs connectés.

        Args:
            event_type: Type d'événement (WebSocketEventType)
            event_data: Données de l'événement
        """
        async with self._lock:
            contexts = list(self.user_plugin_contexts.values())

        # Log du dispatch
        if contexts:
            logger.debug(
                f"🔌 Plugin dispatch: {event_type} → {len(contexts)} plugin context(s)"
            )

            # Dispatcher à tous les contextes en parallèle
            from .plugin import plugin_manager

            # STORY-172 : dispatch d'événement tracé (succès/erreur —
            # best-effort, jamais de changement de comportement).
            try:
                await asyncio.gather(
                    *[
                        plugin_manager.dispatch(event_type, event_data, ctx)  # type: ignore[arg-type]
                        for ctx in contexts
                    ],
                    return_exceptions=True,
                )
                _safe(record_event_dispatch, event_type, True)
            except Exception:
                _safe(record_event_dispatch, event_type, False)
                raise
        else:
            logger.debug(f"🔌 No plugin contexts to dispatch {event_type}")


# ============================================================================
# INSTANCES GLOBALES
# ============================================================================

# Instance globale du gestionnaire de connexions par déploiement
manager = ConnectionManager()

# Instance globale du gestionnaire de connexions par utilisateur
user_manager = UserConnectionManager()
