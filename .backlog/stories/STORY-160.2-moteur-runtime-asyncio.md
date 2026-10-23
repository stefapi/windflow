# STORY-160.2 : Moteur runtime asyncio du scheduler — boucle lifespan, verrous, timeout, orphelins, fuseaux IANA et contrat ExecutionStore (P2-1, partie moteur)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-160 ([ABANDONED — découpe proactive post-analyse le 2026-10-21](STORY-160-moteur-scheduler-asyncio.md))
**Item plan :** P2-1 (axe A8, rapport §12) — ampleur **M**

> **Périmètre (découpe)** : cette sous-story reprend le **volet moteur runtime** de STORY-160 — boucle asyncio au lifespan (4ᵉ tâche lifespan, sans fusionner les 3 existantes), évaluation cron via croniter vendored, verrou anti-chevauchement en mémoire, timeout configurable, politique d'erreur, relecture défensive à chaque tick, récupération des orphelins au démarrage, fuseaux IANA (global + surcharge par tâche, réinscription à chaud) et **contrat `ExecutionStore`** (interface + implémentation mémoire pour l'isolation des tests). Couvre les AC 1, 3, 4 de la mère et son AC 5 (partie moteur/non-régression lifespan). Le volet définition (modèle/registre/API) est porté par [STORY-160.1](STORY-160.1-modele-registre-actions-api-schedules.md) (**pré-requis**) ; les actions réelles et triggers événement par [STORY-160.3](STORY-160.3-actions-core-triggers-evenement.md).

## Description

En tant qu'administrateur WindFlow, je veux que les tâches planifiées (`scheduled_tasks`) soient **réellement exécutées** par un moteur asyncio d'évaluation des crons (croniter vendored) — avec verrou anti-chevauchement, timeout, relecture défensive des définitions à chaque tick, récupération des orphelins au démarrage, politique d'erreur et fuseaux IANA — afin que la planification ne soit plus un simple CRUD de définitions sans effet ([`scheduler_service.py`](../../backend/app/services/scheduler_service.py:20)) et que l'automatisation core promise par la spec 17 fonctionne, conformément à l'arbitrage F1 (runtime asyncio dans le processus API, contrepartie assumée du plan §3).

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §5, §9) : [`scheduler_service.py`](../../backend/app/services/scheduler_service.py:20) ne fait que du CRUD ; aucun moteur n'évalue les expressions cron, rien n'exécute les tâches. L'arbitrage F1 (validé, STORY-130.2) ayant purgé Celery, le runtime est **asyncio dans le processus API** — « les tâches longues tournent dans le processus API → à isoler via le scheduler engine ».

## Contexte technique

> Extrait de l'analyse STORY-160 (2026-10-21, `analyse-story`) — volet moteur. Fondée sur le code réel du dépôt (fichiers/lignes cités). Aucun code modifié.

### Patterns existants à réutiliser (directs)

