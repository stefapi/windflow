# STORY-122.1 : Socle RBAC — `auth/rbac.py`, hiérarchie 4 rôles et cache TTL 300 s

**Statut :** DONE
**Story Parente :** STORY-122 — Dépendances RBAC `require_role(...)` — hiérarchie, cache TTL 300 s et protections d'escalade sur les ~110 endpoints (P1-2, application)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'administrateur sécurité de WindFlow, je veux disposer du socle d'autorisation RBAC réutilisable : une dépendance FastAPI `require_role(minimum_role)` appliquant la hiérarchie des 4 rôles (viewer < operator < admin < super_admin), un `AuthorizationService` résolvant le rôle via `user_organizations` avec cache TTL 300 s (Redis en mode standard, mémoire en mode léger) et l'invalidation immédiate du cache au changement de rôle — ce socle étant ensuite appliqué aux ~118 endpoints par les sous-stories 122.2 à 122.6.

Cette sous-story ne modifie **aucun endpoint existentiel** (aucun router) : elle pose uniquement les primitives d'autorisation et leurs tests. Les seules modifications hors nouveaux fichiers sont les hooks d'invalidation de cache dans le router organizations (écritures membres, posées par STORY-121.2).

## Critères d'acceptation (AC)

- [x] AC 1 : La dépendance `require_role(minimum_role)` (nouveau module `auth/rbac.py` ou équivalent) est implémentée avec la hiérarchie viewer < operator < admin < super_admin ; `User.is_superadmin` = tous droits sur toutes les organisations ; le rôle est résolu via `user_organizations` avec **cache TTL 300 s** (Redis standard / mémoire léger) — test : un changement de rôle est pris en compte au plus tard 300 s après (invalidation au changement de rôle testée).

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-08) — patterns vérifiés dans le code.

**Couches impactées :** Backend uniquement — nouveau module auth, nouveau service, nouveau module cache, hooks d'invalidation, tests backend. **Aucun endpoint nouvellement protégé** dans cette sous-story.

**Spécifications de référence :**
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — **intégral** : § Rôles (enum 4 valeurs), § Implémentation (`AuthorizationService`, `role_hierarchy`, cache TTL 300 s, `require_role`), § Sécurité du RBAC (invalidation du cache — Redis pub/sub en mode standard, instantané en mémoire) ;
- `.roo/rules/40-security.md` — RBAC côté API = source de vérité.

**Fichiers de référence (patterns vérifiés) :**
- Dépendances FastAPI existantes → [`backend/app/auth/dependencies.py`](../../backend/app/auth/dependencies.py) : `get_current_user` (l. 41, gestion `settings.disable_auth`), `get_current_active_user` (l. 92), `require_superuser` (l. 114 — 403 « Not enough permissions »), `get_current_user_ws` (l. 140, `WebSocketException` 1008) — **`require_role` doit composer avec `get_current_active_user`** (même chaîne de dépendances) ;
- Enum `Role` (viewer/operator/admin, **sans** super_admin) → [`backend/app/enums/rbac.py`](../../backend/app/enums/rbac.py) ;
- Primitives rôle/appartenance → [`backend/app/services/user_organization_service.py`](../../backend/app/services/user_organization_service.py) : `is_member` (l. 37, bypass superuser), `get_user_organization_ids` (l. 75) — ajouter `get_role_in_organization` ;
- Abstraction cache → [`backend/app/core/abstractions.py`](../../backend/app/core/abstractions.py) l. 53 : `CacheManager` ABC (`get`/`set`/`delete`, TTL en secondes) — **aucune implémentation concrète n'existe** (grep `CacheInterface|MemoryCache|RedisCache` = 0 module applicatif) ;
- Pattern service statique async → [`backend/app/services/user_organization_service.py`](../../backend/app/services/user_organization_service.py) ;
- Écritures membres (où poser les invalidations) → [`backend/app/api/v1/organizations.py`](../../backend/app/api/v1/organizations.py) : `update_organization_member_role` (l. ~1473), `add_organization_member` (l. ~1272), `remove_organization_member` (l. ~1617) ;
- Fixtures tests → [`backend/tests/conftest.py`](../../backend/tests/conftest.py) : `db_session`, `test_organization`, `test_user` (operator), `test_superuser`, `client`, `authenticated_client`, `admin_client`.

