# STORY-126 : [ABANDONED] Enveloppes de réponse API — `APIResponse{data,message}` / `PaginatedResponse{data,pagination}` / erreur `{error:{code,message}}` (P1-5)

**Statut :** ABANDONED *(découpe proactive `split-story` — remplacée par STORY-126.1/126.2/126.3, voir « Sous-stories »)*
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-5 (axe A10, rapport §1) — ampleur **L** — ⚠️ **breaking change consommateur**

## Description

En tant que développeur d'intégrations WindFlow (frontend Vue, CLI, scripts), je veux que **tous** les endpoints API répondent dans des enveloppes standard (`{data, message}` en réponse simple, `{data, pagination}` en liste, `{error:{code, message}}` en erreur), afin d'avoir un contrat de réponse homogène, documenté OpenAPI et stable — base indispensable avant d'élargir la surface API (vague P2).

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §1, §14) : les routers renvoient des objets/listes nus, sans enveloppe ; seuls les handlers d'exception Pydantic/FastAPI ([`main.py:380`](../../backend/app/main.py:380)) produisent un format d'erreur partiel (422 + correlation_id). La spec 09 définit précisément les trois enveloppes et les modèles Pydantic associés (`APIResponse`, `PaginatedResponse`, `ErrorResponse`…).

⚠️ **Breaking change** : frontend et CLI consomment le format actuel — la synchronisation des clients doit se faire **dans le même lot** (plan §7.1), avec versionnement documenté dans le changelog.

## Contexte technique

> Analyse réalisée par `analyse-story` (2026-09-27) — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches. Découpe validée par l'utilisateur le 2026-09-27 : **3 sous-stories avec flag de bascule** (chaque sous-story reste verte indépendamment).

### Inventaire de l'existant (vérifié dans le code)

**Surface impactée** — 139 endpoints REST sur 16 routers (+ sous-packages), montés dans [`backend/app/api/v1/__init__.py`](../../backend/app/api/v1/__init__.py:28) :

| Router | Fichier | Endpoints | Particularités |
|---|---|---|---|
| auth | [`auth.py`](../../backend/app/api/v1/auth.py) | 9 | `/login` renvoie les **tokens nus** au sommet du body (`access_token`, `refresh_token`, `expires_in`, `user`, …) — cas particulier du CLI |
| users | [`users.py`](../../backend/app/api/v1/users.py) | 8 | inclut `/me` + bulk |
| organizations | [`organizations.py`](../../backend/app/api/v1/organizations.py) | 9 | **409 déjà émis** (nom dupliqué, [`organizations.py:502`](../../backend/app/api/v1/organizations.py:502)) mais au format `detail` string, pas `error.code` |
| targets | [`targets/`](../../backend/app/api/v1/targets) (crud, connectivity, scanning, capabilities) | 13 | 4 sous-modules |
| stacks | [`stacks.py`](../../backend/app/api/v1/stacks.py) | 15 | versions, actions |
| deployments | [`deployments.py`](../../backend/app/api/v1/deployments.py) | 7 | liste paginée `{items,total,skip,limit}` (`DeploymentListResponse`) |
| workflows | [`workflows.py`](../../backend/app/api/v1/workflows.py) | 1 | stub `[]` |
| stats | [`stats.py`](../../backend/app/api/v1/stats.py) | 2 | dashboard |
| import_export | [`import_export.py`](../../backend/app/api/v1/import_export.py) | 2 | export YAML (fichier), import |
| schedules | [`schedules.py`](../../backend/app/api/v1/schedules.py) | 6 | |
| docker | [`docker.py`](../../backend/app/api/v1/docker.py) | 40 | garde-fou §2.G : **aucune suppression d'endpoint** |
| compute | [`compute.py`](../../backend/app/api/v1/compute.py) | 2 | |
| discovery | [`discovery.py`](../../backend/app/api/v1/discovery.py) | 2 | |
| plugins | [`plugins.py`](../../backend/app/api/v1/plugins.py) | 9 | |
| plugin_registry | [`plugin_registry.py`](../../backend/app/api/v1/plugin_registry.py) | 2 | |
| admin | [`admin/`](../../backend/app/api/v1/admin) (audit, stacks_management) | 16 | `GET /admin/audit` livré en `{items,total,skip,limit}` (STORY-125.3) |
| websockets | [`websockets.py`](../../backend/app/api/v1/websockets.py) | 5 canaux | **HORS périmètre** (format `type/data` distinct, spec 09 § WebSocket) |

