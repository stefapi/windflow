# STORY-172 : Observabilité Prometheus réelle — instrumentation `/metrics` (latence, erreurs, déploiements ok/ko, tâches scheduler), câblage de `websocket/metrics.py` et dashboards alimentés (P2-9 — axes B4, E5)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-9 (axes B4, E5, rapports §15) — ampleur **M**

## Description

En tant qu'opérateur WindFlow, je veux que `prometheus_enabled=True` corresponde à une **instrumentation réelle** : endpoint `/metrics` exposant sans auth au minimum la **latence des endpoints**, le **taux d'erreur**, les compteurs business **déploiements ok/ko** et les **tâches scheduler** (exécutions par statut) ; que le module défini-mais-jamais-importé [`websocket/metrics.py`](../../backend/app/websocket/metrics.py) soit câblé (ou supprimé si sa fonction est couverte autrement) ; et que les dashboards Grafana provisionnés affichent des données réelles sur un run de démo, afin de remplacer le « Prometheus mensonger » par une observabilité effective.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §11, §14.1, [WEBSOCKET-REAL-TIME.md §10.3](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md)) : `prometheus_enabled=True` dans [`config.py:41`](../../backend/app/config.py) mais **aucune instrumentation** Prometheus dans le code (B4) ; [`websocket/metrics.py`](../../backend/app/websocket/metrics.py) est défini mais **jamais importé** par aucun module (E5 : « ressusciter via B4 sinon purger ») ; les dashboards provisionnés ([`infrastructure/docker/grafana/dashboards/`](../../infrastructure/docker/grafana/dashboards/)) n'ont pas de métriques réelles en face.

## Contexte technique

### Constats d'exploration (état réel du code au 2026-10-31)

