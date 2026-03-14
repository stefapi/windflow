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
- Core stable : containers Docker + VMs (KVM/Proxmox)
- Système de plugins mature avec marketplace
- 20+ plugins disponibles couvrant les cas d'usage courants
- Fonctionne sur Raspberry Pi 4+ avec 2 Go de RAM (core seul)
- Interface web moderne avec deux modes (Standard / Avancé)

**2027 : Écosystème et communauté**
- SDK plugins pour contributions communautaires
- Plugins IA optionnels (diagnostic, génération de configs)
- Multi-node basique (piloter plusieurs machines depuis une instance)
- 50+ plugins, templates communautaires
- Interface mobile-first avec PWA

**2028+ : Maturité**
- Fédération multi-instances
- Mobile app native
- Plugin marketplace communautaire avec review et rating
- Page de statut publique

---

## Architecture Core vs Plugins

### Ce qui fait partie du Core

| Composant | Description |
|-----------|-------------|
| **API REST** | FastAPI, endpoints pour containers, VMs, plugins, marketplace |
| **Base de données** | PostgreSQL (ou SQLite en mode léger pour RPi) |
| **Cache** | Redis (ou en-mémoire en mode léger) |
| **Auth** | JWT avec refresh tokens, organisations, RBAC (4 rôles) |
| **Chiffrement secrets** | AES-256 Fernet pour les données sensibles en base |
| **Audit trail** | Journal d'audit pour toutes les actions modifiantes |
| **Web UI** | Vue.js 3, dashboard, gestion containers/VMs, deux modes (Standard/Avancé) |
| **CLI/TUI** | Rich + Typer + Textual |
| **Container engine** | Docker : containers, compose stacks, images, volumes, networks |
| **VM engine** | Libvirt (KVM/QEMU), Proxmox API, VirtualBox (optionnel) |
| **Stack Definitions** | Templates YAML avec Jinja2, chargement auto depuis fichiers YAML, marketplace de stacks |
| **Plugin manager** | Installation, mise à jour, configuration, dépendances entre plugins |
| **Marketplace** | Catalogue de stacks et plugins, installation one-click |
| **Target manager** | Discovery et gestion des machines cibles (local, SSH) |
| **Bus d'événements** | Redis Pub/Sub (standard) ou asyncio queues (léger) |

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
| **SSO** | Keycloak (LDAP/AD, OIDC, SAML) |

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
- Organisations, environnements, RBAC (4 rôles : Viewer, Operator, Admin, Super Admin)
- Celery pour tâches asynchrones
- Chiffrement des secrets AES-256 Fernet en base
- Rate limiting sur login (5 tentatives/min/IP)

**Interface :**
- Web UI Vue.js 3 + TypeScript + Element Plus
- Dashboard, éditeur YAML, logs temps réel
- Terminal WebSocket dans containers (xterm.js)
- CLI/TUI (Rich + Typer + Textual)

**Docker :**
- Containers et stacks Docker Compose
- Pipeline de déploiement avec retry et rollback automatique
- Targets CRUD avec discovery
- Stacks avec versioning et templates Jinja2
- Stack Definitions : templates YAML auto-chargés au démarrage avec validation Pydantic

**Stack Definitions :**
- Système de templates YAML pour stacks réutilisables
- Fonctions Jinja2 intégrées : `generate_password()`, `generate_secret()`, `random_string()`, `generate_uuid()`, `base64_encode()`, `hash_value()`, `random_port()`, `env()`, `now()`
- Stratégies de mise à jour (`skip_existing`, `update_if_newer`, `force_update`)
- Validation automatique par Pydantic au chargement

#### Métriques
- Couverture tests : ~70%
- API endpoints : 50+
- Templates stacks : 5

---

### Phase 2 : Plugin System, VM Foundation & Refonte UI (Q2 2026)

**Version :** 1.1  
**Durée :** 3 mois (Avril - Juin 2026)  
**Statut :** Planifié — Priorité haute

