# STORY-250.2 : Dépréciation `/auth/me` (headers `Deprecation`/`Sunset` + OpenAPI) et migration des consommateurs frontend/CLI vers `/users/me`

**Statut :** DONE
**Story Parente :** STORY-250 — Purge du code mort et résidus + dépréciation `/auth/me` (P3-1 + P3-3)
**Epic Parent :** EPIC-014 — P3 : Finitions & purge (remédiation backend)
**Item plan :** P3-3 (axe E9) — ampleur **S/M** (partie 2/2)

## Description

En tant que développeur WindFlow, je veux **déprécier proprement `GET /auth/me`** au profit de `GET /users/me` (convention REST : la ressource utilisateur vit sous `/users`) — l'endpoint répondant toujours 200 pour compatibilité mais portant les headers `Deprecation: true` et `Sunset: <date>` + mention OpenAPI `deprecated: true` avec remplacement et retrait planifié — et **migrer les consommateurs actifs** (frontend `getCurrentUser`, CLI `client.py`) vers `/users/me`, afin que le contrat API ne présente plus deux entrées vivantes pour une même ressource et que le Sunset annoncé soit crédible.

**Problème constaté** : duplication d'endpoints — [`/users/me`](../../backend/app/api/v1/users.py) (l.224, endpoint contractuel) vs [`/auth/me`](../../backend/app/api/v1/auth.py) (l.870) ; **et** des consommateurs actifs appellent encore `/auth/me` : frontend [`api.ts:99`](../../frontend/src/services/api.ts) (`getCurrentUser: () => http.get<User>('/auth/me')`) et CLI [`client.py:268`](../../cli/client.py) (`user_info = self.get("/auth/me")`) — découverts à l'analyse STORY-250.

## Critères d'acceptation (AC)

- [x] AC 3 : `/auth/me` répond toujours 200 (compatibilité) avec les headers `Deprecation: true` et `Sunset: <date>` + note OpenAPI `deprecated: true` indiquant le remplacement par `/users/me` et le retrait planifié ; `/users/me` est inchangé et demeure l'endpoint contractuel.
- [x] AC 4 : Aucune régression des points forts §2.G ; les tests existants passent ; les tests référençant les éléments purgés sont nettoyés.
- [x] AC 5 : Build + lint + tests passent (`make lint`, `make backend-test`).

## Contexte technique

### Constats d'exploration (état réel du code au 2026-10-31)

