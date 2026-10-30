"""Canal WebSocket ``/ws/ssh/{host_id}`` — session SSH interactive (STORY-164.2).

Session SSH PTY bidirectionnelle vers un Host distant (modèle
``terminal.py`` — canal interactif Docker) :

- connexion via :func:`app.services.ssh_connection.build_ssh_kwargs`
  (STORY-131, **TOFU STRICT** — jamais ``known_hosts: None``) :
  empreinte inconnue/non acceptée (``SSHHostKeyNotAcceptedError``) ou
  divergence (``SSHHostKeyMismatchError``) → fermeture **1011** avec
  message **générique** côté client (jamais d'empreinte en clair),
  détail complet côté serveur (log) ;
- PTY asyncssh (``create_process(term_type=…, term_size=…)``) + resize
  (``channel.change_terminal_size``) — compatible xterm.js ;
- rate limit 3 sessions simultanées par utilisateur (calqué
  ``terminal_sessions``) ;
- audit dédié : logger ``ssh_session_audit`` (pattern
  ``log_terminal_audit``) — ouverture/fermeture, user, host, durée,
  **jamais de secret** ;
- expiration des connexions muettes via le helper STORY-164.1
  (``receive_with_expiry`` — tout message reçu reset le délai).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

import asyncssh
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import SSHHostKeyMismatchError, SSHHostKeyNotAcceptedError
from ..models.user import User
from ..services.ssh_connection import HostKeyPolicy, build_ssh_kwargs
from .heartbeat import HeartbeatExpiredError, receive_with_expiry
from .host_access import resolve_host_and_check_access, resolve_ssh_username

logger = logging.getLogger(__name__)

# =============================================================================
# Rate limiting des sessions SSH (modèle terminal.py)
# =============================================================================

# Store en mémoire pour les sessions SSH actives (en production, Redis).
ssh_sessions: dict[str, dict] = {}
MAX_SSH_SESSIONS_PER_USER = 3

# Message générique TOFU — ne révèle jamais l'empreinte (rules 40 : la
# divergence est détaillée côté serveur uniquement).
TOFU_REFUSED_CLIENT_MESSAGE = (
    "SSH host key verification failed: the host key is not accepted. "
    "Ask an administrator to review and accept the host fingerprint."
)

WS_CLOSE_POLICY_VIOLATION = 1008
WS_CLOSE_INTERNAL_ERROR = 1011


async def check_ssh_rate_limit(user_id: str) -> tuple[bool, str]:
    """Vérifie le rate limit des sessions SSH simultanées par utilisateur.

    Args:
        user_id: Identifiant de l'utilisateur.

    Returns:
        Tuple (autorisé, message d'erreur si refus).
    """
    user_sessions = [
        sid for sid, info in ssh_sessions.items() if info.get("user_id") == user_id
    ]
    if len(user_sessions) >= MAX_SSH_SESSIONS_PER_USER:
        return (
            False,
            f"Maximum {MAX_SSH_SESSIONS_PER_USER} SSH sessions allowed per user",
        )
    return True, ""


async def register_ssh_session(session_id: str, user_id: str, host_id: str) -> None:
    """Enregistre une session SSH active (rate limiting)."""
    ssh_sessions[session_id] = {
        "user_id": user_id,
        "host_id": host_id,
        "started_at": datetime.utcnow().isoformat(),
    }


async def unregister_ssh_session(session_id: str) -> None:
    """Supprime une session SSH du store."""
    ssh_sessions.pop(session_id, None)


async def log_ssh_session_audit(
    user_id: str,
    username: str,
    host_id: str,
    action: str,
    success: bool,
    details: str = "",
    duration_seconds: Optional[float] = None,
) -> None:
    """Journalise les événements de session SSH pour l'audit trail.

    Pattern ``log_terminal_audit`` : logger dédié ``ssh_session_audit``,
    extra structuré (user, host, action, succès, durée) — **jamais de
    secret ni d'empreinte** dans les logs (rules 40).

    Args:
        user_id: Identifiant de l'utilisateur.
        username: Nom de l'utilisateur.
        host_id: Identifiant du Host (jamais l'adresse IP).
        action: Action (connect, disconnect, error).
        success: Succès de l'action.
        details: Détail complémentaire (message serveur uniquement).
        duration_seconds: Durée de session (fermeture).
    """
    audit_logger = logging.getLogger("ssh_session_audit")

    extra: dict = {
        "event": "ssh_session",
        "user_id": str(user_id),
        "username": username,
        "host_id": host_id,
        "action": action,
        "success": success,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if duration_seconds is not None:
        extra["duration_seconds"] = round(duration_seconds, 2)
    if details:
        extra["details"] = details

    message = f"SSH session: {action} by {username} on host {host_id}"
    if success:
        audit_logger.info(message, extra=extra)
    else:
        audit_logger.warning(f"{message} - {details}", extra=extra)


async def ssh_session_websocket_endpoint(
    websocket: WebSocket,
    host_id: str,
    user: User,
    session: AsyncSession,
    cols: int = 80,
    rows: int = 24,
) -> None:
    """Session SSH interactive PTY relayée sur WebSocket.

    Auth/RBAC : réalisés **avant accept** par la route
    (``get_current_user_ws`` + ``ensure_role_ws`` operator, STORY-122.6)
    — ce handler reçoit un utilisateur déjà authentifié et autorisé.

    Sécurité :
    - TOFU STRICT via ``build_ssh_kwargs`` — empreinte inconnue/divergente
      → close 1011, message générique (jamais d'empreinte côté client) ;
    - rate limit 3 sessions/user ;
    - audit ``ssh_session_audit`` (ouverture/fermeture, user, host, durée) ;
    - isolation organisation (``resolve_host_and_check_access``).

    Messages client :
    - input: ``{"type": "input", "data": "ls\\n"}``
    - resize: ``{"type": "resize", "cols": 120, "rows": 30}``
    - ping: ``{"type": "ping"}``

    Messages serveur :
    - ready: ``{"type": "ready", "session_id": …, "host_id": …, "cols": …, "rows": …}``
    - output: ``{"type": "output", "data": "…"}``
    - error: ``{"type": "error", "message": "…"}``
    - exit: ``{"type": "exit", "code": …}``
    - pong: ``{"type": "pong", "timestamp": …}``
    """
    await websocket.accept()
    channel = f"ssh:{host_id}"
    started_at = datetime.utcnow()
    session_id: Optional[str] = None
    registered = False
    connection: Optional[asyncssh.SSHClientConnection] = None
    process: Optional[asyncssh.SSHClientProcess] = None
    streaming_task: Optional[asyncio.Task] = None

    try:
        # ── Résolution du Host + isolation organisation ────────────
        try:
            host = await resolve_host_and_check_access(host_id, user, session)
        except Exception as e:
            detail = getattr(e, "detail", "Host access denied")
            await websocket.send_json({"type": "error", "message": str(detail)})
            await websocket.close(code=WS_CLOSE_POLICY_VIOLATION)
            return

        # ── Rate limiting (3 sessions/user, modèle terminal) ───────
        can_connect, rate_limit_msg = await check_ssh_rate_limit(str(user.id))
        if not can_connect:
            await log_ssh_session_audit(
                str(user.id), user.username, host_id, "connect", False, rate_limit_msg
            )
            await websocket.send_json({"type": "error", "message": rate_limit_msg})
            await websocket.close(code=WS_CLOSE_POLICY_VIOLATION)
            return

        # ── Connexion SSH TOFU STRICT (STORY-131) ──────────────────
        username = resolve_ssh_username(host)
        try:
            ssh_kwargs = await build_ssh_kwargs(
                session,
                host=host.host,
                port=host.port,
                username=username,
                mode=HostKeyPolicy.STRICT,
                host_model=host,
            )
            connection = await asyncssh.connect(**ssh_kwargs)
        except (SSHHostKeyNotAcceptedError, SSHHostKeyMismatchError) as e:
            # Divergence/inconnu : détail serveur uniquement (jamais
            # d'empreinte en clair côté client — rules 40).
            await log_ssh_session_audit(
                str(user.id), user.username, host_id, "connect", False, str(e)
            )
            logger.warning(
                "SSH session refused by TOFU policy",
                extra={
                    "host_id": host_id,
                    "user_id": str(user.id),
                    "reason": type(e).__name__,
                },
            )
            await websocket.send_json(
                {"type": "error", "message": TOFU_REFUSED_CLIENT_MESSAGE}
            )
            await websocket.close(code=WS_CLOSE_INTERNAL_ERROR)
            return
        except (asyncssh.Error, OSError) as e:
            await log_ssh_session_audit(
                str(user.id), user.username, host_id, "connect", False, str(e)
            )
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"SSH connection failed: {type(e).__name__}",
                }
            )
            await websocket.close(code=WS_CLOSE_INTERNAL_ERROR)
            return

        # ── Session PTY interactive ─────────────────────────────────
        try:
            process = await connection.create_process(
                term_type="xterm-256color",
                term_size=(cols, rows),
                encoding="utf-8",
            )
        except asyncssh.Error as e:
            await log_ssh_session_audit(
                str(user.id), user.username, host_id, "connect", False, str(e)
            )
            await websocket.send_json(
                {"type": "error", "message": "Failed to open remote shell"}
            )
            await websocket.close(code=WS_CLOSE_INTERNAL_ERROR)
            connection.close()
            return

        session_id = (
            f"ssh-{host_id}-{str(user.id)[:8]}-{int(datetime.utcnow().timestamp())}"
        )
        await register_ssh_session(session_id, str(user.id), host_id)
        registered = True

        await log_ssh_session_audit(
            str(user.id),
            user.username,
            host_id,
            "connect",
            True,
            f"cols={cols}, rows={rows}",
        )
        logger.info(
            "SSH session WebSocket opened",
            extra={"host_id": host_id, "user_id": str(user.id)},
        )

        await websocket.send_json(
            {
                "type": "ready",
                "session_id": session_id,
                "host_id": host_id,
                "cols": cols,
                "rows": rows,
            }
        )

        # ── Pont PTY → WebSocket (tâche de streaming) ─────────────
        async def stream_output() -> None:
            """Relaye la sortie du PTY vers le client WebSocket."""
            try:
                async for data in process.stdout:
                    await websocket.send_json({"type": "output", "data": data})
            except asyncio.CancelledError:
                raise
            except Exception as e:  # envoi impossible : connexion morte
                logger.debug(
                    "SSH session output stream ended: %s", e, extra={"channel": channel}
                )

        streaming_task = asyncio.create_task(stream_output())

        # ── Boucle principale : WebSocket → PTY ────────────────────
        # STORY-164.1 : expiration sur inactivité TOTALE uniquement —
        # tout message reçu (input, resize, ping) reset le délai ; pas
        # de ping serveur périodique (canal émetteur via stream_output,
        # modèle terminal).
        while True:
            data = await receive_with_expiry(websocket, channel, user_id=str(user.id))

            if data == "ping":
                await websocket.send_json(
                    {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                )
                continue

            try:
                message: dict[str, Any] = json.loads(data)
            except json.JSONDecodeError:
                continue

            msg_type = message.get("type")

            if msg_type == "input":
                input_data = message.get("data")
                if isinstance(input_data, str):
                    process.stdin.write(input_data)

            elif msg_type == "resize":
                try:
                    new_cols = int(message.get("cols", cols))
                    new_rows = int(message.get("rows", rows))
                except (TypeError, ValueError):
                    continue
                if new_cols > 0 and new_rows > 0:
                    process.channel.change_terminal_size(new_cols, new_rows)

    except WebSocketDisconnect:
        logger.info(
            "SSH session WebSocket disconnected",
            extra={"host_id": host_id, "user_id": str(user.id)},
        )
    except HeartbeatExpiredError:
        logger.info(
            "SSH session WebSocket expired (idle)",
            extra={"host_id": host_id, "user_id": str(user.id)},
        )
    except Exception as e:  # défense en profondeur
        logger.error(
            "SSH session WebSocket error: %s",
            e,
            extra={"host_id": host_id, "user_id": str(user.id)},
        )
        try:
            await websocket.send_json({"type": "error", "message": "SSH session error"})
        except Exception:
            pass
    finally:
        # Fermeture propre WS ↔ PTY ↔ connexion SSH (ordre inverse).
        if streaming_task is not None:
            streaming_task.cancel()
            try:
                await streaming_task
            except asyncio.CancelledError:
                pass

        if registered and session_id is not None:
            await unregister_ssh_session(session_id)
            duration = (datetime.utcnow() - started_at).total_seconds()
            await log_ssh_session_audit(
                str(user.id),
                user.username,
                host_id,
                "disconnect",
                True,
                duration_seconds=duration,
            )

        if process is not None:
            try:
                exit_status = process.exit_status
                if exit_status is not None:
                    await websocket.send_json({"type": "exit", "code": exit_status})
            except Exception:
                pass
            try:
                process.close()
            except Exception:
                pass
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
