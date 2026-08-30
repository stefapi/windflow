# STORY-124 : Clés API `wf_ak_` — table `api_keys`, auth `X-API-Key` coexistant avec JWT (P1-3, partie clés API)

**Statut :** TODO
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-3 partie clés API (axe A5, rapport §2) — ampleur **M** (partie clés API de l'item L)

## Description

En tant qu'utilisateur de WindFlow, je veux pouvoir créer des clés API préfixées `wf_ak_` (hashées en base, révocables, avec expiration optionnelle) qui m'authentifient sur les routes API via le header `X-API-Key` (ou `Authorization: Bearer wf_ak_…`), afin de scripter la CLI et les intégrations tierces sans manipuler de JWT courts.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §2, §7.4, §14) : aucune table `api_keys`, aucun endpoint de gestion ; [`auth/dependencies.py`](../../backend/app/auth/dependencies.py:23) n'accepte que les JWT. La spec exige des clés `wf_ak_` + 48 caractères aléatoires (`secrets.token_urlsafe`), hash bcrypt stocké, affichage unique, révocation immédiate.

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- Schéma cible spec 06 : `api_keys (id, user_id FK CASCADE, name VARCHAR(100), key_hash VARCHAR(255), expires_at TIMESTAMP null, last_used_at, revoked BOOLEAN DEFAULT FALSE, created_at)` + index `user_id` ;
- Endpoints spec 09 § Authentification : `POST /auth/api-keys` (création → **affichage unique** de la clé complète), `GET /auth/api-keys` (liste **sans jamais** la clé ni son hash), `DELETE /auth/api-keys/{id}` (révocation) ;
- Auth : `get_current_user` ([`auth/dependencies.py`](../../backend/app/auth/dependencies.py:23)) doit accepter JWT **ou** clé API — header `X-API-Key` **ou** `Authorization: Bearer wf_ak_…` (les deux formes spécifiées) ; résolution par comparaison de hash bcrypt ; utilisateur désactivé → refus ; `last_used_at` mis à jour ;
- **RBAC s'applique** : une clé API porte les permissions de son propriétaire — `require_role(...)` (STORY-122) s'exécute après authentification par clé ; une clé n'est jamais un contournement du RBAC ;
- Révocation immédiate : `revoked=true` ou expiration → `401` instantané (pas de cache long sur les clés révoquées) ;
- La CLI peut s'appuyer sur les clés API (`windflow auth login --api-key`, `WINDFLOW_API_KEY` — spec 10) : côté frontend/CLI, l'adaptation est un plus, le cœur de la story est backend.

## Critères d'acceptation (AC)

- [ ] AC 1 : La table `api_keys` existe via migration Alembic (STORY-120) conformément au schéma spec 06 ; la création génère `wf_ak_` + 48 caractères (`secrets.token_urlsafe`), stocke **uniquement le hash bcrypt** (jamais la clé), et retourne la clé complète **une seule fois** à la création ; expiration configurable à la création (null = n'expire jamais).
- [ ] AC 2 : Une clé `wf_ak_...` **authentifie** via `X-API-Key` (et `Authorization: Bearer wf_ak_…`) sur les routes API protégées, avec les permissions RBAC du propriétaire appliquées (STORY-122) ; clé invalide/révoquée/expirée → `401` ; `last_used_at` alimenté.
- [ ] AC 3 : **Révocation immédiate** : `DELETE /auth/api-keys/{id}` → les requêtes suivantes avec cette clé → `401` ; `GET /auth/api-keys` liste les clés (nom, dates, statut) **sans exposer** clé, hash ni secret.
- [ ] AC 4 : Tests de sécurité obligatoires : `401` sans clé ; clé d'un utilisateur désactivé → `401` ; `403` lorsque le RBAC du propriétaire refuse (viewer sur endpoint modifiant) ; `422` sur body de création invalide ; isolation — un user ne liste/révoque que **ses** clés (`404`/`403` sur clé étrangère) ; aucune clé ni hash dans les réponses ni les logs.

## Références spécification

- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Authentification par clé API (format `wf_ak_`, hash bcrypt, affichage unique, expiration, révocation), § Validation des tokens dans l'API (JWT ou clé API, `X-API-Key`) ;
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités auth et audit → `APIKey` (schéma SQL) ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Authentification (`POST/GET /auth/api-keys`, `DELETE /auth/api-keys/{id}`), § Authentification (Bearer JWT ou `wf_ak_`) ;
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — la matrice s'applique à l'identique après auth par clé ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §2, §7.4, §14 (aucune clé API existante) ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-3 (partie clés API), §2.A A5.

## Dépendances

- **STORY-120** (migration de la table `api_keys`) ; **STORY-122** (le RBAC `require_role` s'applique aux requêtes authentifiées par clé — coexiste avec JWT).

## Sous-stories

*(section réservée — ampleur M, découpe non prévue a priori)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
