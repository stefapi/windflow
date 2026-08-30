# STORY-104 : Protection brute-force du login — compteur par username, blocage temporaire (P0-5)

**Statut :** TODO
**Epic Parent :** EPIC-011 — P0 : Sécurité bloquante
**Item plan :** P0-5 (rapport d'écart C2, §2) — ampleur **M**

## Description

En tant qu'administrateur sécurité de WindFlow, je veux un verrouillage progressif du compte après des échecs répétés de connexion (compteur par username/IP : 5 essais sur 10 minutes, blocage 5 minutes), afin de rendre impraticable toute attaque par force brute ciblant les mots de passe — y compris via des requêtes multiplexées depuis plusieurs IP.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §3.1) : l'endpoint [`POST /auth/login`](../../backend/app/api/v1/auth.py:27) ne dispose que du rate limit global 5/min par IP (lui-même no-op sans Redis — traité par STORY-102). Rien ne compte les **échecs par identité** : un attaquant distribué (plusieurs IP, tentative espacée par IP) peut énumérer les mots de passe sans jamais déclencher de blocage. La spec exige un compteur dédié « 5 tentatives / fenêtre 600 s / blocage 300 s », indexé par couple (username ou IP), stocké « Redis en mode standard, mémoire en mode léger », réinitialisé après un login réussi (07-authentification.md § Protection brute-force).

## Contexte technique

*(à remplir par analyse-story)*

Points d'appui existants :
- [`auth.py`](../../backend/app/api/v1/auth.py:27) : login username OU email, JWT + refresh, support `disable_auth` ; réponses d'erreur normalisées `401 INVALID_CREDENTIALS` ;
- Réutilisation du fallback mémoire de **STORY-102** (même mécanique de stockage Redis-ou-mémoire — dépendance P0-3 → P0-5 du plan) : ne pas réimplémenter un deuxième limiteur maison ;
- **Distinction des deux couches** (à garder clairement séparées) : le rate limit API 5/min **par IP** (STORY-102) protège le volume ; le compteur brute-force **par username** protège l'identité — les deux coexistent (07-authentification.md : « La limite `POST /auth/login` (5/minute par IP) est aussi appliquée au niveau API ») ;
- Paramètres configurables via env : `AUTH_MAX_ATTEMPTS` (5), `AUTH_LOCKOUT_SECONDS` (300), fenêtre de comptage 600 s (07-authentification.md) ;
- Erreur de blocage : `429` avec code `TOO_MANY_ATTEMPTS` et header `Retry-After` (07-authentification.md § refresh/erreurs + plan : « 6e essai → 429 avec `Retry-After` ») ;
- Audit : les échecs de login sont des événements d'audit (`user.login_failed` — 15-securite.md § Audit trail) mais la **table audit_logs n'arrive qu'en P1-4** : se limiter ici au log structuré existant, sans données sensibles (jamais le mot de passe).

## Critères d'acceptation (AC)

- [ ] AC 1 : Après **5 échecs d'authentification pour un même username** sur la fenêtre glissante de 10 minutes, le **6e essai** (même avec le bon mot de passe) reçoit **429 avec code d'erreur `TOO_MANY_ATTEMPTS` et header `Retry-After`** indiquant la durée de blocage restante — quelles que soient les IP sources utilisées (compteur par username, pas par IP seule).
- [ ] AC 2 : Le blocage expire après **5 minutes** : un essai légitime post-fenêtre réussit ; **un login réussi réinitialise le compteur** d'échecs du username (spec 07) ; la fenêtre de comptage (600 s) et les seuils sont configurables (`AUTH_MAX_ATTEMPTS`, `AUTH_LOCKOUT_SECONDS`).
- [ ] AC 3 : Le stockage fonctionne dans les **deux profils** : Redis quand `RATE_LIMIT_STORAGE_URL` est présent, **mémoire** sinon — réutilisation du mécanisme introduit par STORY-102, sans double implémentation divergente ; test des deux chemins.
- [ ] AC 4 : Non-régression : le rate limit API global 5/min par IP (STORY-102) reste actif et distinct ; messages d'erreur existants inchangés pour le cas nominal (`401 INVALID_CREDENTIALS` sans divulgation de l'existence du compte) ; mode `disable_auth` non impacté ; aucune donnée sensible dans les logs.
- [ ] AC 5 : Tests écrits et passants (critères de done du plan) : `test_sixth_attempt_returns_429_with_retry_after`, `test_counter_resets_after_window`, `test_counter_reset_on_successful_login`, `test_counter_per_username_not_ip_only` (échecs depuis 2 IP différentes → même compteur), `test_lockout_expires_after_5_minutes`, `test_storage_memory_and_redis_paths` — `make lint` + `make backend-test` verts.

## Références spécification

- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) § Protection brute-force (table des paramètres : 5 tentatives / `AUTH_MAX_ATTEMPTS`, blocage 300 s / `AUTH_LOCKOUT_SECONDS`, fenêtre 600 s ; compteur par couple username-IP dans le cache Redis-ou-mémoire ; réinitialisation après login réussi) et § Erreurs (`429 TOO_MANY_ATTEMPTS`) ;
- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) § Authentification et RBAC — synthèse (« rate limiting 5 tentatives/minute par IP puis blocage 5 minutes ») et § Audit trail (`user.login_failed` loggé avec username, IP, raison) ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — `POST /auth/login` public, RL 5/min (couche API distincte, renvoyée à STORY-102) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §3.1 (login actuel : RL 5/min uniquement), §13.3 (« Auth : register/refresh/RBAC peu couverts ») ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 Vague P0 — item P0-5, §2.C — item C2.

## Dépendances

- **STORY-102** (obligatoire, antérieure) : réutilise sa mécanique de stockage Redis-ou-mémoire — plan : P0-5 « Dépend de P0-3 (même mécanique de stockage) ».
- Aucune dépendance inter-vagues directe ; pose la base du comportement login attendu par P1-4 (audit `user.login_failed` persisté) sans l'implémenter.

## Sous-stories

*(section réservée — STORY-104 ampleur M, découpage non prévu a priori)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
