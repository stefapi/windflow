"""
Service for scanning deployment targets capabilities (local or remote).

Provides detection of virtualization, container, and orchestration tooling,
including hardware platform information.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, Protocol, Tuple, TypeVar

import asyncssh
from asyncssh import ConnectionLost
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.target import Target
from ..schemas.target_scan import (
    DockerCapabilities,
    DockerComposeInfo,
    DockerSwarmInfo,
    OSInfo,
    PlatformArchitecture,
    PlatformInfo,
    ScanRequest,
    ScanResult,
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

    async def run(
        self,
        command: str,
        timeout: int = 30,
        require_success: bool = False
    ) -> CommandResult:
        ...


class LocalCommandExecutor:
    """Execute commands on the local machine using subprocess."""

    def __init__(self, sudo_user: Optional[str] = None, sudo_password: Optional[str] = None):
        self._sudo_user = sudo_user
        self._sudo_password = sudo_password

    async def run(
        self,
        command: str,
        timeout: int = 30,
        require_success: bool = False
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
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            raise CommandExecutionError(
                command,
                exit_status=124,
                stderr=f"Command timed out after {timeout}s: {exc}"
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
        sudo_user: Optional[str] = None,
        sudo_password: Optional[str] = None,
    ):
        self._connection = connection
        self._sudo_user = sudo_user
        self._sudo_password = sudo_password

    async def run(
        self,
        command: str,
        timeout: int = 30,
        require_success: bool = False
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
                timeout=timeout
            )
        except asyncio.TimeoutError as exc:
            raise CommandExecutionError(
                command,
                exit_status=124,
                stderr=f"Remote command timed out after {timeout}s"
            ) from exc
        except (asyncssh.Error, ConnectionLost) as exc:
            raise CommandExecutionError(
                command,
                exit_status=255,
                stderr=f"SSH execution failed: {exc}"
            ) from exc

        result = CommandResult(
            completed.exit_status,
            completed.stdout or "",
            completed.stderr or ""
        )
        if require_success and not result.success:
            raise CommandExecutionError(command, result.exit_status, result.stderr)
        return result

    def _wrap_with_sudo(self, command: str) -> str:
        sudo_parts = ["sudo", "-S", "-p", "''", "-u", self._sudo_user]
        return " ".join(sudo_parts + [command])


Parser = Callable[[str], Dict[str, Any]]
T = TypeVar("T")


class ContainerEnvironmentDetector:
    """Detects runtime environment characteristics."""

    _DOCKER_SOCKET = Path("/var/run/docker.sock")
    _LIBVIRT_SOCKET = Path("/var/run/libvirt/libvirt-sock")
    _DOCKERENV = Path("/.dockerenv")

    @staticmethod
    def is_in_container() -> bool:
        """Returns True if running inside a container."""
        if ContainerEnvironmentDetector._DOCKERENV.exists():
            return True
        try:
            with open("/proc/1/cgroup", encoding="utf-8") as cgroup_file:
                content = cgroup_file.read().lower()
            return any(token in content for token in ("docker", "containerd", "kubepods"))
        except FileNotFoundError:  # pragma: no cover - uncommon
            return False

    @staticmethod
    def has_docker_socket() -> bool:
        """Checks whether the Docker socket is available."""
        return ContainerEnvironmentDetector._DOCKER_SOCKET.exists()

    @staticmethod
    def has_libvirt_socket() -> bool:
        """Checks whether the libvirt socket is available."""
        return ContainerEnvironmentDetector._LIBVIRT_SOCKET.exists()


class DockerSocketClient:
    """Collects Docker capabilities through the mounted Unix socket."""

    def __init__(self, socket_path: str = "/var/run/docker.sock"):
        self.socket_path = socket_path

    async def is_available(self) -> bool:
        """Returns True if the Docker socket is accessible."""
        if docker is None or not Path(self.socket_path).exists():
            return False
        return await asyncio.to_thread(self._can_connect)

    async def collect_capabilities(self) -> Optional[DockerCapabilities]:
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

    def _collect_capabilities_sync(self) -> Optional[DockerCapabilities]:
        client = None
        try:
            client = self._create_client()
            info = client.info()
            version_info = client.version()
            swarm_info = info.get("Swarm") if isinstance(info, dict) else None

            return DockerCapabilities(
                installed=True,
                version=version_info.get("Version") if isinstance(version_info, dict) else None,
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
    def _build_swarm_info(swarm_info: Optional[Dict[str, Any]]) -> Optional[DockerSwarmInfo]:
        if not swarm_info:
            return None

        local_state = swarm_info.get("LocalNodeState")
        available = local_state not in {None, "inactive"}
        active = local_state == "active"
        node_role: Optional[str] = None
        if available:
            node_role = "manager" if swarm_info.get("ControlAvailable") else "worker"

        return DockerSwarmInfo(
            available=available,
            active=active,
            node_role=node_role,
            details=swarm_info
        )


class LibvirtSocketClient:
    """Collects libvirt (KVM/QEMU) capabilities via the libvirt socket."""

    def __init__(
        self,
        socket_path: str = "/var/run/libvirt/libvirt-sock",
        uri: str = "qemu:///system"
    ):
        self.socket_path = socket_path
        self.uri = uri

    async def is_available(self) -> bool:
        """Returns True if the libvirt socket is accessible."""
        if libvirt is None or not Path(self.socket_path).exists():
            return False
        return await asyncio.to_thread(self._can_connect)

    async def collect_details(self) -> Dict[str, Any]:
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

    def _collect_details_sync(self) -> Dict[str, Any]:
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
    def _format_version(value: int) -> Optional[str]:
        if not value:
            return None
        major = value // 1_000_000
        minor = (value // 1_000) % 1_000
        patch = value % 1_000
        return f"{major}.{minor}.{patch}"


class TargetScannerService:
    """Service capable of scanning deployment targets for capabilities."""

    _DEFAULT_TIMEOUT = 30

    async def scan_localhost(self) -> ScanResult:
        """
        Scan the local machine using shell execution or mounted sockets.

        Returns:
            ScanResult: Detected capabilities for localhost.
        """
        detector = ContainerEnvironmentDetector()
        executor: CommandExecutor = LocalCommandExecutor()

        # Prioritize Docker socket when available (works both inside/outside containers)
        use_socket = detector.has_docker_socket()
        if detector.is_in_container() and not use_socket:
            # Fallback to command execution when socket not provided
            use_socket = False

        # Run regular scan (Docker detection routine will leverage the socket)
        host_label = "localhost"
        return await self._run_scan(executor, host=host_label)

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
        ssh_kwargs = {
            "host": scan_request.host,
            "port": scan_request.port,
            "username": scan_request.username,
            "password": scan_request.password,
            "known_hosts": None,
        }
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
                "ssh-connect",
                exit_status=255,
                stderr=f"SSH connection failed: {exc}"
            ) from exc

    async def scan_and_update_target(
        self,
        target: Target,
        db: AsyncSession
    ) -> Target:
        """
        Scan a stored target and persist discovered capabilities.

        Args:
            target: Target instance to scan.
            db: Database session.

        Returns:
            Target: Updated target with new capabilities.

        Raises:
            ValueError: When credentials are missing for remote scan.
        """
        await TargetService.set_scan_status(db, target, "scanning")

        is_localhost = target.host in {"localhost", "127.0.0.1"}
        try:
            if is_localhost:
                scan_result = await self.scan_localhost()
            else:
                credentials = target.credentials or {}
                username = credentials.get("username")
                password = credentials.get("password")
                if not username or not password:
                    raise ValueError(
                        "Target credentials must contain 'username' and 'password' "
                        "for remote scanning."
                    )

                scan_request = ScanRequest(
                    host=target.host,
                    port=target.port or 22,
                    username=username,
                    password=password,
                    sudo_user=credentials.get("sudo_user"),
                    sudo_password=credentials.get("sudo_password") or password,
                )
                scan_result = await self.scan_remote(scan_request)

            payload = scan_result.model_dump(mode="json")
            await TargetService.update_discovered_capabilities(
                db=db,
                target=target,
                capabilities=payload,
                scan_date=scan_result.scan_date,
                status="completed" if scan_result.success else "failed"
            )
            return target
        except Exception:  # noqa: B902
            await TargetService.set_scan_status(db, target, "failed")
            raise

    async def _run_scan(
        self,
        executor: CommandExecutor,
        host: str
    ) -> ScanResult:
        errors: list[str] = []
        platform_info = await self._safe_execute(self._detect_platform, executor, errors)
        os_info = await self._safe_execute(self._detect_os, executor, errors)
        virtualization = await self._safe_execute(
            self._detect_virtualization,
            executor,
            errors,
            default={}
        )
        docker_info = await self._safe_execute(
            lambda exec_: self._detect_docker(exec_, host=host),
            executor,
            errors
        )
        kubernetes = await self._safe_execute(
            self._detect_kubernetes,
            executor,
            errors,
            default={}
        )

        success = not errors

        return ScanResult(
            host=host,
            scan_date=datetime.utcnow(),
            success=success,
            platform=platform_info,
            os=os_info,
            virtualization=virtualization or {},
            docker=docker_info,
            kubernetes=kubernetes or {},
            errors=errors,
        )

    async def _safe_execute(
        self,
        func: Callable[[CommandExecutor], Awaitable[T]],
        executor: CommandExecutor,
        errors: list[str],
        default: Optional[T] = None
    ) -> Optional[T]:
        try:
            return await func(executor)
        except CommandExecutionError as exc:
            errors.append(str(exc))
            return default
        except Exception as exc:  # noqa: B902
            errors.append(str(exc))
            return default

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
                        total_memory_gb = round(memory_kb / (1024 ** 3), 2)
                    else:
                        total_memory_gb = round(memory_kb / (1024 ** 1) / 1024, 2)
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

        os_release_result = await executor.run("cat /etc/os-release", timeout=self._DEFAULT_TIMEOUT)
        if os_release_result.success and os_release_result.stdout:
            for line in os_release_result.stdout.splitlines():
                if line.startswith("NAME="):
                    distribution = self._strip_quotes(line.split("=", 1)[1])
                if line.startswith("VERSION="):
                    version = self._strip_quotes(line.split("=", 1)[1])

        if not distribution:
            lsb_result = await executor.run("lsb_release -ds", timeout=self._DEFAULT_TIMEOUT)
            if lsb_result.success and lsb_result.stripped_stdout():
                distribution = self._strip_quotes(lsb_result.stripped_stdout())

        return OSInfo(
            system=system,
            distribution=distribution,
            version=version,
            kernel=kernel,
        )

    async def _detect_virtualization(self, executor: CommandExecutor) -> Dict[str, ToolInfo]:
        virtualization: Dict[str, ToolInfo] = {}

        # libvirt socket detection (KVM/QEMU)
        libvirt_client = LibvirtSocketClient()
        if ContainerEnvironmentDetector.has_libvirt_socket() and await libvirt_client.is_available():
            libvirt_details = await libvirt_client.collect_details()
            virtualization["libvirt"] = ToolInfo(
                available=True,
                version=libvirt_details.get("version"),
                details=libvirt_details or None
            )

        checks: Dict[str, Tuple[str, Optional[Parser]]] = {
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
                    details=details
                )
            else:
                virtualization.setdefault(tool, ToolInfo(available=False))

        kvm_result = await executor.run("test -e /dev/kvm && echo 'present'", timeout=self._DEFAULT_TIMEOUT)
        if "present" in kvm_result.stdout:
            virtualization.setdefault("qemu_kvm", ToolInfo(available=True)).details = {
                **(virtualization.get("qemu_kvm").details or {}),
                "kvm_device": True
            }
        return virtualization

    async def _detect_docker(
        self,
        executor: CommandExecutor,
        host: str
    ) -> Optional[DockerCapabilities]:
        docker_socket_client = DockerSocketClient()
        is_local_execution = isinstance(executor, LocalCommandExecutor) and host in {"localhost", "127.0.0.1"}

        if is_local_execution and await docker_socket_client.is_available():
            capabilities = await docker_socket_client.collect_capabilities()
            if capabilities:
                return capabilities

        docker_version_result = await executor.run("docker --version", timeout=self._DEFAULT_TIMEOUT)
        if not docker_version_result.success:
            return None

        docker_version = self._parse_docker_version(docker_version_result.stdout)

        running = False
        socket_accessible = False
        swarm_info = None

        info_result = await executor.run("docker info --format '{{json .}}'", timeout=self._DEFAULT_TIMEOUT)
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
                details=swarm_info
            )
        else:
            info_result_plain = await executor.run("docker info", timeout=self._DEFAULT_TIMEOUT)
            if info_result_plain.success and "Swarm: active" in info_result_plain.stdout:
                swarm_details = DockerSwarmInfo(
                    available=True,
                    active=True,
                    node_role=None,
                    details=None
                )
            elif info_result_plain.success and "Swarm: inactive" in info_result_plain.stdout:
                swarm_details = DockerSwarmInfo(
                    available=True,
                    active=False,
                    node_role=None,
                    details=None
                )

        return DockerCapabilities(
            installed=True,
            version=docker_version,
            running=running,
            socket_accessible=socket_accessible,
            compose=compose_info,
            swarm=swarm_details,
        )

    async def _detect_docker_compose(self, executor: CommandExecutor) -> Optional[DockerComposeInfo]:
        compose_plugin_result = await executor.run("docker compose version", timeout=self._DEFAULT_TIMEOUT)
        if compose_plugin_result.success:
            version = self._parse_version_only(compose_plugin_result.stdout).get("version")
            return DockerComposeInfo(
                available=True,
                version=version,
                plugin_based=True
            )

        compose_binary_result = await executor.run("docker-compose --version", timeout=self._DEFAULT_TIMEOUT)
        if compose_binary_result.success:
            version = self._parse_version_only(compose_binary_result.stdout).get("version")
            return DockerComposeInfo(
                available=True,
                version=version,
                plugin_based=False
            )
        return None

    async def _detect_kubernetes(self, executor: CommandExecutor) -> Dict[str, ToolInfo]:
        kube_tools: Dict[str, Tuple[str, Optional[Parser]]] = {
            "kubectl": ("kubectl version --client -o json", self._parse_kubectl_version),
            "kubeadm": ("kubeadm version -o json", self._parse_kubeadm_version),
            "k3s": ("k3s --version", self._parse_version_only),
            "microk8s": ("microk8s.kubectl version --output=json", self._parse_kubectl_version),
        }

        kubernetes: Dict[str, ToolInfo] = {}
        for tool, (command, parser) in kube_tools.items():
            result = await executor.run(command, timeout=self._DEFAULT_TIMEOUT)
            if result.success and parser:
                kubernetes[tool] = ToolInfo(
                    available=True,
                    version=parser(result.stdout).get("version"),
                    details=parser(result.stdout),
                )
            elif result.success:
                kubernetes[tool] = ToolInfo(available=True)
            else:
                kubernetes[tool] = ToolInfo(available=False)
        return kubernetes

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
        if stripped.startswith(("\"", "'")) and stripped.endswith(("\"", "'")):
            return stripped[1:-1]
        return stripped

    @staticmethod
    def _parse_version_only(output: str) -> Dict[str, Any]:
        match = re.search(r"(\d+\.\d+(?:\.\d+)?)", output)
        if match:
            return {"version": match.group(1)}
        return {}

    @staticmethod
    def _parse_vagrant_version(output: str) -> Dict[str, Any]:
        result = TargetScannerService._parse_version_only(output)
        if result:
            result["raw"] = output.strip()
        return result

    @staticmethod
    def _parse_qemu_version(output: str) -> Dict[str, Any]:
        first_line = output.splitlines()[0] if output else ""
        version_info = TargetScannerService._parse_version_only(first_line)
        if version_info:
            version_info["raw"] = first_line.strip()
        return version_info

    @staticmethod
    def _parse_docker_version(output: str) -> Optional[str]:
        info = TargetScannerService._parse_version_only(output)
        return info.get("version")

    @staticmethod
    def _parse_kubectl_version(output: str) -> Dict[str, Any]:
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
    def _parse_kubeadm_version(output: str) -> Dict[str, Any]:
        try:
            data = json.loads(output)
            return {
                "version": data.get("clientVersion", {}).get("gitVersion"),
                "major": data.get("clientVersion", {}).get("major"),
                "minor": data.get("clientVersion", {}).get("minor"),
            }
        except json.JSONDecodeError:
            return TargetScannerService._parse_version_only(output)
