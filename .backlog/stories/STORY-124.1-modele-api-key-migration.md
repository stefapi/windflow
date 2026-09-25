# STORY-124.1 : Modèle `APIKey` et migration Alembic

**Statut :** DONE
**Story Parente :** STORY-124 — Clés API `wf_ak_` — table `api_keys`, auth `X-API-Key` coexistant avec JWT (P1-3, partie clés API)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'utilisateur de WindFlow, je veux une table dédiée `api_keys` stockant le **hash** des clés API `wf_ak_` (jamais la valeur en clair), créée par migration Alembic conforme au schéma spec 06, avec expiration optionnelle (`expires_at` null = n'expire jamais) et révocation distincte de l'expiration (`revoked`), afin de poser le socle de données des clés API (génération, auth `X-API-Key`, révocation) implémenté par les sous-stories suivantes.

Cette sous-story est la première étape de STORY-124 (découpée en raison de sa complexité : 7 tâches / 8 fichiers hors tests) : elle fournit le socle modèle/migration sur lequel s'appuient STORY-124.2 (génération + hash déterministe + service + schemas), STORY-124.3 (endpoints + intégration `get_current_user`) et STORY-124.4 (tests transverses et sécurité).

## Critères d'acceptation (AC)

- [x] AC 1 : La table `api_keys` existe via migration Alembic (STORY-120) conformément au schéma spec 06 ; la création génère `wf_ak_` + 48 caractères (`secrets.token_urlsafe`), stocke **uniquement le hash bcrypt** (jamais la clé), et retourne la clé complète **une seule fois** à la création ; expiration configurable à la création (null = n'expire jamais). *(part structurelle validée dans cette sous-story : table + migration conformes spec 06 ; la génération `wf_ak_` + 48 caractères, le hash et l'affichage unique sont portés par STORY-124.2/124.3)*

> **Note de découpe :** cette sous-story couvre la part **structurelle** de l'AC 1 (table via migration, schéma spec 06 complet, `expires_at` nullable). La part « génération + hash + affichage unique » est implémentée par STORY-124.2 (`jwt.py` + service) et démontrée de bout en bout par STORY-124.3 (`POST /auth/api-keys`) — l'AC n'est cochable sur la story parente qu'une fois les sous-stories fermées. La mention « hash bcrypt » se lit « hash fort vérifié, jamais la clé en clair » — **arbitrage Argon2 déterministe** tranché dans STORY-124.2 (alignement F2/STORY-123, divergence consignée pour la correction de spec portée par STORY-252).

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-13) — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches.

**Couches impactées :** Backend uniquement — models, migration Alembic, tests backend (unit + integration). **Aucun endpoint**, aucun schéma Pydantic, aucun service, aucun impact frontend/CLI.

**Spécifications de référence :**
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités auth et audit → `APIKey` (schéma SQL cible) ;
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Authentification par clé API (format `wf_ak_`, hash, affichage unique, expiration, révocation).

**Fichiers de référence (patterns validés par STORY-123.1) :**
- Modèle → pattern [`backend/app/models/refresh_token.py`](../../backend/app/models/refresh_token.py) : PK `String(36)` UUID, FK `users.id` `ondelete=CASCADE`, colonnes indexées, docstring de sécurité, `__repr__` sans secret ;
- Migration → pattern [`backend/alembic/versions/2026_09_12_1231_refresh_tokens_table.py`](../../backend/alembic/versions/2026_09_12_1231_refresh_tokens_table.py) : strictement additive, `batch_alter_table` pour les index, commentaires de colonnes — **head actuel : `1231_refresh_tokens`** (`down_revision` de la nouvelle migration) ;
- Tests migrations à adapter → [`backend/tests/unit/test_alembic_config.py`](../../backend/tests/unit/test_alembic_config.py), [`backend/tests/integration/test_migrations.py`](../../backend/tests/integration/test_migrations.py), [`backend/tests/unit/test_database.py`](../../backend/tests/unit/test_database.py) ;
- Fixtures disponibles : `db_session`, `test_user`, `test_organization` ([`backend/tests/conftest.py`](../../backend/tests/conftest.py)) — le schéma de test provient des migrations (`_migrated_schema_template`), la nouvelle table y sera présente automatiquement.

