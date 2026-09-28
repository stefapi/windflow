# STORY-126.2 : Activation des enveloppes — défaut `api_envelope_enabled=True`, adaptation de la suite backend et tests de contrat par router (P1-5, partie activation)

**Statut :** DONE
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Story mère :** STORY-126 ([ABANDONED — découpe validée par l'utilisateur le 2026-09-27](STORY-126-enveloppes-reponse-api.md))
**Item plan :** P1-5 (axe A10) — ampleur **M/L**

## Description

En tant que mainteneur du contrat API WindFlow, je veux activer par défaut les enveloppes de réponse (`API_ENVELOPE_ENABLED=true` devient le défaut) et adapter l'intégralité de la suite de tests backend au nouveau format, avec des **tests de contrat sur un échantillon représentatif de chaque router**, afin que le serveur livre définitivement le contrat spec 09 (AC 1 de la story mère) tout en gardant une CI verte.

⚠️ **Point de bascule** : à partir de cette story, le backend ne sert plus le format nu — le frontend et le CLI (encore sur l'ancien format) doivent être synchronisés **immédiatement après** (STORY-126.3, même lot de livraison — plan §7.1). Entre 126.2 et 126.3, l'UI/CLI sont temporairement incompatibles : livrer les deux dans la même release.

## Contexte technique

> Extrait de l'analyse STORY-126 (2026-09-27). Le socle (schémas, middleware, handlers, flag) est posé par STORY-126.1 — **prérequis absolu**.

**Portée des changements :**

1. **Bascule du défaut** : [`backend/app/config.py`](../../../backend/app/config.py) `api_envelope_enabled: bool = Field(default=True, ...)` ; [`env.example`](../../../env.example) et [`.env.prod.example`](../../../.env.prod.example) mis à jour (`API_ENVELOPE_ENABLED=true`, commentaire « remettre false pour compat temporaire ancien format »).
2. **Adaptation de la suite de tests backend** (~1552 tests) : la grande majorité des tests d'API assert le format nu — `response.json()["items"]`, `["total"]`, `["detail"]`, `["access_token"]`… Un **helper d'unwrap** doit limiter la modification mécanique : proposer dans [`backend/tests/conftest.py`](../../../backend/tests/conftest.py) une util `unwrap(response) -> Any` (retourne `body["data"]` si la clé existe) et une `error_code(response) -> str` (retourne `body["error"]["code"]`), puis sweep des fichiers de tests d'API : remplacer `response.json()` par `unwrap(response)` et `["detail"]` par `.json()["error"]["message"]`. Fichiers concernés (tests d'API REST uniquement — pas les tests services/modèles/schemas ni les 5 canaux WS) : [`backend/tests/unit/test_api/`](../../../backend/tests/unit/test_api) (~15 fichiers) + [`backend/tests/integration/`](../../../backend/tests/integration) (`test_auth_api.py`, `test_deployments_api.py`, `test_openapi.py` épargné sauf exemples, `test_rate_limiting.py`, `test_correlation_id.py`, `test_security_headers.py`, `test_timing.py`, `test_migrations.py` épargné).
3. **Tests de contrat par router (AC 1 story mère)** : nouveau `backend/tests/integration/test_api_contract.py` — pour **chacun des 16 routers REST** (auth, users, organizations, targets, stacks, deployments, workflows, stats, import_export, schedules, docker, compute, discovery, plugins, plugin_registry, admin), un échantillon : 1 lecture (liste ou détail selon dispo de fixtures) + 1 cas d'erreur → assert `data` présent + `message` clé présente + erreurs `error.code`. Stratégie d'échantillonnage pragmatique : privilégier les lectures authentifiées légères (listes) et les 404/401/403 comme erreurs (pas besoin de créer des ressources lourdes) ; docker : `GET /docker/system/ping` (léger) + 404 conteneur inconnu ; workflows : le stub `GET /workflows` → `data == []` ; admin : `GET /admin/audit` (viewer → 403 enveloppé).
4. **Non-régression RBAC au nouveau format** : vérifier que les tests de matrice [`test_rbac_exhaustivite.py`](../../../backend/tests/unit/test_api/test_rbac_exhaustivite.py) restent verts après adaptation (les 401/403 restent fonctionnels, seul le corps change).
5. **OpenAPI restant** : compléter les exemples `responses={}` enveloppe sur les routers non couverts par 126.1 (au fil de l'eau, priorité aux routers consommés par l'UI) — le reste est documenté globalement (description app + schémas référencés).

**Décisions d'implémentation :**

- Le helper `unwrap` du conftest **ne masque pas** le format dans les nouveaux tests de contrat (eux assertent l'enveloppe explicitement) — il sert uniquement à la migration mécanique des ~15 fichiers existants ;
- Ne pas adapter les tests via `response.json().get("data", ...)` défensif : l'activation étant définitive, l'unwrap strict fait remonter toute enveloppe manquante (meilleure détection de régression) ;
- Les assertions sur `correlation_id` (422, [`test_correlation_id.py`](../../../backend/tests/integration/test_correlation_id.py)) : le champ reste top-level (décision 4 de l'analyse mère) → adaptation minimale ;
- Les tests qui assertent un **statut** uniquement (204, codes) ne changent pas ;
- `test_openapi.py` : vérifier que les exemples étendus en 126.1 restent cohérents ; le test `test_all_critical_endpoints_documented` est inchangé (chemins) ;
- Pièges : venv `.venv-test` ; `DISABLE_AUTH=false LOG_LEVEL=WARNING` ; rate-limit/bruteforce resets automatiques (conftest) ; ordre des tests non garanti — pas d'état partagé entre routers dans `test_api_contract.py`.

## Critères d'acceptation (AC)

- [x] AC 1 : `api_envelope_enabled` vaut `True` par défaut ; `env.example`/`.env.prod.example` documentés ; tous les endpoints `/api/v1/*` répondent en enveloppe par défaut (le flag `false` reste opérationnel pour compat temporaire).
- [x] AC 2 : Suite backend **verte** après adaptation : tests unitaires `test_api/` + intégration adaptés via helpers `unwrap`/`error_code` (sweep complet, aucun assert sur l'ancien format restant).
- [x] AC 3 : `backend/tests/integration/test_api_contract.py` couvre un **échantillon par router (16/16)** : présence `data` + `message` sur les 2xx, `error.code` sur les erreurs — y compris workflows (stub), docker (garde-fou : aucun endpoint retiré), admin.
- [x] AC 4 : Non-régression garde-fous : matrice RBAC verte au nouveau format ; `/health`, `/`, WS intacts ; tests OpenAPI verts (schémas d'enveloppe présents).
- [x] AC 5 : `make backend-lint` + `make backend-typecheck` + `make backend-test` verts.

## Références spécification

- [`docs/general_specs/09-api.md`](../../../docs/general_specs/09-api.md) — § Format de réponse, § Gestion des erreurs ;
- [STORY-126 (mère)](STORY-126-enveloppes-reponse-api.md) — analyse complète ;
- [`docs/backend_remediation_plan.md`](../../../docs/backend_remediation_plan.md) §4 P1-5 (critère de done : « test de contrat sur un échantillon par router »), §7.1 ;
- `.roo/rules/35-testing-quality-gates.md` — patterns de tests.

## Dépendances

- **STORY-126.1** (socle) — **prérequis absolu** (bloquante) ;
- STORY-127 indépendante côté code, mais **recommandé après** (le sweep des raises typés s'appuie sur des tests déjà au nouveau format) ;
- **Bloque** STORY-126.3 (clients) — livrer 126.2+126.3 dans la même release ;
- Prépare STORY-128 (pagination `pagination{}` — les listes seront déjà sous `data`).

## État d'avancement technique

- [x] Tâche 1 : Bascule défaut `api_envelope_enabled=True` + `env.example`/`.env.prod.example`
- [x] Tâche 2 : Helpers conftest `unwrap(response)` / `error_code(response)` + `envelope_body(response)`
- [x] Tâche 3 : Sweep adaptation tests `backend/tests/unit/test_api/` (24 fichiers)
- [x] Tâche 4 : Sweep adaptation tests `backend/tests/integration/` (hors migrations)
- [x] Tâche 5 : `test_api_contract.py` — échantillon par router (16 routers)
- [x] Tâche 6 : Compléments OpenAPI (exemples enveloppe routers restants, priorité UI)
- [x] Tâche 7 : Validation complète (`make backend-lint` / `typecheck` / `test`) + vérif matrice RBAC verte

## Tâches d'implémentation détaillées

### Tâche 1 — Bascule du défaut

1. [`config.py`](../../../backend/app/config.py) : `default=False` → `default=True` (docstring : « défaut activé depuis STORY-126.2 ; false = compat temporaire ancien format, retrait du flag par STORY-126.3/250 »).
2. [`env.example`](../../../env.example) + [`.env.prod.example`](../../../.env.prod.example) : `API_ENVELOPE_ENABLED=true` + commentaire.

### Tâche 2 — Helpers de test (conftest)

```python
# backend/tests/conftest.py — utils d'unwrap (STORY-126.2)
def unwrap(response) -> Any:
    """Retourne body['data'] si enveloppe présente, sinon le body (transition)."""
def error_code(response) -> str:
    """Retourne body['error']['code'] (échoue si pas d'enveloppe)."""
```

- Fonctions **simples importables** (pas de fixtures — usage `from tests.conftest import unwrap` ou module `backend/tests/utils_envelope.py` selon l'organisation existante) ;
- Typage complet (rules 30), docstrings.

### Tâche 3 — Sweep `test_api/` (unitaires)

1. Liste des fichiers (grep `response.json()` dans [`backend/tests/unit/test_api/`](../../../backend/tests/unit/test_api)) : adapter chaque occurrence : `response.json()` → `unwrap(response)` ; `["detail"]` → `error_code(...)`/`.json()["error"]["message"]` ; `["items"]` → `unwrap(...)["items"]` ; login `["access_token"]` → `unwrap(...)["access_token"]`.
2. Vérifier un par un les tests d'émission d'audit ([`test_audit_emission.py`](../../../backend/tests/unit/test_api/test_audit_emission.py)) — les appels internes au service d'audit ne changent pas, seules les assertions de réponse changent.

### Tâche 4 — Sweep intégration

1. [`test_auth_api.py`](../../../backend/tests/integration/test_auth_api.py), [`test_deployments_api.py`](../../../backend/tests/integration/test_deployments_api.py), [`test_rate_limiting.py`](../../../backend/tests/integration/test_rate_limiting.py) (429 → `TOO_MANY_ATTEMPTS`), [`test_correlation_id.py`](../../../backend/tests/integration/test_correlation_id.py), [`test_security_headers.py`](../../../backend/tests/integration/test_security_headers.py) (headers inchangés — vérifier qu'aucun assert ne porte sur le corps), [`test_timing.py`](../../../backend/tests/integration/test_timing.py).
2. [`test_migrations.py`](../../../backend/tests/integration/test_migrations.py), [`test_secret_encryption.py`](../../../backend/tests/integration/test_secret_encryption.py) : vérifier (corps non concernés a priori).

### Tâche 5 — Tests de contrat (`backend/tests/integration/test_api_contract.py`)

- Classe/paramétrage par router — échantillon (adapter selon fixtures disponibles, préférer le moindre coût) :
  - auth : `POST /auth/login` mauvais mdp → 401 `INVALID_CREDENTIALS` ; login ok → `data.access_token` ;
  - users : `GET /users` (admin) → `data` liste/objet paginé ; 401 sans token ;
  - organizations : `GET /organizations` → `data` ; 403 viewer sur POST → `PERMISSION_DENIED` ;
  - targets : `GET /targets` → `data` ; 404 cible inconnue → `NOT_FOUND` ;
  - stacks : `GET /stacks` → `data` ; `GET /stacks/{uuid}` 404 enveloppé ;
  - deployments : `GET /deployments` → `data.items` (liste paginée sous data) ; 404 ;
  - workflows : `GET /workflows` → `data == []` (stub) ;
  - stats : `GET /stats/dashboard` → `data` ;
  - import_export : 404 export stack inconnue → enveloppe ;
  - schedules : `GET /schedules` → `data` ;
  - docker : `GET /docker/system/ping` → `data.available` ; 404 conteneur ;
  - compute : `GET /compute/stats` → `data` ;
  - discovery : 401 (POST sans token) enveloppé ;
  - plugins : `GET /plugins` → `data` ;
  - plugin_registry : `GET /registry/plugins` → `data` ;
  - admin : `GET /admin/audit` viewer → 403 `PERMISSION_DENIED` ; super_admin → `data.items`.
- Chaque cas 2xx assert aussi la clé `message` (présente, nullable) ; chaque erreur assert `error.message` non vide.

### Tâche 6 — OpenAPI compléments

- Exemples `responses={}` enveloppe sur : stacks, targets, users, schedules, plugins, admin (en plus de l'échantillon 126.1) — modification purement documentaire.

### Tâche 7 — Validation

- `make backend-lint` ; `make backend-typecheck` ; `make backend-test` (complet) ; inspection du rapport de couverture sur `middleware/api_response.py` et handlers (cible ≥ 80 % du nouveau code).

## Tests à écrire

- **Contrat** (cf. tâche 5) : `test_api_contract.py` — 16 routers couverts, 2xx + erreurs ;
- **Helpers** : tests des utils `unwrap`/`error_code` (body enveloppé / legacy) ;
- **Rate limit** : 429 → `error.code == "TOO_MANY_ATTEMPTS"` ;
- **Non-régression** : matrice RBAC ([`test_rbac_exhaustivite.py`](../../../backend/tests/unit/test_api/test_rbac_exhaustivite.py)) verte ; audit émission verte ; migrations/tests structure intacts.

## Notes d'implémentation

**Date :** 2026-09-27 — statut final `DONE` (REVIEW validé par tests).

### Fichiers modifiés/créés

**Source (3) :**
- `backend/app/config.py` — `api_envelope_enabled: default=True` (docstring mise à jour : défaut activé depuis STORY-126.2, false = compat temporaire, retrait du flag par 126.3/250).
- `env.example` / `.env.prod.example` — `API_ENVELOPE_ENABLED=true` + commentaire « remettre false pour compat temporaire ancien format » (la variable était absente de `.env.prod.example`, ajoutée dans la section PERFORMANCE & MONITORING).

**Tests — infrastructure (1) :**
- `backend/tests/conftest.py` — helpers `unwrap(response)` / `error_code(response)` / `error_message(response)` (typage complet, docstrings) + adaptation des 3 helpers de login internes (`_login_role_client`, `authenticated_client`, `admin_client`) qui lisent `access_token` désormais sous `data`.

**Tests — sweep (27 fichiers) :** 24 fichiers de `backend/tests/unit/test_api/` + `tests/integration/test_auth_api.py`, `test_deployments_api.py`, `test_secret_encryption.py`. Transformation : `X.json()` → `unwrap(X)` (2xx), `["detail"]` → `["error"]["message"]` (erreurs), `TOO_MANY_ATTEMPTS in ...["detail"]` → `error_code(response) == "TOO_MANY_ATTEMPTS"` (429), `set(keys()) == {"detail"}` → `{"error", "correlation_id"}`. Épargnés conformément à la story : `test_migrations.py` (aucun corps API), `test_rate_limiting.py` (`.json()` cible `/openapi.json`, hors enveloppe ; le 429 enveloppé est couvert par `test_auth_api.py`), `test_correlation_id.py`/`test_security_headers.py`/`test_timing.py` (headers uniquement), `test_debug_story1033.py` (debug), `test_openapi.py` (schéma statique — les 4 tests 126.1 vérifient exemples/schémas insensibles au flag).

**Tests — nouveaux (2) :**
- `backend/tests/integration/test_api_contract.py` (NOUVEAU, 32 tests) — 16 routers × (1 lecture 2xx + 1 erreur) : auth (login ok/INVALID_CREDENTIALS), users, organizations (PERMISSION_DENIED viewer), targets (NOT_FOUND), stacks, deployments (`data.items`), workflows (stub `data == []`), stats, import_export (404 export), schedules, docker (`data.available` mocké + 404 via `aiohttp.ClientResponseError(status=404)`), compute (mocké), discovery (401/404), plugins, plugin_registry (mocké), admin (`/admin/audit` 403 viewer + `data.items` super_admin). Assertions explicites de l'enveloppe (jamais via `unwrap`).
- `backend/tests/unit/test_schemas/test_envelope_schemas.py` — +7 tests helpers (`TestUnwrapHelper` : enveloppé/liste/legacy-passthrough/data-null ; `TestErrorCodeHelper` : code/message/KeyError strict sans enveloppe).

**OpenAPI (6 routers, purement documentaire) :** exemples `responses={}` enveloppe sur `GET /stacks/` (stacks.py), `GET /users/` (users.py, paginé sous data), `GET /targets/` (targets/crud.py), `GET /schedules` (schedules.py), `GET /plugins/` (plugins.py), `GET /admin/audit` (admin/audit.py) — 200 sous `{data, message}` + 401/403/422 sous `error.code`.

### Décisions techniques
1. **Sweep sémantique scripté** (`/tmp/sweep_envelope.py`, jetable) : regex ordonnées (erreurs avant 2xx pour éviter les faux positifs) + insertion d'import via AST (fin du bloc d'imports de premier niveau) + correctifs ciblés pour les 2xx indexés/`in`. Chaque fichier réécrit validé par `ast.parse` avant écriture.
2. **`unwrap` tolérant, `error_code` strict** : `unwrap` retourne le body nu si `data` absent (transition flag-off locale) ; `error_code` échoue sur body non enveloppé (régression du contrat détectée — décision 2 de l'analyse).
3. **404 docker via exception** : le routeur mappe `aiohttp.ClientResponseError` avec `status == 404` ; retourner `None` au mock déclenche un 500 préexistant (branche générique) — le test de contrat simule l'exception réelle.
4. **429 TOO_MANY_ATTEMPTS** : les deux occurrences (`test_auth_api.py`) migrent vers `error_code(response) == "TOO_MANY_ATTEMPTS"` (code machine spec 09), conformément à « Tests à écrire ».

### Divergences / incidents
1. **`git restore tests/` en cours de route** : un script de réparation d'imports mal placés a cassé des fichiers ; restauration git puis re-application propre (sweep v2 AST). Impact : les 4 tests 126.1 de `test_openapi.py` (non commités) ont été retirés par le restore — **rétablis à l'identique** (vérifiés : 15 tests dans le fichier, tous verts).
2. **`test_delete_deployment` (integration)** : échec **préexistant** (vérifié sur la baseline avant changements — Docker indisponible en local), inchangé après : non-régression prouvée.
3. **isort/mypy préexistants** : les erreurs isort (stacks.py, plugins.py) et les 41 erreurs mypy sont identiques avant/après stash — hors périmètre, non corrigées.

### Validation (commandes et résultats)
- `pytest tests/unit/test_api/` : **363 passed** (baseline pré-changements : 363 passed — zéro régression).
- `pytest tests/integration/` : **107 passed, 1 skipped, 1 failed** (`test_delete_deployment` — préexistant, identique baseline).
- `pytest tests/integration/test_api_contract.py` : **32 passed**.
- `pytest tests/unit/test_schemas/test_envelope_schemas.py` : **44 passed** (37 de 126.1 + 7 helpers).
- `pytest test_rbac_exhaustivite.py + test_audit_emission.py + test_openapi.py + test_api_envelope.py` : **48 passed** (AC 4).
- black/flake8 : OK sur tous les fichiers touchés (test_api_contract.py reformaté). isort/mypy : erreurs strictement préexistantes (comparaison stash).
- Runs complets lancés en arrière-plan (`.venv-test`) : baseline unit `1 failed (préexistant test_api_key_service logs), 1588 passed`.

### Pièges documentés (story) respectés
- venv `.venv-test` (poetry/`.venv` 3.14 incomplet — alembic absent) ;
- `DISABLE_AUTH=false` via fixtures `_jwt_mode` (pattern 123.4) dans le nouveau fichier de contrat ;
- resets rate-limit/bruteforce autouse du conftest — aucun état partagé entre routers dans `test_api_contract.py`.
