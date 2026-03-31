"""
Unit tests for target scanner related utilities.

Covers parsing helpers, capability payload building, socket probing,
and new detector methods (LXC, LXD, Incus, containerd, OCI tools).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock

import pytest

from app.schemas.target_scan import (
    ContainerRuntimeInfo,
    DockerCapabilities,
    DockerComposeInfo,
    ScanResult,
    SocketInfo,
    ToolInfo,
)
from app.services.commands import CommandResult
from app.services.socket_clients import SocketProbe
from app.services.target_scan_parsers import (
    build_capabilities_payload,
    map_architecture,
    map_kubernetes_key,
    map_oci_key,
    map_runtime_key,
    map_virtualization_key,
    parse_k3s_version,
    parse_kubectl_version,
    parse_runc_version,
    parse_vagrant_version,
    parse_version_only,
)
from app.services.target_scanner_service import TargetScannerService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockExecutor:
    """Mock command executor returning pre-configured results per command."""

    def __init__(
        self,
        responses: Optional[dict[str, CommandResult]] = None,
        default: Optional[CommandResult] = None,
    ):
        self._responses = responses or {}
        self._default = default or CommandResult(1, "", "not found")

    async def run(
        self, command: str, timeout: int = 30, require_success: bool = False
    ) -> CommandResult:
        # Match by prefix to handle variations
        for cmd_prefix, result in self._responses.items():
            if command.startswith(cmd_prefix) or command == cmd_prefix:
                return result
        return self._default


def _make_result(
    exit_status: int = 0, stdout: str = "", stderr: str = ""
) -> CommandResult:
    return CommandResult(exit_status, stdout, stderr)


# ---------------------------------------------------------------------------
# Architecture mapping
# ---------------------------------------------------------------------------

class TestMapArchitecture:
    """Verify architecture mappings cover major variants."""

    @pytest.mark.parametrize(
        ("raw_arch", "expected"),
        [
            ("x86_64", "x86_64"),
            ("amd64", "x86_64"),
            ("i386", "x86_32"),
            ("i686", "x86_32"),
            ("aarch64", "arm64"),
            ("arm64", "arm64"),
            ("armv8l", "armv8"),
            ("armv8", "armv8"),
            ("armv7l", "armv7"),
            ("armv7", "armv7"),
            ("armv6l", "armv6"),
            ("armv6", "armv6"),
            ("mips64", "unknown"),
            ("riscv64", "unknown"),
        ],
    )
    def test_map_architecture_variants(self, raw_arch: str, expected: str) -> None:
        assert map_architecture(raw_arch).value == expected


# ---------------------------------------------------------------------------
# Version parsing
# ---------------------------------------------------------------------------

class TestVersionParsing:
    """Test all version parsers."""

    def test_parse_version_only_standard(self) -> None:
        result = parse_version_only("podman version 4.8.0")
        assert result == {"version": "4.8.0"}

    def test_parse_version_only_no_match(self) -> None:
        result = parse_version_only("no version here")
        assert result == {}

    def test_parse_k3s_version_with_prefix(self) -> None:
        result = parse_k3s_version("k3s version v1.28.4+k3s2\n")
        assert result == {"version": "1.28.4+k3s2"}

    def test_parse_k3s_version_without_prefix(self) -> None:
        result = parse_k3s_version("k3s version 1.27.1")
        assert result == {"version": "1.27.1"}

    def test_parse_runc_version_multiline(self) -> None:
        output = "runc version 1.1.12\ncommit: v1.1.12-0-g51d5e94\nspec: 1.0.2"
        result = parse_runc_version(output)
        assert result.get("version") == "1.1.12"

    def test_parse_runc_version_single_line(self) -> None:
        result = parse_runc_version("1.1.11")
        assert result.get("version") == "1.1.11"

    def test_parse_kubectl_version_json(self) -> None:
        output = '{"clientVersion": {"gitVersion": "v1.28.4", "major": "1", "minor": "28"}}'
        result = parse_kubectl_version(output)
        assert result["version"] == "v1.28.4"
        assert result["major"] == "1"

    def test_parse_kubectl_version_text_fallback(self) -> None:
        result = parse_kubectl_version("Client Version: v1.27.0")
        assert result["version"] == "1.27.0"

    def test_parse_vagrant_version(self) -> None:
        result = parse_vagrant_version("Vagrant 2.4.1")
        assert result["version"] == "2.4.1"
        assert result["raw"] == "Vagrant 2.4.1"


# ---------------------------------------------------------------------------
# SocketProbe
# ---------------------------------------------------------------------------

class TestSocketProbe:
    """Test SocketProbe socket path resolution."""

    def test_socket_paths_defined(self) -> None:
        """Ensure all expected tools have socket paths defined."""
        expected_tools = {"docker", "podman", "lxd", "incus", "libvirt", "lxc", "containerd"}
        for tool in expected_tools:
            assert tool in SocketProbe.SOCKET_PATHS, f"Missing socket paths for {tool}"

    def test_docker_has_system_and_rootless(self) -> None:
        docker_paths = SocketProbe.SOCKET_PATHS["docker"]
        assert "system" in docker_paths
        assert "rootless" in docker_paths
        assert "/var/run/docker.sock" in docker_paths["system"]

    def test_lxd_has_system_paths(self) -> None:
        lxd_paths = SocketProbe.SOCKET_PATHS["lxd"]
        assert "/var/lib/lxd/unix.socket" in lxd_paths["system"]
        assert "/var/snap/lxd/common/lxd/unix.socket" in lxd_paths["system"]

    def test_incus_has_system_paths(self) -> None:
        incus_paths = SocketProbe.SOCKET_PATHS["incus"]
        assert "/var/lib/incus/unix.socket" in incus_paths["system"]
        assert "/var/snap/incus/common/incus/unix.socket" in incus_paths["system"]

    def test_libvirt_has_system_and_session(self) -> None:
        libvirt_paths = SocketProbe.SOCKET_PATHS["libvirt"]
        assert "system" in libvirt_paths
        assert "session" in libvirt_paths

    def test_containerd_has_system_and_k3s(self) -> None:
        containerd_paths = SocketProbe.SOCKET_PATHS["containerd"]
        assert "/run/containerd/containerd.sock" in containerd_paths["system"]
        assert "/run/k3s/containerd/containerd.sock" in containerd_paths["system"]

    @pytest.mark.asyncio
    async def test_probe_returns_none_for_unknown_tool(self) -> None:
        executor = MockExecutor()
        result = await SocketProbe.probe(executor, "nonexistent_tool")
        assert result is None

    @pytest.mark.asyncio
    async def test_probe_detects_accessible_socket(self) -> None:
        executor = MockExecutor(
            responses={
                "test -S /var/run/docker.sock": _make_result(0, "ok"),
                "test -r /var/run/docker.sock": _make_result(0, "ok"),
            }
        )
        result = await SocketProbe.probe(executor, "docker")
        assert result is not None
        assert result.path == "/var/run/docker.sock"
        assert result.mode == "system"
        assert result.exists is True
        assert result.accessible is True

    @pytest.mark.asyncio
    async def test_probe_detects_existing_but_not_accessible_socket(self) -> None:
        """Socket exists but user can't read it (e.g. LXD without group membership)."""
        executor = MockExecutor(
            responses={
                "test -S /var/snap/lxd/common/lxd/unix.socket": _make_result(0, "ok"),
                "test -r /var/snap/lxd/common/lxd/unix.socket": _make_result(1, ""),
            }
        )
        result = await SocketProbe.probe(executor, "lxd")
        assert result is not None
        assert result.path == "/var/snap/lxd/common/lxd/unix.socket"
        assert result.exists is True
        assert result.accessible is False

    @pytest.mark.asyncio
    async def test_probe_returns_none_when_no_socket(self) -> None:
        executor = MockExecutor(default=_make_result(1, "", "not found"))
        result = await SocketProbe.probe(executor, "docker")
        assert result is None


