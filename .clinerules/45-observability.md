# Observabilité (monitoring & logging)

## Logging
- format JSON structuré
- niveaux cohérents (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- correlation IDs pour tracing distribué
- pas de données sensibles dans les logs

## Métriques obligatoires
- latence endpoints
- taux d’erreur par service
- métriques business (déploiements ok/ko)

## Outils cibles
- Prometheus + Grafana
- Tracing : OpenTelemetry
