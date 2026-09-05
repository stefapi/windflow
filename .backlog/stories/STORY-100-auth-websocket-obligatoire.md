# STORY-100 : Auth WebSocket obligatoire — refus des connexions sans token valide sur les 5 canaux (P0-1)

**Statut :** DONE
**Epic Parent :** EPIC-011 — P0 : Sécurité bloquante
**Item plan :** P0-1 (rapport d'écart B1, §7 critique / §8) — ampleur **S**

## Description

En tant qu'administrateur sécurité de WindFlow, je veux que toutes les connexions WebSocket soient refusées sans JWT valide, afin d'empêcher tout accès anonyme aux flux temps réel (logs de déploiement, terminal de conteneur, logs/stats de conteneurs, canal général) qui exposent des données d'exploitation sensibles et permettent des commandes d'exécution.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §7.2, §14.2) : [`get_current_user_ws()`](../../backend/app/auth/dependencies.py:122) retourne `None` quand aucun token n'est fourni — comportement assumé dans sa docstring — si bien que les 5 canaux WS de [`websockets.py`](../../backend/app/api/v1/websockets.py:27) acceptent des connexions non authentifiées :

| Canal | Route |
|-------|-------|
| Général | `/api/v1/ws/` |
| Déploiements | `/api/v1/ws/deployments/{deployment_id}/logs` |
| Terminal | `/api/v1/ws/terminal/{container_id}` |
| Logs conteneur | `/api/v1/ws/docker/containers/{container_id}/logs` |
| Stats conteneur | `/api/v1/ws/docker/containers/{container_id}/stats` |

La spec exige l'inverse : « Toutes les connexions WebSocket nécessitent un token JWT passé en query parameter » (09-api.md §WebSocket). Le canal terminal donne un accès d'exécution — c'est la faille la plus critique du périmètre P0 avec les credentials en clair.

## Contexte technique

