# Temps réel WebSocket — WindFlow

> **Statut** : Spécification technique · Partiellement implémenté — refondu vague 3 · 2026-08-23
> **Périmètre** : Spécification du temps réel : architecture backend, canaux, articulation des deux couches d'événements, authentification, protocole client (heartbeats, reconnexion, acknowledgment), usage frontend.
> **Référence de fond** : [general_specs — ch. 09 API (canaux canoniques)](../general_specs/09-api.md) · [ch. 11 Plugins (liste canonique des événements)](../general_specs/11-plugins.md) · [ch. 04 Architecture (temps réel)](../general_specs/04-architecture.md) · [ch. 02 Familles & workloads](../general_specs/02-familles-workloads.md)
> **Dernière mise à jour** : 2026-08-23 — refonte pilotée par [PLAN-REFONTE-TECHNICAL-SPECS.md](../../PLAN-REFONTE-TECHNICAL-SPECS.md) (constats traités : X6, X7, X8, R4-R7, G16-G20, G38, A7)

> **Terminologie** : ce document emploie le vocabulaire canonique du glossaire
> ([19-glossaire.md](../general_specs/19-glossaire.md)) : Host (ex-*Target*), Machine (ex-*VM*), App, Cluster,
> profil. Les identifiants du code historique (`target_id`, `Deployment`, `target_type`…) sont cités entre
> backticks et mis en correspondance à la première occurrence.

> **Note état actuel vs cible** *(G10)* — *État actuel (implémenté)* : la ressource temps réel est le
> **déploiement** (`Deployment`, créé via `POST /api/v1/deployments` avec `target_id`). *Cible
> (general_specs ch. 09)* : l'**App** (`POST /api/v1/apps`, triple XOR `host_id`/`machine_id`/`cluster_id`) et
> les canaux dédiés `/ws/logs/{app_id}`. Ce document décrit l'implémenté et marque la cible ⚠️ le cas échéant.

---

