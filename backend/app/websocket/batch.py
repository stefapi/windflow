"""Canal WebSocket ``/ws/batch/{batch_id}`` — progression des opérations
groupées (STORY-164.2 — P2-5, axes C3/C4).

Canal **émetteur-ready** (décision 7 de l'analyse STORY-164) : il n'existe
aucune orchestration batch en backend aujourd'hui (vérifié — aucune
occurrence de ``batch_id`` hors ce module). Le canal est donc livré avec :

- un manager de connexions dédié par ``batch_id`` (réutilise
  :class:`~app.websocket.connection_managers.ConnectionManager`) ;
- une fonction d'émission testée :func:`broadcast_batch_event`, sur le
  modèle de ``_broadcast_deployment_event`` (timestamp auto + manager +
  dispatch plugins), diffusant les phases ``start`` / ``progress`` /
  ``complete`` / ``error`` (spec 09 § WebSocket — même enveloppe
  ``type``/``data`` que les autres canaux) ;

**Branchement futur** (documenté — évite le « contrat dormant ») : la
première alimentation réelle est attendue par STORY-173
(``POST /compute/check-updates`` → ``batch_id``) puis par la mise à jour
groupée multi-Apps (``POST /apps/batch-update``, Roadmap). Ces
orchestrateurs appelleront ``broadcast_batch_event(batch_id, phase, data)``
à chaque étape — aucun autre branchement n'est nécessaire.

Le déclenchement d'une opération groupée passe par l'API REST
RBAC-protégée ; ce canal de **suivi** requiert le rôle viewer minimum
(décision 2 de l'analyse STORY-164).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User
from .connection_managers import ConnectionManager, user_manager
from .heartbeat import (
    HeartbeatExpiredError,
    periodic_ping,
    receive_with_expiry,
)

logger = logging.getLogger(__name__)

# Manager dédié aux abonnés par batch_id (clé : batch_id, modèle
# ConnectionManager — dict id → set[WebSocket], purge des connexions
# mortes incluse).
batch_manager = ConnectionManager()

# Phases canoniques du canal (spec 09 § WebSocket — batch update et
# check-updates diffusent start / progress / complete / error).
BATCH_PHASES = ("start", "progress", "complete", "error")


async def broadcast_batch_event(batch_id: str, phase: str, data: dict) -> None:
    """Diffuse un événement de progression d'une opération groupée.

    Modèle ``_broadcast_deployment_event`` (``broadcasting.py``) :
    timestamp auto si absent, enveloppe ``{"type": phase, "data": …}``,
    broadcast aux abonnés du ``batch_id`` puis dispatch aux plugins WS.
    Fonction d'émission « émetteur-ready » — les orchestrateurs batch
    futurs (STORY-173 check-updates, batch-update Apps) l'appellent à
    chaque étape.

    Args:
        batch_id: Identifiant de l'opération groupée (clé du canal).
        phase: Phase de l'événement — ``start``, ``progress``,
            ``complete`` ou ``error`` (spec 09).
        data: Charge utile de l'événement (ex. ``{"batch_id": …,
            "total": 3}`` pour ``start`` ; résumé
            ``{total, succeeded, failed, skipped}`` pour ``complete``).
    """
    if phase not in BATCH_PHASES:
        raise ValueError(
            f"Unknown batch phase {phase!r}: expected one of {BATCH_PHASES}"
        )

    event_data = dict(data)
    event_data.setdefault("batch_id", batch_id)
    if "timestamp" not in event_data:
        event_data["timestamp"] = datetime.utcnow().isoformat()

    message = {"type": phase, "data": event_data}

    await batch_manager.broadcast_to_deployment(batch_id, message)
    await user_manager.dispatch_to_plugins(phase, event_data)

    logger.debug(
        "Batch event broadcast",
        extra={"batch_id": batch_id, "phase": phase},
    )


async def batch_websocket_endpoint(
    websocket: WebSocket,
    batch_id: str,
    user: User,
    session: AsyncSession,  # noqa: ARG001 — signature homogène des canaux
) -> None:
    """Canal de suivi d'une opération groupée (abonnement au flux).

    Auth/RBAC : réalisés **avant accept** par la route
    (``get_current_user_ws`` + ``ensure_role_ws`` viewer, STORY-122.6).
    Le handler ne fait qu'enregistrer la connexion auprès du manager
    (elle recevra les ``broadcast_batch_event`` du batch) puis maintient
    la connexion (heartbeat + expiration — STORY-164.1). Aucune
    validation d'existence du ``batch_id`` n'est possible : les batchs
    ne sont pas persistés (livraison émetteur-ready) — l'abonnement
    précède potentiellement le démarrage de l'opération.

    Messages serveur :
    - subscribed: ``{"type": "subscribed", "batch_id": …}``
    - start/progress/complete/error: événements diffusés par
      :func:`broadcast_batch_event` (enveloppe ``type``/``data``)
    - pong: ``{"type": "pong", "timestamp": …}``
    """
    channel = f"batch:{batch_id}"

    # ConnectionManager.connect fait l'accept (pattern deployment_logs —
    # jamais de double accept).
    await batch_manager.connect(websocket, batch_id)
    await websocket.send_json({"type": "subscribed", "batch_id": batch_id})

    # STORY-164.1 : ping serveur périodique + expiration des connexions
    # muettes (modèle deployment_logs).
    heartbeat_task: asyncio.Task | None = None
    try:
        heartbeat_task = asyncio.create_task(periodic_ping(websocket, channel))

        while True:
            data = await receive_with_expiry(websocket, channel, user_id=str(user.id))
            if data == "ping":
                await websocket.send_json(
                    {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                )

    except WebSocketDisconnect:
        logger.info(
            "Batch WebSocket disconnected",
            extra={"batch_id": batch_id, "user_id": str(user.id)},
        )
    except HeartbeatExpiredError:
        logger.info(
            "Batch WebSocket expired (idle)",
            extra={"batch_id": batch_id, "user_id": str(user.id)},
        )
    finally:
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        await batch_manager.disconnect(websocket, batch_id)
