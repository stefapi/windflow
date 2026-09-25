# STORY-124.4 : Tests transverses et sécurité des clés API

**Statut :** DONE
**Story Parente :** STORY-124 — Clés API `wf_ak_` — table `api_keys`, auth `X-API-Key` coexistant avec JWT (P1-3, partie clés API)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant que responsable sécurité de WindFlow, je veux que le socle clés API posé par STORY-124.1 à 124.3 (table, hash déterministe, endpoints, auth `X-API-Key`/Bearer coexistant avec JWT) soit validé par des tests de sécurité transverses systématiques — refus 401/403/422/404, isolation multi-users, absence de tout secret dans les réponses et les logs — afin de garantir qu'une clé API n'est jamais un contournement du RBAC ni une fuite de secret.

Quatrième et dernière étape de STORY-124 (découpe proactive : 7 tâches / 8 fichiers) : consolide et complète les tests amorcés dans les sous-stories précédentes, couvre l'AC 4 en intégralité, et vérifie les non-régressions globales (auth JWT, refresh tokens STORY-123, RBAC STORY-122).

## Critères d'acceptation (AC)

- [x] AC 4 : Tests de sécurité obligatoires : `401` sans clé ; clé d'un utilisateur désactivé → `401` ; `403` lorsque le RBAC du propriétaire refuse (viewer sur endpoint modifiant) ; `422` sur body de création invalide ; isolation — un user ne liste/révoque que **ses** clés (`404`/`403` sur clé étrangère) ; aucune clé ni hash dans les réponses ni les logs. *(validé — 6 nouveaux tests 124.4 + 15 tests 124.3 consolidés, 21 passed ; traçabilité complète en Notes d'implémentation)*

> **Note de découpe :** cette sous-story couvre l'AC 4 **en intégralité**. Une partie des tests a été amorcée dans les sous-stories précédentes (422/404/401 dans STORY-124.3, hash jamais en clair dans STORY-124.2) — cette sous-story consolide, ajoute les cas manquants (RBAC viewer par clé, utilisateur désactivé, secrets dans les logs, révocation immédiate de bout en bout) et vérifie la non-régression globale.

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-13) — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches.

