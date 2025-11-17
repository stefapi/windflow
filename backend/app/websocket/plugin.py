"""
WebSocket Plugin System - Base classes.

Provides extensible architecture for handling WebSocket events
through a plugin-based approach.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Set, Optional, Any, Callable
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from datetime import datetime

from ..models.user import User
from ..schemas.websocket_events import WebSocketEventType


@dataclass
class PluginContext:
    """
    Context provided to plugins for accessing application services.

    This is the backend equivalent of the frontend PluginContext,
    adapted for server-side operations.
    """

    # Core dependencies
    db: AsyncSession
    """Database session for persistence operations."""

    user: Optional[User]
    """Currently authenticated user (None if not authenticated)."""

    websocket: WebSocket
    """WebSocket connection instance."""

    logger: logging.Logger
    """Structured logger for plugin debugging."""

    # Helper functions (will be injected by PluginManager)
    broadcast_to_user: Optional[Callable] = None
    """Broadcast message to specific user."""

    broadcast_to_event_subscribers: Optional[Callable] = None
    """Broadcast message to all event subscribers."""

    send_notification: Optional[Callable] = None
    """Send notification to specific user."""

    trigger_deployment_event: Optional[Callable] = None
    """Trigger deployment-specific event."""


class WebSocketPlugin(ABC):
    """
    Interface that each WebSocket plugin must implement.

    This is the backend equivalent of the frontend WebSocketPlugin interface.
    Plugins can react to WebSocket events and perform server-side operations
    like persistence, webhooks, audit logging, etc.

    This class handles SERVER → CLIENT events (broadcast events).
    """

    name: str
    """Unique plugin name."""

    version: str = "1.0.0"
    """Plugin version (semantic versioning)."""

    description: str = ""
    """Optional plugin description."""

    listens_for: List[WebSocketEventType] = []
    """List of WebSocketEventType that this plugin handles."""

    async def initialize(self, context: PluginContext) -> None:
        """
        Initialize the plugin at startup.

        Override this method to perform setup operations like:
        - Loading configuration
        - Setting up resources
        - Initializing connections

        Args:
            context: Plugin context with application services
        """
        pass

    @abstractmethod
    async def handle_event(
        self,
        event: WebSocketEventType,
        data: Dict[str, Any],
        context: PluginContext
    ) -> None:
        """
        Handle a WebSocket event.

        This is the main entry point for plugin logic.

        Args:
            event: The WebSocketEventType being handled
            data: Event data payload
            context: Plugin context with application services
        """
        pass

    async def cleanup(self) -> None:
        """
        Clean up plugin resources on disconnection.

        Override this method to perform cleanup operations like:
        - Closing connections
        - Flushing buffers
        - Releasing resources
        """
        pass


class WebSocketMessageHandler(ABC):
    """
    Interface for plugins that handle incoming CLIENT → SERVER messages.

    Unlike WebSocketPlugin which handles broadcast events (SERVER → CLIENT),
    this handles messages sent by clients to the server (e.g., subscribe, unsubscribe).
    """

    name: str
    """Unique handler name."""

    version: str = "1.0.0"
    """Handler version."""

    description: str = ""
    """Optional handler description."""

    handles_message_types: List[str] = []
    """List of message types this handler processes (e.g., ["subscribe", "unsubscribe"])."""

    async def initialize(self, context: PluginContext) -> None:
        """
        Initialize the handler at startup.

        Args:
            context: Plugin context with application services
        """
        pass

    @abstractmethod
    async def handle_message(
        self,
        message: Dict[str, Any],
        context: PluginContext
    ) -> Optional[Dict[str, Any]]:
        """
        Handle an incoming client message.

        Args:
            message: Message data from client
            context: Plugin context with application services

        Returns:
            Optional response to send back to client (or None)
        """
        pass

    async def cleanup(self) -> None:
        """Clean up handler resources on disconnection."""
        pass


class WebSocketPluginManager:
    """
    Manager for WebSocket plugins.

    Handles registration, initialization, event dispatching,
    and cleanup of plugins.
    """

    def __init__(self):
        # Event plugins (SERVER → CLIENT)
        self._plugins: Dict[str, WebSocketPlugin] = {}
        self._event_handlers: Dict[WebSocketEventType, Set[WebSocketPlugin]] = {}

        # Message handlers (CLIENT → SERVER)
        self._message_handlers: Dict[str, WebSocketMessageHandler] = {}
        self._message_type_handlers: Dict[str, Set[WebSocketMessageHandler]] = {}

        self._context: Optional[PluginContext] = None
        self._logger = logging.getLogger(__name__)

    def register(self, plugin: WebSocketPlugin) -> None:
        """
        Register a plugin.

        Args:
            plugin: Plugin instance to register
        """
        if plugin.name in self._plugins:
            self._logger.warning(
                f"Plugin '{plugin.name}' is already registered, replacing..."
            )

        self._plugins[plugin.name] = plugin

        # Build event handler index
        for event_type in plugin.listens_for:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = set()
            self._event_handlers[event_type].add(plugin)

        self._logger.info(f"✅ WebSocket plugin '{plugin.name}' registered")

    def register_message_handler(self, handler: WebSocketMessageHandler) -> None:
        """
        Register a message handler for CLIENT → SERVER messages.

        Args:
            handler: Message handler instance to register
        """
        if handler.name in self._message_handlers:
            self._logger.warning(
                f"Message handler '{handler.name}' is already registered, replacing..."
            )

        self._message_handlers[handler.name] = handler

        # Build message type index
        for msg_type in handler.handles_message_types:
            if msg_type not in self._message_type_handlers:
                self._message_type_handlers[msg_type] = set()
            self._message_type_handlers[msg_type].add(handler)

        self._logger.info(f"✅ WebSocket message handler '{handler.name}' registered")

    def unregister(self, plugin_name: str) -> None:
        """
        Unregister a plugin.

        Args:
            plugin_name: Name of the plugin to unregister
        """
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            self._logger.warning(f"Plugin '{plugin_name}' not found")
            return

        # Remove from event handlers
        for event_type in plugin.listens_for:
            handlers = self._event_handlers.get(event_type)
            if handlers:
                handlers.discard(plugin)
                if not handlers:
                    del self._event_handlers[event_type]

        del self._plugins[plugin_name]
        self._logger.info(f"✅ WebSocket plugin '{plugin_name}' unregistered")

    def get(self, plugin_name: str) -> Optional[WebSocketPlugin]:
        """
        Get a plugin by name.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin instance or None if not found
        """
        return self._plugins.get(plugin_name)

    def list(self) -> List[WebSocketPlugin]:
        """
        List all registered plugins.

        Returns:
            List of all registered plugin instances
        """
        return list(self._plugins.values())

    async def initialize_all(self, context: PluginContext) -> None:
        """
        Initialize all registered plugins and message handlers with the context.

        Args:
            context: Plugin context to use for initialization
        """
        self._context = context

        # Initialize event plugins
        for plugin in self._plugins.values():
            try:
                await plugin.initialize(context)
                context.logger.debug(f"Plugin '{plugin.name}' initialized")
            except Exception as e:
                context.logger.error(
                    f"Failed to initialize plugin '{plugin.name}': {e}",
                    exc_info=True
                )

        # Initialize message handlers
        for handler in self._message_handlers.values():
            try:
                await handler.initialize(context)
                context.logger.debug(f"Message handler '{handler.name}' initialized")
            except Exception as e:
                context.logger.error(
                    f"Failed to initialize message handler '{handler.name}': {e}",
                    exc_info=True
                )

    async def dispatch(
        self,
        event: WebSocketEventType,
        data: Dict[str, Any],
        context: PluginContext
    ) -> None:
        """
        Dispatch an event to all plugins that listen for it.

        Args:
            event: WebSocketEventType to dispatch
            data: Event data payload
            context: Plugin context for event handling
        """
        if not self._context:
            self._logger.warning(
                "PluginManager not initialized, cannot dispatch events"
            )
            return

        handlers = self._event_handlers.get(event)
        if not handlers:
            return

        # Execute all handlers in parallel
        import asyncio

        async def handle_with_plugin(plugin: WebSocketPlugin):
            try:
                await plugin.handle_event(event, data, context)
            except Exception as e:
                context.logger.error(
                    f"Error in plugin '{plugin.name}' handling event '{event}': {e}",
                    exc_info=True
                )

        await asyncio.gather(
            *[handle_with_plugin(plugin) for plugin in handlers],
            return_exceptions=True
        )

    async def handle_client_message(
        self,
        message: Dict[str, Any],
        context: PluginContext
    ) -> Optional[Dict[str, Any]]:
        """
        Dispatch a client message to appropriate handlers.

        Args:
            message: Message from client
            context: Plugin context for message handling

        Returns:
            Optional response to send back to client
        """
        message_type = message.get("type")
        if not message_type:
            return {"type": "error", "message": "Missing message type"}

        handlers = self._message_type_handlers.get(message_type)
        if not handlers:
            context.logger.debug(f"No handler for message type: {message_type}")
            return None

        # Execute first handler that returns a response
        import asyncio

        for handler in handlers:
            try:
                response = await handler.handle_message(message, context)
                if response:
                    return response
            except Exception as e:
                context.logger.error(
                    f"Error in handler '{handler.name}' for message type '{message_type}': {e}",
                    exc_info=True
                )
                return {
                    "type": "error",
                    "message": f"Handler error: {str(e)}"
                }

        return None

    async def cleanup_all(self, context: PluginContext) -> None:
        """Clean up all registered plugins and handlers."""
        # Cleanup event plugins
        for plugin in self._plugins.values():
            try:
                await plugin.cleanup()
            except Exception as e:
                self._logger.error(
                    f"Failed to cleanup plugin '{plugin.name}': {e}",
                    exc_info=True
                )

        # Cleanup message handlers
        for handler in self._message_handlers.values():
            try:
                await handler.cleanup()
            except Exception as e:
                self._logger.error(
                    f"Failed to cleanup handler '{handler.name}': {e}",
                    exc_info=True
                )


# Singleton instance of the plugin manager
plugin_manager = WebSocketPluginManager()
