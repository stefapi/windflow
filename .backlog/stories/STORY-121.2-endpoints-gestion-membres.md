# STORY-121.2 : Endpoints de gestion des membres d'une organisation

**Statut :** DONE
**Story Parente :** STORY-121 — Modèle `user_organizations` — association utilisateur ↔ organisation avec rôle (P1-2, partie modèle)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'administrateur WindFlow, je veux pouvoir **gérer les membres** d'une organisation via l'API REST (spec 09 § Organisations) : lister les membres (rôle + `joined_at`), ajouter un membre (rôle par défaut `viewer`), modifier le rôle d'un membre et retirer un membre — ces opérations étant protégées par l'authentification, l'isolation cross-organisation et la dépendance la plus forte disponible (`require_superuser` en intérim, la couverture RBAC finale `require_role(...)` étant portée par STORY-122).

Cette sous-story est la deuxième étape de STORY-121 : elle expose et sécurise la table `user_organizations` créée par STORY-121.1. Elle ne modifie pas les lectures existantes `current_user.organization_id` (bascule portée par STORY-121.3).

## Critères d'acceptation (AC)

- [x] AC 3 : Endpoints de gestion des membres opérationnels conformément à spec 09 : lister les membres (rôle + joined_at), ajouter un membre (rôle défaut `viewer`), modifier le rôle, retirer un membre — protégés a minima par l'authentification + la dépendance la plus forte disponible (cf. contexte), la couverture RBAC finale étant vérifiée par STORY-122.
- [x] AC 4 : Tests de sécurité : `401` sans token sur les endpoints membres ; `403` pour un rôle insuffisant ; `422` sur rôle invalide dans le body ; un utilisateur ne peut pas lister/modifier les membres d'une organisation à laquelle il n'appartient pas.

## Contexte technique

> Analyse réalisée par `analyse-story` (2026-09-07) — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches.

**Couches impactées :** Backend uniquement — schémas Pydantic, services, endpoints API, tests backend (unitaires). **Aucun** modèle/migration (STORY-121.1), **aucune** bascule des lectures existantes `current_user.organization_id` (STORY-121.3), aucun impact frontend/CLI.

