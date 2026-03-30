"""
Configuration Celery avec Beat pour les tâches planifiées.

Usage:
    celery -A backend.app.celery_app worker --beat --loglevel=info
"""

import logging
import os

from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger(__name__)

# Configuration broker (Redis par défaut)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "windflow",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Tâches prédéfinies avec Celery Beat
celery_app.conf.beat_schedule = {
    "cleanup-logs-daily": {
        "task": "windflow.tasks.cleanup_logs",
        "schedule": crontab(hour=2, minute=0),  # Tous les jours à 2h
        "args": (),
    },
    "health-check-targets": {
        "task": "windflow.tasks.health_check_targets",
        "schedule": crontab(minute="*/5"),  # Toutes les 5 minutes
        "args": (),
    },
    "retry-pending-deployments": {
        "task": "windflow.tasks.retry_pending_deployments",
        "schedule": crontab(minute="*/10"),  # Toutes les 10 minutes
        "args": (),
    },
}


# --- Définition des tâches Celery ---


@celery_app.task(name="windflow.tasks.cleanup_logs")
def cleanup_logs():
    """Nettoyage des logs anciens."""
    logger.info("Exécution tâche planifiée : nettoyage des logs")
    # Import tardif pour éviter les imports circulaires
    import asyncio
    from datetime import datetime, timedelta

    from .database import db as database
    from .models.deployment import Deployment

    async def _cleanup():
        async with database.session_factory() as db:
            cutoff = datetime.utcnow() - timedelta(days=30)
            # Nettoyage des logs de déploiements anciens
            from sqlalchemy import update

            await db.execute(
                update(Deployment)
                .where(Deployment.created_at < cutoff)
                .where(Deployment.logs.isnot(None))
                .values(logs=None)
            )
            await db.commit()
            logger.info(f"Logs nettoyés pour les déploiements avant {cutoff}")

    asyncio.run(_cleanup())
    return {"status": "success", "task": "cleanup_logs"}


@celery_app.task(name="windflow.tasks.health_check_targets")
def health_check_targets():
    """Vérification de la santé des targets via TCP reachability probe."""
    logger.info("Exécution tâche planifiée : vérification santé targets")
    import asyncio

    async def _check():
        from .database import db as database
        from .services.target_service import TargetService

        async with database.session_factory() as db:
            results = await TargetService.check_all_health(db)
            return results

    result = asyncio.run(_check())
    return {"status": "success", "task": "health_check_targets", "results": result}


@celery_app.task(name="windflow.tasks.retry_pending_deployments")
def retry_pending_deployments():
    """Relance des déploiements en attente."""
    logger.info("Exécution tâche planifiée : retry déploiements pending")
    import asyncio

    from .tasks.background_tasks import retry_pending_deployments_async

    asyncio.run(retry_pending_deployments_async())
    return {"status": "success", "task": "retry_pending_deployments"}
