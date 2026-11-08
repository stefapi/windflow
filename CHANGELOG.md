# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

> Trace de la remédiation backend (plan `docs/backend_remediation_plan.md` — vagues P0 → P3, EPIC-011 à EPIC-014, stories STORY-100 → 253). Le détail complet vit dans le backlog (`.backlog/`) ; chaque entrée renvoie à sa story.

### Added

- **Harness de pilotage aligné sur PreviImmo (EPIC-020)** : refonte du corpus `.roo/rules/` (12 règles réécrites + 6 nouvelles : glossaire, frontend Vue 3, Python/uv, temps réel WebSocket, IA/LiteLLM, performance/résilience) ; règles de modes Roo (orchestrator, architect, code, debug) ; migration des skills vers `.agents/skills/` avec versions concises pilotées par contrat (+ `write-acceptance-tests`) ; `AGENTS.md`/`CLAUDE.md` et `.rooignore` à la racine ; protocole commun d'exécution et matrice de validation (`docs/dev/`) ; support des epics directes (mode de réalisation, statut `REVIEW`, section « Exécution directe » du gabarit) ; nouvelles cibles `make ci-fast` et `make check` ; `make check-harness` étendu (points d'entrée, règles de modes, emplacement `.agents/skills/`).
- **STORY-255 — Migration Poetry → UV** (EPIC-016) : gestion des dépendances et environnements Python migrée vers UV — `pyproject.toml` PEP 621 natif (`[project]`, `[dependency-groups]`, `tool.uv package=false`), `uv.lock` versionné, Python 3.11 épinglé via `.python-version`, `poetry.lock`/`poetry.toml` supprimés. Makefile (24 cibles `uv run`/`uv sync`/`uv export` + cible `install-vm`), `Dockerfile.api` (image `ghcr.io/astral-sh/uv`, `uv sync --frozen`), workflows Gitea (ci/test/quality-gates), `run.sh`, scripts dev et docs passés à UV ; `.roo/rules` synchronisées via `update-rules`. `libvirt-python` (sdist sans wheel, build exigeant `pkg-config`+`libvirt-dev` absents de l'hôte/Docker, jamais réellement installée) sorti du graphe résolu — install ciblée `make install-vm`, import défensif inchangé. Dette comblée : black/isort/flake8/mypy/bandit/pylint/types-PyYAML déclarés dans le groupe dev (invoqués par le Makefile mais absents de l'ancien lock Poetry). Bugs latents révélés par l'épinglage Python 3.11 réparés : forward-ref `StackDefinitionInfo` (STORY-171, masquée par les annotations différées de Python 3.14), annotations obsolètes `Target`→`Host` (4 fichiers de tests non collectables sous 3.11), fixtures `_jwt_mode` ajoutées à 2 fichiers de tests exposés à un `.env` local `DISABLE_AUTH=true` (cause racine historique STORY-122). Versions résolues fidèles à l'ancien lock (pydantic 2.12.x, sqlalchemy 2.0.x, anyio 3.7.x).
- **STORY-120 — Alembic : baseline du schéma et migrations au démarrage** (P1-1 — EPIC-012) : infra Alembic async + migration baseline ; `alembic upgrade head` exécuté au démarrage à la place de `Base.metadata.create_all()` (plus aucun `create_all` nu) ; Makefile/CI et tests d'intégration round-trip upgrade/downgrade.
- **STORY-121 — Association `user_organizations`** (P1-2 — EPIC-012) : table d'association utilisateur ↔ organisation avec rôle (`Role`), endpoints de gestion des membres (liste/ajout/modification/retrait), migration des données et retrait de la colonne héritée.
- **STORY-122 — RBAC granulaire `require_role(...)`** (P1-2 — EPIC-012) : hiérarchie 4 rôles `viewer < operator < admin < super_admin`, protection de ~174 usages REST + canaux WebSocket (`ensure_role_ws`), isolation organisationnelle, cache de rôles, matrice transverse vérifiée par des tests avec garde-fous d'exhaustivité.
- **STORY-123 — Refresh tokens révocables** (P1-3 — EPIC-012) : table `refresh_tokens`, tokens opaques `wf_rt_` persistés, rotation à chaque refresh, logout invalidant côté serveur, purge périodique des entrées expirées.
- **STORY-125.1 — Socle audit trail** (P1-4 — EPIC-012) : table `audit_logs` et service central d'audit.
  - Table `audit_logs` + modèle `AuditLog` et migration Alembic `1251_audit_logs` — FK `SET NULL` sur `users`/`organizations` (conservation documentaire : la trace survit à la suppression de son acteur), colonnes `correlation_id` (indexée — recherche d'incident par requête) et `organization_id` au-delà de la spec 06, `details` JSON natif, index composite `idx_audit_resource`.
  - `AuditService` : écriture **best-effort** ne levant jamais (`audit.write_failed` loggé sans le contenu de `details`), masquage systématique à l'écriture par `_sanitize_details` (clés password/token/secret/key/credential/authorization/cookie → `***`, récursif, troncature 512), `log_from_request()` extrayant IP/correlation_id du middleware, consultation filtrée paginée `list_entries()`, purge `purge_expired()` (no-op si rétention None).
  - Config rétention : `AUDIT_RETENTION_DAYS` (défaut None = conservation indéfinie, spec 15) + `AUDIT_PURGE_INTERVAL_HOURS` (24) ; schemas Pydantic en lecture seule (`AuditLogResponse`, `AuditLogListResponse`) — l'audit n'est pas inscriptible par API.
  - L'émission sur les actions critiques (STORY-125.2) et l'endpoint `GET /admin/audit` + purge périodique (STORY-125.3) suivent.
- **STORY-124 — Clés API `wf_ak_`** (P1-3, partie clés API — EPIC-012) : authentification par clé API coexistant avec JWT.
  - Table `api_keys` + modèle `APIKey` et migration Alembic `1241_api_keys` (STORY-124.1) — hash uniquement en base, FK CASCADE, expiration optionnelle, révocation distincte de l'expiration.
  - `ApiKeyService` : génération `wf_ak_` + 48 caractères (`secrets.token_urlsafe`), hash déterministe Argon2 (sel dérivé HMAC-SHA256, lookup par hash — arbitrage F2/STORY-123), création/liste/révocation idempotente/vérification ; schemas Pydantic n'exposant jamais `key_hash` ni la clé brute (affichage unique à la création) (STORY-124.2).
  - Endpoints `POST/GET/DELETE /auth/api-keys` (201 + clé affichée une seule fois, liste sans secrets, révocation scoped 404 sur clé étrangère, rate limiting) et auth par clé dans `get_current_user` via `X-API-Key` ou `Authorization: Bearer wf_ak_…` — résolue avant la voie JWT, RBAC du propriétaire appliqué à l'identique, `last_used_at` throttlé (STORY-124.3).
  - Tests transverses de sécurité : 401/403/422/404, RBAC viewer par clé, isolation multi-users, aucune clé ni hash dans réponses/logs/base, révocation immédiate de bout en bout (STORY-124.4).
- **STORY-129 — Endpoints santé & mot de passe : `GET /system/ready` sans auth et `PUT /auth/password`** (P1-7 + P1-8 — EPIC-012) : signal de démarrage réel pour les orchestrateurs et self-service de changement de mot de passe.
  - `GET /api/v1/system/ready` **sans authentification** (exemptions spec 09) : vérifie migrations appliquées (`current == head` Alembic — base non versionnée → non-prêt), DB (`SELECT 1`) et Redis optionnel (uniquement si rate limiting configuré) ; `200` enveloppé spec 09 quand prêt, **`503` nu** avec les causes par check ; payload anti-fingerprinting. `GET /api/v1/system/health` formalisé ; `/health` racine conservé en alias.
  - `PUT /api/v1/auth/password` (JWT **ou** clé API) : ancien mot de passe requis (400 si faux), hash Argon2, **révocation de tous les refresh tokens**, clés API conservées, audit `user.password_changed`, rate limit 5/min.
  - Healthchecks compose/Traefik basculés vers `/api/v1/system/ready`.
- **STORY-125.3 — Endpoint admin audit + purge lifespan et rétention** (P1-4, partie consultation/rétention — EPIC-012) : exploitation opérationnelle du journal d'audit.
  - `GET /api/v1/admin/audit` (super_admin uniquement) : pagination `{items, total, skip, limit}` plafonnée 100, filtres bornés, lecture seule stricte. Garde-fou routes admin incrémenté 15 → 16.
  - Boucle lifespan dédiée `_periodic_audit_purge` : purge par âge selon `AUDIT_RETENTION_DAYS`, démarrage conditionnel, cancellation au shutdown.
- **STORY-131 — Clés SSH réutilisables et empreintes hôtes TOFU anti-MITM** (P1-9 — EPIC-012) : modèles `ssh_keys`/`host_ssh_fingerprints` + migration (data migration crypto), service et API `/ssh-keys` (generate/import/CRUD), empreintes par host avec acceptation TOFU, helper de connexion sécurisé intégré aux 5 sites SSH.
- **STORY-160 — Scheduler v2 : moteur runtime asyncio + `/schedules`** (P2-1 — EPIC-013) : modèle `ScheduledTask` spec 17 + registre d'actions et API v2 (STORY-160.1) ; moteur runtime asyncio en tâche lifespan — verrous anti-chevauchement, timeout, récupération des orphelins, fuseaux IANA (STORY-160.2) ; actions core réelles `host.scan`/`compute.docker.prune` et triggers événement (STORY-160.3).
- **STORY-161 — Historique des exécutions scheduler** (P2-1 — EPIC-013) : table `scheduled_task_executions`, endpoints de consultation paginés, run manuel 202, rétention par purge périodique.
- **STORY-162 — Bus d'événements canonique** (P2-2/F6 — EPIC-013) : interface `Bus` unique, `InMemoryEventBus` par défaut, `RedisPubSubEventBus` optionnel sur le canal `windflow:events`, nomenclature `domaine.action_passé` + `LEGACY_EVENT_ALIASES`. Redis Streams assumé hors périmètre.
- **STORY-163 — Consommateurs plugins du bus** (P2-2 — EPIC-013) : SDK hooks `@on_event` (`app.plugins.hooks`) + pont isolé (timeout/pool), plugin `deployment_notifications` enregistré, jalons de déploiement émis depuis les 2 chemins d'exécution.
- **STORY-164 — WebSocket : protocole, canaux et reconnexion** (P2-5/P2-14 — EPIC-013) : heartbeats avec expiration des connexions muettes + acknowledgment des messages critiques (164.1) ; canaux `/ws/ssh/{host}` TOFU STRICT, `/ws/journal/{host}`, `/ws/batch/{batch_id}` (164.2) ; reconnexion unifiée avec jitter + resynchronisation d'état côté client (164.3).
- **STORY-166 — Modèle `Host` et environments** (P2-4/F4 — EPIC-013) : renommage canonique `target_*` → `host_*` (modèle, enums, migration Alembic, services, scanners, WS) ; surface API `/api/v1/hosts/*` + alias `/targets` déprécié (166.2) ; axe `origin` + table `environments` + `stacks.environment_id`/`git_url` (166.4) ; auto-détection désactivable du host local (166.5) ; synchronisation frontend/CLI et purge des références internes (166.6).
- **STORY-167 — `deployment_events` structurés** (P2-7 — EPIC-013) : table dédiée + migration des données (log texte → événements typés), store `deployment_event_store`, endpoint paginé `GET /deployments/{id}/events`, double écriture, rétention.
- **STORY-168 — Cache unifié avec fallback mémoire** (P2-8 — EPIC-013) : interface unique `get_cache()` (`MemoryCache` bornée / `RedisCache` avec fallback mémoire par opération), consommation rate limiter/registre plugins/cache LLM, `shutdown_cache()` au lifespan.
- **STORY-169 — Plugins : package, validation, INSTALL réel** (P2-3 — EPIC-013) : téléchargement sécurisé (SSRF strict, checksum SHA-256 obligatoire, extraction anti path-traversal — 169.1) ; validation complète manifest/architecture/ressources/dépendances (169.2) ; INSTALL réel avec hooks lifecycle, `docker compose up` et **rollback complet** (169.3) ; CONFIGURE chiffré au repos + durcissement (169.4).
- **STORY-170 — Plugins : routes dynamiques et gates pre-deploy** (P2-3 — EPIC-013) : montage/démontage de routes API dynamiques `/api/v1/plugins/{name}/…` avec RBAC core et OpenAPI (170.1) ; SDK gates, `PluginGateService` timeout/multi-gates, insertion dans le pipeline **avant** création des conteneurs (170.2) ; plugin Trivy de référence (170.3).
- **STORY-171 — Validation des stacks unifiée** (P2-6 — EPIC-013) : schéma Pydantic strict `StackDefinition` consommé par le seed et l'import admin (même verdict), bornes numériques `minimum`/`maximum` servies au formulaire et appliquées frontend.
- **STORY-172 — Observabilité Prometheus réelle** (P2-9 — EPIC-013) : module central `core/metrics.py`, endpoint `GET /api/v1/metrics` sans auth (jamais enveloppé, 404 si désactivé), instrumentation HTTP (chemins normalisés, sans query string), métriques business déploiements/scheduler, 14 séries `windflow_websocket_*`, dashboards Grafana + alertes provisionnés, runbook.
- **STORY-173 — `/compute` élargi** (P2-11/F3 — EPIC-013) : `GET /compute/browse` (inventaire aplati paginé/filtrable), `GET /compute/volumes[/{name}[/browse]]` (conteneur éphémère durci), `POST /compute/prune` (superadmin + confirmation + dry-run + audit) ; mapping `/compute`↔`/docker` documenté.
- **STORY-174 — Socle `WorkloadAdapter` + recreate sécurisé** (P2-12/P2-13/F7 — EPIC-013) : enum `WorkloadFamily` + ABC `WorkloadAdapter`/`AppAdapter`, adapters Docker/Compose **enveloppant** les exécuteurs existants, bascule du chemin de déploiement (174.1) ; recreate sécurisé — rebase par valeur, rollback automatique, secrets masqués `***` (174.2).
- **STORY-251 — CircuitBreaker câblé sur les appels externes** (P3-2 — EPIC-014) : `CircuitBreakerRegistry` (registres `docker_engine`/`plugin_registry`/`ssh:{uuid}`, settings `circuit_breaker_*`), garde partagé sur les adapters Docker et le transport SSH, séries `windflow_circuit_breaker_state/failures_total` + alerte `WindflowCircuitBreakerOpen`. (3 sites SSH ad hoc non câblés — divergence documentée.)

### Changed

- **STORY-127 — Hiérarchie d'exceptions typées** (P1-5, partie exceptions — EPIC-012) : `core/exceptions.py` complété (~21 classes, `WindFlowException` avec `details`/`error`/`suggestion`), remplacement des `HTTPException` brutes — erreurs normalisées `{error: {code, message}, correlation_id}` avec codes machines stables. Complète les enveloppes STORY-126/128 ci-dessous.
- **STORY-130.1 — Migration Argon2id : double lecture bcrypt legacy + re-hash automatique au login** (P1-10 — arbitrage F2, EPIC-012) : password hashing — double lecture bcrypt legacy + re-hash automatique Argon2id au login (aucun reset de mot de passe requis — arbitrage F2) ; dépendance `bcrypt` ajoutée en transition (lecture seule — retrait post-migration, cf. STORY-250).
  - `pwd_context` étendu à `schemes=["argon2", "bcrypt"]` avec `deprecated="auto"` : argon2 reste le schème par défaut en **écriture**, bcrypt est **lecture seule dépréciée** pour vérifier les hashes legacy et les re-hacher transparentement au login via `verify_and_update`.
  - Blindage `verify_password`/`verify_and_update` contre les hashes illisibles : échec silencieux → jamais de 500 au login, 401 générique anti-énumération.
  - Descriptions OpenAPI corrigées « bcrypt » → Argon2id.
- **STORY-125.2 — Émission d'audit sur les actions critiques** (P1-4, partie émission — EPIC-012) : branchement de `AuditService.log_from_request` sur le catalogue complet (20 actions / 18 points d'insertion) — auth, suppressions, rôles/membres, déploiements, conteneurs/plugins ; résilience (échec d'écriture injecté → l'action métier répond quand même) ; bugs pré-existants corrigés au passage (`StackService.delete()` inexistante → 500, crash naive/aware dans `update_status`).
- **BREAKING — STORY-128 : pagination généralisée sur tous les endpoints de liste (spec 09, P1-6 — EPIC-012)** — toutes les listes `/api/v1/*` répondent désormais dans l'enveloppe paginée commune `{"data": [...], "pagination": {"page": 1, "per_page": 20, "total": 87, "pages": 5}}` via `?page=&per_page=` (défauts `page=1`/`per_page=20`, bornes `per_page` 1-100 — dépassement → `422 VALIDATION_ERROR` ; page au-delà de la dernière → `200` avec `data: []`). Complète l'harmonisation annoncée en STORY-126.3 ; API, frontend et CLI livrés dans la même release.
  - **Endpoints convertis** (listes nues → paginées) : `GET /stacks/`, `/organizations/`, `/organizations/{id}/users`, `/stacks/{id}/versions`, `/schedules`, `/plugins/`, `/plugins/{id}/hooks/logs`, `/registry/plugins`, `/hosts/`, `/users/`, `/deployments`, `/auth/api-keys`, `/admin/audit`, `/admin/stacks-management/definitions`, `/admin/stacks-management/imported` ; **harmonisés au même format** : `GET /docker/containers|images|volumes|networks` ; les formats intermédiaires `{items, total, skip, limit}` et `{items, total, page, size, pages}` sont retirés.
  - **Bugs préexistants corrigés** : l'agrégation multi-organisation de `GET /targets/` et `GET /deployments` appliquait `skip/limit` **par organisation** avant concaténation → requête unique + `COUNT` scopé ; tris stables ajoutés.
  - **Migration consommateurs** : (1) remplacer `?skip=&limit=` par `?page=&per_page=` et lire la liste dans `data` ; (2) frontend — interceptor axios déplie `data` et rattache `response.pagination` ; (3) CLI — `api_client.get_paginated()` et `get_all()` remplacent les `get()` nus.
  - Le helper commun `backend/app/helper/pagination.py` (`PaginationQuery`, `build_meta`, `paginate_sequence`) est le socle canonique des futures surfaces paginées.
  - Le flag transitoire `API_ENVELOPE_ENABLED` (introduit en STORY-126.1, activé par défaut en 126.2) est **retiré** : le format enveloppe est systématique, plus de mode legacy.
