# STORY-102 : Rate limiting effectif sans Redis — fallback mémoire + warning (P0-3)

**Statut :** TODO
**Epic Parent :** EPIC-011 — P0 : Sécurité bloquante
**Item plan :** P0-3 (rapport d'écart B2, §7) — ampleur **M**

## Description

En tant qu'administrateur sécurité de WindFlow, je veux que le rate limiting reste effectif même sans Redis configuré, via un limiteur mémoire process-local en fenêtre glissante, afin que les endpoints protégés (dont `POST /auth/login` à 5/min) ne soient plus librement bombardables sur les installations en mode léger (Raspberry Pi, SQLite, sans Redis).

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §2.2, §10.1, §14.2) : [`conditional_rate_limiter()`](../../backend/app/core/rate_limit.py:18) est un **no-op sans Redis** — l'init de FastAPILimiter au startup ne se fait que si `rate_limit_enabled` **ET** `rate_limit_storage_url` sont présents (dégradation silencieuse, ligne [`rate_limit.py`](../../backend/app/core/rate_limit.py:43)). Résultat : sur une installation sans `RATE_LIMIT_STORAGE_URL`, **tous** les limiteurs (`strict` 5/min, `moderate` 30/min, `relaxed` 100/min) sont inactifs, y compris sur le login. La spec exige l'inverse : « Rate limiting sur login » est une mesure **core toujours active** (15-securite.md), fonctionnant « dans les deux profils de déploiement » (07-authentification.md § Protection brute-force).

## Contexte technique

*(à remplir par analyse-story)*

Points d'appui existants :
- [`rate_limit.py`](../../backend/app/core/rate_limit.py:18) : `conditional_rate_limiter()` + alias `strict/moderate/relaxed` (5/30/100 par min) — l'API des décorateurs est déjà consommée par les routers, garder la façade inchangée ;
- Startup lifespan ([`main.py`](../../backend/app/main.py:59)) : init FastAPILimiter Redis conditionnelle à remplacer par une stratégie Redis **ou** mémoire ;
- Principe d'optionalité : « quand une dépendance n'est pas indispensable (Redis…), elle doit avoir un fallback léger (cache mémoire…) » (05-stack-technologique.md § Principes) ;
- Limite connue assumée : le fallback mémoire est **process-local** (non partagé entre workers multiples) — le warning de démarrage doit le mentionner ; non-régression requise avec Redis configuré (chemin actuel).

## Critères d'acceptation (AC)

- [ ] AC 1 : Sans `RATE_LIMIT_STORAGE_URL`, les limiteurs déployés via [`conditional_rate_limiter()`](../../backend/app/core/rate_limit.py:18) deviennent **effectifs en mémoire** (fenêtre glissante process-local, nettoyage des entrées expirées pour éviter toute fuite mémoire) ; l'API des alias `strict` (5/min), `moderate` (30/min), `relaxed` (100/min) est préservée — aucun changement requis côté routers.
- [ ] AC 2 : Test de done du plan vérifié : **sans `RATE_LIMIT_STORAGE_URL`, 6 requêtes/min sur `/auth/login` → 429** ; un **warning unique** (pas répété à chaque requête) est émis dans les logs au démarrage/primer usage, mentionnant le mode mémoire process-local et sa limite (non-partagé entre workers).
- [ ] AC 3 : Avec `RATE_LIMIT_STORAGE_URL` configuré, le comportement Redis actuel est **strictement préservé** (chemin FastAPILimiter existant, aucune régression des tests d'intégration rate limiting déjà bons — `backend_status.md` §13.3 « Middleware/sécurité »).
- [ ] AC 4 : Plus aucune dégradation silencieuse : l'état du rate limiting (Redis vs mémoire vs désactivé) est observable dans les logs de démarrage ; `rate_limit_enabled=false` reste un choix explicite documenté.
- [ ] AC 5 : Tests écrits et passants : `test_memory_limiter_returns_429_after_threshold` (6e requête dans la fenêtre), `test_memory_limiter_window_resets_after_expiry`, `test_memory_limiter_distinct_keys_per_identifier`, `test_no_repeated_warning_in_logs`, `test_redis_path_unchanged_when_configured`, `test_expired_entries_cleanup` — `make lint` + `make backend-test` verts.

## Références spécification

- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) § Vue d'ensemble → Principes (« le rate limiting est actif — sans configuration supplémentaire ») et § Ce qui est core vs plugin (« Rate limiting sur login » = core) ;
- [`docs/general_specs/07-authentification.md`](../../docs/general_specs/07-authentification.md) § Protection brute-force — compteur « Redis en mode standard, mémoire en mode léger », fonctionne « dans les deux profils de déploiement » ;
- [`docs/general_specs/04-architecture.md`](../../docs/general_specs/04-architecture.md) § Résilience et performance — stratégies pragmatiques attendues (le fallback mémoire est l'application au rate limiting) ;
- [`docs/general_specs/05-stack-technologique.md`](../../docs/general_specs/05-stack-technologique.md) § Principes — « Optionalité : quand une dépendance n'est pas indispensable (Redis, PostgreSQL), elle doit avoir un fallback léger (cache mémoire, SQLite) » ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §2.2 (dégradation silencieuse au startup), §10.1 (`conditional_rate_limiter` no-op sans Redis), §14.2 ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 Vague P0 — item P0-3, §2.B — item B2.

## Dépendances

- Aucune en amont (item racine de la vague P0).
- **Dépendance descendante** : STORY-104 (brute-force login) réutilise cette même mécanique de stockage Redis-ou-mémoire — implémenter 102 **avant** 104 (déjà noté dans le plan : P0-5 « Dépend de P0-3 (même mécanique de stockage) »).

## Sous-stories

*(section réservée — STORY-102 ampleur M, découpage non prévu a priori)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
