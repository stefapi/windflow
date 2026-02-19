"""
Schemas Pydantic V2 pour l'entité User.

Validation stricte avec type hints obligatoires selon backend.md.
Chaque modèle inclut model_config avec exemples et json_schema_extra
pour une documentation OpenAPI complète.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    """Schema de base pour User."""

    email: EmailStr = Field(
        ...,
        description="Email de l'utilisateur",
        json_schema_extra={"example": "user@example.com"}
    )
    username: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Nom d'utilisateur unique",
        json_schema_extra={"example": "johndoe"}
    )
    full_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Nom complet",
        json_schema_extra={"example": "John Doe"}
    )


class UserCreate(UserBase):
    """
    Schema pour création d'utilisateur.

    **Règles de validation:**
    - email: Format email valide, unique dans le système
    - username: 3-100 caractères, unique
    - password: 8-100 caractères minimum
    - organization_id: Optionnel, utilise l'organisation du créateur par défaut
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "john.doe@company.com",
                    "username": "johndoe",
                    "full_name": "John Doe",
                    "password": "SecureP@ss123",
                    "organization_id": "org-001"
                },
                {
                    "email": "admin@windflow.io",
                    "username": "admin",
                    "full_name": "System Administrator",
                    "password": "Admin$ecure456",
                    "is_superuser": True
                },
                {
                    "email": "minimal@example.com",
                    "username": "minuser",
                    "password": "password123"
                }
            ]
        }
    )

    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Mot de passe",
        json_schema_extra={"example": "SecureP@ss123"}
    )
    organization_id: Optional[str] = Field(
        None,
        description="ID de l'organisation (optionnel, utilise l'organisation du créateur par défaut)",
        json_schema_extra={"example": "org-001"}
    )
    is_superuser: bool = Field(
        default=False,
        description="Superutilisateur",
        json_schema_extra={"example": False}
    )


class UserUpdate(BaseModel):
    """
    Schema pour mise à jour d'utilisateur.

    Tous les champs sont optionnels. Seuls les champs fournis
    seront mis à jour.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "full_name": "John D. Updated",
                    "email": "john.updated@company.com"
                },
                {
                    "password": "NewSecureP@ss456",
                    "is_active": True
                },
                {
                    "is_superuser": True,
                    "is_active": True
                }
            ]
        }
    )

    email: Optional[EmailStr] = Field(
        None,
        description="Nouvel email",
        json_schema_extra={"example": "new.email@company.com"}
    )
    username: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
        description="Nouveau nom d'utilisateur",
        json_schema_extra={"example": "newusername"}
    )
    full_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Nouveau nom complet",
        json_schema_extra={"example": "John Doe Updated"}
    )
    password: Optional[str] = Field(
        None,
        min_length=8,
        max_length=100,
        description="Nouveau mot de passe",
        json_schema_extra={"example": "NewSecureP@ss456"}
    )
    is_active: Optional[bool] = Field(
        None,
        description="Statut actif",
        json_schema_extra={"example": True}
    )
    is_superuser: Optional[bool] = Field(
        None,
        description="Statut superutilisateur",
        json_schema_extra={"example": False}
    )


class UserResponse(UserBase):
    """
    Schema pour réponse User (sans données sensibles).

    Ne contient jamais le mot de passe ou d'autres données
    sensibles. Inclut les métadonnées du compte.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "user-990e8400",
                "email": "john.doe@company.com",
                "username": "johndoe",
                "full_name": "John Doe",
                "is_active": True,
                "is_superuser": False,
                "organization_id": "org-001",
                "keycloak_id": None,
                "created_at": "2026-01-02T10:00:00Z",
                "updated_at": "2026-01-02T10:00:00Z",
                "last_login": "2026-01-02T22:30:00Z"
            }
        }
    )

    id: str = Field(
        ...,
        description="ID unique de l'utilisateur",
        json_schema_extra={"example": "user-990e8400"}
    )
    is_active: bool = Field(
        ...,
        description="Utilisateur actif",
        json_schema_extra={"example": True}
    )
    is_superuser: bool = Field(
        ...,
        description="Superutilisateur",
        json_schema_extra={"example": False}
    )
    organization_id: str = Field(
        ...,
        description="ID de l'organisation",
        json_schema_extra={"example": "org-001"}
    )
    keycloak_id: Optional[str] = Field(
        None,
        description="ID Keycloak SSO",
        json_schema_extra={"example": None}
    )
    created_at: datetime = Field(
        ...,
        description="Date de création",
        json_schema_extra={"example": "2026-01-02T10:00:00Z"}
    )
    updated_at: datetime = Field(
        ...,
        description="Date de mise à jour",
        json_schema_extra={"example": "2026-01-02T10:00:00Z"}
    )
    last_login: Optional[datetime] = Field(
        None,
        description="Dernière connexion",
        json_schema_extra={"example": "2026-01-02T22:30:00Z"}
    )


