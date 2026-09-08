# STORY-121.3 : Migration des données, bascule des lectures vers l'association et retrait de la colonne héritée

**Statut :** DONE
**Story Parente :** STORY-121 — Modèle `user_organizations` — association utilisateur ↔ organisation avec rôle (P1-2, partie modèle)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'administrateur WindFlow, je veux que l'appartenance actuelle des utilisateurs (FK directe `users.organization_id`) soit **migrée sans perte** vers la table d'association `user_organizations` (mapping non cassant : superuser → Super_Admin via flag inchangé ; autres utilisateurs actifs → `operator`), que toutes les lectures backend soient **basculées** sur l'association, et que la colonne héritée `users.organization_id` soit retirée (ou reléguée en simple valeur par défaut) — sans casser login/register/seed ni les ~30 fichiers consommateurs.

Cette sous-story est la troisième et dernière étape de STORY-121 : elle consomme la table créée par STORY-121.1 et les endpoints de STORY-121.2 (couverts eux aussi par la bascule et la non-régression), et clôt le remplacement complet de la FK directe par l'association à rôle.

## Critères d'acceptation (AC)

- [x] AC 2 : Migration de données sans perte : chaque utilisateur existant avec `organization_id` direct obtient sa ligne d'association avec le mapping non cassant (superuser → Super_Admin via flag inchangé ; autres → `operator`) ; les lectures sont basculées sur l'association et la colonne héritée `users.organization_id` est retirée (ou reléguée en simple valeur par défaut) **sans perte de données** — test sur fixture réaliste.
- [x] AC 5 : Non-régression : login username/email, register, `disable_auth` (auto-login superadmin) et seed continuent de fonctionner ; `make lint` + `make backend-test` verts.

## Contexte technique

