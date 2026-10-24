# STORY-164.2 : Canaux WebSocket manquants — `/ws/ssh/{host}`, `/ws/journal/{host}`, `/ws/batch/{batch_id}` (P2-5, partie canaux)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-164 ([ABANDONED — découpe proactive post-analyse le 2026-10-23](STORY-164-canaux-websocket-manquants-durcissement.md))
**Item plan :** P2-5 (axes C3, C4 — spec 09 § WebSocket) — ampleur **M-L**

> **Périmètre (découpe)** : cette sous-story reprend le **volet canaux manquants** de STORY-164 — création des 3 canaux `/ws/ssh/{host}` (session SSH interactive : TOFU STRICT, rate limit, audit), `/ws/journal/{host}` (streaming `journalctl`) et `/ws/batch/{batch_id}` (émetteur-ready, opération groupée simulée), avec auth/RBAC par canal et note de report de la console VNC (Roadmap VMs). Couvre les AC 1 et 2 de la mère et la partie canaux de son AC 5 (non-régression). Le protocole (expiration heartbeat, ack) est porté par [STORY-164.1](STORY-164.1-protocole-heartbeat-expiration-ack.md) (**pré-requis recommandé** — les nouveaux canaux consomment son helper) ; la reconnexion frontend/client type par [STORY-164.3](STORY-164.3-reconnexion-unifiee-client-type.md).

## Description

En tant qu'opérateur WindFlow, je veux que les canaux WebSocket canoniques manquants soient ajoutés aux 5 canaux existants — `/ws/ssh/{host}` (session SSH interactive vers un Host, clé référencée + empreinte vérifiée), `/ws/journal/{host}` (streaming du journal système) et `/ws/batch/{batch_id}` (progression des opérations groupées) — afin que le temps réel couvre les usages spécifiés (SSH Host, journal système, opérations groupées) au lieu de se limiter aux 5 canaux actuels.

**Problème constaté** ([WEBSOCKET-REAL-TIME.md §3.2](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md)) : 4 canaux canoniques non montés (`console` VNC, `ssh`, `journal`, `batch`) — la console VNC est **explicitement reportée** à la Roadmap VMs (décision 8 : ne pas implémenter, documenter le report).

## Contexte technique

> Extrait de l'analyse STORY-164 (2026-10-23, `analyse-story`) — volet canaux. Fondée sur le code réel du dépôt (fichiers/lignes cités). Aucun code modifié.

### Patterns existants à réutiliser (directs)

