"""
Routes de gestion des utilisateurs.
"""

from typing import List
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas.user import UserResponse, UserCreate, UserUpdate
from ...services.user_service import UserService
from ...auth.dependencies import get_current_active_user, require_superuser
from ...models.user import User
from ...services.organization_service import OrganizationService
from ...core.rate_limit import conditional_rate_limiter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List organization users",
    description="""
List all users within the current user's organization.

## Access Control
- **Regular Users**: Can only see users from their own organization
- **Superusers**: Can see users from their organization (cross-org access requires specific endpoint)

## Pagination
Use `skip` and `limit` parameters for pagination:
- Default: Returns first 100 users
- Maximum limit: 100 users per request

## Use Cases
- Display user directory in admin panel
- User selection for role assignment
- Team member management
- Organization user audit

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
    openapi_extra={
        "parameters": [
            {
                "name": "skip",
                "in": "query",
                "description": "Number of users to skip for pagination",
                "required": False,
                "schema": {
                    "type": "integer",
                    "default": 0,
                    "minimum": 0
                },
                "examples": {
                    "first_page": {
                        "summary": "First page",
                        "value": 0
                    },
                    "second_page": {
                        "summary": "Second page (skip 100)",
                        "value": 100
                    }
                }
            },
            {
                "name": "limit",
                "in": "query",
                "description": "Maximum number of users to return",
                "required": False,
                "schema": {
                    "type": "integer",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 100
                },
                "examples": {
                    "default": {
                        "summary": "Default (100 users)",
                        "value": 100
                    },
                    "small_page": {
                        "summary": "Small page (10 users)",
                        "value": 10
                    }
                }
            }
        ]
    },
    responses={
        200: {
            "description": "List of users retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "username": "admin",
                            "email": "admin@windflow.io",
                            "full_name": "Administrator",
                            "is_active": True,
                            "is_superuser": True,
                            "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                            "created_at": "2026-01-01T10:00:00Z",
                            "updated_at": "2026-01-15T14:30:00Z"
                        },
                        {
                            "id": "770e8400-e29b-41d4-a716-446655440002",
                            "username": "john_doe",
                            "email": "john@windflow.io",
                            "full_name": "John Doe",
                            "is_active": True,
                            "is_superuser": False,
                            "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                            "created_at": "2026-01-10T09:15:00Z",
                            "updated_at": "2026-01-20T11:45:00Z"
                        }
                    ]
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Not authenticated"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds."
                    }
                }
            }
        }
    }
)
async def list_users(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """List all users within the current user's organization."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Listing users for organization",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "organization_id": str(current_user.organization_id),
            "skip": skip,
            "limit": limit
        }
    )

    users = await UserService.list_by_organization(
        session,
        current_user.organization_id,
        skip,
        limit
    )
    return users


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="""
Get the profile of the currently authenticated user.

## Use Cases
- Display user info in UI
- Verify user roles and permissions
- Confirm user is still authenticated

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(60, 60))],
    responses={
        200: {
            "description": "User profile retrieved successfully"
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authenticated"}
                }
            }
        }
    },
    tags=["users"]
)
async def get_current_user_me(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Retourne le profil de l'utilisateur authentifié."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Getting current user profile",
        extra={"correlation_id": correlation_id, "user_id": str(current_user.id)}
    )
    return current_user


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user by ID",
    description="""
Retrieve detailed information about a specific user.

## Access Control
- **Regular Users**: Can only access users from their own organization
- **Superusers**: Can access users from their organization

## Use Cases
- View user profile details
- Check user permissions and roles
- Audit user information
- User management operations

