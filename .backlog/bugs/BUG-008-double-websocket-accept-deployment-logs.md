# BUG-008 : Double `websocket.accept()` sur le canal `deployment_logs` — Starlette rejette le second accept, le client reçoit `error` au lieu du statut initial

**Statut :** DONE
*(transitions : NEW → CONFIRMED le 2026-10-24 — bug reproduit et validé par l'analyse technique, démontré sans contournement par le test `xfail(strict=True)` de STORY-165 → IN_PROGRESS le 2026-10-24 → REVIEW/DONE le 2026-10-24 — correction implémentée, tests verts sans modification des tests sécurité)*
**Gravité :** Majeur
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend) — détecté lors de STORY-165 (tests WebSocket)

## Reproduction

1. Se connecter au canal `/ws/deployment/{id}` en conditions réelles (serveur Starlette/uvicorn, token valide, accès autorisé).
2. L'endpoint [`deployment_logs`](../../backend/app/websocket/deployment_logs.py:102) appelle `await websocket.accept()` (l.102).
3. À la ligne 115, [`manager.connect(websocket, deployment_id)`](../../backend/app/websocket/connection_managers.py:129) ré-exécute `await websocket.accept()`.
4. Starlette lève : `Expected ASGI message "websocket.send" or "websocket.close", but got 'websocket.accept'` — la connexion bascule dans la branche d'erreur du handler → **le client reçoit un message `error` au lieu du statut initial `{"type": "status", …}`** attendu par la spec (§9.2 de [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md)).

## Comportement attendu

Une seule acceptance par connexion : l'endpoint accepte la connexion **ou** délègue l'acceptance au manager, jamais les deux. Le client autorisé doit recevoir le message de statut initial (`{"type": "status", "data": {"status", "deployment_id", "name"}}`) puis les événements `DEPLOYMENT_LOGS_UPDATE` — conformément au portage §9.2 testé par STORY-165.

## Comportement actuel

Le double accept fait échouer le canal en conditions réelles : le chemin nominal (`manager.connect` → statut initial → boucle ping/pong → streaming logs) n'est jamais atteint. **Ce bug passait inaperçu** car les anciens tests validaient le premier message avec `assert type in ("error", "status", "initial")` — l'`error` issu du crash étant accepté comme nominal. Les tests STORY-165 l'ont isolé via le contournement `_register_only_connect` (patch qui enregistre la connexion **sans** ré-accepter) pour les parcours nominaux, et le démontrent sans contournement en `xfail(strict=True)`.

## Test documentant le bug

- Constante [`DOUBLE_ACCEPT_BUG`](../../backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py:63) (backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py, l.62-64) ;
- [`test_initial_status_without_connect_workaround`](../../backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py:376) — `xfail(strict=True)` : sans contournement, le client reçoit `error` ; une fois corrigé, le test XPASS et **échoue** → retirer alors le marquage **et** le contournement `_register_only_connect` (l.223).

## Résolution

**Corrigé le 2026-10-24** — option retenue : chemin d'enregistrement sans acceptance dans le manager.

### Correction implémentée

- [`ConnectionManager.connect()`](../../backend/app/websocket/connection_managers.py:120) — nouveau paramètre `accept_connection: bool = True` : l'accept devient conditionnel (`if accept_connection: await websocket.accept()`), l'enregistrement sous lock et le log sont inchangés ; docstring documentant le paramètre et le cas d'usage double-accept de `deployment_logs`. Défaut `True` → rétrocompatible avec [`batch.py:123`](../../backend/app/websocket/batch.py:123) (pattern manager-accept sain, non modifié).
- [`deployment_logs.py:115`](../../backend/app/websocket/deployment_logs.py:113) — l'endpoint appelle `await manager.connect(websocket, deployment_id, accept_connection=False)` (il a déjà accepté en l.102, accept précoce indispensable à la branche 404/403 error + close 1008) ; commentaire mis à jour. **Une seule acceptance par connexion.**

### Tests de non-régression

