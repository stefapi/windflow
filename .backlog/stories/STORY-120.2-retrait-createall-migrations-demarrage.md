# STORY-120.2 : Retrait de `create_all` — migrations au démarrage

**Statut :** DONE
**Story Parente :** STORY-120 — Alembic — baseline du schéma existant et `upgrade head` au démarrage à la place de `create_all` (P1-1)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant que développeur backend de WindFlow, je veux que la création du schéma au démarrage/install soit effectuée **exclusivement par les migrations Alembic** (`alembic upgrade head`) et que le `create_all` nu soit retiré du code — avec un **stamp automatique** de la baseline sur les installations existantes non versionnées — afin que les évolutions futures du modèle soient réellement appliquées aux bases existantes sans perte de données (un `create_all` ne modifie jamais une table existante).

Le seed de données initiales (admin, organisation par défaut) est **préservé** à l'identique.

Prérequis : l'infrastructure Alembic et la migration baseline sont fournies par STORY-120.1.

## Critères d'acceptation (AC)

- [x] AC 2 : Sur une **base vierge** : la création du schéma complet se fait **par les migrations uniquement** (`alembic upgrade head`) ; le [`create_all`](../../backend/app/database.py:89) nu est retiré du démarrage (remplacé par l'exécution des migrations au démarrage/install, seed préservé) ; plus aucun `create_all` nu dans le code (critère de done de l'epic).

## Contexte technique

Éléments existants à réutiliser / contraintes (hérités de STORY-120, filtrés pour cette sous-story) :

- [`create_tables()`](../../backend/app/database.py:89) — méthode à remplacer par un runner de migrations ; le moteur async et `session_factory` ([`database.py`](../../backend/app/database.py) l. 27-80) sont conservés tels quels ;
- Déclaration abstraite [`DatabaseManager.create_tables()`](../../backend/app/core/abstractions.py:30) — l'interface doit évoluer en conséquence ;
- Appel au démarrage : [`main.py`](../../backend/app/main.py) l. 85 (`await db.create_tables()` — à remplacer ; `await db.seed_tables()` l. 86 conservé) ;
- [`conftest.py`](../../backend/tests/conftest.py) l. 93 — la fixture `test_db_engine` initialise le schéma via `Base.metadata.create_all` : à adapter pour utiliser les migrations sans `create_all` nu ;
- Compatibilité des installations existantes (plan §1.5 / §7.1) : baseline + `stamp` sur schéma existant, `create_all` retiré seulement après validation de STORY-120.1 ;
- Runner Alembic programmatique : API `alembic.command` (`upgrade` / `stamp`) pilotée depuis `database.py` en préservant le comportement async de la classe.

## Dépendances

- STORY-120.1 : Infra Alembic async + migration baseline

## Tâches d'implémentation détaillées

