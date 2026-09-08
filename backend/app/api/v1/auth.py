"""
Routes d'authentification JWT.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import get_current_active_user
from ...auth.jwt import create_token_pair, decode_refresh_token
from ...config import settings
from ...core.bruteforce_protection import bruteforce_protector
from ...core.rate_limit import conditional_rate_limiter
from ...database import get_db
from ...models.user import User
from ...schemas.user import (
    LoginResponse,
    RefreshResponse,
    RefreshTokenRequest,
    UserCreate,
    UserResponse,
)
from ...services.user_organization_service import UserOrganizationService
from ...services.user_service import UserService

logger = logging.getLogger("windflow.auth")

router = APIRouter()


async def _user_response(session, user: User) -> UserResponse:
    """
    Construit la réponse utilisateur avec l'organisation primaire résolue.

    STORY-121.3 : la colonne ``users.organization_id`` n'existe plus —
    ``UserResponse.organization_id`` (contrat API conservé) est peuplé
    depuis l'association (première appartenance par ``joined_at``).
    Helper partagé, réutilisé par ``users.py``.

    Args:
        session: Session de base de données async
        user: Utilisateur à sérialiser

    Returns:
        UserResponse: Réponse avec ``organization_id`` = org primaire
    """
    resp = UserResponse.model_validate(user)
    resp.organization_id = await UserOrganizationService.get_primary_organization_id(
        session, user
    )
    return resp


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="User authentication",
    description="""
Authenticate a user and generate JWT tokens.

## Process
1. Validates user credentials (username/email + password)
2. Checks if user account is active
3. Generates access token and refresh token pair
4. Returns tokens with user profile information

## Authentication Methods
- **Username**: Login with username and password
- **Email**: Login with email and password

## Token Types
- **Access Token**: Short-lived token for API requests (default: 30 minutes)
- **Refresh Token**: Long-lived token to obtain new access tokens (default: 7 days)

## Security Features
- Password hashing with bcrypt
- Automatic password hash upgrade if needed
- Account status verification
- Rate limiting to prevent brute force attacks
- Progressive account lockout after repeated failures (5 attempts / 10 min, 5 min lockout)

**No Authentication Required** - This is the login endpoint
""",
    dependencies=[Depends(conditional_rate_limiter(5, 60))],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/x-www-form-urlencoded": {
                    "examples": {
                        "username_login": {
                            "summary": "Login with username",
                            "description": "Standard username and password authentication",
                            "value": {
                                "username": "admin",
                                "password": "SecurePassword123!",
                            },
                        },
                        "email_login": {
                            "summary": "Login with email",
                            "description": "Use email instead of username",
                            "value": {
                                "username": "user@windflow.io",
                                "password": "MyPassword456!",
                            },
                        },
                        "simple_login": {
                            "summary": "Simple login",
                            "description": "Basic authentication example",
                            "value": {
                                "username": "john_doe",
                                "password": "password123",
                            },
                        },
                    }
                }
            }
        }
    },
    responses={
        200: {
            "description": "Authentication successful",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer",
                        "expires_in": 1800,
                        "user": {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "username": "admin",
                            "email": "admin@windflow.io",
                            "full_name": "Administrator",
                            "is_active": True,
                            "is_superuser": True,
                            "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                        },
                    }
                }
            },
        },
        401: {
            "description": "Invalid credentials",
            "content": {
                "application/json": {
                    "example": {"detail": "Incorrect username or password"}
                }
            },
        },
        403: {
            "description": "Account inactive",
            "content": {"application/json": {"example": {"detail": "Inactive user"}}},
        },
        429: {
            "description": (
                "Too many requests — either the per-IP rate limit (5/min) or the "
                "brute-force lockout (`TOO_MANY_ATTEMPTS`, `Retry-After` header "
                "indicating the remaining lockout duration in seconds)"
            ),
            "headers": {
                "Retry-After": {
                    "description": "Seconds to wait before retrying",
                    "schema": {"type": "integer"},
                }
            },
            "content": {
                "application/json": {
                    "examples": {
                        "rate_limited": {
                            "summary": "Per-IP rate limit exceeded",
                            "value": {
                                "detail": "Too Many Requests. Maximum 5 login attempts per minute."
                            },
                        },
                        "too_many_attempts": {
                            "summary": "Brute-force lockout (per-username counter)",
                            "value": {
                                "detail": "TOO_MANY_ATTEMPTS: too many failed login attempts, try again later"
                            },
                        },
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "An unexpected error occurred"}
                }
            },
        },
    },
    tags=["authentication"],
)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
):
    """User authentication and JWT token generation."""
    # Mode développement : auto-login avec credentials vides — hors comptage
    # brute-force (aucun username fourni, AC 4)
    if settings.disable_auth and not form_data.username and not form_data.password:
        user = await UserService.get_first_superadmin(session)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No superadmin user found in database for development mode",
            )
    else:
        client_ip = request.client.host if request.client else "unknown"

        # Protection brute-force (STORY-104) : rejet précoce si le username est
        # bloqué — AVANT tout lookup DB (compteur par username, pas par IP seule)
        key = form_data.username.strip().lower()
        locked, retry_after = await bruteforce_protector.is_locked_out(key)
        if locked:
            logger.warning(
                "user.login_failed username=%s ip=%s reason=locked_out",
                form_data.username,
                client_ip,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="TOO_MANY_ATTEMPTS: too many failed login attempts, try again later",
                headers={"Retry-After": str(retry_after)},
            )

        # Récupérer l'utilisateur
        user = await UserService.get_by_username(session, form_data.username)
        if not user:
            user = await UserService.get_by_email(session, form_data.username)

        # Vérifier le mot de passe et mettre à jour le hash si nécessaire
        if not user or not await UserService.verify_and_update_user(
            session, user, form_data.password
        ):
            # Échec de credentials : compté dans le compteur brute-force —
            # aussi si l'utilisateur n'existe pas (anti-énumération : le 429 ne
            # doit pas devenir un oracle d'existence de compte)
            await bruteforce_protector.register_failure(key)
            logger.warning(
                "user.login_failed username=%s ip=%s reason=invalid_credentials",
                form_data.username,
                client_ip,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            # NON compté : le mot de passe était correct, ce n'est pas un signal
            # de force brute (décision documentée STORY-104)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
            )

        # Login réussi : réinitialisation du compteur d'échecs du username
        await bruteforce_protector.reset(key)
        logger.info("user.login username=%s ip=%s", form_data.username, client_ip)

    # Créer la paire de tokens JWT — STORY-121.3 : le claim
    # organization_id n'est plus émis (multi-appartenance incompatible,
    # l'organisation est résolue en base à chaque requête)
    token_data = {
        "sub": user.id,
        "username": user.username,
        "is_superuser": user.is_superuser,
    }

    access_token, refresh_token = create_token_pair(token_data)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=await _user_response(session, user),
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="""
Refresh an access token using a valid refresh token.

