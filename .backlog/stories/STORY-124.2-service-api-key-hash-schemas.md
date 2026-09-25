# STORY-124.2 : `ApiKeyService` — génération `wf_ak_`, hash déterministe et schemas

**Statut :** DONE
**Story Parente :** STORY-124 — Clés API `wf_ak_` — table `api_keys`, auth `X-API-Key` coexistant avec JWT (P1-3, partie clés API)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'utilisateur de WindFlow, je veux que la création d'une clé API génère une valeur `wf_ak_` + 48 caractères aléatoires dont seul le **hash déterministe** est stocké en base (rendant la clé lookup-able par hash), avec des schemas Pydantic n'exposant jamais `key_hash` ni la clé brute hors création, et un service portant création / liste / révocation / vérification (refus des clés invalides, révoquées, expirées, propriétaire inactif ; `last_used_at` alimenté sans pénaliser les réponses), afin que STORY-124.3 (endpoints + `get_current_user`) dispose de toute la mécanique métier des clés API.

Deuxième étape de STORY-124 (découpe proactive : 7 tâches / 8 fichiers) : s'appuie sur le modèle `APIKey` et la migration posés par STORY-124.1 ; prépare STORY-124.3 (endpoints `/auth/api-keys` + intégration auth) et STORY-124.4 (tests transverses et sécurité).

## Critères d'acceptation (AC)

- [x] AC 2 : Une clé `wf_ak_...` **authentifie** via `X-API-Key` (et `Authorization: Bearer wf_ak_…`) sur les routes API protégées, avec les permissions RBAC du propriétaire appliquées (STORY-122) ; clé invalide/révoquée/expirée → `401` ; `last_used_at` alimenté. *(part mécanique validée dans cette sous-story : `ApiKeyService.verify` — refus invalide/révoquée/expirée/utilisateur inactif + `last_used_at` throttlé ; l'authentification de bout en bout sur les routes protégées avec RBAC est portée par STORY-124.3 et démontrée par STORY-124.4)*

> **Note de découpe :** cette sous-story couvre la part **mécanique** de l'AC 2 (génération, hash déterministe, `verify`, `last_used_at`). La part « authentifie via `X-API-Key` / `Authorization: Bearer wf_ak_…` sur les routes protégées, RBAC du propriétaire » est implémentée par STORY-124.3 (`dependencies.py`) et validée transversalement par STORY-124.4 — l'AC n'est cochable sur la story parente qu'une fois les sous-stories fermées.

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-13) — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches.

**Couches impactées :** Backend uniquement — auth (génération), schemas, service, exceptions, tests unitaires service. **Aucun endpoint** (reporté à STORY-124.3), aucun impact frontend/CLI.

**Spécifications de référence :**
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Authentification par clé API (format `wf_ak_` + 48 caractères `secrets.token_urlsafe`, hash en base, affichage unique, expiration, révocation) ;
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités auth et audit → `APIKey` ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Authentification (contrats `POST/GET /auth/api-keys`, `DELETE /auth/api-keys/{id}` — consommés par STORY-124.3).

**Fichiers de référence (patterns validés par STORY-123.2) :**
- Génération → pattern [`backend/app/auth/jwt.py`](../../backend/app/auth/jwt.py) (`generate_refresh_token` : `secrets.token_urlsafe` + préfixe `wf_rt_`, constante `MAX_TOKEN_LENGTH`) — à décliner en `wf_ak_` + 48 caractères ;
- Service → pattern [`backend/app/services/refresh_token_service.py`](../../backend/app/services/refresh_token_service.py) : classe statique async, hash **déterministe** (sel dérivé du token par HMAC-SHA256 de la clé serveur → lookup `WHERE key_hash = :h`), validation de forme **avant** hachage (anti-DoS), logs sans valeurs sensibles, `_as_utc`/`_utcnow_naive` pour SQLite naive ;
- Schemas → pattern [`backend/app/schemas/user.py`](../../backend/app/schemas/user.py) : séparation Create/Response, `ConfigDict` + exemples OpenAPI, `from_attributes=True` ;
- Exception → pattern `InvalidRefreshTokenError` ([`backend/app/core/exceptions.py`](../../backend/app/core/exceptions.py)) : refus sémantique 401 sans divulgation (anti-énumération) ;
- Tests service → pattern tests unitaires `RefreshTokenService` (fixtures `db_session`, `test_user` ; mock éventuel du temps).

