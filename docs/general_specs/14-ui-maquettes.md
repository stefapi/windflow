# Chapitre 14 — Maquettes d'écrans

> **Statut** : Spec cible · **Public** : Développeurs frontend, designers, product · **Lié à** : [13-ui-principes.md](13-ui-principes.md), [02-familles-workloads.md](02-familles-workloads.md), [03-modele-compute.md](03-modele-compute.md)

## Vue d'ensemble

Ce chapitre présente les **27 écrans** de l'interface WindFlow, renumérotés et nettoyés de tout vestige. Chaque maquette est un bloc ASCII avec sa légende ; la grammaire UI (squelette, action bars, onglets canoniques) et la navigation de référence sont définies aux chapitres [02-familles-workloads.md](02-familles-workloads.md) et [13-ui-principes.md](13-ui-principes.md) — ce chapitre montre des instances concrètes. Les Écrans 20 et 21 sont rendus avec Vue Flow (chapitre [05-stack-technologique.md](05-stack-technologique.md)). Les Écrans 22 à 26 complètent le Mode Infra (Vue Compute, vues listes Stacks/Volumes/Networks/Images) et les écrans transverses (Settings, Login/SSO, Assistant IA) ; l'Écran 27 — **Clusters** — matérialise l'entité Cluster de premier rang (chapitre 02) : liste des grappes Kubernetes/Proxmox/Swarm, membres, santé, workloads hébergés. Une piste d'évolution — Écran E1, vue Réseaux éditable — est maquettée en fin de chapitre et ne renumérote pas les écrans livrés. Valeurs d'exemple cohérentes : Apps `nextcloud`, `gitea`, `jellyfin` ; Machines `ubuntu-dev`, `pfsense-router` ; Hosts `nas-server`, `pi4-home`, `prox-home` ; Clusters `k3s-cluster`, `prox-cluster`.

## Écran 1 — Dashboard (homepage)

Inspiré d'Umbrel (widgets) + Runtipi (métriques système). Grille d'Apps cliquables, widgets plugins repositionnables, widget natif « Dernière activité ».

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Sidebar │  Bonjour admin 👋             🎯 nas-server (x86_64)  🔔 2       │
│         │                                                                   │
│         │  ┌─ Système ──────────────────────────────────────────────────┐   │
│         │  │ CPU ████░░░░░░ 38%   RAM ██████░░░░ 4.8/16 GB              │   │
│         │  │ Disque ███░░░░░░░ 1.2/4 TB    Uptime: 47j                  │   │
│         │  │ 🟢 10 instances running (7 containers · 3 Machines) · 3 plugins │
│         │  └────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         │  ┌─ Apps ─────────────────────────────────────────────────────┐   │
│         │  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │   │
│         │  │  │  ☁️     │ │  🐙    │ │  🎬    │ │  🔀    │ │  📊    │  │   │
│         │  │  │Nextcloud│ │ Gitea  │ │Jellyfin│ │Traefik │ │ Kuma   │  │   │
│         │  │  │  🟢 UP  │ │ 🟢 UP  │ │ 🟢 UP  │ │ 🟢 UP  │ │ 🟢 UP  │  │   │
│         │  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘  │   │
│         │  │  cloud.example.com  git.example.com  media.example.com    │   │
│         │  │  (Traefik ✓)        (Traefik ✓)      (Traefik ✓)         │   │
│         │  └────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         │  ┌─ Widgets ─────────────────────────────────────────────────┐   │
│         │  │  ┌─ Uptime Kuma ─────┐  ┌─ Traefik ─────────────────┐    │   │
│         │  │  │  ✅ 5/5 services  │  │  🌍 3 domaines actifs     │    │   │
│         │  │  │  UP depuis 15j    │  │  🔒 3 certificats valides │    │   │
│         │  │  │  nextcloud ✅ 99% │  │  📊 1.2K req/h            │    │   │
│         │  │  └───────────────────┘  └───────────────────────────┘    │   │
│         │  │  ┌─ Restic ──────────┐  ┌─ Dernière activité ─────────┐   │   │
│         │  │  │  ✅ Backup: 6h    │  │  ✅ Nextcloud mis à jour(2h)│   │   │
│         │  │  │  📦 3 vol, 2.1 GB │  │  🔔 Certificat expire 30j   │   │   │
│         │  │  └───────────────────┘  └─────────────────────────────┘   │   │
│         │  └────────────────────────────────────────────────────────────┘   │
└─────────┴───────────────────────────────────────────────────────────────────┘
```

**Légende :** chaque App ouvre son UI native dans un nouvel onglet ; le domaine Traefik est affiché si le plugin est installé ; chaque plugin peut injecter un widget.

## Écran 2 — Liste Apps

Inspiré de Cloudron (apps avec domaine) + Runtipi (statut et actions inline). Vue principale de la famille Apps : tout ce qui est déployé apparaît, quel que soit le profil.

```
┌─ Apps ──────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  Mes Apps (5)            [Sur quel Host ? ▾]  [🔍]  [+ Nouvelle App]       │
│                                                                             │
│  ┌── Nextcloud ──────────────────────────────────────────────── 🟢 ─────┐  │
│  │  ☁️  Nextcloud 28.0.4                                                │  │
│  │  cloud.example.com (🔒 TLS)    Stack: nextcloud    Sur : nas-server  │  │
│  │  3 services: nginx, php-fpm, cron    RAM: 342 MB                     │  │
│  │  [🔗 Ouvrir]  [⏵ Lifecycle ▾]  [📋 Logs]  [🖥 Console]  [⚙ Config] [⋯]│ │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌── Jellyfin ───────────────────────────────────────────────── 🟢 ─────┐  │
│  │  🎬  Jellyfin 10.9.6                                                │  │
│  │  media.example.com (🔒 TLS)    Sur : nas-server    RAM: 456 MB       │  │
│  │  [🔗 Ouvrir]  [⏵ Lifecycle ▾]  [📋 Logs]  [🖥 Console]  [⚙ Config] [⋯]│ │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌── old-test-app ───────────────────────────────────────────── 🔴 ─────┐  │
│  │  📦  myapp:1.0       Arrêtée depuis 3 jours    Sur : nas-server      │  │
│  │  [▶ Start]  [📋 Logs]  [🗑 Supprimer]                             [⋯] │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** action bar canonique Apps (chapitre 02) — `[🔗 Ouvrir]` en premier (action la plus courante), split-button `[⏵ Lifecycle ▾]` (Start/Stop/Restart/Pause), badge `⬆` si mise à jour disponible, RAM visible (critique sur RPi). Badge d'origine sur chaque carte — `Managé` (discret, défaut) / `Adopté` / `Externe` (lecture seule) — traduction UI de la colonne `origin` (matrice profil × origine, chapitre [03-modele-compute.md](03-modele-compute.md)).

## Écran 3 — Détail App

Inspiré de Proxmox (onglets) + Cosmos (URL/routing) + Cloudron (backup + domain). Squelette invariant du chapitre 02 ; contenu adapté au profil par l'adapter.

```
┌─ Nextcloud ────────────────────────────────────────────────────────────────┐
│  ☁️ Nextcloud 28.0.4           🟢 Running (15 jours)       [🔗 Ouvrir]     │
│  cloud.example.com (🔒 TLS expire dans 89j)                                │
│  Sur : nas-server  │  RAM: 342 MB  │  CPU: 5%                              │
│                                                                            │
│  [🔗 Ouvrir] [⏵ Lifecycle ▾] [📋 Logs] [🖥 Console] [📸 Backup] [⚙ Config] [⋯]│
│                                                                            │
│  ┌ Aperçu ─┬ Logs ─┬ Console ─┬ Métriques ─┬ Sauvegardes ─┬ Config ────┐  │
│  │                                                                      │  │
│  │  ┌─ Services (3) ──────────────────────────────────────────────┐    │  │
│  │  │  nginx       nginx:alpine     🟢 running   80→80           │    │  │
│  │  │  php-fpm     nextcloud:28     🟢 running   9000            │    │  │
│  │  │  cron        nextcloud:28     🟢 running   —               │    │  │
│  │  └──────────────────────────────────────────────────────────────┘    │  │
│  │  ┌─ Ressources ────────────────────────────────────────────────┐    │  │
│  │  │  CPU  ██░░░░░░░░ 5%     RAM  ████░░░░░░ 342/512 MB        │    │  │
│  │  └──────────────────────────────────────────────────────────────┘    │  │
│  │  ┌─ Volumes ──────────────────────────────────────────────────┐     │  │
│  │  │  nextcloud_data    → /var/www/html        2.1 GB  [📂]    │     │  │
│  │  └──────────────────────────────────────────────────────────────┘    │  │
│  │  ┌─ Actions Plugin ───────────────────────────────────────────┐     │  │
│  │  │  🐘 PostgreSQL Manager : 2 databases, 3 users              │     │  │
│  │  │  [Créer une DB] [Créer un User] [Backup SQL] [Stats]      │     │  │
│  │  └──────────────────────────────────────────────────────────────┘    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** onglets canoniques Apps (Aperçu → Config), onglet « Domaine » ajouté par le plugin Traefik, actions contextuelles des plugins en bas de l'Aperçu. En Mode Infra : onglets additionnels « Composants techniques » (qui donne accès au Graphe de dépendances — Écran 20) et « Manifest ».

## Écran 4 — Marketplace

Inspiré d'Umbrel App Store + Runtipi (catégories) + Cloudron (apps vérifiées). Structure 3 onglets du chapitre [12-marketplace.md](12-marketplace.md).

```
┌─ Marketplace ──────────────────────────────────────────────────────────────┐
│  [🔍 Rechercher apps et plugins...]                                        │
│  [📱 Apps] [🖥️ Machine Templates] [🔌 Plugins]                              │
│                                                                            │
│  Catégories:                                                               │
│  [Tous] [🔀 Accès] [📊 Monitoring] [🐘 Bases de données] [💾 Backup]     │
│  [🔒 Sécurité] [🐙 Git] [✉️ Mail] [🤖 IA] [📡 Messagerie]                  │
│                                                                            │
│  ── Recommandés pour vous ──────────────────────────────────────────────  │
│  (basé sur votre config : pas de reverse proxy détecté)                    │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐           │
│  │  🔀  Traefik     │ │  📊 Uptime Kuma  │ │  💾 Restic       │           │
│  │  Reverse proxy   │ │  Monitoring de   │ │  Backup auto     │           │
│  │  avec HTTPS      │ │  disponibilité   │ │  des volumes     │           │
│  │  128 Mo • arm64 ✓│ │  98 Mo • arm64 ✓ │ │  64 Mo • arm64 ✓ │           │
│  │  [Installer]     │ │  [Installer]     │ │  [Installer]     │           │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘           │
│                                                                            │
│  ── Toutes les Apps ── (onglet Apps) ────────────────────────────────────  │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐           │
│  │  ☁️ Nextcloud     │ │  🐙 Gitea        │ │  🎬 Jellyfin     │           │
│  │  Cloud personnel │ │  Git self-hosted │ │  Streaming média │           │
│  │  512 Mo • arm64 ✓│ │  256 Mo • arm64 ✓│ │  512 Mo • arm64 ✓│           │
│  │  [Déployé ✅]    │ │  [Déployer]      │ │  [Déployer]      │           │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘           │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** compatibilité ARM et RAM toujours visibles ; badge « Extension » sur les plugins sans container ; ratings communautaires ; « Recommandés pour vous » basé sur l'état de l'infrastructure.

