"""
Routes de gestion des cibles de déploiement.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import get_current_active_user
from ...core.rate_limit import conditional_rate_limiter
from ...database import get_db
from ...models.user import User
from ...schemas.target import TargetResponse, TargetCreate, TargetUpdate, TargetType
from ...schemas.target_capability import CapabilityType, TargetCapabilityResponse
from ...schemas.target_scan import (
    ScanResult,
    TargetCapabilitiesResponse,
    TargetDiscoveryRequest,
    TargetDiscoveryResponse,
)
from ...services.target_scanner_service import TargetScannerService
from ...services.target_service import TargetService

router = APIRouter()
logger = logging.getLogger(__name__)

VIRTUALIZATION_CAPABILITY_TYPES: set[CapabilityType] = {
    CapabilityType.LIBVIRT,
    CapabilityType.VIRTUALBOX,
    CapabilityType.VAGRANT,
    CapabilityType.PROXMOX,
    CapabilityType.QEMU_KVM,
}


@router.get(
    "/",
    response_model=List[TargetResponse],
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
                            "created_at": "2026-01-15T10:30:00Z"
                        },
                        {
                            "id": "770e8400-e29b-41d4-a716-446655440002",
                            "name": "staging-k8s",
                            "type": "kubernetes",
                            "host": "k8s.staging.example.com",
                            "port": 6443,
                            "is_active": True,
                            "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                            "created_at": "2026-01-20T14:20:00Z"
                        }
                    ]
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 100 requests per minute.",
                        "retry_after": 30
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    },
    tags=["targets"]
)
async def list_targets(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> List[TargetResponse]:
    """List deployment targets for the organization."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Listing targets for organization",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "organization_id": str(current_user.organization_id),
            "skip": skip,
            "limit": limit
        }
    )
    targets = await TargetService.list_by_organization(
        session,
        current_user.organization_id,
        skip,
        limit
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
                            "cert_path": "/etc/docker/certs"
                        },
                        "created_at": "2026-01-15T10:30:00Z",
                        "updated_at": "2026-01-20T08:15:00Z"
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Access denied to this target",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Accès refusé à cette cible"
                    }
                }
            }
        },
        404: {
            "description": "Target not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Cible 550e8400-e29b-41d4-a716-446655440000 non trouvée"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 100 requests per minute.",
                        "retry_after": 30
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    },
    tags=["targets"]
)
async def get_target(
    request: Request,
    target_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> TargetResponse:
    """Retrieve a deployment target by ID."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting target {target_id}",
        extra={"correlation_id": correlation_id, "target_id": target_id}
    )
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    if target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
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
                                    "client_key": "-----BEGIN PRIVATE KEY-----\n..."
                                }
                            }
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
                                    "ssh_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n..."
                                }
                            }
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
                                }
                            }
                        },
                        "local_docker": {
                            "summary": "Local Docker (Unix socket)",
                            "description": "Connect to local Docker daemon",
                            "value": {
                                "name": "local-docker",
                                "type": "docker",
                                "host": "unix:///var/run/docker.sock",
                                "port": 0
                            }
                        }
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
                        "created_at": "2026-02-02T21:50:00Z"
                    }
                }
            }
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
                                "detail": "Invalid target type: invalid_type"
                            }
                        },
                        "missing_credentials": {
                            "summary": "Missing credentials",
                            "value": {
                                "error": "Validation Error",
                                "detail": "Credentials required for target type: docker"
                            }
                        }
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        409: {
            "description": "Target name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Conflict",
                        "detail": "Cible avec le nom 'production-docker' existe déjà"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 20 requests per minute.",
                        "retry_after": 30
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    },
    tags=["targets"]
)
async def create_target(
    request: Request,
    target_data: TargetCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> TargetResponse:
    """Create a new deployment target."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Creating target '{target_data.name}'",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "target_name": target_data.name
        }
    )
    existing = await TargetService.get_by_name(
        session,
        current_user.organization_id,
        target_data.name
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cible avec le nom '{target_data.name}' existe déjà"
        )

    target = await TargetService.create(
        session,
        target_data,
        organization_id=current_user.organization_id
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
                                "port": 2377
                            }
                        },
                        "update_credentials": {
                            "summary": "Update credentials",
                            "description": "Rotate certificates or keys",
                            "value": {
                                "credentials": {
                                    "tls_enabled": True,
                                    "ca_cert": "-----BEGIN CERTIFICATE-----\nNEW_CERT...",
                                    "client_cert": "-----BEGIN CERTIFICATE-----\nNEW_CERT...",
                                    "client_key": "-----BEGIN PRIVATE KEY-----\nNEW_KEY..."
                                }
                            }
                        },
                        "rename_target": {
                            "summary": "Rename target",
                            "description": "Change target name",
                            "value": {
                                "name": "production-docker-v2"
                            }
                        },
                        "disable_target": {
                            "summary": "Disable target",
                            "description": "Temporarily disable target",
                            "value": {
                                "is_active": False
                            }
                        }
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
                        "updated_at": "2026-02-02T21:50:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation Error",
                        "detail": "Invalid port number: must be between 1 and 65535"
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Access denied to this target",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Accès refusé à cette cible"
                    }
                }
            }
        },
        404: {
            "description": "Target not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Cible 550e8400-e29b-41d4-a716-446655440000 non trouvée"
                    }
                }
            }
        },
        409: {
            "description": "Target name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Conflict",
                        "detail": "Cible avec le nom 'production-docker-v2' existe déjà"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 50 requests per minute.",
                        "retry_after": 30
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "Erreur lors de la mise à jour de la cible"
                    }
                }
            }
        }
    },
    tags=["targets"]
)
async def update_target(
    request: Request,
    target_id: str,
    target_data: TargetUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> TargetResponse:
    """Update a deployment target."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Updating target {target_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "target_id": target_id
        }
    )
    existing_target = await TargetService.get_by_id(session, target_id)
    if not existing_target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    if existing_target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
        )

    if target_data.name and target_data.name != existing_target.name:
        existing_name = await TargetService.get_by_name(
            session,
            current_user.organization_id,
            target_data.name
        )
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cible avec le nom '{target_data.name}' existe déjà"
            )

    target = await TargetService.update(session, target_id, target_data)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la mise à jour de la cible"
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
        204: {
            "description": "Target deleted successfully (no content)"
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Access denied to this target",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Accès refusé à cette cible"
                    }
                }
            }
        },
        404: {
            "description": "Target not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Cible 550e8400-e29b-41d4-a716-446655440000 non trouvée"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 30 requests per minute.",
                        "retry_after": 30
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    },
    tags=["targets"]
)
async def delete_target(
    request: Request,
    target_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> None:
    """Delete a deployment target permanently."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Deleting target {target_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "target_id": target_id
        }
    )
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    if target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
        )

    await TargetService.delete(session, target_id)


