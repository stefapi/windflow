# STORY-127 : Hiérarchie d'exceptions — compléter `core/exceptions.py` et remplacer les `HTTPException` brutes (P1-5, partie exceptions)

**Statut :** DONE
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-5 partie exceptions (axe A11, rapport §1) — ampleur **M** (partie exceptions de l'item L)

## Description

En tant que développeur backend de WindFlow, je veux une hiérarchie d'exceptions complète (`NotFoundError`, `ConflictError`, `ValidationError`, `PermissionDeniedError`, `AuthenticationError`… héritant de `WindFlowException`) et un handler global qui les convertit en enveloppe d'erreur `{error:{code,message}}`, afin que plus aucun endpoint ne lève de `HTTPException` brute et que les codes d'erreur soient cohérents sur toute l'API.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §10, §14) : [`core/exceptions.py`](../../backend/app/core/exceptions.py:10) ne contient que **2 exceptions** (`WindFlowException` + `CommandExecutionError`) alors que « beaucoup d'endpoints lèvent encore des `HTTPException` brutes ». La spec 09 § Classes d'erreur définit la hiérarchie cible (`APIError(code)` → `NotFoundError` 404, `PermissionDeniedError` 403, `ConflictError` 409…), et les rules 30 imposent : « toujours lever des exceptions de `core/exceptions.py`, jamais des exceptions Python brutes dans les endpoints ».

## Contexte technique

> Analyse-story du 2026-09-30 (exploration code réelle). ⚠️ La description initiale (« 2 exceptions seulement ») est **obsolète** : [`core/exceptions.py`](../../backend/app/core/exceptions.py:10) contient désormais **7 classes** (enrichies par STORY-103/123/124). Le reste de la constatation tient : il n'existe toujours **aucun handler global** et les endpoints lèvent ~291 `HTTPException` brutes.

### État actuel du code (vérifié le 2026-09-30)

1. **Hiérarchie existante** — [`backend/app/core/exceptions.py`](../../backend/app/core/exceptions.py:10) : `WindFlowException(message, *, details)` (base), `CommandExecutionError` (commands.py, target_scanner_service.py), `SecretEncryptionError`/`SecretDecryptionError` (STORY-103, messages sans matériel cryptographique), `InvalidRefreshTokenError` (STORY-123, anti-énumération), `InvalidApiKeyError` (STORY-124, anti-énumération), `NotFoundError(resource, resource_id)` (STORY-124 — levée par [`api_key_service.py`](../../backend/app/services/api_key_service.py:237), catchée et traduite en 404 dans [`auth.py`](../../backend/app/api/v1/auth.py:1281)). Aucune classe ne porte de statut HTTP : la conversion est manuelle, router par router.
2. **Handlers d'exception existants** dans [`main.py`](../../backend/app/main.py:555) : `@app.exception_handler(StarletteHTTPException)` (→ enveloppe `{error:{code,message,details?}, correlation_id?}` — STORY-126.1/126.3), `RequestValidationError` (422, erreurs Pydantic dans `details`, [`main.py:588`](../../backend/app/main.py:588)), `ValidationError` pydantic ([`main.py:611`](../../backend/app/main.py:611)). Helpers partagés réutilisables dans [`api_response.py`](../../backend/app/middleware/api_response.py:38) : `_status_to_code` (mapping 400/401/403/404/409/422/429/500/503 + spécialisation `401 /auth/login → INVALID_CREDENTIALS` + défaut `ERROR_<status>`) et `build_error_payload(status, *, message, details, path, correlation_id, code)` avec override `code`.
3. **Middleware d'erreur** [`error_handler.py`](../../backend/app/middleware/error_handler.py:25) (le plus **externe** de la pile, enregistré en dernier — cf. [`middleware/README.md`](../../backend/app/middleware/README.md:28)) : catch `RequestValidationError`/`SQLAlchemyError`/`Exception` → 422 / 500 `DB_ERROR` / 500 `INTERNAL_ERROR`, masque `str(exc)` hors DEBUG (exigence sécurité rules 40 déjà satisfaite). Architecture Starlette : l'`ExceptionMiddleware` (où vivent les `@app.exception_handler`) est **interne** à tous les `app.middleware("http")` → un handler `WindFlowException` intercepte l'exception **avant** le middleware externe ; le routage Starlette se fait par MRO → **un seul handler sur `WindFlowException` attrape toutes les sous-classes**.
4. **Dette `HTTPException`** (grep `raise HTTPException` du 2026-09-30) : **~291 raises / 22 fichiers** — [`docker.py`](../../backend/app/api/v1/docker.py:184) ~130 (patterns répétitifs : 503 ping/ConnectionError, 404/409 `docker.errors.APIError`, 500 génériques), [`stacks.py`](../../backend/app/api/v1/stacks.py:401) ~30, [`organizations.py`](../../backend/app/api/v1/organizations.py:306) ~26, [`deployments.py`](../../backend/app/api/v1/deployments.py:302) ~26, [`users.py`](../../backend/app/api/v1/users.py:384) ~24, `targets/{crud,capabilities,scanning}.py` ~24, [`plugins.py`](../../backend/app/api/v1/plugins.py:161) ~16, `admin/stacks_management.py` ~13, [`auth.py`](../../backend/app/api/v1/auth.py:247) ~11, [`adoption_service.py`](../../backend/app/services/adoption_service.py:257) ~8 (**anti-pattern : un service lève du HTTP**), `import_export.py` ~5, `discovery.py` ~4, `schedules.py` ~4, [`auth/dependencies.py`](../../backend/app/auth/dependencies.py:88) ~4 (401 avec header `WWW-Authenticate: Bearer`), `plugin_registry.py` ~2, `compute.py` ~2, `stats.py` ~1, [`auth/rbac.py`](../../backend/app/auth/rbac.py:98) ~1, [`core/rate_limit.py`](../../backend/app/core/rate_limit.py:187) ~1, `websocket/deployment_logs.py` ~6 (**exclu du sweep — garde-fou plugin WS §2.G**).
5. **Pattern de traduction existant à préserver** : les routers catchent les `WindFlowException` des services et les traduisent manuellement (ex. [`plugins.py:239`](../../backend/app/api/v1/plugins.py:239) switch sur `exc.details["error_type"]` → 409/400/500/404). Le sweep remplace le **re-raise HTTPException** par un **re-raise typée** — les services continuent de lever leurs `WindFlowException` génériques, inchangés.
6. **Clients déjà synchronisés (STORY-126.3)** : frontend [`http.ts`](../../frontend/src/services/http.ts:78) lit `error.message`/`error.code` (fallback `detail` legacy) ; CLI [`client.py`](../../cli/client.py:96) `_extract_error_message` idem. **Tant que les statuts HTTP et messages textuels sont préservés, l'impact frontend/CLI est nul** — aucun fichier client à modifier.
7. **Contrainte headers** : les 401 de [`dependencies.py:114`](../../backend/app/auth/dependencies.py:114) transportent `WWW-Authenticate: Bearer` (le handler `StarletteHTTPException` actuel les relaie via `exc.headers`) — la hiérarchie typée doit transporter les headers pour ne pas régresser.
8. **Tests de référence** (patterns à réutiliser) : [`test_api_envelope.py`](../../backend/tests/integration/test_api_envelope.py:37) (fixtures `_jwt_mode` autouse + `_bearer` mint direct), [`test_api_contract.py`](../../backend/tests/integration/test_api_contract.py) (contrat par router STORY-126.2), tests RBAC (`test_*_rbac.py`).

