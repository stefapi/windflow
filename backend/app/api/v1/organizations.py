"""
Routes de gestion des organisations.
"""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import get_current_active_user
from ...auth.rbac import require_admin, require_super_admin
from ...core.rate_limit import conditional_rate_limiter
from ...database import get_db
from ...enums.rbac import Role
from ...models.user import User
from ...models.user_organization import UserOrganization
from ...schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from ...schemas.organization_member import (
    MemberRoleUpdateRequest,
    OrganizationMemberAddRequest,
    OrganizationMemberResponse,
)
from ...services.audit_service import AuditService
from ...services.authorization_service import (
    ROLE_HIERARCHY,
    AuthorizationService,
)
from ...services.organization_service import OrganizationService
from ...services.user_organization_service import UserOrganizationService
from ...services.user_service import UserService

router = APIRouter()
logger = logging.getLogger(__name__)


# Schema for bulk operations
class BulkDeleteOrgRequest(BaseModel):
    """Request schema for bulk organization deletion."""

    organization_ids: List[str]


class BulkOperationResponse(BaseModel):
    """Response schema for bulk operations."""

    success: List[str]
    failed: List[str]
    message: str


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
                            "updated_at": "2024-01-15T10:30:00Z",
                        },
                        {
                            "id": "660e8400-e29b-41d4-a716-446655440001",
                            "name": "TechStart Inc",
                            "description": "Innovative startup",
                            "is_active": True,
                            "created_at": "2024-02-20T14:20:00Z",
                            "updated_at": "2024-02-20T14:20:00Z",
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
        403: {
            "description": "Insufficient permissions - superuser required",
            "content": {
                "application/json": {"example": {"detail": "Superuser access required"}}
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds."
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
)
async def list_organizations(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Liste toutes les organisations (super_admin uniquement).

    ## Access Control (STORY-122.4)

    Nécessite le rôle global ``super_admin`` (admin instance — matrice
    spec 08 : liste globale des organisations).

    Args:
        request: Requête HTTP (pour correlation_id)
        skip: Nombre d'éléments à ignorer pour la pagination
        limit: Nombre maximum d'éléments à retourner
        current_user: Utilisateur courant (doit être super_admin)
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
            "limit": limit,
        },
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
                        "updated_at": "2024-01-15T10:30:00Z",
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
        403: {
            "description": "Access denied - user does not belong to this organization",
            "content": {
                "application/json": {
                    "example": {"detail": "Accès refusé à cette organisation"}
                }
            },
        },
        404: {
            "description": "Organization not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Organisation 550e8400-e29b-41d4-a716-446655440000 non trouvée"
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds."
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
)
async def get_organization(
    request: Request,
    organization_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
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
        extra={
            "correlation_id": correlation_id,
            "organization_id": str(organization_id),
        },
    )
    # Vérifier que l'utilisateur appartient à l'organisation ou est superuser
    # (STORY-121.3 : appartenance via l'association — le bypass superuser
    # est déjà intégré à is_member, on garde le court-circuit is_superuser
    # pour éviter la requête inutile)
    if not current_user.is_superuser and not await UserOrganizationService.is_member(
        session, current_user, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette organisation",
        )

    organization = await OrganizationService.get_by_id(session, organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organisation {organization_id} non trouvée",
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
                                "description": "Leading technology company",
                            },
                        },
                        "detailed_organization": {
                            "summary": "Detailed organization",
                            "description": "Organization with all fields specified",
                            "value": {
                                "name": "TechStart Inc",
                                "description": "Innovative startup specializing in cloud solutions and DevOps automation",
                                "is_active": True,
                            },
                        },
                        "inactive_organization": {
                            "summary": "Inactive organization",
                            "description": "Create organization in inactive state",
                            "value": {
                                "name": "Legacy Systems Ltd",
                                "description": "Organization for migration purposes",
                                "is_active": False,
                            },
                        },
                        "minimal_organization": {
                            "summary": "Minimal organization",
                            "description": "Only required name field",
                            "value": {"name": "Simple Org"},
                        },
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
                        "updated_at": "2024-01-15T10:30:00Z",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request data",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Validation error: name must be between 1 and 100 characters"
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
        403: {
            "description": "Insufficient permissions - superuser required",
            "content": {
                "application/json": {"example": {"detail": "Superuser access required"}}
            },
        },
        409: {
            "description": "Organization name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Organisation avec le nom 'Acme Corporation' existe déjà"
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds."
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
)
async def create_organization(
    request: Request,
    organization_data: OrganizationCreate,
    current_user: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Crée une nouvelle organisation (super_admin uniquement).

    ## Access Control (STORY-122.4)

    Nécessite le rôle global ``super_admin`` (matrice spec 08 :
    « Créer = Super Admin uniquement »).

    Args:
        request: Requête HTTP (pour correlation_id)
        organization_data: Données de l'organisation à créer
        current_user: Utilisateur courant (doit être super_admin)
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
            "org_name": organization_data.name,
        },
    )
    # Vérifier que le nom n'existe pas déjà
    existing = await OrganizationService.get_by_name(session, organization_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organisation avec le nom '{organization_data.name}' existe déjà",
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
                            "value": {"name": "Acme Corporation Rebranded"},
                        },
                        "update_description": {
                            "summary": "Update description",
                            "description": "Change only the description",
                            "value": {
                                "description": "Updated company description with new focus areas"
                            },
                        },
                        "deactivate_organization": {
                            "summary": "Deactivate organization",
                            "description": "Set organization to inactive state",
                            "value": {"is_active": False},
                        },
                        "full_update": {
                            "summary": "Full update",
                            "description": "Update all fields at once",
                            "value": {
                                "name": "New Organization Name",
                                "description": "Completely updated description with new information",
                                "is_active": True,
                            },
                        },
                        "reactivate_organization": {
                            "summary": "Reactivate organization",
                            "description": "Re-enable a previously deactivated organization",
                            "value": {"is_active": True},
                        },
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
                        "updated_at": "2024-02-20T15:45:00Z",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request data",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Validation error: name must be between 1 and 100 characters"
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
        403: {
            "description": "Insufficient permissions - superuser required",
            "content": {
                "application/json": {"example": {"detail": "Superuser access required"}}
            },
        },
        404: {
            "description": "Organization not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Organisation 550e8400-e29b-41d4-a716-446655440000 non trouvée"
                    }
                }
            },
        },
        409: {
            "description": "Organization name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Organisation avec le nom 'Acme Corporation' existe déjà"
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds."
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
)
async def update_organization(
    request: Request,
    organization_id: UUID,
    organization_data: OrganizationUpdate,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Met à jour une organisation (admin de l'organisation).

    ## Access Control (STORY-122.4)

    Nécessite le rôle global ``admin`` **et** l'appartenance à
    l'organisation (isolation via ``is_member`` — un admin global
    non-membre ne modifie pas l'org ; les superusers bypassent).

    Args:
        request: Requête HTTP (pour correlation_id)
        organization_id: ID de l'organisation à modifier
        organization_data: Nouvelles données de l'organisation
        current_user: Utilisateur courant (admin membre ou superuser)
        session: Session de base de données

    Returns:
        OrganizationResponse: Organisation mise à jour

    Raises:
        HTTPException: 403 si non-membre, 404 si introuvable, 409 conflit nom
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Updating organization {organization_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "organization_id": str(organization_id),
        },
    )
    # Isolation : admin global non-membre → refus (superuser bypass)
    if not current_user.is_superuser and not await UserOrganizationService.is_member(
        session, current_user, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette organisation",
        )
    # Vérifier que l'organisation existe
    existing_org = await OrganizationService.get_by_id(session, organization_id)
    if not existing_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organisation {organization_id} non trouvée",
        )

    # Si changement de nom, vérifier qu'il n'existe pas déjà
    if organization_data.name and organization_data.name != existing_org.name:
        existing_name = await OrganizationService.get_by_name(
            session, organization_data.name
        )
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Organisation avec le nom '{organization_data.name}' existe déjà",
            )

    organization = await OrganizationService.update(
        session, organization_id, organization_data
    )
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
        204: {"description": "Organization deleted successfully (no content returned)"},
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {"example": {"detail": "Not authenticated"}}
            },
        },
        403: {
            "description": "Insufficient permissions - superuser required",
            "content": {
                "application/json": {"example": {"detail": "Superuser access required"}}
            },
        },
        404: {
            "description": "Organization not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Organisation 550e8400-e29b-41d4-a716-446655440000 non trouvée"
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds."
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
)
async def delete_organization(
    request: Request,
    organization_id: UUID,
    current_user: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Supprime une organisation (super_admin uniquement).

    ## Access Control (STORY-122.4)

    Nécessite le rôle global ``super_admin`` — suppression irréversible
    avec effets cascade (matrice spec 08 : opération d'administration
    d'instance).

    Args:
        request: Requête HTTP (pour correlation_id)
        organization_id: ID de l'organisation à supprimer
        current_user: Utilisateur courant (doit être super_admin)
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
            "organization_id": str(organization_id),
        },
    )
    # Vérifier que l'organisation existe
    organization = await OrganizationService.get_by_id(session, organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organisation {organization_id} non trouvée",
        )

    await OrganizationService.delete(session, organization_id)

    # STORY-125.2 : audit de la suppression (après succès). org supprimée →
    # la FK SET NULL anonymise la ligne (conservation documentaire, 125.1) ;
    # on trace l'id tout de même via organization_id + details.name.
    await AuditService.log_from_request(
        request,
        "organization.deleted",
        user=current_user,
        organization_id=str(organization_id),
        resource_type="organization",
        resource_id=str(organization_id),
        details={"name": organization.name},
    )


