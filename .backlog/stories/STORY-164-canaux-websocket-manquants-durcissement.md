# STORY-164 : [ABANDONED] Canaux WebSocket manquants + durcissement du protocole — `/ws/ssh`, `/ws/journal`, `/ws/batch`, heartbeats avec expiration, ack et reconnexion unifiée (P2-5, partie durcissement — axes C3, C4)

**Statut :** ABANDONED
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-5 (axes C3, C4, rapports §8) — ampleur **L**

> **Note de clôture — découpe `split-story` (2026-10-23, mode proactif)** : cette story a été **découpée à l'issue de la phase d'analyse** (`analyse-story`), qui a conclu à une **complexité excessive** (ampleur L confirmée : ~10 tâches hétérogènes estimées sur **3 périmètres largement indépendants** — mécaniques de protocole serveur, canaux manquants, reconnexion client + documentation ; verdict §Évaluation de complexité ci-dessous). Conformément au pipeline (règles 01 §5.1, étape 2b), elle est refermée `ABANDONED` selon le pattern STORY-160/131 (Règle d'Or : fichier conservé pour l'historique) et **remplacée sans perte d'information** par 3 sous-stories autonomes, prêtes pour `treat-story` :
>
> - [STORY-164.1](STORY-164.1-protocole-heartbeat-expiration-ack.md) — Mécaniques de protocole serveur : heartbeats avec expiration des connexions muettes (~2 intervalles) + acknowledgment des messages critiques (couvre l'AC 3 et la partie protocole de l'AC 5)
> - [STORY-164.2](STORY-164.2-canaux-ws-ssh-journal-batch.md) — Canaux manquants : `/ws/ssh/{host}` (TOFU STRICT), `/ws/journal/{host}`, `/ws/batch/{batch_id}` émetteur-ready, VNC reporté documenté (couvre les AC 1-2 et la partie canaux de l'AC 5)
> - [STORY-164.3](STORY-164.3-reconnexion-unifiee-client-type.md) — Reconnexion unifiée avec jitter + resynchronisation d'état + client type documenté (couvre l'AC 4 et la partie frontend/doc de l'AC 5)
>
> Le contexte technique, les décisions d'analyse 1-9, les points d'attention, les dépendances et les principes directeurs de tests documentés ci-dessous ont été **intégralement répartis** dans ces sous-stories — **se reporter à elles pour le détail d'implémentation** (tâches ordonnées, tests à écrire) et pour toute exécution.

## Description

En tant qu'utilisateur WindFlow, je veux que les canaux WebSocket canoniques manquants (`/ws/ssh/{host}`, `/ws/journal/{host}`, `/ws/batch/{batch_id}`) soient ajoutés aux 5 canaux existants et que le protocole soit durci — authentification obligatoire généralisée (dépend STORY-100), heartbeats avec expiration des connexions muettes, acknowledgment des messages critiques et politique de reconnexion unifiée avec jitter — afin que le temps réel couvre les usages spécifiés (SSH Host, journal système, opérations groupées) et ne laisse plus de connexions zombies.

**Problème constaté** ([WEBSOCKET-REAL-TIME.md §3.2, §8](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md)) : 4 canaux canoniques non montés (`console` VNC, `ssh`, `journal`, `batch`) ; le nommage réel `/api/v1/ws/...` diverge de `/ws/...` ; le serveur **n'expire pas** une connexion silencieuse (aucun contrôle des `pong`, `receive_text()` attend indéfiniment) ; l'acknowledgment est non implémenté ; la reconnexion n'est pas unifiée (backoff 1/2/4 s × 3 sur le canal général vs 5 × 2 s fixes sur les canaux dédiés, sans jitter ni resynchronisation d'état).

## Contexte technique

### Cartographie du code existant (analyse du 2026-10-23)

**Router & 5 canaux existants** :

