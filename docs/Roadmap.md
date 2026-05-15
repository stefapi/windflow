# Roadmap de Développement - WindFlow

## Vision Produit

WindFlow est un **gestionnaire d'infrastructure self-hosted léger** pour piloter conteneurs et machines virtuelles depuis une interface unique. Il tourne aussi bien sur un Raspberry Pi que sur un serveur x86 dédié.

Le principe fondamental : un **cœur minimal** qui gère le compute (containers, VMs) et une **marketplace de plugins** qui étend les capacités à la demande — DNS, reverse proxy, bases de données, mail, messagerie, monitoring, etc.

### Philosophie

**Cœur minimal :** WindFlow de base ne fait que trois choses — gérer des containers, gérer des VMs, et proposer une marketplace pour installer des stacks et des plugins. Tout le reste est un plugin.

**Tout est plugin :** Le reverse proxy, le DNS, la gestion mail, les bases de données, le monitoring, les workflows — chaque brique est un plugin installable et désinstallable depuis l'UI. Un Raspberry Pi avec 2 Go de RAM n'a pas besoin d'Elasticsearch. Un homelab n'a pas besoin d'un workflow engine. On installe uniquement ce dont on a besoin.

**ARM-first, x86 aussi :** Toutes les images Docker utilisées doivent être multi-arch (arm64 + amd64). Le core est testé sur Raspberry Pi 4/5 et équivalents. Les plugins déclarent leurs exigences minimales (RAM, CPU) et l'UI prévient si la machine n'a pas assez de ressources.

**Self-hosting accessible :** L'utilisateur type est quelqu'un qui a un Raspberry Pi ou un petit serveur chez lui ou dans un datacenter, et qui veut gérer ses services sans être sysadmin. WindFlow doit rester simple, documenté, et ne jamais imposer de complexité inutile.

### Objectifs Stratégiques

**2026 : Fondation solide**
- Core stable : containers Docker + VMs (KVM/LXC/LXD)
- Système de plugins mature avec marketplace
- 20+ plugins disponibles couvrant les cas d'usage courants
- Fonctionne sur Raspberry Pi 4+ avec 2 Go de RAM (core seul)

**2027 : Écosystème et communauté**
- SDK plugins pour contributions communautaires
- Plugins IA optionnels (diagnostic, génération de configs)
- Multi-node basique (piloter plusieurs machines depuis une instance)
- 50+ plugins, templates communautaires

**2028+ : Maturité**
- Fédération multi-instances
- Mobile app
- Plugin marketplace communautaire avec review et rating

---

## Architecture Core vs Plugins

### Ce qui fait partie du Core

| Composant | Description                                                                   |
|-----------|-------------------------------------------------------------------------------|
| **API REST** | FastAPI, endpoints pour containers, VMs, plugins, marketplace                 |
| **Base de données** | PostgreSQL (ou SQLite en mode léger pour RPi)                                 |
| **Cache** | Redis (ou en-mémoire en mode léger)                                           |
| **Auth** | JWT, organisations, RBAC                                                      |
| **Web UI** | Vue.js 3, dashboard, gestion containers/VMs                                   |
| **CLI/TUI** | Rich + Typer + Textual                                                        |
| **Container engine** | Docker / Podman / K8s : containers, compose stacks, images, volumes, networks |
| **VM engine** | Libvirt (KVM/QEMU), LXC, LXD, Incus                                           |
| **Plugin manager** | Installation, mise à jour, configuration, dépendances entre plugins           |
| **Marketplace** | Catalogue de stacks et plugins, installation one-click                        |
| **Target manager** | Discovery et gestion des machines cibles (local, SSH)                         |

### Ce qui est un Plugin (exemples)