- **BREAKING — STORY-126 : enveloppes API systématiques (spec 09, P1-5 — EPIC-012)** : les réponses 2xx JSON sont enveloppées `{"data": …}` et les erreurs `{"error": {"code": "…", "message": "…"}, "correlation_id": "…"}` avec codes machines stables (`INVALID_CREDENTIALS`, `PERMISSION_DENIED`, `CONFLICT`, `VALIDATION_ERROR`, …) ; `204 No Content` et canaux WebSocket inchangés ; les clients frontend/CLI déplient `data` centralement.

### Deprecated

- **STORY-250.2 — `GET /auth/me` remplacé par `GET /users/me`** (P3-3 — EPIC-014) : l'endpoint répond 200 mais porte les headers `Deprecation: true` et `Sunset: 2027-05-31` (RFC 8594, constante `AUTH_ME_SUNSET`) et l'annotation OpenAPI `deprecated: true` avec renvoi vers `/users/me` ; les consommateurs frontend et CLI sont migrés.
- **STORY-166.2 — alias `/api/v1/targets` remplacé par `/api/v1/hosts`** (P2-4 — EPIC-013) : l'alias réexpose la surface hosts avec headers `Deprecation`/`Sunset` indicatif **2027-01-01** ; les consommateurs frontend et CLI sont migrés vers `/hosts`.

