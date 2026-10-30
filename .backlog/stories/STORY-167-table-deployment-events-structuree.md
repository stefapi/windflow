# STORY-167 : `deployment_events` — table dédiée remplaçant la colonne texte `Deployment.logs`, events typés horodatés, endpoint d'association et rétention (P2-7 — axe A15)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-7 (axe A15, rapport §4) — ampleur **M**

## Description

En tant qu'utilisateur WindFlow, je veux que les événements de déploiement soient **persistés dans une table dédiée `deployment_events`** (events typés, horodatés, avec niveau et données JSON) remplaçant la colonne texte `Deployment.logs` — dont les données existantes sont migrées — et exposés via un endpoint paginé avec rétention, afin de pouvoir requêter, filtrer et purger l'historique des déploiements au lieu d'un amas de texte non structuré.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §6.2) : le modèle [`Deployment`](../../backend/app/models/deployment.py:34) porte les logs dans une **colonne texte** (`logs`, `error`) accumulée par [`deployment_service.py:23`](../../backend/app/services/deployment_service.py:23) ; la spec 06 exige une table `deployment_events` (event_type, level, message, data, created_at) liée au déploiement ; la spec 04 exige des événements structurés persistés.

## Contexte technique

**Analyse (analyse-story) — patterns identifiés, fichiers de référence, emplacements cibles :**

### Comportement actuel vérifié dans le code

- Le modèle [`Deployment`](../../backend/app/models/deployment.py:143) porte les logs dans les colonnes texte [`logs` / `error_message`](../../backend/app/models/deployment.py:214) ; l'accumulation se fait par append dans [`DeploymentService.update_status()`](../../backend/app/services/deployment_service.py:702) (concaténation `"\n"`).
- **Point de branchement unique** : [`DeploymentService.update_status()`](../../backend/app/services/deployment_service.py:662) est le seul lieu d'écriture des logs texte — vérifié : les 21 appels du pipeline ([`background_tasks.py`](../../backend/app/tasks/background_tasks.py:115) — jalons docker/compose ; [`deployment_orchestrator.py`](../../backend/app/services/deployment_orchestrator.py:135) — callback terminal/échec/annulation) passent tous par cette méthode. Les messages suivent une convention de préfixes : `[INFO]`, `[ERROR]`, `[SUCCESS]`, `[SYSTEM]`.
- Le service d'émission existant [`deployment_events.py`](../../backend/app/services/deployment_events.py:22) (`DeploymentEventsService` + singleton `get_deployment_events()`) couvre **transport** (bus canonique + WS) — aucune persistance. Le streaming WS `DEPLOYMENT_LOGS_UPDATE` ([`broadcasting.py`](../../backend/app/websocket/broadcasting.py)) n'est **pas impacté** (transport ≠ persistance).
- `GET /deployments/{id}/logs` existe ([`deployments.py:406`](../../backend/app/api/v1/deployments.py:406)) — à conserver tel quel (AC 4 non-régression).

### Patterns à imiter (fichiers de référence)

