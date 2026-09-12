# STORY-122.6 : Application RBAC — admin instance et canaux WebSocket

**Statut :** DONE
**Story Parente :** STORY-122 — Dépendances RBAC `require_role(...)` — hiérarchie, cache TTL 300 s et protections d'escalade sur les ~110 endpoints (P1-2, application)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'administrateur sécurité de WindFlow, je veux que les 15 endpoints d'administration instance (`admin/stacks_management.py` — gestion du catalogue global de stacks) soient réservés au Super Admin, et que les 5 canaux WebSocket appliquent la matrice spec 08 (terminal/console = Operator+ ; logs/stats/déploiements = Viewer+) — remplaçant les `get_current_superadmin` et l'authentification seule actuelle.

## Critères d'acceptation (AC)

- [x] AC 2 (volet admin/ws) : Tous les endpoints `admin/*` exigent `super_admin` ; les 5 canaux WebSocket exigent le rôle minimum matriciel (terminal → operator+, logs/stats/deployment logs/general → viewer) ; vérifié par une matrice représentative : viewer → refus terminal (1008), 200 ailleurs ; operator+ → tous ; admin non-superuser → 403 sur `admin/*` ; `super_admin` → tout.

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-08) — 15 routes admin + 5 canaux WS vérifiés par grep.

**Couches impactées :** Backend uniquement — router admin + router websockets (+ handlers consommés) + tests.

**Spécifications de référence :**
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — § Matrice : Système « Paramètres globaux / Registres » = Super Admin ; Stacks catalogue/registre = registres → Super Admin (confirmé par l'existant `get_current_superadmin` ×15) ; Apps « Console » = Operator+ ; « Logs / Lister / Inspecter » = tous rôles ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Administration (Super Admin).

**Inventaire vérifié :**

**[`admin/stacks_management.py`](../../backend/app/api/v1/admin/stacks_management.py) — 15 routes, toutes `get_current_superadmin` (l. 110, 181, 229, 333, 367, 428, 576, 613, 653, 681, 729, 774, 838, 916, 989) :**

| Routes | Verbe | Rôle cible |
|-------|-------|-----------|
| `/definitions` (l. 108), `/imported` (l. 326), `/sync/status` (l. 365), `/{id}/export` (l. 572), `/stats/overview` (l. 772), `/{id}/usage` (l. 834), `/health` (l. 914), `/search` (l. 979) | GET | **super_admin** |
| `/validate` (l. 179), `/import` (l. 220), `/sync/auto` (l. 422), `/export/bulk` (l. 608), `/{id}/duplicate` (l. 673) | POST | **super_admin** |
| `/{id}/toggle-visibility` (l. 649) | PATCH | **super_admin** |
| `/{id}` (l. 722) | DELETE | **super_admin** |

> Arbitrage : même les GET admin restent `super_admin` — c'est un **registre système global** (import/sync du catalogue d'installations), cohérent avec la protection existante exhaustive (garde-fou : ne pas élargir). La matrice « Registres = Super Admin » couvre.

**[`websockets.py`](../../backend/app/api/v1/websockets.py) — 5 canaux (déjà authentifiés via `get_current_user_ws` l. 69, 150, 191 ou handlers) :**

| Canal | Rôle cible | Justification matrice |
|-------|-----------|----------------------|
| `/` general (l. 29) | viewer | Événements généraux (lecture) |
| `/deployments/{id}/logs` (l. 65) | viewer | Logs déploiement = lecture |
| `/terminal/{container_id}` (l. 108) | **operator** | Console = Operator+ (§ Apps) |
| `/docker/containers/{id}/logs` (l. 143) | viewer | Logs |
| `/docker/containers/{id}/stats` (l. 185) | viewer | Métriques |

**Fichiers de référence (patterns vérifiés) :**
- Dépendance WS — `require_role_ws` (STORY-122.1, `auth/rbac.py`) : lève `WebSocketException(1008)` — compose `get_current_user_ws` (refus handshake avant accept) ;
- Handlers WebSocket — [`backend/app/websocket/terminal.py`](../../backend/app/websocket/terminal.py), [`container_logs.py`](../../backend/app/websocket/container_logs.py), [`container_stats.py`](../../backend/app/websocket/container_stats.py), [`deployment_logs.py`](../../backend/app/websocket/deployment_logs.py), [`general.py`](../../backend/app/websocket/general.py) — la protection se pose **dans websockets.py** (router) par composition de dépendances, sans modifier la logique interne des handlers ;
- Tests WS — [`backend/tests/unit/test_websocket/test_ws_auth.py`](../../backend/tests/unit/test_websocket/test_ws_auth.py) (fixtures `ws_client`, paramétrage CHANNELS) et [`test_ws_isolation_1213.py`](../../backend/tests/unit/test_websocket/test_ws_isolation_1213.py) (`_make_user` non-persisté).

