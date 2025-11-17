"""
WebSocket plugin system for WindFlow backend.

Provides an extensible architecture for handling WebSocket events
with a plugin-based approach similar to the frontend implementation.
"""

from .plugin import (
    PluginContext,
    WebSocketPlugin,
    WebSocketMessageHandler,
    WebSocketPluginManager,
    plugin_manager
)

__all__ = [
    "PluginContext",
    "WebSocketPlugin",
    "WebSocketMessageHandler",
    "WebSocketPluginManager",
    "plugin_manager"
]
