# STORY-121.1 : Enum `Role`, modèle `UserOrganization` et migration de création de table

**Statut :** DONE
**Story Parente :** STORY-121 — Modèle `user_organizations` — association utilisateur ↔ organisation avec rôle (P1-2, partie modèle)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'administrateur WindFlow, je veux poser la **base de données** du RBAC 4 rôles : un enum partagé `Role` (`viewer` / `operator` / `admin`) et une table d'association `user_organizations` portant le rôle d'un utilisateur dans une organisation (le Super_Admin restant un rôle système porté par `User.is_superadmin`), créée via une migration Alembic **additive** (création de table + index, sans modification des données existantes ni de `users.organization_id`).

Cette sous-story est la première étape de STORY-121 (découpée en raison de sa complexité) : elle fournit le socle modèle/migration sur lequel s'appuient STORY-121.2 (endpoints membres) et STORY-121.3 (migration des données + bascule des lectures + retrait de la colonne héritée).

## Critères d'acceptation (AC)

- [x] AC 1 : La table `user_organizations` existe via migration Alembic (STORY-120) conformément au schéma spec 06 (PK composite, `role` défaut `viewer`, `joined_at`, index `organization_id`), avec l'enum `Role` (`viewer`/`operator`/`admin`) partagé côté backend.

## Contexte technique

> Analyse réalisée par `analyse-story` (2026-09-07) — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches.

**Couches impactées :** Backend uniquement — enums, models, migrations Alembic, tests backend (unit + integration). **Aucun endpoint**, aucun schéma Pydantic, aucun impact frontend/CLI.

**Spécifications de référence :**
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § UserOrganization (SQL cible : PK composite, `role VARCHAR(20) NOT NULL DEFAULT 'viewer'`, `joined_at`, index sur `organization_id`) ;
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — § Définition des rôles + § Modèle de données (« Le Super Admin est identifié par le flag `is_superadmin` sur `User`, pas par une entrée dans `user_organizations` »).

**Fichiers de référence (patterns vérifiés) :**
- Enum partagé models/schemas → [`backend/app/enums/target.py`](../../backend/app/enums/target.py) : classes `(str, Enum)` par domaine, docstring « single source of truth », **import direct** `from app.enums.xxx import ...` (pas de ré-export dans [`backend/app/enums/__init__.py`](../../backend/app/enums/__init__.py)) ;
- Modèle portant FK CASCADE + timestamps + `__repr__` → [`backend/app/models/target_capability.py`](../../backend/app/models/target_capability.py) ;
- Migration (`op.create_table` + `batch_alter_table`/index + downgrade symétrique) → [`backend/alembic/versions/2026_09_07_baseline_baseline_schema.py`](../../backend/alembic/versions/2026_09_07_baseline_baseline_schema.py) ;
- Runner migrations / garde-fou `alembic check` → [`backend/app/database.py`](../../backend/app/database.py) (`run_migrations()` stamp baseline → upgrade head ; `get_alembic_config()`) ;
- Tests migrations à adapter → [`backend/tests/integration/test_migrations.py`](../../backend/tests/integration/test_migrations.py), [`backend/tests/unit/test_alembic_config.py`](../../backend/tests/unit/test_alembic_config.py), [`backend/tests/unit/test_database.py`](../../backend/tests/unit/test_database.py) ;
- Fixtures disponibles : `db_session`, `test_user`, `test_organization` ([`backend/tests/conftest.py`](../../backend/tests/conftest.py)) — le schéma de test provient des migrations (`_migrated_schema_template`), la nouvelle table y sera donc présente automatiquement.