### Removed

- **STORY-130.2 — Runtime Celery fantôme purgé : `celery_app.py`, `Dockerfile.worker`, service compose `windflow-worker`, cibles Makefile `docker-build-worker`/`enable-workers`, jobs CI worker, scrape + alertes Prometheus, variables `CELERY_*`/Flower (arbitrage F1 — runtime asyncio unique)** (P1-11 — EPIC-012).
  - Le module Celery complet mais **jamais importé** (runtime réel : asyncio — `DeploymentOrchestrator`, boucles lifespan, `background_tasks.py`), la dépendance non installable via Poetry et le `Dockerfile.worker` référençant un chemin inexistant sont supprimés ; garde-fou `backend/tests/unit/test_no_celery_residue.py`.
  - **Disparition du Beat schedule « cleanup-logs-daily » sans remplacement immédiat** (jamais exécuté — la rétention structurée relève du scheduler P2, STORY-160) ; la dépendance `redis` est **conservée** (rate limiting, cache).
- **STORY-250.1 — Purge du code mort backend** (P3-1 — EPIC-014) : `helper/permissions.py` (système policies legacy jamais importé), stub router `/workflows`, `HealthCheck`/`HealthCheckRegistry` (~200 lignes de `core/resilience.py` — `CircuitBreaker`/`RetryPolicy` conservés), `DatabaseManager` (`CacheManager` conservé, consommé par STORY-168), print de debug au chargement de `main.py`. Décisions conditionnelles tranchées par les faits : croniter vendored **conservé** (consommé par le scheduler STORY-160) et `litellm_service.py` **conservé** (cache LLM STORY-168 ; non exposé par API). Garde-fou : OpenAPI sans `/workflows`, grep 0 référence.

