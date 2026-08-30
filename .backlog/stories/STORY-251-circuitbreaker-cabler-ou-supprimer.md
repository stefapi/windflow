# STORY-251 : CircuitBreaker — câbler sur les appels externes ou supprimer (P3-2)

**Statut :** TODO
**Epic Parent :** EPIC-014 — P3 : Finitions & purge (remédiation backend)
**Item plan :** P3-2 (axe E2) — ampleur **M**

## Description

En tant que développeur WindFlow, je veux statuer définitivement sur le module [`core/resilience.py`](../../backend/app/core/resilience.py) : soit **(a) câbler le `CircuitBreaker`** sur les appels externes (SSH, Docker, registre plugins) avec des seuils configurés, soit **(b) supprimer le module** (code mort), afin que la résilience annoncée par la spec 04 soit réelle et non décorative.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §4.5, §17) : `CircuitBreaker`/`RetryPolicy`/`HealthCheck` existent dans [`resilience.py`](../../backend/app/core/resilience.py) mais **0 import dans l'application** — le module est décoratif. Le plan recommande le câblage (option a) : « Conforme spec 04 "résilience" sans dupliquer » — le retry existe déjà dans l'orchestrateur ([`deployment_orchestrator.py:21`](../../backend/app/services/deployment_orchestrator.py:21), backoff lignes 36-38) et `HealthCheck` est redondant avec [`target_service.check_all_health()`](../../backend/app/services/target_service.py:30) (sa purge est portée par STORY-250).

## Contexte technique

*(à remplir par analyse-story)*

Deux options documentées — la **recommandation du plan est l'option (a)** :

**Option (a) — Câbler (recommandée, plan §2.E E2)** :
- Point d'accroche naturel : le **`WorkloadAdapter`** de STORY-174 (EPIC-013) — le circuit breaker enveloppe les appels Docker distants passant par l'adapter, sans réécrire les exécuteurs ;
- Périmètre d'appels externes à protéger : appels **Docker distants** (via [`docker_executor.py:76`](../../backend/app/services/docker_executor.py:76)), appels **SSH** (via [`commands.py`](../../backend/app/services/commands.py:167)), appels au **registre plugins** ([`plugin_registry_service.py:23`](../../backend/app/services/plugin_registry_service.py:23)) ;
- Seuils configurés et exposés dans la configuration (settings Pydantic) : `failure_threshold` (défaut 5), `timeout` (défaut 60 s), `half_open_timeout` (défaut 30 s) — valeurs actuelles du constructeur [`resilience.py:44`](../../backend/app/core/resilience.py:44) ;
- **Métrique exposée** : état des circuits (état, compteur d'échecs) intégré à `/metrics` (instrumentation posée par STORY-172) ;
- Ne **pas** dupliquer le retry existant de l'orchestrateur (§2.G — le backoff de `deployment_orchestrator.py` est conservé) ;
- Comportement : cible Docker défaillante → circuit **ouvert après N échecs consécutifs** (appels suivants rejetés immédiatement sans tentative), **demi-ouvert après délai** (tentatives limitées), **fermé** après succès.

**Option (b) — Supprimer (si l'option (a) est refusée à l'analyse)** :
- Suppression du module `core/resilience.py` + décorateur `circuit_breaker` ;
- La spec 04 § Résilience est alors à ajuster (coordination avec STORY-252) pour ne plus annoncer un circuit breaker non livré ;
- Cette option laisse la résilience reposer uniquement sur le retry/backoff de l'orchestrateur — moins conforme à la spec.

Arbitrage : l'option appartient in fine à l'utilisateur si l'analyse révèle un coût disproportionné du câblage ; par défaut, suivre la recommandation du plan (option a).

## Critères d'acceptation (AC)

- [ ] AC 1 : Test de comportement — une cible Docker défaillante (mockée) entraîne l'**ouverture du circuit après N échecs** configurés (appels rejetés immédiatement, sans tentative réseau), puis passage en **demi-ouvert après le délai** configuré, et refermeture après succès.
- [ ] AC 2 : Le CircuitBreaker est câblé sur les appels Docker distants **via le `WorkloadAdapter`** (STORY-174) — les seuils sont **configurés** (settings + documentation) et ne dupliquent pas le retry existant de l'orchestrateur (non-régression des déploiements).
- [ ] AC 3 : L'état des circuits est **exposé dans `/metrics`** (état, échecs cumulés — instrumentation STORY-172) et tracé dans les logs structurés aux transitions (ouverture/fermeture), avec correlation_id.
- [ ] AC 4 : Si l'option (b) suppression est retenue à l'issue de l'analyse : module supprimé, aucune référence résiduelle, spec 04 ajustée en coordination avec STORY-252, décision argumentée dans les notes d'implémentation.
- [ ] AC 5 : Non-régression des déploiements et des points forts §2.G ; build + lint + tests passent ; couverture ≥ 80 % sur les modules touchés.

## Références spécification

- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — **§ Résilience et fiabilité** (stratégies adaptées : circuit breaker attendu sur appels externes) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §2.E E2 (décision « ressusciter partiellement : câbler CircuitBreaker »), §4 P3-2 (critère de done), §5 (dépendance P2-12 → P3-2) ;
- [`backend_status.md`](../../docs/backend_status.md) — §4.5 (résilience non câblée : CircuitBreaker/RetryPolicy/HealthCheck 0 import), §17 ;
- [`02-familles-workloads.md`](../../docs/general_specs/02-familles-workloads.md) — § WorkloadAdapter (contrat sur lequel s'accroche le breaker, posé par STORY-174) ;
- `.roo/rules/20-architecture-and-api.md` — § Résilience & performance (circuit breaker, retries attendus).

## Dépendances

- **STORY-174** (EPIC-013) — `WorkloadAdapter` = point d'accroche naturel du breaker sur les appels Docker (dépendance explicite du plan : P3-2 dépend de P2-12).
- **STORY-172** (EPIC-013) — exposition de la métrique d'état des circuits via `/metrics`.
- Interagit avec STORY-250 (purge de `HealthCheck` dans le même module `resilience.py` — séquencer pour éviter les conflits).

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
