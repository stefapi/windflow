# Familles de Workloads et WorkloadAdapter — WindFlow

Ce document décrit le **modèle de convergence à trois familles** de WindFlow et l'architecture
en couches qui le rend possible. Il complète [`11-UI-mockups.md`](11-UI-mockups.md) (mockups
d'écrans) et [`12-compute-model.md`](12-compute-model.md) (modèle Compute interne) en posant
le principe directeur : **trois familles distinctes (Apps, Machines, Hosts), une grammaire
UI partagée**.

> Ce document remplace `11b-app-convergence-and-adapters.md`. Le concept d'"App" unique (qui
> englobait tout) est remplacé par trois familles complémentaires, après constat que mélanger
> les concepts service / machine / substrat crée plus de confusion qu'il n'en évite.

---

## 1. Le Principe à Trois Familles

### 1.1 Pourquoi Trois Familles

WindFlow gère trois types d'objets fondamentalement différents dans le modèle mental des
utilisateurs :

| Famille | Identité | Pattern | Durée de vie | Mental model |
|---------|----------|---------|--------------|---------------|
| **Apps** | un service | cattle | courte/moyenne | "je déploie un service" |
| **Machines** | un OS complet | pet | longue (années) | "je gère une machine" |
| **Hosts** | un substrat | infrastructure | très longue | "j'administre un serveur" |