## Écran 5 — Wizard d'installation

Inspiré de Scaleway (wizard par étapes) + Cloudron (configuration simplifiée).

```
┌─ Installer Traefik ────────────────────────────────────────────────────────┐
│  ○───────●───────○                                                        │
│  Vérifier  Configurer  Installer                                          │
│                                                                            │
│  Étape 2 sur 3 — Configuration                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  Email Let's Encrypt *   [admin@example.com             ]           │  │
│  │  Dashboard Traefik       [✓ Activé]                                 │  │
│  │  ▸ Options avancées                                                 │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│  ┌─ Ce plugin va : ────────────────────────────────────────────────────┐  │
│  │  ✓ Déployer Traefik (1 container, ~128 Mo RAM)                      │  │
│  │  ✓ Ajouter la page « Domaines » dans le menu                        │  │
│  │  ✓ Utiliser les ports 80 et 443                                     │  │
│  │  ✓ Configurer automatiquement le routage des futures apps           │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                           [← Retour]  [Installer →]        │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** stepper visuel ; options avancées cachées par défaut (accordion) ; encadré « Ce plugin va » résumant l'impact (containers, RAM, ports).

## Écran 6 — Liste Machines

Inspiré de Proxmox VE (liste VMs) + Incus (`incus list`) + Scaleway (cards). Famille Machines — vocabulaire matériel.

```
┌─ Machines ────────────────────────────[🏪 Templates] [+ Nouvelle Machine]─┐
│  Filtres : [▼ Tout statut] [▼ Tout Host] [▼ Tout OS] [🔍]                 │
│                                                                            │
│  ┌─ 🖥️ ubuntu-dev ──────────────────────────── 🟢 Running ───────────┐   │
│  │  Ubuntu 22.04 LTS · KVM · 2 vCPU · 2 GB RAM · 20 GB                 │   │
│  │  Sur : nas-server  ·  IP : 192.168.1.55                             │   │
│  │  CPU 12% · RAM 1.8/2 GB · 📸 2 snapshots                            │   │
│  │  💡 Cette Machine héberge 3 Apps Docker  [→ Gérer comme Host]        │   │
│  │  [🔗 SSH] [⏵ Power ▾] [📸 Snapshot] [🖥 VNC] [⚙ Hardware]       [⋯]  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
│  ┌─ 🖥️ k3s-node-1 ──────────────────────────── 🟢 Running ───────────┐   │
│  │  Alpine 3.19 · LXC system container · 2 vCPU · 4 GB · 20 GB         │   │
│  │  Sur : prox-home  ·  IP : 192.168.1.61                              │   │
│  │  💡 Membre du cluster k3s-cluster (worker)  [→ Voir le cluster]      │   │
│  │  [🔗 SSH] [⏵ Power ▾] [📸 Snapshot] [🖥 Console] [⚙ Config]      [⋯]  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
│  ┌─ 🖥️ windows-legacy ────────────────────────── ⚪ Stopped ─────────┐   │
│  │  Windows Server 2019 · KVM · 4 vCPU · 8 GB · 80 GB                  │   │
│  │  Sur : nas-server  ·  Arrêtée depuis 12 jours                       │   │
│  │  📸 3 snapshots dont « before-patch-tuesday »                        │   │
│  │  [▶ Power on] [📸 Snapshots] [⚙ Hardware] [🗑]                   [⋯]  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** action bar canonique Machines — « Power » (pas « Lifecycle »), `Snapshot` canonique, `Hardware` au lieu de `Config`. Split-button `[⏵ Power ▾]` : Power on / Power off (ACPI) / Reboot / Reset / Pause / Suspend. Notes `💡` pour les cas particuliers ; Machines arrêtées → barre réduite aux actions hors-tension. La note `💡 Membre du cluster` pointe vers l'entité **Cluster** (Écran 27) — l'appartenance (`cluster_members`) est orthogonale à l'hébergement : cette Machine reste hébergée par son Host `prox-home` (chapitre 02).

## Écran 7 — Détail Machine

Inspiré de Proxmox (onglets identiques VM/CT) + Incus. Squelette identique au détail App — c'est la cohérence inter-familles.

```
┌─ Détail Machine : ubuntu-dev ─────────────────────────────────────────────┐
│  🖥️ ubuntu-dev                  🟢 Running (3 jours)          [🔗 SSH]    │
│  Ubuntu 22.04 LTS · KVM · IP : 192.168.1.55                                │
│  Sur : nas-server · CPU 12% · 1.8/2 GB RAM · 8.2/20 GB disque             │
│  💡 Cette Machine héberge 3 Apps  [→ Gérer comme Host]                     │
│                                                                            │
│  [🔗 SSH] [⏵ Power ▾] [📸 Snapshot] [🖥 VNC] [⚙ Hardware]              [⋯] │
│                                                                            │
│  ┌Aperçu┬Console VNC┬Métriques┬Disques┬Réseau┬Snapshots┬Hardware┬Config─┐ │
│  │                                                                     │ │
│  │  ┌─ Système ─────────────────────────────────────────────────┐     │ │
│  │  │  Type KVM/QEMU via libvirt · OS Ubuntu 22.04.3 LTS        │     │ │
│  │  │  Kernel 5.15.0-91-generic · Firmware EFI · hostname ubuntu-dev │ │
│  │  └────────────────────────────────────────────────────────────┘     │ │
│  │  ┌─ Ressources allouées ─────────────────────────────────────┐     │ │
│  │  │  CPU 2 vCPU · charge ██░░░░░░░░ 12%                       │     │ │
│  │  │  RAM 2 GB · utilisé █████████░ 1.8/2 GB                   │     │ │
│  │  │  Disque 20 GB qcow2 · utilisé ████░░░░░░ 8.2/20 GB        │     │ │
│  │  └────────────────────────────────────────────────────────────┘     │ │
│  │  ┌─ Apps hébergées dans cette Machine (3) ───────────────────┐     │ │
│  │  │  ☁️ dev-postgres   🟢 docker_container · 89 MB              │     │ │
│  │  │  🔴 dev-redis      🟢 docker_container · 12 MB              │     │ │
│  │  │  📊 dev-monitoring 🟢 docker_compose · 145 MB               │     │ │
│  │  │  💡 Pour piloter ces Apps, basculer sur la vue Host.       │     │ │
│  │  │  [→ Gérer comme Host]                                      │     │ │
│  │  └────────────────────────────────────────────────────────────┘     │ │
│  │  ┌─ Snapshots récents (2) ───────────────────────────────────┐     │ │
│  │  │  📸 clean-install   2026-03-28 10:00 · 1.2 GB      [⟲]     │     │ │
│  │  │  📸 before-update   2026-04-29 15:30 · 0.8 GB      [⟲]     │     │ │
│  │  │                                     [+ Nouveau snapshot]    │     │ │
│  │  └────────────────────────────────────────────────────────────┘     │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** onglets canoniques Machines (Aperçu en premier, Config en dernier). L'onglet « Apps hébergées » est **conditionnel** : il n'apparaît que si un moteur container est détecté sur la Machine. En Mode Infra : onglet « Définition libvirt (XML) ». Menu `[⋯ Plus]` section « Avancé (KVM) » : Cloner, Convertir en template, Redimensionner un disque, Migrer vers un autre Host, Importer/exporter qcow2, Éditer la définition libvirt.

## Écran 8 — Snapshots Machines (arbre)

Inspiré de Proxmox (arbre de snapshots) + vSphere. Vue dédiée multi-Machines (chapitre [03-modele-compute.md](03-modele-compute.md)).

```
┌─ Snapshots : ubuntu-dev ──────────────────────────────────────────────────┐
│  🖥️ ubuntu-dev                                       [+ Nouveau snapshot] │
│  Mode : [⊞ Arbre]  [☰ Liste plate]                                        │
│                                                                            │
│  📌  État actuel (running)                                                 │
│  │                                                                         │
│  ├─ 📸  clean-install                     2026-03-28 10:00                 │
│  │      Snapshot froid · 1.2 GB · « Capture après installation initiale »  │
│  │      [⟲ Restaurer]  [📋 Cloner depuis]  [📦 → Template]  [🗑]           │
│  │                                                                         │
│  └─ 📸  before-update                     2026-04-29 15:30                 │
│         Snapshot chaud (RAM incluse) · 0.8 GB                              │
│         « Avant mise à jour kernel 5.15 → 6.1 »                            │
│         [⟲ Restaurer]  [📋 Cloner depuis]  [🗑]                            │
│         │                                                                  │
│         └─ 📸  after-broken-kernel-update  2026-04-30 09:15                │
│                Snapshot froid · 0.3 GB · État cassé                        │
│                [⟲ Restaurer]  [🗑]                                         │
│                                                                            │
│  ⚠ La chaîne dépasse 2 niveaux — considérer une consolidation             │
│    (backup complet plugin Restic puis suppression de la chaîne).          │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** arbre de parenté interactif, restauration en un clic, alerte sur les chaînes longues (performances I/O, chapitre 03). Le modal « Nouveau snapshot » propose chaud (avec mémoire) ou froid (disques seuls) avec compression zstd recommandée.

