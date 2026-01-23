"""
WebSocket package - Architecture extensible pour WebSocket temps réel.

Expose les composants principaux du système WebSocket :
- Plugin system (plugin.py)
- Connection managers (connection_managers.py)
- Broadcasting utilities (broadcasting.py)
- Event bridge (event_bridge.py)
"""

# Plugin system
from .plugin import (
    WebSocketPlugin,
    WebSocketMessageHandler,
    WebSocketPluginManager,
    PluginContext,
    plugin_manager
)

# Connection managers
from .connection_managers import (
    BroadcastManager,
    ConnectionManager,
    UserConnectionManager,
    manager,
    user_manager
)

# Broadcasting utilities
from .broadcasting import (
    # Deployment broadcasts
    broadcast_deployment_log,
    broadcast_deployment_status,
    broadcast_deployment_progress,
    broadcast_deployment_complete,

    # User broadcasts
    broadcast_to_user,
    broadcast_to_event_subscribers,
    broadcast_deployment_log_to_subscribers,

    # Subscription management
    add_user_connection,
    remove_user_connection,
    subscribe_to_event,
    unsubscribe_from_event,
    subscribe_to_deployment_logs
)

# Event bridge
from .event_bridge import setup_event_bridge, teardown_event_bridge

__all__ = [
    # Plugin system
    'WebSocketPlugin',
    'WebSocketMessageHandler',
    'WebSocketPluginManager',
    'PluginContext',
    'plugin_manager',

    # Connection managers
    'BroadcastManager',
    'ConnectionManager',
    'UserConnectionManager',
    'manager',
    'user_manager',

    # Broadcasting
    'broadcast_deployment_log',
    'broadcast_deployment_status',
    'broadcast_deployment_progress',
    'broadcast_deployment_complete',
    'broadcast_to_user',
    'broadcast_to_event_subscribers',
    'broadcast_deployment_log_to_subscribers',

    # Subscriptions
    'add_user_connection',
    'remove_user_connection',
    'subscribe_to_event',
    'unsubscribe_from_event',
    'subscribe_to_deployment_logs',

    # Event bridge
    'setup_event_bridge',
    'teardown_event_bridge'
]
