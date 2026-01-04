"""
Service d'orchestration des déploiements avec asyncio.

Remplace Celery pour la gestion des tâches de déploiement asynchrones.
Fournit retry automatique, recovery après crash, et tracking des tâches.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.deployment import Deployment, DeploymentStatus
from ..database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class DeploymentOrchestrator:
    """
    Orchestrateur de déploiements basé sur asyncio.

    Gère le cycle de vie complet des déploiements :
    - Lancement des tâches asyncio
    - Retry automatique avec backoff exponentiel
    - Recovery des tâches après crash
    - Tracking des tâches actives
    """

    # Stockage des tâches actives
    _active_tasks: Dict[str, asyncio.Task] = {}

    # Configuration retry
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 60  # secondes
    MAX_RETRY_DELAY = 600  # 10 minutes

    @classmethod
    async def start_deployment(
        cls,
        deployment_id: str,
        stack_id: str,
        target_id: str,
        user_id: str,
        configuration: Dict[str, Any]
    ) -> asyncio.Task:
        """
        Démarre un déploiement en arrière-plan.

        Args:
            deployment_id: ID du déploiement
            stack_id: ID de la stack
            target_id: ID de la cible
            user_id: ID de l'utilisateur
            configuration: Configuration du déploiement

        Returns:
            Tâche asyncio créée
        """
        logger.info(f"Démarrage du déploiement {deployment_id}")

        # Marquer le démarrage de la tâche
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Deployment).where(Deployment.id == deployment_id)
            )
            deployment = result.scalar_one_or_none()
            if deployment:
                deployment.task_started_at = datetime.utcnow()
                deployment.task_retry_count = 0
                await db.commit()

        # Créer la tâche asyncio
        task = asyncio.create_task(
            cls._execute_deployment_with_retry(
                deployment_id=deployment_id,
                stack_id=stack_id,
                target_id=target_id,
                user_id=user_id,
                configuration=configuration
            )
        )

        # Tracker la tâche
        cls._active_tasks[deployment_id] = task

        # Ajouter callback de nettoyage
        def cleanup_callback(t: asyncio.Task):
            """Nettoie le tracking quand la tâche est terminée."""
            if deployment_id in cls._active_tasks:
                del cls._active_tasks[deployment_id]
                logger.debug(f"Tâche {deployment_id} nettoyée du tracking")

            # Logger le résultat
            try:
                if t.exception():
                    logger.error(f"Déploiement {deployment_id} échoué: {t.exception()}")
                else:
                    result = t.result()
                    logger.info(f"Déploiement {deployment_id} terminé: {result.get('status', 'unknown')}")
            except asyncio.CancelledError:
                logger.warning(f"Déploiement {deployment_id} annulé")
            except Exception as e:
                logger.error(f"Erreur dans le callback du déploiement {deployment_id}: {e}")

        task.add_done_callback(cleanup_callback)

        return task

    @classmethod
    async def _execute_deployment_with_retry(
        cls,
        deployment_id: str,
        stack_id: str,
        target_id: str,
        user_id: str,
        configuration: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Exécute le déploiement avec retry automatique.

        Args:
            deployment_id: ID du déploiement
            stack_id: ID de la stack
            target_id: ID de la cible
            user_id: ID de l'utilisateur
            configuration: Configuration du déploiement

        Returns:
            Résultat du déploiement

        Raises:
            Exception: Si toutes les tentatives échouent
        """
        from ..tasks.background_tasks import deploy_stack_async

        retry_count = 0
        last_error = None

        while retry_count <= cls.MAX_RETRIES:
            try:
                # Mettre à jour le compteur de retry
                if retry_count > 0:
                    async with AsyncSessionLocal() as db:
                        result = await db.execute(
                            select(Deployment).where(Deployment.id == deployment_id)
                        )
                        deployment = result.scalar_one_or_none()
                        if deployment:
                            deployment.task_retry_count = retry_count
                            await db.commit()

                    logger.info(f"Tentative {retry_count}/{cls.MAX_RETRIES} pour {deployment_id}")

                # Exécuter le déploiement
                result = await deploy_stack_async(
                    deployment_id=deployment_id,
                    stack_id=stack_id,
                    target_id=target_id,
                    user_id=user_id,
                    configuration=configuration
                )

                # Succès !
                logger.info(f"Déploiement {deployment_id} réussi après {retry_count} retry(s)")
                return result

            except Exception as e:
                last_error = e
                retry_count += 1

                if retry_count > cls.MAX_RETRIES:
                    # Toutes les tentatives ont échoué
                    logger.error(
                        f"Déploiement {deployment_id} échoué après {cls.MAX_RETRIES} tentatives: {e}"
                    )

                    # Marquer comme FAILED
                    async with AsyncSessionLocal() as db:
                        from ..services.deployment_service import DeploymentService
                        await DeploymentService.update_status(
                            db,
                            deployment_id,
                            DeploymentStatus.FAILED,
                            error_message=f"Échec après {cls.MAX_RETRIES} tentatives: {str(e)}",
                            logs=f"[ERROR] Toutes les tentatives de retry ont échoué\nDernière erreur: {str(e)}"
                        )

                    raise

                # Calculer le délai de retry avec backoff exponentiel
                delay = min(
                    cls.INITIAL_RETRY_DELAY * (2 ** (retry_count - 1)),
                    cls.MAX_RETRY_DELAY
                )

                logger.warning(
                    f"Déploiement {deployment_id} échoué (tentative {retry_count}/{cls.MAX_RETRIES}), "
                    f"retry dans {delay}s: {e}"
                )

                # Attendre avant de réessayer
                await asyncio.sleep(delay)

        # Ne devrait jamais arriver ici
        raise last_error

    @classmethod
    async def recover_pending_deployments(
        cls,
        max_age_minutes: int = 2,
        timeout_minutes: int = 60
    ) -> Dict[str, int]:
        """
        Récupère les déploiements bloqués en PENDING ou DEPLOYING.

        Cette fonction est appelée au démarrage de l'application pour
        récupérer les déploiements qui étaient en cours lors d'un crash.

        Args:
            max_age_minutes: Âge minimum pour considérer un déploiement comme bloqué
            timeout_minutes: Âge maximum avant de marquer comme FAILED

        Returns:
            Statistiques de recovery (retried, failed, skipped, errors)
        """
        logger.info(
            f"Démarrage du recovery des déploiements "
            f"(max_age={max_age_minutes}min, timeout={timeout_minutes}min)"
        )

        stats = {
            "retried": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0
        }

        try:
            async with AsyncSessionLocal() as db:
                # Trouver les déploiements bloqués
                now = datetime.utcnow()
                max_age_threshold = now - timedelta(minutes=max_age_minutes)
                timeout_threshold = now - timedelta(minutes=timeout_minutes)

                result = await db.execute(
                    select(Deployment).where(
                        Deployment.status.in_([
                            DeploymentStatus.PENDING,
                            DeploymentStatus.DEPLOYING
                        ]),
                        Deployment.created_at < max_age_threshold
                    )
                )
                pending_deployments = result.scalars().all()

                logger.info(f"Trouvé {len(pending_deployments)} déploiements à récupérer")

                for deployment in pending_deployments:
                    try:
                        # Vérifier si le déploiement a timeout
                        if deployment.created_at < timeout_threshold:
                            logger.warning(
                                f"Déploiement {deployment.id} timeout "
                                f"(créé il y a {(now - deployment.created_at).total_seconds() / 60:.1f} min)"
                            )

                            deployment.status = DeploymentStatus.FAILED
                            deployment.error_message = (
                                f"Timeout: déploiement bloqué pendant plus de {timeout_minutes} minutes"
                            )
                            deployment.logs = (
                                f"{deployment.logs or ''}\n"
                                f"[ERROR] Déploiement marqué comme FAILED après timeout de {timeout_minutes} min"
                            )
                            await db.commit()
                            stats["failed"] += 1
                            continue

                        # Vérifier si déjà en cours de traitement
                        if deployment.id in cls._active_tasks:
                            task = cls._active_tasks[deployment.id]
                            if not task.done():
                                logger.info(f"Déploiement {deployment.id} déjà en cours, skip")
                                stats["skipped"] += 1
                                continue

                        # Relancer le déploiement
                        logger.info(f"Relance du déploiement {deployment.id}")

                        await cls.start_deployment(
                            deployment_id=deployment.id,
                            stack_id=deployment.stack_id,
                            target_id=deployment.target_id,
                            user_id=str(deployment.organization_id),  # Utiliser l'org comme user_id
                            configuration=deployment.variables
                        )

                        stats["retried"] += 1

                    except Exception as e:
                        logger.error(f"Erreur lors du recovery de {deployment.id}: {e}")
                        stats["errors"] += 1

                logger.info(
                    f"Recovery terminé: {stats['retried']} relancés, "
                    f"{stats['failed']} marqués FAILED, {stats['skipped']} skippés, "
                    f"{stats['errors']} erreurs"
                )

        except Exception as e:
            logger.error(f"Erreur lors du recovery des déploiements: {e}")
            stats["errors"] += 1

        return stats

    @classmethod
    def get_active_task(cls, deployment_id: str) -> Optional[asyncio.Task]:
        """
        Récupère une tâche active par ID de déploiement.

        Args:
            deployment_id: ID du déploiement

        Returns:
            Tâche asyncio ou None si non trouvée
        """
        return cls._active_tasks.get(deployment_id)

    @classmethod
    def cancel_task(cls, deployment_id: str) -> bool:
        """
        Annule une tâche active.

        Args:
            deployment_id: ID du déploiement

        Returns:
            True si la tâche a été annulée, False si non trouvée
        """
        task = cls._active_tasks.get(deployment_id)
        if task and not task.done():
            task.cancel()
            logger.info(f"Tâche {deployment_id} annulée")
            return True

        return False

    @classmethod
    def get_active_tasks_count(cls) -> int:
        """
        Retourne le nombre de tâches actives.

        Returns:
            Nombre de tâches en cours d'exécution
        """
        return len([t for t in cls._active_tasks.values() if not t.done()])

    @classmethod
    def get_all_active_tasks(cls) -> Dict[str, asyncio.Task]:
        """
        Retourne toutes les tâches actives.

        Returns:
            Dictionnaire {deployment_id: task}
        """
        return {
            dep_id: task
            for dep_id, task in cls._active_tasks.items()
            if not task.done()
        }
