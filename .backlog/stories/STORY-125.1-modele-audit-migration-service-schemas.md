# STORY-125.1 : Socle audit trail — modèle, migration, config, schemas et service

**Statut :** DONE
**Story Parente :** STORY-125 — [ABANDONED] Audit trail — table `audit_logs`, émission sur actions critiques, `GET /admin/audit`, rétention (P1-4) *(découpée — le fichier mère reste la source d'analyse détaillée)*
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-4 (axe A3, rapport §7) — ampleur **M**

## Description

En tant qu'auditeur sécurité de WindFlow, je veux une table `audit_logs` créée par migration Alembic conforme au schéma spec 06 **augmenté** des colonnes `organization_id` et `correlation_id`, une configuration de rétention (`AUDIT_RETENTION_DAYS`, défaut illimité), des schemas Pydantic de consultation et un service central `AuditService` — écriture **best-effort** (ne levant jamais) masquant systématiquement les secrets dans `details`, consultation filtrée paginée, purge par âge — afin de poser le socle de données de l'audit trail consommé par STORY-125.2 (émission sur les actions critiques) et STORY-125.3 (endpoint admin `GET /admin/audit` + purge périodique lifespan).

Première étape de STORY-125 (découpe proactive `split-story` validée par l'utilisateur le 2026-09-25 ; ampleur M : 10 tâches / ~40 tests répartis) : cette sous-story couvre les tâches 1 à 6 de l'analyse mère plus les tests associés (modèle, migrations, service). **Aucune émission dans les routers** (→ STORY-125.2), **aucun endpoint** (→ STORY-125.3), aucun impact frontend/CLI.

## Critères d'acceptation (AC)

- [x] AC 1 : La table `audit_logs` existe via migration Alembic (STORY-120) conformément au schéma spec 06 **+ colonne correlation_id** ; un service d'audit central (`services/audit_service.py`) expose l'écriture (`action`, acteur, org, cible `resource_type/resource_id`, `details` JSON, `ip_address`, `correlation_id`) sans données sensibles.

> **Note de découpe :** cette sous-story couvre l'AC 1 **en intégralité** (table + migration + service central). Elle porte en outre :
> - la part **structurelle** de l'AC 4 : écriture best-effort ne levant jamais (`AuditService.log()` attrape toute exception → `audit.write_failed` loggé — test `test_log_never_raises_on_db_failure`) ;
> - la garantie structurelle de l'AC 5 : masquage systématique à l'écriture via `_sanitize_details` (test `test_log_sanitizes_sensitive_details`) — la case AC 5 elle-même est portée par STORY-125.2 (démonstration sur parcours réel).
>
> La part rétention de l'AC 4 (application périodique) est portée par STORY-125.3 ; la démonstration en conditions réelles des AC 4/5 (parcours API) est portée par STORY-125.2.

## Contexte technique

> Analyse réalisée par `analyse-story` (2026-09-25), répartie par `split-story` — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches. Source : [`STORY-125-audit-trail-table-emission-retention.md`](STORY-125-audit-trail-table-emission-retention.md).

**Couches impactées :** Backend uniquement — modèle SQLAlchemy, migration Alembic, configuration, schemas Pydantic, service, tests backend (unit + integration). **Aucun endpoint, aucune émission dans les routers, aucun impact frontend/CLI.**

**Spécifications de référence :**
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités auth et audit → `AuditLog` (schéma SQL cible) ;
- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) — § Audit trail (rétention `AUDIT_RETENTION_DAYS`, défaut : conservation indéfinie ; jamais de données sensibles dans `details`) ;
- [`.roo/rules/45-observability.md`](../../.roo/rules/45-observability.md) — correlation ID propagé dans toute la chaîne.

**Fichiers de référence (patterns validés par STORY-123.x/124.x) :**
- Modèle → pattern [`backend/app/models/refresh_token.py`](../../backend/app/models/refresh_token.py) / [`backend/app/models/api_key.py`](../../backend/app/models/api_key.py) : PK `String(36)` UUID, colonnes indexées, docstring de sécurité, `__repr__` sans données sensibles — **sauf FK** : `audit_logs.user_id` est `ondelete="SET NULL"` (spec 06, conservation documentaire), pas `CASCADE` ;
- Migration → pattern [`backend/alembic/versions/2026_09_13_1241_api_keys_table.py`](../../backend/alembic/versions/2026_09_13_1241_api_keys_table.py) : strictement additive, `batch_alter_table` pour les index, commentaires de colonnes — **head actuel : `1241_api_keys`** (`down_revision` de la nouvelle migration) ;
- Service → pattern [`backend/app/services/api_key_service.py`](../../backend/app/services/api_key_service.py) : classe statique async, logs structurés `audit.*` sans valeurs sensibles, `_as_utc`/`_utcnow_naive` (SQLite naive) ; purge → pattern `RefreshTokenService.purge_expired` ([`backend/app/services/refresh_token_service.py:336`](../../backend/app/services/refresh_token_service.py)) : `delete()` SQL bulk + `synchronize_session=False`, log comptages uniquement ;
- Masquage → pattern `_mask_sensitive_values` ([`backend/app/schemas/deployment.py:301`](../../backend/app/schemas/deployment.py)) : valeurs sensibles remplacées par `***` ;
- Schemas → pattern [`backend/app/schemas/api_key.py`](../../backend/app/schemas/api_key.py) : `ConfigDict` + exemples OpenAPI, `from_attributes=True` ;
- Pagination (consommée par 125.3, shape posée ici) → pattern `skip`/`limit` `Query(0, ge=0)` / `Query(100, ge=1, le=100)` + réponse `{items, total, skip, limit}` ([`backend/app/schemas/common.py:49`](../../backend/app/schemas/common.py) `PaginatedResponse`, [`backend/app/schemas/deployment.py:308`](../../backend/app/schemas/deployment.py) `DeploymentListResponse`) ;
- Correlation ID → [`backend/app/middleware/correlation.py`](../../backend/app/middleware/correlation.py) : `request.state.correlation_id` (header `X-Correlation-ID` ou UUID généré) — récupéré par `getattr(request.state, "correlation_id", None)` dans `log_from_request` ;
- IP → `request.client.host if request.client else "unknown"` (pattern [`backend/app/api/v1/auth.py:219`](../../backend/app/api/v1/auth.py)) ; pas de traitement `X-Forwarded-For` dans le codebase à date (à documenter comme limite derrière proxy) ;
- Fixtures disponibles : `db_session`, `test_user`, `test_organization` ([`backend/tests/conftest.py`](../../backend/tests/conftest.py)) — schéma de test issu des migrations, la nouvelle table y sera présente automatiquement.

**Décisions d'analyse (arbitrages pertinents pour ce périmètre) :**

1. **Schéma cible = spec 06 + 3 ajouts** : `audit_logs (id String(36) PK, user_id String(36) FK users.id ON DELETE SET NULL nullable, organization_id String(36) FK organizations.id ON DELETE SET NULL nullable, action String(50) NOT NULL, resource_type String(30) nullable, resource_id Text nullable, details JSON nullable, ip_address String(45) nullable, correlation_id String(64) nullable, created_at DateTime NOT NULL)` + index spec 06 (`user_id`, `action`, `(resource_type, resource_id)`, `created_at`) + index `organization_id` (recherche par org, critère de done) + index `correlation_id` (recherche d'incident par requête — divergence spec 06 assumée, la story introduit la colonne) ;
2. **`SET NULL` et non `CASCADE`** : contrairement aux tables 123/124, la trace d'audit **survit** à la suppression de l'utilisateur (spec 06 : conservation documentaire « qui a fait quoi » même après suppression du compte). Relation `User.audit_logs` **sans cascade ni delete-orphan** : la suppression ORM d'un user nullifie `user_id` des lignes chargées, le `ON DELETE SET NULL` couvre les suppressions SQL directes. Idem pour `organization_id` (FK `SET NULL`, aucune relation ORM côté `Organization` requise) ;
3. **`details` en JSON natif** (`sqlalchemy.JSON`, pattern `Deployment.variables/config`) et non `TEXT` : lecture requêtable sans parsing. **Masquage systématique à l'écriture** : helper `_sanitize_details` dans le service (pattern `_mask_sensitive_values`) qui remplace par `***` les valeurs des clés sensibles (password, token, secret, key, credential, authorization, cookie) sur toute profondeur — garantie structurelle AC 5 ;
4. **Écriture best-effort non bloquante** : `AuditService.log()` n'**ever** lève — toute exception est attrapée → `logger.error("audit.write_failed ...")` avec contexte (action, resource_type, jamais details) + la ligne est perdue (pas de file d'attente dans cette story). L'action métier continue (AC 4). Ne pas réutiliser la session métier si elle est en échec : `log()` ouvre sa propre session via `AsyncSessionLocal` en cas d'exception de commit ;
5. **Signature d'émission** (posée ici, consommée par STORY-125.2) : `AuditService.log(action, *, user_id=None, organization_id=None, resource_type=None, resource_id=None, details=None, request=None)` — quand `request` est fourni, `ip_address` et `correlation_id` sont extraits du middleware ; helper `AuditService.log_from_request(db|request, user, action=..., ...)` côté endpoints pour rester à 1-3 lignes par point d'émission ;
6. **Rétention — configuration** : `audit_retention_days: Optional[int] = Field(None, ge=1)` (**None = illimité, défaut** — spec 15) + `audit_purge_interval_hours: int = Field(24, ge=1)` ; `AuditService.purge_expired(db)` supprime `created_at < now - retention_days` (`RETENTION` None → no-op). La boucle lifespan périodique est portée par STORY-125.3 ;
7. **Pas d'event Redis dédié** : l'audit est une écriture DB directe best-effort ; l'EventBus ([`backend/app/core/events.py`](../../backend/app/core/events.py)) reste inchangé. Un pont event-driven pourra être ajouté en P2 ;
8. **Garde-fous à mettre à jour (partie migrations)** : `EXPECTED_TABLES` (+ `audit_logs`) dans `test_alembic_config.py`, `test_migrations.py`, `test_database.py` (simulations legacy += `DROP TABLE audit_logs`). Le garde-fou routes (`EXPECTED_ROUTE_COUNTS["admin"]` 15 → 16) relève de STORY-125.3.

**Pièges environnement (documentés par 123.x/124.x, toujours valables) :**
- Exécuter les tests avec `DISABLE_AUTH=false LOG_LEVEL=WARNING` et le venv **`.venv-test`** (Python 3.11) — le venv Poetry racine est cassé (alembic défectueux) ;
- `alembic check` sans diff exigé (pas de `server_default` non réflété dans le modèle) ;
- caplog pour « aucun secret dans les logs » : neutraliser `sqlalchemy.engine` en WARNING (paramètres bindés).

## Dépendances

> Statuts vérifiés par l'analyse de la story mère (2026-09-25).

- **STORY-120** (Alembic) — **DONE ✔** (head courant : `1241_api_keys` ← `1231` ← `1213` ← `1211` ← `baseline`) ; la migration `audit_logs` chaînera sur `1241_api_keys` ;
- **STORY-121** (modèle RBAC) / **STORY-122** (`require_role` + `require_super_admin`) / **STORY-123/124** — **DONE ✔** : socle disponible, aucune dépendance bloquante (les ajouts sont purement additifs) ;
- **Sous-stories :** aucune prérequise — **bloque** STORY-125.2 (émission) et STORY-125.3 (endpoint + purge périodique) ;
- **Services externes :** aucun requis — SQLite/PostgreSQL existants ; Redis **non requis** (arbitrage n°7) ;
- **Est un prérequis recommandé de :** STORY-162 (plugins réels, EPIC-013 — audit branché avant l'introduction de la surface d'attaque download/hooks) ;
- **Coordination (non bloquante) :** STORY-126 (enveloppes) et STORY-128 (pagination `?page&per_page`) réaligneront le format de réponse de `/admin/audit` — le socle livre le format courant (`{items,total,skip,limit}`).

## Tâches d'implémentation détaillées

### Tâche 1 : Modèle `AuditLog`
**Objectif :** Créer le modèle SQLAlchemy de la table `audit_logs` conforme au schéma spec 06 **+ colonnes story** (`organization_id`, `correlation_id`), avec FK `SET NULL` (conservation documentaire).
**Fichiers :**
- `backend/app/models/audit_log.py` — Créer — (pattern [`backend/app/models/refresh_token.py`](../../backend/app/models/refresh_token.py), divergences documentées en docstring). Classe `AuditLog(Base)` :
  - `__tablename__ = "audit_logs"` ; docstring de sécurité (journal immuable, jamais de secrets dans `details` — masqués à l'écriture) ;
  - `id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))` ;
  - `user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)` — nullable + `SET NULL` (spécifique audit, ≠ CASCADE de 123/124) ;
  - `organization_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)` ;
  - `action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)` — `user.login`, `stack.deleted`… (catalogue spec 15) ;
  - `resource_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)` ;
  - `resource_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)` (TEXT : IDs conteneurs Docker longs) ;
  - `details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)` — **toujours passé par `_sanitize_details` avant persistance** (garantie portée par le service, docstring du modèle) ;
  - `ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)` — IPv6 max ;
  - `correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)` ;
  - `created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)` ;
  - index composite `__table_args__ = (Index("idx_audit_resource", "resource_type", "resource_id"),)` (nommage spec 06) ;
  - relation `user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs", passive_deletes=True)` — **sans cascade** ;
  - `__repr__` : `<AuditLog(id=..., user_id=..., action=..., resource_type=...)>` — **jamais `details`** ;
- `backend/app/models/user.py` — Modifier — Ajouter la relation `audit_logs` (pattern `refresh_tokens`, **sans** `cascade="all, delete-orphan"`, avec `passive_deletes=True`) ;
- `backend/app/models/__init__.py` — Modifier — Importer `AuditLog` + `__all__` (ordre alphabétique) — indispensable pour `Base.metadata` (schéma de test conftest + `alembic check`).
**Exigences sécurité :** `SET NULL` (trace survit à la suppression du compte) ; `__repr__` sans details ; aucune colonne pour données non masquées (le masquage est structural côté service).
**Dépend de :** Aucune

### Tâche 2 : Migration Alembic additive `1251_audit_logs`
**Objectif :** Créer la table `audit_logs` par migration chaînée sur le head courant.
**Fichiers :**
- `backend/alembic/versions/2026_09_25_1251_audit_logs_table.py` — Créer — (pattern 1241 : docstring STORY-125.1, commentaires de colonnes, `batch_alter_table` pour les index). `revision = "1251_audit_logs"`, `down_revision = "1241_api_keys"`. Génération recommandée `make migrate MIGRATION_MESSAGE="add audit_logs table"` puis revue manuelle — ⚠️ wrapper Poetry racine cassé (piège documenté) : si échec, écrire à la main sur le pattern 1241 et vérifier la chaîne programmatiquement (`ScriptDirectory` head unique `1251` ← `1241` ← `1231` ← `1213` ← `1211` ← `baseline`). Contenu :
  - `upgrade()` : `op.create_table("audit_logs", ...)` avec `sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL")` + `sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL")` + PK ; index `ix_audit_logs_user_id`, `ix_audit_logs_organization_id`, `ix_audit_logs_action`, `ix_audit_logs_correlation_id`, `ix_audit_logs_created_at`, composite `idx_audit_resource (resource_type, resource_id)` via `batch_alter_table` ;
  - `downgrade()` symétrique : drop index puis drop table ;
  - après la tâche : `alembic check` sans diff ; downgrade complet continue de vider la base.
**Exigences sécurité :** Migration strictement additive — aucune donnée existante lue ou modifiée.
**Dépend de :** Tâche 1

### Tâche 3 : Tests du modèle + adaptation tests migrations
**Objectif :** Couvrir le modèle (défauts, FK `SET NULL`, bornes, `__repr__`) et mettre à jour les tests Alembic existants.
**Fichiers :**
- `backend/tests/unit/test_models/test_audit_log.py` — Créer — Fixtures `db_session`, `test_user`, `test_organization`. Détail en section « Tests à écrire ».
- `backend/tests/unit/test_alembic_config.py` — Modifier — `EXPECTED_TABLES` += `audit_logs` ; simulations legacy += `DROP TABLE audit_logs` ;
- `backend/tests/integration/test_migrations.py` — Modifier — idem `EXPECTED_TABLES` + simulations legacy (3 endroits) + assertions after-upgrade ;
- `backend/tests/unit/test_database.py` — Modifier — simulation legacy += `DROP TABLE audit_logs`.
**Exigences sécurité :** Test `SET NULL` (suppression user → ligne conservée avec `user_id=None`) — inversion volontaire du test CASCADE des stories 123/124.
**Dépend de :** Tâche 2

### Tâche 4 : Configuration rétention
**Objectif :** Exposer `AUDIT_RETENTION_DAYS` (défaut illimité) et l'intervalle de purge.
**Fichiers :**
- `backend/app/config.py` — Modifier — À côté du bloc refresh (pattern `refresh_token_purge_interval_hours`, lignes ~51-59) :
  - `audit_retention_days: Optional[int] = Field(default=None, ge=1, description="Audit log retention in days (None = keep forever, spec 15 § Rétention ; e.g. 90 on RPi).")` ;
  - `audit_purge_interval_hours: int = Field(default=24, ge=1, description="Interval (hours) between audit log purge runs (background lifespan job).")` ;
- `env.example` — Modifier — Documenter `AUDIT_RETENTION_DAYS` / `AUDIT_PURGE_INTERVAL_HOURS` (commentés, défaut illimité).
**Exigences sécurité :** Rétention jamais < 1 jour (ge=1) ; aucune donnée sensible en config.
**Dépend de :** Aucune

### Tâche 5 : Schemas Pydantic `audit.py`
**Objectif :** Schemas I/O de consultation — jamais de champ non masqué (le masquage est à l'écriture, la lecture est fidèle).
**Fichiers :**
- `backend/app/schemas/audit.py` — Créer — (pattern [`backend/app/schemas/api_key.py`](../../backend/app/schemas/api_key.py)) :
  - `AuditLogResponse(BaseModel)` : `id: str`, `user_id: Optional[str]`, `organization_id: Optional[str]`, `action: str`, `resource_type: Optional[str]`, `resource_id: Optional[str]`, `details: Optional[dict]`, `ip_address: Optional[str]`, `correlation_id: Optional[str]`, `created_at: datetime` — `model_config = ConfigDict(from_attributes=True)` + exemples OpenAPI (docstring : `details` est masqué à l'écriture par le service) ;
  - `AuditLogListResponse(BaseModel)` : `items: list[AuditLogResponse]`, `total: int (ge=0)`, `skip: int (ge=0)`, `limit: int (ge=1)` (pattern `DeploymentListResponse`) + exemple OpenAPI.
**Exigences sécurité :** Aucun champ « créé par » falsifiable exposé ; pas de endpoint d'écriture (l'audit n'est pas inscriptible par API — écriture interne uniquement).
**Dépend de :** Tâche 1

### Tâche 6 : `AuditService`
**Objectif :** Service central d'écriture (best-effort, masqué), de consultation (filtré paginé — consommé par STORY-125.3) et de purge (consommée par STORY-125.3).
**Fichiers :**
- `backend/app/services/audit_service.py` — Créer — (pattern [`backend/app/services/api_key_service.py`](../../backend/app/services/api_key_service.py) : classe statique async, `_utcnow_naive` pour SQL, logs sans données sensibles) :
  - `_SENSITIVE_KEY_MARKERS = ("password", "token", "secret", "key", "credential", "authorization", "cookie")` ;
  - `_sanitize_details(details: Optional[dict]) -> Optional[dict]` — copie défensive, remplace par `***` la **valeur** de toute clé (inspectée en lowercase) contenant un marqueur, récursif sur dicts/lists (pattern `_mask_sensitive_values` de [`backend/app/schemas/deployment.py`](../../backend/app/schemas/deployment.py)) ; tronque les valeurs > 512 chars (borne anti-abus) ;
  - `log(action, *, user_id=None, organization_id=None, resource_type=None, resource_id=None, details=None, ip_address=None, correlation_id=None, db=None)` — persiste une ligne (details sanitizés) ; **jamais ne lève** : commit dans `try/except`, échec → `logger.error("audit.write_failed action=%s resource_type=%s error=%s", ...)` (jamais `details` dans le log) ; `db` optionnel → si absent, session courte via `AsyncSessionLocal()` ;
  - `log_from_request(request, action, *, user=None, ...)` — helper endpoints : extrait `ip_address` (`request.client.host if request.client else "unknown"`) et `correlation_id` (`getattr(request.state, "correlation_id", None)`) + `user_id`/`organization_id` de l'utilisateur courant, délègue à `log()` ;
  - `list_entries(db, *, user_id=None, action=None, resource_type=None, since=None, skip=0, limit=100) -> tuple[list[AuditLog], int]` — `select` + `count` (filtres equality + `created_at >= since`), ordre `created_at desc`, `offset/limit` — valeurs bornées côté API (STORY-125.3) ;
  - `purge_expired(db) -> int` — `RETENTION None` → `return 0` ; sinon `delete(AuditLog).where(created_at < now - retention_days)` + `synchronize_session=False` + log comptage (pattern [`refresh_token_service.py:336`](../../backend/app/services/refresh_token_service.py)) ;
- `backend/app/core/exceptions.py` — **inchangé** (aucune exception métier : l'audit n'échoue jamais côté appelant).
**Exigences sécurité :** Masquage systématique avant persistance (AC 5) ; best-effort structurel (AC 4) ; logs service = action/ids/comptages uniquement ; consultation scopée super_admin côté endpoint (le service ne filtre pas par rôle — la garde est HTTP, posée en 125.3).
**Dépend de :** Tâches 1, 4, 5

### Tâche 7 : Tests du service
**Objectif :** Couvrir la mécanique du service — persistance, masquage, best-effort, extraction du contexte requête, liste filtrée paginée, purge (part tâche 10 de la story mère).
**Fichiers :**
- `backend/tests/unit/test_services/test_audit_service.py` — Créer — Fixtures `db_session`, `test_user`, `test_organization` ; `request` factice pour `log_from_request`. Détail en section « Tests à écrire ».
**Exigences sécurité :** Assertions « aucune exception propagée sur échec DB », « jamais le contenu de `details` dans les logs » (caplog), « valeurs sensibles → `***` ».
**Dépend de :** Tâche 6

## Tests à écrire

### Backend — unitaires (modèle)
- `backend/tests/unit/test_models/test_audit_log.py`
  - `test_create_audit_log_defaults` — id UUID, `created_at` défini, colonnes nullable OK
  - `test_action_max_length` — `String(50)` respectée
  - `test_user_deletion_sets_null_not_cascade` — suppression du user → ligne **conservée** avec `user_id=None` (SET NULL — inverse volontaire du test CASCADE 123/124)
  - `test_organization_deletion_sets_null` — idem côté org
  - `test_repr_does_not_expose_details` — `__repr__` sans `details` ni `ip_address`

### Backend — intégration (migrations)
- `test_migrations.py` : table `audit_logs` présente après `upgrade head` (base vierge **et** baseline stampée) ; downgrade → absente ; index composites présents
- `test_alembic_config.py` / `test_database.py` : `EXPECTED_TABLES` += `audit_logs`, simulations legacy `DROP TABLE audit_logs`

### Backend — unitaires (service)
- `backend/tests/unit/test_services/test_audit_service.py`
  - `test_log_persists_full_line` — acteur, org, action, cible, ip, correlation_id, details persistés
  - `test_log_sanitizes_sensitive_details` — `{password, token, secret, api_key, authorization}` → valeurs `***` (paramétré), clés non sensibles intactes ; récursion (nested dict/list)
  - `test_log_truncates_long_values` — valeur > 512 chars tronquée
  - `test_log_never_raises_on_db_failure` — session en échec (mock `commit` levant) → aucune exception propagée, `audit.write_failed` loggé
  - `test_log_opens_own_session_when_db_none` — appel sans `db` → session courte (mock `AsyncSessionLocal`)
  - `test_log_from_request_extracts_context` — `ip_address` + `correlation_id` extraits de `request` factice (`state.correlation_id`, `client.host`)
  - `test_list_entries_filters_and_pagination` — filtres `user_id`/`action`/`resource_type`/`since` combinés ; ordre `created_at desc` ; `skip/limit` respectés ; `total` exact
  - `test_purge_expired_noop_when_retention_none` — `audit_retention_days=None` → 0 suppression, aucune requête delete
  - `test_purge_expired_removes_only_old_entries` — lignes au-delà du seuil purgées, récentes conservées (mock temps ou lignes datées)
  - `test_no_details_in_logs` — caplog : jamais le contenu de `details` dans les logs du service

### Commandes de validation
```bash
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/test_models/test_audit_log.py backend/tests/unit/test_services/test_audit_service.py -v
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/test_alembic_config.py backend/tests/unit/test_database.py backend/tests/integration/test_migrations.py -v
# Non-régression large
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/ -q --no-cov -p no:randomly
make backend-lint && make backend-typecheck
```
*(⚠️ venv Poetry racine cassé — utiliser `.venv-test` comme documenté par 124.4 ; ajuster les chemins relatifs selon cwd.)*

## État d'avancement technique

*(coché par `treat-story` pendant l'implémentation)*

- [x] Tâche 1 : Modèle `AuditLog` + relations + exports (`SET NULL`, index spec 06 + story)
- [x] Tâche 2 : Migration Alembic `1251_audit_logs` (additive, head `1241` → `1251`)
- [x] Tâche 3 : Tests modèle + adaptation tests migrations (`EXPECTED_TABLES` += `audit_logs`, simulations legacy `DROP TABLE`)
- [x] Tâche 4 : Config — `audit_retention_days` (défaut illimité) + `audit_purge_interval_hours` + `env.example`
- [x] Tâche 5 : Schemas Pydantic `audit.py` (`AuditLogResponse` + `AuditLogListResponse` paginée)
- [x] Tâche 6 : `AuditService` — `log()` best-effort, `log_from_request()`, `_sanitize_details`, `list_entries()` filtré paginé, `purge_expired()`
- [x] Tâche 7 : Tests unitaires du service (sanitize/best-effort/liste/purge/logs)

## Notes d'implémentation

> Clôture (2026-09-26) — session reprise après interruption : l'audit d'état a constaté les 7 tâches réalisées ; cette session a vérifié la conformité, exécuté la validation complète et clôturé le backlog.

### Fichiers créés

- `backend/app/models/audit_log.py` — modèle `AuditLog` : FK `SET NULL` (user/organization — conservation documentaire spec 06), `correlation_id` String(64) indexé, `details` JSON natif, `resource_id` Text (IDs Docker longs), `created_at` indexé, index composite `idx_audit_resource`, relation `user` sans cascade (`passive_deletes=True`), `__repr__` sans `details`/`ip_address` ;
- `backend/alembic/versions/2026_09_25_1251_audit_logs_table.py` — migration strictement additive (`down_revision="1241_api_keys"`, head 1241 → 1251) : FK `SET NULL`, 6 index via `batch_alter_table`, downgrade symétrique ;
- `backend/app/schemas/audit.py` — `AuditLogResponse` (from_attributes + exemples OpenAPI) et `AuditLogListResponse` `{items,total,skip,limit}` bornées ; lecture seule (aucun schema d'écriture — l'audit n'est pas inscriptible par API) ;
- `backend/app/services/audit_service.py` — `AuditService` : `_sanitize_details` (7 marqueurs password/token/secret/key/credential/authorization/cookie → `***`, récursif dicts/lists, troncature 512, copie défensive), `log()` best-effort ne levant jamais (`audit.write_failed` loggé sans `details`, rollback best-effort, session courte `AsyncSessionLocal` si `db` absent), `log_from_request()` (extraction `ip_address`/`correlation_id` du contexte requête), `list_entries()` (filtres + `created_at desc` + pagination + total), `purge_expired()` (no-op si rétention None, delete bulk `synchronize_session=False`) ;
- `backend/tests/unit/test_models/test_audit_log.py` — 12 tests : défauts, bornes colonnes, **FK SET NULL** (suppression ORM et SQL direct → ligne conservée `user_id=None` — inverse volontaire du CASCADE 123/124), `__repr__` sans données sensibles, relation sans cascade ;
- `backend/tests/unit/test_services/test_audit_service.py` — 27 tests : persistance complète/minimale, masquage paramétré (9 cas dont casse), récursion, troncature, non-mutation de l'entrée, best-effort (échec commit session fournie + session courte), extraction contexte requête (avec/sans client), filtres/pagination/ordre/total, purge (no-op None, seuil par âge), **aucun `details` dans les logs** (caplog) ;
- `backend/tests/unit/test_schemas/test_audit_schemas.py` — 7 tests : lecture ORM, fidélité `details`, champs requis, bornes liste rejetées, exemples OpenAPI valides.

### Fichiers modifiés

- `backend/app/models/user.py` — relation `audit_logs` sans cascade (`passive_deletes=True`) ;
- `backend/app/models/__init__.py` — export `AuditLog` (ordre alphabétique) ;
- `backend/app/config.py` — `audit_retention_days: Optional[int] = Field(None, ge=1)` (None = illimité, spec 15) + `audit_purge_interval_hours: int = Field(24, ge=1)` ;
- `env.example` — documentation `AUDIT_RETENTION_DAYS` / `AUDIT_PURGE_INTERVAL_HOURS` (commentés, défaut illimité) ;
- `backend/tests/unit/test_alembic_config.py`, `backend/tests/integration/test_migrations.py`, `backend/tests/unit/test_database.py` — garde-fous : `EXPECTED_TABLES` += `audit_logs`, simulations legacy += `DROP TABLE audit_logs`, classe dédiée `TestAuditLogsTableMigration` (structure, FK `ondelete=SET NULL`, index, downgrade ciblé 1251 → 1241) ;
- `.backlog/kanban.md`, `.backlog/epics/EPIC-012-remediation-p1-socle-structurant.md`, `CHANGELOG.md` — clôture backlog.

### Validation exécutée (venv `.venv-test`, pièges 124.4 appliqués)

- Tests ciblés : 46/46 verts (modèle 12 + service 27 + schemas 7) ;
- Tests migrations/garde-fous : 38 passés, 1 skipped (préexistant) ;
- Couverture fichiers du périmètre : `audit_log.py` **100%**, `audit.py` **100%**, `audit_service.py` **99%** (ligne 66 : branche naive de `_to_naive_utc`, triviale) — seuil 80% respecté ;
- Non-régression : `tests/unit/` **1528/1528 verts** (58 s) ;
- black/isort/flake8 : clean sur les 10 fichiers du périmètre ; bandit : aucun signalement ; mypy : aucune erreur sur les fichiers du périmètre (5 erreurs préexistantes tierces yaml/jose/docker_client_service, hors périmètre).

### Décisions techniques

- Conformité intégrale à l'analyse de la story mère (10 arbitrages) — aucune divergence ;
- `purge_expired()` exposé mais **non appelé** (boucle lifespan = STORY-125.3) ; `log_from_request()` prêt pour l'émission (STORY-125.2) ;
- `audit.write_failed` loggé avec action/resource_type/erreur uniquement — jamais `details` ni `ip_address`.

### Difficultés rencontrées

- Session d'implémentation initiale interrompue : reprise par audit d'état (constat : 7/7 tâches déjà réalisées) puis validation complète ci-dessus — aucun complément de code nécessaire.
