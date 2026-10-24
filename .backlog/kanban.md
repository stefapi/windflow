# KANBAN BOARD

## 📋 BACKLOG

### EPIC-013 : P2 — Conformité fonctionnelle (remédiation backend)
- [ ] BUG-009 : `WebSocketService.disconnect()` frontend ne purge pas `authToken`/`authenticated`/`listeners`/`serverSubscriptions` — fuite d'état entre sessions (Majeur — détecté STORY-165 T10)
- [ ] STORY-166 : Migration `Target`→`Host` + axe `origin` + `environments` + `Stack.git_url` + auto-détection du host local (P2-4 + P2-10 — F4 étape 2)
- [ ] STORY-167 : `deployment_events` structurés — table dédiée, migration des données, endpoint paginé, rétention (P2-7)
- [ ] STORY-168 : Cache avec fallback mémoire — interface unique + TTL, Redis sinon mémoire locale (P2-8)
- [ ] STORY-169 : Plugins — installation réelle — download, checksum SHA-256, extraction, compose up, rollback (P2-3, partie installation)
- [ ] STORY-170 : Plugins — routes API dynamiques + gates pre-deploy (approve/deny, timeout, Trivy) (P2-3, partie extension)
- [ ] STORY-171 : Unification de la validation des stacks + bornes numériques `min/max` (P2-6)
- [ ] STORY-172 : Observabilité Prometheus réelle — `/metrics`, métriques business, dashboards alimentés (P2-9)
- [ ] STORY-173 : `/compute` élargi — `browse` paginé et `prune` protégé, rapprochement `/compute`↔`/docker` (P2-11 — F3)
- [ ] STORY-174 : Socle `WorkloadAdapter` + adapter Docker + recreate sécurisé (P2-12 + P2-13 — F7)

### Divers (sans epic)

### EPIC-014 : P3 — Finitions & purge (remédiation backend)
- [ ] STORY-250 : Purge du code mort et résidus + dépréciation `/auth/me` — permissions legacy, croniter conditionnel, abstractions, stub workflows, litellm orphelin, print debug, HealthCheck (P3-1 + P3-3)
- [ ] STORY-251 : CircuitBreaker — câbler sur les appels externes ou supprimer le module (P3-2)
- [ ] STORY-252 : Corrections consolidées des spécifications — arbitrages F1-F6 appliqués aux specs (P3-4)
- [ ] STORY-253 : Mise à jour documentaire post-remédiation — `backend_status.md`, rules `.roo`, CHANGELOG (P3-5)
- [ ] STORY-254 : Revue finale de conformité — audit specs ↔ code et tableau de conformité final (clôture du plan)

### EPIC-015 : Compute — Clusters Kubernetes & Apps cluster-scoped

## 🏗️ IN PROGRESS

_(vide)_

## 🚫 BLOCKED

_(vide)_

## 🚧 REVIEW

_(vide)_

## ✅ DONE

