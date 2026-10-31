"""
Service métier pour gestion des stacks Docker Compose.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.stack import Stack
from ..schemas.stack import StackCreate, StackUpdate
from ..schemas.stack_definition import format_validation_errors
from .stack_loader_service import StackLoaderService

logger = logging.getLogger(__name__)


class StackService:
    """Service de gestion des stacks."""

    @staticmethod
    async def get_by_id(db: AsyncSession, stack_id: str) -> Optional[Stack]:
        """Récupère un stack par son ID."""
        result = await db.execute(select(Stack).where(Stack.id == stack_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(
        db: AsyncSession, name: str, organization_id: str
    ) -> Optional[Stack]:
        """Récupère un stack par son nom et organisation."""
        result = await db.execute(
            select(Stack).where(
                Stack.name == name, Stack.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_organization(
        db: AsyncSession,
        organization_id: str,
        skip: int = 0,
        limit: int = 100,
        include_archived: bool = False,
    ) -> List[Stack]:
        """Liste les stacks d'une organisation, excluant les archivées par défaut."""
        query = select(Stack).where(Stack.organization_id == organization_id)
        if not include_archived:
            query = query.where(Stack.is_archived == False)  # noqa: E712
        result = await db.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    @staticmethod
    async def list_by_organizations(
        db: AsyncSession,
        organization_ids: List[str],
        page: int = 1,
        per_page: int = 20,
        include_archived: bool = False,
    ) -> List[Stack]:
        """Liste les stacks d'un ensemble d'organisations (STORY-128).

        Requête unique ``WHERE organization_id IN (...)`` avec tri stable
        ``ORDER BY name`` — remplace la boucle par-organisation de
        ``list_stacks`` dont l'application de skip/limit **par org**
        produisait des pages chevauchantes et un total faux.

        Args:
            db: Session de base de données async
            organization_ids: Identifiants des organisations scopées
                (appartenances de l'utilisateur)
            page: Page demandée (1-indexée)
            per_page: Taille de page (bornée 1-100 par le Query endpoint)
            include_archived: Inclure les stacks archivées

        Returns:
            Liste des stacks de la page, triée par nom
        """
        if not organization_ids:
            return []
        query = select(Stack).where(Stack.organization_id.in_(organization_ids))
        if not include_archived:
            query = query.where(Stack.is_archived == False)  # noqa: E712
        query = query.order_by(Stack.name).offset((page - 1) * per_page).limit(per_page)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def count_by_organizations(
        db: AsyncSession,
        organization_ids: List[str],
        include_archived: bool = False,
    ) -> int:
        """Compte les stacks d'un ensemble d'organisations (STORY-128).

        ``COUNT`` avec les **mêmes filtres et le même scoping** que
        :meth:`list_by_organizations` (rules 40 — pas d'oracle de
        comptage cross-org).

        Args:
            db: Session de base de données async
            organization_ids: Identifiants des organisations scopées
            include_archived: Inclure les stacks archivées

        Returns:
            Nombre total de stacks correspondant aux filtres
        """
        if not organization_ids:
            return 0
        query = (
            select(func.count())
            .select_from(Stack)
            .where(Stack.organization_id.in_(organization_ids))
        )
        if not include_archived:
            query = query.where(Stack.is_archived == False)  # noqa: E712
        result = await db.execute(query)
        return int(result.scalar() or 0)

    @staticmethod
    async def create(db: AsyncSession, stack_data: StackCreate) -> Stack:
        """Crée un nouveau stack."""
        stack = Stack(**stack_data.model_dump())
        db.add(stack)
        await db.commit()
        await db.refresh(stack)
        return stack

    @staticmethod
    async def update(
        db: AsyncSession, stack_id: str, stack_update: StackUpdate
    ) -> Optional[Stack]:
        """Met à jour un stack existant."""
        stack = await StackService.get_by_id(db, stack_id)
        if not stack:
            return None

        # Mettre à jour les champs fournis
        update_data = stack_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(stack, field, value)

        await db.commit()
        await db.refresh(stack)
        return stack

    @staticmethod
    @staticmethod
    async def delete(db: AsyncSession, stack_id: str) -> bool:
        """Supprime définitivement un stack (STORY-125.2 — divergence
        documentée : la méthode était référencée par le DELETE /{stack_id}
        mais n'existait pas, l'endpoint levait ``AttributeError`` → 500).

        Args:
            db: Session de base de données async
            stack_id: ID du stack à supprimer

        Returns:
            True si supprimé, False si non trouvé
        """
        stack = await StackService.get_by_id(db, stack_id)
        if not stack:
            return False

        await db.delete(stack)
        await db.commit()
        return True

    @staticmethod
    async def archive(db: AsyncSession, stack_id: str) -> Stack:
        """
        Archive un stack.

        Args:
            db: Session de base de données
            stack_id: ID du stack à archiver

        Returns:
            Stack: Stack mis à jour

        Raises:
            ValueError: Si le stack n'existe pas
        """
        stack = await StackService.get_by_id(db, stack_id)
        if not stack:
            raise ValueError(f"Stack non trouvé: {stack_id}")

        stack.is_archived = True
        stack.archived_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(stack)
        return stack

    @staticmethod
    async def unarchive(db: AsyncSession, stack_id: str) -> Stack:
        """
        Désarchive un stack.

        Args:
            db: Session de base de données
            stack_id: ID du stack à désarchiver

        Returns:
            Stack: Stack mis à jour

        Raises:
            ValueError: Si le stack n'existe pas
        """
        stack = await StackService.get_by_id(db, stack_id)
        if not stack:
            raise ValueError(f"Stack non trouvé: {stack_id}")

        stack.is_archived = False
        stack.archived_at = None
        await db.commit()
        await db.refresh(stack)
        return stack

    @staticmethod
    async def import_from_yaml(
        db: AsyncSession, yaml_path: Path, organization_id: str
    ) -> Stack:
        """
        Importe un stack depuis une définition YAML.

        Args:
            db: Session de base de données
            yaml_path: Chemin vers le fichier YAML
            organization_id: ID de l'organisation propriétaire

        Returns:
            Stack: Stack créé

        Raises:
            FileNotFoundError: Si le fichier n'existe pas
            ValueError: Si la définition est invalide
        """
        # STORY-171 : charger + valider via le moteur unique
        definition = StackLoaderService.load_definition(yaml_path)
        stack_create = StackLoaderService.to_stack_create(definition, organization_id)

        # Créer le stack
        return await StackService.create(db, stack_create)

    @staticmethod
    async def upsert_from_yaml(
        db: AsyncSession,
        yaml_path: Path,
        organization_id: str,
        force_update: bool = False,
    ) -> tuple[Stack, bool]:
        """
        Crée ou met à jour un stack depuis une définition YAML.

        Args:
            db: Session de base de données
            yaml_path: Chemin vers le fichier YAML
            organization_id: ID de l'organisation
            force_update: Forcer la mise à jour si le stack existe déjà

        Returns:
            tuple[Stack, bool]: (Stack créé/mis à jour, True si créé, False si mis à jour)
        """
        # STORY-171 : charger + valider via le moteur unique
        definition = StackLoaderService.load_definition(yaml_path)
        stack_create = StackLoaderService.to_stack_create(definition, organization_id)

        # Vérifier si le stack existe déjà
        existing = await StackService.get_by_name(
            db, stack_create.name, organization_id
        )

        if existing:
            if force_update:
                # Mettre à jour le stack existant — STORY-171 : propagation
                # de target_type/target_parameters (StackUpdate étendu, Tâche 1)
                stack_update = StackUpdate(  # type: ignore[call-arg]
                    description=stack_create.description,
                    template=stack_create.template,
                    variables=stack_create.variables,
                    version=stack_create.version,
                    category=stack_create.category,
                    tags=stack_create.tags,
                    is_public=stack_create.is_public,
                    target_type=stack_create.target_type,
                    target_parameters=stack_create.target_parameters,
                )
                updated_stack = await StackService.update(db, existing.id, stack_update)
                return updated_stack, False  # type: ignore[return-value]
            else:
                # Ne rien faire si déjà existant
                return existing, False
        else:
            # Créer un nouveau stack
            new_stack = await StackService.create(db, stack_create)
            return new_stack, True

    @staticmethod
    async def import_all_from_directory(
        db: AsyncSession,
        directory: Path,
        organization_id: str,
        force_update: bool = False,
    ) -> dict:
        """
        Importe tous les stacks d'un répertoire.

        Args:
            db: Session de base de données
            directory: Répertoire contenant les fichiers YAML
            organization_id: ID de l'organisation
            force_update: Forcer la mise à jour des stacks existants

        Returns:
            dict: Statistiques d'import (created, updated, errors)
        """
        stats: dict[str, Any] = {"created": 0, "updated": 0, "skipped": 0, "errors": []}

        # Charger tous les stacks du répertoire
        stack_creates = StackLoaderService.load_all_from_directory(
            directory, organization_id
        )

        # Importer chaque stack
        for stack_create in stack_creates:
            try:
                # Vérifier si existe déjà
                existing = await StackService.get_by_name(
                    db, stack_create.name, organization_id
                )

                if existing:
                    if force_update:
                        # Mettre à jour — STORY-171 : propagation
                        # target_type/target_parameters (StackUpdate étendu)
                        stack_update = StackUpdate(  # type: ignore[call-arg]
                            description=stack_create.description,
                            template=stack_create.template,
                            variables=stack_create.variables,
                            version=stack_create.version,
                            category=stack_create.category,
                            tags=stack_create.tags,
                            is_public=stack_create.is_public,
                            target_type=stack_create.target_type,
                            target_parameters=stack_create.target_parameters,
                        )
                        await StackService.update(db, existing.id, stack_update)
                        stats["updated"] += 1
                        logger.info("↻ Mis à jour: %s", stack_create.name)
                    else:
                        stats["skipped"] += 1
                        logger.info("⊝ Ignoré (déjà existant): %s", stack_create.name)
                else:
                    # Créer
                    await StackService.create(db, stack_create)
                    stats["created"] += 1
                    logger.info("✓ Créé: %s", stack_create.name)

            except ValidationError as e:
                # STORY-171 : erreurs Pydantic détaillées sans valeur d'input
                details = "; ".join(format_validation_errors(e))
                stats["errors"].append({"stack": stack_create.name, "error": details})
                logger.warning("✗ Validation pour %s: %s", stack_create.name, details)
            except Exception as e:
                stats["errors"].append({"stack": stack_create.name, "error": str(e)})
                logger.warning("✗ Erreur pour %s: %s", stack_create.name, e)

        return stats
