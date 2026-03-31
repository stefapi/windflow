"""
Service de scan de cibles de déploiement.

Orchestre la détection des capacités de virtualisation, conteneurisation
et orchestration sur les machines locales ou distantes.
Délègue le parsing à :mod:`target_scan_parsers`, l'exécution de commandes
à :mod:`commands`, la détection par socket à :mod:`socket_clients`,
et la détection du profil d'accès à :mod:`target_access_profile`.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypeVar

import asyncssh
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import CommandExecutionError
from ..enums.target import AccessLevel
from ..models.target import Target
from ..schemas.target import TargetAccessProfile
from ..schemas.target_scan import (
    ContainerRuntimeInfo,
    DockerCapabilities,
    DockerComposeInfo,
    DockerSwarmInfo,
    OSInfo,
    PlatformInfo,
    ScanRequest,
    ScanResult,
    SocketInfo,
    ToolInfo,
)
from .commands import CommandExecutor, CommandResult, LocalCommandExecutor, SSHCommandExecutor
from .socket_clients import (
    DockerSocketClient,
    LibvirtSocketClient,
    SocketProbe,
)
from .target_access_profile import TargetAccessProfileDetector
from .target_scan_parsers import (
    Parser,
    build_capabilities_payload,
    extract_capability_names,
    map_architecture,
    parse_docker_version,
    parse_k3s_version,
    parse_kubeadm_version,
    parse_kubectl_version,
    parse_qemu_version,
    parse_runc_version,
    parse_vagrant_version,
    parse_version_only,
    strip_quotes,
)
from .target_service import TargetService

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ─── Service principal ────────────────────────────────────────


class TargetScannerService:
    """Service de scan des cibles de déploiement.

    Orchestre la détection concurrente des capacités (plateforme, OS,
    virtualisation, Docker, Kubernetes, runtimes, outils OCI) et
    la persistance des résultats via :class:`TargetService`.
    """

    _DEFAULT_TIMEOUT = 30

    def __init__(self) -> None:
        self._access_profile_detector = TargetAccessProfileDetector()

    # ─── Points d'entrée publics ──────────────────────────────

    async def scan_localhost(self) -> ScanResult:
        """Scanne la machine locale via exécution shell ou sockets montés.

        Returns:
            Résultat du scan avec les capacités détectées.
        """
        executor: CommandExecutor = LocalCommandExecutor()
        return await self._run_scan(executor, host="localhost")

    async def scan_remote(self, scan_request: ScanRequest) -> ScanResult:
        """Scanne une machine distante via SSH.

        Args:
            scan_request: Paramètres de connexion distante.

        Returns:
            Résultat du scan avec les capacités détectées.

        Raises:
            CommandExecutionError: Si la connexion SSH échoue.
        """
        ssh_kwargs = self._build_ssh_kwargs(scan_request)
        try:
            async with asyncssh.connect(**ssh_kwargs) as connection:
                executor = SSHCommandExecutor(
                    connection,
                    sudo_user=scan_request.sudo_user,
                    sudo_password=scan_request.sudo_password,
                )
                return await self._run_scan(executor, host=scan_request.host)
        except (OSError, asyncssh.Error, asyncio.TimeoutError) as exc:
            raise CommandExecutionError(
                "ssh-connect", exit_status=255, stderr=f"Échec connexion SSH : {exc}"
            ) from exc

    async def scan_and_update_target(self, target: Target, db: AsyncSession) -> Target:
        """Scanne une cible stockée et persiste les capacités découvertes.

        Effectue :
        1. Un scan standard (avec sudo si configuré)
        2. La détection du profil d'accès
        3. Un double scan (standard vs elevé) si applicable
        4. La persistance via :class:`TargetService`

        Args:
            target: Instance de la cible à scanner.
            db: Session de base de données.

        Returns:
            La cible mise à jour.

        Raises:
            ValueError: Si les identifiants sont manquants pour un scan distant.
        """
        await TargetService.mark_scan_in_progress(db, target)

        is_localhost = target.host in {"localhost", "127.0.0.1"}
        try:
            scan_result, access_profile, standard_caps, elevated_caps = (
                await self._execute_full_scan(target, is_localhost)
            )

            access_profile.standard_capabilities = standard_caps
            access_profile.elevated_capabilities = elevated_caps

            await self._persist_scan(db, target, scan_result, access_profile)
            return target
        except Exception:
            await TargetService.mark_scan_failed(db, target)
            raise

    # ─── Orchestration interne ────────────────────────────────

    async def _execute_full_scan(
        self, target: Target, is_localhost: bool
    ) -> tuple[ScanResult, TargetAccessProfile, list[str], list[str]]:
        """Exécute le scan complet : scan + profil d'accès + double scan.

        Returns:
            Tuple (scan_result, access_profile, standard_caps, elevated_caps).
        """
        credentials = target.credentials or {}
        sudo_user = credentials.get("sudo_user")
        sudo_password = credentials.get("sudo_password")
        sudo_enabled = credentials.get("sudo_enabled", False)

        if is_localhost:
            return await self._full_scan_localhost(credentials, sudo_user, sudo_password, sudo_enabled)

        return await self._full_scan_remote(target, credentials, sudo_user, sudo_password, sudo_enabled)

    async def _full_scan_localhost(
        self, credentials: dict, sudo_user: str | None, sudo_password: str | None, sudo_enabled: bool
    ) -> tuple[ScanResult, TargetAccessProfile, list[str], list[str]]:
        """Scan complet pour une cible locale."""
        scan_result = await self.scan_localhost()
        local_executor: CommandExecutor = LocalCommandExecutor()

        access_profile = await self._access_profile_detector.detect(
            executor=local_executor, ssh_user=None,
            sudo_user=sudo_user, sudo_password=sudo_password,
            sudo_enabled=sudo_enabled, detection_method="scan",
        )

        standard_caps, elevated_caps = await self._perform_double_scan(
            access_profile=access_profile, is_localhost=True,
            host="localhost", credentials=credentials,
        )
        return scan_result, access_profile, standard_caps, elevated_caps

    async def _full_scan_remote(
        self, target: Target, credentials: dict, sudo_user: str | None, sudo_password: str | None, sudo_enabled: bool
    ) -> tuple[ScanResult, TargetAccessProfile, list[str], list[str]]:
        """Scan complet pour une cible distante — connexion SSH unique réutilisée."""
        username = credentials.get("username")
        if not username:
            raise ValueError("Les identifiants doivent contenir 'username' pour un scan distant.")

        ssh_kwargs = self._build_ssh_kwargs(ScanRequest(
            host=target.host, port=target.port or 22, username=username,
            password=credentials.get("password"),
            ssh_private_key=credentials.get("ssh_private_key"),
            ssh_private_key_passphrase=credentials.get("ssh_private_key_passphrase"),
            sudo_user=sudo_user, sudo_password=sudo_password,
        ))

        try:
            async with asyncssh.connect(**ssh_kwargs) as connection:
                sudo_executor = SSHCommandExecutor(
                    connection, sudo_user=sudo_user, sudo_password=sudo_password,
                )
                plain_executor = SSHCommandExecutor(connection)

                # 1) Scan des capacités (avec sudo si configuré)
                scan_result = await self._run_scan(sudo_executor, host=target.host)

                # 2) Détection du profil d'accès (même connexion)
                access_profile = await self._access_profile_detector.detect(
                    executor=plain_executor, ssh_user=username,
                    sudo_user=sudo_user, sudo_password=sudo_password,
                    sudo_enabled=sudo_enabled, detection_method="scan",
                )

                # 3) Double scan sans sudo (même connexion)
                standard_caps, elevated_caps = await self._perform_double_scan(
                    access_profile=access_profile, is_localhost=False,
                    host=target.host, credentials=credentials,
                    executor=plain_executor,
                )
        except (OSError, asyncssh.Error, asyncio.TimeoutError) as exc:
            raise CommandExecutionError(
                "ssh-connect", exit_status=255, stderr=f"Échec connexion SSH : {exc}"
            ) from exc

        return scan_result, access_profile, standard_caps, elevated_caps

    async def _persist_scan(
        self, db: AsyncSession, target: Target,
        scan_result: ScanResult, access_profile: TargetAccessProfile,
    ) -> None:
        """Persiste le résultat du scan en base de données."""
        capabilities = build_capabilities_payload(scan_result)
        platform_payload = scan_result.platform.model_dump(mode="json") if scan_result.platform else None
        os_payload = scan_result.os.model_dump(mode="json") if scan_result.os else None

        await TargetService.apply_scan_result(
            db=db, target=target, capabilities=capabilities,
            scan_date=scan_result.scan_date, success=scan_result.success,
            platform_info=platform_payload, os_info=os_payload,
            access_profile=access_profile.model_dump(mode="json"),
        )

    @staticmethod
    def _build_ssh_kwargs(scan_request: ScanRequest) -> dict:
        """Construit les kwargs SSH à partir d'une requête de scan."""
        kwargs: dict = {
            "host": scan_request.host, "port": scan_request.port,
            "username": scan_request.username, "known_hosts": None,
        }
        if scan_request.ssh_private_key:
            kwargs["client_keys"] = [scan_request.ssh_private_key]
            if getattr(scan_request, "ssh_private_key_passphrase", None):
                kwargs["passphrase"] = scan_request.ssh_private_key_passphrase
        else:
            kwargs["password"] = scan_request.password
        return kwargs

    # ─── Double scan (standard vs elevé) ─────────────────────

    async def _perform_double_scan(
        self,
        access_profile: TargetAccessProfile,
        is_localhost: bool,
        host: str,
        credentials: dict,
        executor: CommandExecutor | None = None,
    ) -> tuple[list[str], list[str]]:
        """Effectue un second scan sans sudo pour distinguer les capacités standard.

        Args:
            executor: Executor existant à réutiliser (évite une nouvelle connexion SSH).
                Si ``None``, un nouvel executor sera créé.

        Returns:
            Tuple (standard_capabilities, elevated_capabilities).
        """
        if access_profile.access_level == AccessLevel.LIMITED or access_profile.is_root_user:
            return [], []

        try:
            standard_scan = await self._run_standard_scan(
                is_localhost, host, credentials, executor,
            )
            standard_payload = build_capabilities_payload(standard_scan)
            return extract_capability_names(standard_payload), []
        except Exception:
            logger.warning(
                "Double scan échoué pour %s", host,
                exc_info=True, extra={"host": host},
            )
            return [], []

    async def _run_standard_scan(
        self,
        is_localhost: bool,
        host: str,
        credentials: dict,
        executor: CommandExecutor | None = None,
    ) -> ScanResult:
        """Exécute un scan sans sudo pour capturer les capacités standard.

        Args:
            executor: Executor existant à réutiliser. Si ``None``, une nouvelle
                connexion SSH sera établie.
        """
        if is_localhost:
            local_exec: CommandExecutor = LocalCommandExecutor()
            return await self._run_scan(local_exec, host=host)

        if executor is not None:
            return await self._run_scan(executor, host=host)

        # Fallback : nouvelle connexion SSH si aucun executor fourni
        scan_request = ScanRequest(
            host=host,
            port=credentials.get("port", 22),
            username=credentials.get("username"),
            password=credentials.get("password"),
            ssh_private_key=credentials.get("ssh_private_key"),
            ssh_private_key_passphrase=credentials.get("ssh_private_key_passphrase"),
        )
        ssh_kwargs = self._build_ssh_kwargs(scan_request)
        async with asyncssh.connect(**ssh_kwargs) as connection:
            remote_exec = SSHCommandExecutor(connection)
            return await self._run_scan(remote_exec, host=host)

    # ─── Pipeline de scan principal ───────────────────────────

    async def _run_scan(self, executor: CommandExecutor, host: str) -> ScanResult:
        """Orchestre la détection concurrente de toutes les capacités.

        Lance toutes les détections en parallèle via ``asyncio.gather``.
        """
        errors: list[str] = []

        results = await asyncio.gather(
            self._safe_execute(self._detect_platform, executor, errors),
            self._safe_execute(self._detect_os, executor, errors),
            self._safe_execute(self._detect_virtualization, executor, errors, default={}),
            self._safe_execute(self._detect_docker_for_host(executor, host), errors),
            self._safe_execute(self._detect_kubernetes, executor, errors, default={}),
            self._safe_execute(self._detect_container_runtimes, executor, errors, default={}),
            self._safe_execute(self._detect_oci_tools, executor, errors, default={}),
        )

        platform_info, os_info, virtualization, docker_info, kubernetes, container_runtimes, oci_tools = results

        discovered_sockets = self._collect_discovered_sockets(
            docker_info, virtualization, container_runtimes,
        )

        # Le scan est considéré réussi si la plateforme a pu être détectée
        # (preuve que la machine est joignable), même si des outils individuels
        # n'ont pas été trouvés — c'est le comportement normal.
        is_reachable = platform_info is not None

        return ScanResult(
            host=host,
            scan_date=datetime.now(timezone.utc),
            success=is_reachable,
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

    def _detect_docker_for_host(
        self, executor: CommandExecutor, host: str,
    ) -> Callable[[], Awaitable[DockerCapabilities | None]]:
        """Crée un callable sans paramètre pour la détection Docker.

        Évite l'utilisation d'un lambda qui casse l'inférence de type
        dans ``_safe_execute``.
        """
        async def _detect() -> DockerCapabilities | None:
            return await self._detect_docker(executor, host)
        return _detect

    async def _safe_execute(
        self,
        func: Callable[[CommandExecutor], Awaitable[T]] | Callable[[], Awaitable[T]],
        executor_or_errors: CommandExecutor | list[str],
        errors_or_default: list[str] | T | None = None,
        *,
        default: T | None = None,
    ) -> T | None:
        """Exécute une fonction de détection avec gestion d'erreur centralisée."""
        if isinstance(executor_or_errors, list):
            return await self._safe_execute_bare(func, executor_or_errors, errors_or_default)
        return await self._safe_execute_with_executor(
            func, executor_or_errors, errors_or_default, default,
        )

    @staticmethod
    async def _safe_execute_bare(
        func: Callable[[], Awaitable[T]], errors: list[str], default: T | None,
    ) -> T | None:
        """Exécute un callable sans argument avec gestion d'erreur."""
        try:
            return await func()  # type: ignore[call-arg]
        except CommandExecutionError as exc:
            errors.append(str(exc))
            return default
        except Exception as exc:
            logger.warning("Erreur inattendue durant le scan", exc_info=True, extra={"error": str(exc)})
            errors.append(str(exc))
            return default

    @staticmethod
    async def _safe_execute_with_executor(
        func: Callable[[CommandExecutor], Awaitable[T]],
        executor: CommandExecutor, errors: list[str], default: T | None,
    ) -> T | None:
        """Exécute un callable recevant un executor avec gestion d'erreur."""
        try:
            return await func(executor)  # type: ignore[call-arg]
        except CommandExecutionError as exc:
            errors.append(str(exc))
            return default
        except Exception as exc:
            logger.warning("Erreur inattendue durant le scan", exc_info=True, extra={"error": str(exc)})
            errors.append(str(exc))
            return default

    @staticmethod
    def _collect_discovered_sockets(
        docker_info: DockerCapabilities | None,
        virtualization: dict[str, Any] | None,
        container_runtimes: dict[str, Any] | None,
    ) -> dict[str, SocketInfo]:
        """Regroupe tous les sockets découverts en un dict unifié."""
        sockets: dict[str, SocketInfo] = {}

        if docker_info and docker_info.socket:
            sockets["docker"] = docker_info.socket

        for key, info in (virtualization or {}).items():
            if isinstance(info, ToolInfo) and info.details:
                sock = info.details.get("socket")
                if isinstance(sock, dict):
                    try:
                        sockets[key] = SocketInfo(**sock)
                    except Exception:
                        logger.debug(
                            "Impossible de parser le socket pour %s", key,
                            extra={"tool": key},
                        )
                elif isinstance(sock, SocketInfo):
                    sockets[key] = sock

        for key, info in (container_runtimes or {}).items():
            if isinstance(info, ContainerRuntimeInfo) and info.socket:
                sockets[key] = info.socket

        return sockets

    # ─── Détection plateforme & OS ────────────────────────────

    async def _detect_platform(self, executor: CommandExecutor) -> PlatformInfo:
        """Détecte les informations de plateforme matérielle.

        Chaque propriété est détectée de manière indépendante :
        si la détection de la mémoire échoue, l'architecture et le CPU
        sont quand même retournés.
        """
        timeout = self._DEFAULT_TIMEOUT

        # Chaque propriété est isolée — un échec n'empêche pas les autres
        arch_result = await self._safe_run(executor, "uname -m", timeout)
        architecture = map_architecture(arch_result.stripped_stdout() if arch_result else "")

        cpu_model = await self._safe_detect_first_success(executor, [
            r"grep -m1 'model name' /proc/cpuinfo | cut -d':' -f2",
            "sysctl -n machdep.cpu.brand_string",
        ], timeout)

        cpu_cores = await self._safe_detect_cpu_cores(executor, timeout)
        total_memory_gb = await self._safe_detect_memory(executor, timeout)

        return PlatformInfo(
            architecture=architecture,
            cpu_model=cpu_model.strip() if cpu_model else None,
            cpu_cores=cpu_cores,
            total_memory_gb=total_memory_gb,
        )

    async def _detect_os(self, executor: CommandExecutor) -> OSInfo:
        """Détecte les informations du système d'exploitation.

        Chaque propriété est isolée — si ``uname -s`` échoue,
        le kernel et la distribution sont quand même détectés.
        """
        timeout = self._DEFAULT_TIMEOUT

        sys_result = await self._safe_run(executor, "uname -s", timeout)
        system = sys_result.stripped_stdout() if sys_result and sys_result.success else "unknown"

        kernel_result = await self._safe_run(executor, "uname -r", timeout)
        kernel = kernel_result.stripped_stdout() if kernel_result and kernel_result.success else None

        distribution, version = await self._detect_os_release(executor, timeout)

        return OSInfo(system=system, distribution=distribution, version=version, kernel=kernel)

    async def _detect_os_release(
        self, executor: CommandExecutor, timeout: int,
    ) -> tuple[str | None, str | None]:
        """Détecte la distribution et la version via /etc/os-release ou lsb_release."""
        distribution: str | None = None
        version: str | None = None

        os_result = await self._safe_run(executor, "cat /etc/os-release", timeout)
        if os_result and os_result.success and os_result.stdout:
            for line in os_result.stdout.splitlines():
                if line.startswith("NAME="):
                    distribution = strip_quotes(line.split("=", 1)[1])
                if line.startswith("VERSION="):
                    version = strip_quotes(line.split("=", 1)[1])

        if not distribution:
            lsb_result = await self._safe_run(executor, "lsb_release -ds", timeout)
            if lsb_result and lsb_result.success and lsb_result.stripped_stdout():
                distribution = strip_quotes(lsb_result.stripped_stdout())

        return distribution, version

    async def _safe_detect_cpu_cores(
        self, executor: CommandExecutor, timeout: int,
    ) -> int | None:
        """Détecte le nombre de cœurs CPU avec tolérance d'erreur."""
        for cmd in ["nproc", "sysctl -n hw.ncpu"]:
            result = await self._safe_run(executor, cmd, timeout)
            if result and result.success and result.stripped_stdout().isdigit():
                return int(result.stripped_stdout())
        return None

    async def _safe_detect_memory(
        self, executor: CommandExecutor, timeout: int,
    ) -> float | None:
        """Détecte la mémoire totale en Go avec tolérance d'erreur."""
        mem_cmds = [
            (r"grep MemTotal /proc/meminfo | awk '{print $2}'", False),
            ("sysctl -n hw.memsize", True),
        ]
        for cmd, is_memsize in mem_cmds:
            result = await self._safe_run(executor, cmd, timeout)
            if result and result.success and result.stripped_stdout():
                try:
                    value_kb = float(result.stripped_stdout())
                    if is_memsize:
                        return round(value_kb / (1024**3), 2)
                    return round(value_kb / 1024 / 1024, 2)
                except ValueError:
                    continue
        return None

    async def _safe_detect_first_success(
        self, executor: CommandExecutor, commands: list[str], timeout: int,
    ) -> str | None:
        """Exécute une liste de commandes et retourne le premier résultat fructueux."""
        for cmd in commands:
            result = await self._safe_run(executor, cmd, timeout)
            if result and result.success and result.stripped_stdout():
                return result.stripped_stdout()
        return None

    @staticmethod
    async def _safe_run(
        executor: CommandExecutor, command: str, timeout: int,
    ) -> CommandResult | None:
        """Exécute une commande en tolérant les erreurs (timeout, SSH).

        Retourne ``None`` au lieu de lever une exception, pour permettre
        aux autres propriétés de continuer à être détectées.
        """
        try:
            return await executor.run(command, timeout=timeout)
        except CommandExecutionError as exc:
            logger.debug(
                "Commande échouée (safe_run): %s — %s",
                command, exc, extra={"command": command},
            )
            return None
        except Exception as exc:
            logger.debug(
                "Erreur inattendue (safe_run): %s — %s",
                command, exc, extra={"command": command},
            )
            return None

    # ─── Détection virtualisation ─────────────────────────────

    async def _detect_virtualization(
        self, executor: CommandExecutor,
    ) -> dict[str, ToolInfo]:
        """Détecte les outils de virtualisation disponibles en parallèle."""
        timeout = self._DEFAULT_TIMEOUT
        result: dict[str, ToolInfo] = {}

        # Exécuter les détections indépendantes en parallèle
        libvirt_task = self._detect_libvirt(executor, result, timeout)
        cli_task = self._detect_cli_tools(executor, result, timeout)
        podman_task = self._detect_podman(executor, result, timeout)
        kvm_task = self._check_kvm_device(executor, result, timeout)
        multipass_task = self._detect_tool(
            executor, "multipass", "multipass version", result, timeout,
        )

        await asyncio.gather(
            libvirt_task, cli_task, podman_task, kvm_task, multipass_task,
        )

        return result

    async def _detect_libvirt(
        self, executor: CommandExecutor, result: dict[str, ToolInfo], timeout: int,
    ) -> None:
        """Détecte libvirt via socket et CLI."""
        libvirt_socket = await SocketProbe.probe(executor, "libvirt")
        if libvirt_socket is not None:
            await self._collect_libvirt_details(executor, libvirt_socket, result)

        await self._detect_tool(executor, "virsh", "virsh --version", result, timeout)
        await self._detect_tool(executor, "virt_install", "virt-install --version", result, timeout)

    async def _collect_libvirt_details(
        self, executor: CommandExecutor, socket_info: SocketInfo, result: dict[str, ToolInfo],
    ) -> None:
        """Collecte les détails libvirt via le client socket."""
        uri = "qemu:///session" if socket_info.mode == "session" else "qemu:///system"
        libvirt_client = LibvirtSocketClient(socket_path=socket_info.path, uri=uri)

        if await libvirt_client.is_available():
            details = await libvirt_client.collect_details()
            result["libvirt"] = ToolInfo(
                available=True, version=details.get("version"),
                details={**(details or {}), "socket": socket_info.model_dump()},
            )

    async def _detect_cli_tools(
        self, executor: CommandExecutor, result: dict[str, ToolInfo], timeout: int,
    ) -> None:
        """Détecte les outils CLI de virtualisation simples."""
        checks: dict[str, tuple[str, Parser | None]] = {
            "virtualbox": ("vboxmanage --version", parse_version_only),
            "vagrant": ("vagrant --version", parse_vagrant_version),
            "proxmox": ("pveversion", parse_version_only),
            "qemu_kvm": ("qemu-system-x86_64 --version", parse_qemu_version),
        }
        for tool, (command, parser) in checks.items():
            await self._detect_tool(executor, tool, command, result, timeout, parser)

    async def _detect_podman(
        self, executor: CommandExecutor, result: dict[str, ToolInfo], timeout: int,
    ) -> None:
        """Détecte Podman avec son socket rootless."""
        podman_version = await executor.run("podman --version", timeout=timeout)
        if not podman_version.success:
            result.setdefault("podman", ToolInfo(available=False))
            return

        version_info = parse_version_only(podman_version.stdout)
        podman_details: dict[str, Any] = {}

        socket_info = await SocketProbe.probe(executor, "podman")
        if socket_info:
            podman_details["socket"] = socket_info.model_dump()

        info_result = await executor.run("podman info --format json", timeout=timeout)
        if info_result.success and info_result.stripped_stdout():
            try:
                podman_details["info"] = json.loads(info_result.stripped_stdout())
            except json.JSONDecodeError:
                podman_details["raw_output"] = info_result.stripped_stdout()

        result["podman"] = ToolInfo(
            available=True,
            version=version_info.get("version") if version_info else None,
            details=podman_details or None,
        )

    async def _check_kvm_device(
        self, executor: CommandExecutor, result: dict[str, ToolInfo], timeout: int,
    ) -> None:
        """Vérifie la présence du device /dev/kvm."""
        kvm_result = await executor.run(
            "test -e /dev/kvm && echo 'present'", timeout=timeout,
        )
        if "present" in kvm_result.stdout:
            existing = result.get("qemu_kvm")
            if existing:
                existing.details = {**(existing.details or {}), "kvm_device": True}
            else:
                result.setdefault("qemu_kvm", ToolInfo(available=True, details={"kvm_device": True}))

    async def _detect_tool(
        self, executor: CommandExecutor, tool_name: str, command: str,
        result: dict[str, ToolInfo], timeout: int,
        parser: Parser | None = None,
    ) -> None:
        """Détecte un outil via une commande CLI optionnelle."""
        cmd_result = await executor.run(command, timeout=timeout)
        if cmd_result.success:
            details = parser(cmd_result.stdout) if parser else None
            result[tool_name] = ToolInfo(
                available=True,
                version=details.get("version") if details else None,
                details=details,
            )
        else:
            result.setdefault(tool_name, ToolInfo(available=False))

    # ─── Détection Docker ─────────────────────────────────────

    async def _detect_docker(
        self, executor: CommandExecutor, host: str,
    ) -> DockerCapabilities | None:
        """Détecte les capacités Docker (CLI + socket)."""
        timeout = self._DEFAULT_TIMEOUT
        docker_version_result = await executor.run("docker --version", timeout=timeout)
        if not docker_version_result.success:
            return None

        docker_version = parse_docker_version(docker_version_result.stdout)
        docker_socket = await self._probe_docker_socket(executor, host)

        # Tentative de détection via socket local
        if docker_socket and self._is_local_execution(executor, host):
            caps = await self._try_docker_socket_capabilities(docker_socket, docker_version, executor)
            if caps:
                return caps

        # Fallback : détection CLI
        return await self._detect_docker_via_cli(executor, docker_version, docker_socket, timeout)

    async def _probe_docker_socket(
        self, executor: CommandExecutor, host: str,
    ) -> SocketInfo | None:
        """Sonde le socket Docker selon le type d'exécution."""
        if self._is_local_execution(executor, host):
            return await SocketProbe.probe_local("docker")
        return await SocketProbe.probe(executor, "docker")

    async def _try_docker_socket_capabilities(
        self, socket_info: SocketInfo, docker_version: str | None,
        executor: CommandExecutor,
    ) -> DockerCapabilities | None:
        """Tente la collecte de capacités via le socket Docker."""
        socket_client = DockerSocketClient(socket_path=socket_info.path)
        if not await socket_client.is_available():
            return None

        capabilities = await socket_client.collect_capabilities()
        if capabilities:
            capabilities.version = capabilities.version or docker_version
            capabilities.socket = socket_info
            capabilities.compose = await self._detect_docker_compose(executor)
            return capabilities
        return None

    async def _detect_docker_via_cli(
        self, executor: CommandExecutor,
        docker_version: str | None, docker_socket: SocketInfo | None,
        timeout: int,
    ) -> DockerCapabilities | None:
        """Détection Docker via CLI en fallback."""
        running = False
        socket_accessible = False
        swarm_info = None

        info_result = await executor.run(
            "docker info --format '{{json .}}'", timeout=timeout,
        )
        if info_result.success and info_result.stripped_stdout():
            running, socket_accessible, swarm_info = self._parse_docker_info_json(
                info_result.stripped_stdout(), info_result.stdout,
            )
        else:
            running = "Swarm:" in info_result.stdout

        compose_info = await self._detect_docker_compose(executor)
        swarm_details = await self._resolve_swarm_details(executor, swarm_info, running, timeout)

        return DockerCapabilities(
            installed=True, version=docker_version,
            running=running, socket_accessible=socket_accessible,
            socket=docker_socket, compose=compose_info, swarm=swarm_details,
        )

    @staticmethod
    def _parse_docker_info_json(
        json_output: str, raw_output: str,
    ) -> tuple[bool, bool, dict | None]:
        """Parse la sortie JSON de ``docker info``."""
        try:
            info_data = json.loads(json_output)
            return True, True, info_data.get("Swarm")
        except json.JSONDecodeError:
            return "Swarm:" in raw_output, False, None

    async def _resolve_swarm_details(
        self, executor: CommandExecutor, swarm_info: dict | None,
        running: bool, timeout: int,
    ) -> DockerSwarmInfo | None:
        """Résout les détails Swarm à partir des infos disponibles."""
        if swarm_info:
            local_state = swarm_info.get("LocalNodeState")
            return DockerSwarmInfo(
                available=local_state not in {None, "inactive"},
                active=local_state == "active",
                node_role=(swarm_info.get("ControlAvailable") and "manager") or "worker",
                details=swarm_info,
            )

        if not running:
            return None

        plain_result = await executor.run("docker info", timeout=timeout)
        if not plain_result.success:
            return None

        if "Swarm: active" in plain_result.stdout:
            return DockerSwarmInfo(available=True, active=True, node_role=None, details=None)
        if "Swarm: inactive" in plain_result.stdout:
            return DockerSwarmInfo(available=True, active=False, node_role=None, details=None)
        return None

    async def _detect_docker_compose(
        self, executor: CommandExecutor,
    ) -> DockerComposeInfo | None:
        """Détecte Docker Compose (plugin v2 ou binaire standalone)."""
        timeout = self._DEFAULT_TIMEOUT

        plugin_result = await executor.run("docker compose version", timeout=timeout)
        if plugin_result.success:
            version = parse_version_only(plugin_result.stdout).get("version")
            return DockerComposeInfo(available=True, version=version, plugin_based=True)

        binary_result = await executor.run("docker-compose --version", timeout=timeout)
        if binary_result.success:
            version = parse_version_only(binary_result.stdout).get("version")
            return DockerComposeInfo(available=True, version=version, plugin_based=False)
        return None

    @staticmethod
    def _is_local_execution(executor: CommandExecutor, host: str) -> bool:
        """Retourne ``True`` si l'exécution est locale."""
        return isinstance(executor, LocalCommandExecutor) and host in {"localhost", "127.0.0.1"}

    # ─── Détection Kubernetes ─────────────────────────────────

    async def _detect_kubernetes(
        self, executor: CommandExecutor,
    ) -> dict[str, ToolInfo]:
        """Détecte les outils Kubernetes et orchestration."""
        kube_tools: dict[str, tuple[str, Parser | None]] = {
            "kubectl": ("kubectl version --client -o json", parse_kubectl_version),
            "kubeadm": ("kubeadm version -o json", parse_kubeadm_version),
            "k3s": ("k3s --version", parse_k3s_version),
            "microk8s": ("microk8s.kubectl version --output=json", parse_kubectl_version),
            "helm": ("helm version --short", parse_version_only),
        }

        kubernetes: dict[str, ToolInfo] = {}
        timeout = self._DEFAULT_TIMEOUT

        for tool, (command, parser) in kube_tools.items():
            result = await executor.run(command, timeout=timeout)
            if result.success and parser:
                parsed = parser(result.stdout)
                kubernetes[tool] = ToolInfo(
                    available=True, version=parsed.get("version"), details=parsed,
                )
            elif result.success:
                kubernetes[tool] = ToolInfo(available=True)
            else:
                kubernetes[tool] = ToolInfo(available=False)
        return kubernetes

    # ─── Détection runtimes de conteneurs ─────────────────────

    async def _detect_container_runtimes(
        self, executor: CommandExecutor,
    ) -> dict[str, ContainerRuntimeInfo]:
        """Détecte les runtimes de conteneurs (LXC, LXD, Incus, containerd)."""
        return {
            "lxc": await self._detect_lxc(executor),
            "lxd": await self._detect_lxd(executor),
            "incus": await self._detect_incus(executor),
            "containerd": await self._detect_containerd(executor),
        }

    async def _detect_lxc(self, executor: CommandExecutor) -> ContainerRuntimeInfo:
        """Détecte les outils LXC bruts."""
        timeout = self._DEFAULT_TIMEOUT
        version_result = await executor.run("lxc-info --version", timeout=timeout)
        if not version_result.success:
            return ContainerRuntimeInfo(available=False)

        details: dict[str, Any] = {}
        checkconfig = await executor.run(
            "lxc-checkconfig 2>/dev/null | head -20", timeout=timeout,
        )
        if checkconfig.success and checkconfig.stripped_stdout():
            details["kernel_support"] = checkconfig.stripped_stdout()

        socket_info = await SocketProbe.probe(executor, "lxc")
        if socket_info:
            details["socket"] = socket_info.model_dump()

        return ContainerRuntimeInfo(
            available=True, version=version_result.stripped_stdout() or None,
            socket=socket_info, details=details or None,
        )

    async def _detect_lxd(self, executor: CommandExecutor) -> ContainerRuntimeInfo:
        """Détecte LXD et son client CLI."""
        timeout = self._DEFAULT_TIMEOUT

        daemon_result = await executor.run("lxd --version", timeout=timeout)
        client_result = await executor.run("lxc version 2>/dev/null", timeout=timeout)

        if not daemon_result.success and not client_result.success:
            return ContainerRuntimeInfo(available=False)

        daemon_version = daemon_result.stripped_stdout() if daemon_result.success else None
        client_version = (
            parse_version_only(client_result.stdout).get("version")
            if client_result.success else None
        )

        details: dict[str, Any] = {}
        install_method = await self._detect_snap_install(executor, "lxd", details)
        socket_info = await self._detect_service_socket(executor, "lxd", details, timeout)

        return ContainerRuntimeInfo(
            available=True, version=daemon_version or client_version,
            socket=socket_info, install_method=install_method,
            details=details or None,
        )

    async def _detect_incus(self, executor: CommandExecutor) -> ContainerRuntimeInfo:
        """Détecte Incus (fork communautaire de LXD)."""
        timeout = self._DEFAULT_TIMEOUT
        version_result = await executor.run("incus version", timeout=timeout)
        if not version_result.success:
            return ContainerRuntimeInfo(available=False)

        parsed = parse_version_only(version_result.stdout)
        details: dict[str, Any] = {}
        install_method = await self._detect_snap_install(executor, "incus", details)
        socket_info = await self._detect_service_socket(executor, "incus", details, timeout)

        return ContainerRuntimeInfo(
            available=True,
            version=parsed.get("version", version_result.stripped_stdout()),
            socket=socket_info, install_method=install_method,
            details=details or None,
        )

    async def _detect_containerd(self, executor: CommandExecutor) -> ContainerRuntimeInfo:
        """Détecte le runtime containerd."""
        timeout = self._DEFAULT_TIMEOUT
        version_result = await executor.run("containerd --version", timeout=timeout)
        if not version_result.success:
            return await self._detect_containerd_via_ctr(executor, timeout)

        parsed = parse_version_only(version_result.stdout)
        details: dict[str, Any] = {}
        socket_info = await SocketProbe.probe(executor, "containerd")
        if socket_info:
            details["socket"] = socket_info.model_dump()

        k3s_check = await executor.run(
            "test -S /run/k3s/containerd/containerd.sock && echo 'k3s'", timeout=timeout,
        )
        if k3s_check.success and "k3s" in k3s_check.stdout:
            details["managed_by"] = "k3s"

        return ContainerRuntimeInfo(
            available=True, version=parsed.get("version"),
            socket=socket_info, details=details or None,
        )

    async def _detect_containerd_via_ctr(
        self, executor: CommandExecutor, timeout: int,
    ) -> ContainerRuntimeInfo:
        """Tente de détecter containerd via ``ctr``."""
        ctr_result = await executor.run("ctr version", timeout=timeout)
        if not ctr_result.success:
            return ContainerRuntimeInfo(available=False)
        parsed = parse_version_only(ctr_result.stdout)
        return ContainerRuntimeInfo(
            available=True, version=parsed.get("version"),
            details={"detected_via": "ctr"},
        )

    # ─── Détection outils OCI ─────────────────────────────────

    async def _detect_oci_tools(
        self, executor: CommandExecutor,
    ) -> dict[str, ToolInfo]:
        """Détecte les runtimes et outils OCI (runc, crun, buildah, skopeo, podman-compose)."""
        timeout = self._DEFAULT_TIMEOUT
        oci_checks: dict[str, tuple[str, Parser | None]] = {
            "runc": ("runc --version", parse_runc_version),
            "crun": ("crun --version", parse_version_only),
            "buildah": ("buildah --version", parse_version_only),
            "skopeo": ("skopeo --version", parse_version_only),
            "podman_compose": ("podman-compose --version", parse_version_only),
        }

        tools: dict[str, ToolInfo] = {}
        for tool, (command, parser) in oci_checks.items():
            result = await executor.run(command, timeout=timeout)
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

    # ─── Helpers de détection génériques ──────────────────────

    async def _detect_snap_install(
        self, executor: CommandExecutor, tool: str, details: dict[str, Any],
    ) -> str:
        """Détecte si un outil est installé via snap."""
        snap_result = await executor.run(
            f"snap list {tool} 2>/dev/null | tail -1", timeout=self._DEFAULT_TIMEOUT,
        )
        if snap_result.success and snap_result.stripped_stdout():
            details["snap_info"] = snap_result.stripped_stdout()
            return "snap"
        return "package"

    async def _detect_service_socket(
        self, executor: CommandExecutor, tool: str, details: dict[str, Any], timeout: int,
    ) -> SocketInfo | None:
        """Détecte le socket et le statut du service pour un outil."""
        socket_info = await SocketProbe.probe(executor, tool)
        if socket_info:
            details["socket"] = socket_info.model_dump()

        if tool == "lxd":
            service_cmd = (
                "systemctl is-active snap.lxd.daemon 2>/dev/null "
                "|| systemctl is-active lxd 2>/dev/null"
            )
        else:
            service_cmd = f"systemctl is-active {tool} 2>/dev/null"

        service_result = await executor.run(service_cmd, timeout=timeout)
        if service_result.success and service_result.stripped_stdout():
            details["service_status"] = service_result.stripped_stdout()

        return socket_info
