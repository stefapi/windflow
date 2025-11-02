"""
Schemas for target capability scanning and discovery.

Validation strictly follows project backend guidelines (Pydantic V2).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .target import TargetResponse, TargetType


class PlatformArchitecture(str, Enum):
    """Supported CPU architecture identifiers."""
    X86_64 = "x86_64"
    X86_32 = "x86_32"
    ARM64 = "arm64"
    ARMV8 = "armv8"
    ARMV7 = "armv7"
    ARMV6 = "armv6"
    UNKNOWN = "unknown"


class ScanRequest(BaseModel):
    """Scan request parameters for remote or local target discovery."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True
    )

    host: str = Field(..., description="Hostname or IP address to scan")
    port: int = Field(
        default=22,
        ge=1,
        le=65535,
        description="SSH port for remote connection"
    )
    username: str = Field(..., min_length=1, max_length=128, description="Login username")
    password: str = Field(..., min_length=1, max_length=512, description="Login password")
    sudo_user: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Optional sudo username if privilege escalation required"
    )
    sudo_password: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=512,
        description="Optional sudo password for privilege escalation"
    )


class PlatformInfo(BaseModel):
    """Hardware platform information detected during scan."""

    model_config = ConfigDict(from_attributes=True)

    architecture: PlatformArchitecture = Field(
        default=PlatformArchitecture.UNKNOWN,
        description="Normalized CPU architecture identifier"
    )
    cpu_model: Optional[str] = Field(
        default=None,
        description="CPU model name reported by the host"
    )
    cpu_cores: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of CPU cores available"
    )
    total_memory_gb: Optional[float] = Field(
        default=None,
        ge=0,
        description="Total system memory in gigabytes"
    )


class OSInfo(BaseModel):
    """Operating system details detected during scan."""

    model_config = ConfigDict(from_attributes=True)

    system: str = Field(..., description="Operating system family (Linux, Windows, etc.)")
    distribution: Optional[str] = Field(
        default=None,
        description="Distribution or vendor name when available"
    )
    version: Optional[str] = Field(
        default=None,
        description="Operating system version string"
    )
    kernel: Optional[str] = Field(
        default=None,
        description="Kernel version information"
    )


class ToolInfo(BaseModel):
    """Generic tool availability and metadata."""

    model_config = ConfigDict(from_attributes=True)

    available: bool = Field(..., description="Indicates whether the tool is installed")
    version: Optional[str] = Field(
        default=None,
        description="Detected version string when available"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional information about the tool state"
    )


class DockerComposeInfo(BaseModel):
    """Docker Compose capability information."""

    model_config = ConfigDict(from_attributes=True)

    available: bool = Field(..., description="Indicates whether Docker Compose is available")
    version: Optional[str] = Field(
        default=None,
        description="Docker Compose version when available"
    )
    plugin_based: Optional[bool] = Field(
        default=None,
        description="True if docker compose plugin is used instead of standalone binary"
    )


class DockerSwarmInfo(BaseModel):
    """Docker Swarm capability information."""

    model_config = ConfigDict(from_attributes=True)

    available: bool = Field(..., description="Indicates whether Swarm functionality is available")
    active: Optional[bool] = Field(
        default=None,
        description="True when the node is part of an active swarm"
    )
    node_role: Optional[str] = Field(
        default=None,
        description="Role of the node within the swarm (manager/worker)"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional swarm information gathered during scan"
    )


class DockerCapabilities(BaseModel):
    """Docker capability information grouped in a dedicated structure."""

    model_config = ConfigDict(from_attributes=True)

    installed: bool = Field(..., description="Indicates whether Docker engine is installed")
    version: Optional[str] = Field(
        default=None,
        description="Docker engine version when available"
    )
    running: bool = Field(
        default=False,
        description="True if Docker daemon is reachable and running"
    )
    socket_accessible: bool = Field(
        default=False,
        description="Indicates whether Docker socket is accessible to the user"
    )
    compose: Optional[DockerComposeInfo] = Field(
        default=None,
        description="Docker Compose capability details"
    )
    swarm: Optional[DockerSwarmInfo] = Field(
        default=None,
        description="Docker Swarm capability details"
    )


class ScanResult(BaseModel):
    """Complete scan result containing detected capabilities."""

    model_config = ConfigDict(from_attributes=True)

    host: str = Field(..., description="Scanned host identifier")
    scan_date: datetime = Field(..., description="Timestamp when the scan occurred")
    success: bool = Field(..., description="Indicates whether the scan succeeded")

    platform: Optional[PlatformInfo] = Field(
        default=None,
        description="Platform hardware capabilities"
    )
    os: Optional[OSInfo] = Field(
        default=None,
        description="Operating system information"
    )
    virtualization: Dict[str, ToolInfo] = Field(
        default_factory=dict,
        description="Virtualization tools detected on the target"
    )
    docker: Optional[DockerCapabilities] = Field(
        default=None,
        description="Docker related capabilities"
    )
    kubernetes: Dict[str, ToolInfo] = Field(
        default_factory=dict,
        description="Kubernetes related tooling capabilities"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="List of error messages encountered during the scan"
    )


class CapabilityUpdate(BaseModel):
    """Schema used when updating target discovered capabilities."""

    model_config = ConfigDict(from_attributes=True)

    discovered_capabilities: Dict[str, Any] = Field(
        ...,
        description="Capabilities map to persist on the target model"
    )
    last_scan_date: datetime = Field(
        ...,
        description="Timestamp of the scan that produced these capabilities"
    )
    scan_status: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Status of the scan (pending, scanning, completed, failed)"
    )


class TargetDiscoveryRequest(ScanRequest):
    """Discovery request that leads to automatic target creation."""

    name: str = Field(..., min_length=1, max_length=255, description="Desired target name")
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional target description"
    )
    organization_id: Optional[str] = Field(
        default=None,
        description="Organization identifier, defaults to current user's organization"
    )
    preferred_type: Optional[TargetType] = Field(
        default=None,
        description="Optional preferred target type overriding automatic detection"
    )


class TargetDiscoveryResponse(BaseModel):
    """Response payload for discovery + creation workflow."""

    model_config = ConfigDict(from_attributes=True)

    target: TargetResponse = Field(..., description="Created target representation")
    scan_result: ScanResult = Field(..., description="Scan result used for creation")


class TargetCapabilitiesResponse(BaseModel):
    """Response payload for retrieving stored capabilities."""

    model_config = ConfigDict(from_attributes=True)

    scan_status: Optional[str] = Field(
        default=None,
        description="Status of the last scan (pending, scanning, completed, failed)"
    )
    last_scan_date: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the last capabilities scan"
    )
    scan_result: Optional[ScanResult] = Field(
        default=None,
        description="Stored scan result when available"
    )