Une convergence totale (à la manière naïve d'Umbrel "tout est une App") fait violence aux
modèles mentaux : un utilisateur qui crée une VM Ubuntu **pense en termes de machine**, pas
en termes de service. Lui présenter sa VM comme une "App" l'oblige à apprendre une
abstraction inverse à la sienne.

À l'inverse, une UI complètement séparée par technologie (à la Proxmox) impose de naviguer
entre des outils qui semblent indépendants alors qu'ils partagent énormément.

**Le compromis WindFlow** : trois familles distinctes au niveau du modèle, mais une grammaire
UI unifiée. Le squelette de page, le pattern Adapter, les menus contextuels, le Mode App /
Mode Infra, la marketplace s'appliquent identiquement aux trois familles.

### 1.2 Définition des Familles

#### Famille Apps — Workloads container-based

Tout ce qui tourne dans un container ou un orchestrateur de containers. Le user pense :
"j'installe un service".

Profils inclus :
- `docker_container` — container Docker/Podman standalone
- `docker_compose` — stack Compose multi-services
- `helm_release` — release Helm sur un cluster Kubernetes
- `k8s_manifest` — manifests YAML appliqués directement

**Pourquoi Kubes et Compose dans la même famille ?** Du point de vue user, "Nextcloud
installé via Compose" et "Nextcloud installé via Helm" produisent le même résultat : un
service qui tourne, accessible par URL, sauvegardable, configurable. La différence
opérationnelle (values vs env, revisions Helm, scale d'un workload) est traitée dans le menu
contextuel `[⋯ Plus]` section "Avancé (Helm)" — exactement le rôle des ContextualActions.

#### Famille Machines — Workloads VM-based

Tout ce qui est une machine virtuelle avec son OS complet. Le user pense : "je crée et je
gère une machine".

Profils inclus :
- `vm_kvm` — VM KVM/QEMU via libvirt
- `vm_lxd` — VM ou system container LXD (en mode VM)
- `vm_incus` — VM ou system container Incus
- `vm_virtualbox` — VM VirtualBox
- `vm_lxc` — system container LXC

**Distinction system container vs container Docker** : un LXC ou un LXD en mode container
système se comporte comme une VM légère (un OS complet, un init system, SSH dedans). Il
appartient à la famille Machines, pas Apps. Un container Docker, lui, n'a qu'un process et
appartient à Apps.

#### Famille Hosts — Substrat d'exécution

Toute machine physique ou virtuelle sur laquelle WindFlow agit pour déployer Apps et
Machines. C'est l'équivalent du "target" en vocabulaire interne. Le user pense : "j'ai un
serveur que j'administre".

Sous-types :
- `host_baremetal` — machine physique sur laquelle WindFlow tourne ou qu'il pilote via SSH
- `host_proxmox` — serveur ou cluster Proxmox VE accessible via son API
- `host_kubernetes` — cluster Kubernetes (k8s, k3s, microk8s) accessible via kubeconfig
- `host_remote_docker` — daemon Docker distant accessible via SSH

Un Host est différent d'une App ou d'une Machine parce qu'il **n'est pas déployé** par
WindFlow — il est **adopté** au moment où il est ajouté comme target. Une fois adopté, on
peut y déployer des Apps et y créer des Machines.

### 1.3 La Hiérarchie

```
                ┌─ Host ──────────────────────────────────┐
                │  Substrat : RPi 4 / nas-server /        │
                │  Proxmox-home / k3s-cluster             │
                │                                          │
                │  Services système (systemd, hôte natif) │
                │  ────────────────────────────────       │
                │  - nginx.service                         │
                │  - postgresql.service                    │
                │  - samba.service                         │
                └────────────┬────────────────────────────┘
                             │ héberge
              ┌──────────────┴────────────────┐
              ▼                                ▼
      ┌─ Apps ──────────────┐         ┌─ Machines ──────────┐
      │  Container-based    │         │  VM-based            │
      │  ─────────────────  │         │  ─────────────────   │
      │  - nextcloud         │         │  - ubuntu-dev        │
      │    (compose)         │         │    (KVM)             │
      │  - monitoring        │         │  - pfsense-router    │
      │    (helm release)    │         │    (KVM)             │
      │  - pihole            │         │  - k3s-node-1        │
      │    (docker container)│         │    (LXC)             │
      └──────────────────────┘         └──────────────────────┘
```

Les services système (systemd sur le Host) sont gérés **dans le détail du Host**, pas dans
une famille à part. Ils peuvent être adoptés comme Apps (avec un profil `app_native_service`
si on veut les faire apparaître dans la liste Apps).

---

## 2. La Grammaire UI Partagée

Bien que les trois familles soient conceptuellement distinctes, elles partagent **rigoureusement
la même grammaire UI**. C'est cette grammaire qui crée la cohérence sans imposer une fausse
unification.

### 2.1 Squelette de Page (Invariant)

Toutes les pages détail (App, Machine, Host) partagent exactement la même structure visuelle :

```
┌─ <Nom> ─────────────────────────────────────────────────┐
│                                                          │
│ [Icône] <Nom> <version>     <Status pill>     [Action P]│  ← HEADER
│ <contexte (URL, IP, target)>                            │
│ <métriques inline : CPU, RAM>                           │
│                                                          │
│ [Action canonique 1] [2] [3] [4] [5]        [⋯ Plus ▾] │  ← ACTION BAR (5 + Plus)
│                                                          │
│ ┌ Aperçu ┬ Tab ┬ Tab ┬ Tab ┬ Tab ┬ Config ┐            │  ← TABS canoniques
│ │                                          │            │
│ │   ...contenu...                          │            │
│ └──────────────────────────────────────────┘            │
└──────────────────────────────────────────────────────────┘
```

Le **squelette est invariant** ; les verbes, les onglets et le contenu varient par famille.

### 2.2 Action Bar Canonique par Famille

Chaque famille a son propre jeu de 5 verbes canoniques :

| Famille | Verbes canoniques |
|---------|-------------------|
| **Apps** | `[🔗 Ouvrir]` `[⏵ Lifecycle ▾]` `[📋 Logs]` `[🖥 Console]` `[⚙ Config]` `[⋯ Plus]` |
| **Machines** | `[🔗 Ouvrir]` `[⏵ Power ▾]` `[📸 Snapshot]` `[🖥 Console VNC]` `[⚙ Hardware]` `[⋯ Plus]` |
| **Hosts** | `[🖥 SSH]` `[📊 Métriques]` `[📋 journalctl]` `[📦 Packages]` `[⚙ Config]` `[⋯ Plus]` |

Le **bouton [⏵]** est un split-button dans les deux premières familles :
- Apps : `Start / Stop / Restart / Pause`
- Machines : `Power on / Power off / Reboot / Reset / Pause / Suspend / Hibernate`

Pour les Hosts, pas de lifecycle universel (un host n'a pas vraiment d'état "off" géré depuis
WindFlow). À la place, l'opération de bas niveau qui équivaut est `Reboot`, accessible dans le
menu `[⋯ Plus]`.

### 2.3 Onglets Canoniques par Famille

Chaque famille a son ensemble d'onglets canoniques, dans un ordre cohérent (Aperçu en premier,
Config en dernier, observabilité au milieu) :

#### Onglets Apps

```
Aperçu | Logs | Console | Métriques | Sauvegardes | Config
```

Plus en Mode Infra :
```
... | Composants techniques | Manifest
```

#### Onglets Machines

```
Aperçu | Console VNC | Métriques | Disques | Réseau | Snapshots | Hardware
```

Plus en Mode Infra :
```
... | Définition libvirt (XML)
```

#### Onglets Hosts

```
Aperçu | Apps déployées | Machines hébergées | Services système | Métriques | Stockage | Réseau | Config
```

Plus en Mode Infra :
```
... | Moteurs installés | Scan & Diagnostics
```

### 2.4 Menus Contextuels (Identique aux trois familles)

Le menu `[⋯ Plus ▾]` est peuplé par l'adapter du profil, avec les **mêmes cinq sections
ordonnées** quelle que soit la famille :

```
[⋯ Plus ▾]
  ┌─────────────────────────────────────┐
  │  ── Cycle de vie ──                 │
  │  ── Configuration ──                │
  │  ── Données ──                      │
  │  ── Avancé (<profil>) ──            │  ← section type-labellée
  │  ── Dangereux ──                    │
  └─────────────────────────────────────┘
```

Le contenu varie par profil. C'est dans la section "Avancé" — et là seulement en Mode App —
que le profil technique du workload fuit.

### 2.5 Pattern Inner Hierarchy (familles composites)

Pour les workloads composites (compose, helm, mixed stack pour Apps ; certaines Machines avec
plusieurs disques ; Hosts qui hébergent plusieurs Apps/Machines), l'onglet `Aperçu` adopte un
**layout 2 colonnes** identique :

```
┌─ Aperçu ─────────────────────────────────────────────┐
│  ┌─ Inventaire ──────┐ ┌─ Détail item sélectionné ─┐│
│  │ Item 1   🟢       │ │ Métadonnées              ││
│  │ Item 2   🟢       │ │                          ││
│  │ Item 3   🟡       │ │ Sous-actions             ││
│  └────────────────────┘ └──────────────────────────┘│
└──────────────────────────────────────────────────────┘
```

Le contenu de la colonne gauche change (services compose, pods helm, snapshots VM, services
systemd d'un host), le squelette reste identique.

---

## 3. Famille Apps

### 3.1 Verbes Universels (Apps)

Sept verbes définissent l'expérience App. Sémantique universelle, implémentation déléguée à
l'adapter du profil.

| Verbe | Sémantique App |
|-------|----------------|
| **Ouvrir** | Accède à l'UI web/interface native de l'App via le navigateur |
| **Démarrer / Arrêter / Redémarrer** | Cycle de vie de l'App entière (tous les services) |
| **Mettre à jour** | Passe l'App à une version plus récente, avec rollback automatique |
| **Sauvegarder** | Snapshot restaurable des données utilisateur (volumes, values, config) |
| **Configurer** | Modifie les paramètres de l'App via formulaire |
| **Logs** | Stream textuel des événements de l'App (agrégé pour les composites) |
| **Console** | Session shell interactive dans le composant principal |

### 3.2 Mapping par Profil App

| Verbe | docker_container | docker_compose | helm_release | k8s_manifest |
|-------|------------------|-----------------|---------------|----------------|
| Ouvrir | URL port mappé | URL via ingress/proxy | URL via ingress | URL via service |
| Start | `docker start` | `compose up -d` | `helm upgrade --reset` | `kubectl scale` ou re-apply |
| Stop | `docker stop` | `compose stop` | scale to 0 | `kubectl scale --replicas=0` |
| Restart | `docker restart` | `compose restart` | `kubectl rollout restart` | `kubectl rollout restart` |
| Update | pull + recreate | pull + redeploy | `helm upgrade` | re-apply |
| Backup | volume snapshot | volumes + DB | values + PV | PV + manifests |
| Configure | env (form) | env + ports (form) | values (form) | manifest values |
| Logs | `docker logs` | `compose logs` | `kubectl logs --all` | `kubectl logs --all` |
| Console | `exec sh` | `exec sh` (service principal) | `exec` pod | `exec` pod |

### 3.3 Hiérarchie de l'AppAdapter

```python
class AppAdapter(WorkloadAdapter):
    """Base pour la famille Apps."""

    @abstractmethod
    async def get_open_url(self) -> str | None: ...

    @abstractmethod
    async def list_services_or_pods(self) -> list[AppComponent]:
        """Composants internes : services Compose, pods Helm, container unique."""
        ...

# Implémentations concrètes
class DockerContainerAdapter(AppAdapter):
    """Profil docker_container — container Docker standalone."""

class ComposeStackAdapter(AppAdapter):
    """Profil docker_compose — stack Compose."""

class HelmReleaseAdapter(AppAdapter):
    """Profil helm_release — release Helm sur Kubernetes."""

class K8sManifestAdapter(AppAdapter):
    """Profil k8s_manifest — manifests YAML appliqués directement."""
```

### 3.4 Catalogue des ContextualActions par Profil App

Voir document précédent pour les détails complets. Synthèse :

| Section | docker_container | docker_compose | helm_release | k8s_manifest |
|---------|------------------|-----------------|---------------|----------------|
| Cycle de vie | force restart, pause | recreate, scale service, restart service | rollout restart, scale workload | rollout restart |
| Configuration | edit env, edit limits | edit env, edit ports, edit compose YAML | edit values (form), edit values.yaml | edit manifests |
| Données | volume snapshot | volumes backup | values + PV backup | PV backup |
| Avancé | commit image, export, inspect | pull images, logs per service | history, rollback, sync chart, helm test | dry-run, diff |
| Dangereux | force remove | down -v --rmi | uninstall --no-hooks | delete --cascade |

---

## 4. Famille Machines

### 4.1 Verbes Universels (Machines)

Six verbes définissent l'expérience Machine. Vocabulaire de **machine**, pas de service.

| Verbe | Sémantique Machine |
|-------|--------------------|
| **Ouvrir** | Accède à la Machine (URL exposée ou Console VNC) |
| **Power on / off / Reboot / Reset** | Cycle de vie matériel de la VM |
| **Snapshot** | Capture l'état complet de la Machine (mémoire + disques) |
| **Console** | Accès graphique VNC/SPICE ou texte série |
| **Hardware** | Modifier les ressources allouées (CPU, RAM, disques, réseau) |
| **Sauvegarder** | Export du disque qcow2 vers un emplacement de backup |

**Différences sémantiques notables avec Apps :**
- `Power off` ≠ `Stop` — une Machine s'arrête comme un PC physique (shutdown ACPI), pas comme
  un service. Le bouton est nommé "Power" et non "Lifecycle".
- `Snapshot` est un verbe canonique (toujours présent) pour les Machines, contextuel
  (dans `[⋯ Plus]`) pour les Apps.
- Pas de verbe `Mettre à jour` universel — une Machine se met à jour de l'intérieur (apt
  upgrade depuis la console) ou par recréation depuis un template plus récent (action dans
  le menu Avancé).

### 4.2 Mapping par Profil Machine

| Verbe | vm_kvm (libvirt) | vm_lxd | vm_incus | vm_lxc | vm_virtualbox |
|-------|------------------|---------|----------|--------|----------------|
| Power on | `virsh start` | `lxc start` | `incus start` | `lxc-start` | `VBoxManage startvm` |
| Power off | `virsh shutdown` | `lxc stop` | `incus stop` | `lxc-stop` | `VBoxManage controlvm acpipowerbutton` |
| Reboot | `virsh reboot` | `lxc restart` | `incus restart` | `lxc-stop && lxc-start` | `VBoxManage controlvm reset` |
| Snapshot | `virsh snapshot-create-as` | `lxc snapshot` | `incus snapshot create` | (limité) | `VBoxManage snapshot take` |
| Console | VNC/SPICE via libvirt | `lxc console` | `incus console` | `lxc-console` | RDP/VRDE |
| Hardware | `virsh edit` (XML) | `lxc config edit` | `incus config edit` | container config | `VBoxManage modifyvm` |
| Backup | qcow2 copy | `lxc export` | `incus export` | tarball rootfs | OVA export |

### 4.3 Hiérarchie de la MachineAdapter

```python
class MachineAdapter(WorkloadAdapter):
    """Base pour la famille Machines."""

    @abstractmethod
    async def power_state(self) -> PowerState:
        """running | stopped | paused | suspended | crashed."""
        ...

    @abstractmethod
    async def list_snapshots(self) -> list[Snapshot]: ...

    @abstractmethod
    async def list_disks(self) -> list[Disk]: ...

    @abstractmethod
    async def list_network_interfaces(self) -> list[NetworkInterface]: ...

    @abstractmethod
    async def open_vnc_console(self) -> VNCHandle:
        """WebSocket pour noVNC."""
        ...

    @abstractmethod
    async def open_serial_console(self) -> ConsoleHandle:
        """WebSocket pour console série (xterm.js)."""
        ...

# Implémentations
class KVMAdapter(MachineAdapter):
    """Profil vm_kvm — KVM/QEMU via libvirt."""

class LXDAdapter(MachineAdapter):
    """Profil vm_lxd — VM ou system container LXD."""

class IncusAdapter(MachineAdapter):
    """Profil vm_incus — VM ou system container Incus."""

class LXCAdapter(MachineAdapter):
    """Profil vm_lxc — system container LXC pur."""

class VirtualBoxAdapter(MachineAdapter):
    """Profil vm_virtualbox — VM VirtualBox."""
```

### 4.4 Catalogue des ContextualActions par Profil Machine

| Section | Contenu (commun à toutes les machines) |
|---------|----------------------------------------|
| Cycle de vie | Force reset (kill), Pause/Resume, Suspend/Resume (hibernate) |
| Configuration | Edit hardware (CPU/RAM/disks), Mount ISO, Add disk, Add NIC, Firmware (BIOS/EFI), Edit native config (XML/yaml) |
| Données | Snapshot now, Restore snapshot…, Browse disks, Backup (export disk) |
| Avancé (<profil>) | Clone, Convert to template, Resize disk, Migrate to another target, Live migration (KVM) |
| Dangereux | Delete VM (with/without disks) |

---

## 5. Famille Hosts

### 5.1 Verbes Universels (Hosts)

Cinq verbes définissent l'expérience Host. Vocabulaire d'**administration**, pas de
déploiement.

| Verbe | Sémantique Host |
|-------|------------------|
| **SSH** | Ouvre une session shell sur le host (équivalent du "Console" pour les autres familles) |
| **Métriques** | Affiche les métriques live (CPU, RAM, disque, réseau, température) |
| **journalctl** | Stream du journal système (logs du host, pas d'une App spécifique) |
| **Packages** | Inventaire et gestion des paquets système (apt, yum, apk) |
| **Configuration** | Réseau, utilisateurs, hostname, fuseau horaire, timezone |

**Différences sémantiques notables avec Apps/Machines :**
- Pas de cycle de vie universel — un Host n'a pas vraiment d'état "running" géré par
  WindFlow. À la place, l'action `Reboot` est dans `[⋯ Plus]`.
- Pas de "Snapshot" universel — un host n'a pas de mécanisme natif de snapshot complet
  (les Hosts Proxmox/k8s peuvent avoir des snapshots, mais c'est spécifique à l'adapter).
- Pas de "Mettre à jour" comme bouton de barre — l'update OS du host est dans `[⋯ Plus]`,
  marqué `danger=True` (peut nécessiter un reboot).

### 5.2 Mapping par Profil Host

| Verbe | host_baremetal (SSH) | host_proxmox | host_kubernetes | host_remote_docker |
|-------|------------------------|---------------|------------------|---------------------|
| SSH | session SSH directe | session SSH au node | kubectl exec sur node ou `kubectl debug` | session SSH au daemon |
| Métriques | parse `/proc`, `node_exporter` | API Proxmox `/nodes/.../status` | `kubectl top nodes` + metrics-server | docker stats agrégé |
| journalctl | `journalctl` via SSH | API Proxmox tasks/syslog | `kubectl logs -n kube-system` | `journalctl` via SSH |
| Packages | apt/yum/apk via SSH | apt sur le node Proxmox | (limité à kubectl get nodes -o wide) | apt via SSH |
| Configuration | edit `/etc/network/...`, hostname | API Proxmox node config | kubeconfig, taints, labels | docker daemon.json |

### 5.3 Hiérarchie de la HostAdapter

```python
class HostAdapter(WorkloadAdapter):
    """Base pour la famille Hosts."""

    @abstractmethod
    async def get_hardware_info(self) -> HardwareInfo:
        """CPU model, architecture, RAM total, disks, network interfaces."""
        ...

    @abstractmethod
    async def list_engines(self) -> list[InstalledEngine]:
        """Moteurs détectés sur le host : Docker, libvirt, Kubernetes, etc.
        Voir VIRTUALIZATION-SYSTEMS.md pour la taxonomie complète."""
        ...

    @abstractmethod
    async def list_apps_hosted(self) -> list[App]:
        """Apps déployées sur ce host."""
        ...

    @abstractmethod
    async def list_machines_hosted(self) -> list[Machine]: ...

    @abstractmethod
    async def list_system_services(self) -> list[SystemService]:
        """Services systemd / openrc / runit / launchd du host."""
        ...

    @abstractmethod
    async def open_ssh(self) -> SSHHandle: ...

    @abstractmethod
    async def get_metrics(self) -> HostMetrics:
        """CPU, RAM, disk, network, température, charge."""
        ...

# Implémentations
class BaremetalHostAdapter(HostAdapter):
    """host_baremetal — machine physique/virtuelle directement accessible (SSH ou local)."""

class ProxmoxHostAdapter(HostAdapter):
    """host_proxmox — serveur Proxmox VE accessible via API."""

class KubernetesHostAdapter(HostAdapter):
    """host_kubernetes — cluster k8s/k3s/microk8s accessible via kubeconfig."""

class RemoteDockerHostAdapter(HostAdapter):
    """host_remote_docker — daemon Docker distant accessible via SSH."""
```

### 5.4 Catalogue des ContextualActions par Profil Host

| Section | Contenu |
|---------|---------|
| Cycle de vie | Reboot (danger), Shutdown (danger), Schedule reboot |
| Configuration | Edit network, Edit users, Edit hostname, Edit SSH config, Set timezone |
| Données | Backup configuration, Export inventory |
| Avancé (<profil>) | Install package, Run command (sudo), Refresh scan, Update OS (danger), View kernel info, Diagnostics |
| Dangereux | Retirer du suivi WindFlow (ne supprime pas le host, juste la connexion) |

### 5.5 Services Système — Mode Adoption

Sur un Host de type `host_baremetal`, les services systemd détectés peuvent être :

- **Listés** dans l'onglet "Services système" du détail Host (toujours visible)
- **Adoptés** comme Apps avec profil spécial `app_native_service`, ce qui les fait apparaître
  dans la liste Apps avec le même traitement que les autres Apps

```python
class NativeServiceAdapter(AppAdapter):
    """Profil app_native_service — service systemd adopté comme App.
    
    Permet de gérer un service installé directement sur le host (sans container)
    comme s'il était une App, avec les mêmes verbes universels."""
```

L'adoption nécessite quelques métadonnées que WindFlow demande à l'utilisateur (icône, nom
affiché, URL d'ouverture si applicable). C'est l'équivalent de l'adoption Discovered →
Managed décrit dans le compute model.

---

## 6. La Hiérarchie Hosts → Apps + Machines

### 6.1 Relation d'Hébergement

Chaque App et chaque Machine est **hébergée par un et un seul Host** à un instant donné. Cette
relation est exposée :

- Dans la card de l'App/Machine : `Sur : nas-server`
- Dans le détail de l'App/Machine : header avec le Host cliquable
- Dans le détail du Host : onglets "Apps déployées" et "Machines hébergées"

### 6.2 Filtres et Vues Croisées

La liste Apps a un filtre `Sur quel Host ?` qui permet de voir uniquement les Apps sur un
host donné. Idem pour la liste Machines.

Inversement, depuis le détail d'un Host, on accède directement aux Apps/Machines hébergées.

### 6.3 Migration entre Hosts

Cas particuliers :
- **Une App docker_container/docker_compose** peut être migrée vers un autre Host Docker
  (export volumes + redéploiement)
- **Une App helm_release** ne se "migre" pas (elle est liée au cluster k8s qui est un Host)
- **Une Machine KVM** peut être migrée vers un autre Host KVM (live migration ou cold
  migration selon la configuration)

Ces opérations apparaissent dans `[⋯ Plus]` section "Avancé".

---

## 7. Les Deux Modes UI Appliqués aux Trois Familles

### 7.1 Sidebar Mode App

```
┌──────────────────────────┐
│  🌀 WindFlow              │
│                          │
│  🏠  Dashboard           │
│                          │
│  ── Workloads ──         │
│  📱  Apps                │  ← Famille Apps
│  🖥️  Machines           │  ← Famille Machines
│  🖧  Hosts               │  ← Famille Hosts
│                          │
│  🏪  Marketplace         │  ← Apps + templates Machines
│  🔌  Plugins             │
│                          │
│  ── Plugins ──           │
│  🌍  Domaines            │
│  📈  Monitoring          │
│  💾  Backups             │
│                          │
│  ⚙️  Settings            │
│                          │
│  ─────────────────────── │
│  [🔧 Mode Infra]         │  ← Toggle
│  🟢 nas-server (x86_64)  │
│  👤 admin                │
└──────────────────────────┘
```

### 7.2 Sidebar Mode Infra

```
┌──────────────────────────┐
│  🌀 WindFlow              │
│                          │
│  🏠  Dashboard           │
│                          │
│  ── Workloads ──         │
│  📱  Apps                │  ← profil révélé dans le header
│  🖥️  Machines           │
│  🖧  Hosts               │
│                          │
│  🏪  Marketplace         │
│  🔌  Plugins             │
│                          │
│  ── Compute (technique) ─│
│  ⚡  Compute             │  ← vue par technologie
│  📚  Stacks              │
│  💾  Volumes             │
│  🌐  Networks            │
│  🖼️  Images              │
│  📸  Snapshots           │
│                          │
│  ⚙️  Settings            │
│  📋  Audit               │
│                          │
│  ─────────────────────── │
│  [📱 Mode App]           │  ← Toggle retour
│  🟢 nas-server (x86_64)  │
│  👤 admin                │
└──────────────────────────┘
```

La vue **Compute** (décrite dans `12-compute-model.md`) reste accessible en Mode Infra ; elle
montre les objets bas-niveau (containers individuels, instances VM, snapshots) **par
technologie** plutôt que par famille. C'est un complément aux trois familles, pas un
remplaçant.

### 7.3 Mode Infra Ciblé (par Workload)

Le toggle `[🔧 Voir les composants techniques]` dans le menu `[⋯ Plus]` d'un workload
bascule **uniquement cette page** en Mode Infra. Disponible pour les trois familles :

- **App** → ajoute onglets "Composants techniques" (workloads K8s, services Compose) et "Manifest"
- **Machine** → ajoute onglet "Définition libvirt (XML)" et révèle l'hyperviseur exact
- **Host** → ajoute onglets "Moteurs installés", "Scan & Diagnostics"

---

## 8. Marketplace

### 8.1 Structure de la Marketplace

La Marketplace propose trois catégories :

```
┌─ Marketplace ────────────────────────────────────────────────┐
│                                                              │
│  [📱 Apps] [🖥️ Machine Templates] [🔌 Plugins]               │
│                                                              │
│  ── Apps ── (onglet sélectionné) ────────────────────────── │
│  Nextcloud, Gitea, Jellyfin, Home Assistant, Plex, ...       │
│  → Le user clique [Installer] → choix automatique du backend │
│                                                              │
│  ── Machine Templates ── (autre onglet) ──────────────────── │
│  Ubuntu 22.04, Debian 12, Alpine 3.19, Home Assistant OS,    │
│  pfSense, OpenWRT, Rocky Linux, Windows Server, ...          │
│  → Le user clique [Créer une Machine] → wizard Machine       │
│                                                              │
│  ── Plugins ── (cf. 09-plugins.md) ──────────────────────── │
│  Traefik, Restic, Uptime Kuma, Trivy, Vault, ...             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 8.2 Apps Multi-Backend

Une entrée App marketplace peut déclarer **plusieurs backends** (cf. §6 du document précédent),
WindFlow choisit le bon selon les Hosts disponibles :

```yaml
name: Nextcloud
category: cloud
backends:
  - profile: docker_compose
    available_for: [host_baremetal_with_docker, host_remote_docker]
    recommended: true
  - profile: helm_release
    available_for: [host_kubernetes]
  - profile: docker_container
    available_for: [host_baremetal_with_docker]
    note: "Configuration minimale, pour tester"
```

### 8.3 Machine Templates

Les templates de Machines sont des **images OS prêtes à l'emploi**, pas des Apps avec
backends multiples :

```yaml
name: Ubuntu 22.04 LTS
category: linux
type: machine_template
image_format: qcow2
size_mb: 580
architecture: [amd64, arm64]
cloud_init: true
default_user: ubuntu
recommended_specs:
  cpu: 2
  ram_mb: 2048
  disk_gb: 20
available_for: [host_baremetal_with_kvm, host_proxmox]
```

Le wizard de création de Machine consomme directement le template choisi.

### 8.4 Plugins

Les plugins sont des extensions de WindFlow (cf. `09-plugins.md`). Ils ne créent ni Apps ni
Machines ni Hosts par eux-mêmes — ils ajoutent des fonctionnalités transversales (Traefik
gère les domaines de toutes les Apps, Restic sauvegarde les volumes de toutes les Apps, etc.).

---

## 9. WorkloadAdapter (Interface Abstraite)

L'interface abstraite est commune aux trois familles, avec des spécialisations par famille.

### 9.1 Base Commune

```python
from abc import ABC, abstractmethod

class WorkloadAdapter(ABC):
    """Base commune aux trois familles."""

    # ─── Identité ─────────────────────────────────
    @abstractmethod
    def family(self) -> WorkloadFamily:
        """APP | MACHINE | HOST"""
        ...

    @abstractmethod
    def profile(self) -> str: ...

    @abstractmethod
    def profile_label(self) -> str: ...

    # ─── Métriques (universel) ────────────────────
    @abstractmethod
    async def get_metrics(self) -> WorkloadMetrics:
        """CPU, RAM, Net, I/O — format unifié."""
        ...

    @abstractmethod
    async def health(self) -> HealthStatus: ...

    # ─── ContextualActions ────────────────────────
    @abstractmethod
    def contextual_actions(self, context: str = "detail") -> list[ContextualAction]: ...

    @abstractmethod
    def child_actions(self, child_kind: str, child_id: str) -> list[ContextualAction]: ...

    # ─── Mode Infra ───────────────────────────────
    @abstractmethod
    async def get_native_config(self) -> NativeConfig:
        """Représentation native : compose YAML, libvirt XML, kubeconfig partiel, ..."""
        ...

    @abstractmethod
    async def get_technical_components(self) -> list[TechnicalComponent]:
        """Sous-composants techniques pour l'onglet Composants en Mode Infra."""
        ...


class WorkloadFamily(str, Enum):
    APP = "app"
    MACHINE = "machine"
    HOST = "host"
```

### 9.2 Spécialisations par Famille

```python
class AppAdapter(WorkloadAdapter):
    """Spécialisation pour la famille Apps — sémantique service."""

    def family(self): return WorkloadFamily.APP

    @abstractmethod
    async def get_open_url(self) -> str | None: ...

    @abstractmethod
    async def start(self) -> ActionResult: ...

    @abstractmethod
    async def stop(self) -> ActionResult: ...

    @abstractmethod
    async def restart(self) -> ActionResult: ...

    @abstractmethod
    async def update(self, target_version: str | None = None) -> UpdateResult: ...

    @abstractmethod
    async def backup(self, destination: str) -> BackupResult: ...

    @abstractmethod
    async def restore(self, backup_id: str) -> RestoreResult: ...

    @abstractmethod
    async def configure(self, values: dict) -> None: ...

    @abstractmethod
    async def stream_logs(self) -> AsyncIterator[LogLine]: ...

    @abstractmethod
    async def open_console(self, component_id: str | None = None) -> ConsoleHandle: ...


class MachineAdapter(WorkloadAdapter):
    """Spécialisation pour la famille Machines — sémantique matériel."""

    def family(self): return WorkloadFamily.MACHINE

    @abstractmethod
    async def get_open_url(self) -> str | None: ...

    @abstractmethod
    async def power_on(self) -> ActionResult: ...

    @abstractmethod
    async def power_off(self, force: bool = False) -> ActionResult: ...

    @abstractmethod
    async def reboot(self, force: bool = False) -> ActionResult: ...

    @abstractmethod
    async def pause(self) -> ActionResult: ...

    @abstractmethod
    async def suspend(self) -> ActionResult: ...

    @abstractmethod
    async def take_snapshot(self, name: str, description: str | None = None) -> Snapshot: ...

    @abstractmethod
    async def restore_snapshot(self, snapshot_id: str) -> ActionResult: ...

    @abstractmethod
    async def get_hardware(self) -> HardwareConfig: ...

    @abstractmethod
    async def set_hardware(self, config: HardwareConfig) -> None: ...

    @abstractmethod
    async def open_vnc(self) -> VNCHandle: ...

    @abstractmethod
    async def open_serial(self) -> ConsoleHandle: ...

    @abstractmethod
    async def backup_disk(self, destination: str) -> BackupResult: ...


class HostAdapter(WorkloadAdapter):
    """Spécialisation pour la famille Hosts — sémantique administration."""

    def family(self): return WorkloadFamily.HOST

    @abstractmethod
    async def open_ssh(self) -> SSHHandle: ...

    @abstractmethod
    async def get_hardware_info(self) -> HardwareInfo: ...

    @abstractmethod
    async def list_engines(self) -> list[InstalledEngine]: ...

    @abstractmethod
    async def list_apps_hosted(self) -> list[App]: ...

    @abstractmethod
    async def list_machines_hosted(self) -> list[Machine]: ...

    @abstractmethod
    async def list_system_services(self) -> list[SystemService]: ...

    @abstractmethod
    async def install_package(self, package: str) -> ActionResult: ...

    @abstractmethod
    async def reboot(self) -> ActionResult: ...

    @abstractmethod
    async def update_os(self) -> UpdateResult: ...

    @abstractmethod
    async def stream_journal(self, unit: str | None = None) -> AsyncIterator[LogLine]: ...
```

---

## 10. Modèle de Données

### 10.1 Entités

```python
class App:
    id: UUID
    name: str
    icon: str
    description: str | None
    profile: AppProfile     # docker_container, docker_compose, helm_release, k8s_manifest, app_native_service
    host_id: UUID           # ← le Host qui l'héberge
    organization_id: UUID
    environment_id: UUID | None
    domain: str | None
    status: AppStatus
    current_version: str | None
    available_version: str | None
    backup_enabled: bool
    last_backup_at: datetime | None
    marketplace_entry_id: UUID | None
    adopted_from_discovered: bool
    created_at: datetime
    updated_at: datetime


class Machine:
    id: UUID
    name: str
    icon: str
    description: str | None
    profile: MachineProfile  # vm_kvm, vm_lxd, vm_incus, vm_lxc, vm_virtualbox
    host_id: UUID            # ← le Host qui l'héberge
    organization_id: UUID
    environment_id: UUID | None
    power_state: PowerState
    hardware: HardwareConfig  # CPU, RAM, disks, NICs
    os_info: OSInfo           # nom, version, architecture
    template_id: UUID | None  # template d'origine
    adopted_from_discovered: bool
    created_at: datetime
    updated_at: datetime


class Host:
    id: UUID
    name: str
    description: str | None
    profile: HostProfile     # host_baremetal, host_proxmox, host_kubernetes, host_remote_docker
    organization_id: UUID
    connection_config: dict  # SSH config, API endpoint, kubeconfig (chiffré)
    hardware_info: HardwareInfo
    installed_engines: list[InstalledEngine]  # Docker, libvirt, k8s, ...
    status: HostStatus       # online | offline | unreachable | scanning
    last_scan_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AppProfile(str, Enum):
    DOCKER_CONTAINER     = "docker_container"
    DOCKER_COMPOSE       = "docker_compose"
    HELM_RELEASE         = "helm_release"
    K8S_MANIFEST         = "k8s_manifest"
    APP_NATIVE_SERVICE   = "app_native_service"  # service systemd adopté

class MachineProfile(str, Enum):
    VM_KVM               = "vm_kvm"
    VM_LXD               = "vm_lxd"
    VM_INCUS             = "vm_incus"
    VM_LXC               = "vm_lxc"
    VM_VIRTUALBOX        = "vm_virtualbox"

class HostProfile(str, Enum):
    HOST_BAREMETAL       = "host_baremetal"
    HOST_PROXMOX         = "host_proxmox"
    HOST_KUBERNETES      = "host_kubernetes"
    HOST_REMOTE_DOCKER   = "host_remote_docker"
```

### 10.2 Statuts Unifiés (par Famille)

Chaque famille a son enum de status, avec des conventions de couleur cohérentes :

```python
class AppStatus(str, Enum):
    RUNNING   = "running"     # 🟢
    STOPPED   = "stopped"     # ⚪
    STARTING  = "starting"    # 🟡
    STOPPING  = "stopping"    # 🟡
    UPDATING  = "updating"    # 🔵
    DEGRADED  = "degraded"    # 🟠
    ERROR     = "error"       # 🔴
    UNKNOWN   = "unknown"     # ⚫

class PowerState(str, Enum):       # Machines
    RUNNING   = "running"     # 🟢
    STOPPED   = "stopped"     # ⚪
    PAUSED    = "paused"      # 🟡
    SUSPENDED = "suspended"   # 🟡
    CRASHED   = "crashed"     # 🔴

class HostStatus(str, Enum):
    ONLINE       = "online"        # 🟢
    OFFLINE      = "offline"       # ⚪
    UNREACHABLE  = "unreachable"   # 🔴
    SCANNING     = "scanning"      # 🔵
```

---

## 11. API REST

L'API expose trois sections principales correspondant aux trois familles, plus la section
Compute en Mode Infra :

```
# Famille Apps (Mode App)
GET    /api/v1/apps
POST   /api/v1/apps
GET    /api/v1/apps/{id}
POST   /api/v1/apps/{id}/start
POST   /api/v1/apps/{id}/stop
POST   /api/v1/apps/{id}/restart
POST   /api/v1/apps/{id}/update
POST   /api/v1/apps/{id}/backup
POST   /api/v1/apps/{id}/restore
PUT    /api/v1/apps/{id}/config
GET    /api/v1/apps/{id}/logs           # WebSocket
GET    /api/v1/apps/{id}/console        # WebSocket
GET    /api/v1/apps/{id}/actions
POST   /api/v1/apps/{id}/actions/{action_id}

# Famille Machines (Mode App)
GET    /api/v1/machines
POST   /api/v1/machines
GET    /api/v1/machines/{id}
POST   /api/v1/machines/{id}/power-on
POST   /api/v1/machines/{id}/power-off
POST   /api/v1/machines/{id}/reboot
POST   /api/v1/machines/{id}/snapshot
POST   /api/v1/machines/{id}/snapshots/{snap_id}/restore
GET    /api/v1/machines/{id}/snapshots
PUT    /api/v1/machines/{id}/hardware
GET    /api/v1/machines/{id}/vnc        # WebSocket noVNC
GET    /api/v1/machines/{id}/serial     # WebSocket xterm
POST   /api/v1/machines/{id}/backup
GET    /api/v1/machines/{id}/actions
POST   /api/v1/machines/{id}/actions/{action_id}

# Famille Hosts
GET    /api/v1/hosts
POST   /api/v1/hosts                    # ajouter un host (target)
GET    /api/v1/hosts/{id}
GET    /api/v1/hosts/{id}/ssh           # WebSocket SSH
GET    /api/v1/hosts/{id}/metrics
GET    /api/v1/hosts/{id}/journal       # WebSocket
GET    /api/v1/hosts/{id}/services      # services systemd
GET    /api/v1/hosts/{id}/apps          # Apps déployées
GET    /api/v1/hosts/{id}/machines      # Machines hébergées
POST   /api/v1/hosts/{id}/actions/{action_id}
POST   /api/v1/hosts/{id}/scan          # rescanner les moteurs

# Mode Infra — vue Compute (cf. 12-compute-model.md)
GET    /api/v1/compute/containers
GET    /api/v1/compute/vms
GET    /api/v1/compute/stacks
GET    /api/v1/compute/snapshots
...
```

---

## 12. Mockups Synthétiques

### 12.1 Liste Apps (Mode App)

```
┌─ Apps ───────────────────────────────────────── [🏪 Marketplace]──────────┐
│  Mes Apps (5)                                       [+ Nouvelle App]      │
│                                                                            │
│  ┌─ ☁️ Nextcloud ──────────────────────────────── 🟢 ─────────────────┐ │
│  │  cloud.example.com  ·  Sur nas-server  ·  342 MB                   │ │
│  │  [🔗 Ouvrir] [📋 Logs] [⚙ Config] [⏸]                          [⋯] │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ 📊 Monitoring ───────────────────────────── 🟢 ──── ⬆ ───────────┐ │
│  │  monitoring.example.com  ·  Sur k3s-cluster  ·  287 MB             │ │
│  │  [🔗 Ouvrir] [📋 Logs] [⚙ Config] [⏸]                          [⋯] │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ 🐙 Gitea ────────────────────────────────── 🟢 ─────────────────┐  │
│  │  git.example.com  ·  Sur nas-server  ·  189 MB                     │ │
│  │  [🔗 Ouvrir] [📋 Logs] [⚙ Config] [⏸]                          [⋯] │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 Liste Machines (Mode App)

```
┌─ Machines ─────────────────────────────── [🏪 Templates]──────────────────┐
│  Mes Machines (3)                                  [+ Nouvelle Machine]   │
│                                                                            │
│  ┌─ 🖥️ ubuntu-dev ──────────────────────────── 🟢 Running ──────────┐  │
│  │  Ubuntu 22.04 · 2 vCPU · 2 GB RAM · 20 GB · Sur nas-server          │ │
│  │  IP: 192.168.1.55 · 12% CPU · 1.8 GB RAM                            │ │
│  │  [🔗 Ouvrir] [⏵ Power ▾] [📸 Snapshot] [🖥 VNC] [⚙ Hardware]  [⋯] │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ 🖥️ pfsense-router ──────────────────────── 🟢 Running ──────────┐  │
│  │  pfSense 2.7 · 1 vCPU · 512 MB · 4 GB · Sur nas-server              │ │
│  │  IP: 192.168.1.1 · 8% CPU · 384 MB RAM                              │ │
│  │  [🔗 Ouvrir] [⏵ Power ▾] [📸 Snapshot] [🖥 VNC] [⚙ Hardware]  [⋯] │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ 🖥️ windows-legacy ───────────────────────── ⚪ Stopped ──────────┐  │
│  │  Windows Server 2019 · 4 vCPU · 8 GB · 80 GB · Sur nas-server      │ │
│  │  Arrêtée depuis 12j · 3 snapshots                                   │ │
│  │  [▶ Power on] [📸 Snapshots] [⚙ Hardware] [🗑]                  [⋯] │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

### 12.3 Liste Hosts (Mode App)

```
┌─ Hosts ────────────────────────────────────────── [+ Ajouter un Host]────┐
│  Mes Hosts (3)                                                            │
│                                                                            │
│  ┌─ 🖧 local (RPi 4) ──────────────────────── 🟢 Online · 15j ────────┐  │
│  │  Raspberry Pi 4 · arm64 · Ubuntu 22.04                              │ │
│  │  CPU 38% · RAM 1.2/4 GB · Disque 28/64 GB · 🌡 52°C                │ │
│  │  Moteurs : 🐳 Docker  ✗ libvirt  ✗ k8s                              │ │
│  │  Héberge : 3 Apps · 0 Machines                                       │ │
│  │  [🖥 SSH] [📊 Métriques] [📋 journalctl]                         [⋯] │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ 🖧 nas-server ─────────────────────────── 🟢 Online · 47j ────────┐  │
│  │  Mini PC x86_64 · Ubuntu 22.04                                      │ │
│  │  CPU 12% · RAM 4.8/16 GB · Disque 1.2/4 TB                          │ │
│  │  Moteurs : 🐳 Docker  ✅ libvirt  ✗ k8s                             │ │
│  │  Héberge : 5 Apps · 2 Machines                                       │ │
│  │  [🖥 SSH] [📊 Métriques] [📋 journalctl]                         [⋯] │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ 🖧 k3s-cluster ──────────────────────────── 🟢 Online · 3 nodes ──┐  │
│  │  Kubernetes (k3s v1.28.5) · 3 nodes amd64                           │ │
│  │  Total : CPU 22% · RAM 8.4/24 GB · 23 pods · 4 namespaces           │ │
│  │  Moteurs : ✗ Docker (containerd)  ✗ libvirt  ✅ k3s                 │ │
│  │  Héberge : 2 Apps · 0 Machines                                       │ │
│  │  [🖥 kubectl] [📊 Métriques] [📋 events]                          [⋯] │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

### 12.4 Détail Host — Onglets typiques

```
┌─ Détail Host : nas-server ───────────────────────────────────────────────┐
│                                                                          │
│  🖧 nas-server               🟢 Online (uptime 47j)         [🖥 SSH]    │
│  Mini PC x86_64 · Ubuntu 22.04 · 16 GB RAM · 4 TB disque                │
│                                                                          │
│  [🖥 SSH] [📊 Métriques] [📋 journalctl] [📦 Packages] [⚙ Config] [⋯] │
│                                                                          │
│  ┌Aperçu┬Apps déployées┬Machines hébergées┬Services système┬Métriques┐ │
│  │       ┴Stockage┬Réseau┬Config                                       │ │
│  │                                                                     │ │
│  │  ── Aperçu (actif) ──                                              │ │
│  │  Hardware, OS, uptime, charges agrégées, moteurs installés         │ │
│  │  Cartes d'aperçu : 5 Apps, 2 Machines, 8 services système          │ │
│  │                                                                     │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 13. Roadmap d'Implémentation

### Phase 1 — Modèles de données et adapters de base

- Définir `App`, `Machine`, `Host` en base
- Implémenter `WorkloadAdapter` ABC et ses 3 spécialisations
- Implémenter `DockerContainerAdapter`, `ComposeStackAdapter`, `BaremetalHostAdapter`,
  `KVMAdapter` (les 4 plus représentatifs)
- Tests unitaires des contrats sémantiques

### Phase 2 — UI Mode App pour les 3 familles

- Sidebar avec sections `📱 Apps`, `🖥️ Machines`, `🖧 Hosts`
- Listes pour chacune avec actions universelles
- Pages détail avec onglets canoniques par famille
- Marketplace avec 3 onglets (Apps / Templates / Plugins)
- Menus contextuels `[⋯ Plus]` peuplés par adapter

### Phase 3 — Adapters supplémentaires

- Family Apps : `HelmReleaseAdapter`, `K8sManifestAdapter`, `NativeServiceAdapter`
- Family Machines : `LXDAdapter`, `IncusAdapter`, `LXCAdapter`, `VirtualBoxAdapter`
- Family Hosts : `ProxmoxHostAdapter`, `KubernetesHostAdapter`, `RemoteDockerHostAdapter`

### Phase 4 — Mode Infra

- Toggle Mode App / Mode Infra
- Mode Infra ciblé (par workload)
- Onglets supplémentaires (Composants techniques, Manifest)
- Vue Compute (cf. `12-compute-model.md`)

### Phase 5 — Affinements et adoption

- Wizard d'adoption Discovered → Managed (par famille)
- Migration de workloads entre Hosts
- Cas spéciaux : stack mixte (App + Machine liées par dépendance)

---

## 14. Glossaire

| Terme | Définition |
|-------|------------|
| **Workload** | Terme générique pour App, Machine ou Host |
| **App** | Workload container-based (Docker, Compose, Helm, K8s manifest, service systemd adopté) |
| **Machine** | Workload VM-based (KVM, LXD, Incus, LXC, VirtualBox) |
| **Host** | Substrat d'exécution (machine physique/virtuelle ou cluster) qui héberge Apps et Machines |
| **Famille** | App, Machine ou Host — les trois familles distinctes du modèle |
| **Profil** | Sous-type technique d'un workload (ex: `docker_compose`, `vm_kvm`, `host_proxmox`) |
| **Adapter** | Code qui traduit les verbes universels en opérations natives pour un profil |
| **Verbes universels** | Actions exposées dans l'UI Mode App, spécifiques à chaque famille |
| **ContextualAction** | Action spécifique au profil, exposée dans `[⋯ Plus]` |
| **Mode App** | UI par défaut, Umbrel-style, vocabulaire convergent par famille |
| **Mode Infra** | UI augmentée, Harvester-light, profil et composants techniques révélés |
| **Mode Infra ciblé** | Mode Infra activé pour une seule workload, sans toggle global |

---

**Références croisées :**

- [`01-overview.md`](01-overview.md) — Vision et positionnement de WindFlow
- [`02-architecture.md`](02-architecture.md) — Architecture globale (à enrichir avec les trois familles)
- [`04-data-model.md`](04-data-model.md) — Modèle de données (à enrichir avec `App`, `Machine`, `Host` distincts)
- [`06-rbac-permissions.md`](06-rbac-permissions.md) — RBAC appliqué par famille
- [`07-api-design.md`](07-api-design.md) — APIs REST par famille
- [`09-plugins.md`](09-plugins.md) — Plugins (transversaux aux familles)
- [`10-core-features.md`](10-core-features.md) — Fonctionnalités principales
- [`11-UI-mockups.md`](11-UI-mockups.md) — Mockups détaillés (révisés pour les trois familles)
- [`12-compute-model.md`](12-compute-model.md) — Modèle Compute (vue Mode Infra par technologie)
- [`VIRTUALIZATION-SYSTEMS.md`](../VIRTUALIZATION-SYSTEMS.md) — Couche Engine (services par moteur)
