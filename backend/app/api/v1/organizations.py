"""
Routes de gestion des organisations.
"""

from typing import List
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas.organization import OrganizationResponse, OrganizationCreate, OrganizationUpdate
from ...services.organization_service import OrganizationService
from ...auth.dependencies import get_current_active_user, require_superuser
from ...models.user import User
from ...core.rate_limit import conditional_rate_limiter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/",
    response_model=List[OrganizationResponse],
    status_code=status.HTTP_200_OK,
    summary="List all organizations",
    description="""
List all organizations in the system.

## Access Control
- **Superuser only**: Only system administrators can list all organizations
- Regular users can only access their own organization via GET /{organization_id}

## Pagination
- Use `skip` and `limit` parameters for pagination
- Default limit: 100 organizations per page
- Maximum limit: 1000 organizations per page

## Use Cases
- System administration and monitoring
- Organization management dashboard
- Bulk operations and reporting
- Multi-tenant system overview

**Authentication Required** - Superuser role required
""",
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
    responses={
        200: {
            "description": "List of organizations retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "name": "Acme Corporation",
                            "description": "Leading technology company",
                            "is_active": True,
                            "created_at": "2024-01-15T10:30:00Z",
                            "updated_at": "2024-01-15T10:30:00Z"
                        },
                        {
                            "id": "660e8400-e29b-41d4-a716-446655440001",
                            "name": "TechStart Inc",
                            "description": "Innovative startup",
                            "is_active": True,
                            "created_at": "2024-02-20T14:20:00Z",
                            "updated_at": "2024-02-20T14:20:00Z"
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
        403: {
            "description": "Insufficient permissions - superuser required",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Superuser access required"
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
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    }
)
async def list_organizations(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_db)
):
    """
    Liste toutes les organisations (superuser uniquement).

    Args:
        request: Requête HTTP (pour correlation_id)
        skip: Nombre d'éléments à ignorer pour la pagination
        limit: Nombre maximum d'éléments à retourner
        current_user: Utilisateur courant (doit être superuser)
        session: Session de base de données

    Returns:
        List[OrganizationResponse]: Liste des organisations
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Listing all organizations",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "skip": skip,
            "limit": limit
        }
    )

    organizations = await OrganizationService.list_all(session, skip, limit)
    return organizations


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get organization by ID",
    description="""
Retrieve detailed information about a specific organization.

## Access Control
- **Superuser**: Can access any organization
- **Regular User**: Can only access their own organization
- Users from other organizations will receive a 403 Forbidden error

## Use Cases
- View organization profile and settings
- Check organization status and metadata
- Retrieve organization details for user context
- Validate organization membership

## Response Data
Returns complete organization information including:
- Organization ID and name
- Description and metadata
- Active status
- Creation and update timestamps

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(60, 60))],
    responses={
        200: {
            "description": "Organization retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Acme Corporation",
                        "description": "Leading technology company specializing in cloud solutions",
                        "is_active": True,
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-15T10:30:00Z"
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
            "description": "Access denied - user does not belong to this organization",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Accès refusé à cette organisation"
                    }
                }
            }
        },
        404: {
            "description": "Organization not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Organisation 550e8400-e29b-41d4-a716-446655440000 non trouvée"
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
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    }
)
async def get_organization(
    request: Request,
    organization_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Récupère une organisation par son ID.

    Args:
        request: Requête HTTP (pour correlation_id)
        organization_id: ID de l'organisation
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        OrganizationResponse: Organisation demandée

    Raises:
        HTTPException: Si l'organisation n'existe pas ou accès refusé
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting organization {organization_id}",
        extra={"correlation_id": correlation_id, "organization_id": str(organization_id)}
    )
    # Vérifier que l'utilisateur appartient à l'organisation ou est superuser
    if not current_user.is_superuser and current_user.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette organisation"
        )

    organization = await OrganizationService.get_by_id(session, organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organisation {organization_id} non trouvée"
        )
    return organization


