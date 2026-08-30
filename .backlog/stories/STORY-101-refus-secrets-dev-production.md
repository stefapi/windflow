# STORY-101 : Garde-fou de démarrage — refus des secrets dev par défaut en production (P0-2)

**Statut :** TODO
**Epic Parent :** EPIC-011 — P0 : Sécurité bloquante
**Item plan :** P0-2 (rapport d'écart B12, §7) — ampleur **S**

## Description

En tant qu'administrateur système déployant WindFlow en production, je veux que le démarrage échoue explicitement si des secrets de développement par défaut sont encore utilisés, afin d'empêcher qu'une instance exposée tourne avec un `jwt_secret` prédictible (forgabilité des JWT) et un compte admin `changeme123` (prise de contrôle immédiate).

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §11, §14.3) : [`config.py`](../../backend/app/config.py:15) embarque un **secret JWT dev par défaut** et le seeding ([`database_seed.py`](../../backend/app/database_seed.py)) crée un admin avec le mot de passe **`changeme123`** (`Seeding` : email/username/password admin par défaut). Rien n'empêche `environment=production` de démarrer avec ces valeurs : quiconque connaît le code source peut forger des tokens valides et se connecter en admin. La spec exige l'inverse : `SECRET_KEY` « généré automatiquement par `install.sh` », « mot de passe admin suffisamment fort » (15-securite.md § Checklists de sécurité).

## Contexte technique

*(à remplir par analyse-story)*

Points d'appui existants :
- `Settings` pydantic-settings avec propriété `is_production` / champ `environment` ([`config.py`](../../backend/app/config.py:15)) ;
- Lifespan startup : `db.connect()` + `create_tables()` + `seed_tables()` puis init rate limiter ([`main.py`](../../backend/app/main.py:59)) — la validation doit intervenir **avant** toute exposition réseau ;
- Fichiers env à maintenir cohérents : `env.example` (critère de done du plan), `.env.prod.example` ;
- Mode dev (`environment` ≠ production) : comportement inchangé, aucun blocage.

## Critères d'acceptation (AC)

- [ ] AC 1 : Au démarrage avec `environment=production`, si `jwt_secret` garde sa valeur dev par défaut **ou** si le seeding admin utiliserait le mot de passe `changeme123`, l'application **refuse de démarrer** : exception au startup avec un message explicite nommant la/les variable(s) concernée(s) et la marche à suivre (aucun démarrage partiel, aucune exposition de l'API).
- [ ] AC 2 : Le même démarrage avec des secrets forts (`jwt_secret` défini, mot de passe admin défini via env) fonctionne normalement en production — pas de faux positif bloquant les installations légitimes.
- [ ] AC 3 : Les environnements de développement/test ne sont pas impactés : valeurs par défaut toujours acceptées dès que `environment` ≠ production.
- [ ] AC 4 : [`env.example`](../../env.example) documente les variables concernées et le comportement de blocage en production (critère de done du plan : « doc `env.example` à jour ») ; `.env.prod.example` vérifié cohérent.
- [ ] AC 5 : Tests écrits et passants : `test_startup_fails_in_production_with_default_jwt_secret`, `test_startup_fails_in_production_with_default_admin_password`, `test_startup_fails_lists_all_offending_secrets`, `test_startup_succeeds_in_production_with_strong_secrets`, `test_dev_environment_unaffected_by_guard` — `make lint` + `make backend-test` verts.

## Références spécification

- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) § Checklists de sécurité → « À l'installation » (`SECRET_KEY` généré aléatoirement, mot de passe admin suffisamment fort) et § Chiffrement des secrets → « Protection du SECRET_KEY » (jamais commité, compromission = compromission de tous les JWT) ;
- [`docs/general_specs/16-deploiement.md`](../../docs/general_specs/16-deploiement.md) § Installation — `install.sh` génère un `SECRET_KEY` aléatoire et crée le `.env` (le garde-fou couvre les installations hors `install.sh`) ;
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) § Access token (JWT) — signature HS256 avec le `SECRET_KEY` de l'instance, § Configuration — `SECRET_KEY` généré automatiquement ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §11 (Configuration : « Secret (valeur dev par défaut) », seeding `changeme123`), §14.3 (« Secrets dev par défaut ») ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 Vague P0 — item P0-2, §2.B — item B12.

## Dépendances

- Aucune (item autonome de la vague P0).

## Sous-stories

*(section réservée — STORY-101 ampleur S, découpage non prévu)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
