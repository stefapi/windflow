# Chapitre 01 — Vision

> **Statut** : Spec cible · **Public** : Tous · **Lié à** : [02-familles-workloads.md](02-familles-workloads.md), [03-modele-compute.md](03-modele-compute.md), [04-architecture.md](04-architecture.md), [../Roadmap.md](../Roadmap.md)

## Vue d'ensemble

Ce chapitre définit la vision de WindFlow : ce que le produit est, à qui il s'adresse, la proposition de valeur par profil d'utilisateur, les cas d'usage types, les différenciateurs et les métriques de succès. C'est le seul chapitre au ton volontairement « marketing » ; les chapitres suivants sont factuels. L'architecture (chapitre 04), le modèle directeur Apps/Machines/Hosts (chapitre 02) et le modèle Compute (chapitre 03) sont décrits ailleurs — ce chapitre n'en donne que les intuitions.

## Qu'est-ce que WindFlow ?

WindFlow est un **gestionnaire d'infrastructure self-hosted** pour piloter des Apps (containers Docker, stacks Compose, releases Helm), des Machines (VMs) et leurs Hosts (substrats d'exécution) depuis une interface web unique. Il est conçu pour tourner aussi bien sur un Raspberry Pi 4 que sur un serveur x86 dédié.

Son architecture repose sur un **cœur minimal** — gestion des workloads des trois familles, gestion des stacks, du stockage et des réseaux, et marketplace — complété par un **écosystème de plugins installables** qui étendent les capacités à la demande : reverse proxy, bases de données, DNS, monitoring, backups, mail, workflows, IA, et plus encore. La frontière core/plugins est spécifiée au chapitre [04-architecture.md](04-architecture.md).

WindFlow s'adresse à toute personne qui veut gérer une petite infrastructure (homelab, serveur personnel, petite équipe) sans être administrateur système, tout en gardant un contrôle total sur ses données et ses services.

## Vision et objectifs

### Vision

Rendre la gestion d'infrastructure accessible à tous en proposant un outil self-hosted qui combine :

- la simplicité d'un Cloudron ou YunoHost pour le déploiement applicatif,
- la profondeur de Portainer pour la gestion fine des containers,
- la gestion de VMs d'un Proxmox ou vSphere pour les machines virtuelles,
- le tout dans une interface moderne, unifiée, et extensible par plugins.

### Objectifs principaux

**Trois familles de workloads — Apps, Machines, Hosts**
- Une seule interface regroupe tout ce qui s'exécute, organisé par famille : Apps (container-based), Machines (VM-based), Hosts (substrats).
- Les containers et les VMs peuvent coexister dans une même stack WindFlow (environnement mixte).
- On distingue toujours ce que WindFlow gère de ce qu'il observe (discovery/adoption, chapitre 03).

**Cœur minimal, extensible à l'infini**
- Le core gère les workloads, les stacks, le stockage/réseau et la marketplace de plugins.
- Tout le reste est un plugin installable et désinstallable depuis l'UI.
- On n'impose jamais de complexité inutile : un RPi avec 2 Go de RAM ne charge pas Elasticsearch.

**Self-hosted et souverain**
- Tourne sur votre matériel, sur votre réseau, sans dépendance cloud.
- Pas de vendor lock-in, pas de service externe obligatoire.
- Données sous votre contrôle total.

**Léger et universel**
- Fonctionne sur Raspberry Pi 4+ (ARM64) comme sur serveur x86.
- Mode léger avec SQLite et sans Redis pour les machines contraintes.
- Empreinte mémoire core < 512 Mo en mode léger.

**Simple à utiliser**
- Interface web moderne et intuitive.
- Installation en 5 minutes.
- Déploiement d'un premier service en moins de 10 minutes.
- CLI/TUI puissants pour ceux qui préfèrent le terminal.

Le concept central de **niveaux de contrôle** sur les objets Compute (stacks gérées, objets discovered observés, objets standalone) est détaillé au chapitre [03-modele-compute.md](03-modele-compute.md) ; le modèle à trois familles au chapitre [02-familles-workloads.md](02-familles-workloads.md).

## Proposition de valeur

### Pour le self-hoster

- **Un seul outil** pour gérer Apps et Machines au lieu de jongler entre Portainer, virt-manager et des scripts SSH.
- **Vue par famille, filtres croisés** : toutes les Apps, toutes les Machines, tous les Hosts, en une page avec filtres « Sur quel Host ? ».
- **Marketplace** : installer Nextcloud, Gitea, Jellyfin ou Home Assistant en un clic.
- **Plugins à la demande** : ajouter un reverse proxy (Traefik), du monitoring (Uptime Kuma), des backups (Restic) quand on en a besoin, pas avant.
- **Tourne sur du matériel modeste** : un Raspberry Pi 4 suffit pour commencer.

