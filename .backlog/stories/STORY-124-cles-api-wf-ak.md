# STORY-124 : Clés API `wf_ak_` — table `api_keys`, auth `X-API-Key` coexistant avec JWT (P1-3, partie clés API)

**Statut :** DONE
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-3 partie clés API (axe A5, rapport §2) — ampleur **M** (partie clés API de l'item L)

## Description

En tant qu'utilisateur de WindFlow, je veux pouvoir créer des clés API préfixées `wf_ak_` (hashées en base, révocables, avec expiration optionnelle) qui m'authentifient sur les routes API via le header `X-API-Key` (ou `Authorization: Bearer wf_ak_…`), afin de scripter la CLI et les intégrations tierces sans manipuler de JWT courts.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §2, §7.4, §14) : aucune table `api_keys`, aucun endpoint de gestion ; [`auth/dependencies.py`](../../backend/app/auth/dependencies.py:23) n'accepte que les JWT. La spec exige des clés `wf_ak_` + 48 caractères aléatoires (`secrets.token_urlsafe`), hash bcrypt stocké, affichage unique, révocation immédiate.

## Contexte technique

### Analyse exploratoire (analyse-story — 2026-09-13)

**Couches impactées :** Backend uniquement — models, migration Alembic, schemas, service, endpoints, dépendance `get_current_user`. CLI/frontend explicitement hors périmètre (la story les qualifie de « plus », aucun AC ne les exige).

**État actuel vérifié (grep sur `backend/`) :** aucune table `api_keys`, aucun modèle `APIKey`, aucun endpoint `/auth/api-keys`, aucun support `X-API-Key` — les seules occurrences `api_key` du code concernent les clés providers LiteLLM et les configs plugins (sans rapport). Périmètre 100 % à créer.

**Chaîne Alembic actuelle :** `baseline → 1211_user_organizations → 1213_users_org_migration → 1231_refresh_tokens` (head) — la migration `api_keys` devra chaîner sur `1231_refresh_tokens`.

**Fichiers de référence (patterns validés par STORY-123) :**
- Modèle → pattern [`backend/app/models/refresh_token.py`](../../backend/app/models/refresh_token.py) : PK `String(36)` UUID, FK `users.id` `ondelete=CASCADE`, colonnes indexées, docstring de sécurité, `__repr__` sans secret
- Migration → pattern [`backend/alembic/versions/2026_09_12_1231_refresh_tokens_table.py`](../../backend/alembic/versions/2026_09_12_1231_refresh_tokens_table.py) : strictement additive, `batch_alter_table` pour les index, commentaires de colonnes
- Service → pattern [`backend/app/services/refresh_token_service.py`](../../backend/app/services/refresh_token_service.py) : classe statique async, hash **déterministe** (sel dérivé du token par HMAC-SHA256 de la clé serveur → lookup `WHERE key_hash = :h` possible), validation de forme **avant** hachage (anti-DoS, `MAX_TOKEN_LENGTH`), logs sans valeurs sensibles, `_as_utc`/`_utcnow_naive` pour SQLite naive
- Génération → pattern [`backend/app/auth/jwt.py`](../../backend/app/auth/jwt.py) (`generate_refresh_token` : `secrets.token_urlsafe` + préfixe `wf_rt_`) — à décliner en `wf_ak_` + 48 caractères aléatoires
- Schemas → pattern [`backend/app/schemas/user.py`](../../backend/app/schemas/user.py) : séparation Create/Response, `ConfigDict` + exemples OpenAPI, `from_attributes=True`
- Endpoints → pattern [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py) : docstring OpenAPI riche, `conditional_rate_limiter`, mapping exception métier → 401 générique (`from None`)
- Exception → pattern `InvalidRefreshTokenError` ([`backend/app/core/exceptions.py`](../../backend/app/core/exceptions.py)) : refus sémantique 401 sans divulgation (anti-énumération)
- Tests → pattern [`backend/tests/unit/test_api/test_auth_refresh_security.py`](../../backend/tests/unit/test_api/test_auth_refresh_security.py) : fixture `_jwt_mode` (monkeypatch `disable_auth=False`), 401 paramétrés, vérification hash jamais en clair en base, isolation multi-users

