# EPIC-018 : Documentation exhaustive des endpoints (tags, exemples, badges, échantillons)

**Statut :** TODO
**Priorité :** Haute

## Vision

Porter le contrat OpenAPI de windflow au niveau d'exigence de la règle 20 (« OpenAPI doit rester à jour avec un maximum de documentation, examples ») **sur chaque opération** : résumés, descriptions, exemples par réponse et par champ, tags groupés, badges de module et de sécurité, et échantillons d'utilisation appelables (curl + TypeScript) par endpoint. Fournir également une **documentation d'utilisation de l'API** transverse (authentification, enveloppe, pagination, erreurs, rate limiting) publiée dans `info.description` et rendue comme pages de navigation par Scalar/ReDoc.

Inspiré de previimmo EPIC-003 (« Badges Scalar et exemples d'utilisation des API »), adapté à l'échelle windflow : ~20 routers dans [`backend/app/api/v1/`](../../backend/app/api/v1/) (auth, users, organizations, docker, stacks, deployments, schedules, plugins, plugin_registry, hosts/, ssh_keys, compute, stats, import_export, websockets, system, metrics, discovery, admin/, targets_legacy) — soit plusieurs centaines d'opérations.

## Description

### 1. Socle commun du contrat

- Module `backend/app/core/openapi/tags.py` : registre central des tags (une étiquette par module/router) + groupes `TAG_GROUPS` publiés en `x-tagGroups` (lus par ReDoc et Scalar) ; un module qui monte son routeur déclare son tag dans le même changement (garde-fou par test).
- `generate_unique_id_function` : operationId normalisés `<module>_<nom_de_fonction>` (snake_case strict) — stabilité pour les clients générés.
- Assemblage central dans un `backend/app/core/openapi/document.py` : `_complete_operation()` enrichit chaque opération (en-têtes de corrélation, réponses d'erreur communes) et dérive automatiquement les `x-badges`.

### 2. Badges dérivés automatiquement (`x-badges`)

- Dérivés des déclarations existantes, **jamais saisis en double** : étiquette de module (tag, position `before`) + nature de sécurité (position `after`) — « Publique » (security vide), « JWT » (bearer), « API Key », « JWT ou API Key ».
- Source : `require_role(...)` / `get_current_user` déjà posés sur les endpoints (RBAC effectif, règle 40) ; le badge **affiche, il ne contrôle pas**.
- Champ lu par le bundle Scalar 1.76.4 : `name` (pas `text` — constat de sonde previimmo), à re-vérifier par sonde au moment de l'implémentation.

### 3. Exemples par réponse et par champ (règle 20)

- Chaque contenu de réponse porte un `example` ; chaque champ de schéma porte `description` et, en pratique, `examples=[…]` — les schémas Pydantic existants (`json_schema_extra={"example": ...}`) sont complétés là où c'est absent.
- Chaque opération documente **tous ses codes de réponse réels** (200/201/204/400/401/403/404/409/422…) avec exemples — précède EPIC-019 qui s'en sert comme source du mock.

### 4. Échantillons d'utilisation par opération (`x-codeSamples`)

- Helper `backend/app/core/openapi/code_samples.py` : `code_samples(path, summary, authenticated=False)` produisant au minimum **curl** et **TypeScript** (axios, forme des services windflow) par opération — déclarés à côté des routes ; base d'URL fictive commune, en-têtes d'auth pour les routes protégées, libellés français.
- Test de cohérence : chaque échantillon lié au chemin/paramètres de son opération (anti-dérive).
- Couverture : **toutes** les opérations publiées du contrat (garde-fou par test de complétude sur `app.openapi()`).

### 5. Guide transverse d'utilisation de l'API

- Publié dans `info.description` (mécanisme `load_guides()` d'EPIC-017), couvre les mécanismes transverses avec exemples curl + TypeScript : authentification JWT + refresh + clés API `wf_ak_`, RBAC et codes 401/403, **enveloppe de réponse** (STORY-126 : `data`/`message`/`pagination`), pagination `page`/`per_page`, erreurs typées `WindFlowException`, rate limiting, correlation ID `X-Correlation-ID`, WebSocket (canaux, auth `ensure_role_ws`).
- La couverture par opération reste aux `x-codeSamples` (anti-double-maintenance).

### 6. Documentation hors contrat

- Page `docs/API.md` : point d'entrée humain (URLs des trois interfaces `/docs` `/swagger` `/redoc`, conventions, liens vers le guide transverse).
- Mise à jour de `.roo/rules/20-architecture-and-api.md` via la skill `update-rules` après livraison (nouveaux mécanismes : guides, badges, codeSamples).

## Liste des Stories liées

*À créer ultérieurement via `create-stories`*

- [ ] STORY-XXX : Socle du contrat — tags centralisés + `x-tagGroups`, operationId normalisés, module `document.py` d'enrichissement
- [ ] STORY-XXX : Dérivation automatique des `x-badges` (module + nature de sécurité) + test de cohérence badge ↔ sécurité sur toutes les opérations
- [ ] STORY-XXX : Helper `code_samples` + `x-codeSamples` curl/TypeScript sur les routers cœur (auth, users, organizations, system, docker)
- [ ] STORY-XXX : `x-codeSamples` sur les routers métier (stacks, deployments, schedules, hosts/, ssh_keys, compute, plugins, plugin_registry, stats, import_export, websockets, discovery, admin/, targets_legacy — à découper en sous-stories par lots si besoin)
- [ ] STORY-XXX : Complétude des exemples par réponse et par champ sur les routers (audit + comblement, lots par domaine)
- [ ] STORY-XXX : Guide transverse « Utiliser l'API » (auth, enveloppe, pagination, erreurs, rate limiting, correlation ID, WebSocket) publié dans `info.description`
- [ ] STORY-XXX : Page `docs/API.md` + mise à jour des règles (update-rules) + garde-fous de complétude (test : toute opération a résumé, badges, codeSamples, exemples de réponse)

## Notes de conception

- **Découpage** : le volume (~20 routers, plusieurs centaines d'opérations) impose des stories par lots de routers ; le pipeline `analyse-story` → `split-story` pourra découper davantage.
- **RBAC (règle 40)** : la dérivation des badges s'appuie sur les dépendances `require_role(...)` **déjà** posées (STORY-121/122) — aucun contournement, le contrôle d'accès reste aux `Depends`.
- **Champs sensibles (règle 40)** : les exemples ne contiennent jamais de secrets réels ; les schémas `*Response` excluent déjà password/token (à vérifier par échantillon).
- **Précédent previimmo** : le lecteur « Code Examples » de Scalar 1.76.4 ne rend que la langue active du `x-codeSamples` (sélecteur en haut du bloc) ; alias acceptés `x-code-samples`, `x-custom-examples`, `x-scalar-examples` ; navigation directe par ancre `#tag/<tag>/GET/<chemin>`.
- **Client généré** : les extensions `x-badges`/`x-codeSamples` sont ignorées par les générateurs de clients — aucun effet attendu sur `frontend/src/types/api.ts`, à constater et consigner.
- **Plugins (routes dynamiques)** : les routes dynamiques de plugins héritent du mécanisme via `_complete_operation()` ; leur tag `plugin-{name}` existe déjà (garde-fou présent dans `test_plugin_dynamic_routes.py`).
- **Dépréciations** : les endpoints dépréciés (ex. `/auth/me`, `deprecated: true` posé par STORY) conservent leur documentation mais leurs échantillons pointent vers le remplacement.

## Critères de succès (Definition of Done)

- [ ] Toute opération du contrat a : un résumé non vide, une description, au moins un `example` par contenu de réponse, des `x-badges` non vides cohérents avec sa sécurité, et au moins un `x-codeSamples` (curl + TypeScript)
- [ ] Test de complétude automatisé sur `app.openapi()` : échec si une opération (présente ou future) manque d'un élément
- [ ] `x-tagGroups` publiés ; tout router monté dans `main.py` déclare son tag (garde-fou)
- [ ] Guide transverse « Utiliser l'API » rendu dans Scalar (pages de navigation) avec exemples curl/TypeScript par mécanisme
- [ ] `docs/API.md` publié ; `.roo/rules/20-architecture-and-api.md` synchronisé via `update-rules`
- [ ] `make lint` + `make backend-test-unit` au vert ; aucun effet de régression sur les garde-fous OpenAPI existants (`test_system_endpoints.py`, `test_rate_limiting.py`, `test_deprecation_auth_me.py`, `test_plugin_dynamic_routes.py`)

## Risques

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Volume : plusieurs centaines d'opérations à documenter | Élevé | Stories par lots de routers + `split-story` ; helper commun factorisant la forme des échantillons ; complétude vérifiée par test unique sur `app.openapi()` |
| Dérive badges ↔ sécurité réelle | Moyen | Dérivation depuis la déclaration unique (Depends) + test de cohérence ; badge sans valeur d'autorité |
| Dérive des échantillons quand une route change | Moyen | Test liant chaque échantillon au chemin/paramètres de son opération ; helper commun |
| `x-badges`/`x-codeSamples` non rendus par le bundle épinglé | Moyen | Sonde empirique en premier geste (patron previimmo) ; constat consigné avant montée de version ou réexamen |
| Croissance du temps de génération OpenAPI | Faible | Dérivation au fil de `_complete_operation()` (O(opérations)) ; métrique constatée en recette |

## Dépendances

- **Prérequis** : EPIC-017 (mécanisme des guides `load_guides()`, assets Scalar auto-hébergés pour la recette du rendu).
- **Prérequis de** EPIC-019 : le bac à sable sert les exemples documentés par cette epic.
- Existant mobilisé : RBAC `require_role(...)`/`ensure_role_ws` (règle 40), enveloppe STORY-126, pagination `PaginationQuery` (STORY-127), schémas Pydantic par domaine, `PluginApiRouterService` (invalidation cache OpenAPI).
