"""Opérations CRUD sur les cibles de déploiement."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....auth.dependencies import get_current_active_user
from ....core.rate_limit import conditional_rate_limiter
from ....database import get_db
from ....models.user import User
from ....schemas.target import (
    TargetCreate,
    TargetResponse,
    TargetUpdate,
)
from ....services.target_service import TargetService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/",
    response_model=list[TargetResponse],
    status_code=status.HTTP_200_OK,
    summary="List deployment targets",
    description="""
List all deployment targets for the current user's organization.

## Features
- Paginated results with skip/limit parameters
- Organization-scoped access (users only see their org's targets)
- Returns all target types (Docker, SSH, Kubernetes, etc.)

## Target Types
- **Docker**: Docker daemon targets
- **SSH**: Remote SSH servers
- **Kubernetes**: K8s clusters
- **Docker Swarm**: Swarm clusters
- **Nomad**: HashiCorp Nomad clusters

## Pagination
Use `skip` and `limit` parameters to paginate through large result sets.
Default limit is 100 targets per request.

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        200: {
            "description": "List of targets retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "name": "production-docker",
                            "type": "docker",
                            "host": "docker.prod.example.com",
                            "port": 2376,
                            "is_active": True,
                            "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                            "created_at": "2026-01-15T10:30:00Z",
                        },
                        {
                            "id": "770e8400-e29b-41d4-a716-446655440002",
                            "name": "staging-k8s",
                            "type": "kubernetes",
                            "host": "k8s.staging.example.com",
                            "port": 6443,
                            "is_active": True,
                            "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                            "created_at": "2026-01-20T14:20:00Z",
                        },
                    ]
                }
            },
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token",
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 100 requests per minute.",
                        "retry_after": 30,
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                    }
                }
            },
        },
    },
    tags=["targets"],
)
async def list_targets(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> list[TargetResponse]:
    """List deployment targets for the organization."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Listing targets for organization",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "organization_id": str(current_user.organization_id),
            "skip": skip,
            "limit": limit,
        },
    )
    targets = await TargetService.list_by_organization(
        session, current_user.organization_id, skip, limit
    )
    return [TargetResponse.model_validate(t) for t in targets]


@router.get(
    "/{target_id}",
    response_model=TargetResponse,
    status_code=status.HTTP_200_OK,
    summary="Get deployment target by ID",
    description="""
Retrieve detailed information about a specific deployment target.

## Features
- Get complete target configuration
- Includes connection details and credentials
- Organization-scoped access control

## Access Control
Users can only access targets belonging to their organization.
Attempting to access targets from other organizations returns 403 Forbidden.

## Use Cases
- View target configuration before deployment
- Verify target connectivity settings
- Check target capabilities and status

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        200: {
            "description": "Target retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "production-docker",
                        "type": "docker",
                        "host": "docker.prod.example.com",
                        "port": 2376,
                        "is_active": True,
                        "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                        "credentials": {
                            "tls_enabled": True,
                            "cert_path": "/etc/docker/certs",
                        },
                        "created_at": "2026-01-15T10:30:00Z",
                        "updated_at": "2026-01-20T08:15:00Z",
                    }
                }
            },
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token",
                    }
                }
            },
        },
        403: {
            "description": "Access denied to this target",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Accès refusé à cette cible",
                    }
                }
            },
        },
        404: {
            "description": "Target not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Cible 550e8400-e29b-41d4-a716-446655440000 non trouvée",
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 100 requests per minute.",
                        "retry_after": 30,
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                    }
                }
            },
        },
    },
    tags=["targets"],
)
async def get_target(
    request: Request,
    target_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> TargetResponse:
    """Retrieve a deployment target by ID."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting target {target_id}",
        extra={"correlation_id": correlation_id, "target_id": target_id},
    )
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée",
        )

    if target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé à cette cible"
        )

    return TargetResponse.model_validate(target)


@router.post(
    "/",
    response_model=TargetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new deployment target",
    description="""
Create a new deployment target for the organization.

## Process
1. Validates target configuration
2. Checks for name conflicts within organization
3. Creates target with provided credentials
4. Returns created target details

## Target Types
- **Docker**: Docker daemon connection (TCP/Unix socket)
- **SSH**: Remote server via SSH
- **Kubernetes**: K8s cluster connection
- **Docker Swarm**: Swarm cluster manager
- **Nomad**: HashiCorp Nomad cluster

## Credentials
Each target type requires specific credentials:
- Docker: TLS certificates or Unix socket path
- SSH: Username/password or SSH key
- Kubernetes: Kubeconfig or service account token

## Name Uniqueness
Target names must be unique within an organization.
Attempting to create a target with an existing name returns 409 Conflict.

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "docker_target": {
                            "summary": "Docker daemon target",
                            "description": "Connect to remote Docker daemon via TLS",
                            "value": {
                                "name": "production-docker",
                                "type": "docker",
                                "host": "docker.prod.example.com",
                                "port": 2376,
                                "credentials": {
                                    "tls_enabled": True,
                                    "ca_cert": "-----BEGIN CERTIFICATE-----\n...",
                                    "client_cert": "-----BEGIN CERTIFICATE-----\n...",
                                    "client_key": "-----BEGIN PRIVATE KEY-----\n...",
                                },
                            },
                        },
                        "ssh_target": {
                            "summary": "SSH remote server",
                            "description": "Connect to server via SSH",
                            "value": {
                                "name": "staging-server",
                                "type": "ssh",
                                "host": "staging.example.com",
                                "port": 22,
                                "credentials": {
                                    "username": "deploy",
                                    "ssh_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n...",
                                },
                            },
                        },
                        "kubernetes_target": {
                            "summary": "Kubernetes cluster",
                            "description": "Connect to K8s cluster",
                            "value": {
                                "name": "prod-k8s-cluster",
                                "type": "kubernetes",
                                "host": "k8s.prod.example.com",
                                "port": 6443,
                                "credentials": {
                                    "kubeconfig": "apiVersion: v1\nkind: Config\n..."
                                },
                            },
                        },
                        "local_docker": {
                            "summary": "Local Docker (Unix socket)",
                            "description": "Connect to local Docker daemon",
                            "value": {
                                "name": "local-docker",
                                "type": "docker",
                                "host": "unix:///var/run/docker.sock",
                                "port": 0,
                            },
                        },
                    }
                }
            }
        }
    },
    responses={
        201: {
            "description": "Target created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "production-docker",
                        "type": "docker",
                        "host": "docker.prod.example.com",
                        "port": 2376,
                        "is_active": True,
                        "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                        "created_at": "2026-02-02T21:50:00Z",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_type": {
                            "summary": "Invalid target type",
                            "value": {
                                "error": "Validation Error",
                                "detail": "Invalid target type: invalid_type",
                            },
                        },
                        "missing_credentials": {
                            "summary": "Missing credentials",
                            "value": {
                                "error": "Validation Error",
                                "detail": "Credentials required for target type: docker",
                            },
                        },
                    }
                }
            },
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token",
                    }
                }
            },
        },
        409: {
            "description": "Target name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Conflict",
                        "detail": "Cible avec le nom 'production-docker' existe déjà",
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 20 requests per minute.",
                        "retry_after": 30,
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                    }
                }
            },
        },
    },
    tags=["targets"],
)
async def create_target(
    request: Request,
    target_data: TargetCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> TargetResponse:
    """Create a new deployment target."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Creating target '{target_data.name}'",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "target_name": target_data.name,
        },
    )
    existing = await TargetService.get_by_name(
        session, current_user.organization_id, target_data.name
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cible avec le nom '{target_data.name}' existe déjà",
        )

    target = await TargetService.create(
        session, target_data, organization_id=current_user.organization_id
    )

    # Trigger initial health check so status is not stuck at default
    try:
        await TargetService.check_health(session, target)
        await session.refresh(target)
    except Exception as exc:
        logger.warning(
            "Initial health check failed for target %s: %s",
            target.id,
            exc,
        )

    return TargetResponse.model_validate(target)


@router.put(
    "/{target_id}",
    response_model=TargetResponse,
    status_code=status.HTTP_200_OK,
    summary="Update deployment target",
    description="""
Update an existing deployment target configuration.

## Features
- Partial updates supported (only send fields to change)
- Name uniqueness validation within organization
- Organization-scoped access control
- Credential updates with validation

## Update Scenarios
- Change target host or port
- Update credentials (certificates, keys, passwords)
- Modify target name (with uniqueness check)
- Enable/disable target

## Access Control
Users can only update targets belonging to their organization.
Attempting to update targets from other organizations returns 403 Forbidden.

## Name Conflicts
If updating the name, the new name must be unique within the organization.
Attempting to use an existing name returns 409 Conflict.

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(50, 60))],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "update_host": {
                            "summary": "Update host and port",
                            "description": "Change target connection details",
                            "value": {
                                "host": "docker-new.prod.example.com",
                                "port": 2377,
                            },
                        },
                        "update_credentials": {
                            "summary": "Update credentials",
                            "description": "Rotate certificates or keys",
                            "value": {
                                "credentials": {
                                    "tls_enabled": True,
                                    "ca_cert": "-----BEGIN CERTIFICATE-----\nNEW_CERT...",
                                    "client_cert": "-----BEGIN CERTIFICATE-----\nNEW_CERT...",
                                    "client_key": "-----BEGIN PRIVATE KEY-----\nNEW_KEY...",
                                }
                            },
                        },
                        "rename_target": {
                            "summary": "Rename target",
                            "description": "Change target name",
                            "value": {"name": "production-docker-v2"},
                        },
                        "disable_target": {
                            "summary": "Disable target",
                            "description": "Temporarily disable target",
                            "value": {"is_active": False},
                        },
                    }
                }
            }
        }
    },
    responses={
        200: {
            "description": "Target updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "production-docker-v2",
                        "type": "docker",
                        "host": "docker-new.prod.example.com",
                        "port": 2377,
                        "is_active": True,
                        "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                        "created_at": "2026-01-15T10:30:00Z",
                        "updated_at": "2026-02-02T21:50:00Z",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation Error",
                        "detail": "Invalid port number: must be between 1 and 65535",
                    }
                }
            },
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token",
                    }
                }
            },
        },
        403: {
            "description": "Access denied to this target",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Accès refusé à cette cible",
                    }
                }
            },
        },
        404: {
            "description": "Target not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Cible 550e8400-e29b-41d4-a716-446655440000 non trouvée",
                    }
                }
            },
        },
        409: {
            "description": "Target name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Conflict",
                        "detail": "Cible avec le nom 'production-docker-v2' existe déjà",
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 50 requests per minute.",
                        "retry_after": 30,
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "Erreur lors de la mise à jour de la cible",
                    }
                }
            },
        },
    },
    tags=["targets"],
)
async def update_target(
    request: Request,
    target_id: str,
    target_data: TargetUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> TargetResponse:
    """Update a deployment target."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Updating target {target_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "target_id": target_id,
        },
    )
    existing_target = await TargetService.get_by_id(session, target_id)
    if not existing_target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée",
        )

    if existing_target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé à cette cible"
        )

    if target_data.name and target_data.name != existing_target.name:
        existing_name = await TargetService.get_by_name(
            session, current_user.organization_id, target_data.name
        )
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cible avec le nom '{target_data.name}' existe déjà",
            )

    target = await TargetService.update(session, target_id, target_data)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la mise à jour de la cible",
        )
    return TargetResponse.model_validate(target)


@router.delete(
    "/{target_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete deployment target",
    description="""
Delete a deployment target permanently.

## Warning
This operation is irreversible. The target and all its configuration will be permanently deleted.

## Prerequisites
- Target must exist
- User must belong to target's organization
- No active deployments should be using this target (recommended)

## Access Control
Users can only delete targets belonging to their organization.
Attempting to delete targets from other organizations returns 403 Forbidden.

## Response
Returns 204 No Content on successful deletion (empty response body).

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
    responses={
        204: {"description": "Target deleted successfully (no content)"},
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token",
                    }
                }
            },
        },
        403: {
            "description": "Access denied to this target",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Accès refusé à cette cible",
                    }
                }
            },
        },
        404: {
            "description": "Target not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Cible 550e8400-e29b-41d4-a716-446655440000 non trouvée",
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 30 requests per minute.",
                        "retry_after": 30,
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                    }
                }
            },
        },
    },
    tags=["targets"],
)
async def delete_target(
    request: Request,
    target_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a deployment target permanently."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Deleting target {target_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "target_id": target_id,
        },
    )
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée",
        )

    if target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé à cette cible"
        )

    await TargetService.delete(session, target_id)