**Spécifications de référence :**
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Organisations : `GET /{id}/users`, `POST /{id}/users`, `PUT /{id}/users/{user_id}` (changement de rôle), `DELETE /{id}/users/{user_id}` — rôle défaut `viewer` à l'ajout. Le router est déjà monté sous `/api/v1/organizations` ([`backend/app/api/v1/__init__.py`](../../backend/app/api/v1/__init__.py)) → les chemins relatifs du router sont `/{organization_id}/users` et `/{organization_id}/users/{user_id}` ;
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — § Matrice des permissions (Voir les membres = tous rôles ; Ajouter/Retirer/Changer rôle = Admin+ et Super_Admin), § Sécurité du RBAC (audit des modifications de permissions, protection contre l'escalade).

**Fichiers de référence (patterns vérifiés) :**
- Schémas Pydantic ConfigDict + `json_schema_extra` examples → [`backend/app/schemas/organization.py`](../../backend/app/schemas/organization.py) ;
- Service statique async (select/commit/refresh, conversions `str(...)` des UUID) → [`backend/app/services/organization_service.py`](../../backend/app/services/organization_service.py) ; lecture user → [`backend/app/services/user_service.py`](../../backend/app/services/user_service.py) (`get_by_id`) ;
- Endpoints documentés (summary/description/responses avec examples, `conditional_rate_limiter(n, 60)`, `correlation_id` via `request.state`, logs `extra={...}`, pattern isolation 403 de `get_organization`) → [`backend/app/api/v1/organizations.py`](../../backend/app/api/v1/organizations.py) ;
- Dépendances auth disponibles et vérifiées → [`backend/app/auth/dependencies.py`](../../backend/app/auth/dependencies.py) : `get_current_active_user` (l. 92), `require_superuser` (l. 114, 403 « Not enough permissions ») ;
- Fixtures tests → [`backend/tests/conftest.py`](../../backend/tests/conftest.py) : `db_session`, `test_organization`, `test_user` (non-superuser, `organization_id=test_organization.id`), `test_superuser`, `authenticated_client`, `admin_client`. Le schéma de test provient des migrations (`_migrated_schema_template`) → la table `user_organizations` (STORY-121.1) y sera présente **automatiquement** ;
- Pattern tests API sécurité (seed direct en session, classes de test) → [`backend/tests/unit/test_api/test_deployments.py`](../../backend/tests/unit/test_api/test_deployments.py).

**Décisions d'analyse :**
- **⚠️ STORY-121.1 non encore implémentée** (grep `UserOrganization`/`user_organizations`/`enums.rbac` = 0 résultat au 2026-09-07) : les tâches importent `from ..enums.rbac import Role` et `from ..models.user_organization import UserOrganization` — **implémenter STORY-121.1 d'abord** ;
- **Isolation cross-org via helper service** `UserOrganizationService.is_member(db, user, organization_id)` : appartenance = ligne dans `user_organizations` **OU** (fallback intérim) colonne héritée `user.organization_id`. Sans ce fallback, la table étant vide avant la migration de données (STORY-121.3), aucun utilisateur existant ne serait considéré membre — l'isolation serait inopérante. Le fallback sera retiré par STORY-121.3. **Le superuser bypass l'isolation** (pattern existant `get_organization` l. 282 ; spec 08 : le Super Admin a tous les droits) ;
- **Schéma membre dédié** : ne **pas** réutiliser [`UserResponse`](../../backend/app/schemas/user.py) (il expose `keycloak_id`, interdit ici) — `OrganizationMemberResponse` n'expose que `user_id`, `username`, `email`, `full_name`, `role`, `joined_at` (`hashed_password` jamais inclus) ;
- **Bornage `role` double barrière** : enum `Role` dans les schémas Pydantic (422 immédiat — `super_admin` structurellement impossible, anti-escalade) + `@validates("role")` modèle (STORY-121.1) ;
- **Erreurs via `HTTPException`** (pattern actuel du router ; [`backend/app/core/exceptions.py`](../../backend/app/core/exceptions.py) est minimal — hiérarchie complète portée par STORY-127) ;
- **Liste membres avec `skip`/`limit`** (défauts 0/100, pattern `list_organizations` — pagination exigée par `.roo/rules/20-architecture-and-api.md` pour les listes > 20) ; pas d'enveloppe paginée (harmonisation `pagination{}` portée par STORY-126/128) ;
- **Statuts de retour** : GET 200 · POST 201 · PUT 200 · DELETE 204 ; erreurs 401 (auth), 403 (rôle insuffisant / isolation cross-org), 404 (org, user ou membre introuvable), 409 (déjà membre), 422 (body invalide dont `role` hors enum) ;
- Divergence connue confirmée : `backend/app/helper/permissions.py` = code mort à **ignorer**.

**Exigences sécurité identifiées (Phase 2.6) :**
- **Auth :** oui — `get_current_active_user` sur `GET /{id}/users` ; `require_superuser` sur POST/PUT/DELETE (intérim ; RBAC finale `require_role("admin")` portée par STORY-122) ; 401 sans token sur les 4 ;
- **RBAC / isolation :** lecture des membres = tous rôles (membres de l'org) ; écritures = Admin+ (intérim superuser) ; **isolation cross-organisation sur les 4 endpoints** (403 si l'utilisateur n'appartient pas à l'org ciblée ; superuser bypass) — le check est posé dès maintenant sur les écritures (no-op intérim derrière `require_superuser`, mais structure prête : STORY-122 n'aura qu'à remplacer la dépendance pour que l'isolation devienne le garde effectif des admins d'org) ;
- **Validation :** `user_id`/`organization_id` typés `UUID` (422 si format invalide) ; `role` borné à `{viewer, operator, admin}` via enum Pydantic (422 sinon) ;
- **Exposition :** réponses membres **sans** `hashed_password` ni `keycloak_id` (schéma dédié) ; aucun secret/token loggé ;
- **Audit :** ajout / changement de rôle / retrait de membre = actions critiques (spec 08 § Audit des permissions) → logs structurés avec `correlation_id`, `user_id` (acteur), `organization_id`, `target_user_id`, `role` — la table `audit_logs` étant portée par STORY-125, ces logs constituent la traçabilité intérimaire ;
- **Escalade :** l'enum sans `super_admin` interdit le stockage d'un rôle système en association ; protections « dernier superadmin » / non-promotion portées par STORY-122 (le retrait d'une association ne touche jamais `User.is_superuser`).

## Dépendances

- STORY-121.1 : Enum `Role`, modèle `UserOrganization` et migration de création de table.
- La couverture RBAC finale (`require_role`) de ces endpoints est portée par STORY-122 (postérieur).

## Périmètre indicatif (répartition des tâches identifiées par l'analyse de STORY-121)

| # | Tâche (issue de l'analyse STORY-121) | Périmètre de cette sous-story |
|---|--------------------------------------|-------------------------------|
| T5 | Schémas Pydantic membres (Request/Response, exclusion champs sensibles) | ✅ Complet |
| T6 | Service `UserOrganizationService` (statique async, patterns services existants) | ✅ Complet |
| T7 | 4 endpoints API de gestion des membres (`GET/POST /organizations/{id}/users`, `PUT/DELETE /organizations/{id}/users/{user_id}`) | ✅ Complet |
| T8 | Tests | 🔶 Partie : tests service + tests API sécurité (401/403/422, isolation cross-org) |

**Hors périmètre :** enum/modèle/migration de table (STORY-121.1) ; migration des données, bascule des ~30 consommateurs `current_user.organization_id`, retrait/relégation de la colonne, JWT, seed, non-régression globale (STORY-121.3).

## Tâches d'implémentation détaillées

> Exécuter dans l'ordre (API-first : schemas → service → endpoints → tests, cf. `.roo/rules/20-architecture-and-api.md`). Références : `.roo/rules/30-code-standards.md` (conventions), `.roo/rules/40-security.md` (checklist sécurité), `.roo/rules/55-project-structure.md` (chemins). **Prérequis : STORY-121.1 implémentée** (enum `Role` + modèle `UserOrganization`).

### Tâche 1 : Schémas Pydantic membres (Request/Response)
**Objectif :** Créer les schémas Pydantic de validation I/O des endpoints membres, avec bornage `role` par l'enum `Role` (STORY-121.1) et exclusion structurelle des champs sensibles.
**Fichiers :**
- `backend/app/schemas/organization_member.py` — Créer — Nouveau module (pattern : `backend/app/schemas/organization.py` — ConfigDict + `json_schema_extra` examples sur chaque modèle). Définir :
  - `OrganizationMemberAddRequest(BaseModel)` : `user_id: UUID` (champ requis, description « ID de l'utilisateur à ajouter », example UUID) ; `role: Role = Field(default=Role.VIEWER, description=...)` avec import `from ..enums.rbac import Role` — toute valeur hors `{viewer, operator, admin}` (dont `super_admin`) → **422 Pydantic** ;
  - `MemberRoleUpdateRequest(BaseModel)` : `role: Role` **requis** (borné enum, 422 sinon) ;
  - `OrganizationMemberResponse(BaseModel)` avec `model_config = ConfigDict(from_attributes=True, ...)` et example complet : `user_id: str`, `username: str`, `email: str`, `full_name: Optional[str]`, `role: Role`, `joined_at: datetime`. **Champs sensibles interdits** : ne déclarer ni `hashed_password` ni `keycloak_id` (ni aucun champ password/token) — la whitelist stricte de champs garantit l'exclusion (ne pas réutiliser `UserResponse` qui expose `keycloak_id`) ;
  - Docstrings en tête de module et par classe (rôle par défaut `viewer` à l'ajout, spec 09 § Organisations).
**Exigences sécurité :** Validation `role` bornée enum (422, anti-escalade : `super_admin` structurellement impossible) ; `user_id: UUID` (422 si format invalide) ; schéma Response en whitelist — `hashed_password`/`keycloak_id` absents par construction.
**Dépend de :** STORY-121.1 (enum `Role`) — tâches 1-2 de la sous-story sœur.

### Tâche 2 : Service `UserOrganizationService`
**Objectif :** Créer le service métier CRUD des associations `user_organizations` + le helper d'isolation cross-organisation, en suivant le pattern des services statiques async existants.
**Fichiers :**
- `backend/app/services/user_organization_service.py` — Créer — Nouveau service (pattern : `backend/app/services/organization_service.py` — classe à méthodes `@staticmethod async`, conversions `str(...)` des UUID car les modèles stockent `String(36)`, `db.commit()`/`db.refresh()` après écriture). Classe `UserOrganizationService` :
  - `is_member(db: AsyncSession, user: User, organization_id: Union[UUID, str]) -> bool` — **isolation cross-org** : `True` si `user.is_superuser` (bypass, pattern `get_organization` de `organizations.py` l. 282) ; sinon `True` s'il existe une ligne `UserOrganization` pour `(user.id, str(organization_id))`, **ou** (fallback intérim) si `user.organization_id == str(organization_id)` — commentaire explicite : fallback à retirer par STORY-121.3 une fois les données migrées et les lectures basculées ;
  - `list_members(db: AsyncSession, organization_id: Union[UUID, str], skip: int = 0, limit: int = 100) -> List[UserOrganization]` — `select(UserOrganization).where(UserOrganization.organization_id == str(...)).options(selectinload(UserOrganization.user)).order_by(UserOrganization.joined_at).offset(skip).limit(limit)` (import `selectinload` de `sqlalchemy.orm`) — chaque ligne porte sa relation `user` chargée pour la réponse ;
  - `add_member(db: AsyncSession, organization_id: Union[UUID, str], data: OrganizationMemberAddRequest) -> UserOrganization` — lève `ValueError` si l'utilisateur cible n'existe pas (`UserService.get_by_id`, import depuis `..services.user_service`) ou est déjà membre (mappés 404/409 par l'endpoint) ; sinon `db.add(UserOrganization(user_id=str(data.user_id), organization_id=str(organization_id), role=data.role))` + commit/refresh, retour du lien créé (défaut `viewer` géré par le schéma) ;
  - `get_membership(db: AsyncSession, organization_id: Union[UUID, str], user_id: Union[UUID, str]) -> Optional[UserOrganization]` — lookup par PK composite (`user_id == str(...)` ET `organization_id == str(...)`) avec `selectinload(UserOrganization.user)` ;
  - `update_member_role(db: AsyncSession, membership: UserOrganization, role: Role) -> UserOrganization` — `membership.role = role` + commit/refresh + retour ;
  - `remove_member(db: AsyncSession, membership: UserOrganization) -> None` — `db.delete(membership)` + commit ;
  - Docstring module : table et enum fournis par STORY-121.1 ; le rôle système `super_admin` ne peut jamais être stocké (enum + `@validates` modèle).
**Exigences sécurité :** Aucune donnée sensible manipulée ni loggée ; `is_member` est la garde d'isolation consommée par les 4 endpoints ; `add_member` ne peut créer que des rôles bornés (type `Role` + `@validates` modèle en double barrière).
**Dépend de :** Tâche 1 (schéma `OrganizationMemberAddRequest`), STORY-121.1 (modèle `UserOrganization`).

### Tâche 3 : 4 endpoints API de gestion des membres
**Objectif :** Exposer les 4 endpoints spec 09 § Organisations dans le router existant, avec auth, protection intérimaire `require_superuser`, isolation cross-org, documentation OpenAPI complète et rate limiting.
**Fichiers :**
- `backend/app/api/v1/organizations.py` — Modifier — Ajouter au router existant (pattern des 6 endpoints actuels : `summary`/`description` détaillés avec section `## Access Control`, `responses={...}` avec examples JSON par code, `dependencies=[Depends(conditional_rate_limiter(n, 60))]`, extraction `correlation_id = getattr(request.state, "correlation_id", None)`, logs `logger.info(..., extra={...})`). Imports à ajouter : les 3 schémas depuis `...schemas.organization_member` ; `UserOrganizationService` depuis `...services.user_organization_service` ; `UserService` depuis `...services.user_service` :
  - **`GET /{organization_id}/users`** (`list_organization_members`) — `response_model=List[OrganizationMemberResponse]`, 200 ; rate limiter `(60, 60)` ; `current_user: User = Depends(get_current_active_user)` ; query params `skip: int = 0, limit: int = 100` ; **isolation avant toute lecture** : `if not current_user.is_superuser and not await UserOrganizationService.is_member(session, current_user, organization_id): raise HTTPException(403, "Accès refusé à cette organisation")` ; 404 si `OrganizationService.get_by_id` retourne `None` ; mappe chaque `UserOrganization` vers `OrganizationMemberResponse(user_id=link.user_id, username=link.user.username, email=link.user.email, full_name=link.user.full_name, role=link.role, joined_at=link.joined_at)` ; responses 200/401/403/404/429/500 ;
  - **`POST /{organization_id}/users`** (`add_organization_member`) — `response_model=OrganizationMemberResponse`, **201** ; rate limiter `(10, 60)` ; `current_user: User = Depends(require_superuser)` (intérim — remplacé par `require_role("admin")` en STORY-122) + même check d'isolation `is_member` (structure prête pour les admins d'org post-122) ; 404 org inexistante ; 404 utilisateur cible introuvable (check explicite via `UserService.get_by_id` ou mapping de la `ValueError` du service) ; **409** si déjà membre ; log d'audit intérimaire : `logger.info("Member added", extra={"correlation_id": ..., "user_id": str(current_user.id), "organization_id": str(organization_id), "target_user_id": str(member_data.user_id), "role": member_data.role.value})` ; responses 201/401/403/404/409/422/429/500 + `openapi_extra` requestBody examples (rôle `viewer` par défaut / rôle explicite `operator`) ;
  - **`PUT /{organization_id}/users/{user_id}`** (`update_organization_member_role`) — `response_model=OrganizationMemberResponse`, 200 ; rate limiter `(20, 60)` ; `Depends(require_superuser)` + isolation `is_member` ; `user_id: UUID` path param ; body `MemberRoleUpdateRequest` (**422** automatique si `role` hors enum) ; 404 org ou membership introuvable (`get_membership` → `None`) ; log d'audit intérimaire avec ancien/nouveau rôle (`previous_role`, `new_role`) ; responses 200/401/403/404/422/429/500 ;
  - **`DELETE /{organization_id}/users/{user_id}`** (`remove_organization_member`) — **204** sans corps ; rate limiter `(10, 60)` ; `Depends(require_superuser)` + isolation `is_member` ; `user_id: UUID` ; 404 org ou membership introuvable ; log d'audit intérimaire `"Member removed"` avec contexte ; responses 204/401/403/404/429/500 ;
  - Docstrings complètes par fonction (Args/Returns/Raises, pattern existant) ; descriptions OpenAPI mentionnant la protection intérimaire superuser et le renforcement prévu (RBAC STORY-122). ⚠️ Ordre de déclaration dans le fichier : routes statiques (`/bulk/delete`) et `/` d'abord, puis `/{organization_id}/...` — FastAPI matche par ordre, `/{organization_id}/users` doit être déclaré après `/{organization_id}` (pas de conflit : chemins distincts).
**Exigences sécurité :** `get_current_active_user` minimum partout (401 sans token via `oauth2_scheme`) ; `require_superuser` sur les 3 écritures (403 sinon) ; **isolation cross-org sur les 4** (403, superuser bypass) ; 422 par validation Pydantic UUID + enum `role` ; aucune donnée sensible dans les logs ; audit logs sur les 3 écritures.
**Dépend de :** Tâches 1 et 2.

### Tâche 4 : Tests service + tests API sécurité
**Objectif :** Couvrir le service (nominal + erreurs) et les 4 endpoints (nominal + **sécurité 401/403/404/409/422 + isolation cross-org + exclusion champs sensibles**) — couverture AC 3 (fonctionnel) et AC 4 (sécurité).
**Fichiers :**
- `backend/tests/unit/test_services/test_user_organization_service.py` — Créer — Tests du service avec fixtures conftest `db_session`, `test_user`, `test_superuser`, `test_organization` (détail en section « Tests à écrire ») ;
- `backend/tests/unit/test_api/test_organization_members.py` — Créer — Tests des 4 endpoints avec fixtures `client` (401), `authenticated_client` (403 non-superuser), `admin_client` (nominal) + seeds directs en session (pattern `test_deployments.py`) : création d'une **organisation étrangère** `other_org` + utilisateur externe pour l'isolation cross-org, lignes `UserOrganization` insérées directement en `db_session` ;
- Pas de fichier d'intégration dédié : le schéma de test provient déjà des migrations (conftest `_migrated_schema_template`), les tests API ci-dessus couvrent le chemin HTTP + DB réelle.
**Exigences sécurité :** Tests sécurité obligatoires (`.roo/rules/40-security.md`) : 401 sans token ×4 endpoints, 403 rôle insuffisant (non-superuser sur écritures), 403 isolation cross-org, 422 `role` invalide (dont `super_admin`), absence `hashed_password`/`keycloak_id` dans les réponses.
**Dépend de :** Tâches 1, 2, 3.

## Tests à écrire

> Patterns détaillés : `.roo/rules/35-testing-quality-gates.md` · Tests sécurité obligatoires : `.roo/rules/40-security.md`

### Unitaires Backend — service

- `backend/tests/unit/test_services/test_user_organization_service.py` — Créer (fixtures `db_session`, `test_user`, `test_superuser`, `test_organization`) :
  - `test_is_member_true_via_association` — cas nominal : ligne `UserOrganization` créée en session → `is_member` True ;
  - `test_is_member_true_via_legacy_column_fallback` — **intérim** : aucune ligne en table mais `test_user.organization_id == org.id` → True (comportement pré-121.3) ;
  - `test_is_member_false_for_foreign_user` — cas d'erreur : utilisateur d'une autre org → False ;
  - `test_is_member_superuser_bypass` — sécurité : `test_superuser` sans aucune appartenance → True ;
  - `test_add_member_defaults_to_viewer` — cas nominal : `add_member` sans rôle → `role == Role.VIEWER` ;
  - `test_add_member_with_explicit_role` — cas nominal : rôle `operator` explicite persisté ;
  - `test_add_member_unknown_user_raises` — cas d'erreur : `user_id` inexistant → `ValueError` ;
  - `test_add_member_duplicate_raises` — cas d'erreur : membre déjà présent → `ValueError`/`IntegrityError` (409 côté API) ;
  - `test_list_members_returns_links_with_user_loaded` — cas nominal : membres retournés ordonnés par `joined_at`, relation `user` accessible sans requête supplémentaire ;
  - `test_list_members_pagination` — `skip`/`limit` respectés ;
  - `test_get_membership_by_composite_pk` — found / `None` si autre org ou autre user ;
  - `test_update_member_role_persists` — cas nominal : changement `viewer` → `admin` persisté ;
  - `test_remove_member_deletes_row` — cas nominal : ligne supprimée, `get_membership` → `None` après.

### Unitaires Backend — API (nominal + sécurité)

- `backend/tests/unit/test_api/test_organization_members.py` — Créer (fixtures `client`/`authenticated_client`/`admin_client`, seeds `UserOrganization` directs en `db_session`, organisation étrangère `other_org` + utilisateur externe pour l'isolation) :
  - **GET liste** : `test_list_members_returns_members_with_role_and_joined_at` (200, champs `role` + `joined_at` présents) ; `test_list_members_empty_organization` (200, `[]`) ; `test_list_members_returns_401_without_token` — **sécurité** ; `test_list_members_returns_403_for_non_member` — **sécurité isolation** (`authenticated_client`, user non membre de `other_org`, non superuser) ; `test_list_members_superuser_can_list_any_organization` (200 sur `other_org`) ; `test_list_members_returns_404_unknown_organization` ;
  - **POST ajout** : `test_add_member_creates_with_default_viewer_role` (201, `role == "viewer"`) ; `test_add_member_with_explicit_role` (201, `role == "operator"`) ; `test_add_member_returns_401_without_token` — **sécurité** ; `test_add_member_returns_403_for_non_superuser` — **sécurité RBAC intérim** (`authenticated_client` = user standard) ; `test_add_member_returns_403_for_foreign_organization` — **sécurité isolation** ; `test_add_member_returns_404_unknown_user` ; `test_add_member_returns_409_when_already_member` ; `test_add_member_returns_422_on_invalid_role` — **sécurité anti-escalade** : body `{"user_id": ..., "role": "super_admin"}` → 422 (idem `"hacker"`) ; `test_add_member_returns_422_on_invalid_user_id_format` ;
  - **PUT rôle** : `test_update_member_role_changes_role` (200, nouveau rôle retourné) ; `test_update_member_role_returns_401_without_token` — **sécurité** ; `test_update_member_role_returns_403_for_non_superuser` — **sécurité** ; `test_update_member_role_returns_403_for_foreign_organization` — **sécurité isolation** ; `test_update_member_role_returns_404_when_not_member` ; `test_update_member_role_returns_422_on_invalid_role` — **sécurité** (`"super_admin"` → 422) ; `test_update_member_role_returns_422_on_missing_role` ;
  - **DELETE retrait** : `test_remove_member_returns_204_and_deletes` (204, membership supprimé en base) ; `test_remove_member_returns_401_without_token` — **sécurité** ; `test_remove_member_returns_403_for_non_superuser` — **sécurité** ; `test_remove_member_returns_403_for_foreign_organization` — **sécurité isolation** ; `test_remove_member_returns_404_when_not_member` ;
  - **Exposition** (transverse) : `test_members_responses_do_not_expose_sensitive_fields` — **sécurité** : aucune réponse (liste/ajout/update) ne contient `hashed_password` ni `keycloak_id` (assertions `not in` sur le JSON sérialisé) ;
  - ⚠️ Note : l'utilisateur cible ajouté via POST doit exister en base (créé en session via `UserService.create`) ; le retrait d'un membre via DELETE ne modifie jamais `User.is_superuser` (protections « dernier superadmin » / non-promotion portées par STORY-122).

### Commandes de validation

```bash
# Tests ciblés (voir Makefile — source de vérité)
poetry run pytest backend/tests/unit/test_services/test_user_organization_service.py -v
poetry run pytest backend/tests/unit/test_api/test_organization_members.py -v --tb=short

# Non-régression + qualité
make backend-test-all
make backend-lint
make backend-typecheck
```

## État d'avancement technique

- [x] Tâche 1 : Schémas Pydantic membres (`backend/app/schemas/organization_member.py`)
- [x] Tâche 2 : Service `UserOrganizationService` (`backend/app/services/user_organization_service.py`)
- [x] Tâche 3 : 4 endpoints API membres + protections (auth, `require_superuser` intérim, isolation cross-org)
- [x] Tâche 4 : Tests service + tests sécurité API (401/403/404/409/422, isolation, champs sensibles)
- [x] Tests non-régression backend complets verts (`make backend-test-all`) — validé via `.venv-test` (Poetry cassé) : 42 échecs unit + 20 intégration **pré-existants** (référence 121.1, listes identiques), **aucun nouvel échec**, aucun sur les fichiers 121.2
- [x] Lint + typecheck OK (`make backend-lint` + `make backend-typecheck`) — validé via `.venv-test` : isort/black/flake8/ruff/bandit ✅ ; mypy : 0 erreur sur les fichiers 121.2 (5 erreurs d'environnement sur fichiers tiers transitifs, pré-existantes)

## Notes d'implémentation

**Date :** 2026-09-08

### Fichiers modifiés/créés
- `backend/app/schemas/organization_member.py` : **créé** — schémas `OrganizationMemberAddRequest` (rôle défaut `viewer`), `MemberRoleUpdateRequest`, `OrganizationMemberResponse` (whitelist stricte, ConfigDict + examples OpenAPI)
- `backend/app/services/user_organization_service.py` : **créé** — service statique async : `is_member` (bypass superuser + fallback intérim `user.organization_id`, commenté pour retrait STORY-121.3), `list_members` (pagination + `selectinload`), `add_member`, `get_membership`, `update_member_role`, `remove_member`
- `backend/app/api/v1/organizations.py` : **modifié** — imports ajoutés ; helpers module `_role_str`/`_member_to_response` ; 4 endpoints `GET/POST /{organization_id}/users` (200/201), `PUT/DELETE /{organization_id}/users/{user_id}` (200/204) avec isolation 403, rate limiting, OpenAPI riche, logs d'audit intérimaires (`correlation_id`, acteur, cible, rôles)
- `backend/tests/unit/test_services/test_user_organization_service.py` : **créé** — 13 tests (couverture service 100 %)
- `backend/tests/unit/test_api/test_organization_members.py` : **créé** — 29 tests dont ~22 sécurité

### Décisions techniques
- Fixture `auth_enabled` (autouse, `monkeypatch.setattr(settings, "disable_auth", False)`) sur le module de tests API : pattern projet (`test_plugins.py`, `test_compute_api.py`) — sans elle, `get_current_user` en mode dev cherche un superadmin en base → 500 au lieu de 401/403
- `add_organization_member` : check explicite `UserService.get_by_id` (404 utilisateur) **avant** l'appel service, puis mapping `ValueError` → 409 — sépare clairement 404/409
- Helpers privés `_role_str` (enum ou str stockée) et `_member_to_response` (mapping whitelist) factorisés hors des 4 endpoints (DRY)
- Test `test_add_member_returns_403_for_foreign_organization` : avec `require_superuser` intérim, un non-superuser reçoit 403 (RBAC) avant même le check d'isolation — les deux gardes convergent vers 403 ; complété par `test_add_member_superuser_can_add_to_foreign_organization` documentant le bypass superuser

### Divergences par rapport à l'analyse
- Aucune divergence fonctionnelle. Aménagements mineurs : (1) scission du test « 403 foreign org » POST en deux tests (isolation 403 + bypass superuser 201) pour refléter fidèlement le comportement intérim ; (2) lignes de validation de l'état d'avancement annotées avec le contournement `.venv-test` (Poetry cassé, cf. STORY-121.1)

### Difficultés rencontrées
- 11 échecs initiaux des tests API (500 au lieu de 401/403) : cause racine `DISABLE_AUTH=true` en environnement de test → résolu via fixture `auth_enabled` (pattern existant, aucune modification du code applicatif)
- mypy/bandit absents du venv de test → installés localement dans `.venv-test` pour la validation ; mypy : 0 erreur sur les fichiers 121.2 (5 erreurs pré-existantes d'environnement sur fichiers tiers transitifs : stubs yaml, imports)

### Tests ajoutés
- `backend/tests/unit/test_services/test_user_organization_service.py` : 13/13 passés — couverture `user_organization_service.py` **100 %**
- `backend/tests/unit/test_api/test_organization_members.py` : 29/29 passés (GET×6, POST×10, PUT×7, DELETE×5, exposition champs sensibles×1) dont sécurité : 401 ×4, 403 RBAC ×3, 403 isolation ×4, 422 `super_admin`/rôle invalide ×3, 404 ×4, 409 ×1, exclusion `hashed_password`/`keycloak_id` ×1
- Non-régression : unit 1029 passed / 42 failed pré-existants ; intégration 58 passed / 20 failed pré-existants — listes identiques à la référence STORY-121.1, **aucun nouvel échec**
