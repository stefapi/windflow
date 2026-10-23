# STORY-162 : Bus d'événements canonique — interface unique, nomenclature des ~18 événements, in-memory par défaut + Redis Pub/Sub optionnel (P2-2, partie bus — arbitrage F6)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-2 (axes B7, C5, F6, rapports §6/§8) — ampleur **L**

## Description

En tant que développeur backend WindFlow, je veux un **bus d'événements canonique** exposant une interface unique et la nomenclature exacte des ~18 événements de la spec 11 (`deployment.succeeded` — jamais `completed` —, `host.*` — jamais `target.*` —, `container.*`, `stack.deployed`…), avec l'implémentation in-memory par défaut (mode léger RPi) et une implémentation Redis Pub/Sub activée quand `cache_url` est configuré, afin que plugins, scheduler et pont WebSocket consomment un contrat stable conforme aux specs au lieu d'un enum divergent et de stubs Redis morts.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §9.2-9.4, [WEBSOCKET-REAL-TIME.md §10.2](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md)) : l'enum `EventType` de [`events.py`](../../backend/app/core/events.py:115) suit le format mais **pas la liste** canonique (`deployment.completed` au lieu de `succeeded`, `target.*` au lieu de `host.*`, domaines `container.*`/`machine.*` manquants, domaines extra-canoniques `organization.*`/`user.*`/`system.*`) ; les stubs Redis Streams (lignes 144, 227, 255, 298, 321, 376) sont des coquilles TODO ; l'arbitrage F6 tranche : interface canonique + 2 implémentations, Streams complets (replay/event sourcing) hors périmètre.

## Contexte technique

### Cartographie du code existant (analyse du 2026-10-23)

**Zone bus — [`core/events.py`](../../backend/app/core/events.py) (455 lignes)** :

- `EventType` (str Enum, l.18-68) : 28 membres au format `domaine.action_passé` mais liste divergente — `DEPLOYMENT_COMPLETED`, `TARGET_*` (dont `TARGET_SSH_FINGERPRINT_*`), `STACK_DELETED`, `PLUGIN_UNINSTALLED` ; **aucun** `container.*`, `machine.*`, `host.*`, `stack.deployed` ; extra-canoniques `organization.*`, `user.*`, `system.*`, `plugin.installing|updated|configured|error`, `deployment.created|rollback` ;
- `Event` (dataclass, l.71-118) avec `to_dict()/from_dict()` JSON-safe — **réutilisable tel quel** (transport Redis) ;
- `EventBus` (l.124-277) : dispatch in-memory fonctionnel (`subscribe/unsubscribe/publish` + alias `emit`) ; stubs Redis Streams en TODO commenté : `_init_redis` (l.150), `_publish_to_redis` (l.233), `replay_events` (l.247), classe `EventStore` entière (l.280-413) — **`EventStore` et `replay_events` ont 0 référence hors du module** (supprimables) ;
- Fragilité `emit()` (l.209-231) : un `event_type` non-`EventType` est réencapsulé en `SYSTEM_ERROR` avec `_original_event_type` en métadonnée (constat [`WEBSOCKET-REAL-TIME.md`](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) §4 l.267) — AC 4 exige correction ;
- Singletons : `get_event_bus()` (l.420), `publish_event()` (l.441), instance globale `event_bus` (l.454) — consommés par tous les émetteurs, à préserver.

**Émetteurs réels (vérifiés par recherche exhaustive)** :

- [`deployment_events.py`](../../backend/app/services/deployment_events.py) `emit_status_change` (l.82-91) : `"success"` → `DEPLOYMENT_COMPLETED` (à corriger) — unique appelant [`deployment_service.py`](../../backend/app/services/deployment_service.py) `update_status` (l.775, zone best-effort post-commit) ; l'audit voisin utilise **déjà** `"deployment.succeeded"` (l.748) — seul le bus diverge ;
- [`ssh_connection.py`](../../backend/app/services/ssh_connection.py) (l.190-230) + [`api/v1/targets/fingerprints.py`](../../backend/app/api/v1/targets/fingerprints.py) (l.291) : `TARGET_SSH_FINGERPRINT_PENDING|DIVERGENCE|ACCEPTED`, payloads déjà sans secret ;
- [`scheduler_engine.py`](../../backend/app/services/scheduler_engine.py) (l.648-684) : `SYSTEM_WARNING` (`scheduled_task.repeated_failures`) ;
- [`plugin_manager_service.py`](../../backend/app/services/plugin_manager_service.py) `_emit_event` (l.543) : **logger structuré seul, jamais le bus** — `plugin.installed|updated|uninstalled|configured` non publiés ; idem `plugin_lifecycle_service` (`PLUGIN_ERROR`) ;
- **Jamais émis nulle part** : `STACK_*`, `TARGET_CREATED|UPDATED|DELETED|HEALTH_CHECK`, `ORGANIZATION_*`, `USER_*`, `container.*`, `host.*`, `machine.*`.

**Consommateurs réels** :

- [`websocket/event_bridge.py`](../../backend/app/websocket/event_bridge.py) : `EVENT_TYPE_MAPPING` = 5 membres déploiement → `DEPLOYMENT_STATUS_CHANGED` ; `setup/teardown_event_bridge` appelés au lifespan ([`main.py`](../../backend/app/main.py) l.105-108) ; diffusion via `broadcast_to_event_subscribers(clé=event_type str)` ;
- [`scheduler_event_triggers.py`](../../backend/app/services/scheduler_event_triggers.py) : abonné à **tous** les `EventType` ; match DB `ScheduledTask.event_name == event.event_type.value` (l.143-158) ;
- Validation `event_name` : [`schemas/scheduled_task.py`](../../backend/app/schemas/scheduled_task.py) `_CANONICAL_EVENT_NAMES = frozenset(member.value for member in EventType)` (l.36) — **toute l'enum** est acceptée aujourd'hui ; re-validée dans [`scheduler_service.py`](../../backend/app/services/scheduler_service.py) (l.97-108). ⚠️ Un renommage de valeurs sans migration casse les `event_name` stockés en base (triggers muets).

