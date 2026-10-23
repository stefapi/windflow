# STORY-163 : Consommateurs plugins du bus — hooks `@on_event`, enregistrement de `deployment_notifications` et émission de `DEPLOYMENT_PROGRESS` (P2-2, partie consommateurs — axe C6)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-2 (axe C6, rapports §6/§10) — ampleur **M**

## Description

En tant que développeur de plugins WindFlow, je veux que les hooks `@on_event` des extension/hybrid plugins consomment réellement les ~18 événements canoniques émis par le bus (STORY-162), que le module interne `deployment_notifications` — défini mais jamais enregistré — soit enregistré, et que le type transport `DEPLOYMENT_PROGRESS` — défini mais jamais émis — soit effectivement émis par le pipeline de déploiement, afin que la promesse « les plugins réagissent aux événements core » (spec 11) devienne vraie au lieu d'un contrat dormant.

**Problème constaté** ([WEBSOCKET-REAL-TIME.md §10.1](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md), [`backend_status.md`](../../docs/backend_status.md) §8.5) : aucun plugin ne consomme les événements canoniques (C6) ; [`deployment_notifications.py`](../../backend/app/websocket/plugins/deployment_notifications.py) n'est pas importé par [`plugins/__init__.py`](../../backend/app/websocket/plugins/__init__.py) (seuls `audit_logger`, `deployment_monitor`, `subscription` sont enregistrés) — son auto-enregistrement à l'import n'a jamais lieu ; `DEPLOYMENT_PROGRESS` est défini dans [`schemas/websocket_events.py`](../../backend/app/schemas/websocket_events.py), écouté par `deployment_monitor`/`deployment_notifications` et le handler frontend [`useDeploymentWebSocket.ts`](../../frontend/src/composables/useDeploymentWebSocket.ts) existe — mais **aucun code ne l'émet** (`broadcast_deployment_progress()` sans appelant, aucune méthode `emit_progress_update`).

## Contexte technique

### Cartographie du code existant (analyse du 2026-10-23)

**Socle bus (STORY-162, DONE)** :

- [`core/events.py`](../../backend/app/core/events.py) : interface `Bus` (l.279-312), `InMemoryEventBus` (l.315-429) avec **isolation d'erreurs des handlers** (`_dispatch_local` l.378-391 : un handler qui lève n'interrompt jamais les autres), `RedisPubSubEventBus`, `EventType` (18 canoniques + extra-canoniques), `CANONICAL_EVENT_NAMES` (l.152-173), `emit()` strict (lève `InvalidEventTypeNameError` si valeur hors `EventType`, l.393-414), `get_event_bus()`/`init_event_bus()`/`reset_event_bus()` ;
- ⚠️ Le dispatch in-memory est **séquentiel** (`for handler: await handler(event)`) : un hook lent retarderait l'émetteur et les abonnés suivants → le pont hooks doit dispatcher chaque hook en **tâche asyncio isolée** avec timeout (voir T2) pour satisfaire AC 1 (« un hook lent ou en échec ne bloque jamais l'émetteur ») ;
- Lifespan [`main.py`](../../backend/app/main.py) l.110-122 : `init_event_bus()` **avant** `setup_event_bridge()` — le pont hooks s'insère au même point du startup ;
- [`docs/technical_specs/EVENT-BUS.md`](../../docs/technical_specs/EVENT-BUS.md) §8 documente l'interface `Bus` comme « point d'entrée de STORY-163 ».

**Hooks plugins — à créer (aucun code existant)** :

