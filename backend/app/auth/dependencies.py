"""
Dépendances FastAPI pour authentification et autorisation.

Fournit les fonctions de dépendance pour protéger les routes API.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, WebSocket, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.user import User
from ..services.user_service import UserService
from ..config import settings
from .jwt import decode_access_token

# Schéma OAuth2 pour extraction du token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db)
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
                detail="No superadmin user found in database for development mode"
            )
        return user

    # Mode production avec authentification JWT normale
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Décoder le token
    if token == None:
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
    current_user: User = Depends(get_current_user)
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
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def require_superuser(
    current_user: User = Depends(get_current_active_user)
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
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


# Alias pour compatibilité avec les routes admin
get_current_superadmin = require_superuser


async def get_current_user_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Récupère l'utilisateur courant à partir du token JWT pour WebSocket.

    En mode développement (DISABLE_AUTH=true), retourne automatiquement
    le premier utilisateur superadmin trouvé en base de données.

    L'authentification WebSocket se fait via query parameter:
    ws://host/path?token=JWT_TOKEN

    Args:
        websocket: Connexion WebSocket
        token: Token JWT extrait du query parameter
        session: Session de base de données

    Returns:
        Utilisateur authentifié ou None si pas de token

    Note:
        Cette fonction retourne None si pas de token (pour compatibilité
        avec le code existant qui accepte les connexions non authentifiées).
        Pour forcer l'authentification, vérifier le retour dans l'endpoint.
    """
    # Mode développement sans authentification
    if settings.disable_auth:
        user = await UserService.get_first_superadmin(session)
        return user  # Peut être None si pas de superadmin en base

    # Mode production avec authentification JWT
    if not token:
        # Pas de token fourni - connexion non authentifiée
        return None

    try:
        # Décoder le token
        token_data = decode_access_token(token)
        if token_data is None or token_data.user_id is None:
            return None

        # Récupérer l'utilisateur
        user = await UserService.get_by_id(session, token_data.user_id)
        if user is None or not user.is_active:
            return None

        return user

    except Exception:
        # En cas d'erreur, retourner None
        # L'endpoint WebSocket décidera comment gérer
        return None
