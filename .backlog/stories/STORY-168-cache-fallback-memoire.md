# STORY-168 : Cache avec fallback mémoire — interface unique get/set/delete + TTL, Redis si configuré sinon mémoire locale, utilisée par rate limiter, plugin registry et caches divers (P2-8 — axes C7, E4)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-8 (axes C7, E4, rapports §6) — ampleur **M**

## Description

En tant que développeur backend WindFlow, je veux une **interface de cache unique** (get/set/delete avec TTL) instanciée avec Redis quand il est configuré et un fallback mémoire locale sinon — consommée par le rate limiter, le plugin registry (cache TTL 300 s), le cache RBAC et les caches divers — afin de supprimer les dégradations silencieuses en no-op et les implémentations de cache dispersées, avec un warning explicite en mode dégradé.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §10.1, §14.2) : sans Redis, [`rate_limit.py:43`](../../backend/app/core/rate_limit.py:43) est un **no-op** (le fallback mémoire dédié de STORY-102 traite le login mais pas les autres limiteurs) ; le plugin registry porte son propre cache TTL ([`plugin_registry_service.py:23`](../../backend/app/services/plugin_registry_service.py:23)) ; l'ABC [`CacheManager`](../../backend/app/core/abstractions.py:13) est un contrat **non consommé** (E4 : « ressusciter `CacheManager` via C7 ») ; le plan exige un `core/cache.py` unique avec TTL mémoire et warning de dégradation.

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- **Interface** : ressusciter/adapter l'ABC `CacheManager` de [`core/abstractions.py:13`](../../backend/app/core/abstractions.py:13) (décision E4) dans un nouveau [`core/cache.py`](../../backend/app/core/cache.py) — méthodes get/set/delete + TTL (+ incrément/compteur si nécessaire pour le rate limiting et le brute-force) ;
- **Deux implémentations** : Redis (activé quand `cache_url`/Redis est configuré — même détection que le bus STORY-162) et mémoire locale process-local avec TTL respecté (mode léger RPi, spec 04 § Performance : « cache dict en mémoire remplace Redis avec les mêmes TTL ») ;
- **Warning de dégradation** : un warning unique (pas répété à chaque appel) quand le fallback mémoire est actif ; échec Redis en cours de route → bascule mémoire avec log ;
- **Consommateurs à brancher** : rate limiter ([`core/rate_limit.py:18`](../../backend/app/core/rate_limit.py:18) — harmoniser avec le fallback de STORY-102 sans double implémentation), plugin registry (TTL 300 s, timeout 10 s — [`plugin_registry_service.py:23`](../../backend/app/services/plugin_registry_service.py:23)), **cache RBAC TTL 300 s** (posé par STORY-121/122 — dépendance P1-2 du plan pour P2-8), caches divers identifiés à l'analyse ;
- **Ne pas casser** : `disable_auth` dev, comportement des limiteurs strict/moderate/relaxed (5/30/100 par min) ;
- Décision E4 connexe : `DatabaseManager` (l'autre ABC d'`abstractions.py`) est **hors périmètre** ici — son sort est statué par P3-1 (purge si non consommé) ;
- Spéc 15 § principes : aucune donnée sensible en clair dans les clés/valeurs de cache.

## Critères d'acceptation (AC)

- [ ] AC 1 : L'interface de cache unique existe (`core/cache.py`, contractée sur `CacheManager`) avec get/set/delete + TTL ; **sans Redis**, le cache mémoire fonctionne (test : set avec TTL → get avant expiration retourne la valeur, après expiration retourne rien) et **un warning de dégradation est émis** (une fois, vérifié en logs).
- [ ] AC 2 : **Avec Redis**, les clés sont visibles dans Redis (test d'intégration avec Redis réel : set → `KEYS`/`GET` côté Redis, TTL exposé) ; un échec de connexion Redis en cours d'exécution bascule sur mémoire avec log sans faire échouer l'appelant.
- [ ] AC 3 : Le **rate limiter** consomme l'interface unique : sans `RATE_LIMIT_STORAGE_URL`, les limiteurs ne sont plus des no-op (test : limite dépassée → 429), en cohérence/harmonie avec le fallback STORY-102 (une seule implémentation partagée) ; le **plugin registry** consomme l'interface (TTL 300 s respecté, test de péremption) ; le **cache RBAC TTL 300 s** (STORY-121/122) est migré sur l'interface (test : changement de rôle pris en compte au plus tard 300 s après).
- [ ] AC 4 : Tests de sécurité/non-régression : aucun secret/token en clair dans les entrées de cache ; `disable_auth` et les limites par défaut non régressés ; consommation CPU/mémoire bornée (le cache mémoire a une taille maximale ou une politique d'éviction simple).
- [ ] AC 5 : Couverture ≥ 80 % sur `core/cache.py` et les consommateurs modifiés ; build + lint + tests passent.

## Références spécification

- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § Performance (cache Redis en mode standard, cache dict en mémoire avec mêmes TTL en mode léger), § Profils de déploiement (brique Redis optionnelle) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Rate limiting (protection des endpoints sensibles), § Principes (pas de données sensibles en clair) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Rate limiting (limites par endpoint) ;
- [ARCHITECTURE-MODULAIRE.md](../../docs/technical_specs/ARCHITECTURE-MODULAIRE.md) — brique `cache` (Redis optionnel, activation) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-8, §2.C C7 (« dégradation silencieuse en no-op → warning + TTL mémoire »), §2.E E4 (CacheManager), §2.B B2 ;
- [`backend_status.md`](../../docs/backend_status.md) — §10.1 (`CacheManager` non consommé, rate limit no-op sans Redis), §3.15 (registry cache TTL 300 s), §11 (config Redis).

## Dépendances

- **STORY-121/STORY-122** (cache RBAC TTL 300 s posé en P1 — le plan marque P2-8 dépendant de P1-2 pour le consommateur RBAC).
- Harmonisation avec **STORY-102** (fallback mémoire rate limiting P0) — une seule implémentation à terme ; interagit avec **STORY-162** (même détection Redis) et prépare **P3-1** (statut de `DatabaseManager`).

## Sous-stories

*(non prévue — story M)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
