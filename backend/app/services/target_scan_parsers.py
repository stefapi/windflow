"""
Parsers et constructeurs de capacités pour le scan de cibles.

Contient toutes les fonctions de parsing de version, les mappings de clés
vers ``CapabilityType``, et le constructeur de payload de capacités.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from ..enums.target import CapabilityType
from ..schemas.target_scan import (
    ContainerRuntimeInfo,
    PlatformArchitecture,
    ScanResult,
    ToolInfo,
)


# ─── Type alias ────────────────────────────────────────────────

Parser = Callable[[str], dict[str, Any]]


# ─── Architecture ──────────────────────────────────────────────


def map_architecture(raw_arch: str) -> PlatformArchitecture:
    """Mappe une chaîne d'architecture vers :class:`PlatformArchitecture`.

    Args:
        raw_arch: Sortie brute de ``uname -m``.

    Returns:
        L'énumération d'architecture correspondante.
    """
    normalized = raw_arch.strip().lower()
    arch_map: dict[str, PlatformArchitecture] = {
        "x86_64": PlatformArchitecture.X86_64,
        "amd64": PlatformArchitecture.X86_64,
        "i386": PlatformArchitecture.X86_32,
        "i686": PlatformArchitecture.X86_32,
        "aarch64": PlatformArchitecture.ARM64,
        "arm64": PlatformArchitecture.ARM64,
        "armv8": PlatformArchitecture.ARMV8,
        "armv8l": PlatformArchitecture.ARMV8,
        "armv7l": PlatformArchitecture.ARMV7,
        "armv7": PlatformArchitecture.ARMV7,
        "armv6l": PlatformArchitecture.ARMV6,
        "armv6": PlatformArchitecture.ARMV6,
    }
    return arch_map.get(normalized, PlatformArchitecture.UNKNOWN)


# ─── Parsers de version ────────────────────────────────────────


def strip_quotes(value: str) -> str:
    """Supprime les guillemets entourant une chaîne."""
    stripped = value.strip()
    if stripped.startswith(('"', "'")) and stripped.endswith(('"', "'")):
        return stripped[1:-1]
    return stripped


def parse_version_only(output: str) -> dict[str, Any]:
    """Extrait un numéro de version (X.Y.Z) d'une sortie texte.

    Args:
        output: Sortie brute d'une commande ``--version``.

    Returns:
        Dict avec la clé ``"version"`` si trouvée, sinon dict vide.
    """
    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", output)
    if match:
        return {"version": match.group(1)}
    return {}


def parse_vagrant_version(output: str) -> dict[str, Any]:
    """Parse la version de Vagrant."""
    result = parse_version_only(output)
    if result:
        result["raw"] = output.strip()
    return result


def parse_qemu_version(output: str) -> dict[str, Any]:
    """Parse la version de QEMU."""
    first_line = output.splitlines()[0] if output else ""
    version_info = parse_version_only(first_line)
    if version_info:
        version_info["raw"] = first_line.strip()
    return version_info


def parse_docker_version(output: str) -> str | None:
    """Extrait la version Docker d'une sortie texte.

    Returns:
        Le numéro de version ou ``None``.
    """
    info = parse_version_only(output)
    return info.get("version")


def parse_kubectl_version(output: str) -> dict[str, Any]:
    """Parse la version de kubectl (JSON ou texte).

    Args:
        output: Sortie de ``kubectl version --client -o json``.

    Returns:
        Dict avec ``"version"``, ``"major"``, ``"minor"``.
    """
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


def parse_kubeadm_version(output: str) -> dict[str, Any]:
    """Parse la version de kubeadm (JSON ou texte)."""
    try:
        data = json.loads(output)
        return {
            "version": data.get("clientVersion", {}).get("gitVersion"),
            "major": data.get("clientVersion", {}).get("major"),
            "minor": data.get("clientVersion", {}).get("minor"),
        }
    except json.JSONDecodeError:
        return parse_version_only(output)


def parse_k3s_version(output: str) -> dict[str, Any]:
    """Parse la version de k3s (ex: ``k3s version v1.28.4+k3s2``)."""
    match = re.search(r"v?(\d+\.\d+(?:\.\d+)?(?:\+\S+)?)", output)
    if match:
        return {"version": match.group(1)}
    return parse_version_only(output)


def parse_runc_version(output: str) -> dict[str, Any]:
    """Parse la version de runc (potentiellement multi-ligne)."""
    for line in output.splitlines():
        if "runc" in line.lower() or line.strip().startswith("1.") or line.strip().startswith("2."):
            return parse_version_only(line)
    return parse_version_only(output)


# ─── Mappings clé → CapabilityType ────────────────────────────

_VIRTUALIZATION_MAP: dict[str, CapabilityType] = {
    "libvirt": CapabilityType.LIBVIRT,
    "virsh": CapabilityType.VIRSH,
    "virtualbox": CapabilityType.VIRTUALBOX,
    "vagrant": CapabilityType.VAGRANT,
    "proxmox": CapabilityType.PROXMOX,
    "qemu_kvm": CapabilityType.QEMU_KVM,
    "podman": CapabilityType.PODMAN,
    "multipass": CapabilityType.MULTIPASS,
}

_KUBERNETES_MAP: dict[str, CapabilityType] = {
    "kubectl": CapabilityType.KUBECTL,
    "kubeadm": CapabilityType.KUBEADM,
    "k3s": CapabilityType.K3S,
    "microk8s": CapabilityType.MICROK8S,
    "helm": CapabilityType.HELM,
}

_RUNTIME_MAP: dict[str, CapabilityType] = {
    "lxc": CapabilityType.LXC,
    "lxd": CapabilityType.LXD,
    "incus": CapabilityType.INCUS,
    "containerd": CapabilityType.CONTAINERD,
}

_OCI_MAP: dict[str, CapabilityType] = {
    "runc": CapabilityType.RUNC,
    "crun": CapabilityType.CRUN,
    "buildah": CapabilityType.BUILDAH,
    "skopeo": CapabilityType.SKOPEO,
    "podman_compose": CapabilityType.PODMAN_COMPOSE,
}


def map_virtualization_key(key: str) -> CapabilityType | None:
    """Mappe une clé de virtualisation vers ``CapabilityType``."""
    return _VIRTUALIZATION_MAP.get(key.lower())


def map_kubernetes_key(key: str) -> CapabilityType | None:
    """Mappe une clé kubernetes vers ``CapabilityType``."""
    return _KUBERNETES_MAP.get(key.lower())


def map_runtime_key(key: str) -> CapabilityType | None:
    """Mappe une clé de runtime vers ``CapabilityType``."""
    return _RUNTIME_MAP.get(key.lower())


def map_oci_key(key: str) -> CapabilityType | None:
    """Mappe une clé OCI vers ``CapabilityType``."""
    return _OCI_MAP.get(key.lower())


# ─── Extraction d'informations outil ──────────────────────────


def extract_tool_info(
    info: Any,
) -> tuple[bool, str | None, dict[str, Any | None]]:
    """Extrait les informations standardisées d'un outil détecté.

    Accepte un :class:`ToolInfo` ou un dict brut.

    Returns:
        Tuple (available, version, details).
    """
    if isinstance(info, ToolInfo):
        return info.available, info.version, info.details
    if isinstance(info, dict):
        available = bool(info.get("available"))
        version = info.get("version")
        raw_details = info.get("details")
        details = raw_details if isinstance(raw_details, dict) else None
        return available, version, details
    return False, None, None


# ─── Extraction de noms de capacités ──────────────────────────


def extract_capability_names(capabilities_payload: list[dict[str, Any]]) -> list[str]:
    """Extrait les noms de types de capacité d'un payload.

    Args:
        capabilities_payload: Liste de dicts de capacité.

    Returns:
        Liste triée de noms uniques.
    """
    names: list[str] = []
    for cap in capabilities_payload:
        cap_type = cap.get("capability_type")
        if cap_type:
            names.append(cap_type.value if hasattr(cap_type, "value") else str(cap_type))
    return sorted(set(names))


# ─── Constructeur de payload de capacités ─────────────────────


def build_capabilities_payload(scan_result: ScanResult) -> list[dict[str, Any]]:
    """Construit la liste normalisée des capacités détectées.

    Ne crée des entrées que pour les capacités réellement disponibles.

    Args:
        scan_result: Résultat complet du scan.

    Returns:
        Liste de dicts de capacité prêts à être persistés.
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

    _build_virtualization_caps(scan_result, add_capability)
    _build_docker_caps(scan_result, add_capability)
    _build_kubernetes_caps(scan_result, add_capability)
    _build_runtime_caps(scan_result, add_capability)
    _build_oci_caps(scan_result, add_capability)

    return capabilities


