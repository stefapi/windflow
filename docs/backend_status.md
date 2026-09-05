# Statut fonctionnel du Backend WindFlow

> **Date du document :** 30 août 2026
>
> **Périmètre :** backend uniquement (`backend/`), analyse du code source uniquement — hors documentation, frontend et CLI.
>
> **Avertissement :** ce document reflète l'état du code **au moment de l'analyse** (analyse en lecture seule). Il décrit ce qui existe réellement dans le code, avec les écarts identifiés vis-à-vis de ce qui est annoncé dans la documentation projet. Toute évolution ultérieure du code peut rendre certaines sections obsolètes.

---

## Sommaire

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture & runtime](#2-architecture--runtime)
3. [API REST — inventaire exhaustif](#3-api-rest--inventaire-exhaustif)
4. [Exécution des déploiements — runners & orchestrateur](#4-exécution-des-déploiements--runners--orchestrateur)
5. [Services métier](#5-services-métier)
6. [Base de données & modèles](#6-base-de-données--modèles)
7. [Sécurité — AuthN / AuthZ / RBAC](#7-sécurité--authn--authz--rbac)
8. [WebSocket temps réel](#8-websocket-temps-réel)
9. [Event-driven & tâches de fond](#9-event-driven--tâches-de-fond)
10. [Core transversal, middleware, helper, enums](#10-core-transversal-middleware-helper-enums)
11. [Configuration](#11-configuration)
12. [IA / LiteLLM](#12-ia--litellm)
13. [Tests & couverture](#13-tests--couverture)
14. [Implémenté vs annoncé — zones mortes & lacunes](#14-implémenté-vs-annoncé--zones-mortes--lacunes)
15. [Synthèse](#15-synthèse)

---

## 1. Vue d'ensemble

Le backend WindFlow est un **modular monolith FastAPI** (~135 fichiers Python) centré sur : authentification JWT simple (modèle binaire user/superadmin), gestion multi-tenant (organisations / utilisateurs / cibles / stacks), déploiement Docker/Compose via des exécuteurs CLI/socket avec orchestration asyncio (retry/recovery), scan de cibles poussé, WebSocket temps réel modulaire et un système de plugins complet.

```
backend/  (~135 fichiers Python au total)
├── app/
│   ├── main.py, config.py, database.py, database_seed.py, celery_app.py
│   ├── api/v1/            → 17 routers + sous-packages admin/ et targets/ (~20 fichiers)
│   ├── auth/              → 3 fichiers (jwt, dependencies, __init__)
│   ├── core/              → 6 fichiers (events, exceptions, resilience, rate_limit, abstractions)
│   ├── enums/             → 2 fichiers (target.py : TargetType, TargetStatus, CapabilityType…)
│   ├── helper/            → ~12 fichiers (noms générés, croniter, jinja, template_renderer, security…)
│   ├── middleware/        → 6 middlewares + README
│   ├── models/            → 10 entités ORM
│   ├── schemas/           → ~21 fichiers Pydantic
│   ├── services/          → ~36 services métier
│   ├── tasks/             → 1 fichier (background_tasks.py)
│   └── websocket/         → ~12 modules + 4 plugins
└── tests/                 → ~66 fichiers de test (conftest + ~52 unit + 7 integration)
```

**Point majeur :** il n'existe **pas** de dossier `backend/alembic/` — aucune migration Alembic dans le backend. Le schéma est créé par `Base.metadata.create_all()` au démarrage (voir [§6](#6-base-de-données--modèles)).

---

## 2. Architecture & runtime

### 2.1 Point d'entrée & montage — [`main.py`](backend/app/main.py)

- Application FastAPI (titre/version depuis les settings, description OpenAPI riche, `servers` construits dynamiquement via `build_server_urls()` dans [`config.py`](backend/app/config.py)).
- **Documentation API :**
  - Scalar sur `/docs` ([`scalar_docs()`](backend/app/main.py:359)),
  - Swagger UI sur `/swagger`,
  - ReDoc sur `/redoc`,
  - OpenAPI sur `/openapi.json` — `docs_url` est redéfini vers `/swagger` ([`main.py`](backend/app/main.py:224)).
- **Endpoints racine :**
  - `GET /` : infos API ([`main.py`](backend/app/main.py:296)) ;
  - `GET /health` : vérifie DB + Redis si configuré, 503 si DB down ([`main.py`](backend/app/main.py:315)).
- **Exception handlers** Pydantic/FastAPI → 422 avec `correlation_id` ([`main.py`](backend/app/main.py:380)).

### 2.2 Lifespan ([`main.py`](backend/app/main.py:59))

**Startup :**

1. `db.connect()` + `db.create_tables()` + `db.seed_tables()` — création du schéma + seed admin/org par défaut ;
2. [`setup_event_bridge()`](backend/app/websocket/event_bridge.py:82) — pont EventBus → WebSocket ;
3. Init `FastAPILimiter` (Redis) si `rate_limit_enabled` **ET** `rate_limit_storage_url` (dégrade silencieusement sinon) ;
4. `DeploymentOrchestrator.recover_pending_deployments()` — reprise des déploiements orphelins au redémarrage ;
5. Boucle asyncio de health-check des cibles toutes les 5 min ([`_periodic_health_check()`](backend/app/main.py:134)) — explicitement décrite comme « fallback quand Celery est indisponible ».

**Shutdown :** annulation de la tâche de santé, fermeture du rate limiter, `db.disconnect()`.

### 2.3 Middlewares — ordre critique ([`main.py`](backend/app/main.py:254), documenté dans [`middleware/README.md`](backend/app/middleware/README.md))

| # | Middleware | Rôle |
|---|-----------|------|
| 1 | CORS | Conditionné par `cors_enabled` |
| 2 | Security Headers | CSP construite par [`build_csp_header()`](backend/app/config.py:267), HSTS, X-Frame-Options |
| 3 | Timing | Mesure `X-Process-Time`, log des requêtes lentes > `slow_request_threshold` |
| 4 | Correlation ID | Header `X-Correlation-ID` |
| 5 | Logging | Logging structuré |
| 6 | Error Handler | Dernier, catch-all |

### 2.4 Montage des routers ([`api/v1/__init__.py`](backend/app/api/v1/__init__.py:28))

`api_router = APIRouter(prefix="/api/v1")`, puis 17 sous-routers avec préfixes/tags :

`/auth`, `/users`, `/organizations`, `/targets`, `/stacks`, `/deployments`, `/workflows`, `/ws`, `stats` (sans préfixe), `import-export`, `/schedules`, `/admin` (préfixe porté par le router), `/docker`, `/compute`, `/discovery`, `/plugins`, `/registry`.

---

## 3. API REST — inventaire exhaustif

> ~110 endpoints + 5 canaux WebSocket.
>
> **Rôles :** `auth` = `get_current_active_user` ; `superadmin` = `require_superuser`.
> **RL** = rate limiting conditionnel ([`conditional_rate_limiter()`](backend/app/core/rate_limit.py:18)).

### 3.1 [`auth.py`](backend/app/api/v1/auth.py:27)

| Méthode | Route | Accès | Notes |
|---------|-------|-------|-------|
| POST | `/auth/login` | Public, RL 5/min | Login username OU email, JWT + refresh, support `disable_auth` (auto-login superadmin) |
| POST | `/auth/refresh` | Public, RL 10/min | Rotation des tokens (vérifie user actif + cohérence des claims) |
| POST | `/auth/logout` | auth, RL 20/min | Stateless — le client supprime les tokens, pas de blacklist serveur |
| POST | `/auth/register` | Public | Inscription + auto-login (201) |
| GET | `/auth/me` | auth | Profil courant |

### 3.2 [`users.py`](backend/app/api/v1/users.py:49)

| Méthode | Route | Accès | Notes |
|---------|-------|-------|-------|
| GET | `/users/` | auth | Liste paginée (skip/limit) |
| GET | `/users/me` | auth | Profil courant (doublon fonctionnel de `/auth/me`) |
| GET | `/users/{user_id}` | auth | Détail |
| POST | `/users/` | auth | Création |
| PUT | `/users/{user_id}` | auth | Mise à jour |
| DELETE | `/users/{user_id}` | auth | Suppression |
| POST | `/users/bulk/delete` | superadmin | Suppression en masse |
| POST | `/users/bulk/assign-organization` | superadmin | Assignation d'organisation en masse |

### 3.3 [`organizations.py`](backend/app/api/v1/organizations.py:43)

| Méthode | Route | Accès | Notes |
|---------|-------|-------|-------|
| GET | `/organizations/` | superadmin | Liste paginée |
| GET | `/organizations/{id}` | auth (membre) | Détail |
| POST | `/organizations/` | superadmin | Création |
| PUT | `/organizations/{id}` | superadmin | Mise à jour |
| DELETE | `/organizations/{id}` | superadmin | Suppression |
| POST | `/organizations/bulk/delete` | superadmin | Suppression en masse |

### 3.4 [`targets/`](backend/app/api/v1/targets) — 4 sous-modules

**[`crud.py`](backend/app/api/v1/targets/crud.py)** (tous auth) :

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `/targets/` | Paginé |
| GET | `/targets/{target_id}` | Détail |
| PUT | `/targets/{target_id}` | Mise à jour |
| DELETE | `/targets/{target_id}` | Suppression |
| POST | `/targets/` | Création |

**[`connectivity.py`](backend/app/api/v1/targets/connectivity.py)** (auth, RL) :

| Méthode | Route | Notes |
|---------|-------|-------|
| POST | `/targets/test-reachability` | TCP/ping sans credentials |
| POST | `/targets/test-connection` | Test SSH complet |

**[`capabilities.py`](backend/app/api/v1/targets/capabilities.py)** (auth) :

| Méthode | Route | Notes |
|---------|-------|-------|
| POST | `/targets/{target_id}/health-check` | Vérification de santé |
| GET | `/targets/{target_id}/capabilities` | Filtre par type |
| GET | `/targets/{target_id}/capabilities/{capability_type}` | Capacité d'un type donné |
| GET | `/targets/{target_id}/capabilities/virtualization` | Capacités de virtualisation |

**[`scanning.py`](backend/app/api/v1/targets/scanning.py)** (auth, RL) :

| Méthode | Route | Notes |
|---------|-------|-------|
| POST | `/targets/discover` | Découverte réseau de cibles |
| POST | `/targets/{target_id}/scan` | Scan complet de capacités |

### 3.5 [`stacks.py`](backend/app/api/v1/stacks.py:116) — 17 endpoints, tous auth

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `/stacks/` | Filtre `include_archived` |
| GET | `/stacks/{stack_id}` | Détail |
| PUT | `/stacks/{stack_id}` | Mise à jour |
| DELETE | `/stacks/{stack_id}` | Suppression |
| POST | `/stacks/` | Création |
| POST | `/stacks/{stack_id}/regenerate-variable/{variable_name}` | Régénération d'une valeur générée |
| GET | `/stacks/{stack_id}/versions` | Historique de versions |
| POST | `/stacks/{stack_id}/versions` | Création de version |
| POST | `/stacks/{stack_id}/versions/{version_id}/restore` | Restauration d'une version |
| POST | `/stacks/{stack_id}/start` | Démarrage |
| POST | `/stacks/{stack_id}/stop` | Arrêt |
| POST | `/stacks/{stack_id}/redeploy` | Redéploiement |
| POST | `/stacks/{stack_id}/duplicate` | Duplication |
| POST | `/stacks/{stack_id}/archive` | Archivage |
| POST | `/stacks/{stack_id}/unarchive` | Désarchivage |

### 3.6 [`deployments.py`](backend/app/api/v1/deployments.py:29) — tous auth

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `/deployments` | Paginé |
| GET | `/deployments/{deployment_id}` | Détail |
| GET | `/deployments/{deployment_id}/logs` | Logs |
| POST | `/deployments` | Création + lancement orchestrateur |
| PUT | `/deployments/{deployment_id}` | Mise à jour |
| POST | `/deployments/{deployment_id}/retry` | Retry |
| POST | `/deployments/{deployment_id}/cancel` | Annulation |
| DELETE | `/deployments/{deployment_id}` | Suppression |

### 3.7 [`docker.py`](backend/app/api/v1/docker.py:69) — 40 endpoints, tous auth (le plus gros router)

**Conteneurs :**

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `/docker/containers` | Paginé (`limit` 1-100) |
| GET | `/docker/containers/{id}` | Détail |
| POST | `/docker/containers` | Création |
| POST | `/docker/containers/batch/start` | Démarrage en masse |
| POST | `/docker/containers/batch/stop` | Arrêt en masse |
| POST | `/docker/containers/{id}/start` | Démarrage |
| POST | `/docker/containers/{id}/stop` | Arrêt |
| POST | `/docker/containers/{id}/restart` | Redémarrage |
| POST | `/docker/containers/{id}/pause` | Pause |
| POST | `/docker/containers/{id}/unpause` | Reprise |
| DELETE | `/docker/containers/{id}` | Suppression |
| POST | `/docker/containers/{id}/recreate` | Recréation |
| PATCH | `/docker/containers/{id}/restart-policy` | Politique de redémarrage |
| PATCH | `/docker/containers/{id}/resources` | Ressources |
| POST | `/docker/containers/{id}/rename` | Renommage |
| POST | `/docker/containers/{id}/networks/connect` | Connexion réseau |
| POST | `/docker/containers/{id}/networks/disconnect` | Déconnexion réseau |
| POST | `/docker/containers/{id}/promote` | Promotion conteneur → stack managée |
| GET | `/docker/containers/{id}/shells` | Shells disponibles |
| GET | `/docker/containers/{id}/stats` | Statistiques |
| GET | `/docker/containers/{id}/top` | Processus |
| GET | `/docker/containers/{id}/logs` | Logs |

**Images :**

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `/docker/images` | Paginé |
| GET | `/docker/images/{image_id}` | Détail |
| POST | `/docker/images/pull` | Pull |
| DELETE | `/docker/images/{image_id}` | Suppression |
| POST | `/docker/images/load` | Upload tar |
| GET | `/docker/images/{image_id}/save` | Export tar |

**Volumes / Réseaux :**

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `/docker/volumes` | Paginé |
| POST | `/docker/volumes` | Création |
| DELETE | `/docker/volumes` | Suppression |
| GET | `/docker/networks` | Paginé |

**Système :**

| Méthode | Route |
|---------|-------|
| GET | `/docker/system/info` |
| GET | `/docker/system/version` |
| GET | `/docker/system/ping` |

### 3.8 [`compute.py`](backend/app/api/v1/compute.py:25) — auth

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `/compute/stats` | Statistiques compute |
| GET | `/compute/global` | Vue agrégée de l'inventaire compute (stacks managées / items découverts / conteneurs standalone, groupés par cible) |

### 3.9 [`discovery.py`](backend/app/api/v1/discovery.py:25) — auth

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `/discovery/{item_type}/{item_id}/adoption-data` | Données pour l'assistant d'adoption (secrets env masqués) |
| POST | `/discovery/adopt` | Adoption d'un conteneur découvert en stack managée |

### 3.10 [`stats.py`](backend/app/api/v1/stats.py:34) — auth

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `/stats/dashboard` | KPIs globaux |
| GET | `/stats/stacks/{stack_id}` | Statistiques d'une stack |

### 3.11 [`import_export.py`](backend/app/api/v1/import_export.py:20) — auth

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `/stacks/{stack_id}/export` | Export YAML |
| POST | `/stacks/import` | Import par upload de fichier |

### 3.12 [`schedules.py`](backend/app/api/v1/schedules.py:24) — tous auth

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `/schedules` | Liste |
| POST | `/schedules` | Création |
| GET | `/schedules/{task_id}` | Détail |
| PUT | `/schedules/{task_id}` | Mise à jour |
| DELETE | `/schedules/{task_id}` | Suppression |
| POST | `/schedules/{task_id}/toggle` | Activation/désactivation |

### 3.13 [`admin/stacks_management.py`](backend/app/api/v1/admin/stacks_management.py:16) — superadmin partout (`get_current_superadmin`)

Monté sur `/api/v1/admin/stacks-management`. Remplace les anciens scripts seed/check (docstring).

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `definitions` | Liste des définitions |
| POST | `validate` | Validation |
| POST | `import` | Import |
| GET | `imported` | Définitions importées |
| GET | `sync/status` | Statut de synchronisation |
| POST | `sync/auto` | Synchronisation automatique |
| GET | `{stack_id}/export` | Export |
| POST | `export/bulk` | Export en masse |
| PATCH | `{stack_id}/toggle-visibility` | Visibilité |
| POST | `{stack_id}/duplicate` | Duplication |
| DELETE | `{stack_id}` | Suppression |
| GET | `stats/overview` | Vue d'ensemble des statistiques |
| GET | `{stack_id}/usage` | Usage |
| GET | `health` | Santé |
| GET | `search` | Recherche |

### 3.14 [`plugins.py`](backend/app/api/v1/plugins.py:45)

**Lecture (auth) :**

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `/plugins/` | Liste |
| GET | `/plugins/{plugin_id}` | Détail |
| GET | `/plugins/{plugin_id}/dependencies` | Dépendances |
| GET | `/plugins/{plugin_id}/hooks/logs` | Logs de hooks (RL 100/min) |
| GET | `/plugins/{plugin_id}/hooks/logs/{log_id}` | Détail d'un log de hook |

**Gestion (superadmin, RL 10-20/min) :**

| Méthode | Route | Notes |
|---------|-------|-------|
| POST | `/plugins/install` | Installation |
| PUT | `/plugins/{id}/update` | Mise à jour |
| PUT | `/plugins/{id}/configure` | Configuration |
| DELETE | `/plugins/{id}/uninstall` | Désinstallation |

### 3.15 [`plugin_registry.py`](backend/app/api/v1/plugin_registry.py:39) — auth, RL 60/min

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `/registry/plugins` | Recherche, cache TTL 300 s — interroge l'index JSON distant (`plugin_registry_url`) |
| GET | `/registry/plugins/{plugin_name}` | Détail d'un plugin du registre |

### 3.16 [`workflows.py`](backend/app/api/v1/workflows.py:17)

| Méthode | Route | Notes |
|---------|-------|-------|
| GET | `/workflows/` | **STUB** : retourne toujours `[]` ([`workflows.py`](backend/app/api/v1/workflows.py:40), commentaire : modèle Workflow à venir) |

### 3.17 WebSocket ([[`websockets.py`](backend/app/api/v1/websockets.py:27)]) — 5 canaux sous `/api/v1/ws`

| Type | Route | Rôle |
|------|-------|------|
| WS | `/ws/` | Canal général |
| WS | `/ws/deployments/{deployment_id}/logs` | Logs de déploiement en direct |
| WS | `/ws/terminal/{container_id}` | Terminal interactif |
| WS | `/ws/docker/containers/{container_id}/logs` | Logs de conteneur en temps réel |
| WS | `/ws/docker/containers/{container_id}/stats` | Statistiques de conteneur en temps réel |

---

## 4. Exécution des déploiements — runners & orchestrateur

### 4.1 Exécution de commandes — [`services/commands.py`](backend/app/services/commands.py)

| Classe | Ligne | Description |
|--------|-------|-------------|
| [`CommandExecutor`](backend/app/services/commands.py:49) | :49 | Protocole commun (`run(command, timeout, require_success) -> CommandResult`) |
| [`LocalCommandExecutor`](backend/app/services/commands.py:76) | :76 | Subprocess asyncio local, support sudo (`sudo -S` avec mot de passe passé par stdin) |
| [`SSHCommandExecutor`](backend/app/services/commands.py:167) | :167 | Exécution distante via asyncssh — le « runner SSH » du projet |

### 4.2 Exécution Docker — [`services/docker_executor.py`](backend/app/services/docker_executor.py) (1018 lignes)

| Classe / fonction | Ligne | Description |
|-------------------|-------|-------------|
| [`DockerExecutorBase`](backend/app/services/docker_executor.py:26) | :26 | ABC : deploy/start/stop/restart/remove/status/logs/volume |
| [`CLIDockerExecutor`](backend/app/services/docker_executor.py:76) | :76 | Via subprocess `docker run` (prioritaire, « meilleure visibilité debug ») |
| [`SocketDockerExecutor`](backend/app/services/docker_executor.py:397) | :397 | Via Docker REST API sur socket Unix (fallback) |
| [`get_docker_executor()`](backend/app/services/docker_executor.py:640) | :640 | Factory `prefer_cli=True` |
| [`DockerExecutor`](backend/app/services/docker_executor.py:680) | :680 | Façade haut niveau (conteneur simple) |
| [`ComposeExecutor`](backend/app/services/docker_executor.py:786) | :786 | Façade haut niveau (Compose) |

### 4.3 Orchestration des déploiements — [`services/deployment_orchestrator.py`](backend/app/services/deployment_orchestrator.py:21)

Orchestrateur asyncio (docstring : « Remplace Celery ») :

- `start_deployment()` : marque `task_started_at`, crée la tâche, la tracke dans `_active_tasks`, callback de finalisation qui notifie le statut terminal via `DeploymentService.update_status` (donc WebSocket) ;
- **retry avec backoff exponentiel** : `MAX_RETRIES=3`, délai initial 60 s, max 600 s (lignes 36-38) ;
- `cancel_deployment()`, `recover_pending_deployments()` (reprise post-crash, appelée au startup).

### 4.4 Tâches de fond — [`tasks/background_tasks.py`](backend/app/tasks/background_tasks.py:24)

[`deploy_stack_async()`](backend/app/tasks/background_tasks.py:24) (615 lignes) : déploiement complet en mode « fallback asyncio » dans le processus backend — charge deployment/stack, rend les variables, exécute via `DockerService`/`DockerComposeService` selon le type de cible, met à jour les statuts et logs.

### 4.5 Résilience — [`core/resilience.py`](backend/app/core/resilience.py)

Implémente `CircuitBreaker` (états CLOSED/OPEN/HALF_OPEN), `RetryPolicy`, `HealthCheck` + `HealthCheckRegistry`.

> ⚠️ **NON CÂBLÉ** : aucune import de ce module dans l'application (vérifié par recherche) — bibliothèque disponible mais inutilisée.

---

## 5. Services métier

~36 fichiers dans [`services/`](backend/app/services).

| Fichier | Ligne | Rôle |
|---------|-------|------|
| [`docker_client_service.py`](backend/app/services/docker_client_service.py:312) | :312 | Client Docker bas niveau (dataclasses ContainerInfo/Detail, ImageInfo, VolumeInfo, NetworkInfo, SystemInfo, PullProgressEvent, ExecResult) + factory [`get_docker_client()`](backend/app/services/docker_client_service.py:1662) (:1662) — accès direct au socket Unix |
| [`docker_service.py`](backend/app/services/docker_service.py:20) | :20 | Gestion des conteneurs simples (via exécuteurs) |
| [`docker_compose_service.py`](backend/app/services/docker_compose_service.py:20) | :20 | Gestion des stacks Compose (via exécuteurs) |
| [`deployment_service.py`](backend/app/services/deployment_service.py:23) | :23 | CRUD + statuts/logs des déploiements |
| [`deployment_events.py`](backend/app/services/deployment_events.py:22) | :22 | Émission d'événements de cycle de vie déploiement sur l'EventBus |
| [`stack_service.py`](backend/app/services/stack_service.py:19) | :19 | CRUD stacks |
| [`stack_loader_service.py`](backend/app/services/stack_loader_service.py:18) | :18 | Parsing YAML |
| [`stack_definitions_loader.py`](backend/app/services/stack_definitions_loader.py:22) | :22 | Chargement auto du répertoire `stacks_definitions/` |
| [`target_service.py`](backend/app/services/target_service.py:30) | :30 | CRUD cibles + `check_all_health()` (utilisée par la boucle périodique) |
| [`target_scanner_service.py`](backend/app/services/target_scanner_service.py:70) | :70 | Scan de capacités des cibles (orchestre commands + socket_clients + parsers) |
| [`target_scan_parsers.py`](backend/app/services/target_scan_parsers.py:29) | :29 | ~20 parseurs de versions/outils (docker, kubectl, kubeadm, k3s, runc, qemu, vagrant…) + construction du payload de capacités normalisé |
| [`socket_clients.py`](backend/app/services/socket_clients.py:38) | :38 | `SocketProbe` (chemins de sockets Unix pour docker/podman/lxd/incus/libvirt/lxc/containerd, modes system/rootless/session), `DockerSocketClient`, `LibvirtSocketClient` (libvirt-python en import défensif optionnel) |
| [`target_access_profile.py`](backend/app/services/target_access_profile.py:21) | :21 | Détection du profil d'accès (root / sudo / sudo_passwordless / limited) |
| [`compute_service.py`](backend/app/services/compute_service.py:58) | :58 | `get_compute_stats` / `get_compute_global` — agrégation de l'inventaire |
| [`container_classifier.py`](backend/app/services/container_classifier.py:61) | :61 | Classification des conteneurs : managés WindFlow (labels) / projets Compose / standalone |
| [`container_builder.py`](backend/app/services/container_builder.py:99) | :99 | Construction des vues (stacks managées, items découverts, standalone, groupes par cible) |
| [`adoption_service.py`](backend/app/services/adoption_service.py:230) | :230 | Adoption de conteneurs découverts (extraction env/volumes/réseaux/ports depuis inspect, masquage des secrets env, génération aperçu Compose) |
| [`terminal_service.py`](backend/app/services/terminal_service.py:56) | :56 | Shells disponibles + sessions exec dans les conteneurs |
| [`user_service.py`](backend/app/services/user_service.py:20) | :20 | CRUD users, hash/mise à jour mot de passe, `get_first_superadmin` (mode dev) |
| [`organization_service.py`](backend/app/services/organization_service.py:54) | :54 | Multi-tenant + génération de slug |
| [`scheduler_service.py`](backend/app/services/scheduler_service.py:20) | :20 | CRUD des tâches planifiées |
| [`plugin_manager_service.py`](backend/app/services/plugin_manager_service.py:27) | :27 | Cycle de vie plugins (install/update/configure/uninstall) |
| [`plugin_manifest_service.py`](backend/app/services/plugin_manifest_service.py:21) | :21 | Validation des manifests |
| [`plugin_registry_service.py`](backend/app/services/plugin_registry_service.py:23) | :23 | Accès au registre distant (aiohttp, cache TTL) |
| [`plugin_dependency_service.py`](backend/app/services/plugin_dependency_service.py:54) | :54 | Vérification des dépendances inter-plugins |
| [`plugin_lifecycle_service.py`](backend/app/services/plugin_lifecycle_service.py:40) | :40 | Exécution des hooks lifecycle |
| [`litellm_service.py`](backend/app/services/litellm_service.py:24) | :24 | IA multi-provider — **simulation, orphelin** (voir [§12](#12-ia--litellm)) |

---

## 6. Base de données & modèles

### 6.1 Connexion & création du schéma — [`database.py`](backend/app/database.py:27)

Classe `Database` :

- moteur async (SQLite `StaticPool` + création du répertoire data ; sinon pool PostgreSQL),
- `session_factory`,
- [`create_tables()`](backend/app/database.py:89) → `Base.metadata.create_all` (ligne 89),
- `seed_tables()` → [`database_seed.py`](backend/app/database_seed.py) (org + admin par défaut),
- `health_check()`.

`get_db` : dépendance FastAPI de session.

> ⚠️ **Aucune migration Alembic** (pas de `backend/alembic/`) : le schéma évolue par `create_all` — **les changements de colonnes sur tables existantes ne sont pas gérés**.

### 6.2 Entités (10 modèles dans [`models/`](backend/app/models))

| Entité | Contenu |
|--------|---------|
| `User` | org FK, superuser, keycloak_id |
| `Organization` | 1-N users/targets/stacks/deployments |
| `Target` | host/port/type, credentials JSON, statut, résultats de scan : platform_info, os_info, access_profile |
| `TargetCapability` | Capacités détectées par cible |
| `Stack` | Définition, variables, visibilité |
| `StackVersion` | Historique de versions |
| [`Deployment`](backend/app/models/deployment.py:34) | FK stack+target+org, statut enum 6 états dont ROLLING_BACK, snapshot config/variables/`rendered_target_parameters`, `task_started_at`/`task_retry_count` pour l'orchestrateur, logs/error |
| `Plugin` | Plugins installés |
| `PluginHookLog` | Logs d'exécution des hooks |
| `ScheduledTask` | Tâches planifiées (cron) |

Conventions respectées : PK en `String(36)` UUID, `created_at/updated_at`, snake_case.

---

## 7. Sécurité — AuthN / AuthZ / RBAC

### 7.1 JWT — [`auth/jwt.py`](backend/app/auth/jwt.py:16)

- python-jose, HS256.
- Access token **15 min**, refresh **7 jours** (config).
- `create_token_pair()`, `decode_access_token()`, `decode_refresh_token()` avec claims `sub/username/organization_id/is_superuser/type`.

### 7.2 Dépendances — [`auth/dependencies.py`](backend/app/auth/dependencies.py:23)

| Dépendance | Comportement |
|-----------|--------------|
| `get_current_user()` | OAuth2 Bearer ; en mode `disable_auth` retourne le premier superadmin (500 s'il n'existe pas) |
| `get_current_active_user()` | Vérifie `is_active` (403) |
| `require_superuser()` | 403 si non superadmin — alias `get_current_superadmin` |
| `get_current_user_ws()` | Auth WebSocket par query param `?token=` — **stricte** : sans token, token invalide/expiré ou utilisateur inactif, le handshake est refusé (`WebSocketException` 1008). Gère `DISABLE_AUTH` (auto-login superadmin). Utilisée par les 3 canaux dédiés (`deployments/logs`, `containers/logs`, `containers/stats`) |
| `authenticate_ws_first_message()` | Auth « JWT au premier message » centralisée (timeout 30 s via `WS_AUTH_TIMEOUT_SECONDS`, close 1008, callback `on_failure` pour l'audit) — utilisée par les canaux général et terminal (STORY-100) |

### 7.3 RBAC réel

- Modèle **binaire** : user actif / superadmin.
- Il n'existe **pas** de rôles viewer/operator ni de `require_role(...)` granulaire.
- [`helper/permissions.py`](backend/app/helper/permissions.py:64) contient un système policies/groups/cron hérité du legacy mais il n'est importé nulle part (**code mort**).

### 7.4 Keycloak SSO

Uniquement un bloc de config ([`config.py`](backend/app/config.py:41)) + champ `keycloak_id` sur `User`. **Aucune implémentation d'OIDC dans le code.**

### 7.5 Mots de passe

passlib (hash + upgrade automatique à la connexion, `verify_and_update_user` utilisé dans login).

### 7.6 Sessions / logout

Logout stateless : pas de blacklist de tokens serveur ([`auth.py`](backend/app/api/v1/auth.py:391)).

---

## 8. WebSocket temps réel

Module [`websocket/`](backend/app/websocket) — documentation interne exhaustive : [`websocket/README.md`](backend/app/websocket/README.md) (601 lignes).

### 8.1 Connection managers — [`websocket/connection_managers.py`](backend/app/websocket/connection_managers.py:27)

- `BroadcastManager` (base),
- `ConnectionManager` (1 connexion par déploiement),
- `UserConnectionManager` (multi-connexions par user),
- instances globales `manager`/`user_manager`.

### 8.2 Broadcasting — [`websocket/broadcasting.py`](backend/app/websocket/broadcasting.py)

`broadcast_deployment_log/status/progress/complete`, `broadcast_to_user`, système de souscription (`subscribe_to_event`/`unsubscribe_from_event`/`subscribe_to_deployment_logs`, `broadcast_to_event_subscribers`).

### 8.3 Event bridge — [`websocket/event_bridge.py`](backend/app/websocket/event_bridge.py:20)

Mappe les `EventType` déploiement → `WebSocketEventType` et re-broadcast ; monté au startup (5 types d'événements).

### 8.4 Handlers

[`terminal.py`](backend/app/websocket/terminal.py) (terminal interactif, rate limit maison 3 sessions/user en mémoire), [`container_logs.py`](backend/app/websocket/container_logs.py), [`container_stats.py`](backend/app/websocket/container_stats.py), [`deployment_logs.py`](backend/app/websocket/deployment_logs.py), [`general.py`](backend/app/websocket/general.py), [`metrics.py`](backend/app/websocket/metrics.py).

### 8.5 Système de plugins WS — [`websocket/plugin.py`](backend/app/websocket/plugin.py)

`WebSocketPlugin`, `WebSocketPluginManager`, `PluginContext` + 4 plugins :

| Plugin | Notes |
|--------|-------|
| `audit_logger` | TODO : persistance DB |
| `deployment_monitor` | — |
| `deployment_notifications` | — |
| `subscription` | — |

---

## 9. Event-driven & tâches de fond

### 9.1 Celery — [`celery_app.py`](backend/app/celery_app.py:19)

- App Celery + Beat schedule :
  - cleanup logs 2h/jour,
  - health-check cibles */5 min,
  - retry déploiements */10 min,
- 3 tâches définies.
- ⚠️ `celery_app` n'est **jamais importé** par [`main.py`](backend/app/main.py) ni par aucun service — il faut le lancer explicitement (`celery -A backend.app.celery_app worker`).
- **En pratique, le backend tourne sur les équivalents asyncio** : boucle de santé dans le lifespan + `DeploymentOrchestrator` + [`background_tasks.py`](backend/app/tasks/background_tasks.py).

### 9.2 EventBus — [`core/events.py`](backend/app/core/events.py:115)

- Pub/sub in-memory (pattern Observer), ~25 `EventType` (déploiement, target, stack, org, user, plugin, système).
- Singleton global `event_bus`.

### 9.3 Redis Streams — TODO intégral

[`_init_redis`](backend/app/core/events.py:144), `_publish_to_redis`, `_append_to_redis`, `get_events` (replay) sont tous des **stubs commentés** (lignes 144, 227, 255, 298, 321, 376). `EventStore` (event sourcing) est également un stub in-memory.

### 9.4 Consommateurs

L'event bridge (WebSocket) est le **seul handler réel** enregistré sur le bus.

---

## 10. Core transversal, middleware, helper, enums

### 10.1 Core

| Fichier | Contenu | État |
|---------|---------|------|
| [`core/exceptions.py`](backend/app/core/exceptions.py:10) | `WindFlowException` (base, avec `details`) et `CommandExecutionError` — seules 2 exceptions | Beaucoup d'endpoints lèvent encore des `HTTPException` brutes |
| [`core/abstractions.py`](backend/app/core/abstractions.py:13) | ABC `DatabaseManager`, `CacheManager` | Contrats non consommés par [`database.py`](backend/app/database.py) (concret) |
| [`core/rate_limit.py`](backend/app/core/rate_limit.py:18) | `conditional_rate_limiter()` — no-op si Redis absent ; alias strict/moderate/relaxed (5/30/100 par min) | Sans `RATE_LIMIT_STORAGE_URL`, tous les limiteurs sont des no-op ([`rate_limit.py`](backend/app/core/rate_limit.py:43)) |
| [`core/resilience.py`](backend/app/core/resilience.py) | CircuitBreaker/RetryPolicy/HealthCheck | Non câblé (voir [§4.5](#45-résilience--coreresiliencepy)) |

### 10.2 Helper (~12 fichiers)

[`template_renderer.py`](backend/app/helper/template_renderer.py) + [`jinja_functions.py`](backend/app/helper/jinja_functions.py) (rendu des variables de stacks), [`security.py`](backend/app/helper/security.py), [`email.py`](backend/app/helper/email.py), [`compute_helpers.py`](backend/app/helper/compute_helpers.py), générateurs de noms ([`animalname.py`](backend/app/helper/animalname.py), [`cosmicname.py`](backend/app/helper/cosmicname.py), [`mythologyname.py`](backend/app/helper/mythologyname.py)), [`croniter.py`](backend/app/helper/croniter.py) (copie vendored, seul consommateur potentiel = [`permissions.py`](backend/app/helper/permissions.py) mort).

### 10.3 Enums — [`enums/target.py`](backend/app/enums/target.py:10)

- `TargetType` : docker, docker_compose, docker_swarm, kubernetes, vm, physical ;
- `TargetStatus` ;
- `SSHAuthMethod` : local / password / ssh_key ;
- `AccessLevel` ;
- `CapabilityType` (~25 capacités : virtualisation, conteneurisation, runtimes OCI…).

---

## 11. Configuration

[`config.py`](backend/app/config.py:15) — `Settings` (pydantic-settings, `.env`, `extra="ignore"`). Grandes sections :

| Section | Contenu |
|---------|---------|
| **App** | Nom, version, debug, environment (+ propriétés `is_production`) |
| **DB** | `database_url` SQLite/aiosqlite par défaut, pool (5/10/3600 s) pour PostgreSQL |
| **JWT** | Secret (**valeur dev par défaut**), HS256, 15 min / 7 j |
| **Flags optionnels** | `keycloak_enabled=False`, `vault_enabled=False`, `litellm_enabled=False` (+ clés OpenAI/Anthropic, URL Ollama), `prometheus_enabled=True` (**aucune instrumentation Prometheus trouvée dans le code backend**), `disable_auth=False` ([`config.py`](backend/app/config.py:254), marqué DANGER) |
| **API/CORS/CSP/HSTS** | Origines/methods/headers parsables JSON ou CSV, CSP détaillée ([`build_csp_header()`](backend/app/config.py:267)), HSTS off par défaut |
| **Rate limiting** | enabled + `rate_limit_storage_url` (Redis) + default `100/minute` |
| **Performance** | Timing middleware, `slow_request_threshold=1.0`, correlation ID |
| **Seeding** | Email/username/password admin par défaut (`changeme123`), org par défaut |
| **Stacks** | `stacks_definitions_path`, `auto_load_stack_definitions=True`, stratégie `update_if_newer` |
| **Plugins** | URL du registre officiel, TTL cache 300 s, timeout 10 s, répertoire base des hooks |
| **Logging** | Niveau + format json/text |

---

## 12. IA / LiteLLM

Un seul module : [`litellm_service.py`](backend/app/services/litellm_service.py:24) (355 lignes).

- `LLMProvider` : openai / claude / ollama ; méthodes `generate_docker_compose()`, `optimize_resources()`, diagnostic d'erreurs, suggestions.
- **Tout est simulé** : [`_call_llm()`](backend/app/services/litellm_service.py:285) retourne des réponses en dur — `TODO: Intégrer litellm.completion() quand la dépendance sera ajoutée` (ligne 110) ; la dépendance `litellm` n'est pas dans le code.
- **Service orphelin** : aucun router ni service n'importe `LiteLLMService` — aucune endpoint IA exposée.

---

## 13. Tests & couverture

### 13.1 Volumétrie

~66 fichiers : ~52 unitaires, 7 intégration.

### 13.2 Fixtures clés — [`tests/conftest.py`](backend/tests/conftest.py:42)

Engine SQLite in-memory par fonction, `db_session`, `test_organization`, `test_user`, client HTTP via `httpx.AsyncClient` + `ASGITransport` (override `get_db`).

### 13.3 Couverture par domaine

| Domaine | ~Fichiers | Qualité |
|---------|-----------|---------|
| Docker (services + API) | 19 | Très bonne (create, recreate, networks, shells, stats, pause, auth security, pagination, import/export images, terminal) |
| Plugins (API + services) | 10 | Bonne (hooks, registry, manifests, dépendances, lifecycle, manager) |
| Stacks (API + actions) | 9 | Bonne (variables rendering, archive, duplicate, stats, actions) |
| Compute | 3 | Bonne (API, helpers, service) |
| Targets/scanner | 3 | Correcte (scanner, parsers via compute_helpers, health check) |
| Deployments (service) | 3 | Correcte (service, rendering, API en intégration) |
| Auth | 2 (1 unit dev-mode + 1 integration) | Moyenne (register/refresh/RBAC peu couverts) |
| Middleware/sécurité | 6 intégrations | Bonne (headers, correlation, timing, rate limiting, OpenAPI) |

### 13.4 Zéros / non couverts

Organizations (API), users (API), **websocket (aucun test)**, schedules, discovery/adoption (sauf 1 fichier [`test_adoption_service.py`](backend/tests/unit/test_services/test_adoption_service.py)), import_export, workflows, stats, compute API partiel.

---

## 14. Implémenté vs annoncé — zones mortes & lacunes

### 14.1 Écarts entre implémentation réelle et fonctionnalités annoncées

| Annoncé / squelette | État réel dans le code |
|--------------------|------------------------|
| Celery non intégré au runtime | [`celery_app.py`](backend/app/celery_app.py) complet mais jamais importé ; le runtime réel = asyncio (orchestrateur + boucle de santé + [`background_tasks.py`](backend/app/tasks/background_tasks.py)) |
| Redis Streams non implémenté | EventBus/EventStore in-memory ; toutes les méthodes Redis = TODO commentés ([`events.py`](backend/app/core/events.py:227)) |
| Résilience non câblée | CircuitBreaker/RetryPolicy/HealthCheck existent mais 0 import dans l'app |
| IA simulée et orpheline | [`litellm_service.py`](backend/app/services/litellm_service.py) : réponses en dur, non référencé |
| Pas de RBAC granulaire | Seul `require_superuser` ; système policies legacy + croniter = code mort non importé |
| Workflows = stub | [`workflows.py`](backend/app/api/v1/workflows.py:40) retourne `[]` |
| Pas d'Alembic | Schéma par `create_all` ; aucun fichier de migration |
| Keycloak/Vault/Prometheus = flags sans implémentation | Config + `keycloak_id` en base, rien d'autre ; `prometheus_enabled=True` sans métriques instrumentées |

### 14.2 Lacunes & remarques de sécurité

| Constat | Détail |
|---------|--------|
| ~~WS auth tolérante~~ **résolu (STORY-100)** | `get_current_user_ws()` est désormais stricte (refus handshake 1008) et câblée sur les 3 canaux dédiés ; auth « premier message » centralisée via `authenticate_ws_first_message()` sur général/terminal ; tests `test_ws_auth.py` (42 cas) |
| Rate limiting effectif conditionnel | Sans `RATE_LIMIT_STORAGE_URL`, tous les limiteurs sont des no-op ([`rate_limit.py`](backend/app/core/rate_limit.py:43)) |
| Logout stateless | Pas de blacklist de tokens serveur ([`auth.py`](backend/app/api/v1/auth.py:391)) |

### 14.3 Divers

| Constat | Détail |
|---------|--------|
| Print de debug au chargement | [`main.py`](backend/app/main.py:12) |
| Duplication d'endpoints | `/users/me` vs `/auth/me` |
| TODOs bénins dans les plugins WS | Ex. `audit_logger` (persistance DB) |
| Secrets dev par défaut | `jwt_secret`, admin `changeme123` |

### 14.4 Points solides réels

| Point fort | Détail |
|-----------|--------|
| Scan de cibles | Très complet (~20 parseurs, probes sockets, profils d'accès) |
| Module Docker | Riche (40 endpoints, promote, adoption) |
| WebSocket | Modulaire et documenté ([`websocket/README.md`](backend/app/websocket/README.md), 601 lignes) |
| OpenAPI | Soignée (Scalar/Swagger/ReDoc, description riche) |
| Recovery des déploiements | Reprise des déploiements orphelins au démarrage (`recover_pending_deployments()`) |

---

## 15. Synthèse

Le backend est un modular monolith FastAPI fonctionnel centré sur :

- **auth JWT simple** (binaire user/superadmin) ;
- **gestion multi-tenant** (organisations / utilisateurs / cibles / stacks) ;
- **déploiement Docker/Compose** via exécuteurs CLI/socket avec orchestration asyncio (retry/recovery) ;
- **scan de cibles poussé** ;
- **WebSocket temps réel modulaire** ;
- **système de plugins complet**.

Les briques « enterprise » annoncées — Celery, Redis Streams, circuit breaker, RBAC fin, IA LiteLLM, Keycloak, Vault, Prometheus, Alembic — existent en squelette, en flag ou en code mort : **aucune n'est réellement active dans le runtime**.