**Exigences sécurité identifiées (Phase 2.6) :**
- **Auth :** oui — `get_current_user` ([`backend/app/auth/dependencies.py`](../../backend/app/auth/dependencies.py)) doit lire `X-API-Key` **ou** `Authorization: Bearer wf_ak_…` **avant** la voie JWT ; clé préfixée `wf_ak_` → jamais soumise au décodeur JWT ; utilisateur désactivé → 401 ; `last_used_at` alimenté sans bloquer la réponse ; mode `disable_auth` inchangé
- **RBAC :** une clé porte les permissions de son propriétaire — aucun changement à `require_role` ([`backend/app/auth/rbac.py`](../../backend/app/auth/rbac.py)) : la dépendance s'exécute après résolution utilisateur, qu'elle vienne d'un JWT ou d'une clé ; viewer par clé sur endpoint modifiant → 403
- **Hash — point d'arbitrage pour split-story :** spec 06/07 disent « hash bcrypt », mais l'arbitrage F2/STORY-123 a retenu Argon2 déterministe (sel dérivé HMAC) via `pwd_context` pour le lookup par hash — recommandé d'**aligner les clés API sur le pattern STORY-123** (Argon2 déterministe) en le documentant comme consolidation de spec (même garantie unilatérale, bcrypt étant déprécié côté passlib) ; le lookup par hash impose un hash déterministe, incompatible avec un sel bcrypt aléatoire sans scanner toute la table
- **Exposition :** `APIKeyResponse` n'expose jamais `key_hash` ni la clé ; clé brute **uniquement** dans la réponse 201 du POST (affichage unique) ; révocation immédiate = vérification en base à chaque requête (pas de cache long sur les clés)
- **Isolation :** liste/révocation scoped `user_id == current_user.id` — clé étrangère → 404 (ne pas révéler l'existence)
- **Audit :** logs `api_key.created / revoked / auth_failed` avec `user_id` + `key_id` uniquement — jamais la clé ni son hash (rules 40)
- **Rate limiting :** `conditional_rate_limiter` sur POST/DELETE `/auth/api-keys` (pattern auth.py)

### Évaluation de complexité — STORY-124 (Phase 2.5)

**Critères remplis :**
- [x] > 5 tâches identifiées → **Oui — 7 tâches** (voir tâches brutes ci-dessous)
- [x] > 6 fichiers impactés → **Oui — 8 fichiers hors tests** : `models/api_key.py` (créer), `models/__init__.py` (modifier), `models/user.py` (modifier — relation `api_keys`), migration Alembic (créer), `schemas/api_key.py` (créer), `services/api_key_service.py` (créer), `api/v1/auth.py` (modifier), `auth/dependencies.py` (modifier) — + ~3 fichiers de tests
- [ ] Backend + Frontend ou CLI → Non (backend pur)
- [ ] > 8 AC → Non (4 AC)

**Verdict : COMPLEXE** — 2 critères déclencheurs remplis. Découpe à déléguer à la skill `split-story` (mode proactif — story TODO).

**Tâches brutes identifiées (non finales — entrée pour split-story) :**
1. Modèle `APIKey` (`backend/app/models/api_key.py`, pattern refresh_token.py) + export dans `models/__init__.py` + relation `User.api_keys` dans `models/user.py` — schéma spec 06 : `id, user_id FK CASCADE, name VARCHAR(100), key_hash VARCHAR(255), expires_at null, last_used_at null, revoked bool default false, created_at` + index `user_id`
2. Migration Alembic table `api_keys` chaînée sur `1231_refresh_tokens` (strictement additive)
3. Génération `wf_ak_` + 48 caractères (`secrets.token_urlsafe`) + hash déterministe + schemas Pydantic (`backend/app/schemas/api_key.py` : `APIKeyCreate{name 1-100, expires_at optionnelle}, APIKeyCreated{clé brute affichée une seule fois}, APIKeyResponse{id, name, expires_at, last_used_at, revoked, created_at}` — jamais `key_hash`)
4. Service `ApiKeyService` (`backend/app/services/api_key_service.py`, pattern refresh_token_service.py) : `create` (génère+hash+persist), `list_for_user`, `revoke` (scoped user, idempotent), `verify` (résolution par hash, refus révoquée/expirée/utilisateur inactif, update `last_used_at`)
5. Endpoints `POST /auth/api-keys` (201 + clé en clair une seule fois), `GET /auth/api-keys` (liste sans secrets), `DELETE /auth/api-keys/{id}` (révocation, 404 sur clé étrangère) dans `api/v1/auth.py` — auth via `get_current_active_user`, rate limiting, OpenAPI documenté
6. Intégration auth par clé dans `get_current_user` (`auth/dependencies.py`) : header `X-API-Key` ou `Bearer wf_ak_…` → `ApiKeyService.verify` → User propriétaire ou 401 ; fallback JWT sinon ; `last_used_at` mis à jour
7. Tests : service (`backend/tests/unit/test_services/test_api_key_service.py`), API + sécurité transverse (`backend/tests/unit/test_api/test_api_keys.py`) : 401 sans clé / clé invalide / révoquée / expirée / utilisateur désactivé, 403 RBAC viewer par clé, 422 création invalide, 404 clé étrangère, hash jamais en clair en base, aucune clé/hash dans réponses ni logs, `last_used_at` alimenté, révocation immédiate effective

Éléments existants à réutiliser / contraintes :
- Schéma cible spec 06 : `api_keys (id, user_id FK CASCADE, name VARCHAR(100), key_hash VARCHAR(255), expires_at TIMESTAMP null, last_used_at, revoked BOOLEAN DEFAULT FALSE, created_at)` + index `user_id` ;
- Endpoints spec 09 § Authentification : `POST /auth/api-keys` (création → **affichage unique** de la clé complète), `GET /auth/api-keys` (liste **sans jamais** la clé ni son hash), `DELETE /auth/api-keys/{id}` (révocation) ;
- Auth : `get_current_user` ([`auth/dependencies.py`](../../backend/app/auth/dependencies.py:23)) doit accepter JWT **ou** clé API — header `X-API-Key` **ou** `Authorization: Bearer wf_ak_…` (les deux formes spécifiées) ; résolution par comparaison de hash bcrypt ; utilisateur désactivé → refus ; `last_used_at` mis à jour ;
- **RBAC s'applique** : une clé API porte les permissions de son propriétaire — `require_role(...)` (STORY-122) s'exécute après authentification par clé ; une clé n'est jamais un contournement du RBAC ;
- Révocation immédiate : `revoked=true` ou expiration → `401` instantané (pas de cache long sur les clés révoquées) ;
- La CLI peut s'appuyer sur les clés API (`windflow auth login --api-key`, `WINDFLOW_API_KEY` — spec 10) : côté frontend/CLI, l'adaptation est un plus, le cœur de la story est backend.

## Critères d'acceptation (AC)

- [x] AC 1 : La table `api_keys` existe via migration Alembic (STORY-120) conformément au schéma spec 06 ; la création génère `wf_ak_` + 48 caractères (`secrets.token_urlsafe`), stocke **uniquement le hash bcrypt** (jamais la clé), et retourne la clé complète **une seule fois** à la création ; expiration configurable à la création (null = n'expire jamais). *(validé par STORY-124.1 DONE + démontré par 124.2/124.3 — hash Argon2 déterministe, arbitrage F2 consigné pour STORY-252)*
- [x] AC 2 : Une clé `wf_ak_...` **authentifie** via `X-API-Key` (et `Authorization: Bearer wf_ak_…`) sur les routes API protégées, avec les permissions RBAC du propriétaire appliquées (STORY-122) ; clé invalide/révoquée/expirée → `401` ; `last_used_at` alimenté. *(validé par STORY-124.2/124.3 DONE — RBAC propriétaire garanti par `require_role` inchangé ; tests sécurité systématiques en 124.4)*
- [x] AC 3 : **Révocation immédiate** : `DELETE /auth/api-keys/{id}` → les requêtes suivantes avec cette clé → `401` ; `GET /auth/api-keys` liste les clés (nom, dates, statut) **sans exposer** clé, hash ni secret. *(validé par STORY-124.3 DONE)*
- [x] AC 4 : Tests de sécurité obligatoires : `401` sans clé ; clé d'un utilisateur désactivé → `401` ; `403` lorsque le RBAC du propriétaire refuse (viewer sur endpoint modifiant) ; `422` sur body de création invalide ; isolation — un user ne liste/révoque que **ses** clés (`404`/`403` sur clé étrangère) ; aucune clé ni hash dans les réponses ni les logs. *(validé par STORY-124.4 DONE — traçabilité AC↔tests dans la sous-story)*

## Références spécification

- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Authentification par clé API (format `wf_ak_`, hash bcrypt, affichage unique, expiration, révocation), § Validation des tokens dans l'API (JWT ou clé API, `X-API-Key`) ;
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités auth et audit → `APIKey` (schéma SQL) ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Authentification (`POST/GET /auth/api-keys`, `DELETE /auth/api-keys/{id}`), § Authentification (Bearer JWT ou `wf_ak_`) ;
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — la matrice s'applique à l'identique après auth par clé ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §2, §7.4, §14 (aucune clé API existante) ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-3 (partie clés API), §2.A A5.

## Dépendances

- **STORY-120** (migration de la table `api_keys`) ; **STORY-122** (le RBAC `require_role` s'applique aux requêtes authentifiées par clé — coexiste avec JWT).

## Sous-stories

> Découpe proactive réalisée le 2026-09-13 par `split-story` (complexité détectée par `analyse-story` Phase 2.5 : 7 tâches / 8 fichiers hors tests). Ordre d'implémentation : 124.1 → 124.2 → 124.3 → 124.4.

- [x] STORY-124.1 : Modèle `APIKey` et migration Alembic — Couvre AC 1 (part structurelle)
- [x] STORY-124.2 : `ApiKeyService` — génération `wf_ak_`, hash déterministe et schemas — Couvre AC 2 (part mécanique)
- [x] STORY-124.3 : Endpoints `/auth/api-keys` et auth par clé dans `get_current_user` — Couvre AC 3 et démontre AC 1/AC 2 de bout en bout
- [x] STORY-124.4 : Tests transverses et sécurité des clés API — Couvre AC 4

## État d'avancement technique

> ⚠️ L'avancement technique est désormais suivi dans les sous-stories individuelles.

**Progression :** 4/4 sous-stories terminées
- [x] STORY-124.1 : Modèle `APIKey` et migration Alembic
- [x] STORY-124.2 : `ApiKeyService` — génération `wf_ak_`, hash déterministe et schemas
- [x] STORY-124.3 : Endpoints `/auth/api-keys` et auth par clé dans `get_current_user`
- [x] STORY-124.4 : Tests transverses et sécurité des clés API

## Tâches d'implémentation détaillées

> ⚠️ Cette story a été découpée en sous-stories avant implémentation (complexité détectée par analyse-story).
> Toutes les tâches ont été redistribuées dans les sous-stories listées ci-dessus.
> Consulter chaque sous-story pour les tâches détaillées.

## Tests à écrire

> ⚠️ Les tests sont désormais définis dans les sous-stories individuelles.

## Notes d'implémentation

> Consignées à la finalisation du bloc (`finalise-story`, 2026-09-25) — le détail complet figure dans les Notes d'implémentation de chaque sous-story (124.1 : 2026-09-13, 124.2 : 2026-09-15, 124.3 : 2026-09-16, 124.4 : tests transverses).

### Fichiers modifiés/créés (consolidé depuis les sous-stories)

- `backend/app/models/api_key.py` — **créé** (124.1) : modèle `APIKey` (schéma spec 06, FK CASCADE, index `user_id`, docstring « hash uniquement »)
- `backend/app/models/user.py` — **modifié** (124.1) : relation `api_keys` (`cascade="all, delete-orphan"`)
- `backend/app/models/__init__.py` — **modifié** (124.1) : export `APIKey` (`Base.metadata`)
- `backend/alembic/versions/2026_09_13_1241_api_keys_table.py` — **créé** (124.1) : migration additive `1241_api_keys` (`down_revision = "1231_refresh_tokens"`)
- `backend/app/auth/jwt.py` — **modifié** (124.2) : `API_KEY_PREFIX`, `MAX_API_KEY_LENGTH`, `generate_api_key()` (`wf_ak_` + 48 car.)
- `backend/app/schemas/api_key.py` — **créé** (124.2) : `APIKeyCreate` / `APIKeyResponse` / `APIKeyCreated` (jamais `key_hash`)
- `backend/app/core/exceptions.py` — **modifié** (124.2) : `InvalidApiKeyError` (401 générique anti-énumération)
- `backend/app/services/api_key_service.py` — **créé** (124.2) : `create` / `list_for_user` / `revoke` / `verify`, hash déterministe Argon2
- `backend/app/api/v1/auth.py` — **modifié** (124.3) : endpoints `POST/GET/DELETE /auth/api-keys` (201 affichage unique, rate limiting)
- `backend/app/auth/dependencies.py` — **modifié** (124.3) : voie clé API dans `get_current_user` (`X-API-Key` / `Bearer wf_ak_…` résolus avant la voie JWT)
- Tests : `backend/tests/unit/test_models/test_api_key.py` (13 tests, 124.1), `backend/tests/unit/test_services/test_api_key_service.py` (16 tests, 124.2), `backend/tests/unit/test_api/test_api_keys.py` (15 tests en 124.3 + 6 transverses en 124.4 = 21 tests) ; adaptations `test_alembic_config.py`, `test_migrations.py`, `test_database.py` (124.1) et `test_rbac_exhaustivite.py` (garde-fou routes auth 5→8, 124.3)

### Décisions techniques (synthèse)

- **Hash Argon2 déterministe** (sel dérivé HMAC-SHA256 de la clé serveur) et non bcrypt : imposé par le lookup `WHERE key_hash = :h` — arbitrage F2/STORY-123, divergence des specs 06/07 consignée pour STORY-252
- **`last_used_at` throttlé** : 1 écriture/minute/clé max, best-effort hors du chemin critique de `verify`
- **Clés expirées listées** avec `expires_at` visible, `revoked` distinct de l'expiration
- **RBAC inchangé** : `require_role` s'exécute après résolution utilisateur — la clé porte les permissions du propriétaire (jamais un contournement)
- **401/404 génériques** anti-énumération ; logs `api_key.*` avec `user_id`/`key_id` uniquement

### Validation de clôture (finalise-story, 2026-09-25)

- Tests ciblés du bloc (`.venv-test`, Python 3.11.10) : **78 passed** — `test_api_keys.py` 21 + `test_api_key_service.py` 16 + `test_auth_refresh_security.py` 8 + `tests/unit/test_auth/` 33
- Lint isort/black/flake8 : **OK** sur les 7 fichiers du bloc (`test_api_keys.py`, `api_key_service.py`, `auth.py`, `dependencies.py`, `api_key.py` schemas, `api_key.py`/`user.py` models)
- Suite unitaire complète : 1447 passed / **35 failed pré-existants à HEAD** (endpoints stacks : `test_stack_actions.py`, `test_stacks_archive.py`, `test_stacks_duplicate.py`… — vérifiés identiques via `git stash` en 124.4, hors périmètre STORY-124)
