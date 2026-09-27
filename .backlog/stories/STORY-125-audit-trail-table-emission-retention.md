# STORY-125 : [ABANDONED] Audit trail — table `audit_logs`, émission sur actions critiques, `GET /admin/audit`, rétention (P1-4)

**Statut :** ABANDONED *(découpe proactive `split-story` — remplacée par STORY-125.1/125.2/125.3, voir « Sous-stories »)*
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-4 (axe A3, rapport §7) — ampleur **M**

## Description

En tant qu'auditeur sécurité de WindFlow, je veux que toute action critique (déploiements, suppressions, modifications de configuration, événements d'authentification, changements de rôles) soit tracée dans une table `audit_logs` avec l'acteur, l'action, la cible, l'IP et le correlation_id, consultable via `GET /admin/audit` paginé et filtrable, afin de répondre à « qui a fait quoi, quand » en cas d'incident.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §7, §14) : aucune table `audit_logs`, aucun service d'audit ; seuls des logs applicatifs existent (non requêtables). La spec 15 exige : « toutes les actions modifiantes sont loggées avec l'utilisateur, l'IP et l'horodatage » — le plan en fait la base du futur endpoint `GET /admin/audit`.

## Contexte technique

> Analyse réalisée par `analyse-story` (2026-09-25) — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches.

**Couches impactées :** Backend uniquement — modèle + migration Alembic + config + schemas + service + 1 endpoint admin (`/admin/audit`) + boucle de purge lifespan + **émission ponctuelle dans les routers existants** (auth, stacks, targets, organizations, deployments, docker, plugins). Aucun impact frontend/CLI (la consultation UI/CLI viendra après les enveloppes STORY-126/128).

**Fichiers de référence (patterns validés par STORY-123.x/124.x) :**
- Modèle → pattern [`backend/app/models/refresh_token.py`](../../backend/app/models/refresh_token.py) / [`backend/app/models/api_key.py`](../../backend/app/models/api_key.py) : PK `String(36)` UUID, colonnes indexées, docstring de sécurité, `__repr__` sans données sensibles — **sauf FK** : `audit_logs.user_id` est `ondelete="SET NULL"` (spec 06, conservation documentaire), pas `CASCADE` ;
- Migration → pattern [`backend/alembic/versions/2026_09_13_1241_api_keys_table.py`](../../backend/alembic/versions/2026_09_13_1241_api_keys_table.py) : strictement additive, `batch_alter_table` pour les index, commentaires de colonnes — **head actuel : `1241_api_keys`** (`down_revision` de la nouvelle migration) ;
- Service → pattern [`backend/app/services/api_key_service.py`](../../backend/app/services/api_key_service.py) : classe statique async, logs structurés `audit.*` sans valeurs sensibles, `_as_utc`/`_utcnow_naive` (SQLite naive) ; purge → pattern `RefreshTokenService.purge_expired` ([`backend/app/services/refresh_token_service.py:336`](../../backend/app/services/refresh_token_service.py)) : `delete()` SQL bulk + `synchronize_session=False`, log comptages uniquement ;
- Job de purge → pattern lifespan [`backend/app/main.py:158`](../../backend/app/main.py) (STORY-123.4) : boucle asyncio `while True` + `AsyncSessionLocal` + `asyncio.create_task` + cancellation au shutdown — à dupliquer pour l'audit (ne pas fusionner les deux boucles : intervalles et logs distincts) ;
- Endpoint admin → pattern [`backend/app/api/v1/admin/stacks_management.py`](../../backend/app/api/v1/admin/stacks_management.py) : `require_super_admin` ([`backend/app/auth/rbac.py`](../../backend/app/auth/rbac.py)), docstrings OpenAPI riches ; montage dans [`backend/app/api/v1/admin/__init__.py`](../../backend/app/api/v1/admin/__init__.py) (`admin_router` préfixe `/admin`) ;
- Pagination → pattern `skip`/`limit` `Query(0, ge=0)` / `Query(100, ge=1, le=100)` + réponse `{items, total, skip, limit}` ([`backend/app/schemas/common.py:49`](../../backend/app/schemas/common.py) `PaginatedResponse`, [`backend/app/schemas/deployment.py:308`](../../backend/app/schemas/deployment.py) `DeploymentListResponse`) ;
- Correlation ID → [`backend/app/middleware/correlation.py`](../../backend/app/middleware/correlation.py) : `request.state.correlation_id` (header `X-Correlation-ID` ou UUID généré) — récupéré par `getattr(request.state, "correlation_id", None)` au point d'émission ;
- IP → `request.client.host if request.client else "unknown"` (pattern [`backend/app/api/v1/auth.py:219`](../../backend/app/api/v1/auth.py)) ; pas de traitement `X-Forwarded-For` dans le codebase à date (à documenter comme limite derrière proxy) ;
- Masquage → pattern `_mask_sensitive_values` ([`backend/app/schemas/deployment.py:301`](../../backend/app/schemas/deployment.py)) : valeurs sensibles remplacées par `***` ;
- Schemas → pattern [`backend/app/schemas/api_key.py`](../../backend/app/schemas/api_key.py) : `ConfigDict` + exemples OpenAPI, `from_attributes=True` ;
- Tests API → pattern [`backend/tests/unit/test_api/test_api_keys.py`](../../backend/tests/unit/test_api/test_api_keys.py) : fixture `_jwt_mode` (monkeypatch `disable_auth=False`), fixtures rôles conftest (`viewer_user`, `operator_user`, `org_admin_user`, `test_superuser`), mint direct JWT ;
- Fixtures disponibles : `db_session`, `test_user`, `test_organization` ([`backend/tests/conftest.py`](../../backend/tests/conftest.py)) — schéma de test issu des migrations, la nouvelle table y sera présente automatiquement.

