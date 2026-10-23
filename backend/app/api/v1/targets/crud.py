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
from ....schemas.target import (
    TargetCreate,
    TargetResponse,
    TargetUpdate,
)
from ....services.audit_service import AuditService
from ....services.target_service import TargetService
from ....services.user_organization_service import UserOrganizationService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/",
    response_model=PaginatedResponse,
    status_code=status.HTTP_200_OK,
    summary="List deployment targets",
    description="""
List all deployment targets for the current user's organizations.

## Features
- **Pagination**: `?page=1&per_page=20` (max 100) — STORY-128 canonical format,
  response envelope `PaginatedResponse{data, pagination{page, per_page, total, pages}}`
- **Organization-scoped access**: users only see their orgs' targets
  (single scoped query, no per-org paging)
- Returns all target types (Docker, SSH, Kubernetes, etc.)
- **Stable order**: `ORDER BY name` — no duplicates/holes across pages

## Target Types
- **Docker**: Docker daemon targets
- **SSH**: Remote SSH servers
- **Kubernetes**: K8s clusters
- **Docker Swarm**: Swarm clusters
- **Nomad**: HashiCorp Nomad clusters

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        200: {
            "description": ("Paginated list of targets — enveloppe spec 09"),
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
    tags=["targets"],
)
async def list_targets(
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
        "Listing targets for user organizations",
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
    targets = await TargetService.list_by_organizations(
        session, org_ids, page=page, per_page=per_page
    )
    total = await TargetService.count_by_organizations(session, org_ids)

    data: List[dict] = [TargetResponse.model_validate(t).model_dump() for t in targets]
    return PaginatedResponse(data=data, pagination=build_meta(page, per_page, total))


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
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_db),
) -> TargetResponse:
    """Retrieve a deployment target by ID.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — matrice spec 08)
    + isolation par organisation (``is_member``).
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting target {target_id}",
        extra={"correlation_id": correlation_id, "target_id": target_id},
    )
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise NotFoundError(f"Cible {target_id} non trouvée")

    if not await UserOrganizationService.is_member(
        session, current_user, target.organization_id
    ):
        raise PermissionDeniedError("Accès refusé à cette cible")

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
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> TargetResponse:
    """Create a new deployment target.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``admin`` minimum (matrice spec 08 :
    « Ajouter un host » = Admin+).
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Creating target '{target_data.name}'",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "target_name": target_data.name,
        },
    )
    # STORY-121.3 : organisation primaire de l'utilisateur
    primary_org = await UserOrganizationService.get_primary_organization_id(
        session, current_user
    )
    if primary_org is None:
        raise InvalidInputError("Aucune organisation : rattachez d'abord votre compte")
    existing = await TargetService.get_by_name(session, primary_org, target_data.name)
    if existing:
        raise ConflictError(f"Cible avec le nom '{target_data.name}' existe déjà")

    target = await TargetService.create(
        session, target_data, organization_id=primary_org
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

    # STORY-162 (AC 3) : événement canonique ``host.added`` — émission
    # best-effort post-commit (try/except : n'altère jamais la réponse
    # API) ; payload strictement sans secret ni matériel de clé SSH
    # (rules 40 — IDs/nom/type uniquement).
    try:
        from ....core.events import EventType, get_event_bus

        await get_event_bus().emit(
            EventType.HOST_ADDED,
            {
                "host_id": str(target.id),
                "name": target.name,
                "profile": target.type.value if target.type else None,
                "engines": [],  # capacités non détectées à la création
                "organization_id": str(target.organization_id),
            },
        )
    except Exception as exc:  # best-effort : jamais bloquant
        logger.warning("host.added event emission failed: %s", exc)

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
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> TargetResponse:
    """Update a deployment target.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``admin`` minimum (matrice spec 08 — gestion
    host) + isolation par organisation (``is_member``).
    """
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
        raise NotFoundError(f"Cible {target_id} non trouvée")

    if not await UserOrganizationService.is_member(
        session, current_user, existing_target.organization_id
    ):
        raise PermissionDeniedError("Accès refusé à cette cible")

    if target_data.name and target_data.name != existing_target.name:
        # STORY-121.3 : unicité vérifiée dans l'organisation de la cible
        existing_name = await TargetService.get_by_name(
            session, existing_target.organization_id, target_data.name
        )
        if existing_name:
            raise ConflictError(f"Cible avec le nom '{target_data.name}' existe déjà")

    target = await TargetService.update(session, target_id, target_data)
    if target is None:
        raise WindFlowException("Erreur lors de la mise à jour de la cible")
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
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a deployment target permanently.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``admin`` minimum (matrice spec 08 :
    « Supprimer un host » = Admin+) + isolation par organisation.
    """
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
        raise NotFoundError(f"Cible {target_id} non trouvée")

    if not await UserOrganizationService.is_member(
        session, current_user, target.organization_id
    ):
        raise PermissionDeniedError("Accès refusé à cette cible")

    await TargetService.delete(session, target_id)

    # STORY-125.2 : audit de la suppression (après succès, org du target).
    await AuditService.log_from_request(
        request,
        "target.deleted",
        user=current_user,
        organization_id=target.organization_id,
        resource_type="target",
        resource_id=target_id,
        details={"name": target.name},
    )

    # STORY-162 (AC 3) : événement canonique ``host.removed`` — best-effort
    # post-commit (n'altère jamais la réponse API) ; payload sans secret
    # (rules 40 — IDs/nom uniquement).
    try:
        from ....core.events import EventType, get_event_bus

        await get_event_bus().emit(
            EventType.HOST_REMOVED,
            {
                "host_id": str(target.id),
                "name": target.name,
            },
        )
    except Exception as exc:  # best-effort : jamais bloquant
        logger.warning("host.removed event emission failed: %s", exc)