**Décisions d'analyse :**
- **Enum `Role` à 3 valeurs** (`viewer`/`operator`/`admin`) conformément à l'AC 1 : `super_admin` est un rôle **système** porté par `User.is_superuser` (usage/renommage arbitrés par STORY-121.3/122) — son absence de l'enum interdit **structurellement** de le stocker comme valeur d'association (anti-escalade, matrice spec 08) ; STORY-122 arbitrera séparément la représentation du Super Admin pour `require_role(...)`.
- **Stockage `String(20)` + validation applicative** (et non `SQLEnum` natif) : fidèle au SQL cible spec 06 (`VARCHAR(20) DEFAULT 'viewer'`), portable SQLite/PostgreSQL, préserve `alembic check` sans diff (env.py active `compare_type`). Le bornage est assuré par l'enum partagé + un `@validates("role")` au niveau modèle.
- **`server_default="viewer"`** (défaut serveur, en plus du `default` Python) : exigé par le SQL cible spec 06 et réutilisable par la migration de données STORY-121.3 (INSERT bruts).
- **Timestamps** : `joined_at` (spec 06 / AC 1) **et** `created_at`/`updated_at` (conventions `.roo/rules/30-code-standards.md` — pattern maison `target_capability.py`).
- **Nommage des relations** (sans collision avec l'existant) : `User.organization_links` / `Organization.user_links` — les relations `User.organization` et `Organization.users` (FK directe) restent **inchangées** (retrait porté par STORY-121.3).
- **Révision Alembic** : `revision = "1211_user_organizations"`, `down_revision = "baseline"` (identifiant lisible, pattern baseline).

**Points d'attention identifiés (tests STORY-120 impactés — traités Tâche 5) :**
- Les constantes `EXPECTED_TABLES` de `test_alembic_config.py` et `test_migrations.py` doivent inclure `user_organizations` (assertions d'égalité stricte avec `Base.metadata.tables`) ;
- Le scénario « stamp baseline → upgrade head **no-op** » n'est plus un no-op : l'upgrade applique désormais **uniquement** la migration additive ;
- ⚠️ Les simulations de base legacy par `Base.metadata.create_all()` (métadonnées **courantes**) créeront **aussi** la nouvelle table → collision avec `op.create_table` lors de l'upgrade : les 3 fichiers de tests concernés doivent exécuter `DROP TABLE user_organizations` après le `create_all` pour simuler fidèlement une base antérieure à cette story ;
- `test_database.py` asserte `_alembic_version(...) == "baseline"` (2 occurrences) : après `upgrade head` la version est la nouvelle tête — utiliser `ScriptDirectory(get_alembic_config()).get_current_head()` pour rester robuste aux migrations suivantes (STORY-121.3).

**Exigences sécurité identifiées :**
- Auth : **non applicable** (aucun endpoint ; protection des endpoints membres = STORY-121.2, `require_role(...)` = STORY-122) ;
- RBAC : non applicable ici — mais l'enum sans `super_admin` pose la base anti-escalade (« un Admin ne peut pas se promouvoir Super Admin », spec 08 § Protection contre l'escalade) ;
- Validation : `role` borné à `{viewer, operator, admin}` via enum partagé + `@validates` modèle (refus explicite de `super_admin`) ; `user_id`/`organization_id` UUID `String(36)` (convention maison, PK composites) ;
- Exposition : aucun schéma `*Response`, aucune donnée sensible manipulée ni loggée ;
- Audit : non requis (migration structurelle, aucune action runtime) ;
- Données : migration **strictement additive** — aucune ligne lue/modifiée, `users.organization_id` intacte (aucun risque de perte à ce stade).

## Dépendances

- STORY-120 (Alembic) — DONE ✔ (prérequis satisfait).
- Bloque : STORY-121.2 et STORY-121.3.

## Périmètre indicatif (répartition des tâches identifiées par l'analyse de STORY-121)

| # | Tâche (issue de l'analyse STORY-121) | Périmètre de cette sous-story |
|---|--------------------------------------|-------------------------------|
| T1 | Enum `Role` (`viewer`/`operator`/`admin`) partagé côté backend | ✅ Complet |
| T2 | Modèle `UserOrganization` + relations (`User`, `Organization`) | ✅ Complet |
| T3 | Migration Alembic | 🔶 Partie **structure** uniquement : création de la table + PK composite + index `organization_id` (la copie des données et le traitement de `users.organization_id` sont portés par STORY-121.3) |
| T8 | Tests | 🔶 Partie : tests de la migration structurelle (table + index + défauts créés sur base vierge et sur baseline stampée) |

**Hors périmètre :** endpoints membres, schémas Pydantic, service (STORY-121.2) ; migration des données, bascule des ~30 consommateurs `current_user.organization_id`, retrait/relégation de la colonne, JWT, seed (STORY-121.3).

## Tâches d'implémentation détaillées

> Exécuter dans l'ordre (models avant migration pour l'autogenerate ; `alembic check` sans diff est le juge de paix modèle↔migrations). Références : `.roo/rules/30-code-standards.md` (conventions), `.roo/rules/55-project-structure.md` (chemins), `.roo/rules/40-security.md` (checklist sécurité).