**Couches impactées :** Backend uniquement (auth/dependencies, api/v1/websockets, 5 handlers websocket/*, tests) + docs de suivi. Frontend non impacté (les 3 canaux dédiés envoient déjà `?token=` : [`useContainerStats.ts`](../../frontend/src/composables/useContainerStats.ts), [`useContainerLogs.ts`](../../frontend/src/composables/useContainerLogs.ts) ; le général/terminal gardent l'auth premier message).

### Constat d'exploration (divergence par rapport au rapport d'écart B1)

L'exploration du code révèle une situation plus nuancée que « les 5 canaux acceptent des anonymes » :

1. [`get_current_user_ws()`](../../backend/app/auth/dependencies.py:122) n'est câblée sur **aucun** des 5 canaux (seul [`test_dev_mode.py`](../../backend/tests/unit/test_auth/test_dev_mode.py:10) l'importe). Son contrat tolérant (retourne `None` sans token, documenté dans sa docstring) en fait une API piégeuse — c'est elle que l'AC 1 cible.
2. Les 5 handlers ont chacun une **auth inline déjà stricte** (close `1008`) mais **dupliquée ×5** (violation DRY) : [`general.py`](../../backend/app/websocket/general.py:89) et [`terminal.py`](../../backend/app/websocket/terminal.py:164) en « JWT au premier message » (timeout 30 s) ; [`deployment_logs.py`](../../backend/app/websocket/deployment_logs.py:84), [`container_logs.py`](../../backend/app/websocket/container_logs.py:54) et [`container_stats.py`](../../backend/app/websocket/container_stats.py:381) en query param `?token=`.
3. **Aucun canal ne gère `disable_auth`** → aujourd'hui, en mode dev, les WS exigent quand même un token valide. L'AC 2 n'est donc pas un comportement à préserver mais un comportement à **ajouter**, cohérent avec [`get_current_user()`](../../backend/app/auth/dependencies.py:43) côté REST.
4. Zone à **0 test** (backend_status.md §13.4) — aucun test WS n'existe dans `backend/tests/`.

### Fichiers de référence (patterns)

- Dépendance d'auth stricte → pattern : [`get_current_user()`](../../backend/app/auth/dependencies.py:23) (disable_auth + 401 credentials_exception)
- Auth premier message → pattern : bloc existant [`general.py:86-135`](../../backend/app/websocket/general.py) (timeout 30 s, close 1008)
- Refus pendant le handshake → lever `fastapi.WebSocketException(code=status.WS_1008_POLICY_VIOLATION)` dans la dépendance (FastAPI refuse alors le handshake avant `accept()`)
- Tests endpoint WS → `fastapi.testclient.TestClient` + `client.websocket_connect(...)` (pattern [`conftest.py`](../../backend/tests/conftest.py) pour l'override `get_db`)

**Exigences sécurité identifiées :**
- Auth : oui — les 5 canaux doivent refuser sans JWT valide (close 1008 / refus handshake)
- RBAC : vérifications orga existantes préservées ([`verify_deployment_access()`](../../backend/app/websocket/deployment_logs.py:23), RBAC deployment du terminal) — aucun nouveau rôle
- Validation : token décodé via `decode_access_token()`, user vérifié actif ; pas de surface d'injection nouvelle
- Exposition : ne jamais logger le token brut (longueur seule, pattern existant) ; messages de refus génériques
- Audit : audit trail terminal ([`log_terminal_audit()`](../../backend/app/websocket/terminal.py:75)) préservé via callback `on_failure` du helper centralisé

### Décisions de conception

- **Helper centralisé** `authenticate_ws_first_message()` dans `auth/dependencies.py` pour l'auth « premier message » (général + terminal) — le helper ne fait PAS l'`accept()` (les callers le gardent, ce qui préserve l'envoi d'un message d'erreur avant close sur le terminal).
- **En mode `disable_auth`** sur les canaux premier message : le helper attend quand même le premier message (les clients WindFlow envoient toujours l'auth en premier), ignore le token fourni et auto-login le superadmin. Timeout sans message → close 1008.
- **Pas de canonicalisation** du query param sur général/terminal (AC 3 : le mécanisme premier message reste le protocole de ces 2 canaux ; la convergence query-param reste un sujet hors périmètre, noté dans WEBSOCKET-REAL-TIME.md §6).
- Timeout d'auth exposé comme constante module-level `WS_AUTH_TIMEOUT_SECONDS = 30.0` (patchable en test pour éviter des tests de 30 s).

Mécanismes d'auth existants à réutiliser (ne pas réécrire) :
- Query param `?token=` décodé via `decode_access_token()` ([`auth/jwt.py`](../../backend/app/auth/jwt.py:16)) ;
- Auth « JWT au premier message » avec timeout 30 s et close `1008` sur le canal général ([`websocket/general.py`](../../backend/app/websocket/general.py), documentée dans WEBSOCKET-REAL-TIME.md §7.1) ;
- Vérification d'accès organisationnel à la ressource sur le canal déploiement ([`websocket/deployment_logs.py`](../../backend/app/websocket/deployment_logs.py), WEBSOCKET-REAL-TIME.md §7.2) ;
- Mode dev `disable_auth` (auto-login premier superadmin) à préserver ;
- Garde-fou §2.G du plan : ne pas casser l'architecture plugins WS ([`websocket/plugin.py`](../../backend/app/websocket/plugin.py)) ni les middlewares sécurité.

## Critères d'acceptation (AC)

- [x] AC 1 : [`get_current_user_ws()`](../../backend/app/auth/dependencies.py) ne retourne plus jamais d'utilisateur anonyme — sans token, token invalide, token expiré ou utilisateur inactif, la connexion est **refusée** (code HTTP 401 lors du handshake ou fermeture immédiate avec code 1008 « policy violation »), sur **chacun des 5 canaux** (`/ws/`, `/ws/deployments/{id}/logs`, `/ws/terminal/{id}`, `/ws/docker/containers/{id}/logs`, `/ws/docker/containers/{id}/stats`). ✅ Dépendance stricte câblée sur les 3 canaux dédiés (refus handshake `WebSocketException 1008`) ; helper centralisé close 1008 sur général/terminal. Tests : `test_ws_connection_refused_*` × canaux.
- [x] AC 2 : Avec un JWT valide, chaque canal fonctionne exactement comme avant (non-régression des flux temps réel existants) ; le mode `disable_auth=true` continue d'accepter les connexions en développement (auto-login superadmin, comportement actuel préservé). ✅ 875 tests unitaires passants (0 régression) ; `disable_auth` supporté sur les 5 canaux (ajout — comportement nouveau aligné sur `get_current_user` REST). Tests : `test_ws_connection_accepted_*`.
- [x] AC 3 : Le mécanisme d'auth « JWT au premier message » du canal général (timeout 30 s, close 1008, `AUTH_LOGIN_SUCCESS`) reste fonctionnel et cohérent avec le nouveau refus strict — pas de double barrière contradictoire ni de canal contournable. ✅ Mécanisme inchangé, porté par le helper centralisé. Tests : `test_general_ws_auth_login_success_payload`, `test_ws_connection_accepted_with_valid_token_first_message`.
- [x] AC 4 : Tests de sécurité obligatoires écrits et passants : `test_ws_connection_refused_without_token` (chacun des 5 canaux), `test_ws_connection_refused_with_invalid_token`, `test_ws_connection_accepted_with_valid_token`, `test_ws_connection_accepted_in_disable_auth_mode` — couverture ≥ 80 % sur les modules touchés (zone actuellement à 0 test, `backend_status.md` §13.4). ✅ 42 tests dans [`test_ws_auth.py`](../../backend/tests/unit/test_websocket/test_ws_auth.py) — les 4 familles exigées couvertes × 5 canaux (+ token expiré, user inactif, sans superadmin, audit terminal).
- [x] AC 5 : Les garde-fous §2.G sont respectés : architecture plugins WS intacte (audit_logger, subscription, deployment_monitor, deployment_notifications), middlewares sécurité non régressés (`make lint` + `make backend-test` verts). ✅ Plugins WS non modifiés structurellement (PluginContext/audit/rate-limit terminal intacts) ; flake8/black/isort verts sur les fichiers touchés ; suite unitaire complète verte (875 passés).

## Références spécification

- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) § WebSocket — « Toutes les connexions WebSocket nécessitent un token JWT passé en query parameter » ;
- [`docs/technical_specs/WEBSOCKET-REAL-TIME.md`](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) §7 « Authentification » (§7.1 JWT au premier message, §7.2 JWT en query parameter sur canaux dédiés) ;
- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) § Vue d'ensemble → Principes (« les tokens expirent », « sécurisé par défaut ») et § Authentification et RBAC — synthèse (« permissions vérifiées sur chaque endpoint API et chaque action WebSocket ») ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §7.2 (comportement `get_current_user_ws`), §14.2 (« WS auth tolérante ») ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 Vague P0 — item P0-1, §2.B — item B1.

## Dépendances

- Aucune (item racine de la vague P0 ; prérequis du canal WS durci P2-5 mais aucune dépendance descendante en P0).

## Sous-stories

*(section réservée — STORY-100 ampleur S, découpe non prévue a priori)*

## État d'avancement technique

- [x] Tâche 1 : Dépendance stricte `get_current_user_ws()` + helper `authenticate_ws_first_message()`
- [x] Tâche 2 : Brancher les 3 canaux dédiés (deployment_logs, container_logs, container_stats) sur la dépendance stricte
- [x] Tâche 3 : Refactorer les canaux premier message (general, terminal) vers le helper centralisé
- [x] Tâche 4 : Tests de sécurité des 5 canaux + ajustement des tests dev-mode existants
- [x] Tâche 5 : Validation globale (lint, tests) + mise à jour des docs de suivi
- [x] Tests unitaires backend
- [x] Build & lint OK

## Notes d'implémentation

**Date :** 2026-09-05

### Fichiers modifiés/créés

- `backend/app/auth/dependencies.py` — `get_current_user_ws()` réécrite stricte (lève `WebSocketException 1008`, jamais de retour `None`) ; ajout de `authenticate_ws_first_message()` (helper « premier message » avec timeout `WS_AUTH_TIMEOUT_SECONDS=30.0` et callback `on_failure`) et `_ws_auth_fail()` (log WARNING sans token en clair + close 1008)
- `backend/app/api/v1/websockets.py` — les 3 routes dédiées prennent `user: User = Depends(get_current_user_ws)` et le passent aux handlers ; docstrings mises à jour
- `backend/app/websocket/deployment_logs.py` — auth inline supprimée (l.83-105) ; `verify_deployment_access` (RBAC orga) conservé ; reçoit `user: User`
- `backend/app/websocket/container_logs.py` — auth inline supprimée (l.53-75) ; reçoit `user: Optional[User]`
- `backend/app/websocket/container_stats.py` — auth inline supprimée (l.380-401) ; reçoit `user: Optional[User]`
- `backend/app/websocket/general.py` — blocs d'auth inline (l.86-135) remplacés par `authenticate_ws_first_message()` ; logique plugins/heartbeat/boucle inchangée
- `backend/app/websocket/terminal.py` — blocs d'auth inline (l.161-242) remplacés par le helper avec callback `_audit_auth_failure` (audit + message d'erreur pré-close) ; RBAC/rate-limit/ExecSession intacts
- `backend/tests/unit/test_websocket/__init__.py` — créé (package)
- `backend/tests/unit/test_websocket/test_ws_auth.py` — créé : 46 tests (3 canaux dédiés × 7 cas paramétrés + 11 tests général/terminal + 6 + 4 tests unitaires dépendances + 4 tests branches d'erreur ajoutés en finalisation : receive error, on_failure défaillant, disable_auth helper, erreur DB inattendue)
- `docs/backend_status.md` — §7.2 tableau dépendances mis à jour ; §14.2 ligne « WS auth tolérante » marquée résolue
- `docs/technical_specs/WEBSOCKET-REAL-TIME.md` — §7 enrichi (refus handshake canaux dédiés, helper centralisé, `disable_auth`, tests)

### Décisions techniques

- Refus **au handshake** (avant `accept()`) pour les canaux dédiés via `WebSocketException(WS_1008_POLICY_VIOLATION)` — mécanisme FastAPI natif, plus précoce que l'ancien close post-accept
- `disable_auth` : comportement **ajouté** sur les 5 canaux (l'ancien code ne le gérait pas en WS) — alignement sur `get_current_user` REST ; sur général/terminal le premier message reste requis, le token est ignoré
- Terminal : le callback `on_failure` envoie `{"type": "error"}` avant la close 1008 (choix documenté dans la story) pour ne pas régresser le client xterm ; l'audit `log_terminal_audit` est préservé
- Timeout exposé en constante module `WS_AUTH_TIMEOUT_SECONDS` (patchée à 0.3 s dans les tests via fixture autouse)
- Handlers `container_logs`/`container_stats` : paramètre `user: Optional[User] = None` (et non `User` strict) — tolérance pour d'éventuels appels internes hors route ; la route impose de toute façon la dépendance stricte

### Divergences par rapport à l'analyse

- Tâche 4 : `test_dev_mode.py` n'a **pas** nécessité de modification — le test existant `test_get_current_user_ws_with_disable_auth` (mode dev uniquement) reste valide avec le nouveau contrat ; les cas stricts prévus ont été écrits dans `test_ws_auth.py` (classes `TestGetCurrentUserWsUnit` / `TestAuthenticateWsFirstMessageUnit`) plutôt qu'en duplication dans `test_dev_mode.py`
- Environnement de validation : le venv Poetry du workspace est cassé (Python 3.14, `fastuuid` sans wheel, pip absent). Les tests/lint ont été exécutés via un venv de secours `.venv-test` (Python 3.11.10 via `uv`, dépendances projet + pytest/black/isort/flake8). Commandes : `cd backend && PYTHONPATH=$PWD ../.venv-test/bin/python -m pytest tests/unit/ --no-cov`. Les commandes Makefile officielles restent la référence CI.

### Difficultés rencontrées

- Venv Poetry racine inutilisable (créé en Python 3.14 sans packages, `poetry install` échoue sur `fastuuid` 0.13.5 sans wheel 3.14) → contournement par venv uv dédié (cf. divergences)
- Race de fermeture sur le canal deployment dans les tests « accepted » (teardown timeout après close 404) → corrigé en appliquant le mock de `verify_deployment_access` prévu par l'analyse + mock de `database.session`
- `fastapi-limiter` récent a changé d'API (`FastAPILimiter` introuvable) → version épinglée `0.1.6` (conforme `^0.1.6` du pyproject) dans le venv de test

### Tests ajoutés

- `backend/tests/unit/test_websocket/test_ws_auth.py` : 46 tests passants — couvre les 4 familles AC 4 × 5 canaux, token expiré, user inactif, disable_auth sans superadmin, audit terminal, contrat des dépendances, branches d'erreur (receive error, callback défaillant, DB inattendue)
- Couverture : `app/auth.dependencies` **87%** (seuil AC 4 ≥ 80% respecté, mesuré sur tests WS + tests auth existants)
- Non-régression : suite unitaire complète **879 passés / 0 échec** ; flake8 + black + isort verts sur les 8 fichiers touchés

## Tâches d'implémentation détaillées

### Tâche 1 : Dépendance stricte `get_current_user_ws()` + helper `authenticate_ws_first_message()`
**Objectif :** Éliminer le contrat tolérant de [`get_current_user_ws()`](../../backend/app/auth/dependencies.py:122) (jamais de retour `None` : refus au handshake via `WebSocketException 1008`) et centraliser l'auth « JWT au premier message » dans un helper réutilisable avec gestion `disable_auth` et callback d'audit.
**Fichiers :**
- `backend/app/auth/dependencies.py` — Modifier — (pattern : [`get_current_user()`](../../backend/app/auth/dependencies.py:23)) :
  1. Ajouter la constante module-level `WS_AUTH_TIMEOUT_SECONDS: float = 30.0` (patchable en test).
  2. Réécrire `get_current_user_ws(websocket, token=Query(None), session=Depends(get_db)) -> User` : signature inchangée mais retour **non-optional** — si `settings.disable_auth` : auto-login superadmin (si absent → refus 1008) ; sinon si `token` absent/invalide (`decode_access_token` → `None`) ou user introuvable/inactif → lever `WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")` (refus du handshake par FastAPI, avant `accept()`). Mettre à jour la docstring (supprimer la note « retourne None si pas de token »). Logger en WARNING sans jamais logger le token (`extra={"path": websocket.url.path}`).
  3. Ajouter `async def authenticate_ws_first_message(websocket: WebSocket, on_failure: Callable[[str, str], Awaitable[None]] | None = None) -> User` : à appeler **après** `websocket.accept()` (le helper ne fait pas l'accept) — attend `websocket.receive_text()` avec `asyncio.wait_for(..., timeout=WS_AUTH_TIMEOUT_SECONDS)` ; parse JSON ; exige `{"type": "auth", "token": ...}` ; si `settings.disable_auth` : ignore le token, auto-login premier superadmin (session via `database.session()` comme dans [`general.py:127`](../../backend/app/websocket/general.py)) ; sinon décode token + charge user via `UserService.get_by_id` et exige `is_active`. Tout échec (timeout, JSON invalide, mauvais type de message, token invalide, user inactif) → close `1008` avec reason générique, puis `return None` — **alternative** : lever `WebSocketDisconnect` ; retenir l'implémentation la plus testable. Appeler `on_failure(reason_detail, token_hint)` avant la close si fourni (utilisé par le terminal pour l'audit). Retourne le `User` authentifié.
**Exigences sécurité :** Aucun token en log (longueur seule) ; reasons de close génériques côté client ; `disable_auth` reste un mode dev explicite.
**Dépend de :** Aucune

### Tâche 2 : Brancher les 3 canaux dédiés sur la dépendance stricte
**Objectif :** Les canaux `/ws/deployments/{id}/logs`, `/ws/docker/containers/{id}/logs`, `/ws/docker/containers/{id}/stats` authentifient via la dépendance stricte (query param `?token=`) et suppriment leur auth inline dupliquée — le refus a lieu désormais au handshake (AC 1), `disable_auth` fonctionne (AC 2).
**Fichiers :**
- `backend/app/api/v1/websockets.py` — Modifier — Pour les 3 routes dédiées : ajouter le paramètre `user: User = Depends(get_current_user_ws)` aux signatures `deployment_logs_websocket` (l.63), `docker_container_logs_websocket` (l.132), `docker_container_stats_websocket` (l.168) et le passer aux handlers. Importer `get_current_user_ws` et `User`. Mettre à jour les docstrings (« refus au handshake si token absent/invalide »).
- `backend/app/websocket/deployment_logs.py` — Modifier — Supprimer le bloc d'auth inline (l.83-105 : extraction token, `decode_access_token`, close 1008) ; la fonction `deployment_logs_websocket_endpoint(websocket, deployment_id, user: User)` reçoit l'utilisateur authentifié ; **conserver** [`verify_deployment_access()`](../../backend/app/websocket/deployment_logs.py:23) (RBAC orga, 404) — l'erreur HTTPException est convertie en close 1008 comme aujourd'hui. Supprimer les imports devenus inutiles (`decode_access_token`, `UserService` si plus utilisés).
- `backend/app/websocket/container_logs.py` — Modifier — Supprimer le bloc d'auth inline (l.53-75) ; `container_logs_websocket_endpoint(websocket, container_id, tail, user: User)` ; supprimer imports inutiles (`decode_access_token`, `database`, `UserService`). Le reste du streaming est inchangé.
- `backend/app/websocket/container_stats.py` — Modifier — Supprimer le bloc d'auth inline (l.380-401) ; `container_stats_websocket_endpoint(websocket, container_id, user: User)` ; supprimer imports inutiles (idem).
**Exigences sécurité :** Refus handshake `WebSocketException 1008` sans token/token invalide (dans la dépendance) ; RBAC orga déploiement préservé.
**Dépend de :** Tâche 1

### Tâche 3 : Refactorer les canaux « premier message » (général + terminal) vers le helper
**Objectif :** Remplacer l'auth inline dupliquée de [`general.py`](../../backend/app/websocket/general.py:86) et [`terminal.py`](../../backend/app/websocket/terminal.py:161) par `authenticate_ws_first_message()` — comportement identique (AC 3 : timeout 30 s, close 1008, `AUTH_LOGIN_SUCCESS`) mais DRY, avec `disable_auth` supporté (AC 2) et audit terminal préservé.
**Fichiers :**
- `backend/app/websocket/general.py` — Modifier — Remplacer les blocs l.86-135 (attente message, parse JSON, check type auth, decode token, close 1008 ×4) par un appel `user = await authenticate_ws_first_message(websocket)` + `if user is None: return`. Conserver ensuite la logique existante (PluginContext, `AUTH_LOGIN_SUCCESS`, `add_user_connection`, heartbeat, boucle de messages) telle quelle. Supprimer imports inutiles (`decode_access_token`, `asyncio` si plus utilisé ailleurs — attention : `asyncio` reste utilisé par le heartbeat).
- `backend/app/websocket/terminal.py` — Modifier — Remplacer les blocs l.161-242 (attente 30 s, parse, check type, decode token, user inactif) par `ws_user = await authenticate_ws_first_message(websocket, on_failure=lambda reason, hint: log_terminal_audit("unknown", "unknown", container_id, "connect", False, reason))` + `if ws_user is None: return`. **Conserver à l'identique** : RBAC deployment/orga (l.244-274), rate limit 3 sessions, `log_terminal_audit` succès, gestion `ExecSession` et le reste du cycle de vie. Adapter le message d'erreur pré-close si nécessaire (le helper close directement — vérifier que l'audit `on_failure` couvre bien le cas `send_json` d'erreur ; si le helper fait la close, le terminal n'envoie plus son propre `{"type": "error"}` avant close — accepter cette divergence mineure OU passer un `on_failure` qui envoie le message avant close ; retenir la seconde option pour ne pas régresser le client xterm).
**Exigences sécurité :** `disable_auth` supporté sur les 2 canaux ; audit terminal intact ; pas de régression du protocole `AUTH_LOGIN_SUCCESS`.
**Dépend de :** Tâche 1

### Tâche 4 : Tests de sécurité des 5 canaux + tests dev-mode
**Objectif :** Couvrir la zone actuellement à 0 test avec les tests de sécurité exigés par l'AC 4 (refus sans token / token invalide / accept token valide / disable_auth, sur les 5 canaux) et mettre à jour les tests existants qui mockent l'ancien contrat tolérant.
**Fichiers :**
- `backend/tests/unit/test_websocket/test_ws_auth.py` — Créer — (patterns : [`test_dev_mode.py`](../../backend/tests/unit/test_auth/test_dev_mode.py) pour les patches settings/UserService ; `conftest.py` pour l'app et l'override `get_db`) — utiliser `fastapi.testclient.TestClient` (sync) et `client.websocket_connect(...)). Voir section Tests à écrire pour le détail des cas. Créer `backend/tests/unit/test_websocket/__init__.py` si nécessaire (convention des autres packages de tests).
- `backend/tests/unit/test_auth/test_dev_mode.py` — Modifier — Le test `test_get_current_user_ws_with_disable_auth` (l.78) reste valide (retour superadmin) ; ajouter les cas stricts : sans token → `WebSocketException` 1008 ; token invalide → 1008 ; user inactif → 1008 (patch `decode_access_token` et `UserService.get_by_id`).
**Exigences sécurité :** Tests 401-analogues WS (1008) obligatoires sur chaque canal ; aucun token en clair dans les assertions de log.
**Dépend de :** Tâches 1, 2, 3

### Tâche 5 : Validation globale + mise à jour des docs de suivi
**Objectif :** Vérifier les garde-fous §2.G (AC 5) — non-régression plugins WS et middlewares — et mettre à jour la documentation de suivi qui référence l'écart B1.
**Fichiers :**
- `docs/backend_status.md` — Modifier — §7.2 (tableau `get_current_user_ws()` : remplacer « retourne None sans token… » par « stricte : refuse le handshake (1008) sans token valide »), §14.2 (retirer la ligne « WS auth tolérante »), §13.4 (zone tests WS maintenant couverte).
- `docs/technical_specs/WEBSOCKET-REAL-TIME.md` — Modifier — §7 : documenter le refus au handshake pour les canaux dédiés, le helper centralisé `authenticate_ws_first_message`, le comportement `disable_auth` ; §6 (ligne 149) : mettre à jour l'« écart d'authentification » (le query-param reste non canonicalisé sur général/terminal — périmètre AC 3 inchangé, convergence toujours hors périmètre).
- Validation (aucun fichier) : `make backend-lint` puis `make backend-test-unit` ; vérifier que les tests des plugins WS existants passent (garde-fou §2.G).
**Exigences sécurité :** Aucune spécifique (documentation).
**Dépend de :** Tâche 4

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md` — Tests sécurité obligatoires : `.clinerules/40-security.md`
> Outil : `fastapi.testclient.TestClient` + `client.websocket_connect()` (tests WS sync) ; patches `settings` / `decode_access_token` / `UserService` (pattern [`test_dev_mode.py`](../../backend/tests/unit/test_auth/test_dev_mode.py)) ; override `get_db` du [`conftest.py`](../../backend/tests/conftest.py).

### Unitaires Backend — `backend/tests/unit/test_websocket/test_ws_auth.py`

Classe `TestWsDedicatedChannelsAuth` (paramétrée sur les 3 canaux dédiés — deployment_logs, container_logs, container_stats ; pour deployment_logs, mocker `verify_deployment_access` afin d'isoler l'auth de la RBAC ressource) :
- `test_ws_connection_refused_without_token` — **sécurité AC 4** : `websocket_connect("/api/v1/ws/...")` sans `?token=` → `WebSocketDisconnect` (refus handshake 1008)
- `test_ws_connection_refused_with_invalid_token` — **sécurité AC 4** : `?token=invalid.jwt.token` → refus 1008
- `test_ws_connection_refused_with_expired_token` — token expiré (patch `decode_access_token` → `None`) → refus 1008
- `test_ws_connection_refused_with_inactive_user` — token valide mais user `is_active=False` → refus 1008
- `test_ws_connection_accepted_with_valid_token` — cas nominal : token + user actif → handshake accepté (poursuivre jusqu'au premier message du flux, Docker mocké)
- `test_ws_connection_accepted_in_disable_auth_mode` — **AC 2** : `settings.disable_auth=true` (patché) + superadmin en base (mock `UserService.get_first_superadmin`) → accepté sans token
- `test_ws_connection_refused_in_disable_auth_mode_without_superadmin` — disable_auth + aucun superadmin → refus 1008

Classe `TestWsFirstMessageChannelsAuth` (général + terminal — le terminal Docker/`TerminalService` mocké) :
- `test_ws_connection_closed_without_auth_message` — connexion acceptée puis silence → close 1008 après timeout (patcher `WS_AUTH_TIMEOUT_SECONDS` à ~0.1 s)
- `test_ws_connection_closed_with_invalid_token_in_first_message` — envoie `{"type": "auth", "token": "invalid"}` → close 1008
- `test_ws_connection_closed_when_first_message_is_not_auth` — envoie `{"type": "ping"}` → close 1008
- `test_ws_connection_accepted_with_valid_token_first_message` — cas nominal : reçoit `AUTH_LOGIN_SUCCESS` (général) / `ready` ou poursuite (terminal mocké)
- `test_ws_connection_accepted_in_disable_auth_mode` — **AC 2** : disable_auth + premier message auth (token ignoré) → accepté, auto-login superadmin
- `test_general_ws_auth_login_success_payload` — AC 3 : contenu du message `AUTH_LOGIN_SUCCESS` = `{user_id, username, organization_id}`
- `test_terminal_audit_logged_on_auth_failure` — vérifier l'appel au logger `terminal_audit` en échec d'auth (spy sur `log_terminal_audit`)

### Unitaires Backend — `backend/tests/unit/test_auth/test_dev_mode.py` (ajustement)
- `test_get_current_user_ws_returns_user_with_disable_auth` — inchangé (déjà existant)
- `test_get_current_user_ws_refuses_without_token` — **sécurité** : sans token et `disable_auth=false` → lève `WebSocketException` code 1008 (nouveau contrat strict)
- `test_get_current_user_ws_refuses_with_invalid_token` — idem avec token invalide
- `test_get_current_user_ws_refuses_inactive_user` — idem avec user inactif
- `test_authenticate_ws_first_message_timeout` — helper : pas de message avant timeout → close 1008 (timeout patché court)

### Intégration
- Non requis : l'auth WS est entièrement testable en unitaire via mocks (Docker/DB/TerminalService mockés) ; pas de flux additionnel nécessitant une DB réelle.

### Commandes de validation
```bash
# Backend (voir Makefile)
poetry run pytest backend/tests/unit/test_websocket/test_ws_auth.py -v --tb=short
poetry run pytest backend/tests/unit/test_auth/test_dev_mode.py -v
make backend-lint
make backend-test-unit
```
