"""Enums canoniques du domaine Host (spec 06 — STORY-166.1).

Source de vérité unique du modèle directeur : ``HostProfile`` (3 valeurs,
``host_kubernetes`` supprimé — spec 02, arbitrage Kubernetes : les grappes
multi-nœuds deviendront l'entité ``Cluster`` en Roadmap Phase 2),
``HostStatus`` (statuts unifiés) et ``WorkloadOrigin`` (axe origine de la
matrice « profil × origine »).

Les enums d'accès (``SSHAuthMethod``, ``AccessLevel``, ``CapabilityType``)
sont inchangés par le renommage ``Target``→``Host`` : leurs définitions
sont **déplacées ici** (home canonique du domaine) et re-exportées par
:mod:`app.enums.target` pour la compatibilité des imports legacy — la
direction d'import est unique (``target`` → ``host``), l'inverse
(hôte ← cible, tel que rédigé initialement dans la story) créant un
cycle d'import cassant le build.

⚠️ Les colonnes issues de ces enums persistent désormais les **valeurs**
(``values_callable`` — 'online', 'host_baremetal'…) ; les bases legacy
stockaient les **noms de membres** ('ONLINE', 'DOCKER'…) : la
normalisation nom-ou-valeur est portée par
:mod:`app.helper.target_host_migration` et la migration ``1661``.
"""

from enum import Enum


class HostProfile(str, Enum):
    """Profils canoniques d'un Host (spec 06 § Profils canoniques).

    Le profil décrit **comment on pilote** le substrat, pas ce qu'il y a
    dessous (modèle compute spec 03) :

    - ``host_baremetal`` : pilotage direct d'une machine physique ou
      virtuelle (accès local ou SSH) ;
    - ``host_proxmox`` : serveur Proxmox VE isolé (un cluster Proxmox =
      entité ``Cluster``) ;
    - ``host_remote_docker`` : pilotage d'un Docker **distant** (TCP/API)
      — réservé à cet usage, un Docker sur socket local est
      ``host_baremetal``.
    """

    HOST_BAREMETAL = "host_baremetal"
    HOST_PROXMOX = "host_proxmox"
    HOST_REMOTE_DOCKER = "host_remote_docker"


class HostStatus(str, Enum):
    """Statuts unifiés d'un Host (spec 06 § Statuts unifiés).

    - ``online`` : joignable ;
    - ``offline`` : injoignable / arrêté ;
    - ``unreachable`` : détecté injoignable (sémantique canonique de
      l'ancien ``TargetStatus.ERROR``) ;
    - ``scanning`` : scan de capacités en cours (posé par
      ``mark_scan_in_progress``, STORY-166.1).
    """

    ONLINE = "online"
    OFFLINE = "offline"
    UNREACHABLE = "unreachable"
    SCANNING = "scanning"


class WorkloadOrigin(str, Enum):
    """Origine d'un workload (spec 06 — matrice « profil × origine »).

    Deuxième axe canonique : il s'appliquera aux Apps, Machines et
    Clusters ; la colonne ``hosts.origin`` le porte dès cette story
    (défaut ``managed``), la pose métier complète relève de STORY-166.4.
    """

    MANAGED = "managed"
    ADOPTED = "adopted"
    EXTERNAL = "external"


# ─── Enums d'accès (déplacés depuis enums/target.py — STORY-166.1) ─────


class SSHAuthMethod(str, Enum):
    """Méthodes d'authentification SSH supportées."""

    LOCAL = "local"
    PASSWORD = "password"
    SSH_KEY = "ssh_key"


class AccessLevel(str, Enum):
    """Niveau d'accès détecté sur une cible."""

    ROOT = "root"  # SSH user is root
    SUDO = "sudo"  # Can escalate to root via sudo (with password)
    SUDO_PASSWORDLESS = "sudo_passwordless"  # sudo without password
    LIMITED = "limited"  # No root access, standard user only


class CapabilityType(str, Enum):
    """Types de capacités détectées sur un host."""

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
