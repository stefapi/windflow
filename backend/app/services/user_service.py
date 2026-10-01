"""
Service métier pour gestion des utilisateurs.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

from typing import List, Optional, Tuple
from uuid import UUID

from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User
from ..models.user_organization import UserOrganization
from ..schemas.organization_member import OrganizationMemberAddRequest
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
    def verify_and_update(
        plain_password: str, hashed_password: str
    ) -> Tuple[bool, Optional[str]]:
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
        verified, new_hash = pwd_context.verify_and_update(
            plain_password, hashed_password
        )

        return verified, new_hash

    @staticmethod
    async def verify_and_update_user(
        db: AsyncSession, user: User, plain_password: str
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
        is_valid, new_hash = UserService.verify_and_update(
            plain_password, user.hashed_password
        )

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
        result = await db.execute(select(User).where(User.id == user_id))
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
        result = await db.execute(select(User).where(User.email == email))
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
        result = await db.execute(select(User).where(User.username == username))
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
    async def count_superadmins(db: AsyncSession) -> int:
        """
        Compte les utilisateurs superadmins (STORY-122.4, AC 3).

        Sert de garde aux protections « dernier superadmin » : ni démotable
        (``is_superuser=False``), ni désactivable (``is_active=False``), ni
        supprimable — les endpoints lèvent 409 quand le comptage tombe à 1.

        Args:
            db: Session de base de données async

        Returns:
            Nombre d'utilisateurs avec ``is_superuser == True``
        """
        result = await db.execute(
            select(func.count()).select_from(User).where(User.is_superuser == True)
        )
        return int(result.scalar_one())

    @staticmethod
    async def list_all(
        db: AsyncSession, page: int = 1, per_page: int = 20
    ) -> Tuple[List[User], int]:
        """
        Liste tous les utilisateurs de toutes les organisations (pour superusers).

        STORY-128 : pagination canonique ``page``/``per_page`` avec tri
        stable ``ORDER BY username`` (l'ancien listing sans ``order_by``
        rendait les pages non déterministes).

        Args:
            db: Session de base de données async
            page: Page demandée (1-indexée, bornée par le Query endpoint)
            per_page: Taille de page (1-100, bornée par le Query endpoint)

        Returns:
            Tuple[List[User], int]: Liste d'utilisateurs et nombre total
        """
        # Requête pour les utilisateurs paginés
        result = await db.execute(
            select(User)
            .order_by(User.username)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        users = list(result.scalars().all())

        # Requête pour le count total
        count_result = await db.execute(select(func.count()).select_from(User))
        total = count_result.scalar_one()

        return users, total

    @staticmethod
    async def list_by_organization_ids(
        db: AsyncSession,
        organization_ids: List[str],
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[User], int]:
        """
        Liste les utilisateurs de plusieurs organisations via les associations.

        STORY-121.3 : scoping multi-appartenance — les utilisateurs dont
        l'id apparaît dans ``user_organizations`` pour l'une des
        organisations données (remplace le filtre sur la colonne héritée).
        STORY-128 : pagination canonique ``page``/``per_page`` avec tri
        stable ``ORDER BY username``.

        Args:
            db: Session de base de données async
            organization_ids: IDs des organisations (appartenances du demandeur)
            page: Page demandée (1-indexée, bornée par le Query endpoint)
            per_page: Taille de page (1-100, bornée par le Query endpoint)

        Returns:
            Tuple[List[User], int]: Liste d'utilisateurs et nombre total
        """
        if not organization_ids:
            return [], 0

        subq = select(UserOrganization.user_id).where(
            UserOrganization.organization_id.in_(organization_ids)
        )
        result = await db.execute(
            select(User)
            .where(User.id.in_(subq))
            .order_by(User.username)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        users = list(result.scalars().all())

        count_subq = select(func.count()).select_from(User).where(User.id.in_(subq))
        count_result = await db.execute(count_subq)
        total = count_result.scalar_one()

        return users, total

    @staticmethod
    async def create(db: AsyncSession, user_data: UserCreate) -> User:
        """
        Crée un nouvel utilisateur.

        STORY-121.3 : l'utilisateur est créé **sans** colonne organisation ;
        si ``user_data.organization_id`` est fourni (org cible validée par
        l'endpoint appelant), l'appartenance est créée via l'association
        ``user_organizations`` avec le rôle par défaut ``viewer`` (least
        privilege — un rôle explicite ne peut être posé que via les
        endpoints membres protégés).

        Args:
            db: Session de base de données async
            user_data: Données de création

        Returns:
            Utilisateur créé
        """
        # Hash du mot de passe
        hashed_password = UserService.hash_password(user_data.password)

        # Création du modèle (sans organisation — STORY-121.3)
        user = User(
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            hashed_password=hashed_password,
            is_superuser=user_data.is_superuser,
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Rattachement via l'association (rôle viewer par défaut).
        # Import différé : user_organization_service importe UserService
        # (import cyclique sinon).
        if user_data.organization_id:
            from .user_organization_service import UserOrganizationService

            await UserOrganizationService.add_member(
                db,
                user_data.organization_id,
                OrganizationMemberAddRequest(user_id=UUID(user.id)),
            )

        return user

    @staticmethod
    async def update(db: AsyncSession, user: User, user_data: UserUpdate) -> User:
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

        # organization_id : traité comme opération d'association par
        # l'endpoint users.py — pas une colonne (STORY-121.3)
        update_data.pop("organization_id", None)

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

    @staticmethod
    async def delete_many(
        db: AsyncSession, user_ids: List[str], current_user_id: str
    ) -> Tuple[List[str], List[str]]:
        """
        Supprime plusieurs utilisateurs en masse.

        Args:
            db: Session de base de données async
            user_ids: Liste des IDs d'utilisateurs à supprimer
            current_user_id: ID de l'utilisateur effectuant la suppression (pour empêcher l'auto-suppression)

        Returns:
            Tuple[List[str], List[str]]: (IDs supprimés avec succès, IDs en échec)
        """
        success = []
        failed = []

        for user_id in user_ids:
            # Empêcher l'auto-suppression
            if user_id == current_user_id:
                failed.append(user_id)
                continue

            user = await UserService.get_by_id(db, user_id)
            if user:
                await db.delete(user)
                success.append(user_id)
            else:
                failed.append(user_id)

        await db.commit()
        return success, failed

    @staticmethod
    async def update_organization_many(
        db: AsyncSession, user_ids: List[str], organization_id: str
    ) -> Tuple[List[str], List[str]]:
        """
        Met à jour l'organisation de plusieurs utilisateurs en masse.

        Args:
            db: Session de base de données async
            user_ids: Liste des IDs d'utilisateurs à mettre à jour
            organization_id: ID de la nouvelle organisation

        Returns:
            Tuple[List[str], List[str]]: (IDs mis à jour avec succès, IDs en échec)
        """
        success = []
        failed = []

        # Import différé : user_organization_service importe UserService
        from .user_organization_service import UserOrganizationService

        for user_id in user_ids:
            user = await UserService.get_by_id(db, user_id)
            if user:
                # STORY-121.3 : réaffectation via les associations —
                # suppression des appartenances existantes puis
                # rattachement à la nouvelle organisation (rôle viewer)
                result = await db.execute(
                    select(UserOrganization).where(UserOrganization.user_id == user.id)
                )
                for link in result.scalars().all():
                    await db.delete(link)
                await db.flush()
                await UserOrganizationService.add_member(
                    db,
                    organization_id,
                    OrganizationMemberAddRequest(user_id=UUID(user.id)),
                )
                success.append(user_id)
            else:
                failed.append(user_id)

        await db.commit()
        return success, failed
