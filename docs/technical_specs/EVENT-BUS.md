# Bus d'événements canonique — nomenclature & architecture (STORY-162)

> Référence technique du bus d'événements WindFlow (P2-2, arbitrage F6).
> Source de vérité code : [`backend/app/core/events.py`](../../backend/app/core/events.py).
> Source de vérité nomenclature : spec 11 (`docs/general_specs/11-plugins.md`) § Liste canonique.

## 1. Vue d'ensemble

Le bus expose une **interface unique** `Bus` (Protocol typing) avec deux
implémentations interchangeables :

| Mode | Implémentation | Activation | Portée |
|------|----------------|------------|--------|
| **Léger** (défaut) | `InMemoryEventBus` | aucune configuration | process-local (RPi, dev, tests) |
| **Standard** | `RedisPubSubEventBus` | `CACHE_URL` configuré **et** Redis joignable | multi-instances |

```python
from app.core.events import EventType, get_event_bus, init_event_bus

# Startup (lifespan) — choisit l'implémentation selon CACHE_URL
bus = await init_event_bus()

# Partout ailleurs : bus actif (sans l'initialiser)
bus = get_event_bus()
await bus.emit(EventType.DEPLOYMENT_SUCCEEDED, {"deployment_id": "..."})
```

**Hors périmètre assumé (arbitrage F6)** : Redis **Streams**, replay,
event-sourcing — l'ancienne classe `EventStore` et `replay_events()`
(stubs morts) ont été supprimés. Le besoin event-sourcing, s'il émerge,
fera l'objet d'une décision d'architecture séparée.

## 2. Nomenclature canonique (18 événements — spec 11)

`EventType` est l'**unique référentiel** : bloc canonique + bloc
extra-canonique documenté (pas de second enum qui divergerait).