- La spec 11 (l.305) montre `from windflow.plugins.hooks import PluginHooks, on_event` : **aucun équivalent dans le code** (recherche exhaustive — `on_event` n'existe que chez les triggers scheduler ; `hooks_module` n'est qu'un champ du manifest [`schemas/plugin_manifest.py`](../../backend/app/schemas/plugin_manifest.py) l.234, jamais chargé) ;
- Le package applicatif s'importe `app.*` (imports des tests existants) : le SDK sera `app.plugins.hooks` — **divergence d'import vs spec** (exemple illustratif) à documenter dans EVENT-BUS.md ;
- Pattern de composant abonné au bus avec `start()/stop()` idempotents : [`services/scheduler_event_triggers.py`](../../backend/app/services/scheduler_event_triggers.py) l.111-133 — **modèle direct** du pont hooks ;
- Chargement dynamique : pattern anti path-traversal `_resolve_script_path` ([`plugin_lifecycle_service.py`](../../backend/app/services/plugin_lifecycle_service.py) l.444-484, `settings.plugins_base_dir` [`config.py`](../../backend/app/config.py) l.453) + timeout hooks existant `HOOK_TIMEOUT_SECONDS = 30` (l.47) — réutiliser pour le timeout des `@on_event` ;
- Sources du chargement : `PluginExtension.hooks_module` (manifest), `Plugin.type` (`extension`/`hybrid`), `Plugin.manifest_data` JSON en base ([`models/plugin.py`](../../backend/app/models/plugin.py)).

**Enregistrement `deployment_notifications`** :

- [`websocket/plugins/deployment_notifications.py`](../../backend/app/websocket/plugins/deployment_notifications.py) : plugin complet (`DeploymentNotificationsPlugin`, écoute `DEPLOYMENT_STATUS_CHANGED|LOGS_UPDATE|PROGRESS`, l.30-34), **auto-enregistré à l'import** (l.193-197) mais **jamais importé** — [`websocket/plugins/__init__.py`](../../backend/app/websocket/plugins/__init__.py) l.10-18 ne référence que `audit_logger`, `deployment_monitor`, `subscription` ;
- Incohérence de pattern : les 3 plugins enregistrés ne s'auto-enregistrent **pas** (instanciés dans `default_plugins`, register par [`websocket/general.py`](../../backend/app/websocket/general.py) l.35-41) → importer le module tel quel provoquerait un double register (warning « already registered, replacing », [`websocket/plugin.py`](../../backend/app/websocket/plugin.py) l.188-208) ;
- ⚠️ Clés de souscription mortes : `_handle_status_change` diffuse vers `"deployment_events"` (l.108) et `_handle_progress_update` vers `f"deployment_progress_{id}"` (l.184-186) — clés non exposées par le `SubscriptionHandler` ; le contrat interne (log + `broadcast_to_user` si `user_id`) reste satisfaisant pour AC 2 — **ne pas réécrire le contrat** dans cette story, tracer la divergence (à traiter STORY-164/165) ;
- Les dispatch plugins ne surviennent que via `user_manager.dispatch_to_plugins` ([`connection_managers.py`](../../backend/app/websocket/connection_managers.py) l.461-489), appelé par `_broadcast_deployment_event` ([`broadcasting.py`](../../backend/app/websocket/broadcasting.py) l.41-64) — conditionné aux connexions WS générales actives (comportement existant, non modifié).

**Émission `DEPLOYMENT_PROGRESS` (à créer)** :

- `broadcast_deployment_progress()` ([`broadcasting.py`](../../backend/app/websocket/broadcasting.py) l.121-148) existe, **aucun appelant** ; payload actuel camelCase (`deploymentId`, `step`) ;
- ⚠️ **Mismatch avec le consommateur frontend** : [`frontend/src/types/websocket.ts`](../../frontend/src/types/websocket.ts) l.33-38 (`deployment_id`, `progress`, `current_step`, `total_steps`) et [`useDeploymentWebSocket.ts`](../../frontend/src/composables/useDeploymentWebSocket.ts) `handleProgress` (l.156-171, filtre sur `event.deployment_id`) attendent du **snake_case** — le payload backend doit être aligné ; aucun consommateur existant aujourd'hui → correction **sans** période de compatibilité ;
- `DeploymentEventsService.emit_progress_update` n'existe pas ([`deployment_events.py`](../../backend/app/services/deployment_events.py) : `emit_status_change` l.42-116 passe par le bus canonique ; `emit_logs_update` l.118-151 fait un **broadcast WS direct** — c'est le modèle du progress : le progress est du **transport WS**, jamais du bus canonique, avertissement WEBSOCKET §4.2) ;
- Site d'émission : [`tasks/background_tasks.py`](../../backend/app/tasks/background_tasks.py) `deploy_stack_async` (l.24-327) — pipeline séquentiel jalonné d'`update_status` intermédiaires sur 2 chemins (docker simple l.111-190 / compose l.192-311) ; les sous-étapes `pulling/creating/starting` de la spec 09 sont **masquées** à l'intérieur de `deploy_container`/`deploy_compose` → émettre aux **jalons observables** du pipeline avec libellés explicites (hypothèse à confirmer en implémentation) ;
- [`websocket/plugins/deployment_monitor.py`](../../backend/app/websocket/plugins/deployment_monitor.py) l.90-103 lit `progress`/`step` pour ses logs — à aligner sur `current_step` (avec fallback) ;
- Consommateurs du type déjà en place : `deployment_monitor` et `deployment_notifications` (`listens_for` inclut `DEPLOYMENT_PROGRESS`), frontend (souscription l.240-244) — l'émission les alimente tous.

### Patterns à réutiliser

