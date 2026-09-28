"""
Routes d'authentification JWT.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import get_current_active_user
from ...auth.jwt import create_access_token, create_token_pair
from ...config import settings
from ...core.bruteforce_protection import bruteforce_protector
from ...core.exceptions import InvalidRefreshTokenError, NotFoundError
from ...core.rate_limit import conditional_rate_limiter
from ...database import get_db
from ...models.user import User
from ...schemas.api_key import APIKeyCreate, APIKeyCreated, APIKeyResponse
from ...schemas.user import (
    LoginResponse,
    RefreshResponse,
    RefreshTokenRequest,
    UserCreate,
    UserResponse,
)
from ...services.api_key_service import ApiKeyService
from ...services.audit_service import AuditService
from ...services.refresh_token_service import RefreshTokenService
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
- **Access Token**: Short-lived JWT for API requests (default: 15 minutes)
- **Refresh Token**: **Opaque** server-side token (default: 7 days, `REFRESH_TOKEN_EXPIRE_DAYS`) — only its hash is stored in `refresh_tokens` (revocable, STORY-123)

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
            "description": (
                "Authentication successful — enveloppe spec 09"
            ),
            "content": {
                "application/json": {
                    "example": {
                        "data": {
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
                        },
                        "message": None,
                    }
                }
            },
        },
        401: {
            "description": "Invalid credentials",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INVALID_CREDENTIALS",
                            "message": "Incorrect username or password",
                        }
                    }
                }
            },
        },
        403: {
            "description": "Account inactive",
            "content": {
                "application/json": {
                    "example": {
                        "error": {"code": "PERMISSION_DENIED", "message": "Inactive user"}
                    }
                }
            },
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
                                "error": {
                                    "code": "TOO_MANY_ATTEMPTS",
                                    "message": (
                                        "Too Many Requests. Maximum 5 login attempts "
                                        "per minute."
                                    ),
                                }
                            },
                        },
                        "too_many_attempts": {
                            "summary": "Brute-force lockout (per-username counter)",
                            "value": {
                                "error": {
                                    "code": "TOO_MANY_ATTEMPTS",
                                    "message": (
                                        "TOO_MANY_ATTEMPTS: too many failed login "
                                        "attempts, try again later"
                                    ),
                                }
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
                    "example": {
                        "error": {
                            "code": "INTERNAL_ERROR",
                            "message": "An unexpected error occurred",
                        }
                    }
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
            # STORY-125.2 : audit de l'échec de credentials (catalogue spec 15).
            # Volontairement audité dans le chemin d'erreur 401 — user_id=None
            # si user inconnu ; ``username`` autorisé dans details (identifiant
            # public déjà loggé), jamais le password (rules 40).
            await AuditService.log_from_request(
                request,
                "user.login_failed",
                user=user,
                resource_type="user",
                resource_id=str(user.id) if user is not None else None,
                details={
                    "username": form_data.username,
                    "reason": "invalid_credentials",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            # NON compté : le mot de passe était correct, ce n'est pas un signal
            # de force brute (décision documentée STORY-104)
            # STORY-125.2 : 2e refus audité (user inactif, password correct).
            await AuditService.log_from_request(
                request,
                "user.login_failed",
                user=user,
                resource_type="user",
                resource_id=str(user.id),
                details={"username": form_data.username, "reason": "inactive_user"},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
            )

        # Login réussi : réinitialisation du compteur d'échecs du username
        await bruteforce_protector.reset(key)
        logger.info("user.login username=%s ip=%s", form_data.username, client_ip)
        # STORY-125.2 : audit du login réussi (après reset brute-force —
        # l'action métier est validée, l'audit ne doit pas la précéder).
        await AuditService.log_from_request(
            request,
            "user.login",
            user=user,
            resource_type="user",
            resource_id=str(user.id),
            details={"username": user.username},
        )

    # Créer la paire de tokens JWT — STORY-121.3 : le claim
    # organization_id n'est plus émis (multi-appartenance incompatible,
    # l'organisation est résolue en base à chaque requête)
    token_data = {
        "sub": user.id,
        "username": user.username,
        "is_superuser": user.is_superuser,
    }

    access_token, refresh_token = create_token_pair(token_data)

    # STORY-123.3 : persister le hash du refresh opaque émis (sans cette
    # ligne le token serait inutilisable au prochain /auth/refresh) — bloc
    # commun aux deux branches : couvre le login par credentials ET
    # l'auto-login du mode dev ``disable_auth`` (arbitrage n°3). Le service
    # ne logge que des identifiants, jamais la valeur claire (rules 40).
    await RefreshTokenService.create(session, user.id, refresh_token)

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
Refresh an access token using a valid **opaque** refresh token.

## Process
1. Resolves the submitted token by hash lookup in `refresh_tokens` (STORY-123)
2. Rejects unknown, expired, already-consumed or revoked tokens (401)
3. Verifies the user still exists and is active
4. **Rotates** the refresh token (single use) and issues a new access JWT
5. Returns the new token pair

## Token Rotation (single use)
- Each refresh **consumes** the current token and emits a **new opaque one**
- Replaying a consumed token returns 401 **and revokes the whole token
  family** of the user (reuse detection — stolen token defense)
- Logout revokes all refresh tokens of the user server-side

## Security Features
- Opaque tokens: no readable claims, hash-only storage (Argon2)
- Generic 401 `INVALID_OR_EXPIRED_TOKEN` (no token existence oracle)
- Request body validated (non-empty, max 512 chars) before hashing
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
                            "description": "Refresh access token with valid opaque refresh token",
                            "value": {
                                "refresh_token": "wf_rt_<86-chars-base64url-opaque-token>"
                            },
                        },
                        "before_expiration": {
                            "summary": "Proactive refresh",
                            "description": "Refresh before access token expires",
                            "value": {
                                "refresh_token": "wf_rt_<86-chars-base64url-opaque-token>"
                            },
                        },
                        "after_expiration": {
                            "summary": "After access token expired",
                            "description": "Refresh after access token has expired",
                            "value": {
                                "refresh_token": "wf_rt_<86-chars-base64url-opaque-token>"
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
                        "invalid_or_expired": {
                            "summary": "Unknown, expired, consumed or revoked token",
                            "value": {"detail": "INVALID_OR_EXPIRED_TOKEN"},
                        },
                        "reuse_detected": {
                            "summary": "Replayed consumed token (family revoked)",
                            "value": {"detail": "INVALID_OR_EXPIRED_TOKEN"},
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
    """Refresh access token by rotating a valid opaque refresh token."""
    # STORY-123.3 : rotation via lookup par hash (service 123.2) — usage
    # unique, nouveau token émis dans la même transaction. Refus 401
    # générique sur inconnu/expiré/consommé/révoqué : la révocation
    # défensive de la famille est déjà appliquée par le service, et le
    # message ne révèle pas si le token a existé (spec 09).
    try:
        new_row, new_refresh_token = await RefreshTokenService.rotate(
            session, refresh_request.refresh_token
        )
    except InvalidRefreshTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_OR_EXPIRED_TOKEN",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    # Utilisateur actif — cohérence conservée avec les vérifications
    # actuelles (AC 2). Défense : le token fraîchement émis est révoqué
    # pour ne pas laisser de ligne active à un compte désactivé.
    user = await UserService.get_by_id(session, new_row.user_id)
    if not user or not user.is_active:
        await RefreshTokenService.revoke_all_for_user(session, new_row.user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="INVALID_OR_EXPIRED_TOKEN",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Access JWT seul — le refresh neuf vient de la rotation (claims
    # réduits STORY-121.3 : sans organization_id)
    new_token_data = {
        "sub": user.id,
        "username": user.username,
        "is_superuser": user.is_superuser,
    }

    new_access_token = create_access_token(new_token_data)

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
Logout the current user and revoke their refresh tokens.

## Process
1. Validates the user's access token
2. **Revokes all refresh tokens** of the user in database (server-side)
3. Returns success confirmation
4. Client should delete stored tokens

## Revocation Semantics (STORY-123)
- Logout is **stateful**: every refresh token of the user is revoked —
  any subsequent `/auth/refresh` with a former token returns 401
- Idempotent: calling logout twice still returns 200

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
                        "detail": "All refresh tokens revoked server-side",
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
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """User logout — server-side revocation of all refresh tokens."""
    # STORY-123.3 (arbitrage n°2, Option A) : logout révocant global — le
    # frontend appelle /logout sans body, on révoque donc tous les refresh
    # tokens de l'utilisateur authentifié (« déconnexion de partout »).
    # Ne révoque JAMAIS sur la base d'un id fourni par le client
    # (current_user résolu par la dépendance d'auth). Idempotent : un
    # second logout révoque 0 token → 200.
    revoked_count = await RefreshTokenService.revoke_all_for_user(
        session, current_user.id
    )
    # Audit léger : user_id + volume seulement — jamais de token (rules 40)
    logger.info(
        "user.logout user_id=%s refresh_tokens_revoked=%d",
        current_user.id,
        revoked_count,
    )
    # STORY-125.2 : audit du logout (après révocation effective).
    await AuditService.log_from_request(
        request,
        "user.logout",
        user=current_user,
        resource_type="user",
        resource_id=str(current_user.id),
        details={"refresh_tokens_revoked": revoked_count},
    )
    return {
        "message": "Successfully logged out",
        "detail": "All refresh tokens revoked server-side",
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

    # STORY-123.3 : persister le hash du refresh opaque émis (auto-login
    # du register) — même obligation que /login ; le service ne logge
    # que des identifiants, jamais la valeur claire (rules 40).
    await RefreshTokenService.create(session, user.id, refresh_token)

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


@router.post(
    "/api-keys",
    response_model=APIKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create an API key",
    description="""