| Catégorie | Plugins |
|-----------|---------|
| **Accès & Routage** | Traefik, Caddy, Nginx Proxy Manager, Cloudflare Tunnel |
| **DNS** | CoreDNS, Pi-hole, Cloudflare DNS, OVH DNS |
| **Certificats** | Let's Encrypt (ACME), cert-manager |
| **Bases de données** | PostgreSQL, MySQL/MariaDB, MongoDB, Redis, SQLite tools |
| **Messagerie** | MQTT (Mosquitto), RabbitMQ, NATS |
| **Mail** | Mail-in-a-Box, Mailu, Stalwart |
| **Monitoring** | Prometheus + Grafana, Uptime Kuma, Netdata |
| **Stockage** | MinIO (S3), NFS manager, Samba |
| **Sécurité** | Vault (secrets), Trivy (scanning), Authelia, Vaultwarden |
| **Backup** | Restic, Borg, Duplicati |
| **Git** | Gitea, auto-deploy webhooks |
| **Workflows** | n8n, Node-RED |
| **IA** | Ollama, LiteLLM |
| **Sites web** | WordPress, Ghost, Hugo, Strapi |
| **Collaboration** | Nextcloud, Mattermost, Immich |
| **Analytics** | Matomo, Plausible, Grafana |

Un plugin peut être :
- **Un service déployable** (stack Docker avec configuration guidée) — ex : installer Gitea
- **Une extension fonctionnelle** (ajoute des capacités au core) — ex : plugin PostgreSQL qui permet de créer des databases depuis l'UI de WindFlow
- **Les deux** — ex : plugin Traefik qui déploie Traefik ET s'intègre au core pour le routage automatique

---

## Phases de Développement

### Phase 1 : Core Platform (Q1 2026) ✅ COMPLÉTÉ

**Version :** 1.0  
**Durée :** 3 mois (Janvier - Mars 2026)

#### Ce qui a été livré

**Backend & API :**
- API REST FastAPI avec documentation OpenAPI
- PostgreSQL + SQLAlchemy 2.0 async + Redis
- Auth JWT avec refresh tokens
- Organisations, environnements, RBAC
- Celery pour tâches asynchrones

**Interface :**
- Web UI Vue.js 3 + TypeScript + Element Plus
- Dashboard, éditeur YAML, logs temps réel
- Terminal WebSocket dans containers
- CLI/TUI (Rich + Typer + Textual)

**Docker :**
- Containers et stacks Docker Compose
- Pipeline de déploiement avec retry
- Targets CRUD avec discovery
- Stacks avec versioning et templates Jinja2

#### Métriques
- Couverture tests : ~70%
- API endpoints : 50+
- Templates stacks : 5

---

### Phase 2 : Plugin System & VM Foundation (Q2 2026)

**Version :** 1.1  
**Durée :** 3 mois (Avril - Juin 2026)  
**Statut :** Planifié — Priorité haute

> **Objectif :** Construire le système de plugins qui est le cœur de l'extensibilité de WindFlow, ajouter la gestion des VMs, et livrer les premiers plugins essentiels. À la fin de cette phase, un utilisateur peut installer WindFlow sur un Raspberry Pi, déployer des containers, installer un reverse proxy via plugin, et exposer ses services avec un domaine et du TLS — le tout depuis l'UI.

#### Système de Plugins (priorité #1)

C'est la fondation de tout ce qui suit. Sans un système de plugins solide, WindFlow reste un Portainer-like.