- [`test_ws_deployment_logs_e2e.py`](../../backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py) : marquage `xfail(strict=True)` retiré de `test_initial_status_without_connect_workaround` (devenu garde-fou nominal : premier message = `status` **sans** contournement) ; helper `_register_only_connect` supprimé ainsi que tous ses usages (les 6 parcours nominaux passent par le vrai `manager.connect`) ; constante `DOUBLE_ACCEPT_BUG` supprimée ; docstrings module/classe mises à jour. Tests sécurité (404/403/401 + close 1008, superadmin bypass) **inchangés et verts**.
- [`test_connection_managers.py`](../../backend/tests/unit/test_websocket/test_connection_managers.py) : 2 nouveaux tests du paramètre — `test_connect_with_accept_false_registers_without_accept` (accept jamais appelé + connexion enregistrée) et `test_connect_default_accepts` (contrat du défaut rétrocompatible : accept awaited exactly once).

### Validation

- Ciblée : `pytest test_ws_deployment_logs_e2e.py test_connection_managers.py` → **63 passed, 0 xfailed** (`connection_managers.py` 100 % couverture, `deployment_logs.py` 96 %).
- Élargie : `pytest backend/tests/unit/test_websocket/` → **416 passed, 0 xfailed** (BUG-008 était le dernier xfail du module).
- Non-régression explicite : `pytest test_connection_managers.py test_ws_batch.py` → **62 passed** (canal batch = pattern manager-accept intact).
- Qualité : `black --check` + `isort --check` + `flake8` OK sur les 4 fichiers modifiés.

## Analyse technique

### Cause racine

Le handler [`deployment_logs_websocket_endpoint`](../../backend/app/websocket/deployment_logs.py:62) exécute **deux acceptances ASGI** sur la même connexion :

1. [`await websocket.accept()`](../../backend/app/websocket/deployment_logs.py:102) — accept explicite de l'endpoint, **nécessaire** : la branche d'erreur 404/403 (l.104-111) envoie un message applicatif `{"type": "error", …}` **puis** `close(1008)`, ce qui exige une connexion déjà acceptée (impossible d'émettre un message avant l'accept en ASGI) ;
2. [`manager.connect(websocket, deployment_id)`](../../backend/app/websocket/deployment_logs.py:115) — or [`ConnectionManager.connect`](../../backend/app/websocket/connection_managers.py:120) fait lui-même [`await websocket.accept()`](../../backend/app/websocket/connection_managers.py:128) avant l'enregistrement.

Starlette maintient une machine à états par connexion (`application_state`) : après la première acceptance, seuls `websocket.send` / `websocket.close` sont attendus. Le second accept lève `AssertionError: Expected ASGI message "websocket.send" or "websocket.close", but got 'websocket.accept'` — attrapée par le `except Exception` générique (l.169-174) → le client reçoit `{"type": "error", "message": "…"}` au lieu du statut initial `{"type": "status", …}` attendu par la spec (§9.2 de [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md)). **Le chemin nominal du canal n'est jamais atteint en conditions réelles** (serveur Starlette/uvicorn) : streaming logs, broadcast `DEPLOYMENT_LOGS_UPDATE` et boucle ping/pong sont inaccessibles.

### Pourquoi le bug est passé inaperçu

- Les tests d'auth historiques validaient le premier message avec une assertion permissive : [`assert message["type"] in ("error", "status", "initial")`](../../backend/tests/unit/test_websocket/test_ws_auth.py:260) (idem [`test_ws_rbac.py:525`](../../backend/tests/unit/test_websocket/test_ws_rbac.py:525)) — le `error` issu du crash était accepté comme nominal ;
- Les autres consommateurs de `manager.connect` ne déclenchent pas le bug : en production seuls deux appelants existent — [`batch.py:123`](../../backend/app/websocket/batch.py:123) (sans accept préalable → pattern sain) et le handler fautif ; les tests unitaires du manager utilisent des `AsyncMock` qui ne valident pas les messages ASGI (le double accept y est invisible).

### Patterns existants (choix de correction)

Le module porte **deux patterns d'acceptance** cohabitant légitimement :

| Pattern | Illustration | Manager concerné |
|---------|--------------|------------------|
| Endpoint accepte + manager **enregistre seulement** | [`general.py:79`](../../backend/app/websocket/general.py:79) + [`UserConnectionManager.add_connection`](../../backend/app/websocket/connection_managers.py:218) (aucun accept) | `UserConnectionManager` |
| Manager fait l'accept + enregistre | [`batch.py:121-123`](../../backend/app/websocket/batch.py:121) (commentaire explicite « jamais de double accept ») | `ConnectionManager` |

