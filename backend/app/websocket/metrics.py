"""
Métriques Prometheus pour le système WebSocket.

Ce module expose des métriques pour surveiller :
- Nombre de connexions actives
- Messages broadcastés
- Latence des broadcasts
- Erreurs WebSocket
- Événements dispatché aux plugins
"""

from prometheus_client import Counter, Gauge, Histogram
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# MÉTRIQUES WEBSOCKET
# ============================================================================

# Connexions actives
WEBSOCKET_CONNECTIONS_ACTIVE = Gauge(
    'windflow_websocket_connections_active',
    'Nombre de connexions WebSocket actives',
    ['connection_type']  # 'deployment', 'user', 'general'
)

WEBSOCKET_CONNECTIONS_TOTAL = Counter(
    'windflow_websocket_connections_total',
    'Nombre total de connexions WebSocket',
    ['connection_type', 'status']  # status: 'connected', 'disconnected'
)

# Messages
WEBSOCKET_MESSAGES_SENT = Counter(
    'windflow_websocket_messages_sent_total',
    'Nombre total de messages WebSocket envoyés',
    ['message_type', 'status']  # status: 'success', 'error'
)

WEBSOCKET_MESSAGES_RECEIVED = Counter(
    'windflow_websocket_messages_received_total',
    'Nombre total de messages WebSocket reçus',
    ['message_type']
)