@router.post(
    "/bulk/delete",
    response_model=BulkOperationResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk delete organizations",
    description="""
Delete multiple organizations in a single operation.

## Access Control
- **Superusers only**: This endpoint requires superuser privileges

## Safety Features
- **Maximum 100 organizations per request**: Prevents accidental mass deletions

## Request Body
- `organization_ids`: List of organization UUIDs to delete (max 100)

## Response
- `success`: List of organization IDs that were successfully deleted
- `failed`: List of organization IDs that could not be deleted
- `message`: Summary of the operation

**Authentication Required - Superuser Only**
""",
    dependencies=[Depends(conditional_rate_limiter(5, 60))],
    responses={
        200: {
            "description": "Bulk delete operation completed",
            "content": {
                "application/json": {
                    "example": {
                        "success": ["550e8400-e29b-41d4-a716-446655440000"],
                        "failed": [],
                        "message": "1 organisation(s) supprimée(s), 0 échec(s)",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request - too many organizations or empty list",
            "content": {
                "application/json": {
                    "example": {"detail": "Maximum 100 organisations par requête"}
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not a superuser"},
    },
)
async def bulk_delete_organizations(
    request: Request,
    bulk_data: BulkDeleteOrgRequest,
    current_user: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Delete multiple organizations in bulk.

    ## Access Control (STORY-122.4)

    Nécessite le rôle global ``super_admin`` — opération globale
    d'administration d'instance.
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Bulk deleting organizations",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "org_count": len(bulk_data.organization_ids),
        },
    )

    # Validate request
    if not bulk_data.organization_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La liste des organisations ne peut pas être vide",
        )

    if len(bulk_data.organization_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 100 organisations par requête",
        )

    # Perform bulk delete
    success: List[str] = []
    failed: List[str] = []

    for org_id in bulk_data.organization_ids:
        try:
            # Check if organization exists
            org = await OrganizationService.get_by_id(session, UUID(org_id))
            if not org:
                failed.append(org_id)
                continue

            await OrganizationService.delete(session, UUID(org_id))
            # STORY-125.2 : une ligne d'audit par org supprimée (bulk) —
            # chaque suppression destructrice est tracée individuellement.
            await AuditService.log_from_request(
                request,
                "organization.deleted",
                user=current_user,
                organization_id=org_id,
                resource_type="organization",
                resource_id=org_id,
                details={"name": org.name, "bulk": True},
            )
            success.append(org_id)
        except Exception as e:
            logger.error(
                f"Failed to delete organization {org_id}: {str(e)}",
                extra={"correlation_id": correlation_id, "org_id": org_id},
            )
            failed.append(org_id)

    return BulkOperationResponse(
        success=success,
        failed=failed,
        message=f"{len(success)} organisation(s) supprimée(s), {len(failed)} échec(s)",
    )


# ---------------------------------------------------------------------------
# Gestion des membres d'une organisation (spec 09 § Organizations — STORY-121.2)
# ---------------------------------------------------------------------------


def _role_str(role: object) -> str:
    """
    Valeur chaîne d'un rôle (enum ``Role`` ou str lue depuis la base).

    Args:
        role: Rôle (instance ``Role`` ou chaîne stockée en ``String(20)``)

    Returns:
        Valeur du rôle sous forme de chaîne (ex. ``"viewer"``)
    """
    return role.value if isinstance(role, Role) else str(role)


def _member_to_response(link: UserOrganization) -> OrganizationMemberResponse:
    """
    Mappe une association ``UserOrganization`` vers le schéma de réponse membre.

    Whitelist stricte : seuls ``user_id``, ``username``, ``email``,
    ``full_name``, ``role`` et ``joined_at`` sont exposés — jamais
    ``hashed_password`` ni ``keycloak_id``.

    Args:
        link: Association utilisateur ↔ organisation (relation ``user`` chargée)

    Returns:
        OrganizationMemberResponse: Réponse membre prête à sérialiser
    """
    return OrganizationMemberResponse(
        user_id=link.user_id,
        username=link.user.username,
        email=link.user.email,
        full_name=link.user.full_name,
        role=link.role,
        joined_at=link.joined_at,
    )


@router.get(
    "/{organization_id}/users",
    response_model=List[OrganizationMemberResponse],
    status_code=status.HTTP_200_OK,
    summary="List members of an organization",
    description="""
List the members of an organization with their role and join date.

## Access Control
- **Authentication required** (any active member of the organization)
- **Isolation**: Users who do not belong to the organization receive a 403
  Forbidden error (superusers can list members of any organization)
- Reading members is allowed for all roles (spec 08 permission matrix)

## Pagination
- Use `skip` and `limit` query parameters for pagination
- Default limit: 100 members per page

## Response Data
Each member entry includes:
- `user_id`, `username`, `email`, `full_name` (public user information only)
- `role`: organization role (`viewer` | `operator` | `admin`)
- `joined_at`: membership creation date

Sensitive fields (`hashed_password`, `keycloak_id`) are never exposed.

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(60, 60))],
    responses={
        200: {
            "description": "List of members retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "user_id": "770e8400-e29b-41d4-a716-446655440010",
                            "username": "jdoe",
                            "email": "jdoe@example.com",
                            "full_name": "John Doe",
                            "role": "viewer",
                            "joined_at": "2026-09-08T10:00:00Z",
                        }
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
        403: {
            "description": "Access denied - user does not belong to this organization",
            "content": {
                "application/json": {
                    "example": {"detail": "Accès refusé à cette organisation"}
                }
            },
        },
        404: {
            "description": "Organization not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Organisation 550e8400-e29b-41d4-a716-446655440000 non trouvée"
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds."
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
)
async def list_organization_members(
    request: Request,
    organization_id: UUID,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Liste les membres d'une organisation avec leur rôle et date d'adhésion.

    Args:
        request: Requête HTTP (pour correlation_id)
        organization_id: ID de l'organisation
        skip: Nombre d'éléments à ignorer pour la pagination
        limit: Nombre maximum d'éléments à retourner
        current_user: Utilisateur courant (doit être membre de l'organisation)
        session: Session de base de données

    Returns:
        List[OrganizationMemberResponse]: Membres de l'organisation

    Raises:
        HTTPException: 403 si l'utilisateur n'appartient pas à l'organisation,
            404 si l'organisation n'existe pas
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    # Isolation cross-organisation AVANT toute lecture
    # (superuser bypass — spec 08 ; helper STORY-121.2)
    if not current_user.is_superuser and not await UserOrganizationService.is_member(
        session, current_user, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette organisation",
        )

    organization = await OrganizationService.get_by_id(session, organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organisation {organization_id} non trouvée",
        )

    logger.info(
        f"Listing members of organization {organization_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "organization_id": str(organization_id),
            "skip": skip,
            "limit": limit,
        },
    )

    members = await UserOrganizationService.list_members(
        session, organization_id, skip, limit
    )
    return [_member_to_response(link) for link in members]


@router.post(
    "/{organization_id}/users",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member to an organization",
    description="""
Add a user as a member of an organization with an optional role.

## Access Control
- **Minimum role**: Admin in the organization — non-superusers must be a
  member of the organization (cross-organization isolation via membership
  check) and cannot assign a role equal or higher than their own
  (escalation protection, spec 08 § Security)
- Superusers bypass the isolation check
- Adding members requires Admin+ permissions (spec 08 permission matrix)

## Validation Rules
- `user_id`: required UUID of an existing user (404 if the user does not exist)
- `role`: optional, one of `viewer` | `operator` | `admin` — **defaults to
  `viewer`** (spec 09); any other value (including `super_admin`) returns 422
- Adding an existing member returns 409 Conflict

## Use Cases
- Onboarding a new user into an organization
- Granting a user access to organization resources
- Multi-tenant membership management

**Authentication Required - Admin role in the organization**
""",
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "default_viewer_role": {
                            "summary": "Default viewer role",
                            "description": "Add a member with the default `viewer` role",
                            "value": {
                                "user_id": "770e8400-e29b-41d4-a716-446655440010"
                            },
                        },
                        "explicit_operator_role": {
                            "summary": "Explicit operator role",
                            "description": "Add a member with an explicit `operator` role",
                            "value": {
                                "user_id": "770e8400-e29b-41d4-a716-446655440010",
                                "role": "operator",
                            },
                        },
                    }
                }
            }
        }
    },
    responses={
        201: {
            "description": "Member added successfully",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "770e8400-e29b-41d4-a716-446655440010",
                        "username": "jdoe",
                        "email": "jdoe@example.com",
                        "full_name": "John Doe",
                        "role": "viewer",
                        "joined_at": "2026-09-08T10:00:00Z",
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
        403: {
            "description": "Insufficient permissions or access denied to this organization",
            "content": {
                "application/json": {"example": {"detail": "Not enough permissions"}}
            },
        },
        404: {
            "description": "Organization or target user not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Utilisateur 770e8400-e29b-41d4-a716-446655440010 introuvable"
                    }
                }
            },
        },
        409: {
            "description": "User is already a member of this organization",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "L'utilisateur 770e8400-e29b-41d4-a716-446655440010 est déjà membre"
                    }
                }
            },
        },
        422: {
            "description": "Validation error - invalid role (super_admin is a system role) or invalid user_id format",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Input should be 'viewer', 'operator' or 'admin'"
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds."
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
)
async def add_organization_member(
    request: Request,
    organization_id: UUID,
    member_data: OrganizationMemberAddRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Ajoute un utilisateur comme membre d'une organisation (admin de l'org).

    ## Access Control (STORY-122.4)

    Nécessite le rôle global ``admin`` **et** l'appartenance à
    l'organisation (isolation ``is_member`` — garde effectif ; les
    superusers bypassent). Anti-escalade : un admin non-superuser ne peut
    ajouter qu'un membre avec un rôle **strictement inférieur** au sien
    (spec 08 § Protection contre l'escalade).

    Args:
        request: Requête HTTP (pour correlation_id)
        organization_id: ID de l'organisation
        member_data: Données d'ajout (``user_id`` requis, ``role`` défaut viewer)
        current_user: Utilisateur courant (admin membre ou superuser)
        session: Session de base de données

    Returns:
        OrganizationMemberResponse: Membre ajouté (rôle par défaut ``viewer``)

    Raises:
        HTTPException: 403 si accès refusé, 404 si l'organisation ou
            l'utilisateur cible n'existe pas, 409 si déjà membre
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    # Isolation cross-organisation (structure prête pour les admins d'org
    # post-STORY-122 ; no-op intérim derrière le bypass superuser)
    if not current_user.is_superuser and not await UserOrganizationService.is_member(
        session, current_user, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette organisation",
        )

    organization = await OrganizationService.get_by_id(session, organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organisation {organization_id} non trouvée",
        )

    # Check explicite de l'utilisateur cible (404 distinct du 409)
    target_user = await UserService.get_by_id(session, str(member_data.user_id))
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Utilisateur {member_data.user_id} introuvable",
        )

    # Anti-escalade (AC 3, spec 08 § Protection contre l'escalade) :
    # un acteur non-superuser ne peut ajouter un membre qu'avec un rôle
    # strictement inférieur au sien dans l'organisation.
    if not current_user.is_superuser:
        actor_role = await AuthorizationService.get_role_in_organization(
            session, current_user, organization_id
        )
        if (
            actor_role is None
            or ROLE_HIERARCHY.get(actor_role, -1) < ROLE_HIERARCHY["admin"]
        ):
            # Double garde : l'isolation is_member a déjà filtré, mais un
            # non-admin membre (viewer/operator) ne doit pas passer.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        if ROLE_HIERARCHY[member_data.role.value] >= ROLE_HIERARCHY[actor_role]:
            logger.warning(
                "Escalation attempt blocked: role equal or higher than actor",
                extra={
                    "correlation_id": correlation_id,
                    "user_id": str(current_user.id),
                    "target_user_id": str(member_data.user_id),
                    "organization_id": str(organization_id),
                    "requested_role": member_data.role.value,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot assign a role equal or higher than your own",
            )

    try:
        membership = await UserOrganizationService.add_member(
            session, organization_id, member_data
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    # STORY-122.1 : invalidation cache rôle (TTL max 300 s sinon)
    await AuthorizationService.invalidate_user_role_cache(str(member_data.user_id))

    # Audit intérimaire (traçabilité structurée ; table audit_logs portée
    # par STORY-125) — aucune donnée sensible dans les logs
    logger.info(
        "Member added",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "organization_id": str(organization_id),
            "target_user_id": str(member_data.user_id),
            "role": member_data.role.value,
        },
    )
    # STORY-125.2 : audit persisté de l'ajout de membre (après succès).
    await AuditService.log_from_request(
        request,
        "member.added",
        user=current_user,
        organization_id=str(organization_id),
        resource_type="user",
        resource_id=str(member_data.user_id),
        details={"role": member_data.role.value},
    )
    return _member_to_response(membership)


@router.put(
    "/{organization_id}/users/{user_id}",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a member's role",
    description="""
Change the role of an existing member of an organization.

## Access Control
- **Minimum role**: Admin in the organization — non-superusers must be a
  member of the organization (cross-organization isolation via membership
  check)
- **Escalation protection** (spec 08 § Security): a non-superuser admin
  cannot assign a role equal or higher than their own, cannot modify a
  member whose current role is equal or higher, and cannot promote
  themselves; superusers bypass these checks
- Changing roles requires Admin+ permissions (spec 08 permission matrix)
- Permission changes are audit-logged (spec 08 security section)

## Validation Rules
- `role`: required, one of `viewer` | `operator` | `admin` — any other
  value (including `super_admin`) returns 422
- Returns 404 if the organization exists but the user is not one of its members

## Escalation Protection
`super_admin` is a system role carried by `User.is_superuser` and can never
be stored as an organization role (validation error 422).

**Authentication Required - Admin role in the organization**
""",
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "promote_to_operator": {
                            "summary": "Promote to operator",
                            "description": "Change the member role to `operator`",
                            "value": {"role": "operator"},
                        },
                        "promote_to_admin": {
                            "summary": "Promote to admin",
                            "description": "Change the member role to `admin`",
                            "value": {"role": "admin"},
                        },
                        "demote_to_viewer": {
                            "summary": "Demote to viewer",
                            "description": "Change the member role back to `viewer`",
                            "value": {"role": "viewer"},
                        },
                    }
                }
            }
        }
    },
    responses={
        200: {
            "description": "Member role updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "770e8400-e29b-41d4-a716-446655440010",
                        "username": "jdoe",
                        "email": "jdoe@example.com",
                        "full_name": "John Doe",
                        "role": "operator",
                        "joined_at": "2026-09-08T10:00:00Z",
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
        403: {
            "description": "Insufficient permissions or access denied to this organization",
            "content": {
                "application/json": {"example": {"detail": "Not enough permissions"}}
            },
        },
        404: {
            "description": "Organization not found or user is not a member",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Membre 770e8400-e29b-41d4-a716-446655440010 introuvable dans cette organisation"
                    }
                }
            },
        },
        422: {
            "description": "Validation error - invalid role (super_admin is a system role)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Input should be 'viewer', 'operator' or 'admin'"
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds."
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
)
async def update_organization_member_role(
    request: Request,
    organization_id: UUID,
    user_id: UUID,
    role_data: MemberRoleUpdateRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Modifie le rôle d'un membre d'une organisation (admin de l'org).

    ## Access Control & Anti-escalade (STORY-122.4)

    Nécessite le rôle global ``admin`` **et** l'appartenance à
    l'organisation (isolation ``is_member`` ; superusers bypassent).
    Anti-escalade (spec 08 § Protection contre l'escalade) : un acteur
    non-superuser ne peut ni attribuer un rôle >= au sien, ni modifier un
    membre dont le rôle actuel est >= au sien (couvre l'auto-promotion).

    Args:
        request: Requête HTTP (pour correlation_id)
        organization_id: ID de l'organisation
        user_id: ID de l'utilisateur membre
        role_data: Nouveau rôle (borné enum ``Role``)
        current_user: Utilisateur courant (admin membre ou superuser)
        session: Session de base de données

    Returns:
        OrganizationMemberResponse: Membre avec son nouveau rôle

    Raises:
        HTTPException: 403 si accès refusé, 404 si l'organisation
            n'existe pas ou l'utilisateur n'est pas membre
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    # Isolation cross-organisation (structure prête pour STORY-122)
    if not current_user.is_superuser and not await UserOrganizationService.is_member(
        session, current_user, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette organisation",
        )

    organization = await OrganizationService.get_by_id(session, organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organisation {organization_id} non trouvée",
        )

    membership = await UserOrganizationService.get_membership(
        session, organization_id, user_id
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Membre {user_id} introuvable dans cette organisation",
        )

    # Anti-escalade (AC 3, spec 08 § Protection contre l'escalade) :
    # un acteur non-superuser ne peut ni attribuer un rôle >= au sien,
    # ni modifier un membre dont le rôle actuel est >= au sien
    # (la seconde condition couvre l'auto-promotion : son propre rôle
    # actuel est >= à son rôle d'acteur).
    if not current_user.is_superuser:
        actor_role = await AuthorizationService.get_role_in_organization(
            session, current_user, organization_id
        )
        if actor_role is None:
            # Double garde : is_member a déjà filtré les non-membres.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé à cette organisation",
            )
        new_role_level = ROLE_HIERARCHY[role_data.role.value]
        current_role_level = ROLE_HIERARCHY[_role_str(membership.role)]
        actor_level = ROLE_HIERARCHY[actor_role]
        if new_role_level >= actor_level or current_role_level >= actor_level:
            logger.warning(
                "Escalation attempt blocked: cannot assign or modify a role "
                "equal or higher than your own",
                extra={
                    "correlation_id": correlation_id,
                    "user_id": str(current_user.id),
                    "target_user_id": str(user_id),
                    "organization_id": str(organization_id),
                    "previous_role": _role_str(membership.role),
                    "requested_role": role_data.role.value,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot assign a role equal or higher than your own",
            )

    previous_role = _role_str(membership.role)
    updated = await UserOrganizationService.update_member_role(
        session, membership, role_data.role
    )

    # STORY-122.1 : invalidation cache rôle (TTL max 300 s sinon)
    await AuthorizationService.invalidate_user_role_cache(str(user_id))

    # Audit intérimaire : ancien/nouveau rôle tracés (spec 08 § Audit)
    logger.info(
        "Member role updated",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "organization_id": str(organization_id),
            "target_user_id": str(user_id),
            "previous_role": previous_role,
            "new_role": role_data.role.value,
        },
    )
    # STORY-125.2 : audit persisté du changement de rôle (spec 08 § Audit —
    # changements de rôles = action critique du catalogue spec 15).
    await AuditService.log_from_request(
        request,
        "user.role_changed",
        user=current_user,
        organization_id=str(organization_id),
        resource_type="user",
        resource_id=str(user_id),
        details={"previous_role": previous_role, "new_role": role_data.role.value},
    )
    return _member_to_response(updated)


@router.delete(
    "/{organization_id}/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from an organization",
    description="""
Remove a member from an organization (deletes the membership association).

## Access Control
- **Minimum role**: Admin in the organization — non-superusers must be a
  member of the organization (cross-organization isolation via membership
  check); superusers bypass the isolation check
- Removing members requires Admin+ permissions (spec 08 permission matrix)
- Removals are audit-logged (spec 08 security section)

## Impact of Removal
- The user loses access to organization resources tied to the membership
- The user account itself is **never** deleted
- The system role (`User.is_superuser`) is **never** modified by removal

## Response
Returns 204 No Content on success; 404 if the organization exists but the
user is not one of its members.

**Authentication Required - Admin role in the organization**
""",
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
    responses={
        204: {"description": "Member removed successfully (no content returned)"},
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {"example": {"detail": "Not authenticated"}}
            },
        },
        403: {
            "description": "Insufficient permissions or access denied to this organization",
            "content": {
                "application/json": {"example": {"detail": "Not enough permissions"}}
            },
        },
        404: {
            "description": "Organization not found or user is not a member",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Membre 770e8400-e29b-41d4-a716-446655440010 introuvable dans cette organisation"
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Try again in 60 seconds."
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
)
async def remove_organization_member(
    request: Request,
    organization_id: UUID,
    user_id: UUID,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Retire un membre d'une organisation (admin de l'org).

    ## Access Control (STORY-122.4)

    Nécessite le rôle global ``admin`` **et** l'appartenance à
    l'organisation (isolation ``is_member`` — garde effectif ; les
    superusers bypassent).

    Supprime uniquement l'association — jamais le compte utilisateur ni le
    rôle système ``User.is_superuser``.

    Args:
        request: Requête HTTP (pour correlation_id)
        organization_id: ID de l'organisation
        user_id: ID de l'utilisateur membre à retirer
        current_user: Utilisateur courant (admin membre ou superuser)
        session: Session de base de données

    Raises:
        HTTPException: 403 si accès refusé, 404 si l'organisation
            n'existe pas ou l'utilisateur n'est pas membre
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    # Isolation cross-organisation (structure prête pour STORY-122)
    if not current_user.is_superuser and not await UserOrganizationService.is_member(
        session, current_user, organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette organisation",
        )

    organization = await OrganizationService.get_by_id(session, organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organisation {organization_id} non trouvée",
        )

    membership = await UserOrganizationService.get_membership(
        session, organization_id, user_id
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Membre {user_id} introuvable dans cette organisation",
        )

    await UserOrganizationService.remove_member(session, membership)

    # STORY-122.1 : invalidation cache rôle (TTL max 300 s sinon)
    await AuthorizationService.invalidate_user_role_cache(str(user_id))

    # Audit intérimaire (spec 08 § Audit — traçabilité du retrait)
    logger.info(
        "Member removed",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "organization_id": str(organization_id),
            "target_user_id": str(user_id),
        },
    )
    # STORY-125.2 : audit persisté du retrait de membre (après succès).
    await AuditService.log_from_request(
        request,
        "member.removed",
        user=current_user,
        organization_id=str(organization_id),
        resource_type="user",
        resource_id=str(user_id),
    )
    return None