@router.post(
    "/discover",
    response_model=TargetDiscoveryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Discover and create deployment target",
    description="""
Automatically discover target capabilities and create a new deployment target.

## Process
1. Connects to the target machine (localhost or remote via SSH)
2. Scans for available capabilities (Docker, Kubernetes, virtualization, etc.)
3. Detects OS, platform, and system information
4. Infers optimal target type based on discovered capabilities
5. Creates target with discovered configuration
6. Returns target details with complete scan results

## Discovery Methods
- **Localhost**: Scans the local machine where WindFlow is running
- **Remote SSH**: Connects via SSH to scan remote servers

## Discovered Capabilities
- Docker daemon and Docker Compose
- Kubernetes (kubectl, kubeconfig)
- Virtualization (libvirt, VirtualBox, Vagrant, Proxmox, QEMU/KVM)
- Container runtimes (containerd, podman)
- Orchestration tools (Docker Swarm, Nomad)

## Target Type Inference
If no preferred type is specified, the system automatically selects:
- **Docker**: If Docker daemon is available
- **Kubernetes**: If kubectl and kubeconfig are found
- **SSH**: Fallback for general remote access

## Use Cases
- Quick onboarding of new deployment targets
- Automated infrastructure discovery
- Capability assessment before deployment

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "discover_localhost": {
                            "summary": "Discover localhost",
                            "description": "Scan local machine capabilities",
                            "value": {
                                "name": "local-machine",
                                "host": "localhost",
                                "port": 22,
                                "description": "Local development machine"
                            }
                        },
                        "discover_remote_ssh": {
                            "summary": "Discover remote server via SSH",
                            "description": "Scan remote server with SSH credentials",
                            "value": {
                                "name": "production-server",
                                "host": "prod.example.com",
                                "port": 22,
                                "username": "deploy",
                                "password": "SecurePassword123!",
                                "description": "Production deployment server"
                            }
                        },
                        "discover_with_sudo": {
                            "summary": "Discover with sudo access",
                            "description": "Scan with elevated privileges",
                            "value": {
                                "name": "staging-server",
                                "host": "staging.example.com",
                                "port": 22,
                                "username": "deploy",
                                "password": "Password123!",
                                "sudo_user": "root",
                                "sudo_password": "RootPassword456!",
                                "description": "Staging server with sudo"
                            }
                        },
                        "discover_preferred_type": {
                            "summary": "Discover with preferred type",
                            "description": "Force specific target type",
                            "value": {
                                "name": "k8s-cluster",
                                "host": "k8s.example.com",
                                "port": 22,
                                "username": "admin",
                                "password": "AdminPass789!",
                                "preferred_type": "kubernetes",
                                "description": "Kubernetes cluster"
                            }
                        }
                    }
                }
            }
        }
    },
    responses={
        201: {
            "description": "Target discovered and created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "target": {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "name": "production-server",
                            "type": "docker",
                            "host": "prod.example.com",
                            "port": 22,
                            "is_active": True,
                            "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                            "created_at": "2026-02-02T21:50:00Z"
                        },
                        "scan_result": {
                            "success": True,
                            "scan_date": "2026-02-02T21:50:00Z",
                            "capabilities": {
                                "docker": True,
                                "docker_compose": True,
                                "kubernetes": False,
                                "libvirt": False
                            },
                            "platform": {
                                "system": "Linux",
                                "release": "5.15.0-91-generic",
                                "machine": "x86_64"
                            },
                            "os": {
                                "name": "Ubuntu",
                                "version": "22.04",
                                "codename": "jammy"
                            }
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "examples": {
                        "connection_failed": {
                            "summary": "Connection failed",
                            "value": {
                                "error": "Connection Error",
                                "detail": "Failed to connect to host: Connection refused"
                            }
                        },
                        "authentication_failed": {
                            "summary": "Authentication failed",
                            "value": {
                                "error": "Authentication Error",
                                "detail": "SSH authentication failed: Invalid credentials"
                            }
                        }
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Impossible de découvrir une cible pour une autre organisation"
                    }
                }
            }
        },
        409: {
            "description": "Target name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Conflict",
                        "detail": "Cible avec le nom 'production-server' existe déjà"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 10 requests per minute.",
                        "retry_after": 30
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred during discovery"
                    }
                }
            }
        }
    },
    tags=["targets"]
)
async def discover_target(
    request: Request,
    discovery_request: TargetDiscoveryRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> TargetDiscoveryResponse:
    """Discover target capabilities and create deployment target."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Discovering target at {discovery_request.host}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "host": discovery_request.host
        }
    )
    organization_id = discovery_request.organization_id or current_user.organization_id
    if organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Impossible de découvrir une cible pour une autre organisation"
        )

    existing = await TargetService.get_by_name(session, organization_id, discovery_request.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cible avec le nom '{discovery_request.name}' existe déjà"
        )

    scanner = TargetScannerService()
    host = discovery_request.host
    is_localhost = host in {"localhost", "127.0.0.1"}

    scan_result = await (
        scanner.scan_localhost()
        if is_localhost
        else scanner.scan_remote(discovery_request)
    )

    target_type = discovery_request.preferred_type or _infer_target_type(scan_result)

    credentials = {
        "username": discovery_request.username,
        "password": discovery_request.password,
    }
    if discovery_request.sudo_user:
        credentials["sudo_user"] = discovery_request.sudo_user
    if discovery_request.sudo_password:
        credentials["sudo_password"] = discovery_request.sudo_password

    target_payload = TargetCreate(
        name=discovery_request.name,
        description=discovery_request.description,
        host=discovery_request.host,
        port=discovery_request.port,
        type=target_type,
        credentials=credentials,
        organization_id=organization_id,
        extra_metadata={
            "auto_discovered": True,
            "discovery_date": scan_result.scan_date.isoformat(),
            "source": "target_discovery_endpoint",
        },
    )

    target = await TargetService.create(
        session,
        target_payload,
        organization_id=organization_id
    )

    capabilities_payload = scanner.build_capabilities_payload(scan_result)
    platform_payload = (
        scan_result.platform.model_dump(mode="json")
        if scan_result.platform
        else None
    )
    os_payload = (
        scan_result.os.model_dump(mode="json")
        if scan_result.os
        else None
    )

    await TargetService.apply_scan_result(
        db=session,
        target=target,
        capabilities=capabilities_payload,
        scan_date=scan_result.scan_date,
        success=scan_result.success,
        platform_info=platform_payload,
        os_info=os_payload,
    )

    return TargetDiscoveryResponse(
        target=TargetResponse.model_validate(target),
        scan_result=scan_result
    )


