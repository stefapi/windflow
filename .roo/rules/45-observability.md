# Observabilité (monitoring & logging)

## Logging
- Python `logging` standard avec format JSON configurable (pas structlog)
- niveaux cohérents (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- pas de données sensibles dans les logs

### Correlation ID
- Middleware dédié (`correlation_middleware`)
- Header `X-Correlation-ID` propagé dans toute la chaîne
- Inclus dans les logs pour tracing distribué

### Timing middleware
- Middleware dédié (`timing_middleware`)
- Seuil configurable via `slow_request_threshold`
- Log automatique des requêtes lentes

## Métriques obligatoires
- latence endpoints
- taux d'erreur par service
- métriques business (déploiements ok/ko)

## Outils cibles

### Prometheus + Grafana (instrumentation réelle — STORY-172)
- `prometheus_enabled: bool = True` dans la configuration (`False` → endpoint `/api/v1/metrics` en 404, aucune instrumentation HTTP)
- Endpoint d'exposition : `GET /api/v1/metrics` **sans auth** (scrape interne Docker), format texte Prometheus, jamais enveloppé
- Définitions centrales dans `backend/app/core/metrics.py` (HTTP, déploiements ok/ko, exécutions scheduler) + `backend/app/websocket/metrics.py` (14 séries `windflow_websocket_*`), préfixe unique `windflow_`
- Labels sans données sensibles : chemins normalisés (UUID → `{id}`, numérique → `{n}`), jamais de query string
- Dashboards Grafana provisionnés dans `infrastructure/docker/grafana/dashboards/` (requêtes alignées sur les vraies séries)
- Configuration Prometheus dans `infrastructure/docker/prometheus.yml` (scrape `windflow-api`, `metrics_path: /api/v1/metrics`)
- Alertes définies dans `infrastructure/docker/prometheus-alerts.yml` (montées directement dans les 3 compose — `/etc/prometheus/rules/alerts.yml`)
- Procédure de démo/vérification : `docs/technical_specs/MONITORING-RUNBOOK.md`

### Tracing : OpenTelemetry
- ⚠️ **Prévu mais pas encore implémenté** (pas de dépendance, pas de tracing setup dans le code)