# ---------------------------------------------------------------------------
# Container runtime detectors
# ---------------------------------------------------------------------------

class TestDetectLXC:
    """Test LXC detection."""

    @pytest.mark.asyncio
    async def test_lxc_available(self) -> None:
        service = TargetScannerService()
        executor = MockExecutor(
            responses={
                "lxc-info --version": _make_result(0, "5.0.3\n"),
                "lxc-checkconfig": _make_result(0, "Kernel support enabled"),
                "test -S": _make_result(1, ""),
            }
        )
        result = await service._detect_lxc(executor)
        assert result.available is True
        assert result.version == "5.0.3"

    @pytest.mark.asyncio
    async def test_lxc_not_installed(self) -> None:
        service = TargetScannerService()
        executor = MockExecutor(default=_make_result(127, "", "command not found"))
        result = await service._detect_lxc(executor)
        assert result.available is False


class TestDetectLXD:
    """Test LXD detection."""

    @pytest.mark.asyncio
    async def test_lxd_snap_install(self) -> None:
        service = TargetScannerService()
        executor = MockExecutor(
            responses={
                "lxd --version": _make_result(0, "5.21\n"),
                "lxc version": _make_result(0, "5.21"),
                "snap list lxd": _make_result(0, "lxd  5.21  28429  latest/stable  canonical✓  -"),
                "systemctl": _make_result(0, "active"),
                "test -S /var/snap/lxd/common/lxd/unix.socket": _make_result(0, "ok"),
            }
        )
        result = await service._detect_lxd(executor)
        assert result.available is True
        assert result.version == "5.21"
        assert result.install_method == "snap"

    @pytest.mark.asyncio
    async def test_lxd_not_installed(self) -> None:
        service = TargetScannerService()
        executor = MockExecutor(default=_make_result(127, "", "not found"))
        result = await service._detect_lxd(executor)
        assert result.available is False

    @pytest.mark.asyncio
    async def test_lxd_package_install(self) -> None:
        service = TargetScannerService()
        executor = MockExecutor(
            responses={
                "lxd --version": _make_result(0, "5.19\n"),
                "lxc version": _make_result(0, "5.19"),
                "snap list lxd": _make_result(1, "", "not installed"),
                "test -S /var/lib/lxd/unix.socket": _make_result(0, "ok"),
            }
        )
        result = await service._detect_lxd(executor)
        assert result.available is True
        assert result.install_method == "package"