@router.post(
    "/{target_id}/scan",
    response_model=TargetResponse,
    status_code=status.HTTP_200_OK,
    summary="Scan target capabilities",
    description="""
Scan or rescan an existing target to update its capabilities.

## Process
1. Connects to the target using stored credentials
2. Scans for available capabilities
3. Updates target's capability information
4. Returns updated target details

## Use Cases
- Refresh capabilities after software installation
- Verify target configuration changes
- Update capability status after system updates
- Periodic capability audits

## Detected Capabilities
- Docker daemon and Docker Compose
- Kubernetes (kubectl, kubeconfig)
- Virtualization platforms (libvirt, VirtualBox, etc.)
- Container runtimes
- Orchestration tools

## Access Control
Users can only scan targets belonging to their organization.

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    responses={
        200: {
            "description": "Target scanned successfully",
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
                        "scan_date": "2026-02-02T21:50:00Z",
                        "scan_success": True,
                        "created_at": "2026-01-15T10:30:00Z",
                        "updated_at": "2026-02-02T21:50:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Scan failed",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Scan Error",
                        "detail": "Failed to connect to target for scanning"
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Access denied to this target",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Accès refusé à cette cible"
                    }
                }
            }
        },
        404: {
            "description": "Target not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Cible 550e8400-e29b-41d4-a716-446655440000 non trouvée"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 20 requests per minute.",
                        "retry_after": 30
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred during scan"
                    }
                }
            }
        }
    },
    tags=["targets"]
)
async def scan_target(
    request: Request,
    target_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> TargetResponse:
    """Scan target capabilities and update information."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Scanning target {target_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "target_id": target_id
        }
    )
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    if target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
        )

    scanner = TargetScannerService()
    updated_target = await scanner.scan_and_update_target(target, session)
    return TargetResponse.model_validate(updated_target)


