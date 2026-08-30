# STORY-120 : Alembic — baseline du schéma existant et `upgrade head` au démarrage à la place de `create_all` (P1-1)

**Statut :** TODO
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-1 (axe A1, rapports §4/§14) — ampleur **M**

## Description

En tant que développeur backend de WindFlow, je veux que le schéma de base de données soit géré exclusivement par des migrations Alembic (baseline du schéma existant, `alembic upgrade head` au démarrage/install) afin que toute évolution future du modèle (RBAC `user_organizations`, `refresh_tokens`, `api_keys`, `audit_logs`, `ssh_keys`, `environments`, modèle Hosts en P2…) soit versionnée, reproductible et applicable sur les installations existantes sans perte de données.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §6, §14) : il n'existe **aucun** dossier `backend/alembic/` — le schéma est créé par `Base.metadata.create_all()` via [`create_tables()`](../../backend/app/database.py:89) au démarrage. Conséquence : les changements de colonnes sur tables existantes ne sont **pas gérés** (un `create_all` ne modifie jamais une table existante). La spec de déploiement exige pourtant `alembic upgrade head` à l'installation ([`16-deploiement.md`](../../docs/general_specs/16-deploiement.md) : install.sh « initialise la base SQLite (migrations Alembic) », `docker compose exec -T windflow-api alembic upgrade head`).

Cette story est le **prérequis de toutes les migrations de modèle des vagues P1 et P2** (règle de dépendance du plan §4 : « Alembic avant toute migration de modèle »).

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- [`database.py`](../../backend/app/database.py:27) — moteur async SQLAlchemy + `session_factory` + [`create_tables()`](../../backend/app/database.py:89) (à remplacer) + `seed_tables()` ([`database_seed.py`](../../backend/app/database_seed.py)) ;
- ~10 modèles SQLAlchemy existants (cf. [`backend_status.md`](../../docs/backend_status.md) §6 — users, organizations, targets, stacks, deployments, plugins…) : la baseline doit les capturer **à l'identique** ;
- Alembic est déjà déclaré côté stack (rules 05 — SQLAlchemy 2.0 async + Alembic) ; vérifier la dépendance Poetry et la config async (`aiosqlite` / async engine dans `env.py`) ;
- `make migrate` existe déjà dans le Makefile (génération de migration) — doit devenir fonctionnel avec l'infra réelle ;
- Compatibilité **PostgreSQL + SQLite** requise pour les migrations (spec 06 § compatibilité) ;
- Compatibilité des installations existantes (plan §1.5 / §7.1) : baseline + `stamp` sur schéma existant, `create_all` retiré seulement après validation.

## Critères d'acceptation (AC)

- [ ] AC 1 : `backend/alembic/` est initialisé (config async compatible SQLite/PostgreSQL) avec une **migration baseline** reproduisant exactement le schéma des ~10 modèles existants ; sur une **base existante** : `alembic stamp baseline` puis démarrage → **aucun diff** (aucune tentative de recréation/altération, vérifiable via `alembic check` ou équivalent).
- [ ] AC 2 : Sur une **base vierge** : la création du schéma complet se fait **par les migrations uniquement** (`alembic upgrade head`) ; le [`create_all`](../../backend/app/database.py:89) nu est retiré du démarrage (remplacé par l'exécution des migrations au démarrage/install, seed préservé) ; plus aucun `create_all` nu dans le code (critère de done de l'epic).
- [ ] AC 3 : `make migrate` génère correctement une migration à partir des changements de modèles (testé sur un changement factice reverté ensuite) ; la CI exécute les migrations (base vierge → schéma complet).
- [ ] AC 4 : Tests de non-régression : démarrage sur base existante migrée → seed et comportements inchangés (login admin, org par défaut) ; `make lint` + `make backend-test` verts ; migrations compatibles SQLite **et** PostgreSQL.

## Références spécification

- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § migrations Alembic (compatibilité PostgreSQL + SQLite, exemple de migration `hosts`) et § « Modèle SQLAlchemy » ;
- [`docs/general_specs/16-deploiement.md`](../../docs/general_specs/16-deploiement.md) — § installation (`alembic upgrade head` par install.sh, commandes docker compose exec, mode léger, mode dev) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §6 (pas de `backend/alembic/`, `create_all` ligne 89), §14 (« Pas d'Alembic ») ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 « Vague P1 » — item P1-1, §2.A — item A1, §7.1 (baseline + stamp, retrait de `create_all` après validation).

## Dépendances

- Aucune (item racine de la vague P1). **Bloque** : STORY-121, STORY-123, STORY-124, STORY-125, STORY-131 (toute migration de modèle) et, en cascade, les migrations P2 (STORY-160+).

## Sous-stories

*(section réservée — STORY-120 ampleur M, découpe non prévue a priori ; plage 132-159 disponible si nécessaire)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
