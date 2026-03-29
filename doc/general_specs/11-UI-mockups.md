# Propositions de Maquettes d'Écran - WindFlow

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

### 1. Convergence Container / VM — Le Principe Fondateur

Inspiré d'Incus/LXD (unification totale) et Proxmox VE (convergence VMs + LXC) :

**Le type (container, VM, pod K8s) est un attribut, pas un paradigme.** Tout objet Compute est une **"Instance"** dans l'interface, avec les mêmes actions de base (Start, Stop, Restart, Console, Snapshot, Metrics) quelle que soit la technologie sous-jacente.

**Règle de convergence :**
- Si une action a du sens pour les containers ET les VMs → **même bouton, même emplacement, même comportement**
- Si une action est spécifique à un type → **elle apparaît en plus**, jamais à la place d'une action commune
- La barre d'actions d'une card Instance est la même pour tous les types : seules les icônes spécifiques changent (Terminal pour container, VNC pour VM)

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

### 2. Deux Modes d'Interface

Inspiré de Cosmos Server (mode simple vs admin) et Proxmox (vue simple vs vue complète) :

**Mode Standard** : Dashboard, Apps installées, Marketplace, Volumes, Settings. Suffisant pour 80% des utilisateurs.

**Mode Avancé** : Ajoute la vue Compute détaillée (instances individuelles, stacks, images), Targets, Réseaux, Audit. Pour les admins et les power users.

Le toggle est dans la sidebar (un bouton discret en bas). Le mode est mémorisé par utilisateur. Les Viewers voient toujours le mode Standard.

### 3. "Instance" comme Concept Central (Mode Standard : "Apps")

Inspiré de Cosmos, Cloudron et Incus : en mode Standard, tout ce qui est déployé (stack, container, VM) apparaît comme une **"App"** avec son icône, son domaine, son statut, et des actions convergentes. En mode Avancé, on voit la réalité technique : des **Instances** (containers, VMs, pods) regroupées en Stacks.

Les actions convergentes s'appliquent à tous les types :
- `[🖥 Console]` → Terminal xterm.js pour containers, VNC/noVNC pour VMs
- `[📋 Logs]` → Docker logs pour containers, serial console pour VMs
- `[📸 Snapshot]` → Docker commit pour containers, qcow2 snapshot pour VMs

### 4. Dashboard Type "Homepage"

Inspiré d'Umbrel (wallpaper + widgets) mais avec la densité d'information de Runtipi (métriques système + instances running). Le dashboard est le point d'entrée unique, personnalisable avec des widgets ajoutés par les plugins.

### 5. Wizard Everywhere

Inspiré de Scaleway et Cloudron : chaque action complexe (installer un plugin, déployer une stack, ajouter un target, créer une instance) passe par un **wizard par étapes** au lieu d'un formulaire monolithique. Le wizard de création d'Instance est unifié : le choix du type (Container / Stack / VM) est la première étape, les étapes suivantes s'adaptent.

### 6. Actions sans Navigation

Inspiré de Portainer, Runtipi et Proxmox : les actions courantes (start, stop, restart, console, logs, snapshot) sont accessibles **directement depuis les listes**, sans ouvrir le détail. Ces actions sont **les mêmes** pour les containers et les VMs. Le détail existe pour la configuration et le troubleshooting.

---

## Navigation Révisée

### Sidebar — Mode Standard

```
┌──────────────────────────┐
│  🌀 WindFlow              │
│                          │
│  🏠  Dashboard           │  ← Homepage personnalisable
│  📱  Apps                │  ← Tout ce qui est déployé (stacks, containers nommés)
│  🏪  Marketplace         │  ← Plugins + Stacks one-click
│  🔌  Plugins             │  ← Plugins installés + config
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
│  [🔧 Mode Avancé]       │  ← Toggle
│  🟢 local (arm64)        │
│  👤 admin                │
└──────────────────────────┘
```

### Sidebar — Mode Avancé (toggle activé)

