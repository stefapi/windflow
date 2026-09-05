# STORY-102 : Rate limiting effectif sans Redis — fallback mémoire + warning (P0-3)

**Statut :** DONE
**Epic Parent :** EPIC-011 — P0 : Sécurité bloquante
**Item plan :** P0-3 (rapport d'écart B2, §7) — ampleur **M**

## Description

En tant qu'administrateur sécurité de WindFlow, je veux que le rate limiting reste effectif même sans Redis configuré, via un limiteur mémoire process-local en fenêtre glissante, afin que les endpoints protégés (dont `POST /auth/login` à 5/min) ne soient plus librement bombardables sur les installations en mode léger (Raspberry Pi, SQLite, sans Redis).

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §2.2, §10.1, §14.2) : [`conditional_rate_limiter()`](../../backend/app/core/rate_limit.py:18) est un **no-op sans Redis** — l'init de FastAPILimiter au startup ne se fait que si `rate_limit_enabled` **ET** `rate_limit_storage_url` sont présents (dégradation silencieuse, ligne [`rate_limit.py`](../../backend/app/core/rate_limit.py:43)). Résultat : sur une installation sans `RATE_LIMIT_STORAGE_URL`, **tous** les limiteurs (`strict` 5/min, `moderate` 30/min, `relaxed` 100/min) sont inactifs, y compris sur le login. La spec exige l'inverse : « Rate limiting sur login » est une mesure **core toujours active** (15-securite.md), fonctionnant « dans les deux profils de déploiement » (07-authentification.md § Protection brute-force).

## Contexte technique

**Couches impactées :** Backend uniquement (core/rate_limit.py, main.py startup, tests). Frontend/CLI non impactés — l'API de la façade est inchangée pour les ~110 call-sites.

### Constat d'exploration

1. **La façade réelle est la fonction** `conditional_rate_limiter(times, seconds)` : ~110 usages directs dans les routers (`auth.py`, `docker.py`, `stacks.py`, `deployments.py`, `users.py`, `organizations.py`, `plugins.py`, `targets/*`…) avec des valeurs variées (3→100 req/60 s). Les alias `rate_limit_strict/moderate/relaxed` ([rate_limit.py:50-62](../../backend/app/core/rate_limit.py)) ne sont utilisés **que dans les tests** — les préserver aussi, mais le contrat critique est celui de la fonction.
2. `RateLimiter` (fastapi-limiter) **exige** `FastAPILimiter.init()` au préalable — sinon erreur runtime (`Limiter is not initialized`). C'est la raison du no-op actuel. Le fallback mémoire doit donc être une **dépendance FastAPI standalone** (callable async acceptant `Request`), pas un `RateLimiter`.
3. Clé fastapi-limiter = `{request.client.host}:{route.path}` — le fallback mémoire réplique ce schéma pour rester cohérent (AC 5 `distinct_keys_per_identifier`).
4. **Tests d'intégration existants** ([`test_rate_limiting.py`](../../backend/tests/integration/test_rate_limiting.py)) assertent le no-op actuel (`test_conditional_rate_limiter_returns_noop` l.44, `test_conditional_rate_limiter_noop_allows_request` l.55, `test_rate_limit_no_429_without_redis` l.25, `test_rate_limit_headers_not_present_without_redis` l.34, `test_multiple_rapid_requests_without_rate_limit` l.127) → **à mettre à jour** : le comportement sans Redis devient « 429 après seuil » (divergence inévitable, validée).
5. Config : `rate_limit_enabled=True` par défaut ([config.py:181](../../backend/app/config.py)), `rate_limit_storage_url=None` par défaut — le cas « sans Redis » est le mode léger par défaut (RPi/SQLite).
6. Init lifespan actuel ([main.py:105-121](../../backend/app/main.py)) : tente Redis si les 2 conditions, sinon warning de dégradation — à remplacer par une stratégie à 3 états observable.

### Fichiers de référence (patterns)

