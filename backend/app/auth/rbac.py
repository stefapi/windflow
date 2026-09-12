"""
Dépendances FastAPI RBAC — ``require_role`` / ``require_role_ws`` (STORY-122.1).

Socle d'autorisation appliqué aux ~118 endpoints par les sous-stories
122.2 → 122.6 (spec 08 § Dépendance FastAPI) :

- ``require_role(minimum_role)`` : factory de dépendance HTTP vérifiant que
  l'utilisateur actif authentifié atteint au moins ``minimum_role`` dans la
  hiérarchie ``viewer < operator < admin < super_admin`` (résolution via
  ``AuthorizationService.get_global_role``, cache TTL 300 s) ;
- ``require_role_ws(minimum_role)`` : variante handshake WebSocket — rôle
  insuffisant → ``WebSocketException(1008)`` (pattern ``get_current_user_ws``).

Chaîne de dépendances : ``get_current_active_user`` (401 sans token via
``oauth2_scheme``, 403 utilisateur inactif) **puis** 403 « Not enough
permissions » si rôle insuffisant (message identique à ``require_superuser``,
sans révéler la hiérarchie interne).

Mode développement (``DISABLE_AUTH=true``) : l'auto-login superadmin rend
tout ``require_role`` passant sans code dédié — l'utilisateur résolu est
déjà ``super_admin`` par construction.

Aliases prédéfinis : ``require_viewer``, ``require_operator``,
``require_admin``, ``require_super_admin`` (usage direct dans les routers).
"""

import logging
from collections.abc import Callable