Create a new API key (`wf_ak_...`) for the authenticated user.

## ⚠️ One-Time Display
The response contains the **complete raw key** in the `key` field — this is
the **only** time it is ever returned by the API:
- Only its Argon2 hash is stored server-side (never the value)
- `GET /auth/api-keys` will never return it again
- Once lost, the key must be revoked and a new one created

Copy and store it securely (vault, secret manager) immediately.

## Process
1. Validates the request body (label 1-100 chars, optional `expires_at`)
2. Generates a random key `wf_ak_` + 48 base64url chars (~288 bits entropy)
3. Persists **only** its deterministic Argon2 hash in `api_keys`
4. Returns the key metadata **and the raw key** (201)

## Key Properties
- Prefix: `wf_ak_` (usable via `X-API-Key` header or `Authorization: Bearer`)
- Permissions: the key carries its **owner's RBAC roles** (spec 08 applies
  identically)
- Expiration: optional — `expires_at: null` means the key never expires
- Revocation: immediate via `DELETE /auth/api-keys/{id}`

## Security Features
- Rate limited (10 creations per minute)
- Owner-scoped: the key belongs to the authenticated user
- Audit: `api_key.created` event with `user_id` + `key_id` only

**Authentication Required** - Bearer JWT (API keys cannot create keys)
""",
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
    responses={
        201: {
            "description": (
                "API key created — the raw `key` is returned ONE TIME ONLY, "
                "copy it now"
            ),
            "content": {
                "application/json": {
                    "example": {
                        "id": "9d2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
                        "name": "CLI laptop",
                        "expires_at": "2027-01-01T00:00:00Z",
                        "last_used_at": None,
                        "revoked": False,
                        "created_at": "2026-09-15T10:00:00Z",
                        "key": "wf_ak_8kL2mNpQ4rStUvWxYz0a1B3c5D7f9h1j3k5l7n9pR2t4v",
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
        422: {
            "description": "Invalid body (name empty or > 100 chars, invalid expires_at)",
            "content": {
                "application/json": {
                    "example": {"detail": "Name must be 1-100 characters long"}
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Too Many Requests. Maximum 10 requests per minute."
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
async def create_api_key(
    request: Request,
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """Create an API key — the raw key is returned ONE TIME ONLY (201)."""
    # STORY-124.3 : affichage unique — la valeur claire ne transite qu'ici
    # (schemas 124.2 : APIKeyCreated). Aucun log d'endpoint : les events
    # ``api_key.*`` du service suffisent (user_id + key_id uniquement).
    created = await ApiKeyService.create(session, current_user.id, key_data)
    # STORY-125.2 : audit de la création (après succès) — key_id seulement,
    # jamais la valeur brute ni son hash (rules 40).
    await AuditService.log_from_request(
        request,
        "api_key.created",
        user=current_user,
        resource_type="api_key",
        resource_id=str(created.id),
        details={"name": created.name},
    )
    return created


@router.get(
    "/api-keys",
    response_model=list[APIKeyResponse],
    status_code=status.HTTP_200_OK,
    summary="List my API keys",
    description="""