- [x] BUG-008 : Double `websocket.accept()` sur `deployment_logs` — le client reçoit `error` au lieu du statut initial (Majeur — détecté STORY-165, xfail strict) (EPIC-013) — corrigé (paramètre `accept_connection: bool = True` sur `ConnectionManager.connect` — accept conditionnel, défaut rétrocompatible batch.py intact ; handler `deployment_logs` appelle `accept_connection=False` : une seule acceptance par connexion, l'accept précoce reste dédié à la branche 404/403 error + close 1008), xfail retiré + contournement `_register_only_connect` supprimé (6 parcours nominaux sur le vrai chemin de production) + 2 tests du paramètre, 63/63 ciblés puis 416 passed + **0 xfailed** sur `test_websocket/` (BUG-008 était le dernier), non-régression batch 62 passed, connection_managers.py 100 % couverture, lint OK
- [x] BUG-007 : Clé vide résiduelle dans `ConnectionManager.broadcast_to_deployment` — purge sans `del` de l'entrée (Mineur — détecté STORY-165, note de divergence) (EPIC-013) — corrigé (hygiène `disconnect` appliquée à la purge post-broadcast : `difference_update` + `del` de la clé vide, garde `.get()` contre `KeyError` sur disconnect concurrent ; canaux deployment_logs et batch couverts), test documentaire inversé/renommé + 3 tests non-régression (no-op après purge, reconnect, tolérance race), 50/50 ciblés puis 413 passed + 1 xfailed (BUG-008 seul restant), connection_managers.py 100 % couverture, lint OK
- [x] BUG-006 : `WebSocketPluginManager.register` duplicate — index `_event_handlers` obsolète, le plugin remplacé continue de recevoir les dispatchs (Majeur — détecté STORY-165) (EPIC-013) — corrigé (pattern unregister : discard de l'ancienne instance + purge clés vides avant remplacement ; bug jumeau `register_message_handler` inclus), xfail retiré + 4 tests non-régression (dispatch, cleanup_all, écoutes partielles, routage messages), 44/44 ciblés puis 410 passed + 1 xfailed (BUG-008 seul restant), plugin.py 100 % couverture, lint OK
- [x] BUG-005 : Deadlock `UserConnectionManager.broadcast_to_user` — purge des connexions mortes sous le lock non-réentrant (Bloquant — détecté STORY-165) (EPIC-013) — corrigé (remove_connection appelé hors lock, pattern broadcast_to_event_subscribers ; cascade abonnements/contextes préservée), xfail retiré + 3 tests non-régression (lock libéré, purge multiple, cascade), 47/47 puis 405 passed + 2 xfailed (BUG-006/008 restants), connection_managers.py 100 % couverture, lint OK
- [x] STORY-165 : Tests WebSocket — couverture complète du module temps réel (P2-5/P2-14, partie tests) (EPIC-013) — 10 fichiers de tests (+229 backend : 401 passed + 3 xfailed ; +25 frontend), couverture 94 % module WS / 94,05 % `websocket.ts`, 5 bugs consignés (BUG-005→009), story tests-only : zéro code de production modifié
- [x] STORY-164.3 : Reconnexion unifiée avec jitter + resynchronisation d'état + client type documenté (P2-5, partie client — STORY-164 découpée) (EPIC-013) — module partagé `ws-reconnect.ts` consommé par canal général + composables, resync GET, logout conservé, client type documenté §8, 60 tests, couverture 97/82/80 %
- [x] STORY-164.2 : Canaux WebSocket manquants — `/ws/ssh/{host}` TOFU STRICT, `/ws/journal/{host}`, `/ws/batch/{batch_id}` émetteur-ready, VNC reporté documenté (P2-5, partie canaux — STORY-164 découpée) (EPIC-013) — 3 canaux + host_access, 51 tests, couverture 84-100 %, RBAC journal=operator (D1)
- [x] STORY-164.1 : Mécaniques de protocole serveur — heartbeats avec expiration des connexions muettes + acknowledgment des messages critiques (P2-5, partie protocole — STORY-164 découpée) (EPIC-013) — helpers heartbeat/ack_registry sur les 5 canaux, 34 tests, couverture 100 % nouveaux modules

- [x] STORY-163 : Consommateurs plugins du bus — hooks `@on_event`, `deployment_notifications` enregistré, `DEPLOYMENT_PROGRESS` émis (P2-2, partie consommateurs) (EPIC-013) — SDK `app.plugins.hooks` + pont isolé (timeout/pool), 4 plugins WS, jalons 2 chemins, 2106 tests verts
- [x] BUG-004 : `test_schedules_v2.py::test_parameters_not_logged_raw` échoue sur main (echo SQL local — herméticité cwd)  # divers (sans epic) — corrigé (défense en profondeur : caplog + fixture autouse conftest sqlalchemy.engine/aiosqlite + bridage main.py WARNING-sauf-DEBUG), re-vérifié à la clôture (57 + 22 tests verts)
- [x] BUG-003 : `POST /docker/containers` — `response_model=ContainerResponse` inadéquat → 500 systématique sur création  # divers (sans epic) — corrigé (response_model=ContainerDetailResponse), 32 tests ciblés verts
- [x] STORY-162 : Bus d'événements canonique — interface unique, nomenclature spec, in-memory + Redis Pub/Sub optionnel (P2-2, partie bus — F6) (EPIC-013)
- [x] STORY-161 : Table `scheduled_task_executions` — historique des exécutions, endpoints de consultation paginés, run manuel 202, rétention (P2-1, partie traçabilité) (EPIC-013)
- [x] STORY-160.3 : Actions core réelles et triggers événement — handlers `host.scan`/`compute.docker.prune` (dry-run défaut, liste protégée, audit), stubs tracés, triggers EventBus via le chemin moteur (P2-1, partie exécution — STORY-160 découpée) (EPIC-013)
- [x] STORY-160.2 : Moteur runtime asyncio — boucle lifespan, verrous, timeout, orphelins, fuseaux IANA, contrat `ExecutionStore` (P2-1, partie moteur — STORY-160 découpée) (EPIC-013)
- [x] STORY-160.1 : Modèle ScheduledTask spec 17, registre d'actions et API `/schedules` v2 (P2-1, partie définition — STORY-160 découpée) (EPIC-013)
- [x] BUG-002 : Makefile .ONESHELL masque les échecs de lint
- [x] BUG-001 : 35 échecs préexistants suite unitaire backend (herméticité DISABLE_AUTH + enveloppes spec-09)
- [x] STORY-131.3 : Anti-MITM TOFU runtime — helper de connexion et intégration aux 5 sites SSH (P1-9 — STORY-131 découpée) (EPIC-012)
- [x] STORY-131.2 : Service & API de gestion des clés SSH et des empreintes hôtes (P1-9 — STORY-131 découpée) (EPIC-012)
- [x] STORY-131.1 : Modèles & migrations — `ssh_keys`, `host_ssh_fingerprints` et data migration crypto (P1-9 — STORY-131 découpée) (EPIC-012)
- [x] STORY-130.2 : Purge des références Celery — runtime asyncio unique assumé (P1-11 — STORY-130 découpée) (EPIC-012)
- [x] STORY-130.1 : Migration Argon2id — double lecture bcrypt et re-hash automatique au login (P1-10 — STORY-130 découpée) (EPIC-012)
- [x] STORY-129 : Endpoints santé & mot de passe — `GET /system/ready` sans auth et `PUT /auth/password` (P1-7 + P1-8) (EPIC-012)
- [x] STORY-128 : Pagination généralisée — `?page&per_page` sur toutes les listes + enveloppe `{data, pagination}` + clients CLI/frontend synchronisés (P1-6)
- [x] STORY-127 : Hiérarchie d'exceptions — compléter `core/exceptions.py` et remplacer les `HTTPException` brutes (P1-5, partie exceptions)
- [x] STORY-126.3 : Synchronisation des clients — frontend unwrap `data`, CLI, CHANGELOG versionné (P1-5 — STORY-126 découpée)
- [x] STORY-126.2 : Activation des enveloppes — défaut `True`, adaptation suite backend, tests de contrat par router (P1-5 — STORY-126 découpée)
- [x] STORY-126.1 : Socle enveloppes API — schémas spec 09, middleware/handlers derrière `api_envelope_enabled=False` (P1-5 — STORY-126 découpée)
- [x] STORY-125.3 : Endpoint admin `GET /admin/audit`, purge lifespan et rétention (P1-4 — STORY-125 découpée)
- [x] STORY-125.2 : Émission d'audit sur les actions critiques (P1-4 — STORY-125 découpée)
- [x] STORY-125.1 : Socle audit trail — modèle, migration, config, schemas et service (EPIC-012 — STORY-125)
- [x] STORY-124 : Clés API `wf_ak_` — table `api_keys`, auth `X-API-Key` coexistant avec JWT (P1-3, partie clés API) (EPIC-012) — via STORY-124.1 → 124.4
- [x] STORY-124.4 : Tests transverses et sécurité des clés API (EPIC-012 — STORY-124)
- [x] STORY-124.1 : Modèle `APIKey` et migration Alembic (EPIC-012 — STORY-124)
- [x] STORY-124.2 : `ApiKeyService` — génération `wf_ak_`, hash déterministe et schemas (EPIC-012 — STORY-124)
- [x] STORY-124.3 : Endpoints `/auth/api-keys` et auth par clé dans `get_current_user` (EPIC-012 — STORY-124)

- [x] STORY-123 : Refresh tokens révocables — table, rotation et logout invalidant (P1-3, partie refresh) (EPIC-012) — via STORY-123.1 → 123.4
- [x] STORY-123.4 : Purge des entrées expirées et tests sécurité transverses (EPIC-012 — STORY-123)
- [x] STORY-123.1 : Modèle `RefreshToken`, migration Alembic et configuration (EPIC-012 — STORY-123)
- [x] STORY-123.2 : `RefreshTokenService` et refresh token opaque dans `jwt.py` (EPIC-012 — STORY-123)
- [x] STORY-123.3 : Endpoints auth — émission persistée, `/refresh` rotatif, `/logout` révocant (EPIC-012 — STORY-123)
- [x] STORY-122 : Dépendances RBAC `require_role(...)` — 140 endpoints + 5 canaux WS protégés, matrice transverse vérifiée (P1-2, application) (EPIC-012) — via STORY-122.1 → 122.7
- [x] STORY-122.7 : RBAC — matrice transverse, non-régression et couverture (EPIC-012 — STORY-122)
- [x] STORY-122.6 : Application RBAC — admin instance et canaux WebSocket (EPIC-012 — STORY-122)
- [x] STORY-122.5 : Application RBAC — plugins, registry, targets et endpoints de lecture (EPIC-012 — STORY-122)
- [x] STORY-122.4 : Application RBAC — organizations, users et protections d'escalade (EPIC-012 — STORY-122)
- [x] STORY-122.3 : Application RBAC — stacks, deployments, schedules et isolation organisationnelle (EPIC-012 — STORY-122)
- [x] STORY-122.2 : Application RBAC au module Docker — 35 endpoints (EPIC-012 — STORY-122)
- [x] STORY-121 : Modèle `user_organizations` — association utilisateur ↔ organisation avec rôle (P1-2, partie modèle) (EPIC-012) — via STORY-121.1/.2/.3
- [x] STORY-121.3 : Migration des données, bascule des lectures vers l'association et retrait de la colonne héritée (EPIC-012 — STORY-121)

- [x] STORY-121.2 : Endpoints de gestion des membres d'une organisation (EPIC-012 — STORY-121)
- [x] STORY-121.1 : Enum `Role`, modèle `UserOrganization` et migration de création de table (EPIC-012 — STORY-121)

- [x] STORY-120 : Alembic — baseline du schéma existant et `upgrade head` au démarrage à la place de `create_all` (P1-1)
- [x] STORY-120.1 : Infra Alembic async + migration baseline (EPIC-012 — STORY-120)
- [x] STORY-120.2 : Retrait de `create_all` — migrations au démarrage (EPIC-012 — STORY-120)
- [x] STORY-120.3 : Makefile, CI et tests d'intégration des migrations (EPIC-012 — STORY-120)