## Security
- Returns 403 if trying to access user from different organization
- Returns 404 if user doesn't exist

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(60, 60))],
    openapi_extra={
        "parameters": [
            {
                "name": "user_id",
                "in": "path",
                "description": "UUID of the user to retrieve",
                "required": True,
                "schema": {
                    "type": "string",
                    "format": "uuid"
                },
                "examples": {
                    "valid_user": {
                        "summary": "Valid user ID",
                        "value": "550e8400-e29b-41d4-a716-446655440000"
                    }
                }
            }
        ]
    },
    responses={
        200: {
            "description": "User retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "username": "john_doe",
                        "email": "john@windflow.io",
                        "full_name": "John Doe",
                        "is_active": True,
                        "is_superuser": False,
                        "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                        "created_at": "2026-01-10T09:15:00Z",
                        "updated_at": "2026-01-20T11:45:00Z"
                    }
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Not authenticated"
                    }
                }
            }
        },
        403: {
            "description": "Access denied - user from different organization",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Accès refusé à cet utilisateur"
                    }
                }
            }
        },
        404: {
            "description": "User not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Utilisateur 550e8400-e29b-41d4-a716-446655440000 non trouvé"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds."
                    }
                }
            }
        }
    }
)
async def get_user(
    request: Request,
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """Retrieve detailed information about a specific user."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting user {user_id}",
        extra={"correlation_id": correlation_id, "target_user_id": str(user_id)}
    )

    user = await UserService.get_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Utilisateur {user_id} non trouvé"
        )

    # Vérifier que l'utilisateur appartient à la même organisation ou est superuser
    if not current_user.is_superuser and user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cet utilisateur"
        )

    return user


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    description="""
Create a new user within an organization.

## Organization Assignment Logic
### Regular Users
- **No organization_id provided**: User created in current user's organization
- **organization_id provided**: Must match current user's organization, otherwise returns 403

### Superusers
- **No organization_id provided**: User created in superuser's organization
- **organization_id provided**: User created in specified organization (must exist)

## Validation
- Email must be unique across all organizations
- Username must be unique within the organization
- Password must meet security requirements

## Use Cases
- Add new team members to organization
- Create service accounts
- Onboard new employees
- Provision user accounts via API

## Security
- Passwords are hashed with bcrypt before storage
- Email uniqueness is enforced
- Organization isolation is maintained

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "basic_user": {
                            "summary": "Basic user creation",
                            "description": "Create a regular user in current organization",
                            "value": {
                                "username": "john_doe",
                                "email": "john.doe@windflow.io",
                                "password": "SecurePassword123!",
                                "full_name": "John Doe",
                                "is_active": True
                            }
                        },
                        "with_organization": {
                            "summary": "User with specific organization (superuser only)",
                            "description": "Superuser creating user in specific organization",
                            "value": {
                                "username": "jane_smith",
                                "email": "jane.smith@company.com",
                                "password": "AnotherSecure456!",
                                "full_name": "Jane Smith",
                                "is_active": True,
                                "organization_id": "660e8400-e29b-41d4-a716-446655440001"
                            }
                        },
                        "admin_user": {
                            "summary": "Create admin user",
                            "description": "Create user with superuser privileges",
                            "value": {
                                "username": "admin_user",
                                "email": "admin@windflow.io",
                                "password": "AdminPass789!",
                                "full_name": "Admin User",
                                "is_active": True,
                                "is_superuser": True
                            }
                        },
                        "inactive_user": {
                            "summary": "Create inactive user",
                            "description": "Create user account that is initially disabled",
                            "value": {
                                "username": "pending_user",
                                "email": "pending@windflow.io",
                                "password": "TempPass123!",
                                "full_name": "Pending User",
                                "is_active": False
                            }
                        }
                    }
                }
            }
        }
    },
    responses={
        201: {
            "description": "User created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "username": "john_doe",
                        "email": "john.doe@windflow.io",
                        "full_name": "John Doe",
                        "is_active": True,
                        "is_superuser": False,
                        "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                        "created_at": "2026-02-02T21:57:00Z",
                        "updated_at": "2026-02-02T21:57:00Z"
                    }
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Not authenticated"
                    }
                }
            }
        },
        403: {
            "description": "Access denied - trying to create user in different organization",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Vous ne pouvez créer un utilisateur que dans votre propre organisation"
                    }
                }
            }
        },
        404: {
            "description": "Organization not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Organisation '660e8400-e29b-41d4-a716-446655440001' non trouvée"
                    }
                }
            }
        },
        409: {
            "description": "Email already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Utilisateur avec l'email 'john.doe@windflow.io' existe déjà"
                    }
                }
            }
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "email"],
                                "msg": "value is not a valid email address",
                                "type": "value_error.email"
                            }
                        ]
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds."
                    }
                }
            }
        }
    }
)
async def create_user(
    request: Request,
    user_data: UserCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """Create a new user within an organization."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Creating user '{user_data.email}'",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "new_user_email": user_data.email
        }
    )
    # Vérifier que l'email n'existe pas déjà
    existing = await UserService.get_by_email(session, user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Utilisateur avec l'email '{user_data.email}' existe déjà"
        )

    # Déterminer l'organisation cible selon les règles métier
    provided_org_id = user_data.organization_id

    if current_user.is_superuser:
        # Superadmin: peut créer dans n'importe quelle organisation
        if provided_org_id:
            # Vérifier que l'organisation cible existe

            org = await OrganizationService.get_by_id(session, provided_org_id)
            if not org:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Organisation '{provided_org_id}' non trouvée"
                )
        else:
            # Aucune organisation spécifiée: utiliser celle du superadmin
            user_data.organization_id = current_user.organization_id
    else:
        # Utilisateur normal: ne peut créer que dans sa propre organisation
        if provided_org_id:
            # Vérifier que c'est bien son organisation
            if provided_org_id != str(current_user.organization_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Vous ne pouvez créer un utilisateur que dans votre propre organisation"
                )
        user_data.organization_id = current_user.organization_id

    user = await UserService.create(session, user_data)
    return user


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user information",
    description="""
Update an existing user's information.

## Access Control
- **Regular Users**: Can only update users from their own organization
- **Superusers**: Can update users from their organization

## Updatable Fields
- Email (must be unique)
- Full name
- Active status
- Superuser status (superuser only)
- Password (if provided)

## Validation
- Email uniqueness is checked if email is being changed
- User must exist and belong to accessible organization
- Cannot update users from different organizations (non-superusers)

## Use Cases
- Update user profile information
- Change user email address
- Enable/disable user accounts
- Reset user passwords
- Modify user permissions

## Security
- Email uniqueness is enforced
- Organization isolation is maintained
- Password changes are hashed

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    openapi_extra={
        "parameters": [
            {
                "name": "user_id",
                "in": "path",
                "description": "UUID of the user to update",
                "required": True,
                "schema": {
                    "type": "string",
                    "format": "uuid"
                },
                "examples": {
                    "valid_user": {
                        "summary": "Valid user ID",
                        "value": "550e8400-e29b-41d4-a716-446655440000"
                    }
                }
            }
        ],
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "update_email": {
                            "summary": "Update email address",
                            "description": "Change user's email address",
                            "value": {
                                "email": "newemail@windflow.io"
                            }
                        },
                        "update_profile": {
                            "summary": "Update profile information",
                            "description": "Update full name and other profile fields",
                            "value": {
                                "full_name": "John Smith",
                                "email": "john.smith@windflow.io"
                            }
                        },
                        "disable_user": {
                            "summary": "Disable user account",
                            "description": "Set user account to inactive",
                            "value": {
                                "is_active": False
                            }
                        },
                        "reset_password": {
                            "summary": "Reset user password",
                            "description": "Change user's password",
                            "value": {
                                "password": "NewSecurePassword123!"
                            }
                        },
                        "promote_to_admin": {
                            "summary": "Promote to superuser",
                            "description": "Grant superuser privileges (superuser only)",
                            "value": {
                                "is_superuser": True
                            }
                        },
                        "full_update": {
                            "summary": "Complete profile update",
                            "description": "Update multiple fields at once",
                            "value": {
                                "email": "updated@windflow.io",
                                "full_name": "Updated Name",
                                "is_active": True,
                                "password": "NewPassword456!"
                            }
                        }
                    }
                }
            }
        }
    },
    responses={
        200: {
            "description": "User updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "username": "john_doe",
                        "email": "newemail@windflow.io",
                        "full_name": "John Smith",
                        "is_active": True,
                        "is_superuser": False,
                        "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                        "created_at": "2026-01-10T09:15:00Z",
                        "updated_at": "2026-02-02T21:57:00Z"
                    }
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Not authenticated"
                    }
                }
            }
        },
        403: {
            "description": "Access denied - user from different organization",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Accès refusé à cet utilisateur"
                    }
                }
            }
        },
        404: {
            "description": "User not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Utilisateur 550e8400-e29b-41d4-a716-446655440000 non trouvé"
                    }
                }
            }
        },
        409: {
            "description": "Email already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Utilisateur avec l'email 'newemail@windflow.io' existe déjà"
                    }
                }
            }
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "email"],
                                "msg": "value is not a valid email address",
                                "type": "value_error.email"
                            }
                        ]
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds."
                    }
                }
            }
        }
    }
)
async def update_user(
    request: Request,
    user_id: UUID,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """Update an existing user's information."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Updating user {user_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "target_user_id": str(user_id)
        }
    )
    # Vérifier que l'utilisateur existe
    existing_user = await UserService.get_by_id(session, user_id)
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Utilisateur {user_id} non trouvé"
        )

    # Vérifier les permissions (même organisation ou superuser)
    if not current_user.is_superuser and existing_user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cet utilisateur"
        )

    # Si changement d'email, vérifier qu'il n'existe pas déjà
    if user_data.email and user_data.email != existing_user.email:
        existing_email = await UserService.get_by_email(session, user_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Utilisateur avec l'email '{user_data.email}' existe déjà"
            )

    user = await UserService.update(session, user_id, user_data)
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user",
    description="""
Permanently delete a user account.

## Access Control
- **Regular Users**: Can only delete users from their own organization
- **Superusers**: Can delete users from their organization

## Safety Features
- **Self-deletion prevention**: Users cannot delete their own account
- **Organization isolation**: Cannot delete users from other organizations
- **Permanent action**: This operation cannot be undone

## Use Cases
- Remove inactive or terminated employees
- Clean up test accounts
- Comply with data deletion requests
- Decommission service accounts

## Important Notes
- All user data and associations will be permanently deleted
- Consider deactivating users instead of deleting them for audit purposes
- Deletion is immediate and cannot be reversed

## Security
- Prevents self-deletion to avoid accidental lockout
- Enforces organization boundaries
- Requires authentication

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
    openapi_extra={
        "parameters": [
            {
                "name": "user_id",
                "in": "path",
                "description": "UUID of the user to delete",
                "required": True,
                "schema": {
                    "type": "string",
                    "format": "uuid"
                },
                "examples": {
                    "valid_user": {
                        "summary": "Valid user ID",
                        "value": "550e8400-e29b-41d4-a716-446655440000"
                    }
                }
            }
        ]
    },
    responses={
        204: {
            "description": "User deleted successfully (no content returned)"
        },
        400: {
            "description": "Bad request - attempting to delete own account",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Impossible de supprimer son propre compte"
                    }
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Not authenticated"
                    }
                }
            }
        },
        403: {
            "description": "Access denied - user from different organization",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Accès refusé à cet utilisateur"
                    }
                }
            }
        },
        404: {
            "description": "User not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Utilisateur 550e8400-e29b-41d4-a716-446655440000 non trouvé"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds."
                    }
                }
            }
        }
    }
)
async def delete_user(
    request: Request,
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """Permanently delete a user account."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Deleting user {user_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "target_user_id": str(user_id)
        }
    )
    # Empêcher l'auto-suppression
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de supprimer son propre compte"
        )

    # Vérifier que l'utilisateur existe
    user = await UserService.get_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Utilisateur {user_id} non trouvé"
        )

    # Vérifier les permissions (même organisation ou superuser)
    if not current_user.is_superuser and user.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cet utilisateur"
        )

    await UserService.delete(session, user_id)
