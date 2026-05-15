# Vue d'Ensemble — WindFlow

## Qu'est-ce que WindFlow ?

WindFlow est un **gestionnaire d'infrastructure self-hosted** pour piloter des containers Docker, des compositions (Compose, Helm) et des machines virtuelles depuis une interface web unique. Il est conçu pour tourner aussi bien sur un Raspberry Pi 4 que sur un serveur x86 dédié ou un nœud LXD.

Son architecture repose sur un **cœur minimal** — gestion unifiée du Compute (containers + VMs), gestion du stockage et des réseaux, et marketplace de plugins — complété par un **écosystème de plugins installables** qui étendent les capacités à la demande : reverse proxy, bases de données, DNS, monitoring, backups, mail, workflows, IA, et plus encore.

WindFlow s'adresse à toute personne qui veut gérer une petite infrastructure (homelab, serveur personnel, petite équipe) sans être administrateur système, tout en gardant un contrôle total sur ses données et ses services.

---

## Vision et Objectifs

### Vision

Rendre la gestion d'infrastructure accessible à tous en proposant un outil self-hosted qui combine :

- la simplicité d'un Cloudron ou YunoHost pour le déploiement applicatif,
- la profondeur de Portainer pour la gestion fine des containers,
- la gestion de VMs d'un Proxmox ou vsphere pour les machines virtuelles,
- le tout dans une interface moderne, unifiée, et extensible par plugins.

### Objectifs principaux

**Compute unifié — containers et VMs côte à côte**
- Une seule vue "Compute" regroupe tous les objets qui s'exécutent : containers individuels, stacks Compose, releases Helm, machines virtuelles KVM ou lxd.
- Les containers et les VMs peuvent coexister dans une même stack WindFlow (environnement mixte)
- On distingue toujours ce que WindFlow gère de ce qu'il observe

**Cœur minimal, extensible à l'infini**
- Le core ne fait que trois choses : Compute (containers + VMs), stockage/réseau, marketplace de plugins
- Tout le reste est un plugin installable et désinstallable depuis l'UI
- On n'impose jamais de complexité inutile : un RPi avec 2 Go de RAM ne charge pas Elasticsearch

**Self-hosted et souverain**
- Tourne sur votre matériel, sur votre réseau, sans dépendance cloud
- Pas de vendor lock-in, pas de service externe obligatoire
- Données sous votre contrôle total

**Léger et universel**
- Fonctionne sur Raspberry Pi 4+ (ARM64) comme sur serveur x86
- Mode léger avec SQLite et sans Redis pour les machines contraintes
- Empreinte mémoire core < 512 Mo en mode léger

**Simple à utiliser**
- Interface web moderne et intuitive
- Installation en 5 minutes
- Déploiement d'un premier service en moins de 10 minutes
- CLI/TUI puissants pour ceux qui préfèrent le terminal

---

## Modèle Compute — le concept central

WindFlow introduit une distinction fondamentale entre trois niveaux de contrôle sur les objets Compute :

### Stacks WindFlow (gérées)

Une **stack WindFlow** est un ensemble d'objets Compute dont WindFlow est l'auteur et le source of truth. Elle peut contenir :

- des containers Docker (définis par un Compose ou déployés individuellement),
- des releases Helm (sur un cluster Kubernetes connecté),
- des machines virtuelles KVM ou LXD,
- ou un **mélange des trois** dans un environnement cohérent.

WindFlow gère le cycle de vie complet : déploiement, mise à jour, restart, suppression, sauvegarde. Les stacks sont éditables directement depuis l'UI ou pilotées depuis un dépôt Git.

### Objets Discovered (observés)

Quand WindFlow scanne un target (machine distante ou locale), il peut détecter des objets qu'il n'a pas créés :

- des containers Docker lancés hors WindFlow,
- des fichiers `docker-compose.yml` ou `compose.yaml` existant dans le docker,
- des releases Helm déjà déployées sur un cluster Kube,
- des VMs libvirt/LXD existantes.

Ces objets sont affichés en **lecture seule** : WindFlow les observe et remonte leurs métriques, mais ne les modifie pas sans action explicite de l'utilisateur. Un bouton "Adopter" permet de les intégrer dans une stack WindFlow, déclenchant un wizard qui reprend la configuration existante.

### Objets Standalone (gérés individuellement)

