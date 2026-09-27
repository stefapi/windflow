# STORY-125.3 : Endpoint admin `GET /admin/audit`, purge lifespan et rétention

**Statut :** DONE
**Story Parente :** STORY-125 — [ABANDONED] Audit trail — table `audit_logs`, émission sur actions critiques, `GET /admin/audit`, rétention (P1-4) *(découpée — le fichier mère reste la source d'analyse détaillée)*
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-4 (axe A3, rapport §7) — ampleur **M**

## Description

En tant que super-administrateur de WindFlow, je veux consulter le journal d'audit via `GET /api/v1/admin/audit` — paginé (`{items, total, skip, limit}`, plafond 100), filtrable (`user_id`, `action`, `resource_type`, `since`), strictement réservé au rôle super_admin — et voir la rétention configurable `AUDIT_RETENTION_DAYS` (défaut illimité) appliquée par une boucle de purge lifespan dédiée, afin d'exploiter opérationnellement le journal posé par le socle (STORY-125.1) et alimenté par l'émission (STORY-125.2) sans croissance incontrôlée de la table.

Troisième étape de STORY-125 (découpe proactive `split-story` validée par l'utilisateur le 2026-09-25) : couvre les **tâches 7 et 9** de l'analyse mère (endpoint admin + boucle de purge lifespan) et les tests associés (endpoint 401/403/422/pagination/filtres, rétention). Consomme le service `AuditService.list_entries`/`purge_expired` et les schemas posés par STORY-125.1. Parallélisable avec STORY-125.2 (aucune intersection de fichiers).

## Critères d'acceptation (AC)

- [x] AC 3 : `GET /api/v1/admin/audit` répond **paginé** avec filtres (`user_id`, `action`, `since`) ; protégé `super_admin` (STORY-122) : `401` sans token, `403` pour viewer/operator/admin d'org.
- [x] AC 4 : **Rétention configurable** appliquée : `AUDIT_RETENTION_DAYS` (défaut illimité) purge les entrées au-delà du seuil — test avec valeur courte.

> **Note de découpe :** cette sous-story couvre l'AC 3 **en intégralité** et la part **application périodique** de l'AC 4 (boucle lifespan + test avec valeur courte). Les autres parts de l'AC 4 sont portées ailleurs : garantie structurelle « écriture ne levant jamais » → STORY-125.1 (test service `test_log_never_raises_on_db_failure`), démonstration en conditions réelles « échec d'écriture n'interrompt pas l'action métier » → STORY-125.2 (`test_audit_failure_does_not_break_business_action`). L'AC 5 est porté par STORY-125.2 (case unique) : secrets jamais dans `details` structurellement (125.1) et sur parcours réel (125.2) ; ici, l'endpoint ne fait qu'exposer des lignes déjà masquées (lecture fidèle, aucun champ falsifiable) — `make lint` + tests figurent dans les commandes de validation.

## Contexte technique

> Analyse réalisée par `analyse-story` (2026-09-25), répartie par `split-story` — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches. Source : [`STORY-125-audit-trail-table-emission-retention.md`](STORY-125-audit-trail-table-emission-retention.md).

**Couches impactées :** Backend uniquement — 1 endpoint admin (fichier nouveau + montage), boucle lifespan dans `main.py`, garde-fou routes, tests API et rétention. Aucun impact frontend/CLI (la consultation UI/CLI viendra après les enveloppes STORY-126/128).

**Spécifications de référence :**
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Administration → `GET /admin/audit` (filtres user/action/date) ;
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — matrice : Audit consultation = Admin+ ; administration système (endpoint sous `/admin/`) = **Super Admin** ;
- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) — § Audit trail : rétention `AUDIT_RETENTION_DAYS` (défaut : conservation indéfinie, ex. 90 jours sur RPi) ;
- [`.roo/rules/20-architecture-and-api.md`](../../.roo/rules/20-architecture-and-api.md) — pagination obligatoire pour listes > 20 éléments ; OpenAPI documenté.

**Disponible en entrée (posé par STORY-125.1) :** table `audit_logs` ; `AuditService.list_entries(db, *, user_id, action, resource_type, since, skip, limit) -> tuple[list[AuditLog], int]` (ord re `created_at desc`) ; `AuditService.purge_expired(db) -> int` (no-op si `audit_retention_days=None`) ; config `audit_retention_days` / `audit_purge_interval_hours` ; schemas `AuditLogResponse` / `AuditLogListResponse`.

**Fichiers de référence (patterns validés) :**
- Endpoint admin → pattern [`backend/app/api/v1/admin/stacks_management.py`](../../backend/app/api/v1/admin/stacks_management.py) : `require_super_admin` ([`backend/app/auth/rbac.py`](../../backend/app/auth/rbac.py)), docstrings OpenAPI riches ; montage dans [`backend/app/api/v1/admin/__init__.py`](../../backend/app/api/v1/admin/__init__.py) (`admin_router` préfixe `/admin`) ;
- Pagination → pattern `skip`/`limit` `Query(0, ge=0)` / `Query(100, ge=1, le=100)` + réponse `{items, total, skip, limit}` ([`backend/app/schemas/common.py:49`](../../backend/app/schemas/common.py) `PaginatedResponse`, [`backend/app/schemas/deployment.py:308`](../../backend/app/schemas/deployment.py) `DeploymentListResponse`) — **pas** d'enveloppe `{data,pagination}` (STORY-126 non mergée ; réalignement prévu par elle) ;
- Job de purge → pattern lifespan [`backend/app/main.py:158`](../../backend/app/main.py) (STORY-123.4) : boucle asyncio `while True` + `AsyncSessionLocal` + `asyncio.create_task` + cancellation au shutdown — **à dupliquer** pour l'audit (ne pas fusionner les deux boucles : intervalles et logs distincts) ; purge service → pattern `RefreshTokenService.purge_expired` ([`backend/app/services/refresh_token_service.py:336`](../../backend/app/services/refresh_token_service.py)) : `delete()` SQL bulk + `synchronize_session=False`, log comptages uniquement ;
- Tests API → pattern [`backend/tests/unit/test_api/test_api_keys.py`](../../backend/tests/unit/test_api/test_api_keys.py) : fixture `_jwt_mode` (monkeypatch `disable_auth=False`), fixtures rôles conftest (`viewer_user`, `operator_user`, `org_admin_user`, `test_superuser`), mint direct JWT, `reset_role_cache` autouse si rôles variés ;
- Fixtures disponibles : `db_session`, `test_user`, `test_organization` ([`backend/tests/conftest.py`](../../backend/tests/conftest.py)).

**Décisions d'analyse (arbitrages pertinents pour ce périmètre) :**

1. **Endpoint consultation** : `GET /api/v1/admin/audit` — **`require_super_admin`** (l'endpoint vit sous `/admin/` ; matrice spec 08 : administration système = Super Admin) ; filtres `user_id` (str), `action` (str ≤ 50), `resource_type` (str ≤ 30), `since` (datetime ISO) ; pagination `skip`/`limit` Query bornés (max 100) ; réponse `AuditLogListResponse {items, total, skip, limit}` (pattern `DeploymentListResponse`) — **pas** d'enveloppe `{data,pagination}` (STORY-126 non mergée ; réalignement prévu par elle, cf. Dépendances) ;
2. **Boucle de purge lifespan dédiée** : dupliquer le bloc STORY-123.4 (lignes ~158-190) en boucle dédiée `_periodic_audit_purge` — intervalle `settings.audit_purge_interval_hours * 3600` ; corps : `async with AsyncSessionLocal() as db: removed = await AuditService.purge_expired(db)` ; log démarrage + comptages ; `asyncio.create_task` + cancellation au shutdown (task nommée distincte de `purge_task`) ; si `audit_retention_days is None` → **démarrage conditionnel** + log unique « audit retention disabled (keep forever) » (évite un réveil horaire inutile) ;
3. **Purge par âge uniquement** (jamais de purge sélective par acteur — inamovible) ; logs comptages.

**Pièges environnement (documentés par 123.x/124.x, toujours valables) :**
- Exécuter les tests avec `DISABLE_AUTH=false LOG_LEVEL=WARNING` et le venv **`.venv-test`** (Python 3.11) — le venv Poetry racine est cassé (alembic défectueux) ;
- Garde-fou routes : tout ajout de route admin doit incrémenter `EXPECTED_ROUTE_COUNTS["admin"]` (mécanisme prévu par le test pour tout ajout explicite).

## Dépendances

> Statuts vérifiés par l'analyse de la story mère (2026-09-25).

- **STORY-125.1** — **prérequis dur** : `AuditService.list_entries`/`purge_expired`, schemas `AuditLogResponse`/`AuditLogListResponse`, config `audit_retention_days`/`audit_purge_interval_hours` ;
- **STORY-122** (`require_super_admin`) / **STORY-120** (Alembic) — **DONE ✔** : aucune dépendance bloquante ;
- **Parallélisable avec** STORY-125.2 (aucune intersection de fichiers : `admin/audit.py` + `main.py` + garde-fou ici, routers métier là) ;
- **Coordination (non bloquante) :** STORY-126 (enveloppes) et STORY-128 (pagination `?page&per_page`) réaligneront le format de réponse de `/admin/audit` — cette sous-story livre le format courant (`{items,total,skip,limit}`), les AC ne présument pas de l'enveloppe ;
- **Référence croisée epic :** critère de done P1-4 « rétention configurable appliquée » — démontré par les tests de rétention de cette sous-story.

## Tâches d'implémentation détaillées

### Tâche 1 : Endpoint `GET /admin/audit`
**Objectif :** Exposer la consultation paginée filtrée, réservée Super Admin (tâche 7 de l'analyse mère).
**Fichiers :**
- `backend/app/api/v1/admin/audit.py` — Créer — `router = APIRouter()` + `GET ""` (monté sous `/audit`, cf. Tâche 2) :
  - dépendance `current_user=Depends(require_super_admin)` ;
  - query params : `user_id: Optional[str] = Query(None, max_length=36)`, `action: Optional[str] = Query(None, max_length=50)`, `resource_type: Optional[str] = Query(None, max_length=30)`, `since: Optional[datetime] = Query(None)`, `skip: int = Query(0, ge=0)`, `limit: int = Query(100, ge=1, le=100)` ;
  - appelle `AuditService.list_entries` → `AuditLogListResponse` ; docstring OpenAPI riche (filtres, exemple, note rétention) ;
  - `since` invalide → 422 (validation Pydantic native) ;
- `backend/app/api/v1/admin/__init__.py` — Modifier — `admin_router.include_router(audit_router, prefix="/audit")` ;
- `backend/tests/unit/test_api/test_rbac_exhaustivite.py` — Modifier — `EXPECTED_ROUTE_COUNTS["admin"]` 15 → 16 (mécanisme prévu par le garde-fou pour tout ajout explicite).
**Exigences sécurité :** `require_super_admin` (401 sans token, 403 viewer/operator/admin org — AC 3) ; filtres bornés (anti-abus) ; pagination plafonnée 100 (rules 20) ; aucun log de requête contenant les entrées.
**Dépend de :** STORY-125.1 (service + schemas)

### Tâche 2 : Boucle de purge lifespan
**Objectif :** Purge périodique selon `AUDIT_RETENTION_DAYS` (défaut : no-op — démarrage conditionnel) (tâche 9 de l'analyse mère).
**Fichiers :**
- `backend/app/main.py` — Modifier — Dupliquer le bloc STORY-123.4 (lignes ~158-190) en boucle dédiée `_periodic_audit_purge` :
  - intervalle `settings.audit_purge_interval_hours * 3600` ; corps : `async with AsyncSessionLocal() as db: removed = await AuditService.purge_expired(db)` ; log démarrage + comptages ;
  - `asyncio.create_task` + cancellation au shutdown (task nommée distincte de `purge_task`) ;
  - si `audit_retention_days is None` : **démarrage conditionnel** + log unique « audit retention disabled (keep forever) » (évite un réveil horaire inutile).
**Exigences sécurité :** Purge par âge uniquement (jamais de purge sélective par acteur — inamovible) ; logs comptages.
**Dépend de :** STORY-125.1 (config + `purge_expired`)

### Tâche 3 : Tests endpoint et rétention
**Objectif :** Couvrir l'endpoint (401/403/422, pagination, filtres) et la rétention (AC 4) — part de la tâche 10 de l'analyse mère.
**Fichiers :**
- `backend/tests/unit/test_api/test_admin_audit.py` — Créer — Pattern `test_api_keys.py` : fixture `_jwt_mode` + fixtures rôles conftest + `reset_role_cache` autouse (rôles variés) ; seed de lignes d'audit via `AuditService.log`. Détail en section « Tests à écrire » ;
- Rétention : dans `backend/tests/unit/test_services/test_audit_service.py` (créé par STORY-125.1) ou `backend/tests/unit/test_api/test_audit_emission.py` (STORY-125.2) — selon l'emplacement le plus naturel, sans dupliquer les tests service `test_purge_expired_*` déjà écrits en 125.1 : les tests ici valident l'**application configurable** (monkeypatch settings).
**Exigences sécurité :** 401 sans token ; 403 viewer/operator/org_admin (paramétré) ; 422 query invalide ; pagination/filtres exacts ; rétention par âge uniquement.
**Dépend de :** Tâches 1, 2

## Tests à écrire

### Backend — API (endpoint `/admin/audit`)
- `backend/tests/unit/test_api/test_admin_audit.py` (fixture `_jwt_mode` + fixtures rôles + `reset_role_cache` autouse si rôles variés)
  - `test_list_audit_superuser_200_paginated` — `test_superuser` → 200, `{items, total, skip, limit}` respectés
  - `test_list_audit_returns_401_without_token`
  - `test_list_audit_returns_403_for_org_admin` — `org_admin_user` → 403 (admin d'org ≠ super_admin)
  - `test_list_audit_returns_403_for_operator_and_viewer` — paramétré
  - `test_list_audit_invalid_query_422` — `since` non-ISO, `limit=0`/`101`, `action` > 50 chars
  - `test_list_audit_filters` — seed de lignes → filtres `user_id`, `action`, `since` retournent le sous-ensemble attendu
  - `test_list_audit_empty_returns_empty_page` — 200, `items: []`, `total: 0`

### Backend — rétention (AC 4)
- dans `test_audit_service.py` ou `test_audit_emission.py`
  - `test_purge_applied_with_short_retention` — `AUDIT_RETENTION_DAYS=1` (monkeypatch settings) + lignes de > 1 j → `purge_expired` les supprime ; récentes conservées
  - `test_retention_default_keeps_forever` — défaut `None` → aucune purge

### Commandes de validation
```bash
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/test_api/test_admin_audit.py -v
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/test_services/test_audit_service.py -v  # si tests rétention côté service
# Garde-fou routes (EXPECTED_ROUTE_COUNTS admin 15 → 16)
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/test_api/test_rbac_exhaustivite.py -v
# Non-régression large
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/ -q --no-cov -p no:randomly
make backend-lint && make backend-typecheck
```
*(⚠️ venv Poetry racine cassé — utiliser `.venv-test` comme documenté par 124.4 ; ajuster les chemins relatifs selon cwd.)*

## État d'avancement technique

*(coché par `treat-story` pendant l'implémentation)*

- [x] Tâche 1 : Endpoint `GET /api/v1/admin/audit` (super_admin, filtres, pagination) + garde-fou routes admin 15 → 16
- [x] Tâche 2 : Boucle de purge lifespan dédiée (démarrage conditionnel, no-op par défaut)
- [x] Tâche 3 : Tests endpoint (401/403/422/pagination/filtres) + tests rétention

## Notes d'implémentation

*(clôture `treat-story` — 2026-09-27)*

### Fichiers modifiés/créés

- [`backend/app/api/v1/admin/audit.py`](../../backend/app/api/v1/admin/audit.py) — **créé** : `GET ""` (monté sous `/admin/audit`) avec `require_super_admin`, filtres bornés (`user_id` ≤ 36, `action` ≤ 50, `resource_type` ≤ 30, `since` datetime ISO), pagination `skip`/`limit` plafonnée 100, réponse `AuditLogListResponse {items, total, skip, limit}`, docstring OpenAPI riche (filtres, exemple, note masquage `details`, rétention).
- [`backend/app/api/v1/admin/__init__.py`](../../backend/app/api/v1/admin/__init__.py) — montage `admin_router.include_router(audit_router, prefix="/audit")`.
- [`backend/app/main.py`](../../backend/app/main.py) — boucle lifespan dédiée `_periodic_audit_purge` (pattern STORY-123.4 dupliqué, **non fusionnée** avec la purge refresh tokens : intervalles/logs distincts) : intervalle `audit_purge_interval_hours * 3600`, corps `AsyncSessionLocal` + `AuditService.purge_expired`, **démarrage conditionnel** — `audit_retention_days is None` (défaut) → job non démarré + log unique « audit retention disabled (keep forever) » ; cancellation au shutdown (task `audit_purge_task` distincte de `purge_task`).
- [`backend/tests/unit/test_api/test_rbac_exhaustivite.py`](../../backend/tests/unit/test_api/test_rbac_exhaustivite.py) — garde-fou `EXPECTED_ROUTE_COUNTS["admin"]` 15 → 16.
- [`backend/tests/unit/test_api/test_admin_audit.py`](../../backend/tests/unit/test_api/test_admin_audit.py) — **créé** : 9 tests (200 paginé + ordre décroissant, 401, 403 org_admin/viewer/operator, 422 × 7 variantes, page vide, filtres `user_id`/`action`/`since`, pagination `skip`/`limit` sans chevauchement).
- [`backend/tests/unit/test_services/test_audit_service.py`](../../backend/tests/unit/test_services/test_audit_service.py) — `test_purge_applied_with_short_retention` ajouté dans `TestPurgeExpired` (AC 4 « valeur courte » : rétention 1 j → lignes de 3 j purgées, 2 h conservées).

### Décisions techniques

- **Réponse non enveloppée** `{items, total, skip, limit}` (pattern `DeploymentListResponse`) — pas d'enveloppe `{data, pagination}` : STORY-126 (non mergée) réalignera, cf. Dépendances.
- **Lecture seule stricte** : l'endpoint ne fait que consommer `AuditService.list_entries` — aucun schema d'écriture, la donnée d'audit reste non falsifiable depuis l'extérieur ; `details` restitué tel quel (masquage structurel à l'écriture, STORY-125.1).
- **Démarrage conditionnel du job** plutôt que boucle no-op : évite un réveil horaire inutile au défaut « conservation indéfinie » (spec 15).
- **Tests rétention** placés dans `test_audit_service.py` (`TestPurgeExpired`) — les tests `test_purge_expired_noop_when_retention_none` / `test_purge_expired_removes_only_old_entries` de 125.1 couvraient déjà l'essentiel ; seul le cas « valeur courte 1 j » exigé par l'AC 4 a été ajouté, sans duplication.

### Divergences par rapport à l'analyse

1. Test paramétré `test_list_audit_returns_403_for_operator_and_viewer` : le paramétrage via `request.getfixturevalue` sur fixture async lève `RuntimeError: Runner.run() cannot be called from a running event loop` (pytest-asyncio) — remplacé par deux tests directs viewer/operator (même couverture, libellés conservés).
2. `test_retention_default_keeps_forever` : non dupliqué — déjà couvert par `test_purge_expired_noop_when_retention_none` (STORY-125.1, spy prouvant zéro requête delete).

### Validation

```bash
# Exécuté (venv .venv-test documenté — venv Poetry racine cassé)
DISABLE_AUTH=false LOG_LEVEL=WARNING .venv-test/bin/pytest backend/tests/unit/test_api/test_admin_audit.py backend/tests/unit/test_api/test_rbac_exhaustivite.py backend/tests/unit/test_services/test_audit_service.py -q --no-cov -p no:randomly
# → 41 passed (dont garde-fou routes admin = 16)
DISABLE_AUTH=false LOG_LEVEL=WARNING .venv-test/bin/pytest backend/tests/unit/ -q --no-cov -p no:randomly
# → 1552 passed (non-régression complète)
# lint black/isort/flake8 sur fichiers modifiés : OK ; mypy : audit.py clean
# (19 erreurs pré-existantes stubs yaml/jose dans fichiers transitifs — hors périmètre)
```