List the API keys of the authenticated user.

## Response Content
Metadata only — **never** the key value nor its hash:
- `id`, `name`: identification
- `expires_at`: expiration date (`null` = never expires)
- `last_used_at`: last successful use (throttled update, max 1 write/min)
- `revoked`: revocation status (**distinct** from expiration)
- `created_at`: creation timestamp

## Expired Keys
Expired keys **remain listed** with their `expires_at` visible (arbitrage
STORY-124.3): expiration and revocation are separate concepts. An expired
key simply stops authenticating (401).

## Ordering
Most recent first (`created_at` descending).

## Security Features
- Owner-scoped: only the authenticated user's keys are returned
- No secrets in response (`key_hash` and `key` are never serialized)

**Authentication Required** - Bearer JWT or API key
""",
    responses={
        200: {
            "description": "List of API keys (metadata only, no secrets)",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "9d2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
                            "name": "CLI laptop",
                            "expires_at": "2027-01-01T00:00:00Z",
                            "last_used_at": "2026-09-15T14:22:05Z",
                            "revoked": False,
                            "created_at": "2026-09-15T10:00:00Z",
                        },
                        {
                            "id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
                            "name": "Old CI key",
                            "expires_at": "2026-01-01T00:00:00Z",
                            "last_used_at": "2025-12-30T08:15:00Z",
                            "revoked": False,
                            "created_at": "2025-06-01T09:00:00Z",
                        },
                    ]
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
async def list_api_keys(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """List the authenticated user's API keys (metadata only, no secrets)."""
    # STORY-124.3 : clés expirées conservées (arbitrage) — revoked distinct
    # de l'expiration ; jamais key_hash ni key (schema APIKeyResponse).
    return await ApiKeyService.list_for_user(session, current_user.id)


