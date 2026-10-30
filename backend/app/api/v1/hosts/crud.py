"""Opérations CRUD sur les cibles de déploiement."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....auth.rbac import require_admin, require_viewer
from ....core.exceptions import (
    ConflictError,
    InvalidInputError,
    NotFoundError,
    PermissionDeniedError,
    WindFlowException,
)
from ....core.rate_limit import conditional_rate_limiter
from ....database import get_db
from ....helper.pagination import PaginationQuery, build_meta
from ....models.user import User
from ....schemas.common import PaginatedResponse
from ....schemas.host import (
    HostCreateRequest,
    HostResponse,
    HostUpdate,
)
from ....services.audit_service import AuditService
from ....services.host_service import HostService
from ....services.user_organization_service import UserOrganizationService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/",
    response_model=PaginatedResponse,
    status_code=status.HTTP_200_OK,
    summary="List deployment hosts",
    description="""
List all deployment hosts for the current user's organizations.

## Features
- **Pagination**: `?page=1&per_page=20` (max 100) — STORY-128 canonical format,
  response envelope `PaginatedResponse{data, pagination{page, per_page, total, pages}}`
- **Organization-scoped access**: users only see their orgs' hosts
  (single scoped query, no per-org paging)
- Returns all host types (Docker, SSH, Kubernetes, etc.)
- **Stable order**: `ORDER BY name` — no duplicates/holes across pages

## Host Types
- **Docker**: Docker daemon hosts
- **SSH**: Remote SSH servers
- **Kubernetes**: K8s clusters
- **Docker Swarm**: Swarm clusters
- **Nomad**: HashiCorp Nomad clusters

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        200: {
            "description": ("Paginated list of hosts — enveloppe spec 09"),
            "content": {
                "application/json": {
                    "example": {
                        "data": [
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
                        ],
                        "pagination": {
                            "page": 1,
                            "per_page": 20,
                            "total": 42,
                            "pages": 3,
                        },
                        "message": None,
                    }
                }
            },
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INVALID_OR_EXPIRED_TOKEN",
                            "message": "Missing or invalid authentication token",
                        }
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
    tags=["hosts"],
)
async def list_hosts(
    request: Request,
    page: int = PaginationQuery.page,
    per_page: int = PaginationQuery.per_page,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """Liste paginée des cibles de déploiement (STORY-128).

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — matrice spec 08 :
    « Lister les hosts » = tous les rôles) + scoping par organisation.
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Listing hosts for user organizations",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "page": page,
            "per_page": per_page,
        },
    )
    # STORY-121.3 : scoping sur les organisations de l'utilisateur
    # (appartenances via l'association ; STORY-128 : requête unique IN)
    org_ids = await UserOrganizationService.get_user_organization_ids(
        session, current_user
    )
    hosts = await HostService.list_by_organizations(
        session, org_ids, page=page, per_page=per_page
    )
    total = await HostService.count_by_organizations(session, org_ids)

    data: List[dict] = [HostResponse.model_validate(h).model_dump() for h in hosts]
    return PaginatedResponse(data=data, pagination=build_meta(page, per_page, total))


@router.get(
    "/{host_id}",
    response_model=HostResponse,
    status_code=status.HTTP_200_OK,
    summary="Get deployment host by ID",
    description="""
Retrieve detailed information about a specific deployment host.

## Features
- Get complete host configuration
- Includes connection details and credentials
- Organization-scoped access control

## Access Control
Users can only access hosts belonging to their organization.
Attempting to access hosts from other organizations returns 403 Forbidden.

## Use Cases
- View host configuration before deployment
- Verify host connectivity settings
- Check host capabilities and status

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        200: {
            "description": "Host retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "production-docker",
                        "profile": "host_remote_docker",
                        "type": "docker",
                        "host": "docker.prod.example.com",
                        "port": 2376,
                        "status": "online",
                        "hardware_info": {"system": "Linux", "machine": "x86_64"},
                        "installed_engines": [
                            {
                                "capability_type": "docker",
                                "version": "24.0.7",
                                "is_available": True,
                            }
                        ],
                        "last_scan_at": "2026-01-18T09:00:00Z",
                        "origin": "managed",
                        "auth_method": "ssh_key",
                        "username": "deploy",
                        "has_sudo": False,
                        "ssh_key_id": None,
                        "organization_id": "660e8400-e29b-41d4-a716-446655440001",
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
            "description": "Access denied to this host",
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
            "description": "Host not found",
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
    tags=["hosts"],
)
async def get_host(
    request: Request,
    host_id: str,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_db),
) -> HostResponse:
    """Retrieve a deployment host by ID.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — matrice spec 08)
    + isolation par organisation (``is_member``).
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting host {host_id}",
        extra={"correlation_id": correlation_id, "host_id": host_id},
    )
    host = await HostService.get_by_id(session, host_id)
    if not host:
        raise NotFoundError(f"Cible {host_id} non trouvée")

    if not await UserOrganizationService.is_member(
        session, current_user, host.organization_id
    ):
        raise PermissionDeniedError("Accès refusé à cette cible")

    return HostResponse.model_validate(host)


@router.post(
    "/",
    response_model=HostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new deployment host",
    description="""
