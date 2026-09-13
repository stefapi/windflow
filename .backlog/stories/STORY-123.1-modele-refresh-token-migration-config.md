# STORY-123.1 : Modèle `RefreshToken`, migration Alembic et configuration

**Statut :** DONE
**Story Parente :** STORY-123 — Refresh tokens révocables — table, rotation et logout invalidant (P1-3, partie refresh)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'utilisateur de WindFlow, je veux une table dédiée `refresh_tokens` stockant le **hash** des refresh tokens (jamais la valeur en clair), créée par migration Alembic conforme au schéma spec 06, avec une durée de vie configurable (`REFRESH_TOKEN_EXPIRE_DAYS`), afin de poser le socle de données des tokens révocables (rotation, logout invalidant, révocation globale) implémenté par les sous-stories suivantes.

Cette sous-story est la première étape de STORY-123 (découpée en raison de sa complexité : ~9 tâches / 11 fichiers) : elle fournit le socle modèle/migration/configuration sur lequel s'appuient STORY-123.2 (service + émission opaque), STORY-123.3 (endpoints auth) et STORY-123.4 (purge + tests transverses).

## Critères d'acceptation (AC)

- [x] AC 1 : La table `refresh_tokens` existe via migration Alembic (STORY-120) conformément au schéma spec 06 ; le refresh token émis au login est **opaque** (pas un JWT), seul son **hash** est stocké en base ; durée 7 jours configurable (`REFRESH_TOKEN_EXPIRE_DAYS`). *(part structurelle validée dans cette sous-story : table + migration + setting ; l'émission opaque au login est portée par STORY-123.2/123.3)*

> **Note de découpe :** cette sous-story couvre la part **structurelle** de l'AC 1 (table via migration + setting configurable). La part « émission opaque au login » est implémentée par STORY-123.2 (`jwt.py`) et démontrée de bout en bout par STORY-123.3 (`/login` persiste la ligne) — l'AC n'est cochable sur la story parente qu'une fois les trois fermées.

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-12) — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches.

**Couches impactées :** Backend uniquement — models, migrations Alembic, configuration, tests backend (unit + integration). **Aucun endpoint**, aucun schéma Pydantic, aucun impact frontend/CLI.

**Spécifications de référence :**
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités auth et audit → `RefreshToken` (schéma SQL cible) ;
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Refresh token (opaque, hash en base), § Configuration (`REFRESH_TOKEN_EXPIRE_DAYS`).

**Fichiers de référence (patterns vérifiés) :**
- Modèle FK CASCADE + timestamps + `__repr__` → [`backend/app/models/target_capability.py`](../../backend/app/models/target_capability.py) et [`backend/app/models/user_organization.py`](../../backend/app/models/user_organization.py) (récent, pattern UUID `String(36)`) ;
- Migration additive (`op.create_table` + index + downgrade symétrique) → pattern révision `1211` ([`backend/alembic/versions/`](../../backend/alembic/versions/)) — **head actuel : `1213_users_org_migration`** (down_revision de la nouvelle migration) ;
- Runner migrations / garde-fou `alembic check` → [`backend/app/database.py`](../../backend/app/database.py) (`run_migrations()`) ;
- Configuration pydantic-settings → [`backend/app/config.py`](../../backend/app/config.py) ;
- Tests migrations à adapter → [`backend/tests/unit/test_alembic_config.py`](../../backend/tests/unit/test_alembic_config.py), [`backend/tests/integration/test_migrations.py`](../../backend/tests/integration/test_migrations.py), [`backend/tests/unit/test_database.py`](../../backend/tests/unit/test_database.py) ;
- Fixtures disponibles : `db_session`, `test_user`, `test_organization` ([`backend/tests/conftest.py`](../../backend/tests/conftest.py)) — le schéma de test provient des migrations (`_migrated_schema_template`), la nouvelle table y sera présente automatiquement.

