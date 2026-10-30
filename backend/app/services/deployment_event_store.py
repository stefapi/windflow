"""Store de persistance des événements de déploiement (STORY-167).

Isole toute la logique SQL des ``deployment_events`` (aucune dépendance
HTTP) derrière une classe unique réutilisée par :

- le pipeline (double écriture dans ``DeploymentService.update_status``
  — même transaction que le changement de statut, AC 3) ;
- l'endpoint paginé ``GET /deployments/{id}/events`` (filtres + COUNT
  au même scoping, AC 2) ;
- la rétention (boucle lifespan + action scheduler
  ``deployment_events.purge`` — purge par cutoff idempotente, AC 4).

Patterns : ``scheduler_execution_store.py`` (purge par cutoff avec
horloge injectable — time travel des tests AC 4 ; COUNT aux mêmes
filtres que la liste).

Sécurité (rules 40) : le payload ``data`` est limité aux champs non
sensibles par construction (liste blanche au moment de l'append) ;
aucune valeur de message n'est journalisée (identifiants uniquement).
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.deployment_event import (
    DeploymentEvent,
    DeploymentEventLevel,
    DeploymentEventType,
)

logger = logging.getLogger(__name__)

# Clés autorisées dans le payload ``data`` (liste blanche — rules 40) :
# identifiants et métriques uniquement, jamais de variables
# d'environnement, configuration ni secret.
# STORY-170.2 : ``code``/``plugin``/``reason`` portent la trace typée
# des refus de gate pre-deploy (code GATE_* + nom de plugin + raison
# lisible — la raison provient du SDK gate, jamais de secret).
_ALLOWED_DATA_KEYS: frozenset[str] = frozenset(
    {
        "old_status",
        "new_status",
        "container_id",
        "duration_seconds",
        "step",
        "host_id",
        "error",
        "code",
        "plugin",
        "reason",
    }
)

# Domaines fermés spec 06 (validation au moment de l'append — defense in
# depth : l'endpoint valide déjà via Query(pattern=...)).
_VALID_EVENT_TYPES: frozenset[str] = frozenset(
    member.value for member in DeploymentEventType
)
_VALID_LEVELS: frozenset[str] = frozenset(
    member.value for member in DeploymentEventLevel
)


def _sanitize_data(data: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Filtre le payload ``data`` sur la liste blanche des clés non sensibles.

    Args:
        data: Payload brut proposé par l'émetteur.

    Returns:
        Copie ne contenant que les clés autorisées (``None`` si vide) —
        jamais de variable d'environnement ni de secret (rules 40).
    """
    if not data:
        return None
    sanitized = {key: value for key, value in data.items() if key in _ALLOWED_DATA_KEYS}
    return sanitized or None


