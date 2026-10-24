# BUG-009 : `WebSocketService.disconnect()` (frontend) ne purge pas l'état — `authToken`, `authenticated`, `listeners`, `serverSubscriptions` survivent à la déconnexion

**Statut :** NEW
**Gravité :** Majeur
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend) — détecté lors de STORY-165 (tests WebSocket, Tâche 10 frontend)

## Reproduction

1. Dans un onglet, l'utilisateur A se connecte au canal général via [`WebSocketService`](../../frontend/src/services/websocket.ts) (auth JWT, souscriptions serveur `subscribe`/`deployment_logs` tracées dans `serverSubscriptions`).
2. A se déconnecte (logout applicatif appelant [`disconnect()`](../../frontend/src/services/websocket.ts:149), fermeture volontaire) — la socket est fermée et la politique de reconnexion arrêtée, **mais** les champs privés [`authToken`](../../frontend/src/services/websocket.ts:31), [`authenticated`](../../frontend/src/services/websocket.ts:30), `listeners` et [`serverSubscriptions`](../../frontend/src/services/websocket.ts:28) ne sont **jamais réinitialisés**.
3. L'utilisateur B (ou A re-login) ouvre une session dans le **même onglet** sur le singleton : à la reconnexion, `resubscribeActiveTopics()` rejoue les abonnements serveur du précédent, et l'état d'auth (`authToken` périmé de A, `authenticated=true`) est hérité.

## Comportement attendu

`disconnect()` doit réinitialiser l'état de session du singleton : `authToken = null`, `authenticated = false`, `listeners` vidés, `serverSubscriptions` vidées — un `connect()` ultérieur (nouvel utilisateur) part d'un état neutre, sans hériter des abonnements serveur ni de l'identité d'authentification de la session précédente.

## Comportement actuel

**Fuite d'état entre sessions logout/login successives dans un même onglet** : le successeur hérite des `serverSubscriptions` de l'ancien utilisateur (rejeu automatique à la reconnexion — abonnements serveur résiduels, données reçues pour des déploiements/événements auxquels il ne s'est pas abonné) et d'un `authToken` obsolète (tentative d'auth WS avec le token du précédent). Détail de sécurité : le token de l'utilisateur A reste en mémoire au-delà de sa session, et l'état `authenticated=true` est mensonger avant toute auth du nouvel utilisateur.

## Test documentant le bug

- Contournement dans [`websocket-helpers.spec.ts`](../../frontend/tests/unit/services/websocket-helpers.spec.ts:115) (frontend/tests/unit/services/websocket-helpers.spec.ts, beforeEach l.105-131) : reset **explicite** des champs privés du singleton (`internals.authenticated = false`, `internals.authToken = null`, `listeners.clear()`, `serverSubscriptions.clear()`) avec commentaire « champs privés que disconnect() ne purge PAS (sans ce reset, les abonnements des tests précédents seraient rejoués à la première [reconnexion]) ». À la correction, ce reset manuel peut être allégé (il ne sera plus nécessaire) — le conserver d'abord comme garde-fou de non-régression.

## Résolution

*(à compléter à la résolution — piste suggérée : dans `disconnect()`, après fermeture de la socket et arrêt de la politique de reconnexion, réinitialiser les 4 champs privés ; tests : le workaround du beforeEach n'est plus nécessaire si `disconnect()` purge seul)*