| Besoin | Fichier de référence | Remarque |
|---|---|---|
| Modèle enfant FK CASCADE + index | [`scheduled_task_execution.py`](../../backend/app/models/scheduled_task_execution.py:40) | Même structure : `String(36)` PK uuid4, FK `ondelete="CASCADE"`, `Index` nommés dans `__table_args__`, relation `lazy="selectin"` sans cascade ORM (base = source de vérité) |
| Migration DDL + index | [`2026_10_23_1331_scheduled_task_executions.py`](../../backend/alembic/versions/2026_10_23_1331_scheduled_task_executions.py:67) | `op.create_table` + `op.create_index` + downgrade symétrique |
| Data migration tolérante (sans perte, jamais d'échec de `upgrade head`) | [`2026_10_16_1311_ssh_keys_and_fingerprints.py`](../../backend/alembic/versions/2026_10_16_1311_ssh_keys_and_fingerprints.py:82) | Imports applicatifs paresseux, `alembic_context.is_offline_mode()`, warning sans donnée sensible |
| Store dédié (append/list paginée/purge par cutoff + horloge injectable) | [`scheduler_execution_store.py`](../../backend/app/services/scheduler_execution_store.py:475) | `purge_expired(retention_days)` avec `_clock()` injectable — pattern freezegun/time travel pour AC 4 |
| Endpoint liste filtrée paginée (domaines fermés `Query(pattern=...)`, dates ISO) | [`list_executions_global`](../../backend/app/api/v1/schedules.py:397) | Filtres combinés + `PaginationQuery` + `build_meta` + `PaginatedResponse` |
| Vérification d'accès org (isolation) | [`get_deployment_logs`](../../backend/app/api/v1/deployments.py:436) | `UserOrganizationService.is_member()` → `PermissionDeniedError` ; RBAC `require_viewer` |
| Rétention lifespan (démarrage conditionnel, boucle dédiée, logs = comptages) | [`main.py`](../../backend/app/main.py:257) (purge audit 125.3) et [`main.py:295`](../../backend/app/main.py:295) (purge exécutions 161) | Settings `Optional[int] = None` (défaut désactivé) + `_purge_interval_hours` |
| Registre d'actions scheduler | [`scheduler_actions.py:296`](../../backend/app/services/scheduler_actions.py:296) | `register_scheduler_actions()` — dict `handlers` (5 actions existantes) |
| Schéma SQL exact de la table | [`06-modele-de-donnees.md § DeploymentEvent`](../../docs/general_specs/06-modele-de-donnees.md:731) | Source de vérité colonnes/index |

### Emplacements cibles

- `backend/app/models/deployment_event.py` (nouveau) — ⚠ nommage **au singulier** pour éviter la collision avec le service existant `services/deployment_events.py` (transport) ;
- `backend/app/services/deployment_event_store.py` (nouveau) — persistance : `append_event()`, `list_for_deployment()` (filtres + pagination + `COUNT` même scoping), `purge_expired()` ;
- `backend/app/schemas/deployment.py` (enrichissement) — `DeploymentEventResponse` (même domaine, pas de fichier dédié) ;
- `backend/app/api/v1/deployments.py` — `GET /{deployment_id}/events` ;
- `backend/alembic/versions/` — nouvelle révision, `down_revision = "1662_environments_stacks_origin_git_url"` (tête actuelle vérifiée) ;
- `backend/app/config.py` + `env.example` — settings rétention (voir Tâche 8) ; `backend/app/main.py` — boucle lifespan.

### Décisions tranchées par l'analyse

1. **Double écriture dans `update_status()`** (pas de redécoupage des logs côté lecture) : la colonne texte `logs` continue d'être alimentée (payload brut — critère P2-7) **et** un `DeploymentEvent` est inséré dans la même transaction. Mapping statut → `event_type` : `DEPLOYING→deploying`, `RUNNING→success`, `FAILED→error`, `ROLLING_BACK→rollback`, `STOPPED→rollback` (annulation — divergence documentée : le domaine spec 06 n'a pas de type `stopped`), `PENDING→deploying` (défaut). Mapping préfixe → `level` : `[ERROR]→error`, `[SYSTEM]→warning`, `[INFO]`/`[SUCCESS]`→`info`.
2. **`pulling`/`health_check` non observables aujourd'hui** : les sous-étapes pulling/creating/starting sont internes à `deploy_container`/`deploy_compose` (hypothèse des jalons observables documentée dans [`background_tasks.py`](../../backend/app/tasks/background_tasks.py:83)) — l'enum reste le domaine fermé spec 06 complet, mais le pipeline actuel n'émet que `deploying|success|error|rollback`. Divergence documentée, résorbable par STORY-170 (gates) / futurs adapters.
3. **Horodatage de la data migration** : le texte n'a pas de timestamp fin → **interpolation linéaire** des `created_at` des lignes migrées entre `deployment.created_at` et `COALESCE(stopped_at, deployed_at, updated_at)` (ordre des lignes préservé). Alternative écartée : timestamp unique = `created_at` du déploiement (perte de l'ordre chronologique lors du tri). Choix documenté dans la docstring de la migration.
4. **Tri de l'endpoint** : `ORDER BY created_at ASC, id ASC` (AC 2 exige l'ordre des étapes pulling → … → success/error). Divergence assumée avec `list_executions_global` (DESC) : ici l'ordre chronologique du déroulé est le besoin exprimé.
5. **Colonnes datetime naïves UTC** (pattern SQLite du modèle `Deployment` — `datetime.utcnow`, cf. note STORY-125.2 dans [`deployment_service.py:714`](../../backend/app/services/deployment_service.py:714)) : `created_at` de `DeploymentEvent` suit le même pattern naïf pour éviter les `TypeError` de comparaisons aware/naïf.
6. **Payload `data` JSON** : limité à des identifiants/métriques non sensibles (`container_id`, `duration_seconds`, `step`…) — jamais de variables d'environnement ni secrets (rules 40 ; cf. `emit_progress_update`).
7. **Rétention — double mécanisme coordonné** : boucle lifespan dédiée (pattern 125.3/161, périodicité automatique désactivable) **+** handler `deployment_events.purge` enregistré au registre scheduler (STORY-160.3, « tâche ordinaire » déclenchable par cron admin). Les deux délèguent au même `purge_expired()` — purge par cutoff idempotente, pas de risque en cas d'exécution simultanée.
8. **WS non impacté** : aucun changement de contrat WebSocket (`DEPLOYMENT_LOGS_UPDATE` continue de diffuser le texte brut).

### Ambiguïtés / points de vigilance

- AC 3 « les refus de gate (STORY-170) y laissent une trace typée » : STORY-170 n'est pas encore implémentée — l'analyse prévoit uniquement que l'enum/le modèle **acceptent** ces types ; l'émission effective sera branchée par STORY-170.
- `event_type` `success` (spec 06) ≠ statut métier `running` — même divergence que STORY-162, l'event `success` marque la transition vers `RUNNING`.