**Socle Pydantic divergent existant** : [`backend/app/schemas/common.py`](../../backend/app/schemas/common.py) contient `PaginatedResponse{items,total,skip,limit,has_more}`, `ErrorResponse{error:str, detail, correlation_id, timestamp}`, `PaginationParams{skip,limit}`, `HealthResponse` — **divergents** de la spec 09 (`{data,pagination{page,per_page,total,pages}}` / `{error{code,message,details?}}`) et **0 consommateur backend** (grep vérifié) → réécriture libre, sans migration de consommateurs.

**Trois producteurs d'erreurs à unifier :**
1. Handlers `RequestValidationError`/`ValidationError` dans [`main.py:478-514`](../../backend/app/main.py:478) → 422 `{error:"Validation Error", detail:[...], correlation_id}` ;
2. Middleware [`error_handler_middleware`](../../backend/app/middleware/error_handler.py:17) → 500 `{error:"...", detail, path}` (et 422 dupliqué) ;
3. `HTTPException` brutes dans les routers (~150+ occurrences `detail=...`) — sweep confié à **STORY-127** (hiérarchie d'exceptions), cette story ne fait que **brancher le handler**.

**Clients (breaking change) :**
- Frontend : interceptor axios [`frontend/src/services/http.ts:47`](../../frontend/src/services/http.ts:47) lit `data.detail` sur 403/404/500 ; stores lisent `response.data.items` ([`deployments.ts:27`](../../frontend/src/stores/deployments.ts:27), [`useUsers.ts:66`](../../frontend/src/composables/useUsers.ts:66)) avec fallbacks défensifs `items || data` ([`stacks.ts:25`](../../frontend/src/stores/stacks.ts:25), [`targets.ts:24`](../../frontend/src/stores/targets.ts:24), [`workflows.ts:19`](../../frontend/src/stores/workflows.ts:19), [`useOrganizations.ts:63`](../../frontend/src/composables/useOrganizations.ts:63)) ; vues lisent `err.response.data.detail` ([`Stacks.vue:1022`](../../frontend/src/views/Stacks.vue:1022), …) ; [`stores/auth.ts`](../../frontend/src/stores/auth.ts:36) lit `response.data.access_token` ; type [`PaginatedResponse<T>`](../../frontend/src/types/api.ts:374) et [`ApiError{detail}`](../../frontend/src/types/api.ts:416) à réaligner.
- CLI : [`cli/client.py:59`](../../cli/client.py:59) lit `error_data.get("detail")` ; [`client.py:104-116`](../../cli/client.py:104) lit `result["access_token"]` au sommet du body après login.

**Garde-fous à préserver (plan §2.G + AC 5) :** `/health` et `/` hors `/api/v1` (format libre inchangé) ; middlewares sécurité/CORS/timing/correlation intacts ; aucune suppression d'endpoint Docker ; WebSocket hors périmètre ; `X-Correlation-ID` continue d'être exposé (header) et inclus dans les 422.

**Charge de tests** : ~1552 tests backend dont une grande part assert le format actuel (`response.json()["items"]`, `["detail"]`, `["total"]`…) — l'activation de l'enveloppe casse mécaniquement ces assertions ; les tests frontend/CLI consomment aussi l'ancien format.

### Décisions d'analyse (arbitrages)

1. **Découpe en 3 sous-stories avec flag de bascule** `api_envelope_enabled: bool = Field(default=False)` dans [`config.py`](../../backend/app/config.py) (+ `API_ENVELOPE_ENABLED` dans [`env.example`](../../env.example)) — validée par l'utilisateur le 2026-09-27 :
   - **STORY-126.1** pose le socle **inactif** (schémas, middleware d'enveloppe, handlers d'erreur, 409, OpenAPI, tests du socle en mode activé ponctuel) — merge non breaking, suite backend **verte sans modification** (flag off par défaut) ;
   - **STORY-126.2** flippet le défaut à `True` et adapte la suite de tests backend + ajoute les **tests de contrat par router** (AC 1) — c'est le point de bascule du contrat serveur ;
   - **STORY-126.3** synchronise frontend + CLI (unwrap `data` centralisé, `.error.message`, tokens sous `data`) + CHANGELOG versionné — ferme le breaking change.
   - Le flag est **transitoire** : retiré après 126.3 (documenté dans la sous-story 126.3, note « à retirer lors du nettoyage P3 » — la retraite du flag elle-même est suivie dans la story 126.3 avec test de non-régression ; si le retrait total est différé, le consigner à STORY-250).
2. **Middleware HTTP d'enveloppe plutôt que `response_model` partout** : envelopper la réponse **sortante** dans un middleware dédié (`api_response_middleware`, ordre après error_handler — cf. [`middleware/README.md`](../../backend/app/middleware/README.md)) plutôt que modifier les 139 signatures `response_model=`. Rationale : (a) zéro toucher aux corps de handlers (garde-fou module Docker) ; (b) les `response_model` existants restent la **validation** de sortie, l'enveloppe est un habillage ; (c) le JSON est déjà sérialisé au niveau middleware (StreamingResponse) — ré-encapsuler `response.json()` quand `content-type: application/json` et chemin sous `/api/v1` et flag actif et statut < 400. Coût : double sérialisation négligeable ; exclusion explicite des réponses non-JSON (fichiers export YAML, `RedirectResponse`) et des 204 (body vide → pas d'enveloppe ; spec 09 : 204 = supprimé).
3. **Succès enveloppe** : statuts 2xx JSON → `{"data": <corps actuel>, "message": null}` par défaut ; `message` renseignable via header interne `X-API-Message` posé par le handler (simple, opt-in) — la spec montre `message` optionnel ; les enveloppes de **liste** sont la responsabilité de STORY-128 (pagination `{page,per_page,total,pages}`) : en attendant, les listes existantes (y compris `{items,total,...}`) passent telles quelles sous `data` — pas de reformatage `pagination{}` dans cette story (dépendance : STORY-128 **bloquée par** 126, pas l'inverse).
4. **Erreurs enveloppe** : un `@app.exception_handler` dédié capture `HTTPException` (et via 127, `WindFlowException`) → status quo du code HTTP + corps `{"error": {"code": <CODE>, "message": <detail str>, "details": <dict|erreur Pydantic list>}}` + `correlation_id` **préservé** (top-level, champ existant des 422 actuels — AC 2). Mapping code spec 09 : 400→`INVALID_INPUT`, 401→`INVALID_OR_EXPIRED_TOKEN` (sauf login → `INVALID_CREDENTIALS`), 403→`PERMISSION_DENIED`, 404→`NOT_FOUND`, 409→`CONFLICT`, 422→`VALIDATION_ERROR`, 429→`TOO_MANY_ATTEMPTS`, 500→`INTERNAL_ERROR`, 503→`SERVICE_UNAVAILABLE`. Le middleware `error_handler_middleware` (500/SQLAlchemy) voit son format aligné sur la même enveloppe. Les handlers 422 de [`main.py`](../../backend/app/main.py:478) deviennent enveloppe : `{"error":{"code":"VALIDATION_ERROR","message":"Validation Error","details":[<erreurs pydantic>]},"correlation_id":...}` — le `detail` liste Pydantic passe dans `error.details` (AC 2 : « garde le format d'erreur enveloppe + correlation_id préservé »).
5. **409 CONFLICT** : le code HTTP 409 existe déjà (organizations) — le handler enveloppe fait que ces réponses portent automatiquement `error.code="CONFLICT"` sans toucher les raise. **Aucun changement de statut** n'est introduit par cette story (les 400 actuels restent 400 ; la convergence métier 400→409 est dans STORY-127 avec `ConflictError`). Test de référence AC 2 : POST `/organizations` avec nom dupliqué → 409 + `error.code == "CONFLICT"`.
6. **OpenAPI** : les schémas `APIResponse`/`PaginatedResponse`/`ErrorResponse`/`ErrorDetail`/`PaginationMeta` (Pydantic V2, `ConfigDict` + `json_schema_extra` exemples, pattern [`schemas/api_key.py`](../../backend/app/schemas/api_key.py)) sont enregistrés dans `components.schemas` via au moins un `response_model` de démonstration + exemples globaux ; les `responses={...}` exemples d'erreur existants (pattern [`deployments.py:54`](../../backend/app/api/v1/deployments.py:54)) sont mis au format enveloppe progressivement (échantillon : auth, deployments, organizations, docker) — documentation exhaustive de chaque endpoint reportée au fil de l'eau (l'enveloppe étant appliquée par middleware, l'OpenAPI généré reste exact sur les schémas métier ; l'habillage est documenté globalement dans la description app + schémas d'enveloppe référencés).
7. **Tests de contrat (AC 1)** : un test paramétré par router — un échantillon représentatif (1 liste + 1 détail + 1 création si applicable) sur **chacun des 16 routers REST** — assertant `data` présent, `message` présent (nullable), erreurs `error.code`. Fichier : `backend/tests/integration/test_api_contract.py` (client httpx `ASGITransport`, pattern [`test_openapi.py`](../../backend/tests/integration/test_openapi.py)).
8. **Pièges environnement** (documentés par 122-125, toujours valables) : venv **`.venv-test`** (Python 3.11) — le venv Poetry racine est cassé ; `DISABLE_AUTH=false LOG_LEVEL=WARNING` pour les tests d'API ; fixtures rôles conftest (`viewer_user`, `operator_user`, `org_admin_user`, `test_superuser`) disponibles ; rate-limit store reset automatiquement entre tests (conftest).

### Réutilisation proposée

- **Directe** : correlation middleware ([`correlation.py`](../../backend/app/middleware/correlation.py)) — `request.state.correlation_id` repris tel quel dans les erreurs ; patterns `ConfigDict`/exemples des schemas existants ; fixtures conftest.
- **Adaptation** : [`schemas/common.py`](../../backend/app/schemas/common.py) réécrit (enveloppes spec 09) — 0 consommateur à migrer ; [`middleware/error_handler.py`](../../backend/app/middleware/error_handler.py) aligné sur l'enveloppe (quand flag actif) ; exemples `responses={}` des routers (échantillon) reformattés.
- **Réécriture** : aucune logique métier — l'enveloppe est strictement un habillage transport.

## Critères d'acceptation (AC)

- [ ] AC 1 : Les enveloppes `APIResponse{data, message}`, `PaginatedResponse{data, pagination{page, per_page, total, pages}}` et `ErrorResponse{error{code, message, details?}}` sont implémentées (schémas Pydantic) et **tous** les endpoints `/api/v1/*` répondent dans ces enveloppes — vérifié par un **test de contrat sur un échantillon représentatif par router** (~16 routers REST).
- [ ] AC 2 : Les erreurs suivent l'enveloppe `{error:{code,message}}` : codes spec 09 (`NOT_FOUND`, `PERMISSION_DENIED`, `CONFLICT`, `INVALID_CREDENTIALS`, `INVALID_OR_EXPIRED_TOKEN`, `TOO_MANY_ATTEMPTS`…) ; un cas de **conflit réel** (nom d'organisation dupliqué) répond **409** `CONFLICT` ; la 422 de validation Pydantic garde le format d'erreur enveloppe (+ correlation_id existant préservé).
- [ ] AC 3 : OpenAPI à jour : schémas d'enveloppes + exemples documentés sur Scalar/Swagger/ReDoc ; tests d'intégration OpenAPI étendus et verts.
- [ ] AC 4 : **Clients synchronisés dans le même lot** : frontend (unwrap `data` dans les services/stores, non-régression des vues clés) et CLI ([`cli/client.py`](../../cli/client.py)) adaptés ; tests frontend et CLI verts ; breaking change **versionné et documenté** dans le CHANGELOG.
- [ ] AC 5 : `make lint` + `make backend-test` + `make frontend-test` verts ; aucune régression des garde-fous §2.G (aucun endpoint supprimé, middlewares sécurité intacts).

## Références spécification

- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Format de réponse (les 3 enveloppes + modèles Pydantic), § Gestion des erreurs (codes HTTP, classes d'erreur), § Documentation OpenAPI ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §1 (réponses nues, handler 422), §14 ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-5 (« à merger tôt »), §2.A A10, §5 chaîne critique n°4, §7.1 (breaking change — synchroniser frontend/CLI), §7.4 arbitrage n°6 ;
- `.roo/rules/20-architecture-and-api.md` — OpenAPI à jour avec un maximum de documentation et d'exemples, tout couvert par Pydantic.

## Dépendances

> Analyse réalisée par `analyse-story` (2026-09-27) — statuts vérifiés dans `.backlog/` et le code.

- **Aucune dépendance technique en amont** — peut démarrer immédiatement (« à merger tôt », plan §4) ;
- **STORY-120/121/122/123/124/125.x** : **DONE ✔** — la base (RBAC, auth, audit) est posée ; STORY-125.3 a livré `/admin/audit` en `{items,total,skip,limit}` : cette story l'enveloppe (`data`), STORY-128 le convertira en `pagination{}` ;
- **Coordonnée avec STORY-127** (hiérarchie d'exceptions) : séquencement arrêté — **126 d'abord** (handler enveloppe branché sur `HTTPException` existantes), **127 ensuite** (remplace les raises par la hiérarchie typée qui transite par le même handler) ; la frontière est nette : 126 = habillage transport, 127 = typage des raises ;
- **Bloque** STORY-128 (format `pagination{}`) et les surfaces P2 (STORY-170 notamment — plan §5 chaîne critique n°4).

## Sous-stories

> **Découpe proactive `split-story` (mode proactif, validée par l'utilisateur le 2026-09-27)** — cette story est **ABANDONNÉE** et remplacée par 3 sous-stories autonomes qui couvrent l'intégralité de son périmètre (analyse, AC et tests ci-dessous répartis sans perte) :
>
> - [ ] STORY-126.1 : Socle enveloppes — schémas spec 09, middleware/handlers d'erreur derrière `api_envelope_enabled=False`, 409, OpenAPI ([`STORY-126.1-socle-enveloppes-schemas-handler.md`](STORY-126.1-socle-enveloppes-schemas-handler.md)) ;
> - [ ] STORY-126.2 : Activation du format enveloppe — défaut `True`, adaptation de la suite backend, tests de contrat par router ([`STORY-126.2-activation-tests-contrat.md`](STORY-126.2-activation-tests-contrat.md)) ;
> - [ ] STORY-126.3 : Synchronisation des clients — frontend unwrap `data`, CLI, CHANGELOG versionné ([`STORY-126.3-clients-frontend-cli.md`](STORY-126.3-clients-frontend-cli.md)).
>
> **Ce fichier est conservé pour historique et comme source d'analyse détaillée** — les sous-stories en sont des extractions adaptées ; en cas d'ambiguïté, le découpage des sous-stories prévaut. Conformément à la règle d'or, aucun fichier de backlog n'est supprimé.

## État d'avancement technique

*(coché par `treat-story` pendant l'implémentation — réparti dans les sous-stories)*

- [ ] Tâche 1 : Schémas enveloppes spec 09 dans `schemas/common.py` (`PaginationMeta`, `APIResponse`, `PaginatedResponse`, `ErrorDetail`, `ErrorResponse`) + exports — *126.1*
- [ ] Tâche 2 : Config `api_envelope_enabled` (défaut `False`) + `env.example` — *126.1*
- [ ] Tâche 3 : Middleware `api_response_middleware` (2xx JSON `/api/v1` → `{data, message}` ; exclusions non-JSON/204) + enregistrement ordonné dans `main.py` — *126.1*
- [ ] Tâche 4 : Handler `HTTPException` → enveloppe `{error:{code,message,details?}}` + `correlation_id` ; alignement des handlers 422 et du middleware `error_handler_middleware` ; mapping codes spec 09 — *126.1*
- [ ] Tâche 5 : Tests socle (flag on ponctuel) : enveloppe 2xx, erreurs par statut, 409 `CONFLICT`, 422 enveloppe + correlation_id, `/health` et `/` intacts, WS non enveloppé — *126.1*
- [ ] Tâche 6 : OpenAPI — schémas d'enveloppe exposés + exemples ; extension `test_openapi.py` ; mise à jour échantillon `responses={}` (auth, deployments, organizations, docker) — *126.1/126.2*
- [ ] Tâche 7 : Bascule défaut `api_envelope_enabled=True` + `env.example`/`env.prod` — *126.2*
- [ ] Tâche 8 : Adaptation suite backend (~assertions `items`/`detail`/`total`) + tests de contrat par router (`test_api_contract.py`) — *126.2*
- [ ] Tâche 9 : Frontend — unwrap centralisé (interceptor), types `ApiError`/`PaginatedResponse`, stores/composables/vues, non-régression vues clés — *126.3*
- [ ] Tâche 10 : CLI — `client.py` (login tokens sous `data`, erreurs `.error.message`) + tests ; CHANGELOG versionné ; retrait/verrouillage du flag transitoire — *126.3*

## Tâches d'implémentation détaillées

> **Réparties dans les sous-stories** (cf. liens ci-dessus) — le détail pas-à-pas (fichiers, ordre, pièges) y est porté. Synthèse de la répartition :
>
> - **STORY-126.1** (tâches 1-6) : socle inactif, merge non breaking — schémas, flag, middleware, handlers d'erreur, tests du socle (activation ponctuelle du flag dans les tests), OpenAPI ;
> - **STORY-126.2** (tâches 7-8) : point de bascule serveur — défaut `True`, adaptation massive des assertions de tests, tests de contrat par router (AC 1), extension OpenAPI restante ;
> - **STORY-126.3** (tâches 9-10) : clients — frontend (interceptor unwrap, types, stores, vues), CLI, CHANGELOG (breaking change documenté + version), retrait du flag transitoire.

## Tests à écrire

> **Répartis dans les sous-stories.** Synthèse :
>
> - **Socle (126.1)** : unitaires schémas (sérialisation enveloppes, `details` optionnel) ; intégration flag-on : GET liste/détail → `data` ; POST 201 → `data` ; DELETE 204 **sans** enveloppe ; 401/403/404/409/422/429/500 → `error.code` mapping + `correlation_id` ; `/health`, `/` et canaux WS non impactés ; réponses non-JSON (export YAML) non enveloppées ;
> - **Contrat (126.2)** : `test_api_contract.py` — échantillon par router (16 routers REST) : présence `data`, `message` nullable, erreurs enveloppées ; non-régression RBAC (401/403 toujours fonctionnels au nouveau format) ; OpenAPI : schémas `APIResponse`/`ErrorResponse` présents dans `components.schemas` ;
> - **Clients (126.3)** : frontend — interceptor unwrap (succès + erreur `.error.message`), store auth (login tokens sous `data`), stores listes (`data.data.items` puis `pagination` en 128), vues clés sans régression ; CLI — login/store tokens, affichage erreur `.error.message`, tests `cli/tests` si présents.