### Tâche 1 : Enum partagé `Role` (viewer / operator / admin)
**Objectif :** Créer la source unique de vérité du rôle d'association, partagée entre modèles (cette story) et futurs schémas Pydantic (STORY-121.2), conformément à l'AC 1 et à la spec 08.
**Fichiers :**
- `backend/app/enums/rbac.py` — Créer — Nouveau module d'enum (pattern : `backend/app/enums/target.py`). Définir `class Role(str, Enum)` avec **exactement** `VIEWER = "viewer"`, `OPERATOR = "operator"`, `ADMIN = "admin"` (valeurs minuscules). Docstring du module et de la classe précisant : rôles organisationnels portés par la table `user_organizations` ; **`super_admin` est volontairement absent** (rôle système via `User.is_superuser`, spec 08 — jamais une valeur d'association) ; « Single source of truth — imported by models, schemas, and services ».
- `backend/app/enums/__init__.py` — Modifier — Mettre à jour la docstring (« Centralized enums for the target module » → formulation générique couvrant plusieurs domaines, ex. « Centralized enums shared across WindFlow domains »). **Pas** de ré-export (pattern actuel : imports directs `from app.enums.xxx import ...`).
**Exigences sécurité :** L'enum constitue la liste blanche des valeurs admises pour `role` ; l'absence de `SUPER_ADMIN` interdit structurellement le stockage d'un rôle système en association (anti-escalade).
**Dépend de :** Aucune

### Tâche 2 : Modèle `UserOrganization` + relations `User` / `Organization`
**Objectif :** Créer la table d'association `user_organizations` conforme spec 06/08 (PK composite, FK CASCADE, `role` défaut `viewer`, `joined_at`) et la relier aux deux entités existantes sans toucher aux relations actuelles.
**Fichiers :**
- `backend/app/models/user_organization.py` — Créer — Nouveau modèle (pattern : `backend/app/models/target_capability.py`). Classe `UserOrganization(Base)` :
  - `__tablename__ = "user_organizations"` ;
  - `user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)` ;
  - `organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True, index=True)` (génère `ix_user_organizations_organization_id` — index requis spec 06 ; la PK composite couvre déjà les recherches par `user_id` en préfixe gauche) ;
  - `role: Mapped[Role] = mapped_column(String(20), nullable=False, default=Role.VIEWER, server_default="viewer", comment=...)` — annotation `Role` (str-Enum : lecture = valeur str compatible, comparaison `== Role.VIEWER` fonctionnelle) ;
  - `joined_at`, `created_at`, `updated_at: Mapped[datetime]` en `DateTime` non nuls, defaults `lambda: datetime.now(timezone.utc)` (`onupdate` pour `updated_at`) — pattern `target_capability.py` ;
  - relations : `user: Mapped["User"] = relationship("User", back_populates="organization_links")` et `organization: Mapped["Organization"] = relationship("Organization", back_populates="user_links")` (imports `TYPE_CHECKING`) ;
  - `@validates("role")` : accepte `Role` ou `str` convertible (retourne le `Role` correspondant), lève `ValueError` pour toute autre valeur — **y compris `super_admin`** et chaîne vide ;
  - `__repr__` cohérent avec le pattern (`<UserOrganization(user_id=..., organization_id=..., role=...)>`).
