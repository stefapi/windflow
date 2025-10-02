"""
Service métier pour gestion des utilisateurs.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from ..models.user import User
from ..schemas.user import UserCreate, UserUpdate

# Configuration password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    """
    Service de gestion des utilisateurs.

    Implémente la logique métier pour les opérations CRUD sur les utilisateurs.
    """

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash un mot de passe."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Vérifie un mot de passe."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
        """
        Récupère un utilisateur par son ID.

        Args:
            db: Session de base de données async
            user_id: ID de l'utilisateur

        Returns:
            User ou None si non trouvé
        """
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """
        Récupère un utilisateur par son email.

        Args:
            db: Session de base de données async
            email: Email de l'utilisateur

        Returns:
            User ou None si non trouvé
        """
        result = await db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> Optional[User]:
        """
        Récupère un utilisateur par son username.

        Args:
            db: Session de base de données async
            username: Username de l'utilisateur

        Returns:
            User ou None si non trouvé
        """
        result = await db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_organization(
        db: AsyncSession,
        organization_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Liste les utilisateurs d'une organisation.

        Args:
            db: Session de base de données async
            organization_id: ID de l'organisation
            skip: Nombre d'éléments à sauter (pagination)
            limit: Nombre max d'éléments à retourner

        Returns:
            Liste d'utilisateurs
        """
        result = await db.execute(
            select(User)
            .where(User.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, user_data: UserCreate) -> User:
        """
        Crée un nouvel utilisateur.

        Args:
            db: Session de base de données async
            user_data: Données de création

        Returns:
            Utilisateur créé
        """
        # Hash du mot de passe
        hashed_password = UserService.hash_password(user_data.password)

        # Création du modèle
        user = User(
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            hashed_password=hashed_password,
            organization_id=user_data.organization_id,
            is_superuser=user_data.is_superuser
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user

    @staticmethod
    async def update(
        db: AsyncSession,
        user: User,
        user_data: UserUpdate
    ) -> User:
        """
        Met à jour un utilisateur.

        Args:
            db: Session de base de données async
            user: Utilisateur à mettre à jour
            user_data: Données de mise à jour

        Returns:
            Utilisateur mis à jour
        """
        update_data = user_data.model_dump(exclude_unset=True)

        # Hash du nouveau mot de passe si fourni
        if "password" in update_data:
            update_data["hashed_password"] = UserService.hash_password(
                update_data.pop("password")
            )

        # Mise à jour des champs
        for field, value in update_data.items():
            setattr(user, field, value)

        await db.commit()
        await db.refresh(user)

        return user

    @staticmethod
    async def delete(db: AsyncSession, user: User) -> None:
        """
        Supprime un utilisateur.

        Args:
            db: Session de base de données async
            user: Utilisateur à supprimer
        """
        await db.delete(user)
        await db.commit()
