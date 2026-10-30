"""Health check et capacités des cibles de déploiement."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....auth.rbac import require_viewer
from ....core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
)
from ....core.rate_limit import conditional_rate_limiter
from ....database import get_db
from ....enums.host import CapabilityType
from ....enums.host import HostStatus as HS
from ....models.user import User
from ....schemas.host import (
    HostCapabilitiesResponse,
    HostHealthCheckResponse,
)
from ....schemas.target_capability import TargetCapabilityResponse
from ....services.host_service import HostService
from ....services.user_organization_service import UserOrganizationService

router = APIRouter()
logger = logging.getLogger(__name__)

# Types de capacités liés à la virtualisation
VIRTUALIZATION_CAPABILITY_TYPES: set[CapabilityType] = {
    CapabilityType.LIBVIRT,
    CapabilityType.VIRTUALBOX,
    CapabilityType.VAGRANT,
    CapabilityType.PROXMOX,
    CapabilityType.QEMU_KVM,
}


@router.post(
    "/{host_id}/health-check",
    response_model=HostHealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Check host health (TCP reachability probe)",
    description="""
Perform a lightweight health check on a host by testing TCP port reachability.

## Process
1. Determines the appropriate port based on host type
2. Attempts a TCP connection (no authentication)
3. Updates host status to ONLINE or OFFLINE
4. Returns the health check result

## Port Selection
Uses the **configured port** of the host (``host.port``), which is the
management channel (typically SSH port 22).  This port is always reachable
on a functioning remote machine.

## Status Updates
- **ONLINE**: TCP connection succeeded
- **OFFLINE**: Connection refused or timed out
- **ERROR**: Unexpected error during check

The `last_check` timestamp is updated on every check.

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(60, 60))],
    responses={
        200: {
            "description": "Health check completed",
            "content": {
                "application/json": {
                    "example": {
                        "host_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "online",
                        "last_check": "2026-03-30T21:00:00Z",
                        "message": "Port 2376 ouvert sur docker.prod.example.com",
                    }
                }
            },
        },
        401: {"description": "Authentication required"},
        403: {"description": "Access denied to this host"},
        404: {"description": "Host not found"},
    },
    tags=["hosts"],
)
async def health_check_host(
    request: Request,
    host_id: str,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_db),
) -> HostHealthCheckResponse:
    """Perform a lightweight TCP health check on a host.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture de statut —
    matrice spec 08 : « statut des hosts » = tous les rôles) + isolation
    par organisation (``is_member``).

    Divergence inventaire : la story cible admin (« associer
    capabilities ») mais le libellé réel est un health-check TCP de
    lecture → viewer, conforme matrice Hosts.
    """

    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Health check requested for host {host_id}",
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

    new_status = await HostService.check_health(session, host)

    messages = {
        HS.ONLINE: f"Port ouvert sur {host.host}",
        HS.OFFLINE: f"Impossible de joindre {host.host} — port fermé ou injoignable",
        HS.UNREACHABLE: f"Erreur inattendue lors du check de {host.host}",
    }

    return HostHealthCheckResponse(
        host_id=host.id,
        status=new_status,
        last_check=host.last_check,  # type: ignore[arg-type]
        message=messages.get(new_status, "Statut mis à jour"),
    )


@router.get(
    "/{host_id}/capabilities",
    response_model=HostCapabilitiesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get host capabilities",
    description="""
Retrieve all capabilities detected for a specific host.

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
- Verify host readiness
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
                            "machine": "x86_64",
                        },
                        "os_info": {
                            "name": "Ubuntu",
                            "version": "22.04",
                            "codename": "jammy",
                        },
                        "capabilities": [
                            {
                                "type": "docker",
                                "available": True,
                                "version": "24.0.7",
                                "details": {
                                    "api_version": "1.43",
                                    "socket": "/var/run/docker.sock",
                                },
                            },
                            {
                                "type": "docker_compose",
                                "available": True,
                                "version": "2.23.0",
                            },
                            {"type": "kubernetes", "available": False},
                        ],
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
async def get_host_capabilities(
    request: Request,
    host_id: str,
    capability_type: CapabilityType | None = None,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_db),
) -> HostCapabilitiesResponse:
    """Retrieve host capabilities with optional filtering.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — matrice
    spec 08) + isolation par organisation (``is_member``).
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting capabilities for host {host_id}",
        extra={"correlation_id": correlation_id, "host_id": host_id},
    )
    host = await HostService.get_by_id(session, host_id)
    if not host:
        raise NotFoundError(f"Cible {host_id} non trouvée")

    if not await UserOrganizationService.is_member(
        session, current_user, host.organization_id
    ):
        raise PermissionDeniedError("Accès refusé à cette cible")

    capabilities = await HostService.list_capabilities(
        db=session, host_id=host.id, capability_type=capability_type
    )

    return HostCapabilitiesResponse(
        scan_date=host.scan_date,
        scan_success=host.scan_success,
        platform_info=host.platform_info,
        os_info=host.os_info,
        capabilities=[
            TargetCapabilityResponse.model_validate(capability)
            for capability in capabilities
        ],
    )