@router.delete(
    "/api-keys/{key_id}",
    response_model=APIKeyResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke an API key",
    description="""
Revoke one of the authenticated user's API keys — **effective immediately**:
any subsequent request using this key returns `401` (the key is verified
against the database on every request, no long-lived cache).

## Semantics
- **Scoped**: only the owner's keys can be revoked — a key belonging to
  another user is treated as non-existent (404, no existence oracle)
- **Idempotent**: revoking an already-revoked key returns its current
  state (200)
- **Irreversible**: a revoked key can never authenticate again; create a
  new one if needed

## Process
1. Resolves the key by `key_id` **scoped to the current user**
2. Sets `revoked = true` (no-op if already revoked)
3. Emits `api_key.revoked` audit event (`user_id` + `key_id` only)
4. Returns the key metadata in its final state

**Authentication Required** - Bearer JWT or API key
""",
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
    responses={
        200: {
            "description": "Key revoked (or already revoked — idempotent)",
            "content": {
                "application/json": {
                    "example": {
                        "id": "9d2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
                        "name": "CLI laptop",
                        "expires_at": "2027-01-01T00:00:00Z",
                        "last_used_at": "2026-09-15T14:22:05Z",
                        "revoked": True,
                        "created_at": "2026-09-15T10:00:00Z",
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
        404: {
            "description": "Key not found (unknown or owned by another user)",
            "content": {
                "application/json": {"example": {"detail": "API key not found"}}
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Too Many Requests. Maximum 10 requests per minute."
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
async def revoke_api_key(
    request: Request,
    key_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """Revoke an API key (owner-scoped, idempotent, immediate effect)."""
    # STORY-124.3 : NotFoundError du service (clé inexistante OU étrangère,
    # sans distinction) → 404 — l'isolation est garantie par le scoping
    # ``user_id == current_user.id`` posé par 124.2.
    try:
        revoked = await ApiKeyService.revoke(session, current_user.id, key_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        ) from None
    # STORY-125.2 : audit de la révocation (après succès, idempotent — la
    # ligne est émise même sur re-révocation, reflétant l'action HTTP).
    await AuditService.log_from_request(
        request,
        "api_key.revoked",
        user=current_user,
        resource_type="api_key",
        resource_id=key_id,
    )
    return revoked