class TestDetectIncus:
    """Test Incus detection."""

    @pytest.mark.asyncio
    async def test_incus_available(self) -> None:
        service = TargetScannerService()
        executor = MockExecutor(
            responses={
                "incus version": _make_result(0, "Incus 6.0.1\n"),
                "snap list incus": _make_result(0, "incus  6.0.1  123  latest/stable"),
                "systemctl": _make_result(0, "active"),
                "test -S /var/lib/incus/unix.socket": _make_result(0, "ok"),
            }
        )
        result = await service._detect_incus(executor)
        assert result.available is True
        assert result.install_method == "snap"

    @pytest.mark.asyncio
    async def test_incus_not_installed(self) -> None:
        service = TargetScannerService()
        executor = MockExecutor(default=_make_result(127, "", "not found"))
        result = await service._detect_incus(executor)
        assert result.available is False


class TestDetectContainerd:
    """Test containerd detection."""

    @pytest.mark.asyncio
    async def test_containerd_available(self) -> None:
        service = TargetScannerService()
        executor = MockExecutor(
            responses={
                "containerd --version": _make_result(0, "containerd github.com/containerd/containerd v1.7.13\n"),
                "test -S /run/containerd/containerd.sock": _make_result(0, "ok"),
            }
        )
        result = await service._detect_containerd(executor)
        assert result.available is True
        assert result.version == "1.7.13"

    @pytest.mark.asyncio
    async def test_containerd_via_ctr(self) -> None:
        service = TargetScannerService()
        executor = MockExecutor(
            responses={
                "containerd --version": _make_result(1, "", "not found"),
                "ctr version": _make_result(0, "ctr version 1.7.11\n"),
            }
        )
        result = await service._detect_containerd(executor)
        assert result.available is True
        assert result.details.get("detected_via") == "ctr"

    @pytest.mark.asyncio
    async def test_containerd_not_installed(self) -> None:
        service = TargetScannerService()
        executor = MockExecutor(default=_make_result(127, "", "not found"))
        result = await service._detect_containerd(executor)
        assert result.available is False

    @pytest.mark.asyncio
    async def test_containerd_managed_by_k3s(self) -> None:
        service = TargetScannerService()

        # Need a smarter executor because prefix matching confuses
        # "test -S /run/k3s/containerd/containerd.sock" with
        # "test -S /run/k3s/containerd/containerd.sock && echo 'k3s'"
        class K3sMockExecutor(MockExecutor):
            async def run(self, command, timeout=30, require_success=False):
                if "echo 'k3s'" in command:
                    return _make_result(0, "k3s")
                return await super().run(command, timeout, require_success)

        executor = K3sMockExecutor(
            responses={
                "containerd --version": _make_result(0, "containerd v1.7.10\n"),
                "test -S /run/containerd/containerd.sock": _make_result(1, ""),
                "test -S /run/k3s/containerd/containerd.sock": _make_result(0, "ok"),
            }
        )
        result = await service._detect_containerd(executor)
        assert result.available is True
        assert result.details.get("managed_by") == "k3s"