## Process
1. Validates the refresh token signature and expiration
2. Verifies the user still exists and is active
3. Checks that user data hasn't changed (username, organization, permissions)
4. Generates a new token pair (access + refresh)
5. Returns new tokens with updated expiration

## Token Rotation
This endpoint implements **token rotation** for enhanced security:
- Each refresh generates a **new refresh token**
- Old refresh tokens become invalid after use
- Prevents token replay attacks

## Use Cases
- **Seamless UX**: Refresh tokens before access token expires
- **Session Extension**: Keep users logged in without re-authentication
- **Security**: Shorter access token lifetime with automatic renewal

## Security Features
- Validates token signature and expiration
- Checks user account status
- Detects token data tampering
- Rate limiting to prevent abuse

**No Authentication Required** - Uses refresh token for authentication
""",
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "standard_refresh": {
                            "summary": "Standard token refresh",
                            "description": "Refresh access token with valid refresh token",
                            "value": {
                                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJ1c2VybmFtZSI6ImFkbWluIiwib3JnYW5pemF0aW9uX2lkIjoiNjYwZTg0MDAtZTI5Yi00MWQ0LWE3MTYtNDQ2NjU1NDQwMDAxIiwiaXNfc3VwZXJ1c2VyIjp0cnVlLCJ0eXBlIjoicmVmcmVzaCIsImV4cCI6MTczNTk0NTIwMH0.signature"
                            },
                        },
                        "before_expiration": {
                            "summary": "Proactive refresh",
                            "description": "Refresh before access token expires",
                            "value": {
                                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                            },
                        },
                        "after_expiration": {
                            "summary": "After access token expired",
                            "description": "Refresh after access token has expired",
                            "value": {
                                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                            },
                        },
                    }
                }
            }
        }
    },
    responses={
        200: {
            "description": "Token refreshed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.new_access_token...",
                        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.new_refresh_token...",
                        "token_type": "bearer",
                        "expires_in": 1800,
                    }
                }
            },
        },
        401: {
            "description": "Invalid or expired refresh token",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_token": {
                            "summary": "Invalid token",
                            "value": {"detail": "Invalid refresh token"},
                        },
                        "user_not_found": {
                            "summary": "User not found",
                            "value": {"detail": "User not found or inactive"},
                        },
                        "token_mismatch": {
                            "summary": "Token data mismatch",
                            "value": {"detail": "Token data mismatch"},
                        },
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Too Many Requests. Maximum 10 refresh attempts per minute."
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "An unexpected error occurred"}
                }
            },
        },
    },
    tags=["authentication"],
)
async def refresh_token(
    request: Request,
    refresh_request: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db),
):
    """Refresh access token using a valid refresh token."""
    # Décoder et valider le refresh token
    token_data = decode_refresh_token(refresh_request.refresh_token)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Vérifier que l'utilisateur existe toujours et est actif
    user = await UserService.get_by_id(session, token_data.user_id)  # type: ignore[arg-type]
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Vérifier que les données du token correspondent à l'utilisateur
    # (STORY-121.3 : comparaison sur username + is_superuser uniquement —
    # le claim organization_id n'existe plus, l'appartenance peut évoluer
    # sans invalider le refresh)
    if (
        user.username != token_data.username
        or user.is_superuser != token_data.is_superuser
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token data mismatch",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Créer une nouvelle paire de tokens (claims réduits — STORY-121.3)
    new_token_data = {
        "sub": user.id,
        "username": user.username,
        "is_superuser": user.is_superuser,
    }

    new_access_token, new_refresh_token = create_token_pair(new_token_data)

    return RefreshResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="User logout",
    description="""