### Fixed

- **BUG-005 — Deadlock `UserConnectionManager.broadcast_to_user`** (EPIC-013) : `remove_connection` appelé hors lock, cascade abonnements/contextes préservée.
- **BUG-006 — `WebSocketPluginManager.register` duplicate** (EPIC-013) : index `_event_handlers` obsolète purgé avant remplacement — le plugin remplacé ne reçoit plus les dispatchs.
- **BUG-007 — Clé vide résiduelle dans `ConnectionManager.broadcast_to_deployment`** (EPIC-013) : purge complète de l'entrée après broadcast.
- **BUG-008 — Double `websocket.accept()` sur `deployment_logs`** (EPIC-013) : paramètre `accept_connection` — accept conditionnel, une seule acceptance par connexion.
- **BUG-009 — `WebSocketService.disconnect()` frontend ne purge pas l'état entre sessions** (EPIC-013) : détachement des handlers + purge `authToken`/`authenticated`/`listeners`/`serverSubscriptions` ; `reconnectWithToken()` dédié au flux refresh.
- **BUG-004 — Journalisation du SQL avec paramètres bindés + `test_schedules_v2.py::test_parameters_not_logged_raw` sensible au cwd** : le logger `sqlalchemy.engine` était positionné à INFO à l'import de `app.main` — or à INFO il émet chaque statement SQL **avec ses paramètres bindés** (hash de mots de passe, `key_hash` des clés API…) : fuite sensible en production à `LOG_LEVEL=INFO`. Correction en défense en profondeur : bridage WARNING sauf DEBUG, fixture autouse d'herméticité, le test pose son propre bridage caplog.
- **BUG-003 — `POST /api/v1/docker/containers` renvoyait systématiquement 500** : le décorateur déclarait `response_model=ContainerResponse` alors que le handler retourne un `ContainerDetailResponse`. Correction du contrat OpenAPI ; les contournements de tests sont retirés.
- `DELETE /api/v1/stacks/{id}` renvoyait 500 (`AttributeError`) : `StackService.delete()` était appelée mais n'existait pas — méthode ajoutée.
- `DeploymentService.update_status` levait `TypeError` (soustraction naive/aware) sur toute transition RUNNING → FAILED/STOPPED : calculs passés en naïf UTC cohérent.