- Dépendance de rate limiting → pattern du `no_op_limiter` existant (callable async `(request: Request)`)
- Exception HTTP de refus → `HTTPException(status_code=429, detail=..., headers={"Retry-After": ...})` (fastapi-limiter fait de même)
- Tests unitaires → pattern [`test_production_guard.py`](../../backend/tests/unit/test_config/test_production_guard.py) (isolation via patch settings)
- Tests d'intégration client → pattern [`conftest.py`](../../backend/tests/conftest.py) fixture `client`

**Exigences sécurité identifiées :**
- Auth : non applicable (middleware transverse, s'applique avant l'authentification)
- Identification : clé = IP client + path (cohérent fastapi-limiter) ; fenêtre glissante par deque de timestamps
- Fuite mémoire : purge des timestamps expirés à chaque check + éviction des clés vides ; cap raisonnable (ex. purge périodique des clés inactives > 10 min)
- Exposition : warning sans données sensibles (IPs jamais loggées)
- Audit : état du rate limiting observable au démarrage (Redis / mémoire / désactivé) — fin de la dégradation silencieuse (AC 4)

### Décisions de conception (validées par l'utilisateur)

- **`MemoryRateLimiter`** : classe simple (dict[str, deque[timestamp]]), méthode `check(key, times, seconds) -> bool`, purge à chaque appel — aucune dépendance, thread-safety via single event loop asyncio (documenté)
- **3 branches** dans `conditional_rate_limiter()` : Redis → `RateLimiter` (inchangé) ; pas d'URL + enabled → dépendance mémoire (warning **unique** via flag module) ; disabled → no-op explicite
- **Warning unique** émis au premier usage (pas au startup) — les décorateurs s'exécutent à l'import des routers, potentiellement avant le lifespan
- **429 avec `Retry-After`** (header calculé depuis la fenêtre) — prépare STORY-104
- **Divergence assumée** : tests d'intégration no-op réécrits pour le nouveau comportement (documenté en notes)

Points d'appui existants :
- [`rate_limit.py`](../../backend/app/core/rate_limit.py:18) : `conditional_rate_limiter()` + alias `strict/moderate/relaxed` (5/30/100 par min) — l'API des décorateurs est déjà consommée par les routers, garder la façade inchangée ;
- Startup lifespan ([`main.py`](../../backend/app/main.py:59)) : init FastAPILimiter Redis conditionnelle à remplacer par une stratégie Redis **ou** mémoire ;
- Principe d'optionalité : « quand une dépendance n'est pas indispensable (Redis…), elle doit avoir un fallback léger (cache mémoire…) » (05-stack-technologique.md § Principes) ;
- Limite connue assumée : le fallback mémoire est **process-local** (non partagé entre workers multiples) — le warning de démarrage doit le mentionner ; non-régression requise avec Redis configuré (chemin actuel).

## Critères d'acceptation (AC)

