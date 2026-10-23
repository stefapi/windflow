# STORY-161 : Table `scheduled_task_executions` — historique des exécutions, endpoints de consultation et rétention (P2-1, partie traçabilité)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-1 (axe A8, rapport §12) — ampleur **M** (découpe de P2-1 : persistance + consultation)

## Description

En tant qu'administrateur WindFlow, je veux que chaque exécution de tâche planifiée — par cron, par événement ou manuelle — soit **matérialisée** dans une table `scheduled_task_executions` (statut, déclencheur, horodatages, durée, erreur, journaux ligne à ligne) et consultable via des endpoints paginés, avec un job de purge/rétention configurable, afin de rendre l'automatisation exploitable (écran Activité, alerte « 3 échecs répétés ») au lieu de laisser les exécutions sans trace.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §6.2) : la table n'existe pas — le CRUD [`scheduler_service.py`](../../backend/app/services/scheduler_service.py:20) n'a aucun support d'exécution ; l'historique et la rétention spécifiés (spec 17) sont inexistants.

## Contexte technique

> Analyse `analyse-story` du 2026-10-23, fondée sur le code réel du dépôt (fichiers/lignes cités). Aucun code modifié. Verdict complexité : **ampleur M confirmée — pas de découpage requis** (9 tâches, domaine unique backend scheduler/traçabilité, ni UI ni CLI dans le périmètre).

### Patterns existants à réutiliser (directs)