**Décisions d'analyse :**
- **Schéma cible spec 06** : `api_keys (id, user_id FK CASCADE, name VARCHAR(100), key_hash VARCHAR(255), expires_at TIMESTAMP null, last_used_at TIMESTAMP null, revoked BOOLEAN DEFAULT FALSE, created_at)` + index `user_id` ;
- **`revoked` booléen (et non `revoked_at`)** : conforme au schéma spec 06 — l'expiration porte la sémantique temporelle (`expires_at`), `revoked` porte l'action administrative ; les deux états restent **distincts** (arbitrage : une clé expirée n'est pas `revoked=true` — documenté dans STORY-124.2/124.3) ;
- **Révision Alembic** : `revision = "1241_api_keys"`, `down_revision = "1231_refresh_tokens"` (identifiant lisible, pattern maison).

## Dépendances

- STORY-120 (Alembic) — DONE ✔ (prérequis satisfait ; head `1231_refresh_tokens`).
- Bloque : STORY-124.2, STORY-124.3, STORY-124.4.

## Tâches d'implémentation détaillées

### Tâche 1 : Modèle `APIKey`
**Objectif :** Créer le modèle SQLAlchemy de la table `api_keys` conforme au schéma spec 06, avec FK CASCADE, index de recherche et garantie structurelle « hash uniquement ».
**Fichiers :**
- `backend/app/models/api_key.py` — Créer — Nouveau modèle (pattern : [`backend/app/models/refresh_token.py`](../../backend/app/models/refresh_token.py)). Classe `APIKey(Base)` :
  - `__tablename__ = "api_keys"` ; docstring de sécurité (jamais de valeur en clair, hash uniquement) ;
  - `id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))` (convention maison UUID `String(36)`) ;
  - `user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)` (index requis spec 06) ;
  - `name: Mapped[str] = mapped_column(String(100), nullable=False)` — libellé choisi par l'utilisateur ;
  - `key_hash: Mapped[str] = mapped_column(String(255), nullable=False)` — **jamais de valeur en clair** ;
  - `expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)` — null = n'expire jamais ;
  - `last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)` — alimenté par STORY-124.2/124.3 (throttlé) ;
  - `revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)` ;
  - `created_at` : `DateTime` non nul, default UTC (naive — pattern `_utcnow_naive` du codebase) ;
  - relation `user: Mapped["User"] = relationship("User", back_populates="api_keys")` (côté `User` : relation `api_keys` avec `cascade="all, delete-orphan"`) — imports `TYPE_CHECKING` ;
  - `__repr__` cohérent avec le pattern (`<APIKey(id=..., user_id=..., name=..., revoked=...)>` — **sans le hash ni la clé**).
- `backend/app/models/user.py` — Modifier — Ajouter la relation `api_keys` (pattern `refresh_tokens` posé par STORY-123.1).
- `backend/app/models/__init__.py` — Modifier — Importer `APIKey` et l'ajouter à `__all__` (ordre alphabétique) — indispensable pour `Base.metadata` (autogenerate + schéma de test conftest).
**Exigences sécurité :** Garantie structurelle « hash uniquement » (aucune colonne pour la valeur claire) ; `ondelete="CASCADE"` (suppression user → purge de ses clés) ; `__repr__` sans secret.
**Dépend de :** Aucune

### Tâche 2 : Migration Alembic additive
**Objectif :** Créer la table `api_keys` par migration Alembic chaînée sur le head courant (`1231_refresh_tokens`).
**Fichiers :**
- `backend/alembic/versions/..._1241_api_keys_table.py` — Créer — Nouvelle migration (pattern révision `1231`). En-tête : `revision: str = "1241_api_keys"`, `down_revision: Union[str, None] = "1231_refresh_tokens"` ; docstring documentant STORY-124.1 et le caractère **additif**. Génération recommandée : `make migrate MIGRATION_MESSAGE="add api_keys table"` puis **revue/ajustement manuel**. Contenu cible :
  - `upgrade()` : `op.create_table("api_keys", ...)` avec les colonnes de la Tâche 1 + `sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE")` + PK `id` ; puis index sur `user_id` (`batch_alter_table` si SQLite) ; commentaires de colonnes (pattern `1231`) ;
  - `downgrade()` symétrique : `drop_index` puis `drop_table("api_keys")` ;
  - après la tâche : `alembic check` sans diff (garde-fou vérifié par les tests existants) et le downgrade complet continue de vider la base ;
  - ⚠️ Rappel environnement (divergence STORY-123.1) : le wrapper `poetry run alembic` du repo pointe vers un venv racine sans alembic — si `make migrate` échoue, écrire la migration à la main sur le pattern `1231` et vérifier la chaîne programmatiquement (`ScriptDirectory` : head unique `1241_api_keys` ← `1231` ← `1213` ← `1211` ← `baseline`).
**Exigences sécurité :** Migration strictement additive — aucun accès aux données, aucune perte possible.
**Dépend de :** Tâche 1

### Tâche 3 : Tests du modèle et adaptation des tests migrations (non-régression STORY-120)
**Objectif :** Couvrir le modèle (défauts, FK CASCADE, bornes, `__repr__` sans secret) et mettre à jour les tests Alembic existants impactés par l'ajout d'une table.
**Fichiers :**
- `backend/tests/unit/test_models/test_api_key.py` — Créer — Fixtures `db_session`, `test_user`. Détail en section « Tests à écrire ».
- `backend/tests/unit/test_alembic_config.py` — Modifier — Ajouter `api_keys` à `EXPECTED_TABLES` (assertion d'égalité stricte avec `Base.metadata.tables`).
- `backend/tests/integration/test_migrations.py` — Modifier — Idem `EXPECTED_TABLES` ; scénario « stamp baseline → upgrade head » applique désormais les migrations additives (1211/1213/1231/1241) ; si une simulation de base legacy par `Base.metadata.create_all()` est utilisée, exécuter `DROP TABLE api_keys` après le `create_all` pour simuler fidèlement une base antérieure (pattern posé par STORY-121.1/123.1).
- `backend/tests/unit/test_database.py` — Modifier — Idem `DROP TABLE api_keys` dans la simulation legacy si applicable (les assertions de version utilisent déjà `get_current_head()`, robustes).
**Exigences sécurité :** Tests du CASCADE (suppression user → lignes purgées) — garantie d'hygiène des données ; test `__repr__` sans hash.
**Dépend de :** Tâche 2

## Tests à écrire

### Backend — unitaires (modèle)
- `backend/tests/unit/test_models/test_api_key.py`
  - `test_create_api_key_defaults` — création avec defaults valides (id UUID, `revoked=False`, `expires_at` NULL, `last_used_at` NULL, `created_at` défini)
  - `test_name_max_length` — colonne `String(100)` respectée
  - `test_key_hash_max_length` — colonne `String(255)` respectée
  - `test_user_deletion_cascades` — suppression du user → lignes `api_keys` purgées (CASCADE)
  - `test_repr_does_not_expose_hash` — `__repr__` sans la valeur du hash ni de la clé
  - `test_revoked_distinct_from_expiration` — `revoked` et `expires_at` sont deux états indépendants (clé expirée reste `revoked=False`)

### Backend — intégration (migrations)
- `test_migrations.py` : table `api_keys` présente après `upgrade head` (base vierge **et** baseline stampée) ; downgrade → table absente
- `test_alembic_config.py` : `EXPECTED_TABLES` inclut `api_keys` (égalité stricte métadonnées ↔ migrations)

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_models/test_api_key.py backend/tests/unit/test_alembic_config.py backend/tests/unit/test_database.py -v
poetry run pytest backend/tests/integration/test_migrations.py -v
make backend-lint && make backend-typecheck
```

## État d'avancement technique
- [x] Tâche 1 : Modèle `APIKey` + relations
- [x] Tâche 2 : Migration Alembic `1241_api_keys` (down_revision `1231`)
- [x] Tâche 3 : Tests modèle + adaptation tests migrations (EXPECTED_TABLES)

## Notes d'implémentation

**Date :** 2026-09-13

### Fichiers modifiés/créés
- `backend/app/models/api_key.py` : **créé** — modèle `APIKey` (table `api_keys`, schéma spec 06 complet : `id` UUID String(36) PK, `user_id` FK `users.id` `ondelete=CASCADE` indexé, `name` String(100), `key_hash` String(255), `expires_at` DateTime null, `last_used_at` DateTime null, `revoked` Boolean default False, `created_at` DateTime non nul) — docstring de sécurité « hash uniquement », `__repr__` sans hash ni clé ;
- `backend/app/models/user.py` : **modifié** — import `TYPE_CHECKING` `APIKey` + relation `api_keys` (`cascade="all, delete-orphan"`, `back_populates`) ;
- `backend/app/models/__init__.py` : **modifié** — import `APIKey` (ordre alphabétique) + ajout à `__all__` → enregistré dans `Base.metadata` (schéma de test conftest + `alembic check`) ;
- `backend/alembic/versions/2026_09_13_1241_api_keys_table.py` : **créé** — migration additive `1241_api_keys` (`down_revision = "1231_refresh_tokens"`), `create_table` + `ForeignKeyConstraint ondelete=CASCADE` + index `ix_api_keys_user_id` via `batch_alter_table`, commentaires de colonnes (pattern 1231), `downgrade` symétrique (drop index puis drop table) ;
- `backend/tests/unit/test_models/test_api_key.py` : **créé** — 13 tests modèle ;
- `backend/tests/unit/test_alembic_config.py` : **modifié** — `EXPECTED_TABLES` += `api_keys`, simulation legacy += `DROP TABLE api_keys` (2 endroits), assertions after-upgrade += `api_keys` ;
- `backend/tests/integration/test_migrations.py` : **modifié** — `EXPECTED_TABLES` += `api_keys`, simulations legacy += `DROP TABLE api_keys` (3 endroits), assertion tables_after += `api_keys` ;
- `backend/tests/unit/test_database.py` : **modifié** — simulation legacy += `DROP TABLE api_keys`.

### Décisions techniques
- **`created_at` default `datetime.now(timezone.utc)`** (pattern `refresh_token.py`) plutôt que `_utcnow_naive` : la story renvoie au « pattern du codebase » ; le pattern effectif du modèle de référence (STORY-123.1) est le default Python aware UTC — suivi du fichier de référence désigné (la variante naive du service concerne les clauses SQL WHERE de purge, hors périmètre modèle) ;
- **Pas de `server_default` sur `revoked`** : la spec 06 mentionne `BOOLEAN DEFAULT FALSE` mais (a) le pattern `1231` n'utilise aucun server_default pour les colonnes votées par défaut client (`revoked_at` etc.), (b) `env.py` ne configure pas `compare_server_default` — un server_default sur la table migrée mais absent du modèle déclencherait un diff `alembic check`. Le default client `default=False` garantit la valeur `False` à l'INSERT (colonne NOT NULL) — cohérent avec le comportement observé dans les tests ;
- **`revoked` booléen + `__repr__` avec `bool(self.revoked)`** : sur une instance non flushée l'attribut vaut `None` avant application du default ; `bool()` rend le `__repr__` robuste (une clé non flushée n'est pas révoquée) sans effet post-flush (colonne NOT NULL) ;
- **Migration écrite à la main** (pattern 1231) conformément à l'avertissement de la Tâche 2 : le wrapper `poetry run alembic` du repo pointe vers un venv racine sans alembic (divergence consignée par STORY-123.1) — chaîne vérifiée programmatiquement par les tests existants (`ScriptDirectory` head unique `1241_api_keys` ← `1231` ← `1213` ← `1211` ← `baseline`, scénario stamp baseline → upgrade head passant).

### Divergences par rapport à l'analyse
- **Tâche 1 (`created_at` default)** : la tâche mentionnait « pattern `_utcnow_naive` du codebase » ; le pattern réel du fichier de référence `refresh_token.py` est `default=lambda: datetime.now(timezone.utc)` — suivi du fichier de référence (sans impact : SQLite stocke de toute façon en naive) ;
- **Tâche 2 (génération `make migrate`)** : non exécutable dans cet environnement (wrapper Poetry sans alembic) — fallback prévu par la story elle-même (écriture manuelle + vérification programmatique), exécuté ;
- **`server_default` `revoked`** : la spec 06 dit `BOOLEAN DEFAULT FALSE` ; implémenté en default client (cf. décisions) pour préserver le garde-fou `alembic check` sans diff — sans impact fonctionnel (NOT NULL + default client).

### Difficultés rencontrées
- Environnement : validations exécutées via `.venv-test` du workspace (pytest/black/isort/flake8/mypy) — le venv Poetry racine n'a pas alembic (divergence déjà consignée par STORY-123.1) ;
- mypy : 5 erreurs préexistantes sur fichiers non touchés (stubs `yaml`/`jose` absents du `.venv-test`, `docker_client_service.py:693`) — aucune sur les fichiers de la story ;
- 1er passage de test : `test_repr_does_not_expose_hash` échouait sur instance non flushée (`revoked=None`) → corrigé par `bool(self.revoked)` dans `__repr__`.

### Non-régression full-suite unitaire (comparaison stash HEAD propre ↔ story)
- **Avec la story** : `1410 passed, 35 failed, 1 error` (2 min 53) ;
- **HEAD propre (stash)** : `35 failed, 1349 passed, 48 errors` (1 min 06) ;
- Les **35 failed sont identiques sur HEAD propre** (fichiers `test_stacks_*` etc., 500 préexistants) — aucun lien avec la story ; les 48 errors du HEAD propre comme l'unique error restant correspondent au teardown non-déterministe `test_ws_auth.py`/TestClient déjà documenté par STORY-123.1 ;
- Lint : black + isort + flake8 **OK** sur les 8 fichiers touchés ; mypy **0 erreur** sur les fichiers de la story.

### Tests ajoutés
- `backend/tests/unit/test_models/test_api_key.py` : 13 tests — défauts (2), bornes name/key_hash (4), CASCADE + isolation (2), sécurité `__repr__`/tablename/garantie « hash uniquement » (3), indépendance `revoked`↔`expires_at` (1), relation `User.api_keys` (1). **Résultat : 13/13 passed.**
- `backend/tests/unit/test_alembic_config.py` : `EXPECTED_TABLES` inclut `api_keys` — égalité stricte métadonnées ↔ migrations vérifiée (8/8 passed) ;
- `backend/tests/integration/test_migrations.py` : table `api_keys` présente après `upgrade head` (base vierge et baseline stampée), downgrade complet fonctionnel (18 passed, 1 skipped PostgreSQL hors ligne — skip documenté) ;
- `backend/tests/unit/test_database.py` : simulations legacy étendues (7/7 passed).
