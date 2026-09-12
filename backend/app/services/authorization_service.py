"""
Service central d'autorisation RBAC (STORY-122.1, spec 08 § Implémentation).

Résout le rôle d'un utilisateur avec cache TTL 300 s et expose les
primitives de vérification hiérarchique consommées par les dépendances
``require_role`` / ``require_role_ws`` (``auth/rbac.py``) puis par les
sous-stories 122.2 → 122.6 pour les ~118 endpoints.

Deux notions de rôle distinctes :
- **rôle global effectif** — ``get_global_role`` : ``super_admin`` si
  ``User.is_superuser`` (accès total toutes organisations), sinon le max
  des rôles portés par les associations ``user_organizations`` ;
  ``viewer`` si aucune appartenance (moindre privilège, conservateur) ;
- **rôle dans une organisation** — ``get_role_in_organization`` : la ligne
  ``user_organizations.role`` pour ``(user_id, organization_id)``, utilisée
  pour l'isolation et la gestion des membres. Le superuser y est
  ``super_admin`` partout (bypass, spec 08).

Le rôle ``super_admin`` n'est **jamais** stockable en association (enum
``Role`` sans cette valeur + ``@validates`` du modèle) : il ne peut être
dérivé que du flag système ``User.is_superuser``.

Cache : clé ``rbac:role:{user_id}`` via ``core.cache.get_role_cache()``
(Redis en mode standard, mémoire en mode léger), TTL ``settings.
rbac_role_cache_ttl`` (300 s). Invalidation immédiate au changement de
rôle via ``invalidate_user_role_cache`` (hooks des écritures membres).
"""

import logging
from typing import Optional, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.cache import RedisRoleCache, get_role_cache
from ..models.user import User
from ..models.user_organization import UserOrganization

logger = logging.getLogger("windflow.authorization")

# Hiérarchie des rôles (spec 08 § Implémentation) — tout rôle inconnu est
# traité comme -1 (jamais suffisant) côté vérification.
ROLE_HIERARCHY: dict[str, int] = {
    "viewer": 0,
    "operator": 1,
    "admin": 2,
    "super_admin": 3,
}

# Rôle système (porté par User.is_superuser, jamais stockable en association)
SUPER_ADMIN: str = "super_admin"

# Rôle par défaut — conservateur (moindre privilège)
DEFAULT_ROLE: str = "viewer"

# Clé de cache du rôle global + canal pub/sub d'invalidation (spec 08)
ROLE_CACHE_KEY_PREFIX: str = "rbac:role:"
ROLE_INVALIDATION_CHANNEL: str = "rbac:role:invalidate"


def _as_str_id(value: Union[UUID, str]) -> str:
    """Convertit un identifiant en chaîne (les modèles stockent des ``String(36)``)."""
    return str(value) if isinstance(value, UUID) else value


def _role_to_str(role: object) -> str:
    """Normalise un rôle en chaîne (enum ``Role`` ou valeur déjà texte)."""
    return getattr(role, "value", str(role))