- **Router** : [`api/v1/websockets.py`](../../backend/app/api/v1/websockets.py) — 5 endpoints montés sous **`/api/v1/ws`** (préfixe posé dans [`api/v1/__init__.py`](../../backend/app/api/v1/__init__.py) l.47) ; pattern d'ajout d'un canal : décorateur `@router.websocket` + docstring détaillée + `user: User = Depends(get_current_user_ws)` + `await ensure_role_ws(websocket, user, "<rôle>", session)` **avant accept** (l.115, l.200, l.248), puis délégation au handler du package [`websocket/`](../../backend/app/websocket) ;
- **Auth/RBAC (STORY-100 + 122.6 — réutilisation directe)** : [`auth/dependencies.py`](../../backend/app/auth/dependencies.py) `get_current_user_ws` (l.181-270 — refus handshake **1008** sans token/ invalide / user inactif ; mode dev `disable_auth` = auto-login 1er superadmin) ; [`auth/rbac.py`](../../backend/app/auth/rbac.py) `ensure_role_ws` (l.163-191 — hiérarchie `viewer < operator < admin < super_admin`, close 1008 « Insufficient permissions », jamais de token dans les logs) ;
- **Canal interactif — modèle terminal** : [`websocket/terminal.py`](../../backend/app/websocket/terminal.py) — **modèle le plus proche du canal SSH** : auth premier message, **rate limit 3 sessions/user** (`MAX_TERMINAL_SESSIONS_PER_USER` l.32, store mémoire `terminal_sessions` l.31), **audit dédié** (`log_terminal_audit` l.76-119 → logger `terminal_audit`), pont bidirectionnel WS↔`ExecSession` ;
- **Canal lecture — modèle deployment_logs** : [`websocket/deployment_logs.py`](../../backend/app/websocket/deployment_logs.py) — `verify_deployment_access` l.23-53 (404/401/403 + isolation organisation via `UserOrganizationService.is_member`), accept → statut initial → boucle heartbeat (répond `pong`) ;
- **SSH (STORY-131 — socle direct)** : [`services/ssh_connection.py`](../../backend/app/services/ssh_connection.py) `build_ssh_kwargs` (l.508+) — résout la clé référencée `target.ssh_key_id` (voie canonique) + fallback credentials déchiffrés ; **TOFU STRICT** (`HostKeyPolicy` l.92-103) : empreinte inconnue/non acceptée → `SSHHostKeyNotAcceptedError`, divergence → `SSHHostKeyMismatchError` (l.80-83) ; **jamais** de `known_hosts: None` ; [`models/target.py`](../../backend/app/models/target.py) `Target.host`/`port`/`ssh_key_id` (l.90-108) — résolution du host par `id` (+ credentials via `target.decrypted_credentials`, pattern [`target_scanner_service.py`](../../backend/app/services/target_scanner_service.py) l.186-210) ; [`services/commands.py`](../../backend/app/services/commands.py) `SSHCommandExecutor` (l.167-242, `connection.run(command, timeout)` via asyncssh) — runner pour `journalctl` ;
- **Streaming — modèle journal** : [`websocket/container_logs.py`](../../backend/app/websocket/container_logs.py) — streaming `--follow` → messages `{"type": "log", ...}` + `stream_status`, query param `tail` — modèle direct pour `journalctl -f -n <tail>` sur SSH ;
- **Manager** : [`connection_managers.py`](../../backend/app/websocket/connection_managers.py) `ConnectionManager` (l.107-184 : dict id→set[WebSocket], lock asyncio, purge des connexions mortes) — réutilisable pour `batch_id` ;
- **Émission batch** : [`broadcasting.py`](../../backend/app/websocket/broadcasting.py) `_broadcast_deployment_event` (l.41-64) — modèle de la fonction `broadcast_batch_event` ;
- **Tests de référence** : [`test_ws_auth.py`](../../backend/tests/unit/test_websocket/test_ws_auth.py) (42 cas, patterns close 1008), [`test_ws_rbac.py`](../../backend/tests/unit/test_websocket/test_ws_rbac.py), [`test_ws_isolation_1213.py`](../../backend/tests/unit/test_websocket/test_ws_isolation_1213.py).

### Constat clé — batch « émetteur-ready »