> **Objectif :** Construire le système de plugins qui est le cœur de l'extensibilité de WindFlow, ajouter la gestion des VMs, poser les bases de la nouvelle UI à deux modes, et livrer les premiers plugins essentiels. À la fin de cette phase, un utilisateur peut installer WindFlow sur un Raspberry Pi, déployer des containers, installer un reverse proxy via plugin, et exposer ses services avec un domaine et du TLS — le tout depuis l'UI.

#### Système de Plugins (priorité #1)

C'est la fondation de tout ce qui suit. Sans un système de plugins solide, WindFlow reste un Portainer-like.

**Plugin Manager :**
- [ ] Format de déclaration plugin (manifest YAML : nom, version, type, dépendances, ressources minimum, architectures supportées, capabilities fournies)
- [ ] Installation / mise à jour / désinstallation depuis l'UI et la CLI
- [ ] Gestion des dépendances entre plugins (ex : Let's Encrypt nécessite Traefik ou Caddy)
- [ ] Vérification compatibilité architecture (arm64/amd64) et ressources disponibles
- [ ] Configuration plugin depuis l'UI (formulaires générés depuis le manifest)
- [ ] Hooks lifecycle : `on_install`, `on_configure`, `on_start`, `on_stop`, `on_uninstall`
- [ ] Vérification d'intégrité (checksum SHA-256 à l'installation)
- [ ] Avertissements de sécurité pour les plugins demandant accès au Docker socket

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
- [ ] Recommandations contextuelles (ex : "Vous avez installé Nextcloud, voulez-vous ajouter Traefik pour exposer le service ?")

**Registre :**
- [ ] Registre de plugins hébergé (index JSON ou API simple)
- [ ] Support registre custom (self-hosted)
- [ ] Vérification d'intégrité (checksums)

#### Mode Léger (Raspberry Pi)

- [ ] Option SQLite au lieu de PostgreSQL pour le core
- [ ] Option cache en-mémoire au lieu de Redis
- [ ] Profil d'installation "léger" (`install.sh --light`)
- [ ] Empreinte mémoire core < 512 Mo RAM
- [ ] Build multi-arch (arm64 + amd64) de toutes les images core
- [ ] Tests CI sur architecture ARM (QEMU ou runner ARM)
- [ ] Bus d'événements via asyncio queues (remplacement Redis Pub/Sub en mode léger)

#### Gestion VMs (core)

**KVM/QEMU (via libvirt) :**
- [ ] Détection automatique si libvirt est disponible
- [ ] CRUD machines virtuelles
- [ ] Console VNC/SPICE intégrée à l'UI (noVNC)
- [ ] Snapshots et clones (full clone et linked clone)
- [ ] Gestion disques (qcow2, raw, conversion entre formats)
- [ ] Gestion images ISO et cloud-init
- [ ] Wizard de création VM par étapes (inspiré Scaleway)

**Proxmox VE :**
- [ ] Connexion API Proxmox
- [ ] CRUD VMs et conteneurs LXC
- [ ] Snapshots, backup/restore
- [ ] Vue nodes et ressources

#### Stockage (core)

**Docker Volumes :**
- [ ] API CRUD volumes
- [ ] Cleanup automatique volumes orphelins

**Volume Browser :**
- [ ] Navigation arborescente dans les volumes avec breadcrumbs
- [ ] Upload/Download fichiers (drag & drop)
- [ ] Preview fichiers (texte, images, logs) — inspiré CasaOS
- [ ] Éditeur de fichiers basique avec coloration syntaxique
- [ ] Affichage des permissions fichiers

**VM Disks :**
- [ ] Gestion disques qcow2, raw
- [ ] Conversion entre formats
- [ ] Snapshots disques

#### Réseau Docker (core)

- [ ] API CRUD networks Docker
- [ ] Network drivers (bridge, overlay, macvlan)
- [ ] Isolation réseau par environnement (network dédié par env)
- [ ] Connecter/déconnecter un container d'un network depuis l'UI

