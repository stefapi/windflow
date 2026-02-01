"""
Service métier pour gestion des utilisateurs.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

from typing import Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from ..models.user import User
from ..schemas.user import UserCreate, UserUpdate

# Configuration password hashing avec Argon2
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class UserService:
    """
    Service de gestion des utilisateurs.

    Implémente la logique métier pour les opérations CRUD sur les utilisateurs.
    """

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash un mot de passe avec Argon2.

        Argon2 est un algorithme moderne de hashing de mots de passe,
        gagnant du Password Hashing Competition (PHC). Il offre une meilleure
        sécurité que bcrypt et n'a pas de limite de longueur pour les mots de passe.

        Args:
            password: Mot de passe en clair

        Returns:
            Hash Argon2 du mot de passe
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Vérifie un mot de passe avec Argon2.

        Contrairement à bcrypt, Argon2 n'a pas de limite de longueur pour les mots de passe,
        donc aucune troncature n'est nécessaire.

        Args:
            plain_password: Mot de passe en clair à vérifier
            hashed_password: Hash Argon2 stocké

        Returns:
            True si le mot de passe correspond, False sinon
        """
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def verify_and_update(plain_password: str, hashed_password: str) -> Tuple[bool, Optional[str]]:
        """
        Vérifie un mot de passe et détecte si le hash doit être renouvelé.

        Cette méthode utilise la fonctionnalité de passlib pour détecter
        automatiquement si un hash doit être mis à jour (par exemple si
        les paramètres de sécurité Argon2 ont été modifiés dans la configuration).

        Args:
            plain_password: Mot de passe en clair à vérifier
            hashed_password: Hash Argon2 stocké

        Returns:
            Tuple[bool, Optional[str]]:
                - bool: True si le mot de passe correspond, False sinon
                - Optional[str]: Nouveau hash si une mise à jour est nécessaire, None sinon

        Example:
            >>> is_valid, new_hash = UserService.verify_and_update("password123", old_hash)
            >>> if is_valid and new_hash:
            ...     # Mettre à jour le hash en base de données
            ...     user.hashed_password = new_hash
            ...     await db.commit()
        """
        # Vérifier le mot de passe et obtenir le résultat
        verified, new_hash = pwd_context.verify_and_update(plain_password, hashed_password)

        return verified, new_hash

    @staticmethod
    async def verify_and_update_user(
        db: AsyncSession,
        user: User,
        plain_password: str
    ) -> bool:
        """
        Vérifie le mot de passe d'un utilisateur et met à jour automatiquement
        le hash si nécessaire.

        Cette méthode combine la vérification et la mise à jour du hash en une seule
        opération. Si le hash doit être renouvelé, il est automatiquement mis à jour
        en base de données.

        Args:
            db: Session de base de données async
            user: Utilisateur dont on vérifie le mot de passe
            plain_password: Mot de passe en clair à vérifier

        Returns:
            True si le mot de passe est valide, False sinon

        Example:
            >>> user = await UserService.get_by_email(db, "user@example.com")
            >>> is_valid = await UserService.verify_and_update_user(db, user, "password123")
            >>> if is_valid:
            ...     # L'utilisateur est authentifié
            ...     pass
        """
        is_valid, new_hash = UserService.verify_and_update(plain_password, user.hashed_password)

        # Si le mot de passe est valide et qu'un nouveau hash est disponible
        if is_valid and new_hash:
            # Mettre à jour le hash en base de données
            user.hashed_password = new_hash
            await db.commit()
            await db.refresh(user)

        return is_valid

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
    async def get_first_superadmin(db: AsyncSession) -> Optional[User]:
        """
        Récupère le premier utilisateur superadmin actif de la base.

        Utilisé principalement en mode développement avec DISABLE_AUTH=true.

        Args:
            db: Session de base de données async

        Returns:
            Premier User superadmin actif ou None si aucun trouvé
        """
        result = await db.execute(
            select(User)
            .where(User.is_superuser == True)
            .where(User.is_active == True)
            .limit(1)
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