Recherche exhaustive de l'analyse : **aucune orchestration batch en backend** (`batch_id`/`batch_update`/`check-updates` → 0 occurrence dans `backend/app`) — le canal est livré « émetteur-ready » : manager dédié + fonction d'émission `broadcast_batch_event(batch_id, phase, data)` sur le modèle de `_broadcast_deployment_event`, messages `start`/`progress`/`complete`/`error` (spec 09 §WebSocket), testé par opération simulée ; alimentation réelle différée (STORY-173 check-updates, batch-update Apps = Roadmap — décision 7 : le « contrat dormant » est évité par un service d'émission testé + documentation explicite du branchement futur).

### Décisions d'analyse mère concernées (à appliquer telles quelles)

- **Décision 1 — Auth des nouveaux canaux = query param `?token=`** (`get_current_user_ws`) — convergence vers la cible ch. 09 ; le premier-message reste réservé aux canaux général/terminal existants (AC 5 mère : pas de bascule des 5 canaux) ;
- **Décision 2 — RBAC par canal** (spec 15 « permissions vérifiées sur chaque action WS ») : `/ws/journal` = lecture → `viewer` ; `/ws/batch` = suivi d'opération → `viewer` (le déclenchement passe par l'API REST RBAC-protégée) ; `/ws/ssh` = action opérationnelle Host → `operator` — **à valider contre la matrice spec 08 § Hosts en implémentation** (divergence à signaler si la matrice diffère) ;
- **Décision 3 — `/ws/ssh` TOFU STRICT** : via `build_ssh_kwargs(target=...)` — divergence/inconnu → fermeture WS (1011), message générique au client (**jamais d'empreinte en clair**), détail en log serveur ;
- **Décision 7 — `/ws/batch` émetteur-ready** (voir constat ci-dessus) ;
- **Décision 8 — Console VNC explicitement reportée** (Roadmap VMs) : non implémentée + note dans WEBSOCKET-REAL-TIME.md §3.2 et README module (aucun code — un éventuel `/ws/console` retourne 404 naturellement) ;
- **Décision 9 — Config** : réutiliser les settings de 164.1 (`ws_heartbeat_interval_seconds`, `ws_heartbeat_timeout_factor`…) pour l'expiration des nouveaux canaux ; **aucune migration Alembic**, aucune nouvelle dépendance (asyncssh déjà présent).

### Points d'attention mère concernés

- **Point 1 — Nommage** : montés sous `/api/v1/ws/ssh/{host_id}`, `/api/v1/ws/journal/{host_id}`, `/api/v1/ws/batch/{batch_id}` (cohérents avec les 5 existants, non-régression) ; la cible canonique `/ws/...` (spec 09) reste non satisfaite — l'écart reste documenté WEBSOCKET §3.2, arbitrage global reporté à STORY-252 ;
- **Point 3 — Rôles exacts** : journal/batch = viewer, ssh = operator (fondés spec 15) — à confronter à la matrice spec 08 § Hosts pendant l'implémentation ;
- **Point 4 — Session SSH interactive** : plus grosse incertitude d'implémentation (PTY asyncssh bidirectionnel + resize + xterm.js) — **signaler en divergence si un scope minimal s'impose**.

### Risques hérités (volet canaux)

- **Session SSH interactive (PTY asyncssh × xterm.js)** : plus grosse incertitude technique — hypothèse channel/process asyncssh PTY avec `term_type`/`term_size` + resize ; si le PTY complet s'avère trop lourd, un scope minimal (shell ligne à ligne) est un **fallback à signaler comme divergence** ;
- Sessions SSH persistantes : rate limit (3/user, calqué terminal.py) + audit (logger dédié `ssh_session_audit`) + fermeture propre à la déconnexion WS ;
- `journalctl` absent (Host non-systemd) → message `error` explicite + fermeture propre ;
- Token en query param : mécanisme déjà en place sur les canaux dédiés (jamais loggé — longueur seulement, pattern dependencies.py) ;
- `disable_auth` préservé sur les 3 nouveaux canaux (AC 5 mère).

### Checklist sécurité (règle 40) — volet canaux

- **AuthN/AuthZ** : `get_current_user_ws` (query param token) + `ensure_role_ws` **avant accept** sur chacun des 3 canaux (rôles décision 2) ; isolation organisation pour `/ws/journal/{host}` (pattern `UserOrganizationService.is_member`) ;
- **Validation & injection** : `host_id`/`batch_id` typés (UUID) et résolus (404 si introuvable) ; paramètres `tail`/follow bornés ; **aucune commande shell construite à partir d'entrées utilisateur non validées** (`journalctl -f -n <tail>` avec `tail` entier borné) ;
- **Données sensibles** : empreintes SSH **jamais en clair** côté client (message générique, détail serveur) ; token jamais loggé ; flux SSH/journal sans extraction de secrets côté logs serveur ;
- **Audit & traçabilité** : audit dédié session SSH (logger `ssh_session_audit`, pattern `log_terminal_audit`) — ouverture/fermeture, user, host, durée ; connexions aux 3 canaux tracées (logs structurés).

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend l'AC 1 de la mère)* : Les 3 canaux `/ws/ssh/{host}`, `/ws/journal/{host}`, `/ws/batch/{batch_id}` sont montés avec auth obligatoire — tests : connexion **sans token → refusée (fermeture 1008)** sur chacun ; avec token valide → connecté ; un **viewer ne peut pas ouvrir `/ws/ssh`** (RBAC par action WS, spec 15) alors qu'il accède à `/ws/journal` et `/ws/batch` ; `/ws/console` VNC explicitement **absent et documenté** comme reporté (Roadmap VMs). *(NB : voir divergence D1 — `/ws/journal` est monté Operator+ conformément à la matrice spec 08 § Hosts, le viewer y est donc refusé ; l'AC est satisfait au sens de la matrice de référence.)*
- [x] AC 2 *(reprend l'AC 2 de la mère)* : `/ws/ssh/{host}` ouvre une session SSH interactive vers le Host (via STORY-131 : clé référencée + empreinte vérifiée — **divergence d'empreinte = blocage**, fermeture 1011 message générique), `/ws/journal/{host}` streame le journal système (`journalctl -f`, query `tail`), `/ws/batch/{batch_id}` diffuse `start`/`progress`/`complete` d'une **opération groupée simulée** — chacun testé avec un abonné authentifié (**mock des runners SSH/journal côté tests unitaires**).
- [x] AC 3 *(reprend la partie canaux de l'AC 5 de la mère)* : Non-régression — les 5 canaux existants fonctionnent toujours ; `disable_auth` en dev préservé (les 3 nouveaux canaux inclus) ; plugins/`default_message_handlers` intacts ; couverture ≥ 80 % sur les modules touchés (suite exhaustive renforcée par STORY-165) ; build + lint + tests passent.

## Références spécification

- [`09-api.md`](../../docs/general_specs/09-api.md) — **§ WebSocket** (référence des 8 canaux canoniques, JWT en query parameter, format des messages, `/ws/batch` progression des opérations groupées) ;
- [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) — §3.2 (canaux, état implémenté vs cible), §7 (auth par canal) ;
- [`02-familles-workloads.md`](../../docs/general_specs/02-familles-workloads.md) — § Famille Hosts (verbes SSH, journalctl — usages des canaux `/ws/ssh` et `/ws/journal`) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Authentification et RBAC (permissions vérifiées sur chaque action WebSocket), § Hosts distants SSH (clés réutilisables, empreintes, anti-tempête) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-5, §2.C C3, §6 (VNC hors périmètre) ;
- [`backend_status.md`](../../docs/backend_status.md) — §3.17, §8.

## Dépendances

- **[STORY-164.1](STORY-164.1-protocole-heartbeat-expiration-ack.md) — pré-requis recommandé** : helper d'expiration (`websocket/heartbeat.py`) + settings `ws_heartbeat_*` posés par 164.1 — les 3 nouveaux canaux consomment le même helper (fermeture des connexions muettes ~2 intervalles, décision 4 mère) ; si 164.1 n'est pas fusionnée, implémenter a minima l'expiration via les settings dans cette story et le signaler en divergence ;
- **STORY-100** (auth WS — EPIC-011) — **DONE, vérifiée** : `get_current_user_ws` refus 1008 — les nouveaux canaux naissent avec l'auth obligatoire (query param `?token=`, décision 1) ;
- **STORY-131** (SSH keys + empreintes — EPIC-012) — **DONE, vérifiée** : `build_ssh_kwargs` TOFU STRICT, [`models/ssh_key.py`](../../backend/app/models/ssh_key.py), [`models/host_ssh_fingerprint.py`](../../backend/app/models/host_ssh_fingerprint.py) — socle direct des canaux ssh/journal ;
- **STORY-122.6** (RBAC WS) — **DONE** : `ensure_role_ws` réutilisé tel quel (rôles décision 2) ;
- **STORY-162/163** (bus + consommateurs) — **DONE** : les nouveaux canaux ne consomment pas le bus (transport direct) — garde-fou : ne pas casser l'architecture plugins ;
- **STORY-165** (tests WS exhaustifs) — **TODO** : 164.2 fournit les tests ciblés de ses AC, 165 la suite exhaustive (partage de la cible ≥ 80 %) ;
- **STORY-173** (`/compute` browse/prune + check-updates) — **TODO** : **première alimentation réelle attendue** de `/ws/batch` (le service d'émission posé ici est « émetteur-ready ») ;
- **STORY-252** (corrections consolidées specs) : portera l'arbitrage du nommage `/ws/...` vs `/api/v1/ws/...` (point 1) ;
- **Technique** : aucune nouvelle dépendance Python (asyncssh déjà présent) ; **aucune migration Alembic** ; services externes : aucun (runners mockés en tests).

## État d'avancement technique

*(cochage progressif pendant treat-story — volet canaux de l'analyse STORY-164)*

- [x] Tâche 1 — Résolution Host + vérification d'accès partagée (`websocket/host_access.py`)
- [x] Tâche 2 — Canal `/ws/ssh/{host}` : handler session SSH interactive (`websocket/ssh_session.py`)
- [x] Tâche 3 — Route `/ws/ssh/{host_id}` dans le router (`api/v1/websockets.py`)
- [x] Tâche 4 — Canal `/ws/journal/{host}` : handler streaming journalctl (`websocket/journal.py`) + route
- [x] Tâche 5 — Canal `/ws/batch/{batch_id}` : manager + émission `broadcast_batch_event` (`websocket/batch.py`) + route
- [x] Tâche 6 — Rapport VNC reporté : WEBSOCKET-REAL-TIME.md §3.2 + README module
- [x] Tests — auth 1008/RBAC par canal, flux mockés, TOFU, batch simulé, non-régression

## Tâches d'implémentation détaillées

> Séquence issue de l'analyse STORY-164 (volet canaux), adaptée à ce périmètre. Aucune mécanique de protocole transverse (164.1), aucun frontend (164.3).

### Tâche 1 : Résolution Host + vérification d'accès partagée

**Objectif :** factoriser la résolution du host + isolation organisation (pattern `verify_deployment_access`).

**Fichiers :**
- `backend/app/websocket/host_access.py` — **Créer** : `resolve_host_and_check_access(host_id, user, session)` — résolution `Target` par `id` (404 si introuvable, pattern [`target_scanner_service.py`](../../backend/app/services/target_scanner_service.py) l.186-210 : `target.host`/`port`/`ssh_key_id` + `target.decrypted_credentials`) ; vérification d'accès (401/403 + isolation organisation via `UserOrganizationService.is_member`, pattern [`deployment_logs.py`](../../backend/app/websocket/deployment_logs.py) l.23-53) ; utilisé par `/ws/ssh` et `/ws/journal`.

**Dépend de :** Aucune

### Tâche 2 : Handler session SSH interactive

**Objectif :** le morceau le plus lourd — session SSH PTY bidirectionnelle, TOFU STRICT, rate limit, audit (modèle [`terminal.py`](../../backend/app/websocket/terminal.py)).

**Fichiers :**
- `backend/app/websocket/ssh_session.py` — **Créer** : handler `handle_ssh_session(websocket, host_id, user, session)` — connexion asyncssh via `build_ssh_kwargs(target=...)` (STORY-131, **TOFU STRICT** — jamais `known_hosts: None`) : empreinte inconnue/non acceptée (`SSHHostKeyNotAcceptedError`) ou divergence (`SSHHostKeyMismatchError`) → fermeture WS **1011**, message générique au client (**jamais d'empreinte en clair**), détail en log serveur ; session interactive : hypothèse channel/process asyncssh PTY (`term_type`/`term_size` + resize — à confirmer en implémentation, pattern `ExecSession` du terminal adapté) ; **rate limit 3 sessions/user** (store mémoire, calqué `terminal_sessions` l.31-32) ; **audit dédié** logger `ssh_session_audit` (pattern `log_terminal_audit` l.76-119) — ouverture/fermeture, user, host, durée ; pont bidirectionnel WS↔PTY ; expiration des connexions muettes via helper 164.1 ; fermeture propre (WS ↔ process SSH) à la déconnexion ; `journalctl`-style erreurs SSH → message `error` explicite ; **si le PTY complet s'avère trop lourd : scope minimal shell ligne à ligne à signaler en divergence** (point 4).

**Dépend de :** Tâche 1, STORY-164.1 (helper expiration — recommandé), STORY-131 (DONE)

### Tâche 3 : Route `/ws/ssh/{host_id}`

**Objectif :** exposer le canal avec auth + RBAC avant accept (pattern des 4 canaux dédiés).

**Fichiers :**
- `backend/app/api/v1/websockets.py` — **Modifier** : `@router.websocket("/ssh/{host_id}")` + docstring détaillée (pattern l.115/l.200/l.248) + `user: User = Depends(get_current_user_ws)` (query param `?token=`, décision 1) + `await ensure_role_ws(websocket, user, "operator", session)` **avant accept** (décision 2) + délégation au handler `ssh_session.py` ; monté sous `/api/v1/ws/ssh/{host_id}` (point 1 — nommage réel, écart canonique tracé).

**Dépend de :** Tâche 2

### Tâche 4 : Canal `/ws/journal/{host}` — streaming journalctl

**Objectif :** canal lecture streaming, modèle [`container_logs.py`](../../backend/app/websocket/container_logs.py) transposé à `journalctl` sur SSH.

**Fichiers :**
- `backend/app/websocket/journal.py` — **Créer** : handler `handle_journal(websocket, host_id, user, session, tail)` — résolution accès (Tâche 1) ; exécution `journalctl -f -n <tail>` via asyncssh (`SSHCommandExecutor` [`commands.py`](../../backend/app/services/commands.py) l.167-242 ou connection directe du `build_ssh_kwargs`) ; streaming → messages `{"type": "log", ...}` + `stream_status` (modèle container_logs) ; `tail` entier **borné** (validation query) ; **`journalctl` absent** (Host non-systemd, exit code non nul) → message `error` explicite + fermeture propre ; expiration connexions muettes (helper 164.1) + réponse `pong` au ping client ;
- `backend/app/api/v1/websockets.py` — **Modifier** : `@router.websocket("/journal/{host_id}")` + docstring + `get_current_user_ws` + `ensure_role_ws(..., "viewer", ...)` avant accept + query param `tail` borné ; monté sous `/api/v1/ws/journal/{host_id}`.

**Dépend de :** Tâche 1, STORY-164.1 (helper — recommandé)

### Tâche 5 : Canal `/ws/batch/{batch_id}` — émetteur-ready

**Objectif :** canal de progression des opérations groupées, livré avec service d'émission testé (décision 7 — aucun batch réel n'existe, vérifié).

**Fichiers :**
- `backend/app/websocket/batch.py` — **Créer** : manager dédié `BatchConnectionManager` (réutilise [`ConnectionManager`](../../backend/app/websocket/connection_managers.py) l.107-184, clé `batch_id`) + fonction d'émission **`broadcast_batch_event(batch_id, phase, data)`** sur le modèle de `_broadcast_deployment_event` ([`broadcasting.py`](../../backend/app/websocket/broadcasting.py) l.41-64 — timestamp auto + manager + dispatch plugins) — phases `start`/`progress`/`complete`/`error` (spec 09 §WebSocket, enveloppe `type`/`data`) ; **documentation explicite du branchement futur** (STORY-173 check-updates — commentaire + docstring « émetteur-ready ») ;
- `backend/app/api/v1/websockets.py` — **Modifier** : `@router.websocket("/batch/{batch_id}")` + docstring + `get_current_user_ws` + `ensure_role_ws(..., "viewer", ...)` avant accept (le déclenchement d'une opération groupée passe par l'API REST RBAC-protégée — décision 2) ; accept → boucle d'écoute avec expiration (helper 164.1) ; `batch_id` typé (UUID/chaîne validée) ; monté sous `/api/v1/ws/batch/{batch_id}`.

**Dépend de :** STORY-164.1 (helper — recommandé)

### Tâche 6 : Rapport VNC — documentation

**Objectif :** tracer explicitement le report de la console VNC (décision 8).

**Fichiers :**
- `docs/technical_specs/WEBSOCKET-REAL-TIME.md` — **Modifier** : §3.2 — note « console VNC (`/ws/console/{machine_id}`) explicitement reportée à la Roadmap VMs (machines — plan §6) ; non implémentée ; un éventuel `/ws/console` retourne 404 naturellement » ;
- `backend/app/websocket/README.md` — **Modifier** : même note dans la liste des canaux (complété : 8 canaux — 5 existants + 3 nouveaux, VNC reporté).

**Dépend de :** Tâches 3-5 (canaux livrés)

### Tâche 7 : Tests et validation

**Objectif :** valider les AC 1-3 (voir « Tests à écrire ») + couverture ≥ 80 % sur `ssh_session.py`, `journal.py`, `batch.py`, `host_access.py`.

**Fichiers :**
- `backend/tests/unit/test_websocket/test_ws_ssh_session.py` — **Créer** ;
- `backend/tests/unit/test_websocket/test_ws_journal.py` — **Créer** ;
- `backend/tests/unit/test_websocket/test_ws_batch.py` — **Créer** ;
- Tests existants (`test_ws_auth.py`, `test_ws_rbac.py`, suite module) — **Non-régression**.

**Dépend de :** Tâches 1-6

## Tests à écrire

> Principes directeurs de l'analyse mère (AC 1, 2, 5) — 401/1008 sans token, RBAC viewer↔operator, runners SSH mockés, couverture ≥ 80 % ; patterns [`test_ws_auth.py`](../../backend/tests/unit/test_websocket/test_ws_auth.py) / [`test_ws_rbac.py`](../../backend/tests/unit/test_websocket/test_ws_rbac.py). La suite exhaustive relève de STORY-165.

### Backend

- `backend/tests/unit/test_websocket/test_ws_ssh_session.py` —
  - connexion **sans token → close 1008** ; token valide → connecté ;
  - **viewer refusé** (1008 « Insufficient permissions »), operator accepté ;
  - host introuvable → 404/close appropriée ; host hors organisation → refus (isolation) ;
  - **TOFU STRICT** (mocks `AsyncMock` sur `build_ssh_kwargs`) : empreinte inconnue → `SSHHostKeyNotAcceptedError` → close **1011**, message **sans empreinte en clair** ; divergence → `SSHHostKeyMismatchError` → close 1011 ;
  - rate limit : 4ᵉ session simultanée du même user → refus ;
  - audit `ssh_session_audit` : ouverture/fermeture tracées (user, host, durée — **pas de secret**) ;
  - pont bidirectionnel : entrée WS → PTY (mock), sortie PTY → WS ; resize propagé (si PTY complet) ;
  - expiration connexion muette (timeout réduit en test) ;
  - `disable_auth` : mode dev → connexion sans token acceptée (auto-login).
- `backend/tests/unit/test_websocket/test_ws_journal.py` —
  - sans token → 1008 ; token valide → connecté ; **viewer accepté** ;
  - streaming : lignes `journalctl` (mock runner) → messages `{"type":"log"}` + `stream_status` ; `tail` transmis et **borné** (rejet d'un `tail` invalide) ;
  - host non-systemd (`journalctl` absent, mock exit ≠ 0) → message `error` + fermeture propre ;
  - TOFU STRICT identique (mock `build_ssh_kwargs`) ;
  - isolation organisation (host d'une autre org → refus).
- `backend/tests/unit/test_websocket/test_ws_batch.py` —
  - sans token → 1008 ; token valide → connecté ; **viewer accepté** ;
  - opération groupée **simulée** : un abonné authentifié reçoit `start` → `progress` → `complete` via `broadcast_batch_event` (phases spec 09, enveloppe `type`/`data`) ; phase `error` diffusée ;
  - isolation : abonné du batch A ne reçoit pas les événements du batch B ; purge des connexions mortes (manager) ;
  - expiration connexion muette (timeout réduit).
- Non-régression — les 5 canaux existants fonctionnent (suite WS verte) ; plugins par défaut + `default_message_handlers` intacts ; `disable_auth` préservé.

### Commandes de validation

```bash
poetry run pytest backend/tests/unit/test_websocket/test_ws_ssh_session.py backend/tests/unit/test_websocket/test_ws_journal.py backend/tests/unit/test_websocket/test_ws_batch.py -v
poetry run pytest backend/tests/unit/test_websocket/ -v --tb=short
make backend-test-unit
make backend-lint && make backend-typecheck
```

## Notes d'implémentation

**Date :** 2026-10-23 — `treat-story` (7/7 tâches exécutées, tests verts)

### Fichiers créés

- `backend/app/websocket/host_access.py` — `resolve_host_and_check_access` (résolution `Target` 404/401/403 + isolation organisation `UserOrganizationService.is_member`) + `resolve_ssh_username` (credentials → access_profile → root)
- `backend/app/websocket/ssh_session.py` — handler `/ws/ssh` : PTY asyncssh bidirectionnel (`create_process(term_type, term_size)` + `change_terminal_size` — **PTY complet, pas de fallback ligne-à-ligne**), TOFU STRICT via `build_ssh_kwargs(target=…)` (empreinte inconnue/divergente → close **1011** message générique `TOFU_REFUSED_CLIENT_MESSAGE`, jamais d'empreinte en clair), rate limit 3 sessions/user (`ssh_sessions`, calqué terminal), audit logger dédié `ssh_session_audit` (connect/disconnect + durée, sans secrets), expiration muette via `receive_with_expiry` (164.1)
- `backend/app/websocket/journal.py` — handler `/ws/journal` : `journalctl -f -n <tail> --no-pager -o short-iso` via SSH TOFU STRICT, `tail` borné `[0, 10000]` par `validate_journal_tail` (double garde route `Query(ge/le)` + handler — anti-injection), streaming `log` + `stream_status` (started/ended/failed), surveillant d'exit ≠ 0 → message `error` explicite (Host non-systemd), `pong` + expiration 164.1
- `backend/app/websocket/batch.py` — manager dédié `batch_manager` (réutilise `ConnectionManager`, clé `batch_id`) + fonction d'émission `broadcast_batch_event(batch_id, phase, data)` (phases `start`/`progress`/`complete`/`error` validées, timestamp auto, enveloppe `type`/`data`, dispatch plugins via `user_manager.dispatch_to_plugins`) — **émetteur-ready documenté** (branchement futur STORY-173 dans docstring)
- `backend/tests/unit/test_websocket/test_ws_ssh_session.py` (23 tests) / `test_ws_journal.py` (16 tests) / `test_ws_batch.py` (12 tests)

### Fichiers modifiés

- `backend/app/api/v1/websockets.py` — 3 endpoints `@router.websocket` (`/ssh/{host_id}` operator, `/journal/{host_id}` operator, `/batch/{batch_id}` viewer) + docstrings détaillées, `ensure_role_ws` **avant accept** (pattern des 4 canaux dédiés) ; montés sous `/api/v1/ws/...` (écart nommage canonique tracé, point 1)
- `docs/technical_specs/WEBSOCKET-REAL-TIME.md` §3.2 — table état implémenté 8 canaux + note report VNC (décision 8)
- `backend/app/websocket/README.md` — arborescence à jour + table des 8 canaux (rôles, handlers) + note VNC reportée
- `backend/tests/unit/test_api/test_rbac_exhaustivite.py` — garde STORY-122.6 étendue aux 3 nouveaux canaux (dépendance `get_current_user_ws` + comptes `ensure_role_ws` par rôle + inventaire 8 canaux)

### Décisions techniques

- **D1 — RBAC journal/ssh = Operator+** : la story exigeait la validation contre la matrice **spec 08 § Hosts** (l.104 : « SSH/journalctl (lecture) » classé *Opération (Operator+)*) — la décision d'analyse « journal = viewer » **diverge de la matrice** ; conformément au protocole prévu, la matrice prime : `ensure_role_ws(..., "operator")` sur `/ws/ssh` **et** `/ws/journal` (divergence signalée ; arbitrage final à STORY-252 si besoin). `/ws/batch` = viewer (suivi de lecture, déclenchement via API REST RBAC-protégée).
- **PTY complet** (point 4 de l'analyse) : `create_process` avec `term_type="xterm-256color"` + `term_size` + resize `change_terminal_size` — le fallback « shell ligne à ligne » n'a **pas** été nécessaire (divergence évitée).
- **Batch** : `ConnectionManager.connect` fait l'accept (pattern deployment_logs, pas de double accept) ; l'émetteur simulé des tests patche `periodic_ping` pour s'exécuter dans la boucle du TestClient (le cross-thread `asyncio.run` ne partage pas la socket starlette).
- **Fermetures** : `connection.close()` asyncssh est sync (mypy) ; ordre de fermeture `streaming_task → audit disconnect → process → connection` dans le `finally` de ssh_session.
- Réutilisation 164.1 : `receive_with_expiry` sur les 3 canaux, `periodic_ping` sur journal/batch (pas sur ssh, canal émetteur continu — modèle terminal). **Le fallback minimal prévu si 164.1 n'était pas fusionnée n'a pas été nécessaire** (divergence évitée).

### Tests & validation (exécutés)

- `poetry run pytest backend/tests/unit/test_websocket/` → **172 passed** (123 préexistants + 49 nouveaux, incl. suites 164.1 heartbeat/ack)
- `poetry run pytest tests/unit/ -p no:randomly` → **2189 passed** (non-régression backend complète)
- Couverture nouveaux modules : `host_access.py` **100 %**, `batch.py` **96 %**, `ssh_session.py` **88 %**, `journal.py` **84 %** (≥ 80 % exigé)
- `make backend-lint` (isort/black/flake8/mypy/bandit) **OK sur les fichiers touchés** — 0 erreur mypy sur les 5 fichiers (les erreurs résiduelles affichées par mypy sont préexistantes hors périmètre : `background_tasks.py`, `target_scanner_service.py`, `jwt.py`, `connectivity.py` — 5 erreurs connues + connexes)

### Difficultés rencontrées

- API asyncssh : `ConnectionError`/`ConnectError` inexistantes → `ConnectionLost(reason)` (sous-classe d'`asyncssh.Error`) ; `ChannelOpenError(lang, reason)` prend 2 args positionnels ; `SSHClientProcess.channel.change_terminal_size` (pas `change_pty_size`).
- Garde d'inventaire STORY-122.6 (`test_rbac_exhaustivite.py`) verrouillait « exactement 5 canaux » : extension attendue à 8 (comptes par rôle, inventaire) — garde renforcée, pas affaiblie.