**Décisions d'analyse :**
- **Schéma cible spec 06** : `refresh_tokens (id, user_id FK CASCADE, token_hash VARCHAR(255), expires_at, created_at)` + index `user_id` et `expires_at` ;
- **Colonne `revoked_at` (nullable) ajoutée** au-delà du schéma spec 06 minimal : nécessaire pour (a) **détecter la réutilisation d'un token consommé/révoqué** (AC 2 — révocation défensive de la famille) et (b) laisser une trace auditable de la révocation (AC 3 — logout). Alternative rejetée : suppression physique de la ligne (impossible de distinguer « token inconnu » de « token consommé réutilisé » et donc de déclencher la révocation défensive) ;
- **`token_hash` non unique-required au sens applicatif** : plusieurs lignes peuvent partager un hash si un token est régénéré identique (probabilité négligeable avec `secrets.token_urlsafe`, cf. 123.2) — pas de contrainte d'unicité imposée par la spec ;
- **Setting `refresh_token_expire_days: int = 7`** dans `config.py` (env var `REFRESH_TOKEN_EXPIRE_DAYS`, spec 07 § Configuration) ;
- **Révision Alembic** : `revision = "1231_refresh_tokens"`, `down_revision = "1213_users_org_migration"` (identifiant lisible, pattern maison).

## ⚠️ Points d'arbitrage à traiter dans cette sous-story