**Couches impactées :** Backend uniquement — tests. Aucun code de production sauf correction de défaut détecté par ces tests (dans ce cas : documenter la divergence dans les Notes d'implémentation).

**Spécifications de référence :**
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — la matrice rôle×endpoint s'applique à l'identique après auth par clé (viewer → 403 sur endpoint modifiant) ;
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Authentification par clé API (jamais la clé ni son hash dans les réponses/logs) ;
- [`.roo/rules/40-security.md`](../../.roo/rules/40-security.md) — checklist tests sécurité obligatoires (401/403/422/404, champs sensibles absents, isolation).

**Disponible en entrée (posé par STORY-124.1/.2/.3) :** table `api_keys`, `ApiKeyService` (`verify` refus invalide/révoquée/expirée/inactif + `last_used_at` throttlé), endpoints `POST/GET/DELETE /auth/api-keys`, auth `X-API-Key`/`Bearer wf_ak_…` dans `get_current_user`, RBAC `require_role` (STORY-122) inchangé et appliqué après résolution utilisateur.

**Fichiers de référence (patterns validés) :**
- [`backend/tests/unit/test_api/test_auth_refresh_security.py`](../../backend/tests/unit/test_api/test_auth_refresh_security.py) — fixture `_jwt_mode`, 401 paramétrés, vérification hash jamais en clair en base, isolation multi-users ;
- [`backend/tests/unit/test_api/test_admin_rbac.py`](../../backend/tests/unit/test_api/test_admin_rbac.py) / [`test_docker_rbac.py`](../../backend/tests/unit/test_api/test_docker_rbac.py) — patterns RBAC 403 par rôle sur endpoints modifiants ;
- [`backend/tests/unit/test_services/test_api_key_service.py`](../../backend/tests/unit/test_services/test_api_key_service.py) (créé par 124.2) — à compléter si des cas transverses y manquent.

> **Analyse d'affinage (analyse-story, 2026-09-16)** — recouvrement exact avec l'existant et patterns vérifiés dans le code :

**Recouvrement déjà couvert par les 15 tests de STORY-124.3** (dans `test_api_keys.py`) — ne PAS réécrire, la Tâche 1 consolide sans dupliquer :
- 401 sans clé → `test_create_api_key_requires_auth_401` ; 401 inconnue/malformée/révoquée/expirée → `test_invalid_or_expired_key_401` (paramétré) ; 401 désactivé → `test_disabled_user_key_401` ;
- 422 body invalide → `test_create_api_key_invalid_body_422` ; 404 clé étrangère + isolation liste → `test_list_api_keys_scoped_404_isolation` ;
- révocation immédiate → `test_revoke_then_key_unauthorized_401` (≈ « end_to_end » de la Tâche 2 : POST → auth OK → DELETE → 401 — déjà de bout en bout) ;
- clé expirée listée `revoked=false` → `test_list_api_keys_keeps_expired` ; `last_used_at` alimenté → `test_last_used_at_updated_on_request` (⚠️ le **throttling** n'y est pas) ;
- JWT non régressé → `test_jwt_still_works_alongside_api_key` ; hash ≠ clé en base → assertions dans `test_create_api_key_returns_201_with_key_once`.

**Vrai delta de 124.4** (cas NON couverts) : 403 RBAC viewer **par clé** + contraste rôle suffisant ; secrets absents des **réponses** sur parcours complet (consolidation) ; secrets absents des **logs** au niveau API (caplog — le test service 124.2 ne couvre que le service, pas la couche HTTP) ; **throttling** `last_used_at` de bout en bout ; non-régression refresh (STORY-123) par exécution des suites dédiées.

**Patterns vérifiés dans le code (à réutiliser tels quels) :**
- Fixtures rôles du conftest (STORY-122.7) : `viewer_user`, `operator_user` (rattachés `test_organization`) + helper `create_user_with_role(db_session, org, Role.X, suffix=...)` ;
- Cache rôles : fixture locale `autouse` `reset_role_cache()` avant/après (pattern [`test_docker_rbac.py:138`](../../backend/tests/unit/test_api/test_docker_rbac.py)) — le cache TTL 300 s de `require_role` fuiterait sinon entre tests de rôles différents ;
- Endpoint modifiant de référence : `DELETE /api/v1/docker/containers/{container_id}` (viewer → 403, opérateur/admin → succès ; Docker local = rôle **global**, pas d'org requise) ; le 403 RBAC court-circuite **avant toute E/S Docker** → pas de mock Docker nécessaire pour le 403 ; pour le contraste 200, mocker `patch("app.api.v1.docker.get_docker_client", return_value=AsyncMock())` (pattern [`test_docker_rbac.py:206`](../../backend/tests/unit/test_api/test_docker_rbac.py)) ;
- Clé × RBAC : la clé du viewer remplace simplement le JWT — header `X-API-Key: wf_ak_…` au lieu de `Authorization: Bearer` sur le même endpoint ; la chaîne `require_role` est identique (résolution rôle global via `AuthorizationService` sur le `User` propriétaire) ;
- caplog : `caplog.set_level(logging.DEBUG)` sur le parcours complet ; ⚠️ **piège environnement** : le `.env` racine (`DISABLE_AUTH=true`) doit être neutralisé (`DISABLE_AUTH=false`) ET **`LOG_LEVEL=WARNING`** en tête de commande — sinon les logs SQL SQLAlchemy (INFO) loggent les paramètres bindés (dont `key_hash`) et font échouer `test_no_key_no_hash_in_logs` (découvert en clôture 124.3).

**Exigences sécurité (Phase 2.6) :** story de **tests uniquement** — aucun endpoint nouveau, aucune dépendance à ajouter. L'audit de l'AC 4 est le livrable : 401 (sans clé/invalide/révoquée/expirée/désactivé), 403 (RBAC viewer par clé), 422, 404 (isolation), secrets absents (réponses + logs + base). Aucune production de code en dehors des fichiers de test.

## ⚖️ Arbitrages applicables (découpe proactive, validés le 2026-09-13)

1. **Clé expirée ≠ révoquée** : les tests doivent vérifier qu'une clé **expirée** retourne 401 en authentification mais reste **listée** dans `GET /auth/api-keys` avec `revoked=false` ;
2. **`last_used_at` throttlé** : les tests valident l'alimentation **et** le throttling (pas d'écriture multiple dans la même minute) ;
3. **Hash Argon2 déterministe** (alignement F2/STORY-123) : les assertions « hash bcrypt » de l'AC se lisent « hash fort vérifié, jamais la clé en clair » — divergence consignée pour STORY-252.

## Dépendances

- STORY-124.1, STORY-124.2, STORY-124.3 (tout le socle doit être implémenté).
- Réutilise : fixtures et patterns de tests RBAC (STORY-122) et auth refresh (STORY-123).

## Tâches d'implémentation détaillées

### Tâche 1 : Tests sécurité transverses API (RBAC par clé, désactivé, secrets)
**Objectif :** Compléter `test_api_keys.py` avec les cas sécurité systématiques de l'AC 4 non couverts par 124.3 — RBAC viewer par clé, absence de secrets dans réponses **et logs**.
**Fichiers :**
- `backend/tests/unit/test_api/test_api_keys.py` — Modifier — Ajouter une classe `TestRbacViaApiKey` et une classe `TestSecretsHygiene` (pattern `_jwt_mode` existant + `caplog`). Nouvelle classe d'import : `from unittest.mock import AsyncMock, patch` et `from app.core.cache import reset_role_cache` :
  - Fixture locale `autouse` `_clean_role_cache` (reset avant/après — pattern [`test_docker_rbac.py:138`](../../backend/tests/unit/test_api/test_docker_rbac.py)) dans `TestRbacViaApiKey` ;
  - `test_viewer_key_forbidden_on_modifying_endpoint_403` — `viewer_user` (fixture conftest) → créer une clé pour lui (JWT `_auth_headers(viewer_user)` → `POST /auth/api-keys`) → `DELETE /api/v1/docker/containers/any-container-id` avec `headers={"X-API-Key": clé}` → **403** (le RBAC du propriétaire s'applique par clé ; court-circuit avant E/S Docker → **pas de mock Docker requis**) ;
  - `test_operator_key_allowed_on_same_endpoint` — `operator_user` → clé → même DELETE avec mock `patch("app.api.v1.docker.get_docker_client", return_value=AsyncMock())` (le mock doit permettre `containers.delete()`/`containers.get()` — vérifier le handler du DELETE containers, pattern `test_docker_rbac.py`) → **200/204** (contraste : la clé n'est pas un rabaissement) ;
  - `test_no_key_no_hash_in_any_response` — parcours complet avec `test_user` : POST (201 contient `key` — unique occurrence) → GET liste → auth par clé sur `/auth/me` → DELETE → GET liste : `raw_key not in response.text` et `"key_hash" not in response.text` pour toutes les réponses hors POST 201 ;
  - `test_no_key_no_hash_in_logs` — même parcours sous `caplog.set_level(logging.DEBUG)` (import `logging`) + un échec volontaire (clé révoquée) pour couvrir `api_key.auth_failed` : `raw_key not in caplog.text` et hash récupéré en base `not in caplog.text` — ⚠️ exiger `LOG_LEVEL=WARNING` dans l'environnement d'exécution (piège documenté en Contexte technique) ;
  - `test_hash_not_plaintext_in_db` — consolidation : après POST, `select(APIKey)` → `row.key_hash != raw_key`, `raw_key not in row.key_hash`, et `row.key_hash.startswith("$argon2")` (hash fort Argon2 déterministe — arbitrage n°3, « bcrypt » de l'AC se lit « hash fort vérifié »).
**Exigences sécurité :** AC 4 — le 403 RBAC par clé prouve qu'une clé n'est jamais un contournement du RBAC ; secrets absents des réponses ET des logs (couche HTTP, en complément du test service 124.2).
**Dépend de :** STORY-124.3

### Tâche 2 : Tests transverses consolidés et non-régression
**Objectif :** Vérifier l'invariant transverse non couvert par 124.3 (throttling `last_used_at` de bout en bout au niveau API) et consigner les couvertures déjà existantes.
**Fichiers :**
- `backend/tests/unit/test_api/test_api_keys.py` — Modifier — Ajouter dans `TestAuthViaApiKey` (ou classe `TestTransversalInvariants`) :
  - `test_last_used_at_throttled_end_to_end` — POST → GET liste (`last_used_at: null`) → **deux** auths par clé sur `/auth/me` dans la même minute → GET liste : `last_used_at` alimenté **une seule fois** (comparer la valeur après 1er usage = valeur après 2e usage — le service throttle à 60 s, arbitrage n°2 ; le test service `test_last_used_at_throttled` de 124.2 couvre la mécanique, ce test prouve le comportement via HTTP) ;
  - `test_revocation_immediate_end_to_end` et `test_expired_key_401_but_listed_not_revoked` : **déjà couverts** par 124.3 (`test_revoke_then_key_unauthorized_401`, `test_list_api_keys_keeps_expired` + `test_invalid_or_expired_key_401[expired]`) — **ne pas dupliquer** ; référencer ces tests dans les Notes d'implémentation comme couverture de l'AC 4 ;
  - `test_jwt_and_refresh_not_regressed` — **ne pas dupliquer** : `test_jwt_still_works_alongside_api_key` (124.3) couvre le JWT ; la non-régression refresh (STORY-123) est garantie par l'exécution de `test_auth_refresh_security.py` + `tests/unit/test_auth/` en Tâche 3 (commandes).
- `backend/tests/unit/test_services/test_api_key_service.py` — Modifier (uniquement si un manque est détecté pendant l'implémentation) — à date de l'analyse, les 16 tests couvrent les cas transverses service (throttling, expiré≠révoqué, isolation, idempotence, logs) : aucun manque identifié.
**Exigences sécurité :** Invariant de throttling vérifié de bout en bout ; traçabilité explicite couverture AC 4 ↔ tests existants.
**Dépend de :** Tâche 1

### Tâche 3 : Validation globale et clôture du bloc STORY-124
**Objectif :** Exécuter les suites ciblées + non-régression large, consigner les résultats, et vérifier la complétude de l'AC 4 pour permettre la clôture de la story parente.
**Fichiers :**
- Aucun nouveau fichier — exécution des commandes de validation + mise à jour des sections « État d'avancement » / « Notes d'implémentation » de cette sous-story (et cohérence des cases AC de la parente via le workflow `finalise-story`).
**Exigences sécurité :** Vérifier qu'aucun test sécurité obligatoire (rules 40 / rules 35) ne manque : 401 sans clé, 403 RBAC viewer, 422 body invalide, 404 clé étrangère, secrets absents des réponses et logs.
**Dépend de :** Tâche 2

## Tests à écrire

> Les tests **sont** les tâches de cette sous-story — détail exhaustif dans les tâches ci-dessus. Récapitulatif AC 4 :

### Backend — sécurité transverse (`test_api_keys.py`)
- 401 sans clé / clé invalide / révoquée / expirée / utilisateur désactivé (paramétré)
- 403 viewer par clé sur endpoint modifiant (RBAC du propriétaire) + contraste rôle suffisant
- 422 body de création invalide
- Isolation : liste/révocation scoped user — 404 sur clé étrangère
- Aucune clé ni hash dans les réponses (hors 201 création) ni dans les logs
- Hash jamais en clair en base
- Révocation immédiate de bout en bout ; clé expirée listée mais non authentifiante ; `last_used_at` alimenté et throttlé
- Non-régression JWT + refresh (STORY-123)

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_api/test_api_keys.py backend/tests/unit/test_services/test_api_key_service.py -v
poetry run pytest backend/tests/unit/test_api/test_auth_refresh_security.py backend/tests/unit/test_auth/ -v  # non-régression auth
poetry run pytest backend/tests/unit/ -q  # non-régression large
make backend-lint && make backend-typecheck
```

## État d'avancement technique
- [x] Tâche 1 : Tests sécurité transverses API (RBAC 403 par clé, contraste rôle suffisant, secrets réponses/logs/base)
- [x] Tâche 2 : Throttling `last_used_at` end-to-end + traçabilité couverture AC 4
- [x] Tâche 3 : Validation globale et clôture du bloc STORY-124

## Notes d'implémentation

### Fichiers modifiés/créés
- [`backend/tests/unit/test_api_keys.py`](../../backend/tests/unit/test_api/test_api_keys.py) — **seul fichier modifié** : +6 tests dans 3 nouvelles classes (`TestRbacViaApiKey`, `TestSecretsHygiene`, `TestTransversalInvariants`) + imports (`logging`, `AsyncMock`/`patch`, `reset_role_cache`) ; docstring d'en-tête mise à jour.
- [`backend/tests/unit/test_services/test_api_key_service.py`](../../backend/tests/unit/test_services/test_api_key_service.py) — **non modifié** : conformément à la Tâche 2, aucun manque détecté (les 16 tests couvrent les cas transverses service — throttling, expiré≠révoqué, isolation, idempotence, logs).

### Tests écrits (6)
| Test | Cas AC 4 |
|------|----------|
| `TestRbacViaApiKey::test_viewer_key_forbidden_on_modifying_endpoint_403` | 403 RBAC viewer **par clé** (`X-API-Key` sur DELETE conteneur `require_admin`) — une clé n'est jamais un contournement du RBAC |
| `TestRbacViaApiKey::test_admin_key_allowed_on_same_endpoint` | Contraste rôle suffisant : admin par clé → 204 + `remove_container` appelé — la clé n'est ni rabaissement ni élévation |
| `TestSecretsHygiene::test_no_key_no_hash_in_any_response` | Parcours complet (POST→GET→`/auth/me` par clé→DELETE→GET) : `raw_key`/`key_hash` absents de toute réponse hors 201 |
| `TestSecretsHygiene::test_no_key_no_hash_in_logs` | caplog DEBUG sur parcours + échec volontaire (clé révoquée → `api_key.auth_failed`) : ni clé ni hash dans les logs (couche HTTP) |
| `TestSecretsHygiene::test_hash_not_plaintext_in_db` | `key_hash` ≠ clé, hash Argon2 (`$argon2…`) — arbitrage n°3 |
| `TestTransversalInvariants::test_last_used_at_throttled_end_to_end` | 2 auths dans la même minute → `last_used_at` identique après 1er et 2e usage (throttle 60 s via HTTP) |

### Traçabilité AC 4 ↔ couverture (consolidation, non duplication)
- **401 sans clé** : `test_create_api_key_requires_auth_401` (124.3) ;
- **401 invalide/inconnue/révoquée/expirée** : `test_invalid_or_expired_key_401` paramétré (124.3) ;
- **401 utilisateur désactivé** : `test_disabled_user_key_401` (124.3) ;
- **403 RBAC viewer par clé + contraste** : tests 124.4 ci-dessus ;
- **422 body invalide** : `test_create_api_key_invalid_body_422` (124.3) ;
- **Isolation 404 clé étrangère + liste scopée** : `test_list_api_keys_scoped_404_isolation` (124.3) ;
- **Secrets réponses** : `test_no_key_no_hash_in_any_response` (124.4) + `test_list_api_keys_no_secrets` (124.3) ;
- **Secrets logs** : `test_no_key_no_hash_in_logs` (124.4, couche HTTP — complément du test service 124.2) ;
- **Hash jamais en clair en base** : `test_hash_not_plaintext_in_db` (124.4) + assertions 124.2/124.3 ;
- **Révocation immédiate end-to-end** : `test_revoke_then_key_unauthorized_401` (124.3 — POST→200→DELETE→401, déjà de bout en bout) ;
- **Expirée listée mais non authentifiante** : `test_list_api_keys_keeps_expired` + `test_invalid_or_expired_key_401[expired]` (124.3) ;
- **`last_used_at` alimenté + throttlé** : `test_last_used_at_updated_on_request` (124.3) + `test_last_used_at_throttled_end_to_end` (124.4) ;
- **Non-régression JWT** : `test_jwt_still_works_alongside_api_key` (124.3) ; **non-régression refresh STORY-123** : suites dédiées exécutées ci-dessous.

### Décisions techniques
- Fixture `_clean_role_cache` autouse dans `TestRbacViaApiKey` (pattern `test_docker_rbac.py`) : le cache TTL 300 s de `require_role` fuiterait entre tests de rôles différents.
- `test_no_key_no_hash_in_logs` : `caplog.set_level(logging.DEBUG)` + `caplog.set_level(logging.WARNING, logger="sqlalchemy.engine")` — neutralise en interne le piège `LOG_LEVEL` documenté (les logs SQL INFO échappent les paramètres bindés dont `key_hash`) ; `LOG_LEVEL=WARNING` reste requis en tête de commande pour l'environnement global.
- Réutilisation des fixtures conftest STORY-122.7 (`viewer_user`, `org_admin_user`) et du mint direct JWT `_auth_headers` (pattern 124.3, évite le quota rate-limit login).

### Divergences vs analyse
1. **Contraste opérateur → admin** : la Tâche 1 spécifiait `test_operator_key_allowed_on_same_endpoint` (operator → 200/204 sur `DELETE /docker/containers/{id}`), mais la matrice spec 08 appliquée par STORY-122.2 réserve cet endpoint aux **admins** (`require_admin`, cf. `test_docker_rbac.py::TestOperatorMatrix::test_operator_403_delete_container` — operator y est 403). Le contraste « la clé n'est pas un rabaissement » a donc été réalisé avec `org_admin_user` (rôle réellement suffisant → 204 + appel Docker effectif), renommé `test_admin_key_allowed_on_same_endpoint`. L'intention du test (rôle suffisant par clé ≠ par JWT) est préservée ; suivre la spec 08 était la contrainte supérieure citée par la story elle-même.
2. **Story passée directement de IN_PROGRESS à DONE** (REVIEW franchi dans la même session) : tous les tests étaient déjà verts à la validation.

### Difficultés rencontrées
- **Environnement Poetry cassé** : `poetry run pytest` échoue sur l'import conftest (`ImportError: cannot import name 'command' from 'alembic'`) — le venv Poetry actif `.venv` est en **Python 3.14** avec un alembic défectueux. Contournement : exécution via **`.venv-test` (Python 3.11.10, conforme >=3.11)** où alembic fonctionne. À investiguer hors story (le Makefile `make backend-test-unit` est impacté).
- **35 échecs pré-existants** dans `backend/tests/unit/` (fichiers `test_stack_actions.py`, `test_stacks_archive.py`, `test_stacks_duplicate.py`, etc. — 500 sur endpoints stacks) : vérifiés **identiques à HEAD** via `git stash` (dernier commit = STORY-123), donc **antérieurs et hors périmètre** (story tests-only, aucun code de production touché). Aucun test du bloc auth/API keys/RBAC n'est en échec.

### Validation (commandes réelles exécutées)
```bash
# 1. Fichier ciblé (21 passed : 15 existants + 6 nouveaux)
LOG_LEVEL=WARNING .venv-test/bin/python -m pytest backend/tests/unit/test_api/test_api_keys.py -v
# → 21 passed, 5 warnings in 6.80s

# 2. Ciblé + service + non-régression auth refresh STORY-123 (78 passed)
LOG_LEVEL=WARNING .venv-test/bin/python -m pytest backend/tests/unit/test_api/test_api_keys.py backend/tests/unit/test_services/test_api_key_service.py backend/tests/unit/test_api/test_auth_refresh_security.py backend/tests/unit/test_auth/ -v --no-cov
# → 78 passed, 5 warnings in 5.32s

# 3. Non-régression large unitaires
LOG_LEVEL=WARNING .venv-test/bin/python -m pytest backend/tests/unit/ -q --no-cov -p no:randomly
# → 1447 passed, 35 failed (pré-existants à HEAD, hors périmètre — cf. Difficultés)

# 4. Format + lint du fichier modifié
.venv-test/bin/python -m isort --profile black backend/tests/unit/test_api/test_api_keys.py
.venv-test/bin/python -m black backend/tests/unit/test_api/test_api_keys.py
.venv-test/bin/python -m flake8 backend/tests/unit/test_api/test_api_keys.py
# → OK (fichier reformaté par black, tests repassés : 21 passed)

# 5. Re-vérification post-format
LOG_LEVEL=WARNING .venv-test/bin/python -m pytest backend/tests/unit/test_api/test_api_keys.py -q --no-cov -p no:randomly
# → 21 passed in 2.19s
```
*(`make backend-lint`/`backend-typecheck` non exécutés via Poetry : venv 3.14 cassé — cf. Difficultés ; équivalents isort/black/flake8 passés sur le fichier modifié via `.venv-test`.)*
