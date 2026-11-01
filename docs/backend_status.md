# Statut fonctionnel du Backend WindFlow

> **Date du document :** 1ᵉʳ novembre 2026 (édition post-remédiation)
>
> **Périmètre :** backend uniquement (`backend/`), analyse du code source uniquement — hors documentation, frontend et CLI.
>
> **Avertissement :** ce document reflète l'état du code **au moment de l'analyse** (analyse en lecture seule). Il décrit ce qui existe réellement dans le code, chaque affirmation ayant été re-vérifiée par inspection (grep / lecture des sources) lors de cette édition. Toute évolution ultérieure du code peut rendre certaines sections obsolètes.
>
> **Lié au plan de remédiation :** cette édition fait suite à l'exécution complète du plan [`backend_remediation_plan.md`](backend_remediation_plan.md) — vagues P0→P3 (EPIC-011 à EPIC-014, stories STORY-100 → STORY-253). Les constats de l'édition du 30/08/2026 restent visibles en [§14](#14-implémenté-vs-annoncé--zones-mortes--lacunes), barrés et marqués « résolu (STORY-XXX) » lorsqu'ils ont été traités.

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

Le backend WindFlow est un **modular monolith FastAPI** (~209 fichiers Python sous `app/`, ~462 avec les tests) centré sur : authentification JWT + RBAC granulaire 4 rôles, gestion multi-tenant (organisations / utilisateurs / hosts / stacks), déploiement Docker/Compose via des exécuteurs CLI/socket avec orchestration asyncio (retry/recovery), scan de hosts poussé, scheduler de tâches à moteur runtime, bus d'événements canonique, WebSocket temps réel modulaire, système de plugins complet (install réel, gates, routes dynamiques) et observabilité Prometheus effective.

```
backend/
├── app/                    (~209 fichiers Python)
│   ├── main.py, config.py, database.py, database_seed.py
│   ├── alembic/            → 13 migrations (baseline 2026_09_07 → 1671_deployment_events)
│   ├── api/v1/             → 19 routers + sous-packages admin/ (2) et hosts/ (6) (~25 fichiers)
│   ├── auth/               → 4 fichiers (jwt, dependencies, rbac, __init__)
│   ├── core/               → 10 fichiers (events, exceptions, resilience, rate_limit,
│   │                         abstractions, cache, metrics, secret_manager,
│   │                         bruteforce_protection…)
│   ├── enums/              → 4 fichiers (host, target, rbac, workload)
│   ├── helper/             → ~13 fichiers (noms générés, croniter vendored, jinja,
│   │                         template_renderer, security, pagination…)
│   ├── middleware/         → 6 middlewares + README
│   ├── models/             → 19 entités ORM
│   ├── schemas/            → 30 fichiers Pydantic
│   ├── services/           → 50 services métier + package workloads/ (adapters)
│   ├── tasks/              → 1 fichier (background_tasks.py)
│   └── websocket/          → ~16 modules + 4 plugins
└── tests/                  → ~225 fichiers de test (conftest + 204 unit + 21 integration)
```

**Point majeur résolu :** le dossier [`backend/alembic/`](../backend/alembic) existe désormais — **13 migrations** (baseline `2026_09_07_baseline_baseline_schema.py` → `1671_deployment_events_table.py`), et le schéma est appliqué par `alembic upgrade head` au démarrage (STORY-120.2) — plus aucun `create_all` nu (résolu, STORY-120). `celery_app.py` a été **purgé** (STORY-130.2, garde-fou [`test_no_celery_residue.py`](../backend/tests/unit/test_no_celery_residue.py)).

---

## 2. Architecture & runtime

### 2.1 Point d'entrée & montage — [`main.py`](../backend/app/main.py)

- Application FastAPI (titre/version depuis les settings, description OpenAPI riche, `servers` construits dynamiquement via `build_server_urls()` dans [`config.py`](../backend/app/config.py)).
- **Documentation API :** Scalar sur `/docs`, Swagger UI sur `/swagger`, ReDoc sur `/redoc`, OpenAPI sur `/openapi.json`.
- **Endpoints racine :** `GET /` (infos API), `GET /health` (vérifie DB + Redis si configuré, 503 si DB down).
- **Exception handlers** Pydantic/FastAPI → 422 avec `correlation_id`, plus handlers d'exceptions métier typées (STORY-127).

### 2.2 Lifespan (main.py:77)

**Startup :**

1. `db.connect()` + [`db.run_migrations()`](../backend/app/database.py:132) (`alembic upgrade head`, STORY-120.2) + `db.seed_tables()` (seed admin/org par défaut + auto-détection optionnelle du host local, STORY-166.5) ;
2. [`init_event_bus()`](../backend/app/core/events.py) — bus canonique (STORY-162) : `InMemoryEventBus` par défaut, `RedisPubSubEventBus` si `cache_url` configuré (canal `windflow:events`) ;
3. [`setup_event_bridge()`](../backend/app/websocket/event_bridge.py) — pont bus → WebSocket (abonné au bus actif) ;
4. Init `FastAPILimiter` (Redis) si `rate_limit_enabled` **ET** `rate_limit_storage_url` — sinon **fallback mémoire process-local effectif** (STORY-102, plus de no-op silencieux) ;
5. `DeploymentOrchestrator.recover_pending_deployments()` — reprise des déploiements orphelins au redémarrage ;
6. **Boucles périodiques** (tâches lifespan, arbitrage F1 — runtime asyncio unique) :
   - health-check des hosts toutes les 5 min ([`_periodic_health_check()`](../backend/app/main.py:250)),
   - purge des refresh tokens expirés ([`_periodic_refresh_token_purge()`](../backend/app/main.py:278), STORY-123),
   - purge des audit logs ([`_periodic_audit_purge()`](../backend/app/main.py:314), STORY-125.3),
   - purge des exécutions scheduler ([`_periodic_executions_purge()`](../backend/app/main.py:359), STORY-161),
   - purge des deployment events ([`_periodic_deployment_events_purge()`](../backend/app/main.py:413), STORY-167),
   - **SchedulerEngine** ([`main.py:447+`](../backend/app/main.py:447)) — moteur cron asyncio (STORY-160.2) : évalue les crons via croniter vendored, verrou anti-chevauchement process-local, orphelins récupérés au démarrage, branché sur `DatabaseExecutionStore` (STORY-161), triggers événement `SchedulerEventTriggers` (STORY-160.3). ⚠️ Single-worker assumé (verrou process-local).

**Shutdown :** annulation des tâches périodiques et du moteur scheduler, fermeture du bus et du cache (`shutdown_cache()`, STORY-168), fermeture du rate limiter, `db.disconnect()`.

### 2.3 Middlewares — ordre critique (documenté dans [`middleware/README.md`](../backend/app/middleware/README.md))

| # | Middleware | Rôle |
|---|-----------|------|
| 1 | CORS | Conditionné par `cors_enabled` |
| 2 | Security Headers | CSP construite par `build_csp_header()`, HSTS, X-Frame-Options |
| 3 | Timing | Mesure `X-Process-Time`, log des requêtes lentes > `slow_request_threshold`, **instrumentation Prometheus HTTP** (STORY-172 : chemins normalisés UUID→`{id}`/num→`{n}`, jamais de query string, scrape exclu) |
| 4 | Correlation ID | Header `X-Correlation-ID` |
| 5 | Logging | Logging structuré |
| 6 | Error Handler | Dernier, catch-all |

### 2.4 Montage des routers ([`api/v1/__init__.py`](../backend/app/api/v1/__init__.py))

`api_router = APIRouter(prefix="/api/v1")`, 19 sous-routers :

`/auth`, `/users`, `/organizations`, **`/hosts` (canonique, 6 sous-modules)** + **alias `/targets` déprécié** ([`targets_legacy.py`](../backend/app/api/v1/targets_legacy.py), header `Deprecation` + `Sunset` — STORY-166.2/166.6), `/ssh-keys` (STORY-131.2), `/stacks`, `/deployments`, `/ws`, `stats` (sans préfixe), `import-export`, `/schedules`, `/admin` (préfixe porté par le router), `/docker`, `/compute`, `/discovery`, `/plugins`, `/registry`, `/system` (STORY-129), `/metrics` (STORY-172).

~~`/workflows`~~ — router supprimé (STORY-250.1, garde-fou OpenAPI sans `/workflows`).

---

## 3. API REST — inventaire exhaustif

> ~140 endpoints REST + 8 canaux WebSocket. Enveloppes API `{success, data, error}` par défaut (`api_envelope_enabled=True`, STORY-126/128), pagination `?page&per_page` avec enveloppe `{data, pagination}` (STORY-128).
>
> **Rôles :** RBAC granulaire via `require_role("viewer"|"operator"|"admin"|"super_admin")` et alias — ~174 usages dans les routers (STORY-121/122) ; canaux WS protégés par `get_current_user_ws` + `ensure_role_ws` (STORY-122.6).
> **RL** = rate limiting conditionnel, fallback mémoire effectif sans Redis (STORY-102).

### 3.1 [`auth.py`](../backend/app/api/v1/auth.py)

| Méthode | Route | Accès | Notes |
|---------|-------|-------|-------|
| POST | `/auth/login` | Public, RL 5/min | Login username OU email, JWT + refresh **persistés** ; protection brute-force 5 échecs/10 min → lockout 5 min (STORY-104) ; re-hash Argon2id automatique au login (STORY-130.1) |
| POST | `/auth/refresh` | Public, RL 10/min | **Rotation** des refresh tokens opaques `wf_rt_` révocables (STORY-123) |
| POST | `/auth/logout` | auth, RL 20/min | **Révoque** le refresh token serveur (STORY-123) — plus stateless |
| POST | `/auth/register` | Public | Inscription + auto-login (201) |
| GET | `/auth/me` | auth | ⚠️ **Déprécié** (STORY-250.2) : headers `Deprecation: true` + `Sunset: 2027-05-31`, OpenAPI `deprecated: true` — utiliser `/users/me` |
| PUT | `/auth/password` | auth | Changement de mot de passe (STORY-129) |
| GET | `/auth/api-keys` | auth | Liste des clés API de l'utilisateur (STORY-124) |
| POST | `/auth/api-keys` | auth | Création clé `wf_ak_` (STORY-124) |
| DELETE | `/auth/api-keys/{key_id}` | auth | Révocation (STORY-124) |

### 3.2 [`users.py`](../backend/app/api/v1/users.py) — CRUD + bulk

`GET /users/` (paginé `page/per_page`), `GET /users/me` (canonical), `GET /users/{user_id}`, `POST /users/`, `PUT /users/{user_id}`, `DELETE /users/{user_id}`, `POST /users/bulk/delete` (admin), `POST /users/bulk/assign-organization` (admin).

### 3.3 [`organizations.py`](../backend/app/api/v1/organizations.py)

CRUD + bulk delete + **gestion des membres** `user_organizations` (STORY-121 : liste/ajout/modification de rôle/retrait des membres).

### 3.4 [`hosts/`](../backend/app/api/v1/hosts) — 6 sous-modules (STORY-166.2)

**[`crud.py`](../backend/app/api/v1/hosts/crud.py)** : `GET/POST /hosts/`, `GET/PUT/DELETE /hosts/{host_id}` — paginé.

**[`connectivity.py`](../backend/app/api/v1/hosts/connectivity.py)** : `POST /hosts/test-reachability`, `POST /hosts/test-connection`.

**[`capabilities.py`](../backend/app/api/v1/hosts/capabilities.py)** : `POST /hosts/{host_id}/health-check`, `GET .../capabilities`, `GET .../capabilities/{type}`, `GET .../capabilities/virtualization`.

**[`scanning.py`](../backend/app/api/v1/hosts/scanning.py)** : `POST /hosts/discover`, `POST /hosts/{host_id}/scan`.

**[`fingerprints.py`](../backend/app/api/v1/hosts/fingerprints.py)** (STORY-131) : `GET /hosts/{host_id}/ssh-fingerprints`, `POST .../ssh-fingerprints/accept` (TOFU), `DELETE .../ssh-fingerprints/{fingerprint_id}`.

**[`helpers.py`](../backend/app/api/v1/hosts/helpers.py)** : dépendances partagées.

L'alias [`targets_legacy.py`](../backend/app/api/v1/targets_legacy.py) réexpose l'ancienne surface `/targets` avec headers `Deprecation`/`Sunset` (**Sunset indicatif 2027-01-01**, STORY-166.2).

### 3.5 [`stacks.py`](../backend/app/api/v1/stacks.py) — 15 endpoints

CRUD + `regenerate-variable/{name}`, versions (liste/création/restore), actions `start/stop/redeploy/duplicate/archive/unarchive` — validation unifiée `StackDefinition` avec bornes `minimum`/`maximum` (STORY-171).

### 3.6 [`deployments.py`](../backend/app/api/v1/deployments.py) — 9 endpoints

CRUD + `POST /deployments` (lancement orchestrateur), `retry`, `cancel`, `GET .../logs`, **`GET /deployments/{id}/events`** (événements structurés paginés, STORY-167).

### 3.7 [`docker.py`](../backend/app/api/v1/docker.py) — 35 endpoints

Conteneurs (CRUD, start/stop/restart/pause/unpause, batch start/stop, **recreate sécurisé** avec rebase par valeur + rollback + secrets masqués `***` — STORY-174.2, restart-policy, resources, rename, networks connect/disconnect, promote, shells, stats, top, logs), images (liste/détail/pull/delete/load/save), volumes, réseaux, système (info/version/ping).

### 3.8 [`compute.py`](../backend/app/api/v1/compute.py) — 7 endpoints (STORY-173)

`GET /compute/stats`, `GET /compute/global`, **`GET /compute/browse`** (inventaire aplati paginé/filtrable), `GET /compute/volumes`, `GET /compute/volumes/{name}`, `GET /compute/volumes/{name}/browse` (conteneur éphémère durci busybox ro), **`POST /compute/prune`** (superadmin + `confirm` + `dry_run` + audit `compute.prune`). Mapping `/compute`↔`/docker` documenté ([`COMPUTE-DOCKER-MAPPING.md`](technical_specs/COMPUTE-DOCKER-MAPPING.md)).

### 3.9 [`discovery.py`](../backend/app/api/v1/discovery.py)

`GET /discovery/{item_type}/{item_id}/adoption-data` (secrets env masqués), `POST /discovery/adopt`.

### 3.10 [`stats.py`](../backend/app/api/v1/stats.py)

`GET /stats/dashboard`, `GET /stats/stacks/{stack_id}`.

### 3.11 [`import_export.py`](../backend/app/api/v1/import_export.py)

`GET /stacks/{stack_id}/export`, `POST /stacks/import`.

### 3.12 [`schedules.py`](../backend/app/api/v1/schedules.py) — API v2 (STORY-160.1/161)

`GET/POST /schedules`, `GET/PUT/DELETE /schedules/{task_id}`, `POST .../toggle`, **`GET /schedules/executions`** (paginé, filtres), `GET /schedules/executions/{execution_id}`, `GET /schedules/{task_id}/executions`, **`POST /schedules/{task_id}/run`** (run manuel 202).

### 3.13 [`admin/`](../backend/app/api/v1/admin) — superadmin

**[`stacks_management.py`](../backend/app/api/v1/admin/stacks_management.py)** (15 endpoints sur `/admin/stacks-management`) : definitions, validate, import, imported, sync/status, sync/auto, export, export/bulk, toggle-visibility, duplicate, delete, stats/overview, usage, health, search.

**[`audit.py`](../backend/app/api/v1/admin/audit.py)** (STORY-125.3) : `GET /admin/audit` — consultation paginée de l'audit trail.

### 3.14 [`plugins.py`](../backend/app/api/v1/plugins.py) — 9 endpoints

Lecture : liste, détail, dependencies, hooks/logs (RL). Gestion (admin, RL) : **install réel** (STORY-169 : package sécurisé, hooks lifecycle, `docker compose up`, rollback), update, **configure** (valeurs password chiffrées, STORY-169.4), uninstall. **Routes dynamiques** `/api/v1/plugins/{name}/…` montées/démontées à l'installation avec RBAC core (STORY-170.1).

### 3.15 [`plugin_registry.py`](../backend/app/api/v1/plugin_registry.py)

`GET /registry/plugins` (cache TTL 300 s via cache unifié, stale-while-error), `GET /registry/plugins/{plugin_name}`.

### 3.16 [`system.py`](../backend/app/api/v1/system.py) (STORY-129)

`GET /system/health` (alias santé), **`GET /system/ready`** — readiness **sans auth** (sondes).

### 3.17 [`metrics.py`](../backend/app/api/v1/metrics.py) (STORY-172)

`GET /metrics` — exposition Prometheus **sans auth** (scrape interne), format texte, jamais enveloppé, 404 si `prometheus_enabled=False`. Séries `windflow_*` : HTTP, déploiements ok/ko, scheduler, 14 séries `windflow_websocket_*`, `windflow_circuit_breaker_state/failures_total` (STORY-251).

### 3.18 [`ssh_keys.py`](../backend/app/api/v1/ssh_keys.py) (STORY-131.2)

`GET /ssh-keys/generate`, `POST /ssh-keys/import`, `GET/PUT/DELETE /ssh-keys/{key_id}` — admin.

### 3.19 WebSocket — 8 canaux sous /api/v1/ws

| Type | Route | Rôle |
|------|-------|------|
| WS | `/ws/` | Canal général (auth premier message) |
| WS | `/ws/deployments/{deployment_id}/logs` | Logs de déploiement en direct |
| WS | `/ws/terminal/{container_id}` | Terminal interactif |
| WS | `/ws/docker/containers/{container_id}/logs` | Logs de conteneur en temps réel |
| WS | `/ws/docker/containers/{container_id}/stats` | Statistiques de conteneur en temps réel |
| WS | `/ws/ssh/{host_id}` | Session SSH avec TOFU strict (STORY-164.2) |
| WS | `/ws/journal/{host_id}` | Journal système host (STORY-164.2) |
| WS | `/ws/batch/{batch_id}` | Progression batch (STORY-164.2) |

---

## 4. Exécution des déploiements — runners & orchestrateur

### 4.1 Exécution de commandes — [`services/commands.py`](../backend/app/services/commands.py)

`CommandExecutor` (protocole), `LocalCommandExecutor` (subprocess asyncio, sudo), `SSHCommandExecutor` (asyncssh — runner SSH, transport protégé par circuit breaker `ssh:{uuid}` STORY-251).

### 4.2 Exécution Docker — [`services/docker_executor.py`](../backend/app/services/docker_executor.py)

`DockerExecutorBase` (ABC), `CLIDockerExecutor` (subprocess `docker run`, prioritaire), `SocketDockerExecutor` (API REST socket), `get_docker_executor()`, `DockerExecutor` (façade conteneur), `ComposeExecutor` (façade Compose) — appels Docker **enveloppés par le garde circuit breaker** [`workloads/_circuit_guard.py`](../backend/app/services/workloads/_circuit_guard.py) (STORY-251).

### 4.3 Socle `WorkloadAdapter` — [`services/workloads/`](../backend/app/services/workloads) (STORY-174)

[`base.py`](../backend/app/services/workloads/base.py) : enum `WorkloadFamily`, 7 schémas, ABC `WorkloadAdapter`/`AppAdapter`, catalogues ContextualActions déclaratifs. [`docker_container.py`](../backend/app/services/workloads/docker_container.py) et [`compose_stack.py`](../backend/app/services/workloads/compose_stack.py) **enveloppent** les services/exécuteurs existants (zéro duplication) ; factory `get_app_adapter`. Le chemin `deploy_stack_async` passe par l'adapter sur les 2 branches (gates STORY-170.2 et jalons STORY-163 inchangés). **Recreate sécurisé** (STORY-174.2) : capture image, renommage `-old`, rebase par valeur, rollback automatique, secrets masqués `***`.

### 4.4 Orchestration des déploiements — [`services/deployment_orchestrator.py`](../backend/app/services/deployment_orchestrator.py)

Orchestrateur asyncio : `start_deployment()` (tracking, callback de finalisation via `DeploymentService.update_status` → WS + métriques + events), retry backoff exponentiel (3 essais, 60→600 s), `cancel_deployment()`, `recover_pending_deployments()`.

### 4.5 Tâches de fond — [`tasks/background_tasks.py`](../backend/app/tasks/background_tasks.py)

[`deploy_stack_async()`](../backend/app/tasks/background_tasks.py) : déploiement complet dans le processus backend — chargement, rendu des variables, exécution via **l'adapter WorkloadAdapter** (STORY-174.1), mise à jour statuts/logs/events.

### 4.6 Résilience — [`core/resilience.py`](../backend/app/core/resilience.py)

`CircuitBreaker` (états CLOSED/OPEN/HALF_OPEN, horloge injectable, `CircuitBreakerRegistry` avec registres `docker_engine`/`plugin_registry`/`ssh:{uuid}`, exception typée `CircuitBreakerOpenError`) et `RetryPolicy` — **câblés** (STORY-251) : settings `circuit_breaker_*`, séries `windflow_circuit_breaker_*`, alerte `WindflowCircuitBreakerOpen`. ~~`HealthCheck`/`HealthCheckRegistry`~~ purgés (STORY-250.1).

> ⚠️ Divergence documentée (STORY-251) : 3 sites SSH « ad hoc » (chemins sans UUID de host) ne sont pas câblés au circuit breaker.

---

## 5. Services métier

50 services dans [`services/`](../backend/app/services) (+ package [`workloads/`](../backend/app/services/workloads)). Inventaire par famille :

| Famille | Services |
|---------|----------|
| Docker/compute | [`docker_client_service.py`](../backend/app/services/docker_client_service.py) (client bas niveau + factory), `docker_service.py`, `docker_compose_service.py`, `compute_service.py` (stats/global/**browse**/volumes/prune — STORY-173), `volume_browser_service.py`, `container_classifier.py`, `container_builder.py`, `adoption_service.py`, `terminal_service.py` |
| Déploiements | `deployment_service.py` (CRUD + statuts/logs + métriques + double écriture events), `deployment_events.py` (émission bus), [`deployment_event_store.py`](../backend/app/services/deployment_event_store.py) (STORY-167 : append/liste paginée/purge, `data` assaini), `deployment_orchestrator.py` |
| Hosts | `host_service.py`, `host_scanner_service.py`, `host_scan_parsers.py` (~20 parseurs), `host_access_profile.py`, `socket_clients.py`, `ssh_connection.py` (TOFU), `ssh_key_service.py` (STORY-131) |
| Stacks | `stack_service.py`, `stack_loader_service.py` (validation unifiée STORY-171), `stack_definitions_loader.py` |
| Scheduler | `scheduler_service.py` (CRUD), [`scheduler_engine.py`](../backend/app/services/scheduler_engine.py) (STORY-160.2 : moteur asyncio, verrous, timeout, orphelins, fuseaux IANA), `scheduler_actions.py` (STORY-160.3 : `host.scan`, `compute.docker.prune`, triggers), `scheduler_execution_store.py` (STORY-161), `action_registry.py`, `scheduler_event_triggers.py` |
| Plugins | `plugin_manager_service.py` (INSTALL réel + rollback STORY-169.3), `plugin_package_service.py` (download/checksum/anti-traversal STORY-169.1), `plugin_validation_service.py` (STORY-169.2), `plugin_lifecycle_service.py`, `plugin_hooks_service.py` (SDK `@on_event` STORY-163), [`plugin_gate_service.py`](../backend/app/services/plugin_gate_service.py) (gates pre-deploy STORY-170.2), [`plugin_api_router_service.py`](../backend/app/services/plugin_api_router_service.py) (routes dynamiques STORY-170.1), `plugin_manifest_service.py`, `plugin_registry_service.py`, `plugin_dependency_service.py` |
| Auth/org | `user_service.py`, `organization_service.py`, `user_organization_service.py` (STORY-121), `authorization_service.py`, `refresh_token_service.py` (STORY-123), `api_key_service.py` (STORY-124), `audit_service.py` (STORY-125) |
| Système | `system_service.py` (STORY-129), `commands.py`, `litellm_service.py` (cf. [§12](#12-ia--litellm)) |

---

## 6. Base de données & modèles

### 6.1 Connexion & migrations — [`database.py`](../backend/app/database.py)

Classe `Database` : moteur async (SQLite `StaticPool` / PostgreSQL), `session_factory`, **[`run_migrations()`](../backend/app/database.py:132) = `alembic upgrade head`** (STORY-120.2), `seed_tables()` (org + admin par défaut + host local optionnel — STORY-166.5), `health_check()`. `get_db` : dépendance FastAPI.

> ✅ **Résolu (STORY-120)** : ~~aucune migration Alembic, schéma par `create_all`~~ → 13 migrations dans [`alembic/versions/`](../backend/alembic/versions), appliquées au démarrage ; tests d'intégration round-trip upgrade/downgrade (STORY-120.3).

### 6.2 Entités (19 modèles dans [`models/`](../backend/app/models))

| Entité | Contenu |
|--------|---------|
| `User` | keycloak_id, association N-N aux organisations |
| `Organization` | 1-N hosts/stacks/deployments |
| [`UserOrganization`](../backend/app/models/user_organization.py) | Association user↔org avec rôle (STORY-121) |
| `Host` (ex-`Target`, STORY-166.1) | host/port/type, **credentials chiffrés** (SecretManager, STORY-103), statut `HostStatus`, `origin`, `environment_id`, scans : platform_info/os_info/access_profile/hardware_info/installed_engines |
| `HostCapability` | Capacités détectées par host |
| `Environment` | Environnements par org (STORY-166.4) |
| `Stack` | Définition, variables, visibilité, `origin`/`git_url`/`environment_id` |
| `StackVersion` | Historique de versions |
| `Deployment` | FK stack+host+org, statut enum (dont ROLLING_BACK), snapshot config/variables, `task_started_at`/`task_retry_count`, logs/error |
| [`DeploymentEvent`](../backend/app/models/deployment_event.py) | Événements structurés (STORY-167) |
| `ScheduledTask` | Tâches planifiées spec 17 (STORY-160.1) |
| `ScheduledTaskExecution` | Historique des exécutions (STORY-161) |
| [`RefreshToken`](../backend/app/models/refresh_token.py) | Tokens opaques révocables (STORY-123) |
| [`APIKey`](../backend/app/models/api_key.py) | Clés `wf_ak_` (STORY-124) |
| [`AuditLog`](../backend/app/models/audit_log.py) | Audit trail (STORY-125) |
| [`SSHKey`](../backend/app/models/ssh_key.py) / [`HostSSHFingerprint`](../backend/app/models/host_ssh_fingerprint.py) | Clés SSH + empreintes TOFU (STORY-131) |
| `Plugin` / `PluginHookLog` | Plugins installés + logs de hooks (config password chiffrée, STORY-169.4) |

Conventions respectées : PK en `String(36)` UUID, `created_at/updated_at`, snake_case.

---

## 7. Sécurité — AuthN / AuthZ / RBAC

### 7.1 JWT — [`auth/jwt.py`](../backend/app/auth/jwt.py)

python-jose, HS256. Access token **15 min**, refresh **7 jours** (config). `create_token_pair()`, `decode_access_token()`, `decode_refresh_token()` — les refresh tokens sont **opaques** (`wf_rt_`, persistés en base, révocables — STORY-123).

### 7.2 Dépendances — [`auth/dependencies.py`](../backend/app/auth/dependencies.py)

| Dépendance | Comportement |
|-----------|--------------|
| `get_current_user()` | OAuth2 Bearer **ou** clé API `X-API-Key` (STORY-124) ; en mode `disable_auth`, retourne le premier superadmin |
| `get_current_active_user()` | Vérifie `is_active` (403) |
| `require_role(...)` | RBAC granulaire (voir 7.3) |
| `require_superuser()` | 403 si non superadmin — alias `get_current_superadmin` |
| `get_current_user_ws()` | Auth WebSocket stricte par query param `?token=` : handshake refusé 1008 si token absent/invalide/expiré ou user inactif (STORY-100) |
| `authenticate_ws_first_message()` | Auth « JWT au premier message » centralisée (timeout 30 s, close 1008) — canaux général/terminal |

### 7.3 RBAC granulaire — [`auth/rbac.py`](../backend/app/auth/rbac.py) (STORY-121/122)

- Hiérarchie **4 rôles** : `viewer < operator < admin < super_admin` (enum [`enums/rbac.py`](../backend/app/enums/rbac.py), `UserRole`) ;
- [`require_role("...")`](../backend/app/auth/rbac.py:74) + alias `require_viewer`/`require_operator`/`require_admin`/`require_super_admin` — **~174 usages** couvrant les endpoints REST (viewer minimum en lecture, operator actions, admin gestion, super_admin instance) ;
- `ensure_role_ws` sur les canaux WebSocket (STORY-122.6) ;
- isolation organisationnelle vérifiée (un user n'accède pas aux ressources d'une autre org) ;
- matrice transverse testée par router avec garde-fous d'exhaustivité (STORY-122.7) ;
- cache de rôles via le cache unifié (STORY-168) ;
- ~~`helper/permissions.py` policies héritées~~ **purgé** (STORY-250.1).

### 7.4 Keycloak SSO

Toujours optionnel (`keycloak_enabled=False` par défaut) : bloc de config + champ `keycloak_id` sur `User`, activable via `make enable-sso`. **Aucune implémentation OIDC dans le code** (inchangé — extension).

### 7.5 Mots de passe — Argon2id (STORY-130.1)

passlib + argon2-cffi : hash **Argon2id effectif**, **double lecture bcrypt legacy** avec re-hash automatique au login. `bcrypt ^4.0.0` conservé uniquement pour la vérification des hashes legacy (retrait post-migration, cf. STORY-250).

### 7.6 Sessions / logout

Logout **révocant** : le refresh token est supprimé en base, la rotation détecte la réutilisation (STORY-123).

### 7.7 Protection brute-force — [`core/bruteforce_protection.py`](../backend/app/core/bruteforce_protection.py) (STORY-104)

5 échecs par username sur fenêtre glissante 10 min → lockout 5 min (`auth_max_attempts=5`, `auth_lockout_seconds=300`, `auth_attempt_window_seconds=600`).

### 7.8 Secrets — [`core/secret_manager.py`](../backend/app/core/secret_manager.py) (STORY-103)

Chiffrement des credentials en base : **AES-256 via Fernet**, clé dérivée du `master_key` par PBKDF2HMAC (SHA-256). Appliqué aux credentials des hosts, aux config values password des plugins (STORY-169.4) ; masquage `***` dans les aperçus. Vault reste optionnel (`vault_enabled=False`).

### 7.9 Clés SSH & TOFU (STORY-131)

Gestion des clés SSH réutilisables + empreintes de hosts avec politique **TOFU** (Trust On First Use) anti-MITM : premier enregistrement de l'empreinte, vérification stricte ensuite, helper de connexion sécurisé intégré aux sites SSH.

### 7.10 Audit trail (STORY-125)

Modèle `AuditLog` + émission sur actions critiques (login, déploiements, gestion plugins/hosts, prunes, configuration) + `GET /admin/audit` paginé + purge lifespan avec rétention configurable.

---

## 8. WebSocket temps réel

Module [`websocket/`](../backend/app/websocket) — documentation interne exhaustive : [`websocket/README.md`](../backend/app/websocket/README.md).

### 8.1 Connection managers — [`connection_managers.py`](../backend/app/websocket/connection_managers.py)

`BroadcastManager` (base), `ConnectionManager` (1 connexion par déploiement, accept conditionnel — BUG-008 corrigé), `UserConnectionManager` (multi-connexions par user, purge hors lock — BUG-005), instances globales `manager`/`user_manager`. 100 % couverts par les tests (STORY-165).

### 8.2 Broadcasting — [`broadcasting.py`](../backend/app/websocket/broadcasting.py)

`broadcast_deployment_log/status/progress/complete`, `broadcast_to_user`, souscriptions (`subscribe_to_event`…, purge des clés vides — BUG-007).

### 8.3 Event bridge — [`event_bridge.py`](../backend/app/websocket/event_bridge.py)

Mappe les événements du **bus canonique** → `WebSocketEventType` et re-broadcast ; monté au startup, abonné au bus actif (in-memory ou Redis Pub/Sub).

### 8.4 Canaux & protocole (STORY-164)

8 canaux (voir [§3.19](#319-websocket--8-canaux-sous-apiv1ws)). Mécaniques de protocole serveur (STORY-164.1) : **heartbeats** avec expiration des connexions muettes ([`heartbeat.py`](../backend/app/websocket/heartbeat.py)) + **acknowledgment** des messages critiques ([`ack_registry.py`](../backend/app/websocket/ack_registry.py), timeout `ack_timeout` → `record_error`). Canaux supplémentaires STORY-164.2 : `ssh/{host_id}` (TOFU STRICT), `journal/{host_id}` (operator), `batch/{batch_id}` (émetteur-ready) ; VNC reporté (documenté). Client : reconnexion unifiée avec jitter + resynchronisation d'état (module partagé `ws-reconnect.ts` côté frontend, STORY-164.3).

### 8.5 Système de plugins WS — [`plugin.py`](../backend/app/websocket/plugin.py)

`WebSocketPlugin`, `WebSocketPluginManager` (enregistrement sans fuite — BUG-006 corrigé), `PluginContext` + 4 plugins : `audit_logger`, `deployment_monitor`, `deployment_notifications` (consommateur bus réel STORY-163), `subscription`.

### 8.6 Métriques WS — [`websocket/metrics.py`](../backend/app/websocket/metrics.py) (STORY-172)

14 séries `windflow_websocket_*` (broadcast, connexions, auth, plugins, `ack_timeout`) câblées dans les 6 modules temps réel.

---

## 9. Event-driven & tâches de fond

### 9.1 Runtime — asyncio unique (arbitrage F1)

~~`celery_app.py` complet mais jamais importé~~ → **purgé** (STORY-130.2). Le runtime est **asyncio unique, assumé** : 6 tâches lifespan (santé, purges ×4, SchedulerEngine — cf. [§2.2](#22-lifespan-mainpy77)), `DeploymentOrchestrator` et [`background_tasks.py`](../backend/app/tasks/background_tasks.py). Garde-fou : [`test_no_celery_residue.py`](../backend/tests/unit/test_no_celery_residue.py).

### 9.2 Bus canonique — core/events.py (STORY-162)

Interface **`Bus`** (Protocol) avec 2 implémentations : **`InMemoryEventBus`** (défaut, mode léger) et **`RedisPubSubEventBus`** (optionnelle, activée quand `cache_url` est configurée) — toutes sur le **canal unique `windflow:events`**. Nomenclature `domaine.action_passé` + table `LEGACY_EVENT_ALIASES` (ex. `deployment.completed` → `deployment.succeeded`). Redis Streams **assumé hors périmètre** (arbitrage F6).

### 9.3 Consommateurs (STORY-163)

Le pont WebSocket (event bridge) **et** les hooks plugins `@on_event` ([`plugins/hooks.py`](../backend/app/plugins/hooks.py), SDK isolé avec timeout/pool) : `deployment_notifications` enregistré, `DEPLOYMENT_PROGRESS` émis, jalons de déploiement publiés sur le bus depuis les 2 chemins d'exécution.

---

## 10. Core transversal, middleware, helper, enums

### 10.1 Core (10 fichiers)

| Fichier | Contenu | État |
|---------|---------|------|
| [`core/exceptions.py`](../backend/app/core/exceptions.py) | Hiérarchie complète ~21 classes : `WindFlowException` (base avec `details`, `error`, `suggestion`) + sous-classes typées par domaine | ✅ Résolu (STORY-127) : plus d'`HTTPException` brutes dans les endpoints |
| [`core/cache.py`](../backend/app/core/cache.py) | ABC `CacheManager` + `MemoryCache` (bornée FIFO) / `RedisCache` (fallback mémoire par opération) + factory `get_cache()` — préfixes `rbac:`/`registry:`/`llm:` | ✅ Résolu (STORY-168) : interface unique effective |
| [`core/metrics.py`](../backend/app/core/metrics.py) | Instrumentation Prometheus centrale : HTTP, déploiements ok/ko + durée, scheduler, circuit breaker | ✅ Résolu (STORY-172) |
| [`core/secret_manager.py`](../backend/app/core/secret_manager.py) | Fernet AES-256, clé PBKDF2 | ✅ Résolu (STORY-103) |
| [`core/bruteforce_protection.py`](../backend/app/core/bruteforce_protection.py) | `BruteforceProtector` (compteur par username) | ✅ Résolu (STORY-104) |
| [`core/rate_limit.py`](../backend/app/core/rate_limit.py) | `conditional_rate_limiter()` — Redis **ou fallback mémoire process-local effectif** | ✅ Résolu (STORY-102) |
| [`core/resilience.py`](../backend/app/core/resilience.py) | `CircuitBreaker` + `CircuitBreakerRegistry` + `RetryPolicy` — **câblés** | ✅ Résolu (STORY-251) |
| [`core/events.py`](../backend/app/core/events.py) | Bus canonique (voir [§9.2](#92-bus-canonique--coreeventspy-story-162)) | ✅ Résolu (STORY-162) |
| [`core/abstractions.py`](../backend/app/core/abstractions.py) | `CacheManager` (consommé par STORY-168) — ~~`DatabaseManager`~~ purgé (STORY-250.1) | ✅ nettoyé |

### 10.2 Helper (~13 fichiers)

[`template_renderer.py`](../backend/app/helper/template_renderer.py) + `jinja_functions.py`, `security.py`, `email.py`, `compute_helpers.py`, générateurs de noms (`animalname`/`cosmicname`/`mythologyname`), `pagination.py` (STORY-128), [`croniter.py`](../backend/app/helper/croniter.py) (vendored — **consommé** par le scheduler, STORY-160.1 ; dépendance `python-dateutil` déclarée), `target_host_migration.py` (helpers de transition STORY-166).

### 10.3 Enums — 4 fichiers

[`host.py`](../backend/app/enums/host.py) (`HostProfile`, `HostStatus`, `WorkloadOrigin` — STORY-166.1), [`target.py`](../backend/app/enums/target.py) (`TargetType`, `SSHAuthMethod`…), [`rbac.py`](../backend/app/enums/rbac.py) (`UserRole` — STORY-121), [`workload.py`](../backend/app/enums/workload.py) (`WorkloadFamily` — STORY-174).

---

## 11. Configuration

[`config.py`](../backend/app/config.py) — `Settings` (pydantic-settings, `.env`, `extra="ignore"`). Grandes sections :

| Section | Contenu |
|---------|---------|
| **App** | Nom, version, debug, environment (+ propriétés `is_production`) |
| **DB** | `database_url` SQLite/aiosqlite par défaut, pool pour PostgreSQL |
| **JWT** | Secret (**garde-fou dev en prod** — STORY-101 : refus de démarrer avec le secret par défaut en production), HS256, 15 min / 7 j |
| **Auth** | Brute-force (`auth_max_attempts=5`, `auth_lockout_seconds=300`, `auth_attempt_window_seconds=600` — STORY-104), `disable_auth=False` (marqué DANGER) |
| **Flags optionnels** | `keycloak_enabled=False`, `vault_enabled=False`, `litellm_enabled=False`, `prometheus_enabled=True` (**instrumentation réelle** — STORY-172) |
| **API/CORS/CSP/HSTS** | Origines parsables JSON/CSV, CSP détaillée, HSTS off par défaut |
| **Rate limiting** | enabled + `rate_limit_storage_url` (Redis) + défaut 100/min + **fallback mémoire** (STORY-102) |
| **Cache** | `cache_url` (Redis, active aussi le bus Pub/Sub) — cache unifié STORY-168 |
| **Performance** | Timing middleware, `slow_request_threshold=1.0`, correlation ID |
| **Seeding** | Admin par défaut, org par défaut, **`auto_detect_local_host=True`** (STORY-166.5) |
| **Scheduler** | `scheduler_enabled`, `scheduler_tick_seconds`, `scheduler_task_timeout_seconds`, purge des exécutions |
| **Rétentions/purges** | `refresh_token_purge_interval_hours`, `audit_purge_interval_hours` (STORY-125.3), `scheduler_executions_purge_interval_hours` (STORY-161), `deployment_events_purge_interval_hours` (STORY-167) |
| **Circuit breaker** | `circuit_breaker_enabled`, `_failure_threshold`, `_success_threshold`, `_timeout`, `_half_open_timeout` (+ alias `WINDFLOW_*` — STORY-251) |
| **Stacks/Plugins/Logging** | Définitions auto, registre distant TTL 300 s, niveau + format json/text |

---

## 12. IA / LiteLLM

Un module : [`litellm_service.py`](../backend/app/services/litellm_service.py).

- **Conservé et consommé partiellement** : le cache LLM **borné** est réel (préfixe `llm:`, clé sha256 du prompt — prompt jamais en clair — TTL 300 s) via le cache unifié [`core/cache.py`](../backend/app/core/cache.py) (STORY-168) ; la dépendance `litellm ^1.79.0` est **réelle** dans [`pyproject.toml`](../pyproject.toml).
- **Appels LLM toujours simulés** : `_call_llm()` retourne des réponses en dur — l'intégration `litellm.completion()` reste en TODO (commentaires lignes 127/303/331) ; la dépendance n'est **pas encore importée** à ce jour (inspection 2026-11-01).
- **Aucun endpoint IA exposé** (aucun router ne référence `LiteLLMService`) — traçabilité : plugin IA Phase 5 → STORY-254.

---

## 13. Tests & couverture

### 13.1 Volumétrie (comptage du 2026-11-01)

**~3041 fonctions de test unitaires** (204 fichiers) + **~237 d'intégration** (21 fichiers). Répartition unitaires : `test_api` 48 fichiers, `test_services` 52, `test_docker` 22, `test_websocket` 20 (~394 tests — module WS couvert à 94 %, STORY-164/165), `test_models` 12, `test_core` 10, `test_schemas` 9, `test_auth` 4, `test_tasks` 3, `test_middleware`/`test_helper`/`test_plugins`/`test_config` 8.

### 13.2 Fixtures clés — [`tests/conftest.py`](../backend/tests/conftest.py)

Engine SQLite in-memory par fonction, `db_session`, `test_organization`, `test_user`, client HTTP via `httpx.AsyncClient` + `ASGITransport` (override `get_db`), herméticité renforcée (bridage logging, BUG-004).

### 13.3 Couverture par domaine (post-remédiation)

| Domaine | État |
|---------|------|
| WebSocket | ✅ 94 % du module, ~394 tests (STORY-164/165) — ancienne zone zéro comblée |
| RBAC | ✅ matrice transverse par router + garde-fous d'exhaustivité (STORY-122.7) |
| Migrations Alembic | ✅ intégration round-trip upgrade/downgrade (STORY-120.3) |
| Enveloppes/pagination | ✅ tests de contrat par router (STORY-126/128) |
| Cache/rate limiting | ✅ cache 93 %, rate_limit 100 %, registry 94 % (STORY-168) |
| Scheduler | ✅ moteur, actions, executions, métriques (STORY-160/161/172) |
| Docker/workloads | ✅ très bonne (create, recreate sécurisé, networks, stats, adapters 100 % modules workloads — STORY-174) |
| Plugins | ✅ package/validation/install/gates/routes dynamiques (STORY-169/170) |
| Auth | ✅ brute-force, Argon2 double lecture, refresh révocables, clés API (STORY-104/123/124/130.1) |
| Déploiements | ✅ service + events structurés (STORY-167) |

### 13.4 Zones restantes (réelles)

Intégration continue sur quelques surfaces périphériques (discovery/adoption UI, VNC WS reporté), tests E2E backend hors périmètre (choix projet : `unit/` + `integration/` uniquement). ⚠️ **Échecs préexistants** dans la suite au 2026-11-01 (15, prouvés sur HEAD par stash — aucun causé par cette édition documentaire, aucun fichier code/test modifié) : le résidu STORY-172 (`test_rbac_exhaustivite.py::test_every_api_route_is_protected` — l'endpoint `/api/v1/metrics` est sans auth **par design** pour le scrape, le garde-fou historique attend un contrôle d'accès) signalé STORY-251/252, **plus 14 échecs supplémentaires** apparus depuis le dernier comptage STORY-252 (7 `test_admin_stacks_validation.py`, 7 `test_stacks_variables_contract.py`) — signalés ici, à arbitrer en STORY-254. Jamais lissés.

---

## 14. Implémenté vs annoncé — zones mortes & lacunes

### 14.1 Écarts de l'édition du 30/08/2026 — état après remédiation

| Constat du 30/08/2026 | État réel (2026-11-01) |
|------------------------|------------------------|
| ~~Celery non intégré au runtime~~ | **résolu (STORY-130.2)** : `celery_app.py` purgé, runtime asyncio unique assumé, garde-fou `test_no_celery_residue.py` |
| ~~Redis Streams non implémenté (stubs commentés)~~ | **résolu (STORY-162)** : bus canonique `Bus` livré — `InMemoryEventBus` + `RedisPubSubEventBus` canal `windflow:events` ; Redis Streams **assumé hors périmètre** (F6) |
| ~~Résilience non câblée~~ | **résolu (STORY-251)** : CircuitBreaker câblé (Docker/SSH/registre plugins), métriques + alerte ; ~~HealthCheck~~ purgé (STORY-250.1) |
| ~~IA simulée et orpheline~~ | **partiellement résolu (STORY-168/250)** : conservée, dépendance réelle + cache LLM borné effectif ; **appels LLM toujours simulés** (TODO import), 0 endpoint exposé → STORY-254 |
| ~~Pas de RBAC granulaire~~ | **résolu (STORY-121/122)** : 4 rôles, `require_role` ~174 usages, matrice testée ; ~~permissions.py~~ purgé (STORY-250.1) |
| ~~Workflows = stub `[]`~~ | **résolu (STORY-250.1)** : router supprimé, OpenAPI sans `/workflows` (garde-fou) |
| ~~Pas d'Alembic~~ | **résolu (STORY-120)** : 13 migrations, `upgrade head` au démarrage |
| ~~Keycloak/Vault/Prometheus = flags sans implémentation~~ | **Prometheus résolu (STORY-172)** : instrumentation réelle + dashboards + alertes ; Keycloak/Vault restent optionnels par design (extensions `make enable-*`) |
| ~~RBAC binaire, logout stateless, bcrypt seul~~ | **résolu (STORY-122/123/130.1)** : RBAC granulaire, logout révocant, Argon2id + double lecture bcrypt |
| ~~Credentials en clair~~ | **résolu (STORY-103)** : SecretManager Fernet effectif |

### 14.2 Écarts résiduels réels (non lissés — renvoi STORY-254)

| Écart résiduel | Détail |
|----------------|--------|
| Échec test `/api/v1/metrics` | **Résidu STORY-172** : l'endpoint sans auth (par design scrape) contredit le garde-fou `test_rbac_exhaustivite.py::test_every_api_route_is_protected` — signalé STORY-251/252, à arbitrer en STORY-254 |
| 14 échecs de tests supplémentaires (2026-11-01) | `test_admin_stacks_validation.py` ×7 (matrice sécurité 401/403) + `test_stacks_variables_contract.py` ×7 (contrat variables + sécurité) — **préexistants sur HEAD** (prouvé par stash), apparus depuis le dernier comptage STORY-252 ; signalés, à diagnostiquer en STORY-254 |
| [`helper/security.py`](../backend/app/helper/security.py) bcrypt orphelin | 0 consommateur : hash bcrypt non utilisé (Argon2 effectif via services auth) — signalement n°1 STORY-252, retrait à tracer |
| Docstrings `expires_in: 1800` mensongers | [`auth.py`](../backend/app/api/v1/auth.py) : 3 docstrings codent en dur `expires_in: 1800` alors que le code calcule `jwt_access_token_expire_minutes * 60` (900) — signalement n°2 STORY-252 |
| `env.example` variables non consommées | `ACCESS_TOKEN`/`SECRET_KEY`… : noms ne correspondant à aucun setting réel — signalement n°4 STORY-252 |
| 3 sites SSH ad hoc non câblés au circuit breaker | Divergence documentée STORY-251 (chemins sans UUID de host) |
| Appels LLM simulés | [`litellm_service.py`](../backend/app/services/litellm_service.py) : TODO `litellm.completion()` (cf. [§12](#12-ia--litellm)) — décisions plugin IA Phase 5 → STORY-254 |

### 14.3 Lacunes & remarques de sécurité

| Constat | Détail |
|---------|--------|
| ~~WS auth tolérante~~ **résolu (STORY-100)** | `get_current_user_ws()` stricte (refus 1008) + `authenticate_ws_first_message()` sur général/terminal |
| ~~Rate limiting no-op sans Redis~~ **résolu (STORY-102)** | Fallback mémoire process-local effectif |
| ~~Logout stateless~~ **résolu (STORY-123)** | Refresh tokens révocables, rotation avec détection de réutilisation |
| Secrets dev par défaut | `jwt_secret`/admin `changeme123` toujours présents **en dev** — mais **garde-fou STORY-101** : refus de démarrer en production avec le secret par défaut |

### 14.4 Divers

| Constat | Détail |
|---------|--------|
| ~~Print de debug au chargement~~ **résolu (STORY-250.1)** | Purgé de `main.py` |
| ~~Duplication `/users/me` vs `/auth/me`~~ **résolu (STORY-250.2)** | `/auth/me` déprécié (headers `Deprecation`/`Sunset: 2027-05-31`), consommateurs frontend/CLI migrés vers `/users/me` |
| ~~TODOs bénins plugins WS~~ | `audit_logger` : persistance DB toujours en TODO (bénin, futur) |

### 14.5 Points solides réels (inchangés ou renforcés)

| Point fort | Détail |
|-----------|--------|
| Scan de hosts | Très complet (~20 parseurs, probes sockets, profils d'accès) — golden tests §2.G (STORY-166.3) |
| Module Docker | Riche (35 endpoints, promote, adoption, recreate sécurisé) |
| WebSocket | Modulaire, documenté, 94 % couvert, protocole heartbeat/ack |
| OpenAPI | Soignée (Scalar/Swagger/ReDoc, description riche) |
| Recovery des déploiements | `recover_pending_deployments()` au démarrage |
| Observabilité | Prometheus réel : HTTP, business, WS, circuit breaker + dashboards Grafana + alertes (STORY-172/251) |

---

## 15. Synthèse

Le backend WindFlow est un modular monolith FastAPI **consolidé par la remédiation P0-P3** (STORY-100 → 253). Les briques précédemment « annoncées mais inertes » sont désormais **actives et testées** :

- **RBAC granulaire 4 rôles** sur ~174 usages REST + canaux WS (STORY-121/122) ;
- **Alembic** : 13 migrations, appliquées au démarrage (STORY-120) ;
- **Secrets chiffrés** Fernet + Argon2id + brute-force protection + refresh tokens révocables + clés API + TOFU SSH (STORY-103/104/123/124/130.1/131) ;
- **Scheduler** à moteur runtime asyncio avec exécutions historisées et triggers événement (STORY-160/161) ;
- **Bus canonique** in-memory + Redis Pub/Sub optionnel, consommateurs plugins (STORY-162/163) ;
- **WebSocket** 8 canaux, protocole heartbeat/ack, 94 % couvert (STORY-164/165, BUG-005→009 corrigés) ;
- **Plugins réels** : install complet avec rollback, gates pre-deploy, routes dynamiques (STORY-169/170) ;
- **Observabilité Prometheus** effective + dashboards + alertes (STORY-172) ;
- **CircuitBreaker câblé** Docker/SSH/registre (STORY-251) ;
- **Enveloppes API + pagination** généralisées (STORY-126/128), exceptions typées (STORY-127) ;
- **Purge du code mort** (STORY-250.1) et dépréciations tracées `/auth/me`, `/targets` (STORY-250.2/166.2).

Restent en **squelette/flag par design ou report assumés** : Keycloak SSO et Vault (extensions optionnelles `make enable-*`), appels LLM simulés (0 endpoint IA exposé — STORY-254), VNC WebSocket (reporté), étape 3 du modèle de données compute (reportée, annotation phasage spec 06 — STORY-166.4/252). Les **écarts résiduels réels** sont listés en [§14.2](#142-écarts-résiduels-réels-non-lissés--renvoi-story-254) — le tableau de conformité final sera produit par STORY-254 sur la base de ce document.