Des containers ou des VMs créés directement depuis WindFlow, sans appartenir à une stack. WindFlow les gère entièrement mais sans notion d'environnement groupé. Utile pour les services "one-shot" ou les tests rapides.

---

## Proposition de Valeur

### Pour le Self-Hoster

- **Un seul outil** pour gérer containers et VMs au lieu de jongler entre Portainer, virt-manager, et des scripts SSH
- **Vue Compute unifiée** : tous les objets qui s'exécutent sur toutes les machines, en une seule page avec filtres
- **Marketplace de stacks** : installer Nextcloud, Gitea, Jellyfin ou Home Assistant en un clic
- **Plugins à la demande** : ajouter un reverse proxy (Traefik), du monitoring (Uptime Kuma), des backups (Restic) quand on en a besoin, pas avant
- **Tourne sur du matériel modeste** : un Raspberry Pi 4 suffit pour commencer

### Pour la Petite Équipe

- **Gestion multi-machines** : piloter plusieurs serveurs depuis une seule instance WindFlow
- **Environnements séparés** : isoler dev, staging, prod avec des stacks, des réseaux et des permissions distincts
- **Stacks mixtes** : une stack peut embarquer une VM de base et ses services containers associés
- **Auth et RBAC** intégrés au core : chaque membre a les permissions adaptées à son rôle

### Pour l'Administrateur Système

- **VMs et containers côte à côte** : libvirt/LXD/Incus pour les VMs, Docker ou podman pour les containers, Kube avec K8s ou K3s le tout accessible au travers d'un SSH
- **Profondeur Portainer** pour les containers : logs inline, terminal exec, gestion des images/volumes/réseaux, gestion variables d'environnement et Labels, métriques live
- **Console VNC/SPICE** intégrée au navigateur pour les VMs, sans client lourd
- **Volume browser** : naviguer, éditer, uploader des fichiers dans les volumes sans accès SSH
- **Gestion des snapshots VM** : créer, restaurer, supprimer depuis une vue dédiée multi-machines
- **Bibliothèque d'images OS** : templates cloud-init (Ubuntu, Debian, Alpine…) et ISOs stockés localement pour provisionner des VMs rapidement

---

## Cas d'Usage

### Homelab

Un passionné dispose d'un Raspberry Pi ou d'un mini PC et veut héberger ses propres services.

- Installer WindFlow en mode léger sur un RPi 4 (ARM64, 512 Mo de RAM pour le core)
- Depuis la marketplace, déployer Nextcloud (cloud personnel), Immich (photos), Jellyfin (médias)
- Installer le plugin Traefik pour exposer les services avec un nom de domaine et du HTTPS automatique
- Installer le plugin Restic pour sauvegarder les données automatiquement
- Tout gérer depuis l'interface web, sans toucher à la ligne de commande

### Petit Serveur Dédié

Un développeur ou une petite équipe loue un serveur dédié (OVH, Hetzner…) et veut y déployer plusieurs projets.

- WindFlow détecte les containers et compositions déjà présents sur la machine (objets discovered)
- L'utilisateur adopte en un clic les compositions existantes pour les intégrer dans des stacks WindFlow
- Plugin Traefik + Let's Encrypt pour le routage et les certificats
- Plugin Gitea + webhook auto-deploy pour du déploiement automatique depuis Git
- Plugin Uptime Kuma pour surveiller la disponibilité des services

### Infrastructure Mixte Containers + VMs

Un administrateur système gère quelques serveurs avec un mix de VMs et de containers.

- WindFlow sur un serveur principal, connecté à d'autres machines via SSH
- KVM/libvirt ou LXD/incus pour les VMs existantes, détectées automatiquement en tant qu'objets discovered
- Création de nouvelles VMs depuis des templates cloud-init Ubuntu/Debian/Alpine stockés dans la bibliothèque d'images OS. Ces VMs créés peuvent ensuite servir de container pour du docker ou Kube
- Console VNC intégrée ou shell terminal pour accéder aux VMs sans client lourd
- Vue Compute globale : toutes les machines, tous les containers, toutes les VMs, en une seule page
- Stacks mixtes : environnements qui combinent une VM de base (ex. k3s-node) et ses services containers

### Environnement de Développement

Une équipe de développeurs veut des environnements de dev/test rapides à provisionner.

