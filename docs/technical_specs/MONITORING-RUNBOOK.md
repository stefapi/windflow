# Runbook Monitoring — Observabilité Prometheus réelle (STORY-172)

> Ce runbook documente l'observabilité **réelle** de WindFlow : l'endpoint
> d'exposition, le contrat exact des séries, la procédure de démo
> reproductible et les vérifications à effectuer. Il remplace le constat
> « Prometheus mensonger » (backend_status.md §11 — `prometheus_enabled=True`
> sans aucune instrumentation ; mise à jour documentaire portée par STORY-253).

## 1. Architecture de l'exposition

```
API WindFlow (uvicorn, port 8000)
  └── GET /api/v1/metrics            (sans auth — exemption sondes spec 09)
        PlainTextResponse generate_latest(REGISTRY)
        404 si prometheus_enabled=false
              ▲
              │ scrape 15s, réseau interne Docker uniquement
Prometheus (prometheus.yml — job "windflow-api")
  └── rules: /etc/prometheus/rules/alerts.yml   (prometheus-alerts.yml monté)
        ▲
Grafana (dashboards provisionnés windflow-*.json)
```

Fichiers de référence :

| Rôle | Fichier |
|---|---|
| Définitions centrales (HTTP/déploiements/scheduler) | `backend/app/core/metrics.py` |
| Définitions WebSocket (14 séries `windflow_websocket_*`) | `backend/app/websocket/metrics.py` |
| Endpoint d'exposition | `backend/app/api/v1/metrics.py` |
| Point de collecte HTTP (middleware Timing) | `backend/app/middleware/timing.py` |
| Config scrape Prometheus | `infrastructure/docker/prometheus.yml` |
| Règles d'alertes | `infrastructure/docker/prometheus-alerts.yml` |
| Dashboards provisionnés | `infrastructure/docker/grafana/dashboards/windflow-{deployments,system-overview}.json` |

**Sécurité** (rules 40, spec 15) : l'endpoint est **sans authentification**
par conception (scrape interne, symétrique de `/system/health`) et
**jamais exposé sur Internet** — aucun router Traefik ne matche
`/api/v1/metrics` (garanti par le test
`test_metrics_not_exposed_by_traefik_routers`). Aucune donnée sensible dans
les labels : ni query string, ni token, ni paramètre d'URL (chemins
normalisés UUID → `{id}`, numérique → `{n}` — cardinalité bornée).

## 2. Contrat des séries exposées (décision D3)

| Famille | Série (type) | Labels |
|---|---|---|
| HTTP | `windflow_http_requests_total` (Counter) | `method`, `path` (normalisé), `status` |
| HTTP | `windflow_http_request_duration_seconds` (Histogram) | `method`, `path` |
| Déploiements | `windflow_deployments_total` (Counter) | `result` ∈ `success` \| `failed` |
| Déploiements | `windflow_deployment_duration_seconds` (Histogram) | — |
| Déploiements | `windflow_deployments_active` (Gauge) | — |
| Scheduler | `windflow_scheduler_executions_total` (Counter) | `status` ∈ `success` \| `failed` \| `skipped` |
| Scheduler | `windflow_scheduler_execution_duration_seconds` (Histogram) | — |
| Résilience | `windflow_circuit_breaker_state` (Gauge — STORY-251) | `name` : 0=closed, 1=half_open, 2=open |
| Résilience | `windflow_circuit_breaker_failures_total` (Counter — STORY-251) | `name` (échecs cumulés comptés par le circuit) |
| WebSocket | `windflow_websocket_*` (14 séries : connexions, messages, broadcasts, plugins, auth, abonnements, erreurs) | cf. `app/websocket/metrics.py` |

Correspondance historique (dashboards/alertes corrigés en conséquence) :

