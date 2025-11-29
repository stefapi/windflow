"""
Service métier pour gestion des déploiements.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from jinja2 import Template, TemplateSyntaxError
import logging

from ..models.deployment import Deployment, DeploymentStatus
from ..models.stack import Stack
from ..schemas.deployment import DeploymentCreate, DeploymentUpdate
from ..config import settings
from .deployment_events import deployment_events

logger = logging.getLogger(__name__)


class DeploymentService:
    """Service de gestion des déploiements."""

    @staticmethod
    def _generate_deployment_name(stack: Stack) -> str:
        """Génère un nom de déploiement unique basé sur le stack et un timestamp."""
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        return f"{stack.name}-{timestamp}"

    @staticmethod
    def _merge_variables(stack_variables: Dict[str, Any], user_variables: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge les variables par défaut du stack avec celles fournies par l'utilisateur.

        Args:
            stack_variables: Variables définies dans le stack avec leurs defaults
            user_variables: Variables fournies par l'utilisateur (peuvent override les defaults)

        Returns:
            Dict contenant les variables mergées
        """
        merged = {}

        # D'abord, extraire les valeurs par défaut du stack
        for var_name, var_config in stack_variables.items():
            if isinstance(var_config, dict) and 'default' in var_config:
                merged[var_name] = var_config['default']
            else:
                # Si pas de structure complexe, utiliser la valeur directement
                merged[var_name] = var_config

        # Ensuite, appliquer les overrides de l'utilisateur
        if user_variables:
            merged.update(user_variables)

        return merged

    @staticmethod
    def _render_template(template_data: Any, variables: Dict[str, Any]) -> Any:
        """
        Rend un template (dict, list ou str) en remplaçant les variables Jinja2.

        Args:
            template_data: Données du template (peut être dict, list, str)
            variables: Variables à substituer

        Returns:
            Template rendu avec variables substituées
        """
        if isinstance(template_data, dict):
            return {
                key: DeploymentService._render_template(value, variables)
                for key, value in template_data.items()
            }
        elif isinstance(template_data, list):
            return [
                DeploymentService._render_template(item, variables)
                for item in template_data
            ]
        elif isinstance(template_data, str):
            try:
                # Rendre la chaîne avec Jinja2
                template = Template(template_data)
                return template.render(**variables)
            except TemplateSyntaxError:
                # Si erreur de syntaxe, retourner la chaîne originale
                return template_data
        else:
            # Pour les autres types (int, bool, None, etc.), retourner tel quel
            return template_data

    @staticmethod
    async def _get_stack(db: AsyncSession, stack_id: str) -> Optional[Stack]:
        """Récupère un stack par son ID."""
        result = await db.execute(
            select(Stack).where(Stack.id == stack_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(db: AsyncSession, deployment_id: str) -> Optional[Deployment]:
        """Récupère un déploiement par son ID."""
        result = await db.execute(
            select(Deployment).where(Deployment.id == deployment_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_organization(
        db: AsyncSession,
        organization_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Deployment]:
        """Liste les déploiements d'une organisation."""
        result = await db.execute(
            select(Deployment)
            .where(Deployment.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_name(
        db: AsyncSession,
        organization_id: str,
        name: str
    ) -> Optional[Deployment]:
        """Récupère un déploiement par son nom dans une organisation."""
        result = await db.execute(
            select(Deployment).where(
                and_(
                    Deployment.organization_id == organization_id,
                    Deployment.name == name
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[Deployment]:
        """Liste tous les déploiements."""
        result = await db.execute(
            select(Deployment)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(
        db: AsyncSession,
        deployment_data: DeploymentCreate,
        organization_id: str,
        user_id: str
    ) -> Deployment:
        """
        Crée un nouveau déploiement et déclenche le déploiement asynchrone.

        Cette méthode génère automatiquement :
        - Le nom du déploiement si non fourni
        - La configuration en rendant le template du stack avec les variables
        - Les variables mergées (defaults du stack + overrides utilisateur)
        - Déclenche la tâche Celery de déploiement si activé

        Args:
            db: Session de base de données
            deployment_data: Données de création du déploiement
            organization_id: ID de l'organisation
            user_id: ID de l'utilisateur créateur

        Returns:
            Deployment créé

        Raises:
            ValueError: Si le stack n'existe pas
        """
        # 1. Charger le stack
        stack = await DeploymentService._get_stack(db, deployment_data.stack_id)
        if not stack:
            raise ValueError(f"Stack {deployment_data.stack_id} non trouvé")

        # 2. Générer le nom si absent
        deployment_name = deployment_data.name
        if not deployment_name:
            deployment_name = DeploymentService._generate_deployment_name(stack)

        # 3. Merger les variables (defaults du stack + overrides utilisateur)
        merged_variables = DeploymentService._merge_variables(
            stack.variables or {},
            deployment_data.variables
        )

        # 4. Générer le config en rendant le template avec les variables
        config = deployment_data.config
        if not config:
            config = DeploymentService._render_template(
                stack.template,
                merged_variables
            )

        # 5. Créer le déploiement avec statut initial PENDING
        deployment_dict = {
            "name": deployment_name,
            "stack_id": deployment_data.stack_id,
            "target_id": deployment_data.target_id,
            "config": config,
            "variables": merged_variables,
            "organization_id": organization_id,
            "status": DeploymentStatus.PENDING
        }

        deployment = Deployment(**deployment_dict)
        db.add(deployment)
        await db.commit()
        await db.refresh(deployment)

        # 6. Déclencher la tâche de déploiement (Celery ou fallback asyncio)
        # Vérifier si Celery est activé ET disponible
        from ..celery_app import is_celery_available

        celery_available = settings.celery_enabled and is_celery_available()

        if celery_available:
            # Option 1: Celery est disponible - utilisation prioritaire
            try:
                from ..tasks.deployment_tasks import deploy_stack

                # Mettre à jour le statut à DEPLOYING
                deployment.status = DeploymentStatus.DEPLOYING
                await db.commit()
                await db.refresh(deployment)

                # Lancer la tâche asynchrone Celery
                task = deploy_stack.delay(
                    deployment_id=str(deployment.id),
                    stack_id=str(deployment.stack_id),
                    target_id=str(deployment.target_id),
                    user_id=str(user_id),
                    configuration=merged_variables
                )

                logger.info(
                    f"Tâche Celery de déploiement lancée: {task.id} "
                    f"pour deployment {deployment.id}"
                )
            except Exception as e:
                logger.error(f"Erreur lors du lancement de la tâche Celery: {e}")
                # En cas d'erreur Celery, fallback vers asyncio
                logger.warning(f"Fallback vers asyncio pour deployment {deployment.id}")

                from ..tasks.background_tasks import create_background_task, track_background_task

                deployment.status = DeploymentStatus.DEPLOYING
                await db.commit()
                await db.refresh(deployment)

                # Créer et tracker la tâche background
                task = create_background_task(
                    deployment_id=str(deployment.id),
                    stack_id=str(deployment.stack_id),
                    target_id=str(deployment.target_id),
                    user_id=str(user_id),
                    configuration=merged_variables
                )
                track_background_task(str(deployment.id), task)

                logger.info(
                    f"Tâche asyncio de déploiement lancée (fallback) "
                    f"pour deployment {deployment.id}"
                )
        else:
            # Option 2: Celery non disponible - fallback asyncio direct
            logger.info(
                f"Celery non disponible (enabled={settings.celery_enabled}, "
                f"available={celery_available}), utilisation fallback asyncio "
                f"pour deployment {deployment.id}"
            )

            from ..tasks.background_tasks import create_background_task, track_background_task

            # Mettre à jour le statut à DEPLOYING
            deployment.status = DeploymentStatus.DEPLOYING
            await db.commit()
            await db.refresh(deployment)

            # Créer et tracker la tâche background asyncio
            task = create_background_task(
                deployment_id=str(deployment.id),
                stack_id=str(deployment.stack_id),
                target_id=str(deployment.target_id),
                user_id=str(user_id),
                configuration=merged_variables
            )
            track_background_task(str(deployment.id), task)

            logger.info(
                f"Tâche asyncio de déploiement lancée "
                f"pour deployment {deployment.id}"
            )

        return deployment

    @staticmethod
    async def update(
        db: AsyncSession,
        deployment_id: str,
        deployment_data: DeploymentUpdate
    ) -> Optional[Deployment]:
        """Met à jour un déploiement."""
        deployment = await DeploymentService.get_by_id(db, deployment_id)
        if not deployment:
            return None

        update_data = deployment_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(deployment, field, value)

        await db.commit()
        await db.refresh(deployment)
        return deployment

    @staticmethod
    async def delete(db: AsyncSession, deployment_id: str) -> bool:
        """Supprime un déploiement."""
        deployment = await DeploymentService.get_by_id(db, deployment_id)
        if not deployment:
            return False

        await db.delete(deployment)
        await db.commit()
        return True

    @staticmethod
    async def update_status(
        db: AsyncSession,
        deployment_id: str,
        status: DeploymentStatus,
        error_message: Optional[str] = None,
        logs: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Optional[Deployment]:
        """
        Met à jour le statut d'un déploiement avec logs et erreurs optionnels.
        Émet des événements WebSocket pour notifier les clients en temps réel.

        Args:
            db: Session de base de données
            deployment_id: ID du déploiement
            status: Nouveau statut
            error_message: Message d'erreur optionnel
            logs: Logs à ajouter (append)
            user_id: ID de l'utilisateur (pour événements WebSocket)

        Returns:
            Deployment mis à jour ou None si non trouvé
        """
        deployment = await DeploymentService.get_by_id(db, deployment_id)
        if not deployment:
            logger.warning(f"Déploiement {deployment_id} non trouvé pour mise à jour statut")
            return None

        # Sauvegarder l'ancien statut pour l'événement
        old_status = deployment.status

        # Mise à jour du statut
        deployment.status = status

        # Mise à jour du message d'erreur si fourni
        if error_message:
            deployment.error_message = error_message

        # Ajout des logs (append)
        if logs:
            existing_logs = deployment.logs or ""
            if existing_logs:
                deployment.logs = existing_logs + "\n" + logs
            else:
                deployment.logs = logs

        # Mise à jour des timestamps selon le statut
        if status == DeploymentStatus.RUNNING:
            deployment.deployed_at = datetime.utcnow()
            logger.info(f"Déploiement {deployment_id} démarré avec succès")
        elif status in [DeploymentStatus.STOPPED, DeploymentStatus.FAILED]:
            deployment.stopped_at = datetime.utcnow()

            # Calculer la durée si possible
            if deployment.deployed_at:
                duration = (deployment.stopped_at - deployment.deployed_at).total_seconds()
                deployment.deploy_duration_seconds = duration
                logger.info(
                    f"Déploiement {deployment_id} terminé en {duration:.2f}s "
                    f"avec statut {status.value}"
                )

        await db.commit()
        await db.refresh(deployment)

        # Émettre événement de changement de statut via WebSocket
        try:
            from uuid import UUID
            await deployment_events.emit_status_change(
                deployment_id=UUID(deployment_id),
                new_status=status,
                old_status=old_status,
                user_id=UUID(user_id) if user_id else None,
                additional_data={
                    "name": deployment.name,
                    "error_message": error_message
                }
            )
        except Exception as e:
            logger.error(f"Erreur lors de l'émission de l'événement de statut: {e}")

        # Émettre événement de logs si des logs ont été ajoutés
        if logs:
            try:
                from uuid import UUID
                await deployment_events.emit_logs_update(
                    deployment_id=UUID(deployment_id),
                    logs=logs,
                    user_id=UUID(user_id) if user_id else None,
                    append=True
                )
            except Exception as e:
                logger.error(f"Erreur lors de l'émission de l'événement de logs: {e}")

        return deployment

    @staticmethod
    async def get_by_status(
        db: AsyncSession,
        organization_id: str,
        status: DeploymentStatus,
        skip: int = 0,
        limit: int = 100
    ) -> List[Deployment]:
        """
        Liste les déploiements par statut pour une organisation.

        Args:
            db: Session de base de données
            organization_id: ID de l'organisation
            status: Statut à filtrer
            skip: Nombre d'éléments à ignorer pour la pagination
            limit: Nombre maximum d'éléments à retourner

        Returns:
            Liste des déploiements avec le statut demandé
        """
        result = await db.execute(
            select(Deployment)
            .where(
                and_(
                    Deployment.organization_id == organization_id,
                    Deployment.status == status
                )
            )
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_stale_pending_deployments(
        db: AsyncSession,
        max_age_minutes: int = 2
    ) -> List[Deployment]:
        """
        Récupère les déploiements bloqués en PENDING depuis trop longtemps.

        Args:
            db: Session de base de données
            max_age_minutes: Âge maximum en minutes pour considérer un déploiement comme bloqué

        Returns:
            Liste des déploiements PENDING trop anciens
        """
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)

        result = await db.execute(
            select(Deployment)
            .where(
                and_(
                    Deployment.status == DeploymentStatus.PENDING,
                    Deployment.created_at < cutoff_time
                )
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def mark_stale_as_failed(
        db: AsyncSession,
        max_age_minutes: int = 60
    ) -> int:
        """
        Marque les déploiements PENDING trop anciens comme FAILED.

        Args:
            db: Session de base de données
            max_age_minutes: Âge maximum en minutes avant de marquer comme FAILED

        Returns:
            Nombre de déploiements marqués comme FAILED
        """
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)

        # Récupérer les déploiements à marquer
        result = await db.execute(
            select(Deployment)
            .where(
                and_(
                    Deployment.status == DeploymentStatus.PENDING,
                    Deployment.created_at < cutoff_time
                )
            )
        )
        stale_deployments = list(result.scalars().all())

        count = 0
        for deployment in stale_deployments:
            deployment.status = DeploymentStatus.FAILED
            deployment.error_message = (
                f"Déploiement marqué comme échoué automatiquement après "
                f"{max_age_minutes} minutes en statut PENDING (timeout)"
            )
            deployment.stopped_at = datetime.utcnow()

            if deployment.logs:
                deployment.logs += "\n[SYSTEM] Timeout - Déploiement abandonné"
            else:
                deployment.logs = "[SYSTEM] Timeout - Déploiement abandonné"

            logger.warning(
                f"Déploiement {deployment.id} marqué comme FAILED après timeout "
                f"(créé à {deployment.created_at}, age: {datetime.utcnow() - deployment.created_at})"
            )
            count += 1

        if count > 0:
            await db.commit()
            logger.info(f"Marqué {count} déploiements PENDING comme FAILED (timeout)")

        return count

    @staticmethod
    async def retry_deployment(
        db: AsyncSession,
        deployment_id: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Réessaye un déploiement PENDING en relançant la tâche.

        Args:
            db: Session de base de données
            deployment_id: ID du déploiement à réessayer
            user_id: ID de l'utilisateur (optionnel, pour logs)

        Returns:
            True si la relance a réussi, False sinon
        """
        deployment = await DeploymentService.get_by_id(db, deployment_id)

        if not deployment:
            logger.error(f"Déploiement {deployment_id} non trouvé pour retry")
            return False

        if deployment.status != DeploymentStatus.PENDING:
            logger.warning(
                f"Déploiement {deployment_id} n'est pas PENDING (statut: {deployment.status}), "
                "skip retry"
            )
            return False

        logger.info(f"Retry du déploiement PENDING {deployment_id}")

        # Vérifier si Celery est disponible
        from ..celery_app import is_celery_available

        celery_available = settings.celery_enabled and is_celery_available()

        try:
            if celery_available:
                # Option 1: Utiliser Celery
                from ..tasks.deployment_tasks import deploy_stack

                # Mettre à jour le statut
                deployment.status = DeploymentStatus.DEPLOYING
                if deployment.logs:
                    deployment.logs += "\n[RETRY] Nouvelle tentative de déploiement (Celery)..."
                else:
                    deployment.logs = "[RETRY] Nouvelle tentative de déploiement (Celery)..."

                await db.commit()
                await db.refresh(deployment)

                # Lancer la tâche
                task = deploy_stack.delay(
                    deployment_id=str(deployment.id),
                    stack_id=str(deployment.stack_id),
                    target_id=str(deployment.target_id),
                    user_id=str(user_id) if user_id else "system",
                    configuration=deployment.variables or {}
                )

                logger.info(f"Tâche Celery de retry lancée: {task.id} pour {deployment_id}")
                return True

            else:
                # Option 2: Fallback asyncio
                from ..tasks.background_tasks import create_background_task, track_background_task

                # Mettre à jour le statut
                deployment.status = DeploymentStatus.DEPLOYING
                if deployment.logs:
                    deployment.logs += "\n[RETRY] Nouvelle tentative de déploiement (asyncio)..."
                else:
                    deployment.logs = "[RETRY] Nouvelle tentative de déploiement (asyncio)..."

                await db.commit()
                await db.refresh(deployment)

                # Créer et tracker la tâche
                task = create_background_task(
                    deployment_id=str(deployment.id),
                    stack_id=str(deployment.stack_id),
                    target_id=str(deployment.target_id),
                    user_id=str(user_id) if user_id else "system",
                    configuration=deployment.variables or {}
                )
                track_background_task(str(deployment.id), task)

                logger.info(f"Tâche asyncio de retry lancée pour {deployment_id}")
                return True

        except Exception as e:
            logger.error(f"Erreur lors du retry du déploiement {deployment_id}: {e}")

            # Remettre en PENDING en cas d'échec du retry
            deployment.status = DeploymentStatus.PENDING
            if deployment.logs:
                deployment.logs += f"\n[ERROR] Échec du retry: {str(e)}"
            else:
                deployment.logs = f"[ERROR] Échec du retry: {str(e)}"

            await db.commit()
            return False

    @staticmethod
    async def recover_pending_deployments(
        db: AsyncSession,
        max_age_minutes: int = 2,
        timeout_minutes: int = 60
    ) -> Dict[str, int]:
        """
        Recovery automatique des déploiements PENDING.

        Cette méthode :
        1. Réessaye les déploiements PENDING récents (< timeout)
        2. Marque comme FAILED les déploiements trop anciens (> timeout)

        Args:
            db: Session de base de données
            max_age_minutes: Âge minimum pour considérer un PENDING comme bloqué
            timeout_minutes: Âge maximum avant de marquer comme FAILED

        Returns:
            Statistiques de recovery (retried, failed, skipped)
        """
        logger.info(
            f"Lancement du recovery des déploiements PENDING "
            f"(max_age={max_age_minutes}min, timeout={timeout_minutes}min)"
        )

        stats = {
            "retried": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0
        }

        # 1. Marquer comme FAILED les trop anciens
        failed_count = await DeploymentService.mark_stale_as_failed(
            db,
            max_age_minutes=timeout_minutes
        )
        stats["failed"] = failed_count

        # 2. Réessayer les récents
        stale_deployments = await DeploymentService.get_stale_pending_deployments(
            db,
            max_age_minutes=max_age_minutes
        )

        for deployment in stale_deployments:
            # Vérifier que le déploiement n'est pas trop ancien (déjà géré ci-dessus)
            age_minutes = (datetime.utcnow() - deployment.created_at).total_seconds() / 60

            if age_minutes >= timeout_minutes:
                # Déjà marqué comme FAILED ci-dessus
                stats["skipped"] += 1
                continue

            # Réessayer
            success = await DeploymentService.retry_deployment(
                db,
                str(deployment.id),
                user_id="system_recovery"
            )

            if success:
                stats["retried"] += 1
            else:
                stats["errors"] += 1

        logger.info(
            f"Recovery terminé: {stats['retried']} retried, {stats['failed']} failed, "
            f"{stats['skipped']} skipped, {stats['errors']} errors"
        )

        return stats
