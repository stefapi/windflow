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
from ..helper.template_renderer import TemplateRenderer

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

        Utilise TemplateRenderer pour avoir accès aux fonctions personnalisées
        comme generate_password(), generate_secret(), etc.

        Args:
            template_data: Données du template (peut être dict, list, str)
            variables: Variables à substituer

        Returns:
            Template rendu avec variables substituées
        """
        # Créer une instance de TemplateRenderer avec les fonctions Jinja2
        renderer = TemplateRenderer()

        if isinstance(template_data, dict):
            return renderer.render_dict(template_data, variables)
        elif isinstance(template_data, list):
            return [
                DeploymentService._render_template(item, variables)
                for item in template_data
            ]
        elif isinstance(template_data, str):
            return renderer.render_string(template_data, variables)
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
        - Déclenche la tâche asyncio de déploiement via DeploymentOrchestrator

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

        # 3.5. Rendre les variables mergées pour exécuter les macros (generate_password, etc.)
        # Cela garantit que le frontend reçoit les valeurs générées, pas les macros brutes
        rendered_variables = DeploymentService._render_template(
            merged_variables,
            {}  # Pas de variables utilisateur supplémentaires pour le rendu des variables
        )

        # 3.6. Ajouter deployment_name aux variables pour qu'il soit disponible dans les templates
        rendered_variables['deployment_name'] = deployment_name

        # 3.7. Rendre les target_parameters du stack avec les variables (pour snapshot)
        rendered_target_parameters = None
        if stack.target_parameters:
            rendered_target_parameters = DeploymentService._render_template(
                stack.target_parameters,
                rendered_variables
            )

        # 4. Générer le config en rendant le template avec les variables rendues
        config = deployment_data.config
        if not config:
            config = DeploymentService._render_template(
                stack.template,
                rendered_variables
            )

        # 5. Créer le déploiement avec statut initial PENDING
        deployment_dict = {
            "name": deployment_name,
            "stack_id": deployment_data.stack_id,
            "target_id": deployment_data.target_id,
            "config": config,
            "variables": rendered_variables,
            "rendered_target_parameters": rendered_target_parameters,
            "organization_id": organization_id,
            "status": DeploymentStatus.PENDING
        }

        deployment = Deployment(**deployment_dict)
        db.add(deployment)
        await db.commit()
        await db.refresh(deployment)

        # 6. Déclencher la tâche de déploiement avec DeploymentOrchestrator
        from .deployment_orchestrator import DeploymentOrchestrator

        # Mettre à jour le statut à DEPLOYING
        deployment.status = DeploymentStatus.DEPLOYING
        await db.commit()
        await db.refresh(deployment)

        # Lancer la tâche asynchrone avec l'orchestrateur
        task = await DeploymentOrchestrator.start_deployment(
            deployment_id=str(deployment.id),
            stack_id=str(deployment.stack_id),
            target_id=str(deployment.target_id),
            user_id=str(user_id),
            configuration=rendered_variables
        )

        logger.info(
            f"Tâche de déploiement lancée avec DeploymentOrchestrator "
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
    async def _remove_named_volumes(deployment: Deployment, docker_service) -> None:
        """
        Supprime les volumes nommés définis dans rendered_target_parameters du déploiement.

        Utilise les target_parameters déjà rendus avec Jinja lors de la création du déploiement,
        évitant ainsi de devoir re-rendre les templates lors de la suppression.

        Args:
            deployment: Déploiement contenant les rendered_target_parameters
            docker_service: Instance de DockerService pour supprimer les volumes
        """
        try:
            # Récupérer les target_parameters rendus du déploiement
            rendered_target_parameters = deployment.rendered_target_parameters

            logger.debug(f"rendered_target_parameters pour {deployment.id}: {rendered_target_parameters}")

            if not rendered_target_parameters or 'volumes' not in rendered_target_parameters:
                logger.debug(f"Pas de volumes définis dans rendered_target_parameters pour {deployment.id}")
                return

            volumes_list = rendered_target_parameters.get('volumes', [])
            if not volumes_list:
                logger.debug(f"Liste de volumes vide pour {deployment.id}")
                return

            logger.info(f"Suppression de {len(volumes_list)} volume(s) nommé(s) pour le déploiement {deployment.id}")

            # Parcourir chaque volume défini (déjà rendus avec Jinja)
            for volume_entry in volumes_list:
                # Les volumes dans target_parameters sont de simples noms de volumes
                # Format: "volume_name" (pas de mapping volume:path comme dans template.volumes)
                if isinstance(volume_entry, str):
                    volume_name = volume_entry.strip()

                    logger.info(f"Suppression du volume nommé: {volume_name}")
                    success, message = await docker_service.remove_volume(
                        volume_name=volume_name,
                        force=False
                    )

                    if success:
                        logger.info(f"Volume {volume_name} supprimé avec succès: {message}")
                    else:
                        logger.warning(f"Échec de la suppression du volume {volume_name}: {message}")

        except Exception as e:
            logger.error(f"Erreur lors de la suppression des volumes nommés pour {deployment.id}: {e}")

    @staticmethod
    async def delete(db: AsyncSession, deployment_id: str) -> bool:
        """
        Supprime complètement un déploiement.

        Cette méthode:
        1. Annule la tâche de déploiement en cours si elle existe
        2. Arrête et supprime les conteneurs/pods et volumes selon le type de stack
        3. Supprime l'entrée en base de données UNIQUEMENT si la destruction réussit

        Args:
            db: Session de base de données
            deployment_id: ID du déploiement à supprimer

        Returns:
            bool: True si la suppression a réussi, False sinon
        """
        from sqlalchemy.orm import selectinload
        from ..schemas.target import TargetType

        # Charger le déploiement avec ses relations (stack)
        result = await db.execute(
            select(Deployment)
            .options(selectinload(Deployment.stack))
            .where(Deployment.id == deployment_id)
        )
        deployment = result.scalar_one_or_none()

        if not deployment:
            logger.warning(f"Déploiement {deployment_id} non trouvé pour suppression")
            return False

        logger.info(f"Suppression du déploiement {deployment_id} (statut: {deployment.status.value}, stack: {deployment.stack.name}, target_type: {deployment.stack.target_type})")

        # 1. Annuler la tâche en cours si elle existe
        try:
            from .deployment_orchestrator import DeploymentOrchestrator
            await DeploymentOrchestrator.cancel_deployment(deployment_id)
            logger.info(f"Tâche de déploiement {deployment_id} annulée")
        except Exception as e:
            logger.warning(f"Erreur lors de l'annulation de la tâche {deployment_id}: {e}")
            # Continue même si l'annulation échoue (la tâche n'existe peut-être pas)

        # 2. Supprimer les ressources selon le type de stack
        resources_deleted = False
        deletion_error = None

        if deployment.status.value in ["running", "deploying", "pending"]:
            try:
                # Router vers le bon service selon le type de stack
                if deployment.stack.target_type == TargetType.DOCKER.value:
                    # === DOCKER NATIF ===
                    logger.info(f"Suppression d'un container Docker natif: {deployment.name}")
                    from .docker_service import DockerService
                    docker_service = DockerService()

                    # Supprimer le container (force=True pour supprimer même si running)
                    success, output = await docker_service.remove_container(
                        container_name=deployment.name,
                        force=True,
                        remove_volumes=True
                    )

                    if success:
                        logger.info(f"Container Docker supprimé pour {deployment_id}: {output}")
                        resources_deleted = True

                        # Supprimer les volumes nommés explicitement définis dans le template
                        await DeploymentService._remove_named_volumes(
                            deployment=deployment,
                            docker_service=docker_service
                        )
                    else:
                        deletion_error = f"Échec de la suppression du container Docker: {output}"
                        logger.error(deletion_error)
                else:
                    # === DOCKER COMPOSE / AUTRES ===
                    logger.info(f"Suppression d'un projet Docker Compose: {deployment.name}")
                    from .docker_compose_service import DockerComposeService
                    docker_compose_service = DockerComposeService()

                    # Supprimer complètement le projet (conteneurs + volumes)
                    success, output = await docker_compose_service.remove_compose(
                        project_name=deployment.name,
                        remove_volumes=True
                    )

                    if success:
                        logger.info(f"Projet Docker Compose supprimé pour {deployment_id}: {output}")
                        resources_deleted = True
                    else:
                        deletion_error = f"Échec de la suppression du projet Docker Compose: {output}"
                        logger.error(deletion_error)

            except Exception as e:
                deletion_error = f"Erreur lors de la suppression des ressources: {str(e)}"
                logger.error(f"Erreur lors de la suppression des ressources pour {deployment_id}: {e}")
        else:
            # Déploiement déjà arrêté ou en échec, pas de ressources à supprimer
            logger.info(f"Déploiement {deployment_id} en statut {deployment.status.value}, pas de ressources actives à supprimer")
            resources_deleted = True

        # 3. Gérer le résultat de la suppression
        if not resources_deleted and deletion_error:
            # La suppression des ressources a échoué
            # Mettre le déploiement en statut FAILED au lieu de le supprimer
            logger.warning(f"Impossible de supprimer les ressources pour {deployment_id}, mise en statut FAILED")
            deployment.status = DeploymentStatus.FAILED
            deployment.error_message = deletion_error
            deployment.stopped_at = datetime.utcnow()

            # Ajouter aux logs
            error_log = f"\n[ERROR] Échec de la suppression des ressources: {deletion_error}"
            if deployment.logs:
                deployment.logs += error_log
            else:
                deployment.logs = error_log

            try:
                await db.commit()
                await db.refresh(deployment)
                logger.info(f"Déploiement {deployment_id} marqué comme FAILED")
                return False
            except Exception as e:
                logger.error(f"Erreur lors de la mise à jour du statut FAILED pour {deployment_id}: {e}")
                await db.rollback()
                return False

        # 4. Supprimer l'entrée en base de données (seulement si ressources supprimées)
        try:
            await db.delete(deployment)
            await db.commit()
            logger.info(f"Déploiement {deployment_id} supprimé de la base de données")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la suppression en base de données du déploiement {deployment_id}: {e}")
            await db.rollback()
            return False

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
        Réessaye un déploiement PENDING ou FAILED en relançant la tâche.

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

        if deployment.status not in [DeploymentStatus.PENDING, DeploymentStatus.FAILED]:
            logger.warning(
                f"Déploiement {deployment_id} n'est pas PENDING ou FAILED (statut: {deployment.status}), "
                "skip retry"
            )
            return False

        logger.info(f"Retry du déploiement {deployment.status.value} {deployment_id}")

        try:
            from .deployment_orchestrator import DeploymentOrchestrator

            # Mettre à jour le statut
            deployment.status = DeploymentStatus.DEPLOYING
            if deployment.logs:
                deployment.logs += "\n[RETRY] Nouvelle tentative de déploiement..."
            else:
                deployment.logs = "[RETRY] Nouvelle tentative de déploiement..."

            await db.commit()
            await db.refresh(deployment)

            # Lancer la tâche avec l'orchestrateur
            task = await DeploymentOrchestrator.start_deployment(
                deployment_id=str(deployment.id),
                stack_id=str(deployment.stack_id),
                target_id=str(deployment.target_id),
                user_id=str(user_id) if user_id else "system",
                configuration=deployment.variables or {}
            )

            logger.info(f"Tâche de retry lancée avec DeploymentOrchestrator pour {deployment_id}")
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

