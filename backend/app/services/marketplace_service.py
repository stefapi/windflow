"""
Service métier pour gestion de la marketplace WindFlow.

Gestion des stacks publics et déploiements depuis la marketplace.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from ..models.stack import Stack
from ..schemas.stack import MarketplaceStackResponse, DeploymentConfigRequest
from ..services.deployment_service import DeploymentService
from ..schemas.deployment import DeploymentCreate


class MarketplaceService:
    """Service de gestion de la marketplace."""

    @staticmethod
    async def list_public_stacks(
        db: AsyncSession,
        category: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[Stack], int]:
        """
        Liste les stacks publics de la marketplace.

        Args:
            db: Session de base de données
            category: Filtrer par catégorie
            search: Recherche textuelle (nom, description, tags)
            skip: Offset pour pagination
            limit: Nombre de résultats

        Returns:
            Tuple[List[Stack], int]: Liste des stacks et total
        """
        # Base query - seulement les stacks publics
        query = select(Stack).where(Stack.is_public == True)

        # Filtre par catégorie
        if category:
            query = query.where(Stack.category == category)

        # Recherche textuelle
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    Stack.name.ilike(search_pattern),
                    Stack.description.ilike(search_pattern),
                    Stack.tags.cast(str).ilike(search_pattern)
                )
            )

        # Count total
        from sqlalchemy import func
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Trier par popularité (downloads desc) puis par date
        query = query.order_by(
            Stack.downloads.desc(),
            Stack.created_at.desc()
        )

        # Pagination
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        stacks = list(result.scalars().all())

        return stacks, total

    @staticmethod
    async def get_stack_details(
        db: AsyncSession,
        stack_id: str
    ) -> Optional[Stack]:
        """
        Récupère les détails complets d'un stack marketplace.

        Args:
            db: Session de base de données
            stack_id: ID du stack

        Returns:
            Stack complet avec template et variables
        """
        result = await db.execute(
            select(Stack).where(
                Stack.id == stack_id,
                Stack.is_public == True
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def increment_downloads(
        db: AsyncSession,
        stack_id: str
    ) -> None:
        """
        Incrémente le compteur de téléchargements d'un stack.

        Args:
            db: Session de base de données
            stack_id: ID du stack
        """
        result = await db.execute(
            select(Stack).where(Stack.id == stack_id)
        )
        stack = result.scalar_one_or_none()

        if stack:
            stack.downloads += 1
            await db.commit()

    @staticmethod
    async def get_categories(db: AsyncSession) -> List[str]:
        """
        Récupère la liste des catégories disponibles.

        Args:
            db: Session de base de données

        Returns:
            Liste des catégories uniques
        """
        from sqlalchemy import distinct

        result = await db.execute(
            select(distinct(Stack.category)).where(
                Stack.is_public == True,
                Stack.category.isnot(None)
            )
        )
        categories = [cat for cat in result.scalars().all() if cat]
        return sorted(categories)

    @staticmethod
    async def deploy_from_marketplace(
        db: AsyncSession,
        stack_id: str,
        config: DeploymentConfigRequest,
        user_id: str
    ) -> str:
        """
        Déploie un stack depuis la marketplace.

        Args:
            db: Session de base de données
            stack_id: ID du stack à déployer
            config: Configuration du déploiement
            user_id: ID de l'utilisateur

        Returns:
            ID du déploiement créé

        Raises:
            ValueError: Si le stack n'existe pas ou n'est pas public
        """
        # Vérifier que le stack existe et est public
        stack = await MarketplaceService.get_stack_details(db, stack_id)
        if not stack:
            raise ValueError(f"Stack {stack_id} non trouvé ou non public")

        # Incrémenter les téléchargements
        await MarketplaceService.increment_downloads(db, stack_id)

        # Créer le déploiement
        deployment_service = DeploymentService()

        # Générer un nom de déploiement si non fourni
        deployment_name = config.name or f"{stack.name}-{stack.version}"

        deployment_create = DeploymentCreate(
            name=deployment_name,
            stack_id=stack_id,
            target_id=config.target_id,
            configuration=config.configuration,
            user_id=user_id
        )

        # Créer le déploiement (qui lancera la tâche asyncio)
        deployment = await deployment_service.create(db, deployment_create)

        return deployment.id

    @staticmethod
    async def install_to_organization(
        db: AsyncSession,
        stack_id: str,
        organization_id: str,
        user_id: str
    ) -> Stack:
        """
        Copie un stack public dans l'organisation de l'utilisateur.

        Args:
            db: Session de base de données
            stack_id: ID du stack à copier
            organization_id: ID de l'organisation cible
            user_id: ID de l'utilisateur

        Returns:
            Nouveau stack créé dans l'organisation

        Raises:
            ValueError: Si le stack n'existe pas
        """
        # Récupérer le stack source
        source_stack = await MarketplaceService.get_stack_details(db, stack_id)
        if not source_stack:
            raise ValueError(f"Stack {stack_id} non trouvé")

        # Créer une copie dans l'organisation
        new_stack = Stack(
            name=f"{source_stack.name} (copie)",
            description=source_stack.description,
            template=source_stack.template.copy(),
            variables=source_stack.variables.copy(),
            version=source_stack.version,
            category=source_stack.category,
            tags=source_stack.tags.copy(),
            icon_url=source_stack.icon_url,
            screenshots=source_stack.screenshots.copy(),
            documentation_url=source_stack.documentation_url,
            author=source_stack.author,
            license=source_stack.license,
            is_public=False,  # Copie privée par défaut
            organization_id=organization_id
        )

        db.add(new_stack)
        await db.commit()
        await db.refresh(new_stack)

        # Incrémenter les téléchargements du stack source
        await MarketplaceService.increment_downloads(db, stack_id)

        return new_stack

    @staticmethod
    async def get_popular_stacks(
        db: AsyncSession,
        limit: int = 10
    ) -> List[Stack]:
        """
        Récupère les stacks les plus populaires.

        Args:
            db: Session de base de données
            limit: Nombre de stacks à retourner

        Returns:
            Liste des stacks les plus téléchargés
        """
        result = await db.execute(
            select(Stack)
            .where(Stack.is_public == True)
            .order_by(Stack.downloads.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_recent_stacks(
        db: AsyncSession,
        limit: int = 10
    ) -> List[Stack]:
        """
        Récupère les stacks récemment ajoutés.

        Args:
            db: Session de base de données
            limit: Nombre de stacks à retourner

        Returns:
            Liste des stacks les plus récents
        """
        result = await db.execute(
            select(Stack)
            .where(Stack.is_public == True)
            .order_by(Stack.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
