# STORY-168 : Cache avec fallback mémoire — interface unique get/set/delete + TTL, Redis si configuré sinon mémoire locale, utilisée par rate limiter, plugin registry et caches divers (P2-8 — axes C7, E4)

**Statut :** REVIEW
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-8 (axes C7, E4, rapports §6) — ampleur **M**

## Description

En tant que développeur backend WindFlow, je veux une **interface de cache unique** (get/set/delete avec TTL) instanciée avec Redis quand il est configuré et un fallback mémoire locale sinon — consommée par le rate limiter, le plugin registry (cache TTL 300 s), le cache RBAC et les caches divers — afin de supprimer les dégradations silencieuses en no-op et les implémentations de cache dispersées, avec un warning explicite en mode dégradé.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §10.1, §14.2) : sans Redis, [`rate_limit.py:43`](../../backend/app/core/rate_limit.py:43) est un **no-op** (le fallback mémoire dédié de STORY-102 traite le login mais pas les autres limiteurs) ; le plugin registry porte son propre cache TTL ([`plugin_registry_service.py:23`](../../backend/app/services/plugin_registry_service.py:23)) ; l'ABC [`CacheManager`](../../backend/app/core/abstractions.py:13) est un contrat **non consommé** (E4 : « ressusciter `CacheManager` via C7 ») ; le plan exige un `core/cache.py` unique avec TTL mémoire et warning de dégradation.

## Contexte technique

*(AnalyseStory — analyse du 2026-10-30)*

### Inventaire de l'existant (points d'ancrage)

**Socle déjà livré — germe de l'interface unique :**
- [`core/cache.py`](../../backend/app/core/cache.py) (posé par STORY-122.1) contient déjà : `RoleCacheProtocol` (get/set/delete/clear_prefix), `MemoryRoleCache` ([dict process-local + horloge monotone + purge paresseuse](../../backend/app/core/cache.py:66)), `RedisRoleCache` ([redis.asyncio, TTL native `ex=`, fallback mémoire **par opération**, `publish` best-effort](../../backend/app/core/cache.py:114)) et la factory singleton [`get_role_cache()`](../../backend/app/core/cache.py:197) (import conditionnel redis → ping → mémosation, `reset_role_cache()` pour les tests). **C'est la base à généraliser** : valeurs `str` → `Any`, URL `rate_limit_storage_url` → résolution unifiée.
- ABC [`CacheManager`](../../backend/app/core/abstractions.py:53) (get/set/delete/clear/exists/health_check) : contrat **non consommé** (E4) que les implémentations unifiées devront concrétiser (subclassing). `DatabaseManager` ([`core/abstractions.py:13`](../../backend/app/core/abstractions.py:13)) est hors périmètre (statué par P3-1 / STORY-250).
- Pattern factory Redis + `_safe_redis_url` (masquage des credentials dans les logs, règles 40) déjà éprouvé dans [`core/events.py:599`](../../backend/app/core/events.py:599) (`init_event_bus`, setting `cache_url`) — même mécanique à mutualiser.

**Consommateurs — état des lieux réel :**
- **Rate limiter** ([`core/rate_limit.py`](../../backend/app/core/rate_limit.py)) : STORY-102 **déjà livrée** — [`MemoryRateLimiter`](../../backend/app/core/rate_limit.py:34) (fenêtre glissante deque + purge amortie) + [`conditional_rate_limiter`](../../backend/app/core/rate_limit.py:153) en 3 modes (fastapi-limiter Redis / mémoire effective avec warning unique / no-op explicite si disabled). Le no-op est **déjà éradiqué** ; reste à mutualiser détection d'URL + warning unique avec le cache (suppression de la double implémentation d'infra mémoire).
- **Plugin registry** ([`plugin_registry_service.py:37`](../../backend/app/services/plugin_registry_service.py:37)) : cache maison `_cached_index` + `_cache_timestamp` (TTL `plugin_registry_cache_ttl` = 300 s, timeout fetch 10 s) + fallback « index expiré servi sur erreur fetch » — à migrer sur l'interface unique.
- **RBAC** ([`authorization_service.py:98`](../../backend/app/services/authorization_service.py:98)) : consomme déjà `get_role_cache()` (clé `rbac:role:{user_id}`, TTL `rbac_role_cache_ttl` = 300 s, `invalidate_user_role_cache` + `publish` si instance Redis) — migration quasi gratuite via la généralisation.
- **Cache divers identifié** : [`litellm_service.py:60`](../../backend/app/services/litellm_service.py:60) — `self._cache: Dict[str, Any]` **sans TTL ni borne** (fuite mémoire potentielle — cible AC 4) ; **aucun test litellm n'existe** (risque à couvrir).
- Initialisation lifespan : [`main.py:157`](../../backend/app/main.py:157) initialise fastapi-limiter (client Redis dédié sur `rate_limit_storage_url`) et le ferme à l'extinction — le client du cache unifié devra être fermé aussi.

