# STORY-121 : Modèle `user_organizations` — association utilisateur ↔ organisation avec rôle (P1-2, partie modèle)

**Statut :** DONE
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-2 partie modèle (axe A2, rapport §3) — ampleur **M** (partie modèle de l'item XL)

## Description

En tant qu'administrateur WindFlow, je veux que l'appartenance d'un utilisateur à une organisation porte un **rôle** (Viewer / Operator / Admin) via une table d'association `user_organizations`, afin de poser la base de données du RBAC 4 rôles spécifié (le Super_Admin restant un rôle système porté par `User.is_superadmin`), avec migration **non cassante** des utilisateurs existants.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §6, §14) : le modèle actuel est **binaire** — [`User`](../../backend/app/models) porte une FK `organization_id` directe + flag `superuser` ; il n'existe aucune table `user_organizations`, aucun rôle par organisation (seule dépendance [`require_superuser`](../../backend/app/auth/dependencies.py:23)). La spec exige : « Le rôle est porté par la table d'association `user_organizations` » et « Le Super Admin est identifié par le flag `is_superadmin` sur l'entité `User` » ([`08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) § Implémentation).

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- Schéma cible spec 06 : `user_organizations (user_id FK CASCADE, organization_id FK CASCADE, role VARCHAR(20) DEFAULT 'viewer', joined_at, PK composite)` + index sur `organization_id` ;
- Enum `Role` (`viewer` / `operator` / `admin`) — spec 08 § Définition des rôles ; `super_admin` **n'est pas** une valeur de l'association (rôle système via `User.is_superadmin`) ;
- Migration de données : l'appartenance actuelle (`users.organization_id` FK directe) doit être copiée vers des lignes d'association ; **mapping non cassant** du plan §7.1 : superuser → Super_Admin (flag, inchangé), autres utilisateurs actifs → **Operator** (droits proches de l'existant, ajustable ensuite) ;
- Endpoints de gestion des membres (spec 09 § Organisations) : `GET/POST /organizations/{id}/users`, `PUT /organizations/{id}/users/{user_id}` (changement de rôle), `DELETE /organizations/{id}/users/{user_id}` — rôle par défaut `viewer` à l'ajout ;
- Ces endpoints de gestion doivent être protégés selon la matrice spec 08 (Admin+ / gestion des utilisateurs) — le mécanisme `require_role(...)` et les **protections d'escalade** sont portés par STORY-122, dont l'AC de couverture inclut ces endpoints ; en attendant la fusion de STORY-122, protection `require_superuser` ;
- STORY-120 (Alembic) **doit** être fusionnée avant toute migration de modèle.

## Critères d'acceptation (AC)

- [x] AC 1 : La table `user_organizations` existe via migration Alembic (STORY-120) conformément au schéma spec 06 (PK composite, `role` défaut `viewer`, `joined_at`, index `organization_id`), avec l'enum `Role` (`viewer`/`operator`/`admin`) partagé côté backend.
- [x] AC 2 : Migration de données sans perte : chaque utilisateur existant avec `organization_id` direct obtient sa ligne d'association avec le mapping non cassant (superuser → Super_Admin via flag inchangé ; autres → `operator`) ; les lectures sont basculées sur l'association et la colonne héritée `users.organization_id` est retirée (ou reléguée en simple valeur par défaut) **sans perte de données** — test sur fixture réaliste.
- [x] AC 3 : Endpoints de gestion des membres opérationnels conformément à spec 09 : lister les membres (rôle + joined_at), ajouter un membre (rôle défaut `viewer`), modifier le rôle, retirer un membre — protégés a minima par l'authentification + la dépendance la plus forte disponible (cf. contexte), la couverture RBAC finale étant vérifiée par STORY-122.
- [x] AC 4 : Tests de sécurité : `401` sans token sur les endpoints membres ; `403` pour un rôle insuffisant ; `422` sur rôle invalide dans le body ; un utilisateur ne peut pas lister/modifier les membres d'une organisation à laquelle il n'appartient pas.
- [x] AC 5 : Non-régression : login username/email, register, `disable_auth` (auto-login superadmin) et seed continuent de fonctionner ; `make lint` + `make backend-test` verts.

## Références spécification

- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — § Rôles (définition des 4 rôles, « Super Admin = flag `is_superadmin` sur User, pas une entrée dans `user_organizations` »), § Implémentation → Modèle de données (`UserOrganization`) ;
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités comptes et organisations → `UserOrganization` (schéma SQL) ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Organisations (`/organizations/{id}/users`) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §6 (User : « org FK, superuser »), §14 (« Pas de RBAC granulaire ») ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-2 (partie modèle), §2.A A2, §3 F4 étape 1, §7.1 (mapping non cassant).

## Dépendances

- **STORY-120** (Alembic avant toute migration de modèle).
- Est un prérequis de : STORY-122 (`require_role` + application RBAC + protections d'escalade) et, pour « l'acteur rôle », STORY-125 (audit trail).

## Sous-stories

> Découpe effectuée le 2026-09-07 (skill `split-story`, **mode proactif** — complexité détectée par `analyse-story` : 8 tâches > 5, 16+ fichiers > 6, colonne `users.organization_id` consommée par ~30 fichiers backend). Découpe **basée sur les AC uniquement** (l'analyse s'était arrêtée au verdict COMPLEXE sans rédiger les tâches détaillées) : chaque sous-story devra passer par `analyse-story` avant `treat-story`.

- [x] STORY-121.1 : Enum `Role`, modèle `UserOrganization` et migration de création de table — Couvre AC 1
- [x] STORY-121.2 : Endpoints de gestion des membres d'une organisation — Couvre AC 3, AC 4
- [x] STORY-121.3 : Migration des données, bascule des lectures vers l'association et retrait de la colonne héritée — Couvre AC 2, AC 5

## État d'avancement technique

> ⚠️ L'avancement technique est désormais suivi dans les sous-stories individuelles.

**Progression :** 3/3 sous-stories terminées
- [x] STORY-121.1 : Enum `Role`, modèle `UserOrganization` et migration de création de table
- [x] STORY-121.2 : Endpoints de gestion des membres d'une organisation
- [x] STORY-121.3 : Migration des données, bascule des lectures vers l'association et retrait de la colonne héritée

## Tâches d'implémentation détaillées

> ⚠️ Cette story a été découpée en sous-stories avant implémentation (complexité détectée par analyse-story).
> Toutes les tâches identifiées ont été redistribuées à titre indicatif dans les sous-stories listées ci-dessus
> (découpe AC-uniquement : les tâches détaillées restent à rédiger par `analyse-story` sur chaque sous-story).
> Consulter chaque sous-story pour le périmètre et les dépendances.

## Tests à écrire

> ⚠️ Les tests sont désormais définis dans les sous-stories individuelles.

## Notes d'implémentation

**Date de clôture :** 2026-09-08 (finalisation `finalise-story` après traitement des 3 sous-stories)

### Récapitulatif de clôture

La story a été implémentée intégralement via ses 3 sous-stories (découpe proactive `split-story`, complexité détectée par `analyse-story`) :

- **STORY-121.1** — Enum `Role` ([`backend/app/enums/rbac.py`](../../backend/app/enums/rbac.py)), modèle `UserOrganization` ([`backend/app/models/user_organization.py`](../../backend/app/models/user_organization.py)), migration additive `1211_user_organizations` (table + PK composite + index). 14 tests modèle/enum + 6 tests migration structurelle.
- **STORY-121.2** — Schémas [`backend/app/schemas/organization_member.py`](../../backend/app/schemas/organization_member.py), service [`UserOrganizationService`](../../backend/app/services/user_organization_service.py), 4 endpoints membres dans [`backend/app/api/v1/organizations.py`](../../backend/app/api/v1/organizations.py) (auth + `require_superuser` intérim + isolation cross-org). 42 tests (13 service + 29 API dont ~22 sécurité).
- **STORY-121.3** — Migration de données `1213_users_org_migration` (mapping non cassant : superuser→`admin`, autres→`operator` ; retrait colonne `users.organization_id`), bascule de ~24 fichiers de lectures vers l'association, retrait claim JWT `organization_id`, correction bugs WS `is_superadmin`, seed via association. ~39 tests ajoutés.

Les notes d'implémentation détaillées (fichiers, décisions, divergences, difficultés) sont portées par chaque sous-story.

### Validation de finalisation (quality gate `finalise-story`)

- **Tests** : suite backend complète **1188 passed / 1 skipped / 0 failed** en conditions CI (`.env` local neutralisé — son `DISABLE_AUTH=true`/`CSP_ENABLED=false` de dev contamine autrement les settings pydantic et provoque 67 échecs environnementaux sans lien avec la story) ; 105 tests ciblés story verts.
- **Couverture** : 100 % sur les 4 nouveaux modules (`enums/rbac.py`, `models/user_organization.py`, `schemas/organization_member.py`, `services/user_organization_service.py`).
- **Lint** : isort + black + flake8 verts sur les 33 fichiers du périmètre — **correction apportée à la finalisation** : tri d'imports isort sur [`backend/app/api/v1/stacks.py`](../../backend/app/api/v1/stacks.py), [`backend/app/api/v1/deployments.py`](../../backend/app/api/v1/deployments.py), [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py) (dégradés par la story) et [`backend/app/api/v1/plugins.py`](../../backend/app/api/v1/plugins.py) (pré-existant, fichier du périmètre) ; 49 tests des fichiers corrigés re-passés verts.
- **Typecheck** : mypy 26 erreurs = baseline pré-story (diff avant/après stash : 1 numéro de ligne décalé uniquement — stubs `psutil` environnementaux).
- **Bandit** : 0 vulnérabilité haute sur le périmètre.
- **Build** : `poetry build` non exécutable (venv Poetry cassé — contournement `.venv-test` documenté) ; `compileall` OK sur `backend/app`.
- **Oublis** : aucun TODO/FIXME, aucun fichier annoncé manquant, plus aucune lecture `current_user.organization_id` active (uniquement commentaires historiques), `helper/permissions.py` = code mort hors périmètre confirmé.

### Suivi

- La couverture RBAC finale des endpoints membres (`require_role("admin")`) reste portée par **STORY-122** (prochaine étape), conformément au contexte de la story.
- Débloque : STORY-122 (RBAC application), STORY-125 (audit trail).