- **Boucles asyncio au lifespan** : 3 boucles existantes à imiter — health check ([`main.py:158-169`](../../backend/app/main.py)), refresh token purge ([`main.py:186-198`](../../backend/app/main.py), STORY-123.4), audit purge ([`main.py:222-234`](../../backend/app/main.py), STORY-125.3) ; pattern shutdown `cancel()` + `await` + `CancelledError` ([`main.py:254-280`](../../backend/app/main.py)) ; session DB fraîche par itération via `AsyncSessionLocal`. Le moteur s'ajoute comme **4ᵉ tâche lifespan, sans fusionner les boucles existantes** (garde-fou AC 5 de la mère).
- **Reprise au démarrage** : [`DeploymentOrchestrator.recover_pending_deployments()`](../../backend/app/services/deployment_orchestrator.py:316) appelé au lifespan ([`main.py:140`](../../backend/app/main.py)) — modèle direct pour la récupération des orphelins (`queued`/`running` → `failed` « interrompue — le scheduler a été redémarré pendant l'exécution »).
- **Définitions** : [`SchedulerService.get_enabled_tasks()`](../../backend/app/services/scheduler_service.py:165) déjà prévu pour le moteur ; `record_run()` ([`:148`](../../backend/app/services/scheduler_service.py)) persiste `last_run`/`last_status`/`last_error`/`run_count` sur la définition (complémentaire de STORY-161).
- **Parseur cron** : vendored [`helper/croniter.py`](../../backend/app/helper/croniter.py) (décision E3 : « ressusciter via A8, seul consommateur crédible » — sa consommation conditionne la purge P3-1) ; ⚠️ il importe `dateutil.relativedelta`/`dateutil.tz` ([`croniter.py:15-16`](../../backend/app/helper/croniter.py)) alors que `python-dateutil` n'est pas déclarée dans `pyproject.toml` — **la déclaration Poetry est portée par STORY-160.1 (tâche 2, pré-requis)**.
- **Config** : pattern `Settings` + `Field(default=…, description/alias)` ([`config.py:54-56`](../../backend/app/config.py), [`:73-75`](../../backend/app/config.py)) pour les nouveaux settings : `scheduler_enabled` (défaut à définir — activation au lifespan), `scheduler_tick_seconds` (~30-60 s, granularité cron = minute), `scheduler_task_timeout_seconds` (défaut 10 min), `scheduler_default_timezone` (défaut UTC), `scheduler_default_error_policy` (défaut), `scheduler_retry_backoff` (3).
- **Transversal** : exceptions [`WindFlowException`](../../backend/app/core/exceptions.py) ; logs structurés (task_id/action/statut/durée — **jamais les `parameters` bruts**), correlation ID propagé.

### Contraintes runtime (arbitrage F1 — asyncio dans le processus API)

- **Mono-processus** : verrou anti-chevauchement = ensemble **en mémoire** des `task_id` en cours (limite multi-workers `--workers>1` à **documenter** — single-worker par défaut) ; timeout via `asyncio.wait_for` (défaut 10 min configurable) **sans tuer la boucle** ; chaque exécution dans une **tâche dédiée**, jamais inline dans le tick.
- **Tick minute** : granularité cron = minute → tick ~30-60 s ; **relecture défensive** (existence + `enabled`) à chaque échéance — une tâche désactivée ou supprimée entre deux ticks n'est jamais exécutée.
- **Fuseaux IANA** : évaluation via croniter + `zoneinfo` — fuseau global (settings, défaut UTC) ; **surcharge par Host résolue depuis les paramètres de la tâche** (`host_id`…) car `Target` n'a **pas** de colonne timezone ([`models/target.py`](../../backend/app/models/target.py)) — l'ajout de la colonne relève de STORY-166 (alignement à tracer, non bloquant) ; **réinscription à chaud** = recalcul des prochaines échéances au tick suivant (pas de cache à invalidation complexe).
- **Contrat `ExecutionStore`** : `scheduled_task_executions` n'existe pas encore (STORY-161) — le moteur consomme une interface (`mark_queued/running/success/failed/skipped`, journaux ligne à ligne) ; **implémentation mémoire** pour l'isolation des tests du moteur ; l'implémentation DB est livrée par STORY-161 (« fonctionne en tests avec la table posée par 161 » — l'impl DB se branchera sur l'interface sans toucher au moteur).
- **Verrou anti-chevauchement** : si l'exécution précédente tourne encore → nouvelle exécution `skipped` (jamais empilée), tracée.
- **Politique d'erreur** : ignorer / réessayer avec backoff (défaut 3) / désactiver — appliquée à l'échec d'une exécution.
- **Observabilité** : logs structurés (task_id/action/statut/durée, jamais les `parameters` bruts), correlation ID propagé ; les compteurs d'exécutions par statut posés en base (STORY-161) serviront STORY-172.
- **Secrets** : jamais dans les journaux d'exécution ni les logs (spec 17 § Bonnes pratiques ; masquage pattern `_sanitize_details`).
- **Dispatch des actions** : le moteur résout l'action via le registre de 160.1 et invoque son handler ; une action **inconnue** dans une définition → exécution `failed` avec erreur explicite (AC 2 de la mère, partie moteur) ; les handlers **réels** ne sont livrés qu'en 160.3 — à ce stade le moteur s'appuie sur les handlers enregistrés au registre (stubs de 160.1 pour les actions non implémentées, comportement stub explicite tracé `failed`/`skipped` documenté).

### Risques hérités (de l'analyse mère, périmètre moteur)

- **`python-dateutil` non déclarée** (prérequis croniter vendored) — **déjà portée par STORY-160.1 (tâche 2)** : vérifier sa présence avant de merger le moteur (rules 05, justification E3).
- **Limite multi-workers `--workers>1`** : verrou en mémoire non partagé entre workers — à **documenter** explicitement (single-worker par défaut, arbitrage F1).
- **STORY-161 non fusionnée** : le moteur tourne sur l'implémentation mémoire du contrat `ExecutionStore` ; le branchement DB (161) ne doit pas nécessiter de refonte du moteur (couplage par interface uniquement — analyse conjointe recommandée).
- **Time travel en tests** : l'évaluation cron doit être testable par monkeypatch d'une horloge injectée (jamais `time.sleep` réel) — concevoir le moteur avec horloge/`now` injectables dès le départ.

### Checklist sécurité (règle 40) — volet moteur

- **AuthN/AuthZ** : le moteur est un **runtime interne sans endpoint** — aucune surface HTTP nouvelle ; le déclenchement manuel (`triggered_by=manual`) est renvoyé à STORY-161 ; exécution des actions **sans contexte utilisateur** (système) → actions destructrices (`prune`) réservées à des définitions créées par Admin (RBAC à la création, verrouillé par le registre de 160.1).
- **Validation & injection** : les définitions exécutées ont été validées à l'écriture par 160.1 (croniter, zoneinfo, action ∈ registre) ; le moteur **re-valide défensivement** action ∈ registre avant exécution (action inconnue → `failed` explicite) ; jamais d'exécution shell/SSH avec paramètres non validés.
- **Données sensibles** : journaux d'exécution sans secrets ; `last_error` tronqué/assaini ; logs sans `parameters` bruts.
- **Audit & traçabilité** : exécutions matérialisées via le contrat `ExecutionStore` (tracées au minimum en impl mémoire, persistées dès que 161 fournit l'impl DB) ; événements système émis pour échecs répétés (renvoi alerte 3 échecs → STORY-161/P2-15).

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend l'AC 1 de la mère)* : une boucle asyncio démarre au lifespan et exécute les tâches cron à l'heure — test par time travel/monkeypatch : une tâche `cron_expression="* * * * *"` (toutes les minutes) est déclenchée à chaque échéance ; une tâche désactivée (`enabled=false`) ou supprimée entre deux ticks n'est **jamais** exécutée (relecture défensive).
- [x] AC 2 *(reprend l'AC 3 de la mère)* : verrou anti-chevauchement — 2 déclenchements simultanés de la même tâche → **1 seule exécution**, la seconde est tracée `skipped` ; timeout d'exécution configurable (défaut 10 min) → au-delà, la tâche est `failed` **sans tuer la boucle** ; politique d'erreur (ignorer / retry backoff 3 / désactiver) appliquée.
- [x] AC 3 *(reprend l'AC 4 de la mère)* : au démarrage du scheduler, toute exécution restée `queued`/`running` est marquée `failed` avec la raison « interrompue — le scheduler a été redémarré pendant l'exécution » (test : simulation de lignes orphelines dans le store) ; fuseaux IANA respectés — test : cron `0 2 * * 0` avec fuseau `Europe/Paris` déclenche à 2 h heure locale (pas à un décalage UTC implicite) ; la modification d'un fuseau **réinscrit les tâches sans redémarrage** (recalcul au tick suivant).
- [x] AC 4 *(reprend la partie moteur de l'AC 5 de la mère)* : non-régression — la boucle de santé existante et `recover_pending_deployments()` au startup ne sont **pas cassés** (4ᵉ tâche lifespan, aucune fusion) ; couverture ≥ 80 % sur le nouveau module moteur ; build + lint + tests passent.

## Références spécification

- [`17-automatisation-workflows.md`](../../docs/general_specs/17-automatisation-workflows.md) — § Scheduler core (moteur, triggers), **§ Exécutions : traçabilité, verrous et fuseaux** (verrou `skipped`, relecture défensive, orphelins, IANA global/par Host/réinscription à chaud, journaux horodatés), § Bonnes pratiques (idempotence, timeout 10 min, secrets jamais dans les logs) ;
- [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités d'automatisation (`ScheduledTaskExecution` : statuts `queued/running/success/failed/skipped`, `triggered_by`, sémantique de récupération après crash) ;
- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § Tâches async (runtime, arbitrage F1) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-1, §2.E E3 (croniter), §3 F1 (asyncio, contrepartie), §5 chaîne critique n°3 ; [`backend_status.md`](../../docs/backend_status.md) §2.2 (lifespan), §5, §9.1.

## Dépendances

- **[STORY-160.1](STORY-160.1-modele-registre-actions-api-schedules.md) — pré-requis obligatoire** : modèle étendu (`trigger_type`, `timezone`, `error_policy`, `action`), registre d'actions (dispatch, validation défensive) et déclaration `python-dateutil` (tâche 2 de 160.1) doivent être fusionnés.
- **STORY-161** (persistance des exécutions) — couplage fort sans blocage : cette story définit le **contrat `ExecutionStore`** (interface) et tourne en tests sur l'implémentation mémoire ; l'impl DB + endpoints de consultation + rétention sont portés par 161 (analyse conjointe recommandée — le branchement DB de 161 ne doit pas modifier le moteur).
- **STORIES 122/126/128** — **faites ✅** (aucune surface HTTP nouvelle ici ; le moteur consomme les définitions validées).
- **STORY-130.2** — **faite ✅** (purge Celery : runtime asyncio unique assumé, arbitrage F1).
- **Story notifications P2-15 / STORY-161** : l'alerte « 3 échecs » est renvoyée à 161/P2-15 — le moteur se contente d'appliquer la politique d'erreur et d'émettre des événements système.
- **STORY-166** (entité Host) : pas de colonne timezone sur `Target` — surcharge fuseau portée par la définition de tâche à ce stade ; alignement à tracer, non bloquant.
- **Conditionne** : [STORY-160.3](STORY-160.3-actions-core-triggers-evenement.md) (les handlers réels s'enregistrent au registre et sont invoqués par ce moteur) ; **P3-1** (purge croniter, STORY-250/EPIC-014 — chaîne critique n°3 du plan §5) et partiellement STORY-172 (métriques scheduler par statut via 161).

## État d'avancement technique

*(cochage progressif pendant treat-story ; origine mère indiquée par tâche — volet moteur de l'analyse STORY-160)*

- [x] Tâche 1 — Contrat `ExecutionStore` (interface + implémentation mémoire)
- [x] Tâche 2 — Settings scheduler (`config.py`)
- [x] Tâche 3 — Moteur `SchedulerEngine` : tick, évaluation croniter, fuseaux IANA, horloge injectable
- [x] Tâche 4 — Verrou anti-chevauchement, tâche dédiée par exécution, timeout `asyncio.wait_for`
- [x] Tâche 5 — Politique d'erreur (ignore/retry backoff 3/disable) + `record_run` sur la définition
- [x] Tâche 6 — Récupération des orphelins au démarrage (pattern `recover_pending_deployments`)
- [x] Tâche 7 — Intégration lifespan `main.py` (4ᵏ tâche, shutdown propre, documentation multi-workers)
- [x] Tests — Moteur (time travel/monkeypatch) : déclenchement, défensive, verrou, timeout, politique, orphelins, fuseaux, logs sans secrets

## Tâches d'implémentation détaillées

> Séquence issue de l'analyse STORY-160 (volet moteur), renumérotée. Périmètre : runtime uniquement — aucune implémentation d'action réelle ni abonnement EventBus (160.3), aucune évolution du modèle/API (160.1).

### Tâche 1 : Contrat `ExecutionStore` (interface + implémentation mémoire)

**Objectif :** isoler le moteur de la persistance (STORY-161 livrera l'impl DB sur cette même interface).

**Fichiers :**
- `backend/app/services/scheduler_execution_store.py` — **Créer** : interface `ExecutionStore` (Protocol/ABC) — `mark_queued(task_id, triggered_by)`, `mark_running(execution_id)`, `mark_success(execution_id, duration)`, `mark_failed(execution_id, error)`, `mark_skipped(task_id, reason)`, `append_log(execution_id, line)` (journaux ligne à ligne horodatés), `recover_orphans()` (marque `queued`/`running` → `failed` « interrompue — le scheduler a été redémarré pendant l'exécution », sémantique spec 06) ; **implémentation mémoire** (`InMemoryExecutionStore`) pour l'isolation des tests et le fonctionnement pré-161 ; statuts `queued/running/success/failed/skipped` + `triggered_by` alignés spec 06.

**Dépend de :** Aucune (contrat autonome — alignement STORY-161 à tracer)

### Tâche 2 : Settings scheduler

**Objectif :** configurer le runtime (pattern `Settings` existant).

**Fichiers :**
- `backend/app/config.py` — **Modifier** : `scheduler_enabled: bool` (activation de la boucle au lifespan), `scheduler_tick_seconds: int` (~30-60 s), `scheduler_task_timeout_seconds: int = 600` (10 min), `scheduler_default_timezone: str = "UTC"`, `scheduler_default_error_policy: str = "retry"`, `scheduler_retry_backoff: int = 3` — `Field(default=…, description=…, alias=…)` pattern [`config.py:54-56`](../../backend/app/config.py)/[`73-75`](../../backend/app/config.py) ; validation `zoneinfo` du fuseau par défaut au chargement.

**Dépend de :** Aucune

### Tâche 3 : Moteur `SchedulerEngine` — tick, évaluation cron, fuseaux

**Objectif :** cœur du moteur : évaluation des échéances cron par fuseau, relecture défensive, dispatch via le registre.

**Fichiers :**
- `backend/app/services/scheduler_engine.py` — **Créer** : classe `SchedulerEngine` — boucle `run()` (tick configurable), **horloge injectable** (`now()` — testable time travel/monkeypatch, jamais `datetime.now()` en dur), évaluation via [`helper/croniter.py`](../../backend/app/helper/croniter.py) (croniter vendored, décision E3) + `zoneinfo` (fuseau global défaut UTC, **surcharge depuis les paramètres de la tâche** — `host_id`… — car `Target` n'a pas de colonne timezone, alignement STORY-166) ; **relecture défensive** à chaque échéance (relecture de la définition en base : existence + `enabled` avant tout déclenchement) ; résolution de l'action via le registre de 160.1 (`action_registry.get_action`) — **action inconnue → exécution `failed` avec erreur explicite** (jamais de KeyError brut, jamais d'exécution) ; session DB fraîche par itération via `AsyncSessionLocal` (pattern des boucles existantes) ; lecture via `SchedulerService.get_enabled_tasks()` ([`:165`](../../backend/app/services/scheduler_service.py)) ; **réinscription à chaud** : recalcul des prochaines échéances au tick suivant (pas de cache complexe à invalider).

**Dépend de :** Tâches 1-2, STORY-160.1 (registre + modèle + `python-dateutil`)

### Tâche 4 : Verrou anti-chevauchement + tâche dédiée + timeout

**Objectif :** garantir « 1 exécution à la fois par tâche » et borner chaque exécution sans tuer la boucle.

**Fichiers :**
- `backend/app/services/scheduler_engine.py` — **Modifier** (complément) : ensemble **en mémoire** des `task_id` en cours (verrou mono-processus — limite `--workers>1` documentée, single-worker par défaut) ; déclenchement simultané → seconde exécution **`skipped` tracée** (jamais empilée) ; chaque exécution dans une **tâche asyncio dédiée** (jamais inline dans le tick) ; timeout via `asyncio.wait_for(handler(...), timeout=scheduler_task_timeout_seconds)` → au-delà : `failed` + `asyncio.TimeoutError` capturé, **la boucle survit** ; `last_error` tronqué/assaini.

**Dépend de :** Tâche 3

### Tâche 5 : Politique d'erreur + `record_run`

**Objectif :** appliquer la politique d'erreur de la définition et refléter l'état sur la définition.

**Fichiers :**
- `backend/app/services/scheduler_engine.py` — **Modifier** (complément) : à l'échec — `ignore` (log + exécution `failed`), `retry` (nouvelles tentatives avec **backoff, défaut 3** — retentatives tracées, pas de tempête), `disable` (`enabled=false` sur la définition + log WARNING + événement système) ; après chaque exécution : [`SchedulerService.record_run()`](../../backend/app/services/scheduler_service.py:148) (last_run/last_status/last_error/run_count) ; émission d'événements système pour **échecs répétés** (matérialisation de l'alerte 3 échecs → STORY-161/P2-15).

**Dépend de :** Tâches 3-4

### Tâche 6 : Récupération des orphelins au démarrage

**Objectif :** reprise après crash/redémarrage (sémantique spec 06, pattern orchestrator).

**Fichiers :**
- `backend/app/services/scheduler_engine.py` — **Modifier** (complément) : au démarrage du moteur, `ExecutionStore.recover_orphans()` — toute exécution `queued`/`running` → `failed` avec la raison « interrompue — le scheduler a été redémarré pendant l'exécution » (modèle direct : [`DeploymentOrchestrator.recover_pending_deployments()`](../../backend/app/services/deployment_orchestrator.py:316)) ; logs structurés de la récupération.

**Dépend de :** Tâche 1 (contrat), Tâche 3

### Tâche 7 : Intégration lifespan `main.py`

**Objectif :** démarrer/arrêter le moteur comme 4ᵉ tâche lifespan, sans fusionner les boucles existantes (AC 4, garde-fou).

**Fichiers :**
- `backend/app/main.py` — **Modifier** : démarrage conditionné par `settings.scheduler_enabled` (pattern [`main.py:158-169`](../../backend/app/main.py) health check) ; **4ᵉ tâche lifespan** — ne pas fusionner les 3 boucles existantes ni toucher à [`recover_pending_deployments()`](../../backend/app/services/deployment_orchestrator.py:316) ([`main.py:140`](../../backend/app/main.py)) ; shutdown selon le pattern `cancel()` + `await` + `CancelledError` ([`main.py:254-280`](../../backend/app/main.py)) ; **documenter la limite multi-workers** (`--workers>1` : verrou mémoire non partagé — single-worker par défaut, arbitrage F1).

**Dépend de :** Tâches 3-6

## Tests à écrire

> Règles 35/40 : time travel/monkeypatch (jamais de sleep réel), `InMemoryExecutionStore` (aucune dépendance à la table 161), mocks des handlers (aucune action réelle — 160.3 couvrira les handlers). Familles issues de l'analyse mère (famille 160.2-moteur).

### Backend — unitaires

- `backend/tests/unit/test_services/test_scheduler_execution_store.py` : contrat mémoire — transitions `queued→running→success/failed/skipped` ; `recover_orphans()` marque `queued`/`running` → `failed` avec la raison exacte « interrompue — le scheduler a été redémarré pendant l'exécution » (simulation de lignes orphelines) ; `append_log` horodate ligne à ligne ; `triggered_by` tracé.
- `backend/tests/unit/test_services/test_scheduler_engine.py` (time travel/monkeypatch de l'horloge injectée) : cron `* * * * *` déclenché **à chaque échéance** (AC 1) ; tâche `enabled=false` ou **supprimée entre deux ticks jamais exécutée** (relecture défensive — AC 1) ; **2 déclenchements simultanés → 1 exécution + 1 `skipped` tracée** (AC 2) ; **timeout** (handler lent monkeypatché) → `failed` **sans tuer la boucle** (l'itération suivante s'exécute — AC 2) ; **politique d'erreur** : `ignore` (exécution suivante normale), `retry` (backoff 3 retentatives tracées), `disable` (définition passée `enabled=false` + événement) (AC 2) ; **orphelins** : au démarrage du moteur, lignes `queued`/`running` du store → `failed` raison exacte (AC 3) ; **fuseaux IANA** : cron `0 2 * * 0` + `Europe/Paris` déclenche à **2 h heure locale** (pas à un décalage UTC implicite) ; fuseau global UTC par défaut ; surcharge par paramètres de tâche (AC 3) ; **réinscription à chaud** : modification du fuseau/cron d'une définition prise en compte au tick suivant **sans redémarrage** (AC 3) ; **action inconnue** → exécution `failed` erreur explicite, boucle intacte ; exécution dans une tâche dédiée (jamais inline) ; `record_run()` appelé (last_status/run_count).
- **Logs sans secrets** (checklist règle 40) : caplog — aucun `parameters` brut dans les logs du moteur ; `last_error` tronqué/assaini.
- **Non-régression lifespan** : la boucle de santé et `recover_pending_deployments()` au startup restent fonctionnels (tests existants [`main.py`](../../backend/app/main.py) lifespan / smoke — vérifier suite existante) ; `scheduler_enabled=false` → boucle non démarrée.
- **Couverture ≥ 80 %** sur `scheduler_engine.py` + `scheduler_execution_store.py` (AC 4).

### Commandes de validation

```bash
poetry run pytest backend/tests/unit/test_services/test_scheduler_execution_store.py backend/tests/unit/test_services/test_scheduler_engine.py -v
make lint && make backend-typecheck
```

## Notes d'implémentation

*(clôture treat-story — 2026-10-21)*

### Fichiers créés

- [`backend/app/services/scheduler_execution_store.py`](../../backend/app/services/scheduler_execution_store.py) — contrat `ExecutionStore` (ABC : `mark_queued`/`mark_running`/`mark_success`/`mark_failed`/`mark_skipped`/`append_log`/`recover_orphans`) + `InMemoryExecutionStore` (horloge injectable, `ExecutionRecord` miroir de la future table 161) + `sanitize_error()` (assainissement/troncature des erreurs, rules 40) ; constante `ORPHAN_REASON` (libellé exact contractualisé par les tests) ;
- [`backend/app/services/scheduler_engine.py`](../../backend/app/services/scheduler_engine.py) — moteur `SchedulerEngine` complet (détail ci-dessous) ;
- Tests : `backend/tests/unit/test_services/test_scheduler_execution_store.py` (11), `backend/tests/unit/test_services/test_scheduler_engine.py` (28).

### Fichiers modifiés

- [`backend/app/config.py`](../../backend/app/config.py) — settings runtime : `scheduler_enabled` (**défaut `False`**, opt-in — prudence : le moteur ne démarre au lifespan que si `SCHEDULER_ENABLED=true`, les handlers réels n'arrivant qu'en 160.3), `scheduler_tick_seconds` (30, borné 1-3600), `scheduler_task_timeout_seconds` (600 = 10 min), `scheduler_retry_backoff` (3) + `field_validator` zoneinfo sur `scheduler_default_timezone` ;
- [`backend/app/main.py`](../../backend/app/main.py) — 4ᵉ tâche lifespan `scheduler_task` (conditionnée par `settings.scheduler_enabled`, pattern `cancel()` + `await` + `CancelledError` au shutdown, **aucune fusion** des 3 boucles existantes ni toucher à `recover_pending_deployments`) ; commentaire documentant la limite multi-workers.

### Architecture du moteur (décisions techniques)

1. **Horloge injectable** : `clock: Callable[[], datetime]` (aware UTC) est le **seul** point de lecture du temps — tous les tests se font par time travel (`TimeTravel`), jamais de `sleep` réel pour le cron ;
2. **Snapshots scalaires** (`_TaskSnapshot`) : le moteur ne conserve jamais d'instance ORM détachée de sa session — lecture du tick et relecture défensive produisent des copies, l'exécution dédiée consomme le snapshot ;
3. **Évaluation cron par fuseau** : `croniter(expr, start_time=now_local_aware).get_prev(datetime)` — le croniter vendored supporte les datetimes **aware** (vérifié par sanity check : il évalue en horloge locale murale du fuseau, DST inclus) ; échéances comparées par **timestamp UTC** (comparaison totale, insensible aux changements d'heure) ; fuseau résolu `task.timezone` → `settings.scheduler_default_timezone` → `UTC` ;
4. **Réinscription à chaud par empreinte** : `_last_due_ts[task_id]` + `_last_def[task_id] = (cron, timezone)` — un changement de cron/fuseau est détecté au tick suivant (empreinte différente) et **réinitialise sans déclencher** ; pas de cache à invalidation complexe ; première vue = initialisation sans trigger ;
5. **`get_prev` strict** : l'échéance calculée est **strictement antérieure** à now — une échéance tombant exactement à l'instant du tick est traitée au tick suivant (granularité minute, tick ~30 s : écart ≤ 1 tick) ;
6. **Retentatives dans le verrou** : le timeout s'applique **par tentative** et le verrou anti-chevauchement reste tenu pendant toute la stratégie retry (1 exécution à la fois, retentatives incluses — spec 17) ; backoff exponentiel borné (base × 2^n, plafond 30 s, base injectable `retry_backoff_base=0` en tests) ;
7. **Dispatch défensif** (checklist 40) : `get_action` (action inconnue → `SchedulerEngineError` explicite), `implemented=False` → échec « stub explicite », `handler is None` → échec « attendu STORY-160.3 », `validate_params` **rejoué avant exécution** (défense en profondeur derrière la validation à l'écriture) ; aucune de ces erreurs ne tue la boucle ;
8. **Annulation propre** : `CancelledError` traverse `_execute` (après avoir tracé `failed` « annulée — arrêt du scheduler ») ; `run()` annule les exécutions en vol au shutdown (`_cancel_inflight`) ;
9. **Événements système** : `SYSTEM_WARNING` sur `disable` par politique et au seuil de 3 échecs consécutifs (`scheduled_task.repeated_failures`, émis **une fois** au franchissement exact) — matérialisation minimale, alerte renvoyée STORY-161/P2-15 ; `aggregate_id` best-effort (`_safe_uuid`, les ids de tests non-UUID ne cassent pas l'émission) ;
10. **Échecs répétés** comptés par tâche en mémoire, reset sur succès.

### Divergences par rapport à l'analyse

- **Tâche 2 (settings)** : `scheduler_enabled` par défaut à **`False`** alors que l'analyse disait « défaut à définir ». Choix : opt-in explicite — à ce stade (160.2), toutes les actions `implemented` n'ont pas encore de handler (160.3) ; démarrer le moteur par défaut ne produirait que des échecs tracés. La description du setting documente le opt-in ; le basculement à `True` interviendra avec 160.3 ou la config de déploiement.
- **Tâche 3** : la surcharge de fuseau « depuis les paramètres de la tâche (`host_id`…) » de l'analyse n'a **pas** de colonne source à ce stade (`Target` sans timezone, STORY-166) — la résolution retenue est `task.timezone` → settings → UTC (la colonne `timezone` de la définition EST la surcharge par tâche, posée par 160.1). Point d'entrée 160.3/166 documenté.
- **Timeout par tentative vs global** : l'analyse ne précisait pas ; retenu par-tentative (cohérent avec le verrou tenu pendant les retentatives — une stratégie retry ne peut pas durer `timeout × (1+retries)` en tenant le verrou au-delà du raisonnable).

### Validation exécutée

- `poetry run pytest backend/tests/unit/test_services/test_scheduler_execution_store.py backend/tests/unit/test_services/test_scheduler_engine.py -v` : **39 passed** ;
- Non-régression : `poetry run pytest backend/tests/unit -q` (depuis la racine) : **1921 passed** (1882 barre post-160.1 + 39 nouveaux, 0 échec) ;
- Couverture nouveaux modules : `scheduler_engine.py` **96 %**, `scheduler_execution_store.py` **98 %** (≥ 80 % AC 4) ;
- `black` + `isort` + `flake8` sur les 6 fichiers de la story : OK ; `bandit -ll` sur les modules : **0 issue** (seul issue résiduel `main.py` B104 `0.0.0.0` du bloc `__main__` préexistant) ;
- `poetry run mypy backend/app` : **23 erreurs, toutes préexistantes** (0 sur les nouveaux modules, 0 nouvelle — barre 23 conservée).
- **Revalidation post-reprise (2026-10-23)** : la session de clôture avait été interrompue après écriture des notes — l'intégralité des commandes ci-dessus a été **re-exécutée et re-confirmée verte** ce jour (39 passed ciblés, 1921 passed non-régression, couverture 96 %/98 %, black/isort/flake8 OK, mypy 23 préexistantes + 0 sur modules scheduler, bandit -ll 0 issue) ; aucune divergence code ↔ notes constatée, backlog déjà synchronisé (kanban ✅ DONE, epic cochée).
- ⚠ Note : lancer pytest depuis `backend/` au lieu de la racine change le `env_file` résolu (`.env` racine non lu → `LOG_LEVEL=INFO` → echo SQL SQLAlchemy dans caplog) et fait échouer 2 tests de sécurité logs **préexistants** (`test_schedules_v2.py::TestSecurity::test_parameters_not_logged_raw`, `test_api_key_service.py::TestLogsSecurity::test_no_key_or_hash_in_logs`) — artefact de cwd, pas une régression ; la commande canonique (racine) est verte.

### Points d'entrée pour STORY-160.3

- **Enregistrer un handler** : `ActionDefinition.handler` du [registre](../../backend/app/services/action_registry.py) — `replace(get_action(name), handler=async_handler)` + mise à jour de `_REGISTRY[name]` (pattern des tests `_patch_handler`) ; contrat handler : `Callable[[dict], Awaitable[Any]]` — reçoit les **paramètres validés** (`validate_params().model_dump()`), retour attendu ignoré ;
- **`implemented=False`** (stubs `stack.backup`/`admin.backup`/`notification.send`) : le moteur lève `SchedulerEngineError` → exécution `failed` avec l'erreur « action non implémentée (stub explicite du registre) » — jamais de succès silencieux ; passer `implemented=True` en même temps que le handler ;
- **Contrat `ExecutionStore`** pour STORY-161 : implémenter l'ABC (`mark_queued`/`mark_running`/`mark_success`/`mark_failed`/`mark_skipped`/`append_log`/`recover_orphans`) sur la table `scheduled_task_executions` et injecter via `SchedulerEngine(store=...)` — le moteur n'a **aucune** dépendance à l'implémentation (couplage interface uniquement) ;
- **Triggers événement** (`trigger_type="event"`) : le moteur n'évalue que `trigger_type="cron"` à ce stade — l'abonnement EventBus (160.3) appellera le même `_execute`/verrou/politique (prévoir un `triggered_by` dédié si besoin) ;
- **Réactivation du moteur** : `SCHEDULER_ENABLED=true` (env) une fois les handlers réels disponibles ; fuseau global `SCHEDULER_DEFAULT_TIMEZONE`, timeout `SCHEDULER_TASK_TIMEOUT_SECONDS`, retry `SCHEDULER_RETRY_BACKOFF` ;
- **Limite multi-workers** (documentée `main.py` + module) : verrou/échéances en mémoire process-local — single-worker par défaut (arbitrage F1), `--workers > 1` = exécutions dupliquées possibles.
