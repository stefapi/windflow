# STORY-166.4 : Axe `origin` + table `environments` + `stacks.environment_id` + `Stack.git_url` (P2-4, partie modèle piloté — STORY-166 découpée)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-166 ([ABANDONED — découpe proactive post-analyse le 2026-10-24](STORY-166-migration-target-vers-host-origin.md))
**Item plan :** P2-4 (F4 étape 2 — axes A14, D2, partie origine C13) — ampleur **M-L**

> **Périmètre (découpe)** : cette sous-story reprend le **volet entités pilotées** de STORY-166 — pose métier de l'axe `origin` (`managed`/`adopted`/`external`) sur `hosts` *(colonne déjà créée par [STORY-166.1](STORY-166.1-modele-host-enums-migration-alembic.md))* et **`stacks`**, **adoption marque `origin=adopted`**, création de la table **`environments`** (A14 — n'existe pas en base, vérifié), `stacks.environment_id` + `hosts.environment_id`, `Stack.git_url` optionnel (D2). Couvre l'**AC 3 (partie origin) et AC 4 (partie environments/git_url) de la mère**. L'API `environments` reste **minimale** (table + rattachement — le CRUD multi-env complet est hors périmètre, plan §6) ; le GitOps complet est hors périmètre (plugin Git, Roadmap).

## Description