```
┌──────────────────────────┐
│  🌀 WindFlow              │
│                          │
│  🏠  Dashboard           │
│  📱  Apps                │
│  🏪  Marketplace         │
│  🔌  Plugins             │
│                          │
│  COMPUTE                 │  ← Visible en mode avancé uniquement (cf. 12-compute-model.md)
│  ⚡  Compute             │  ← Vue unifiée : instances containers + VMs, par stack/standalone
│  📚  Stacks              │  ← Stacks WindFlow (compose, helm, mixtes)
│  🎯  Targets             │  ← Machines cibles (local, SSH, Proxmox)
│  💾  Stockage            │  ← Volumes Docker + disques VM + file browser
│  🌐  Réseaux             │  ← Networks Docker + bridges VM
│  🖼️  Images              │  ← Images Docker + ISOs / templates VM
│  📸  Snapshots           │  ← Snapshots VM (vue centralisée multi-machines)
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
│  [📱 Mode Standard]     │  ← Toggle retour
│  🟢 local (arm64)        │
│  👤 admin                │
└──────────────────────────┘
```

**Rationale** : Un self-hoster débutant qui veut juste installer Nextcloud et Jellyfin ne devrait jamais voir "Containers", "Networks", ou "Images". Un admin qui veut debug un container qui crashe a besoin de tout.

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

| # | Écran | Inspiré de | Innovation WindFlow |
|---|-------|------------|---------------------|
| 1 | Dashboard | Umbrel + Runtipi | Compteurs unifiés (instances containers + VMs), widgets plugins |
| 2 | Apps (vue unifiée) | Cloudron + Runtipi + Incus | Containers + Stacks + VMs dans la même liste, actions convergentes |
| 3 | Détail App / Container | Proxmox + Cosmos + Cloudron | Onglets dynamiques (plugins), backup inline, métriques live |
| 3b | Détail VM (convergent) | Proxmox + Incus | **Même structure d'onglets** que Container, Hardware + Snapshots |
| 4 | Marketplace | Umbrel + Runtipi | Recommandations contextuelles, ratings, séparation plugins/stacks |
| 5 | Wizard Installation | Scaleway + Cloudron | Résumé d'impact, options avancées cachées |
| 6 | Targets | Coolify + Proxmox | Cards métriques, température, bouton SSH |
| 7 | Volume Browser | CasaOS + Nextcloud | Preview inline, breadcrumbs, drag & drop |
| 8 | Console Unifiée | Proxmox + Incus | **Même page** pour Terminal (container) et VNC (VM), même chrome UI |
| 9 | Plugins | Runtipi + Cosmos | Résumé d'activité par plugin, RAM totale |
| 10 | Activité | Cloudron + Umbrel | Journal chronologique avec actions directes |
| 11 | Onboarding | Umbrel + Cosmos | Détection auto du hardware, recommandation de profil |
| 11b | Wizard Création Instance | Proxmox + Incus | **Wizard unifié** : choix Container/Stack/VM → config adaptée → déployer |
| 12 | Vue Compute (avancé) | Proxmox + Incus | **Table unifiée** TYPE/NOM/STATUS/CPU/RAM, stacks mixtes, vue par stack/machine |
| — | Mobile | Umbrel (dock) | Dock fixe en bas, cards simplifiées |

### Principes de convergence appliqués

| Principe | Outils de référence | Application WindFlow |
|----------|-------------------|---------------------|
| Instance = concept unique | Incus, Harvester | Container, VM et Pod K8s sont des "Instances" avec mêmes actions de base |
| Type = colonne, pas paradigme | Incus (`incus list`) | La colonne TYPE différencie, les actions sont convergentes |
| Mêmes onglets par instance | Proxmox (VM/CT) | Aperçu, Console, Métriques, Stockage, Réseau, Config — communs à tous |
| Même barre d'actions | Proxmox + Incus | `[Console] [Logs] [Stop] [Restart] [Snapshot] [Config]` — adaptés au type |
| Même wizard de création | Proxmox (Create VM/CT) | Étape 1 : choisir le type → étapes suivantes adaptées |
| Métriques même format | Harvester | CPU/RAM/Net/I/O identiques pour containers et VMs |

---

**Références :**
- [Fonctionnalités Principales](general_specs/10-core-features.md) — Features core derrière chaque écran
- [Architecture Modulaire](ARCHITECTURE-MODULAIRE.md) — Comment les plugins injectent pages et widgets
- [API Design](general_specs/07-api-design.md) — Endpoints consommés par chaque écran
- [Catalogue des Plugins](general_specs/09-plugins.md) — Plugins disponibles dans la marketplace