@router.post(
    "/",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization",
    description="""
Create a new organization in the system.

## Access Control
- **Superuser only**: Only system administrators can create organizations
- This is a privileged operation for multi-tenant setup

## Validation Rules
- **Name**: Must be unique across all organizations
- **Name**: 1-100 characters, alphanumeric with spaces and hyphens
- **Description**: Optional, up to 500 characters
- **is_active**: Defaults to True if not specified

## Use Cases
- Initial system setup and tenant onboarding
- Adding new client organizations
- Multi-tenant SaaS provisioning
- Organization hierarchy management

## Post-Creation Steps
After creating an organization, you typically need to:
1. Create organization admin users
2. Configure organization-specific settings
3. Set up environments and targets
4. Assign resource quotas

**Authentication Required** - Superuser role required
""",
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "basic_organization": {
                            "summary": "Basic organization",
                            "description": "Minimal organization with required fields only",
                            "value": {
                                "name": "Acme Corporation",
                                "description": "Leading technology company"
                            }
                        },
                        "detailed_organization": {
                            "summary": "Detailed organization",
                            "description": "Organization with all fields specified",
                            "value": {
                                "name": "TechStart Inc",
                                "description": "Innovative startup specializing in cloud solutions and DevOps automation",
                                "is_active": True
                            }
                        },
                        "inactive_organization": {
                            "summary": "Inactive organization",
                            "description": "Create organization in inactive state",
                            "value": {
                                "name": "Legacy Systems Ltd",
                                "description": "Organization for migration purposes",
                                "is_active": False
                            }
                        },
                        "minimal_organization": {
                            "summary": "Minimal organization",
                            "description": "Only required name field",
                            "value": {
                                "name": "Simple Org"
                            }
                        }
                    }
                }
            }
        }
    },
    responses={
        201: {
            "description": "Organization created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Acme Corporation",
                        "description": "Leading technology company",
                        "is_active": True,
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid request data",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Validation error: name must be between 1 and 100 characters"
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
            "description": "Insufficient permissions - superuser required",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Superuser access required"
                    }
                }
            }
        },
        409: {
            "description": "Organization name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Organisation avec le nom 'Acme Corporation' existe déjà"
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
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    }
)
async def create_organization(
    request: Request,
    organization_data: OrganizationCreate,
    current_user: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_db)
):
    """
    Crée une nouvelle organisation (superuser uniquement).

    Args:
        request: Requête HTTP (pour correlation_id)
        organization_data: Données de l'organisation à créer
        current_user: Utilisateur courant (doit être superuser)
        session: Session de base de données

    Returns:
        OrganizationResponse: Organisation créée

    Raises:
        HTTPException: Si le nom existe déjà
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Creating organization '{organization_data.name}'",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "org_name": organization_data.name
        }
    )
    # Vérifier que le nom n'existe pas déjà
    existing = await OrganizationService.get_by_name(session, organization_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organisation avec le nom '{organization_data.name}' existe déjà"
        )

    organization = await OrganizationService.create(session, organization_data)
    return organization


@router.put(
    "/{organization_id}",
    response_model=OrganizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an organization",
    description="""
Update an existing organization's information.

## Access Control
- **Superuser only**: Only system administrators can update organizations
- This is a privileged operation affecting tenant configuration

## Validation Rules
- **Name**: Must be unique if changed (checked against other organizations)
- **Name**: 1-100 characters if provided
- **Description**: Up to 500 characters if provided
- **is_active**: Can be toggled to enable/disable organization

## Partial Updates
All fields are optional - only provided fields will be updated:
- Omitted fields remain unchanged
- Null values are ignored (use empty string to clear text fields)
- Use PATCH semantics with PUT method

## Use Cases
- Rename organization
- Update organization description
- Activate/deactivate organization
- Modify organization metadata

## Impact of Deactivation
Setting `is_active` to False will:
- Prevent users from logging in
- Block API access for organization members
- Maintain data integrity (no deletion)
- Allow reactivation later