- [x] AC 1 : Sans `RATE_LIMIT_STORAGE_URL`, les limiteurs déployés via [`conditional_rate_limiter()`](../../backend/app/core/rate_limit.py) deviennent **effectifs en mémoire** (fenêtre glissante process-local, nettoyage des entrées expirées pour éviter toute fuite mémoire) ; l'API des alias `strict` (5/min), `moderate` (30/min), `relaxed` (100/min) est préservée — aucun changement requis côté routers. ✅ `MemoryRateLimiter` (deque par clé, purge à chaque check + purge périodique 5 min) ; façade signature inchangée pour les ~110 call-sites ; tests `test_allows_under_threshold_then_blocks`, `test_aliases_return_effective_limiters`.
- [x] AC 2 : Test de done du plan vérifié : **sans `RATE_LIMIT_STORAGE_URL`, 6 requêtes/min sur `/auth/login` → 429** ; un **warning unique** (pas répété à chaque requête) est émis dans les logs au démarrage/primer usage, mentionnant le mode mémoire process-local et sa limite (non-partagé entre workers). ✅ tests `test_memory_limiter_returns_429_after_threshold` (seuil 5 → 6e = 429), `test_no_repeated_warning_in_logs` (1 seul warning), `test_warning_mentions_process_local_limitation` (« process-local » + « workers »), `test_memory_dependency_returns_429_with_retry_after` (Retry-After).
- [x] AC 3 : Avec `RATE_LIMIT_STORAGE_URL` configuré, le comportement Redis actuel est **strictement préservé** (chemin FastAPILimiter existant, aucune régression des tests d'intégration rate limiting déjà bons — `backend_status.md` §13.3 « Middleware/sécurité »). ✅ branche Redis identique (retour `RateLimiter` inchangé) ; test `test_redis_path_unchanged_when_configured` (instance + times + milliseconds).
- [x] AC 4 : Plus aucune dégradation silencieuse : l'état du rate limiting (Redis vs mémoire vs désactivé) est observable dans les logs de démarrage ; `rate_limit_enabled=false` reste un choix explicite documenté. ✅ startup 3 états loggés ([main.py](../../backend/app/main.py)) + `test_disabled_returns_explicit_noop` (log INFO « désactivé — choix explicite »).
- [x] AC 5 : Tests écrits et passants : `test_memory_limiter_returns_429_after_threshold` (6e requête dans la fenêtre), `test_memory_limiter_window_resets_after_expiry`, `test_memory_limiter_distinct_keys_per_identifier`, `test_no_repeated_warning_in_logs`, `test_redis_path_unchanged_when_configured`, `test_expired_entries_cleanup` — `make lint` + `make backend-test` verts. ✅ les 6 tests exigés présents nommément dans [`test_rate_limit.py`](../../backend/tests/unit/test_core/test_rate_limit.py) (18 tests unitaires + 9 intégration = 27) ; couverture `rate_limit.py` **100%** ; flake8/black/isort verts ; suite complète 910/910.

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

- [x] Tâche 1 : Classe `MemoryRateLimiter` (fenêtre glissante + purge)
- [x] Tâche 2 : Façade `conditional_rate_limiter()` v2 (3 branches + warning unique)
- [x] Tâche 3 : Startup main.py — logs d'état observables
- [x] Tâche 4 : Tests unitaires `test_rate_limit.py`
- [x] Tâche 5 : Mise à jour tests d'intégration `test_rate_limiting.py`
- [x] Tests unitaires backend
- [x] Build & lint OK

## Notes d'implémentation

**Date :** 2026-09-05

### Fichiers modifiés/créés

- `backend/app/core/rate_limit.py` — Réécrit : `MemoryRateLimiter` (fenêtre glissante deque, purge par check + périodique `MEMORY_LIMITER_PURGE_INTERVAL=300`, `reset()`) ; `_memory_limiter` module-level ; flags `_memory_warning_emitted`/`_disabled_info_emitted` ; `conditional_rate_limiter()` v2 en 3 branches (Redis inchangé / mémoire 429+Retry-After / no-op explicite loggé) ; alias préservés
- `backend/app/main.py` — Bloc rate limiter restructuré en 3 états observables ; URL Redis masquée (`re.sub(r"://[^@/]+@", "://***@", ...)`) ; échec Redis bascule explicitement en mémoire
- `backend/tests/unit/test_core/__init__.py` — créé
- `backend/tests/unit/test_core/test_rate_limit.py` — créé : 18 tests (7 classe pure + 11 façade)
- `backend/tests/integration/test_rate_limiting.py` — réécrit : 9 tests alignés sur le nouveau comportement (divergence validée)
- `backend/tests/conftest.py` — fixture autouse `_reset_rate_limit_store` (isolation inter-tests)

### Décisions techniques

- Clé mémoire `f"{client.host}:{url.path}"` (cohérent fastapi-limiter) ; fallback `"unknown"` si client absent
- Warning unique émis au **premier appel de la façade** (pas au startup) car les décorateurs s'exécutent à l'import des routers
- `Retry-After: str(seconds)` sur le 429 (prépare STORY-104)
- Attribut fastapi-limiter 0.1.6 : la fenêtre s'appelle `milliseconds` (test adapté)

### Divergences par rapport à l'analyse

- **Fixture conftest.py ajoutée** (non prévue à l'analyse) : le store mémoire étant global au process, les suites de tests d'API (login par `authenticated_client`) dépassaient le quota `/auth/login` 5/min dès le 6e test → 7 FAILED + 77 ERROR en suite complète. Fixture autouse reset le store entre chaque test. Comportement de production inchangé (c'est précisément l'efficacité du garde-fou qui se manifestait).
- Tests d'intégration : réécrits conformément au plan validé (l'ancien `test_rate_limit_no_429_without_redis` devient `test_memory_limiter_429_kicks_in_without_redis`, etc.)

### Difficultés rencontrées

- Régression suite complète (429 en cascade) diagnostiquée puis résolue via la fixture conftest — voir divergences
- Environnement : venv de secours `.venv-test` (même situation que STORY-100/101, documentée)

### Tests ajoutés

- `backend/tests/unit/test_core/test_rate_limit.py` : 18/18 passants
- `backend/tests/integration/test_rate_limiting.py` : 9/9 passants (réécrits)
- Couverture : `app/core/rate_limit.py` **100%** ; suite unitaire complète **910/910** ; flake8 + black + isort verts

## Tâches d'implémentation détaillées

### Tâche 1 : Classe `MemoryRateLimiter` (fenêtre glissante + purge)
**Objectif :** Créer le limiteur mémoire process-local qui remplace le no-op : une fenêtre glissante par clé (deque de timestamps), avec purge des entrées expirées à chaque check pour éviter toute fuite mémoire.
**Fichiers :**
- `backend/app/core/rate_limit.py` — Modifier — Ajouter en tête de module (avant `conditional_rate_limiter`) :
  1. Import `time` (monotonic) et `from collections import deque`.
  2. Instance module-level `_memory_limiter: MemoryRateLimiter = MemoryRateLimiter()` (partagée par toutes les dépendances — cohérent avec le compteur global de fastapi-limiter).
  3. Classe `MemoryRateLimiter` :
     - `__init__(self) -> None` : `self._windows: dict[str, deque[float]] = {}` et compteur simple pour stats éventuelles
     - `check(self, key: str, times: int, seconds: float) -> bool` — purger les timestamps `< now - seconds` de la deque de la clé (popleft tant que expirés ; si deque vide → supprimer la clé du dict) ; si `len(window) >= times` → retourner `False` (refusé) ; sinon append `time.monotonic()` et retourner `True`. Docstring documentant : fenêtre glissante, process-local, non-partagé entre workers, sûre en event loop unique (mutations atomiques entre awaits).
     - `purge_expired(self) -> None` — parcours de toutes les clés, purge des timestamps expirés et éviction des clés vides (appelé périodiquement — garde-fou fuite mémoire sur clés à usage unique)
     - `reset(self) -> None` — vide tout (utilisé par les tests)
  4. Constante `MEMORY_LIMITER_PURGE_INTERVAL: int = 300` + timestamp `_last_purge` : `check()` déclenche `purge_expired()` tous les 5 min max (amortisé).
**Exigences sécurité :** Aucune donnée sensible stockée (clés = IP+path, timestamps) ; aucune IP loggée.
**Dépend de :** Aucune

### Tâche 2 : Façade `conditional_rate_limiter()` v2 (3 branches + warning unique)
**Objectif :** Remplacer la logique no-op : Redis → `RateLimiter` inchangé ; sinon enabled → dépendance mémoire effective ; sinon no-op explicite. Warning unique au premier usage mémoire.
**Fichiers :**
- `backend/app/core/rate_limit.py` — Modifier — Réécrire `conditional_rate_limiter(times, seconds)` (signature inchangée) :
  1. Si `settings.rate_limit_enabled and settings.rate_limit_storage_url` → `return RateLimiter(times=times, seconds=seconds)` (chemin Redis **strictement identique**, AC 3).
  2. Sinon si `settings.rate_limit_enabled` (sans URL) → émettre le **warning unique** (flag module-level `_memory_warning_emitted: bool`, logger dédié `windflow.rate_limit`) : « Rate limiting actif en mode mémoire process-local (sans RATE_LIMIT_STORAGE_URL) — les compteurs ne sont PAS partagés entre workers ; définir RATE_LIMIT_STORAGE_URL=redis://… pour un comptage distribué » — puis retourner une **closure** `async def memory_limiter(request: Request)` qui : construit la clé `f"{request.client.host}:{request.url.path}"` (fallback `"unknown"` si client absent), appelle `_memory_limiter.check(key, times, seconds)` ; si refusé → `raise HTTPException(status_code=429, detail="Too many requests", headers={"Retry-After": str(seconds)})` (import `HTTPException` depuis fastapi).
  3. Sinon (`rate_limit_enabled=false`) → no-op explicite **avec log INFO unique** « Rate limiting désactivé (RATE_LIMIT_ENABLED=false) — choix explicite » (fin de la dégradation silencieuse, AC 4).
  4. Mettre à jour la docstring du module et de la fonction (3 modes).
**Exigences sécurité :** 429 + `Retry-After` ; warning sans IP ; aucun log par requête.
**Dépend de :** Tâche 1

### Tâche 3 : Startup main.py — logs d'état observables
**Objectif :** Rendre l'état du rate limiting observable au démarrage (AC 4) et anticiper le warning mémoire avant le premier hit.
**Fichiers :**
- `backend/app/main.py` — Modifier — Dans le lifespan, remplacer le bloc conditionnel actuel (l.105-121 : if enabled and url → Redis ; elif enabled → 2 warnings) par une structure à 3 états loggée :
  1. Redis OK (si enabled + URL) → init FastAPILimiter (code inchangé) + `logger.info("✓ Rate limiting: Redis distribué (%s)", url_sans_credentials)` ;
  2. enabled sans URL → `logger.warning("⚠ Rate limiting: mémoire process-local (RATE_LIMIT_STORAGE_URL absent) — compteurs non partagés entre workers")` (le warning runtime unique de la Tâche 2 reste pour le premier hit) ;
  3. disabled → `logger.warning("⚠ Rate limiting: DÉSACTIVÉ (RATE_LIMIT_ENABLED=false)")`.
  Nota : masquer les credentials éventuels de l'URL Redis dans le log (regex `://[^@]+@` → `://***@`).
**Exigences sécurité :** Log sans credentials ni IPs.
**Dépend de :** Tâche 2

### Tâche 4 : Tests unitaires `test_rate_limit.py`
**Objectif :** Couvrir `MemoryRateLimiter` et la façade v2 — les 6 tests exigés par l'AC 5 + cas complémentaires.
**Fichiers :**
- `backend/tests/unit/test_core/__init__.py` — Créer — Package vide si absent (vérifier l'existant).
- `backend/tests/unit/test_core/test_rate_limit.py` — Créer — (pattern : [`test_production_guard.py`](../../backend/tests/unit/test_config/test_production_guard.py)) — patcher `settings` pour chaque scénario, `_memory_limiter.reset()` en setup. Voir section Tests.
**Exigences sécurité :** Aucune valeur sensible.
**Dépend de :** Tâches 1, 2

### Tâche 5 : Mise à jour tests d'intégration `test_rate_limiting.py`
**Objectif :** Aligner les tests d'intégration sur le nouveau comportement (divergence validée) : sans Redis → 429 après seuil ; Redis → inchangé.
**Fichiers :**
- `backend/tests/integration/test_rate_limiting.py` — Modifier —
  1. `test_conditional_rate_limiter_returns_noop` (l.44) → renommer `test_conditional_rate_limiter_returns_memory_dependency` : sans URL + enabled → callable ; appel avec `Request` mockée → pas d'exception sous le seuil.
  2. `test_conditional_rate_limiter_noop_allows_request` (l.55) → réécrire : sous le seuil (ex. limite 10, 5 appels) → autorisé ; au-delà → HTTPException 429.
  3. `test_rate_limit_no_429_without_redis` (l.25) → renommer `test_rate_limit_429_kick_in_without_redis_after_threshold` : `/health` n'a PAS de limiteur (route non décorée) — assertions sur les dépendances directement plutôt que via `/health` ; OU frapper 6× une route décorée si accessible sans auth. Conserver l'esprit : sans Redis le limiting est EFFECTIF.
  4. `test_rate_limit_headers_not_present_without_redis` (l.34) → vérifier plutôt que `Retry-After` est **présent** sur le 429 (ou retirer si non testable proprement).
  5. `test_multiple_rapid_requests_without_rate_limit` (l.127) → réécrire avec une dépendance mémoire à seuil bas (ex. 3) : 3 OK puis 429.
  6. `test_auth_endpoints_have_rate_limiting` (l.99) et `test_organization_endpoints_have_rate_limiting` (l.111) : inchangés (vérifient la présence des dépendances).
  7. `test_rate_limit_aliases` (l.81) : inchangé.
**Exigences sécurité :** Aucune.
**Dépend de :** Tâches 1, 2, 4

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md` — sécurité : `.clinerules/40-security.md`
> Isolation : patch `settings.rate_limit_enabled` / `rate_limit_storage_url` ; `_memory_limiter.reset()` en setup de chaque test ; `time.monotonic` patchable pour la fenêtre.

### Unitaires Backend — `backend/tests/unit/test_core/test_rate_limit.py`

Classe `TestMemoryRateLimiter` (tests purs de la classe) :
- `test_memory_limiter_returns_429_after_threshold` — **AC 5** : `check(key, 5, 60)` → 5× True puis 6e → False (via la dépendance : HTTPException 429)
- `test_memory_limiter_window_resets_after_expiry` — **AC 5** : après `times` refus, avancer le temps (patch `time.monotonic` + 61 s) → à nouveau True
- `test_memory_limiter_distinct_keys_per_identifier` — **AC 5** : clé A épuisée → clé B toujours True (isolation par IP+path)
- `test_expired_entries_cleanup` — **AC 5** : peupler des clés, expirer, appeler `purge_expired()` → le dict interne ne contient plus les clés vides
- `test_check_purges_on_each_call` — les timestamps expirés sont purgés à chaque check (deque raccourcie)
- `test_exact_threshold_boundary` — exactement `times` appels OK, le suivant refusé (pas de off-by-one)
- `test_reset_clears_all_state` — `reset()` vide les fenêtres

Classe `TestConditionalRateLimiterV2` (façade) :
- `test_no_repeated_warning_in_logs` — **AC 5** : 2 appels à `conditional_rate_limiter(5, 60)` sans URL → `caplog` ne contient le warning mémoire qu'**une** fois
- `test_redis_path_unchanged_when_configured` — **AC 5 / AC 3** : URL configurée → retourne une instance de `RateLimiter` (type exact, times/seconds propagés)
- `test_disabled_returns_explicit_noop` — `rate_limit_enabled=false` → callable no-op, log INFO explicite unique
- `test_memory_dependency_returns_429_with_retry_after` — la dépendance mémoire lève HTTPException 429 avec header `Retry-After` au-delà du seuil
- `test_memory_key_uses_ip_and_path` — Request mockée (client.host=1.2.3.4, path=/auth/login) → la clé utilisée est `1.2.3.4:/auth/login` (via introspection du store)
- `test_warning_mentions_process_local_limitation` — le texte du warning contient « process-local » et « workers » (AC 2)
- `test_aliases_return_effective_limiters` — `rate_limit_strict()/moderate()/relaxed()` → callables effectifs sans Redis (5/30/100)

### Intégration — `backend/tests/integration/test_rate_limiting.py` (mise à jour)
- Sans Redis + enabled : 6 appels d'une dépendance seuil 5 → 429 au 6e ; sous le seuil → 200
- Redis configuré (mock FastAPILimiter.init) : chemin inchangé
- Routes auth décorées : présence des dépendances (inchangé)

### Commandes de validation
```bash
cd backend && poetry run pytest tests/unit/test_core/test_rate_limit.py -v --tb=short
cd backend && poetry run pytest tests/integration/test_rate_limiting.py -v --tb=short
make backend-lint && make backend-test-unit
```
