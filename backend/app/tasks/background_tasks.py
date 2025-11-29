"""
Tâches asynchrones en background (fallback quand Celery n'est pas disponible).

Ce module fournit une alternative à Celery pour exécuter des tâches
asynchrones directement dans le backend FastAPI. Il est utilisé comme
fallback lorsque Celery n'est pas disponible (worker down, broker down, etc.).

Important:
    - Ces tâches s'exécutent dans le processus backend
    - Pas de garantie de persistence en cas de crash
    - Pas de retry automatique comme Celery
    - Adapté pour développement ou petites charges
"""

import logging
import asyncio
from typing import Dict, Any
from datetime import datetime
from uuid import UUID
from pathlib import Path

logger = logging.getLogger(__name__)


async def deploy_stack_async(
    deployment_id: str,
    stack_id: str,
    target_id: str,
    user_id: str,
    configuration: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Version asyncio du déploiement de stack (fallback Celery).

    Cette fonction réplique la logique de deploy_stack de Celery
    mais s'exécute directement dans le processus backend via asyncio.

    Args:
        deployment_id: ID du déploiement
        stack_id: ID de la stack à déployer
        target_id: ID de la cible de déploiement
        user_id: ID de l'utilisateur qui lance le déploiement
        configuration: Configuration du déploiement

    Returns:
        Résultat du déploiement avec statut et détails

    Raises:
        Exception: En cas d'erreur de déploiement
    """
    from backend.app.services.docker_compose_service import DockerComposeService
    from backend.app.services.docker_service import DockerService
    from backend.app.services.deployment_service import DeploymentService
    from backend.app.database import AsyncSessionLocal
    from backend.app.models.stack import Stack
    from backend.app.models.deployment import DeploymentStatus
    from backend.app.schemas.target import TargetType
    from sqlalchemy import select

    logger.info(
        f"[FALLBACK-ASYNCIO] Début du déploiement {deployment_id} "
        f"du stack {stack_id} sur target {target_id} par user {user_id}"
    )

    try:
        async with AsyncSessionLocal() as db:
            # Mise à jour: démarrage du déploiement
            await DeploymentService.update_status(
                db,
                deployment_id,
                DeploymentStatus.DEPLOYING,
                logs="[INFO] Démarrage du déploiement (mode fallback asyncio)..."
            )

            # 1. Charger le stack
            result = await db.execute(
                select(Stack).where(Stack.id == stack_id)
            )
            stack = result.scalar_one_or_none()

            if not stack:
                raise ValueError(f"Stack {stack_id} non trouvé")

            logger.info(f"Stack chargé: {stack.name} v{stack.version}, target_type={stack.target_type}")
            await DeploymentService.update_status(
                db, deployment_id, DeploymentStatus.DEPLOYING,
                logs=f"[INFO] Stack chargé: {stack.name} v{stack.version} (type: {stack.target_type})"
            )

            # Router vers le bon service selon le target_type
            if stack.target_type == TargetType.DOCKER.value:
                # === DÉPLOIEMENT DOCKER SIMPLE ===
                logger.info("[FALLBACK-ASYNCIO] Mode déploiement: Docker container simple")
                await DeploymentService.update_status(
                    db, deployment_id, DeploymentStatus.DEPLOYING,
                    logs="[INFO] Mode déploiement: Docker container simple (asyncio fallback)"
                )

                # 2. Substituer les variables avec DockerService
                docker_service = DockerService()
                final_config = docker_service.substitute_variables(
                    stack.template,
                    configuration
                )

                logger.info("Variables substituées dans le template")
                await DeploymentService.update_status(
                    db, deployment_id, DeploymentStatus.DEPLOYING,
                    logs="[INFO] Variables substituées dans le template"
                )

                # 3. Valider la configuration container
                is_valid, error_msg = docker_service.validate_container_config(final_config)
                if not is_valid:
                    raise ValueError(f"Configuration container invalide: {error_msg}")

                await DeploymentService.update_status(
                    db, deployment_id, DeploymentStatus.DEPLOYING,
                    logs="[INFO] Validation de la configuration container réussie"
                )

                # 4. Déployer le container
                container_name = f"windflow-{deployment_id[:8]}"
                await DeploymentService.update_status(
                    db, deployment_id, DeploymentStatus.DEPLOYING,
                    logs=f"[INFO] Lancement du container {container_name}..."
                )

                success, output = await docker_service.deploy_container(
                    final_config,
                    container_name
                )

                if not success:
                    raise Exception(f"Échec du déploiement: {output}")

                logger.info(f"Container déployé avec succès: {output}")

                # 5. Mise à jour finale: succès
                await DeploymentService.update_status(
                    db,
                    deployment_id,
                    DeploymentStatus.RUNNING,
                    logs=f"[SUCCESS] Container déployé avec succès (asyncio fallback)\nContainer ID: {output}"
                )

                return {
                    "deployment_id": deployment_id,
                    "status": "success",
                    "message": "Container déployé avec succès (asyncio fallback)",
                    "stack_id": stack_id,
                    "stack_name": stack.name,
                    "target_id": target_id,
                    "container_name": container_name,
                    "container_id": output,
                    "deployment_type": "docker",
                    "execution_mode": "asyncio_fallback",
                    "started_at": datetime.utcnow().isoformat(),
                    "completed_at": datetime.utcnow().isoformat()
                }

            else:
                # === DÉPLOIEMENT DOCKER-COMPOSE ===
                logger.info("[FALLBACK-ASYNCIO] Mode déploiement: Docker Compose")
                await DeploymentService.update_status(
                    db, deployment_id, DeploymentStatus.DEPLOYING,
                    logs="[INFO] Mode déploiement: Docker Compose (asyncio fallback)"
                )

                # 2. Substituer les variables dans le template
                compose_service = DockerComposeService()
                final_compose = compose_service.substitute_variables(
                    stack.template,
                    configuration
                )

                logger.info("Variables substituées dans le template")
                await DeploymentService.update_status(
                    db, deployment_id, DeploymentStatus.DEPLOYING,
                    logs="[INFO] Variables substituées dans le template"
                )

                # 3. Valider le compose généré
                is_valid, error_msg = compose_service.validate_compose(final_compose)
                if not is_valid:
                    raise ValueError(f"Compose invalide: {error_msg}")

                await DeploymentService.update_status(
                    db, deployment_id, DeploymentStatus.DEPLOYING,
                    logs="[INFO] Validation du fichier compose réussie"
                )

                # 4. Générer le fichier docker-compose.yml
                deploy_dir = Path(f"/tmp/windflow-deployments/{deployment_id}")
                compose_file = deploy_dir / "docker-compose.yml"

                compose_service.generate_compose_file(final_compose, compose_file)
                logger.info(f"Fichier compose généré: {compose_file}")
                await DeploymentService.update_status(
                    db, deployment_id, DeploymentStatus.DEPLOYING,
                    logs=f"[INFO] Fichier compose généré: {compose_file}"
                )

                # 5. Déployer avec docker-compose
                project_name = f"windflow-{deployment_id[:8]}"
                await DeploymentService.update_status(
                    db, deployment_id, DeploymentStatus.DEPLOYING,
                    logs=f"[INFO] Lancement de docker-compose pour {project_name}..."
                )

                success, output = await compose_service.deploy_compose(
                    compose_file,
                    project_name
                )

                if not success:
                    raise Exception(f"Échec du déploiement: {output}")

                logger.info(f"Déploiement réussi: {output}")

                # 6. Mise à jour finale: succès
                await DeploymentService.update_status(
                    db,
                    deployment_id,
                    DeploymentStatus.RUNNING,
                    logs=f"[SUCCESS] Déploiement terminé avec succès (asyncio fallback)\n{output}"
                )

                return {
                    "deployment_id": deployment_id,
                    "status": "success",
                    "message": "Stack déployée avec succès (asyncio fallback)",
                    "stack_id": stack_id,
                    "stack_name": stack.name,
                    "target_id": target_id,
                    "project_name": project_name,
                    "compose_file": str(compose_file),
                    "deployment_type": "docker-compose",
                    "execution_mode": "asyncio_fallback",
                    "started_at": datetime.utcnow().isoformat(),
                    "completed_at": datetime.utcnow().isoformat(),
                    "output": output
                }

    except Exception as e:
        logger.error(f"[FALLBACK-ASYNCIO] Déploiement {deployment_id} échoué: {e}")

        # Mettre à jour le statut en FAILED
        async with AsyncSessionLocal() as db:
            await DeploymentService.update_status(
                db,
                deployment_id,
                DeploymentStatus.FAILED,
                error_message=str(e),
                logs=f"[ERROR] Erreur lors du déploiement (asyncio fallback): {str(e)}"
            )

        # Re-raise l'exception
        raise


def create_background_task(
    deployment_id: str,
    stack_id: str,
    target_id: str,
    user_id: str,
    configuration: Dict[str, Any]
) -> asyncio.Task:
    """
    Crée une tâche asyncio en arrière-plan pour le déploiement.

    Cette fonction encapsule la création de la tâche asyncio avec
    gestion d'erreurs et logging appropriés.

    Args:
        deployment_id: ID du déploiement
        stack_id: ID de la stack
        target_id: ID de la cible
        user_id: ID de l'utilisateur
        configuration: Configuration du déploiement

    Returns:
        asyncio.Task créée

    Example:
        >>> task = create_background_task(
        >>>     deployment_id=str(deployment.id),
        >>>     stack_id=str(stack_id),
        >>>     target_id=str(target_id),
        >>>     user_id=str(user_id),
        >>>     configuration=merged_variables
        >>> )
    """
    logger.info(
        f"Creating background task for deployment {deployment_id} "
        f"(asyncio fallback mode)"
    )

    # Créer la tâche asyncio
    task = asyncio.create_task(
        deploy_stack_async(
            deployment_id=deployment_id,
            stack_id=stack_id,
            target_id=target_id,
            user_id=user_id,
            configuration=configuration
        )
    )

    # Ajouter un callback pour logger la fin de la tâche
    def task_done_callback(t: asyncio.Task):
        """Callback appelé quand la tâche est terminée."""
        try:
            if t.exception():
                logger.error(
                    f"Background task for deployment {deployment_id} failed: "
                    f"{t.exception()}"
                )
            else:
                result = t.result()
                logger.info(
                    f"Background task for deployment {deployment_id} completed: "
                    f"{result.get('status', 'unknown')}"
                )
        except asyncio.CancelledError:
            logger.warning(f"Background task for deployment {deployment_id} was cancelled")
        except Exception as e:
            logger.error(f"Error in task callback for deployment {deployment_id}: {e}")

    task.add_done_callback(task_done_callback)

    return task


# Storage pour tracking des tâches actives (optionnel)
_active_background_tasks: Dict[str, asyncio.Task] = {}


def track_background_task(deployment_id: str, task: asyncio.Task) -> None:
    """
    Enregistre une tâche background pour tracking.

    Args:
        deployment_id: ID du déploiement
        task: Tâche asyncio à tracker
    """
    _active_background_tasks[deployment_id] = task

    # Callback pour nettoyer le tracking
    def cleanup_callback(t: asyncio.Task):
        if deployment_id in _active_background_tasks:
            del _active_background_tasks[deployment_id]
            logger.debug(f"Cleaned up tracking for deployment {deployment_id}")

    task.add_done_callback(cleanup_callback)


def get_background_task(deployment_id: str) -> asyncio.Task | None:
    """
    Récupère une tâche background active par ID de déploiement.

    Args:
        deployment_id: ID du déploiement

    Returns:
        Tâche asyncio ou None si non trouvée
    """
    return _active_background_tasks.get(deployment_id)


def cancel_background_task(deployment_id: str) -> bool:
    """
    Annule une tâche background active.

    Args:
        deployment_id: ID du déploiement

    Returns:
        True si la tâche a été annulée, False si non trouvée
    """
    task = _active_background_tasks.get(deployment_id)
    if task and not task.done():
        task.cancel()
        logger.info(f"Cancelled background task for deployment {deployment_id}")
        return True

    return False


def get_active_background_tasks_count() -> int:
    """
    Retourne le nombre de tâches background actives.

    Returns:
        Nombre de tâches en cours d'exécution
    """
    return len([t for t in _active_background_tasks.values() if not t.done()])


async def retry_pending_deployments_async(
    max_age_minutes: int = 2,
    timeout_minutes: int = 60
) -> Dict[str, Any]:
    """
    Version asyncio de la tâche de recovery des déploiements PENDING.

    Utilisée comme fallback quand Celery n'est pas disponible.
    Cette fonction réplique exactement le comportement de la tâche Celery
    mais s'exécute directement dans le processus backend via asyncio.

    Args:
        max_age_minutes: Âge minimum pour considérer un PENDING comme bloqué (défaut: 2min)
        timeout_minutes: Âge maximum avant de marquer comme FAILED (défaut: 60min)

    Returns:
        Statistiques de recovery (retried, failed, skipped, errors)
    """
    from backend.app.services.deployment_service import DeploymentService
    from backend.app.database import AsyncSessionLocal
    from datetime import datetime

    logger.info(
        f"[FALLBACK-ASYNCIO] Exécution du recovery des déploiements PENDING "
        f"(max_age={max_age_minutes}min, timeout={timeout_minutes}min)"
    )

    try:
        async with AsyncSessionLocal() as db:
            stats = await DeploymentService.recover_pending_deployments(
                db,
                max_age_minutes=max_age_minutes,
                timeout_minutes=timeout_minutes
            )

            result = {
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "statistics": stats,
                "execution_mode": "asyncio_fallback",
                "message": (
                    f"Recovery terminé (asyncio): {stats['retried']} réessayés, "
                    f"{stats['failed']} marqués FAILED, {stats['errors']} erreurs"
                )
            }

            logger.info(
                f"[FALLBACK-ASYNCIO] Tâche de recovery terminée: {stats['retried']} retried, "
                f"{stats['failed']} failed, {stats['errors']} errors"
            )

            return result

    except Exception as e:
        logger.error(f"[FALLBACK-ASYNCIO] Erreur lors du recovery: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "execution_mode": "asyncio_fallback",
            "error": str(e),
            "message": f"Erreur lors du recovery (asyncio): {str(e)}"
        }


def schedule_recovery_task() -> asyncio.Task:
    """
    Planifie une tâche de recovery des déploiements PENDING.

    Cette fonction crée une tâche asyncio pour le recovery automatique
    des déploiements bloqués en PENDING.

    Returns:
        asyncio.Task créée pour le recovery
    """
    logger.info("Planification de la tâche de recovery des déploiements PENDING (asyncio)")

    task = asyncio.create_task(retry_pending_deployments_async())

    def task_done_callback(t: asyncio.Task):
        """Callback appelé quand la tâche est terminée."""
        try:
            if t.exception():
                logger.error(f"Tâche de recovery échouée: {t.exception()}")
            else:
                result = t.result()
                logger.info(f"Tâche de recovery terminée: {result.get('message', 'unknown')}")
        except asyncio.CancelledError:
            logger.warning("Tâche de recovery annulée")
        except Exception as e:
            logger.error(f"Erreur dans le callback de recovery: {e}")

    task.add_done_callback(task_done_callback)

    return task