**Arbitrage n°1 — bcrypt vs Argon2 (hash du `token_hash`) :**
- **Constat :** l'AC 4 de STORY-123 et la spec exigent « hash **bcrypt** en base », mais le code utilise **Argon2** ([`pwd_context` schemes="argon2"] dans `backend/app/auth/`) et **bcrypt n'est pas une dépendance du lock Poetry** ;
- **Option A (recommandée par l'analyse) :** réutiliser le `pwd_context` Argon2 existant — cohérent avec l'arbitrage **F2 déjà validé par l'utilisateur** (Argon2 retenu, migration bcrypt→Argon2id portée par STORY-130) ; zéro dépendance nouvelle ; l'AC 4 « bcrypt » se lit alors « hash fort vérifié, jamais la valeur brute » (**divergence à documenter** dans les Notes d'implémentation et à consigner pour la correction de spec portée par STORY-252) ;
- **Option B :** ajouter `bcrypt` aux dépendances et l'utiliser pour les refresh tokens uniquement — conforme à la lettre de l'AC 4 mais introduit un double algorithme de hash dans le codebase (contraire à F2) ;
- **Impact :** le choix conditionne STORY-123.2 (fonction de hash du service) et STORY-123.4 (test « jamais la valeur brute en base »). **Trancher en début d'implémentation et consigner la décision ici-même.**

**Exigences sécurité identifiées (Phase 2.6 de l'analyse) :**
- Validation : `token_hash VARCHAR(255)` borné, `expires_at` non nul ;
- Exposition : par conception, seule la colonne `token_hash` existe — **jamais de colonne pour la valeur en clair** (garantie structurelle) ;
- Audit : non requis ici (migration structurelle — audit formel reporté à STORY-125) ;
- Données : migration **strictement additive** — aucune ligne existante lue/modifiée.

## Dépendances

- STORY-120 (Alembic) — DONE ✔ (prérequis satisfait ; head `1213`).
- Bloque : STORY-123.2, STORY-123.3, STORY-123.4.

## Périmètre indicatif (répartition des tâches identifiées par l'analyse de STORY-123)

| # | Tâche (issue de l'analyse STORY-123) | Périmètre de cette sous-story |
|---|--------------------------------------|-------------------------------|
| T1 | Modèle + migration Alembic | ✅ Complet |
| T2 | Config `REFRESH_TOKEN_EXPIRE_DAYS` | ✅ Complet |
| T3 | Service (hash/rotation/révocations/purge) | ❌ STORY-123.2 |
| T4 | `jwt.py` token opaque | ❌ STORY-123.2 |
| T5 | `/login` + `/register` persistance | ❌ STORY-123.3 |
| T6 | `/refresh` rotation + révocation famille | ❌ STORY-123.3 |
| T7 | `/logout` révocant | ❌ STORY-123.3 |
| T8 | Job de purge lifespan | ❌ STORY-123.4 |
| T9 | Tests (modèle/migration → ici ; service/endpoint/transverses → 123.2/123.3/123.4) | 🔶 Partie modèle + migration |

**Hors périmètre :** service et logique de rotation (123.2) ; endpoints et schémas Pydantic (123.3) ; job de purge et tests transverses (123.4).

## Tâches d'implémentation détaillées

### Tâche 1 : Modèle `RefreshToken`
**Objectif :** Créer le modèle SQLAlchemy de la table `refresh_tokens` conforme au schéma spec 06 (augmenté de `revoked_at`), avec FK CASCADE et index de recherche.
**Fichiers :**
- `backend/app/models/refresh_token.py` — Créer — Nouveau modèle (pattern : `backend/app/models/user_organization.py`). Classe `RefreshToken(Base)` :
  - `__tablename__ = "refresh_tokens"` ;
  - `id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))` (convention maison UUID `String(36)`) ;
  - `user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)` (index requis spec 06) ;
  - `token_hash: Mapped[str] = mapped_column(String(255), nullable=False)` — **jamais de valeur en clair** ;
  - `expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)` (index requis spec 06 — purge) ;
  - `revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)` (décision d'analyse ci-dessus) ;
  - `created_at` (et `updated_at` selon conventions `.roo/rules/30-code-standards.md`) : `DateTime` non nuls, defaults UTC ;
  - relation `user: Mapped["User"] = relationship("User", back_populates=...)` (côté `User` : relation `refresh_tokens` avec `cascade="all, delete-orphan"`) — imports `TYPE_CHECKING` ;
  - `__repr__` cohérent avec le pattern (`<RefreshToken(user_id=..., expires_at=..., revoked=...)>` — **sans le hash**).
- `backend/app/models/user.py` — Modifier — Ajouter la relation `refresh_tokens` (pattern `organization_links` posé par STORY-121.1).
- `backend/app/models/__init__.py` — Modifier — Importer `RefreshToken` et l'ajouter à `__all__` (ordre alphabétique) — indispensable pour `Base.metadata` (autogenerate + schéma de test conftest).
**Exigences sécurité :** Garantie structurelle « hash uniquement » (aucune colonne pour la valeur claire) ; `ondelete="CASCADE"` (suppression user → purge de ses refresh tokens).
**Dépend de :** Aucune

### Tâche 2 : Migration Alembic additive
**Objectif :** Créer la table `refresh_tokens` par migration Alembic posée sur le head courant (`1213`).
**Fichiers :**
- `backend/alembic/versions/..._1231_refresh_tokens_table.py` — Créer — Nouvelle migration (pattern révision `1211`). En-tête : `revision: str = "1231_refresh_tokens"`, `down_revision: Union[str, None] = "1213_users_org_migration"` ; docstring documentant STORY-123.1 et le caractère **additif**. Génération recommandée : `make migrate MIGRATION_MESSAGE="add refresh_tokens table"` puis **revue/ajustement manuel** (vérifier index `ix_refresh_tokens_user_id` / `ix_refresh_tokens_expires_at`, complétude du downgrade, docstring). Contenu cible :
  - `upgrade()` : `op.create_table("refresh_tokens", ...)` avec les colonnes de la Tâche 1 + `sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE")` + PK `id` ; puis index sur `user_id` et `expires_at` (`batch_alter_table` si SQLite) ;
  - `downgrade()` symétrique : `drop_index` ×2 puis `drop_table("refresh_tokens")` ;
  - après la tâche : `alembic check` sans diff (garde-fou vérifié par les tests existants) et le downgrade complet continue de vider la base.
**Exigences sécurité :** Migration strictement additive — aucun accès aux données, aucune perte possible.
**Dépend de :** Tâche 1

### Tâche 3 : Configuration `REFRESH_TOKEN_EXPIRE_DAYS`
**Objectif :** Exposer la durée de vie des refresh tokens en setting pydantic-settings (7 jours par défaut), remplaçant toute durée codée en dur.
**Fichiers :**
- `backend/app/config.py` — Modifier — Ajouter `refresh_token_expire_days: int = 7` (env var `REFRESH_TOKEN_EXPIRE_DAYS`, spec 07 § Configuration) avec docstring. Vérifier qu'aucune constante JWT refresh 7 j résiduelle ne reste source de vérité alternative (renvoi vers `jwt.py` géré par STORY-123.2).
**Exigences sécurité :** Aucune exigence spécifique (setting code-only, pas d'input utilisateur).
**Dépend de :** Aucune

### Tâche 4 : Tests du modèle et adaptation des tests migrations (non-régression STORY-120)
**Objectif :** Couvrir le modèle (défauts, FK CASCADE, index) et mettre à jour les tests Alembic existants impactés par l'ajout d'une table.
**Fichiers :**
- `backend/tests/unit/test_models/test_refresh_token.py` — Créer — Fixtures `db_session`, `test_user`. Détail en section « Tests à écrire ».
- `backend/tests/unit/test_alembic_config.py` — Modifier — Ajouter `refresh_tokens` à `EXPECTED_TABLES` (assertion d'égalité stricte avec `Base.metadata.tables`).
- `backend/tests/integration/test_migrations.py` — Modifier — Idem `EXPECTED_TABLES` ; scénario « stamp baseline → upgrade head » applique désormais les migrations additives (1211/1212/1213/1231) ; si une simulation de base legacy par `Base.metadata.create_all()` est utilisée, exécuter `DROP TABLE refresh_tokens` après le `create_all` pour simuler fidèlement une base antérieure (pattern posé par STORY-121.1).
- `backend/tests/unit/test_database.py` — Modifier — Vérifier que les assertions de version utilisent `ScriptDirectory(get_alembic_config()).get_current_head()` (robuste aux migrations suivantes — pattern posé par STORY-121.1).
**Exigences sécurité :** Tests du CASCADE (suppression user → lignes purgées) — garantie d'hygiène des données.
**Dépend de :** Tâche 2

## Tests à écrire

### Backend — unitaires
- `backend/tests/unit/test_models/test_refresh_token.py`
  - `test_create_refresh_token_defaults` — création avec defaults valides (id UUID, `revoked_at` NULL, `created_at` défini)
  - `test_token_hash_max_length` — colonne `String(255)` respectée
  - `test_user_deletion_cascades` — suppression du user → lignes `refresh_tokens` purgées (CASCADE)
  - `test_repr_does_not_expose_hash` — `__repr__` sans la valeur du hash

### Backend — intégration (migrations)
- `test_migrations.py` : table `refresh_tokens` présente après `upgrade head` (base vierge **et** baseline stampée) ; downgrade → table absente
- `test_alembic_config.py` : `EXPECTED_TABLES` inclut `refresh_tokens` (égalité stricte métadonnées ↔ migrations)

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_models/test_refresh_token.py backend/tests/unit/test_alembic_config.py backend/tests/unit/test_database.py -v
poetry run pytest backend/tests/integration/test_migrations.py -v
make backend-lint && make backend-typecheck
```

## État d'avancement technique
- [x] Tâche 1 : Modèle `RefreshToken` + relations
- [x] Tâche 2 : Migration Alembic `1231_refresh_tokens` (down_revision `1213`)
- [x] Tâche 3 : Setting `refresh_token_expire_days` (7 j par défaut)
- [x] Tâche 4 : Tests modèle + adaptation tests migrations (EXPECTED_TABLES)

## Notes d'implémentation

**Date :** 2026-09-13

### Décision d'arbitrage n°1 — bcrypt vs Argon2 (hash du `token_hash`)
**Option A retenue : réutiliser le `pwd_context` Argon2 existant** (`backend/app/auth/`).
- Conforme à l'arbitrage **F2 déjà validé par l'utilisateur** (Argon2 retenu, correction de spec portée par STORY-252) ;
- zéro dépendance nouvelle (bcrypt absent du lock Poetry) ;
- l'AC 4 « hash bcrypt » de STORY-123 se lit « hash fort vérifié, jamais la valeur brute » ;
- **consigné pour STORY-123.2** (fonction de hash du service : `pwd_context.hash`) et **STORY-123.4** (test « jamais la valeur brute en base »).

### Fichiers créés
- `backend/app/models/refresh_token.py` — modèle `RefreshToken` (table `refresh_tokens` : `id` UUID String(36) PK, `user_id` FK CASCADE indexé, `token_hash` String(255), `expires_at` indexé, `revoked_at` nullable, timestamps) + relation `user` + `__repr__` sans hash ;
- `backend/alembic/versions/2026_09_12_1231_refresh_tokens_table.py` — migration **strictement additive** `1231_refresh_tokens` (`down_revision = "1213_users_org_migration"`), index `ix_refresh_tokens_user_id`/`ix_refresh_tokens_expires_at` via `batch_alter_table`, downgrade symétrique ;
- `backend/tests/unit/test_models/test_refresh_token.py` — 10 tests (défauts, bornes String(255), CASCADE, isolation par user, `__repr__` sans hash, colonnes exactes, relation).

### Fichiers modifiés
- `backend/app/models/user.py` — relation `refresh_tokens` (`cascade="all, delete-orphan"`, pattern `organization_links`) + import `TYPE_CHECKING` ;
- `backend/app/models/__init__.py` — export `RefreshToken` dans `__all__` (indispensable pour `Base.metadata`) ;
- `backend/app/config.py` — setting `refresh_token_expire_days: int = Field(default=7, ge=1)` (env var `REFRESH_TOKEN_EXPIRE_DAYS`, spec 07) ;
- `backend/tests/unit/test_alembic_config.py` — `EXPECTED_TABLES` + `refresh_tokens` ; scénario stamp : `DROP TABLE refresh_tokens` dans la simulation legacy (pattern STORY-121.1) ;
- `backend/tests/integration/test_migrations.py` — `EXPECTED_TABLES` + `refresh_tokens` ; les 3 simulations de bases legacy droppent désormais `refresh_tokens` après `create_all` ;
- `backend/tests/unit/test_database.py` — `DROP TABLE refresh_tokens` dans la simulation legacy (les assertions de version utilisaient déjà `get_current_head()`, robustes).

### Divergences par rapport à l'analyse
- **Tâche 3** : la constante legacy `jwt_refresh_token_expire_days` n'a **pas** été supprimée — elle reste consommée par `create_refresh_token()` dans `backend/app/auth/jwt.py` (le refresh JWT actuel). Son retrait est explicitement porté par STORY-123.2 (bascule opaque) ; le supprimer ici aurait cassé `jwt.py`. Le nouveau setting `refresh_token_expire_days` est la source de vérité pour `refresh_tokens.expires_at`.
- **Génération migration** : `make migrate` (autogenerate) non utilisé — le wrapper `poetry run alembic` du repo pointe vers un venv racine sans alembic (problème d'environnement local). Migration écrite à la main sur le pattern de la révision `1211`, chaîne vérifiée programmatiquement (`ScriptDirectory` : head unique `1231_refresh_tokens` ← `1213` ← `1211` ← `baseline`).

### Difficultés rencontrées
- Environnement : venv Poetry racine incomplet (pas d'alembic) → validations exécutées via `.venv-test` du workspace (pytest/black/isort/flake8/mypy) ;
- Full-suite unitaire : 1386 passed / 1 error (`test_ws_auth.py` teardown TestClient/anyio, **préexistant sur HEAD propre** — vérifié par stash : 48 errors sur la même sélection avant la story ; le test passe isolément et en sous-ensemble `test_websocket/` 68/68).

### Tests ajoutés et validation
- `tests/unit/test_models/test_refresh_token.py` : **couverture `app/models/refresh_token.py` = 100 %** (10 tests) ;
- Ciblés : `pytest tests/unit/test_models/test_refresh_token.py tests/unit/test_alembic_config.py tests/unit/test_database.py` → 24 passed ; `pytest tests/integration/test_migrations.py` → 33 passed, 1 skipped (variante PostgreSQL, skip attendu sans service PG) ;
- Non-régression : `pytest tests/unit/` → 1386 passed, 1 error WS préexistant ;
- Lint : black + isort + flake8 OK sur les 9 fichiers touchés ; mypy : 0 erreur sur les fichiers de la story (4 erreurs préexistantes dans des services non modifiés : stubs yaml absents du venv-test).
