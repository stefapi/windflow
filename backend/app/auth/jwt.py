"""
Gestion des tokens JWT pour authentification.

Création et validation des tokens d'accès avec python-jose.
"""

from datetime import datetime, timedelta
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
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Décode et valide un token JWT.

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