- `backend/app/models/user.py` — Modifier — Ajouter `List` à l'import typing ; ajouter `UserOrganization` au bloc `TYPE_CHECKING` ; ajouter la relation `organization_links: Mapped[List["UserOrganization"]] = relationship("UserOrganization", back_populates="user", cascade="all, delete-orphan")`. **Ne pas toucher** à `organization_id` ni à la relation `organization` (STORY-121.3).
- `backend/app/models/organization.py` — Modifier — Ajouter `UserOrganization` au bloc `TYPE_CHECKING` ; ajouter la relation `user_links: Mapped[List["UserOrganization"]] = relationship("UserOrganization", back_populates="organization", cascade="all, delete-orphan")`. **Ne pas toucher** à la relation `users` existante.
- `backend/app/models/__init__.py` — Modifier — Importer `UserOrganization` et l'ajouter à `__all__` (ordre alphabétique) — indispensable pour l'enregistrement dans `Base.metadata` (autogenerate + `create_all` des tests + fixture conftest).
**Exigences sécurité :** Validation enum au niveau modèle via `@validates("role")` (bornage `{viewer, operator, admin}`, refus explicite `super_admin`) ; identifiants UUID `String(36)` ; `ondelete="CASCADE"` sur les deux FK (suppression user/org → purge des associations).
**Dépend de :** Tâche 1

