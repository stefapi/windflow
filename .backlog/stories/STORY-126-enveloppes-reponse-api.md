# STORY-126 : Enveloppes de réponse API — `APIResponse{data,message}` / `PaginatedResponse{data,pagination}` / erreur `{error:{code,message}}` (P1-5)

**Statut :** TODO
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-5 (axe A10, rapport §1) — ampleur **L** — ⚠️ **breaking change consommateur**

## Description

En tant que développeur d'intégrations WindFlow (frontend Vue, CLI, scripts), je veux que **tous** les endpoints API répondent dans des enveloppes standard (`{data, message}` en réponse simple, `{data, pagination}` en liste, `{error:{code, message}}` en erreur), afin d'avoir un contrat de réponse homogène, documenté OpenAPI et stable — base indispensable avant d'élargir la surface API (vague P2).

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §1, §14) : les routers renvoient des objets/listes nus, sans enveloppe ; seuls les handlers d'exception Pydantic/FastAPI ([`main.py:380`](../../backend/app/main.py:380)) produisent un format d'erreur partiel (422 + correlation_id). La spec 09 définit précisément les trois enveloppes et les modèles Pydantic associés (`APIResponse`, `PaginatedResponse`, `ErrorResponse`…).

⚠️ **Breaking change** : frontend et CLI consomment le format actuel — la synchronisation des clients doit se faire **dans le même lot** (plan §7.1), avec versionnement documenté dans le changelog.

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- Modèles Pydantic cibles (spec 09 § Format de réponse) : `PaginationMeta{page, per_page, total, pages}`, `APIResponse{data, message?}`, `PaginatedResponse{data, pagination}`, `ErrorDetail{code, message, details?}`, `ErrorResponse{error}` — à créer dans `schemas/` et à référencer comme `response_model` ;
- Application à **tous** les routers ([`api/v1/`](../../backend/app/api/v1/__init__.py:28), ~17 routers + sous-packages) : le format des erreurs passe par le **handler global** (voir STORY-127 pour la hiérarchie d'exceptions qui l'alimente — la coordination des deux stories est à organiser par l'analyse : handler d'enveloppe ici, migration des `HTTPException` brutes là) ;
- **409 conflits** : les cas de conflit (ex. slug organisation dupliqué, nom déjà pris) doivent répondre `409` avec `error.code = "CONFLICT"` (au lieu du 400/500 actuel) ;
- OpenAPI multi-interfaces (Scalar `/docs`, Swagger `/swagger`, ReDoc `/redoc`) : exemples et schémas mis à jour (garde-fou §2.G) ; les tests d'intégration OpenAPI existants ([`test_openapi.py`](../../backend/tests/integration/test_openapi.py)) à étendre ;
- **Tests de contrat sur un échantillon par router** (critère de done) + tests de non-régression des clients : adapter [`stores/`](../../frontend/src/stores) / services axios (unwrap `data`) et [`cli/client.py`](../../cli/client.py) ;
- Doit être **mergée tôt** pour éviter les conflits (dépend de rien, mais tout le reste de P1/P2 dépend d'elle) ; WebSocket **hors périmètre** (format de messages `type/data` distinct, spec 09 § WebSocket) ;
- Garde-fou : ne pas casser `/health` ni `/` (format libre autorisé hors `/api/v1` si specifié ainsi).

## Critères d'acceptation (AC)

- [ ] AC 1 : Les enveloppes `APIResponse{data, message}`, `PaginatedResponse{data, pagination{page, per_page, total, pages}}` et `ErrorResponse{error{code, message, details?}}` sont implémentées (schémas Pydantic) et **tous** les endpoints `/api/v1/*` répondent dans ces enveloppes — vérifié par un **test de contrat sur un échantillon représentatif par router** (~17 routers).
- [ ] AC 2 : Les erreurs suivent l'enveloppe `{error:{code,message}}` : codes spec 09 (`NOT_FOUND`, `PERMISSION_DENIED`, `CONFLICT`, `INVALID_CREDENTIALS`, `INVALID_OR_EXPIRED_TOKEN`, `TOO_MANY_ATTEMPTS`…) ; un cas de **conflit réel** (slug/nom d'organisation dupliqué) répond **409** `CONFLICT` ; la 422 de validation Pydantic garde le format d'erreur enveloppe (+ correlation_id existant préservé).
- [ ] AC 3 : OpenAPI à jour : schémas d'enveloppes + exemples documentés sur Scalar/Swagger/ReDoc ; tests d'intégration OpenAPI étendus et verts.
- [ ] AC 4 : **Clients synchronisés dans le même lot** : frontend (unwrap `data` dans les services/stores, non-régression des vues clés) et CLI ([`cli/client.py`](../../cli/client.py)) adaptés ; tests frontend et CLI verts ; breaking change **versionné et documenté** dans le CHANGELOG.
- [ ] AC 5 : `make lint` + `make backend-test` + `make frontend-test` verts ; aucune régression des garde-fous §2.G (aucun endpoint supprimé, middlewares sécurité intacts).

## Références spécification

- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Format de réponse (les 3 enveloppes + modèles Pydantic), § Gestion des erreurs (codes HTTP, classes d'erreur), § Documentation OpenAPI ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §1 (réponses nues, handler 422), §14 ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-5 (« à merger tôt »), §2.A A10, §5 chaîne critique n°4, §7.1 (breaking change — synchroniser frontend/CLI), §7.4 arbitrage n°6 ;
- `.roo/rules/20-architecture-and-api.md` — OpenAPI à jour avec un maximum de documentation et d'exemples, tout couvert par Pydantic.

## Dépendances

- Aucune dépendance technique en amont (peut démarrer dès le début de P1 — **à merger tôt**).
- Coordonnée avec : STORY-127 (la hiérarchie d'exceptions alimente le handler d'erreur enveloppe — sequencement à préciser par analyse-story) ; **bloque** STORY-128 (format `pagination{}`) et les surfaces P2 (STORY-170 notamment).

## Sous-stories

*(section réservée — ampleur L : `analyse-story` pourra découper (ex. schémas+handler / routers par lots / clients frontend+CLI) ; plage réservée STORY-132-159)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
