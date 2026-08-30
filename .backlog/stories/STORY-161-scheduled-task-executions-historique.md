# STORY-161 : Table `scheduled_task_executions` — historique des exécutions, endpoints de consultation et rétention (P2-1, partie traçabilité)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-1 (axe A8, rapport §12) — ampleur **M** (découpe de P2-1 : persistance + consultation)

## Description

En tant qu'administrateur WindFlow, je veux que chaque exécution de tâche planifiée — par cron, par événement ou manuelle — soit **matérialisée** dans une table `scheduled_task_executions` (statut, déclencheur, horodatages, durée, erreur, journaux ligne à ligne) et consultable via des endpoints paginés, avec un job de purge/rétention configurable, afin de rendre l'automatisation exploitable (écran Activité, alerte « 3 échecs répétés ») au lieu de laisser les exécutions sans trace.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §6.2) : la table n'existe pas — le CRUD [`scheduler_service.py`](../../backend/app/services/scheduler_service.py:20) n'a aucun support d'exécution ; l'historique et la rétention spécifiés (spec 17) sont inexistants.

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- **Schéma exact** (spec 06) : `id`, `task_id` FK `scheduled_tasks` (ON DELETE CASCADE), `status` (`queued|running|success|failed|skipped`), `triggered_by` (`cron|event|manual`), `started_at`, `finished_at`, `duration_seconds` (calculée à la clôture), `error`, `logs` (journal horodaté ligne à ligne, ISO 8601, stockage UTC), `created_at` ; index sur `task_id`, `status`, `started_at` (requêtes de rétention/historique) ;
- Migration Alembic (dépend STORY-120), compatible PostgreSQL + SQLite (UUID TEXT, JSON TEXT) ;
- **Journaux** : un échec d'écriture d'une ligne de journal n'affecte jamais le statut de l'exécution (seule la ligne est perdue, avec trace d'erreur) ; secrets jamais dans les logs (spec 17 § Bonnes pratiques) ;
- **Rétention** : job de maintenance « rétention des exécutions de tâches » (périodicité cron + rétention en jours, désactivable, configurable dans les réglages admin) — exécuté comme une tâche ordinaire (ligne d'exécution, statut, durée, journaux) qui purge ses propres traces comme celles des tâches utilisateur ; **jamais** l'audit (gouverné séparément, spec 17 § Maintenance) ;
- **Alerte 3 échecs répétés** : 3 échecs consécutifs d'une tâche cron → notification in-app (s'appuyer sur la story notifications P2-15 si disponible, sinon émission d'événement bus tracée) ;
- Le **moteur** (STORY-160) écrit dans cette table ; cette story fournit le modèle, les schémas Pydantic, les endpoints de consultation et le job de rétention ;
- `triggered_by=manual` couvre le déclenchement explicite (`windflow admin tasks run` côté CLI futur / bouton UI) — exposer un endpoint de déclenchement manuel si le router `/schedules` s'y prête.

## Critères d'acceptation (AC)

- [ ] AC 1 : Migration Alembic crée `scheduled_task_executions` conformément au schéma spec 06 (colonnes, FK CASCADE, index sur `task_id`/`status`/`started_at`) — vérifiable sur base vierge (création par migrations uniquement) et base existante (`alembic upgrade head` sans erreur).
- [ ] AC 2 : Les exécutions sont persistées et **listables** de façon paginée : par tâche (`GET /schedules/{task_id}/executions`) et vue globale filtrable (`status`, `triggered_by`, dates) — enveloppe `pagination{}` (STORY-126/128), auth + RBAC (`require_role`), tests 401/403/422 ; le détail d'une exécution expose statut, `triggered_by`, `duration_seconds`, `error`, `logs`.
- [ ] AC 3 : Cycle de vie conforme : `queued → running → success | failed | skipped` ; un saut par verrou reste tracé (`skipped`) ; `duration_seconds` calculée à la clôture ; journal horodaté ligne à ligne où un échec d'écriture de ligne ne fait jamais échouer l'exécution.
- [ ] AC 4 : La rétention purge les lignes au-delà de la durée configurée (test avec rétention courte + time travel) et purge ses propres traces ; désactivable ; ne touche **jamais** `audit_logs` ; l'alerte « 3 échecs répétés » d'une tâche cron génère une notification/événement tracé.
- [ ] AC 5 : Non-régression des endpoints `/schedules` existants ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités d'automatisation (ScheduledTaskExecution : schéma SQL complet, sémantique des statuts, relations/exploitation) ;
- [`17-automatisation-workflows.md`](../../docs/general_specs/17-automatisation-workflows.md) — § Exécutions : traçabilité, verrous et fuseaux (matérialisation, `triggered_by`, journaux horodatés), § Maintenance système planifiée (rétention des exécutions, audit exclu), § Gestion des tâches (UI/CLI, écran Activité), § Bonnes pratiques (alerte 3 échecs) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Conventions générales (pagination, enveloppes, codes d'erreur) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-1 (« exécutions persistées et listables »), §2.A A8 ;
- [`backend_status.md`](../../docs/backend_status.md) — §3.12 (router `/schedules` : CRUD seul, non paginé), §6.2 (absence de la table).

## Dépendances

- **STORY-120** (Alembic avant toute migration de modèle).
- Étroitement couplée à **STORY-160** (le moteur écrit les exécutions) — analyse conjointe recommandée.
- Interagit avec la story notifications P2-15 (alerte 3 échecs, `notification.send`) et **STORY-173** (couverture schedules, plan P2-14).

## Sous-stories

*(non prévue — story M)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