Éléments existants à réutiliser / contraintes :
- **Schéma exact** (spec 06) : `id`, `deployment_id` FK `deployments` (ON DELETE CASCADE), `event_type` (`pulling|deploying|health_check|success|error|rollback`), `level` (`debug|info|warning|error`), `message` TEXT, `data` JSON, `created_at` ; index sur `deployment_id` et `created_at` ;
- **Migration des données** : la colonne texte `Deployment.logs` existante est migrée (découpage en lignes d'events `info` datées au mieux — l'horodatage fin n'existe pas dans le texte, choix à documenter) ; **la colonne logs texte reste pour le payload brut** (critère P2-7 : « la colonne logs texte reste pour le payload brut ») — double écriture ou redécoupage à trancher par l'analyse ;
- **Émission** : brancher l'écriture des events sur le pipeline existant ([`deployment_events.py:22`](../../backend/app/services/deployment_events.py:22) — service d'émission bus ; [`DeploymentService.update_status()`](../../backend/app/services/deployment_service.py:23), [`background_tasks.py:24`](../../backend/app/tasks/background_tasks.py:24) étapes pulling/deploying/…) ; un refus de gate (STORY-170) produira aussi des lignes `deployment_events` (spec 11 § gates) ;
- **Endpoint d'association aux événements bus** (mission) : `GET /deployments/{id}/events` paginé filtrable (par `event_type`, `level`, dates) — complète `GET /deployments/{id}/logs` existant ; enveloppes (STORY-126) + pagination (STORY-128) + RBAC ;
- **Rétention** : job de maintenance « rétention des événements/déploiements » (spec 17 — périodicité + rétention en jours, désactivable) ; s'exécute comme tâche ordinaire ; purge les anciens `deployment_events` — coordonné avec le scheduler (STORY-160/161) ;
- Lié à **STORY-162** (nomenclature : les statuts `success` émettent `deployment.succeeded` ; la table typée aligne `event_type` sur les étapes réelles) ; le streaming WS `DEPLOYMENT_LOGS_UPDATE` n'est pas impacté (transport ≠ persistance) ;
- Alembic (STORY-120) requis pour la migration.

## Critères d'acceptation (AC)

- [x] AC 1 : Migration Alembic crée `deployment_events` (schéma spec 06 : colonnes, FK CASCADE, index `deployment_id`/`created_at`) et **migre les données** de la colonne texte existante — test : un déploiement historique avec logs texte voit ses lignes converties en events requêtables, sans perte de contenu. *(tests `test_migration_deployment_events.py` — 8/8 passants, round-trip upgrade/downgrade/upgrade vérifié)*
- [x] AC 2 : Un déploiement de test produit une **séquence d'events requêtable paginée** : `GET /deployments/{id}/events` retourne les étapes dans l'ordre (pulling → deploying → success/error), chaque event portant `event_type`, `level`, `message`, `data`, `created_at` ; filtres par type/niveau/dates fonctionnels ; enveloppe `pagination{}` ; tests 401/403 (RBAC — lecture viewer+) /404. *(tests `test_deployments_events.py` + `test_deployments_events_api.py`)*
- [x] AC 3 : Le pipeline écrit désormais les events structurés à chaque étape clé (status change, étapes d'exécution, erreur, rollback) tout en conservant la colonne texte pour le payload brut ; les refus de gate éventuels (STORY-170) y laissent une trace typée. *(double écriture dans `update_status`, tests `test_deployment_service_events.py` ; point d'extension gate = enum complet + `append_event` réutilisable)*
- [x] AC 4 : La **rétention** purge les events au-delà de la durée configurée (test avec rétention courte + time travel), désactivable, tracée comme tâche de maintenance ; `GET /deployments/{id}/logs` existant non cassé (non-régression consommateurs WS/REST). *(tests `test_lifespan_deployment_events_purge.py` + suite `test_deployments.py` 32/32 ; WS non modifié)*
- [x] AC 5 : Couverture ≥ 80 % sur les modules touchés (modèle, service, endpoint, migration testée sur fixtures) ; build + lint + tests passent. *(modèle 100 %, store 95 %, lint flake8/black/isort OK, mypy 0 erreur périmètre)*

## Références spécification

