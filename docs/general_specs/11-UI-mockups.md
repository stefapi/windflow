# Propositions de Maquettes d'Écran - WindFlow

> **À lire en premier** : [`11b-workload-families-and-adapters.md`](11b-workload-families-and-adapters.md)
> pose le modèle directeur de l'UI : **trois familles distinctes — Apps, Machines, Hosts —
> partageant une grammaire UI commune**. Les Apps regroupent les workloads container-based
> (Docker, Compose, Helm, K8s manifests). Les Machines regroupent les workloads VM-based
> (KVM, LXD, Incus, LXC, VirtualBox). Les Hosts sont le substrat (machines physiques/virtuelles
> et clusters) qui hébergent Apps et Machines.
>
> Les mockups ci-dessous se concentrent principalement sur la famille Apps (cas le plus
> représentatif), mais le même squelette UI s'applique aux Machines et aux Hosts avec leur
> vocabulaire propre. Les termes "Mode Standard" et "Mode Avancé" employés dans ce document
> correspondent à **Mode App** et **Mode Infra**.

## Analyse Approfondie de l'Existant

### Panorama des Interfaces Étudiées

L'analyse couvre 18+ outils répartis en 4 familles :

**Homeserver / App Stores** : Umbrel, Runtipi, CasaOS, Cosmos Server, YunoHost, FreedomBox
**PaaS / Déploiement** : Coolify, Cloudron, CapRover
**Infra / VMs** : Proxmox VE, vSphere, Scaleway Console
**Infra unifiée (Containers + VMs)** : Proxmox VE, Incus/LXD, Harvester (SUSE)

### Leçons Tirées par Outil

#### Umbrel — La Référence UX

L'interface la plus soignée du marché self-hosted. Design inspiré d'iOS : grille d'apps sur fond de wallpaper personnalisable, dock fixe en bas (Home, App Store, Settings, Activity, Widgets), effets de verre dépoli.

