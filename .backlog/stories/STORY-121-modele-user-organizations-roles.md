# STORY-121 : Modèle `user_organizations` — association utilisateur ↔ organisation avec rôle (P1-2, partie modèle)

**Statut :** TODO
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

- [ ] AC 1 : La table `user_organizations` existe via migration Alembic (STORY-120) conformément au schéma spec 06 (PK composite, `role` défaut `viewer`, `joined_at`, index `organization_id`), avec l'enum `Role` (`viewer`/`operator`/`admin`) partagé côté backend.
- [ ] AC 2 : Migration de données sans perte : chaque utilisateur existant avec `organization_id` direct obtient sa ligne d'association avec le mapping non cassant (superuser → Super_Admin via flag inchangé ; autres → `operator`) ; les lectures sont basculées sur l'association et la colonne héritée `users.organization_id` est retirée (ou reléguée en simple valeur par défaut) **sans perte de données** — test sur fixture réaliste.
- [ ] AC 3 : Endpoints de gestion des membres opérationnels conformément à spec 09 : lister les membres (rôle + joined_at), ajouter un membre (rôle défaut `viewer`), modifier le rôle, retirer un membre — protégés a minima par l'authentification + la dépendance la plus forte disponible (cf. contexte), la couverture RBAC finale étant vérifiée par STORY-122.
- [ ] AC 4 : Tests de sécurité : `401` sans token sur les endpoints membres ; `403` pour un rôle insuffisant ; `422` sur rôle invalide dans le body ; un utilisateur ne peut pas lister/modifier les membres d'une organisation à laquelle il n'appartient pas.
- [ ] AC 5 : Non-régression : login username/email, register, `disable_auth` (auto-login superadmin) et seed continuent de fonctionner ; `make lint` + `make backend-test` verts.

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

*(section réservée — STORY-121 ampleur M, découpe non prévue a priori)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
