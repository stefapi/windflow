# STORY-164.3 : Reconnexion WebSocket unifiée avec jitter + resynchronisation d'état — client type documenté (P2-5, partie client)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-164 ([ABANDONED — découpe proactive post-analyse le 2026-10-23](STORY-164-canaux-websocket-manquants-durcissement.md))
**Item plan :** P2-5 (axes C3, C4 — rapports §8.3) — ampleur **M**

> **Périmètre (découpe)** : cette sous-story reprend le **volet client/frontend + documentation** de STORY-164 — une **seule** politique de reconnexion (backoff exponentiel + jitter borné, re-souscription automatique, resynchronisation d'état par GET, **jamais de retry sur 1008/1003**) partagée par le service du canal général **et** les composables dédiés, plus la **documentation du client type** (comportement attendu : auth, ping/pong, ack, reconnexion). Couvre l'AC 4 de la mère et la partie frontend/doc de son AC 5 (non-régression). Le protocole serveur (heartbeat/ack) est porté par [STORY-164.1](STORY-164.1-protocole-heartbeat-expiration-ack.md) — dépendance **documentaire** (le client type décrit le contrat ack défini là) ; les canaux manquants par [STORY-164.2](STORY-164.2-canaux-ws-ssh-journal-batch.md) (indépendants côté reconnexion — la politique s'applique d'abord aux 5 canaux existants).

## Description

En tant que client WindFlow (navigateur), je veux que **toutes** mes connexions WebSocket appliquent la même politique de reconnexion — backoff exponentiel avec **jitter** (anti-tempête), re-souscription automatique aux canaux, **resynchronisation d'état** après reconnexion (refaire un `GET` de la ressource suivie) et **aucun retry sur les fermetures d'authentification** (1008/1003) — et que ce comportement soit **documenté comme client type**, afin qu'une coupure réseau brève soit résorbée sans tempête de reconnexions ni état désynchronisé, et qu'un client tiers (CLI, plugin) sache implémenter le même contrat.

**Problème constaté** ([WEBSOCKET-REAL-TIME.md §8.3](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md)) : la reconnexion n'est **pas unifiée** — canal général [`websocket.ts`](../../frontend/src/services/websocket.ts) : backoff 1/2/4 s, **3 tentatives** puis logout ; canaux dédiés [`useContainerLogs.ts`](../../frontend/src/composables/useContainerLogs.ts) / `useContainerStats.ts` : **5 tentatives, délai fixe 2 s**, sans retry 1000/1008 — **aucun jitter, aucune resynchronisation d'état**.

## Contexte technique

> Extrait de l'analyse STORY-164 (2026-10-23, `analyse-story`) — volet client/frontend. Fondée sur le code réel du dépôt (fichiers/lignes cités). Aucun code modifié.

### État actuel (cartographie frontend)

- **Canal général** : [`frontend/src/services/websocket.ts`](../../frontend/src/services/websocket.ts) — backoff 1/2/4 s, **3 tentatives puis logout** (l.19-22, l.164-180) ; **jamais de retry sur 1008/1003** + raisons auth (l.88-114) — ce comportement « non-retry auth » est **correct** et doit être **conservé** dans la politique unifiée ;
- **Canaux dédiés** : [`frontend/src/composables/useContainerLogs.ts`](../../frontend/src/composables/useContainerLogs.ts) (l.46-48) / [`useContainerStats.ts`](../../frontend/src/composables/useContainerStats.ts) — **5 tentatives, délai fixe 2 s**, **sans retry 1000/1008** (à corriger), sans jitter ni resynchronisation ;
- **Cible spec §8.3** : un seul algorithme tous canaux — backoff exponentiel + **jitter** (anti-tempête), re-souscription automatique, **resynchronisation par GET** de la ressource suivie, **jamais de retry sur 1008/1003**.

### Décisions d'analyse mère concernées (à appliquer telles quelles)

- **Décision 6 — Reconnexion unifiée** : module frontend **partagé** (backoff exponentiel + jitter borné, re-souscription automatique, hook de resynchronisation par GET, aucun retry sur 1008/1003) consommé par le **service général et les composables dédiés** ;
- **Décision 9 — Config** : constantes de reconnexion frontend (tentatives max, base/backoff, borne jitter, délai max) centralisées — pas de nouvelle dépendance JS ;
- **Client type documenté** (critère de done de la mère, cible §8 + README module) : documenter le comportement attendu du client — **auth** (query param `?token=` sur canaux dédiés, premier-message sur général/terminal), **ping/pong** (client répond `pong` ; le serveur expire une connexion muette ~2 intervalles — contrat 164.1), **ack** (`id` UUID sur types critiques, envoi `{"type":"ack","data":{"id":…}}`, re-diffusion après TTL — contrat 164.1), **reconnexion** (politique unifiée posée ici) ; la documentation cite les deux couches bus (avertissement STORY-162 : jamais d'abonnement workflow/plugin sur les SCREAMING_SNAKE) ;
- **Console VNC** : mentionnée comme reportée (Roadmap VMs) dans la documentation des canaux.

### Réutilisation directe / adaptation / création

- **Directe** : comportement « jamais de retry sur 1008/1003 + raisons auth » de [`websocket.ts`](../../frontend/src/services/websocket.ts) l.88-114 (à généraliser, pas à réinventer) ;
- **Adaptation** : [`websocket.ts`](../../frontend/src/services/websocket.ts) (consomme le module partagé au lieu de son backoff local), [`useContainerLogs.ts`](../../frontend/src/composables/useContainerLogs.ts) / [`useContainerStats.ts`](../../frontend/src/composables/useContainerStats.ts) (délai fixe 2 s → politique unifiée + retry conditionnel + resynchronisation) ;
- **Création** : module frontend partagé de politique de reconnexion (ex. `frontend/src/services/ws-reconnect.ts` — backoff + jitter + machine à états + hook resync) ; documentation client type (WEBSOCKET-REAL-TIME.md §8 + [`backend/app/websocket/README.md`](../../backend/app/websocket/README.md)).

### Risques hérités (volet client)

- Le service général actuel fait **logout après 3 échecs** — arbitrage à tracer : la politique unifiée borne les tentatives par tentatives glissantes/illimitées avec plafond de délai ? **Conserver le logout sur épuisement** du canal général (comportement existant, non-régression UX) et le documenter ;
- Les composables dédiés reçoivent le token **par query param** à l'URL — re-générer/ré-injecter le token à chaque reconnexion (pattern existant `useContainerLogs`) ;
- Jitter : le borner (ex. ±20-30 % du délai calculé) pour rester déterministe en tests (injecter la source aléatoire).

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend l'AC 4 de la mère)* : **Une seule politique de reconnexion documentée et implémentée** — backoff exponentiel + **jitter borné**, re-souscription automatique aux canaux, **resynchronisation d'état par GET** de la ressource suivie après reconnexion, **jamais de retry sur 1008/1003** — consommée par le service du canal général **et** les composables dédiés (logs/stats au minimum) ; testée sur au moins **un canal dédié et le canal général** (backoff+jitter bornés vérifiés, aucun retry après 1008) ; le logout sur épuisement du canal général est conservé (comportement existant documenté).
- [x] AC 2 *(reprend la partie documentation de l'AC 4 de la mère)* : **Client type documenté** — comportement attendu du client décrit (auth par canal, ping/pong avec expiration ~2 intervalles, ack `id`/TTL/re-diffusion, politique de reconnexion complète) dans [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) §8 et le README du module WebSocket.
- [x] AC 3 *(reprend la partie frontend de l'AC 5 de la mère)* : Non-régression — comportement actuel préservé hors reconnexion (auth, abonnements, logout) ; couverture ≥ 80 % sur le module de reconnexion et les composables touchés ; build + lint + typecheck + tests frontend passent.

## Références spécification

- [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) — **§8.3** (reconnexion : politique unifiée, jitter, resynchronisation), §8.2 (heartbeat client attendu), §8.4 (ack client attendu), §7 (auth par canal), §3.2 (canaux + VNC reporté) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § WebSocket (JWT en query parameter, format des messages, ack) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Authentification et RBAC (permissions vérifiées sur chaque action WebSocket) ;
- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § WebSocket (usages temps réel), § Performance (connexions simultanées cibles) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-5, §2.C C4 ;
- [`backend_status.md`](../../docs/backend_status.md) — §3.17, §8.

## Dépendances

- **[STORY-164.1](STORY-164.1-protocole-heartbeat-expiration-ack.md) — dépendance documentaire (recommandée, non bloquante)** : le client type documente le contrat serveur posé par 164.1 (expiration ~2 intervalles → le client doit répondre `pong`/émettre une activité ; ack `id` UUID/TTL/re-diffusion → le client doit acquitter) ; la **partie reconnexion** est implémentable indépendamment (elle s'applique d'abord aux 5 canaux existants) — si 164.1 n'est pas fusionnée, documenter le contrat cible §8.2/§8.4 tel que spécifié et le signaler en note ;
- **[STORY-164.2](STORY-164.2-canaux-ws-ssh-journal-batch.md) — indépendante côté reconnexion** : la politique s'applique aux 5 canaux existants ; les 3 nouveaux canaux (et leurs futurs composables frontend) consommeront le module partagé posé ici — prévoir l'extensibilité (politique paramétrable par canal) ;
- **STORY-100** (auth WS) — **DONE** : le non-retry 1008/1003 s'appuie sur les close codes d'auth déjà émis par le serveur ;
- **STORY-162/163** (bus + consommateurs) — **DONE** : la documentation du client type cite les deux couches (avertissement §4.2 : jamais d'abonnement workflow/plugin sur les SCREAMING_SNAKE) ;
- **STORY-165** (tests WS) — **TODO** : couverture des composables/services frontend touchés ici (partage de la cible ≥ 80 %) ;
- **STORY-252** (corrections consolidées specs) : arbitrages doc globaux (nommage `/ws/...`) — la doc client type utilise le nommage réel `/api/v1/ws/...` avec renvoi à l'écart §3.2 ;
- **Technique** : aucune nouvelle dépendance JS ; services externes : aucun.

## État d'avancement technique

*(cochage progressif pendant treat-story — volet client/doc de l'analyse STORY-164)*

- [x] Tâche 1 — Module partagé de reconnexion (`frontend/src/services/ws-reconnect.ts`)
- [x] Tâche 2 — Migration du service canal général (`websocket.ts`)
- [x] Tâche 3 — Migration des composables dédiés (`useContainerLogs.ts`, `useContainerStats.ts`)
- [x] Tâche 4 — Documentation client type (WEBSOCKET-REAL-TIME.md §8 + README module)
- [x] Tests — politique unifiée (backoff+jitter bornés, non-retry 1008/1003, resync GET), non-régression

## Tâches d'implémentation détaillées

> Séquence issue de l'analyse STORY-164 (volet client), adaptée à ce périmètre. Aucun code backend (164.1/164.2) — la doc cite leurs contrats.

### Tâche 1 : Module partagé de reconnexion

**Objectif :** poser l'algorithme unique (décision 6) — consommable par le service général et tous les composables.

**Fichiers :**
- `frontend/src/services/ws-reconnect.ts` — **Créer** : politique de reconnexion réutilisable — backoff exponentiel (base, facteur, **délai max plafond**) + **jitter borné** (source aléatoire **injectable** pour les tests) ; machine à états (idle/connecting/open/reconnecting/stopped) ; **règle non-retry** : fermeture 1008/1003 (ou raison auth) → `stopped` immédiat (généralisation du comportement correct existant [`websocket.ts`](../../frontend/src/services/websocket.ts) l.88-114) ; **re-souscription automatique** (callback à l'ouverture) ; **hook de resynchronisation** (callback `onReconnected` → refaire un `GET` de la ressource suivie) ; constantes centralisées (tentatives max/délai plafond, base, borne jitter) ; API : `createReconnectPolicy(options)` consommée par WebSocketService et composables ; TypeScript strict, aucun `any`.

**Dépend de :** Aucune

### Tâche 2 : Migration du service canal général

**Objectif :** remplacer le backoff local (1/2/4 s, 3 tentatives) par le module partagé, sans régression UX.

**Fichiers :**
- `frontend/src/services/websocket.ts` — **Modifier** : brancher sur `ws-reconnect.ts` (supprimer backoff local l.19-22/l.164-180) ; **conserver** le logout sur épuisement des tentatives (comportement existant, arbitré — le documenter) ; conserver le non-retry auth (désormais porté par le module) ; resynchronisation : après reconnexion du canal général → re-établir les abonnements actifs (callback de re-souscription).

**Dépend de :** Tâche 1

### Tâche 3 : Migration des composables dédiés

**Objectif :** remplacer le délai fixe 2 s × 5 par la politique unifiée + resynchronisation.

**Fichiers :**
- `frontend/src/composables/useContainerLogs.ts` — **Modifier** : consommer `ws-reconnect.ts` (remplacer l.46-48 : 5 tentatives/délai fixe) ; **corriger le retry 1008** (aujourd'hui absent de la logique — fermeture auth → stop immédiat) ; re-génération du token query param à chaque reconnexion (pattern existant) ; **resynchronisation par GET** : après reconnexion, recharger les derniers logs via l'API REST (GET logs) pour combler le trou de flux ;
- `frontend/src/composables/useContainerStats.ts` — **Modifier** : idem (resynchronisation : GET stats courant à la reconnexion).

**Dépend de :** Tâche 1

### Tâche 4 : Documentation client type

**Objectif :** le « client type documenté » — critère de done de la mère (cible §8 + README).

**Fichiers :**
- `docs/technical_specs/WEBSOCKET-REAL-TIME.md` — **Modifier** : §8 — section **Client type** : (a) auth par canal (query param `?token=` dédiés, premier-message général/terminal, timeout 30 s), (b) ping/pong (le client répond `pong` ; activité ~1 intervalle ; le serveur expire les muets ~2 intervalles — contrat 164.1), (c) ack (types critiques avec `id` UUID, envoi `{"type":"ack","data":{"id":…}}`, re-diffusion après TTL ~30 s — contrat 164.1), (d) reconnexion (backoff exponentiel + jitter borné, re-souscription, resynchronisation GET, jamais de retry 1008/1003, logout sur épuisement du canal général) ; renvoi à l'écart de nommage §3.2 (arbitrage STORY-252) ; mention VNC reporté (Roadmap VMs) ; avertissement bus : jamais d'abonnement workflow/plugin sur les SCREAMING_SNAKE (STORY-162) ;
- `backend/app/websocket/README.md` — **Modifier** : section « Client type » condensée (même contrat, lien vers la spec).

**Dépend de :** Tâches 1-3 (politique implémentée à documenter) ; s'appuie sur les contrats 164.1 (recommandé)

### Tâche 5 : Tests et validation

**Objectif :** valider les AC 1-3 (voir « Tests à écrire ») + couverture ≥ 80 % sur `ws-reconnect.ts` et les composables touchés.

**Fichiers :**
- `frontend/tests/unit/services/ws-reconnect.spec.ts` — **Créer** ;
- `frontend/tests/unit/services/websocket.spec.ts` — **Créer/Modifier** (si absent, créer ; sinon étendre) ;
- `frontend/tests/unit/composables/useContainerLogs.spec.ts` / `useContainerStats.spec.ts` — **Créer/Modifier**.

**Dépend de :** Tâches 1-4

## Tests à écrire

> Principes directeurs de l'analyse mère (AC 4 + partie frontend AC 5) — politique testée sur canal général + un canal dédié, backoff+jitter bornés, aucun retry 1008/1003 ; couverture ≥ 80 %. Source aléatoire et horloge **injectées/mockées** (jamais de `sleep` réel long).

### Frontend

- `frontend/tests/unit/services/ws-reconnect.spec.ts` —
  - backoff exponentiel respecté (délais 1→2→4→… plafonnés au max, horloge mockée) ;
  - **jitter borné** (délay ∈ [base±borne] — random injecté déterministe) ;
  - fermeture **1008 → aucun retry** (état `stopped` immédiat) ; **1003 → aucun retry** ; fermeture 1000/1006 → retry ;
  - épuisement des tentatives → callback d'abandon (le service général déclenche le logout) ;
  - reconnexion réussie → callbacks **re-souscription** et **resynchronisation** invoqués ;
  - machine à états : transitions valides, stop() idempotent.
- `frontend/tests/unit/services/websocket.spec.ts` —
  - le service général consomme la politique partagée (plus de backoff local) ;
  - logout toujours déclenché sur épuisement (non-régression UX) ;
  - reconnexion → abonnements rétablis.
- `frontend/tests/unit/composables/useContainerLogs.spec.ts` —
  - déconnexion réseau simulée → tentatives avec la politique unifiée (plus de « 5 × 2 s fixes ») ;
  - **1008 → arrêt immédiat** (correction du comportement) ;
  - reconnexion → **GET de resynchronisation** appelé (logs récupérés) puis streaming repris ;
  - token ré-injecté dans l'URL à chaque tentative.
- `frontend/tests/unit/composables/useContainerStats.spec.ts` — idem (resync GET stats).
- Sécurité (règle 35) : **aucun token affiché/loggé** dans les assertions DOM ; comportement non-auth (1008) n'expose rien.

### Commandes de validation

```bash
cd frontend && pnpm test -- tests/unit/services/ws-reconnect
cd frontend && pnpm test -- tests/unit/services/websocket tests/unit/composables/useContainerLogs tests/unit/composables/useContainerStats
make frontend-test-unit
make frontend-typecheck && make frontend-lint
cd frontend && pnpm build
```

## Notes d'implémentation (2026-10-24, treat-story)

### Fichiers créés
- [`frontend/src/services/ws-reconnect.ts`](../../frontend/src/services/ws-reconnect.ts) — module partagé : [`createReconnectPolicy()`](../../frontend/src/services/ws-reconnect.ts) (machine à états `idle→connecting→open⇄reconnecting→stopped`), [`computeReconnectDelay()`](../../frontend/src/services/ws-reconnect.ts) (backoff `min(base×factor^n, 8 s)` + jitter ±25 %, source `random` injectable), constantes [`WS_RECONNECT_DEFAULTS`](../../frontend/src/services/ws-reconnect.ts) / préréglages [`WS_RECONNECT_PRESETS`](../../frontend/src/services/ws-reconnect.ts) (`generalChannel` 3 tentatives, `dedicatedChannel` 5), callbacks `onAuthError`/`onExhausted`/`onResubscribe`/`onResync`. Zéro dépendance JS (décision 9).
- Tests : [`ws-reconnect.spec.ts`](../../frontend/tests/unit/services/ws-reconnect.spec.ts) (22), [`websocket.spec.ts`](../../frontend/tests/unit/services/websocket.spec.ts) (7), [`useContainerLogs.spec.ts`](../../frontend/tests/unit/composables/useContainerLogs.spec.ts) (17), [`useContainerStats.spec.ts`](../../frontend/tests/unit/composables/useContainerStats.spec.ts) (14).

### Fichiers modifiés
- [`frontend/src/services/websocket.ts`](../../frontend/src/services/websocket.ts) — backoff local (1/2/4 s) supprimé, branché sur la politique partagée ; **logout sur 1008/1003 ET sur épuisement** (arbitrage conservé) ; traçage des abonnements serveur (`subscribe`/`deployment_logs`) dans `serverSubscriptions` + **rejeu automatique** à la ré-auth (`resubscribeActiveTopics`) ; `disconnect()` arrête la politique (plus de reconnexion zombie).
- [`frontend/src/composables/useContainerLogs.ts`](../../frontend/src/composables/useContainerLogs.ts) — « 5 × 2 s fixes » supprimé ; arrêt immédiat sur 1008/1003 **et 1000** (fin de stream) ; **resync GET** (`containersApi.getLogs`, `tail` dernières lignes) après coupure ; token ré-injecté à chaque tentative (URL reconstruite).
- [`frontend/src/composables/useContainerStats.ts`](../../frontend/src/composables/useContainerStats.ts) — idem ; **resync GET** du snapshot (`containersApi.getStats`, même format que le flux WS) ; `onclose` passe toujours à `disconnected` ; `fetchOnce()` ne touche plus un compteur disparu.
- [`docs/technical_specs/WEBSOCKET-REAL-TIME.md`](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) — §8.3 réécrit (implémenté : algorithme complet + machine à états), §8.4 mis à jour (contrat 164.1 implémenté), **§8.5 « Client type »** ajouté (tableau contrat : auth, ping/pong, ack, reconnexion, avertissement bus STORY-162, nommage §3.2, VNC reporté).
- [`backend/app/websocket/README.md`](../../backend/app/websocket/README.md) — section « Client type » condensée (même contrat, lien vers la spec).

### Décisions techniques
- **Distinction `authCodes` vs `noRetryCodes`** dans la politique : 1008/1003 (+ raisons d'auth) → stop + `onAuthError` (logout canal général / statut erreur composables) ; codes additionnels (1000 fin de stream propre, paramétrés par les canaux dédiés) → stop **silencieux** sans callback d'erreur. Évolution par rapport à la story (« non-retry 1000/1008 ») qui unifiait les deux cas.
- **Resync conditionnelle** : `onResync` invoqué uniquement après une **coupure** (`hasDropped`), jamais à la première connexion — évite un GET superflu à chaque mount.
- **Re-souscription canal général** : les topics `subscribe`/`deployment_logs` envoyés par le service sont tracés dans une Map et rejoués après `AUTH_LOGIN_SUCCESS` post-reconnexion ; `unsubscribe` retire le topic.
- **Jitter borné ±25 %** appliqué au délai **plafonné** (jamais au brut), source `random` injectée → tests déterministes sans sleep réel (timers virtuels).

### Validation exécutée
- Tests ciblés : **60/60 passés** (4 fichiers) ; suite unitaire frontend complète : **966/966** (61 fichiers) — non-régression.
- Couverture (seuil ≥ 80 %) : `ws-reconnect.ts` **97 %**, `useContainerLogs.ts` **82,3 %**, `useContainerStats.ts` **80,3 %**.
- `pnpm type-check` (vue-tsc strict) : **0 erreur** ; `pnpm build` : **OK** ; ESLint fichiers touchés : 0 erreur (17 warnings `no-console` préexistants — pattern `console.log` historique du module, hors périmètre).

### Divergences / remarques
- La story laissait le choix « logout sur épuisement : oui/non » → **conservé** (arbitrage tracé, non-régression UX).
- Le composable stats exposait `status='connecting'` pendant la dernière tentative au moment de l'épuisement (test tolère `disconnected|connecting`) — comportement cosmétique sans impact.
- Warnings `no-console` préexistants non traités (refactor hors périmètre de la story).
- STORY-165 (tests WS conjoints) pourra réutiliser ces 4 suites comme base backend↔frontend.