Le bug vient du mélange des deux patterns sur un seul canal. **Option retenue : paramètre `accept_connection: bool = True` sur `ConnectionManager.connect`** — le handler passé `accept_connection=False` puisqu'il a déjà accepté (l'accept précoce est indispensable pour la branche 404/403 error+close).

Options écartées :
- *Retirer l'accept de l'endpoint et déléguer au manager* : impossible sans restructurer — la vérification d'accès (404/403) survient **entre** l'accept et l'enregistrement, et doit pouvoir envoyer un message d'erreur applicatif avant le close 1008 (contrat testé E2E, §9.3) ;
- *Retirer l'accept de `ConnectionManager.connect`* : casserait [`batch.py`](../../backend/app/websocket/batch.py:123) (plus aucune acceptance → handshake jamais complété) et le test de contrat [`test_connect_accepts_and_registers_by_deployment`](../../backend/tests/unit/test_websocket/test_connection_managers.py:194) ;
- *Vérifier l'accès avant l'accept et refuser le handshake* : changerait le contrat client (refus handshake au lieu du message `error` + close 1008) et casserait les 3 tests E2E 404/403/401 — hors périmètre d'un bugfix.

La correction est rétrocompatible : `batch.py` (défaut `True`) et les tests du manager existants restent intacts.

### Checklist sécurité (`.roo/rules/40-security.md`) — endpoint exposé

- **AuthN** : handshake protégé par `get_current_user_ws` (query param `?token=`, refus 1008 avant le handler) — inchangé par la correction ;
- **AuthZ** : [`ensure_role_ws(websocket, user, "viewer", session)`](../../backend/app/api/v1/websockets.py:118) dans le routeur (STORY-122.6) **+** [`verify_deployment_access`](../../backend/app/websocket/deployment_logs.py:29) (RBAC organisation via `UserOrganizationService.is_member`, STORY-121.3, superuser bypass) — inchangés ;
- **Isolation** : la branche 403 (org étrangère) reste couverte E2E — la correction ne touche que le chemin **après** validation ;
- **Exposition de données** : le statut initial ne contient que `status`/`deployment_id`/`name` — aucun champ sensible ;
- **Audit** : canal de lecture, pas d'audit supplémentaire requis ;
- **Conclusion** : aucune faille introduite ou corrigée par le bug — c'est une régression fonctionnelle (disponibilité du canal), pas une faille de sécurité. Les tests sécurité existants (401/403/404 + close 1008) restent valides et doivent passer **sans modification**.

## Contexte technique

Fichiers de production impliqués :

| Fichier | Rôle dans le bug |
|---------|------------------|
| [`backend/app/websocket/deployment_logs.py`](../../backend/app/websocket/deployment_logs.py) | Handler fautif : accept l.102 + `manager.connect` l.115 (ligne à modifier) |
| [`backend/app/websocket/connection_managers.py`](../../backend/app/websocket/connection_managers.py) | [`ConnectionManager.connect`](../../backend/app/websocket/connection_managers.py:120) : signature à étendre (`accept_connection: bool = True`) |
| [`backend/app/websocket/batch.py`](../../backend/app/websocket/batch.py) | Second appelant de `connect` — **non modifié** (défaut `True`), non-régression à vérifier |
| [`backend/app/api/v1/websockets.py`](../../backend/app/api/v1/websockets.py) | Route `/deployments/{deployment_id}/logs` (l.71-119) — AuthN/AuthZ du canal, référence non modifiée |

Fichiers de tests impliqués :

| Fichier | Impact |
|---------|--------|
| [`backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py`](../../backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py) | Retrait `xfail(strict=True)` + contournement `_register_only_connect` + constante `DOUBLE_ACCEPT_BUG` + docstring |
| [`backend/tests/unit/test_websocket/test_connection_managers.py`](../../backend/tests/unit/test_websocket/test_connection_managers.py) | Nouveaux tests du paramètre `accept_connection` |
| [`backend/tests/unit/test_websocket/test_ws_batch.py`](../../backend/tests/unit/test_websocket/test_ws_batch.py) | Non-régression (aucune modification attendue) |

