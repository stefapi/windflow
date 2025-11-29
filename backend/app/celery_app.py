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


def get_celery_broker_url() -> Optional[str]:
    """
    Retourne l'URL du broker Celery.

    - Si celery_broker_url est définie, l'utilise directement
    - Sinon, dérive depuis database_url selon celery_broker_type

    Returns:
        URL du broker Celery ou None si Celery désactivé
    """
    if not settings.celery_enabled:
        return None

    # URL explicite fournie
    if settings.celery_broker_url:
        return settings.celery_broker_url

    # Dérivation depuis database_url
    if settings.celery_broker_type == "database":
        # Convertir l'URL async PostgreSQL en URL sync pour Celery
        db_url = settings.database_url

        # SQLite ne peut pas être utilisé comme broker Celery
        if db_url.startswith("sqlite"):
            logger.warning(
                "SQLite ne peut pas être utilisé comme broker Celery. "
                "Utilisez PostgreSQL ou configurez Redis."
            )
            return None

        # Conversion asyncpg -> psycopg2 pour Celery
        if "postgresql+asyncpg" in db_url:
            broker_url = db_url.replace("postgresql+asyncpg", "db+postgresql+psycopg2")
        elif "postgresql" in db_url and "psycopg2" not in db_url:
            broker_url = f"db+postgresql+psycopg2{db_url.split('postgresql')[1]}"
        else:
            broker_url = f"db+{db_url}"

        logger.info(f"Using database as Celery broker: {broker_url.split('@')[0]}@***")
        return broker_url

    elif settings.celery_broker_type == "redis":
        logger.warning("celery_broker_type=redis but no celery_broker_url provided")
        return None

    return None


def get_celery_result_backend() -> Optional[str]:
    """
    Retourne l'URL du result backend Celery.

    Returns:
        URL du result backend ou None si Celery désactivé
    """
    if not settings.celery_enabled:
        return None

    # URL explicite fournie
    if settings.celery_result_backend:
        return settings.celery_result_backend

    # Dérivation depuis database_url
    if settings.celery_broker_type == "database":
        db_url = settings.database_url

        if db_url.startswith("sqlite"):
            logger.warning("SQLite ne peut pas être utilisé comme result backend Celery")
            return None

        # Conversion asyncpg -> psycopg2
        if "postgresql+asyncpg" in db_url:
            result_url = db_url.replace("postgresql+asyncpg", "db+postgresql+psycopg2")
        elif "postgresql" in db_url and "psycopg2" not in db_url:
            result_url = f"db+postgresql+psycopg2{db_url.split('postgresql')[1]}"
        else:
            result_url = f"db+{db_url}"

        logger.info(f"Using database as Celery result backend: {result_url.split('@')[0]}@***")
        return result_url

    return None


# Initialisation de l'application Celery
celery_app = Celery(
    "windflow",
    broker=get_celery_broker_url(),
    backend=get_celery_result_backend(),
    include=[
        "backend.app.tasks.deployment_tasks",
        "backend.app.tasks.backup_tasks",
        "backend.app.tasks.monitoring_tasks",
    ]
)


class CeleryConfig:
    """Configuration Celery pour WindFlow."""

    # Broker settings - utilise les fonctions de dérivation
    broker_url = get_celery_broker_url()
    result_backend = get_celery_result_backend()
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
        # Retry des déploiements PENDING toutes les 5 minutes
        "retry-pending-deployments": {
            "task": "backend.app.tasks.deployment_tasks.retry_pending_deployments",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "deployments", "priority": 9},
            "kwargs": {
                "max_age_minutes": 2,  # Déploiements PENDING > 2min sont bloqués
                "timeout_minutes": 60   # Déploiements PENDING > 60min sont FAILED
            }
        },
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


def is_celery_available(timeout: float = 1.0) -> bool:
    """
    Vérifie si au moins un worker Celery est disponible.

    Cette fonction effectue un ping des workers actifs pour déterminer
    si Celery est opérationnel. Elle est utilisée pour décider du
    fallback vers asyncio en cas d'indisponibilité.

    Args:
        timeout: Timeout en secondes pour la vérification (défaut: 1.0s)

    Returns:
        True si au moins un worker est disponible, False sinon

    Example:
        >>> if is_celery_available():
        >>>     task = deploy_stack.delay(...)
        >>> else:
        >>>     asyncio.create_task(execute_deployment_async(...))
    """
    if not settings.celery_enabled:
        logger.debug("Celery is disabled in settings")
        return False

    try:
        # Utiliser inspect() pour vérifier les workers actifs
        inspect = celery_app.control.inspect(timeout=timeout)

        # Tenter de récupérer les stats des workers
        stats = inspect.stats()

        # Si stats est None ou vide, aucun worker n'est disponible
        if stats is None or len(stats) == 0:
            logger.warning("No Celery workers available")
            return False

        # Au moins un worker est disponible
        worker_count = len(stats)
        logger.info(f"Celery is available with {worker_count} worker(s)")
        return True

    except Exception as e:
        # En cas d'erreur (timeout, connexion refusée, etc.)
        logger.warning(
            f"Failed to check Celery availability: {e}",
            extra={"exception_type": type(e).__name__}
        )
        return False


if __name__ == "__main__":
    # Permet de lancer le worker avec: python -m backend.app.celery_app worker
    celery_app.start()