#### Refonte UI — Fondations (priorité haute)

**Deux modes d'interface (Standard / Avancé) :**
- [ ] **Mode Standard** : Dashboard, Apps, Marketplace, Plugins, Settings — suffisant pour 80% des utilisateurs
- [ ] **Mode Avancé** : ajoute Containers, VMs, Stacks, Targets, Volumes, Networks, Images, Audit — pour admins et power users
- [ ] Toggle dans la sidebar (mémorisé par utilisateur), Viewers voient toujours le mode Standard

**Dashboard Homepage :**
- [ ] Salutation personnalisée (Umbrel-like)
- [ ] Métriques système temps réel (CPU, RAM, disque, uptime)
- [ ] Grille d'apps déployées avec icône, statut, port, domaine Traefik (si installé)
- [ ] Zone widgets extensible par les plugins (Uptime Kuma, Traefik, Restic, etc.)
- [ ] Widget "Dernière activité" (journal chronologique des actions récentes)
- [ ] Compteur de notifications avec centre de notifications

**Vue "Apps" unifiée :**
- [ ] Vue unifiée : stacks, containers nommés et VMs dans la même liste
- [ ] Domaine affiché si plugin Traefik actif — clic direct vers l'app
- [ ] Actions inline sans navigation : Ouvrir, Logs, Terminal, Stop/Start, Update
- [ ] Menu contextuel [⋯] pour actions secondaires (backup, clone, modifier, supprimer, voir compose)
- [ ] Badge mise à jour disponible
- [ ] RAM consommée visible directement (essentiel sur RPi)
- [ ] Filtres : par target, par statut, par environnement

