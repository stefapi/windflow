# STORY-129 : Endpoints santé & mot de passe — `GET /system/ready` sans auth et `PUT /auth/password` (P1-7 + P1-8)

**Statut :** TODO
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-7 (axe A12) + P1-8 (axe A13, rapport §1/§2) — ampleur **S**

## Description

En tant qu'exploitant de WindFlow, je veux un endpoint de **readiness** `GET /api/v1/system/ready` accessible sans authentification (vérifiant DB, migrations appliquées et dépendances optionnelles) et un endpoint `PUT /api/v1/auth/password` permettant à un utilisateur authentifié de changer son mot de passe (ancien requis), afin que les orchestrateurs (docker compose healthcheck, install.sh « attend que l'API soit prête ») disposent d'un vrai signal de démarrage et que les utilisateurs gèrent leurs credentials.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §1, §2, §14) : seul [`GET /health`](../../backend/app/main.py:315) existe (vérifie DB + Redis, 503 si DB down) — pas de `/ready` ; `PUT /auth/password` n'existe pas ([`auth.py`](../../backend/app/api/v1/auth.py:27)). La spec 09 exige `/system/health` **et** `/system/ready` sans auth, et la liste canonique auth inclut `PUT /password`.

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- [`GET /health`](../../backend/app/main.py:315) existant (DB + Redis si configuré, 503 si DB down) : à **formaliser** sous `/system/health` (sans auth, garde-fou : ne pas l'exposer derrière l'auth) — la route racine actuelle peut être conservée/aliasée le temps de la transition (analyse arbitrera l'alias vs remplacement, spec 09 plaçant les deux sous `/system/`) ;
- `/ready` : vérifie **migrations appliquées** (version Alembic courante = head — dépend STORY-120), **DB** joignable, et **dépendances optionnelles** (Redis si configuré) ; réponse **503** avec détails si non-prêt ; sans auth ;
- `PUT /auth/password` : authentifié (`get_current_user`) ; body `{current_password, new_password}` — **ancien mot de passe requis** et vérifié (`400`/`401` si faux — aligné sur le critère de done : « 400 si faux ») ; nouveau hash écrit (bcrypt actuellement ; Argon2id via STORY-130 si fusionnée avant) ; **révocation de tous les refresh tokens** de l'utilisateur (mécanisme posé par STORY-123) ; validation force du mot de passe (politique existante) ;
- Rate limiting existant sur `/auth/*` à appliquer si pertinent ; audit du changement de mot de passe (STORY-125 si fusionnée — sinon à prévoir) ;
- install.sh ([`16-deploiement.md`](../../docs/general_specs/16-deploiement.md)) « attend que l'API soit prête (health check) » → `/ready` devient le signal docummenté (docker compose `healthcheck`).

## Critères d'acceptation (AC)

- [ ] AC 1 : `GET /api/v1/system/ready` répond **sans auth** : vérifie migrations appliquées + DB + dépendances optionnelles (Redis si configuré) ; `200` avec détails des checks quand prêt, **503** avec causes quand non-prêt ; `/system/health` formalisé sans auth (comportement du `/health` actuel préservé ou aliasé).
- [ ] AC 2 : `PUT /api/v1/auth/password` authentifié : **200** avec ancien mot de passe correct (hash mis à jour, login suivant fonctionne avec le nouveau) ; **400** si ancien mot de passe faux ; **422** sur body invalide (champs manquants, mot de passe trop faible selon la politique) ; **401** sans token.
- [ ] AC 3 : Après un changement de mot de passe réussi : **tous les refresh tokens de l'utilisateur sont révoqués** (le refresh suivant avec un ancien token → `401`) ; les clés API ne sont pas affectées (comportement à documenter).
- [ ] AC 4 : Tests de sécurité : `/ready` accessible sans token (et insensible à l'info sensible — pas de versions/secrets dans la réponse) ; `make lint` + `make backend-test` verts.

## Références spécification

- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Système (`GET /system/health`, `GET /system/ready` « pas d'auth requise »), § Authentification (`PUT /password`), § Authentification (exemptions d'auth) ;
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Authentification par mot de passe (hashage), § Endpoints auth ;
- [`docs/general_specs/16-deploiement.md`](../../docs/general_specs/16-deploiement.md) — § installation (install.sh attend l'API prête ; `curl /api/v1/system/health`) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §1 (existe `/health` seul), §2 (pas de `PUT /password`), §14 ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-7 (A12) et P1-8 (A13, dépend de P1-3 refresh).

## Dépendances

- Partie `/ready` : **STORY-120** (check « migrations appliquées » significatif uniquement avec Alembic).
- Partie `/auth/password` : **STORY-123** (révocation des refresh tokens).
- Interaction : STORY-130 (Argon2id — hash du nouveau mot de passe selon l'état de fusion) ; STORY-125 (audit de l'événement).

## Sous-stories

*(section réservée — ampleur S, découpe non prévue)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
