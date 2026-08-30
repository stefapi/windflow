# STORY-127 : Hiérarchie d'exceptions — compléter `core/exceptions.py` et remplacer les `HTTPException` brutes (P1-5, partie exceptions)

**Statut :** TODO
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-5 partie exceptions (axe A11, rapport §1) — ampleur **M** (partie exceptions de l'item L)

## Description

En tant que développeur backend de WindFlow, je veux une hiérarchie d'exceptions complète (`NotFoundError`, `ConflictError`, `ValidationError`, `PermissionDeniedError`, `AuthenticationError`… héritant de `WindFlowException`) et un handler global qui les convertit en enveloppe d'erreur `{error:{code,message}}`, afin que plus aucun endpoint ne lève de `HTTPException` brute et que les codes d'erreur soient cohérents sur toute l'API.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §10, §14) : [`core/exceptions.py`](../../backend/app/core/exceptions.py:10) ne contient que **2 exceptions** (`WindFlowException` + `CommandExecutionError`) alors que « beaucoup d'endpoints lèvent encore des `HTTPException` brutes ». La spec 09 § Classes d'erreur définit la hiérarchie cible (`APIError(code)` → `NotFoundError` 404, `PermissionDeniedError` 403, `ConflictError` 409…), et les rules 30 imposent : « toujours lever des exceptions de `core/exceptions.py`, jamais des exceptions Python brutes dans les endpoints ».

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- Base existante : [`WindFlowException`](../../backend/app/core/exceptions.py:10) (avec `details`) — la hiérarchie cible hérite de cette base (spec 09 montre des `APIError` HTTPException-like : l'analyse arbitrera l'ancrage exact — `WindFlowException` → traduction en HTTP par le handler global, en préservant le contrat `{error:{code,message,details}}`) ;
- Classes minimales attendues : `NotFoundError` (404, `NOT_FOUND`), `ConflictError` (409, `CONFLICT`), `ValidationError`/`InvalidInputError` (400/422), `PermissionDeniedError` (403, `PERMISSION_DENIED`), `AuthenticationError` (401, `INVALID_OR_EXPIRED_TOKEN` / `INVALID_CREDENTIALS`), `RateLimitError` (429, `TOO_MANY_ATTEMPTS`), plus la conservation de `CommandExecutionError` ;
- **Handler global** dans [`main.py`](../../backend/app/main.py:380) (où résident déjà les handlers Pydantic/FastAPI → 422 + correlation_id) : capture `WindFlowException` et sous-classes → enveloppe erreur STORY-126 ; les handlers existants (422, correlation_id) ne régressent pas ;
- **Remplacement des `HTTPException` brutes** dans les endpoints/services : sweep sur les ~20 fichiers routers + services concernés (docker.py, stacks, organizations, targets…) — chaque raise devient une exception typée ; pas de changement de **comportement** HTTP (mêmes codes, messages stabilisés) ;
- Coordination STORY-126 : le format d'erreur enveloppe est posé par STORY-126 ; cette story branche la hiérarchie dessus. Si STORY-126 n'est pas encore fusionnée, le handler produit le format cible et les tests de contrat valident à la fusion ;
- Ne pas toucher aux middlewares sécurité ni au plugin WS (garde-fous §2.G).

## Critères d'acceptation (AC)

- [ ] AC 1 : [`core/exceptions.py`](../../backend/app/core/exceptions.py:10) expose la hiérarchie complète héritant de `WindFlowException` avec code d'erreur et statut HTTP associés (404/409/400/422/401/403/429) ; un **handler global** convertit toute `WindFlowException` non interceptée en enveloppe `{error:{code,message,details?}}` (format STORY-126) en préservant le `correlation_id` existant.
- [ ] AC 2 : **Plus aucune `HTTPException` brute** dans les endpoints `api/v1/` (grep vérifié) : tous les raises passent par la hiérarchie ; les codes HTTP effectifs sont inchangés par rapport au comportement actuel (non-régression des tests d'API existants).
- [ ] AC 3 : Les cas d'erreur types répondent avec les bons codes : ressource inexistante → `404 NOT_FOUND` ; conflit (slug dupliqué) → `409 CONFLICT` ; rôle insuffisant → `403 PERMISSION_DENIED` ; non authentifié → `401` ; validation → `422` (format handler Pydantic existant conservé).
- [ ] AC 4 : Tests unitaires sur la hiérarchie (mapping exception → code/statut) + tests d'API de non-régression sur un échantillon par router ; `make lint` + `make backend-test` verts.

## Références spécification

- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Gestion des erreurs → Classes d'erreur (`APIError`, `NotFoundError`, `PermissionDeniedError`, `ConflictError`), § Codes HTTP utilisés ;
- `.roo/rules/30-code-standards.md` — § Gestion d'erreurs backend : exceptions personnalisées héritant de `WindFlowException`, codes HTTP appropriés, logs structurés avec contexte ;
- `.roo/rules/55-project-structure.md` — « Toujours lever des exceptions de `core/exceptions.py`, jamais des exceptions Python brutes dans les endpoints » ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §10 (2 exceptions seulement, HTTPException brutes), §14 ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-5 (partie exceptions), §2.A A11.

## Dépendances

- Coordonnée avec **STORY-126** (le handler global alimente l'enveloppe d'erreur — séquencement à préciser par analyse-story ; indépendante techniquement sur la partie hiérarchie).
- Facilite : STORY-122 (le refus RBAC lève `PermissionDeniedError` typée), STORY-125 (échecs d'audit loggés avec contexte).

## Sous-stories

*(section réservée — ampleur M, découpe non prévue a priori)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
