# Architecture, API & intégrations

## API-first (obligatoire)
Toute fonctionnalité doit être exposée via API REST avant d'être consommée par UI/CLI/TUI.
- OpenAPI/Swagger doit rester à jour avec un maximum de documentation, examples
- tous les éléments sont couverts par pydantic
- Pagination obligatoire pour listes > 20 éléments.

### Documentation API

L'API expose trois interfaces de documentation automatique :
- **Scalar** sur `/docs` (interface principale)
- **Swagger UI** sur `/swagger`
- **ReDoc** sur `/redoc`

## Style d'architecture
- Modular monolith (modules cohérents, frontières claires).

## Event-driven
- Communication asynchrone via le bus canonique `Bus` (`backend/app/core/events.py`) : `InMemoryEventBus` par défaut, `RedisPubSubEventBus` optionnel sur le canal unique `windflow:events` (STORY-162).
- Redis Streams est **hors périmètre** (arbitrage F6) — ne pas l'introduire sans décision explicite.
- Prévoir retry/backoff, idempotence, et gestion d'erreurs robuste.

## WebSocket

Module complet temps réel via WebSocket :
- **Terminal** : connexion terminal interactif aux conteneurs
- **Container logs/stats** : flux de logs et statistiques en temps réel
- **Deployment logs** : suivi des déploiements en direct
- **Event bridge** : pont entre événements backend et clients WebSocket
- **Plugins** : audit, notifications, subscription

## Middlewares

Les middlewares sont appliqués dans un ordre critique (documenté dans `middleware/README.md`) :

| Middleware | Rôle |
|------------|------|
| CORS | Gestion des origines cross-origin |
| Security headers | CSP configurable, HSTS, X-Frame-Options |
| Timing | Mesure du temps de réponse, seuil configurable `slow_request_threshold` |
| Correlation ID | Header `X-Correlation-ID` pour tracing distribué |
| Logging | Logging structuré des requêtes |
| Error handler | Gestion centralisée des erreurs |

## Résilience & performance (attendu)
- Cache unifié (`get_cache()`) : Redis si configuré, sinon mémoire locale bornée avec fallback par opération (STORY-168)
- Rate limiting, circuit breaker, bulkhead, retries
- Circuit breaker **câblé** sur Docker, SSH et le registre de plugins (STORY-251) — séries `windflow_circuit_breaker_*` exposées via `/api/v1/metrics`
- Scalabilité horizontale, services stateless autant que possible (déploiement single-worker assumé, verrous anti-chevauchement scheduler)
