# STORY-124.3 : Endpoints `/auth/api-keys` et auth par clé dans `get_current_user`

**Statut :** DONE
**Story Parente :** STORY-124 — Clés API `wf_ak_` — table `api_keys`, auth `X-API-Key` coexistant avec JWT (P1-3, partie clés API)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'utilisateur de WindFlow, je veux gérer mes clés API via des endpoints REST dédiés — `POST /auth/api-keys` (retourne la clé complète **une seule fois** à la création), `GET /auth/api-keys` (liste sans jamais exposer clé ni hash), `DELETE /auth/api-keys/{id}` (révocation) — et être authentifié par ma clé via le header `X-API-Key` (ou `Authorization: Bearer wf_ak_…`) sur toutes les routes API protégées, **coexistant avec la voie JWT** et portant les permissions RBAC de mon compte, afin de scripter la CLI et les intégrations tierces sans manipuler de JWT courts.

Troisième étape de STORY-124 (découpe proactive : 7 tâches / 8 fichiers) : consomme le modèle (STORY-124.1) et le service/schemas/génération (STORY-124.2) ; démontre les AC 1 et 2 de bout en bout et couvre l'AC 3 ; les tests transverses de sécurité sont consolidés par STORY-124.4.

## Critères d'acceptation (AC)

- [x] AC 3 : **Révocation immédiate** : `DELETE /auth/api-keys/{id}` → les requêtes suivantes avec cette clé → `401` ; `GET /auth/api-keys` liste les clés (nom, dates, statut) **sans exposer** clé, hash ni secret.

> **Note de découpe :** cette sous-story couvre l'AC 3 en intégralité (endpoints + démonstration de la révocation immédiate). Elle démontre également de bout en bout l'AC 1 (génération `wf_ak_` + affichage unique au POST — implémenté par 124.2/124.3) et l'AC 2 (auth via `X-API-Key`/Bearer + RBAC propriétaire + `last_used_at`) ; les tests sécurité systématiques exigés par l'AC 4 sont portés par STORY-124.4.

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-13) — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches.

**Couches impactées :** Backend uniquement — endpoints auth, dépendance `get_current_user`, tests API. Aucun impact frontend/CLI (explicitement hors périmètre de STORY-124).

**Spécifications de référence :**
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Authentification : `POST /auth/api-keys` (affichage unique de la clé complète), `GET /auth/api-keys` (liste sans jamais la clé ni son hash), `DELETE /auth/api-keys/{id}` (révocation) ; Bearer JWT ou `wf_ak_` ;
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Validation des tokens dans l'API (JWT ou clé API, header `X-API-Key`) ;
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — la matrice s'applique à l'identique après auth par clé.

**Disponible en entrée (posé par STORY-124.1/.2) :**
- Modèle `APIKey` (table `api_keys`) + migration `1241_api_keys` ;
- `generate_api_key()` + constantes `API_KEY_PREFIX`/`MAX_API_KEY_LENGTH` dans `jwt.py` ;
- Schemas `APIKeyCreate` / `APIKeyCreated` / `APIKeyResponse` (jamais `key_hash`) ;
- `ApiKeyService` (`create`, `list_for_user`, `revoke` idempotent scoped, `verify` → `User`, `last_used_at` throttlé) ;
- `InvalidApiKeyError` (401 générique anti-énumération).

**Fichiers de référence (patterns validés par STORY-123.3) :**
- Endpoints → pattern [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py) : docstring OpenAPI riche, `conditional_rate_limiter`, mapping exception métier → 401 générique (`from None`) ;
- Dépendance auth → [`backend/app/auth/dependencies.py`](../../backend/app/auth/dependencies.py) (`get_current_user` ligne ~23 : voies JWT + dev mode `disable_auth`) ;
- RBAC → [`backend/app/auth/rbac.py`](../../backend/app/auth/rbac.py) : `require_role(...)` s'exécute **après** résolution utilisateur — aucun changement requis, la clé porte les permissions de son propriétaire ;
- Tests API → pattern [`backend/tests/unit/test_api/test_auth_refresh_security.py`](../../backend/tests/unit/test_api/test_auth_refresh_security.py) : fixture `_jwt_mode` (monkeypatch `disable_auth=False`), 401 paramétrés, isolation multi-users.