class DeploymentEventStore:
    """Persistance des événements de déploiement (spec 06 — STORY-167).

    Toutes les méthodes acceptent une session externe : l'append dans
    ``update_status`` partage la transaction du changement de statut
    (cohérence garantie — un échec d'insert annule le statut) ; la purge
    ouvre sa propre session courte via :attr:`_session_factory`.
    """

    def __init__(
        self,
        session_factory: Optional[Callable[..., Any]] = None,
        *,
        clock: Callable[[], datetime] = datetime.utcnow,
    ) -> None:
        """Initialise le store.

        Args:
            session_factory: Factory de sessions async (défaut :
                ``app.database.AsyncSessionLocal`` — résolue paresseux
                pour éviter un import cyclique au chargement du module).
            clock: Horloge injectable (défaut ``datetime.utcnow`` naïf
                UTC, décision d'analyse 5) — pattern freezegun/time
                travel pour les tests de rétention (AC 4).
        """
        self._session_factory = session_factory
        self._clock = clock

    # --- Écriture (double écriture pipeline) --------------------------------

    async def append_event(
        self,
        db: AsyncSession,
        deployment_id: str,
        event_type: str,
        level: str,
        message: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> DeploymentEvent:
        """Insère un événement dans la session courante (sans commit).

        La transaction reste portée par l'appelant : appelé depuis
        ``update_status`` avant son ``commit``, l'événement est persisté
        **dans la même transaction** que le changement de statut (AC 3 —
        un échec annule le statut).

        Args:
            db: Session SQLAlchemy (transaction de l'appelant).
            deployment_id: FK du déploiement concerné.
            event_type: Valeur du domaine fermé spec 06.
            level: Valeur du domaine fermé spec 06.
            message: Ligne de journal lisible (jamais de secret).
            data: Payload additionnel — filtré sur la liste blanche
                (rules 40).

        Returns:
            L'entité insérée (PK générée, non encore commitée).

        Raises:
            ValueError: Si ``event_type`` ou ``level`` hors domaine fermé
                spec 06 (validation stricte — defense in depth).
        """
        if event_type not in _VALID_EVENT_TYPES:
            raise ValueError(
                f"event_type invalide : {event_type!r} "
                f"(domaines fermés spec 06 : {sorted(_VALID_EVENT_TYPES)})"
            )
        if level not in _VALID_LEVELS:
            raise ValueError(
                f"level invalide : {level!r} "
                f"(domaines fermés spec 06 : {sorted(_VALID_LEVELS)})"
            )

        event = DeploymentEvent(
            deployment_id=deployment_id,
            event_type=event_type,
            level=level,
            message=message,
            data=_sanitize_data(data),
            created_at=self._clock(),
        )
        db.add(event)
        # Pas de commit ici : la transaction appartient à l'appelant
        # (même transaction que le statut dans update_status — AC 3).
        logger.debug(
            "DeploymentEvent en file pour le déploiement %s (event_type=%s, "
            "level=%s)",
            deployment_id,
            event_type,
            level,
        )
        return event

    # --- Lecture (endpoint paginé) ------------------------------------------

    async def list_for_deployment(
        self,
        db: AsyncSession,
        deployment_id: str,
        *,
        event_type: Optional[str] = None,
        level: Optional[str] = None,
        after: Optional[datetime] = None,
        before: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[DeploymentEvent], int]:
        """Liste paginée des events d'un déploiement, tri chronologique.

        Tri ``created_at ASC, id ASC`` (décision d'analyse 4 : l'ordre
        chronologique du déroulé pulling → … → success/error est le
        besoin exprimé par AC 2 — divergence assumée avec
        ``list_executions_global`` en DESC).

        Args:
            db: Session SQLAlchemy.
            deployment_id: FK du déploiement (isolation stricte : les
                events des autres déploiements n'apparaissent jamais).
            event_type: Filtre optionnel (domaine fermé spec 06).
            level: Filtre optionnel (domaine fermé spec 06).
            after: Borne inférieure inclusive (``created_at >= after``).
            before: Borne supérieure inclusive (``created_at <= before``).
            page: Page 1-indexée.
            per_page: Taille de page (1-100, validée par l'endpoint).

        Returns:
            Tuple ``(items, total)`` — ``total`` issu d'un ``COUNT`` aux
            **mêmes filtres** que la liste (pattern spec 09, pas
            d'oracle de pagination).
        """
        filters = [DeploymentEvent.deployment_id == deployment_id]
        if event_type is not None:
            filters.append(DeploymentEvent.event_type == event_type)
        if level is not None:
            filters.append(DeploymentEvent.level == level)
        if after is not None:
            filters.append(DeploymentEvent.created_at >= after)
        if before is not None:
            filters.append(DeploymentEvent.created_at <= before)

        count_stmt = select(func.count()).select_from(DeploymentEvent).where(*filters)
        total = int((await db.execute(count_stmt)).scalar() or 0)

        list_stmt = (
            select(DeploymentEvent)
            .where(*filters)
            .order_by(DeploymentEvent.created_at.asc(), DeploymentEvent.id.asc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        items = list((await db.execute(list_stmt)).scalars().all())
        return items, total

    # --- Rétention (AC 4) ---------------------------------------------------

    async def purge_expired(self, retention_days: int) -> int:
        """Purge les events au-delà de la rétention (cutoff ``created_at``).

        Idempotente et sûre en exécution simultanée (boucle lifespan +
        cron scheduler) : purge par cutoff uniquement, jamais
        conditionnelle à un état — deux exécutions concurrentes se
        resolvent en no-op pour la seconde (lignes déjà supprimées).

        Args:
            retention_days: Rétention en jours (≥ 1 — ``None`` est géré
                par l'appelant : boucle lifespan non démarrée).

        Returns:
            Le nombre de lignes supprimées.
        """
        cutoff = self._clock() - timedelta(days=retention_days)
        async with self._get_session() as session:
            result = await session.execute(
                delete(DeploymentEvent).where(DeploymentEvent.created_at < cutoff)
            )
            await session.commit()
            # rowcount : accès défensif (CursorResult uniquement — mypy,
            # pattern scheduler_execution_store).
            removed = int(getattr(result, "rowcount", 0) or 0)
        if removed:
            logger.info(
                "DeploymentEvents purge : %d ligne(s) supprimée(s) " "(rétention %d j)",
                removed,
                retention_days,
            )
        return removed

    def _get_session(self) -> Any:
        """Retourne un context manager de session (factory ou défaut DB).

        La factory par défaut est résolue paresseusement (import module
        ``app.database`` — évite l'import cyclique au chargement).
        """
        if self._session_factory is not None:
            return self._session_factory()
        from ..database import AsyncSessionLocal

        return AsyncSessionLocal()
