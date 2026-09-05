"""
Dépendances FastAPI pour authentification et autorisation.

Fournit les fonctions de dépendance pour protéger les routes API.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Optional

from fastapi import (
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketException,
    status,
)
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import db as database
from ..database import get_db
from ..models.user import User
from ..services.user_service import UserService
from .jwt import decode_access_token

logger = logging.getLogger(__name__)

# Schéma OAuth2 pour extraction du token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# Timeout (secondes) pour recevoir le message d'authentification WebSocket
# ("JWT au premier message"). Constante module-level pour être patchée en tests.
WS_AUTH_TIMEOUT_SECONDS: float = 30.0


async def get_current_user(
    token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_db)
) -> User:
    """
    Récupère l'utilisateur courant à partir du token JWT.

    En mode développement (DISABLE_AUTH=true), retourne automatiquement
    le premier utilisateur superadmin trouvé en base de données.

    Args:
        token: Token JWT extrait de l'en-tête Authorization
        session: Session de base de données

    Returns:
        Utilisateur authentifié

    Raises:
        HTTPException: Si le token est invalide ou l'utilisateur n'existe pas
    """
    # Mode développement sans authentification
    if settings.disable_auth:
        user = await UserService.get_first_superadmin(session)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No superadmin user found in database for development mode",
            )
        return user

    # Mode production avec authentification JWT normale
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Décoder le token
    if token is None:
        raise credentials_exception
    token_data = decode_access_token(token)
    if token_data is None or token_data.user_id is None:
        raise credentials_exception

    # Récupérer l'utilisateur
    user = await UserService.get_by_id(session, token_data.user_id)
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Vérifie que l'utilisateur est actif.

    Args:
        current_user: Utilisateur courant

    Returns:
        Utilisateur actif

    Raises:
        HTTPException: Si l'utilisateur est inactif
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )
    return current_user


async def require_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Vérifie que l'utilisateur est un superutilisateur.

    Args:
        current_user: Utilisateur courant actif

    Returns:
        Superutilisateur

    Raises:
        HTTPException: Si l'utilisateur n'est pas superutilisateur
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return current_user


# Alias pour compatibilité avec les routes admin
get_current_superadmin = require_superuser


async def get_current_user_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    Récupère l'utilisateur courant à partir du token JWT pour WebSocket.

    Dépendance **stricte** : sans token, token invalide/expiré ou utilisateur
    inactif, le handshake WebSocket est refusé (code 1008 « policy violation »)
    — cette fonction ne retourne jamais d'utilisateur anonyme.

    En mode développement (DISABLE_AUTH=true), retourne automatiquement
    le premier utilisateur superadmin trouvé en base de données (si aucun
    superadmin n'existe, la connexion est refusée).

    L'authentification WebSocket se fait via query parameter:
    ws://host/path?token=JWT_TOKEN

    Args:
        websocket: Connexion WebSocket
        token: Token JWT extrait du query parameter
        session: Session de base de données

    Returns:
        Utilisateur authentifié

    Raises:
        WebSocketException: Code 1008 si l'authentification échoue
            (refus du handshake par FastAPI, avant acceptation).
    """
    # Mode développement sans authentification : auto-login superadmin
    if settings.disable_auth:
        user = await UserService.get_first_superadmin(session)
        if user is None:
            logger.warning(
                "WebSocket auth refused in disable_auth mode: no superadmin in database",
                extra={"path": websocket.url.path},
            )
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="No superadmin user found for development mode",
            )
        return user

    # Mode authentification JWT stricte (query parameter)
    if not token:
        logger.warning(
            "WebSocket handshake refused: no token provided",
            extra={"path": websocket.url.path},
        )
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required"
        )

    try:
        token_data = decode_access_token(token)
        if token_data is None or token_data.user_id is None:
            logger.warning(
                "WebSocket handshake refused: invalid or expired token",
                extra={"path": websocket.url.path, "token_length": len(token)},
            )
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
            )

        user = await UserService.get_by_id(session, token_data.user_id)
        if user is None or not user.is_active:
            logger.warning(
                "WebSocket handshake refused: user not found or inactive",
                extra={"path": websocket.url.path, "user_id": str(token_data.user_id)},
            )
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="User not found or inactive",
            )

        return user

    except WebSocketException:
        raise
    except Exception:
        # Erreur inattendue (DB, décodage) → refus sans exposer le détail
        logger.exception(
            "WebSocket handshake refused: unexpected error during authentication",
            extra={"path": websocket.url.path},
        )
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed"
        )


