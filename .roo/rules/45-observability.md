# 45 — Observabilité

## 1. Journaux

- Python `logging` standard avec format JSON configurable (pas structlog — `02` §8).
- Niveaux cohérents : `DEBUG` (développement seulement), `INFO` (fonctionnement normal), `WARNING` (anomalie récupérée), `ERROR` (opération échouée qui demande une action), `CRITICAL` (service inutilisable).
- **Jamais de données sensibles dans les logs** (`40` §6) : uniquement des identifiants (`user_id`, `request_id`, `correlation_id`).

## 2. Corrélation et temps de réponse

- Middleware `correlation_middleware` : header `X-Correlation-ID` propagé dans toute la chaîne, inclus dans les logs pour tracing distribué.
- Middleware `timing_middleware` : seuil configurable `slow_request_threshold`, log automatique des requêtes lentes.

## 3. Métriques obligatoires

- Latence des endpoints ; taux d'erreur par service ; métriques business (déploiements ok/ko).

## 4. Prometheus + Grafana (instrumentation réelle — STORY-172)

- `prometheus_enabled: bool = True` dans la configuration (`False` → endpoint `/api/v1/metrics` en 404, aucune instrumentation HTTP).
- Exposition : `GET /api/v1/metrics` **sans auth** (scrape interne Docker), format texte Prometheus, jamais enveloppé.
- Définitions centrales dans `backend/app/core/metrics.py` (HTTP, déploiements ok/ko, exécutions scheduler) + `backend/app/websocket/metrics.py` (14 séries `windflow_websocket_*`) ; préfixe unique `windflow_` ; séries circuit breaker `windflow_circuit_breaker_*` (STORY-251).
- Labels sans données sensibles : chemins normalisés (UUID → `{id}`, numérique → `{n}`), jamais de query string.
- Dashboards Grafana provisionnés dans `infrastructure/docker/grafana/dashboards/` (requêtes alignées sur les vraies séries) ; configuration Prometheus dans `infrastructure/docker/prometheus.yml` ; alertes dans `infrastructure/docker/prometheus-alerts.yml` (montées dans les 3 compose).
- Procédure de vérification : [`docs/technical_specs/MONITORING-RUNBOOK.md`](../../docs/technical_specs/MONITORING-RUNBOOK.md).

## 5. Tracing : OpenTelemetry

- ⚠️ **Prévu mais pas encore implémenté** (pas de dépendance, pas de tracing setup dans le code) — cible assumée, implémentation par une story du backlog (`02` §5).
