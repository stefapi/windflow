# STORY-122.3 : Application RBAC — stacks, deployments, schedules et isolation organisationnelle

**Statut :** DONE
**Story Parente :** STORY-122 — Dépendances RBAC `require_role(...)` — hiérarchie, cache TTL 300 s et protections d'escalade sur les ~110 endpoints (P1-2, application)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'administrateur sécurité de WindFlow, je veux que les 29 endpoints de déploiement (stacks 15, deployments 8, schedules 6) soient protégés par `require_role(...)` selon la matrice spec 08 (lectures → viewer ; deploy/rollback/actions → operator ; CRUD → admin), et que l'isolation organisationnelle soit vérifiée par tests : un utilisateur n'accède pas aux ressources d'une organisation à laquelle il n'appartient pas.

## Critères d'acceptation (AC)

- [x] AC 2 (volet stacks/deployments/schedules) : Tous les endpoints de ces 3 routers sont protégés par `require_role(...)` conformément à la matrice spec 08 ; vérifié par une matrice rôle×endpoint représentative : viewer → `403` sur les POST/PUT/DELETE de gestion ; operator → `200` sur les actions opérationnelles (deploy/rollback) et `403` sur la gestion ; admin → gestion `200` dans son organisation.
- [x] AC 4 : Isolation organisationnelle : un utilisateur n'accède pas aux ressources d'une organisation à laquelle il n'appartient pas (`403`/`404` selon la matrice) — vérifié sur un échantillon représentatif (stacks, targets, deployments).

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-08) — inventaire vérifié par grep ; scoping STORY-121.3 déjà en place sur les listes.

**Couches impactées :** Backend uniquement — 3 routers + tests.

