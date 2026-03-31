"""
Clients de détection par socket pour le scan de cibles.

Fournit la détection via sockets Unix pour Docker, Libvirt, et les runtimes
de conteneurs, ainsi que la sonde de topologie socket centralisée.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from ..schemas.target_scan import (
    DockerCapabilities,
    DockerSwarmInfo,
    SocketInfo,
)
from .commands import CommandExecutor

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


# ─── Sonde de topologie socket ────────────────────────────────


class SocketProbe:
    """Définitions centralisées des chemins de sockets et utilitaires de sonde.

    Associe chaque outil conteneur/VM à ses emplacements de socket Unix possibles,
    couvrant les variantes système (root), rootless (utilisateur), session et snap.
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
        """Remplace les marqueurs ``{uid}`` par l'UID courant."""
        uid = os.getuid()
        return [p.format(uid=uid) for p in paths]

    @classmethod
    async def probe(
        cls,
        executor: CommandExecutor,
        tool: str,
        timeout: int = 5,
    ) -> SocketInfo | None:
        """Sonde les chemins de socket pour *tool* et retourne le premier trouvé.

        Essaie d'abord les chemins système, puis rootless/session.
        Retourne un :class:`SocketInfo` même si le socket n'est pas
        accessible en lecture (``exists=True, accessible=False``).
        """
        paths_by_mode = cls.SOCKET_PATHS.get(tool)
        if not paths_by_mode:
            return None

        probe_order = cls._build_probe_order(paths_by_mode)

        for mode, paths in probe_order:
            result = await cls._probe_paths(executor, paths, mode, timeout)
            if result is not None:
                return result
        return None

    @classmethod
    def _build_probe_order(
        cls, paths_by_mode: dict[str, list[str]]
    ) -> list[tuple[str, list[str]]]:
        """Construit l'ordre de sonde : système → rootless → session."""
        order: list[tuple[str, list[str]]] = []
        for mode in ("system", "rootless", "session"):
            raw = paths_by_mode.get(mode)
            if raw:
                resolved = cls._resolve_uid_paths(raw) if "{uid}" in str(raw) else raw
                order.append((mode, resolved))
        return order

    @classmethod
    async def _probe_paths(
        cls,
        executor: CommandExecutor,
        paths: list[str],
        mode: str,
        timeout: int,
    ) -> SocketInfo | None:
        """Sonde une liste de chemins de socket pour un mode donné."""
        for socket_path in paths:
            exists_result = await executor.run(
                f"test -S {socket_path}", timeout=timeout,
            )
            if not exists_result.success:
                continue

            accessible_result = await executor.run(
                f"test -r {socket_path}", timeout=timeout,
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
        """Sonde locale rapide (pas de subprocess, vérifications ``Path`` uniquement).

        Retourne un :class:`SocketInfo` même quand le socket existe
        mais n'est pas accessible en lecture.
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


# ─── Détection d'environnement ────────────────────────────────


class ContainerEnvironmentDetector:
    """Détecte les caractéristiques de l'environnement d'exécution."""

    _DOCKERENV = Path("/.dockerenv")

    @staticmethod
    def is_in_container() -> bool:
        """Retourne ``True`` si l'exécution a lieu dans un conteneur."""
        if ContainerEnvironmentDetector._DOCKERENV.exists():
            return True
        try:
            with open("/proc/1/cgroup", encoding="utf-8") as f:
                content = f.read().lower()
            return any(
                token in content for token in ("docker", "containerd", "kubepods")
            )
        except FileNotFoundError:  # pragma: no cover - uncommon
            return False


# ─── Client Docker via socket ─────────────────────────────────


class DockerSocketClient:
    """Collecte les capacités Docker via le socket Unix monté."""

    def __init__(self, socket_path: str = "/var/run/docker.sock"):
        self.socket_path = socket_path

    async def is_available(self) -> bool:
        """Retourne ``True`` si le socket Docker est accessible."""
        if docker is None or not Path(self.socket_path).exists():
            return False
        return await asyncio.to_thread(self._can_connect)

    async def collect_capabilities(self) -> DockerCapabilities | None:
        """Collecte les capacités Docker via le socket."""
        if docker is None:
            return None
        return await asyncio.to_thread(self._collect_capabilities_sync)

    def _create_client(self):
        """Crée un client Docker pointant vers le socket."""
        return docker.DockerClient(base_url=f"unix://{self.socket_path}")  # type: ignore[no-any-return]

    def _can_connect(self) -> bool:
        """Vérifie la connexion au démon Docker (synchrone)."""
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
        """Collecte synchrone des capacités Docker."""
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
                swarm=DockerSocketClient._build_swarm_info(swarm_info),
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
        """Construit les informations Swarm à partir du dict Docker info."""
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


# ─── Client Libvirt via socket ────────────────────────────────


class LibvirtSocketClient:
    """Collecte les capacités libvirt (KVM/QEMU) via le socket."""

    def __init__(
        self,
        socket_path: str = "/var/run/libvirt/libvirt-sock",
        uri: str = "qemu:///system",
    ):
        self.socket_path = socket_path
        self.uri = uri

    async def is_available(self) -> bool:
        """Retourne ``True`` si le socket libvirt est accessible."""
        if libvirt is None or not Path(self.socket_path).exists():
            return False
        return await asyncio.to_thread(self._can_connect)

    async def collect_details(self) -> dict[str, Any]:
        """Collecte les informations hôte et VM via libvirt."""
        if libvirt is None:
            return {}
        return await asyncio.to_thread(self._collect_details_sync)

    def _can_connect(self) -> bool:
        """Vérifie la connexion en lecture seule à libvirt (synchrone)."""
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
        """Collecte synchrone des détails libvirt."""
        connection = None
        try:
            connection = libvirt.openReadOnly(self.uri)
            if connection is None:
                return {}

            version = connection.getVersion()
            lib_version = connection.getLibVersion()
            host_info = connection.getInfo()

            domains_summary = self._collect_domains(connection)

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
    def _collect_domains(connection) -> list[dict[str, Any]]:
        """Collecte les informations de tous les domaines."""
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
        return domains_summary

    @staticmethod
    def _format_version(value: int) -> str | None:
        """Formate un numéro de version libvirt (entier → chaîne)."""
        if not value:
            return None
        major = value // 1_000_000
        minor = (value // 1_000) % 1_000
        patch = value % 1_000
        return f"{major}.{minor}.{patch}"