## Écran 9 — Hardware Editor (Machine)

Inspiré de Proxmox (édition par sections) + VirtualBox (panneaux). Famille Machines.

```
┌─ Hardware : ubuntu-dev ──────────────────────────────────────────────────┐
│  ⚠ Machine en cours d'exécution — la plupart des changements            │
│    nécessitent un redémarrage (indiqué par ↻).                           │
│                                                                          │
│  ┌─ CPU & Mémoire ─────────────────────────────────────────────────┐   │
│  │  vCPU [ - ] 2 [ + ] cores  ↻      Modèle CPU [▼ host-passthrough] ↻│   │
│  │  RAM  [ - ] 2048 [ + ] MB        Ballooning ✓ activé              │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│  ┌─ Disques (1) ──────────────────────────────────────────────────────┐ │
│  │  vda · qcow2 · 20 GB · monté sur /                                 │ │
│  │   [📈 Resize] [💾 Sauvegarder] [📂 Parcourir] [🗑 Détacher]        │ │
│  │  [+ Ajouter un disque]   [+ Monter une ISO]                        │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│  ┌─ Interfaces réseau (1) ────────────────────────────────────────────┐ │
│  │  eth0 · virtio · MAC 52:54:00:af:12:38 · IP 192.168.1.55           │ │
│  │   Bridge [▼ vmbr0 (LAN principal)] ↻   [+ Ajouter une interface]    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│  ┌─ Firmware ─────────────────────────────────────────────────────────┐ │
│  │  Type ◯ BIOS (SeaBIOS)  ● EFI (OVMF) ↻    Secure Boot ✗   TPM ✗    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│       [Annuler]  [Sauvegarder]  [Sauvegarder + Redémarrer maintenant]    │
└──────────────────────────────────────────────────────────────────────────┘
```

**Légende :** édition par sections, indicateur `↻` pour les changements nécessitant un reboot. **Mode Infra ciblé** : toggle `[</> Vue native (XML libvirt)]` basculant vers l'éditeur XML direct (Monaco).

## Écran 10 — Liste Hosts

Inspiré de Coolify (cards serveurs). Famille Hosts — sémantique d'administration. Les Hosts sont des **substrats individuels** : les grappes multi-nœuds (k3s-cluster…) ne figurent plus dans cette liste — elles sont des Clusters (Écran 27).

```
┌─ Hosts ───────────────────────────────────────[+ Ajouter un Host]────────┐
│  Mes Hosts (3)              [▼ Tous profils] [▼ Tous statuts]            │
│  ⎈ Clusters (2) — grappes multi-nœuds  [→ Voir les Clusters]             │
│                                                                            │
│  ┌─ 🖧 nas-server ─────────────────────────── 🟢 Online · 47j ─────────┐ │
│  │  Profil : Baremetal SSH · x86_64 · Ubuntu 22.04                      │ │
│  │  CPU 12% · RAM 4.8/16 GB · Disque 1.2/4 TB · 🌡 38°C                 │ │
│  │  Moteurs : 🐳 Docker ✓  ✅ libvirt ✓  ✗ k8s                          │ │
│  │  Héberge : 5 Apps · 3 Machines · 12 services système (2 adoptés)     │ │
│  │  [📊 Détails] [🖥 SSH] [📋 journalctl]                            [⋯] │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│  ┌─ 🖧 ubuntu-dev ──────────────────────────── 🟢 Online · 3j ──────────┐ │
│  │  Profil : Baremetal (Machine sur nas-server)                         │ │
│  │  💡 Aussi une Machine  [→ Voir comme Machine]                        │ │
│  │  Moteurs : 🐳 Docker ✓  ✗ libvirt  ✗ k8s                             │ │
│  │  Héberge : 3 Apps · 0 sous-Machines                                   │ │
│  │  [📊 Détails] [🖥 SSH] [→ Voir comme Machine]                      [⋯] │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│  ┌─ 🖧 prox-home ──────────────────────────── 🔴 Unreachable ──────────┐ │
│  │  Profil : Proxmox VE 8.1 (serveur isolé)                            │ │
│  │  💡 Membre du cluster prox-cluster  [→ Voir le cluster]              │ │
│  │  Pas de connexion depuis 2h17min · Dernière erreur : timeout API     │ │
│  │  Dernière vue : CPU 8% · 22/64 GB RAM · 15 VMs · 4 LXC               │ │
│  │  [🔄 Réessayer] [📊 Détails (dernière vue)]                       [⋯] │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** action bar canonique Hosts — pas de Lifecycle, pas de Snapshot (chapitre 02). Status pills : `🟢 Online` / `⚪ Offline` / `🔴 Unreachable` / `🔵 Scanning`. Moteurs détectés avec ✓/✗ (déterminent ce qui peut être déployé) ; compteurs `Héberge : X Apps · Y Machines · Z services` ; Host unreachable → actions réduites, aucune action destructive. Le bandeau `⎈ Clusters` sous le titre renvoie à l'Écran 27 — les métriques agrégées de grappe (« 3 nodes », pods, namespaces) vivent dans la carte Cluster, plus ici.

## Écran 11 — Détail Host (baremetal)

```
┌─ Détail Host : nas-server ────────────────────────────────────────────────┐
│  🖧 nas-server                🟢 Online (uptime 47j)          [🖥 SSH]     │
│  Mini PC x86_64 · Ubuntu 22.04 · 16 GB RAM · 4 TB stockage                 │
│  Moteurs : 🐳 Docker 24.0.7 ✓  ✅ libvirt 9.0 ✓  ✗ Kubernetes             │
│                                                                            │
│  [🖥 SSH] [📊 Métriques] [📋 journalctl] [📦 Packages] [⚙ Config]      [⋯] │
│                                                                            │
│  ┌Aperçu┬Apps déployées┬Machines hébergées┬Services système┬Métriques─┐   │
│  │       ┴Stockage┬Réseau┬Config                                        │   │
│  │                                                                     │   │
│  │  ┌─ Hardware ──────────────────────────────────────────────────┐   │   │
│  │  │  CPU Intel N100 (4 cores @ 3.4 GHz) · RAM 16 GB DDR4         │   │   │
│  │  │  Stockage 4 TB NVMe · Réseau 1 Gb ethernet enp1s0            │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │  ┌─ Apps déployées sur ce Host (5) ────────────────────────────┐   │   │
│  │  │  ☁️ Nextcloud 🟢 docker_compose · 342 MB                      │   │   │
│  │  │  🎬 Jellyfin  🟢 docker_container · 456 MB · GPU passthrough  │   │   │
│  │  │                              [+ Déployer une nouvelle App ici] │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │  ┌─ Machines hébergées (3) ────────────────────────────────────┐   │   │
│  │  │  🖥️ ubuntu-dev      🟢 KVM · Ubuntu 22.04 · 2 GB              │   │   │
│  │  │     └─ aussi Host pour 3 Apps internes [→ Voir comme Host]    │   │   │
│  │  │                              [+ Créer une nouvelle Machine ici]│   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │  ┌─ Services système (12 dont 2 adoptés) ──────────────────────┐   │   │
│  │  │  🟢 nginx.service       Adopté → « Nginx Web » (App)          │   │   │
│  │  │  🟢 postgresql.service  Adopté → « PG Direct » (App)          │   │   │
│  │  │  🟢 ssh.service  🟢 docker.service  🟢 libvirtd.service       │   │   │
│  │  │                                          [→ Voir tous (12)]   │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** squelette identique aux autres familles. Onglets conditionnels : « Machines hébergées » seulement si un moteur de virtualisation est détecté ; « Apps déployées » seulement si Docker/Podman/k8s est détecté. Boutons de création contextuels `[+ … ici]` pré-sélectionnant ce Host.

## Écran 12 — Détail Host (cas récursif : Machine-as-Host)

Une Machine virtuelle avec Docker devient aussi un Host. La même entité a deux projections (Machine — Écran 7, Host — ici) avec navigation croisée.