**Compatibilité à préserver (contrainte forte)** : ~30 fichiers de tests importent `from app.core.cache import reset_role_cache` via fixtures autouse (ex : [`test_rbac_matrix_consolidated.py:34`](../../backend/tests/unit/test_api/test_rbac_matrix_consolidated.py:34)) ; `MemoryRoleCache`/`RedisRoleCache`/`get_role_cache` sont importés par [`test_core/test_cache.py`](../../backend/tests/unit/test_core/test_cache.py) et `authorization_service.py`. La généralisation **doit conserver ces noms** (aliases/wrappers).

**Configuration** : `cache_url` ([`config.py:351`](../../backend/app/config.py:351), posé par STORY-162 — commentaire « réutilisée par STORY-168 ») ; `rate_limit_storage_url` ([`config.py:413`](../../backend/app/config.py:413)) ; `rbac_role_cache_ttl` ([`config.py:422`](../../backend/app/config.py:422), 300 s) ; `plugin_registry_cache_ttl` ([`config.py:515`](../../backend/app/config.py:515), 300 s). `env.example` documente `RATE_LIMIT_STORAGE_URL` mais pas encore `CACHE_URL` pour le cache partagé.

**Sécurité (checklist 40 appliquée)** : aucun nouvel endpoint → aucun changement AuthN/AuthZ/RBAC ; valeurs cachées non sensibles (libellés de rôle publics, index registre public, réponses LLM avec clés **hashées** — jamais de prompt/token en clair dans clé ou valeur) ; URLs Redis jamais loggées avec credentials (`_safe_redis_url`) ; aucun audit log requis (pas de mutation de données métier).

Éléments existants à réutiliser / contraintes :
- **Interface** : ressusciter/adapter l'ABC `CacheManager` de [`core/abstractions.py:13`](../../backend/app/core/abstractions.py:13) (décision E4) dans un nouveau [`core/cache.py`](../../backend/app/core/cache.py) — méthodes get/set/delete + TTL (+ incrément/compteur si nécessaire pour le rate limiting et le brute-force) ;
- **Deux implémentations** : Redis (activé quand `cache_url`/Redis est configuré — même détection que le bus STORY-162) et mémoire locale process-local avec TTL respecté (mode léger RPi, spec 04 § Performance : « cache dict en mémoire remplace Redis avec les mêmes TTL ») ;
- **Warning de dégradation** : un warning unique (pas répété à chaque appel) quand le fallback mémoire est actif ; échec Redis en cours de route → bascule mémoire avec log ;
- **Consommateurs à brancher** : rate limiter ([`core/rate_limit.py:18`](../../backend/app/core/rate_limit.py:18) — harmoniser avec le fallback de STORY-102 sans double implémentation), plugin registry (TTL 300 s, timeout 10 s — [`plugin_registry_service.py:23`](../../backend/app/services/plugin_registry_service.py:23)), **cache RBAC TTL 300 s** (posé par STORY-121/122 — dépendance P1-2 du plan pour P2-8), caches divers identifiés à l'analyse ;
- **Ne pas casser** : `disable_auth` dev, comportement des limiteurs strict/moderate/relaxed (5/30/100 par min) ;
- Décision E4 connexe : `DatabaseManager` (l'autre ABC d'`abstractions.py`) est **hors périmètre** ici — son sort est statué par P3-1 (purge si non consommé) ;
- Spéc 15 § principes : aucune donnée sensible en clair dans les clés/valeurs de cache.

