# Propositions de Maquettes d'Écran - WindFlow

## Analyse des Interfaces Existantes

Avant de concevoir l'UI de WindFlow, il est utile d'identifier ce qui fonctionne et ce qui ne fonctionne pas dans les outils concurrents.

### Ce qu'on emprunte

| Outil | Ce qui marche | On prend pour WindFlow |
|-------|---------------|----------------------|
| **Portainer** | Dashboard avec tuiles compteurs (containers, images, volumes). Liste de containers avec actions en ligne (start/stop/restart). Stack editor intégré. | Tuiles synthétiques sur le dashboard. Actions en ligne sur chaque ressource. Éditeur de stacks. |
| **CasaOS** | App Store type smartphone (grille d'icônes, installation one-click). Interface épurée orientée grand public. Frosted glass effect. | Marketplace en grille avec icônes. Wizard d'installation simplifié. Esthétique moderne et accessible. |
| **Proxmox** | Arbre de navigation latéral (Datacenter → Node → VM/CT). Onglets détails par ressource (Summary, Console, Hardware, Snapshots). Recherche globale. | Arbre de navigation par target. Onglets détaillés par ressource. Console VNC intégrée. |
| **Coolify** | Navigation par projet avec déploiements. Vue serveur avec métriques. One-click services. | Concept de stack comme unité de déploiement. Métriques inline sur les targets. |
| **Cloudron** | App store épuré avec catégories. Gestion domaines + TLS intégrée. Mise à jour apps en un clic. | Marketplace catégorisée. Mises à jour plugins simplifiées. |

### Ce qu'on évite

| Outil | Problème UX | On évite |
|-------|-------------|----------|
| **Portainer** | Trop de niveaux de navigation (Home → Environment → Container list → Container detail). Multi-environment ajoute de la complexité. | Navigation max 2 clics pour atteindre n'importe quelle ressource. |
| **Proxmox** | Interface datée (ExtJS), dense, intimidante pour les non-sysadmins. Pas de marketplace. | Design moderne. Marketplace comme citoyen de première classe. |
| **Coolify** | Dashboard qui n'affiche presque rien d'utile. Il faut 3 pages pour arriver à la config d'un service. | Dashboard actionnable. Actions directes depuis les listes. |
| **CasaOS** | Trop simpliste pour de la gestion d'infra. Pas de gestion de VMs, pas de multi-machine. | Garder la simplicité visuelle mais avec la profondeur technique nécessaire. |

---

## Principes UX WindFlow

### Règle des 2 Clics

Toute ressource (container, VM, stack, plugin) est accessible en **2 clics maximum** depuis le dashboard. Le premier clic choisit la catégorie (sidebar), le second sélectionne la ressource.

### Dashboard Actionnable

Le dashboard n'est pas juste un résumé — c'est un point de départ pour agir. Chaque élément affiché est cliquable et mène directement à l'action pertinente.

### Sidebar Stable + Contenu Dynamique

La sidebar reste visible et stable sur toutes les pages. Elle montre les sections core + les sections ajoutées par les plugins. Le contenu central change selon la sélection.

### Plugins Visibles, Pas Envahissants

Les plugins qui ajoutent des pages apparaissent dans la sidebar sous une section "Plugins". Les plugins qui ajoutent des widgets apparaissent dans le dashboard. Mais un utilisateur sans plugin voit une interface propre et non vide.

### Thème Sombre par Défaut

Le self-hosting est souvent fait le soir sur un bureau perso. Thème sombre par défaut, thème clair disponible.

---

## Navigation Globale

### Structure de la Sidebar

```
┌──────────────────────┐
│  🌀 WindFlow          │
│                      │
│  📊 Dashboard        │  ← Vue d'ensemble + widgets plugins
│                      │
│  INFRASTRUCTURE      │
│  📦 Containers       │  ← Liste containers Docker
│  🖥️ VMs              │  ← Liste machines virtuelles
│  📚 Stacks           │  ← Stacks Docker Compose
│  🎯 Targets          │  ← Machines cibles
│                      │
│  STOCKAGE & RÉSEAU   │
│  💾 Volumes          │  ← Volumes Docker + file browser
│  🌐 Networks         │  ← Networks Docker
│  🖼️ Images           │  ← Images Docker
│                      │
│  MARKETPLACE         │
│  🏪 Marketplace      │  ← Catalogue plugins + stacks
│  🔌 Plugins          │  ← Plugins installés
│                      │
│  ── Plugins ──       │  ← Section dynamique (ajoutée par plugins)
│  🌍 Domaines         │  ← (Plugin Traefik)
│  📈 Monitoring       │  ← (Plugin Uptime Kuma)
│  💾 Backups          │  ← (Plugin Restic)
│  🤖 Assistant IA     │  ← (Plugin Ollama/LiteLLM)
│                      │
│  ADMINISTRATION      │
│  ⚙️ Settings         │  ← Orgs, envs, users, RBAC
│  📋 Audit            │  ← Journal d'audit
│                      │
│  ─────────────────── │
│  🟢 local (arm64)    │  ← Target actif + sélecteur
│  admin               │  ← Utilisateur connecté
└──────────────────────┘
```

La sidebar est rétractable en mode icônes sur les petits écrans. La section "Plugins" n'apparaît que si au moins un plugin avec pages UI est installé.

---

## Écran 1 : Dashboard

Le dashboard est la page d'accueil. Il montre l'état de l'infrastructure en un coup d'œil et permet d'agir directement.

```
┌─ 🌀 WindFlow ──────────────────────────────────────────────────────────────────┐
│ Sidebar │                                                                      │
│         │  Dashboard                                        🎯 local (arm64)   │
│ (voir   │                                                                      │
│  ci-    │  ┌─ Système ─────────────────────────────────────────────────────┐   │
│  dessus)│  │  CPU ████░░░░░░ 38%    RAM ██████░░░░ 1.2/4 GB              │   │
│         │  │  Disque █████████░ 28/64 GB    Uptime: 15j 3h               │   │
│         │  └───────────────────────────────────────────────────────────────┘   │
│         │                                                                      │
│         │  ┌─ Containers ──────┐ ┌─ VMs ───────────────┐ ┌─ Stacks ────────┐ │
│         │  │  🟢 4 running     │ │  🟢 1 running       │ │  ✅ 3 deployed  │ │
│         │  │  🔴 1 stopped     │ │  ⚪ 1 stopped       │ │  ⚪ 1 stopped   │ │
│         │  │  5 total          │ │  2 total             │ │  4 total        │ │
│         │  │  [Voir tout →]    │ │  [Voir tout →]       │ │  [Voir tout →]  │ │
│         │  └──────────────────┘ └──────────────────────┘ └────────────────┘ │
│         │                                                                      │
│         │  ┌─ Derniers Déploiements ───────────────────────────────────────┐   │
│         │  │  ✅ web-app        deployed   il y a 2h    par admin         │   │
│         │  │  ❌ monitoring     failed     il y a 5h    par admin         │   │
│         │  │  ✅ nextcloud      deployed   il y a 1j    par alice         │   │
│         │  └───────────────────────────────────────────────────────────────┘   │
│         │                                                                      │
│         │  ┌─ Widgets Plugins ─────────────────────────────────────────────┐   │
│         │  │ ┌─ Uptime Kuma ──────┐  ┌─ Traefik ────────────────────┐    │   │
│         │  │ │  ✅ 5/5 UP         │  │  🌍 3 domaines actifs        │    │   │
│         │  │ │  nextcloud  ✅     │  │  🔒 3 certificats valides    │    │   │
│         │  │ │  gitea      ✅     │  │  [Gérer les domaines →]      │    │   │
│         │  │ │  jellyfin   ✅     │  └──────────────────────────────┘    │   │
│         │  │ │  api        ✅     │                                      │   │
│         │  │ │  blog       ✅     │  ┌─ Backups (Restic) ───────────┐    │   │
│         │  │ │  [Détails →]       │  │  ✅ Dernier: il y a 6h       │    │   │
│         │  │ └────────────────────┘  │  📦 3 volumes sauvegardés    │    │   │
│         │  │                         │  [Voir les backups →]         │    │   │
│         │  │                         └──────────────────────────────┘    │   │
│         │  └───────────────────────────────────────────────────────────────┘   │
│         │                                                                      │
└─────────┴──────────────────────────────────────────────────────────────────────┘
```

**Points clés :**
- Barre système en haut : CPU, RAM, disque du target actif, uptime
- 3 tuiles compteurs : Containers, VMs, Stacks — cliquables pour accéder aux listes
- Derniers déploiements avec statut et lien direct
- Zone widgets plugins : chaque plugin peut injecter un widget. Sans plugin, cette zone n'apparaît pas
- Le sélecteur de target (🎯) en haut à droite permet de basculer entre machines

---

## Écran 2 : Liste Containers

```
┌─ Containers ───────────────────────────────────────────────────────────────────┐
│                                                                                │
│  Containers (5)          🎯 local          [🔍 Rechercher...]  [+ Créer]      │
│                                                                                │
│  Filtres: [Tous ▾] [Running ▾] [Target ▾]                                     │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │ ☐  NOM            IMAGE              STATUT     PORTS         ACTIONS   │  │
│  ├──────────────────────────────────────────────────────────────────────────┤  │
│  │ ☐  nextcloud      nextcloud:28       🟢 run     8080→80      ⏸ 📋 🗑   │  │
│  │ ☐  postgres-1     postgres:15        🟢 run     5432→5432    ⏸ 📋 🗑   │  │
│  │ ☐  redis          redis:7-alpine     🟢 run     6379→6379    ⏸ 📋 🗑   │  │
│  │ ☐  gitea          gitea/gitea:1.21   🟢 run     3000→3000    ⏸ 📋 🗑   │  │
│  │ ☐  old-app        myapp:1.0          🔴 stop    —            ▶ 📋 🗑   │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  Sélection: [▶ Start] [⏸ Stop] [🔄 Restart] [🗑 Supprimer]                   │
│                                                                                │
│  Actions rapides: ⏸ = Stop  📋 = Logs  🗑 = Supprimer  ▶ = Start             │
│                                                                                │
│  💡 Tip: Le plugin PostgreSQL détecte vos containers postgres.                 │
│     [Installer PostgreSQL Manager →]                                           │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Points clés :**
- Actions inline par container (stop, logs, supprimer) — pas besoin d'ouvrir le détail pour agir
- Sélection multiple avec actions groupées (comme Portainer)
- Suggestion contextuelle de plugins pertinents (si un container postgres est détecté et que le plugin n'est pas installé)
- Cliquer sur le nom ouvre le détail du container

---

## Écran 3 : Détail Container

```
┌─ Container: nextcloud ─────────────────────────────────────────────────────────┐
│                                                                                │
│  nextcloud                              🟢 Running depuis 3 jours             │
│  Image: nextcloud:28                    Target: local                          │
│                                                                                │
│  [⏸ Stop] [🔄 Restart] [📋 Logs] [>_ Terminal] [🔍 Inspect]                 │
│                                                                                │
│  ┌─ Infos ──────────┬─ Logs ──────────┬─ Terminal ──┬─ Stats ──┬─ Plugin ──┐  │
│  │                  │                 │             │          │           │  │
│  │  ──── Onglet Infos (actif) ────                                        │  │
│  │                                                                        │  │
│  │  ID: 3a7f2b1c9d...                                                    │  │
│  │  Créé: 2026-03-28 10:15                                               │  │
│  │  Stack: nextcloud-stack                                                │  │
│  │                                                                        │  │
│  │  Ports:                                                                │  │
│  │    8080 → 80/tcp                                                       │  │
│  │                                                                        │  │
│  │  Volumes:                                                              │  │
│  │    nextcloud_data → /var/www/html    [📂 Parcourir]                    │  │
│  │    nextcloud_config → /var/www/html/config  [📂 Parcourir]             │  │
│  │                                                                        │  │
│  │  Réseau: windflow-homelab-prod                                         │  │
│  │                                                                        │  │
│  │  Variables d'environnement:                                            │  │
│  │    POSTGRES_HOST = postgres-1                                          │  │
│  │    POSTGRES_DB = nextcloud                                             │  │
│  │    POSTGRES_PASSWORD = ●●●●●●●● [👁]                                  │  │
│  │                                                                        │  │
│  │  ──── Actions Plugin (PostgreSQL Manager) ────                         │  │
│  │  Ce container utilise PostgreSQL. Actions disponibles :                 │  │
│  │  [Créer une DB] [Créer un User] [Backup SQL] [Stats DB]               │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Points clés :**
- Onglets horizontaux : Infos, Logs, Terminal, Stats, et un onglet par plugin actif sur ce container
- Accès direct au volume browser depuis le détail
- Actions plugin contextuelles en bas (ex: PostgreSQL Manager détecte que ce container utilise postgres)
- Mot de passe masqué avec bouton révéler

---

## Écran 4 : Liste VMs

```
┌─ Machines Virtuelles ──────────────────────────────────────────────────────────┐
│                                                                                │
│  VMs (2)                 🎯 local          [🔍 Rechercher...]  [+ Créer]      │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  NOM            HYPERVISEUR  STATUT     vCPU  RAM      ACTIONS          │  │
│  ├──────────────────────────────────────────────────────────────────────────┤  │
│  │  ubuntu-dev     KVM          🟢 run     2     2 GB     🖥 ⏸ 📸 🗑      │  │
│  │  windows-10     KVM          🔴 stop    4     8 GB     🖥 ▶ 📸 🗑      │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  🖥 = Console    ⏸ = Stop    ▶ = Start    📸 = Snapshot    🗑 = Supprimer     │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Points clés :**
- Bouton Console (🖥) ouvre directement la console VNC/SPICE dans un nouvel onglet ou un panneau
- Snapshot en un clic depuis la liste

---

## Écran 5 : Console VM (noVNC intégré)

```
┌─ Console: ubuntu-dev ──────────────────────────────────────────────────────────┐
│                                                                                │
│  ubuntu-dev (KVM)        🟢 Running        [Ctrl+Alt+Del] [Plein Écran]       │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                                                                          │  │
│  │                                                                          │  │
│  │                    ┌──────────────────────────┐                           │  │
│  │                    │  ubuntu@ubuntu-dev:~$ _  │                           │  │
│  │                    │                          │                           │  │
│  │                    │                          │                           │  │
│  │                    │   Console VNC / SPICE    │                           │  │
│  │                    │   (noVNC embedded)       │                           │  │
│  │                    │                          │                           │  │
│  │                    │                          │                           │  │
│  │                    └──────────────────────────┘                           │  │
│  │                                                                          │  │
│  │                                                                          │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  Résolution: 1024x768  |  Qualité: Auto  |  Clipboard: Sync                   │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Inspiration :** Proxmox fait ça très bien — console intégrée dans un onglet de l'interface web, avec boutons Ctrl+Alt+Del et plein écran.

---

## Écran 6 : Stacks

```
┌─ Stacks ───────────────────────────────────────────────────────────────────────┐
│                                                                                │
│  Stacks (4)              🎯 local    [🔍 Rechercher]  [+ Créer] [📦 Marketplace]│
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  NOM            SERVICES        STATUT        VERSION   ACTIONS          │  │
│  ├──────────────────────────────────────────────────────────────────────────┤  │
│  │  nextcloud      3 services      ✅ deployed   v3        🔄 ⏸ ↩ 📝     │  │
│  │  web-app        2 services      ✅ deployed   v5        🔄 ⏸ ↩ 📝     │  │
│  │  gitea          2 services      ✅ deployed   v1        🔄 ⏸ ↩ 📝     │  │
│  │  monitoring     4 services      ⏸ stopped     v2        ▶  🗑 ↩ 📝     │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  🔄 = Re-deploy    ⏸ = Stop    ▶ = Start    ↩ = Rollback    📝 = Éditer       │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

Le détail d'une stack montre l'éditeur YAML + l'historique des versions + le log du dernier déploiement.

---

## Écran 7 : Marketplace

La marketplace est l'écran clé de WindFlow — c'est ce qui le différencie de Portainer. Inspiration directe de CasaOS et des stores d'apps mobiles.

```
┌─ Marketplace ──────────────────────────────────────────────────────────────────┐
│                                                                                │
│  [🔍 Rechercher plugins et stacks...]                                         │
│                                                                                │
│  [Tout] [Plugins] [Stacks]    Catégories: [Accès] [Monitoring] [DB] [Backup]  │
│                                            [Sécurité] [Git] [Mail] [IA] [...]  │
│                                                                                │
│  ── Plugins Populaires ────────────────────────────────────────────────────── │
│                                                                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │
│  │  🔀          │ │  📊          │ │  🐘          │ │  💾          │         │
│  │  Traefik     │ │  Uptime Kuma │ │  PostgreSQL  │ │  Restic      │         │
│  │              │ │              │ │  Manager     │ │              │         │
│  │  Reverse     │ │  Monitoring  │ │  Gestion DB  │ │  Backup      │         │
│  │  proxy + TLS │ │  uptime      │ │  intégrée    │ │  automatique │         │
│  │              │ │              │ │              │ │              │         │
│  │  128 Mo RAM  │ │  128 Mo RAM  │ │  32 Mo RAM   │ │  64 Mo RAM   │         │
│  │  arm64 ✓     │ │  arm64 ✓     │ │  arm64 ✓     │ │  arm64 ✓     │         │
│  │              │ │              │ │              │ │              │         │
│  │ [Installer]  │ │ [Installer]  │ │ [Installé ✓] │ │ [Installer]  │         │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘         │
│                                                                                │
│  ── Stacks One-Click ──────────────────────────────────────────────────────── │
│                                                                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │
│  │  ☁️           │ │  🐙          │ │  🎬          │ │  🏠          │         │
│  │  Nextcloud   │ │  Gitea       │ │  Jellyfin    │ │  Home        │         │
│  │              │ │              │ │              │ │  Assistant   │         │
│  │  Cloud perso │ │  Git self-   │ │  Streaming   │ │  Domotique   │         │
│  │              │ │  hosted      │ │  média       │ │              │         │
│  │              │ │              │ │              │ │              │         │
│  │ [Déployer]   │ │ [Déployer]   │ │ [Déployer]   │ │ [Déployer]   │         │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘         │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Points clés :**
- Séparation visuelle entre Plugins (étendent WindFlow) et Stacks (applications complètes)
- Chaque carte montre : icône, nom, description courte, RAM requise, compatibilité ARM
- Bouton vert "Installé ✓" pour les plugins déjà présents
- Onglets de catégorie en haut pour filtrer rapidement

---

## Écran 8 : Fiche Plugin (Marketplace)

```
┌─ Plugin: Traefik ──────────────────────────────────────────────────────────────┐
│                                                                                │
│  ← Retour à la Marketplace                                                    │
│                                                                                │
│  🔀 Traefik — Reverse Proxy                            [Installer]            │
│                                                                                │
│  Reverse proxy moderne avec TLS automatique via                                │
│  Let's Encrypt. Permet d'associer des noms de domaine                          │
│  à vos services depuis l'interface WindFlow.                                   │
│                                                                                │
│  ┌─ Détails ──────────────────────────────────────────────────────────────┐   │
│  │  Type:           Hybrid (service + extension)                          │   │
│  │  Catégorie:      Accès & Routage                                       │   │
│  │  Version:        1.2.0                                                 │   │
│  │  Auteur:         WindFlow Team (officiel)                               │   │
│  │  Licence:        MIT                                                   │   │
│  │  Architectures:  amd64 ✓  arm64 ✓                                     │   │
│  │  RAM minimum:    128 Mo                                                │   │
│  │  Fournit:        reverse_proxy, tls_certificates                       │   │
│  │  Dépendances:    Docker                                                │   │
│  │  Conflits:       Nginx Proxy Manager, Caddy                            │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                                                                                │
│  ┌─ Ce que ce plugin ajoute ──────────────────────────────────────────────┐   │
│  │  ✓ Page "Domaines & Routage" dans le menu WindFlow                     │   │
│  │  ✓ Association domaine ↔ service en un clic                            │   │
│  │  ✓ Certificats TLS automatiques (Let's Encrypt)                        │   │
│  │  ✓ Auto-configuration lors du déploiement de stacks                    │   │
│  │  ✓ Widget dashboard avec routes actives                                │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                                                                                │
│  ┌─ Compatibilité ───────────────────────────────────────────────────────┐   │
│  │  ✅ Architecture compatible (arm64)                                    │   │
│  │  ✅ RAM suffisante (1.2 Go libre, 128 Mo requis)                       │   │
│  │  ✅ Docker disponible sur le target actif                              │   │
│  │  ⚠️ Ports 80 et 443 seront utilisés par Traefik                       │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                                                                                │
│  [Installer Traefik]                                                          │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Points clés :**
- Vérification de compatibilité automatique avant installation (arch, RAM, dépendances)
- Description claire de ce que le plugin ajoute à l'interface
- Avertissements (ports utilisés, conflits)

---

## Écran 9 : Wizard d'Installation Plugin

```
┌─ Installation: Traefik ────────────────────────────────────────────────────────┐
│                                                                                │
│  Étape 2/3 — Configuration                                                    │
│  ● Vérification  ● Configuration  ○ Installation                              │
│                                                                                │
│  ┌─ Configuration Traefik ────────────────────────────────────────────────┐   │
│  │                                                                        │   │
│  │  Email Let's Encrypt *                                                 │   │
│  │  ┌──────────────────────────────────────────────────┐                  │   │
│  │  │ admin@example.com                                │                  │   │
│  │  └──────────────────────────────────────────────────┘                  │   │
│  │  Utilisé pour les notifications d'expiration de certificats            │   │
│  │                                                                        │   │
│  │  Activer le dashboard Traefik                                          │   │
│  │  [✓ Oui]                                                               │   │
│  │                                                                        │   │
│  │  Niveau de logs                                                        │   │
│  │  ┌──────────────────────────────────────────────────┐                  │   │
│  │  │ INFO                                         [▾] │                  │   │
│  │  └──────────────────────────────────────────────────┘                  │   │
│  │                                                                        │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                                                                                │
│                                            [← Retour]  [Installer →]          │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Points clés :**
- Wizard par étapes : Vérification → Configuration → Installation
- Formulaire généré dynamiquement depuis le manifest du plugin
- Descriptions inline pour chaque champ
- On ne montre que les champs nécessaires (pas de config avancée par défaut)

---

## Écran 10 : Volume Browser

```
┌─ Volume: nextcloud_data ───────────────────────────────────────────────────────┐
│                                                                                │
│  📂 nextcloud_data (2.1 GB)           [⬆ Upload] [📄 Nouveau fichier]         │
│                                                                                │
│  Chemin: / data / nextcloud / config /                                         │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  NOM                TYPE      TAILLE    MODIFIÉ           ACTIONS        │  │
│  ├──────────────────────────────────────────────────────────────────────────┤  │
│  │  📁 ..              dossier   —         —                 —              │  │
│  │  📄 config.php      fichier   12 KB     2026-04-01 14:30  📝 ⬇ 🗑       │  │
│  │  📄 .htaccess       fichier   0.4 KB    2026-03-28 10:15  📝 ⬇ 🗑       │  │
│  │  📄 CAN_INSTALL     fichier   0.0 KB    2026-03-28 10:15  📝 ⬇ 🗑       │  │
│  │  📁 themes          dossier   —         2026-03-28 10:15  —              │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  📝 = Éditer    ⬇ = Télécharger    🗑 = Supprimer                             │
│                                                                                │
│  ┌─ Prévisualisation: config.php ─────────────────────────────────────────┐   │
│  │  <?php                                                                 │   │
│  │  $CONFIG = array (                                                     │   │
│  │    'instanceid' => 'oc3a7f2b1c',                                       │   │
│  │    'passwordsalt' => '●●●●●●●●●●',                                    │   │
│  │    'trusted_domains' =>                                                │   │
│  │      array (                                                           │   │
│  │        0 => 'cloud.example.com',                                       │   │
│  │    ...                                                                 │   │
│  │                                                    [Éditer] [Fermer]   │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Inspiration :** Gestionnaire de fichiers web classique (type FileBrowser, Nextcloud Files) mais intégré à WindFlow. Pas besoin de SSH pour éditer un fichier de config.

---

## Écran 11 : Targets

```
┌─ Targets ──────────────────────────────────────────────────────────────────────┐
│                                                                                │
│  Targets (3)                        [🔍 Rechercher]  [+ Ajouter un target]    │
│                                                                                │
│  ┌─ local ───────────────────────────────────────────────────────── 🟢 ────┐  │
│  │  Type: Local  │  Arch: arm64  │  OS: Raspberry Pi OS 12                 │  │
│  │  CPU: ████░░░░░░ 38% (4 cores)                                          │  │
│  │  RAM: ██████░░░░ 1.2/4.0 GB                                             │  │
│  │  Disk: █████████░ 28/64 GB                                               │  │
│  │  Docker: ✅ 24.0.7   KVM: ✅ 9.0.0   Proxmox: —                        │  │
│  │  Containers: 5 (4 running)  │  VMs: 2 (1 running)  │  Stacks: 4        │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  ┌─ remote-srv ──────────────────────────────────────────────────── 🟢 ────┐  │
│  │  Type: SSH (deploy@192.168.1.50)  │  Arch: amd64  │  OS: Debian 12     │  │
│  │  CPU: ██░░░░░░░░ 12% (8 cores)                                          │  │
│  │  RAM: ████░░░░░░ 6.2/32 GB                                              │  │
│  │  Disk: ███░░░░░░░ 89/500 GB                                              │  │
│  │  Docker: ✅ 25.0.3   KVM: —   Proxmox: —                               │  │
│  │  Containers: 12 (10 running)  │  VMs: 0  │  Stacks: 6                  │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  ┌─ proxmox-1 ──────────────────────────────────────────────────── 🔴 ────┐  │
│  │  Type: Proxmox (192.168.1.100)  │  Arch: amd64  │  Proxmox VE 8.1     │  │
│  │  ⚠️ Connexion perdue il y a 2h — Dernière vue: 2026-04-01 12:30        │  │
│  │  [🔄 Réessayer la connexion]                                            │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Points clés :**
- Chaque target est une carte avec ses métriques inline (pas besoin d'ouvrir un détail pour voir la RAM)
- Barres de progression visuelles pour CPU/RAM/disque
- Capabilities détectées (Docker, KVM, Proxmox) avec versions
- Compteurs de ressources gérées (containers, VMs, stacks)
- État de connexion visible immédiatement (🟢/🔴)

---

## Écran 12 : Plugins Installés

```
┌─ Plugins Installés ───────────────────────────────────────────────────────────┐
│                                                                                │
│  Plugins (3)                         [🏪 Marketplace]  [🔄 Tout mettre à jour]│
│                                                                                │
│  ┌─ Traefik ─────────────────────────────────────────────────── 🟢 ────────┐  │
│  │  v1.2.0 │ Hybrid │ Accès & Routage       RAM: 142 MB                   │  │
│  │  3 domaines configurés, 3 certificats valides                           │  │
│  │  [⚙ Config] [⏸ Stop] [🔄 Mettre à jour] [🗑 Désinstaller]             │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  ┌─ PostgreSQL Manager ──────────────────────────────────────── 🟢 ────────┐  │
│  │  v1.0.0 │ Extension │ Bases de données    RAM: 28 MB                    │  │
│  │  2 containers postgres détectés, 5 databases gérées                     │  │
│  │  [⚙ Config] [🔄 Mettre à jour] [🗑 Désinstaller]                       │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  ┌─ Uptime Kuma ─────────────────────────────────────────────── 🟢 ────────┐  │
│  │  v1.0.0 │ Service │ Monitoring            RAM: 98 MB       ⬆ v1.1.0    │  │
│  │  5 monitors actifs, tous UP                                             │  │
│  │  [⚙ Config] [⏸ Stop] [🔄 Mettre à jour] [🗑 Désinstaller]             │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  RAM totale plugins: 268 MB / 4096 MB disponibles                             │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Points clés :**
- Chaque plugin montre son type, sa catégorie, sa RAM consommée
- Résumé de l'activité du plugin (domaines, databases gérées, monitors actifs)
- Badge de mise à jour disponible
- Compteur total de RAM plugins en bas

---

## Écran 13 : Page Plugin (Traefik — Domaines)

Exemple d'écran injecté par un plugin dans la sidebar.

```
┌─ Domaines & Routage (Traefik) ─────────────────────────────────────────────────┐
│                                                                                │
│  Domaines (3)                                            [+ Ajouter un domaine]│
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  DOMAINE              SERVICE          TLS       STATUT     ACTIONS      │  │
│  ├──────────────────────────────────────────────────────────────────────────┤  │
│  │  cloud.example.com    nextcloud:80     🔒 Valide ✅ OK      📝 🗑       │  │
│  │                                        expire: 89j                      │  │
│  │  git.example.com      gitea:3000       🔒 Valide ✅ OK      📝 🗑       │  │
│  │                                        expire: 89j                      │  │
│  │  app.example.com      web-app:8080     🔒 Valide ✅ OK      📝 🗑       │  │
│  │                                        expire: 45j                      │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  ┌─ Ajouter un domaine ──────────────────────────────────────────────────┐    │
│  │                                                                        │    │
│  │  Domaine:     ┌────────────────────────────────────────┐               │    │
│  │               │ photos.example.com                     │               │    │
│  │               └────────────────────────────────────────┘               │    │
│  │                                                                        │    │
│  │  Service:     ┌────────────────────────────────────────┐               │    │
│  │               │ immich (port 2283)                 [▾] │               │    │
│  │               └────────────────────────────────────────┘               │    │
│  │               Liste auto-complétée depuis les containers running       │    │
│  │                                                                        │    │
│  │  TLS:         [✓] Certificat Let's Encrypt automatique                 │    │
│  │                                                                        │    │
│  │                                            [Annuler] [Ajouter →]       │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Points clés :**
- Le dropdown "Service" est auto-complété depuis les containers running
- TLS automatique par défaut (Let's Encrypt)
- Expiration du certificat visible directement dans la liste

---

## Écran 14 : Settings

```
┌─ Paramètres ───────────────────────────────────────────────────────────────────┐
│                                                                                │
│  [Organisations] [Environnements] [Utilisateurs] [Registres] [Système]        │
│                                                                                │
│  ── Utilisateurs ──────────────────────────────────────────────────────────── │
│                                                                                │
│  Organisation: homelab                                  [+ Ajouter un membre]  │
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  UTILISATEUR    EMAIL                  RÔLE        CONNECTÉ    ACTIONS   │  │
│  ├──────────────────────────────────────────────────────────────────────────┤  │
│  │  admin          admin@example.com      🔑 Super    il y a 5m   ⚙        │  │
│  │  alice          alice@example.com      👤 Operator il y a 2h   ⚙ 🗑     │  │
│  │  bob            bob@example.com        👁 Viewer   il y a 3j   ⚙ 🗑     │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## Responsive & Mobile

WindFlow n'est pas une app mobile, mais le dashboard doit être lisible sur tablette et smartphone pour vérifier rapidement l'état de l'infrastructure.

**Tablette (≥768px) :** Sidebar rétractée en icônes, contenu pleine largeur. Les cartes target passent en une colonne.

**Mobile (≤480px) :** Sidebar remplacée par un hamburger menu. Dashboard en cards empilées. Actions containers/VMs accessibles via menu contextuel au lieu de boutons inline. Console VNC et terminal non disponibles (trop petit).

---

## Palette de Couleurs et Typographie

### Direction Esthétique

**Industriel-épuré** — L'esthétique de WindFlow doit être celle d'un outil d'ingénieur moderne : sobre, lisible, sans fioriture, mais avec des touches de couleur fonctionnelles (vert = ok, rouge = erreur, bleu = action).

**Typographie :**
- Titres et UI : **Inter** ou **IBM Plex Sans** (lisible, technique, multi-plateforme)
- Code et logs : **JetBrains Mono** ou **Fira Code** (monospace avec ligatures)
- Pas de serif, pas de fantaisie — c'est un outil, pas un portfolio

**Couleurs (thème sombre) :**
- Fond principal : `#0f1117` (presque noir, comme un terminal)
- Fond cartes : `#1a1d27` (léger contraste)
- Bordures : `#2a2d37` (subtil)
- Texte principal : `#e1e4eb` (blanc cassé, pas blanc pur)
- Texte secondaire : `#8b8fa3`
- Accent principal : `#3b82f6` (bleu)
- Succès : `#22c55e` (vert)
- Erreur : `#ef4444` (rouge)
- Warning : `#f59e0b` (orange)

---

## Résumé des Écrans

| # | Écran | Inspiration principale | Fonction clé |
|---|-------|----------------------|--------------|
| 1 | Dashboard | Portainer (tuiles) + CasaOS (widgets) | Vue d'ensemble + widgets plugins |
| 2 | Liste Containers | Portainer (table + actions) | Actions inline, pas de navigation |
| 3 | Détail Container | Portainer (onglets) + Proxmox (tabs) | Onglets + actions plugin contextuelles |
| 4 | Liste VMs | Proxmox (table) | Console en un clic |
| 5 | Console VM | Proxmox (noVNC) | VNC intégré au navigateur |
| 6 | Stacks | Portainer (stacks) | Versions + rollback |
| 7 | Marketplace | CasaOS (app store) + Cloudron | Grille plugins + stacks one-click |
| 8 | Fiche Plugin | App Store mobile | Compatibilité + description |
| 9 | Wizard Installation | Cloudron | Formulaire généré depuis manifest |
| 10 | Volume Browser | FileBrowser / Nextcloud Files | Navigation + édition + preview |
| 11 | Targets | Custom | Cartes avec métriques inline |
| 12 | Plugins Installés | Custom | État + RAM + actions |
| 13 | Page Plugin (Traefik) | Custom | Domaines + auto-complétion services |
| 14 | Settings | Standard | Orgs, users, RBAC |

---

**Références :**
- [Fonctionnalités Principales](general_specs/10-core-features.md) — Features core derrière chaque écran
- [Architecture Modulaire](ARCHITECTURE-MODULAIRE.md) — Comment les plugins injectent des pages et widgets
- [API Design](general_specs/07-api-design.md) — Endpoints consommés par chaque écran
- [Catalogue des Plugins](general_specs/09-plugins.md) — Plugins disponibles dans la marketplace
