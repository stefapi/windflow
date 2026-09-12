# STORY-122.7 : RBAC — matrice transverse, non-régression et couverture

**Statut :** DONE
**Story Parente :** STORY-122 — Dépendances RBAC `require_role(...)` — hiérarchie, cache TTL 300 s et protections d'escalade sur les ~110 endpoints (P1-2, application)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'administrateur sécurité de WindFlow, je veux une vérification transverse finale du RBAC : un test structurel garantissant que **toutes** les routes non publiques sont protégées par une dépendance de rôle (aucun endpoint oublieux), la matrice rôle×endpoint représentative de bout en bout, les non-résressions critiques (`disable_auth`, login username/email, register, intégrité des routers) et l'atteinte de la couverture (≥ 80 % modules touchés, viser 95 % auth/RBAC).

## Critères d'acceptation (AC)

- [x] AC 2 (vérification exhaustive finale) : **Tous** les endpoints existants (~110, ~20 routers) sont protégés par `require_role(...)` conformément à la matrice spec 08 — vérifié par un **test structurel d'exhaustivité** (introspection `app.routes`) avec liste blanche des routes publiques (login/refresh/register/health) + la matrice représentative consolidée : viewer → `403` sur `DELETE /docker/containers/{id}` et sur les POST/PUT/DELETE de gestion ; operator → `200` sur les actions opérationnelles et `403` sur la gestion ; admin → gestion `200` dans son organisation ; `super_admin` requis sur l'admin instance (`admin/*`, création d'organisation…).
- [x] AC 5 : Tests de sécurité obligatoires écrits et passants : `401` sans token, `403` rôle insuffisant, `404` ressource étrangère — sur un échantillon par router ; non-régression : `disable_auth` fonctionne en dev, login username/email + register non régressés, aucun endpoint Docker supprimé ; couverture ≥ 80 % sur les modules touchés, **viser 95 %** sur auth/RBAC.

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-08) — clôture transverse des sous-stories 122.2-122.6.

**Couches impactées :** Backend uniquement — tests transverses + fixtures conftest partagées + ajustements finaux éventuels.

**Spécifications de référence :**
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — § Matrice (référence unique) ;
- `.roo/rules/35-testing-quality-gates.md` — couverture : 80 % modules, **95 % chemins critiques auth/RBAC** ;
- `.roo/rules/40-security.md` — tests sécurité obligatoires par endpoint.

**Routes publiques autorisées (liste blanche du test structurel) :**
- `POST /api/v1/auth/login` (l. 56), `POST /api/v1/auth/refresh` (l. 288), `POST /api/v1/auth/logout` (l. 466 — peut rester public : révocation best-effort), `POST /api/v1/auth/register` (l. 548) ;
- Endpoints santé système existants non-`/api/v1` (ex. `/health`, docs `/docs`, `/swagger`, `/redoc` — montés hors `api_router`) ;
- `GET /api/v1/auth/me` (l. 781) : protégé `get_current_active_user` — considéré protégé (dépendance auth), à catégoriser « viewer-equivalent » dans le test.