**Plugin Manager :**
- [ ] Format de déclaration plugin (manifest YAML : nom, version, type, dépendances, ressources minimum, architectures supportées)
- [ ] Installation / mise à jour / désinstallation depuis l'UI et la CLI
- [ ] Gestion des dépendances entre plugins (ex : Let's Encrypt nécessite Traefik ou Caddy)
- [ ] Vérification compatibilité architecture (arm64/amd64) et ressources disponibles
- [ ] Configuration plugin depuis l'UI (formulaires générés depuis le manifest)
- [ ] Hooks lifecycle : on_install, on_configure, on_start, on_stop, on_uninstall

**Types de plugins :**
- [ ] **Service plugin** : déploie une stack Docker avec wizard de configuration
- [ ] **Extension plugin** : ajoute des endpoints API et des pages UI au core
- [ ] **Hybrid plugin** : les deux (déploie un service ET étend le core)

**Marketplace :**
- [ ] Catalogue browsable depuis l'UI (catégories, recherche, filtres)
- [ ] Fiches plugin : description, screenshots, ressources requises, compatibilité arch
- [ ] Installation one-click
- [ ] Mise à jour des plugins avec changelog
- [ ] Distinction plugins officiels / communautaires

**Registre :**
- [ ] Registre de plugins hébergé (index JSON ou API simple)
- [ ] Support registre custom (self-hosted)
- [ ] Vérification d'intégrité (checksums)

#### Mode Léger (Raspberry Pi)

- [ ] Option SQLite au lieu de PostgreSQL pour le core
- [ ] Option cache en-mémoire au lieu de Redis
- [ ] Profil d'installation "léger" (install.sh --light)
- [ ] Empreinte mémoire core < 512 Mo RAM
- [ ] Build multi-arch (arm64 + amd64) de toutes les images core
- [ ] Tests CI sur architecture ARM (QEMU ou runner ARM)

#### Gestion VMs (core)

**KVM/QEMU (via libvirt) :**
- [ ] Détection automatique si libvirt est disponible
- [ ] CRUD machines virtuelles
- [ ] Console VNC/SPICE intégrée à l'UI
- [ ] Snapshots et clones
- [ ] Gestion disques (qcow2, raw)
- [ ] Gestion images ISO et cloud-init

** LXC / LXD / Incus :**
- [ ] Connexion API
- [ ] CRUD VMs et conteneurs LXC
- [ ] Snapshots, backup/restore
- [ ] Vue nodes et ressources

#### Stockage (core)

**Docker Volumes :**
- [ ] API CRUD volumes
- [ ] Cleanup automatique volumes orphelins

**Volume Browser :**
- [ ] Navigation arborescente dans les volumes
- [ ] Upload/Download fichiers
- [ ] Preview fichiers (texte, images, logs)
- [ ] Éditeur de fichiers basique

**VM Disks :**
- [ ] Gestion disques qcow2, raw
- [ ] Conversion entre formats
- [ ] Snapshots disques

#### Réseau Docker (core)

- [ ] API CRUD networks Docker
- [ ] Network drivers (bridge, overlay, macvlan)
- [ ] Isolation réseau par environnement

#### Premiers Plugins

**Plugin Traefik (accès & routage) :**
- [ ] Déploie Traefik comme reverse proxy
- [ ] Association domaine ↔ service depuis l'UI WindFlow
- [ ] Routage automatique via labels Docker
- [ ] Let's Encrypt intégré (HTTP challenge + DNS challenge)
- [ ] Dashboard Traefik accessible

**Plugin PostgreSQL (extension) :**
- [ ] Détection auto des containers PostgreSQL
- [ ] Créer databases, users, grants depuis l'UI
- [ ] Backup/restore
- [ ] Métriques basiques

**Plugin Redis (extension) :**
- [ ] Détection auto des containers Redis
- [ ] Monitoring clés, flush, stats

**Plugin Uptime Kuma (monitoring) :**
- [ ] Déploie Uptime Kuma
- [ ] Widget status sur le dashboard WindFlow

#### Critères de succès
- Le plugin system est fonctionnel : on peut installer, configurer et désinstaller des plugins depuis l'UI
- WindFlow core tourne sur Raspberry Pi 4 (4 Go) en mode léger
- Un utilisateur peut installer le plugin Traefik et exposer un service avec domaine + TLS automatique
- Au moins 4 plugins fonctionnels
- Build multi-arch fonctionnel

---

### Phase 3 : Plugins Essentiels & Multi-Target (Q3 2026)

**Version :** 1.2  
**Durée :** 3 mois (Juillet - Septembre 2026)  
**Statut :** Planifié — Priorité haute

> **Objectif :** Étoffer le catalogue de plugins pour couvrir les besoins classiques du self-hosting (DNS, backup, mail, monitoring avancé), et ajouter le support multi-machine pour piloter plusieurs serveurs depuis une seule instance WindFlow.

#### Multi-Target (core)

**Serveurs distants :**
- [ ] Ajout de machines cibles via SSH
- [ ] Déploiement de containers sur machines distantes
- [ ] Gestion VMs sur hyperviseurs distants (libvirt, LXC, LXD, Incus)
- [ ] Vue consolidée de toutes les machines et services
- [ ] Monitoring basique par machine (CPU, RAM, disque, réseau)

**Agent léger (optionnel) :**
- [ ] Binaire statique ARM/x86 pour collecte de métriques
- [ ] Communication sécurisée avec l'instance WindFlow
- [ ] Auto-discovery des services locaux

#### Kubernetes (core, optionnel)

- [ ] Connexion clusters Kubernetes (kubeconfig)
- [ ] Déploiement manifests YAML et Helm charts
- [ ] Gestion releases Helm
- [ ] Dashboard cluster : pods, deployments, services, logs
- [ ] Terminal dans pods

#### Nouveaux Plugins

**DNS :**
- [ ] **Plugin Pi-hole** : déploiement + gestion DNS/adblock depuis WindFlow
- [ ] **Plugin CoreDNS** : zones DNS locales
- [ ] **Plugin Cloudflare DNS** : gestion DNS via API Cloudflare

**Backup :**
- [ ] **Plugin Restic** : backup automatique volumes et configs, scheduling, restore
- [ ] **Plugin Borg** : alternative Restic

**Monitoring :**
- [ ] **Plugin Prometheus + Grafana** : stack monitoring complète, dashboards préconfigurés
- [ ] **Plugin Netdata** : monitoring léger (bon pour RPi)

**Bases de données :**
- [ ] **Plugin MySQL/MariaDB** : create DB, users, grants, backup/restore
- [ ] **Plugin MongoDB** : create DB, collections, users

**Messagerie :**
- [ ] **Plugin MQTT (Mosquitto)** : topics, ACLs, monitoring
- [ ] **Plugin RabbitMQ** : queues, exchanges, users

**Stockage :**
- [ ] **Plugin MinIO** : stockage S3-compatible, buckets, policies
- [ ] **Plugin Samba/NFS** : partages réseau

**Sécurité :**
- [ ] **Plugin Authelia** : authentification 2FA devant les services
- [ ] **Plugin Vaultwarden** : gestionnaire de mots de passe

#### Templates Marketplace

Stacks préconfigurées installables en un clic :
- [ ] Nextcloud, Immich, Photoprism (cloud perso / photos)
- [ ] Gitea, Forgejo (Git self-hosted)
- [ ] Mattermost, Matrix/Element (communication)
- [ ] Home Assistant (domotique)
- [ ] Jellyfin, Plex (média)
- [ ] Baserow, NocoDB (bases de données no-code)
- [ ] Ghost, WordPress (sites web / blogs)
- [ ] Plausible, Matomo (analytics)

#### Critères de succès
- Multi-target fonctionnel : piloter 2+ machines depuis une instance
- 15+ plugins disponibles dans la marketplace
- 10+ templates de stacks one-click
- Kubernetes basique fonctionnel
- Backup automatisé via plugin Restic

---

### Phase 4 : Sécurité, Git & Polish (Q4 2026)

**Version :** 1.3  
**Durée :** 3 mois (Octobre - Décembre 2026)  
**Statut :** Planifié — Priorité moyenne

> **Objectif :** Solidifier la plateforme — sécurité, traçabilité, intégration Git, et amélioration globale de l'expérience utilisateur. WindFlow doit inspirer confiance pour gérer une petite infrastructure en production.

#### Sécurité (core + plugins)

**Core — Secrets :**
- [ ] Chiffrement des secrets stockés (AES-256-GCM)
- [ ] Rotation de secrets
- [ ] Variables d'environnement sécurisées par stack

**Plugin Trivy (vulnerability scanning) :**
- [ ] Scan d'images Docker avant déploiement
- [ ] Dashboard vulnérabilités
- [ ] Alertes severity high/critical
- [ ] Scan planifié des images existantes

**Plugin Vault (secrets avancés) :**
- [ ] HashiCorp Vault déployé et intégré
- [ ] Secrets dynamiques pour bases de données

**Core — Audit :**
- [ ] Audit trail : qui a fait quoi, quand
- [ ] Logs immuables
- [ ] Export des logs

#### Git Integration (core)

- [ ] Stacks depuis un dépôt Git (git_url, branch, path)
- [ ] Sync automatique (pull périodique)
- [ ] Webhook auto-deploy on push (GitHub, GitLab, Gitea)
- [ ] Rollback vers un commit précédent
- [ ] Auth SSH keys et tokens

#### SSO (plugin)

- [ ] **Plugin Keycloak** : déploiement + intégration auth WindFlow
- [ ] LDAP/Active Directory
- [ ] OIDC providers

#### UX & Polish

- [ ] Wizard première installation (guide pas à pas)
- [ ] Onboarding : suggestions de plugins selon le cas d'usage
- [ ] Notifications système (email, webhook, push)
- [ ] Amélioration responsive mobile du dashboard
- [ ] Documentation intégrée à l'UI (tooltips, aide contextuelle)
- [ ] Internationalisation (français, anglais minimum)

#### Plugin Mail

- [ ] **Plugin Mailu** : serveur mail complet (SMTP, IMAP, webmail)
- [ ] **Plugin Stalwart** : alternative Mailu plus légère
- [ ] Gestion domaines mail, boîtes, alias depuis l'UI WindFlow

#### Critères de succès
- Secrets chiffrés en base
- Scanning vulnérabilités fonctionnel
- Auto-deploy depuis Git opérationnel
- Audit trail complet
- 20+ plugins dans la marketplace

---

### Phase 5 : Automatisation & Intelligence (H1 2027)

**Version :** 2.0  
**Durée :** 6 mois (Janvier - Juin 2027)  
**Statut :** Planifié — Priorité moyenne

> **Objectif :** Ajouter de l'intelligence et de l'automatisation — toujours sous forme de plugins optionnels. Un Raspberry Pi n'a pas besoin d'un LLM, mais un homelab plus costaud peut en profiter.

#### Plugin Workflow Engine

- [ ] **Plugin n8n** ou **Node-RED** : déploiement + intégration events WindFlow
- [ ] Triggers depuis WindFlow : deploy, alert, scale, backup terminé…
- [ ] Workflows préconfigurés : backup → notify, alert → restart, push → deploy

#### Plugin IA (LiteLLM / Ollama)

- [ ] **Plugin Ollama** : LLM local (pour machines avec assez de RAM)
- [ ] **Plugin LiteLLM** : proxy multi-provider (OpenAI, Claude, Ollama)
- [ ] Génération de docker-compose depuis description en langage naturel
- [ ] Diagnostic automatique : analyse logs → suggestion de fix
- [ ] Chat assistant intégré à l'UI
- [ ] Suggestions d'optimisation ressources

#### Auto-Updates (core)

- [ ] Vérification mises à jour pour les stacks déployées
- [ ] Politiques : auto, notification seule, manual
- [ ] Rollback automatique si health check échoue
- [ ] Changelog intégré

#### Plugin SDK & Communauté

- [ ] SDK documenté pour créer des plugins
- [ ] Template de plugin (scaffolding)
- [ ] Guide contributeur plugins
- [ ] Soumission de plugins communautaires au registre
- [ ] Système de review et rating

#### Critères de succès
- Workflow engine fonctionnel via plugin
- IA capable de générer des configs valides (sur machine compatible)
- SDK plugins documenté avec au moins 2 plugins communautaires
- Auto-updates avec rollback

---

### Phase 6 : Long Terme (2027+)

**Statut :** Vision

#### Fédération Multi-Instances

- [ ] Piloter plusieurs instances WindFlow depuis un dashboard central
- [ ] Sync de configurations entre instances
- [ ] Vue globale multi-sites

#### Mobile

- [ ] App mobile (React Native) pour monitoring et actions rapides
- [ ] Notifications push
- [ ] Actions : restart, logs, status

#### PaaS Léger (plugin)

- [ ] Build depuis source (Buildpacks / Dockerfile auto-detect)
- [ ] Deploy depuis git push (Heroku-like)
- [ ] Review apps (environnement par branche)

#### Analytics (plugin)

- [ ] Capacity planning basique
- [ ] Alertes proactives (disque bientôt plein, certificat expirant…)
- [ ] Historique de consommation ressources

---

## Priorités Court Terme

| # | Fonctionnalité | Phase | Impact |
|---|----------------|-------|--------|
| 1 | Plugin System (manager + marketplace) | 2 | Fondation de tout le reste |
| 2 | Mode léger RPi (SQLite, empreinte réduite) | 2 | Élargit la base d'utilisateurs |
| 3 | Gestion VMs (KVM/Proxmox) | 2 | Core promise du produit |
| 4 | Plugin Traefik (reverse proxy + TLS) | 2 | Indispensable pour exposer des services |
| 5 | Volume Browser | 2 | UX essentielle |
| 6 | Premiers plugins DB (PostgreSQL, Redis) | 2 | Valide le plugin system |
| 7 | Multi-target (SSH) | 3 | Gestion multi-machines |
| 8 | Templates marketplace (Nextcloud, Gitea…) | 3 | Adoption self-hosters |
| 9 | Plugins backup (Restic) | 3 | Confiance en production |
| 10 | Git integration + auto-deploy | 4 | Workflow développeur |

---

## Exigences Techniques Transversales

### Compatibilité ARM / x86

- Toutes les images Docker du core : multi-arch (linux/arm64 + linux/amd64)
- Chaque plugin déclare ses architectures supportées dans son manifest
- CI/CD : build et test sur les deux architectures
- Documentation des limitations ARM le cas échéant (ex : certains plugins peuvent ne pas avoir d'image ARM)

### Empreinte Ressources

| Profil | RAM minimum | CPU | Stockage | Exemple machine |
|--------|-------------|-----|----------|-----------------|
| **Léger** (core seul, SQLite) | 512 Mo | 1 core ARM | 2 Go | Raspberry Pi 4 (2 Go) |
| **Standard** (core + PostgreSQL + Redis) | 1.5 Go | 2 cores | 5 Go | Raspberry Pi 4 (4 Go), mini PC |
| **Complet** (core + 5-10 plugins) | 4 Go | 4 cores | 20 Go | NUC, serveur dédié |

### Format Plugin Manifest (draft)

```yaml
name: traefik
version: 1.0.0
type: hybrid  # service | extension | hybrid
display_name: "Traefik - Reverse Proxy"
description: "Reverse proxy avec TLS automatique via Let's Encrypt"
category: access
icon: traefik.svg

architectures:
  - linux/amd64
  - linux/arm64

resources:
  ram_min_mb: 128
  cpu_min_cores: 0.5

dependencies:
  - docker  # nécessite Docker (pas compatible VM-only)

provides:
  - reverse_proxy  # capability fournie
  - tls_certificates

ports:
  - 80
  - 443

config:
  - key: acme_email
    label: "Email pour Let's Encrypt"
    type: string
    required: true
  - key: dashboard_enabled
    label: "Activer le dashboard Traefik"
    type: boolean
    default: true
```

---

## Métriques de Succès

### KPIs

**Adoption :**
- Installations actives (par profil : léger / standard / complet)
- Plugins installés par instance (moyenne)
- Templates marketplace utilisés
- Architectures : ratio ARM vs x86

**Expérience :**
- Temps d'installation (cible < 5 min pour le core)
- Temps pour déployer un premier service (cible < 10 min)
- Taux de succès des déploiements (> 95%)

**Qualité :**
- Couverture tests (> 85%)
- Vulnérabilités critiques (0)
- Empreinte mémoire core en mode léger (< 512 Mo)

### Objectifs

| Métrique | Q2 2026 | Q4 2026 | Q2 2027 |
|----------|---------|---------|---------|
| Installations actives | 50 | 300 | 1,500 |
| Plugins disponibles | 6 | 20 | 40+ |
| Templates marketplace | 5 | 15 | 30+ |
| Plugins communautaires | 0 | 0 | 5+ |
| Couverture tests | 80% | 85% | 85% |

---

## Risques et Mitigation

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Plugin system trop complexe à développer | Élevé | MVP simple (manifest YAML + stack Docker), itérer |
| Images Docker sans support ARM | Moyen | Lister les images multi-arch, builder si nécessaire, documenter |
| Performance sur Raspberry Pi | Moyen | Mode léger (SQLite, pas de Redis), profiling continu |
| Trop de plugins à maintenir | Moyen | SDK + communauté, plugins officiels limités aux essentiels |
| Concurrence (Portainer, Coolify, CasaOS, Cosmos) | Moyen | Différenciation : VMs + containers + plugins, pas juste Docker |
| Scope creep | Élevé | Règle stricte : si c'est pas core (containers, VMs, marketplace), c'est un plugin |

---

**Références :**
- [Vue d'Ensemble](01-overview.md) — Vision et objectifs
- [Architecture](02-architecture.md) — Architecture technique
- [Architecture Modulaire](09-plugins.md) — Système d'extensions
- [Fonctionnalités Principales](10-core-features.md) — Fonctionnalités core
- [Stack Technologique](03-technology-stack.md) — Technologies
- [Guide de Déploiement](15-deployment-guide.md) — Installation
- [Intégration LLM](17-llm-integration.md) — Intelligence artificielle