- **Contrat `ExecutionStore`** ([`scheduler_execution_store.py`](../../backend/app/services/scheduler_execution_store.py)) livré par STORY-160.2 **pour cette story** : interface `mark_queued/mark_running/mark_success/mark_failed/mark_skipped/append_log/recover_orphans` + constantes statuts (`queued|running|success|failed|skipped`), `sanitize_error` (assainissement/troncature rules 40), `ORPHAN_REASON` (libellé contractualisé par les tests 160.2) et `InMemoryExecutionStore` (à conserver intact pour l'isolation des tests moteur). La docstring l'explicite : « STORY-161 branchera son implémentation DB sur cette même interface, sans modifier le moteur » — l'impl DB est **couplée par interface uniquement**.
- **Injection du store dans le moteur** : [`SchedulerEngine.__init__(store=…)`](../../backend/app/services/scheduler_engine.py:151) est injectable ; [`main.py`](../../backend/app/main.py:266) instancie aujourd'hui `SchedulerEngine(settings=settings)` (store mémoire par défaut) → c'est **le point de branchement** de l'impl DB.
- **Divergences documentées à consommer** (notes d'implémentation de 160.3, [`scheduler_event_triggers.py:28-43`](../../backend/app/services/scheduler_event_triggers.py)) : le moteur code `triggered_by="schedule"` en dur dans `_execute` ([`scheduler_engine.py:369-371`](../../backend/app/services/scheduler_engine.py)) — la distinction `event`/`manual` est un **point d'entrée assumé de 161** (modification additive minimale du moteur, voir tâche 4).
- **Router `/schedules` v2** ([`api/v1/schedules.py`](../../backend/app/api/v1/schedules.py)) : pattern exact à imiter — `require_viewer/require_operator/require_admin` ([`auth/rbac.py`](../../backend/app/auth/rbac.py)), enveloppe `PaginatedResponse` + `build_meta` (STORY-126/128, [`helper/pagination.py`](../../backend/app/helper/pagination.py)), exemples OpenAPI riches, `AuditService.log_from_request` **sans jamais les `parameters` bruts**. Garde-fou : les 6 routes historiques restent inchangées (AC 5).
- **Modèle + migration** : [`models/scheduled_task.py`](../../backend/app/models/scheduled_task.py) (PK `String(36)` uuid4, `mapped_column`, `created_at/updated_at`) comme gabarit ; migration pattern [`2026_10_21_1321_scheduled_tasks_spec17_actions.py`](../../backend/alembic/versions/2026_10_21_1321_scheduled_tasks_spec17_actions.py) — la nouvelle migration a `down_revision = "1321_scheduled_tasks_spec17"` (tête actuelle de la chaîne) ; scénarios d'intégration numérotés + `EXPECTED_TABLES` dans [`tests/integration/test_migrations.py`](../../backend/tests/integration/test_migrations.py) (inspection colonnes/index/FK CASCADE, base vierge **et** base stampée).
- **Rétention** : pattern complet audit STORY-125.3 — settings [`audit_retention_days`/`audit_purge_interval_hours`](../../backend/app/config.py:65) (None = conservation infinie, démarrage conditionnel de la boucle), boucle lifespan dédiée [`main.py:207-242`](../../backend/app/main.py) (session fraîche par itération via `AsyncSessionLocal`, logs = comptages uniquement, shutdown `cancel()` + `CancelledError`) et service `AuditService.purge_expired(db) -> int` ([`audit_service.py:311`](../../backend/app/services/audit_service.py:311)).
- **Tests** : [`test_schedules_v2.py`](../../backend/tests/unit/test_api/test_schedules_v2.py) (helpers `_create_user_with_role`/`_auth_headers`/`_seed_task`, fixture `_jwt_mode` forçant JWT, `caplog` pour « parameters non loggés bruts ») ; [`test_scheduler_execution_store.py`](../../backend/tests/unit/test_services/test_scheduler_execution_store.py) (raison orphelin exacte, `triggered_by` tracé — **ne pas casser** : l'impl mémoire garde les valeurs du contrat).
- **Alerte 3 échecs** : le moteur émet **déjà** un événement bus tracé au 3ᵉ échec consécutif — [`_note_failure`](../../backend/app/services/scheduler_engine.py:548) publie `EventType.SYSTEM_WARNING` raison `scheduled_task.repeated_failures` (seuil `_CONSECUTIVE_FAILURES_ALERT = 3`, fire-and-forget). L'AC 4 « notification/événement tracé » est donc couvert par cet événement existant + sa persistance indirecte (3 lignes `failed`) ; la notification **in-app** relève de la story notifications P2-15.

### Points d'intégration

- [`main.py`](../../backend/app/main.py) lifespan : (a) instancier le moteur avec le store DB ; (b) ajouter la **5ᵉ tâche lifespan** (boucle rétention — pattern 123.4/125.3 : intervalle distinct, **sans fusionner** les 4 boucles existantes), shutdown propre symétrique.
- [`models/__init__.py`](../../backend/app/models/__init__.py) : exporter `ScheduledTaskExecution` (enregistrement des modèles requis par Alembic et les tests d'intégration).
- [`scheduler_event_triggers.py`](../../backend/app/services/scheduler_event_triggers.py) : passer `triggered_by="event"` au chemin moteur (paramètre additif de `_execute`).
- **Registre d'actions non modifié** : les jobs système de maintenance sont hors registre des actions utilisateur (spec 17 § Maintenance) — la rétention est une boucle lifespan interne, pas une action du registre ([`action_registry.py`](../../backend/app/services/action_registry.py)).
- **Ordre des routes FastAPI** : `GET /schedules/executions…` doit être déclaré **avant** les routes paramétrées `/schedules/{task_id}` du fichier (matching dans l'ordre d'enregistrement — sinon « executions » capture le `{task_id}`).

### Décisions d'analyse (à respecter en implémentation)

1. **`duration_seconds` en `Float`** : le moteur produit des secondes fractionnaires (`total_seconds()`, [`scheduler_engine.py:406`](../../backend/app/services/scheduler_engine.py)) — divergence mineure vs spec 06 (`INTEGER`), à tracer en note d'implémentation et signaler à STORY-252.
2. **`logs` en `Text` JSON** : liste `[{"timestamp": "<ISO 8601 UTC>", "message": str}]` (spec 06 : « horodatages ISO 8601, stockage UTC ») ; append délégué au store DB.
3. **`append_log` best-effort** (AC 3) : un échec d'écriture d'une ligne de journal **n'est jamais propagé** (try/except + `logger.error` dans l'impl DB — seule la ligne est perdue) ; en revanche les transitions `mark_*` propagent leurs erreurs (le moteur les convertit en échec d'exécution propre).
4. **Mapping `triggered_by` à la persistance** : valeurs spec 06 (`cron|event|manual`) en base ; traduction au point unique qu'est l'impl DB (`"schedule"` → `"cron"`, `"event"` et `"manual"` inchangés) ; `InMemoryExecutionStore` conserve les valeurs du contrat (`schedule|retry|manual` — tests 160.2 intacts). `"retry"` ne crée pas de ligne dédiée : les retentatives sont des lignes de journal au sein de la **même** exécution ([`scheduler_engine.py:447`](../../backend/app/services/scheduler_engine.py)).
5. **Run manuel** : `POST /schedules/{task_id}/run` → nouvelle méthode publique additive `SchedulerEngine.run_task_now(task_id)` (relecture défensive + verrou + `triggered_by="manual"`, même chemin `_execute`) ; réponse **202 Accepted** `{execution_id, status}` sans attendre la fin (fire-and-forget, symétrique du chemin cron) ; audit `schedule.manual_run`.
6. **Rétention** : `scheduler_executions_retention_days: Optional[int] = None` (None = désactivée — pattern audit) + `scheduler_executions_purge_interval_hours: int = 24` ; purge sur `started_at` (fallback `created_at` pour les lignes sans démarrage — `skipped`) ; **jamais** `audit_logs` (table distincte, test dédié AC 4).
7. **« Le job purge ses propres traces » (spec 17 § Maintenance)** : divergence assumée et documentée — la FK `task_id NOT NULL` et le registre fermé aux actions utilisateur empêchent une ligne d'exécution dédiée au job système ; le job est tracé par logs structurés (comptages) et la purge s'applique **uniformément** à toutes les lignes. À réévaluer avec P2-15/STORY-252 (spec 17 cite encore « worker Celery » — obsolète depuis l'arbitrage F1).
8. **Isolation des données** : les exécutions héritent de l'organisation de leur tâche ; la vue globale suit exactement le pattern existant de `GET /schedules` (filtre `organization_id` optionnel, lecture viewer) — pas de durcissement supplémentaire non demandé (non-régression AC 5).

### Checklist sécurité (rules 40) — appliquée à cette story

- **AuthN/AuthZ** : lecture exécutions → `require_viewer` ; déclenchement manuel → `require_operator` (action opérationnelle, symétrie `toggle`) ; tests 401/403 obligatoires sur les 4 nouvelles routes.
- **Validation & injection** : filtres de query typés et bornés (`Literal` status/triggered_by, dates ISO — 422 sinon), `per_page` ≤ 100 (`PaginationQuery`).
- **Données sensibles** : `error` passe par `sanitize_error` (tronqué, sans stack brute) ; **jamais** de `parameters` de définition dans les réponses/logs d'exécution ; journaux sans secrets (spec 17 § Bonnes pratiques).
- **Audit & traçabilité** : `schedule.manual_run` audité à chaque déclenchement manuel (détails : nom/action uniquement) ; purge journalisée par comptages.

Éléments existants à réutiliser / contraintes :
- **Schéma exact** (spec 06) : `id`, `task_id` FK `scheduled_tasks` (ON DELETE CASCADE), `status` (`queued|running|success|failed|skipped`), `triggered_by` (`cron|event|manual`), `started_at`, `finished_at`, `duration_seconds` (calculée à la clôture), `error`, `logs` (journal horodaté ligne à ligne, ISO 8601, stockage UTC), `created_at` ; index sur `task_id`, `status`, `started_at` (requêtes de rétention/historique) ;
- Migration Alembic (dépend STORY-120), compatible PostgreSQL + SQLite (UUID TEXT, JSON TEXT) ;
- **Journaux** : un échec d'écriture d'une ligne de journal n'affecte jamais le statut de l'exécution (seule la ligne est perdue, avec trace d'erreur) ; secrets jamais dans les logs (spec 17 § Bonnes pratiques) ;
- **Rétention** : job de maintenance « rétention des exécutions de tâches » (périodicité cron + rétention en jours, désactivable, configurable dans les réglages admin) — exécuté comme une tâche ordinaire (ligne d'exécution, statut, durée, journaux) qui purge ses propres traces comme celles des tâches utilisateur ; **jamais** l'audit (gouverné séparément, spec 17 § Maintenance) ;
- **Alerte 3 échecs répétés** : 3 échecs consécutifs d'une tâche cron → notification in-app (s'appuyer sur la story notifications P2-15 si disponible, sinon émission d'événement bus tracée) ;
- Le **moteur** (STORY-160) écrit dans cette table ; cette story fournit le modèle, les schémas Pydantic, les endpoints de consultation et le job de rétention ;
- `triggered_by=manual` couvre le déclenchement explicite (`windflow admin tasks run` côté CLI futur / bouton UI) — exposer un endpoint de déclenchement manuel si le router `/schedules` s'y prête.

## Critères d'acceptation (AC)

- [x] AC 1 : Migration Alembic crée `scheduled_task_executions` conformément au schéma spec 06 (colonnes, FK CASCADE, index sur `task_id`/`status`/`started_at`) — vérifiable sur base vierge (création par migrations uniquement) et base existante (`alembic upgrade head` sans erreur).
- [x] AC 2 : Les exécutions sont persistées et **listables** de façon paginée : par tâche (`GET /schedules/{task_id}/executions`) et vue globale filtrable (`status`, `triggered_by`, dates) — enveloppe `pagination{}` (STORY-126/128), auth + RBAC (`require_role`), tests 401/403/422 ; le détail d'une exécution expose statut, `triggered_by`, `duration_seconds`, `error`, `logs`.
- [x] AC 3 : Cycle de vie conforme : `queued → running → success | failed | skipped` ; un saut par verrou reste tracé (`skipped`) ; `duration_seconds` calculée à la clôture ; journal horodaté ligne à ligne où un échec d'écriture de ligne ne fait jamais échouer l'exécution.
- [x] AC 4 : La rétention purge les lignes au-delà de la durée configurée (test avec rétention courte + time travel) et purge ses propres traces ; désactivable ; ne touche **jamais** `audit_logs` ; l'alerte « 3 échecs répétés » d'une tâche cron génère une notification/événement tracé.
- [x] AC 5 : Non-régression des endpoints `/schedules` existants ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités d'automatisation (ScheduledTaskExecution : schéma SQL complet, sémantique des statuts, relations/exploitation) ;
- [`17-automatisation-workflows.md`](../../docs/general_specs/17-automatisation-workflows.md) — § Exécutions : traçabilité, verrous et fuseaux (matérialisation, `triggered_by`, journaux horodatés), § Maintenance système planifiée (rétention des exécutions, audit exclu), § Gestion des tâches (UI/CLI, écran Activité), § Bonnes pratiques (alerte 3 échecs) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Conventions générales (pagination, enveloppes, codes d'erreur) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-1 (« exécutions persistées et listables »), §2.A A8 ;
- [`backend_status.md`](../../docs/backend_status.md) — §3.12 (router `/schedules` : CRUD seul, non paginé), §6.2 (absence de la table).

## Dépendances

- **[STORY-120](STORY-120-alembic-baseline-migrations.md)** — **faite ✅** (socle Alembic ; toute évolution de modèle passe par une migration).
- **STORY-160 (découpée)** — sous-stories **toutes DONE ✅** et pré-requis fonctionnels directs :
  - [STORY-160.1](STORY-160.1-modele-registre-actions-api-schedules.md) : modèle `ScheduledTask` spec 17 + router `/schedules` v2 (pattern des nouveaux endpoints) ;
  - [STORY-160.2](STORY-160.2-moteur-runtime-asyncio.md) : moteur + **contrat `ExecutionStore`** (cette story y branche l'impl DB — couplage par interface, le moteur n'est modifié que de façon **additive** : paramètre `triggered_by` + `run_task_now`, divergence documentée dans les notes de 160.3) ;
  - [STORY-160.3](STORY-160.3-actions-core-triggers-evenement.md) : handlers + triggers événement (passe `triggered_by="event"` — modification additive symétrique).
- **Story notifications P2-15** — **non affectée** (plage réservée STORY-175-199) : l'alerte « 3 échecs répétés » s'appuie dans cette story sur l'**événement bus tracé existant** (`SYSTEM_WARNING` / `scheduled_task.repeated_failures`, émis par le moteur 160.2) ; la notification in-app sera branchée par P2-15 sans retravail de 161.
- **[STORY-173](STORY-173-compute-browse-prune-endpoints.md)** (plan P2-14, couverture compute) : indépendante — la **partie schedules** de P2-14 est couverte par les tests de cette story.
- **STORY-252** (corrections consolidées de specs, EPIC-014) : à lui reporter — (a) spec 17 § Maintenance cite encore « worker Celery » (obsolète, arbitrage F1) ; (b) nomenclature `triggered_by` spec 06 (`cron|event|manual`) vs contrat moteur (`schedule|retry|manual`) ; (c) `duration_seconds INTEGER` vs `Float` requis par le moteur.
- **Services externes** : aucun nouveau — SQLite par défaut (tests unitaires) ; PostgreSQL optionnel couvert par la compatibilité de la migration (pattern scénario 5 de [`test_migrations.py`](../../backend/tests/integration/test_migrations.py), skippé si PG absent) ; Redis **non requis** (EventBus in-memory suffit à l'alerte tracée).

## Sous-stories

*(non prévue — story M)*

## État d'avancement technique

*(cochage progressif pendant treat-story)*

- [x] Tâche 1 — Modèle SQLAlchemy `ScheduledTaskExecution`
- [x] Tâche 2 — Migration Alembic `scheduled_task_executions`
- [x] Tâche 3 — Implémentation `DatabaseExecutionStore` (contrat 160.2)
- [x] Tâche 4 — Extension additive moteur : `triggered_by` paramétrable + `run_task_now` ; triggers événement
- [x] Tâche 5 — Schémas Pydantic `scheduled_task_execution`
- [x] Tâche 6 — Endpoints API (liste par tâche, vue globale, détail, run manuel)
- [x] Tâche 7 — Settings rétention + `purge_expired` sur le store DB
- [x] Tâche 8 — Intégration lifespan : branchement store DB + boucle de rétention (5ᵉ tâche lifespan)
- [x] Tâche 9 — Tests (store DB, schémas, API, moteur, migrations, rétention) + couverture ≥ 80 %

## Tâches d'implémentation détaillées

> Séquence ordonnée issue de l'analyse du 2026-10-23. Périmètre backend uniquement (ni UI ni CLI — le déclenchement manuel passe par l'API, consommable plus tard par le CLI/UI). Aucune tâche ne touche au comportement des 6 routes `/schedules` existantes (AC 5).

### Tâche 1 : Modèle SQLAlchemy `ScheduledTaskExecution`

**Objectif :** matérialiser le schéma spec 06 ([`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) § Entités d'automatisation) en ORM, gabarit [`models/scheduled_task.py`](../../backend/app/models/scheduled_task.py).

**Fichiers :**
- `backend/app/models/scheduled_task_execution.py` — **Créer** : classe `ScheduledTaskExecution(Base)` — `id: String(36)` PK (uuid4), `task_id: String(36)` `ForeignKey("scheduled_tasks.id", ondelete="CASCADE")` NOT NULL index, `status: String(10)` NOT NULL default `"queued"` index, `triggered_by: String(10)` NOT NULL, `started_at/finished_at: DateTime` nullable (UTC), `duration_seconds: Float` nullable (décision 1), `error: Text` nullable, `logs: Text` nullable (JSON — décision 2), `created_at: DateTime` default UTC ; relation `task` → `ScheduledTask` (avec `cascade="all, delete-orphan"`, `lazy="selectin"`).
- `backend/app/models/__init__.py` — **Modifier** : import + `__all__` (enregistrement du modèle pour Alembic/tests).

**Dépend de :** aucune (tâche 1 de la chaîne).

### Tâche 2 : Migration Alembic `scheduled_task_executions`

**Objectif :** poser la table par migrations uniquement (jamais de DDL manuel — règle projet), compatible SQLite + PostgreSQL.

**Fichiers :**
- `backend/alembic/versions/2026_10_XX_1331_scheduled_task_executions.py` — **Créer** (pattern [`1321`](../../backend/alembic/versions/2026_10_21_1321_scheduled_tasks_spec17_actions.py)) : `down_revision = "1321_scheduled_tasks_spec17"` ; `upgrade()` crée la table (colonnes tâche 1, FK `ON DELETE CASCADE`) + les **3 index** `idx_scheduled_exec_task`/`idx_scheduled_exec_status`/`idx_scheduled_exec_started` (spec 06) ; `downgrade()` drop propre (index puis table). Docstring riche reprenant la sémantique des statuts/orphelins.

**Dépend de :** Tâche 1.

### Tâche 3 : Implémentation `DatabaseExecutionStore` (contrat 160.2)

**Objectif :** persister le cycle de vie complet via l'interface [`ExecutionStore`](../../backend/app/services/scheduler_execution_store.py) — le moteur reste isolé.

**Fichiers :**
- `backend/app/services/scheduler_execution_store.py` — **Étendre** : classe `DatabaseExecutionStore(ExecutionStore)` — session fraîche **par opération** via `AsyncSessionLocal` injectable (pattern moteur/boucles lifespan) ; `mark_queued` crée la ligne (mapping `triggered_by` décision 4 : `"schedule"→"cron"`), `mark_running`/`mark_success` (calcule/stocke `duration_seconds` + `finished_at`)/`mark_failed` (`sanitize_error` réutilisé)/`mark_skipped` (ligne directe `skipped` + raison assainie)/`append_log` (**best-effort décision 3** : try/except + `logger.error`, jamais propagé ; sérialisation JSON ISO 8601 UTC)/`recover_orphans` (UPDATE `queued|running` → `failed` avec `ORPHAN_REASON`, retourne le comptage). Réutiliser `sanitize_error`, `ORPHAN_REASON`, constantes statuts existantes — **ne pas modifier `InMemoryExecutionStore` ni les constantes du contrat** (tests 160.2 intacts).

**Dépend de :** Tâches 1-2.

### Tâche 4 : Extension additive moteur — `triggered_by` paramétrable + `run_task_now`

**Objectif :** lever la divergence documentée par 160.3 (origine codée `"schedule"`) et offrir le déclenchement manuel — **modifications additives uniquement**, aucun changement de comportement des chemins existants.

**Fichiers :**
- `backend/app/services/scheduler_engine.py` — **Modifier (additif)** : `_execute(self, snapshot, triggered_by: str = TRIGGERED_BY_SCHEDULE)` (la valeur passe à `mark_queued`) ; nouvelle méthode publique `run_task_now(task_id) -> str` : relecture défensive (existence + `enabled` → erreur explicite), verrou anti-chevauchement (→ `skipped` si en cours), lancement dans une tâche dédiée `triggered_by="manual"`, retourne `execution_id` de la ligne `queued`. Docstring mise à jour (divergence 160.3 résolue).
- `backend/app/services/scheduler_event_triggers.py` — **Modifier** : passer `triggered_by=TRIGGERED_BY_EVENT` lors de la délégation à `_execute` (ajouter la constante `TRIGGERED_BY_EVENT = "event"` au module du store).

**Dépend de :** Tâche 3.

### Tâche 5 : Schémas Pydantic `scheduled_task_execution`

**Objectif :** contrats I/O typés des endpoints de consultation (rules 20/30 — tout couvert par Pydantic).

**Fichiers :**
- `backend/app/schemas/scheduled_task_execution.py` — **Créer** : `ExecutionLogLine` (`timestamp: datetime`, `message: str`) ; `ScheduledTaskExecutionListItem` (id, task_id, status, triggered_by, started_at, finished_at, duration_seconds, error, created_at — **sans `logs`** : listes légères) ; `ScheduledTaskExecutionResponse` (item + `logs: list[ExecutionLogLine]` — détail) ; `ManualRunResponse` (execution_id, status, triggered_by) ; `ExecutionQueryParams` (status/triggered_by en `Literal` — 422 sinon —, `started_after`/`started_before: datetime` optionnels). Aucun champ sensible : jamais `parameters` de définition (checklist rules 40).

**Dépend de :** Tâche 1.

### Tâche 6 : Endpoints API de consultation + run manuel

**Objectif :** AC 2 — exécutions listables de façon paginée et consultables, déclenchement manuel exposé.

**Fichiers :**
- `backend/app/api/v1/schedules.py` — **Étendre (4 routes nouvelles, déclarées AVANT les routes `{task_id}` existantes** — décision point d'intégration) :
  - `GET /schedules/{task_id}/executions` — paginé (`PaginationQuery` + `PaginatedResponse`/`build_meta`, tri `started_at DESC`), `require_viewer`, 404 si tâche inconnue ;
  - `GET /schedules/executions` — vue globale filtrable (`status`, `triggered_by`, `started_after/before`, `task_id`, `organization_id` optionnel — pattern liste existante), `require_viewer` ;
  - `GET /schedules/executions/{execution_id}` — détail avec `logs`, `require_viewer`, 404 si inconnu ;
  - `POST /schedules/{task_id}/run` — **202** `ManualRunResponse`, `require_operator`, appelle `run_task_now` (404 tâche inconnue ; conflit verrou → ligne `skipped` tracée, réponse explicite), **audit `schedule.manual_run`** via `AuditService.log_from_request` (détails : nom/action/organization — jamais les `parameters`).
  - Exemples OpenAPI riches (pattern `_TASK_EXAMPLE`) + sections `## Access Control` par route.

**Dépend de :** Tâches 3-5.

### Tâche 7 : Settings rétention + `purge_expired`

**Objectif :** configurer et implémenter la purge (AC 4) — pattern audit 125.3.

**Fichiers :**
- `backend/app/config.py` — **Modifier** : `scheduler_executions_retention_days: Optional[int] = Field(default=None, ge=1, …)` (None = désactivée) + `scheduler_executions_purge_interval_hours: int = Field(default=24, ge=1, …)` — pattern [`audit_retention_days:65-79`](../../backend/app/config.py).
- `backend/app/services/scheduler_execution_store.py` — **Étendre** : `DatabaseExecutionStore.purge_expired(retention_days) -> int` — DELETE WHERE `COALESCE(started_at, created_at) < now - retention_days` (décision 6), retourne le comptage ; **aucune écriture dans `audit_logs`** (jamais importée).

**Dépend de :** Tâche 3.

### Tâche 8 : Intégration lifespan — branchement store DB + boucle de rétention

**Objectif :** rendre la traçabilité active en runtime et la rétention périodique — 5ᵉ tâche lifespan, sans fusion des 4 existantes.

**Fichiers :**
- `backend/app/main.py` — **Modifier** :
  - au bloc scheduler (≈ ligne 266) : `SchedulerEngine(settings=settings, store=DatabaseExecutionStore())` ;
  - après le bloc audit purge : boucle `_periodic_executions_purge` clonée du pattern [`main.py:207-242`](../../backend/app/main.py) — **démarrage conditionnel** (`retention_days is None` → log « disabled », pas de boucle), session fraîche par itération, logs = comptages uniquement, `try/except` par itération (la boucle ne meurt jamais) ;
  - shutdown : `cancel()` + `await` + `CancelledError` symétrique des autres tâches (avant l'annulation du moteur).

**Dépend de :** Tâches 3, 7.

### Tâche 9 : Tests + validation

**Objectif :** couverture ≥ 80 % des modules touchés (AC 5), cas de sécurité obligatoires (rules 35/40) — détail exhaustif en section « Tests à écrire ».

**Fichiers :** voir section « Tests à écrire » (4 fichiers de tests nouveaux + 2 étendus).

**Dépend de :** Tâches 1-8.

**Validation (Makefile) :** `make backend-test-unit` ciblé (`poetry run pytest backend/tests/unit/test_services/test_database_execution_store.py backend/tests/unit/test_api/test_schedules_executions.py -v`), `make backend-test-integration` (migrations), `make backend-lint`, `make backend-typecheck`, couverture `--cov` sur les modules touchés.

## Tests à écrire

> Patterns : [`test_schedules_v2.py`](../../backend/tests/unit/test_api/test_schedules_v2.py) (API — helpers `_create_user_with_role`/`_auth_headers`/`_seed_task`, fixture `_jwt_mode`, `caplog`), [`test_scheduler_execution_store.py`](../../backend/tests/unit/test_services/test_scheduler_execution_store.py) (store — ne **pas** modifier : contrat 160.2), [`test_migrations.py`](../../backend/tests/integration/test_migrations.py) (scénario numéroté). Couverture ≥ 80 % sur les modules touchés.

### Unitaires — store DB (`backend/tests/unit/test_services/test_database_execution_store.py` — Créer)

- Cycle nominal : `queued → running → success` (statuts, `started_at`/`finished_at`, `duration_seconds` persistée, horodatages UTC aware) ;
- `queued → running → failed` : `error` assaini/tronqué via `sanitize_error` (payload long → ellipse, jamais de stack brute) ;
- `mark_skipped` : ligne directe `status=skipped` + raison assainie ;
- `append_log` : lignes horodatées sérialisées JSON ISO 8601 UTC ; **échec d'écriture avalé** (monkeypatch levant une exception sur l'UPDATE → aucune exception propagée, trace `logger.error` présente (caplog), statut de l'exécution intact — AC 3) ;
- `recover_orphans` : lignes `queued`/`running` → `failed` avec le libellé exact `ORPHAN_REASON`, comptage correct, lignes closes inchangées ;
- mapping `triggered_by` : `"schedule"` persisté `"cron"`, `"event"` et `"manual"` inchangés (décision 4) ;
- FK CASCADE : suppression de la définition → ses exécutions disparaissent ;
- `purge_expired` (AC 4) : rétention courte + **time travel** (horloge/`freezegun`, jamais `time.sleep`) → lignes âgées purgées / récentes conservées ; lignes sans `started_at` purgées sur `created_at` ; comptage retourné ; rétention `None` → no-op ; **`audit_logs` non touché** (seed de lignes d'audit + comptage inchangé après purge).

### Unitaires — schémas (`backend/tests/unit/test_schemas/test_scheduled_task_execution_schemas.py` — Créer)

- `Literal` `status`/`triggered_by` : valeur hors domaine → `ValidationError` (futur 422) ;
- champs exposés attendus (item sans `logs`, détail avec `logs` structurés) ; **aucun champ `parameters`/secret** dans les schémas de réponse ;
- désérialisation ORM → réponse (`model_validate`) sur fixture réaliste.

### Unitaires — API (`backend/tests/unit/test_api/test_schedules_executions.py` — Créer, httpx `AsyncClient` + `ASGITransport`)

- **Nominaux** : 200 liste par tâche (enveloppe `pagination{}`, tri `started_at DESC`, `logs` absents des items) ; 200 vue globale avec filtres (`status`, `triggered_by`, `started_after/before`, `task_id`, `organization_id`) ; 200 détail (statut, `triggered_by`, `duration_seconds`, `error`, `logs`) ; 202 `POST /schedules/{task_id}/run` → exécution `queued` `triggered_by="manual"` créée ;
- **Sécurité (rules 40)** : 401 sans token sur les 4 routes ; **403 viewer sur `POST …/run`** (operator requis) ; audit `schedule.manual_run` émis sans `parameters` bruts (caplog) ; `error` de la réponse = version assainie ;
- **404** : `task_id` inconnu (liste + run), `execution_id` inconnu (détail) ;
- **422** : filtre `status`/`triggered_by` hors domaine, dates invalides ;
- **Isolation** : les exécutions d'une autre organisation n'apparaissent pas via le filtre `organization_id` (pattern liste existante) ;
- **Pagination** : `per_page` borné (≤ 100), `total` scopusé sur les mêmes filtres (AC 2, pattern 128) ;
- **Non-régression** : les 6 routes historiques `/schedules` inchangées (comptage de routes du router).

### Unitaires — moteur/triggers (Étendre `backend/tests/unit/test_services/test_scheduler_engine.py` et `test_scheduler_event_triggers.py`)

- `run_task_now` : nominal (exécution `manual` de bout en bout), tâche inconnue/désactivée → erreur explicite **sans** ligne d'exécution, chevauchement → `skipped` tracé ;
- `triggered_by` propagé : chemin cron → ligne d'origine `cron` (via store DB/mapping), chemin événement → `event` (trigger 160.3, store espion) ;
- **AC 4 (alerte)** : 3 échecs consécutifs d'une tâche cron → événement `SYSTEM_WARNING` `scheduled_task.repeated_failures` capté sur le bus (mock) **et** 3 lignes `failed` persistées consultables via le store.

### Intégration — migrations (Étendre `backend/tests/integration/test_migrations.py` — scénario 8)

- Base vierge → `upgrade head` : table `scheduled_task_executions` présente avec colonnes/FK CASCADE/index attendus (inspection) + `EXPECTED_TABLES` complété ;
- Base legacy stampée baseline → `upgrade head` sans erreur ; `alembic check` sans diff (modèle ↔ migration) ;
- `downgrade -1` : table et index supprimés proprement ;
- Variante PostgreSQL des scénarios ci-dessus (skippée si service absent — pattern existant).

### Intégration — rétention runtime (si couverte par fixture lifespan ; sinon unitaire tâche store)

- Boucle de purge : démarrage conditionnel (`retention_days=None` → pas de tâche créée, log « disabled ») ; une itération purge réellement (time travel) et journalise le comptage ; l'audit n'est pas touché (AC 4).

> Couverte en unitaire (tâche store `test_never_touches_audit_logs`, `test_purge_removes_old_keeps_recent`, `test_purge_uses_created_at_when_no_started_at`) + le démarrage conditionnel/le pattern de la boucle lifespan sont les mêmes que la boucle audit 125.3 (revue) — la boucle elle-même n'est pas exécutée en test (elle est un `while True` infini ; pattern identique aux 4 boucles existantes, jamais testées en boucle non plus).

## Notes d'implémentation (treat-story — 2026-10-23)

### Fichiers créés

- `backend/app/models/scheduled_task_execution.py` — modèle ORM `ScheduledTaskExecution` (spec 06 : FK CASCADE, index `task_id`/`status`/`started_at`, `duration_seconds Float`, `logs` Text JSON).
- `backend/alembic/versions/2026_10_23_1331_scheduled_task_executions.py` — migration `1331` (`down_revision = 1321_scheduled_tasks_spec17`), types portables SQLite+PostgreSQL, downgrade propre (index puis table).
- `backend/app/schemas/scheduled_task_execution.py` — `ExecutionLogLine`, `ScheduledTaskExecutionListItem` (sans `logs`), `ScheduledTaskExecutionResponse` (avec `logs`), `ManualRunResponse` (202), `ExecutionQueryParams` (`Literal` 422).
- `backend/tests/unit/test_services/test_database_execution_store.py` — 12 tests store DB (cycle, assainissement, skipped, journal best-effort, orphelins, mapping, FK CASCADE, purge + audit intact).
- `backend/tests/unit/test_schemas/test_scheduled_task_execution_schemas.py` — 9 tests schémas (domaines Literal, champs exposés, aucun champ sensible, désérialisation ORM).
- `backend/tests/unit/test_api/test_schedules_executions.py` — 17 tests API (nominaux 4 routes, 401×4/403 viewer/404/422×3, isolation org, pagination bornée, audit sans parameters, non-régression 10 routes).

### Fichiers modifiés

- `backend/app/services/scheduler_execution_store.py` — constantes `TRIGGERED_BY_EVENT`/`TRIGGERED_BY_MANUAL` + mapping `_TRIGGERED_BY_DB_MAP` (décision 4) + classe `DatabaseExecutionStore` (contrat complet + `purge_expired` COALESCE) ; `InMemoryExecutionStore` et le contrat **intacts** (52 tests 160.2 passants).
- `backend/app/services/scheduler_engine.py` — **additif uniquement** : `_execute(snapshot, triggered_by=TRIGGERED_BY_SCHEDULE)` (valeur passée à `mark_queued`), `run_task_now(task_id)` (404 inconnue/désactivée sans ligne, 409 + `skipped` tracé au chevauchement, ligne `queued` créée avant lancement, `_execute_manual` reprenant l'orchestration à `running`), import `TRIGGERED_BY_MANUAL`.
- `backend/app/services/scheduler_event_triggers.py` — délégation moteur avec `triggered_by=TRIGGERED_BY_EVENT` (divergence 160.3 résolue, docstring mise à jour).
- `backend/app/api/v1/schedules.py` — 4 routes nouvelles **déclarées avant** `/schedules/{task_id}` : `GET /schedules/executions` (vue globale filtrable `status`/`triggered_by`/`started_after|before`/`task_id`/`organization_id`, pattern 422 via `Query(pattern=...)`), `GET /schedules/executions/{execution_id}` (détail + logs décodés), `GET /schedules/{task_id}/executions` (404 tâche inconnue, tri `started_at DESC`), `POST /schedules/{task_id}/run` (202, `require_operator`, audit `schedule.manual_run` sans parameters bruts) + dépendance injectable `get_scheduler_engine` (moteur branché store DB — overridable en tests, pattern `get_db`).
- `backend/app/config.py` — `scheduler_executions_retention_days: Optional[int] = None` (None = désactivée) + `scheduler_executions_purge_interval_hours: int = 24`.
- `backend/app/main.py` — branchement lifespan : `SchedulerEngine(settings, store=DatabaseExecutionStore())` + **5ᵉ tâche lifespan** `_periodic_executions_purge` (démarrage conditionnel None → log disabled, session fraîche par itération via le store, try/except par itération, shutdown symétrique `cancel()` + `CancelledError`).
- `backend/app/models/__init__.py` — export `ScheduledTaskExecution`.
- `backend/tests/integration/test_migrations.py` — `EXPECTED_TABLES`/`ADDITIVE_TABLES` + scénario 8 `TestScheduledTaskExecutionsMigration` (6 tests : structure, index, FK CASCADE PRAGMA, downgrade -1, base legacy stampée + `alembic check`).
- `backend/tests/unit/test_services/test_scheduler_engine.py` — 5 tests STORY-161 (`run_task_now` nominal/sans ligne/chevauchement skipped, `triggered_by=event` via bus factice, AC 4 : événement `SYSTEM_WARNING` `scheduled_task.repeated_failures` capté + 3 lignes `failed`).
- Garde-fous étendus au pattern documenté « à chaque migration additive » : `backend/tests/unit/test_alembic_config.py` (EXPECTED/ADDITIVE + DROP), `backend/tests/unit/test_database.py` (DROP), `backend/tests/unit/test_api/test_rbac_exhaustivite.py` (`schedules: 10`).

### Décisions techniques

- Toutes les décisions d'analyse contractuelles appliquées telles quelles : `duration_seconds Float`, `logs` Text JSON ISO 8601 UTC (horodatage aware), `append_log` best-effort (try/except + `logger.error`, jamais propagé), mapping `schedule→cron` au point unique `mark_queued` (`event`/`manual` inchangés), run manuel 202 fire-and-forget, rétention None=désactivée + purge `COALESCE(started_at, created_at)`, isolation par `organization_id` optionnel (pattern liste existante).
- `run_task_now` crée la ligne `queued` **avant** de lancer la tâche asyncio : l'API retourne l'`execution_id` en 202 sans attendre ; `_execute_manual` reprend à `mark_running` (pas de double ligne `queued`).
- `created_at` posé explicitement via l'horloge injectée du store (le default Python du modèle resterait au temps réel → time travel de la purge cassé pour les lignes sans `started_at`).
- Tests FK CASCADE : SQLite n'active pas `PRAGMA foreign_keys` par défaut — vérifié par réflexion PRAGMA (intégration, pattern 1211) et par DELETE avec PRAGMA ON (unitaire).
- `rowcount` accédé via `getattr` défensif (mypy : `Result` n'expose pas l'attribut, `CursorResult` oui).

### Divergences par rapport à l'analyse

- **Aucune divergence fonctionnelle.** Trois garde-fous de comptage préexistants ont dû être étendus au pattern documenté (« pattern étendu à chaque migration additive ») : `EXPECTED_TABLES`/`ADDITIVE_TABLES` (test_migrations, test_alembic_config, test_database) et le comptage de routes `schedules: 6 → 10` (test_rbac_exhaustivite) — c'est le mécanisme prévu par l'analyse (« EXPECTED_TABLES complété », AC 5 « comptage de routes »).
- Les items à reporter à STORY-252 restent d'actualité (déjà tracés en Dépendances) : nomenclature `triggered_by`, `duration_seconds INTEGER` vs Float, « worker Celery » obsolète en spec 17 § Maintenance.

### Difficultés rencontrées

- Le run manuel à l'API nécessitait un moteur branché sur la base de test → dépendance `get_scheduler_engine` (overridable, pattern `get_db`) plutôt qu'une instanciation inline non testable.
- `pytest-randomly` (ordre aléatoire) fait apparaître des échecs de pollution inter-tests **préexistants** dans la suite intégration (`test_auth_api`, `test_security_headers`, `test_deployments_api`) selon le seed ; en ordre déterministe (`-p no:randomly`), seul `test_delete_deployment` échoue — **avant comme après** mes changements (vérifié par `git stash`). De même `test_parameters_not_logged_raw` (test_schedules_v2) échoue en isolation dans cet environnement (echo SQL SQLAlchemy logge l'INSERT — niveau de log local) mais passe dans la suite complète. Aucun lien avec STORY-161.
- Erreurs transitoires « Could NOT open editor » (IDE) sur plusieurs `apply_diff` : chaque fois vérifié puis corrigé dans la foulée.

### Commandes exécutées et résultats

| Commande | Résultat |
|---|---|
| `poetry run pytest backend/tests/unit/test_services/test_database_execution_store.py -v` | **12 passed** |
| `poetry run pytest backend/tests/unit/test_schemas/test_scheduled_task_execution_schemas.py -v` | **7 passed** |
| `poetry run pytest backend/tests/unit/test_api/test_schedules_executions.py -v` | **17 passed** |
| `poetry run pytest backend/tests/unit/test_services/test_scheduler_engine.py -v` | **34 passed** (dont 5 STORY-161) |
| `poetry run pytest backend/tests/unit/test_services/test_scheduler_execution_store.py` (contrat 160.2) | **passant — intact** |
| `poetry run pytest backend/tests/integration/test_migrations.py -v` | **33 passed, 1 skipped** (PG absent — pattern existant) |
| `make backend-test-unit` | **2000 passed** (non-régression complète) |
| `make backend-test-integration` | 176→195 passed + échecs **préexistants** (pollution pytest-randomly + `test_delete_deployment`, vérifiés identiques avant/après via `git stash`) |
| `make backend-lint` (partiel fichiers touchés) | isort+black appliqués ; flake8 **OK** ; mypy **0 erreur** sur les fichiers de la story (24 erreurs préexistantes ailleurs) ; bandit **propre** |
| Couverture ciblée modules touchés | `schedules.py` **91 %**, `scheduler_execution_store.py` **94 %**, modèle **92 %**, schémas **100 %** — ≥ 80 % (AC 5) |