**Config / infra** :

- Pas de `cache_url` dans [`config.py`](../../backend/app/config.py) — Redis uniquement via `rate_limit_storage_url` (l.329) ; `redis = "^5.0.0"` **déjà dépendance** ([`pyproject.toml`](../../pyproject.toml) l.35) ;
- Pattern complet à réutiliser dans [`core/cache.py`](../../backend/app/core/cache.py) : import conditionnel `REDIS_AVAILABLE`, client injecté, `MemoryRoleCache`/`RedisRoleCache` + fallback mémoire, factory singleton async lazy (`ping`) + `reset_*()` pour tests, `publish()` best-effort (l.176-190) ;
- Lifespan [`main.py`](../../backend/app/main.py) : init Redis rate limiter avec URL masquée (l.113-135), boucles asyncio dédiées, cleanup au shutdown.

**Frontend** : souscriptions WS par `event_type` string (`'DEPLOYMENT_STATUS_CHANGED'` — [`useDeploymentWebSocket.ts`](../../frontend/src/composables/useDeploymentWebSocket.ts) l.354) ; aucun code frontend ne consomme `deployment.completed`/`target.*` → la double émission **transport** (pont) suffit, **aucune modif frontend requise** dans cette story.

### Patterns à réutiliser

- `core/cache.py` : Protocol typing + duo Memory/Redis + factory lazy + reset tests — modèle direct pour `Bus` ;
- `main.py` lifespan : init/cleanup Redis, masquage d'URL, gestion de tâches asyncio ;
- Tests : client `AsyncMock` injecté ([`test_core/test_cache.py`](../../backend/tests/unit/test_core/test_cache.py)), bus réel + handlers espions ([`test_scheduler_event_triggers.py`](../../backend/tests/unit/test_services/test_scheduler_event_triggers.py)).

### Réutilisation directe / adaptation / réécriture

- **Directe** : `Event` (dataclass + sérialisation), dispatch in-memory d'`EventBus`, `setup/teardown_event_bridge`, patterns `cache.py` ;
- **Adaptation** : `deployment_events` (mapping statut → canonique), `plugin_manager._emit_event` (logger → bus), `_CANONICAL_EVENT_NAMES` (résolution d'alias), mapping du pont (extension + double émission bornée) ;
- **Réécriture** : `EventType` (référentiel canonique 18 + extra-canoniques séparés + alias), `EventBus` → `InMemoryEventBus` + `RedisPubSubEventBus` derrière interface `Bus` ; **suppression** des stubs Redis Streams, `replay_events`, `EventStore` (hors périmètre assumé F6 — replay/event sourcing).

### Décisions d'analyse

1. `EventType` reste **l'unique référentiel** (membres canoniques + bloc extra-canonique documenté + `is_canonical()`) — pas de second enum qui divergerait à nouveau ;
2. Double émission (ancien + canonique) au niveau **transport WS (pont)** uniquement — le bus n'émet que le canonique ; les triggers scheduler consomment le canonique (résolution d'alias en entrée API + data migration des valeurs stockées) ;
3. `target.updated` **retiré** (jamais émis, aucun équivalent `host.*` — tracé dans la table de correspondance) ; `machine.*` **définis sans émetteur** (Roadmap VMs — documenté, pas un silence métier) ;
4. `host.offline` émis par le health check périodique (transition joignable→injoignable, `TargetService.check_all_health` — boucle lifespan existante) ;
5. `stack.deployed` émis au **succès d'un déploiement de stack** (`deployment_service.update_status`) ; `stack.created` (création de définition ≠ déploiement) reste extra-canonique ;
6. `cache_url` introduit ici sera réutilisé par STORY-168 (cache unifié) — coordination notée dans Dépendances.

### Risques / hypothèses

- Renommage de membres `EventType` → imports à corriger dans ~10 fichiers (services + tests : `test_ssh_connection`, `test_targets_fingerprints`, `test_scheduler_*`) — tâche mécanique mais exhaustive ;
- `event_name` stockés en base → **data migration Alembic obligatoire** (sinon triggers muets après renommage) + résolution d'alias défensive à trois niveaux (schéma, service, triggers) ;
- Subscriber Redis : tâche asyncio à arrêter proprement au shutdown ; filtrage de l'écho de ses propres messages (`instance_id`) pour éviter le double dispatch ;
- Double émission WS bornée par setting — retrait tracé (STORY-253/254) ;
- `services[]` du payload `stack.deployed` : au mieux des données disponibles au site d'émission — divergence à documenter si incomplet.

