# STORY-160.1 : Modèle ScheduledTask spec 17, registre d'actions et API `/schedules` v2 (P2-1, partie définition)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-160 ([ABANDONED — découpe proactive post-analyse le 2026-10-21](STORY-160-moteur-scheduler-asyncio.md))
**Item plan :** P2-1 (axe A8, rapport §12) — ampleur **M-L**

> **Périmètre (découpe)** : cette sous-story reprend le **volet définition** de STORY-160 — évolution du modèle [`ScheduledTask`](../../backend/app/models/scheduled_task.py) alignée spec 17 (`action` du registre remplaçant l'enum fermé, `trigger_type` `cron|event`, `event_name`, `timezone` IANA, politique d'erreur), migration Alembic d'évolution avec mapping défensif des 5 `task_type` legacy, **registre d'actions** avec nomenclature canonique arbitrée, schémas Pydantic Create/Update/Response avec validation complète, et endpoints `/schedules` **non régressés**. Couvre l'AC 2 de la mère (partie définition/registre) et son AC 5 (partie API/non-régression). Le volet moteur runtime est porté par [STORY-160.2](STORY-160.2-moteur-runtime-asyncio.md) (pré-requis : le présent modèle/registre) ; le volet exécution réelle des actions et triggers événement par [STORY-160.3](STORY-160.3-actions-core-triggers-evenement.md).

## Description

En tant qu'administrateur WindFlow, je veux que les définitions de tâches planifiées soient **conformes à la spec 17** — une `action` issue d'un registre canonique (et non un enum fermé arbitraire), un trigger `cron` **ou** `event`, un fuseau IANA et une politique d'erreur — exposées et validées par l'API `/schedules` v2, afin que le moteur scheduler (STORY-160.2) puisse ensuite exécuter des définitions dont la structure est prédictible et sécurisée.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §5) : [`models/scheduled_task.py`](../../backend/app/models/scheduled_task.py) porte un enum `TaskType` **fermé** (`CLEANUP_LOGS`/`HEALTH_CHECK`/`GIT_SYNC`/`RETRY_DEPLOYMENTS`/`CUSTOM`, [`:21-28`](../../backend/app/models/scheduled_task.py)) et **aucune** colonne `trigger_type`/`event_name`/timezone/politique d'erreur — la spec 17 § Scheduler core exige une action du registre + trigger `cron|event` + politique d'erreur. La nomenclature des actions diverge de surcroît **entre le plan P2-1** (`stack.backup`, `compute.docker.prune`, `admin.backup`) **et la spec 17** (`app.backup`, `compute.images.prune`/`compute.volumes.prune`, `admin.backup.create`…) → l'arbitrage du registre canonique est un **prérequis d'entrée** de cette story.

## Contexte technique

> Extrait de l'analyse STORY-160 (2026-10-21, `analyse-story`) — volet définition. Fondée sur le code réel du dépôt (fichiers/lignes cités). Aucun code modifié.

### Patterns existants à réutiliser (directs)