def _build_virtualization_caps(
    scan_result: ScanResult,
    add_fn: Callable,
) -> None:
    """Ajoute les capacités de virtualisation au payload."""
    virtualization = scan_result.virtualization or {}
    for key, info in virtualization.items():
        cap_type = map_virtualization_key(key)
        if cap_type is None:
            continue
        available, version, details = extract_tool_info(info)
        add_fn(cap_type, available, version, details)


def _build_docker_caps(
    scan_result: ScanResult,
    add_fn: Callable,
) -> None:
    """Ajoute les capacités Docker (engine, compose, swarm) au payload."""
    docker_caps = scan_result.docker
    if docker_caps is None or not docker_caps.installed:
        return

    docker_details: dict[str, Any] = {
        "running": docker_caps.running,
        "socket_accessible": docker_caps.socket_accessible,
    }
    if docker_caps.socket:
        docker_details["socket"] = docker_caps.socket.model_dump()
    add_fn(CapabilityType.DOCKER, docker_caps.installed, docker_caps.version, docker_details)

    _build_docker_compose_cap(docker_caps, add_fn)
    _build_docker_swarm_cap(docker_caps, add_fn)


def _build_docker_compose_cap(docker_caps, add_fn: Callable) -> None:
    """Ajoute la capacité Docker Compose si disponible."""
    compose = docker_caps.compose
    if not compose or not compose.available:
        return
    compose_details: dict[str, Any] = {}
    if compose.plugin_based is not None:
        compose_details["plugin_based"] = compose.plugin_based
    add_fn(CapabilityType.DOCKER_COMPOSE, compose.available, compose.version, compose_details or None)