**Modèle disponible (posé par STORY-124.1) :** `APIKey` — `id, user_id FK CASCADE, name VARCHAR(100), key_hash VARCHAR(255), expires_at null, last_used_at null, revoked bool default false, created_at` + index `user_id`.

## ⚖️ Arbitrages tranchés (découpe proactive `split-story`, validés par l'utilisateur le 2026-09-13)

1. **Hash — Argon2 déterministe** (recommandation retenue) : aligné sur l'arbitrage **F2/STORY-123** — le lookup par hash (`WHERE key_hash = :h`) impose un hash **déterministe** (sel dérivé du token par HMAC-SHA256 de la clé serveur, pattern `refresh_token_service.py`) ; bcrypt à sel aléatoire rendrait la recherche impossible sans scanner toute la table. La mention « hash bcrypt » des specs 06/07 et de l'AC 1 se lit « hash fort vérifié, jamais la clé en clair » — divergence consignée dans les Notes d'implémentation et pour la correction de spec portée par STORY-252.
2. **Clés expirées restent listées** : `list_for_user` (puis `GET /auth/api-keys`, STORY-124.3) conserve les clés expirées avec `expires_at` visible ; `revoked` reste **distinct** de l'expiration (une clé expirée n'est pas `revoked=true`).
3. **`last_used_at` throttlé** : max **1 écriture/minute par clé**, sans dépendance externe — condition SQL `last_used_at IS NULL OR last_used_at < :now_minus_60s` ; mise à jour best-effort qui ne bloque pas la réponse (jamais dans le chemin critique de `verify`).

## Dépendances

- STORY-124.1 : Modèle `APIKey` et migration Alembic (table disponible).
- Réutilise : arbitrage Argon2 déterministe posé par STORY-123.2 (pattern de hash).
- Bloque : STORY-124.3, STORY-124.4.

## Tâches d'implémentation détaillées

### Tâche 1 : Génération `generate_api_key()` dans `jwt.py`
**Objectif :** Ajouter la fonction de génération des clés API `wf_ak_` + 48 caractères aléatoires, déclinée du pattern `generate_refresh_token`.
**Fichiers :**
- `backend/app/auth/jwt.py` — Modifier — Ajouter :
  - `API_KEY_PREFIX = "wf_ak_"` et `MAX_API_KEY_LENGTH = len(API_KEY_PREFIX) + 48` (constantes de module, exposées pour la validation de forme avant hachage — pattern `MAX_TOKEN_LENGTH`, anti-DoS) ;
  - `generate_api_key() -> str` : `API_KEY_PREFIX + secrets.token_urlsafe(36)` — `token_urlsafe(36)` produit exactement 48 caractères base64url (36 octets × 4/3 = 48) ; docstring précisant que la clé brute n'est **jamais** stockée ni loggée et n'apparaît qu'une seule fois dans la réponse 201 du `POST /auth/api-keys` (STORY-124.3).
**Exigences sécurité :** Entropie ~288 bits (48 caractères urlsafe) ; aucune valeur générée loggée ; la clé `wf_ak_…` ne doit jamais être soumise au décodeur JWT (garantie posée par STORY-124.3 côté `dependencies.py`).
**Dépend de :** STORY-124.1 (aucune pour le code lui-même — dépendance fonctionnelle pour les tests)

