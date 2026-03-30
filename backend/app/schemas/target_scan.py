"""Schemas Pydantic pour les résultats de scan de cibles."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from ..enums.target import CapabilityType


# ─── Architecture ───────────────────────────────────────────────


class Architecture(str, Enum):
    """Architecture CPU normalisée (utile pour les tests unitaires)."""

    X86_64 = "x86_64"
    X86_32 = "x86_32"
    ARM64 = "arm64"
    ARMV8 = "armv8"
    ARMV7 = "armv7"
    ARMV6 = "armv6"
    RISCV64 = "riscv64"
    UNKNOWN = "unknown"


class PlatformArchitecture(str, Enum):
    """Architecture CPU normalisée pour le scan de cibles."""

    X86_64 = "x86_64"
    X86_32 = "x86_32"
    ARM64 = "arm64"
    ARMV8 = "armv8"
    ARMV7 = "armv7"
    ARMV6 = "armv6"
    RISCV64 = "riscv64"
    UNKNOWN = "unknown"


# ─── Platform & OS ──────────────────────────────────────────────


class PlatformInfo(BaseModel):
    """Informations sur la plateforme matérielle."""

    architecture: PlatformArchitecture = PlatformArchitecture.UNKNOWN
    cpu_model: str | None = None
    cpu_cores: int | None = None
    total_memory_gb: float | None = None


class OSInfo(BaseModel):
    """Informations sur le système d'exploitation."""

    system: str = "unknown"
    distribution: str | None = None
    version: str | None = None
    kernel: str | None = None
    uname: str | None = None


# ─── Socket / Runtime info ──────────────────────────────────────


class SocketInfo(BaseModel):
    """Information about a detected Unix socket."""

    path: str
    exists: bool = False
    accessible: bool = False
    mode: str | None = Field(
        default=None,
        description="system, rootless, or session",
    )


class ContainerRuntimeInfo(BaseModel):
    """Container runtime detected on the target."""

    available: bool = False
    version: str | None = None
    install_method: str | None = Field(
        default=None,
        description="snap, package, binary, etc.",
    )
    socket: SocketInfo | None = None
    details: dict[str, Any] | None = None


class ToolInfo(BaseModel):
    """Generic tool detection result."""

    available: bool = False
    version: str | None = None
    details: dict[str, Any] | None = None


# ─── Docker-specific ────────────────────────────────────────────


class DockerComposeInfo(BaseModel):
    """Docker Compose detection result."""

    available: bool = False
    version: str | None = None
    plugin_based: bool | None = Field(
        default=None,
        description="True if compose is a Docker plugin (v2)",
    )


class DockerSwarmInfo(BaseModel):
    """Docker Swarm detection result."""

    available: bool = False
    active: bool | None = None
    node_role: str | None = None
    details: dict[str, Any] | None = None


class DockerCapabilities(BaseModel):
    """Docker engine detection result."""

    installed: bool = False
    version: str | None = None
    running: bool = False
    socket_accessible: bool = False
    compose: DockerComposeInfo | None = None
    swarm: DockerSwarmInfo | None = None
    socket: SocketInfo | None = None


# ─── Scan Request ───────────────────────────────────────────────


class ScanRequest(BaseModel):
    """Paramètres pour un scan de cible distante."""

    host: str
    port: int = 22
    username: str | None = None
    password: str | None = None
    ssh_private_key: str | None = None
    ssh_private_key_passphrase: str | None = None
    sudo_user: str | None = None
    sudo_password: str | None = None


# ─── Scan Result ────────────────────────────────────────────────


class ScanResult(BaseModel):
    """Résultat complet d'un scan de cible."""

    host: str
    scan_date: datetime
    success: bool = True

    # Détections
    docker: DockerCapabilities | None = None
    virtualization: dict[str, ToolInfo] = Field(default_factory=dict)
    kubernetes: dict[str, ToolInfo] = Field(default_factory=dict)
    container_runtimes: dict[str, ContainerRuntimeInfo] = Field(default_factory=dict)
    oci_tools: dict[str, ToolInfo] = Field(default_factory=dict)

    # Informations système
    platform: PlatformInfo | None = None
    os: OSInfo | None = None
    platform_info: dict[str, Any] | None = None
    os_info: dict[str, Any] | None = None

    # Sockets découverts
    discovered_sockets: dict[str, SocketInfo] = Field(default_factory=dict)

    # Erreurs
    errors: list[str] = Field(default_factory=list)


# ─── Capability payload item ────────────────────────────────────


class CapabilityPayloadItem(BaseModel):
    """Élément de capacité prêt à être persisté en base."""

    capability_type: CapabilityType
    is_available: bool
    version: str | None = None
    details: dict[str, Any] | None = None


# ─── Discovery ──────────────────────────────────────────────────


class TargetDiscoveryRequest(BaseModel):
    """Requête de découverte automatique d'une cible."""

    name: str = Field(..., min_length=1, max_length=255)
    host: str = Field(..., min_length=1)
    port: int = Field(default=22, ge=1, le=65535)
    description: str | None = None
    username: str | None = None
    password: str | None = None
    ssh_private_key: str | None = None
    ssh_private_key_passphrase: str | None = None
    sudo_user: str | None = None
    sudo_password: str | None = None
    preferred_type: str | None = Field(
        default=None, description="Type de cible souhaité (auto-détecté si absent)"
    )
    organization_id: str | None = None


class TargetDiscoveryResponse(BaseModel):
    """Réponse après découverte et création d'une cible."""

    target: Any = Field(..., description="Cible créée (TargetResponse)")
    scan_result: ScanResult = Field(..., description="Résultat du scan")