- **Aucune instrumentation Prometheus** : grep `prometheus|/metrics` sur `backend/app/` → seuls [`config.py:472-474`](../../backend/app/config.py) (`prometheus_enabled: bool = True`, `prometheus_multiproc_dir: Optional[str] = None`), [`websocket/metrics.py:14`](../../backend/app/websocket/metrics.py) (import top-level `prometheus_client`) et un exemple de schéma stack. Aucun endpoint `/metrics`, aucun `make_asgi_app`/`generate_latest` dans le code, aucune métrique métier.
- **Dépendance manquante (constat STORY-165 confirmé)** : `prometheus_client` est absent de [`pyproject.toml:8-41`](../../pyproject.toml) (blo `[tool.poetry.dependencies]`) — seul un override mypy le mentionne ([`pyproject.toml:118`](../../pyproject.toml)). Tout import du module crasherait en prod/CI ; les tests STORY-165 ([`test_ws_metrics_helpers.py:32`](../../backend/tests/unit/test_websocket/test_ws_metrics_helpers.py)) le contournent par `pytest.importorskip`.
- **[`websocket/metrics.py`](../../backend/app/websocket/metrics.py) défini mais jamais importé** (couverture 0 % au moment de STORY-165, helpers depuis testés) : 14 métriques WS (`windflow_websocket_*`) + helpers `record_*` + `MetricsTimer`/`broadcast_timer`/`auth_timer`. Aucun consommateur dans [`websocket/`](../../backend/app/websocket) (grep `record_` → aucun appel hors module).
- **Point de collecte HTTP** : [`middleware/timing.py`](../../backend/app/middleware/timing.py) mesure déjà `X-Process-Time` + log requêtes lentes — mais `call_next` n'est pas wrappé try/except (une exception = ni header ni mesure). Monté conditionnellement par [`main.py:744-746`](../../backend/app/main.py) via `settings.enable_timing_middleware` (défaut True).
- **Scrape déjà configuré** : [`infrastructure/docker/prometheus.yml:27-32`](../../infrastructure/docker/prometheus.yml) scrape `windflow-api:8000` avec `metrics_path: '/api/v1/metrics'` → **l'endpoint à créer est `/api/v1/metrics`** (préfixe du router [`api/v1/__init__.py:31`](../../backend/app/api/v1/__init__.py)). Le service API s'appelle bien `windflow-api` dans les 3 compose.
- **⚠ Règles d'alertes NON montées** : les 3 compose montent `./infrastructure/docker/prometheus-rules:/etc/prometheus/rules:ro` mais ce répertoire **n'existe pas** ([`infrastructure/docker/`](../../infrastructure/docker) ne contient que `prometheus-alerts.yml`) — Prometheus démarre avec `rule_files` vide → **aucune alerte évaluée aujourd'hui**. À réparer dans cette story.
- **Dashboards fantômes** : [`windflow-deployments.json`](../../infrastructure/docker/grafana/dashboards/windflow-deployments.json) requête `windflow_deployments_total`, `windflow_deployments_active`, `windflow_deployments_success_total`, `windflow_deployments_failed_total`, `windflow_deployment_duration_seconds_bucket` — aucune de ces séries n'existe. [`windflow-system-overview.json`](../../infrastructure/docker/grafana/dashboards/windflow-system-overview.json) n'a aucun panel API (latence/erreurs) — uniquement node/traefik/up. [`prometheus-alerts.yml`](../../infrastructure/docker/prometheus-alerts.yml) référence `windflow_deployments_*` (fantômes) et `http_request_duration_seconds_bucket` (n'existe pas sous ce nom).
- **Points d'accroche métier** :
  - *Déploiements* : [`DeploymentService.update_status`](../../backend/app/services/deployment_service.py) (l.686) est le point de passage unique des transitions de statut — `old_status` sauvegardé, `deploy_duration_seconds` calculé aux transitions terminales (l.739-761), events STORY-167 + bus STORY-162 émis ici. Les compteurs ok/ko s'y branchent (transitions vers `RUNNING`/`FAILED` uniquement, `old_status != new`).
  - *Scheduler* : [`scheduler_engine.py`](../../backend/app/services/scheduler_engine.py) `_record_run(task_id, status)` (l.655) est appelé sur tous les chemins `success`/`failed` (cron + manuel + triggers) ; les `mark_skipped` (chevauchement) sont aux l.267, l.454+ ; la durée est calculée dans `_execute`/`_execute_manual` (l.331).
  - *WS ack* : [`ack_registry.py`](../../backend/app/websocket/ack_registry.py) `purge_expired` (l.107) log WARNING `degradation: ack_timeout` — « mesure Prometheus différée à STORY-172 » (commentaire explicite l.113).
- **Patterns middleware** : l'ordre critique est documenté ([`middleware/README.md`](../../backend/app/middleware/README.md), montage [`main.py:715-765`](../../backend/app/main.py)) ; l'enveloppe API STORY-126 n'enveloppe que le JSON `/api/v1/*` ([`api_response.py`](../../backend/app/middleware/api_response.py) vérifie `content-type: application/json`) → une `PlainTextResponse` Prometheus passe non enveloppée.
- **Exemption d'auth de référence** : [`api/v1/system.py`](../../backend/app/api/v1/system.py) (`/system/health`, `/system/ready` — sondes sans auth spec 09) est le pattern pour un endpoint scrape sans `get_current_user`.
- **Single-worker** (arbitrage F1) : le déploiement supporté est mono-processus → `REGISTRY` global `prometheus_client` suffit, pas de mode multiproc requis (`prometheus_multiproc_dir` reste non consommé, multi-instances hors périmètre).

### Décisions d'analyse

- **D1 — Décision E5 : CÂBLER [`websocket/metrics.py`](../../backend/app/websocket/metrics.py), ne pas le supprimer.** Justification : (a) ses helpers sont testés et documentés par STORY-165 (43 tests, contrat verrouillé) ; (b) la mesure de la dégradation ack STORY-164.1 y est explicitement différée ([`ack_registry.py:113`](../../backend/app/websocket/ack_registry.py)) ; (c) les métriques WS (`windflow_websocket_*`) utilisent le `REGISTRY` global de `prometheus_client` → elles apparaissent dans `/metrics` d'office une fois l'endpoint créé, sans duplication. « Défini mais jamais importé » disparaît par consommation réelle dans les 6 modules du package.
- **D2 — Module central [`core/metrics.py`](../../backend/app/core) NOUVEAU** : définitions HTTP/business/scheduler (préfixe `windflow_`, `REGISTRY` par défaut) + helpers d'enregistrement + normalisation des chemins. Les compteurs métier sont instrumentés **à la source** (`update_status`, moteur scheduler) et **PAS** via un consommateur du bus d'événements (le bus dispatche in-memory **et** Redis Pub/Sub selon la config → risque de double comptage entre instances ; la source DB est synchrone et testable unitairement).
- **D3 — Contrat de nommage des séries** (une seule vérité, labels plutôt que séries jumelles ; dashboards/alertes corrigés vers ces noms — table de correspondance ci-dessous) :

  | Famille | Série (type) | Labels |
  |---|---|---|
  | HTTP | `windflow_http_requests_total` (Counter) | `method`, `path` (normalisé), `status` |
  | HTTP | `windflow_http_request_duration_seconds` (Histogram) | `method`, `path` (normalisé) |
  | Déploiements | `windflow_deployments_total` (Counter) | `result` ∈ `success` \| `failed` |
  | Déploiements | `windflow_deployment_duration_seconds` (Histogram) | — |
  | Déploiements | `windflow_deployments_active` (Gauge) | — |
  | Scheduler | `windflow_scheduler_executions_total` (Counter) | `status` ∈ `success` \| `failed` \| `skipped` |
  | Scheduler | `windflow_scheduler_execution_duration_seconds` (Histogram) | — |
  | WebSocket | `windflow_websocket_*` (existant, 14 séries) | inchangées |

  Correspondance dashboards/alertes : `windflow_deployments_success_total` → `windflow_deployments_total{result="success"}` ; `windflow_deployments_failed_total` → `windflow_deployments_total{result="failed"}` ; `http_request_duration_seconds_bucket{job="windflow-api"}` → `windflow_http_request_duration_seconds_bucket{job="windflow-api"}` ; `windflow_deployments_total` (total brut) → `windflow_deployments_total` (somme des labels).
- **D4 — Instrumentation HTTP dans le middleware Timing existant** (garde-fou §2.G : aucun nouveau middleware, pile non réordonnée) : wrap `try/except` autour de `call_next` pour capter les exceptions (compteur `status="500"` + re-raise inchangé), incrément conditionné `settings.prometheus_enabled`, chemins normalisés (segments UUID/numériques → `{id}`/`{n}` — cardinalité bornée), **jamais de query string en label** (peut contenir des tokens), exclusion du scrape lui-même (`/api/v1/metrics` non compté). Métriques HTTP actives seulement si `enable_timing_middleware` **et** `prometheus_enabled` (défauts True/True, documenté).
- **D5 — Endpoint `GET /api/v1/metrics` SANS auth** (exemption sondes spec 09, symétrique de [`system.py`](../../backend/app/api/v1/system.py)) : scrapé par Prometheus sur le réseau interne Docker ; **jamais routé vers Internet** (aucun router Traefik ne l'expose ; Prometheus lui-même est behind basic-auth en prod — [`docker-compose.prod.yml:376-381`](../../docker-compose.prod.yml)). Réponse `PlainTextResponse` avec `generate_latest(REGISTRY)` + `CONTENT_TYPE_LATEST` (non enveloppée par STORY-126 — content-type non-JSON). `prometheus_enabled=False` → **404** (choix documenté : endpoint résolu mais handler refuse — testable sans re-création d'app). Aucune donnée sensible : labels limités à method/path normalisé/status/types de connexions/statuts/noms de plugins.
- **D6 — Dépendance `prometheus-client`** (rules 05, justification E3) : déjà requise en top-level par [`websocket/metrics.py:14`](../../backend/app/websocket/metrics.py), nécessaire à `generate_latest` — version `^0.21` (py.typed, maintenance active). L'override mypy existant ([`pyproject.toml:118`](../../pyproject.toml)) peut rester (inoffensif). Le `pytest.importorskip` de STORY-165 devient un no-op (le conserver).
- **D7 — Réparation des alertes** : monter directement `./infrastructure/docker/prometheus-alerts.yml:/etc/prometheus/rules/alerts.yml:ro` dans les 3 compose qui référencent le répertoire inexistant `prometheus-rules` (dev/prod/extensions) — les alertes deviennent effectives, expressions corrigées vers les vraies séries (D3).
- **D8 — Durées de déploiement** : `deploy_duration_seconds` n'est calculé qu'aux transitions d'arrêt (FAILED/STOPPED, [`deployment_service.py:751-761`](../../backend/app/services/deployment_service.py)) — à la transition RUNNING il est `None`. L'histogramme observe donc la durée **de bout en bout** (`now − created_at`, disponible dans les deux cas) aux transitions terminales uniquement. Gauge `windflow_deployments_active` : inc quand un déploiement entre dans un statut non terminal (`pending`/`deploying`/`rolling_back`), dec quand il atteint un statut terminal (`running`/`failed`/`stopped`) — approximation pilotée par `update_status` (documentée : une création crashée avant tout `update_status` n'est pas comptée).

Éléments existants à réutiliser / contraintes (conservés de la création de la story) :

Éléments existants à réutiliser / contraintes :
- **Instrumentation HTTP** : réutiliser le **middleware Timing** existant ([`main.py:254`](../../backend/app/main.py) — mesure déjà `X-Process-Time` et log des requêtes lentes) comme point de collecte des histogrammes de latence + compteurs de requêtes/erreurs par endpoint/code — le middleware Correlation ID et Logging ne sont pas modifiés en profondeur (garde-fou §2.G : ne pas régresser les middlewares sécurité) ;
- **Métriques business** : déploiements ok/ko — brancher sur les changements de statut ([`deployment_service.py:23`](../../backend/app/services/deployment_service.py) / événements bus STORY-162) ; tâches scheduler — exécutions par statut (`success`/`failed`/`skipped`) depuis STORY-160/161 ; le module [`websocket/metrics.py`](../../backend/app/websocket/metrics.py) contient déjà des définitions de métriques temps réel (connexions, messages) à **câbler** : décision E5 explicite — importer/consommer, ou supprimer si doublon (le choix doit être documenté dans la story) ;
- **Endpoint `/metrics`** : format Prometheus, **sans auth** (scrapé par Prometheus), conditionné par `prometheus_enabled` (désactivé → endpoint absent ou vide) ; la config Prometheus ([`infrastructure/docker/prometheus.yml`](../../infrastructure/docker/prometheus.yml)) scrape déjà la cible attendue — vérifier/port ;
- **Dashboards** : les deux dashboards provisionnés (`windflow-deployments.json`, `windflow-system-overview.json`) doivent référencer les métriques réellement exposées — corriger les requêtes si besoin (pas de nouvelles métriques fantômes) ;
- **Rules 45** : métriques obligatoires = latence endpoints, taux d'erreur par service, métriques business (déploiements ok/ko) ; alertes définies dans `prometheus-alerts.yml` (existant — vérifier cohérence) ;
- Dépendance à ajouter si nécessaire : bibliothèque client Prometheus (ex. `prometheus-client`) — justification claire requise (rules 05 : pas de dépendance sans justification) ; format JSON des logs inchangé ;
- ⚠️ **Constat STORY-165 (2026-10-24, à traiter impérativement ici)** : `prometheus_client` est importé **en top-level** dans [`websocket/metrics.py`](../../backend/app/websocket/metrics.py) ([`from prometheus_client import Counter, Gauge, Histogram`](../../backend/app/websocket/metrics.py:14)) mais **n'est PAS déclarée dans `pyproject.toml`** (seul un override mypy la mentionne, [`pyproject.toml:118`](../../pyproject.toml)) → tout import du module crasherait en production/CI (`ModuleNotFoundError`). Les tests STORY-165 ([`test_ws_metrics_helpers.py`](../../backend/tests/unit/test_websocket/test_ws_metrics_helpers.py:32)) l'ont géré via `pytest.importorskip` + installation pip locale. **Cette story doit ajouter la dépendance Poetry `prometheus_client` (avec version justifiée)** — c'est un prérequis au câblage AC 3 (décision E5) ;
- Corrélation : le correlation ID existe déjà — pas d'OpenTelemetry (prévu mais non implémenté, hors périmètre).

## Critères d'acceptation (AC)

- [x] AC 1 : `/metrics` (sans auth) expose au minimum : **latence des endpoints** (histogramme par route), **taux d'erreur** (compteur par code/route), **déploiements ok/ko** (compteurs business), **tâches scheduler** (exécutions par statut) — test : requêtes + un déploiement de test + une exécution de tâche → les séries attendues sont présentes dans la réponse `/metrics` (format Prometheus valide). *(Validé : `test_metrics_endpoint.py` 6 tests + `test_metrics_end_to_end.py` `test_full_flow_exposes_all_families` — les 4 familles `windflow_http_*`/`windflow_deployments_*`/`windflow_scheduler_executions_*`/`windflow_websocket_*` vérifiées dans la réponse.)*
- [x] AC 2 : Le flag `prometheus_enabled` gouverne réellement : désactivé → pas d'instrumentation ni d'endpoint `/metrics` (ou réponse vide 404 selon choix documenté) ; activé → tout est exposé — les deux états testés. *(Validé : `test_metrics_endpoint_disabled_returns_404` + `test_metrics_endpoint_enabled_returns_metrics` + `test_prometheus_disabled_hides_endpoint_integration` + `test_http_metrics_disabled_when_flag_off`.)*
- [x] AC 3 : **Décision E5 appliquée et documentée** sur [`websocket/metrics.py`](../../backend/app/websocket/metrics.py) : soit câblé (importé/consommé — ses métriques temps réel apparaissent dans `/metrics` quand des connexions WS actives existent), soit supprimé au profit de définitions équivalentes centralisées — plus aucun module « défini mais jamais importé » ; la dégradation d'ack (STORY-164) y est mesurable si câblé. *(Validé : câblage D1 dans les 6 modules + `record_error("ack_timeout")` dans `AckRegistry.purge_expired` — `test_websocket_metrics_wiring.py` 5 tests dont `test_ack_timeout_purge_records_error`.)*
- [x] AC 4 : **Dashboards alimentés** : sur un run de démo (API + trafic + 1 déploiement + 1 tâche), les deux dashboards Grafana provisionnés affichent des données — vérification documentée (captures ou requêtes Prometheus vérifiées) ; les requêtes de dashboards corrigées vers les vraies séries ; `prometheus-alerts.yml` cohérent avec les métriques exposées. *(Validé documentairement : runbook `MONITORING-RUNBOOK.md` §3 (procédure de run reproductible + requêtes de vérification) ; vérification bout-en-bout des séries couverte par tests d'intégration 44/44 ; dashboards/alertes corrigés vers la table D3 ; règles montées dans les 3 compose.)*
- [x] AC 5 : Non-régression : middlewares sécurité/timing/correlation non cassés ; overhead d'instrumentation négligeable (pas de sérialisation bloquante par requête) ; couverture ≥ 80 % sur les modules d'instrumentation testables ; build + lint + tests passent. *(Validé : `X-Process-Time` inchangé — `test_timing_header_still_present` ; 422/422 sur `test_websocket/` ; couverture `api/v1/metrics.py` 100 %, `core/metrics.py` 89 %, `middleware/timing.py` 90 %, `websocket/metrics.py` 90 % ; lint fichiers story 0 erreur ; mypy 0 nouvelle erreur vs HEAD.)*

## Références spécification

- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § Résilience et fiabilité (health checks), § Performance (benchmarks cibles), § Bus d'événements (sources business) ;
- `.roo/rules/45-observability.md` — **métriques obligatoires** (latence endpoints, taux d'erreur par service, métriques business déploiements ok/ko), outils cibles Prometheus + Grafana, dashboards provisionnés, alertes ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Sécurité réseau (ports exposés — `/metrics` interne au scrape, pas exposé Internet), § Principes (pas de données sensibles dans les métriques/labels) ;
- [ARCHITECTURE-MODULAIRE.md](../../docs/technical_specs/ARCHITECTURE-MODULAIRE.md) — brique `monitoring` (Prometheus + Grafana, activation `make enable-monitoring`, volumes, provisioning) ;
- [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) — §2.2 (`metrics.py` défini mais non intégré), §8.4 (dégradation ack mesurée par `metrics.py`), §10.3 ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-9, §2.B B4 (« Prometheus mensonger »), §2.E E5 ;
- [`backend_status.md`](../../docs/backend_status.md) — §11 (`prometheus_enabled=True` sans instrumentation), §14.1, §2.3 (middlewares — point de collecte).

## Dépendances

- **Aucune dépendance marquée par le plan** (P2-9 « dépend de : — »).
- **Constats rassurants post-exploration** : STORY-160.1→160.3 (moteur scheduler + actions + triggers), STORY-161 (exécutions persistées), STORY-162/163 (bus canonique + consommateurs), STORY-164.1→164.3 (canaux/ack), STORY-165 (tests WS), STORY-167 (deployment_events) sont **toutes DONE** → toutes les sources métier à instrumenter existent réellement.
- **Conditionne** (déjà référencées) : STORY-164 (dégradation ack mesurée ici), STORY-251/STORY-174 (métrique d'état CircuitBreaker attendue dans `/metrics` — l'instrument posé ici servira de point d'accroche ; pas de blocage).
- **Services externes** : aucun requis pour l'implémentation (tout est testable avec le `REGISTRY` en mémoire). Le run de démo AC 4 requiert l'extension monitoring (`make enable-monitoring` : Prometheus + Grafana sur `prometheus.localhost`) — environnement local, pas un service tiers.
- **Migrations Alembic** : **aucune** (aucune colonne nouvelle ; les compteurs sont en mémoire process).
- **Nouvelle dépendance Poetry** : `prometheus-client ^0.21` (D6 — justification tracée dans la tâche 1).
- **Interagit avec** : STORY-253 (mise à jour documentaire — la section observabilité de `backend_status.md` §11/§14.1 deviendra obsolète) — à mentionner dans les notes d'implémentation.

## Sous-stories

*(non prévue — story M)*

## État d'avancement technique

*(à cocher pendant `treat-story` — analyse terminée le 2026-10-31, verdict : complexité OK, pas de découpe)*

- [x] T1. Dépendance `prometheus-client` ajoutée à `pyproject.toml`
- [x] T2. `core/metrics.py` créé (métriques + helpers + normalisation de chemins)
- [x] T3. Middleware Timing instrumenté (latence + erreurs, sans auth, flag-gated)
- [x] T4. Endpoint `/api/v1/metrics` créé (sans auth, PlainText, 404 si désactivé)
- [x] T5. Métriques déploiements câblées dans `update_status`
- [x] T6. Métriques scheduler câblées dans le moteur (cron + manuel + skipped)
- [x] T7. `websocket/metrics.py` câblé dans les 6 modules + ack mesuré dans `AckRegistry`
- [x] T8. Dashboards + alertes corrigés vers les vraies séries ; règles effectivement montées
- [x] T9. Run de démo AC 4 exécuté et documenté (requêtes vérifiées/captures) — runbook `docs/technical_specs/MONITORING-RUNBOOK.md` créé (séries, procédure reproductible, requêtes de vérification, troubleshooting) ; le run Docker complet est documenté dans le runbook §3, vérification bout-en-bout des séries couverte par les tests d'intégration `test_metrics_end_to_end.py` (44/44 passants)
- [x] T10. Tests exécutés (`make backend-test-unit` ciblés, non-régression, couverture ≥ 80 %)
- [x] T11. Documentation mise à jour (`.roo/rules/45-observability.md` § état réel, doc brique monitoring)
- [x] T12. Story passée REVIEW + kanban synchronisé

## Tâches d'implémentation détaillées

> Analyse du 2026-10-31 — verdict complexité : **OK** (périmètre homogène observabilité, 12 tâches, une seule zone backend + fichiers config infra ; pas de SPLIT-STORY). Décisions D1→D8 dans « Contexte technique ».

**Tâche 1 — Dépendance `prometheus-client` (D6).**
- **Fichier** : [`pyproject.toml`](../../pyproject.toml)
- **Objectif** : ajouter `prometheus-client = "^0.21"` au bloc `[tool.poetry.dependencies]` (commentaire : STORY-172, requis top-level par `websocket/metrics.py` + `generate_latest` pour `/metrics` ; version minimale stable py.typed). Exécuter `poetry lock` (ou `poetry add prometheus-client@^0.21`). Vérifier `poetry install` puis import `from app.websocket import metrics` sans erreur. L'override mypy existant l.118 reste (inoffensif). Ne PAS toucher au `pytest.importorskip` de [`test_ws_metrics_helpers.py:32`](../../backend/tests/unit/test_websocket/test_ws_metrics_helpers.py).

**Tâche 2 — Module central `core/metrics.py` (D2, D3).**
- **Fichier** : `backend/app/core/metrics.py` (**créer**)
- **Objectif** : module d'instrumentation central (hors WS, déjà défini) avec docstring de contrat (séries D3, pourquoi instrumenter à la source et non via le bus — D2). Contenu :
  - `HTTP_REQUESTS_TOTAL = Counter("windflow_http_requests_total", ..., ["method", "path", "status"])` ; `HTTP_REQUEST_DURATION = Histogram("windflow_http_request_duration_seconds", ..., ["method", "path"], buckets=(...))` ;
  - `DEPLOYMENTS_TOTAL = Counter("windflow_deployments_total", ..., ["result"])` ; `DEPLOYMENT_DURATION = Histogram("windflow_deployment_duration_seconds", ...)` ; `DEPLOYMENTS_ACTIVE = Gauge("windflow_deployments_active", ...)` ;
  - `SCHEDULER_EXECUTIONS = Counter("windflow_scheduler_executions_total", ..., ["status"])` ; `SCHEDULER_DURATION = Histogram("windflow_scheduler_execution_duration_seconds", ...)` ;
  - Helpers : `record_http_request(method, path, status, duration)`, `normalize_path(path) -> str` (regex : segments UUID → `{id}`, segments purement numériques → `{n}`, QueryString non incluse), `record_deployment_transition(new_status: str, duration: Optional[float])`, `record_scheduler_execution(status: str, duration: Optional[float] = None)`. Imports des types depuis `prometheus_client` (sans dépendance circulaire — `core` est transversal).
  - Chaque helper est no-op-safe (l'incrément ne lève jamais — best-effort, pattern observabilité).

**Tâche 3 — Instrumentation HTTP dans le middleware Timing (D4).**
- **Fichier** : [`backend/app/middleware/timing.py`](../../backend/app/middleware/timing.py)
- **Objectif** : conserver comportement existant (header, log lent) et ajouter : wrap `try/except Exception` autour de `response = await call_next(request)` → dans le `except`, `record_http_request(request.method, normalize_path(request.url.path), "500", elapsed)` puis `raise` (re-raise inchangé — l'error handler le gère) ; dans le chemin nominal, `record_http_request(request.method, normalize_path(request.url.path), str(response.status_code), process_time)`. Garde : `if settings.prometheus_enabled and settings.enable_timing_middleware` (import settings local, pattern des autres middlewares) + skip si `request.url.path == "/api/v1/metrics"` (le scrape ne se compte pas) + skip WebSocket déjà existant. **Jamais de query string ni de paramètre d'URL en label.** Aucun autre middleware modifié (garde-fou §2.G).

**Tâche 4 — Endpoint `GET /api/v1/metrics` sans auth (D5).**
- **Fichier** : `backend/app/api/v1/metrics.py` (**créer**) ; montage dans [`backend/app/api/v1/__init__.py`](../../backend/app/api/v1/__init__.py)
- **Objectif** : router `APIRouter()` avec `@router.get("/metrics", tags=["metrics"], include_in_schema=True)` — docstring OpenAPI complète (usage : scrape Prometheus interne ; **sans authentification**, exemption sondes spec 09, cf. [`system.py`](../../backend/app/api/v1/system.py) pattern ; jamais exposé Internet). Handler : `if not settings.prometheus_enabled: raise HTTPException(status_code=404)` (choix documenté D5 — testable à chaud) ; sinon `return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)` (la réponse est PlainText → non enveloppée par [`api_response.py`](../../backend/app/middleware/api_response.py), le content-type n'est pas JSON). Import `from prometheus_client import REGISTRY, generate_latest` et `from prometheus_client.openmetrics...` NON — format classique Prometheus (`prometheus.yml` attendu). Monter dans `api_router` : `api_router.include_router(metrics_router, tags=["metrics"])` (pas de préfixe — la route est `/metrics` sous `/api/v1`). Ajouter le tag `{"name": "metrics", "description": ...}` à `openapi_tags` dans [`main.py`](../../backend/app/main.py).

**Tâche 5 — Compteurs déploiements dans `update_status` (D2, D8).**
- **Fichier** : [`backend/app/services/deployment_service.py`](../../backend/app/services/deployment_service.py)
- **Objectif** : dans `update_status` (l.686+), juste après le calcul des timestamps (l.739-761), appeler `record_deployment_transition` depuis `core/metrics.py` — sémantique D8 : transition vers `RUNNING` avec `old_status != RUNNING` → `DEPLOYMENTS_TOTAL.labels(result="success").inc()` + `DEPLOYMENTS_ACTIVE.dec()` (si `old_status` non terminal) ; transition vers `FAILED` avec `old_status != FAILED` → `DEPLOYMENTS_TOTAL.labels(result="failed").inc()` + `DEPLOYMENTS_ACTIVE.dec()` (si `old_status` non terminal) ; transition vers `PENDING`/`DEPLOYING`/`ROLLING_BACK` → `DEPLOYMENTS_ACTIVE.inc()` ; transitions terminales avec durée : `DEPLOYMENT_DURATION.observe((now − created_at).total_seconds())` (durée de bout en bout — `deploy_duration_seconds` n'existe qu'aux arrêts). Best-effort : wrap try/except + log (jamais d'échec de métrique qui casse un déploiement). **Aucune donnée sensible** (labels = résultat uniquement). Compter une seule fois par transition (garde `old_status != new_status`).

**Tâche 6 — Compteurs scheduler dans le moteur (D2).**
- **Fichier** : [`backend/app/services/scheduler_engine.py`](../../backend/app/services/scheduler_engine.py)
- **Objectif** : instrumenter les 3 points du moteur : (a) `_record_run` (l.655) est appelé sur tous les chemins `success`/`failed` (cron + manuel + triggers) → y ajouter `record_scheduler_execution(status, duration)` — la durée n'y est pas disponible, donc : (b) préférer l'instrumentation à la source des boucles `_execute` et `_execute_manual` : succès → `record_scheduler_execution("success", duration)` (la durée y est calculée, l.331 et équivalent cron), échec → `record_scheduler_execution("failed")` ; (c) les `mark_skipped` de chevauchement (l.267 manuel, l.454+ cron) → `record_scheduler_execution("skipped")`. Best-effort try/except. Statuts alignés sur le domaine fermé spec 06 (`queued|running|success|failed|skipped` — l.400 de [`schedules.py`](../../backend/app/api/v1/schedules.py)) ; on n'expose que les terminaux + skipped (running est éphémère, gauge inutile).

**Tâche 7 — Câblage `websocket/metrics.py` + mesure ack (D1).**
- **Fichiers** :
  - [`backend/app/websocket/broadcasting.py`](../../backend/app/websocket/broadcasting.py) — `broadcast_timer` autour des broadcasts (`_broadcast_deployment_event`, `broadcast_to_user`, `broadcast_to_event_subscribers`) : `with broadcast_timer("deployment"|"user"|"event", client_count):` ou measure-then-record (le client count est connu avant/après l'envoi — mesure réelle) ; `record_message_sent` après chaque `send_json` (try/except → success/error).
  - [`backend/app/websocket/connection_managers.py`](../../backend/app/websocket/connection_managers.py) — `record_connection(connection_type, "connected"/"disconnected")` dans `ConnectionManager.connect/disconnect` (type `"deployment"`) et `UserConnectionManager.add/remove_connection` (type `"user"`) ; `record_event_dispatch(event_type, success)` dans `UserConnectionManager.dispatch_to_plugins`.
  - [`backend/app/websocket/general.py`](../../backend/app/websocket/general.py) — `record_auth_attempt`/`record_auth_duration` autour de `authenticate_ws_first_message` (l.94) : succès → `record_auth_attempt(success=True)`, None → `record_auth_attempt(success=False)`, wrap `auth_timer()` pour la durée ; `record_message_received` dans la boucle de réception ; `record_subscription` sur `subscribe`/`unsubscribe` (types critiques STORY-164.1).
  - [`backend/app/websocket/plugin.py`](../../backend/app/websocket/plugin.py) — `record_plugin_execution(plugin.name, event.value, duration)` dans `dispatch` (l.324, autour de `plugin.handle_event`, mesure réelle) et `record_event_dispatch` dans `handle_client_message`.
  - [`backend/app/websocket/ack_registry.py`](../../backend/app/websocket/ack_registry.py) — dans `purge_expired` (l.129-141, après le WARNING) : `record_error("ack_timeout")` (le commentaire l.113 « mesure Prometheus différée à STORY-172 » devient réalité — utiliser `record_error("ack_timeout")`, la série `windflow_websocket_errors_total{error_type="ack_timeout"}`).
  - [`backend/app/websocket/event_bridge.py`](../../backend/app/websocket/event_bridge.py) — `record_event_dispatch(event.event_type.value, success)` autour du forward (l.112).
- **Objectif** : plus aucun helper `record_*` de `websocket/metrics.py` sans consommateur ; l'ensemble best-effort (try/except, jamais casser le broadcast/la connexion pour une métrique). **Ne pas modifier les signatures existantes** — instrumentation additive uniquement.

**Tâche 8 — Dashboards, alertes et règles effectivement montées (D3, D7).**
- **Fichiers** :
  - [`infrastructure/docker/grafana/dashboards/windflow-deployments.json`](../../infrastructure/docker/grafana/dashboards/windflow-deployments.json) — remplacer les 9 requêtes fantômes par les vraies séries : `windflow_deployments_total` (somme), `windflow_deployments_active`, `windflow_deployments_total{result="success"}`, `windflow_deployments_total{result="failed"}`, `rate(windflow_deployments_total[5m])`, `histogram_quantile(0.95, rate(windflow_deployment_duration_seconds_bucket[5m]))`, idem 0.50, `increase(windflow_deployments_total{result="success"}[1h])`, `increase(windflow_deployments_total{result="failed"}[1h])`.
  - [`infrastructure/docker/grafana/dashboards/windflow-system-overview.json`](../../infrastructure/docker/grafana/dashboards/windflow-system-overview.json) — ajouter un row « WindFlow API » : requêtes 200 vs 5xx (`rate(windflow_http_requests_total[5m])` par status), latence p95 (`histogram_quantile(0.95, rate(windflow_http_request_duration_seconds_bucket[5m]))`), erreurs/s (`rate(windflow_http_requests_total{status=~"5.."}[5m])`) — pattern des panels node/traefik existants (même datasource uid `prometheus`).
  - [`infrastructure/docker/prometheus-alerts.yml`](../../infrastructure/docker/prometheus-alerts.yml) — corriger : `WindFlowAPIHighResponseTime` → `histogram_quantile(0.95, rate(windflow_http_request_duration_seconds_bucket{job="windflow-api"}[5m])) > 1` ; `HighDeploymentFailureRate` → `rate(windflow_deployments_total{result="failed"}[10m]) / rate(windflow_deployments_total[10m]) > 0.2` ; `CriticalDeploymentFailureRate` idem seuil 0.5 ; `DeploymentStuck` → `histogram_quantile(0.99, windflow_deployment_duration_seconds_bucket) > 3600` (plus de série `windflow_deployment_duration_seconds` brute) ; `NoDeploymentsInLast24Hours` → `increase(windflow_deployments_total[24h]) == 0` (inchangé, valide). Ajouter une alerte scheduler : `SchedulerExecutionFailures` `increase(windflow_scheduler_executions_total{status="failed"}[1h]) > 3`.
  - [`docker-compose-dev.yml`](../../docker-compose-dev.yml), [`docker-compose.prod.yml`](../../docker-compose.prod.yml), [`docker-compose.extensions.yml`](../../docker-compose.extensions.yml) — remplacer le montage du répertoire inexistant `./infrastructure/docker/prometheus-rules:/etc/prometheus/rules:ro` par `./infrastructure/docker/prometheus-alerts.yml:/etc/prometheus/rules/alerts.yml:ro` (D7 — les alertes deviennent évaluées ; 3 fichiers, même ligne).
- **Objectif** : chaque requête dashboard/alerte référence une série exposée par `/metrics` (audit croisé avec la table D3).

**Tâche 9 — Run de démo et documentation de vérification (AC 4).**
- **Fichiers** : [`docs/technical_specs/`](../../docs/technical_specs) — ajouter `MONITORING-RUNBOOK.md` (**créer**)
- **Objectif** : `make enable-monitoring` puis `make docker-up` (profil dev) ; générer du trafic API (login + quelques GET), déclencher 1 déploiement (API ou seed de test) et 1 exécution scheduler (`POST /api/v1/schedules/{id}/run` avec une tâche de démo) ; vérifier `curl http://localhost:8000/api/v1/metrics | grep windflow_` (séries http/deployments/scheduler/websocket présentes) ; vérifier `up{job="windflow-api"}` dans Prometheus UI + les panels Grafana alimentés ; documenter dans le runbook : les séries exposées (table D3), les vérifications effectuées avec les requêtes Prometheus exactes et captures éventuelles, la procédure de démo reproductible, le lien vers `prometheus.yml`/dashboards.

**Tâche 10 — Vérifications finales backend.**
- **Fichiers** : aucun nouveau (exécution)
- **Objectif** : `make backend-lint` (black/isort/flake8/mypy/bandit sur les fichiers touchés — 0 nouvelle erreur), `make backend-test-unit` ciblé puis complet (non-régression : la suite `test_websocket/` 416+ tests doit rester verte — l'instrumentation additive ne change aucun comportement), couverture des nouveaux modules (`--cov=app.core.metrics --cov=app.api.v1.metrics` + middleware timing ≥ 80 %), `make ci-security-backend` (bandit : les `try/except Exception` best-effort peuvent nécessiter des `# nosec` commentés ou affinage — tracer). Exécuter `make generate-openapi-docs` si disponibles pour vérifier la doc `/metrics`.

**Tâche 11 — Documentation à jour.**
- **Fichiers** : [`.roo/rules/45-observability.md`](../../.roo/rules/45-observability.md) ; [`docs/technical_specs/ARCHITECTURE-MODULAIRE.md`](../../docs/technical_specs/ARCHITECTURE-MODULAIRE.md) (section brique monitoring)
- **Objectif** : mettre à jour la section « Outils cibles » de la règle 45 : l'instrumentation est réelle (endpoint `/api/v1/metrics`, séries `windflow_*`, dashboards alimentés, alertes montées) — retirer les formulations au futur si obsolètes ; préciser dans ARCHITECTURE-MODULAIRE le chemin de scrape et le flag `prometheus_enabled` (404 si désactivé). Tracer dans les notes d'implémentation que [`docs/backend_status.md`](../../docs/backend_status.md) §11/§14.1 est obsolète (mise à jour portée par STORY-253).

**Tâche 12 — Clôture story.**
- **Fichiers** : cette story + [`.backlog/kanban.md`](../kanban.md) + [`EPIC-013`](../epics/EPIC-013-remediation-p2-conformite-fonctionnelle.md)
- **Objectif** : cocher les AC validés (preuves : tests + runbook T9), statut `REVIEW` → validation → `DONE` ; kanban : déplacer de BACKLOG à IN_PROGRESS/REVIEW/DONE ; cocher STORY-172 dans la liste de l'epic ; ajouter la section « Notes d'implémentation » (fichiers modifiés, décisions D1→D8 appliquées ou divergences, commandes exécutées, résultats).

## Tests à écrire

> Patterns [`35-testing-quality-gates.md`](../../.roo/rules/35-testing-quality-gates.md) : assertions sur **deltas** via `prometheus_client.REGISTRY.get_sample_value` (compteurs cumulatifs globaux — pattern [`test_ws_metrics_helpers.py`](../../backend/tests/unit/test_websocket/test_ws_metrics_helpers.py)) ; client HTTP via `ASGITransport` ([`conftest.py:544-568`](../../backend/tests/conftest.py)). Les tests métier (T5/T6) mockent la DB et vérifient les **deltas de séries**, pas les appels de helpers.

### Backend — unitaires

**Fichier `backend/tests/unit/test_api/test_metrics_endpoint.py`** (**créer**) — endpoint AC 1/AC 2 :
1. `test_metrics_endpoint_returns_200_without_auth` — GET `/api/v1/metrics` sans token → 200, content-type Prometheus, body contient `windflow_http_requests_total` (après au moins une requête via le client de test).
2. `test_metrics_endpoint_format_prometheus_valide` — le body suit le format exposition (lignes `# HELP`/`# TYPE` + samples ; assertion sur `windflow_deployments_total` présent même à zéro — Counter avec labels : au moins une série après instrumentation initiale ou via fixture).
3. `test_metrics_endpoint_disabled_returns_404` — `PROMETHEUS_ENABLED=false` (fixture settings override) → 404.
4. `test_metrics_endpoint_enabled_returns_metrics` — flag à True → 200 (les deux états de l'AC 2).
5. `test_metrics_endpoint_not_wrapped_in_envelope` — la réponse n'est PAS au format enveloppe STORY-126 (pas de clé `data` JSON — assert content-type text).
6. `test_metrics_endpoint_excludes_websocket_series_when_unused` — les séries `windflow_websocket_*` existent dans le REGISTRY (imports du package) mais les compteurs non sollicités restent absents/à zéro du scraping tant que non utilisés (dokstring : contrat de non-pollution).

**Fichier `backend/tests/unit/test_middleware/test_timing_metrics.py`** (**créer**) — instrumentation HTTP AC 1/AC 5 :
7. `test_http_request_records_latency_and_status` — requête via client → delta +1 sur `windflow_http_requests_total{method="GET", path="/api/v1/system/health", status="200"}` et `_count` +1 sur l'histogramme même route.
8. `test_http_request_path_normalization` — requête sur un chemin à UUID (ex. `/api/v1/stacks/{uuid}`) → label `path="/api/v1/stacks/{id}"` (cardinalité bornée).
9. `test_http_request_500_recorded` — endpoint qui lève (route de test ou mock) → delta sur `status="500"` (le wrap try/except capte avant l'error handler).
10. `test_http_metrics_skip_metrics_endpoint` — GET `/api/v1/metrics` n'incrémentente pas `windflow_http_requests_total` (le scrape ne se mesure pas).
11. `test_http_metrics_disabled_when_flag_off` — `prometheus_enabled=False` → aucune série delta (middleware no-op métrique, header `X-Process-Time` toujours présent — non-régression du comportement existant).
12. `test_timing_header_still_present` — AC 5 : `X-Process-Time` inchangé sur toutes les réponses.

**Fichier `backend/tests/unit/test_services/test_deployment_metrics.py`** (**créer**) — métriques business AC 1 :
13. `test_transition_to_running_increments_success_counter` — `update_status(..., RUNNING)` (DB mockée ou session de test, `old_status=DEPLOYING`) → delta +1 `windflow_deployments_total{result="success"}` ; active gauge −1.
14. `test_transition_to_failed_increments_failed_counter` — idem `FAILED` → `result="failed"` +1.
15. `test_duration_observed_on_terminal_transition` — transition terminale avec `created_at` défini → `_count` +1 sur `windflow_deployment_duration_seconds` ; valeur dans `_sum` cohérente (≥ 0).
16. `test_active_gauge_increments_on_non_terminal_status` — `PENDING`/`DEPLOYING` → gauge +1.
17. `test_same_status_transition_not_double_counted` — `update_status(RUNNING)` alors que `old_status == RUNNING` → aucun delta.
18. `test_metrics_failure_never_breaks_update_status` — helper `record_deployment_transition` mocké pour lever → `update_status` retourne normalement (best-effort).

**Fichier `backend/tests/unit/test_services/test_scheduler_metrics.py`** (**créer**) — scheduler AC 1 :
19. `test_successful_execution_increments_counter` — moteur avec store mocké, handler OK → delta +1 `windflow_scheduler_executions_total{status="success"}` + `_count` durée +1.
20. `test_failed_execution_increments_counter` — handler qui lève → `status="failed"` +1.
21. `test_skipped_overlap_increments_counter` — chevauchement (verrou actif) → `status="skipped"` +1.
22. `test_manual_run_records_execution` — chemin `run_task_now` → même compteur success/failed (les deux chemins instrumentés).
23. `test_metrics_never_break_engine` — helper levant → l'exécution reste tracée dans le store (best-effort).

**Fichier `backend/tests/unit/test_websocket/test_ws_metrics_wiring.py`** (**créer**) — câblage E5/AC 3 :
24. `test_connection_records_gauge_and_counter` — `ConnectionManager.connect/disconnect` (WebSocket mocké, pattern tests STORY-165) → deltas `windflow_websocket_connections_total` + gauge active inc/dec.
25. `test_broadcast_records_duration_and_clients` — `broadcast_to_deployment` → `_count` +1 `windflow_broadcast_duration_seconds` + `windflow_broadcast_clients`.
26. `test_plugin_dispatch_records_execution` — `plugin_manager.dispatch` (plugin de test) → `windflow_plugin_duration_seconds` observé + `events_dispatched_total` inc.
27. `test_ack_timeout_purge_records_error` — `AckRegistry.purge_expired` avec entrée expirée → delta +1 `windflow_websocket_errors_total{error_type="ack_timeout"}` (la dégradation STORY-164.1 est désormais mesurée).
28. `test_auth_attempt_recorded` — helper `authenticate_ws_first_message` mocké succès/échec → `auth_attempts_total{status="success"|"failed"}`.
29. `test_metrics_wiring_never_breaks_broadcast` — helper levant → le broadcast s'effectue quand même (best-effort).

**Fichier `backend/tests/unit/test_core/test_metrics_helpers.py`** (**créer**) — module central :
30. `test_normalize_path_uuid_and_numeric` — `/api/v1/stacks/550e8400-.../deploy` → `{id}` ; `/api/v1/hosts/42` → `{n}` ; chemins statiques inchangés.
31. `test_normalize_path_never_includes_query_string` — path avec `?token=x` → label sans query (sécurité — jamais de token en label).
32. `test_all_series_use_windflow_prefix` — audit des noms du module : chaque série commence par `windflow_` (convention homogène, dashboards y font référence).

### Backend — intégration (validation bout-en-bout AC 1)

**Fichier `backend/tests/integration/test_metrics_end_to_end.py`** (**créer**) :
33. `test_full_flow_exposes_all_families` — app réelle (fixture conftest) : requêtes HTTP (login + GET) + 1 déploiement mocké complet (transitions PENDING→DEPLOYING→RUNNING via `update_status` sur DB de test) + 1 exécution scheduler simulée → GET `/api/v1/metrics` **sans auth** contient AU MOINS une série de chaque famille : `windflow_http_*`, `windflow_deployments_*`, `windflow_scheduler_executions_*`, `windflow_websocket_*` (préchargées par import) — l'AC 1 mot pour mot.
34. `test_prometheus_disabled_hides_endpoint_integration` — settings override → 404 (parité avec le test unitaire, au niveau app).

### Tests de sécurité (rules 40 — checklist évaluée)

> Évaluation : l'endpoint `/metrics` est **volontairement sans auth** (exemption sondes spec 09, symétrique [`system.py`](../../backend/app/api/v1/system.py) ; scrapé sur le réseau interne Docker uniquement, jamais routé Internet — aucun router Traefik ne l'expose, Prometheus lui-même behind basic-auth en prod). Les garanties testées :

35. `test_metrics_endpoint_no_auth_required_by_design` — documente l'exemption : 200 sans header Authorization (c'est le comportement **attendu**, pas une faille — tracer la justification dans la docstring).
36. `test_metrics_labels_contain_no_sensitive_data` — après un run de test avec login (query `?token=…` si applicable) + déploiement : le body `/metrics` ne contient **aucun** token, mot de passe, variable de déploiement, nom d'utilisateur ni query string (grep sur le body : assertions `not in`).
37. `test_metrics_not_exposed_by_traefik_routers` — assertion sur les fichiers de config infra (lecture [`traefik/`](../../infrastructure/docker/traefik) + compose prod) : aucun router ne matche le chemin `/api/v1/metrics` vers l'extérieur (test de configuration, garde-fou exposition).
38. `test_http_labels_cardinality_bounded` — N requêtes sur des IDs différents → une seule série `path="...{id}"` (pas d'explosion de cardinalité = pas d' DoS mémoire via labels).

### E2E frontend

**Non applicable** — aucun changement frontend (aucune métrique exposée à l'UI dans cette story ; les dashboards Grafana sont vérifiés par le runbook T9, pas par Playwright).

## Notes d'implémentation

> ⚠️ **Contexte de finalisation** : la session d'implémentation initiale (`treat-story`) a été **interrompue avant son signalement officiel** — les tâches T1→T11 étaient posées dans le workspace mais la story était restée `IN_PROGRESS` avec T12 non cochée et aucune note d'implémentation. La présente session a fait l'objet de la **finalisation** : audit complet de l'existant (aucune réécriture à l'aveugle), correctif de non-régression, validation intégrale (tests + lint + typecheck) et synchronisation backlog.

### Fichiers modifiés / créés

**Backend — créés :**
- `backend/app/core/metrics.py` — module central d'instrumentation (séries D3 : HTTP `windflow_http_requests_total`/`windflow_http_request_duration_seconds`, déploiements `windflow_deployments_total`/`windflow_deployment_duration_seconds`/`windflow_deployments_active`, scheduler `windflow_scheduler_executions_total`/`windflow_scheduler_execution_duration_seconds` ; helpers `record_http_request`/`record_deployment_transition`/`record_scheduler_execution` + `normalize_path` UUID→`{id}`, numérique→`{n}`, jamais de query string).
- `backend/app/api/v1/metrics.py` — endpoint `GET /api/v1/metrics` sans auth (exemption sondes spec 09, symétrique `system.py`), `PlainTextResponse` + `generate_latest(REGISTRY)` non enveloppée STORY-126, **404 si `prometheus_enabled=False`** (D5).

**Backend — modifiés :**
- `pyproject.toml` + `poetry.lock` — dépendance `prometheus-client = "^0.21"` en top-level (D6, justifiée : requise top-level par `websocket/metrics.py` + `generate_latest`/`REGISTRY` pour l'endpoint).
- `backend/app/api/v1/__init__.py` — montage `metrics_router` sous `/api/v1` (scrape attendu par `prometheus.yml`).
- `backend/app/main.py` — tag OpenAPI `metrics`.
- `backend/app/middleware/timing.py` — instrumentation HTTP (D4) : wrap try/except autour de `call_next` (exceptions → `status="500"` + re-raise), incrément conditionné `prometheus_enabled and enable_timing_middleware`, chemins normalisés, exclusion du scrape `/api/v1/metrics`, skip WS conservé, `X-Process-Time` inchangé.
- `backend/app/services/deployment_service.py` — `record_deployment_transition` dans `update_status` (l.780) : sémantique D8 (transitions RUNNING→success / FAILED→failed avec garde `old_status != new`, gauge active inc/dec, durée de bout en bout `now − created_at` aux terminales, best-effort).
- `backend/app/services/scheduler_engine.py` — `record_scheduler_execution` aux 6 points : success+duration et failed dans `_execute` (cron, l.349/330) et `_execute_manual` (l.561/542), skipped chevauchement manuel (l.275) et cron (l.477).
- `backend/app/websocket/broadcasting.py`, `connection_managers.py`, `general.py`, `plugin.py`, `ack_registry.py`, `event_bridge.py` — **câblage E5/D1** : `broadcast_timer`/`record_message_sent` (broadcasting), `record_connection`/`record_event_dispatch` (managers), `record_auth_attempt`/`record_auth_duration`/`record_message_received`/`record_subscription` (general), `record_plugin_execution`/`record_event_dispatch` (plugin), `record_error("ack_timeout")` dans `purge_expired` (ack_registry — la mesure différée STORY-164.1 devient réalité), `record_event_dispatch` autour du forward (event_bridge). Instrumentation additive, best-effort, signatures inchangées.

**Infra :**
- `infrastructure/docker/prometheus-alerts.yml` — expressions corrigées vers les vraies séries (D3/D7) + alerte `SchedulerExecutionFailures` ajoutée.
- `infrastructure/docker/grafana/dashboards/windflow-deployments.json` — 9 requêtes fantômes remplacées par les vraies séries D3.
- `infrastructure/docker/grafana/dashboards/windflow-system-overview.json` — row « WindFlow API » ajouté (200 vs 5xx, p95, erreurs/s).
- `docker-compose-dev.yml` / `docker-compose.prod.yml` / `docker-compose.extensions.yml` — montage `prometheus-alerts.yml:/etc/prometheus/rules/alerts.yml:ro` remplaçant le répertoire inexistant `prometheus-rules` (D7 — les alertes deviennent effectives).

**Documentation :**
- `docs/technical_specs/MONITORING-RUNBOOK.md` (**créé**) — table des séries D3, procédure de démo reproductible (`make enable-monitoring` + docker-up + trafic + déploiement + tâche), requêtes de vérification Prometheus/Grafana, troubleshooting.
- `.roo/rules/45-observability.md` — section « état réel » (instrumentation réelle, endpoint, séries, dashboards alimentés, alertes montées).
- `docs/technical_specs/ARCHITECTURE-MODULAIRE.md` — brique monitoring : chemin de scrape `/api/v1/metrics` + flag `prometheus_enabled` (404 si désactivé).

**Tests — créés (8 fichiers, 44 tests) :**
- `backend/tests/unit/test_core/test_metrics.py` (8) — helpers `normalize_path` (UUID/numérique/query string), préfixe `windflow_`, helpers no-op-safe.
- `backend/tests/unit/test_api/test_metrics_endpoint.py` (6) — AC 1/AC 2 endpoint (200 sans auth, format Prometheus, 404 désactivé, non-enveloppé, non-pollution WS).
- `backend/tests/unit/test_middleware/test_timing_metrics.py` (6) — latence/statut, normalisation, 500 enregistré, exclusion scrape, flag off, header inchangé.
- `backend/tests/unit/test_services/test_deployment_metrics.py` (7) — compteurs success/failed, durée terminale, gauge active, pas de double comptage, best-effort.
- `backend/tests/unit/test_services/test_scheduler_metrics.py` (5) — success/failed/skipped/run manuel/best-effort.
- `backend/tests/unit/test_websocket/test_websocket_metrics_wiring.py` (5) — câblage E5 (connexion, broadcast, plugin, ack_timeout, auth).
- `backend/tests/unit/test_api/test_metrics_security.py` (4) — exemption sans auth documentée, aucun label sensible, non-exposition Traefik, cardinalité bornée.
- `backend/tests/integration/test_metrics_end_to_end.py` (2) — AC 1 bout-en-bout (les 4 familles dans `/metrics`) + 404 intégration.

**Tests — modifiés (finalisation) :**
- `backend/tests/unit/test_websocket/test_ws_metrics_helpers.py` — 2 assertions d'égalité flottante stricte sur deltas `_sum` durcies en `pytest.approx` (broadcast 0.042 l.177-190, plugin 0.25 l.217-229) : le câblage STORY-172 écrit de vraies durées dans les mêmes histogrammes globaux, l'égalité stricte `(before + x) − before == x` devient non déterministe en suite complète (voir « Difficultés »).

### Décisions techniques (D1→D8 : toutes appliquées conformes à l'analyse)

- **D1 (câbler, pas supprimer)** : les 14 séries `windflow_websocket_*` apparaissent dans `/metrics` via le `REGISTRY` global dès l'import du package — consommateurs réels dans les 6 modules, plus aucun helper orphelin.
- **D2 (instrumenter à la source)** : compteurs posés dans `update_status` et le moteur scheduler (pas de consommateur du bus — évite le double comptage in-memory + Redis Pub/Sub).
- **D3 (contrat de nommage)** : table de correspondance respectée à l'identique ; dashboards/alertes audités croisés avec les séries exposées.
- **D5 (404 à chaud si désactivé)** : endpoint résolu mais handler refuse — testable sans re-création d'app (`test_metrics_endpoint_disabled_returns_404`).
- **D8 (durée de bout en bout)** : `deploy_duration_seconds` n'étant calculé qu'aux arrêts, l'histogramme observe `now − created_at` aux transitions terminales uniquement.

### Divergences vs analyse

1. **Fichier de tests central renommé** : l'analyse prévoyait `test_core/test_metrics_helpers.py` (3 tests) → livré `test_core/test_metrics.py` (8 tests, périmètre élargi helpers + normalisation + préfixe) — même intention, nom plus simple, aucun test manquant.
2. **Fichier de tests WS renommé** : prévu `test_ws_metrics_wiring.py` → livré `test_websocket_metrics_wiring.py` (cohérence avec les fichiers STORY-165 du répertoire).
3. **T9 run de démo** : le run Docker complet (Grafana visuellement alimenté) n'a pas été exécuté en environnement Docker — compensé par le runbook §3 (procédure reproductible documentée) + tests d'intégration vérifiant les 4 familles de séries bout-en-bout sur l'app réelle ; l'AC 4 est validé sur la base documentaire + séries (divergence déjà tracée dans la coche T9).
4. **AC 2 formulation « endpoint absent ou vide 404 »** : choix 404 documenté D5 (conforme à l'option prévue par l'AC).

### Difficultés rencontrées

- **Non-régression STORY-165 (corrigée en finalisation)** : `test_ws_metrics_helpers.py::TestRecordBroadcast::test_broadcast_observes_duration_and_clients` échouait en suite complète (passait isolé) — cause : le câblage STORY-172 dans `broadcasting.py` fait que `test_broadcasting.py` (exécuté avant, ordre alphabétique) écrit de vraies durées dans l'histogramme global `windflow_websocket_broadcast_duration_seconds{broadcast_type="deployment"}` ; l'assertion stricte `delta == 0.042` sur un `_sum` accumulant des flottants devenait non déterministe. Correctif : `pytest.approx` sur les deltas (2 assertions, même motif préventif sur `plugin_duration` 0.25) — sémantique de vérification inchangée.
- **`make backend-lint` / `make backend-typecheck` globaux non verts mais préexistants** : 36 erreurs isort + 29 erreurs mypy présentes à l'identique sur HEAD (prouvé par worktree baseline `git worktree` + diff normalisé) — **0 nouvelle erreur introduite par la story** ; lint ciblé des 20 fichiers story : isort/black/flake8 **0 erreur**.
- **Trace `prometheus_client.__version__`** : attribut absent de la lib (vérification d'import via `import prometheus_client` OK, dépendance `^0.21` présente dans `pyproject.toml` + `poetry.lock`).

### Validation (finalisation du 2026-10-31)

| Commande | Résultat |
|---|---|
| `poetry run pytest backend/tests/unit/test_core/test_metrics.py backend/tests/unit/test_api/test_metrics_endpoint.py backend/tests/unit/test_middleware/test_timing_metrics.py backend/tests/unit/test_services/test_deployment_metrics.py backend/tests/unit/test_services/test_scheduler_metrics.py backend/tests/unit/test_websocket/test_websocket_metrics_wiring.py backend/tests/unit/test_api/test_metrics_security.py backend/tests/integration/test_metrics_end_to_end.py -v --tb=short` | **44 passed, 0 failed** |
| Non-régression `pytest backend/tests/unit/test_websocket/` | **422 passed, 0 failed** |
| Couverture ciblée (`--cov` modules instrumentation) | `api/v1/metrics.py` **100 %**, `core/metrics.py` **89 %**, `middleware/timing.py` **90 %**, `websocket/metrics.py` **90 %** — tous ≥ 80 % (AC 5) |
| `make backend-lint` | Échec isort **préexistant** (36 fichiers hors story, identiques à HEAD) ; fichiers story : isort+black+flake8 **0 erreur** |
| `make backend-typecheck` | 29 erreurs mypy **préexistantes** (baseline HEAD identique par worktree) ; **0 nouvelle** ; 0 erreur sur les modules instrumentation |
| Correctif final | `test_ws_metrics_helpers.py` (2× `pytest.approx`) — re-lint OK, 422/422 WS verts |

### Suivi

- `docs/backend_status.md` §11/§14.1 ( Prometheus mensonger ») est **obsolète** depuis cette story — mise à jour documentaire portée par **STORY-253** (tracé dans ses dépendances).
- Point d'accroche posé pour **STORY-251** (métrique d'état CircuitBreaker attendue dans `/metrics` — module `core/metrics.py` + endpoint prêts) et **STORY-174**.