@router.get(
    "/{target_id}/capabilities",
    response_model=TargetCapabilitiesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get target capabilities",
    description="""
Retrieve all capabilities detected for a specific target.

## Features
- Returns complete capability information
- Optional filtering by capability type
- Includes platform and OS information
- Shows last scan date and status

## Capability Types
- **Docker**: Docker daemon availability
- **Docker Compose**: Docker Compose support
- **Kubernetes**: kubectl and cluster access
- **Libvirt**: KVM/QEMU virtualization
- **VirtualBox**: VirtualBox hypervisor
- **Vagrant**: Vagrant tool
- **Proxmox**: Proxmox VE platform
- **QEMU/KVM**: Direct QEMU/KVM access

## Query Parameters
- `capability_type`: Optional filter to return only specific capability type

## Use Cases
- Check available deployment options
- Verify target readiness
- Plan deployment strategies
- Audit infrastructure capabilities

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        200: {
            "description": "Capabilities retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "scan_date": "2026-02-02T21:50:00Z",
                        "scan_success": True,
                        "platform_info": {
                            "system": "Linux",
                            "release": "5.15.0-91-generic",
                            "machine": "x86_64"
                        },
                        "os_info": {
                            "name": "Ubuntu",
                            "version": "22.04",
                            "codename": "jammy"
                        },
                        "capabilities": [
                            {
                                "type": "docker",
                                "available": True,
                                "version": "24.0.7",
                                "details": {
                                    "api_version": "1.43",
                                    "socket": "/var/run/docker.sock"
                                }
                            },
                            {
                                "type": "docker_compose",
                                "available": True,
                                "version": "2.23.0"
                            },
                            {
                                "type": "kubernetes",
                                "available": False
                            }
                        ]
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Access denied to this target",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Accès refusé à cette cible"
                    }
                }
            }
        },
        404: {
            "description": "Target not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Cible 550e8400-e29b-41d4-a716-446655440000 non trouvée"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 100 requests per minute.",
                        "retry_after": 30
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    },
    tags=["targets"]
)
async def get_target_capabilities(
    request: Request,
    target_id: str,
    capability_type: Optional[CapabilityType] = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> TargetCapabilitiesResponse:
    """Retrieve target capabilities with optional filtering."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting capabilities for target {target_id}",
        extra={"correlation_id": correlation_id, "target_id": target_id}
    )
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    if target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
        )

    capabilities = await TargetService.list_capabilities(
        db=session,
        target_id=target.id,
        capability_type=capability_type
    )

    return TargetCapabilitiesResponse(
        scan_date=target.scan_date,
        scan_success=target.scan_success,
        platform_info=target.platform_info,
        os_info=target.os_info,
        capabilities=[
            TargetCapabilityResponse.model_validate(capability)
            for capability in capabilities
        ],
    )


