# WindFlow - Documentation Technique

Documentation technique du projet WindFlow, un gestionnaire d'infrastructure self-hosted léger pour conteneurs et machines virtuelles, extensible par plugins.

## Structure de la Documentation

### Vue d'Ensemble et Architecture
- **[01-overview.md](01-overview.md)** — Vision du projet, philosophie core + plugins, cas d'usage, architecture de haut niveau
- **[02-architecture.md](02-architecture.md)** — Architecture monolithique modulaire, profils de déploiement (léger/standard), système de plugins, modèle de données, communication et événements
- **[03-technology-stack.md](03-technology-stack.md)** — Stack technique core vs plugins, PostgreSQL/SQLite, Redis/mémoire, FastAPI, Vue.js, Docker SDK, libvirt, Celery

### Conception Technique
- **[04-data-model.md](04-data-model.md)** — Modèle de données (13 tables), entités core et plugins, compatibilité SQLite, modèle SQLAlchemy
- **[05-authentication.md](05-authentication.md)** — Auth JWT, refresh tokens, API keys, auth CLI, protection brute-force, SSO via plugin Keycloak
- **[06-rbac-permissions.md](06-rbac-permissions.md)** — 4 rôles (Viewer, Operator, Admin, Super Admin), matrice de permissions, gestion des utilisateurs

### Interfaces
- **[07-api-design.md](07-api-design.md)** — API REST complète (containers, VMs, stacks, targets, plugins, marketplace), WebSocket, routes dynamiques des plugins, gestion des erreurs
- **[08-cli-interface.md](08-cli-interface.md)** — CLI (Typer + Rich) et TUI (Textual), référence complète des commandes, configuration

### Fonctionnalités et Plugins
- **[09-plugins.md](09-plugins.md)** — Catalogue des plugins officiels (30+ plugins par catégorie), fiches techniques, bonnes pratiques
- **[10-core-features.md](10-core-features.md)** — Fonctionnalités core détaillées : containers, VMs, plugins, marketplace, stacks, targets, volumes, réseaux, RBAC, UI, CLI
- - **[11-UI-mockups.md](11-UI-mockups.md)** — Maquettes d'écran et interface utilisateur présentant toutes les fonctionnalités

### Sécurité et Déploiement
- **[13-security.md](13-security.md)** — Chiffrement des secrets, sécurité du Docker socket, audit trail, sécurité réseau, sécurité des plugins, checklist
- **[15-deployment-guide.md](15-deployment-guide.md)** — Installation (mode léger RPi / standard / développement), docker-compose, script d'installation, backup/restore, dépannage

### Workflows
- **[16-workflows.md](16-workflows.md)** — Mécanismes de workflows entre les composants et mécanismes de déploiement

### Référence
- **[17-llm-integration.md](17-llm-integration.md)** — Plugins IA (Ollama, LiteLLM), fonctionnalités, prérequis ARM, architecture technique
- **[18-roadmap.md](18-roadmap.md)** — Roadmap de développement, phases, priorités, métriques de succès

## Navigation par Profil

### Self-Hoster / Utilisateur
1. [Vue d'Ensemble](01-overview.md) — Comprendre WindFlow
2. [Guide de Déploiement](15-deployment-guide.md) — Installer WindFlow
3. [Fonctionnalités Principales](10-core-features.md) — Ce que le core fait
4. [Catalogue des Plugins](09-plugins.md) — Quels plugins installer
5. [CLI Interface](08-cli-interface.md) — Utiliser la ligne de commande
6. [UI Mockups](08-UI-mockups.md) — Maquettes d'écran du frontend

### Développeur Backend
1. [Architecture](02-architecture.md) — Comment WindFlow est construit
2. [Stack Technologique](03-technology-stack.md) — Technologies et dépendances
3. [Modèle de Données](04-data-model.md) — Tables et relations
4. [API Design](07-api-design.md) — Endpoints et modèles
5. [Authentification](05-authentication.md) — Auth et sécurité

### Développeur de Plugins
1. [Architecture Modulaire](../ARCHITECTURE-MODULAIRE.md) — Tout sur les plugins
2. [Catalogue des Plugins](09-plugins.md) — Exemples de plugins existants
3. [API Design](07-api-design.md) — Comment les plugins étendent l'API
4. [Stack Technologique](03-technology-stack.md) — Plugin Manager et registre
5. [Workflows](16-workflows.md) — Systèmes de workflows et mécanismes de déploiement

### Administrateur Système
1. [Guide de Déploiement](15-deployment-guide.md) — Installation et configuration
2. [Sécurité](13-security.md) — Checklist et bonnes pratiques
3. [RBAC et Permissions](06-rbac-permissions.md) — Gestion des accès
4. [CLI Interface](08-cli-interface.md) — Administration en ligne de commande

---

**Version de la documentation :** 2.0
**Dernière mise à jour :** Mars 2026
**Projet :** WindFlow — Gestionnaire d'infrastructure self-hosted
