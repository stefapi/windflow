"""
Service métier pour gestion des organisations.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

import re
import unicodedata
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.organization import Organization
from ..schemas.organization import OrganizationCreate, OrganizationUpdate


def generate_slug(name: str) -> str:
    """
    Génère un slug à partir d'un nom.

    - Convertit en minuscules
    - Supprime les accents
    - Remplace les espaces et caractères spéciaux par des tirets
    - Supprime les tirets consécutifs et en début/fin

    Args:
        name: Nom de l'organisation

    Returns:
        Slug généré
    """
    # Normalisation Unicode (supprime les accents)
    normalized = unicodedata.normalize('NFKD', name)
    ascii_text = normalized.encode('ASCII', 'ignore').decode('ASCII')

    # Conversion en minuscules
    slug = ascii_text.lower()

    # Remplacement des caractères non alphanumériques par des tirets
    slug = re.sub(r'[^a-z0-9]+', '-', slug)

    # Suppression des tirets en début et fin
    slug = slug.strip('-')

    # Si le slug est vide, utiliser un fallback
    if not slug:
        slug = 'organization'

    return slug


class OrganizationService:
    """Service de gestion des organisations (multi-tenant)."""

    @staticmethod
    async def get_by_id(db: AsyncSession, org_id: UUID) -> Optional[Organization]:
        """Récupère une organisation par son ID."""
        result = await db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(db: AsyncSession, name: str) -> Optional[Organization]:
        """Récupère une organisation par son nom."""
        result = await db.execute(
            select(Organization).where(Organization.name == name)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[Organization]:
        """
        Liste toutes les organisations avec pagination.

        Args:
            db: Session de base de données async
            skip: Nombre d'éléments à sauter (pagination)
            limit: Nombre max d'éléments à retourner

        Returns:
            Liste d'organisations
        """
        result = await db.execute(
            select(Organization)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_slug(db: AsyncSession, slug: str) -> Optional[Organization]:
        """Récupère une organisation par son slug."""
        result = await db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _generate_unique_slug(db: AsyncSession, name: str) -> str:
        """
        Génère un slug unique à partir du nom.

        Si le slug existe déjà, ajoute un suffixe numérique (-1, -2, etc.)

        Args:
            db: Session de base de données async
            name: Nom de l'organisation

        Returns:
            Slug unique
        """
        base_slug = generate_slug(name)
        slug = base_slug
        counter = 1

        while await OrganizationService.get_by_slug(db, slug):
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    @staticmethod
    async def create(db: AsyncSession, org_data: OrganizationCreate) -> Organization:
        """
        Crée une nouvelle organisation.

        Le slug est généré automatiquement à partir du nom s'il n'est pas fourni.
        Si le slug généré existe déjà, un suffixe numérique est ajouté.
        """
        data = org_data.model_dump()

        # Générer le slug automatiquement si non fourni
        if not data.get('slug'):
            data['slug'] = await OrganizationService._generate_unique_slug(db, data['name'])
        else:
            # Vérifier l'unicité du slug fourni
            existing = await OrganizationService.get_by_slug(db, data['slug'])
            if existing:
                raise ValueError(f"Le slug '{data['slug']}' est déjà utilisé")

        org = Organization(**data)
        db.add(org)
        await db.commit()
        await db.refresh(org)
        return org

    @staticmethod
    async def update(
        db: AsyncSession,
        org_id: UUID,
        org_data: OrganizationUpdate
    ) -> Optional[Organization]:
        """
        Met à jour une organisation.

        Args:
            db: Session de base de données async
            org_id: ID de l'organisation à mettre à jour
            org_data: Données de mise à jour

        Returns:
            Organisation mise à jour ou None si non trouvée
        """
        org = await OrganizationService.get_by_id(db, org_id)
        if not org:
            return None

        update_data = org_data.model_dump(exclude_unset=True)

        # Mise à jour des champs
        for field, value in update_data.items():
            setattr(org, field, value)

        await db.commit()
        await db.refresh(org)

        return org

    @staticmethod
    async def delete(db: AsyncSession, org_id: UUID) -> bool:
        """
        Supprime une organisation.

        Args:
            db: Session de base de données async
            org_id: ID de l'organisation à supprimer

        Returns:
            True si supprimée, False si non trouvée
        """
        org = await OrganizationService.get_by_id(db, org_id)
        if not org:
            return False

        await db.delete(org)
        await db.commit()

        return True