async def authenticate_ws_first_message(
    websocket: WebSocket,
    on_failure: Optional[Callable[[str, str], Awaitable[None]]] = None,
) -> Optional[User]:
    """
    Authentifie une connexion WebSocket via le mécanisme « JWT au premier message ».

    À appeler **après** ``websocket.accept()`` (ce helper ne fait pas l'accept).
    Le client doit envoyer ``{"type": "auth", "token": "<JWT>"}`` dans les
    ``WS_AUTH_TIMEOUT_SECONDS`` secondes suivant l'acceptation.

    En mode développement (DISABLE_AUTH=true), le token fourni est ignoré et
    le premier superadmin de la base est auto-login ; le premier message reste
    toutefois obligatoire (les clients WindFlow envoient toujours l'auth en
    premier). Un silence au-delà du timeout ferme la connexion (1008).

    Args:
        websocket: Connexion WebSocket déjà acceptée
        on_failure: Callback asynchrone optionnel ``(reason_detail, token_hint)``
            appelé avant la fermeture en cas d'échec (ex. audit terminal).

    Returns:
        Utilisateur authentifié, ou ``None`` si l'authentification a échoué
        (la connexion est alors fermée avec le code 1008).

    Note:
        Les raisons de fermeture sont volontairement génériques côté client ;
        ``on_failure`` reçoit le détail pour l'audit/les logs. Le token n'est
        jamais loggé (sa longueur seulement).
    """
    try:
        data = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=WS_AUTH_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        await _ws_auth_fail(
            websocket,
            on_failure,
            "Authentication timeout - no message received",
            "Authentication timeout",
        )
        return None
    except Exception:
        await _ws_auth_fail(
            websocket,
            on_failure,
            "Receive error before authentication",
            "Receive error",
        )
        return None

    try:
        message = json.loads(data)
    except json.JSONDecodeError:
        await _ws_auth_fail(
            websocket, on_failure, "Invalid JSON format", "Invalid message format"
        )
        return None

    if (
        not isinstance(message, dict)
        or message.get("type") != "auth"
        or "token" not in message
    ):
        await _ws_auth_fail(
            websocket,
            on_failure,
            "Authentication required as first message",
            "Authentication required",
        )
        return None

    token = message["token"]
    token_hint = (
        f"length={len(token)}" if isinstance(token, str) else "non-string-token"
    )

    async with database.session() as db:
        # Mode développement : auto-login superadmin, token ignoré
        if settings.disable_auth:
            user = await UserService.get_first_superadmin(db)
            if user is None:
                await _ws_auth_fail(
                    websocket,
                    on_failure,
                    "No superadmin user found in database for development mode",
                    "Authentication failed",
                )
                return None
            return user

        token_data = decode_access_token(token)
        if token_data is None or token_data.user_id is None:
            await _ws_auth_fail(
                websocket,
                on_failure,
                "Invalid token - could not decode",
                "Invalid token",
                token_hint,
            )
            return None

        user = await UserService.get_by_id(db, token_data.user_id)
        if user is None or not user.is_active:
            await _ws_auth_fail(
                websocket,
                on_failure,
                "User not found or inactive",
                "Invalid user",
                token_hint,
            )
            return None

        return user


async def _ws_auth_fail(
    websocket: WebSocket,
    on_failure: Optional[Callable[[str, str], Awaitable[None]]],
    reason_detail: str,
    close_reason: str,
    token_hint: str = "",
) -> None:
    """Journalise un échec d'auth WebSocket, appelle le callback d'audit puis ferme (1008)."""
    logger.warning(
        "WebSocket first-message authentication failed: %s",
        reason_detail,
        extra={"path": websocket.url.path, "token_hint": token_hint},
    )
    if on_failure is not None:
        try:
            await on_failure(reason_detail, token_hint)
        except Exception:
            logger.exception("on_failure callback error during WS auth failure")
    try:
        await websocket.close(code=1008, reason=close_reason)
    except Exception:
        # Connexion déjà fermée côté client : rien à faire
        pass
