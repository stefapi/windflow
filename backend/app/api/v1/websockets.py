"""
Endpoints WebSocket pour WindFlow.

Ce module contient uniquement les routes WebSocket.
La logique métier a été déplacée dans backend/app/websocket/ pour une
meilleure organisation et maintenabilité.
"""

from fastapi import APIRouter, WebSocket

from ...websocket.container_logs import container_logs_websocket_endpoint
from ...websocket.deployment_logs import deployment_logs_websocket_endpoint

# Import des endpoints WebSocket depuis le package websocket
from ...websocket.general import general_websocket_endpoint
from ...websocket.terminal import container_terminal_websocket_endpoint

router = APIRouter()


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================


@router.websocket("/", name="general_websocket")
async def general_websocket(websocket: WebSocket):
    """
    General WebSocket connection for real-time events.

    Connect to the general WebSocket endpoint for real-time system notifications and events.

    Authentication Process:
    1. Client connects to WebSocket endpoint
    2. Server accepts connection
    3. Client sends authentication message within 30 seconds: {"type": "auth", "token": "JWT_TOKEN"}
    4. Server validates token and user status
    5. Server sends authentication confirmation
    6. Connection is established for bidirectional communication

    Event Types Received:
    - System Notifications: Global system events and alerts
    - Deployment Updates: Real-time deployment status changes
    - Deployment Logs: Live streaming of deployment logs
    - User Events: User-specific notifications
    - Organization Events: Organization-wide updates

    Client Messages:
    - Authentication: {"type": "auth", "token": "JWT_TOKEN"}
    - Heartbeat: Send "ping" to keep connection alive
    - Custom Messages: Plugin-based message handling

    Server Responses:
    - Authentication Success: {"type": "auth.login.success", "data": {...}}
    - Pong: {"type": "pong", "timestamp": "..."}
    - Events: Various event types based on subscriptions
    - Errors: {"type": "error", "message": "..."}
    """
    await general_websocket_endpoint(websocket)


@router.websocket("/deployments/{deployment_id}/logs", name="deployment_logs_websocket")
async def deployment_logs_websocket(websocket: WebSocket, deployment_id: str):
    """
    Stream deployment logs in real-time.

    Connect to a specific deployment's log stream for real-time monitoring.

    Authentication:
    Authentication is performed via query parameter: ?token=JWT_TOKEN

    Connection Flow:
    1. Client connects with deployment ID and token in query string
    2. Server validates token and user permissions
    3. Server verifies user has access to the deployment
    4. Server sends initial deployment status
    5. Client receives real-time log updates as they occur

    Message Types Received:
    - Status: Initial deployment status
    - Log: Real-time log entries
    - Progress: Deployment progress updates
    - Complete: Deployment completion notification
    - Error: Error notifications

    Client Messages:
    - Heartbeat: Send "ping" to keep connection alive
    - Server Response: Receives {"type": "pong", "timestamp": "..."}

    Access Control:
    - User must be authenticated with valid JWT token
    - User must belong to the same organization as the deployment
    - Superadmins can access all deployments
    """
    await deployment_logs_websocket_endpoint(websocket, deployment_id)


@router.websocket("/terminal/{container_id}", name="container_terminal_websocket")
async def container_terminal_websocket(
    websocket: WebSocket, container_id: str, shell: str = "/bin/sh", user: str = "root"
):
    """
    Interactive terminal WebSocket for Docker containers.

    Provides bidirectional streaming for command execution in containers.

    Authentication:
    First message must be: {"type": "auth", "token": "JWT_TOKEN"}

    Security:
    - RBAC: User must have access to the deployment containing the container
    - Rate limiting: Maximum 3 concurrent sessions per user
    - Audit trail: All sessions are logged for compliance

    Client Messages:
    - auth: {"type": "auth", "token": "JWT_TOKEN"}
    - input: {"type": "input", "data": "ls\\n"}
    - resize: {"type": "resize", "cols": 120, "rows": 30}
    - ping: {"type": "ping"}

    Server Messages:
    - ready: {"type": "ready", "exec_id": "xxx", "shell": "/bin/sh", "user": "root", "cols": 80, "rows": 24}
    - output: {"type": "output", "data": "..."}
    - error: {"type": "error", "message": "..."}
    - exit: {"type": "exit", "code": 0}
    - pong: {"type": "pong", "timestamp": "..."}
    """
    await container_terminal_websocket_endpoint(websocket, container_id, shell, user)


@router.websocket(
    "/docker/containers/{container_id}/logs", name="docker_container_logs_websocket"
)
async def docker_container_logs_websocket(
    websocket: WebSocket, container_id: str, tail: int = 100
):
    """
    Stream Docker container logs in real-time.

    Connect to stream logs from a specific Docker container.

    Authentication:
    Authentication is performed via query parameter: ?token=JWT_TOKEN

    Query Parameters:
    - token: JWT token for authentication
    - tail: Number of lines to retrieve (default: 100)

    Connection Flow:
    1. Client connects with container ID and token in query string
    2. Server validates token and user permissions
    3. Server sends initial container info
    4. Client receives real-time log updates using Docker logs --follow

    Message Types Sent:
    - initial: Initial container information and existing logs
    - log: Real-time log entries as they occur
    - error: Error notifications
    - stream_status: Streaming status updates (started, stopped, container_stopped)

    Client Messages:
    - Heartbeat: Send "ping" to keep connection alive
    """
    await container_logs_websocket_endpoint(websocket, container_id, tail)