### Tâche 1 : Runner `alembic upgrade head` au démarrage avec stamp automatique
**Objectif :** Remplacer `create_tables()` par un runner qui applique les migrations au démarrage : `upgrade head` sur base vierge ; stamp automatique de la baseline sur base existante non versionnée (installations créées historiquement par `create_all`) puis `upgrade head`.
**Fichiers :**
- `backend/app/database.py` — Modifier — remplacer `create_tables()` (l. 89) par `run_migrations()` : détection « base existante non versionnée » (tables présentes sans table `alembic_version`) → `alembic stamp baseline` puis `upgrade head` ; exécution programmatique via `alembic.config.Config` (alembic.ini racine) + `alembic.command` ; base vierge → `upgrade head` direct ;
- `backend/app/main.py` — Modifier — l. 85 : `await db.create_tables()` → `await db.run_migrations()` ; `await db.seed_tables()` (l. 86) inchangé ;
- `backend/app/core/abstractions.py` — Modifier — remplacer la méthode abstraite `create_tables()` (l. 30) par `run_migrations()` dans `DatabaseManager`.
**Exigences sécurité :** Logs structurés du runner (INFO : base vierge → migrations appliquées ; base existante → stamp puis upgrade) **sans données sensibles** — jamais l'URL DB ni de credentials ; échec de migration → lever une `WindFlowException` bloquant le démarrage (pas de repli silencieux vers `create_all`).
**Dépend de :** Aucune (dans le cadre de cette sous-story — l'infra Alembic vient de STORY-120.1).

### Tâche 2 : Fixtures de test sans `create_all` nu
**Objectif :** Adapter la fixture `test_db_engine` pour créer le schéma de test via les migrations (`upgrade head`) au lieu de `Base.metadata.create_all`, garantissant « plus aucun `create_all` nu dans le code ».
**Fichiers :**
- `backend/tests/conftest.py` — Modifier — fixture `test_db_engine` (l. 93) : exécuter les migrations Alembic sur la base SQLite en mémoire (StaticPool) au lieu de `run_sync(Base.metadata.create_all)` ; conserver l'isolation par test (création/destruction par fonction) ; vérifier que toute la suite existante reste verte.
**Exigences sécurité :** Aucune exigence spécifique.
**Dépend de :** Tâche 1.

## Tests à écrire

### Backend
- `backend/tests/unit/test_database.py`
  - `test_run_migrations_on_fresh_db_applies_upgrade_head` — base vierge → schéma complet créé **par les migrations uniquement** ;
  - `test_run_migrations_stamps_existing_unversioned_db` — base pré-remplie sans `alembic_version` → stamp automatique, aucune tentative de recréation/altération ;
  - `test_run_migrations_failure_raises_windflow_exception` — erreur de migration → exception métier bloquante (pas de fallback `create_all`) ;
  - `test_no_naked_create_all_in_app_code` — inspection statique : plus aucun `Base.metadata.create_all` dans `backend/app/` (critère de done de l'epic).

### Commandes de validation
```bash
# Tests ciblés
poetry run pytest backend/tests/unit/test_database.py -v

# Suite complète (fixtures conftest migrées)
make backend-test-unit

# Lint + types
make backend-lint
```

## État d'avancement technique
- [x] Tâche 1 : Runner migrations au démarrage + stamp automatique (database.py, main.py, abstractions.py)
- [x] Tâche 2 : Fixtures de test sans `create_all` nu (conftest.py)

## Definition of Done (DoD) Checklist
- [x] Tous les critères d'acceptation (AC) sont cochés
- [x] Toutes les tâches d'implémentation sont cochées dans "État d'avancement technique"
- [x] Tests unitaires écrits et passants (couverture `app.database` 80%)
- [x] Pas de régression sur les tests existants (preuve A/B, voir Notes)
- [x] Documentation technique mise à jour si nécessaire (docstrings runner + fixtures)
- [x] Section "Notes d'implémentation" ajoutée au fichier story
- [x] Lint passe sans erreur (ruff check + format ; E402 main.py pré-existants hors périmètre)
- [x] Passage REVIEW → DONE automatique : validation utilisateur accordée par avance (tests + lint verts ⇒ DONE), conformément à l'instruction de traiter la story en chaîne automatique.

## Notes d'implémentation

**Date :** 2026-09-07

### Fichiers modifiés/créés
- `backend/app/database.py` — `create_tables()` (create_all nu) remplacé par `run_migrations()` : détection d'état (`_detect_schema_state`) → `fresh` : `upgrade head` direct ; `unversioned` : `alembic stamp baseline` puis `upgrade head` ; `versioned` : `upgrade head`. Runner programmatique via `alembic.command` (`get_alembic_config()` : `Config` **sans fichier ini** pour ne pas réécrire le logging du processus hôte via `fileConfig`, `script_location` absolu). Exécution via `asyncio.to_thread` (`env.py` fait `asyncio.run()`, interdit dans la boucle du lifespan). Échec → `WindFlowException` bloquante avec message sanitisé (`_sanitize_error` masque l'URL DB). Logs structurés INFO (`extra={"event": "db_migrations", "state": ...}`), sans URL ni credentials.
- `backend/app/main.py` — startup : `await db.create_tables()` → `await db.run_migrations()` (l. 85) ; `await db.seed_tables()` (l. 86) inchangé — ordre startup identique.
- `backend/app/core/abstractions.py` — `DatabaseManager.create_tables()` (abstraite) renommée en `run_migrations()` ; vérifié : aucune sous-classe concrète de `DatabaseManager` dans le code (la classe `Database` n'en hérite pas), aucune autre référence à actualiser.
- `backend/tests/conftest.py` — fixture `test_db_engine` : `Base.metadata.create_all` remplacé par un template migré une fois par session (`_migrated_schema_template` : `alembic upgrade head` sur base SQLite fichier) copié par test (`shutil.copy2` vers `tmp_path`) ; isolation par test conservée ; suppression du fichier au teardown à la place du `drop_all`.
- `backend/tests/unit/test_database.py` — **créé** — 8 tests (voir § Tests ajoutés).

### Décisions techniques
- **`Config` Alembic sans fichier ini** : évite que `env.py` (`fileConfig`) ne remplace la config de logging du processus applicatif au démarrage ; `script_location` résolu en absolu depuis `__file__` (robuste dev + Docker `/app`).
- **Stamp automatique** : détection = tables présentes SANS `alembic_version` → `stamp baseline` (id de révision littéral posé par 120.1) puis `upgrade head` → no-op. Base versionnée → `upgrade head` seul. Aucune altération des données (testé : données métier intactes avant/après).
- **`asyncio.to_thread`** : `env.py` appelle `asyncio.run()` (interdit dans une boucle active) → les commandes alembic s'exécutent dans un thread sans boucle.
- **Conftest template+copie** : migrations exécutées 1×/session (perf : ~1s de gagné par test), isolation stricte conservée par copie fichier unique par test.

### Divergences par rapport à l'analyse
- **Tâche 2 (conftest)** — la story suggérait « SQLite en mémoire (StaticPool) » : **impossible** car `backend/alembic/env.py` construit son propre engine depuis `settings.database_url` — une base `:memory:` serait une base **vide distincte** pour le runner Alembic (schema appliqué à une autre base que celle du test). Solution retenue : template fichier migré par session + copie par test (l'isolation par test exigée par la story est conservée). `StaticPool` devenu sans objet.
- **Seed test** : `settings.admin_email` ponctuellement redéfini en email `example.com` dans le test seed — le défaut `admin@windflow.local` est rejeté par les versions récentes d'`email-validator` (divergence de versions `.venv-test` vs lock, même famille que les échecs pré-existants ; sans lien avec le schéma/seed).

### Difficultés rencontrées
- **Baseline des 61 échecs pré-existants (héritée de 120.1)** — méthode A/B appliquée avec stash **ciblé sur les 5 fichiers 120.2 uniquement** (le 1er stash `-u` global avait embarqué les fichiers non-commités de 120.1 ; re-stash sélectif pour isoler correctement) :
  - **Unit** : A (avec 120.2) vs B (sans) → listes FAILED **strictement identiques** (42 = 42, `diff` vide). Auparavant observé 41 vs 42 : la seule différence est `test_debug_story1033.py::test_debug_get_deployment_500` (test de debug **flaky**, non-tracké, hors story — échoue en B, passe en A) ;
  - **Intégration** : A = B = 20 failed / 48 passed (security_headers, deployments_api… échecs pré-existants documentés en 120.1) ;
  - **Conclusion** : **aucune régression imputable à 120.2** ; +8 nouveaux tests passants (972 vs 965 passants en unit).
- **Ruff indisponible** (poetry cassé, absent de `.venv-test`) → installé dans `.venv-test` via `ensurepip`+`pip` (version lockée 0.15.13), sans toucher à `pyproject.toml`/lock. E402 de `main.py` pré-existants (le `print` avant les imports existait déjà dans HEAD — non introduits par cette story).

### Tests ajoutés
- `backend/tests/unit/test_database.py` — 8 tests, tous passants (`.venv-test`) :
  - `test_run_migrations_on_fresh_db_applies_upgrade_head` — base vierge → schéma complet par migrations uniquement + `alembic_version` à `baseline` ;
  - `test_run_migrations_stamps_existing_unversioned_db` — base legacy create_all + données → stamp auto, **aucune perte de données**, 2e démarrage no-op ;
  - `test_detect_schema_state_classifies_correctly` — classification fresh/unversioned/versioned + garde-fous `RuntimeError` ;
  - `test_run_migrations_failure_raises_windflow_exception` — échec → `WindFlowException` (cause chaînée), **URL DB masquée** dans le message ;
  - `test_seed_runs_after_migrations_on_fresh_db` — ordre startup inchangé : org par défaut + admin superuser créés après migrations (seed préservé) ;
  - `test_no_naked_create_all_in_app_code` — inspection statique : zéro `create_all` actif dans `backend/app/` (critère de done de l'epic) ;
  - `test_engine_schema_comes_from_migrations` / `test_engine_data_isolated_per_test` — fixtures : schéma issu des migrations + isolation par test.
- Couverture : `app.database` 80 % (lignes restantes préexistantes : `AsyncSessionLocal`, `get_db`, `health_check` — couvertes par le reste de la suite).

### Validation
- Tests ciblés : `pytest backend/tests/unit/test_database.py` → **8/8 ✅** ;
- Suites complètes via `.venv-test` : unit 972 passed / 42 failed (identiques sans changements, preuve A/B `diff` vide) ; intégration 48 passed / 20 failed (A = B) ;
- Lint : `ruff check` + `ruff format` ✅ sur les 5 fichiers modifiés/créés (E402 `main.py` pré-existants, prouvés présents dans HEAD) ;
- Commandes exécutées avec `.venv-test/bin/python -m pytest` (poetry racine partiellement cassé — contexte story).
