"""
Routes d'authentification JWT.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...config import settings
from ...schemas.user import LoginResponse, UserResponse, UserLogin, RefreshTokenRequest, RefreshResponse, UserCreate
from ...services.user_service import UserService
from ...auth.jwt import create_access_token, create_token_pair, decode_refresh_token
from ...auth.dependencies import get_current_active_user
from ...models.user import User

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


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_active_user)
):
    """
    Déconnecte l'utilisateur.

    Note: Pour un système JWT stateless, le logout est géré côté client
    en supprimant le token. Cet endpoint est fourni pour la cohérence API
    et permet d'ajouter une logique de blacklist si nécessaire.

    Args:
        current_user: Utilisateur courant authentifié

    Returns:
        dict: Message de confirmation
    """
    return {
        "message": "Successfully logged out",
        "detail": "Token invalidated on client side"
    }


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Enregistre un nouvel utilisateur.

    Args:
        user_data: Données de l'utilisateur à créer
        session: Session de base de données

    Returns:
        LoginResponse: Token d'accès et informations utilisateur

    Raises:
        HTTPException: Si l'email ou le username existe déjà
    """
    # Vérifier que l'email n'existe pas déjà
    existing_email = await UserService.get_by_email(session, user_data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{user_data.email}' already exists"
        )

    # Vérifier que le username n'existe pas déjà
    existing_username = await UserService.get_by_username(session, user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with username '{user_data.username}' already exists"
        )

    # Créer l'utilisateur
    user = await UserService.create(session, user_data)

    # Créer la paire de tokens JWT pour authentification automatique
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


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """
    Récupère le profil de l'utilisateur courant.

    Args:
        current_user: Utilisateur courant authentifié

    Returns:
        UserResponse: Profil de l'utilisateur
    """
    return current_user