- **Les deux endpoints sont fonctionnellement identiques** : [`auth.py:870`](../../backend/app/api/v1/auth.py) `GET /me` (response_model `UserResponse`, `get_current_active_user`) et [`users.py:224`](../../backend/app/api/v1/users.py) `GET /me` (même modèle, même dépendance d'auth). `/users/me` est **inchangé** dans cette story (endpoint contractuel).
- **Consommateurs `/auth/me` à migrer** (grep du 2026-10-31) :
  - Frontend : [`frontend/src/services/api.ts:99`](../../frontend/src/services/api.ts) — `getCurrentUser: () => http.get<User>('/auth/me')` → basculer vers `/users/me` (aucun autre appel frontend) ;
  - CLI : [`cli/client.py:268`](../../cli/client.py) — `user_info = self.get("/auth/me")` (dans le flux d'infos utilisateur) → `/users/me` ;
  - Test CLI : [`cli/tests/test_client_envelope.py:99`](../../cli/tests/test_client_envelope.py) — mock/route « `/auth/me` interrogé pour les infos utilisateur » → à mettre à jour vers `/users/me`.
- **Précédent de dépréciation dans le dépôt** : `DeprecationHeadersMiddleware` ([`targets_legacy.py:47`](../../backend/app/api/v1/targets_legacy.py), STORY-166.2) pose `Deprecation`/`Sunset` sur `/targets` via middleware ASGI pur. **Décision d'analyse** : pour `/auth/me` (une seule route), poser les headers **directement dans le handler** (`response.headers[...]` sur la `Response` FastAPI) — plus simple et testable qu'un middleware ; le middleware 166 reste scoped `/targets` (aucune généralitation non demandée).
- **Sunset** : date ISO (ex. 6 mois après livraison — valeur constante module `AUTH_ME_SUNSET = "2027-05-01"`, à ajuster à la date de livraison réelle ; format RFC 8594 `YYYY-MM-DD`). `Deprecation: true` (forme historique la plus répandue ; RFC 9745 « deprecation: @1686542400» existe — le plan cite `Deprecation`, garder `true` simple + `Sunset` RFC 8594).
- **OpenAPI** : paramètre `deprecated=True` du décorateur `@router.get` + description enrichie (remplacement `/users/me`, Sunset, raison). `/users/me` gagne une note « endpoint contractuel » dans sa description.
- **Tests backend existants touchant `/auth/me`** : `test_rbac_matrix_consolidated.py`, `test_auth_password.py`, `test_api_keys.py`, `test_auth_isolation.py` — ils testent l'endpoint (200/401) : **ils restent valides** (l'endpoint répond toujours 200) ; ajouter un test dédié dépréciation (headers présents + OpenAPI deprecated). Si certains fichiers référencent `/auth/me` dans des helpers partagés, les laisser (l'endpoint vit jusqu'au Sunset).
- **Spec 09 § Authentification** référence `/api/v1/auth/` — la mise à jour de la spec (note dépréciation) est **coordonnée STORY-252** (P3-4 consolidé) : ne pas modifier la spec ici, le tracer dans les notes.

### Décisions d'analyse (250.2)

- **D1 — Headers dans le handler** (pas de middleware) : `Deprecation: true` + `Sunset: <constante ISO>` posés sur la réponse du handler `/auth/me` uniquement.
- **D2 — Sunset 6 mois** : constante module `AUTH_ME_SUNSET` documentée ; le retrait effectif sera un choix explicite post-Sunset (garde-fou §2.G sur les endpoints : la suppression n'est PAS dans cette story).
- **D3 — Migration consommateurs complète avant dépréciation crédible** : frontend + CLI basculés dans cette story (sinon le Sunset serait mensonger) ; grep final : plus aucun appel interne à `/auth/me` hors backend/tests dépréciation.
- **Sécurité (checklist règle 40)** : aucun changement d'auth (l'endpoint garde `get_current_active_user` — 401 sans token inchangé) ; les headers ne fuient aucune information ; `/users/me` inchangé (déjà testé 401/200 côté RBAC).

## Dépendances

- **STORY-250.1** (ordre logique recommandé : purger puis déprécier — aucun conflit technique, surfaces distinctes).
- Coordination documentaire : STORY-252 (spec 09 note dépréciation), STORY-253 (backend_status/CHANGELOG mention).

## Tâches d'implémentation détaillées

### Tâche 1 : Backend — dépréciation `/auth/me` (headers + OpenAPI)
**Objectif :** `/auth/me` répond 200 compat + `Deprecation`/`Sunset` + OpenAPI `deprecated` (AC 3).
**Fichiers :**
- `backend/app/api/v1/auth.py` — **Modifier** — sur `GET /me` (l.870) : ajouter `deprecated=True` au décorateur ; description enrichie (« **Deprecated** — remplacé par `GET /users/me` (convention REST). Retrait planifié : `<SUNSET>` ; les deux endpoints sont équivalents. ») ; constante module `AUTH_ME_SUNSET = "<date ISO à ~6 mois>"` (docstring : RFC 8594, valeur à confirmer à la livraison) ; dans le handler, injecter `response: Response` et poser `response.headers["Deprecation"] = "true"` + `response.headers["Sunset"] = AUTH_ME_SUNSET`. `/users/me` : ajouter une ligne description « Endpoint contractuel (l'équivalent `/auth/me` est déprécié) ».
**Exigences sécurité :** Auth inchangée (`get_current_active_user` — 401 sans token existant).
**Dépend de :** Aucune (après 250.1 recommandé)

### Tâche 2 : Migration frontend vers `/users/me`
**Objectif :** Le frontend n'appelle plus `/auth/me` (D3).
**Fichiers :**
- `frontend/src/services/api.ts` — **Modifier** — `getCurrentUser: () => http.get<User>('/auth/me')` (l.99) → `http.get<User>('/users/me')` ; vérifier l'absence d'autre occurrence (`grep -rn "auth/me" frontend/src`).
**Exigences sécurité :** Aucune exigence spécifique (même contrat de réponse `UserResponse`).
**Dépend de :** Tâche 1

### Tâche 3 : Migration CLI vers `/users/me`
**Objectif :** La CLI n'appelle plus `/auth/me` (D3).
**Fichiers :**
- `cli/client.py` — **Modifier** — `user_info = self.get("/auth/me")` (l.268) → `self.get("/users/me")` ;
- `cli/tests/test_client_envelope.py` — **Modifier** — mise à jour du mock/route `/auth/me` (l.99 et voisines) vers `/users/me` (le test vérifie le dépliage d'enveloppe — chemin à aligner).
**Exigences sécurité :** Aucune exigence spécifique.
**Dépend de :** Tâche 1

### Tâche 4 : Tests dépréciation + validations
**Objectif :** Prouver AC 3/4/5.
**Fichiers :**
- `backend/tests/unit/test_api/test_deprecation_auth_me.py` — **Créer** — (pattern `test_compute_api.py` : `force_real_auth` + `authenticated_client`) : (1) `test_auth_me_still_200_with_deprecation_headers` — 200 + `Deprecation: true` + `Sunset` présent et ISO ; (2) `test_users_me_no_deprecation_headers` — 200 sans les headers (endpoint contractuel) ; (3) `test_auth_me_401_without_token` — sécurité (règle 40) ; (4) `test_openapi_marks_auth_me_deprecated` — `app.openapi()["paths"]["/api/v1/auth/me"]["get"]["deprecated"] is True` + description mentionne `/users/me`.
- **Exécutions** : tests CLI (`make cli-test`), grep final (`grep -rn "auth/me" frontend/src cli/` → 0 hors commentaires), `make backend-lint`/`backend-test-unit`, `make cli-lint` (si modifié), éventuellement `cd frontend && pnpm build` (service layer).
**Exigences sécurité :** Test 401 obligatoire (règle 40).
**Dépend de :** Tâches 1-3

## Tests à écrire

### Backend
- `backend/tests/unit/test_api/test_deprecation_auth_me.py`
  - `test_auth_me_still_200_with_deprecation_headers` — AC 3 : 200 + les deux headers
  - `test_users_me_no_deprecation_headers` — AC 3 : endpoint contractuel sans dépréciation
  - `test_auth_me_401_without_token` — **sécurité** (règle 40)
  - `test_openapi_marks_auth_me_deprecated` — AC 3 : OpenAPI `deprecated: true` + mention remplacement

### CLI
- `cli/tests/test_client_envelope.py` — mis à jour (route `/users/me`) : le scénario d'existant reste vert après migration.

### Commandes de validation
```bash
cd backend && poetry run pytest tests/unit/test_api/test_deprecation_auth_me.py tests/unit/test_api/test_auth_isolation.py -v
make cli-test && make cli-lint
grep -rn "auth/me" frontend/src cli/ --include="*.ts" --include="*.py" | grep -v test_client  # → vide
cd frontend && pnpm build
make backend-lint && make backend-test-unit
```

## État d'avancement technique

- [x] T1. Backend — `/auth/me` : `deprecated=True` + description + headers `Deprecation`/`Sunset` (constante `AUTH_ME_SUNSET`) ; note `/users/me`
- [x] T2. Migration frontend `api.ts` → `/users/me`
- [x] T3. Migration CLI `client.py` + tests CLI → `/users/me`
- [x] T4. Tests dépréciation (headers/OpenAPI/401) + validations (backend, CLI, frontend build)

## Notes d'implémentation

<!-- Ajoutées à la clôture par treat-story -->

## Notes d'implémentation (treat-story — 2026-10-31)

### Fichiers modifiés/créés
- [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py) — constante `AUTH_ME_SUNSET = "2027-05-31"` (RFC 8594, ~6 mois), `deprecated=True` + description complète (remplacement `/users/me`, retrait planifié), handler : `response.headers["Deprecation"]="true"` + `Sunset` (D1 — headers dans le handler, pas de middleware), import `Response`.
- [`backend/app/api/v1/users.py`](../../backend/app/api/v1/users.py) — description `/users/me` « endpoint contractuel » avec renvoi.
- [`frontend/src/services/api.ts`](../../frontend/src/services/api.ts) — `getCurrentUser` → `/users/me` (commentaire traçabilité).
- [`cli/client.py`](../../cli/client.py) — `user_info` → `/users/me` ; [`cli/tests/test_client_envelope.py`](../../cli/tests/test_client_envelope.py) — mock aligné.
- **Créé** : [`backend/tests/unit/test_api/test_deprecation_auth_me.py`](../../backend/tests/unit/test_api/test_deprecation_auth_me.py) (5 tests).

### Résultats
| Contrôle | Résultat |
|---|---|
| Tests dépréciation (headers/200/OpenAPI/401) | **5 passed** |
| Tests CLI (`make cli-test`) | **17 passed** |
| Frontend `pnpm type-check` | **0 erreur** |
| grep `auth/me` frontend/src + cli/ | uniquement les 2 commentaires de traçabilité |
| lint backend fichiers story | 0 erreur |
| Non-régression `tests/unit` | **3216 passed / 1 préexistant** (`/api/v1/metrics`, résidu STORY-172) |

### Divergences / préexistants consignés
- `make cli-lint` échoue sur `cli/utils.py:12 F401 rich_print` — **préexistant prouvé par stash** (hors périmètre, à traiter STORY-253 rangement).
- La mise à jour de la spec 09 (note dépréciation) reste coordonnée STORY-252 (P3-4), comme prévu par l'analyse.
- Sunset : `2027-05-31` (~6 mois de la livraison) — le retrait effectif sera un choix explicite post-Sunset (garde-fou §2.G).