class AuthorizationService:
    """Service central d'autorisation RBAC (méthodes statiques async)."""

    @staticmethod
    async def get_global_role(db: AsyncSession, user: User) -> str:
        """Résout le rôle global effectif de l'utilisateur (avec cache TTL).

        ``super_admin`` immédiatement si ``user.is_superuser`` (court-circuit,
        pas de cache nécessaire — rôle système non révocable via associations).
        Sinon : max des rôles des associations ``user_organizations`` ;
        ``viewer`` si aucune appartenance (conservateur). Le résultat est mis
        en cache sous ``rbac:role:{user_id}`` pour ``settings.rbac_role_cache_ttl``
        secondes.

        Args:
            db: Session de base de données async
            user: Utilisateur dont résoudre le rôle global

        Returns:
            Libellé de rôle : ``viewer`` | ``operator`` | ``admin`` | ``super_admin``
        """
        if user.is_superuser:
            return SUPER_ADMIN

        user_id = str(user.id)
        cache = await get_role_cache()
        cache_key = f"{ROLE_CACHE_KEY_PREFIX}{user_id}"

        cached = await cache.get(cache_key)
        if cached is not None:
            logger.debug(
                "RBAC global role resolved from cache",
                extra={"user_id": user_id, "role": cached},
            )
            return cached

        result = await db.execute(
            select(UserOrganization.role).where(UserOrganization.user_id == user_id)
        )
        roles = [
            _role_to_str(role)
            for role in result.scalars().all()
            if _role_to_str(role) in ROLE_HIERARCHY
        ]
        role = (
            max(roles, key=lambda label: ROLE_HIERARCHY[label])
            if roles
            else DEFAULT_ROLE
        )

        await cache.set(cache_key, role, ttl=settings.rbac_role_cache_ttl)
        logger.debug(
            "RBAC global role resolved from database",
            extra={"user_id": user_id, "role": role},
        )
        return role

    @staticmethod
    async def get_role_in_organization(
        db: AsyncSession, user: User, organization_id: Union[UUID, str]
    ) -> Optional[str]:
        """Résout le rôle de l'utilisateur dans une organisation donnée.

        ``super_admin`` si superuser (accès total toutes organisations,
        spec 08) ; sinon la valeur ``user_organizations.role`` pour
        ``(user.id, organization_id)`` — ``None`` si non-membre (isolation
        cross-organisation).

        Non caché : lecture directe réservée aux checks d'isolation ; le
        cache TTL cible le rôle global (clé par utilisateur).

        Args:
            db: Session de base de données async
            user: Utilisateur dont résoudre le rôle
            organization_id: ID de l'organisation ciblée

        Returns:
            Libellé de rôle, ou ``None`` si l'utilisateur n'est pas membre
        """
        if user.is_superuser:
            return SUPER_ADMIN

        result = await db.execute(
            select(UserOrganization.role).where(
                UserOrganization.user_id == user.id,
                UserOrganization.organization_id == _as_str_id(organization_id),
            )
        )
        stored = result.scalar_one_or_none()
        if stored is None:
            return None
        return _role_to_str(stored)

    @staticmethod
    async def role_at_least(
        db: AsyncSession,
        user: User,
        minimum: str,
        organization_id: Optional[Union[UUID, str]] = None,
    ) -> bool:
        """Vérifie que l'utilisateur atteint au moins le rôle ``minimum``.

        Si ``organization_id`` est fournie : vérifie le rôle **dans cette
        organisation** (non-membre → False) ; sinon le rôle global effectif.

        Args:
            db: Session de base de données async
            user: Utilisateur à vérifier
            minimum: Rôle minimum requis (doit être dans ``ROLE_HIERARCHY``)
            organization_id: Organisation de scope (optionnel)

        Returns:
            True si le rôle effectif est >= ``minimum`` dans la hiérarchie

        Raises:
            ValueError: Si ``minimum`` n'est pas un rôle connu
        """
        if minimum not in ROLE_HIERARCHY:
            raise ValueError(
                f"Unknown minimum role {minimum!r}: expected one of "
                f"{sorted(ROLE_HIERARCHY)}"
            )

        if organization_id is not None:
            role = await AuthorizationService.get_role_in_organization(
                db, user, organization_id
            )
            if role is None:
                return False
        else:
            role = await AuthorizationService.get_global_role(db, user)

        return ROLE_HIERARCHY.get(role, -1) >= ROLE_HIERARCHY[minimum]

    @staticmethod
    async def invalidate_user_role_cache(user_id: Union[UUID, str]) -> None:
        """Invalide immédiatement le rôle global caché de l'utilisateur.

        Appelée par les écritures de gestion des membres (ajout / changement
        de rôle / retrait) pour qu'un changement de rôle soit effectif sans
        attendre l'expiration de la TTL (300 s au pire cas sinon).

        En mode Redis, publie en best-effort un message d'invalidation pour
        les autres workers (spec 08 § Invalidation) ; un échec de publication
        est sans conséquence — la TTL garantit la convergence.

        Args:
            user_id: ID de l'utilisateur dont invalider le cache de rôle
        """
        user_id_str = _as_str_id(user_id)
        cache = await get_role_cache()
        await cache.delete(f"{ROLE_CACHE_KEY_PREFIX}{user_id_str}")

        # Publication best-effort aux autres workers (mode Redis uniquement)
        if isinstance(cache, RedisRoleCache):
            await cache.publish(ROLE_INVALIDATION_CHANNEL, user_id_str)

        logger.info(
            "RBAC role cache invalidated",
            extra={"user_id": user_id_str},
        )
