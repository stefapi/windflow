"""
Tâches asynchrones pour WindFlow.

Ce module contient les tâches asynchrones basées sur asyncio:
- background_tasks: Déploiements asynchrones avec retry automatique
"""

from backend.app.tasks.background_tasks import (
    deploy_stack_async,
    retry_pending_deployments_async,
)

__all__ = [
    "deploy_stack_async",
    "retry_pending_deployments_async",
]
