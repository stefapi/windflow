"""
Centralized enums for the target domain.

Single source of truth — imported by models, schemas, and services.
"""

from enum import Enum


class TargetType(str, Enum):
    """Types de cibles de déploiement supportés."""

    DOCKER = "docker"
    DOCKER_COMPOSE = "docker_compose"
    DOCKER_SWARM = "docker_swarm"
    KUBERNETES = "kubernetes"
    VM = "vm"
    PHYSICAL = "physical"


class TargetStatus(str, Enum):
    """Statuts possibles pour une cible."""

    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class SSHAuthMethod(str, Enum):
    """Méthodes d'authentification SSH supportées."""

    LOCAL = "local"
    PASSWORD = "password"
    SSH_KEY = "ssh_key"


class CapabilityType(str, Enum):
    """Types de capacités détectées sur une cible."""

    # Virtualisation
    LIBVIRT = "libvirt"
    VIRSH = "virsh"
    VIRTUALBOX = "virtualbox"
    VAGRANT = "vagrant"
    PROXMOX = "proxmox"
    QEMU_KVM = "qemu_kvm"
    MULTIPASS = "multipass"

    # Conteneurisation — Docker
    DOCKER = "docker"
    DOCKER_COMPOSE = "docker_compose"
    DOCKER_SWARM = "docker_swarm"

    # Conteneurisation — Podman
    PODMAN = "podman"
    PODMAN_COMPOSE = "podman_compose"

    # Conteneurisation — Système (LXC/LXD/Incus)
    LXC = "lxc"
    LXD = "lxd"
    INCUS = "incus"

    # Runtimes OCI bas niveau
    RUNC = "runc"
    CRUN = "crun"
    CONTAINERD = "containerd"

    # Outils OCI
    BUILDAH = "buildah"
    SKOPEO = "skopeo"

    # Kubernetes / Orchestration
    KUBECTL = "kubectl"
    KUBEADM = "kubeadm"
    K3S = "k3s"
    MICROK8S = "microk8s"
    HELM = "helm"