| Ancien nom (fantôme) | Vraie série |
|---|---|
| `windflow_deployments_success_total` | `windflow_deployments_total{result="success"}` |
| `windflow_deployments_failed_total` | `windflow_deployments_total{result="failed"}` |
| `http_request_duration_seconds_bucket` | `windflow_http_request_duration_seconds_bucket` |
| `windflow_deployment_duration_seconds` (brute) | `windflow_deployment_duration_seconds_bucket` (histogram_quantile) |

Points d'instrumentation (décision D2 — à la source, pas via le bus) :

- **HTTP** : middleware Timing (`app/middleware/timing.py`) — compteur +
  latence par route normalisée, exceptions comptées `status="500"` puis
  re-levées ; le scrape `/api/v1/metrics` n'est pas compté ; actif seulement
  si `prometheus_enabled` **et** `enable_timing_middleware`.
- **Déploiements** : `DeploymentService.update_status` (l.~763) — transitions
  vers `running` → `success`, `failed` → `failed`, gauge active inc/dec,
  durée de bout en bout (`now − created_at`) observée aux transitions
  terminales.
- **Scheduler** : `scheduler_engine.py` — succès (`_execute`/`_execute_manual`,
  durée incluse), échec (les deux chemins), `skipped` (chevauchements cron l.466
  et manuel l.270).
- **WebSocket** : `broadcasting.py`, `connection_managers.py`, `general.py`,
  `plugin.py`, `ack_registry.py` (dégradation `ack_timeout` mesurée — série
  `windflow_websocket_errors_total{error_type="ack_timeout"}`),
  `event_bridge.py`.
- **Circuit breakers (STORY-251)** : `core/resilience.py` — chaque échec
  compté incrémente `windflow_circuit_breaker_failures_total{name}` ; chaque
  transition d'état (closed→open, open→half_open, half_open→closed) met à
  jour la gauge `windflow_circuit_breaker_state{name}` **et** loggue un
  enregistrement structuré (`extra` : `circuit`, `old_state`, `new_state`,
  `correlation_id` via contextvar STORY-251 D8). Circuits : `docker_engine`
  (verbes réseau des WorkloadAdapters), `plugin_registry` (fetch HTTP du
  registre — le fallback stale-while-error sert toujours `_last_good_index`
  après échec), `ssh:{host_id}` (UUID d'hôte stable — seuls les échecs
  transport exit 124/255 comptent, jamais les exit codes métier).
  Seuils configurés : `WINDFLOW_CIRCUIT_BREAKER_*` (`env.example`).
  Alerte : `WindflowCircuitBreakerOpen` (`state == 2` pendant 1 m,
  severity warning).

Tous les helpers sont **best-effort** (try/except) : une métrique en échec ne
casse jamais un déploiement, une exécution scheduler ou un broadcast.

**Vérification des séries breaker** (STORY-251) :

```bash
# État des circuits (0=closed, 1=half_open, 2=open) + échecs cumulés
curl -s http://localhost:8000/api/v1/metrics | grep windflow_circuit_breaker
# attendu : une ligne state par circuit déjà utilisé (les gauges n'apparaissent
# qu'après la première transition ou le premier échec compté) ;
# docker_engine apparaît dès le premier verbe réseau d'un adapter.
```

Réinitialisation : l'état des circuits est en mémoire process (un circuit
ouvert se referme de lui-même après `timeout` s + succès en demi-ouvert ;
redémarrer l'API réinitialise tous les circuits — chaque worker uvicorn
possède ses propres circuits, modular monolith, cf. README workloads).

## 3. Procédure de démo reproductible (AC 4)

### 3.1 Démarrage de la stack avec monitoring

```bash
make enable-monitoring   # active le profil Prometheus + Grafana
make docker-up           # démarre l'environnement dev (windflow-api inclus)
```

Vérifier que l'API est prête : `curl -f http://localhost:8000/api/v1/system/ready`.

### 3.2 Génération de trafic et d'événements métier

