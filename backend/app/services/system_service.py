"""Service système — checks de santé et de readiness (STORY-129).

Centralise la logique de health/readiness hors de la couche HTTP :
consommée par le router ``/api/v1/system`` **et** par le ``/health``
racine historique (délegation, zéro duplication — arbitrage n°2 de
l'analyse STORY-129).

Contrat de readiness (AC 4 — anti-fingerprinting) : le payload de
``get_readiness`` ne contient **ni version applicative, ni
environnement, ni détail de connexion** — uniquement ``status``, l'état
booléen/texte par check et les révisions Alembic courantes
(``current``/``head``, identifiants de schéma internes non sensibles,
utiles au diagnostic).
"""

import logging
from typing import Any

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncConnection

from ..config import settings
from ..database import db, get_alembic_config

logger = logging.getLogger("windflow.system")


class SystemService:
    """Checks système réutilisables (health historique + readiness).

    Toutes les méthodes sont best-effort : une dépendance indisponible
    produit un check ``unhealthy``, jamais une exception remontée — le
    endpoint doit toujours répondre (contrat orchestrateur).
    """

    @staticmethod
    async def get_health() -> dict[str, Any]:
        """Santé applicative — comportement du ``/health`` racine historique.

        Réplique exactement le contrat de l'endpoint racine (non-régression,
        arbitrage n°2) : clés ``status``/``version``/``environment``/
        ``services{database{status,type}, rate_limiter{status}?}``, ``503``
        porté par l'appelant si ``status != "healthy"``.

        Returns:
            dict: Payload de santé historique (version et environnement
            inclus — contrat préservé à l'identique).
        """
        health_status: dict[str, Any] = {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.environment,
            "services": {},
        }

        # Check database
        db_healthy = await db.health_check()
        health_status["services"]["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "type": "sqlite" if "sqlite" in settings.database_url else "postgresql",
        }

        # Check rate limiter (Redis optionnel — même condition que /health racine)
        if settings.rate_limit_enabled and settings.rate_limit_storage_url:
            redis_healthy = await SystemService._check_redis()
            health_status["services"]["rate_limiter"] = {
                "status": "healthy" if redis_healthy else "unhealthy",
            }

        if not db_healthy:
            health_status["status"] = "unhealthy"

        return health_status

    @staticmethod
    async def get_readiness() -> tuple[dict[str, Any], int]:
        """Readiness — signal de démarrage pour les orchestrateurs.

        Checks (arbitrage n°5 — Redis seul comme dépendance optionnelle) :
        - ``database`` : ``SELECT 1`` via ``db.health_check()`` ;
        - ``migrations`` : révision courante (table ``alembic_version``)
          comparée strictement au ``head`` du ScriptDirectory (arbitrage
          n°7 — base non versionnée → check ``unhealthy``) ;
        - ``redis`` : uniquement si ``rate_limit_enabled`` +
          ``rate_limit_storage_url`` (absent sinon).

        Returns:
            tuple: ``(payload, http_code)`` — ``200`` si tous les checks
            présents sont sains, ``503`` sinon. Le payload ne contient
            aucune information de fingerprinting (AC 4).
        """
        checks: dict[str, Any] = {
            "database": await SystemService._database_check(),
            "migrations": await SystemService._migrations_check(),
        }

        if settings.rate_limit_enabled and settings.rate_limit_storage_url:
            checks["redis"] = {
                "status": (
                    "healthy" if await SystemService._check_redis() else "unhealthy"
                )
            }

        ready = all(
            check.get("status") in ("healthy", "ok") for check in checks.values()
        )
        payload = {"status": "ready" if ready else "unready", "checks": checks}
        code = 200 if ready else 503

        logger.info(
            "system.ready status=%s database=%s migrations=%s redis=%s",
            payload["status"],
            checks["database"]["status"],
            checks["migrations"]["status"],
            checks.get("redis", {}).get("status", "skipped"),
        )
        return payload, code

    # --- Checks unitaires ---------------------------------------------------

    @staticmethod
    async def _database_check() -> dict[str, str]:
        """Check base de données — ``SELECT 1`` via ``db.health_check()``.

        Returns:
            dict: ``{"status": "healthy"|"unhealthy"}``.
        """
        try:
            healthy = await db.health_check()
            return {"status": "healthy" if healthy else "unhealthy"}
        except Exception:  # best-effort : jamais d'exception remontée
            logger.warning("system.check database failed", exc_info=True)
            return {"status": "unhealthy"}

    @staticmethod
    async def _migrations_check() -> dict[str, Any]:
        """Check « migrations appliquées » — ``current == head`` (arbitrage n°7).

        La révision courante est lue via ``MigrationContext`` sur l'engine
        applicatif (table ``alembic_version``) et comparée strictement au
        ``head`` du ``ScriptDirectory`` Alembic. Une base sans table
        ``alembic_version`` produit ``current: null`` → check ``unhealthy``
        (un ``/ready`` prêt avec un schéma non migré serait un signal
        mensonger).

        Returns:
            dict: ``{"status": "ok"|"pending", "current": str|None,
            "head": str|None}``.
        """
        try:
            if db.engine is None:
                return {"status": "pending", "current": None, "head": None}

            async with db.engine.connect() as conn:
                current = await SystemService._current_revision(conn)
            head = ScriptDirectory.from_config(get_alembic_config()).get_current_head()

            status = "ok" if current is not None and current == head else "pending"
            return {"status": status, "current": current, "head": head}
        except Exception:  # best-effort : jamais d'exception remontée
            logger.warning("system.check migrations failed", exc_info=True)
            return {"status": "pending", "current": None, "head": None}

    @staticmethod
    async def _current_revision(conn: AsyncConnection) -> str | None:
        """Révision Alembic courante depuis une connexion async ouverte.

        Args:
            conn: Connexion async active sur l'engine applicatif.

        Returns:
            str | None: Révision courante (``None`` si la base n'est pas
            versionnée — pas de table ``alembic_version``).
        """

        def _has_alembic_table(sync_conn: Any) -> bool:
            return "alembic_version" in set(inspect(sync_conn).get_table_names())

        def _get_revision(sync_conn: Any) -> str | None:
            return MigrationContext.configure(sync_conn).get_current_revision()

        if not await conn.run_sync(_has_alembic_table):
            return None
        return await conn.run_sync(_get_revision)

    @staticmethod
    async def _check_redis() -> bool:
        """Ping Redis (stockage du rate limiter) — fermé proprement.

        Pattern du ``/health`` racine historique : client jetable depuis
        ``rate_limit_storage_url``, jamais d'exception remontée.

        Returns:
            bool: ``True`` si le ping réussit.
        """
        import redis.asyncio as redis

        try:
            redis_client = redis.from_url(settings.rate_limit_storage_url)
            await redis_client.ping()
            await redis_client.close()
            return True
        except Exception:
            return False