@router.get(
    "/{target_id}/capabilities/{capability_type}",
    response_model=TargetCapabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Get specific target capability",
    description="""
Retrieve a specific capability by type for a target.

## Features
- Returns detailed information for a single capability
- Includes version and configuration details
- Shows availability status

## Capability Types
Available capability types to query:
- `docker` - Docker daemon
- `docker_compose` - Docker Compose
- `kubernetes` - Kubernetes cluster
- `libvirt` - Libvirt/KVM
- `virtualbox` - VirtualBox
- `vagrant` - Vagrant
- `proxmox` - Proxmox VE
- `qemu_kvm` - QEMU/KVM

## Use Cases
- Check if specific capability is available
- Get version information for a tool
- Verify deployment prerequisites
- Validate target compatibility

## Error Handling
Returns 404 if the capability type is not found for the target.

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        200: {
            "description": "Capability retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "type": "docker",
                        "available": True,
                        "version": "24.0.7",
                        "details": {
                            "api_version": "1.43",
                            "socket": "/var/run/docker.sock",
                            "root_dir": "/var/lib/docker"
                        }
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Access denied to this target",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Accès refusé à cette cible"
                    }
                }
            }
        },
        404: {
            "description": "Target or capability not found",
            "content": {
                "application/json": {
                    "examples": {
                        "target_not_found": {
                            "summary": "Target not found",
                            "value": {
                                "error": "Not Found",
                                "detail": "Cible 550e8400-e29b-41d4-a716-446655440000 non trouvée"
                            }
                        },
                        "capability_not_found": {
                            "summary": "Capability not found",
                            "value": {
                                "error": "Not Found",
                                "detail": "Capacité kubernetes non trouvée pour cette cible"
                            }
                        }
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 100 requests per minute.",
                        "retry_after": 30
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    },
    tags=["targets"]
)
async def get_target_capability_by_type(
    request: Request,
    target_id: str,
    capability_type: CapabilityType,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> TargetCapabilityResponse:
    """Retrieve a specific capability by type for a target."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting capability {capability_type} for target {target_id}",
        extra={"correlation_id": correlation_id, "target_id": target_id, "capability_type": str(capability_type)}
    )
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    if target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
        )

    capabilities = await TargetService.list_capabilities(
        db=session,
        target_id=target.id,
        capability_type=capability_type
    )

    if not capabilities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capacité {capability_type.value} non trouvée pour cette cible"
        )

    return TargetCapabilityResponse.model_validate(capabilities[0])


