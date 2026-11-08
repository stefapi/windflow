# 20 — Architecture, API et intégrations (source de vérité)

## 1. Style

Monolithe modulaire : un dépôt, une base (SQLite par défaut, PostgreSQL optionnel), un backend FastAPI exécuté derrière Nginx/Compose. Pas de microservices. Principes : **API d'abord** (toute fonctionnalité est exposée via API REST avant d'être consommée par l'UI ou la CLI), séparation stricte des couches (`55` §2), notification d'événements (pas de sourçage d'événements), temps explicite, services stateless autant que possible (déploiement single-worker assumé, verrous anti-chevauchement scheduler).

## 2. API-first (obligatoire)

- Toute fonctionnalité est disponible via API REST avant UI/CLI/TUI ; l'UI et la CLI consomment l'API.
- OpenAPI/Swagger reste à jour avec un maximum de documentation et d'exemples ; tous les éléments sont couverts par Pydantic (schémas `*Request` / `*Response` / `*Update`).
- Pagination obligatoire pour les listes de plus de 20 éléments.
- Documentation API exposée : **Scalar** sur `/docs` (interface principale), **Swagger UI** sur `/swagger`, **ReDoc** sur `/redoc`.
- Le client TypeScript est **généré** depuis les routes backend (`make generate-api`) et régénéré dans le même changement que toute modification du contrat ; jamais édité à la main.

## 3. Bus d'événements

- Bus canonique `Bus` (`backend/app/core/events.py`) : `InMemoryEventBus` par défaut, `RedisPubSubEventBus` optionnel sur le canal unique `windflow:events` (STORY-162).
- **Redis Streams est hors périmètre** (arbitrage F6) — ne pas l'introduire sans décision explicite du propriétaire.
- Prévoir retry/backoff, idempotence et gestion d'erreurs robuste.

## 4. WebSocket

Module temps réel complet (`backend/app/websocket/`, détail en `21-realtime-websocket.md`) : terminal interactif, logs/stats conteneurs, logs de déploiement, pont événements backend → clients WebSocket, plugins (audit, notifications, subscription).

## 5. Middlewares

Les middlewares sont appliqués dans un ordre critique (documenté dans `backend/app/middleware/README.md`) :

| Middleware | Rôle |
| --- | --- |
| CORS | Gestion des origines cross-origin |
| Security headers | CSP configurable, HSTS, X-Frame-Options |
| Timing | Temps de réponse, seuil configurable `slow_request_threshold` |
| Correlation ID | Header `X-Correlation-ID` pour tracing distribué |
| Logging | Logging structuré des requêtes |
| Error handler | Gestion centralisée des erreurs |

## 6. Couches backend

- Routers `api/v1/` (un fichier par domaine, monté dans `main.py`) : déclarent les routes, valident par schémas, injectent les dépendances (`get_current_user`, `require_role(...)`), appellent un service, choisissent le statut HTTP. **Interdit** : logique métier ou requête SQL dans un router.
- Services `services/` (une classe, injection de dépendances, pas de singleton global sauf DB) : portent les règles métier et pilotent les transactions. **Interdit** : connaître HTTP (`HTTPException`) dans un service.
- Modèles `models/` (SQLAlchemy 2.0), schémas `schemas/` (Pydantic), tâches `tasks/`, handlers WebSocket `websocket/`, utilitaires purs `helper/` — détail en `55` §2.
- **Toujours** lever des exceptions de `core/exceptions.py` (`WindFlowException` et sous-classes), jamais des exceptions Python brutes dans les endpoints (`30` §5).
- Migrations Alembic dans `backend/alembic/versions/` ; jamais modifier les tables manuellement.

## 7. Résilience et performance

- Cache unifié `get_cache()` : Redis si configuré, sinon mémoire locale bornée avec fallback par opération (STORY-168).
- Circuit breaker **câblé** sur Docker, SSH et le registre de plugins (STORY-251) — séries `windflow_circuit_breaker_*` exposées via `/api/v1/metrics`.
- Latences cibles, timeouts et dégradation : `46-performance-resilience.md`.

## 8. Faire évoluer l'architecture

| Besoin | Patron imposé |
| --- | --- |
| Nouveau domaine | Router + service + modèles + schémas du domaine dans `backend/app/`, monté dans `main.py` |
| Nouvelle intégration externe | Service/adaptateur dédié avec doublure de test ; jamais d'appel direct dispersé dans les routers |
| Nouvelle famille de workload | `WorkloadAdapter` spécialisé (glossaire `03`, `docs/general_specs/02-familles-workloads.md`) |
| Nouvel événement temps réel | Publication via le bus `Bus` puis relayé par l'event bridge WebSocket (`21`) |
| Nouveau canal WebSocket | Handler dans `websocket/` avec `ensure_role_ws` (`40` §3) |

Contourner un patron (requête dans un endpoint, logique métier dans le frontend, appel direct à un provider LLM hors LiteLLM) est refusé en revue.

## 9. Concevoir et justifier une abstraction

Quand plusieurs besoins du même domaine répètent un mécanisme complexe, l'agent évalue une abstraction avant de prolonger les duplications (`01` §12). Comparer une simplification locale, un service partagé et un moteur si pertinent ; le nombre de répétitions n'est pas un seuil automatique. Décrire les cas concrets, ce qui varie, les invariants et le coût d'évolution.

Avant implémentation du mécanisme, définir ses entrées/sorties, erreurs, responsabilités, transactions et effets selon le risque. Éprouver la conception sur un premier parcours complet puis sur un cas différent avant généralisation. Ne pas créer un moteur universel par anticipation ni ajouter de couches sans variation démontrée.

Les décisions durables sur frontières, persistance, modèle d'exécution, contrats publics, sécurité ou dépendance importante sont soumises au propriétaire avant implémentation dépendante (décision consignée, `02` §2). Une extraction interne compatible n'exige pas d'arbitrage.
