"""Registre d'acknowledgment des messages WebSocket critiques (STORY-164.1 — P2-5, axe C4).

Fiabilise la livraison des messages critiques (décision 5 de l'analyse
STORY-164) :

- les messages critiques (types configurés via ``ws_ack_critical_types``,
  défaut ``DEPLOYMENT_STATUS_CHANGED`` + ``NOTIFICATION_USER``) portent un
  ``id`` UUID et sont enregistrés ici à l'émission ;
- le client accuse réception via ``{"type":"ack","data":{"id":…}}`` →
  :meth:`AckRegistry.ack` retire l'entrée (isolation par utilisateur) ;
- à la **reconnexion du même utilisateur**, les messages non acquittés
  (expirés compris) sont re-diffusés puis purgés
  (:meth:`AckRegistry.redeliver_pending`) — le registre est **par user**
  (point d'attention 5 : la re-diffusion vise les reconnexions du même
  utilisateur, pas le même socket) ;
- un message critique non acquitté au-delà du TTL
  (``ws_ack_ttl_seconds``) **sans reconnexion** est une dégradation
  journalisée en WARNING puis purgé (purge paresseuse à l'accès —
  ``register``/``ack`` ; la mesure Prometheus est différée à STORY-172).

Registre **en mémoire** (process unique, cohérent avec
``connection_managers``) — aucun payload n'est journalisé (rules 40).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from ..config import settings

# STORY-172 (E5/D1) : mesure de la dégradation ack_timeout promise par
# STORY-164.1 (best-effort — ne lève jamais).
from .metrics import record_error

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AckEntry:
    """Message critique en attente d'acquittement.

    Attributes:
        message_id: UUID porté par l'enveloppe (champ ``id``).
        user_id: Utilisateur destinataire (registre par user).
        event_type: Type d'événement WebSocket critique.
        payload: Données du message (jamais journalisées).
        emitted_at: Horodatage d'émission (base du TTL).
    """

    message_id: str
    user_id: str
    event_type: str
    payload: dict
    emitted_at: datetime


class AckRegistry:
    """Registre en mémoire des messages critiques en attente d'ack.

    Thread-safety : coroutinier unique — protégé par un ``asyncio.Lock``
    pour les accès concurrents entre canaux/broadcasts.
    """

    def __init__(self, ttl_seconds: Optional[int] = None) -> None:
        """Initialise le registre.

        Args:
            ttl_seconds: TTL des entrées (défaut : settings
                ``ws_ack_ttl_seconds``) ; paramétrable pour les tests.
        """
        if ttl_seconds is None:
            ttl_seconds = settings.ws_ack_ttl_seconds
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._entries: dict[str, AckEntry] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Type critique
    # ------------------------------------------------------------------

    @staticmethod
    def is_critical_type(event_type: object) -> bool:
        """Indique si un type d'événement est critique (ack requis).

        Liste **configurable** (décision 5) — les streaming logs,
        heartbeats et toasts sont exclus par conception (aucun ``id``
        généré pour eux, donc aucune tempête d'acks sur les flux).

        Args:
            event_type: Type d'événement (``WebSocketEventType`` ou str).

        Returns:
            True si le type fait partie de ``ws_ack_critical_types``.
        """
        # ``WebSocketEventType`` (mixin str) : ``str(enum)`` rendrait
        # "WebSocketEventType.X" — la valeur est extraite explicitement.
        value = getattr(event_type, "value", event_type)
        return str(value) in settings.ws_ack_critical_types

    # ------------------------------------------------------------------
    # Cycle de vie des entrées
    # ------------------------------------------------------------------

    def _is_expired(self, entry: AckEntry, now: datetime) -> bool:
        return now - entry.emitted_at > timedelta(seconds=self._ttl_seconds)

    async def purge_expired(self, now: Optional[datetime] = None) -> int:
        """Purge paresseuse des entrées expirées non acquittées.

        Chaque entrée purgée est une **dégradation journalisée** WARNING
        (message critique non acquitté au-delà du TTL, sans reconnexion) —
        mesure Prometheus différée à STORY-172. Jamais de payload dans les
        logs (rules 40).

        Args:
            now: Horloge injectable (tests), défaut ``utcnow``.

        Returns:
            Nombre d'entrées purgées.
        """
        reference = now or datetime.utcnow()
        purged = 0
        async with self._lock:
            expired_ids = [
                message_id
                for message_id, entry in self._entries.items()
                if self._is_expired(entry, reference)
            ]
            for message_id in expired_ids:
                entry = self._entries.pop(message_id)
                purged += 1
                # STORY-172 : la dégradation ack_timeout promise par
                # STORY-164.1 est désormais mesurée (best-effort — le helper
                # ne lève jamais, la purge ne doit pas échouer pour une
                # métrique). Série :
                # windflow_websocket_errors_total{error_type="ack_timeout"}.
                record_error("ack_timeout")
                logger.warning(
                    "Critical WebSocket message unacknowledged beyond TTL — dropped",
                    extra={
                        "message_id": entry.message_id,
                        "user_id": entry.user_id,
                        "event_type": entry.event_type,
                        "ttl_seconds": self._ttl_seconds,
                        "degradation": "ack_timeout",
                    },
                )
        return purged

    async def register(
        self,
        message_id: str,
        user_id: str,
        event_type: str,
        payload: Optional[dict] = None,
    ) -> None:
        """Enregistre un message critique émis, en attente d'acquittement.

        Déclenche la purge paresseuse des entrées expirées avant stockage.

        Args:
            message_id: UUID porté par l'enveloppe.
            user_id: Utilisateur destinataire.
            event_type: Type d'événement critique.
            payload: Données du message (re-diffusées telles quelles).
        """
        await self.purge_expired()
        entry = AckEntry(
            message_id=str(message_id),
            user_id=str(user_id),
            event_type=str(event_type),
            payload=dict(payload or {}),
            emitted_at=datetime.utcnow(),
        )
        async with self._lock:
            self._entries[entry.message_id] = entry
        logger.debug(
            "Critical WebSocket message registered for ack",
            extra={
                "message_id": entry.message_id,
                "user_id": entry.user_id,
                "event_type": entry.event_type,
            },
        )

    async def ack(self, message_id: str, user_id: str) -> bool:
        """Acquitte un message critique (message retiré du registre).

        Isolation entre utilisateurs : un ack n'est accepté que s'il
        émane du destinataire de l'entrée (jamais de retrait croisé).

        Args:
            message_id: UUID porté par l'enveloppe.
            user_id: Utilisateur qui accuse réception.

        Returns:
            True si l'entrée existait pour cet utilisateur et a été
            retirée ; False sinon (inconnue, déjà acquittée, déjà purgée
            ou destinataire différent).
        """
        await self.purge_expired()
        async with self._lock:
            entry = self._entries.get(str(message_id))
            if entry is None:
                return False
            if entry.user_id != str(user_id):
                logger.warning(
                    "WebSocket ack rejected — user mismatch",
                    extra={
                        "message_id": str(message_id),
                        "ack_user_id": str(user_id),
                        "event_type": entry.event_type,
                    },
                )
                return False
            del self._entries[str(message_id)]
        logger.debug(
            "Critical WebSocket message acknowledged",
            extra={
                "message_id": str(message_id),
                "user_id": str(user_id),
                "event_type": entry.event_type,
            },
        )
        return True

    async def redeliver_pending(self, user_id: str) -> list[AckEntry]:
        """Retourne les messages non acquittés d'un utilisateur, puis les purge.

        Appelé à la **reconnexion du même utilisateur** (canal général) :
        les entrées non acquittées — expirées comprises, la purge
        paresseuse n'est PAS déclenchée ici pour laisser une chance à la
        re-diffusion post-TTL — sont retirées du registre et retournées à
        l'appelant pour re-diffusion (``{"type", "data", "id"}``).

        Isolation : seules les entrées du ``user_id`` demandé sont
        retournées (le user B ne reçoit jamais les critiques du user A).

        Args:
            user_id: Utilisateur qui se reconnecte.

        Returns:
            Liste des entrées à re-diffuser (ordre d'émission).
        """
        uid = str(user_id)
        async with self._lock:
            pending = sorted(
                (e for e in self._entries.values() if e.user_id == uid),
                key=lambda e: e.emitted_at,
            )
            for entry in pending:
                del self._entries[entry.message_id]
        if pending:
            logger.info(
                "Re-delivering unacknowledged critical WebSocket message(s) "
                "after reconnect",
                extra={
                    "user_id": uid,
                    "count": len(pending),
                    "event_types": [e.event_type for e in pending],
                },
            )
        return pending

    def pending_count(self) -> int:
        """Nombre d'entrées en attente (introspection / tests)."""
        return len(self._entries)


# Instance module-level — cohérent avec ``manager``/``user_manager``
# (process unique, registre mémoire par user).
ack_registry = AckRegistry()
