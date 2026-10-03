# STORY-160 : Moteur d'exécution du scheduler — boucle asyncio, registre d'actions, triggers cron/événement, verrous et fuseaux IANA (P2-1, partie moteur)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-1 (axe A8, rapport §12) — ampleur **XL** (prévoir sous-découpe possible, plage réservée STORY-175-199)

## Description

En tant qu'administrateur WindFlow, je veux que les tâches planifiées (`scheduled_tasks`) soient **réellement exécutées** par un moteur asyncio d'évaluation des crons (croniter) — avec registre d'actions, déclencheurs cron **et** événement, verrous anti-chevauchement, relecture défensive des définitions, récupération des orphelins et fuseaux IANA — afin que la planification ne soit plus un simple CRUD de définitions sans effet ([`scheduler_service.py`](../../backend/app/services/scheduler_service.py:20)) et que l'automatisation core promise par la spec 17 fonctionne.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §5, §9) : [`scheduler_service.py`](../../backend/app/services/scheduler_service.py:20) ne fait que du CRUD sur `ScheduledTask` ; aucun moteur n'évalue les expressions cron, rien n'exécute les tâches, la table `scheduled_task_executions` n'existe pas. L'arbitrage F1 (validé, STORY-130.2) ayant purgé Celery, le runtime d'exécution est **asyncio dans le processus API** — conformément à la contrepartie assumée du plan (§3 F1 : « les tâches longues tournent dans le processus API → à isoler via le scheduler engine »).

## Contexte technique

*(à remplir par analyse-story)*

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

- **STORY-120** (Alembic — la migration `scheduled_task_executions` de STORY-161 passe par Alembic ; le moteur 160 lui-même ne migre pas le schéma).
- Étroitement couplée à **STORY-161** (persistance des exécutions) — analyse conjointe recommandée, découpe moteur/persistance assumée.
- Interagit avec **STORY-162** (nomenclature canonique pour les triggers événement) et la story notifications P2-15 (`notification.send`).
- Conditionne **P3-1** (purge croniter, EPIC-014).

## Sous-stories

*(section réservée — story XL : `analyse-story` devra évaluer une sous-découpe, ex. moteur/registre d'actions vs verrous-orchestration/fuseaux ; plage réservée STORY-175-199)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