### Security

- **Vague P0 — remédiation sécurité (EPIC-011, livrée 2026-09-07)** :
  - **STORY-100 — Auth WebSocket stricte** : `get_current_user_ws()` refuse le handshake (close 1008) sans token valide — fini le canal général ouvert ; auth « JWT au premier message » centralisée (`authenticate_ws_first_message`, timeout 30 s) sur les canaux général/terminal.
  - **STORY-101 — Garde-fou secrets de développement en production** : l'API refuse de démarrer en production avec les valeurs par défaut (`jwt_secret` dev, mot de passe admin `changeme123`).
  - **STORY-102 — Rate limiting effectif sans Redis** : fallback mémoire process-local dans `conditional_rate_limiter()` — les limiteurs ne sont plus des no-op silencieux quand `RATE_LIMIT_STORAGE_URL` est absent.
  - **STORY-103 — SecretManager (chiffrement des credentials)** : AES-256 via Fernet, clé dérivée du `master_key` par PBKDF2HMAC — chiffrement effectif des credentials des hosts en base, masquage des secrets dans les API.
  - **STORY-104 — Protection brute-force du login** : 5 échecs par username sur fenêtre glissante de 10 min → lockout 5 min (`auth_max_attempts`/`auth_lockout_seconds`/`auth_attempt_window_seconds`).

## Template for Future Releases

## [x.y.z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Now removed features

### Fixed
- Bug fixes

### Security
- Vulnerabilities fixed
