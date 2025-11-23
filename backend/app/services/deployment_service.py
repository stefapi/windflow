"""
Service métier pour gestion des déploiements.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from jinja2 import Template, TemplateSyntaxError

from ..models.deployment import Deployment
from ..models.stack import Stack
from ..schemas.deployment import DeploymentCreate, DeploymentUpdate


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
        Crée un nouveau déploiement.

        Cette méthode génère automatiquement :
        - Le nom du déploiement si non fourni
        - La configuration en rendant le template du stack avec les variables
        - Les variables mergées (defaults du stack + overrides utilisateur)

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

        # 5. Créer le déploiement avec toutes les données
        deployment_dict = {
            "name": deployment_name,
            "stack_id": deployment_data.stack_id,
            "target_id": deployment_data.target_id,
            "config": config,
            "variables": merged_variables,
            "organization_id": organization_id
        }

        deployment = Deployment(**deployment_dict)
        db.add(deployment)
        await db.commit()
        await db.refresh(deployment)
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