- [`api/v1/websockets.py`](../../backend/app/api/v1/websockets.py) : 5 endpoints montés sous **`/api/v1/ws`** (préfixe posé dans [`api/v1/__init__.py`](../../backend/app/api/v1/__init__.py) l.47) — général `/`, `/deployments/{id}/logs`, `/terminal/{container_id}`, `/docker/containers/{id}/logs|stats`. Pattern d'ajout d'un canal : décorateur `@router.websocket` + docstring détaillée + `user: User = Depends(get_current_user_ws)` + `await ensure_role_ws(websocket, user, "<rôle>", session)` **avant accept** (l.115, l.200, l.248), puis délégation au handler du package [`websocket/`](../../backend/app/websocket) ;
- ⚠️ Nommage réel `/api/v1/ws/...` ≠ canonique `/ws/...` (WEBSOCKET §3.2) — la story n'exige pas de renommage (AC 5 non-régression) : les 3 nouveaux canaux suivent le nommage réel, l'écart reste tracé (voir Points d'attention).

**Auth/RBAC (STORY-100 + 122.6 — réutilisation directe)** :

- [`auth/dependencies.py`](../../backend/app/auth/dependencies.py) : `get_current_user_ws` (l.181-270) — refus du handshake **1008** sans token / token invalide-expiré / user inactif ; mode dev `disable_auth` = auto-login 1er superadmin ; `authenticate_ws_first_message` (l.273+) — JWT premier message, timeout `WS_AUTH_TIMEOUT_SECONDS` (30 s), réservé aux canaux général/terminal ;
- [`auth/rbac.py`](../../backend/app/auth/rbac.py) : `ensure_role_ws` (l.163-191) — hiérarchie `viewer < operator < admin < super_admin`, close 1008 « Insufficient permissions », jamais de token dans les logs ;
- [`websocket/terminal.py`](../../backend/app/websocket/terminal.py) : **modèle le plus proche du canal SSH interactif** — auth premier message, **rate limit 3 sessions/user** (`MAX_TERMINAL_SESSIONS_PER_USER` l.32, store mémoire `terminal_sessions` l.31), **audit dédié** (`log_terminal_audit` l.76-119 → logger `terminal_audit`), pont bidirectionnel WS↔`ExecSession` ;
- [`websocket/deployment_logs.py`](../../backend/app/websocket/deployment_logs.py) : modèle canal dédié lecture — `verify_deployment_access` l.23-53 (404/401/403 + isolation organisation via `UserOrganizationService.is_member`), accept → statut initial → boucle heartbeat (répond `pong`) ;
- Tests de référence : [`test_ws_auth.py`](../../backend/tests/unit/test_websocket/test_ws_auth.py) (42 cas), [`test_ws_rbac.py`](../../backend/tests/unit/test_websocket/test_ws_rbac.py), [`test_ws_isolation_1213.py`](../../backend/tests/unit/test_websocket/test_ws_isolation_1213.py).

**SSH (STORY-131 — socle direct des canaux `/ws/ssh` et `/ws/journal`)** :

- [`services/ssh_connection.py`](../../backend/app/services/ssh_connection.py) : `build_ssh_kwargs` (l.508+) — résout la clé référencée `target.ssh_key_id` (voie canonique) + fallback credentials déchiffrés ; **TOFU STRICT** (`HostKeyPolicy` l.92-103) : empreinte inconnue/non acceptée → `SSHHostKeyNotAcceptedError`, divergence → `SSHHostKeyMismatchError` (l.80-83) — implémente exactement le « divergence d'empreinte = blocage » (AC 2) ; jamais de `known_hosts: None` ;
- [`models/target.py`](../../backend/app/models/target.py) : `Target.host`/`port`/`ssh_key_id` (l.90-108) — résolution du host par `id` (+ credentials via `target.decrypted_credentials`, pattern [`target_scanner_service.py`](../../backend/app/services/target_scanner_service.py) l.186-210) ;
- [`services/commands.py`](../../backend/app/services/commands.py) : `SSHCommandExecutor` (l.167-242, `connection.run(command, timeout)` via asyncssh) — runner pour `journalctl` ; session interactive : asyncssh `connect(**kwargs)` puis channel PTY (`create_ssh_session`/process) — à confirmer en implémentation, pattern `ExecSession` du terminal adapté.

**Streaming (modèle `/ws/journal`)** :

- [`websocket/container_logs.py`](../../backend/app/websocket/container_logs.py) : streaming `--follow` → messages `{"type": "log", ...}` + `stream_status`, query param `tail` — modèle direct pour `journalctl -f -n <tail>` sur SSH.

**Batch (`/ws/batch` — tout à créer)** :

- Recherche exhaustive : **aucune orchestration batch en backend** (`batch_id`/`batch_update`/`check-updates` → 0 occurrence dans `backend/app`) — le canal est livré « émetteur-ready » : manager dédié + fonction d'émission `broadcast_batch_event(batch_id, phase, data)` sur le modèle de `_broadcast_deployment_event` ([`broadcasting.py`](../../backend/app/websocket/broadcasting.py) l.41-64), messages `start`/`progress`/`complete`/`error` (spec 09 §WebSocket), testé par opération simulée (AC 2) ; alimentation réelle différée (STORY-173 check-updates, batch-update Apps = Roadmap) ;
- Manager : [`connection_managers.py`](../../backend/app/websocket/connection_managers.py) `ConnectionManager` (l.107-184 : dict id→set[WebSocket], lock asyncio, purge des connexions mortes) — réutilisable pour `batch_id`.

**Heartbeat / expiration (à durcir)** :

- État : seul le canal général émet un ping serveur **30 s** ([`general.py`](../../backend/app/websocket/general.py) l.158-175) **sans aucun contrôle des `pong`** ; `receive_text()` attend indéfiniment partout (WEBSOCKET §8.2) ; les canaux dédiés répondent au ping client mais n'émettent pas de heartbeat périodique.

**Reconnexion (frontend — à unifier)** :

- Canal général [`services/websocket.ts`](../../frontend/src/services/websocket.ts) : backoff 1/2/4 s, **3 tentatives** puis logout (l.19-22, l.164-180) ; jamais de retry sur 1008/1003 + raisons auth (l.88-114) ;
- Canaux dédiés [`useContainerLogs.ts`](../../frontend/src/composables/useContainerLogs.ts) (l.46-48) / `useContainerStats.ts` : **5 tentatives, délai fixe 2 s**, sans retry 1000/1008 — aucun jitter, aucune resynchronisation d'état ; cible §8.3 : un seul algorithme (backoff + **jitter**, re-souscription, **resynchronisation par GET**, jamais de retry 1008/1003).

**Ack (à créer)** :

- [`schemas/websocket_events.py`](../../backend/app/schemas/websocket_events.py) : `WebSocketEventType` — aucune notion d'`id`/ack aujourd'hui ; cible §8.4 : champ `id` UUID sur les messages **critiques**, ack client `{"type":"ack","data":{"id":…}}`, rétention par connexion TTL ~30 s, re-diffusion à la reconnexion, dégradation journalisée (+ mesurée quand [`metrics.py`](../../backend/app/websocket/metrics.py) sera branché — STORY-172) ; exclus par conception : streaming logs, heartbeats, toasts ;
- Dispatch client : la boucle du canal général ([`general.py`](../../backend/app/websocket/general.py) l.178+) est le point d'entrée du message `ack`.

**Plugins internes (garde-fou §2.G)** :

- [`websocket/plugins/__init__.py`](../../backend/app/websocket/plugins/__init__.py) : 4 plugins par défaut depuis STORY-163 — l'extension ne doit casser ni `plugin_manager`, ni `default_message_handlers`, ni les 5 canaux ; clés mortes `"deployment_events"`/`"deployment_progress_{id}"` de [`deployment_notifications.py`](../../backend/app/websocket/plugins/deployment_notifications.py) tracées par STORY-163 pour cette story — statuer sans réécrire le contrat.

### Patterns à réutiliser

- Router : `Depends(get_current_user_ws)` + `ensure_role_ws` avant accept + délégation handler (pattern des 4 canaux dédiés existants) ;
- Canal lecture : `verify_*_access` (404/403/isolation org) + statut initial + heartbeat (deployment_logs) ;
- Canal interactif : rate limit par user + audit logger dédié + pont bidirectionnel (terminal) ;
- SSH : `build_ssh_kwargs` STRICT systématique (jamais `known_hosts: None`) ;
- Émission : `_broadcast_deployment_event` (timestamp auto + manager + dispatch plugins) ;
- Frontend : `useContainerLogs` (URL token + reconnexion dédiée) comme base du client unifié ; `test_ws_auth.py` comme patterns d'assertion close 1008.

### Réutilisation directe / adaptation / création

- **Directe** : `get_current_user_ws`, `ensure_role_ws`, `build_ssh_kwargs`, `SSHCommandExecutor`, `ConnectionManager`, exceptions SSH (`SSHHostKeyMismatchError`/`SSHHostKeyNotAcceptedError`), `UserOrganizationService.is_member` ;
- **Adaptation** : `terminal.py` (ExecSession → PTY SSH), `container_logs.py` (logs Docker → journalctl), `general.py` (expiration heartbeat + dispatch ack), `websocket.ts`/`useContainerLogs`/`useContainerStats` (politique unifiée), `broadcasting.py` (fonction batch) ;
- **Création** : handlers `websocket/ssh_session.py`, `websocket/journal.py`, `websocket/batch.py` + routes router ; fonction d'émission `broadcast_batch_event` ; registre d'ack par connexion (UUID + TTL + re-diffusion) ; politique de reconnexion frontend partagée (backoff+jitter+resync) ; documentation client type (spec §8 + README module).

### Décisions d'analyse

1. **Auth des nouveaux canaux = query param `?token=`** (`get_current_user_ws`) — convergence vers la cible ch. 09 (« JWT query parameter généralisé ») ; le premier-message reste réservé aux canaux général/terminal existants (AC 5 : pas de bascule des 5 canaux) ;
2. **RBAC par canal** (spec 15 « permissions vérifiées sur chaque action WS ») : `/ws/journal` = lecture → `viewer` ; `/ws/batch` = suivi d'opération → `viewer` (le déclenchement passe par l'API REST RBAC-protégée) ; `/ws/ssh` = action opérationnelle Host → `operator` — à valider contre la matrice spec 08 § Hosts en implémentation (divergence à signaler si la matrice diffère) ;
3. `/ws/ssh` : TOFU **STRICT** via `build_ssh_kwargs(target=...)` — divergence/inconnu → fermeture WS (1011), message générique au client (jamais d'empreinte en clair), détail en log serveur ;
4. **Expiration heartbeat** : baseline 30 s conservée ; fermeture serveur si **aucune activité reçue** (pong ou tout message) pendant ~2 intervalles — `asyncio.wait_for(receive_text(), timeout=2×interval)` + reset à chaque message reçu, appliqué à tous les canaux ; recommandation : le serveur ping périodiquement aussi sur les nouveaux canaux (même mécanique que general.py) ;
5. **Ack** : liste explicite configurable de types critiques (défaut proposé : statuts terminaux `DEPLOYMENT_STATUS_CHANGED` + `NOTIFICATION_USER`) ; `id` UUID ajouté à l'enveloppe uniquement pour ces types ; registre mémoire par connexion TTL ~30 s ; re-diffusion à la reconnexion du même utilisateur ; dégradation loggée WARNING (métriques via STORY-172) ; exclus : logs streaming, heartbeats, toasts ;
6. **Reconnexion unifiée** : module frontend partagé (backoff exponentiel + jitter borné, re-souscription automatique, hook de resynchronisation par GET, aucun retry sur 1008/1003) consommé par le service général **et** les composables dédiés ;
7. `/ws/batch` **émetteur-ready** : aucun batch réel n'existe (vérifié) — le « contrat dormant » est évité par un service d'émission testé + documentation explicite du branchement futur (STORY-173) ;
8. **Console VNC explicitement reportée** (Roadmap VMs) : non implémentée + note dans WEBSOCKET-REAL-TIME.md §3.2 et README module (aucun code — un éventuel `/ws/console` retourne 404 naturellement) ;
9. **Config** : nouvelles settings `ws_heartbeat_interval_seconds` (30), `ws_heartbeat_timeout_factor` (2), `ws_ack_ttl_seconds` (30), `ws_ack_critical_types` (liste), constantes reconnexion frontend ; **aucune migration Alembic**, aucune nouvelle dépendance (asyncssh déjà présent).

### Risques / hypothèses

- **Session SSH interactive (PTY asyncssh × xterm.js)** : plus grosse incertitude technique — hypothèse channel/process asyncssh PTY avec `term_type`/`term_size` + resize ; si le PTY complet s'avère trop lourd, un scope minimal (shell ligne à ligne) est un fallback à signaler comme divergence ;
- Sessions SSH persistantes : rate limit (3/user, calqué terminal.py) + audit (logger dédié `ssh_session_audit`) + fermeture propre à la déconnexion WS ;
- `journalctl` absent (Host non-systemd) → message `error` explicite + fermeture propre ;
- Token en query param : mécanisme déjà en place sur les canaux dédiés (jamais loggé — longueur seulement, pattern dependencies.py) ;
- `disable_auth` préservé sur les 3 nouveaux canaux (AC 5) ;
- Ack « par connexion » : les messages critiques partent du canal général (abonnements) — la re-diffusion vise les reconnexions du **même utilisateur** (registre par user vs par socket à trancher en implémentation).

Éléments existants à réutiliser / contraintes :
- **Auth** : STORY-100 (P0-1) rend le refus sans token obligatoire sur les 5 canaux — les nouveaux canaux naissent avec ; convergence du mécanisme (JWT query param généralisé, cible ch. 09) vs premier-message (canal général/terminal) à trancher à l'analyse ;
- **Canal `/ws/ssh/{host}`** : s'appuie sur STORY-131 (SSH keys + empreintes anti-MITM — la mission et l'epic corrigée citent bien **STORY-131**, pas 128) et les runners [`commands.py:167`](../../backend/app/services/commands.py:167) / [`socket_clients.py`](../../backend/app/services/socket_clients.py) ; le canal `/ws/terminal` reste réservé aux containers (consoles Machines = `/ws/console`) ;
- **Canal `/ws/journal/{host}`** : journal système du Host (`journalctl` via SSH — verbe Host spec 02) ; ≠ logs d'App (`/ws/logs`) ;
- **Canal `/ws/batch/{batch_id}`** : progression des opérations groupées (batch update, check-updates — messages `start`/`progress`/`complete`/`error`, enveloppe `type`/`data` spec 09) ; alimenté par l'orchestration batch (à câbler côté émission) ;
- **Console VNC explicitement reportée** aux phases Roadmap VMs (machines — plan §6 « Console VNC / canaux WS liés aux machines ») : **ne pas implémenter** `/ws/console/{machine_id}`, le noter dans la doc ;
- **Heartbeats** : expiration serveur si aucun `pong` sous ~2 intervalles (cible §8.2) ; le heartbeat 30 s existant est conservé comme base ;
- **Ack** (cible §8.4) : champ `id` UUID sur les messages critiques, ack client `{"type":"ack","data":{"id":…}}`, rétention par connexion TTL ~30 s avec re-diffusion à la reconnexion, dégradation en logs/métriques au-delà ; **pas d'ack** pour streaming de logs, heartbeats, toasts éphémères ;
- **Reconnexion unifiée** : un seul algorithme tous canaux, backoff avec **jitter** (anti-tempête), re-souscription automatique, resynchronisation d'état après reconnexion (refaire un `GET` de la ressource suivie), pas de retry sur fermetures d'auth (1008/1003) ;
- **Client type documenté** (critère de done) : documenter le comportement attendu du client (auth, ping/pong, ack, reconnexion) — côté spec technique WEBSOCKET-REAL-TIME et README du module ;
- Zones : [`websocket/`](../../backend/app/websocket) (handlers, [`connection_managers.py:27`](../../backend/app/websocket/connection_managers.py:27), [`broadcasting.py`](../../backend/app/websocket/broadcasting.py)), router [`api/v1/websockets.py:27`](../../backend/app/api/v1/websockets.py:27) ; frontend [`services/websocket.ts`](../../frontend/src/services/websocket.ts) + composables à synchroniser ;
- Garde-fou §2.G : WebSocket modulaire — étendre sans casser l'architecture plugins interne ni les 5 canaux existants.