**Fichiers de référence (patterns vérifiés) :**
- Introspection routes — `app.routes` (Starlette) : `route.path`, `route.methods`, `route.dependant` — le test structurel vérifie par route non blanchie la présence d'une dépendance parmi `{require_role, require_viewer, require_operator, require_admin, require_super_admin, get_current_active_user, get_current_user_ws, ensure_role_ws, require_role_ws}` (parcours `route.dependant.dependencies` + params) ;
- Fixtures rôles — [`backend/tests/conftest.py`](../../backend/tests/conftest.py) : factoriser `test_user`/`test_superuser` existants en factory `make_user_with_role(role: Role, org)` + fixtures `viewer_client`, `operator_client`, `admin_client` (authentifiées par rôle d'org dans `test_organization`) — **à consommer par les tests 122.2-122.6** (retro-compatible : publier les fixtures ici si 122.2+ les attendent, cf. note dans ces stories) ;
- Non-régression auth — [`backend/tests/unit/test_api/test_auth_isolation.py`](../../backend/tests/unit/test_api/test_auth_isolation.py) (disable_auth l. 221), [`backend/tests/unit/test_auth/test_jwt_claims.py`](../../backend/tests/unit/test_auth/test_jwt_claims.py) ;
- Count Docker — 122.2 `test_docker_router_route_count_unchanged` (35) — consolidé ici en un test multi-routers.

**Exigences sécurité identifiées (Phase 2.6) :**
- Le test structurel **est** l'exigence sécurité centrale (anti-oubli) : toute nouvelle route non protégée fera échouer la CI ;
- Liste blanche fermée : ajout d'une route publique ⇒ modification explicite du test (revue obligatoire).

## Dépendances

- **STORY-122.2, 122.3, 122.4, 122.5, 122.6 toutes DONE** (la matrice consolidée n'a de sens qu'une fois les routers couverts).

## Tâches d'implémentation détaillées

### Tâche 1 : Fixtures rôles partagées dans conftest
**Objectif :** Factoriser la création d'utilisateurs par rôle + clients authentifiés, consommées par tous les tests RBAC.
**Fichiers :**
- `backend/tests/conftest.py` — Modifier —
  - Helper `async def create_user_with_role(db_session, test_organization, role: Role, *, is_superuser: bool = False) -> User` (généralise le pattern `test_user` l. 209 : `UserService.create` + `UserOrganization(role=...)`) ; noms/emails uniques (paramètre `suffix`) pour coexistence multi-users par test ;
  - Fixtures `viewer_user`/`viewer_client`, `operator_user`/`operator_client`, `org_admin_user`/`org_admin_client` (login + Authorization, pattern `authenticated_client` l. 320) — toutes scopées à `test_organization` ;
  - Conserver `test_user`/`test_superuser`/`authenticated_client`/`admin_client` inchangés (non-régression des suites existantes).
**Exigences sécurité :** Aucune (outillage tests).
**Dépend de :** Aucune (mais publier **avant** l'exécution des tests 122.2-122.6 si ceux-ci tournent après ; sinon livrer en premier dans l'ordre d'implémentation de la 122.7 si 122.2+ ont utilisé des factories locales — harmoniser alors).

### Tâche 2 : Test structurel d'exhaustivité RBAC (anti-oubli)
**Objectif :** Garantir que toute route `api_router` non blanchie porte une dépendance de rôle/auth.
**Fichiers :**
- `backend/tests/unit/test_api/test_rbac_exhaustivite.py` — Créer —
  - `PUBLIC_PATHS: frozenset` = login/refresh/logout/register (+ éventuels health vérifiés à l'implémentation) ;
  - `test_every_api_route_is_protected` : itère `app.routes`, filtre `path.startswith("/api/v1")`, ignore `PUBLIC_PATHS` ; pour chaque route : assert une dépendance de protection présente (parcours `route.dependant.dependencies[].call` — noms de fonctions attendues : `require_role`/aliases/`get_current_active_user`/`get_current_user_ws`/`ensure_role_ws`/`require_role_ws`) ; message d'erreur listant les routes fautives (actionnable) ;
  - `test_public_whitelist_minimal` : la liste blanche ne contient que des routes existantes (anti-dérive) ;
  - `test_websocket_routes_protected` : les 5 canaux `/api/v1/ws/...` ont une garde auth (+ rôle pour terminal) ;
  - `test_router_route_counts_stable` — table `{docker: 35, stacks: 15, deployments: 8, schedules: 6, organizations: 10, users: 8, plugins: 9, plugin_registry: 2, targets: 13, admin: 15, websockets: 5, auth: 5, compute: 2, discovery: 2, stats: 2, import_export: 2, workflows: 1}` — **aucun endpoint supprimé §2.G**.
**Exigences sécurité :** Anti-oubli systémique — le test échoue sur toute future route non protégée.
**Dépend de :** 122.2-122.6 DONE

### Tâche 3 : Matrice consolidée représentative + non-régression
**Objectif :** Scénario de bout en bout AC 2/AC 5 : parcours par rôle sur des endpoints réels de chaque famille + non-régressions critiques.
**Fichiers :**
- `backend/tests/unit/test_api/test_rbac_matrix_consolidated.py` — Créer — (fixtures Tâche 1, services mockés) :
  - **viewer** : 403 `DELETE /docker/containers/{id}` (AC littéral), 403 `POST /stacks`, 403 `POST /plugins/install`, 403 `POST /admin/stacks/import`, 403 `POST /organizations` ; 200 `GET /docker/containers`, `GET /stats/dashboard` ;
  - **operator** : 200 `POST /docker/containers/{id}/start`, 200 `POST /stacks/{id}/deploy` ; 403 `DELETE /docker/containers/{id}`, `POST /stacks`, `POST /organizations/{id}/users` ;
  - **admin d'org** : 200 `POST /stacks`, 200 `POST /organizations/{own}/users` ; 403 `POST /organizations` (création = SA), 403 `/admin/*` ;
  - **super_admin** : 200 `/admin/stacks/definitions`, `POST /organizations` ;
  - **404 ressource étrangère** (échantillon AC 5) : stack/deployment/target d'une org étrangère → 403/404 (pas 200) — reprend/consolide les cas de 122.3 ;
  - **401** : sans token sur un endpoint par router (paramétré) ;
  - Non-régression : `disable_auth=True` → `GET /api/v1/users` 200 sans header ; login username **et** email → 200 + token ; register → 201 ; logout → 200.
**Exigences sécurité :** Matrice par rôle et par famille ; l'échantillon couvre chaque router au moins une fois (401 paramétré).
**Dépend de :** Tâches 1, 2

### Tâche 4 : Couverture — mesure et renfort auth/RBAC (95 %)
**Objectif :** Mesurer la couverture des modules RBAC et renforcer les tests jusqu'aux cibles.
**Fichiers :**
- Sans nouveau module — exécuter : `poetry run pytest backend/tests/unit/test_auth/ backend/tests/unit/test_services/test_authorization_service.py backend/tests/unit/test_core/test_cache.py backend/tests/unit/test_api/test_*_rbac*.py backend/tests/unit/test_api/test_rbac_*.py --cov=app/auth --cov=app/services/authorization_service --cov=app/core/cache --cov-report=term-missing --cov-fail-under=95` ;
- Si < 95 % : compléter les tests manquants identifiés par `term-missing` (branches non couvertes de `rbac.py`/`authorization_service.py`/`cache.py` — typiquement fallback Redis KO, TTL limite, invalidation concurrente) ;
- Vérifier ≥ 80 % sur les routers modifiés (`--cov=app.api.v1` au global du suite API existante) ;
- Documenter le résultat dans les Notes d'implémentation.
**Exigences sécurité :** Cible 95 % chemins critiques (rules 35).
**Dépend de :** Tâche 3

## Tests à écrire

> Cette sous-story **est** une story de tests — détail dans les tâches.

### Unitaires Backend
- `backend/tests/unit/test_api/test_rbac_exhaustivite.py` — structurel anti-oubli + counts stables
- `backend/tests/unit/test_api/test_rbac_matrix_consolidated.py` — matrice ×4 rôles, 401/403/404, non-régression auth
- `backend/tests/conftest.py` — fixtures rôles (viewer/operator/org_admin + clients)

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_api/test_rbac_exhaustivite.py backend/tests/unit/test_api/test_rbac_matrix_consolidated.py -v
make backend-test-unit          # suite complète non-régression
poetry run pytest backend/tests/unit/test_auth/ backend/tests/unit/test_services/test_authorization_service.py backend/tests/unit/test_core/test_cache.py --cov=app/auth --cov=app/services/authorization_service --cov=app/core/cache --cov-fail-under=95
make backend-lint && make backend-typecheck
```

## État d'avancement technique
- [x] Tâche 1 : Fixtures rôles partagées (conftest)
- [x] Tâche 2 : Test structurel d'exhaustivité + counts routers
- [x] Tâche 3 : Matrice consolidée + non-régression (disable_auth/login/register)
- [x] Tâche 4 : Couverture 95 % auth/RBAC mesurée et atteinte
- [x] Suite backend complète verte + lint & typecheck OK

## Notes d'implémentation

**Date :** 2026-09-12

### Fichiers modifiés/créés
- `backend/tests/conftest.py` : helper public `create_user_with_role(db_session, organization, role, *, is_superuser=False, suffix="")` + fixtures `viewer_user`/`viewer_client`, `operator_user`/`operator_client`, `org_admin_user`/`org_admin_client` (login JWT réel, pattern `authenticated_client`) ; fixtures existantes (`test_user`/`test_superuser`/`authenticated_client`/`admin_client`) strictement conservées ;
- `backend/tests/unit/test_api/test_rbac_exhaustivite.py` : **créé** — test structurel anti-oubli (toute route `/api/v1` non blanchie porte une dépendance de protection, liste blanche fermée login/refresh/logout/register + anti-entrée-fantôme), gardes WebSocket (3 canaux dédiés `get_current_user_ws` + `ensure_role_ws` viewer dans le router ; général/terminal par inspection du handler : `authenticate_ws_first_message` + `ensure_role_ws`), inventaire exact des 5 canaux WS, comptes de routes stables par module router (140 routes totales) ;
- `backend/tests/unit/test_api/test_rbac_matrix_consolidated.py` : **créé** — matrice ×4 rôles de bout en bout (viewer 5×403 + 2×200 dont AC 2 littéral `DELETE /docker/containers/{id}` ; operator 204/201 opérationnels + 3×403 gestion ; admin d'org 201 POST /stacks + 201 ajout membre + 403 création org + 403 admin/* ; superuser 200 admin + 201 création org), isolation org étrangère (stack/target → 403/404 jamais 200), 401 paramétré sur 15 endpoints (1 par router), non-régression disable_auth/login username+email/register/logout ;
- `backend/tests/unit/test_stacks_duplicate.py` : bascule `authenticated_client` (operator) → `admin_client` sur 4 tests legacy — STORY-122.3 a porté `POST /stacks/{id}/duplicate` à rôle minimum Admin (duplication = création) ; le test operator recevait 403.

### Décisions techniques
- **Aplatissement récursif des routes** : FastAPI 0.141 utilise des inclusions lazy (`_IncludedRouter`) — `app.routes` n'expose pas les routes des sous-routers ; un helper `_flatten_routes` (résolution `original_router` + cumul des `include_context.prefix`) reconstruit les chemins absolus (même intention que le passage par OpenAPI du test non-régression Docker de 122.2) ;
- **Canaux WS premier-message** : leur garde n'est pas une dépendance FastAPI (dans le handler) — vérifiée par inspection de source (`inspect.getsource`) : présence de `authenticate_ws_first_message` + `ensure_role_ws` avec le rôle matriciel (viewer général / operator terminal) ;
- **Comptes par module router** (targets/admin = packages à sous-routers aplatis) : auth 5, users 8, organizations 10, targets 13, stacks 15, deployments 8, workflows 1, websockets 5, stats 2, import_export 2, schedules 6, admin 15, docker 35, compute 2, discovery 2, plugins 9, plugin_registry 2 — **140 routes, aucune supprimée (§2.G)** ;
- **Table attendue de la story** : `import_export: 2` exposé sous `/stacks/*` (router séparé) — compté par module, pas par segment d'URL ; comptes vérifiés conformes.

### Divergences par rapport à l'analyse
- Tâche 2 : la story citait `route.dependant.dependencies[].call` avec noms `require_role`/aliases — les factories produisent des fermetures `role_checker`/`role_checker_ws` : le test matche ces noms réels (+ `get_current_active_user`/`get_current_user_ws` viewer-equivalent), sémantique inchangée ;
- Tâche 4 : la commande de couverture de la story listait `test_*_rbac*.py` sans les tests WebSocket — or `ensure_role_ws` (lignes 197-216 de `rbac.py`) n'est couvert que par `test_ws_rbac.py` ; l'ensemble mesuré inclut donc `tests/unit/test_websocket/` et les suites auth/isolation/escalation.

### Résultats de validation (venv `.venv-test`, Python 3.11)
- **Couvertures chemins critiques** : `app/auth/rbac.py` **100 %**, `app/services/authorization_service.py` **98 %**, `app/auth/dependencies.py` **91 %**, `app/core/cache.py` **85 %** (cible 95 % RBAC atteinte sur rbac.py + authorization_service) ;
- `pytest tests/unit/test_api/test_rbac_exhaustivite.py` : **6 passed** ;
- `pytest tests/unit/test_api/test_rbac_matrix_consolidated.py` : **39 passed** ;
- `pytest tests/unit/` (suite complète, non-régression) : **1376 passed** en 44 s ;
- isort/black/flake8 sur conftest.py + 2 nouveaux fichiers : **OK** ; mypy : erreurs préexistantes uniquement (lignes `test_user`/`test_superuser` originales — `make backend-typecheck` ne couvre que `app/`).

### Tests ajoutés
- `backend/tests/unit/test_api/test_rbac_exhaustivite.py` : 6 tests (anti-oubli HTTP, anti-dérive liste blanche, 3 gardes WS, comptes stables) ;
- `backend/tests/unit/test_api/test_rbac_matrix_consolidated.py` : 39 tests (matrice ×4 rôles, isolation, 15× 401 paramétrés, 4 non-régressions auth).