# ---------------------------------------------------------------------------
# OCI tools detection
# ---------------------------------------------------------------------------

class TestDetectOciTools:
    """Test OCI tools detection."""

    @pytest.mark.asyncio
    async def test_all_oci_tools_available(self) -> None:
        service = TargetScannerService()
        executor = MockExecutor(
            responses={
                "runc --version": _make_result(0, "runc version 1.1.12\n"),
                "crun --version": _make_result(0, "crun version 1.14\n"),
                "buildah --version": _make_result(0, "buildah version 1.33.3\n"),
                "skopeo --version": _make_result(0, "skopeo version 1.15.0\n"),
                "podman-compose --version": _make_result(0, "podman-compose version 1.2.0\n"),
            }
        )
        result = await service._detect_oci_tools(executor)
        assert len(result) == 5
        assert all(info.available for info in result.values())
        assert result["runc"].version == "1.1.12"
        assert result["crun"].version == "1.14"
        assert result["buildah"].version == "1.33.3"
        assert result["skopeo"].version == "1.15.0"
        assert result["podman_compose"].version == "1.2.0"

    @pytest.mark.asyncio
    async def test_no_oci_tools(self) -> None:
        service = TargetScannerService()
        executor = MockExecutor(default=_make_result(127, "", "not found"))
        result = await service._detect_oci_tools(executor)
        assert len(result) == 5
        assert all(not info.available for info in result.values())


# ---------------------------------------------------------------------------
# Kubernetes detection (enhanced with helm)
# ---------------------------------------------------------------------------

class TestDetectKubernetes:
    """Test Kubernetes tooling detection."""

    @pytest.mark.asyncio
    async def test_kubernetes_with_helm(self) -> None:
        service = TargetScannerService()
        executor = MockExecutor(
            responses={
                "kubectl version --client -o json": _make_result(
                    0,
                    '{"clientVersion": {"gitVersion": "v1.29.1", "major": "1", "minor": "29"}}',
                ),
                "kubeadm version -o json": _make_result(1, "", "not found"),
                "k3s --version": _make_result(1, "", "not found"),
                "microk8s.kubectl version --output=json": _make_result(1, "", "not found"),
                "helm version --short": _make_result(0, "v3.14.0+g3.14.0\n"),
            }
        )
        result = await service._detect_kubernetes(executor)
        assert result["kubectl"].available is True
        assert result["kubectl"].version == "v1.29.1"
        assert result["helm"].available is True
        assert result["helm"].version == "3.14.0"
        assert result["kubeadm"].available is False
        assert result["k3s"].available is False
        assert result["microk8s"].available is False


# ---------------------------------------------------------------------------
# Build capabilities payload
# ---------------------------------------------------------------------------

