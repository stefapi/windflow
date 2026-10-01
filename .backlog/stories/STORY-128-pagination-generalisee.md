# STORY-128 : Pagination généralisée — `?page&per_page` sur toutes les listes non paginées (P1-6)

**Statut :** DONE
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-6 (axe C1, rapport §1) — ampleur **M**

## Description

En tant que consommateur de l'API WindFlow (UI, CLI, scripts), je veux que **toutes** les listes soient paginées via `?page=&per_page=` et répondent dans l'enveloppe `PaginatedResponse{data, pagination{page, per_page, total, pages}}`, afin de maîtriser le volume de données transférées et de disposer d'un contrat homogène (rules 20 : pagination obligatoire pour les listes > 20 éléments).

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §1, §14) : les listes stacks ([`stacks.py:116`](../../backend/app/api/v1/stacks.py:116)), organizations ([`organizations.py:43`](../../backend/app/api/v1/organizations.py:43)), schedules ([`schedules.py:24`](../../backend/app/api/v1/schedules.py:24)) et plugins ([`plugins.py:45`](../../backend/app/api/v1/plugins.py:45)) ne sont **pas paginées** (retour complet). La spec 09 exige : « toutes les listes sont paginées avec `?page=1&per_page=20` ».

## Contexte technique

> Analyse réalisée en mode exploration (remplace `analyse-story`) — aucun code modifié. La story reste `TODO`.

### Inventaire des listes — 3 formats coexistants (audit code)

**Format A — liste nue (pas de pagination de contrat)** :

| Endpoint | Handler | Params actuels | Source |
|---|---|---|---|
| `GET /api/v1/stacks/` | [`list_stacks`](../../backend/app/api/v1/stacks.py:201) | `skip=0, limit=100` **nus** (non validés par `Query()`) | SQL |
| `GET /api/v1/organizations/` | [`list_organizations`](../../backend/app/api/v1/organizations.py:148) | idem | SQL |
| `GET /api/v1/schedules` | [`list_schedules`](../../backend/app/api/v1/schedules.py:74) | aucun | SQL |
| `GET /api/v1/plugins/` | [`list_plugins`](../../backend/app/api/v1/plugins.py:95) | idem stacks | SQL |
| `GET /api/v1/registry/plugins` | [`list_registry_plugins`](../../backend/app/api/v1/plugin_registry.py:53) | idem + `category`/`query` | YAML filesystem (slicing mémoire l.91) |
| `GET /api/v1/targets/` | [`list_targets`](../../backend/app/api/v1/targets/crud.py:133) | idem | SQL multi-org |
| `GET /api/v1/auth/api-keys` | [`list_api_keys`](../../backend/app/api/v1/auth.py:1174) | aucun | SQL |
| `GET /api/v1/workflows/` | [`list_workflows`](../../backend/app/api/v1/workflows.py:16) | skip/limit morts (stub retourne `[]`) | stub |
| `GET /api/v1/stacks/{id}/versions` | [`list_stack_versions`](../../backend/app/api/v1/stacks.py:1466) | aucun | SQL (select direct) |
| `GET /api/v1/organizations/{id}/users` | [`list_organization_members`](../../backend/app/api/v1/organizations.py:1159) | skip/limit nus | SQL |
| `GET /api/v1/plugins/{id}/hooks/logs` | [`get_hook_logs`](../../backend/app/api/v1/plugins.py:552) | skip/limit nus | SQL |
| `GET /api/v1/admin/stacks/definitions` | [`list_stack_definitions`](../../backend/app/api/v1/admin/stacks_management.py:113) | aucun | filesystem YAML |
| `GET /api/v1/admin/stacks/imported` | [`list_imported_stacks`](../../backend/app/api/v1/admin/stacks_management.py:336) | `skip/limit` `Query` | SQL |
| `GET /api/v1/docker/containers|images|volumes|networks` | [`list_containers`](../../backend/app/api/v1/docker.py:147), [`list_images`](../../backend/app/api/v1/docker.py:1549)… | `skip/limit` `Query(ge/le=100)` + slicing mémoire | Docker daemon (non SQL) |

**Format B — `{items, total, skip, limit}`** : [`list_deployments`](../../backend/app/api/v1/deployments.py:124) (`DeploymentListResponse`) et [`list_audit_entries`](../../backend/app/api/v1/admin/audit.py:153) (`AuditLogListResponse` — bornes `Query` correctes).

**Format C — `{items, total, page, size, pages}`** : [`list_users`](../../backend/app/api/v1/users.py:181) — le plus proche de la cible (renommages `size`→`per_page`, restructuration sous `data`/`pagination`).

### Socle réutilisable (STORY-126 — DONE ✔)

- [`schemas/common.py`](../../backend/app/schemas/common.py:22) livre déjà `PaginationMeta{page, per_page, total, pages}` et `PaginatedResponse{data, pagination}` — **aucun nouveau schéma à créer** ; [`PaginationParams`](../../backend/app/schemas/common.py:189) legacy skip/limit est marqué déprécié « voir STORY-128 » (0 consommateur backend — retrait à confirmer par grep en tâche 3).
- **Piège architectural — double enveloppement** : [`api_response_middleware`](../../backend/app/middleware/api_response.py:150) enveloppe tout 2xx JSON `/api/v1/*` en `{data, message}` ; un handler retournant `PaginatedResponse` produirait `{data: {data: [...], pagination: {...}}, message: null}`. Le middleware doit reconnaître un corps déjà paginé (détection structurelle `data`+`pagination`, symétrique du [`_unwrap_payload`](../../cli/client.py:79) CLI) et le laisser passer en complétant `message: null`.

### Clients (STORY-126.3 — DONE ✔)

- **CLI** : [`_unwrap_payload`](../../cli/client.py:79) déplie déjà `{data, pagination}` (couvert par [`test_client_envelope.py`](../../cli/tests/test_client_envelope.py:44)) mais **droppait `pagination`** — les commandes liste (ex. [`org.py`](../../cli/commands/org.py)) devront boucler sur les pages ou monter `per_page=100` pour conserver un affichage complet.
- **Frontend** : [`unwrapResponse`](../../frontend/src/services/http.ts:43) remplace `response.data` par `body.data` → `pagination` perdue ; [`PaginatedResponse<T>`](../../frontend/src/types/api.ts:378) documente déjà « STORY-128 convertira en `pagination{}` ». Stores concernés (pattern défensif `Array.isArray(body) ? body : body.items ?? []`) : [`stacks.ts`](../../frontend/src/stores/stacks.ts:24), [`targets.ts`](../../frontend/src/stores/targets.ts:21), [`deployments.ts`](../../frontend/src/stores/deployments.ts:25), [`workflows.ts`](../../frontend/src/stores/workflows.ts:16).

### Bugs préexistants découverts (à corriger pour tenir AC 3)

1. **Agrégation multi-org faussée** — [`list_targets`](../../backend/app/api/v1/targets/crud.py:164) et [`list_deployments`](../../backend/app/api/v1/deployments.py:152) appliquent `skip/limit` **par organisation** puis concatènent : une pagination correcte exige une requête unique `WHERE organization_id IN (...)` + `COUNT` global scopusé (sinon `total`/`pages` faux et pages chevauchantes).
2. **Ordre non déterministe** — [`OrganizationService.list_all`](../../backend/app/services/organization_service.py:75) (et autres listes sans `order_by`) : la pagination exige un tri stable (`ORDER BY name` ou `created_at`) sous peine de doublons/trous entre pages.

### Décisions tranchées par l'analyse (AC 2)

| Question | Décision | Justification |
|---|---|---|
| `per_page` > 100 | **422** via `Query(ge=1, le=100)` — pas de clamp silencieux | Cohérent avec [`audit.py`](../../backend/app/api/v1/admin/audit.py:175) et docker `Query(50, ge=1, le=100)` ; explicite et auto-documenté OpenAPI |
| `page` au-delà de la dernière | **200 + `data: []`** + métadonnées exactes | Convention REST ; évite les races sur `total` variable |
| `page=0` / négatif | 422 via `Query(ge=1)` | Pagination 1-indexée spec 09 |
| Défauts | `page=1`, `per_page=20` | Spec 09 § Principes ; AC 2 |
| Sources non SQL (Docker daemon, YAML registry/filesystem) | `total = len(liste)` + slicing mémoire | Pas de COUNT possible ; généralise le slicing existant |
| `total` SQL | `SELECT COUNT(*)` avec **les mêmes filtres/scoping que la liste** | Évite un oracle de comptage cross-org (rules 40 — isolation) |

Éléments existants à réutiliser / contraintes :
- **Harmonisation avec l'enveloppe** : chaque liste paginée répond `{data, pagination{page, per_page, total, pages}}` (STORY-126 dont dépend cette story pour le format) ;
- **Bornes** : `per_page` par défaut **20**, maximum **100** (critère de done P1-6 ; dépassement → clamp ou `422` — à trancher par l'analyse, cohérent avec la validation Pydantic `Query(ge=1, le=100)`) ; defaults documentés dans OpenAPI ;
- Cibles explicites du plan : [`stacks.py`](../../backend/app/api/v1/stacks.py:116), [`organizations.py`](../../backend/app/api/v1/organizations.py:43), [`schedules.py`](../../backend/app/api/v1/schedules.py:24), [`plugins.py`](../../backend/app/api/v1/plugins.py:45), [`targets/`](../../backend/app/api/v1/targets) (crud) **+ `plugin_registry`** (mentionné mission/epic) — et passer en revue les autres listes non paginées (users, deployments si applicable…) pour couverture complète ;
- Les listes **déjà** paginées (module Docker — cf. backend_status « pagination » dans les points forts) doivent être **harmonisées** au format `pagination{}` commun si leur format diffère ;
- Réutiliser un helper commun (query params + comptage `total` + calcul `pages`) plutôt que dupliquer par router (DRY) ;
- Breaking change léger pour les consommateurs qui lisaient des listes nues : couvert/absorbé par la synchronisation clients de STORY-126 (même lot de coordination frontend/CLI si non déjà fusionnée) ;
- Tests frontend/CLI de non-régression sur les vues concernées (Stacks.vue, Targets.vue…).

## Critères d'acceptation (AC)

- [x] AC 1 : Chaque liste cible (stacks, organizations, schedules, plugins, plugin_registry, targets, et toute autre liste non paginée identifiée) expose `?page=&per_page=` et répond `{data, pagination{page, per_page, total, pages}}` ; les listes déjà paginées (Docker) sont harmonisées au même format `pagination{}`. *(vérifié : 20/20 endpoints convertis/harmonisés, contrat validé par test_api_pagination.py + tests unitaires par router ; endpoint `shells` exclu — exception documentée)*
- [x] AC 2 : **Bornes respectées** : défaut `per_page=20`, max `100` (valeur au-delà → 422 documenté) ; `page=0` → 422 (pagination 1-indexée) ; defaults visibles dans OpenAPI (vérifié par génération de la spec : `page=1`/`per_page=20`/`maximum=100` sur les 20 endpoints).
- [x] AC 3 : `total` et `pages` exacts (comptage SQL réel `COUNT` scopusé, requête unique `IN (org_ids)` pour targets/deployments) ; tri/filtres existants combinables (`include_archived`, `category`/`query` registry, `user_id`/`action`/`since` audit, `organization_id` schedules — filtrage avant pagination, `total` filtré exact).
- [x] AC 4 : Tests par endpoint paginé (vide, < per_page, multi-pages, bornes 422, page au-delà) + non-régression clients (frontend 918/918 Vitest dont http/stores/Stacks.spec ; CLI 17/17) ; backend sweep 1807 passed / 12 échecs préexistants baseline (stack_actions ×11, delete_deployment, api_key_logs — prouvés pré-STORY-128 par git stash) ; lint/flake8/mypy/vue-tsc clean sur les fichiers touchés.

## Références spécification

- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Principes (« toutes les listes sont paginées avec `?page=1&per_page=20` »), § Format de réponse (`PaginatedResponse`/`PaginationMeta`) ;
- `.roo/rules/20-architecture-and-api.md` — « Pagination obligatoire pour listes > 20 éléments » ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §1 (listes non paginées), §14 ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-6 (dépend de P1-5 pour le format), §2.C C1, §5 chaîne critique n°4.

## Dépendances

- **STORY-126 (.1/.2/.3) — DONE ✔** : prérequis absolu satisfait — [`PaginatedResponse`](../../backend/app/schemas/common.py:92)/[`PaginationMeta`](../../backend/app/schemas/common.py:22) disponibles, enveloppe active, clients synchronisés (unwrap CLI/frontend en place).
- **STORY-127 — DONE ✔** : les erreurs de validation 422 des `Query(ge/le)` transiteront par la hiérarchie typée existante vers l'enveloppe erreur — rien à re-câbler.
- **Aucune migration DB** : la pagination est purement couche API/requêtes (aucune table modifiée).
- **Aucun service externe nouveau** ; Docker daemon et filesystem YAML restent les sources non-SQL (slicing mémoire).
- **Conditionne** : toutes les surfaces élargies P2 (STORY-170 `/compute` browse paginé, STORY-167 `GET /deployments/{id}/events`, STORY-173 compute browse/prune) — qui devront réutiliser le helper commun livré ici.
- **Coordination CHANGELOG** : breaking change contrat (listes nues → `pagination{}`) → entrée versionnée comme STORY-126.3 l'a fait.

## Sous-stories

*(section réservée — ampleur M, découpe non prévue a priori)*

## État d'avancement technique

> Exécution découpée en vagues. **Vagues 1-2 (backend) + vague 3 (clients,
> CHANGELOG) terminées** — statut `DONE`.

- [x] Tâche 1 — Helper pagination commun (`backend/app/helper/pagination.py` :
  `PaginationQuery`, `build_meta`, `paginate_sequence`) *(vague 1)*
- [x] Tâche 2 — Middleware anti double-enveloppement (`api_response.py` :
  `_is_paginated_body` + passage du corps avec `message: null` complété) *(vague 1)*
- [x] Tâche 3 — Ménage schémas legacy : `PaginationParams` retiré de
  `schemas/common.py` (grep : 0 consommateur confirmé) ; champs morts
  `skip/limit` retirés des signatures des handlers convertis *(vague 1)*
- [x] Tâche 4 — Router stacks : `list_stacks` (requête unique multi-org `IN`,
  tri `name`, COUNT scopusé — corrige l'agrégation par-org) +
  `list_stack_versions` (tri `version_number desc` conservé + COUNT) ;
  `StackService.list_by_organizations`/`count_by_organizations` ajoutés *(vague 1)*
- [x] Tâche 5 — Router organizations : `list_organizations` (super_admin,
  tri `name`, `OrganizationService.count_all` ajouté) +
  `list_organization_members` (tri `joined_at`,
  `UserOrganizationService.count_members` ajouté, isolation conservée) *(vague 1)*
- [x] Tâche 6 — Router schedules : `PaginationQuery` + COUNT scopusé
  (`organization_id` combinable), tri stable *(vague 2)*
- [x] Tâche 7 — Router plugins + registry : `list_plugins` (COUNT par org,
  tri `name`) + `get_hook_logs` (COUNT par plugin) ; registry : filtres
  `category`/`query` avant slicing + tri stable par nom via
  `paginate_sequence` *(vague 2)*
- [x] Tâche 8 — Router targets : requête unique `WHERE organization_id IN
  (org_ids)` + COUNT scopusé + tri `name` (bug agrégation corrigé) *(vague 2)*
- [x] Tâche 9 — Router users : format C `{items, total, page, size, pages}`
  converti en `PaginatedResponse` ; `UserService.list_all` retourne
  `(items, total)` avec scoping identique *(vague 2)*
- [x] Tâche 10 — Router deployments : format B converti + bug agrégation
  multi-org corrigé (requête unique `IN`), tri `created_at desc` *(vague 2)*
- [x] Tâche 11 — Router auth api-keys : `page/per_page` + COUNT scopusé
  owner, tri `created_at desc`, contrat sans secrets inchangé *(vague 2)*
- [x] Tâche 12 — Routers admin : audit (`skip/limit` → `page/per_page`,
  `AuditLogListResponse` retiré) + stacks_management (`definitions` via
  `paginate_sequence`, `imported` COUNT SQL) *(vague 2)*
- [x] Tâche 13 — Module docker : containers/images/volumes/networks
  harmonisés via `paginate_sequence` (per_page le=100 conservé) ; `shells`
  exclu (exception documentée) ; **aucun endpoint supprimé** (garde-fou
  EPIC-012) *(vague 2)*
- [x] Tâche 14 — Workflows stub : `PaginatedResponse` vide contracté
  (`total: 0, pages: 0`) *(vague 2)*
- [x] Tâche 15 — CLI : `PaginatedResult` (NamedTuple items+pagination,
  propriété `total`) + `get_paginated()` (métadonnées conservées, tolérant
  liste nue) + `get_all()` (assemblage multi-pages `per_page=100`, garde-fou
  `max_pages=50`) ; commandes liste `org`/`deploy`/`env` migrées vers
  `get_all` avec total réel affiché ; 17/17 tests CLI *(vague 3)*
- [x] Tâche 16 — Frontend : `PaginatedResponse<T>` → `{data, pagination}` +
  `PaginationMeta` + `LegacyListBody` (transition) ; `unwrapResponse`
  rattache `pagination` à `response.pagination` (augmentation AxiosResponse) ;
  stores stacks/targets/deployments/workflows lisent `data` avec fallback
  `items` et exposent `pagination{total, pages}` ; services `api.ts` en
  `page/per_page` ; composables useUsers/useOrganizations et
  RecentDeploymentsWidget migrés ; 918/918 Vitest *(vague 3)*
- [x] Tâche 17 — OpenAPI vérifié par génération (20/20 endpoints :
  `page=1`/`per_page=20`/`maximum=100` documentés) ; entrée CHANGELOG
  « BREAKING — STORY-128 » versionnée sous `[Unreleased]` (pattern
  STORY-126.3) *(vague 3)*

### Validation vague 1

- `backend/tests/unit/test_helper/test_pagination.py` : 17 tests — helper à
  **100% de couverture** ;
- `backend/tests/unit/test_middleware/test_api_response.py` : 8 tests
  (détection structurelle, non-confusion payload métier) ;
- `backend/tests/integration/test_api_pagination.py` : 21 tests (contrat paginé
  stacks/orgs/members/versions, multi-pages sans doublon, multi-org total
  exact, bornes 422, page au-delà, filtre `include_archived`, sécurité
  401/403/404 isolation) ;
- Non-régression : 174 tests enveloppe/contrat/RBAC verts ; sweep complet
  comparé au baseline (git stash) → **0 régression**, 7 échecs préexistants
  réparés (`test_stacks_archive.py`), 20 échecs préexistants restants hors
  périmètre (divergence n°3) ;
- Qualité : black + isort appliqués, flake8 clean, mypy sans erreur sur les
  fichiers modifiés.

## Tâches d'implémentation détaillées

> Séquencement : socle → middleware → routers SQL → routers non-SQL → harmonisation formats B/C → clients → docs. Sécurité (rules 40) intégrée inline ; RBAC existant (`require_viewer`/`require_admin`/`require_super_admin`) **inchangé** — la pagination n'ajoute aucun privilège.

1. **Helper pagination commun** — créer `backend/app/helper/pagination.py` :
   - `PaginationQuery` : `page: int = Query(1, ge=1)`, `per_page: int = Query(20, ge=1, le=100)` avec descriptions/examples OpenAPI (AC 2 — defaults visibles) ;
   - `paginate_sequence(items, page, per_page) -> PaginatedResponse` (slicing mémoire + `total=len`, `pages=ceil`) pour sources non-SQL ;
   - `build_meta(page, per_page, total) -> PaginationMeta` (`pages = ceil(total/per_page)`, 0 si total=0) ;
   - fonctions pures, type hints complets (rules 30), docstrings — pattern fichier : [`helper/permissions.py`](../../backend/app/helper/permissions.py).

2. **Middleware — anti double-enveloppement** — [`api_response.py`](../../backend/app/middleware/api_response.py:150) : après `json.loads`, si le corps est un dict contenant `data` (liste) + `pagination` (dict avec clés `page`/`per_page`/`total`/`pages`), le laisser passer tel quel en ajoutant `message: null` si absent (détection structurelle symétrique du [`_unwrap_payload`](../../cli/client.py:87) CLI) ; sinon enveloppe standard. Tests unitaires dédiés (pas de fuite du corps métier).

3. **Ménage schémas legacy** — [`common.py`](../../backend/app/schemas/common.py:189) : grep `PaginationParams` — si 0 consommateur (vérifié à l'analyse), le retirer (sa docstring pointait déjà vers STORY-128) ; sinon le conserver déprécié. Retirer également les champs morts `skip/limit` des `Query` des handlers convertis.

4. **Router stacks** — [`stacks.py`](../../backend/app/api/v1/stacks.py:201) : `list_stacks` passe à `page/per_page` `Query` validés ; service [`StackService`](../../backend/app/services/stack_service.py) : ajouter `count` (SQL `COUNT` avec `include_archived` identique à la liste — pas d'oracle cross-org), tri stable `ORDER BY name` ; retour `PaginatedResponse`. Idem [`list_stack_versions`](../../backend/app/api/v1/stacks.py:1466) (tri existant `version_number.desc` conservé + COUNT). Mettre à jour les examples OpenAPI 200 (`pagination{}`).

5. **Router organizations** — [`organizations.py`](../../backend/app/api/v1/organizations.py:148) : `list_organizations` (super_admin — RBAC inchangé) + [`list_organization_members`](../../backend/app/api/v1/organizations.py:1159) ; services : `count_all`, `count_members(org_id)` ; tri stable (name / joined_at) ; isolation membre existante conservée.

6. **Router schedules** — [`schedules.py`](../../backend/app/api/v1/schedules.py:74) : ajouter `page/per_page` ; [`SchedulerService`](../../backend/app/services/scheduler_service.py) : COUNT + `ORDER BY name` (filtre `organization_id` combiné).

7. **Router plugins + registry** — [`plugins.py`](../../backend/app/api/v1/plugins.py:95) : `list_plugins` (COUNT par org, tri `name` existant) + [`get_hook_logs`](../../backend/app/api/v1/plugins.py:552) (COUNT par plugin) ; [`plugin_registry.py`](../../backend/app/api/v1/plugin_registry.py:53) : filtres `category`/`query` appliqués **avant** slicing, `total = len(filtrée)` via `paginate_sequence`.

8. **Router targets (bug agrégation)** — [`targets/crud.py`](../../backend/app/api/v1/targets/crud.py:133) : remplacer la boucle par-org par une requête unique `WHERE organization_id IN (org_ids)` + `COUNT` scopusé + `ORDER BY name` (corrige le bug préexistant identifié en Contexte technique) ; `TargetService.list_by_organizations(session, org_ids, page, per_page)` + `count_by_organizations`.

9. **Router users (format C → cible)** — [`users.py`](../../backend/app/api/v1/users.py:181) : convertir `UserListResponse{items,total,page,size,pages}` vers `PaginatedResponse` ; [`UserService.list_all`](../../backend/app/services/user_service.py) étendu pour retourner `(items, total)` dans les deux branches scoping (superuser / org_ids — COUNT avec le même scoping) ; tri stable username.

10. **Router deployments (format B + bug agrégation)** — [`deployments.py`](../../backend/app/api/v1/deployments.py:124) : idem targets — requête unique `IN (org_ids)` + COUNT scopusé, retour `PaginatedResponse` (remplace `DeploymentListResponse{items,total,skip,limit}`) ; tri `created_at desc`.

11. **Router auth api-keys** — [`auth.py`](../../backend/app/api/v1/auth.py:1174) : `page/per_page` + COUNT scopusé owner (`list_for_user` existant — jamais `key_hash`/clé en clair dans la réponse, contrat [`APIKeyResponse`](../../backend/app/schemas/api_key.py) inchangé) ; tri `created_at desc`.

12. **Routers admin** — [`admin/audit.py`](../../backend/app/api/v1/admin/audit.py:153) : convertir `skip/limit` `Query` → `page/per_page` (bornes le=100 conservées), [`AuditService.list_entries`](../../backend/app/services/audit_service.py) reçoit offset calculé, retour `PaginatedResponse` (remplace `AuditLogListResponse`) ; [`admin/stacks_management.py`](../../backend/app/api/v1/admin/stacks_management.py:113) : `definitions` + `imported` via `paginate_sequence`/COUNT.

13. **Module docker (harmonisation AC 1)** — [`docker.py`](../../backend/app/api/v1/docker.py:147) : `list_containers`/`list_images`/`list_volumes`/`list_networks` : remplacer `skip/limit` par `page/per_page` (le=100 conservé), slicing `(page-1)*per_page` sur la liste daemon, `total = len(liste)`, retour `PaginatedResponse` ; garde-fou : aucune suppression d'endpoint (EPIC-012) ; endpoint `shells` (liste technique énumérant les shells disponibles d'un conteneur, hors collection exploitable) **exclu** de la pagination — documenter l'exception.

14. **Workflows stub** — [`workflows.py`](../../backend/app/api/v1/workflows.py:16) : retourner `PaginatedResponse` vide (`data: [], pagination: {page, per_page, total: 0, pages: 0}`) pour contracter le format dès maintenant.

15. **CLI** — [`client.py`](../../cli/client.py) : exposer `get_paginated()` ou faire survivre `pagination` au unwrap (option return_meta) ; commandes liste concernées ([`org.py`](../../cli/commands/org.py) etc.) : boucle multi-pages ou `per_page=100` par défaut avec message « N résultats affichés sur T » — aucune régression d'affichage.

16. **Frontend** — [`types/api.ts`](../../frontend/src/types/api.ts:378) : `PaginatedResponse<T>` → `{data: T[], pagination: {page, per_page, total, pages}}` ; [`http.ts`](../../frontend/src/services/http.ts:43) `unwrapResponse` : préserver `pagination` (la rattacher à `response.data.pagination` ou exposer `response.pagination`) ; stores [`stacks.ts`](../../frontend/src/stores/stacks.ts:24)/[`targets.ts`](../../frontend/src/stores/targets.ts:21)/[`deployments.ts`](../../frontend/src/stores/deployments.ts:25)/[`workflows.ts`](../../frontend/src/stores/workflows.ts:16) : lire `body.data` (nouveau format) avec fallback transition `Array.isArray(body) ? body : body.items ?? []` (un seul lot de coordination, cf. 126.3).

17. **OpenAPI + CHANGELOG** : vérifier examples 200 de tous les endpoints convertis (defaults `page=1&per_page=20` visibles — AC 2) ; entrée CHANGELOG « Changed: toutes les listes → pagination{page,per_page,total,pages} » versionnée.

## Tests à écrire

> Patterns : rules 35 (`httpx.AsyncClient` + `ASGITransport`, `_jwt_mode`/`_bearer` du [`test_api_envelope.py`](../../backend/tests/integration/test_api_envelope.py:37)) ; sécurité rules 40 intégrée par endpoint. Cible couverture ≥ 80 % (helper pagination : viser ~100 % — fonctions pures).

### Unitaires — backend

- `backend/tests/unit/test_helper/test_pagination.py` : `build_meta` (total=0 → pages=0 ; total=21, per_page=20 → pages=2), `paginate_sequence` (page 1, dernière page, page au-delà → `data: []` + méta exactes, slicing sans chevauchement), `PaginationQuery` bornes (per_page=101 invalide, page=0 invalide).
- `backend/tests/unit/test_middleware/test_api_response.py` : corps `{data, pagination}` existant → **pas** de double enveloppement, `message: null` ajouté ; corps liste nue → enveloppé normalement (non-régression STORY-126).

### Intégration API — par endpoint converti (contrat + sécurité)

Fichier : `backend/tests/integration/test_api_pagination.py` — tests paramétrés par endpoint cible :

- `test_2xx_returns_pagination_envelope` : `{data: [...], pagination: {page, per_page, total, pages}}`, `len(data) <= per_page`, `pages == ceil(total/per_page)` ;
- `test_empty_list_page_meta` : liste vide → `total: 0, pages: 0, data: []` ;
- `test_multi_page_consistency` : 25 éléments, per_page=20 → page 1 (20 items) + page 2 (5 items), aucun doublon ni trou (tri stable) ;
- `test_per_page_bounds_422` : `per_page=101` → 422 `VALIDATION_ERROR` (enveloppe erreur spec 09) ; `page=0` → 422 (AC 2) ;
- `test_beyond_last_page_returns_empty` : page = pages+1 → 200 `data: []` ;
- `test_returns_401_without_token` (rules 40 — obligatoire) ;
- `test_returns_403_for_insufficient_role` : organizations → viewer 403, admin/audit → admin 403, admin/stacks → admin 403 (RBAC inchangé — non-régression) ;
- `test_403_for_foreign_resource` : members d'une org non membre, versions d'un stack d'une autre org (isolation conservée) ;
- `test_no_sensitive_fields` : api-keys → pas de `key_hash`/`key` dans `data` ;
- `test_existing_filters_combinable` : schedules `organization_id`, registry `category`/`query`, stacks `include_archived`, audit `user_id`/`since` — filtrage **avant** pagination, `total` filtré exact (AC 3) ;
- `test_multi_org_total_exact` : user membre de 2 orgs avec ressources dans chacune → `total` = somme réelle, pages sans doublon (cible les bugs targets/deployments).

### Intégration — module docker

- Mock daemon (pattern [`test_container_shells.py`](../../backend/tests/unit/test_docker/test_container_shells.py)) : slicing page correct, `total = len(liste)`, per_page>100 → 422 ; endpoints inchangés en dehors du format.

### Frontend (Vitest)

- `tests/unit/services/http.spec.ts` : réponse `{data, pagination}` → `response.data` = liste, `pagination` préservée et accessible ;
- `tests/unit/stores/` (stacks/targets/deployments) : mock axios → store alimenté depuis `body.data`, fallback `items` transition, exposition `total`/`pages` pour l'UI ;
- `tests/unit/views/Stacks.spec.ts` (existant, à adapter) : rendu liste + meta pagination sans régression.

### CLI

- [`test_client_envelope.py`](../../cli/tests/test_client_envelope.py) : unwrap `{data, pagination}` retourne la liste **et** rend `pagination` accessible (nouvelle API) ; commande liste : assemblage multi-pages complet (N > 100 → 2 requêtes, affichage fusionné).

### Commandes de validation

```bash
make backend-test           # dont nouveau test_api_pagination.py
make frontend-test          # stores/http/views
make cli-test
make lint && make typecheck
```

## Notes d'implémentation — Vague 1

### Divergences rencontrées

1. **`List[StackSummaryResponse]`/`OrganizationResponse` en `response_model` → `PaginatedResponse`** : l'analyse demandait un retour `PaginatedResponse` ; le `response_model` des décorateurs a été basculé sur `PaginatedResponse` (schéma spec 09, `data: List[Any]`) pour un OpenAPI cohérent avec le corps réel.
2. **Sérialisation explicite dans les handlers** : les items sont sérialisés via `StackSummaryResponse.model_validate(s).model_dump()` avant insertion dans `PaginatedResponse.data` (le champ `data: List[Any]` ne déclenche pas la validation par attribut de FastAPI) — champs restreints des schémas de listing conservés.
3. **Réparation préexistante `test_stacks_archive.py`** : ce fichier couvre `GET /stacks/` (converti vague 1) mais échouait AVANT la vague (migration enveloppe STORY-126 manquante — itérait `response.json()` nu). Réparé au minimum vital : `unwrap()`/`error_message()` + assertions sur le contrat paginé `body["data"]`/`body["pagination"]`. Les autres échecs préexistants (`test_stack_actions.py` POST /start|stop|redeploy, `test_deployments_api.py::test_delete_deployment`, `test_security_headers.py` — tous cassés pré-STORY-128, prouvés par baseline git stash) sont HORS périmètre vague 1 et n'ont pas été touchés.
4. **Middleware — `message` complété** : conformément à la tâche 2, un corps paginé sans `message` reçoit `message: null` (homogénéité du contrat pour les clients qui lisent la clé sur tout 2xx) ; le `X-API-Message` header interne est ignoré sur les corps paginés (réservé à l'enveloppe standard).

### Fichiers modifiés/créés (vague 1)

- Créés : `backend/app/helper/pagination.py`, `backend/tests/unit/test_helper/__init__.py`, `backend/tests/unit/test_helper/test_pagination.py`, `backend/tests/unit/test_middleware/__init__.py`, `backend/tests/unit/test_middleware/test_api_response.py`, `backend/tests/integration/test_api_pagination.py`
- Modifiés : `backend/app/middleware/api_response.py`, `backend/app/schemas/common.py`, `backend/app/services/stack_service.py`, `backend/app/services/organization_service.py`, `backend/app/services/user_organization_service.py`, `backend/app/api/v1/stacks.py`, `backend/app/api/v1/organizations.py`, `backend/tests/unit/test_stacks_archive.py` (réparation)

### Tests/validation

- Exécuté : `DISABLE_AUTH=false poetry run pytest backend/tests/unit/test_helper backend/tests/unit/test_middleware backend/tests/integration/test_api_pagination.py backend/tests/unit/test_stacks_archive.py` → 55 passed ;
- `DISABLE_AUTH=false poetry run pytest backend/tests/unit backend/tests/integration` → 1798+55 passed / 20 failed préexistants (baseline stashé : 27 failed — aucune régression, 7 réparés) ;
- Note environnement : le `.env` local porte `DISABLE_AUTH=true` qui fait échouer 9 tests préexistants en mode dev-mode (superadmin requis) — lancer avec `DISABLE_AUTH=false` pour la validation.

## Notes d'implémentation — Vague 2 (routers backend restants)

### Divergences rencontrées

1. **Ordre du registry trié par `name`** : l'ordre filesystem YAML n'étant pas
   garanti, un tri stable par nom a été appliqué avant slicing — les
   consommateurs ne peuvent plus dépendre de l'ordre d'inscription.
2. **`AuditLogListResponse`/`DeploymentListResponse` retirés** : les schémas
   de liste intermédiaires (`{items, total, skip, limit}`) ont été supprimés
   au profit du `PaginatedResponse` commun (zéro consommateur restant).

### Fichiers modifiés (vague 2)

- Routers : `backend/app/api/v1/{schedules,plugins,plugin_registry,targets/crud,users,deployments,auth,workflows,docker}.py`, `backend/app/api/v1/admin/{audit,stacks_management}.py`
- Services : `scheduler_service.py`, `plugin_manager_service.py`, `target_service.py`, `user_service.py`, `deployment_service.py`, `api_key_service.py`, `audit_service.py`, `plugin_lifecycle_service.py`, `stack_definitions_loader.py` (COUNT scopusés, tris stables)

## Notes d'implémentation — Vague 3 (clients + CHANGELOG)

### Décisions techniques

1. **CLI — API à deux niveaux** plutôt qu'un flag sur `get()` :
   `get()` reste inchangé (retourne la liste, zéro rupture pour les
   commandes existantes) ; `get_paginated()` (corps brut non déplié via
   `_handle_response(unwrap=False)`, métadonnées normalisées `Dict[str, int]`,
   tolérant aux sources non paginées en déduisant `total=len(liste)`) et
   `get_all()` (boucle `page=1..pages`, `per_page=100` = maximum serveur,
   garde-fou `max_pages=50` contre un serveur incohérent) sont les nouvelles
   primitives de lecture de liste. Les commandes `org list`, `deploy list` et
   `env list` affichent le **total réel** de la collection (« Total: N »)
   au lieu du nombre d'items chargés.
2. **Frontend — pagination rattachée à la réponse axios** : le bloc
   `pagination` est accroché à `response.pagination` via augmentation du
   module `axios` (`AxiosResponse.pagination?: PaginationMeta` — pattern
   officiel, génériques repris de la signature d'origine avec disable ESLint
   justifié). Les stores exposent un `pagination` ref (`null` en fallback
   transition), l'UI peut lire `total`/`pages` sans changer le chargement.
   Fallback de transition conservé **une release** : `Array.isArray(body) ?
   body : body.items ?? []` (types `LegacyListBody<T>`).
3. **Breaking change absorbe `skip/limit` → `page/per_page`** : les 6 APIs de
   liste du `services/api.ts` (users/organizations/targets/stacks/deployments/
   workflows) + `useUsers`/`useOrganizations` (signatures `page`/`perPage`) +
   `RecentDeploymentsWidget` (`per_page: props.limit`) — le backend ignore
   désormais `skip/limit` silencieusement (params inconnus FastAPI).

### Divergences rencontrées

4. **Tests backend legacy non migrés par la vague 2** : le sweep complet a
   révélé 27 échecs en sus de la baseline (tests couvrant l'ancien contrat
   `skip/limit`/`items` : docker pagination ×21, audit ×5, registry ×2, hooks,
   users scoping, deployments rbac/isolation, api_contract, deployments_api).
   Migrés au contrat STORY-128 dans cette vague (AC 4 — non-régression).
5. **Régression camelCase docker images (vague 2)** : la sérialisation
   manuelle `model_dump()` des items images avait perdu les alias camelCase
   (`inUse`, `containersCount`…) du contrat historique STORY-031.1 — corrigé
   par `model_dump(by_alias=True)` (5 tests `test_images_list_in_use`
   rétablis). Idem import `Query` mort dans `docker.py` retiré.
6. **`test_no_key_or_hash_in_logs` (api_key_service)** : échec **préexistant**
   confirmé par baseline git stash (non lié à la pagination — caplog/environnement),
   laissé hors périmètre.

### Fichiers modifiés/créés (vague 3)

- CLI : `cli/client.py` (`PaginatedResult`, `get_paginated`, `get_all`,
  `unwrap` param), `cli/commands/{org,deploy,env}.py` (listes via `get_all`),
  `cli/tests/test_client_envelope.py` (+7 tests STORY-128)
- Frontend : `frontend/src/types/api.ts` (`PaginationMeta`, `PaginatedResponse{data, pagination}`, `LegacyListBody`, augmentation axios), `frontend/src/services/http.ts` (`unwrapResponse` préserve `pagination`), `frontend/src/services/api.ts` (page/per_page), stores `stacks/targets/deployments/workflows.ts` (+`pagination` ref), `frontend/src/composables/{useUsers,useOrganizations}.ts`, `frontend/src/components/dashboard/RecentDeploymentsWidget.vue`
- Tests frontend : `tests/unit/services/http.spec.ts` (+3 tests),
  `tests/unit/stores/pagination.spec.ts` (créé, 5 tests)
- Backend (finalisation) : `backend/app/api/v1/docker.py` (`by_alias=True`),
  10 fichiers de tests migrés au contrat paginé
  (`test_docker_pagination.py` réécrit, `test_images_list_in_use.py`,
  `test_admin_audit.py`, `test_plugin_registry.py`, `test_plugin_hooks.py`,
  `test_users.py`, `test_deployments_rbac.py`, `test_rbac_isolation.py`,
  `test_api_contract.py`, `test_deployments_api.py`)
- Docs : `CHANGELOG.md` (entrée « BREAKING — STORY-128 » sous Unreleased)

### Tests/validation (vagues 2-3)

- CLI : `poetry run pytest cli/tests -v` → **17 passed** (10 existants + 7 nouveaux) ;
- Frontend : `pnpm test` → **918 passed / 57 fichiers** (dont nouveaux `pagination.spec.ts` + http.spec étendu) ; `pnpm type-check` (vue-tsc strict) → 0 erreur ; ESLint/Prettier clean sur les fichiers touchés ;
- Backend : `DISABLE_AUTH=false poetry run pytest backend/tests` → **1807 passed / 12 failed** — les 12 échecs sont **tous préexistants** (baseline git stash vague 1 : `test_stack_actions.py` ×11, `test_deployments_api.py::test_delete_deployment`, `test_api_key_service.py::test_no_key_or_hash_in_logs`) ;
- OpenAPI : génération de la spec vérifiée — 20/20 endpoints de liste avec `page` (default 1), `per_page` (default 20, maximum 100) documentés ;
- Qualité : black + isort appliqués (backend/CLI), flake8 clean sur tous les fichiers touchés (F401 restants préexistants dans `test_auth_isolation.py`, non touché), mypy OK (`cli/client.py`, `docker.py`).
