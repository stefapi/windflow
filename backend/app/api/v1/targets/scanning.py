"""Scan et découverte automatique des cibles de déploiement."""

from __future__ import annotations

import logging
from typing import Any

import asyncssh
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....auth.dependencies import get_current_active_user
from ....core.rate_limit import conditional_rate_limiter
from ....database import get_db
from ....models.user import User
from ....schemas.target import (
    SSHAuthMethod,
    SSHCredentials,
    TargetCreate,
    TargetResponse,
    TargetType,
)
from ....schemas.target_scan import (
    ScanResult,
    TargetDiscoveryRequest,
    TargetDiscoveryResponse,
)
from ....services.commands import LocalCommandExecutor, SSHCommandExecutor
from ....services.target_scan_parsers import build_capabilities_payload
from ....services.target_scanner_service import TargetScannerService
from ....services.target_service import TargetService

router = APIRouter()
logger = logging.getLogger(__name__)


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
                                "description": "Local development machine",
                            },
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
                                "description": "Production deployment server",
                            },
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
                                "description": "Staging server with sudo",
                            },
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
                                "description": "Kubernetes cluster",
                            },
                        },
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
                            "created_at": "2026-02-02T21:50:00Z",
                        },
                        "scan_result": {
                            "success": True,
                            "scan_date": "2026-02-02T21:50:00Z",
                            "capabilities": {
                                "docker": True,
                                "docker_compose": True,
                                "kubernetes": False,
                                "libvirt": False,
                            },
                            "platform": {
                                "system": "Linux",
                                "release": "5.15.0-91-generic",
                                "machine": "x86_64",
                            },
                            "os": {
                                "name": "Ubuntu",
                                "version": "22.04",
                                "codename": "jammy",
                            },
                        },
                    }
                }
            },
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
                                "detail": "Failed to connect to host: Connection refused",
                            },
                        },
                        "authentication_failed": {
                            "summary": "Authentication failed",
                            "value": {
                                "error": "Authentication Error",
                                "detail": "SSH authentication failed: Invalid credentials",
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
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Impossible de découvrir une cible pour une autre organisation",
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
                        "detail": "Cible avec le nom 'production-server' existe déjà",
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
                        "detail": "Rate limit exceeded. Maximum 10 requests per minute.",
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
                        "detail": "An unexpected error occurred during discovery",
                    }
                }
            },
        },
    },
    tags=["targets"],
)
async def discover_target(
    request: Request,
    discovery_request: TargetDiscoveryRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> TargetDiscoveryResponse:
    """Discover target capabilities and create deployment target."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Discovering target at {discovery_request.host}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "host": discovery_request.host,
        },
    )
    organization_id = discovery_request.organization_id or current_user.organization_id
    if organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Impossible de découvrir une cible pour une autre organisation",
        )

    existing = await TargetService.get_by_name(
        session, organization_id, discovery_request.name
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cible avec le nom '{discovery_request.name}' existe déjà",
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

    ssh_credentials = SSHCredentials(
        auth_method=SSHAuthMethod.PASSWORD,
        username=discovery_request.username,
        password=discovery_request.password,
        sudo_user=discovery_request.sudo_user,
        sudo_password=discovery_request.sudo_password,
    )

    target_payload = TargetCreate(
        name=discovery_request.name,
        description=discovery_request.description,
        host=discovery_request.host,
        port=discovery_request.port,
        type=target_type,
        credentials=ssh_credentials,
        organization_id=organization_id,
        extra_metadata={
            "auto_discovered": True,
            "discovery_date": scan_result.scan_date.isoformat(),
            "source": "target_discovery_endpoint",
        },
    )

    target = await TargetService.create(
        session, target_payload, organization_id=organization_id
    )

    capabilities_payload = build_capabilities_payload(scan_result)
    platform_payload = (
        scan_result.platform.model_dump(mode="json") if scan_result.platform else None
    )
    os_payload = scan_result.os.model_dump(mode="json") if scan_result.os else None

    # Detect access profile (for discovery)
    access_profile_dict = await _detect_access_profile(
        scanner=scanner,
        discovery_request=discovery_request,
        is_localhost=is_localhost,
    )

    await TargetService.apply_scan_result(
        db=session,
        target=target,
        capabilities=capabilities_payload,
        scan_date=scan_result.scan_date,
        success=scan_result.success,
        platform_info=platform_payload,
        os_info=os_payload,
        access_profile=access_profile_dict,
    )

    return TargetDiscoveryResponse(
        target=TargetResponse.model_validate(target), scan_result=scan_result
    )


async def _detect_access_profile(
    scanner: TargetScannerService,
    discovery_request: TargetDiscoveryRequest,
    is_localhost: bool,
) -> dict[str, Any] | None:
    """Détecte le profil d'accès pendant la découverte."""
    try:
        if is_localhost:
            local_exec = LocalCommandExecutor()
            access_profile = await scanner.detect_access_profile(
                executor=local_exec,
                ssh_user=None,
                sudo_user=discovery_request.sudo_user,
                sudo_password=discovery_request.sudo_password,
                detection_method="discovery",
            )
        else:
            ssh_kwargs_detect: dict[str, Any] = {
                "host": discovery_request.host,
                "port": discovery_request.port,
                "username": discovery_request.username,
                "known_hosts": None,
            }
            if discovery_request.ssh_private_key:
                ssh_kwargs_detect["client_keys"] = [discovery_request.ssh_private_key]
                if getattr(discovery_request, "ssh_private_key_passphrase", None):
                    ssh_kwargs_detect["passphrase"] = discovery_request.ssh_private_key_passphrase
            else:
                ssh_kwargs_detect["password"] = discovery_request.password

            async with asyncssh.connect(**ssh_kwargs_detect) as conn:
                ssh_exec = SSHCommandExecutor(conn)
                access_profile = await scanner.detect_access_profile(
                    executor=ssh_exec,
                    ssh_user=discovery_request.username,
                    sudo_user=discovery_request.sudo_user,
                    sudo_password=discovery_request.sudo_password,
                    detection_method="discovery",
                )
        return access_profile.model_dump(mode="json")
    except Exception as ap_exc:
        logger.warning(
            "Access profile detection failed during discovery for %s: %s",
            discovery_request.host,
            ap_exc,
        )
        return None


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
                        "updated_at": "2026-02-02T21:50:00Z",
                    }
                }
            },
        },
        400: {
            "description": "Scan failed",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Scan Error",
                        "detail": "Failed to connect to target for scanning",
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
                        "detail": "An unexpected error occurred during scan",
                    }
                }
            },
        },
    },
    tags=["targets"],
)
async def scan_target(
    request: Request,
    target_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> TargetResponse:
    """Scan target capabilities and update information."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Scanning target {target_id}",
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

    scanner = TargetScannerService()
    updated_target = await scanner.scan_and_update_target(target, session)
    return TargetResponse.model_validate(updated_target)


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
