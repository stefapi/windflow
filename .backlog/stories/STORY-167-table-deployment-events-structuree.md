# STORY-167 : `deployment_events` — table dédiée remplaçant la colonne texte `Deployment.logs`, events typés horodatés, endpoint d'association et rétention (P2-7 — axe A15)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-7 (axe A15, rapport §4) — ampleur **M**

## Description

En tant qu'utilisateur WindFlow, je veux que les événements de déploiement soient **persistés dans une table dédiée `deployment_events`** (events typés, horodatés, avec niveau et données JSON) remplaçant la colonne texte `Deployment.logs` — dont les données existantes sont migrées — et exposés via un endpoint paginé avec rétention, afin de pouvoir requêter, filtrer et purger l'historique des déploiements au lieu d'un amas de texte non structuré.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §6.2) : le modèle [`Deployment`](../../backend/app/models/deployment.py:34) porte les logs dans une **colonne texte** (`logs`, `error`) accumulée par [`deployment_service.py:23`](../../backend/app/services/deployment_service.py:23) ; la spec 06 exige une table `deployment_events` (event_type, level, message, data, created_at) liée au déploiement ; la spec 04 exige des événements structurés persistés.

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- **Schéma exact** (spec 06) : `id`, `deployment_id` FK `deployments` (ON DELETE CASCADE), `event_type` (`pulling|deploying|health_check|success|error|rollback`), `level` (`debug|info|warning|error`), `message` TEXT, `data` JSON, `created_at` ; index sur `deployment_id` et `created_at` ;
- **Migration des données** : la colonne texte `Deployment.logs` existante est migrée (découpage en lignes d'events `info` datées au mieux — l'horodatage fin n'existe pas dans le texte, choix à documenter) ; **la colonne logs texte reste pour le payload brut** (critère P2-7 : « la colonne logs texte reste pour le payload brut ») — double écriture ou redécoupage à trancher par l'analyse ;
- **Émission** : brancher l'écriture des events sur le pipeline existant ([`deployment_events.py:22`](../../backend/app/services/deployment_events.py:22) — service d'émission bus ; [`DeploymentService.update_status()`](../../backend/app/services/deployment_service.py:23), [`background_tasks.py:24`](../../backend/app/tasks/background_tasks.py:24) étapes pulling/deploying/…) ; un refus de gate (STORY-170) produira aussi des lignes `deployment_events` (spec 11 § gates) ;
- **Endpoint d'association aux événements bus** (mission) : `GET /deployments/{id}/events` paginé filtrable (par `event_type`, `level`, dates) — complète `GET /deployments/{id}/logs` existant ; enveloppes (STORY-126) + pagination (STORY-128) + RBAC ;
- **Rétention** : job de maintenance « rétention des événements/déploiements » (spec 17 — périodicité + rétention en jours, désactivable) ; s'exécute comme tâche ordinaire ; purge les anciens `deployment_events` — coordonné avec le scheduler (STORY-160/161) ;
- Lié à **STORY-162** (nomenclature : les statuts `success` émettent `deployment.succeeded` ; la table typée aligne `event_type` sur les étapes réelles) ; le streaming WS `DEPLOYMENT_LOGS_UPDATE` n'est pas impacté (transport ≠ persistance) ;
- Alembic (STORY-120) requis pour la migration.

## Critères d'acceptation (AC)

- [ ] AC 1 : Migration Alembic crée `deployment_events` (schéma spec 06 : colonnes, FK CASCADE, index `deployment_id`/`created_at`) et **migre les données** de la colonne texte existante — test : un déploiement historique avec logs texte voit ses lignes converties en events requêtables, sans perte de contenu.
- [ ] AC 2 : Un déploiement de test produit une **séquence d'events requêtable paginée** : `GET /deployments/{id}/events` retourne les étapes dans l'ordre (pulling → deploying → success/error), chaque event portant `event_type`, `level`, `message`, `data`, `created_at` ; filtres par type/niveau/dates fonctionnels ; enveloppe `pagination{}` ; tests 401/403 (RBAC — lecture viewer+) /404.
- [ ] AC 3 : Le pipeline écrit désormais les events structurés à chaque étape clé (status change, étapes d'exécution, erreur, rollback) tout en conservant la colonne texte pour le payload brut ; les refus de gate éventuels (STORY-170) y laissent une trace typée.
- [ ] AC 4 : La **rétention** purge les events au-delà de la durée configurée (test avec rétention courte + time travel), désactivable, tracée comme tâche de maintenance ; `GET /deployments/{id}/logs` existant non cassé (non-régression consommateurs WS/REST).
- [ ] AC 5 : Couverture ≥ 80 % sur les modules touchés (modèle, service, endpoint, migration testée sur fixtures) ; build + lint + tests passent.

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

## Sous-stories

*(non prévue — story M)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
