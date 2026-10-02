# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **STORY-129 — Endpoints santé & mot de passe : `GET /system/ready` sans auth et `PUT /auth/password`** (P1-7 + P1-8 — EPIC-012) : signal de démarrage réel pour les orchestrateurs et self-service de changement de mot de passe.
  - `GET /api/v1/system/ready` **sans authentification** (exemptions spec 09) : vérifie migrations appliquées (`current == head` Alembic — base non versionnée → non-prêt), DB (`SELECT 1`) et Redis optionnel (uniquement si rate limiting configuré) ; `200` enveloppé spec 09 quand prêt, **`503` nu** avec les causes par check (symétrique du `/health` racine — l'orchestrateur ne lit que le code HTTP) ; payload anti-fingerprinting (ni version, ni environnement — uniquement `current`/`head` de schéma). `GET /api/v1/system/health` formalisé sur le même router ; le `/health` racine historique est **conservé en alias** (non-régression compose/traefik/tests), logique factorisée dans `SystemService`.
  - `PUT /api/v1/auth/password` (authentifié JWT **ou** clé API, self-service sans rôle) : ancien mot de passe requis (**400** `INVALID_INPUT` si faux — arbitrage : l'utilisateur est authentifié, 401 serait trompeur ; 422 sur body invalide/mot de passe < 8), hash **Argon2** via `UserService.hash_password`, **révocation de tous les refresh tokens** (`revoke_all_for_user`, STORY-123), **clés API conservées** (documenté), audit `user.password_changed` (STORY-125 — jamais de matériau de mot de passe), rate limit 5/min ; aucun identifiant utilisateur dans le body (isolation structurelle).
  - Bascule des signaux de démarrage : healthchecks `docker-compose.prod.yml` (api ×2) + Traefik `loadbalancer.healthcheck.path` et `docker-compose.minimal.yml` → `curl -f /api/v1/system/ready` ; doc déploiement (spec 16) : `/ready` signal canonique, `/system/health` vérification légère. Corrections au passage : le healthcheck minimal pointait vers `/api/health` (route inexistante — le middleware strip-prefix n'est pas attaché au router Traefik) ; la description OpenAPI et le tag `system` sont déclarés.
  - Tests : 3 fichiers unitaires (`test_system_service`, `test_system`, `test_auth_password` — sécurité 401/400/422, révocation refresh, clés API intactes, isolation, audit) + 2 intégration (`test_system_endpoints` — enveloppe 200 / 503 nu, correlation ID, contrat OpenAPI ; `test_auth_password_flow` — flux complet login → change → ancien refresh 401 → re-login 200 → clé API survive).

- **STORY-125.3 — Endpoint admin audit + purge lifespan et rétention** (P1-4, partie consultation/rétention — EPIC-012) : exploitation opérationnelle du journal d'audit.
  - `GET /api/v1/admin/audit` (super_admin uniquement — spec 08 § Système) : pagination `{items, total, skip, limit}` plafonnée 100, filtres bornés `user_id`/`action`/`resource_type`/`since`, OpenAPI documenté ; lecture seule stricte (l'audit n'est pas falsifiable depuis l'API, `details` masqué structurellement à l'écriture). Garde-fou routes admin incrémenté 15 → 16.
  - Boucle lifespan dédiée `_periodic_audit_purge` (pattern STORY-123.4, non fusionnée avec la purge refresh tokens) : purge par âge uniquement selon `AUDIT_RETENTION_DAYS` ; **démarrage conditionnel** — défaut illimité = job non démarré + log unique ; intervalle `AUDIT_PURGE_INTERVAL_HOURS` ; cancellation au shutdown.
  - Tests : endpoint (200 paginé + ordre, 401, 403 admin d'org/viewer/operator, 422 × 7, page vide, filtres, pagination sans chevauchement) + rétention courte (1 j) — 41 tests story verts, 1552 au total.

### Changed

- **BREAKING — STORY-128 : pagination généralisée sur tous les endpoints de liste (spec 09, P1-6 — EPIC-012)** — toutes les listes `/api/v1/*` répondent désormais dans l'enveloppe paginée commune `{"data": [...], "pagination": {"page": 1, "per_page": 20, "total": 87, "pages": 5}}` via `?page=&per_page=` (défauts `page=1`/`per_page=20`, bornes `per_page` 1-100 — dépassement → `422 VALIDATION_ERROR` ; page au-delà de la dernière → `200` avec `data: []`). Complète l'harmonisation annoncée en STORY-126.3 ; API, frontend et CLI livrés dans la même release.
  - **Endpoints convertis** (listes nues → paginées) : `GET /stacks/`, `/organizations/`, `/organizations/{id}/users`, `/stacks/{id}/versions`, `/schedules`, `/plugins/`, `/plugins/{id}/hooks/logs`, `/registry/plugins`, `/targets/`, `/users/`, `/deployments`, `/auth/api-keys`, `/workflows/`, `/admin/audit`, `/admin/stacks-management/definitions`, `/admin/stacks-management/imported` ; **harmonisés au même format** : `GET /docker/containers|images|volumes|networks` (l'endpoint technique `shells` reste exclu — énumération non exploitable, exception documentée) ; les formats intermédiaires `{items, total, skip, limit}` et `{items, total, page, size, pages}` sont retirés.
  - **Bugs préexistants corrigés** : l'agrégation multi-organisation de `GET /targets/` et `GET /deployments` appliquait `skip/limit` **par organisation** avant concaténation (totaux faux, pages chevauchantes) → requête unique `WHERE organization_id IN (...)` + `COUNT` scopusé ; tris stables ajoutés (`ORDER BY name`/`created_at`/`joined_at`/`version_number desc`) là où la pagination exigeait un ordre déterministe.
  - **Migration consommateurs** : (1) remplacer `?skip=&limit=` par `?page=&per_page=` et lire la liste dans `data` avec les métadonnées dans `pagination` ; (2) frontend — l'interceptor axios déplie `data` et rattache le bloc à `response.pagination`, les stores Pinia (stacks/targets/deployments/workflows) exposent `pagination{total, pages}` (fallback `{items}` legacy toléré une release) ; (3) CLI — `api_client.get_paginated()` (liste + métadonnées) et `api_client.get_all()` (assemblage multi-pages, `per_page=100`) remplacent les `get()` nus dans les commandes liste, qui affichent le total réel de la collection.
  - Le helper commun `backend/app/helper/pagination.py` (`PaginationQuery`, `build_meta`, `paginate_sequence`) est le socle canonique que les futures surfaces paginées (STORY-170, STORY-173…) devront réutiliser.
  - **Succès (2xx JSON)** : avant `{"id": "app_1", "status": "running"}` → après `{"data": {"id": "app_1", "status": "running"}, "message": null}`.
  - **Listes paginées** : avant `{"items": [...], "total": 87}` → après `{"data": [...], "pagination": {"page": 1, "per_page": 20, "total": 87, "pages": 5}}` (harmonisation complète en STORY-128).
  - **Erreurs** : avant `{"detail": "Not found"}` → après `{"error": {"code": "NOT_FOUND", "message": "App not found"}, "correlation_id": "…"}` avec codes machines stables (`INVALID_CREDENTIALS`, `PERMISSION_DENIED`, `CONFLICT`, `VALIDATION_ERROR`, …).
  - **Migration consommateurs** : (1) déplier `response.data` pour récupérer la charge utile — fait centralement par l'interceptor axios côté frontend et `_handle_response` côté CLI, les stores/vues restent inchangés ; (2) lire les messages d'erreur via `.error.message` (`.detail` n'est plus émis par le backend) ; (3) les réponses `204 No Content` et les canaux WebSocket (format `type`/`data`) sont inchangés.
  - Le flag transitoire `API_ENVELOPE_ENABLED` (introduit en STORY-126.1, activé par défaut en 126.2) est **retiré** : le format enveloppe est systématique, plus de mode legacy.

- **STORY-125.2 — Émission d'audit sur les actions critiques** (P1-4, partie émission — EPIC-012) : branchement de `AuditService.log_from_request` sur le catalogue complet (20 actions / 18 points d'insertion).
  - Auth : `user.login` (après reset brute-force), `user.login_failed` aux 2 refus 401 (credentials invalides / user inactif — `user_id=None` si inconnu, `username` seul en `details`, jamais le password), `user.logout`, `api_key.created` / `api_key.revoked`.
  - Suppressions : `stack.deleted` (test de référence P1-4 : acteur, org de la stack, cible, `correlation_id` strictement égal au header `X-Correlation-ID`), `target.deleted`, `organization.deleted` (une ligne par org en bulk), `container.deleted`.
  - Rôles/membres : `user.role_changed` (`{previous_role, new_role}`), `member.added` / `member.removed`. Déploiements : `deployment.created` (acteur = initiateur), `deployment.succeeded` / `deployment.failed` sur transition terminale (acteur système `user_id=None`), `stack.rollback`. Conteneurs/plugins : `container.started` / `container.stopped`, `plugin.installed` / `plugin.removed`.
  - Tests d'émission `test_audit_emission.py` (14 tests) : test de référence P1-4, parcours complets par famille, résilience (échec d'écriture injecté → l'action métier répond quand même) et sécurité (aucun password ni clé `wf_ak_` brute dans `details` ni les logs).
  - Bugs pré-existants corrigés au passage (révélés par les tests d'émission) : `StackService.delete()` inexistante (`DELETE /stacks/{id}` levait `AttributeError` → 500, masqué par un `type: ignore`) et crash naive/aware dans `DeploymentService.update_status` sur la transition RUNNING → FAILED (calcul de durée).

### Fixed

- `DELETE /api/v1/stacks/{id}` renvoyait 500 (`AttributeError`) : `StackService.delete()` était appelée mais n'existait pas — méthode ajoutée (pattern `TargetService.delete`), `type: ignore` masqueur retiré.
- `DeploymentService.update_status` levait `TypeError` (soustraction naive/aware) sur toute transition RUNNING → FAILED/STOPPED avec `deployed_at` défini : `stopped_at` et le calcul de durée passés en naïf UTC cohérent avec les colonnes DateTime SQLite.

- **STORY-125.1 — Socle audit trail** (P1-4, partie socle — EPIC-012) : table `audit_logs` et service central d'audit.
  - Table `audit_logs` + modèle `AuditLog` et migration Alembic `1251_audit_logs` — FK `SET NULL` sur `users`/`organizations` (conservation documentaire : la trace survit à la suppression de son acteur), colonnes `correlation_id` (indexée — recherche d'incident par requête) et `organization_id` au-delà de la spec 06, `details` JSON natif, index composite `idx_audit_resource`.
  - `AuditService` : écriture **best-effort** ne levant jamais (`audit.write_failed` loggé sans le contenu de `details`), masquage systématique à l'écriture par `_sanitize_details` (clés password/token/secret/key/credential/authorization/cookie → `***`, récursif, troncature 512), `log_from_request()` extrayant IP/correlation_id du middleware, consultation filtrée paginée `list_entries()`, purge `purge_expired()` (no-op si rétention None).
  - Config rétention : `AUDIT_RETENTION_DAYS` (défaut None = conservation indéfinie, spec 15) + `AUDIT_PURGE_INTERVAL_HOURS` (24) ; schemas Pydantic en lecture seule (`AuditLogResponse`, `AuditLogListResponse`) — l'audit n'est pas inscriptible par API.
  - L'émission sur les actions critiques (STORY-125.2) et l'endpoint `GET /admin/audit` + purge périodique (STORY-125.3) suivent.
- **STORY-124 — Clés API `wf_ak_`** (P1-3, partie clés API — EPIC-012) : authentification par clé API coexistant avec JWT.
  - Table `api_keys` + modèle `APIKey` et migration Alembic `1241_api_keys` (STORY-124.1) — hash uniquement en base, FK CASCADE, expiration optionnelle, révocation distincte de l'expiration.
  - `ApiKeyService` : génération `wf_ak_` + 48 caractères (`secrets.token_urlsafe`), hash déterministe Argon2 (sel dérivé HMAC-SHA256, lookup par hash — arbitrage F2/STORY-123, divergence « bcrypt » des specs consignée pour STORY-252), création/liste/révocation idempotente/vérification ; schemas Pydantic n'exposant jamais `key_hash` ni la clé brute (affichage unique à la création) (STORY-124.2).
  - Endpoints `POST/GET/DELETE /auth/api-keys` (201 + clé affichée une seule fois, liste sans secrets, révocation scoped 404 sur clé étrangère, rate limiting) et auth par clé dans `get_current_user` via `X-API-Key` ou `Authorization: Bearer wf_ak_…` — résolue avant la voie JWT, RBAC du propriétaire appliqué à l'identique, `last_used_at` throttlé (1 écriture/min/clé) (STORY-124.3).
  - Tests transverses de sécurité : 401/403/422/404, RBAC viewer par clé, isolation multi-users, aucune clé ni hash dans réponses/logs/base, révocation immédiate de bout en bout — 78 tests auth/API keys verts (STORY-124.4).

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