@router.get(
    "/{host_id}/capabilities/{capability_type}",
    response_model=TargetCapabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Get specific host capability",
    description="""
Retrieve a specific capability by type for a host.

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
- Validate host compatibility

## Error Handling
Returns 404 if the capability type is not found for the host.

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
                            "root_dir": "/var/lib/docker",
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
            "description": "Host or capability not found",
            "content": {
                "application/json": {
                    "examples": {
                        "target_not_found": {
                            "summary": "Host not found",
                            "value": {
                                "error": "Not Found",
                                "detail": "Cible 550e8400-e29b-41d4-a716-446655440000 non trouvée",
                            },
                        },
                        "capability_not_found": {
                            "summary": "Capability not found",
                            "value": {
                                "error": "Not Found",
                                "detail": "Capacité kubernetes non trouvée pour cette cible",
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
async def get_host_capability_by_type(
    request: Request,
    host_id: str,
    capability_type: CapabilityType,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_db),
) -> TargetCapabilityResponse:
    """Retrieve a specific capability by type for a host.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — matrice
    spec 08) + isolation par organisation (``is_member``).
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting capability {capability_type} for host {host_id}",
        extra={
            "correlation_id": correlation_id,
            "host_id": host_id,
            "capability_type": str(capability_type),
        },
    )
    host = await HostService.get_by_id(session, host_id)
    if not host:
        raise NotFoundError(f"Cible {host_id} non trouvée")

    if not await UserOrganizationService.is_member(
        session, current_user, host.organization_id
    ):
        raise PermissionDeniedError("Accès refusé à cette cible")

    capabilities = await HostService.list_capabilities(
        db=session, host_id=host.id, capability_type=capability_type
    )

    if not capabilities:
        raise NotFoundError(
            f"Capacité {capability_type.value} non trouvée pour cette cible"
        )

    return TargetCapabilityResponse.model_validate(capabilities[0])


@router.get(
    "/{host_id}/capabilities/virtualization",
    response_model=list[TargetCapabilityResponse],
    status_code=status.HTTP_200_OK,
    summary="Get host virtualization capabilities",
    description="""
Retrieve only virtualization-related capabilities for a host.

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
                            "summary": "Host with virtualization",
                            "value": [
                                {
                                    "type": "libvirt",
                                    "available": True,
                                    "version": "8.0.0",
                                    "details": {
                                        "uri": "qemu:///system",
                                        "hypervisor": "QEMU",
                                    },
                                },
                                {
                                    "type": "virtualbox",
                                    "available": True,
                                    "version": "7.0.12",
                                },
                            ],
                        },
                        "no_capabilities": {
                            "summary": "No virtualization detected",
                            "value": [],
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
async def get_host_virtualization_capabilities(
    request: Request,
    host_id: str,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_db),
) -> list[TargetCapabilityResponse]:
    """Retrieve virtualization capabilities for a host.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``viewer`` minimum (lecture — matrice
    spec 08) + isolation par organisation (``is_member``).
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting virtualization capabilities for host {host_id}",
        extra={"correlation_id": correlation_id, "host_id": host_id},
    )
    host = await HostService.get_by_id(session, host_id)
    if not host:
        raise NotFoundError(f"Cible {host_id} non trouvée")

    if not await UserOrganizationService.is_member(
        session, current_user, host.organization_id
    ):
        raise PermissionDeniedError("Accès refusé à cette cible")

    capabilities = await HostService.list_capabilities(db=session, host_id=host.id)

    virtualization_capabilities = [
        TargetCapabilityResponse.model_validate(capability)
        for capability in capabilities
        if capability.capability_type in VIRTUALIZATION_CAPABILITY_TYPES
    ]
    return virtualization_capabilities