**Ce qu'on prend :**
- Le concept de "homepage personnalisable" avec widgets repositionnables
- L'App Store avec fiches détaillées et bouton "Install" unique
- Le système de widgets (jusqu'à 3) sur le dashboard pour un résumé rapide
- L'onboarding ultra-simplifié (wizard première installation)

**Ce qu'on adapte :**
- Umbrel cache toute la complexité Docker — WindFlow doit la montrer (c'est un outil d'infra, pas un OS grand public)
- Pas de gestion de VMs ni de multi-machine chez Umbrel — WindFlow doit intégrer ça dans la même fluidité

#### Runtipi — L'App Store Pragmatique

Interface propre et moderne avec un dashboard minimaliste (CPU, RAM, disque), une liste d'apps installées avec statut, et un app store avec ~300 apps.

**Ce qu'on prend :**
- La page "My Apps" avec statut inline (running/stopped), boutons d'action (start, stop, settings, open, uninstall), et badge de mise à jour disponible
- Le concept d'app stores multiples (officiel + communautaire)
- Le backup/restore par app avant mise à jour
- La modification du docker-compose par app (advanced settings)

**Ce qu'on adapte :**
- Runtipi ne gère que des apps Docker — WindFlow ajoute les VMs et les plugins fonctionnels (extensions API/UI)

#### Cosmos Server — La Sécurité Intégrée

Unique par son approche "security-first" : reverse proxy intégré, SmartShield (anti-bot/DDoS), SSO natif, monitoring built-in.

**Ce qu'on prend :**
- Le concept de "Server Apps" : tout container Docker exposé devient une "app" avec sa propre URL, son certificat TLS, et ses règles de sécurité — le tout configurable depuis l'UI
- Le monitoring et les alertes intégrés sans plugin séparé (mais dans WindFlow ce sera un plugin léger)
- Le menu hamburger qui bascule entre mode simple et mode admin (évite de surcharger l'UI pour les non-admins)
- Le storage manager intégré (gestion des disques, mounts, parity)

**Ce qu'on adapte :**
- Cosmos est monolithique (reverse proxy + auth + container manager en un bloc) — WindFlow sépare ça en core + plugins
- Le marketplace de Cosmos est moins riche — WindFlow vise un registre ouvert avec contribution communautaire

#### CasaOS — L'Expérience Grand Public

Interface la plus simple du lot : homepage type bureau de smartphone, cards frosted glass, app store catégorisé, file manager intégré.

**Ce qu'on prend :**
- Le file manager intégré avec preview de fichiers (essentiel pour le volume browser)
- Les cards d'apps avec port affiché et bouton "Open" direct
- L'import de containers Docker existants (pas seulement ceux installés via le store)
- Le gestionnaire de stockage avec visualisation de l'espace disque

**Ce qu'on évite :**
- Trop simpliste pour un outil d'infra — pas de terminal, pas de compose editor, pas de VMs
- Pas de multi-machine

#### Coolify — Le PaaS Self-Hosted

Orienté déploiement depuis Git (comme Heroku). Dashboard par projet, gestion de serveurs multiples, déploiement auto.

**Ce qu'on prend :**
- La vue multi-serveurs avec métriques par serveur (CPU, RAM, disque, nombre de containers)
- Le déploiement depuis Git avec preview des logs en temps réel
- La notion de "Resources" qui unifie apps, databases, et services sous un même serveur

**Problèmes UX qu'on évite :**
- Le dashboard est quasiment vide et ne sert à rien (juste un compteur de projets)
- Il faut 3 clics pour arriver à la config d'un service (Project → Environment → Resource)
- Pas d'actions rapides depuis les listes

#### Cloudron — L'App Store Mature

Le plus abouti en termes de gestion d'apps : installation one-click, gestion domaines, TLS automatique, mises à jour automatiques, backup intégré par app.

**Ce qu'on prend :**
- Le tableau de bord "Apps" avec icône, nom, domaine attribué, statut, et actions (configure, backup, restart, logs, terminal)
- La gestion des domaines directement liée aux apps (chaque app a son sous-domaine)
- Le système de backup par app (pas juste un backup global)
- La page "Activity" (journal d'audit) avec filtres

**Ce qu'on adapte :**
- Cloudron est payant au-delà de 2 apps gratuites — WindFlow est entièrement open source
- Pas de VMs ni de gestion d'infra au-delà de Docker

#### Proxmox VE — La Gestion de VMs

Interface technique avec arbre de navigation latéral (Datacenter → Node → VM/CT), onglets par ressource (Summary, Console, Hardware, Snapshots, Backup, Firewall).

**Ce qu'on prend :**
- L'arbre de navigation pour la hiérarchie targets → ressources
- La console VNC/SPICE intégrée dans un onglet de l'interface web
- Les onglets de détail par VM (Summary, Hardware, Snapshots, Backup, Network)
- Le summary du node avec graphiques CPU/RAM/réseau en temps réel

**Ce qu'on adapte :**
- L'UI Proxmox est datée (ExtJS 2010) — WindFlow utilise un design moderne
- Proxmox ne gère pas Docker ni les app stores

#### vSphere / Scaleway — L'Infra Cloud

vSphere : interface enterprise avec vue inventaire, performance charts, vMotion. Scaleway Console : design cloud moderne, sidebar fixe, création d'instances via wizard étape par étape.

**Ce qu'on prend :**
- Le wizard de création de VM/instance par étapes (Scaleway : choisir l'image → configurer → réseau → créer)
- Les métriques de performance avec graphiques temporels (vSphere)
- La vue inventaire avec filtres et recherche rapide

#### CapRover — Le PaaS Simple

Interface minimaliste : liste d'apps, one-click apps, déploiement via Git ou image Docker, gestion de domaines.

**Ce qu'on prend :**
- La simplicité de la page "One-Click Apps" : recherche + grille d'apps + install
- Le concept de "App Configs" modifiable post-installation (env vars, ports, volumes)

#### Proxmox VE — La Convergence VMs + LXC

Proxmox est le seul outil du marché qui gère VMs (KVM) et containers système (LXC) dans une interface unifiée. L'arbre de navigation (Datacenter → Node → VM/CT) traite les deux types comme des "guests" avec les mêmes onglets : Summary, Console, Resources, Network, Snapshots.

**Ce qu'on prend pour la convergence :**
- Le pattern "Instance" unique : VMs et LXC partagent la même arborescence, les mêmes actions (Start/Stop/Reboot/Snapshot/Console), le type n'est qu'un attribut
- Les onglets identiques par instance (Summary, Console, Snapshots, Network, Storage) — le contenu s'adapte au type mais la structure reste la même
- La vue Datacenter qui agrège tous les nodes avec leurs instances respectives
- Les colonnes Status/Name/Type/CPU/RAM identiques dans la liste des guests

**Ce qu'on adapte :**
- Proxmox LXC ≠ Docker container — WindFlow gère Docker/Podman containers ET KVM/LXD VMs, mais le principe de convergence est identique
- L'UI Proxmox est datée (ExtJS) — WindFlow applique ce pattern de convergence avec un design moderne

#### Incus / LXD — L'Unification Totale par Canonique

Incus (fork communautaire de LXD) est la référence absolue en matière de convergence container/VM. La CLI `incus list` affiche containers et VMs dans la même table, avec les mêmes colonnes. Les commandes sont identiques : `incus start`, `incus stop`, `incus snapshot`, `incus exec` fonctionnent pour les deux types.

**Ce qu'on prend pour la convergence :**
- Le principe fondamental : **le type (container vs VM) est une colonne, pas un paradigme** — tout objet Compute est une "Instance"
- Les actions convergentes : Start, Stop, Restart, Snapshot, Console, Exec — mêmes commandes, comportement adapté au type
- `incus exec` pour containers (shell direct) et `incus console` pour VMs (VNC) — WindFlow applique le même pattern : Terminal pour containers, Console VNC pour VMs, mais le bouton "Console" est le même
- La table unifiée avec colonne TYPE qui permet le filtrage tout en gardant la vue globale

**Ce qu'on adapte :**
- Incus ne gère pas Docker/Podman — WindFlow ajoute les containers Docker à ce modèle convergent
- Incus n'a pas de marketplace — WindFlow ajoute l'App Store au-dessus de cette couche Compute unifiée

#### Harvester (SUSE) — Le Cloud Natif Unifié

Harvester est un hyperviseur open-source construit sur Kubernetes qui gère VMs et workloads containers dans la même interface Rancher. Chaque VM est un objet K8s (VirtualMachineInstance), les containers sont des Pods, et l'UI Rancher unifie les deux.

**Ce qu'on prend pour la convergence :**
- Le concept d'"Instance" comme abstraction commune au-dessus des technologies
- La même interface pour provisionner une VM ou un container — le wizard est identique, seul le choix initial du type diffère
- Les métriques unifiées : même format de CPU/RAM/Réseau pour tous les types d'instances

---

## Principes UX Révisés

### 1. Trois Familles, Une Grammaire UI — Le Principe Fondateur

Inspiré d'**Umbrel** (ergonomie centrée App pour la famille Apps), de **Proxmox VE** (séparation
nette VMs / containers / hosts avec UX cohérente) et de **Harvester/Incus** (convergence
applicable au sein d'une famille). Détaillé dans
[`11b-workload-families-and-adapters.md`](11b-workload-families-and-adapters.md).

WindFlow distingue **trois familles de workloads** au niveau du modèle mental, mais leur
applique une **grammaire UI commune** au niveau de la présentation :

| Famille | Workloads inclus | Mental model |
|---------|--------------------|---------------|
| **Apps** | Docker container, Compose, Helm release, K8s manifest, service systemd adopté | "je déploie un service" |
| **Machines** | VM KVM, LXD, Incus, LXC, VirtualBox | "je crée et je gère une machine" |
| **Hosts** | Machine physique (SSH), serveur Proxmox, cluster k8s, daemon Docker distant | "j'administre un serveur" |

**Pourquoi trois familles plutôt qu'une seule abstraction "App" ?** Les modèles mentaux sont
trop différents pour être unifiés sans mensonge. Le user qui crée une VM Ubuntu pense en
termes de machine (CPU, RAM, disque, console VNC, snapshot, longue durée de vie). Le user
qui installe Nextcloud pense en termes de service (URL, configuration, redéploiement
facile). Forcer les deux dans le même bucket les oblige à apprendre une abstraction inverse.

**Pourquoi grouper Kubes avec Docker/Compose ?** Du point de vue user, "Nextcloud installé
via Compose" et "Nextcloud installé via Helm" produisent le même résultat : un service qui
tourne. La différence opérationnelle (values vs env, history Helm, scale workload) est
absorbée par le menu contextuel `[⋯ Plus]` section "Avancé (Helm)".

**Règles de convergence (au sein d'une famille) :**
- Le vocabulaire UI est universel pour la famille ; les implémentations natives sont
  déléguées à un **WorkloadAdapter** par profil.
- Une action universelle est **toujours présente** dans la barre d'action, même si l'adapter
  retourne `NotApplicable` (auquel cas le bouton est grisé avec un tooltip explicatif).
- Les actions spécifiques à un profil vivent dans le **menu contextuel `[⋯ Plus ▾]`**, peuplé
  par l'adapter. C'est là — et là seulement en Mode App — que le profil technique fuit.

**Règles de grammaire commune (entre familles) :**
- Squelette de page identique : header + barre d'action + onglets canoniques + tab content
- Pattern d'inner hierarchy identique (colonne gauche = inventaire, colonne droite = détail)
- Système de status et métriques uniforme (mêmes couleurs, mêmes formats)
- Marketplace structurée en trois sections (Apps / Machine Templates / Plugins)
- Mode App / Mode Infra appliqué identiquement aux trois familles

**Matrice de convergence des actions :**

| Action | Container | VM | Pod K8s | Bouton UI |
|--------|-----------|-----|---------|-----------|
| Démarrer / Arrêter / Redémarrer | ✅ | ✅ | ✅ | `[▶ Start]` `[⏸ Stop]` `[🔄 Restart]` |
| Console (Terminal ou VNC) | ✅ Terminal | ✅ VNC/SPICE | ✅ Terminal | `[🖥 Console]` |
| Logs | ✅ stdout/stderr | ✅ Serial console | ✅ kubectl logs | `[📋 Logs]` |
| Métriques live | ✅ CPU/RAM/Net | ✅ CPU/RAM/Net | ✅ CPU/RAM/Net | Onglet Metrics |
| Snapshots | ✅ (image commit) | ✅ (qcow2 COW) | ❌ | `[📸 Snapshot]` |
| Stockage | ✅ Volumes Docker | ✅ Disques VM | ✅ PVC | Onglet Storage |
| Réseau | ✅ Docker network | ✅ Bridge/VLAN | ✅ Service | Onglet Network |
| Configuration | ✅ Env vars + Labels | ✅ Hardware (CPU/RAM) | ✅ ConfigMap | `[⚙ Config]` |

### 2. Deux Modes d'Interface : Mode App et Mode Infra

Inspiré de Cosmos Server (mode simple vs admin) et Proxmox (vue simple vs vue complète),
mais formalisé comme deux **niveaux de vocabulaire**, pas seulement de densité :

**Mode App** (Umbrel-style, par défaut) : aucune apparition des mots "container", "compose",
"helm", "VM", "namespace", "pod" en dehors du menu contextuel `[⋯ Plus]` section "Avancé".
Écrans : Dashboard, Apps, Marketplace, Backups, Settings. Suffisant pour 80% des
utilisateurs.

**Mode Infra** (Harvester-light, opt-in) : la même expérience App, **augmentée**. Le profil
de chaque App est révélé dans son header, deux onglets supplémentaires apparaissent
(`Composants techniques`, `Manifest`), et la vue Compute détaillée devient accessible dans
la sidebar (cf. `12-compute-model.md`).

Le toggle est dans la sidebar (bouton discret en bas). Le mode est mémorisé par utilisateur.
Les Viewers sont forcés en Mode App. Un **Mode Infra ciblé** existe aussi : depuis le menu
`[⋯ Plus]` d'une App, l'action `[🔧 Voir les composants techniques]` bascule cette **page
seulement** en Mode Infra sans activer le toggle global.

### 3. "Workload" (App / Machine / Host) comme Vocabulaire Central

Tout ce qui est déployé ou administré apparaît comme un **Workload** appartenant à l'une des
trois familles. Le vocabulaire user adopté :
- **App** : pour les workloads container-based (cf. famille Apps)
- **Machine** : pour les workloads VM-based (cf. famille Machines)
- **Host** : pour le substrat (cf. famille Hosts)

Le terme "Workload" est interne (modèle de données, doc d'architecture) ; l'utilisateur en
Mode App ne le voit jamais — il manipule directement des Apps, des Machines, ou des Hosts.

En Mode Infra uniquement, la section Compute (cf. `12-compute-model.md`) offre une vue
complémentaire **par technologie** (containers individuels, instances VM, snapshots) destinée
aux opérations de bas niveau. Cette vue agrège les Workloads transversalement à leur famille.

Les actions convergent **au sein d'une famille** mais peuvent différer entre familles :
- Famille Apps : `[🖥 Console]` → Terminal xterm.js (container, pod, sub-shell compose)
- Famille Machines : `[🖥 Console VNC]` → graphique noVNC, ou série pour serveurs sans GPU
- Famille Hosts : `[🖥 SSH]` → session SSH directe vers le host

Le bouton est positionné au même endroit dans la barre d'action des trois familles, ce qui
crée la cohérence visuelle. Mais sa nature s'adapte au contexte — c'est exactement le compromis
qui permet aux modèles mentaux de cohabiter sans se contredire.

### 4. Dashboard Type "Homepage"

Inspiré d'Umbrel (wallpaper + widgets) mais avec la densité d'information de Runtipi (métriques système + instances running). Le dashboard est le point d'entrée unique, personnalisable avec des widgets ajoutés par les plugins.

### 5. Marketplace-First par Famille, puis Wizard

Inspiré de Cloudron, Umbrel et Runtipi : le point d'entrée naturel pour créer une App est la
**Marketplace** (onglet Apps), pour une Machine la **Marketplace** (onglet Machine Templates),
pour un Host le bouton dédié `[+ Ajouter un Host]` (pas de marketplace, on adopte un substrat
existant). Détaillé dans
[`11b-workload-families-and-adapters.md`](11b-workload-families-and-adapters.md) §8.

L'entrée marketplace d'une App déclare un ou plusieurs **backends** (compose, helm, container
standalone) ; WindFlow choisit le backend recommandé selon les Hosts disponibles et propose
un mini-wizard de 2-3 questions (Host cible, domaine, config minimale).

Pour les besoins explicites — déployer un compose à soi, importer un chart, créer une VM
nue — un bouton `[+ Importer]` ou `[+ Créer manuellement]` complète la marketplace et passe
par un wizard plus complet. Le wizard de création manuelle (Écran 11b) reste disponible en
Mode Infra pour les power-users qui savent exactement ce qu'ils veulent.

### 6. Actions sans Navigation

Inspiré de Portainer, Runtipi et Proxmox : les actions courantes (start, stop, restart, console, logs, snapshot) sont accessibles **directement depuis les listes**, sans ouvrir le détail. Ces actions sont **les mêmes** pour les containers et les VMs. Le détail existe pour la configuration et le troubleshooting.

---

## Navigation Révisée

### Sidebar — Mode App (par défaut)

```
┌──────────────────────────┐
│  🌀 WindFlow              │
│                          │
│  🏠  Dashboard           │  ← Homepage personnalisable
│                          │
│  ── Workloads ──         │
│  📱  Apps                │  ← Famille container-based (Docker, Compose, Helm, K8s)
│  🖥️  Machines           │  ← Famille VM-based (KVM, LXD, Incus, LXC, VirtualBox)
│  🖧  Hosts               │  ← Substrat : machines physiques, Proxmox, k8s
│                          │
│  🏪  Marketplace         │  ← Apps + Templates Machines + Plugins
│  🔌  Plugins             │
│                          │
│  ── Plugins ──           │  ← Ajouté dynamiquement par les plugins
│  🌍  Domaines            │  ← (Plugin Traefik)
│  📈  Monitoring          │  ← (Plugin Uptime Kuma)
│  💾  Backups             │  ← (Plugin Restic)
│  🤖  Assistant IA        │  ← (Plugin Ollama/LiteLLM)
│                          │
│  ⚙️  Settings            │
│                          │
│  ─────────────────────── │
│  [🔧 Mode Infra]         │  ← Toggle pour basculer en Mode Infra
│  🟢 local (arm64)        │
│  👤 admin                │
└──────────────────────────┘
```

### Sidebar — Mode Infra (toggle activé)

```
┌──────────────────────────┐
│  🌀 WindFlow              │
│                          │
│  🏠  Dashboard           │
│                          │
│  ── Workloads ──         │
│  📱  Apps                │  ← profil révélé dans le header de chaque App
│  🖥️  Machines           │
│  🖧  Hosts               │
│                          │
│  🏪  Marketplace         │
│  🔌  Plugins             │
│                          │
│  ── Compute (technique) ─│  ← Visible en Mode Infra uniquement (cf. 12-compute-model.md)
│  ⚡  Compute             │  ← Vue par technologie : containers + VMs agrégés multi-hosts
│  📚  Stacks              │  ← Stacks WindFlow (compose, helm, mixtes)
│  💾  Stockage            │  ← Volumes Docker + disques VM + file browser
│  🌐  Réseaux             │  ← Networks Docker + bridges VM
│  🖼️  Images              │  ← Images Docker + ISOs / templates VM
│  📸  Snapshots           │  ← Snapshots VM (vue centralisée multi-hosts)
│                          │
│  ── Plugins ──           │
│  🌍  Domaines            │
│  📈  Monitoring          │
│  💾  Backups             │
│  🤖  Assistant IA        │
│                          │
│  ADMINISTRATION          │
│  ⚙️  Settings            │
│  📋  Audit               │
│                          │
│  ─────────────────────── │
│  [📱 Mode App]           │  ← Toggle retour
│  🟢 local (arm64)        │
│  👤 admin                │
└──────────────────────────┘
```

**Rationale** : Un self-hoster débutant qui veut juste installer Nextcloud et Jellyfin ne devrait jamais voir "Containers", "Networks", ou "Images". Un admin qui veut debug un container qui crashe a besoin de tout. Le Mode App reste honnête sur les problèmes (statut `degraded`, badge `⚠`) sans forcer la connaissance technique ; le passage en Mode Infra (global ou ciblé) ouvre l'accès au détail.

---

## Écran 1 : Dashboard (Homepage)

Inspiré d'Umbrel (widgets personnalisables) + Runtipi (métriques système) + Cosmos (monitoring intégré).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Sidebar │                                                                   │
│         │  Bonjour admin 👋             🎯 local (arm64)  🔔 2 notifications│
│         │                                                                   │
│         │  ┌─ Système ──────────────────────────────────────────────────┐   │
│         │  │ CPU ████░░░░░░ 38%   RAM ██████░░░░ 1.2/4 GB             │   │
│         │  │ Disque █████████░ 28/64 GB   Uptime: 15j 3h              │   │
│         │  │ 🟢 12 instances running (10 containers · 2 VMs) · 🔌 3 plugins actifs │   │
│         │  └────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         │  ┌─ Apps ─────────────────────────────────────────────────────┐   │
│         │  │                                                            │   │
│         │  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │   │
│         │  │  │  ☁️     │ │  🐙    │ │  🎬    │ │  🐘    │ │  🔴    │  │   │
│         │  │  │Nextcloud│ │ Gitea  │ │Jellyfin│ │Postgres│ │ Redis  │  │   │
│         │  │  │  🟢 UP  │ │ 🟢 UP  │ │ 🟢 UP  │ │ 🟢 UP  │ │ 🟢 UP  │  │   │
│         │  │  │ :8080   │ │ :3000  │ │ :8096  │ │ :5432  │ │ :6379  │  │   │
│         │  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘  │   │
│         │  │                                                            │   │
│         │  │  cloud.example.com  git.example.com  media.example.com     │   │
│         │  │  (Traefik ✓)        (Traefik ✓)      (Traefik ✓)          │   │
│         │  └────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         │  ┌─ Widgets ──────────────────────────────────────────────────┐   │
│         │  │                                                            │   │
│         │  │  ┌─ Uptime Kuma ─────┐  ┌─ Traefik ─────────────────┐    │   │
│         │  │  │  ✅ 5/5 services  │  │  🌍 3 domaines actifs     │    │   │
│         │  │  │  UP depuis 15j    │  │  🔒 3 certificats valides │    │   │
│         │  │  │                   │  │  📊 1.2K req/h            │    │   │
│         │  │  │  nextcloud ✅ 99% │  └───────────────────────────┘    │   │
│         │  │  │  gitea     ✅ 99% │                                   │   │
│         │  │  │  jellyfin  ✅ 99% │  ┌─ Restic ──────────────────┐    │   │
│         │  │  └───────────────────┘  │  ✅ Dernier backup: 6h    │    │   │
│         │  │                         │  📦 3 volumes, 2.1 GB     │    │   │
│         │  │  ┌─ Dernière activité ┐ │  Prochain: dans 18h       │    │   │
│         │  │  │ ✅ Nextcloud mis   │ └───────────────────────────┘    │   │
│         │  │  │   à jour (2h)      │                                  │   │
│         │  │  │ ✅ Backup terminé  │                                  │   │
│         │  │  │   (6h)             │                                  │   │
│         │  │  │ 🔔 Certificat     │                                  │   │
│         │  │  │   expire dans 30j  │                                  │   │
│         │  │  └────────────────────┘                                  │   │
│         │  └────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
└─────────┴───────────────────────────────────────────────────────────────────┘
```

**Améliorations vs v1 :**
- **Section "Apps"** avec grille d'icônes type Umbrel — chaque app est cliquable et ouvre son UI native dans un nouvel onglet. Le domaine Traefik est affiché sous chaque app (si plugin installé).
- **Section "Widgets"** repositionnable — chaque plugin peut injecter un widget. Le widget "Dernière activité" est natif (core) et montre les actions récentes type Cloudron Activity.
- **Salutation personnalisée** en haut à gauche (Umbrel-like) au lieu d'un titre froid
- **Compteur de notifications** (🔔) pour les alertes et événements importants

---

## Écran 2 : Apps (vue unifiée)

Inspiré de Cloudron (apps avec domaine) + Runtipi (statut + actions inline) + Cosmos (server apps).

C'est la vue principale. Tout ce qui est "déployé" apparaît ici, qu'il ait été installé depuis la marketplace ou créé manuellement.

```
┌─ Apps ──────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  Mes Apps (5)                    [🔍 Rechercher]  [+ Nouvelle App]         │
│                                                                             │
│  ┌── Nextcloud ──────────────────────────────────────────────── 🟢 ─────┐  │
│  │  ☁️  Nextcloud 28.0.4                                                │  │
│  │  cloud.example.com (🔒 TLS)    Stack: nextcloud    Target: local     │  │
│  │  3 services: nginx, php-fpm, cron    RAM: 342 MB                     │  │
│  │                                                                       │  │
│  │  [🔗 Ouvrir]  [📋 Logs]  [>_ Terminal]  [⏸ Stop]  [🔄 Update ⬆]  [⋯] │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌── Gitea ──────────────────────────────────────────────────── 🟢 ─────┐  │
│  │  🐙  Gitea 1.21.8                                                   │  │
│  │  git.example.com (🔒 TLS)      Stack: gitea       Target: local     │  │
│  │  2 services: gitea, gitea-db    RAM: 189 MB                          │  │
│  │                                                                       │  │
│  │  [🔗 Ouvrir]  [📋 Logs]  [>_ Terminal]  [⏸ Stop]  [🔄]            [⋯] │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌── Jellyfin ───────────────────────────────────────────────── 🟢 ─────┐  │
│  │  🎬  Jellyfin 10.9.6                                                │  │
│  │  media.example.com (🔒 TLS)    Container: jellyfin  Target: local   │  │
│  │  1 service    RAM: 456 MB    GPU: ✓                                  │  │
│  │                                                                       │  │
│  │  [🔗 Ouvrir]  [📋 Logs]  [>_ Terminal]  [⏸ Stop]                   [⋯] │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌── ubuntu-dev (VM) ────────────────────────────────────────── 🟢 ─────┐  │
│  │  🖥️  Ubuntu 22.04 (KVM)                                             │  │
│  │  2 vCPU, 2 GB RAM, 20 GB disk    Target: local    Stack: dev-env    │  │
│  │                                                                       │  │
│  │  [🖥 Console]  [📋 Logs]  [📸 Snapshot]  [⏸ Stop]  [🔄 Restart]  [⋯] │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌── old-test-app ───────────────────────────────────────────── 🔴 ─────┐  │
│  │  📦  myapp:1.0                                                       │  │
│  │  Container arrêté depuis 3 jours    Target: local                    │  │
│  │                                                                       │  │
│  │  [▶ Start]  [📋 Logs]  [🗑 Supprimer]                               [⋯] │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Améliorations clés :**
- **Vue unifiée** : Stacks, containers individuels ET VMs dans la même liste, différenciés par icône
- **Domaine affiché** si plugin Traefik actif — clic direct vers l'app dans le navigateur
- **Bouton [🔗 Ouvrir]** en premier (c'est l'action la plus courante — inspiré Runtipi)
- **Actions inline** complètes sans ouvrir le détail — inspiré Cloudron et Portainer
- **Bouton [⋯]** pour les actions secondaires (backup, clone, modifier, supprimer, voir compose)
- **Badge [⬆]** pour les mises à jour disponibles — inspiré Runtipi et Cloudron
- **RAM consommée** visible directement — important sur RPi

---

## Écran 3 : Détail App / Container

Inspiré de Proxmox (onglets) + Cosmos (URL/routing intégré) + Cloudron (backup + domain).

```
┌─ Nextcloud ────────────────────────────────────────────────────────────────┐
│                                                                            │
│  ☁️ Nextcloud 28.0.4           🟢 Running (15 jours)      [🔗 Ouvrir]    │
│  cloud.example.com (🔒 TLS expire dans 89j)                              │
│  Stack: nextcloud  │  Target: local  │  RAM: 342 MB  │  CPU: 5%          │
│                                                                            │
│  [⏸ Stop] [🔄 Restart] [📋 Logs] [>_ Terminal] [📸 Backup] [⚙ Config]   │
│                                                                            │
│  ┌ Aperçu ─┬ Services ─┬ Logs ─┬ Terminal ─┬ Volumes ─┬ Domaine ─┬ ⚙ ─┐  │
│  │                                                                      │  │
│  │  ──── Onglet Aperçu (actif) ────                                    │  │
│  │                                                                      │  │
│  │  ┌─ Services (3) ──────────────────────────────────────────────┐    │  │
│  │  │  nginx       nginx:alpine     🟢 running   80→80           │    │  │
│  │  │  php-fpm     nextcloud:28     🟢 running   9000            │    │  │
│  │  │  cron        nextcloud:28     🟢 running   —               │    │  │
│  │  └──────────────────────────────────────────────────────────────┘    │  │
│  │                                                                      │  │
│  │  ┌─ Ressources ────────────────────────────────────────────────┐    │  │
│  │  │  CPU  ██░░░░░░░░ 5%     RAM  ████░░░░░░ 342/512 MB        │    │  │
│  │  │  NET ↑ 12 MB/s  ↓ 340 KB/s    I/O ↑ 2 MB/s  ↓ 500 KB/s  │    │  │
│  │  └──────────────────────────────────────────────────────────────┘    │  │
│  │                                                                      │  │
│  │  ┌─ Volumes ──────────────────────────────────────────────────┐     │  │
│  │  │  nextcloud_data    → /var/www/html        2.1 GB  [📂]    │     │  │
│  │  │  nextcloud_config  → /var/www/html/config  12 MB  [📂]    │     │  │
│  │  │  nextcloud_db      → /var/lib/mysql        890 MB [📂]    │     │  │
│  │  └──────────────────────────────────────────────────────────────┘    │  │
│  │                                                                      │  │
│  │  ┌─ Actions Plugin ───────────────────────────────────────────┐     │  │
│  │  │  🐘 PostgreSQL Manager : 2 databases, 3 users              │     │  │
│  │  │  [Créer une DB] [Créer un User] [Backup SQL] [Stats]      │     │  │
│  │  └──────────────────────────────────────────────────────────────┘    │  │
│  │                                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

**Améliorations :**
- **Onglet "Domaine"** (ajouté par plugin Traefik) : permet de modifier le domaine, voir le certificat, configurer le routing
- **Onglet "Services"** : liste tous les containers de la stack avec statut individuel
- **Métriques inline** avec mini-graphiques (inspiré Proxmox Summary)
- **Bouton [📸 Backup]** directement sur l'app (inspiré Cloudron et Runtipi) — nécessite plugin Restic
- **Actions plugin contextuelles** en bas : le plugin PostgreSQL détecte les containers DB et propose ses actions

---

## Écran 3b : Détail Instance — VM (vue convergente)

La **même structure d'onglets** que le détail Container, adaptée au type VM. Inspiré de Proxmox (onglets identiques VM/CT) et Incus (même CLI pour les deux types).

```
┌─ ubuntu-dev (VM) ──────────────────────────────────────────────────────────┐
│                                                                            │
│  🖥️ Ubuntu 22.04 (KVM)        🟢 Running (3 jours)      [🖥 Console]    │
│  IP: 192.168.1.55 (dhcp)                                                  │
│  Stack: dev-env  │  Target: local  │  RAM: 1.8 / 2 GB  │  CPU: 12%      │
│                                                                            │
│  [⏸ Stop] [🔄 Restart] [📋 Logs] [📸 Snapshot] [🖥 Console] [⚙ Config]  │
│                                                                            │
│  ┌ Aperçu ─┬ Console ─┬ Métriques ─┬ Stockage ─┬ Réseau ─┬ Snapshots ─┬ ⚙ ─┐
│  │                                                                      │  │
│  │  ──── Onglet Aperçu (actif) ────                                    │  │
│  │                                                                      │  │
│  │  ┌─ Hardware ───────────────────────────────────────────────────┐    │  │
│  │  │  Type    KVM / QEMU (libvirt)                               │    │  │
│  │  │  vCPU    2 (cortex-a72)                                     │    │  │
│  │  │  RAM     2 GB                                               │    │  │
│  │  │  Firmware EFI                                               │    │  │
│  │  │  OS      Ubuntu 22.04.3 LTS (cloud-init)                    │    │  │
│  │  └──────────────────────────────────────────────────────────────┘    │  │
│  │                                                                      │  │
│  │  ┌─ Ressources ────────────────────────────────────────────────┐    │  │
│  │  │  CPU  ████░░░░░░ 12%    RAM  █████████░ 1.8 / 2 GB         │    │  │
│  │  │  NET ↑ 2.4 MB/s  ↓ 890 KB/s   I/O ↑ 5 MB/s  ↓ 1 MB/s    │    │  │
│  │  └──────────────────────────────────────────────────────────────┘    │  │
│  │                                                                      │  │
│  │  ┌─ Disques (1) ──────────────────────────────────────────────┐     │  │
│  │  │  vda    qcow2    20 GB    /         8.2 GB used    [📂]    │     │  │
│  │  └──────────────────────────────────────────────────────────────┘    │  │
│  │                                                                      │  │
│  │  ┌─ Snapshots (2) ────────────────────────────────────────────┐     │  │
│  │  │  📸 clean-install    2024-03-28 10:00    1.2 GB    [⟲]    │     │  │
│  │  │  📸 before-update    2024-03-29 15:30    0.8 GB    [⟲]    │     │  │
│  │  │                                              [+ Nouveau]    │     │  │
│  │  └──────────────────────────────────────────────────────────────┘    │  │
│  │                                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

**Convergence avec le détail Container (Écran 3) :**

| Élément | Container (Écran 3) | VM (Écran 3b) | Convergence |
|---------|---------------------|----------------|-------------|
| Barre d'actions | Stop, Restart, Logs, Terminal, Backup, Config | Stop, Restart, Logs, Snapshot, Console, Config | Mêmes positions, adaptées au type |
| Onglet Aperçu | Services + Ressources + Volumes | Hardware + Ressources + Disques + Snapshots | Même layout, contenu adapté |
| Onglet Console | Terminal xterm.js | Console VNC/noVNC | Même chrome UI (toolbar, fullscreen) |
| Onglet Métriques | CPU/RAM/Net/I/O | CPU/RAM/Net/I/O | Identique |
| Onglet Stockage | Volumes Docker | Disques VM (qcow2/raw) | Même structure liste + actions |
| Onglet Réseau | Docker networks | Bridges/VLANs | Même structure liste + actions |
| Onglet Config | Env vars + Labels | Hardware (CPU/RAM/firmware) | Même principe éditable |
| Onglet Snapshots | — (dans ⋯) | Arbre de snapshots | Spécifique VM, visible si applicable |

**Règle :** Les onglets communs (Aperçu, Console, Métriques, Stockage, Réseau, Config) sont toujours présents. Les onglets spécifiques (Snapshots pour VM, Services pour stack) apparaissent selon le type d'instance.

---

## Écran 4 : Marketplace

Inspiré de Umbrel App Store (fiches détaillées, design soigné) + Runtipi (catégories, 300 apps) + Cloudron (apps vérifiées avec domaine).

```
┌─ Marketplace ──────────────────────────────────────────────────────────────┐
│                                                                            │
│  [🔍 Rechercher apps et plugins...]                                       │
│                                                                            │
│  ┌ Plugins ─┬ Stacks ─┐                                                   │
│                                                                            │
│  Catégories:                                                               │
│  [Tous] [🔀 Accès] [📊 Monitoring] [🐘 Bases de données] [💾 Backup]     │
│  [🔒 Sécurité] [🐙 Git] [✉️ Mail] [🤖 IA] [📡 Messagerie] [📦 Stockage] │
│                                                                            │
│  ── Recommandés pour vous ────────────────────────────────────────────── │
│  (basé sur votre config : pas de reverse proxy détecté)                   │
│                                                                            │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐          │
│  │                  │ │                  │ │                  │          │
│  │  🔀  Traefik     │ │  📊 Uptime Kuma  │ │  💾 Restic       │          │
│  │                  │ │                  │ │                  │          │
│  │  Reverse proxy   │ │  Monitoring de   │ │  Backup auto     │          │
│  │  avec HTTPS      │ │  disponibilité   │ │  de vos volumes  │          │
│  │  automatique     │ │                  │ │                  │          │
│  │                  │ │  128 Mo • arm64 ✓│ │  64 Mo • arm64 ✓ │          │
│  │  128 Mo • arm64 ✓│ │                  │ │                  │          │
│  │  ⭐ Recommandé   │ │  ★★★★★ (12)     │ │  ★★★★☆ (8)      │          │
│  │                  │ │                  │ │                  │          │
│  │  [Installer]     │ │  [Installer]     │ │  [Installer]     │          │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘          │
│                                                                            │
│  ── Toutes les Apps ──────────────────────────────────────────────────── │
│                                                                            │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐          │
│  │  🐘 PostgreSQL   │ │  🔴 Redis        │ │  🍃 MongoDB      │          │
│  │  Manager         │ │  Manager         │ │  Manager         │          │
│  │  Extension       │ │  Extension       │ │  Extension       │          │
│  │  32 Mo • arm64 ✓ │ │  32 Mo • arm64 ✓ │ │  32 Mo • arm64 ✓ │          │
│  │  [Installé ✅]   │ │  [Installer]     │ │  [Installer]     │          │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘          │
│                                                                            │
│  ┌ Stacks ─┐  (onglet Stacks)                                             │
│                                                                            │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐          │
│  │  ☁️ Nextcloud     │ │  🐙 Gitea        │ │  🎬 Jellyfin     │          │
│  │  Cloud personnel │ │  Git self-hosted │ │  Streaming       │          │
│  │                  │ │                  │ │  média           │          │
│  │  512 Mo • arm64 ✓│ │  256 Mo • arm64 ✓│ │  512 Mo • arm64 ✓│          │
│  │  [Déployé ✅]    │ │  [Déployer]      │ │  [Déployer]      │          │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘          │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

**Améliorations vs v1 :**
- **"Recommandés pour vous"** basé sur l'état de l'infrastructure (pas de reverse proxy → recommander Traefik, pas de backup → recommander Restic). Inspiré des stores intelligents.
- **Ratings** par la communauté (étoiles) — inspiré Runtipi et CasaOS
- **Onglets Plugins / Stacks** pour séparer clairement les deux types
- **Badge "Extension"** visible sur les plugins qui n'ajoutent pas de container (pour rassurer sur la consommation mémoire)
- **Compatibilité ARM** et RAM toujours visibles — critique pour les utilisateurs RPi

---

## Écran 5 : Wizard Installation (étapes)

Inspiré de Scaleway (wizard par étapes) + Cloudron (configuration simplifiée).

```
┌─ Installer Traefik ────────────────────────────────────────────────────────┐
│                                                                            │
│  ○───────●───────○                                                        │
│  Vérifier  Configurer  Installer                                          │
│                                                                            │
│  Étape 2 sur 3 — Configuration                                           │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                                                                     │  │
│  │  Email Let's Encrypt *                                              │  │
│  │  ┌─────────────────────────────────────────────────────┐            │  │
│  │  │ admin@example.com                                   │            │  │
│  │  └─────────────────────────────────────────────────────┘            │  │
│  │  📎 Requis pour recevoir les alertes d'expiration de certificats   │  │
│  │                                                                     │  │
│  │  ─────────────────────────────────────────────────────              │  │
│  │                                                                     │  │
│  │  Dashboard Traefik                                                  │  │
│  │  [✓ Activé]                                                         │  │
│  │  📎 Accessible à traefik.votre-domaine.com                         │  │
│  │                                                                     │  │
│  │  ─────────────────────────────────────────────────────              │  │
│  │                                                                     │  │
│  │  ▸ Options avancées                                                 │  │
│  │                                                                     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─ Ce plugin va : ────────────────────────────────────────────────────┐  │
│  │  ✓ Déployer Traefik (1 container, ~128 Mo RAM)                     │  │
│  │  ✓ Ajouter la page "Domaines" dans le menu                        │  │
│  │  ✓ Utiliser les ports 80 et 443                                    │  │
│  │  ✓ Configurer automatiquement le routage des futures apps          │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│                                           [← Retour]  [Installer →]      │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

**Améliorations :**
- **Stepper visuel** en haut (●───○───○) — clair et non-intimidant
- **Options avancées cachées** par défaut (accordion) — les débutants ne voient que l'essentiel
- **Encadré "Ce plugin va"** en bas qui résume l'impact (containers, RAM, ports) — inspiré de la transparence de Cosmos et des dialogues d'installation mobile

---

## Écran 6 : Targets (machines)

Inspiré de Coolify (vue multi-serveurs) + Proxmox (arbre de nodes) + Scaleway (instances cards).

```
┌─ Targets ──────────────────────────────────────────────────────────────────┐
│                                                                            │
│  Machines (3)                         [+ Ajouter une machine]             │
│                                                                            │
│  ┌── local ────────────────────────────────────────────────── 🟢 ──────┐  │
│  │                                                                      │  │
│  │  🏠 Machine locale │ arm64 │ Raspberry Pi OS 12                     │  │
│  │                                                                      │  │
│  │  CPU ████░░░░░░ 38%    RAM ██████░░░░ 1.2 / 4.0 GB                 │  │
│  │  Disk █████████░ 28 / 64 GB     Temp: 52°C                          │  │
│  │                                                                      │  │
│  │  Docker 24.0.7 ✅    KVM 9.0.0 ✅    5 apps, 1 VM                   │  │
│  │                                                                      │  │
│  │  [📊 Métriques]  [⚙ Configurer]                                     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌── nas-server ───────────────────────────────────────────── 🟢 ──────┐  │
│  │                                                                      │  │
│  │  🔗 SSH deploy@192.168.1.50 │ amd64 │ Debian 12                    │  │
│  │                                                                      │  │
│  │  CPU ██░░░░░░░░ 12%    RAM ████░░░░░░ 6.2 / 32 GB                  │  │
│  │  Disk ███░░░░░░░ 2.1 / 8.0 TB                                       │  │
│  │                                                                      │  │
│  │  Docker 25.0.3 ✅    12 apps                                         │  │
│  │                                                                      │  │
│  │  [📊 Métriques]  [⚙ Configurer]  [>_ SSH]                           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌── proxmox-1 ───────────────────────────────────────────── 🔴 ──────┐  │
│  │                                                                      │  │
│  │  🖥️ Proxmox VE (192.168.1.100) │ amd64 │ PVE 8.1                   │  │
│  │                                                                      │  │
│  │  ⚠️ Hors ligne depuis 2h (dernière vue: 12:30)                      │  │
│  │                                                                      │  │
│  │  [🔄 Réessayer]  [⚙ Configurer]                                     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

**Améliorations :**
- **Température CPU** affichée (pertinent sur RPi) — inspiré des dashboards hardware
- **Bouton [>_ SSH]** pour ouvrir un terminal SSH directement dans le navigateur vers la machine distante
- **Compteur d'apps** par machine pour voir rapidement la répartition de charge
- **Taille de stockage** en TB pour les NAS

---

## Écran 7 : Volume Browser

Inspiré de CasaOS File Manager + Nextcloud Files + Cosmos Storage Manager.

```
┌─ Volume Browser : nextcloud_data ──────────────────────────────────────────┐
│                                                                            │
│  📂 nextcloud_data (2.1 GB)     Utilisé par: nextcloud                    │
│                                                                            │
│  Chemin: / ▸ data ▸ admin ▸ files                                         │
│                                                                            │
│  [⬆ Upload]  [📁 Nouveau dossier]  [📄 Nouveau fichier]                  │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  NOM                 TYPE      TAILLE    MODIFIÉ        ACTIONS     │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │  📁 Documents        dossier   340 MB    01/04 14:30    →          │  │
│  │  📁 Photos           dossier   1.2 GB    01/04 10:15    →          │  │
│  │  📄 notes.md         fichier   2.4 KB    01/04 14:30    📝 ⬇ 🗑   │  │
│  │  🖼️ wallpaper.jpg    image     1.8 MB    28/03 10:15    👁 ⬇ 🗑   │  │
│  │  📄 config.php       fichier   12 KB     28/03 10:15    📝 ⬇ 🗑   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─ Preview : wallpaper.jpg ───────────────────────────────────────────┐  │
│  │                                                                     │  │
│  │  ┌─────────────────────────────────────────────┐                    │  │
│  │  │                                             │                    │  │
│  │  │           [ Image Preview ]                 │                    │  │
│  │  │                                             │                    │  │
│  │  └─────────────────────────────────────────────┘                    │  │
│  │                                                                     │  │
│  │  1920×1080 • JPEG • 1.8 MB          [⬇ Télécharger]  [Fermer]     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

**Améliorations :**
- **Preview inline** pour images, texte, markdown, logs — inspiré CasaOS et Nextcloud
- **Breadcrumbs cliquables** pour la navigation (/ ▸ data ▸ admin ▸ files)
- **Bouton [👁]** pour preview rapide sans ouvrir l'éditeur
- **Drag & drop** pour l'upload (indication zone de drop)

---

## Écran 8 : Console Unifiée (Terminal + VNC)

Inspiré de Proxmox (noVNC dans un onglet) et Incus (même commande console pour containers et VMs).

Le bouton `[🖥 Console]` ouvre la même page pour tous les types d'instances. Le contenu s'adapte :
- **Container / Pod K8s** → Terminal xterm.js (shell interactif via WebSocket)
- **VM** → Console VNC/noVNC (accès graphique via WebSocket)

Même chrome UI pour les deux : barre d'outils, plein écran, clipboard.

### Console Terminal (Container)

```
┌─ Console : nextcloud-php ──────────────────────────────────────────────────┐
│                                                                            │
│  📦 nextcloud-php (container) 🟢    [🖥 Terminal]  [Plein Écran]          │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  root@nextcloud-php:/var/www/html# ls -la                            │ │
│  │  total 184                                                            │ │
│  │  drwxr-xr-x  1 www-data www-data  4096 Mar 28  config               │ │
│  │  drwxr-xr-x  1 www-data www-data  4096 Mar 28  apps                 │ │
│  │  -rw-r--r--  1 www-data www-data  2847 Mar 28  index.php             │ │
│  │  root@nextcloud-php:/var/www/html# _                                 │ │
│  │                                                                      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  Shell: /bin/bash  │  User: root  │  Container: nextcloud-php            │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Console VNC (VM)

```
┌─ Console : ubuntu-dev ─────────────────────────────────────────────────────┐
│                                                                            │
│  🖥️ ubuntu-dev (VM KVM) 🟢    [Ctrl+Alt+Del]  [Plein Écran]  [Coller]   │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                                                                      │ │
│  │          ubuntu@ubuntu-dev:~$ sudo apt update                        │ │
│  │          Hit:1 http://archive.ubuntu.com/ubuntu jammy InRelease      │ │
│  │          Get:2 http://archive.ubuntu.com/ubuntu jammy-updates        │ │
│  │          ...                                                         │ │
│  │          ubuntu@ubuntu-dev:~$ _                                      │ │
│  │                                                                      │ │
│  │                    [ Console VNC via noVNC ]                          │ │
│  │                                                                      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  Résolution: 1024×768  │  Qualité: Auto  │  Clipboard: Bidirectionnel     │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

**Convergence :** La barre de titre affiche le type d'instance (`📦 container` ou `🖥️ VM KVM`), mais le chrome (toolbar, fullscreen, status bar) est identique. L'utilisateur sait toujours s'il est dans un terminal ou une console graphique, mais l'expérience d'ouverture est la même.

---

## Écran 9 : Plugins Installés

Inspiré de Runtipi (app management) + Cosmos (server apps).

```
┌─ Plugins ──────────────────────────────────────────────────────────────────┐
│                                                                            │
│  Plugins installés (3)            RAM: 268 MB     [🏪 Marketplace]        │
│                                                                            │
│  ┌── 🔀 Traefik ──────────────────────────── v1.2.0 ──── 🟢 ──────────┐ │
│  │  Hybrid │ Accès & Routage │ 142 MB RAM                              │ │
│  │                                                                      │ │
│  │  📊 3 domaines actifs • 3 certificats valides • 1.2K req/h          │ │
│  │                                                                      │ │
│  │  [⚙ Config]  [📋 Logs]  [⏸ Stop]  [🔄 Update]  [🗑 Désinstaller]  │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌── 🐘 PostgreSQL Manager ───────────────── v1.0.0 ──── 🟢 ──────────┐ │
│  │  Extension │ Bases de données │ 28 MB RAM                            │ │
│  │                                                                      │ │
│  │  📊 2 containers détectés • 5 databases • 3 users                   │ │
│  │                                                                      │ │
│  │  [⚙ Config]  [🔄 Update]  [🗑 Désinstaller]                        │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌── 📊 Uptime Kuma ─────────── v1.0.0 ⬆ v1.1.0 ──── 🟢 ──────────┐   │
│  │  Service │ Monitoring │ 98 MB RAM                                    │ │
│  │                                                                      │ │
│  │  📊 5 monitors • 100% uptime (30j)                                  │ │
│  │                                                                      │ │
│  │  [🔗 Ouvrir]  [⚙ Config]  [📋 Logs]  [⏸ Stop]  [🔄 Update ⬆]     │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Écran 10 : Notifications / Activity

Inspiré de Cloudron (Activity log) + Umbrel (Activity tab).

```
┌─ Activité ─────────────────────────────────────────────────────────────────┐
│                                                                            │
│  [Tout]  [Déploiements]  [Plugins]  [Sécurité]  [Système]                │
│                                                                            │
│  Aujourd'hui                                                              │
│                                                                            │
│  🔔 14:30  Certificat cloud.example.com expire dans 30 jours             │
│            [Renouveler maintenant]                                        │
│                                                                            │
│  ✅ 12:15  Nextcloud mis à jour 28.0.3 → 28.0.4          par admin      │
│            Durée: 45s • Backup créé avant mise à jour                    │
│                                                                            │
│  ✅ 06:00  Backup automatique terminé                      par système   │
│            3 volumes • 2.1 GB • Destination: /backup/restic              │
│                                                                            │
│  Hier                                                                     │
│                                                                            │
│  ❌ 18:30  Déploiement monitoring échoué                   par admin      │
│            Erreur: port 9090 déjà utilisé                                │
│            [Voir les logs] [Réessayer]                                    │
│                                                                            │
│  ✅ 15:00  Plugin Restic installé (v1.0.0)                par admin      │
│                                                                            │
│  ✅ 14:45  Target nas-server ajouté                        par admin      │
│            SSH deploy@192.168.1.50 • Docker détecté                      │
│                                                                            │
│  🔒 10:22  Connexion refusée (brute force)                 IP: 45.33.x.x │
│            5 tentatives échouées → IP bloquée 5 min                      │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

**Inspiré de Cloudron Activity :** Journal chronologique filtrable avec actions directes ("Renouveler", "Voir les logs", "Réessayer"). Chaque entrée montre qui, quand, quoi, et le résultat. Les événements de sécurité sont visibles directement ici.

---

## Responsive et Mobile

### Tablette (768px-1024px)

- Sidebar rétractée en icônes (hover pour voir les labels)
- Dashboard : widgets en 2 colonnes au lieu de 3
- Apps : une card par ligne (plus de place pour les actions)

### Mobile (< 768px)

Inspiré de l'approche Umbrel (dock en bas) :

```
┌─────────────────────────┐
│ 🌀 WindFlow    🔔  👤   │
├─────────────────────────┤
│                         │
│  CPU 38%  RAM 1.2/4 GB  │
│  5 apps running         │
│                         │
│ ┌─────────────────────┐ │
│ │ ☁️ Nextcloud  🟢    │ │
│ │ cloud.example.com   │ │
│ │ [Ouvrir] [⋯]       │ │
│ └─────────────────────┘ │
│ ┌─────────────────────┐ │
│ │ 🐙 Gitea     🟢    │ │
│ │ git.example.com     │ │
│ │ [Ouvrir] [⋯]       │ │
│ └─────────────────────┘ │
│ ...                     │
│                         │
├─────────────────────────┤
│ 🏠  📱  🏪  🔌  ⚙️    │
│ Home Apps Market Plug Set│
└─────────────────────────┘
```

- **Dock fixe en bas** (inspiré Umbrel) avec les 5 sections principales
- **Cards simplifiées** avec bouton "Ouvrir" (action principale) et menu [⋯] pour les actions secondaires
- Console VNC et Terminal non accessibles sur mobile (écran trop petit)
- Volume Browser en mode lecture seule sur mobile

---

## Onboarding (Premier Lancement)

Inspiré de Umbrel (wizard simple) + Cosmos (setup wizard).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                        🌀 Bienvenue sur WindFlow                        │
│                                                                         │
│                  Votre infrastructure, sous votre contrôle.             │
│                                                                         │
│                                                                         │
│         ○─────────●─────────○─────────○                                │
│        Compte    Machine   Première   Terminé                          │
│                             app                                        │
│                                                                         │
│         Étape 2 — Votre machine                                        │
│                                                                         │
│         WindFlow a détecté :                                           │
│                                                                         │
│         🖥️  Raspberry Pi 4 (arm64)                                     │
│         💾  4 GB RAM • 64 GB stockage                                  │
│         🐳  Docker 24.0.7 ✅                                           │
│         🖥️  KVM/libvirt ✅                                             │
│                                                                         │
│         Profil recommandé : Standard                                   │
│         (PostgreSQL + Redis, ~1.5 GB RAM)                              │
│                                                                         │
│         💡 Votre machine a assez de ressources pour                    │
│            installer 5-10 apps et plugins.                             │
│                                                                         │
│                                                                         │
│                              [Continuer →]                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

L'étape 3 propose d'installer un premier plugin (Traefik recommandé) et une première app (Nextcloud, Gitea, ou Jellyfin au choix).

---

## Écran 11b : Wizard Création d'Instance Unifié

Inspiré de Proxmox (Create VM/CT dans la même UI) et Incus (`incus launch` — même commande pour containers et VMs).

Le wizard démarre par le choix du type d'instance, puis les étapes s'adaptent. C'est le même point d'entrée `[+ Nouvelle App]` qui déclenche ce wizard.

### Étape 1 — Choix du Type

```
┌─ Créer une Instance ───────────────────────────────────────────────────────┐
│                                                                            │
│  ○─────────○───────○───────○                                              │
│  Type      Config  Déploy                                                  │
│                                                                            │
│  Étape 1 — Que voulez-vous créer ?                                        │
│                                                                            │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐          │
│  │                  │ │                  │ │                  │          │
│  │  📦  Container   │ │  📚  Stack       │ │  🖥️  VM          │          │
│  │                  │ │  (Compose)       │ │                  │          │
│  │  Un container    │ │                  │ │  Machine         │          │
│  │  unique depuis   │ │  Groupe de       │ │  virtuelle KVM   │          │
│  │  une image       │ │  containers      │ │  ou LXD/Incus    │          │
│  │  Docker          │ │  via Compose     │ │                  │          │
│  │                  │ │                  │ │                  │          │
│  │  Rapide, simple  │ │  Pour les apps   │ │  Pour les OS     │          │
│  │  128+ Mo RAM     │ │  multi-services  │ │  complets, legacy│          │
│  │                  │ │  256+ Mo RAM     │ │  512+ Mo RAM     │          │
│  │                  │ │                  │ │                  │          │
│  │  [Choisir]       │ │  [Choisir]       │ │  [Choisir]       │          │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘          │
│                                                                            │
│  💡 Pas sûr ? Commencez par la Marketplace pour un déploiement one-click  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Étape 2 — Configuration (adaptée au type choisi : Container)

```
┌─ Créer un Container ───────────────────────────────────────────────────────┐
│                                                                            │
│  ●─────────○───────○───────○                                              │
│  Type      Config  Déploy                                                  │
│                                                                            │
│  Étape 2 — Configuration du Container                                    │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  Nom *           [nginx-proxy            ]                         │  │
│  │  Image *         [nginx:latest           ]  [🔍 Chercher]         │  │
│  │  Target          [▼ local (RPi 4)       ]                          │  │
│  │                                                                     │  │
│  │  ── Ressources ──────────────────────────────────────               │  │
│  │  RAM limit       [512] MB    CPU limit    [1] cores               │  │
│  │                                                                     │  │
│  │  ── Ports ───────────────────────────────────────────               │  │
│  │  Host: [80] → Container: [80]    [+ Ajouter un port]              │  │
│  │                                                                     │  │
│  │  ▸ Volumes  ▸ Réseau  ▸ Env vars  ▸ Labels (avancé)               │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│                                           [← Retour]  [Déployer →]       │
└────────────────────────────────────────────────────────────────────────────┘
```

### Étape 2 — Configuration (adaptée au type choisi : VM)

```
┌─ Créer une VM ─────────────────────────────────────────────────────────────┐
│                                                                            │
│  ●─────────○───────○───────○                                              │
│  Type      Config  Déploy                                                  │
│                                                                            │
│  Étape 2 — Configuration de la Machine Virtuelle                         │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  Nom *           [ubuntu-dev            ]                         │  │
│  │  Target          [▼ local (RPi 4)       ]                          │  │
│  │  Hyperviseur     [▼ KVM/libvirt         ]                          │  │
│  │                                                                     │  │
│  │  ── Image OS ───────────────────────────────────────                │  │
│  │  Template        [▼ Ubuntu 22.04 LTS (cloud-init) ]               │  │
│  │  Architecture    [▼ arm64              ]                          │  │
│  │                                                                     │  │
│  │  ── Hardware ───────────────────────────────────────                │  │
│  │  vCPU            [2] cores   RAM     [2048] MB                    │  │
│  │  Disque          [20] GB     Format  [▼ qcow2  ]                  │  │
│  │                                                                     │  │
│  │  ── Cloud-init ─────────────────────────────────────                │  │
│  │  Hostname        [ubuntu-dev]                                     │  │
│  │  Utilisateur     [ubuntu    ]                                     │  │
│  │  Clé SSH         [▼ ~/.ssh/id_rsa.pub]                            │  │
│  │  Packages        [htop, curl, git ]                                │  │
│  │                                                                     │  │
│  │  ▸ Réseau (bridge/VLAN)  ▸ Storage pool  ▸ Firmware (avancé)      │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│                                           [← Retour]  [Déployer →]       │
└────────────────────────────────────────────────────────────────────────────┘
```

**Convergence :** Le wizard Container et le wizard VM partagent :
- Le même stepper visuel (Type → Config → Déploy)
- Les mêmes sections "Nom", "Target", "Ressources"
- La même logique de sections dépliables (▸ Réseau, ▸ Avancé)
- Le même bouton final "Déployer"

Seules les sections spécifiques diffèrent (Image Docker vs Template OS, Ports vs Cloud-init, Volumes vs Disques).

---

## Écran 12 : Vue Compute (Mode Avancé)

Inspiré de Proxmox (arbre Datacenter → Node → VM/CT) et Incus (`incus list` — table unifiée). Cf. `12-compute-model.md` pour le modèle conceptuel.

### Vue Globale (onglet par défaut)

```
┌─ Compute ──────────────────────────────────────────────────────────────────┐
│                                                                            │
│  [Vue globale] [Containers] [VMs] [Images & ISOs] [Snapshots]             │
│                                                                            │
│  Filtres: [▼ Tout type] [▼ Tout target] [▼ Tout statut] [🔍 Rechercher]  │
│  Vue: [▣ Par stack] [☰ Par machine]                                       │
│                                                                            │
│  ── Stacks WindFlow ─────────────────────────────────────────────────────  │
│                                                                            │
│  ┌─ ☁️ nextcloud (compose · local) — 3/3 running ──────────────────────┐ │
│  │  [▶ Start all] [⏸ Stop all] [🔄 Redeploy] [📝 Edit] [⋯]          │ │
│  │                                                                     │ │
│  │  TYPE       NOM              IMAGE/OS           STATUS   CPU  RAM   │ │
│  │  📦 Ctr     nextcloud-nginx  nginx:alpine       🟢 run   2%   45MB  │ │
│  │  📦 Ctr     nextcloud-php    nextcloud:28       🟢 run   5%   297MB │ │
│  │  📦 Ctr     nextcloud-cron   nextcloud:28       🟢 run   0%   12MB  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ 🔧 dev-env (mixte · local) — all up ──────────────────────────────┐ │
│  │  [▶ Start all] [⏸ Stop all] [🔄 Redeploy] [📝 Edit] [⋯]          │ │
│  │                                                                     │ │
│  │  TYPE       NOM              IMAGE/OS           STATUS   CPU  RAM   │ │
│  │  🖥️ VM      ubuntu-dev       Ubuntu 22.04       🟢 run   12%  1.8G  │ │
│  │  📦 Ctr     dev-postgres     postgres:15        🟢 run   1%   89MB  │ │
│  │  📦 Ctr     dev-redis        redis:7-alpine     🟢 run   0%   12MB  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ── Discovered (non managés) ──────────────────────────────────────────   │
│                                                                            │
│  ┌─ monitoring (compose · nas-server) — observé, adoptable ───────────┐  │
│  │  TYPE       NOM              IMAGE/OS           STATUS   CPU  RAM   │ │
│  │  📦 Ctr     prometheus       prom/prometheus    🟢 run   3%   234MB │ │
│  │  📦 Ctr     grafana          grafana/grafana    🟢 run   1%   89MB  │ │
│  │                                          [📥 Adopter dans WindFlow] │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ── Standalone ────────────────────────────────────────────────────────   │
│                                                                            │
│  TYPE       NOM              IMAGE/OS           STATUS   CPU  RAM  TGT   │ │
│  📦 Ctr     traefik          traefik:v3         🟢 run   1%  142MB local │ │
│  🖥️ VM      pfsense-router   pfSense 2.7       🟢 run   8%  512MB local │ │
│  📦 Ctr     pihole           pihole:latest      🟢 run   2%   67MB pi4  │ │
│                                                                            │
│  [+ Créer une Instance]                                                   │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

**Points clés de convergence :**
- **Même table** pour tous les types : la colonne TYPE différencie (`📦 Ctr` vs `🖥️ VM`)
- **Mêmes colonnes** : STATUS, CPU, RAM — comparables entre containers et VMs
- **Stacks mixtes** : une stack peut contenir des VMs ET des containers (cf. `dev-env`)
- **Actions de stack identiques** : Start/Stop/Redeploy/Edit — quel que soit le contenu
- **Toggle vue** : Par stack (logique) ou Par machine (physique)
- **Bouton Adopter** pour les objets discovered — même workflow pour containers et VMs

---

## Écran 13 : Liste Machines (famille Machines)

Inspiré de **Proxmox VE** (liste de VMs avec status) et **Incus/LXD** (`incus list`) et **Scaleway Console** (cards moderne pour les instances). Famille Machines uniquement — pour les Apps, voir Écran 2 ; pour les Hosts, voir Écran 17.

```
┌─ Machines ────────────────────────────[🏪 Templates] [+ Nouvelle Machine]─┐
│                                                                            │
│  Filtres : [▼ Tout statut] [▼ Tout Host] [▼ Tout OS] [🔍 Rechercher]      │
│  Mes Machines (4)                                                          │
│                                                                            │
│  ┌─ 🖥️ ubuntu-dev ──────────────────────────── 🟢 Running ───────────┐ │
│  │  Ubuntu 22.04 LTS · KVM · 2 vCPU · 2 GB RAM · 20 GB                  │ │
│  │  Sur : nas-server  ·  IP : 192.168.1.55                               │ │
│  │  CPU 12% · RAM 1.8/2 GB · 📸 2 snapshots                              │ │
│  │  💡 Cette Machine héberge 3 Apps Docker  [→ Gérer comme Host]         │ │
│  │                                                                       │ │
│  │  [🔗 SSH] [⏵ Power ▾] [📸 Snapshot] [🖥 VNC] [⚙ Hardware]        [⋯] │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ 🖥️ pfsense-router ──────────────────────── 🟢 Running ───────────┐ │
│  │  pfSense 2.7 · KVM · 1 vCPU · 512 MB RAM · 4 GB                       │ │
│  │  Sur : nas-server  ·  IP : 192.168.1.1 (gateway)                      │ │
│  │  CPU 8% · RAM 384/512 MB · pas de snapshots                           │ │
│  │  💡 Console graphique requise (pas de SSH par défaut)                  │ │
│  │                                                                       │ │
│  │  [🔗 Web UI] [⏵ Power ▾] [📸 Snapshot] [🖥 VNC] [⚙ Hardware]     [⋯] │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ 🖥️ k3s-node-1 ──────────────────────────── 🟢 Running ───────────┐ │
│  │  Alpine 3.19 · LXC system container · 2 vCPU · 4 GB · 20 GB         │ │
│  │  Sur : nas-server  ·  IP : 192.168.1.61                               │ │
│  │  CPU 35% · RAM 2.8/4 GB · 📸 1 snapshot                               │ │
│  │  💡 Membre du cluster k3s-cluster  [→ Voir le cluster]                │ │
│  │                                                                       │ │
│  │  [🔗 SSH] [⏵ Power ▾] [📸 Snapshot] [🖥 Console] [⚙ Config]       [⋯] │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ 🖥️ windows-legacy ────────────────────────── ⚪ Stopped ──────────┐ │
│  │  Windows Server 2019 · KVM · 4 vCPU · 8 GB · 80 GB                   │ │
│  │  Sur : nas-server  ·  Arrêtée depuis 12 jours                         │ │
│  │  📸 3 snapshots dont "before-patch-tuesday"                            │ │
│  │                                                                       │ │
│  │  [▶ Power on] [📸 Snapshots] [⚙ Hardware] [🗑]                    [⋯] │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

**Points clés de la famille Machines :**

- **Barre d'action canonique** : `[🔗 Ouvrir/SSH]` `[⏵ Power ▾]` `[📸 Snapshot]` `[🖥 VNC/Console]` `[⚙ Hardware]` `[⋯]`. Différente de la barre d'Apps : on parle "Power" (matériel) et non "Lifecycle" (service), `Snapshot` est canonique au lieu d'être dans le menu Plus, et `Hardware` remplace `Config`.
- **Status pill** : `🟢 Running` / `⚪ Stopped` / `🟡 Paused` / `🟡 Suspended` / `🔴 Crashed`. Vocabulaire matériel.
- **Le split-button `[⏵ Power ▾]`** propose : Power on / Power off (ACPI shutdown) / Reboot / Reset (hard reboot) / Pause / Suspend (hibernation).
- **Notes contextuelles `💡`** : signalent les cas particuliers (machine qui héberge des Apps, membre d'un cluster, console requise). Évitent de surcharger les cards tout en donnant le contexte clé.
- **Cas récursif** : `ubuntu-dev` est une Machine **et** un Host pour ses 3 Apps Docker internes. Le bouton `[→ Gérer comme Host]` bascule vers la vue Host (Écran 19) de la même entité.
- **Cas particulier LXC** : `k3s-node-1` est un system container LXC, traité comme une Machine (OS complet, SSH possible) mais avec quelques actions limitées.
- **Stopped machines** affichent une barre d'action réduite (pas de console, pas de snapshot d'état mémoire — seulement les actions applicables hors-tension).

---

## Écran 14 : Détail Machine

Inspiré de **Proxmox** (onglets identiques VM/CT) et **Incus** (même grammaire UI pour tous les types). Squelette identique au détail App (Écran 3) — c'est ce qui crée la cohérence inter-familles — mais vocabulaire matériel.

```
┌─ Détail Machine : ubuntu-dev ────────────────────────────────────────────┐
│                                                                          │
│  🖥️ ubuntu-dev                  🟢 Running (3 jours)         [🔗 SSH]   │
│  Ubuntu 22.04 LTS · KVM · IP : 192.168.1.55                              │
│  Sur : nas-server  ·  CPU 12% · 1.8 / 2 GB RAM · 8.2 / 20 GB disque     │
│  💡 Cette Machine héberge 3 Apps  [→ Gérer comme Host]                  │
│                                                                          │
│  [🔗 SSH] [⏵ Power ▾] [📸 Snapshot] [🖥 VNC] [⚙ Hardware]            [⋯]│
│                                                                          │
│  ┌Aperçu┬Console VNC┬Métriques┬Disques┬Réseau┬Snapshots┬Apps hébergées┐│
│  │       ┴Hardware┬Config                                              │ │
│  │                                                                     │ │
│  │  ── Aperçu (actif) ──                                              │ │
│  │                                                                     │ │
│  │  ┌─ Système ─────────────────────────────────────────────────┐    │ │
│  │  │  Type       KVM/QEMU via libvirt                          │    │ │
│  │  │  OS         Ubuntu 22.04.3 LTS (cloud-init initialisé)    │    │ │
│  │  │  Kernel     5.15.0-91-generic                              │    │ │
│  │  │  Firmware   EFI · Secure Boot désactivé                    │    │ │
│  │  │  Hostname   ubuntu-dev                                     │    │ │
│  │  │  Utilisateurs (cloud-init)   ubuntu (clé SSH)              │    │ │
│  │  └────────────────────────────────────────────────────────────┘    │ │
│  │                                                                     │ │
│  │  ┌─ Ressources allouées ─────────────────────────────────────┐    │ │
│  │  │  CPU       2 vCPU (host-passthrough)                       │    │ │
│  │  │  ├ Charge  ██░░░░░░░░ 12%                                  │    │ │
│  │  │  RAM       2 GB (ballooning activé)                         │    │ │
│  │  │  ├ Utilisé █████████░ 1.8 / 2 GB                            │    │ │
│  │  │  Disque    20 GB qcow2 (thin provisioning)                  │    │ │
│  │  │  ├ Utilisé ████░░░░░░ 8.2 / 20 GB                           │    │ │
│  │  │  Réseau    eth0 (virtio) · bridge vmbr0                     │    │ │
│  │  │  ├ I/O     ↑ 2.4 MB/s   ↓ 890 KB/s                          │    │ │
│  │  └────────────────────────────────────────────────────────────┘    │ │
│  │                                                                     │ │
│  │  ┌─ Apps hébergées dans cette Machine (3) ────────────────────┐   │ │
│  │  │  ☁️ dev-postgres   🟢 PostgreSQL 15 (docker)  · 89 MB        │   │ │
│  │  │  🔴 dev-redis      🟢 Redis 7 (docker)        · 12 MB        │   │ │
│  │  │  📊 dev-monitoring 🟢 prom + grafana (compose) · 145 MB     │   │ │
│  │  │                                          [→ Voir toutes]      │   │ │
│  │  │  ──────────────────────────────────────────────────────       │   │ │
│  │  │  💡 Pour piloter ces Apps (start/stop/update/sauvegarder),    │   │ │
│  │  │     basculer sur la vue Host de cette même Machine.           │   │ │
│  │  │  [→ Gérer comme Host]                                          │   │ │
│  │  └─────────────────────────────────────────────────────────────┘  │ │
│  │                                                                     │ │
│  │  ┌─ Snapshots récents (2) ────────────────────────────────────┐   │ │
│  │  │  📸 clean-install   2026-03-28 10:00 · 1.2 GB     [⟲]      │   │ │
│  │  │  📸 before-update   2026-04-29 15:30 · 0.8 GB     [⟲]      │   │ │
│  │  │                                          [+ Nouveau snapshot]│   │ │
│  │  └────────────────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

**Convergence avec les autres familles :**

| Élément | Détail App (Écran 3) | Détail Machine (ici) | Détail Host (Écran 18) |
|---------|----------------------|------------------------|-------------------------|
| Squelette | Header + Action bar + Tabs | Identique | Identique |
| Barre d'action | 5 verbes + `[⋯]` | 5 verbes + `[⋯]` | 5 verbes + `[⋯]` |
| Onglet 1 | Aperçu | Aperçu | Aperçu |
| Onglet 2+ | Logs, Console, Métriques, Sauvegardes | Console VNC, Métriques, Disques, Réseau, Snapshots, Hardware | Apps déployées, Machines hébergées, Services système, Métriques |
| Dernier onglet | Config | Config | Config |

L'utilisateur reconnaît la grammaire visuelle. Les onglets et leur contenu reflètent la nature de la famille — mais leur position et leur ordre suivent le même schéma (Aperçu en premier, Config en dernier).

**L'onglet "Apps hébergées"** est conditionnel : il n'apparaît que si la Machine a un moteur container détecté (Docker, Podman, k8s). Sans moteur, l'onglet n'est pas montré.

**Menu contextuel `[⋯ Plus]` pour cette Machine (extrait section "Avancé (KVM)") :**

```
── Avancé (KVM) ──
📋  Cloner cette Machine
📦  Convertir en template
📈  Redimensionner un disque…           (submenu)
🖥  Console VNC plein écran
🔁  Migrer vers un autre Host           (live migration si possible)
📥  Importer/exporter qcow2
</> Éditer la définition libvirt (XML)   (advanced)
```

---

## Écran 15 : Snapshots VM (arbre)

Inspiré de **Proxmox** (arbre de snapshots) et **VMware vSphere** (gestion graphique des snapshots). Spécifique famille Machines.

```
┌─ Snapshots : ubuntu-dev ─────────────────────────────────────────────────┐
│                                                                          │
│  🖥️ ubuntu-dev                                       [+ Nouveau snapshot]│
│                                                                          │
│  Mode : [⊞ Arbre]  [☰ Liste plate]   Vue : [Tous] [Adopté] [Cassé]      │
│                                                                          │
│  ── Arbre de snapshots ────────────────────────────────────────────     │
│                                                                          │
│  📌  État actuel (running)                                               │
│  │                                                                       │
│  ├─ 📸  clean-install                              2026-03-28 10:00     │
│  │      Snapshot froid · 1.2 GB · Description : "Capture après          │
│  │      installation initiale, cloud-init terminé"                       │
│  │      [⟲ Restaurer]  [📋 Cloner machine depuis]  [📦 → Template]  [🗑]│
│  │                                                                       │
│  └─ 📸  before-update                              2026-04-29 15:30     │
│         Snapshot chaud (RAM incluse) · 0.8 GB                            │
│         Description : "Avant mise à jour kernel 5.15 → 6.1"             │
│         [⟲ Restaurer]  [📋 Cloner machine depuis]  [🗑]                  │
│         │                                                                │
│         └─ 📸  after-broken-kernel-update          2026-04-30 09:15     │
│                Snapshot froid · 0.3 GB · État cassé                      │
│                Description : "Test reverted — kernel 6.1 ne boote pas"  │
│                [⟲ Restaurer]  [🗑]                                       │
│                                                                          │
│  ⚠ La chaîne `before-update → after-broken-kernel-update` dépasse 2     │
│    niveaux. Pour la performance I/O, considérer la consolidation avec   │
│    un backup complet (plugin Restic) puis la suppression de la chaîne.  │
└──────────────────────────────────────────────────────────────────────────┘
```

**Nouveau snapshot — modal :**

```
┌─ Nouveau snapshot : ubuntu-dev ──────────────────────────────────────────┐
│                                                                          │
│  Nom *           [_______________________]                              │
│  Description     [_______________________]                              │
│                  [_______________________]                              │
│                                                                          │
│  Type            ● Chaud (avec mémoire)  · 1-2 minutes · ~RAM Go        │
│                  ◯ Froid (disques seuls) · 30s · plus léger             │
│                                                                          │
│  Compression     [▼ zstd (recommandé)  ]                                │
│                                                                          │
│  💡 Un snapshot chaud capture l'état exact (processus en cours, RAM).   │
│     Un snapshot froid n'a que les disques — utile pour une sauvegarde   │
│     rapide.                                                              │
│                                                                          │
│                                       [Annuler]  [Créer le snapshot]   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Écran 16 : Hardware Editor (Machine)

Spécifique famille Machines. Inspiré de **Proxmox** (édition hardware par sections) et **VirtualBox** (panneaux).

```
┌─ Hardware : ubuntu-dev ──────────────────────────────────────────────────┐
│                                                                          │
│  ⚠ Cette Machine est en cours d'exécution. La plupart des changements   │
│    nécessitent un redémarrage pour être appliqués (indiqué par ↻).      │
│                                                                          │
│  ┌─ CPU & Mémoire ─────────────────────────────────────────────────┐   │
│  │  vCPU       [ - ] 2 [ + ] cores                          ↻       │   │
│  │  Modèle CPU [▼ host-passthrough              ]           ↻       │   │
│  │  RAM        [ - ] 2048 [ + ] MB                                   │   │
│  │  Ballooning  ✓ activé (alloué dynamiquement)                      │   │
│  │  NUMA        ✗ désactivé                                ↻ avancé │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─ Disques (1) ──────────────────────────────────────────────────────┐ │
│  │  vda · qcow2 · 20 GB · monté sur /                                 │ │
│  │   ├ Bus       virtio       Cache  writeback                         │ │
│  │   ├ Discard   ✓ (TRIM)     SSD emulation  ✓                         │ │
│  │   └ [📈 Resize] [💾 Sauvegarder] [📂 Parcourir] [🗑 Détacher]       │ │
│  │                                                                     │ │
│  │  [+ Ajouter un disque]   [+ Monter une ISO]                         │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌─ Interfaces réseau (1) ────────────────────────────────────────────┐ │
│  │  eth0 · virtio · MAC 52:54:00:af:12:38 · IP 192.168.1.55           │ │
│  │   ├ Bridge   [▼ vmbr0 (LAN principal)  ]                ↻          │ │
│  │   ├ Modèle   [▼ virtio                  ]                ↻          │ │
│  │   ├ Firewall ✓ règles libvirt actives                              │ │
│  │   └ [🗑 Retirer]                                                    │ │
│  │                                                                     │ │
│  │  [+ Ajouter une interface]                                          │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌─ Périphériques (avancé) ───────────────────────────────────────────┐ │
│  │  ◯ Aucun  ● Sélectionner                                            │ │
│  │  USB         pas de pass-through configuré       [+ Ajouter]         │ │
│  │  PCI         pas de pass-through configuré       [+ Ajouter]         │ │
│  │  GPU         pas de pass-through configuré       [+ Ajouter]         │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌─ Firmware ─────────────────────────────────────────────────────────┐ │
│  │  Type         ◯ BIOS (SeaBIOS)   ● EFI (OVMF)            ↻         │ │
│  │  Secure Boot  ✗ désactivé                                ↻          │ │
│  │  TPM 2.0      ✗ désactivé                                ↻          │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  Légende : ↻ nécessite un redémarrage                                   │
│                                                                          │
│       [Annuler]  [Sauvegarder]  [Sauvegarder + Redémarrer maintenant]   │
└──────────────────────────────────────────────────────────────────────────┘
```

**Mode Infra ciblé** : un toggle `[</> Vue native (XML libvirt)]` en haut bascule l'écran sur l'éditeur XML direct (Monaco editor avec coloration syntaxique).

---

## Écran 17 : Liste Hosts (famille Hosts)

Inspiré de **Coolify** (cards de serveurs avec métriques) et **Proxmox** (cluster view avec nodes). Détaille les 5 types de Hosts possibles.

```
┌─ Hosts ───────────────────────────────────────[+ Ajouter un Host]───────┐
│                                                                          │
│  Mes Hosts (5)              [▼ Tous types] [▼ Tous statuts]              │
│                                                                          │
│  ┌─ 🖧 local (RPi 4) ───────────────────────── 🟢 Online · 15j ───────┐│
│  │  Type : Baremetal SSH · arm64 · Ubuntu 22.04                         ││
│  │  CPU 38% · RAM 1.2/4 GB · Disque 28/64 GB · 🌡 52°C                  ││
│  │  Moteurs : 🐳 Docker ✓  ✗ libvirt  ✗ k8s                              ││
│  │  Héberge : 3 Apps · 0 Machines · 5 services système (1 adopté)      ││
│  │                                                                       ││
│  │  [📊 Détails] [🖥 SSH] [📋 journalctl]                            [⋯]││
│  └──────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ┌─ 🖧 nas-server ─────────────────────────── 🟢 Online · 47j ───────┐│
│  │  Type : Baremetal SSH · x86_64 · Ubuntu 22.04                       ││
│  │  CPU 12% · RAM 4.8/16 GB · Disque 1.2/4 TB · 🌡 38°C                ││
│  │  Moteurs : 🐳 Docker ✓  ✅ libvirt ✓  ✗ k8s                          ││
│  │  Héberge : 5 Apps · 3 Machines · 8 services système (2 adoptés)     ││
│  │                                                                       ││
│  │  [📊 Détails] [🖥 SSH] [📋 journalctl]                            [⋯]││
│  └──────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ┌─ 🖧 ubuntu-dev ──────────────────────────── 🟢 Online · 3j ─────────┐│
│  │  Type : Baremetal (Machine sur nas-server)                          ││
│  │  💡 Aussi une Machine [→ Voir comme Machine]                         ││
│  │  Ubuntu 22.04 · 2 vCPU · 1.8/2 GB RAM                                ││
│  │  Moteurs : 🐳 Docker ✓  ✗ libvirt  ✗ k8s                              ││
│  │  Héberge : 3 Apps · 0 sous-Machines                                   ││
│  │                                                                       ││
│  │  [📊 Détails] [🖥 SSH] [→ Voir comme Machine]                    [⋯] ││
│  └──────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ┌─ 🖧 k3s-cluster ───────────────────────── 🟢 Online · 3 nodes ─────┐│
│  │  Type : Kubernetes (k3s v1.28.5) · 3 nodes amd64                   ││
│  │  Total : CPU 22% · RAM 8.4/24 GB · 23 pods · 4 namespaces           ││
│  │  Moteurs : ✗ Docker (containerd interne)  ✗ libvirt  ✅ k3s + helm  ││
│  │  Héberge : 2 Apps (helm releases) · 0 Machines                       ││
│  │                                                                       ││
│  │  [📊 Détails] [🖥 kubectl] [📋 events]                            [⋯]││
│  └──────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ┌─ 🖧 prox-home ──────────────────────────── 🔴 Unreachable ─────────┐│
│  │  Type : Proxmox VE 8.1 · cluster 2 nodes                            ││
│  │  Pas de connexion depuis 2h17min · Dernière erreur : timeout API    ││
│  │  Dernière vue : CPU 8% · 22/64 GB RAM · 15 VMs · 4 LXC              ││
│  │                                                                       ││
│  │  [🔄 Réessayer] [📊 Détails (dernière vue)]                       [⋯]││
│  └──────────────────────────────────────────────────────────────────────┘│
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**Points clés de la famille Hosts :**

- **Barre d'action canonique** : `[📊 Détails]` `[🖥 SSH/kubectl]` `[📋 journalctl/events]` `[⋯]`. Pas de Lifecycle (un Host n'a pas d'état "off" géré par WindFlow), pas de Snapshot, pas de Hardware. Les actions ont une sémantique d'**administration**, pas de gestion.
- **Status pill** : `🟢 Online` / `🟠 Degraded` / `🔴 Unreachable` / `🔵 Scanning` / `⚪ Offline (planifié)`.
- **5 types de Hosts visuellement distinguables** :
  - **Baremetal SSH** — machine physique ou VM directement accessible
  - **Baremetal (Machine sur ...)** — cas récursif : une Machine qui est aussi Host
  - **Kubernetes** — cluster k8s/k3s/microk8s
  - **Proxmox VE** — serveur ou cluster Proxmox accessible via API
  - **Docker distant** — daemon Docker accessible SSH/TCP (non illustré, similaire au baremetal)
- **Affichage des moteurs détectés** : `🐳 Docker` / `✅ libvirt` / `✅ k3s + helm` / etc. avec ✓ ou ✗ pour montrer ce qui est installé. Détermine ce qui peut être déployé.
- **Compteurs `Héberge : X Apps · Y Machines · Z services système`** : donne immédiatement la richesse de chaque Host.
- **Cas récursif** : `ubuntu-dev` apparaît dans la liste Hosts avec une note `💡 Aussi une Machine`. Le bouton `[→ Voir comme Machine]` bascule vers la vue Machine (Écran 14) du même objet.
- **Host unreachable** : actions réduites (Réessayer + Détails sur dernière vue). Pas d'actions destructives possibles.

---

## Écran 18 : Détail Host (baremetal)

Cas standard : un host baremetal SSH qui héberge à la fois des Apps et des Machines.

```
┌─ Détail Host : nas-server ───────────────────────────────────────────────┐
│                                                                          │
│  🖧 nas-server                🟢 Online (uptime 47j)        [🖥 SSH]    │
│  Mini PC x86_64 · Ubuntu 22.04 · 16 GB RAM · 4 TB stockage              │
│  Moteurs : 🐳 Docker 24.0.7 ✓  ✅ libvirt 9.0 ✓  ✗ Kubernetes           │
│                                                                          │
│  [🖥 SSH] [📊 Métriques] [📋 journalctl] [📦 Packages] [⚙ Config]    [⋯]│
│                                                                          │
│  ┌Aperçu┬Apps déployées┬Machines hébergées┬Services système┬Métriques─┐ │
│  │       ┴Stockage┬Réseau┬Config                                      │ │
│  │                                                                     │ │
│  │  ── Aperçu (actif) ──                                              │ │
│  │                                                                     │ │
│  │  ┌─ Hardware ──────────────────────────────────────────────────┐ │ │
│  │  │  CPU           Intel N100 (4 cores @ 3.4 GHz) · x86_64       │ │ │
│  │  │  RAM           16 GB DDR4-3200                               │ │ │
│  │  │  Stockage      4 TB NVMe Samsung 980 Pro                     │ │ │
│  │  │  Réseau        1 Gb ethernet enp1s0                           │ │ │
│  │  │  Accélération  Intel QSV ✓ (transcoding)  ·  vt-x ✓          │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                     │ │
│  │  ┌─ Ressources live ───────────────────────────────────────────┐ │ │
│  │  │  CPU           ██░░░░░░░░ 12%   (charge 1m : 0.48)          │ │ │
│  │  │  RAM           ███░░░░░░░ 4.8 / 16 GB                       │ │ │
│  │  │  Disque /      ███░░░░░░░ 1.2 / 4 TB                         │ │ │
│  │  │  Température   🌡 38°C   ·   Conso ⚡ 12W                   │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                     │ │
│  │  ┌─ Apps déployées sur ce Host (5) ────────────────────────────┐ │ │
│  │  │  ☁️ Nextcloud     🟢 docker_compose · 342 MB                  │ │ │
│  │  │  🐙 Gitea          🟢 docker_compose · 189 MB                  │ │ │
│  │  │  🎬 Jellyfin       🟢 docker_container · 456 MB · GPU passthrough│ │ │
│  │  │  🔀 Traefik        🟢 docker_container · 142 MB                │ │ │
│  │  │  📊 Uptime Kuma    🟢 docker_container · 98 MB                 │ │ │
│  │  │                                          [→ Voir toutes (5)]   │ │ │
│  │  │  [+ Déployer une nouvelle App ici]                              │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                     │ │
│  │  ┌─ Machines hébergées (3) ────────────────────────────────────┐ │ │
│  │  │  🖥️ ubuntu-dev      🟢 KVM · Ubuntu 22.04 · 2 GB              │ │ │
│  │  │     └─ aussi Host pour 3 Apps internes  [→ Voir comme Host]   │ │ │
│  │  │  🖥️ pfsense-router 🟢 KVM · pfSense 2.7 · 512 MB              │ │ │
│  │  │  🖥️ windows-legacy  ⚪ KVM · Windows Server 2019 · 8 GB        │ │ │
│  │  │                                          [→ Voir toutes (3)]   │ │ │
│  │  │  [+ Créer une nouvelle Machine ici]                             │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                     │ │
│  │  ┌─ Services système (12 dont 2 adoptés) ─────────────────────┐ │ │
│  │  │  🟢 nginx.service       Adopté → "Nginx Web" (App)           │ │ │
│  │  │  🟢 postgresql.service  Adopté → "PG Direct" (App)           │ │ │
│  │  │  🟢 ssh.service                                              │ │ │
│  │  │  🟢 docker.service                                           │ │ │
│  │  │  🟢 libvirtd.service                                          │ │ │
│  │  │                                          [→ Voir tous (12)]   │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                     │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

**Convergence et originalités :**

- **Squelette identique** : header, action bar, onglets canoniques (Aperçu en premier, Config en dernier).
- **Onglets conditionnels** : "Machines hébergées" n'apparaît que si `libvirt` ou un autre moteur de virtualisation est détecté. "Apps déployées" n'apparaît que si Docker/Podman ou un client k8s est détecté.
- **Boutons de création contextuels** `[+ Déployer une App ici]` et `[+ Créer une Machine ici]` : lancent les wizards correspondants en pré-sélectionnant ce Host comme cible. Évite à l'utilisateur de devoir naviguer ailleurs.
- **Services système avec statut d'adoption** : on voit quels services sont gérés par WindFlow comme App (`adopté → "X" (App)`) vs simplement observés.

---

## Écran 19 : Détail Host (cas récursif : Machine-as-Host)

Une Machine virtuelle qui possède Docker installé devient aussi un Host. La même entité a deux projections : Machine (Écran 14) et Host (ici). Le contexte de la page indique clairement que c'est un cas particulier.

```
┌─ Détail Host : ubuntu-dev ───────────────────────────────────────────────┐
│                                                                          │
│  🖧 ubuntu-dev (Host)         🟢 Online (3 jours)            [🖥 SSH]   │
│  Sur : nas-server  ·  IP : 192.168.1.55  ·  Ubuntu 22.04 · 2 vCPU · 2 GB│
│  💡 Aussi une Machine [→ Gérer comme Machine]                            │
│  Moteurs : 🐳 Docker 24.0.7 ✓  ✗ libvirt  ✗ k8s                          │
│                                                                          │
│  [🖥 SSH] [📊 Métriques] [📋 journalctl] [📦 Packages] [⚙ Config]    [⋯]│
│                                                                          │
│  ┌Aperçu┬Apps déployées┬Services système┬Métriques┬Stockage┬Config ──┐  │
│  │      (pas d'onglet "Machines hébergées" : pas de moteur VM)        │ │
│  │                                                                     │ │
│  │  ── Aperçu (actif) ──                                              │ │
│  │                                                                     │ │
│  │  ┌─ Substrat de cette instance ───────────────────────────────┐  │ │
│  │  │  Cette entité est une Machine virtuelle KVM hébergée sur   │  │ │
│  │  │  le Host `nas-server`. Elle a Docker installé dedans, ce   │  │ │
│  │  │  qui permet à WindFlow de la gérer aussi comme un Host.    │  │ │
│  │  │                                                             │  │ │
│  │  │  Pour modifier le matériel (CPU, RAM, snapshots, hardware) │  │ │
│  │  │  ou le cycle de vie matériel (power on/off) :              │  │ │
│  │  │  [→ Gérer comme Machine]                                    │  │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                     │ │
│  │  ┌─ Ressources live (vues de l'intérieur) ─────────────────────┐ │ │
│  │  │  CPU       █░░░░░░░░░ 8%   (charge 1m : 0.15)              │ │ │
│  │  │  RAM       █████████░ 1.8 / 2 GB                            │ │ │
│  │  │  Disque /  ████░░░░░░ 8.2 / 20 GB                           │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                     │ │
│  │  ┌─ Apps déployées dans ce Host (3) ──────────────────────────┐ │ │
│  │  │  ☁️ dev-postgres    🟢 docker_container · 89 MB              │ │ │
│  │  │  🔴 dev-redis       🟢 docker_container · 12 MB              │ │ │
│  │  │  📊 dev-monitoring  🟢 docker_compose · 145 MB              │ │ │
│  │  │                                                              │ │ │
│  │  │  [+ Déployer une nouvelle App ici]                           │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  │                                                                     │ │
│  │  ┌─ Services système (5) ──────────────────────────────────────┐ │ │
│  │  │  🟢 ssh.service                                              │ │ │
│  │  │  🟢 docker.service                                           │ │ │
│  │  │  🟢 systemd-resolved.service                                 │ │ │
│  │  │  🟢 cron.service                                             │ │ │
│  │  │  🟢 systemd-timesyncd.service                                │ │ │
│  │  └─────────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

**Points clés du cas récursif :**

- **Identité dual** : la même entité apparaît dans la liste Machines (focus matériel) ET dans la liste Hosts (focus déploiements). Les deux pages partagent l'identité mais ont des onglets et un focus différents.
- **Navigation croisée** : le bouton `[→ Gérer comme Machine]` dans le header bascule vers l'autre projection. Réciproquement, le détail Machine a `[→ Gérer comme Host]`.
- **Carte "Substrat de cette instance"** : remplace la card "Hardware" de l'écran Host baremetal. Indique clairement que c'est une VM et où elle vit physiquement.
- **Pas d'onglet "Machines hébergées"** : une VM peut techniquement nested-virtualiser, mais sans libvirt détecté, l'onglet est absent. Si l'utilisateur active la virtualisation imbriquée, l'onglet apparaîtrait automatiquement.
- **Sémantique cohérente** : "Apps déployées dans ce Host" — du point de vue de l'utilisateur, les Apps sont déployées dans `ubuntu-dev`, peu importe que celui-ci soit lui-même une VM sur `nas-server`. L'oignon des couches reste navigable.

---

## Écran 20 : Wizard "Ajouter un Host"

Inspiré de **Coolify** (wizard d'ajout de serveur SSH) et **Proxmox** (datacenter join wizard).

### Étape 1 — Choix du type

```
┌─ Ajouter un Host ────────────────────────────────────────────────────────┐
│                                                                          │
│  ○────●────○────○                                                       │
│  Type Connexion Tester Confirmer                                        │
│                                                                          │
│  Étape 1 — Quel type de Host souhaitez-vous ajouter ?                   │
│                                                                          │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐         │
│  │ 🖧 Baremetal SSH │ │ 🖥️ Proxmox VE    │ │ ⎈ Kubernetes     │         │
│  │                  │ │                  │ │                  │         │
│  │ Machine          │ │ Serveur ou       │ │ Cluster k8s,     │         │
│  │ physique ou VM   │ │ cluster Proxmox  │ │ k3s ou microk8s  │         │
│  │ accessible SSH   │ │ VE accessible    │ │ accessible via   │         │
│  │                  │ │ via son API      │ │ kubeconfig       │         │
│  │ Pour : NAS, RPi, │ │                  │ │                  │         │
│  │ VPS, mini-PC...  │ │ Pour : homelab   │ │ Pour : cluster   │         │
│  │                  │ │ multi-VMs, edge  │ │ géré ou cloud    │         │
│  │ [Choisir]        │ │ [Choisir]        │ │ [Choisir]        │         │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘         │
│                                                                          │
│  ┌──────────────────┐                                                   │
│  │ 🐳 Docker        │                                                   │
│  │    distant       │                                                   │
│  │                  │                                                   │
│  │ Daemon Docker    │                                                   │
│  │ accessible par   │                                                   │
│  │ SSH ou TCP TLS   │                                                   │
│  │                  │                                                   │
│  │ Pour : Docker    │                                                   │
│  │ Engine seul      │                                                   │
│  │ [Choisir]        │                                                   │
│  └──────────────────┘                                                   │
│                                                                          │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Étape 2 — Configuration (cas baremetal SSH)

```
┌─ Ajouter un Host (baremetal SSH) ────────────────────────────────────────┐
│                                                                          │
│  ●────●────○────○                                                       │
│  Type Connexion Tester Confirmer                                        │
│                                                                          │
│  Étape 2 — Connexion SSH                                                │
│                                                                          │
│  ┌─ Identification ──────────────────────────────────────────────┐     │
│  │  Nom *           [nas-server-2                  ]              │     │
│  │  Description     [NAS de backup                  ]              │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                                                          │
│  ┌─ Connexion ───────────────────────────────────────────────────┐     │
│  │  Hôte / IP   *   [192.168.1.51                  ]              │     │
│  │  Port SSH        [22         ]                                  │     │
│  │  Utilisateur *   [deploy                        ]              │     │
│  │                                                                  │     │
│  │  Authentification  ● Clé SSH    ◯ Mot de passe                  │     │
│  │                                                                  │     │
│  │  Clé privée      [▼ ~/.ssh/windflow_id_ed25519  ]              │     │
│  │                  ou [📋 Coller une clé privée…]                  │     │
│  │                                                                  │     │
│  │  ✓ Vérifier que l'utilisateur peut sudo sans mot de passe       │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                                                          │
│  ┌─ Options de scan ─────────────────────────────────────────────┐     │
│  │  ✓ Détecter automatiquement les moteurs installés              │     │
│  │  ✓ Découvrir les containers/VMs non gérés (pour adoption)      │     │
│  │  ✓ Scanner périodiquement (toutes les 5 minutes)               │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                                                          │
│                       [← Retour]      [Tester la connexion →]          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Étape 3 — Tester et détecter

```
┌─ Ajouter un Host — Test & détection ─────────────────────────────────────┐
│                                                                          │
│  ●────●────●────○                                                       │
│  Type Connexion Tester Confirmer                                        │
│                                                                          │
│  Étape 3 — Test et détection des moteurs                                │
│                                                                          │
│  ✓ Connexion SSH établie (1.2s)                                          │
│  ✓ Authentification réussie (clé Ed25519)                                │
│  ✓ Sudo sans mot de passe vérifié                                        │
│                                                                          │
│  ── Hardware détecté ───────────────────────────────────────────────    │
│  CPU         AMD Ryzen 5 5500U (6 cores @ 2.1 GHz) · x86_64              │
│  RAM         32 GB DDR4                                                  │
│  Stockage    8 TB (1× NVMe 2 TB + 1× HDD 6 TB) · 2.4 TB utilisés        │
│  OS          Debian 12 (bookworm) · kernel 6.1.0-17                     │
│                                                                          │
│  ── Moteurs détectés ───────────────────────────────────────────────    │
│  🐳 Docker            ✓ détecté (version 24.0.7)                        │
│  ✅ libvirt/KVM       ✓ détecté (version 9.0.0, 8 VMs définies)         │
│  ✗ LXD                non installé                                       │
│  ✗ Incus              non installé                                       │
│  ✗ Kubernetes         non installé                                       │
│                                                                          │
│  ── Objets découverts (non gérés par WindFlow) ─────────────────────    │
│  📦  5 containers Docker en cours d'exécution                            │
│  📚  2 fichiers compose détectés (dans /opt/stacks/)                    │
│  🖥️  1 VM libvirt en cours d'exécution                                  │
│  ⚙  12 services systemd actifs (hors WindFlow-related)                  │
│                                                                          │
│  💡 Après l'ajout du Host, un wizard d'adoption vous proposera          │
│     d'importer les objets découverts dans WindFlow.                      │
│                                                                          │
│                       [← Retour]      [Ajouter le Host →]              │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Écran 21 : Adoption d'objets découverts

Apparaît automatiquement après l'ajout d'un Host (Écran 20), ou peut être déclenché manuellement depuis le détail Host onglet "Découverts".

```
┌─ Adopter des objets découverts sur nas-server-2 ─────────────────────────┐
│                                                                          │
│  WindFlow a détecté 8 objets non gérés sur ce Host.                     │
│  Vous pouvez les adopter pour les piloter depuis WindFlow.              │
│                                                                          │
│  Filtrer : [Tous] [Apps] [Machines] [Services]                          │
│  [Tout sélectionner] [Tout désélectionner]                              │
│                                                                          │
│  ── Apps : containers Docker (3) ──────────────────────────────────     │
│  ☐ 📦 plex            plex/plex:latest          running   1.2 GB         │
│       → Profil : docker_container · Adapter : DockerContainerAdapter    │
│       → Affecter à : [▼ Aucune stack (standalone)  ]                     │
│  ☐ 📦 sonarr          linuxserver/sonarr       running   245 MB          │
│  ☐ 📦 radarr          linuxserver/radarr       running   189 MB          │
│                                                                          │
│  ── Apps : stacks Compose (2) ────────────────────────────────────      │
│  ☐ 📚 immich          (3 services : server, db, redis)   running         │
│       → Path : /opt/stacks/immich/docker-compose.yml                    │
│       → Profil : docker_compose · Adapter : ComposeStackAdapter          │
│  ☐ 📚 vaultwarden     (1 service)              running   89 MB           │
│                                                                          │
│  ── Machines : VMs libvirt (1) ────────────────────────────────────     │
│  ☐ 🖥️ windows-vm     Windows 10 · 4 vCPU · 8 GB · 80 GB    running     │
│       → Profil : vm_kvm · Adapter : KVMAdapter                          │
│       → ⚠ Les snapshots existants seront importés                       │
│                                                                          │
│  ── Services système (à adopter comme Apps) (2) ────────────────────    │
│  ☐ ⚙ nginx.service                                                       │
│       → Nom proposé : "Nginx Web Server"  [Modifier]                     │
│       → Profil : app_native_service · Pas d'URL détectée [Configurer]   │
│  ☐ ⚙ samba.service                                                       │
│       → Nom proposé : "Samba Shares"      [Modifier]                     │
│                                                                          │
│  💡 Les objets non adoptés resteront visibles en lecture seule dans      │
│     l'onglet "Découverts" du détail Host. Vous pourrez les adopter       │
│     plus tard sans perte.                                                │
│                                                                          │
│                       [Plus tard]      [Adopter la sélection (0)]      │
└──────────────────────────────────────────────────────────────────────────┘
```

**Points clés :**

- **Sélection granulaire** : l'utilisateur choisit exactement ce qu'il veut adopter, item par item.
- **Catégorisation par famille de cible** : Apps containers / Apps compose / Machines / Services système — chaque ligne indique le profil WindFlow qui sera utilisé.
- **Métadonnées d'adoption éditables** : nom proposé, stack d'affectation, URL d'ouverture (pour les services système qui n'ont pas d'URL détectable, il faut la configurer manuellement).
- **Avertissements explicites** : "Les snapshots existants seront importés", "Cette opération ne casse pas le service existant", etc.
- **Non-destructif** : l'adoption est purement ajoutative. WindFlow prend connaissance de l'objet existant et l'enrichit avec ses métadonnées, sans rien modifier dans la réalité technique.
- **Adoption différable** : on peut sauter cette étape et adopter plus tard depuis l'onglet "Découverts" du Host.

---

## Direction Esthétique Révisée

### Inspiration Visuelle

Le design de WindFlow se positionne entre **Umbrel** (élégance, polish) et **Proxmox/Cosmos** (densité d'information, fonctionnalité). Plus précisément :

- **Élégance d'Umbrel** : Coins arrondis, espacement généreux, animations subtiles, wallpaper optionnel
- **Densité de Cosmos** : Métriques inline, actions accessibles, pas de perte d'espace
- **Transparence de Proxmox** : Montrer ce qui se passe (containers, réseaux, volumes), pas le cacher

### Typographie

- **UI / Corps** : Inter (lisible, technique, open source, large support de langues)
- **Code / Logs / Terminal** : JetBrains Mono (ligatures, lisible en petite taille)
- **Titres d'apps** : Inter Semi-Bold (pas besoin d'une display font pour un outil technique)

### Palette Thème Sombre (par défaut)

```
Fond principal     #0c0e14    (noir profond, comme un terminal moderne)
Fond carte/card    #151821    (léger relief)
Fond hover         #1c1f2b    (feedback subtil)
Bordures           #252838    (séparation douce)
Texte principal    #e2e5f0    (blanc cassé, confortable pour les yeux)
Texte secondaire   #7c8098    (gris moyen pour les métadonnées)
Accent bleu        #4f8ff7    (actions, liens, sélections)
Succès             #34d399    (vert menthe, moins agressif que le vert vif)
Erreur             #f87171    (rouge doux)
Warning            #fbbf24    (ambre)
Info               #60a5fa    (bleu clair)
```

### Palette Thème Clair

```
Fond principal     #f8f9fc
Fond carte/card    #ffffff
Bordures           #e5e7eb
Texte principal    #1f2937
Texte secondaire   #6b7280
Accent bleu        #3b82f6
```

### Composants Clés

- **Cards** : `border-radius: 12px`, `padding: 20px`, bordure subtile, pas d'ombre lourde (ombre douce 1px uniquement)
- **Boutons d'action** : Icône + texte pour les actions principales, icône seule pour les actions inline
- **Status dots** : 🟢 running (vert pulsant subtil), 🔴 stopped (rouge statique), 🟡 deploying (jaune clignotant)
- **Barres de progression** : Coins arrondis, dégradé subtil, pas de couleur vive uniforme — gradient du bleu accent vers le bleu clair
- **Toast notifications** : En haut à droite, auto-dismiss 5s, empilables

---

## Récapitulatif des Écrans

| # | Écran | Famille | Mode | Inspiré de | Innovation WindFlow |
|---|-------|---------|------|------------|---------------------|
| 1 | Dashboard | toutes | App | Umbrel + Runtipi | Grille icônes Apps + Machines épinglées + widgets plugins + agrégat Hosts |
| 2 | Liste Apps | Apps | App | Cloudron + Runtipi + Umbrel | Liste Apps quel que soit le profil, actions universelles |
| 3 | Détail App (générique) | Apps | App | Proxmox + Cosmos + Cloudron | Squelette commun à tous profils App, menu `[⋯ Plus]` peuplé par adapter |
| 3b | Détail Instance VM (convergent) | Machines | App | Proxmox + Incus | Vue d'origine, complétée et détaillée par les Écrans 13-16 |
| 4 | Marketplace | toutes | App | Umbrel + Runtipi | 3 onglets : Apps multi-backend, Machine Templates, Plugins |
| 5 | Wizard Installation App | Apps | App | Scaleway + Cloudron | Mini-wizard 2-3 questions, sélecteur d'adapter en "Options avancées" |
| 6 | Targets/Hosts (vue d'origine) | Hosts | App/Infra | Coolify + Proxmox | Vue d'origine, complétée et détaillée par les Écrans 17-21 |
| 7 | Volume Browser | Apps/Machines | App/Infra | CasaOS + Nextcloud | Preview inline, breadcrumbs, drag & drop |
| 8 | Console Unifiée | toutes | App | Proxmox + Incus | `[🖥 Console]` ouvre Terminal (App), VNC (Machine), SSH (Host) — même chrome UI |
| 9 | Plugins | — | App | Runtipi + Cosmos | Résumé d'activité par plugin, RAM totale |
| 10 | Activité | toutes | App | Cloudron + Umbrel | Journal chronologique avec actions directes |
| 11 | Onboarding | — | App | Umbrel + Cosmos | Détection auto du hardware, recommandation de profil |
| 11b | Wizard Création Manuelle | Apps/Machines | Infra | Proxmox + Incus | Wizard de création directe (sans marketplace) — Mode Infra |
| 12 | Vue Compute | toutes | Infra | Proxmox + Incus | Table par technologie : containers + VMs + snapshots agrégés multi-hosts |
| **13** | **Liste Machines** | **Machines** | **App** | **Proxmox + Incus** | **Cards de VMs avec power state, snapshots inline, note récursive pour les Machines-as-Host** |
| **14** | **Détail Machine** | **Machines** | **App** | **Proxmox + Incus** | **Squelette identique App ; onglets Aperçu/VNC/Disques/Réseau/Snapshots/Hardware ; onglet "Apps hébergées" conditionnel si Docker détecté** |
| **15** | **Snapshots VM (arbre)** | **Machines** | **App/Infra** | **Proxmox + VMware** | **Arbre interactif des snapshots avec descriptions, restauration en un clic, alerte sur chaînes longues** |
| **16** | **Hardware Editor** | **Machines** | **App/Infra** | **Proxmox + VirtualBox** | **Édition CPU/RAM/Disques/NIC/Firmware par sections, indicateur ↻ pour les changements nécessitant reboot, toggle vers XML libvirt** |
| **17** | **Liste Hosts** | **Hosts** | **App** | **Coolify + Proxmox** | **Cards avec hardware, moteurs détectés, compte Apps + Machines + services ; cas récursif explicite pour Machine-as-Host** |
| **18** | **Détail Host (baremetal)** | **Hosts** | **App** | **Coolify + Proxmox** | **Onglets Apps déployées + Machines hébergées + Services système ; boutons contextuels de création (Apps/Machines) pré-ciblés sur ce Host** |
| **19** | **Détail Host (récursif : Machine-as-Host)** | **Hosts** | **App** | **(spécifique WindFlow)** | **Vue Host d'une Machine qui contient Docker ; navigation croisée [→ Gérer comme Machine] ; onglets adaptés aux moteurs effectivement détectés** |
| **20** | **Wizard "Ajouter un Host"** | **Hosts** | **App** | **Coolify + Proxmox** | **Sélection type (Baremetal SSH / Proxmox / k8s / Docker remote) ; détection auto des moteurs et des objets adoptables ; preview avant validation** |
| **21** | **Adoption d'objets découverts** | **toutes** | **App** | **Proxmox (import VM) + Portainer** | **Adoption granulaire item-par-item ; édition des métadonnées (nom, URL, stack) ; non-destructif et différable** |
| — | Mobile | Apps | App | Umbrel (dock) | Dock fixe en bas, cards simplifiées |

**Note sur la cohabitation des écrans :** Les Écrans 3b et 6 (versions d'origine) restent dans le document à titre historique et de référence. Les Écrans 13-21 les complètent avec un niveau de détail aligné sur le modèle à trois familles. Lors de l'implémentation, les Écrans 13-16 remplacent fonctionnellement l'Écran 3b ; les Écrans 17-21 remplacent fonctionnellement l'Écran 6.

### Principes de convergence appliqués

| Principe | Outils de référence | Application WindFlow |
|----------|-------------------|---------------------|
| Trois familles distinctes | Proxmox VE (VMs/CTs/Nodes) | Apps, Machines, Hosts — chacune avec son mental model et vocabulaire |
| Grammaire UI partagée | Umbrel + Cloudron | Squelette de page, action bar, onglets, menus contextuels identiques entre familles |
| Convergence forte intra-famille | Harvester, Incus | Au sein d'Apps : Compose et Helm convergent ; au sein de Machines : KVM et LXD convergent |
| Profil = métadonnée invisible | Harvester (K8s sous le capot) | Le profil technique est caché en Mode App, révélé en Mode Infra ou via menu contextuel |
| WorkloadAdapter par profil | (Architecture WindFlow) | Un adapter traduit verbes universels → opérations natives. L'UI ne dépend d'aucun moteur |
| Menus contextuels peuplés par adapter | iOS, macOS (clic-droit app) | `[⋯ Plus ▾]` expose les actions spécifiques au profil sans casser l'abstraction de la famille |
| Hiérarchie Host → Apps + Machines | Proxmox (Datacenter → Node → VM/CT) | Chaque App et chaque Machine est hébergée par un Host. Le Host expose les Apps/Machines qu'il porte |
| Mêmes onglets canoniques par famille | Proxmox (VM/CT) | Apps : Aperçu/Logs/Console/Métriques/Sauvegardes/Config. Machines : Aperçu/VNC/Snapshots/Hardware. Hosts : Aperçu/Apps/Machines/Services |
| Marketplace par famille | Umbrel | 3 onglets : Apps (multi-backend), Machine Templates, Plugins |
| Métriques même format | Harvester | CPU/RAM/Net/I/O identiques toutes familles (issus de `adapter.get_metrics()`) |

---

**Références :**
- [Familles de Workloads et Adapters](11b-workload-families-and-adapters.md) — **Modèle directeur** : Apps, Machines, Hosts, WorkloadAdapter, ContextualActions, Mode App / Mode Infra
- [Fonctionnalités Principales](general_specs/10-core-features.md) — Features core derrière chaque écran
- [Modèle Compute](general_specs/12-compute-model.md) — Vue Compute par technologie (Mode Infra)
- [Architecture Modulaire](ARCHITECTURE-MODULAIRE.md) — Comment les plugins injectent pages et widgets
- [API Design](general_specs/07-api-design.md) — Endpoints REST par famille (`/apps`, `/machines`, `/hosts`)
- [Catalogue des Plugins](general_specs/09-plugins.md) — Plugins disponibles dans la marketplace
- [Systèmes de Virtualisation](../VIRTUALIZATION-SYSTEMS.md) — Couche Engine sur laquelle s'appuient les adapters