### Tâche 2 : Schemas Pydantic `api_key.py`
**Objectif :** Créer les schemas I/O du domaine clés API — jamais `key_hash`, clé brute uniquement dans `APIKeyCreated` (affichage unique).
**Fichiers :**
- `backend/app/schemas/api_key.py` — Créer — (pattern [`backend/app/schemas/user.py`](../../backend/app/schemas/user.py) : `ConfigDict`, exemples OpenAPI, `from_attributes=True`) :
  - `APIKeyCreate(BaseModel)` : `name: str = Field(min_length=1, max_length=100)` (description + exemple) ; `expires_at: Optional[datetime] = None` (null = n'expire jamais — documenté dans la description OpenAPI) ;
  - `APIKeyCreated(APIKeyResponse)` : + `key: str` — **clé brute complète, affichée une seule fois** (réservée à la réponse 201 du POST — avertissement dans la description OpenAPI) ;
  - `APIKeyResponse(BaseModel)` : `id: str`, `name: str`, `expires_at: Optional[datetime]`, `last_used_at: Optional[datetime]`, `revoked: bool`, `created_at: datetime` — **jamais** `key_hash` ni `key` ; `model_config = ConfigDict(from_attributes=True)` ; exemples OpenAPI documentés.
**Exigences sécurité :** Exposition — `APIKeyResponse` n'expose ni `key_hash` ni la clé ; `APIKeyCreated` est le seul schema portant `key` (usage unique création).
**Dépend de :** Aucune

### Tâche 3 : Exception `InvalidApiKeyError` + service `ApiKeyService`
**Objectif :** Créer l'exception métier de refus (401 générique anti-énumération) et le service portant toute la logique métier des clés API, hash déterministe lookup-able et `last_used_at` throttlé.
**Fichiers :**
- `backend/app/core/exceptions.py` — Modifier — Ajouter `InvalidApiKeyError(WindFlowException)` : refus sémantique 401 sans divulgation (pattern `InvalidRefreshTokenError` — ne pas distinguer « clé inconnue » de « clé révoquée/expirée » côté message client).
- `backend/app/services/api_key_service.py` — Créer — (pattern [`backend/app/services/refresh_token_service.py`](../../backend/app/services/refresh_token_service.py) : classe statique async, logs sans valeurs sensibles, `_as_utc`/`_utcnow_naive`) :
  - `_hash_key(key: str) -> str` — **hash déterministe** : sel dérivé du token par HMAC-SHA256 de la clé serveur → hash Argon2 avec ce sel dérivé (pattern refresh_token_service) — rend possible le lookup `WHERE key_hash = :h` (arbitrage n°1) ;
  - `create(db, user_id, data: APIKeyCreate) -> APIKeyCreated` — génère via `generate_api_key()`, hash via `_hash_key`, persist (`expires_at` telle que fournie, null = n'expire jamais), retourne `APIKeyCreated` (clé brute **une seule fois**) ; log `api_key.created` avec `user_id` + `key_id` uniquement ;
  - `list_for_user(db, user_id) -> list[APIKeyResponse]` — scoped `user_id == current_user.id`, ordre `created_at` desc ; **les clés expirées restent listées** avec `expires_at` visible, `revoked` distinct de l'expiration (arbitrage n°2) ;
  - `revoke(db, user_id, key_id) -> APIKeyResponse` — scoped user : clé étrangère/introuvable → `NotFoundError` (→ 404 côté API, sans révéler l'existence) ; **idempotent** (révoquer une clé déjà révoquée = no-op succès, retourne l'état courant) ; log `api_key.revoked` avec `user_id` + `key_id` ;
  - `verify(db, key: str) -> User` — validation de forme **avant** hachage (préfixe `wf_ak_`, longueur `MAX_API_KEY_LENGTH` — anti-DoS), hash + lookup par hash, refus → `InvalidApiKeyError` si : clé inconnue / `revoked` / expirée (`expires_at` passé) / propriétaire inactif (`is_active=False`) ; retourne le `User` propriétaire ; alimente `last_used_at` **throttlé** (arbitrage n°3) : condition SQL `last_used_at IS NULL OR last_used_at < now - 60s`, mise à jour best-effort hors du chemin critique de la réponse ; log `api_key.auth_failed` avec contexte (`user_id` si résolu, raison) — jamais la clé ni son hash.
**Exigences sécurité :** Hash déterministe Argon2 (arbitrage n°1) ; logs `api_key.created / revoked / auth_failed` avec `user_id` + `key_id` uniquement (rules 40 — jamais la clé ni son hash) ; révocation immédiate = vérification en base à chaque requête (pas de cache long) ; refus 401 générique anti-énumération.
**Dépend de :** Tâche 1, Tâche 2, STORY-124.1

### Tâche 4 : Tests unitaires du service
**Objectif :** Couvrir la mécanique du service — génération, hash déterministe lookup-able, refus, throttling `last_used_at`, scoping et idempotence.
**Fichiers :**
- `backend/tests/unit/test_services/test_api_key_service.py` — Créer — Fixtures `db_session`, `test_user` (+ second user pour l'isolation). Détail en section « Tests à écrire ».
**Exigences sécurité :** Assertions « hash ≠ clé en clair », « jamais la clé dans les logs » (caplog), isolation multi-users.
**Dépend de :** Tâche 3

## Tests à écrire

### Backend — unitaires (service)
- `backend/tests/unit/test_services/test_api_key_service.py`
  - `test_create_generates_wf_ak_48_chars` — la clé générée porte le préfixe `wf_ak_` et 48 caractères aléatoires (longueur totale `MAX_API_KEY_LENGTH`)
  - `test_create_stores_hash_not_plaintext` — `key_hash` ≠ clé brute ; la clé n'est stockée nulle part
  - `test_create_hash_is_deterministic_and_lookupable` — deux hash de la même clé sont identiques (sel dérivé) → lookup par hash possible
  - `test_create_with_and_without_expires_at` — `expires_at` fournie persistée ; null = n'expire jamais
  - `test_verify_nominal_returns_active_owner` — clé valide → `User` propriétaire actif ; `last_used_at` alimenté
  - `test_verify_rejects_unknown_key` — clé inconnue → `InvalidApiKeyError`
  - `test_verify_rejects_malformed_key` — forme invalide (mauvais préfixe/longueur) rejetée **avant** hachage (anti-DoS)
  - `test_verify_rejects_revoked_key` — clé révoquée → `InvalidApiKeyError`
  - `test_verify_rejects_expired_key` — `expires_at` passé → `InvalidApiKeyError`
  - `test_verify_rejects_inactive_owner` — propriétaire `is_active=False` → `InvalidApiKeyError`
  - `test_last_used_at_throttled` — deux `verify` dans la même minute → une seule écriture de `last_used_at`
  - `test_revoke_scoped_and_idempotent` — révocation par le propriétaire OK ; clé étrangère → `NotFoundError` ; re-révocation = succès no-op
  - `test_list_for_user_scoped_and_keeps_expired` — un user ne voit que ses clés ; les clés expirées restent listées avec `expires_at` visible et `revoked=False`
  - `test_no_key_or_hash_in_logs` — caplog : jamais la clé brute ni son hash dans les logs des opérations create/revoke/verify

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_services/test_api_key_service.py -v
make backend-lint && make backend-typecheck
```

## État d'avancement technique
- [x] Tâche 1 : `generate_api_key()` + constantes dans `jwt.py`
- [x] Tâche 2 : Schemas Pydantic `api_key.py`
- [x] Tâche 3 : `InvalidApiKeyError` + `ApiKeyService`
- [x] Tâche 4 : Tests unitaires du service

## Notes d'implémentation

**Date :** 2026-09-15

### État initial trouvé

Travail **partiellement implémenté sur disque** (non-tracké git, comme pour 124.1) : Tâches 1-3 déjà conformes aux specs de la story (`generate_api_key` + constantes dans `jwt.py`, schemas `api_key.py`, `InvalidApiKeyError` + service complet), fichier de tests déjà écrit mais **non exécuté** et Tâche 4 non cochée. Cette session a : vérifié la conformité disque ↔ story tâche par tâche, corrigé une coquille de docstring, reformaté au standard black, exécuté et validé toute la suite de tests, et mené les vérifications lint/typecheck/non-régression.

### Fichiers modifiés/créés

- [`backend/app/auth/jwt.py`](../../backend/app/auth/jwt.py) : + `API_KEY_PREFIX`, `MAX_API_KEY_LENGTH`, `generate_api_key()` (Tâche 1 — pré-existant sur disque, vérifié conforme)
- [`backend/app/schemas/api_key.py`](../../backend/app/schemas/api_key.py) : création `APIKeyCreate` / `APIKeyResponse` / `APIKeyCreated` (Tâche 2 — vérifié conforme + reformaté black)
- [`backend/app/core/exceptions.py`](../../backend/app/core/exceptions.py) : + `InvalidApiKeyError(WindFlowException)` (Tâche 3 — vérifié conforme)
- [`backend/app/services/api_key_service.py`](../../backend/app/services/api_key_service.py) : création `ApiKeyService` — `create` / `list_for_user` / `revoke` / `verify` / `_touch_last_used`, hash déterministe Argon2 à sel dérivé HMAC-SHA256 (Tâche 3 — vérifié conforme, coquille docstring corrigée, reformaté black)
- [`backend/tests/unit/test_services/test_api_key_service.py`](../../backend/tests/unit/test_services/test_api_key_service.py) : 16 tests couvrant les 14 cas listés + 2 bonus sécurité (Tâche 4 — exécutés et validés cette session, reformatés black)

### Décisions techniques

- **Hash déterministe Argon2** (arbitrage n°1) : réutilise le `pwd_context` passlib existant (`user_service.py`) avec sel de 16 octets dérivé par HMAC-SHA256 de `jwt_secret_key` — zéro dépendance nouvelle, lookup `WHERE key_hash = :h` possible, divergence « bcrypt » des specs 06/07 consignée pour STORY-252.
- **`verify` en une requête jointe** `select(APIKey, User).join(...)` avec `populate_existing=True` — évite un second round-trip et contourne l'identity map SQLAlchemy en async.
- **`last_used_at` throttlé best-effort** (arbitrage n°3) : `UPDATE ... WHERE last_used_at IS NULL OR last_used_at < now-60s`, échec avalé (log warning `api_key.last_used_update_failed`, jamais la clé) — hors chemin critique de `verify`.
- **Refus anti-énumération** : message client unique (« Invalid API key ») quel que soit le motif (inconnue/révoquée/expirée/inactive) ; la raison fine n'existe que dans les logs serveur (`api_key.auth_failed ... reason=...`).

### Divergences par rapport à l'analyse

- Aucune divergence fonctionnelle. Détails d'exécution :
  - black a reformaté 3 fichiers (largeur 88 — retours à la ligne uniquement, aucun changement sémantique).
  - La couverture stricte `--cov=app` du `addopts` pyproject mesure tout le backend (31% global au moment de la session) — la mesure pertinente ciblée sur les fichiers de la story donne **97,48%** (service 99%, schemas 100%, jwt.py 94% en combinant la suite STORY-123).

### Difficultés rencontrées

- **35 échecs apparents** dans la suite unitaire complète (`test_stacks_*` etc., 500 au lieu de 401) : diagnostiqués via worktree git propre (tests passants au HEAD) puis reproduction hors pytest — cause racine = `.env` local du workspace avec `DISABLE_AUTH=true` (le fallback dev de `dependencies.py` cherche un superadmin inexistant → 500). **Sans lien avec STORY-124.2** ; avec `DISABLE_AUTH=false` la suite complète passe : **1461 passed / 0 failed**. Correctif environnement local à considérer hors story (le `.env` de dev local pollue les runs pytest).
- mypy signale 1 erreur dans `docker_client_service.py:693` — pré-existente au HEAD (vérifiée worktree propre), hors périmètre story ; les 4 fichiers de la story sont propres.

### Tests ajoutés

- `backend/tests/unit/test_services/test_api_key_service.py` : **16 tests** (5 classes : create/verify/revoke/list/logs+schemas) — couverture fichiers story **97,48%** (cible ≥ 80% atteinte), assertions caplog « jamais la clé ni son hash dans les logs », isolation multi-users, idempotence révocation, throttling `last_used_at`, expiré ≠ révoqué.

### Résultats de validation

- `pytest backend/tests/unit/test_services/test_api_key_service.py` : **16 passed**
- `pytest backend/tests/unit` (env `DISABLE_AUTH=false`) : **1461 passed, 0 failed** — pas de régression
- Couverture ciblée (service + schemas + jwt) : **97,48%** ≥ 80% ✅
- `black --check` + `isort --check` + `flake8` sur les 5 fichiers touchés : **OK**
- `mypy` ciblé : fichiers story propres (1 erreur pré-existante hors périmètre dans `docker_client_service.py`)
