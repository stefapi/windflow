# STORY-122.4 : Application RBAC — organizations, users et protections d'escalade

**Statut :** DONE
**Story Parente :** STORY-122 — Dépendances RBAC `require_role(...)` — hiérarchie, cache TTL 300 s et protections d'escalade sur les ~110 endpoints (P1-2, application)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'administrateur sécurité de WindFlow, je veux que les 18 endpoints organizations (10) et users (8) soient protégés selon la matrice spec 08 (gestion des membres → Admin de l'organisation ; création d'organisation et gestion globale des utilisateurs → Super Admin), et que les protections anti-escalade soient effectives : le dernier superadmin n'est ni démotable ni désactivable, un Admin ne peut pas modifier un rôle supérieur ou égal au sien ni se promouvoir, et le rôle `super_admin` n'est pas attribuable via l'API d'organisations.

## Critères d'acceptation (AC)

- [x] AC 3 : **Protections d'escalade** : le **dernier superadmin** n'est ni démotable ni désactivable (`409`/`400` avec message explicite) ; un Admin ne peut pas modifier un rôle supérieur ou égal au sien ni se promouvoir ; le rôle `Super_Admin` n'est pas attribuable via l'API d'organisations (rôle système).
- [x] AC 2 (volet organizations/users) : Tous les endpoints organizations + users sont protégés conformément à la matrice spec 08 ; `super_admin` requis sur l'admin instance (création d'organisation…) ; admin → gestion `200` **dans son organisation**.

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-08) — marqueurs intérimaires « porté par STORY-122 » identifiés par grep.

**Couches impactées :** Backend uniquement — 2 routers + service utilisateurs + tests.