**Spécifications de référence :**
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — § Matrice : Stacks (Lister/Voir config = tous ; Déployer/Rollback = Operator+ ; Créer/Éditer/Supprimer = Admin+) ; Système (schedules = gestion d'automatisation → Admin+, activation/toggle = Operator+ par analogie avec les actions opérationnelles) ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Sécurité : permissions vérifiées après authentification, par famille.

**Inventaire vérifié et rôles minimum cibles :**

**[`stacks.py`](../../backend/app/api/v1/stacks.py) — 15 routes :**

| # | Route (ligne) | Verbe | Rôle min | Justification matrice |
|---|---------------|-------|----------|----------------------|
| 1 | `/` (l. 117) | GET | viewer | Lister stacks |
| 2 | `/{stack_id}` (l. 245) | GET | viewer | Voir config |
| 3 | `/` (l. 409) | POST | admin | Créer stack |
| 4 | `/{stack_id}` (l. 797) | PUT | admin | Éditer |
| 5 | `/{stack_id}` (l. 1074) | DELETE | admin | Supprimer |
| 6 | `/{stack_id}/deploy` (l. 1199) | POST | operator | Déployer |
| 7 | `/{stack_id}` (l. 1450) | GET | viewer | Lecture (détail/usage) |
| 8 | l. 1495 | POST | operator | Action opérationnelle (ex. start/scale) |
| 9 | l. 1554 | POST | operator | Action opérationnelle |
| 10 | l. 1670 | POST | operator | Action opérationnelle |
| 11 | l. 1746 | POST | operator | Action opérationnelle |
| 12 | l. 1823 | POST | operator | Action opérationnelle |
| 13 | l. 1929 | POST | operator | Rollback (rollback = Operator+) |
| 14 | l. 2021 | POST | operator | Action opérationnelle |
| 15 | l. 2120 | POST | operator | Action opérationnelle |

> Les routes POST n° 8-12, 14 (lignes 1495-2120) sont des actions opérationnelles sur stacks (start/stop/restart/scale/validate…) — vérifier le libellé exact de chacune à l'implémentation ; toute route s'avérant être une création/modification de configuration (ex. duplicate, adopt) basculera en `admin` **après signalement de divergence** (règle 01 §5.3).

**[`deployments.py`](../../backend/app/api/v1/deployments.py) — 8 routes :**

| # | Route (ligne) | Verbe | Rôle min |
|---|---------------|-------|----------|
| 1 | `/` (l. 30) | GET | viewer |
| 2 | `/{deployment_id}` (l. 161) | GET | viewer |
| 3 | `/stats` ou similaire (l. 304) | GET | viewer |
| 4 | l. 446 | POST | operator (action déploiement) |
| 5 | l. 711 | PUT | admin (modification config deployment) |
| 6 | l. 933 | POST | operator (rollback/cancel) |
| 7 | l. 1130 | POST | operator (retry/action) |
| 8 | `/{deployment_id}` (l. 1326) | DELETE | admin |

**[`schedules.py`](../../backend/app/api/v1/schedules.py) — 6 routes :**

| # | Route (ligne) | Verbe | Rôle min |
|---|---------------|-------|----------|
| 1 | `/schedules` (l. 24) | GET | viewer |
| 2 | `/schedules/{task_id}` (l. 35) | GET | viewer |
| 3 | `/schedules` (l. 49) | POST | admin |
| 4 | `/schedules/{task_id}` (l. 68) | PUT | admin |
| 5 | `/schedules/{task_id}` (l. 83) | DELETE | admin |
| 6 | `/schedules/{task_id}/toggle` (l. 96) | POST | operator (activation = opération) |

**Isolation existante (réutilisation, pas de réécriture) :**
- Listes déjà scopées par appartenance (STORY-121.3) : `UserOrganizationService.get_user_organization_ids` dans `stacks.py` (l. 223), `deployments.py` (l. 127), cf. grep « STORY-121.3 : scoping » ;
- Contrôle d'appartenance cible : pattern existant deployments.py l. 284/l. 422 (« Vérifier que le déploiement appartient à la même organisation ») — les tests AC 4 vérifient que ce contrôle tient avec les nouveaux rôles (un admin d'org A ne déploie pas un stack de l'org B → 403/404).

**Fichiers de référence (patterns vérifiés) :**
- Dépendances — [`backend/app/auth/rbac.py`](../../backend/app/auth/rbac.py) (STORY-122.1) : `require_viewer`, `require_operator`, `require_admin` ;
- Tests isolation — [`backend/tests/unit/test_api/test_auth_isolation.py`](../../backend/tests/unit/test_api/test_auth_isolation.py) + seeds directs en session (pattern `test_deployments.py`).

**Exigences sécurité identifiées (Phase 2.6) :**
- Auth : 401 sans token (chaîne `require_role`) ;
- RBAC : matrice ci-dessus — rôle **global** pour la dépendance + isolation **par organisation** via les checks existants (superuser bypass) ;
- Validation : inchangée ;
- Exposition : inchangée ;
- Audit : non (STORY-125).

## Dépendances

- STORY-122.1 (socle). Peut être menée en parallèle de 122.2/122.4/122.5/122.6.

## Tâches d'implémentation détaillées

### Tâche 1 : Protéger les 15 routes de `stacks.py`
**Objectif :** Appliquer `require_role` aux 15 routes selon la matrice (GET → viewer ; POST opérationnels + rollback → operator ; POST/PUT/DELETE gestion → admin).
**Fichiers :**
- `backend/app/api/v1/stacks.py` — Modifier — Même mécanique que docker.py : remplacer `Depends(get_current_active_user)` par `require_viewer`/`require_operator`/`require_admin` selon le tableau ; import `from ...auth.rbac import require_admin, require_operator, require_viewer` ; mettre à jour les sections OpenAPI `## Access Control` ; vérifier individuellement les libellés des POST l. 1495-2120 (divergence → signaler avant bascule en admin) ; **aucun changement de path/response_model**.
**Exigences sécurité :** Dépendance uniquement ; 401/403 par socle.
**Dépend de :** STORY-122.1

### Tâche 2 : Protéger les 8 routes de `deployments.py`
**Objectif :** Appliquer `require_role` aux 8 routes (lectures viewer ; actions operator ; PUT/DELETE admin).
**Fichiers :**
- `backend/app/api/v1/deployments.py` — Modifier — Idem Tâche 1 ; conserver les checks d'isolation organisationnelle existants (l. 284, 422) intacts — la dépendance de rôle est additive.
**Exigences sécurité :** Idem Tâche 1.
**Dépend de :** STORY-122.1

### Tâche 3 : Protéger les 6 routes de `schedules.py`
**Objectif :** Appliquer `require_role` aux 6 routes (lectures viewer ; toggle operator ; POST/PUT/DELETE admin).
**Fichiers :**
- `backend/app/api/v1/schedules.py` — Modifier — Idem Tâche 1.
**Exigences sécurité :** Idem Tâche 1.
**Dépend de :** STORY-122.1

### Tâche 4 : Tests matrice + isolation cross-organisation (AC 4)
**Objectif :** Vérifier la matrice par échantillon et l'isolation organisationnelle sur stacks/deployments (ressources d'une org étrangère inaccessibles même avec un rôle suffisant).
**Fichiers :**
- `backend/tests/unit/test_api/test_stacks_rbac.py` — Créer — viewer 403 sur `POST /stacks`, `PUT /stacks/{id}`, `DELETE /stacks/{id}` ; viewer 200 `GET /stacks` ; operator 200 `POST /stacks/{id}/deploy` (orchestrateur mocké), 403 sur `POST /stacks` et `DELETE /stacks/{id}` ; admin 200 CRUD (dans son org) ; 401 sans token (échantillon).
- `backend/tests/unit/test_api/test_deployments_rbac.py` — Créer — matrice équivalente sur échantillon GET/POST/DELETE.
- `backend/tests/unit/test_api/test_schedules_rbac.py` — Créer — viewer 403 `POST /schedules` ; operator 200 `toggle` + 403 `POST /schedules` ; admin 200 CRUD.
- `backend/tests/unit/test_api/test_rbac_isolation.py` — Créer — **AC 4** : seed 2 organisations (org A, org B) + users (admin-A : admin dans A seulement ; viewer-B) + ressources (stack-A, deployment-A, target-A en A ; ressources B) :
  - `test_admin_org_a_cannot_deploy_stack_of_org_b` → 403/404 sur `POST /stacks/{stack_B}/deploy` ;
  - `test_admin_org_a_cannot_read_deployment_of_org_b` → 403/404 sur `GET /deployments/{deployment_B}` (assert : pas 200) ;
  - `test_user_without_membership_gets_404_list_scoped` → listes scopées : `GET /stacks` ne retourne aucune ressource de B pour admin-A (scoping 121.3 non régressé) ;
  - `test_superuser_accesses_all_orgs` → superuser 200 partout.