- **CRUD existant** : [`SchedulerService`](../../backend/app/services/scheduler_service.py:21) — `record_run()` ([`:148`](../../backend/app/services/scheduler_service.py)) persiste `last_run`/`last_status`/`last_error`/`run_count` sur la définition (complémentaire de STORY-161) ; `get_enabled_tasks()` ([`:165`](../../backend/app/services/scheduler_service.py)) est déjà prévu pour le moteur (consommé par 160.2).
- **Router `/schedules`** : [`api/v1/schedules.py`](../../backend/app/api/v1/schedules.py) — CRUD paginé (`PaginatedResponse` + `PaginationQuery`/`build_meta`, STORY-128), RBAC `require_viewer`(lecture)/`require_operator`/`require_admin`(écriture) (STORY-122), exemples OpenAPI riches, endpoint `POST /schedules/{task_id}/toggle` — à **non-régresser** (tests existants [`test_schedules_rbac.py`](../../backend/tests/unit/test_api/test_schedules_rbac.py) + [`test_api_contract.py`](../../backend/tests/integration/test_api_contract.py)).
- **Parseur cron** : vendored [`helper/croniter.py`](../../backend/app/helper/croniter.py) (décision E3 : « ressusciter via A8 ») — ⚠️ il importe `dateutil.relativedelta`/`dateutil.tz` ([`croniter.py:15-16`](../../backend/app/helper/croniter.py)) alors que **`python-dateutil` n'est pas déclarée** dans `pyproject.toml` → déclaration Poetry explicite requise dès cette story (la validation cron à l'API consomme croniter ; rules 05 : dépendance justifiée par E3, à tracer en note d'implémentation).
- **Config** : pattern `Settings` + `Field(default=…, description/alias)` ([`config.py:54-56`](../../backend/app/config.py), [`:73-75`](../../backend/app/config.py)) — pour les défauts exposés dans la doc OpenAPI (fuseau global défaut UTC, politique d'erreur défaut, timeout défaut 10 min — les settings runtime complets sont posés par 160.2).
- **Transversal** : exceptions [`WindFlowException`](../../backend/app/core/exceptions.py) → `APIError` (InvalidInput/NotFound/Conflict…) ; audit [`AuditService.log`](../../backend/app/services/audit_service.py) (`_sanitize_details` masque `key`/`password`/`credential`) — pattern d'audit des créations/modifications/suppressions de tâches à conserver/compléter.

### Points d'intégration & contraintes (arbitrages d'analyse)

- **Arbitrage de nomenclature du registre (prérequis d'entrée)** : la liste de travail est celle du plan P2-1 — `stack.backup`, `compute.docker.prune` (images/volumes), `host.scan`, `admin.backup`, `notification.send` — à confronter à la nomenclature spec 17 (`app.backup`, `compute.images.prune`/`compute.volumes.prune`, `admin.backup.create`…) et à la sémantique `prune` de STORY-173 (liste `windflow-plugin-*` épargnée, dry-run). Décision à **tracer en note d'implémentation** (et signalée à STORY-252 si elle implique une correction de spec) ; la clé retenue conditionne le modèle, l'API et le moteur.
- **Migration d'évolution, pas data migration lourde** : la table `scheduled_tasks` n'est pas seedée ([`database_seed.py`](../../backend/app/database_seed.py) ne la touche pas) — migration Alembic (pattern STORY-120, `batch_alter_table` pour SQLite) : ajout des nouvelles colonnes + **mapping défensif** des 5 `task_type` legacy sans perte silencieuse (toute ligne legacy non mappable est **désactivée** `enabled=false` et journalisée, aucune suppression muette) ; retrait de la colonne/enum `task_type` après mapping.
- **Contrat posé pour le moteur** : `trigger_type` (`cron`|`event`), `event_name` (nullable, requis si `event`), `timezone` IANA (nullable → défaut settings, surcharge résolue depuis les paramètres de la tâche car `Target` n'a **pas** de colonne timezone — alignement STORY-166 à tracer, non bloquant), `error_policy` (`ignore`|`retry`|`disable`, défaut configurable), `action` (clé du registre) + `parameters` validés par **schéma Pydantic par action** (registre).
- **Stubs explicites** : les actions non implémentables à ce stade (`stack.backup`→F8/initiative backup, `admin.backup`→F8, `notification.send`→P2-15) sont enregistrées au registre en **stub explicite documenté** (statut d'implémentation visible) — jamais de succès silencieux à l'exécution (comportement porté par 160.3).
- **Dépendance Python** : déclarer `python-dateutil` (Poetry, `pyproject.toml`) — prérequis du croniter vendored (justification E3, rules 05).

### Risques hérités (de l'analyse mère, périmètre définition)

- **Nomenclature divergente plan ↔ spec 17** : arbitrage obligatoire d'entrée (cf. ci-dessus) — impact cross-story (160.2/160.3 consomment les clés du registre).
- **`python-dateutil` non déclarée** alors que [`croniter.py:15-16`](../../backend/app/helper/croniter.py) l'importe — sans déclaration, la validation cron à l'API échoue en runtime.
- **Fixtures existantes** : les tests actuels (`test_schedules_rbac.py`, fixtures créant des tâches avec `task_type`) devront être adaptés au nouveau contrat — divergence à tracer, la non-régression porte sur RBAC/enveloppes/pagination/champs existants.
- **P2-15 / arbitrage EPIC-013** : `notification.send` reste en stub ; l'arbitrage de matérialisation (plage réservée STORY-175-199 ou vague suivante) doit être **tracé avant la finalisation** de la famille 160 (cf. epic, traçabilité).

### Checklist sécurité (règle 40) — volet définition

- **AuthN/AuthZ** : endpoints `/schedules` restent `require_viewer`(lecture)/`require_admin`(écriture) — actions destructrices (`prune`) réservées à des définitions créées par Admin (RBAC à la création ; le registre verrouille les actions disponibles).
- **Validation & injection** : expression cron validée via croniter à l'API (**422**) ; fuseau via `zoneinfo` (`ZoneInfoNotFoundError` → **422**) ; `action` restreinte au registre (**422**) ; `event_name` restreint à la liste canonique (`EventType`, spec 11) (**422**) ; `trigger_type="event"` sans `event_name` rejeté (**422**) ; `parameters` validés par schéma Pydantic par action — jamais d'exécution shell/SSH avec paramètres non validés.
- **Données sensibles** : réponses `/schedules` sans champ sensible ; `parameters` potentiellement sensibles jamais loggés bruts (audit `_sanitize_details`) ; pas de secret dans les exemples OpenAPI.
- **Audit & traçabilité** : audit des créations/modifications/suppressions de tâches conservé/complété (pattern existant).

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend la partie définition/registre de l'AC 2 de la mère)* : registre d'actions core en place avec **nomenclature canonique arbitrée et tracée** (alignement plan P2-1 ↔ spec 17 ↔ STORY-173), paramètres validés par **schéma Pydantic par action**, stubs **explicites documentés** pour `stack.backup`/`admin.backup`/`notification.send` (renvois F8/P2-15) ; une définition référençant une action hors registre est rejetée en **422** à l'API.
- [x] AC 2 *(découpe locale : validation & non-régression API, hérite de l'AC 5 de la mère)* : endpoints `/schedules` existants **non régressés** (RBAC viewer/admin, enveloppes spec 09, pagination) et étendus aux nouveaux champs (`action`, `trigger_type`, `event_name`, `timezone`, `error_policy`) avec validation complète : 422 (cron invalide via croniter, fuseau IANA inconnu, action hors registre, `event_name` non canonique, `event` sans `event_name`) ; 401/403/404 inchangés ; couverture ≥ 80 % sur les nouveaux modules.
- [x] AC 3 *(découpe locale : migration)* : migration Alembic d'évolution appliquée (nouvelles colonnes + mapping défensif des 5 `task_type` legacy **sans perte silencieuse** — lignes non mappables désactivées et journalisées, table vraisemblablement vide vérifiée en migration) ; `upgrade head` et downgrade testés (pattern tests migrations STORY-120.3).

## Références spécification

- [`17-automatisation-workflows.md`](../../docs/general_specs/17-automatisation-workflows.md) — § Scheduler core (modèle : action du registre, trigger `cron|event`, politique d'erreur), § Actions core (liste canonique des actions), § Bonnes pratiques ;
- [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités d'automatisation (`ScheduledTask`) ;
- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Liste canonique des événements (validation `event_name`) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — enveloppes et validation sémantique 422 ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-1, §2.A A8, §2.E E3 (croniter) ; [`backend_status.md`](../../docs/backend_status.md) §5.

## Dépendances

- **Pré-requis posés (faits ✅)** : STORY-120 (Alembic opérationnel — migrations jusqu'à [`2026_10_16_1311_ssh_keys_and_fingerprints.py`](../../backend/alembic/versions/2026_10_16_1311_ssh_keys_and_fingerprints.py)), STORY-122 (RBAC `require_viewer`/`require_admin`), STORY-126/128 (enveloppes, pagination) — consommés directement.
- **STORY-161** (table `scheduled_task_executions`) — couplage fort sans blocage : les colonnes posées ici sont lues par le moteur et par les endpoints de consultation de 161 ; analyse conjointe recommandée (l'implémentation DB du contrat `ExecutionStore` défini en 160.2 est portée par 161).
- **STORY-173** (prune protégé `/compute`) — alignement de sémantique pour `compute.docker.prune` (liste `windflow-plugin-*` épargnée, dry-run) : si 173 n'est pas fusionné, la définition de l'action (schéma de paramètres, défaut dry-run) est posée ici et l'implémentation coordonnée en 160.3.
- **Story notifications P2-15** — `notification.send` enregistrée en **stub explicite** ; arbitrage EPIC-013 (matérialisation STORY-175-199 ou report) à tracer avant finalisation de la famille 160.
- **Conditionne** : [STORY-160.2](STORY-160.2-moteur-runtime-asyncio.md) (le moteur lit `trigger_type`/`timezone`/`error_policy` et dispatche via le registre) et [STORY-160.3](STORY-160.3-actions-core-triggers-evenement.md) (handlers réels enregistrés au registre) ; partiellement P3-1 (purge croniter, chaîne critique n°3) et STORY-252 si l'arbitrage de nomenclature implique une correction de spec.

## État d'avancement technique

*(cochage progressif pendant treat-story ; origine mère indiquée par tâche — volet définition de l'analyse STORY-160)*

- [x] Tâche 1 — Registre d'actions + arbitrage de nomenclature d'entrée
- [x] Tâche 2 — Dépendance Poetry `python-dateutil` (prérequis croniter vendored)
- [x] Tâche 3 — Évolution du modèle `ScheduledTask` + migration Alembic d'évolution (mapping défensif)
- [x] Tâche 4 — Schémas Pydantic Create/Update/Response avec validateurs (croniter, zoneinfo, registre, event_name)
- [x] Tâche 5 — Service `SchedulerService` : validation création/modification via le registre
- [x] Tâche 6 — Router `/schedules` v2 : exposition des nouveaux champs + OpenAPI + audit (non-régression)
- [x] Tests — Registre, validation API 422/401/403/404, schémas, migration, non-régression

## Tâches d'implémentation détaillées

> Séquence issue de l'analyse STORY-160 (volet définition), renumérotée. Périmètre : modèle + registre + API — aucun runtime (160.2), aucune implémentation d'action réelle (160.3).

### Tâche 1 : Registre d'actions + arbitrage de nomenclature (décision d'entrée)

**Objectif :** poser le registre canonique des actions scheduler avec schéma de paramètres par action et statut d'implémentation (réel|stub), après arbitrage tracé de la nomenclature (plan P2-1 ↔ spec 17 § Actions core ↔ STORY-173).

**Fichiers :**
- `backend/app/schemas/actions.py` — **Créer** : schémas Pydantic de paramètres par action (ex. `HostScanParams {target_id}`, `DockerPruneParams {resource: images|volumes, dry_run: bool = True, ...}` bornés et typés strictement — jamais de paramètre libre non validé) ;
- `backend/app/services/action_registry.py` — **Créer** : `ActionDefinition {name, description, params_schema, handler, implemented: bool}` ; actions core enregistrées : `host.scan` (consommable — implémentation 160.3), `compute.docker.prune` (clé arbitrée : `compute.docker.prune` vs `compute.images.prune`/`compute.volumes.prune` spec 17 — **décision tracée en note d'implémentation**), `stack.backup`/`admin.backup` (stubs explicites, renvoi F8/initiative backup), `notification.send` (stub explicite, renvoi P2-15) ; API interne : `get_action(name)`, `list_actions()`, `is_valid(name)` — action inconnue → erreur explicite (pas de KeyError brut).

**Dépend de :** Aucune (arbitrage d'entrée — tracer la décision + alerte STORY-252 si spec impactée)

### Tâche 2 : Dépendance Poetry `python-dateutil`

**Objectif :** rendre le croniter vendored réellement exécutable (l'analyse a constaté l'import non déclaré).

**Fichiers :**
- `pyproject.toml` — **Modifier** : ajouter `python-dateutil` en dépendance principale (justification E3 — `helper/croniter.py` importe `dateutil.relativedelta`/`dateutil.tz`, [`croniter.py:15-16`](../../backend/app/helper/croniter.py) ; rules 05 : dépendance justifiée, à tracer en note d'implémentation).

**Dépend de :** Aucune (à merger avant toute tâche consommant croniter — tâches 4/5)

### Tâche 3 : Évolution du modèle `ScheduledTask` + migration Alembic

**Objectif :** aligner le modèle sur la spec 17 (action du registre, trigger cron|event, fuseau IANA, politique d'erreur) avec mapping défensif des `task_type` legacy.

**Fichiers :**
- `backend/app/models/scheduled_task.py` — **Modifier** : colonnes `action: str` (clé du registre), `trigger_type: str` (`cron`|`event`, défaut `cron`), `event_name: str | None`, `timezone: str | None` (IANA, défaut résolu au runtime), `error_policy: str` (`ignore`|`retry`|`disable`, défaut depuis settings) ; retrait de l'enum fermé `TaskType` ([`:21-28`](../../backend/app/models/scheduled_task.py)) ; colonnes existantes conservées (`cron_expression`, `parameters`, `enabled`, `last_run`/`last_status`/`last_error`/`run_count`, organisation) ;
- `backend/alembic/versions/<daté>_scheduled_tasks_spec17_actions.py` — **Créer** (pattern STORY-120, `batch_alter_table` SQLite) : ajout des colonnes, **mapping défensif** des 5 `task_type` legacy (`CLEANUP_LOGS`/`HEALTH_CHECK`/`GIT_SYNC`/`RETRY_DEPLOYMENTS`/`CUSTOM` → action équivalente du registre si évidente, sinon ligne **désactivée** `enabled=false` et journalisée — aucune perte silencieuse, table vraisemblablement vide à vérifier), puis drop de `task_type` ; downgrade inverse ;
- `backend/app/models/__init__.py` — **Modifier** si les exports changent (retrait `TaskType`).

**Dépend de :** Tâche 1 (registre — clés d'action du mapping), STORY-120 ✅

### Tâche 4 : Schémas Pydantic `/schedules` v2

**Objectif :** contrats I/O validés de bout en bout (422 sémantique, checklist sécurité).

**Fichiers :**
- `backend/app/schemas/scheduled_task.py` — **Modifier** : `ScheduledTaskCreate`/`Update`/`Response` étendus (`action`, `trigger_type`, `event_name`, `timezone`, `error_policy`, `parameters` re-validés par le schéma du registre via validator) ; validateurs : cron via croniter (expression invalide → 422 `VALIDATION_ERROR`), fuseau via `zoneinfo.ZoneInfo` (`ZoneInfoNotFoundError` → 422), `action` ∈ registre (via `action_registry.is_valid`), `event_name` ∈ liste canonique (`EventType`, [`events.py:18`](../../backend/app/core/events.py)) et requis si `trigger_type="event"` ; `Response` **sans champ sensible** (parameters potentiellement sensibles non développés bruts — au besoin masqués).

**Dépend de :** Tâches 1-2 (registre, dateutil), Tâche 3 (modèle)

### Tâche 5 : Service `SchedulerService` — validation création/modification

**Objectif :** centraliser la validation métier des définitions (100 % hors HTTP, logique existante conservée).

**Fichiers :**
- `backend/app/services/scheduler_service.py` — **Modifier** : `create()`/`update()` valident via le registre (action, schéma params) + croniter + zoneinfo, lèvent `InvalidInputError` (422) ; mapping éventuel `task_type` legacy **accepté en entrée pour compat** puis retiré (divergence à tracer) ; `record_run()` ([`:148`](../../backend/app/services/scheduler_service.py)) et `get_enabled_tasks()` ([`:165`](../../backend/app/services/scheduler_service.py)) inchangés (consommés par 160.2) ; logs sans `parameters` bruts.

**Dépend de :** Tâches 1-4

### Tâche 6 : Router `/schedules` v2 + OpenAPI + audit

**Objectif :** exposer les nouveaux champs sans régresser RBAC/enveloppes/pagination (API-first, rules 20).

**Fichiers :**
- `backend/app/api/v1/schedules.py` — **Modifier** : schémas v2 branchés sur les 6 endpoints existants (liste paginée, détail, create, update, delete, toggle) ; exemples OpenAPI enrichis (cron/event/IANA/error_policy, cron invalide → exemple 422) ; audit des écritures conservé/complété (pattern `_sanitize_details`) ; **aucun** changement de route existante (garde-fou §2.G : `test_router_route_counts_stable` — compteurs inchangés).

**Dépend de :** Tâches 4-5

## Tests à écrire

> Règles 35/40 : sécurité obligatoire (401/403/422/404 par endpoint), httpx `AsyncClient` + `ASGITransport`. Familles issues de l'analyse mère (famille 160.1-API), adaptées au format dépôt.

### Backend — unitaires

- `backend/tests/unit/test_services/test_action_registry.py` : le registre expose les 5 actions core ; chaque action porte un `params_schema` Pydantic ; stubs marqués `implemented=False` (`stack.backup`, `admin.backup`, `notification.send`) ; action inconnue → erreur explicite (pas de KeyError brut) ; `is_valid()` cohérent avec `get_action()`.
- `backend/tests/unit/test_schemas/test_scheduled_task_schemas.py` : validateurs unitaires — cron invalide → 422 ; fuseau IANA inconnu → 422 ; action hors registre → 422 ; `trigger_type="event"` sans `event_name` → 422 ; `event_name` non canonique → 422 ; `parameters` invalides rejetés par le schéma de l'action ; nominaux acceptés (cron + event + timezone `Europe/Paris`).
- `backend/tests/unit/test_api/test_schedules_v2.py` (extension cohérente de [`test_schedules_rbac.py`](../../backend/tests/unit/test_api/test_schedules_rbac.py)) : nominaux (201 create avec `action`+`trigger_type`+`timezone`, 200 liste paginée avec enveloppe `pagination{}`, 200 détail, 200 update, 204 delete, 200 toggle) ; **sécurité** : 401 sans token, 403 viewer sur écritures (RBAC inchangé), 422 (cron invalide, fuseau inconnu, action hors registre, `event` sans `event_name`, body manquant), 404 id inconnu ; **aucun champ sensible** dans les réponses ni les logs (assert caplog — parameters non loggés bruts).
- **Migration** : étendre [`backend/tests/integration/test_migrations.py`](../../backend/tests/integration/test_migrations.py) (pattern STORY-120.3) — `upgrade head` avec la nouvelle migration, downgrade/upgrade round-trip ; si le pattern le permet, test du mapping défensif (ligne legacy `task_type` non mappable → `enabled=false`, aucune perte silencieuse).
- **Non-régression** : [`test_schedules_rbac.py`](../../backend/tests/unit/test_api/test_schedules_rbac.py) + [`test_api_contract.py`](../../backend/tests/integration/test_api_contract.py) passent — adapter les fixtures utilisant `task_type` au nouveau contrat (divergence à tracer en note d'implémentation) ; garde-fou comptage de routes inchangé.

### Commandes de validation

```bash
poetry run pytest backend/tests/unit/test_services/test_action_registry.py backend/tests/unit/test_schemas/test_scheduled_task_schemas.py -v
poetry run pytest backend/tests/unit/test_api/test_schedules_v2.py backend/tests/unit/test_api/test_schedules_rbac.py -v --tb=short
poetry run pytest backend/tests/integration/test_migrations.py backend/tests/integration/test_api_contract.py -v
make lint && make backend-typecheck
```

## Notes d'implémentation

*(clôture treat-story — 2026-10-21)*

### Fichiers créés

- [`backend/app/schemas/actions.py`](../../backend/app/schemas/actions.py) — schémas de paramètres par action (`HostScanParams`, `DockerPruneParams`, `StackBackupParams`, `AdminBackupParams`, `NotificationSendParams`), tous `extra="forbid"`, `dry_run=True` par défaut pour prune (STORY-173) ;
- [`backend/app/services/action_registry.py`](../../backend/app/services/action_registry.py) — registre canonique (`ActionDefinition{name, description, params_schema, implemented, handler}`, `get_action`/`list_actions`/`is_valid`/`validate_params`), action inconnue → `InvalidInputError` explicite (pas de KeyError brut) ;
- [`backend/alembic/versions/2026_10_21_1321_scheduled_tasks_spec17_actions.py`](../../backend/alembic/versions/2026_10_21_1321_scheduled_tasks_spec17_actions.py) — migration d'évolution (revision `1321_scheduled_tasks_spec17`, down_revision `1311_ssh_keys`) ;
- Tests : `backend/tests/unit/test_services/test_action_registry.py` (20), `backend/tests/unit/test_schemas/test_scheduled_task_schemas.py` (25), `backend/tests/unit/test_api/test_schedules_v2.py` (20).

### Fichiers modifiés

- [`backend/app/models/scheduled_task.py`](../../backend/app/models/scheduled_task.py) — retrait enum `TaskType` ; colonnes `action`, `trigger_type` (défaut `cron`), `event_name`, `timezone`, `error_policy` (défaut `ignore`) ;
- [`backend/app/schemas/scheduled_task.py`](../../backend/app/schemas/scheduled_task.py) — Create/Update/Response v2 avec validateurs (croniter, zoneinfo, EventType, registre) ; `extra="forbid"` (champ legacy `task_type` rejeté) ; validation `parameters` couplée à `action` via `model_validator(mode="before")` sur le payload brut ;
- [`backend/app/services/scheduler_service.py`](../../backend/app/services/scheduler_service.py) — `create_task`/`update_task` v2 : validation défense en profondeur (registre + croniter + zoneinfo + EventType), update sur **définition fusionnée revalidée** ; `record_run`/`get_enabled_tasks` inchangés (consommés par 160.2) ; logs sans `parameters` bruts ;
- [`backend/app/api/v1/schedules.py`](../../backend/app/api/v1/schedules.py) — 6 routes inchangées (garde-fou comptage respecté : `schedules: 6`) ; exemples OpenAPI enrichis (cron/event/IANA/error_policy, exemple 422) ; audit `schedule.created/updated/deleted/toggled` via `AuditService.log_from_request` (jamais de parameters dans les details) ;
- [`backend/app/config.py`](../../backend/app/config.py) — settings `scheduler_default_timezone` (None) et `scheduler_default_error_policy` ("ignore") documentés OpenAPI ;
- [`backend/app/main.py`](../../backend/app/main.py) — correctif socle : `jsonable_encoder(exc.errors())` dans les 2 handlers 422 (les validators Pydantic V2 placent l'objet `ValueError` dans `ctx.error`, non sérialisable JSON → 500 au lieu de 422 sinon) ;
- [`pyproject.toml`](../../pyproject.toml) + `poetry.lock` — `python-dateutil = "^2.9.0"` déclaré en dépendance principale (déjà résolue transitive 2.9.0.post0 ; `poetry add --lock` impossible sans réseau, édition + `poetry lock` régénéré depuis le cache) ;
- Tests adaptés : `test_schedules_rbac.py` (payloads `action` v2), `test_migrations.py` / `test_alembic_config.py` / `test_database.py` (helper `_restore_legacy_scheduled_tasks` : les simulations de bases legacy via `create_all` portaient désormais les colonnes v2 → retour à l'état pré-1321 avant stamp, pattern 121.3/131.1).

### Décisions techniques

1. **Arbitrage nomenclature (prérequis d'entrée)** — liste de travail plan P2-1 retenue, confrontée à spec 17 § Actions core et STORY-173 :
   - `compute.docker.prune` (clé unique plan P2-1, paramètre borné `resource: images|volumes`) retenu **au lieu de** `compute.images.prune`/`compute.volumes.prune` (spec 17) : évite la duplication de handler, matche l'API Docker `POST /prune` ;
   - `stack.backup` / `admin.backup` (plan P2-1) retenus **au lieu de** `app.backup` / `admin.backup.create` (spec 17) : l'entité « App » n'existe pas dans WindFlow (les stacks en tiennent lieu — cf. F7/STORY-174) ;
   - `host.scan` paramètre `target_id` (l'entité Host n'existe pas en base — arbitrage F3, renommage STORY-166) ;
   - **Alerte STORY-252** : la spec 17 § Actions core diverge du registre implémenté sur ces 3 points — correction de spec à porter par STORY-252 (P3-4).
2. **Mapping défensif des 5 `task_type` legacy** : aucun équivalent registre évident (sémantiques distinctes — `cleanup_logs` ≠ prune Docker, `health_check` ≠ `host.scan`…) → clés **gelées** `legacy.<task_type>` hors registre + `enabled=false` + journalisation (aucune perte silencieuse, aucune exécution non validée). Downgrade : reverse-mapping `legacy.*` → enum d'origine, `CUSTOM` sinon. La table n'est pas seedée — mapping no-op en pratique, vérifié par test d'intégration avec lignes legacy injectées.
3. **Update = PATCH sémantique sur PUT** (comportement historique conservé) : champs fournis validés par les schémas, puis **définition fusionnée revalidée intégralement au service** — un update ne peut pas corrompre la cohérence trigger/event ni référencer des paramètres incohérents avec l'action (défense en profondeur derrière Pydantic, utile aux appelants hors HTTP).
4. **`ScheduledTaskUpdate` accepte `event_name=None`** si `trigger_type` n'est pas fourni (retrait d'event_name impossible via update — la cohérence est garantie par la revalidation de la fusion ; divergence mineure assumée).

### Divergences par rapport à l'analyse

- **Analyse Tâche 3** : « mapping des task_type legacy → action équivalente du registre **si évidente** » — aucune équivalence n'était sûre ; la branche défensive (gel + désactivation + journal) a été appliquée à toutes les lignes, conformément à l'exigence « sans perte silencieuse ». `models/__init__.py` inchangé (n'exportait pas `TaskType`).
- **Analyse Tâche 5** : le mapping `task_type` legacy « accepté en entrée pour compat puis retiré » n'a **pas** été implémenté — `extra="forbid"` rejette `task_type` en 422 explicite dès l'API (choix sécurité : aucune compat silencieuse avec un champ retiré ; les 3 seuls consommateurs API — tests backend — ont été adaptés). Le frontend `Schedules.vue` référence encore `task_type` : hors périmètre backend (adaptation frontend à planifier, l'API est la source de vérité — divergence tracée ici pour visibilité).
- **Correctif socle hors périmètre strict mais requis** : `main.py` handlers 422 (bug latent : toute erreur de validator Pydantic V2 custom dans un endpoint faisait 500 au lieu de 422 — découvert par les tests de cette story, corrigé au plus près avec `jsonable_encoder`).
- **Poetry** : `poetry add` impossible (pas d'accès réseau sortant) → édition manuelle de `pyproject.toml` + `poetry lock` régénéré avec succès depuis le cache local (version 2.9.0.post0 inchangée, déjà résolue transitive).

### Validation exécutée

- `poetry run pytest backend/tests/unit -q` : **1882 passed** (après correctif `test_database.py`, 1 préexistant corrigé par adaptation de simulation legacy) ;
- `poetry run pytest backend/tests/integration/test_migrations.py backend/tests/integration/test_api_contract.py backend/tests/unit/test_api/test_rbac_exhaustivite.py backend/tests/unit/test_alembic_config.py` : **144 passed, 1 skipped** (PostgreSQL indisponible localement — skip documenté, scénario PG couvert en CI) ;
- Couverture nouveaux modules : `action_registry.py` **100 %**, `schemas/actions.py` **100 %**, `schemas/scheduled_task.py` **98 %**, `models/scheduled_task.py` **100 %** (≥ 80 % AC 2) ;
- `black` + `isort` + `flake8` sur tous les fichiers modifiés : OK ; `bandit -ll` : 0 issue ; `mypy backend/app` : 23 erreurs **toutes préexistantes** (vérifié par comparaison git stash avant/après — 0 nouvelle) ;
- `alembic upgrade head` / `downgrade 1311_ssh_keys` / re-upgrade : OK (tests d'intégration round-trip).

### Points d'entrée pour STORY-160.2 / 160.3

- Le moteur (160.2) lit `trigger_type`/`timezone`/`error_policy` sur `ScheduledTask` et consomme `SchedulerService.get_enabled_tasks()` (inchangé) ; fuseau résolu : `task.timezone` sinon `settings.scheduler_default_timezone` sinon UTC ;
- Les handlers d'actions réelles (160.3) s'enregistrent via `ActionDefinition.handler` (champ prêt, `None` à ce stade) ; les stubs `stack.backup`/`admin.backup`/`notification.send` portent `implemented=False` — l'exécution doit échouer proprement (jamais de succès silencieux) ;
- Le registre expose `validate_params()` pour toute validation hors HTTP ;
- La divergence de nomenclature vs spec 17 est à faire entrer dans STORY-252.
