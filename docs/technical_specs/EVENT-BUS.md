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

## 8. Interface `Bus` pour les plugins (entrée de STORY-163)

```python
class Bus(Protocol):
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None: ...
    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None: ...
    async def publish(self, event: Event) -> None: ...
    async def emit(self, event_type: EventType, event_data: dict[str, Any]) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
```

STORY-163 (consommateurs plugins : hooks `@on_event`,
`deployment_notifications`, décision `DEPLOYMENT_PROGRESS`) s'appuiera
sur ce contrat tel quel — interface identique pour les plugins en mode
léger et standard (spec 11 § Bus d'événements).