**Exigences sécurité :** 401/403/404 par rôle et par org ; l'assertion clé est « pas 200 » sur ressource étrangère.
**Dépend de :** Tâches 1, 2, 3

## Tests à écrire

> Détail en Tâche 4. Commandes :

### Unitaires Backend
- `backend/tests/unit/test_api/test_stacks_rbac.py` — matrice stacks
- `backend/tests/unit/test_api/test_deployments_rbac.py` — matrice deployments
- `backend/tests/unit/test_api/test_schedules_rbac.py` — matrice schedules
- `backend/tests/unit/test_api/test_rbac_isolation.py` — **AC 4** isolation cross-org (stacks, deployments, targets)

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_api/test_stacks_rbac.py backend/tests/unit/test_api/test_deployments_rbac.py backend/tests/unit/test_api/test_schedules_rbac.py backend/tests/unit/test_api/test_rbac_isolation.py -v
poetry run pytest backend/tests/unit/test_api/test_auth_isolation.py -v  # non-régression isolation 121.3
make backend-lint && make backend-typecheck
```

## État d'avancement technique
- [x] Tâche 1 : Matrice `require_role` sur stacks.py (15 routes)
- [x] Tâche 2 : Matrice `require_role` sur deployments.py (8 routes)
- [x] Tâche 3 : Matrice `require_role` sur schedules.py (6 routes)
- [x] Tâche 4 : Tests matrice + isolation cross-org (AC 4)
- [x] Lint & typecheck OK

## Notes d'implémentation

**Date :** 2026-09-11

### Fichiers modifiés/créés

**Modifiés (3 routers) :**
- `backend/app/api/v1/stacks.py` — 15 routes protégées (GET ×3 → `require_viewer` ; POST start/stop/redeploy/regenerate-variable/versions/restore/archive/unarchive → `require_operator` ; POST / + PUT / + DELETE / + POST duplicate → `require_admin`) ; import `auth.rbac` ; sections OpenAPI `## Access Control` ajoutées (pattern 122.2) ; **réparation** de l'appel `StackService.create(session, data, org)` (TypeError 500 préexistant — signature à 2 args) + check d'appartenance `is_member` sur l'`organization_id` du body (AC 4).
- `backend/app/api/v1/deployments.py` — 8 routes protégées (GET ×3 → `require_viewer` ; POST / + retry + cancel → `require_operator` ; PUT /{id} + DELETE /{id} → `require_admin`) ; **check d'isolation ajouté** dans `create_deployment` : la stack référencée doit appartenir à une organisation de l'utilisateur (403 sinon, 404 si inexistante) — AC 4 ; import `StackService`.
- `backend/app/api/v1/schedules.py` — 6 routes protégées (GET ×2 → `require_viewer` ; POST/PUT/DELETE → `require_admin` ; toggle → `require_operator`) ; sections OpenAPI `## Access Control` + summaries/descriptions.