def _build_docker_swarm_cap(docker_caps, add_fn: Callable) -> None:
    """Ajoute la capacité Docker Swarm si disponible."""
    swarm = docker_caps.swarm
    if not swarm or not swarm.available:
        return
    swarm_details = swarm.details or {
        "active": swarm.active,
        "node_role": swarm.node_role,
    }
    add_fn(CapabilityType.DOCKER_SWARM, swarm.available, None, swarm_details)


def _build_kubernetes_caps(
    scan_result: ScanResult,
    add_fn: Callable,
) -> None:
    """Ajoute les capacités Kubernetes au payload."""
    kubernetes_tools = scan_result.kubernetes or {}
    for key, info in kubernetes_tools.items():
        cap_type = map_kubernetes_key(key)
        if cap_type is None:
            continue
        available, version, details = extract_tool_info(info)
        add_fn(cap_type, available, version, details)


def _build_runtime_caps(
    scan_result: ScanResult,
    add_fn: Callable,
) -> None:
    """Ajoute les capacités de runtimes de conteneurs au payload."""
    container_runtimes = scan_result.container_runtimes or {}
    for key, info in container_runtimes.items():
        cap_type = map_runtime_key(key)
        if cap_type is None:
            continue
        details_payload: dict[str, Any | None] = {}
        if info.socket:
            details_payload["socket"] = info.socket.model_dump()
        if info.install_method:
            details_payload["install_method"] = info.install_method
        if info.details:
            details_payload.update(info.details)
        add_fn(cap_type, info.available, info.version, details_payload or None)


def _build_oci_caps(
    scan_result: ScanResult,
    add_fn: Callable,
) -> None:
    """Ajoute les capacités d'outils OCI au payload."""
    oci_tools = scan_result.oci_tools or {}
    for key, info in oci_tools.items():
        cap_type = map_oci_key(key)
        if cap_type is None:
            continue
        available, version, details = extract_tool_info(info)
        add_fn(cap_type, available, version, details)
