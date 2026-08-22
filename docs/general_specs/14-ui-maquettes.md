# Chapitre 14 — Maquettes d'écrans

> **Statut** : Spec cible · **Public** : Développeurs frontend, designers, product · **Lié à** : [13-ui-principes.md](13-ui-principes.md), [02-familles-workloads.md](02-familles-workloads.md), [03-modele-compute.md](03-modele-compute.md)

## Vue d'ensemble

Ce chapitre présente les **19 écrans** de l'interface WindFlow, renumérotés et nettoyés de tout vestige. Chaque maquette est un bloc ASCII avec sa légende ; la grammaire UI (squelette, action bars, onglets canoniques) et la navigation de référence sont définies aux chapitres [02-familles-workloads.md](02-familles-workloads.md) et [13-ui-principes.md](13-ui-principes.md) — ce chapitre montre des instances concrètes. Valeurs d'exemple cohérentes : Apps `nextcloud`, `gitea`, `jellyfin` ; Machines `ubuntu-dev`, `pfsense-router` ; Hosts `nas-server`, `pi4-home`, `k3s-cluster`, `prox-home`.

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

**Légende :** action bar canonique Apps (chapitre 02) — `[🔗 Ouvrir]` en premier (action la plus courante), split-button `[⏵ Lifecycle ▾]` (Start/Stop/Restart/Pause), badge `⬆` si mise à jour disponible, RAM visible (critique sur RPi).

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

**Légende :** onglets canoniques Apps (Aperçu → Config), onglet « Domaine » ajouté par le plugin Traefik, actions contextuelles des plugins en bas de l'Aperçu. En Mode Infra : onglets additionnels « Composants techniques » et « Manifest ».

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
│  │  💡 Membre du cluster k3s-cluster  [→ Voir le cluster]               │   │
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

**Légende :** action bar canonique Machines — « Power » (pas « Lifecycle »), `Snapshot` canonique, `Hardware` au lieu de `Config`. Split-button `[⏵ Power ▾]` : Power on / Power off (ACPI) / Reboot / Reset / Pause / Suspend. Notes `💡` pour les cas particuliers ; Machines arrêtées → barre réduite aux actions hors-tension.

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

Inspiré de Coolify (cards serveurs) + Proxmox (cluster view). Famille Hosts — sémantique d'administration.

```
┌─ Hosts ───────────────────────────────────────[+ Ajouter un Host]────────┐
│  Mes Hosts (4)              [▼ Tous profils] [▼ Tous statuts]            │
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
│  ┌─ 🖧 k3s-cluster ───────────────────────── 🟢 Online · 3 nodes ──────┐ │
│  │  Profil : Kubernetes (k3s v1.28.5) · 3 nodes amd64                  │ │
│  │  Total : CPU 22% · RAM 8.4/24 GB · 23 pods · 4 namespaces            │ │
│  │  Moteurs : ✗ Docker (containerd)  ✗ libvirt  ✅ k3s + helm           │ │
│  │  [📊 Détails] [🖥 kubectl] [📋 events]                             [⋯] │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│  ┌─ 🖧 prox-home ──────────────────────────── 🔴 Unreachable ──────────┐ │
│  │  Profil : Proxmox VE 8.1 · cluster 2 nodes                          │ │
│  │  Pas de connexion depuis 2h17min · Dernière erreur : timeout API     │ │
│  │  Dernière vue : CPU 8% · 22/64 GB RAM · 15 VMs · 4 LXC               │ │
│  │  [🔄 Réessayer] [📊 Détails (dernière vue)]                       [⋯] │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

**Légende :** action bar canonique Hosts — pas de Lifecycle, pas de Snapshot (chapitre 02). Status pills : `🟢 Online` / `⚪ Offline` / `🔴 Unreachable` / `🔵 Scanning`. Moteurs détectés avec ✓/✗ (déterminent ce qui peut être déployé) ; compteurs `Héberge : X Apps · Y Machines · Z services` ; Host unreachable → actions réduites, aucune action destructive.

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

Inspiré de Coolify (wizard SSH) + Proxmox (datacenter join). Étape 1 : choix du profil parmi `baremetal`, `proxmox`, `kubernetes`, `remote-docker`.

```
┌─ Ajouter un Host ────────────────────────────────────────────────────────┐
│  ○────●────○────○                                                        │
│  Type Connexion Tester Confirmer                                         │
│                                                                            │
│  Étape 1 — Quel type de Host souhaitez-vous ajouter ?                     │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐           │
│  │ 🖧 Baremetal SSH │ │ 🖥️ Proxmox VE    │ │ ⎈ Kubernetes     │           │
│  │ Machine          │ │ Serveur ou       │ │ Cluster k8s,     │           │
│  │ physique ou VM   │ │ cluster Proxmox  │ │ k3s, microk8s    │           │
│  │ accessible SSH   │ │ via son API      │ │ via kubeconfig   │           │
│  │ [Choisir]        │ │ [Choisir]        │ │ [Choisir]        │           │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘           │
│  ┌──────────────────┐                                                   │
│  │ 🐳 Docker distant│  Daemon Docker accessible par SSH ou TCP TLS      │
│  │ [Choisir]        │                                                   │
│  └──────────────────┘                                                   │
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

**Légende :** le wizard partage stepper, sections « Nom / Host / Ressources » et bouton « Déployer » entre types ; seules les sections spécifiques diffèrent (Image Docker vs Template OS, Ports vs Cloud-init). La variante Container expose Nom, Image (avec recherche), Host, RAM/CPU limits, Ports, et les sections dépliables Volumes / Réseau / Env vars / Labels.

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
| 10 | Liste Hosts | Hosts | App | Coolify + Proxmox | Moteurs détectés, cas récursif explicite |
| 11 | Détail Host (baremetal) | Hosts | App | Coolify + Proxmox | Onglets Apps/Machines/Services ; création contextuelle |
| 12 | Détail Host (Machine-as-Host) | Hosts | App | spécifique WindFlow | Navigation croisée [→ Gérer comme Machine] |
| 13 | Wizard Ajouter un Host | Hosts | App | Coolify + Proxmox | 4 profils, détection des moteurs et objets adoptables |
| 14 | Adoption d'objets découverts | toutes | App | Proxmox + Portainer | Adoption granulaire, non-destructive, différable |
| 15 | Wizard création manuelle | Apps/Machines | Infra | Proxmox + Incus | Wizard unifié, sections adaptées au type |
| 16 | Volume Browser | Apps | App/Infra | CasaOS + Nextcloud | Preview inline, breadcrumbs, drag & drop |
| 17 | Console unifiée | toutes | App | Proxmox + Incus | Terminal / VNC / SSH — même chrome UI |
| 18 | Plugins installés | — | App | Runtipi + Cosmos | Résumé d'activité, RAM totale |
| 19 | Activité | toutes | App | Cloudron + Umbrel | Journal filtrable avec actions directes |

L'onboarding (wizard de premier lancement) est décrit au chapitre [13-ui-principes.md](13-ui-principes.md) ; les variantes mobile/tablette également.

## Voir aussi

- [13-ui-principes.md](13-ui-principes.md) — principes UX, navigation de référence, direction esthétique
- [02-familles-workloads.md](02-familles-workloads.md) — grammaire UI, action bars et onglets canoniques par famille
- [03-modele-compute.md](03-modele-compute.md) — taxonomie derrière l'écran Compute et l'adoption
- [09-api.md](09-api.md) — endpoints et canaux WebSocket consommés par ces écrans
- [12-marketplace.md](12-marketplace.md) — catalogue officiel derrière l'écran Marketplace