Logout the current user and invalidate their session.

## Process
1. Validates the user's access token
2. Returns success confirmation
3. Client should delete stored tokens

## JWT Stateless Architecture
This endpoint follows a **stateless JWT approach**:
- Tokens are **not stored server-side**
- Logout is handled by **client deleting tokens**
- No server-side token blacklist (for simplicity)

## Implementation Notes
- This endpoint is provided for **API consistency**
- Can be extended with token blacklist/revocation if needed
- Useful for logging user activity and audit trails

## Client Responsibilities
After calling this endpoint, the client must:
1. Delete access token from storage
2. Delete refresh token from storage
3. Clear any cached user data
4. Redirect to login page

**Authentication Required** - Bearer token
""",
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    responses={
        200: {
            "description": "Logout successful",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Successfully logged out",
                        "detail": "Token invalidated on client side",
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {"example": {"detail": "Not authenticated"}}
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Too Many Requests. Maximum 20 requests per minute."
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "An unexpected error occurred"}
                }
            },
        },
    },
    tags=["authentication"],
)
async def logout(
    request: Request, current_user: User = Depends(get_current_active_user)
):
    """User logout and session invalidation."""
    return {
        "message": "Successfully logged out",
        "detail": "Token invalidated on client side",
    }


@router.post(
    "/register",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="""
Register a new user account and automatically log them in.

## Process
1. Validates user data (email, username, password)
2. Checks for existing email or username
3. Creates new user account with hashed password
4. Automatically generates JWT tokens
5. Returns tokens and user profile

## Validation Rules
- **Email**: Must be valid email format and unique
- **Username**: 3-50 characters, alphanumeric with underscores, unique
- **Password**: Minimum 8 characters (configurable)
- **Full Name**: Optional, 1-100 characters

## Default Settings
New users are created with:
- `is_active`: true (account enabled)
- `is_superuser`: false (regular user)
- `organization_id`: null (no organization assigned)

## Auto-Login
After successful registration, the user is **automatically logged in**:
- Access token and refresh token are generated
- No need for separate login request
- Seamless onboarding experience

## Security Features
- Password hashing with bcrypt
- Email and username uniqueness validation
- Rate limiting to prevent spam registrations