## Sommaire

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture backend](#2-architecture-backend)
3. [Canaux](#3-canaux)
4. [Les deux couches d'événements](#4-les-deux-couches-dévénements)
5. [Flux de données d'un déploiement](#5-flux-de-données-dun-déploiement)
6. [Usage frontend](#6-usage-frontend)
7. [Authentification](#7-authentification)
8. [Protocole détaillé](#8-protocole-détaillé)
9. [Tests manuels](#9-tests-manuels)
10. [Écarts connus](#10-écarts-connus)
11. [Voir aussi](#11-voir-aussi)

---

## 1. Vue d'ensemble

Le WebSocket complète l'API REST pour tout ce qui ne peut pas passer par du polling : notifications push,
streaming de logs, terminaux interactifs (renvoi [ch. 04 §Communication](../general_specs/04-architecture.md)).
Concrètement, WindFlow utilise le temps réel pour quatre familles d'usages :

| Famille | Exemples | Couches concernées |
|---|---|---|
| **Notifications push** | changement de statut d'un déploiement, confirmation d'authentification | canal général `/ws` |
| **Streaming de logs** | logs de déploiement, logs/stats de container Docker | canaux dédiés |
| **Terminaux interactifs** | shell dans un container (entrée/sortie bidirectionnels) | canal dédié |
| **Événements système** | événements du bus interne relayés aux clients abonnés | canal général + abonnements |

Deux mécanismes coexistent et sont articulés à la [section 4](#4-les-deux-couches-dévénements) :

- une **couche d'événements interne** (bus [`core/events.py`](../../backend/app/core/events.py), format
  `domaine.action_passé`) — les services publient des faits ;
- une **couche de transport WebSocket** (messages `SCREAMING_SNAKE` définis dans
  [`schemas/websocket_events.py`](../../backend/app/schemas/websocket_events.py)) — ce que voient les clients.

⚠️ Les « plugins WebSocket » internes de [`backend/app/websocket/plugins/`](../../backend/app/websocket/plugins)
sont des **modules de broadcast internes** (G38) : ils n'ont aucun rapport avec les **Plugins marketplace**
(manifest, hooks, lifecycle — [ch. 11](../general_specs/11-plugins.md)).

---

## 2. Architecture backend

### 2.1 Chaîne d'émission

```
POST /api/v1/deployments
        ▼
deploy_stack_async() + DeploymentOrchestrator (retry)
        ▼
DeploymentService.update_status() ──▶ DeploymentEventsService
        │                                 ├─ emit_status_change() ─emit()─▶ EventBus (core/events)
        │                                 └─ emit_logs_update() ──broadcast direct──────────┐
        ▼                                                                           │
event_bridge (EVENT_TYPE_MAPPING) ◀── EventBus                                       │
        ▼                                                                           │
broadcasting.py + connection_managers.py (manager / user_manager) ◀─────────────────┘
        ▼
Clients WebSocket (frontend)
```

Deux chemins d'émission, à ne pas confondre :

- **Statut** : passe par le bus (`emit_status_change` → `EventBus` → `event_bridge` → broadcast aux abonnés) ;
- **Logs** : court-circuitent le bus (`emit_logs_update` → [`broadcast_deployment_log()`](../../backend/app/websocket/broadcasting.py) en direct),
  car il s'agit de données de streaming, pas de faits.

### 2.2 Modules de [`backend/app/websocket/`](../../backend/app/websocket)

| Module | Rôle | État |
|---|---|---|
| [`general.py`](../../backend/app/websocket/general.py) | Endpoint général : auth premier message, heartbeat serveur, boucle de messages, dispatch aux modules | Implémenté |
| [`deployment_logs.py`](../../backend/app/websocket/deployment_logs.py) | Canal dédié logs de déploiement (statut initial + streaming) | Implémenté |
| [`terminal.py`](../../backend/app/websocket/terminal.py) | Terminal interactif de container (exec Docker, rate limit 3 sessions/user, audit) | Implémenté |
| [`container_logs.py`](../../backend/app/websocket/container_logs.py) / [`container_stats.py`](../../backend/app/websocket/container_stats.py) | Streaming logs / stats (~1 s) d'un container Docker | Implémenté |
| [`broadcasting.py`](../../backend/app/websocket/broadcasting.py) | Fonctions de broadcast (déploiement, utilisateur, abonnements) | Implémenté |
| [`connection_managers.py`](../../backend/app/websocket/connection_managers.py) | `ConnectionManager` (par déploiement) et `UserConnectionManager` (par utilisateur, abonnements, dispatch plugins) | Implémenté |
| [`event_bridge.py`](../../backend/app/websocket/event_bridge.py) | Pont bus interne → WebSocket (voir §4.3) | Implémenté |
| [`plugin.py`](../../backend/app/websocket/plugin.py) | Socle des modules de broadcast internes (`WebSocketPlugin`, `WebSocketMessageHandler`, `PluginContext`) | Implémenté |
| [`plugins/`](../../backend/app/websocket/plugins) | Modules internes : `audit_logger`, `deployment_monitor`, `subscription` (+ `deployment_notifications` — voir [écarts](#10-écarts-connus)) | Partiel |
| [`metrics.py`](../../backend/app/websocket/metrics.py) | Métriques Prometheus du temps réel | ⚠️ défini mais non intégré (aucun import) |

Le pont est monté au démarrage de l'application : [`setup_event_bridge()`](../../backend/app/main.py) est
appelé dans le `lifespan` FastAPI ([`main.py`](../../backend/app/main.py)).

---

## 3. Canaux

### 3.1 Référence canonique (general_specs)

La **référence unique** des canaux WebSocket est le
[ch. 09 §WebSocket](../general_specs/09-api.md) — elle n'est pas redéfinie ici. Rappel de la cible :

| Canal canonique | Usage |
|---|---|
| `/ws/terminal/{container_id}` | Terminal container |
| `/ws/console/{machine_id}` | Console VNC/SPICE de Machine (noVNC) |
| `/ws/ssh/{host_id}` | Session SSH de Host |
| `/ws/logs/{app_id}` | Streaming de logs d'App |
| `/ws/journal/{host_id}` | Journal système de Host |
| `/ws/deploy/{deployment_id}` | Événements de déploiement |
| `/ws/batch/{batch_id}` | Progression des opérations groupées |
| `/ws/events` | Événements système globaux (nommage `domaine.action_passé`) |

### 3.2 État implémenté

*État actuel (implémenté)* : le routeur [`api/v1/websockets.py`](../../backend/app/api/v1/websockets.py) est
monté sous le préfixe **`/api/v1/ws`** ([`api/v1/__init__.py`](../../backend/app/api/v1/__init__.py)). Cinq
endpoints existent :

| Endpoint réel | Rôle | Équivalent canonique |
|---|---|---|
| `/api/v1/ws/` | Canal général : auth, abonnements (`subscribe`), notifications, heartbeat | `/ws/events` (partiel) |
| `/api/v1/ws/deployments/{deployment_id}/logs` | Statut initial + logs d'un déploiement | `/ws/deploy/{deployment_id}` (partiel) |
| `/api/v1/ws/terminal/{container_id}?shell=&user=` | Terminal interactif container | `/ws/terminal/{container_id}` |
| `/api/v1/ws/docker/containers/{container_id}/logs?tail=` | Streaming logs container | `/ws/logs/{app_id}` (partiel — périmètre container, voir C7) |
| `/api/v1/ws/docker/containers/{container_id}/stats` | Streaming stats container | — (hors liste canonique) |

| Canal canonique non monté | Statut |
|---|---|
| `/ws/console/{machine_id}`, `/ws/ssh/{host_id}`, `/ws/journal/{host_id}`, `/ws/batch/{batch_id}` | ⚠️ **Non implémenté** — cible general_specs |

Sur le canal général, les clients ne se connectent pas à un canal par sujet mais **s'abonnent à des types
d'événements** via le message `subscribe` (voir §8.1) — les abonnements sont gérés par
[`UserConnectionManager`](../../backend/app/websocket/connection_managers.py) (`user_subscriptions`,
`deployment_subscribers`).

⚠️ **Écart d'authentification** : la cible canonicalise le JWT en query parameter sur **tous** les canaux
(ch. 09) ; l'implémenté utilise le query param `?token=` sur les canaux dédiés, mais le **premier message**
d'authentification sur le canal général et le terminal (voir §7). Convergence à planifier.

---

## 4. Les deux couches d'événements

Il existe **deux nomenclatures d'événements** dans le code. Ne jamais les mélanger : les workflows et les
plugins marketplace s'abonnent à la couche canonique ; les clients WebSocket consomment la couche transport.

### 4.1 Couche 1 — bus interne (canonique, semi-conforme)

[`core/events.py`](../../backend/app/core/events.py) définit l'enum `EventType` au format
`domaine.action_passé` (celui de la [liste canonique des 18 événements](../general_specs/11-plugins.md)) :

```python
# Extrait réel — backend/app/core/events.py:22-47
class EventType(str, Enum):
    """Types d'événements système."""

    # Déploiement
    DEPLOYMENT_CREATED = "deployment.created"
    DEPLOYMENT_STARTED = "deployment.started"
    DEPLOYMENT_COMPLETED = "deployment.completed"
    DEPLOYMENT_FAILED = "deployment.failed"
    DEPLOYMENT_ROLLED_BACK = "deployment.rollback"

    # Target
    TARGET_CREATED = "target.created"
    TARGET_UPDATED = "target.updated"
    TARGET_DELETED = "target.deleted"
    TARGET_HEALTH_CHECK = "target.health_check"

    # Stack
    STACK_CREATED = "stack.created"
    STACK_UPDATED = "stack.updated"
    STACK_DELETED = "stack.deleted"

    # Organisation
    ORGANIZATION_CREATED = "organization.created"
    ORGANIZATION_UPDATED = "organization.updated"
```

S'y ajoutent les domaines `user.*`, `plugin.*` et `system.*` — voir le fichier source. Le bus
(`EventBus.publish/subscribe`) est en mémoire ; les branches Redis Streams/EventStore sont des coquilles
TODO ⚠️ non implémentées.

**⚠️ Semi-conformité (G18)** : le format est canonique mais **pas la liste** — écarts détaillés en
[§10.2](#10-écarts-connus).

### 4.2 Couche 2 — transport WebSocket (SCREAMING_SNAKE)

[`schemas/websocket_events.py`](../../backend/app/schemas/websocket_events.py) définit `WebSocketEventType`,
le contrat partagé backend/frontend (doublé côté front dans `frontend/src/services/websocket/types.ts`) :

| Groupe | Types | Émis aujourd'hui |
|---|---|---|
| Auth | `AUTH_LOGIN_SUCCESS`, `AUTH_LOGOUT`, `AUTH_TOKEN_REFRESH` | `AUTH_LOGIN_SUCCESS` (canal général, après auth) |
| Notifications | `NOTIFICATION_SYSTEM`, `NOTIFICATION_USER`, `NOTIFICATION_DEPLOYMENT` | ⚠️ aucun émetteur backend (contrat) |
| Session | `SESSION_EXPIRED`, `SESSION_AUTH_REQUIRED`, `SESSION_PERMISSION_CHANGED`, `SESSION_ORGANIZATION_CHANGED` | ⚠️ aucun émetteur backend (contrat) |
| UI (server-driven) | `UI_NAVIGATION_REQUEST`, `UI_MODAL_DISPLAY`, `UI_TOAST_DISPLAY`, `UI_WORKFLOW_STEP` | ⚠️ aucun émetteur backend (contrat) |
| Déploiement | `DEPLOYMENT_STATUS_CHANGED`, `DEPLOYMENT_LOGS_UPDATE`, `DEPLOYMENT_PROGRESS` | les deux premiers ; `DEPLOYMENT_PROGRESS` ⚠️ **jamais émis** |
| Système | `SYSTEM_MAINTENANCE`, `SYSTEM_BROADCAST` | ⚠️ aucun émetteur backend (contrat) |
| Types protocole (minuscules) | `pong`, `error`, `subscribed`, `unsubscribed`, `logs_subscribed`, `message_received`, `text_received` | selon le protocole (§8) |

> ⚠️ **Avertissement** : les noms SCREAMING_SNAKE sont un détail de transport, pas un contrat de workflow.
> Ne jamais brancher un workflow, un trigger scheduler ou un plugin marketplace sur ces noms — la
> souscription se fait sur les événements canoniques `domaine.action_passé` ([ch. 11](../general_specs/11-plugins.md),
> [ch. 17](../general_specs/17-automatisation-workflows.md)).

### 4.3 Le pont : qui émet quoi, qui consomme quoi

**Traduction statut → événement canonique** ([`deployment_events.py`](../../backend/app/services/deployment_events.py)) :

```python
# Extrait réel — backend/app/services/deployment_events.py:79-91
        # Map DeploymentStatus to EventType
        status_str = (
            new_status.value if isinstance(new_status, DeploymentStatus) else new_status
        )
        event_type_map = {
            "pending": EventType.DEPLOYMENT_CREATED,
            "deploying": EventType.DEPLOYMENT_STARTED,
            "running": EventType.DEPLOYMENT_STARTED,  # Un déploiement "running" est démarré, pas terminé
            "success": EventType.DEPLOYMENT_COMPLETED,
            "failed": EventType.DEPLOYMENT_FAILED,
            "rollback": EventType.DEPLOYMENT_ROLLED_BACK,
        }

        event_type = event_type_map.get(status_str, EventType.DEPLOYMENT_COMPLETED)
```

**Traduction événement canonique → type transport** ([`event_bridge.py`](../../backend/app/websocket/event_bridge.py)) :

```python
# Extrait réel — backend/app/websocket/event_bridge.py:20-26
# Mapping from EventType to WebSocketEventType
# This allows us to convert internal event types to WebSocket event types
EVENT_TYPE_MAPPING: Dict[EventType, WebSocketEventType] = {
    EventType.DEPLOYMENT_CREATED: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
    EventType.DEPLOYMENT_STARTED: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
    EventType.DEPLOYMENT_COMPLETED: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
    EventType.DEPLOYMENT_FAILED: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
    EventType.DEPLOYMENT_ROLLED_BACK: WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
}
```

**Tableau d'articulation des deux couches** :

| Événement canonique (bus) | Type transport (WS) | Émis par | Consommé par |
|---|---|---|---|
| `deployment.created` / `started` / `completed` / `failed` / `rollback` | `DEPLOYMENT_STATUS_CHANGED` | [`emit_status_change()`](../../backend/app/services/deployment_events.py) (appelée par [`DeploymentService.update_status()`](../../backend/app/services/deployment_service.py)) → bus → `event_bridge` | clients abonnés `subscribe` (`broadcast_to_event_subscribers`) ; frontend [`useDeploymentWebSocket`](../../frontend/src/composables/useDeploymentWebSocket.ts) / `useDeploymentStatusMonitor` ; module `deployment_monitor` (logs/audit) |
| — (pas d'événement bus : streaming direct) | `DEPLOYMENT_LOGS_UPDATE` | [`emit_logs_update()`](../../backend/app/services/deployment_events.py) → [`broadcast_deployment_log()`](../../backend/app/websocket/broadcasting.py) | connexions du canal dédié (`manager.broadcast_to_deployment`) + abonnés `deployment_subscribers` + module `deployment_monitor` |
| — | `DEPLOYMENT_PROGRESS` | ⚠️ **aucun émetteur** (voir §10.1) | [`deployment_notifications`](../../backend/app/websocket/plugins/deployment_notifications.py) et `deployment_monitor` déclarent l'écouter — mais jamais déclenchés ; le handler frontend existe et ne se déclenche jamais |
| — (protocole) | `AUTH_LOGIN_SUCCESS`, `pong`, `subscribed`… | [`general.py`](../../backend/app/websocket/general.py), [`subscription.py`](../../backend/app/websocket/plugins/subscription.py) | service WebSocket frontend + ses plugins (`session`, `navigation`, `notification`…) |
| `target.*`, `stack.*`, `user.*`, `organization.*`, `plugin.*`, `system.*` | — (aucun mapping) | services backend via le bus | ⚠️ aucun consommateur WebSocket : le pont ne mappe que `deployment.*` |

Fragilité connue du pont : `EventBus.emit()` appelé avec un `WebSocketEventType` (au lieu d'un `EventType`)
réencapsule le message en `system.error` avec le type d'origine en métadonnée `_original_event_type`
([`core/events.py:200-222`](../../backend/app/core/events.py)) — ne pas dépendre de ce comportement.

---

## 5. Flux de données d'un déploiement

*État actuel (implémenté)* — le chemin d'exécution réel (corrigé par X7 : il n'existe pas de tâche Celery
de déploiement ; [`celery_app.py`](../../backend/app/celery_app.py) ne définit que `cleanup_logs`,
`health_check_targets`, `retry_pending_deployments`) :

1. Le client crée un déploiement : `POST /api/v1/deployments` (`stack_id`, `target_id`, variables).
2. `DeploymentService` crée l'enregistrement (`PENDING`) puis confie l'exécution au
   [`DeploymentOrchestrator`](../../backend/app/services/deployment_orchestrator.py), qui appelle
   [`deploy_stack_async()`](../../backend/app/tasks/background_tasks.py) — **tâche asyncio dans le processus
   backend** (mode fallback « sans Celery »), avec retry automatique (`MAX_RETRIES`).
3. À chaque étape, le worker appelle [`DeploymentService.update_status()`](../../backend/app/services/deployment_service.py)
   (statut, logs cumulés, `user_id`).
4. `update_status()` persiste puis émet :
   - [`emit_status_change()`](../../backend/app/services/deployment_events.py) → bus `EventBus` ;
   - [`emit_logs_update()`](../../backend/app/services/deployment_events.py) → broadcast direct.
5. Le pont [`event_bridge.py`](../../backend/app/websocket/event_bridge.py) reçoit l'événement bus, le
   traduit en `DEPLOYMENT_STATUS_CHANGED` et le diffuse aux abonnés.
6. Les clients connectés reçoivent l'enveloppe `{type, data}` ; le frontend met à jour l'UI
   (statut, logs en streaming).

*Cible (general_specs ch. 09)* : `POST /apps` + `POST /compute/stacks/{id}/deploy`, événements
`deployment.started/succeeded/failed` sur `/ws/deploy/{deployment_id}` — ⚠️ non implémenté.

---

## 6. Usage frontend

Le service singleton [`frontend/src/services/websocket.ts`](../../frontend/src/services/websocket.ts)
gère la connexion au canal général (`/api/v1/ws/`), l'authentification, la reconnexion et le dispatch vers
des plugins frontend ([`services/websocket/plugins/`](../../frontend/src/services/websocket/plugins)) et des
callbacks. Les composables applicatifs s'appuient dessus ou ouvrent des connexions dédiées :

| Composable | Connexion | Rôle |
|---|---|---|
| [`useDeploymentWebSocket.ts`](../../frontend/src/composables/useDeploymentWebSocket.ts) | générale | Statut/logs/progression d'un déploiement (abonnements `wsService.on(...)`) ; charge l'état initial via l'API REST avant connexion |
| [`useDeploymentLogs.ts`](../../frontend/src/composables/useDeploymentLogs.ts) | générale | Logs via `deploymentEvents.subscribeToLogs` |
| [`useContainerLogs.ts`](../../frontend/src/composables/useContainerLogs.ts) | dédiée `/ws/docker/containers/{id}/logs?token=` | Streaming logs, reconnexion 5 × 2 s |
| [`useContainerStats.ts`](../../frontend/src/composables/useContainerStats.ts) | dédiée `/ws/docker/containers/{id}/stats?token=` | Stats temps réel |
| [`useTerminal.ts`](../../frontend/src/composables/useTerminal.ts) | dédiée `/ws/terminal/{container_id}` | Terminal interactif (xterm.js) |

Exemple d'abonnement (extrait réel, [`useDeploymentWebSocket.ts:229-250`](../../frontend/src/composables/useDeploymentWebSocket.ts)) :

```typescript
    // S'abonner aux événements de statut
    unsubscribeStatus = wsService.on(
      WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
      handleStatusChange
    )

    // S'abonner aux événements de logs
    unsubscribeLogs = wsService.on(
      WebSocketEventType.DEPLOYMENT_LOGS_UPDATE,
      handleLogsUpdate
    )

    // S'abonner aux événements de progression
    unsubscribeProgress = wsService.on(
      WebSocketEventType.DEPLOYMENT_PROGRESS,
      handleProgress
    )

    // Envoyer une demande d'abonnement au serveur pour ce déploiement
    wsService.send('subscribe', {
      event_type: 'deployment_logs',
      deployment_id: getDeploymentId()
    })
```

⚠️ Le handler `handleProgress` existe côté frontend mais n'est jamais alimenté : `DEPLOYMENT_PROGRESS`
n'est émis par personne (§10.1).

---

## 7. Authentification

L'authentification WebSocket est **implémentée** (X8/R4/R5 résolus) — les « TODO/Phase 5 » des versions
antérieures de ce document sont obsolètes. Deux mécanismes selon le canal :

### 7.1 Canal général et terminal : JWT au premier message

La connexion est acceptée, puis le client **doit** envoyer `{"type": "auth", "token": "<JWT>"}` dans les
**30 secondes** ; token décodé (`decode_access_token`), utilisateur vérifié (actif). Tout échec ferme avec **1008**.

```python
# Extrait réel — backend/app/websocket/general.py:89-98
        try:
            data = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=30.0,  # 30 secondes timeout pour le debug
            )
            logger.info(f"Received data from client: {data}")
        except asyncio.TimeoutError:
            logger.warning("WebSocket authentication timeout - no message received")
            await websocket.close(code=1008, reason="Authentication timeout")
            return
```

Succès → le serveur envoie `AUTH_LOGIN_SUCCESS` avec `{user_id, username, organization_id}`, enregistre la
connexion utilisateur et initialise les modules de broadcast internes.

### 7.2 Canaux dédiés : JWT en query parameter

`/ws/deployments/{id}/logs`, `/ws/docker/containers/{id}/logs|stats` authentifient via `?token=<JWT>` —
c'est le mécanisme que la cible general_specs généralise à **tous** les canaux. Le canal déploiement vérifie
en plus l'accès organisationnel à la ressource (superadmin excepté)
([`deployment_logs.py:23-48`](../../backend/app/websocket/deployment_logs.py)).

Le terminal applique un **rate limit** de 3 sessions simultanées par utilisateur et journalise chaque
session (audit) — [`terminal.py`](../../backend/app/websocket/terminal.py).

---

## 8. Protocole détaillé

Cette section remplit la promesse du [ch. 09 §WebSocket](../general_specs/09-api.md) (« le protocole
détaillé — reconnexion, heartbeats, acknowledgment — est spécifié dans WEBSOCKET-REAL-TIME.md »). Chaque
sous-section distingue **l'observé** (comportement du code actuel) de **la cible** (⚠️ non implémenté).

### 8.1 Enveloppe des messages

Tous les messages serveur → client utilisent l'enveloppe `{type, data}` (conforme ch. 09 — G20), la plupart
avec un `timestamp` ISO 8601 :

```json
{"type": "DEPLOYMENT_STATUS_CHANGED", "data": {"deployment_id": "…", "new_status": "running"}, "timestamp": "2026-08-23T00:00:00"}
```

Messages client → serveur gérés à ce jour (canal général) :

| Message | Effet |
|---|---|
| `{"type": "auth", "token": "…"}` | Authentification (premier message obligatoire) |
| `ping` (texte brut) | Heartbeat → réponse `{"type": "pong", "timestamp": …}` |
| `{"type": "subscribe", "data": {"event_type": "DEPLOYMENT_STATUS_CHANGED"}}` | Abonnement → `{"type": "subscribed", …}` |
| `{"type": "unsubscribe", "data": {"event_type": …}}` | Désabonnement → `{"type": "unsubscribed", …}` |
| `{"type": "deployment_logs", "data": {"deployment_id": …}}` | Abonnement aux logs d'un déploiement → `logs_subscribed` |

Tout autre message JSON reçoit un écho `message_received` (texte brut : `text_received`) — comportement de
développement, à ne pas utiliser comme API.

### 8.2 Heartbeats / ping-pong

*Observé* : le serveur envoie un heartbeat `{"type": "ping", "timestamp": …}` **toutes les 30 s** sur le
canal général ; le client peut envoyer `ping` (texte) à tout moment et reçoit `pong`. Les canaux dédiés
répondent aussi à `ping`.

```python
# Extrait réel — backend/app/websocket/general.py:189-198
            async def send_heartbeat():
                """Envoie un heartbeat périodique au client."""
                try:
                    while True:
                        await asyncio.sleep(30)  # Toutes les 30 secondes
                        await websocket.send_json(
                            {"type": "ping", "timestamp": datetime.utcnow().isoformat()}
                        )
                except asyncio.CancelledError:
                    pass  # Tâche annulée, normal lors de la déconnexion
```

⚠️ **Cible non implémentée** : le serveur n'expire pas une connexion silencieuse (aucun contrôle des
`pong`, la boucle `receive_text()` attend indéfiniment). Cible : fermeture côté serveur si aucun
`pong` n'est reçu sous ~2 intervalles.

### 8.3 Reconnexion

*Observé* (canal général, [`services/websocket.ts`](../../frontend/src/services/websocket.ts)) :
backoff exponentiel **1 s / 2 s / 4 s**, **3 tentatives** max, puis déconnexion de l'utilisateur
(logout). Les fermetures dues à une erreur d'authentification (codes 1008/1003, ou raisons « Invalid
token », « Authentication timeout », etc.) ne sont **jamais** retentées → logout immédiat.

```typescript
// Extrait réel — frontend/src/services/websocket.ts:19-22
  private reconnectAttempts = 0
  private maxReconnectAttempts = 3 // Aligned with HTTP retry logic
  private reconnectDelays = [1000, 2000, 4000] // Exponential backoff: 1s, 2s, 4s
  private isReconnecting = false // Prevent simultaneous reconnection attempts
```

*Observé* (canaux dédiés, `useContainerLogs` / `useContainerStats`) : reconnexion simple — 5 tentatives,
délai fixe de 2 s, sans retry si fermeture 1000/1008.

⚠️ **Cible non implémentée** : politique unifiée (un seul algorithme tous canaux), gigue (jitter) sur le
backoff pour éviter les tempêtes de reconnexion, reconnexion transparente après veille réseau, et
**resynchronisation d'état** après reconnexion (refaire un `GET` de la ressource suivie pour combler les
événements manqués). À spécifier au moment de l'implémentation.

### 8.4 Acknowledgment

⚠️ **Non implémenté — cible** (promesse general_specs). Spécification cible, pour les messages critiques
(tout message dont la perte est inacceptable) :

1. Le serveur ajoute un champ `id` (UUID) à l'enveloppe des messages critiques ;
2. Le client accuse réception en renvoyant `{"type": "ack", "data": {"id": "<uuid>"}}` ;
3. Le serveur retient les messages non acquittés **par connexion** (TTL ~30 s) et re-diffuse à la
   reconnexion — pas de persistence longue (le passé se réconcilie par l'API REST, pas par rejou WS) ;
4. Un `ack` absent au-delà du TTL ⇒ dégradation en logs serveur (métriques [`metrics.py`](../../backend/app/websocket/metrics.py)).

L'acknowledgment ne s'applique ni au streaming de logs, ni aux heartbeats, ni aux messages d'UI
éphémères (toasts) — par conception, ces flux sont perdables.

---

## 9. Tests manuels

### 9.1 Canal général avec wscat

```bash
wscat -c ws://localhost:8000/api/v1/ws/
> {"type": "auth", "token": "<JWT>"}          # 1. s'authentifier (< 30 s)
< {"type": "AUTH_LOGIN_SUCCESS", "data": {...}}
> {"type": "subscribe", "data": {"event_type": "DEPLOYMENT_STATUS_CHANGED"}}   # 2. s'abonner
< {"type": "subscribed", ...}
# 3. déclencher un déploiement (autre terminal) :
curl -X POST http://localhost:8000/api/v1/deployments -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"stack_id": "<uuid>", "target_id": "<uuid>", "variables": {"PORT": "8080"}}'
# 4. observer :
< {"type": "DEPLOYMENT_STATUS_CHANGED", "data": {"new_status": "deploying", ...}, "timestamp": ...}
< {"type": "DEPLOYMENT_STATUS_CHANGED", "data": {"new_status": "success", ...}, "timestamp": ...}
```

### 9.2 Canal dédié logs de déploiement

```bash
wscat -c "ws://localhost:8000/api/v1/ws/deployments/<deployment_id>/logs?token=<JWT>"
< {"type": "status", "data": {"status": "...", "deployment_id": "...", "name": "..."}}
< {"type": "DEPLOYMENT_LOGS_UPDATE", "data": {"logs": ["..."], "level": "info", ...}}
```

### 9.3 Sans client WebSocket

Les événements sont émis même sans client connecté (broadcast no-op) ; on les observe dans les logs
backend (`docker-compose logs -f backend`) : `📡 [STEP 1/4] Emitting status change event …`,
`🌉 [STEP 2/4] Event Bridge received …`.

---

## 10. Écarts connus

Écarts explicites code ↔ cible general_specs ; la correction relève du backlog (code), pas de ce document.

### 10.1 `DEPLOYMENT_PROGRESS` défini mais jamais émis (X6, A7)

Le type existe dans le contrat ([`websocket_events.py`](../../backend/app/schemas/websocket_events.py)), les
modules internes `deployment_monitor` et [`deployment_notifications`](../../backend/app/websocket/plugins/deployment_notifications.py)
déclarent l'écouter, et [`broadcast_deployment_progress()`](../../backend/app/websocket/broadcasting.py) existe —
mais **aucun code n'émet jamais cet événement** (aucune méthode `emit_progress_update` ;
`broadcast_deployment_progress` n'a aucun appelant). Le handler frontend de `useDeploymentWebSocket` n'est
donc jamais déclenché.

À noter : `deployment_notifications` **n'est pas importé** par [`plugins/__init__.py`](../../backend/app/websocket/plugins/__init__.py)
(seuls `audit_logger`, `deployment_monitor` et `subscription` sont enregistrés) — son auto-enregistrement à
l'import n'a jamais lieu. **Recommandation** : retirer `DEPLOYMENT_PROGRESS` du contrat ou inscrire l'émission
de progression au backlog.

### 10.2 Bus interne semi-canonique (G18)

[`core/events.py`](../../backend/app/core/events.py) suit le format `domaine.action_passé` mais **pas** la
[liste canonique des 18 événements](../general_specs/11-plugins.md) :

| Code actuel | Canonique | Nature de l'écart |
|---|---|---|
| `deployment.completed` | `deployment.succeeded` | nom divergent (jamais `success`/`completed` en canonique) |
| `deployment.rollback` | — | absent de la liste canonique |
| `target.*` (4 événements) | `host.added` / `host.removed` / `host.offline` | domaine historique (alias interdit) + granularité différente |
| — | `container.*` (4), `machine.*` (3), `host.*`, `stack.deployed`… | domaines entiers manquants |
| `plugin.uninstalled`… | `plugin.removed` | granularité différente |
| `organization.*`, `user.*`, `system.*` | — | domaines extra-canoniques |

Alignement du code à inscrire au backlog ; d'ici là, **tout nouvel abonnement doit viser les noms
canoniques**, pas l'état actuel de l'enum.

### 10.3 Autres écarts

- **Canaux** (G16) : voir la table §3.2 — 4 canaux canoniques non montés, nommage `/api/v1/ws/...` ≠
  `/ws/...`, abonnement par topics sur le canal général vs canaux par ressource.
- **Acknowledgment** : non implémenté (§8.4, cible spécifiée).
- **Heartbeat serveur sans expiration** : aucun contrôle des `pong` (§8.2, cible spécifiée).
- **[`metrics.py`](../../backend/app/websocket/metrics.py)** : métriques Prometheus définies mais aucun
  module ne les importe — non intégré.
- **Redis Streams / EventStore** dans [`core/events.py`](../../backend/app/core/events.py) : coquilles TODO,
  bus en mémoire uniquement.

---

## 11. Voir aussi

- [general_specs — ch. 09 API](../general_specs/09-api.md) — référence unique des canaux WebSocket et de l'enveloppe `{type, data}`
- [general_specs — ch. 11 Plugins](../general_specs/11-plugins.md) — liste canonique des 18 événements `domaine.action_passé`
- [general_specs — ch. 04 Architecture](../general_specs/04-architecture.md) — usages du temps réel, bus d'événements
- [general_specs — ch. 02 Familles & workloads](../general_specs/02-familles-workloads.md) — familles Apps/Machines/Hosts et profils derrière les canaux
- [general_specs — ch. 17 Automatisation & workflows](../general_specs/17-automatisation-workflows.md) — triggers sur événements canoniques (≠ types transport)
- [general_specs — ch. 19 Glossaire](../general_specs/19-glossaire.md) — terminologie canonique et alias interdits
- [STACK-DEFINITIONS.md](STACK-DEFINITIONS.md), [DYNAMIC-FORMS.md](DYNAMIC-FORMS.md) — note d'articulation état/cible sur `POST /deployments` vs `POST /apps`
- [README.md](README.md) — index du corpus technique et matrice d'état
