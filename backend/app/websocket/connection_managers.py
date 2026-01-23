"""
Gestionnaires de connexions WebSocket.

Ce module contient toutes les classes de gestion des connexions WebSocket,
extraites de api/v1/websockets.py pour une meilleure organisation et maintenabilité.

Classes:
    BroadcastManager: Logique commune de broadcast WebSocket
    ConnectionManager: Gestion des connexions par déploiement
    UserConnectionManager: Gestion des connexions par utilisateur
"""

from typing import Dict, Set, Optional
from fastapi import WebSocket
import asyncio
import logging

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
        connections: Set[WebSocket],
        message: dict,
        context_description: str = ""
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
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket {context_description}: {e}")
                disconnected.add(websocket)

        return sent_count, disconnected

    @staticmethod
    def _log_broadcast(
        message: dict,
        sent_count: int,
        total_count: int,
        context: str,
        icon: str = "📡"
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
            logger.info(
                f"{icon} WebSocket broadcast: {message.get('type', 'unknown')} "
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

    async def connect(self, websocket: WebSocket, deployment_id: str):
        """
        Accepte une nouvelle connexion WebSocket.

        Args:
            websocket: Instance de connexion WebSocket
            deployment_id: ID du déploiement concerné
        """
        await websocket.accept()

        async with self._lock:
            if deployment_id not in self.active_connections:
                self.active_connections[deployment_id] = set()
            self.active_connections[deployment_id].add(websocket)

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

        # Utiliser la logique commune de broadcast
        sent_count, disconnected = await BroadcastManager._broadcast_to_connections(
            connections,
            message,
            f"deployment {deployment_id}"
        )

        # Log standardisé
        BroadcastManager._log_broadcast(
            message,
            sent_count,
            connection_count,
            f"deployment: {deployment_id}"
        )

        # Nettoyer les connexions mortes
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self.active_connections[deployment_id].discard(ws)


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
        self.user_plugin_contexts: Dict[str, 'PluginContext'] = {}
        self._lock = asyncio.Lock()

    async def add_connection(self, user_id: str, websocket: WebSocket, context: Optional['PluginContext'] = None):
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

    async def subscribe_to_event(self, user_id: str, event_type: str, websocket: WebSocket):
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

    async def unsubscribe_from_event(self, user_id: str, event_type: str, websocket: WebSocket):
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

    async def subscribe_to_deployment_logs(self, user_id: str, deployment_id: str, websocket: WebSocket):
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

        # Utiliser la logique commune de broadcast
        sent_count, disconnected = await BroadcastManager._broadcast_to_connections(
            connections,
            message,
            f"user {user_id}"
        )

        # Log standardisé
        BroadcastManager._log_broadcast(
            message,
            sent_count,
            connection_count,
            f"user: {user_id}"
        )

        # Nettoyer les connexions mortes
        if disconnected:
            async with self._lock:
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

        logger.info(
            f"📢 [STEP 4/4] Finding subscribers for event: {event_type}"
        )

        async with self._lock:
            for user_id, subscriptions in self.user_subscriptions.items():
                if event_type in subscriptions:
                    subscriber_count += 1
                    if user_id in self.user_connections:
                        all_connections.update(self.user_connections[user_id])
                        logger.debug(
                            f"Found subscriber: user {user_id} with {len(self.user_connections[user_id])} connection(s)"
                        )

        logger.info(
            f"📢 [STEP 4/4] Found {subscriber_count} subscriber(s) with {len(all_connections)} total connection(s)"
        )

        # Utiliser la logique commune de broadcast
        sent_count, disconnected = await BroadcastManager._broadcast_to_connections(
            all_connections,
            message,
            f"event subscribers for {event_type}"
        )

        # Log standardisé avec info sur les subscribers
        if sent_count > 0:
            logger.info(
                f"✅ [STEP 4/4] WebSocket broadcast successful: {message.get('type', 'unknown')} "
                f"→ {sent_count} client(s) / {subscriber_count} subscriber(s) (event: {event_type})"
            )
        elif subscriber_count > 0:
            logger.warning(
                f"⚠️ [STEP 4/4] Event {event_type} has {subscriber_count} subscriber(s) but NO active connections!"
            )
        else:
            logger.warning(
                f"⚠️ [STEP 4/4] No subscribers found for event {event_type}"
            )

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

    async def broadcast_deployment_log_to_subscribers(self, deployment_id: str, message: dict):
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
            all_connections,
            message,
            f"deployment log subscribers for {deployment_id}"
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
                        user_disconnected = disconnected & self.user_connections[user_id]
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
            logger.info(
                f"🔌 Plugin dispatch: {event_type} → {len(contexts)} plugin context(s)"
            )

            # Dispatcher à tous les contextes en parallèle
            from .plugin import plugin_manager

            await asyncio.gather(
                *[plugin_manager.dispatch(event_type, event_data, ctx) for ctx in contexts],
                return_exceptions=True
            )
        else:
            logger.debug(f"🔌 No plugin contexts to dispatch {event_type}")


# ============================================================================
# INSTANCES GLOBALES
# ============================================================================

# Instance globale du gestionnaire de connexions par déploiement
manager = ConnectionManager()

# Instance globale du gestionnaire de connexions par utilisateur
user_manager = UserConnectionManager()
