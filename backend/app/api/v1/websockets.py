"""
Endpoints WebSocket pour WindFlow.

Ce module contient uniquement les routes WebSocket.
La logique métier a été déplacée dans backend/app/websocket/ pour une
meilleure organisation et maintenabilité.
"""

from fastapi import APIRouter, Depends, Query, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import get_current_user_ws
from ...auth.rbac import ensure_role_ws
from ...database import get_db
from ...models.user import User
from ...websocket.batch import batch_websocket_endpoint
from ...websocket.container_logs import container_logs_websocket_endpoint
from ...websocket.container_stats import container_stats_websocket_endpoint
from ...websocket.deployment_logs import deployment_logs_websocket_endpoint

# Import des endpoints WebSocket depuis le package websocket
from ...websocket.general import general_websocket_endpoint
from ...websocket.journal import journal_websocket_endpoint, validate_journal_tail
from ...websocket.ssh_session import ssh_session_websocket_endpoint
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
async def deployment_logs_websocket(
    websocket: WebSocket,
    deployment_id: str,
    user: User = Depends(get_current_user_ws),
    session: AsyncSession = Depends(get_db),
):
    """
    Stream deployment logs in real-time.

    Connect to a specific deployment's log stream for real-time monitoring.

    Authentication:
    Authentication is performed via query parameter: ?token=JWT_TOKEN.
    The handshake is **refused** (close code 1008) if the token is absent,
    invalid, expired or the user is inactive. In development mode
    (DISABLE_AUTH=true), the first superadmin is auto-logged in.

    Connection Flow:
    1. Client connects with deployment ID and token in query string
    2. Server validates token and user permissions (refuses handshake on failure)
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

    ## Access Control — RBAC (STORY-122.6)

    - **Minimum role**: Viewer — logs de déploiement = lecture (matrice
      spec 08 § Apps « Logs ») ; rôle insuffisant → handshake refusé
      (close 1008) avant acceptation du canal.
    """
    await ensure_role_ws(websocket, user, "viewer", session)
    await deployment_logs_websocket_endpoint(websocket, deployment_id, user)


