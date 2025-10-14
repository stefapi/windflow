"""
Schemas Pydantic V2 pour l'entité User.

Validation stricte avec type hints obligatoires selon backend.md.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    """Schema de base pour User."""

    email: EmailStr = Field(..., description="Email de l'utilisateur")
    username: str = Field(..., min_length=3, max_length=100, description="Nom d'utilisateur unique")
    full_name: Optional[str] = Field(None, max_length=255, description="Nom complet")


class UserCreate(UserBase):
    """Schema pour création d'utilisateur."""

    password: str = Field(..., min_length=8, max_length=100, description="Mot de passe")
    organization_id: str = Field(..., description="ID de l'organisation")
    is_superuser: bool = Field(default=False, description="Superutilisateur")


class UserUpdate(BaseModel):
    """Schema pour mise à jour d'utilisateur."""

    email: Optional[EmailStr] = Field(None, description="Nouvel email")
    username: Optional[str] = Field(None, min_length=3, max_length=100, description="Nouveau nom d'utilisateur")
    full_name: Optional[str] = Field(None, max_length=255, description="Nouveau nom complet")
    password: Optional[str] = Field(None, min_length=8, max_length=100, description="Nouveau mot de passe")
    is_active: Optional[bool] = Field(None, description="Statut actif")
    is_superuser: Optional[bool] = Field(None, description="Statut superutilisateur")


class UserResponse(UserBase):
    """Schema pour réponse User (sans données sensibles)."""

    id: str = Field(..., description="ID unique de l'utilisateur")
    is_active: bool = Field(..., description="Utilisateur actif")
    is_superuser: bool = Field(..., description="Superutilisateur")
    organization_id: str = Field(..., description="ID de l'organisation")
    keycloak_id: Optional[str] = Field(None, description="ID Keycloak SSO")
    created_at: datetime = Field(..., description="Date de création")
    updated_at: datetime = Field(..., description="Date de mise à jour")
    last_login: Optional[datetime] = Field(None, description="Dernière connexion")

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    """Schema pour authentification utilisateur."""

    username: str = Field(..., description="Nom d'utilisateur ou email")
    password: str = Field(..., description="Mot de passe")


class Token(BaseModel):
    """Schema pour token JWT."""

    access_token: str = Field(..., description="Token d'accès JWT")
    token_type: str = Field(default="bearer", description="Type de token")
    expires_in: int = Field(..., description="Durée de validité en secondes")


class RefreshTokenRequest(BaseModel):
    """Schema pour demande de refresh token."""

    refresh_token: str = Field(..., description="Token de rafraîchissement")


class LoginResponse(BaseModel):
    """Schema pour réponse de login avec user data."""

    access_token: str = Field(..., description="Token d'accès JWT")
    refresh_token: str = Field(..., description="Token de rafraîchissement")
    token_type: str = Field(default="bearer", description="Type de token")
    expires_in: int = Field(..., description="Durée de validité en secondes")
    user: UserResponse = Field(..., description="Données de l'utilisateur")


class RefreshResponse(BaseModel):
    """Schema pour réponse de refresh token."""

    access_token: str = Field(..., description="Nouveau token d'accès JWT")
    refresh_token: str = Field(..., description="Nouveau token de rafraîchissement")
    token_type: str = Field(default="bearer", description="Type de token")
    expires_in: int = Field(..., description="Durée de validité en secondes")


class TokenData(BaseModel):
    """Schema pour données extraites du token JWT."""

    user_id: Optional[str] = Field(None, description="ID de l'utilisateur")
    username: Optional[str] = Field(None, description="Nom d'utilisateur")
    organization_id: Optional[str] = Field(None, description="ID de l'organisation")
    is_superuser: bool = Field(default=False, description="Superutilisateur")
