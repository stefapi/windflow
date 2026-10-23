# STORY-160 : [ABANDONED] Moteur d'exécution du scheduler — boucle asyncio, registre d'actions, triggers cron/événement, verrous et fuseaux IANA (P2-1, partie moteur)

**Statut :** ABANDONED
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-1 (axe A8, rapport §12) — ampleur **XL** (prévoir sous-découpe possible, plage réservée STORY-175-199)

> **Note de clôture — découpe `split-story` (2026-10-21, mode proactif)** : cette story a été **découpée à l'issue de la phase d'analyse** (`analyse-story`), qui a conclu à une **complexité excessive** (ampleur XL confirmée : ~13 tâches hétérogènes estimées sur **4 domaines peu couplés** — modèle/API, moteur runtime, actions core, triggers événement ; verdict §Contexte technique ci-dessous). Conformément au pipeline (règles 01 §5.1, étape 2b), elle est refermée `ABANDONED` selon le pattern STORY-131 (Règle d'Or : fichier conservé pour l'historique) et **remplacée sans perte d'information** par 3 sous-stories autonomes, prêtes pour `treat-story` :
>
> - [STORY-160.1](STORY-160.1-modele-registre-actions-api-schedules.md) — Modèle ScheduledTask spec 17, registre d'actions et API `/schedules` v2 (couvre AC 2 partie définition + AC 5)
> - [STORY-160.2](STORY-160.2-moteur-runtime-asyncio.md) — Moteur runtime asyncio : boucle lifespan, verrous, timeout, orphelins, fuseaux IANA, contrat `ExecutionStore` (couvre AC 1, 3, 4 + AC 5 partie moteur)
> - [STORY-160.3](STORY-160.3-actions-core-triggers-evenement.md) — Actions core réelles et triggers événement (couvre AC 2 partie exécution)
>
> Le contexte technique, les dépendances, les risques et les familles de tests documentés ci-dessous ont été **intégralement répartis** dans ces sous-stories — **se reporter à elles pour le détail d'implémentation** (tâches ordonnées, tests à écrire) et pour toute exécution.

## Description

En tant qu'administrateur WindFlow, je veux que les tâches planifiées (`scheduled_tasks`) soient **réellement exécutées** par un moteur asyncio d'évaluation des crons (croniter) — avec registre d'actions, déclencheurs cron **et** événement, verrous anti-chevauchement, relecture défensive des définitions, récupération des orphelins et fuseaux IANA — afin que la planification ne soit plus un simple CRUD de définitions sans effet ([`scheduler_service.py`](../../backend/app/services/scheduler_service.py:20)) et que l'automatisation core promise par la spec 17 fonctionne.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §5, §9) : [`scheduler_service.py`](../../backend/app/services/scheduler_service.py:20) ne fait que du CRUD sur `ScheduledTask` ; aucun moteur n'évalue les expressions cron, rien n'exécute les tâches, la table `scheduled_task_executions` n'existe pas. L'arbitrage F1 (validé, STORY-130.2) ayant purgé Celery, le runtime d'exécution est **asyncio dans le processus API** — conformément à la contrepartie assumée du plan (§3 F1 : « les tâches longues tournent dans le processus API → à isoler via le scheduler engine »).

## Contexte technique

> **Analyse `analyse-story` (2026-10-21)** — fondée sur le code réel du dépôt (fichiers/lignes cités). Aucun code modifié.

### ⚠️ Verdict d'analyse : complexité excessive → découpe `split-story` requise