```bash
# 1) Trafic HTTP (login + lectures)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d 'username=admin&password=<mot de passe admin>' | jq -r '.data.access_token')
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/stacks > /dev/null
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/hosts > /dev/null

# 2) Un déploiement (transitions PENDING→DEPLOYING→RUNNING via l'API ou le seed)
#    → compteurs windflow_deployments_total{result=...} + gauge active + durée

# 3) Une exécution scheduler manuelle
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/schedules/{task_id}/run
#    → windflow_scheduler_executions_total{status=...} + durée
```

### 3.3 Vérifications

**Séries exposées par l'API** (toutes familles) :

```bash
curl -s http://localhost:8000/api/v1/metrics | grep '^windflow_' | cut -d'{' -f1 | sort -u
# attendu : au moins windflow_http_requests_total,
# windflow_http_request_duration_seconds_*, windflow_deployments_*,
# windflow_scheduler_executions_* et les windflow_websocket_* initialisées
```

**Cible scrape UP dans Prometheus** (UI `http://prometheus.localhost` ou
`http://localhost:9090`) :

```promql
up{job="windflow-api"}          # attendu : 1
```

**Requêtes des dashboards vérifiées** :

```promql
sum(windflow_deployments_total)                                         # total
windflow_deployments_active                                             # gauge active
windflow_deployments_total{result="success"}                            # ok
windflow_deployments_total{result="failed"}                             # ko
rate(windflow_deployments_total[5m])
histogram_quantile(0.95, rate(windflow_deployment_duration_seconds_bucket[5m]))
sum by (status) (rate(windflow_http_requests_total[5m]))                # 200 vs 5xx
histogram_quantile(0.95, sum by (le) (rate(windflow_http_request_duration_seconds_bucket[5m])))
sum(rate(windflow_http_requests_total{status=~"5.."}[5m]))              # erreurs/s
```

**Dashboards Grafana** (`http://grafana.localhost`, compte par défaut
admin/admin) : « WindFlow - Deployments » et « WindFlow - System Overview »
(row « WindFlow API ») affichent des données réelles sur le run de démo.

**Alertes évaluées** : `prometheus-alerts.yml` est monté directement dans
`/etc/prometheus/rules/alerts.yml` (les 3 compose) — vérifiable dans
l'UI Prometheus → Alerts (règles chargées, état `OK`/`Firing`).

### 3.4 Désactivation (AC 2)

```bash
PROMETHEUS_ENABLED=false  # .env / variable d'environnement du service api
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/api/v1/metrics
# attendu : 404 — plus aucune instrumentation HTTP ni exposition.
```

## 4. Troubleshooting

| Symptôme | Cause probable | Action |
|---|---|---|
| `/api/v1/metrics` → 404 | `prometheus_enabled=false` | Réactiver le flag |
| `up{job="windflow-api"} == 0` | API down ou chemin de scrape erroné | Vérifier `metrics_path: '/api/v1/metrics'` dans `prometheus.yml` |
| Alertes absentes de l'UI Prometheus | Règles non montées (ancien montage répertoire inexistant) | Vérifier le bind `prometheus-alerts.yml:/etc/prometheus/rules/alerts.yml` puis `docker compose restart prometheus` |
| Dashboards vides | Séries non encore scrapées (15 s) ou trafic nul | Générer du trafic (§3.2), vérifier le range temporel |
| Gauge active négative | Redémarrage API entre inc et dec (compteurs en mémoire process) | Comportement connu, single-worker (arbitrage F1) — la gauge se recale aux transitions |

## 5. Limites connues

- **Single-worker** (arbitrage F1) : les compteurs vivent en mémoire du
  process (`REGISTRY` global). Multi-instances = agrégation Prometheus
  requise ; `prometheus_multiproc_dir` reste non consommé (hors périmètre).
- **Gauge `windflow_deployments_active`** : approximation pilotée par
  `update_status` — un déploiement créé puis crashé avant toute transition
  n'est pas compté (documenté, décision D8).
- **Durées de déploiement** : observées **aux transitions terminales**
  uniquement (durée de bout en bout `now − created_at`), car
  `deploy_duration_seconds` n'est calculé qu'aux arrêts dans le service.
