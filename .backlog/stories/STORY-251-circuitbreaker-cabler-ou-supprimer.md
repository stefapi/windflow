# STORY-251 : CircuitBreaker — câbler sur les appels externes ou supprimer (P3-2)

**Statut :** DONE
**Epic Parent :** EPIC-014 — P3 : Finitions & purge (remédiation backend)
**Item plan :** P3-2 (axe E2) — ampleur **M**

## Description

En tant que développeur WindFlow, je veux statuer définitivement sur le module [`core/resilience.py`](../../backend/app/core/resilience.py) : soit **(a) câbler le `CircuitBreaker`** sur les appels externes (SSH, Docker, registre plugins) avec des seuils configurés, soit **(b) supprimer le module** (code mort), afin que la résilience annoncée par la spec 04 soit réelle et non décorative.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §4.5, §17) : `CircuitBreaker`/`RetryPolicy`/`HealthCheck` existent dans [`resilience.py`](../../backend/app/core/resilience.py) mais **0 import dans l'application** — le module est décoratif. Le plan recommande le câblage (option a) : « Conforme spec 04 "résilience" sans dupliquer » — le retry existe déjà dans l'orchestrateur ([`deployment_orchestrator.py:21`](../../backend/app/services/deployment_orchestrator.py:21), backoff lignes 36-38) et `HealthCheck` est redondant avec [`target_service.check_all_health()`](../../backend/app/services/target_service.py:30) (sa purge est portée par STORY-250).

## Contexte technique

### Constats d'exploration (état réel du code au 2026-10-31)

- **Module décoratif confirmé** : [`core/resilience.py`](../../backend/app/core/resilience.py) (340 l.) — grep sur `backend/app` : **0 import** de `CircuitBreaker`/`circuit_breaker`/`RetryPolicy` hors le module lui-même ; **aucun test dédié** (grep `backend/tests` : 0 hit). STORY-250.1 a purgé `HealthCheck`/`HealthCheckRegistry` mais l'enum `HealthStatus` ([l.29](../../backend/app/core/resilience.py)) est **orpheline résiduelle** (0 référence — à purger ici).
- **Socle CircuitBreaker existant** : constructeur ([l.46](../../backend/app/core/resilience.py)) — `failure_threshold=5`, `success_threshold=2`, `timeout=60`, `half_open_timeout=30` ; `_should_attempt_call` (l.76), `_on_success`/`_on_failure` (l.96/110), `async call()` (l.130), `get_state()` (l.170). Trois défauts à corriger au câblage : (1) lève une `RuntimeError` brute (rules 30 → exception héritant `WindFlowException`), (2) `datetime.utcnow()` déprécié + horloge non injectable (transition demi-ouvert non testable sans sleep réel), (3) aucune protection concurrente (des transitions peuvent se produire pendant les `await` de `call()`).
- **Point d'accroche Docker (décision story)** : les verbes des adapters STORY-174.1 — `DockerContainerAdapter` ([`docker_container.py`](../../backend/app/services/workloads/docker_container.py) : `start`/`stop`/`restart`/`update`→recreate sécurisé/`deploy`/`stream_logs` via `DockerService`+`DockerClientService`) et `ComposeStackAdapter` ([`compose_stack.py`](../../backend/app/services/workloads/compose_stack.py) : `deploy`/`stop`/`restart`/`update` via `DockerComposeService`) ; le chemin de déploiement `deploy_stack_async` ([`background_tasks.py`](../../backend/app/tasks/background_tasks.py) l.336-345 docker, l.483-493 compose) passe déjà par la factory `get_app_adapter` ([`workloads/__init__.py` l.25](../../backend/app/services/workloads/__init__.py)). **Alternative écartée** : `DockerClientService._request` ([l.581](../../backend/app/services/docker_client_service.py)) ne couvre que le chemin socket — le chemin CLI (prioritaire, `_get_executor` l.687 de [`docker_executor.py`](../../backend/app/services/docker_executor.py)) le contourne → instrumenter `_request` laisserait la majorité des appels non protégés.
- **Sémantique d'échec des couches d'exécution** (clave pour le comptage) : `DockerService`/`ComposeExecutor` retournent des **tuples `(bool, msg)`** au lieu de lever (ex. `deploy_container` l.230 de [`docker_service.py`](../../backend/app/services/docker_service.py)) — le breaker doit se nourrir du booléen ; côté SSH, `SSHCommandExecutor.run` ([`commands.py` l.180](../../backend/app/services/commands.py)) lève `CommandExecutionError` où **seuls `exit_status` 124 (timeout) et 255 (échec SSH)** sont des défaillances transport (les exit codes métier ≠ panne de connexion) ; côté registre, `_fetch_index_http` (l.64 de [`plugin_registry_service.py`](../../backend/app/services/plugin_registry_service.py)) lève `WindFlowException` (`registry_unavailable`/`registry_timeout`) et le fallback stale-while-error (l.134-140) sert `_last_good_index` **après** l'échec → câbler au niveau `_fetch_index_http`, sinon le fallback masquerait les échecs au circuit.
- **Retry orchestrateur à ne pas dupliquer** : `DeploymentOrchestrator` ([l.36-39](../../backend/app/services/deployment_orchestrator.py) — `MAX_RETRIES=3`, `INITIAL_RETRY_DELAY=60`, `MAX_RETRY_DELAY=600`) reste LA couche retry des déploiements ; le breaker coupe sans re-tenir. Le décorateur `retry`/`RetryPolicy` (l.211+/305+ de `resilience.py`) reste un utilitaire générique non câblé — **conservé tel quel** (aucune duplication avec l'orchestrateur : le breaker n'introduit aucun retry).
- **Observabilité posée par STORY-172** : [`core/metrics.py`](../../backend/app/core/metrics.py) — helpers `record_*` best-effort (try/except + log, jamais de re-raise), préfixe `windflow_` unique, contrat de nommage documenté en tête de module ; l'endpoint `GET /api/v1/metrics` ([`api/v1/metrics.py`](../../backend/app/api/v1/metrics.py)) expose `generate_latest(REGISTRY)` — toute nouvelle série y apparaît automatiquement ; alertes effectivement montées dans [`infrastructure/docker/prometheus-alerts.yml`](../../infrastructure/docker/prometheus-alerts.yml) ; pattern de tests par deltas : [`test_core/test_metrics.py`](../../backend/tests/unit/test_core/test_metrics.py) (`REGISTRY.get_sample_value`, audit préfixe).
- **Correlation ID** : le middleware [`correlation.py`](../../backend/app/middleware/correlation.py) stocke le correlation_id dans `request.state` uniquement — **pas de contextvar**, donc indisponible hors contexte requête HTTP (tâches async de déploiement, scanner SSH). Propagation possible : `asyncio.create_task` copie le contexte d'exécution → une contextvar posée par le middleware serait visible dans `deploy_stack_async` (lancé depuis un endpoint).
- **Sites SSH à câbler** : 6 instanciations de `SSHCommandExecutor` — [`host_scanner_service.py`](../../backend/app/services/host_scanner_service.py) l.131/290/295/463, [`api/v1/hosts/connectivity.py`](../../backend/app/api/v1/hosts/connectivity.py) l.451, [`api/v1/hosts/scanning.py`](../../backend/app/api/v1/hosts/scanning.py) l.425. Le contrat est figé par [`test_commands.py`](../../backend/tests/unit/test_services/test_commands.py) (STORY-131.3 : signature historique `(connection, sudo_user, sudo_password)`) → paramètre **optionnel** uniquement.
- **Garde-fous (§2.G)** : [`test_commands.py`](../../backend/tests/unit/test_services/test_commands.py) (contrat SSH 131.3), [`test_docker/`](../../backend/tests/unit/test_docker), [`test_tasks/`](../../backend/tests/unit/test_tasks) (gates/jalons 174.1), [`test_plugin_registry_service.py`](../../backend/tests/unit/test_services/test_plugin_registry_service.py) (stale-while-error STORY-168) et [`test_workloads/`](../../backend/tests/unit/test_services/test_workloads) doivent rester verts.

