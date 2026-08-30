# STORY-100 : Auth WebSocket obligatoire — refus des connexions sans token valide sur les 5 canaux (P0-1)

**Statut :** TODO
**Epic Parent :** EPIC-011 — P0 : Sécurité bloquante
**Item plan :** P0-1 (rapport d'écart B1, §7 critique / §8) — ampleur **S**

## Description

En tant qu'administrateur sécurité de WindFlow, je veux que toutes les connexions WebSocket soient refusées sans JWT valide, afin d'empêcher tout accès anonyme aux flux temps réel (logs de déploiement, terminal de conteneur, logs/stats de conteneurs, canal général) qui exposent des données d'exploitation sensibles et permettent des commandes d'exécution.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §7.2, §14.2) : [`get_current_user_ws()`](../../backend/app/auth/dependencies.py:122) retourne `None` quand aucun token n'est fourni — comportement assumé dans sa docstring — si bien que les 5 canaux WS de [`websockets.py`](../../backend/app/api/v1/websockets.py:27) acceptent des connexions non authentifiées :

| Canal | Route |
|-------|-------|
| Général | `/api/v1/ws/` |
| Déploiements | `/api/v1/ws/deployments/{deployment_id}/logs` |
| Terminal | `/api/v1/ws/terminal/{container_id}` |
| Logs conteneur | `/api/v1/ws/docker/containers/{container_id}/logs` |
| Stats conteneur | `/api/v1/ws/docker/containers/{container_id}/stats` |

La spec exige l'inverse : « Toutes les connexions WebSocket nécessitent un token JWT passé en query parameter » (09-api.md §WebSocket). Le canal terminal donne un accès d'exécution — c'est la faille la plus critique du périmètre P0 avec les credentials en clair.

## Contexte technique

*(à remplir par analyse-story)*

Mécanismes d'auth existants à réutiliser (ne pas réécrire) :
- Query param `?token=` décodé via `decode_access_token()` ([`auth/jwt.py`](../../backend/app/auth/jwt.py:16)) ;
- Auth « JWT au premier message » avec timeout 30 s et close `1008` sur le canal général ([`websocket/general.py`](../../backend/app/websocket/general.py), documentée dans WEBSOCKET-REAL-TIME.md §7.1) ;
- Vérification d'accès organisationnel à la ressource sur le canal déploiement ([`websocket/deployment_logs.py`](../../backend/app/websocket/deployment_logs.py), WEBSOCKET-REAL-TIME.md §7.2) ;
- Mode dev `disable_auth` (auto-login premier superadmin) à préserver ;
- Garde-fou §2.G du plan : ne pas casser l'architecture plugins WS ([`websocket/plugin.py`](../../backend/app/websocket/plugin.py)) ni les middlewares sécurité.

## Critères d'acceptation (AC)

- [ ] AC 1 : [`get_current_user_ws()`](../../backend/app/auth/dependencies.py:122) ne retourne plus jamais d'utilisateur anonyme — sans token, token invalide, token expiré ou utilisateur inactif, la connexion est **refusée** (code HTTP 401 lors du handshake ou fermeture immédiate avec code 1008 « policy violation »), sur **chacun des 5 canaux** (`/ws/`, `/ws/deployments/{id}/logs`, `/ws/terminal/{id}`, `/ws/docker/containers/{id}/logs`, `/ws/docker/containers/{id}/stats`).
- [ ] AC 2 : Avec un JWT valide, chaque canal fonctionne exactement comme avant (non-régression des flux temps réel existants) ; le mode `disable_auth=true` continue d'accepter les connexions en développement (auto-login superadmin, comportement actuel préservé).
- [ ] AC 3 : Le mécanisme d'auth « JWT au premier message » du canal général (timeout 30 s, close 1008, `AUTH_LOGIN_SUCCESS`) reste fonctionnel et cohérent avec le nouveau refus strict — pas de double barrière contradictoire ni de canal contournable.
- [ ] AC 4 : Tests de sécurité obligatoires écrits et passants : `test_ws_connection_refused_without_token` (chacun des 5 canaux), `test_ws_connection_refused_with_invalid_token`, `test_ws_connection_accepted_with_valid_token`, `test_ws_connection_accepted_in_disable_auth_mode` — couverture ≥ 80 % sur les modules touchés (zone actuellement à 0 test, `backend_status.md` §13.4).
- [ ] AC 5 : Les garde-fous §2.G sont respectés : architecture plugins WS intacte (audit_logger, subscription, deployment_monitor, deployment_notifications), middlewares sécurité non régressés (`make lint` + `make backend-test` verts).

## Références spécification

- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) § WebSocket — « Toutes les connexions WebSocket nécessitent un token JWT passé en query parameter » ;
- [`docs/technical_specs/WEBSOCKET-REAL-TIME.md`](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) §7 « Authentification » (§7.1 JWT au premier message, §7.2 JWT en query parameter sur canaux dédiés) ;
- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) § Vue d'ensemble → Principes (« les tokens expirent », « sécurisé par défaut ») et § Authentification et RBAC — synthèse (« permissions vérifiées sur chaque endpoint API et chaque action WebSocket ») ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §7.2 (comportement `get_current_user_ws`), §14.2 (« WS auth tolérante ») ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 Vague P0 — item P0-1, §2.B — item B1.

## Dépendances

- Aucune (item racine de la vague P0 ; prérequis du canal WS durci P2-5 mais aucune dépendance descendante en P0).

## Sous-stories

*(section réservée — STORY-100 ampleur S, découpe non prévue a priori)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