**Exigences sécurité (Phase 2.6 de l'analyse) :**
- `get_current_user` doit lire `X-API-Key` **ou** `Authorization: Bearer wf_ak_…` **avant** la voie JWT ; une clé préfixée `wf_ak_` n'est **jamais** soumise au décodeur JWT ;
- utilisateur désactivé → 401 (refus déjà garanti par `ApiKeyService.verify`) ; mode `disable_auth` inchangé ;
- RBAC : une clé porte les permissions de son propriétaire — viewer par clé sur endpoint modifiant → 403 (garanti par `require_role`, aucun changement) ;
- révocation immédiate : vérification en base à chaque requête (pas de cache long sur les clés) ;
- isolation : liste/révocation scoped `user_id == current_user.id` — clé étrangère → 404 (ne pas révéler l'existence) ;
- audit : logs `api_key.created / revoked / auth_failed` avec `user_id` + `key_id` uniquement (posés par STORY-124.2 — ne pas logger d'avantage ici) ;
- rate limiting : `conditional_rate_limiter` sur POST/DELETE `/auth/api-keys` (pattern `auth.py`).

## ⚖️ Arbitrage applicable (découpe proactive, validé le 2026-09-13)

**Clés expirées listées dans `GET /auth/api-keys`** : le GET conserve les clés expirées avec `expires_at` visible ; `revoked` distinct de l'expiration (une clé expirée reste `revoked=false` et n'est plus authentifiante depuis `verify` — STORY-124.2).

## Dépendances

- STORY-124.1 : Modèle `APIKey` et migration Alembic.
- STORY-124.2 : `ApiKeyService`, schemas, `generate_api_key()`, `InvalidApiKeyError`.
- Réutilise : STORY-122 (`require_role` — inchangé), STORY-120 (Alembic — head `1241`).
- Bloque : STORY-124.4.

## Tâches d'implémentation détaillées

### Tâche 1 : Endpoints `/auth/api-keys` dans `api/v1/auth.py`
**Objectif :** Exposer la gestion des clés API — création avec affichage unique, liste sans secrets, révocation scoped — avec OpenAPI documenté et rate limiting.
**Fichiers :**
- `backend/app/api/v1/auth.py` — Modifier — Ajouter trois endpoints (pattern docstring OpenAPI + `conditional_rate_limiter` + mapping exceptions) :
  - `POST /auth/api-keys` — dépendance `get_current_active_user` ; body `APIKeyCreate` ; appelle `ApiKeyService.create` ; retourne **201** + `APIKeyCreated` (clé brute **une seule fois** — avertissement dans la docstring OpenAPI) ; `conditional_rate_limiter` ; 401 sans auth ; 422 body invalide (validation Pydantic) ;
  - `GET /auth/api-keys` — dépendance `get_current_active_user` ; appelle `ApiKeyService.list_for_user` ; retourne `list[APIKeyResponse]` — **jamais** `key_hash` ni `key` ; **les clés expirées restent listées** (`expires_at` visible, `revoked` distinct) ; 401 sans auth ;
  - `DELETE /auth/api-keys/{key_id}` — dépendance `get_current_active_user` ; `key_id: str` en path ; appelle `ApiKeyService.revoke` ; retourne `APIKeyResponse` (état révoqué) ; `NotFoundError` → **404** (clé étrangère ou inexistante — sans révéler laquelle) ; `conditional_rate_limiter` ; idempotent par clé déjà révoquée (comportement service).
  - Contrainte : aucun log d'endpoint ne doit contenir la clé brute ou son hash (les logs `api_key.*` du service suffisent).
**Exigences sécurité :** Affichage unique (201 uniquement) ; exposition contrôlée par les schemas (jamais `key_hash`) ; isolation scoped user (404 sur clé étrangère) ; rate limiting POST/DELETE.
**Dépend de :** STORY-124.2

### Tâche 2 : Auth par clé dans `get_current_user` (`dependencies.py`)
**Objectif :** Accepter l'authentification par clé API (`X-API-Key` ou `Bearer wf_ak_…`) en amont de la voie JWT, sans régresser JWT ni mode dev.
**Fichiers :**
- `backend/app/auth/dependencies.py` — Modifier — Dans `get_current_user` (et uniquement là — ne pas toucher `require_role` ni `rbac.py`) :
  - ordre de résolution : (1) mode `disable_auth` → comportement actuel inchangé ; (2) header `X-API-Key` présent **ou** `Authorization: Bearer wf_ak_…` (préfixe `API_KEY_PREFIX`) → `ApiKeyService.verify(db, key)` → `User` ou `InvalidApiKeyError` → **401 générique** (`from None` — pas de divulgation du motif) ; (3) sinon → voie JWT existante à l'identique ;
  - garantir qu'une valeur préfixée `wf_ak_` n'est **jamais** soumise au décodeur JWT (garantie structurelle de l'ordre de résolution) ;
  - `last_used_at` est alimenté par `verify` (throttlé — STORY-124.2) sans bloquer la réponse ;
  - l'utilisateur résolu par clé suit exactement le même chemin que par JWT (statut, `get_current_active_user`, `require_role` — la clé porte les permissions du propriétaire ; viewer par clé sur endpoint modifiant → 403 sans changement de code).
**Exigences sécurité :** 401 générique anti-énumération ; utilisateur désactivé → 401 ; révocation immédiate (vérification en base à chaque requête) ; aucun changement RBAC ; mode dev `disable_auth` inchangé.
**Dépend de :** STORY-124.2, Tâche 1 (tests croisés)

### Tâche 3 : Tests des endpoints et de l'auth par clé
**Objectif :** Couvrir les endpoints (201+affichage unique, liste sans secrets, révocation immédiate, 404 isolation) et la coexistence clé/JWT dans `get_current_user`.
**Fichiers :**
- `backend/tests/unit/test_api/test_api_keys.py` — Créer — Pattern `test_auth_refresh_security.py` : fixture `_jwt_mode` (monkeypatch `disable_auth=False`), auth par JWT pour gérer les clés, puis appels avec la clé. Détail en section « Tests à écrire ». Les tests sécurité transverses systématiques (RBAC viewer par clé, logs, etc.) sont consolidés dans STORY-124.4.
**Exigences sécurité :** 401 sans auth ; 422 body invalide ; 404 clé étrangère ; clé jamais rejouée après révocation.
**Dépend de :** Tâche 1, Tâche 2

## Tests à écrire

### Backend — API (endpoints)
- `backend/tests/unit/test_api/test_api_keys.py`
  - `test_create_api_key_returns_201_with_key_once` — 201 + `APIKeyCreated` ; la clé `wf_ak_…` (48 car.) apparaît **uniquement** dans cette réponse ; `GET` ultérieur ne la montre plus
  - `test_create_api_key_invalid_body_422` — `name` vide/>100 chars, `expires_at` invalide → 422
  - `test_create_api_key_requires_auth_401` — sans token/clé → 401
  - `test_list_api_keys_no_secrets` — 200 ; liste `APIKeyResponse` sans `key_hash` ni `key` ; champs nom/dates/statut présents
  - `test_list_api_keys_keeps_expired` — clé expirée toujours listée avec `expires_at` visible et `revoked=false`
  - `test_list_api_keys_scoped_404_isolation` — un user ne liste que ses clés ; DELETE de la clé d'un autre user → 404
  - `test_revoke_then_key_unauthorized_401` — DELETE → requête suivante avec cette clé → 401 (révocation immédiate)
  - `test_auth_via_x_api_key_header` — `X-API-Key: wf_ak_…` authentifie sur une route protégée (200)
  - `test_auth_via_bearer_wf_ak` — `Authorization: Bearer wf_ak_…` authentifie (200)
  - `test_invalid_or_expired_key_401` — clé inconnue/invalide/révoquée/expirée → 401 (paramétré)
  - `test_jwt_still_works_alongside_api_key` — auth JWT existante non régressée (200 sans clé)
  - `test_disabled_user_key_401` — clé d'un utilisateur `is_active=False` → 401
  - `test_last_used_at_updated_on_request` — requête authentifiée par clé → `last_used_at` alimenté (visible via GET)

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_api/test_api_keys.py -v
poetry run pytest backend/tests/unit/test_api/test_auth_refresh_security.py -v  # non-régression auth JWT
make backend-lint && make backend-typecheck
```

## État d'avancement technique
- [x] Tâche 1 : Endpoints POST/GET/DELETE `/auth/api-keys`
- [x] Tâche 2 : Auth par clé dans `get_current_user` (`X-API-Key` / `Bearer wf_ak_…`)
- [x] Tâche 3 : Tests endpoints + coexistence clé/JWT

## Notes d'implémentation

**Date :** 2026-09-16 (reprise et validation d'une session interrompue)

### État initial trouvé (session interrompue)
Tâches 1 et 2 déjà implémentées sur disque (fichiers non-trackés git, conformes à la story ligne à ligne) et fichier de tests déjà écrit mais **jamais exécuté**. Statut story déjà `IN_PROGRESS`, kanban déjà en 🏗️ IN PROGRESS `[~]`. Session terminée par : correction d'une régression induite par la Tâche 2, exécution des tests, garde-fou routes, lint, clôture.

### Fichiers modifiés/créés
- `backend/app/api/v1/auth.py` — **Tâche 1** : 3 endpoints `POST/GET/DELETE /auth/api-keys` (docstrings OpenAPI riches avec examples, `conditional_rate_limiter(10, 60)` sur POST/DELETE, `get_current_active_user`, 201 + `APIKeyCreated` affichage unique, `NotFoundError` → 404 sans oracle d'existence). Reformaté par black en clôture.
- `backend/app/auth/dependencies.py` — **Tâche 2** : voie clé API dans `get_current_user` (ordre : `disable_auth` → `X-API-Key`/`Bearer wf_ak_…` → JWT) + **fix de clôture** : paramètre `x_api_key` migré en `Annotated[Optional[str], Header(alias="X-API-Key")] = None` (voir divergences).
- `backend/tests/unit/test_api/test_api_keys.py` — **Tâche 3** : 15 tests (13 listés dans la story + `test_revoke_idempotent` + `test_revoke_unknown_key_404`), fixture `_jwt_mode` (pattern 123.4), mint direct JWT pour éviter le quota rate-limit login.
- `backend/tests/unit/test_api/test_rbac_exhaustivite.py` — garde-fou §2.G : `EXPECTED_ROUTE_COUNTS["auth"]` 5 → 8 (les 3 routes `/api-keys`, protégées `get_current_active_user`).

### Décisions techniques
- **Réutilisation stricte du socle 124.1/124.2** : les endpoints ne font qu'orchestrer `ApiKeyService` (create/list_for_user/revoke/verify) — zéro logique métier côté HTTP, aucun log d'endpoint (les events `api_key.*` du service suffisent).
- **Discriminateur Bearer** : `token.startswith(API_KEY_PREFIX)` résolu **avant** la voie JWT — garantie structurelle qu'une valeur `wf_ak_` n'atteint jamais le décodeur JWT.
- **404 sans oracle** : `NotFoundError` du service (clé inexistante OU étrangère, indifférenciées) mappée en 404 générique `from None`.
- **Pas d'ajout à `PUBLIC_PATHS`** du garde-fou RBAC : les 3 routes sont protégées (test 1 d'exhaustivité passé sans changement de liste blanche).

### Divergences par rapport à l'analyse
- **Tâche 2 (fix complémentaire)** : la signature initiale posée par la session interrompue utilisait `x_api_key: Optional[str] = Header(None, alias="X-API-Key")` (valeur par défaut = objet `Header`, truthy). Les appels **directs** Python de `get_current_user` (tests 123.x `test_dev_mode`) recevaient alors l'objet `Header` non résolu → déviation vers la voie clé API → `AttributeError` (régression détectée par la non-régression). Correctif : métadonnées dans `Annotated[...]`, défaut Python `= None` réel — comportement FastAPI identique, appels directs restaurés. (Note : pydantic v2 interdit `Header(None, ...)` dans `Annotated` — default uniquement via `=`.)
- **Garde-fou routes** : mise à jour `auth: 5 → 8` dans `EXPECTED_ROUTE_COUNTS` — mécanisme prévu par le test lui-même pour tout ajout explicite de routes (les 3 endpoints sont un choix de la story, pas un effet de bord).

### Difficultés rencontrées
- **Piège environnement `DISABLE_AUTH=true` confirmé** (`.env` racine) : neutralisé par `DISABLE_AUTH=false` en tête de commande + fixture `_jwt_mode` (double sécurité).
- **Piège environnement supplémentaire découvert** : `LOG_LEVEL` par défaut `INFO` → logger `sqlalchemy.engine` en INFO → le test 124.2 `test_no_key_or_hash_in_logs` voit le hash dans les **logs SQL** (paramètres bindés), échec environnemental sans lien avec la story → neutralisé par `LOG_LEVEL=WARNING` en tête de commande (même stratégie).
- **Couverture** : le rapport `term-missing` sous-trace certaines frames async (ex. `except NotFoundError` → 404 rapporté non couvert alors que le body de réponse `{"detail": "API key not found"}` prouve l'exécution). Couverture fonctionnelle vérifiée empiriquement ; chiffres mesurés : `schemas/api_key.py` 100 %, `api_key_service.py` 99 % (seule ligne 119 `_as_utc` tzinfo None non atteinte, hors périmètre 124.3).

### Tests ajoutés et résultats
- `backend/tests/unit/test_api/test_api_keys.py` : **15/15 passés** (`DISABLE_AUTH=false LOG_LEVEL=WARNING .venv-test/bin/pytest tests/unit/test_api/test_api_keys.py -v`).
- Non-régression auth JWT (commande de la story) : `test_auth_refresh_security.py` **8/8 passés**.
- Non-régression backend unitaire complète : `tests/unit/` **1476/1476 passés** (après fix `Annotated` + garde-fou routes 5→8).
- Lint ciblé : black ✓ (2 fichiers reformatés en clôture), isort ✓, flake8 ✓.
- mypy ciblé : **0 erreur sur les fichiers de la story** (19 erreurs préexistantes : stubs `jose`/`psutil` absents du venv-test + `connectivity.py` préexistant).
- Commande de référence : `cd backend && DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest tests/unit/test_api/test_api_keys.py -v`