@router.get(
    "/{target_id}/capabilities/virtualization",
    response_model=List[TargetCapabilityResponse],
    status_code=status.HTTP_200_OK,
    summary="Get target virtualization capabilities",
    description="""
Retrieve only virtualization-related capabilities for a target.

## Features
- Filters capabilities to show only virtualization platforms
- Returns detailed information for each virtualization tool
- Useful for VM deployment planning

## Virtualization Capabilities
This endpoint returns only these capability types:
- **Libvirt**: KVM/QEMU via libvirt
- **VirtualBox**: Oracle VirtualBox hypervisor
- **Vagrant**: HashiCorp Vagrant
- **Proxmox**: Proxmox Virtual Environment
- **QEMU/KVM**: Direct QEMU/KVM access

## Use Cases
- Check available VM platforms
- Plan virtual machine deployments
- Verify hypervisor availability
- Select optimal virtualization platform

## Response
Returns an array of virtualization capabilities, which may be empty if no virtualization platforms are detected.

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        200: {
            "description": "Virtualization capabilities retrieved successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "with_capabilities": {
                            "summary": "Target with virtualization",
                            "value": [
                                {
                                    "type": "libvirt",
                                    "available": True,
                                    "version": "8.0.0",
                                    "details": {
                                        "uri": "qemu:///system",
                                        "hypervisor": "QEMU"
                                    }
                                },
                                {
                                    "type": "virtualbox",
                                    "available": True,
                                    "version": "7.0.12"
                                }
                            ]
                        },
                        "no_capabilities": {
                            "summary": "No virtualization detected",
                            "value": []
                        }
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Access denied to this target",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Accès refusé à cette cible"
                    }
                }
            }
        },
        404: {
            "description": "Target not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Cible 550e8400-e29b-41d4-a716-446655440000 non trouvée"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 100 requests per minute.",
                        "retry_after": 30
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred"
                    }
                }
            }
        }
    },
    tags=["targets"]
)
async def get_target_virtualization_capabilities(
    request: Request,
    target_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> List[TargetCapabilityResponse]:
    """Retrieve virtualization capabilities for a target."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting virtualization capabilities for target {target_id}",
        extra={"correlation_id": correlation_id, "target_id": target_id}
    )
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    if target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
        )

    capabilities = await TargetService.list_capabilities(db=session, target_id=target.id)

    virtualization_capabilities = [
        TargetCapabilityResponse.model_validate(capability)
        for capability in capabilities
        if capability.capability_type in VIRTUALIZATION_CAPABILITY_TYPES
    ]
    return virtualization_capabilities


def _infer_target_type(scan_result: ScanResult) -> TargetType:
    """
    Déduit le type de cible à partir des capacités détectées.
    """
    docker_caps = scan_result.docker
    if docker_caps and docker_caps.swarm and docker_caps.swarm.available:
        return TargetType.DOCKER_SWARM
    if docker_caps and docker_caps.installed:
        return TargetType.DOCKER

    if any(tool.available for tool in scan_result.kubernetes.values()):
        return TargetType.KUBERNETES

    if any(tool.available for tool in scan_result.virtualization.values()):
        return TargetType.VM

    return TargetType.PHYSICAL