```
┌─ Détail Host : ubuntu-dev ────────────────────────────────────────────────┐
│  🖧 ubuntu-dev (Host)         🟢 Online (3 jours)            [🖥 SSH]      │
│  Sur : nas-server · IP : 192.168.1.55 · Ubuntu 22.04 · 2 vCPU · 2 GB      │
│  💡 Aussi une Machine  [→ Gérer comme Machine]                             │
│  Moteurs : 🐳 Docker 24.0.7 ✓  ✗ libvirt  ✗ k8s                           │
│                                                                            │
│  [🖥 SSH] [📊 Métriques] [📋 journalctl] [📦 Packages] [⚙ Config]      [⋯] │
│                                                                            │
│  ┌Aperçu┬Apps déployées┬Services système┬Métriques┬Stockage┬Config─────┐   │
│  │      (pas d'onglet « Machines hébergées » : pas de moteur VM)       │   │
│  │                                                                     │   │
│  │  ┌─ Substrat de cette instance ───────────────────────────────┐   │   │
│  │  │  Cette entité est une Machine KVM hébergée sur nas-server.  │   │   │
│  │  │  Elle a Docker installé, ce qui permet à WindFlow de la     │   │   │
│  │  │  gérer aussi comme un Host.                                 │   │   │
│  │  │  Pour le matériel ou le cycle de vie : [→ Gérer comme Machine]│   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │  ┌─ Apps déployées dans ce Host (3) ──────────────────────────┐   │   │
│  │  │  ☁️ dev-postgres    🟢 docker_container · 89 MB              │   │   │
│  │  │  📊 dev-monitoring  🟢 docker_compose · 145 MB               │   │   │
│  │  │                              [+ Déployer une nouvelle App ici] │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** identité duale (l'entité apparaît dans les listes Machines **et** Hosts) ; carte « Substrat » remplaçant le Hardware ; pas d'onglet « Machines hébergées » sans moteur VM (il apparaîtrait avec la virtualisation imbriquée) ; « Apps déployées **dans** ce Host » — les couches restent navigables.

## Écran 13 — Wizard « Ajouter un Host »

Inspiré de Coolify (wizard SSH) + Proxmox (datacenter join). Étape 1 : choix du profil parmi `baremetal`, `proxmox`, `remote-docker` ; les grappes multi-nœuds (Kubernetes k8s/k3s/microk8s, cluster Proxmox, Swarm) s'ajoutent via **Ajouter un Cluster** — même wizard, choix du type de Cluster (`kubernetes`, `proxmox`, `docker_swarm`) et de sa connexion (kubeconfig, API du cluster, socket Swarm) ; le test résout les membres et propose leur rattachement aux Hosts/Machines existants.

```
┌─ Ajouter un Host ────────────────────────────────────────────────────────┐
│  ○────●────○────○                                                        │
│  Type Connexion Tester Confirmer                                         │
│                                                                            │
│  Étape 1 — Quel type de Host souhaitez-vous ajouter ?                     │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐           │
│  │ 🖧 Baremetal SSH │ │ 🖥️ Proxmox VE    │ │ 🐳 Docker distant│           │
│  │ Machine          │ │ Serveur Proxmox  │ │ Daemon Docker    │           │
│  │ physique ou VM   │ │ isolé via son    │ │ accessible par   │           │
│  │ accessible SSH   │ │ API              │ │ SSH ou TCP TLS   │           │
│  │ [Choisir]        │ │ [Choisir]        │ │ [Choisir]        │           │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘           │
│  💡 Un cluster k8s/k3s/microk8s, un cluster Proxmox multi-nœuds ou un    │
│     Swarm ?  [⎈ Ajouter un Cluster à la place]                           │
└──────────────────────────────────────────────────────────────────────────┘
```

Étape 2 (cas baremetal SSH) — connexion : nom, hôte/IP, port, utilisateur, authentification par clé SSH (sélecteur de clé ou collage), vérification sudo sans mot de passe ; options de scan (détection des moteurs, découverte des objets adoptables, scan périodique 5 min).

Étape 3 — test et détection :

```
┌─ Ajouter un Host — Test & détection ──────────────────────────────────────┐
│  ●────●────●────○                                                        │
│  Type Connexion Tester Confirmer                                         │
│                                                                            │
│  ✓ Connexion SSH établie (1.2s)      ✓ Authentification par clé Ed25519  │
│  ✓ Sudo sans mot de passe vérifié                                         │
│                                                                            │
│  ── Hardware détecté ──────────────────────────────────────────────────   │
│  CPU AMD Ryzen 5 5500U (6 cores) · RAM 32 GB · Stockage 8 TB              │
│  OS Debian 12 (bookworm) · kernel 6.1.0-17                                │
│                                                                            │
│  ── Moteurs détectés ──────────────────────────────────────────────────   │
│  🐳 Docker ✓ (24.0.7)    ✅ libvirt/KVM ✓ (9.0.0, 8 VMs définies)         │
│  ✗ LXD · ✗ Incus · ✗ Kubernetes                                           │
│                                                                            │
│  ── Objets découverts (non gérés par WindFlow) ─────────────────────────   │
│  📦 5 containers Docker en cours d'exécution                               │
│  📚 2 fichiers compose détectés (dans /opt/stacks/)                        │
│  🖥️ 1 VM libvirt en cours d'exécution                                      │
│  ⚙ 12 services systemd actifs                                              │
│                                                                            │
│  💡 Après l'ajout du Host, un wizard d'adoption vous proposera            │
│     d'importer les objets découverts dans WindFlow.                        │
│                       [← Retour]      [Ajouter le Host →]                  │
└────────────────────────────────────────────────────────────────────────────┘
```

## Écran 14 — Adoption d'objets découverts

Apparaît après l'ajout d'un Host, ou depuis le détail Host onglet « Découverts ». Implémente le wizard du chapitre [03-modele-compute.md](03-modele-compute.md).

```
┌─ Adopter des objets découverts sur nas-server-2 ──────────────────────────┐
│  WindFlow a détecté 8 objets non gérés sur ce Host.                       │
│                                                                            │
│  Filtrer : [Tous] [Apps] [Machines] [Services]   [Tout sélectionner]      │
│                                                                            │
│  ── Apps : containers Docker (3) ─────────────────────────────────────    │
│  ☐ 📦 plex          plex/plex:latest          running   1.2 GB            │
│  │    → Profil : docker_container · Adapter : DockerContainerAdapter      │
│  │    → Affecter à : [▼ Aucune stack (standalone)]                         │
│  ☐ 📦 sonarr        linuxserver/sonarr        running   245 MB            │
│  ☐ 📦 radarr        linuxserver/radarr        running   189 MB            │
│                                                                            │
│  ── Apps : stacks Compose (2) ────────────────────────────────────────    │
│  ☐ 📚 immich        (3 services : server, db, redis)   running            │
│  │    → Path : /opt/stacks/immich/docker-compose.yml                       │
│  │    → Profil : docker_compose · Adapter : ComposeStackAdapter           │
│  ☐ 📚 vaultwarden   (1 service)                     running   89 MB       │
│                                                                            │
│  ── Machines : VMs libvirt (1) ───────────────────────────────────────    │
│  ☐ 🖥️ windows-vm    Windows 10 · 4 vCPU · 8 GB · 80 GB       running      │
│  │    → Profil : vm_kvm · Adapter : KVMAdapter                            │
│  │    → ⚠ Les snapshots existants seront importés                        │
│                                                                            │
│  ── Services système (à adopter comme Apps) (2) ──────────────────────    │
│  ☐ ⚙ nginx.service  → Nom proposé : « Nginx Web Server » [Modifier]       │
│  │    → Profil : app_native_service · Pas d'URL détectée [Configurer]     │
│  ☐ ⚙ samba.service  → Nom proposé : « Samba Shares »      [Modifier]      │
│                                                                            │
│  💡 Les objets non adoptés resteront visibles en lecture seule dans       │
│     l'onglet « Découverts » du Host. Vous pourrez les adopter plus tard.  │
│                       [Plus tard]      [Adopter la sélection (0)]          │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** sélection granulaire item par item ; catégorisation par famille avec profil et adapter indiqués ; métadonnées éditables (nom proposé, stack d'affectation, URL) ; avertissements explicites ; **non-destructif** et **différable**.

## Écran 15 — Wizard création manuelle (Mode Infra)

Inspiré de Proxmox (Create VM/CT) + Incus. Point d'entrée `[+ Nouvelle App]` / `[+ Nouvelle Machine]` pour les power-users qui savent exactement ce qu'ils veulent.

Étape 1 — choix du type :

```
┌─ Créer ───────────────────────────────────────────────────────────────────┐
│  ○─────────○───────○───────○                                             │
│  Type      Config  Déploy                                                 │
│                                                                            │
│  Étape 1 — Que voulez-vous créer ?                                        │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐           │
│  │  📦  Container   │ │  📚  Stack       │ │  🖥️  Machine     │           │
│  │  Un container    │ │  (Compose)       │ │  Machine         │           │
│  │  unique depuis   │ │  Groupe de       │ │  virtuelle KVM   │           │
│  │  une image       │ │  containers      │ │  ou LXD/Incus    │           │
│  │  [Choisir]       │ │  [Choisir]       │ │  [Choisir]       │           │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘           │
│  💡 Pas sûr ? Commencez par la Marketplace pour un déploiement one-click  │
└────────────────────────────────────────────────────────────────────────────┘
```

Étape 2 (Machine) — configuration :

```
┌─ Créer une Machine ───────────────────────────────────────────────────────┐
│  ●─────────○───────○───────○                                             │
│  Type      Config  Déploy                                                 │
│                                                                            │
│  Nom *           [ubuntu-dev            ]                                 │
│  Host            [▼ nas-server (KVM ✓)  ]                                 │
│  Profil          [▼ vm_kvm              ]                                 │
│                                                                            │
│  ── Image OS ──                                                           │
│  Template        [▼ Ubuntu 24.04 LTS (cloud-init)]                        │
│  Architecture    [▼ arm64              ]                                  │
│                                                                            │
│  ── Hardware ──                                                           │
│  vCPU [2] cores   RAM [2048] MB   Disque [20] GB   Format [▼ qcow2]       │
│                                                                            │
│  ── Cloud-init ──                                                          │
│  Hostname [ubuntu-dev]  Utilisateur [ubuntu]                              │
│  Clé SSH [▼ ~/.ssh/id_ed25519.pub]  Packages [htop, curl, git]            │
│                                                                            │
│  ▸ Réseau (bridge/VLAN)  ▸ Storage pool  ▸ Firmware (avancé)             │
│                                           [← Retour]  [Déployer →]         │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** le wizard partage stepper, sections « Nom / Host / Ressources » et bouton « Déployer » entre types ; seules les sections spécifiques diffèrent (Image Docker vs Template OS, Ports vs Cloud-init). La variante Container expose Nom, Image (avec recherche), Host, RAM/CPU limits, Ports, et les sections dépliables Volumes / Réseau / Env vars / Labels. La variante Stack (Compose) propose à l'étape Config un lien « Éditer visuellement » vers l'Éditeur de composition (Écran 21).

## Écran 16 — Volume Browser

Inspiré de CasaOS File Manager + Nextcloud Files.

```
┌─ Volume Browser : nextcloud_data ──────────────────────────────────────────┐
│  📂 nextcloud_data (2.1 GB)     Utilisé par : nextcloud                    │
│  Chemin : / ▸ data ▸ admin ▸ files                                         │
│  [⬆ Upload]  [📁 Nouveau dossier]  [📄 Nouveau fichier]                   │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  NOM                 TYPE      TAILLE    MODIFIÉ        ACTIONS     │  │
│  │  📁 Documents        dossier   340 MB    01/04 14:30    →          │  │
│  │  📁 Photos           dossier   1.2 GB    01/04 10:15    →          │  │
│  │  📄 notes.md         fichier   2.4 KB    01/04 14:30    📝 ⬇ 🗑   │  │
│  │  🖼️ wallpaper.jpg    image     1.8 MB    28/03 10:15    👁 ⬇ 🗑   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│  ┌─ Preview : wallpaper.jpg ───────────────────────────────────────────┐  │
│  │  [ Image Preview ]   1920×1080 • JPEG • 1.8 MB                      │  │
│  │                                        [⬇ Télécharger]  [Fermer]   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** breadcrumbs cliquables ; preview inline (images, texte, markdown, logs) ; drag & drop pour l'upload ; actions 📝 éditer, ⬇ télécharger, 🗑 supprimer. Fonctionne en montant temporairement le volume dans un container utilitaire léger. Lecture seule sur mobile.

## Écran 17 — Console unifiée (Terminal + VNC)

Inspiré de Proxmox (noVNC dans un onglet) et Incus (même commande console). Le bouton `[🖥 Console]` ouvre la même page pour tous les types ; seul le contenu s'adapte (Terminal pour App, VNC pour Machine, SSH pour Host).

### Console Terminal (App)

```
┌─ Console : nextcloud-php ──────────────────────────────────────────────────┐
│  📦 nextcloud-php (App) 🟢    [🖥 Terminal]  [Plein Écran]                 │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  root@nextcloud-php:/var/www/html# ls -la                            │ │
│  │  total 184                                                            │ │
│  │  -rw-r--r--  1 www-data www-data  2847 Mar 28  index.php             │ │
│  │  root@nextcloud-php:/var/www/html# _                                 │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│  Shell: /bin/bash  │  User: root                                          │
└────────────────────────────────────────────────────────────────────────────┘
```

### Console VNC (Machine)

```
┌─ Console : ubuntu-dev ─────────────────────────────────────────────────────┐
│  🖥️ ubuntu-dev (Machine KVM) 🟢   [Ctrl+Alt+Del] [Plein Écran] [Coller]   │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │          ubuntu@ubuntu-dev:~$ sudo apt update                        │ │
│  │          Hit:1 http://archive.ubuntu.com/ubuntu jammy InRelease      │ │
│  │                    [ Console VNC via noVNC ]                          │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│  Résolution: 1024×768  │  Qualité: Auto  │  Clipboard: Bidirectionnel     │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** la barre de titre affiche le type (App / Machine / Host), le chrome (toolbar, fullscreen, status bar) est identique. Canaux WebSocket : `/ws/terminal/{container_id}`, `/ws/console/{machine_id}`, `/ws/ssh/{host_id}` (chapitre [09-api.md](09-api.md)).

## Écran 18 — Plugins installés

Inspiré de Runtipi (app management) + Cosmos (server apps).

```
┌─ Plugins ──────────────────────────────────────────────────────────────────┐
│  Plugins installés (3)            RAM: 268 MB     [🏪 Marketplace]         │
│                                                                            │
│  ┌── 🔀 Traefik ──────────────────────────── v1.2.0 ──── 🟢 ──────────┐  │
│  │  Hybrid │ Accès & Routage │ 142 MB RAM                               │  │
│  │  📊 3 domaines actifs • 3 certificats valides • 1.2K req/h           │  │
│  │  [⚙ Config]  [📋 Logs]  [⏸ Stop]  [🔄 Update]  [🗑 Désinstaller]    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  ┌── 🐘 PostgreSQL Manager ───────────────── v1.0.0 ──── 🟢 ──────────┐  │
│  │  Extension │ Bases de données │ 28 MB RAM                            │  │
│  │  📊 2 containers détectés • 5 databases • 3 users                   │  │
│  │  [⚙ Config]  [🔄 Update]  [🗑 Désinstaller]                         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  ┌── 📊 Uptime Kuma ─────────── v1.0.0 ⬆ v1.1.0 ──── 🟢 ──────────┐     │
│  │  Service │ Monitoring │ 98 MB RAM                                    │ │
│  │  📊 5 monitors • 100% uptime (30j)                                  │ │
│  │  [🔗 Ouvrir]  [⚙ Config]  [📋 Logs]  [⏸ Stop]  [🔄 Update ⬆]      │ │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** type et catégorie visibles, RAM totale consommée, résumé d'activité par plugin, badge `⬆` de mise à jour disponible. Le cycle de vie correspond au Plugin Manager du chapitre [11-plugins.md](11-plugins.md).

## Écran 19 — Activité

Inspiré de Cloudron (Activity log) + Umbrel (Activity tab). Journal chronologique filtrable avec actions directes.

```
┌─ Activité ─────────────────────────────────────────────────────────────────┐
│  [Tout]  [Déploiements]  [Plugins]  [Sécurité]  [Système]                 │
│                                                                            │
│  Aujourd'hui                                                              │
│  🔔 14:30  Certificat cloud.example.com expire dans 30 jours             │
│            [Renouveler maintenant]                                         │
│  ✅ 12:15  Nextcloud mis à jour 28.0.3 → 28.0.4          par admin       │
│            Durée: 45s • Backup créé avant mise à jour                     │
│  ✅ 06:00  Backup automatique terminé                      par système    │
│            3 volumes • 2.1 GB • Destination: /backup/restic              │
│                                                                            │
│  Hier                                                                     │
│  ❌ 18:30  Déploiement monitoring échoué                   par admin       │
│            Erreur: port 9090 déjà utilisé                                 │
│            [Voir les logs] [Réessayer]                                     │
│  ✅ 15:00  Plugin Restic installé (v1.0.0)                par admin       │
│  ✅ 14:45  Host nas-server-2 ajouté                        par admin       │
│            SSH deploy@192.168.1.51 • Docker détecté                       │
│  🔒 10:22  Connexion refusée (brute force)                 IP: 45.33.x.x  │
│            5 tentatives échouées → IP bloquée 5 min                       │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** chaque entrée montre qui, quand, quoi, et le résultat ; actions directes (« Renouveler », « Voir les logs », « Réessayer »). Les événements de sécurité y sont visibles (l'audit complet et sa rétention : chapitre [15-securite.md](15-securite.md)).

## Écran 20 — Graphe de dépendances

Inspiré du `WorkflowEditor` WindFlow existant (précédent Vue Flow interne) + viewers type Portainer/Compose. Vue **lecture seule** rendue avec Vue Flow + dagre (layout automatique). Nœuds = services conteneurs, arêtes = `depends_on`. Trois points d'entrée : l'onglet « Composants techniques » du Détail App (Écran 3, Mode Infra), la vue Compute (chapitre [03-modele-compute.md](03-modele-compute.md)) et le détail d'une stack (vue Stacks).

```
┌─ Graphe de dépendances ──────────────────────────────────────────────────────┐
│  ⊞ Par application   [App ▾: Toutes] [Origine ▾: Toutes] [Statut ▾: Tous]   │
│  ⚠ 1 cycle détecté : baserow-web → baserow-backend → baserow-web            │
│                                                                            │
│  ┌─ 🖧 nas-server ──────────────────────────────────────────────────┐      │
│  │  ┌─ ☁️ App « baserow » (docker_compose · Managé) ──────────────┐ │      │
│  │  │                                                             │ │      │
│  │  │   ┌──────────────┐        ┌──────────────┐                  │ │      │
│  │  │   │ 🗄 baserow-db │◀───────│ 🛠 baserow-  │                  │ │      │
│  │  │   │ postgres:15  │ healthy│ backend      │                  │ │      │
│  │  │   │ 🟢 Managé    │        │ 🟢 Managé    │                  │ │      │
│  │  │   └──────────────┘        └──────┬───────┘                  │ │      │
│  │  │                                  │ service_started           │ │      │
│  │  │                                  ▼                          │ │      │
│  │  │   ┌──────────────┐        ┌──────────────┐                  │ │      │
│  │  │   │ 🌐 traefik    │◀───────│ 🖥 baserow-  │                  │ │      │
│  │  │   │ Externe      │        │ web          │                  │ │      │
│  │  │   │ 🟢 [Adopter] │        │ 🟢 Managé    │                  │ │      │
│  │  │   └──────────────┘        └──────────────┘                  │ │      │
│  │  └─────────────────────────────────────────────────────────────┘ │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│  🔍 ──────── ·  [⊞ Réorganiser (dagre)]  [⤢ Ajuster]  [⋯]   ┌─────┐        │
│  Zoom: − 100% +                          Minimap ▢          │ ▢ │        │
│                                                            └─────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** lecture seule — aucun nœud ni arête éditable. Chaque nœud porte l'icône du profil (`docker_container` / `docker_compose`), le badge d'origine (`Managé` / `Adopté` / `Externe`) et le statut runtime (🟢 running / 🔴 stopped / 🟡 degraded). Les arêtes `depends_on` portent la condition (`service_started` / `service_healthy`) quand elle est disponible. Regroupement par application (sous-graphe/cluster par App), l'app hôte affichée en amont (nas-server) — respect de la relation d'hébergement Host/Machine (chapitre [02-familles-workloads.md](02-familles-workloads.md)) ; les arêtes animées reflètent l'activité runtime. Filtres par application, origine et statut. Minimap, zoom/pan (Controls), bouton « Réorganiser » relançant le layout dagre. Clic sur un nœud → Détail App (Écran 3) ou fiche conteneur Compute. Les nœuds `Externe` offrent un bouton `[Adopter]` qui renvoie au wizard d'adoption (Écran 14). Un cycle détecté affiche un bandeau `⚠` (détection transposable du moteur de dépendances plugins). Source de données : graphe normalisé `nodes`/`edges` exposé par l'API (chapitre [09-api.md](09-api.md) — `GET /compute/graph`, `GET /apps/{id}/graph`), dérivé du parsing des compose et de l'inspection runtime ; pour Kubernetes/Helm, arêtes entre workloads du même namespace (généralisation profil × origine, chapitre [03-modele-compute.md](03-modele-compute.md)).

## Écran 21 — Éditeur de composition

Inspiré du `WorkflowEditor` WindFlow existant (palette + canvas + propriétés) + éditeurs compose type Portainer. Éditeur **interactif** Vue Flow, Mode Infra uniquement, ciblant le profil `docker_compose`. Génération/sérialisation du compose depuis le graphe ; les autres profils restent en lecture seule (matrice profil × origine, chapitre [03-modele-compute.md](03-modele-compute.md)).

```
┌─ Éditeur de composition : baserow ───────────────────────────────────────────┐
│  ┌─ Palette ────────┐  ┌─ Canvas ──────────────────────────────────────┐   │
│  │ ── Nœuds ──      │  │  [↶ Undo] [↷ Redo] [🧲 Snap] [⊞ Réorganiser]   │   │
│  │  🛠 Service   │  │        ┌──────────────┐                          │   │
│  │  🌐 Réseau    │  │        │ 🛠 web        │◀────┐                    │   │
│  │  💾 Volume    │  │        │ nginx:alpine │     │ service_started   │   │
│  │ (glisser sur   │  │        └──────────────┘     │                    │   │
│  │  le canvas)    │  │        ┌──────────────┐     │                    │   │
│  │ ── Représ. ──  │  │        │ 🛠 backend   │─────┘                    │   │
│  │ [⊞ Graphe]     │  │        └──────────────┘                          │   │
│  │ [📋 YAML]      │  │             ▼                                  │   │
│  │                │  │        ┌──────────────┐     ┌─────┐ Minimap      │   │
│  │                │  │        │ 🗄 db         │     │ ▢ │              │   │
│  │                │  │        └──────────────┘     └─────┘              │   │
│  └────────────────┘  └─────────────────────────────────────────────────┘   │
│  ┌─ Propriétés : 🛠 web ──────────────────────────────────────────────┐   │
│  │  Image *  [nginx:alpine        ]   Ports  [80:80          ] (+)      │   │
│  │  Env      [KEY=value         ] (+)   Volumes [data:/data   ] (+)     │   │
│  │  Réseau  [▼ interne]  ⚠ Dépendances : aucune (créées par connexion) │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  Graphe ⇄ YAML synchronisés ·     [Valider]  [Déployer]                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** palette de nœuds `Service` / `Réseau` / `Volume` à glisser sur le canvas ; panneau « Propriétés » latéral (image, ports, env, volumes ; `depends_on` créé par connexion entre deux services, condition éditable sur l'arête). Représentation double et synchrone **graphe ⇄ YAML** (le YAML reste éditable, two-way). Validation temps réel via `isValidConnection` (pas d'auto-boucle, pas de cycle — détection locale complétée par la validation serveur) ; boutons `[Valider]` (`POST /compute/stacks/validate`) et `[Déployer]` ; compose régénéré depuis les `nodes`/`edges`. Undo/redo, snapping + snaplines, minimap, zoom. Round-trip complet : réimport d'un compose existant → graphe. Trois cas d'usage : création manuelle (prolonge le wizard de l'Écran 15 — l'étape Config propose « Éditer visuellement »), édition d'une stack existante (depuis la vue Stacks), adoption (compose généré par le wizard d'adoption — Écran 14 — éditable avant déploiement). Mode Infra uniquement.

Modèle de données du graphe (sérialisation JSON `nodes`/`edges`) :

```json
{
  "nodes": [
    { "id": "web", "type": "service", "data": { "image": "nginx:alpine", "ports": ["80:80"], "env": {}, "volumes": [], "networks": ["interne"] } },
    { "id": "interne", "type": "network", "data": { "driver": "bridge" } },
    { "id": "data", "type": "volume", "data": { "driver": "local" } }
  ],
  "edges": [
    { "id": "web-backend", "source": "backend", "target": "web", "data": { "condition": "service_started" } }
  ]
}
```

Mapping compose : les arêtes `service → service` produisent `services.<cible>.depends_on` (avec `condition` si définie) ; les nœuds `network` deviennent des réseaux top-level (`networks:`) ; les nœuds `volume` des volumes top-level (`volumes:`). Endpoints : `POST /compute/stacks/from-graph` (génération compose), `POST /compute/stacks/validate` (chapitre [09-api.md](09-api.md)).

## Écran 22 — Vue Compute (Mode Infra)

Écran central du Mode Infra (chapitre [03-modele-compute.md](03-modele-compute.md)). Inspiré de Portainer (profondeur containers) + Proxmox (vue globale datacenter). La section **Compute** unifie ce qui serait autrement des sections séparées « Containers », « VMs », « Stacks » : les objets y sont affichés **par technologie**, pas par famille.

### Vue globale (groupement logique)

```
┌─ Compute ───────────────────────────────────────────────────────────────────┐
│  [Vue globale] [Containers] [VMs] [Images & ISOs] [Snapshots]               │
│  Filtres : [▼ Niveau de contrôle] [▼ Technologie] [▼ Host] [▼ Statut] [🔍]  │
│  Vue : (⊞ Logique — par stack)  (🖥 Par Host)                                │
│                                                                             │
│  ── 1. Stacks WindFlow ──────────────────────────────────────────────────── │
│  ┌─ 📚 nextcloud · compose · nas-server ─────────────────────── 3/3 🟢 ──┐  │
│  │   ├─ 📦 nextcloud   🟢 running · Managé      [🖥] [📋] [⋯]           │  │
│  │   ├─ 📦 postgres    🟢 running · Managé      [🖥] [📋] [⋯]           │  │
│  │   └─ 📦 redis       🟢 running · Managé      [🖥] [📋] [⋯]           │  │
│  │   [⏵ Démarrer] [⏹ Arrêter] [🔄 Redéployer] [🕸 Graphe] [⋯]           │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ 📚 dev-env · compose mixte · nas-server ────────────────── all up 🟢 ┐  │
│  │   ├─ 🖥️ ubuntu-dev   VM KVM 🟢 · Managé       [VNC] [📸] [⋯]         │  │
│  │   ├─ 📦 postgres     🟢 running · Managé      [🖥] [📋] [⋯]           │  │
│  │   └─ 📦 redis        🟢 running · Managé      [🖥] [📋] [⋯]           │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ ⎈ web · helm · k3s-cluster ─────────────────────────────── 5/5 🟢 ──┐  │
│  │   └─ 5 workloads · namespace windflow           [🕸 Graphe] [⋯]       │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ── 2. Discovered — non managés ─────────────────────────────────────────── │
│  ┌─ 📚 monitoring · compose détecté · nas-server ──── observé, adoptable ┐  │
│  │   ├─ 📦 prometheus  🟢 running · Externe      [Adopter] [📋]          │  │
│  │   └─ 📦 grafana     🟢 running · Externe      [Adopter] [📋]          │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ 🖥️ windows-legacy · VM KVM · local ───────────── observé, adoptable ─┐  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ── 3. Standalone ───────────────────────────────────────────────────────── │
│  🖥️ pfsense-router   VM KVM    · local      · 🟢 running    [VNC] [⋯]       │
│  🖥️ k3s-node-1       LXC       · prox-home  · 🟢 running    [Console] [⋯]   │
│  📦 traefik          container · local      · 🟢 running    [🖥] [📋] [⋯]    │
│  📦 pihole           container · pi4-home   · 🟢 running    [🖥] [📋] [⋯]    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Vue par Host (groupement physique)

```
┌─ Compute · Par Host ────────────────────────────────────────────────────────┐
│  ┌─ 🖧 local ── Docker 24.0.7 · libvirt 9.0 ─────────────────────────────┐  │
│  │  1 container · 1 VM · CPU 9% · RAM 3.1/8 GB                          │  │
│  │  traefik 🟢 · windows-legacy ⚪ (adoptable)                           │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ 🖧 nas-server ── Docker 24.0.7 · libvirt 9.0 ────────────────────────┐  │
│  │  8 containers · 3 VMs · CPU 18% · RAM 6.4/16 GB                      │  │
│  │  nextcloud 3/3 🟢 · dev-env all up 🟢 · monitoring (adoptable)        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ 🖧 k3s-cluster ── containerd · k3s v1.28.5 ──────────────────────────┐  │
│  │  web (helm) 5/5 🟢 · 23 pods · 4 namespaces                          │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ 🖧 pi4-home ── Docker 24.0.7 ────────────────────────────────────────┐  │
│  │  1 container · pihole 🟢                                             │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** la vue globale affiche les objets Compute en trois sections ordonnées (stacks managées → discovered → standalone). Onglets internes : Vue globale / Containers / VMs / Images & ISOs / Snapshots (chapitre 03). Filtres combinables : niveau de contrôle (croisé avec l'origine `managed`/`adopted`/`external` — chaque cellule de la matrice profil × origine est adressable), technologie, Host, statut, recherche libre. Chaque ligne porte le badge d'origine (`Managé` / `Adopté` / `Externe`) et des actions conditionnées par la cellule profil × origine — un objet `Externe` n'expose ni Lifecycle ni Supprimer, seulement l'observation et `[Adopter]` (wizard Écran 14). Les stacks exposent les actions globales de stack (chapitre 03) ; `[🕸 Graphe]` ouvre le Graphe de dépendances (Écran 20). Le toggle bascule entre vue logique (par stack) et vue physique (par Host : résumé containers/VMs, métriques agrégées CPU/RAM, hyperviseur et version du daemon Docker). Source de données : endpoints `/compute/*` (chapitre [09-api.md](09-api.md)).

## Écran 23 — Settings (Utilisateurs · Audit · Tâches planifiées)

Écran transverse de gestion. Inspiré de Cloudron (membres) + Proxmox (journal d'audit). Point d'entrée unique « Settings » de la sidebar (chapitre [13-ui-principes.md](13-ui-principes.md)) ; l'Audit dispose en outre d'une entrée directe en Mode Infra.

### Onglet Utilisateurs

```
┌─ Settings ──────────────────────────────────────────────────────────────────┐
│  [👤 Utilisateurs] [📋 Audit] [⏰ Tâches planifiées]                         │
│  Organisation : homelab · 3 membres                    [+ Inviter un membre]│
│                                                                             │
│  👤 admin   admin@example.com   Super Admin   depuis 2026-03-15         [⋯] │
│  👤 alice   alice@example.com   Operator      depuis 2026-04-01   [⚙ Rôle ▾]│
│  👤 bob     bob@example.com     Viewer        depuis 2026-04-02   [⚙ Rôle ▾]│
│                                                                             │
│  ⚠ Le dernier Super Admin ne peut pas être supprimé ni rétrogradé.          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Onglet Audit

```
┌─ Settings · Audit ──────────────────────────────────────────────────────────┐
│  [👤 Utilisateurs] [📋 Audit] [⏰ Tâches planifiées]                         │
│  Filtres : [▼ Type d'événement] [▼ Utilisateur] [📅 Période]                │
│                                                                             │
│  🔒 14:32  admin a changé le rôle de bob (viewer → operator)   IP 192.168.1.10│
│  ✏️ 11:03  admin a invité alice (operator) dans homelab        IP 192.168.1.10│
│  🗑 09:58  admin a révoqué la clé API « ci-deploy »             IP 192.168.1.10│
└─────────────────────────────────────────────────────────────────────────────┘
```

### Onglet Tâches planifiées

```
┌─ Settings · Tâches planifiées ──────────────────────────────────────────────┐
│  [👤 Utilisateurs] [📋 Audit] [⏰ Tâches planifiées]       [+ Nouvelle tâche]│
│                                                                             │
│  ⏰ backup-nextcloud       app.backup · cron 0 2 * * *        🟢 ✅ 02:00 · 12s│
│  ⏰ prune-images-nuit      compute.images.prune · cron 30 3 * * *  🟢 ✅ 03:30│
│  ⚡ notify-deploy-failure  notification.send · event deployment.failed · 🟢  │
│                                                                             │
│  ▸ backup-nextcloud — dernières exécutions                                  │
│     aujourd'hui 02:00 ✅ 12s · hier 02:00 ✅ 11s · il y a 2j 02:00 ❌ timeout │
│                                         [▶ Exécuter maintenant] [⚙] [⋯]     │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** **Utilisateurs** — membres de l'organisation courante, changement de rôle, protections anti-escalade du chapitre [08-rbac-permissions.md](08-rbac-permissions.md) ; miroir UI de `windflow admin user` (chapitre 10). **Audit** — toutes les modifications de permissions loggées avec qui/quand/quoi/IP (rétention : chapitre [15-securite.md](15-securite.md)) ; consultation équivalente en CLI (`windflow admin audit`). **Tâches planifiées** — scheduler core du chapitre [17-automatisation-workflows.md](17-automatisation-workflows.md) : liste, statut de la dernière exécution, historique des exécutions (durée, résultat) ; `[▶ Exécuter maintenant]` = `windflow admin tasks run` ; les exécutions sont aussi visibles dans l'écran Activité (Écran 19).

## Écran 24 — Login / SSO

Page de login core (auth JWT native, chapitre [07-authentification.md](07-authentification.md)). Le bouton « Se connecter avec SSO » n'est rendu que lorsque le plugin Keycloak est installé.

```
┌───────────────────────────────────────────────┐
│                                               │
│                 🌀 WindFlow                    │
│      Votre infrastructure, simplifiée         │
│                                               │
│   ┌───────────────────────────────────────┐   │
│   │  Utilisateur   [admin              ]  │   │
│   │  Mot de passe  [••••••••            ]  │   │
│   │                                       │   │
│   │  ⚠ 5 tentatives échouées — blocage   │   │
│   │    pendant 5 min                      │   │
│   │                                       │   │
│   │           [Se connecter]              │   │
│   │   ──────────  ou  ──────────          │   │
│   │   [🔑 Se connecter avec SSO]          │   │
│   └───────────────────────────────────────┘   │
│                                               │
│   Auth native JWT core · SSO via plugin       │
│   Keycloak (bouton absent si non installé)    │
└───────────────────────────────────────────────┘
```

**Légende :** formulaire core — `POST /auth/login` délivre access + refresh tokens (chapitre 07). Le bouton « Se connecter avec SSO » est ajouté par le plugin Keycloak (OIDC/SAML, LDAP/AD, 2FA côté Keycloak) ; le flow SSO aboutit à un JWT WindFlow standard — le reste de l'application ignore le mode d'authentification. Message de blocage après 5 échecs (fenêtre 10 min, blocage 5 min, compteur réinitialisé après un login réussi — chapitre 07).

## Écran 25 — Vues listes Mode Infra (Stacks · Volumes · Networks · Images)

Vues listes du bloc « Compute (technique) » de la sidebar Mode Infra (chapitre [02-familles-workloads.md](02-familles-workloads.md)), inspirées de Portainer. Une seule maquette de référence (vue Stacks) ; Volumes, Networks et Images en sont des variantes décrites en légende.

```
┌─ Stacks ────────────────────────────────────────────────────────────────────┐
│  Stacks (3)           [▼ Host] [▼ Statut] [🔍]             [+ Nouvelle stack]│
│                                                                             │
│  ┌─ 📚 nextcloud · compose · nas-server ─────────────────────── 3/3 🟢 ──┐  │
│  │  3 services · version 5 · déployée il y a 15 jours · RAM 342 MB       │  │
│  │  [⏵ Démarrer] [⏹ Arrêter] [🔄 Redéployer] [✏️ Éditer] [🕸 Graphe] [⋯]  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ 📚 dev-env · compose mixte · nas-server ────────────────── all up 🟢 ┐  │
│  │  3 composants (1 VM KVM + 2 containers) · RAM 2.4 GB                 │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  ┌─ ⎈ web · helm · k3s-cluster ─────────────────────────────── 5/5 🟢 ──┐  │
│  │  release · namespace windflow · 5 workloads                          │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** grammaire commune — titre + compteur, filtres `[▼ Host] [▼ Statut] [🔍]`, bouton de création, cards avec état global à droite et actions inline. Variantes :

- **Stacks** (ci-dessus) : actions globales de stack du chapitre [03-modele-compute.md](03-modele-compute.md) — démarrer dans l'ordre des dépendances, arrêter dans l'ordre inverse, redéployer, mettre à jour depuis Git (plugin Git), dupliquer, archiver ; `[✏️ Éditer]` ouvre l'Éditeur de composition (Écran 21) pour les stacks `docker_compose` ; `[🕸 Graphe]` → Écran 20.
- **Volumes** : lignes `nom · driver · taille · utilisé par` (ex. `nextcloud_data · local · 2.1 GB · utilisé par nextcloud`) ; `[📂 Browser]` ouvre le Volume Browser (Écran 16) ; suppression bloquée si le volume est utilisé.
- **Networks** : lignes `nom · driver · scope · containers rattachés` (ex. `windflow_net · bridge · local · 4 containers`).
- **Images** : bibliothèque images Docker + ISOs/qcow2 — lignes `tag · taille · date de pull · utilisée par N containers` ; action « Prune » des images inutilisées (cf. tâche `compute.images.prune`, chapitre [17-automatisation-workflows.md](17-automatisation-workflows.md)) ; fait écho à l'onglet « Images & ISOs » de la Vue Compute (Écran 22).

## Écran 26 — Assistant IA (page plugin)

**Exemple d'intégration plugin, pas un écran core.** Chat intégré à l'UI, page « Assistant IA » ajoutée dynamiquement à la sidebar par les plugins IA (Ollama/LiteLLM — chapitre [18-plugins-ia.md](18-plugins-ia.md)).

```
┌─ 🤖 Assistant IA ────────────────────────────────────────────────────────────┐
│  Moteur : Ollama · plugin « windflow-ollama » v1.0.0                        │
│                                                                             │
│  ┌─ Contexte accessible ────────────────────────────────────────────────┐   │
│  │  ✅ Hosts (4) · Apps (5) · stacks (3) · plugins (3) · logs récents    │   │
│  │  ⛔ Secrets — jamais transmis au modèle                               │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  👤 Pourquoi mon container redis redémarre en boucle ?                │   │
│  │                                                                       │   │
│  │  🤖 redis (stack nextcloud) a redémarré 6 fois en 1 h :              │   │
│  │     OOMKilled — limite RAM 128 MB atteinte (logs 14:02, 14:11, …).   │   │
│  │     Suggestions :                                                     │   │
│  │     • passer la limite à 256 MB                                       │   │
│  │     • réduire maxmemory-policy à allkeys-lru                          │   │
│  │     [→ Ouvrir la stack]  [📋 Copier la config suggérée]               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│  ┌───────────────────────────────────────────────────────┐    [Envoyer ➤]   │
│  │  Poser une question sur votre infrastructure…          │                 │
│  └───────────────────────────────────────────────────────┘                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** contrat d'intégration UI d'une page apportée par un plugin. Sans plugin IA installé, la page n'existe pas — l'entrée « Assistant IA » de la section Plugins de la sidebar (chapitre [13-ui-principes.md](13-ui-principes.md)) est ajoutée dynamiquement. Le chrome de la page est standard WindFlow (sidebar, header) ; le contenu est rendu par l'extension UI du plugin via les endpoints `/plugins/ai/*` (chapitres [18-plugins-ia.md](18-plugins-ia.md) et [09-api.md](09-api.md)). L'encart « Contexte accessible » explicite le périmètre : contexte de l'instance oui, secrets jamais. Les suggestions sont accompagnées d'actions de navigation/copy — **rien n'est exécuté ni déployé automatiquement**. Cette maquette sert de contrat de référence pour toute page plugin ; les autres pages plugins (Domaines, Monitoring, Backups) ne sont volontairement pas maquettées.

## Écran 27 — Clusters (liste et détail)

**Arbitrage UI** : plutôt qu'un Écran 10 renommé « Hosts & Clusters » (qui brouillerait la sémantique « Hosts = substrats individuels »), les grappes multi-nœuds obtiennent leur **propre écran** au gabarit existant (titre + compteur, filtres, bouton d'ajout, cards avec actions inline) — cohérent avec le rang de première classe de l'entité. Entrée de navigation : section Workloads des sidebars, sous « Hosts » (icône ⎈, chapitre 02). La card k3s-cluster autrefois dans l'Écran 10 vit ici, avec ses métriques agrégées.

Liste :

```
┌─ Clusters ─────────────────────────────────[+ Ajouter un Cluster]───────┐
│  Mes Clusters (2)           [▼ Tous types] [▼ Tous statuts]             │
│                                                                           │
│  ┌─ ⎈ k3s-cluster ──────────────────────────── 🟢 Healthy ───────────┐  │
│  │  Type : Kubernetes (k3s v1.28.5) · kubeconfig · Origine : Adopté   │  │
│  │  Membres : 3 (1 control-plane · 2 workers) · 23 pods · 4 ns        │  │
│  │  Agrégé : CPU 22% · RAM 8.4/24 GB                                  │  │
│  │  Héberge : 4 Apps (helm_release, k8s_manifest)                     │  │
│  │  [📊 Détails] [🖥 kubectl] [📋 events]                          [⋯] │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│  ┌─ ⎈ prox-cluster ─────────────────────────── 🟢 Healthy ───────────┐  │
│  │  Type : Proxmox VE 8.1 (quorum 2 nodes) · API cluster              │  │
│  │  Membres : 2 nodes (prox-home, prox-2) · 15 VMs · 4 LXC            │  │
│  │  Agrégé : CPU 8% · RAM 22/64 GB                                    │  │
│  │  [📊 Détails] [🖥 Console nœud ▾] [📋 tâches]                   [⋯] │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

Détail (squelette invariant, onglets canoniques Clusters — chapitre 02) :

```
┌─ Détail Cluster : k3s-cluster ───────────────────────────────────────────┐
│  ⎈ k3s-cluster                    🟢 Healthy · 3 nodes          [🖥]      │
│  Kubernetes k3s v1.28.5 · kubeconfig · Origine : Adopté                  │
│  CPU 22% · RAM 8.4/24 GB · 23 pods · 4 namespaces                        │
│                                                                           │
│  [🔗 Ouvrir dashboard] [📊 Santé] [📋 Events] [🖥 Console nœud ▾] [⚙][⋯] │
│                                                                           │
│  ┌Aperçu┬Nœuds & Membres┬Santé┬Workloads hébergés┬Config─────────────┐   │
│  │                                                                │   │
│  │  ┌─ Nœuds & Membres (3) ─────────────────────────────────────┐   │   │
│  │  │  pi4-home    control-plane · Host · ready · v1.28.5       │   │   │
│  │  │  k3s-node-1  worker · Machine LXC (sur prox-home) · ready │   │   │
│  │  │  k3s-node-2  worker · Machine KVM (sur nas-server) · ready│   │   │
│  │  │  💡 L'appartenance est orthogonale à l'hébergement —      │   │   │
│  │  │     chaque nœud reste hébergé par son Host physique.      │   │   │
│  │  └───────────────────────────────────────────────────────────┘   │   │
│  │  ┌─ Workloads hébergés (4) ──────────────────────────────────┐   │   │
│  │  │  ⎈ web (helm_release · namespace windflow) 🟢             │   │   │
│  │  │  ⎈ cert-manager (k8s_manifest) 🟢                         │   │   │
│  │  │                                  [+ Déployer une App ici] │   │   │
│  │  └───────────────────────────────────────────────────────────┘   │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** les trois types (`kubernetes`, `proxmox`, `docker_swarm`) partagent le même gabarit — seuls les libellés changent (rôles `control-plane`/`worker` vs `member`/`manager`, dashboard vs port Swarm). La note `💡` rappelle l'orthogonalité hébergement/appartenance (chapitre 02). En Mode App, l'écran reste accessible (c'est une vue d'infrastructure), mais sans exposer pods/namespaces comme termes techniques — les compteurs restent. Wizard d'ajout : Écran 13 (`[⎈ Ajouter un Cluster à la place]`). Source de données : endpoints `/clusters` (chapitre [09-api.md](09-api.md)).

## Écran E1 (piste d'évolution) — Réseaux : vue infra éditable

**Piste d'évolution, non comptée dans les 27 écrans livrés.** Vue Vue Flow des networks et containers d'un Host, **éditable** — à distinguer du Graphe de dépendances (Écran 20, lecture seule) et de l'Éditeur de composition (Écran 21, round-trip compose) : ici les liens représentent les connexions réseau réelles, manipulables à chaud. Point d'entrée : onglet Networks de la vue listes Mode Infra (Écran 25) → bascule `[🕸 Vue infra]`.

```
┌─ Réseaux : nas-server ──────────────────────────────────────────────────────┐
│  Host : [▼ nas-server]        [⊞ Réorganiser (dagre)]  [💾 Positions]  [⋯]  │
│                                                                             │
│   ┌───────────────────┐          ┌──────────────┐                           │
│   │ 🌐 windflow_prod  │────┬────▶│ ☁️ nextcloud  │         ┌──────────┐      │
│   │ bridge · 3 conn.  │    │     │ 🟢 Managé     │         │ Minimap ▢│      │
│   └───────────────────┘    │     └──────────────┘         └──────────┘      │
│                            ├────▶┌──────────────┐                           │
│   ┌───────────────────┐    │     │ 🐙 gitea      │                           │
│   │ 🌐 monitoring     │────┤     │ 🟢 Managé     │                           │
│   │ bridge · 2 conn.  │    │     └──────────────┘                           │
│   └───────────────────┘    └────▶┌──────────────┐                           │
│                                  │ 📊 grafana    │  [Adopter] (Externe)      │
│                                  │ 🟢 Externe    │                           │
│                                  └──────────────┘                           │
│                                                                             │
│  💡 Glisser un lien container → network = docker network connect à chaud ;  │
│     supprimer un lien = disconnect (confirmation en environnement prod).    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** nœuds = networks (driver, nombre de connexions) et containers (badge d'origine `Managé`/`Adopté`/`Externe`, statut runtime) ; création/suppression de liens mappées sur `connect`/`disconnect` à chaud via l'API réseaux (chapitre [09-api.md](09-api.md)), avec confirmation avant toute déconnexion ; **positions des nœuds persistées** par Host (sauvegarde implicite — la disposition survit aux rechargements), disposition automatique dagre disponible en action (chapitre [05-stack-technologique.md](05-stack-technologique.md)). Les nœuds `Externe` offrent le bouton `[Adopter]` (wizard Écran 14). La persistance des positions réutilise le même mécanisme que celui applicable à l'Éditeur de composition (Écran 21).

## Récapitulatif des écrans

| # | Écran | Famille | Mode | Inspiré de | Point saillant |
|---|-------|---------|------|------------|----------------|
| 1 | Dashboard | toutes | App | Umbrel + Runtipi | Grille Apps + widgets plugins + activité |
| 2 | Liste Apps | Apps | App | Cloudron + Runtipi | Actions universelles quel que soit le profil |
| 3 | Détail App | Apps | App/Infra | Proxmox + Cosmos | Squelette commun, onglets canoniques |
| 4 | Marketplace | toutes | App | Umbrel + Runtipi | 3 onglets : Apps / Machine Templates / Plugins |
| 5 | Wizard installation | toutes | App | Scaleway + Cloudron | Mini-wizard, encadré d'impact |
| 6 | Liste Machines | Machines | App | Proxmox + Incus | Power state, snapshots inline, note récursive |
| 7 | Détail Machine | Machines | App/Infra | Proxmox + Incus | Onglets VNC/Disques/Snapshots/Hardware ; « Apps hébergées » conditionnel |
| 8 | Snapshots (arbre) | Machines | App/Infra | Proxmox + VMware | Arbre interactif, alerte chaînes longues |
| 9 | Hardware Editor | Machines | App/Infra | Proxmox + VirtualBox | Indicateur ↻, toggle XML libvirt (Mode Infra) |
| 10 | Liste Hosts | Hosts | App | Coolify | Moteurs détectés, cas récursif explicite ; grappes renvoyées vers l'Écran 27 |
| 11 | Détail Host (baremetal) | Hosts | App | Coolify + Proxmox | Onglets Apps/Machines/Services ; création contextuelle |
| 12 | Détail Host (Machine-as-Host) | Hosts | App | spécifique WindFlow | Navigation croisée [→ Gérer comme Machine] |
| 13 | Wizard Ajouter un Host | Hosts/Clusters | App | Coolify + Proxmox | 3 profils de Host + création de Cluster, détection des moteurs et objets adoptables |
| 14 | Adoption d'objets découverts | toutes | App | Proxmox + Portainer | Adoption granulaire, non-destructive, différable |
| 15 | Wizard création manuelle | Apps/Machines | Infra | Proxmox + Incus | Wizard unifié, sections adaptées au type |
| 16 | Volume Browser | Apps | App/Infra | CasaOS + Nextcloud | Preview inline, breadcrumbs, drag & drop |
| 17 | Console unifiée | toutes | App | Proxmox + Incus | Terminal / VNC / SSH — même chrome UI |
| 18 | Plugins installés | — | App | Runtipi + Cosmos | Résumé d'activité, RAM totale |
| 19 | Activité | toutes | App | Cloudron + Umbrel | Journal filtrable avec actions directes |
| 20 | Graphe de dépendances | toutes | Infra | WorkflowEditor WindFlow + Portainer | Lecture seule, nœuds/depends_on, filtres, adoption inline |
| 21 | Éditeur de composition | Apps | Infra | WorkflowEditor WindFlow + Portainer | Graphe ⇄ YAML, validation cycles, round-trip compose |
| 22 | Vue Compute | toutes | Infra | Portainer + Proxmox | 3 sections (stacks/discovered/standalone), filtres croisés, vue par Host |
| 23 | Settings (Utilisateurs · Audit · Tâches planifiées) | — | App | Cloudron + Proxmox | Gestion des membres, journal d'audit, scheduler core |
| 24 | Login / SSO | — | — | spécifique WindFlow | Auth JWT native + bouton SSO apporté par le plugin Keycloak |
| 25 | Vues listes Mode Infra (Stacks · Volumes · Networks · Images) | toutes | Infra | Portainer | Maquette de référence + variantes par onglet |
| 26 | Assistant IA (page plugin) | — | App/Infra | spécifique WindFlow | Contrat d'intégration plugin : chat, contexte sans secrets, zéro auto-exécution |
| 27 | Clusters (liste et détail) | Clusters | App/Infra | Proxmox (cluster view) + Coolify | Grappes k8s/Proxmox/Swarm : membres avec rôles, santé, workloads hébergés |
| E1 *(évolution)* | Réseaux — vue infra éditable | toutes | Infra | Portainer + Écrans 20/21 WindFlow | connect/disconnect à chaud, positions persistées |

L'onboarding (wizard de premier lancement) est décrit au chapitre [13-ui-principes.md](13-ui-principes.md) ; les variantes mobile/tablette également.

## Voir aussi

- [13-ui-principes.md](13-ui-principes.md) — principes UX, navigation de référence, direction esthétique
- [02-familles-workloads.md](02-familles-workloads.md) — grammaire UI, action bars et onglets canoniques par famille
- [03-modele-compute.md](03-modele-compute.md) — taxonomie derrière l'écran Compute et l'adoption
- [09-api.md](09-api.md) — endpoints et canaux WebSocket consommés par ces écrans
- [12-marketplace.md](12-marketplace.md) — catalogue officiel derrière l'écran Marketplace
