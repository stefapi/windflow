"""
Service métier pour gestion des stacks Docker Compose.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

from typing import Optional, List
from pathlib import Path
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.stack import Stack
from ..schemas.stack import StackCreate, StackUpdate
from .stack_loader_service import StackLoaderService


class StackService:
    """Service de gestion des stacks."""

    @staticmethod
    async def get_by_id(db: AsyncSession, stack_id: str) -> Optional[Stack]:
        """Récupère un stack par son ID."""
        result = await db.execute(
            select(Stack).where(Stack.id == stack_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(
        db: AsyncSession,
        name: str,
        organization_id: str
    ) -> Optional[Stack]:
        """Récupère un stack par son nom et organisation."""
        result = await db.execute(
            select(Stack).where(
                Stack.name == name,
                Stack.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_organization(
        db: AsyncSession,
        organization_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Stack]:
        """Liste les stacks d'une organisation."""
        result = await db.execute(
            select(Stack)
            .where(Stack.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

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
        db: AsyncSession,
        stack_id: str,
        stack_update: StackUpdate
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
    async def import_from_yaml(
        db: AsyncSession,
        yaml_path: Path,
        organization_id: str
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
        # Charger et parser le YAML
        data = StackLoaderService.load_from_yaml(yaml_path)
        stack_create = StackLoaderService.to_stack_create(data, organization_id)

        # Créer le stack
        return await StackService.create(db, stack_create)

    @staticmethod
    async def upsert_from_yaml(
        db: AsyncSession,
        yaml_path: Path,
        organization_id: str,
        force_update: bool = False
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
        # Charger le YAML
        data = StackLoaderService.load_from_yaml(yaml_path)
        stack_create = StackLoaderService.to_stack_create(data, organization_id)

        # Vérifier si le stack existe déjà
        existing = await StackService.get_by_name(
            db,
            stack_create.name,
            organization_id
        )

        if existing:
            if force_update:
                # Mettre à jour le stack existant
                stack_update = StackUpdate(
                    description=stack_create.description,
                    template=stack_create.template,
                    variables=stack_create.variables,
                    version=stack_create.version,
                    category=stack_create.category,
                    tags=stack_create.tags,
                    is_public=stack_create.is_public
                )
                updated_stack = await StackService.update(db, existing.id, stack_update)
                return updated_stack, False
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
        force_update: bool = False
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
        stats = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": []
        }

        # Charger tous les stacks du répertoire
        stack_creates = StackLoaderService.load_all_from_directory(
            directory,
            organization_id
        )

        # Importer chaque stack
        for stack_create in stack_creates:
            try:
                # Vérifier si existe déjà
                existing = await StackService.get_by_name(
                    db,
                    stack_create.name,
                    organization_id
                )

                if existing:
                    if force_update:
                        # Mettre à jour
                        stack_update = StackUpdate(
                            description=stack_create.description,
                            template=stack_create.template,
                            variables=stack_create.variables,
                            version=stack_create.version,
                            category=stack_create.category,
                            tags=stack_create.tags,
                            is_public=stack_create.is_public
                        )
                        await StackService.update(db, existing.id, stack_update)
                        stats["updated"] += 1
                        print(f"  ↻ Mis à jour: {stack_create.name}")
                    else:
                        stats["skipped"] += 1
                        print(f"  ⊝ Ignoré (déjà existant): {stack_create.name}")
                else:
                    # Créer
                    await StackService.create(db, stack_create)
                    stats["created"] += 1
                    print(f"  ✓ Créé: {stack_create.name}")

            except Exception as e:
                stats["errors"].append({
                    "stack": stack_create.name,
                    "error": str(e)
                })
                print(f"  ✗ Erreur pour {stack_create.name}: {e}")

        return stats