La story est **XL confirmée** au-delà du seuil de découpe (~8-10 tâches hétérogènes) : le périmètre cumule **4 domaines peu couplés** — (1) évolution du modèle `ScheduledTask` + API `/schedules` (divergence majeure avec la spec 17, migration Alembic d'évolution), (2) moteur runtime asyncio (boucle/verrous/timeout/orphelins/fuseaux), (3) actions core réelles (`host.scan`, `compute.docker.prune`…), (4) triggers événement (bus) — soit **~13 tâches hétérogènes** estimées, avec des dépendances croisées (STORY-161/162/173, P2-15). Conformément au pipeline (règles 01 §5.1, étape 2b), l'analyse **délègue à `split-story`** : les tâches détaillées et tests ne sont PAS rédigés au niveau de la mère — proposition de découpe en § Sous-stories ci-dessous (3 sous-stories autonomes, suffixes `.1/.2/.3` comme STORY-131, ou plage réservée 175-199 à discrétion du split).

### Patterns existants à réutiliser (directs)

- **Boucles asyncio au lifespan** : 3 boucles existantes à imiter — health check ([`main.py:158-169`](../../backend/app/main.py)), refresh token purge ([`main.py:186-198`](../../backend/app/main.py), STORY-123.4), audit purge ([`main.py:222-234`](../../backend/app/main.py), STORY-125.3) ; pattern shutdown `cancel()` + `await` + `CancelledError` ([`main.py:254-280`](../../backend/app/main.py)) ; session DB fraîche par itération via `AsyncSessionLocal`. Le moteur s'ajoute comme 4ᵉ tâche lifespan, **sans fusionner les boucles existantes** (AC 5).
- **Reprise au démarrage** : [`DeploymentOrchestrator.recover_pending_deployments()`](../../backend/app/services/deployment_orchestrator.py:316) appelé au lifespan ([`main.py:140`](../../backend/app/main.py)) — modèle direct pour la récupération des orphelins (`queued`/`running` → `failed`).
- **CRUD existant** : [`SchedulerService`](../../backend/app/services/scheduler_service.py:21) — `get_enabled_tasks()` ([`:165`](../../backend/app/services/scheduler_service.py)) déjà prévu pour le moteur ; `record_run()` ([`:148`](../../backend/app/services/scheduler_service.py)) persiste `last_run`/`last_status`/`last_error`/`run_count` sur la définition (complémentaire de STORY-161).
- **Router `/schedules`** : [`api/v1/schedules.py`](../../backend/app/api/v1/schedules.py) — CRUD paginé (`PaginatedResponse` + `PaginationQuery`/`build_meta`, STORY-128), RBAC `require_viewer`/`require_operator`/`require_admin` (STORY-122), exemples OpenAPI riches — à **non-régresser** (AC 5, tests existants [`test_schedules_rbac.py`](../../backend/tests/unit/test_api/test_schedules_rbac.py) + [`test_api_contract.py`](../../backend/tests/integration/test_api_contract.py)).
- **Parseur cron** : vendored [`helper/croniter.py`](../../backend/app/helper/croniter.py) (décision E3 : « ressusciter via A8 ») — ⚠️ il importe `dateutil.relativedelta`/`dateutil.tz` ([`croniter.py:15-16`](../../backend/app/helper/croniter.py)) alors que **`python-dateutil` n'est pas déclarée** dans `pyproject.toml` (seul `croniter` apparaît, en override mypy) → déclaration Poetry explicite requise à la consommation (rules 05 : dépendance justifiée par E3 ; à tracer en note d'implémentation).
- **Bus événementiel** : [`EventType`](../../backend/app/core/events.py:18) (~33 événements, nomenclature legacy `target.*`, `deployment.completed`…) + `EventBus.subscribe/emit` — point d'accroche des triggers événement ; STORY-162 fera migrer la nomenclature (période de double émission, risque §7.3).
- **Action `host.scan`** : [`TargetScannerService`](../../backend/app/services/target_scanner_service.py) — `scan_localhost()` ([`:90`](../../backend/app/services/target_scanner_service.py)), `scan_remote()` ([`:99`](../../backend/app/services/target_scanner_service.py), TOFU STRICT), `scan_and_update_target()` ([`:145`](../../backend/app/services/target_scanner_service.py)) directement consommables.
- **Action `compute.docker.prune`** : ⚠️ [`docker_client_service.py`](../../backend/app/services/docker_client_service.py) n'expose que `remove_image(force, no_prune)` ([`:1199`](../../backend/app/services/docker_client_service.py)) — **aucun wrapper** `images.prune()`/`volumes.prune()` : l'action exige soit de nouveaux wrappers (docker SDK), soit la consommation du prune protégé de STORY-173 (sémantique `windflow-plugin-*` épargnée, dry-run) — coordination à tracer.
- **Config** : pattern `Settings` + `Field(default=…, description/alias)` ([`config.py:54-56`](../../backend/app/config.py), [`:73-75`](../../backend/app/config.py)) pour les nouveaux settings (`scheduler_enabled`, tick, timeout défaut 10 min, fuseau global défaut UTC, politique d'erreur défaut, backoff 3).
- **Transversal** : exceptions [`WindFlowException`](../../backend/app/core/exceptions.py) → `APIError` ; audit [`AuditService.log`](../../backend/app/services/audit_service.py) (`_sanitize_details` masque `key`/`password`/`credential`) ; enveloppes [`schemas/common.py`](../../backend/app/schemas/common.py).

### Divergence modèle ↔ spec 17 (constat central, motivation de la découpe)

[`models/scheduled_task.py`](../../backend/app/models/scheduled_task.py) : enum `TaskType` **fermé** (`CLEANUP_LOGS`/`HEALTH_CHECK`/`GIT_SYNC`/`RETRY_DEPLOYMENTS`/`CUSTOM`, [`:21-28`](../../backend/app/models/scheduled_task.py)) et **aucune** colonne `trigger_type`/`event_name`/timezone/politique d'erreur — la spec 17 § Scheduler core exige une **action du registre** + trigger `cron`|`event` + politique d'erreur. De plus, la nomenclature des actions diverge **entre le plan P2-1** (`stack.backup`, `compute.docker.prune`, `admin.backup`) **et la spec 17** (`app.backup`, `compute.images.prune`/`compute.volumes.prune`, `admin.backup.create`…) → l'**arbitrage du registre canonique est un prérequis d'entrée** (alignement STORY-173 pour prune). La table n'est pas seedée ([`database_seed.py`](../../backend/app/database_seed.py) ne la touche pas) : la migration est une évolution de schéma + mapping défensif des 5 `task_type` legacy (table vraisemblablement vide), **pas** une data migration lourde.

`scheduled_task_executions` **n'existe pas** (STORY-161) : le moteur doit consommer un **contrat de persistance** (interface `ExecutionStore` : `mark_queued/running/success/failed/skipped`, journaux ligne à ligne) — implémentation DB livrée par STORY-161, implémentation mémoire pour l'isolation des tests du moteur (la story l'annonce déjà : « fonctionne en tests avec la table posée par 161 »).

### Contraintes runtime (arbitrage F1 — asyncio dans le processus API)

- **Mono-processus** : verrou anti-chevauchement = ensemble **en mémoire** des `task_id` en cours (limite multi-workers `--workers>1` à documenter ; single-worker par défaut) ; timeout via `asyncio.wait_for` (défaut 10 min configurable) sans tuer la boucle ; chaque exécution dans une tâche dédiée, jamais inline dans le tick.
- **Tick minute** : granularité cron = minute → tick ~30-60 s, relecture défensive (existence + `enabled`) à chaque échéance.
- **Fuseaux IANA** : évaluation via croniter + `zoneinfo` — fuseau global (settings, défaut UTC) ; **surcharge par Host résolue depuis les paramètres de la tâche** (`host_id`…) car `Target` n'a **pas** de colonne timezone ([`models/target.py`](../../backend/app/models/target.py)) — l'ajout de la colonne relève de STORY-166 (alignement à tracer, pas bloquant) ; réinscription à chaud = recalcul des prochaines échéances au tick suivant (pas de cache à invalidation complexe).
- **Observabilité** : logs structurés (task_id/action/statut/durée, jamais les `parameters` bruts), correlation ID propagé ; compteurs d'exécutions par statut posés en base (STORY-161) serviront STORY-172.
- **Secrets** : jamais dans les journaux d'exécution ni les logs (spec 17 § Bonnes pratiques ; masquage pattern `_sanitize_details`).

### Checklist sécurité (règle 40) — appliquée à l'analyse

- **AuthN/AuthZ** : endpoints CRUD `/schedules` restent `require_viewer`(lecture)/`require_admin`(écriture) (STORY-122) ; le moteur est un **runtime interne sans endpoint** — le déclenchement manuel (`triggered_by=manual`) est renvoyé à STORY-161 ; exécution des actions **sans contexte utilisateur** (système) → actions destructrices (`prune`) réservées à des définitions créées par Admin (RBAC à la création, verrouillé par le registre).
- **Validation & injection** : expression cron validée via croniter à l'API (422) ; fuseau via `zoneinfo` (`ZoneInfoNotFoundError` → 422) ; `action` restreinte au registre (sinon exécution `failed` « action inconnue », AC 2) ; `event_name` restreint à la liste canonique ; `parameters` validés par **schéma Pydantic par action** (registre) — jamais d'exécution shell/SSH avec paramètres non validés.
- **Données sensibles** : réponses `/schedules` sans champ sensible ; journaux d'exécution sans secrets (masquage) ; `last_error` tronqué/assaini.
- **Audit & traçabilité** : exécutions matérialisées (STORY-161) ; audit des créations/modifications/suppressions de tâches (pattern existant à compléter) ; événements système émis pour échecs répétés (renvoi alerte 3 échecs → STORY-161/P2-15).

Éléments existants à réutiliser / contraintes :
- **Runtime asyncio assumé** (F1) : boucle dans le lifespan [`main.py:59`](../../backend/app/main.py) — s'inspirer de la boucle de santé `_periodic_health_check()` ([`main.py:134`](../../backend/app/main.py)) et du pattern de reprise `DeploymentOrchestrator.recover_pending_deployments()` (§2.G, à conserver) ;
- **Parseur cron** : consommer le vendored [`helper/croniter.py`](../../backend/app/helper/croniter.py) (décision E3 : « ressusciter via A8, seul consommateur crédible ») — sa consommation conditionne la purge P3-1 ;
- **Registre d'actions** (spec 17 § Actions core) : actions core à enregistrer — `stack.backup`, `compute.docker.prune` (le plan cite `compute.images.prune`/`compute.volumes.prune`, alignables sur STORY-173), `host.scan`, `admin.backup` (prépare F8), `notification.send` (implémentation réelle via la story P2-15/notifications — cf. EPIC-013) ; les actions non implémentables à ce stade sont enregistrées en stub **explicite** ;
- **Triggers** : cron **et** événement — le trigger événement s'abonne aux événements canoniques du bus (STORY-162) ; si STORY-162 n'est pas encore fusionnée, brancher sur l'enum `EventType` existant avec période de double émission (risque §7.3) ;
- **Verrou anti-chevauchement** : si l'exécution précédente tourne encore → nouvelle exécution `skipped` (jamais empilée), tracée ;
- **Relecture défensive** : à chaque tick, relire la définition en base (existence + `enabled`) avant tout déclenchement ;
- **Récupération des orphelins** : au démarrage, les exécutions `queued`/`running` sont marquées `failed` (« interrompue — le scheduler a été redémarré pendant l'exécution ») ;
- **Fuseaux IANA** : fuseau global (défaut UTC) + surcharge par Host + réinscription à chaud sans redémarrage ;
- **Timeout** : chaque exécution a un timeout configurable (défaut 10 min) ; politique d'erreur ignorer/réessayer backoff (défaut 3)/désactiver ;
- La persistance des exécutions (`scheduled_task_executions`) est portée par **STORY-161** — cette story définit le contrat de persistance (interface/service) et fonctionne en tests avec la table posée par 161 ;
- Chaîne critique du plan : scheduler engine (160) → purge croniter (P3-1).

## Critères d'acceptation (AC)

- [ ] AC 1 : Une boucle asyncio démarre au lifespan et exécute les tâches cron à l'heure — test par time travel/monkeypatch : une tâche `cron_expression="* * * * *"` (toutes les minutes) est déclenchée à chaque échéance ; une tâche désactivée (`enabled=false`) ou supprimée entre deux ticks n'est **jamais** exécutée (relecture défensive).
- [ ] AC 2 : Registre d'actions core en place (`stack.backup`, `compute.docker.prune` (images/volumes), `host.scan`, `admin.backup`, `notification.send`) avec paramètres validés par schéma ; une action inconnue dans une définition → exécution `failed` avec erreur explicite ; les triggers **événement** déclenchent l'action avec les données de l'événement en paramètres additionnels (ex. `deployment.failed` → `notification.send`).
- [ ] AC 3 : Verrou anti-chevauchement : 2 déclenchements simultanés de la même tâche → **1 seule exécution**, la seconde est tracée `skipped` ; timeout d'exécution configurable (défaut 10 min) → au-delà, la tâche est `failed` sans tuer la boucle ; politique d'erreur (ignorer / retry backoff 3 / désactiver) appliquée.
- [ ] AC 4 : Au démarrage du scheduler, toute exécution restée `queued`/`running` est marquée `failed` avec la raison « interrompue — le scheduler a été redémarré pendant l'exécution » (test : simulation de lignes orphelines en base) ; les fuseaux IANA sont respectés — test : cron `0 2 * * 0` avec fuseau `Europe/Paris` déclenche à 2 h heure locale (pas à un décalage UTC implicite), la modification d'un fuseau réinscrit les tâches sans redémarrage.
- [ ] AC 5 : Non-régression : la boucle de santé existante et `recover_pending_deployments()` au startup ne sont pas cassés ; endpoints `/schedules` existants non régressés ; couverture ≥ 80 % sur les nouveaux modules ; build + lint + tests passent.

## Références spécification

- [`17-automatisation-workflows.md`](../../docs/general_specs/17-automatisation-workflows.md) — **§ Scheduler core** (modèle, registre d'actions, triggers), **§ Exécutions : traçabilité, verrous et fuseaux** (verrou `skipped`, relecture défensive, orphelins, IANA global/par Host/réinscription à chaud, journaux horodatés), **§ Bonnes pratiques** (idempotence, timeout 10 min, secrets jamais dans les logs) ;
- [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités d'automatisation (`ScheduledTaskExecution` : statuts `queued/running/success/failed/skipped`, `triggered_by`, sémantique de récupération après crash) ;
- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § Bus d'événements internes (triggers événement), § Tâches async (runtime, arbitration F1) ;
- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Liste canonique des événements (nomenclature des triggers) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-1, §2.A A8, §2.E E3 (croniter), §3 F1 (asyncio, contrepartie), §5 chaîne critique n°3 ;
- [`backend_status.md`](../../docs/backend_status.md) — §5 (`scheduler_service.py` CRUD seul), §2.2 (lifespan), §9.1 (runtime réel asyncio).

## Dépendances

> Complété par l'analyse (2026-10-21) — statuts vérifiés dans le dépôt.

- **STORY-120** (Alembic) — **faite ✅** (migrations opérationnelles jusqu'à [`2026_10_16_1311_ssh_keys_and_fingerprints.py`](../../backend/alembic/versions/2026_10_16_1311_ssh_keys_and_fingerprints.py)) : la migration d'évolution `scheduled_tasks` (sous-story modèle) et celle de `scheduled_task_executions` (STORY-161) passent par Alembic.
- **STORIES 122/126/128** (RBAC, enveloppes, pagination) — **faites ✅** : consommées directement par l'API `/schedules` v2.
- **STORY-161** (persistance des exécutions) — couplage fort : le moteur définit le **contrat `ExecutionStore`** (interface) et tourne en tests sur store mémoire ; l'impl DB + endpoints de consultation/rétention + rétention sont portés par 161 (analyse conjointe des sous-stories recommandée).
- **STORY-162** (nomenclature canonique du bus) — le trigger événement se branche sur l'`EventType` legacy avec **période de double émission** tant que 162 n'est pas fusionnée (risque §7.3).
- **STORY-173** (prune protégé `/compute`) — l'action `compute.docker.prune` doit s'aligner sur sa sémantique (liste `windflow-plugin-*` épargnée, dry-run, confirmation) : consommer son service si fusionné, sinon wrappers minimaux avec dry-run par défaut.
- **Story notifications P2-15** — `notification.send` enregistrée en **stub explicite** ; ⚠️ arbitrage EPIC-013 à **tracer avant finalisation** : matérialisation dans la plage réservée STORY-175-199 ou report vague suivante (recommandation : la laisser hors 160, stub documenté).
- **STORY-166** (entité Host) — la colonne timezone Host n'existe pas : surcharge fuseau portée par la définition de tâche à ce stade, alignement 166 à tracer.
- **Dépendance Python** : déclarer `python-dateutil` (Poetry) — prérequis du croniter vendored (justification E3, rules 05).
- **Conditionne** : **P3-1** (purge croniter, STORY-250/EPIC-014 — chaîne critique n°3 du plan §5) et partiellement STORY-172 (métriques scheduler par statut via 161).

## Sous-stories

> **Découpe exécutée le 2026-10-21** (`split-story` proactif, suffixes `.1/.2/.3` — pattern STORY-131) — la proposition d'analyse ci-dessous a été reprise **intégralement** dans 3 fichiers autonomes de `.backlog/stories/` :

- [ ] [STORY-160.1](STORY-160.1-modele-registre-actions-api-schedules.md) — **Modèle spec 17, registre d'actions et API `/schedules` v2** (M-L) : évolution de [`ScheduledTask`](../../backend/app/models/scheduled_task.py) (`action` du registre remplaçant l'enum fermé, `trigger_type` `cron|event`, `event_name`, `timezone` IANA, politique d'erreur) + migration Alembic avec mapping défensif des 5 `task_type` legacy + **registre d'actions** (nomenclature canonique arbitrée d'entrée — alignement plan P2-1 ↔ spec 17 ↔ STORY-173 ; schéma Pydantic de paramètres par action ; stubs explicites documentés pour `stack.backup`/`admin.backup`/`notification.send`) + schémas Create/Update/Response avec validation (croniter, `zoneinfo`, action du registre, événement canonique) + endpoints `/schedules` **non régressés** (RBAC/enveloppes/pagination, tests 401/403/422/404 existants étendus). Couvre AC 2 (partie définition/registre) et AC 5.
- [ ] [STORY-160.2](STORY-160.2-moteur-runtime-asyncio.md) — **Moteur runtime asyncio** (M) : boucle lifespan (pattern des 3 boucles existantes), évaluation cron via **croniter vendored** (+ déclaration `python-dateutil` portée par 160.1), verrou anti-chevauchement en mémoire (exécution `skipped` tracée), timeout configurable (`asyncio.wait_for`, défaut 10 min), politique d'erreur ignorer/retry backoff 3/désactiver, relecture défensive à chaque tick, **récupération des orphelins** au démarrage (`queued`/`running` → `failed`, pattern `recover_pending_deployments`), fuseaux IANA (global défaut UTC + surcharge par paramètres de tâche, réinscription à chaud), **contrat `ExecutionStore`** (interface + impl mémoire pour tests, impl DB = STORY-161), settings dédiés, logs structurés sans secrets. Couvre AC 1, AC 3, AC 4, AC 5 (time travel/monkeypatch).
- [ ] [STORY-160.3](STORY-160.3-actions-core-triggers-evenement.md) — **Actions core réelles et triggers événement** (M) : implémentation `host.scan` (via [`TargetScannerService`](../../backend/app/services/target_scanner_service.py)), `compute.docker.prune` (wrappers docker SDK `images.prune`/`volumes.prune` ou consommation STORY-173 — dry-run par défaut, liste protégée `windflow-plugin-*`), stubs tracés `stack.backup`/`admin.backup` (renvoi F8/initiative backup) et `notification.send` (renvoi P2-15) ; **abonnement `EventBus`** pour les triggers événement (données de l'événement en paramètres additionnels, ex. `deployment.failed` → `notification.send` ; double nomenclature si 162 non fusionnée) ; tests avec mocks (aucun Docker/SSH/réseau réel). Couvre AC 2 (partie exécution/triggers événement).

## État d'avancement technique

*(non instancié à dessein — story XL : l'instanciation a été faite dans les sous-stories créées par `split-story` (section Sous-stories ci-dessus) ; la story mère est refermée `ABANDONED` selon le pattern STORY-131 — le suivi d'avancement vit dans STORY-160.1/.2/.3)*

## Tâches d'implémentation détaillées

*(non rédigées à dessein — complexité excessive constatée à l'analyse (story XL, ~13 tâches hétérogènes sur 4 domaines) : délégation à `split-story` conformément au pipeline (règles 01 §5.1, étape 2b). Les tâches détaillées seront rédigées dans les sous-stories 160.1/.2/.3 à partir du contexte technique ci-dessus.)*

## Tests à écrire

*(non rédigés à dessein — délégation à `split-story` (cf. Tâches d'implémentation détaillées). Familles directrices par sous-story, conformes aux règles 35/40 :*

- *160.1 (API) : validation 422 (cron invalide, fuseau IANA inconnu, action hors registre, `event_name` non canonique) ; 401/403 RBAC (viewer/admin) sur les champs nouveaux ; 404 ; non-régression `test_schedules_rbac.py`/`test_api_contract.py` ; mapping `task_type` legacy vérifié par migration.*
- *160.2 (moteur) : time travel/monkeypatch (cron `* * * * *` déclenché à chaque échéance ; `0 2 * * 0` + `Europe/Paris` → 2 h locale) ; désactivée/supprimée entre deux ticks jamais exécutée (relecture défensive) ; 2 déclenchements simultanés → 1 exécution + 1 `skipped` ; timeout → `failed` sans tuer la boucle ; politique d'erreur (retry backoff 3/désactiver) ; orphelins marqués `failed` au démarrage (store mémoire) ; logs sans secrets (caplog).*
- *160.3 (actions/triggers) : actions mockées (scanner/docker) — action inconnue → `failed` explicite ; `host.scan` appelle `scan_and_update_target` ; prune dry-run par défaut + liste protégée ; trigger événement `deployment.failed` → `notification.send` (stub) avec payload événement en paramètres ; échec d'action n'affecte pas la boucle.*
