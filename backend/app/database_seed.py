"""
Module de seeding pour initialisation de la base de données.

Crée les données minimales requises au premier démarrage :
- Organisation par défaut
- Utilisateur admin avec droits superuser
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models.organization import Organization
from .models.user import User
from .schemas.user import UserCreate
from .services.user_service import UserService
from .config import settings


async def seed_database(session: AsyncSession) -> None:
    """
    Initialise la base de données avec les données minimales.

    Crée une organisation par défaut et un utilisateur administrateur
    si la base de données est vide (première initialisation).

    Args:
        session: Session de base de données async

    Raises:
        Exception: En cas d'erreur lors du seeding
    """
    try:
        # Vérifier si des organisations existent déjà
        result = await session.execute(select(Organization))
        existing_org = result.scalar_one_or_none()

        if existing_org:
            # Base de données déjà initialisée
            return

        # Créer l'organisation par défaut
        default_org = Organization(
            name=settings.default_org_name,
            slug=settings.default_org_slug,
            description="Organisation créée automatiquement lors de l'initialisation",
            settings={}
        )
        session.add(default_org)
        await session.flush()  # Pour obtenir l'ID de l'organisation

        # Vérifier si un utilisateur admin existe déjà
        result = await session.execute(
            select(User).where(User.username == settings.admin_username)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            # Utilisateur admin déjà existant
            await session.commit()
            return

        # Créer l'utilisateur admin
        admin_data = UserCreate(
            email=settings.admin_email,
            username=settings.admin_username,
            full_name=settings.admin_full_name,
            password=settings.admin_password,
            organization_id=default_org.id,
            is_superuser=True
        )

        await UserService.create(session, admin_data)

        print(f"✓ Base de données initialisée avec succès")
        print(f"  - Organisation: {default_org.name} ({default_org.slug})")
        print(f"  - Admin: {settings.admin_username} ({settings.admin_email})")
        print(f"  - Mot de passe par défaut: {settings.admin_password}")
        print(f"  ⚠️  IMPORTANT: Changez le mot de passe admin en production!")

    except Exception as e:
        await session.rollback()
        print(f"✗ Erreur lors du seeding de la base de données: {e}")
        raise


async def check_admin_exists(session: AsyncSession) -> bool:
    """
    Vérifie si un utilisateur admin existe dans la base de données.

    Args:
        session: Session de base de données async

    Returns:
        bool: True si au moins un superuser existe
    """
    result = await session.execute(
        select(User).where(User.is_superuser == True)
    )
    admin = result.scalar_one_or_none()
    return admin is not None
