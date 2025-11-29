"""
Tâches Celery pour les déploiements.

Gère les déploiements asynchrones, rollbacks, et nettoyage
avec retry automatique et gestion d'erreurs.
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from uuid import UUID

from backend.app.celery_app import celery_app
from backend.app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="backend.app.tasks.deployment_tasks.deploy_stack",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def deploy_stack(
    self,
    deployment_id: str,
    stack_id: str,
    target_id: str,
    user_id: str,
    configuration: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Déploie une stack sur une cible avec mise à jour du statut.

    Args:
        self: Context Celery (bind=True)
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
    from pathlib import Path
    import asyncio

    logger.info(
        f"Début du déploiement {deployment_id} du stack {stack_id} "
        f"sur target {target_id} par user {user_id}"
    )

    async def update_deployment_status(status, error_message=None, logs=None):
        """Helper pour mettre à jour le statut du déploiement."""
        async with AsyncSessionLocal() as db:
            await DeploymentService.update_status(
                db, deployment_id, status, error_message, logs, user_id
            )

    try:
        # Fonction async pour gérer le déploiement
        async def execute_deployment():
            async with AsyncSessionLocal() as db:
                # Mise à jour: démarrage du déploiement
                await DeploymentService.update_status(
                    db,
                    deployment_id,
                    DeploymentStatus.DEPLOYING,
                    logs="[INFO] Démarrage du déploiement..."
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
                    logger.info("Mode déploiement: Docker container simple")
                    await DeploymentService.update_status(
                        db, deployment_id, DeploymentStatus.DEPLOYING,
                        logs="[INFO] Mode déploiement: Docker container simple"
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
                        logs=f"[SUCCESS] Container déployé avec succès\nContainer ID: {output}"
                    )

                    return {
                        "deployment_id": deployment_id,
                        "status": "success",
                        "message": "Container déployé avec succès",
                        "stack_id": stack_id,
                        "stack_name": stack.name,
                        "target_id": target_id,
                        "container_name": container_name,
                        "container_id": output,
                        "deployment_type": "docker",
                        "started_at": datetime.utcnow().isoformat(),
                        "completed_at": datetime.utcnow().isoformat(),
                        "task_id": self.request.id,
                        "retry_count": self.request.retries
                    }

                else:
                    # === DÉPLOIEMENT DOCKER-COMPOSE ===
                    logger.info("Mode déploiement: Docker Compose")
                    await DeploymentService.update_status(
                        db, deployment_id, DeploymentStatus.DEPLOYING,
                        logs="[INFO] Mode déploiement: Docker Compose"
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
                        logs=f"[SUCCESS] Déploiement terminé avec succès\n{output}"
                    )

                    return {
                        "deployment_id": deployment_id,
                        "status": "success",
                        "message": "Stack déployée avec succès",
                        "stack_id": stack_id,
                        "stack_name": stack.name,
                        "target_id": target_id,
                        "project_name": project_name,
                        "compose_file": str(compose_file),
                        "deployment_type": "docker-compose",
                        "started_at": datetime.utcnow().isoformat(),
                        "completed_at": datetime.utcnow().isoformat(),
                        "task_id": self.request.id,
                        "retry_count": self.request.retries,
                        "output": output
                    }

        # Exécuter la fonction async
        result = asyncio.run(execute_deployment())

        logger.info(f"Déploiement {deployment_id} terminé avec succès")
        return result

    except Exception as e:
        logger.error(f"Déploiement {deployment_id} échoué: {e}")

        # Mettre à jour le statut en FAILED
        asyncio.run(update_deployment_status(
            DeploymentStatus.FAILED,
            error_message=str(e),
            logs=f"[ERROR] Erreur lors du déploiement: {str(e)}\nRetry {self.request.retries}/{self.max_retries}"
        ))

        # Retry automatique géré par Celery
        raise


@celery_app.task(
    bind=True,
    name="backend.app.tasks.deployment_tasks.rollback_deployment",
    max_retries=2,
    default_retry_delay=30
)
def rollback_deployment(
    self,
    deployment_id: str,
    user_id: str,
    reason: str = "Manual rollback"
) -> Dict[str, Any]:
    """
    Effectue un rollback d'un déploiement.

    Args:
        self: Context Celery
        deployment_id: ID du déploiement à rollback
        user_id: ID de l'utilisateur qui demande le rollback
        reason: Raison du rollback

    Returns:
        Résultat du rollback

    Raises:
        Exception: En cas d'erreur de rollback
    """
    logger.info(f"Starting rollback of deployment {deployment_id}: {reason}")

    try:
        # TODO: Implémenter le rollback réel
        # from backend.app.services.deployment_service import DeploymentService
        # async with get_db() as db:
        #     service = DeploymentService(db)
        #     result = await service.rollback(deployment_id)

        result = {
            "deployment_id": deployment_id,
            "status": "rolled_back",
            "message": f"Deployment rolled back: {reason}",
            "rolled_back_at": datetime.utcnow().isoformat(),
            "task_id": self.request.id,
            "reason": reason
        }

        logger.info(f"Rollback of deployment {deployment_id} completed")

        # Publier un événement de rollback
        # await publish_event(Event(
        #     event_type=EventType.DEPLOYMENT_ROLLED_BACK,
        #     aggregate_id=UUID(deployment_id),
        #     aggregate_type="deployment",
        #     user_id=UUID(user_id),
        #     payload=result
        # ))

        return result

    except Exception as e:
        logger.error(f"Rollback of deployment {deployment_id} failed: {e}")
        raise


@celery_app.task(
    name="backend.app.tasks.deployment_tasks.cleanup_old_deployments"
)
def cleanup_old_deployments(days: int = 90) -> Dict[str, Any]:
    """
    Nettoie les déploiements anciens (tâche périodique).

    Args:
        days: Nombre de jours avant de considérer un déploiement comme ancien

    Returns:
        Résultat du nettoyage avec nombre de déploiements supprimés
    """
    logger.info(f"Starting cleanup of deployments older than {days} days")

    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # TODO: Implémenter le nettoyage réel
        # from backend.app.services.deployment_service import DeploymentService
        # async with get_db() as db:
        #     service = DeploymentService(db)
        #     deleted_count = await service.cleanup_old(cutoff_date)

        deleted_count = 0  # Simulation

        result = {
            "status": "completed",
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date.isoformat(),
            "message": f"Cleaned up {deleted_count} old deployments"
        }

        logger.info(f"Cleanup completed: {deleted_count} deployments removed")

        return result

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise


@celery_app.task(
    bind=True,
    name="backend.app.tasks.deployment_tasks.validate_deployment",
    max_retries=1
)
def validate_deployment(
    self,
    deployment_id: str,
    validation_checks: list
) -> Dict[str, Any]:
    """
    Valide un déploiement après exécution.

    Args:
        self: Context Celery
        deployment_id: ID du déploiement à valider
        validation_checks: Liste des checks à effectuer

    Returns:
        Résultat de la validation
    """
    logger.info(f"Validating deployment {deployment_id}")

    try:
        # TODO: Implémenter la validation réelle
        # - Health checks des services
        # - Vérification des ports ouverts
        # - Tests de connectivité
        # - Validation des logs

        results = {
            "deployment_id": deployment_id,
            "validation_status": "passed",
            "checks": validation_checks,
            "passed_checks": len(validation_checks),
            "failed_checks": 0,
            "validated_at": datetime.utcnow().isoformat()
        }

        logger.info(f"Validation of deployment {deployment_id} passed")

        return results

    except Exception as e:
        logger.error(f"Validation of deployment {deployment_id} failed: {e}")
        raise


@celery_app.task(
    bind=True,
    name="backend.app.tasks.deployment_tasks.scale_deployment",
    max_retries=2
)
def scale_deployment(
    self,
    deployment_id: str,
    service_name: str,
    replicas: int
) -> Dict[str, Any]:
    """
    Scale un service dans un déploiement.

    Args:
        self: Context Celery
        deployment_id: ID du déploiement
        service_name: Nom du service à scaler
        replicas: Nombre de réplicas souhaité

    Returns:
        Résultat du scaling
    """
    logger.info(
        f"Scaling service {service_name} in deployment {deployment_id} "
        f"to {replicas} replicas"
    )

    try:
        # TODO: Implémenter le scaling réel selon la cible
        # - Docker Compose: docker-compose scale
        # - Docker Swarm: docker service scale
        # - Kubernetes: kubectl scale

        result = {
            "deployment_id": deployment_id,
            "service_name": service_name,
            "replicas": replicas,
            "status": "scaled",
            "scaled_at": datetime.utcnow().isoformat()
        }

        logger.info(f"Service {service_name} scaled to {replicas} replicas")

        return result

    except Exception as e:
        logger.error(f"Scaling failed: {e}")
        raise


@celery_app.task(
    name="backend.app.tasks.deployment_tasks.retry_pending_deployments"
)
def retry_pending_deployments(
    max_age_minutes: int = 2,
    timeout_minutes: int = 60
) -> Dict[str, Any]:
    """
    Tâche périodique pour réessayer les déploiements PENDING bloqués.

    Cette tâche s'exécute périodiquement (configurée dans Celery Beat) pour :
    1. Détecter les déploiements bloqués en PENDING depuis > max_age_minutes
    2. Réessayer ceux qui sont récents (< timeout_minutes)
    3. Marquer comme FAILED ceux qui sont trop anciens (> timeout_minutes)

    Args:
        max_age_minutes: Âge minimum pour considérer un PENDING comme bloqué (défaut: 2min)
        timeout_minutes: Âge maximum avant de marquer comme FAILED (défaut: 60min)

    Returns:
        Statistiques de recovery (retried, failed, skipped, errors)
    """
    import asyncio
    from backend.app.services.deployment_service import DeploymentService
    from backend.app.database import AsyncSessionLocal

    logger.info(
        f"Exécution de la tâche périodique de recovery des déploiements PENDING "
        f"(max_age={max_age_minutes}min, timeout={timeout_minutes}min)"
    )

    async def run_recovery():
        """Fonction async pour exécuter le recovery."""
        async with AsyncSessionLocal() as db:
            stats = await DeploymentService.recover_pending_deployments(
                db,
                max_age_minutes=max_age_minutes,
                timeout_minutes=timeout_minutes
            )
            return stats

    try:
        # Exécuter la fonction async
        stats = asyncio.run(run_recovery())

        result = {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "statistics": stats,
            "message": (
                f"Recovery terminé: {stats['retried']} réessayés, "
                f"{stats['failed']} marqués FAILED, {stats['errors']} erreurs"
            )
        }

        logger.info(
            f"Tâche de recovery terminée avec succès: {stats['retried']} retried, "
            f"{stats['failed']} failed, {stats['errors']} errors"
        )

        return result

    except Exception as e:
        logger.error(f"Erreur lors de la tâche de recovery: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "message": f"Erreur lors du recovery: {str(e)}"
        }