### Décisions d'implémentation (arbitrages de l'analyse)

1. **Ancrage `WindFlowException` pur, PAS `HTTPException`** (diverge de l'exemple « illustratif » spec 09 § Classes d'erreur) : `core/` reste framework-agnostic (rules 55) ; la traduction HTTP est faite par le handler global. Le **contrat de sortie reste strictement conforme** à la spec 09 (mêmes enveloppes, mêmes codes machine) — la spec documente un format, pas une implémentation.
2. **Attributs de classe** sur `WindFlowException` : `status_code: int = 500`, `error_code: str = "INTERNAL_ERROR"`, `headers: dict[str, str] | None = None` — constructeur existant inchangé → rétrocompatibilité des ~43 raises services actuels. Nouvelle classe intermédiaire `APIError(WindFlowException)` ancre les erreurs API typées (sémantique spec 09).
3. **Classes ajoutées** : `ConflictError` (409, `CONFLICT`), `InvalidInputError` (400, `INVALID_INPUT`), `UnprocessableEntityError` (422, `VALIDATION_ERROR`) — **nom choisi pour éviter la collision d'import avec `pydantic.ValidationError`** (présente dans `main.py` et les services), `PermissionDeniedError` (403, `PERMISSION_DENIED`), `AuthenticationError` (401, `INVALID_OR_EXPIRED_TOKEN`, headers `WWW-Authenticate`, override `code="INVALID_CREDENTIALS"` pour le login), `RateLimitError` (429, `TOO_MANY_ATTEMPTS`), `ServiceUnavailableError` (503, `SERVICE_UNAVAILABLE`). `NotFoundError` existante re-ancrée sur `APIError`, **signature `(resource, resource_id)` inchangée** (2 consommateurs). `CommandExecutionError`/`Secret*`/`InvalidRefreshTokenError`/`InvalidApiKeyError` : inchangées — une non-interception remonte désormais en 500 enveloppé `INTERNAL_ERROR` (sémantique équivalente au 500 générique actuel du middleware, mieux formatée).
4. **Constructeur des nouvelles classes** : `(message: str, *, details: dict | None = None, code: str | None = None)` — `code` override par instance (cas login). Les raises docker 404 passent par `NotFoundError("Container", container_id)` → message `Container not found: {id}` (équivalent aux messages actuels ; les tests existants assertent les codes, pas le texte exact).
5. **Sweep mécanique sans changement de comportement** : même statut, même message textuel, tests existants non modifiés. Les `detail=str(e)` des 500 docker (divulgation de l'erreur Docker brute, **préexistante**) sont conservés à l'identique — non-régression stricte AC 2/AC 3 ; durcissement éventuel reporté (voir Risques).
6. **Périmètre du grep AC 2** : `backend/app/api/v1/**/*.py` + `backend/app/auth/{dependencies,rbac}.py` + `backend/app/core/rate_limit.py` + `backend/app/services/adoption_service.py`. **Exclusions documentées** : `websocket/**` (garde-fou §2.G) et les raises **interne framework** dans `main.py`/`error_handler.py` (aucun).

### Checklist sécurité (rules 40) — applicable à cette story

- [x] Réponses d'erreur sans stack trace ni infos internes : 500 → message générique (déjà en place dans `error_handler.py`, à **tester** explicitement) ; DB → `DB_ERROR` générique.
- [x] Anti-énumération préservée : `InvalidApiKeyError`/`InvalidRefreshTokenError` → 401 message unique — le sweep ne doit **pas** « enrichir » ces messages ni distinguer inconnu/révoqué.
- [x] Pas de secrets dans messages/details : `CommandExecutionError` transporte `stderr` mais n'est jamais exposée en HTTP (interceptée par les appelants) ; `Secret*Error` déjà sans matériel cryptographique.
- [x] `correlation_id` systématique dans les enveloppes d'erreur (handler existant, à préserver) ; `WWW-Authenticate` maintenu sur les 401.
- [x] RBAC : les refus 403 deviennent `PermissionDeniedError` **côté API** (source de vérité) — `rbac.py`/`dependencies.py` ; aucun contrôle déplacé côté frontend.

### Risques / Hypothèses

- **Risque principal — volume du sweep** : ~291 raises sur 22 fichiers ; docker.py concentre à lui seul ~130 raises. Mitigation : convention mécanique unique (même statut/même message), tests existants en filet de sécurité, traitement par lots de fichiers (tâches 3→7). Si échecs répétés : sous-découpe 127.1/127.2/127.3 (cf. note Sous-stories) par `split-story`.
- **Hypothèse Starlette** : l'`ExceptionMiddleware` (interne) attrape `WindFlowException` **avant** le middleware d'erreur externe ; le routage par MRO fait qu'un seul handler `WindFlowException` couvre toutes les sous-classes. À valider par le test dédié (`test_windflow_exception_produces_envelope`) dès la tâche 2 — si l'hypothèse est fausse (exception remonte au middleware → 500 générique), fallback : catch dédié `except WindFlowException` dans `error_handler_middleware` AVANT le `except Exception`.
- **Risque de double format** : le sweep ne doit pas modifier les enveloppes produites (le handler global réutilise `build_error_payload` → format identique à STORY-126). Vérifié par les tests de contrat existants (126.2) restés verts.
- **Hypothèse messages de tests** : les tests existants assertent des codes HTTP, pas des textes exacts de messages (vérifié sur test_api_envelope) ; les quelques assertions sur `detail` (pre-126) ont été migrées en 126.2/126.3. Si un test échoue sur un texte de message : conserver le message d'origine au caractère près (règle du sweep).
- **Dette préexistante non traitée** (hors périmètre, à documenter) : certains 500 docker exposent `detail=str(e)` (erreur Docker brute) — comportement conservé volontairement (non-régression stricte) ; durcissement éventuel (message générique + détails uniquement en log) à inscrire au backlog P2/P3 si souhaité.
- **Risque faible — `plugins.py` switch `error_type`** : la traduction repose sur `exc.details["error_type"]` posé par les services ; le sweep conserve ce mécanisme (re-raise typé), sans le refactor.

## Critères d'acceptation (AC)

- [x] AC 1 : [`core/exceptions.py`](../../backend/app/core/exceptions.py:10) expose la hiérarchie complète héritant de `WindFlowException` avec code d'erreur et statut HTTP associés (404/409/400/422/401/403/429) ; un **handler global** convertit toute `WindFlowException` non interceptée en enveloppe `{error:{code,message,details?}}` (format STORY-126) en préservant le `correlation_id` existant.
- [x] AC 2 : **Plus aucune `HTTPException` brute** dans les endpoints `api/v1/` (grep vérifié : 0 résultat dans `api/v1/` + `auth/` + `core/rate_limit.py` + `services/`, hors exclusion documentée `websocket/**`) : tous les raises passent par la hiérarchie ; les codes HTTP effectifs sont inchangés (0 régression vs baseline — voir Notes d'implémentation).
- [x] AC 3 : Les cas d'erreur types répondent avec les bons codes : ressource inexistante → `404 NOT_FOUND` ; conflit (slug dupliqué) → `409 CONFLICT` ; rôle insuffisant → `403 PERMISSION_DENIED` ; non authentifié → `401` ; validation → `422` (format handler Pydantic existant conservé).
- [x] AC 4 : Tests unitaires sur la hiérarchie (mapping exception → code/statut) + tests d'API de non-régression sur un échantillon par router ; lint/format/typecheck verts sur les fichiers modifiés (mypy `no issues found`, black/flake8 OK — la suite backend complète comporte des échecs **pré-existants** documentés, 0 régression).

## Références spécification

- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Gestion des erreurs → Classes d'erreur (`APIError`, `NotFoundError`, `PermissionDeniedError`, `ConflictError`), § Codes HTTP utilisés ;
- `.roo/rules/30-code-standards.md` — § Gestion d'erreurs backend : exceptions personnalisées héritant de `WindFlowException`, codes HTTP appropriés, logs structurés avec contexte ;
- `.roo/rules/55-project-structure.md` — « Toujours lever des exceptions de `core/exceptions.py`, jamais des exceptions Python brutes dans les endpoints » ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §10 (2 exceptions seulement, HTTPException brutes), §14 ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-5 (partie exceptions), §2.A A11.

## Dépendances

- **Pré-requise : STORY-126** — **satisfaite** : STORY-126.1 (socle schémas/handler/middleware), STORY-126.2 (activation par défaut, tests de contrat), STORY-126.3 (clients frontend/CLI synchronisés, retrait du flag) sont toutes **DONE** (vérifié dans l'epic et le code : [`schemas/common.py`](../../backend/app/schemas/common.py) docstring « il n'existe plus de mode legacy », handler [`main.py:555`](../../backend/app/main.py:555) inconditionnel). Le séquencement arrêté en 126.1 (**126 → 127**) est respecté ; cette story branche la hiérarchie typée sur le handler existant.
- **Aucune autre dépendance technique** — la story est prête à être traitée immédiatement (statut TODO conservé, conformément au pipeline : seul `treat-story` passera la story en `IN_PROGRESS`).
- Facilite (sans bloquer) : les refus RBAC futurs lèveront `PermissionDeniedError` plutôt que `HTTPException` (pattern posé ici pour STORY-122 déjà DONE) ; les échecs d'audit (STORY-125, DONE) continuent d'être loggés avec `correlation_id` — les enveloppes typées transportent le même contexte.
- **Services externes** : aucun (pas de nouvelle dépendance, pas de migration DB, pas de Redis) — purement code Python + tests.

## Sous-stories

*(section réservée — ampleur M confirmée par l'analyse, découpe non prévue)*

> **Note analyse-story (2026-09-30)** : la story reste traitable en une passe grâce au caractère mécanique du sweep (convention unique, zéro changement de comportement). Point de vigilance : `docker.py` concentre ~130 raises — si `treat-story` constate des échecs répétés ou un scope trop volumineux, une sous-découpe `127.1` (socle hiérarchie + handler + auth) / `127.2` (sweep routers) / `127.3` (sweep docker.py) est envisageable — décision relevant de `split-story`, pas de cette analyse.

## État d'avancement technique

- [x] Tâche 1 : Hiérarchie `APIError` + classes typées dans `core/exceptions.py`
- [x] Tâche 2 : Handler global `WindFlowException` dans `main.py`
- [x] Tâche 3 : Sweep auth/rbac/rate_limit (exceptions d'authentification)
- [x] Tâche 4 : Sweep routers cœur (stacks, organizations, users, deployments, schedules, admin/stacks_management)
- [x] Tâche 5 : Sweep routers périphériques (targets/*, discovery, stats, import_export, plugin_registry, compute)
- [x] Tâche 6 : Sweep plugins.py (traduction `error_type`) + adoption_service (service levant du HTTP)
- [x] Tâche 7 : Sweep docker.py (~130 raises, patterns répétitifs)
- [x] Tâche 8 : Tests (mapping hiérarchie, handler, non-régression par router, sécurité)
- [x] Tâche 9 : Validation finale (grep AC 2 + lint + typecheck + suite backend complète)

## Tâches d'implémentation détaillées

> Convention sweep (s'applique à toutes les tâches 3-7) : remplacer chaque `raise HTTPException(status_code=S, detail=D)` par l'exception typée correspondante (table tâche 1) — **même statut, même message**, sans toucher à la logique métier ; retirer les imports `HTTPException`/`status` devenus inutiles ; préserver les headers (`WWW-Authenticate`) ; les `except ... raise ... from exc` conservent leur chaînage. Objectif par fichier : zéro `HTTPException` importé, zéro changement de comportement HTTP.

### Tâche 1 — Hiérarchie dans `backend/app/core/exceptions.py`

1. Ajouter sur `WindFlowException` les attributs de classe : `status_code: int = 500`, `error_code: str = "INTERNAL_ERROR"`, `headers: ClassVar[dict[str, str] | None] = None` — constructeur inchangé (rétrocompatibilité des ~43 raises services existants, grep vérifié).
2. Créer `class APIError(WindFlowException)` : constructeur `(message: str = "", *, details: dict | None = None, code: str | None = None, headers: dict[str, str] | None = None)` — stocke `self.http_headers`, `self.code = code or type(self).error_code`.
3. Ajouter les classes avec leur couple (statut, code) : `ConflictError` (409, `CONFLICT`), `InvalidInputError` (400, `INVALID_INPUT`), `UnprocessableEntityError` (422, `VALIDATION_ERROR`), `PermissionDeniedError` (403, `PERMISSION_DENIED`), `AuthenticationError` (401, `INVALID_OR_EXPIRED_TOKEN`, headers défaut `{"WWW-Authenticate": "Bearer"}`), `RateLimitError` (429, `TOO_MANY_ATTEMPTS`), `ServiceUnavailableError` (503, `SERVICE_UNAVAILABLE`).
4. Ré-ancrer `NotFoundError` sur `APIError` (status 404 / `NOT_FOUND`) **sans changer sa signature** `(resource: str, resource_id: str)` ni son message `f"{resource} not found: {resource_id}"` (2 consommateurs : [`api_key_service.py:237`](../../backend/app/services/api_key_service.py:237), [`auth.py:1281`](../../backend/app/api/v1/auth.py:1281)).
5. Docstrings complètes (message type hints, sémantique HTTP, anti-énumération le cas échéant) + module `__all__`.

### Tâche 2 — Handler global dans `backend/app/main.py`

1. `@app.exception_handler(WindFlowException)` : `build_error_payload(exc.status_code, message=exc.message, details=exc.details or None, path=request.url.path, correlation_id=..., code=getattr(exc, "code", None))` + `JSONResponse(status_code=exc.status_code, headers=getattr(exc, "http_headers", None))` — réutilise [`build_error_payload`](../../backend/app/middleware/api_response.py:73) (helpers STORY-126.1) ; log `logger.warning/error` avec `extra={"correlation_id": ...}` **sans données sensibles**.
2. Cas 401 : laisser `path.endswith("/auth/login")` produire `INVALID_CREDENTIALS` via `_status_to_code` **sauf** si l'exception porte un `code` explicite (login lèvera `AuthenticationError(code="INVALID_CREDENTIALS")` — l'override `code` prime). Vérifier la cohérence : le handler HTTP existant donne `INVALID_CREDENTIALS` sur 401 login ; le handler typé doit aboutir au même résultat.
3. Cas `CommandExecutionError` non interceptée : statut 500 / `INTERNAL_ERROR`, `details` réduit à `{"command", "exit_status"}` — **exclure `stderr`** du payload HTTP (divulgation de sortie brute — check sécurité rules 40) ; log complet côté serveur.
4. Ne pas modifier les 3 handlers existants (`StarletteHTTPException`, `RequestValidationError`, `ValidationError`) ni les middlewares — vérifier (test) qu'une `WindFlowException` sort bien par le NOUVEAU handler et non par le catch générique du middleware externe.
5. Mettre à jour le docstring module de `exceptions.py` et [`middleware/README.md`](../../backend/app/middleware/README.md) (rôle du handler `WindFlowException` dans la chaîne de gestion d'erreurs, position vis-à-vis de l'ExceptionMiddleware).

### Tâche 3 — Sweep authentification (`backend/app/auth/dependencies.py`, `backend/app/auth/rbac.py`, `backend/app/core/rate_limit.py`)

1. `dependencies.py` : 401 credentials → `AuthenticationError("Could not validate credentials")` (headers `WWW-Authenticate` transportés par défaut de classe) ; 403 inactive/superuser → `PermissionDeniedError` ; 500 dev-mode → laisser `HTTPException` (erreur interne de configuration) ou `WindFlowException` nue → 500 enveloppé — arbitrage : lever `WindFlowException(...)` (500 par défaut).
2. `rbac.py:98` : 403 → `PermissionDeniedError("...")` (le refus RBAC typé attendu par STORY-122).
3. `rate_limit.py:187` : 429 → `RateLimitError` (vérifier les headers `Retry-After` éventuels — si présents, les passer via `headers`).
4. `auth.py` (router, ~11 raises, [`auth.py:247`](../../backend/app/api/v1/auth.py:247)) : 401 login → `AuthenticationError("...", code="INVALID_CREDENTIALS")` ; 429 → `RateLimitError` ; 403 inactive → `PermissionDeniedError` ; 409 conflits email/username/org → `ConflictError` ; 404 target_org → `NotFoundError("Organization", ...)` ; les `except InvalidRefreshTokenError/InvalidApiKeyError → HTTPException 401` deviennent `→ raise AuthenticationError(...) from exc` (401 générique anti-énumération **inchangé**).

### Tâche 4 — Sweep routers cœur (`stacks.py`, `organizations.py`, `users.py`, `deployments.py`, `schedules.py`, `admin/stacks_management.py`)

1. 404 → `NotFoundError("<Type>", "<id>")` ; 403 → `PermissionDeniedError` (messages FR actuels conservés tels quels, ex. « Accès refusé à cette stack ») ; 409 → `ConflictError` ; 400 → `InvalidInputError` ; 503 → `ServiceUnavailableError` ; 500 → `WindFlowException(...)` nue (enveloppe `INTERNAL_ERROR`).
2. `deployments.py:778` : `HTTPException(404, detail=str(e))` → `NotFoundError("Deployment", e str)` à message identique.
3. `organizations.py:1468` : `except ValueError → 409` → `ConflictError(str(exc))` (message identique).
4. Vérifier à chaque fichier : plus aucun import `HTTPException` résiduel (flake8 F401 en alerte).

### Tâche 5 — Sweep routers périphériques (`targets/crud.py`, `targets/capabilities.py`, `targets/scanning.py`, `discovery.py`, `stats.py`, `import_export.py`, `plugin_registry.py`, `compute.py`)

1. Même convention que tâche 4 (404/403/400/409 dominants ; 403 → `PermissionDeniedError("Accès refusé à cette cible")` etc.).
2. `plugin_registry.py:135` : 422 pattern name → `UnprocessableEntityError` ; `import_export.py` : 400 JSON invalide → `InvalidInputError` ; 500 → `WindFlowException` nue.
3. `compute.py` : 403 → `PermissionDeniedError` ; `stats.py` : 403 → `PermissionDeniedError`.

### Tâche 6 — Sweep `plugins.py` + `adoption_service.py`

1. [`plugins.py:239`](../../backend/app/api/v1/plugins.py:239) : remplacer chaque branche `raise HTTPException` du switch `error_type` par l'exception typée équivalente — `duplicate`/`dependency_unsatisfied` → `ConflictError(exc.message)` ; `validation`/`yaml_syntax`/`value` → `InvalidInputError(exc.message)` ; `not_found` → `NotFoundError("Plugin", plugin_id)` ; défaut 500 → `WindFlowException(exc.message) from exc` — **conserver le `from exc`**.
2. `adoption_service.py` : anti-pattern service→HTTP ; lever `ServiceUnavailableError` (503 ping), `NotFoundError` (404), `ConflictError` (409 déjà-installé) — le service devient framework-agnostic ; endpoints appelants inchangés (le handler global fait la traduction).
3. Vérifier les tests [`test_plugin_hooks.py`](../../backend/tests/unit/test_api/test_plugin_hooks.py)/[`test_plugins.py`](../../backend/tests/unit/test_api/test_plugins.py) non modifiés (codes attendus inchangés).

### Tâche 7 — Sweep `docker.py` (~130 raises, [`docker.py:184`](../../backend/app/api/v1/docker.py:184))

1. Patterns répétitifs à traiter en série : `except DockerException as e` avec `e.status == 404` → `NotFoundError("Container", id)` / `("Image", id)` / `("Volume", id)` ; `e.status == 409` → `ConflictError` ; 503 ping/ConnectionError → `ServiceUnavailableError` ; 500 génériques → `WindFlowException(str(e))` nue à message identique ; 400 promote/load → `InvalidInputError`.
2. Les messages d'erreur Docker (`detail=str(e)`) sont conservés à l'identique (non-régression stricte) — **ne pas** les enrichir ni les tronquer dans ce sweep.
3. `docker.py:1250` : 409 container managed → `ConflictError` ; `docker.py:1350-1360` : 400/409 promote → typés.
4. Vérification attendue : tests docker existants ([`test_docker/`](../../backend/tests/unit/test_docker/)) **inchangés et verts** (ils mockent le DockerClient et assertent les statuts).

### Tâche 8 — Tests (fichiers listés en « Tests à écrire »)

1. Créer [`backend/tests/unit/test_core/test_exceptions.py`](../../backend/tests/unit/test_core/test_exceptions.py) : mapping complet exception → (statut, code) — cf. détail en section Tests.
2. Étendre/ créer `backend/tests/integration/test_api_envelope_typing.py` : cas réels par statut + anti-régression handler (une `WindFlowException` levée → enveloppe unique, pas de 500 générique) + 401 `WWW-Authenticate` préservé + 401 login `INVALID_CREDENTIALS` via exception typée.
3. Vérifier la non-régression : suite backend complète (patterns 126.1 : stash/unstash si besoin de baseline) — **zéro test existant modifié**.

### Tâche 9 — Validation finale

1. Grep AC 2 : `grep -rn "raise HTTPException" backend/app/api/v1/ backend/app/auth/ backend/app/core/rate_limit.py backend/app/services/` → **0 résultat hors exclusions documentées** (`websocket/**`).
2. `make backend-lint` + `make backend-typecheck` + `make backend-test` (via `.venv-test` — piège documenté 126.1 décision 10) ; couverture sur `core/exceptions.py` ≥ 80 %.
3. Clôture selon protocole : notes d'implémentation, statut REVIEW, kanban.

## Tests à écrire

> Patterns : fixtures `_jwt_mode` autouse + `_bearer` de [`test_api_envelope.py`](../../backend/tests/integration/test_api_envelope.py:37) ; client httpx `ASGITransport` ; couverture ≥ 80 % sur `core/exceptions.py`.

**Unitaires — `backend/tests/unit/test_core/test_exceptions.py` (nouveaux)** :
- Mapping exception → (statut, code) : chaque classe (404/409/400/422/403/401/429/503/500 défaut) ; `WindFlowException` nue → 500 `INTERNAL_ERROR` ;
- `NotFoundError("Stack", id)` → 404, `NOT_FOUND`, message `Stack not found: {id}`, `details` `{resource, resource_id}` ;
- `AuthenticationError` → headers `WWW-Authenticate: Bearer` ; override `code="INVALID_CREDENTIALS"` par instance ;
- Rétrocompatibilité : `CommandExecutionError`/`InvalidApiKeyError`/`InvalidRefreshTokenError`/`Secret*Error` — attributs et signatures inchangés (raise/catch sans régression) ;
- `APIError` constructeur : `details=None` → `{}` ; `code` override prime sur `error_code` de classe.

**Intégration — `backend/tests/integration/test_api_envelope_typing.py` (nouveaux)** :
- `test_windflow_exception_produces_envelope` : une exception typée non interceptée → enveloppe `{error:{code,message}}`, **pas** le 500 générique du middleware — preuve du routage handler vs middleware ;
- `test_401_www_authenticate_header_preserved` : 401 typée → header `WWW-Authenticate: Bearer` présent (non-régression) ;
- `test_401_login_invalid_credentials_typed` : mauvais mot de passe → 401 `INVALID_CREDENTIALS` (via `AuthenticationError` typée) ;
- `test_409_conflict_typed` : slug dupliqué → 409 `CONFLICT` (référence AC 3) ;
- `test_404_not_found_typed` : ressource inconnue → 404 `NOT_FOUND` avec `details` resource/resource_id ;
- `test_403_permission_denied_typed` : viewer sur action admin → 403 `PERMISSION_DENIED` ;
- `test_429_rate_limit_typed` : rate limit → 429 `TOO_MANY_ATTEMPTS` (adapter si `Retry-After`) ;
- `test_command_execution_error_500_no_stderr` : `CommandExecutionError` non interceptée → 500 `INTERNAL_ERROR`, `details` **sans `stderr`** (sécurité) ;
- `test_correlation_id_in_error_envelope` : toute erreur → `correlation_id` top-level présent.

**Sécurité (checklist rules 40 — obligatoire)** :
- `test_error_response_no_stack_trace` : corps 500 → ni traceback, ni nom de module interne, ni `str(exc)` brute (message générique uniquement) ;
- `test_401_anti_enumeration` : clé API inconnue/révoquée/expirée + refresh token invalide → **même** message 401 (pas de distinction) ;
- `test_no_secrets_in_error_details` : `CommandExecutionError.stderr` absent du payload HTTP ; `Secret*Error` sans matériel cryptographique ;
- `test_error_details_no_sensitive_fields` : `details` ne transporte jamais password/token/key (revue des `details` construits par le sweep).

**Non-régression (obligatoire, sans modification des tests existants)** :
- Suite backend complète inchangée avant/après sweep (statuts et messages préservés) — cf. méthodologie stash/unstash STORY-126.1 validation ;
- Échantillon par router déjà couvert par [`test_api_contract.py`](../../backend/tests/integration/test_api_contract.py) et les `test_*_rbac.py` — ils doivent rester verts sans édition.

**Clients (aucune modification attendue — vérification seulement)** :
- [`cli/tests/test_client_envelope.py`](../../cli/tests/test_client_envelope.py) et [`frontend/tests/unit/services/http.spec.ts`](../../frontend/tests/unit/services/http.spec.ts) restent verts sans changement : preuve que le format d'erreur consommé (`error.code`/`error.message`) est inchangé.

## Notes d'implémentation

> Traitée le 2026-10-01 par `treat-story` (venv de test `.venv-test`).

### Fichiers modifiés/créés

**Socle (tâches 1-2)** :
- `backend/app/core/exceptions.py` — hiérarchie complétée : attributs de classe (`status_code`/`error_code`/`headers`) sur `WindFlowException`, `APIError` intermédiaire, 7 classes typées (409/400/422/403/401/429/503), `NotFoundError` ré-ancrée sur `APIError`, `__all__`, docstring module.
- `backend/app/middleware/error_handler.py` — **handler global `windflow_exception_handler` extrait ici** (fonction réutilisable ; `main.py` l'enregistre via `add_exception_handler`). Cas `CommandExecutionError` : message générique `"Command execution failed"` + `details` réduits à `{command, exit_status}` (stderr exclu du HTTP, loggé serveur — durcissement sécurité réel).
- `backend/app/main.py` — enregistrement du handler + import `WindFlowException`.
- `backend/app/middleware/__init__.py` — export `windflow_exception_handler`.
- `backend/app/middleware/README.md` — section « Exception handlers (STORY-127) » (position ExceptionMiddleware interne vs middlewares http).

**Sweep (tâches 3-7, ~250 raises convertis via script AST dédié)** :
- `backend/app/auth/dependencies.py`, `backend/app/auth/rbac.py`, `backend/app/core/rate_limit.py`, `backend/app/api/v1/auth.py` (tâche 3, manuel) ;
- `stacks.py` (33), `organizations.py` (25), `users.py` (21), `deployments.py` (22), `schedules.py` (4), `admin/stacks_management.py` (13) (tâche 4) ;
- `targets/{crud,capabilities,scanning}.py` (24), `discovery.py` (4), `stats.py` (1), `import_export.py` (6), `plugin_registry.py` (2), `compute.py` (2), `plugins.py` (20) (tâches 5-6) ;
- `backend/app/services/adoption_service.py` (7 — **service devenu framework-agnostic**, l'anti-pattern service→HTTP est éliminé) ;
- `docker.py` (88) (tâche 7). `except HTTPException:` internes → `except WindFlowException:` (stacks.py, docker.py, adoption_service.py). Imports `HTTPException`/`status` inutiles retirés partout (flake8 F401 propre).

**Outils de sweep (réutilisables)** : `dev/scripts/sweep_127.py` (transformation AST `HTTPException` → classe typée, même statut/message/headers, validation syntaxique intégrée) et `dev/scripts/add_handler_127.py` (enregistrement du handler sur les apps de test minimales).

**Tests (tâche 8)** :
- `backend/tests/unit/test_core/test_exceptions.py` (**nouveau**, 23 tests : mapping complet, NotFoundError 2 formes, AuthenticationError headers/override, rétrocompatibilité classes techniques, chaînage `from`) ;
- `backend/tests/integration/test_api_envelope_typing.py` (**nouveau**, 13 tests : preuve routage handler vs middleware, WWW-Authenticate préservé, INVALID_CREDENTIALS login, 409/404/403/429 typés, CommandExecutionError sans stderr, correlation_id, sécurité rules 40 — pas de stack trace, anti-énumération, pas de champs sensibles).

**Tests existants adaptés (divergences — voir ci-dessous)** : `test_rate_limit.py` (unit, 5 asserts), `test_rate_limiting.py` (intégration, 4 asserts), `test_dev_mode.py` (2 asserts), `test_adoption_service.py` (4 asserts + imports) — types `HTTPException` → classes typées, vérifications fonctionnelles identiques. Tests docker : enregistrement du handler sur les apps minimales (16 fichiers, via script) + 14 assertions `["detail"]` → `["error"]["message"]` (contrat spec-09 courant).

### Décisions techniques

1. **Handler déplacé de `main.py` vers `middleware/error_handler.py`** (vs tâche 2.1 qui le plaçait inline dans `main.py`) : les ~16 fichiers de tests docker montent des apps FastAPI minimales sans `app.main` — le handler partagé y est enregistré, sinon les exceptions typées sortent brutes (échec de handshake httpx). Comportement de l'app réelle strictement identique.
2. **`NotFoundError` à double signature** : `(resource, resource_id)` historique (2 consommateurs services, message `"{resource} not found: {id}"` + `details`) **et** forme message-libre `NotFoundError(message)` pour le sweep — la convention « même message au caractère près » est incompatible avec la seule signature historique (les messages 404 existants sont hétérogènes : FR, formats variés). Les deux formes sont documentées et testées.
3. **`CommandExecutionError` : message HTTP écrasé** (`"Command execution failed"`) dans le handler — le message de la classe embarquant `stderr`, l'exclure des seuls `details` laissait une fuite par `error.message` (test `test_command_execution_error_500_no_stderr`). Log serveur complet conservé.
4. Sweep par **script AST déterministe** (`dev/scripts/sweep_127.py`) plutôt que manuel : ~250 raises, risque d'erreur humaine trop élevé. Le script préserve exactement statut/message/headers (via `ast.unparse` des expressions), valider la syntaxe après transformation, et gère les imports (retrait `HTTPException`/`status` inutiles, insertion/fusion `core.exceptions`).

### Divergences par rapport à l'analyse

1. **Tests existants assertant le type `HTTPException`** (5 fichiers listés ci-dessus) : ces tests contredisaient directement l'AC 2/les tâches 3-7 (elles imposent les classes typées là où les tests vérifiaient `pytest.raises(HTTPException)` + `.detail`/`.headers`). Cas prévu par le protocole (« si le test contredit l'AC, documenter ») : assertions adaptées aux types nouveaux **sans changer les vérifications fonctionnelles** (statuts, messages, `Retry-After`). Idem pour les 14 asserts docker `["detail"]` (format pré-STORY-126) → `["error"]["message"]`.
2. **Volume réel du sweep ~250 raises** (vs ~291 estimés) : l'estimation de l'analyse comptait aussi les fichiers exclus (`websocket/**`, 6) et les re-comptages.
3. **Handler dans `error_handler.py`** plutôt qu'inline `main.py` (décision 1 ci-dessus).

### Échecs pré-existants (non causés par cette story, baseline HEAD vérifiée par stash/unstash)

`test_auth_isolation` (2), `test_users` (3), `test_debug_story1033` (1), `test_deployments_api` (9), `test_security_headers` (9), `test_auth_api` (3), `test_stack_actions`/`test_stacks_archive`/`test_stacks_duplicate` (29) — dette antérieure (tests lisant `["detail"]` pré-126, fixtures DB). **0 régression** : chaque lot a été comparé avant/après (run différentielle), aucun échec nouveau.

### Commandes de validation exécutées (.venv-test)

- `pytest backend/tests/unit/test_core/test_exceptions.py backend/tests/integration/test_api_envelope_typing.py` → **36/36 passés** ;
- `pytest backend/tests/unit/test_docker/ backend/tests/unit/test_api/test_docker_rbac.py` → **380/380 passés** ;
- `pytest backend/tests/unit/test_core/ backend/tests/unit/test_docker/ backend/tests/integration/test_api_envelope.py backend/tests/integration/test_api_envelope_typing.py backend/tests/integration/test_api_contract.py` → **516/516 passés** ;
- `pytest backend/tests/unit backend/tests/integration` (suite complète) → 1713 passés / 59 échecs **tous pré-existants** (différentielle baseline = 0 régression) ;
- `pytest cli/tests/test_client_envelope.py` → 10/10 (clients inchangés) ;
- grep AC 2 : `grep -rn "raise HTTPException" backend/app/{api/v1,auth,core/rate_limit.py,services} --include="*.py" | grep -v websocket` → **0 résultat** ;
- `black --check` + `isort` + `flake8 --select=E9,F63,F7,F82,F401` sur les fichiers modifiés → OK ; `mypy backend/app/core/exceptions.py backend/app/middleware/error_handler.py` → *Success: no issues found* ;
- couverture `core/exceptions.py` : couverte à 100 % des lignes par `test_exceptions.py` + handler (cible ≥ 80 % atteinte).

### Difficultés rencontrées

- Baseline complète sous stash : runs complets interrompus par timeout (un test bloque en état stashed) → différentielles par subsets (équivalentes, plus granulaires).
- ~16 apps de test docker minimales à équiper du handler (script dédié) — point non anticipé par l'analyse (hypothèse « apps minimales = comportement natif » inexacte).
- Imports relatifs à profondeur variable (`api/v1/admin`, `api/v1/targets`, `services`) à corriger après génération script.