**Design System :**
- [ ] Thème sombre par défaut (fond #0c0e14, cartes #151821)
- [ ] Thème clair alternatif (fond #f8f9fc, cartes #ffffff)
- [ ] Typographie : Inter (UI) + JetBrains Mono (code/logs/terminal)
- [ ] Cards arrondies (`border-radius: 12px`), status dots animés
- [ ] Toast notifications (haut droite, auto-dismiss 5s, empilables)

#### Premiers Plugins

**Plugin Traefik (accès & routage) :**
- [ ] Déploie Traefik comme reverse proxy
- [ ] Association domaine ↔ service depuis l'UI WindFlow
- [ ] Routage automatique via labels Docker
- [ ] Let's Encrypt intégré (HTTP challenge + DNS challenge)
- [ ] Dashboard Traefik accessible
- [ ] Onglet "Domaine" injecté dans le détail app (certificat, routing, URL)

**Plugin PostgreSQL (extension) :**
- [ ] Détection auto des containers PostgreSQL
- [ ] Créer databases, users, grants depuis l'UI
- [ ] Backup/restore SQL
- [ ] Métriques basiques
- [ ] Section "Actions Plugin" dans le détail app

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
- UI avec les deux modes (Standard/Avancé) opérationnelle
- Dashboard avec widgets extensibles par plugins

---

### Phase 3 : Plugins Essentiels, Multi-Target & UX Avancée (Q3 2026)

**Version :** 1.2  
**Durée :** 3 mois (Juillet - Septembre 2026)  
**Statut :** Planifié — Priorité haute

> **Objectif :** Étoffer le catalogue de plugins pour couvrir les besoins classiques du self-hosting (DNS, backup, mail, monitoring avancé), ajouter le support multi-machine, et enrichir l'expérience utilisateur avec des fonctionnalités interactives qui rendent la gestion d'infrastructure plaisante.

#### Multi-Target (core)

**Serveurs distants :**
- [ ] Ajout de machines cibles via SSH (clés SSH chiffrées en base)
- [ ] Déploiement de containers sur machines distantes
- [ ] Gestion VMs sur hyperviseurs distants (libvirt, Proxmox)
- [ ] Vue consolidée de toutes les machines et services
- [ ] Monitoring basique par machine (CPU, RAM, disque, réseau)
- [ ] Page "Targets" avec cards métriques et température (inspiré Coolify)

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

#### UX Avancée — Fonctionnalités Utilisateur

**Command Palette (Cmd+K / Ctrl+K) :**
- [ ] Recherche globale rapide : apps, containers, VMs, plugins, stacks, paramètres
- [ ] Actions rapides depuis la palette : restart, deploy, logs, ouvrir une app
- [ ] Navigation clavier complète entre les sections
- [ ] Résultats catégorisés (Apps, Plugins, Targets, Actions, Settings)

**Détail App enrichi (onglets dynamiques) :**
- [ ] Onglet "Aperçu" : services, ressources temps réel, volumes avec [📂] pour ouvrir le volume browser
- [ ] Onglet "Logs" : multi-service avec filtres, coloration syntaxique, recherche regex, export
- [ ] Onglet "Terminal" : shell WebSocket avec copier/coller et redimensionnement
- [ ] Onglet "Volumes" : volume browser intégré avec preview inline
- [ ] Onglets dynamiques ajoutés par les plugins (ex : "Domaine" par Traefik, "Base de données" par plugin PostgreSQL)
- [ ] Métriques de ressources temps réel avec graphiques (CPU, RAM, réseau, I/O)

**Personnalisation du Dashboard :**
- [ ] Widgets repositionnables par drag & drop
- [ ] Choix des widgets affichés (chaque plugin peut fournir un widget)
- [ ] Wallpaper personnalisable (optionnel, inspiré Umbrel)
- [ ] Disposition sauvegardée par utilisateur

**Bulk Actions :**
- [ ] Sélection multiple de containers/VMs/stacks
- [ ] Actions groupées : start, stop, restart, supprimer, mettre à jour
- [ ] Confirmation avec résumé des actions avant exécution

**Gestion améliorée des notifications :**
- [ ] Centre de notifications (panneau latéral ou page dédiée)
- [ ] Catégorisation : déploiements, alertes, mises à jour, sécurité
- [ ] Filtres et marquage lu/non lu
- [ ] Notifications sonores optionnelles pour les alertes critiques

**Responsive Mobile :**
- [ ] Dock fixe en bas pour les 5 sections principales (Home, Apps, Market, Plugins, Settings) — inspiré Umbrel
- [ ] Cards d'apps simplifiées avec bouton "Ouvrir" et menu [⋯]
- [ ] Volume Browser en lecture seule sur mobile
- [ ] Console VNC et Terminal désactivés sur mobile (écran trop petit)
- [ ] Tablette : sidebar rétractée en icônes, widgets en 2 colonnes

#### Critères de succès
- Multi-target fonctionnel : piloter 2+ machines depuis une instance
- 15+ plugins disponibles dans la marketplace
- 10+ templates de stacks one-click
- Kubernetes basique fonctionnel
- Backup automatisé via plugin Restic
- Command palette fonctionnelle
- Dashboard avec widgets personnalisables

---

### Phase 4 : Sécurité, Git, Polish & Expérience Utilisateur (Q4 2026)

**Version :** 1.3  
**Durée :** 3 mois (Octobre - Décembre 2026)  
**Statut :** Planifié — Priorité moyenne

> **Objectif :** Solidifier la plateforme — sécurité, traçabilité, intégration Git, et amélioration globale de l'expérience utilisateur. WindFlow doit inspirer confiance pour gérer une petite infrastructure en production. L'UI devient un véritable outil de travail quotidien.

#### Sécurité (core + plugins)

**Core — Secrets :**
- [ ] Chiffrement des secrets stockés (AES-256 via Fernet, déjà implémenté en base — compléter avec rotation)
- [ ] Rotation de secrets avec invalidation de cache
- [ ] Variables d'environnement sécurisées par stack (champ `env_vars_encrypted`)
- [ ] Protection du SECRET_KEY : permissions 600, alerte si compromis

**Plugin Trivy (vulnerability scanning) :**
- [ ] Scan d'images Docker avant déploiement
- [ ] Dashboard vulnérabilités avec tri par sévérité
- [ ] Alertes severity high/critical
- [ ] Scan planifié des images existantes
- [ ] Option de blocage du déploiement si vulnérabilités critiques

**Plugin Vault (secrets avancés) :**
- [ ] HashiCorp Vault déployé et intégré
- [ ] Secrets dynamiques pour bases de données
- [ ] Rotation automatique
- [ ] Audit trail des accès aux secrets

**Core — Audit :**
- [ ] Audit trail complet : qui a fait quoi, quand, depuis quelle IP
- [ ] Consultation depuis l'UI (page Settings > Audit) et CLI (`windflow admin audit`)
- [ ] Filtres : par utilisateur, par action, par date
- [ ] Politique de rétention configurable (`AUDIT_RETENTION_DAYS`)
- [ ] Export des logs d'audit

#### Git Integration (core)

- [ ] Stacks depuis un dépôt Git (git_url, branch, path)
- [ ] Sync automatique (pull périodique)
- [ ] Webhook auto-deploy on push (GitHub, GitLab, Gitea)
- [ ] Rollback vers un commit précédent
- [ ] Auth SSH keys et tokens
- [ ] Preview des logs de déploiement en temps réel (inspiré Coolify)

#### SSO (plugin)

- [ ] **Plugin Keycloak** : déploiement + intégration auth WindFlow
- [ ] Mapping rôles Keycloak → rôles WindFlow (Viewer, Operator, Admin)
- [ ] LDAP/Active Directory
- [ ] OIDC providers

#### UX & Polish

**Onboarding (premier lancement) :**
- [ ] Wizard 4 étapes : Compte → Machine → Première app → Terminé
- [ ] Détection automatique du hardware (architecture, RAM, stockage, Docker, KVM)
- [ ] Recommandation de profil d'installation (Léger/Standard)
- [ ] Suggestion d'installer un premier plugin (Traefik) et une première app (Nextcloud, Gitea, Jellyfin)

**Guided Troubleshooting :**
- [ ] Wizard de diagnostic quand un déploiement échoue
- [ ] Analyse automatique des logs d'erreur avec suggestions de résolution
- [ ] Vérification des prérequis (port occupé, image introuvable, ressources insuffisantes)
- [ ] Bouton "Réessayer" avec options de correction (changer le port, libérer de la RAM)

**Topologie réseau visuelle :**
- [ ] Vue graphique des networks Docker : quels containers sont connectés à quels réseaux
- [ ] Visualisation des dépendances entre services d'une stack
- [ ] Vue interactive (clic sur un node pour détails)

**App Groups / Dossiers :**
- [ ] Regrouper les apps par catégorie personnalisée (ex : "Production", "Dev", "Média")
- [ ] Dossiers repliables dans la vue Apps
- [ ] Tags personnalisés sur les apps avec filtrage

**Historique des déploiements :**
- [ ] Timeline visuelle des déploiements par stack (version, date, durée, statut)
- [ ] Comparaison side-by-side de deux versions de configuration
- [ ] Rollback en un clic depuis la timeline

**Quick Actions depuis le Dashboard :**
- [ ] Raccourcis clavier pour les actions les plus fréquentes
- [ ] Bouton "Nouvelle App" accessible partout (FAB sur mobile)
- [ ] Actions contextuelles sur les widgets (restart depuis le widget Uptime Kuma)

**Internationalisation :**
- [ ] Français et anglais au minimum
- [ ] Système i18n extensible pour contributions communautaires

**Amélioration du Marketplace :**
- [ ] Recommandations "Souvent installé avec…" (ex : Nextcloud → Redis, Traefik)
- [ ] Filtres avancés : par architecture, par catégorie, par RAM minimum
- [ ] Preview de l'impact ressources avant installation
- [ ] Wizard d'installation par étapes avec résumé d'impact (inspiré Scaleway/Cloudron)
- [ ] Badge de popularité et de mise à jour récente

**Documentation intégrée :**
- [ ] Tooltips et aide contextuelle sur les formulaires
- [ ] Liens "En savoir plus" vers la documentation en ligne
- [ ] FAQ inline pour les erreurs courantes

#### Plugin Mail

- [ ] **Plugin Mailu** : serveur mail complet (SMTP, IMAP, webmail)
- [ ] **Plugin Stalwart** : alternative Mailu plus légère
- [ ] Gestion domaines mail, boîtes, alias depuis l'UI WindFlow

#### Critères de succès
- Secrets chiffrés en base avec rotation
- Scanning vulnérabilités fonctionnel via plugin Trivy
- Auto-deploy depuis Git opérationnel
- Audit trail complet consultable depuis l'UI
- 20+ plugins dans la marketplace
- Onboarding wizard fonctionnel
- Topologie réseau visuelle
- Internationalisation FR/EN

---

### Phase 5 : Automatisation & Intelligence (H1 2027)

**Version :** 2.0  
**Durée :** 6 mois (Janvier - Juin 2027)  
**Statut :** Planifié — Priorité moyenne

> **Objectif :** Ajouter de l'intelligence et de l'automatisation — toujours sous forme de plugins optionnels. Un Raspberry Pi n'a pas besoin d'un LLM, mais un homelab plus costaud peut en profiter. L'interface franchit un cap en termes de productivité.

#### Plugin Workflow Engine

- [ ] **Plugin n8n** ou **Node-RED** : déploiement + intégration events WindFlow
- [ ] Triggers depuis WindFlow : deploy, alert, scale, backup terminé…
- [ ] Workflows préconfigurés : backup → notify, alert → restart, push → deploy
- [ ] Éditeur visuel drag-and-drop intégré à l'UI (si workflow engine natif WindFlow)

#### Plugin IA (LiteLLM / Ollama)

**Plugin Ollama (LLM local) :**
- [ ] Déploiement d'Ollama avec gestion des modèles depuis l'UI
- [ ] Modèles recommandés selon les ressources de la machine (3b pour 4Go, 8b pour 8Go, 13b pour 16Go)
- [ ] Support ARM64 (RPi 5 avec 8Go)

**Plugin LiteLLM (proxy cloud) :**
- [ ] Proxy multi-provider (OpenAI, Anthropic Claude, Google Gemini, Groq, Mistral AI)
- [ ] Configuration du provider et de la clé API depuis l'UI
- [ ] Empreinte mémoire négligeable (~50 Mo)

**Fonctionnalités IA :**
- [ ] Génération de docker-compose depuis description en langage naturel
- [ ] Diagnostic automatique : analyse logs → suggestion de fix
- [ ] Chat assistant intégré à l'UI (panneau latéral)
- [ ] Suggestions d'optimisation ressources (basées sur l'usage réel)
- [ ] Suggestions de sécurité : analyse de configuration et signalement de problèmes
- [ ] L'IA ne prend jamais de décision automatiquement — elle suggère, l'utilisateur valide
- [ ] L'IA n'a pas accès aux secrets ni aux données sensibles

#### Auto-Updates (core)

- [ ] Vérification mises à jour pour les stacks déployées
- [ ] Politiques : auto, notification seule, manual
- [ ] Rollback automatique si health check échoue après mise à jour
- [ ] Changelog intégré
- [ ] Badge [⬆] sur les apps avec mise à jour disponible (déjà présent en UI depuis Phase 2)
- [ ] Backup automatique avant mise à jour (si plugin Restic installé)

#### Plugin SDK & Communauté

- [ ] SDK documenté pour créer des plugins
- [ ] Template de plugin (scaffolding CLI : `windflow plugin create my-plugin`)
- [ ] Guide contributeur plugins avec bonnes pratiques
- [ ] Soumission de plugins communautaires au registre
- [ ] Système de review et rating dans la marketplace
- [ ] Test automatisé des plugins soumis (lint, validation manifest, build multi-arch)

#### UX Avancée — Phase 2

**PWA (Progressive Web App) :**
- [ ] Installation comme app native sur mobile et desktop
- [ ] Notifications push pour les alertes critiques
- [ ] Mode hors-ligne basique (dernière vue connue du dashboard)

**Page de statut publique :**
- [ ] Page publique (sans auth) avec le statut des services exposés
- [ ] Personnalisable : logo, couleurs, services affichés
- [ ] Historique d'uptime sur 30/90 jours
- [ ] Incidents avec timeline

**Resource Planner :**
- [ ] Visualisation de la répartition des ressources (CPU, RAM) par app et par target
- [ ] Alertes proactives : "Si vous installez Nextcloud, votre RAM restante sera de 500 Mo"
- [ ] Suggestions de redistribution des workloads entre machines (multi-target)

**Live Terminal amélioré :**
- [ ] Multiples onglets de terminal simultanés
- [ ] Historique de commandes partagé par container
- [ ] Raccourcis pour les commandes fréquentes par type de container

**Import d'infrastructure existante :**
- [ ] Scanner Docker Engine pour détecter les containers existants (non gérés par WindFlow)
- [ ] Import en un clic : adopter un container existant dans WindFlow
- [ ] Génération automatique du docker-compose correspondant

**Tableaux de bord personnalisés :**
- [ ] Création de dashboards custom avec widgets au choix
- [ ] Dashboards partageables entre utilisateurs
- [ ] Export de dashboards en JSON

#### Critères de succès
- Workflow engine fonctionnel via plugin
- IA capable de générer des configs valides (sur machine compatible)
- SDK plugins documenté avec au moins 2 plugins communautaires
- Auto-updates avec rollback
- PWA installable avec notifications push
- Page de statut publique

---

### Phase 6 : Long Terme (2027+)

**Statut :** Vision

#### Fédération Multi-Instances

- [ ] Piloter plusieurs instances WindFlow depuis un dashboard central
- [ ] Sync de configurations entre instances
- [ ] Vue globale multi-sites
- [ ] Agrégation des métriques et alertes

#### Mobile App Native

- [ ] App mobile (React Native ou Flutter) pour monitoring et actions rapides
- [ ] Notifications push natives
- [ ] Actions : restart, logs, status, déploiement rapide
- [ ] Widget iOS/Android pour le statut des services
- [ ] Biométrie pour l'authentification

#### PaaS Léger (plugin)

- [ ] Build depuis source (Buildpacks / Dockerfile auto-detect)
- [ ] Deploy depuis git push (Heroku-like)
- [ ] Review apps (environnement par branche)
- [ ] Preview environments avec URL temporaire

#### Analytics & Capacity Planning (plugin)

- [ ] Capacity planning basique avec prédictions
- [ ] Alertes proactives (disque bientôt plein, certificat expirant, RAM tendanciellement saturée)
- [ ] Historique de consommation ressources sur 1/6/12 mois
- [ ] Rapports d'utilisation exportables

#### Multi-Tenant SaaS (optionnel)

- [ ] Mode SaaS pour proposer WindFlow en tant que service
- [ ] Facturation par organisation/ressource
- [ ] Isolation complète entre tenants

#### Marketplace Communautaire Mature

- [ ] Système de review et rating par les utilisateurs
- [ ] Badges de qualité (officiels, vérifié, populaire)
- [ ] Versioning des plugins avec historique
- [ ] Plugin bundles (collections thématiques : "Homelab Starter", "Dev Team Essentials")

---

## Priorités Court Terme

| # | Fonctionnalité | Phase | Impact |
|---|----------------|-------|--------|
| 1 | Plugin System (manager + marketplace) | 2 | Fondation de tout le reste |
| 2 | Mode léger RPi (SQLite, empreinte réduite) | 2 | Élargit la base d'utilisateurs |
| 3 | Gestion VMs (KVM/Proxmox) | 2 | Core promise du produit |
| 4 | Plugin Traefik (reverse proxy + TLS) | 2 | Indispensable pour exposer des services |
| 5 | UI deux modes (Standard/Avancé) + Dashboard widgets | 2 | UX fondamentale |
| 6 | Volume Browser | 2 | UX essentielle pour le self-hosting |
| 7 | Premiers plugins DB (PostgreSQL, Redis) | 2 | Valide le plugin system |
| 8 | Multi-target (SSH) | 3 | Gestion multi-machines |
| 9 | Command Palette + Bulk Actions | 3 | Productivité quotidienne |
| 10 | Templates marketplace (Nextcloud, Gitea…) | 3 | Adoption self-hosters |
| 11 | Plugins backup (Restic) | 3 | Confiance en production |
| 12 | Git integration + auto-deploy | 4 | Workflow développeur |
| 13 | Onboarding wizard | 4 | First-time UX |
| 14 | Topologie réseau visuelle | 4 | Compréhension de l'infra |

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

extensions:
  api_module: extensions/api.py
  api_permissions:
    read: viewer
    write: operator
    admin: admin
```

### Format Stack Definition (draft)

```yaml
metadata:
  name: "PostgreSQL"
  version: "1.0.0"
  category: "Database"
  description: "Base de données PostgreSQL"
  tags: [database, postgresql]
  is_public: true
  target_type: "docker"

template:
  image: "postgres:{{ version }}"
  container_name: "{{ name }}"
  environment:
    POSTGRES_PASSWORD: "{{ password }}"
  ports:
    - "{{ port }}:5432"
  volumes:
    - "postgres_data:/var/lib/postgresql/data"

variables:
  version:
    type: string
    label: "Version"
    default: "16"
    required: true
    enum: ["16", "15", "14"]
  password:
    type: password
    label: "Mot de passe"
    default: "{{ generate_password(24) }}"
    required: true
    min_length: 12
  port:
    type: number
    label: "Port"
    default: 5432
    required: true
    minimum: 1
    maximum: 65535
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
| Sécurité des plugins tiers | Moyen | Checksum SHA-256, niveaux de confiance, avertissements pour extensions sensibles |
| UX trop complexe pour les débutants | Moyen | Mode Standard par défaut, onboarding wizard, documentation contextuelle |

---

**Références :**
- [Vue d'Ensemble](01-overview.md) — Vision et objectifs
- [Architecture](02-architecture.md) — Architecture technique
- [Stack Technologique](03-technology-stack.md) — Technologies
- [Modèle de Données](04-data-model.md) — Structure des données
- [Authentification](05-authentication.md) — JWT, API keys, brute-force protection
- [RBAC et Permissions](06-rbac-permissions.md) — Rôles et matrice de permissions
- [API Design](07-api-design.md) — APIs et endpoints
- [CLI Interface](08-cli-interface.md) — Commandes CLI/TUI
- [Architecture Modulaire](09-plugins.md) — Système de plugins
- [Fonctionnalités Principales](10-core-features.md) — Fonctionnalités core
- [UI Mockups](11-UI-mockups.md) — Maquettes d'interface
- [Sécurité](13-security.md) — Sécurité globale
- [Guide de Déploiement](15-deployment-guide.md) — Installation
- [Workflows](16-workflows.md) — Système de workflows
- [Intégration LLM](17-llm-integration.md) — Intelligence artificielle
- [Stack Definitions](STACK-DEFINITIONS.md) — Templates de stacks YAML
- [Fonctions Jinja2](JINJA2-FUNCTIONS.md) — Fonctions disponibles dans les templates
- [Architecture Modulaire](ARCHITECTURE-MODULAIRE.md) — Extensions et configurations
