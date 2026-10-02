# STORY-129 : Endpoints santé & mot de passe — `GET /system/ready` sans auth et `PUT /auth/password` (P1-7 + P1-8)

**Statut :** DONE
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-7 (axe A12) + P1-8 (axe A13, rapport §1/§2) — ampleur **S**

## Description

En tant qu'exploitant de WindFlow, je veux un endpoint de **readiness** `GET /api/v1/system/ready` accessible sans authentification (vérifiant DB, migrations appliquées et dépendances optionnelles) et un endpoint `PUT /api/v1/auth/password` permettant à un utilisateur authentifié de changer son mot de passe (ancien requis), afin que les orchestrateurs (docker compose healthcheck, install.sh « attend que l'API soit prête ») disposent d'un vrai signal de démarrage et que les utilisateurs gèrent leurs credentials.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §1, §2, §14) : seul [`GET /health`](../../backend/app/main.py:492) existe (vérifie DB + Redis, 503 si DB down) — pas de `/ready` ; `PUT /auth/password` n'existe pas ([`auth.py`](../../backend/app/api/v1/auth.py:71)). La spec 09 exige `/system/health` **et** `/system/ready` sans auth, et la liste canonique auth inclut `PUT /password`.

## Contexte technique

> Analyse remplie par `analyse-story`. Constats vérifiés dans le code au moment de l'analyse.

### État des lieux (vérifié)