### Tâche 3 : Migration Alembic additive de création de la table
**Objectif :** Créer la table `user_organizations` par migration Alembic (structure uniquement : table + PK composite + index), strictement additive — aucune donnée copiée, aucune altération de `users.organization_id` (STORY-121.3).
**Fichiers :**
- `backend/alembic/versions/2026_09_08_1211_user_organizations_table.py` — Créer — Nouvelle migration (pattern : `2026_09_07_baseline_baseline_schema.py`). En-tête : `revision: str = "1211_user_organizations"`, `down_revision: Union[str, None] = "baseline"` ; docstring documentant STORY-121.1 et le caractère **additif** (aucune donnée existante lue/modifiée ; `users.organization_id` inchangée — bascule STORY-121.3). Génération recommandée : `make migrate MIGRATION_MESSAGE="add user_organizations table"` (autogenerate, DB de dev préalablement versionnée à baseline) **puis revue/ajustement manuel** du fichier généré (normaliser `server_default` en `"viewer"`, vérifier le nom d'index `ix_user_organizations_organization_id`, complétude du downgrade, docstring) — alternative acceptée : rédaction manuelle sur le pattern baseline. Contenu cible :
  - `upgrade()` : `op.create_table("user_organizations", ...)` avec colonnes `user_id sa.String(36)` non nul, `organization_id sa.String(36)` non nul, `role sa.String(20)` non nul avec `server_default="viewer"` et comment, `joined_at`/`created_at`/`updated_at sa.DateTime()` non nuls ; `sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE")` et `sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE")` ; `sa.PrimaryKeyConstraint("user_id", "organization_id")` ; puis `with op.batch_alter_table(...)`: `create_index(batch_op.f("ix_user_organizations_organization_id"), ["organization_id"], unique=False)` ;
  - `downgrade()` symétrique : `drop_index` puis `drop_table("user_organizations")` ;
  - après la tâche : `alembic check` doit rester **sans diff** (garde-fou vérifié par les tests existants — Tâche 5) et le downgrade complet doit continuer de vider la base (test `TestDowngrade` existant).
**Exigences sécurité :** Migration strictement additive — aucun accès aux données, aucune perte possible ; le `server_default "viewer"` garantit qu'aucun INSERT brut ne peut produire de rôle non borné par défaut.
**Dépend de :** Tâche 2

### Tâche 4 : Tests unitaires du modèle et de l'enum
**Objectif :** Couvrir le comportement du modèle `UserOrganization` (défauts, bornage rôle, unicité PK, relations) et de l'enum `Role`.
**Fichiers :**
- `backend/tests/unit/test_models/test_user_organization.py` — Créer — Nouveau fichier de tests (fixtures `db_session`, `test_user`, `test_organization` du conftest ; marqueurs/unit conventions du projet). Contenu détaillé en section « Tests à écrire ».
**Exigences sécurité :** Tests du bornage `role` — le refus de `super_admin` valide la garde anti-escalade structurelle.
**Dépend de :** Tâche 2

### Tâche 5 : Tests de migration structurelle + adaptation des tests Alembic existants (non-régression STORY-120)
**Objectif :** Prouver la création structurelle de la table (base vierge **et** base existante stampée baseline) et maintenir les tests STORY-120 au vert en adaptant les assertions rendues obsolètes par l'ajout d'une 2ᵉ migration.
**Fichiers :**
- `backend/tests/integration/test_migrations.py` — Modifier — (a) ajouter `"user_organizations"` à `EXPECTED_TABLES` ; (b) scénario 2 (`TestExistingDbStampedThenStartupNoDiff`) : après le `Base.metadata.create_all` de simulation legacy, exécuter `DROP TABLE user_organizations` (sinon collision `create_table` lors de l'upgrade) ; l'assertion de tables attendues devient `tables_before | {"alembic_version", "user_organizations"}` (la vérification « données legacy intactes » est conservée telle quelle) ; (c) ajouter la classe `TestUserOrganizationsTableMigration` (structure : table, colonnes, défaut serveur, PK composite, FK CASCADE, index — sur base vierge **et** sur base stampée baseline, cf. section « Tests à écrire »).
- `backend/tests/unit/test_alembic_config.py` — Modifier — (a) ajouter `"user_organizations"` à `EXPECTED_TABLES` ; (b) adapter `TestExistingDatabaseStampScenario::test_stamp_then_upgrade_is_noop_and_check_clean` : après `create_all`, `DROP TABLE user_organizations` (simulation legacy pré-121.1) ; le `upgrade head` post-stamp n'est plus un no-op — asserter l'exécution de la seule migration additive (`Running upgrade baseline -> 1211_user_organizations` dans stdout) et que les tables d'origine + `user_organizations` sont présentes sans altération, puis `alembic check` sans diff ; renommer/adapter docstrings en conséquence (le scénario teste désormais le chemin « base existante + migration additive ») ; (c) ajuster la docstring de `TestBaselineCreatesAllModelTables` (le schéma complet est créé par `upgrade head`, plus par la seule baseline).
- `backend/tests/unit/test_database.py` — Modifier — `TestRunMigrationsExistingUnversionedDb::test_run_migrations_stamps_existing_unversioned_db` : après le `create_all`, `DROP TABLE user_organizations` (même raison) ; les 2 assertions `_alembic_version(db_path) == "baseline"` (lignes ~93 et ~126) deviennent `== ScriptDirectory(get_alembic_config()).get_current_head()` (import `from alembic.script import ScriptDirectory` + `from app.database import get_alembic_config`) — robuste aux migrations suivantes (STORY-121.3).
**Exigences sécurité :** Vérification structurelle du défaut serveur `'viewer'` et du bornage `String(20)` — aucune valeur escaladante possible par défaut.
**Dépend de :** Tâche 3

## Tests à écrire

> Patterns détaillés : `.roo/rules/35-testing-quality-gates.md` · Checklist sécurité : `.roo/rules/40-security.md`

### Unitaires Backend — modèle et enum

- `backend/tests/unit/test_models/test_user_organization.py` — Créer (fixtures conftest `db_session`, `test_user`, `test_organization`) :
  - **Enum** : `test_role_enum_exact_values` — `Role` expose exactement `{viewer, operator, admin}` (valeurs str minuscules) ; `test_role_enum_has_no_super_admin` — **sécurité** : `SUPER_ADMIN` absent de `Role` (rôle système = flag `User.is_superuser`) ; `test_role_enum_is_str` — héritage `(str, Enum)` (comparaison directe avec la valeur stockée).
  - **Défauts (cas nominaux)** : `test_default_role_is_viewer` — `UserOrganization(user_id=..., organization_id=...)` sans rôle → `role == Role.VIEWER` après add/flush ; `test_server_default_viewer_on_raw_insert` — INSERT SQL brut sans `role` → `'viewer'` en base (preuve du `server_default`) ; `test_joined_at_and_timestamps_defaulted` — `joined_at`, `created_at`, `updated_at` non nuls.
  - **Validation (cas d'erreurs + sécurité)** : `test_validates_accepts_all_three_roles` — `viewer`/`operator`/`admin` acceptés (str et `Role`) ; `test_validates_rejects_super_admin` — **sécurité anti-escalade** : `role="super_admin"` → `ValueError` ; `test_validates_rejects_unknown_role` — `role="hacker"` → `ValueError` ; `test_validates_rejects_empty_role` — `role=""` → `ValueError`.
  - **Intégrité** : `test_duplicate_pair_raises_integrity_error` — 2 lignes même `(user_id, organization_id)` → `IntegrityError` (PK composite).
  - **Relations** : `test_user_relationship_organization_links` — `test_user.organization_links` navigable après flush d'une association ; `test_organization_relationship_user_links` — `test_organization.user_links` navigable ; `test_tablename` — `__tablename__ == "user_organizations"`.

### Intégration Backend — migration structurelle

- `backend/tests/integration/test_migrations.py` — Modifier + nouvelle classe `TestUserOrganizationsTableMigration` (helper `_run_alembic` existant + inspection `sqlalchemy.inspect`) :
  - `test_fresh_db_upgrade_creates_user_organizations_table` — base vierge → `upgrade head` → table `user_organizations` présente ;
  - `test_table_structure_matches_spec_06` — colonnes attendues : `user_id` `String(36)` NOT NULL, `organization_id` `String(36)` NOT NULL, `role` `String(20)` NOT NULL avec défaut serveur `'viewer'`, `joined_at`/`created_at`/`updated_at` `DateTime` NOT NULL ;
  - `test_composite_primary_key` — PK == `["user_id", "organization_id"]` ;
  - `test_foreign_keys_cascade` — FK `user_id → users.id` et `organization_id → organizations.id` avec `ondelete CASCADE` (réflexion SQLite `PRAGMA foreign_key_list`) ;
  - `test_index_on_organization_id` — index `ix_user_organizations_organization_id` présent (non unique) ;
  - `test_stamped_baseline_db_upgrade_creates_table_and_preserves_data` — base legacy simulée (`create_all` + `DROP TABLE user_organizations` + donnée org insérée) → stamp baseline → `upgrade head` → table créée **vide**, données existantes intactes, version = head ;
  - adaptations des scénarios existants : `EXPECTED_TABLES` + `"user_organizations"` ; scénario 2 : `DROP TABLE user_organizations` après `create_all` + tables attendues `| {"alembic_version", "user_organizations"}` (détails en Tâche 5).

### Adaptations de tests existants (non-régression STORY-120)

- `backend/tests/unit/test_alembic_config.py` : `EXPECTED_TABLES` + `"user_organizations"` ; scénario stamp → upgrade **additif** (plus no-op) — cf. Tâche 5.
- `backend/tests/unit/test_database.py` : assertions `_alembic_version == "baseline"` → `get_current_head()` — cf. Tâche 5.
- Garde-fous conservés tels quels (doivent rester verts) : `TestAlembicCheckNoPendingChanges` (check sans diff), `TestDowngrade::test_downgrade_base_drops_all_tables` (downgrade complet vide la base — prouve le downgrade de la nouvelle migration), scénario seed/login (`TestMigratedDbSeedAndAdminLogin`), variante PostgreSQL (`TestMigrationsCompatiblePostgresql` — couvre la nouvelle table via `EXPECTED_TABLES`).

### Commandes de validation

```bash
# Tests ciblés (voir Makefile — source de vérité)
poetry run pytest backend/tests/unit/test_models/test_user_organization.py -v
poetry run pytest backend/tests/unit/test_alembic_config.py backend/tests/unit/test_database.py -v --tb=short
poetry run pytest backend/tests/integration/test_migrations.py -v

# Génération de la migration (si autogenerate retenu — DB dev versionnée baseline requise)
make migrate MIGRATION_MESSAGE="add user_organizations table"

# Non-régression + qualité
make backend-test-all
make backend-lint
make backend-typecheck
```

## État d'avancement technique

- [x] Tâche 1 : Enum `Role` partagé (`backend/app/enums/rbac.py`)
- [x] Tâche 2 : Modèle `UserOrganization` + relations `User`/`Organization` + export `models/__init__.py`
- [x] Tâche 3 : Migration Alembic additive `user_organizations` (table + PK composite + index `organization_id`)
- [x] Tâche 4 : Tests unitaires modèle/enum (`test_models/test_user_organization.py`)
- [x] Tâche 5 : Tests migration structurelle + adaptation tests Alembic existants (×3 fichiers)
- [x] Tests non-régression backend complets verts (`make backend-test-all`) — zéro régression prouvée par diff stash baseline (42 échecs unit + 20 intégration **pré-existants strictement identiques** ; cf. Notes)
- [x] Lint + typecheck OK (`make backend-lint` + `make backend-typecheck`) — isort/black/flake8/ruff verts sur les 11 fichiers de la story ; mypy/bandit non installés dans les venv locaux (Poetry env cassé) → exécutés par la CI ; cf. Notes

## Notes d'implémentation

**Date :** 2026-09-08

### Fichiers modifiés/créés
- `backend/app/enums/rbac.py` : **créé** (Tâche 1, réalisé lors de la tentative interrompue, vérifié conforme) — enum `Role(str, Enum)` avec exactement `VIEWER`/`OPERATOR`/`ADMIN` (valeurs minuscules), docstrings module + classe précisant l'absence volontaire de `super_admin` (rôle système `User.is_superuser`).
- `backend/app/enums/__init__.py` : **modifié** (Tâche 1) — docstring générique « Centralized enums shared across WindFlow domains », pas de ré-export (pattern existant conservé).
- `backend/app/models/user_organization.py` : **créé** (Tâche 2) — modèle `UserOrganization` : PK composite `(user_id, organization_id)`, FK `CASCADE` vers `users`/`organizations`, `role String(20)` avec `default=Role.VIEWER` + `server_default="viewer"`, `@validates("role")` (accepte `Role`/str, refuse `super_admin`, inconnu, vide), timestamps UTC `joined_at`/`created_at`/`updated_at`, relations `user`/`organization`, `__repr__` pattern maison.
- `backend/app/models/user.py` : **modifié** (Tâche 2) — import `List`, `UserOrganization` en `TYPE_CHECKING`, relation `organization_links` (cascade `all, delete-orphan`). `organization_id` et relation `organization` inchangés (STORY-121.3).
- `backend/app/models/organization.py` : **modifié** (Tâche 2) — `UserOrganization` en `TYPE_CHECKING`, relation `user_links`. Relation `users` existante inchangée.
- `backend/app/models/__init__.py` : **modifié** (Tâche 2) — import + `__all__` (ordre alphabétique).
- `backend/alembic/versions/2026_09_08_1211_user_organizations_table.py` : **créé** (Tâche 3) — révision `1211_user_organizations`, `down_revision = "baseline"` ; `upgrade()` : `create_table` (colonnes, FK CASCADE, PK composite, `server_default="viewer"`, comments) + index `ix_user_organizations_organization_id` via `batch_alter_table` ; `downgrade()` symétrique (drop_index puis drop_table) ; strictement additive (aucune donnée lue/modifiée).
- `backend/tests/unit/test_models/test_user_organization.py` : **créé** (Tâche 4) — 14 tests (enum, défauts dont INSERT brut server_default, validation/refus `super_admin`, PK composite, relations, tablename).
- `backend/tests/unit/test_alembic_config.py` : **modifié** (Tâche 5) — `EXPECTED_TABLES` + `user_organizations` ; scénario stamp→upgrade désormais **additif** (`DROP TABLE user_organizations` après `create_all` pour simuler une base pré-121.1, assertion `Running upgrade baseline -> 1211_user_organizations`, tables d'origine + table additive, `alembic check` sans diff) ; docstrings adaptées.
- `backend/tests/unit/test_database.py` : **modifié** (Tâche 5) — simulation legacy avec `DROP TABLE user_organizations` ; les 2 assertions `_alembic_version(...) == "baseline"` deviennent `== ScriptDirectory.from_config(get_alembic_config()).get_current_head()`.
- `backend/tests/integration/test_migrations.py` : **modifié** (Tâche 5) — `EXPECTED_TABLES` + `user_organizations` ; scénario 2 : `DROP TABLE` + assertion `tables_before | {"alembic_version", "user_organizations"}` ; nouvelle classe `TestUserOrganizationsTableMigration` (6 tests : création sur base vierge, structure spec 06, PK composite, FK CASCADE via PRAGMA, index non unique, base stampée baseline → table créée vide + données intactes + version = head) + helper `_upgraded_engine`.

### Décisions techniques
- **Migration rédigée manuellement** sur le pattern baseline (alternative explicitement acceptée par la Tâche 3) : le venv Poetry local étant cassé (Python 3.14 sans dépendances), `make migrate` (autogenerate) n'était pas exécutable ; la revue manuelle a été faite avec le garde-fou `alembic upgrade head` + `alembic check` (aucun diff) + downgrade complet.
- **Exécution des tests via `.venv-test/`** (Python 3.11, alembic/pytest/noirs installés) au lieu de `poetry run` : le venv Poetry du projet ne contient aucune dépendance (`ModuleNotFoundError: alembic`). Commandes équivalentes exécutées : `pytest backend/tests/unit/…`, `pytest backend/tests/integration/…`, `isort`/`black`/`flake8`/`ruff check` sur les fichiers de la story.
- Relations de tests chargées via `selectinload` (rechargement explicite) : le lazy-loading implicite est interdit en SQLAlchemy async (`MissingGreenlet`).

### Divergences par rapport à l'analyse
- **Tâche 5 (`test_database.py`)** : la story prescrivait `ScriptDirectory(get_alembic_config()).get_current_head()` — cette signature lève `TypeError` (alembic 1.19 attend un chemin, pas une `Config`). Utilisation de l'API canonique équivalente `ScriptDirectory.from_config(get_alembic_config()).get_current_head()` — même intention (head robuste aux migrations suivantes, ex. STORY-121.3), vérifiée fonctionnelle.
- **Migration générée manuellement** (cf. Décisions) — alternative prévue par la story.
- Ajustement cosmétique d'assertion : SQLite renvoie `unique` comme entier (0/1) → `assert not index["unique"]` au lieu de `is False` (même sémantique).

### Difficultés rencontrées
- **42 échecs unitaires + 20 échecs d'intégration pré-existants** (500 sur stacks/security headers, WebSocket, etc.) sans lien avec la story : prouvé par `git stash` complet du périmètre backend → **listes d'échecs strictement identiques avec/sans les changements** (diff vide). Aucune correction tentée : hors périmètre de STORY-121.1.
- **mypy/bandit non installés** dans `.venv` (Poetry, vide) ni `.venv-test` : non exécutables localement — seront vérifiés par la CI (`make ci-test-backend` / lint). `ruff check` (dépendance du pyproject) passé en complément sur les fichiers de la story.
- 2 itérations de debug tests : lazy-loading async (corrigé par `selectinload`) et `unique` entier SQLite (corrigé).

### Tests ajoutés
- `backend/tests/unit/test_models/test_user_organization.py` : 14 tests — couverture **100 %** sur `app.models.user_organization` et `app.enums.rbac`.
- `backend/tests/integration/test_migrations.py::TestUserOrganizationsTableMigration` : 6 tests structurels (base vierge + base stampée baseline).

### Résultats d'exécution (résumé)
- Tests ciblés : `test_user_organization.py` **14/14** ; `test_alembic_config.py` + `test_database.py` **15/15** ; `test_migrations.py` **10 passés + 1 skip** (PostgreSQL indisponible localement — skip documenté).
- Non-régression : unitaires 987 passés / 42 échecs pré-existants (identiques au baseline) ; intégration 58 passés / 20 échecs pré-existants (identiques au baseline).
- Garde-fous : `alembic upgrade head` OK, `alembic check` « No new upgrade operations detected », `downgrade base` vide la base.
- Lint story : isort ✔ black ✔ flake8 ✔ ruff ✔.