Fichiers de référence (patterns) : [`general.py`](../../backend/app/websocket/general.py) (accept endpoint + enregistrement sans accept), [`test_ws_batch.py:209-211`](../../backend/tests/unit/test_websocket/test_ws_batch.py:209) (E2E premier message d'un canal manager-accept), spec [`WEBSOCKET-REAL-TIME.md`](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) §9.2/§9.3.

## Tâches d'implémentation détaillées

1. **[`connection_managers.py`](../../backend/app/websocket/connection_managers.py)** — Étendre [`ConnectionManager.connect`](../../backend/app/websocket/connection_managers.py:120) avec un paramètre `accept_connection: bool = True` : l'accept l.128 devient conditionnel (`if accept_connection: await websocket.accept()`), l'enregistrement sous lock et le log restent inchangés ; mettre à jour la docstring (documenter le paramètre et le cas d'usage double-accept de `deployment_logs`). Objectif : offrir un chemin d'enregistrement sans acceptance, rétrocompatible (défaut `True`).
2. **[`deployment_logs.py`](../../backend/app/websocket/deployment_logs.py)** — L.115 : appeler `await manager.connect(websocket, deployment_id, accept_connection=False)` (l'endpoint a déjà accepté en l.102) ; ajuster le commentaire l.114 (« Enregistrer la connexion — sans ré-acceptance : la connexion est déjà acceptée l.102 »). Objectif : éliminer le double accept — une seule acceptance par connexion.
3. **[`test_ws_deployment_logs_e2e.py`](../../backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py)** — Retirer le marquage `@pytest.mark.xfail(strict=True, reason=DOUBLE_ACCEPT_BUG)` de [`test_initial_status_without_connect_workaround`](../../backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py:380) (le test devient le garde-fou nominal : premier message = `status` **sans** contournement) ; supprimer le helper [`_register_only_connect`](../../backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py:220) et tous ses usages (tests nominaux l.291/313/328/343/468/513), la constante `DOUBLE_ACCEPT_BUG` (l.63-70), et mettre à jour la docstring du module (l.23-34 : le bug est corrigé). Objectif : les parcours nominaux passent par le vrai `manager.connect`.
4. **[`test_connection_managers.py`](../../backend/tests/unit/test_websocket/test_connection_managers.py)** — Dans `TestConnectionManagerConnectDisconnect`, ajouter : (a) `test_connect_with_accept_false_registers_without_accept` — `accept_connection=False` → `websocket.accept` **non** appelé + connexion enregistrée ; (b) `test_connect_default_accepts` — appel sans paramètre → `accept` awaited exactly once (contrat du défaut rétrocompatible). Objectif : couvrir le nouveau paramètre des deux côtés.
5. **Validation ciblée** — `poetry run pytest backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py backend/tests/unit/test_websocket/test_connection_managers.py -v` : tous verts, **0 xfail** sur ces fichiers. Objectif : preuve de la correction (l'ex-xfail XPASS retiré devient passant).
6. **Validation élargie + qualité** — `poetry run pytest backend/tests/unit/test_websocket/ -v` (attendu : **0 xfailed sur tout le module** — BUG-008 était le dernier ; tous les tests nominaux deployment_logs désormais sans contournement) puis `black --check` + `isort --check` + `flake8` sur les 4 fichiers modifiés. Objectif : non-régression du module temps réel (notamment `test_ws_batch.py`, `test_ws_auth.py`, `test_ws_rbac.py`, `test_broadcasting.py`) et conformité lint.

## Tests à écrire

Conformes à `.roo/rules/35-testing-quality-gates.md` — le canal est déjà couvert E2E (STORY-165) ; cette correction **transforme** les tests existants plutôt qu'elle n'en crée ex nihilo :

**[`backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py`](../../backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py)** (modification — tâche 3) :

- Nominal §9.2 : `test_initial_status_without_connect_workaround` (l.380) — **retirer `xfail(strict=True)`** : sans contournement, premier message = `{"type": "status", "data": {status, deployment_id, name}}` (le test tel qu'écrit devient la non-régression du bug) ;
- Nominaux (statut initial, ping/pong, déconnexion→manager vidé, broadcast `DEPLOYMENT_LOGS_UPDATE`, superadmin org étrangère, expiration muette) : exécutés **sans** `_register_only_connect` — le vrai chemin de production est désormais testé ;
- Sécurité (déjà présents, doivent rester verts sans modification — aucune régression AuthN/AuthZ) : 404 unknown deployment → `error` + close 1008 ; 403 org étrangère → `error` + close 1008 ; 401 user None → HTTPException (branche unitaire) ; superadmin bypass.

**[`backend/tests/unit/test_websocket/test_connection_managers.py`](../../backend/tests/unit/test_websocket/test_connection_managers.py)** (ajouts — tâche 4) :

- Cas nominal : `connect(websocket, "dep-1")` sans paramètre → accept awaited once + enregistré (défaut rétrocompatible — batch.py) ;
- Cas nominal : `connect(websocket, "dep-1", accept_connection=False)` → accept **jamais** appelé + enregistré (chemin deployment_logs).

**Non-régression (exécution seule, aucune écriture)** : `test_ws_batch.py` (canal batch = manager-accept intact), `test_ws_auth.py` + `test_ws_rbac.py` (handshake refusé/accepté — l'assertion permissive l.260 reste valide pour les canaux Docker ; sur le canal deployment_logs elle recevra désormais `status`), `test_broadcasting.py`.

## État d'avancement technique

- [x] Tâche 1 — `ConnectionManager.connect` : paramètre `accept_connection: bool = True` (accept conditionnel + docstring)
- [x] Tâche 2 — `deployment_logs.py:115` : `manager.connect(..., accept_connection=False)` + commentaire
- [x] Tâche 3 — `test_ws_deployment_logs_e2e.py` : xfail retiré, `_register_only_connect` supprimé, docstring mise à jour
- [x] Tâche 4 — `test_connection_managers.py` : 2 tests du paramètre `accept_connection`
- [x] Tâche 5 — Validation ciblée (2 fichiers de tests : tous verts, 0 xfail)
- [x] Tâche 6 — Validation élargie (`test_websocket/` : 0 xfailed) + black/isort/flake8 sur les 4 fichiers

## Notes d'implémentation

### Fichiers modifiés

| Fichier | Changement |
|---------|------------|
| [`backend/app/websocket/connection_managers.py`](../../backend/app/websocket/connection_managers.py) | `connect()` : signature étendue `accept_connection: bool = True`, accept conditionnel, docstring enrichie |
| [`backend/app/websocket/deployment_logs.py`](../../backend/app/websocket/deployment_logs.py) | Appel `manager.connect(..., accept_connection=False)` + commentaire « sans ré-acceptance » |
| [`backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py`](../../backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py) | xfail strict retiré, `_register_only_connect` + `DOUBLE_ACCEPT_BUG` supprimés, 6 parcours nominaux sur le vrai chemin, docstrings à jour |
| [`backend/tests/unit/test_websocket/test_connection_managers.py`](../../backend/tests/unit/test_websocket/test_connection_managers.py) | +2 tests (`accept_connection=False` sans accept, défaut = accept once) |

### Décisions techniques

- Correction appliquée exactement selon l'option retenue par l'analyse (paramètre `accept_connection`, défaut `True`) — aucune des options écartées n'a été revisitée ; `batch.py` non touché (défaut rétrocompatible vérifié par test).
- Ordre des tâches respecté : le xfail a été retiré (tâche 3) **après** la correction (tâches 1-2) et aucune exécution pytest intermédiaire n'a été lancée entre les deux, évitant tout XPASS = échec de suite.
- `test_connect_default_accepts` ajoute un test dédié au contrat du défaut alors que `test_connect_accepts_and_registers_by_deployment` le couvrait déjà de fait — exigence explicite de la tâche 4 (contrat rétrocompatible garanti par deux gardes-fous).

### Divergences par rapport à l'analyse

- Aucune divergence fonctionnelle. Point de forme : l'instruction de clôture demandait de « cocher la case BUG-008 dans la liste de l'epic EPIC-013 » ; la « Liste des Stories liées » de l'epic ne contient pas de case pour les bugs (pattern établi par BUG-005/006/007 : traçabilité via une note ✅ dans « Notes de conception »). Ce pattern a été suivi — note ✅ BUG-008 ajoutée dans l'epic.
- `black` a reformatté le fichier de tests E2E après édition (ré-indentation des blocs dé-dédentés) ; tests re-exécutés post-formatage : 63 passed.

### Difficultés rencontrées

- Aucune difficulté bloquante. Un `apply_diff` multi-blocs n'a été appliqué que partiellement (2 usages résiduels de `_register_only_connect`), détecté par relecture + `grep` puis corrigé immédiatement — vérification finale : plus aucune référence au contournement dans le module.
