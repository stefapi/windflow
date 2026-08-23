# Systèmes de Virtualisation & Conteneurisation — Taxonomie et détection

> **Statut** : Spécification technique · Partiellement implémenté — fiches de détection dérivées du code réel (scanner de Host) ; verbes/adapters = cible general_specs ; annexes = propositions ⚠️ non implémentées · refondu vague 5 — 23/08/2026
> **Périmètre** : Taxonomie des moteurs de virtualisation/conteneurisation derrière les profils canoniques, fiches de détection réelles (commandes, sockets, parsers), correspondance vers les adapters canoniques, et état des lieux du code du scanner.
> **Référence de fond** : [general_specs — ch. 02 Familles de workloads](../general_specs/02-familles-workloads.md) · [ch. 03 Modèle compute](../general_specs/03-modele-compute.md) · [ch. 04 Architecture](../general_specs/04-architecture.md) · [ch. 05 Stack technologique](../general_specs/05-stack-technologique.md) · [ch. 19 Glossaire](../general_specs/19-glossaire.md)
> **Dernière mise à jour** : 2026-08-23

> **Terminologie** : ce document emploie le vocabulaire canonique du glossaire
> ([19-glossaire.md](../general_specs/19-glossaire.md)) : Host (ex-*Target*), Machine (ex-*VM*),
> App, Cluster, profil. Les identifiants du code historique (`target_id`, `TargetType`,
> `target_scanner_service`…) sont cités entre backticks et mis en correspondance à la première
> occurrence.

---

## Table des matières

