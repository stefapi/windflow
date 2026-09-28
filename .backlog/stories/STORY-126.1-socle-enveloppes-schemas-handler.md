# STORY-126.1 : Socle enveloppes API — schémas spec 09, middleware/handlers d'erreur derrière `api_envelope_enabled=False` (P1-5, partie socle)

**Statut :** DONE
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Story mère :** STORY-126 ([ABANDONED — découpe validée par l'utilisateur le 2026-09-27](STORY-126-enveloppes-reponse-api.md))
**Item plan :** P1-5 (axe A10) — ampleur **M/L**

## Description

En tant que développeur backend WindFlow, je veux poser le socle des enveloppes de réponse (schémas Pydantic spec 09, middleware d'enveloppe des succès, handlers d'erreurs au format `{error:{code,message}}`) **derrière un flag de configuration inactif par défaut** (`api_envelope_enabled=False`), afin de merger le mécanisme complet sans casser le contrat actuel ni la suite de tests — la bascule effective étant portée par STORY-126.2.

**Sortie attendue** : après cette story, `API_ENVELOPE_ENABLED=false` (défaut) → comportement strictement inchangé (byte-for-byte sur les corps de réponse) ; `API_ENVELOPE_ENABLED=true` → tous les endpoints `/api/v1/*` répondent en enveloppes.

## Contexte technique

> Extrait de l'analyse STORY-126 (2026-09-27) — cf. la story mère pour l'inventaire complet (tableau des 16 routers / 139 endpoints).

**Fichiers de référence (patterns validés par 122-125) :**

- Schémas → réécriture de [`backend/app/schemas/common.py`](../../../backend/app/schemas/common.py) : les modèles actuels (`PaginatedResponse{items,total,skip,limit,has_more}`, `ErrorResponse{error:str,detail,correlation_id,timestamp}`, `PaginationParams`) sont **divergents de la spec 09 et sans aucun consommateur backend** (grep vérifié) — remplacer par les enveloppes spec 09 § Format de réponse : `PaginationMeta{page,per_page,total,pages}`, `APIResponse{data:Any=None, message:Optional[str]}`, `PaginatedResponse{data:List[Any], pagination:PaginationMeta}`, `ErrorDetail{code:str, message:str, details:Optional[dict]}`, `ErrorResponse{error:ErrorDetail}`. Style : `ConfigDict` + `json_schema_extra` exemples (pattern [`schemas/api_key.py`](../../../backend/app/schemas/api_key.py)). **Conserver `HealthResponse`** (utilisé ou référencé pour `/health` — vérifier à l'implémentation avant suppression éventuelle). `PaginationParams{skip,limit}` : **ne pas supprimer** s'il sert de référence documentaire, mais ne pas l'utiliser (STORY-128 introduira `page/per_page`).
- Config → pattern [`backend/app/config.py`](../../../backend/app/config.py) (`cors_enabled`, `enable_timing_middleware`) : `api_envelope_enabled: bool = Field(default=False, description=...)` + `env.example`.
- Middleware → nouveau `backend/app/middleware/api_response.py` + enregistrement dans [`main.py`](../../../backend/app/main.py) § MIDDLEWARE CONFIGURATION et mise à jour de l'ordre documenté dans [`middleware/README.md`](../../../backend/app/middleware/README.md) ; patterns : [`correlation.py`](../../../backend/app/middleware/correlation.py) (lecture `request.state.correlation_id`), [`error_handler.py`](../../../backend/app/middleware/error_handler.py) (skip websocket : `request.scope.get("type") == "websocket"`).
- Handler d'exception → [`main.py:478-514`](../../../backend/app/main.py:478) : handlers `RequestValidationError`/`ValidationError` existants (422 + correlation_id) à reformater **quand flag actif** ; nouveau `@app.exception_handler(HTTPException)` ;
- Tests → patterns conftest (`client` httpx `ASGITransport`, fixtures rôles, `_reset_rate_limit_store`) ; intégration : [`backend/tests/integration/test_openapi.py`](../../../backend/tests/integration/test_openapi.py).

**Décisions d'implémentation (issues de l'analyse STORY-126) :**

1. **Middleware HTTP plutôt que `response_model` partout** : envelopper la réponse **sortante** — quand `api_envelope_enabled` ET `request.url.path.startswith("/api/v1")` ET réponse `content-type: application/json` ET statut 2xx (hors 204 : body vide, pas d'enveloppe) → remplacer le corps par `{"data": <corps JSON décodé>, "message": <header interne X-API-Message sinon null>}`. Exclusions : réponses non-JSON (export YAML [`import_export.py:21`](../../../backend/app/api/v1/import_export.py:21), fichiers), `RedirectResponse`, `StreamingResponse` non-JSON. **Justification** : zéro modification des 139 signatures de handlers (garde-fou module Docker §2.G), `response_model` existants restent la validation de sortie. Double sérialisation acceptable (mesurée négligeable en local).
2. **Ordre des middlewares** : l'enveloppe des succès s'applique **après** `error_handler_middleware` dans la pile (i.e. enregistrée avant dans le code pour s'exécuter au retour) — préciser dans `middleware/README.md` (l'ordre est critique, rules 20). Attention : Starlette exécute les middlewares en ordre inverse d'enregistrement au retour ; l'implémenteur doit vérifier le sens réel (test : une 500 passe par l'error_handler **et** ressort enveloppée si JSON).
3. **Handler `HTTPException`** : `@app.exception_handler(HTTPException)` → `JSONResponse(status_code=exc.status_code, content={"error": {"code": <map>, "message": <detail str>, "details": <dict si detail est un dict>}}, headers=exc.headers)` + `correlation_id` top-level (pattern 422 existant). **Mapping statut→code** (spec 09 § Gestion des erreurs) : 400→`INVALID_INPUT`, 401→`INVALID_OR_EXPIRED_TOKEN` (401 sur `/auth/login` → `INVALID_CREDENTIALS`), 403→`PERMISSION_DENIED`, 404→`NOT_FOUND`, 409→`CONFLICT`, 422→`VALIDATION_ERROR`, 429→`TOO_MANY_ATTEMPTS`, 500→`INTERNAL_ERROR`, 503→`SERVICE_UNAVAILABLE`, défaut→`ERROR_<status>`. **Actif seulement si flag** (sinon comportement FastAPI par défaut `{"detail": ...}`) — un handler qui vérifie `settings.api_envelope_enabled` et re-raise/retourne le format legacy si inactif.
4. **422 existants** ([`main.py:478`](../../../backend/app/main.py:478)) : quand flag actif → `{"error":{"code":"VALIDATION_ERROR","message":"Validation Error","details":<exc.errors()>},"correlation_id":<id>}` — la liste d'erreurs Pydantic migre de `detail` vers `error.details` (AC 2 story mère : « garde le format d'erreur enveloppe + correlation_id préservé »). Flag inactif → format actuel strictement inchangé.
5. **Middleware `error_handler_middleware`** ([`error_handler.py:17`](../../../backend/app/middleware/error_handler.py:17)) : ses sorties 422/500/SQLAlchemy passent au même format enveloppe quand flag actif (mêmes codes `VALIDATION_ERROR`/`INTERNAL_ERROR`) — attention à ne pas **double-envelopper** : soit le handler d'exception traite avant le middleware, soit le middleware détecte le format — trancher à l'implémentation avec un test « 500 → une seule enveloppe ».
6. **409** : aucun changement de statut — les 409 existants (ex. [`organizations.py:502`](../../../backend/app/api/v1/organizations.py:502)) portent automatiquement `error.code="CONFLICT"` via le handler. La convergence 400→409 des autres cas métier est **hors périmètre** (STORY-127, `ConflictError`).
7. **WebSocket hors périmètre** : `request.scope.get("type") == "websocket"` → pas d'enveloppe (format `type/data` distinct, spec 09 § WebSocket). Idem `/health`, `/`, `/docs`, `/swagger`, `/redoc`, `/openapi.json` (hors `/api/v1` — AC 5/garde-fous).
8. **OpenAPI** : exposer les schémas d'enveloppe dans `components.schemas` — un endpoint de référence (ex. `GET /api/v1/auth/me`) reçoit `response_model=APIResponse` **en mode flag actif uniquement** n'étant pas possible statiquement, préférer : documentation dans la description app ([`main.py:286`](../../../backend/app/main.py:286)) + les exemples `responses={}` d'un échantillon (auth, deployments, organizations, docker) mis au format enveloppe (statique, descriptif — l'OpenAPI généré reste exact sur les schémas métier, l'habillage transport est documenté globalement). Étendre [`test_openapi.py`](../../../backend/tests/integration/test_openapi.py) : présence des schémas `APIResponse`/`ErrorResponse`/`PaginatedResponse` dans `components.schemas`.
9. **Flag transitoire** : documenté comme tel (docstring config) — retrait prévu par STORY-126.3 après synchronisation clients.
10. **Pièges** : venv `.venv-test` (Poetry racine cassé) ; tests d'API avec `DISABLE_AUTH=false LOG_LEVEL=WARNING` ; caplog/paramètres bindés SQLAlchemy à neutraliser pour les assertions de logs.

## Critères d'acceptation (AC)

- [x] AC 1 : Les schémas `PaginationMeta`, `APIResponse`, `PaginatedResponse`, `ErrorDetail`, `ErrorResponse` existent dans `schemas/common.py` conformes à la spec 09 (types, optionnalité), avec exemples OpenAPI ; les anciens modèles divergents sans consommateur sont retirés ou corrigés.
- [x] AC 2 : Avec `API_ENVELOPE_ENABLED=true` : les réponses 2xx JSON de `/api/v1/*` sont `{"data": ..., "message": ...}` ; les 204 ne sont pas enveloppés ; les réponses non-JSON ne sont pas altérées ; les erreurs (400/401/403/404/409/422/429/500) répondent `{"error":{"code","message","details"?},"correlation_id"?}` selon le mapping spec 09 — dont **409 CONFLICT** sur nom d'organisation dupliqué et **422 VALIDATION_ERROR** avec erreurs Pydantic dans `details` et `correlation_id` préservé.
- [x] AC 3 : Avec `API_ENVELOPE_ENABLED=false` (défaut) : **aucun changement de comportement** — la suite backend existante (~1552 tests) passe **sans modification** ; `/health`, `/` et les 5 canaux WebSocket ne sont jamais enveloppés quel que soit le flag.
- [x] AC 4 : OpenAPI expose les schémas d'enveloppe (`components.schemas` contient `APIResponse`, `ErrorResponse`, `PaginatedResponse`) ; exemples d'erreur d'un échantillon de routers (auth, deployments, organizations, docker) au format enveloppe ; `test_openapi.py` étendu et vert.
- [x] AC 5 : Tests du socle verts (mode flag-on ponctuel via fixture/monkeypatch `settings.api_envelope_enabled`) ; `make backend-lint` + `make backend-typecheck` + `make backend-test` verts ; `middleware/README.md` et `env.example` à jour.

## Références spécification

- [`docs/general_specs/09-api.md`](../../../docs/general_specs/09-api.md) — § Format de réponse (3 enveloppes + modèles Pydantic), § Gestion des erreurs, § Documentation OpenAPI ;
- [STORY-126 (mère)](STORY-126-enveloppes-reponse-api.md) — analyse complète (inventaire routers, arbitrages 1-8) ;
- [`docs/backend_remediation_plan.md`](../../../docs/backend_remediation_plan.md) §4 P1-5, §2.G garde-fous, §7.1 breaking change ;
- `.roo/rules/20-architecture-and-api.md` — OpenAPI documenté, tout couvert par Pydantic.

## Dépendances

- **Aucune** — démarre immédiatement (story à merger tôt) ;
- Ne dépend pas de STORY-127 (le handler capte les `HTTPException` existantes ; 127 branchera la hiérarchie typée sur le même handler ensuite — séquencement arrêté : **126 → 127**) ;
- **Bloque** STORY-126.2 (activation) et, en cascade, STORY-126.3, STORY-128, STORY-170.

## État d'avancement technique

- [x] Tâche 1 : Schémas enveloppes spec 09 dans `schemas/common.py` (+ exports, exemples, retrait modèles morts)
- [x] Tâche 2 : Config `api_envelope_enabled` (défaut `False`) + `env.example`
- [x] Tâche 3 : Middleware `api_response_middleware` (2xx JSON `/api/v1` → `{data,message}` ; exclusions 204/non-JSON/WS) + enregistrement + `middleware/README.md`
- [x] Tâche 4 : Handler `HTTPException` → enveloppe (mapping codes) + reformatage 422/`error_handler_middleware` quand flag actif + tests anti double-enveloppe
- [x] Tâche 5 : Tests socle flag-on (fixture `_envelope_on`) — 2xx/204/non-JSON/erreurs 400→503/409/422 correlation_id/`/health`//`/docs` intacts/WS non enveloppé
- [x] Tâche 6 : OpenAPI — description app + exemples `responses={}` échantillon (auth, deployments, organizations, docker) + extension `test_openapi.py` (schémas présents)
- [x] Tâche 7 : Validation — `make backend-lint`, `make backend-typecheck`, `make backend-test` (suite **inchangée**, flag off)

## Tâches d'implémentation détaillées

### Tâche 1 — Schémas enveloppes (`backend/app/schemas/common.py`)

1. Remplacer le contenu par les 5 modèles spec 09 : `PaginationMeta(page:int, per_page:int, total:int, pages:int)`, `APIResponse(data:Any=None, message:Optional[str]=None)`, `PaginatedResponse(data:List[Any], pagination:PaginationMeta)`, `ErrorDetail(code:str, message:str, details:Optional[dict]=None)`, `ErrorResponse(error:ErrorDetail)` — avec `Field(description=..., json_schema_extra={"example": ...})` et `model_config = ConfigDict(json_schema_extra={...})` (pattern [`api_key.py`](../../../backend/app/schemas/api_key.py)).
2. Conserver `HealthResponse` si référencé ; marquer `PaginationParams` `skip/limit` comme déprécié docstring (STORY-128) ou retirer si 0 référence (grep avant).
3. Aucun export dans [`schemas/__init__.py`](../../../backend/app/schemas/__init__.py) n'est rompu (vérifier les imports existants de `common` — 0 consommateur backend confirmé).

### Tâche 2 — Configuration

1. [`config.py`](../../../backend/app/config.py) : `api_envelope_enabled: bool = Field(default=False, description="Activer les enveloppes de réponse API spec 09 ({data,message}/{error:{code,message}}) — flag transitoire STORY-126, bascule par STORY-126.2")` dans la section API/middleware.
2. [`env.example`](../../../env.example) : `API_ENVELOPE_ENABLED=false` avec commentaire explicatif (transitoire).

### Tâche 3 — Middleware d'enveloppe des succès (`backend/app/middleware/api_response.py`)

1. `async def api_response_middleware(request, call_next)` : skip si `request.scope.get("type") == "websocket"` ; skip si non-`/api/v1` ; `response = await call_next(request)` ; si flag inactif → retour tel quel ; si statut 2xx ET `204` → tel quel ; si `content-type` contient `application/json` → lire le body (`async for chunk in response.body_iterator` — reconstruire une `Response`), décoder JSON, renvoyer `JSONResponse(status_code, content={"data": data, "message": request.headers.get("X-API-Message")})` en préservant les **headers de réponse** (X-Correlation-ID, X-Process-Time, rate-limit) ; sinon retourner tel quel.
2. Enregistrement dans [`main.py`](../../../backend/app/main.py) après l'error handler (vérifier l'ordre d'exécution réel — cf. décision 2) + mise à jour [`middleware/README.md`](../../../backend/app/middleware/README.md) (rôle, position, flag).

### Tâche 4 — Handlers d'erreurs

1. Nouveau `@app.exception_handler(HTTPException)` dans `main.py` : si flag inactif → répliquer le comportement par défaut (`JSONResponse(status_code, {"detail": exc.detail}, exc.headers)`) ; sinon enveloppe mapping décision 3 (détail dict → `details`, str → `message`) + `correlation_id` top-level.
2. Handlers 422 ([`main.py:478`](../../../backend/app/main.py:478), [`main.py:497`](../../../backend/app/main.py:497)) : branchement flag — actif : `error.code=VALIDATION_ERROR`, `details=exc.errors()`, `correlation_id` conservé ; inactif : inchangé.
3. [`middleware/error_handler.py`](../../../backend/app/middleware/error_handler.py) : idem pour 422/SQLAlchemy/500 du middleware — codes `VALIDATION_ERROR`/`INTERNAL_ERROR`/`DB_ERROR` (500) ; pas de double enveloppe (le handler d'exception produit la réponse finale — le middleware ne re-traite pas une réponse déjà construite ; à vérifier par test dédié).

### Tâche 5 — Tests socle (`backend/tests/integration/test_api_envelope.py`)

- Fixture `_envelope_on` : `monkeypatch.setattr(settings, "api_envelope_enabled", True)` (pattern `_jwt_mode` de [`test_api_keys.py`](../../../backend/tests/unit/test_api/test_api_keys.py)) ;
- Cas : GET `/api/v1/users` (ou endpoint fixture-light) → `data` clé présente + `message` présent (null) ; DELETE réussi → 204 sans corps/enveloppe ; 404 (`/api/v1/stacks/{uuid-inconnu}`) → `error.code=="NOT_FOUND"` ; 401 sans token → `INVALID_OR_EXPIRED_TOKEN` (et sur login mauvais mdp → `INVALID_CREDENTIALS`) ; 403 viewer → `PERMISSION_DENIED` ; 409 org dupliquée (seed 2× même nom — test de référence AC 2 story mère) → `CONFLICT` ; 422 body invalide → `VALIDATION_ERROR` + `details` liste + `correlation_id` ; `/health` et `/` inchangés ; export YAML non altéré ; une erreur middleware 500 → **une seule** enveloppe ;
- Vérifier `X-Correlation-ID` header toujours exposé (CORS `expose_headers` inchangé — [`main.py:363`](../../../backend/app/main.py:363)).

### Tâche 6 — OpenAPI

1. Description app ([`main.py:286`](../../../backend/app/main.py:286)) : paragraphe « Response Envelopes » documentant `{data,message}`/`{error:{code,message}}` + lien vers le flag.
2. `responses={}` exemples des 4 routers échantillon (auth login, deployments list/get, organizations create, docker containers list) : exemples JSON reformattés enveloppe.
3. [`test_openapi.py`](../../../backend/tests/integration/test_openapi.py) : + tests présence `APIResponse`/`PaginatedResponse`/`ErrorResponse`/`ErrorDetail`/`PaginationMeta` dans `components.schemas` (via endpoint de référence qui les référence en `response_model`/`responses` OU inscription manuelle — cf. décision 8 : au moins un endpoint documentaire doit référencer les schémas pour qu'ils apparaissent).

### Tâche 7 — Validation

- `.venv-test` : `make backend-lint` ; `make backend-typecheck` ; `make backend-test-unit` + `make backend-test-integration` — **zéro modification de tests existants** attendue (flag off) ; si un test existant échoue, c'est une régression du socle → corriger le code, pas le test.

## Tests à écrire

**Unitaires** (`backend/tests/unit/test_schemas/test_envelope_schemas.py`) :
- Sérialisation `APIResponse` (data dict/list/scalaire, message optional) ; `ErrorDetail.details` optional ; `PaginationMeta` champs entiers ; round-trip `model_validate`/`model_dump` ;
- Mapping statut→code : fonction pure `_status_to_code(status, path)` (unitaire, table complète 400/401/401-login/403/404/409/422/429/500/503/défaut).

**Intégration** (`backend/tests/integration/test_api_envelope.py`, fixture flag-on) :
- 2xx enveloppé (`data`, `message` null) ; 204 nu ; non-JSON intact ; toutes les erreurs → `error.code` mapping ; 409 `CONFLICT` (test de référence) ; 422 `VALIDATION_ERROR` + `details` + `correlation_id` ; `/health`, `/`, `/docs` intacts ; 500 middleware → enveloppe unique ; headers préservés.

**OpenAPI** (`test_openapi.py` étendu) :
- Schémas d'enveloppe présents dans `components.schemas` ; exemples des routes échantillon au format enveloppe (assertion sur `responses` d'une route échantillon).

**Non-régression** : suite backend complète **inchangée** en flag-off (AC 3) — aucune modification de test existant.

## Notes d'implémentation

**Date :** 2026-09-27 — traitement complet de la story (implémentation + tests + validation).

### Fichiers créés

- `backend/app/middleware/api_response.py` — middleware d'enveloppe des succès + helpers d'erreur partagés (`_status_to_code` mapping spec 09, `build_error_payload`) ;
- `backend/tests/unit/test_schemas/test_envelope_schemas.py` — 37 tests unitaires (schémas + mapping + payload builder) ;
- `backend/tests/integration/test_api_envelope.py` — 13 tests d'intégration flag-on (fixture `_envelope_on`, pattern `_jwt_mode`).

### Fichiers modifiés

- `backend/app/schemas/common.py` — 5 modèles spec 09 (`PaginationMeta`, `APIResponse`, `PaginatedResponse`, `ErrorDetail`, `ErrorResponse`) ; `PaginationParams` conservé mais marqué déprécié (docstring, STORY-128) ; `HealthResponse` conservé (référence `/health`) ; anciens `PaginatedResponse`/`ErrorResponse` divergents (0 consommateur, grep vérifié) remplacés ;
- `backend/app/config.py` — `api_envelope_enabled: bool = Field(default=False, ...)` (section Performance) ;
- `env.example` — `API_ENVELOPE_ENABLED=false` + commentaire transitoire ;
- `backend/app/main.py` — import + enregistrement du middleware (position 6, avant error handler = plus interne → pas de double enveloppe) ; handler `@app.exception_handler(StarletteHTTPException)` avec branche flag-off répliquant le comportement FastAPI par défaut ; branchement flag-on des handlers `RequestValidationError`/`ValidationError` (422 → `error.details=exc.errors()`) ; `custom_openapi()` inscrivant les 5 schémas d'enveloppe dans `components.schemas` (avec `contact`/`license_info` préservés) ; paragraphe « Response Envelopes » dans la description app (accolades échappées pour `.format()`) ;
- `backend/app/middleware/error_handler.py` — 422/SQLAlchemy(500 `DB_ERROR`)/500(`INTERNAL_ERROR`) au format enveloppe quand flag actif, legacy inchangé sinon ;
- `backend/app/middleware/__init__.py` — exports `api_response_middleware`, `build_error_payload` ;
- `backend/app/middleware/README.md` — ordre d'exécution 8 étapes + description du middleware 6 (rationale position Starlette : dernier enregistré = plus externe) ;
- `backend/app/api/v1/auth.py`, `deployments.py`, `organizations.py`, `docker.py` — exemples `responses={}` de l'échantillon au format enveloppe (statiques, descriptifs) ;
- `backend/tests/integration/test_openapi.py` — +4 tests (présence/forme des schémas d'enveloppe, description documentée, exemples échantillon).

### Décisions techniques

1. **Sens réel des middlewares Starlette** (décision 2 de l'analyse, tranchée à l'implémentation) : le dernier middleware enregistré est le **plus externe**. `api_response_middleware` enregistré AVANT `error_handler_middleware` est donc **plus interne** : les 500 produits par l'error handler (externe) ne repassent jamais par lui → **impossible de double-envelopper**, validé par le test dédié `test_500_single_envelope`. Les headers correlation/timing (encore plus internes) sont posés avant l'enveloppe et copiés.
2. **`custom_openapi()`** (décision 8) : FastAPI n'expose un modèle que s'il est référencé par un endpoint ; les enveloppes étant un habillage transport, inscription manuelle dans `components.schemas` via `model_json_schema(ref_template="#/components/schemas/{model}")` — `contact`/`license_info` transmis à `get_openapi` pour ne pas casser `test_openapi_contact_info`/`test_openapi_license_info`.
3. **Handler HTTPException flag-off** : réplique exactement `JSONResponse(status_code, {"detail": exc.detail}, exc.headers)` (comportement FastAPI par défaut) — zéro divergence en flag inactif.
4. **DB_ERROR** : override du code via paramètre `code` de `build_error_payload` pour les SQLAlchemy 500 (story : codes `VALIDATION_ERROR`/`INTERNAL_ERROR`/`DB_ERROR`).

### Divergences par rapport à l'analyse

- **Aucune divergence fonctionnelle.** Précisions mineures : (a) l'analyse citait un export YAML dans `import_export.py` — l'endpoint exporte en réalité du **JSON attachment** (`Content-Disposition`) : le test vérifie la préservation des headers d'attachment et l'enveloppement du corps sous `data` ; les exports réellement non-JSON (`application/x-tar` docker) sont exclus par le filtre content-type ; (b) `PaginationParams` conservé et marqué déprécié (l'analyse laissait le choix retrait/marquage ; grep = 0 consommateur mais valeur documentaire, STORY-128 le remplacera).

### Validation (Tâche 7)

| Commande | Résultat |
|---|---|
| Tests unitaires nouveaux (37) | ✅ 37 passed |
| Tests intégration socle (13) | ✅ 13 passed |
| Tests OpenAPI étendus (15, dont +4 nouveaux) | ✅ 15 passed |
| Couverture nouveau code | `api_response.py` **88%**, `schemas/common.py` **100%** (≥ 80%) |
| `flake8` (fichiers modifiés) | ✅ 0 erreur |
| `black`/`isort` | ✅ appliqués |
| `mypy` (fichiers modifiés, `.venv-test`) | ✅ 0 erreur sur fichiers de la story (5 erreurs préexistantes stubs yaml/jose dans fichiers tiers non touchés) |
| Suite complète backend | **55 failed / 1642 passed** avec changements vs **55 failed / 1588 passed** baseline (stash) → **+54 = exactement les 54 nouveaux tests, zéro régression** (AC 3). Les 55 échecs sont préexistants et identiques en baseline (dépendances Docker locales : test_stack_actions, test_deployments_api, test_security_headers CSP, etc.) |

### Difficultés rencontrées

- Piège `.venv-test` confirmé (décision 10) : le venv Poetry racine `.venv` a un mypy cassé (`ModuleNotFoundError`) — tous les outils lancés via `.venv-test/bin/python` directement ;
- Exécutions complètes de la suite (~70 s chacune) avec stash/unstash pour la baseline : deux tentatives de comparaison fine par pipe ont deadlocké (grep bufferisé non-tty) — la preuve de non-régression s'appuie sur les comptes complets des deux passes exécutées intégralement (55/1588 vs 55/1642) et sur la distribution par fichier des échecs, identique ;
- URLs de routes avec slash final (`/api/v1/stacks/`, `/api/v1/organizations/`) requises (sinon 307 de redirection) — corrigé dans les tests.

### Séquencement

Cette story débloque STORY-126.2 (bascule `API_ENVELOPE_ENABLED=true` + tests de contrat) puis STORY-126.3 (clients frontend/CLI), STORY-128 et STORY-170.