**Décisions d'analyse (arbitrages) :**

1. **Schéma cible = spec 06 + 3 ajouts** : `audit_logs (id String(36) PK, user_id String(36) FK users.id ON DELETE SET NULL nullable, organization_id String(36) FK organizations.id ON DELETE SET NULL nullable, action String(50) NOT NULL, resource_type String(30) nullable, resource_id Text nullable, details JSON nullable, ip_address String(45) nullable, correlation_id String(64) nullable, created_at DateTime NOT NULL)` + index spec 06 (`user_id`, `action`, `(resource_type, resource_id)`, `created_at`) + index `organization_id` (recherche par org, critère de done) + index `correlation_id` (recherche d'incident par requête — divergence spec 06 assumée, la story introduit la colonne) ;
2. **`SET NULL` et non `CASCADE`** : contrairement aux tables 123/124, la trace d'audit **survit** à la suppression de l'utilisateur (spec 06 : conservation documentaire « qui a fait quoi » même après suppression du compte). Relation `User.audit_logs` **sans cascade ni delete-orphan** : la suppression ORM d'un user nullifie `user_id` des lignes chargées, le `ON DELETE SET NULL` couvre les suppressions SQL directes. Idem pour `organization_id` (FK `SET NULL`, aucune relation ORM côté `Organization` requise) ;
3. **`details` en JSON natif** (`sqlalchemy.JSON`, pattern `Deployment.variables/config`) et non `TEXT` : lecture requêtable sans parsing. **Masquage systématique à l'écriture** : helper `_sanitize_details` dans le service (pattern `_mask_sensitive_values`) qui remplace par `***` les valeurs des clés sensibles (password, token, secret, key, credential, authorization…) sur toute profondeur — garantie structurelle AC 5 ;
4. **Écriture best-effort non bloquante** : `AuditService.log()` n'**ever** lève — toute exception est attrapée → `logger.error("audit.write_failed ...")` avec contexte (action, resource_type, jamais details) + la ligne est perdue (pas de file d'attente dans cette story). L'action métier continue (AC 4). Ne pas réutiliser la session métier si elle est en échec : `log()` ouvre sa propre session via `AsyncSessionLocal` en cas d'exception de commit ;
5. **Signature d'émission** : `AuditService.log(action, *, user_id=None, organization_id=None, resource_type=None, resource_id=None, details=None, request=None)` — quand `request` est fourni, `ip_address` et `correlation_id` sont extraits du middleware ; helper `AuditService.log_from_request(db|request, user, action=..., ...)` côté endpoints pour rester à 1-3 lignes par point d'émission ;
6. **Catalogue d'émission borné** (AC 2, ampleur M — chaque point = un appel service) :
   - **Auth** ([`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py)) : `user.login` (réussi), `user.login_failed` (échec credentials — `user_id=None` si user inconnu ; `username` autorisé dans `details` : identifiant public déjà loggé par le `user.login_failed` existant ; **jamais** le password ni aucun secret), `user.logout`, `api_key.created`, `api_key.revoked` ;
   - **Suppressions** : `stack.deleted` ([`backend/app/api/v1/stacks.py`](../../backend/app/api/v1/stacks.py) DELETE `/{stack_id}` — **test de référence**), `target.deleted` ([`backend/app/api/v1/targets/crud.py`](../../backend/app/api/v1/targets/crud.py) DELETE), `organization.deleted` ([`backend/app/api/v1/organizations.py`](../../backend/app/api/v1/organizations.py) DELETE), `container.deleted` ([`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py) DELETE `/{container_id}`) ;
   - **Rôles** (organizations.py) : `user.role_changed` (PUT `/{org}/users/{user_id}` — `details: {previous_role, new_role}`, données déjà loggées), `member.added` / `member.removed` (POST/DELETE members) ;
   - **Déploiements** : `deployment.created` (POST [`deployments.py`](../../backend/app/api/v1/deployments.py), acteur = `current_user`), `deployment.succeeded`/`deployment.failed` émis sur transition terminale dans `DeploymentService.update_status` avec `user_id=None` (**acteur système** — le modèle `Deployment` n'a pas de colonne acteur, vérifié ; l'initiateur reste traçable via la ligne `deployment.created`), `stack.rollback` (POST `/{stack_id}/versions/{version_id}/restore`) ;
   - **Conteneurs/plugins** : `container.started`/`container.stopped` (docker.py start/stop), `plugin.installed`/`plugin.removed` ([`plugins.py`](../../backend/app/api/v1/plugins.py) install/uninstall) ;
   - Hors périmètre (reporté, à documenter) : `settings.changed` et `machine.*` (aucun endpoint settings/machine à ce jour), émissions WebSocket (le plugin `audit_logger` WS existant est un mécanisme distinct — ne pas casser) ;
