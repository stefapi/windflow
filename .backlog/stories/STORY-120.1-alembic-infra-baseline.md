# STORY-120.1 : Infra Alembic async + migration baseline

**Statut :** DONE
**Story Parente :** STORY-120 — Alembic — baseline du schéma existant et `upgrade head` au démarrage à la place de `create_all` (P1-1)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant que développeur backend de WindFlow, je veux que l'infrastructure Alembic soit initialisée (`backend/alembic/` avec une config async compatible SQLite/PostgreSQL) et qu'une **migration baseline** reproduise exactement le schéma des ~10 modèles ORM existants, afin de poser le socle versionné requis par toutes les futures migrations de modèle (vagues P1 et P2).

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §6, §14) : il n'existe **aucun** dossier `backend/alembic/` — le schéma est créé par `Base.metadata.create_all()` via [`create_tables()`](../../backend/app/database.py:89) au démarrage, et [`Dockerfile.api`](../../infrastructure/docker/Dockerfile.api) copie un `alembic.ini` inexistant (l. 63). La spec de déploiement exige pourtant des migrations Alembic réelles ([`16-deploiement.md`](../../docs/general_specs/16-deploiement.md) : install.sh « initialise la base SQLite (migrations Alembic) », `docker compose exec -T windflow-api alembic upgrade head`).

Cette sous-story est le **prérequis direct** de STORY-120.2 (retrait du `create_all`) et STORY-120.3 (Makefile/CI/tests). Elle ne modifie **pas** le démarrage de l'application : le `create_all` reste en place jusqu'à STORY-120.2.

## Critères d'acceptation (AC)

- [x] AC 1 : `backend/alembic/` est initialisé (config async compatible SQLite/PostgreSQL) avec une **migration baseline** reproduisant exactement le schéma des ~10 modèles existants ; sur une **base existante** : `alembic stamp baseline` puis démarrage → **aucun diff** (aucune tentative de recréation/altération, vérifiable via `alembic check` ou équivalent).

## Contexte technique

Éléments existants à réutiliser / contraintes (hérités de STORY-120, filtrés pour cette sous-story) :

- [`database.py`](../../backend/app/database.py) — moteur async SQLAlchemy (`create_async_engine`, `settings.database_url` : SQLite/aiosqlite ou PostgreSQL) : `env.py` doit réutiliser la même URL en mode **async** (pas d'engine synchrone parallèle) ;
- ~10 modèles SQLAlchemy existants (cf. [`backend_status.md`](../../docs/backend_status.md) §6 — users, organizations, targets, stacks, deployments, plugins…) : la baseline doit les capturer **à l'identique** ;
- Alembic déjà déclaré côté stack (rules 05 — SQLAlchemy 2.0 async + Alembic) : vérifier la dépendance Poetry réelle dans `pyproject.toml` et arbitrer le driver async PostgreSQL (**asyncpg** vs **psycopg2**) ;
- Compatibilité **PostgreSQL + SQLite** requise pour les migrations (spec 06 § compatibilité) — types portables (UUID, JSON, DateTime) dans la baseline ;
- [`Dockerfile.api`](../../infrastructure/docker/Dockerfile.api) l. 62-63 : `COPY backend /app/backend` + `COPY alembic.ini /app/` — l'`alembic.ini` est attendu **à la racine du repo** ;
- [`scripts/install.sh`](../../scripts/install.sh) : doit exécuter `alembic upgrade head` à l'installation (spec 16) — vérifier les chemins.

## Dépendances

- Aucune (première sous-story de STORY-120). **Bloque** : STORY-120.2, STORY-120.3.

## Tâches d'implémentation détaillées

### Tâche 1 : Dépendance Alembic + arbitrage du driver async PostgreSQL
**Objectif :** Ajouter Alembic aux dépendances Poetry principales et arbitrer le driver async PostgreSQL (asyncpg vs psycopg2) afin que `env.py` exécute les migrations sur le même type d'engine async que l'application.
**Fichiers :**
- `pyproject.toml` — Modifier — ajouter `alembic` en dépendance principale ; arbitrage driver PostgreSQL : recommandation **asyncpg** (driver async natif, cohérent avec `create_async_engine` de `database.py`) vs psycopg2 (synchrone, imposerait un mode sync dans `env.py`) — documenter la décision dans les notes d'implémentation ;
- `poetry.lock` — Modifier — régénérer via `poetry add alembic asyncpg` (ne jamais éditer le lock à la main).
**Exigences sécurité :** Aucune exigence spécifique (aucun secret impliqué).
**Dépend de :** Aucune.

### Tâche 2 : Initialisation de l'infrastructure Alembic async
**Objectif :** Créer `backend/alembic/` (env.py async SQLite/PostgreSQL, template de migration) et l'`alembic.ini` à la racine du repo, sans modifier le démarrage applicatif.
**Fichiers :**
- `backend/alembic/env.py` — Créer — `env.py` async : engine construit depuis `settings.database_url` (jamais en dur), `run_async_migrations()` via `async_engine_from_config` + `connection.run_sync(context.run_migrations)` ; `target_metadata = Base.metadata` avec import de **tous** les modèles (autogenerate fonctionnel) ;
- `backend/alembic/script.py.mako` — Créer — template standard de migration (`revision`/`down_revision`, `upgrade()`/`downgrade()`) ;
- `alembic.ini` — Créer (racine du repo) — `script_location = backend/alembic`, `sqlalchemy.url` **laissée vide** (surchargée par `env.py` depuis les settings — aucun secret en dur), `file_template` avec date + slug lisible ;
- `infrastructure/docker/Dockerfile.api` — Modifier — la ligne 63 `COPY alembic.ini /app/` devient valide avec l'`alembic.ini` racine ; vérifier que `backend/alembic/` est bien embarqué par `COPY backend /app/backend` (l. 62) et ajuster si nécessaire.
**Exigences sécurité :** `env.py` lit l'URL DB depuis les settings **sans jamais la logger** (elle peut contenir le mot de passe PostgreSQL) ; aucun secret dans `alembic.ini`.
**Dépend de :** Tâche 1.

### Tâche 3 : Migration baseline du schéma existant
**Objectif :** Générer la migration baseline reproduisant **exactement** le schéma des ~10 modèles ORM existants, compatible SQLite et PostgreSQL, avec downgrade complet.
**Fichiers :**
- `backend/alembic/versions/<revision>_baseline_schema.py` — Créer — générée par `alembic revision --autogenerate` sur base vierge puis **revue manuelle** : tables, FK (`ondelete`), index, uniques, defaults/server_defaults à l'identique des modèles ; types portables SQLite **et** PostgreSQL (UUID, JSON, DateTime) ; `downgrade()` implémenté (drops dans l'ordre inverse des dépendances) ; nom de révision explicite (`baseline`) pour permettre `alembic stamp baseline` ;
- `scripts/install.sh` — Vérifier — confirmer que l'installation exécute bien `alembic upgrade head` avec les bons chemins (alembic.ini racine, script_location) ; ajuster si besoin.
**Exigences sécurité :** Aucune exigence spécifique.
**Dépend de :** Tâche 2.