En tant qu'administrateur WindFlow, je veux que l'axe `origin` soit réellement posé sur les entités pilotées (l'adoption marque `origin=adopted`), que la table `environments` existe avec le rattachement des stacks (`stacks.environment_id`) et des hosts (`hosts.environment_id`), et que `Stack.git_url` soit persisté — afin que le modèle compute spec 03 (matrice profil × origine) et le rattachement environnement (A14) soient effectifs.

**Problème constaté** : [`adoption_service.py`](../../backend/app/services/adoption_service.py) ne pose **aucun** `origin` (seulement `tags=["adopted", ...]` + `target_id=LOCAL_TARGET_ID` — divergence n°4 de la mère) ; **aucune table `environments`** en base (aucun modèle Environment — STORY-121 ne l'a pas posée, vérifié) ; `Stack.git_url` absent (D2).

## Contexte technique

> Extrait de l'analyse STORY-166 (2026-10-24, `analyse-story`) — volet origin/environments, fondé sur le code réel du dépôt.

### État réel du code (exploration mère)

- [`services/adoption_service.py`](../../backend/app/services/adoption_service.py) : adoption d'un conteneur découvert → pose `tags` + rattachement `target_id=LOCAL_TARGET_ID` ; **l'axe `origin` est entièrement à créer** (pose `origin=adopted` sur stack/host résultants, P2-4) ;
- [`models/stack.py`](../../backend/app/models/stack.py) : pas de colonne `environment_id`, pas de `git_url` — à ajouter (migration) ;
- **Table `environments` à créer entièrement** — schéma canonique spec 06 : `id`, `name`, `type`, `organization_id` FK, `configuration`, `is_active`, **`UNIQUE(organization_id, name)`** ;
- `hosts.origin` : créé par 166.1 (schema complet) — ici : pose métier + défauts pertinents ;
- Détection de l'origine par runtime (labels WindFlow) — spec 03 § : à considérer pour l'adoption, sans surdimensionner.

### Décisions de découpe (clarifications vs tableau de la mère)

- `WorkloadOrigin` (enum) + colonne `hosts.origin` : **créés en 166.1** (une seule migration du schéma `hosts`) — cette sous-story fait la **pose métier** (adoption → `adopted`, création manuelle → `managed`, import externe → `external`) ;
- `stacks.origin` : colonne créée **ici** (migration dédiée, après celle de 166.1 — ordre des migrations à coordonner) ;
- ⚠️ **Renvoi fuseau STORY-160** : la surcharge timezone par Host (renvoyée par 160.x) est **tracée comme renvoi explicite** — à arbitrer : colonne ici ou story dédiée (non bloquant pour 160).

### Checklist sécurité (règle 40)

- `environments` rattachés à une organisation — isolation organisationnelle sur tout endpoint exposé (le cas échéant minimal : lecture interne) ;
- `Stack.git_url` : validation Pydantic URL (pas d'injection — pas de clone/exécution à ce stade, GitOps hors périmètre) ;
- L'axe `origin` n'expose pas de données sensibles ; audit de l'adoption conservé.

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend la partie origin de l'AC 3 de la mère)* : L'axe `origin` est en place — colonne sur `hosts` *(166.1)* et **`stacks`** (migration ici) avec défaut pertinent (`managed`) ; **l'adoption marque `origin=adopted`** : test — adoption d'un conteneur découvert → stack/host marqués `adopted`.
- [x] AC 2 *(reprend la partie environments/git_url de l'AC 4 de la mère)* : `environments` activés — table canonique (`UNIQUE(organization_id, name)`, FK organization) + rattachement des stacks (`stacks.environment_id`) et des hosts (`hosts.environment_id`) ; `Stack.git_url` optionnel persisté (validation URL).
- [x] AC 3 : Non-régression — adoption existante (tags, rattachement) conservée, déploiements intacts ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [`03-modele-compute.md`](../../docs/general_specs/03-modele-compute.md) — § Axe origine managed/adopted/external (matrice canonique), § Détection de l'origine par runtime (labels WindFlow) ;
- [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Environment (schéma canonique), § WorkloadOrigin ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §2.A A14, §2.D D2, §4 P2-4, §6 (CRUD multi-env hors périmètre).

## Dépendances

- **[STORY-166.1](STORY-166.1-modele-host-enums-migration-alembic.md)** (dur) — enum `WorkloadOrigin` + colonne `hosts.origin` ;
- **[STORY-166.3](STORY-166.3-services-host-scanners-ws.md)** (recommandé avant) — `adoption_service` renommé `host_*`, cette story modifie sa logique métier ;
- **STORY-103** ✔ (`env_vars_encrypted` déjà couvert — rien à faire ici) ;
- Coordination migrations : numéro de révision **après** 166.1 (une seule migration touchant `hosts` à la fois) ;
- Renvoi STORY-160 (timezone par host) : tracé, non bloquant.

## État d'avancement technique

*(à cocher pendant `treat-story` — une case par tâche détaillée ci-dessous)*

- [x] T1. `models/environment.py` (schéma canonique + UNIQUE org/name)
- [x] T2. Colonnes `Stack.origin`/`Stack.git_url`/`Stack.environment_id` + `Host.environment_id` (modèles)
- [x] T3. Migration Alembic `1662_environments_stacks_origin_git_url`
- [x] T4. Schémas stack : `origin`, `git_url` (validation URL), `environment_id` + défauts `managed`
- [x] T5. Adoption pose `origin=adopted` (stack + host local)
- [x] T6. Détection d'origine par runtime (labels WindFlow) à l'adoption
- [x] T7. Tests (adoption, modèles, migrations, schémas)

## Tâches d'implémentation détaillées

### Tâche 1 : Modèle `Environment` (schéma canonique)
**Objectif :** Créer `models/environment.py` — table `environments` : `id` (UUID str, PK), `name` (`String(100)`, index), `type` (`String(30)` — ex. dev/staging/prod, valeur libre à ce stade), `organization_id` (FK `organizations.id` CASCADE, index), `configuration` (JSON, défaut `{}`), `is_active` (Boolean, défaut `True`), timestamps `created_at`/`updated_at`, **`UNIQUE(organization_id, name)`** (contrainte `uq_environment_org_name`). Relation `organization` (back_populates `environments` à ajouter sur `Organization`). Pas d'endpoint API dans cette story (lecture interne uniquement — CRUD multi-env hors périmètre plan §6).
**Fichiers :**
- `backend/app/models/environment.py` — [Créer] — modèle complet
- `backend/app/models/organization.py` — [Modifier] — relation `environments`
- `backend/app/models/__init__.py` — [Modifier] — export `Environment`
**Dépend de :** STORY-166.1 (base Host)

### Tâche 2 : Colonnes `stacks`/`hosts` (modèles)
**Objectif :** `models/stack.py` : `origin: Mapped[str]` (`String(10)`, défaut `managed`, valeurs `WorkloadOrigin` — stockage VARCHAR + validation Pydantic côté schéma), `git_url: Mapped[str | None]` (`String(500)`, nullable, comment « URL du dépôt Git source — GitOps futur »), `environment_id: Mapped[str | None]` (FK `environments.id` SET NULL, index) + relation `environment`. `models/host.py` : `environment_id: Mapped[str | None]` (FK `environments.id` SET NULL, index) + relation (colonne posée ici ; `hosts.origin` existe déjà via 166.1).
**Fichiers :**
- `backend/app/models/stack.py` — [Modifier] — 3 colonnes + relation (après l.96 `organization_id`)
- `backend/app/models/host.py` — [Modifier] — `environment_id` + relation
**Dépend de :** Tâche 1

### Tâche 3 : Migration Alembic `1662_environments_stacks_origin_git_url`
**Objectif :** Révision `1662_...`, `down_revision = "1661_targets_to_hosts"` (coordination : **après** la migration 166.1 — une seule migration touchant `hosts` à la fois). Upgrade : (1) `CREATE TABLE environments` (schéma Tâche 1 + UNIQUE) ; (2) `batch_alter_table stacks` : ADD `origin VARCHAR(10) NOT NULL DEFAULT 'managed'` (backfill : les stacks `category='adopted'` OU `tags` contenant `'adopted'` → `origin='adopted'` — UPDATE data), ADD `git_url VARCHAR(500) NULL`, ADD `environment_id VARCHAR(36) NULL` + FK ; (3) `batch_alter_table hosts` : ADD `environment_id VARCHAR(36) NULL` + FK. Downgrade : drop colonnes + drop table (reversible — pas de perte : les colonnes sont nouvelles, `origin` backfillé est perdable au downgrade, documenté). Docstring : arbitrage timezone-Par-Host **tracé comme renvoi explicite** à STORY-160 (voir Décisions de découpe) — pas de colonne ici.
**Fichiers :**
- `backend/alembic/versions/2026_10_24_1662_environments_stacks_origin_git_url.py` — [Créer] — upgrade/downgrade complets
**Dépend de :** Tâches 1, 2 (+ migration 166.1 livrée)

### Tâche 4 : Schémas stack — `origin`, `git_url`, `environment_id` + validation
**Objectif :** `schemas/stack.py` : `StackCreate`/`StackUpdate`/`StackResponse` étendus — `origin: WorkloadOrigin = Field(default=MANAGED)` (lecture/écriture admin seulement si exposé — défaut `managed` à la création manuelle), `git_url: str | None` validé **URL** (`AnyHttpUrl` ou validateur custom schéma — rejet relatif/injection → 422 ; pas de clone ni d'exécution à ce stade, GitOps hors périmètre), `environment_id: str | None` (UUID validé, FK vérifiée à l'écriture → 404 si environnement inexistant, isolation org). `HostResponse` : exposer `environment_id` (lecture seule). `HostCreateRequest` : `environment_id` optionnel.
**Fichiers :**
- `backend/app/schemas/stack.py` — [Modifier] — champs + validateurs (l.68 `StackCreate`, l.200 `StackUpdate`, l.319 `StackResponse`)
- `backend/app/schemas/host.py` — [Modifier] — `environment_id` (lecture) + option création
**Dépend de :** Tâche 2

### Tâche 5 : Adoption pose `origin=adopted`
**Objectif :** `adoption_service.adopt_discovered_item` (l.493-507) : `new_stack = Stack(..., origin=WorkloadOrigin.ADOPTED, ...)` — tags `["adopted", ...]` et `category="adopted"` **conservés** (non-régression, AC 3). Le host de rattachement : si `request.target_id` résout un host réel (Tâche 8 de 166.3 — `_resolve_local_host`), poser `host.origin = WorkloadOrigin.ADOPTED` **seulement si le host porte des workloads adoptés et n'est pas déjà `managed`** — ⚠ **arbitrage d'analyse** : le host local reste `managed` (il EST piloté par WindFlow ; l'axe origin décrit le **workload**, pas le substrat) → **ne pas modifier `hosts.origin` à l'adoption** ; seul le stack/deployment résultant porte `adopted` (conforme spec 03 : l'origine s'applique aux entités pilotées — Apps/Machines/Clusters ; `hosts.origin` décrit la provenance du host lui-même : seedé/créé → `managed`). Documenter cet arbitrage en Notes d'implémentation. Audit adoption conservé.
**Fichiers :**
- `backend/app/services/adoption_service.py` — [Modifier] — `origin=WorkloadOrigin.ADOPTED` sur `new_stack` (l.493)
**Dépend de :** STORY-166.3 T8 (`_resolve_local_host`), Tâche 3

### Tâche 6 : Détection de l'origine par runtime (labels WindFlow)
**Objectif :** Sans surdimensionner (spec 03 § Détection de l'origine) : lors de l'adoption, si les containers portent le label `windflow.stack_id` (déjà pilotés par WindFlow), l'adoption refuser (409) ou marquer `managed` — **décision d'analyse** : simple garde-fou existant à conserver (les containers labelisés ne sont pas « découverts ») ; sinon `adopted`. Implémentation : vérifier la présence du label dans la boucle de collecte existante (l.448-460) — log DEBUG sans données sensibles.
**Fichiers :**
- `backend/app/services/adoption_service.py` — [Modifier] — garde-fou label `windflow.stack_id` (si non déjà présent)
**Dépend de :** Tâche 5

### Tâche 7 : Tests
**Objectif :** Étendre tests adoption/modèles/migrations + validation schémas (voir Tests à écrire).
**Fichiers :**
- `backend/tests/unit/test_services/test_adoption_service.py` — [Modifier] — classe `TestAdoptionOrigin`
- `backend/tests/unit/test_models/test_environment.py` — [Créer]
- `backend/tests/unit/test_models/test_stack.py` — [Créer/Modifier] — `git_url`/`origin`/`environment_id`
- `backend/tests/integration/test_migrations.py` — [Modifier] — classe `TestMigration1662`
- `backend/tests/unit/test_schemas/test_stack_schema.py` — [Créer/Modifier] — validation `git_url`
**Dépend de :** Tâches 3-6

## Tests à écrire

### Backend

**`backend/tests/unit/test_services/test_adoption_service.py`** *(étendre — classe `TestAdoptionOrigin`)* :
- adoption d'un conteneur découvert (sans label WindFlow) → `Stack.origin == "adopted"` (AC 1), tags `["adopted", ...]` et `category="adopted"` conservés (AC 3), deployment créé (non-régression `test_successful_adoption` l.378) ;
- host local **non modifié** (`hosts.origin` reste `managed` — arbitrage Tâche 5) ;
- conteneur portant `windflow.stack_id` → refus/contournement selon garde-fou Tâche 6 ;
- création manuelle de stack (API/service) → `origin == "managed"` par défaut.

**`backend/tests/unit/test_models/test_environment.py`** *(créer)* :
- `UNIQUE(organization_id, name)` violé → `IntegrityError` ;
- 2 environnements de même nom dans 2 organisations différentes → OK (isolation) ;
- FK organization CASCADE (suppression org purge les environnements) ;
- `is_active` défaut `True`, `configuration` défaut `{}`.

**`backend/tests/unit/test_models/test_stack.py`** *(étendre)* :
- `origin` défaut `managed` ; `git_url` nullable persisté ; `environment_id` FK SET NULL (suppression environnement → stack conservée, colonne NULL) ;
- `Host.environment_id` FK SET NULL idem.

**`backend/tests/integration/test_migrations.py`** *(étendre — classe `TestMigration1662`)* :
- upgrade : `environments` présente avec UNIQUE ; stacks existants → `origin='managed'` **sauf** `category='adopted'`/tags contient `adopted` → `origin='adopted'` (backfill) ; `git_url` NULL ; données stacks/hosts sans perte (counts identiques) ;
- downgrade : colonnes supprimées, données cœur intactes.

**`backend/tests/unit/test_schemas/test_stack_schema.py`** *(étendre)* :
- `git_url = "not-a-url"` → 422/ValidationError ; `git_url = "https://git.example.com/org/repo.git"` → valide ; `git_url = None` → valide (optionnel) ;
- `origin` hors `{managed, adopted, external}` → rejeté ;
- `environment_id` non-UUID → rejeté.

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_services/test_adoption_service.py backend/tests/unit/test_models/test_environment.py -v
poetry run pytest backend/tests/integration/test_migrations.py -v
make backend-test-unit
make backend-lint
```

## Notes d'implémentation

### Fichiers créés
- `backend/app/models/environment.py` — modèle `Environment` (schéma canonique spec 06 : `id`, `name`, `type`, `organization_id` FK CASCADE, `configuration` JSON, `is_active`, timestamps, **`UNIQUE(organization_id, name)`** via contrainte `uq_environment_org_name`) + relations `stacks`/`hosts` (miroir FK SET NULL) ; `__repr__` sans `configuration` (règle 40) ;
- `backend/alembic/versions/2026_10_24_1662_environments_stacks_origin_git_url.py` — migration `1662` (`down_revision = 1661_targets_to_hosts`) : CREATE `environments` + `batch_alter_table stacks` (origin VARCHAR(10) NOT NULL DEFAULT 'managed' + backfill, git_url VARCHAR(500) NULL, environment_id FK SET NULL + index) + `batch_alter_table hosts` (environment_id FK SET NULL + index) ; **défensive** (no-op journalisé si table/colonnes déjà présentes — bases `create_all` des tests), mode **offline `--sql`** supporté (DDL seul), downgrade **réversible et documenté** (colonnes nouvelles zéro perte ; seule la valeur backfillée `origin` est perdable, signaux `category`/`tags` conservés pour re-backfill) ;
- `backend/tests/unit/test_models/test_environment.py` — 9 tests (UNIQUE violé → IntegrityError, même nom inter-org OK, CASCADE org, défauts `is_active=True`/`configuration={}`, `origin` défaut `managed`, `git_url` nullable persisté, FK SET NULL stack conservée, `__repr__` sans `configuration`) ;
- `backend/tests/unit/test_schemas/test_stack_schema.py` — 18 tests (git_url : https valide / None / `not-a-url` / relatif / ftp rejetés en create **et** update ; origin : défaut `managed`, 3 valeurs valides, 4 invalides rejetées ; environment_id : UUID canonique str, non-UUID rejeté).

### Fichiers modifiés
- `backend/app/models/stack.py` — colonnes `origin` (défaut `WorkloadOrigin.MANAGED.value`), `git_url` (nullable, comment GitOps futur), `environment_id` (FK SET NULL, index) + relation `environment` ;
- `backend/app/models/host.py` — colonne `environment_id` (FK SET NULL, index) + relation `environment` ;
- `backend/app/models/organization.py` — relation `environments` (back_populates, cascade delete-orphan) ;
- `backend/app/models/__init__.py` — export `Environment` ;
- `backend/app/schemas/stack.py` — `StackCreate`/`StackUpdate`/`StackResponse` : `origin` (WorkloadOrigin, défaut managed), `git_url` (validateur `AnyHttpUrl` strict — rejet relatif/ftp → 422), `environment_id` (UUID validé, normalisé str) ;
- `backend/app/schemas/host.py` — `HostCreateRequest.environment_id` (option création), `HostUpdate.environment_id`, `HostResponse.environment_id` (lecture) — couvre aussi les alias `/targets` (mêmes classes) ;
- `backend/app/services/adoption_service.py` — pose `origin=WorkloadOrigin.ADOPTED.value` sur la stack (arbitrage : `hosts.origin` NON modifié) + **garde-fou T6** : container portant `windflow.stack_id` → `ConflictError` 409 avant toute écriture (log DEBUG sans donnée sensible) ;
- `backend/app/api/v1/stacks.py` — create/update : FK `environment_id` vérifiée à l'écriture (`session.get(Environment)`) → 404 si inexistante **ou appartenant à une autre organisation** (isolation, règle 40) ;
- `backend/tests/integration/test_migrations.py` — `EXPECTED_TABLES`/`ADDITIVE_TABLES` + `environments`, helper `_restore_legacy_stacks_hosts_1662` (simulation base pré-1662 : drop des 3 colonnes stacks + environment_id hosts **avec leurs index dans le même batch** avant le DROP d'environments — FK résolvable), classe `TestMigration1662EnvironmentsStacksOrigin` (4 tests : table+UNIQUE, backfill adopted/managed, colonnes+counts sans perte+git_url NULL, downgrade) ;
- `backend/tests/unit/test_alembic_config.py` — mêmes mises à jour (EXPECTED/ADDITIVE + helper + DROP environments dans la simulation legacy) ;
- `backend/tests/unit/test_services/test_adoption_service.py` — classe `TestAdoptionOrigin` (4 tests : origin=adopted + tags/category conservés, aucun Host touché, garde-fou 409 sans écriture, deployment créé non-régression).

### Décisions techniques
1. **Arbitrage T5 appliqué tel quel** : l'adoption marque uniquement la **stack** `origin=adopted` — `hosts.origin` reste `managed` (l'axe origin décrit le workload, pas le substrat ; le host local est piloté par WindFlow). Documenté en commentaire du code + testé (`test_adoption_does_not_touch_host_origin`).
2. **Backfill double signal** : `category='adopted'` **OU** `tags LIKE '%"adopted"%'` — la vérification du code réel confirme que `adopt_discovered_item` pose les deux (l.501-502) ; le backfill ne peut manquer aucune ligne adoptée historique.
3. **`stacks.origin` en VARCHAR(10)** avec validation Pydantic côté schémas (comme demandé par la story — pas de CHECK SQL), stockage `WorkloadOrigin.MANAGED.value` à la création (défaut colonne + défaut schéma alignés).
4. **Migration défensive + offline** : no-op journalisé sur base déjà canonique (pattern 1661/1311), `RuntimeError` si état partiel incohérent de `stacks`, DDL seul en `--sql` (test `test_env_does_not_log_database_url` le couvre en PostgreSQL offline).
5. **Tests modèles : `PRAGMA foreign_keys=ON`** + delete SQL direct (Core `delete()`) pour tester les ON DELETE CASCADE/SET NULL **au niveau FK** et non via la cascade ORM (qui masquerait la FK).
6. **Simulations legacy des tests de migrations** : les index `ix_stacks_environment_id`/`ix_hosts_environment_id` doivent être droppés **dans le même batch** que leurs colonnes (le rebuild batch recrée les index reflétés → `OperationalError` sinon), et avant le DROP d'environments (sinon FK dangling → `NoSuchTableError` à la réflexion Alembic).

### Divergences par rapport à l'analyse
- Aucune divergence fonctionnelle. Points d'implémentation non prévus par l'analyse : (a) le drop des index en même temps que les colonnes dans les helpers de simulation legacy (découverte de test, cf. décision 6) ; (b) la vérification FK `environment_id` posée dans l'API `stacks.py` (create+update) plutôt que dans `StackService` — l'isolation organisationnelle (404 env d'une autre org) vit naturellement au côté des checks existants (`UserOrganizationService.is_member`), le service reste générique.

### Difficultés rencontrées
- Alembic `create_foreign_key` exige `referent_table` en argument positionnel (`(name, referent_table, local_cols, remote_cols)`) — signature differente de l'intuition `local→remote` directe ;
- Mode offline `--sql` : `sa.inspect(bind)` indisponible → branche `is_offline_mode()` (pattern 1661) ;
- Round-trips tests : base `create_all` courante inclut `environments` + FK — les 6 sites de simulation legacy (5 dans `test_migrations.py`, 1 dans `test_alembic_config.py`) ont nécessité le helper dédié.

### Validation
- Tests ciblés : `pytest backend/tests/unit/test_models/test_environment.py backend/tests/unit/test_schemas/test_stack_schema.py backend/tests/unit/test_services/test_adoption_service.py -q` → **70 passed** ;
- Intégration migrations : `pytest backend/tests/integration/test_migrations.py -q` → **45 passed, 1 skipped** (PostgreSQL hors CI locale) — dont les 4 nouveaux `TestMigration1662EnvironmentsStacksOrigin` ; `pytest backend/tests/unit/test_alembic_config.py` → **7 passed** (offline `--sql` PG inclus) ;
- Non-régression : `make backend-test-unit` → **2601 passed, 0 failed** (vs 2520 à la livraison 166.3 : +81 tests au compteur dont les 31 nouveaux de cette story et rattrapage de comptage) ;
- Lint périmètre : isort + black appliqués, flake8 **0 erreur** sur les 15 fichiers touchés ;
- mypy périmètre : **0 erreur** sur les fichiers de la story (1 erreur préexistante `schemas/deployment.py` import-not-found, **prouvée préexistante par `git stash`** ; erreurs transitives `hosts/connectivity.py`/`stats.py` hors périmètre, préexistantes) ;
- Couverture modules nouveaux/touchés : `models/environment.py` **100 %**, `models/stack.py` **100 %**, `adoption_service.py` **83 %** (seuil 80 % respecté).

### Points d'attention pour STORY-166.5 / STORY-166.6
- **166.5 (seed/auto-détection)** : la colonne `hosts.environment_id` est posée et nullable — le seed n'a **pas** besoin de créer d'environnement par défaut (pas d'endpoint environments dans cette story, lecture interne uniquement) ; si un env par défaut est souhaité (ex. « production »), il passera par le seed 166.5 ou le CRUD multi-env (plan §6) ;
- **166.6 (frontend/CLI/purge)** : `StackResponse`/`HostResponse` exposent désormais `origin`/`git_url`/`environment_id` (lecture) — les types TS/CLI peuvent les consommer ; les alias `Target*` exposent aussi `environment_id` via les mêmes classes (contrat `/targets` étendu de façon additive, non breaking) ;
- le garde-fou `windflow.stack_id` (409) est un **contrat API nouveau** de `POST /discovery/adopt` — le frontend devra afficher le message d'erreur explicite (déjà i18n-ready côté backend via le message métier) ;
- la migration `1662` est **la seule** touchant le schéma : toute migration future de `environments` (CRUD multi-env, config chiffrée) devra partir de `1662_...` comme `down_revision` ;
- timezone par Host (STORY-160) : **renvoi explicite tracé** dans la docstring de la migration — aucune colonne posée ici.

(Renvoi fuseau STORY-160 : tracé comme renvoi explicite dans la docstring de la migration `1662` — cf. « Décisions de découpe ».)