**Authentication Required** - Superuser role required
""",
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "update_name": {
                            "summary": "Update organization name",
                            "description": "Change only the organization name",
                            "value": {
                                "name": "Acme Corporation Rebranded"
                            }
                        },
                        "update_description": {
                            "summary": "Update description",
                            "description": "Change only the description",
                            "value": {
                                "description": "Updated company description with new focus areas"
                            }
                        },
                        "deactivate_organization": {
                            "summary": "Deactivate organization",
                            "description": "Set organization to inactive state",
                            "value": {
                                "is_active": False
                            }
                        },
                        "full_update": {
                            "summary": "Full update",
                            "description": "Update all fields at once",
                            "value": {
                                "name": "New Organization Name",
                                "description": "Completely updated description with new information",
                                "is_active": True
                            }
                        },
                        "reactivate_organization": {
                            "summary": "Reactivate organization",
                            "description": "Re-enable a previously deactivated organization",
                            "value": {
                                "is_active": True
                            }
                        }
                    }
                }
            }
        }
    },
    responses={
        200: {
            "description": "Organization updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Acme Corporation Rebranded",
                        "description": "Updated company description",
                        "is_active": True,
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-02-20T15:45:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid request data",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Validation error: name must be between 1 and 100 characters"
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
            "description": "Insufficient permissions - superuser required",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Superuser access required"
                    }
                }
            }
        },
        404: {
            "description": "Organization not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Organisation 550e8400-e29b-41d4-a716-446655440000 non trouvée"
                    }
                }
            }
        },
        409: {
            "description": "Organization name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Organisation avec le nom 'Acme Corporation' existe déjà"
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
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    }
)
async def update_organization(
    request: Request,
    organization_id: UUID,
    organization_data: OrganizationUpdate,
    current_user: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_db)
):
    """
    Met à jour une organisation (superuser uniquement).

    Args:
        request: Requête HTTP (pour correlation_id)
        organization_id: ID de l'organisation à modifier
        organization_data: Nouvelles données de l'organisation
        current_user: Utilisateur courant (doit être superuser)
        session: Session de base de données

    Returns:
        OrganizationResponse: Organisation mise à jour

    Raises:
        HTTPException: Si l'organisation n'existe pas ou nom en conflit
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Updating organization {organization_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "organization_id": str(organization_id)
        }
    )
    # Vérifier que l'organisation existe
    existing_org = await OrganizationService.get_by_id(session, organization_id)
    if not existing_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organisation {organization_id} non trouvée"
        )

    # Si changement de nom, vérifier qu'il n'existe pas déjà
    if organization_data.name and organization_data.name != existing_org.name:
        existing_name = await OrganizationService.get_by_name(session, organization_data.name)
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Organisation avec le nom '{organization_data.name}' existe déjà"
            )

    organization = await OrganizationService.update(session, organization_id, organization_data)
    return organization


@router.delete(
    "/{organization_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an organization",
    description="""
Delete an organization from the system.

## Access Control
- **Superuser only**: Only system administrators can delete organizations
- This is a destructive operation with cascading effects

## ⚠️ Warning - Destructive Operation
Deleting an organization will:
- **Remove all users** belonging to the organization
- **Delete all deployments** created by organization members
- **Remove all stacks** owned by the organization
- **Delete all environments and targets** configured for the organization
- **Cascade delete all related data** (logs, metrics, configurations)

## Recommended Alternative
Instead of deletion, consider:
- **Deactivating** the organization (PUT with `is_active: false`)
- This preserves data while preventing access
- Allows reactivation if needed later

## Use Cases
- Complete tenant removal from multi-tenant system
- Cleanup after testing or demo organizations
- Compliance with data deletion requests (GDPR)
- System maintenance and cleanup

## Best Practices
1. **Backup data** before deletion
2. **Notify users** of impending deletion
3. **Export important data** for archival
4. **Verify organization ID** carefully
5. **Consider deactivation** instead of deletion

**Authentication Required** - Superuser role required
""",
    dependencies=[Depends(conditional_rate_limiter(5, 60))],
    responses={
        204: {
            "description": "Organization deleted successfully (no content returned)"
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
            "description": "Insufficient permissions - superuser required",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Superuser access required"
                    }
                }
            }
        },
        404: {
            "description": "Organization not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Organisation 550e8400-e29b-41d4-a716-446655440000 non trouvée"
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
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    }
)
async def delete_organization(
    request: Request,
    organization_id: UUID,
    current_user: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_db)
):
    """
    Supprime une organisation (superuser uniquement).

    Args:
        request: Requête HTTP (pour correlation_id)
        organization_id: ID de l'organisation à supprimer
        current_user: Utilisateur courant (doit être superuser)
        session: Session de base de données

    Raises:
        HTTPException: Si l'organisation n'existe pas
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Deleting organization {organization_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "organization_id": str(organization_id)
        }
    )
    # Vérifier que l'organisation existe
    organization = await OrganizationService.get_by_id(session, organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organisation {organization_id} non trouvée"
        )

    await OrganizationService.delete(session, organization_id)
