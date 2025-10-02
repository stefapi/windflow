"""
Configuration Celery pour WindFlow.

Gère le traitement asynchrone des tâches longues (déploiements,
backups, migrations, etc.) avec retry automatique et dead letter queue.
"""

from typing import Optional
import logging
from celery import Celery
from celery.schedules import crontab

from backend.app.config import settings

logger = logging.getLogger(__name__)

# Initialisation de l'application Celery
celery_app = Celery(
    "windflow",
    broker=settings.celery_broker_url if settings.celery_enabled else None,
    backend=settings.celery_result_backend if settings.celery_enabled else None,
    include=[
        "backend.app.tasks.deployment_tasks",
        "backend.app.tasks.backup_tasks",
        "backend.app.tasks.monitoring_tasks",
    ]
)


class CeleryConfig:
    """Configuration Celery pour WindFlow."""

    # Broker settings
    broker_url = settings.celery_broker_url
    result_backend = settings.celery_result_backend
    broker_connection_retry_on_startup = True

    # Sérialisation
    task_serializer = "json"
    result_serializer = "json"
    accept_content = ["json"]
    timezone = "UTC"
    enable_utc = True

    # Retry policy par défaut
    task_acks_late = True  # ACK après exécution
    task_reject_on_worker_lost = True  # Rejeter si worker crash
    task_default_retry_delay = 60  # 1 minute
    task_max_retries = 3

    # Timeouts
    task_soft_time_limit = 300  # 5 minutes soft limit
    task_time_limit = 600  # 10 minutes hard limit

    # Routes des queues
    task_routes = {
        "backend.app.tasks.deployment_tasks.*": {"queue": "deployments"},
        "backend.app.tasks.backup_tasks.*": {"queue": "backups"},
        "backend.app.tasks.monitoring_tasks.*": {"queue": "monitoring"},
    }

    # Priorités des queues
    task_queue_max_priority = 10
    task_default_priority = 5

    # Dead Letter Queue
    task_reject_on_worker_lost = True
    task_acks_late = True

    # Worker settings
    worker_prefetch_multiplier = 4
    worker_max_tasks_per_child = 1000  # Recycler worker après 1000 tâches
    worker_disable_rate_limits = False

    # Beat scheduler pour tâches périodiques
    beat_schedule = {
        # Health checks toutes les 5 minutes
        "health-check-all-targets": {
            "task": "backend.app.tasks.monitoring_tasks.check_all_targets_health",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "monitoring", "priority": 8}
        },
        # Backup quotidien à 2h du matin
        "daily-backup": {
            "task": "backend.app.tasks.backup_tasks.daily_backup",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": "backups", "priority": 7}
        },
        # Nettoyage des déploiements anciens chaque semaine
        "cleanup-old-deployments": {
            "task": "backend.app.tasks.deployment_tasks.cleanup_old_deployments",
            "schedule": crontab(day_of_week=0, hour=3, minute=0),
            "options": {"queue": "deployments", "priority": 3}
        },
    }

    # Monitoring et métriques
    worker_send_task_events = True
    task_send_sent_event = True
    task_track_started = True

    # Résultats
    result_expires = 3600  # Expiration après 1h
    result_extended = True


# Appliquer la configuration
celery_app.config_from_object(CeleryConfig)


# Event handlers pour logging
@celery_app.task(bind=True)
def debug_task(self):
    """Tâche de debug pour tester Celery."""
    logger.info(f"Request: {self.request!r}")
    return {"status": "ok", "worker": self.request.hostname}


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Configure les tâches périodiques additionnelles."""
    if not settings.celery_enabled:
        logger.info("Celery is disabled, skipping periodic tasks setup")
        return

    logger.info("Celery periodic tasks configured")


# Callbacks pour les événements
@celery_app.task(bind=True, name="task.on_failure")
def on_task_failure(self, exc, task_id, args, kwargs, einfo):
    """Handler appelé en cas d'échec d'une tâche."""
    logger.error(
        f"Task {task_id} failed with exception: {exc}",
        extra={
            "task_id": task_id,
            "args": args,
            "kwargs": kwargs,
            "exception": str(exc)
        }
    )

    # TODO: Publier un événement d'échec via EventBus
    # from backend.app.core.events import publish_event, Event, EventType
    # await publish_event(Event(
    #     event_type=EventType.SYSTEM_ERROR,
    #     payload={"task_id": task_id, "error": str(exc)}
    # ))


@celery_app.task(bind=True, name="task.on_success")
def on_task_success(self, retval, task_id, args, kwargs):
    """Handler appelé en cas de succès d'une tâche."""
    logger.info(
        f"Task {task_id} completed successfully",
        extra={
            "task_id": task_id,
            "result": retval
        }
    )


@celery_app.task(bind=True, name="task.on_retry")
def on_task_retry(self, exc, task_id, args, kwargs, einfo):
    """Handler appelé lors d'un retry."""
    logger.warning(
        f"Task {task_id} is being retried due to: {exc}",
        extra={
            "task_id": task_id,
            "exception": str(exc),
            "retry_count": self.request.retries
        }
    )


def get_celery_app() -> Optional[Celery]:
    """
    Retourne l'instance Celery si activée.

    Returns:
        Instance Celery ou None si désactivé
    """
    if not settings.celery_enabled:
        logger.warning("Celery is not enabled")
        return None

    return celery_app


def get_task_info(task_id: str) -> dict:
    """
    Récupère les informations d'une tâche.

    Args:
        task_id: ID de la tâche

    Returns:
        Informations de la tâche
    """
    if not settings.celery_enabled:
        return {"error": "Celery is not enabled"}

    result = celery_app.AsyncResult(task_id)

    return {
        "task_id": task_id,
        "state": result.state,
        "result": result.result if result.ready() else None,
        "traceback": result.traceback if result.failed() else None,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else False,
        "failed": result.failed() if result.ready() else False,
    }


def revoke_task(task_id: str, terminate: bool = False) -> dict:
    """
    Révoque (annule) une tâche.

    Args:
        task_id: ID de la tâche à annuler
        terminate: Si True, termine brutalement le worker

    Returns:
        Statut de la révocation
    """
    if not settings.celery_enabled:
        return {"error": "Celery is not enabled"}

    celery_app.control.revoke(task_id, terminate=terminate)

    logger.info(f"Task {task_id} revoked (terminate={terminate})")

    return {
        "task_id": task_id,
        "revoked": True,
        "terminated": terminate
    }


def get_active_tasks() -> list:
    """
    Récupère la liste des tâches actives.

    Returns:
        Liste des tâches en cours d'exécution
    """
    if not settings.celery_enabled:
        return []

    inspect = celery_app.control.inspect()
    active = inspect.active()

    if not active:
        return []

    # Flatten le dictionnaire des workers
    tasks = []
    for worker, worker_tasks in active.items():
        for task in worker_tasks:
            task["worker"] = worker
            tasks.append(task)

    return tasks


def get_worker_stats() -> dict:
    """
    Récupère les statistiques des workers.

    Returns:
        Statistiques des workers Celery
    """
    if not settings.celery_enabled:
        return {"error": "Celery is not enabled"}

    inspect = celery_app.control.inspect()

    return {
        "stats": inspect.stats(),
        "active_queues": inspect.active_queues(),
        "registered_tasks": inspect.registered(),
        "scheduled_tasks": inspect.scheduled(),
        "reserved_tasks": inspect.reserved(),
    }


if __name__ == "__main__":
    # Permet de lancer le worker avec: python -m backend.app.celery_app worker
    celery_app.start()
