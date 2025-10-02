"""
Tâches asynchrones Celery pour WindFlow.

Ce module contient toutes les tâches asynchrones exécutées par les workers Celery:
- deployment_tasks: Déploiements et rollbacks
- backup_tasks: Sauvegardes et restaurations
- monitoring_tasks: Health checks et métriques
"""

from backend.app.tasks.deployment_tasks import (
    deploy_stack,
    rollback_deployment,
    cleanup_old_deployments,
)

from backend.app.tasks.backup_tasks import (
    backup_database,
    daily_backup,
    restore_backup,
)

from backend.app.tasks.monitoring_tasks import (
    check_target_health,
    check_all_targets_health,
    collect_metrics,
)

__all__ = [
    # Deployment tasks
    "deploy_stack",
    "rollback_deployment",
    "cleanup_old_deployments",
    # Backup tasks
    "backup_database",
    "daily_backup",
    "restore_backup",
    # Monitoring tasks
    "check_target_health",
    "check_all_targets_health",
    "collect_metrics",
]
