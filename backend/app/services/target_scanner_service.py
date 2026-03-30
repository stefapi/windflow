"""
Service for scanning deployment targets capabilities (local or remote).

Provides detection of virtualization, container, and orchestration tooling,
including hardware platform information, socket topology, and CLI availability.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Protocol,
    TypeVar,
)

import asyncssh
from asyncssh import ConnectionLost
from sqlalchemy.ext.asyncio import AsyncSession

from ..enums.target import AccessLevel, CapabilityType
from ..models.target import Target
from ..schemas.target import TargetAccessProfile
from ..schemas.target_scan import (
    ContainerRuntimeInfo,
    DockerCapabilities,
    DockerComposeInfo,
    DockerSwarmInfo,
    OSInfo,
    PlatformArchitecture,
    PlatformInfo,
    ScanRequest,
    ScanResult,
    SocketInfo,
    ToolInfo,
)
from .target_service import TargetService

try:  # pragma: no cover - defensive import
    import docker
    from docker.errors import DockerException
except ImportError:  # pragma: no cover - optional dependency
    docker = None  # type: ignore[assignment]
    DockerException = Exception  # type: ignore

try:  # pragma: no cover - defensive import
    import libvirt  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    libvirt = None  # type: ignore[misc]


class CommandExecutionError(Exception):
    """Raised when a command execution fails."""

    def __init__(self, command: str, exit_status: int, stderr: str):
        message = (
            f"Command '{command}' exited with status {exit_status}. "
            f"Stderr: {stderr.strip()}"
        )
        super().__init__(message)
        self.command = command
        self.exit_status = exit_status
        self.stderr = stderr.strip()


@dataclass(slots=True)
class CommandResult:
    """Holds the result of a command execution."""

    exit_status: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.exit_status == 0

    def stripped_stdout(self) -> str:
        return self.stdout.strip()

    def stripped_stderr(self) -> str:
        return self.stderr.strip()


class CommandExecutor(Protocol):
    """Protocol describing a command executor implementation."""

    async def run(  # noqa: E704
        self, command: str, timeout: int = 30, require_success: bool = False
    ) -> CommandResult: ...


class LocalCommandExecutor:
    """Execute commands on the local machine using subprocess."""

    def __init__(
        self, sudo_user: str | None = None, sudo_password: str | None = None
    ):
        self._sudo_user = sudo_user
        self._sudo_password = sudo_password

    async def run(
        self, command: str, timeout: int = 30, require_success: bool = False
    ) -> CommandResult:
        wrapped_command = self._wrap_with_sudo(command) if self._sudo_user else command
        try:
            process = await asyncio.create_subprocess_shell(
                wrapped_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE if self._sudo_user else None,
            )
            if self._sudo_user and self._sudo_password:
                password_payload = f"{self._sudo_password}\n".encode("utf-8")
                if process.stdin:
                    process.stdin.write(password_payload)
                    await process.stdin.drain()
                    process.stdin.close()

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            raise CommandExecutionError(
                command,
                exit_status=124,
                stderr=f"Command timed out after {timeout}s: {exc}",
            ) from exc

        stdout = stdout_bytes.decode("utf-8", errors="ignore")
        stderr = stderr_bytes.decode("utf-8", errors="ignore")
        result = CommandResult(process.returncode, stdout, stderr)

        if require_success and not result.success:
            raise CommandExecutionError(command, result.exit_status, result.stderr)
        return result

    def _wrap_with_sudo(self, command: str) -> str:
        sudo_parts = ["sudo", "-S", "-p", "''", "-u", self._sudo_user]
        return " ".join(sudo_parts + [command])


class SSHCommandExecutor:
    """Execute commands on a remote host via asyncssh."""

    def __init__(
        self,
        connection: asyncssh.SSHClientConnection,
        sudo_user: str | None = None,
        sudo_password: str | None = None,
    ):
        self._connection = connection
        self._sudo_user = sudo_user
        self._sudo_password = sudo_password

    async def run(
        self, command: str, timeout: int = 30, require_success: bool = False
    ) -> CommandResult:
        wrapped_command = self._wrap_with_sudo(command) if self._sudo_user else command
        input_payload = None
        if self._sudo_user and self._sudo_password:
            input_payload = f"{self._sudo_password}\n"

        try:
            completed = await asyncio.wait_for(
                self._connection.run(
                    wrapped_command,
                    input=input_payload,
                    check=False,
                    encoding="utf-8",
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise CommandExecutionError(
                command,
                exit_status=124,
                stderr=f"Remote command timed out after {timeout}s",
            ) from exc
        except (asyncssh.Error, ConnectionLost) as exc:
            raise CommandExecutionError(
                command, exit_status=255, stderr=f"SSH execution failed: {exc}"
            ) from exc

        result = CommandResult(
            completed.exit_status, completed.stdout or "", completed.stderr or ""
        )
        if require_success and not result.success:
            raise CommandExecutionError(command, result.exit_status, result.stderr)
        return result

    def _wrap_with_sudo(self, command: str) -> str:
        sudo_parts = ["sudo", "-S", "-p", "''", "-u", self._sudo_user]
        return " ".join(sudo_parts + [command])


Parser = Callable[[str], dict[str, Any]]
T = TypeVar("T")


# ---------------------------------------------------------------------------
# Socket topology
# ---------------------------------------------------------------------------

class SocketProbe:
    """Centralized socket path definitions and probing utilities.

    Maps every container/VM tool to its possible Unix socket locations,
    covering system (root), rootless (user), session, and snap variants.
    """

    SOCKET_PATHS: dict[str, dict[str, list[str]]] = {
        "docker": {
            "system": ["/var/run/docker.sock"],
            "rootless": ["/run/user/{uid}/docker.sock"],
        },
        "podman": {
            "system": ["/run/podman/podman.sock"],
            "rootless": ["/run/user/{uid}/podman/podman.sock"],
        },
        "lxd": {
            "system": [
                "/var/lib/lxd/unix.socket",
                "/var/snap/lxd/common/lxd/unix.socket",
            ],
        },
        "incus": {
            "system": [
                "/var/lib/incus/unix.socket",
                "/var/snap/incus/common/incus/unix.socket",
            ],
        },
        "libvirt": {
            "system": ["/var/run/libvirt/libvirt-sock"],
            "session": ["/run/user/{uid}/libvirt/libvirt-sock"],
        },
        "lxc": {
            "system": ["/run/lxc.socket"],
        },
        "containerd": {
            "system": [
                "/run/containerd/containerd.sock",
                "/run/k3s/containerd/containerd.sock",
            ],
        },
    }

    @classmethod
    def _resolve_uid_paths(cls, paths: list[str]) -> list[str]:
        """Replace ``{uid}`` placeholders with the current UID."""
        uid = os.getuid()
        return [p.format(uid=uid) for p in paths]

    @classmethod
    async def probe(
        cls,
        executor: CommandExecutor,
        tool: str,
        timeout: int = 5,
    ) -> SocketInfo | None:
        """Probe socket paths for *tool* and return the first match.

        Tries system paths first, then rootless/session paths.
        Returns a :class:`SocketInfo` even when the socket exists but is not
        readable by the current user (``exists=True, accessible=False``).
        This is important for tools like LXD/Incus whose control sockets are
        group-owned (``lxd``, ``incus``) and may not be readable.
        """
        paths_by_mode = cls.SOCKET_PATHS.get(tool)
        if not paths_by_mode:
            return None

        # Order: system → rootless → session
        probe_order: list[tuple[str, list[str]]] = []
        for mode in ("system", "rootless", "session"):
            raw = paths_by_mode.get(mode)
            if raw:
                resolved = cls._resolve_uid_paths(raw) if "{uid}" in str(raw) else raw
                probe_order.append((mode, resolved))

        for mode, paths in probe_order:
            for socket_path in paths:
                # Step 1: check if the socket file exists
                exists_result = await executor.run(
                    f"test -S {socket_path}",
                    timeout=timeout,
                )
                if not exists_result.success:
                    continue

                # Socket exists — check readability
                accessible_result = await executor.run(
                    f"test -r {socket_path}",
                    timeout=timeout,
                )
                return SocketInfo(
                    path=socket_path,
                    exists=True,
                    accessible=accessible_result.success,
                    mode=mode,
                )
        return None

    @classmethod
    async def probe_local(cls, tool: str) -> SocketInfo | None:
        """Fast local-only probe (no subprocess, just ``Path`` checks).

        Returns a :class:`SocketInfo` even when the socket exists but is not
        readable by the current user.
        """
        paths_by_mode = cls.SOCKET_PATHS.get(tool)
        if not paths_by_mode:
            return None

        for mode in ("system", "rootless", "session"):
            raw = paths_by_mode.get(mode)
            if not raw:
                continue
            resolved = cls._resolve_uid_paths(raw) if "{uid}" in str(raw) else raw
            for socket_path in resolved:
                p = Path(socket_path)
                if p.is_socket():
                    return SocketInfo(
                        path=socket_path,
                        exists=True,
                        accessible=os.access(socket_path, os.R_OK),
                        mode=mode,
                    )
        return None


# ---------------------------------------------------------------------------
# Environment detector
# ---------------------------------------------------------------------------

class ContainerEnvironmentDetector:
    """Detects runtime environment characteristics."""

    _DOCKERENV = Path("/.dockerenv")

    @staticmethod
    def is_in_container() -> bool:
        """Returns True if running inside a container."""
        if ContainerEnvironmentDetector._DOCKERENV.exists():
            return True
        try:
            with open("/proc/1/cgroup", encoding="utf-8") as cgroup_file:
                content = cgroup_file.read().lower()
            return any(
                token in content for token in ("docker", "containerd", "kubepods")
            )
        except FileNotFoundError:  # pragma: no cover - uncommon
            return False


# ---------------------------------------------------------------------------
# Docker socket client
# ---------------------------------------------------------------------------

class DockerSocketClient:
    """Collects Docker capabilities through the mounted Unix socket."""

    def __init__(self, socket_path: str = "/var/run/docker.sock"):
        self.socket_path = socket_path

    async def is_available(self) -> bool:
        """Returns True if the Docker socket is accessible."""
        if docker is None or not Path(self.socket_path).exists():
            return False
        return await asyncio.to_thread(self._can_connect)

    async def collect_capabilities(self) -> DockerCapabilities | None:
        """Collects Docker capabilities via the socket."""
        if docker is None:
            return None
        return await asyncio.to_thread(self._collect_capabilities_sync)

    def _create_client(self):
        return docker.DockerClient(base_url=f"unix://{self.socket_path}")  # type: ignore[no-any-return]

    def _can_connect(self) -> bool:
        client = None
        try:
            client = self._create_client()
            client.ping()
            return True
        except DockerException:
            return False
        finally:
            if client is not None:
                client.close()

    def _collect_capabilities_sync(self) -> DockerCapabilities | None:
        client = None
        try:
            client = self._create_client()
            info = client.info()
            version_info = client.version()
            swarm_info = info.get("Swarm") if isinstance(info, dict) else None

            return DockerCapabilities(
                installed=True,
                version=(
                    version_info.get("Version")
                    if isinstance(version_info, dict)
                    else None
                ),
                running=True,
                socket_accessible=True,
                compose=None,
                swarm=self._build_swarm_info(swarm_info),
            )
        except DockerException:
            return None
        finally:
            if client is not None:
                client.close()

    @staticmethod
    def _build_swarm_info(
        swarm_info: dict[str, Any | None],
    ) -> DockerSwarmInfo | None:
        if not swarm_info:
            return None

        local_state = swarm_info.get("LocalNodeState")
        available = local_state not in {None, "inactive"}
        active = local_state == "active"
        node_role: str | None = None
        if available:
            node_role = "manager" if swarm_info.get("ControlAvailable") else "worker"

        return DockerSwarmInfo(
            available=available, active=active, node_role=node_role, details=swarm_info
        )


# ---------------------------------------------------------------------------
# Libvirt socket client
# ---------------------------------------------------------------------------

class LibvirtSocketClient:
    """Collects libvirt (KVM/QEMU) capabilities via the libvirt socket."""

    def __init__(
        self,
        socket_path: str = "/var/run/libvirt/libvirt-sock",
        uri: str = "qemu:///system",
    ):
        self.socket_path = socket_path
        self.uri = uri

    async def is_available(self) -> bool:
        """Returns True if the libvirt socket is accessible."""
        if libvirt is None or not Path(self.socket_path).exists():
            return False
        return await asyncio.to_thread(self._can_connect)

    async def collect_details(self) -> dict[str, Any]:
        """Collects host and VM information via libvirt."""
        if libvirt is None:
            return {}
        return await asyncio.to_thread(self._collect_details_sync)

    def _can_connect(self) -> bool:
        connection = None
        try:
            connection = libvirt.openReadOnly(self.uri)
            return connection is not None
        except libvirt.libvirtError:
            return False
        finally:
            if connection is not None:
                connection.close()

    def _collect_details_sync(self) -> dict[str, Any]:
        connection = None
        try:
            connection = libvirt.openReadOnly(self.uri)
            if connection is None:
                return {}

            version = connection.getVersion()
            lib_version = connection.getLibVersion()
            host_info = connection.getInfo()

            domains_summary: list[dict[str, Any]] = []
            for domain in connection.listAllDomains():
                info = domain.info()
                domains_summary.append(
                    {
                        "id": domain.ID() if domain.ID() != -1 else None,
                        "name": domain.name(),
                        "uuid": domain.UUIDString(),
                        "state": info[0],
                        "max_memory_mb": info[1] // 1024,
                        "memory_mb": info[2] // 1024,
                        "vcpus": info[3],
                    }
                )

            return {
                "version": self._format_version(version),
                "lib_version": self._format_version(lib_version),
                "host": {
                    "model": host_info[0],
                    "memory_mb": host_info[1],
                    "cpus": host_info[2],
                    "mhz": host_info[3],
                },
                "domains": domains_summary,
            }
        except libvirt.libvirtError:
            return {}
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _format_version(value: int) -> str | None:
        if not value:
            return None
        major = value // 1_000_000
        minor = (value // 1_000) % 1_000
        patch = value % 1_000
        return f"{major}.{minor}.{patch}"


# ---------------------------------------------------------------------------
# Main scanner service
# ---------------------------------------------------------------------------

class TargetScannerService:
    """Service capable of scanning deployment targets for capabilities."""

    _DEFAULT_TIMEOUT = 30

    async def scan_localhost(self) -> ScanResult:
        """
        Scan the local machine using shell execution or mounted sockets.

        Returns:
            ScanResult: Detected capabilities for localhost.
        """
        executor: CommandExecutor = LocalCommandExecutor()
        return await self._run_scan(executor, host="localhost")

    async def scan_remote(self, scan_request: ScanRequest) -> ScanResult:
        """
        Scan a remote machine via SSH.

        Args:
            scan_request: Parameters describing the remote host.

        Returns:
            ScanResult: Detected capabilities for the remote host.

        Raises:
            CommandExecutionError: When SSH connection or commands fail.
        """
        ssh_kwargs: dict = {
            "host": scan_request.host,
            "port": scan_request.port,
            "username": scan_request.username,
            "known_hosts": None,
        }
        # Support both password and SSH key authentication
        if scan_request.ssh_private_key:
            ssh_kwargs["client_keys"] = [scan_request.ssh_private_key]
            if getattr(scan_request, "ssh_private_key_passphrase", None):
                ssh_kwargs["passphrase"] = scan_request.ssh_private_key_passphrase
        else:
            ssh_kwargs["password"] = scan_request.password
        try:
            async with asyncssh.connect(**ssh_kwargs) as connection:
                executor = SSHCommandExecutor(
                    connection,
                    sudo_user=scan_request.sudo_user,
                    sudo_password=scan_request.sudo_password,
                )
                return await self._run_scan(executor, host=scan_request.host)
        except (OSError, asyncssh.Error) as exc:
            raise CommandExecutionError(
                "ssh-connect", exit_status=255, stderr=f"SSH connection failed: {exc}"
            ) from exc

    async def scan_and_update_target(self, target: Target, db: AsyncSession) -> Target:
        """
        Scan a stored target and persist discovered capabilities.

        This method performs:
        1. A standard scan (with sudo if configured) → elevated capabilities
        2. An access profile detection → determines access level
        3. If access is elevated (root/sudo), a second scan without sudo → standard capabilities
        4. Computes the difference (elevated - standard) → elevated-only capabilities

        Args:
            target: Target instance to scan.
            db: Database session.

        Returns:
            Target: Updated target with new capabilities and access profile.

        Raises:
            ValueError: When credentials are missing for remote scan.
        """
        await TargetService.mark_scan_in_progress(db, target)

        is_localhost = target.host in {"localhost", "127.0.0.1"}
        try:
            credentials = target.credentials or {}
            sudo_user = credentials.get("sudo_user")
            sudo_password = credentials.get("sudo_password")
            sudo_enabled = credentials.get("sudo_enabled", False)

            if is_localhost:
                scan_result = await self.scan_localhost()

                # Detect access profile
                local_executor: CommandExecutor = LocalCommandExecutor()
                access_profile = await self.detect_access_profile(
                    executor=local_executor,
                    ssh_user=None,
                    sudo_user=sudo_user,
                    sudo_password=sudo_password,
                    sudo_enabled=sudo_enabled,
                    detection_method="scan",
                )

                # Double scan for localhost: run without sudo to get standard capabilities
                standard_caps, elevated_caps = await self._perform_double_scan(
                    access_profile=access_profile,
                    is_localhost=True,
                    host="localhost",
                    credentials=credentials,
                )
            else:
                username = credentials.get("username")
                if not username:
                    raise ValueError(
                        "Target credentials must contain 'username' for remote scanning."
                    )

                scan_request = ScanRequest(
                    host=target.host,
                    port=target.port or 22,
                    username=username,
                    password=credentials.get("password"),
                    ssh_private_key=credentials.get("ssh_private_key"),
                    ssh_private_key_passphrase=credentials.get("ssh_private_key_passphrase"),
                    sudo_user=sudo_user,
                    sudo_password=sudo_password,
                )
                scan_result = await self.scan_remote(scan_request)

                # Detect access profile via SSH
                ssh_kwargs: dict = {
                    "host": scan_request.host,
                    "port": scan_request.port,
                    "username": scan_request.username,
                    "known_hosts": None,
                }
                if scan_request.ssh_private_key:
                    ssh_kwargs["client_keys"] = [scan_request.ssh_private_key]
                    if scan_request.ssh_private_key_passphrase:
                        ssh_kwargs["passphrase"] = scan_request.ssh_private_key_passphrase
                else:
                    ssh_kwargs["password"] = scan_request.password

                async with asyncssh.connect(**ssh_kwargs) as connection:
                    ssh_executor = SSHCommandExecutor(connection)
                    access_profile = await self.detect_access_profile(
                        executor=ssh_executor,
                        ssh_user=username,
                        sudo_user=sudo_user,
                        sudo_password=sudo_password,
                        sudo_enabled=sudo_enabled,
                        detection_method="scan",
                    )

                # Double scan for remote: run without sudo to get standard capabilities
                standard_caps, elevated_caps = await self._perform_double_scan(
                    access_profile=access_profile,
                    is_localhost=False,
                    host=target.host,
                    credentials=credentials,
                )

            # Fill access profile with capability lists
            access_profile.standard_capabilities = standard_caps
            access_profile.elevated_capabilities = elevated_caps

            # Build capabilities from the main scan result (with sudo if configured)
            capabilities = self.build_capabilities_payload(scan_result)

            platform_payload = (
                scan_result.platform.model_dump(mode="json")
                if scan_result.platform
                else None
            )
            os_payload = (
                scan_result.os.model_dump(mode="json") if scan_result.os else None
            )

            await TargetService.apply_scan_result(
                db=db,
                target=target,
                capabilities=capabilities,
                scan_date=scan_result.scan_date,
                success=scan_result.success,
                platform_info=platform_payload,
                os_info=os_payload,
                access_profile=access_profile.model_dump(mode="json"),
            )
            return target
        except Exception:  # noqa: B902
            await TargetService.mark_scan_failed(db, target)
            raise

    async def _perform_double_scan(
        self,
        access_profile: TargetAccessProfile,
        is_localhost: bool,
        host: str,
        credentials: dict,
    ) -> tuple[list[str], list[str]]:
        """Perform a double scan to distinguish standard vs elevated capabilities.

        If access_level is LIMITED (no sudo), standard and elevated lists are
        identical (the single scan result). Otherwise, a second scan is run
        without sudo to capture what the standard user can see.

        Args:
            access_profile: The already-detected access profile.
            is_localhost: Whether the target is localhost.
            host: Target hostname.
            credentials: Target credentials dict.

        Returns:
            Tuple of (standard_capabilities, elevated_capabilities) as name lists.
        """
        if access_profile.access_level == AccessLevel.LIMITED or access_profile.is_root_user:
            # For root or limited: no difference between standard and elevated
            # Root user: everything is "standard"
            # Limited user: everything is "standard" (no elevation possible)
            return [], []

        # Run a second scan WITHOUT sudo to get standard user capabilities
        try:
            if is_localhost:
                standard_executor: CommandExecutor = LocalCommandExecutor()
                standard_scan = await self._run_scan(standard_executor, host=host)
            else:
                ssh_kwargs: dict = {
                    "host": host,
                    "port": credentials.get("port", 22),
                    "username": credentials.get("username"),
                    "known_hosts": None,
                }
                if credentials.get("ssh_private_key"):
                    ssh_kwargs["client_keys"] = [credentials["ssh_private_key"]]
                    if credentials.get("ssh_private_key_passphrase"):
                        ssh_kwargs["passphrase"] = credentials["ssh_private_key_passphrase"]
                else:
                    ssh_kwargs["password"] = credentials.get("password")

                async with asyncssh.connect(**ssh_kwargs) as connection:
                    standard_executor = SSHCommandExecutor(connection)
                    standard_scan = await self._run_scan(standard_executor, host=host)

            standard_payload = self.build_capabilities_payload(standard_scan)
            standard_names = self.extract_capability_names(standard_payload)
            return standard_names, []
        except Exception:
            # If second scan fails, return empty lists
            return [], []

    # ------------------------------------------------------------------
    # Access Profile detection
    # ------------------------------------------------------------------

    async def detect_access_profile(
        self,
        executor: CommandExecutor,
        ssh_user: str | None = None,
        sudo_user: str | None = None,
        sudo_password: str | None = None,
        sudo_enabled: bool = False,
        detection_method: str = "scan",
    ) -> TargetAccessProfile:
        """Detect the access level of the current executor on the target.

        Steps:
        1. Check whoami → is root?
        2. Check ``which sudo`` → sudo binary exists?
        3. If not root, sudo is enabled, and sudo binary exists:
           a. If sudo_user + sudo_password provided → test ``sudo -S -u <user> whoami``
           b. If sudo_user but no password → test ``sudo -n -u <user> whoami`` (passwordless)
           c. If no sudo_user → try passwordless sudo to root
        4. Build the TargetAccessProfile with the results.

        Args:
            executor: Command executor (local or SSH).
            ssh_user: Username used for SSH connection (for metadata).
            sudo_user: Sudo user from credentials (if configured).
            sudo_password: Sudo password from credentials (if configured).
            sudo_enabled: Whether sudo escalation is explicitly enabled by the user.
            detection_method: Origin of detection ("scan" or "discovery").

        Returns:
            TargetAccessProfile with detected access information.
        """
        now = datetime.now(timezone.utc)

        # 1. Determine who we are connected as
        whoami_result = await executor.run("whoami", timeout=10)
        connected_user = whoami_result.stripped_stdout() if whoami_result.success else (ssh_user or "unknown")
        is_root = connected_user == "root"

        # 2. Check if sudo binary exists
        sudo_available = False
        which_sudo = await executor.run("which sudo 2>/dev/null", timeout=10)
        if which_sudo.success and which_sudo.stripped_stdout():
            sudo_available = True

        # 3. Determine access level
        sudo_verified = False
        sudo_passwordless = False
        effective_sudo_user: str | None = None
        access_level = AccessLevel.LIMITED

        if is_root:
            # Direct root access
            access_level = AccessLevel.ROOT
            effective_sudo_user = "root"
        elif sudo_enabled and sudo_available:
            # Sudo is explicitly enabled by user and sudo binary exists
            if sudo_user and sudo_password:
                # Test: sudo -S -u <user> whoami with password piped via stdin
                sudo_test = await self._test_sudo_with_password(
                    executor, sudo_user, sudo_password,
                )
                if sudo_test.success and sudo_test.stripped_stdout():
                    effective_sudo_user = sudo_test.stripped_stdout()
                    sudo_verified = True
                    access_level = AccessLevel.SUDO
            elif sudo_user and not sudo_password:
                # Try passwordless sudo to the specified user
                sudo_test = await executor.run(
                    f"sudo -n -u {sudo_user} whoami 2>/dev/null",
                    timeout=15,
                )
                if sudo_test.success and sudo_test.stripped_stdout():
                    effective_sudo_user = sudo_test.stripped_stdout()
                    sudo_verified = True
                    sudo_passwordless = True
                    access_level = AccessLevel.SUDO_PASSWORDLESS
            else:
                # No sudo_user configured → try passwordless sudo to root
                sudo_test = await executor.run(
                    "sudo -n whoami 2>/dev/null",
                    timeout=15,
                )
                if sudo_test.success and sudo_test.stripped_stdout():
                    effective_sudo_user = sudo_test.stripped_stdout()
                    sudo_verified = True
                    sudo_passwordless = True
                    access_level = AccessLevel.SUDO_PASSWORDLESS

        # 4. Determine if we can install packages
        # Only root can install packages — sudo to a non-root account does NOT
        # grant package installation capability.
        can_install_packages = is_root or (
            sudo_verified and effective_sudo_user == "root"
        )

        return TargetAccessProfile(
            ssh_user=connected_user,
            is_root_user=is_root,
            sudo_available=sudo_available,
            sudo_verified=sudo_verified,
            sudo_passwordless=sudo_passwordless,
            sudo_user=effective_sudo_user,
            access_level=access_level,
            can_install_packages=can_install_packages,
            standard_capabilities=[],  # Filled after double scan
            elevated_capabilities=[],  # Filled after double scan
            detected_at=now,
            detection_method=detection_method,
        )

    async def _test_sudo_with_password(
        self,
        executor: CommandExecutor,
        sudo_user: str,
        sudo_password: str,
    ) -> CommandResult:
        """Test sudo with password, using robust stdin piping.

        Works correctly for both local and SSH executors.
        Uses a heredoc-style approach to avoid shell escaping issues.
        """
        if isinstance(executor, LocalCommandExecutor):
            # For local execution, write password directly to stdin
            # This avoids shell escaping issues with echo pipe
            return await self._test_sudo_local_stdin(sudo_user, sudo_password)
        else:
            # For SSH, use echo pipe (asyncssh handles stdin properly)
            return await executor.run(
                f"echo '{sudo_password}' | sudo -S -p '' -u {sudo_user} whoami 2>/dev/null",
                timeout=15,
            )

    async def _test_sudo_local_stdin(
        self,
        sudo_user: str,
        sudo_password: str,
    ) -> CommandResult:
        """Test sudo locally by piping password through stdin.

        Uses subprocess directly instead of the executor to ensure
        the password is properly piped via stdin (not echo).
        """
        command = f"sudo -S -p '' -u {sudo_user} whoami"
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )
            password_bytes = f"{sudo_password}\n".encode("utf-8")
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(input=password_bytes),
                timeout=15,
            )
            stdout = stdout_bytes.decode("utf-8", errors="ignore")
            stderr = stderr_bytes.decode("utf-8", errors="ignore")
            return CommandResult(process.returncode, stdout, stderr)
        except asyncio.TimeoutError:
            process.kill()
            return CommandResult(124, "", "Command timed out")

    @staticmethod
    def extract_capability_names(capabilities_payload: list[dict[str, Any]]) -> list[str]:
        """Extract capability type names from a capabilities payload list.

        Args:
            capabilities_payload: List of capability dicts from ``build_capabilities_payload``.

        Returns:
            Sorted list of unique capability type names.
        """
        names: list[str] = []
        for cap in capabilities_payload:
            cap_type = cap.get("capability_type")
            if cap_type:
                # Handle both enum values and string values
                names.append(cap_type.value if hasattr(cap_type, "value") else str(cap_type))
        return sorted(set(names))

    # ------------------------------------------------------------------
    # Core scan pipeline
    # ------------------------------------------------------------------

    async def _run_scan(self, executor: CommandExecutor, host: str) -> ScanResult:
        errors: list[str] = []

        # Run all detection tasks concurrently for performance
        platform_task = self._safe_execute(
            self._detect_platform, executor, errors
        )
        os_task = self._safe_execute(self._detect_os, executor, errors)
        virtualization_task = self._safe_execute(
            self._detect_virtualization, executor, errors, default={}
        )
        docker_task = self._safe_execute(
            lambda exec_: self._detect_docker(exec_, host=host), executor, errors
        )
        kubernetes_task = self._safe_execute(
            self._detect_kubernetes, executor, errors, default={}
        )
        container_runtimes_task = self._safe_execute(
            self._detect_container_runtimes, executor, errors, default={}
        )
        oci_tools_task = self._safe_execute(
            self._detect_oci_tools, executor, errors, default={}
        )

        (
            platform_info,
            os_info,
            virtualization,
            docker_info,
            kubernetes,
            container_runtimes,
            oci_tools,
        ) = await asyncio.gather(
            platform_task,
            os_task,
            virtualization_task,
            docker_task,
            kubernetes_task,
            container_runtimes_task,
            oci_tools_task,
        )

        success = not errors

        # Build unified discovered_sockets map
        discovered_sockets: dict[str, SocketInfo] = {}

        # Docker socket
        if docker_info and docker_info.socket:
            discovered_sockets["docker"] = docker_info.socket

        # Virtualization sockets (podman, libvirt)
        for _vkey, _vinfo in (virtualization or {}).items():
            if isinstance(_vinfo, ToolInfo) and _vinfo.details:
                _sock_data = _vinfo.details.get("socket")
                if isinstance(_sock_data, dict):
                    try:
                        discovered_sockets[_vkey] = SocketInfo(**_sock_data)
                    except Exception:
                        pass
                elif isinstance(_sock_data, SocketInfo):
                    discovered_sockets[_vkey] = _sock_data

        # Container runtime sockets (lxc, lxd, incus, containerd)
        for _rkey, _rinfo in (container_runtimes or {}).items():
            if isinstance(_rinfo, ContainerRuntimeInfo) and _rinfo.socket:
                discovered_sockets[_rkey] = _rinfo.socket

        return ScanResult(
            host=host,
            scan_date=datetime.now(timezone.utc),
            success=success,
            platform=platform_info,
            os=os_info,
            virtualization=virtualization or {},
            docker=docker_info,
            kubernetes=kubernetes or {},
            container_runtimes=container_runtimes or {},
            oci_tools=oci_tools or {},
            discovered_sockets=discovered_sockets,
            errors=errors,
        )

    async def _safe_execute(
        self,
        func: Callable[[CommandExecutor], Awaitable[T]],
        executor: CommandExecutor,
        errors: list[str],
        default: T | None = None,
    ) -> T | None:
        try:
            return await func(executor)
        except CommandExecutionError as exc:
            errors.append(str(exc))
            return default
        except Exception as exc:  # noqa: B902
            errors.append(str(exc))
            return default

    # ------------------------------------------------------------------
    # Platform & OS detection
    # ------------------------------------------------------------------

    async def _detect_platform(self, executor: CommandExecutor) -> PlatformInfo:
        architecture = PlatformArchitecture.UNKNOWN
        cpu_model = None
        cpu_cores = None
        total_memory_gb = None

        arch_result = await executor.run("uname -m", timeout=self._DEFAULT_TIMEOUT)
        raw_arch = arch_result.stripped_stdout()
        architecture = self._map_architecture(raw_arch)

        cpu_model_cmds = [
            r"grep -m1 'model name' /proc/cpuinfo | cut -d':' -f2",
            "sysctl -n machdep.cpu.brand_string",
        ]
        for cmd in cpu_model_cmds:
            result = await executor.run(cmd, timeout=self._DEFAULT_TIMEOUT)
            if result.success and result.stripped_stdout():
                cpu_model = result.stripped_stdout()
                break

        cpu_cores_cmds = [
            "nproc",
            "sysctl -n hw.ncpu",
        ]
        for cmd in cpu_cores_cmds:
            result = await executor.run(cmd, timeout=self._DEFAULT_TIMEOUT)
            if result.success and result.stripped_stdout().isdigit():
                cpu_cores = int(result.stripped_stdout())
                break

        mem_cmds = [
            r"grep MemTotal /proc/meminfo | awk '{print $2}'",
            "sysctl -n hw.memsize",
        ]
        for cmd in mem_cmds:
            result = await executor.run(cmd, timeout=self._DEFAULT_TIMEOUT)
            if result.success and result.stripped_stdout():
                try:
                    memory_kb = float(result.stripped_stdout())
                    if "memsize" in cmd:
                        total_memory_gb = round(memory_kb / (1024**3), 2)
                    else:
                        total_memory_gb = round(memory_kb / (1024**1) / 1024, 2)
                    break
                except ValueError:
                    continue

        return PlatformInfo(
            architecture=architecture,
            cpu_model=cpu_model.strip() if cpu_model else None,
            cpu_cores=cpu_cores,
            total_memory_gb=total_memory_gb,
        )

    async def _detect_os(self, executor: CommandExecutor) -> OSInfo:
        system = "unknown"
        distribution = None
        version = None
        kernel = None

        sys_result = await executor.run("uname -s", timeout=self._DEFAULT_TIMEOUT)
        if sys_result.success and sys_result.stripped_stdout():
            system = sys_result.stripped_stdout()

        kernel_result = await executor.run("uname -r", timeout=self._DEFAULT_TIMEOUT)
        if kernel_result.success and kernel_result.stripped_stdout():
            kernel = kernel_result.stripped_stdout()

        os_release_result = await executor.run(
            "cat /etc/os-release", timeout=self._DEFAULT_TIMEOUT
        )
        if os_release_result.success and os_release_result.stdout:
            for line in os_release_result.stdout.splitlines():
                if line.startswith("NAME="):
                    distribution = self._strip_quotes(line.split("=", 1)[1])
                if line.startswith("VERSION="):
                    version = self._strip_quotes(line.split("=", 1)[1])

        if not distribution:
            lsb_result = await executor.run(
                "lsb_release -ds", timeout=self._DEFAULT_TIMEOUT
            )
            if lsb_result.success and lsb_result.stripped_stdout():
                distribution = self._strip_quotes(lsb_result.stripped_stdout())

        return OSInfo(
            system=system,
            distribution=distribution,
            version=version,
            kernel=kernel,
        )

    # ------------------------------------------------------------------
    # Virtualization detection
    # ------------------------------------------------------------------

    async def _detect_virtualization(
        self, executor: CommandExecutor
    ) -> dict[str, ToolInfo]:
        virtualization: dict[str, ToolInfo] = {}

        # --- libvirt socket detection (KVM/QEMU) ---
        libvirt_socket_info = await SocketProbe.probe(executor, "libvirt")
        if libvirt_socket_info is not None:
            libvirt_client = LibvirtSocketClient(
                socket_path=libvirt_socket_info.path,
                uri=(
                    "qemu:///session"
                    if libvirt_socket_info.mode == "session"
                    else "qemu:///system"
                ),
            )
            if await libvirt_client.is_available():
                libvirt_details = await libvirt_client.collect_details()
                virtualization["libvirt"] = ToolInfo(
                    available=True,
                    version=libvirt_details.get("version"),
                    details={
                        **(libvirt_details or {}),
                        "socket": libvirt_socket_info.model_dump(),
                    },
                )

        # --- virsh CLI ---
        virsh_result = await executor.run(
            "virsh --version", timeout=self._DEFAULT_TIMEOUT
        )
        if virsh_result.success and virsh_result.stripped_stdout():
            virtualization["virsh"] = ToolInfo(
                available=True,
                version=virsh_result.stripped_stdout(),
            )
        else:
            virtualization.setdefault("virsh", ToolInfo(available=False))

        # --- virt-install ---
        virt_install_result = await executor.run(
            "virt-install --version", timeout=self._DEFAULT_TIMEOUT
        )
        if virt_install_result.success and virt_install_result.stripped_stdout():
            virtualization["virt_install"] = ToolInfo(
                available=True,
                version=virt_install_result.stripped_stdout(),
            )

        # --- Other virtualization tools ---
        checks: dict[str, tuple[str, Parser | None]] = {
            "virtualbox": ("vboxmanage --version", self._parse_version_only),
            "vagrant": ("vagrant --version", self._parse_vagrant_version),
            "proxmox": ("pveversion", self._parse_version_only),
            "qemu_kvm": ("qemu-system-x86_64 --version", self._parse_qemu_version),
        }

        for tool, (command, parser) in checks.items():
            result = await executor.run(command, timeout=self._DEFAULT_TIMEOUT)
            if result.success:
                details = parser(result.stdout) if parser else None
                virtualization[tool] = ToolInfo(
                    available=True,
                    version=details.get("version") if details else None,
                    details=details,
                )
            else:
                virtualization.setdefault(tool, ToolInfo(available=False))

        # --- Podman (with rootless socket detection) ---
        podman_socket_info = await SocketProbe.probe(executor, "podman")
        podman_version_result = await executor.run(
            "podman --version", timeout=self._DEFAULT_TIMEOUT
        )
        if podman_version_result.success:
            version_info = self._parse_version_only(podman_version_result.stdout)
            podman_details: dict[str, Any] = {}
            if podman_socket_info:
                podman_details["socket"] = podman_socket_info.model_dump()
            podman_info_result = await executor.run(
                "podman info --format json", timeout=self._DEFAULT_TIMEOUT
            )
            if podman_info_result.success and podman_info_result.stripped_stdout():
                try:
                    podman_details["info"] = json.loads(
                        podman_info_result.stripped_stdout()
                    )
                except json.JSONDecodeError:
                    podman_details["raw_output"] = podman_info_result.stripped_stdout()
            virtualization["podman"] = ToolInfo(
                available=True,
                version=version_info.get("version") if version_info else None,
                details=podman_details or None,
            )
        else:
            virtualization.setdefault("podman", ToolInfo(available=False))

        # --- KVM device check ---
        kvm_result = await executor.run(
            "test -e /dev/kvm && echo 'present'", timeout=self._DEFAULT_TIMEOUT
        )
        if "present" in kvm_result.stdout:
            virtualization.setdefault("qemu_kvm", ToolInfo(available=True)).details = {
                **(virtualization.get("qemu_kvm").details or {}),
                "kvm_device": True,
            }

        # --- Multipass ---
        multipass_result = await executor.run(
            "multipass version", timeout=self._DEFAULT_TIMEOUT
        )
        if multipass_result.success and multipass_result.stripped_stdout():
            version_info = self._parse_version_only(multipass_result.stdout)
            virtualization["multipass"] = ToolInfo(
                available=True,
                version=version_info.get("version"),
                details={"raw": multipass_result.stripped_stdout()},
            )
        else:
            virtualization.setdefault("multipass", ToolInfo(available=False))

        return virtualization

    # ------------------------------------------------------------------
    # Docker detection
    # ------------------------------------------------------------------

    async def _detect_docker(
        self, executor: CommandExecutor, host: str
    ) -> DockerCapabilities | None:
        docker_version_result = await executor.run(
            "docker --version", timeout=self._DEFAULT_TIMEOUT
        )
        if not docker_version_result.success:
            return None

        docker_version = self._parse_docker_version(docker_version_result.stdout)

        running = False
        socket_accessible = False
        swarm_info = None

        # Try socket-based detection (local only)
        is_local_execution = isinstance(executor, LocalCommandExecutor) and host in {
            "localhost",
            "127.0.0.1",
        }

        docker_socket_path = "/var/run/docker.sock"
        docker_socket: SocketInfo | None = None

        # Probe socket for all execution types (local uses fast path, remote uses command)
        if is_local_execution:
            docker_socket = await SocketProbe.probe_local("docker")
        else:
            docker_socket = await SocketProbe.probe(executor, "docker")

        if is_local_execution and docker_socket:
            docker_socket_path = docker_socket.path
            socket_client = DockerSocketClient(socket_path=docker_socket_path)
            if await socket_client.is_available():
                capabilities = await socket_client.collect_capabilities()
                if capabilities:
                    capabilities.version = capabilities.version or docker_version
                    capabilities.socket = docker_socket
                    compose_info = await self._detect_docker_compose(executor)
                    capabilities.compose = compose_info
                    return capabilities

        # Fallback: CLI-based detection
        info_result = await executor.run(
            "docker info --format '{{json .}}'", timeout=self._DEFAULT_TIMEOUT
        )
        if info_result.success and info_result.stripped_stdout():
            try:
                info_data = json.loads(info_result.stripped_stdout())
                running = True
                socket_accessible = True
                swarm_info = info_data.get("Swarm")
            except json.JSONDecodeError:
                running = "Swarm:" in info_result.stdout

        compose_info = await self._detect_docker_compose(executor)

        swarm_details = None
        if swarm_info:
            swarm_details = DockerSwarmInfo(
                available=swarm_info.get("LocalNodeState") not in {None, "inactive"},
                active=swarm_info.get("LocalNodeState") == "active",
                node_role=swarm_info.get("ControlAvailable") and "manager" or "worker",
                details=swarm_info,
            )
        else:
            info_result_plain = await executor.run(
                "docker info", timeout=self._DEFAULT_TIMEOUT
            )
            if (
                info_result_plain.success
                and "Swarm: active" in info_result_plain.stdout
            ):
                swarm_details = DockerSwarmInfo(
                    available=True, active=True, node_role=None, details=None
                )
            elif (
                info_result_plain.success
                and "Swarm: inactive" in info_result_plain.stdout
            ):
                swarm_details = DockerSwarmInfo(
                    available=True, active=False, node_role=None, details=None
                )

        return DockerCapabilities(
            installed=True,
            version=docker_version,
            running=running,
            socket_accessible=socket_accessible,
            socket=docker_socket,
            compose=compose_info,
            swarm=swarm_details,
        )

    async def _detect_docker_compose(
        self, executor: CommandExecutor
    ) -> DockerComposeInfo | None:
        compose_plugin_result = await executor.run(
            "docker compose version", timeout=self._DEFAULT_TIMEOUT
        )
        if compose_plugin_result.success:
            version = self._parse_version_only(compose_plugin_result.stdout).get(
                "version"
            )
            return DockerComposeInfo(available=True, version=version, plugin_based=True)

        compose_binary_result = await executor.run(
            "docker-compose --version", timeout=self._DEFAULT_TIMEOUT
        )
        if compose_binary_result.success:
            version = self._parse_version_only(compose_binary_result.stdout).get(
                "version"
            )
            return DockerComposeInfo(
                available=True, version=version, plugin_based=False
            )
        return None

    # ------------------------------------------------------------------
    # Kubernetes / Orchestration detection
    # ------------------------------------------------------------------

    async def _detect_kubernetes(
        self, executor: CommandExecutor
    ) -> dict[str, ToolInfo]:
        kube_tools: dict[str, tuple[str, Parser | None]] = {
            "kubectl": (
                "kubectl version --client -o json",
                self._parse_kubectl_version,
            ),
            "kubeadm": ("kubeadm version -o json", self._parse_kubeadm_version),
            "k3s": ("k3s --version", self._parse_k3s_version),
            "microk8s": (
                "microk8s.kubectl version --output=json",
                self._parse_kubectl_version,
            ),
            "helm": (
                "helm version --short",
                self._parse_version_only,
            ),
        }

        kubernetes: dict[str, ToolInfo] = {}
        for tool, (command, parser) in kube_tools.items():
            result = await executor.run(command, timeout=self._DEFAULT_TIMEOUT)
            if result.success and parser:
                parsed = parser(result.stdout)
                kubernetes[tool] = ToolInfo(
                    available=True,
                    version=parsed.get("version"),
                    details=parsed,
                )
            elif result.success:
                kubernetes[tool] = ToolInfo(available=True)
            else:
                kubernetes[tool] = ToolInfo(available=False)
        return kubernetes

    # ------------------------------------------------------------------
    # Container runtimes detection (LXC, LXD, Incus, containerd)
    # ------------------------------------------------------------------

    async def _detect_container_runtimes(
        self, executor: CommandExecutor
    ) -> dict[str, ContainerRuntimeInfo]:
        runtimes: dict[str, ContainerRuntimeInfo] = {}

        # --- LXC ---
        runtimes["lxc"] = await self._detect_lxc(executor)

        # --- LXD ---
        runtimes["lxd"] = await self._detect_lxd(executor)

        # --- Incus ---
        runtimes["incus"] = await self._detect_incus(executor)

        # --- containerd ---
        runtimes["containerd"] = await self._detect_containerd(executor)

        return runtimes

    async def _detect_lxc(
        self, executor: CommandExecutor
    ) -> ContainerRuntimeInfo:
        """Detect raw LXC tools (lxc-info, lxc-create, etc.)."""
        version_result = await executor.run(
            "lxc-info --version", timeout=self._DEFAULT_TIMEOUT
        )
        if not version_result.success:
            return ContainerRuntimeInfo(available=False)

        version = version_result.stripped_stdout()
        details: dict[str, Any] = {}

        # Check kernel support
        checkconfig = await executor.run(
            "lxc-checkconfig 2>/dev/null | head -20", timeout=self._DEFAULT_TIMEOUT
        )
        if checkconfig.success and checkconfig.stripped_stdout():
            details["kernel_support"] = checkconfig.stripped_stdout()

        # Socket
        socket_info = await SocketProbe.probe(executor, "lxc")
        if socket_info:
            details["socket"] = socket_info.model_dump()

        return ContainerRuntimeInfo(
            available=True,
            version=version or None,
            socket=socket_info,
            details=details or None,
        )

    async def _detect_lxd(
        self, executor: CommandExecutor
    ) -> ContainerRuntimeInfo:
        """Detect LXD daemon and its CLI client."""
        # Check daemon
        daemon_result = await executor.run(
            "lxd --version", timeout=self._DEFAULT_TIMEOUT
        )
        daemon_version = None
        if daemon_result.success:
            daemon_version = daemon_result.stripped_stdout()

        # Check client (lxc command for LXD, not raw LXC)
        client_result = await executor.run(
            "lxc version 2>/dev/null", timeout=self._DEFAULT_TIMEOUT
        )
        client_version = None
        if client_result.success:
            parsed = self._parse_version_only(client_result.stdout)
            client_version = parsed.get("version")

        if not daemon_result.success and not client_result.success:
            return ContainerRuntimeInfo(available=False)

        version = daemon_version or client_version
        details: dict[str, Any] = {}

        # Determine install method
        snap_result = await executor.run(
            "snap list lxd 2>/dev/null | tail -1", timeout=self._DEFAULT_TIMEOUT
        )
        install_method = "package"
        if snap_result.success and snap_result.stripped_stdout():
            install_method = "snap"
            details["snap_info"] = snap_result.stripped_stdout()

        # Socket
        socket_info = await SocketProbe.probe(executor, "lxd")
        if socket_info:
            details["socket"] = socket_info.model_dump()

        # Service status
        service_result = await executor.run(
            "systemctl is-active snap.lxd.daemon 2>/dev/null "
            "|| systemctl is-active lxd 2>/dev/null",
            timeout=self._DEFAULT_TIMEOUT,
        )
        if service_result.success and service_result.stripped_stdout():
            details["service_status"] = service_result.stripped_stdout()

        return ContainerRuntimeInfo(
            available=True,
            version=version,
            socket=socket_info,
            install_method=install_method,
            details=details or None,
        )

    async def _detect_incus(
        self, executor: CommandExecutor
    ) -> ContainerRuntimeInfo:
        """Detect Incus (community fork of LXD)."""
        version_result = await executor.run(
            "incus version", timeout=self._DEFAULT_TIMEOUT
        )
        if not version_result.success:
            return ContainerRuntimeInfo(available=False)

        parsed = self._parse_version_only(version_result.stdout)
        version = parsed.get("version", version_result.stripped_stdout())
        details: dict[str, Any] = {}

        # Determine install method
        snap_result = await executor.run(
            "snap list incus 2>/dev/null | tail -1", timeout=self._DEFAULT_TIMEOUT
        )
        install_method = "package"
        if snap_result.success and snap_result.stripped_stdout():
            install_method = "snap"
            details["snap_info"] = snap_result.stripped_stdout()

        # Socket
        socket_info = await SocketProbe.probe(executor, "incus")
        if socket_info:
            details["socket"] = socket_info.model_dump()

        # Service status
        service_result = await executor.run(
            "systemctl is-active incus 2>/dev/null",
            timeout=self._DEFAULT_TIMEOUT,
        )
        if service_result.success and service_result.stripped_stdout():
            details["service_status"] = service_result.stripped_stdout()

        return ContainerRuntimeInfo(
            available=True,
            version=version,
            socket=socket_info,
            install_method=install_method,
            details=details or None,
        )

    async def _detect_containerd(
        self, executor: CommandExecutor
    ) -> ContainerRuntimeInfo:
        """Detect containerd runtime."""
        version_result = await executor.run(
            "containerd --version", timeout=self._DEFAULT_TIMEOUT
        )
        if not version_result.success:
            # Try ctr as alternative
            ctr_result = await executor.run(
                "ctr version", timeout=self._DEFAULT_TIMEOUT
            )
            if not ctr_result.success:
                return ContainerRuntimeInfo(available=False)
            parsed = self._parse_version_only(ctr_result.stdout)
            return ContainerRuntimeInfo(
                available=True,
                version=parsed.get("version"),
                details={"detected_via": "ctr"},
            )

        parsed = self._parse_version_only(version_result.stdout)
        details: dict[str, Any] = {}

        # Socket
        socket_info = await SocketProbe.probe(executor, "containerd")
        if socket_info:
            details["socket"] = socket_info.model_dump()

        # Check if k3s containerd
        k3s_check = await executor.run(
            "test -S /run/k3s/containerd/containerd.sock && echo 'k3s'",
            timeout=self._DEFAULT_TIMEOUT,
        )
        if k3s_check.success and "k3s" in k3s_check.stdout:
            details["managed_by"] = "k3s"

        return ContainerRuntimeInfo(
            available=True,
            version=parsed.get("version"),
            socket=socket_info,
            details=details or None,
        )

    # ------------------------------------------------------------------
    # OCI low-level tools detection
    # ------------------------------------------------------------------

    async def _detect_oci_tools(
        self, executor: CommandExecutor
    ) -> dict[str, ToolInfo]:
        """Detect OCI runtimes and tools (runc, crun, buildah, skopeo, podman-compose)."""
        tools: dict[str, ToolInfo] = {}

        oci_checks: dict[str, tuple[str, Parser | None]] = {
            "runc": ("runc --version", self._parse_runc_version),
            "crun": ("crun --version", self._parse_version_only),
            "buildah": ("buildah --version", self._parse_version_only),
            "skopeo": ("skopeo --version", self._parse_version_only),
            "podman_compose": (
                "podman-compose --version",
                self._parse_version_only,
            ),
        }

        for tool, (command, parser) in oci_checks.items():
            result = await executor.run(command, timeout=self._DEFAULT_TIMEOUT)
            if result.success:
                details = parser(result.stdout) if parser else None
                tools[tool] = ToolInfo(
                    available=True,
                    version=details.get("version") if details else None,
                    details=details,
                )
            else:
                tools[tool] = ToolInfo(available=False)

        return tools

    # ------------------------------------------------------------------
    # Capabilities payload builder
    # ------------------------------------------------------------------

    def build_capabilities_payload(
        self, scan_result: ScanResult
    ) -> list[dict[str, Any]]:
        """Construit la liste normalisée des capacités détectées.

        Ne crée des entrées que pour les capacités réellement disponibles.
        """
        capabilities: list[dict[str, Any]] = []
        detected_at = scan_result.scan_date

        def add_capability(
            capability_type: CapabilityType,
            available: bool,
            version: str | None,
            details: dict[str, Any | None],
        ) -> None:
            if available:
                capabilities.append(
                    {
                        "capability_type": capability_type,
                        "is_available": available,
                        "version": version,
                        "details": details,
                        "detected_at": detected_at,
                    }
                )

        # Virtualization tools
        virtualization = scan_result.virtualization or {}
        for key, info in virtualization.items():
            capability_type = self._map_virtualization_key_to_capability(key)
            if capability_type is None:
                continue
            available, version, details = self._extract_tool_info(info)
            add_capability(capability_type, available, version, details)

        # Docker
        docker_caps = scan_result.docker
        if docker_caps is not None and docker_caps.installed:
            docker_details: dict[str, Any] = {
                "running": docker_caps.running,
                "socket_accessible": docker_caps.socket_accessible,
            }
            if docker_caps.socket:
                docker_details["socket"] = docker_caps.socket.model_dump()
            add_capability(
                CapabilityType.DOCKER,
                docker_caps.installed,
                docker_caps.version,
                docker_details,
            )

            compose_info = docker_caps.compose
            if compose_info and compose_info.available:
                compose_details: dict[str, Any] = {}
                if compose_info.plugin_based is not None:
                    compose_details["plugin_based"] = compose_info.plugin_based
                add_capability(
                    CapabilityType.DOCKER_COMPOSE,
                    compose_info.available,
                    compose_info.version,
                    compose_details or None,
                )

            swarm_info = docker_caps.swarm
            if swarm_info and swarm_info.available:
                swarm_details = swarm_info.details or {
                    "active": swarm_info.active,
                    "node_role": swarm_info.node_role,
                }
                add_capability(
                    CapabilityType.DOCKER_SWARM,
                    swarm_info.available,
                    None,
                    swarm_details,
                )

        # Kubernetes tools
        kubernetes_tools = scan_result.kubernetes or {}
        for key, info in kubernetes_tools.items():
            capability_type = self._map_kubernetes_key_to_capability(key)
            if capability_type is None:
                continue
            available, version, details = self._extract_tool_info(info)
            add_capability(capability_type, available, version, details)

        # Container runtimes (LXC, LXD, Incus, containerd)
        container_runtimes = scan_result.container_runtimes or {}
        for key, info in container_runtimes.items():
            capability_type = self._map_runtime_key_to_capability(key)
            if capability_type is None:
                continue
            details_payload: dict[str, Any | None] = {}
            if info.socket:
                details_payload["socket"] = info.socket.model_dump()
            if info.install_method:
                details_payload["install_method"] = info.install_method
            if info.details:
                details_payload.update(info.details)
            add_capability(
                capability_type,
                info.available,
                info.version,
                details_payload or None,
            )

        # OCI tools (runc, crun, buildah, skopeo, podman-compose)
        oci_tools = scan_result.oci_tools or {}
        for key, info in oci_tools.items():
            capability_type = self._map_oci_key_to_capability(key)
            if capability_type is None:
                continue
            available, version, details = self._extract_tool_info(info)
            add_capability(capability_type, available, version, details)

        return capabilities

    # ------------------------------------------------------------------
    # Key-to-capability mapping helpers
    # ------------------------------------------------------------------

    def _map_virtualization_key_to_capability(
        self, key: str
    ) -> CapabilityType | None:
        mapping = {
            "libvirt": CapabilityType.LIBVIRT,
            "virsh": CapabilityType.VIRSH,
            "virt_install": None,  # no dedicated capability type
            "virtualbox": CapabilityType.VIRTUALBOX,
            "vagrant": CapabilityType.VAGRANT,
            "proxmox": CapabilityType.PROXMOX,
            "qemu_kvm": CapabilityType.QEMU_KVM,
            "podman": CapabilityType.PODMAN,
            "multipass": CapabilityType.MULTIPASS,
        }
        return mapping.get(key.lower())

    def _map_kubernetes_key_to_capability(self, key: str) -> CapabilityType | None:
        mapping = {
            "kubectl": CapabilityType.KUBECTL,
            "kubeadm": CapabilityType.KUBEADM,
            "k3s": CapabilityType.K3S,
            "microk8s": CapabilityType.MICROK8S,
            "helm": CapabilityType.HELM,
        }
        return mapping.get(key.lower())

    def _map_runtime_key_to_capability(self, key: str) -> CapabilityType | None:
        mapping = {
            "lxc": CapabilityType.LXC,
            "lxd": CapabilityType.LXD,
            "incus": CapabilityType.INCUS,
            "containerd": CapabilityType.CONTAINERD,
        }
        return mapping.get(key.lower())

    def _map_oci_key_to_capability(self, key: str) -> CapabilityType | None:
        mapping = {
            "runc": CapabilityType.RUNC,
            "crun": CapabilityType.CRUN,
            "buildah": CapabilityType.BUILDAH,
            "skopeo": CapabilityType.SKOPEO,
            "podman_compose": CapabilityType.PODMAN_COMPOSE,
        }
        return mapping.get(key.lower())

    def _extract_tool_info(
        self, info: Any
    ) -> tuple[bool, str | None, dict[str, Any | None]]:
        if isinstance(info, ToolInfo):
            return info.available, info.version, info.details
        if isinstance(info, dict):
            available = bool(info.get("available"))
            version = info.get("version")
            raw_details = info.get("details")
            details = raw_details if isinstance(raw_details, dict) else None
            return available, version, details
        return False, None, None

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _map_architecture(self, raw_arch: str) -> PlatformArchitecture:
        normalized = raw_arch.strip().lower()
        if normalized in {"x86_64", "amd64"}:
            return PlatformArchitecture.X86_64
        if normalized in {"i386", "i686"}:
            return PlatformArchitecture.X86_32
        if normalized in {"aarch64", "arm64"}:
            return PlatformArchitecture.ARM64
        if normalized in {"armv8", "armv8l"}:
            return PlatformArchitecture.ARMV8
        if normalized in {"armv7l", "armv7"}:
            return PlatformArchitecture.ARMV7
        if normalized in {"armv6l", "armv6"}:
            return PlatformArchitecture.ARMV6
        return PlatformArchitecture.UNKNOWN

    @staticmethod
    def _strip_quotes(value: str) -> str:
        stripped = value.strip()
        if stripped.startswith(('"', "'")) and stripped.endswith(('"', "'")):
            return stripped[1:-1]
        return stripped

    @staticmethod
    def _parse_version_only(output: str) -> dict[str, Any]:
        match = re.search(r"(\d+\.\d+(?:\.\d+)?)", output)
        if match:
            return {"version": match.group(1)}
        return {}

    @staticmethod
    def _parse_vagrant_version(output: str) -> dict[str, Any]:
        result = TargetScannerService._parse_version_only(output)
        if result:
            result["raw"] = output.strip()
        return result

    @staticmethod
    def _parse_qemu_version(output: str) -> dict[str, Any]:
        first_line = output.splitlines()[0] if output else ""
        version_info = TargetScannerService._parse_version_only(first_line)
        if version_info:
            version_info["raw"] = first_line.strip()
        return version_info

    @staticmethod
    def _parse_docker_version(output: str) -> str | None:
        info = TargetScannerService._parse_version_only(output)
        return info.get("version")

    @staticmethod
    def _parse_kubectl_version(output: str) -> dict[str, Any]:
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            match = re.search(r"Client Version:\s*v?([\w\.\-]+)", output)
            return {"version": match.group(1)} if match else {}

        client_ver = data.get("clientVersion") or data.get("client")
        if isinstance(client_ver, dict):
            version = client_ver.get("gitVersion") or client_ver.get("gitVersion", "")
            return {
                "version": version,
                "major": client_ver.get("major"),
                "minor": client_ver.get("minor"),
            }
        return {}

    @staticmethod
    def _parse_kubeadm_version(output: str) -> dict[str, Any]:
        try:
            data = json.loads(output)
            return {
                "version": data.get("clientVersion", {}).get("gitVersion"),
                "major": data.get("clientVersion", {}).get("major"),
                "minor": data.get("clientVersion", {}).get("minor"),
            }
        except json.JSONDecodeError:
            return TargetScannerService._parse_version_only(output)

    @staticmethod
    def _parse_k3s_version(output: str) -> dict[str, Any]:
        """Parse k3s version output like 'k3s version v1.28.4+k3s2'."""
        match = re.search(r"v?(\d+\.\d+(?:\.\d+)?(?:\+\S+)?)", output)
        if match:
            return {"version": match.group(1)}
        return TargetScannerService._parse_version_only(output)

    @staticmethod
    def _parse_runc_version(output: str) -> dict[str, Any]:
        """Parse runc version output (may be multi-line)."""
        for line in output.splitlines():
            if "runc" in line.lower() or line.strip().startswith("1.") or line.strip().startswith("2."):
                return TargetScannerService._parse_version_only(line)
        return TargetScannerService._parse_version_only(output)