### Pour la petite équipe

- **Gestion multi-Hosts** : piloter plusieurs serveurs depuis une seule instance WindFlow.
- **Environnements séparés** : isoler dev, staging, prod avec des stacks, des réseaux et des permissions distincts.
- **Stacks mixtes** : une stack peut embarquer une Machine de base et ses services containers associés.
- **Auth et RBAC** intégrés au core : chaque membre a les permissions adaptées à son rôle.

### Pour l'administrateur système

- **Machines et Apps côte à côte** : KVM/libvirt, LXD, Incus, VirtualBox pour les Machines ; Docker, Podman ou Kubernetes pour les Apps — le tout accessible au travers d'un SSH ou d'APIs natives.
- **Proxmox comme Host** : un serveur ou cluster Proxmox VE s'ajoute comme Host (`host_proxmox`) ; ses VMs deviennent des Machines standard.
- **Profondeur Portainer** pour les containers : logs inline, terminal exec, gestion des images/volumes/réseaux, variables d'environnement et labels, métriques live.
- **Console VNC/SPICE** intégrée au navigateur pour les Machines, sans client lourd.
- **Volume browser** : naviguer, éditer, uploader des fichiers dans les volumes sans accès SSH.
- **Gestion des snapshots** : créer, restaurer, supprimer depuis une vue dédiée multi-Machines.
- **Bibliothèque d'images OS** : templates cloud-init (Ubuntu, Debian, Alpine…) et ISOs stockés localement pour provisionner des Machines rapidement.

## Cas d'usage

### Homelab

Un passionné dispose d'un Raspberry Pi ou d'un mini PC et veut héberger ses propres services.

- Installer WindFlow en mode léger sur un RPi 4 (ARM64, 512 Mo de RAM pour le core).
- Depuis la marketplace, déployer Nextcloud (cloud personnel), Immich (photos), Jellyfin (médias).
- Installer le plugin Traefik pour exposer les services avec un nom de domaine et du HTTPS automatique.
- Installer le plugin Restic pour sauvegarder les données automatiquement.
- Tout gérer depuis l'interface web, sans toucher à la ligne de commande.

### Petit serveur dédié

Un développeur ou une petite équipe loue un serveur dédié (OVH, Hetzner…) et veut y déployer plusieurs projets.

- WindFlow détecte les containers et compositions déjà présents sur la machine (objets discovered).
- L'utilisateur adopte en un clic les compositions existantes pour les intégrer dans des stacks WindFlow.
- Plugin Traefik + Let's Encrypt pour le routage et les certificats.
- Plugin Gitea + webhook auto-deploy pour du déploiement automatique depuis Git.
- Plugin Uptime Kuma pour surveiller la disponibilité des services.

### Infrastructure mixte containers + VMs

Un administrateur système gère quelques serveurs avec un mix de VMs et de containers.

- WindFlow sur un serveur principal, connecté à d'autres Hosts (SSH, Proxmox, k3s).
- KVM/libvirt ou LXD/Incus pour les Machines existantes, détectées automatiquement comme objets discovered.
- Création de nouvelles Machines depuis des templates cloud-init Ubuntu/Debian/Alpine stockés dans la bibliothèque d'images OS. Ces Machines peuvent ensuite servir de substrat pour des Apps Docker ou Kubernetes.
- Console VNC intégrée ou terminal série pour accéder aux Machines sans client lourd.
- Vue Compute globale : toutes les machines, tous les containers, toutes les VMs, en une seule page.
- Stacks mixtes : environnements qui combinent une Machine de base (ex. k3s-node) et ses services containers.

### Environnement de développement

Une équipe de développeurs veut des environnements de dev/test rapides à provisionner.

- Templates de stacks pour les environnements types (API + PostgreSQL + Redis, ou Machine Ubuntu + DB containers).
- Environnements isolés par projet avec réseaux séparés.
- Plugin Git pour synchroniser les stacks depuis un dépôt.
- Déploiement en un clic depuis la marketplace.
- Nettoyage facile des environnements obsolètes.

## Différenciateurs

### Trois familles, une grammaire : Apps ET Machines ET Hosts

La plupart des outils self-hosted gèrent soit les containers (Portainer, CasaOS), soit les VMs (Incus, virt-manager). WindFlow fait les deux dans la même interface, avec un modèle explicite à trois familles et une grammaire UI partagée (chapitre 02). Un Raspberry Pi avec Docker et un serveur Proxmox avec des VMs KVM se gèrent depuis le même dashboard, sans navigation entre plusieurs outils.

### Profondeur Portainer pour les containers