**Décisions d'analyse :**
- **Deux notions de rôle distinctes** : (a) *rôle global effectif* d'un utilisateur = max(`is_superuser` → `super_admin`, sinon max des rôles dans ses associations) — utilisé par `require_role` sur les endpoints globaux ; (b) *rôle dans une organisation* = ligne `user_organizations.role` — utilisé pour l'isolation/gestion des membres. Le superuser est `super_admin` partout (spec 08 : accès total toutes organisations) ;
- **`require_role` compose `get_current_active_user`** (pas `get_current_user` seul) : user inactif → 403 avant toute vérification de rôle (chaîne existante inchangée) ;
- **403 (pas 401)** pour rôle insuffisant — pattern `require_superuser` ; message sans révéler la hiérarchie interne ;
- **`disable_auth` préservé** : le mode dev auto-login superadmin passe tous les `require_role` sans code dédié (l'utilisateur est déjà super_admin par construction) — à couvrir par un test ;
- **Cache** : implémentation concrète double backend — `MemoryRoleCache` (dict + `time.monotonic()`, pattern [`plugin_registry_service.py`](../../backend/app/services/plugin_registry_service.py) l. 41-56 `_is_cache_valid`) et `RedisRoleCache` si Redis configuré (`settings.redis_url`, cf. `backend/app/config.py` l. 196) — sélection à l'init selon la disponibilité Redis ; TTL 300 s configurable (`rbac_role_cache_ttl: int = 300` dans settings) ;
- **Clé de cache** : `rbac:role:{user_id}` (rôle global) — l'invalidation est appelée dans les 3 écritures membres et à toute modification de rôle ; Redis pub/sub multi-workers (spec 08 § Invalidation) : la publication est best-effort, la TTL 300 s garantissant la convergence au pire cas ;
- **WebSocket** : `require_role_ws(minimum_role)` — même logique mais lève `WebSocketException(1008)` (pattern `get_current_user_ws` l. 140) ; consommé par STORY-122.6 ;
- `helper/permissions.py` = code mort confirmé (0 import) — **ne pas y toucher** (décision E1, purge par STORY-250).

**Exigences sécurité identifiées (Phase 2.6) :**
- Auth : oui — `require_role` hérite de `get_current_active_user` (401 sans token via `oauth2_scheme`) ;
- RBAC : la hiérarchie **est** l'objet de la story — viewer(0) < operator(1) < admin(2) < super_admin(3) ; `super_admin` uniquement via `User.is_superuser`, jamais stockable en association ;
- Validation : `minimum_role` paramètre code-only (pas d'input utilisateur) ;
- Exposition : aucune donnée sensible dans les logs (user_id seulement, jamais de tokens) ;
- Audit : les logs d'invalidation de cache (user_id, org_id) sans données sensibles.

## Dépendances

- STORY-121 (DONE) : modèle `user_organizations` + enum `Role` + primitives service.
- Pré-requise par : STORY-122.2, 122.3, 122.4, 122.5, 122.6, 122.7.

## Tâches d'implémentation détaillées

### Tâche 1 : Implémentations concrètes du cache (`MemoryRoleCache` / `RedisRoleCache`)
**Objectif :** Créer le module cache avec TTL, fournissant l'implémentation concrète du `CacheManager` abstrait (inexistante à ce jour), sélectionnée selon la disponibilité Redis.
**Fichiers :**
- `backend/app/core/cache.py` — Créer — Nouveau module (pattern : docstrings/structure de [`backend/app/core/rate_limit.py`](../../backend/app/core/rate_limit.py) — store mémoire + variante Redis conditionnelle, constantes module-level patchables en tests). Définir :
  - `MemoryRoleCache` : classe avec `_store: dict[str, tuple[str, float]]` (valeur + timestamp `time.monotonic()`), méthodes `async get(key) -> Optional[str]`, `async set(key, value, ttl)` , `async delete(key)`, `async clear_prefix(prefix)` — TTL expiré → miss + purge paresseuse (pattern `_is_cache_valid` de `plugin_registry_service.py`) ;
  - `RedisRoleCache` : même interface via client `redis.asyncio` (import conditionnel), `set(key, value, ex=ttl)`, `delete`, clés préfixées `rbac:` ; échec Redis → log warning + fallback transparent vers l'instance mémoire interne (résilience `.roo/rules/20-architecture-and-api.md`) ;
  - `get_role_cache() -> RoleCacheProtocol` : factory singleton choisissant Redis si `settings.redis_url` configuré **et** connexion OK, sinon mémoire (mode léger) — résolution paresseuse mémorisée ;
  - `Protocol RoleCacheProtocol` (typing) pour testabilité (mock simple).
- `backend/app/config.py` — Modifier — Ajouter `rbac_role_cache_ttl: int = Field(default=300, ...)` (description « TTL du cache des rôles RBAC en secondes », cohérence avec `plugin_registry_cache_ttl` l. 275).
**Exigences sécurité :** Aucune donnée sensible stockée (clé = user_id, valeur = libellé de rôle public).
**Dépend de :** Aucune

### Tâche 2 : `AuthorizationService` — résolution du rôle global et par organisation
**Objectif :** Créer le service central d'autorisation (spec 08 § Implémentation) qui résout le rôle d'un utilisateur avec cache TTL 300 s et expose les primitives de vérification hiérarchique.
**Fichiers :**
- `backend/app/services/authorization_service.py` — Créer — Nouveau service (pattern : classe à méthodes statiques async de `user_organization_service.py`). Classe `AuthorizationService` :
  - `ROLE_HIERARCHY: dict[str, int] = {"viewer": 0, "operator": 1, "admin": 2, "super_admin": 3}` (constante module) + `SUPER_ADMIN = "super_admin"` ;
  - `async get_global_role(db: AsyncSession, user: User) -> str` — `super_admin` si `user.is_superuser` (court-circuit, pas de cache nécessaire) ; sinon max des `UserOrganization.role` de l'utilisateur (`select(UserOrganization.role).where(user_id == user.id)`), `viewer` si aucune appartenance — **conservateur** (privilège minimum) ; résultat mis en cache `rbac:role:{user_id}` via `get_role_cache()` TTL `settings.rbac_role_cache_ttl` ;
  - `async get_role_in_organization(db, user, organization_id) -> Optional[str]` — `super_admin` si superuser ; sinon lit `user_organizations.role` pour `(user.id, str(organization_id))` (helper interne réutilisable, caching optionnel même mécanique) ;
  - `async role_at_least(db, user, minimum: str, organization_id: Optional[UUID|str] = None) -> bool` — si `organization_id` fournie : rôle dans l'org (None → False) ; sinon rôle global ; compare via `ROLE_HIERARCHY` ;
  - `async invalidate_user_role_cache(user_id)` — `delete("rbac:role:{user_id}")` (+ publication best-effort si Redis) ;
  - Logs DEBUG de résolution avec `extra={"user_id": ...}` uniquement.
**Exigences sécurité :** Rôle par défaut `viewer` (moindre privilège, spec 15) ; jamais de rôle système dérivé d'une association.
**Dépend de :** Tâche 1

### Tâche 3 : Dépendances `require_role(...)` et `require_role_ws(...)` dans `auth/rbac.py`
**Objectif :** Créer les dépendances FastAPI appliquant le rôle minimum sur les endpoints HTTP et WebSocket.
**Fichiers :**
- `backend/app/auth/rbac.py` — Créer — Nouveau module. Définir :
  - `def require_role(minimum_role: str) -> Callable` — factory retournant `async def role_checker(current_user: User = Depends(get_current_active_user), session: AsyncSession = Depends(get_db)) -> User` qui : valide `minimum_role in ROLE_HIERARCHY` (AssertionError = erreur dev, pas HTTP) ; appelle `AuthorizationService.get_global_role` ; si hiérarchie insuffisante → `HTTPException(403, "Not enough permissions")` (message identique à `require_superuser` l. 131) + log warning avec `extra={"user_id", "minimum_role", "path"` si request accessible`}` ; retourne `current_user` ; docstring complète avec exemples (spec 08 § Dépendance FastAPI) ;
  - `def require_role_ws(minimum_role: str) -> Callable` — variante pour handshake WebSocket : `WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Insufficient permissions")` en cas de rôle insuffisant (pattern `get_current_user_ws` l. 140-229 — compose cette dépendance, **jamais** de user anonyme) ; docstring précisant la consommation par STORY-122.6 ;
  - Réexporter commodément `require_viewer = require_role("viewer")`, `require_operator`, `require_admin`, `require_super_admin` (prédéfinies, usage direct dans les routers) ;
  - `require_role("viewer")` sémantiquement équivalent à `get_current_active_user` (tout utilisateur authentifié actif a un rôle global ≥ viewer) — à documenter explicitement.
**Exigences sécurité :** Chaîne `get_current_active_user` (401 sans token, 403 inactif) puis 403 rôle insuffisant ; aucun contournement `disable_auth` nécessaire (superadmin auto-login ≥ tous rôles).
**Dépend de :** Tâche 2

### Tâche 4 : Invalidation du cache sur les écritures membres (hooks organizations)
**Objectif :** Brancher `AuthorizationService.invalidate_user_role_cache` sur les 3 écritures de gestion des membres pour que tout changement de rôle soit effectif immédiatement (AC 1 : invalidation au changement de rôle).
**Fichiers :**
- `backend/app/api/v1/organizations.py` — Modifier — Dans `add_organization_member` (l. ~1272), `update_organization_member_role` (l. ~1473) et `remove_organization_member` (l. ~1617) : après commit réussi, appeler `await AuthorizationService.invalidate_user_role_cache(str(member_data.user_id))` / `str(user_id)` — import `from ...services.authorization_service import AuthorizationService`. Ajout d'un commentaire `# STORY-122.1 : invalidation cache rôle (TTL max 300 s sinon)`. Ne **pas** modifier les dépendances de ces endpoints ici (déjà `require_superuser` intérimaire — bascule `require_role` en STORY-122.4).
**Exigences sécurité :** Action critique déjà loggée (audit intérimaire STORY-121.2) — l'invalidation est additive, sans donnée sensible.
**Dépend de :** Tâche 2

### Tâche 5 : Tests du socle RBAC (hiérarchie, cache TTL, invalidation, disable_auth)
**Objectif :** Couvrir unitairement le cache, la résolution de rôle et les dépendances — cas nominaux, TTL, invalidation, sécurité.
**Fichiers :**
- `backend/tests/unit/test_auth/test_rbac_dependencies.py` — Créer — Tests `require_role` : hiérarchie (viewer passe `require_role("viewer")` mais 403 sur `require_role("operator")` ; operator 403 sur admin ; admin 403 sur super_admin ; superuser passe tout) ; composition `get_current_active_user` (401 sans token via client sans Authorization ; 403 user inactif) ; `disable_auth` → superadmin auto-login passe `require_super_admin` ;
- `backend/tests/unit/test_services/test_authorization_service.py` — Créer — Tests service : `get_global_role` superuser → `super_admin` ; multi-appartenances → max (viewer+admin → admin) ; aucune appartenance → `viewer` ; `get_role_in_organization` isolation (membre vs non-membre → None) ; `role_at_least` bornes exactes (admin ≥ admin True, admin ≥ super_admin False) ; **cache** : 2e appel sans re-requête SQL (patch/mocker sur la session), TTL expiré → re-requête (monkeypatch `time.monotonic` ou TTL court) ; **invalidation** : rôle changé en base + `invalidate_user_role_cache` → nouvelle résolution immédiate (AC 1 « au plus tard 300 s » — l'invalidation force l'immédiateté) ; sans invalidation → valeur périmée servie jusqu'à TTL (test du pire cas borne 300 s) ;
- `backend/tests/unit/test_core/test_cache.py` — Créer — Tests `MemoryRoleCache` : set/get, TTL expiré → None, delete, clear_prefix ; `RedisRoleCache` : mocké (pas de Redis réel en unitaire) ; factory : sans `redis_url` → mémoire ;
- `backend/tests/unit/test_auth/test_rbac_ws.py` — Créer — Test `require_role_ws` : rôle insuffisant → `WebSocketException` 1008 (pattern tests de [`test_ws_auth.py`](../../backend/tests/unit/test_websocket/test_ws_auth.py)).
**Exigences sécurité :** Tests sécurité obligatoires : 401 sans token, 403 hiérarchie insuffisante, rôle par défaut conservateur `viewer`.
**Dépend de :** Tâches 1, 2, 3, 4

## Tests à écrire

> Patterns détaillés : `.roo/rules/35-testing-quality-gates.md` — tests sécurité : `.roo/rules/40-security.md`. Détail exhaustif en Tâche 5.

### Unitaires Backend
- `backend/tests/unit/test_auth/test_rbac_dependencies.py` — hiérarchie ×4 rôles, 401/403, disable_auth
- `backend/tests/unit/test_services/test_authorization_service.py` — rôles global/org, cache TTL, invalidation
- `backend/tests/unit/test_core/test_cache.py` — MemoryRoleCache/RedisRoleCache/factory
- `backend/tests/unit/test_auth/test_rbac_ws.py` — refus 1008 WebSocket

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_auth/test_rbac_dependencies.py backend/tests/unit/test_services/test_authorization_service.py backend/tests/unit/test_core/test_cache.py backend/tests/unit/test_auth/test_rbac_ws.py -v
poetry run pytest backend/tests/unit/test_api/test_organization_members.py -v  # non-régression hooks invalidation
make backend-lint && make backend-typecheck
```

## État d'avancement technique
- [x] Tâche 1 : Cache rôle TTL (`MemoryRoleCache`/`RedisRoleCache` + factory)
- [x] Tâche 2 : `AuthorizationService` (rôle global, rôle par org, hiérarchie)
- [x] Tâche 3 : `require_role(...)` / `require_role_ws(...)` dans `auth/rbac.py`
- [x] Tâche 4 : Invalidation cache sur écritures membres (organizations.py)
- [x] Tâche 5 : Tests socle RBAC
- [x] Lint & typecheck OK

## Notes d'implémentation

**Date :** 2026-09-09

### Fichiers modifiés/créés
- `backend/app/core/cache.py` : **créé** — `RoleCacheProtocol` (typing Protocol), `MemoryRoleCache` (dict + `time.monotonic()`, TTL expiré → miss + purge paresseuse), `RedisRoleCache` (client `redis.asyncio` injecté, TTL native `ex=`, fallback mémoire transparent sur échec, `publish()` best-effort pour l'invalidation multi-workers), `get_role_cache()` (factory singleton paresseuse : Redis si URL configurée + ping OK, sinon mémoire) et `reset_role_cache()` (tests).
- `backend/app/services/authorization_service.py` : **créé** — `ROLE_HIERARCHY`, `AuthorizationService.get_global_role` (superuser → `super_admin` court-circuit sans cache ; sinon max des associations, `viewer` si aucune, mise en cache `rbac:role:{user_id}` TTL `settings.rbac_role_cache_ttl`), `get_role_in_organization` (superuser bypass, `None` si non-membre), `role_at_least` (scope global ou org), `invalidate_user_role_cache` (delete + publication pub/sub best-effort).
- `backend/app/auth/rbac.py` : **créé** — `require_role(minimum_role)` (compose `get_current_active_user`, 403 « Not enough permissions », assertion sur rôle inconnu = erreur dev), `require_role_ws(minimum_role)` (compose `get_current_user_ws`, `WebSocketException(1008, "Insufficient permissions")`), aliases `require_viewer`/`require_operator`/`require_admin`/`require_super_admin`.
- `backend/app/config.py` : **modifié** — ajout `rbac_role_cache_ttl: int = Field(default=300, ...)` (section RBAC, cohérente avec `plugin_registry_cache_ttl`).
- `backend/app/api/v1/organizations.py` : **modifié** — hooks `AuthorizationService.invalidate_user_role_cache(...)` après commit dans `add_organization_member`, `update_organization_member_role` et `remove_organization_member` (commentaire `# STORY-122.1`), aucune dépendance d'endpoint modifiée (basculée par 122.4).
- Tests créés : `backend/tests/unit/test_core/test_cache.py`, `backend/tests/unit/test_services/test_authorization_service.py`, `backend/tests/unit/test_auth/test_rbac_dependencies.py`, `backend/tests/unit/test_auth/test_rbac_ws.py`.

### Décisions techniques
- **URL Redis** : la story citait `settings.redis_url` (config.py l. 196) qui **n'existe pas** — l'URL Redis réelle de la config est `settings.rate_limit_storage_url` (l. 194). La factory s'appuie donc sur ce champ existant (aucune duplication de config). *Divergence, cf. section dédiée.*
- **Publication pub/sub** : `RedisRoleCache.publish()` ajouté (canal `rbac:role:invalidate`) — la spec 08 § Invalidation exige une diffusion multi-workers en mode Redis ; best-effort, la TTL 300 s garantit la convergence au pire cas.
- **`require_role` injecte `Request`** en plus de `get_current_active_user`/`get_db` pour logger `path` dans les refus (exigence story « si request accessible »).
- **`role_at_least` lève `ValueError`** sur rôle minimum inconnu (défense en profondeur) ; `require_role`/`require_role_ws` lèvent `AssertionError` à la construction comme demandé.
- **Tests dépendances** : mini-router monté sur `app` (préfixe unique `/test-rbac-1221`) pour exercer la chaîne réelle oauth2 → JWT → actif → rôle, avec fixture autouse `_jwt_mode` forçant `disable_auth=False` (le `.env` local de dev porte `DISABLE_AUTH=true`, absent en CI — sans ce patch les 401/403 seraient court-circuités en local uniquement).

### Divergences par rapport à l'analyse
- **Tâche 1** : `settings.redis_url` inexistant → utilisation de `settings.rate_limit_storage_url` (seule URL Redis de la config). Aucun autre champ Redis disponible ; cohérent avec le rate limiting distribué.
- **Tâche 2** : `get_role_in_organization` volontairement **non caché** (lecture d'isolation, le cache TTL cible le rôle global par utilisateur) — précisé en docstring.
- **Tâche 3** : la signature de `role_checker` inclut `Request` (non mentionné explicitement mais exigé pour le log `path`).

### Difficultés rencontrées
- venv Poetry principal (`.venv`, python 3.14) cassé (alembic manquant) → tests exécutés avec `.venv-test` (python 3.11, complet). Recommander `poetry install` pour recréer `.venv`.
- 5 échecs préexistants dans `test_users.py`/`test_auth_isolation.py` confirmés **antérieurs** à la story (vérifiés via `git stash`) : causés par le `.env` local (`DISABLE_AUTH=true`), ils passent en CI (sans `.env`). Aucune régression introduite.

### Tests ajoutés
- `backend/tests/unit/test_core/test_cache.py` : 18 tests — MemoryRoleCache (set/get, TTL expiré + purge, delete, clear_prefix, ttl=None), RedisRoleCache mocké (décodage bytes, TTL native, fallback mémoire get/set/delete, publish best-effort), factory (sans URL → mémoire, mémoïsation, Redis injoignable → fallback). Couverture `cache.py` : **82 %**.
- `backend/tests/unit/test_services/test_authorization_service.py` : 13 tests — rôles global (superuser, multi-appartenances max, aucune → viewer), rôle par org (bypass, membre, non-membre → None), `role_at_least` bornes exactes (admin ≥ admin, admin ≱ super_admin, scope org vs global, rôle inconnu → ValueError), cache (2e appel sans SQL, valeur périmée servie jusqu'à TTL, invalidation → résolution immédiate, superuser sans cache). Couverture `authorization_service.py` : **98 %**.
- `backend/tests/unit/test_auth/test_rbac_dependencies.py` : 11 tests — hiérarchie ×4 via HTTP (viewer 403 operator, operator 403 admin, admin 403 super_admin, superuser passe tout, sans appartenance → viewer), 401 sans/avec token invalide, 403 inactif, `disable_auth` → superadmin passe `require_super_admin`, AssertionError rôle inconnu, aliases. Couverture `auth/rbac.py` : **100 %**.
- `backend/tests/unit/test_auth/test_rbac_ws.py` : 5 tests — refus 1008 (viewer sur admin, operator sur super_admin), passage (admin, super_admin), AssertionError rôle inconnu.

### Validation
- `pytest` ciblé (4 fichiers story + non-régression hooks) : **81 passed**.
- flake8 + black + isort sur tous les fichiers touchés : OK. mypy sur les 3 nouveaux modules : OK (notes préexistantes uniquement).
- Commandes équivalentes exécutées avec `.venv-test/bin/python -m pytest ...` (venv Poetry principal cassé).