## Critères d'acceptation (AC)

- [x] AC 1 : L'interface de cache unique existe (`core/cache.py`, contractée sur `CacheManager`) avec get/set/delete + TTL ; **sans Redis**, le cache mémoire fonctionne (test : set avec TTL → get avant expiration retourne la valeur, après expiration retourne rien) et **un warning de dégradation est émis** (une fois, vérifié en logs).
- [x] AC 2 : **Avec Redis**, les clés sont visibles dans Redis (test d'intégration avec Redis réel : set → `KEYS`/`GET` côté Redis, TTL exposé) ; un échec de connexion Redis en cours d'exécution bascule sur mémoire avec log sans faire échouer l'appelant.
- [x] AC 3 : Le **rate limiter** consomme l'interface unique : sans `RATE_LIMIT_STORAGE_URL`, les limiteurs ne sont plus des no-op (test : limite dépassée → 429), en cohérence/harmonie avec le fallback STORY-102 (une seule implémentation partagée) ; le **plugin registry** consomme l'interface (TTL 300 s respecté, test de péremption) ; le **cache RBAC TTL 300 s** (STORY-121/122) est migré sur l'interface (test : changement de rôle pris en compte au plus tard 300 s après).
- [x] AC 4 : Tests de sécurité/non-régression : aucun secret/token en clair dans les entrées de cache ; `disable_auth` et les limites par défaut non régressés ; consommation CPU/mémoire bornée (le cache mémoire a une taille maximale ou une politique d'éviction simple).
- [x] AC 5 : Couverture ≥ 80 % sur `core/cache.py` et les consommateurs modifiés ; build + lint + tests passent.

## Références spécification

- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § Performance (cache Redis en mode standard, cache dict en mémoire avec mêmes TTL en mode léger), § Profils de déploiement (brique Redis optionnelle) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Rate limiting (protection des endpoints sensibles), § Principes (pas de données sensibles en clair) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Rate limiting (limites par endpoint) ;
- [ARCHITECTURE-MODULAIRE.md](../../docs/technical_specs/ARCHITECTURE-MODULAIRE.md) — brique `cache` (Redis optionnel, activation) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-8, §2.C C7 (« dégradation silencieuse en no-op → warning + TTL mémoire »), §2.E E4 (CacheManager), §2.B B2 ;
- [`backend_status.md`](../../docs/backend_status.md) — §10.1 (`CacheManager` non consommé, rate limit no-op sans Redis), §3.15 (registry cache TTL 300 s), §11 (config Redis).

## Dépendances

- **Satisfaites** : STORY-122.1 (socle `core/cache.py`), STORY-102 (limiteur mémoire effectif — le fallback rate limiting existe déjà), STORY-162 (setting `cache_url` + pattern factory Redis/ping/`_safe_redis_url`).
- **STORY-121/STORY-122** : cache RBAC déjà branché — cette story le **migre** sur l'interface généralisée (aucune nouvelle fonctionnalité RBAC ; comportement TTL 300 s + invalidation inchangé).
- **Services externes** : Redis **optionnel** — tests d'intégration skippés sans Redis joignable (pattern [`test_events_pubsub.py`](../../backend/tests/integration/test_events_pubsub.py), `WINDFLOW_TEST_REDIS_URL`, DB 15 éphémère) ; aucune dépendance nouveau package (`redis` déjà au pyproject).
- **Migrations** : **aucune** (aucune table/colonne — infrastructure process uniquement).
- **Aval** : STORY-250 (sort de `DatabaseManager` — non concerné ici), STORY-169 (cache registry consommé par l'installation réelle des plugins).

## Sous-stories

*(non prévue — story M)*

Analyse du 2026-10-30 : verdict **pas de découpage** — périmètre backend homogène (une interface + ses consommateurs), ~7 fichiers code + ~5 fichiers tests, aucun changement de schéma DB, tous les points d'ancrage déjà testés.

## État d'avancement technique

- [x] T1 : Config `cache_memory_max_entries` + documentation `env.example` (CACHE_URL)
- [x] T2 : Interface unifiée dans `core/cache.py` (implémentations `CacheManager` ABC + factory `get_cache()` + compatibilité role cache)
- [x] T3 : Rate limiter mutualisé sur les helpers partagés (détection URL + warning unique)
- [x] T4 : Plugin registry migré sur l'interface unique (TTL 300 s + fallback last-known-good)
- [x] T5 : RBAC vérifié sur l'interface généralisée (non-régression)
- [x] T6 : Cache LLM migré (clé hashée, TTL borné, purge préfixe)
- [x] T7 : Fermeture du client cache au shutdown (`main.py`)
- [x] T8 : Tests unitaires (cache, rate_limit, registry, litellm, authorization)
- [x] T9 : Test d'intégration Redis réel (clés visibles, TTL, bascule mémoire)
- [x] T10 : Couverture ≥ 80 % + `make backend-lint` + `make backend-test-all` verts

## Tâches d'implémentation détaillées

Périmètre **backend uniquement** (infrastructure interne — aucun frontend/CLI). Ordre séquentiel :

### T1 — Configuration
- **Fichier** : [`backend/app/config.py`](../../backend/app/config.py) — ajouter dans le bloc cache (près de `cache_url`, ligne ~351) le setting `cache_memory_max_entries: int = Field(default=10_000, gt=0, description=...)` (env var `CACHE_MEMORY_MAX_ENTRIES`) — borne du fallback mémoire, exigée par AC 4. **Ne pas dupliquer** `cache_url` (posé par STORY-162).
- **Fichier** : [`env.example`](../../env.example) — documenter `CACHE_URL` (cache partagé + bus événements, `None` = mode léger mémoire) et `CACHE_MEMORY_MAX_ENTRIES` à côté du bloc `RATE_LIMIT_STORAGE_URL` (ligne ~186).

### T2 — Interface unifiée (cœur de la story)
- **Fichier** : [`backend/app/core/cache.py`](../../backend/app/core/cache.py) — généraliser **sans casser l'API publique** :
  - Créer `CacheProtocol` (typing `Protocol` : `get/set/delete` sur `Any`, `clear_prefix`) et deux implémentations **subclassant l'ABC `CacheManager`** ([`core/abstractions.py:53`](../../backend/app/core/abstractions.py:53) — décision E4) : `MemoryCache` et `RedisCache`, qui concrétisent `get(key) -> Optional[Any]`, `set(key, value, ttl) -> bool`, `delete(key) -> bool`, `clear() -> bool`, `exists(key) -> bool`, `health_check() -> bool` (mémoire : True ; Redis : ping) + `clear_prefix`.
  - `MemoryCache` : entries `(valeur JSON-compatible, expires_at monotone)`, purge paresseuse au `get` (pattern `MemoryRoleCache` actuel), `ttl=None` → permanent, **borne `settings.cache_memory_max_entries`** avec éviction simple (purger d'abord les expirées, puis éviction FIFO de la plus ancienne insertion — politique simple AC 4), `reset()` pour les tests.
  - `RedisCache` : délégation `redis.asyncio` avec TTL native `ex=`, **sérialisation JSON** (`json.dumps`/`loads` — round-trip compatible avec les valeurs `str` actuelles du RBAC), fallback mémoire **par opération** sur exception (log warning, jamais lever — AC 2), `publish` best-effort conservé (utilisé par `invalidate_user_role_cache`), health_check via ping.
  - Factory `get_cache()` (singleton mémosé + `reset_cache()`) : résolution d'URL **`settings.cache_url` en priorité, sinon `settings.rate_limit_storage_url`** (conserve le comportement RBAC actuel quand seul RATE_LIMIT_STORAGE_URL est posé) ; import conditionnel redis ; ping avant décision ; log info du backend actif (URL masquée via `_safe_redis_url` partagé — l'extraire de `core/events.py` vers `core/cache.py` et le réimporter côté events) ; **warning unique de dégradation** en mode mémoire (helper `emit_degraded_warning_once()`, flag module-level — pattern `_emit_memory_warning_once` de rate_limit).
  - Ajouter `shutdown_cache()` (fermeture idempotente du client Redis, no-op en mémoire).
  - **Compatibilité** : aliases `MemoryRoleCache = MemoryCache` / `RedisRoleCache = RedisCache` ; `get_role_cache()` délègue au même singleton unifié ; `reset_role_cache()` → `reset_cache()` ; `RoleCacheProtocol` conservé (les instances le satisfont structurellement — `isinstance(cache, RedisRoleCache)` dans `authorization_service.py:227` reste vrai via l'alias).
  - Mettre à jour la docstring d'entête : rôle généralisé + conventions de clés par consommateur (`rbac:`, `registry:`, `llm:`).

### T3 — Rate limiter : mutualisation (harmonisation STORY-102)
- **Fichier** : [`backend/app/core/rate_limit.py`](../../backend/app/core/rate_limit.py) — remplacer la détection d'URL ad-hoc et le warning maison par les helpers partagés de `core/cache.py` (`resolve_cache_redis_url()`, `emit_degraded_warning_once()`) ; `_emit_memory_warning_once` devient un appel au helper partagé. **Conserver** : l'algorithme `MemoryRateLimiter` fenêtre glissante (compteur, pas un kv — divergence assumée et documentée en docstring) et le chemin fastapi-limiter **strictement inchangé** (décision sur `rate_limit_enabled` + `rate_limit_storage_url`, non-régression STORY-102, ~110 call-sites intouchés). Objectif : une seule implémentation de l'infra « détection Redis + warning dégradé », zéro double bookkeeping.

### T4 — Plugin registry sur l'interface unique
- **Fichier** : [`backend/app/services/plugin_registry_service.py`](../../backend/app/services/plugin_registry_service.py) — supprimer `_cached_index`/`_cache_timestamp`/`_is_cache_valid` ; `fetch_index()` : hit → `get("registry:index")` + désérialisation `RegistryIndex.model_validate` ; miss → fetch aiohttp (timeout 10 s inchangé) + validation Pydantic + `set("registry:index", index.model_dump(), ttl=settings.plugin_registry_cache_ttl)`. **Conserver la sémantique stale-while-error** : garder une copie locale last-known-good `_last_good_index` servie si le fetch échoue (l'interface unique expire les entrées — le fallback sur expiré est porté par le service). `_invalidate_cache()` → `delete("registry:index")` + reset de la copie locale.

### T5 — RBAC : vérification sur interface généralisée
- **Fichier** : [`backend/app/services/authorization_service.py`](../../backend/app/services/authorization_service.py) — **aucune modification fonctionnelle attendue** (déjà sur `get_role_cache()`) : vérifier le round-trip JSON des libellés de rôle (`"admin"` → `"admin"`), ajuster imports/annotations si la généralisation Any l'exige. Ne pas toucher aux clés `rbac:role:{user_id}` ni au canal `rbac:role:invalidate`.

### T6 — Cache LLM borné
- **Fichier** : [`backend/app/services/litellm_service.py`](../../backend/app/services/litellm_service.py) — remplacer `self._cache: Dict[str, Any]` par l'interface unique : clé `llm:{sha256(provider + prompt)}` (**hash** — jamais de prompt en clair dans la clé, règles 40), constante module `LLM_CACHE_TTL: int = 300` (pas de nouveau setting — YAGNI), valeur = réponse sérialisable ; `clear_cache()` → `clear_prefix("llm:")` (best-effort). Les accès se font dans les méthodes async existantes (`generate_docker_compose`).

### T7 — Cycle de vie
- **Fichier** : [`backend/app/main.py`](../../backend/app/main.py) — dans le shutdown (après `shutdown_event_bus()`, ~ligne 520), appeler `await shutdown_cache()` (fermeture du client Redis du cache unifié), à côté du `FastAPILimiter.close()` existant (~ligne 541).

### T8–T10 — Tests & validation
- Voir section « Tests à écrire » ; commands : `make backend-lint`, `make backend-test-all`, couverture `--cov` ≥ 80 % sur `core/cache.py` + consommateurs modifiés (AC 5).

## Tests à écrire

### Backend — unitaires

**`backend/tests/unit/test_core/test_cache.py` (étendre — pattern existant, client `MagicMock`/`AsyncMock`)** :
- `MemoryCache` : set/get valeurs `Any` (str, dict, int) ; TTL expiré → miss + purge paresseuse (AC 1, patch `time.monotonic`) ; `ttl=None` → permanent ; `delete` existante/absente ; `clear_prefix` épargne les autres préfixes ; **borne `cache_memory_max_entries`** : insertion au-delà → éviction FIFO sans erreur (AC 4) ; `exists`/`clear`/`health_check` (contrat ABC `CacheManager`).
- `RedisCache` : sérialisation JSON round-trip (str/dict, bytes décodées) ; `set` passe `ex=ttl` à Redis ; **échec Redis (ConnectionError) sur get/set/delete → fallback mémoire transparent, l'appel n'échoue jamais** (AC 2 volet unitaire) ; warning d'épisode dégradé émis **une fois** (caplog) ; `publish` best-effort.
- Factory `get_cache()` : sans URL → mémoire + **warning de dégradation émis exactement une fois** même après N appels (AC 1) ; `cache_url` prioritaire sur `rate_limit_storage_url` (mock `from_url` pour distinguer) ; URL configurée mais ping KO → mémoire + warning ; singleton mémosé ; `reset_cache()` ; `shutdown_cache()` idempotente.
- Compatibilité : `get_role_cache()` retourne le singleton unifié ; `MemoryRoleCache is MemoryCache` (alias) ; les clés/valeurs rôle passent le round-trip.

**`backend/tests/unit/test_core/test_rate_limit.py` (adapter — non-régression)** :
- Les 3 modes restent effectifs : Redis → `RateLimiter` fastapi-limiter exact ; mémoire seuil N → N+1e requête refuse (429 + `Retry-After`) ; disabled → no-op loggé. Le warning mémoire provient désormais du helper partagé (un seul record même après appels croisés cache + limiter).

**`backend/tests/unit/test_services/test_plugin_registry_service.py` (adapter)** :
- Cache hit via interface unique (2e `fetch_index` sans HTTP — mock aiohttp compté) ; **TTL écoulé → refetch** (AC 3, patch monotonic ou TTL 0) ; erreur fetch → last-known-good servi ; `_invalidate_cache` force le refetch ; deux instances du service partagent le même index (mémoire process-local).

**`backend/tests/unit/test_services/test_litellm_service.py` (nouveau — aucun test n'existe)** :
- Cache hit/miss sur `generate_docker_compose` (provider mocké) ; TTL expiré → régénération ; `clear_cache()` purge le préfixe ; **la clé ne contient pas le prompt en clair** (sécurité AC 4 : assertion `prompt not in key`).

**`backend/tests/unit/test_services/test_authorization_service.py` (non-régression)** : la classe `TestGlobalRoleCache` existante doit passer telle quelle (cache rôle TTL 300 s + invalidation immédiate — AC 3).

### Backend — intégration (Redis réel, skip sans `WINDFLOW_TEST_REDIS_URL` — pattern [`test_events_pubsub.py`](../../backend/tests/integration/test_events_pubsub.py))

**`backend/tests/integration/test_cache_redis.py` (nouveau)** :
- `set` → clé lisible côté Redis via un client témoin (`GET`, préfixe `windflow`/`rbac` selon la clé) ; `TTL` exposé > 0 (AC 2) ; `delete` → clé absente ; `clear_prefix` via `SCAN` ; **échec en cours de route** (client fermé/`ConnectionError` injectée) → bascule mémoire + log sans exception remontée à l'appelant.

### Sécurité (obligatoires — règles 40/35)

- `test_llm_cache_key_does_not_leak_prompt` — aucun prompt/token en clair dans clé ou valeur (AC 4).
- `test_redis_url_masked_in_logs` — `_safe_redis_url("redis://:secret@host:6379/1")` ne contient pas `secret` (les logs ne fuient pas les credentials).
- `test_role_cache_stores_only_public_labels` — la valeur cachée RBAC est un libellé parmi `viewer|operator|admin|super_admin` (pas de token/secret).
- Non-régression `disable_auth` + limites par défaut : couvert par les tests existants (`test_auth/test_dev_mode.py`, `test_rate_limiting.py`) à **exécuter sans modification**.

### Non-applicable

- Pas de nouvel endpoint HTTP → pas de matrice 401/403/404/422 ; pas de tests frontend/CLI (périmètre backend exclusivement) ; pas de migration Alembic → pas de test de migration.

## Notes d'implémentation

*(treat-story — clôture du 2026-10-30)*

### Fichiers modifiés

- `backend/app/core/cache.py` — **réécriture** : interface unifiée `CacheProtocol` + `MemoryCache`/`RedisCache` **subclassant l'ABC `CacheManager`** (décision E4 — l'ABC jusqu'ici non consommé est concrétisé) ; `MemoryCache` bornée (`cache_memory_max_entries`, purge expirées puis FIFO), `RedisCache` JSON round-trip + fallback mémoire **par opération** avec warning **un épisode dégradé = un warning** (flag désarmé au retour à la normale) ; factory `get_cache()` (résolution `cache_url` **prioritaire** sur `rate_limit_storage_url`, ping avant décision, log URL masquée) + `reset_cache()`/`shutdown_cache()` idempotente ; helper partagé `emit_degraded_warning_once()` + `resolve_cache_redis_url()` ; `_safe_redis_url` devient la référence unique (events.py délègue) ; **compatibilité STORY-122.1** : aliases `MemoryRoleCache`/`RedisRoleCache`, `get_role_cache()` → même singleton, `reset_role_cache()`, `RoleCacheProtocol` conservé (~30 fichiers de tests intouchés, vérifié par la run complète).
- `backend/app/core/rate_limit.py` — `_emit_memory_warning_once()` délègue au helper partagé (plus de double bookkeeping) ; `MemoryRateLimiter` (fenêtre glissante) et chemin fastapi-limiter **strictement inchangés** (divergence compteur vs kv-cache documentée en docstring).
- `backend/app/core/events.py` — `_safe_redis_url()` délègue à `core/cache.py` (mutualisation), import `re` retiré.
- `backend/app/services/plugin_registry_service.py` — cache maison supprimé ; `fetch_index()` sur `get_cache()` (clé `registry:index`, TTL `plugin_registry_cache_ttl`, payload `model_dump(mode="json")`, revalidation Pydantic au hit avec purge d'entrée corrompue) ; **stale-while-error conservé** via copie locale `_last_good_index` servie si fetch KO ; `_invalidate_cache()` async (delete + reset copie locale).
- `backend/app/services/litellm_service.py` — dict non borné remplacé par le cache unifié : clé `llm:{sha256(provider:prompt)}` (hash, jamais de prompt en clair dans la clé **ni dans la valeur** — l'ancien champ `prompt[:100]` de la réponse simulée a été retiré), `LLM_CACHE_TTL=300` (constante, YAGNI), `clear_cache()` → `clear_prefix("llm:")` (devenu async) ; génération extraite dans `_generate_llm_response()` (séparée du chemin cache, substituable pour la future intégration litellm).
- `backend/app/services/authorization_service.py` — **aucune modification** (T5 : déjà sur `get_role_cache()`, round-trip JSON des libellés vérifié par tests, aliases maintiennent `isinstance(cache, RedisRoleCache)`).
- `backend/app/config.py` — setting `cache_memory_max_entries` (10 000, `gt=0`).
- `backend/app/main.py` — `await shutdown_cache()` au shutdown (après `shutdown_event_bus()`, à côté de `FastAPILimiter.close()`).
- `env.example` — documentation `CACHE_URL` + `CACHE_MEMORY_MAX_ENTRIES` à côté du bloc rate limit.

### Fichiers de tests créés/étendus

- `backend/tests/unit/test_core/test_cache.py` — étendu 19→37 tests : MemoryCache valeurs `Any`/borne FIFO/purge avant éviction/contrat ABC ; RedisCache JSON round-trip/legacy str brute/`ex=`/fallback par opération/warning un épisode/`clear()` scopé aux préfixes gérés ; factory (priorité `cache_url`, ping KO, mémo, shutdown idempotent) ; compatibilité aliases ; sécurité `_safe_redis_url`.
- `backend/tests/unit/test_services/test_litellm_service.py` — **nouveau** (18 tests) : hit/miss/expiration/distinct prompts/purge préfixe + sécurité (clé hashée déterministe, prompt absent des clés ET valeurs, TTL borné) + méthodes historiques.
- `backend/tests/unit/test_services/test_plugin_registry_service.py` — adapté à l'interface unique + 2 nouveaux (partage inter-instances via cache process-local ; TTL écoulé → refetch).
- `backend/tests/unit/test_core/test_rate_limit.py` — fixtures/attentes basculées sur le helper partagé (`windflow.cache`) + test croisé cache+limiter → un seul warning.
- `backend/tests/integration/test_cache_redis.py` — **nouveau** (8 tests, skip sans `WINDFLOW_TEST_REDIS_URL`, DB 15) : clés visibles côté témoin (`GET`/`TTL`), round-trip dict, `clear_prefix` par SCAN, bascule mémoire sur `ConnectionError` injectée, health_check, masquage URL.
- `backend/tests/integration/test_rate_limiting.py` — fixture flag partagé adaptée.

### Décisions techniques

1. **Warning « un épisode dégradé » dans `RedisCache`** : la story exigeait un warning unique côté factory ; implémenté aussi par opération (flag `_episode_warned` désarmé dès qu'une commande réussit) — ni spam ni aveuglement sur les échecs persistants.
2. **`RedisCache.clear()` jamais `FLUSHDB`** : la base Redis est partagée (fastapi-limiter) — seuls les préfixes `rbac:`/`registry:`/`llm:` (`CACHE_KEY_PREFIXES`) sont supprimés par SCAN.
3. **Borne mémoire = purge expirées puis FIFO**, ré-écriture d'une clé = rafraîchissement de position FIFO (pas d'éviction d'une clé chaude re-écrite).
4. **Lecture legacy Redis tolérante** : les valeurs `str` brutes écrites avant STORY-168 restent lisibles (déploiements sans flush).
5. **Sécurité** : aucune URL Redis loggée avec credentials (masquage mutualisé) ; prompt LLM absent des clés/valeurs ; valeurs RBAC = libellés publics uniquement.

### Divergences

- **Aucune divergence de périmètre.** Deux adaptations de tests préexistants étaient prévues par la story (sérialisation JSON des valeurs Redis → 2 assertions de `test_cache.py` ; warning déplacé vers le logger partagé `windflow.cache` → fixtures de 2 fichiers rate-limit). `clear_cache()` de LiteLLMService est devenu **async** (contrainte de l'interface unifiée) — aucun appelant n'existait dans le code (service orphelin tracé STORY-250).
- Test d'intégration « client fermé » remplacé par « `ConnectionError` injectée » : le pool redis-py se reconnecte automatiquement après `aclose()` (alternative explicitement prévue par la story).

### Difficultés rencontrées

- Conflits d'éditeur transitoires (PyCharm) sur 2 écritures — résolus (fichiers vérifiés conformes).
- 3 échecs d'intégration **préexistants** (`test_deployments_api::test_delete_deployment`, 2 × `test_deployments_events_api`) + 1 erreur de collection préexistante (`test_secret_encryption.py` — import résiduel `TargetStatus` de STORY-166) : **prouvés identiques sur HEAD par stash**, hors périmètre.

### Validation (commandes exécutées)

- `poetry run pytest tests/unit/test_core/test_cache.py tests/unit/test_core/test_rate_limit.py tests/unit/test_services/test_plugin_registry_service.py tests/unit/test_services/test_litellm_service.py tests/unit/test_services/test_authorization_service.py` → **104 passed**.
- `poetry run pytest tests/integration/test_cache_redis.py` → **8 passed** (Redis réel local disponible).
- Suite complète : `poetry run pytest tests/unit tests/integration --ignore=tests/integration/test_secret_encryption.py` → **2954 passed, 1 skipped, 3 failed préexistants (prouvés sur HEAD)**.
- Couverture périmètre : `core/cache.py` **93 %**, `core/rate_limit.py` **100 %**, `plugin_registry_service.py` **94 %**, `litellm_service.py` **97 %** (AC 5 ≥ 80 % respecté).
- Lint : `isort` + `black` + `flake8` + `bandit` sur le périmètre → **0 erreur** ; `mypy` → **0 erreur sur les fichiers du périmètre** (6 erreurs transitives préexistantes prouvées sur HEAD).