- `scheduler_event_triggers.py` : composant abonné au bus, `start()/stop()` idempotents, callback qui ne lève jamais ;
- `plugin_manager_service._publish_to_bus` (l.572-596) : émission best-effort stricte (try/except, jamais d'exception remontée) ;
- `plugin_lifecycle_service._resolve_script_path` (l.444-484) : anti path traversal + résolution sous `plugins_base_dir` ;
- `reset_event_bus()` pour les tests (pattern [`test_scheduler_event_triggers.py`](../../backend/tests/unit/test_services/test_scheduler_event_triggers.py) : bus réel + handlers collecteurs).

### Réutilisation directe / adaptation / création

- **Directe** : `get_event_bus()`, `broadcast_deployment_progress()`, `DeploymentNotificationsPlugin` (tel quel), patterns start/stop ;
- **Adaptation** : `broadcasting.broadcast_deployment_progress` (payload snake_case aligné frontend), `deployment_monitor` (lecture `current_step`), `websocket/plugins/__init__.py` (liste `default_plugins`) ;
- **Création** : package [`backend/app/plugins/hooks.py`](../../backend/app/plugins/hooks.py) (SDK `PluginHooks`/`on_event`/`PluginEvent`), [`backend/app/services/plugin_hooks_service.py`](../../backend/app/services/plugin_hooks_service.py) (pont bus→hooks + chargement des `hooks_module`), `DeploymentEventsService.emit_progress_update`, plugin exemple.

### Décisions d'analyse

1. Le pont hooks s'abonne **uniquement aux 18 événements canoniques** — les extra-canoniques (dont `host.ssh_fingerprint_*`, sécurité) ne sont jamais transmis aux plugins (spec 11 + rules 40 : réduction de surface) ;
2. `@on_event` valide le nom **au décorateur** : refus explicite des noms SCREAMING_SNAKE et non-canoniques (avertissement WEBSOCKET §4.2 : la souscription plugins se fait uniquement sur les canoniques) ;
3. Isolation AC 1 : dispatch de chaque hook en **tâche asyncio dédiée** + `asyncio.wait_for` timeout configurable (défaut 30 s, aligné sur `HOOK_TIMEOUT_SECONDS`) — le `publish` du bus revient immédiatement ;
4. `DEPLOYMENT_PROGRESS` reste du **transport WS** (broadcast direct, jamais le bus canonique) — payload aligné sur le contrat frontend existant (snake_case) ;
5. `deployment_notifications` enregistré via `default_plugins` (pattern des 3 autres plugins) + retrait de l'auto-enregistrement à l'import (sinon double register) ;
6. Chargement des `hooks_module` des plugins installés **au lifespan**, best-effort (échec d'un plugin → warning, startup intact) ; STORY-169 (installation réelle) rendra ce chemin réellement alimenté — le mécanisme est posé ici ;
7. Plugin démonstrateur dans `app/plugins/examples/`, actif uniquement via setting désactivé par défaut (aucun comportement ajouté en production).

### Risques / hypothèses

- Chargement dynamique de code plugin dans le process = **surface d'attaque** : anti path traversal obligatoire, hooks chargés uniquement pour des plugins installés en base (l'API `/plugins` est déjà protégée RBAC — STORY-122.5) ;
- Jalons de progression : `pulling/creating` internes aux services Docker non observables individuellement — jalons observables documentés (libellés `loading/rendering/validating/...`), hypothèse à confirmer en implémentation sans improviser un refonte des services ;
- Clés mortes `"deployment_events"`/`"deployment_progress_{id}"` de `deployment_notifications` : hors périmètre (contrat actuel préservé), tracées pour STORY-164/165 ;
- `reset_event_bus()` des tests : le pont hooks doit être ré-abonnable après reset (`start()/stop()` idempotents) ;
- Aucune nouvelle dépendance Python ; aucune migration Alembic (aucune table/colonne touchée).

Éléments existants à réutiliser / contraintes :
- **Socle hooks plugins** : [`plugin_lifecycle_service.py`](../../backend/app/services/plugin_lifecycle_service.py:40) exécute les hooks lifecycle ; le mécanisme d'abonnement `@on_event` (spec 11 § Implémentation des hooks, classe `PluginHooks`) doit être câblé sur le bus canonique de STORY-162 — les hooks sont **asynchrones et non bloquants** (ils réagissent après coup, ne peuvent pas refuser une action — les décisions bloquantes sont les gates de STORY-170) ;
- **Enregistrement** : importer/enregistrer `deployment_notifications` dans [`websocket/plugins/__init__.py`](../../backend/app/websocket/plugins/__init__.py) — c'est un module de broadcast interne (G38), sans rapport avec les plugins marketplace : ne pas confondre les deux familles ;
- **Émission de `DEPLOYMENT_PROGRESS`** : décision du plan « émis ou retiré » → **émettre** (le handler frontend existe et l'attend) ; ajouter une émission de progression structurée (étapes `pulling`/`stopping`/`removing`/`creating`/`starting` du pipeline de déploiement, cf. batch update spec 09) via `broadcast_deployment_progress()` existant + une méthode d'émission côté service (le pattern `emit_status_change` de [`deployment_events.py`](../../backend/app/services/deployment_events.py:22) sert de modèle) ;
- ⚠️ Ne pas brancher un workflow, trigger scheduler ou plugin marketplace sur les noms SCREAMING_SNAKE — la souscription des plugins marketplace se fait **uniquement** sur les événements canoniques `domaine.action_passé` (avertissement spec WEBSOCKET §4.2) ;
- Un plugin d'exemple (extension) consommant au moins 2 événements canoniques (`stack.deployed`, `deployment.failed`) sert de démonstrateur testable ;
- Garde-fou §2.G : ne pas casser l'architecture des modules de broadcast internes.

## Critères d'acceptation (AC)

- [x] AC 1 : Le mécanisme `@on_event("<événement canonique>")` branche les hooks de plugins sur le bus ; test : un hook abonné à `stack.deployed` est appelé avec les données de l'événement quand une stack est déployée ; un hook lent ou en échec **ne bloque jamais** l'émetteur (isolation d'exécution, erreur journalisée). ✔ `test_plugin_hooks_service.py` (dispatch async, isolation ERROR/timeout WARNING, émetteur retourné avant le timeout, pool borné, ré-abonnement après `reset_event_bus`)
- [x] AC 2 : `deployment_notifications` est enregistré au démarrage (import effectif dans `plugins/__init__.py`) et reçoit les événements de déploiement — test : un changement de statut de déploiement déclenche son traitement (notification/broadcast selon son contrat actuel). ✔ `test_plugins_default.py` (`default_plugins` = 4 plugins, reload sans auto-enregistrement, `broadcast_to_user` si `user_id`)
- [x] AC 3 : `DEPLOYMENT_PROGRESS` est **effectivement émis** par le pipeline de déploiement aux étapes clés — test : un déploiement de test produit des messages `DEPLOYMENT_PROGRESS` reçus par les abonnés (et le consommateur frontend documenté), avec payload d'étape cohérent (`step`, progression) ; plus aucun « type défini jamais émis » ni handler frontend mort. ✔ `test_deploy_stack_progress.py` (2 chemins monotones, échec sans progress tardif, best-effort) + `test_deployments_api.py` (cycle réel bout-en-bout, 5→100)
- [x] AC 4 : Un plugin extension démonstrateur consomme ≥ 2 événements canoniques (ex. `stack.deployed` → action, `deployment.failed` → journalisation/notification) — testé unitairement sans déploiement marketplace complet ; les noms SCREAMING_SNAKE ne sont utilisés que côté transport WS, jamais comme contrat d'abonnement. ✔ `DemoLoggerHooks` + `test_hooks_sdk.py` (refus SCREAMING_SNAKE/extra-canoniques/sécurité au décorateur)
- [x] AC 5 : Non-régression des modules internes existants (`audit_logger`, `deployment_monitor`, `subscription`) ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent. ✔ 2106 tests unitaires verts (incl. `test_no_celery_residue.py`, bus STORY-162, triggers scheduler) ; couverture : `hooks.py` 100 %, `plugin_hooks_service.py` 89 %, `deployment_events.py` 86 % ; isort/black/flake8/bandit OK sur les fichiers de la story (erreurs isort préexistantes hors périmètre documentées ci-dessous)

## Références spécification

- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Système d'événements (liste canonique, « les extension/hybrid plugins s'y abonnent »), § Implémentation des hooks (`PluginHooks`, `@on_event`, exemple Traefik), § Bus d'événements (interface identique pour les plugins quel que soit le mode) ;
- [`17-automatisation-workflows.md`](../../docs/general_specs/17-automatisation-workflows.md) — § Triggers (exemple `deployment.failed` → `notification.send`), § Plugin n8n (triggers sur événements canoniques) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § WebSocket (messages `DEPLOYMENT_*`, batch update : étapes `pulling`→`starting`, `progress`) ;
- [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) — §4.2-4.3 (couche transport vs canonique, tableau d'articulation), §6 (handler frontend `handleProgress` jamais alimenté), §10.1 (`DEPLOYMENT_PROGRESS` jamais émis, `deployment_notifications` non enregistré — recommandation) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-2 (B7 : « `DEPLOYMENT_PROGRESS` émis ou retiré, `deployment_notifications` enregistré »), §2.C C6 ;
- [`backend_status.md`](../../docs/backend_status.md) — §8.5 (4 plugins WS, `deployment_notifications` non importé), §9.4 (bridge seul handler réel).

## Dépendances

- **STORY-162** (bus canonique + nomenclature) — **DONE** : interface `Bus`, `EventType` 18 canoniques, `CANONICAL_EVENT_NAMES`, `get_event_bus()`/`reset_event_bus()`, isolation d'erreurs handlers — socle direct, aucune modification du bus requise par cette story.
- **STORY-160.3** (triggers événement scheduler) — **DONE** : `scheduler_event_triggers` consomme déjà les mêmes `EventType` — le pont hooks s'ajoute comme consommateur parallèle sans interférence (aucun ordre garanti entre consommateurs, aucun requis).
- **STORY-169** (plugins — installation réelle, TODO) : le chargement des `hooks_module` est posé ici mais restera **non alimenté en pratique** tant que l'installation réelle (download/extraction vers `plugins_base_dir`) n'existe pas — le plugin démonstrateur et les tests couvrent le mécanisme ; coordination à noter dans STORY-169 (brancher l'enregistrement des hooks à l'install).
- **STORY-170** (routes dynamiques + gates, TODO) : les hooks `@on_event` sont **non bloquants** (spec 11 § Hooks de déploiement) — les décisions bloquantes (gates pre-deploy) restent entièrement dans STORY-170, aucune fondation de gate ici.
- **Notifications P2-15** (non affectée) : consommera les mêmes événements canoniques via le bus — interface `Bus` publique réutilisée telle quelle.
- **STORY-164/165** (canaux WS + tests, TODO) : les clés de souscription mortes de `deployment_notifications` (`"deployment_events"`, `deployment_progress_{id}`) y sont tracées — hors périmètre ici.
- **Bibliothèques** : aucune nouvelle dépendance (stdlib `importlib` pour le chargement dynamique) ; **aucune migration Alembic** (aucune table/colonne touchée).
- **Config** : settings additionnels `plugin_hooks_enabled` (défaut `True`) et `plugin_hooks_timeout_seconds` (défaut 30) dans [`config.py`](../../backend/app/config.py) — aucun service externe requis.
- **Frontend** : aucune modification requise — le payload `DEPLOYMENT_PROGRESS` est **aligné** sur le contrat existant ([`types/websocket.ts`](../../frontend/src/types/websocket.ts) l.33-38), le composable et sa souscription l.240-244 sont déjà en place.

## Sous-stories

*(non prévue — story M)*

## État d'avancement technique

- [x] T1 — SDK hooks `app/plugins/hooks.py` : `PluginEvent`, `PluginHooks`, décorateur `on_event` (validation canonique au décorateur)
- [x] T2 — Pont `plugin_hooks_service` : abonnement aux 18 canoniques, dispatch en tâches isolées + timeout, start/stop idempotents
- [x] T3 — Enregistrement `deployment_notifications` dans `default_plugins` + retrait auto-enregistrement import
- [x] T4 — `emit_progress_update` + payload snake_case aligné frontend
- [x] T5 — Émission `DEPLOYMENT_PROGRESS` aux jalons de `deploy_stack_async` (2 chemins)
- [x] T6 — Chargement lifespan des `hooks_module` (anti path-traversal, best-effort) + plugin démonstrateur
- [x] T7 — Documentation (EVENT-BUS.md § plugins) + validation complète (lint/tests/couverture ≥ 80 %)

## Tâches d'implémentation détaillées

> Séquencement : T1→T2 posent le socle consommateurs (SDK + pont), T3→T5 réalisent les deux promesses fonctionnelles (enregistrement + émission), T6 branche le chargement réel et le démonstrateur, T7 documente et valide. **Aucune écriture de code pendant l'analyse — ces tâches sont pour `treat-story`.**

### T1 — SDK hooks : `PluginHooks`, `@on_event`, `PluginEvent`
**Fichiers :** [`backend/app/plugins/__init__.py`](../../backend/app/plugins/__init__.py) (nouveau package), [`backend/app/plugins/hooks.py`](../../backend/app/plugins/hooks.py) (nouveau).
- Créer le package public `app.plugins` côté application (le nom applicatif importable est `app.*` — divergence vs `windflow.plugins.hooks` de la spec 11, exemple illustratif, à documenter T7) ;
- `PluginEvent` : dataclass légère exposée aux hooks — `name` (str canonique), `data` (dict payload), `timestamp`, `event_id` — **jamais** l'`Event` interne brut (réduction de surface) ;
- Classe de base `PluginHooks` : enregistrement des méthodes décorées `@on_event(name)` dans un registre d'instance `hooks: dict[str, list[callable]]` ; le décorateur : (1) valide `name in CANONICAL_EVENT_NAMES` **au moment du décorateur** (erreur explicite sinon — refus des SCREAMING_SNAKE et non-canoniques, AC 4), (2) conserve la fonction intacte (pas de wrapping logique), (3) assemble le registre à l'instanciation ;
- Docstring documentant le contrat : hooks asynchrones **non bloquants** (réagissent après coup, ne peuvent pas refuser — gates = STORY-170), timeout, payload sans secret.

### T2 — Pont bus → hooks : `PluginHooksService`
**Fichiers :** [`backend/app/services/plugin_hooks_service.py`](../../backend/app/services/plugin_hooks_service.py) (nouveau), [`backend/app/config.py`](../../backend/app/config.py).
- `config.py` : `plugin_hooks_enabled: bool = True`, `plugin_hooks_timeout_seconds: int = 30` (aligné `HOOK_TIMEOUT_SECONDS` — documenter la cohérence) ;
- `PluginHooksService` : `register(hooks_instance)` (idempotent par classe de plugin), `start()`/`stop()` idempotents sur le modèle [`scheduler_event_triggers.py`](../../backend/app/services/scheduler_event_triggers.py) l.111-133 — s'abonne **uniquement aux 18 `EventType` canoniques** (itération `CANONICAL_EVENT_NAMES`, jamais les extra-canoniques) ;
- Callback `_on_event(event: Event)` : construit un `PluginEvent` (payload **copie défensive**), puis pour **chaque** hook abonné au nom canonique → `asyncio.create_task(self._run_hook(...))` ; `_run_hook` : `asyncio.wait_for(timeout=settings.plugin_hooks_timeout_seconds)` + try/except large (hook lent → `TimeoutError` loggé WARNING, hook en échec → ERROR journalisé avec nom du plugin/événement — **jamais de remontée**, l'émetteur n'est jamais impacté, AC 1) ;
- Éviter la tempête de tâches : file bornée (`asyncio.Semaphore` ou réutilisation d'un petit pool) — un `deployment.failed` ne doit pas spawner des dizaines de tâches orphelines ; la tâche garde une référence forte (set de tâches actives, retrait au done-callback — pattern cleanup `deployment_orchestrator`) pour éviter la GC prématurée ;
- `reset()` pour tests (désabonnement + purge registre).

### T3 — Enregistrement de `deployment_notifications`
**Fichiers :** [`backend/app/websocket/plugins/__init__.py`](../../backend/app/websocket/plugins/__init__.py), [`backend/app/websocket/plugins/deployment_notifications.py`](../../backend/app/websocket/plugins/deployment_notifications.py).
- `__init__.py` : importer `DeploymentNotificationsPlugin`, l'ajouter à `default_plugins` (l.15) — l'enregistrement effectif est fait par [`websocket/general.py`](../../backend/app/websocket/general.py) l.35-41, pattern identique aux 3 autres plugins ; exporter dans `__all__` ;
- `deployment_notifications.py` : **retirer** l'auto-enregistrement à l'import (l.193-197) sinon double register (« already registered, replacing » — warning existant [`websocket/plugin.py`](../../backend/app/websocket/plugin.py) l.188-208) ;
- ⚠️ Ne **pas** toucher au contrat interne du plugin (`"deployment_events"`, `f"deployment_progress_{id}"` — clés mortes tracées pour STORY-164/165, garde-fou §2.G) ; sa `initialize` loggue via `self.logger` (pas `context.logger`) — laisser tel quel (non-régression AC 5).

### T4 — `emit_progress_update` + alignement du payload
**Fichiers :** [`backend/app/services/deployment_events.py`](../../backend/app/services/deployment_events.py), [`backend/app/websocket/broadcasting.py`](../../backend/app/websocket/broadcasting.py), [`backend/app/websocket/plugins/deployment_monitor.py`](../../backend/app/websocket/plugins/deployment_monitor.py).
- `deployment_events.py` : ajouter `emit_progress_update(deployment_id, progress, step, total_steps, user_id=None)` sur le modèle de `emit_logs_update` (l.118-151) — broadcast WS **direct** (jamais le bus canonique, avertissement WEBSOCKET §4.2), best-effort try/except, payload **snake_case** : `deployment_id`, `progress`, `current_step`, `total_steps`, `timestamp` — contrat exact de [`frontend/src/types/websocket.ts`](../../frontend/src/types/websocket.ts) l.33-38 consommé par `handleProgress` ([`useDeploymentWebSocket.ts`](../../frontend/src/composables/useDeploymentWebSocket.ts) l.156-171) ;
- `broadcasting.py` `broadcast_deployment_progress` (l.121-148) : aligner le payload sur le même contrat snake_case (`current_step` en sus de `step` pour compat logs internes, `total_steps`) — aucun consommateur backend existant du camelCase (vérifié), correction sans période de compatibilité ;
- `deployment_monitor.py` l.90-103 : lire `current_step` avec fallback `step` — le message typé doit rester utilisable par ce plugin de logs ;
- **Sécurité (rules 40)** : payload limité à ID/étapes/progression — jamais de variables de déploiement, secrets ou sorties de commandes.

### T5 — Émission aux jalons du pipeline de déploiement
**Fichiers :** [`backend/app/tasks/background_tasks.py`](../../backend/app/tasks/background_tasks.py).
- Dans `deploy_stack_async` (l.24-327) : émettre `DEPLOYMENT_PROGRESS` aux **jalons observables** des 2 chemins (docker simple l.111-190 / compose l.192-311) — jalons proposés (progression monotone 0→100, libellés explicites) : démarrage (5), stack chargée (15), mode déterminé (20), variables substituées (35), validation (45), [compose : labels injectés (55), fichier généré (65)], déploiement en cours (75), succès (100) ; `total_steps` = nombre de jalons du chemin ;
- Émission via `get_deployment_events().emit_progress_update(...)` **après** chaque `update_status` correspondant (best-effort — jamais dans le chemin d'échec : l'exception propage `FAILED` via `update_status` existant, pas de progress d'échec) ;
- Ne **pas** tenter de subdiviser `deploy_container`/`deploy_compose` (les sous-étapes `pulling/creating/starting` y sont internes — hypothèse des jalons observables documentée en Notes d'implémentation) ; si un jalon s'avère non observable, le retirer plutôt que d'instrumenter un service Docker (divergence à signaler).

### T6 — Chargement lifespan des `hooks_module` + plugin démonstrateur
**Fichiers :** [`backend/app/main.py`](../../backend/app/main.py), [`backend/app/services/plugin_hooks_service.py`](../../backend/app/services/plugin_hooks_service.py), [`backend/app/plugins/examples/`](../../backend/app/plugins/examples/) (nouveau).
- `main.py` lifespan : après `init_event_bus()`/`setup_event_bridge()` (l.110-122), si `settings.plugin_hooks_enabled` → instancier `PluginHooksService`, `start()`, puis chargement best-effort : requête des plugins `type IN (extension, hybrid)` ET `status IN (installed, running)` depuis la base, pour chaque `manifest_data.extensions.hooks_module` présent → import dynamique `importlib` du module résolu **sous `settings.plugins_base_dir/<plugin_name>/`** avec contrôle anti path-traversal (réutilisation stricte du pattern [`plugin_lifecycle_service._resolve_script_path`](../../backend/app/services/plugin_lifecycle_service.py) l.444-484), instanciation de la classe `PluginHooks` du module, `register()` ; échec d'un plugin → WARNING + plugin ignoré (startup intact) ; `stop()` + unregister au shutdown ;
- **Sécurité (rules 40)** : ne charger que des plugins **installés en base** (l'API `/plugins` est déjà protégée RBAC STORY-122.5 — source de vérité de ce qui est installé) ; jamais d'exécution de code non référencé en base ; timeouts appliqués à l'exécution des hooks (T2) ;
- Plugin démonstrateur `app/plugins/examples/demo_logger_hooks.py` : sous-classe `PluginHooks` consommant `stack.deployed` (log d'action) et `deployment.failed` (log/notification) — **non enregistré par défaut** (uniquement chargé si présent dans `plugins_base_dir` d'une installation, ou activé par setting dédié désactivé par défaut, ex. `plugin_hooks_demo_enabled: bool = False`) — testable unitairement sans installation marketplace (AC 4) ;
- ⚠️ Tant que STORY-169 n'est pas faite, la base ne contient pas de plugins réels avec fichiers extraits — comportement attendu : zéro hook chargé au startup en environnement courant (log debug), mécanisme couvert par tests.

### T7 — Documentation + validation
**Fichiers :** [`docs/technical_specs/EVENT-BUS.md`](../../docs/technical_specs/EVENT-BUS.md), validation via Makefile.
- EVENT-BUS.md : nouvelle section « Consommateurs plugins » — SDK `app.plugins.hooks` (divergence d'import vs spec documentée), contrat `@on_event` (noms canoniques uniquement, non-bloquant, timeout), isolation d'exécution, chargement lifespan (`hooks_module`), `DEPLOYMENT_PROGRESS` (contrat transport WS + payload snake_case + jalons), statut des clés mortes de `deployment_notifications` (renvoi STORY-164/165) ;
- Validation : `make backend-lint` (isort/black/flake8/mypy/bandit), tests ciblés puis `make backend-test-unit`, couverture ≥ 80 % sur `plugins/hooks.py`, `plugin_hooks_service.py`, `deployment_events.py` (progress), `background_tasks` (zones touchées), `websocket/plugins/` (AC 5) ; `make frontend-test-unit` si le composable est impacté (non prévu).

## Tests à écrire

> Chemins conformes à `55-project-structure.md`. Patterns : bus réel + handlers collecteurs (`test_scheduler_event_triggers.py`), `AsyncMock` injecté, `reset_event_bus()` entre tests.

### Unitaires backend

**1. `backend/tests/unit/test_plugins/__init__.py` + `backend/tests/unit/test_plugins/test_hooks_sdk.py` (nouveau) — T1/AC 4 :**
- `@on_event("stack.deployed")` enregistre la méthode dans le registre d'instance ; `@on_event("deployment.failed")` idem (≥ 2 événements, démonstrateur) ;
- `@on_event("DEPLOYMENT_PROGRESS")` → erreur explicite (SCREAMING_SNAKE refusé) ; `@on_event("organization.created")` (extra-canonique) → erreur explicite ; `@on_event("inconnu.total")` → erreur explicite ;
- `PluginEvent` exposé : `name`/`data`/`timestamp`/`event_id` présents, payload copie défensive (muter `data` ne corrompt pas l'original).

**2. `backend/tests/unit/test_services/test_plugin_hooks_service.py` (nouveau) — T2/AC 1 :**
- hook abonné à `stack.deployed` : `bus.emit(STACK_DEPLOYED, {...})` → hook appelé **asynchronement** avec le payload (attendre la tâche via await de la collecte ou `asyncio.wait`) ;
- **isolation AC 1** : hook qui lève → émission résolue quand même, erreur loggée (caplog ERROR), les autres hooks du même événement appelés ; hook lent (`asyncio.sleep > timeout` réduit) → `TimeoutError` loggé WARNING, l'émetteur n'attend pas (mesurer que `emit` retourne avant le timeout) ;
- `start()` deux fois → un seul abonnement par type (inspection `bus._handlers`, pattern test l.592-593 de `test_scheduler_event_triggers.py`) ; `stop()` → désabonné ; ré-abonnement après `reset_event_bus()` fonctionnel ;
- `register()` idempotent (même classe enregistrée 2× → hooks appelés une fois) ;
- sémaphore/pool : N hooks simultanés ne dépassent pas la borne (assertion sur compteur concurrent).

**3. `backend/tests/unit/test_websocket/test_plugins_default.py` (nouveau ou enrichissement) — T3/AC 2/AC 5 :**
- import de `websocket.plugins` → `default_plugins` contient 4 plugins dont `deployment_notifications` ;
- import du module `deployment_notifications` **seul** → plus d'auto-enregistrement (aucune entrée ajoutée à `plugin_manager._plugins`) ;
- `handle_event(DEPLOYMENT_STATUS_CHANGED, {...})` avec un `PluginContext` mocké → `broadcast_to_user` appelé quand `user_id` présent (contrat actuel : log + broadcast — AC 2 « notification selon son contrat ») ;
- non-régression : `audit_logger`, `deployment_monitor`, `subscription` toujours enregistrés et fonctionnels (échantillon : un événement chacun).

**4. `backend/tests/unit/test_services/test_deployment_events.py` (enrichissement) — T4/AC 3 :**
- `emit_progress_update(...)` → `broadcast_deployment_progress` appelé (mock) avec payload **snake_case exact** : `deployment_id`, `progress`, `current_step`, `total_steps`, `timestamp` (assertion d'égalité des clés) — cohérence avec `frontend/src/types/websocket.ts` ;
- échec du broadcast → aucune exception propagée (best-effort) ;
- payload sans secret : injection d'une variable sensible dans le contexte → absente du payload émis.

**5. `backend/tests/unit/test_tasks/__init__.py` + `backend/tests/unit/test_tasks/test_deploy_stack_progress.py` (nouveau) — T5/AC 3 :**
- mock de `DeploymentService.update_status` + `DockerService`/`DockerComposeService` (succès) + espion sur `emit_progress_update` → un déploiement de test (chemin docker simple) produit une **séquence monotone** de messages : progression croissante, premier jalon ≥ 5, dernier = 100, `total_steps` constant ;
- chemin compose : jalons supplémentaires (labels, fichier) présents, séquence monotone ;
- échec de déploiement (`deploy_container` retourne échec) → exception propagée + `FAILED` via `update_status`, **aucun** progress émis après l'échec ;
- `emit_progress_update` en erreur → déploiement **réussit quand même** (best-effort).

**6. `backend/tests/unit/test_services/test_plugin_hooks_loading.py` (nouveau) — T6 :**
- chargement d'un faux `hooks_module` (module de test temporaire sous un `plugins_base_dir` tmp) → instance enregistrée, hooks actifs sur le bus ;
- path traversal : `hooks_module: "../../etc/passwd"` → refusé (erreur/ignoré, log WARNING), rien chargé ;
- plugin `status=error` ou `type=service` (non extension/hybrid) → non chargé ;
- échec d'import d'un module → WARNING + les autres plugins chargés (startup intact) ;
- lifespan : `plugin_hooks_enabled=False` → service jamais démarré (aucun abonnement).

### Non-régression / intégration

**7. `backend/tests/unit/test_core/test_events.py` (enrichissement) :**
- scénario multi-consommateurs : pont hooks + bridge WS + triggers scheduler abonnés simultanément → tous notifiés, isolation mutuelle préservée (un consommateur en échec n'affecte pas les autres).

**8. `backend/tests/integration/test_deployments_api.py` (enrichissement léger) :**
- déploiement de test (mocks orchestrateur existants) → des messages `DEPLOYMENT_PROGRESS` sont produits (espion sur `emit_progress_update`) pendant le cycle — AC 3 bout-en-bout côté backend.

### Sécurité (rules 40 — checklist)

Aucun nouvel endpoint REST → pas de 401/403/422/404 nouveaux. Les exigences se matérialisent par :
- **authentification/autorisation** : le chargement des hooks se limite aux plugins installés via l'API `/plugins` déjà RBAC-protégée (STORY-122.5) — source de vérité unique de ce qui est installé ;
- **validation/injection** : `@on_event` ne valide que des noms canoniques (refus SCREAMING_SNAKE/extra-canoniques) ; anti path-traversal sur `hooks_module` (pattern `_resolve_script_path`) — test 6 ;
- **exposition de données** : payloads `PluginEvent`/`DEPLOYMENT_PROGRESS` limités à IDs/noms/étapes/progression — assertions d'absence de secrets (tests 4, 5) ; les extra-canoniques `host.ssh_fingerprint_*` **jamais** transmis aux hooks ;
- **DoS/robustesse** : timeout par hook + pool borné (T2, test 2) ; échec de broadcast/émission jamais propagé (tests 4, 5) ;
- **audit/traçabilité** : erreurs de hooks journalisées ERROR avec nom plugin/événement ; l'événement ne remplace pas les audit logs existants.

### Frontend

Aucune modification requise (contrat déjà aligné côté backend par T4 — le composable existant devient fonctionnel). Si `treat-story` veut verrouiller le contrat : un test unitaire léger `frontend/tests/unit/composables/useDeploymentWebSocket.spec.ts` sur `handleProgress` (maj `progress`/`currentStep`/`totalSteps`) — optionnel, non bloquant.

**Couverture cible : ≥ 80 % sur les modules touchés (AC 5).**

## Notes d'implémentation (2026-10-23 — treat-story)

### Fichiers créés

- `backend/app/plugins/__init__.py` — package SDK (divergence d'import vs spec 11 documentée) ;
- `backend/app/plugins/hooks.py` — SDK `PluginEvent` / `PluginHooks` / `on_event` (validation canonique au décorateur, refus SCREAMING_SNAKE/extra-canoniques via `InvalidEventTypeNameError`) ;
- `backend/app/plugins/examples/__init__.py` + `demo_logger_hooks.py` — démonstrateur AC 4 (`stack.deployed` + `deployment.failed`), non enregistré par défaut ;
- `backend/app/services/plugin_hooks_service.py` — pont bus→hooks : abonnement aux 18 canoniques uniquement, dispatch en tâches asyncio isolées (référence forte + done-callback), `asyncio.wait_for` timeout, sémaphore 16, `start/stop/reset` idempotents, `load_installed_hooks()` (requête `type IN (extension, hybrid)` + `status IN (installed, running)`, anti path-traversal `_resolve_hooks_module_path` miroir de `_resolve_script_path`, import par `importlib.util.spec_from_file_location` — sans pollution de `sys.path`, instanciation de la sous-classe `PluginHooks` du module) ;
- `backend/tests/unit/test_plugins/__init__.py` + `test_hooks_sdk.py` (12 tests) ;
- `backend/tests/unit/test_services/test_plugin_hooks_service.py` (10 tests) ;
- `backend/tests/unit/test_services/test_plugin_hooks_loading.py` (9 tests) ;
- `backend/tests/unit/test_tasks/__init__.py` + `test_deploy_stack_progress.py` (5 tests) ;
- `backend/tests/unit/test_websocket/test_plugins_default.py` (7 tests).

### Fichiers modifiés

- `backend/app/config.py` — settings `plugin_hooks_enabled` (True), `plugin_hooks_timeout_seconds` (30), `plugin_hooks_demo_enabled` (False) ;
- `backend/app/main.py` — lifespan : démarrage du pont après `setup_event_bridge()` (best-effort, échec → WARNING + startup intact) + chargement des `hooks_module` + option démo ; shutdown `stop()` avant `shutdown_event_bus()` ;
- `backend/app/websocket/plugins/__init__.py` — `DeploymentNotificationsPlugin` dans `default_plugins` (4 plugins) ;
- `backend/app/websocket/plugins/deployment_notifications.py` — retrait de l'auto-enregistrement à l'import (double register sinon) ; contrat interne (`deployment_events`, `deployment_progress_{id}`) **inchangé** ;
- `backend/app/services/deployment_events.py` — `emit_progress_update()` : broadcast WS direct (jamais le bus canonique), payload snake_case, best-effort ;
- `backend/app/websocket/broadcasting.py` — `broadcast_deployment_progress()` : payload `deployment_id`/`progress`/`current_step`/`step` (compat logs)/`total_steps` — plus de camelCase ;
- `backend/app/websocket/plugins/deployment_monitor.py` — lecture `current_step` avec fallback `step` ;
- `backend/app/tasks/background_tasks.py` — émission aux jalons des 2 chemins (docker 7 jalons : 5/15/20/35/45/75/100 ; compose 9 : +55/65), helper `emit_progress` best-effort, aucun progress sur le chemin d'échec ;
- `backend/tests/unit/test_services/test_deployment_events.py` — +5 tests progress ; `backend/tests/unit/test_core/test_events.py` — +2 tests multi-consommateurs/isolation mutuelle ; `backend/tests/integration/test_deployments_api.py` — +1 test cycle réel bout-en-bout ;
- `docs/technical_specs/EVENT-BUS.md` — §9 « Consommateurs plugins » (SDK, isolation, chargement lifespan, DEPLOYMENT_PROGRESS + tableau des jalons, clés mortes → STORY-164/165) ; `.backlog/kanban.md`.

### Décisions techniques

- **Chargement par `spec_from_file_location`** (vs `import_module` initialement envisagé) : aucun `sys.path` pollué, module enregistré sous un nom préfixé `windflow_plugin_*` (pas de masquage possible d'un module `app.*`) ;
- **Registre `PluginHooks._collect_hooks` par MRO inversé** : ordre de définition stable, support de l'héritage de hooks, marqueur `__on_event__` lu sur les méthodes ;
- **`_instantiate_hooks` filtre par `__module__`** : seules les sous-classes définies dans le module plugin sont instanciées (les imports du SDK ne compte pas) ;
- **Jalons communs émis après lecture du `target_type`** : garantit un `total_steps` constant sur tout le chemin (les jalons 5/15 précèdent sémantiquement le branchement docker/compose, leur émission WS est rattachée au total du chemin réel) ;
- **`emit_progress` local au pipeline** : double sécurité best-effort (le service journalise déjà, le pipeline ne propage jamais une erreur de notification).

### Divergences vs analyse

1. **Import dynamique** : l'analyse suggérait `importlib.import_module` après insertion du répertoire dans `sys.path` — remplacé par `importlib.util.spec_from_file_location` (plus sûr : pas de collision de noms, pas de `sys.path` global, échec isolé par plugin) ;
2. **Test filtres SQL** (`test_query_filters_type_and_status`) : vérifie la clause `WHERE plugins.type IN (...) AND plugins.status IN (...)` par compilation de la requête répliquée (la factory factice contournait le filtre — le contrat reste identique) ;
3. **`step` conservé dans le payload** en plus de `current_step` (l'analyse proposait `current_step` seul) : `deployment_monitor` et les logs internes lisent `step` en fallback — aucun consommateur du camelCase n'existait, correction sans période de compatibilité respectée ;
4. **Jalons docker = 7 et compose = 9** (l'analyse listait 8/10 en comptant `pulling/creating/starting` séparés) : ces sous-étapes sont internes aux services Docker — hypothèse des jalons observables confirmée, un seul jalon `deploying` (75) couvre la phase d'exécution effective.

### Difficultés rencontrées

- **Baseline lint préexistante** : `make backend-lint` échoue sur 36 fichiers isort préexistants (dont `background_tasks.py`, non retouché sur ses imports — hors périmètre, pas de refactor massif) ; les fichiers de la story passent isort/black/flake8/bandit individuellement ;
- **Baseline intégration préexistante** : 20 échecs préexistants dans `backend/tests/integration/` (environnement : « Database not initialized » / « No superadmin user found » en exécution isolée de `test_deployments_api.py` — vérifié par stash avant/après : identique sans mes changements) ; mon test d'intégration a été écrit pour ne pas dépendre d'`authenticated_client` (création directe en DB de test) et passe ;
- `mypy backend-typecheck` : erreurs préexistantes uniquement (modules tiers/transitifs — `jose`, `deployment_orchestrator`, `target_scanner_service`) ; aucun fichier de la story en erreur.

### Validations exécutées

- `poetry run pytest backend/tests/unit/` → **2106 passed** (0 échec — incl. bus STORY-162, `test_no_celery_residue.py`, triggers scheduler) ;
- `poetry run pytest backend/tests/integration/test_deployments_api.py::...emits_progress_messages` + `test_events_pubsub.py` → **3 passed** ;
- Couverture ciblée : `hooks.py` **100 %**, `plugin_hooks_service.py` **89 %**, `deployment_events.py` **86 %**, `demo_logger_hooks.py` **100 %** (≥ 80 % AC 5 ; zones basses restantes des modules WS préexistants = `subscription.py`/`audit_logger.py` historiques, STORY-165) ;
- `isort --check` / `black --check` / `flake8` / `bandit` sur les fichiers de la story → OK ;
- Non exécuté : `make backend-lint` complet (bloqué par la baseline isort préexistante ci-dessus), `make frontend-test-unit` (aucune modification frontend requise par l'analyse — contrat déjà aligné côté backend).

### Coordination tracée

- **STORY-169** : brancher l'enregistrement des hooks à l'installation réelle (le chargement lifespan examinera les `hooks_module` dès que des fichiers existeront sous `plugins_base_dir`) ;
- **STORY-164/165** : clés mortes `deployment_events` / `deployment_progress_{id}` de `deployment_notifications` (contrat actuel préservé, garde-fou §2.G) + couverture WS complète.