> Analyse réalisée par `analyse-story` (2026-09-07) — grep exhaustif des consommateurs (`organization_id` : **300+ résultats** dans `backend/`), patterns vérifiés, arbitrages tranchés, exigences sécurité intégrées aux tâches. Évaluation complexité Phase 2.5 : **Moyenne** (bascule transverse mais **mécanique**, regroupée par domaine — voir « Décisions d'analyse »).

**Couches impactées :** Backend uniquement — migration Alembic (données + DDL), modèles, schémas Pydantic, JWT/auth, services, ~24 fichiers de lectures API/WebSocket, seed, fixtures/tests. **Aucun impact frontend/CLI** (les champs `organization_id` exposés par l'API sont conservés, désormais résolus depuis l'association).

**Spécifications de référence :**
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § `user_organizations` (SQL cible l. 608-616 : l'entité `User` cible ne porte **pas** de colonne organisation ; PK composite, `role VARCHAR(20) DEFAULT 'viewer'`, index) ;
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — Super Admin = flag sur `User`, jamais une valeur d'association ;
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — les claims JWT requis n'incluent pas `organization_id` ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §7.1 — mapping non cassant.

**Fichiers de référence (patterns vérifiés) :**
- Migration données + `batch_alter_table` (SQLite) → [`backend/alembic/versions/2026_09_07_baseline_baseline_schema.py`](../../backend/alembic/versions/2026_09_07_baseline_baseline_schema.py) (l. 249-258 : create/drop index `ix_users_organization_id` en batch ; le downgrade complet l. 629-633 prouve le pattern symétrique) ; chaînage sur `1211_user_organizations` (STORY-121.1) ;
- Helper d'appartenance → `UserOrganizationService.is_member` (STORY-121.2, [`backend/app/services/user_organization_service.py`](../../backend/app/services/user_organization_service.py)) ;
- JWT → [`backend/app/auth/jwt.py`](../../backend/app/auth/jwt.py) (`decode_access_token` l. 85-122, `decode_refresh_token` l. 125-162) ; `TokenData` dans [`backend/app/schemas/user.py`](../../backend/app/schemas/user.py) ;
- Émission des tokens → [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py) (login l. 245-250, refresh l. 410-428, register l. 696-715) ;
- Seed → [`backend/app/database_seed.py`](../../backend/app/database_seed.py) ; fixtures → [`backend/tests/conftest.py`](../../backend/tests/conftest.py) ;
- Code mort à ignorer : [`backend/app/helper/permissions.py`](../../backend/app/helper/permissions.py).

**Inventaire des consommateurs `organization_id` (vérifié par grep au 2026-09-07) :**

- **Catégorie A — modèle/schémas user (modifications structurelles)** : [`backend/app/models/user.py`](../../backend/app/models/user.py) l. 50-55 (colonne) + l. 67-69 (relation `organization`) ; [`backend/app/models/organization.py`](../../backend/app/models/organization.py) l. 57-59 (relation `users`, héritée de la FK) ; [`backend/app/schemas/user.py`](../../backend/app/schemas/user.py) (`UserCreate.organization_id` l. 82, `UserUpdate.organization_id` l. 145, `UserResponse.organization_id` l. 190, `TokenData.organization_id` l. 409).
- **Catégorie B — lectures `current_user.organization_id` en API (bascule mécanique)** : [`backend/app/api/v1/organizations.py`](../../backend/app/api/v1/organizations.py) l. 282 ; [`backend/app/api/v1/users.py`](../../backend/app/api/v1/users.py) l. 146, 158-159, 330, 539-565, 782, 934, 1121 ; [`backend/app/api/v1/stats.py`](../../backend/app/api/v1/stats.py) l. 46 ; [`backend/app/api/v1/compute.py`](../../backend/app/api/v1/compute.py) l. 52, 126 ; [`backend/app/api/v1/discovery.py`](../../backend/app/api/v1/discovery.py) l. 60, 105 ; [`backend/app/api/v1/import_export.py`](../../backend/app/api/v1/import_export.py) l. 39, 106 ; [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py) l. 1151-1152, 1166 ; [`backend/app/api/v1/workflows.py`](../../backend/app/api/v1/workflows.py) l. 21 (paramètre non utilisé, endpoint stub) ; [`backend/app/api/v1/stacks.py`](../../backend/app/api/v1/stacks.py) l. 216, 224, 384, 757-771, 1008-1016, 1164, 1369, 1437, 1482, 1538, 1599, 2044-2053, 2142-2151 ; [`backend/app/api/v1/deployments.py`](../../backend/app/api/v1/deployments.py) l. 121-132, 272, 408, 646-663, 855-872, 1036, 1233, 1415 ; [`backend/app/api/v1/targets/crud.py`](../../backend/app/api/v1/targets/crud.py) l. 133-139, 270, 480-490, 702-709, 835 ; [`backend/app/api/v1/targets/capabilities.py`](../../backend/app/api/v1/targets/capabilities.py) l. 109, 284, 454, 616 ; [`backend/app/api/v1/targets/scanning.py`](../../backend/app/api/v1/targets/scanning.py) l. 275-276, 555 ; [`backend/app/api/v1/plugins.py`](../../backend/app/api/v1/plugins.py) l. 67-74, 142-151, 378-379, 428-429, 480-481, 524-525.
- **Catégorie C — WebSocket** : [`backend/app/websocket/terminal.py`](../../backend/app/websocket/terminal.py) l. 192-194 (isolation + bug `is_superadmin`) ; [`backend/app/websocket/deployment_logs.py`](../../backend/app/websocket/deployment_logs.py) l. 41 (isolation + bug `is_superadmin`) ; [`backend/app/websocket/general.py`](../../backend/app/websocket/general.py) l. 118-124 (payload `AUTH_LOGIN_SUCCESS`).
- **Catégorie D — JWT/auth** : [`backend/app/auth/jwt.py`](../../backend/app/auth/jwt.py) l. 106, 115, 146, 155 (claims) ; [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py) l. 245-250, 411-414, 423-428, 700-705 (émission + comparaison refresh).
- **Catégorie E — seed/fixtures/tests** : [`backend/app/database_seed.py`](../../backend/app/database_seed.py) l. 73 ; [`backend/tests/conftest.py`](../../backend/tests/conftest.py) l. 227, 256 ; adaptations tests : [`backend/tests/unit/test_websocket/test_ws_auth.py`](../../backend/tests/unit/test_websocket/test_ws_auth.py) l. 43, 382 ; [`backend/tests/unit/test_user_service.py`](../../backend/tests/unit/test_user_service.py) l. 64 ; [`backend/tests/unit/test_auth/test_dev_mode.py`](../../backend/tests/unit/test_auth/test_dev_mode.py) l. 28, 88 ; tests migrations/alembic/database (simulation base legacy).
- **Hors périmètre** : colonnes `organization_id` des **autres** entités (`Stack`, `Deployment`, `Target`, `Plugin`, `ScheduledTask` — légitimes, ne pas toucher) ; schémas de ces entités ([`backend/app/schemas/stack.py`](../../backend/app/schemas/stack.py), [`target.py`](../../backend/app/schemas/target.py), [`plugin.py`](../../backend/app/schemas/plugin.py), [`scheduled_task.py`](../../backend/app/schemas/scheduled_task.py), [`target_scan.py`](../../backend/app/schemas/target_scan.py)) ; services consommant un `organization_id` **en paramètre** (déjà basculés par les endpoints) ; [`backend/app/helper/permissions.py`](../../backend/app/helper/permissions.py) (code mort) ; API clés API/refresh (STORY-123/124) ; RBAC `require_role` (STORY-122).

**Arbitrage JWT (décision d'analyse) :** le claim `organization_id` est **retiré** des tokens (login l. 245-250, refresh l. 423-428, register l. 700-705 de [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py) ; payload lu l. 106/146 de [`backend/app/auth/jwt.py`](../../backend/app/auth/jwt.py)). Justification : (1) **incompatible multi-appartenance** (une valeur unique ne peut représenter N appartenances) ; (2) **zéro consommateur runtime** : `get_current_user` recharge systématiquement l'utilisateur en base ([`backend/app/auth/dependencies.py`](../../backend/app/auth/dependencies.py) l. 85) — aucun endpoint ne lit le claim, le seul usage est la **comparaison anti-dérive** du refresh (l. 413), qui disparaît avec le claim ; (3) moins de données en transit dans le token (réduction de la surface). Le claim `is_superuser` est **conservé** (rôle système, valeur unique). Rétro-compatibilité : `decode_access_token`/`decode_refresh_token` deviennent tolérants (payload sans le claim → tokens émis avant déploiement restent valides jusqu'à expiration ; le check refresh compare uniquement `username` + `is_superuser`). Champ `TokenData.organization_id` retiré (source de vérité = association, lue en base à la requête).

**Arbitrage `is_superadmin` vs `is_superuser` (décision d'analyse) :** les 2 occurrences websocket ([`terminal.py`](../../backend/app/websocket/terminal.py) l. 194, [`deployment_logs.py`](../../backend/app/websocket/deployment_logs.py) l. 41) sont des **bugs latents** (`AttributeError` masqué par les conditions court-circuitées — le check d'isolation est aujourd'hui **inopérant**) — alignement sur le modèle réel `User.is_superuser`. La spec 06 cible `is_superadmin` : la divergence spec↔code est **documentée** ici et sera arbitrée globalement (renommage éventuel) par STORY-122/STORY-252 — **pas** dans cette story.

**Décisions d'analyse :**
- **Colonne `users.organization_id` : retrait complet** (pas de relégation) — spec 06 cible (l'entité User n'a pas de colonne organisation), supprime l'ambiguïté double source de vérité. Option AC « relégation en valeur par défaut » écartée : elle aurait conservé la FK et le risque de divergence ;
- **Re-découpe écartée** (Phase 2.5) : retrait de la colonne (NOT NULL) et bascule des lectures sont **inséparables** — retirer la colonne sans basculer casse ~24 fichiers (AttributeError), basculer sans retirer casse les INSERT users (colonne NOT NULL sans valeur). Une découpe 121.3.1/121.3.2 imposerait de maintenir un fallback temporaire de toute façon retiré à la fin ;
- **Mapping de copie (héritage, plan §7.1)** : chaque user avec `organization_id` → **1 ligne** `user_organizations` ; superuser → rôle **`admin`** (rôle max de l'association — le statut Super_Admin reste porté par le flag `is_superuser`, **inchangé**) ; autres → **`operator`** ;
- **Helper de bascule** : `UserOrganizationService.get_user_organization_ids(db, user)` (scoping/listes) et `get_primary_organization_id(db, user)` (créations de ressources : MIN(`joined_at`)) ; isolation → `is_member` existant (STORY-121.2). Superuser : helper scoping → toutes les organisations **via les ressources** (comportement actuel : bypass des checks, scoping sur `user.organization_id` non contraint) — les checks d'isolation restent court-circuités par `is_superuser` ;
- **Retrait du fallback intérim** dans `is_member` (colonne `user.organization_id`, STORY-121.2) : sans perte grâce à la migration de données de cette story ;
- **Rôle par défaut des rattachements** : `viewer` partout à l'ajout (register auto-service, création user, réaffectation) — spec 09 ; l'héritage `operator` ne s'applique qu'aux utilisateurs **pré-existants** (mapping de copie) ;
- **Register sans `organization_id` dans le body** : rattachement à l'organisation par défaut résolue par `settings.default_org_slug` (409 explicite si inexistante — incite à corriger la config plutôt qu'un user orphelin) ; org fournie → doit exister (404) ; rôle `viewer` ;
- **`UserService.create`** : construit `User` **sans** `organization_id` puis crée l'association via `UserOrganizationService.add_member` (rôle `viewer` par défaut) — le champ `UserCreate.organization_id` reste dans le contrat API (désigne l'org cible, n'est plus une colonne) ;
- **`UserUpdate.organization_id`** : traité comme **opération d'association** dans `users.py` (retrait de l'ancienne appartenance unique + ajout dans la nouvelle, rôle `viewer`) ; `UserService.update` doit l'exclure du `setattr` générique ;
- **`UserResponse.organization_id`** : champ **conservé** (contrat API non breaking), `Optional[str] = None`, peuplé à la sérialisation depuis l'association primaire (`organization_id` de la première appartenance par `joined_at`) — la multi-appartenance complète est exposée par les endpoints membres (STORY-121.2) ;
- **`workflows.py` l. 21** : paramètre `organization_id` non consommé (endpoint stub retourne `[]`) → retrait du paramètre mort ;
- **Seed** : admin créé sans colonne org + association `(default_org, Role.ADMIN)` explicite — même mapping que la migration ;
- **Fixtures conftest** : `test_user` → association `operator`, `test_superuser` → association `admin` (cohérent avec le mapping de migration) ;
- **Tests migrations (simulation base legacy)** : après retrait de la colonne du modèle, `Base.metadata.create_all` ne crée plus `users.organization_id` — les scénarios « base existante » doivent **recréer la colonne à la main** (`ALTER TABLE users ADD COLUMN organization_id VARCHAR(36)` + UPDATE de valeurs réalistes) pour simuler une base pré-121.3 fidèlement.

**Exigences sécurité identifiées (Phase 2.6) :**
- **Auth :** aucun nouvel endpoint ; garanties d'isolation existantes **renforcées** par la bascule (appartenance multi-org via `is_member` au lieu d'une égalité stricte mono-org) ; retrait du fallback `user.organization_id` de `is_member` ;
- **JWT :** claim `organization_id` retiré (arbitrage ci-dessus) ; tokens pré-existants acceptés pendant leur durée de vie (décodage tolérant) ; `is_superuser` conservé ;
- **Validation :** `organization_id` fourni (register/create/update user) → vérification d'existence de l'org (404/409) + appartenance du créateur (403) avant rattachement ; rôle d'auto-enregistrement borné `viewer` (least privilege) ;
- **Exposition :** `UserResponse.organization_id` = UUID d'organisation (non sensible), aucun `hashed_password`/`keycloak_id` introduit ; payloads websocket `AUTH_LOGIN_SUCCESS` sans données sensibles supplémentaires ;
- **Logs :** la migration de données logge uniquement des **compteurs** (nb users, nb associations créées, nb superusers) — jamais de credentials, emails ou identifiants individuels ;
- **Audit :** migration de données = action critique → log INFO avant/après avec compteurs ; les écritures membres restent tracées par les logs de STORY-121.2 ;
- **Isolation post-retrait du fallback :** garantie par `is_member` (association en base OU superuser) — testé explicitement (cf. Tests).

## Dépendances

- STORY-121.1 : Enum `Role`, modèle `UserOrganization` et migration de création de table.
- STORY-121.2 : Endpoints de gestion des membres (la bascule et la non-régression couvrent aussi ces nouveaux endpoints).
- Doit être terminée avant STORY-122 (RBAC application) et STORY-125 (audit trail).

## Périmètre indicatif (répartition des tâches identifiées par l'analyse de STORY-121)

| # | Tâche (issue de l'analyse STORY-121) | Périmètre de cette sous-story |
|---|--------------------------------------|-------------------------------|
| T3 | Migration Alembic | 🔶 Partie **données** : copie des lignes d'association depuis `users.organization_id` (mapping non cassant) + traitement de la colonne (retrait ou relégation en valeur par défaut) |
| T4 | Bascule des lectures `current_user.organization_id` vers l'association (~30 fichiers : stacks, deployments, targets, plugins, compute, stats, docker, discovery, import_export, websocket terminal/deployment_logs/general, claims JWT, seed, conftest) | ✅ Complet |
| T8 | Tests | 🔶 Partie : migration sans perte sur fixture réaliste + non-régression complète (`make lint` + `make backend-test` verts) |

**Hors périmètre :** enum/modèle/migration de création de table (STORY-121.1) ; schémas/service/endpoints membres (STORY-121.2).

## Tâches d'implémentation détaillées

> Ordre d'exécution : **T2 → T3 → T4 → T5 → T6 → T7** sont implémentables pendant que la colonne existe encore (aucun casse intermédiaire) ; **T1 (migration) et T8 (retrait modèle) atterrissent ensemble** — le schéma de test provenant des migrations (conftest), la migration qui retire la colonne et le modèle qui la déclare doivent être alignés au même commit (sinon INSERT/SELECT SQLAlchemy échouent ; c'est aussi la condition du `alembic check` sans diff) ; **T9 en dernier**. Références : `.roo/rules/30-code-standards.md` (conventions), `.roo/rules/40-security.md` (checklist sécurité), `.roo/rules/55-project-structure.md` (chemins). **Prérequis : STORY-121.1 et STORY-121.2 implémentées** (enum `Role`, modèle `UserOrganization`, service `UserOrganizationService` avec fallback intérim).

### Tâche 1 : Migration Alembic de copie des données + retrait de la colonne `users.organization_id`
**Objectif :** Copier sans perte chaque appartenance (`users.organization_id` → ligne `user_organizations` avec le mapping non cassant) puis retirer la colonne et son index, de manière symétrique et réversible (AC 2).
**Fichiers :**
- `backend/alembic/versions/2026_09_08_1213_migrate_users_org_to_associations.py` — Créer — Nouvelle migration (pattern : `2026_09_07_baseline_baseline_schema.py`). En-tête : `revision: str = "1213_users_org_migration"`, `down_revision: Union[str, None] = "1211_user_organizations"` (chaînage sur la migration STORY-121.1) ; docstring documentant STORY-121.3, le mapping (superuser → `admin` + flag inchangé ; autres → `operator`) et le caractère sans perte. Contenu :
  - `upgrade()` :
    1. **Copie des données** via SQL brut set-based (portable SQLite/PostgreSQL) : `INSERT INTO user_organizations (user_id, organization_id, role, joined_at, created_at, updated_at) SELECT u.id, u.organization_id, CASE WHEN u.is_superuser = 1 THEN 'admin' ELSE 'operator' END, <now>, <now>, <now> FROM users u WHERE u.organization_id IS NOT NULL` (attention SQLite : booléen stocké 0/1 → utiliser `u.is_superuser IN (1, TRUE)` ou cast ; horodatage via `sa.text` avec la fonction SQL courante, ex. `CURRENT_TIMESTAMP`, plutôt qu'un `datetime.now` Python figé) ; la PK composite garantit l'absence de doublon `(user_id, organization_id)` (un user n'a qu'une organisation) ;
    2. **Retrait de la colonne** : `with op.batch_alter_table("users", schema=None) as batch_op:` → `batch_op.drop_index(batch_op.f("ix_users_organization_id"))` puis `batch_op.drop_column("organization_id")` (rebuild de table SQLite — pattern baseline l. 249-258/629-633) ;
    3. Log applicatif interdit dans la migration (pas de `print` de données) — les compteurs sont vérifiés par les tests (Tâche 9) ;
  - `downgrade()` symétrique : `batch_alter_table("users")` → `add_column` (`sa.String(36)`, **nullable** — impossible de reconstituer l'org d'origine pour les users multi-org créés après la migration) + `create_index("ix_users_organization_id")` ; puis reconstruction best-effort : `UPDATE users SET organization_id = (SELECT organization_id FROM user_organizations WHERE user_organizations.user_id = users.id ORDER BY joined_at LIMIT 1)` (première appartenance) — documenter la limite dans la docstring ; les lignes `user_organizations` ne sont **pas** supprimées au downgrade ;
  - après la tâche : `alembic check` sans diff n'est atteignable qu'une fois Tâche 8 (retrait du modèle) fusionnée — la migration (T1) et le retrait modèle (T8) atterrissent au même commit (cf. note d'ordre d'exécution) ; lancer les garde-fous après.
**Exigences sécurité :** Migration sans perte (copie intégrale vérifiée par tests) ; aucun log de données individuelles dans la migration ; le mapping n'accorde jamais `super_admin` en association (rôle système = flag, inchangé).
**Dépend de :** STORY-121.1 (table `user_organizations` existante), STORY-121.2 (service)

### Tâche 2 : Helpers de lecture de l'appartenance dans `UserOrganizationService` + retrait du fallback
**Objectif :** Fournir les deux primitives de bascule des consommateurs (scoping multi-org et org « primaire » pour les créations) et retirer le fallback intérim `user.organization_id` de `is_member` (devenu mort après la migration).
**Fichiers :**
- `backend/app/services/user_organization_service.py` — Modifier — (pattern : méthodes statiques async existantes du service) :
  - Ajouter `get_user_organization_ids(db: AsyncSession, user: User) -> List[str]` — retourne les `organization_id` des lignes `UserOrganization` de l'utilisateur (une requête `select`, `str()` sur les valeurs ; liste vide si aucune appartenance) — utilisée pour le scoping des listes (Tâches 3-5) ;
  - Ajouter `get_primary_organization_id(db: AsyncSession, user: User) -> Optional[str]` — première appartenance par `joined_at` croissant (`ORDER BY joined_at LIMIT 1`), `None` si aucune — utilisée pour les créations de ressources (Tâches 3-5) ; docstring : « primaire = plus ancienne appartenance (compat: ancien organization_id unique) » ;
  - Retirer du corps de `is_member` la clause fallback `user.organization_id == str(organization_id)` (et son commentaire intérim) — l'appartenance provient désormais exclusivement de la table ; **conserver** le bypass superuser ;
  - Docstrings complètes (Args/Returns) — pattern du fichier.
**Exigences sécurité :** `is_member` reste la garde d'isolation (association en base OU superuser) — le retrait du fallback est sans perte **grâce à la migration Tâche 1** (chaque user pré-existant a sa ligne) ; aucune donnée sensible manipulée.
**Dépend de :** Tâche 1 (données migrées avant retrait du fallback), STORY-121.2

### Tâche 3 : Bascule JWT — retrait du claim `organization_id`
**Objectif :** Appliquer l'arbitrage JWT documenté (cf. Contexte technique) : ne plus émettre ni consommer le claim `organization_id`, en restant tolérant aux tokens déjà en circulation.
**Fichiers :**
- `backend/app/api/v1/auth.py` — Modifier — 3 endroits : (1) `login` (l. ~245-250) : `token_data` réduit à `{"sub", "username", "is_superuser"}` ; (2) `refresh_token` (l. ~410-428) : retirer `user.organization_id != token_data.organization_id` de la comparaison anti-dérive (ne comparer que `username` + `is_superuser`) et `organization_id` du `new_token_data` ; (3) `register` (l. ~700-705) : `token_data` réduit identiquement ;
- `backend/app/auth/jwt.py` — Modifier — `decode_access_token` (l. ~106, 115) et `decode_refresh_token` (l. ~146, 155) : supprimer la lecture `payload.get("organization_id")` et sa conversion — les tokens émis avant déploiement (avec le claim) restent valides (le claim est simplement ignoré), les nouveaux n'en contiennent pas ;
- `backend/app/schemas/user.py` — Modifier — `TokenData` (l. ~409) : retirer le champ `organization_id: Optional[str]` (docstring mise à jour : l'organisation de l'utilisateur est résolue en base à chaque requête, pas dans le token).
**Exigences sécurité :** Claim `organization_id` retiré des tokens (incompatible multi-appartenance, réduction de surface) ; aucune régression d'auth (le chemin critique `get_current_user` ne lisait jamais ce claim) ; `is_superuser` conservé.
**Dépend de :** Aucune (indépendante de Tâches 1-2 ; à merger avant Tâche 8)

### Tâche 4 : Bascule des schémas user + `UserService` (création/mise à jour via association)
**Objectif :** Faire vivre les appartenances par l'association lors des créations/modifications d'utilisateurs, en conservant le contrat API (`organization_id` d'entrée = org cible ; `organization_id` de sortie = org primaire).
**Fichiers :**
- `backend/app/schemas/user.py` — Modifier — `UserResponse.organization_id` (l. ~190) : devenir `Optional[str] = None` avec description « Organisation principale (première appartenance par joined_at) — l'appartenance complète est exposée par GET /organizations/{id}/users » ; **conserver** `UserCreate.organization_id` (l. ~82, description mise à jour : « Organisation cible du rattachement (rôle viewer) — ignoré si l'utilisateur est créé sans organisation ») et `UserUpdate.organization_id` (l. ~145, description « Nouvelle organisation (réaffectation : retrait de l'appartenance actuelle + rattachement rôle viewer) ») ;
- `backend/app/services/user_service.py` — Modifier — (1) `create` (l. ~280-309) : construire `User(email, username, full_name, hashed_password, is_superuser)` **sans** `organization_id` ; si `user_data.organization_id` est fourni, créer l'association via `UserOrganizationService.add_member(db, user_data.organization_id, OrganizationMemberAddRequest(user_id=UUID(user.id)))` (rôle défaut `viewer`) — import depuis `..services.user_organization_service` et `..schemas.organization_member` ; (2) `update` (l. ~311-339) : **exclure** `organization_id` du `setattr` générique (`update_data.pop("organization_id", None)` avec commentaire « traité comme opération d'association par l'endpoint users.py — pas une colonne ») ; (3) `update_organization_many` (l. ~388-414) : réécrire — pour chaque user trouvé : supprimer ses lignes `UserOrganization` existantes (`db.delete`) puis `UserOrganizationService.add_member(..., organization_id, role=viewer défaut)` (ne plus toucher `user.organization_id`) ; conserver la signature et le retour `(success, failed)` ;
- `backend/tests/conftest.py` — Modifier — `test_user` (l. ~222-232) : `UserCreate(..., organization_id=test_organization.id)` continue de fonctionner via le nouveau `UserService.create` (association `viewer`) — vérifier et, si besoin d'un rôle précis pour les tests API existants, ajouter explicitement l'association `operator` via `db_session.add(UserOrganization(user_id=..., organization_id=..., role=Role.OPERATOR))` après création ; `test_superuser` (l. ~251-261) : idem avec `role=Role.ADMIN` (cohérent mapping migration).
**Exigences sécurité :** Le rôle de tout rattachement programmatique est borné `viewer` (least privilege — seuls les endpoints membres STORY-121.2 permettent un rôle explicite, sous protection) ; `UserResponse` n'expose toujours pas `hashed_password`/`keycloak_id` ; les orgs cibles sont validées par les endpoints (Tâche 5) avant d'atteindre le service.
**Dépend de :** Tâche 2 (helpers/`add_member`), STORY-121.2

### Tâche 5 : Bascule des endpoints auth/users — register, création user, réaffectation, listes
**Objectif :** Basculer les flux d'écriture utilisateur (rattachement à la création/réaffectation) et les lectures `current_user.organization_id` du domaine comptes (auth + users + organizations) vers l'association, avec validation des organisations cibles.
**Fichiers :**
- `backend/app/api/v1/auth.py` — Modifier — `register` (l. ~676-715) : avant `UserService.create`, résoudre l'org cible — si `user_data.organization_id` absent : `OrganizationService.get_by_slug(session, settings.default_org_slug)` (409 « Default organization not found — configure DEFAULT_ORG_SLUG » si absente ; import `Organization`/`select` si helper manquant) et injecter dans `user_data.organization_id` ; sinon vérifier que l'org existe (404) ; le rôle d'auto-enregistrement reste `viewer` (déjà le cas via Tâche 4) ;
- **Peuplement `UserResponse.organization_id`** (login l. ~259, register l. ~714, `GET /auth/me`, endpoints users) : après retrait de la colonne, `UserResponse.model_validate(user)` laisse le champ à `None` — créer un helper partagé `async def _user_response(session, user) -> UserResponse` (dans `backend/app/api/v1/auth.py`, réutilisé/importé par `users.py`, ou fonction privée dupliquée au pattern du fichier) : `resp = UserResponse.model_validate(user)` puis `resp.organization_id = await UserOrganizationService.get_primary_organization_id(session, user)` avant retour ;
- `backend/app/api/v1/users.py` — Modifier — (1) `list_users` (l. ~158-159) : `UserService.list_by_organization(session, current_user.organization_id, ...)` → scoping sur les appartenances : `org_ids = await UserOrganizationService.get_user_organization_ids(session, current_user)` puis `UserService.list_by_organization_ids(session, org_ids, skip, limit)` (nouvelle méthode — voir ci-dessous) ; (2) les checks d'isolation mono-org (l. ~330, ~782, ~934 : `user.organization_id != current_user.organization_id`) → `not current_user.is_superuser and not await UserOrganizationService.is_member(session, current_user, user.organization_id)` — ⚠️ après Tâche 8 `user.organization_id` n'existe plus : comparer sur **l'une des** organisations de la cible : `bool(set(await UserOrganizationService.get_user_organization_ids(session, user)) & set(await ...get_user_organization_ids(session, current_user)))` (intersection non vide = même org) ; factoriser ce check dans un helper privé module-level `_share_organization(session, user_a, user_b) -> bool` pour éviter la duplication ; (3) `create_user` (l. ~539-565) : validation explicite de l'org cible (404 si `provided_org_id` fourni et inexistant — lookup `OrganizationService.get_by_id`) ; garder la règle 403 non-superuser + org ≠ sienne (comparaison via `is_member(session, current_user, provided_org_id)`) ; le fallback « org du superadmin » (l. ~555) → org primaire du superuser via `get_primary_organization_id` ; (4) `update_user` : si `user_data.organization_id` est fourni (réaffectation) → valider l'org (404), réaffecter via `UserService.update_organization_many(session, [user.id], org_id)` (sémantique unique-appartenance conservée) ; (5) `reassign_users_bulk` (l. ~1121) : inchangé fonctionnellement (délègue à `update_organization_many` déjà basculé) ;
- `backend/app/services/user_service.py` — Modifier — Ajouter `list_by_organization_ids(db, organization_ids: List[str], skip=0, limit=100) -> Tuple[List[User], int]` : users dont l'id apparaît dans `select(UserOrganization.user_id).where(UserOrganization.organization_id.in_(organization_ids))` (sous-requête `select(User).where(User.id.in_(subq))` + count équivalent) ; conserver `list_by_organization`/`count_by_organization` existants (utilisés par d'éventuels appelants : les basculer ou les supprimer si grep = 0 usage restant) ;
- `backend/app/api/v1/organizations.py` — Modifier — `get_organization` (l. ~282-284) : remplacer `current_user.organization_id != str(organization_id)` par `not await UserOrganizationService.is_member(session, current_user, organization_id)` (le bypass superuser est déjà dans `is_member` — retirer le `not current_user.is_superuser and` redondant ou le conserver en court-circuit, au choix, mais documenter) ; import du service.
**Exigences sécurité :** Isolation cross-org sur les lectures users (403 si aucune org partagée) ; validation existence org (404) avant tout rattachement ; register borné `viewer` ; superuser bypass conservé ; aucune donnée sensible dans les réponses/logs.
**Dépend de :** Tâches 2 et 4

### Tâche 6 : Bascule des lectures API par domaine (stacks, deployments, targets, plugins, compute/stats/docker/discovery/import_export) + retrait fallback endpoints membres
**Objectif :** Basculer mécaniquement, domaine par domaine, toutes les lectures restantes `current_user.organization_id` vers les helpers de Tâche 2, et retirer le fallback des endpoints membres (STORY-121.2) devenu mort.
**Fichiers (bascule mécanique — patterns identiques par type d'usage) :**
- **Scoping de listes/compteurs** (pattern : `org_ids = await UserOrganizationService.get_user_organization_ids(session, current_user)` puis `.where(Model.organization_id.in_(org_ids))` ; si la méthode service sous-jacente prend un org unique, itérer sur `org_ids` et agréger, ou étendre la méthode à une liste) :
  - `backend/app/api/v1/stats.py` (l. ~46) — `org_id = organization_id or current_user.organization_id` → si `organization_id` fourni : vérifier `is_member` (403 sinon) et filtrer dessus ; sinon filtrer `in_ (org_ids)` (adapter les 6 blocs `if org_id:` l. 50-154 en `if org_filter:` avec `in_`) ;
  - `backend/app/api/v1/compute.py` (l. ~52, ~126) — même arbitrage paramètre fourni (check `is_member` + 403) / sinon `org_ids` transmis au service (`compute_service` accepte déjà un filtre par org — étendre à `in_` ou boucle) ;
  - `backend/app/api/v1/plugins.py` (l. ~67-74, ~142-151, ~378-379) — listes/installations : idem scoping ; les checks d'isolation par plugin (l. ~480-481, ~524-525 : `plugin.organization_id != current_user.organization_id`) → `not await is_member(session, current_user, plugin.organization_id)` (superuser bypass dans `is_member`) ;
  - `backend/app/api/v1/deployments.py` (l. ~121-132 listes/compteurs → `org_ids` ; l. ~272, ~408, ~855-872, ~1036, ~1233, ~1415 checks isolation → `is_member` sur `deployment.organization_id`) ;
  - `backend/app/api/v1/stacks.py` (l. ~216-224 scoping ; l. ~384, ~1008-1016, ~1164, ~1369, ~1437, ~1482, ~1538, ~1599, ~2044-2053, ~2142-2151 checks isolation → `is_member` sur `stack.organization_id` ; l. ~757-771 création : unicité + création sur `get_primary_organization_id`) ;
  - `backend/app/api/v1/targets/crud.py` (l. ~133-139 scoping ; l. ~270, ~480-490, ~702-709, ~835 isolation/création → patterns ci-dessus) ;
  - `backend/app/api/v1/targets/capabilities.py` (l. ~109, ~284, ~454, ~616 : isolation → `is_member`) ;
  - `backend/app/api/v1/targets/scanning.py` (l. ~275-276 : `organization_id = request or current_user` → si fourni et `not is_member` → 403 (remplace l'égalité stricte actuelle — assouplissement voulu multi-org) ; l. ~555 isolation → `is_member`) ;
  - `backend/app/api/v1/discovery.py` (l. ~60, ~105 : `org_id = organization_id or current_user.organization_id` → si fourni : check `is_member` (403) ; sinon `primary` pour l'adoption/création de target) ;
  - `backend/app/api/v1/docker.py` (l. ~1151-1152, ~1166 : promotion container → stack : unicité + création sur `get_primary_organization_id`) ;
  - `backend/app/api/v1/import_export.py` (l. ~39 isolation export → `is_member` sur `stack.organization_id` ; l. ~106 création import → `get_primary_organization_id`) ;
  - `backend/app/api/v1/workflows.py` (l. ~21 : paramètre `organization_id` mort dans endpoint stub → retrait du paramètre) ;
  - `backend/app/api/v1/schedules.py` — vérifier : `list_schedules` (l. ~26-32) prend un `organization_id` query optionnel non lié à `current_user` → inchangé (pas un consommateur de la colonne user) ;
- **Retrait du fallback endpoints membres** : `backend/app/api/v1/organizations.py` — si les checks `is_member` des 4 endpoints membres (STORY-121.2) portent un commentaire « fallback intérim retiré par 121.3 », le retirer (le comportement change automatiquement via Tâche 2 — vérifier uniquement la docstring) ;
- **Convention commune** : chaque check isolation garde la structure `if not await UserOrganizationService.is_member(session, current_user, <obj>.organization_id): raise HTTPException(403, ...)` — les logs warning existants (deployments/stacks) conservent leurs `extra` (remplacer la valeur `user_org` par `"multiple"` ou la liste `org_ids` tronquée — jamais de données sensibles).
**Exigences sécurité :** Aucun affaiblissement des garanties d'isolation — au contraire : `is_member` (multi-appartenance) remplace l'égalité stricte mono-org ; le paramètre `organization_id` explicite fourni par le client est désormais **vérifié contre l'appartenance** (403) au lieu d'être ignoré/égalité (fermeture d'une incohérence) ; superuser bypass partout via `is_member`.
**Dépend de :** Tâche 2

### Tâche 7 : Bascule WebSocket + correction `is_superadmin` → `is_superuser`
**Objectif :** Basculer les 3 handlers WebSocket (isolation par appartenance + payload auth) et corriger les bugs latents `is_superadmin` (AttributeError sur attribut inexistant du modèle `User`).
**Fichiers :**
- `backend/app/websocket/deployment_logs.py` — Modifier — `verify_deployment_access` (l. ~41) : `if not user.is_superadmin and deployment.organization_id != user.organization_id:` → `if not user.is_superuser and not await UserOrganizationService.is_member(db, user, deployment.organization_id):` (import du service ; signature déjà `(deployment_id, user, db)` — db disponible) ;
- `backend/app/websocket/terminal.py` — Modifier — l. ~192-194 : `if deployment.organization_id != ws_user.organization_id and not ws_user.is_superadmin:` → `if not ws_user.is_superuser and not await UserOrganizationService.is_member(db, ws_user, deployment.organization_id):` (session `db` déjà ouverte dans le bloc `async with database.session()`) ; retirer le `# type: ignore[attr-defined]` (l'attribut correct est typé) ;
- `backend/app/websocket/general.py` — Modifier — payload `AUTH_LOGIN_SUCCESS` (l. ~118-124) : remplacer `str(user.organization_id) if user.organization_id else None` par la résolution depuis l'association : `org_ids = await UserOrganizationService.get_user_organization_ids(db, user)` puis `"organization_id": org_ids[0] if org_ids else None` (+ champ additionnel `"organization_ids": org_ids` pour la multi-appartenance — documenter dans le schéma websocket_events si le type existe) ; ⚠️ test existant `backend/tests/unit/test_websocket/test_ws_auth.py` l. 382 asserte `response["data"]["organization_id"] == "org-1"` → à mettre à jour avec une association réelle créée en fixture (le champ reste présent).
**Exigences sécurité :** Correction du bypass accidentel (conditions buggées toujours fausses → toujours « autorisé » pour les deployments d'autres orgs en WebSocket) — l'isolation redevient effective ; superuser bypass explicite `is_superuser` ; aucun token/secret dans les payloads.
**Dépend de :** Tâche 2

### Tâche 8 : Retrait de la colonne du modèle + seed + nettoyage final
**Objectif :** Retirer `organization_id` du modèle `User` (après la migration Tâche 1 et toutes les bascules), basculer le seed, et fermer le chantier (garde-fous `alembic check` verts).
**Fichiers :**
- `backend/app/models/user.py` — Modifier — Supprimer la colonne `organization_id` (l. ~49-55) et la relation `organization` (l. ~66-69) ; supprimer l'import `ForeignKey` s'il devient inutilisé et le bloc `TYPE_CHECKING`/`Organization` si les relations 121.1 (`organization_links`) n'en dépendent plus ;
- `backend/app/models/organization.py` — Modifier — Supprimer la relation `users: Mapped[List["User"]] = relationship("User", back_populates="organization", ...)` (l. ~56-59) — ⚠️ **après** Tâches 4-7 uniquement (la relation est consommée par `UserService.list_by_organization` original et les fixtures jusqu'à leur bascule) ; conserver les relations `user_links` (121.1), `targets`, `stacks`, `deployments` ;
- `backend/app/services/user_service.py` — Modifier — Supprimer/adapter `list_by_organization` + `count_by_organization` s'ils filtrent sur `User.organization_id` (remplacés par `list_by_organization_ids` — grep usages restants = 0 attendu après Tâche 5) ; `create` ne référence plus la colonne (déjà fait Tâche 4) ;
- `backend/app/database_seed.py` — Modifier — (1) `UserCreate` (l. ~68-75) : conserver `organization_id=default_org.id` (le nouveau `UserService.create` crée l'association `viewer`) **puis** promouvoir : `await UserOrganizationService.update_member_role(db, membership, Role.ADMIN)` — ou plus simple : après `UserService.create`, `db.add(UserOrganization(user_id=admin.id, organization_id=default_org.id, role=Role.ADMIN))` si pas de membership à portée de main ; l'admin doit être **Admin** de l'org par défaut (mapping cohérent avec la migration) en plus de `is_superuser=True` (flag inchangé) ; (2) vérifier `_create_localhost_target` / `seed_stack_definitions` : ils reçoivent `organization_id` en **paramètre** (`default_org.id`) — aucun changement ;
- `backend/app/api/v1/users.py` — Modifier — Nettoyage final : grep `current_user.organization_id` restant = 0 attendu (l. ~146, ~555, ~560-565 déjà traités Tâche 5) ; les exemples OpenAPI mentionnant `organization_id` dans les réponses users restent valides (champ conservé, valeur = org primaire) ;
- Garde-fous : `alembic check` sans diff (modèle ↔ migrations alignés après retrait) ; `make backend-lint` + `make backend-typecheck` verts (mypy attrapera toute référence résiduelle à la colonne supprimée).
**Exigences sécurité :** `alembic check` garantit l'alignement modèle/migrations (pas de drift schéma silencieux) ; le seed crée l'admin avec rôle `admin` en association + flag superuser (jamais `super_admin` stocké) ; aucun secret loggé.
**Dépend de :** Tâches 1-7 (toutes)

### Tâche 9 : Tests — migration sans perte, bascule, isolation, non-régression
**Objectif :** Prouver l'AC 2 (migration sans perte sur fixture réaliste) et l'AC 5 (non-régression login/register/disable_auth/seed + `make lint` + `make backend-test` verts), ainsi que les nouvelles garanties d'isolation.
**Fichiers :**
- `backend/tests/integration/test_migrations.py` — Modifier — Nouvelle classe `TestUsersOrgMigrationData` : simulation base legacy (create_all + recréer colonne `organization_id` à la main + INSERT users réalistes : superuser / actif non-superuser / user sans pattern) → `upgrade head` → assertions (détail section Tests) ; adaptation des scénarios existants (drop colonne simulée cf. Décisions d'analyse) ;
- `backend/tests/unit/test_auth/test_jwt_claims.py` — Créer — Claims émis sans `organization_id`, décodage tolérant ancien format, refresh anti-dérive sur username/is_superuser uniquement ;
- `backend/tests/unit/test_services/test_user_organization_service.py` — Modifier (STORY-121.2) — retirer le test du fallback (`test_is_member_true_via_legacy_column_fallback`) remplacé par `test_is_member_false_without_association` ; tests des 2 nouveaux helpers ;
- `backend/tests/unit/test_api/test_auth_isolation.py` — Créer — non-régression login username/email, register (rôle viewer + org par défaut), `/auth/me` (organization_id = org primaire) ;
- `backend/tests/unit/test_websocket/test_ws_auth.py` — Modifier — fixture l. 43 (User sans colonne org + association) + assertion l. 382 ;
- `backend/tests/unit/test_user_service.py` + `backend/tests/unit/test_auth/test_dev_mode.py` — Modifier — constructions User sans colonne org (l. 28/88 : user construit à la main → association via UserOrganization ou UserService.create) ;
- Tests existants à garder verts tels quels : STORY-120 (migrations), STORY-121.1 (modèle/enum), STORY-121.2 (membres — le retrait du fallback rend `test_is_member_*` caduque : remplacé ci-dessus), `test_stacks_*`, `test_deployments`, `test_plugins`, `test_container_promote` (utilisent `test_organization.id` en paramètre — inchangés), `test_secret_encryption`, scénario seed/login `TestMigratedDbSeedAndAdminLogin`.
**Exigences sécurité :** Tests sécurité obligatoires (`.roo/rules/40-security.md`) : isolation cross-org renforcée (403 sans appartenance — API **et** WebSocket), register borné `viewer`, aucune exposition de champs sensibles.
**Dépend de :** Tâches 1-8

## Tests à écrire

> Patterns détaillés : `.roo/rules/35-testing-quality-gates.md` · Tests sécurité obligatoires : `.roo/rules/40-security.md`

### Intégration — migration de données sans perte (AC 2)

- `backend/tests/integration/test_migrations.py` — Modifier — Nouvelle classe `TestUsersOrgMigrationData` (helper `_run_alembic` existant ; simulation base legacy pré-121.3 : `Base.metadata.create_all` sur DB vierge **puis** recréer la colonne legacy `ALTER TABLE users ADD COLUMN organization_id VARCHAR(36)` + `CREATE INDEX ix_users_organization_id` + INSERT de fixtures réalistes — 1 org A + 1 org B, 1 superuser→A, 2 users actifs→A/B, 1 user→NULL) :
  - `test_migration_creates_association_for_every_user_with_org` — sans perte : après `upgrade head`, chaque user avec `organization_id` a exactement 1 ligne `user_organizations` avec le bon `(user_id, organization_id)` ;
  - `test_migration_mapping_superuser_gets_admin_role` — **mapping non cassant** : superuser → `role == 'admin'` **et** `users.is_superuser` inchangé (flag non touché) ;
  - `test_migration_mapping_regular_user_gets_operator_role` — user actif non-superuser → `role == 'operator'` ;
  - `test_migration_no_row_for_user_without_org` — user avec `organization_id` NULL → aucune ligne créée (pas de rattachement inventé) ;
  - `test_migration_drops_users_organization_id_column_and_index` — réflexion `sqlalchemy.inspect` : colonne `organization_id` absente de `users`, index `ix_users_organization_id` absent ;
  - `test_migration_idempotent_via_composite_pk` — double exécution du INSERT impossible (PK composite) — la migration rejouée sur données migrées ne duplique pas ;
  - `test_downgrade_restores_column_nullable_and_backfills_first_membership` — `downgrade` : colonne recréée **nullable**, backfill première appartenance par `joined_at`, lignes `user_organizations` conservées (limite documentée) ;
  - `test_full_upgrade_path_preserves_existing_data` — données préexistantes (stacks/targets d'une org) intactes après `upgrade head` complet (baseline → 1211 → 1213) ;
  - Adaptations scénarios existants : `EXPECTED_TABLES` inchangé (aucune table ajoutée/retirée) ; scénarios « base legacy stampée » des tests 121.1 (`test_migrations.py`, `test_alembic_config.py`, `test_database.py`) doivent simuler la colonne legacy à la main (cf. Décisions d'analyse) — sinon l'upgrade 1213 échoue (colonne absente) ;
  - `test_migrated_users_can_login_via_seed_scenario` — scénario `TestMigratedDbSeedAndAdminLogin` (STORY-120) reste vert après migration 1213 (non-régression seed+login sur données migrées).

### Unitaires — service (helpers + retrait fallback)

- `backend/tests/unit/test_services/test_user_organization_service.py` — Modifier :
  - `test_is_member_false_without_association` — **remplace** `test_is_member_true_via_legacy_column_fallback` : user sans ligne en table (et sans colonne legacy) → `False` (retrait du fallback intérim) ;
  - `test_is_member_true_via_association` — inchangé (vert) ;
  - `test_is_member_superuser_bypass` — inchangé (vert) ;
  - `test_get_user_organization_ids_returns_all_memberships` — user avec 2 associations → les 2 org_ids ;
  - `test_get_user_organization_ids_empty_for_user_without_membership` — liste vide ;
  - `test_get_primary_organization_id_returns_oldest_membership` — 2 associations avec `joined_at` ordonnés → la plus ancienne ;
  - `test_get_primary_organization_id_none_without_membership` — `None`.

### Unitaires — JWT / auth (arbitrage claim + non-régression AC 5)

- `backend/tests/unit/test_auth/test_jwt_claims.py` — Créer :
  - `test_access_token_has_no_organization_id_claim` — token émis par `create_access_token` (payload login réduit) → décodé : claim `organization_id` absent, `sub`/`username`/`is_superuser` présents ;
  - `test_decode_accepts_legacy_token_with_organization_id_claim` — **rétro-compatibilité** : token forgé avec le claim → `decode_access_token` retourne un `TokenData` valide (claim ignoré) ;
  - `test_token_data_schema_has_no_organization_id` — `TokenData` n'expose plus le champ ;
  - `test_refresh_rotation_comparison_ignores_organization` — anti-dérive refresh sur `username`+`is_superuser` uniquement (pas d'échec sur changement d'appartenance).
- `backend/tests/unit/test_api/test_auth_isolation.py` — Créer (fixtures `client`/`authenticated_client`/`admin_client`) :
  - `test_login_by_username_and_email_still_work` — **AC 5** : login username ET email → 200 + token ;
  - `test_register_defaults_to_default_org_with_viewer_role` — register sans `organization_id` → 201, user rattaché à l'org par défaut avec `role == "viewer"` (vérifié en base) ;
  - `test_register_with_unknown_org_returns_404` — `organization_id` inexistant → 404 (pas de rattachement fantôme) ;
  - `test_register_role_cannot_be_escalated` — **sécurité** : le register n'expose aucun champ rôle (auto-enregistrement toujours `viewer`) ;
  - `test_me_returns_primary_organization_id` — user avec 2 appartenances → `GET /auth/me` : `organization_id` = org primaire (plus ancienne) ;
  - `test_me_response_does_not_expose_sensitive_fields` — **sécurité** : ni `hashed_password` ni `keycloak_id` dans la réponse ;
  - `test_disable_auth_mode_still_auto_logs_superadmin` — **AC 5** : `settings.disable_auth=True` → `get_current_user` retourne le superadmin seedé (patch settings, pattern `test_dev_mode.py`).

### Unitaires — API utilisateurs (bascule + isolation)

- `backend/tests/unit/test_api/test_users.py` (existant ou à créer selon état) :
  - `test_list_users_scopes_to_all_memberships` — user membre de 2 orgs → users des 2 orgs listés ;
  - `test_get_user_forbidden_without_shared_organization` — **sécurité isolation** : cible sans org commune avec le demandeur (non-superuser) → 403 ;
  - `test_get_user_allowed_with_shared_organization` — cible partageant une org → 200 ;
  - `test_superuser_access_unaffected` — superuser → 200 sur toute cible ;
  - `test_create_user_validates_target_organization_404` — org cible inexistante → 404 ;
  - `test_update_user_reassignment_moves_membership` — update avec `organization_id` → ancienne appartenance supprimée, nouvelle créée `viewer` ;
  - `test_reassign_bulk_moves_memberships` — réaffectation en masse → associations déplacées (pas de colonne).

### Unitaires — WebSocket (isolation réparée + payload)

- `backend/tests/unit/test_websocket/test_ws_auth.py` — Modifier :
  - `test_auth_login_success_payload_primary_organization` — l. ~382 adapté : payload contient `organization_id` (primaire) **et** `organization_ids` (liste) résolus depuis l'association créée en fixture ;
  - `test_terminal_isolation_denied_for_foreign_deployment` — **sécurité** : user non membre de l'org du deployment (non superuser) → connexion refusée (l'ancien bug `is_superadmin` rendait le check inopérant) ;
  - `test_deployment_logs_isolation_denied_for_foreign_deployment` — **sécurité** : `verify_deployment_access` lève 403 pour un non-membre ;
  - `test_terminal_superuser_bypass_is_superuser_flag` — superuser → accès autorisé via `is_superuser` (pas `is_superadmin`).

### Non-régression (AC 5)

- Suites existantes devant rester vertes **sans modification fonctionnelle** : STORY-120 (`test_migrations.py`, `test_alembic_config.py`, `test_database.py` — adaptations simulation legacy documentées Tâche 9), STORY-121.1 (`test_user_organization.py`), 121.2 (`test_organization_members.py`, `test_user_organization_service.py` — swap du test fallback), `test_stacks_duplicate/archive/actions`, `test_deployments`, `test_plugins*`, `test_container_promote`, `test_secret_encryption`, `test_compute_api` ;
- Adaptations mécaniques prévues : `test_ws_auth.py` (fixture l. 43 sans colonne org + associations), `test_dev_mode.py` (l. 28/88 constructions User), `test_user_service.py` (l. 64 assertion via association).

### Commandes de validation

```bash
# Tests ciblés (voir Makefile — source de vérité)
poetry run pytest backend/tests/integration/test_migrations.py -v
poetry run pytest backend/tests/unit/test_auth/ -v --tb=short
poetry run pytest backend/tests/unit/test_services/test_user_organization_service.py backend/tests/unit/test_user_service.py -v
poetry run pytest backend/tests/unit/test_websocket/test_ws_auth.py -v
poetry run pytest backend/tests/unit/test_api/test_users.py backend/tests/unit/test_api/test_auth_isolation.py -v

# Génération de la migration (si autogenerate retenu pour la partie DDL — la copie de données est manuelle)
make migrate MIGRATION_MESSAGE="migrate users organization_id to user_organizations then drop column"

# Non-régression complète + qualité (AC 5)
make backend-test-all
make backend-lint
make backend-typecheck
```

## État d'avancement technique

- [x] Tâche 1 : Migration Alembic copie données (mapping non cassant) + retrait colonne `users.organization_id`
- [x] Tâche 2 : Helpers `get_user_organization_ids` / `get_primary_organization_id` + retrait fallback `is_member`
- [x] Tâche 3 : Bascule JWT (retrait claim `organization_id`, décodage tolérant)
- [x] Tâche 4 : Schémas user + `UserService` (create/update via association) + fixtures conftest
- [x] Tâche 5 : Endpoints auth/users/organizations (register, réaffectation, scoping, isolation)
- [x] Tâche 6 : Bascule lectures API par domaine (stacks, deployments, targets, plugins, compute/stats/docker/discovery/import_export)
- [x] Tâche 7 : Bascule WebSocket + correction `is_superadmin` → `is_superuser` (terminal, deployment_logs, general)
- [x] Tâche 8 : Retrait colonne modèle `User` + relation `organization` + seed + garde-fous `alembic check`
- [x] Tâche 9 : Tests (migration sans perte, JWT, isolation, non-régression)
- [x] Tests non-régression backend complets verts (`make backend-test-all`)
- [x] Lint + typecheck OK (`make backend-lint` + `make backend-typecheck`)

## Notes d'implémentation

**Date :** 2026-09-08

### Fichiers modifiés/créés

**Migration (T1, même commit que T8) :**
- `backend/alembic/versions/2026_09_08_1213_migrate_users_org_to_associations.py` — Créer — Migration `1213_users_org_migration` : INSERT..SELECT set-based (garde `NOT EXISTS` pour rejouabilité), mapping superuser→`admin`/autres→`operator`, drop colonne + index (batch SQLite), downgrade best-effort (colonne nullable + backfill première appartenance, associations conservées)

**Service (T2) :**
- `backend/app/services/user_organization_service.py` — Ajout `get_user_organization_ids` (scoping multi-org) + `get_primary_organization_id` (org primaire = plus ancienne `joined_at`) ; retrait du fallback `user.organization_id` de `is_member` (bypass superuser conservé)

**JWT/auth (T3) :**
- `backend/app/auth/jwt.py` — decode_access/refresh tolérants (claim legacy ignoré)
- `backend/app/api/v1/auth.py` — claims réduits {sub, username, is_superuser} ; anti-dérive refresh sur username+is_superuser ; register : résolution org défaut (409 si absente) / org fournie 404 + **is_superuser forcé False** (anti-escalade) ; helper partagé `_user_response` ; `/auth/me` peuplé via org primaire
- `backend/app/schemas/user.py` — `TokenData.organization_id` retiré ; `UserResponse.organization_id` Optional (org primaire) ; descriptions `UserCreate`/`UserUpdate` mises à jour

**UserService (T4) :**
- `backend/app/services/user_service.py` — `create` sans colonne + association viewer via `add_member` ; `update` exclut organization_id du setattr ; `update_organization_many` réécrit (suppression appartenances + rattachement viewer) ; +`list_by_organization_ids` ; imports différés (cycle) ; `list_by_organization`/`count_by_organization` supprimés (0 usage restant)
- `backend/tests/conftest.py` — fixtures `test_user` (operator) / `test_superuser` (admin) via associations directes

**Endpoints (T5/T6) :**
- `backend/app/api/v1/users.py` — scoping `list_by_organization_ids` ; `_share_organization` (isolation intersection) sur get/update/delete ; create_user avec validation org (404/403/is_member + fallback org primaire) ; update_user réaffectation via `update_organization_many` ; `/users/me` peuplé
- `backend/app/api/v1/organizations.py` — `get_organization` via `is_member`
- `backend/app/api/v1/stats.py` — org_filter `in_` + check is_member 403 sur paramètre explicite
- `backend/app/api/v1/compute.py` + `backend/app/services/compute_service.py` — service étendu à `org_ids: List[str]` (`in_`), endpoints vérifient is_member sinon scopent toutes appartenances
- `backend/app/api/v1/discovery.py` — org explicite vérifiée (403) sinon org primaire
- `backend/app/api/v1/import_export.py` — export via is_member ; import sur org primaire
- `backend/app/api/v1/workflows.py` — paramètre `organization_id` mort retiré
- `backend/app/api/v1/docker.py` — promotion sur org primaire
- `backend/app/api/v1/plugins.py` — listes sur appartenances, isolation is_member
- `backend/app/api/v1/deployments.py`, `stacks.py` — scoping multi-org agrégé + isolation is_member (6+10 occurrences) + créations sur org primaire (unicité vérifiée dans l'org de la ressource en update)
- `backend/app/api/v1/targets/{crud,capabilities,scanning}.py` — scoping, isolation is_member, org explicite vérifiée (scanning), créations sur org primaire

**WebSocket (T7) :**
- `backend/app/websocket/terminal.py`, `deployment_logs.py` — isolation `is_member` + correction `is_superadmin`→`is_superuser` (bugs latents réparés)
- `backend/app/websocket/general.py` — payload AUTH_LOGIN_SUCCESS : `organization_id` (primaire) + `organization_ids` (liste) depuis l'association

**Modèle + seed (T8) :**
- `backend/app/models/user.py` — colonne + relation `organization` supprimées
- `backend/app/models/organization.py` — relation `users` supprimée
- `backend/app/database_seed.py` — admin sans colonne + association `(default_org, ADMIN)` directe

**Tests (T9) :**
- `backend/tests/integration/test_migrations.py` — +`TestUsersOrgMigrationData` (8 tests : sans perte, mapping admin/operator, pas de ligne NULL, drop colonne+index, idempotence via garde NOT EXISTS + PK, downgrade nullable+backfill+conservation, chemin complet préservé)
- `backend/tests/unit/test_auth/test_jwt_claims.py` — Créer (claims sans org, rétro-compat legacy, TokenData sans champ, anti-dérive refresh)
- `backend/tests/unit/test_api/test_auth_isolation.py` — Créer (login username/email, register org défaut viewer + 404 + anti-escalade, /auth/me org primaire, disable_auth)
- `backend/tests/unit/test_api/test_users.py` — Créer (scoping 2 orgs, isolation 403/200/superuser, create 404, réaffectation unitaire + bulk)
- `backend/tests/unit/test_websocket/test_ws_isolation_1213.py` — Créer (isolation réparée deployment_logs/terminal, bypass is_superuser, 404)
- Adaptations : `test_ws_auth.py`, `test_dev_mode.py`, `test_user_service.py`, `test_user_organization_service.py` (swap fallback), `test_organization_members.py`, `test_plugin_hooks.py`, `test_compute_api.py`, `test_compute_service.py`, `test_alembic_config.py`, `test_database.py`, `test_user_organization.py` (simulations legacy colonne + purges PK)

### Décisions techniques
- **Migration rejouable** : garde `NOT EXISTS` dans l'INSERT (le downgrade conservant les associations, un re-upgrade ne duplique jamais) — valide le test d'idempotence exigé ;
- **Register anti-escalade** : `is_superuser=False` forcé côté endpoint (le schéma UserCreate expose le champ pour la création admin — fermé pour l'auto-enregistrement) ;
- **Import différé** `UserOrganizationService` dans `UserService.create/update_organization_many` : casse le cycle d'import (le service d'association importe déjà UserService) ;
- **`compute_service` étendu en liste** (`org_ids`) plutôt que boucle d'agrégation côté endpoint (filtres `in_` natifs SQL) ;
- **Logs** : `user_org` remplacé par `"multiple"` dans les warnings stacks (aucune donnée sensible).

### Divergences par rapport à l'analyse
- **T6/plugins + tests 121.2** (validées par l'utilisateur en cours de route) : le check isolation `is_member` intègre le bypass superuser — `test_plugin_hooks::403_for_other_org` (ancienne égalité stricte refusait aussi le superuser, aucune spec ne le requiert) → 200 attendu désormais ; les fixtures rattachant l'admin fixture à l'org, les listes membres le comportent → assertions ajustées (2 membres, purge avant liste vide) ;
- **Fixtures cible sans appartenance** : `target_user` (121.2) créé nu — `_create_user` rattachait en viewer, faisant légitimement échouer les POST membres en 409 ;
- **T5/create_user** : fallback superadmin sans org → 400 explicite (« rattachez d'abord le compte ») au lieu d'un None silencieux (spec : least surprise).

### Difficultés rencontrées
- **Cycle d'import** user_service ↔ user_organization_service (levé par imports différés) ;
- **Indentations mécaniques** : remplacements de masse sur occurrences imbriquées (corrigées + compileall systématique) ;
- **Fixtures vs PK composite** : les users de test rattachés par fixtures dupliquaient les seeds des tests 121.1/121.2 → helpers de purge (`_purge_user_links`, `_seed_membership` idempotent) ;
- **asyncio.run dans env.py Alembic** : garde-fous exécutés via `asyncio.to_thread` (pattern conftest) ;
- **Contournement environnement** : venv Poetry cassé — `.venv-test/` utilisé (mypy/bandit/black/isort/flake8 y installés).

### Tests ajoutés
- 8 tests migration données (intégration) + 6 tests JWT claims + 7 tests auth isolation + 7 tests users API + 6 tests WS isolation + 5 tests helpers service (swap fallback inclus) ;
- **Non-régression complète : 1188 passed / 1 skipped (PG hors CI) / 0 failed** — les échecs pré-existants (unit 42 / int 20, constatés en 121.2) sont **intégralement résorbés** par la bascule (variation : -62 échecs) ;
- Garde-fous : `alembic upgrade head` + `alembic check` (no new operations) sur base témoin avec données réalistes + downgrade/re-upgrade ;
- Couverture globale backend : ~33% (cumul ses tests ciblés, seuil projet 80% sur nouveau code — les nouveaux modules story couverts par les tests dédiés).

### Commandes de validation exécutées
```bash
.venv-test/bin/python -m pytest backend/tests/ -q          # 1188 passed, 1 skipped
.venv-test/bin/python -m mypy backend/app                   # 24 erreurs = baseline 24 (0 nouvelle)
.venv-test/bin/python -m flake8 backend/app                 # 0 nouveau (pré-existants docker.py/background_tasks)
.venv-test/bin/python -m black --check (fichiers story)     # OK après formatage
.venv-test/bin/python -m bandit (fichiers story)            # 21 medium = baseline (docstrings OpenAPI)
# alembic upgrade head + alembic check : OK
```