7. **Rétention** : `audit_retention_days: Optional[int] = Field(None, ge=1)` (**None = illimité, défaut** — spec 15) + `audit_purge_interval_hours: int = Field(24, ge=1)` ; `AuditService.purge_expired(db)` supprime `created_at < now - retention_days` (`RETENTION` None → no-op) ; boucle lifespan dédiée (pattern 123.4) ;
8. **Endpoint consultation** : `GET /api/v1/admin/audit` — **`require_super_admin`** (l'endpoint vit sous `/admin/` ; matrice spec 08 : administration système = Super Admin) ; filtres `user_id` (str), `action` (str ≤ 50), `resource_type` (str ≤ 30), `since` (datetime ISO) ; pagination `skip`/`limit` Query bornés (max 100) ; réponse `AuditLogListResponse {items, total, skip, limit}` (pattern `DeploymentListResponse`) — **pas** d'enveloppe `{data,pagination}` (STORY-126 non mergée ; réalignement prévu par elle, cf. Contexte existant) ;
9. **Pas d'event Redis dédié** : l'audit est une écriture DB directe best-effort ; l'EventBus ([`backend/app/core/events.py`](../../backend/app/core/events.py)) reste inchangé (son `publish` est in-memory et non requis par les AC). Un pont event-driven pourra être ajouté en P2 ;
10. **Garde-fous à mettre à jour** : `EXPECTED_TABLES` (+ `audit_logs`) dans `test_alembic_config.py`, `test_migrations.py`, `test_database.py` (simulations legacy += `DROP TABLE audit_logs`) ; `EXPECTED_ROUTE_COUNTS["admin"]` 15 → 16 dans [`test_rbac_exhaustivite.py`](../../backend/tests/unit/test_api/test_rbac_exhaustivite.py).

**Pièges environnement (documentés par 123.x/124.x, toujours valables) :**
- Exécuter les tests avec `DISABLE_AUTH=false LOG_LEVEL=WARNING` et le venv **`.venv-test`** (Python 3.11) — le venv Poetry racine est cassé (alembic défectueux) ;
- `alembic check` sans diff exigé (pas de `server_default` non réflété dans le modèle) ;
- caplog pour « aucun secret dans les logs » : neutraliser `sqlalchemy.engine` en WARNING (paramètres bindés).

Éléments existants à réutiliser / contraintes :
- Schéma cible spec 06 : `audit_logs (id, user_id FK SET NULL, action VARCHAR(50), resource_type VARCHAR(30), resource_id TEXT, details TEXT JSON, ip_address VARCHAR(45), created_at)` + index `user_id`, `action`, `(resource_type, resource_id)`, `created_at` — la story ajoute le **correlation_id** (critère de done P1-4 : ligne avec « user, org, action, cible, correlation_id ») ;
- Catalogue d'actions spec 15 § Audit trail : `user.login`/`user.login_failed`, `user.created`/`user.role_changed`, `stack.deployed`/`stack.rollback`, `container.started`/`container.stopped`, `plugin.installed`/`plugin.removed`, `host.added`/`host.removed`, `settings.changed` — à émettre **en plus** sur : suppressions génériques (DELETE stacks/targets/organizations), modifications de config, auth events (login réussi/échoué, logout, création/révocation de clés API — STORY-124) ;
- Correlation ID existant : middleware [`correlation_middleware`](../../backend/app/middleware) (header `X-Correlation-ID`, présent dans les logs — rules 45) → à propager dans les lignes d'audit ;
- Consultation : `GET /api/v1/admin/audit` (spec 09 § Administration — filtres `user`, `action`, `date`/`since`) — **Super Admin** (matrice spec 08 : Audit consultation = Admin+, administration système = Super Admin ; l'endpoint est sous `/admin/` → `super_admin`) ; réponse **paginée** (format d'enveloppe de STORY-126/128 si fusionnées, sinon pagination simple réalignée ensuite) ;
- Rétention configurable (`AUDIT_RETENTION_DAYS`, défaut : conservation indéfinie ; ex. 90 jours sur RPi) — purge périodique asyncio (cf. cleanup existant), jamais de données sensibles dans `details` (masquer secrets) ;
- Écriture asynchrone non bloquante : l'échec d'écriture d'audit ne doit pas faire échouer l'action métier (log ERROR + métrique) ;
- « Acteur rôle » : dépend de STORY-121 (rôle dans l'org de l'acteur) ; le plugin `audit_logger` WS existant n'est **pas** ce mécanisme (audit applicatif temps réel) — ne pas confondre, ne pas casser.

## Critères d'acceptation (AC)

- [ ] AC 1 : La table `audit_logs` existe via migration Alembic (STORY-120) conformément au schéma spec 06 **+ colonne correlation_id** ; un service d'audit central (`services/audit_service.py`) expose l'écriture (`action`, acteur, org, cible `resource_type/resource_id`, `details` JSON, `ip_address`, `correlation_id`) sans données sensibles.
- [ ] AC 2 : Les **actions critiques** émettent une ligne d'audit : déploiements (création/succès/échec/rollback), suppressions (stacks, targets, organizations, conteneurs), modifications de configuration (settings, config stacks/plugins), événements d'authentification (login réussi/échoué, logout, clés API créées/révoquées), changements de rôles — test de référence : `DELETE` d'une stack → ligne avec **user, org, action, cible, correlation_id** (celui du middleware).
- [ ] AC 3 : `GET /api/v1/admin/audit` répond **paginé** avec filtres (`user_id`, `action`, `since`) ; protégé `super_admin` (STORY-122) : `401` sans token, `403` pour viewer/operator/admin d'org.
- [ ] AC 4 : **Rétention configurable** appliquée : `AUDIT_RETENTION_DAYS` (défaut illimité) purge les entrées au-delà du seuil — test avec valeur courte ; l'écriture d'audit en échec n'interrompt pas l'action métier (test avec injection d'échec).
- [ ] AC 5 : Tests de sécurité : aucune donnée sensible (mot de passe, token, secret) dans `details` des lignes auditées ; `make lint` + `make backend-test` verts.

## Références spécification

- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) — § Audit trail (catalogue d'actions loggées, consultation CLI/API, rétention `AUDIT_RETENTION_DAYS`) ;
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités auth et audit → `AuditLog` (schéma SQL) ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Administration → `GET /admin/audit` (filtres user/action/date) ;
- `.roo/rules/45-observability.md` — correlation ID propagé dans toute la chaîne (inclus dans les lignes d'audit) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §7 (aucun audit trail), §14 ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-4, §2.A A3, §7.3 (audit branché avant plugins réels P2 — STORY-162 idéalement après cette story).

## Dépendances

> Analyse réalisée par `analyse-story` (2026-09-25) — statuts vérifiés dans `.backlog/` et le code.

- **STORY-120** (Alembic) — **DONE ✔** (head courant : `1241_api_keys` ← `1231` ← `1213` ← `1211` ← `baseline`) ; la migration `audit_logs` chaînera sur `1241_api_keys` ;
- **STORY-121** (modèle RBAC `user_organizations.role`) — **DONE ✔** : l'acteur et son rôle org sont résolus à l'émission via `current_user` + `AuthorizationService.get_role_in_organization` quand l'endpoint est org-scopé (stacks/targets) ; pour les endpoints globaux (docker, admin), `organization_id` reste NULL ;
- **STORY-122** (`require_role` + hiérarchie + alias `require_super_admin`) — **DONE ✔** : la protection du endpoint de consultation est déjà disponible — aucune dépendance bloquante ;
- **STORY-123/124** — **DONE ✔** : les événements `api_key.created/revoked` et les events auth s'appuient sur le socle posé (aucune régression attendue — les ajouts sont purement additifs) ;
- **Services externes :** aucun requis — SQLite/PostgreSQL existants ; Redis **non requis** (pas d'event bus dédié, arbitrage n°9) ;
- **Est un prérequis recommandé de :** STORY-162 (plugins réels, EPIC-013 — audit branché avant l'introduction de la surface d'attaque download/hooks) ;
- **Coordination (non bloquante) :** STORY-126 (enveloppes) et STORY-128 (pagination `?page&per_page`) réaligneront le format de réponse de `/admin/audit` — cette story livre le format courant (`{items,total,skip,limit}`), les AC ne présument pas de l'enveloppe.

## Sous-stories

> **Découpe proactive `split-story` (mode proactif, validée par l'utilisateur le 2026-09-25)** — cette story est **ABANDONNÉE** et remplacée par 3 sous-stories autonomes qui couvrent l'intégralité de son périmètre (analyse, AC et tests ci-dessous répartis sans perte) :
>
> - [ ] STORY-125.1 : Socle audit trail — modèle, migration, config, schemas et service ([`STORY-125.1-modele-audit-migration-service-schemas.md`](STORY-125.1-modele-audit-migration-service-schemas.md)) — tâches 1-6 + tests modèle/migrations/service ;
> - [ ] STORY-125.2 : Émission d'audit sur les actions critiques ([`STORY-125.2-emission-audit-actions-critiques.md`](STORY-125.2-emission-audit-actions-critiques.md)) — tâche 8 + tests d'émission (test de référence DELETE stack) ;
> - [ ] STORY-125.3 : Endpoint admin `GET /admin/audit`, purge lifespan et rétention ([`STORY-125.3-endpoint-admin-purge-retention.md`](STORY-125.3-endpoint-admin-purge-retention.md)) — tâches 7 et 9 + tests endpoint/rétention.
>
> **Ce fichier est conservé pour historique et comme source d'analyse détaillée** (sections `## Contexte technique`, `## Dépendances`, `## Tâches d'implémentation détaillées`, `## Tests à écrire` remplies par `analyse-story` le 2026-09-25) — les sous-stories en sont des extractions adaptées ; en cas d'ambiguïté, le découpage des sous-stories prévaut. Conformément à la règle d'or, aucun fichier de backlog n'est supprimé.

## État d'avancement technique

*(coché par `treat-story` pendant l'implémentation)*

- [ ] Tâche 1 : Modèle `AuditLog` + relations + exports (`SET NULL`, index spec 06 + story)
- [ ] Tâche 2 : Migration Alembic `1251_audit_logs` (additive, head `1241` → `1251`)
- [ ] Tâche 3 : Tests modèle + adaptation tests migrations (`EXPECTED_TABLES` += `audit_logs`, simulations legacy `DROP TABLE`)
- [ ] Tâche 4 : Config — `audit_retention_days` (défaut illimité) + `audit_purge_interval_hours` + `env.example`
- [ ] Tâche 5 : Schemas Pydantic `audit.py` (`AuditLogResponse` + `AuditLogListResponse` paginée)
- [ ] Tâche 6 : `AuditService` — `log()` best-effort, `log_from_request()`, `_sanitize_details`, `list_entries()` filtré paginé, `purge_expired()`
- [ ] Tâche 7 : Endpoint `GET /api/v1/admin/audit` (super_admin, filtres, pagination) + garde-fou routes admin 15 → 16
- [ ] Tâche 8 : Émission sur actions critiques — auth (login/logout/api-keys), suppressions (stack **[test de référence]**, target, organization, container), rôles, déploiements, conteneurs/plugins
- [ ] Tâche 9 : Boucle de purge lifespan (rétention configurable, no-op par défaut)
- [ ] Tâche 10 : Tests — service (sanitize/best-effort/purge/liste), endpoint (401/403/422/pagination/filtres), émission de référence (DELETE stack), rétention, non-exposition de secrets + validation globale (`make backend-lint`, `make backend-typecheck`, non-régression)

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
- `backend/alembic/versions/2026_09_25_1251_audit_logs_table.py` — Créer — (pattern 1241 : docstring STORY-125, commentaires de colonnes, `batch_alter_table` pour les index). `revision = "1251_audit_logs"`, `down_revision = "1241_api_keys"`. Génération recommandée `make migrate MIGRATION_MESSAGE="add audit_logs table"` puis revue manuelle — ⚠️ wrapper Poetry racine cassé (piège documenté) : si échec, écrire à la main sur le pattern 1241 et vérifier la chaîne programmatiquement (`ScriptDirectory` head unique `1251` ← `1241` ← `1231` ← `1213` ← `1211` ← `baseline`). Contenu :
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
**Objectif :** Service central d'écriture (best-effort, masqué), de consultation (filtré paginé) et de purge.
**Fichiers :**
- `backend/app/services/audit_service.py` — Créer — (pattern [`backend/app/services/api_key_service.py`](../../backend/app/services/api_key_service.py) : classe statique async, `_utcnow_naive` pour SQL, logs sans données sensibles) :
  - `_SENSITIVE_KEY_MARKERS = ("password", "token", "secret", "key", "credential", "authorization", "cookie")` ;
  - `_sanitize_details(details: Optional[dict]) -> Optional[dict]` — copie défensive, remplace par `***` la **valeur** de toute clé (inspectée en lowercase) contenant un marqueur, récursif sur dicts/lists (pattern `_mask_sensitive_values` de [`backend/app/schemas/deployment.py`](../../backend/app/schemas/deployment.py)) ; tronque les valeurs > 512 chars (borne anti-abus) ;
  - `log(action, *, user_id=None, organization_id=None, resource_type=None, resource_id=None, details=None, ip_address=None, correlation_id=None, db=None)` — persiste une ligne (details sanitizés) ; **jamais ne lève** : commit dans `try/except`, échec → `logger.error("audit.write_failed action=%s resource_type=%s error=%s", ...)` (jamais `details` dans le log) ; `db` optionnel → si absent, session courte via `AsyncSessionLocal()` ;
  - `log_from_request(request, action, *, user=None, ...)` — helper endpoints : extrait `ip_address` (`request.client.host if request.client else "unknown"`) et `correlation_id` (`getattr(request.state, "correlation_id", None)`) + `user_id`/`organization_id` de l'utilisateur courant, délègue à `log()` ;
  - `list_entries(db, *, user_id=None, action=None, resource_type=None, since=None, skip=0, limit=100) -> tuple[list[AuditLog], int]` — `select` + `count` (filtres equality + `created_at >= since`), ordre `created_at desc`, `offset/limit` — valeurs bornées côté API ;
  - `purge_expired(db) -> int` — `RETENTION None` → `return 0` ; sinon `delete(AuditLog).where(created_at < now - retention_days)` + `synchronize_session=False` + log comptage (pattern [`refresh_token_service.py:336`](../../backend/app/services/refresh_token_service.py)) ;
- `backend/app/core/exceptions.py` — **inchangé** (aucune exception métier : l'audit n'échoue jamais côté appelant).
**Exigences sécurité :** Masquage systématique avant persistance (AC 5) ; best-effort structurel (AC 4) ; logs service = action/ids/comptages uniquement ; consultation scopée super_admin côté endpoint (le service ne filtre pas par rôle — la garde est HTTP).
**Dépend de :** Tâches 1, 4, 5

### Tâche 7 : Endpoint `GET /admin/audit`
**Objectif :** Exposer la consultation paginée filtrée, réservée Super Admin.
**Fichiers :**
- `backend/app/api/v1/admin/audit.py` — Créer — `router = APIRouter()` + `GET ""` (monté sous `/audit`, cf. tâche montage) :
  - dépendance `current_user=Depends(require_super_admin)` ;
  - query params : `user_id: Optional[str] = Query(None, max_length=36)`, `action: Optional[str] = Query(None, max_length=50)`, `resource_type: Optional[str] = Query(None, max_length=30)`, `since: Optional[datetime] = Query(None)`, `skip: int = Query(0, ge=0)`, `limit: int = Query(100, ge=1, le=100)` ;
  - appelle `AuditService.list_entries` → `AuditLogListResponse` ; docstring OpenAPI riche (filtres, exemple, note rétention) ;
  - `since` invalide → 422 (validation Pydantic native) ;
- `backend/app/api/v1/admin/__init__.py` — Modifier — `admin_router.include_router(audit_router, prefix="/audit")` ;
- `backend/tests/unit/test_api/test_rbac_exhaustivite.py` — Modifier — `EXPECTED_ROUTE_COUNTS["admin"]` 15 → 16 (mécanisme prévu par le garde-fou pour tout ajout explicite).
**Exigences sécurité :** `require_super_admin` (401 sans token, 403 viewer/operator/admin org — AC 3) ; filtres bornés (anti-abus) ; pagination plafonnée 100 (rules 20) ; aucun log de requête contenant les entrées.
**Dépend de :** Tâche 6

### Tâche 8 : Émission sur actions critiques
**Objectif :** Brancher `log_from_request`/`log` sur les points du catalogue (arbitrage n°6) — un appel par point, après succès de l'action métier.
**Fichiers (un appel `AuditService.log_from_request(...)` par point, inséré après le succès métier — jamais dans le chemin d'erreur 4xx de validation) :**
- `backend/app/api/v1/auth.py` — Modifier — `user.login` (après `bruteforce_protector.reset`, avec user + ip), `user.login_failed` (aux 2 refus 401 — credentials invalides et user inactif, `details={reason}`), `user.logout`, `api_key.created` / `api_key.revoked` (dans/near les handlers `/api-keys`, `resource_id=key_id`) ;
- `backend/app/api/v1/stacks.py` — Modifier — `stack.deleted` sur DELETE `/{stack_id}` — **test de référence P1-4** : ligne avec user, org (org de la stack), action, cible, correlation_id ;
- `backend/app/api/v1/targets/crud.py` — Modifier — `target.deleted` (org du target) ;
- `backend/app/api/v1/organizations.py` — Modifier — `organization.deleted` (bulk delete → une ligne par org), `user.role_changed` (details `{previous_role, new_role}` — données déjà loggées), `member.added` / `member.removed` ;
- `backend/app/api/v1/deployments.py` — Modifier — `deployment.created` (POST, acteur `current_user`, resource = deployment) ;
- `backend/app/services/deployment_service.py` — Modifier — `deployment.succeeded` / `deployment.failed` sur transition terminale de `update_status` (`user_id=None` — acteur système, documenté) ; `stack.rollback` dans le handler restore de [`stacks.py`](../../backend/app/api/v1/stacks.py) ;
- `backend/app/api/v1/docker.py` — Modifier — `container.started` / `container.stopped` / `container.deleted` (start/stop/delete, `resource_type="container"`, `resource_id` = id conteneur) ;
- `backend/app/api/v1/plugins.py` — Modifier — `plugin.installed` / `plugin.removed` (install/uninstall, org du plugin) ;
- ⚠️ **Garde-fou** : chaque insertion doit rester non bloquante (`log` n'échoue jamais) et ne pas modifier les réponses HTTP existantes ; ne **pas** toucher au plugin `audit_logger` WebSocket (mécanisme distinct).
**Exigences sécurité :** Émission après succès (pas d'audit d'actions rejetées par validation — sauf `login_failed` volontairement audité) ; details toujours sanitizés (le service le garantit, les appelants peuvent passer des données brutes de contexte) ; correlation_id systématiquement extrait du middleware.
**Dépend de :** Tâche 6

### Tâche 9 : Boucle de purge lifespan
**Objectif :** Purge périodique selon `AUDIT_RETENTION_DAYS` (défaut : no-op).
**Fichiers :**
- `backend/app/main.py` — Modifier — Dupliquer le bloc STORY-123.4 (lignes ~158-190) en boucle dédiée `_periodic_audit_purge` : intervalle `settings.audit_purge_interval_hours * 3600` ; corps : `async with AsyncSessionLocal() as db: removed = await AuditService.purge_expired(db)` ; log démarrage + comptages ; `asyncio.create_task` + cancellation au shutdown (task nommée distincte de `purge_task`) ; si `audit_retention_days is None`, la boucle tourne quand même (no-op service) **ou** est démarrée conditionnellement — préférer : démarrage conditionnel + log unique « audit retention disabled (keep forever) » (évite un réveil horaire inutile).
**Exigences sécurité :** Purge par âge uniquement (jamais de purge sélective par acteur — inamovible) ; logs comptages.
**Dépend de :** Tâches 4, 6

### Tâche 10 : Tests — service, endpoint, émission, rétention, sécurité
**Objectif :** Écrire la couche de tests détaillée en section « Tests à écrire » (patterns 123.x/124.x : `_jwt_mode`, caplog, fixtures rôles).
**Fichiers :**
- `backend/tests/unit/test_services/test_audit_service.py` — Créer ;
- `backend/tests/unit/test_api/test_admin_audit.py` — Créer ;
- `backend/tests/unit/test_api/test_audit_emission.py` — Créer — inclut le **test de référence** DELETE stack et la non-exposition de secrets ;
- `backend/tests/integration/test_migrations.py` — Modifier (déjà couvert tâche 3).
**Exigences sécurité :** 401/403/422 endpoint ; secrets jamais dans `details` ni les logs (caplog) ; échec d'écriture n'interrompt pas l'action métier.
**Dépend de :** Tâches 7, 8, 9

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

### Backend — API (endpoint `/admin/audit`)
- `backend/tests/unit/test_api/test_admin_audit.py` (fixture `_jwt_mode` + fixtures rôles + `reset_role_cache` autouse si rôles variés)
  - `test_list_audit_superuser_200_paginated` — `test_superuser` → 200, `{items, total, skip, limit}` respectés
  - `test_list_audit_returns_401_without_token`
  - `test_list_audit_returns_403_for_org_admin` — `org_admin_user` → 403 (admin d'org ≠ super_admin)
  - `test_list_audit_returns_403_for_operator_and_viewer` — paramétré
  - `test_list_audit_invalid_query_422` — `since` non-ISO, `limit=0`/`101`, `action` > 50 chars
  - `test_list_audit_filters` — seed de lignes → filtres `user_id`, `action`, `since` retournent le sous-ensemble attendu
  - `test_list_audit_empty_returns_empty_page` — 200, `items: []`, `total: 0`

### Backend — émission (test de référence P1-4 + sécurité)
- `backend/tests/unit/test_api/test_audit_emission.py`
  - `test_delete_stack_writes_audit_line` — **critère de done P1-4** : DELETE d'une stack (mock dépendances si requis par les patterns stacks existants) → ligne `audit_logs` avec `user_id` (acteur), `organization_id` (org de la stack), `action="stack.deleted"`, `resource_type="stack"`, `resource_id`, `correlation_id` **= celui du header `X-Correlation-ID` envoyé** (assertion stricte middleware → DB)
  - `test_login_success_and_failure_audited` — login OK → `user.login` avec ip ; mauvais password → `user.login_failed` (`user_id=None` si user inconnu)
  - `test_logout_audited` / `test_api_key_created_and_revoked_audited` — lignes `api_key.created`/`api_key.revoked` (STORY-124 non régressé)
  - `test_role_change_audited` — PUT member role → `user.role_changed` avec `{previous_role, new_role}` dans `details`
  - `test_target_and_organization_deletion_audited`
  - `test_deployment_created_audited` — POST deployment → `deployment.created` avec acteur
  - `test_audit_failure_does_not_break_business_action` — injection d'échec (patch `AuditService.log` interne levant, ou session en échec) → le DELETE stack répond quand même 200/204 (AC 4)
  - `test_no_secrets_in_audit_details` — login avec password + création clé API → aucune ligne d'audit ne contient le password ni la clé `wf_ak_...` brute dans `details` (AC 5)
  - `test_no_secrets_in_logs_caplog` — parcours émission sous caplog : password/clé absents des logs (neutraliser `sqlalchemy.engine` en WARNING — piège documenté)

### Backend — rétention (AC 4)
- dans `test_audit_service.py` ou `test_audit_emission.py`
  - `test_purge_applied_with_short_retention` — `AUDIT_RETENTION_DAYS=1` (monkeypatch settings) + lignes de > 1 j → `purge_expired` les supprime ; récentes conservées
  - `test_retention_default_keeps_forever` — défaut `None` → aucune purge

### Commandes de validation
```bash
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/test_models/test_audit_log.py backend/tests/unit/test_services/test_audit_service.py -v
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/test_api/test_admin_audit.py backend/tests/unit/test_api/test_audit_emission.py -v
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/test_alembic_config.py backend/tests/unit/test_database.py backend/tests/integration/test_migrations.py -v
# Non-régression (suites sœurs + large)
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/test_api/test_api_keys.py backend/tests/unit/test_api/test_auth_refresh_security.py backend/tests/unit/test_auth/ -v
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/ -q --no-cov -p no:randomly
make backend-lint && make backend-typecheck
```
*(⚠️ venv Poetry racine cassé — utiliser `.venv-test` comme documenté par 124.4 ; ajuster les chemins relatifs selon cwd.)*
