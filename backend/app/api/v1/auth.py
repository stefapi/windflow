"""
Routes d'authentification JWT.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...config import settings
from ...schemas.user import LoginResponse, UserResponse, UserLogin, RefreshTokenRequest, RefreshResponse
from ...services.user_service import UserService
from ...auth.jwt import create_access_token, create_token_pair, decode_refresh_token

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db)
):
    """
    Authentification utilisateur et génération de token JWT.
    """
    # Récupérer l'utilisateur
    user = await UserService.get_by_username(session, form_data.username)
    if not user:
        user = await UserService.get_by_email(session, form_data.username)

    # Vérifier le mot de passe et mettre à jour le hash si nécessaire
    if not user or not await UserService.verify_and_update_user(session, user, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    # Créer la paire de tokens JWT
    token_data = {
        "sub": user.id,
        "username": user.username,
        "organization_id": user.organization_id,
        "is_superuser": user.is_superuser
    }

    access_token, refresh_token = create_token_pair(token_data)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user)
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    refresh_request: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Rafraîchit un token d'accès en utilisant un token de rafraîchissement.

    Args:
        refresh_request: Requête contenant le refresh token

    Returns:
        Nouveaux tokens d'accès et de rafraîchissement
    """
    # Décoder et valider le refresh token
    token_data = decode_refresh_token(refresh_request.refresh_token)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Vérifier que l'utilisateur existe toujours et est actif
    user = await UserService.get_by_id(session, token_data.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Vérifier que les données du token correspondent à l'utilisateur
    if (user.username != token_data.username or
        user.organization_id != token_data.organization_id or
        user.is_superuser != token_data.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token data mismatch",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Créer une nouvelle paire de tokens
    new_token_data = {
        "sub": user.id,
        "username": user.username,
        "organization_id": user.organization_id,
        "is_superuser": user.is_superuser
    }

    new_access_token, new_refresh_token = create_token_pair(new_token_data)

    return RefreshResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )
