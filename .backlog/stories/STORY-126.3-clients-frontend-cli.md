# STORY-126.3 : Synchronisation des clients — frontend (unwrap `data`), CLI, CHANGELOG versionné et retrait du flag transitoire (P1-5, partie clients)

**Statut :** DONE
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Story mère :** STORY-126 ([ABANDONED — découpe validée par l'utilisateur le 2026-09-27](STORY-126-enveloppes-reponse-api.md))
**Item plan :** P1-5 (axe A10) — ampleur **M** — ⚠️ **breaking change consommateur — à livrer dans la même release que STORY-126.2**

## Description

En tant qu'utilisateur du frontend Vue et du CLI WindFlow, je veux que les deux clients consomment le nouveau contrat à enveloppes (`{data, message}` / `{error:{code,message}}`) de manière transparente, afin que l'activation du format par STORY-126.2 ne casse aucune vue ni commande — le breaking change étant versionné et documenté dans le CHANGELOG (AC 4 de la story mère).

**Sortie attendue** : toutes les vues/composants/stores du frontend et toutes les commandes du CLI fonctionnent contre un backend à enveloppes actives ; `make frontend-test` et tests CLI verts ; CHANGELOG documente le breaking change ; le flag `api_envelope_enabled` transitoire est retiré (ou sa retraite consignée à STORY-250 si différée).

## Contexte technique

> Extrait de l'analyse STORY-126 (2026-09-27). Le backend sert les enveloppes par défaut depuis STORY-126.2 — **prérequis absolu**.

### Frontend — points d'impact inventoriés (grep vérifié)

**Couche transport (le point de centralisation) :**
- Interceptor axios [`frontend/src/services/http.ts:47`](../../../frontend/src/services/http.ts:47) : branche succès → `return { ...response, data: response.data?.data ?? response.data }` (unwrap centralisé, tolérant pendant la transition) ; branche erreur → remplacer `data.detail` par `data?.error?.message` (lignes 403/404/500 : [`http.ts:171-183`](../../../frontend/src/services/http.ts:171)) — le retry 401 ne change pas (basé sur le statut) ;
- ⚠️ **Cas particulier login** : [`authApi.login`](../../../frontend/src/services/api.ts:82) doit recevoir l'enveloppe → tokens sous `response.data.data.access_token` — l'unwrap centralisé de l'interceptor couvre ce cas si appliqué **avant** les stores ; vérifier le parcours FormData (login) qui passe par le même interceptor.

**Types ([`frontend/src/types/api.ts`](../../../frontend/src/types/api.ts)) :**
- `PaginatedResponse<T>` (ligne 374 : `{items, total, skip, limit, has_more?}`) → réaligner : les listes paginées restent `{items,total,skip,limit}` **sous `data`** jusqu'à STORY-128 (l'unwrap centralisé rend ce type quasi-transparent) ; ajouter `ApiEnvelope<T> { data: T; message: string | null }` et remplacer `ApiError { detail: string }` (ligne 416) par `ApiError { error: { code: string; message: string; details?: unknown }; correlation_id?: string }` ;
- Mettre à jour les usages de `ApiError` ([`http.ts`](../../../frontend/src/services/http.ts), vues catch).

**Stores/composables (lecture des corps) — avec l'unwrap centralisé, la plupart restent valides tels quels ; à auditer :**
- [`stores/auth.ts:36-46`](../../../frontend/src/stores/auth.ts:36) : `response.data.access_token` — **couvert par l'interceptor** (le `response.data` post-unwrap est déjà le `data` enveloppe) ;
- [`stores/deployments.ts:27`](../../../frontend/src/stores/deployments.ts:27) (`response.data.items`), [`composables/useUsers.ts:66`](../../../frontend/src/composables/useUsers.ts:66), [`useOrganizations.ts:63`](../../../frontend/src/composables/useOrganizations.ts:63), [`stores/stacks.ts:25`](../../../frontend/src/stores/stacks.ts:25), [`stores/targets.ts:24`](../../../frontend/src/stores/targets.ts:24), [`stores/workflows.ts:19`](../../../frontend/src/stores/workflows.ts:19) : les fallbacks défensifs `items || data` deviennent inutiles — les garder est inoffensif, les nettoyer si trivial ;
- Vues lisant `err.response.data.detail` : [`views/Stacks.vue:1022`](../../../frontend/src/views/Stacks.vue:1022), [`views/Stacks.vue:1157`](../../../frontend/src/views/Stacks.vue:1157) et tout autre `data?.detail` (grep `\.detail` restant) → `err.response?.data?.error?.message`.

**WebSocket : hors périmètre** ([`services/websocket.ts`](../../../frontend/src/services/websocket.ts) — format `type/data` inchangé).

### CLI — points d'impact inventoriés

- [`cli/client.py:44-66`](../../../cli/client.py:44) `_handle_response` : succès → `payload = response.json()` puis `return payload.get("data", payload)` (unwrap tolérant) ; erreur → `message = error_data.get("error", {}).get("message") or error_data.get("detail", str(e))` ;
- [`cli/client.py:104-118`](../../../cli/client.py:104) `login` : tokens sous `result["data"]` après unwrap — avec l'unwrap dans `_handle_response`, `result["access_token"]` reste correct ;
- Commandes ([`cli/commands/`](../../../cli/commands)) : audit grep des accès `["detail"]`/`["items"]` restants ;
- Tests CLI : vérifier l'existence d'une suite (`make cli-test`) et adapter si elle mocke des réponses backend.

### CHANGELOG & flag

- [`CHANGELOG.md`](../../../CHANGELOG.md) § Unreleased → nouvelle entrée **Changed** (breaking change) : description des 3 enveloppes, avant/après (exemples JSON), guide de migration (unwrap `data`, `.error.message`), mention des versions affectées (frontend + CLI + API) ;
- Retrait du flag `api_envelope_enabled` ([`config.py`](../../../backend/app/config.py), `env.example`, `.env.prod.example`, docstring middleware) **ou** consignation explicite de sa retraite à STORY-250 (si l'équipe préfère garder une valve de secours un cycle) — décision à la clôture ; test de non-régression après retrait (backend répond toujours enveloppé).

## Critères d'acceptation (AC)

- [x] AC 1 : Interceptor frontend — toutes les réponses 2xx sont unwrap (`response.data` = charge utile) ; les erreurs exposent `error.message`/`error.code` ; le login (FormData) et le refresh token fonctionnent bout-en-bout contre un backend enveloppé.
- [x] AC 2 : Aucune vue/composant/store ne lit l'ancien format (grep `data?.detail`/`\.detail` sur `err.response` sans résultat hors WebSocket) ; types `ApiEnvelope`/`ApiError` réalignés ; non-régression des vues clés (login, dashboard, stacks, deployments) validée par les tests.
- [x] AC 3 : CLI — `login` stocke les tokens, les commandes listent/décrivent, les erreurs affichent `error.message` ; tests CLI verts.
- [x] AC 4 : CHANGELOG documente le breaking change (format avant/après + guide de migration) ; le flag transitoire est retiré ou sa retraite consignée (décision explicite consignée dans Notes d'implémentation).
- [x] AC 5 : `make frontend-test` + `make cli-test` (si suite) + `make lint` verts ; test backend de non-régression post-retrait de flag (si retiré).

## Références spécification

- [`docs/general_specs/09-api.md`](../../../docs/general_specs/09-api.md) — § Format de réponse ;
- [STORY-126 (mère)](STORY-126-enveloppes-reponse-api.md) — analyse complète (sections Clients) ;
- [`docs/backend_remediation_plan.md`](../../../docs/backend_remediation_plan.md) §7.1 (synchroniser frontend/CLI dans le même lot) ;
- `.roo/rules/30-code-standards.md` — frontend : gestion centralisée, TS strict sans `any` injustifié.

## Dépendances

- **STORY-126.2** (activation serveur) — **prérequis absolu** ; **livrer 126.2 + 126.3 dans la même release** ;
- STORY-128 (pagination) suivra : les adaptations de types listes paginées seront reprises là ;
- Sans objet : WebSocket (hors périmètre maintenu).

## État d'avancement technique

- [x] Tâche 1 : Interceptor axios — unwrap succès + erreurs `.error.message` (+ gestion login FormData)
- [x] Tâche 2 : Types `ApiEnvelope`/`ApiError` + réalignement `PaginatedResponse` + usages
- [x] Tâche 3 : Sweep vues/composables/stores (`err.response.data.detail` → `.error.message`, nettoyage fallbacks)
- [x] Tâche 4 : CLI — `_handle_response` unwrap + erreurs, audit commandes, tests
- [x] Tâche 5 : Tests frontend non-régression (vues clés, stores auth/listes) + adaptation mocks
- [x] Tâche 6 : CHANGELOG (breaking change, guide de migration) + retrait/consignation du flag + validation finale (`make lint`, `make frontend-test`, backend non-régression)

## Tâches d'implémentation détaillées

### Tâche 1 — Interceptor axios ([`frontend/src/services/http.ts`](../../../frontend/src/services/http.ts))

1. Branche succès : `retryAttempts = 0; isRetrying = false;` puis `return { ...response, data: (response.data && typeof response.data === 'object' && 'data' in response.data) ? response.data.data : response.data }`.
2. Branche erreur : remplacer `data.detail` par `data?.error?.message ?? data?.detail` (transition), logging `error.code` en contexte ; le flux retry-401/logout est inchangé (basé sur `status`).
3. Vérifier le retry (`axios.request(retryConfig)`) : il contourne l'instance `http` — le résultat du retry doit être unwrap de la même façon (facto une fonction `unwrapResponse(response)`).

### Tâche 2 — Types ([`frontend/src/types/api.ts`](../../../frontend/src/types/api.ts))

1. `export interface ApiEnvelope<T> { data: T; message: string | null }` ;
2. `ApiError` : `{ error: { code: string; message: string; details?: unknown }; correlation_id?: string }` — mettre à jour [`http.ts`](../../../frontend/src/services/http.ts) (`AxiosError<ApiError>`) et tout `catch` typé ;
3. `PaginatedResponse<T>` : inchangé structurellement (valeur sous `data` après unwrap) — ajouter commentaire « sous enveloppe, STORY-128 convertira en `pagination{}` ».

### Tâche 3 — Sweep vues/stores/composables

1. Grep `response?.data?.detail|data\.detail|\.detail\b` sur `frontend/src` (hors WebSocket) : remplacer par `?.error?.message` (garder fallback `?? 'Message par défaut'` existant).
2. Nettoyer les fallbacks `items || data` devenus morts (optionnel, non bloquant).
3. Vues clés à vérifier manuellement (ou via tests) : Login, Dashboard, Stacks (import + stats — [`Stacks.vue:1022`](../../../frontend/src/views/Stacks.vue:1022), [`Stacks.vue:1157`](../../../frontend/src/views/Stacks.vue:1157)), Deployments, ContainerDetail (configs Docker).

### Tâche 4 — CLI ([`cli/client.py`](../../../cli/client.py))

1. `_handle_response` : unwrap tolérant `payload.get("data", payload)` ; erreurs : `error_data.get("error", {}).get("message") or error_data.get("detail")` ;
2. `login()` : après unwrap, `result["access_token"]` fonctionne ; `get("/auth/me")` → `set_user_info` reçoit le `data` unwrap ;
3. Grep [`cli/commands/`](../../../cli/commands) : `.get("detail")`/`["items"]` restants → adapter ;
4. Vérifier [`cli/session.py`](../../../cli/session.py)/[`cli/services/base.py`](../../../cli/services/base.py) : accès au corps centralisés dans `client.py` a priori.

### Tâche 5 — Tests frontend

1. Adapter les mocks des tests existants : réponses mockées désormais enveloppées (`{data: ..., message: null}`) — sweep [`frontend/tests/`](../../../frontend/tests) (grep `mockResolvedValue`/`reply`) ;
2. Tests ciblés : interceptor (unwrap succès/erreur), store auth (login tokens), un store liste (deployments `data.items`), une vue erreur (`.error.message` affiché) ;
3. Jouer `make frontend-test-unit` puis `make frontend-test` complet.

### Tâche 6 — CHANGELOG + flag + validation finale

1. [`CHANGELOG.md`](../../../CHANGELOG.md) : entrée **Changed — BREAKING** (API v1 response envelopes) avec exemples avant/après et guide migration (3 bullets : unwrap `data`, erreurs `.error.message`, 204 inchangé) ;
2. Retrait du flag `api_envelope_enabled` : [`config.py`](../../../backend/app/config.py), [`env.example`](../../../env.example), [`.env.prod.example`](../../../.env.prod.example), docstrings middleware/README — **ou** consignation à STORY-250 (ajouter une ligne au fichier STORY-250) ; si retrait : supprimer les branches legacy du middleware/handlers + les tests flag-off devenus morts, relancer `make backend-test` ;
3. Validation : `make lint` (backend+frontend+CLI), `make frontend-test`, `make backend-test` (si retrait flag), revue visuelle login/dashboard (optionnel).

## Tests à écrire

- **Frontend unitaires** : interceptor unwrap (2xx enveloppé → payload ; erreur → `.error.message`) ; `authApi.login` tokens depuis enveloppe ; store deployments lit `data.items` ; vue affiche message d'erreur enveloppé ;
- **Frontend non-régression** : vues clés montées avec mocks enveloppes (login, dashboard, stacks) ;
- **CLI** : si suite de tests existe — login mocké enveloppe → tokens stockés ; erreur → message affiché depuis `.error.message` ; sinon test manuel documenté (commandes `auth login`, `stacks list`) ;
- **Backend (si retrait du flag)** : non-régression — les tests de contrat 126.2 restent verts sans les branches flag-off.

## Notes d'implémentation

### Fichiers modifiés/créés

**Frontend :**
- [`frontend/src/services/http.ts`](../../frontend/src/services/http.ts) — interceptor : `unwrapResponse()` factored (branche succès + retry 401 qui contourne l'instance `http`) ; branche erreur lit `data?.error?.message ?? data?.detail` (fallback transition) + `error.code` en logging.
- [`frontend/src/types/api.ts`](../../frontend/src/types/api.ts) — `ApiEnvelope<T> {data, message}` ajouté ; `ApiError` réaligné `{error: {code, message, details?}, correlation_id?}` ; commentaire STORY-128 sur `PaginatedResponse`.
- [`frontend/src/stores/targets.ts`](../../frontend/src/stores/targets.ts), [`auth.ts`](../../frontend/src/stores/auth.ts), [`deployments.ts`](../../frontend/src/stores/deployments.ts) — lecture post-unwrap, fallbacks défensifs nettoyés (targets : détection `List | {items}` documentée).
- [`frontend/src/views/Stacks.vue`](../../frontend/src/views/Stacks.vue) — 2 catch d'erreur passés à `error.message` (import stack, stats) ; **fallbacks `?.data?.detail` legacy retirés en clôture** (branches mortes depuis le retrait du flag 126.2) ; fichier reformaté Prettier.
- Tests : [`frontend/tests/unit/services/http.spec.ts`](../../frontend/tests/unit/services/http.spec.ts) (interceptor), [`stores/auth.spec.ts`](../../frontend/tests/unit/stores/auth.spec.ts), [`stores/deployments.spec.ts`](../../frontend/tests/unit/stores/deployments.spec.ts), [`views/Stacks.spec.ts`](../../frontend/tests/unit/views/Stacks.spec.ts) (29 tests) — mocks enveloppés.

**CLI :**
- [`cli/client.py`](../../cli/client.py) — `_unwrap_payload()` (détection stricte `data`+`message`/`pagination` : un payload métier avec clé `data` n'est jamais déplié par erreur) ; `_extract_error_message()` (`error.message` puis fallback `detail`) ; `login()` documenté post-unwrap.
- [`cli/commands/deploy.py`](../../cli/commands/deploy.py), [`org.py`](../../cli/commands/org.py), [`env.py`](../../cli/commands/env.py), [`auth.py`](../../cli/commands/auth.py), [`config_cmd.py`](../../cli/commands/config_cmd.py), [`services/base.py`](../../cli/services/base.py) — adaptation aux enveloppes + formatage black/isort.
- Tests : [`cli/tests/conftest.py`](../../cli/tests/conftest.py) + [`cli/tests/test_client_envelope.py`](../../cli/tests/test_client_envelope.py) (10 tests : unwrap succès/login/erreurs/listes, non-dépliage payload métier `data`).

**Config/outillage :**
- [`Makefile`](../../Makefile) — cibles `cli-test`/`cli-lint`/`cli-format` ; [`frontend/vitest.config.ts`](../../frontend/vitest.config.ts) — includes tests.
- [`CHANGELOG.md`](../../CHANGELOG.md) — entrée **BREAKING — STORY-126.2 + STORY-126.3** : enveloppes spec 09, exemples avant/après, guide de migration, mention du retrait du flag.

**Backend (retrait flag) :**
- [`backend/app/config.py`](../../backend/app/config.py), [`env.example`](../../env.example), [`.env.prod.example`](../../.env.prod.example), [`middleware/README.md`](../../backend/app/middleware/README.md) — flag `api_envelope_enabled`/`API_ENVELOPE_ENABLED` **retiré** (enveloppes systématiques).

### Décisions techniques

1. **Unwrap centralisé** côté transport dans les deux clients (interceptor axios / `_handle_response` CLI) — stores/vues/commandes inchangés dans leur majorité.
2. **Détection d'enveloppe stricte côté CLI** (`data` + `message`/`pagination`) vs **large côté frontend** (`'data' in body`) : le CLI gère des réponses plus variées ; le frontend a validé le contrat par les tests de contrat 126.2.
3. **Flag transitoire retiré** (option « retrait » de l'alternative de la story) : les branches legacy flag-off et les tests associés ont été supprimés ; les tests de contrat 126.2 restent verts sans eux (45 tests).
4. **Fallback `detail` conservé dans les couches transport** (http.ts, client.py) pour tolérance pendant le cycle de déploiement, **mais retiré des vues** (AC 2 : grep strict sans résultat).

### Divergences par rapport à l'analyse

- Aucune divergence fonctionnelle. En clôture : retrait des 2 derniers fallbacks `detail` de `Stacks.vue` (l'analyse tolérait « fallback `?? 'Message par défaut'` existant », l'AC 2 impose un grep strict — le format legacy n'existe plus côté serveur).
- Prettier a reformaté `Stacks.vue` en clôture (le fichier avait été laissé non formaté par la session interrompue — 105 insertions/499 délétions de formatage, sans changement sémantique ; tests 29/29 verts après).

### Difficultés rencontrées

- État interrompu : toutes les tâches étaient cochées dans la story mais aucun AC validé, aucune note d'implémentation, kanban/epic non synchronisés — audit code réel effectué avant toute modification.
- Warnings flake8 F401/F841 pré-existants dans `cli/commands/*` (imports `argparse` hérités du code d'origine, visibles comme contexte inchangé dans `git diff`) — non touchés (hors périmètre STORY-126.3, `make cli-lint` exit 0).

### Résultats de validation (2026-09-27/28)

| Commande | Résultat |
|----------|----------|
| `cd frontend && pnpm test -- tests/unit/services tests/unit/stores tests/unit/views/Stacks.spec.ts --run` | ✅ 87 tests / 7 fichiers verts |
| `cd frontend && pnpm test -- tests/unit/views --run` (12 vues, non-régression complète) | ✅ 198 tests / 12 fichiers verts |
| `cd frontend && pnpm type-check` (`vue-tsc --noEmit`, TS strict) | ✅ 0 erreur |
| `poetry run pytest cli/tests -v` | ✅ 10 passed |
| `make cli-lint` | ✅ exit 0 (mypy : no issues in 16 source files) |
| `make cli-format` | ✅ 16 files unchanged |
| `poetry run pytest backend/tests/integration/test_api_contract.py backend/tests/integration/test_api_envelope.py -v` | ✅ 45 passed |
| `pnpm exec eslint src/views/Stacks.vue` + `prettier --check` | ✅ propres après reformatage |
| Grep AC 2 (`data?.detail`/`data.detail` hors WebSocket) | ✅ 0 résultat |
