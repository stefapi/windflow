"""Health check et capacités des cibles de déploiement."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....auth.dependencies import get_current_active_user
from ....core.rate_limit import conditional_rate_limiter
from ....database import get_db
from ....enums.target import CapabilityType
from ....models.user import User
from ....schemas.target import (
    HealthCheckResponse,
    TargetCapabilitiesResponse,
    TargetResponse,
)
from ....schemas.target_capability import TargetCapabilityResponse
from ....services.target_service import TargetService

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
    "/{target_id}/health-check",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Check target health (TCP reachability probe)",
    description="""
Perform a lightweight health check on a target by testing TCP port reachability.

## Process
1. Determines the appropriate port based on target type
2. Attempts a TCP connection (no authentication)
3. Updates target status to ONLINE or OFFLINE
4. Returns the health check result

## Port Selection
Uses the **configured port** of the target (``target.port``), which is the
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
                        "target_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "online",
                        "last_check": "2026-03-30T21:00:00Z",
                        "message": "Port 2376 ouvert sur docker.prod.example.com",
                    }
                }
            },
        },
        401: {"description": "Authentication required"},
        403: {"description": "Access denied to this target"},
        404: {"description": "Target not found"},
    },
    tags=["targets"],
)
async def health_check_target(
    request: Request,
    target_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> HealthCheckResponse:
    """Perform a lightweight TCP health check on a target."""
    from ....enums.target import TargetStatus as TS

    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Health check requested for target {target_id}",
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

    new_status = await TargetService.check_health(session, target)

    messages = {
        TS.ONLINE: f"Port ouvert sur {target.host}",
        TS.OFFLINE: f"Impossible de joindre {target.host} — port fermé ou injoignable",
        TS.ERROR: f"Erreur inattendue lors du check de {target.host}",
    }

    return HealthCheckResponse(
        target_id=target.id,
        status=new_status,
        last_check=target.last_check,
        message=messages.get(new_status, "Statut mis à jour"),
    )


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
async def get_target_capabilities(
    request: Request,
    target_id: str,
    capability_type: CapabilityType | None = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> TargetCapabilitiesResponse:
    """Retrieve target capabilities with optional filtering."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting capabilities for target {target_id}",
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

    capabilities = await TargetService.list_capabilities(
        db=session, target_id=target.id, capability_type=capability_type
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
            "description": "Target or capability not found",
            "content": {
                "application/json": {
                    "examples": {
                        "target_not_found": {
                            "summary": "Target not found",
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
    tags=["targets"],
)
async def get_target_capability_by_type(
    request: Request,
    target_id: str,
    capability_type: CapabilityType,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> TargetCapabilityResponse:
    """Retrieve a specific capability by type for a target."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting capability {capability_type} for target {target_id}",
        extra={
            "correlation_id": correlation_id,
            "target_id": target_id,
            "capability_type": str(capability_type),
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

    capabilities = await TargetService.list_capabilities(
        db=session, target_id=target.id, capability_type=capability_type
    )

    if not capabilities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capacité {capability_type.value} non trouvée pour cette cible",
        )

    return TargetCapabilityResponse.model_validate(capabilities[0])


@router.get(
    "/{target_id}/capabilities/virtualization",
    response_model=list[TargetCapabilityResponse],
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
async def get_target_virtualization_capabilities(
    request: Request,
    target_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> list[TargetCapabilityResponse]:
    """Retrieve virtualization capabilities for a target."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting virtualization capabilities for target {target_id}",
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

    capabilities = await TargetService.list_capabilities(
        db=session, target_id=target.id
    )

    virtualization_capabilities = [
        TargetCapabilityResponse.model_validate(capability)
        for capability in capabilities
        if capability.capability_type in VIRTUALIZATION_CAPABILITY_TYPES
    ]
    return virtualization_capabilities
