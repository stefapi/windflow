"""Résolution d'un Host (``Target``) + vérification d'accès pour les canaux
WebSocket SSH (STORY-164.2 — P2-5, axe C3).

Factorise la logique partagée par ``/ws/ssh/{host_id}`` et
``/ws/journal/{host_id}`` (pattern ``verify_deployment_access`` de
``deployment_logs.py``) :

- résolution de la ``Target`` par ``id`` (404 si introuvable) ;
- isolation organisationnelle via ``UserOrganizationService.is_member``
  (STORY-121.3 — appartenance par association, superuser bypass inclus) ;
- résolution du username SSH (credentials → access profile → ``root``).

Les exceptions levées sont des ``HTTPException`` (404/401/403) que les
handlers WebSocket traduisent en message ``error`` + fermeture 1008 —
jamais de détail sensible dans le message client (rules 40).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.target import Target
from ..models.user import User
from ..services.user_organization_service import UserOrganizationService

logger = logging.getLogger(__name__)

# Username SSH de repli quand ni les credentials ni le profil d'accès
# n'en définissent un (convention Hosts distants — spec 15).
DEFAULT_SSH_USERNAME = "root"


async def resolve_host_and_check_access(
    host_id: str, user: Optional[User], db: AsyncSession
) -> Target:
    """Résout un Host par id et vérifie l'accès de l'utilisateur.

    Résolution ``Target`` par ``id`` (404 si introuvable), puis isolation
    organisationnelle (403 si l'utilisateur n'est pas membre de
    l'organisation du Host) — pattern ``verify_deployment_access``
    (``deployment_logs.py``).

    Args:
        host_id: Identifiant du Host (``targets.id``).
        user: Utilisateur authentifié (None → 401, garde défensive).
        db: Session de base de données async.

    Returns:
        La ``Target`` résolue (host/port/ssh_key_id/credentials).

    Raises:
        HTTPException: 404 (introuvable), 401 (non authentifié) ou
            403 (organisation étrangère).
    """
    stmt = select(Target).where(Target.id == host_id)
    result = await db.execute(stmt)
    target = result.scalar_one_or_none()

    if target is None:
        logger.info("Host not found for WebSocket channel", extra={"host_id": host_id})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Host not found"
        )

    if user is None:
        # Garde défensive — l'auth est déjà refusée au handshake par
        # get_current_user_ws ; conservée par symétrie avec le pattern
        # verify_deployment_access.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    # Isolation organisationnelle — STORY-121.3 : appartenance via
    # l'association (is_member, superuser bypass inclus).
    if not await UserOrganizationService.is_member(db, user, target.organization_id):
        logger.info(
            "Host access denied (organization mismatch)",
            extra={"host_id": host_id, "user_id": str(user.id)},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this host",
        )

    return target


def resolve_ssh_username(target: Target) -> str:
    """Résout le username SSH d'un Host (credentials → access profile → root).

    Priorité cohérente avec le scanner : ``credentials["username"]``
    (auth password persistée), puis ``access_profile["ssh_user"]``
    (profil détecté au scan), sinon ``root``.

    Args:
        target: Cible persistée.

    Returns:
        Username SSH (jamais vide).
    """
    creds: Any = target.decrypted_credentials or {}
    if isinstance(creds, dict):
        username = creds.get("username")
        if isinstance(username, str) and username.strip():
            return username.strip()

        profile = target.access_profile
        if isinstance(profile, dict):
            ssh_user = profile.get("ssh_user")
            if isinstance(ssh_user, str) and ssh_user.strip():
                return ssh_user.strip()

    return DEFAULT_SSH_USERNAME
