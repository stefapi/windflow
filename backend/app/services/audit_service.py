"""Service métier de l'audit trail (STORY-125.1).

Centralise toute la logique d'audit : écriture best-effort masquée,
consultation filtrée paginée (consommée par l'endpoint admin
STORY-125.3) et purge par âge selon la rétention configurable. Les
points d'émission (STORY-125.2) ne doivent qu'appeler ``log()`` /
``log_from_request()`` — aucune logique d'audit côté HTTP.

Sécurité (rules 40, spec 15 § Audit trail) :
- **Masquage systématique à l'écriture** : ``_sanitize_details``
  remplace par ``***`` la valeur de toute clé dont le nom (lowercase)
  contient un marqueur sensible (password, token, secret, key,
  credential, authorization, cookie), récursivement sur dicts/lists —
  garantie structurelle : aucun appelant ne peut persister un secret ;
- **Best-effort structurel** : ``log()`` ne lève **jamais** — toute
  exception est attrapée (``audit.write_failed`` loggé avec action et
  resource_type, **jamais** le contenu de ``details``) et la ligne est
  perdue : l'action métier continue (l'échec d'audit ne doit jamais
  faire échouer l'action auditée) ;
- **Logs** : action, ids et comptages uniquement — jamais de valeurs
  de contexte.

Persistance : écriture DB directe (pas d'event Redis dédié —
arbitrage STORY-125 n°9) ; ``created_at`` en naive UTC pour les
comparaisons SQL SQLite (pattern ``api_key_service``).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import AsyncSessionLocal
from ..models.audit_log import AuditLog

if TYPE_CHECKING:
    from fastapi import Request

    from ..models.user import User

logger = logging.getLogger(__name__)

# Masque substitué à toute valeur sensible (même convention que
# schemas.deployment._mask_sensitive_values).
MASKED_VALUE = "***"

# Longueur maximale d'une valeur de ``details`` persistée (borne
# anti-abus — les payloads démesurés sont tronqués, pas rejetés :
# l'audit ne doit jamais faire échouer l'action métier).
MAX_DETAIL_VALUE_LENGTH = 512


def _utcnow_naive() -> datetime:
    """UTC now en naive — exclusif pour les clauses SQL (bind SQLite)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_naive_utc(value: datetime) -> datetime:
    """Convertit un datetime aware en naive UTC (comparaison SQLite)."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class AuditService:
    """Service de l'audit trail (statique async) : écriture best-effort
    masquée, consultation filtrée paginée, purge par rétention."""

    _SENSITIVE_KEY_MARKERS = (
        "password",
        "token",
        "secret",
        "key",
        "credential",
        "authorization",
        "cookie",
    )

    # ------------------------------------------------------------------
    # Masquage (garantie structurelle AC 5)
    # ------------------------------------------------------------------

    @classmethod
    def _sanitize_details(
        cls, details: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Retourne une copie de ``details`` sans aucune valeur sensible.

        Copie défensive (l'entrée n'est jamais mutée) : la valeur de
        toute clé dont le nom — inspecté en lowercase — contient un
        marqueur sensible est remplacée par ``***`` ; la récursion
        s'applique aux dicts imbriqués et aux listes ; les valeurs
        string trop longues sont tronquées (borne anti-abus).
        """
        if details is None:
            return None
        return cls._sanitize_mapping(details)

    @classmethod
    def _sanitize_mapping(cls, mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Masque les entrées sensibles d'un niveau de dict."""
        sanitized: Dict[str, Any] = {}
        for key, value in mapping.items():
            key_lower = str(key).lower()
            if any(marker in key_lower for marker in cls._SENSITIVE_KEY_MARKERS):
                sanitized[key] = MASKED_VALUE
            else:
                sanitized[key] = cls._sanitize_value(value)
        return sanitized

    @classmethod
    def _sanitize_value(cls, value: Any) -> Any:
        """Sanitise récursivement une valeur non clé (dict/list/scalaire)."""
        if isinstance(value, dict):
            return cls._sanitize_mapping(value)
        if isinstance(value, (list, tuple)):
            return [cls._sanitize_value(item) for item in value]
        if isinstance(value, str) and len(value) > MAX_DETAIL_VALUE_LENGTH:
            return value[:MAX_DETAIL_VALUE_LENGTH]
        return value

    # ------------------------------------------------------------------
    # Écriture (AC 4 : best-effort, jamais d'exception propagée)
    # ------------------------------------------------------------------

    @staticmethod
    async def log(
        action: str,
        *,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> None:
        """Persiste une ligne d'audit — **ne lève jamais** (AC 4).

        ``details`` est systématiquement passé par ``_sanitize_details``
        avant persistance (AC 5 — garantie structurelle, quel que soit
        l'appelant). En cas d'échec DB : ``audit.write_failed`` loggé
        (action/resource_type/erreur — jamais ``details``) et la ligne
        est perdue (pas de file d'attente dans cette story).

        Args:
            action: Action auditée (catalogue spec 15 — ``user.login``,
                ``stack.deleted``…).
            user_id: Acteur (None : acteur système ou inconnu).
            organization_id: Organisation concernée (None : globale).
            resource_type: Type de la cible (``stack``, ``container``…).
            resource_id: Identifiant de la cible.
            details: Contexte JSON — masqué avant persistance.
            ip_address: IP source.
            correlation_id: Correlation ID du middleware.
            db: Session à réutiliser ; si absente, une session courte
                est ouverte via ``AsyncSessionLocal`` (utile hors
                requête ou quand la session métier est en échec).
        """
        entry = AuditLog(
            action=action,
            user_id=user_id,
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=AuditService._sanitize_details(details),
            ip_address=ip_address,
            correlation_id=correlation_id,
        )
        try:
            if db is not None:
                db.add(entry)
                await db.commit()
            else:
                async with AsyncSessionLocal() as session:
                    session.add(entry)
                    await session.commit()
        except Exception as exc:  # best-effort : jamais propagée (AC 4)
            logger.error(
                "audit.write_failed action=%s resource_type=%s error=%s",
                action,
                resource_type,
                exc,
            )
            if db is not None:
                try:
                    await db.rollback()
                except Exception:  # pragma: no cover - rollback déjà mort
                    pass

    @staticmethod
    async def log_from_request(
        request: "Request",
        action: str,
        *,
        user: Optional["User"] = None,
        organization_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        db: Optional[AsyncSession] = None,
    ) -> None:
        """Émet une ligne d'audit depuis un contexte de requête HTTP.

        Helper des endpoints (STORY-125.2) : extrait ``ip_address``
        (``request.client.host``, ``"unknown"`` sinon — pas de
        traitement ``X-Forwarded-For`` à date, limite documentée derrière
        proxy) et ``correlation_id`` (posé par le middleware, rules 45),
        puis délègue à ``log()`` (best-effort, masqué).

        Args:
            request: Requête FastAPI courante.
            action: Action auditée (catalogue spec 15).
            user: Utilisateur authentifié acteur de l'action (None :
                acteur système — ex. login échoué sur user inconnu).
            organization_id: Organisation concernée par l'action (à
                résoudre côté endpoint selon son scopé).
            resource_type: Type de la cible.
            resource_id: Identifiant de la cible.
            details: Contexte JSON — masqué avant persistance.
            db: Session à réutiliser (sinon session courte).
        """
        ip_address = request.client.host if request.client else "unknown"
        correlation_id = getattr(request.state, "correlation_id", None)
        await AuditService.log(
            action,
            user_id=user.id if user is not None else None,
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            correlation_id=correlation_id,
            db=db,
        )

    # ------------------------------------------------------------------
    # Consultation (consommée par STORY-125.3)
    # ------------------------------------------------------------------

    @staticmethod
    async def list_entries(
        db: AsyncSession,
        *,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        since: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[AuditLog], int]:
        """Liste les lignes d'audit filtrées, paginées (ordre
        ``created_at`` décroissant).

        Les bornes de pagination/sensibilité des filtres sont posées
        côté endpoint (STORY-125.3, super_admin) — le service ne filtre
        pas par rôle (la garde est HTTP).

        Args:
            db: Session de base de données async.
            user_id: Filtre par acteur.
            action: Filtre par action exacte.
            resource_type: Filtre par type de cible.
            since: Borne inférieure inclusive sur ``created_at``.
            skip: Offset de pagination.
            limit: Taille de page.

        Returns:
            Tuple ``(lignes de la page, total filtré)``.
        """
        conditions = []
        if user_id is not None:
            conditions.append(AuditLog.user_id == user_id)
        if action is not None:
            conditions.append(AuditLog.action == action)
        if resource_type is not None:
            conditions.append(AuditLog.resource_type == resource_type)
        if since is not None:
            conditions.append(AuditLog.created_at >= _to_naive_utc(since))

        rows_stmt = select(AuditLog)
        count_stmt = select(func.count()).select_from(AuditLog)
        if conditions:
            rows_stmt = rows_stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        total: int = (await db.execute(count_stmt)).scalar_one()
        rows = (
            (
                await db.execute(
                    rows_stmt.order_by(AuditLog.created_at.desc())
                    .offset(skip)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total

    # ------------------------------------------------------------------
    # Rétention (consommée par STORY-125.3)
    # ------------------------------------------------------------------

    @staticmethod
    async def purge_expired(db: AsyncSession) -> int:
        """Supprime les lignes au-delà de la rétention configurée.

        ``AUDIT_RETENTION_DAYS`` None (défaut) = conservation
        indéfinie : no-op immédiat (aucune requête delete émise).
        Purge par **âge uniquement** — jamais de purge sélective par
        acteur (inamovible). Implémentation consommée par la boucle
        lifespan de STORY-125.3.

        Args:
            db: Session de base de données async.

        Returns:
            Nombre de lignes supprimées.
        """
        retention_days = settings.audit_retention_days
        if retention_days is None:
            return 0

        cutoff = _utcnow_naive() - timedelta(days=retention_days)
        result = cast(
            CursorResult,
            await db.execute(
                delete(AuditLog)
                .where(AuditLog.created_at < cutoff)
                .execution_options(synchronize_session=False)
            ),
        )
        removed = result.rowcount or 0
        await db.commit()
        if removed:
            logger.info(
                "audit.purged retention_days=%d removed=%d",
                retention_days,
                removed,
            )
        return removed
