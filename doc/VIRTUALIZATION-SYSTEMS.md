# Systèmes de Virtualisation & Conteneurisation — Architecture WindFlow

Ce document décrit l'organisation complète des systèmes de virtualisation et conteneurisation
supportés par WindFlow, la classification en groupes et catégories, les stratégies d'installation
sur les plateformes cibles, et l'architecture des services mutualisés.

---

## Table des matières

1. [Taxonomie des systèmes](#1-taxonomie-des-systèmes)
2. [Fiches détaillées par système](#2-fiches-détaillées-par-système)
3. [Architecture d'installation distante](#3-architecture-dinstallation-distante)
4. [Services mutualisés — Interfaces abstraites](#4-services-mutualisés--interfaces-abstraites)
5. [Matrice de mutualisation](#5-matrice-de-mutualisation)
6. [Impacts sur le code existant](#6-impacts-sur-le-code-existant)
7. [Plan de mise en œuvre](#7-plan-de-mise-en-œuvre)

---

## 1. Taxonomie des systèmes

WindFlow classifie les systèmes en **3 groupes**, chacun contenant des catégories et des
outils/interfaces. Cette hiérarchie guide la détection, l'installation et les services exposés.

```
┌─────────────────────────────────────────────────────────────────┐
│                    WINDFLOW — SYSTÈMES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─ GROUPE VMs ──────────────────────────────────────────────┐  │
│  │                                                           │  │
│  │  Catégorie Hyperviseurs                                   │  │
│  │  ├── QEMU/KVM          (outil CLI + /dev/kvm + sockets)   │  │
│  │  └── VirtualBox        (outil CLI uniquement)              │  │
│  │                                                           │  │
│  │  Catégorie Gestionnaires libvirt                          │  │
│  │  ├── Libvirt/Virsh     (libs + CLI + socket Unix)         │  │
│  │  └── Virt-install      (CLI, complément libvirt)          │  │
│  │                                                           │  │
│  │  Catégorie Provisioning                                   │  │
│  │  └── Vagrant           (outil CLI, wrapper hyperviseur)   │  │
│  │                                                           │  │
│  │  Catégorie Containers Système (VMs légères)               │  │
│  │  ├── LXC               (outil CLI + socket)               │  │
│  │  ├── LXD               (outil CLI + socket + snap)        │  │
│  │  └── Incus             (outil CLI + socket + snap)        │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ GROUPE CONTAINERS ───────────────────────────────────────┐  │
│  │                                                           │  │
│  │  Catégorie Moteurs de conteneurs                          │  │
│  │  ├── Docker            (CLI + socket + API REST)          │  │
│  │  └── Podman            (CLI + socket rootless)            │  │
│  │                                                           │  │
│  │  Catégorie Runtimes bas niveau                            │  │
│  │  ├── Containerd        (daemon + socket)                  │  │
│  │  ├── Runc              (CLI, runtime OCI de référence)    │  │
│  │  └── Crun              (CLI, runtime OCI alternatif)      │  │
│  │                                                           │  │
│  │  Catégorie Outils OCI                                    │  │
│  │  ├── Buildah           (build sans daemon)                │  │
│  │  └── Skopeo            (transport d'images)               │  │
│  │                                                           │  │
│  │  Catégorie Compose                                       │  │
│  │  ├── Docker Compose    (plugin v2 / standalone v1)        │  │
│  │  └── Podman Compose    (wrapper Podman)                   │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ GROUPE ORCHESTRATION ─────────────────────────────────────┐ │
│  │                                                           │  │
│  │  Catégorie Kubernetes                                    │  │
│  │  ├── K8s (kubeadm)     (CLI + API server + kubeconfig)   │  │
│  │  ├── K3s               (binaire unique + socket containerd)│ │
│  │  └── MicroK8s          (snap + CLI intégrée)              │  │
│  │                                                           │  │
│  │  Catégorie Outils K8s                                    │  │
│  │  ├── Kubectl           (CLI, client universel K8s)        │  │
│  │  └── Helm              (CLI, gestionnaire de packages)    │  │
│  │                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.1 Enumération normée

Cette taxonomie doit se refléter dans le code via des enums structurés :

```python
class VirtualizationGroup(str, Enum):
    """Groupes principaux de systèmes."""
    VMS = "vms"
    CONTAINERS = "containers"
    ORCHESTRATION = "orchestration"

class SystemCategory(str, Enum):
    """Catégories au sein de chaque groupe."""
    # Groupe VMs
    HYPERVISORS = "hypervisors"
    LIBVIRT_MANAGERS = "libvirt_managers"
    PROVISIONING = "provisioning"
    SYSTEM_CONTAINERS = "system_containers"
    # Groupe Containers
    CONTAINER_ENGINES = "container_engines"
    LOWLEVEL_RUNTIMES = "lowlevel_runtimes"
    OCI_TOOLS = "oci_tools"
    COMPOSE = "compose"
    # Groupe Orchestration
    KUBERNETES = "kubernetes"
    K8S_TOOLS = "k8s_tools"

class SystemTool(str, Enum):
    """Outils individuels détectables."""
    # VMs — Hyperviseurs
    QEMU_KVM = "qemu_kvm"
    VIRTUALBOX = "virtualbox"
    # VMs — Libvirt
    LIBVIRT = "libvirt"
    VIRSH = "virsh"
    VIRT_INSTALL = "virt_install"
    # VMs — Provisioning
    VAGRANT = "vagrant"
    # VMs — Containers système
    LXC = "lxc"
    LXD = "lxd"
    INCUS = "incus"
    # Containers — Moteurs
    DOCKER = "docker"
    PODMAN = "podman"
    # Containers — Runtimes
    CONTAINERD = "containerd"
    RUNC = "runc"
    CRUN = "crun"
    # Containers — Outils OCI
    BUILDAH = "buildah"
    SKOPEO = "skopeo"
    # Containers — Compose
    DOCKER_COMPOSE = "docker_compose"
    PODMAN_COMPOSE = "podman_compose"
    # Orchestration — K8s
    KUBEADM = "kubeadm"
    K3S = "k3s"
    MICROK8S = "microk8s"
    # Orchestration — Outils
    KUBECTL = "kubectl"
    HELM = "helm"
```

### 1.2 Mapping Groupe → Catégorie → Outils

| Groupe | Catégorie | Outils | Interfaces |
|--------|-----------|--------|------------|
| VMs | Hyperviseurs | `qemu_kvm`, `virtualbox` | CLI, `/dev/kvm` (QEMU) |
| VMs | Libvirt Managers | `libvirt`, `virsh`, `virt_install` | CLI, socket Unix, lib C |
| VMs | Provisioning | `vagrant` | CLI uniquement |
| VMs | System Containers | `lxc`, `lxd`, `incus` | CLI, socket Unix, snap |
| Containers | Container Engines | `docker`, `podman` | CLI, socket Unix, API REST |
| Containers | Lowlevel Runtimes | `containerd`, `runc`, `crun` | CLI, socket Unix |
| Containers | OCI Tools | `buildah`, `skopeo` | CLI uniquement |
| Containers | Compose | `docker_compose`, `podman_compose` | CLI (plugin ou standalone) |
| Orchestration | Kubernetes | `kubeadm`, `k3s`, `microk8s` | CLI, API server, kubeconfig |
| Orchestration | K8s Tools | `kubectl`, `helm` | CLI |

---

## 2. Fiches détaillées par système

Chaque fiche décrit la détection, les prérequis, les plateformes supportées,
les variantes de version, et les services applicables.

---

### 2.1 QEMU/KVM

**Groupe :** VMs — Hyperviseurs
**Détection actuelle :** `target_scanner_service._detect_cli_tools` + `_check_kvm_device`

| Aspect | Détail |
|--------|--------|
| **Commande de détection** | `qemu-system-x86_64 --version`, `test -e /dev/kvm` |
| **Socket** | Aucun socket direct (passe par libvirt) |
| **Prérequis noyau** | Modules `kvm`, `kvm_intel` ou `kvm_amd` chargés, VT-x/AMD-V dans le BIOS |
| **Architectures** | amd64 (KVM natif), arm64 (KVM sur ARM), émulation TCG sans KVM |

**Variantes de version / plateforme :**

| Famille OS | Variante | Notes |
|------------|----------|-------|
| Debian 11+ | `qemu-kvm` + `qemu-system-x86` | Paquet principal |
| Debian < 11 | `qemu-kvm` (binaire séparé) | Ancien packaging |
| Ubuntu 20.04+ | `qemu-kvm` | Identique Debian |
| Ubuntu 18.04 | `qemu-system-x86` | Pas de meta-paquet `qemu-kvm` |
| RHEL 8/9 | `qemu-kvm` | Module stream AppStream |
| Fedora | `qemu-kvm` | Version récente |
| Alpine | `qemu-system-x86_64` + `qemu-modules` | Paquets séparés |
| Arch Linux | `qemu-full` ou `qemu-headless` | Choix GUI/headless |

**Services WindFlow applicables :** `VMService` (via le moteur libvirt)

---

### 2.2 Libvirt / Virsh

**Groupe :** VMs — Gestionnaires
**Détection actuelle :** `target_scanner_service._detect_libvirt` + `socket_clients.LibvirtSocketClient`

| Aspect | Détail |
|--------|--------|
| **Commande de détection** | `virsh --version`, `virt-install --version` |
| **Socket** | `/var/run/libvirt/libvirt-sock` (system), `/run/user/{uid}/libvirt/libvirt-sock` (session) |
| **Lib C** | `libvirt` (binding Python optionnel) |
| **Modes** | system (root) ou session (utilisateur) |

**Variantes de version / plateforme :**

| Famille OS | Variante | Notes |
|------------|----------|-------|
| Debian/Ubuntu | `libvirt-daemon-system` + `libvirt-clients` + `virtinst` | Standard |
| Debian (ancien) | `libvirt-bin` | Avant Debian Buster |
| RHEL/CentOS 8+ | `libvirt` module + `virt-install` | Stream AppStream |
| RHEL/CentOS 7 | `libvirt` + `python-libvirt` | Anciens bindings |
| Alpine | `libvirt-daemon` + `libvirt-client` | Pas de `virtinst` natif |
| Arch Linux | `libvirt` + `virt-install` | Paquets séparés |

**Services WindFlow applicables :** `VMService` (principal), `SnapshotService`, `ConsoleService` (VNC/SPICE), `DiskService`, `ImageService` (qcow2/ISO)

---

### 2.3 VirtualBox

**Groupe :** VMs — Hyperviseurs
**Détection actuelle :** `target_scanner_service._detect_cli_tools` avec `vboxmanage --version`

| Aspect | Détail |
|--------|--------|
| **Commande de détection** | `vboxmanage --version` |
| **Socket** | Aucun (API propriétaire via `vboxmanage` CLI) |
| **Driver Vagrant** | `virtualbox` (driver natif) |

**Variantes de version / plateforme :**

| Famille OS | Variante | Notes |
|------------|----------|-------|
| Debian/Ubuntu | Dépôt Oracle ou `virtualbox` (partner) | Nécessite DKMS ou modules précompilés |
| RHEL/Fedora | Dépôt Oracle RPM | Nécessite kernel-devel |
| Alpine | **Non supporté** | Pas de paquet VirtualBox |
| Arch Linux | `virtualbox-host-modules-arch` + `virtualbox` | AUR si hors noyau standard |

**Limitation :** Pas de socket — toutes les opérations passent par CLI.
**Services WindFlow applicables :** `VMService` (réduit, pas de live migration)

---

### 2.4 Vagrant

**Groupe :** VMs — Provisioning
**Détection actuelle :** `target_scanner_service._detect_cli_tools` avec `vagrant --version`

| Aspect | Détail |
|--------|--------|
| **Commande de détection** | `vagrant --version` |
| **Socket** | Aucun |
| **Rôle** | Provisioning déclaratif (Vagrantfile), pas de gestion au runtime |

**Variantes de version / plateforme :**

| Famille OS | Variante | Notes |
|------------|----------|-------|
| Debian/Ubuntu | Binaire HashiCorp (`.deb`) | Pas de paquet natif |
| RHEL/Fedora | Binaire HashiCorp (`.rpm`) | — |
| Alpine | Binaire (non officiel) | Compatibility limitée musl vs glibc |
| Arch Linux | AUR `vagrant` | Paquet communautaire |

**Rôle WindFlow :** Utilisé uniquement pour le provisioning initial. Les VMs créées par Vagrant
sont ensuite gérées via l'hyperviseur sous-jacent (VirtualBox, Libvirt).

**Services WindFlow applicables :** `ProvisioningService` (Vagrantfile → VM), pas de gestion runtime.

---

### 2.5 LXC

**Groupe :** VMs — Containers Système
**Détection actuelle :** `target_scanner_service._detect_lxc`

| Aspect | Détail |
|--------|--------|
| **Commande de détection** | `lxc-info --version`, `lxc-checkconfig` |
| **Socket** | `/run/lxc.socket` (rare) |
| **Prérequis noyau** | Namespaces, cgroups v1/v2, seccomp — `lxc-checkconfig` vérifie |

**Variantes de version / plateforme :**

| Famille OS | Variante | Notes |
|------------|----------|-------|
| Debian/Ubuntu | `lxc` + `lxc-templates` | Standard |
| RHEL 8+ | **Non supporté** | Red Hat recommande Podman/Toolbx |
| Alpine | `lxc` + `lxc-templates` | Support partiel |
| Arch Linux | `lxc` | Paquet standard |

**Spécificité :** LXC bruts = conteneurs système sans daemon de gestion. Moins de fonctionnalités que LXD/Incus.
**Services WindFlow applicables :** `SystemContainerService` (CRUD simplifié), `SnapshotService` (via `lxc-snapshot`)

---

### 2.6 LXD

**Groupe :** VMs — Containers Système
**Détection actuelle :** `target_scanner_service._detect_lxd`

| Aspect | Détail |
|--------|--------|
| **Commande de détection** | `lxd --version`, `lxc version` |
| **Socket** | `/var/lib/lxd/unix.socket` ou `/var/snap/lxd/common/lxd/unix.socket` |
| **Installation** | Snap (principale) ou paquet natif (rares distributions) |
| **API** | REST via socket Unix (clé d'authentification client) |

**Variantes de version / plateforme :**

| Famille OS | Variante | Notes |
|------------|----------|-------|
| **Toutes** | **Snap** (recommandé) | `snap install lxd` — méthode universelle |
| Debian testing | `lxd` paquet natif | Experimental |
| Alpine | **Non supporté** | Pas de snap, pas de paquet natif |
| Arch Linux | AUR `lxd` | Paquet communautaire |

**Note importante :** LXD a été racheté par Canonical. Le fork communautaire est **Incus** (section suivante).
Les deux outils sont quasi-identiques en API mais divergent progressivement.

**Services WindFlow applicables :** `SystemContainerService`, `SnapshotService`, `ConsoleService` (via `lxc exec`)

---

### 2.7 Incus

**Groupe :** VMs — Containers Système
**Détection actuelle :** `target_scanner_service._detect_incus`

| Aspect | Détail |
|--------|--------|
| **Commande de détection** | `incus version` |
| **Socket** | `/var/lib/incus/unix.socket` ou `/var/snap/incus/common/incus/unix.socket` |
| **Installation** | Snap ou paquet natif |
| **API** | REST via socket Unix (quasi-identique LXD) |

**Variantes de version / plateforme :**

| Famille OS | Variante | Notes |
|------------|----------|-------|
| **Toutes** | **Snap** | `snap install incus` |
| Debian/Ubuntu | Paquet natif (récent) | Disponible depuis les dépôts |
| Alpine | Paquet natif `incus` | Support en cours d'ajout |
| Arch Linux | AUR `incus` | Paquet communautaire |

**Mutualisation avec LXD :** Les API REST LXD et Incus étant quasi-identiques, le même
client peut servir pour les deux avec un adapter. Voir section 4.3.

**Services WindFlow applicables :** Identiques à LXD.

---

### 2.8 Docker

**Groupe :** Containers — Moteurs
**Détection actuelle :** `target_scanner_service._detect_docker` + `socket_clients.DockerSocketClient`

| Aspect | Détail |
|--------|--------|
| **Commande de détection** | `docker --version`, `docker info --format '{{json .}}'` |
| **Socket** | `/var/run/docker.sock` (system), `/run/user/{uid}/docker.sock` (rootless) |
| **API** | REST via socket Unix (versionnée, rétrocompatible) |
| **Modes** | System (root) ou rootless (utilisateur) |

**Variantes de version / plateforme :**

| Famille OS | Variante | Notes |
|------------|----------|-------|
| Debian/Ubuntu | Dépôt officiel Docker (`.deb`) | Recommandé (version récente) |
| Debian/Ubuntu | `docker.io` (dépôt distribution) | Version plus ancienne |
| RHEL/CentOS 7 | `docker` (dépôt Docker) | CentOS 7 uniquement |
| RHEL 8/9 | **Non officiel** → Podman recommandé | Installation possible mais déconseillée |
| Fedora | `moby-engine` ou dépôt Docker | Alternatives |
| Alpine | `docker` + `docker-cli` | Paquets community |
| Arch Linux | `docker` | Paquet standard |

**Spécificité Docker Compose :** Plugin intégré (`docker compose`) ou standalone (`docker-compose`).
La détection distingue les deux.

**Services WindFlow applicables :** `ContainerEngineService`, `ComposeService`, `ImageService` (OCI), `VolumeService`, `NetworkService`, `SwarmService`

---

### 2.9 Podman

**Groupe :** Containers — Moteurs
**Détection actuelle :** `target_scanner_service._detect_podman`

| Aspect | Détail |
|--------|--------|
| **Commande de détection** | `podman --version`, `podman info --format json` |
| **Socket** | `/run/podman/podman.sock` (system), `/run/user/{uid}/podman/podman.sock` (rootless) |
| **API** | REST compatible Docker (socket) |
| **Mode par défaut** | Rootless — pas de daemon |

**Variantes de version / plateforme :**

| Famille OS | Variante | Notes |
|------------|----------|-------|
| RHEL 8/9 | `podman` (natif, recommandé) | Outil officiel Red Hat |
| Fedora | `podman` | Version cutting-edge |
| Debian/Ubuntu | Dépôt Kubic (OBS) | Paquet officiel Podman |
| Debian/Ubuntu | `podman` (dépôt distribution) | Version variable |
| Alpine | `podman` | Paquet community |
| Arch Linux | `podman` | Paquet standard |

**Compatibilité Docker :** L'API REST Podman est volontairement compatible avec l'API Docker.
Cela permet une mutualisation majeure du code (voir section 4.1).

**Services WindFlow applicables :** Identiques à Docker via `ContainerEngineService` (adapter).

---

### 2.10 Containerd

**Groupe :** Containers — Runtimes bas niveau
**Détection actuelle :** `target_scanner_service._detect_containerd`

| Aspect | Détail |
|--------|--------|
| **Commande de détection** | `containerd --version`, `ctr version` |
| **Socket** | `/run/containerd/containerd.sock`, `/run/k3s/containerd/containerd.sock` |
| **API** | gRPC via socket Unix |

**Variantes :** Souvent installé comme dépendance de Docker ou K3s. Peut aussi être standalone.
**Services WindFlow applicables :** Pas de service direct — utilisé via Docker ou K3s.

---

### 2.11 Runc / Crun

**Groupe :** Containers — Runtimes bas niveau
**Détection actuelle :** `target_scanner_service._detect_oci_tools`

| Aspect | Détail |
|--------|--------|
| **Commandes** | `runc --version`, `crun --version` |
| **Socket** | Aucun — invoqués par le runtime parent (containerd) |

**Rôle :** Exécution de conteneurs conformes OCI. Pas de gestion directe dans WindFlow.
**Services WindFlow applicables :** Aucun — information de détection uniquement.

---

### 2.12 Buildah / Skopeo

**Groupe :** Containers — Outils OCI
**Détection actuelle :** `target_scanner_service._detect_oci_tools`

| Outil | Rôle | Interface |
|-------|------|-----------|
| Buildah | Build d'images sans daemon | CLI uniquement |
| Skopeo | Copie/inspection d'images entre registries | CLI uniquement |

**Services WindFlow applicables :** `ImageService` (build et transport comme alternatives au Docker CLI).

---

### 2.13 Docker Compose / Podman Compose

**Groupe :** Containers — Compose
**Détection actuelle :** `target_scanner_service._detect_docker_compose`, `_detect_oci_tools` (podman-compose)

| Outil | Variante | Notes |
|-------|----------|-------|
| Docker Compose v2 | `docker compose version` | Plugin Docker intégré |
| Docker Compose v1 | `docker-compose --version` | Binaire standalone Python (déprécié) |
| Podman Compose | `podman-compose --version` | Wrapper Python autour de Podman |

**Services WindFlow applicables :** `ComposeService` (unifié pour les deux moteurs).

---

### 2.14 Kubernetes (K8s via kubeadm)

**Groupe :** Orchestration — Kubernetes
**Détection actuelle :** `target_scanner_service._detect_kubernetes`

| Aspect | Détail |
|--------|--------|
| **Commande de détection** | `kubectl version --client -o json`, `kubeadm version -o json` |
| **API** | API server Kubernetes (HTTP/S via kubeconfig) |
| **Auth** | kubeconfig (certificats, tokens, oidc) |

**Variantes de version / plateforme :**

| Famille OS | Variante | Notes |
|------------|----------|-------|
| Debian/Ubuntu | `kubeadm`, `kubelet`, `kubectl` (dépôt Google/Kubernetes) | Installation standard |
| RHEL/CentOS | Idem + SELinux config | Configurations spécifiques |
| Alpine | Paquets community | Pas de support officiel upstream |
| Arch Linux | AUR `kubeadm`, `kubectl` | Paquets communautaires |

**Services WindFlow applicables :** `OrchestratorService`, `HelmService`, `NamespaceService`

---

### 2.15 K3s

**Groupe :** Orchestration — Kubernetes
**Détection actuelle :** `target_scanner_service._detect_kubernetes` avec `k3s --version`

| Aspect | Détail |
|--------|--------|
| **Commande de détection** | `k3s --version` |
| **Socket containerd** | `/run/k3s/containerd/containerd.sock` |
| **API** | Kubeconfig généré à l'installation (`/etc/rancher/k3s/k3s.yaml`) |
| **Installation** | Script officiel unique (`install.sh`) |

**Variantes de version / plateforme :**

| Famille OS | Variante | Notes |
|------------|----------|-------|
| **Toutes (glibc)** | Script officiel `curl -sfL https://get.k3s.io \| sh -` | Méthode universelle |
| Alpine (musl) | Binaire spécifique ou `apk add k3s` | Compatibility partielle |
| RHEL/Fedora | RPM officiel ou script | — |

**Spécificité :** K3s embarque son propre containerd. Pas besoin d'installation séparée.
**Services WindFlow applicables :** `OrchestratorService` (même interface que K8s standard).

---

### 2.16 MicroK8s

**Groupe :** Orchestration — Kubernetes
**Détection actuelle :** `target_scanner_service._detect_kubernetes` avec `microk8s.kubectl version`

| Aspect | Détail |
|--------|--------|
| **Commande de détection** | `microk8s.kubectl version --output=json` |
| **Installation** | Snap uniquement (`snap install microk8s --classic`) |
| **API** | Via `microk8s.kubectl` ou kubeconfig exporté |

**Limitation :** Snap uniquement — pas disponible sur Alpine ou systèmes sans snapd.
**Services WindFlow applicables :** `OrchestratorService` (même interface).

---

### 2.17 Helm

**Groupe :** Orchestration — Outils K8s
**Détection actuelle :** `target_scanner_service._detect_kubernetes` avec `helm version --short`

| Aspect | Détail |
|--------|--------|
| **Commande de détection** | `helm version --short` |
| **Installation** | Binaire depuis GitHub releases ou gestionnaire de paquets |

**Services WindFlow applicables :** `HelmService` (install, upgrade, rollback, list releases).

---

## 3. Architecture d'installation distante

### 3.1 Vue d'ensemble

WindFlow doit pouvoir installer les outils manquants sur les machines cibles via la connexion
SSH (ou locale). L'installation est :

- **Idempotente** — réexécuter ne casse rien
- **Conditionnelle** — ne réinstalle pas si déjà présent à la bonne version
- **Versionnée** — possibilité de cibler une version spécifique
- **Sécurisée** — exécution avec privilèges minimaux, validation post-install

### 3.2 Détection de la plateforme cible

La détection du type de Linux est déjà partiellement implémentée dans
`target_scanner_service._detect_os_release`. Il faut l'enrichir pour obtenir :

```python
class PlatformFamily(str, Enum):
    """Famille de distribution Linux pour l'installation de paquets."""
    DEBIAN = "debian"      # apt — Debian, Ubuntu, Raspbian, Pop!_OS, Linux Mint
    REDHAT = "redhat"      # dnf/yum — RHEL, CentOS, Fedora, Rocky, Alma, Oracle Linux
    ALPINE = "alpine"      # apk — Alpine Linux
    ARCH = "arch"          # pacman — Arch Linux, Manjaro, EndeavourOS
    OPENSUSE = "opensuse"  # zypper — openSUSE, SLES
    GENTOO = "gentoo"      # emerge — Gentoo, Funtoo
    UNKNOWN = "unknown"
```

**Logique de détection :**

```
/etc/os-release → ID + ID_LIKE
├── ID=debian, ubuntu, raspbian, pop, linuxmint → DEBIAN
├── ID=rhel, centos, fedora, rocky, almalinux, ol → REDHAT
├── ID=alpine → ALPINE
├── ID=arch, manjaro, endeavouros → ARCH
├── ID=opensuse*, sles → OPENSUSE
├── ID=gentoo, funtoo → GENTOO
└── sinon → vérifier ID_LIKE, puis UNKNOWN
```

**Variantes de version :** Certaines familles changent de gestionnaire de paquets selon la version :
- RHEL 7 → `yum`, RHEL 8+ → `dnf`
- Debian ancien → pas de kernel en mémoire, versions récentes OK

### 3.3 Architecture des installateurs

```
backend/app/services/installers/
├── __init__.py
├── base.py                         # ToolInstaller ABC + InstallResult
├── platform_detector.py            # Détection plateforme enrichie
├── platform/
│   ├── __init__.py
│   ├── base_platform.py            # PlatformInstaller ABC
│   ├── debian.py                   # AptInstaller
│   ├── redhat.py                   # DnfInstaller / YumInstaller
│   ├── alpine.py                   # ApkInstaller
│   ├── arch.py                     # PacmanInstaller
│   └── opensuse.py                 # ZypperInstaller
├── recipes/
│   ├── __init__.py
│   ├── qemu_kvm.py                 # Installateur QEMU/KVM
│   ├── libvirt.py                  # Installateur Libvirt + Virsh
│   ├── virtualbox.py               # Installateur VirtualBox
│   ├── vagrant.py                  # Installateur Vagrant
│   ├── lxc.py                      # Installateur LXC
│   ├── lxd.py                      # Installateur LXD (snap)
│   ├── incus.py                    # Installateur Incus (snap)
│   ├── docker.py                   # Installateur Docker Engine
│   ├── podman.py                   # Installateur Podman
│   ├── containerd.py               # Installateur Containerd
│   ├── k3s.py                      # Installateur K3s
│   ├── microk8s.py                 # Installateur MicroK8s (snap)
│   ├── kubectl.py                  # Installateur kubectl
│   ├── helm.py                     # Installateur Helm
│   └── docker_compose.py           # Installateur Docker Compose (plugin v2)
└── installer_orchestrator.py       # Orchestration multi-étapes
```

### 3.4 Interface de base

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class InstallStatus(str, Enum):
    """Résultat d'une installation."""
    SUCCESS = "success"
    ALREADY_INSTALLED = "already_installed"
    VERSION_MISMATCH = "version_mismatch"
    FAILED = "failed"
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    REQUIRES_REBOOT = "requires_reboot"


@dataclass
class InstallResult:
    """Résultat d'une opération d'installation."""
    status: InstallStatus
    tool: str
    version_installed: str | None = None
    message: str | None = None
    requires_reboot: bool = False
    requires_relogin: bool = False
    steps_executed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class PlatformInfo:
    """Informations plateforme pour l'installation."""
    family: PlatformFamily
    distribution: str          # ex: "ubuntu", "debian", "rocky"
    version: str | None        # ex: "22.04", "12", "9.2"
    version_major: int | None  # ex: 22, 12, 9
    architecture: str          # ex: "x86_64", "aarch64"
    init_system: str           # "systemd", "openrc", "sysvinit"


class PlatformInstaller(ABC):
    """Interface abstraite pour les opérations de gestion de paquets."""

    @abstractmethod
    async def update_package_index(self, executor: CommandExecutor) -> CommandResult:
        """Met à jour l'index des paquets (apt update, dnf check-update, etc.)."""
        ...

    @abstractmethod
    async def install_packages(
        self, executor: CommandExecutor, packages: list[str], **kwargs: Any
    ) -> CommandResult:
        """Installe une liste de paquets."""
        ...

    @abstractmethod
    async def is_package_installed(
        self, executor: CommandExecutor, package: str
    ) -> bool:
        """Vérifie si un paquet est installé."""
        ...

    @abstractmethod
    async def add_repository(
        self, executor: CommandExecutor, repo_url: str, **kwargs: Any
    ) -> CommandResult:
        """Ajoute un dépôt tiers."""
        ...

    @abstractmethod
    async def install_from_url(
        self, executor: CommandExecutor, url: str, dest: str, **kwargs: Any
    ) -> CommandResult:
        """Télécharge et installe un binaire depuis une URL."""
        ...


class ToolInstaller(ABC):
    """Interface abstraite pour l'installation d'un outil spécifique.

    Chaque outil (Docker, Libvirt, etc.) implémente cette interface
    pour définir sa logique d'installation multi-plateforme.
    """

    tool_name: str
    supported_platforms: list[PlatformFamily]

    @abstractmethod
    async def detect_current(
        self, executor: CommandExecutor
    ) -> tuple[bool, str | None]:
        """Détecte si l'outil est déjà installé et sa version.

        Returns:
            Tuple (installed, version).
        """
        ...

    @abstractmethod
    async def install(
        self,
        executor: CommandExecutor,
        platform: PlatformInfo,
        version: str | None = None,
    ) -> InstallResult:
        """Installe l'outil sur la plateforme cible.

        Args:
            executor: Exécuteur de commandes (SSH ou local).
            platform: Informations plateforme détectées.
            version: Version cible (None = dernière disponible).

        Returns:
            Résultat de l'installation.
        """
        ...

    @abstractmethod
    async def post_install_setup(
        self, executor: CommandExecutor, platform: PlatformInfo
    ) -> InstallResult:
        """Configuration post-installation (service, permissions, etc.)."""
        ...

    @abstractmethod
    async def verify_installation(
        self, executor: CommandExecutor
    ) -> bool:
        """Vérifie que l'outil est fonctionnel après installation."""
        ...
```

### 3.5 Flux d'installation

```
1. Détecter la plateforme cible
   └── PlatformDetector.detect(executor) → PlatformInfo

2. Vérifier si l'outil est déjà installé
   └── ToolInstaller.detect_current(executor) → (installed, version)

3. Si déjà installé à la bonne version → ALREADY_INSTALLED
   Si version différente → proposer upgrade (avec confirmation utilisateur)

4. Sélectionner le PlatformInstaller approprié
   └── factory pattern : get_platform_installer(family)

5. Exécuter l'installation
   ├── pré-étapes (ajout dépôt, dépendances)
   ├── installation paquets ou binaire
   └── post-installation (démarrage service, permissions)

6. Vérifier l'installation
   └── ToolInstaller.verify_installation(executor)

7. Optionnel : re-scan de la cible pour mettre à jour les capacités
```

### 3.6 Gestion des variantes de version

Chaque installateur de recette (`recipes/`) doit gérer les différences entre versions de plateforme :

```python
class DockerInstaller(ToolInstaller):
    """Exemple : installation Docker avec gestion des variantes."""

    tool_name = "docker"
    supported_platforms = [PlatformFamily.DEBIAN, PlatformFamily.REDHAT, ...]

    async def install(self, executor, platform, version=None):
        # Adapter la commande selon la plateforme ET sa version
        if platform.family == PlatformFamily.DEBIAN:
            # Debian ancien (< 11) : pas de plugin compose natif
            # Ubuntu 18.04 : dépôt spécifique
            # Ubuntu 20.04+ / Debian 11+ : procédure standard
            ...
        elif platform.family == PlatformFamily.REDHAT:
            # RHEL 7 : docker via dépôt Docker (yum)
            # RHEL 8/9 : docker non officiel → avertissement
            # Fedora : moby-engine ou dépôt Docker
            ...
```

---

## 4. Services mutualisés — Interfaces abstraites

L'architecture repose sur **4 familles de services** avec interfaces abstraites,
chaque système implémentant l'interface correspondante.

### 4.1 `ContainerEngineService` — Moteurs de conteneurs

**Systèmes implémentant cette interface :** Docker, Podman

```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator


class ContainerEngineService(ABC):
    """Interface commune pour les moteurs de conteneurs (Docker, Podman).

    Both Docker and Podman expose a compatible REST API via Unix socket.
    This interface abstracts over both, with Podman implementing the same
    endpoints as Docker for compatibility.
    """

    # ─── Containers ────────────────────────────────────

    @abstractmethod
    async def list_containers(
        self, all: bool = False, filters: dict | None = None
    ) -> list[ContainerInfo]:
        """Liste les conteneurs.

        Args:
            all: Inclure les conteneurs arrêtés.
            filters: Filtres (status, label, name, etc.).
        """
        ...

    @abstractmethod
    async def get_container(self, container_id: str) -> ContainerInfo:
        """Récupère les détails d'un conteneur."""
        ...

    @abstractmethod
    async def create_container(self, config: ContainerCreateConfig) -> ContainerInfo:
        """Crée un conteneur à partir d'une configuration."""
        ...

    @abstractmethod
    async def start_container(self, container_id: str) -> None:
        """Démarre un conteneur."""
        ...

    @abstractmethod
    async def stop_container(self, container_id: str, timeout: int = 10) -> None:
        """Arrête un conteneur (SIGTERM puis SIGKILL après timeout)."""
        ...

    @abstractmethod
    async def restart_container(self, container_id: str, timeout: int = 10) -> None:
        """Redémarre un conteneur."""
        ...

    @abstractmethod
    async def pause_container(self, container_id: str) -> None:
        """Met en pause un conteneur (freeze processus)."""
        ...

    @abstractmethod
    async def unpause_container(self, container_id: str) -> None:
        """Reprend un conteneur en pause."""
        ...

    @abstractmethod
    async def remove_container(self, container_id: str, force: bool = False, volumes: bool = False) -> None:
        """Supprime un conteneur."""
        ...

    @abstractmethod
    async def rename_container(self, container_id: str, new_name: str) -> None:
        """Renomme un conteneur."""
        ...

    @abstractmethod
    async def get_container_logs(
        self, container_id: str, tail: int | None = None, follow: bool = False, timestamps: bool = False
    ) -> str | AsyncGenerator[str, None]:
        """Récupère les logs d'un conteneur."""
        ...

    @abstractmethod
    async def exec_in_container(
        self, container_id: str, command: list[str], tty: bool = False, stdin: bool = False
    ) -> ExecResult:
        """Exécute une commande dans un conteneur en cours d'exécution."""
        ...

    @abstractmethod
    async def get_container_stats(self, container_id: str, stream: bool = False) -> ContainerStats | AsyncGenerator[ContainerStats, None]:
        """Récupère les statistiques d'un conteneur (CPU, RAM, réseau, IO)."""
        ...

    @abstractmethod
    async def inspect_container(self, container_id: str) -> dict:
        """Inspection complète d'un conteneur (config bas niveau)."""
        ...

    # ─── Images ────────────────────────────────────────

    @abstractmethod
    async def list_images(self, filters: dict | None = None) -> list[ImageInfo]:
        """Liste les images disponibles localement."""
        ...

    @abstractmethod
    async def pull_image(self, image: str, tag: str = "latest", platform: str | None = None) -> ImageInfo:
        """Tire une image depuis un registre."""
        ...

    @abstractmethod
    async def remove_image(self, image_id: str, force: bool = False) -> list[str]:
        """Supprime une image."""
        ...

    @abstractmethod
    async def image_exists(self, image: str, tag: str = "latest") -> bool:
        """Vérifie si une image existe localement."""
        ...

    # ─── Volumes ───────────────────────────────────────

    @abstractmethod
    async def list_volumes(self, filters: dict | None = None) -> list[VolumeInfo]:
        """Liste les volumes."""
        ...

    @abstractmethod
    async def create_volume(self, name: str, driver: str = "local", labels: dict | None = None) -> VolumeInfo:
        """Crée un volume."""
        ...

    @abstractmethod
    async def remove_volume(self, name: str, force: bool = False) -> None:
        """Supprime un volume."""
        ...

    @abstractmethod
    async def inspect_volume(self, name: str) -> VolumeInfo:
        """Inspection d'un volume."""
        ...

    # ─── Networks ──────────────────────────────────────

    @abstractmethod
    async def list_networks(self, filters: dict | None = None) -> list[NetworkInfo]:
        """Liste les réseaux."""
        ...

    @abstractmethod
    async def create_network(self, config: NetworkCreateConfig) -> NetworkInfo:
        """Crée un réseau."""
        ...

    @abstractmethod
    async def remove_network(self, network_id: str) -> None:
        """Supprime un réseau."""
        ...

    # ─── Info système ──────────────────────────────────

    @abstractmethod
    async def engine_info(self) -> EngineInfo:
        """Informations sur le moteur (version, storage driver, OS, etc.)."""
        ...

    @abstractmethod
    async def disk_usage(self) -> DiskUsageInfo:
        """Utilisation disque (images, conteneurs, volumes, build cache)."""
        ...

    @abstractmethod
    async def prune_unused(self, containers: bool = False, images: bool = False, volumes: bool = False) -> PruneResult:
        """Nettoyage des ressources non utilisées."""
        ...
```

**Mutualisation Docker/Podman :**

```
ContainerEngineService (ABC)
├── DockerEngineService      # Implémente via socket Docker (docker lib Python ou HTTP)
└── PodmanEngineService      # Implémente via socket Podman (API compatible Docker)
    # → Peut hériter de DockerEngineService avec override mineur
    #   car l'API REST Podman est volontairement compatible Docker
```

### 4.2 `ComposeService` — Compositions multi-conteneurs

**Systèmes implémentant cette interface :** Docker Compose, Podman Compose

```python
class ComposeService(ABC):
    """Interface commune pour les compositions de conteneurs.

    Abstrait les différences entre Docker Compose (plugin v1/v2)
    et Podman Compose.
    """

    @abstractmethod
    async def deploy(
        self,
        project_name: str,
        compose_content: str,      # YAML du compose file
        compose_path: str | None = None,  # Chemin sur le target
        env_vars: dict[str, str] | None = None,
    ) -> ComposeDeployResult:
        """Déploie une composition (up -d).

        Args:
            project_name: Nom du projet Compose.
            compose_content: Contenu YAML du fichier compose.
            compose_path: Chemin où écrire le fichier sur le target (si None, temp).
            env_vars: Variables d'environnement supplémentaires.
        """
        ...

    @abstractmethod
    async def tear_down(
        self, project_name: str, remove_volumes: bool = False, remove_images: bool = False
    ) -> ComposeDownResult:
        """Arrête et supprime une composition (down)."""
        ...

    @abstractmethod
    async def list_projects(self) -> list[ComposeProject]:
        """Liste les projets Compose en cours ou arrêtés."""
        ...

    @abstractmethod
    async def get_project(self, project_name: str) -> ComposeProject:
        """Récupère les détails d'un projet (services, conteneurs, état)."""
        ...

    @abstractmethod
    async def get_project_logs(
        self, project_name: str, service: str | None = None, tail: int | None = None
    ) -> str | AsyncGenerator[str, None]:
        """Récupère les logs d'un projet ou d'un service spécifique."""
        ...

    @abstractmethod
    async def restart_service(self, project_name: str, service: str) -> None:
        """Redémarre un service dans une composition."""
        ...

    @abstractmethod
    async def scale_service(self, project_name: str, service: str, replicas: int) -> None:
        """Scale un service à un nombre donné de réplicas."""
        ...

    @abstractmethod
    async def pull_images(self, project_name: str) -> list[PullResult]:
        """Tire les dernières images d'une composition."""
        ...

    @abstractmethod
    async def validate_compose(self, compose_content: str) -> ComposeValidationResult:
        """Valide un fichier compose sans le déployer."""
        ...

    @abstractmethod
    async def convert_compose(self, compose_content: str) -> str:
        """Convertit un compose en config finale résolue (docker compose config)."""
        ...
```

**Mutualisation :**

```
ComposeService (ABC)
├── DockerComposeService    # docker compose (plugin v2) ou docker-compose (v1 standalone)
└── PodmanComposeService    # podman-compose (wrapper Python)
```

### 4.3 `VMService` — Machines virtuelles

**Systèmes implémentant cette interface :** Libvirt/KVM, LXD, Incus, VirtualBox

```python
class VMService(ABC):
    """Interface commune pour la gestion de machines virtuelles.

    Unified across hypervisors: Libvirt/KVM, LXD, Incus, VirtualBox.
    Each implementation adapts the common interface to the underlying API.
    """

    # ─── CRUD VMs ──────────────────────────────────────

    @abstractmethod
    async def list_vms(self, all: bool = False) -> list[VMInfo]:
        """Liste les VMs.

        Args:
            all: Inclure les VMs arrêtées.
        """
        ...

    @abstractmethod
    async def get_vm(self, vm_id: str) -> VMInfo:
        """Récupère les détails d'une VM."""
        ...

    @abstractmethod
    async def create_vm(self, config: VMCreateConfig) -> VMInfo:
        """Crée une VM à partir d'une configuration.

        Le format de config varie selon l'hyperviseur :
        - Libvirt : XML definition ou cloud-init
        - LXD/Incus : dictionnaire de configuration
        - VirtualBox : paramètres vboxmanage
        """
        ...

    @abstractmethod
    async def delete_vm(self, vm_id: str, remove_disks: bool = True) -> None:
        """Supprime une VM et optionnellement ses disques."""
        ...

    @abstractmethod
    async def clone_vm(self, vm_id: str, new_name: str, linked: bool = False) -> VMInfo:
        """Clone une VM (clone complet ou lié)."""
        ...

    # ─── États ─────────────────────────────────────────

    @abstractmethod
    async def start_vm(self, vm_id: str) -> None:
        """Démarre une VM."""
        ...

    @abstractmethod
    async def stop_vm(self, vm_id: str, force: bool = False) -> None:
        """Arrête une VM (ACPI shutdown ou force stop)."""
        ...

    @abstractmethod
    async def reboot_vm(self, vm_id: str, force: bool = False) -> None:
        """Redémarre une VM."""
        ...

    @abstractmethod
    async def pause_vm(self, vm_id: str) -> None:
        """Met en pause une VM (freeze mémoire)."""
        ...

    @abstractmethod
    async def resume_vm(self, vm_id: str) -> None:
        """Reprend une VM en pause."""
        ...

    @abstractmethod
    async def suspend_vm(self, vm_id: str) -> None:
        """Suspend une VM (hibernation — sauvegarde RAM sur disque)."""
        ...

    # ─── Configuration ─────────────────────────────────

    @abstractmethod
    async def get_vm_config(self, vm_id: str) -> VMConfig:
        """Récupère la configuration d'une VM (CPU, RAM, disques, réseau)."""
        ...

    @abstractmethod
    async def update_vm_config(self, vm_id: str, config: VMConfigUpdate) -> VMConfig:
        """Modifie la configuration d'une VM (nécessite arrêt pour certains changements).

        Certaines modifications (CPU hotplug, RAM ballooning) peuvent s'appliquer
        à chaud selon l'hyperviseur.
        """
        ...

    # ─── Métriques ─────────────────────────────────────

    @abstractmethod
    async def get_vm_stats(self, vm_id: str) -> VMStats:
        """Statistiques d'exécution (CPU, RAM, disque, réseau)."""
        ...

    # ─── Console ───────────────────────────────────────

    @abstractmethod
    async def get_console_url(self, vm_id: str, console_type: str = "vnc") -> ConsoleInfo:
        """URL d'accès console (VNC, SPICE, ou terminal).

        Retourne les informations de connexion pour le client noVNC
        intégré à l'UI WindFlow.
        """
        ...

    # ─── Snapshots ─────────────────────────────────────

    @abstractmethod
    async def list_snapshots(self, vm_id: str) -> list[SnapshotInfo]:
        """Liste les snapshots d'une VM."""
        ...

    @abstractmethod
    async def create_snapshot(
        self, vm_id: str, name: str, description: str | None = None, live: bool = False
    ) -> SnapshotInfo:
        """Crée un snapshot.

        Args:
            live: Si True, snapshot à chaud (mémoire + disque). Sinon disque seul.
        """
        ...

    @abstractmethod
    async def restore_snapshot(self, vm_id: str, snapshot_name: str) -> None:
        """Restaure une VM depuis un snapshot."""
        ...

    @abstractmethod
    async def delete_snapshot(self, vm_id: str, snapshot_name: str) -> None:
        """Supprime un snapshot."""
        ...

    # ─── Disques ───────────────────────────────────────

    @abstractmethod
    async def list_disks(self, vm_id: str) -> list[DiskInfo]:
        """Liste les disques attachés à une VM."""
        ...

    @abstractmethod
    async def attach_disk(self, vm_id: str, disk_config: DiskAttachConfig) -> DiskInfo:
        """Attache un disque à une VM."""
        ...

    @abstractmethod
    async def detach_disk(self, vm_id: str, disk_id: str) -> None:
        """Détache un disque d'une VM."""
        ...

    @abstractmethod
    async def resize_disk(self, disk_id: str, new_size_gb: int) -> DiskInfo:
        """Redimensionne un disque."""
        ...
```

**Hiérarchie d'implémentation :**

```
VMService (ABC)
├── LibvirtVMService         # Via libvirt Python bindings + virsh CLI
├── LXDVMService             # Via API REST LXD (socket Unix)
├── IncusVMService           # Via API REST Incus (socket Unix)
│   # → Incus et LXD partagent ~95% de l'API.
│   #   Un LXDIncusBaseService peut factoriser la logique commune.
└── VirtualBoxVMService      # Via vboxmanage CLI (pas d'API REST)
```

**Factorisation LXD/Incus :**

```python
class LXDIncusBaseService(VMService):
    """Base commune pour LXD et Incus (API REST quasi-identique).

    Les deux outils partagent la même structure d'API REST via socket Unix.
    Cette classe de base factorise toute la logique commune.
    """

    client: UnixSocketRESTClient  # Client HTTP sur socket Unix

    async def list_vms(self, all: bool = False) -> list[VMInfo]:
        response = await self.client.get("/1.0/instances", params={"recursion": 2})
        return [self._parse_instance(inst) for inst in response.json()["metadata"]]

    async def start_vm(self, vm_id: str) -> None:
        await self.client.put(f"/1.0/instances/{vm_id}/state", json={"action": "start"})
    # ... logique commune

    @abstractmethod
    def _get_socket_path(self) -> str:
        """Chemin du socket — différent entre LXD et Incus."""
        ...


class LXDVMService(LXDIncusBaseService):
    def _get_socket_path(self) -> str:
        return "/var/snap/lxd/common/lxd/unix.socket"


class IncusVMService(LXDIncusBaseService):
    def _get_socket_path(self) -> str:
        return "/var/lib/incus/unix.socket"
```

### 4.4 `SystemContainerService` — Conteneurs système (LXC/LXD/Incus)

**Systèmes implémentant cette interface :** LXC, LXD, Incus

LXD et Incus gèrent à la fois des VMs et des conteneurs système.
Pour les conteneurs (pas VMs), cette interface est dédiée :

```python
class SystemContainerService(ABC):
    """Interface pour les conteneurs système (LXC, LXD, Incus).

    Distinct de ContainerEngineService (Docker/Podman) car :
    - Les conteneurs système partagent le noyau hôte directement
    - Pas de notion d'image OCI (images de distribution)
    - Snapshots natifs (pas de layers)
    - Réseau directement sur l'hôte (bridge, macvlan)
    """

    @abstractmethod
    async def list_containers(self, all: bool = False) -> list[SysContainerInfo]:
        """Liste les conteneurs système."""
        ...

    @abstractmethod
    async def get_container(self, name: str) -> SysContainerInfo:
        """Détails d'un conteneur système."""
        ...

    @abstractmethod
    async def create_container(self, config: SysContainerCreateConfig) -> SysContainerInfo:
        """Crée un conteneur système.

        Args:
            config: Config incluant l'image source (ex: "ubuntu:22.04"),
                    les ressources, le réseau, cloud-init.
        """
        ...

    @abstractmethod
    async def delete_container(self, name: str, force: bool = False) -> None:
        """Supprime un conteneur système."""
        ...

    @abstractmethod
    async def start_container(self, name: str) -> None: ...

    @abstractmethod
    async def stop_container(self, name: str, force: bool = False) -> None: ...

    @abstractmethod
    async def restart_container(self, name: str) -> None: ...

    @abstractmethod
    async def freeze_container(self, name: str) -> None:
        """Gèle un conteneur (équivalent pause)."""
        ...

    @abstractmethod
    async def unfreeze_container(self, name: str) -> None: ...

    @abstractmethod
    async def exec_in_container(self, name: str, command: list[str]) -> ExecResult:
        """Exécute une commande dans le conteneur."""
        ...

    @abstractmethod
    async def get_container_file(self, name: str, path: str) -> bytes:
        """Lit un fichier dans le conteneur."""
        ...

    @abstractmethod
    async def push_container_file(self, name: str, path: str, content: bytes) -> None:
        """Écrit un fichier dans le conteneur."""
        ...

    @abstractmethod
    async def list_snapshots(self, name: str) -> list[SnapshotInfo]: ...

    @abstractmethod
    async def create_snapshot(self, name: str, snapshot_name: str) -> SnapshotInfo: ...

    @abstractmethod
    async def restore_snapshot(self, name: str, snapshot_name: str) -> None: ...

    @abstractmethod
    async def get_container_stats(self, name: str) -> SysContainerStats: ...

    @abstractmethod
    async def migrate_container(self, name: str, target_host: str) -> None:
        """Migration à chaud (LXD/Incus uniquement, pas LXC brut)."""
        ...
```

### 4.5 `OrchestratorService` — Orchestration Kubernetes

**Systèmes implémentant cette interface :** K8s, K3s, MicroK8s

```python
class OrchestratorService(ABC):
    """Interface commune pour l'orchestration Kubernetes.

    K8s standard, K3s et MicroK8s exposent tous la même API Kubernetes.
    Cette interface unifie l'accès.
    """

    # ─── Cluster info ──────────────────────────────────

    @abstractmethod
    async def cluster_info(self) -> ClusterInfo:
        """Informations sur le cluster (version, nodes, capacité)."""
        ...

    @abstractmethod
    async def list_nodes(self) -> list[NodeInfo]:
        """Liste les nodes du cluster."""
        ...

    @abstractmethod
    async def get_node(self, name: str) -> NodeInfo: ...

    # ─── Namespaces ────────────────────────────────────

    @abstractmethod
    async def list_namespaces(self) -> list[NamespaceInfo]: ...

    @abstractmethod
    async def create_namespace(self, name: str, labels: dict | None = None) -> NamespaceInfo: ...

    @abstractmethod
    async def delete_namespace(self, name: str) -> None: ...

    # ─── Workloads ─────────────────────────────────────

    @abstractmethod
    async def list_deployments(self, namespace: str = "default") -> list[DeploymentInfo]: ...

    @abstractmethod
    async def get_deployment(self, name: str, namespace: str = "default") -> DeploymentInfo: ...

    @abstractmethod
    async def create_deployment(self, config: DeploymentCreateConfig) -> DeploymentInfo: ...

    @abstractmethod
    async def delete_deployment(self, name: str, namespace: str = "default") -> None: ...

    @abstractmethod
    async def scale_deployment(self, name: str, namespace: str, replicas: int) -> None: ...

    @abstractmethod
    async def restart_deployment(self, name: str, namespace: str) -> None:
        """Rollout restart d'un deployment."""
        ...

    # ─── Pods ──────────────────────────────────────────

    @abstractmethod
    async def list_pods(self, namespace: str | None = None, labels: dict | None = None) -> list[PodInfo]: ...

    @abstractmethod
    async def get_pod(self, name: str, namespace: str = "default") -> PodInfo: ...

    @abstractmethod
    async def delete_pod(self, name: str, namespace: str = "default") -> None: ...

    @abstractmethod
    async def get_pod_logs(
        self, name: str, namespace: str = "default", container: str | None = None, tail: int | None = None, follow: bool = False
    ) -> str | AsyncGenerator[str, None]: ...

    @abstractmethod
    async def exec_in_pod(
        self, name: str, command: list[str], namespace: str = "default", container: str | None = None, tty: bool = False
    ) -> ExecResult: ...

    # ─── Services & Ingress ────────────────────────────

    @abstractmethod
    async def list_services(self, namespace: str | None = None) -> list[ServiceInfo]: ...

    @abstractmethod
    async def create_service(self, config: ServiceCreateConfig) -> ServiceInfo: ...

    @abstractmethod
    async def delete_service(self, name: str, namespace: str) -> None: ...

    @abstractmethod
    async def list_ingresses(self, namespace: str | None = None) -> list[IngressInfo]: ...

    # ─── ConfigMaps & Secrets ──────────────────────────

    @abstractmethod
    async def list_configmaps(self, namespace: str) -> list[ConfigMapInfo]: ...

    @abstractmethod
    async def create_configmap(self, name: str, namespace: str, data: dict) -> ConfigMapInfo: ...

    @abstractmethod
    async def list_secrets(self, namespace: str) -> list[SecretInfo]: ...

    # ─── Events ────────────────────────────────────────

    @abstractmethod
    async def get_events(self, namespace: str | None = None, limit: int = 50) -> list[EventInfo]: ...

    # ─── Apply/Delete manifest ─────────────────────────

    @abstractmethod
    async def apply_manifest(self, manifest: str | dict, namespace: str = "default") -> ApplyResult:
        """Applique un manifest YAML (kubectl apply)."""
        ...

    @abstractmethod
    async def delete_manifest(self, manifest: str | dict, namespace: str = "default") -> None:
        """Supprime les ressources définies par un manifest."""
        ...
```

**Mutualisation :** Les 3 implémentations utilisent le même client `kubernetes` Python
ou communiquent via l'API Kubernetes HTTP standard. Seule l'authentification diffère :

```
OrchestratorService (ABC)
├── KubernetesService    # kubeconfig standard (/etc/kubernetes/admin.conf)
├── K3sService           # kubeconfig K3s (/etc/rancher/k3s/k3s.yaml)
└── MicroK8sService      # kubeconfig via microk8s.kubectl config view
```

### 4.6 `HelmService` — Gestionnaire de charts

**Systèmes implémentant :** Tout cluster Kubernetes (K8s, K3s, MicroK8s)

```python
class HelmService(ABC):
    """Interface pour la gestion des releases Helm."""

    @abstractmethod
    async def list_releases(self, namespace: str | None = None, all: bool = False) -> list[HelmReleaseInfo]:
        """Liste les releases Helm."""
        ...

    @abstractmethod
    async def install(
        self,
        release_name: str,
        chart: str,
        namespace: str = "default",
        values: dict | None = None,
        repo: str | None = None,
        version: str | None = None,
    ) -> HelmReleaseInfo:
        """Installe un chart Helm."""
        ...

    @abstractmethod
    async def upgrade(
        self,
        release_name: str,
        chart: str | None = None,
        namespace: str = "default",
        values: dict | None = None,
        version: str | None = None,
    ) -> HelmReleaseInfo:
        """Met à jour une release Helm."""
        ...

    @abstractmethod
    async def uninstall(self, release_name: str, namespace: str = "default") -> None:
        """Désinstalle une release Helm."""
        ...

    @abstractmethod
    async def rollback(self, release_name: str, revision: int, namespace: str = "default") -> None:
        """Restaure une release à une révision précédente."""
        ...

    @abstractmethod
    async def get_release_values(self, release_name: str, namespace: str = "default") -> dict:
        """Récupère les values d'une release déployée."""
        ...

    @abstractmethod
    async def get_release_history(self, release_name: str, namespace: str = "default") -> list[HelmRevisionInfo]:
        """Historique des révisions d'une release."""
        ...

    @abstractmethod
    async def list_repos(self) -> list[HelmRepoInfo]:
        """Liste les dépôts Helm configurés."""
        ...

    @abstractmethod
    async def add_repo(self, name: str, url: str) -> None:
        """Ajoute un dépôt Helm."""
        ...

    @abstractmethod
    async def search_charts(self, keyword: str, repo: str | None = None) -> list[ChartSearchResult]:
        """Recherche des charts disponibles."""
        ...
```

**Implémentation unique :** `HelmCLIService` via `helm` CLI (identique pour tous les clusters).

---

## 5. Matrice de mutualisation

### 5.1 Récapitulatif des interfaces par système

| Système | ContainerEngine | Compose | VM | SystemContainer | Orchestrator | Helm |
|---------|:-:|:-:|:-:|:-:|:-:|:-:|
| Docker | ✅ | ✅ (Docker Compose) | — | — | — | — |
| Podman | ✅ | ✅ (Podman Compose) | — | — | — | — |
| Libvirt/KVM | — | — | ✅ | — | — | — |
| VirtualBox | — | — | ✅ (réduit) | — | — | — |
| LXC | — | — | — | ✅ (réduit) | — | — |
| LXD | — | — | ✅ | ✅ | — | — |
| Incus | — | — | ✅ | ✅ | — | — |
| K8s | — | — | — | — | ✅ | ✅ |
| K3s | — | — | — | — | ✅ | ✅ |
| MicroK8s | — | — | — | — | ✅ | ✅ |

### 5.2 Diagramme des dépendances entre services

```
┌─────────────────────────────────────────────────────────────────┐
│                    API REST WINDFLOW                             │
│           (Endpoints unifiés, indépendants du moteur)           │
└─────────────────────┬───────────────────────────────────────────┘
                      │
          ┌───────────┼───────────────────────┐
          │           │                       │
          ▼           ▼                       ▼
┌─────────────┐ ┌──────────┐        ┌──────────────────┐
│  Container  │ │  Compose │        │   Orchestrator   │
│  Engine     │ │  Service │        │   Service        │
│  Service    │ │          │        │                  │
│  (ABC)      │ │  (ABC)   │        │  (ABC)           │
└──┬─────┬───┘ └──┬───┬───┘        └────────┬─────────┘
   │     │        │   │                      │
   ▼     ▼        ▼   ▼                      ▼
Docker  Podman  D.   Podman            K8s / K3s / µK8s
                Comp. Compose                  │
                                               ▼
                                        ┌──────────────┐
┌──────────┐ ┌──────────┐               │ Helm Service  │
│  VM      │ │  System  │               │              │
│  Service │ │Container │               │ helm (CLI)   │
│  (ABC)   │ │ Service  │               └──────────────┘
└──┬───┬───┘ │  (ABC)   │
   │   │     └──┬───┬───┘
   │   │        │   │
   ▼   │        ▼   ▼
Libvirt│       LXD  Incus  ← (base LXDIncus commune)
KVM    │
       ▼
   VirtualBox
   (réduit)
   LXD ──────► aussi SystemContainer
   Incus ────► aussi SystemContainer
```

### 5.3 Services transversaux (shared across all engines)

En plus des services spécifiques par type de système, ces services sont transversaux :

| Service | Description | Utilisé par |
|---------|-------------|-------------|
| `ImageService` | Gestion images OCI (pull, push, list, remove) | Docker, Podman |
| `OSImageService` | Gestion images VM (qcow2, ISO, cloud-init) | Libvirt, VirtualBox |
| `SnapshotService` | Snapshots VM (inclus dans VMService) | Tous VMService |
| `ConsoleService` | Accès console (VNC/SPICE/Terminal) | Libvirt, LXD, Incus |
| `TerminalService` | Terminal interactif via WebSocket | Docker, Podman, K8s, LXD, Incus |
| `MonitoringService` | Collecte métriques (CPU, RAM, IO, net) | Tous |
| `VolumeService` | Gestion volumes / disques | Docker, Podman, Libvirt |
| `NetworkService` | Gestion réseaux (bridge, overlay, VLAN) | Docker, Podman, Libvirt |

---

## 6. Impacts sur le code existant

### 6.1 Enums — Restructuration hiérarchique

**Fichier :** `backend/app/enums/target.py`

L'enum `CapabilityType` actuel est plat. Il faut ajouter la hiérarchie :

- Ajouter `VirtualizationGroup` et `SystemCategory` (nouveaux enums)
- Ajouter `SystemTool` comme enum détaillé (remplace une partie de `CapabilityType`)
- Garder `CapabilityType` comme compatibilité (mapper vers `SystemTool`)

### 6.2 Scanner — Modularisation par groupe

**Fichier :** `backend/app/services/target_scanner_service.py`

Le scanner actuel (~700 lignes) fait tout dans une seule classe. Refactoriser en :

```
target_scanner_service.py          # Orchestrateur principal (existe)
├── scanners/
│   ├── vm_scanner.py              # _detect_virtualization → VMScanner
│   ├── container_scanner.py       # _detect_docker + _detect_podman → ContainerScanner
│   ├── kubernetes_scanner.py      # _detect_kubernetes → KubernetesScanner
│   └── oci_scanner.py             # _detect_oci_tools → OCIScanner
```

Chaque scanner retourne un `dict[str, ToolInfo]` enrichi avec le groupe et la catégorie.

### 6.3 Schemas — Enrichissement des résultats de scan

**Fichier :** `backend/app/schemas/target_scan.py`

- Ajouter `VirtualizationGroup`, `SystemCategory` aux résultats `ToolInfo`
- Ajouter un champ `install_suggestions: list[InstallSuggestion]` au `ScanResult`
  pour suggérer les installations possibles

### 6.4 Nouveaux fichiers à créer

| Fichier | Rôle |
|---------|------|
| `backend/app/enums/virtualization.py` | Enums VirtualizationGroup, SystemCategory, SystemTool |
| `backend/app/services/installers/` | Module complet d'installation (section 3) |
| `backend/app/services/engines/container_engine.py` | ContainerEngineService ABC |
| `backend/app/services/engines/docker_engine.py` | Implémentation Docker |
| `backend/app/services/engines/podman_engine.py` | Implémentation Podman |
| `backend/app/services/engines/compose.py` | ComposeService ABC + implémentations |
| `backend/app/services/engines/vm_service.py` | VMService ABC |
| `backend/app/services/engines/libvirt_vm.py` | Implémentation Libvirt |
| `backend/app/services/engines/lxd_incus_base.py` | Base commune LXD/Incus |
| `backend/app/services/engines/lxd_vm.py` | Implémentation LXD |
| `backend/app/services/engines/incus_vm.py` | Implémentation Incus |
| `backend/app/services/engines/virtualbox_vm.py` | Implémentation VirtualBox |
| `backend/app/services/engines/system_container.py` | SystemContainerService ABC |
| `backend/app/services/engines/orchestrator.py` | OrchestratorService ABC |
| `backend/app/services/engines/helm_service.py` | HelmService |

### 6.5 API — Endpoints d'installation

Nouveaux endpoints REST :

```
GET    /api/v1/targets/{id}/install-suggestions     # Outils installables
POST   /api/v1/targets/{id}/install                 # Lancer une installation
GET    /api/v1/targets/{id}/install/{task_id}        # Suivi installation
POST   /api/v1/targets/{id}/install/{tool}/verify    # Vérifier installation
```

---

## 7. Plan de mise en œuvre

### Phase 1 — Fondation (itération 1)

1. **Créer les enums** `VirtualizationGroup`, `SystemCategory`, `SystemTool`
2. **Créer le module `installers/`** avec interfaces abstraites + `PlatformDetector`
3. **Implémenter 2 installateurs** concrets (Docker + K3s) pour valider l'architecture
4. **Créer les interfaces abstraites** des 4 familles de services

### Phase 2 — Scanners modulaires (itération 2)

5. Refactoriser `target_scanner_service.py` en modules par groupe
6. Enrichir les résultats avec groupe/catégorie et suggestions d'installation
7. Ajouter les endpoints API d'installation

### Phase 3 — Services Container Engine (itération 3)

8. Implémenter `DockerEngineService`
9. Implémenter `PodmanEngineService`
10. Implémenter `ComposeService` (Docker + Podman)

### Phase 4 — Services VM (itération 4)

11. Implémenter `LibvirtVMService`
12. Implémenter `LXDIncusBaseService` + `LXDVMService` + `IncusVMService`
13. Implémenter `VirtualBoxVMService`

### Phase 5 — Services Orchestration (itération 5)

14. Implémenter `OrchestratorService` (K8s + K3s + MicroK8s)
15. Implémenter `HelmService`

### Phase 6 — Installateurs complets (itération 6)

16. Implémenter les recettes d'installation pour tous les outils
17. Tests multi-plateforme (Debian, Ubuntu, RHEL, Alpine, Arch)
18. UI : wizard d'installation depuis la page Targets

---

## Annexe A — Tableau récapitulatif des plateformes d'installation

| Outil | Debian/Ubuntu | RHEL/Fedora | Alpine | Arch | openSUSE | Installation principale |
|-------|:---:|:---:|:---:|:---:|:---:|---|
| QEMU/KVM | ✅ | ✅ | ✅ | ✅ | ✅ | Paquet natif |
| Libvirt | ✅ | ✅ | ⚠️ | ✅ | ✅ | Paquet natif |
| VirtualBox | ✅ | ✅ | ❌ | ⚠️ | ✅ | Dépôt Oracle |
| Vagrant | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | Binaire HashiCorp |
| LXC | ✅ | ❌ | ⚠️ | ✅ | ⚠️ | Paquet natif |
| LXD | ✅ (snap) | ✅ (snap) | ❌ | ⚠️ (AUR) | ⚠️ (snap) | Snap |
| Incus | ✅ (snap) | ✅ (snap) | ⚠️ | ⚠️ (AUR) | ⚠️ (snap) | Snap |
| Docker | ✅ | ⚠️ | ✅ | ✅ | ✅ | Dépôt Docker |
| Podman | ✅ | ✅ | ✅ | ✅ | ✅ | Paquet natif |
| Containerd | ✅ | ✅ | ✅ | ✅ | ✅ | Paquet natif |
| K3s | ✅ | ✅ | ⚠️ | ✅ | ✅ | Script officiel |
| MicroK8s | ✅ (snap) | ✅ (snap) | ❌ | ❌ | ✅ (snap) | Snap |
| kubectl | ✅ | ✅ | ✅ | ✅ | ✅ | Binaire + dépôt K8s |
| Helm | ✅ | ✅ | ✅ | ✅ | ✅ | Binaire GitHub |

**Légende :** ✅ supporté nativement | ⚠️ support partiel / communautaire | ❌ non disponible

---

## Annexe B — Glossaire

| Terme | Définition |
|-------|-----------|
| **Container Engine** | Moteur de conteneurs complet (API REST, gestion lifecycle). Ex : Docker, Podman. |
| **Container Runtime** | Runtime bas niveau OCI (exécute les conteneurs). Ex : runc, crun, containerd. |
| **OCI** | Open Container Initiative — standard pour formats d'images et runtimes. |
| **System Container** | Conteneur système (pas OCI) — VM légère partageant le noyau. Ex : LXC, LXD. |
| **Hyperviseur** | Logiciel créant des VMs avec noyau indépendant. Ex : KVM/QEMU, VirtualBox. |
| **Orchestrateur** | Système de gestion de clusters de conteneurs. Ex : Kubernetes, K3s. |
| **Rootless** | Exécution sans privilèges root. Docker rootless, Podman (natif rootless). |
| **Socket Unix** | Point de communication inter-processus local. Utilisé par Docker, Podman, libvirt, LXD, Incus. |
| **Snap** | Système de packaging universel (Canonical). Utilisé par LXD, MicroK8s. |
| **Cloud-init** | Standard de configuration automatique au premier boot d'une VM. |

---

**Références :**
- [Compute Model](general_specs/12-compute-model.md) — Modèle de gestion des objets Compute
- [Architecture](general_specs/02-architecture.md) — Principes architecturaux
- [Roadmap](general_specs/18-roadmap.md) — Plan de développement
- [Stack Technologique](general_specs/03-technology-stack.md) — Technologies utilisées