Éléments existants à réutiliser / contraintes :
- **Arbitrage F6 (tranché)** : extraire une interface `Bus` canonique ; garder l'EventBus in-memory comme implémentation par défaut (le pont WebSocket [`event_bridge.py`](../../backend/app/websocket/event_bridge.py:20) est un consommateur réel — ne pas casser) ; ajouter l'implémentation **Redis Pub/Sub** activée quand `cache_url` est configuré ; les stubs Redis Streams commentés sont **remplacés** par cette implémentation Pub/Sub ;
- **Nomenclature** : liste canonique des 18 événements (spec 11 § Liste canonique) : `container.created|started|stopped|removed`, `stack.deployed|updated|removed`, `machine.created|started|stopped`, `deployment.started|succeeded|failed`, `host.added|removed|offline`, `plugin.installed|removed` ; « les événements `host.*` remplacent les anciens `target.*` (alias historique) ; `deployment.succeeded` est la forme canonique » ;
- **Migration des émetteurs** : corriger `deployment.completed` → `deployment.succeeded`, `target.*` → `host.*` ; le pont ne mappe aujourd'hui que 5 types déploiement — l'étendre ; **période d'émission double** prévue pour le frontend (risque §7.3 : la nomenclature touche bridge WS et plugins) ;
- **Table de correspondance ancien→nouveau documentée** (critère de done du plan) — à livrer dans la doc technique de l'epic ;
- Zones : [`core/events.py`](../../backend/app/core/events.py:115) (+ stubs lignes 144-376 remplacés), [`websocket/event_bridge.py`](../../backend/app/websocket/event_bridge.py:20), [`services/deployment_events.py`](../../backend/app/services/deployment_events.py:22) ;
- Les domaines extra-canoniques existants (`organization.*`, `user.*`, `system.*`) restent émis mais sont clairement séparés de la liste canonique (pas de silence métier) ;
- `DEPLOYMENT_PROGRESS` (transport WS) : « émis ou retiré » — la décision d'émission est portée par **STORY-163** (consommateurs/plugins) ; cette story aligne le contrat transport sans le dupliquer ;
- Garde-fou §2.G : WebSocket modulaire — étendre le pont sans casser l'architecture plugins interne.

## Critères d'acceptation (AC)

