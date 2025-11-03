"""
Unit tests for target scanner related utilities.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.api.v1.targets import _infer_target_type
from app.schemas.target import TargetType
from app.schemas.target_scan import (
    DockerCapabilities,
    DockerComposeInfo,
    DockerSwarmInfo,
    ScanResult,
    ToolInfo,
)
from app.services.target_scanner_service import TargetScannerService


class TestTargetScannerService:
    """Unit tests for TargetScannerService internal helpers."""

    @pytest.mark.parametrize(
        ("raw_arch", "expected"),
        [
            ("x86_64", TargetScannerService()._map_architecture("x86_64")),
        ],
    )
    def test_map_architecture_delegates(self, raw_arch: str, expected) -> None:
        """Ensure _map_architecture behaves consistently."""
        service = TargetScannerService()
        assert service._map_architecture(raw_arch) == expected

    @pytest.mark.parametrize(
        ("raw_arch", "expected"),
        [
            ("x86_64", "x86_64"),
            ("amd64", "x86_64"),
            ("i386", "x86_32"),
            ("aarch64", "arm64"),
            ("armv8l", "armv8"),
            ("armv7l", "armv7"),
            ("armv6l", "armv6"),
            ("mips64", "unknown"),
        ],
    )
    def test_map_architecture_variants(self, raw_arch: str, expected: str) -> None:
        """Verify architecture mappings cover major variants."""
        service = TargetScannerService()
        architecture = service._map_architecture(raw_arch)
        assert architecture.value == expected


class TestBuildCapabilitiesPayload:
    """Unit tests for build_capabilities_payload method."""

    def test_only_available_capabilities_are_included(self) -> None:
        """Verify that only capabilities with is_available=True are included."""
        service = TargetScannerService()
        scan_result = ScanResult(
            host="test-host",
            scan_date=datetime.utcnow(),
            success=True,
            docker=DockerCapabilities(
                installed=True,
                version="24.0.0",
                running=True,
                socket_accessible=True,
                compose=None,  # Not available
                swarm=None,  # Not available
            ),
            virtualization={
                "libvirt": ToolInfo(available=True, version="8.0", details=None),
                "virtualbox": ToolInfo(available=False, version=None, details=None),
            },
            kubernetes={
                "kubectl": ToolInfo(available=True, version="1.28", details=None),
                "kubeadm": ToolInfo(available=False, version=None, details=None),
            },
            errors=[],
        )

        capabilities = service.build_capabilities_payload(scan_result)

        # Vérifier que seules les capabilities disponibles sont présentes
        capability_types = [cap["capability_type"].value for cap in capabilities]

        # Doivent être présents (available=True)
        assert "docker" in capability_types
        assert "libvirt" in capability_types
        assert "kubectl" in capability_types

        # Ne doivent PAS être présents (available=False)
        assert "docker_compose" not in capability_types
        assert "docker_swarm" not in capability_types
        assert "virtualbox" not in capability_types
        assert "kubeadm" not in capability_types

        # Vérifier que toutes les entrées ont is_available=True
        assert all(cap["is_available"] for cap in capabilities)

    def test_docker_not_installed_creates_no_entries(self) -> None:
        """When Docker is not installed, no Docker-related entries should be created."""
        service = TargetScannerService()
        scan_result = ScanResult(
            host="test-host",
            scan_date=datetime.utcnow(),
            success=True,
            docker=None,  # Docker not installed
            virtualization={},
            kubernetes={},
            errors=[],
        )

        capabilities = service.build_capabilities_payload(scan_result)

        # Aucune capability Docker ne devrait être présente
        capability_types = [cap["capability_type"].value for cap in capabilities]
        assert "docker" not in capability_types
        assert "docker_compose" not in capability_types
        assert "docker_swarm" not in capability_types

    def test_docker_compose_available_is_included(self) -> None:
        """When Docker Compose is available, it should be included."""
        service = TargetScannerService()

        scan_result = ScanResult(
            host="test-host",
            scan_date=datetime.utcnow(),
            success=True,
            docker=DockerCapabilities(
                installed=True,
                version="24.0.0",
                running=True,
                socket_accessible=True,
                compose=DockerComposeInfo(
                    available=True,
                    version="2.24.0",
                    plugin_based=True
                ),
                swarm=None,
            ),
            virtualization={},
            kubernetes={},
            errors=[],
        )

        capabilities = service.build_capabilities_payload(scan_result)
        capability_types = [cap["capability_type"].value for cap in capabilities]

        assert "docker" in capability_types
        assert "docker_compose" in capability_types
        assert "docker_swarm" not in capability_types  # Swarm not available

    def test_empty_scan_creates_no_capabilities(self) -> None:
        """When scan finds nothing, the payload should be empty."""
        service = TargetScannerService()
        scan_result = ScanResult(
            host="test-host",
            scan_date=datetime.utcnow(),
            success=True,
            docker=None,
            virtualization={},
            kubernetes={},
            errors=[],
        )

        capabilities = service.build_capabilities_payload(scan_result)
        assert len(capabilities) == 0


class TestInferTargetType:
    """Unit tests for _infer_target_type utility."""

    def test_infer_target_type_docker_swarm(self) -> None:
        """Docker Swarm should win over other capabilities."""
        scan_result = ScanResult(
            host="127.0.0.1",
            scan_date=None,
            success=True,
            docker=DockerCapabilities(
                installed=True,
                version="24.0.0",
                running=True,
                socket_accessible=True,
                compose=None,
                swarm=DockerSwarmInfo(
                    available=True,
                    active=True,
                    node_role="manager",
                    details=None,
                ),
            ),
            virtualization={},
            kubernetes={},
            errors=[],
        )
        assert _infer_target_type(scan_result) == TargetType.DOCKER_SWARM

    def test_infer_target_type_kubernetes(self) -> None:
        """Kubernetes capability should produce a KUBERNETES target."""
        scan_result = ScanResult(
            host="192.168.1.10",
            scan_date=None,
            success=True,
            docker=None,
            virtualization={},
            kubernetes={
                "kubectl": ToolInfo(available=True, version="1.28", details=None)
            },
            errors=[],
        )
        assert _infer_target_type(scan_result) == TargetType.KUBERNETES

    def test_infer_target_type_virtualization(self) -> None:
        """Virtualization tools fallback to VM type."""
        scan_result = ScanResult(
            host="host",
            scan_date=datetime.utcnow(),
            success=True,
            docker=None,
            virtualization={
                "virtualbox": ToolInfo(available=True, version="7.0", details=None)
            },
            kubernetes={},
            errors=[],
        )
        assert _infer_target_type(scan_result) == TargetType.VM

    def test_infer_target_type_default(self) -> None:
        """Default fallback should be PHYSICAL."""
        scan_result = ScanResult(
            host="host",
            scan_date=None,
            success=True,
            docker=None,
            virtualization={},
            kubernetes={},
            errors=[],
        )
        assert _infer_target_type(scan_result) == TargetType.PHYSICAL