- Templates de stacks pour les environnements types (API + PostgreSQL + Redis, ou VM Ubuntu + DB containers)
- Environnements isolés par projet avec réseaux séparés
- Plugin Git pour synchroniser les stacks depuis un dépôt
- Déploiement en un clic depuis la marketplace
- Nettoyage facile des environnements obsolètes

---

## Architecture de Haut Niveau

### Philosophie : Core + Plugins

```
┌─────────────────────────────────────────────────────────┐
│  Interfaces                                             │
│  Web UI (Vue.js 3)  ·  CLI (Typer)  ·  TUI (Textual)  │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────┐
│  Core WindFlow                                          │
│                                                         │
│  API REST (FastAPI)  ·  Auth JWT + RBAC                │
│  Plugin Manager  ·  Marketplace  ·  Celery Worker      │
│  Target Manager (local + SSH)                          │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Compute Engine                                 │   │
│  │  Containers : Docker, Podman, Helm/k8s/K3s      │   │
│  │  VMs        : KVM/libvirt, LXD/Incus            │   │
│  │  Discovery  : scan et réconciliation auto       │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐                    │
│  │ PostgreSQL   │  │ Redis        │                    │
│  │ ou SQLite    │  │ (optionnel)  │                    │
│  └──────────────┘  └──────────────┘                    │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────┐
│  Plugins (installables à la demande)                   │
│                                                         │
│  Reverse Proxy  ·  DNS  ·  Bases de données            │
│  Monitoring  ·  Backup  ·  Sécurité  ·  Git & CI      │
│  Mail  ·  SSO  ·  Workflows  ·  IA  ·  Messagerie     │
└─────────────────────────────────────────────────────────┘
```

### Ce qui est Core vs Plugin