# Broadcasts
WEBSOCKET_BROADCAST_DURATION = Histogram(
    'windflow_websocket_broadcast_duration_seconds',
    'Durée d'un broadcast WebSocket',
    ['broadcast_type'],  # 'deployment', 'user', 'event'
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

WEBSOCKET_BROADCAST_CLIENTS = Histogram(
    'windflow_websocket_broadcast_clients',
    'Nombre de clients touchés par broadcast',
    ['broadcast_type'],
    buckets=(1, 2, 5, 10, 25, 50, 100, 250, 500, 1000)
)

# Événements et plugins
WEBSOCKET_EVENTS_DISPATCHED = Counter(
    'windflow_websocket_events_dispatched_total',
    'Nombre d\'événements dispatchés aux plugins',
    ['event_type', 'status']  # status: 'success', 'error'
)

WEBSOCKET_PLUGIN_DURATION = Histogram(
    'windflow_websocket_plugin_duration_seconds',
    'Durée d\'exécution d\'un plugin',
    ['plugin_name', 'event_type'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

# Erreurs
WEBSOCKET_ERRORS = Counter(
    'windflow_websocket_errors_total',
    'Nombre total d\'erreurs WebSocket',
    ['error_type']  # 'auth', 'broadcast', 'plugin', 'disconnect', 'timeout'
)

# Authentification
WEBSOCKET_AUTH_ATTEMPTS = Counter(
    'windflow_websocket_auth_attempts_total',
    'Nombre de tentatives d\'authentification',
    ['status']  # 'success', 'failed', 'timeout'
)

WEBSOCKET_AUTH_DURATION = Histogram(
    'windflow_websocket_auth_duration_seconds',
    'Durée du processus d\'authentification',
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)

# Abonnements
WEBSOCKET_SUBSCRIPTIONS_ACTIVE = Gauge(
    'windflow_websocket_subscriptions_active',
    'Nombre d\'abonnements actifs',
    ['subscription_type']  # 'event', 'deployment_logs'
)

WEBSOCKET_SUBSCRIPTIONS_TOTAL = Counter(
    'windflow_websocket_subscriptions_total',
    'Nombre total d\'abonnements',
    ['subscription_type', 'action']  # action: 'subscribe', 'unsubscribe'
)


# ============================================================================
# FONCTIONS HELPER POUR ENREGISTRER LES MÉTRIQUES
# ============================================================================

def record_connection(connection_type: str, status: str) -> None:
    """
    Enregistre une connexion ou déconnexion.

    Args:
        connection_type: Type de connexion ('deployment', 'user', 'general')
        status: Statut ('connected', 'disconnected')
    """
    WEBSOCKET_CONNECTIONS_TOTAL.labels(
        connection_type=connection_type,
        status=status
    ).inc()

    if status == 'connected':
        WEBSOCKET_CONNECTIONS_ACTIVE.labels(connection_type=connection_type).inc()
    elif status == 'disconnected':
        WEBSOCKET_CONNECTIONS_ACTIVE.labels(connection_type=connection_type).dec()


def record_message_sent(message_type: str, success: bool = True) -> None:
    """
    Enregistre un message envoyé.

    Args:
        message_type: Type du message
        success: Si l'envoi a réussi
    """
    status = 'success' if success else 'error'
    WEBSOCKET_MESSAGES_SENT.labels(
        message_type=message_type,
        status=status
    ).inc()


def record_message_received(message_type: str) -> None:
    """
    Enregistre un message reçu.

    Args:
        message_type: Type du message
    """
    WEBSOCKET_MESSAGES_RECEIVED.labels(message_type=message_type).inc()


def record_broadcast(broadcast_type: str, duration: float, client_count: int) -> None:
    """
    Enregistre un broadcast.

    Args:
        broadcast_type: Type de broadcast ('deployment', 'user', 'event')
        duration: Durée en secondes
        client_count: Nombre de clients touchés
    """
    WEBSOCKET_BROADCAST_DURATION.labels(broadcast_type=broadcast_type).observe(duration)
    WEBSOCKET_BROADCAST_CLIENTS.labels(broadcast_type=broadcast_type).observe(client_count)


def record_event_dispatch(event_type: str, success: bool = True) -> None:
    """
    Enregistre un dispatch d'événement.

    Args:
        event_type: Type d'événement
        success: Si le dispatch a réussi
    """
    status = 'success' if success else 'error'
    WEBSOCKET_EVENTS_DISPATCHED.labels(
        event_type=event_type,
        status=status
    ).inc()


def record_plugin_execution(plugin_name: str, event_type: str, duration: float) -> None:
    """
    Enregistre l'exécution d'un plugin.

    Args:
        plugin_name: Nom du plugin
        event_type: Type d'événement traité
        duration: Durée d'exécution en secondes
    """
    WEBSOCKET_PLUGIN_DURATION.labels(
        plugin_name=plugin_name,
        event_type=event_type
    ).observe(duration)


def record_error(error_type: str) -> None:
    """
    Enregistre une erreur WebSocket.

    Args:
        error_type: Type d'erreur ('auth', 'broadcast', 'plugin', 'disconnect', 'timeout')
    """
    WEBSOCKET_ERRORS.labels(error_type=error_type).inc()


def record_auth_attempt(success: bool = True, timeout: bool = False) -> None:
    """
    Enregistre une tentative d'authentification.

    Args:
        success: Si l'authentification a réussi
        timeout: Si c'est un timeout
    """
    if timeout:
        status = 'timeout'
    else:
        status = 'success' if success else 'failed'

    WEBSOCKET_AUTH_ATTEMPTS.labels(status=status).inc()


def record_auth_duration(duration: float) -> None:
    """
    Enregistre la durée d'authentification.

    Args:
        duration: Durée en secondes
    """
    WEBSOCKET_AUTH_DURATION.observe(duration)


def record_subscription(subscription_type: str, action: str) -> None:
    """
    Enregistre une opération d'abonnement.

    Args:
        subscription_type: Type d'abonnement ('event', 'deployment_logs')
        action: Action ('subscribe', 'unsubscribe')
    """
    WEBSOCKET_SUBSCRIPTIONS_TOTAL.labels(
        subscription_type=subscription_type,
        action=action
    ).inc()

    if action == 'subscribe':
        WEBSOCKET_SUBSCRIPTIONS_ACTIVE.labels(subscription_type=subscription_type).inc()
    elif action == 'unsubscribe':
        WEBSOCKET_SUBSCRIPTIONS_ACTIVE.labels(subscription_type=subscription_type).dec()


# ============================================================================
# CONTEXTE MANAGER POUR MESURER LA DURÉE
# ============================================================================

class MetricsTimer:
    """Context manager pour mesurer la durée d'une opération."""

    def __init__(self, metric_recorder, *args):
        """
        Args:
            metric_recorder: Fonction pour enregistrer la métrique
            *args: Arguments à passer à la fonction
        """
        self.metric_recorder = metric_recorder
        self.args = args
        self.start_time = None

    def __enter__(self):
        import time
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        duration = time.time() - self.start_time
        self.metric_recorder(*self.args, duration)
        return False


def broadcast_timer(broadcast_type: str, client_count: int):
    """
    Timer pour mesurer la durée d'un broadcast.

    Usage:
        with broadcast_timer('deployment', 5):
            # Code de broadcast
            pass
    """
    return MetricsTimer(record_broadcast, broadcast_type, client_count)


def auth_timer():
    """
    Timer pour mesurer la durée d'authentification.

    Usage:
        with auth_timer():
            # Code d'authentification
            pass
    """
    return MetricsTimer(record_auth_duration)