WindFlow ne se contente pas de lancer des containers. Pour les objets Docker ou Podman, il offre le même niveau de profondeur que Portainer : gestion des images avec détection des images dangling, volume browser pour naviguer dans les fichiers sans SSH, gestion fine des réseaux Docker, métriques CPU/mémoire live par container, terminal exec et logs inline.

### Stacks mixtes VM + containers

Concept unique : une stack WindFlow peut regrouper une Machine (ex. Ubuntu cloud-init) et des containers Docker dans un seul environnement cohérent. Utile pour les applications legacy qui tournent dans une VM mais dont les dépendances (PostgreSQL, Redis) sont des containers.

### Discovery et adoption

WindFlow scanne les Hosts connectés et détecte ce qui existe déjà : containers non gérés, fichiers docker-compose.yml, VMs libvirt, releases Helm. Ces objets sont affichés en lecture seule. L'utilisateur peut les « adopter » pour les intégrer dans une stack WindFlow via un wizard qui préserve la configuration existante (chapitre 03).

### Bibliothèque d'images OS

WindFlow maintient une bibliothèque locale d'images OS pour les Machines : templates cloud-init (Ubuntu, Debian, Alpine, Rocky Linux…) multi-arch (amd64 + arm64), ISOs pour les installations manuelles, et templates cloud-init personnalisés créables depuis l'UI. Le provisionnement d'une nouvelle Machine depuis un template prend moins de 2 minutes.

### Core minimal + tout plugin

Contrairement à Portainer, CasaOS ou Coolify qui embarquent leurs fonctionnalités en dur, WindFlow sépare strictement le core du reste. Chaque brique additionnelle est un plugin avec son propre cycle de vie. Résultat : une empreinte mémoire minimale, et chaque utilisateur n'a que ce dont il a besoin.

### Tourne sur Raspberry Pi

WindFlow est pensé ARM-first. Le core et tous les plugins officiels fournissent des images multi-arch (arm64 + amd64). Le mode léger (SQLite, pas de Redis, pas de KVM) permet de tourner avec 512 Mo de RAM.

## Métriques de succès

### Expérience utilisateur

- **Temps d'installation** : < 5 minutes pour le core.
- **Temps pour déployer un premier service** : < 10 minutes (installation incluse).
- **Temps pour provisionner une Machine** depuis un template cloud-init : < 2 minutes.
- **Taux de succès des déploiements** : > 95 %.
- **Empreinte mémoire core (mode léger)** : < 512 Mo.

### Écosystème

- **Plugins officiels** : 20+ couvrant les besoins courants du self-hosting (compte canonique ; le catalogue est au chapitre [12-marketplace.md](12-marketplace.md)).
- **Entrées marketplace** : 15+ applications one-click.
- **Images OS officielles** : Ubuntu LTS, Debian stable, Alpine, Rocky Linux, Home Assistant OS — multi-arch.
- **Architectures supportées** : ARM64 + x86_64 pour le core et tous les plugins officiels.

### Qualité

- **Couverture tests** : > 85 %.
- **Vulnérabilités critiques** : 0.
- **Documentation** : guide d'installation, guide plugins, guide Machines, référence API complète.

## Standards et compatibilité

### Formats et protocoles

- **Apps** : Docker Engine API, format Docker Compose v3+, Helm v3, API Kubernetes.
- **Machines** : libvirt/QEMU-KVM, API LXD ou Incus, VNC/SPICE pour les consoles. VirtualBox est supporté pour les environnements de test. Proxmox VE est consommé comme profil de Host (`host_proxmox`) via son API.
- **Images OS** : qcow2, raw, ISO, cloud-init (user-data + meta-data + network-config).
- **Architectures** : linux/amd64, linux/arm64.

### Intégrations via plugins

- **Git** : GitHub, GitLab, Bitbucket, Gitea (plugin Git).
- **DNS** : Cloudflare, Pi-hole, CoreDNS (plugins DNS).
- **Reverse proxy** : Traefik, Caddy, Nginx Proxy Manager (plugins).
- **Monitoring** : Prometheus, Grafana, Uptime Kuma, Netdata (plugins).
- **Backup** : Restic, Borg (plugins).
- **Auth externe** : Keycloak, LDAP/AD, OIDC (plugin SSO).

## Voir aussi

- [02-familles-workloads.md](02-familles-workloads.md) — modèle directeur Apps/Machines/Hosts et grammaire UI
- [03-modele-compute.md](03-modele-compute.md) — taxonomie stack/discovered/standalone et vue Compute
- [04-architecture.md](04-architecture.md) — architecture, frontière core/plugins et profils de déploiement
- [12-marketplace.md](12-marketplace.md) — marketplace et catalogue des plugins officiels
- [../Roadmap.md](../Roadmap.md) — feuille de route produit et phases d'implémentation