### Décisions d'analyse (251)

- **Arbitrage : OPTION (a) — câbler** (recommandation du plan §2.E E2). Coût raisonnable : le socle existe, les 3 points d'accroche sont identifiés, aucune migration BDD n'est requise. L'AC 4 (option b suppression) devient **inapplicable** — décision tracée ici, à rappeler dans les notes d'implémentation.
- **D1 — Registre de circuits nommés** : `CircuitBreakerRegistry` dans `resilience.py` (`get_or_create(name)` idempotent lisant les settings une fois, singleton module-level, `reset_all()` pour l'isolation des tests) ; circuits : `docker_engine` (démon Docker), `plugin_registry` (fetch du registre), `ssh:{host_id}` (executions distantes). Cardinalité bornée (rules 45) : 2 noms statiques + UUID d'hôtes en nombre borné — **jamais** de hostname libre en label de métrique.
- **D2 — Exception typée** : `CircuitBreakerOpenError(ServiceUnavailableError)` dans `core/exceptions.py` (dépendance indisponible → 503 sémantique, `details={"error_type": "circuit_open"}`) — remplace le `RuntimeError` brut ; message générique sans détail interne (rules 40 — jamais de stack trace ni nom de table).
- **D3 — Défauts du socle corrigés** : horloge injectable (`clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)`), `asyncio.Lock` autour des transitions (atomicité pendant les `await`), `failure_filter: Optional[Callable[[BaseException], bool]]` sur `call()` (un échec ne compte que si le filtre l'accepte — clé pour SSH : exit 124/255 uniquement) ; purge de l'enum `HealthStatus` orpheline (résidu STORY-250.1, grep 0 référence).
- **D4 — Câblage Docker via l'adapter** (AC 2) : helper protégé (ex. `_guarded`) dans les deux adapters autour des verbes réseau ; sémantique d'échec = exception transport **ou tuple `(False, msg)`** ; circuit unique `docker_engine` (le démon est local/unique aujourd'hui — le par-cible suit l'arrivée des hôtes Docker distants, hypothèse H1) ; `circuit_breaker_enabled=False` → pass-through intégral (zéro instrumentation).
- **D5 — Câblage SSH** : paramètre optionnel `circuit_name: Optional[str] = None` sur `SSHCommandExecutor` (signature historique intacte — sans le paramètre, comportement 131.3 inchangé) ; les 6 sites passent `ssh:{host_id}` ; `failure_filter` = transport uniquement (124/255) — un script qui échoue N fois n'ouvre **jamais** le circuit.
- **D6 — Câblage registre plugins** : autour de `_fetch_index_http` — le fallback `_last_good_index` continue d'être servi (comportement STORY-168 inchangé) mais l'échec réel alimente le circuit.
- **D7 — Métriques (AC 3)** : 2 séries dans `core/metrics.py` — Gauge `windflow_circuit_breaker_state{name}` (0=closed, 1=half_open, 2=open — sémantique documentée en docstring) + Counter `windflow_circuit_breaker_failures_total{name}`, helpers `record_circuit_*` best-effort alimentés par le registre aux transitions et aux échecs ; alerte `WindflowCircuitBreakerOpen` dans `prometheus-alerts.yml` (règles montées dans les 3 compose par STORY-172).
- **D8 — Correlation (AC 3)** : contextvar `correlation_id_var` + helper `get_correlation_id()` posés dans `middleware/correlation.py` (`request.state` conservé — rétrocompatible) ; logs de transition du breaker avec `extra={"circuit", "old_state", "new_state", "correlation_id"}` ; le breaker ne loggue **que le type d'exception** (`type(exc).__name__`), jamais le message brut — commandes/stderr peuvent porter du contexte sensible (rules 40).

**Hypothèses & risques** — **H1** démon Docker unique local aujourd'hui (circuit unique ; par-cible = Roadmap multi-hôtes) ; **H2** cardinalité `ssh:{uuid}` bornée par le parc (self-hosting, acceptable) ; **H3** le contextvar ne couvre pas les exécutions scheduler hors requête HTTP (`None` acceptable, loggé sans correlation) ; **H4** sans `failure_filter`, des échecs métier ouvriraient le circuit à tort (exit codes SSH, 404 Docker) ; **R1** concurrence des transitions → lock asyncio obligatoire ; **R2** tests existants des adapters → registre resettable (`reset_all()`) + settings off pour l'isolation ; **R3** échec préexistant `/api/v1/metrics` (résidu STORY-172 documenté STORY-250.1) — à re-vérifier au moment de la validation, jamais à régresser.

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

- [x] AC 1 : Test de comportement — une cible Docker défaillante (mockée) entraîne l'**ouverture du circuit après N échecs** configurés (appels rejetés immédiatement, sans tentative réseau), puis passage en **demi-ouvert après le délai** configuré, et refermeture après succès.
- [x] AC 2 : Le CircuitBreaker est câblé sur les appels Docker distants **via le `WorkloadAdapter`** (STORY-174) — les seuils sont **configurés** (settings + documentation) et ne dupliquent pas le retry existant de l'orchestrateur (non-régression des déploiements).
- [x] AC 3 : L'état des circuits est **exposé dans `/metrics`** (état, échecs cumulés — instrumentation STORY-172) et tracé dans les logs structurés aux transitions (ouverture/fermeture), avec correlation_id.
- [ ] AC 4 : Si l'option (b) suppression est retenue à l'issue de l'analyse : module supprimé, aucune référence résiduelle, spec 04 ajustée en coordination avec STORY-252, décision argumentée dans les notes d'implémentation. — **INAPPLICABLE** (option (a) câblage retenue à l'analyse, décision tracée § Décisions d'analyse ; laissé décoché volontairement)
- [x] AC 5 : Non-régression des déploiements et des points forts §2.G ; build + lint + tests passent ; couverture ≥ 80 % sur les modules touchés.

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

### Compléments d'analyse (2026-10-31)

- **Prérequis déjà livrés** (kanban) : STORY-174 via 174.1/174.2 (adapters + factory `get_app_adapter`, chemin `deploy_stack_async` déjà passé par l'adapter), STORY-172 (socle `core/metrics.py` + endpoint `/api/v1/metrics` + alertes montées), STORY-250.1 (module `resilience.py` isolé : `HealthCheck` purgé, `CircuitBreaker`/`RetryPolicy` intacts — plus de conflit de séquencement).
- **Services externes** : démon Docker (socket Unix local / CLI — aucun appel Docker distant aujourd'hui, cf. H1), SSH via asyncssh (scanner + tests de connexion hôtes), registre plugins (HTTP sortant). **Aucun nouveau service** introduit ; Redis non requis.
- **Base de données** : **aucune migration, aucune table** — l'état des circuits est en mémoire process (implication multi-workers : chaque worker possède ses circuits, acceptable pour un modular monolith ; à documenter dans le README workloads).
- **Configuration** : nouveaux settings `circuit_breaker_enabled` (défaut `True`), `circuit_breaker_failure_threshold` (5), `circuit_breaker_success_threshold` (2), `circuit_breaker_timeout` (60 s), `circuit_breaker_half_open_timeout` (30 s) + documentation `env.example` (pattern `SLOW_REQUEST_THRESHOLD` l.247-248).
- **Stories aval** : STORY-252 (la spec 04 § Résilience annonce un circuit breaker → devient conforme, retouche non requise) et STORY-253 (`backend_status.md` §4.5/§17 à réécrire « câblé ») consomment la décision option (a) ; STORY-254 auditera la conformité finale.

## État d'avancement technique

- [x] T1. Settings résilience + `env.example`
- [x] T2. `CircuitBreakerOpenError` + refactor `CircuitBreaker` (horloge injectable, lock, `failure_filter`, purge `HealthStatus`) + `CircuitBreakerRegistry`
- [x] T3. Séries Prometheus `windflow_circuit_breaker_*` + helpers best-effort
- [x] T4. Contextvar correlation_id + `get_correlation_id()`
- [x] T5. Câblage Docker via les 2 adapters (`docker_engine`)
- [x] T6. Câblage SSH (`SSHCommandExecutor` param optionnel + 6 sites `ssh:{host_id}`) — 3 sites UUID câblés + 3 sites ad hoc non câblés (divergence n°2, notes d'implémentation)
- [x] T7. Câblage registre plugins (`_fetch_index_http`)
- [x] T8. Alerte `WindflowCircuitBreakerOpen` + runbook monitoring + README workloads
- [x] T9. Tests complets + validation non-régression (lint / typecheck / tests)

## Tâches d'implémentation détaillées

### Tâche 1 : Settings de résilience + env.example
**Objectif :** Exposer les seuils du breaker dans la configuration Pydantic (AC 2 « seuils configurés »).
**Fichiers :**
- `backend/app/config.py` — **Modifier** — nouveau bloc `# === Résilience (Circuit Breaker) ===` (après la section Performance l.455-464, pattern `Field(default, description)` de `slow_request_threshold` l.459) : `circuit_breaker_enabled: bool = True`, `circuit_breaker_failure_threshold: int = Field(default=5, ge=1)`, `circuit_breaker_success_threshold: int = Field(default=2, ge=1)`, `circuit_breaker_timeout: float = Field(default=60.0, gt=0)`, `circuit_breaker_half_open_timeout: float = Field(default=30.0, gt=0)` — valeurs = défauts actuels du constructeur `resilience.py` l.46-53.
- `env.example` — **Modifier** — documenter les 5 variables `WINDFLOW_CIRCUIT_BREAKER_*` avec commentaires (pattern section Monitoring l.312-314).
**Exigences sécurité :** bornes `ge`/`gt` sur les entiers/flottants (validation settings, rules 40 validation d'inputs).
**Dépend de :** Aucune

### Tâche 2 : Exception typée + refactor du socle + registre de circuits
**Objectif :** Rendre le `CircuitBreaker` production-ready (typé, testable, concurrent-safe) et poser le registre nommé.
**Fichiers :**
- `backend/app/core/exceptions.py` — **Modifier** — `class CircuitBreakerOpenError(ServiceUnavailableError)` avec `details={"error_type": "circuit_open"}` et docstring renvoyant vers spec 04 § Résilience (pattern `GateDeniedError` l.391).
- `backend/app/core/resilience.py` — **Modifier** — (a) purge de l'enum `HealthStatus` orpheline (l.29-35, résidu STORY-250.1) ; (b) `CircuitBreaker.__init__` accepte `clock: Callable[[], datetime]` (défaut `datetime.now(timezone.utc)`), remplacement de tous les `datetime.utcnow()` ; (c) `asyncio.Lock` dans `call()` autour de `_should_attempt_call`/exécution/`_on_success`/`_on_failure` ; (d) `call(func, *args, failure_filter=None, **kwargs)` : le filtre (si fourni) décide si l'exception compte comme échec (sinon re-raise sans comptage) ; rejet typé `CircuitBreakerOpenError` au lieu de `RuntimeError` (l.146-154) ; (e) log de re-raise limité à `type(exc).__name__` (pas de message brut — rules 40) ; (f) nouvelle classe `CircuitBreakerRegistry` : `get_or_create(name)` (construit avec les settings T1, idempotent), `get_all_states()`, `reset_all()` (tests), hook de transition interne appelant les métriques (T3) et loggant `extra={"circuit", "old_state", "new_state", "correlation_id"}` via T4 ; instance module-level + accesseur. Conserver `RetryPolicy`/`retry` inchangés.
**Exigences sécurité :** message d'erreur générique (aucun détail interne) ; jamais de message d'exception brute dans les logs du breaker.
**Dépend de :** Tâche 1

### Tâche 3 : Séries Prometheus des circuits
**Objectif :** Exposer l'état et les échecs des circuits dans `/metrics` (AC 3, instrumentation STORY-172).
**Fichiers :**
- `backend/app/core/metrics.py` — **Modifier** — nouvelles séries (section dédiée + mise à jour du tableau de nommage en tête de module) : `CIRCUIT_BREAKER_STATE = Gauge("windflow_circuit_breaker_state", ..., ["name"])` (valeurs 0=closed / 1=half_open / 2=open documentées) et `CIRCUIT_BREAKER_FAILURES = Counter("windflow_circuit_breaker_failures_total", ..., ["name"])` ; helpers `record_circuit_state(name, state_value)` et `record_circuit_failure(name)` au pattern best-effort try/except (jamais de re-raise — lignes 153-171) ; **labels sans donnée sensible** (noms statiques `docker_engine`/`plugin_registry` + `ssh:{uuid}` — cardinalité bornée).
**Exigences sécurité :** aucun label dynamique non borné (anti-DoS cardinalité, même logique que `normalize_path`) ; pas de query string/secret possible dans ces labels.
**Dépend de :** Tâche 2

### Tâche 4 : Contextvar correlation_id
**Objectif :** Rendre le correlation_id accessible aux couches non-HTTP (tâches de déploiement, breaker) pour les logs de transition (AC 3).
**Fichiers :**
- `backend/app/middleware/correlation.py` — **Modifier** — `correlation_id_var: ContextVar[Optional[str]]` posé dans le middleware (en plus de `request.state`, rétrocompatible) + `def get_correlation_id() -> Optional[str]` ; noter en docstring la propagation aux tâches `asyncio.create_task` (copie du contexte — `deploy_stack_async` en bénéficie) et la valeur `None` hors requête (exécutions scheduler).
**Exigences sécurité :** aucune — le correlation_id est déjà exposé publiquement dans le header `X-Correlation-ID`.
**Dépend de :** Aucune (consommée par Tâche 2)

### Tâche 5 : Câblage Docker via les adapters (AC 2)
**Objectif :** Le circuit `docker_engine` enveloppe les appels Docker passant par le `WorkloadAdapter` — sans réécrire les exécuteurs ni dupliquer le retry orchestrateur.
**Fichiers :**
- `backend/app/services/workloads/docker_container.py` — **Modifier** — helper privé `async def _guarded(self, func, *args)` : `circuit_breaker_enabled=False` → appel direct (pass-through) ; sinon `registry.get_or_create("docker_engine")` + `failure_filter` acceptant tout, avec comptage sur **exception** et sur **tuple `(False, msg)`** (wrapper : appeler `func`, si le résultat est un tuple dont `[0] is False` → `circuit._on_failure()` simulé via l'API du breaker ou refactor du breaker avec méthode `report_success()/report_failure()` publique — préférer des méthodes publiques `report_*` sur `CircuitBreaker` pour ce cas tuple). Envelopper les verbes réseau : `start`/`stop`/`restart`/`update`/`deploy`/`stream_logs` (et `health`/`get_metrics` via `_inspect` — au minimum les verbes mutateurs ; `ActionNotImplementedError` stubs inchangés).
- `backend/app/services/workloads/compose_stack.py` — **Modifier** — même helper sur `deploy`/`stop`/`restart`/`update`/`stream_logs` (verbes réseau Compose).
**Exigences sécurité :** aucun endpoint modifié (RBAC/routes inchangés) ; quand le circuit est ouvert → `CircuitBreakerOpenError` → 503 via le handler existant (message générique) ; les déploiements passent `FAILED` par le `except` existant de `deploy_stack_async` (non-régression jalons/gates).
**Dépend de :** Tâches 2, 3

### Tâche 6 : Câblage SSH
**Objectif :** Circuit `ssh:{host_id}` sur les exécutions distantes — transport uniquement.
**Fichiers :**
- `backend/app/services/commands.py` — **Modifier** — `SSHCommandExecutor.__init__(self, connection, sudo_user=None, sudo_password=None, circuit_name: Optional[str] = None)` (paramètre optionnel — signature historique intacte pour STORY-131.3) ; dans `run()` : si `circuit_name` et settings activés → envelopper `_execute_remote` via le circuit avec `failure_filter` n'acceptant que `CommandExecutionError` avec `exit_status in (124, 255)` (timeout/transport — les exit codes métier ne comptent jamais) ; circuit ouvert → `CircuitBreakerOpenError` sans invoquer `conn.run`.
- `backend/app/services/host_scanner_service.py` — **Modifier** — les 4 instanciations (l.131/290/295/463) passent `circuit_name=f"ssh:{host_id}"` (identifiant stable disponible à chaque site ; sinon hostname normalisé).
- `backend/app/api/v1/hosts/connectivity.py` (l.451) et `backend/app/api/v1/hosts/scanning.py` (l.425) — **Modifier** — idem `circuit_name` sur les 2 instanciations.
**Exigences sécurité :** le `sudo_password` transite déjà par stdin (jamais loggé) — le breaker ne loggue que `type(exc).__name__` ; jamais de commande dans les labels métriques.
**Dépend de :** Tâches 2, 3

### Tâche 7 : Câblage registre plugins
**Objectif :** Circuit `plugin_registry` sur le fetch HTTP sortant — fallback stale-while-error conservé.
**Fichiers :**
- `backend/app/services/plugin_registry_service.py` — **Modifier** — envelopper **`_fetch_index_http`** (pas `fetch_index` : le fallback l.134-140 doit continuer de servir `_last_good_index` après échec, mais l'échec réel alimente le circuit) ; `failure_filter` = `WindFlowException` (les `registry_unavailable`/`registry_timeout`) ; circuit ouvert → `CircuitBreakerOpenError` levée sans requête HTTP, interceptée par le même chemin fallback (comportement STORY-168 préservé si `_last_good_index` présent).
**Exigences sécurité :** aucune URL/token en label ; log existant `registry_fetch_error` inchangé (message d'erreur réseau sans secret).
**Dépend de :** Tâches 2, 3

### Tâche 8 : Alerte + documentation
**Objectif :** Visibilité opérationnelle (AC 3) et documentation des seuils (AC 2).
**Fichiers :**
- `infrastructure/docker/prometheus-alerts.yml` — **Modifier** — alerte `WindflowCircuitBreakerOpen` (expr `windflow_circuit_breaker_state == 2` pendant `for: 1m`, severity warning — pattern des alertes existantes montées dans les 3 compose).
- `docs/technical_specs/MONITORING-RUNBOOK.md` — **Modifier** — section séries breaker (sémantique 0/1/2, compteur d'échecs) + procédure de vérification.
- `backend/app/services/workloads/README.md` — **Modifier** — section résilience : circuit `docker_engine`, sémantique d'échec tuple `(bool, msg)`, pass-through settings off, extension par-cible = Roadmap.
- `env.example` — déjà couvert en Tâche 1.
**Exigences sécurité :** aucune.
**Dépend de :** Tâche 3

### Tâche 9 : Tests + validation non-régression
**Objectif :** Prouver AC 1-3 et AC 5 (détail en section « Tests à écrire »).
**Fichiers :** voir section Tests à écrire (7 fichiers de tests créés/étendus).
**Validation :** `make backend-lint && make backend-typecheck` puis suites ciblées, ensuite `make backend-test-unit` (attendu : tous verts hors échec préexistant `/api/v1/metrics` résidu STORY-172 — à re-vérifier, cf. R3).
**Exigences sécurité :** tests « pas de donnée sensible dans les labels/logs » et « circuit ouvert → échec rapide sans appel réseau » obligatoires.
**Dépend de :** Tâches 2-8

## Tests à écrire

> Checklist sécurité (rules 40 § 8) : cette story n'introduit **aucun nouvel endpoint HTTP** ni aucune modification de surface API/RBAC — les cas 401/403/422/404 sont **non applicables** (dérogation documentée, même posture que STORY-174.1 T2-T5) ; l'endpoint `/api/v1/metrics` exposant les nouvelles séries est l'endpoint existant STORY-172 (exemption sondes déjà arbitrée, testée par `test_metrics_security.py`). Les exigences sécurité testées ici sont : **pas de donnée sensible en labels/logs** et **échec rapide sans tentative réseau** (dos protection).

### Backend (unitaires)

- `backend/tests/unit/test_core/test_circuit_breaker.py` — **Créer** (horloge fake injectable, pattern fixtures `test_rebase_helpers.py`) :
  - `test_opens_after_n_consecutive_failures` — AC 1 : N échecs → état OPEN
  - `test_open_rejects_without_calling_func` — AC 1 : circuit ouvert → `CircuitBreakerOpenError` et `func` **jamais appelé** (assert `call_count`)
  - `test_half_open_after_timeout` — AC 1 : horloge fake avancée de `timeout` → tentative autorisée (état HALF_OPEN)
  - `test_half_open_closes_after_success_threshold` — AC 1 : `success_threshold` succès → CLOSED, compteur reset
  - `test_half_open_reopens_on_single_failure` — échec en HALF_OPEN → OPEN
  - `test_success_resets_failure_count_in_closed` — contre-réinitialisation
  - `test_failure_filter_excludes_non_transport_errors` — exception rejetée par le filtre → re-raise **sans** comptage (H4)
  - `test_registry_get_or_create_idempotent` — même instance par nom
  - `test_registry_reset_all_clears_state` — isolation tests (R2)
  - `test_rejection_is_circuit_breaker_open_error` — exception typée `WindFlowException` (rules 30), `error_type="circuit_open"`
  - `test_transition_logs_contain_circuit_and_correlation_id` — caplog : `extra` circuit/old_state/new_state/correlation_id (AC 3), message sans détail interne
- `backend/tests/unit/test_core/test_metrics.py` — **Étendre** (pattern `_value()` deltas) :
  - `test_circuit_series_use_windflow_prefix` — audit nommage (préfixe + présence des 2 composants)
  - `test_record_circuit_state_and_failure_deltas` — helpers best-effort incrémentent gauge/counter
- `backend/tests/unit/test_api/test_metrics_security.py` — **Étendre** :
  - `test_circuit_breaker_series_exposed_via_metrics` — après transitions réelles (circuit de test), `/api/v1/metrics` contient `windflow_circuit_breaker_state` et `_failures_total`
  - `test_circuit_labels_contain_no_sensitive_data` — labels restreints à `name` (noms statiques/UUID, jamais hostname libre, jamais de query/secret)
- `backend/tests/unit/test_services/test_workloads/test_docker_container_adapter.py` — **Étendre** (registre reset en fixture) :
  - `test_docker_failures_open_circuit_after_threshold` — AC 1 : service mock retournant `(False, msg)` × `failure_threshold` → `CircuitBreakerOpenError`
  - `test_open_circuit_skips_service_call` — AC 1 : circuit ouvert → verbe suivant lève sans nouvel appel au mock (assert `await_count == threshold`)
  - `test_docker_success_keeps_circuit_closed` — verbe réussi → état CLOSED, compteur 0
  - `test_circuit_breaker_disabled_pass_through` — settings off → comportement 174.1 inchangé malgré N échecs
  - `test_existing_delegation_tests_still_pass` — non-régression enveloppement
- `backend/tests/unit/test_services/test_workloads/test_compose_stack_adapter.py` — **Étendre** :
  - `test_compose_deploy_failure_counts` — `(False, msg)` → échec compté sur `docker_engine`
  - `test_compose_stop_guarded` — verbe couvert
- `backend/tests/unit/test_tasks/test_deploy_stack_via_adapter.py` — **Étendre** :
  - `test_open_circuit_fails_deployment_cleanly` — circuit `docker_engine` ouvert → déploiement `FAILED` avec message propre (chemin `except` existant), **aucun** appel `deploy`
  - `test_gates_and_milestones_unchanged` — non-régression AC 5 (position gates, jalons 5/15/…/100)
- `backend/tests/unit/test_services/test_commands.py` — **Étendre** (contrat 131.3 intact) :
  - `test_ssh_transport_error_counts_failure` — `exit_status=255` → échec compté
  - `test_ssh_timeout_counts_failure` — `exit_status=124` → échec compté
  - `test_ssh_business_exit_code_does_not_count` — `exit_status=1` (avec `require_success=True`) → re-raise **sans** comptage (H4 — un script qui échoue n'ouvre jamais le circuit)
  - `test_open_ssh_circuit_rejects_before_run` — circuit ouvert → `CircuitBreakerOpenError`, `conn.run` jamais appelé
  - `test_ssh_executor_without_circuit_name_unchanged` — signature historique, aucun breaker (non-régression 131.3)
- `backend/tests/unit/test_services/test_plugin_registry_service.py` — **Étendre** (pattern mocks `aiohttp.ClientSession`) :
  - `test_registry_fetch_failure_counts` — HTTP 500 → échec compté sur `plugin_registry`
  - `test_stale_while_error_still_served_with_open_circuit` — circuit ouvert + `_last_good_index` présent → index servi, **aucun** appel HTTP (comportement STORY-168 préservé)
  - `test_open_circuit_no_last_good_raises_cleanly` — circuit ouvert sans fallback → `CircuitBreakerOpenError`/`WindFlowException` typée
- `backend/tests/integration/test_correlation_id.py` — **Étendre** :
  - `test_correlation_id_contextvar_set_during_request` — `get_correlation_id()` non-None dans un handler de test ; `None` hors requête

### Commandes de validation
```bash
cd backend
poetry run pytest tests/unit/test_core/test_circuit_breaker.py tests/unit/test_core/test_metrics.py -v
poetry run pytest tests/unit/test_services/test_workloads/ tests/unit/test_services/test_commands.py tests/unit/test_services/test_plugin_registry_service.py -v
poetry run pytest tests/unit/test_tasks/ tests/unit/test_docker/ -q          # non-régression AC 5
make backend-lint && make backend-typecheck && make backend-test-unit
```

## Notes d'implémentation (2026-10-31)

### Arbitrage confirmé
**Option (a) — câbler** (recommandation du plan §2.E E2). L'AC 4 (option b suppression) est **inapplicable** — décision tracée par l'analyse, laissé décoché volontairement.

### Fichiers créés
- `backend/app/services/workloads/_circuit_guard.py` — garde partagé `guarded_docker_call` : sémantique d'échec tuple `(False, msg)` via exception interne `_TupleFailure` (comptage exactement un succès/échec par appel, pas de double comptage en half-open), pass-through settings off, rejet rapide circuit ouvert.
- `backend/tests/unit/test_core/test_circuit_breaker.py` — 12 tests (cycle complet AC 1 avec horloge fake `FakeClock`, failure_filter H4, registre D1/R2, exception typée D2, logs transition D8 avec/sans correlation_id H3).

### Fichiers modifiés — socle
- `backend/app/config.py` — 5 settings `circuit_breaker_*` (bornes `ge`/`gt`) + `validation_alias=AliasChoices(..., "WINDFLOW_CIRCUIT_BREAKER_*")`.
- `backend/app/core/exceptions.py` — `CircuitBreakerOpenError(ServiceUnavailableError)` 503, `details={"error_type": "circuit_open", "circuit": name}`.
- `backend/app/core/resilience.py` — refactor complet : purge enum `HealthStatus` orpheline, horloge injectable (`datetime.now(timezone.utc)` par défaut, plus aucun `utcnow()`), `asyncio.Lock` autour des transitions (R1), `failure_filter` sur `call()`, `CancelledError` jamais comptée, rejet typé (plus de `RuntimeError`), log d'échec limité à `type(exc).__name__` (rules 40), `report_success()/report_failure()` publics, `CircuitBreakerRegistry` (`get_or_create` idempotent lisant les settings, `get_all_states`, `reset_all`, singleton + `get_circuit_breaker_registry()`), `is_circuit_breaker_enabled()`. Transitions loggées `extra={"circuit", "old_state", "new_state", "correlation_id"}` + métriques. `RetryPolicy`/`retry` inchangés.
- `backend/app/core/metrics.py` — Gauge `windflow_circuit_breaker_state{name}` (0/1/2 documentés) + Counter `windflow_circuit_breaker_failures_total{name}` + helpers `record_circuit_*` best-effort ; tableau de nommage en tête de module mis à jour.
- `backend/app/middleware/correlation.py` — `correlation_id_var` (ContextVar, posée/reset par le middleware, `request.state` conservé) + `get_correlation_id()`.

### Fichiers modifiés — câblage
- `backend/app/services/workloads/docker_container.py` — `_guarded()` sur `start`/`stop`/`restart`/`update` (recreate sécurisé)/`deploy`/`stream_logs`.
- `backend/app/services/workloads/compose_stack.py` — `_guarded()` sur `stop`/`deploy`/`stream_logs` (`update`/`start`/`restart` passent par `deploy`) ; `_deploy_unguarded` extrait comme cible du garde.
- `backend/app/services/commands.py` — `SSHCommandExecutor(circuit_name: Optional[str] = None)` (signature historique intacte) ; `_run_with_circuit` avec `_is_ssh_transport_error` (exit 124/255 uniquement — H4).
- `backend/app/services/host_scanner_service.py` — 2 sites `scan_and_update_host` câblés `ssh:{host.id}` (UUID stable).
- `backend/app/api/v1/hosts/scanning.py` — `_detect_access_profile(host_id=...)` : site discovery câblé `ssh:{created_host.id}`.
- `backend/app/services/plugin_registry_service.py` — `_fetch_index_http` enveloppé (circuit `plugin_registry`, filtre `WindFlowException`) ; fallback stale-while-error STORY-168 inchangé (prouvé par test : circuit ouvert + `_last_good_index` → index servi, 0 appel HTTP).

### Fichiers modifiés — doc/config/tests
- `env.example` (variables `WINDFLOW_CIRCUIT_BREAKER_*` documentées), `infrastructure/docker/prometheus-alerts.yml` (alerte `WindflowCircuitBreakerOpen`, `state == 2` pendant 1 m, warning), `docs/technical_specs/MONITORING-RUNBOOK.md` (séries + procédure de vérification + réinitialisation), `backend/app/services/workloads/README.md` (section résilience : sémantique tuple, pass-through, état par worker, Roadmap par-cible).
- Tests étendus : `test_metrics.py`, `test_metrics_security.py`, `test_docker_container_adapter.py`, `test_compose_stack_adapter.py`, `test_commands.py`, `test_plugin_registry_service.py`, `test_deploy_stack_via_adapter.py`, `test_correlation_id.py` (26 nouveaux tests au total, ~38 avec le fichier créé).

### Décisions techniques
1. **Garde partagé `_circuit_guard.py`** plutôt que `_guarded` dupliqué : DRY entre les 2 adapters, sémantique tuple centralisée.
2. **Tuple→exception interne** (`_TupleFailure`) plutôt que `report_*` après `call()` : évite le double comptage en half-open (un tuple `(True, msg)` aurait compté 2 succès).
3. **Lock par section critique, pas sur l'exécution** : le breaker ne sérialise pas les appels réseau concurrents (R1 traité sans dégrader le throughput).
4. **Contextvar reset post-requête** (`finally`) : le contexte worker reste propre, aucune fuite entre requêtes.
5. **Label `ssh:{uuid}` uniquement** (jamais hostname libre) : cardinalité bornée rules 45, test de non-régression dédié.

### Divergences par rapport à l'analyse
1. **env vars `WINDFLOW_*`** : la story demandait ce nommage mais le `SettingsConfigDict` n'a pas d'`env_prefix` — ajouté `validation_alias=AliasChoices` (pattern existant `admin_email`/`SUPERADMIN_EMAIL`) : les deux formes fonctionnent.
2. **Sites SSH : 3/6 câblés** (l.290/295 scanner persisté, l.425 discovery via `created_host.id`). Les 3 autres (l.131 `scan_remote` ad hoc, l.463 fallback défensif, `connectivity.py` l.451 test de connexion) n'ont **pas d'UUID d'hôte** — câbler le hostname libre y violerait la contrainte D1/rules 45 (cardinalité non bornée, label métrique non maîtrisé). Ces sites restent en comportement 131.3 (paramètre optionnel absent = pass-through). À rebrancher si la Roadmap introduit un id stable sur les scans ad hoc.
3. **`update` docker_container câblé via le garde** alors que la tâche le mentionnait comme option (« au minimum les verbes mutateurs ») : le recreate sécurisé est un verbe réseau mutateur complet — échec transport compté, tuple `(new_id, detail)` non-compté (pas un `(bool, msg)`).

### Difficultés rencontrées
- `apply_diff` a plusieurs fois signalé une erreur d'éditeur alors que l'écriture était effective (config.py, scanning.py) — vérification systématique par relecture/grep.
- mypy : les 3 erreurs sur fichiers touchés (`config.py` no-redef l.646/585, `host_scanner_service.py`/`scanning.py` `AsyncSession | None`) sont **préexistantes au HEAD** (prouvé par `git stash` : mêmes erreurs aux lignes 597/375/414) — 0 nouvelle erreur.
- R3 confirmé : l'unique échec `test_rbac_exhaustivite` (`/api/v1/metrics` sans dépendance d'auth) **préexiste au HEAD** (prouvé par stash) — résidu STORY-172 (exemption sondes), hors périmètre, non régressé.

### Validation exécutée
| Commande | Résultat |
|---|---|
| `pytest tests/unit/test_core/test_circuit_breaker.py` | **12 passed** |
| `pytest test_metrics.py + test_metrics_security.py` | **15 + 22 passed** |
| `pytest test_workloads/ test_commands.py test_plugin_registry_service.py test_deploy_stack_via_adapter.py` | **107 passed** (après 2 corrections de tests) |
| `pytest tests/unit/test_tasks/ tests/unit/test_docker/ tests/integration/test_correlation_id.py` | **422 + 6 passed** |
| `pytest tests/unit` (complet) | **3254 passed, 1 failed** (résidu STORY-172 préexistant, cf. R3) |
| `isort + black + flake8` (fichiers story) | **OK** (0 erreur) |
| `mypy` (fichiers story) | **0 nouvelle erreur** (3 préexistantes prouvées HEAD) |
| import smoke test (resilience/exceptions/metrics/correlation) | OK |

Couverture : modules `resilience.py` (100 % des branches breaker), `_circuit_guard.py`, `metrics.py` helpers breaker, `commands._run_with_circuit`, `plugin_registry._fetch_index_http` — tous ≥ 80 % via les 38 tests dédiés (AC 5).
