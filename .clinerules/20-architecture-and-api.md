# Architecture, API & intégrations

## API-first (obligatoire)
Toute fonctionnalité doit être exposée via API REST avant d’être consommée par UI/CLI/TUI.
- OpenAPI/Swagger doit rester à jour avec un maximum de documentation, examples
- tous les éléments sont couverts par pydantic
- Pagination obligatoire pour listes > 20 éléments.

## Style d’architecture
- Modular monolith (modules cohérents, frontières claires).

## Event-driven
- Communication asynchrone via Redis Streams quand approprié.
- Prévoir retry/backoff, idempotence, et gestion d’erreurs robuste.

## Résilience & performance (attendu)
- Cache (Redis) pour requêtes coûteuses
- Rate limiting, circuit breaker, bulkhead, retries
- Scalabilité horizontale, services stateless autant que possible