Create a new deployment host for the organization.

## Process
1. Validates host configuration
2. Checks for name conflicts within organization
3. Creates host with provided credentials
4. Returns created host details

## Host Types
- **Docker**: Docker daemon connection (TCP/Unix socket)
- **SSH**: Remote server via SSH
- **Kubernetes**: K8s cluster connection
- **Docker Swarm**: Swarm cluster manager
- **Nomad**: HashiCorp Nomad cluster

## Credentials
Each host type requires specific credentials:
- Docker: TLS certificates or Unix socket path
- SSH: Username/password or SSH key
- Kubernetes: Kubeconfig or service account token

## Name Uniqueness
Host names must be unique within an organization.
Attempting to create a host with an existing name returns 409 Conflict.

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "docker_target": {
                            "summary": "Docker daemon host",
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
            "description": "Host created successfully",
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
                            "summary": "Invalid host type",
                            "value": {
                                "error": "Validation Error",
                                "detail": "Invalid host type: invalid_type",
                            },
                        },
                        "missing_credentials": {
                            "summary": "Missing credentials",
                            "value": {
                                "error": "Validation Error",
                                "detail": "Credentials required for host type: docker",
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
            "description": "Host name already exists",
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
    tags=["hosts"],
)
async def create_host(
    request: Request,
    host_data: HostCreateRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> HostResponse:
    """Create a new deployment host.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``admin`` minimum (matrice spec 08 :
    « Ajouter un host » = Admin+).
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Creating host '{host_data.name}'",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "host_name": host_data.name,
        },
    )
    # STORY-121.3 : organisation primaire de l'utilisateur
    primary_org = await UserOrganizationService.get_primary_organization_id(
        session, current_user
    )
    if primary_org is None:
        raise InvalidInputError("Aucune organisation : rattachez d'abord votre compte")
    existing = await HostService.get_by_name(session, primary_org, host_data.name)
    if existing:
        raise ConflictError(f"Cible avec le nom '{host_data.name}' existe déjà")

    host = await HostService.create(session, host_data, organization_id=primary_org)

    # Trigger initial health check so status is not stuck at default
    try:
        await HostService.check_health(session, host)
        await session.refresh(host)
    except Exception as exc:
        logger.warning(
            "Initial health check failed for host %s: %s",
            host.id,
            exc,
        )

    # STORY-162 (AC 3) : événement canonique ``host.added`` — émission
    # best-effort post-commit (try/except : n'altère jamais la réponse
    # API) ; payload strictement sans secret ni matériel de clé SSH
    # (rules 40 — IDs/nom/type uniquement).
    try:
        from ....core.events import EventType, get_event_bus

        await get_event_bus().emit(
            EventType.HOST_ADDED,
            {
                "host_id": str(host.id),
                "name": host.name,
                "profile": host.profile.value if host.profile else None,
                "engines": [],  # capacités non détectées à la création
                "organization_id": str(host.organization_id),
            },
        )
    except Exception as exc:  # best-effort : jamais bloquant
        logger.warning("host.added event emission failed: %s", exc)

    return HostResponse.model_validate(host)


@router.put(
    "/{host_id}",
    response_model=HostResponse,
    status_code=status.HTTP_200_OK,
    summary="Update deployment host",
    description="""
Update an existing deployment host configuration.

## Features
- Partial updates supported (only send fields to change)
- Name uniqueness validation within organization
- Organization-scoped access control
- Credential updates with validation

## Update Scenarios
- Change host host or port
- Update credentials (certificates, keys, passwords)
- Modify host name (with uniqueness check)
- Enable/disable host

## Access Control
Users can only update hosts belonging to their organization.
Attempting to update hosts from other organizations returns 403 Forbidden.

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
                            "description": "Change host connection details",
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
                            "summary": "Rename host",
                            "description": "Change host name",
                            "value": {"name": "production-docker-v2"},
                        },
                        "disable_target": {
                            "summary": "Disable host",
                            "description": "Temporarily disable host",
                            "value": {"is_active": False},
                        },
                    }
                }
            }
        }
    },
    responses={
        200: {
            "description": "Host updated successfully",
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
            "description": "Access denied to this host",
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
            "description": "Host not found",
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
            "description": "Host name already exists",
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
    tags=["hosts"],
)
async def update_host(
    request: Request,
    host_id: str,
    host_data: HostUpdate,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> HostResponse:
    """Update a deployment host.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``admin`` minimum (matrice spec 08 — gestion
    host) + isolation par organisation (``is_member``).
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Updating host {host_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "host_id": host_id,
        },
    )
    existing = await HostService.get_by_id(session, host_id)
    if not existing:
        raise NotFoundError(f"Cible {host_id} non trouvée")

    if not await UserOrganizationService.is_member(
        session, current_user, existing.organization_id
    ):
        raise PermissionDeniedError("Accès refusé à cette cible")

    if host_data.name and host_data.name != existing.name:
        # STORY-121.3 : unicité vérifiée dans l'organisation de la cible
        existing_name = await HostService.get_by_name(
            session, existing.organization_id, host_data.name
        )
        if existing_name:
            raise ConflictError(f"Cible avec le nom '{host_data.name}' existe déjà")

    updated = await HostService.update(session, host_id, host_data)
    if updated is None:
        raise WindFlowException("Erreur lors de la mise à jour de la cible")
    return HostResponse.model_validate(updated)


@router.delete(
    "/{host_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete deployment host",
    description="""
Delete a deployment host permanently.

## Warning
This operation is irreversible. The host and all its configuration will be permanently deleted.

## Prerequisites
- Host must exist
- User must belong to host's organization
- No active deployments should be using this host (recommended)

## Access Control
Users can only delete hosts belonging to their organization.
Attempting to delete hosts from other organizations returns 403 Forbidden.

## Response
Returns 204 No Content on successful deletion (empty response body).

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
    responses={
        204: {"description": "Host deleted successfully (no content)"},
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
            "description": "Access denied to this host",
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
            "description": "Host not found",
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
    tags=["hosts"],
)
async def delete_host(
    request: Request,
    host_id: str,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a deployment host permanently.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``admin`` minimum (matrice spec 08 :
    « Supprimer un host » = Admin+) + isolation par organisation.
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Deleting host {host_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "host_id": host_id,
        },
    )
    host = await HostService.get_by_id(session, host_id)
    if not host:
        raise NotFoundError(f"Cible {host_id} non trouvée")

    if not await UserOrganizationService.is_member(
        session, current_user, host.organization_id
    ):
        raise PermissionDeniedError("Accès refusé à cette cible")

    await HostService.delete(session, host_id)

    # STORY-125.2 : audit de la suppression (après succès, org du host).
    # STORY-166.2 : action alignée sur la nomenclature canonique
    # ``host.removed`` + ``resource_type="host"`` — vérification
    # consommateurs faite (2026-10-29) : aucun dashboard Grafana ni
    # consommateur métier ne filtre sur l'ancienne valeur
    # ``host.deleted`` (seul ``test_audit_emission.py`` l'assertait,
    # mis à jour dans la même story) ; l'audit trail existant reste
    # lisible (l'action historique est conservée en base).
    await AuditService.log_from_request(
        request,
        "host.removed",
        user=current_user,
        organization_id=host.organization_id,
        resource_type="host",
        resource_id=host_id,
        details={"name": host.name},
    )

    # STORY-162 (AC 3) : événement canonique ``host.removed`` — best-effort
    # post-commit (n'altère jamais la réponse API) ; payload sans secret
    # (rules 40 — IDs/nom uniquement).
    try:
        from ....core.events import EventType, get_event_bus

        await get_event_bus().emit(
            EventType.HOST_REMOVED,
            {
                "host_id": str(host.id),
                "name": host.name,
            },
        )
    except Exception as exc:  # best-effort : jamais bloquant
        logger.warning("host.removed event emission failed: %s", exc)
