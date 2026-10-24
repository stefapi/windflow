# STORY-164.1 : Mécaniques de protocole serveur — heartbeats avec expiration des connexions muettes et acknowledgment des messages critiques (P2-5, partie protocole)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-164 ([ABANDONED — découpe proactive post-analyse le 2026-10-23](STORY-164-canaux-websocket-manquants-durcissement.md))
**Item plan :** P2-5 (axes C3, C4 — rapports §8.2, §8.4) — ampleur **M**

> **Périmètre (découpe)** : cette sous-story reprend le **volet protocole serveur transverse** de STORY-164 — expiration des connexions muettes (heartbeat ~2 intervalles appliqué à **tous** les canaux, les 5 existants) et **acknowledgment** des messages critiques (champ `id` UUID sur l'enveloppe, registre avec TTL ~30 s, re-diffusion à la reconnexion, dégradation journalisée) + settings dédiés. Couvre l'AC 3 de la mère et la partie protocole de son AC 5 (non-régression). Les 3 canaux manquants (`/ws/ssh`, `/ws/journal`, `/ws/batch`) sont portés par [STORY-164.2](STORY-164.2-canaux-ws-ssh-journal-batch.md) (qui **réutilise** le helper d'expiration posé ici) ; la politique de reconnexion frontend et le client type documenté par [STORY-164.3](STORY-164.3-reconnexion-unifiee-client-type.md).

## Description

En tant qu'utilisateur WindFlow connecté en temps réel, je veux que le serveur **expire les connexions muettes** (aucune activité — `pong` ou tout message — pendant ~2 intervalles de heartbeat) et **fiabilise la livraison des messages critiques** via un mécanisme d'acknowledgment (identifiant UUID, rétention TTL ~30 s, re-diffusion à la reconnexion, dégradation journalisée) — afin qu'il n'existe plus de connexions zombies côté serveur ([`receive_text()`](../../backend/app/websocket) attend indéfiniment aujourd'hui) et qu'un message critique émis pendant une déconnexion brève ne soit pas perdu silencieusement.

**Problème constaté** ([WEBSOCKET-REAL-TIME.md §8.2, §8.4](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md)) : seul le canal général émet un ping serveur **30 s** **sans aucun contrôle des `pong`** ; `receive_text()` attend indéfiniment partout ; l'acknowledgment est totalement absent (aucune notion d'`id` dans [`schemas/websocket_events.py`](../../backend/app/schemas/websocket_events.py)).

## Contexte technique

> Extrait de l'analyse STORY-164 (2026-10-23, `analyse-story`) — volet protocole serveur. Fondée sur le code réel du dépôt (fichiers/lignes cités). Aucun code modifié.

### État actuel (cartographie)

- **Heartbeat** : seul le canal général émet un ping serveur **30 s** ([`general.py`](../../backend/app/websocket/general.py) l.158-175) **sans aucun contrôle des `pong`** ; `receive_text()` attend indéfiniment partout (WEBSOCKET §8.2) ; les canaux dédiés ([`deployment_logs.py`](../../backend/app/websocket/deployment_logs.py), [`container_logs.py`](../../backend/app/websocket/container_logs.py), [`container_stats.py`](../../backend/app/websocket/container_stats.py), [`terminal.py`](../../backend/app/websocket/terminal.py)) répondent au ping client mais **n'émettent pas de heartbeat périodique serveur** ;
- **Ack** : [`schemas/websocket_events.py`](../../backend/app/schemas/websocket_events.py) — `WebSocketEventType` sans aucune notion d'`id`/ack ; le point d'entrée du dispatch du message `ack` côté serveur est la boucle de réception du canal général ([`general.py`](../../backend/app/websocket/general.py) l.178+) ;
- **Émission** : [`broadcasting.py`](../../backend/app/websocket/broadcasting.py) `_broadcast_deployment_event` (l.41-64 — timestamp auto + manager + dispatch plugins) = modèle d'enveloppe à étendre pour l'`id` UUID sur types critiques ;
- **Plugins (garde-fou §2.G)** : [`websocket/plugins/__init__.py`](../../backend/app/websocket/plugins/__init__.py) — 4 plugins par défaut depuis STORY-163 ; l'extension ne doit casser ni `plugin_manager`, ni `default_message_handlers`, ni les 5 canaux ; les clés mortes `"deployment_events"`/`"deployment_progress_{id}"` de [`deployment_notifications.py`](../../backend/app/websocket/plugins/deployment_notifications.py) ont été tracées par STORY-163 **pour cette story** — statuer (nettoyage léger ou documentation) sans réécrire le contrat du plugin ;
- **Tests de référence** : [`test_ws_auth.py`](../../backend/tests/unit/test_websocket/test_ws_auth.py) (42 cas), [`test_ws_rbac.py`](../../backend/tests/unit/test_websocket/test_ws_rbac.py), [`test_plugins_default.py`](../../backend/tests/unit/test_websocket/test_plugins_default.py).

### Décisions d'analyse mère concernées (à appliquer telles quelles)

- **Décision 4 — Expiration heartbeat** : baseline 30 s conservée ; fermeture serveur si **aucune activité reçue** (pong ou tout message) pendant ~2 intervalles — `asyncio.wait_for(receive_text(), timeout=2×interval)` + **reset à chaque message reçu**, appliqué à **tous les canaux** ; recommandation : le serveur ping périodiquement aussi sur les canaux dédiés (même mécanique que [`general.py`](../../backend/app/websocket/general.py) l.158-175) ;
- **Décision 5 — Ack** : liste explicite **configurable** de types critiques (défaut proposé : statuts terminaux `DEPLOYMENT_STATUS_CHANGED` + `NOTIFICATION_USER`) ; `id` UUID ajouté à l'enveloppe **uniquement pour ces types** ; registre mémoire **par connexion** TTL ~30 s ; re-diffusion à la reconnexion du **même utilisateur** ; dégradation loggée WARNING (métriques via STORY-172 quand [`websocket/metrics.py`](../../backend/app/websocket/metrics.py) sera branché) ; **exclus par conception** : streaming logs, heartbeats, toasts ;
- **Décision 9 — Config** : nouvelles settings `ws_heartbeat_interval_seconds` (30), `ws_heartbeat_timeout_factor` (2), `ws_ack_ttl_seconds` (30), `ws_ack_critical_types` (liste) ; **aucune migration Alembic**, aucune nouvelle dépendance.

### Points d'attention mère concernés

- **Point 5 — Périmètre de l'ack « par connexion »** : les messages critiques transitent par le canal général (abonnements) ; la re-diffusion « à la reconnexion » suppose d'identifier l'utilisateur à travers ses connexions successives — **registre par user vs par socket à trancher en implémentation** (re-diffusion visée : reconnexions du même utilisateur) ;
- **Point 6 — Clés mortes `deployment_notifications`** (`"deployment_events"`, `f"deployment_progress_{id}"`) : statuer sans réécrire le contrat du plugin ;
- **Point 7 — Heartbeat serveur sur les canaux dédiés** : l'expiration « ~2 intervalles » doit définir si le serveur se met à pinger périodiquement (recommandé : oui, même mécanique que general.py) ou si seule l'inactivité est traquée.

### Risques hérités (volet protocole)

- Le timeout `2×interval` (60 s par défaut) rend les tests lents → **timeout réduit en test** via settings (jamais de `sleep` réel long) ;
- Ne pas casser la boucle de réception du terminal (canal interactif bidirectionnel) : l'expiration doit se déclencher sur l'inactivité **totale** (aucun message dans les deux sens), pas gêner les sessions actives ;
- Exclusion stricte des types streaming/heartbeat/toast de l'ack (sinon tempête d'acks sur les flux de logs).

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend la partie heartbeat de l'AC 3 de la mère)* : **Expiration des connexions muettes** — une connexion qui ne répond pas (aucun `pong` ni aucun message pendant ~2 intervalles) est **fermée côté serveur** sur l'ensemble des canaux — test avec un mock client muet (timeout réduit en test) ; une connexion active (messages réguliers) n'est **jamais** fermée ; le serveur émet un ping périodique sur les canaux dédiés (recommandation décision 4).
- [x] AC 2 *(reprend la partie ack de l'AC 3 de la mère)* : **Acknowledgment** — les messages critiques (types configurables, défaut `DEPLOYMENT_STATUS_CHANGED` + `NOTIFICATION_USER`) portent un `id` UUID ; le client accuse réception (`{"type":"ack","data":{"id":…}}`) ; un message non acquitté au-delà du TTL (~30 s) est **re-diffusé à la reconnexion** du même utilisateur et la dégradation est **journalisée** (WARNING) ; les logs streaming, heartbeats et toasts sont **exclus** de l'ack.
- [x] AC 3 *(reprend la partie protocole de l'AC 5 de la mère)* : Non-régression — les 5 canaux existants (général, deployment logs, terminal, container logs/stats) fonctionnent toujours ; `disable_auth` en dev préservé ; les plugins par défaut (STORY-163) et `default_message_handlers` intacts (les clés mortes `deployment_notifications` sont statuées sans réécrire le contrat) ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) — **§8.2** (heartbeat + expiration cible ~2 intervalles), **§8.4** (acknowledgment cible complet), §7 (auth par canal), §10.3 (écarts) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § WebSocket (format des messages, enveloppe `type`/`data`) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Authentification et RBAC (permissions vérifiées sur chaque action WebSocket) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-5, §2.C C3/C4 ;
- [`backend_status.md`](../../docs/backend_status.md) — §3.17, §8 (module WebSocket).

## Dépendances

- **STORY-100** (auth WS obligatoire — EPIC-011) — **DONE, vérifiée dans le code** : `get_current_user_ws` (refus 1008), `authenticate_ws_first_message` (30 s) — le protocole s'applique derrière l'auth existante, aucune surface d'auth nouvelle ;
- **STORY-122.6** (RBAC WS) — **DONE** : `ensure_role_ws` actif sur les 4 canaux dédiés — non modifié ici ;
- **STORY-162/163** (bus + consommateurs) — **DONE** : les messages critiques partent du canal général (transport direct, pas de consommation bus) ; garde-fou : ne pas casser les 4 plugins par défaut ni `default_message_handlers` ;
- **STORY-165** (tests WebSocket exhaustifs) — **TODO** : 164.1 fournit les tests ciblés de ses AC, 165 la suite exhaustive du module (partage de la cible ≥ 80 %) ; analyse conjointe recommandée ;
- **STORY-172** (Prometheus réel) — **TODO** : branchera [`websocket/metrics.py`](../../backend/app/websocket/metrics.py) — la « mesure » de dégradation ack reste **log-only WARNING** jusque-là ;
- **Conditionne** : [STORY-164.2](STORY-164.2-canaux-ws-ssh-journal-batch.md) (les 3 nouveaux canaux réutilisent le helper d'expiration + le pattern ping serveur posés ici — **pré-requis recommandé**) et [STORY-164.3](STORY-164.3-reconnexion-unifiee-client-type.md) (le client type documente le contrat ack `id`/TTL/re-diffusion défini ici — dépendance documentaire, non bloquante pour la partie reconnexion).
- **Technique** : aucune nouvelle dépendance Python ; **aucune migration Alembic** ; services externes : aucun.

## État d'avancement technique

*(cochage progressif pendant treat-story — volet protocole de l'analyse STORY-164)*

- [x] Tâche 1 — Settings protocole WS (`config.py`)
- [x] Tâche 2 — Helper d'expiration réutilisable (`websocket/heartbeat.py`)
- [x] Tâche 3 — Application au canal général (`general.py` : contrôle des `pong` + dispatch `ack`)
- [x] Tâche 4 — Application aux 4 canaux dédiés (expiration + ping serveur périodique)
- [x] Tâche 5 — Enveloppe : `id` UUID sur les types critiques (`schemas/websocket_events.py` + `broadcasting.py`)
- [x] Tâche 6 — Registre d'ack (UUID + TTL + re-diffusion + dégradation WARNING)
- [x] Tâche 7 — Statuer sur les clés mortes `deployment_notifications`
- [x] Tests — expiration (client muet), ack (TTL, re-diffusion, exclusions), non-régression 5 canaux

## Tâches d'implémentation détaillées

> Séquence issue de l'analyse STORY-164 (volet protocole), adaptée à ce périmètre. Aucun canal nouveau (164.2), aucun frontend (164.3).

### Tâche 1 : Settings protocole WS

**Objectif :** configurer le protocole (pattern `Settings` existant, décision 9).

**Fichiers :**
- `backend/app/config.py` — **Modifier** : `ws_heartbeat_interval_seconds: int = 30`, `ws_heartbeat_timeout_factor: int = 2` (fermeture après `factor × interval` sans activité), `ws_ack_ttl_seconds: int = 30`, `ws_ack_critical_types: list[str]` (défaut : `["DEPLOYMENT_STATUS_CHANGED", "NOTIFICATION_USER"]`) — `Field(default=…, description=…, alias=…)` pattern config existant ; validation défensive (interval > 0, factor ≥ 1, ttl > 0).

**Dépend de :** Aucune

### Tâche 2 : Helper d'expiration réutilisable

**Objectif :** poser la mécanique transverse « fermer si muet ~2 intervalles », consommable par tous les canaux (y compris les 3 futurs de 164.2).

**Fichiers :**
- `backend/app/websocket/heartbeat.py` — **Créer** : helper d'expiration — encapsulation du pattern `asyncio.wait_for(websocket.receive_text(), timeout=ws_heartbeat_timeout_factor × ws_heartbeat_interval_seconds)` avec **reset du délai à chaque message reçu** (décision 4) ; helper `periodic_ping` (émission `ping` serveur à l'intervalle configuré, même mécanique que [`general.py`](../../backend/app/websocket/general.py) l.158-175, à factoriser) ; fermeture propre (close code documenté côté serveur) + log structuré de l'expiration (jamais de données sensibles) ; timeout borné par les settings → **réductible en test** sans `sleep` long.

**Dépend de :** Tâche 1

### Tâche 3 : Application au canal général + dispatch `ack`

**Objectif :** le canal général contrôle l'activité (fini le ping sans contrôle) et traite le message `ack` client.

**Fichiers :**
- `backend/app/websocket/general.py` — **Modifier** : la boucle de réception (l.178+) passe par le helper d'expiration (toute activité reset le délai, pas seulement `pong`) ; le ping périodique existant (l.158-175) est réutilisé/factorisé dans `heartbeat.py` ; **dispatch du message `ack`** : `{"type":"ack","data":{"id":…}}` → acquittement auprès du registre (Tâche 6) ; messages inconnus → comportement actuel préservé (non-régression plugins/`default_message_handlers`).

**Dépend de :** Tâches 2, 6

### Tâche 4 : Application aux 4 canaux dédiés

**Objectif :** expiration de l'inactivité + ping serveur périodique sur les canaux dédiés (recommandation décision 4 / point d'attention 7).

**Fichiers :**
- `backend/app/websocket/deployment_logs.py` — **Modifier** : boucle de réception via helper d'expiration + ping serveur périodique (répond déjà `pong` au ping client — inchangé) ;
- `backend/app/websocket/container_logs.py` — **Modifier** : idem (attention : streaming `--follow` — l'**émission** de logs n'est pas de l'« activité client » ; le délai d'expiration se reset sur les messages **reçus** du client uniquement, décision 4) ;
- `backend/app/websocket/container_stats.py` — **Modifier** : idem ;
- `backend/app/websocket/terminal.py` — **Modifier** : idem avec prudence particulière (canal interactif bidirectionnel — l'expiration ne vise que l'inactivité **totale** ; ne pas perturber `ExecSession`, le rate limit 3 sessions et l'audit existants).

**Dépend de :** Tâche 2

### Tâche 5 : Enveloppe — `id` UUID sur les types critiques

**Objectif :** matérialiser le contrat ack dans l'enveloppe des messages (décision 5).

**Fichiers :**
- `backend/app/schemas/websocket_events.py` — **Modifier** : champ optionnel `id: UUID` sur l'enveloppe des messages — **renseigné uniquement pour les types critiques** (`ws_ack_critical_types`), absent sinon (streaming logs, heartbeats, toasts exclus) ;
- `backend/app/websocket/broadcasting.py` — **Modifier** : l'émission (modèle `_broadcast_deployment_event` l.41-64 : timestamp auto + manager + dispatch plugins) génère l'`id` UUID pour les types critiques et l'adresse au registre (Tâche 6) avant diffusion.

**Dépend de :** Tâches 1, 6

### Tâche 6 : Registre d'ack (TTL + re-diffusion + dégradation)

**Objectif :** fiabiliser la livraison des messages critiques (décision 5, point d'attention 5).

**Fichiers :**
- `backend/app/websocket/ack_registry.py` — **Créer** : registre **en mémoire** — enregistrement (`message_id`, `user_id`, `type`, `payload`, `emitted_at`), acquittement (`ack(message_id, user_id)`), **TTL ~`ws_ack_ttl_seconds`** (purge périodique ou purge paresseuse à l'accès) ; **re-diffusion à la reconnexion** du même utilisateur (messages expirés non acquittés → re-diffusés puis purgés) — registre **par user** (point d'attention 5 : la re-diffusion vise les reconnexions du même utilisateur, pas le même socket) ; **dégradation journalisée WARNING** (message critique non acquitté au-delà du TTL, sans reconnexion) — mesure Prometheus différée à STORY-172 ; jamais de payload sensible dans les logs.

**Dépend de :** Tâche 1

### Tâche 7 : Statuer sur les clés mortes `deployment_notifications`

**Objectif :** lever le tracé STORY-163 (point d'attention 6) sans réécrire le contrat du plugin.

**Fichiers :**
- `backend/app/websocket/plugins/deployment_notifications.py` — **Modifier** : arbitrage simple documenté — nettoyage léger des clés mortes `"deployment_events"`/`"deployment_progress_{id}"` (retrait des handlers fantômes) **ou** commentaire explicite de conservation (si incertitude sur un consommateur externe) ; note de décision dans la section Notes d'implémentation de cette story ; les tests [`test_plugins_default.py`](../../backend/tests/unit/test_websocket/test_plugins_default.py) restent verts (contrat du plugin intact).

**Dépend de :** Aucune (indépendante — peut être faite en parallèle)

### Tâche 8 : Tests et validation

**Objectif :** valider les AC 1-3 (voir « Tests à écrire ») + couverture ≥ 80 % sur `heartbeat.py`, `ack_registry.py` et les modules touchés.

**Fichiers :**
- `backend/tests/unit/test_websocket/test_ws_heartbeat_expiry.py` — **Créer** ;
- `backend/tests/unit/test_websocket/test_ws_ack.py` — **Créer** ;
- `backend/tests/unit/test_websocket/test_plugins_default.py` — **Modifier** (si clés mortes retirées) ;
- Tests existants des 5 canaux — **Non-régression** (suite WS + [`test_ws_auth.py`](../../backend/tests/unit/test_websocket/test_ws_auth.py) / [`test_ws_rbac.py`](../../backend/tests/unit/test_websocket/test_ws_rbac.py)).

**Dépend de :** Tâches 1-7

## Tests à écrire

> Principes directeurs de l'analyse mère (AC 3 + AC 5) — mock client muet, ack TTL, couverture ≥ 80 % ; patterns [`test_ws_auth.py`](../../backend/tests/unit/test_websocket/test_ws_auth.py). La suite exhaustive du module relève de STORY-165.

### Backend

- `backend/tests/unit/test_websocket/test_ws_heartbeat_expiry.py` —
  - client muet (aucun `pong`/message) → connexion **fermée côté serveur** après ~2 intervalles (timeout réduit via settings en test, jamais de `sleep` 60 s) ;
  - client actif (messages réguliers) → connexion **jamais fermée** (reset du délai à chaque message) ;
  - ping serveur périodique émis sur un canal dédié (mock horloge) ;
  - terminal : session interactive émettrice régulière non fermée ; inactivité totale → fermeture ;
  - log d'expiration émis (structured, sans données sensibles).
- `backend/tests/unit/test_websocket/test_ws_ack.py` —
  - message critique (type configuré) → enveloppe avec `id` UUID ; message non critique (log streaming, heartbeat, toast) → **sans** `id` ;
  - `{"type":"ack","data":{"id":…}}` reçu → message retiré du registre ;
  - non-acquitté au-delà du TTL + reconnexion du **même utilisateur** → **re-diffusé** puis purgé ;
  - non-acquitté sans reconnexion → **WARNING loggé** (dégradation) ;
  - TTL respecté (purge des entrées expirées) ;
  - registre : isolation entre utilisateurs (user B ne reçoit pas le critique non acquitté de user A).
- Non-régression — les 5 canaux existants fonctionnent (tests existants verts) ; `disable_auth` préservé en dev ; plugins par défaut + `default_message_handlers` intacts.

### Commandes de validation

```bash
poetry run pytest backend/tests/unit/test_websocket/test_ws_heartbeat_expiry.py backend/tests/unit/test_websocket/test_ws_ack.py -v
poetry run pytest backend/tests/unit/test_websocket/ -v --tb=short
make backend-test-unit
make backend-lint && make backend-typecheck
```

## Notes d'implémentation

*Ajoutées à la clôture de l'implémentation (2026-10-23, treat-story).*

### Fichiers créés

- `backend/app/websocket/heartbeat.py` — helper d'expiration transverse : `receive_with_expiry()` (wait_for borné `factor × interval`, reset à chaque message reçu, fermeture serveur **1001** + `HeartbeatExpiredError`, log structuré `idle_expiry` sans donnée sensible), `periodic_ping()` (ping serveur à `ws_heartbeat_interval_seconds`, `CancelledError` absorbé — pattern de l'ancien heartbeat inline de `general.py`), `ws_inactivity_timeout()` (bornes re-vérifiées, clamp ≥ 1 s).
- `backend/app/websocket/ack_registry.py` — registre **en mémoire par user** (`AckEntry`, `asyncio.Lock`) : `register()`, `ack()` (isolation user, ack croisé rejeté WARNING), `purge_expired()` (purge paresseuse `register`/`ack`, dégradation WARNING `ack_timeout`, horloge injectable), `redeliver_pending()` (re-diffusion à la reconnexion du même user, purge des entrées retournées, isolation inter-users), `is_critical_type()` (liste configurable, extraction `.value` pour les enums). Instance module-level `ack_registry` (cohérent `manager`/`user_manager`).
- `backend/tests/unit/test_websocket/test_ws_heartbeat_expiry.py` — 12 tests.
- `backend/tests/unit/test_websocket/test_ws_ack.py` — 22 tests.

### Fichiers modifiés

- `backend/app/config.py` — 4 settings (`ws_heartbeat_interval_seconds=30` gt 0, `ws_heartbeat_timeout_factor=2` ge 1, `ws_ack_ttl_seconds=30` gt 0, `ws_ack_critical_types=["DEPLOYMENT_STATUS_CHANGED","NOTIFICATION_USER"]`), alias env `WS_*`, doc pattern config existant.
- `backend/app/websocket/general.py` — ping inline remplacé par `periodic_ping` ; boucle via `receive_with_expiry` (toute activité reset) ; **dispatch `ack`** avant les plugins (`continue`, pas d'écho `message_received`) ; **re-diffusion** des critiques non acquittés après `add_user_connection` (`{"type","data","id","redelivered":true}`) ; `except HeartbeatExpiredError` propre.
- `backend/app/websocket/deployment_logs.py` — expiration + ping serveur périodique (heartbeat_task annulé en `finally`).
- `backend/app/websocket/container_logs.py` — idem ; le reset ne compte que les messages **reçus** (l'émission de logs n'est pas de l'activité client) ; `heartbeat_task: Optional` + garde au `finally` (retour prématuré container non-running).
- `backend/app/websocket/container_stats.py` — idem container_logs (garde `Optional` idem).
- `backend/app/websocket/terminal.py` — expiration sur inactivité **totale** uniquement (input/resize/ping reset) ; **pas de ping serveur périodique** (canal interactif bidirectionnel, émission continue via `stream_output`) ; ExecSession/rate-limit/audit intacts (finally existant).
- `backend/app/schemas/websocket_events.py` — `WebSocketMessageEnvelope` (contrat documenté : `type`/`data`/`timestamp`/`id` optionnel UUID réservé aux types critiques).
- `backend/app/websocket/broadcasting.py` — `_attach_ack_id_if_critical()` : id UUID généré uniquement pour les types critiques avec user identifié, adressé au registre ; branché sur `_broadcast_deployment_event` (destinataire `event_data["user_id"]`) et `broadcast_to_user` ; id déjà porté (re-diffusion) → jamais régénéré/réenregistré.
- `backend/app/websocket/plugins/deployment_notifications.py` — **arbitrage tâche 7 : nettoyage léger** (voir Décisions).

### Décisions techniques

1. **Close code 1001** (Going Away) pour l'expiration des connexions muettes — le serveur met fin à une connexion jugée morte ; `HeartbeatExpiredError` (hérite `WindFlowException`) laisse chaque canal sortir proprement via son `finally` existant.
2. **Purge paresseuse, jamais dans `redeliver_pending`** — la re-diffusion post-TTL reste possible tant que l'utilisateur ne s'est pas reconnecté (le TTL mesure la dégradation, pas une durée de rétention dure) ; la dégradation WARNING n'est émise qu'à la purge effective.
3. **`_attach_ack_id_if_critical` sans user identifié** → id ajouté à l'enveloppe mais pas d'entrée registre (pas de destinataire pour une re-diffusion).
4. **Tâche 7 — clés mortes `deployment_notifications`** : retrait des diffusions `"deployment_events"` et `f"deployment_progress_{id}"` (aucun abonné : frontend vérifié — abonnements réels `DEPLOYMENT_STATUS_CHANGED`, `deployment_logs`, `system_event` dans `frontend/src/services/websocket.ts` / `useDeploymentWebSocket.ts`) ; contrat du plugin (`broadcast_to_user` + `listens_for`) inchangé, tests `test_plugins_default.py` verts sans modification.
5. **Terminal sans ping serveur** : la recommandation « ping périodique sur canaux dédiés » (décision 4 / point 7) est appliquée aux canaux de streaming (deployment_logs, container_logs/stats) mais écartée pour le terminal interactif (émission `output` déjà continue ; le ping n'apporterait rien et l'expiration ne vise que le silence client).

### Divergences par rapport à l'analyse

- Aucune divergence structurelle. Précision d'implémentation : l'enregistrement au registre depuis `_broadcast_deployment_event` utilise `event_data.get("user_id")` (destinataire identifiable = initiateur du déploiement dans le payload existant) — l'analyse n'avait pas spécifié ce point.

### Difficultés rencontrées

- `str(WebSocketEventType.X)` rend `"WebSocketEventType.X"` et non la valeur → `is_critical_type` extrait `.value` (corrigé dès la première exécution des tests).
- Deux `return` prématurés dans `container_logs.py`/`container_stats.py` (container non-running) précédaient la création du `heartbeat_task` → initialisation `Optional[asyncio.Task] = None` + garde au `finally` (évite un `NameError`).
- mypy global (`make backend-typecheck`) remonte 5 erreurs **préexistantes** dans des fichiers non touchés (`background_tasks.py`, `target_scanner_service.py`, `jwt.py` — imports stubs/arg-type) : hors périmètre de cette story, aucun fichier de la story en erreur.

### Validation

- `poetry run pytest backend/tests/unit/test_websocket/test_ws_heartbeat_expiry.py backend/tests/unit/test_websocket/test_ws_ack.py` → **34 passed**.
- `poetry run pytest backend/tests/unit/test_websocket/` → **123 passed** (42 ws_auth, ws_rbac, plugins_default, event_bridge + 34 nouveaux, non-régression complète).
- Suites connexes `test_rbac_exhaustivite.py` / `test_deployment_events.py` / `test_deploy_stack_progress.py` → **21 passed**.
- Couverture modules nouveaux/touchés clés : `heartbeat.py` **100 %**, `ack_registry.py` **100 %**, `schemas/websocket_events.py` **100 %** (cible ≥ 80 % dépassée).
- black/isort/flake8/bandit sur les 13 fichiers touchés : **OK** ; mypy : aucune erreur dans les fichiers de la story.
