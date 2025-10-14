"""
Gestion des tokens JWT pour authentification.

Création et validation des tokens d'accès avec python-jose.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt

from ..config import settings
from ..schemas.user import TokenData


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Crée un token JWT d'accès.

    Args:
        data: Données à encoder dans le token
        expires_delta: Durée de validité optionnelle

    Returns:
        Token JWT encodé
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode.update({"exp": expire, "type": "access"})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Crée un token JWT de rafraîchissement.

    Args:
        data: Données à encoder dans le token

    Returns:
        Token JWT de rafraîchissement encodé
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)

    to_encode.update({"exp": expire, "type": "refresh"})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    return encoded_jwt


def create_token_pair(data: dict) -> tuple[str, str]:
    """
    Crée une paire de tokens (access + refresh).

    Args:
        data: Données à encoder dans les tokens

    Returns:
        Tuple (access_token, refresh_token)
    """
    access_token = create_access_token(data)
    refresh_token = create_refresh_token(data)

    return access_token, refresh_token


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Décode et valide un token JWT d'accès.

    Args:
        token: Token JWT à décoder

    Returns:
        TokenData si valide, None sinon
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        # Vérifier que c'est bien un token d'accès
        if payload.get("type") != "access":
            return None

        user_id: str = payload.get("sub")
        username: str = payload.get("username")
        organization_id: str = payload.get("organization_id")
        is_superuser: bool = payload.get("is_superuser", False)

        if user_id is None:
            return None

        token_data = TokenData(
            user_id=user_id,
            username=username,
            organization_id=organization_id,
            is_superuser=is_superuser
        )

        return token_data

    except JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[TokenData]:
    """
    Décode et valide un token JWT de rafraîchissement.

    Args:
        token: Token JWT de rafraîchissement à décoder

    Returns:
        TokenData si valide, None sinon
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        # Vérifier que c'est bien un token de refresh
        if payload.get("type") != "refresh":
            return None

        user_id: str = payload.get("sub")
        username: str = payload.get("username")
        organization_id: str = payload.get("organization_id")
        is_superuser: bool = payload.get("is_superuser", False)

        if user_id is None:
            return None

        token_data = TokenData(
            user_id=user_id,
            username=username,
            organization_id=organization_id,
            is_superuser=is_superuser
        )

        return token_data

    except JWTError:
        return None


def get_token_expiration(token: str) -> Optional[datetime]:
    """
    Récupère la date d'expiration d'un token JWT.

    Args:
        token: Token JWT

    Returns:
        Date d'expiration ou None si invalide
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False}
        )
        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            return datetime.fromtimestamp(exp_timestamp, timezone.utc)
        return None
    except JWTError:
        return None
