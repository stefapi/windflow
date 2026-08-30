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

### Prometheus + Grafana
- `prometheus_enabled: bool = True` dans la configuration
- Dashboards Grafana provisionnés dans `infrastructure/docker/grafana/dashboards/`
- Configuration Prometheus dans `infrastructure/docker/prometheus.yml`
- Alertes définies dans `infrastructure/docker/prometheus-alerts.yml`

### Tracing : OpenTelemetry
- ⚠️ **Prévu mais pas encore implémenté** (pas de dépendance, pas de tracing setup dans le code)