**Créés (4 fichiers de tests) :**
- `backend/tests/unit/test_api/test_stacks_rbac.py` — 9 tests (viewer 200/403×3, operator 200 start Docker-mocké/403×2, admin 201, 401×3).
- `backend/tests/unit/test_api/test_deployments_rbac.py` — 7 tests (viewer 200 liste+détail/403 delete, operator 201 create orchestrateur mocké/403 update, admin 204 delete, 401×3).
- `backend/tests/unit/test_api/test_schedules_rbac.py` — 8 tests (viewer 200 liste/403 create, operator 200 toggle/403 create, admin 201/200/204, 401×3).
- `backend/tests/unit/test_api/test_rbac_isolation.py` — 8 tests AC 4 (2 orgs, admin-A/viewer-B, superuser) : lecture/déploiement/suppression ressource étrangère → 403/pas 200 ; listes scopées sans fuite ; superuser 200 partout.

### Décisions techniques
- Bascule `POST /stacks/{id}/duplicate` en `require_admin` (création de configuration — divergence prévue par la story) ;
- `regenerate-variable`, `create_stack_version`, `restore`, `archive`, `unarchive` → `require_operator` (actions opérationnelles sur ressource existante, pas des CRUD de config) ;
- `POST /deployments` → `require_operator` (action de déploiement conforme matrice spec 08 « Déployer = Operator+ ») ;
- Fixtures autouse `_jwt_mode` (disable_auth=False) + `_fresh_role_cache` (pattern test_docker_rbac 122.2) ;
- Seeds directs en session (pattern test_deployments STORY-103.3) sans tâche async.

### Divergences par rapport à l'analyse
1. **Tâche 1** : la route « l. 1199 » est `regenerate-variable` (pas `deploy`) → `require_operator` maintenu (action opérationnelle). La route `POST /stacks/{id}/deploy` citée en AC n'existe pas : le déploiement passe par `POST /deployments` (stack_id en body) — les tests AC 4 (test_admin_org_a_cannot_deploy_stack_of_org_b) portent sur cette route réelle.
2. **Tâche 2** : ajout (minimal, exigé par AC 4) du check d'isolation sur la stack référencée dans `create_deployment` — l'analyse supposait le contrôle existant, il manquait pour les créations.
3. **Tâche 1** : `StackService.create` appelé avec 3 args (TypeError 500 préexistant, masqué par `# type: ignore[call-arg]`) — corrigé en `create(session, stack_data)` ; `organization_id` vient du body (requis par `StackCreate`) avec vérification `is_member` si ≠ org primaire.
4. Assertions par `id` (pas `organization_id`) : `StackSummaryResponse`/`DeploymentResponse` n'exposent pas ce champ.

### Difficultés rencontrées
- Environnement : le venv Poetry (python3.14) a un package alembic cassé → tests exécutés via `.venv-test` (python3.11) ; les 19 erreurs mypy signalées concernent des modules tiers/non modifiés (stubs psutil, etc.), 0 erreur sur les fichiers touchés.

### Tests ajoutés
- `tests/unit/test_api/test_stacks_rbac.py` : 9 tests — passants
- `tests/unit/test_api/test_deployments_rbac.py` : 7 tests — passants
- `tests/unit/test_api/test_schedules_rbac.py` : 8 tests — passants
- `tests/unit/test_api/test_rbac_isolation.py` : 8 tests — passants

**Validation :** 40/40 tests ciblés + 534 non-régression (test_api + test_docker + test_auth) + flake8/black/isort OK + mypy 0 erreur sur fichiers modifiés (commandes : `../.venv-test/bin/python -m pytest … -q`, `flake8`, `black --check`, `isort --check-only`, `mypy`).