from fastapi import (
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.user import User
from ..services.authorization_service import (
    ROLE_HIERARCHY,
    AuthorizationService,
)
from .dependencies import get_current_active_user, get_current_user_ws

logger = logging.getLogger("windflow.rbac")


def require_role(minimum_role: str) -> Callable:
    """Factory de dépendance FastAPI imposant un rôle minimum (hiérarchique).

    Le rôle global effectif de l'utilisateur est résolu via
    ``AuthorizationService.get_global_role`` (cache TTL 300 s — un changement
    de rôle est pris en compte au plus tard 300 s après, immédiatement via
    l'invalidation posée sur les écritures membres). ``User.is_superuser``
    = ``super_admin`` = tous droits sur toutes les organisations.

    Args:
        minimum_role: Rôle minimum requis — ``"viewer"`` | ``"operator"`` |
            ``"admin"`` | ``"super_admin"``. Paramètre code-only (jamais un
            input utilisateur) : une valeur inconnue est une erreur de
            développement levée à la construction de la dépendance
            (AssertionError), pas une erreur HTTP.

    Returns:
        Dépendance FastAPI retournant l'utilisateur autorisé

    Example:
        @router.post("/compute/stacks/{stack_id}/deploy")
        async def deploy_stack(
            stack_id: UUID,
            user: User = Depends(require_role("operator")),
        ):
            \"\"\"Déployer une stack — nécessite le rôle Operator minimum.\"\"\"
    """
    assert minimum_role in ROLE_HIERARCHY, (
        f"Unknown minimum role {minimum_role!r}: expected one of "
        f"{sorted(ROLE_HIERARCHY)} — require_role est un paramètre code-only"
    )

    async def role_checker(
        request: Request,
        current_user: User = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_db),
    ) -> User:
        """Vérifie le rôle global effectif de l'utilisateur actif courant."""
        role = await AuthorizationService.get_global_role(session, current_user)
        if ROLE_HIERARCHY.get(role, -1) < ROLE_HIERARCHY[minimum_role]:
            logger.warning(
                "RBAC: insufficient role for endpoint",
                extra={
                    "user_id": str(current_user.id),
                    "minimum_role": minimum_role,
                    "path": request.url.path,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return role_checker


def require_role_ws(minimum_role: str) -> Callable:
    """Variante WebSocket de ``require_role`` (refus handshake 1008).

    Même logique de hiérarchie, mais pour les canaux WebSocket à token
    en query parameter : compose la dépendance stricte ``get_current_user_ws``
    (401/1008 sans token valide, jamais d'utilisateur anonyme) puis refuse
    le handshake avec ``WebSocketException(1008)`` (« policy violation »,
    pattern ``get_current_user_ws``) si le rôle global effectif est
    insuffisant.

    Consommé par STORY-122.6 (canaux WebSocket admin/instance).

    Args:
        minimum_role: Rôle minimum requis (même validation que ``require_role``)

    Returns:
        Dépendance WebSocket retournant l'utilisateur autorisé

    Example:
        @router.websocket("/ws/admin")
        async def admin_channel(
            websocket: WebSocket,
            user: User = Depends(require_role_ws("admin")),
        ):
            ...
    """
    assert minimum_role in ROLE_HIERARCHY, (
        f"Unknown minimum role {minimum_role!r}: expected one of "
        f"{sorted(ROLE_HIERARCHY)} — require_role_ws est un paramètre code-only"
    )

    async def role_checker_ws(
        websocket: WebSocket,
        current_user: User = Depends(get_current_user_ws),
        session: AsyncSession = Depends(get_db),
    ) -> User:
        """Vérifie le rôle global effectif au handshake WebSocket."""
        role = await AuthorizationService.get_global_role(session, current_user)
        if ROLE_HIERARCHY.get(role, -1) < ROLE_HIERARCHY[minimum_role]:
            logger.warning(
                "RBAC: insufficient role for WebSocket channel",
                extra={
                    "user_id": str(current_user.id),
                    "minimum_role": minimum_role,
                    "path": websocket.url.path,
                },
            )
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Insufficient permissions",
            )
        return current_user

    return role_checker_ws


async def ensure_role_ws(
    websocket: WebSocket,
    user: User,
    minimum_role: str,
    session: AsyncSession,
) -> User:
    """Vérificateur de rôle minimum appelable manuellement dans un endpoint WS.

    Même sémantique que ``require_role_ws`` (même code 1008, même message,
    même log warning avec path/user_id — jamais de token), adaptée à
    l'enchaînement manuel ``user = Depends(get_current_user_ws)`` puis
    ``await ensure_role_ws(...)`` : FastAPI n'applique pas aussi directement
    les dépendances factory paramétrées sur les décorateurs
    ``@router.websocket`` que sur HTTP.

    À utiliser **avant ``websocket.accept()``** pour refuser le handshake
    sans ouvrir le canal, ou immédiatement après l'authentification « premier
    message » (canaux général/terminal) pour fermer en 1008 sans exécuter la
    logique du canal.

    Args:
        websocket: Connexion WebSocket courante (pour le path de log)
        user: Utilisateur actif authentifié (via ``get_current_user_ws`` ou
            ``authenticate_ws_first_message``)
        minimum_role: Rôle minimum requis (même validation que ``require_role``)
        session: Session de base de données async (résolution du rôle)

    Returns:
        L'utilisateur vérifié (chaînage facilité)

    Raises:
        WebSocketException: 1008 « Insufficient permissions » si rôle insuffisant
    """
    assert minimum_role in ROLE_HIERARCHY, (
        f"Unknown minimum role {minimum_role!r}: expected one of "
        f"{sorted(ROLE_HIERARCHY)} — ensure_role_ws est un paramètre code-only"
    )

    role = await AuthorizationService.get_global_role(session, user)
    if ROLE_HIERARCHY.get(role, -1) < ROLE_HIERARCHY[minimum_role]:
        logger.warning(
            "RBAC: insufficient role for WebSocket channel",
            extra={
                "user_id": str(user.id),
                "minimum_role": minimum_role,
                "path": websocket.url.path,
            },
        )
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Insufficient permissions",
        )
    return user


# Aliases prédéfinis — usage direct dans les routers (sous-stories 122.2 → 122.6)
require_viewer = require_role("viewer")
require_operator = require_role("operator")
require_admin = require_role("admin")
require_super_admin = require_role("super_admin")

# ``require_role("viewer")`` est sémantiquement équivalent à
# ``get_current_active_user`` : tout utilisateur authentifié actif a un
# rôle global >= viewer (défaut conservateur). Les endpoints déjà protégés
# par ``get_current_active_user`` n'ont donc pas besoin de bascule.