**Mécanisme retenu pour les WebSocket :** FastAPI ne supporte pas `Depends` avec paramètre factory sur les décorateurs `@router.websocket` aussi directement que pour HTTP — implémentation : dans chaque endpoint WS du router, **après** récupération du user via `get_current_user_ws`, appeler le vérificateur `ensure_role_ws(user, minimum_role)` (fonction async de `auth/rbac.py` levant `WebSocketException(1008)`) — même sémantique que `require_role_ws`, adaptée à l'enchaînement manuel. `require_role_ws` reste exposé pour usage décorateur si FastAPI le permet ; l'analyse recommande `ensure_role_ws` systématique (à trancher à l'implémentation — signaler divergence).

**Exigences sécurité identifiées (Phase 2.6) :**
- Auth : handshake refusé 1008 sans token (existant `get_current_user_ws`) — inchangé ;
- RBAC : rôle **global** (terminal Docker local = instance) ; refus 1008 policy violation, jamais d'accept-then-drop silencieux ;
- Validation/Exposition : inchangées ;
- Audit : refus RBAC WS loggés warning (path, user_id — jamais de token).

## Dépendances

- STORY-122.1 (socle + `require_role_ws`/`ensure_role_ws`). Parallélisable avec 122.2-122.5.

## Tâches d'implémentation détaillées

### Tâche 1 : `super_admin` sur les 15 routes d'`admin/stacks_management.py`
**Objectif :** Remplacement mécanique de `get_current_superadmin` par `require_super_admin` (sémantique RBAC unifiée).
**Fichiers :**
- `backend/app/api/v1/admin/stacks_management.py` — Modifier — 15 occurrences `Depends(get_current_superadmin)` → `Depends(require_super_admin)` (l. 110, 181, 229, 333, 367, 428, 576, 613, 653, 681, 729, 774, 838, 916, 989) ; import `from ....auth.rbac import require_super_admin` ; retirer import `get_current_superadmin` si plus utilisé ; mettre à jour les docstrings (Access Control : Super Admin — registre global) ; **aucun changement de path/response_model**.
**Exigences sécurité :** 401 sans token, 403 non-superadmin (y compris admin d'org — registre système).
**Dépend de :** STORY-122.1

### Tâche 2 : Rôle minimum sur les 5 canaux WebSocket
**Objectif :** Appliquer la matrice WS : terminal → operator+, 4 autres canaux → viewer (tout authentifié actif).
**Fichiers :**
- `backend/app/api/v1/websockets.py` — Modifier — Dans `container_terminal_websocket` (l. 108) : après `user = Depends(get_current_user_ws)` (ou récupération équivalente), appeler `await ensure_role_ws(user, "operator")` **avant `websocket.accept()`** — refus 1008 sans acceptation ; les 4 autres canaux : `await ensure_role_ws(user, "viewer")` (garde homogène, documente l'exigence matricielle) ; imports depuis `...auth.rbac` ; docstrings mises à jour (rôle minimum par canal) ;
- `backend/app/auth/rbac.py` — Modifier (si absent) — Exposer `async def ensure_role_ws(user: User, minimum_role: str) -> None` : lève `WebSocketException(1008, "Insufficient permissions")` si `AuthorizationService.role_at_least(...)` False ; log warning avec path/user_id. (Complète la Tâche 3 de 122.1 si `require_role_ws` seul y a été livré.)
**Exigences sécurité :** Refus **avant accept** (pas de canal ouvert même brièvement) ; user_id loggé, jamais le token.
**Dépend de :** Tâche 1 (module rbac), STORY-122.1

### Tâche 3 : Tests matrice admin + WebSocket
**Objectif :** Vérifier les 403 admin/* par rôle et les refus 1008 WS par canal/role.
**Fichiers :**
- `backend/tests/unit/test_api/test_admin_rbac.py` — Créer — (HTTP, fixtures par rôle) : viewer/operator/admin-d'org → 403 sur échantillon GET (`/admin/stacks/definitions`) + POST (`/admin/stacks/import`) + DELETE ; superuser → 200 (mock services) ; 401 sans token ; `test_admin_routes_count_unchanged` (15 routes préfixe `/api/v1/admin/`) ;
- `backend/tests/unit/test_websocket/test_ws_rbac.py` — Créer — (pattern `test_ws_auth.py` : paramétrage canaux) : viewer → terminal refusé **1008 avant accept**, logs/stats/deployment/general autorisés ; operator+ → terminal accepté (handshake puis fermeture propre) ; user inactif → 1008 partout (non-régression) ; `disable_auth` → superadmin auto-login, terminal accepté ;
- Vérifier la non-régression de [`test_ws_isolation_1213.py`](../../backend/tests/unit/test_websocket/test_ws_isolation_1213.py) et [`test_ws_auth.py`](../../backend/tests/unit/test_websocket/test_ws_auth.py) (commandes).
**Exigences sécurité :** 401/403 HTTP ; 1008 WS ; tests avant/après accept.
**Dépend de :** Tâches 1, 2

## Tests à écrire

> Détail en Tâche 3.

### Unitaires Backend
- `backend/tests/unit/test_api/test_admin_rbac.py` — matrice admin (403 tous rôles non-SA, 200 SA, count 15)
- `backend/tests/unit/test_websocket/test_ws_rbac.py` — matrice WS (viewer 1008 terminal, operator OK, inactif 1008, disable_auth)

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_api/test_admin_rbac.py backend/tests/unit/test_websocket/test_ws_rbac.py -v
poetry run pytest backend/tests/unit/test_websocket/ -v  # non-régression WS complète
make backend-lint && make backend-typecheck
```

## État d'avancement technique
- [x] Tâche 1 : `require_super_admin` sur admin/stacks_management.py (15 routes)
- [x] Tâche 2 : Rôles minimums sur les 5 canaux WebSocket (ensure_role_ws)
- [x] Tâche 3 : Tests matrice admin + WS
- [x] Lint & typecheck OK

## Notes d'implémentation

**Date :** 2026-09-12

### Fichiers modifiés/créés
- `backend/app/api/v1/admin/stacks_management.py` : 15 occurrences `Depends(get_current_superadmin)` → `Depends(require_super_admin)` (import `from ....auth.rbac import require_super_admin`, retrait de l'import legacy) ; aucun changement de path/response_model ;
- `backend/app/auth/rbac.py` : ajout de `ensure_role_ws(websocket, user, minimum_role, session)` — vérificateur manuel levant `WebSocketException(1008, "Insufficient permissions")` avec log warning (path, user_id — jamais de token) ;
- `backend/app/api/v1/websockets.py` : garde `await ensure_role_ws(websocket, user, "viewer", session)` sur les 3 canaux à token query-param (deployment logs, container logs, container stats) **avant accept** ; docstrings RBAC par canal ;
- `backend/app/websocket/terminal.py` : garde `ensure_role_ws(..., "operator", ...)` immédiatement après l'auth « premier message » (canaux non-Depends) + audit `log_terminal_audit` sur refus ;
- `backend/app/websocket/general.py` : garde `ensure_role_ws(..., "viewer", ...)` après auth premier message ;
- `backend/tests/unit/test_api/test_admin_rbac.py` : créé — matrice 403 (viewer/operator/admin d'org sur GET+POST+PATCH+DELETE), superuser 200/404, 401 sans token, garde structurelle 15 routes ;
- `backend/tests/unit/test_websocket/test_ws_rbac.py` : créé — matrice WS par canal (viewer 1008 terminal + refus message, operator/admin acceptés, audit loggué, rôle corrompu refusé avant accept, canaux lecture viewer OK, inactif 1008 partout, disable_auth OK).

### Décisions techniques
- `ensure_role_ws` retenu (vs `require_role_ws` décorateur) pour tous les canaux : FastAPI n'applique pas aussi directement les dépendances factory paramétrées sur `@router.websocket` — conforme au mécanisme préconisé par l'analyse ;
- Canaux terminal/général (auth « premier message ») : garde posée dans les handlers (`websocket/terminal.py`, `websocket/general.py`) juste après `authenticate_ws_first_message` — conforme à la variante documentée (« ou immédiatement après l'authentification premier message ») ; refus 1008 sans exécuter la logique du canal ;
- Arbitrage conservateur confirmé : même les GET admin restent `super_admin` (registre système global, garde-fou « ne pas élargir »).

### Divergences par rapport à l'analyse
- Tâche 2 : la story plaçait la garde terminal dans `websockets.py` ; l'implémentation la place dans le handler `websocket/terminal.py` car ce canal s'authentifie par premier message (pas de `Depends(get_current_user_ws)` dans la signature) — intention préservée (refus 1008 avant exécution du canal), emplacement adapté. Même chose pour le canal général.

### Difficultés rencontrées
- Le répertoire `stacks_definitions` est résolu via `__file__` dans le routeur : le test superuser `/definitions` substitue un répertoire temporaire (monkeypatch `Path.__truediv__`) pour valider le contrat 200 sans dépendre du layout d'exécution.

### Tests ajoutés
- `backend/tests/unit/test_api/test_admin_rbac.py` : 18 tests — matrice 403 × rôles × verbes, superuser 200/404, 401 sans token, inventaire 15 routes ;
- `backend/tests/unit/test_websocket/test_ws_rbac.py` : 12 tests (dont 3 paramétrés) — matrice complète par canal.

### Résultats de validation (venv `.venv-test`, Python 3.11)
- `pytest backend/tests/unit/test_api/test_admin_rbac.py backend/tests/unit/test_websocket/test_ws_rbac.py -v` : **30 passed** ;
- `pytest backend/tests/unit/test_websocket/ -v` (non-régression) : **68 passed** ;
- isort/black/flake8 sur les 10 fichiers touchés : **OK** ;
- mypy `app/` : **0 erreur sur les fichiers de la story** (24 erreurs préexistantes hors périmètre — stats.py, targets/connectivity.py, etc.).