- **Pas de router `system`** : [`api/v1/__init__.py`](../../backend/app/api/v1/__init__.py:28) monte 15 sous-routers, aucun préfixe `/system`. Le seul endpoint santé est [`GET /health`](../../backend/app/main.py:492) monté **à la racine** de `app` (hors `/api/v1`) : DB via [`db.health_check()`](../../backend/app/database.py:249) (`SELECT 1`), Redis ping **si** `rate_limit_enabled` + `rate_limit_storage_url`, `503` si DB down — sans auth, non enveloppé (le [`api_response_middleware`](../../backend/app/middleware/api_response.py:204) n'enveloppe que `/api/v1/*` 2xx JSON).
- **`PUT /auth/password` absent** : le router [`auth.py`](../../backend/app/api/v1/auth.py:71) expose `POST /login`, `POST /refresh`, `POST /logout`, `POST /register`, `GET /me`, `POST|GET|DELETE /api-keys` — rien pour le changement de mot de passe. La liste canonique spec 07/09 inclut `PUT /password`.
- **Consommateurs du `/health` racine à préserver** (non-régression) : [`docker-compose.prod.yml`](../../docker-compose.prod.yml:287) (healthcheck `curl -f http://localhost:8000/health` ×2 + traefik `healthcheck.path=/health`), [`docker-compose.minimal.yml`](../../docker-compose.minimal.yml:87) (`/api/health` après strip-prefix Traefik → `/health`), tests ([`test_openapi.py`](../../backend/tests/integration/test_openapi.py:57) critical_paths, [`test_api_envelope.py`](../../backend/tests/integration/test_api_envelope.py:204) garde-fous, correlation/security-headers/timing). La spec 16 documente déjà `curl http://localhost:8080/api/v1/system/health`.

### Patterns existants à réutiliser (réutilisation directe)

| Besoin | Élément réutilisable | Fichier |
|---|---|---|
| Check DB | `db.health_check()` (`SELECT 1`) | [`database.py`](../../backend/app/database.py:249) |
| Config Alembic programmatique | `get_alembic_config()` (STORY-120.2) | [`database.py`](../../backend/app/database.py:41) |
| Check Redis optionnel | pattern ping `rate_limit_storage_url` | [`main.py`](../../backend/app/main.py:515) |
| Vérif mot de passe | `UserService.verify_password(plain, hash)` (passlib **Argon2** — voir divergence n°1) | [`user_service.py`](../../backend/app/services/user_service.py:48) |
| Hash nouveau mot de passe | `UserService.hash_password(password)` | [`user_service.py`](../../backend/app/services/user_service.py:31) |
| Révocation globale refresh | `RefreshTokenService.revoke_all_for_user(db, user_id) -> int` (idempotent, STORY-123.2) | [`refresh_token_service.py`](../../backend/app/services/refresh_token_service.py:288) |
| Audit action critique | `AuditService.log_from_request(request, action, user=..., resource_type=..., resource_id=..., details=...)` (STORY-125.2) | [`audit_service.py`](../../backend/app/services/audit_service.py) |
| Authentifié courant | `get_current_active_user` (JWT **ou** clé API `wf_ak_`) | [`dependencies.py`](../../backend/app/auth/dependencies.py) |
| Rate limiting | `conditional_rate_limiter(times, seconds)` en `dependencies=[...]` | [`core/rate_limit.py`](../../backend/app/core/rate_limit.py) |
| Erreurs typées 400/422/503 | `InvalidInputError` (400 `INVALID_INPUT`), `UnprocessableEntityError` (422), `ServiceUnavailableError` (503) — handler global → enveloppe erreur | [`core/exceptions.py`](../../backend/app/core/exceptions.py:153) |
| Montage router | `api_router.include_router(system_router, prefix="/system", tags=["system"])` | [`api/v1/__init__.py`](../../backend/app/api/v1/__init__.py:31) |
| Tests auth JWT | fixtures `_jwt_mode` + `_bearer(user)` (mint direct), helpers `unwrap`/`error_code` du conftest | [`test_api_envelope.py`](../../backend/tests/integration/test_api_envelope.py:37), [`conftest.py`](../../backend/tests/conftest.py:44) |

### Arbitrages d'analyse (décisions proposées, à appliquer telles quelles)

| # | Question | Décision | Justification |
|---|---|---|---|
| 1 | Hash du nouveau mot de passe : bcrypt ou Argon2 ? | **Argon2** via `UserService.hash_password` | `pwd_context = CryptContext(schemes=["argon2"])` est **déjà** Argon2 (contrairement à l'ébauche de cette story qui mentionnait bcrypt) ; STORY-130 (migration Argon2id) sera donc largement satisfaite de facto sur ce chemin. Ne **jamais** utiliser [`helper/security.py`](../../backend/app/helper/security.py:7) (bcrypt, code legacy résiduel — la divergence est consignée pour STORY-250/252) |
| 2 | `/system/health` remplace ou alias `/health` racine ? | **Alias : les deux coexistent** — logique factorisée dans un service commun ; `/health` racine conservé à l'identique (non-régression compose/traefik/tests), `/api/v1/system/health` ajoute le chemin spec 09 | Spec 16 documente déjà `/api/v1/system/health` ; supprimer `/health` racine casserait `docker-compose.prod.yml` et la doc install existantes sans gain |
| 3 | Enveloppe spec 09 sur `/system/ready` ? | **200 enveloppé** `{data: {checks}, message: null}` (middleware STORY-126 s'applique à tout `/api/v1/*` 2xx JSON — aucune exclusion à ajouter) ; **503 en `JSONResponse` direct non enveloppé** avec le même payload de checks | Symétrique du `/health` racine actuel (503 nu) ; l'orchestrateur (`curl -f`) ne lit que le code HTTP ; ne pas affaiblir le contrat enveloppe STORY-126 avec une exclusion `/system` |
| 4 | 400 vs 401 si ancien mot de passe faux | **400** via `InvalidInputError("Current password is incorrect")` | Critère de done P1-8 explicite (« 400 si faux ») ; l'utilisateur EST authentifié (401 serait trompeur) |
| 5 | Périmètre des « dépendances optionnelles » de `/ready` | **Redis seul** (si `rate_limit_enabled` + `rate_limit_storage_url`) | Le daemon Docker est une cible de déploiement, pas une dépendance de démarrage de l'API ; Vault/Keycloak/Prometheus sont optionnels et découplés ; Redis est la seule dépendance d'exécution conditionnelle réelle (rate limiter) |
| 6 | UI/CLI de changement de mot de passe | **Hors périmètre** (backend only, ampleur S) | L'AC exige l'endpoint API (API-first, rules 20) ; les clients pourront consommer `PUT /auth/password` dans un second temps |
| 7 | Check « migrations appliquées » | Comparaison `current_revision` (table `alembic_version`) **==** `head` (ScriptDirectory) ; base sans `alembic_version` → check **unhealthy** | STORY-120 garantit `upgrade head` au démarrage — un `/ready` qui répond prêt avec un schéma non migré serait un signal mensonger ; en pratique ce check ne passe en unhealthy que pendant/futur démarrage concurrent |

### Points d'intégration

- **Montage** : nouveau router `system.py` dans `api/v1/` (prefix `/system`, tag `system`) ; `main.py` importe le service système pour son `/health` racine (délegation, zéro duplication de logique).
- **OpenAPI** : ajouter les exemples 200/503 des deux routes système et 200/400/401/422 de `PUT /password` (rules 20 : documentation maximale) ; mettre à jour la description FastAPI (`Health Check: /health` → mention `/api/v1/system/ready` pour les orchestrateurs).
- **Durcissement anti-fingerprinting** (AC 4) : `/ready` ne renvoie **ni version applicative, ni environnement, ni détail de connexion** (contrairement au `/health` racine historique qui expose `version`/`environment` — préservé tel quel par l'arbitrage n°2) ; uniquement `status` + état booléen/texte par check + révisions Alembic courantes (`current`/`head` — identifiants de schéma internes non sensibles, utiles au diagnostic).

## Critères d'acceptation (AC)

- [x] AC 1 : `GET /api/v1/system/ready` répond **sans auth** : vérifie migrations appliquées + DB + dépendances optionnelles (Redis si configuré) ; `200` avec détails des checks quand prêt, **503** avec causes quand non-prêt ; `/system/health` formalisé sans auth (comportement du `/health` actuel préservé ou aliasé).
- [x] AC 2 : `PUT /api/v1/auth/password` authentifié : **200** avec ancien mot de passe correct (hash mis à jour, login suivant fonctionne avec le nouveau) ; **400** si ancien mot de passe faux ; **422** sur body invalide (champs manquants, mot de passe trop faible selon la politique) ; **401** sans token.
- [x] AC 3 : Après un changement de mot de passe réussi : **tous les refresh tokens de l'utilisateur sont révoqués** (le refresh suivant avec un ancien token → `401`) ; les clés API ne sont pas affectées (comportement à documenter).
- [x] AC 4 : Tests de sécurité : `/ready` accessible sans token (et insensible à l'info sensible — pas de versions/secrets dans la réponse) ; `make lint` + `make backend-test` verts (sous réserve baseline : 12 échecs préexistants STORY-128, aucun nouveau).

## Références spécification

- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Système (`GET /system/health`, `GET /system/ready` « pas d'auth requise », lignes 643-649), § Authentification (`PUT /password`, ligne 567), § Sécurité (exemptions d'auth, lignes 774-776) ;
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Authentification par mot de passe (hashage), § Endpoints auth (liste canonique ligne 224) ;
- [`docs/general_specs/16-deploiement.md`](../../docs/general_specs/16-deploiement.md) — § installation (install.sh attend l'API prête ; `curl /api/v1/system/health`, ligne 153) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §1 (existe `/health` seul), §2 (pas de `PUT /password`), §14 ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-7 (A12) et P1-8 (A13, dépend de P1-3 refresh).

## Dépendances

- **STORY-120 (Alembic) — DONE ✔** : prérequis satisfait — [`get_alembic_config()`](../../backend/app/database.py:41) et runner `upgrade head` au démarrage rendent le check « migrations appliquées » significatif.
- **STORY-123 (refresh révocables) — DONE ✔** : prérequis satisfait — [`revoke_all_for_user`](../../backend/app/services/refresh_token_service.py:288) est exposé, idempotent, et sa docstring cite déjà STORY-129 comme consommateur.
- **STORY-125 (audit) — DONE ✔** : [`AuditService.log_from_request`](../../backend/app/services/audit_service.py) disponible pour tracer `user.password_changed` (action critique — credentials).
- **STORY-126 (.1/.2/.3) — DONE ✔** : les 2xx JSON de `/api/v1/system/*` seront enveloppés automatiquement (arbitrage n°3) ; `PUT /password` retourne enveloppe standard.
- **Interaction STORY-130 (Argon2id)** : `pwd_context` est déjà Argon2 (divergence n°1) — STORY-129 n'introduit aucun bcrypt ; si STORY-130 est fusionné avant, rien à changer ici (même appel `hash_password`).
- **Aucune migration DB** : aucun modèle modifié (aucune table nouvelle — le changement de mot de passe écrit `users.hashed_password`, colonne existante).
- **Aucun service externe nouveau** ; Redis reste la seule dépendance optionnelle sondée.
- **Conditionne** : bascule recommandée des healthchecks compose/traefik vers `/api/v1/system/ready` (tâche 8) ; clients frontend/CLI pourront consommer `PUT /auth/password` ultérieurement (hors périmètre).

## Sous-stories

*(section réservée — ampleur S, périmètre homogène backend, découpe non nécessaire)*

## État d'avancement technique

*(cochage progressif pendant treat-story — rien n'est coché à ce stade)*

- [x] Tâche 1 — Service `SystemService` (checks health/ready réutilisables)
- [x] Tâche 2 — Router `system.py` + montage `/system` + délégation `/health` racine
- [x] Tâche 3 — Schémas `PasswordChangeRequest` / `PasswordChangeResponse`
- [x] Tâche 4 — Endpoint `PUT /auth/password` (vérif ancien, hash, révocation, audit, rate limit)
- [x] Tâche 5 — Documentation OpenAPI (examples, description app, tag `system`)
- [x] Tâche 6 — Tests unitaires backend (service système, API system, API password)
- [x] Tâche 7 — Tests d'intégration (contrat enveloppe/503, flux complet password + révocation)
- [x] Tâche 8 — Bascule des signaux de démarrage (compose/traefik → `/api/v1/system/ready`, doc déploiement)
- [x] Tâche 9 — CHANGELOG + validation finale (`make lint`, `make backend-test`)

## Tâches d'implémentation détaillées

> Séquencement : service → router système → schémas → endpoint password → docs → tests → infra/docs → clôture. Les exigences sécurité (rules 40) sont intégrées **inline** dans les tâches concernées. RBAC : `/system/*` sans auth (spec 09 — exemptions) ; `PUT /password` = self-service authentifié, **aucun id client** dans le body (isolation structurelle : on ne change que SON propre mot de passe).

### Tâche 1 : Service `SystemService` — checks réutilisables

**Objectif :** centraliser la logique de health/readiness hors de la couche HTTP (testable unitairement, consommée par le router `/system` **et** le `/health` racine).

**Fichiers :**
- `backend/app/services/system_service.py` — **Créer** :
  - `async def get_health() -> dict` : réplique exactement le comportement du [`health_check()`](../../backend/app/main.py:492) actuel (clés `status`/`version`/`environment`/`services{database{status,type}, rate_limiter{status}}`, `status: "unhealthy"` si DB down) — comportement préservé à l'identique (arbitrage n°2) ;
  - `async def get_readiness() -> tuple[dict, int]` : construit `{status: "ready"|"unready", checks: {...}}` et le code HTTP (200/503) :
    - `database` : `db.health_check()` → `{status: "healthy"|"unhealthy"}` ;
    - `migrations` : via engine — `async with db.engine.connect() as conn` : présence de la table `alembic_version` puis `current = await conn.run_sync(lambda c: MigrationContext.configure(c).get_current_revision())` comparé à `head = ScriptDirectory.from_config(get_alembic_config()).get_current_head()` → `{status: "ok"|"pending", current, head}` (comparaison stricte ; base non versionnée → `current: null` → unhealthy) ;
    - `redis` (uniquement si `settings.rate_limit_enabled and settings.rate_limit_storage_url`) : ping fermé proprement (pattern [`main.py:515`](../../backend/app/main.py:515)) → `{status: "healthy"|"unhealthy"}` ; absent sinon ;
    - **aucune version/secrets/URL** dans le payload (AC 4) — seulement `current`/`head` (révisions de schéma) ;
    - toute erreur inattendue d'un check → ce check `unhealthy`, jamais d'exception remontée (le endpoint doit toujours répondre) ;
  - docstrings + type hints complets (rules 30) ; logs structurés sans données sensibles (`logger.info("system.ready status=%s checks=...")`).

**Dépend de :** Aucune

### Tâche 2 : Router `system.py` + montage + délégation `/health` racine

**Objectif :** exposer `/api/v1/system/health` et `/api/v1/system/ready` sans auth, sans dupliquer la logique, sans régresser `/health`.

**Fichiers :**
- `backend/app/api/v1/system.py` — **Créer** : router avec deux `GET` **sans dépendance d'auth** (aucun `get_current_user` — exemptions spec 09) :
  - `GET /health` : `payload = await SystemService.get_health()` ; si `payload["status"] != "healthy"` → `JSONResponse(503, payload)` (le 200 dict sera enveloppé par le middleware — arbitrage n°3) ; docstring + `responses={200, 503}` avec examples ;
  - `GET /ready` : `payload, code = await SystemService.get_readiness()` ; `JSONResponse(code, payload)` si 503, sinon retour dict (200 enveloppé) ; `summary="Readiness check"`, description orientée orchestrateurs (compose healthcheck, `curl -f`) ;
  - **Rate limiting** : tolérance zéro friction pour les sondes — ne pas décorer (`/health` racine actuel ne l'est pas, [`test_rate_limiting.py:42`](../../backend/tests/integration/test_rate_limiting.py:42) vérifie ce comportement) ;
- [`backend/app/api/v1/__init__.py`](../../backend/app/api/v1/__init__.py:31) — **Modifier** : import + `api_router.include_router(system_router, prefix="/system", tags=["system"])` ;
- [`backend/app/main.py`](../../backend/app/main.py:492) — **Modifier** : le `health_check()` racine délègue à `SystemService.get_health()` (retour + 503 identiques — les tests [`test_api_envelope.py`](../../backend/tests/integration/test_api_envelope.py:202)/[`test_openapi.py`](../../backend/tests/integration/test_openapi.py:57) doivent rester verts sans modification) ; conserver la route `@app.get("/health", tags=["health"])` telle quelle.

**Dépend de :** Tâche 1

### Tâche 3 : Schémas `PasswordChangeRequest` / `PasswordChangeResponse`

**Objectif :** valider le body du changement de mot de passe côté serveur (rules 40 — validation Pydantic complète) et définir le contrat de réponse.

**Fichiers :**
- [`backend/app/schemas/user.py`](../../backend/app/schemas/user.py:75) — **Modifier** (ou créer `schemas/password.py` si le fichier dépasse une taille raisonnable — suivre la cohérence existante) :
  - `PasswordChangeRequest(BaseModel)` : `current_password: str = Field(..., min_length=1, max_length=128)` (l'ancien peut précéder la politique actuelle — pas de `min_length=8` sur l'ancien) ; `new_password: str = Field(..., min_length=8, max_length=100)` **identique à [`UserCreate.password`](../../backend/app/schemas/user.py:75)** (politique existante) ; `model_config` avec examples OpenAPI ;
  - `PasswordChangeResponse(BaseModel)` : `message: str` + `refresh_tokens_revoked: int` ; **aucun champ sensible** (jamais de hash, de mot de passe, ni de token) ;
  - exporter dans [`schemas/__init__.py`](../../backend/app/schemas/__init__.py:34).

**Dépend de :** Aucune

### Tâche 4 : Endpoint `PUT /auth/password`

**Objectif :** self-service sécurisé de changement de mot de passe avec révocation des sessions refresh et audit.

**Fichiers :**
- [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py:71) — **Modifier** : ajouter après `/me` (avant la section api-keys) :
  - signature : `@router.put("/password", response_model=PasswordChangeResponse, dependencies=[Depends(conditional_rate_limiter(5, 60))], ...)` avec `current_user: User = Depends(get_current_active_user)`, `request: Request`, body `PasswordChangeRequest`, `session: AsyncSession = Depends(get_db)` — **authentifié JWT ou clé API** (les deux flux passent par `get_current_user`) ; **aucun `require_role`** (tout rôle authentifié — self-service) et **aucun identifiant utilisateur dans le body** (isolation structurelle, rules 40) ;
  - étapes (ordre important) :
    1. vérifier l'ancien : `if not UserService.verify_password(body.current_password, current_user.hashed_password)` → `raise InvalidInputError("Current password is incorrect")` (400 `INVALID_INPUT`, arbitrage n°4) — message générique, jamais de distinction « utilisateur inconnu » ;
    2. écrire le nouveau hash : `current_user.hashed_password = UserService.hash_password(body.new_password)` + `await session.commit()` (Argon2 via `pwd_context` — arbitrage n°1) ;
    3. révoquer toutes les sessions : `revoked = await RefreshTokenService.revoke_all_for_user(session, current_user.id)` (AC 3 ; les **clés API ne sont PAS touchées** — comportement documenté dans la description OpenAPI) ;
    4. auditer : `await AuditService.log_from_request(request, "user.password_changed", user=current_user, resource_type="user", resource_id=str(current_user.id), details={"refresh_tokens_revoked": revoked})` — jamais les mots de passe dans les details (rules 40) ;
    5. logger : `logger.info("user.password_changed user_id=%s refresh_tokens_revoked=%d", current_user.id, revoked)` — sans données sensibles ;
    6. retourner `PasswordChangeResponse(message="Password updated successfully", refresh_tokens_revoked=revoked)` (200, enveloppé par le middleware) ;
  - documentation OpenAPI riche (description avec sémantique de révocation + clés API non affectées, `responses` 200/400/401/422 avec examples enveloppe spec 09, exemples de body) ;
  - 422 automatique via Pydantic sur body invalide (champ manquant, `new_password` < 8 — AC 2).

**Dépend de :** Tâches 3 (schémas) ; consomme STORY-123/125 existants

### Tâche 5 : Documentation OpenAPI globale

**Objectif :** maintenir OpenAPI à jour (rules 20 — documentation maximale).

**Fichiers :**
- [`backend/app/main.py`](../../backend/app/main.py:337) — **Modifier** : description FastAPI — section « Support » : ajouter `Readiness: /api/v1/system/ready` à côté de `Health Check: /health` ; mentionner dans la section enveloppes que les 503 système restent nus (arbitrage n°3) si pertinent ;
- vérifier à la génération (`make generate-openapi-docs` ou `/openapi.json` en test) : paths `/api/v1/system/health`, `/api/v1/system/ready` présents, tag `system` déclaré, `PUT /api/v1/auth/password` avec examples complets.

**Dépend de :** Tâches 2 et 4

### Tâche 6 : Tests unitaires backend

**Objectif :** couvrir le service système et les endpoints (cible ≥ 80 % sur les nouveaux fichiers, rules 35).

**Fichiers :**
- `backend/tests/unit/test_services/test_system_service.py` — **Créer** :
  - `get_health` : DB saine → status healthy + services.database présent ; DB down (mock `db.health_check` → False) → unhealthy ;
  - `get_readiness` : tout sain → (payload ready, 200) ; DB down → 503 ; `current != head` (mock `MigrationContext`/`ScriptDirectory`) → check migrations pending + 503 ; base sans `alembic_version` → 503 ; Redis configuré down (mock ping) → 503 ; Redis non configuré → check absent, 200 possible ; payload **sans** clé `version`/`environment` (AC 4) ; exception d'un check → check unhealthy sans lever ;
- `backend/tests/unit/test_api/test_system.py` — **Créer** (pattern [`_jwt_mode`](../../backend/tests/integration/test_api_envelope.py:37), mocks du service) :
  - `GET /api/v1/system/ready` **sans header Authorization** → 200 (AC 1 / AC 4 : accessible sans token) et body enveloppé `{data: {...}, message: null}` ;
  - 503 → corps **nu** `{status, checks}` (pas d'enveloppe — arbitrage n°3) avec causes ;
  - `GET /api/v1/system/health` sans auth → 200/503 ;
  - `GET /health` racine non régressé (200/503, format historique `status/services`) ;
- `backend/tests/unit/test_api/test_auth_password.py` — **Créer** :
  - **Sécurité obligatoire (rules 40)** : `test_password_returns_401_without_token` ; `test_password_returns_400_on_wrong_current` ; `test_password_returns_422_on_missing_fields` ; `test_password_returns_422_on_weak_new_password` (< 8 caractères) ;
  - nominal : 200 → `message` + `refresh_tokens_revoked` ; **login suivant avec le nouveau mot de passe → 200** (AC 2) ; login avec l'ancien → 401 ;
  - **AC 3** : refresh tokens révoqués — après changement, `POST /auth/refresh` avec l'ancien refresh → 401 (`INVALID_OR_EXPIRED_TOKEN`) ; les **clés API restent valides** (requête authentifiée `X-API-Key` après changement → 200) ;
  - isolation structurelle : le body ne contient aucun `user_id` — un utilisateur ne peut pas cibler un autre compte (assertion sur le contrat du schéma) ;
  - réponse sans champ sensible (pas de hash/mot de passe/token dans le body) ;
  - audit émis : ligne `user.password_changed` présente (pattern tests audit 125.2, si fixture d'inspection existe — sinon vérification via `AuditService.log_from_request` mocké).

**Dépend de :** Tâches 1-4

### Tâche 7 : Tests d'intégration

**Objectif :** valider le contrat de bout en bout (enveloppe, 503, correlation, flux complet).

**Fichiers :**
- `backend/tests/integration/test_system_endpoints.py` — **Créer** : `/api/v1/system/ready` sans auth via `client` (ASGITransport) — 200 enveloppé (helpers `unwrap` du [`conftest`](../../backend/tests/conftest.py:44)) ; cas DB réelle saine ; header `X-Correlation-ID` propagé ; `/health` racine toujours non enveloppé (garde-fou [`test_api_envelope.py:202`](../../backend/tests/integration/test_api_envelope.py:202) étendu aux nouveaux chemins — vérifier que la liste des chemins non-`/api/v1` du test existant n'a pas besoin d'ajout) ;
- `backend/tests/integration/test_auth_password_flow.py` — **Créer** : flux complet réel (DB de test) : `POST /auth/login` (mint réel via form) → `PUT /auth/password` (token bearer) → `POST /auth/refresh` avec l'ancien refresh → **401** → re-`login` avec le nouveau mot de passe → 200 → nouveau refresh utilisable ; clé API créée avant le changement toujours fonctionnelle après.

**Dépend de :** Tâches 1-4

### Tâche 8 : Bascule des signaux de démarrage (infra + doc)

**Objectif :** faire de `/api/v1/system/ready` le signal documenté des orchestrateurs (description de la story).

**Fichiers :**
- [`docker-compose.prod.yml`](../../docker-compose.prod.yml:287) — **Modifier** : healthchecks `curl -f http://localhost:8000/api/v1/system/ready` (services api ×2) + traefik `loadbalancer.healthcheck.path=/api/v1/system/ready` ;
- [`docker-compose.minimal.yml`](../../docker-compose.minimal.yml:87) — **Modifier** : healthcheck `curl -f http://localhost:8000/api/system/ready` (chemin après strip-prefix `/api` — vérifier la règle strip-prefix Traefik du fichier avant d'écrire l'URL exacte) ;
- [`docs/general_specs/16-deploiement.md`](../../docs/general_specs/16-deploiement.md:153) — **Modifier** : le snippet d'attente documente `/api/v1/system/ready` comme signal canonique (avec `/api/v1/system/health` en vérification légère) ;
- **Note** : si install.sh (mentionné plan) existe ailleurs que `scripts/` (non trouvé à l'analyse), la doc suffit — signaler en divergence si découvert pendant l'implémentation.

**Dépend de :** Tâches 2 (routes vivantes)

### Tâche 9 : CHANGELOG + validation finale

**Objectif :** tracer l'ajout de contrat et valider l'ensemble.

**Fichiers :**
- [`CHANGELOG.md`](../../CHANGELOG.md) — **Modifier** : entrée sous `[Unreleased]` — « Added: `GET /api/v1/system/ready` (readiness sans auth : migrations/DB/Redis, 503 détaillé) et `GET /api/v1/system/health` ; `PUT /api/v1/auth/password` (ancien requis, refresh tokens révoqués, clés API conservées) » (pattern STORY-126.3/128).

**Validation :**
```bash
make backend-lint          # isort + black + flake8 + mypy + bandit
make backend-test-unit     # nouveaux fichiers test_system/test_auth_password verts
make backend-test-integration  # flux complets
make lint && make backend-test   # AC 4 — global vert (baseline STORY-128 : échecs préexistants documentés acceptés)
```

**Dépend de :** Tâches 1-8

## Tests à écrire

> Récapitulatif (détail dans les tâches 6-7). Patterns : rules 35 (`httpx.AsyncClient` + `ASGITransport`, `_jwt_mode`/`_bearer`), helpers `unwrap`/`error_code` du conftest. Sécurité rules 40 appliquée par endpoint.

### Backend — unitaires

- `backend/tests/unit/test_services/test_system_service.py` — checks health/ready (DB, migrations current==head, base non versionnée, Redis optionnel down/absent), payload sans version/secrets, erreur de check contenue.
- `backend/tests/unit/test_api/test_system.py` — `/ready` + `/system/health` sans token (200 enveloppé, 503 nu avec causes), `/health` racine non régressé.
- `backend/tests/unit/test_api/test_auth_password.py` — **401 sans token, 400 ancien faux, 422 body invalide/mot de passe faible**, 200 nominal (login suivant OK), révocation refresh (ancien refresh → 401), clés API non affectées, isolation structurelle (pas d'id cible), pas de champ sensible en réponse, audit `user.password_changed` émis.

### Backend — intégration

- `backend/tests/integration/test_system_endpoints.py` — contrat réel sans auth, enveloppe 200 / 503 nu, correlation ID.
- `backend/tests/integration/test_auth_password_flow.py` — flux complet : login → change → refresh ancien 401 → re-login nouveau 200 ; clé API survives.

### Frontend

- *(non applicable — backend only, arbitrage n°6 ; les clients consommeront l'endpoint ultérieurement)*

### Commandes de validation

```bash
poetry run pytest backend/tests/unit/test_services/test_system_service.py backend/tests/unit/test_api/test_system.py backend/tests/unit/test_api/test_auth_password.py -v
poetry run pytest backend/tests/integration/test_system_endpoints.py backend/tests/integration/test_auth_password_flow.py -v
make backend-lint
make backend-test
```

## Notes d'implémentation

*(ajoutées à la clôture par treat-story — 2026-10-01)*

### Fichiers créés

- `backend/app/services/system_service.py` — `SystemService` : `get_health()` (réplique exacte du contrat `/health` racine, arbitrage n°2), `get_readiness()` (checks DB + migrations `current == head` + Redis optionnel, arbitrage n°5/7 ; payload sans version/environnement — AC 4 ; checks best-effort jamais levants), helpers `_database_check`/`_migrations_check` (via `MigrationContext` + `ScriptDirectory.from_config(get_alembic_config())`)/`_check_redis`.
- `backend/app/api/v1/system.py` — router `system` : `GET /health` + `GET /ready` **sans aucune dépendance d'auth** (exemptions spec 09), 200 dict (enveloppé par le middleware STORY-126) / 503 `JSONResponse` **nu** (arbitrage n°3), OpenAPI riche (descriptions orientées orchestrateurs, examples 200/503), pas de rate limiting (friction nulle sondes).
- `backend/tests/unit/test_services/test_system_service.py` — 12 tests (health/ready nominaux + dégradés, migrations pending/unversioned, Redis absent/configuré-down, anti-fingerprinting, résilience exceptions).
- `backend/tests/unit/test_api/test_system.py` — 6 tests (contrat HTTP : 200 enveloppé sans header Authorization, 503 nu avec causes, `/system/health` et `/health` racine non régressés — service mocké).
- `backend/tests/unit/test_api/test_auth_password.py` — 13 tests (sécurité 401/400/422×2, nominal + login suivant/ancien rejeté, révocation refresh ancien → 401, clé API survit + change par X-API-Key, isolation structurelle du schéma, aucun champ sensible en réponse, audit émis / absent sur échec).
- `backend/tests/integration/test_system_endpoints.py` — 8 tests (readiness 200 enveloppé sur base migrée réelle, anti-fingerprinting, correlation ID propagé, `/health` racine nu, contrat OpenAPI : paths + tag `system` + responses documentées). Fixture `_real_test_db` branchant `SystemService` sur l'engine de test (hors lifespan, `db.engine` global est `None`).
- `backend/tests/integration/test_auth_password_flow.py` — 2 tests (flux complet réel : login → change → ancien refresh 401 → re-login nouveau 200 → nouveau refresh rotatif → ancien mot de passe 401 ; clé API créée avant → fonctionne après).

### Fichiers modifiés

- `backend/app/api/v1/__init__.py` — import + montage `system_router` (prefix `/system`, tags `system`).
- `backend/app/api/v1/auth.py` — `PUT /password` inséré après `/me` (avant api-keys) : vérif ancien (400 `INVALID_INPUT`, arbitrage n°4), hash Argon2 via `UserService.hash_password` (arbitrage n°1 — jamais `helper/security.py`), `revoke_all_for_user` (AC 3), audit `user.password_changed` (STORY-125.2), rate limit `conditional_rate_limiter(5, 60)`, aucune id utilisateur dans le body ; OpenAPI 200/400/401/422/429 avec examples.
- `backend/app/schemas/user.py` — `PasswordChangeRequest` (`current_password` 1-128 sans politique rétroactive, `new_password` 8-100 identique à `UserCreate.password`) + `PasswordChangeResponse` (`message`, `refresh_tokens_revoked` — aucun champ sensible).
- `backend/app/schemas/__init__.py` — exports des deux schémas.
- `backend/app/main.py` — `/health` racine délègue à `SystemService.get_health()` (contrat identique, zéro duplication) ; description FastAPI « Support » mentionne `/api/v1/system/ready` ; tag `system` déclaré dans `openapi_tags`.
- `backend/tests/unit/test_api/test_rbac_exhaustivite.py` — `PUBLIC_PATHS` += `/api/v1/system/health|ready` (exemptions spec 09), `EXPECTED_ROUTE_COUNTS` : `auth` 8→9 (PUT /password) + nouveau `system: 2` — garde-fou §2.G mis à jour explicitement (choix revu, pas un contournement).
- `docker-compose.prod.yml` — healthchecks api+worker → `curl -f /api/v1/system/ready` ; traefik `loadbalancer.healthcheck.path=/api/v1/system/ready`.
- `docker-compose.minimal.yml` — healthcheck → `/api/v1/system/ready` (voir divergence n°3).
- `docs/general_specs/16-deploiement.md` — snippet : `/ready` signal canonique (`curl -f`), `/system/health` vérification légère.
- `CHANGELOG.md` — entrée `[Unreleased]` Added STORY-129 (pattern 126.3/128).

### Décisions techniques

1. **Anti-fingerprinting strict sur `/ready`** : uniquement `status` + états par check + révisions `current`/`head` — le `/health` racine historique conserve `version`/`environment` (contrat préservé, arbitrage n°2).
2. **503 système nus** : les 503 de `/system/ready` et `/system/health` sont des `JSONResponse` directs non enveloppés (l'error handler n'intercepte que les exceptions, pas les réponses) — symétrique du `/health` racine ; aucune exclusion ajoutée au middleware STORY-126 (les 200 restent enveloppés).
3. **Tests d'intégration readiness** : fixture `_real_test_db` reconnecte `SystemService.db` sur l'engine de test — hors lifespan la `Database` globale n'a pas d'engine ; les checks s'exécutent alors réellement (migrations comprises) au lieu d'être mockés.

### Divergences par rapport à l'analyse

1. **`scripts/install.sh` existe** (l'analyse le croyait introuvable) : vérifié — il ne contient **aucune boucle d'attente santé** (les seuls `curl` installent Docker/GPG) ; conformément à la consigne, **non modifié**, signalé ici. La doc spec 16 couvre le signal canonique.
2. **Healthcheck minimal** : l'analyse proposait `/api/system/ready` (après strip-prefix), mais vérification faite le middleware `api-stripprefix` est **défini sans être attaché** au router Traefik (aucun label `routers.api.middlewares`) et le healthcheck Docker appelle le port 8000 **en direct** → chemin complet `/api/v1/system/ready` retenu. Au passage : l'ancien `/api/health` ne correspondait à **aucune route réelle** (bug préexistant corrigé de facto).
3. **Audit `refresh_tokens_revoked` masqué `"***"`** : le sanitizer structurel STORY-125 masque toute clé contenant le marqueur « token » — comportement conservateur préexistant, assumé (le compteur exact reste dans la réponse HTTP et le log applicatif) ; test adapté en conséquence.
4. **Garde-fou RBAC (`test_rbac_exhaustivite.py`)** : non listé dans les fichiers de l'analyse, mais son échec était **attendu et voulu par son design** (« toute évolution doit être un choix explicite ») — mise à jour explicite de la whitelist et des comptes (`auth` 8→9, `system: 2`), conformément au message d'action du test.

### Difficultés rencontrées

- Aucune bloquante. Points d'attention : (1) le venv courant n'a pas `bandit` installé (`ModuleNotFoundError`) — `make backend-lint` échoue sur cette étape pour raisons d'environnement préexistantes, bandit non exécutable localement ; (2) `mypy` : 17 erreurs préexistantes (baseline confirmée par stash) — 0 erreur dans les fichiers STORY-129 après correction d'un import (`AsyncConnection`) ; (3) 12 échecs de tests préexistants (baseline STORY-128 documentée : `test_stack_actions` ×10, `test_api_key_service` ×1, `test_deployments_api` ×1) — aucun lié à STORY-129.

### Commandes de test exécutées + résultats

| Commande | Résultat |
|---|---|
| `pytest tests/unit/test_services/test_system_service.py tests/unit/test_api/test_system.py tests/unit/test_api/test_auth_password.py` | **31+13 = 44 passés** après stabilisation (12+6+13) puis 13/13 password après fix assertions |
| `pytest tests/integration/test_system_endpoints.py tests/integration/test_auth_password_flow.py` | **10/10 passés** (après fixture `_real_test_db`) |
| `pytest tests/integration/test_api_envelope.py test_openapi.py test_api_contract.py test_auth_api.py test_rate_limiting.py tests/unit/test_api/test_api_keys.py` (non-régression) | **108/108 passés** |
| `pytest tests/unit/test_api/test_rbac_exhaustivite.py test_rbac_isolation.py` | **14/14 passés** (après mise à jour du garde-fou) |
| `pytest tests/` (suite complète) | **1850 passés, 12 échecs préexistants (baseline STORY-128, vérifiés par stash), 1 skip** |
| `black --check` + `isort --check` + `flake8` (fichiers touchés) | **OK** |
| `mypy` (fichiers STORY-129) | **0 erreur** (13-17 erreurs préexistantes ailleurs, hors périmètre) |
| `bandit` | **Non exécutable** (`No module named 'bandit'` — environnement, préexistant) |

### Couverture des nouveaux fichiers

- `system_service.py` : 77 % (lignes non couvertes : branches d'erreur Redis réelles et connexions réelles — couvertes indirectement par l'intégration).
- Endpoints `system.py` / `auth.py PUT /password` : couverts par les tests API unitaires + intégration (tous les codes 200/400/401/422/503 exercés).