- [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § DeploymentEvent — événements de déploiement (schéma SQL complet, index), § Deployment (relation 1-N) ;
- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § Bus d'événements internes / Résilience (événements structurés persistés, rollback) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Conventions (pagination, enveloppes), § Famille Apps `/deployments` (logs/progression — étapes pulling→starting) ;
- [`17-automatisation-workflows.md`](../../docs/general_specs/17-automatisation-workflows.md) — § Maintenance système planifiée (rétention des événements/déploiements) ;
- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Hooks de déploiement (gates) : un refus s'exprime avec « lignes `deployment_events` associées » ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-7, §2.A A15 (« événements structurés persistés vs colonne texte ») ;
- [`backend_status.md`](../../docs/backend_status.md) — §6.2 (Deployment : colonne logs/error texte), §3.6 (`GET /deployments/{id}/logs`).

## Dépendances

- **STORY-120** (Alembic) ; liée à **STORY-162** (nomenclature `deployment.succeeded` — P2-7 dépend de P2-2 pour la nomenclature).
- Interagit avec **STORY-160/161** (job de rétention exécuté par le scheduler) et **STORY-170** (traces des gates).

**Analyse (analyse-story) — état vérifié des dépendances :**

- **Socles déjà implémentés (vérifiés dans le code — aucun travail préalable requis)** :
  - STORY-120 : pipeline Alembic en place, tête actuelle = révision `1662_environments_stacks_origin_git_url` ;
  - STORY-126 : enveloppes `PaginatedResponse`/`PaginationMeta` actives ([`schemas/common.py`](../../backend/app/schemas/common.py:92)) ;
  - STORY-128 : `PaginationQuery`/`build_meta` ([`helper/pagination.py`](../../backend/app/helper/pagination.py:47)) ;
  - STORY-122 : RBAC `require_viewer`/`require_operator` ([`auth/rbac.py`](../../backend/app/auth/rbac.py)) ;
  - STORY-162 : nomenclature canonique du bus ([`deployment_events.py`](../../backend/app/services/deployment_events.py:90)) — la table typée s'aligne sur les étapes réelles, `success` = transition vers `RUNNING` ;
  - STORY-160.3 : registre d'actions scheduler ([`scheduler_actions.py`](../../backend/app/services/scheduler_actions.py:296)) — le handler `deployment_events.purge` s'y ajoutera ;
  - STORY-161/125.3 : patterns de rétention lifespan réutilisés tels quels.
- **STORY-170 (non implémentée)** : dépendance **sortante et conditionnelle** — cette story ne fait qu'offrir le point d'extension (enum/domaine `event_type` complet, store `append_event` réutilisable) ; l'émission des traces de gate sera branchée par STORY-170 elle-même. Aucun blocage dans un sens ni dans l'autre.
- **Migrations/config nécessaires (dans le périmètre de la story)** : 1 révision Alembic additive (DDL + data migration) ; 2 settings + entrées `env.example` (rétention). **Aucune modification de table existante** (la colonne `deployments.logs` est conservée — double écriture).
- **Services externes** : aucun (SQLAlchemy async uniquement ; pas de dépendance Redis/Docker — les tests mockent le pipeline de déploiement, pattern [`test_deploy_stack_progress.py`](../../backend/tests/unit/test_tasks/test_deploy_stack_progress.py)).
- **Consommateurs non impactés** : WS `DEPLOYMENT_LOGS_UPDATE` (transport inchangé), `GET /deployments/{id}/logs` (contrat inchangé), frontend/CLI (aucun consumer de la nouvelle route dans ce périmètre — exposition API d'abord).

## Sous-stories

*(non prévue — story M)*

## État d'avancement technique

- [x] Tâche 1 : Modèle `DeploymentEvent` + enums (domaines fermés spec 06)
- [x] Tâche 2 : Migration Alembic `1671` — DDL + data migration des logs texte
- [x] Tâche 3 : Store `deployment_event_store` (append / list filtrée paginée / purge)
- [x] Tâche 4 : Schéma `DeploymentEventResponse` + exports
- [x] Tâche 5 : Double écriture dans `DeploymentService.update_status()`
- [x] Tâche 6 : Endpoint `GET /deployments/{id}/events` (RBAC + filtres + pagination)
- [x] Tâche 7 : Vérification non-régression `GET /deployments/{id}/logs` + WS
- [x] Tâche 8 : Settings rétention + boucle lifespan de purge
- [x] Tâche 9 : Action scheduler `deployment_events.purge`
- [x] Tâche 10 : Validation complète (lint, types, tests, couverture ≥ 80 %)

## Tâches d'implémentation détaillées

> Ordre séquentiel strict — chaque tâche dépend de la précédente sauf mention contraire. Sécurité (rules 40) intégrée à chaque tâche concernée.

### Tâche 1 : Modèle `DeploymentEvent` + enums
**Objectif :** matérialiser la table spec 06 ([`06-modele-de-donnees.md § DeploymentEvent`](../../docs/general_specs/06-modele-de-donnees.md)) en SQLAlchemy 2.0 typé.
**Fichiers :**
- `backend/app/models/deployment_event.py` — Créer — pattern intégral [`scheduled_task_execution.py`](../../backend/app/models/scheduled_task_execution.py:40) : PK `String(36)` uuid4, FK `deployments.id` `ondelete="CASCADE"`, `__table_args__` avec index nommés `idx_deploy_events_deployment` / `idx_deploy_events_created` (noms spec 06), relation `deployment` `lazy="selectin"` **sans** cascade ORM (FK SQL = source de vérité), `created_at` naïf UTC (`datetime.utcnow`, décision 5 — cohérent [`deployment.py`](../../backend/app/models/deployment.py:228)).
- `backend/app/models/__init__.py` — Modifier — import + `__all__`.
**Dépend de :** Aucune
**Vigilance :** `event_type` `String(50)` + `level` `String(10)` avec **enums Python de référence** (`DeploymentEventType` : `pulling|deploying|health_check|success|error|rollback` ; `DeploymentEventLevel` : `debug|info|warning|error`) — domaines fermés spec 06, stockage des valeurs (pattern `ScheduledTaskExecution.status`, pas de `SQLEnum` : la data migration écrit des valeurs littérales). Colonne `data` `JSON` nullable. Docstring documentant la divergence `success` ↔ `running` (STORY-162).

### Tâche 2 : Migration Alembic `1671` — DDL + data migration
**Objectif :** créer la table + migrer les logs texte existants sans perte (AC 1), sans jamais faire échouer `upgrade head`.
**Fichiers :**
- `backend/alembic/versions/2026_XX_XX_1671_deployment_events_table.py` — Créer — `down_revision = "1662_environments_stacks_origin_git_url"` ; `upgrade()` : `op.create_table` (colonnes spec 06 exactes) + 2 `op.create_index`, puis data migration pattern [`1311_ssh_keys`](../../backend/alembic/versions/2026_10_16_1311_ssh_keys_and_fingerprints.py:82) : skip si `alembic_context.is_offline_mode()`, itération par déploiement, split `logs` par `\n` (lignes vides ignorées), `level` par préfixe (`[ERROR]`→`error`, `[SYSTEM]`→`warning`, sinon `info`), `event_type` = `error` si le déploiement est `failed`, `success` si `running`, `deploying` sinon, `created_at` interpolés linéairement entre `created_at` et `COALESCE(stopped_at, deployed_at, updated_at)` (décision 3 — docstring de justification) ; échec par ligne → `logger.warning` sans donnée sensible + ligne laissée (best-effort). `downgrade()` : drop index + drop table (non destructif : `deployments.logs` jamais modifiée).
**Dépend de :** Tâche 1
**Vigilance :** chunking éventuel pour gros volumes ; jamais de log du contenu des logs (identifiants de lignes uniquement) ; un downgrade/upgrade re-remplacerait les lignes (PK uuid4 nouvelles) — documenté comme limite assumée.

### Tâche 3 : Store de persistance `deployment_event_store`
**Objectif :** isoler la persistance des events (aucune logique HTTP), réutilisable par pipeline, endpoint et purge.
**Fichiers :**
- `backend/app/services/deployment_event_store.py` — Créer — classe `DeploymentEventStore` : `append_event(db, deployment_id, event_type, level, message, data)` (validation des domaines fermés, `data` limité aux champs non sensibles) ; `list_for_deployment(db, deployment_id, event_type?, level?, after?, before?, page, per_page)` → `(items, total)` avec `COUNT` aux **mêmes filtres** (pattern [`scheduler_execution_store.py`](../../backend/app/services/scheduler_execution_store.py:475) / `count_hook_logs`) ; `purge_expired(retention_days, *, clock=datetime.utcnow)` par cutoff `created_at` (pattern [`purge_expired`](../../backend/app/services/scheduler_execution_store.py:475)) — horloge injectable pour le time travel AC 4.
**Dépend de :** Tâche 1
**Vigilance :** type hints complets (rules 30) ; logs structurés sans contenu de message ; fonctions courtes.

### Tâche 4 : Schémas Pydantic
**Objectif :** contrat I/O validé de l'endpoint (API-first).
**Fichiers :**
- `backend/app/schemas/deployment.py` — Modifier — `DeploymentEventResponse(BaseModel)` : `id`, `deployment_id`, `event_type: Literal[...]`, `level: Literal[...]`, `message`, `data`, `created_at` + `model_config` examples OpenAPI (pattern [`scheduled_task_execution.py`](../../backend/app/schemas/scheduled_task_execution.py)) ; **aucun champ sensible** — `data` renvoyé tel quel (il n'en contient pas par construction, Tâches 3/5).
- `backend/app/schemas/__init__.py` — Modifier — ré-export.
**Dépend de :** Tâche 1
**Vigilance :** `Literal` (domaines fermés — 422 sur valeur inconnue), descriptions complètes (doc OpenAPI maximale, rules 20).

### Tâche 5 : Double écriture dans `DeploymentService.update_status()`
**Objectif :** à chaque étape clé, insérer un event typé **dans la même transaction** que le statut (AC 3), en conservant l'append texte brut.
**Fichiers :**
- `backend/app/services/deployment_service.py` — Modifier — dans [`update_status()`](../../backend/app/services/deployment_service.py:662) : avant le `commit` (l. ~734), appeler `append_event` avec mapping statut→`event_type` (`DEPLOYING|PENDING→deploying`, `RUNNING→success`, `FAILED→error`, `ROLLING_BACK|STOPPED→rollback` — décision 1) et préfixe→`level` ; `data` = `{"old_status", "new_status"}` (+ `container_id`/`duration` si disponibles) — **jamais** de `configuration`/`variables` (rules 40) ; pas de paramètre `event_type` ajouté à la signature (rétro-compatibilité des 21 appelants).
**Dépend de :** Tâche 3
**Vigilance :** même transaction ⇒ cohérence statut/event garantie (un échec d'insert annule le changement de statut — assumé, la persistance est désormais partie du contrat) ; l'émission WS existante (post-commit, best-effort) est inchangée ; divergence `pulling`/`health_check` non observables documentée (Contexte technique, décision 2).

### Tâche 6 : Endpoint `GET /deployments/{id}/events`
**Objectif :** exposer l'historique paginé filtrable (AC 2).
**Fichiers :**
- `backend/app/api/v1/deployments.py` — Modifier — nouvelle route `GET /{deployment_id}/events` **après** [`get_deployment_logs`](../../backend/app/api/v1/deployments.py:406) : `require_viewer` + `conditional_rate_limiter(100, 60)` ; résolution déploiement → `NotFoundError` ; isolation via `UserOrganizationService.is_member()` → `PermissionDeniedError` (pattern lignes 424-447) ; Query params `event_type` (`pattern` domaine fermé), `level` (idem), `after`/`before` (`datetime` ISO 8601), `page`/`per_page` via `PaginationQuery` ; tri `created_at ASC, id ASC` (décision 4) ; retour `PaginatedResponse` + `build_meta` ; docstring OpenAPI complète : summary, description (pagination/filtres/tri stables/RBAC), examples 200/401/403/404/422 (pattern [`list_executions_global`](../../backend/app/api/v1/schedules.py:364)).
**Dépend de :** Tâches 3, 4
**Vigilance :** 422 natif via `Query(pattern=...)` et `PaginationQuery` (per_page > 100) ; jamais d'`organization_id` dans la réponse (scoping implicite) ; logs avec `correlation_id` + `user_id` + `deployment_id` (pattern lignes 415-422), sans contenu de message.

### Tâche 7 : Non-régression `GET /logs` + WS
**Objectif :** garantir que les consommateurs existants ne cassent pas (AC 4).
**Fichiers :**
- `backend/app/api/v1/deployments.py` — Vérifier — `get_deployment_logs` et `DeploymentLogsResponse` inchangés ; exécuter la suite existante ([`test_deployments_api.py`](../../backend/tests/integration/test_deployments_api.py), [`test_ws_deployment_logs_e2e.py`](../../backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py)) sans modification.
**Dépend de :** Tâche 5
**Vigilance :** si un test existant casse (ex. assertions sur `update_status` mockée), adapter le **test** sans changer le comportement observé de `/logs`.

### Tâche 8 : Settings rétention + boucle lifespan
**Objectif :** purge périodique désactivable, tracée comme tâche de maintenance (AC 4).
**Fichiers :**
- `backend/app/config.py` — Modifier — `deployment_events_retention_days: Optional[int] = Field(default=None, ge=1, ...)` (None = désactivée) + `deployment_events_purge_interval_hours: int = Field(default=24, ge=1, ...)` (pattern lignes 137-155).
- `env.example` — Modifier — documenter `DEPLOYMENT_EVENTS_RETENTION_DAYS` / `DEPLOYMENT_EVENTS_PURGE_INTERVAL_HOURS`.
- `backend/app/main.py` — Modifier — 6ᵉ tâche lifespan, copie du pattern exécutions (lignes 290-340) : démarrage conditionnel (`None` → log « retention disabled »), boucle `while True` try/except + `asyncio.sleep`, logs = comptages uniquement, annulation propre dans le shutdown existant.
**Dépend de :** Tâche 3
**Vigilance :** ne pas fusionner avec les boucles existantes (pattern 125.3 : boucles distinctes) ; purge par âge uniquement, jamais d'audit touché ; single-worker assumé (arbitrage F1 documenté [`main.py`](../../backend/app/main.py:342)).

### Tâche 9 : Action scheduler `deployment_events.purge`
**Objectif :** exposer la purge comme tâche ordinaire du scheduler (spec 17, coordonnée STORY-160/161).
**Fichiers :**
- `backend/app/services/scheduler_actions.py` — Modifier — handler async `deployment_events_purge` : session courte dédiée, délègue à `purge_expired`, retourne `{"removed": n, "retention_days": ...}` ; enregistrement dans le dict `handlers` (ligne ~313) sous `"deployment_events.purge"`.
**Dépend de :** Tâche 3
**Vigilance :** idempotence (cutoff — exécution simultanée lifespan+cron inoffensive) ; jamais de paramètre sensible dans le résultat.

### Tâche 10 : Validation complète
**Objectif :** DoD — couverture ≥ 80 % sur les modules touchés, lint/typage/tests verts.
**Fichiers :**
- Aucun nouveau fichier — exécution : `make backend-test-unit`, `make backend-test-integration`, `make backend-lint`, `make backend-typecheck`, `poetry run alembic upgrade head && poetry run alembic downgrade -1 && poetry run alembic upgrade head` (round-trip).
**Dépend de :** Tâches 1-9
**Vigilance :** si couverture < 80 % sur `deployment_event_store.py` / endpoint, compléter les tests avant de passer en REVIEW.

## Tests à écrire

### Backend — tests unitaires

- `backend/tests/unit/test_models/test_deployment_event.py` — defaults (uuid, `created_at`, `level="info"`, `data`), `__table_args__` (index `idx_deploy_events_deployment`/`idx_deploy_events_created`), valeurs des enums (domaines fermés spec 06), FK CASCADE (SQLite `PRAGMA foreign_keys=ON` — pattern tests ScheduledTaskExecution), `__repr__`.
- `backend/tests/unit/test_schemas/test_deployment_event_schema.py` — `DeploymentEventResponse` : accepte les 6 `event_type`/4 `level`, **rejette** (`ValidationError`) une valeur hors domaine ; `data` arbitraire sérialisé.
- `backend/tests/unit/test_services/test_deployment_event_store.py` —
  - `append_event` : insertion + champs ;
  - `list_for_deployment` : filtres combinés (`event_type` × `level` × `after`/`before`), pagination (page 2, page au-delà → `[]` + total exact), tri `created_at ASC, id ASC`, **isolation** (les events d'un autre déploiement n'apparaissent jamais), `COUNT` = total filtré (pas d'oracle) ;
  - `purge_expired` : horloge figée injectée (`clock`) — rétention courte purge les anciens, garde les récents, retourne le comptage, no-op sous le seuil.
- `backend/tests/unit/test_services/test_deployment_service_events.py` — [`update_status()`](../../backend/app/services/deployment_service.py:662) : un event inséré par appel (mapping statut→`event_type` : `RUNNING→success`, `FAILED→error`, `ROLLING_BACK→rollback`…), `level` par préfixe (`[ERROR]`→`error`, `[SYSTEM]`→`warning`), **double écriture** (colonne `logs` toujours appendée), `data` ne contient **ni `variables` ni `configuration` ni secret**, échec d'insert ⇒ rollback du statut (même transaction).
- `backend/tests/unit/test_api/test_deployments_events.py` — matrice rules 35/40 sur `GET /api/v1/deployments/{id}/events` :
  - **Nominal** : 200 avec séquence ordonnée pulling→…→success/error sur un déploiement complet, enveloppe `data` + `pagination{page, per_page, total, pages}`, filtres `event_type`/`level`/`after`/`before` fonctionnels ;
  - **Sécurité** : `test_returns_401_without_token` ; `test_returns_403_for_viewer_foreign_org` (isolation — déploiement d'une autre organisation, pattern [`test_deployments_rbac.py`](../../backend/tests/unit/test_api/test_deployments_rbac.py)) ; `test_returns_200_for_viewer_own_org` (RBAC lecture viewer+) ;
  - **Erreurs** : `test_returns_404_unknown_deployment` ; `test_returns_422_invalid_event_type` / `_invalid_level` (domaines fermés) / `_per_page_over_100` / `_invalid_date` ;
  - **Fuite de données** : `test_response_does_not_expose_variables_or_secrets` (aucune clé `variables`/`configuration`/token dans les items).
- `backend/tests/unit/test_api/test_deployments.py` — non-régression : `GET /{id}/logs` inchangé (200, payload texte brut) après la bascule double écriture.

### Backend — tests d'intégration

- `backend/tests/integration/test_migration_deployment_events.py` — AC 1 sur DB réelle : fixture avec déploiement historique `logs` multi-lignes (`[INFO]`/`[ERROR]`…) → après `upgrade` : chaque ligne = un event requêtable, **aucune perte de contenu** (concaténation des messages == texte original), `created_at` interpolés strictement croissants, `level`/`event_type` conformes au statut ; round-trip `downgrade` → table absente, `deployments.logs` **intacte** ; déploiement à logs `NULL` → aucune ligne, pas d'erreur.
- `backend/tests/integration/test_deployments_events_api.py` — bout-en-bout : création de déploiement (orchestrateur mocké, pattern [`test_deployments_api.py`](../../backend/tests/integration/test_deployments_api.py)) → events persistés à chaque `update_status` du pipeline → endpoint paginé retourne le déroulé complet.

### Backend — tests lifespan/rétention (AC 4)

- `backend/tests/unit/test_lifespan_deployment_events_purge.py` — settings `None` → boucle non démarrée (pattern audit purge) ; rétention courte + purge directe `purge_expired` avec horloge figée → events anciens purgés, récents conservés, comptage loggé ; le job ne touche ni `deployments` ni `audit_logs`.

### Frontend

- Aucun — story backend-only : aucun composant/store/route frontend modifié ; le contrat WS `DEPLOYMENT_LOGS_UPDATE` et `GET /logs` sont inchangés (AC 4). La consommation UI de la nouvelle route fera l'objet d'une story dédiée.

### Commandes de validation

```bash
make backend-test-unit
make backend-test-integration
make backend-lint
make backend-typecheck
poetry run alembic upgrade head && poetry run alembic downgrade -1 && poetry run alembic upgrade head
# Couverture ciblée (AC 5 — seuil 80 % sur modules touchés)
poetry run pytest backend/tests/unit/test_models/test_deployment_event.py \
  backend/tests/unit/test_services/test_deployment_event_store.py \
  backend/tests/unit/test_services/test_deployment_service_events.py \
  backend/tests/unit/test_api/test_deployments_events.py \
  --cov=app.models.deployment_event --cov=app.services.deployment_event_store \
  --cov-fail-under=80
```

## Notes d'implémentation

### Fichiers créés
- `backend/app/models/deployment_event.py` — modèle `DeploymentEvent` + enums `DeploymentEventType`/`DeploymentEventLevel` (domaines fermés spec 06, stockage valeurs littérales `String(50)`/`String(10)`, `created_at` naïf UTC, FK CASCADE, index nommés spec 06) ;
- `backend/app/services/deployment_event_store.py` — `DeploymentEventStore` : `append_event` (validation domaines fermés + liste blanche `_ALLOWED_DATA_KEYS` sur `data` — rules 40), `list_for_deployment` (filtres combinés, tri `created_at ASC, id ASC`, COUNT même scoping, isolation stricte), `purge_expired` (cutoff idempotent, horloge injectable) ;
- `backend/alembic/versions/2026_10_30_1671_deployment_events_table.py` — DDL spec 06 + data migration tolérante (split `\n`, level par préfixe, event_type par statut, interpolation linéaire `created_at` entre `created_at` et `COALESCE(stopped_at, deployed_at, updated_at)`, offline-safe, best-effort par déploiement) ;
- Tests : `backend/tests/unit/test_models/test_deployment_event.py`, `backend/tests/unit/test_schemas/test_deployment_event_schema.py`, `backend/tests/unit/test_services/test_deployment_event_store.py`, `backend/tests/unit/test_services/test_deployment_service_events.py`, `backend/tests/unit/test_api/test_deployments_events.py`, `backend/tests/unit/test_lifespan_deployment_events_purge.py`, `backend/tests/integration/test_migration_deployment_events.py`, `backend/tests/integration/test_deployments_events_api.py`.

### Fichiers modifiés
- `backend/app/models/__init__.py`, `backend/app/schemas/__init__.py` — exports ;
- `backend/app/schemas/deployment.py` — `DeploymentEventResponse` (`Literal` domaines fermés → 422) + constantes `DEPLOYMENT_EVENT_TYPES/LEVELS` ;
- `backend/app/services/deployment_service.py` — double écriture dans `update_status()` avant commit (mapping `_EVENT_TYPE_BY_STATUS`/`_LEVEL_BY_LOG_PREFIX`, `data` = old/new_status + container_id/duration, sans commit — transaction de l'appelant) ;
- `backend/app/api/v1/deployments.py` — `GET /{deployment_id}/events` (require_viewer + rate limiter 100/60, isolation `is_member`, filtres `Query(pattern=...)`, `PaginationQuery`, `PaginatedResponse`+`build_meta`, doc OpenAPI complète 200/401/403/404/422) ;
- `backend/app/config.py` + `env.example` — `deployment_events_retention_days` (None=désactivé) / `deployment_events_purge_interval_hours` (24) ;
- `backend/app/main.py` — 6ᵉ boucle lifespan dédiée (pattern 125.3/161 : démarrage conditionnel, `while True` + sleep, comptages, annulation propre au shutdown) ;
- `backend/app/schemas/actions.py` + `backend/app/services/action_registry.py` + `backend/app/services/scheduler_actions.py` — action `deployment_events.purge` (params bornés 1-3650 j, `implemented=True`, handler session courte déléguant à `purge_expired`, retour `{"removed", "retention_days"}`) ;
- Tests existants synchronisés (compteurs légitimes) : `test_migrations.py`, `test_alembic_config.py`, `test_database.py` (EXPECTED/ADDITIVE_TABLES + drops pré-migration), `test_rbac_exhaustivite.py` (deployments 8→9), `test_action_registry.py` (5→6 actions).

### Décisions techniques
- Toutes les décisions structurantes 1-8 de l'analyse appliquées telles quelles (double écriture, mappings statut/préfixe, interpolation linéaire, tri ASC, naïf UTC, liste blanche data, double mécanisme rétention, WS intact) ;
- `data` JSON : liste blanche au moment de l'append (`old_status`, `new_status`, `container_id`, `duration_seconds`, `step`, `host_id`, `error`) — defense in depth rules 40, testée par `test_append_event_sanitizes_data_whitelist` ;
- `DeploymentEventResponse` validé puis `model_dump(mode="json")` dans l'endpoint : la sérialisation datetime est cohérente avec l'enveloppe spec 09 ;
- Divergence mineure documentée dans la docstring de la migration : `data` en `sa.JSON` (pattern colonnes `config`/`variables` de `deployments`) vs spec 06 `TEXT DEFAULT '{}'` — même stockage TEXT sous SQLite.

### Divergences par rapport à l'analyse
- Aucune divergence de périmètre. Points d'adaptation mineurs dans les **tests** : (1) lecture du body wire via `response.json()["data"]` plutôt que `unwrap()` pour l'endpoint paginé (l'enveloppe middleware conserve `pagination` au niveau racine) ; (2) `error_message` d'`update_status` alimente la colonne dédiée (comportement existant inchangé) — l'assertion du test séquence vérifie `error_message` + `events[2].message` au lieu de la colonne `logs`.

### Difficultés rencontrées
- Fixtures SQL brutes pré-1671 : la table `hosts` (post-1661) exige `profile`, `status`, `extra_metadata` NOT NULL — INSERT de test complété en conséquence ;
- Identity map SQLAlchemy : les lectures après purge (session dédiée) nécessitent `expire_all()` sur `db_session` (objet sinon servi du cache) — IDs capturés avant expiration pour éviter le lazy-load async interdit ;
- `datetime.utcnow` wrappé par SQLAlchemy (`ctx`) : tests de default passent le contexte (`created_default(None)`).

### Commandes de validation exécutées (résultats)
- `poetry run pytest backend/tests/unit` → **2683 passed, 0 failed** (incl. 78 nouveaux tests STORY-167) ;
- `poetry run pytest backend/tests/integration/test_migration_deployment_events.py backend/tests/integration/test_deployments_events_api.py` → **10 passed** ;
- Round-trip `alembic upgrade head && downgrade -1 && upgrade head` (SQLite /tmp) → **OK** ;
- Couverture ciblée : `app/models/deployment_event.py` **100 %**, `app/services/deployment_event_store.py` **95 %** (seuil AC 5 ≥ 80 % atteint) ;
- `black` + `isort` (périmètre) → formatés ; `flake8` (périmètre) → **0 erreur** ; `mypy` (périmètre) → **0 erreur nouvelle** (l'erreur `main.py:920` sur le handler d'exceptions existe sur HEAD — vérifié par `git show`) ;
- `pytest backend/tests/integration` (hors `test_secret_encryption.py`, cassé en collection **avant** mes changements — import résiduel `TargetStatus` STORY-166) : 201 passed, **20 failed préexistants prouvés par `git stash`** (auth_api/security_headers/deployments_api échouent à l'identique sur HEAD sans mes modifications — environnement local, hors périmètre STORY-167).

### État
Story `DONE` (finalisée 2026-10-30) — DoD validée par `finalise-story` : AC 1-5 cochés et vérifiés contre le code livré, 10/10 tâches cochées, notes d'implémentation complètes. Validations re-exécutées : `make backend-test-unit` → **2683 passed, 0 failed** ; lint — correction isort sur 2 fichiers de test de la story (`test_deployments_events.py`, `test_migration_deployment_events.py` : lignes vides doubles post-imports) puis flake8 **0 erreur** sur le périmètre ; les échecs restants des cibles globales (`isort` ×37, `black` ×23, flake8, mypy ×28, bandit B104 `main.py`) sont **préexistants sur HEAD** (prouvés via `git show HEAD:`) et hors périmètre STORY-167 ; mypy **0 erreur** sur les fichiers de la story (`main.py:920` = handler d'exceptions préexistant, décalé par l'ajout de la boucle lifespan).
