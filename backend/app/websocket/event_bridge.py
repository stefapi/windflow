"""
Event Bridge between EventBus and WebSocket system.

This module forwards events from the EventBus to WebSocket clients,
acting as a bridge between the event-driven architecture and
the real-time WebSocket communication system.
"""

from typing import Dict
import logging

from ..core.events import Event, EventType, event_bus
from ..schemas.websocket_events import WebSocketEventType
from ..schemas.deployment import DeploymentStatus

logger = logging.getLogger(__name__)


# Mapping from EventType to WebSocketEventType
# This allows us to convert internal event types to WebSocket event types
EVENT_TYPE_MAPPING: Dict[EventType, WebSocketEventType] = {
    EventType.DEPLOYMENT_CREATED: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
    EventType.DEPLOYMENT_STARTED: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
    EventType.DEPLOYMENT_COMPLETED: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
    EventType.DEPLOYMENT_FAILED: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
    EventType.DEPLOYMENT_ROLLED_BACK: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
}


async def websocket_event_handler(event: Event) -> None:
    """
    Handler that forwards EventBus events to WebSocket clients.

    This handler is registered with the EventBus and is called whenever
    an event is published. It converts the event to a WebSocket message
    and broadcasts it to all subscribed clients.

    Args:
        event: Event from the EventBus
    """
    # Check if we have a mapping for this event type
    ws_event_type = EVENT_TYPE_MAPPING.get(event.event_type)

    if not ws_event_type:
        # No mapping, skip this event
        logger.debug(f"No WebSocket mapping for event type: {event.event_type}")
        return

    try:
        # Import here to avoid circular dependency
        from .broadcasting import broadcast_to_event_subscribers

        # Prepare the WebSocket message
        message = {
            "type": ws_event_type,
            "data": event.payload,
            "timestamp": event.timestamp.isoformat()
        }

        logger.info(
            f"🌉 [STEP 2/4] Event Bridge received: {event.event_type} → {ws_event_type} "
            f"(deployment_id: {event.payload.get('deployment_id', 'N/A')})"
        )
        logger.debug(
            f"WebSocket message payload: {message}"
        )

        # Broadcast to all WebSocket clients subscribed to this event type
        await broadcast_to_event_subscribers(ws_event_type, message)

        logger.info(
            f"✅ [STEP 2/4] Event successfully forwarded to broadcast layer"
        )

    except Exception as e:
        logger.error(
            f"❌ [STEP 2/4] Error forwarding event to WebSocket: {e}",
            exc_info=True,
            extra={
                "event_type": event.event_type,
                "event_id": event.event_id,
                "payload": event.payload
            }
        )


def setup_event_bridge() -> None:
    """
    Register event handlers to bridge EventBus to WebSocket system.

    This function should be called during application startup to establish
    the connection between the EventBus and WebSocket system.

    It registers the websocket_event_handler for all event types that
    need to be forwarded to WebSocket clients.
    """
    registered_count = 0

    for event_type in EVENT_TYPE_MAPPING.keys():
        event_bus.subscribe(event_type, websocket_event_handler)
        registered_count += 1
        logger.debug(f"Registered WebSocket bridge for: {event_type}")

    logger.info(
        f"✅ Event bridge initialized: {registered_count} event types "
        f"will be forwarded to WebSocket clients"
    )


def teardown_event_bridge() -> None:
    """
    Unregister event handlers (cleanup).

    This function should be called during application shutdown to properly
    clean up the event bridge handlers.
    """
    for event_type in EVENT_TYPE_MAPPING.keys():
        event_bus.unsubscribe(event_type, websocket_event_handler)

    logger.info("Event bridge handlers unregistered")