class UserLogin(BaseModel):
    """
    Schema pour authentification utilisateur.

    Accepte le nom d'utilisateur ou l'email pour la connexion.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "username": "johndoe",
                    "password": "SecureP@ss123"
                },
                {
                    "username": "john.doe@company.com",
                    "password": "SecureP@ss123"
                }
            ]
        }
    )

    username: str = Field(
        ...,
        description="Nom d'utilisateur ou email",
        json_schema_extra={"example": "johndoe"}
    )
    password: str = Field(
        ...,
        description="Mot de passe",
        json_schema_extra={"example": "SecureP@ss123"}
    )


class Token(BaseModel):
    """Schema pour token JWT."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600
            }
        }
    )

    access_token: str = Field(
        ...,
        description="Token d'accès JWT",
        json_schema_extra={"example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
    )
    token_type: str = Field(
        default="bearer",
        description="Type de token",
        json_schema_extra={"example": "bearer"}
    )
    expires_in: int = Field(
        ...,
        description="Durée de validité en secondes",
        json_schema_extra={"example": 3600}
    )


class RefreshTokenRequest(BaseModel):
    """Schema pour demande de refresh token."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh..."
            }
        }
    )

    refresh_token: str = Field(
        ...,
        description="Token de rafraîchissement",
        json_schema_extra={"example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh..."}
    )


class LoginResponse(BaseModel):
    """
    Schema pour réponse de login avec user data.

    Retourné après une authentification réussie. Contient
    les tokens d'accès et de rafraîchissement ainsi que
    les données de l'utilisateur connecté.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh...",
                "token_type": "bearer",
                "expires_in": 3600,
                "user": {
                    "id": "user-990e8400",
                    "email": "john.doe@company.com",
                    "username": "johndoe",
                    "full_name": "John Doe",
                    "is_active": True,
                    "is_superuser": False,
                    "organization_id": "org-001"
                }
            }
        }
    )

    access_token: str = Field(
        ...,
        description="Token d'accès JWT",
        json_schema_extra={"example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
    )
    refresh_token: str = Field(
        ...,
        description="Token de rafraîchissement",
        json_schema_extra={"example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh..."}
    )
    token_type: str = Field(
        default="bearer",
        description="Type de token",
        json_schema_extra={"example": "bearer"}
    )
    expires_in: int = Field(
        ...,
        description="Durée de validité en secondes",
        json_schema_extra={"example": 3600}
    )
    user: UserResponse = Field(
        ...,
        description="Données de l'utilisateur"
    )


class RefreshResponse(BaseModel):
    """
    Schema pour réponse de refresh token.

    Retourné après un rafraîchissement réussi des tokens.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.new...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.newrefresh...",
                "token_type": "bearer",
                "expires_in": 3600
            }
        }
    )

    access_token: str = Field(
        ...,
        description="Nouveau token d'accès JWT",
        json_schema_extra={"example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.new..."}
    )
    refresh_token: str = Field(
        ...,
        description="Nouveau token de rafraîchissement",
        json_schema_extra={"example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.newrefresh..."}
    )
    token_type: str = Field(
        default="bearer",
        description="Type de token",
        json_schema_extra={"example": "bearer"}
    )
    expires_in: int = Field(
        ...,
        description="Durée de validité en secondes",
        json_schema_extra={"example": 3600}
    )


class TokenData(BaseModel):
    """Schema pour données extraites du token JWT."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user-990e8400",
                "username": "johndoe",
                "organization_id": "org-001",
                "is_superuser": False
            }
        }
    )

    user_id: Optional[str] = Field(
        None,
        description="ID de l'utilisateur",
        json_schema_extra={"example": "user-990e8400"}
    )
    username: Optional[str] = Field(
        None,
        description="Nom d'utilisateur",
        json_schema_extra={"example": "johndoe"}
    )
    organization_id: Optional[str] = Field(
        None,
        description="ID de l'organisation",
        json_schema_extra={"example": "org-001"}
    )
    is_superuser: bool = Field(
        default=False,
        description="Superutilisateur",
        json_schema_extra={"example": False}
    )
