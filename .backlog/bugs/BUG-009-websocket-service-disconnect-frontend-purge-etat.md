# BUG-009 : `WebSocketService.disconnect()` (frontend) ne purge pas l'état — `authToken`, `authenticated`, `listeners`, `serverSubscriptions` survivent à la déconnexion

**Statut :** DONE
*(transitions : NEW → CONFIRMED le 2026-10-24 — cause racine confirmée par lecture du code : [`disconnect()`](../../frontend/src/services/websocket.ts:149) ferme la socket et arrête la politique de reconnexion, mais ne réinitialise aucun des 4 champs privés de session ; CONFIRMED → IN_PROGRESS le 2026-10-24 — implémentation `treat-story` ; IN_PROGRESS → REVIEW → DONE le 2026-10-24 — correction implémentée, 7 tests nouveaux + non-régressions verts, lint/typecheck OK)*
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

## Contexte technique

### Cause racine

[`disconnect()`](../../frontend/src/services/websocket.ts:149) (l.149-157) exécute trois actions — [`reconnect.stop()`](../../frontend/src/services/websocket.ts:151), [`clearReconnectTimer()`](../../frontend/src/services/websocket.ts:152) et fermeture de la socket (`ws.close()` + `ws = null`) — mais **ne réinitialise aucun des 4 champs privés de session** :

