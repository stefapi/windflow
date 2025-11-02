"""
Unit tests for target scanner related utilities.
"""

from __future__ import annotations

import pytest

from backend.app.api.v1.targets import _infer_target_type
from backend.app.schemas.target import TargetType
from backend.app.schemas.target_scan import (
    DockerCapabilities,
    DockerSwarmInfo,
    ScanResult,
    ToolInfo,
)
from backend.app.services.target_scanner_service import TargetScannerService


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
            scan_date=None,
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
