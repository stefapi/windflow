# BUG-008 : Double `websocket.accept()` sur le canal `deployment_logs` — Starlette rejette le second accept, le client reçoit `error` au lieu du statut initial

**Statut :** NEW
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

*(à compléter à la résolution — deux options : retirer `websocket.accept()` de l'endpoint deployment_logs.py:102 en déléguant au manager, ou donner au manager un chemin d'enregistrement sans accept pour ce canal ; harmoniser avec les autres canaux qui utilisent `manager.connect`)*