class TestBuildCapabilitiesPayload:
    """Unit tests for build_capabilities_payload method."""

    def test_only_available_capabilities_are_included(self) -> None:
        scan_result = ScanResult(
            host="test-host",
            scan_date=datetime.now(timezone.utc),
            success=True,
            docker=DockerCapabilities(
                installed=True,
                version="24.0.0",
                running=True,
                socket_accessible=True,
                compose=None,
                swarm=None,
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

        capabilities = build_capabilities_payload(scan_result)
        capability_types = [cap["capability_type"].value for cap in capabilities]

        assert "docker" in capability_types
        assert "libvirt" in capability_types
        assert "kubectl" in capability_types
        assert "docker_compose" not in capability_types
        assert "docker_swarm" not in capability_types
        assert "virtualbox" not in capability_types
        assert "kubeadm" not in capability_types
        assert all(cap["is_available"] for cap in capabilities)

    def test_docker_not_installed_creates_no_entries(self) -> None:
        scan_result = ScanResult(
            host="test-host",
            scan_date=datetime.now(timezone.utc),
            success=True,
            docker=None,
            virtualization={},
            kubernetes={},
            errors=[],
        )
        capabilities = build_capabilities_payload(scan_result)
        capability_types = [cap["capability_type"].value for cap in capabilities]
        assert "docker" not in capability_types
        assert "docker_compose" not in capability_types
        assert "docker_swarm" not in capability_types

    def test_empty_scan_creates_no_capabilities(self) -> None:
        scan_result = ScanResult(
            host="test-host",
            scan_date=datetime.now(timezone.utc),
            success=True,
            docker=None,
            virtualization={},
            kubernetes={},
            errors=[],
        )
        capabilities = build_capabilities_payload(scan_result)
        assert len(capabilities) == 0

    def test_container_runtimes_included(self) -> None:
        scan_result = ScanResult(
            host="test-host",
            scan_date=datetime.now(timezone.utc),
            success=True,
            docker=None,
            virtualization={},
            kubernetes={},
            container_runtimes={
                "lxc": ContainerRuntimeInfo(
                    available=True,
                    version="5.0.3",
                    install_method="package",
                ),
                "lxd": ContainerRuntimeInfo(available=False),
                "incus": ContainerRuntimeInfo(
                    available=True,
                    version="6.0.1",
                    install_method="snap",
                    socket=SocketInfo(
                        path="/var/lib/incus/unix.socket",
                        accessible=True,
                        mode="system",
                    ),
                ),
                "containerd": ContainerRuntimeInfo(available=False),
            },
            errors=[],
        )
        capabilities = build_capabilities_payload(scan_result)
        capability_types = [cap["capability_type"].value for cap in capabilities]

        assert "lxc" in capability_types
        assert "incus" in capability_types
        assert "lxd" not in capability_types
        assert "containerd" not in capability_types

        # Check incus has socket details
        incus_cap = next(
            c for c in capabilities if c["capability_type"].value == "incus"
        )
        assert incus_cap["details"]["install_method"] == "snap"
        assert incus_cap["details"]["socket"]["path"] == "/var/lib/incus/unix.socket"

    def test_oci_tools_included(self) -> None:
        scan_result = ScanResult(
            host="test-host",
            scan_date=datetime.now(timezone.utc),
            success=True,
            docker=None,
            virtualization={},
            kubernetes={},
            oci_tools={
                "runc": ToolInfo(available=True, version="1.1.12", details=None),
                "crun": ToolInfo(available=False, version=None, details=None),
                "buildah": ToolInfo(available=True, version="1.33.3", details=None),
                "skopeo": ToolInfo(available=True, version="1.15.0", details=None),
                "podman_compose": ToolInfo(available=False, version=None, details=None),
            },
            errors=[],
        )
        capabilities = build_capabilities_payload(scan_result)
        capability_types = [cap["capability_type"].value for cap in capabilities]

        assert "runc" in capability_types
        assert "buildah" in capability_types
        assert "skopeo" in capability_types
        assert "crun" not in capability_types
        assert "podman_compose" not in capability_types

    def test_docker_compose_available_is_included(self) -> None:
        scan_result = ScanResult(
            host="test-host",
            scan_date=datetime.now(timezone.utc),
            success=True,
            docker=DockerCapabilities(
                installed=True,
                version="24.0.0",
                running=True,
                socket_accessible=True,
                compose=DockerComposeInfo(
                    available=True, version="2.24.0", plugin_based=True
                ),
                swarm=None,
            ),
            virtualization={},
            kubernetes={},
            errors=[],
        )
        capabilities = build_capabilities_payload(scan_result)
        capability_types = [cap["capability_type"].value for cap in capabilities]
        assert "docker" in capability_types
        assert "docker_compose" in capability_types
        assert "docker_swarm" not in capability_types

    def test_virsh_and_multipass_mapped(self) -> None:
        scan_result = ScanResult(
            host="test-host",
            scan_date=datetime.now(timezone.utc),
            success=True,
            docker=None,
            virtualization={
                "virsh": ToolInfo(available=True, version="9.0.0", details=None),
                "multipass": ToolInfo(available=True, version="1.13.0", details=None),
            },
            kubernetes={},
            errors=[],
        )
        capabilities = build_capabilities_payload(scan_result)
        capability_types = [cap["capability_type"].value for cap in capabilities]
        assert "virsh" in capability_types
        assert "multipass" in capability_types

    def test_helm_mapped_from_kubernetes(self) -> None:
        scan_result = ScanResult(
            host="test-host",
            scan_date=datetime.now(timezone.utc),
            success=True,
            docker=None,
            virtualization={},
            kubernetes={
                "helm": ToolInfo(available=True, version="3.14.0", details=None),
            },
            errors=[],
        )
        capabilities = build_capabilities_payload(scan_result)
        capability_types = [cap["capability_type"].value for cap in capabilities]
        assert "helm" in capability_types


# ---------------------------------------------------------------------------
# Key mapping helpers
# ---------------------------------------------------------------------------

class TestKeyMapping:
    """Test key-to-capability mapping functions."""

    def test_virtualization_key_mapping(self) -> None:
        assert map_virtualization_key("libvirt") is not None
        assert map_virtualization_key("virsh") is not None
        assert map_virtualization_key("multipass") is not None
        assert map_virtualization_key("virt_install") is None

    def test_kubernetes_key_mapping(self) -> None:
        assert map_kubernetes_key("helm") is not None
        assert map_kubernetes_key("kubectl") is not None
        assert map_kubernetes_key("unknown") is None

    def test_runtime_key_mapping(self) -> None:
        assert map_runtime_key("lxc") is not None
        assert map_runtime_key("lxd") is not None
        assert map_runtime_key("incus") is not None
        assert map_runtime_key("containerd") is not None
        assert map_runtime_key("docker") is None

    def test_oci_key_mapping(self) -> None:
        assert map_oci_key("runc") is not None
        assert map_oci_key("crun") is not None
        assert map_oci_key("buildah") is not None
        assert map_oci_key("skopeo") is not None
        assert map_oci_key("podman_compose") is not None


# ---------------------------------------------------------------------------
# Socket storage in DockerCapabilities & discovered_sockets
# ---------------------------------------------------------------------------

class TestSocketStorage:
    """Verify that sockets are stored in capabilities and in discovered_sockets."""

    def test_docker_capabilities_stores_socket(self) -> None:
        """DockerCapabilities should carry the socket field."""
        sock = SocketInfo(path="/var/run/docker.sock", accessible=True, mode="system")
        caps = DockerCapabilities(
            installed=True,
            version="24.0.0",
            running=True,
            socket_accessible=True,
            socket=sock,
        )
        assert caps.socket is not None
        assert caps.socket.path == "/var/run/docker.sock"
        assert caps.socket.mode == "system"

    def test_docker_capabilities_socket_defaults_none(self) -> None:
        """Socket field should default to None."""
        caps = DockerCapabilities(installed=True, version="24.0.0")
        assert caps.socket is None

    def test_discovered_sockets_populated_from_docker(self) -> None:
        """ScanResult.discovered_sockets should contain the Docker socket."""
        sock = SocketInfo(path="/var/run/docker.sock", accessible=True, mode="system")
        scan_result = ScanResult(
            host="localhost",
            scan_date=datetime.now(timezone.utc),
            success=True,
            docker=DockerCapabilities(
                installed=True,
                version="24.0.0",
                running=True,
                socket_accessible=True,
                socket=sock,
            ),
            discovered_sockets={"docker": sock},
        )
        assert "docker" in scan_result.discovered_sockets
        assert scan_result.discovered_sockets["docker"].path == "/var/run/docker.sock"

    def test_discovered_sockets_from_container_runtimes(self) -> None:
        """discovered_sockets should contain sockets from container runtimes."""
        lxd_sock = SocketInfo(
            path="/var/snap/lxd/common/lxd/unix.socket",
            accessible=True,
            mode="system",
        )
        scan_result = ScanResult(
            host="localhost",
            scan_date=datetime.now(timezone.utc),
            success=True,
            docker=None,
            container_runtimes={
                "lxd": ContainerRuntimeInfo(
                    available=True,
                    version="5.21",
                    socket=lxd_sock,
                    install_method="snap",
                ),
            },
            discovered_sockets={"lxd": lxd_sock},
        )
        assert "lxd" in scan_result.discovered_sockets
        assert scan_result.discovered_sockets["lxd"].path == "/var/snap/lxd/common/lxd/unix.socket"

    def test_discovered_sockets_from_virtualization(self) -> None:
        """discovered_sockets should contain sockets from virtualization tools."""
        libvirt_sock = SocketInfo(
            path="/var/run/libvirt/libvirt-sock",
            accessible=True,
            mode="system",
        )
        scan_result = ScanResult(
            host="localhost",
            scan_date=datetime.now(timezone.utc),
            success=True,
            docker=None,
            virtualization={
                "libvirt": ToolInfo(
                    available=True,
                    version="9.0.0",
                    details={"socket": libvirt_sock.model_dump()},
                ),
            },
            discovered_sockets={"libvirt": libvirt_sock},
        )
        assert "libvirt" in scan_result.discovered_sockets

    def test_build_payload_includes_docker_socket(self) -> None:
        """build_capabilities_payload should include socket info in docker details."""
        sock = SocketInfo(path="/var/run/docker.sock", accessible=True, mode="system")
        scan_result = ScanResult(
            host="localhost",
            scan_date=datetime.now(timezone.utc),
            success=True,
            docker=DockerCapabilities(
                installed=True,
                version="24.0.0",
                running=True,
                socket_accessible=True,
                socket=sock,
            ),
            virtualization={},
            kubernetes={},
            errors=[],
        )
        capabilities = build_capabilities_payload(scan_result)
        docker_cap = next(
            c for c in capabilities if c["capability_type"].value == "docker"
        )
        assert "socket" in docker_cap["details"]
        assert docker_cap["details"]["socket"]["path"] == "/var/run/docker.sock"
        assert docker_cap["details"]["socket"]["mode"] == "system"

    def test_build_payload_without_docker_socket(self) -> None:
        """build_capabilities_payload should work when no socket is present."""
        scan_result = ScanResult(
            host="localhost",
            scan_date=datetime.now(timezone.utc),
            success=True,
            docker=DockerCapabilities(
                installed=True,
                version="24.0.0",
                running=False,
                socket_accessible=False,
            ),
            virtualization={},
            kubernetes={},
            errors=[],
        )
        capabilities = build_capabilities_payload(scan_result)
        docker_cap = next(
            c for c in capabilities if c["capability_type"].value == "docker"
        )
        assert "socket" not in docker_cap["details"]

    def test_multiple_sockets_in_discovered_sockets(self) -> None:
        """discovered_sockets can hold multiple sockets simultaneously."""
        docker_sock = SocketInfo(path="/var/run/docker.sock", accessible=True, mode="system")
        lxd_sock = SocketInfo(path="/var/lib/lxd/unix.socket", accessible=True, mode="system")
        scan_result = ScanResult(
            host="localhost",
            scan_date=datetime.now(timezone.utc),
            success=True,
            docker=DockerCapabilities(
                installed=True, version="24.0.0", socket=docker_sock,
            ),
            container_runtimes={
                "lxd": ContainerRuntimeInfo(available=True, socket=lxd_sock),
            },
            discovered_sockets={"docker": docker_sock, "lxd": lxd_sock},
        )
        assert len(scan_result.discovered_sockets) == 2
        assert "docker" in scan_result.discovered_sockets
        assert "lxd" in scan_result.discovered_sockets