| Champ | Déclaration | Fuite après `disconnect()` |
|-------|-------------|----------------------------|
| [`authToken`](../../frontend/src/services/websocket.ts:31) | l.31 | **Toujours** — jamais remis à `null` (seuls `connect`/`authenticateWithToken` l'écrasent) |
| [`listeners`](../../frontend/src/services/websocket.ts:26) | l.26 | **Toujours** — seuls `off()` et la désinscription unitaire vident la Map |
| [`serverSubscriptions`](../../frontend/src/services/websocket.ts:28) | l.28 | **Toujours** — vidée uniquement par `unsubscribe` ciblé dans [`syncServerSubscriptions`](../../frontend/src/services/websocket.ts:303) |
| [`authenticated`](../../frontend/src/services/websocket.ts:30) | l.30 | Remis à `false` **asynchronement** par le `onclose` de la socket fermée (l.105) — jamais synchronement ; fenêtre où [`isAuthenticated()`](../../frontend/src/services/websocket.ts:323) ment |

Deux conséquences au `connect()` suivant (même onglet, singleton l.357) :

- [`resubscribeActiveTopics()`](../../frontend/src/services/websocket.ts:206) rejoue les abonnements serveur du précédent utilisateur (déclenché à `auth_success` → `reconnect.recordOpen()` → `onResubscribe`) ;
- [`onopen`](../../frontend/src/services/websocket.ts:78) réutilise l'`authToken` périmé (auth WS tentée avec le token du précédent).

**Course du handler fantôme** (découverte complémentaire) : `disconnect()` ne détache pas les handlers de la socket fermée — son `onclose` reste branché sur le service. S'il se déclenche **après** l'authentification de la session suivante (le refresh fait `disconnect(); connect()` en synchrone, mais le close event est asynchrone), il exécute `this.authenticated = false` (l.105) sur l'état de la **nouvelle** session et appelle `recordClose` sur une politique repassée en `connecting` → reconnexion parasite possible. Le détachement des handlers fait donc partie de la correction.

### Contrainte critique : le flux de refresh token compte sur la NON-purge

[`refreshAccessToken()`](../../frontend/src/stores/auth.ts:246) fait [`wsService.disconnect()` puis `wsService.connect(newAccessToken)`](../../frontend/src/stores/auth.ts:273) (l.272-274) **au sein de la même session** (rotation JWT) : ce flux repose aujourd'hui sur la survie de `listeners`/`serverSubscriptions` pour que `resubscribeActiveTopics()` rétablisse les abonnements sur la nouvelle socket. Une purge inconditionnelle naïve casserait le temps réel à chaque refresh : les vues suivant un déploiement cesseraient silencieusement de recevoir les événements (listeners vidés = plus aucun callback, abonnements serveur perdus = plus de rejeu).

**La correction doit donc distinguer fin de session (logout → purge totale) et rotation de token (même session → conservation des abonnements).** À noter : le backend n'offre pas de ré-auth sur connexion ouverte (auth JWT au premier message uniquement — [`authenticate_ws_first_message`](../../backend/app/websocket/general.py:94)), la rotation doit recréer la socket côté client.

### Option retenue

1. [`disconnect()`](../../frontend/src/services/websocket.ts:149) devient **fin de session** : purge inconditionnelle des 4 champs + détachement des handlers de la socket fermée **avant** `close()` (`onclose`/`onmessage`/`onopen`/`onerror` = `null`) — conforme au comportement attendu, sûr par défaut pour tout futur appelant ;
2. Nouvelle méthode publique **`reconnectWithToken(token: string): void`** dédiée à la rotation JWT : `clearReconnectTimer()` + `reconnect.stop()` + détachement des handlers + fermeture de la socket + [`connect(token)`](../../frontend/src/services/websocket.ts:58) (qui remet la politique à zéro depuis `stopped`, l.65-67, et écrase le token) — **sans purger** `listeners`/`serverSubscriptions`, rejoués à l'`auth_success` suivant ;
3. Le seul site d'appel refresh ([`auth.ts:272-274`](../../frontend/src/stores/auth.ts:272)) bascule sur `reconnectWithToken(newAccessToken)` ; le site logout ([`auth.ts:100`](../../frontend/src/stores/auth.ts:100)) reste sur `disconnect()` purgateur — c'est précisément lui qui doit purger.

Options écartées :
- *Purge inconditionnelle seule* : casse le flux refresh token (ci-dessus) ;
- *Paramètre `disconnect({ preserveSession: true })`* : lisibilité moindre au site d'appel (flag booléen) et sémantique floue — l'opération du refresh est une reconnexion, pas une déconnexion ;
- *Ré-auth sur connexion ouverte* : exigerait un handler `auth` côté backend (n'existe pas : premier message uniquement) → évolution backend hors périmètre bugfix.

### Patterns existants à réutiliser

- Tests : mock WebSocket avec statiques standard ([`installWebSocketMock`](../../frontend/tests/unit/services/websocket-helpers.spec.ts:55)), pilotage manuel `onopen`/`onmessage`/`onclose`, timers virtuels, accès aux champs privés via cast (`wsService as unknown as {…}` — l.121-126, pattern déjà établi) ;
- Tests sécurité : le token n'est jamais asserté en clair hors du message d'auth (pattern du describe « sécurité » de [`websocket-helpers.spec.ts`](../../frontend/tests/unit/services/websocket-helpers.spec.ts), l.505-543) ;
- Politique : `reset()` depuis `stopped` au `connect()` (l.65-67) — **aucune modification de [`ws-reconnect.ts`](../../frontend/src/services/ws-reconnect.ts) nécessaire**.

### Checklist sécurité (`.roo/rules/40-security.md`) — service frontend

- **Données sensibles** : `authToken` purgé à `disconnect()` — le JWT de l'utilisateur A ne survit pas à sa session dans la mémoire du service (tâche 1 + test dédié) ;
- **Isolation inter-sessions** : `listeners`/`serverSubscriptions` purgés — l'utilisateur B n'hérite ni des callbacks ni des abonnements serveur de A (le rejeu actuel envoie à B des données de déploiements suivis par A) ;
- **⚠️ Asymétrie backend constatée (hors périmètre, à consigner séparément)** : sur le canal général, [`SubscriptionHandler._handle_deployment_logs`](../../backend/app/websocket/plugins/subscription.py:176) enregistre l'abonnement **sans vérification d'accès** au déploiement (contrairement au canal dédié protégé par [`verify_deployment_access`](../../backend/app/websocket/deployment_logs.py:29)) — le rejeu résiduel de BUG-009 exposait donc réellement des logs d'un déploiement étranger à un utilisateur non autorisé ; la correction frontend supprime le vecteur, mais le durcissement backend (RBAC sur le message `deployment_logs` du canal général) doit faire l'objet d'un **bug backend séparé** — ne pas traiter ici (périmètre strict) ;
- **Audit** : sans objet (service client) ; **Endpoints** : aucun endpoint modifié → pas de tests 401/403 backend à prévoir.

### Fichiers concernés

| Fichier | Rôle dans le bug |
|---------|------------------|
| [`frontend/src/services/websocket.ts`](../../frontend/src/services/websocket.ts) | `disconnect()` à purger + détachement handlers + nouvelle méthode `reconnectWithToken` |
| [`frontend/src/stores/auth.ts`](../../frontend/src/stores/auth.ts) | Site d'appel refresh l.272-274 à basculer (logout l.100 **inchangé**) |
| [`frontend/tests/unit/services/websocket-helpers.spec.ts`](../../frontend/tests/unit/services/websocket-helpers.spec.ts) | Nouveau describe BUG-009 + commentaire du contournement beforeEach l.115-131 |
| [`frontend/tests/unit/stores/auth.spec.ts`](../../frontend/tests/unit/stores/auth.spec.ts) | Mock `wsService` étendu (`reconnectWithToken`) + test du site d'appel refresh |
| [`frontend/tests/unit/services/websocket.spec.ts`](../../frontend/tests/unit/services/websocket.spec.ts) | Non-régression attendue **sans modification** (beforeEach l.81 devient auto-suffisant) |
| [`docs/technical_specs/WEBSOCKET-REAL-TIME.md`](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) | §8.5 client type : documenter `disconnect()` purge + `reconnectWithToken` |

## Dépendances

- **Pré-requis** : aucun — bug autonome frontend ; la suite de tests WebSocket existante (STORY-164.3 pour `websocket.spec.ts`/`ws-reconnect.spec.ts`, STORY-165 T10 pour `websocket-helpers.spec.ts`) sert de base directe.
- **Bugs liés (corrigés)** : BUG-005/006/007/008 (module `backend/app/websocket/`, EPIC-013) — aucune interaction de code (BUG-009 est frontend) ; cohérence de format et de démarche reprise (cause racine → option retenue → tests de non-régression).
- **STORY-164.3** : la rotation conserve le pattern « politique remise à zéro au `connect()` après `stopped` » — contrat de `ws-reconnect.ts` intact.
- **Services externes** : aucun (WebSocket mockée dans tous les tests ; pas de backend requis).
- **Hors périmètre signalé** : durcissement RBAC backend du message `deployment_logs` sur canal général (voir checklist sécurité) → bug séparé à consigner ; ré-auth sur connexion ouverte → évolution backend éventuelle.

## Tâches d'implémentation détaillées

1. **[`websocket.ts`](../../frontend/src/services/websocket.ts) — purger `disconnect()`** : après `reconnect.stop()` + `clearReconnectTimer()`, (a) détacher les handlers de la socket **avant** `close()` (`this.ws.onclose = null; this.ws.onmessage = null; this.ws.onopen = null; this.ws.onerror = null` — neutralise la course du handler fantôme) ; (b) fermer puis `this.ws = null` (inchangé) ; (c) purger l'état de session : `this.authenticated = false`, `this.authToken = null`, `this.listeners.clear()`, `this.serverSubscriptions.clear()` ; (d) docstring : « Fin de session — réinitialise tout l'état (token, auth, listeners, abonnements serveur) ; un `connect()` ultérieur part d'un état neutre. Pour une rotation de token en session, utiliser `reconnectWithToken()`. ». Vigilance : ordre détachement → close → purge ; les fonctions de désinscription déjà retournées par `on()` restent inoffensives sur une Map vidée (`off()` est un no-op).
2. **[`websocket.ts`](../../frontend/src/services/websocket.ts) — ajouter `reconnectWithToken(token: string): void`** (public, après `disconnect()`) : `clearReconnectTimer()` + `this.reconnect.stop()` + détachement des handlers + `this.ws?.close(); this.ws = null` si socket présente, puis `this.connect(token)` — **sans purger** `listeners`/`serverSubscriptions` (même session, rejeu par `resubscribeActiveTopics()` à l'`auth_success`). Docstring : rotation JWT (refresh token), pourquoi la purge est absente, référence au flux [`refreshAccessToken`](../../frontend/src/stores/auth.ts:246). Vigilance : ne pas appeler `reconnect.reset()` manuellement — `connect()` gère le retour depuis `stopped` (l.65-67) ; gérer le cas socket absente (`this.ws === null` → simplement `connect(token)`).
3. **[`auth.ts`](../../frontend/src/stores/auth.ts) — basculer le site refresh** : l.272-274, remplacer `wsService.disconnect(); wsService.connect(newAccessToken)` par `wsService.reconnectWithToken(newAccessToken)` (commentaire « Rotation JWT même session : conserve listeners/abonnements serveur — BUG-009 »). Vigilance : le logout (l.100) reste sur `disconnect()` purgateur — **ne pas le modifier**.
4. **[`websocket-helpers.spec.ts`](../../frontend/tests/unit/services/websocket-helpers.spec.ts) — describe BUG-009 + contournement** : (a) ajouter le describe `'BUG-009 : disconnect() purge l'état de session'` avec les 6 tests listés en « Tests à écrire » ; (b) mettre à jour le commentaire du beforeEach (l.115-119) : le reset explicite l.121-130 est **conservé** comme garde-fou de non-régression (conformément à ce fichier bug), mais documenté comme redondant depuis la correction (`disconnect()` purge seul). Vigilance : conserver le cast `internals` existant pour les assertions d'état (pattern établi).
5. **[`auth.spec.ts`](../../frontend/tests/unit/stores/auth.spec.ts) — test du site d'appel refresh** : étendre le mock `vi.mock('@/services/websocket', …)` (l.9-18) avec `reconnectWithToken: vi.fn()` (default + export nommé si présent) ; mocker `authApi.refreshToken` (payload `{ access_token, refresh_token }`) et tester que `refreshAccessToken()` appelle `wsService.reconnectWithToken` avec le nouveau token — et **pas** `disconnect()`. Vigilance : le store doit avoir un `refresh_token` en état initial (le setter via `login` mocké ou état direct).
6. **[`WEBSOCKET-REAL-TIME.md`](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) — doc client type (§8.5)** : documenter la sémantique `disconnect()` = fin de session (état réinitialisé) et `reconnectWithToken(token)` = rotation JWT sans perte d'abonnements, avec le contre-exemple du bug (fuite d'état inter-sessions) — enrichir la ligne « Auth » du tableau §8.5 (« nettoyer la session ») ou ajouter une ligne « Déconnexion ». Mise à jour documentaire seule.
7. **Validation ciblée** : `cd frontend && pnpm test -- tests/unit/services/websocket-helpers.spec.ts tests/unit/services/websocket.spec.ts tests/unit/stores/auth.spec.ts` — tous verts, `websocket.spec.ts` **sans aucune modification** (le test `disconnect() arrête la politique` l.187 et le rejeu d'abonnements l.145 doivent rester verts tels quels).
8. **Validation élargie + qualité** : `pnpm test -- tests/unit/services tests/unit/composables tests/unit/stores` (non-régression composables consommateurs `connectWithAuth` — `useDeploymentLogs`, `useDeploymentWebSocket`) puis `pnpm lint` + `pnpm typecheck` (tsc strict : signature publique `reconnectWithToken` typée, pas de `any`).

## Tests à écrire

Conformes à `.roo/rules/35-testing-quality-gates.md` — nouveau describe dans [`websocket-helpers.spec.ts`](../../frontend/tests/unit/services/websocket-helpers.spec.ts) (patterns du fichier : mock WebSocket, `openAndAuthenticate()`, `sentParsed()`, timers virtuels) :

**`disconnect()` — purge de fin de session :**

- `test: disconnect() réinitialise authToken, authenticated, listeners et serverSubscriptions` — connect('jwt-a') + auth + `send('subscribe', …)` + `on(cb)`, puis `disconnect()` → cast internals : `authToken === null`, `authenticated === false`, `listeners.size === 0`, `serverSubscriptions.size === 0` ; `isAuthenticated() === false` ;
- `après disconnect(), la session suivante ne rejoue PAS les abonnements du précédent` — utilisateur A s'abonne (`subscribe system_event` + `deployment_logs`), `disconnect()`, puis connect('jwt-b') + `openAndAuthenticate()` → sur la nouvelle socket : **aucun** message `subscribe`/`deployment_logs` rejoué, seul l'auth avec `jwt-b` ;
- `sécurité : après disconnect(), le token de l'ancienne session n'est plus jamais émis` — connect('jwt-a') + auth, `disconnect()`, connect('jwt-b') + open → aucun message de la nouvelle socket ne contient `jwt-a` ; l'unique message `auth` porte `jwt-b` (pattern sécurité l.505-543 : le token n'est asserté que dans le message d'auth) ;
- `les listeners de l'ancienne session ne reçoivent plus d'événements` — `on(cb)` en session A, `disconnect()`, re-login session B + auth, émission d'un événement du type écouté → `cb` **jamais** appelé.

**`reconnectWithToken()` — rotation JWT en session (flux refresh) :**

- `reconnectWithToken conserve listeners et abonnements serveur et les rejoue à la reconnexion` — session A authentifiée avec abonnement `system_event` + listener `cb` ; `reconnectWithToken('jwt-b')` + `openAndAuthenticate()` → nouvelle socket : auth porte `jwt-b` **et** le `subscribe system_event` est rejoué **et** `cb` reçoit un événement émis ensuite ;
- `reconnectWithToken détache les handlers de l'ancienne socket (aucune reconnexion parasite)` — référence à l'ancienne socket conservée ; après rotation : `oldWs.onclose === null` (détachement prouvé) ; `advanceTimersByTime(60000)` → aucune construction WebSocket supplémentaire au-delà de la rotation (le close event différé de l'ancienne socket ne déclenche rien).

**[`auth.spec.ts`](../../frontend/tests/unit/stores/auth.spec.ts) :**

- `refreshAccessToken bascule la WebSocket via reconnectWithToken (sans disconnect purgeur)` — mock `authApi.refreshToken` résolu ; assertion : `reconnectWithToken` appelé avec le nouveau token, `disconnect` **non** appelé (le site refresh ne doit plus purger).

**Non-régression (exécution seule, aucune écriture)** : [`websocket.spec.ts`](../../frontend/tests/unit/services/websocket.spec.ts) intégralement (reconnexion/backoff, logout sur 1008/épuisement, re-souscription, `disconnect() arrête la politique` l.187), [`ws-reconnect.spec.ts`](../../frontend/tests/unit/services/ws-reconnect.spec.ts), composables `useDeploymentLogs`/`useDeploymentWebSocket` (consommateurs de `connectWithAuth`).

## État d'avancement technique

- [x] Tâche 1 — `websocket.ts` : `disconnect()` purge les 4 champs + détachement des handlers avant close
- [x] Tâche 2 — `websocket.ts` : méthode publique `reconnectWithToken(token)` (rotation sans purge)
- [x] Tâche 3 — `auth.ts` l.272-274 : refresh via `reconnectWithToken` (logout l.100 inchangé)
- [x] Tâche 4 — `websocket-helpers.spec.ts` : describe BUG-009 (6 tests) + commentaire du contournement
- [x] Tâche 5 — `auth.spec.ts` : mock étendu + test du site d'appel refresh
- [x] Tâche 6 — `WEBSOCKET-REAL-TIME.md` §8.5 : sémantique disconnect/reconnectWithToken
- [x] Tâche 7 — Validation ciblée (3 fichiers de tests verts, websocket.spec.ts non modifié)
- [x] Tâche 8 — Validation élargie (services/composables/stores) + lint + typecheck

## Résolution

**Corrigé le 2026-10-24** (pipeline `treat-story`, étape 3) — conformément à l'option retenue de l'analyse.

### Fichiers modifiés

| Fichier | Changement |
|---------|------------|
| [`frontend/src/services/websocket.ts`](../../frontend/src/services/websocket.ts) | `disconnect()` = fin de session : détachement des handlers (`onclose`/`onmessage`/`onopen`/`onerror` = null via helper privé `detachSocketHandlers()`) **avant** `close()`, puis purge des 4 champs (`authenticated = false`, `authToken = null`, `listeners.clear()`, `serverSubscriptions.clear()`) ; nouvelle méthode publique `reconnectWithToken(token)` : `clearReconnectTimer()` + `reconnect.stop()` + détachement + close + `connect(token)` **sans purge** (rotation JWT même session, rejeu par `resubscribeActiveTopics()` à l'`auth_success`) |
| [`frontend/src/stores/auth.ts`](../../frontend/src/stores/auth.ts) | Site refresh l.272-274 : `wsService.disconnect(); wsService.connect(newAccessToken)` → `wsService.reconnectWithToken(newAccessToken)` (commentaire BUG-009) ; logout l.100 **inchangé** (reste sur `disconnect()` purgateur) |
| [`frontend/tests/unit/services/websocket-helpers.spec.ts`](../../frontend/tests/unit/services/websocket-helpers.spec.ts) | 2 describes BUG-009 (6 tests) : purge des 4 champs + non-rejeu session suivante + sécurité (token A jamais réémis) + listeners fantômes + rotation (conservation listeners/abonnements, rejeu) + détachement handlers (aucune reconnexion parasite) ; commentaire du beforeEach mis à jour (reset explicite conservé comme garde-fou, redondant depuis la correction) ; mock étendu de `onerror` (présent dans le standard WebSocket) |
| [`frontend/tests/unit/stores/auth.spec.ts`](../../frontend/tests/unit/stores/auth.spec.ts) | Mock `wsService` étendu (`reconnectWithToken: vi.fn()` sur default + export nommé) + test `refreshAccessToken bascule la WebSocket via reconnectWithToken (sans disconnect purgeur)` : `authApi.refreshToken` mocké, assertion `reconnectWithToken` appelé avec le nouveau token et `disconnect` **non** appelé |
| [`docs/technical_specs/WEBSOCKET-REAL-TIME.md`](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) | §8.5 : ligne **Auth** enrichie (rotation JWT en session → `reconnectWithToken`, abonnements conservés) + nouvelle ligne **Déconnexion** (`disconnect()` = fin de session, état réinitialisé, handlers détachés — contre-exemple de la fuite inter-sessions BUG-009) |

### Décisions techniques

- **Ordre des opérations** dans `disconnect()` : détachement → close → purge (conforme à la tâche 1) — le close event asynchrone de l'ancienne socket ne peut plus écraser l'état (`authenticated = false`) ni déclencher une reconnexion parasite sur la nouvelle session (course du « handler fantôme » neutralisée) ;
- **Helper privé `detachSocketHandlers()`** mutualisé entre `disconnect()` et `reconnectWithToken()` (DRY, fonctions courtes) ;
- **Aucune modification de [`ws-reconnect.ts`](../../frontend/src/services/ws-reconnect.ts)** : contrat `reset()`/`stop()` intact — `reconnectWithToken()` passe par `reconnect.stop()` puis `connect()`, qui gère le retour depuis `stopped` (reset) et écrase le token ;
- **Cas socket absente** dans `reconnectWithToken()` : simplement `connect(token)` (branche `if (this.ws)`).

### Divergences par rapport à l'analyse

- Aucune divergence fonctionnelle. Micro-ajustement : l'interface `MockWebSocket` des tests (`websocket-helpers.spec.ts`) a été étendue de `onerror` (init à `null`) — champ présent sur le vrai standard WebSocket mais absent du mock initial, nécessaire pour prouver le détachement des 4 handlers dans le test de rotation. `websocket.spec.ts` est resté **strictement inchangé**.

### Tests et validation

| Commande | Résultat |
|----------|----------|
| `cd frontend && pnpm test -- tests/unit/services/websocket-helpers.spec.ts tests/unit/services/websocket.spec.ts tests/unit/stores/auth.spec.ts` | ✅ **41/41 passed** (3 fichiers : 31 helpers dont 6 nouveaux BUG-009 + 7 websocket.spec.ts non modifiés + 3 auth dont 1 nouveau) |
| `cd frontend && pnpm test -- tests/unit/services tests/unit/composables tests/unit/stores` | ✅ **209/209 passed** (15 fichiers, non-régression composables consommateurs `connectWithAuth` incluse) |
| `cd frontend && pnpm type-check` (`vue-tsc --noEmit`) | ✅ 0 erreur |
| `cd frontend && npx eslint src/services/websocket.ts src/stores/auth.ts tests/unit/services/websocket-helpers.spec.ts tests/unit/stores/auth.spec.ts` | ✅ 0 erreur (11 warnings `no-console` préexistants) |

Tests ajoutés : **7** (6 dans `websocket-helpers.spec.ts` : purge complète, non-rejeu inter-sessions, sécurité token, listeners fantômes, conservation/rejeu rotation, détachement handlers ; 1 dans `auth.spec.ts` : site d'appel refresh sans `disconnect`).