**No Authentication Required** - This is the registration endpoint
""",
    dependencies=[Depends(conditional_rate_limiter(3, 60))],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "complete_registration": {
                            "summary": "Complete registration",
                            "description": "Register with all fields",
                            "value": {
                                "username": "john_doe",
                                "email": "john.doe@example.com",
                                "password": "SecurePassword123!",
                                "full_name": "John Doe",
                            },
                        },
                        "minimal_registration": {
                            "summary": "Minimal registration",
                            "description": "Register with required fields only",
                            "value": {
                                "username": "jane_smith",
                                "email": "jane.smith@example.com",
                                "password": "MyPassword456!",
                            },
                        },
                        "organization_user": {
                            "summary": "Organization user",
                            "description": "Register user with organization",
                            "value": {
                                "username": "bob_wilson",
                                "email": "bob@company.com",
                                "password": "CompanyPass789!",
                                "full_name": "Bob Wilson",
                                "organization_id": "770e8400-e29b-41d4-a716-446655440002",
                            },
                        },
                    }
                }
            }
        }
    },
    responses={
        201: {
            "description": "User registered successfully",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer",
                        "expires_in": 1800,
                        "user": {
                            "id": "880e8400-e29b-41d4-a716-446655440003",
                            "username": "john_doe",
                            "email": "john.doe@example.com",
                            "full_name": "John Doe",
                            "is_active": True,
                            "is_superuser": False,
                            "organization_id": None,
                        },
                    }
                }
            },
        },
        400: {
            "description": "Invalid request data",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid email format or password too weak"}
                }
            },
        },
        409: {
            "description": "User already exists",
            "content": {
                "application/json": {
                    "examples": {
                        "email_exists": {
                            "summary": "Email already exists",
                            "value": {
                                "detail": "User with email 'john.doe@example.com' already exists"
                            },
                        },
                        "username_exists": {
                            "summary": "Username already exists",
                            "value": {
                                "detail": "User with username 'john_doe' already exists"
                            },
                        },
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Too Many Requests. Maximum 3 registration attempts per minute."
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "An unexpected error occurred"}
                }
            },
        },
    },
    tags=["authentication"],
)
async def register(
    request: Request, user_data: UserCreate, session: AsyncSession = Depends(get_db)
):
    """Register a new user account and automatically log them in."""
    # Vérifier que l'email n'existe pas déjà
    existing_email = await UserService.get_by_email(session, user_data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{user_data.email}' already exists",
        )

    # Vérifier que le username n'existe pas déjà
    existing_username = await UserService.get_by_username(session, user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with username '{user_data.username}' already exists",
        )

    # Sécurité : l'auto-enregistrement ne peut jamais créer un
    # superuser — UserCreate expose le champ pour la création par un
    # admin, il est forcé à False ici (least privilege)
    user_data.is_superuser = False

    # STORY-121.3 : résolution de l'organisation cible avant création —
    # sans organization_id dans le body, l'auto-enregistrement rattache à
    # l'organisation par défaut (409 explicite si elle n'existe pas :
    # corriger la config plutôt que créer un utilisateur orphelin) ;
    # org fournie → doit exister (404). Rôle d'auto-enregistrement :
    # viewer (borné côté UserService.create).
    if not user_data.organization_id:
        from ...services.organization_service import OrganizationService

        default_org = await OrganizationService.get_by_slug(
            session, settings.default_org_slug
        )
        if default_org is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Default organization not found — configure " "DEFAULT_ORG_SLUG"
                ),
            )
        user_data.organization_id = default_org.id
    else:
        from ...services.organization_service import OrganizationService

        target_org = await OrganizationService.get_by_id(
            session, user_data.organization_id
        )
        if target_org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(f"Organisation '{user_data.organization_id}' non trouvée"),
            )

    # Créer l'utilisateur
    user = await UserService.create(session, user_data)

    # Créer la paire de tokens JWT pour authentification automatique —
    # claims réduits (STORY-121.3 : sans organization_id)
    token_data = {
        "sub": user.id,
        "username": user.username,
        "is_superuser": user.is_superuser,
    }

    access_token, refresh_token = create_token_pair(token_data)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=await _user_response(session, user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="""
Get the profile information of the currently authenticated user.

## Process
1. Validates the access token from Authorization header
2. Retrieves user information from token claims
3. Returns complete user profile

## Use Cases
- **Profile Display**: Show user info in UI
- **Permission Checks**: Verify user roles and permissions
- **Session Validation**: Confirm user is still authenticated
- **User Context**: Get organization and settings

## Returned Information
- User ID, username, email
- Full name and profile details
- Account status (active, superuser)
- Organization membership
- Account creation and update timestamps

## Security
- Requires valid access token
- Only returns data for the authenticated user
- Cannot access other users' profiles through this endpoint

**Authentication Required** - Bearer token
""",
    dependencies=[Depends(conditional_rate_limiter(60, 60))],
    responses={
        200: {
            "description": "User profile retrieved successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "regular_user": {
                            "summary": "Regular user profile",
                            "value": {
                                "id": "550e8400-e29b-41d4-a716-446655440000",
                                "username": "john_doe",
                                "email": "john.doe@example.com",
                                "full_name": "John Doe",
                                "is_active": True,
                                "is_superuser": False,
                                "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                                "created_at": "2026-01-15T10:30:00Z",
                                "updated_at": "2026-02-01T14:20:00Z",
                            },
                        },
                        "superuser": {
                            "summary": "Superuser profile",
                            "value": {
                                "id": "770e8400-e29b-41d4-a716-446655440002",
                                "username": "admin",
                                "email": "admin@windflow.io",
                                "full_name": "Administrator",
                                "is_active": True,
                                "is_superuser": True,
                                "organization_id": None,
                                "created_at": "2026-01-01T00:00:00Z",
                                "updated_at": "2026-02-01T12:00:00Z",
                            },
                        },
                    }
                }
            },
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {"example": {"detail": "Not authenticated"}}
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Too Many Requests. Maximum 60 requests per minute."
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "An unexpected error occurred"}
                }
            },
        },
    },
    tags=["authentication"],
)
async def get_current_user_profile(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """Get the profile information of the currently authenticated user."""
    # STORY-121.3 : organization_id = org primaire (association)
    return await _user_response(session, current_user)
