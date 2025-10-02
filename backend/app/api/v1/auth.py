"""
Routes d'authentification JWT.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas.user import Token, UserLogin
from ...services.user_service import UserService
from ...auth.jwt import create_access_token

router = APIRouter()


@router.post("/login", response_model=Token)
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
    
    if not user or not UserService.verify_password(form_data.password, user.hashed_password):
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
    
    # Créer le token JWT
    access_token = create_access_token(
        data={
            "sub": user.id,
            "username": user.username,
            "organization_id": user.organization_id,
            "is_superuser": user.is_superuser
        }
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=3600
    )