| Domaine | Événements canoniques | Émetteur |
|---------|----------------------|----------|
| `container.*` | `created` · `started` · `stopped` · `removed` | [`api/v1/docker.py`](../../backend/app/api/v1/docker.py) (create/start/stop/remove) |
| `stack.*` | `deployed` · `updated` · `removed` | `deployment_service.update_status` (`stack.deployed` au succès d'un déploiement de stack) |
| `machine.*` | `created` · `started` · `stopped` | **aucun** — Roadmap VMs (définition de contrat, pas un silence métier) |
| `deployment.*` | `started` · `succeeded` · `failed` | [`deployment_events.py`](../../backend/app/services/deployment_events.py) (`succeeded` au statut `success` — jamais `completed`) |
| `host.*` | `added` · `removed` · `offline` | [`targets/crud.py`](../../backend/app/api/v1/targets/crud.py) (create/delete) + [`target_service.check_health`](../../backend/app/services/target_service.py) (transition joignable→injoignable) |
| `plugin.*` | `installed` · `removed` | [`plugin_manager_service.py`](../../backend/app/services/plugin_manager_service.py) |

Helpers du référentiel :

- `CANONICAL_EVENT_NAMES: frozenset[str]` — les 18 valeurs exactes ;
- `is_canonical(value) -> bool` ;
- `resolve_event_name(raw) -> str` — traduit un alias legacy ;
- `LEGACY_EVENT_ALIASES: dict[str, str]` — table de correspondance (§4).

### Extra-canoniques conservés (émis, hors liste spec 11)

Émis par WindFlow et **conservés explicitement** (pas de silence métier) :
`deployment.created`, `deployment.rollback`, `host.ssh_fingerprint_accepted|pending|divergence`
(sécurité TOFU spec 15), `stack.created`, `organization.created|updated`,
`user.created|updated|login|logout`, `plugin.installing|updated|configured|error`,
`system.error`, `system.warning`. Ils ne sont **pas** diffusés sur le pont
WebSocket canonique (comportement historique préservé).

## 3. Modes léger / standard

### 3.1 In-memory (défaut)

`InMemoryEventBus` : dispatch `asyncio` local, isolation d'erreurs par
handler (un handler qui lève n'interrompt jamais les autres). **Aucune
tentative de connexion** tant que `CACHE_URL` n'est pas configuré ; un
seul log info « mode léger » au démarrage.

### 3.2 Redis Pub/Sub (mode standard)

`RedisPubSubEventBus(InMemoryEventBus)` :

- canal unique **`windflow:events`** ;
- `publish()` → dispatch local + `PUBLISH` JSON (`Event.to_dict()` +
  champ `instance_id` uuid identifiant l'instance émettrice) ;
- `start()` → tâche subscriber dédiée (abonnement + boucle `listen`) qui
  re-dispatche **localement** les messages des **autres** instances
  (filtrage `instance_id` — jamais de double dispatch de ses propres
  événements) ;
- échec Redis → log warning **une fois par épisode** + dispatch local
  intact (résilience — pattern `RedisRoleCache` de `core/cache.py`) ;
- `stop()` → annulation propre de la tâche + fermeture pubsub/client.

Câblage : `init_event_bus()` au lifespan, **avant** `setup_event_bridge()`
(le pont s'abonne au bus actif) ; `shutdown_event_bus()` au shutdown.
L'URL Redis est **masquée** dans les logs (`_safe_redis_url` — jamais de
credentials, rules 40).

### 3.3 Setting

```
CACHE_URL=redis://localhost:6379/1   # active le mode standard
# (non défini)                        # mode léger in-memory
```

`cache_url` sera réutilisé par STORY-168 (cache unifié) — un seul
setting pour la brique Redis du mode standard.

## 4. Table de correspondance ancien → nouveau (critère de done P2-2)

Miroir exact de `LEGACY_EVENT_ALIASES`. Les alias sont **acceptés en
entrée API** scheduler (résolus vers le canonique au stockage) et
**traduits en base** par la data migration Alembic
`1341_normalize_event_names` (voir §6).

| Ancien nom (retiré) | Nouveau canonique | Note |
|---------------------|-------------------|------|
| `deployment.completed` | `deployment.succeeded` | forme canonique unique (jamais `completed`) |
| `target.created` | `host.added` | `host.*` remplace `target.*` |
| `target.updated` | — **membre supprimé** | jamais émis, aucun équivalent ; lignes éventuelles traduites `host.offline` (plus proche sémantique) |
| `target.deleted` | `host.removed` | |
| `target.health_check` | `host.offline` | désormais émis sur **transition** joignable→injoignable uniquement |
| `stack.deleted` | `stack.removed` | |
| `plugin.uninstalled` | `plugin.removed` | |

Les empreintes SSH TOFU (`target.ssh_fingerprint_*`) sont devenues
`host.ssh_fingerprint_*` (extra-canoniques sécurité — hors table des
alias car renommage de membre enum sans changement de sémantique
nomenclature).

## 5. Pont WebSocket & double émission bornée

[`websocket/event_bridge.py`](../../backend/app/websocket/event_bridge.py) :

- chaque événement **canonique** est diffusé vers les abonnés
  `/ws/events` sous sa **clé canonique** (ex. `deployment.succeeded`) ;
- les événements `deployment.*` (canoniques **et** extra-canoniques
  created/rollback) continuent **aussi** d'être diffusés vers la clé
  transport historique `DEPLOYMENT_STATUS_CHANGED` — compat frontend
  pendant la période de transition ;
- borne : `LEGACY_WS_EVENT_NAMES_ENABLED` (défaut `true`) — retrait tracé
  **STORY-253/254** ; consigné au CHANGELOG ;
- extra-canoniques non déploiement : non diffusés (log debug inchangé) ;
- `DEPLOYMENT_PROGRESS` (transport WS) : volontairement non mappé —
  décision portée par STORY-163.

Frontend : aucune modification requise pendant la période de double
émission (les souscriptions par `event_type` string existantes
continuent de fonctionner).

## 6. Scheduler : alias & data migration

Les triggers événement (`ScheduledTask.event_name`) comparent la valeur
**canonique** émise par le bus. Trois niveaux de défense (T9) :

1. **Schéma** [`schemas/scheduled_task.py`](../../backend/app/schemas/scheduled_task.py) :
   `_validate_event_name` accepte les alias **en résolvant vers le
   canonique** (stockage canonique ; 422 si inconnu même après
   résolution) ;
2. **Service** [`scheduler_service.py`](../../backend/app/services/scheduler_service.py) :
   même résolution à la re-validation défensive ;
3. **Triggers** [`scheduler_event_triggers.py`](../../backend/app/services/scheduler_event_triggers.py) :
   `resolve_event_name()` avant le match DB (une ligne encore stockée
   sous un alias reste fonctionnelle).

**Data migration Alembic** `1341_normalize_event_names` (data-only) :
`UPDATE scheduled_tasks SET event_name = <canonique> WHERE event_name IN
(<alias>)` — couvre tous les alias, y compris les valeurs jamais émises
(robustesse). Downgrade no-op documenté (non réversible : plusieurs
alias mappent vers `host.offline`).

## 7. Sécurité (rules 40)

- Payloads d'événements : **IDs/noms/statuts/durées uniquement** —
  jamais de secrets, tokens, variables d'environnement ni matériel de
  clé SSH ; les empreintes d'hôte SSH sont publiques par nature
  (identification) ;
- URL Redis masquée dans les logs (`://***@`) ;
- `emit()` : une valeur hors `EventType` lève
  `InvalidEventTypeNameError` (plus de réencapsulation silencieuse en
  `system.error` — fragilité WEBSOCKET-REAL-TIME §4 corrigée) ;
- l'émission est **best-effort** côté émetteurs (try/except) : elle
  n'altère jamais les réponses API ni les opérations métier ;
- `/ws/events` reste protégé RBAC (STORY-122.6) — inchangé ;
- l'événement ne remplace pas les audit logs existants
  (`deployment.succeeded` déjà audité côté `AuditService`).

## 8. Interface `Bus` (contrat stable)

```python
class Bus(Protocol):
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None: ...
    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None: ...
    async def publish(self, event: Event) -> None: ...
    async def emit(self, event_type: EventType, event_data: dict[str, Any]) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
```

Interface identique pour les plugins en mode léger et standard
(spec 11 § Bus d'événements).

## 9. Consommateurs plugins (STORY-163)

### 9.1 SDK hooks — `app.plugins.hooks`

> **Divergence d'import assumée** : la spec 11 montre un exemple
> illustratif `from windflow.plugins.hooks import ...` ; le package
> applicatif s'importe `app.*` (convention de tout le backend) — le SDK
> réel est donc `app.plugins.hooks`.

- `PluginEvent` : enveloppe légère (`name`, `data`, `timestamp`,
  `event_id`) — jamais l'`Event` interne brut (réduction de surface) ;
  `data` est une **copie défensive** du payload ;
- `PluginHooks` : classe de base ; le registre d'instance
  `hooks: dict[str, list[callable]]` est assemblé à l'instanciation ;
- `@on_event("<canonique>")` : valide le nom **au décorateur** — les 18
  canoniques uniquement. Les noms SCREAMING_SNAKE (ex.
  `DEPLOYMENT_PROGRESS` — types de **transport WS**) et les
  extra-canoniques (ex. `organization.created`, sécurité
  `host.ssh_fingerprint_*`) lèvent `InvalidEventTypeNameError`
  (avertissement WEBSOCKET §4.2 : la souscription plugins se fait
  uniquement sur les canoniques).

```python
from app.plugins.hooks import PluginHooks, PluginEvent, on_event

class MyHooks(PluginHooks):
    @on_event("stack.deployed")
    async def on_deployed(self, event: PluginEvent) -> None: ...

    @on_event("deployment.failed")
    async def on_failed(self, event: PluginEvent) -> None: ...
```

Contrat : hooks **asynchrones non bloquants** — ils réagissent après
coup et ne peuvent pas refuser une action (les décisions bloquantes
sont les gates pre-deploy de STORY-170).

### 9.2 Pont `PluginHooksService` — isolation d'exécution

[`plugin_hooks_service.py`](../../backend/app/services/plugin_hooks_service.py)
s'abonne aux **18 canoniques uniquement** (jamais les extra-canoniques —
réduction de surface, sécurité TOFU incluse) et dispatche chaque hook en
**tâche asyncio dédiée** :

- timeout par hook (`plugin_hooks_timeout_seconds`, défaut 30 s —
  cohérent avec `HOOK_TIMEOUT_SECONDS` des hooks lifecycle) : hook lent
  → `TimeoutError` loggé WARNING, hook annulé ;
- erreur de hook → ERROR loggé (plugin + événement), jamais propagée ;
- pool borné (sémaphore, 16 concurrents max) — pas de tempête de tâches ;
- le `publish` de l'émetteur **revient immédiatement** : un plugin lent
  ou en échec ne bloque jamais le bus ni les autres abonnés (AC 1).

Settings : `plugin_hooks_enabled` (défaut `True`),
`plugin_hooks_timeout_seconds` (défaut 30), `plugin_hooks_demo_enabled`
(défaut `False`).

### 9.3 Chargement lifespan des `hooks_module`

Au startup (après `init_event_bus()`/`setup_event_bridge()`) : lecture
des plugins `type IN (extension, hybrid)` ET `status IN (installed,
running)` en base, puis pour chaque `manifest_data.extensions.hooks_module`
présent — import dynamique `importlib` résolu sous
`plugins_base_dir/<plugin_name>/` avec contrôle **anti path-traversal**
(pattern `plugin_lifecycle_service._resolve_script_path` : refus des
chemins absolus, des `..` et de toute sortie du base_dir).

Best-effort : l'échec d'un plugin (chemin refusé, import impossible,
aucune sous-classe `PluginHooks`) est loggé WARNING et ignoré — le
startup reste intact. **Tant que STORY-169 (installation réelle) n'est
pas faite, la base ne contient pas de fichiers extraits : zéro hook
chargé en environnement courant** (log debug) — le mécanisme et le
démonstrateur (`app/plugins/examples/demo_logger_hooks.py`,
`stack.deployed` + `deployment.failed`) sont couverts par les tests.
STORY-169 devra brancher l'enregistrement des hooks à l'installation.

### 9.4 `DEPLOYMENT_PROGRESS` — transport WS (décision : émettre)

Décision du plan de remédiation (§4 P2-2/B7) : le type **existe et est
consommé** (plugins `deployment_monitor`/`deployment_notifications`,
handler frontend `handleProgress` de `useDeploymentWebSocket.ts`) — il
est donc **émis**, jamais retiré.

- **Jamais sur le bus canonique** : c'est un type de transport WebSocket
  (§4.2 WEBSOCKET-REAL-TIME) — émission par
  `DeploymentEventsService.emit_progress_update()` (modèle
  `emit_logs_update` : broadcast direct, best-effort) ;
- payload **snake_case** aligné sur le contrat frontend
  (`frontend/src/types/websocket.ts`) : `deployment_id`, `progress`,
  `current_step`, `total_steps`, `timestamp` (+ `step` conservé pour les
  logs internes de `deployment_monitor`, qui lit `current_step` avec
  fallback `step`) ;
- émission aux **jalons observables** de `deploy_stack_async`
  ([`background_tasks.py`](../../backend/app/tasks/background_tasks.py)) —
  les sous-étapes `pulling/creating/starting` sont internes aux services
  Docker (non observables individuellement, non instrumentées) :

| Jalon | docker simple (7 étapes) | compose (9 étapes) |
|-------|--------------------------|--------------------|
| `starting` | 5 | 5 |
| `stack_loaded` | 15 | 15 |
| `mode_determined` | 20 | 20 |
| `variables_substituted` | 35 | 35 |
| `validated` | 45 | 45 |
| `labels_injected` | — | 55 |
| `compose_generated` | — | 65 |
| `deploying` | 75 | 75 |
| `completed` | 100 | 100 |

Aucun progress sur le chemin d'échec : l'exception propage `FAILED` via
`update_status` existant. Payload limité à ID/étapes/progression
(rules 40 — jamais de variables de déploiement ni secrets).

### 9.5 Statut des clés de souscription mortes de `deployment_notifications`

`deployment_notifications` est désormais **enregistré** via
`default_plugins` (T3 — pattern des 3 autres plugins internes,
auto-enregistrement à l'import retiré). Ses clés de souscription
`"deployment_events"` et `f"deployment_progress_{id}"` ne sont **pas
exposées par le `SubscriptionHandler`** (clés mortes) — son contrat
actuel (log + `broadcast_to_user` si `user_id`) reste satisfaisant ;
la refonte de ces canaux est tracée **STORY-164/165** (hors périmètre
163, garde-fou §2.G : ne pas casser l'architecture des modules de
broadcast internes).
