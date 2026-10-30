"""Scan et découverte automatique des cibles de déploiement."""

from __future__ import annotations

import logging
from typing import Any

import asyncssh
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....auth.rbac import require_admin
from ....core.exceptions import (
    ConflictError,
    InvalidInputError,
    NotFoundError,
    PermissionDeniedError,
)
from ....core.rate_limit import conditional_rate_limiter
from ....database import get_db
from ....enums.target import TargetType
from ....models.user import User
from ....schemas.host import (
    HostCreateRequest,
    HostResponse,
    SSHAuthMethod,
    SSHCredentials,
)
from ....schemas.target_scan import (
    ScanResult,
    TargetDiscoveryRequest,
    TargetDiscoveryResponse,
)
from ....services.commands import LocalCommandExecutor, SSHCommandExecutor
from ....services.host_scan_parsers import build_capabilities_payload
from ....services.host_scanner_service import HostScannerService
from ....services.host_service import HostService
from ....services.ssh_connection import HostKeyPolicy, build_ssh_kwargs
from ....services.user_organization_service import UserOrganizationService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/discover",
    response_model=TargetDiscoveryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Discover and create deployment host",
    description="""
Automatically discover host capabilities and create a new deployment host.

## Process
1. Connects to the host machine (localhost or remote via SSH)
2. Scans for available capabilities (Docker, Kubernetes, virtualization, etc.)
3. Detects OS, platform, and system information
4. Infers optimal host profile based on discovered capabilities
5. Creates host with discovered configuration
6. Returns host details with complete scan results

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
- Quick onboarding of new deployment hosts
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
                            "description": "Force specific target type (legacy alias of profile)",
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
    tags=["hosts"],
)
async def discover_target(
    request: Request,
    discovery_request: TargetDiscoveryRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> TargetDiscoveryResponse:
    """Discover target capabilities and create deployment target.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``admin`` minimum (matrice spec 08 :
    « Scanner / Ajouter un host » = Admin+ — la découverte crée la
    cible) + isolation par organisation (``is_member``).
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Discovering host at {discovery_request.host}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "host": discovery_request.host,
        },
    )
    # STORY-121.3 : org explicite vérifiée contre l'appartenance (403) ;
    # sinon organisation primaire de l'utilisateur
    if (
        discovery_request.organization_id
        and not await UserOrganizationService.is_member(
            session, current_user, discovery_request.organization_id
        )
    ):
        raise PermissionDeniedError(
            "Impossible de découvrir une cible pour une autre organisation"
        )
    organization_id = (
        discovery_request.organization_id
        or await UserOrganizationService.get_primary_organization_id(
            session, current_user
        )
    )
    if organization_id is None:
        raise InvalidInputError("Aucune organisation : rattachez d'abord votre compte")

    existing = await HostService.get_by_name(
        session, organization_id, discovery_request.name
    )
    if existing:
        raise ConflictError(f"Cible avec le nom '{discovery_request.name}' existe déjà")

    scanner = HostScannerService()
    host = discovery_request.host
    is_localhost = host in {"localhost", "127.0.0.1"}

    scan_result = await (
        scanner.scan_localhost()
        if is_localhost
        else scanner.scan_remote(discovery_request)  # type: ignore[arg-type]
    )

    target_type = discovery_request.preferred_type or _infer_target_type(scan_result)

    ssh_credentials = SSHCredentials(
        auth_method=SSHAuthMethod.PASSWORD,
        username=discovery_request.username,
        password=discovery_request.password,
        sudo_user=discovery_request.sudo_user,
        sudo_password=discovery_request.sudo_password,
    )

    host_payload = HostCreateRequest(
        name=discovery_request.name,
        description=discovery_request.description,
        host=discovery_request.host,
        port=discovery_request.port,
        type=target_type,  # type: ignore[arg-type]
        credentials=ssh_credentials,
        organization_id=organization_id,
        extra_metadata={
            "auto_discovered": True,
            "discovery_date": scan_result.scan_date.isoformat(),
            "source": "target_discovery_endpoint",
        },
    )

    created_host = await HostService.create(
        session, host_payload, organization_id=organization_id
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
        session=session,
    )

    await HostService.apply_scan_result(
        db=session,
        host=created_host,
        capabilities=capabilities_payload,
        scan_date=scan_result.scan_date,
        success=scan_result.success,
        platform_info=platform_payload,
        os_info=os_payload,
        access_profile=access_profile_dict,
    )

    return TargetDiscoveryResponse(
        target=HostResponse.model_validate(created_host), scan_result=scan_result
    )


async def _detect_access_profile(
    scanner: HostScannerService,
    discovery_request: TargetDiscoveryRequest,
    is_localhost: bool,
    session: AsyncSession | None = None,
) -> dict[str, Any] | None:
    """Détecte le profil d'accès pendant la découverte.

    TOFU STRICT (STORY-131.3) : la connexion de détection passe par le
    helper ``ssh_connection`` (plus aucun ``known_hosts: None``). La
    cible étant déjà persistée à ce point du flux discovery (créée en
    amont dans ``discover_target``), la vérification lit les
    empreintes de la cible — premier contact → ligne PENDING +
    blocage (le profil d'accès n'est alors pas détecté, comportement
    non-fatal déjà prévu par le ``try/except`` : la discovery
    aboutit, l'acceptation se fait via l'API 131.2 puis re-scan).
    """
    try:
        if is_localhost:
            local_exec = LocalCommandExecutor()
            access_profile = await scanner.detect_access_profile(  # type: ignore[attr-defined]
                executor=local_exec,
                ssh_user=None,
                sudo_user=discovery_request.sudo_user,
                sudo_password=discovery_request.sudo_password,
                detection_method="discovery",
            )
        else:
            ssh_kwargs_detect = await build_ssh_kwargs(
                session,
                host=discovery_request.host,
                port=discovery_request.port,
                username=discovery_request.username,
                mode=HostKeyPolicy.STRICT,
                password=discovery_request.password,
                ssh_private_key=discovery_request.ssh_private_key,
                passphrase=discovery_request.ssh_private_key_passphrase,
            )

            async with asyncssh.connect(**ssh_kwargs_detect) as conn:
                ssh_exec = SSHCommandExecutor(conn)
                access_profile = await scanner.detect_access_profile(  # type: ignore[attr-defined]
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
    "/{host_id}/scan",
    response_model=HostResponse,
    status_code=status.HTTP_200_OK,
    summary="Scan host capabilities",
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
    tags=["hosts"],
)
async def scan_target(
    request: Request,
    host_id: str,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> HostResponse:
    """Scan target capabilities and update information.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``admin`` minimum (matrice spec 08 :
    « Scanner un host » = Admin+) + isolation par organisation
    (``is_member``).
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Scanning host {host_id}",
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

    scanner = HostScannerService()
    updated_host = await scanner.scan_and_update_host(host, session)
    return HostResponse.model_validate(updated_host)


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