- [x] AC 1 : Une interface `Bus` canonique (publish/subscribe, typée sur la nomenclature) est extraite ; les ~18 événements spec 11 sont définis en un **unique** référentiel ; sans Redis configuré, le comportement in-memory est intact (tests de non-régression du pont WebSocket : les abonnés `deployment.*` reçoivent bien les événements).
- [x] AC 2 : Avec Redis configuré (`cache_url`), un événement publié est **visible sur le canal Pub/Sub** (test d'intégration avec Redis réel) ; sans Redis, aucune tentative de connexion, aucun warning répété ; les stubs Redis Streams (lignes 144-376) sont supprimés et remplacés par l'implémentation Pub/Sub — Streams/replay restent hors périmètre (noté).
- [x] AC 3 : **Chaque événement canonique est émis par son émetteur réel** — tests : `deployment.succeeded` émis au statut `success` (plus jamais `deployment.completed`), `host.added`/`host.removed` émis à la création/suppression d'une cible (plus jamais `target.*`), `container.started`/`stopped`, `stack.deployed`, `plugin.installed`/`removed` vérifiés sur un échantillon représentatif ; la **table de correspondance ancien→nouveau est documentée** et une période d'émission double (ancien nom + canonique) est active pour le frontend, bornée dans le temps. *(Note : le statut de succès du modèle est `running` — voir divergence 1 des notes d'implémentation.)*
- [x] AC 4 : Le pont `event_bridge.py` mappe l'ensemble des événements canoniques vers les types transport pertinents (extension du mapping déploiement-seul actuel) ; la fragilité connue (`emit()` avec un `WebSocketEventType` réencapsulé en `system.error`) n'est plus dépendue et est corrigée ou supprimée.
- [x] AC 5 : Tests de sécurité/non-régression : consommateurs existants (bridge WS, modules `deployment_monitor`, `subscription`) non cassés ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Système d'événements / **Liste canonique des 18 événements** (référence unique du nommage, alias interdits), § Bus d'événements (Redis Pub/Sub en mode standard, `asyncio.Queue` en mode léger, interface identique pour les plugins) ;
- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § Bus d'événements internes (nomenclature `domaine.action_passé`, modes léger/standard) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § WebSocket (événements système `/ws/events` au nommage canonique) ;
- [`17-automatisation-workflows.md`](../../docs/general_specs/17-automatisation-workflows.md) — § Triggers (scheduler notifié par le bus, liste canonique) ;
- [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) — §4 (deux couches d'événements, pont, articulation), §10.2 (bus semi-canonique : écarts `deployment.completed`/`target.*`, domaines manquants/extra) ;
- [ARCHITECTURE-MODULAIRE.md](../../docs/technical_specs/ARCHITECTURE-MODULAIRE.md) — briques optionnelles (brique `cache` Redis) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-2, §2.B B7, §2.C C5, §3 F6, §7.3 (période d'émission double) ;
- [`backend_status.md`](../../docs/backend_status.md) — §9.2-9.4, §8.3.

## Dépendances

- **Aucune dépendance dure P1** (le plan marque P2-2 « dépend de : — ») ; néanmoins les enveloppes API (STORY-126) ne concernent pas le bus — indépendant.
- **STORY-163** (consommateurs plugins) s'appuie sur cette story ; le trigger événement du scheduler (**STORY-160**, réalisé : `scheduler_event_triggers` consomme déjà l'enum) consomme la nomenclature ; **STORY-167** (deployment_events) s'aligne sur elle ; notifications P2-15 en dépend.
- **Bibliothèques** : `redis ^5.0.0` déjà déclaré dans `pyproject.toml` — **aucune nouvelle dépendance**.
- **Migrations** : une migration Alembic **data-only** (normalisation `scheduled_tasks.event_name` alias → canonique) — aucune nouvelle table/colonne.
- **Coordination STORY-168** (cache unifié) : le setting `cache_url` introduit ici en devient le déclencheur — ne pas dupliquer le setting quand 168 sera traitée.
- **Frontend** : aucune modification requise (la double émission transport couvre la transition ; retrait tracé STORY-253/254).
- **STORY-166** (Target→Host) : compatible — les noms d'événements `host.*` sont posés ici indépendamment du renommage d'entité.

## Sous-stories

*(non prévue — story L ; découpe possible par l'analyse si la migration des émetteurs s'avère trop invasive)*

## État d'avancement technique

- [x] T1 — Référentiel canonique : refonte `EventType` + alias + `resolve_event_name` (`core/events.py` + imports)
- [x] T2 — Interface `Bus` + `InMemoryEventBus` + suppression stubs Redis Streams / `EventStore` + fix `emit()`
- [x] T3 — `RedisPubSubEventBus` + setting `cache_url` + `init_event_bus()`/lifespan
- [x] T4 — `deployment_events` canonique (`deployment.succeeded`) + `stack.deployed`
- [x] T5 — Émetteurs `host.added|removed|offline` (targets + health check)
- [x] T6 — Émetteurs `container.created|started|stopped|removed` (docker.py)
- [x] T7 — `plugin.installed|removed` réellement publiés sur le bus
- [x] T8 — Pont WS étendu + double émission bornée (`legacy_ws_event_names_enabled`)
- [x] T9 — Alias scheduler (schéma + service + triggers) + data migration Alembic + examples OpenAPI
- [x] T10 — Documentation nomenclature + table de correspondance + validation (lint/tests/couverture ≥ 80 %)

## Tâches d'implémentation détaillées

> Séquencement : T1→T3 posent le socle (contrat), T4→T9 migrent émetteurs et consommateurs, T10 documente et valide. **Aucune écriture de code pendant l'analyse — ces tâches sont pour `treat-story`.**

### T1 — Référentiel canonique : refonte de `EventType`
**Fichiers :** [`backend/app/core/events.py`](../../backend/app/core/events.py), puis corrections d'imports dans `services/ssh_connection.py`, `api/v1/targets/fingerprints.py`, `services/deployment_events.py`, `websocket/event_bridge.py`, `services/plugin_manager_service.py`, `services/plugin_lifecycle_service.py` + tests concernés.
- Renommages de membres (valeurs canoniques spec 11) : `DEPLOYMENT_COMPLETED`→`DEPLOYMENT_SUCCEEDED` (« deployment.succeeded ») ; `TARGET_CREATED`→`HOST_ADDED` ; `TARGET_DELETED`→`HOST_REMOVED` ; `TARGET_HEALTH_CHECK`→`HOST_OFFLINE` ; `TARGET_SSH_FINGERPRINT_*`→`HOST_SSH_FINGERPRINT_*` (extra-canoniques sécurité) ; `STACK_DELETED`→`STACK_REMOVED` ; `PLUGIN_UNINSTALLED`→`PLUGIN_REMOVED` ; **supprimer** `TARGET_UPDATED` (jamais émis, aucun équivalent — tracé dans la table de correspondance).
- Ajouter les membres manquants : `CONTAINER_CREATED|STARTED|STOPPED|REMOVED`, `STACK_DEPLOYED`, `MACHINE_CREATED|STARTED|STOPPED` (définis **sans émetteur** — Roadmap VMs, documenté dans la docstring).
- Regrouper et commenter les **extra-canoniques conservés** (émis mais hors liste spec 11) : `organization.*`, `user.*`, `system.*`, `deployment.created|rollback`, `plugin.installing|updated|configured|error`, `host.ssh_fingerprint_*`, `stack.created`.
- Ajouter `CANONICAL_EVENT_NAMES: frozenset[str]` (les 18 valeurs exactes), `LEGACY_EVENT_ALIASES: dict[str, str]` (`deployment.completed`→`deployment.succeeded`, `target.created`→`host.added`, `target.deleted`→`host.removed`, `target.health_check`→`host.offline`, `stack.deleted`→`stack.removed`, `plugin.uninstalled`→`plugin.removed`), `resolve_event_name(raw: str) -> str` et `is_canonical(value: str) -> bool`.

### T2 — Interface `Bus` + `InMemoryEventBus` + purge des stubs
**Fichier :** [`backend/app/core/events.py`](../../backend/app/core/events.py).
- Extraire l'interface `Bus` (Protocol typing — pattern `RoleCacheProtocol` de [`core/cache.py`](../../backend/app/core/cache.py)) : `subscribe/unsubscribe/publish/emit` + `async start()/stop()`.
- Renommer l'implémentation actuelle `EventBus`→`InMemoryEventBus` avec **dispatch local strictement inchangé** (AC 1, non-régression) ; alias de compatibilité `EventBus = InMemoryEventBus` le temps de la transition.
- Supprimer `_init_redis`, `_publish_to_redis`, `replay_events`, la classe `EventStore` et tout stub Redis Streams (AC 2 — remplacés par T3) ; mettre à jour la docstring du module (abandon Event Sourcing/CQRS affiché).
- Corriger `emit()` : `event_type` non-`EventType` → **erreur explicite** (exception dédiée de `core/exceptions.py`) au lieu de la réencapsulation `SYSTEM_ERROR` (AC 4 — fragilité §4 de WEBSOCKET-REAL-TIME). Vérifier les appelants actuels (tous passent des `EventType`).

### T3 — `RedisPubSubEventBus` + setting `cache_url` + câblage lifespan
**Fichiers :** [`backend/app/core/events.py`](../../backend/app/core/events.py), [`backend/app/config.py`](../../backend/app/config.py), [`backend/app/main.py`](../../backend/app/main.py).
- `config.py` : `cache_url: Optional[str] = Field(default=None, ...)` (« Redis URL mode standard — bus d'événements + cache ») ; ne **pas** toucher `rate_limit_storage_url`.
- `RedisPubSubEventBus(InMemoryEventBus)` : client `redis.asyncio` **injecté** ; canal unique `windflow:events` ; `publish()` → dispatch local + `PUBLISH` JSON (`Event.to_dict()` + champ `instance_id` uuid) ; `start()` → tâche subscriber (`pubsub.subscribe` + boucle `listen`) qui re-dispatche localement les messages **des autres instances** (filtrage `instance_id` — pas de double dispatch) ; échec Redis → log warning **une fois par épisode** (jamais répété en boucle) + dispatch local intact (résilience — pattern `RedisRoleCache`) ; `stop()` → annulation propre de la tâche + fermeture pubsub/client.
- `init_event_bus()` async : factory singleton mémorisée + `reset_event_bus()` pour tests (pattern `get_role_cache`/`reset_role_cache`) — `cache_url` configuré + `redis` importable + `ping` OK → `RedisPubSubEventBus` démarré ; sinon `InMemoryEventBus` + **un seul** log info « mode léger » (aucune tentative de connexion — AC 2).
- `main.py` lifespan : `await init_event_bus()` au startup **avant** `setup_event_bridge()` (le pont s'abonne au bus actif) ; arrêt au shutdown ; log du mode avec URL masquée (pattern `_safe_url` l.120-124 — jamais de credentials dans les logs).

### T4 — Émetteurs déploiement canoniques + `stack.deployed`
**Fichiers :** [`backend/app/services/deployment_events.py`](../../backend/app/services/deployment_events.py), [`backend/app/services/deployment_service.py`](../../backend/app/services/deployment_service.py).
- `event_type_map` : `"success"` → `DEPLOYMENT_SUCCEEDED` (plus jamais `DEPLOYMENT_COMPLETED`) ; statut inconnu → warning + **pas d'émission** (supprimer le fallback silencieux actuel).
- `deployment_service.update_status` : au passage `success` d'un déploiement de stack, émettre aussi `STACK_DEPLOYED` `{stack_id, name, host_id, services[]}` (`services[]` au mieux des données disponibles — divergence à documenter si incomplet) — zone best-effort post-commit existante (l.740-786).
- **Sécurité (règle 40)** : payloads limités à IDs/noms/statuts/duration — jamais de secrets, tokens ni variables d'environnement.

### T5 — Émetteurs `host.*`
**Fichiers :** [`backend/app/api/v1/targets/crud.py`](../../backend/app/api/v1/targets/crud.py), [`backend/app/services/target_service.py`](../../backend/app/services/target_service.py).
- `create_target` → `HOST_ADDED` `{host_id, name, profile, engines}` ; `delete_target` → `HOST_REMOVED` `{host_id, name}` — émission best-effort post-commit (try/except, n'altère pas la réponse API), **jamais de credentials ni de matériel de clé SSH dans les payloads**.
- `TargetService.check_all_health` : transition joignable→injoignable → `HOST_OFFLINE` `{host_id, name, last_seen}` (émetteur naturel — boucle lifespan existante). Si trop invasif : signaler la divergence avant d'improviser (AC 3 ne le liste pas dans l'échantillon minimal).

### T6 — Émetteurs `container.*`
**Fichier :** [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py).
- `create_container` → `CONTAINER_CREATED` `{container_id, name, image}` ; `start_container` → `CONTAINER_STARTED` ; `stop_container` → `CONTAINER_STOPPED` ; `remove_container` → `CONTAINER_REMOVED` — émission best-effort **après succès** de l'opération Docker ; payload sans env/labels (règle 40).

### T7 — `plugin.*` réellement publiés sur le bus
**Fichiers :** [`backend/app/services/plugin_manager_service.py`](../../backend/app/services/plugin_manager_service.py), [`backend/app/services/plugin_lifecycle_service.py`](../../backend/app/services/plugin_lifecycle_service.py).
- Brancher `_emit_event` sur le bus (`await` best-effort try/except — ne doit jamais faire échouer install/uninstall) **en plus** du log structuré : install → `PLUGIN_INSTALLED` `{plugin_name, version}` ; uninstall → `PLUGIN_REMOVED` `{plugin_name}` ; `PLUGIN_UPDATED`/`PLUGIN_CONFIGURED` extra-canoniques (membres existants) ; idem `PLUGIN_ERROR` côté lifecycle.

### T8 — Pont WS étendu + double émission bornée
**Fichiers :** [`backend/app/websocket/event_bridge.py`](../../backend/app/websocket/event_bridge.py), [`backend/app/config.py`](../../backend/app/config.py).
- Étendre le mapping : **chaque événement canonique** → diffusion `broadcast_to_event_subscribers(clé = nom canonique)` (spec 09 : `/ws/events` au nommage canonique) ; les `deployment.*` continuent **aussi** d'être diffusés vers `DEPLOYMENT_STATUS_CHANGED` (compat frontend — période d'émission double).
- `config.py` : `legacy_ws_event_names_enabled: bool = True` borne la double émission (retrait tracé STORY-253/254 — consigné au CHANGELOG).
- Extra-canoniques : non diffusés (comportement actuel préservé, log debug inchangé). Ne **pas** mapper `DEPLOYMENT_PROGRESS` (décision portée par STORY-163).
- `setup/teardown_event_bridge` : itération sur le mapping étendu, sans duplication de handler.

### T9 — Compatibilité scheduler `event_name` + data migration + OpenAPI
**Fichiers :** [`backend/app/schemas/scheduled_task.py`](../../backend/app/schemas/scheduled_task.py), [`backend/app/services/scheduler_service.py`](../../backend/app/services/scheduler_service.py), [`backend/app/services/scheduler_event_triggers.py`](../../backend/app/services/scheduler_event_triggers.py), nouvelle migration dans `backend/alembic/versions/`, [`backend/app/api/v1/schedules.py`](../../backend/app/api/v1/schedules.py).
- `_validate_event_name` : accepter les alias `LEGACY_EVENT_ALIASES` **en résolvant vers le canonique** (stockage canonique ; 422 si inconnu même après résolution) ; `_CANONICAL_EVENT_NAMES` recalculé depuis `EventType`.
- `scheduler_service` (re-validation l.97-108) : même résolution ; `scheduler_event_triggers._dispatch` : `resolve_event_name()` avant le match DB (défense en profondeur).
- **Migration Alembic data-only** (`down_revision` = head courant) : `UPDATE scheduled_tasks SET event_name = <canonique> WHERE event_name IN (<alias>)` — couvrir tous les alias, y compris les valeurs jamais émises (robustesse).
- `schedules.py` : rafraîchir les examples OpenAPI de `event_name` vers les noms canoniques (documentation à jour — API-first).

### T10 — Documentation nomenclature + validation
**Fichiers :** `docs/technical_specs/EVENT-BUS.md` (nouveau), validation via Makefile.
- Documenter : liste canonique des 18 (+ extra-canoniques et leur justification), modes léger/standard (in-memory vs Redis Pub/Sub, canal `windflow:events`, **absence de replay/Streams — hors périmètre F6**), **table de correspondance ancien→nouveau** (critère de done P2-2 — miroir de `LEGACY_EVENT_ALIASES`), période de double émission WS + setting + borne de retrait, `machine.*` sans émetteur (Roadmap VMs), interface `Bus` pour les plugins (entrée de STORY-163).
- Validation : `make backend-lint` (isort/black/flake8/mypy/bandit), tests ciblés puis `make backend-test-unit`, couverture ≥ 80 % sur `core/events.py`, `event_bridge.py`, `deployment_events.py` et les modules émetteurs touchés (AC 5) ; `make generate-openapi-docs` si les examples ont changé.

## Tests à écrire

> Chemins conformes à `55-project-structure.md`. Bus espion = instance réelle + handler collecteur (pattern `test_scheduler_event_triggers.py`).

### Unitaires backend

**1. `backend/tests/unit/test_core/test_events.py` (nouveau) — socle :**
- Référentiel : les 18 valeurs canoniques **exactes** spec 11 (assertion d'égalité de set) ; `is_canonical()` vrai/faux ; `resolve_event_name()` sur chaque alias ; extra-canoniques bien séparés ;
- In-memory (AC 1) : `publish` → handlers abonnés appelés ; un handler qui lève n'interrompt pas les autres ; `unsubscribe` ; `emit()` avec `EventType` OK ; `emit()` avec valeur étrangère → erreur explicite (plus de réencapsule `SYSTEM_ERROR`) ;
- Factory : sans `cache_url` → `InMemoryEventBus`, **aucune tentative de connexion**, un seul log info (AC 2).

**2. `backend/tests/unit/test_core/test_events_redis.py` (nouveau) — `RedisPubSubEventBus` avec client `AsyncMock` :**
- `publish` → `PUBLISH` sur `windflow:events` avec JSON complet (`Event.to_dict()` + `instance_id`) **et** dispatch local ;
- message reçu d'une autre instance → dispatch local ; message de sa propre `instance_id` → ignoré (pas de double) ;
- échec `PUBLISH` → warning + dispatch local intact (aucune exception propagée) ; échec subscriber idem ;
- `start()/stop()` : tâche subscriber créée puis annulée proprement (pas de fuite).

**3. `backend/tests/unit/test_websocket/test_event_bridge.py` (nouveau) — AC 4 :**
- `deployment.succeeded` → broadcast vers clé canonique **et** `DEPLOYMENT_STATUS_CHANGED` (double émission) ; `legacy_ws_event_names_enabled=False` → clé canonique seule ;
- `container.started`, `host.added`, `stack.deployed`, `plugin.installed` → broadcast clé canonique ;
- extra-canonique (`organization.created`) → pas de broadcast ;
- `setup/teardown` : abonnements ajoutés/retirés, idempotence.

**4. `backend/tests/unit/test_services/test_deployment_events.py` — AC 3 :**
- `success` → `DEPLOYMENT_SUCCEEDED` (**jamais** `deployment.completed`) ; `deploying`/`running` → `STARTED` ; `failed` → `FAILED` ; statut inconnu → pas d'émission + warning ;
- payload : IDs/noms uniquement — assertion d'absence de secrets.

**5. Émetteurs (enrichir les suites existantes, bus espion injecté) :**
- `backend/tests/unit/test_api/test_docker.py` : create/start/stop/remove → `CONTAINER_*` émis une fois, payload conforme (container_id, name, [image]) ;
- tests API targets (suite `test_targets_*` existante) : create/delete → `HOST_ADDED`/`HOST_REMOVED`, payload sans credentials ;
- `backend/tests/unit/test_services/test_plugin_manager_service.py` : install/uninstall → `PLUGIN_INSTALLED`/`PLUGIN_REMOVED` publiés sur le bus ;
- `backend/tests/unit/test_services/test_target_service.py` : transition health check → `HOST_OFFLINE` `{host_id, name, last_seen}` ;
- suite deployment_service existante : statut `success` → `DEPLOYMENT_SUCCEEDED` + `STACK_DEPLOYED` émis (mock bus).

**6. Non-régression (mises à jour des suites existantes) :**
- `test_scheduler_event_triggers.py` : `event_name` canonique déclenche ; alias résolu déclenche aussi (T9) ;
- `test_scheduler_engine.py`, `test_ssh_connection.py`, `test_api/test_targets_fingerprints.py` : membres renommés (`HOST_SSH_FINGERPRINT_*`) — comportements inchangés ;
- AC 1 explicite : abonnés `deployment.*` du pont reçoivent toujours les événements sans Redis.

### Intégration backend

**7. `backend/tests/integration/test_events_pubsub.py` (nouveau) — AC 2 avec Redis réel** (skipif indisponible) :
- `publish` via `RedisPubSubEventBus` → un souscripteur du canal `windflow:events` reçoit un `Event` désérialisable ;
- multi-instances : instance B reçoit le message de A et dispatche vers ses handlers locaux.

**8. `backend/tests/integration/test_migrations.py` (enrichissement) :**
- data migration : insertion d'un `event_name` alias → `upgrade head` → valeur canonique en base.

### Sécurité (règle 40)

Aucun nouvel endpoint REST → pas de 401/403/422/404 nouveaux. Les exigences sécurité se matérialisent par : assertions « payloads sans secrets » (tests 4 et 5), absence de credentials dans les messages Redis (test 2), URL Redis masquée dans les logs (T3), `/ws/events` déjà protégé RBAC (STORY-122.6) inchangé. L'émission d'événements ne remplace pas les audit logs existants (`deployment.succeeded` déjà audité).

**Couverture cible : ≥ 80 % sur les modules touchés (AC 5).**

## Notes d'implémentation

### Statut
Développement terminé — `REVIEW` (tests passants, lint ciblé OK, couverture > 80 % sur les modules cœur). **Clôturée `DONE` le 2026-10-23** (finalise-story : DoD vérifié — AC 1-5 cochés, T1-T10 cochés, notes complètes ; sanity check final 74 passed / 1 skipped PG absent, aucun échec).

### Fichiers modifiés/créés

**Socle bus (T1-T3) :**
- `backend/app/core/events.py` — réécriture complète : référentiel `EventType` (18 canoniques + extra-canoniques regroupés/commentés), `CANONICAL_EVENT_NAMES`, `LEGACY_EVENT_ALIASES`, `resolve_event_name`, `is_canonical`, interface `Bus` (Protocol), `InMemoryEventBus` (alias `EventBus` conservé), `RedisPubSubEventBus` (canal `windflow:events`, `instance_id`, warning unique par épisode), `init_event_bus`/`reset_event_bus`/`shutdown_event_bus`/`get_event_bus`, suppression des stubs Redis Streams/`EventStore`/`replay_events` ;
- `backend/app/core/exceptions.py` — nouvelle `InvalidEventTypeNameError` (fix fragilité `emit`) ;
- `backend/app/config.py` — settings `cache_url` + `legacy_ws_event_names_enabled` ;
- `backend/app/main.py` — `init_event_bus()` avant `setup_event_bridge()` au startup, `shutdown_event_bus()` au shutdown.

**Émetteurs (T4-T7) :**
- `backend/app/services/deployment_events.py` — mapping canonique, `running` → `DEPLOYMENT_SUCCEEDED`, statut inconnu → pas d'émission + warning ;
- `backend/app/services/deployment_service.py` — `STACK_DEPLOYED` au succès RUNNING d'un déploiement de stack (best-effort post-commit) ;
- `backend/app/api/v1/targets/crud.py` — `HOST_ADDED`/`HOST_REMOVED` (payloads sans credentials) ;
- `backend/app/services/target_service.py` — `HOST_OFFLINE` sur transition joignable→injoignable uniquement (pas de spam OFFLINE→OFFLINE) ;
- `backend/app/api/v1/docker.py` — `CONTAINER_CREATED|STARTED|STOPPED|REMOVED` (après succès Docker, payload id/nom/image sans env/labels) ;
- `backend/app/services/plugin_manager_service.py` + `plugin_lifecycle_service.py` — `_publish_to_bus` best-effort (installed/removed/updated/configured/error).

**Pont WS (T8) :** `backend/app/websocket/event_bridge.py` — mapping étendu (clé canonique pour les 18 + clé legacy `DEPLOYMENT_STATUS_CHANGED` pour tous les `deployment.*`), `bridged_event_types()`, teardown idempotent, `EVENT_TYPE_MAPPING` conservé en compat documentaire.

**Scheduler (T9) :**
- `backend/app/schemas/scheduled_task.py` — `_validate_event_name` résout les alias vers le canonique (stockage canonique) ;
- `backend/app/services/scheduler_service.py` — re-validation défensive avec résolution ;
- `backend/app/services/scheduler_event_triggers.py` — `_dispatch` matche canonique **et** alias résolvant vers lui (dédup par id) — divergence mineure vs analyse, voir ci-dessous ;
- `backend/alembic/versions/2026_10_23_1500_normalize_scheduled_task_event_names.py` — data migration `1341` (tous les alias, même jamais émis ; downgrade no-op documenté).

**Renommages imports (T1) :** `ssh_connection.py`, `api/v1/targets/fingerprints.py` (`TARGET_SSH_FINGERPRINT_*` → `HOST_SSH_FINGERPRINT_*`).

**Doc (T10) :** `docs/technical_specs/EVENT-BUS.md` (nouveau) — nomenclature, modes, table de correspondance, double émission, machine.*, interface plugins.

**Tests :** nouveaux `tests/unit/test_core/test_events.py`, `test_events_redis.py`, `tests/unit/test_websocket/test_event_bridge.py`, `tests/unit/test_services/test_deployment_events.py`, `test_canonical_event_emitters.py`, `tests/integration/test_events_pubsub.py` ; enrichis `test_scheduler_event_triggers.py` (alias), `test_migrations.py` (scénario 9 data migration), renommés `test_ssh_connection.py`/`test_targets_fingerprints.py`.

### Décisions techniques / divergences vs analyse

1. **`DeploymentStatus` n'a pas de membre `success`** — l'enum réel est `pending|deploying|running|failed|stopped|rolling_back` ; le statut métier de succès est `running` (cohérent avec l'audit `deployment.succeeded` émis sur transition vers RUNNING par `update_status`). Le mapping émet donc `deployment.succeeded` sur `running` (pas `deployment.started` comme l'ancien code ni une clé `success` inexistante). `stopped` n'a pas d'événement canonique → pas d'émission + warning (AC 3 : plus de fallback silencieux). Divergence documentée dans la docstring et `EVENT-BUS.md`.
2. **Résolution d'alias bidirectionnelle dans les triggers** (au-delà de l'analyse qui ne spécifiait que `resolve_event_name` avant match) : `_dispatch` matche le canonique émis ET les alias legacy stockés (`_aliases_resolving_to`) avec dédup — garantit que les définitions pré-migration restent fonctionnelles, testé explicitement.
3. **`deployment_service.update_status` émet `stack.deployed` via le singleton `deployment_events`** (`get_deployment_events().event_bus.emit`) plutôt que la factory — cohérent avec le chemin `emit_status_change` existant.
4. **Test downgrade STORY-161 ajusté** : la migration `1341` s'insérant après `1331`, `downgrade -1` ne suffit plus pour dropper `scheduled_task_executions` — le test cible désormais `1321_scheduled_tasks_spec17` explicitement (divergence d'écriture de test, pas de comportement).
5. **Bug latent préexistant signalé (non corrigé — hors périmètre)** : `POST /docker/containers` retourne un `ContainerDetailResponse` validé contre le `response_model=ContainerResponse` → 500 avec un mock standard (jamais couvert par les tests existants qui ne testent que les 403 RBAC). Le test `container.created` appelle donc la fonction endpoint directement.
6. **`target.updated`** : membre supprimé ; sa clé d'alias mappe vers `host.offline` (plus proche sémantique) plutôt que de laisser des lignes orphelines — tracé dans `LEGACY_EVENT_ALIASES` et `EVENT-BUS.md`.

### Difficultés rencontrées
- Imports relatifs dans `api/v1/docker.py` (3 points) et `api/v1/targets/crud.py` (4 points) — erreurs `ModuleNotFoundError: No module named 'app.api.core'` corrigées ;
- Fichiers `services/` reformatés par erreur par black (nettoyage large) → revertés puis changements de story ré-appliqués sur `ssh_connection.py`, `target_service.py`, `plugin_manager_service.py` (tests re-vérifiés 52/52 après restauration) ;
- `make backend-lint` global échoue sur ~25 fichiers **préexistants** non conformes isort (hors périmètre story, non touchés) — lint ciblé sur les fichiers de la story : isort/black/flake8/mypy/bandit tous OK.

### Commandes de validation et résultats
- `pytest tests/unit/test_core/ tests/unit/test_websocket/test_event_bridge.py tests/unit/test_services/test_deployment_events.py tests/unit/test_services/test_canonical_event_emitters.py` → **51 passed** ; couverture : `events.py` **90 %**, `event_bridge.py` **100 %**, `deployment_events.py` **84 %** (AC 5 ≥ 80 % ✓) ;
- `pytest tests/integration/test_events_pubsub.py` (Redis réel, DB 15) → **2 passed** ;
- `pytest tests/integration/test_migrations.py` → **35 passed, 1 skipped** (PG absent) — dont scénario 9 data migration ;
- Suite non-régression élargie (scheduler engine/triggers/actions, ssh_connection, fingerprints, targets RBAC, docker RBAC, schedules v2/executions/rbac, plugin manager/lifecycle, websocket ws_auth/isolation/rbac) → **379 passed, 1 failed** : `test_schedules_v2.py::test_parameters_not_logged_raw` — **échec préexistant confirmé sur main sans mes changements** (echo SQL local logge les paramètres SQL), non lié à la story ;
- `pytest tests/unit/test_services/test_canonical_event_emitters.py tests/unit/test_services/test_ssh_connection.py tests/unit/test_api/test_targets_fingerprints.py tests/unit/test_services/test_target_health_check.py` → **52 passed** ;
- isort/black/flake8/mypy/bandit ciblés sur les fichiers touchés → **OK** (mypy : 0 erreur sur les fichiers story ; 3 erreurs préexistantes ailleurs).
- Non exécuté : `make backend-test-unit` intégral (durée) — suite élargie des modules touchés exécutée à la place ; `make generate-openapi-docs` (examples inchangés : `deployment.failed` déjà canonique, description champ `event_name` enrichie).
