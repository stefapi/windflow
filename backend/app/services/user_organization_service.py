"""
Service métier pour la gestion des associations utilisateur ↔ organisation.

CRUD de la table ``user_organizations`` (modèle et enum ``Role`` fournis
par STORY-121.1) + helper d'isolation cross-organisation ``is_member``
consommé par les 4 endpoints de gestion des membres (spec 09 §
Organizations).

Le rôle système ``super_admin`` ne peut jamais être stocké dans la table
d'association : il est absent de l'enum ``Role`` (double barrière avec le
``@validates("role")`` du modèle ``UserOrganization``).
"""

from typing import List, Optional, Union
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..enums.rbac import Role
from ..models.user import User
from ..models.user_organization import UserOrganization
from ..schemas.organization_member import OrganizationMemberAddRequest
from .user_service import UserService


def _as_str_id(value: Union[UUID, str]) -> str:
    """Convertit un identifiant en chaîne (les modèles stockent des ``String(36)``)."""
    return str(value) if isinstance(value, UUID) else value


class UserOrganizationService:
    """Service de gestion des associations utilisateur ↔ organisation (RBAC)."""

    @staticmethod
    async def is_member(
        db: AsyncSession, user: User, organization_id: Union[UUID, str]
    ) -> bool:
        """
        Vérifie l'appartenance d'un utilisateur à une organisation (isolation cross-org).

        Retourne ``True`` si l'utilisateur est superuser (bypass — le Super
        Admin a tous les droits, spec 08 ; pattern ``get_organization``),
        sinon s'il existe une ligne ``UserOrganization`` pour
        ``(user.id, organization_id)``.

        Depuis STORY-121.3, l'appartenance provient **exclusivement** de la
        table d'association : le fallback intérim sur la colonne héritée
        ``user.organization_id`` a été retiré après la migration des
        données (chaque utilisateur pré-existant a sa ligne d'association).

        Args:
            db: Session de base de données async
            user: Utilisateur dont vérifier l'appartenance
            organization_id: ID de l'organisation ciblée

        Returns:
            True si l'utilisateur appartient à l'organisation (ou est superuser)
        """
        if user.is_superuser:
            return True

        organization_id_str = _as_str_id(organization_id)

        result = await db.execute(
            select(UserOrganization).where(
                UserOrganization.user_id == user.id,
                UserOrganization.organization_id == organization_id_str,
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def get_user_organization_ids(db: AsyncSession, user: User) -> List[str]:
        """
        Retourne les IDs des organisations auxquelles l'utilisateur appartient.

        Primitive de bascule multi-appartenance (STORY-121.3) : utilisée
        pour le scoping des listes (``.where(Model.organization_id.in_(
        org_ids))``) à la place de l'ancienne valeur unique
        ``user.organization_id``.

        Args:
            db: Session de base de données async
            user: Utilisateur dont lister les appartenances

        Returns:
            Liste des ``organization_id`` (liste vide si aucune appartenance)
        """
        result = await db.execute(
            select(UserOrganization.organization_id).where(
                UserOrganization.user_id == user.id
            )
        )
        return [str(org_id) for org_id in result.scalars().all()]

    @staticmethod
    async def get_primary_organization_id(
        db: AsyncSession, user: User
    ) -> Optional[str]:
        """
        Retourne l'organisation « primaire » de l'utilisateur.

        Primaire = plus ancienne appartenance (compat : ancien
        ``organization_id`` unique) — première ligne ``UserOrganization``
        par ``joined_at`` croissant.

        Primitive de bascule (STORY-121.3) : utilisée pour les créations
        de ressources (stack, deployment, target…) à la place de
        ``user.organization_id``.

        Args:
            db: Session de base de données async
            user: Utilisateur dont résoudre l'organisation primaire

        Returns:
            ``organization_id`` de la plus ancienne appartenance,
            ``None`` si l'utilisateur n'appartient à aucune organisation
        """
        result = await db.execute(
            select(UserOrganization.organization_id)
            .where(UserOrganization.user_id == user.id)
            .order_by(UserOrganization.joined_at)
            .limit(1)
        )
        primary = result.scalar_one_or_none()
        return str(primary) if primary is not None else None

    @staticmethod
    async def list_members(
        db: AsyncSession,
        organization_id: Union[UUID, str],
        skip: int = 0,
        limit: int = 100,
    ) -> List[UserOrganization]:
        """
        Liste les membres d'une organisation avec pagination.

        Chaque ligne est retournée avec sa relation ``user`` chargée
        (``selectinload``) pour construire la réponse sans requête
        supplémentaire.

        Args:
            db: Session de base de données async
            organization_id: ID de l'organisation
            skip: Nombre d'éléments à sauter (pagination)
            limit: Nombre maximum d'éléments à retourner

        Returns:
            Liste des associations triées par date d'adhésion
        """
        organization_id_str = _as_str_id(organization_id)
        result = await db.execute(
            select(UserOrganization)
            .where(UserOrganization.organization_id == organization_id_str)
            .options(selectinload(UserOrganization.user))
            .order_by(UserOrganization.joined_at)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_members(
        db: AsyncSession,
        organization_id: Union[UUID, str],
    ) -> int:
        """
        Compte les membres d'une organisation (STORY-128).

        ``COUNT`` scopé à l'organisation — même filtre que
        :meth:`list_members` (rules 40 : pas d'oracle cross-org).

        Args:
            db: Session de base de données async
            organization_id: ID de l'organisation

        Returns:
            Nombre total de membres de l'organisation
        """
        organization_id_str = _as_str_id(organization_id)
        result = await db.execute(
            select(func.count())
            .select_from(UserOrganization)
            .where(UserOrganization.organization_id == organization_id_str)
        )
        return int(result.scalar() or 0)

    @staticmethod
    async def add_member(
        db: AsyncSession,
        organization_id: Union[UUID, str],
        data: OrganizationMemberAddRequest,
    ) -> UserOrganization:
        """
        Ajoute un utilisateur comme membre d'une organisation.

        Le rôle par défaut ``viewer`` est géré par le schéma
        ``OrganizationMemberAddRequest`` (défaut Pydantic).

        Note sécurité (STORY-122.4) : la protection anti-escalade (rôle
        attribué strictement inférieur à celui de l'acteur) est vérifiée
        au niveau endpoint ; ce service reste intentionnellement neutre
        car il est aussi consommé par la seed/CLI admin.

        Args:
            db: Session de base de données async
            organization_id: ID de l'organisation
            data: Données d'ajout (``user_id`` + ``role`` optionnel)

        Returns:
            Association créée

        Raises:
            ValueError: Si l'utilisateur cible n'existe pas ou est déjà membre
                (mappées 404/409 par l'endpoint)
        """
        organization_id_str = _as_str_id(organization_id)

        target_user = await UserService.get_by_id(db, str(data.user_id))
        if target_user is None:
            raise ValueError(f"Utilisateur {data.user_id} introuvable")

        existing = await UserOrganizationService.get_membership(
            db, organization_id_str, data.user_id
        )
        if existing is not None:
            raise ValueError(f"L'utilisateur {data.user_id} est déjà membre")

        membership = UserOrganization(
            user_id=str(data.user_id),
            organization_id=organization_id_str,
            role=data.role,
        )
        db.add(membership)
        await db.commit()
        await db.refresh(membership)
        return membership

    @staticmethod
    async def get_membership(
        db: AsyncSession,
        organization_id: Union[UUID, str],
        user_id: Union[UUID, str],
    ) -> Optional[UserOrganization]:
        """
        Récupère une association par sa PK composite ``(user_id, organization_id)``.

        La relation ``user`` est chargée (``selectinload``) pour la réponse.

        Args:
            db: Session de base de données async
            organization_id: ID de l'organisation
            user_id: ID de l'utilisateur

        Returns:
            Association trouvée ou None
        """
        result = await db.execute(
            select(UserOrganization)
            .where(
                UserOrganization.user_id == _as_str_id(user_id),
                UserOrganization.organization_id == _as_str_id(organization_id),
            )
            .options(selectinload(UserOrganization.user))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_member_role(
        db: AsyncSession, membership: UserOrganization, role: Role
    ) -> UserOrganization:
        """
        Met à jour le rôle d'un membre existant.

        Note sécurité (STORY-122.4) : la protection anti-escalade (nouveau
        rôle strictement inférieur au rôle de l'acteur, rôle actuel de la
        cible strictement inférieur aussi — couvre l'auto-promotion) est
        vérifiée au niveau endpoint ; ce service reste intentionnellement
        neutre car il est aussi consommé par la seed/CLI admin.

        Args:
            db: Session de base de données async
            membership: Association à mettre à jour
            role: Nouveau rôle (borné enum ``Role``)

        Returns:
            Association mise à jour
        """
        membership.role = role
        await db.commit()
        await db.refresh(membership)
        return membership

    @staticmethod
    async def remove_member(db: AsyncSession, membership: UserOrganization) -> None:
        """
        Retire un membre d'une organisation (supprime l'association).

        Ne touche jamais ``User.is_superuser`` (le retrait d'une
        association ne modifie pas les rôles système).

        Args:
            db: Session de base de données async
            membership: Association à supprimer
        """
        await db.delete(membership)
        await db.commit()