**Spécifications de référence :**
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — § Matrice : Organisations (Voir son org = tous ; Modifier = Admin+ ; **Créer = Super Admin uniquement**) ; Utilisateurs (Voir les membres = tous ; Ajouter/Retirer/Changer rôle = Admin+ dans l'org) ; § Sécurité du RBAC — **Protection contre l'escalade** (4 règles) ; § Gestion des utilisateurs (opérations via `/organizations/{id}/users`) ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Administration (Super Admin).

**Inventaire vérifié et rôles minimum cibles :**

**[`organizations.py`](../../backend/app/api/v1/organizations.py) — 10 routes :**

| # | Route (ligne) | Verbe | Rôle min actuel | Rôle cible | Note |
|---|---------------|-------|-----------------|-----------|------|
| 1 | `/` (l. 52→136) | GET | require_superuser | super_admin | Liste globale = admin instance |
| 2 | `/{organization_id}` (l. 171) | GET | (isolation) | viewer + isolation | Voir son org |
| 3 | `/` (l. 310) | POST | require_superuser | **super_admin** | Créer org (matrice) |
| 4 | `/{organization_id}` (l. 495) | PUT | require_superuser | admin (org) + isolation | Modifier son org |
| 5 | `/{organization_id}` (l. 711) | DELETE | require_superuser | super_admin | Suppression org = irréversible/global |
| 6 | `/bulk/delete` (l. 834) | POST | require_superuser | super_admin | Bulk global |
| 7 | l. 984 | GET | (à vérifier) | viewer + isolation | Détail/membres |
| 8 | `/{organization_id}/users` (l. 1136) | GET | get_current_active_user + isolation | viewer + isolation | Lister membres (121.2) |
| 9 | `/{organization_id}/users` (l. 1272) | POST | require_superuser + isolation | **admin (org)** + isolation | Ajouter membre — remplacement marqueur intérimaire |
| 10 | `/{organization_id}/users/{user_id}` PUT (l. 1473) / DELETE (l. 1617) | PUT/DELETE | require_superuser + isolation | **admin (org)** + isolation | Modifier rôle / retirer — remplacement marqueurs intérimaires |

**[`users.py`](../../backend/app/api/v1/users.py) — 8 routes :**

| # | Route (ligne) | Verbe | Rôle cible | Note |
|---|---------------|-------|-----------|------|
| 1 | `/` (l. 79) | GET | viewer (scopé org existant) | Répertoire users |
| 2 | `/{user_id}` (l. 204) | GET | viewer (isolation existante l. ~370) | |
| 3 | `/{user_id}` (l. 246) | GET | viewer | Variante (ex. by-username) |
| 4 | `/` (l. 376) | POST | **super_admin** | Création user = gestion instance |
| 5 | `/{user_id}` (l. 637) | PUT | **super_admin** | Modification user (rôles/flags) |
| 6 | `/{user_id}` (l. 884) | DELETE | **super_admin** | Suppression user |
| 7 | `/bulk/delete` (l. 1026) | POST | require_superuser → super_admin | Bulk |
| 8 | `/bulk/assign-organization` (l. 1120) | POST | require_superuser → super_admin | Bulk affectation org |

> Arbitrage : gestion des users via `/users/*` = administration d'instance → `super_admin` (aligné sur les marqueurs `require_superuser` existants l. 1081, 1166) ; la gestion des **membres d'une org** (rôles) passe par les endpoints n° 9-10 d'organizations → `admin` de l'org. Cohérent avec spec 08 § Gestion des utilisateurs (CLI `windflow admin user` = Super Admin requis).

**Protections d'escalade AC 3 — emplacements et mécanismes :**
- **`super_admin` non attribuable via API org** : déjà garanti structurellement (enum `Role` sans super_admin → 422 + `@validates` modèle, STORY-121.1/121.2) — **test comportemental à ajouter** (`PUT /organizations/{id}/users/{uid}` avec `role: "super_admin"` → 422) ;
- **Dernier superadmin** : `PUT /users/{id}` qui mettrait `is_superuser=False` ou `is_active=False`, et `DELETE /users/{id}` sur le **dernier** user avec `is_superuser=True` → comptage `select(User).where(is_superuser == True)` (helper `UserService.count_superadmins`) ; si count ≤ 1 et cible superadmin → `409 Conflict` avec message explicite (« Cannot demote/disable/delete the last superadmin ») ;
- **Admin d'org ne modifie pas un rôle ≥ au sien / ne se promeut** : dans `update_organization_member_role` — calcul du rôle de l'**acteur** via `AuthorizationService.get_role_in_organization` : si acteur non-superuser et (`Role(new_role) >= rôle acteur` ou `rôle cible actuel >= rôle acteur`) → `403` (« Cannot assign a role equal or higher than your own ») ; un admin peut donc promouvoir viewer→operator, jamais admin ni lui-même.

**Fichiers de référence (patterns vérifiés) :**
- Marqueurs intérimaires à remplacer : [`organizations.py`](../../backend/app/api/v1/organizations.py) l. 1273, 1474, 1618 (« Protection intérimaire : require_superuser — porté par STORY-122 ») ; docstrings « Interim protection » l. 1144, 1356, 1551 à réécrire en Access Control définitif ;
- Isolation `is_member` déjà posée sur les 4 endpoints membres (organizations.py l. 1300) — **devient le garde effectif** une fois `require_superuser` remplacé par `require_admin` (rôle global ≥ admin ne suffit plus : l'appartenance à l'org est vérifiée) ;
- [`UserOrganizationService`](../../backend/app/services/user_organization_service.py) : `get_membership` (l. 211), `update_member_role` (l. 240) ;
- [`AuthorizationService`](../../backend/app/services/authorization_service.py) (STORY-122.1) : `get_role_in_organization`, `invalidate_user_role_cache` (appeler aussi à la modification du rôle !) ;
- Hooks invalidation cache posés en 122.1 Tâche 4 — la Tâche 2 ci-dessous enrichit `update_member_role` du check d'escalade **avant** commit.

**Exigences sécurité identifiées (Phase 2.6) :**
- Auth : 401 sans token partout ;
- RBAC : hiérarchie + isolation par org + protections escalade (objet de la story) ;
- Validation : `role` borné enum (422, double barrière existante) ;
- Exposition : schémas Response membres sans `hashed_password`/`keycloak_id` (déjà en place 121.2) — tests de non-exposition conservés ;
- Audit : écritures membres déjà loggées (audit intérimaire) — ajouter `previous_role`/`new_role` aux logs d'escalade refusée (warning).

## Dépendances

- STORY-122.1 (socle + hooks invalidation). Parallélisable avec 122.2/122.3/122.5/122.6.

## Tâches d'implémentation détaillées

### Tâche 1 : Matrice `require_role` sur `organizations.py` (10 routes)
**Objectif :** Remplacer les dépendances intérimaires par la couverture RBAC finale, en distinguant admin d'organisation (membres/modification) et super_admin (création/suppression/liste globale).
**Fichiers :**
- `backend/app/api/v1/organizations.py` — Modifier :
  - Routes 1, 3, 5, 6 : `Depends(require_superuser)` → `Depends(require_super_admin)` (sémantique identique, nomenclature RBAC) ;
  - Route 4 (PUT org) : → `Depends(require_admin)` + **conserver** le check `is_member` existant (un admin global non-membre ne modifie pas l'org — sauf superuser) ;
  - Routes 8 (GET membres) : `require_viewer` + isolation `is_member` inchangée ;
  - Routes 9-10 (POST/PUT/DELETE membres) : `Depends(require_superuser)` → `Depends(require_admin)` ; l'isolation `is_member` (l. 1300) devient le garde effectif — **vérifier** que le bypass `current_user.is_superuser` reste le seul contournement (spécifié dans la docstring du service) ;
  - Réécrire les docstrings « Interim protection… STORY-122 » en section `## Access Control` définitive (« Requires admin role in the organization ; superusers bypass ») ;
  - Import `from ...auth.rbac import require_admin, require_super_admin, require_viewer` ;
  - Aucun changement de path/response_model/status.
**Exigences sécurité :** 401/403 par socle + isolation par org via `is_member` ; superuser bypass documenté.
**Dépend de :** STORY-122.1

### Tâche 2 : Protection d'escalade dans la gestion des membres
**Objectif :** Implémenter AC 3 volet membres : un Admin ne modifie pas un rôle ≥ au sien ni ne se promeut ; `super_admin` jamais attribuable.
**Fichiers :**
- `backend/app/api/v1/organizations.py` — Modifier — Dans `update_organization_member_role` (l. ~1473), après résolution du membership et **avant** `UserOrganizationService.update_member_role` :
  - Si `current_user` non-superuser : récupérer `actor_role = await AuthorizationService.get_role_in_organization(session, current_user, organization_id)` ; si `actor_role is None` → 403 (théoriquement déjà filtré par `is_member`, double garde) ; si `ROLE_HIERARCHY[new_role] >= ROLE_HIERARCHY[actor_role]` OU `ROLE_HIERARCHY[membership.role] >= ROLE_HIERARCHY[actor_role]` → 403 avec message explicite ; log warning `extra={"user_id", "target_user_id", "organization_id"}` ;
  - Docstring : règles d'escalade (spec 08 § Protection contre l'escalade) ;
  - Dans `add_organization_member` : si non-superuser et `data.role >= actor_role` → 403 (un admin ne peut ajouter qu'un viewer/operator) ;
- `backend/app/services/user_organization_service.py` — Modifier — Étendre la docstring `update_member_role`/`add_member` pour documenter que l'anti-escalade est vérifiée au niveau endpoint (le service reste intentionnellement neutre — il est aussi consommé par la seed/CLI admin).
**Exigences sécurité :** Anti-escalade = AC 3 ; jamais de `super_admin` en association (enum) — test comportemental requis.
**Dépend de :** Tâche 1, STORY-122.1

### Tâche 3 : Dernier superadmin indestructible (`users.py`)
**Objectif :** Implémenter AC 3 volet users : le dernier superadmin n'est ni démotable (`is_superuser=False`), ni désactivable (`is_active=False`), ni supprimable — 409 message explicite.
**Fichiers :**
- `backend/app/services/user_service.py` — Modifier — Ajouter `count_superadmins(db) -> int` : `select(func.count()).select_from(User).where(User.is_superuser == True)` (import `func` sqlalchemy — pattern services existants) ;
- `backend/app/api/v1/users.py` — Modifier —
  - `PUT /{user_id}` (l. ~637) : si cible est superadmin ET payload modifie `is_superuser`→False ou `is_active`→False ET `count_superadmins() <= 1` → `HTTPException(409, "Cannot demote or deactivate the last superadmin")` ;
  - `DELETE /{user_id}` (l. ~884) : si cible superadmin ET count ≤ 1 → 409 « Cannot delete the last superadmin » ;
  - Matrice RBAC des 8 routes (tableau ci-dessus) : GET → `require_viewer` (scoping existant conservé) ; POST/PUT/DELETE/bulk → `require_super_admin` (remplacement des 2 `require_superuser` l. 1081, 1166) ;
  - Log warning sur chaque 409 escalade avec `extra={"user_id", "target_user_id"}`.
**Exigences sécurité :** 409 (conflit logique) plutôt que 400 — AC 3 tolère 409/400, choisir 409 + message explicite ; pas de révélation du nombre de superadmins au-delà de « dernier ».
**Dépend de :** Tâche 1 (import rbac), STORY-122.1

### Tâche 4 : Tests matrice organizations/users + escalade (AC 3)
**Objectif :** Couvrir la matrice et toutes les protections d'escalade — le cœur sécuritaire de la story.
**Fichiers :**
- `backend/tests/unit/test_api/test_organizations_rbac.py` — Créer — viewer 200 `GET /organizations/{own}/users` + 403 org étrangère ; admin d'org A : 200 `POST/PUT/DELETE` membres **dans A**, 403 sur org B (isolation) ; operator 403 sur écritures membres ; superuser 200 partout ; création org : admin simple → 403, superuser → 201 ;
- `backend/tests/unit/test_api/test_users_rbac.py` — Créer — matrice users (viewer lectures scopées ; super_admin écritures ; operator/admin 403 écritures) ;
- `backend/tests/unit/test_api/test_rbac_escalation.py` — Créer — **AC 3 complet** :
  - `test_last_superadmin_cannot_be_demoted` (PUT is_superuser=False → 409) ;
  - `test_last_superadmin_cannot_be_deactivated` (PUT is_active=False → 409) ;
  - `test_last_superadmin_cannot_be_deleted` (DELETE → 409) ;
  - `test_penultimate_superadmin_demotable` (2 superadmins → PUT OK) ;
  - `test_admin_cannot_promote_to_admin_or_self` (admin A : PUT viewer→admin → 403 ; PUT propre rôle → 403) ;
  - `test_admin_cannot_modify_equal_or_higher_role` (admin A modifie un autre admin → 403) ;
  - `test_admin_can_promote_viewer_to_operator` (200) ;
  - `test_superadmin_role_not_assignable_via_members_api` (PUT/POST role=super_admin → 422) ;
  - `test_operator_cannot_manage_members_at_all` (403) ;
  - `test_role_change_invalidation_cache_effective` — après PUT rôle par superuser, l'utilisateur ciblé voit ses droits modifiés **immédiatement** sur un endpoint protégé (lien AC 1).
**Exigences sécurité :** Tests 401 (échantillon), 403, 404 (org/user inexistant), 409 escalade, 422 super_admin.
**Dépend de :** Tâches 1, 2, 3

## Tests à écrire

> Détail exhaustif en Tâche 4.

### Unitaires Backend
- `backend/tests/unit/test_api/test_organizations_rbac.py` — matrice organizations + isolation membres
- `backend/tests/unit/test_api/test_users_rbac.py` — matrice users
- `backend/tests/unit/test_api/test_rbac_escalation.py` — **AC 3** : dernier superadmin ×3, anti-promotion ×3, super_admin non attribuable, invalidation cache
- `backend/tests/unit/test_services/test_user_service.py` — Modifier — ajouter `test_count_superadmins` (0, 1, N)

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_api/test_organizations_rbac.py backend/tests/unit/test_api/test_users_rbac.py backend/tests/unit/test_api/test_rbac_escalation.py -v
poetry run pytest backend/tests/unit/test_api/test_organization_members.py backend/tests/unit/test_api/test_users.py -v  # non-régression 121.2
make backend-lint && make backend-typecheck
```

## État d'avancement technique
- [x] Tâche 1 : Matrice `require_role` sur organizations.py (10 routes, remplacement intérimaires)
- [x] Tâche 2 : Anti-escalade gestion membres (admin org)
- [x] Tâche 3 : Dernier superadmin indestructible + matrice users.py (8 routes)
- [x] Tâche 4 : Tests matrice + escalade (AC 3)
- [x] Lint & typecheck OK

## Notes d'implémentation

**Date :** 2026-09-11

### Fichiers modifiés/créés

**Backend (modifiés) :**
- `backend/app/api/v1/organizations.py` — Tâches 1+2 : matrice `require_role` sur les 10 routes (liste/création/suppression/bulk → `require_super_admin` ; PUT org + POST/PUT/DELETE membres → `require_admin` ; GET détail/membres → `get_current_active_user` + isolation `is_member` conservée) ; réécriture des docstrings OpenAPI « Interim protection » en sections `## Access Control` définitives ; **anti-escalade** dans `add_organization_member` (rôle attribué strictement < à celui de l'acteur + double garde non-admin) et `update_organization_member_role` (nouveau rôle ET rôle actuel de la cible strictement < à celui de l'acteur — couvre l'auto-promotion) avec logs warning d'audit ; import `ROLE_HIERARCHY` ; **ajout du check `is_member` sur PUT org** (divergence, voir ci-dessous).
- `backend/app/api/v1/users.py` — Tâche 3 : matrice sur les 8 routes (GET liste/détail → `require_viewer` avec scoping existant ; POST/PUT/DELETE/bulk ×2 → `require_super_admin`, remplacement des `require_superuser` l. 1081/1166) ; **protection dernier superadmin** : PUT démotant (`is_superuser=False`) ou désactivant (`is_active=False`) → 409 « Cannot demote or deactivate the last superadmin » ; DELETE → 409 « Cannot delete the last superadmin » (garde `count_superadmins() <= 1`) avec logs warning.
- `backend/app/services/user_service.py` — Tâche 3 : ajout `count_superadmins(db) -> int`.
- `backend/app/services/user_organization_service.py` — Tâche 2 : docstrings `add_member`/`update_member_role` documentant que l'anti-escalade est vérifiée au niveau endpoint (service intentionnellement neutre — consommé aussi par la seed/CLI admin).

**Tests (créés) :**
- `backend/tests/unit/test_api/test_organizations_rbac.py` — matrice organizations (GET membres viewer+isolation, écritures membres admin-dans-son-org / operator-403 / isolation org B, admin instance super_admin only, PUT org, 401 ×4, 404).
- `backend/tests/unit/test_api/test_users_rbac.py` — matrice users (lectures viewer scopées, écritures super_admin only, operator/admin 403, 401 ×4, 404 ×2).
- `backend/tests/unit/test_api/test_rbac_escalation.py` — **AC 3 complet** (dernier superadmin ×3 + avant-dernier démotable ; anti-promotion admin ×6 dont viewer→operator autorisé ; super_admin non attribuable ×2 (422) ; operator 403 ; invalidation cache effective).
- `backend/tests/unit/test_services/test_user_service.py` — créé (n'existait pas) : `test_count_superadmins` 0/1/N.

### Décisions techniques
- **409 Conflict** retenu pour les protections dernier superadmin (AC 3 tolérait 409/400) — message explicite sans révéler le nombre de superadmins au-delà de « dernier » ;
- **Anti-escalade au niveau endpoint** (pas dans `UserOrganizationService`) : le service reste consommable par la seed/CLI admin qui a légitimement besoin d'attribuer n'importe quel rôle ;
- **Double condition dans `update_member_role`** (`new_role >= actor` OU `current_target_role >= actor`) : la seconde couvre structurellement l'auto-promotion (le propre rôle de l'acteur est ≥ à lui-même) ;
- **Garde non-admin dans `add_organization_member`** : vérifie `actor_role >= admin` en plus de `is_member` (défense-en-profondeur).

### Divergences par rapport à l'analyse
- **Tâche 1 (route 4 PUT org)** : la story disait « conserver le check `is_member` existant » mais il n'existait pas sur cette route. Solution minimale : **ajout** du check (même pattern que GET /{organization_id}) — sans lui, `require_admin` aurait laissé tout admin global modifier n'importe quelle org ;
- **Tâche 4 (`test_last_superadmin_cannot_be_deleted`)** : l'auto-suppression du dernier superadmin reçoit **409** (garde count) — comportement observé, conforme AC 3 ; test avec contrôle négatif (avant-dernier supprimable quand count=2) et vérification d'intégrité du compte. Un acteur distinct est structurellement impossible à monter (tout superadmin supplémentaire fait remonter count) ;
- **`test_user_service.py`** : listé « Modifier » mais inexistant → créé.

### Difficultés rencontrées
- Erreurs IDE transitoires (« Could NOT open editor ») lors des apply_diff sur organizations.py — contourné via scripts Python `str.replace` avec assertions d'unicité ;
- Venv Poetry principal cassé (alembic introuvable, Python 3.14) — tests lancés avec `.venv-test` (Python 3.11.10), pattern établi en 122.3 ;
- 6 échecs **préexistants** dans la non-régression (`test_auth_isolation` ×2, `test_debug_story1033` ×1, `test_users` ×3 — « No superadmin user found in development mode »), vérifiés identiques via `git stash` : indépendants de la story.

### Tests et validation (résultats chiffrés)
- 4 nouveaux fichiers + non-régression `test_organization_members.py` : **87 passed** (`.venv-test/bin/python -m pytest …`) ;
- Non-régression élargie `test_api/` + `test_auth/` + services liés : **259 passed / 6 failed préexistants** ;
- Lint : flake8 + black + isort **OK** sur les 8 fichiers touchés ; mypy : **0 erreur** sur les 4 fichiers backend (21 erreurs préexistantes dans des modules tiers importés transitivement — plugin_lifecycle, targets/connectivity, stats — hors périmètre).