1. [Cadre de lecture — mapping vers le modèle directeur](#1-cadre-de-lecture--mapping-vers-le-modèle-directeur)
2. [Taxonomie des moteurs](#2-taxonomie-des-moteurs)
3. [Fiches détaillées par système](#3-fiches-détaillées-par-système)
4. [Verbes canoniques & adapters par technologie](#4-verbes-canoniques--adapters-par-technologie)
5. [Matrice profils × capacités](#5-matrice-profils--capacités)
6. [État des lieux du code (implémenté)](#6-état-des-lieux-du-code-implémenté)
7. [Annexe A — Plateformes d'installation](#annexe-a--plateformes-dinstallation)
8. [Annexe B — Glossaire technique](#annexe-b--glossaire-technique)
9. [Annexe C — Propositions non implémentées (⚠️)](#annexe-c--propositions-non-implémentées)

---

## 1. Cadre de lecture — mapping vers le modèle directeur

Ce document décrit les **moteurs** (glossaire : *technologie de runtime détectée sur un Host via
`list_engines`*) — pas les objets gérés. Le classement des objets relève du modèle directeur
general_specs : trois familles (**Apps**, **Machines**, **Hosts**) et l'entité **Cluster**
([ch. 02](../general_specs/02-familles-workloads.md)). Les anciens « groupes » de ce document
pré-refonte se projettent ainsi :

| Regroupement historique (pré-refonte) | Classement canonique | Détail |
|---|---|---|
| « GROUPE VMs » — hyperviseurs (QEMU/KVM, VirtualBox) | **famille Machines** | profils `vm_kvm`, `vm_virtualbox` |
| « GROUPE VMs » — gestionnaires (libvirt/virsh) | **famille Machines** | libvirt = API du profil `vm_kvm` |
| « GROUPE VMs » — containers système (LXC, LXD, Incus) | **famille Machines** — **pas** Apps | un system container est un OS complet avec init system ([ch. 02](../general_specs/02-familles-workloads.md) : « Distinction system container vs container Docker ») ; profils `vm_lxc`, `vm_lxd`, `vm_incus` |
| « GROUPE CONTAINERS » — moteurs (Docker, Podman) | **famille Apps** (+ substrat Host) | profils `docker_container`, `docker_compose` ; le daemon Docker distant définit le profil de Host `host_remote_docker` |
| « GROUPE CONTAINERS » — runtimes bas niveau (containerd, runc, crun) et outils OCI | pas des profils | détectés à titre informatif (dépendances des moteurs ci-dessus) |
| « GROUPE ORCHESTRATION » — Kubernetes (kubeadm, k3s, microk8s), Helm | **entité Cluster** (type `kubernetes`) — **jamais** un Host | adoption via kubeconfig ; Apps cluster-scoped `helm_release` / `k8s_manifest` ([ch. 02](../general_specs/02-familles-workloads.md), arbitrage Kubernetes) |
| (absent de la taxonomie historique) | Swarm | **entité Cluster** (type `docker_swarm`) — détection réelle via `docker info` (section Swarm) |
| Provisioning (Vagrant, Multipass) | hors périmètre canonique | aucun profil ; détection informative uniquement (voir [Annexe C](#annexe-c--propositions-non-implémentées)) |

> **Arbitrage Proxmox (D1)** — Proxmox VE n'est **pas** un backend de Machine : un serveur PVE
> isolé est un **Host** de profil `host_proxmox` (piloté via son API par `ProxmoxHostAdapter`),
> une grappe multi-nœuds est une entité **Cluster** de type `proxmox`. Les VMs et LXC qu'il
> héberge sont dans tous les cas des Machines standard ([ch. 19](../general_specs/19-glossaire.md),
> arbitrage backends VM ; [ch. 05](../general_specs/05-stack-technologique.md) : « Il n'y a pas de
> `ProxmoxService` dans le core »). Le scanner détecte aujourd'hui Proxmox via `pveversion`
> (fiche §3.14).

**Rôle de ce document** : couvrir les technologies derrière **tous** les profils canoniques —
c'est la cible du renvoi explicite de
[19-glossaire.md](../general_specs/19-glossaire.md) et de
[02-familles-workloads.md](../general_specs/02-familles-workloads.md). L'architecture de pilotage
(adapters) est spécifiée côté general_specs (ch. 02 et 05) ; ici : ce que le dépôt implémente
réellement (scan/détection) et la sémantique technique par moteur.

---

## 2. Taxonomie des moteurs

Taxonomie documentaire organisée par catégorie technique. La traduction en code est aujourd'hui
l'enum plat `CapabilityType` ([§6](#6-état-des-lieux-du-code-implémenté)) — les enums hiérarchiques
proposés jadis en §1.1 sont requalifiés en [Annexe C](#annexe-c--propositions-non-implémentées) ⚠️.

```
┌──────────────────────────────────────────────────────────────────────┐
│                     MOTEURS DÉTECTABLES PAR LE SCANNER               │
├──────────────────────────────────────────────────────────────────────┤
│  Hyperviseurs type 2 + gestionnaires        → Machines               │
│  ├── QEMU/KVM        (CLI + /dev/kvm)         profil vm_kvm          │
│  ├── libvirt/virsh   (socket Unix + CLI)      API du profil vm_kvm   │
│  └── VirtualBox      (CLI vboxmanage)         profil vm_virtualbox   │
│                                                                      │
│  Conteneurisation système (VMs légères)     → Machines               │
│  ├── LXC             (CLI + socket rare)      profil vm_lxc          │
│  ├── LXD             (CLI + socket + snap)    profil vm_lxd          │
│  └── Incus           (CLI + socket + snap)    profil vm_incus        │
│                                                                      │
│  Moteurs de conteneurs OCI                  → Apps                   │
│  ├── Docker          (CLI + socket + REST)   profils docker_*        │
│  └── Podman          (CLI + socket rootless) alternative rootless    │
│                                                                      │
│  Runtimes bas niveau & outils OCI            → informatif seulement  │
│  ├── containerd      (daemon + socket gRPC)   dépendance Docker/k3s  │
│  ├── runc / crun     (CLI, invoqués par le parent)                   │
│  └── buildah / skopeo (build & transport sans daemon)                │
│                                                                      │
│  Compose                                     → Apps (docker_compose) │
│  ├── Docker Compose  (plugin v2 / standalone v1)                     │
│  └── Podman Compose  (wrapper)                                       │
│                                                                      │
│  Orchestration                               → Cluster               │
│  ├── K8s (kubeadm) / K3s / MicroK8s  type kubernetes (kubeconfig)    │
│  ├── Helm            (CLI, packages K8s)     Apps helm_release       │
│  └── Swarm           (socket/API Docker)     type docker_swarm       │
│                                                                      │
│  Hors périmètre canonique (détection informative)                    │
│  └── Vagrant, Multipass, Proxmox CLI (pveversion — voir arbitrage D1)│
└──────────────────────────────────────────────────────────────────────┘
```

### 2.1 Tableau de correspondance moteur → classement canonique

| Catégorie | Moteur | `CapabilityType` (code réel) | Classement canonique | Adapter cible |
|---|---|---|---|---|
| Hyperviseurs | QEMU/KVM | `qemu_kvm` | Machines `vm_kvm` | `KVMAdapter` |
| Hyperviseurs | VirtualBox | `virtualbox` | Machines `vm_virtualbox` | `VirtualBoxAdapter` |
| Gestionnaires | libvirt / virsh / virt-install | `libvirt`, `virsh` | Machines `vm_kvm` (API) | `KVMAdapter` |
| Containers système | LXC | `lxc` | Machines `vm_lxc` | `LXCAdapter` |
| Containers système | LXD | `lxd` | Machines `vm_lxd` (VM ou mode container) | `LXDAdapter` |
| Containers système | Incus | `incus` | Machines `vm_incus` (VM ou mode container) | `IncusAdapter` |
| Moteurs OCI | Docker | `docker` | Apps `docker_container`/`docker_compose` ; Host `host_remote_docker` | `DockerContainerAdapter`/`ComposeStackAdapter` |
| Moteurs OCI | Podman | `podman` | Apps (alternative rootless) | — |
| Runtimes | containerd | `containerd` | informatif (dépendance Docker/k3s) | — |
| Runtimes | runc / crun | `runc` / `crun` | informatif | — |
| Outils OCI | buildah / skopeo | `buildah` / `skopeo` | informatif | — |
| Compose | Docker Compose | `docker_compose` | Apps `docker_compose` | `ComposeStackAdapter` |
| Compose | Podman Compose | `podman_compose` | Apps (alternative) | — |
| Orchestration | K8s/kubeadm | `kubeadm`, `kubectl` | **Cluster** `kubernetes` | `KubernetesClusterAdapter` |
| Orchestration | K3s | `k3s` | **Cluster** `kubernetes` | `KubernetesClusterAdapter` |
| Orchestration | MicroK8s | `microk8s` | **Cluster** `kubernetes` | `KubernetesClusterAdapter` |
| Orchestration | Helm | `helm` | Apps `helm_release` (sur Cluster) | `HelmReleaseAdapter` |
| Orchestration | Swarm | `docker_swarm` | **Cluster** `docker_swarm` | `SwarmClusterAdapter` |
| Hors périmètre | Vagrant / Multipass | `vagrant` / `multipass` | aucun profil (informatif) | — |
| Hors périmètre | Proxmox (CLI) | `proxmox` | Host `host_proxmox` / Cluster `proxmox` (arbitrage D1) | `ProxmoxHostAdapter` / `ProxmoxClusterAdapter` |

Les verbes et le contrat des adapters cités sont spécifiés au [ch. 02](../general_specs/02-familles-workloads.md)
(verbes universels, hiérarchies d'adapters) ; les technologies de binding au
[ch. 05](../general_specs/05-stack-technologique.md) (« pas sur des services de VM monolithiques »).

---

## 3. Fiches détaillées par système

Chaque fiche décrit la **détection réellement implémentée** dans le scanner
([`target_scanner_service.py`](../../backend/app/services/target_scanner_service.py) — scan de
Host, ex-« cible »), les sockets sondés ([`socket_clients.py`](../../backend/app/services/socket_clients.py)),
et les variantes de plateforme qui comptent. Les paquets exacts par distribution sont regroupés en
[Annexe A](#annexe-a--plateformes-dinstallation).

> **Note d'état** : le scanner est l'implémentation actuelle du scan de Host. La cible general_specs
> est `POST /hosts/{id}/scan` + discovery/réconciliation
> ([ch. 09](../general_specs/09-api.md) ; [ch. 03](../general_specs/03-modele-compute.md)) ;
> les routes existantes sont aujourd'hui montées sous `/api/v1/targets` ([§6.4](#64-api)).

### 3.1 QEMU/KVM — profil `vm_kvm`

**Détection réelle :** [`_detect_cli_tools`](../../backend/app/services/target_scanner_service.py) + `_check_kvm_device`

| Aspect | Détail |
|--------|--------|
| Commandes | `qemu-system-x86_64 --version`, `test -e /dev/kvm && echo 'present'` |
| Socket | Aucun — pilotage via libvirt (fiche 3.2) |
| Détails remontés | `version`, `kvm_device: true` si `/dev/kvm` présent |
| Prérequis noyau | Modules `kvm`, `kvm_intel`/`kvm_amd` ; VT-x/AMD-V activé dans le BIOS |
| Architectures | amd64 et arm64 (KVM natif) ; émulation TCG sans KVM |

**Sémantique spécifique** : live migration entre Hosts KVM (action Avancé Machine, [ch. 02](../general_specs/02-familles-workloads.md) § Migration), disques qcow2 (export de backup), définition XML libvirt (onglet Mode Infra « Définition libvirt (XML) »).

### 3.2 libvirt / virsh — API du profil `vm_kvm`

**Détection réelle :** `_detect_libvirt` + [`LibvirtSocketClient`](../../backend/app/services/socket_clients.py)

| Aspect | Détail |
|--------|--------|
| Sockets (sondés dans l'ordre) | `/var/run/libvirt/libvirt-sock` (system) puis `/run/user/{uid}/libvirt/libvirt-sock` (session) |
| URI choisie | `qemu:///system` ou `qemu:///session` selon le mode du socket trouvé |
| Commandes | `virsh --version`, `virt-install --version` |
| Collecte socket | `LibvirtSocketClient.collect_details()` → version + détails si le socket répond |

**Sémantique spécifique** : console VNC/SPICE (`open_vnc_console()` du `MachineAdapter`), snapshots (`virsh snapshot-create-as`), hardware édité via XML (`virsh edit`). Verbe Power traduit par `virsh start` / `virsh shutdown` (ACPI) / `virsh reboot` (mapping complet au [ch. 02](../general_specs/02-familles-workloads.md), « Mapping par profil Machine »).

### 3.3 VirtualBox — profil `vm_virtualbox`

**Détection réelle :** `_detect_cli_tools`

| Aspect | Détail |
|--------|--------|
| Commande | `vboxmanage --version` |
| Socket | Aucun — toutes les opérations passent par le CLI `VBoxManage` (API propriétaire) |
| Conséquence | adapter réduit : pas de live migration ; console via RDP/VRDE |

**Sémantique spécifique** : power via `VBoxManage startvm` / `controlvm acpipowerbutton` / `controlvm reset` ; snapshots `VBoxManage snapshot take` ; hardware `VBoxManage modifyvm` ; export OVA pour le backup.

### 3.4 LXC — profil `vm_lxc`

**Détection réelle :** `_detect_lxc`

| Aspect | Détail |
|--------|--------|
| Commandes | `lxc-info --version`, `lxc-checkconfig 2>/dev/null \| head -20` (support noyau) |
| Socket | `/run/lxc.socket` (rare) |
| Prérequis noyau | namespaces, cgroups v1/v2, seccomp — vérifiés par `lxc-checkconfig` |

**Sémantique spécifique** : conteneurs système sans daemon de gestion — moins de fonctionnalités que LXD/Incus (snapshots limités via `lxc-snapshot`, pas de migration à chaud). Console `lxc-console`, config par fichier. Redémarrage = `lxc-stop && lxc-start`.

### 3.5 LXD — profil `vm_lxd` (VM ou mode container)

**Détection réelle :** `_detect_lxd`

| Aspect | Détail |
|--------|--------|
| Commandes | `lxd --version` (daemon), `lxc version` (client) |
| Sockets | `/var/lib/lxd/unix.socket` ou `/var/snap/lxd/common/lxd/unix.socket` |
| Installation | méthode détectée : `snap list lxd` → `install_method="snap"`, sinon `"package"` |
| Service | `systemctl is-active snap.lxd.daemon \|\| systemctl is-active lxd` |

**Sémantique spécifique** : API REST complète via socket Unix (instances en mode VM **ou** mode
container — les deux sont des Machines, [ch. 02](../general_specs/02-familles-workloads.md)) ;
snapshots natifs (`lxc snapshot`), export (`lxc export`), console (`lxc console`), exec (`lxc exec`),
**migration à chaud** entre Hosts LXD.

### 3.6 Incus — profil `vm_incus` (VM ou mode container)

**Détection réelle :** `_detect_incus`

| Aspect | Détail |
|--------|--------|
| Commande | `incus version` |
| Sockets | `/var/lib/incus/unix.socket` ou `/var/snap/incus/common/incus/unix.socket` |
| Installation | snap ou paquet natif (détecté comme LXD) |

**Mutualisation LXD/Incus** : fork communautaire de LXD — les API REST via socket Unix sont
quasi-identiques (~95 % de surface commune, endpoints `/1.0/instances`…). La cible
general_specs reste **deux adapters distincts** (`LXDAdapter`, `IncusAdapter`), une base commune
de client REST pouvant factoriser la logique ; les deux outils divergent progressivement.
Verbes : `incus start/stop/restart`, `incus snapshot create`, `incus console`, `incus export`.

### 3.7 Docker — profils `docker_container`, `docker_compose` ; Host `host_remote_docker`

**Détection réelle :** `_detect_docker` + [`DockerSocketClient`](../../backend/app/services/socket_clients.py)

| Aspect | Détail |
|--------|--------|
| Commandes | `docker --version`, `docker info --format '{{json .}}'` |
| Sockets | `/var/run/docker.sock` (system), `/run/user/{uid}/docker.sock` (rootless) |
| Cheminement | socket local sondé en priorité (exécution locale) → collecte via client socket ; sinon fallback CLI (`docker info` parsé) |
| Swarm | section `Swarm` de `docker info` : `LocalNodeState` (active/inactive), `ControlAvailable` → rôle manager/worker |

**Sémantique spécifique** : un daemon Docker distant accessible via SSH définit le profil de Host
`host_remote_docker` ([ch. 02](../general_specs/02-familles-workloads.md)) ; l'API Docker n'est
jamais exposée sur le réseau ([ch. 04](../general_specs/04-architecture.md)). Le verbe Mettre à
jour des profils conteneurs est une recréation à configuration préservée (rebase par valeur des
env/labels/cmd — [ch. 02](../general_specs/02-familles-workloads.md) § Sémantique de mise à jour).
Un Swarm actif est une entité **Cluster** `docker_swarm` (membres manager/worker).

### 3.8 Podman — moteur rootless (détecté, pas de profil dédié)

**Détection réelle :** `_detect_podman`

| Aspect | Détail |
|--------|--------|
| Commandes | `podman --version`, `podman info --format json` (payload `info` complet) |
| Sockets | `/run/podman/podman.sock` (system), `/run/user/{uid}/podman/podman.sock` (rootless) |
| Mode par défaut | rootless, sans daemon |

**Compatibilité Docker** : l'API REST Podman est volontairement compatible avec l'API Docker
(socket) — un socle de client commun est envisageable côté implémentation ; le classement
canonique des workloads reste celui de Docker (profils `docker_*`).

### 3.9 containerd — runtime (informatif)

**Détection réelle :** `_detect_containerd`

| Aspect | Détail |
|--------|--------|
| Commandes | `containerd --version`, fallback `ctr version` (`detected_via: "ctr"`) |
| Sockets | `/run/containerd/containerd.sock`, `/run/k3s/containerd/containerd.sock` |
| Détails | `managed_by: "k3s"` si le socket k3s est présent |

Souvent installé comme dépendance de Docker ou k3s — pas de pilotage direct par WindFlow.

### 3.10 runc / crun — runtimes OCI bas niveau (informatifs)

**Détection réelle :** `_detect_oci_tools` — `runc --version` (parser tolérant multi-ligne), `crun --version`. Invoqués par le runtime parent ; jamais pilotés directement.

### 3.11 buildah / skopeo — outils OCI (informatifs)

**Détection réelle :** `_detect_oci_tools` — `buildah --version`, `skopeo --version`. Build sans daemon et transport d'images entre registries ; alternatives possibles aux CLI Docker côté implémentation, sans classement dédié.

### 3.12 Docker Compose / Podman Compose — profil `docker_compose`

**Détection réelle :** `_detect_docker_compose` (plugin puis binaire), `_detect_oci_tools` (podman-compose)

| Outil | Commande | Détail remonté |
|-------|----------|----------------|
| Compose v2 | `docker compose version` | `plugin_based: true` |
| Compose v1 | `docker-compose --version` | `plugin_based: false` (standalone Python, déprécié) |
| Podman Compose | `podman-compose --version` | wrapper Python autour de Podman |

La distinction plugin/binaire est remontée dans le résultat de scan (`DockerComposeInfo`) — elle
conditionne les commandes de déploiement (`docker compose …` vs `docker-compose …`).

### 3.13 Kubernetes : kubeadm / K3s / MicroK8s — **Cluster** type `kubernetes`

> **Classement** : un cluster Kubernetes (k8s, k3s, microk8s) est une entité **Cluster** adoptée
> via kubeconfig — jamais un Host, jamais un « système détecté » de plus ([ch. 02](../general_specs/02-familles-workloads.md),
> arbitrage Kubernetes : le profil `host_kubernetes` est supprimé). Les nœuds restent des
> Hosts/Machines scannés individuellement par SSH.

**Détection réelle :** `_detect_kubernetes`

| Distribution | Commande de détection | Particularité |
|---|---|---|
| K8s via kubeadm | `kubeadm version -o json`, `kubectl version --client -o json` | parsers JSON (gitVersion, major/minor) |
| K3s | `k3s --version` | embarque son propre containerd (`/run/k3s/containerd/…`, cf. fiche 3.9) ; kubeconfig `/etc/rancher/k3s/k3s.yaml` |
| MicroK8s | `microk8s.kubectl version --output=json` | installation snap uniquement |

**Sémantique cible** : connexion par kubeconfig (`KubernetesClusterAdapter`) ; Apps cluster-scoped
`helm_release` / `k8s_manifest` hébergées par le Cluster (`apps.cluster_id`) ; scan cluster-scoped
complémentaire du scan SSH des nœuds ([ch. 03](../general_specs/03-modele-compute.md) § Scan du
Cluster vs scan des nœuds).

### 3.14 Helm — Apps `helm_release`

**Détection réelle :** `_detect_kubernetes` — `helm version --short`. Binaire unique identique
pour tous les clusters (implémentation CLI naturelle) ; les opérations par verbe (install /
upgrade / rollback / history) sont spécifiées au [ch. 02](../general_specs/02-familles-workloads.md)
(mapping par profil App).

### 3.15 Docker Swarm — **Cluster** type `docker_swarm`

**Détection réelle :** intégrée à la détection Docker (fiche 3.7) — section `Swarm` de
`docker info` : `LocalNodeState` → `active`/`inactive`, `ControlAvailable` → rôle
`manager`/`worker` (`DockerSwarmInfo`). Un Swarm actif est une entité Cluster (membres
manager/worker, connexion socket/API Docker) ; les stacks Swarm y sont des Apps hébergées.

### 3.16 Proxmox VE — Host `host_proxmox` / Cluster `proxmox` (arbitrage D1)

**Détection réelle :** `_detect_cli_tools` — `pveversion`. La détection actuelle est purement
CLI ; la consommation cible passe par l'**API REST** Proxmox (`/api2/json/…`), jamais par
« backend VM » : serveur isolé = Host `host_proxmox` (`ProxmoxHostAdapter`), grappe multi-nœuds =
Cluster `proxmox` (`ProxmoxClusterAdapter`) ; les VMs/qemu et LXC du serveur sont des Machines
standard. Le scan cible d'un Host `host_proxmox` est spécifié au [ch. 03](../general_specs/03-modele-compute.md)
(`GET /api2/json/nodes/{node}/qemu`, `…/lxc`).

> Vagrant et Multipass (détectés par le scanner : `vagrant --version`, `multipass version`) n'ont
> **aucun profil canonique** — fiches déplacées en [Annexe C](#annexe-c--propositions-non-implémentées).

---

## 4. Verbes canoniques & adapters par technologie

> ⚠️ **Architecture non implémentée** — les ABC « services mutualisés »
> (`ContainerEngineService`, `ComposeService`, `VMService`, `SystemContainerService`,
> `OrchestratorService`, `HelmService`) qui occupaient ~800 lignes de ce document **n'ont jamais
> été implémentés** et contredisaient le modèle directeur : general_specs impose des
> **`WorkloadAdapter` par profil** — « pas des services de VM monolithiques »
> ([ch. 05](../general_specs/05-stack-technologique.md) ; [ch. 02](../general_specs/02-familles-workloads.md)).
> Ils sont supprimés ; cette section mappe chaque moteur aux adapters canoniques et conserve la
> sémantique technique des opérations en prose.

### 4.1 Correspondance verbes → opérations natives

Les **verbes universels** (Start/Stop, Power, Snapshot, Console, Sauvegarder…) sont définis par
famille au [ch. 02](../general_specs/02-familles-workloads.md) — mappings complets dans ce
chapitre (« Mapping par profil App / Machine / Host », « Mapping par type de Cluster »). Extrait
du mapping Machines (renvoi, non dupliqué ici) :

| Verbe | `vm_kvm` (libvirt) | `vm_lxd` / `vm_incus` | `vm_lxc` | `vm_virtualbox` |
|-------|--------------------|------------------------|----------|-----------------|
| Power on | `virsh start` | `lxc`/`incus start` | `lxc-start` | `VBoxManage startvm` |
| Power off | `virsh shutdown` | `lxc`/`incus stop` | `lxc-stop` | `controlvm acpipowerbutton` |
| Snapshot | `virsh snapshot-create-as` | `snapshot` / `snapshot create` | (limité) | `snapshot take` |
| Console | VNC/SPICE via libvirt | `console` | `lxc-console` | RDP/VRDE |
| Hardware | `virsh edit` (XML) | `config edit` | config fichier | `modifyvm` |
| Backup | copie qcow2 | `export` | tarball rootfs | export OVA |

Sémantique notable, conservée des anciennes sections techniques :
- **`Power off` ≠ `Stop`** : shutdown ACPI d'un PC, pas l'arrêt d'un service ( Machines) ;
- **Snapshots Machines** : capture mémoire + disques (snapshot à chaud), verbe canonique toujours présent ;
- **KVM** : live migration entre Hosts KVM ; console VNC/SPICE pour noVNC (`open_vnc_console()`) ;
- **LXD/Incus** : migration à chaud, exec, fichiers poussés/lus dans l'instance ; API REST ~95 % commune ;
- **VirtualBox** : CLI seul (pas de socket, pas de live migration) ;
- **Apps conteneurs** : mise à jour = **recréation à configuration préservée** (rebase par valeur, secrets masqués `***` — [ch. 02](../general_specs/02-familles-workloads.md)) ;
- **Clusters** : santé agrégée depuis les membres, events, console par membre ; pas de cycle de vie universel.

### 4.2 Services existants vs cible

*État actuel (implémenté)* : le pilotage Docker/compose existe via des services dédiés
([`docker_service.py`](../../backend/app/services/docker_service.py),
[`docker_compose_service.py`](../../backend/app/services/docker_compose_service.py) — voir
[§6.3](#63-services-existants)) ; **aucun** pilotage VM (KVM/LXD/Incus/VirtualBox), Proxmox, K8s
ou Helm n'est implémenté.

*Cible (general_specs ch. 02/04/05)* : `Machine Service` pilotant la famille Machines via
`KVMAdapter`, `LXDAdapter`, `IncusAdapter`, `LXCAdapter`, `VirtualBoxAdapter` ;
`Host Service` via `BaremetalHostAdapter`, `ProxmoxHostAdapter`, `RemoteDockerHostAdapter` ;
`Cluster Service` via `KubernetesClusterAdapter`, `ProxmoxClusterAdapter`, `SwarmClusterAdapter` ;
App adapters par profil (`DockerContainerAdapter`, `ComposeStackAdapter`, `HelmReleaseAdapter`,
`K8sManifestAdapter`). Contrat commun : identité (`family()`, `profile()`), métriques/santé,
`contextual_actions()`, Mode Infra (`get_native_config()`, `get_technical_components()`).

---

## 5. Matrice profils × capacités

La « matrice de mutualisation » historique (systèmes × ABC) est redressée en matrice canonique :
**profils × capacités détection/exécution**. La colonne « scan » reflète ce que le scanner remonte
réellement ; la colonne « verbes » reflète l'adapter cible.

| Profil canonique | Moteurs détectés (`CapabilityType`) | Scan (code réel) | Verbes (adapter cible) |
|---|---|---|---|
| Apps `docker_container` | `docker` | ✅ CLI + socket + info | ✅ `DockerContainerAdapter` (cible) |
| Apps `docker_compose` | `docker`, `docker_compose` | ✅ plugin/binaire distingués | ✅ `ComposeStackAdapter` (cible) |
| Apps `helm_release` | `helm` (+ cluster k8s) | ✅ version | ⚠️ cible |
| Apps `k8s_manifest` | `kubectl` (+ cluster k8s) | ✅ version | ⚠️ cible |
| Machines `vm_kvm` | `qemu_kvm`, `libvirt`, `virsh` | ✅ CLI + `/dev/kvm` + socket libvirt | ⚠️ cible `KVMAdapter` |
| Machines `vm_lxd` | `lxd` | ✅ daemon+client, snap, socket, service | ⚠️ cible `LXDAdapter` |
| Machines `vm_incus` | `incus` | ✅ idem LXD | ⚠️ cible `IncusAdapter` |
| Machines `vm_lxc` | `lxc` | ✅ version + checkconfig | ⚠️ cible `LXCAdapter` |
| Machines `vm_virtualbox` | `virtualbox` | ✅ version CLI | ⚠️ cible `VirtualBoxAdapter` |
| Hosts `host_baremetal` | — (substrat SSH/local) | ✅ plateforme, OS, profil d'accès | ⚠️ cible `BaremetalHostAdapter` |
| Hosts `host_proxmox` | `proxmox` | ✅ `pveversion` (CLI seul) | ⚠️ cible API REST |
| Hosts `host_remote_docker` | `docker` (distant) | ✅ via SSH | ⚠️ cible `RemoteDockerHostAdapter` |
| Cluster `kubernetes` | `kubeadm`/`k3s`/`microk8s`, `kubectl`, `helm` | ✅ versions CLI (outils) | ⚠️ cible kubeconfig |
| Cluster `docker_swarm` | `docker_swarm` (via `docker info`) | ✅ état + rôle | ⚠️ cible socket/API |
| Cluster `proxmox` | `proxmox` (par nœud) | ✅ `pveversion` | ⚠️ cible API cluster |
| — (informatif) | `podman`, `podman_compose`, `containerd`, `runc`, `crun`, `buildah`, `skopeo`, `vagrant`, `multipass` | ✅ versions/socket | pas de profil |

---

## 6. État des lieux du code (implémenté)

Cette section remplace l'ancienne section « Impacts sur le code existant » (obsolète : elle
décrivait des fichiers à créer qui n'existent pas — voir [Annexe C](#annexe-c--propositions-non-implémentées)).
Description du **dépôt réel**.

### 6.1 Enums réels

Fichier unique : [`backend/app/enums/target.py`](../../backend/app/enums/target.py). Cinq enums
plats (aucune hiérarchie groupes/catégories — contrairement à l'ancienne §1.1) :

| Enum | Valeurs | Rôle |
|---|---|---|
| `TargetType` | `docker`, `docker_compose`, `docker_swarm`, `kubernetes`, `vm`, `physical` | type d'une cible en base (correspondance vers profils canoniques : [README](README.md), table de correspondance ; `vm` couvre les profils `vm_kvm`/`vm_lxd`/… cibles) |
| `TargetStatus` | `online`, `offline`, `error`, `maintenance` | statut d'une cible |
| `SSHAuthMethod` | `local`, `password`, `ssh_key` | authentification SSH |
| `AccessLevel` | `root`, `sudo`, `sudo_passwordless`, `limited` | niveau d'accès détecté (profil d'accès) |
| `CapabilityType` | 25 valeurs plates (virtualisation, Docker, Podman, LXC/LXD/Incus, runtimes, OCI, k8s) | capacités remontées par le scan |

### 6.2 Scanner de Host — pipeline réel

Le scan est implémenté par cinq modules collaborateurs :

| Module | Rôle |
|---|---|
| [`target_scanner_service.py`](../../backend/app/services/target_scanner_service.py) | orchestrateur : scan localhost/SSH, profil d'accès, double scan standard/élevé, persistance |
| [`target_scan_parsers.py`](../../backend/app/services/target_scan_parsers.py) | parsers de versions + mappings clé → `CapabilityType` + construction du payload |
| [`target_access_profile.py`](../../backend/app/services/target_access_profile.py) | détection du profil d'accès (`whoami`, `which sudo`, `sudo -n`, `sudo -S`) |
| [`socket_clients.py`](../../backend/app/services/socket_clients.py) | `SocketProbe` (topologie des sockets) + `DockerSocketClient` + `LibvirtSocketClient` |
| [`commands.py`](../../backend/app/services/commands.py) | protocole `CommandExecutor` — `LocalCommandExecutor` (subprocess) et `SSHCommandExecutor` (asyncssh, préfixe sudo `sudo -S -p '' -u <user>`) |

Pipeline central ([`_run_scan`](../../backend/app/services/target_scanner_service.py)) — toutes
les détections en parallèle via `asyncio.gather`, chaque propriété isolée (un échec n'arrête pas
les autres) :

```python
results = await asyncio.gather(
    self._safe_execute(self._detect_platform, executor, errors),
    self._safe_execute(self._detect_os, executor, errors),
    self._safe_execute(self._detect_virtualization, executor, errors, default={}),
    self._safe_execute(self._detect_docker_for_host(executor, host), errors),
    self._safe_execute(self._detect_kubernetes, executor, errors, default={}),
    self._safe_execute(self._detect_container_runtimes, executor, errors, default={}),
    self._safe_execute(self._detect_oci_tools, executor, errors, default={}),
)
```

*Source : `backend/app/services/target_scanner_service.py`, `_run_scan` (timeout par défaut 30 s ;
le scan est réussi si la plateforme est détectée — preuve de joignabilité).*

**Détection plateforme & OS** (`_detect_platform`, `_detect_os`) — chaque propriété est isolée,
un échec n'empêche pas les autres (fallbacks Linux puis macOS/BSD) :

| Information | Commandes (premier succès retenu) |
|---|---|
| Architecture | `uname -m` → mapping `x86_64`/`amd64` → `x86_64` ; `aarch64`/`arm64` → `arm64` ; `i386`/`i686` → `x86_32` ; `armv6`/`v7`/`v8`… (enum `PlatformArchitecture`) |
| Modèle CPU | `grep -m1 'model name' /proc/cpuinfo \| cut -d':' -f2`, sinon `sysctl -n machdep.cpu.brand_string` |
| Cœurs CPU | `nproc`, sinon `sysctl -n hw.ncpu` |
| Mémoire totale | `grep MemTotal /proc/meminfo` (Ko → Go), sinon `sysctl -n hw.memsize` (octets → Go) |
| Système / kernel | `uname -s`, `uname -r` |
| Distribution / version | `cat /etc/os-release` (champs `NAME=`, `VERSION=`), sinon `lsb_release -ds` |

**Scan d'une cible stockée** (`scan_and_update_target`) : 1) marquage `scanning`, 2) scan standard
(avec sudo si configuré), 3) détection du profil d'accès (connexion SSH unique réutilisée),
4) **double scan** sans sudo → `standard_capabilities` vs `elevated_capabilities`, 5) persistance
via `TargetService.apply_scan_result` ; échec → `mark_scan_failed`.

**Sondes de sockets** — topologie centralisée dans `SocketProbe.SOCKET_PATHS`
([`socket_clients.py`](../../backend/app/services/socket_clients.py)), sondée dans l'ordre
system → rootless → session (`test -S` puis `test -r`) :

```python
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
        "system": ["/var/lib/lxd/unix.socket",
                   "/var/snap/lxd/common/lxd/unix.socket"],
    },
    "incus": {
        "system": ["/var/lib/incus/unix.socket",
                   "/var/snap/incus/common/incus/unix.socket"],
    },
    "libvirt": {
        "system": ["/var/run/libvirt/libvirt-sock"],
        "session": ["/run/user/{uid}/libvirt/libvirt-sock"],
    },
    "lxc": {"system": ["/run/lxc.socket"]},
    "containerd": {
        "system": ["/run/containerd/containerd.sock",
                   "/run/k3s/containerd/containerd.sock"],
    },
}
```

*Source : `backend/app/services/socket_clients.py`, `SocketProbe` (extrait ; `{uid}` résolu localement).*

**Profil d'accès** — [`TargetAccessProfileDetector.detect()`](../../backend/app/services/target_access_profile.py) :
`whoami` → root ? · `which sudo` → binaire présent ? · test sudo (avec mot de passe via stdin
local, sans mot de passe `-n`, vers root ou vers un utilisateur) → `AccessLevel` + indicateurs
`sudo_verified`, `sudo_passwordless`, `can_install_packages` (root ou sudo→root uniquement).

**Schéma du résultat** (`ScanResult`, schéma Pydantic de
[`schemas/target_scan.py`](../../backend/app/schemas/target_scan.py)) :

| Champ | Type | Contenu |
|---|---|---|
| `platform` | `PlatformInfo` | `architecture` (enum), `cpu_model`, `cpu_cores`, `total_memory_gb` |
| `os` | `OSInfo` | `system`, `kernel`, `distribution`, `version` |
| `virtualization` | `dict[str, ToolInfo]` | `libvirt`, `virsh`, `virtualbox`, `vagrant`, `proxmox`, `qemu_kvm`, `podman`, `multipass` |
| `docker` | `DockerCapabilities` | `installed`, `running`, `socket_accessible`, `socket`, `compose` (`plugin_based`), `swarm` (`active`, `node_role`) |
| `kubernetes` | `dict[str, ToolInfo]` | `kubectl`, `kubeadm`, `k3s`, `microk8s`, `helm` |
| `container_runtimes` | `dict[str, ContainerRuntimeInfo]` | `lxc`, `lxd`, `incus`, `containerd` (+ `install_method`, `service_status`) |
| `oci_tools` | `dict[str, ToolInfo]` | `runc`, `crun`, `buildah`, `skopeo`, `podman_compose` |
| `discovered_sockets` | `dict[str, SocketInfo]` | sockets unifiés de toutes les familles (`path`, `exists`, `accessible`, `mode`) |
| `errors` | `list[str]` | erreurs de détection non bloquantes |

Un outil est décrit par `ToolInfo` (`available`, `version`, `details` — dict libre : `socket`,
`snap_info`, `managed_by`, `kvm_device`…) ou `ContainerRuntimeInfo` (ajoute `socket` et
`install_method`). La persistance passe par `build_capabilities_payload()`
([`target_scan_parsers.py`](../../backend/app/services/target_scan_parsers.py)) puis
`TargetService.apply_scan_result()` (capacités + payloads plateforme/OS + profil d'accès).

### 6.3 Services existants

Au-delà du scan, le pilotage réellement implémenté se limite à Docker :

| Service | Rôle réel |
|---|---|
| [`docker_service.py`](../../backend/app/services/docker_service.py) | containers Docker simples (substitution de variables, génération de secrets, cycle de vie) |
| [`docker_compose_service.py`](../../backend/app/services/docker_compose_service.py) | déploiement de templates Compose (rendu + exécution) |
| [`docker_client_service.py`](../../backend/app/services/docker_client_service.py) | client REST Engine v1.41+ via socket local (aiohttp) |
| [`docker_executor.py`](../../backend/app/services/docker_executor.py) | abstraction d'exécution : **CLI prioritaire**, socket en fallback |
| [`terminal_service.py`](../../backend/app/services/terminal_service.py) | sessions exec interactives (PTY) pour terminal de container |
| [`compute_service.py`](../../backend/app/services/compute_service.py) | agrégation de la vue Compute (classification par labels, objets domaine) |
| [`adoption_service.py`](../../backend/app/services/adoption_service.py) | adoption d'objets découverts (création Stack+Deployment, labelisation) |

**Écart explicite avec la cible** : aucun adapter `WorkloadAdapter`/`MachineAdapter`/
`HostAdapter`/`ClusterAdapter` n'existe encore dans le dépôt ; les services Docker ci-dessus en
tiennent lieu pour la famille Apps Docker. La migration vers les adapters (et l'ajout des
familles Machines/Hosts/Clusters) est une évolution de code tracée pour la
[Roadmap](../Roadmap.md), hors périmètre de ce document.

### 6.4 API

*État actuel (implémenté)* : routes montées sous `/api/v1/targets`
([`api/v1/targets/`](../../backend/app/api/v1/targets)) :

| Route | Module | Rôle |
|---|---|---|
| `POST /targets/discover` | `scanning.py` | scan + création de cible (localhost ou SSH, inférence du type) |
| `POST /targets/{id}/scan` | `scanning.py` | re-scan d'une cible stockée |
| `POST /targets/{id}/health-check` | `capabilities.py` | test de santé |
| `GET /targets/{id}/capabilities` (+ `/{capability_type}`, `/virtualization`) | `capabilities.py` | capacités persistées |
| `POST /targets/test-reachability`, `POST /targets/test-connection` | `connectivity.py` | tests de connectivité/SSH |
| CRUD `GET/POST/PUT/DELETE /targets…` | `crud.py` | gestion des cibles |

*Cible (general_specs ch. 09)* : `POST /hosts/{id}/scan` et ContextualActions
`POST /hosts/{id}/actions/{action_id}` (reboot, update OS…), surfaces par famille
(`/apps`, `/machines`, `/hosts`, `/clusters`) et `/compute/*` (Mode Infra). Le mapping
`targets` → `hosts` est tracé dans le [README du corpus](README.md).

---

## Annexe A — Plateformes d'installation

Fait technique conservé : disponibilité des moteurs par famille de distribution (utile au
diagnostic et aux futures propositions d'installation — voir Annexe C). Légende : ✅ supporté
nativement · ⚠️ support partiel/communautaire · ❌ non disponible.

| Moteur | Debian/Ubuntu | RHEL/Fedora | Alpine | Arch | openSUSE | Méthode principale |
|--------|:---:|:---:|:---:|:---:|:---:|---|
| QEMU/KVM | ✅ | ✅ | ✅ | ✅ | ✅ | paquet natif |
| libvirt | ✅ | ✅ | ⚠️ | ✅ | ✅ | paquet natif |
| VirtualBox | ✅ | ✅ | ❌ | ⚠️ | ✅ | dépôt Oracle |
| LXC | ✅ | ❌ | ⚠️ | ✅ | ⚠️ | paquet natif |
| LXD | ✅ (snap) | ✅ (snap) | ❌ | ⚠️ (AUR) | ⚠️ (snap) | snap |
| Incus | ✅ (snap) | ✅ (snap) | ⚠️ | ⚠️ (AUR) | ⚠️ (snap) | snap |
| Docker | ✅ | ⚠️ | ✅ | ✅ | ✅ | dépôt Docker |
| Podman | ✅ | ✅ | ✅ | ✅ | ✅ | paquet natif |
| containerd | ✅ | ✅ | ✅ | ✅ | ✅ | paquet natif |
| kubeadm (K8s) | ✅ | ✅ | ⚠️ | ⚠️ (AUR) | ✅ | dépôt Kubernetes |
| K3s | ✅ | ✅ | ⚠️ | ✅ | ✅ | script officiel |
| MicroK8s | ✅ (snap) | ✅ (snap) | ❌ | ❌ | ✅ (snap) | snap |
| kubectl | ✅ | ✅ | ✅ | ✅ | ✅ | binaire + dépôt K8s |
| Helm | ✅ | ✅ | ✅ | ✅ | ✅ | binaire GitHub |

Variantes notables par version (conservées des fiches historiques) : Debian < 11 / Ubuntu 18.04
ont des noms de paquets différents (`qemu-system-x86`, meta-paquet `qemu-kvm` absent) ; RHEL 7 →
`yum`, RHEL 8+ → `dnf` ; Docker non officiel sur RHEL 8/9 (Podman recommandé) ; K3s en musl
(Alpine) partiellement supporté.

---

## Annexe B — Glossaire technique

Définitions techniques strictes ; pour la terminologie produit (Host, Machine, App, Cluster,
profil…), voir le glossaire canonique ([19-glossaire.md](../general_specs/19-glossaire.md)) —
définitif en cas de divergence.

| Terme | Définition |
|-------|-----------|
| **Moteur (engine)** | Technologie de runtime détectée sur un Host (Docker, libvirt, Kubernetes…) via `list_engines` ([ch. 02](../general_specs/02-familles-workloads.md)) |
| **Container engine** | Moteur complet (API REST, cycle de vie) — Docker, Podman |
| **Runtime OCI bas niveau** | Exécuteur de conteneurs conforme OCI, invoqué par le parent — runc, crun, containerd |
| **System container** | Conteneur système à OS complet (init, SSH) partageant le noyau — LXC, LXD/Incus mode container. C'est une **Machine** au sens canonique, pas une App |
| **Hyperviseur** | Créateur de VMs à noyau indépendant — KVM/QEMU, VirtualBox |
| **Rootless** | Exécution sans root — Docker rootless, Podman (natif rootless) |
| **Socket Unix** | Point de communication local utilisé par Docker, Podman, libvirt, LXD, Incus, containerd |
| **Snap** | Packaging Canonical — méthode principale de LXD, Incus, MicroK8s |
| **Cloud-init** | Configuration automatique au premier boot d'une Machine (Machine Templates, [ch. 12](../general_specs/12-marketplace.md)) |

---

## Annexe C — Propositions non implémentées

> ⚠️ Tout le contenu de cette annexe décrit du **non implémenté**.

Contenus de l'ancienne spec décrivant des **cibles jamais arbitrées ni implémentées**, conservés
en trace condensée pour le backlog (aucun de ces éléments n'existe dans le code ; ne pas citer
comme existant).

### C.1 Fiches hors périmètre canonique : Vagrant, Multipass

Détectés par le scanner (`vagrant --version`, `multipass version` — parsers
[`target_scan_parsers.py`](../../backend/app/services/target_scan_parsers.py)) mais **aucun profil
canonique** ne leur correspond :

- **Vagrant** (`vagrant`) — provisioning déclaratif (Vagrantfile), pas de gestion au runtime ; les
  VMs créées seraient gérées via l'hyperviseur sous-jacent. Installation : binaire HashiCorp
  (pas de paquet natif ; AUR/communautaire selon la distribution).
- **Multipass** (`multipass`) — VMs Ubuntu éphémères d'Ubuntu/Canonical.

### C.2 Enums hiérarchiques (`VirtualizationGroup` / `SystemCategory` / `SystemTool`)

Proposition d'enum structuré (groupes → catégories → outils) pour refléter la taxonomie §2 en
code. **Non arbitrée** : general_specs spécifie `list_engines` et le code utilise l'enum plat
`CapabilityType` ([§6.1](#61-enums-réels)). Esquisse :

```python
# ⚠️ Proposition non implémentée — n'existe pas dans le code
class VirtualizationGroup(str, Enum):
    VMS = "vms"
    CONTAINERS = "containers"
    ORCHESTRATION = "orchestration"

class SystemCategory(str, Enum):
    HYPERVISORS = "hypervisors"
    LIBVIRT_MANAGERS = "libvirt_managers"
    SYSTEM_CONTAINERS = "system_containers"
    CONTAINER_ENGINES = "container_engines"
    LOWLEVEL_RUNTIMES = "lowlevel_runtimes"
    OCI_TOOLS = "oci_tools"
    COMPOSE = "compose"
    KUBERNETES = "kubernetes"
    K8S_TOOLS = "k8s_tools"
    # (+ SystemTool : enum détaillé par outil)
```

### C.3 Installation distante d'outils

Architecture d'installateurs (`services/installers/` — recettes par outil, détecteur de
plateforme, orchestrateur multi-étapes) **jamais réalisée**. Principes conservés pour toute
reprise : idempotence, détection conditionnelle, installation versionnée, privilèges minimaux,
vérification post-install, re-scan après installation. Détection de plateforme par famille de
paquets : `/etc/os-release` (`ID`/`ID_LIKE`) → apt (Debian) / dnf-yum (RHEL) / apk (Alpine) /
pacman (Arch) / zypper (openSUSE) — précurseur réel : `_detect_os_release` du scanner
(distribution + version).

Endpoints d'installation proposés jadis sous `/targets/{id}/install*`, reformulés dans le
vocabulaire canonique — **⚠️ non implémenté** :

```
GET    /hosts/{id}/install-suggestions        # moteurs installables (profils × plateforme)
POST   /hosts/{id}/actions/install-engine     # ContextualAction d'installation
GET    /hosts/{id}/actions/{action_id}        # suivi (statut, étapes, erreurs)
POST   /hosts/{id}/actions/verify-engine      # vérification post-install + re-scan
```

*(Cadre : ContextualActions du [ch. 09](../general_specs/09-api.md) ; les verbes de Host —
install package, update OS… — figurent au catalogue des actions Host du [ch. 02](../general_specs/02-familles-workloads.md).)*

### C.4 Plan de mise en œuvre historique

L'ancienne §7 décrivait 6 phases (enums → installateurs → scanners modulaires → services
container → services VM → orchestration). **Jamais exécutées** ; l'architecture cible est
désormais celle des adapters ([ch. 02](../general_specs/02-familles-workloads.md) /
[ch. 05](../general_specs/05-stack-technologique.md)). Toute reprise passe par la
[Roadmap](../Roadmap.md) et le backlog — ce plan n'est plus une référence.

---

## Voir aussi

- [ch. 02 — Familles de workloads](../general_specs/02-familles-workloads.md) — modèle directeur : familles, profils, verbes universels, adapters, arbitrage Kubernetes
- [ch. 03 — Modèle compute](../general_specs/03-modele-compute.md) — discovery/réconciliation, scan des Hosts et Clusters, adoption
- [ch. 04 — Architecture](../general_specs/04-architecture.md) — services core (Machine/Host/Cluster via adapters)
- [ch. 05 — Stack technologique](../general_specs/05-stack-technologique.md) — backends des Machines = adapters, arbitrage Proxmox
- [ch. 19 — Glossaire](../general_specs/19-glossaire.md) — terminologie canonique, arbitrage backends VM (D1), alias interdits
- [WEBSOCKET-REAL-TIME.md](WEBSOCKET-REAL-TIME.md) — canaux temps réel (terminal, console VNC, logs)
- [README.md](README.md) — index du corpus technique et table de correspondance terminologique
- [Roadmap.md](../Roadmap.md) — feuille de route (migration code vers les adapters)