@router.websocket("/terminal/{container_id}", name="container_terminal_websocket")
async def container_terminal_websocket(
    websocket: WebSocket, container_id: str, shell: str = "/bin/sh", user: str = "root"
):
    """
    Interactive terminal WebSocket for Docker containers.

    Provides bidirectional streaming for command execution in containers.

    Authentication:
    First message must be: {"type": "auth", "token": "JWT_TOKEN"}.
    In development mode (DISABLE_AUTH=true), the token is ignored and the
    first superadmin is auto-logged in (the auth message is still required).

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
    websocket: WebSocket,
    container_id: str,
    tail: int = 100,
    user: User = Depends(get_current_user_ws),
    session: AsyncSession = Depends(get_db),
):
    """
    Stream Docker container logs in real-time.

    Connect to stream logs from a specific Docker container.

    Authentication:
    Authentication is performed via query parameter: ?token=JWT_TOKEN.
    The handshake is **refused** (close code 1008) if the token is absent,
    invalid, expired or the user is inactive. In development mode
    (DISABLE_AUTH=true), the first superadmin is auto-logged in.

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

    ## Access Control — RBAC (STORY-122.6)

    - **Minimum role**: Viewer — logs de conteneur = lecture (matrice
      spec 08 § Apps « Logs ») ; rôle insuffisant → handshake refusé
      (close 1008) avant acceptation du canal.
    """
    await ensure_role_ws(websocket, user, "viewer", session)
    await container_logs_websocket_endpoint(websocket, container_id, tail, user)


@router.websocket(
    "/docker/containers/{container_id}/stats", name="docker_container_stats_websocket"
)
async def docker_container_stats_websocket(
    websocket: WebSocket,
    container_id: str,
    user: User = Depends(get_current_user_ws),
    session: AsyncSession = Depends(get_db),
):
    """
    Stream Docker container stats in real-time.

    Connect to stream stats from a specific Docker container.

    Authentication:
    Authentication is performed via query parameter: ?token=JWT_TOKEN.
    The handshake is **refused** (close code 1008) if the token is absent,
    invalid, expired or the user is inactive. In development mode
    (DISABLE_AUTH=true), the first superadmin is auto-logged in.

    Query Parameters:
    - token: JWT token for authentication

    Connection Flow:
    1. Client connects with container ID and token in query string
    2. Server validates token and user permissions
    3. Server sends initial container info
    4. Client receives real-time stats updates every ~1 second

    Message Types Sent:
    - initial: Initial container state
    - stats: Real-time stats (CPU %, Memory %, Network I/O, Block I/O)
    - error: Error notifications
    - stream_status: Streaming status updates (started, stopped, container_stopped)

    Client Messages:
    - Heartbeat: Send "ping" to keep connection alive

    ## Access Control — RBAC (STORY-122.6)

    - **Minimum role**: Viewer — métriques de conteneur = lecture (matrice
      spec 08 § Apps « Inspecter ») ; rôle insuffisant → handshake refusé
      (close 1008) avant acceptation du canal.
    """
    await ensure_role_ws(websocket, user, "viewer", session)
    await container_stats_websocket_endpoint(websocket, container_id, user)


@router.websocket("/ssh/{host_id}", name="ssh_session_websocket")
async def ssh_session_websocket(
    websocket: WebSocket,
    host_id: str,
    cols: int = Query(80, ge=10, le=500),
    rows: int = Query(24, ge=4, le=200),
    user: User = Depends(get_current_user_ws),
    session: AsyncSession = Depends(get_db),
):
    """
    Interactive SSH session WebSocket for remote Hosts.

    Opens a bidirectional PTY session (xterm.js compatible) on a remote
    Host, with TOFU STRICT host key verification (STORY-131): unknown,
    non-accepted or divergent fingerprint **blocks** the session (close
    1011, generic client message — the fingerprint itself is never sent
    to the client).

    Authentication:
    Authentication is performed via query parameter: ?token=JWT_TOKEN.
    The handshake is **refused** (close code 1008) if the token is absent,
    invalid, expired or the user is inactive. In development mode
    (DISABLE_AUTH=true), the first superadmin is auto-logged in.

    Query Parameters:
    - token: JWT token for authentication
    - cols: Initial terminal width (10-500, default 80)
    - rows: Initial terminal height (4-200, default 24)

    Client Messages:
    - input: {"type": "input", "data": "ls\\n"}
    - resize: {"type": "resize", "cols": 120, "rows": 30}
    - ping: {"type": "ping"}

    Server Messages:
    - ready: {"type": "ready", "session_id": "...", "host_id": "...", "cols": 80, "rows": 24}
    - output: {"type": "output", "data": "..."}
    - error: {"type": "error", "message": "..."}
    - exit: {"type": "exit", "code": 0}
    - pong: {"type": "pong", "timestamp": "..."}

    Security:
    - TOFU STRICT: unknown/divergent host key → close 1011, generic
      message (never the fingerprint itself)
    - Rate limiting: maximum 3 concurrent SSH sessions per user
    - Audit trail: dedicated `ssh_session_audit` logger
      (connect/disconnect, user, host, duration — no secrets)
    - Idle expiry: silent connections closed server-side (1001)

    ## Access Control — RBAC (STORY-122.6)

    - **Minimum role**: Operator — session SSH sur Host = action
      opérationnelle (matrice spec 08 § Hosts « SSH/journalctl ») ;
      rôle insuffisant → handshake refusé (close 1008) avant
      acceptation du canal.
    """
    await ensure_role_ws(websocket, user, "operator", session)
    await ssh_session_websocket_endpoint(websocket, host_id, user, session, cols, rows)


@router.websocket("/journal/{host_id}", name="host_journal_websocket")
async def host_journal_websocket(
    websocket: WebSocket,
    host_id: str,
    tail: int = Query(100, ge=0, le=10000),
    user: User = Depends(get_current_user_ws),
    session: AsyncSession = Depends(get_db),
):
    """
    Stream a remote Host system journal (journalctl -f) in real-time.

    Runs `journalctl -f -n <tail> --no-pager` on the Host over SSH (TOFU
    STRICT host key verification — same policy as /ws/ssh) and streams
    each line to the client. Non-systemd hosts (journalctl missing or
    failing, non-zero exit) get an explicit `error` message and a clean
    close.

    Authentication:
    Authentication is performed via query parameter: ?token=JWT_TOKEN.
    The handshake is **refused** (close code 1008) if the token is absent,
    invalid, expired or the user is inactive. In development mode
    (DISABLE_AUTH=true), the first superadmin is auto-logged in.

    Query Parameters:
    - token: JWT token for authentication
    - tail: Number of initial lines (0-10000, default 100) — validated
      and bounded before being interpolated into the remote command

    Message Types Sent:
    - initial: {"type": "initial", "host_id": "...", "tail": 100}
    - stream_status: started / ended / failed
    - log: {"type": "log", "data": "..."} — one message per journal line
    - error: journalctl unavailable (non-systemd host), SSH failure…
    - pong: heartbeat response

    Client Messages:
    - Heartbeat: Send "ping" to keep connection alive

    ## Access Control — RBAC (STORY-122.6)

    - **Minimum role**: Operator — journalctl sur Host = action
      opérationnelle SSH (matrice spec 08 § Hosts « SSH/journalctl
      (lecture) » classée Operator+ ; divergence vs décision d'analyse
      « viewer » signalée dans STORY-164.2) ; rôle insuffisant →
      handshake refusé (close 1008) avant acceptation du canal.
    """
    await ensure_role_ws(websocket, user, "operator", session)
    try:
        validate_journal_tail(tail)
    except ValueError:
        # Garde défensive — Query(ge/le) a déjà borné la valeur.
        await websocket.close(code=1008)
        return
    await journal_websocket_endpoint(websocket, host_id, user, session, tail)


@router.websocket("/batch/{batch_id}", name="batch_progress_websocket")
async def batch_progress_websocket(
    websocket: WebSocket,
    batch_id: str,
    user: User = Depends(get_current_user_ws),
    session: AsyncSession = Depends(get_db),
):
    """
    Follow the progression of a batch operation (batch update, check-updates).

    Subscribes to the event stream of a grouped operation. The channel is
    **emitter-ready** (STORY-164.2, decision 7): no batch orchestration
    exists in the backend yet — the first real producer is expected from
    STORY-173 (`POST /compute/check-updates` → batch_id), then the
    multi-App batch-update (Roadmap). Emitters call
    `broadcast_batch_event(batch_id, phase, data)`.

    Authentication:
    Authentication is performed via query parameter: ?token=JWT_TOKEN.
    The handshake is **refused** (close code 1008) if the token is absent,
    invalid, expired or the user is inactive. In development mode
    (DISABLE_AUTH=true), the first superadmin is auto-logged in.

    Message Types Sent:
    - subscribed: {"type": "subscribed", "batch_id": "..."}
    - start: {"type": "start", "data": {"batch_id": "...", "total": 3}}
    - progress: {"type": "progress", "data": {"app_id": "...", "step": "pulling", ...}}
    - complete: {"type": "complete", "data": {"total": 3, "succeeded": 2, ...}}
    - error: global batch failure
    - pong: heartbeat response

    Client Messages:
    - Heartbeat: Send "ping" to keep connection alive

    ## Access Control — RBAC (STORY-122.6)

    - **Minimum role**: Viewer — suivi d'opération = lecture (le
      déclenchement d'une opération groupée passe par l'API REST
      RBAC-protégée — décision 2 analyse STORY-164) ; rôle insuffisant →
      handshake refusé (close 1008) avant acceptation du canal.
    """
    await ensure_role_ws(websocket, user, "viewer", session)
    await batch_websocket_endpoint(websocket, batch_id, user, session)
