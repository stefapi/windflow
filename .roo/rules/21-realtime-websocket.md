# 21 — Temps réel WebSocket (source de vérité)

> Prime sur toute mention du temps réel ailleurs dans ce corpus. Spécification détaillée : [`docs/technical_specs/WEBSOCKET-REAL-TIME.md`](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) (canaux, protocole, heartbeats, reconnexion) ; canaux canoniques : `docs/general_specs/09-api.md` ; événements plugins : `docs/general_specs/11-plugins.md`.

## 1. Rôle

Le WebSocket complète l'API REST pour tout ce qui ne peut pas passer par du polling : notifications push, streaming de logs, terminaux interactifs. Quatre familles d'usages :

| Famille | Handler | Contenu |
| --- | --- | --- |
| Terminal interactif | `websocket/terminal.py` (+ `ssh_session.py`, `host_access.py`) | Terminal attaché à un conteneur ou à un Host via SSH |
| Logs et stats conteneurs | `websocket/container_logs.py`, `container_stats.py` | Flux de logs et statistiques en temps réel |
| Logs de déploiement | `websocket/deployment_logs.py` | Suivi des déploiements en direct |
| Pont d'événements | `websocket/event_bridge.py`, `general.py` | Relais des événements du bus `Bus` vers les clients WebSocket |

Socle commun : `connection_managers.py`, `broadcasting.py`, `batch.py`, `heartbeat.py`, `ack_registry.py`, `journal.py`, `metrics.py`, `plugin.py` + plugins (`websocket/plugins/` : audit, notifications, subscription).

## 2. Deux couches d'événements

- **Bus applicatif `Bus`** (`core/events.py`) : événements métier internes au backend (`20` §3). Un service publie **après** validation de sa transaction.
- **Event bridge WebSocket** (`websocket/event_bridge.py`) : relaie les événements du bus vers les clients abonnés. **Interdit** : écrire directement dans une connexion WebSocket depuis un service ; passer par le pont.
- Le flux **notifie** ; l'API REST reste la source de vérité. À réception, le client frontend met à jour son état puis relit l'API quand nécessaire (« notifier puis relire »).

## 3. Authentification et droits

- Chaque canal WebSocket vérifie l'authentification et le rôle via `ensure_role_ws` / `require_role_ws` (`backend/app/auth/`) — même politique que les endpoints REST (`40` §3).
- Un canal sensible sans vérification de rôle alors que les endpoints équivalents en ont un est une escalade : à signaler en revue.
- L'accès terminal (`terminal.py`, `ssh_session.py`) suit les mêmes règles ; jamais de session SSH ouverte sans vérification préalable.

## 4. Protocole client

- Heartbeats (`heartbeat.py`) et reconnexion avec attente progressive côté frontend ; acknowledgment via `ack_registry.py`.
- Batching des messages fréquents (`batch.py`) : pas de spam de trames par événément unitaire quand un lot est possible.
- Un message invalide ne coupe jamais la boucle de lecture : journaliser, ignorer, continuer.

## 5. Métriques et limites

- 14 séries `windflow_websocket_*` exposées par `websocket/metrics.py` via `GET /api/v1/metrics` (`45` §4).
- Journalisation des connexions et canaux via `journal.py` ; le plugin audit trace les actions sensibles.
- Pas de données sensibles dans les charges d'événements ni dans les labels de métriques (`40` §6).

## 6. Anti-patterns refusés

Écrire dans une connexion hors des handlers du module ; publier un événement avant validation de la transaction ; polling périodique à la place du flux ; un canal WebSocket sans `ensure_role_ws` ; logique métier dans un gestionnaire WebSocket (elle appartient à un service) ; contourner le bus `Bus` avec un canal Redis parallèle.

## 7. Liste de contrôle d'une tâche temps réel

1. Handler ou extension dans `backend/app/websocket/` avec vérification de rôle.
2. Publication via le bus `Bus` après validation de la transaction, relayée par l'event bridge.
3. Côté frontend : composable/consommateur dédié, reprise sur reconnexion.
4. Tests : droits du canal (refus rôle insuffisant), publication après validation seulement, reprise après coupure, métriques à jour.