## Tests à écrire

### Backend
- `backend/tests/unit/test_alembic_config.py`
  - `test_alembic_ini_resolves_script_location` — l'`alembic.ini` racine est parsable et `script_location` pointe vers un dossier existant (`backend/alembic/`) ;
  - `test_env_does_not_log_database_url` — après chargement/exécution d'`env.py`, l'URL DB (avec credentials en variante PostgreSQL) n'apparaît dans aucun log ;
  - `test_baseline_creates_all_model_tables` — `alembic upgrade head` sur base SQLite temporaire → l'inspection révèle exactement les tables de `Base.metadata` (~10 modèles, ni plus ni moins).

### Commandes de validation
```bash
# Infra + baseline sur base vierge (SQLite)
poetry run alembic upgrade head

# Tests ciblés
poetry run pytest backend/tests/unit/test_alembic_config.py -v

# Lint (pas de régression)
make backend-lint
```

## État d'avancement technique
- [x] Tâche 1 : Dépendance Alembic + arbitrage du driver async PostgreSQL
- [x] Tâche 2 : Infrastructure Alembic async (env.py, script.py.mako, alembic.ini, Dockerfile.api)
- [x] Tâche 3 : Migration baseline du schéma existant + vérification install.sh

## Notes d'implémentation

**Date :** 2026-09-07
**Statut :** REVIEW → DONE — passage direct validée automatiquement (chaîne automatique accordée par l'utilisateur : tests et lint passants ⇒ DONE).

### Fichiers modifiés/créés
- `pyproject.toml` — ajout `alembic = "^1.13.0"` (résolu 1.19.2) + `asyncpg = "^0.30.0"` en dépendances principales
- `poetry.lock` — régénéré via `poetry lock` (résolution OK, `poetry add`/`install` non exécutables dans ce venv : build `fastuuid` cassé sous Python 3.14 — préexistant)
- `alembic.ini` (racine) — créé : `script_location = backend/alembic`, `sqlalchemy.url` **vide** (surchargée par env.py), `file_template` date + slug, timezone UTC
- `backend/alembic/env.py` — créé : engine async depuis `settings.database_url` (jamais en dur, jamais loggée), `run_async_migrations()` via `async_engine_from_config` + `connection.run_sync`, `target_metadata = Base.metadata` avec import de tous les modèles, `render_as_batch` sur SQLite, `compare_type=True`, résolution `sys.path` repo racine
- `backend/alembic/script.py.mako` — créé : template standard (docstring, revision ids, upgrade/downgrade)
- `backend/alembic/versions/2026_09_07_baseline_baseline_schema.py` — créé : migration **baseline** (revision id = `baseline`) générée par autogenerate sur base vierge puis **revue manuellement** : 10 tables à l'identique des modèles (types, FK `ondelete` CASCADE/SET NULL — y compris `scheduled_tasks.organization_id` sans ondelete, fidèle au modèle —, index, uniques, comments, enums natifs), `downgrade()` complet (drops ordre inverse des dépendances)
- `backend/tests/unit/test_alembic_config.py` — créé : 7 tests (voir ci-dessous)

### Décisions techniques
- **Arbitrage driver PostgreSQL : `asyncpg` retenu** — driver async natif, cohérent avec `create_async_engine` de `database.py` ; `psycopg2-binary` conservé (synchrone, autres usages) sans doublon de rôle : les migrations passent par asyncpg, même engine que l'application.
- Revision id **littéral `baseline`** (au lieu d'un hash) : rend `alembic stamp baseline` stable et lisible, exigé par l'AC 1.
- `env.py` écrase toute URL de `alembic.ini` (`config.set_main_option`) depuis les settings → aucun secret possible dans l'ini (testé par `test_alembic_ini_contains_no_secret`).
- Mode batch (`render_as_batch`) actif sur SQLite : ALTER portables pour les migrations futures.
- Variante PostgreSQL testée **sans serveur** via mode offline `--sql` (exécute réellement `env.py` avec dialecte asyncpg).

### Divergences par rapport à l'analyse
- `Dockerfile.api` (Tâche 2) : **aucune modification nécessaire** — `COPY alembic.ini /app/` (l. 63) devient simplement valide avec l'ini racine créé, et `backend/alembic/` est embarqué par `COPY backend /app/backend` (l. 62) ; WORKDIR `/app` → `alembic upgrade head` résout les chemins.
- `scripts/install.sh` (Tâche 3) : **aucune modification nécessaire** — `docker compose exec -T api alembic upgrade head` (l. 503) est fonctionnel avec cette infra (ini à la racine du contexte Docker, script_location relatif).
- `poetry add` impossible dans l'environnement (poetry 2.3.4 résout sur Python 3.14 où `fastuuid` ne build pas — **préexistant**, sans rapport avec cette story) : dépendances saisies dans `pyproject.toml` + `poetry lock` régénéré proprement (lock contient alembic 1.19.2 + asyncpg 0.30.0). Exécution/tests via le venv de test `.venv-test` (Python 3.11.10) où alembic/asyncpg ont été installés aux versions lockées.

### Difficultés rencontrées
- 61 échecs pré-existants dans les suites backend (ex. security_headers, deployments_api) observés sous `.venv-test` : **prouvés indépendants de cette story** par stash A/B (mêmes échecs sans mes changements — venv de test aux versions divergentes du lock poetry). Aucune régression introduite : 1013 tests passants inchangés avant/après.

### Tests ajoutés
- `backend/tests/unit/test_alembic_config.py` — 7 tests, tous passants :
  - `test_alembic_ini_resolves_script_location` (ini parsable, script_location existe)
  - `test_alembic_ini_contains_no_secret` (sécurité : url vide)
  - `test_env_does_not_log_database_url` (sécurité : secret URL absent des sorties, SQLite online + PostgreSQL offline `--sql`)
  - `test_baseline_creates_all_model_tables` (upgrade head → exactement les tables de Base.metadata + alembic_version)
  - `test_stamp_then_upgrade_is_noop_and_check_clean` (**scénario AC 1 complet** : create_all → stamp baseline → upgrade head no-op → alembic check « No new upgrade operations detected »)
  - `test_downgrade_base_drops_all_tables` (downgrade complet)
  - `test_expected_tables_match_metadata` (cohérence liste attendue ↔ metadata)

### Validation
- Commandes : `alembic upgrade head` ✅ · `alembic check` ✅ (no diff) · `alembic current` → `baseline (head)` ✅ · `alembic stamp baseline` sur base existante ✅ · `alembic upgrade base:head --sql` (offline PostgreSQL) ✅ · pytest ciblé 7/7 ✅ · `ruff check` + `ruff format` ✅ · suites unit+integration : 1013 passés / 61 échecs pré-existants (prouvés par stash A/B, sans lien avec cette story).
- Couverture : fichiers d'infrastructure alembic hors périmètre `--cov=app` ; couverture fonctionnelle assurée par les 7 tests ci-dessus.
