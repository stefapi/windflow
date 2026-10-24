"""Canal WebSocket ``/ws/journal/{host_id}`` — streaming du journal système
d'un Host via ``journalctl`` (STORY-164.2 — P2-5, axe C3).

Canal lecture transposé de ``container_logs.py`` (streaming ``--follow``)
à ``journalctl -f -n <tail>`` exécuté sur le Host via SSH :

- connexion SSH via :func:`app.services.ssh_connection.build_ssh_kwargs`
  (**TOFU STRICT** — jamais ``known_hosts: None``) : empreinte
  inconnue/divergente → fermeture **1011** message générique (jamais
  d'empreinte en clair côté client, rules 40) ;
- streaming ligne à ligne → messages ``{"type": "log", "data": …}`` +
  ``stream_status`` (modèle container_logs) ;
- ``tail`` entier **borné** (validation query côté route — aucune
  commande shell construite à partir d'une entrée non validée) ;
- ``journalctl`` absent (Host non-systemd, exit ≠ 0) → message ``error``
  explicite + fermeture propre ;
- expiration des connexions muettes (helper STORY-164.1) + ``pong`` au
  ping client.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

import asyncssh
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import SSHHostKeyMismatchError, SSHHostKeyNotAcceptedError
from ..models.user import User
from ..services.ssh_connection import HostKeyPolicy, build_ssh_kwargs
from .heartbeat import (
    HeartbeatExpiredError,
    periodic_ping,
    receive_with_expiry,
)
from .host_access import resolve_host_and_check_access, resolve_ssh_username
from .ssh_session import TOFU_REFUSED_CLIENT_MESSAGE

logger = logging.getLogger(__name__)

# Bornes du paramètre ``tail`` (validation partagée route/handler — la
# valeur est interpolée dans une commande shell, elle doit être un
# entier borné, jamais une chaîne brute).
JOURNAL_TAIL_MIN = 0
JOURNAL_TAIL_MAX = 10_000
JOURNAL_TAIL_DEFAULT = 100

# Commande de streaming : constantes uniquement — ``tail_lines`` est un
# entier validé par ``validate_journal_tail`` avant interpolation.
_JOURNALCTL_COMMAND = "journalctl -f -n {tail} --no-pager -o short-iso"

WS_CLOSE_POLICY_VIOLATION = 1008
WS_CLOSE_INTERNAL_ERROR = 1011


def validate_journal_tail(tail: int) -> int:
    """Valide et borne le paramètre ``tail`` (anti-injection).

    Args:
        tail: Nombre de lignes initiales demandées.

    Returns:
        La valeur bornée dans ``[JOURNAL_TAIL_MIN, JOURNAL_TAIL_MAX]``.

    Raises:
        ValueError: Si ``tail`` n'est pas un entier valide ou hors bornes.
    """
    if not isinstance(tail, int) or tail < JOURNAL_TAIL_MIN or tail > JOURNAL_TAIL_MAX:
        raise ValueError(
            f"tail must be an integer between {JOURNAL_TAIL_MIN} and {JOURNAL_TAIL_MAX}"
        )
    return tail


async def journal_websocket_endpoint(
    websocket: WebSocket,
    host_id: str,
    user: User,
    session: AsyncSession,
    tail: int = JOURNAL_TAIL_DEFAULT,
) -> None:
    """Streame le journal système d'un Host (``journalctl -f``) sur WebSocket.

    Auth/RBAC : réalisés **avant accept** par la route
    (``get_current_user_ws`` + ``ensure_role_ws``, STORY-122.6) — ce
    handler reçoit un utilisateur déjà authentifié et autorisé.

    Messages serveur :
    - initial: ``{"type": "initial", "host_id": …, "tail": …}``
    - log: ``{"type": "log", "data": "…"}``
    - stream_status: ``{"type": "stream_status", "status": "started|ended|failed"}``
    - error: ``{"type": "error", "message": "…"}``
    - pong: ``{"type": "pong", "timestamp": …}``
    """
    await websocket.accept()
    channel = f"journal:{host_id}"

    connection: Optional[asyncssh.SSHClientConnection] = None
    process: Optional[asyncssh.SSHClientProcess] = None
    heartbeat_task: Optional[asyncio.Task] = None
    streaming_task: Optional[asyncio.Task] = None

    try:
        # ── Résolution du Host + isolation organisation ────────────
        try:
            target = await resolve_host_and_check_access(host_id, user, session)
        except Exception as e:
            detail = getattr(e, "detail", "Host access denied")
            await websocket.send_json({"type": "error", "message": str(detail)})
            await websocket.close(code=WS_CLOSE_POLICY_VIOLATION)
            return

        # ── Validation du tail (anti-injection : entier borné) ─────
        try:
            tail_lines = validate_journal_tail(tail)
        except ValueError as e:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close(code=WS_CLOSE_POLICY_VIOLATION)
            return

        # ── Connexion SSH TOFU STRICT (STORY-131) ──────────────────
        username = resolve_ssh_username(target)
        try:
            ssh_kwargs = await build_ssh_kwargs(
                session,
                host=target.host,
                port=target.port,
                username=username,
                mode=HostKeyPolicy.STRICT,
                target=target,
            )
            connection = await asyncssh.connect(**ssh_kwargs)
        except (SSHHostKeyNotAcceptedError, SSHHostKeyMismatchError) as e:
            logger.warning(
                "Journal stream refused by TOFU policy",
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
            logger.warning(
                "Journal stream SSH connection failed",
                extra={"host_id": host_id, "user_id": str(user.id), "error": str(e)},
            )
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"SSH connection failed: {type(e).__name__}",
                }
            )
            await websocket.close(code=WS_CLOSE_INTERNAL_ERROR)
            return

        # ── Lancement du streaming journalctl -f ───────────────────
        command = _JOURNALCTL_COMMAND.format(tail=tail_lines)
        try:
            process = await connection.create_process(
                command, encoding="utf-8", stderr=asyncssh.STDOUT
            )
        except asyncssh.Error as e:
            logger.warning(
                "Journal stream process creation failed",
                extra={"host_id": host_id, "error": str(e)},
            )
            await websocket.send_json(
                {"type": "error", "message": "Failed to start journalctl"}
            )
            await websocket.close(code=WS_CLOSE_INTERNAL_ERROR)
            connection.close()
            return

        logger.info(
            "Journal WebSocket stream started",
            extra={"host_id": host_id, "user_id": str(user.id), "tail": tail_lines},
        )
        await websocket.send_json(
            {"type": "initial", "host_id": host_id, "tail": tail_lines}
        )
        await websocket.send_json(
            {"type": "stream_status", "status": "started", "message": "journalctl -f"}
        )

        # ── Streaming journalctl → WebSocket ───────────────────────
        async def stream_journal() -> None:
            """Relaye les lignes journalctl vers le client WebSocket."""
            try:
                async for line in process.stdout:
                    await websocket.send_json({"type": "log", "data": line})
                # Fin de flux normale (journalctl terminé / hôte coupé)
                await websocket.send_json(
                    {
                        "type": "stream_status",
                        "status": "ended",
                        "message": "Journal stream ended (host may have stopped journald)",
                    }
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug("Journal stream ended: %s", e, extra={"channel": channel})

        streaming_task = asyncio.create_task(stream_journal())

        # ── Surveillant : journalctl absent (exit ≠ 0) ─────────────
        async def watch_exit_status() -> None:
            """Détecte l'échec immédiat de journalctl (Host non-systemd)."""
            try:
                exit_status = await process.wait()
                if exit_status not in (0, None) and streaming_task:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "journalctl unavailable on this host "
                                f"(exit code {exit_status}) — is this a systemd host?"
                            ),
                        }
                    )
                    await websocket.send_json(
                        {"type": "stream_status", "status": "failed"}
                    )
                    await websocket.close(code=1000)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

        watcher_task = asyncio.create_task(watch_exit_status())

        # STORY-164.1 : ping serveur périodique + expiration des
        # connexions muettes (modèle deployment_logs).
        heartbeat_task = asyncio.create_task(periodic_ping(websocket, channel))

        # ── Boucle de maintien de connexion ────────────────────────
        try:
            while True:
                data = await receive_with_expiry(
                    websocket, channel, user_id=str(user.id)
                )
                if data == "ping":
                    await websocket.send_json(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                    )
        finally:
            for task in (heartbeat_task, streaming_task, watcher_task):
                if task is not None:
                    task.cancel()
            for task in (heartbeat_task, streaming_task, watcher_task):
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    except WebSocketDisconnect:
        logger.info(
            "Journal WebSocket disconnected",
            extra={"host_id": host_id, "user_id": str(user.id)},
        )
    except HeartbeatExpiredError:
        logger.info(
            "Journal WebSocket expired (idle)",
            extra={"host_id": host_id, "user_id": str(user.id)},
        )
    except Exception as e:  # défense en profondeur
        logger.error(
            "Journal WebSocket error: %s",
            e,
            extra={"host_id": host_id, "user_id": str(user.id)},
        )
        try:
            await websocket.send_json(
                {"type": "error", "message": "Journal stream error"}
            )
        except Exception:
            pass
    finally:
        if process is not None:
            try:
                process.close()
            except Exception:
                pass
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
        logger.info(
            "Journal WebSocket stream closed",
            extra={"host_id": host_id, "user_id": str(user.id)},
        )