## Critères d'acceptation (AC)

- [ ] AC 1 : Les 3 canaux `/ws/ssh/{host}`, `/ws/journal/{host}`, `/ws/batch/{batch_id}` sont montés avec auth obligatoire — tests : connexion **sans token → refusée (401/fermeture 1008)** sur chacun ; avec token valide → connecté ; un viewer ne peut pas ouvrir un canal d'opération (RBAC par action WS, spec 15) ; `/ws/console` VNC explicitement absent et documenté comme reporté (Roadmap VMs).
- [ ] AC 2 : `/ws/ssh/{host}` ouvre une session SSH interactive vers le Host (via STORY-131 : clé référencée + empreinte vérifiée — divergeance d'empreinte = blocage), `/ws/journal/{host}` streame le journal système, `/ws/batch/{batch_id}` diffuse `start`/`progress`/`complete` d'une opération groupée simulée — chacun testé avec un abonné authentifié (mock des runners SSH/journal côté tests unitaires).
- [ ] AC 3 : **Heartbeats avec expiration** : une connexion qui ne répond pas (aucun `pong` sous ~2 intervalles) est fermée côté serveur — test avec mock client muet ; les heartbeats streaming/logs restent exclus de l'ack ; **acknowledgment** implémenté pour les messages critiques : le client accuse réception, un message non acquitté au-delà du TTL (~30 s) est re-diffusé à la reconnexion et la dégradation est journalisée/mesurée.
- [ ] AC 4 : **Reconnexion unifiée avec jitter** : une seule politique documentée et implémentée côté client type (backoff + jitter, re-souscription, resynchronisation d'état par GET, jamais de retry sur 1008/1003) — testée sur au moins un canal dédié et le canal général ; le client type (comportement attendu) est documenté.
- [ ] AC 5 : Non-régression : les 5 canaux existants (général, deployment logs, terminal, container logs/stats) fonctionnent toujours ; `disable_auth` en dev préservé ; couverture ≥ 80 % sur les modules touchés (les tests dédiés sont renforcés par STORY-165) ; build + lint + tests passent.

## Références spécification

- [`09-api.md`](../../docs/general_specs/09-api.md) — **§ WebSocket** (référence unique des 8 canaux canoniques, JWT en query parameter, format des messages, `/ws/batch` progression des opérations groupées) ;
- [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) — §3 (canaux, état implémenté vs cible, écart d'authentification), §7 (auth par canal), §8.2 (heartbeat + expiration cible ~2 intervalles), §8.3 (reconnexion : politique unifiée, jitter, resynchronisation), §8.4 (acknowledgment cible complet), §10.3 (écarts) ;
- [`02-familles-workloads.md`](../../docs/general_specs/02-familles-workloads.md) — § Famille Hosts (verbes SSH, journalctl — usages des canaux `/ws/ssh` et `/ws/journal`) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Authentification et RBAC (permissions vérifiées sur chaque action WebSocket), § Hosts distants SSH (clés réutilisables, empreintes, anti-tempête) ;
- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § WebSocket (usages temps réel), § Performance (connexions simultanées cibles) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-5, §2.C C3/C4, §6 (VNC hors périmètre), §5 chaîne n°2 (P1-9 → P2-5) ;
- [`backend_status.md`](../../docs/backend_status.md) — §3.17, §8 (module WebSocket), §13.4 (zéro test WS).

## Dépendances

- **STORY-100** (auth WS obligatoire — EPIC-011) — **vérifiée DONE dans le code** : `get_current_user_ws` (refus 1008), `authenticate_ws_first_message` (30 s), tests [`test_ws_auth.py`](../../backend/tests/unit/test_websocket/test_ws_auth.py) ;
- **STORY-131** (SSH keys + empreintes — EPIC-012) — **vérifiée DONE** : `build_ssh_kwargs` TOFU STRICT, [`models/ssh_key.py`](../../backend/app/models/ssh_key.py), [`models/host_ssh_fingerprint.py`](../../backend/app/models/host_ssh_fingerprint.py), API `/ssh-keys` — socle direct des canaux ssh/journal ;
- **STORY-122.6** (RBAC WS) — vérifiée DONE : `ensure_role_ws` actif sur les 4 canaux dédiés existants ;
- **STORY-165** (tests WebSocket) — TODO, analyse conjointe recommandée : 164 fournit les tests ciblés des AC 1-4, 165 la suite exhaustive du module (partage de la cible de couverture ≥ 80 %) ;
- **STORY-162/163** (bus + consommateurs) — DONE : les nouveaux canaux ne consomment pas le bus (transport direct), mais la documentation du client type cite les deux couches (avertissement §4.2 : jamais d'abonnement workflow/plugin sur les SCREAMING_SNAKE) ;
- **STORY-173** (`/compute` browse/prune + check-updates) — TODO : première alimentation réelle attendue de `/ws/batch` ;
- **STORY-172** (Prometheus réel) — TODO : branchera [`websocket/metrics.py`](../../backend/app/websocket/metrics.py) (la « mesure » de dégradation ack reste log-only jusque-là) ;
- **STORY-252** (corrections consolidées specs) : portera l'arbitrage éventuel du nommage `/ws/...` vs `/api/v1/ws/...` ;
- **Technique** : aucune nouvelle dépendance Python ; **aucune migration Alembic** ; services externes : aucun.

## Points d'attention

1. **Nommage des nouveaux canaux** : montés sous `/api/v1/ws/ssh/{host_id}`, `/api/v1/ws/journal/{host_id}`, `/api/v1/ws/batch/{batch_id}` (cohérents avec les 5 existants, AC 5) — la cible canonique `/ws/...` (spec 09) reste non satisfaite ; la story ne demande pas de renommage (non-régression), l'écart reste documenté WEBSOCKET §3.2 — arbitrage global reporté à STORY-252 ;
2. **`/ws/batch` sans orchestration réelle** : vérifié — aucun code batch n'existe en backend ; le canal serait « jamais alimenté » jusqu'à STORY-173 (risque de contrat dormant, cf. `DEPLOYMENT_PROGRESS` avant STORY-163) — mitigation : service d'émission testé + doc explicite du branchement futur ;
3. **Rôles exacts par canal** : proposition Décision 2 (journal/batch = viewer, ssh = operator) fondée sur spec 15 « RBAC par action » — à confronter à la matrice spec 08 § Hosts pendant l'implémentation ;
4. **Session SSH interactive** : plus grosse incertitude d'implémentation (PTY asyncssh bidirectionnel + resize + xterm.js) — signaler en divergence si un scope minimal s'impose ;
5. **Périmètre de l'ack « par connexion »** : les messages critiques transitent par le canal général (abonnements) ; la re-diffusion « à la reconnexion » suppose d'identifier l'utilisateur à travers ses connexions successives — registre par user vs par socket à préciser en implémentation ;
6. **Clés mortes `deployment_notifications`** (`"deployment_events"`, `f"deployment_progress_{id}"` — tracées par STORY-163) : statuer (nettoyage léger ou documentation) sans réécrire le contrat du plugin ;
7. **Heartbeat serveur sur les canaux dédiés** : aujourd'hui seuls les clients pinguent ; l'expiration « ~2 intervalles » doit définir si le serveur se met à pinger périodiquement sur les nouveaux canaux (recommandé : oui, même mécanique que general.py) ou si seule l'inactivité est traquée.

## Évaluation de complexité (analyse-story — 2026-10-23)

**Découpe `split-story` recommandée** — critères du pipeline remplis :

- **~10 tâches hétérogènes** (settings + heartbeat/ack transverses ; 3 canaux dont une session SSH interactive complexe ; politique de reconnexion frontend ; documentation client type ; validation) ;
- **3 périmètres largement indépendants** :
  - **A. Mécaniques protocole serveur** — expiration heartbeat + acknowledgment + settings (backend transverse, s'applique aux 5 canaux existants et aux nouveaux) ;
  - **B. Canaux manquants** — `/ws/ssh` (le morceau le plus lourd : PTY, TOFU, rate limit, audit), `/ws/journal`, `/ws/batch` + documentation VNC reporté (backend, dépend STORY-131) ;
  - **C. Reconnexion unifiée + client type documenté** — frontend (`websocket.ts` + composables) + spec/README (indépendant de A et B : s'applique d'abord aux 5 canaux existants).
- Ampleur **L** confirmée par l'exploration ; la plage **STORY-175-199** est réservée à cet effet (epic §Notes de conception, section Sous-stories).

**Proposition de découpe** (à exécuter par `split-story` — motif `.1/.2/.3` pattern STORY-160/131) :
- **STORY-164.1** : Mécaniques protocole serveur — heartbeats avec expiration + acknowledgment (TTL, re-diffusion, dégradation) ;
- **STORY-164.2** : Canaux manquants — `/ws/ssh/{host}`, `/ws/journal/{host}`, `/ws/batch/{batch_id}` (auth + RBAC + TOFU + émission batch, VNC reporté documenté) ;
- **STORY-164.3** : Reconnexion unifiée avec jitter + resynchronisation + client type documenté (frontend + WEBSOCKET-REAL-TIME.md §8 + README).

Variante 2 volets si la découpe en 3 est jugée trop fine : backend durci (A+B) / client+doc (C).

**Conséquence** : conformément au pipeline (étape 2b), l'analyse exhaustive (tâches d'implémentation détaillées + tests fichier par fichier) est **volontairement arrêtée ici** — elle sera produite sur chaque sous-story ; la cartographie, les décisions d'analyse 1-9 et les points d'attention ci-dessus servent de base directe. Le statut de la story reste `TODO` (découpe à décider par le propriétaire du backlog).

## Sous-stories

> **Découpe exécutée le 2026-10-23** (`split-story` proactif, suffixes `.1/.2/.3` — pattern STORY-160/131) — la proposition d'analyse ci-dessus a été reprise **intégralement** dans 3 fichiers autonomes de `.backlog/stories/` :

- [ ] [STORY-164.1](STORY-164.1-protocole-heartbeat-expiration-ack.md) — **Mécaniques de protocole serveur** (M) : settings WS (`ws_heartbeat_interval_seconds`/`ws_heartbeat_timeout_factor`/`ws_ack_ttl_seconds`/`ws_ack_critical_types`), helper d'expiration réutilisable (`asyncio.wait_for(receive_text(), timeout=2×interval)` + reset à chaque message, décision 4) appliqué aux **5 canaux existants** + ping serveur périodique sur les canaux dédiés, enveloppe `id` UUID sur les types critiques + registre d'ack **par user** (TTL ~30 s, re-diffusion à la reconnexion, dégradation WARNING — décision 5), dispatch `ack` dans la boucle du canal général, statut sur les clés mortes `deployment_notifications` (point 6). Couvre AC 3 + AC 5 (partie protocole). **Conditionne** 164.2 (helper expiration) et 164.3 (contrat ack documenté).
- [ ] [STORY-164.2](STORY-164.2-canaux-ws-ssh-journal-batch.md) — **Canaux manquants** (M-L) : routes `/api/v1/ws/ssh/{host_id}` (operator, session PTY SSH interactive — TOFU STRICT `build_ssh_kwargs` : divergence/inconnu → close 1011 sans empreinte en clair, rate limit 3/user calqué terminal, audit `ssh_session_audit`), `/api/v1/ws/journal/{host_id}` (viewer, `journalctl -f -n <tail>` borné sur SSH, modèle container_logs), `/api/v1/ws/batch/{batch_id}` (viewer, émetteur-ready : manager + `broadcast_batch_event` `start`/`progress`/`complete`/`error`, alimentation réelle = STORY-173 — décision 7), auth `?token=` (décision 1), RBAC avant accept (décision 2), résolution host + isolation org partagées, note VNC reporté (décision 8 — WEBSOCKET §3.2 + README). Couvre AC 1-2 + AC 5 (partie canaux). **Dépend de** 164.1 (recommandé) et STORY-131 (DONE).
- [ ] [STORY-164.3](STORY-164.3-reconnexion-unifiee-client-type.md) — **Reconnexion unifiée + client type documenté** (M) : module frontend partagé `ws-reconnect.ts` (backoff exponentiel + jitter borné injectable, re-souscription automatique, hook resynchronisation par GET, **aucun retry 1008/1003** — décision 6), migration `websocket.ts` (logout sur épuisement conservé) + `useContainerLogs`/`useContainerStats` (fini 5×2 s fixes, correction retry 1008, resync GET), documentation client type (auth, ping/pong ~2 intervalles, ack id/TTL/re-diffusion, reconnexion) dans WEBSOCKET-REAL-TIME.md §8 + README module. Couvre AC 4 + AC 5 (partie frontend/doc). **Dépendance documentaire** avec 164.1 (non bloquante pour la partie reconnexion).

## État d'avancement technique

- [x] Analyse (2026-10-23) : cartographie du module WS + socles vérifiés (STORY-100/131/122.6), décisions d'analyse 1-9, points d'attention, évaluation de complexité → **découpe split-story recommandée** (protocole serveur / canaux / client+doc)
- [x] Découpe `split-story` (étape 2b du pipeline) — **exécutée le 2026-10-23** → STORY-164.1/.2/.3 créées (autonomes, tâches + tests rédigés) ; story refermée `ABANDONED`
- [x] Tâches d'implémentation détaillées — rédigées dans STORY-164.1 (8 tâches), 164.2 (7 tâches), 164.3 (5 tâches)
- [x] Tests à écrire — rédigés dans chaque sous-story (backend `test_ws_heartbeat_expiry.py`/`test_ws_ack.py`/`test_ws_ssh_session.py`/`test_ws_journal.py`/`test_ws_batch.py` ; frontend `ws-reconnect.spec.ts` + services/composables)

## Tâches d'implémentation détaillées

*(reportées après découpe — voir « Évaluation de complexité » : ~10 tâches hétérogènes réparties sur 3 périmètres indépendants. Répartition cible : **164.1** ← settings WS + heartbeat avec expiration (tous canaux) + ack (enveloppe `id` UUID, registre TTL ~30 s, re-diffusion, dégradation loggée) ; **164.2** ← routes `/ws/ssh|journal|batch` + handlers (`ssh_session.py`, `journal.py`, `batch.py`) + TOFU STRICT + rate limit/audit session SSH + `broadcast_batch_event` + note VNC reporté ; **164.3** ← politique de reconnexion unifiée frontend (backoff + jitter, re-souscription, resynchronisation GET, non-retry 1008/1003) + documentation client type. Chaque sous-story recevra ses tâches détaillées lors de sa propre analyse.)*

## Tests à écrire

*(reportés après découpe — principes directeurs posés par l'analyse : **AC 1** → connexion sans token refusée (close 1008) sur chacun des 3 canaux + token valide connecté + viewer refusé sur `/ws/ssh` + `/ws/console` absent ; **AC 2** → abonné authentifié reçoit les flux avec **runners SSH/journal mockés** (pattern `AsyncMock` sur `build_ssh_kwargs`/`SSHCommandExecutor`) + batch simulé (`start`/`progress`/`complete`) ; **AC 3** → mock client muet fermé après ~2 intervalles (timeout réduit en test) + ack : re-diffusion après TTL, dégradation loggée, logs/heartbeat/toasts exclus de l'ack ; **AC 4** → politique reconnexion testée sur canal général + un canal dédié (backoff+jitter bornés, aucun retry 1008/1003) ; **AC 5** → non-régression des 5 canaux + `disable_auth`. Localisation cible : `backend/tests/unit/test_websocket/test_ws_ssh_session.py`, `test_ws_journal.py`, `test_ws_batch.py`, `test_ws_heartbeat_expiry.py`, `test_ws_ack.py` — patterns [`test_ws_auth.py`](../../backend/tests/unit/test_websocket/test_ws_auth.py) / [`test_ws_rbac.py`](../../backend/tests/unit/test_websocket/test_ws_rbac.py) ; frontend `frontend/tests/unit/` (service + composables) ; la suite exhaustive du module relève de STORY-165.)*