| Core (toujours présent)                            | Plugin (installable à la demande) |
|----------------------------------------------------|---|
| API REST (FastAPI)                                 | Reverse proxy (Traefik, Caddy, Nginx PM) |
| Auth JWT + RBAC                                    | DNS (Pi-hole, CoreDNS, Cloudflare) |
| Compute Engine : containers (Docker, Podman, Helm) | Certificats TLS (Let's Encrypt) |
| Compute Engine : VMs (KVM/libvirt, LXD, Incus)     | Bases de données (PostgreSQL, MySQL, Redis, MongoDB) |
| Discovery & réconciliation                         | Monitoring (Uptime Kuma, Netdata, Prometheus) |
| Plugin Manager + Marketplace                       | Backup (Restic, Borg) |
| Target Manager (local + SSH)                       | Sécurité (Authelia, Trivy, Vault) |
| Celery worker (tâches async)                       | Git & CI (Gitea, auto-deploy) |
| PostgreSQL ou SQLite                               | Mail (Mailu, Stalwart) |
| Redis (optionnel)                                  | Workflows (n8n, Node-RED) |
| Web UI (Vue.js 3)                                  | IA (Ollama, LiteLLM) |
| CLI/TUI                                            | SSO (Keycloak) |
|                                                    | Messagerie (MQTT, RabbitMQ) |

### Profils de Ressources

| Profil | RAM | CPU | Stockage | Machine type |
|---|---|---|---|---|
| **Léger** (core, SQLite, sans Redis, sans VMs) | 512 Mo | 1 core ARM | 2 Go | Raspberry Pi 4 (2 Go) |
| **Standard** (core, PostgreSQL, Redis, KVM) | 1.5 Go | 2 cores | 5 Go | RPi 4 (4 Go), mini PC |
| **Complet** (core + 5-10 plugins, VMs actives) | 4 Go | 4 cores | 20 Go | NUC, serveur dédié |

---

## Différenciateurs

### Compute Unifié : Containers ET VMs

La plupart des outils self-hosted gèrent soit les containers (Portainer, CasaOS), soit les VMs (Lxd,Incus, virt-manager). WindFlow fait les deux dans la même interface, avec une vue globale cross-machine et cross-technologie. Un Raspberry Pi avec Docker et un serveur LXD avec des VMs KVM se gèrent depuis le même dashboard, sans navigation entre plusieurs outils.

### Profondeur Portainer pour les Containers

WindFlow ne se contente pas de lancer des containers. Pour les objets Docker ou Podman, il offre le même niveau de profondeur que Portainer : gestion des images avec détection des images dangling, Volume Browser pour naviguer dans les fichiers sans SSH, gestion fine des réseaux Docker, métriques CPU/mémoire live par container, terminal exec et logs inline.

### Stacks Mixtes VM + Containers

Concept unique : une stack WindFlow peut regrouper une VM (ex. Ubuntu cloud-init) et des containers Docker dans un seul environnement cohérent. Utile pour les applications legacy qui tournent dans une VM mais dont les dépendances (PostgreSQL, Redis) sont des containers.

### Discovery et Adoption

WindFlow scanne les machines connectées et détecte ce qui existe déjà : containers non gérés, fichiers docker-compose.yml, VMs libvirt, releases Helm. Ces objets sont affichés en lecture seule. L'utilisateur peut les "adopter" pour les intégrer dans une stack WindFlow via un wizard qui préserve la configuration existante.

### Bibliothèque d'Images OS

WindFlow maintient une bibliothèque locale d'images OS pour les VMs : templates cloud-init (Ubuntu, Debian, Alpine, Rocky Linux…) multi-arch (amd64 + arm64), ISOs pour les installations manuelles, et templates cloud-init personnalisés créables depuis l'UI. Le provisionnement d'une nouvelle VM depuis un template prend moins de 2 minutes.

### Core Minimal + Tout Plugin

Contrairement à Portainer, CasaOS ou Coolify qui embarquent leurs fonctionnalités en dur, WindFlow sépare strictement le core du reste. Chaque brique additionnelle est un plugin avec son propre cycle de vie. Résultat : une empreinte mémoire minimale, et chaque utilisateur n'a que ce dont il a besoin.

### Tourne sur Raspberry Pi

WindFlow est pensé ARM-first. Le core et tous les plugins officiels fournissent des images multi-arch (arm64 + amd64). Le mode léger (SQLite, pas de Redis, pas de KVM) permet de tourner avec 512 Mo de RAM.

---

## Métriques de Succès

### Expérience Utilisateur

- **Temps d'installation** : < 5 minutes pour le core
- **Temps pour déployer un premier service** : < 10 minutes (installation incluse)
- **Temps pour provisionner une VM** depuis un template cloud-init : < 2 minutes
- **Taux de succès des déploiements** : > 95 %
- **Empreinte mémoire core (mode léger)** : < 512 Mo

### Écosystème

- **Plugins officiels** : 20+ couvrant les besoins courants du self-hosting
- **Templates marketplace** : 15+ applications one-click
- **Images OS officielles** : Ubuntu LTS, Debian stable, Alpine, Rocky Linux, Home Assistant OS — multi-arch
- **Architectures supportées** : ARM64 + x86_64 pour le core et tous les plugins officiels

### Qualité

- **Couverture tests** : > 85 %
- **Vulnérabilités critiques** : 0
- **Documentation** : guide d'installation, guide plugins, guide VMs, référence API complète

---

## Standards et Compatibilité

### Formats et Protocoles

- **Containers** : Docker Engine API, format Docker Compose v3+, Helm v3, API Kubernetes
- **VMs** : libvirt/QEMU-KVM, API LXD ou Incus, VNC/SPICE pour les consoles
- **Images OS** : qcow2, raw, ISO, cloud-init (user-data + meta-data + network-config)
- **Architectures** : linux/amd64, linux/arm64

### Intégrations (via plugins)

- **Git** : GitHub, GitLab, Bitbucket, Gitea (via plugin Git)
- **DNS** : Cloudflare, Pi-hole, CoreDNS (via plugins DNS)
- **Reverse Proxy** : Traefik, Caddy, Nginx Proxy Manager (via plugins)
- **Monitoring** : Prometheus, Grafana, Uptime Kuma, Netdata (via plugins)
- **Backup** : Restic, Borg (via plugins)
- **Auth externe** : Keycloak, LDAP/AD, OIDC (via plugin SSO)

---

**Références :**
- [Modèle Compute](02-compute-model.md) — détail du modèle containers + VMs + discovery
- [Architecture Générale](03-architecture.md) — principes de conception
- [Stack Technologique](04-technology-stack.md) — technologies utilisées
- [Fonctionnalités Principales](10-core-features.md) — fonctionnalités détaillées
- [Roadmap](18-roadmap.md) — plan de développement
